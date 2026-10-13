# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""Cursor + Environment for a background job thread (Odoo 14 and 19)."""

import contextlib
import threading

import odoo
from odoo import api


def env_manage():
    """Odoo 14 needs ``Environment.manage()`` outside a request."""
    manage = getattr(api.Environment, 'manage', None)
    if manage is not None:
        return manage()
    return contextlib.nullcontext()


def registry_of(dbname):
    reg = getattr(odoo, 'registry', None)
    if callable(reg):
        return reg(dbname)
    from odoo.modules.registry import Registry
    return Registry(dbname)


def is_test_mode(env):
    if getattr(threading.current_thread(), 'testing', False):
        return True
    fn = getattr(env.registry, 'in_test_mode', None)
    if callable(fn):
        try:
            return bool(fn())
        except Exception:
            return False
    return False
