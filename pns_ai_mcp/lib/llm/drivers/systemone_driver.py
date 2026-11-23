# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""SystemOne protocol: a closed choice. It does not chat."""

import json
import urllib.error
import urllib.request

from .base import LLMDriver


class SystemOneDriver(LLMDriver):
    """POST a Choice question. Chat completion is refused."""

    chats = False
    chooses = True

    def __init__(self):
        self.endpoint = ''
        self.api_key = ''
        self._model_name_internal = ''

    @property
    def driver_name(self) -> str:
        return 'SystemOneDriver'

    @property
    def model_name(self) -> str:
        return self._model_name_internal or ''

    def initialize(self, config):
        self.endpoint = (config.get('endpoint') or '').strip()
        self.api_key = config.get('api_key') or ''
        self._model_name_internal = (config.get('model_name') or '').strip()

    def format_messages(self, messages, tools=None):
        return ''

    def generate(self, prompt, max_tokens=None, temperature=0.0, stop=None):
        return {}

    def parse_response(self, raw_response):
        return raw_response

    def is_loaded(self) -> bool:
        return True

    def chat_completion(self, messages, tools=None, **kwargs):
        raise RuntimeError(
            'protocol systemone does not complete chat; use the decision call'
        )

    def choose(self, state, criteria, instructions, timeout=3):
        """One Choice named ``pack``. Returns choice, confidence, usage."""
        try:
            from odoo.addons.pns_ai_mcp.utils.decision_choice import (
                DecisionCallError, parse_choice_response,
            )
        except ImportError:
            from utils.decision_choice import (
                DecisionCallError, parse_choice_response,
            )
        url = (self.endpoint or '').strip()
        if url and not url.startswith('http'):
            url = 'https://' + url
        if not url:
            raise DecisionCallError('decision provider has no endpoint')
        model = (self.model_name or '').strip()
        if not model:
            raise DecisionCallError('decision provider has no model')
        if not criteria:
            raise DecisionCallError('decision request has no questions')
        payload = {
            'state': state if state is not None else '',
            'model': model,
            'questions': {
                'pack': {
                    'type': 'choice',
                    'instructions': instructions,
                    'criteria': criteria,
                },
            },
        }
        headers = {'Content-Type': 'application/json'}
        key = (self.api_key or '').strip()
        if key:
            headers['Authorization'] = 'Bearer %s' % key
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode('utf-8'),
            headers=headers,
            method='POST',
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as response:
                raw = response.read().decode('utf-8')
        except urllib.error.HTTPError as exc:
            detail = ''
            try:
                detail = exc.read().decode('utf-8', errors='replace')[:400]
            except Exception:
                detail = ''
            raise DecisionCallError(
                'HTTP %s %s' % (exc.code, detail or exc.reason)
            ) from exc
        except urllib.error.URLError as exc:
            raise DecisionCallError(str(exc.reason or exc)) from exc
        try:
            body = json.loads(raw)
        except (TypeError, ValueError) as exc:
            raise DecisionCallError('response is not JSON') from exc
        parsed = parse_choice_response(body)
        parsed['model'] = body.get('model')
        parsed['usage'] = body.get('usage') or {}
        return parsed
