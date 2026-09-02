# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""Sugerencias estructurales de modelo ante KeyError en RelaxAICode.

Invariante: el registry de Odoo ya conoce los modelos instalados; no hace falta
un contexto de dominio para que el motor se “conozca a sí mismo”. Ante
``env['mcp.log']`` fallido, proponer vecinos del registry (difflib + mismo
sufijo técnico), sin listas de sinónimos de negocio.
"""
from __future__ import annotations

import difflib


def suggest_model_names(wanted, available, *, limit=5, cutoff=0.45):
    """Devuelve nombres de modelo instalados parecidos a ``wanted``.

    Criterios (sin hardcode de dominio):
    1. ``difflib.get_close_matches`` sobre el registry.
    2. Mismo segmento final tras el último punto (``mcp.log`` → ``*.log``).
    """
    wanted = (wanted or '').strip()
    if not wanted or limit <= 0:
        return []
    names = []
    seen = set()
    for raw in available or ():
        if not isinstance(raw, str):
            continue
        name = raw.strip()
        if not name or name == wanted or name in seen:
            continue
        seen.add(name)
        names.append(name)
    if not names:
        return []

    out = []
    for match in difflib.get_close_matches(
        wanted, names, n=limit, cutoff=float(cutoff),
    ):
        if match not in out:
            out.append(match)

    if '.' in wanted:
        suffix = wanted.rsplit('.', 1)[-1]
        if suffix:
            same_suffix = sorted(
                n for n in names
                if n.rsplit('.', 1)[-1] == suffix and n not in out
            )
            for match in same_suffix:
                out.append(match)
                if len(out) >= limit:
                    break

    return out[:limit]


def format_missing_model_hint(wanted, suggestions, *, locale='en_US'):
    """Texto de hint para el error KeyError de modelo ausente."""
    wanted = (wanted or '').strip() or '?'
    lines = [
        f"Error executing code: '{wanted}'",
        f"[HINT] Model '{wanted}' not found in this database registry.",
    ]
    if suggestions:
        listed = ', '.join(suggestions)
        lines.append(
            f"[SUGGESTED MODELS] Closest installed model name(s): {listed}. "
            f"Retry with env['{suggestions[0]}'] if that is the intended model."
        )
    else:
        lines.append(
            "[HINT] No close match among installed models. Verify with "
            "env['ir.model'].search([]).mapped('model')."
        )
    lines.append(
        f"[OPTIONAL] For business-term → model mappings (invoice, employee…), "
        f"consult corporative_terms_{locale} / contexts_index_core."
    )
    return '\n'.join(lines)
