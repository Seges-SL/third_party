# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 Patanegra Soft <https://patanegra.com>
"""On-disk skill file pairing (shape only — no domain literals)."""
from __future__ import annotations

import os


def snake_catalog_id(token):
    """Fold kebab leftovers into a snake_case catalog id."""
    return (token or '').replace('-', '_')


def split_skill_identity(md_filename, meta=None):
    """Return ``(code, command)`` from filename + front-matter.

    * ``code`` — snake_case catalog id (stem or ``artifact:``; hyphens folded).
    * ``command`` — kebab slash from ``skill:``, or the legacy hyphenated
      stem; empty string when it equals ``code`` (single-token skills).
    """
    meta = meta or {}
    stem = os.path.splitext(md_filename or '')[0]
    artifact = (meta.get('artifact') or '').strip() or stem
    code = snake_catalog_id(artifact)
    invoke = (meta.get('skill') or '').strip()
    if not invoke:
        invoke = stem if '-' in stem else code
    command = invoke if invoke != code else ''
    return code, command


def skill_code_body_path(scope_dir, md_filename, code, command=None):
    """Path of the ``.py`` sibling for a skill markdown file.

    Prefer the same stem as the ``.md`` so a tenant artefact and its
    ``.py`` stay paired even when front-matter ``skill:`` is the slash
    command. Fall back to ``{code}.py`` then ``{command}.py`` (legacy).
    """
    stem = os.path.splitext(md_filename or '')[0]
    seen = set()
    for name in (stem, code, command):
        if not name or name in seen:
            continue
        seen.add(name)
        path = os.path.join(scope_dir, '%s.py' % name)
        if os.path.isfile(path):
            return path
    if stem:
        return os.path.join(scope_dir, '%s.py' % stem)
    if code:
        return os.path.join(scope_dir, '%s.py' % code)
    if command:
        return os.path.join(scope_dir, '%s.py' % command)
    return ''


def factory_row_on_disk(rel_path, code, command, disk_rels, disk_codes, disk_commands):
    """True if a factory row still matches a file this addon ships.

    ``rel_path`` is the usual key. Capture leftovers often have an empty
    or stale path after claim; code/command still name the disk skill.
    """
    rel = (rel_path or '').replace('\\', '/')
    if rel and rel in (disk_rels or ()):
        return True
    if code and code in (disk_codes or ()):
        return True
    if command and command in (disk_commands or ()):
        return True
    return False
