# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 Patanegra Soft <https://patanegra.com>
"""Columns for one catalogue item. Missing keys stay empty.

The gateway decides the shape. This module does not name a model or a maker.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse


def listing_url(url: str) -> str:
    """OpenRouter listing must ask for every output shape, in large pages.

    Their GET without this keeps a slice (text, or transcription). Other
    hosts are left as the driver built them.
    """
    parsed = urlparse(url or '')
    if 'openrouter.ai' not in (parsed.netloc or '').lower():
        return url or ''
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    query['output_modalities'] = 'all'
    query['limit'] = '1000'
    return urlunparse(parsed._replace(query=urlencode(query)))


def _as_list(value: Any) -> List[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def _modalities(item: Dict[str, Any]):
    arch = item.get('architecture') if isinstance(item.get('architecture'), dict) else {}
    ins = [part.lower() for part in (
        _as_list(arch.get('input_modalities'))
        or _as_list(arch.get('inputModalities'))
    )]
    outs = [part.lower() for part in (
        _as_list(arch.get('output_modalities'))
        or _as_list(arch.get('outputModalities'))
    )]
    if ins or outs:
        return ins, outs
    modality = str(arch.get('modality') or '')
    if '->' not in modality:
        return [], []
    left, right = modality.split('->', 1)
    ins = [part.strip().lower() for part in left.split('+') if part.strip()]
    outs = [part.strip().lower() for part in right.split('+') if part.strip()]
    return ins, outs


def _slug_tail(slug: str) -> str:
    tail = (slug or '').split('/')[-1]
    if ':' in tail:
        tail = tail.split(':', 1)[0]
    return tail


def _per_million(pricing: Any, key: str) -> Optional[float]:
    if not isinstance(pricing, dict) or key not in pricing:
        return None
    raw = pricing.get(key)
    if raw in (None, ''):
        return None
    try:
        return float(raw) * 1000000.0
    except (TypeError, ValueError):
        return None


def _price_label(value: Optional[float]) -> str:
    if value is None:
        return ''
    return ('%.6f' % value).rstrip('0').rstrip('.')


def _int_or_none(value: Any) -> Optional[int]:
    if value in (None, ''):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def catalogue_fields(item: Dict[str, Any], chooses: bool = False) -> Dict[str, Any]:
    """Stored columns for one ``/models`` object.

    ``chooses`` is the gateway's driver: its models answer a closed Choice.
    """
    slug = str(item.get('id') or '').strip()
    title = str(item.get('name') or '').strip()
    if title == slug:
        title = ''
    maker = slug.split('/')[0].strip() if '/' in slug else ''
    ins, outs = _modalities(item)
    tail = _slug_tail(slug)
    batch = slug.endswith(':batch')
    reasoning = tail.endswith('-pro')
    params = item.get('supported_parameters')
    if isinstance(params, list) and 'reasoning' in [str(p) for p in params]:
        reasoning = True
    pricing = item.get('pricing') if isinstance(item.get('pricing'), dict) else {}
    top = item.get('top_provider') if isinstance(item.get('top_provider'), dict) else {}
    context = _int_or_none(item.get('context_length'))
    if context is None:
        context = _int_or_none(top.get('context_length'))
    max_out = _int_or_none(top.get('max_completion_tokens'))
    if max_out is None:
        max_out = _int_or_none(item.get('max_completion_tokens'))
    price_in = _per_million(pricing, 'prompt')
    price_out = _per_million(pricing, 'completion')
    price_cache = _per_million(pricing, 'input_cache_read')
    modality = ''
    if ins or outs:
        modality = '%s → %s' % (', '.join(ins), ', '.join(outs))
    return {
        'title': title,
        'maker': maker,
        'context_length': context or 0,
        'context_label': '' if context is None else str(context),
        'max_output_label': '' if max_out is None else str(max_out),
        'price_in_label': _price_label(price_in),
        'price_out_label': _price_label(price_out),
        'price_cache_label': _price_label(price_cache),
        'modality_label': modality,
        'apt_conversation': bool(ins and outs and 'text' in ins and 'text' in outs and not batch),
        'apt_reasoning': bool(reasoning),
        'apt_batch': bool(batch),
        'apt_vision': 'image' in ins,
        'apt_audio': 'audio' in ins or 'speech' in ins,
        'apt_transcriptions': (
            ('audio' in ins or 'speech' in ins)
            and ('text' in outs or 'transcription' in outs)
            and 'text' not in ins
        ) or ('transcription' in outs and 'text' not in ins),
        'apt_file': 'file' in ins,
        'apt_decision': bool(chooses),
    }
