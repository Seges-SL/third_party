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

# Intervalo del LATIDO (heartbeat) independiente (segundos). Un hilo aparte
# refresca write_date a este ritmo mientras el job corre, PASE lo que pase con el
# motor: así un modelo lento que tarda minutos en emitir tokens no se confunde
# nunca con un worker muerto. Debe ser < HEARTBEAT_STALE_SECONDS con holgura.
HEARTBEAT_INTERVAL = 10.0
# Antigüedad para considerar un job "colgado" (min) → lo reclama el cron. Gracias
# al latido, un valor bajo es seguro: solo los jobs realmente muertos (sin latido
# reciente) superan el umbral.
STUCK_MINUTES = 3
# Umbral de latido para el reclaim inmediato al abrir Chatboo (segundos). Un job
# vivo late cada HEARTBEAT_INTERVAL; si lleva más de esto sin latir, está muerto.
HEARTBEAT_STALE_SECONDS = 60
# Retención de jobs terminados (horas) antes de purgarlos.
GC_HOURS = 72


def _env_manage():
    """Context manager de entornos thread-local.

    Odoo 14 (owl1) exige ``Environment.manage()`` para crear un Environment con
    cursor propio fuera del request. En Odoo 17+ (owl2) desapareció; devolvemos
    un nullcontext para que el mismo código sirva en ambos stacks.
    """
    manage = getattr(api.Environment, 'manage', None)
    if manage is not None:
        return manage()

    import contextlib
    return contextlib.nullcontext()


def _get_registry(dbname):
    """Devuelve el Registry de la BD, compatible con Odoo 14 y 17+/19.

    En Odoo 14 existe el helper ``odoo.registry(db)``. En Odoo 17+/19 se eliminó
    (``module 'odoo' has no attribute 'registry'``) y hay que usar la clase
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
    """True si el job ya quedó en done/error (cursor fresco)."""
    try:
        with _get_registry(dbname).cursor() as cr:
            cr.execute("SELECT state FROM %s WHERE id=%%s" % table, (rid,))
            row = cr.fetchone()
            return bool(row and row[0] in ('done', 'error'))
    except Exception:
        return False


def _is_test_mode(env):
    """True si estamos en modo test, compatible con Odoo 14 y 17+/19.

    En Odoo 14 el registry expone ``in_test_mode()``. En Odoo 19 ese método ya no
    existe (``'Registry' object has no attribute 'in_test_mode'``), así que nos
    apoyamos en el flag ``testing`` del hilo y solo llamamos a ``in_test_mode`` si
    está disponible.
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
    # El cliente pidió cancelar: el worker lo comprueba y cierra.
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

    # ──────────────────────────── Hilo ────────────────────────────

    def _process(self):
        """The work of the job. Runs in the thread, on its own cursor."""
        raise NotImplementedError

    def _spawn(self):
        """Lanza el procesamiento en un hilo con cursor propio.

        En modo test se ejecuta en línea (los hilos con cursor propio y el
        TestCursor no se llevan bien).
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
            # Patrón estándar de hilo de fondo Odoo: fijar dbname en el hilo (si
            # no, sale "desnudo" -> el log muestra '?' y algunas rutas del ORM/log
            # que lo esperan pueden fallar).
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
                # Commit del cursor del worker al salir del ``with``: un
                # SerializationFailure (PG 40001) aquí NO es un fallo del
                # trabajo — el job ya persistió en un cursor fresco. Marcarlo
                # como error pisaría un resultado bueno.
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
        """Marca un job como error tras un crash de bootstrap del hilo.

        Intenta primero la vía ORM (``_on_crash`` del modelo); si el propio
        Environment es lo que falla, cae a SQL crudo para al menos dejar el
        estado en 'error' con el mensaje.
        """
        table = self._table
        if _job_already_finished(dbname, table, rid):
            _logger.warning(
                "Chatboo job: skip crash mark, %s %s already finished", self._name, rid,
            )
            return
        msg = '%s: %s' % (exc.__class__.__name__, exc) or 'worker crashed'
        try:
            # _env_manage() es imprescindible en Odoo 14 para crear un Environment
            # fuera del request (si no: 'tuple' object has no attribute 'cache').
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
        """Lanza el hilo de latido y devuelve ``(Event, Thread)`` para pararlo.

        Refresca ``write_date`` cada ``HEARTBEAT_INTERVAL`` en un cursor propio,
        sin tocar el contenido. En modo test no se lanza (el TestCursor y los
        hilos con cursor propio no se llevan bien): devuelve ``None``.
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
        """Detiene el latido y ESPERA a que termine, para que no escriba la fila
        mientras el job la persiste (evita colisión de update concurrente)."""
        if not beat:
            return
        stop_beat, thread = beat
        try:
            stop_beat.set()
            thread.join(timeout=HEARTBEAT_INTERVAL + 2)
        except Exception:
            pass

    # ──────────────────────────── Cancelar ────────────────────────────

    def request_cancel(self):
        """Marca el job para cancelación cooperativa.

        Si aún está ``pending``, se cierra al momento (``_cancel_pending``). Si
        ``running``, el worker corta en cuanto lo ve (``_is_cancel_requested``).
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
        """Lee ``cancel_requested`` en cursor fresco (visible desde el worker)."""
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

    # ──────────────────────────── Mantenimiento (cron) ────────────────────────────

    @api.model
    def _reclaim_stuck(self, minutes=None):
        """Recupera los jobs colgados (worker muerto tras un reinicio).

        Gracias al latido (``write_date`` se refresca mientras corre), solo caen
        aquí los jobs REALMENTE muertos. Qué se guarda de cada uno lo decide el
        modelo (``_reclaim_one``).

        ``minutes`` permite un umbral más corto para el reclaim inmediato al abrir
        Chatboo; por defecto usa ``STUCK_MINUTES`` (cron).

        NO BLOQUEANTE: ``FOR UPDATE SKIP LOCKED`` + savepoint por job. Un job
        zombie NUNCA puede colgar la apertura de Chatboo ni el cron.
        """
        mins = STUCK_MINUTES if minutes is None else minutes
        cutoff = fields.Datetime.now() - timedelta(minutes=mins)
        timeout_ms = int(self.env.context.get('chatboo_reclaim_timeout_ms', 8000) or 8000)
        cutoff_s = fields.Datetime.to_string(cutoff)
        table = self._table
        # Candidatos sin lock; cada uno se reclama con SKIP LOCKED (no esperar).
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
                # Último recurso: SQL crudo en savepoint limpio para no dejar
                # el zombie en running ni abortar la TX del caller (poll/cron).
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
        """Purga jobs terminados antiguos."""
        cutoff = fields.Datetime.now() - timedelta(hours=GC_HOURS)
        old = self.search([
            ('state', 'in', ('done', 'error')),
            ('finished_at', '<', cutoff),
        ])
        if old:
            old.unlink()
