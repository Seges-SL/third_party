# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""Context for transparent LLM usage logging (tokens + USD) into ``ai.log``.

Headless shots (wizards, server detection, skill author) open this context
once; ``llm_json_completion_result`` records usage and flush writes one row.

Satellite calls *inside* a Chatboo turn do **not** use this for a child row:
they fold into the parent via ``AgentEngine._accumulate_side_usage`` — see
``docs/llm_usage_metering.md``.
"""
from __future__ import annotations

import logging
from contextlib import contextmanager
from contextvars import ContextVar

from .llm_usage import add_usage, extract_cost, usage_has_tokens

_logger = logging.getLogger(__name__)

_audit_ctx = ContextVar('pns_inference_audit', default=None)


class InferenceAudit:
    """Accumulates usage for one headless operation; flushed on context exit.

    ``log_mode='accumulate'`` skips flush (caller owns the parent total).
    """

    __slots__ = (
        'env', 'endpoint', 'source_channel', 'user_id', 'agent_code',
        'log_mode', 'user_prompt', 'additional_info', 'status', 'turn',
        'provider', 'usage_acc', 'content_preview', '_flushed',
        'require_usage', '_recorded', 'remote_ip',
    )

    def __init__(
        self,
        env,
        endpoint,
        source_channel='internal',
        user_id=None,
        agent_code=None,
        log_mode='single',
        user_prompt=None,
        additional_info=None,
        status='ok',
        turn=None,
        require_usage=True,
        remote_ip=None,
    ):
        self.env = env
        self.endpoint = endpoint
        self.source_channel = source_channel or 'internal'
        self.user_id = user_id
        self.agent_code = agent_code
        self.log_mode = log_mode or 'single'
        self.user_prompt = user_prompt
        self.additional_info = dict(additional_info or {})
        self.status = (status or 'ok').strip() or 'ok'
        self.turn = (turn or '').strip() or None
        self.provider = None
        self.usage_acc = {}
        self.content_preview = ''
        self._flushed = False
        self.require_usage = bool(require_usage)
        self._recorded = False
        self.remote_ip = remote_ip or None

    def record(self, provider, usage, content_preview=''):
        """Merge one LLM round into the accumulator."""
        self._recorded = True
        if provider is not None:
            self.provider = provider
        if usage:
            self.usage_acc = add_usage(self.usage_acc, usage)
        if content_preview:
            self.content_preview = (content_preview or '')[:5000]

    def flush(self):
        """Write one ``ai.log`` row when ``log_mode=single`` and there is usage."""
        if self._flushed or self.log_mode == 'accumulate':
            return
        metered = usage_has_tokens(self.usage_acc) or extract_cost(
            self.usage_acc,
        ) is not None
        if not metered and (self.require_usage or not self._recorded):
            return
        if 'ai.execution.engine' not in self.env:
            return
        self._flushed = True
        uid = self.user_id
        if uid is None and self.env.user:
            uid = self.env.user.id
        from .mcp_correlation import new_turn_id
        turn = self.turn or new_turn_id()
        try:
            self.env['ai.execution.engine'].log_llm_inference(
                self.provider,
                self.usage_acc,
                endpoint=self.endpoint,
                source_channel=self.source_channel,
                user_id=uid,
                agent_code=self.agent_code,
                log_mode=self.log_mode,
                turn=turn,
                turn_step=1,
                user_prompt=self.user_prompt,
                additional_info=self.additional_info,
                content_preview=self.content_preview,
                status=self.status,
                remote_ip=self.remote_ip,
            )
        except Exception:
            _logger.warning(
                'inference_audit: flush failed for %s',
                self.endpoint,
                exc_info=True,
            )


def get_inference_audit():
    """Active audit context, or ``None``."""
    return _audit_ctx.get()


@contextmanager
def inference_audit(
    env,
    endpoint,
    source_channel='internal',
    user_id=None,
    agent_code=None,
    log_mode='single',
    user_prompt=None,
    additional_info=None,
    status='ok',
    turn=None,
    require_usage=True,
    remote_ip=None,
):
    """Declare metadata once; nested LLM calls accumulate usage and flush on exit."""
    ctx = InferenceAudit(
        env,
        endpoint,
        source_channel=source_channel,
        user_id=user_id,
        agent_code=agent_code,
        log_mode=log_mode,
        user_prompt=user_prompt,
        additional_info=additional_info,
        status=status,
        turn=turn,
        require_usage=require_usage,
        remote_ip=remote_ip,
    )
    token = _audit_ctx.set(ctx)
    try:
        yield ctx
    finally:
        try:
            ctx.flush()
        finally:
            _audit_ctx.reset(token)


def record_inference_usage(provider, usage, content_preview=''):
    """Hook from ``llm_json_completion_result`` when audit context is active."""
    ctx = get_inference_audit()
    if not ctx:
        return
    ctx.record(provider, usage, content_preview=content_preview)
