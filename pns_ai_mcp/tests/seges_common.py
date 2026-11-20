# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 Seges
# Seges: tests de la fase 3a sobre 3.1.973 (archivo común). Ver docs/pendiente/parches_pns_ai.md
"""Piezas comunes de los tests de Seges que ejecutan ``tool_relaxaicode``.

``_StubController`` estaba en ``test_seges_sandbox_credentials.py`` (parche 18)
en la rama 14.0-pns-ai-3879; pasa aquí para que los tests de los parches 23 y 24
no dependan del test del 18. Este módulo no es un test: no se importa en
``tests/__init__.py``.
"""

from odoo.addons.pns_ai_mcp.controllers.controller_helpers import get_readonly_env


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
