# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 Patanegra Soft <https://patanegra.com>
"""Slashes never drop carried domain-pack codes.

Skill invoke may *add* the skill's domain ``context_ids`` (engine). Menu,
CRUD, mode and unknown tokens leave ``last_domain_codes`` alone. A new
session is what empties the list.
"""
from __future__ import annotations

from typing import Optional, Tuple


def parse_slash_command(message: Optional[str]) -> Optional[Tuple[str, str]]:
    """Return ``(command, args)`` if ``message`` is a slash, else None."""
    if not message:
        return None
    text = message.strip()
    if not text.startswith('/'):
        return None
    body = text[1:].strip()
    if not body:
        return None
    parts = body.split(None, 1)
    command = parts[0].strip()
    args = parts[1].strip() if len(parts) > 1 else ''
    return command, args


def slash_releases_domain_codes(
    command: Optional[str],
    skill_resolved: bool = False,
) -> bool:
    """Slashes never drop conversation packs.

    ``command`` / ``skill_resolved`` stay on the signature for callers.
    Only a new Chatboo session clears ``last_domain_codes``.
    """
    return False
