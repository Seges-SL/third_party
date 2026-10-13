# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""Validate api_call arguments against a tool ``inputSchema`` (JSON Schema subset).

No Odoo, no vendor names: only nested ``required`` / object-array types.
Empty or shapeless schemas are a no-op (do not invent constraints).
"""
from __future__ import annotations

# English msgid shape for propose/execute (wrapped with ``_()`` at the call site).
UNKNOWN_SERVER_MSG = (
    "Unknown or inactive server code '%s'. "
    "Use an exact code from the catalogue: %s"
)


def check_tool_arguments(schema, arguments):
    """Return ``{'kind', 'path', ...}`` or None. Pure; used for i18n at the hook."""
    if not isinstance(schema, dict):
        return None
    props = schema.get('properties')
    required = schema.get('required')
    stype = schema.get('type')
    if not props and not required and stype not in ('object', 'array'):
        return None
    if arguments is None:
        arguments = {}
    if not isinstance(arguments, dict):
        arguments = {}
    return _walk(schema, arguments, [])


def _pointer(path):
    if not path:
        return 'arguments'
    return 'arguments.' + '.'.join(path)


def _is_object_schema(schema):
    if not isinstance(schema, dict):
        return False
    if schema.get('type') == 'object':
        return True
    if schema.get('properties') or schema.get('required'):
        return True
    return False


def _walk(schema, value, path):
    if not isinstance(schema, dict):
        return None
    if _is_object_schema(schema):
        return _walk_object(schema, value, path)
    stype = schema.get('type')
    if stype == 'array':
        return _walk_array(schema, value, path)
    if stype:
        return _walk_scalar(stype, value, path)
    return None


def _walk_object(schema, value, path):
    required = schema.get('required') or []
    properties = schema.get('properties') or {}
    if required or properties:
        if not isinstance(value, dict):
            return {
                'kind': 'type',
                'path': _pointer(path),
                'expected': 'object',
            }
        for key in required:
            if key not in value:
                return {
                    'kind': 'missing',
                    'name': key,
                    'path': _pointer(path),
                }
        for key, subschema in properties.items():
            if key in value:
                err = _walk(subschema, value[key], path + [key])
                if err:
                    return err
    return None


def _walk_array(schema, value, path):
    if not isinstance(value, list):
        return {
            'kind': 'type',
            'path': _pointer(path),
            'expected': 'array',
        }
    items = schema.get('items')
    if isinstance(items, dict):
        for idx, item in enumerate(value):
            err = _walk(items, item, path + [str(idx)])
            if err:
                return err
    return None


def _walk_scalar(stype, value, path):
    checkers = {
        'string': lambda v: isinstance(v, str),
        'integer': lambda v: isinstance(v, int) and not isinstance(v, bool),
        'number': lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
        'boolean': lambda v: isinstance(v, bool),
        'null': lambda v: v is None,
    }
    check = checkers.get(stype)
    if check and not check(value):
        return {
            'kind': 'type',
            'path': _pointer(path),
            'expected': stype,
        }
    return None
