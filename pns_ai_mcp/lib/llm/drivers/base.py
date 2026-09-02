# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""
drivers/base.py — LLM Driver SPI (Service Provider Interface).

This module defines the contract that every LLM driver must implement.
A driver is a thin adapter between the PNS AI orchestrator and a remote
LLM API (OpenAI, Anthropic, or any OpenAI-compatible gateway).

Architecture
============

The system has three layers:

    ┌─────────────────────────────────────┐
    │  Odoo model (ai.provider)           │  ← UI, config, Odoo fields
    │  Odoo model (ai.execution.engine)   │  ← orchestration, tool loop
    └──────────────┬──────────────────────┘
                   │ get_llm_driver(protocol)
                   ▼
    ┌─────────────────────────────────────┐
    │  LLMDriver  (this interface)        │  ← SPI contract
    │    ├── OpenAIDriver                 │     HTTP POST + Bearer token
    │    ├── AnthropicDriver              │     HTTP POST + x-api-key
    │    └── OllamaDriver(OpenAIDriver)   │     Inherits OpenAI, defaults
    └─────────────────────────────────────┘

Driver lifecycle
================

1. **Registry**: drivers register themselves at import time::

       # In drivers/__init__.py:
       register_llm_driver('openai', OpenAIDriver)
       register_llm_driver('anthropic', AnthropicDriver)

2. **Instantiation**: the orchestrator calls ``get_llm_driver(protocol)``
   which returns a *fresh* driver instance (never shared between requests).

3. **Initialization**: the caller passes a config dict::

       driver.initialize({
           'protocol': 'openai',
           'endpoint': 'https://api.openai.com/v1/chat/completions',
           'api_key': 'sk-...',
           'model_name': 'gpt-4o-mini',
           'temperature': 0.7,
       })

4. **Inference**: ``driver.chat_completion(messages, tools=None, ...)``
   sends the request and returns an OpenAI-shaped response dict.

5. **Disposal**: drivers are ephemeral — no cleanup needed. The orchestrator
   creates a new instance for each request.


How to create a new driver
==========================

Minimal example — a hypothetical Gemini driver (if Google's API were NOT
OpenAI-compatible, which it actually is via their compatibility layer)::

    from .base import LLMDriver
    from .registry import register_llm_driver

    class GeminiDriver(LLMDriver):
        \"\"\"Google Gemini native API driver (hypothetical).\"\"\"

        @property
        def driver_name(self) -> str:
            return 'GeminiDriver'

        @property
        def model_name(self) -> str:
            return self._model

        def initialize(self, config):
            self._model = config.get('model_name', 'gemini-2.5-flash')
            self._api_key = config.get('api_key', '')
            self._endpoint = config.get('endpoint', '')
            self._temperature = config.get('temperature', 0.7)

        def chat_completion(self, messages, tools=None, **kwargs):
            # Convert OpenAI messages to Gemini format, POST, convert back
            ...
            return openai_shaped_response

        # format_messages, generate, parse_response, is_loaded:
        # return stubs if chat_completion is overridden directly.
        def format_messages(self, messages, tools=None): return ''
        def generate(self, prompt, **kw): return {}
        def parse_response(self, raw): return raw
        def is_loaded(self): return True

    # Register at import time:
    register_llm_driver('gemini', GeminiDriver)

In practice, most providers expose an OpenAI-compatible API (Ollama,
LMStudio, vLLM, Lemonade, AI Router, Groq, etc.). For those, just
subclass ``OpenAIDriver`` and override ``initialize()`` to set defaults::

    class LMStudioDriver(OpenAIDriver):
        \"\"\"LMStudio local server — same API as OpenAI.\"\"\"

        @property
        def driver_name(self):
            return 'LMStudioDriver'

        def initialize(self, config):
            cfg = dict(config or {})
            cfg.setdefault('endpoint',
                           'http://localhost:1234/v1/chat/completions')
            if not cfg.get('api_key'):
                cfg['api_key'] = 'lm-studio'  # dummy, required
            super().initialize(cfg)

    register_llm_driver('lmstudio', LMStudioDriver)


The two real driver families
============================

**OpenAI / OpenAI-compatible** (``OpenAIDriver``):

- Auth: ``Authorization: Bearer <api_key>``
- Endpoint: ``POST /v1/chat/completions``
- Models listing: ``GET /v1/models`` → ``{"data": [{"id": "gpt-4o"}, ...]}``
- Temperature: always supported, sent as ``"temperature": float``
- Tools: ``"tools": [...]`` + ``"tool_choice": "auto"``
  (vLLM/OVH requires explicit ``tool_choice`` or returns 422)
- Response: ``{"choices": [{"message": {"content": "...", "tool_calls": [...]}}]}``
- Covers: OpenAI, Azure OpenAI, Ollama, LMStudio, vLLM, Lemonade,
  AI Router, Groq, Together, DeepSeek, Fireworks, Google Gemini
  (via ``/v1beta/openai/`` compatibility layer)

**Anthropic Claude** (``AnthropicDriver``):

- Auth: ``x-api-key: <api_key>`` (NOT Bearer!)
  + mandatory ``anthropic-version: 2023-06-01`` header
- Endpoint: ``POST /v1/messages``
- Models listing: ``GET /v1/models`` → same OpenAI-like format
- Temperature: **some models reject it** (e.g. claude-3.5-sonnet in
  certain configurations). The driver has a ``probe_temperature()`` method
  that sends a 1-token test to detect this. When rejected, the parameter
  is omitted from all subsequent requests. The Odoo model caches this as
  ``temperature_support = 'yes' | 'no' | 'unknown'``.
- Tools: uses Anthropic's native tool format (converted from OpenAI schema
  by the driver before sending).
- Response: Anthropic returns ``{"content": [{"type": "text", "text": "..."}]}``
  which the driver converts to OpenAI-shaped ``{"choices": [...]}`` so the
  orchestrator always sees a uniform format.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional


class LLMDriver(ABC):
    """Abstract base for all LLM drivers.

    Every driver must implement at minimum:

    - ``driver_name`` (property): human-readable identifier (e.g. 'OpenAIDriver').
    - ``model_name`` (property): the LLM model string (e.g. 'gpt-4o-mini').
    - ``initialize(config)``: accept a config dict and store connection params.
    - ``chat_completion(messages, tools, ...)``: send inference request, return
      an **OpenAI-shaped** response dict (even for non-OpenAI providers).

    The ``format_messages``, ``generate``, ``parse_response`` methods exist
    for drivers that use a prompt-based (non-chat) API. Modern drivers that
    support a native chat endpoint should override ``chat_completion`` directly
    and leave those three as stubs.

    Config dict keys (passed to ``initialize``):

    =============================  ==========================================
    Key                            Description
    =============================  ==========================================
    ``protocol``                   Registry key (``'openai'``, ``'anthropic'``)
    ``endpoint``                   Full POST URL for chat completions
    ``api_key``                    Auth token (Bearer for OpenAI, x-api-key
                                   for Anthropic)
    ``model_name``                 Model identifier (``'gpt-4o'``, ``'claude-3.5-sonnet'``)
    ``temperature``                Float 0.0–2.0 (creativity control)
    ``send_temperature``           Bool — ``False`` to omit temperature
                                   (for models that reject it)
    ``context_window``             Int — max tokens for conversation memory
    ``extra_headers``              Dict — additional HTTP headers (e.g. MCP token)
    =============================  ==========================================

    The config keys mirror the ``ai.provider`` fields 1:1 (``protocol``,
    ``api_key``, ``model_name``, ``temperature``, ...): the caller just
    forwards the provider fields into this dict.

    Response contract (return value of ``chat_completion``):

    All drivers MUST return an OpenAI-shaped dict::

        {
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": "Hello!",         # text response (may be None if tool_calls)
                        "tool_calls": [               # optional
                            {
                                "id": "call_abc123",
                                "type": "function",
                                "function": {
                                    "name": "get_weather",
                                    "arguments": "{\"city\": \"Madrid\"}"
                                }
                            }
                        ]
                    }
                }
            ],
            "usage": {                                 # optional but recommended
                "prompt_tokens": 42,
                "completion_tokens": 15,
                "total_tokens": 57
            }
        }

    Non-OpenAI drivers (like Anthropic) must convert their native response
    to this shape before returning.
    """

    @property
    @abstractmethod
    def driver_name(self) -> str:
        """Human-readable driver identifier (e.g. ``'OpenAIDriver'``).

        Used in logs and diagnostics. Must be a short, stable string.
        """
        ...

    @property
    @abstractmethod
    def model_name(self) -> str:
        """The LLM model identifier as sent in API requests.

        Set during ``initialize()`` from ``config['model_name']``.
        Examples: ``'gpt-4o'``, ``'claude-3.5-sonnet'``, ``'llama3.2:3b'``.
        """
        ...

    @abstractmethod
    def initialize(self, config: Dict[str, Any]) -> None:
        """Accept configuration and prepare the driver for inference.

        Called exactly once per driver instance, immediately after
        ``get_llm_driver()`` creates it. The driver should store all
        connection parameters (endpoint, API key, model, temperature)
        as instance attributes.

        Args:
            config: Dict with keys documented in the class docstring above.

        Example::

            driver = get_llm_driver('openai')
            driver.initialize({
                'protocol': 'openai',
                'endpoint': 'https://api.openai.com/v1/chat/completions',
                'api_key': 'sk-...',
                'model_name': 'gpt-4o',
                'temperature': 0.7,
            })
        """
        ...

    @abstractmethod
    def format_messages(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None
    ) -> str:
        """Convert chat messages to a prompt string (legacy/prompt-based APIs).

        Modern drivers that override ``chat_completion()`` directly can
        return an empty string here. This method exists for drivers that
        use a raw text completion endpoint instead of a chat API.
        """
        ...

    @abstractmethod
    def generate(
        self,
        prompt: str,
        max_tokens: Optional[int] = None,
        temperature: float = 0.0,
        stop: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Send a raw prompt to the model (legacy/prompt-based APIs).

        Modern drivers that override ``chat_completion()`` directly can
        return an empty dict here.
        """
        ...

    @abstractmethod
    def parse_response(
        self,
        raw_response: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Convert a raw API response to the OpenAI-shaped standard format.

        Modern drivers that override ``chat_completion()`` directly can
        return the input unchanged here.
        """
        ...

    @abstractmethod
    def is_loaded(self) -> bool:
        """Return True if the driver is ready for inference.

        For HTTP-based drivers (all current ones), this always returns True
        after ``initialize()``. For hypothetical local model drivers that
        load weights into memory, this would return False until loading
        completes.
        """
        ...

    def chat_completion(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: float = 0.0,
        max_tokens: Optional[int] = None,
        tool_choice: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Send a chat completion request and return the response.

        This is the primary inference method. Most drivers override this
        to call their native HTTP API directly. The default implementation
        chains ``format_messages → generate → parse_response`` for
        prompt-based drivers.

        Args:
            messages: List of message dicts (OpenAI format)::

                [
                    {"role": "system", "content": "You are a helpful assistant."},
                    {"role": "user", "content": "Hello!"},
                ]

            tools: Optional list of tool definitions (OpenAI function calling format).
            temperature: Creativity control (0.0 = deterministic, 1.0 = creative).
            max_tokens: Maximum response length in tokens.
            tool_choice: Tool selection strategy (``"auto"``, ``"none"``, or
                         ``{"type": "function", "function": {"name": "..."}}``)

        Returns:
            OpenAI-shaped response dict (see class docstring for schema).

        Raises:
            RuntimeError: On HTTP errors, timeout, or invalid model.
        """
        prompt = self.format_messages(messages, tools)
        raw_response = self.generate(
            prompt,
            max_tokens=max_tokens,
            temperature=temperature,
            stop=self.get_stop_tokens()
        )
        return self.parse_response(raw_response)

    def get_stop_tokens(self) -> List[str]:
        """Return default stop sequences for prompt-based generation.

        Not used by modern chat API drivers. Override in subclasses that
        use raw text completion.
        """
        return ["<|end_of_text|>", "<|eot_id|>"]

    def models_url(self, endpoint: str) -> str:
        """Derive the ``GET /models`` URL from the chat completions endpoint.

        Used by ``ai.provider.action_fetch_models()`` to discover available
        models. Each driver family knows how to map its chat URL to the
        models listing URL.

        The default implementation handles OpenAI-compatible endpoints::

            https://api.openai.com/v1/chat/completions
            → https://api.openai.com/v1/models

        Override in subclasses with different URL patterns.

        Args:
            endpoint: The chat completions POST URL configured in the provider.

        Returns:
            The full URL for ``GET /models``.
        """
        if not endpoint:
            return 'https://api.openai.com/v1/models'
        base = endpoint.rstrip('/')
        for path in ('/api/v1/chat/completions', '/v1/chat/completions', '/chat/completions'):
            if path in base:
                base = base.split(path)[0].rstrip('/')
                break
        if base.endswith('/api/v1'):
            return '%s/models' % base
        if base.endswith('/v1'):
            return '%s/models' % base
        if '/api/v1/' in endpoint or endpoint.rstrip('/').endswith('/api/v1'):
            return '%s/api/v1/models' % base
        return '%s/v1/models' % base

    def auth_headers(self, api_key: str) -> Dict[str, str]:
        """Build the authentication headers for this provider.

        OpenAI-compatible providers use ``Authorization: Bearer <key>``.
        Anthropic uses ``x-api-key: <key>`` + ``anthropic-version`` header.

        Override in subclasses with different auth schemes.

        Args:
            api_key: The API key configured in the provider.

        Returns:
            Dict of HTTP headers to include in requests.

        Example (OpenAI, default)::

            {'Authorization': 'Bearer sk-...'}

        Example (Anthropic, overridden)::

            {'x-api-key': 'sk-ant-...', 'anthropic-version': '2023-06-01'}
        """
        headers = {}
        if api_key:
            headers['Authorization'] = 'Bearer %s' % api_key
        return headers
