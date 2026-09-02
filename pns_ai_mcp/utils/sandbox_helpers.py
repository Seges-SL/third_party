# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 Patanegra Soft <https://patanegra.com>
"""Sandbox-module sync: optional helpers from the live Odoo registry.

A module opts in with ``_sandbox_helper_provider = True`` and a
``sandbox_helpers()`` method that returns ``{name: callable}``. The engine
does not name addons. Uninstall drops the model from the registry; the
next ``build_safe_context`` simply does not see those names. No persisted
cache — a stored list would leave zombie helpers after uninstall.
"""
import logging

_logger = logging.getLogger(__name__)

PROVIDER_FLAG = '_sandbox_helper_provider'


def iter_provider_model_names(env):
    """Sorted model names in ``env.registry`` (empty if there is no registry)."""
    registry = getattr(env, 'registry', None)
    if registry is None:
        return []
    try:
        names = list(registry)
    except TypeError:
        return []
    return sorted(name for name in names if isinstance(name, str))


def _model_class(env, model_name):
    registry = getattr(env, 'registry', None)
    if registry is None:
        return None
    try:
        return registry[model_name]
    except Exception:
        return None


def is_sandbox_helper_provider(env, model_name):
    """True when the model class (or recordset) opted in with the flag."""
    model_cls = _model_class(env, model_name)
    if model_cls is not None and getattr(model_cls, PROVIDER_FLAG, False):
        return True
    try:
        rec = env[model_name]
    except Exception:
        return False
    return bool(getattr(rec, PROVIDER_FLAG, False))


def collect_sandbox_helpers(env, occupied=None):
    """Merge opted-in ``sandbox_helpers()`` dicts.

    Engine keys in ``occupied`` always win (silent skip). The first provider
    in sorted model-name order wins a name; later collisions are logged.
    """
    occupied = set(occupied or ())
    collected = {}
    if env is None:
        return collected
    for model_name in iter_provider_model_names(env):
        if not is_sandbox_helper_provider(env, model_name):
            continue
        try:
            rec = env[model_name]
            if hasattr(rec, 'sudo'):
                rec = rec.sudo()
            helpers = rec.sandbox_helpers()
        except Exception as exc:
            _logger.warning(
                'sandbox-module sync: skip %s: %s', model_name, exc,
            )
            continue
        if not isinstance(helpers, dict):
            continue
        for key, value in helpers.items():
            if not key or not isinstance(key, str) or not callable(value):
                continue
            if key in occupied:
                continue
            if key in collected:
                _logger.warning(
                    'sandbox-module sync: %s from %s skipped, already published',
                    key, model_name,
                )
                continue
            collected[key] = value
    return collected
