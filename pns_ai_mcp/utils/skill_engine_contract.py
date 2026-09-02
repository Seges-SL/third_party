# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 Patanegra Soft <https://patanegra.com>
"""Published skill↔engine contract: capabilities, YAML keys, result protocol.

The engine MAY honour these names. Anything else that looks like an engine
hook (``requires:``, unknown front-matter, unpublished ``__dunder__``) is
rejected at create/import — the skill must change, or a *nameless* generic
mechanism must be proposed. Never patch the addon for one slash command.

Result ``__dunder__`` keys are **not** a handwritten allowlist. They are
the tokens the engine source already reads or writes on a result payload.
Add a reader in the engine → the skill may emit it. Invent a name the
engine does not cite → import/save fails.
"""
from __future__ import annotations

import re
from pathlib import Path

# Front-matter keys the importer / constrain understands.
SKILL_FRONT_MATTER_KEYS = frozenset((
    'skill',
    'code',
    'artifact',
    'name',
    'description',
    'agent_codes',
    'agent_code',
    'version',
    'painter',
    'formatting_mode',
    'param_schema',
    'arg_hint',
    'args_policy',
    'triggers',
    'sequence',
    'active',
    'context_codes',
    'requires',
))

# Capabilities a skill may list in ``requires:`` (comma-separated).
SKILL_ENGINE_CAPABILITIES = frozenset((
    'painter-local',
    'painter-free',
    'report_outline',
    'closing_required',
    'recommendations_stub',
    'recommendations_heading',
    'propose_steps',
    'return_direct',
    'footer',
    'param_schema',
    'args_policy',
    'await_args',
    'skill_state',
    'card',
    'map',
))

# Interpreter / sandbox names that appear quoted in engine files but are
# not a skill-result protocol key. Python's set; it does not track features.
_NOT_RESULT_PROTOCOL = frozenset((
    '__import__',
    '__builtins__',
    '__builtin__',
    '__name__',
    '__class__',
    '__dict__',
    '__doc__',
    '__file__',
    '__module__',
    '__package__',
    '__spec__',
    '__loader__',
    '__cached__',
    '__annotations__',
    '__path__',
    '__all__',
    '__version__',
    '__bases__',
    '__mro__',
    '__subclasses__',
    '__globals__',
    '__code__',
    '__func__',
    '__self__',
    '__closure__',
    '__wrapped__',
    '__qualname__',
    '__traceback__',
))

# This file is the scanner, not a source of protocol names.
_SKIP_ENGINE_FILES = frozenset((
    'skill_engine_contract.py',
    'validators.py',
    'context_builder.py',
    'controller_helpers.py',
))

_DUNDER_IN_SOURCE = re.compile(
    r"""(?:['"])(__[a-z0-9_]+__)(?:['"])"""
)


def _engine_scan_files():
    """Python files that consume or produce a skill/result payload."""
    common = Path(__file__).resolve().parents[1]
    found = []
    for folder in (common / 'utils', common / 'controllers'):
        if not folder.is_dir():
            continue
        for path in sorted(folder.glob('*.py')):
            if path.name in _SKIP_ENGINE_FILES:
                continue
            found.append(path)
    return found


def dunders_in_text(text):
    """Quoted ``__token__`` names in *text* that can be result protocol."""
    found = set()
    for match in _DUNDER_IN_SOURCE.finditer(text or ''):
        key = match.group(1)
        if key in _NOT_RESULT_PROTOCOL:
            continue
        found.add(key)
    return found


def published_result_dunders():
    """``__dunder__`` keys the engine source already cites on a payload."""
    found = set()
    for path in _engine_scan_files():
        try:
            text = path.read_text(encoding='utf-8')
        except OSError:
            continue
        found.update(dunders_in_text(text))
    return frozenset(found)


SKILL_RESULT_DUNDERS = published_result_dunders()


def parse_requires(raw):
    """Split a front-matter ``requires`` value into capability tokens."""
    if raw is None:
        return []
    if isinstance(raw, (list, tuple)):
        return [str(x).strip() for x in raw if str(x).strip()]
    text = str(raw).strip()
    if not text:
        return []
    text = text.strip('[]')
    return [p.strip().strip("'\"") for p in text.split(',') if p.strip().strip("'\"")]


def unknown_front_matter_keys(meta):
    return sorted(
        k for k in (meta or {})
        if k and k not in SKILL_FRONT_MATTER_KEYS
    )


def unknown_requires(meta):
    return sorted(
        cap for cap in parse_requires((meta or {}).get('requires'))
        if cap not in SKILL_ENGINE_CAPABILITIES
    )


def unpublished_dunders_in_mapping(mapping):
    if not isinstance(mapping, dict):
        return []
    published = published_result_dunders()
    return sorted(
        k for k in mapping
        if isinstance(k, str)
        and k.startswith('__')
        and k.endswith('__')
        and k not in published
    )


def unpublished_dunders_in_source(code):
    published = published_result_dunders()
    found = set()
    for match in _DUNDER_IN_SOURCE.finditer(code or ''):
        key = match.group(1)
        if key not in published:
            found.add(key)
    return sorted(found)


def skill_contract_violations(meta=None, code_body=None, result=None):
    """Return unpublished names (capabilities / keys). Empty = OK."""
    bad = []
    bad.extend(unknown_front_matter_keys(meta))
    bad.extend(unknown_requires(meta))
    bad.extend(unpublished_dunders_in_source(code_body))
    bad.extend(unpublished_dunders_in_mapping(result))
    # Stable unique
    seen = set()
    out = []
    for item in bad:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out
