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

class AnthropicDriver(LLMDriver):
    """Driver for Anthropic Claude Messages API.

    This driver handles the Anthropic-specific protocol, which differs from
    OpenAI in several critical ways. All differences are handled internally;
    the orchestrator always sees OpenAI-shaped responses.

    Authentication (different from OpenAI!)
    ----------------------------------------
    Anthropic does NOT use ``Authorization: Bearer``. Instead::

        x-api-key: <api_key>
        anthropic-version: 2023-06-01    ← mandatory, or 400 error

    Both headers are always sent. The version string is hardcoded to the
    latest stable API version.

    Endpoint
    --------
    ``POST /v1/messages`` (not ``/v1/chat/completions``)::

        https://api.anthropic.com/v1/messages          ← Anthropic direct
        https://<router>/v1/messages                   ← via AI Router

    Model listing
    -------------
    Uses the same ``GET /v1/models`` pattern as OpenAI. The ``ai.provider``
    Odoo model derives the URL by stripping ``/messages`` and appending
    ``/models``.

    Temperature quirk
    -----------------
    **Some Anthropic models reject the ``temperature`` parameter entirely**
    (HTTP 400: "temperature ... not supported / deprecated / not allowed").

    This driver includes a ``probe_temperature()`` method that sends a
    minimal 1-token request WITH temperature to detect whether the model
    accepts it. The result is cached in the Odoo ``ai.provider`` record
    as ``temperature_support = 'yes' | 'no' | 'unknown'``.

    When ``config['send_temperature']`` is ``False``, the ``temperature``
    key is omitted from the API request payload entirely.

    Message format conversion
    -------------------------
    Anthropic messages use a different structure than OpenAI:

    **OpenAI format** (what the orchestrator sends)::

        {"role": "user", "content": "Hello!"}

    **Anthropic format** (what this driver converts to)::

        {"role": "user", "content": [{"type": "text", "text": "Hello!"}]}

    The ``system`` role is extracted and sent as a top-level ``system``
    parameter (Anthropic does not accept it inside the messages array).

    Tool format conversion
    ----------------------
    OpenAI tool schema → Anthropic tool schema (different key names).
    Anthropic tool results use ``"type": "tool_result"`` blocks instead of
    OpenAI's ``"role": "tool"`` messages.

    Response normalization
    ----------------------
    Anthropic returns::

        {
            "content": [{"type": "text", "text": "Hello!"}],
            "usage": {"input_tokens": 10, "output_tokens": 5}
        }

    This driver converts it to OpenAI-shaped::

        {
            "choices": [{"message": {"role": "assistant", "content": "Hello!"}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}
        }
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
        # Algunos modelos recientes rechazan `temperature`. El proveedor cachea esa
        # capacidad (sonda) y la pasa aqui: si es False, no se envia el parametro.
        self.send_temperature = bool(config.get("send_temperature", True))
        self.extra_headers = config.get("extra_headers", {})
        self._model_name_internal = config.get("model_name", "gpt-4o-mini")
        self.context_window = int(config.get("context_window", 16384))

    @property
    def driver_name(self) -> str:
        return "AnthropicDriver"

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

    def models_url(self, endpoint):
        """Anthropic models URL — strips ``/messages`` instead of ``/chat/completions``.

        Example::

            https://api.anthropic.com/v1/messages  →  https://api.anthropic.com/v1/models
        """
        if not endpoint:
            return 'https://api.anthropic.com/v1/models'
        base = endpoint.rstrip('/')
        for path in ('/v1/messages', '/api/v1/chat/completions', '/v1/chat/completions', '/chat/completions'):
            if path in base:
                base = base.split(path)[0].rstrip('/')
        if base.endswith('/v1'):
            return '%s/models' % base
        return '%s/v1/models' % base

    def auth_headers(self, api_key):
        """Anthropic auth — ``x-api-key`` + ``anthropic-version`` (NOT Bearer!).

        Example::

            {'x-api-key': 'sk-ant-...', 'anthropic-version': '2023-06-01'}
        """
        headers = {}
        if api_key:
            headers['x-api-key'] = api_key
        headers['anthropic-version'] = '2023-06-01'
        return headers

    def chat_completion(self, messages, tools=None, **kwargs):
        temp = kwargs.get('temperature', self.temperature)
        tool_choice = kwargs.get('tool_choice')
        timeout = kwargs.get('timeout', LLM_HTTP_DEFAULT)
        return self._anthropic_chat(messages, tools, temperature=temp, tool_choice=tool_choice, timeout=timeout)

    def probe_temperature(self, timeout=15):
        """Sonda mínima: ¿acepta este modelo el parámetro `temperature`?

        Envía una petición de 1 token con `temperature`. Devuelve:
          • True  -> el modelo acepta temperature (HTTP 200).
          • False -> el modelo la rechaza (HTTP 400 'temperature ... deprecated/
                     not supported/unsupported/not allowed').
        Para cualquier otro fallo (credenciales, modelo inválido, red) lanza
        RuntimeError con el mensaje real, para que el llamador lo distinga de
        un veredicto de la sonda.
        """
        headers = {
            "Content-Type": "application/json",
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
        }
        headers.update(self.extra_headers or {})
        headers = {k: v for k, v in headers.items() if v is not None}
        payload = {
            "model": self.model_name,
            "messages": [{"role": "user", "content": [{"type": "text", "text": "ping"}]}],
            "max_tokens": 1,
            "temperature": self.temperature if self.temperature is not None else 0.0,
        }
        response = requests.post(self.endpoint, headers=headers, json=payload, timeout=timeout)
        if response.status_code == 200:
            return True
        text = (response.text or "").lower()
        if response.status_code == 400 and "temperature" in text and (
            "deprecated" in text
            or "not supported" in text
            or "unsupported" in text
            or "not allowed" in text
        ):
            return False
        # Otro error: extraer el mensaje real de Anthropic y relanzarlo.
        err_msg = response.text
        try:
            body = response.json()
            if isinstance(body, dict):
                err = body.get("error", body)
                if isinstance(err, dict):
                    err_msg = err.get("message") or response.text
        except Exception:
            pass
        raise RuntimeError("HTTP %s: %s" % (response.status_code, err_msg))

    def _anthropic_chat(self, messages, tools, temperature=None, tool_choice=None, timeout=LLM_HTTP_DEFAULT):
        headers = {
            "Content-Type": "application/json",
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "anthropic-beta": "prompt-caching-2024-07-31"
        }
        headers.update(self.extra_headers)
        headers = {k: v for k, v in headers.items() if v is not None}
        
        # Anthropic separates system prompt
        system_prompt = ""
        anthropic_messages = []
        for msg in messages:
            role = msg.get("role")
            if role == "system":
                system_prompt += msg.get("content", "") + "\n"
            elif role == "user":
                content = msg.get("content", "")
                # Anthropic rejects text blocks with only whitespace — skip empty user messages
                if isinstance(content, str) and not content.strip():
                    continue
                     
                block = {"type": "text", "text": str(content)}
                if anthropic_messages and anthropic_messages[-1]["role"] == "user":
                    anthropic_messages[-1]["content"].append(block)
                else:
                    anthropic_messages.append({"role": "user", "content": [block]})
            elif role == "assistant":
                content_blocks = []
                content = msg.get("content", "")
                if content:
                    content_blocks.append({"type": "text", "text": str(content)})
                
                if msg.get("tool_calls"):
                    for tc in msg.get("tool_calls"):
                        if tc.get("type") == "function":
                            fn = tc.get("function", {})
                            import json
                            args_str = fn.get("arguments", "{}")
                            try:
                                input_dict = json.loads(args_str)
                            except:
                                input_dict = {}
                            content_blocks.append({
                                "type": "tool_use",
                                "id": tc.get("id"),
                                "name": fn.get("name"),
                                "input": input_dict
                            })
                # Anthropic rejects text blocks with only whitespace — only add text block if
                # content is non-empty and non-whitespace. If no content and no tool_calls,
                # skip this assistant turn entirely (avoids invalid empty text blocks in history).
                if not content_blocks:
                    continue
                    
                anthropic_messages.append({"role": "assistant", "content": content_blocks})
            elif role == "tool":
                tool_result_content = msg.get("content", "")
                tool_call_id = msg.get("tool_call_id", "")
                
                # Tool content may come as an MCP list: [{"type": "text", "text": "..."}]
                # Extract text from it to get a plain string for Anthropic's tool_result block
                if isinstance(tool_result_content, list):
                    extracted = ""
                    for item in tool_result_content:
                        if isinstance(item, dict) and item.get("type") == "text":
                            extracted += item.get("text", "")
                        else:
                            extracted += str(item)
                    tool_result_content = extracted or " "
                else:
                    tool_result_content = str(tool_result_content) if tool_result_content else " "
                
                block = {
                    "type": "tool_result",
                    "tool_use_id": tool_call_id,
                    "content": str(tool_result_content)
                }
                
                if anthropic_messages and anthropic_messages[-1]["role"] == "user":
                    anthropic_messages[-1]["content"].append(block)
                else:
                    anthropic_messages.append({"role": "user", "content": [block]})
                
        payload = {
            "model": self.model_name,
            "messages": anthropic_messages,
            "max_tokens": 4096,
        }
        if getattr(self, "send_temperature", True):
            payload["temperature"] = temperature if temperature is not None else self.temperature
        if system_prompt:
            payload["system"] = [
                {
                    "type": "text",
                    "text": system_prompt.strip(),
                    "cache_control": {"type": "ephemeral"}
                }
            ]
            
        if tools:
            anthropic_tools = []
            for t in tools:
                # Support TWO formats:
                # 1. OpenAI-wrapped: {"type": "function", "function": {"name": ..., "parameters": ...}}
                # 2. Raw MCP format: {"name": ..., "description": ..., "inputSchema": {...}}
                # LocalMCPClient.list_tools() returns format #2.
                if t.get("type") == "function":
                    fn = t.get("function", {})
                    params = fn.get("parameters") or {"type": "object", "properties": {}}
                    if not isinstance(params, dict):
                        params = {"type": "object", "properties": {}}
                    anthropic_tools.append({
                        "name": fn.get("name"),
                        "description": fn.get("description") or "",
                        "input_schema": params
                    })
                elif t.get("name"):
                    # Raw MCP format: {name, description, inputSchema}
                    params = t.get("inputSchema") or t.get("parameters") or {"type": "object", "properties": {}}
                    if not isinstance(params, dict):
                        params = {"type": "object", "properties": {}}
                    anthropic_tools.append({
                        "name": t.get("name"),
                        "description": t.get("description") or "",
                        "input_schema": params
                    })
            
            # Only set tools and tool_choice if list is actually non-empty.
            # Anthropic rejects tool_choice when tools = []
            if anthropic_tools:
                payload["tools"] = anthropic_tools
                if tool_choice:
                    if tool_choice == "required":
                        payload["tool_choice"] = {"type": "any"}
                    elif tool_choice == "auto":
                        payload["tool_choice"] = {"type": "auto"}
                    elif isinstance(tool_choice, dict) and "function" in tool_choice:
                        payload["tool_choice"] = {"type": "tool", "name": tool_choice["function"]["name"]}
            
        _logger.info("AnthropicDriver request to %s model %s", self.endpoint, self.model_name)
        response = requests.post(self.endpoint, headers=headers, json=payload, timeout=timeout)

        # Algunos modelos recientes (p.ej. los de razonamiento) rechazan el parametro
        # `temperature`. En lugar de hardcodear que modelos lo soportan, detectamos el
        # rechazo y reintentamos una sola vez sin ese campo (agnostico al modelo).
        if response.status_code == 400 and "temperature" in payload:
            _retry_text = (response.text or "").lower()
            if "temperature" in _retry_text and (
                "deprecated" in _retry_text
                or "not supported" in _retry_text
                or "unsupported" in _retry_text
                or "not allowed" in _retry_text
            ):
                _logger.warning(
                    "AnthropicDriver: el modelo %s rechaza 'temperature'; reintentando sin ese parametro",
                    self.model_name,
                )
                payload.pop("temperature", None)
                response = requests.post(self.endpoint, headers=headers, json=payload, timeout=timeout)

        if response.status_code != 200:
            # Surface Anthropic's real error message instead of the opaque
            # "400 Bad Request" produced by raise_for_status(). Anthropic shape:
            #   {"type":"error","error":{"type":"invalid_request_error","message":".."}}
            err_body = None
            try:
                err_body = response.json()
            except Exception:
                err_body = None

            err_type = ""
            err_msg = response.text
            if isinstance(err_body, dict):
                err = err_body.get("error", err_body)
                if isinstance(err, dict):
                    err_type = err.get("type", "") or ""
                    err_msg = err.get("message") or response.text
                elif isinstance(err, str):
                    err_msg = err or response.text

            _logger.error(
                "AnthropicDriver HTTP %s from %s (model %s): %s",
                response.status_code, self.endpoint, self.model_name, err_msg,
            )

            # Billing/credit issues are reported by Anthropic as a 400, which is
            # confusing. Give an actionable hint pointing to the account, not the config.
            low_text = (err_msg or "").lower()
            if "credit balance" in low_text or "billing" in low_text:
                raise RuntimeError(
                    "Anthropic: la cuenta no tiene saldo suficiente. "
                    "Revisa Plans & Billing en console.anthropic.com (la API key es valida). "
                    "Detalle: %s" % err_msg
                )

            # Invalid/deprecated model
            if response.status_code == 400 and (
                "model" in low_text and ("not found" in low_text or "does not exist" in low_text)
                or (err_type == "invalid_request_error" and self.model_name in (err_msg or ""))
            ):
                raise RuntimeError(
                    "Modelo '%s' no valido o no disponible en Anthropic. "
                    "Actualiza el proveedor en Odoo. Detalle: %s" % (self.model_name, err_msg)
                )

            raise RuntimeError(
                "HTTP %s from %s: %s" % (response.status_code, self.endpoint, err_msg)
            )
            
        data = response.json()
        
        # Translate back to OpenAI format so standard parser works
        return self._translate_anthropic_to_openai(data)

    def _translate_anthropic_to_openai(self, data):
        """Translates Anthropic response to standard OpenAI format"""
        role = data.get("role", "assistant")
        content = ""
        tool_calls = []
        
        for block in data.get("content", []):
            if block.get("type") == "text":
                content += block.get("text", "")
            elif block.get("type") == "tool_use":
                tool_calls.append({
                    "id": block.get("id"),
                    "type": "function",
                    "function": {
                        "name": block.get("name"),
                        "arguments": json.dumps(block.get("input", {}))
                    }
                })
                
        message = {"role": role, "content": content}
        if tool_calls:
            message["tool_calls"] = tool_calls
            
        return {
            "id": data.get("id", str(uuid.uuid4())),
            "model": data.get("model", self.model_name),
            "choices": [{
                "index": 0,
                "message": message,
                "finish_reason": "tool_calls" if tool_calls else "stop"
            }],
            "usage": {
                "prompt_tokens": data.get("usage", {}).get("input_tokens", 0),
                "completion_tokens": data.get("usage", {}).get("output_tokens", 0),
                "total_tokens": data.get("usage", {}).get("input_tokens", 0) + data.get("usage", {}).get("output_tokens", 0)
            }
        }
