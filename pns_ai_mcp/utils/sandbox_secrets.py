# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 Patanegra Soft <https://patanegra.com>
"""Which columns the AI sandbox may not read.

The sandbox reads rows as the asking user. A credential inside a row (a
provider key, a mail password, a token) stays out even when the row is open:
the turn may carry injected text, and a key read once can be repeated.

A column is secret when its model names it in ``_pns_secret_fields``, when
its name says it holds one (``password``, ``secret``, ``token``, ``api_key``
…), when it is a setting stored in a secret system parameter, or when it is a
related field that ends in a secret. A system parameter is secret by its key
under the same rule, plus any key ending in ``key`` and any key a secret
setting stores. This is a security denylist, not a product catalogue.
"""
import re

SANDBOX_CURSOR_FLAG = '_pns_ai_sandbox'

# Every denial the sandbox guard raises starts with this. The engine tells it
# apart from a real ACL denial: the code names a column it must leave out,
# so the model may fix the code and run again.
SECRET_DENIED_PREFIX = 'RelaxAICode cannot read '
SECRET_DENIED_HINT = (
    ' [HINT] This is a code fix, not a permission: name the columns you '
    'need instead of looping over _fields, or drop this one. Then run '
    'again. Never look for another way to read this value.'
)


def is_secret_read_denial(message):
    """True when *message* is the sandbox guard's own denial, not an ACL one."""
    return str(message or '').startswith(SECRET_DENIED_PREFIX)

_SECRET_WORDS = frozenset({
    'password', 'passwd', 'pass', 'pwd', 'secret', 'token', 'apikey',
})
_NAMED_TYPES = frozenset({'char', 'text', 'binary', 'json'})
_RELATED_DEPTH = 8


def sandbox_cursor(cr):
    """True on the read-only cursor ``get_readonly_env`` opens for the sandbox."""
    return bool(getattr(cr, SANDBOX_CURSOR_FLAG, False))


def _words(name):
    return [w for w in re.split(r'[^a-z0-9]+', str(name or '').lower()) if w]


def secret_name(name, key_suffix=False):
    """True when *name* says it holds a credential."""
    words = _words(name)
    if any(w in _SECRET_WORDS for w in words):
        return True
    if any(a == 'api' and b == 'key' for a, b in zip(words, words[1:])):
        return True
    return key_suffix and len(words) > 1 and words[-1] == 'key'


def _related_names(field):
    related = getattr(field, 'related', None)
    if not related:
        return []
    if isinstance(related, str):
        return related.split('.')
    return list(related)


def field_is_secret(model, name, depth=0):
    """True when column *name* of *model* holds a credential."""
    field = model._fields.get(name)
    if field is None:
        return False
    if name in (getattr(model, '_pns_secret_fields', ()) or ()):
        return True
    param = getattr(field, 'config_parameter', None)
    if param and (secret_name(name, key_suffix=True)
                  or secret_name(param, key_suffix=True)):
        return True
    if field.type in _NAMED_TYPES and secret_name(name):
        return True
    names = _related_names(field)
    if not names or depth >= _RELATED_DEPTH:
        return False
    target = model
    for step in names[:-1]:
        hop = target._fields.get(step)
        comodel = getattr(hop, 'comodel_name', None) if hop is not None else None
        if not comodel:
            return False
        target = target.env[comodel]
    return field_is_secret(target, names[-1], depth + 1)


def secret_setting_params(settings):
    """System parameter keys that a secret setting of *settings* stores."""
    keys = set()
    for name, field in settings._fields.items():
        param = getattr(field, 'config_parameter', None)
        if param and field_is_secret(settings, name):
            keys.add(param)
    return frozenset(keys)


def secret_param_key(key, setting_keys=frozenset()):
    """True when system parameter *key* holds a credential."""
    return key in setting_keys or secret_name(key, key_suffix=True)


def _registry_cache(env):
    registry = env.registry
    cache = registry.__dict__.get('_pns_sandbox_secrets')
    if cache is None:
        cache = {}
        try:
            registry._pns_sandbox_secrets = cache
        except Exception:
            pass
    return cache


def secret_column(model, name):
    """``field_is_secret`` remembered per registry (models change only with it)."""
    cache = _registry_cache(model.env)
    key = (model._name, name)
    if key not in cache:
        cache[key] = field_is_secret(model, name)
    return cache[key]


def cached_setting_params(env):
    cache = _registry_cache(env)
    if 'setting_params' not in cache:
        cache['setting_params'] = (
            secret_setting_params(env['res.config.settings'])
            if 'res.config.settings' in env else frozenset()
        )
    return cache['setting_params']
