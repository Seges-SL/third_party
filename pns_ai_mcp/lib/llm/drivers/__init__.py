# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
from .base import LLMDriver
from .openai_driver import OpenAIDriver
from .anthropic_driver import AnthropicDriver
from .ollama_driver import OllamaDriver
from .registry import get_llm_driver, list_llm_driver_types, register_llm_driver

register_llm_driver('openai', OpenAIDriver)
register_llm_driver('anthropic', AnthropicDriver)
register_llm_driver('ollama', OllamaDriver)

__all__ = [
    'LLMDriver',
    'OpenAIDriver',
    'AnthropicDriver',
    'OllamaDriver',
    'get_llm_driver',
    'register_llm_driver',
    'list_llm_driver_types',
]
