# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 Patanegra Soft <https://patanegra.com>
"""Citation strip: one document card, never a mural of related rows.

Nameless. Table cell links stay on the rows; this list is only the footer card.
A ``*.line`` write cites the parent header. A catalog row is not a document.
"""
from __future__ import annotations

_LINE_SUFFIX = '.line'


def parent_model_of_line(model):
    """If ``model`` is ``X.line``, return ``X``. Else None."""
    if not isinstance(model, str) or not model.endswith(_LINE_SUFFIX):
        return None
    parent = model[:-len(_LINE_SUFFIX)]
    return parent or None


def is_document_header_model(model, env=None):
    """True when ``{model}.line`` exists (header with line children)."""
    if not model or not isinstance(model, str) or model.endswith(_LINE_SUFFIX):
        return False
    child = model + _LINE_SUFFIX
    if env is None or child not in env:
        return False
    try:
        fields = getattr(env[model], '_fields', None)
    except Exception:
        fields = None
    if not fields:
        return True
    for field in fields.values():
        if getattr(field, 'type', None) not in ('one2many', 'many2many'):
            continue
        if getattr(field, 'comodel_name', None) == child:
            return True
    return False


def _as_int(rid):
    try:
        return int(rid)
    except (TypeError, ValueError):
        return None


def _browse_line_parent(env, line_model, parent_model, rid):
    try:
        rec = env[line_model].browse(rid)
        if not rec.exists():
            return None
        fields = getattr(rec, '_fields', None) or {}
        for fname, field in fields.items():
            if getattr(field, 'type', None) != 'many2one':
                continue
            if getattr(field, 'comodel_name', None) != parent_model:
                continue
            parent = rec[fname]
            if parent:
                return (parent_model, int(parent.id))
    except Exception:
        return None
    return None


def resolve_document_target(model, rid, env=None, parent_of=None):
    """Return ``(header_model, header_id)`` or None.

    Shape only: a ``*.line`` row lifts to its parent; a model is a document
    header only when ``{model}.line`` is in ``env``.
    """
    rid = _as_int(rid)
    if not model or not isinstance(model, str) or rid is None:
        return None
    parent_model = parent_model_of_line(model)
    if parent_model:
        if parent_of:
            got = parent_of(model, rid)
            if got:
                pid = _as_int(got[1])
                if got[0] and pid is not None:
                    return (got[0], pid)
        if env is not None and model in env:
            return _browse_line_parent(env, model, parent_model, rid)
        return None
    if is_document_header_model(model, env):
        return (model, rid)
    return None


def _header_ref(raw, target):
    out = {'model': target[0], 'id': target[1], 'role': 'document'}
    if raw.get('model') == target[0]:
        name = raw.get('name')
        if name and isinstance(name, str):
            out['name'] = name
    return out


def _unique_headers(refs, env=None, parent_of=None):
    out = []
    seen = set()
    for raw in refs:
        target = resolve_document_target(
            raw.get('model'), raw.get('id'), env=env, parent_of=parent_of,
        )
        if not target:
            continue
        key = (target[0], target[1])
        if key in seen:
            continue
        seen.add(key)
        out.append(_header_ref(raw, target))
    return out


def document_cite_refs(refs, env=None, parent_of=None):
    """Keep ``role=document`` headers, or stamp a single unlabeled header.

    Several unlabeled refs (lines, partner, products) → empty (no mural).
    A lone catalog row or line without a resolvable parent → empty.
    """
    if not isinstance(refs, list):
        return []
    valid = []
    for raw in refs:
        if not isinstance(raw, dict):
            continue
        model = raw.get('model')
        rid = raw.get('id')
        if not model or not isinstance(model, str) or rid in (None, False, ''):
            continue
        valid.append(raw)
    docs = [r for r in valid if r.get('role') == 'document']
    if docs:
        return _unique_headers(docs, env=env, parent_of=parent_of)
    if len(valid) == 1:
        return _unique_headers(valid, env=env, parent_of=parent_of)
    return []
