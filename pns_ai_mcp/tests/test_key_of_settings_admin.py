# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 Patanegra Soft <https://patanegra.com>
"""A Settings administrator's MCP key is set only by the system, another
Settings administrator or that same person.

A key logs in as its owner. An AI administrator without Settings rights
manages everyone else's key, but not one that would let them in as a
Settings administrator: not by generating it, pasting it, writing the hash
or importing it from a file. The import still writes the AI permissions.
"""
from odoo.exceptions import AccessError
from odoo.tests import tagged, TransactionCase

from odoo.addons.pns_ai_mcp.tests._helpers import create_test_user
from odoo.addons.pns_ai_mcp.utils.api_key import hash_api_key
from odoo.addons.pns_ai_mcp.utils.compat import invalidate_recordset_fields
from odoo.addons.pns_ai_mcp.utils.config_backup import _import_users


@tagged('post_install', '-at_install', 'pns_ai_mcp')
class TestKeyOfSettingsAdmin(TransactionCase):

    def setUp(self):
        super().setUp()
        ref = self.env.ref
        self.ai_admin = create_test_user(
            self.env, prefix='pns_key_ai_admin',
            groups=[ref('base.group_user').id, ref('pns_ai_mcp.group_ai_admin').id],
        )
        self.settings_admin = create_test_user(
            self.env, prefix='pns_key_settings',
            groups=[ref('base.group_user').id, ref('base.group_system').id],
        )
        self.employee = create_test_user(self.env, prefix='pns_key_employee')
        self.other_settings_admin = create_test_user(
            self.env, prefix='pns_key_settings_2',
            groups=[
                ref('base.group_user').id,
                ref('base.group_system').id,
                ref('pns_ai_mcp.group_ai_admin').id,
            ],
        )

    def _row(self, user, as_user):
        McpUser = self.env['ai.mcp.user'].sudo().with_context(mcp_skip_ensure_all_users=True)
        row = McpUser.search([('user_id', '=', user.id)], limit=1)
        if not row:
            row = McpUser.create({'user_id': user.id})
        return row.with_user(as_user)

    def test_ai_admin_cannot_paste_or_generate_a_settings_admin_key(self):
        row = self._row(self.settings_admin, self.ai_admin)
        with self.assertRaises(AccessError):
            row.set_mcp_api_key('acme-key-0001')
        with self.assertRaises(AccessError):
            row.action_generate_mcp_api_key()
        self.assertFalse(row.sudo().mcp_api_key_hash)

    def test_ai_admin_cannot_write_the_hash_by_rpc(self):
        row = self._row(self.settings_admin, self.ai_admin)
        with self.assertRaises(AccessError):
            row.write({'mcp_api_key_hash': hash_api_key('acme-key-0002')})

    def test_ai_admin_still_sets_an_employee_key(self):
        row = self._row(self.employee, self.ai_admin)
        row.set_mcp_api_key('acme-key-0003')
        self.assertEqual(row.sudo().mcp_api_key_hash, hash_api_key('acme-key-0003'))

    def test_a_settings_admin_sets_another_settings_admin_key(self):
        row = self._row(self.settings_admin, self.other_settings_admin)
        row.set_mcp_api_key('acme-key-0004')
        self.assertEqual(row.sudo().mcp_api_key_hash, hash_api_key('acme-key-0004'))

    def test_import_skips_the_key_and_keeps_the_permissions(self):
        row = self._row(self.settings_admin, self.ai_admin)
        report = {'sections': {}, 'warnings': [], 'errors': []}
        _import_users(self.env(user=self.ai_admin.id), [{
            'login': self.settings_admin.login,
            'mcp_api_key': 'acme-key-0005',
            'is_ai_writer': True,
        }], report)
        self.assertEqual(report['errors'], [])
        self.assertTrue(any(self.settings_admin.login in w for w in report['warnings']))
        row = row.sudo()
        invalidate_recordset_fields(row, ['mcp_api_key_hash', 'is_ai_writer'])
        self.assertFalse(row.mcp_api_key_hash)
        self.assertTrue(row.is_ai_writer)
