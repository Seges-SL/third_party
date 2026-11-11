# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 Patanegra Soft <https://patanegra.com>
"""Long work in a thread, with a progress dialog that follows it.

The caller checks who may run the work, then::

    return self.env['pns.progress.job']._launch(
        _('Title'), 'my.model', '_my_work', key='my.model.scan',
        done_action='my_module.action_xmlid', done_label=_('Open it'))

``_my_work(job)`` runs as the launching user in its own cursor, calls
``job.step(percent, text)`` as it goes and returns the summary::

    {'message': str,
     'tiles': [{'label': str, 'value': number, 'tone': 'success'|'info'|...}],
     'table': {'columns': [str, ...], 'rows': [[...], ...]}}

Texts are already translated by the caller. Nothing else is shown.
"""
import json
import logging
import threading
from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from ..utils.thread_env import env_manage, is_test_mode, registry_of

_logger = logging.getLogger(__name__)

STALE_AFTER = timedelta(minutes=30)
KEEP_FOR = timedelta(days=7)
TONES = ('success', 'info', 'warning', 'danger', 'secondary')


class ProgressReporter(object):
    """Writes progress from the worker thread on a cursor of its own."""

    def __init__(self, registry, job_id):
        self._registry = registry
        self.job_id = job_id

    def step(self, progress, text=None):
        progress = max(0, min(100, int(progress or 0)))
        with self._registry.cursor() as cr:
            cr.execute(
                "UPDATE pns_progress_job SET progress = %s, step = %s, "
                "write_date = (now() at time zone 'UTC') WHERE id = %s",
                (progress, text or None, self.job_id))


class InlineReporter(object):
    """Same calls when the work runs in the request (tests)."""

    def __init__(self, job):
        self._job = job
        self.job_id = job.id

    def step(self, progress, text=None):
        self._job.write({'progress': max(0, min(100, int(progress or 0))),
                         'step': text or False})


class PnsProgressJob(models.Model):
    _name = 'pns.progress.job'
    _description = 'Background job with progress'
    _order = 'id desc'

    name = fields.Char(string='Title', required=True)
    key = fields.Char(string='Key', index=True)
    user_id = fields.Many2one('res.users', string='User', required=True,
                              index=True, ondelete='cascade')
    state = fields.Selection([
        ('queued', 'Queued'),
        ('running', 'Running'),
        ('done', 'Done'),
        ('failed', 'Failed'),
    ], string='State', required=True, default='queued')
    progress = fields.Integer(string='Progress')
    step = fields.Char(string='Step')
    summary = fields.Text(string='Summary')
    error = fields.Text(string='Error')
    started_at = fields.Datetime(string='Started')
    finished_at = fields.Datetime(string='Finished')

    # ------------------------------------------------------------------ launch

    @api.model
    def _launch(self, title, model, method, args=None, key=None,
                done_action=None, done_label=None):
        """Start ``env[model].method(job, *args)``; return the dialog action."""
        Job = self.sudo()
        Job._purge_old()
        if key:
            running = Job.search([('key', '=', key),
                                  ('state', 'in', ('queued', 'running'))], limit=1)
            if running and not running._is_stale():
                if running.user_id.id != self.env.uid:
                    raise UserError(_('This work is already running for %s. '
                                      'Try again when it finishes.') % running.user_id.name)
                return running._dialog_action(done_action, done_label)
        job = Job.create({'name': title, 'key': key or False,
                          'user_id': self.env.uid})
        args = list(args or [])
        if is_test_mode(self.env):
            job._run_inline(model, method, args)
        else:
            self.env.cr.commit()
            job._spawn(model, method, args)
        return job._dialog_action(done_action, done_label)

    def _dialog_action(self, done_action=None, done_label=None):
        self.ensure_one()
        return {
            'type': 'ir.actions.client',
            'tag': 'pns_progress_dialog',
            'name': self.name,
            'target': 'new',
            'params': {
                'job_id': self.id,
                'done_action': done_action or False,
                'done_label': done_label or False,
            },
        }

    def _run_inline(self, model, method, args):
        self.write({'state': 'running', 'started_at': fields.Datetime.now()})
        target = self.env[model].with_user(self.user_id)
        try:
            summary = getattr(target, method)(InlineReporter(self), *args)
        except Exception as exc:
            self._finish('failed', error=self._error_text(exc))
            raise
        self._finish('done', summary=summary)

    def _spawn(self, model, method, args):
        dbname = self.env.cr.dbname
        uid = self.user_id.id
        context = dict(self.env.context)
        job_id = self.id

        def runner():
            with env_manage():
                registry = registry_of(dbname)
                with registry.cursor() as cr:
                    env = api.Environment(cr, uid, context)
                    env['pns.progress.job'].sudo().browse(job_id).write({
                        'state': 'running', 'started_at': fields.Datetime.now()})
                summary, error = None, None
                try:
                    with registry.cursor() as cr:
                        env = api.Environment(cr, uid, context)
                        summary = getattr(env[model], method)(
                            ProgressReporter(registry, job_id), *args)
                        cr.commit()
                except Exception as exc:
                    _logger.exception('pns.progress.job %s failed (%s.%s)',
                                      job_id, model, method)
                    error = exc
                with registry.cursor() as cr:
                    env = api.Environment(cr, uid, context)
                    job = env['pns.progress.job'].sudo().browse(job_id)
                    if error is None:
                        job._finish('done', summary=summary)
                    else:
                        job._finish('failed', error=job._error_text(error))

        thread = threading.Thread(target=runner, name='pns_progress_job_%s' % job_id,
                                  daemon=True)
        thread.start()

    def _finish(self, state, summary=None, error=None):
        self.write({
            'state': state,
            'progress': 100 if state == 'done' else self.progress,
            'summary': json.dumps(summary, default=str) if summary else False,
            'error': error or False,
            'finished_at': fields.Datetime.now(),
        })

    def _error_text(self, exc):
        if isinstance(exc, UserError):
            return exc.args[0] if exc.args else str(exc)
        return _('The work stopped with an error. The server log has the details.')

    def _is_stale(self):
        self.ensure_one()
        return (self.state in ('queued', 'running')
                and self.write_date
                and fields.Datetime.now() - self.write_date > STALE_AFTER)

    def _purge_old(self):
        limit = fields.Datetime.now() - KEEP_FOR
        self.sudo().search([('state', 'in', ('done', 'failed')),
                            ('finished_at', '<', limit)]).unlink()

    # -------------------------------------------------------------------- read

    def read_progress(self):
        """What the dialog paints. The record rule keeps it to the caller's jobs."""
        self.ensure_one()
        state, error = self.state, self.error or False
        if self._is_stale():
            state = 'failed'
            error = _('The work stopped answering. It may have been cut by a restart.')
        return {
            'state': state,
            'progress': self.progress,
            'step': self.step or '',
            'error': error,
            'summary': self._summary_payload() if state == 'done' else False,
            'duration': self._duration_label(),
        }

    def _summary_payload(self):
        try:
            raw = json.loads(self.summary or '{}')
        except ValueError:
            raw = {}
        if not isinstance(raw, dict):
            raw = {}
        tiles = []
        for tile in raw.get('tiles') or []:
            if not isinstance(tile, dict) or not tile.get('label'):
                continue
            tone = tile.get('tone') if tile.get('tone') in TONES else 'secondary'
            tiles.append({'label': str(tile['label']), 'value': tile.get('value', ''),
                          'tone': tone})
        table = raw.get('table') if isinstance(raw.get('table'), dict) else {}
        rows = [list(row) for row in table.get('rows') or [] if isinstance(row, (list, tuple))]
        return {
            'message': str(raw.get('message') or ''),
            'tiles': tiles,
            'columns': [str(c) for c in table.get('columns') or []] if rows else [],
            'rows': rows,
        }

    def _duration_label(self):
        if not self.started_at:
            return ''
        end = self.finished_at or fields.Datetime.now()
        seconds = max(0, int((end - self.started_at).total_seconds()))
        if seconds < 60:
            return _('%s s') % seconds
        return _('%(minutes)s min %(seconds)s s') % {
            'minutes': seconds // 60, 'seconds': seconds % 60}
