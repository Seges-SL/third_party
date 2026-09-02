# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
import json
import logging
import requests
import uuid
from .base import LLMDriver
from ..utils.timeouts import LLM_HTTP_DEFAULT, LLM_HTTP_RETRY  # noqa: F401 (LLM_HTTP_RETRY available for callers)

_logger = logging.getLogger(__name__)

class OpenAIDriver(LLMDriver):
    """Driver for OpenAI and all OpenAI-compatible HTTP APIs.

    This is the *default* driver and covers the majority of providers:

    ========================  ==============================================
    Provider                  Endpoint shape
    ========================  ==============================================
    OpenAI (native)           ``https://api.openai.com/v1/chat/completions``
    Azure OpenAI              ``https://<resource>.openai.azure.com/openai/deployments/<model>/chat/completions``
    Ollama (local)            ``http://localhost:11434/v1/chat/completions``
    LMStudio (local)          ``http://localhost:1234/v1/chat/completions``
    Lemonade (local)          ``http://localhost:13305/api/v1/chat/completions``
    vLLM                      ``http://<host>:8000/v1/chat/completions``
    Groq                      ``https://api.groq.com/openai/v1/chat/completions``
    Google Gemini (compat)    ``https://generativelanguage.googleapis.com/v1beta/openai/chat/completions``
    AI Router (PNS)           ``https://<host>/api/v1/chat/completions``
    ========================  ==============================================

    Authentication
    --------------
    All OpenAI-compatible providers use ``Authorization: Bearer <api_key>``.
    The key comes from ``config['api_key']`` during ``initialize()``.

    Model listing
    -------------
    The ``ai.provider`` Odoo model derives the models URL from the chat
    endpoint by replacing ``/chat/completions`` with ``/models``::

        POST https://api.openai.com/v1/chat/completions  →  chat
        GET  https://api.openai.com/v1/models             →  model list

    Response: ``{"data": [{"id": "gpt-4o"}, {"id": "gpt-4o-mini"}, ...]}``

    Tool calling
    ------------
    Tools are sent as ``"tools": [...]`` in the request payload.
    **Important**: some gateways (vLLM, OVH) return HTTP 422 if ``tools``
    is present but ``tool_choice`` is absent. This driver always sends
    ``"tool_choice": "auto"`` when tools are provided.

    Temperature
    -----------
    Always sent. All OpenAI-compatible APIs accept the ``temperature``
    parameter (unlike Anthropic which may reject it for certain models).

    Error handling
    --------------
    Error payloads vary wildly across gateways:

    - OpenAI/vLLM: ``{"error": {"code": "..", "message": "..", "type": ".."}}``
    - nginx/local: ``{"error": "Unauthorized. Bearer token required."}``
    - bare string: ``"some error"``

    The driver normalizes all shapes before raising ``RuntimeError``, so
    the orchestrator always gets a clean error message.
    """
    
    def __init__(self):
        super().__init__()
        self.endpoint = ""
        self.protocol = "openai"
        self.api_key = ""
        self.temperature = 0.7
        self.extra_headers = {}

    def initialize(self, config):
        # The base.py LLMDriver requires us to implement this if it was abstract, though base initialize is often just `pass`. 
        # We handle config here.
        # super().initialize(config) # base initialize is abstract but empty usually, let's not call it just in case
        self.protocol = config.get("protocol", "openai")
        self.endpoint = config.get("endpoint", "")
        self.api_key = config.get("api_key", "")
        self.temperature = float(config.get("temperature", 0.7))
        self.extra_headers = config.get("extra_headers", {})
        self._model_name_internal = config.get("model_name", "gpt-4o-mini")
        self.context_window = int(config.get("context_window", 16384))

    @property
    def driver_name(self) -> str:
        return "OpenAIDriver"

    @property
    def model_name(self) -> str:
        return getattr(self, '_model_name_internal', 'gpt-4o-mini')

    @property
    def _n_ctx(self) -> int:
        return getattr(self, 'context_window', 16384)

    def is_loaded(self) -> bool:
        return True

    def format_messages(self, messages, tools=None) -> str:
        # Not used natively since we override chat_completion
        return ""

    def generate(self, prompt, max_tokens=None, temperature=0.0, stop=None):
        # Not used natively since we override chat_completion
        return {}

    def parse_response(self, raw_response):
        # Not used natively since we override chat_completion
        return raw_response

    def chat_completion(self, messages, tools=None, **kwargs):
        temp = kwargs.get('temperature', self.temperature)
        tool_choice = kwargs.get('tool_choice')
        timeout = kwargs.get('timeout', LLM_HTTP_DEFAULT)
        return self._openai_chat(messages, tools, temperature=temp, tool_choice=tool_choice, timeout=timeout)
            
    def _openai_chat(self, messages, tools, temperature=None, tool_choice=None, timeout=LLM_HTTP_DEFAULT):
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        headers.update(self.extra_headers)
        
        # Ensure we don't have None values in headers
        headers = {k: v for k, v in headers.items() if v is not None}
        
        payload = {
            "model": self.model_name,
            "messages": messages,
            "temperature": temperature if temperature is not None else self.temperature,
        }
        if tools:
            payload["tools"] = tools
            # Always set tool_choice when tools are present.
            # OVH/vLLM returns 422 if tools are sent without explicit tool_choice.
            if tool_choice:
                payload["tool_choice"] = tool_choice
            else:
                payload["tool_choice"] = "auto"

        _logger.info("OpenAIDriver request to %s model %s", self.endpoint, self.model_name)
        response = requests.post(self.endpoint, headers=headers, json=payload, timeout=timeout)
        
        if response.status_code != 200:
            err_body = None
            try:
                err_body = response.json()
            except Exception:
                err_body = None

            # The error payload is wildly inconsistent across gateways:
            #  - OpenAI/vLLM:  {"error": {"code": .., "message": .., "type": ..}}
            #  - nginx/local:  {"error": "Unauthorized. Bearer token required."}
            #  - bare string:  "some error"
            # Normalise all shapes so we never crash parsing the very message
            # that explains why the call failed (this used to surface the
            # useless "'str' object has no attribute 'get'").
            err_code = ""
            err_type = ""
            err_msg = response.text
            if isinstance(err_body, dict):
                err = err_body.get("error", err_body)
                if isinstance(err, dict):
                    err_code = err.get("code", "") or ""
                    err_type = err.get("type", "") or ""
                    err_msg = err.get("message") or response.text
                elif isinstance(err, str):
                    err_msg = err or response.text
            elif isinstance(err_body, str):
                err_msg = err_body or response.text

            # Diagnóstico específico: modelo inválido o deprecado
            if response.status_code == 400 and (
                err_code in ("model_not_found", "invalid_model")
                or "does not exist" in err_msg
                or "deprecated" in err_msg.lower()
                or (err_type == "invalid_request_error" and self.model_name in err_msg)
            ):
                raise RuntimeError(
                    f"Modelo '{self.model_name}' no válido o deprecado en OpenAI. "
                    f"Actualiza la configuración del proveedor en Odoo (Settings → AI Providers). "
                    f"Detalle: {err_msg}"
                )

            _logger.error(
                "OpenAIDriver HTTP %s from %s (model %s): %s",
                response.status_code, self.endpoint, self.model_name, err_msg,
            )
            raise RuntimeError(
                "HTTP %s from %s: %s" % (response.status_code, self.endpoint, err_msg)
            )

        return response.json()
