# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 Patanegra Soft <https://patanegra.com>
"""ai.context unlink: core/factory locked; leftovers and owned rows deletable."""
import uuid

from odoo.exceptions import UserError
from odoo.tests import tagged, TransactionCase

from odoo.addons.pns_ai_mcp.tests._helpers import ensure_test_agents
from odoo.addons.pns_ai_mcp.utils.compat import user_add_group, user_has_group_direct


@tagged('post_install', '-at_install', 'pns_ai_mcp')
class TestContextUnlink(TransactionCase):

    def setUp(self):
        super().setUp()
        self.agent = ensure_test_agents(self.env)
        self.admin_group = self.env.ref('pns_ai_mcp.group_ai_admin')
        self.admin_user = self.env.ref('base.user_admin')
        if not user_has_group_direct(self.admin_user, self.admin_group):
            user_add_group(self.admin_user, self.admin_group)
        demo = self.env.ref('base.user_demo', raise_if_not_found=False)
        if not demo:
            self.skipTest('base.user_demo no instalado')
        self.user_a = demo
        writer = self.env.ref('pns_ai_mcp.group_ai_writer')
        if not user_has_group_direct(self.user_a, writer):
            user_add_group(self.user_a, writer)
        self._uid = uuid.uuid4().hex[:8]

    def _code(self, base):
        return '%s_%s' % (base, self._uid)

    def _ctx_body(self, code):
        return (
            '<context><metadata><code>%s</code></metadata>'
            '<body>%s</body></context>'
        ) % (code, code)

    def test_core_context_cannot_be_unlinked(self):
        core = self.env['ai.context'].search([
            ('context_type', '=', 'core'),
        ], limit=1)
        if not core:
            self.skipTest('no core context in this database')
        with self.assertRaises(UserError):
            core.unlink()

    def test_factory_file_context_cannot_be_unlinked(self):
        Context = self.env['ai.context']
        live = Context.search([
            ('owner_id', '=', False),
            ('source_module', '=', 'pns_ai_mcp'),
            ('context_type', '!=', 'core'),
        ])
        locked = live.filtered(lambda rec: rec._is_shipped_factory_locked())
        if locked:
            with self.assertRaises(UserError):
                locked[0].unlink()
            return
        code = self._code('factory_lock')
        ctx = Context.sudo().create({
            'code': code,
            'description': 'factory lock',
            'context_type': 'domain',
            'content': self._ctx_body(code),
            'source_module': 'pns_ai_mcp',
            'rel_path': 'contexts/discovery/discovery_geo.json',
            'owner_id': False,
        })
        if not ctx._factory_source_file_exists():
            ctx.with_context(skip_hardcoded_restrictions=True).unlink()
            self.skipTest('factory source files not on this addon path')
        with self.assertRaises(UserError):
            ctx.unlink()
        ctx.with_context(skip_hardcoded_restrictions=True).unlink()

    def test_owned_context_can_be_unlinked(self):
        code = self._code('owned_unlink')
        ctx = self.env['ai.context'].sudo().create({
            'code': code,
            'description': code,
            'context_type': 'domain',
            'content': self._ctx_body(code),
            'owner_id': self.user_a.id,
        })
        ctx_id = ctx.id
        ctx.unlink()
        self.assertFalse(self.env['ai.context'].browse(ctx_id).exists())

    def test_leftover_discovery_can_be_unlinked(self):
        code = self._code('disc_leftover')
        ctx = self.env['ai.context'].sudo().create({
            'code': code,
            'description': 'fr leftover',
            'context_type': 'discovery',
            'locale': 'fr_FR',
            'content': self._ctx_body(code),
            'source_module': 'pns_ai_mcp',
            'owner_id': False,
        })
        ctx_id = ctx.id
        ctx.unlink()
        self.assertFalse(self.env['ai.context'].browse(ctx_id).exists())
