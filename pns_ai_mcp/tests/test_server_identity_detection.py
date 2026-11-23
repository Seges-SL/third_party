# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 Patanegra Soft <https://patanegra.com>
"""API Detection hangs off ai.api.server: create / archive / unlink / Suggest."""
import uuid
from unittest.mock import patch

from odoo.tests import tagged, TransactionCase

from odoo.addons.pns_ai_mcp.utils.domain_index import (
    identity_detection_triggers,
    normalize_text,
)


@tagged('post_install', '-at_install', 'pns_ai_mcp')
class TestServerIdentityDetection(TransactionCase):

    def _make_server(self, **vals):
        suffix = uuid.uuid4().hex[:8]
        payload = {
            'name': 'My Service Desk',
            'code': 'desk-svc-%s' % suffix,
            'api_type': 'mcp',
            'server_type': 'stdio',
        }
        payload.update(vals)
        return self.env['ai.api.server'].create(payload)

    def _rows(self, server):
        return self.env['ai.context'].with_context(active_test=False).search([
            ('api_server_id', '=', server.id),
        ])

    def _folded(self, server):
        Context = self.env['ai.context']
        tokens = []
        for rec in self._rows(server):
            tokens.extend(Context._discovery_parse_triggers(rec.discovery_triggers))
        return {normalize_text(t) for t in tokens}

    def test_create_server_upserts_identity_detection(self):
        srv = self._make_server()
        rows = self._rows(srv)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows.discovery_target, srv.code)
        self.assertEqual(rows.discovery_target_kind, 'api_server')
        folded = self._folded(srv)
        want = {normalize_text(t) for t in identity_detection_triggers(
            srv.code, srv.name,
        )}
        self.assertTrue(want)
        self.assertTrue(want.issubset(folded))
        self.assertIn(normalize_text(srv.code), folded)
        self.assertIn('service', folded)
        self.assertIn('desk', folded)

    def test_write_name_merges_identity_tokens(self):
        srv = self._make_server()
        srv.write({'name': 'Clock Portal'})
        folded = self._folded(srv)
        self.assertIn('clock', folded)
        self.assertIn('portal', folded)
        self.assertIn('service', folded)
        self.assertIn(normalize_text(srv.code), folded)

    def test_archive_deactivates_detection_row(self):
        srv = self._make_server()
        srv.write({'active': False})
        rows = self._rows(srv)
        self.assertTrue(rows)
        self.assertFalse(any(rows.mapped('active')))

    def test_unlink_server_removes_detection_rows(self):
        srv = self._make_server()
        rows = self._rows(srv)
        self.assertTrue(rows)
        ctx_ids = rows.ids
        srv.unlink()
        leftover = self.env['ai.context'].with_context(active_test=False).browse(
            ctx_ids,
        ).exists()
        self.assertFalse(leftover)

    def test_suggest_keeps_identity_tokens(self):
        srv = self._make_server()
        identity = {normalize_text(t) for t in identity_detection_triggers(
            srv.code, srv.name,
        )}
        with patch.object(
            type(srv),
            '_hybrid_detection_triggers',
            return_value=(['clock-in'], True, {}),
        ):
            srv.action_suggest_detection()
        folded = self._folded(srv)
        self.assertTrue(identity.issubset(folded))
        self.assertIn('clock-in', folded)
