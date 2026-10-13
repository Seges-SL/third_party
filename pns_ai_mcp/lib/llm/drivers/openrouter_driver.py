# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""OpenRouter driver.

Chat and voice use this provider's own address and model. Failover is the
next audio provider, not another URL on this one.
"""

from .openai_driver import OpenAIDriver


class OpenRouterDriver(OpenAIDriver):
    """Same chat and transcribe body as the OpenAI driver."""

    @property
    def driver_name(self) -> str:
        return 'OpenRouterDriver'
