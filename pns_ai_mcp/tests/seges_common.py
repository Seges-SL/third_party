# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 Seges
# Seges: tests de la fase 3a sobre 3.1.973 (archivo común). Ver docs/pendiente/parches_pns_ai.md
# Seges: copiado a la 17 (fase 2, T0), sin cambios; los documentos que citan las líneas anteriores están en
# 14.0. Ver docs/pendiente/parches_pns_ai.md
# Seges: ampliado en la 17 (fase 2, T3): _CursorSpy, copiado de seges_pruebas_3996
# (test_side_cursors.py), para los tests del parche 18.
# Ver docs/pendiente/parches_pns_ai.md
"""Piezas comunes de los tests de Seges que ejecutan ``tool_relaxaicode``.

``_StubController`` estaba en ``test_seges_sandbox_credentials.py`` (parche 18)
en la rama 14.0-pns-ai-3879; pasa aquí para que los tests de los parches 23 y 24
no dependan del test del 18. ``_CursorSpy`` vigila los cursores que abre la caja A
(tests del parche 18 en la 17). Este módulo no es un test: no se importa en
``tests/__init__.py``.
"""

import contextlib
import re

import psycopg2
from psycopg2 import errorcodes

from odoo.addons.pns_ai_mcp.controllers.controller_helpers import get_readonly_env

_WRITE_TABLE = re.compile(
    r'^\s*(?:UPDATE\s+(?:ONLY\s+)?|INSERT\s+INTO\s+|DELETE\s+FROM\s+)"?(\w+)"?',
    re.IGNORECASE,
)


def _table_of(query):
    """Table a query writes (never its parameters), or '?'."""
    text = query if isinstance(query, str) else getattr(query, "code", "")
    found = _WRITE_TABLE.match(text or "")
    return found.group(1) if found else "?"


class _StubController:
    """Lo que tool_relaxaicode pide al controlador (como el test e2e del fabricante)."""

    def __init__(self, env):
        self.env = env
        self.cursors = []

    def _get_env_for_operation(self, operation_type='read'):
        return self.env

    def _get_readonly_env(self):
        ro_env, ro_cr = get_readonly_env(self)
        self.cursors.append(ro_cr)
        return ro_env, ro_cr

    def _check_mcp_permissions(self, operation_type):
        return True, ''

    def _cancel_pending_verifications_for_user(self, user_id, reason=''):
        return 0

    def _get_user_locale(self):
        return 'en_US'

    def _get_company_lang(self):
        return False

    def _log_mcp_operation(self, *args, **kwargs):
        return None


class _CursorSpy:
    """Watch the cursors that registry.cursor() opens while ``watching()`` is on.

    For each one: its class, its commits and rollbacks, the lock timeouts it hit
    and, right before every commit or rollback, the value of ``probe`` (a check
    of the caller's state). With ``lock_timeout``, each watched cursor first runs
    SET LOCAL lock_timeout, so waiting for a row the test holds becomes an error
    instead of a hang.
    """

    def __init__(self, test, lock_timeout=False):
        self.on = False
        self.probe = None
        self.cursors = []
        self.lock_timeout = lock_timeout
        registry_cls = type(test.registry)
        real_cursor = registry_cls.cursor
        spy = self

        def cursor(registry):
            cr = real_cursor(registry)
            if spy.on:
                spy._watch(cr)
            return cr

        test.patch(registry_cls, "cursor", cursor)

    def _watch(self, cr):
        info = {
            "kind": type(cr).__name__,
            "commits": 0,
            "rollbacks": 0,
            "probes": [],
            "lock_waits": [],
        }
        self.cursors.append(info)
        real_commit, real_rollback, real_execute = cr.commit, cr.rollback, cr.execute
        spy = self

        def commit():
            info["commits"] += 1
            if spy.probe:
                info["probes"].append(("commit", spy.probe()))
            return real_commit()

        def rollback():
            info["rollbacks"] += 1
            if spy.probe:
                info["probes"].append(("rollback", spy.probe()))
            return real_rollback()

        def execute(query, params=None, log_exceptions=True):
            try:
                return real_execute(query, params, log_exceptions)
            except psycopg2.Error as exc:
                if exc.pgcode == errorcodes.LOCK_NOT_AVAILABLE:
                    info["lock_waits"].append(_table_of(query))
                raise

        cr.commit, cr.rollback, cr.execute = commit, rollback, execute
        if self.lock_timeout:
            real_execute("SET LOCAL lock_timeout = '3s'")

    @contextlib.contextmanager
    def watching(self, probe=None):
        self.on, self.probe = True, probe
        try:
            yield self
        finally:
            self.on, self.probe = False, None
