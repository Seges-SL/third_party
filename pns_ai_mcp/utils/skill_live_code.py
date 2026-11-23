# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 Patanegra Soft <https://patanegra.com>
"""AST lock: skill code_body must not embed a frozen result snapshot.

Invariant (no business literals): assigning ``data`` / ``rows`` / ``rows_src``
to a list of three or more dict literals, without building those rows in a
``for`` + ``append``/``extend`` loop, is a pasted capture and must not be saved.

Help-only skills and ``api_call``-only skills are unaffected (they never assign
that shape). Small lookup maps of one or two dicts are allowed.
"""
from __future__ import annotations

import ast

_FROZEN_VARS = frozenset(('data', 'rows', 'rows_src'))
_MIN_LITERAL_DICTS = 3
_ROW_MUTATORS = frozenset(('append', 'extend'))


def code_builds_rows_in_loop(tree):
    """True when a for-loop mutates data/rows/rows_src via append/extend."""
    for node in ast.walk(tree):
        if not isinstance(node, ast.For):
            continue
        for child in ast.walk(node):
            if not isinstance(child, ast.Call):
                continue
            func = child.func
            if not isinstance(func, ast.Attribute):
                continue
            if func.attr not in _ROW_MUTATORS:
                continue
            if isinstance(func.value, ast.Name) and func.value.id in _FROZEN_VARS:
                return True
    return False


def code_has_frozen_result_rows(source):
    """True when ``source`` looks like pasted result rows, not a live fetch."""
    body = (source or '').strip()
    if not body:
        return False
    try:
        tree = ast.parse(body)
    except SyntaxError:
        return False
    if code_builds_rows_in_loop(tree):
        return False
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        names = [
            target.id for target in node.targets
            if isinstance(target, ast.Name)
        ]
        if not any(name in _FROZEN_VARS for name in names):
            continue
        value = node.value
        if not isinstance(value, ast.List):
            continue
        dicts = [elt for elt in value.elts if isinstance(elt, ast.Dict)]
        if len(dicts) >= _MIN_LITERAL_DICTS:
            return True
    return False
