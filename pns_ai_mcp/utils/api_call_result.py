# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""Format and paginate external api_call responses for the LLM channel."""

import hashlib
import json

API_CALL_LLM_MAX_CHARS = 10240
API_CALL_DEFAULT_PAGE_SIZE = 50
API_CALL_CACHE_TTL_SECONDS = 600


def cache_key_for_api_call(server, tool, arguments):
    """Stable cache key: server + tool + canonical JSON arguments."""
    canonical = json.dumps(arguments or {}, sort_keys=True, ensure_ascii=False, default=str)
    raw = '%s\0%s\0%s' % (server or '', tool or '', canonical)
    return hashlib.sha256(raw.encode('utf-8')).hexdigest()


def _next_page_arguments(arguments, returned_count, total_count):
    """Suggest the next api_call arguments for pagination (generic)."""
    args = dict(arguments or {})
    hint = {
        'returned_count': returned_count,
        'total_items': total_count,
        'has_more': total_count is None or returned_count < total_count,
    }
    suggested = dict(args)
    if 'page' in args:
        try:
            suggested['page'] = int(args['page']) + 1
        except (TypeError, ValueError):
            pass
    elif 'offset' in args:
        try:
            offset = int(args['offset'])
            limit = int(args.get('limit', returned_count or API_CALL_DEFAULT_PAGE_SIZE))
            suggested['offset'] = offset + limit
        except (TypeError, ValueError):
            pass
    elif 'limit' in args:
        try:
            limit = int(args['limit'])
            suggested['offset'] = limit
        except (TypeError, ValueError):
            suggested['limit'] = min(returned_count or API_CALL_DEFAULT_PAGE_SIZE, API_CALL_DEFAULT_PAGE_SIZE)
            suggested['offset'] = returned_count or API_CALL_DEFAULT_PAGE_SIZE
    else:
        page_size = min(returned_count or API_CALL_DEFAULT_PAGE_SIZE, API_CALL_DEFAULT_PAGE_SIZE)
        suggested['limit'] = page_size
        suggested['offset'] = returned_count or page_size
    hint['suggested_arguments'] = suggested
    return hint


def _shrink_list_to_budget(items, max_chars, wrapper_fn):
    """Pick the largest prefix of *items* whose JSON wrapper fits *max_chars*."""
    if not items:
        return [], 0
    lo, hi = 1, len(items)
    best_n = 1
    while lo <= hi:
        mid = (lo + hi) // 2
        if len(wrapper_fn(items[:mid])) <= max_chars:
            best_n = mid
            lo = mid + 1
        else:
            hi = mid - 1
    return items[:best_n], best_n


def format_api_call_body_for_llm(body, arguments=None, max_chars=API_CALL_LLM_MAX_CHARS):
    """Return ``(llm_body, truncated, pagination_hint)`` for Safe Plan results.

    Full responses are stored separately (``ai.api.result.cache``); this shapes
    what reaches the LLM: JSON-aware first page instead of a blind byte cut.
    """
    body = body or ''
    if len(body) <= max_chars:
        return body, False, None

    arguments = arguments or {}
    try:
        data = json.loads(body)
    except (ValueError, TypeError):
        return body[:max_chars], True, {
            'hint': (
                'Response is not JSON. Request smaller pages via tool arguments '
                '(limit/page/offset) in propose_safe_operations api_call.'
            ),
            'original_size': len(body),
        }

    if isinstance(data, list):
        def _wrap(chunk):
            return json.dumps(chunk, ensure_ascii=False, default=str)

        slice_items, n = _shrink_list_to_budget(data, max_chars, _wrap)
        preview = json.dumps(slice_items, ensure_ascii=False, default=str)
        pagination = _next_page_arguments(arguments, n, len(data))
        pagination['original_size'] = len(body)
        pagination['preview_items'] = n
        return preview, True, pagination

    if isinstance(data, dict):
        list_keys = [k for k, v in data.items() if isinstance(v, list) and v]
        if list_keys:
            key = max(list_keys, key=lambda k: len(data[k]))
            arr = data[key]

            def _wrap(chunk):
                preview_obj = dict(data)
                preview_obj[key] = chunk
                return json.dumps(preview_obj, ensure_ascii=False, default=str)

            slice_items, n = _shrink_list_to_budget(arr, max_chars, _wrap)
            preview_obj = dict(data)
            preview_obj[key] = slice_items
            preview = json.dumps(preview_obj, ensure_ascii=False, default=str)
            pagination = _next_page_arguments(arguments, n, len(arr))
            pagination['original_size'] = len(body)
            pagination['list_field'] = key
            pagination['preview_items'] = n
            return preview, True, pagination

    return body[:max_chars], True, {
        'hint': 'JSON object without a list field; response truncated.',
        'original_size': len(body),
    }
