# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 Patanegra Soft <https://patanegra.com>
"""Document card for the local Safe Plan ack (no LLM turn after Confirm).

Nameless: only CRUD header ids from execute results. Related vals
(partner, products, lines) stay out of the citation strip. A ``*.line``
write cites the parent header.
"""
from __future__ import annotations


def _resolve_document_target(model, rid, env=None, parent_of=None):
    try:
        from .record_cite import resolve_document_target
    except ImportError:
        import importlib.util
        from pathlib import Path
        path = Path(__file__).resolve().parent / 'record_cite.py'
        spec = importlib.util.spec_from_file_location(
            'pns_ai_mcp_record_cite_ack', path,
        )
        if spec is None or spec.loader is None:
            return None
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        resolve_document_target = mod.resolve_document_target
    return resolve_document_target(model, rid, env=env, parent_of=parent_of)


def _push(out, seen, model, rid, name=None):
    if not model or not isinstance(model, str) or not rid:
        return
    key = (model, int(rid))
    if key in seen:
        return
    seen.add(key)
    label = name if (name and isinstance(name, str)) else ('%s #%s' % (model, rid))
    out.append({
        'model': model,
        'id': int(rid),
        'name': label[:120],
        'role': 'document',
    })


def collect_ack_records(results, steps=None, lookup=None, env=None, parent_of=None):
    """Build document-card dicts from execute CRUD ids.

    ``lookup`` is ignored (kept so call sites stay stable).
    """
    out = []
    seen = set()
    for item in results or []:
        if not isinstance(item, dict):
            continue
        op = item.get('op')
        model = item.get('model')
        name = item.get('name')
        rids = []
        if op == 'create' and isinstance(item.get('id'), int):
            rids = [item['id']]
        elif op == 'copy' and isinstance(item.get('new_id'), int):
            rids = [item['new_id']]
        elif op == 'write' and isinstance(item.get('ids'), list):
            rids = [rid for rid in item['ids'] if isinstance(rid, int)]
        for rid in rids:
            target = _resolve_document_target(
                model, rid, env=env, parent_of=parent_of,
            )
            if not target:
                continue
            label = name if model == target[0] else None
            _push(out, seen, target[0], target[1], label)
    return out


def attach_ack_records(payload, results, steps=None, lookup=None, name_of=None,
                       env=None, parent_of=None):
    """Copy of payload plus ``records`` when the execute produced a document."""
    out = dict(payload or {})
    records = collect_ack_records(
        results, steps=steps, lookup=lookup, env=env, parent_of=parent_of,
    )
    if name_of:
        for rec in records:
            named = name_of(rec.get('model'), rec.get('id'))
            if named:
                rec['name'] = str(named)[:120]
    if records:
        out['records'] = records
    return out
