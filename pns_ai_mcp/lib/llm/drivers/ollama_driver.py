# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""
ollama_driver.py — Example of a minimal OpenAI-compatible driver.

This file serves as **documentation by example**. Ollama exposes the exact
same HTTP API as OpenAI (``/v1/chat/completions``), so this driver only
needs to:

1. Subclass ``OpenAIDriver`` (inherits all HTTP logic).
2. Override ``initialize()`` to set sensible defaults.
3. Register itself with ``register_llm_driver('ollama', OllamaDriver)``.

That's it. No new HTTP code, no format conversion, no response parsing.

How to create a driver for YOUR OpenAI-compatible provider
==========================================================

If your provider exposes ``/v1/chat/completions`` with the same request/
response format as OpenAI, you can create a driver in ~15 lines::

    # my_provider_driver.py
    from .openai_driver import OpenAIDriver

    class MyProviderDriver(OpenAIDriver):
        \"\"\"My custom LLM gateway.\"\"\"

        @property
        def driver_name(self) -> str:
            return 'MyProviderDriver'

        def initialize(self, config):
            cfg = dict(config or {})
            # Set defaults for your provider:
            cfg.setdefault('endpoint', 'http://my-server:8080/v1/chat/completions')
            if not cfg.get('api_key'):
                cfg['api_key'] = 'dummy'  # local server, no auth
            super().initialize(cfg)

    # Then in drivers/__init__.py, add:
    #   from .my_provider_driver import MyProviderDriver
    #   register_llm_driver('my_provider', MyProviderDriver)

When do you need a FULL custom driver?
======================================

Only when the provider uses a **different API format** than OpenAI.
Currently, the only such case is Anthropic (different auth headers,
different message format, different tool schema, temperature quirk).

If your provider uses OpenAI's format (which most do — vLLM, Groq,
LMStudio, Lemonade, Together, Fireworks, DeepSeek, Google Gemini via
compat layer, etc.), just subclass ``OpenAIDriver`` as shown above.
"""

from .openai_driver import OpenAIDriver

DEFAULT_OLLAMA_ENDPOINT = 'http://localhost:11434/v1/chat/completions'


class OllamaDriver(OpenAIDriver):
    """Ollama local server — thin wrapper over OpenAI-compatible HTTP API.

    Ollama runs locally and exposes the standard OpenAI API on port 11434.
    This driver only sets two defaults:

    - Endpoint: ``http://localhost:11434/v1/chat/completions``
    - API key: ``'ollama'`` (Ollama ignores the key but the HTTP header
      is still required by the driver's request builder).

    Everything else (chat_completion, error handling, tool calling) is
    inherited from ``OpenAIDriver`` unchanged.
    """

    @property
    def driver_name(self) -> str:
        return 'OllamaDriver'

    def initialize(self, config):
        cfg = dict(config or {})
        cfg.setdefault('protocol', 'ollama')
        endpoint = (cfg.get('endpoint') or '').strip()
        if not endpoint:
            cfg['endpoint'] = DEFAULT_OLLAMA_ENDPOINT
        if not cfg.get('api_key'):
            cfg['api_key'] = 'ollama'
        super().initialize(cfg)
