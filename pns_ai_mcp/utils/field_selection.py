# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""Resolver estructural de etiquetas Selection (cualquier modelo/campo/serie).

``field.selection`` puede ser lista, callable o nombre de método en Odoo 14–19.
Iterarlo a ciegas (``list(field.selection)``) levanta TypeError. Este helper
usa el resolver oficial; no conoce modelos ni campos de negocio.
"""
from __future__ import annotations

import re

_FUNCTION_NOT_ITERABLE_RE = re.compile(
    r"'(function|method|builtin_function_or_method)' object is not iterable",
    re.IGNORECASE,
)


def _model_key(model):
    """Nombre técnico desde string o recordset (``_name``)."""
    if isinstance(model, str):
        key = model.strip()
        if key:
            return key, None
        raise ValueError('field_selection(model, name) needs a model name')
    key = getattr(model, '_name', None)
    if isinstance(key, str) and key.strip():
        return key.strip(), model
    raise ValueError(
        'field_selection(model, name) needs a model name or recordset'
    )


def _model_in_env(env, model_name):
    try:
        return model_name in env
    except Exception:
        return False


def resolve_field_selection(env, model, name):
    """Lista ``[(value, label), …]`` de un campo Selection.

    *model* es el nombre técnico o un recordset; *name* el campo. Sin literales
    de dominio: el registry y ``_description_selection`` / ``fields_get``
    resuelven lista vs callable.
    """
    if not isinstance(name, str) or not name.strip():
        raise ValueError('field_selection(model, name) needs a field name')
    name = name.strip()
    model_name, given = _model_key(model)
    if given is not None and getattr(given, '_fields', None) is not None:
        Model = given
    elif env is None or not _model_in_env(env, model_name):
        raise KeyError(model_name)
    else:
        Model = env[model_name]

    fields_map = getattr(Model, '_fields', None) or {}
    field = fields_map.get(name)
    if field is None:
        raise ValueError('Unknown field %r on %s' % (name, model_name))

    desc = getattr(field, '_description_selection', None)
    if callable(desc) and env is not None:
        sel = desc(env)
        if sel is not None:
            return list(sel)

    getter = getattr(Model, 'fields_get', None)
    if callable(getter):
        info = getter([name], attributes=['selection']) or {}
        meta = info.get(name) or {}
        sel = meta.get('selection')
        if sel is not None:
            return list(sel)

    raw = getattr(field, 'selection', None)
    if callable(raw):
        raise TypeError(
            'Field %s.%s.selection is a callable; use field_selection(%r, %r)'
            % (model_name, name, model_name, name)
        )
    if raw is None:
        raise TypeError('Field %s.%s has no selection' % (model_name, name))
    return list(raw)


def format_selection_iterable_hint(error_msg):
    """Hint retryable si el LLM iteró un ``selection`` callable."""
    text = (error_msg or '').strip()
    if not text or not _FUNCTION_NOT_ITERABLE_RE.search(text):
        return None
    return (
        'Error executing code: %s\n'
        '[HINT] field.selection may be a list or a callable in any Odoo series. '
        'Do not list(field.selection) or dict(field.selection). '
        'Use the PRELOADED helper: field_selection(model, name).'
    ) % text
