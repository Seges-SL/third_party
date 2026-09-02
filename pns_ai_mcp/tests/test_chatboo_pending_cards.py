# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""Chatboo card restore reads the same pending rows as Security."""
from datetime import timedelta

from odoo import api, fields
from odoo.tests import tagged, TransactionCase
from odoo.tests.common import new_test_user


def _make_pending(env, user_id, title='card restore', vid_suffix='own'):
    return env['ai.safe.operation'].create_verification(
        operation_type='write',
        model_name='res.partner',
        records_count=1,
        changes_info={'plan': ['write partner'], 'danger_level': 'medium'},
        user_id=user_id,
        tool_name='test_chatboo_pending_cards',
        operation_data={
            'plan_steps': [{
                'op': 'write', 'model': 'res.partner',
                'ids': [1], 'values': {'comment': vid_suffix},
            }],
            'title': title,
            'plan': ['write partner'],
            'danger_level': 'medium',
        },
    )


@tagged('post_install', '-at_install', 'pns_ai_mcp')
class TestChatbooPendingCards(TransactionCase):

    def test_pending_payload_matches_sse_shape_and_skips_closed(self):
        mine = _make_pending(self.env, self.env.uid, title='my write')
        closed = _make_pending(self.env, self.env.uid, title='already done')
        closed.write({'status': 'cancelled'})

        other = new_test_user(
            self.env, login='pns_other_pending_card',
            groups='base.group_user,pns_ai_mcp.group_ai_writer',
        )
        _make_pending(
            self.env, other.id, title='theirs', vid_suffix='other',
        )

        before = self.env['ai.safe.operation'].search_count([])
        items = self.env['ai.safe.operation'].chatboo_pending_card_payloads()
        after = self.env['ai.safe.operation'].search_count([])
        self.assertEqual(before, after)

        vids = [row['verification_id'] for row in items]
        self.assertIn(mine.verification_id, vids)
        self.assertNotIn(closed.verification_id, vids)
        payload = next(
            row for row in items if row['verification_id'] == mine.verification_id
        )
        self.assertEqual(payload['title'], 'my write')
        self.assertEqual(payload['plan'], ['write partner'])
        self.assertEqual(payload['danger_level'], 'medium')
        self.assertTrue(all(
            row['verification_id'] != closed.verification_id for row in items
        ))
        other_env = api.Environment(self.env.cr, other.id, {})
        other_items = other_env['ai.safe.operation'].chatboo_pending_card_payloads()
        self.assertEqual(
            [row['title'] for row in other_items],
            ['theirs'],
        )

    def test_expired_pending_is_not_restored(self):
        op = _make_pending(self.env, self.env.uid, title='stale')
        past = fields.Datetime.now() - timedelta(hours=1)
        op.write({'create_date': past, 'expires_at': past})
        items = self.env['ai.safe.operation'].chatboo_pending_card_payloads()
        self.assertNotIn(op.verification_id, [
            row['verification_id'] for row in items
        ])
