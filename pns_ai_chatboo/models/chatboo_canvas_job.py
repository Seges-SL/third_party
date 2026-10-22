# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""The Canvas button: one answer's tables laid out as a page, in the background.

A Chatboo job like a chat turn: same thread, heartbeat, cancel and reclaim. The
page itself is stored on the session by ``open_page``; the job keeps where it
came from (the answer) and what it left (the URL or the reason it left none).
"""

import json
import logging
from datetime import timedelta

from odoo import models, fields, api, _

from .chatboo_job import HEARTBEAT_STALE_SECONDS, _env_manage, _get_registry, _is_test_mode

_logger = logging.getLogger(__name__)


class ChatbooCanvasJob(models.Model):
    """One page being laid out from the tables of one answer."""
    _name = 'chatboo.canvas.job'
    _inherit = 'chatboo.job.mixin'
    _description = 'Chatboo Canvas job'
    _order = 'create_date desc'
    _rec_name = 'id'

    msg_index = fields.Integer(string='Answer', index=True)
    tables = fields.Text(string='Tables (JSON)')
    instruction = fields.Text(string='Instruction')
    title = fields.Char(string='Title')
    url = fields.Char(string='Page URL')

    @api.model
    def _start(self, session, tables, question='', title='', msg_index=0):
        """Start a page for one answer of ``session``, or give the one already on its way."""
        from .chatboo_canvas import tables_from_client

        live = self._live_for(session)
        if live:
            return live[0]._client_state()
        blocks = tables_from_client(tables)
        if not blocks:
            return {
                'status': 'error',
                'message': _('This answer has no table to lay out.'),
            }
        question = str(question or '').strip()
        instruction = 'Lay out the tables of one chat answer as a page.'
        if question:
            instruction += '\nThe user had asked: ' + question
        try:
            msg_index = int(msg_index or 0)
        except (TypeError, ValueError):
            msg_index = 0
        job = self.sudo().create({
            'session_id': session.id,
            'user_id': self.env.uid,
            'msg_index': msg_index,
            'tables': json.dumps(blocks, ensure_ascii=False, default=str),
            'instruction': instruction,
            'title': str(title or '').strip()[:200],
        })
        job = job.with_env(self.env)
        if not _is_test_mode(self.env):
            self.env.cr.commit()
        job._spawn()
        return job._client_state()

    @api.model
    def _live_for(self, session):
        """Jobs of ``session`` still laying a page out and not cancelled."""
        alive = fields.Datetime.now() - timedelta(seconds=HEARTBEAT_STALE_SECONDS)
        return self.search([
            ('session_id', '=', session.id),
            ('user_id', '=', self.env.uid),
            ('state', 'in', ('pending', 'running')),
            ('cancel_requested', '=', False),
            ('write_date', '>=', alive),
        ])

    def _client_state(self):
        self.ensure_one()
        if self in self._live_for(self.session_id):
            state = 'building'
        elif self.state == 'done' and self.url:
            state = 'done'
        else:
            state = 'failed'
        return {
            'status': 'ok',
            'job_id': self.id,
            'msg_index': self.msg_index,
            'state': state,
            'url': (self.url or '') if state == 'done' else '',
            'error': (self.error or '') if state == 'failed' else '',
        }

    def _process(self):
        self.ensure_one()
        self._close({'state': 'running', 'started_at': fields.Datetime.now()})
        beat = self._start_heartbeat()
        url = ''
        try:
            from .chatboo_canvas import open_page

            try:
                blocks = json.loads(self.tables or '[]')
            except ValueError:
                blocks = []
            sessions = self.env['chatboo.session'].with_context(
                ai_session_ref=self.session_id.id,
                chatboo_canvas_job=self.id,
            )
            url = open_page(
                sessions, blocks, self.instruction or '', new=True,
                title=self.title or '',
            )
        except Exception:
            _logger.exception('Chatboo canvas job %s: build failed', self.id)
        finally:
            self._stop_heartbeat(beat)
        vals = {'state': 'done', 'finished_at': fields.Datetime.now()}
        if self._is_cancel_requested():
            _logger.info('Chatboo canvas job %s: cancelled, page dropped', self.id)
        elif url:
            vals['url'] = url
        else:
            vals.update({
                'state': 'error',
                'error': _('No page was built. The reason is in the AI History.'),
            })
        self._close(vals)

    def _close(self, vals):
        """The system writes the job's state, on a fresh cursor: the heartbeat
        touches the same row and the worker's snapshot would collide with it."""
        if _is_test_mode(self.env):
            self.sudo().write(vals)
            return
        with _env_manage():
            with _get_registry(self.env.cr.dbname).cursor() as cr:
                env = api.Environment(cr, self.env.uid, dict(self.env.context))
                env[self._name].browse(self.id).sudo().write(vals)
        names = list(vals)
        try:
            self.invalidate_recordset(names)
        except AttributeError:
            self.invalidate_cache(names, self.ids)

    def _on_crash(self, msg):
        self.sudo().write({
            'state': 'error',
            'error': _('No page was built. The reason is in the AI History.'),
            'finished_at': fields.Datetime.now(),
        })

    def _cancel_pending(self):
        self.sudo().write({'state': 'done', 'finished_at': fields.Datetime.now()})

    def _reclaim_one(self, timeout_ms):
        self.sudo().write({
            'state': 'error',
            'error': _('No page was built: the server restarted while it was being laid out.'),
            'finished_at': fields.Datetime.now(),
        })
