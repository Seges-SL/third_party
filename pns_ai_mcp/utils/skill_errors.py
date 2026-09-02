# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 Patanegra Soft <https://patanegra.com>
"""Map ORM / ACL exceptions to short, translatable skill error messages.

Skills run with the chat user's privileges. When they hit AccessError or the
classic ``Invalid field '…' on model '….public'`` (private fields on the
public HR proxy), dumping the raw traceback into Chatboo is cryptic. This
helper turns those into user-facing English msgids for ``_()``.
"""
from __future__ import annotations

import re

from odoo.exceptions import AccessError, MissingError, UserError, ValidationError
from odoo.tools.translate import _

from .error_ux import (  # noqa: F401 — re-export for callers
    humanize_exhausted_tool_error,
    is_permission_denied_message,
    strip_tool_error_wrappers,
)

_INVALID_FIELD_RE = re.compile(
    r"Invalid field '([^']+)' on model '([^']+)'",
    re.IGNORECASE,
)


def _model_label(env, technical_name):
    """Human label for a model technical name; strip trailing ``.public``."""
    name = (technical_name or '').strip()
    if name.endswith('.public'):
        name = name[: -len('.public')]
    if not name:
        return _('that data')
    if env is None:
        return name
    try:
        Model = env['ir.model'].sudo()
        rec = Model.search([('model', '=', name)], limit=1)
        if rec and rec.name:
            return rec.name
    except Exception:
        pass
    return name


def _prefer_exception_text(exc, fallback):
    """Use Odoo's already-translated body when it is usable for humans."""
    text = str(exc).strip() if exc is not None else ''
    if text and 'Traceback' not in text:
        return text
    return fallback


def friendly_skill_error(exc, env=None):
    """Return a short, translated reason string for skill bootstrap / fast-path.

    Technical detail stays in the logger; the chat only sees this string.
    """
    if isinstance(exc, AccessError):
        return _prefer_exception_text(
            exc,
            _('You do not have permission to access that data.'),
        )

    if isinstance(exc, MissingError):
        return _prefer_exception_text(
            exc,
            _('The requested record was not found or you cannot access it.'),
        )

    if isinstance(exc, (UserError, ValidationError)):
        # Already written for humans (often already translated by Odoo).
        text = str(exc).strip()
        return text or _('The skill could not run (%(exc_type)s). '
                         'Ask an administrator if this keeps happening.') % {
            'exc_type': type(exc).__name__,
        }

    if isinstance(exc, ValueError):
        raw = str(exc)
        match = _INVALID_FIELD_RE.search(raw)
        if match:
            model_tech = match.group(2)
            # Public proxy / private-field prefetch ≈ missing master ACL.
            if model_tech.endswith('.public') or '.public' in model_tech:
                label = _model_label(env, model_tech)
                return _('You do not have permission to view %(model)s.') % {
                    'model': label,
                }

    return _(
        'The skill could not run (%(exc_type)s). '
        'Ask an administrator if this keeps happening.'
    ) % {'exc_type': type(exc).__name__}
