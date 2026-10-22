# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""Register LLM drivers that the provider form can select."""

from .base import LLMDriver
from .openai_driver import OpenAIDriver
from .openrouter_driver import OpenRouterDriver
from .anthropic_driver import AnthropicDriver
from .systemone_driver import SystemOneDriver
from .registry import get_llm_driver, list_llm_driver_types, register_llm_driver

register_llm_driver('openai', OpenAIDriver)
register_llm_driver('openrouter', OpenRouterDriver)
register_llm_driver('anthropic', AnthropicDriver)
register_llm_driver('systemone', SystemOneDriver)

__all__ = [
    'LLMDriver',
    'OpenAIDriver',
    'OpenRouterDriver',
    'AnthropicDriver',
    'SystemOneDriver',
    'get_llm_driver',
    'register_llm_driver',
    'list_llm_driver_types',
]
