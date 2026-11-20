# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""User-facing HTML contract: reject untrusted sandbox formatted_text."""
from __future__ import annotations

import logging

_logger = logging.getLogger(__name__)

# Only these __fmt_type__ values may paint formatted_text in the chat.
_TRUSTED_FMT_TYPES = frozenset({
    'server_side_python',
    'author_html',
    'local_json',
    'local_raw',
})


def reject_untrusted_formatted_text(
    result,
    *,
    after_server_render=False,
):
    """Sandbox may not invent user-facing HTML.

    Trust is only by ``__fmt_type__`` set by the platform:
    - skill runtime → ``author_html``
    - ``maybe_attach_formatted_text`` → ``server_side_python`` (after attach)

    ``after_server_render=True``: second pass after ``maybe_attach``; do not
    drop ``server_side_python`` (the server sets it, not the LLM).
    """
    if not isinstance(result, dict) or not result.get('formatted_text'):
        return False
    # Drop self-attribution from the free sandbox (only before the server render).
    if (
        not after_server_render
        and result.get('__fmt_type__') in _TRUSTED_FMT_TYPES
    ):
        result.pop('__fmt_type__', None)
    if result.get('__fmt_type__') in _TRUSTED_FMT_TYPES:
        return False
    preview = result.pop('formatted_text')
    result.pop('__fmt_type__', None)
    result.pop('__return_direct__', None)
    result.pop('__direct_return__', None)
    result.pop('__return_direct_to_user__', None)
    result['__untrusted_html_preview__'] = (preview or '')[:4000]
    result['__force_continue__'] = True
    result.setdefault('__hint__', (
        'relaxaicode must not invent formatted_text for the user. '
        'Return {\'data\': [row dicts…]} so the SERVER renders the table, or '
        'use safe_plan_request for writes. Answer in prose.'
    ))
    _logger.info(
        '🛡️ [CONTRACT] Rejected untrusted formatted_text (no trusted '
        '__fmt_type__). Forcing LLM turn.',
    )
    return True
