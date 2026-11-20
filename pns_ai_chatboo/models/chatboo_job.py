# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""Life of a Chatboo background job, whatever the job does.

A job is a row born for the asking user in one of their own sessions. It runs in
a thread with its own cursor, beats while it runs, can be asked to stop, is
reclaimed when its worker dies and purged when it is old.

What the job does and what it leaves behind belong to the model that inherits:
``_process`` (the work), ``_on_crash``, ``_cancel_pending`` and ``_reclaim_one``.
"""

import logging
import threading
from datetime import timedelta

import odoo
from odoo import models, fields, api, _
from odoo.exceptions import AccessError

_logger = logging.getLogger(__name__)

# Interval of the separate HEARTBEAT (seconds). Another thread refreshes
# write_date at this rate while the job runs, WHATEVER the engine does: so a
# slow model that takes minutes to emit tokens is never mistaken for a dead
# worker. Must be well below HEARTBEAT_STALE_SECONDS.
HEARTBEAT_INTERVAL = 10.0
# Age at which a job is "stuck" (min) → the cron reclaims it. Thanks to the
# heartbeat, a low value is safe: only truly dead jobs (no recent beat) pass
# the threshold.
STUCK_MINUTES = 3
# Heartbeat threshold for the immediate reclaim when Chatboo opens (seconds). A
# live job beats every HEARTBEAT_INTERVAL; past this without a beat, it is dead.
HEARTBEAT_STALE_SECONDS = 60
# How long finished jobs are kept (hours) before purging them.
GC_HOURS = 72


def _env_manage():
    """Context manager for thread-local environments.

    Odoo 14 (owl1) needs ``Environment.manage()`` to build an Environment with
    its own cursor outside the request. Odoo 17+ (owl2) removed it; we return
    a nullcontext so the same code works on both stacks.
    """
    manage = getattr(api.Environment, 'manage', None)
    if manage is not None:
        return manage()

    import contextlib
    return contextlib.nullcontext()


def _get_registry(dbname):
    """Return the database Registry, on Odoo 14 and 17+/19.

    Odoo 14 has the helper ``odoo.registry(db)``. Odoo 17+/19 removed it
    (``module 'odoo' has no attribute 'registry'``), so we use the class
    ``odoo.modules.registry.Registry(db)``.
    """
    reg = getattr(odoo, 'registry', None)
    if callable(reg):
        return reg(dbname)
    from odoo.modules.registry import Registry
    return Registry(dbname)


def _is_pg_serialization_failure(exc):
    """True for Postgres SQLSTATE 40001 (REPEATABLE READ concurrent update).

    Odoo 14/psycopg2 and Odoo 19/psycopg3 expose this under different class
    names; matching pgcode/sqlstate plus the well-known message covers both.
    """
    pgcode = getattr(exc, 'pgcode', None) or getattr(exc, 'sqlstate', None)
    if pgcode == '40001':
        return True
    if type(exc).__name__ == 'SerializationFailure':
        return True
    msg = str(exc or '').lower()
    return 'could not serialize access' in msg


def _job_already_finished(dbname, table, rid):
    """True if the job is already done/error (fresh cursor)."""
    try:
        with _get_registry(dbname).cursor() as cr:
            cr.execute("SELECT state FROM %s WHERE id=%%s" % table, (rid,))
            row = cr.fetchone()
            return bool(row and row[0] in ('done', 'error'))
    except Exception:
        return False


def _is_test_mode(env):
    """True in test mode, on Odoo 14 and 17+/19.

    On Odoo 14 the registry has ``in_test_mode()``. On Odoo 19 that method is
    gone (``'Registry' object has no attribute 'in_test_mode'``), so we rely on
    the thread's ``testing`` flag and only call ``in_test_mode`` if it exists.
    """
    if getattr(threading.current_thread(), 'testing', False):
        return True
    fn = getattr(env.registry, 'in_test_mode', None)
    if callable(fn):
        try:
            return bool(fn())
        except Exception:
            return False
    return False


class ChatbooJobMixin(models.AbstractModel):
    """A job of one user in one of their sessions, run in the background."""
    _name = 'chatboo.job.mixin'
    _description = 'Chatboo background job'

    session_id = fields.Many2one(
        'chatboo.session', string='Session', required=True,
        ondelete='cascade', index=True,
    )
    user_id = fields.Many2one(
        'res.users', string='User', required=True, index=True,
        default=lambda self: self.env.user,
    )
    state = fields.Selection(
        [
            ('pending', 'Pending'),
            ('running', 'Running'),
            ('done', 'Done'),
            ('error', 'Error'),
        ],
        string='State', default='pending', required=True, index=True,
    )
    error = fields.Text(string='Error')
    # The client asked to cancel: the worker checks it and closes.
    cancel_requested = fields.Boolean(
        string='Cancel requested', default=False, index=True,
    )
    started_at = fields.Datetime(string='Started at')
    finished_at = fields.Datetime(string='Finished at')

    # A job is born for the asking user in one of their own sessions, and
    # never moves: the worker saves what it makes into ``session_id``.
    _OWNER_FIELDS = frozenset({'session_id', 'user_id'})

    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.su:
            Session = self.env['chatboo.session']
            for vals in vals_list:
                vals['user_id'] = self.env.uid
                sid = vals.get('session_id')
                if not sid or not Session.search_count([
                    ('id', '=', sid), ('user_id', '=', self.env.uid),
                ]):
                    raise AccessError(_(
                        'A Chatboo job can only run in your own session.'
                    ))
        return super().create(vals_list)

    def write(self, vals):
        if not self.env.su and self._OWNER_FIELDS.intersection(vals):
            raise AccessError(_(
                'A Chatboo job can only run in your own session.'
            ))
        return super().write(vals)

    # ──────────────────────────── Thread ────────────────────────────

    def _process(self):
        """The work of the job. Runs in the thread, on its own cursor."""
        raise NotImplementedError

    def _spawn(self):
        """Run the work in a thread with its own cursor.

        In test mode it runs inline (threads with their own cursor and the
        TestCursor do not get along).
        """
        self.ensure_one()
        rid = self.id
        model = self._name
        table = self._table
        dbname = self.env.cr.dbname
        uid = self.env.uid
        context = dict(self.env.context)

        if _is_test_mode(self.env):
            self._process()
            return

        def _runner():
            # Standard Odoo background-thread pattern: set dbname on the thread
            # (otherwise it is "bare" -> the log shows '?' and some ORM/log paths
            # that expect it may fail).
            try:
                threading.current_thread().dbname = dbname
            except Exception:
                pass
            _logger.info("Chatboo job thread started (%s %s, db %s)", model, rid, dbname)
            try:
                with _env_manage():
                    db_registry = _get_registry(dbname)
                    with db_registry.cursor() as cr:
                        env = api.Environment(cr, uid, context)
                        env[model].browse(rid)._process()
            except Exception as exc:
                # The worker cursor commits when leaving the ``with``: a
                # SerializationFailure (PG 40001) here is NOT a failure of the
                # work — the job already saved on a fresh cursor. Marking it
                # as error would overwrite a good result.
                if _is_pg_serialization_failure(exc):
                    _logger.warning(
                        "Chatboo job cursor raced after finalize (%s %s): %s",
                        model, rid, exc,
                    )
                    if _job_already_finished(dbname, table, rid):
                        return
                _logger.exception("Chatboo job crashed (%s %s)", model, rid)
                self._record_crash(dbname, uid, context, rid, exc)

        thread = threading.Thread(
            target=_runner, name='%s-%s' % (model.replace('.', '-'), rid), daemon=True,
        )
        thread.start()

    @api.model
    def _record_crash(self, dbname, uid, context, rid, exc):
        """Mark a job as error after the thread crashed at startup.

        Tries the ORM first (the model's ``_on_crash``); if the Environment
        itself is what fails, falls back to raw SQL to at least leave the
        state at 'error' with the message.
        """
        table = self._table
        if _job_already_finished(dbname, table, rid):
            _logger.warning(
                "Chatboo job: skip crash mark, %s %s already finished", self._name, rid,
            )
            return
        msg = '%s: %s' % (exc.__class__.__name__, exc) or 'worker crashed'
        try:
            # _env_manage() is required on Odoo 14 to build an Environment
            # outside the request (otherwise: 'tuple' object has no attribute 'cache').
            with _env_manage():
                with _get_registry(dbname).cursor() as cr:
                    env = api.Environment(cr, uid, context)
                    env[self._name].browse(rid)._on_crash(msg)
                    return
        except Exception:
            _logger.exception("Chatboo job: crash mark failed (%s %s)", self._name, rid)
        try:
            with _get_registry(dbname).cursor() as cr:
                cr.execute(
                    "UPDATE %s "
                    "SET state='error', error=%%s, "
                    "finished_at=(now() at time zone 'UTC') WHERE id=%%s" % table,
                    (msg, rid),
                )
        except Exception:
            _logger.exception("Chatboo job: raw crash mark failed (%s %s)", self._name, rid)

    def _on_crash(self, msg):
        """What a crashed job leaves behind."""
        self.sudo().write({
            'state': 'error',
            'error': msg,
            'finished_at': fields.Datetime.now(),
        })

    def _start_heartbeat(self):
        """Start the heartbeat thread and return ``(Event, Thread)`` to stop it.

        Refreshes ``write_date`` every ``HEARTBEAT_INTERVAL`` on its own cursor,
        without touching the content. Not started in test mode (the TestCursor
        and threads with their own cursor do not get along): returns ``None``.
        """
        if _is_test_mode(self.env):
            return None
        stop_beat = threading.Event()
        rid = self.id
        table = self._table
        dbname = self.env.cr.dbname

        def _beat():
            while not stop_beat.wait(HEARTBEAT_INTERVAL):
                try:
                    with _get_registry(dbname).cursor() as cr:
                        cr.execute(
                            "UPDATE %s "
                            "SET write_date=(now() at time zone 'UTC') WHERE id=%%s" % table,
                            (rid,),
                        )
                except Exception:
                    _logger.debug("Chatboo job heartbeat failed (%s %s)", table, rid, exc_info=True)

        thread = threading.Thread(
            target=_beat, name='chatboo-beat-%s-%s' % (table, rid), daemon=True,
        )
        thread.start()
        return (stop_beat, thread)

    @staticmethod
    def _stop_heartbeat(beat):
        """Stop the heartbeat and WAIT for it, so it does not write the row
        while the job saves it (avoids a concurrent update clash)."""
        if not beat:
            return
        stop_beat, thread = beat
        try:
            stop_beat.set()
            thread.join(timeout=HEARTBEAT_INTERVAL + 2)
        except Exception:
            pass

    # ──────────────────────────── Cancel ────────────────────────────

    def request_cancel(self):
        """Mark the job for cooperative cancel.

        If still ``pending``, it closes at once (``_cancel_pending``). If
        ``running``, the worker stops as soon as it sees it (``_is_cancel_requested``).
        """
        self.ensure_one()
        if self.user_id.id != self.env.uid:
            return False
        if self.state not in ('pending', 'running'):
            return False
        self.sudo().write({'cancel_requested': True})
        if self.state == 'pending':
            self._cancel_pending()
        return True

    def _cancel_pending(self):
        """Close a job cancelled before its worker started."""
        self.sudo().write({'state': 'done', 'finished_at': fields.Datetime.now()})

    def _is_cancel_requested(self):
        """Read ``cancel_requested`` on a fresh cursor (visible from the worker)."""
        try:
            with _get_registry(self.env.cr.dbname).cursor() as cr:
                cr.execute(
                    "SELECT cancel_requested FROM %s WHERE id=%%s" % self._table,
                    (self.id,),
                )
                row = cr.fetchone()
                return bool(row and row[0])
        except Exception:
            return False

    # ──────────────────────────── Maintenance (cron) ────────────────────────────

    @api.model
    def _reclaim_stuck(self, minutes=None):
        """Recover stuck jobs (worker dead after a restart).

        Thanks to the heartbeat (``write_date`` is refreshed while it runs), only
        TRULY dead jobs land here. What is kept of each one is up to the
        model (``_reclaim_one``).

        ``minutes`` allows a shorter threshold for the immediate reclaim when
        Chatboo opens; by default it uses ``STUCK_MINUTES`` (cron).

        NON-BLOCKING: ``FOR UPDATE SKIP LOCKED`` + one savepoint per job. A zombie
        job can NEVER hang the opening of Chatboo or the cron.
        """
        mins = STUCK_MINUTES if minutes is None else minutes
        cutoff = fields.Datetime.now() - timedelta(minutes=mins)
        timeout_ms = int(self.env.context.get('chatboo_reclaim_timeout_ms', 8000) or 8000)
        cutoff_s = fields.Datetime.to_string(cutoff)
        table = self._table
        # Candidates without lock; each one is reclaimed with SKIP LOCKED (no wait).
        try:
            candidates = self.search([
                ('state', 'in', ('pending', 'running')),
                ('write_date', '<', cutoff),
            ]).ids
        except Exception:
            _logger.exception("Chatboo job: reclaim candidate search failed (%s)", table)
            return

        for rid in candidates:
            try:
                self.env.cr.execute(
                    """
                    SELECT id FROM %s
                     WHERE id = %%s
                       AND state IN ('pending', 'running')
                       AND write_date < %%s
                       FOR UPDATE SKIP LOCKED
                    """ % table,
                    (rid, cutoff_s),
                )
                if not self.env.cr.fetchone():
                    continue
            except Exception:
                _logger.exception(
                    "Chatboo job: reclaim lock failed for %s %s", table, rid,
                )
                continue

            try:
                with self.env.cr.savepoint():
                    job = self.browse(rid)
                    if not job.exists() or job.state not in ('pending', 'running'):
                        continue
                    job._reclaim_one(timeout_ms)
            except Exception:
                _logger.exception("Chatboo job: reclaim failed for %s %s", table, rid)
                # Last resort: raw SQL in a clean savepoint, so the zombie is not
                # left running and the caller's transaction (poll/cron) is not aborted.
                try:
                    with self.env.cr.savepoint():
                        self.env.cr.execute(
                            """
                            UPDATE %s
                               SET state='done',
                                   error=%%s,
                                   finished_at=(now() at time zone 'UTC')
                             WHERE id=%%s
                               AND state IN ('pending', 'running')
                            """ % table,
                            (
                                'reclaim failed after server restart; please resend',
                                rid,
                            ),
                        )
                except Exception:
                    _logger.exception(
                        "Chatboo job: raw reclaim mark failed (%s %s)", table, rid,
                    )

    def _reclaim_one(self, timeout_ms):
        """Close one job whose worker died."""
        self.sudo().write({
            'state': 'error',
            'error': 'worker stopped (server restart)',
            'finished_at': fields.Datetime.now(),
        })

    @api.model
    def _gc_old(self):
        """Purge old finished jobs."""
        cutoff = fields.Datetime.now() - timedelta(hours=GC_HOURS)
        old = self.search([
            ('state', 'in', ('done', 'error')),
            ('finished_at', '<', cutoff),
        ])
        if old:
            old.unlink()
