# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 Seges
# Seges: parche 18 (PNS-19, seguridad). Ver docs/pendiente/parches_pns_ai.md
"""Forget the secret columns from the thread cache around box A.

Defence behind the read check of ``models/seges_box_a_read.py``. Odoo 14 keeps
one record cache per thread (``odoo/api.py``), shared by box A's cursor and
by the caller's. Two moments:

- B: when ``open_readonly_env`` opens box A, the secret columns the caller
  left in the cache are forgotten;
- B2: after each module helper of the sandbox (``collect_sandbox_helpers``),
  what the helper read as sudo is forgotten too.

A column is secret by the vendor's criterion, ``_pns_hidden_column`` on an
empty recordset (``models/sandbox_secret_read.py``); for
``ir.config_parameter`` that includes ``value``. Only the cache is touched:
pending writes live in ``towrite`` and are kept.
"""

from .sandbox_secrets import SANDBOX_CURSOR_FLAG

_PAIRS_KEY = '_seges_box_a_secret_pairs'


def _secret_pairs(env):
    """``(model, field)`` names of the secret columns, remembered per registry.

    Names, not ``Field`` objects: these are rebuilt on every model load.
    """
    registry = env.registry
    pairs = registry.__dict__.get(_PAIRS_KEY)
    if pairs is None:
        pairs = tuple(
            (model_name, fname)
            for model_name in sorted(registry)
            for fname in env[model_name]._fields
            if env[model_name].browse()._pns_hidden_column(fname)
        )
        setattr(registry, _PAIRS_KEY, pairs)
    return pairs


def _seges_forget_secret_columns(env):
    """Invalidate the secret columns, on every record, in the thread cache."""
    spec = []
    for model_name, fname in _secret_pairs(env):
        field = env[model_name]._fields.get(fname)
        if field is not None:
            spec.append((field, None))
    if spec:
        env.cache.invalidate(spec)


def box_a_cursor(cr):
    """True on box A's cursor (the flag ``open_readonly_env`` sets on it)."""
    return bool(getattr(cr, '__dict__', {}).get(SANDBOX_CURSOR_FLAG))


def forget_after_helper(env, helper):
    """``helper`` that forgets the secret columns when it returns or raises.

    A plain wrapper, without ``functools.wraps``: no ``__wrapped__`` to the
    real callable.
    """
    def _seges_box_a_helper(*args, **kwargs):
        try:
            return helper(*args, **kwargs)
        finally:
            _seges_forget_secret_columns(env)
    return _seges_box_a_helper
