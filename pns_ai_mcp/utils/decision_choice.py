# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 Patanegra Soft <https://patanegra.com>
"""Choice answer parsing. The provider's driver does the call."""
from __future__ import annotations

from typing import Any, Dict


class DecisionCallError(Exception):
    """The decision endpoint did not return a Choice answer."""


def parse_choice_response(body: Any) -> Dict[str, Any]:
    """Pull the ``pack`` Choice out of a system-one response body."""
    if not isinstance(body, dict):
        raise DecisionCallError('response is not a JSON object')
    answers = body.get('answers') or {}
    pack = answers.get('pack') if isinstance(answers, dict) else None
    if not isinstance(pack, dict) or 'choice' not in pack:
        raise DecisionCallError('response has no choice')
    return {
        'choice': pack.get('choice'),
        'confidence': pack.get('confidence'),
        'probabilities': pack.get('probabilities') or {},
        'model': body.get('model'),
        'usage': body.get('usage') or {},
    }
