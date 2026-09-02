# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 Patanegra Soft <https://patanegra.com>
"""Literal catalog + slash prefixes for instance-authored skills.

Code is snake_case; the chat command is kebab-case. Both prefixes are
optional (empty = none). No ``{company}`` / ``{user}`` interpolation.
Factory first-install seeds ``custom_`` / ``custom-`` (ICP via post_init).
A later ``-u`` does not rewrite existing ICPs. This module never names a tenant.
"""
from __future__ import annotations

import re

ICP_SKILL_CODE_PREFIX = 'pns_ai_mcp.skill_code_prefix'
ICP_SKILL_COMMAND_PREFIX = 'pns_ai_mcp.skill_command_prefix'
DEFAULT_SKILL_CODE_PREFIX = 'custom_'
DEFAULT_SKILL_COMMAND_PREFIX = 'custom-'


def normalize_skill_code_prefix(raw):
    """Snake prefix with a trailing underscore. Empty → ``''``."""
    text = (raw or '').strip().lower()
    text = re.sub(r'[^a-z0-9_]+', '_', text).strip('_')
    if not text:
        return ''
    return text + '_'


def normalize_skill_command_prefix(raw):
    """Kebab prefix with a trailing hyphen. Empty → ``''``."""
    text = (raw or '').strip().lower()
    text = re.sub(r'[^a-z0-9]+', '-', text).strip('-')
    if not text:
        return ''
    return text + '-'


def slash_slug(text, default='captured-skill'):
    """Kebab token for the chat slash (no leading ``/``)."""
    text = (text or '').strip().lower()
    text = re.sub(r'[^a-z0-9]+', '-', text).strip('-')
    return (text[:48] if text else '') or default


def _fold_prefix_forms(raw):
    """Return ``(snake_with_us, kebab_with_hyphen)`` or ``('', '')``."""
    text = (raw or '').strip().lower()
    if not text:
        return '', ''
    snake = re.sub(r'[^a-z0-9_]+', '_', text).strip('_')
    kebab = re.sub(r'[^a-z0-9]+', '-', text).strip('-')
    return (
        (snake + '_') if snake else '',
        (kebab + '-') if kebab else '',
    )


def strip_prefix_stem(token, prefixes):
    """Token without the first matching prefix. Stem is snake_case.

    Longer prefixes win (``custom_occ_`` before leftover ``custom_``).
    """
    raw = (token or '').strip().lower()
    if not raw:
        return ''
    snake = re.sub(r'[^a-z0-9_]+', '_', raw).strip('_')
    kebab = re.sub(r'[^a-z0-9]+', '-', raw).strip('-')
    folded = []
    for pref in prefixes or ():
        p_snake, p_kebab = _fold_prefix_forms(pref)
        if p_snake or p_kebab:
            folded.append((p_snake, p_kebab))
    folded.sort(key=lambda pair: max(len(pair[0]), len(pair[1])), reverse=True)
    for p_snake, p_kebab in folded:
        if p_snake and (snake == p_snake.rstrip('_') or snake.startswith(p_snake)):
            rest = snake[len(p_snake.rstrip('_')):].strip('_')
            if rest:
                return rest
        if p_kebab and (kebab == p_kebab.rstrip('-') or kebab.startswith(p_kebab)):
            rest = kebab[len(p_kebab.rstrip('-')):].strip('-')
            if rest:
                return rest.replace('-', '_')
    return snake


def invoke_lookup_tokens(token, code_prefix='', command_prefix=''):
    """Tokens to match a slash the user typed (stem or already prefixed)."""
    raw = (token or '').strip().lower().lstrip('/')
    if not raw:
        return ()
    seen = []

    def _add(value):
        text = (value or '').strip().lower()
        if text and text not in seen:
            seen.append(text)

    _add(raw)
    _add(raw.replace('-', '_'))
    _add(raw.replace('_', '-'))
    code, command = instance_identity(raw, code_prefix, command_prefix)
    _add(command)
    _add(code)
    _add(code.replace('_', '-'))
    return tuple(seen)


def instance_identity(slash_or_code, code_prefix='', command_prefix=''):
    """Return ``(catalog_code, command)`` for a user-authored skill.

    ``facturacion`` + ``occ_custom_`` / ``occ-`` →
    ``('occ_custom_facturacion', 'occ-facturacion')``.
    If the token already starts with a prefix, do not double it.
    """
    cmd_pfx = normalize_skill_command_prefix(command_prefix)
    code_pfx = normalize_skill_code_prefix(code_prefix)
    slug = slash_slug(slash_or_code)
    if cmd_pfx and (slug == cmd_pfx.rstrip('-') or slug.startswith(cmd_pfx)):
        rest = slug[len(cmd_pfx):].strip('-')
        if rest:
            slug = rest
    stem = slug.replace('-', '_')
    if code_pfx and stem.startswith(code_pfx):
        rest = stem[len(code_pfx):].strip('_')
        if rest:
            stem = rest
            slug = stem.replace('_', '-')
    code = (code_pfx + stem) if code_pfx else stem
    command = (cmd_pfx + slug) if cmd_pfx else slug
    return code, command


def is_auto_prefixed_code(code, slash, code_prefix, command_prefix=''):
    """True when ``code`` is exactly prefix + slug of ``slash``."""
    expected, _command = instance_identity(slash, code_prefix, command_prefix)
    return (code or '') == expected


def uniquify_catalog_code(code, taken):
    """Append ``_2``, ``_3``… if ``code`` is already in ``taken``."""
    taken = set(taken or ())
    if code not in taken:
        return code
    n = 2
    while True:
        candidate = '%s_%s' % (code, n)
        if candidate not in taken:
            return candidate
        n += 1


def get_skill_code_prefix(env):
    """Read and normalize the catalog-code ICP (needs an Odoo env)."""
    raw = env['ir.config_parameter'].sudo().get_param(
        ICP_SKILL_CODE_PREFIX, DEFAULT_SKILL_CODE_PREFIX,
    )
    return normalize_skill_code_prefix(raw)


def get_skill_command_prefix(env):
    """Read and normalize the slash-command ICP (needs an Odoo env)."""
    raw = env['ir.config_parameter'].sudo().get_param(
        ICP_SKILL_COMMAND_PREFIX, DEFAULT_SKILL_COMMAND_PREFIX,
    )
    return normalize_skill_command_prefix(raw)


def reserved_slash_commands():
    """Builtin / axis slash tokens the prefixes must not equal."""
    tokens = {
        'skill', 'skills', 'help', 'ayuda', '?',
        # Retired Chatboo slash: keep reserved so nobody recycles the name.
        'reload-skills',
        'create-skill', 'delete-skill', 'rename-skill', 'mode',
        'painter-local', 'painter-free', 'foot-verbose', 'foot-laconic',
        'show-table', 'show-chart',
    }
    try:
        from .skill_help import BUILTIN_SLASH_META
        tokens.update(BUILTIN_SLASH_META.keys())
    except Exception:
        pass
    try:
        from .formatting_mode_policy import AXIS_COMMANDS
        tokens.update(AXIS_COMMANDS.keys())
    except Exception:
        pass
    return frozenset(tokens)


def prefix_stomps_slash(code_prefix, command_prefix, taken_commands=()):
    """True when a prefix (without trailer) equals a reserved or taken slash."""
    folded = []
    cmd = normalize_skill_command_prefix(command_prefix).rstrip('-')
    code = normalize_skill_code_prefix(code_prefix).rstrip('_').replace('_', '-')
    if cmd:
        folded.append(cmd)
    if code:
        folded.append(code)
    reserved = set(reserved_slash_commands())
    reserved.update(taken_commands or ())
    return any(token in reserved for token in folded)


def stem_for_reapply(code, command, old_code_prefixes, old_command_prefixes):
    """Business stem (snake) after stripping historical + current prefixes."""
    prefixes = list(old_command_prefixes or ()) + list(old_code_prefixes or ())
    for token in ((command or '').strip(), (code or '').strip()):
        if not token:
            continue
        stem = strip_prefix_stem(token, prefixes)
        if stem:
            return stem
    return ''


def unprefixed_twin_stems(factory_commands, command_prefix):
    """Bare slashes that duplicate a factory command already carrying the prefix.

    ``('occ-polizas', 'payroll')`` + ``occ-`` → ``{'polizas'}``.
    Empty prefix → no twins (nothing was stripped).
    """
    pfx = normalize_skill_command_prefix(command_prefix)
    if not pfx:
        return frozenset()
    stems = set()
    for raw in factory_commands or ():
        token = slash_slug(raw, default='')
        if token.startswith(pfx):
            stem = token[len(pfx):].strip('-')
            if stem:
                stems.add(stem)
    return frozenset(stems)


def is_unprefixed_slash_twin(
    command, factory_commands, command_prefix, is_system=False,
):
    """True when ``command`` is the stem of a prefixed factory slash."""
    if is_system:
        return False
    token = slash_slug(command, default='')
    if not token:
        return False
    return token in unprefixed_twin_stems(factory_commands, command_prefix)


def leftover_twin_action(
    invoke, factory_commands, command_prefix, rel_path, on_disk, is_factory,
):
    """How to retire a leftover ``/<stem>`` next to factory ``/<prefix><stem>``.

    Unused twins are deleted. ``rel_path`` / ``on_disk`` / ``is_factory``
    stay in the signature for callers; they do not spare a twin.
    """
    token = slash_slug(invoke, default='')
    if not token or token not in unprefixed_twin_stems(
        factory_commands, command_prefix,
    ):
        return ''
    return 'unlink'
