# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 Patanegra Soft <https://patanegra.com>
"""What only a database can show: whose rows a user reaches, the life of a job, CSRF."""

import json
import re
import uuid
from datetime import timedelta

from odoo import fields
from odoo.exceptions import AccessError
from odoo.tests import tagged, HttpCase, TransactionCase

from odoo.addons.pns_ai_mcp.tests._helpers import create_test_user, http_status_code

_DESIGN = '<html><body><p>Example</p></body></html>'


def _internal(env, prefix, password=None):
    vals = {'password': password} if password else {}
    return create_test_user(env, prefix=prefix, **vals)


def _forget(records):
    try:
        records.invalidate_recordset()
    except AttributeError:
        records.invalidate_cache(ids=records.ids)


def _flush(env):
    if hasattr(env, 'flush_all'):
        env.flush_all()
    else:
        env['base'].flush()


def _chatboo_access(user):
    """The conversational group and an MCP key: what Chatboo asks of a user."""
    from odoo.addons.pns_ai_mcp.utils.api_key import hash_api_key
    from odoo.addons.pns_ai_mcp.utils.conversational import GROUP_AI_CONVERSATIONAL
    from odoo.addons.pns_base.utils.compat import USER_GROUPS_FIELD
    env = user.env
    user.sudo().write({USER_GROUPS_FIELD: [(4, env.ref(GROUP_AI_CONVERSATIONAL).id)]})
    McpUser = env['ai.mcp.user'].sudo()
    card = McpUser.search([('user_id', '=', user.id)], limit=1) or McpUser.create({
        'user_id': user.id,
    })
    card.write({
        'mcp_api_key_hash': hash_api_key('pns-test-%s' % uuid.uuid4().hex),
        'mcp_api_key_state': 'generated',
    })


@tagged('post_install', '-at_install', 'pns_ai_chatboo')
class TestChatbooOwnRows(TransactionCase):

    def setUp(self):
        super().setUp()
        self.ann = _internal(self.env, 'chatboo_ann')
        self.bob = _internal(self.env, 'chatboo_bob')
        Session = self.env['chatboo.session']
        self.ann_session = Session.with_user(self.ann).create({'name': 'Ann chat'})
        self.bob_session = Session.with_user(self.bob).create({'name': 'Bob chat'})

    def _job(self, session, user, **vals):
        return self.env['chatboo.canvas.job'].sudo().create(dict(
            {'session_id': session.id, 'user_id': user.id}, **vals,
        ))

    # ── Sessions ──

    def test_a_user_lists_only_their_own_sessions(self):
        mine = self.env['chatboo.session'].with_user(self.ann).search([])
        self.assertIn(self.ann_session, mine)
        self.assertNotIn(self.bob_session, mine)

    def test_another_users_session_cannot_be_read_changed_or_deleted(self):
        theirs = self.bob_session.with_user(self.ann)
        with self.assertRaises(AccessError):
            theirs.read(['messages'])
        with self.assertRaises(AccessError):
            theirs.write({'messages': '[]'})
        with self.assertRaises(AccessError):
            theirs.unlink()

    def test_a_session_cannot_be_opened_for_someone_else(self):
        with self.assertRaises(AccessError):
            self.env['chatboo.session'].with_user(self.ann).create({
                'name': 'For Bob', 'user_id': self.bob.id,
            })

    def test_a_session_stays_with_its_owner(self):
        with self.assertRaises(AccessError):
            self.ann_session.with_user(self.ann).write({'user_id': self.bob.id})
        self.assertEqual(self.ann_session.user_id, self.ann)

    # ── The chat turn and the Canvas job of another user ──

    def test_another_users_chat_turn_cannot_be_read(self):
        turn = self.env['chatboo.async.request'].sudo().create({
            'session_id': self.bob_session.id,
            'user_id': self.bob.id,
            'prompt': 'Bob asks',
        })
        Requests = self.env['chatboo.async.request'].with_user(self.ann)
        self.assertFalse(Requests.search([('id', '=', turn.id)]))
        with self.assertRaises(AccessError):
            turn.with_user(self.ann).read(['prompt'])

    def test_a_user_does_not_write_their_own_job(self):
        job = self._job(self.ann_session, self.ann)
        with self.assertRaises(AccessError):
            job.with_user(self.ann).write({'state': 'done'})

    def test_another_users_job_cannot_be_read(self):
        job = self._job(self.bob_session, self.bob)
        with self.assertRaises(AccessError):
            job.with_user(self.ann).read(['state'])

    # ── Life of a job ──

    def test_the_owner_cancels_a_pending_job(self):
        job = self._job(self.ann_session, self.ann)
        self.assertTrue(job.with_user(self.ann).request_cancel())
        _forget(job)
        self.assertTrue(job.cancel_requested)
        self.assertEqual(job.state, 'done')

    def test_a_finished_job_is_not_cancelled(self):
        job = self._job(self.ann_session, self.ann, state='error')
        self.assertFalse(job.with_user(self.ann).request_cancel())
        _forget(job)
        self.assertFalse(job.cancel_requested)

    def test_a_job_without_heartbeat_is_reclaimed_and_a_live_one_is_not(self):
        dead = self._job(self.ann_session, self.ann, state='running')
        live = self._job(self.ann_session, self.ann, state='running')
        _flush(self.env)
        self.env.cr.execute(
            "UPDATE chatboo_canvas_job SET write_date = %s WHERE id = %s",
            (fields.Datetime.now() - timedelta(hours=1), dead.id),
        )
        _forget(dead | live)
        self.env['chatboo.canvas.job']._reclaim_stuck()
        _forget(dead | live)
        self.assertEqual(dead.state, 'error')
        self.assertTrue(dead.finished_at)
        self.assertEqual(live.state, 'running')

    def test_old_finished_jobs_are_purged_and_recent_ones_kept(self):
        now = fields.Datetime.now()
        old = self._job(
            self.ann_session, self.ann, state='done',
            finished_at=now - timedelta(days=10),
        )
        recent = self._job(self.ann_session, self.ann, state='done', finished_at=now)
        self.env['chatboo.canvas.job']._gc_old()
        self.assertFalse(old.exists())
        self.assertTrue(recent.exists())


@tagged('post_install', '-at_install', 'pns_ai_chatboo')
class TestChatbooHttpPerimeter(HttpCase):

    def setUp(self):
        super().setUp()
        self.password = 'pns-%s' % uuid.uuid4().hex[:16]
        self.ann = _internal(self.env, 'chatboo_http_ann', self.password)
        self.bob = _internal(self.env, 'chatboo_http_bob', self.password)
        for user in (self.ann, self.bob):
            _chatboo_access(user)
        Session = self.env['chatboo.session'].sudo()
        self.ann_session = Session.create({
            'name': 'Ann chat', 'user_id': self.ann.id, 'canvas_design': _DESIGN,
        })
        self.bob_session = Session.create({
            'name': 'Bob chat', 'user_id': self.bob.id, 'canvas_design': _DESIGN,
        })
        _flush(self.env)

    def _csrf_token(self):
        """The token Odoo hands the logged-in user, read from their own Canvas page."""
        response = self.url_open('/chatboo/canvas/%s' % self.ann_session.id)
        self.assertEqual(http_status_code(response), 200)
        found = re.search(r'data-csrf="([^"]+)"', response.text)
        self.assertTrue(found, 'the Canvas page carries no CSRF token')
        return found.group(1)

    def _post_turn(self, query=''):
        return self.url_open(
            '/chatboo/stream' + query,
            data=json.dumps({'session_id': self.ann_session.id, 'message': ''}),
            headers={'Content-Type': 'text/plain'},
        )

    def test_a_turn_without_csrf_token_is_refused(self):
        self.authenticate(self.ann.login, self.password)
        response = self._post_turn()
        self.assertEqual(http_status_code(response), 400)
        self.assertNotIn('application/json', response.headers.get('Content-Type', ''))

    def test_the_same_turn_with_its_token_reaches_chatboo(self):
        self.authenticate(self.ann.login, self.password)
        token = self._csrf_token()
        response = self._post_turn('?csrf_token=%s' % token)
        self.assertIn('application/json', response.headers.get('Content-Type', ''))
        self.assertIn('error', response.json())

    def _rpc(self, path, **params):
        response = self.url_open(
            path,
            data=json.dumps({'jsonrpc': '2.0', 'method': 'call', 'params': params}),
            headers={'Content-Type': 'application/json'},
        )
        self.assertEqual(http_status_code(response), 200)
        return response.json().get('result')

    def test_another_users_session_is_not_found_rather_than_failing(self):
        self.authenticate(self.ann.login, self.password)
        mine = self._rpc('/chatboo/sessions/load', session_id=self.ann_session.id)
        theirs = self._rpc('/chatboo/sessions/load', session_id=self.bob_session.id)
        self.assertEqual(mine['status'], 'ok')
        self.assertEqual(theirs, {'status': 'error', 'message': 'Session not found'})

    def test_another_users_canvas_is_not_found(self):
        self.authenticate(self.ann.login, self.password)
        mine = self.url_open('/chatboo/canvas/%s' % self.ann_session.id)
        theirs = self.url_open('/chatboo/canvas/%s' % self.bob_session.id)
        self.assertEqual(http_status_code(mine), 200)
        self.assertEqual(http_status_code(theirs), 404)
