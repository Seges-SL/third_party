# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 Patanegra Soft <https://patanegra.com>
"""Scan ``ai/contexts`` trees for ``code`` values. No Odoo import.

Used by factory import (owner still ships this code?) and host tests.
"""
import os
import re

_CODE_TAG_RE = re.compile(r'<code>\s*([^<]+?)\s*</code>', re.I)
_CODE_META_RE = re.compile(
    r'^\s*(?:#\s*)?(?:contexto|code)\s*:\s*(\S+)', re.I | re.M,
)


def normalize_context_code(code_candidate):
    """Lowercase token; keep ``_xx_YY`` locale suffix if present."""
    if not code_candidate:
        return ''
    raw = str(code_candidate).strip()
    locale_pattern = re.compile(
        r'^(?P<prefix>.*)(_(?P<lang>[a-zA-Z]{2})_(?P<country>[a-zA-Z]{2}))$'
    )
    match = locale_pattern.match(raw)
    if match:
        prefix = match.group('prefix').lower().strip()
        prefix = re.sub(r'[^a-z0-9_]', '_', prefix)
        prefix = re.sub(r'_+', '_', prefix)
        suffix = '_%s_%s' % (
            match.group('lang').lower(),
            match.group('country').upper(),
        )
        return prefix + suffix
    code = raw.lower().strip()
    code = re.sub(r'[^a-z0-9_]', '_', code)
    return re.sub(r'_+', '_', code)


def code_from_context_filename(filename_or_path):
    name = os.path.splitext(os.path.basename(filename_or_path or ''))[0]
    return normalize_context_code(name)


def code_from_context_file(path):
    """Prefer ``<code>`` / ``code:`` metadata, else the file stem."""
    stem = code_from_context_filename(path)
    try:
        with open(path, 'r', encoding='utf-8') as handle:
            content = handle.read(8000)
    except OSError:
        return stem
    tagged = _CODE_TAG_RE.search(content)
    if tagged:
        return normalize_context_code(tagged.group(1))
    meta = _CODE_META_RE.search(content)
    if meta:
        return normalize_context_code(meta.group(1))
    return stem


def codes_in_contexts_dir(contexts_dir):
    """Set of context codes under ``contexts_dir`` (recursive)."""
    found = set()
    if not contexts_dir or not os.path.isdir(contexts_dir):
        return found
    for root, _dirs, files in os.walk(contexts_dir):
        for filename in files:
            if not filename.endswith(('.md', '.py', '.xml', '.json')):
                continue
            path = os.path.join(root, filename)
            if not os.path.isfile(path):
                continue
            code = code_from_context_file(path)
            if code:
                found.add(code)
    return found


def factory_row_blocks_incoming(
    existing_source, incoming_source, owner_still_ships,
):
    """True when incoming must not overwrite factory content.

    Same owner (or empty owner) → write. Other owner that still ships the
    code → block. Other owner that no longer ships it → allow takeover.
    """
    if not existing_source or existing_source == incoming_source:
        return False
    return bool(owner_still_ships)
