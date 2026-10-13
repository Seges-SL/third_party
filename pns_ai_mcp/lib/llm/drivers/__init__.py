# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""Register LLM drivers (openai, openrouter, anthropic, ollama) on the engine SPI."""

from .base import LLMDriver
from .openai_driver import OpenAIDriver
from .openrouter_driver import OpenRouterDriver
from .anthropic_driver import AnthropicDriver
from .systemone_driver import SystemOneDriver
from .ollama_driver import OllamaDriver
from .registry import get_llm_driver, list_llm_driver_types, register_llm_driver

register_llm_driver('openai', OpenAIDriver)
register_llm_driver('openrouter', OpenRouterDriver)
register_llm_driver('anthropic', AnthropicDriver)
register_llm_driver('systemone', SystemOneDriver)
register_llm_driver('ollama', OllamaDriver)

__all__ = [
    'LLMDriver',
    'OpenAIDriver',
    'OpenRouterDriver',
    'AnthropicDriver',
    'SystemOneDriver',
    'OllamaDriver',
    'get_llm_driver',
    'register_llm_driver',
    'list_llm_driver_types',
]
