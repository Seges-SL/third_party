# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""Queue of chat turns in a thread with its own cursor.

A turn writes progress and result to the database, saves the message to the
session and notifies over the bus. The response survives an F5: the source of
truth is the database. The SSE at /chatboo/stream only tails this job.
"""

import base64
import json
import logging
import time

from odoo import models, fields, api, _

from .chatboo_job import _env_manage, _get_registry, _is_test_mode
from ..utils import file_text, turn_documents
from ..utils.chatboo_product_icp import CHATBOO_AGENT_CODE
from ..utils.turn_deliverable import done_meta_has_deliverable

_logger = logging.getLogger(__name__)

# Sentinela: "no tocar el estado del skill activo de la sesión" al finalizar
# (distinto de code=None, que significa soltarlo).
_SKILL_STATE_LEAVE = object()
_DOMAIN_CODES_LEAVE = object()

# Intervalo de flush del progreso a BD (segundos). Granularidad del preview.
FLUSH_INTERVAL = 0.3
# PDF adjunto: páginas de las que se lee el texto impreso, y páginas de un
# escaneado que van como imágenes (cada una pesa en la llamada de visión).
PDF_TEXT_PAGES = 200
PDF_VISION_PAGES = 10
NO_TEXT = 'NONE'
# PostgreSQL lock_not_available: a ``lock_timeout`` ran out.
_LOCK_NOT_AVAILABLE = '55P03'


def _waited_for_lock(exc):
    while exc is not None:
        if getattr(exc, 'pgcode', None) == _LOCK_NOT_AVAILABLE:
            return True
        exc = exc.__cause__ or exc.__context__
    return False


class ChatbooAsyncRequest(models.Model):
    """Turno de Chatboo ejecutado en segundo plano (desacoplado del request)."""
    _name = 'chatboo.async.request'
    _inherit = 'chatboo.job.mixin'
    _description = 'Chatboo Async Request'
    _order = 'create_date desc'
    _rec_name = 'id'

    prompt = fields.Text(string='Prompt', required=True)
    history = fields.Text(string='History (JSON)')
    agent_code = fields.Char(string='Agent code')
    provider_id = fields.Integer(string='Provider id')
    # Descriptor ligero capturado en el cliente (modelo, id, vista) en JSON.
    screen_context = fields.Text(string='Screen context (JSON)')
    # Imágenes del turno (data URLs, JSON list). El base64 viaja al proveedor de
    # visión SOLO en este turno y se purga con el job (GC 72h); NUNCA entra en el
    # historial que va al LLM (doctrina anti-overflow). Para MOSTRAR, en cambio,
    # sí se persisten una vez como ir.attachment ligado a la sesión y el mensaje
    # de usuario guarda solo su URL (ver _persist_turn_images).
    images = fields.Text(string='Images (JSON)')
    # Nombres originales de las imágenes del turno, alineados por índice con
    # `images` (JSON list). null para las pegadas del portapapeles (sin nombre)
    # y el nombre real para las adjuntadas como fichero. Se usa para nombrar el
    # ir.attachment y mostrar el nombre bajo la miniatura (ver _persist_turn_images).
    image_names = fields.Text(string='Image names (JSON)')
    # Ficheros de texto/datos adjuntados con el clip (JSON list de
    # {name, mimetype, data(dataURL base64)}). Su TEXTO extraído se inyecta en el
    # mensaje de ESTE turno hacia el LLM (transitorio, no entra en el historial);
    # el fichero se persiste como ir.attachment y el mensaje guarda un chip
    # descargable (ver _persist_turn_files / utils.file_text).
    files = fields.Text(string='Files (JSON)')

    # Contenido visible acumulado (tokens/replace) para el preview y el guardado.
    partial = fields.Text(string='Partial content')
    # Eventos estructurados no-token (status, verification, ...) que el tail
    # reemite tal cual por SSE. JSON list.
    struct_events = fields.Text(string='Structured events (JSON)')
    # Metadatos del evento 'done' del motor (usage, context_limit, speed, ...).
    done_meta = fields.Text(string='Done meta (JSON)')
    response = fields.Text(string='Final response')
    # True cuando un cliente ya recibió el resultado en vivo (SSE) o por poll.
    seen = fields.Boolean(string='Seen by client', default=False, index=True)
    # ──────────────────────────── Cola (solo el controlador) ────────────────────────────

    @api.model
    def _enqueue(self, session_id, message, history=None, agent_code=None,
                 provider_id=None, screen_context=None, images=None, files=None,
                 image_names=None):
        """Crea el job en estado pending. No lanza el hilo (ver ``_spawn``)."""
        sc_json = False
        if screen_context:
            if isinstance(screen_context, str):
                sc_json = screen_context
            else:
                sc_json = json.dumps(screen_context, ensure_ascii=False)
        # The user ACL on this model is read-only: jobs are created here, by
        # the server, never by an RPC call from the client.
        return self.sudo().create({
            'session_id': int(session_id),
            'user_id': self.env.uid,
            'prompt': message or '',
            'history': json.dumps(history or [], ensure_ascii=False),
            'agent_code': agent_code or False,
            'provider_id': int(provider_id) if provider_id else False,
            'screen_context': sc_json,
            'images': json.dumps(images, ensure_ascii=False) if images else False,
            'image_names': json.dumps(image_names, ensure_ascii=False) if image_names else False,
            'files': json.dumps(files, ensure_ascii=False) if files else False,
            'state': 'pending',
        })

    def _on_crash(self, msg):
        self._finalize('', [], {}, error=msg)

    # ──────────────────────────── Ejecución ────────────────────────────

    def _process(self):
        """Ejecuta el motor, va volcando progreso a BD, guarda en sesión y avisa."""
        self.ensure_one()
        _logger.info(
            "Chatboo async job %s: _process start (agent=%s, provider=%s)",
            self.id, self.agent_code or '-', self.provider_id or '-',
        )
        # The user ACL on this model is read-only (PNS-55). The worker
        # still has to mark the row running; Canvas jobs already do this
        # with sudo(). The thread runs as the asking uid, so a plain
        # write() is AccessError before the engine starts.
        self.sudo().write({'state': 'running', 'started_at': fields.Datetime.now()})
        self.env.cr.commit()
        self._notify('thinking')

        acc = ''
        struct = []
        done_meta = {}
        last_flush = 0.0
        # Ancla de reutilización de consulta (Nivel 1): recogemos el código de la
        # última consulta exitosa que emita el motor (evento 'query_code') para
        # guardarlo en la sesión, y leemos el del turno anterior para que el
        # motor lo reinyecte como pista (evita que reescriba la query en cada
        # reformateo → fuente principal de variabilidad).
        last_query_code = None
        last_query_data = None
        try:
            prior_query_code = self.session_id.last_query_code or None
        except Exception:
            prior_query_code = None
        # Nivel 2: dataset del turno anterior SOLO si sigue fresco (TTL). Se
        # reinyecta como previous_result para reformatear sin re-consultar.
        try:
            prior_query_data = self.session_id.get_fresh_query_data()
        except Exception:
            prior_query_data = None
        # Skill pegajoso: código + params del skill activo de la sesión. El motor
        # los usa para juzgar (vía IA) si este turno refina el skill activo.
        try:
            prior_active_skill_code = self.session_id.active_skill_code or None
            prior_active_skill_params = self.session_id.active_skill_params or None
        except Exception:
            prior_active_skill_code = None
            prior_active_skill_params = None
        releases_domain_codes = self._slash_releases_domain_codes()
        try:
            prior_domain_codes = (
                [] if releases_domain_codes
                else self.session_id.get_last_domain_payload()
            )
        except Exception:
            prior_domain_codes = []
        try:
            held_domain_codes = self.session_id._held_domain_codes()
        except Exception:
            held_domain_codes = []
        last_domain_codes = _DOMAIN_CODES_LEAVE
        # Layout showmode lives on this session. Chatboo writes it, not the engine.
        try:
            _raw_prompt = (self.prompt or '').strip().lower()
            if _raw_prompt.startswith('/show-table'):
                self.session_id.write({'presentation_show_mode': 'show-table'})
            elif _raw_prompt.startswith('/show-chart'):
                self.session_id.write({'presentation_show_mode': 'show-chart'})
        except Exception:
            _logger.debug(
                'Chatboo async job %s: showmode sticky skipped',
                self.id, exc_info=True,
            )
        # Estado del skill activo emitido por el motor este turno (sentinela =
        # no tocado → no reescribir la sesión).
        active_skill_touched = False
        active_skill_evt = None

        try:
            history = json.loads(self.history) if self.history else []
        except Exception:
            history = []

        # Imágenes del turno (data URLs). Solo para el turno actual: van al
        # proveedor de visión como content-parts; no entran en el historial.
        try:
            images = json.loads(self.images) if self.images else []
        except Exception:
            images = []

        # Ficheros de texto/datos adjuntos con el clip: extraemos su texto y lo
        # inyectamos en el mensaje de ESTE turno (no en self.prompt ni en el
        # historial). Así el LLM ve el contenido del fichero solo cuando se
        # adjunta, igual que las imágenes (transitorio, anti-overflow).
        message_for_engine, inline_file_text, pdf_pages, turn_docs = (
            self._augment_prompt_with_files(self.prompt or '')
        )
        images = images + pdf_pages

        # Axis slashes: one-shot compose/footmode; showmode writes the session.
        formatting_override = None
        turn_compose = None
        turn_footmode = None
        try:
            from odoo.addons.pns_ai_mcp.utils.formatting_mode_policy import (
                AXIS_COMPOSE,
                AXIS_FOOTMODE,
                apply_turn_axis,
                resolve_remote_formatting_override,
            )
            axis, value, stripped = apply_turn_axis(
                self.session_id,
                message_for_engine,
            )
            if axis is not None:
                message_for_engine = stripped
                if not (message_for_engine or '').strip():
                    message_for_engine = '/' + value
                if axis == AXIS_COMPOSE:
                    turn_compose = value
                elif axis == AXIS_FOOTMODE:
                    turn_footmode = value
            formatting_override = resolve_remote_formatting_override(
                turn_mode=turn_compose,
            )
        except Exception:
            formatting_override = None
            _logger.debug(
                'Chatboo async job %s: presentation axis turn parse skipped',
                self.id, exc_info=True,
            )

        # Filas que el usuario marcó en la respuesta anterior. Viajan CON la
        # frase, no solo dentro del dataset: el motor solo lee texto, y un
        # dataset estrechado en silencio lo dejaba libre para volver a buscar
        # el nombre. Se gastan con este turno.
        try:
            marked = self.session_id.marks_sentence()
            if marked:
                message_for_engine = '%s\n\n%s' % (message_for_engine, marked)
                prior_query_data = self.session_id.narrow_query_data(
                    prior_query_data,
                )
            self.session_id.forget_marks()
        except Exception:
            _logger.debug(
                'Chatboo async job %s: marked records skipped',
                self.id, exc_info=True,
            )
        # Documentos de turnos anteriores: como las filas de una tabla, el
        # texto se queda en la sesión y el modelo lo lee con read_document.
        # Los de este turno ya van enteros en el mensaje (o en sus fotos).
        try:
            turn_docs = turn_docs + self._image_documents()
            this_turn = {doc['name'] for doc in turn_docs}
            earlier = [
                doc for doc in self.session_id.get_documents()
                if doc['name'] not in this_turn
            ]
            documents_note = turn_documents.note(earlier)
            if documents_note:
                message_for_engine = '%s\n\n%s' % (message_for_engine, documents_note)
            self.session_id.remember_documents(turn_docs)
        except Exception:
            _logger.warning(
                'Chatboo async job %s: attached documents skipped',
                self.id, exc_info=True,
            )
        # Those writes (showmode, marks, documents) sat on this cursor until
        # the end of the turn. Finalize writes the same session row on a
        # fresh cursor. The two updates collide: the turn is answered, the
        # job is done, and the session never gets the bubbles. Commit now
        # so finalize can write the messages.
        if not _is_test_mode(self.env):
            try:
                self.env.cr.commit()
            except Exception:
                _logger.exception(
                    'Chatboo async job %s: could not commit the session writes',
                    self.id,
                )
                self._release_turn_cursor()
                self._finalize('', [], {}, error=_(
                    'The conversation could not be saved before the reply. Try again.'
                ))
                return
        # Recuerdo acotado de imágenes previas (1c): reenviamos, con tope y
        # reescaladas, las últimas imágenes ya vistas en la conversación para
        # que el modelo pueda referirse a ellas (los LLM son sin estado: la
        # imagen se "recuerda" solo si se REENVÍA). No entran en el historial
        # persistido; se recomponen cada turno desde los ir.attachment.
        #
        # PERO: si ESTE turno YA trae imágenes, NO recordamos las anteriores.
        # Cuando el usuario adjunta imágenes y pregunta "¿qué hay en estas?", se
        # refiere a las del prompt ACTUAL; reenviar imágenes viejas hacía que el
        # modelo mezclara/mencionara una imagen de hace varios turnos. El recuerdo
        # queda para los turnos de SOLO texto que aludan a algo ya enviado.
        recall_images = [] if images else self._recall_prior_images()

        # LATIDO independiente: un hilo aparte refresca write_date cada
        # HEARTBEAT_INTERVAL mientras dura el turno, PASE lo que pase con el motor.
        # Así un modelo lento (que puede tardar minutos en emitir el primer token)
        # no se confunde nunca con un worker muerto y el reclaim no lo mata.
        beat = self._start_heartbeat()

        # Diagnóstico: contamos qué emite el motor. Un turno que acaba en 0s y en
        # blanco casi siempre significa que el motor no llegó a emitir tokens
        # (proveedor no resuelto en el hilo, endpoint vacío, etc.). Este desglose
        # en el log es lo que permite distinguir "sin contenido" de "crash".
        ev_counts = {}
        screen_context_block = ''
        try:
            raw_sc = json.loads(self.screen_context) if self.screen_context else None
            if raw_sc:
                from odoo.addons.pns_ai_chatboo.utils.screen_context import enrich_screen_context
                enriched = enrich_screen_context(self.env, raw_sc)
                screen_context_block = enriched.get('block') or ''
                if screen_context_block:
                    _logger.info(
                        'Chatboo async job %s: screen_context enriched (%d chars)',
                        self.id, len(screen_context_block),
                    )
                if self.session_id:
                    try:
                        self._store_last_screen(raw_sc)
                    except Exception:
                        _logger.debug(
                            'Chatboo async job %s: could not store last screen',
                            self.id, exc_info=True,
                        )
        except Exception:
            _logger.warning(
                'Chatboo async job %s: screen_context enrich failed',
                self.id, exc_info=True,
            )

        try:
            from odoo.addons.pns_ai_mcp.utils.agent_engine import AgentEngine
            engine_env = self.env(context=dict(
                self.env.context or {},
                ai_session_ref=self.session_id.id,
                presentation_show_mode=(
                    self.session_id.presentation_show_mode or False
                ),
                screen_context=(
                    self.screen_context
                    or self.session_id.last_screen_context
                    or False
                ),
                user_message=self.prompt or '',
                inline_file_text=inline_file_text,
                llm_remote_formatting_override=formatting_override,
                turn_compose=turn_compose,
                turn_footmode=turn_footmode,
            ))
            try:
                engine = AgentEngine(
                    engine_env,
                    source_channel='chatboo',
                    agent_code=self.agent_code or CHATBOO_AGENT_CODE,
                )
            except TypeError:
                engine = AgentEngine(engine_env, source_channel='chatboo')
            for evt in engine.run_stream(
                message_for_engine, history, self.session_id.id,
                agent_code=self.agent_code or CHATBOO_AGENT_CODE,
                provider_id=self.provider_id or None,
                prior_query_code=prior_query_code,
                prior_query_data=prior_query_data,
                screen_context_block=screen_context_block or None,
                prior_active_skill_code=prior_active_skill_code,
                prior_active_skill_params=prior_active_skill_params,
                prior_domain_codes=prior_domain_codes,
                images=images or None,
                recall_images=recall_images or None,
                held_domain_codes=held_domain_codes,
            ):
                if self._is_cancel_requested():
                    _logger.info("Chatboo async job %s: cancel requested, stopping", self.id)
                    break
                ev = (evt or {}).get('event', 'token')
                ev_counts[ev] = ev_counts.get(ev, 0) + 1
                if ev == 'active_skill':
                    # Meta-evento interno: estado del skill pegajoso (code+params,
                    # o code=None para soltarlo). Se persiste al finalizar.
                    active_skill_touched = True
                    active_skill_evt = evt
                    continue
                if ev == 'domain_codes':
                    ages = evt.get('ages')
                    if isinstance(ages, dict) and ages:
                        last_domain_codes = ages
                    else:
                        last_domain_codes = list(evt.get('codes') or [])
                    continue
                if ev == 'query_code':
                    # Meta-evento interno: no es contenido ni un evento de tail;
                    # solo memorizamos el último código exitoso del turno.
                    if evt.get('code'):
                        last_query_code = evt['code']
                    continue
                if ev == 'query_data':
                    # Meta-evento interno (Nivel 2): filas del último dataset
                    # exitoso, para cachearlas y reutilizarlas el próximo turno.
                    if evt.get('data') is not None:
                        last_query_data = evt['data']
                    continue
                if ev == 'token' and evt.get('content'):
                    acc += evt['content']
                elif ev == 'replace':
                    # 'replace' fija el contenido acumulado. Un replace VACÍO es
                    # una señal de reset: el motor lo emite al hacer failover tras
                    # haber emitido parcialmente, para que no se DUPLIQUE la
                    # respuesta al regenerarla el siguiente proveedor.
                    acc = evt.get('content') or ''
                elif ev == 'done':
                    done_meta = evt
                elif ev == 'error':
                    if evt.get('content'):
                        acc += evt['content']
                    struct.append(evt)
                else:
                    # status, verification, ... → reemitir tal cual en el tail
                    struct.append(evt)

                now = time.time()
                if now - last_flush >= FLUSH_INTERVAL:
                    self._flush_progress(acc, struct)
                    last_flush = now
                    if self._is_cancel_requested():
                        _logger.info(
                            "Chatboo async job %s: cancel requested after flush",
                            self.id,
                        )
                        break

            cancelled = self._is_cancel_requested()
            if cancelled:
                note = '⏹ ' + _('Generation cancelled.')
                if (acc or '').strip():
                    acc = (acc.rstrip() + '\n\n' + note)
                else:
                    acc = note
                _logger.info("Chatboo async job %s: cancelled by user", self.id)

            _logger.info(
                "Chatboo async job %s: engine done. events=%s acc_len=%s agent=%s provider_id=%s",
                self.id, ev_counts, len(acc), self.agent_code or '(auto)', self.provider_id or '(auto)',
            )
            # Parar y ESPERAR el latido ANTES de persistir: si sigue vivo, su
            # update concurrente a la fila colisiona con _finalize.
            self._stop_heartbeat(beat)
            beat = None
            domain_codes_out = last_domain_codes
            if domain_codes_out is _DOMAIN_CODES_LEAVE and releases_domain_codes:
                domain_codes_out = []
            self._release_turn_cursor()
            self._finalize(
                acc, struct, done_meta, error=None,
                query_code=last_query_code, query_data=last_query_data,
                drop_query_cache=(last_query_data is None),
                active_skill=(active_skill_evt if active_skill_touched
                              else _SKILL_STATE_LEAVE),
                domain_codes=domain_codes_out,
            )
        except Exception as exc:  # noqa: BLE001 — el motor puede fallar de mil formas
            _logger.exception(
                "Chatboo async job %s failed (events so far=%s, acc_len=%s)",
                self.id, ev_counts, len(acc),
            )
            self._stop_heartbeat(beat)
            beat = None
            self._release_turn_cursor()
            self._finalize(acc, struct, done_meta, error=str(exc) or exc.__class__.__name__)
        finally:
            # Parar el latido pase lo que pase (éxito o error).
            self._stop_heartbeat(beat)
            # Este cursor lleva un snapshot REPEATABLE READ de TODO el turno.
            # Lo durable (sesión, job, logs, recetas, usage) ya se commitó en
            # cursores propios. Un commit aquí choca con el latido/flush
            # (PG 40001) y _spawn() pintaba "MCP engine error" sobre un turno
            # bueno. En tests el TestCursor ES la transacción del caso: no
            # rollback.
            if not _is_test_mode(self.env):
                try:
                    self.env.cr.rollback()
                except Exception:
                    pass

    def _flush_progress(self, acc, struct):
        """Vuelca progreso parcial a BD en un cursor propio (visible para el tail).

        Refresca también ``write_date`` (latido): un job que sigue vivo se
        distingue así de uno muerto por un reinicio, que deja de latir.
        """
        try:
            with _get_registry(self.env.cr.dbname).cursor() as cr:
                cr.execute(
                    "UPDATE chatboo_async_request "
                    "SET partial=%s, struct_events=%s, write_date=(now() at time zone 'UTC') "
                    "WHERE id=%s",
                    (acc or '', json.dumps(struct, ensure_ascii=False), self.id),
                )
        except Exception:
            _logger.debug("Chatboo async flush failed (request %s)", self.id, exc_info=True)

    def _store_last_screen(self, raw_sc):
        """Keep the screen of this turn in the session, committed at once.

        Written on the turn cursor, the row stays locked until the turn ends,
        and ``_finalize`` waits for it on the same thread.
        """
        with _get_registry(self.env.cr.dbname).cursor() as cr:
            cr.execute("SET LOCAL lock_timeout = '3s'")
            cr.execute(
                "UPDATE chatboo_session SET last_screen_context=%s WHERE id=%s",
                (json.dumps(raw_sc, ensure_ascii=False), self.session_id.id),
            )

    def _session_busy_error(self):
        return _('The reply could not be saved in the conversation because it is busy. '
                 'Reload the chat and ask again.')

    def _release_turn_cursor(self):
        """End the turn cursor's transaction before ``_finalize`` opens its own.

        Whatever the turn still holds on it (a session row it flushed, a lock)
        would make ``_finalize``, on this same thread, wait forever. Nothing
        durable lives there: the ``finally`` of ``_process`` rolls it back too.
        """
        if _is_test_mode(self.env):
            return
        try:
            self.env.cr.rollback()
        except Exception:
            _logger.warning(
                "Chatboo async job %s: could not roll back the turn cursor",
                self.id, exc_info=True,
            )

    def _slash_releases_domain_codes(self):
        """True when this turn drops packs carried from the previous turn."""
        try:
            from odoo.addons.pns_ai_mcp.utils.slash_domain_codes import (
                parse_slash_command,
                slash_releases_domain_codes,
            )
        except Exception:
            return False
        parsed = parse_slash_command(self.prompt)
        if parsed:
            cmd = parsed[0]
            return slash_releases_domain_codes(
                cmd, skill_resolved=self._command_resolves_skill(cmd),
            )
        # Sticky skill resume is a skill invoke: keep conversation packs.
        return False

    def _resolved_inference_agent_code(self):
        """Same agent the engine uses (empty job field → chatboo feature agent)."""
        code = self.agent_code or CHATBOO_AGENT_CODE
        try:
            return self.env['ai.agent'].resolve_inference_agent_code(code)
        except Exception:
            return code

    def _command_resolves_skill(self, command):
        if not command or 'ai.skill' not in self.env:
            return False
        fold = lambda token: (token or '').strip().lower().replace('_', '-')
        folded = fold(command)
        Skill = self.env['ai.skill'].sudo()
        try:
            skills = Skill.get_for_agent(self._resolved_inference_agent_code())
        except Exception:
            skills = Skill.filter_visible_for_user(
                Skill.search([('active', '=', True)], limit=80),
            )
        for rec in skills.filtered('active'):
            invoke = rec.invoke_code() if hasattr(rec, 'invoke_code') else rec.code
            if fold(invoke) == folded or fold(rec.code) == folded:
                return True
        return False

    def _finalize(self, acc, struct, done_meta, error, query_code=None, query_data=None, active_skill=_SKILL_STATE_LEAVE, domain_codes=_DOMAIN_CODES_LEAVE, drop_query_cache=False):
        """Escribe estado final, persiste el turno en la sesión y avisa por bus."""
        # Red de seguridad anti-blanco: si el motor terminó "bien" pero sin
        # contenido, es un fallo real (proveedor no resuelto en el hilo, stream
        # vacío, etc.). Nunca dejamos un turno en blanco silencioso: lo marcamos
        # como error con un mensaje claro para que el usuario lo vea y se registre.
        # Excepción: exportación nominada (PDF/Excel/…) con tabla oculta a
        # propósito — el globo va vacío y la tarjeta/clip_data son el resultado
        # (C8N1: pintar "MCP engine error" encima de un PDF bueno).
        if not error and not (acc or '').strip():
            if done_meta_has_deliverable(done_meta):
                _logger.info(
                    "Chatboo async job %s finished with empty bubble and a "
                    "session file/clip_data; treating as success.",
                    self.id,
                )
            else:
                _logger.warning(
                    "Chatboo async job %s finished with EMPTY content and no error "
                    "(done_meta=%s). Marking as error to avoid a blank turn.",
                    self.id, done_meta,
                )
                error = _('The model returned no content. Check the AI provider '
                          '(endpoint reachable, model loaded) and the server log.')
        vals = {
            'partial': acc or '',
            'struct_events': json.dumps(struct, ensure_ascii=False),
            'done_meta': json.dumps(done_meta or {}, ensure_ascii=False),
            'response': acc or '',
            'finished_at': fields.Datetime.now(),
        }
        if error:
            vals['state'] = 'error'
            vals['error'] = error
        else:
            vals['state'] = 'done'
            vals['error'] = False

        # Persistencia en una transacción FRESCA (cursor propio), NO en el cursor
        # principal del worker: ese cursor arrastra un snapshot viejo y las
        # escrituras concurrentes a esta misma fila (flush cada 0.3s, latido)
        # hacen que su commit final falle con "could not serialize access due to
        # concurrent update" (REPEATABLE READ), abortando la transacción y dejando
        # el turno en rojo pese a haberse generado. Un cursor nuevo ve los últimos
        # commits y escribe sin colisión.
        dbname = self.env.cr.dbname
        uid = self.env.uid
        context = dict(self.env.context)
        rid = self.id
        try:
            with _env_manage():
                with _get_registry(dbname).cursor() as cr:
                    cr.execute("SET LOCAL lock_timeout = '10s'")
                    env = api.Environment(cr, uid, context)
                    job = env['chatboo.async.request'].browse(rid)
                    job.sudo().write(vals)
                    # A failed statement aborts the transaction; without the
                    # savepoint the commit below drops the job state as well
                    # and the job stays running.
                    try:
                        with cr.savepoint():
                            _chips = job._save_to_session(acc, done_meta, error, query_code=query_code, query_data=query_data, active_skill=active_skill, domain_codes=domain_codes, drop_query_cache=drop_query_cache)
                            # The phone/client only reloads from the session when
                            # this flag is on. Job done is not the same as the
                            # bubbles being in the row.
                            _merged = dict(done_meta or {})
                            _merged['session_saved'] = True
                            # Propagar los chips persistidos del turno de usuario al
                            # done_meta (ya escrito en vals): el controlador vuelca
                            # done_meta en el evento 'done' y el cliente parchea la
                            # burbuja en vivo (base64 → /web/image, ficheros clicables).
                            if _chips and (
                                _chips.get('user_images')
                                or _chips.get('user_files')
                                or _chips.get('assistant_files')
                                or _chips.get('assistant_content') is not None
                            ):
                                _merged.update(_chips)
                            _write = {'done_meta': json.dumps(_merged, ensure_ascii=False)}
                            if _chips and _chips.get('assistant_content') is not None:
                                _write['response'] = _chips['assistant_content']
                                _write['partial'] = _chips['assistant_content']
                            job.sudo().write(_write)
                    except Exception as exc:
                        _logger.exception(
                            "Chatboo async: failed to persist turn to session (job %s)", rid)
                        if _waited_for_lock(exc):
                            error = self._session_busy_error()
                            job.sudo().write({'state': 'error', 'error': error})
                    cr.commit()
                    job._notify('error' if error else 'async_done')
            return
        except Exception as exc:
            _logger.exception("Chatboo async: _finalize fresh-cursor failed (job %s)", rid)
            if _waited_for_lock(exc):
                vals['state'] = 'error'
                error = self._session_busy_error()

        # Último recurso: dejar el estado final por SQL crudo para no colgar el job
        # (el tail SSE reemite el estado/error al cliente aunque no haya sesión).
        try:
            with _get_registry(dbname).cursor() as cr:
                cr.execute("SET LOCAL lock_timeout = '10s'")
                cr.execute(
                    "UPDATE chatboo_async_request "
                    "SET state=%s, error=%s, response=%s, partial=%s, "
                    "finished_at=(now() at time zone 'UTC') WHERE id=%s",
                    (vals['state'], error or None, acc or '', acc or '', rid),
                )
        except Exception:
            _logger.exception("Chatboo async: _finalize raw fallback failed (job %s)", rid)

    # ── Persistencia de imágenes del turno (para MOSTRAR, no para el LLM) ──────
    _IMG_EXT_BY_MIME = {
        'image/png': '.png', 'image/jpeg': '.jpg', 'image/jpg': '.jpg',
        'image/gif': '.gif', 'image/webp': '.webp', 'image/bmp': '.bmp',
        'image/svg+xml': '.svg', 'image/x-icon': '.ico',
        'image/vnd.microsoft.icon': '.ico',
    }

    def _persist_turn_images(self):
        """Persiste las imágenes del turno como ir.attachment y devuelve chips.

        Doctrina revisada: el base64 NUNCA entra en el blob JSON de la sesión ni
        en el historial que viaja al LLM. Pero SÍ persistimos cada imagen una vez
        como adjunto ligado a la sesión, y el mensaje de usuario guarda un chip
        ``{url, name}`` (/web/image sin token: lo abre quien puede leer la sesión). Así el
        histórico conserva las capturas (multi-dispositivo), se abren en pestaña y
        conservan su NOMBRE cuando se adjuntaron como fichero (las pegadas del
        portapapeles no tienen nombre → name=None). Al borrar la sesión, su unlink
        arrastra los ir.attachment ligados (res_model/res_id), así que no se acumulan.
        """
        try:
            imgs = json.loads(self.images) if self.images else []
        except Exception:
            imgs = []
        try:
            names = json.loads(self.image_names) if self.image_names else []
        except Exception:
            names = []
        out = []
        if not imgs:
            return out
        Attachment = self.env['ir.attachment']
        for idx, data_url in enumerate(imgs):
            if not data_url:
                continue
            mimetype, b64 = file_text.split_data_url(data_url)
            if not b64:
                continue
            orig = names[idx] if idx < len(names) else None
            orig = (orig or '').strip() or None
            att_name = self._image_name(idx, mimetype, names)
            try:
                att = Attachment.create({
                    'name': att_name,
                    'datas': b64,
                    'mimetype': mimetype or 'image/png',
                    'res_model': 'chatboo.session',
                    'res_id': self.session_id.id,
                })
                out.append({
                    'url': '/web/image/%s' % att.id,
                    'name': orig,  # None para pegadas del portapapeles
                })
            except Exception:
                _logger.warning(
                    'Chatboo async job %s: no se pudo persistir la imagen %s del turno',
                    self.id, idx, exc_info=True,
                )
        return out

    # ── Recuerdo acotado de imágenes previas (1c) ─────────────────────────────
    # Cuántas imágenes previas de la sesión se reenvían como contexto y a qué
    # lado máximo se reescalan (para acotar tokens, como hacen ChatGPT/Claude).
    _RECALL_MAX_IMAGES = 3
    _RECALL_MAX_SIDE = 768
    # Formatos RÁSTER que los modelos de visión saben decodificar. Se EXCLUYE
    # image/svg+xml (y otros vectoriales/iconos): un SVG en el recall hacía que
    # TODOS los proveedores rechazaran el turno ("cannot identify image file" /
    # "does not contain a valid JPG, PNG, WebP, or ICO image") y disparaba el
    # failover en cascada hasta agotarlos. Además, la sesión acumula adjuntos que
    # no son fotos del usuario (iconos de skills como pin.svg, thumbnails de
    # registros…); filtrar por estos MIME evita reenviar basura vectorial.
    _RECALL_VISION_MIMETYPES = (
        'image/jpeg', 'image/jpg', 'image/png',
        'image/gif', 'image/webp', 'image/bmp',
    )

    def _recall_prior_images(self):
        """Data URLs (reescaladas) de las últimas imágenes ya vistas en la sesión.

        Reenvía, ACOTADO, las imágenes de turnos anteriores para que el modelo
        pueda referirse a ellas (los LLM son sin estado: solo "recuerdan" lo que
        se reenvía). Las del turno ACTUAL aún no están persistidas aquí, así que
        no se duplican. Devuelve orden cronológico.
        """
        if not self.session_id:
            return []
        try:
            # Pedimos más de la cuenta para poder DEDUPLICAR por checksum: la misma
            # foto adjuntada en varios turnos crea varios ir.attachment idénticos;
            # reenviarla repetida gasta contexto y confunde al modelo.
            atts = self.env['ir.attachment'].search([
                ('res_model', '=', 'chatboo.session'),
                ('res_id', '=', self.session_id.id),
                ('mimetype', 'in', list(self._RECALL_VISION_MIMETYPES)),
            ], order='id desc', limit=self._RECALL_MAX_IMAGES * 3)
        except Exception:
            return []
        urls = []
        # A photo kept as a document is read with read_document, not seen again.
        seen = turn_documents.checksums(self.session_id.get_documents())
        for att in atts:
            try:
                key = att.checksum or att.id
                if key in seen:
                    continue
                seen.add(key)
                raw = base64.b64decode(att.datas or b'')
                if not raw:
                    continue
                data_url = self._downscale_image_to_data_url(raw, att.mimetype)
                if data_url:
                    urls.append(data_url)
                if len(urls) >= self._RECALL_MAX_IMAGES:
                    break
            except Exception:
                continue
        urls.reverse()  # de más antigua a más reciente
        return urls

    @classmethod
    def _downscale_image_to_data_url(cls, raw, mimetype):
        """Reescala una imagen al lado máx. y la devuelve como data URL base64.

        La prepara pns_base (derecha, JPEG sigue JPEG, lo demás PNG). Si no
        puede (formato raro, sin Pillow), devuelve la imagen original en
        base64: el tope de NÚMERO ya acota el coste.
        """
        from odoo.addons.pns_base.utils.pdf_io import shrink_picture

        shrunk = shrink_picture(raw, cls._RECALL_MAX_SIDE)
        if shrunk:
            payload, mt = shrunk
            return 'data:%s;base64,%s' % (mt, base64.b64encode(payload).decode('ascii'))
        # Fallback SIN Pillow (o formato que no abre): reenviamos el original
        # SOLO si es un ráster que la visión acepta. NUNCA emitir SVG u otros
        # vectoriales/desconocidos: los proveedores los rechazan y tumban el
        # turno con failover en cascada.
        if (mimetype or '').lower() not in cls._RECALL_VISION_MIMETYPES:
            return ''
        try:
            return 'data:%s;base64,%s' % (mimetype, base64.b64encode(raw).decode('ascii'))
        except Exception:
            return ''

    def _pdf_reading(self, b64):
        """``(page texts, pictures)`` of a PDF attachment; None if it is not a PDF.

        Printed text comes page by page from pns_base. A scan has none: this
        agent's vision chain transcribes it once. When that fails, its pages
        go to this turn as pictures and nothing is kept for later turns.
        """
        import base64
        from odoo.addons.pns_base.utils.pdf_io import (
            is_pdf, pdf_page_texts, pdf_pictures,
        )

        try:
            raw = base64.b64decode(b64 or '')
        except Exception:
            return None
        if not is_pdf(raw):
            return None
        pages = pdf_page_texts(raw, pages=PDF_TEXT_PAGES)
        if pages:
            return pages, []
        pictures = [
            'data:image/jpeg;base64,%s' % base64.b64encode(jpeg).decode()
            for jpeg in pdf_pictures(raw, pages=PDF_VISION_PAGES)
        ]
        pages = self._transcribe_pages(pictures)
        return (pages, []) if pages else ([], pictures)

    def _transcribe_pages(self, pictures, photos=False):
        """The text of each picture, read by this agent's vision chain. [] on failure.

        A scanned page is always transcribed. A photo only when its point is
        its text; for any other the model writes ``NO_TEXT``.
        """
        if not pictures:
            return []
        if photos:
            prompt = (
                'These are %d pictures. Begin each one with a line like "%s", '
                'counting from 1. If the picture is a document whose point is '
                'its text (a ticket, an invoice, a letter, a form, a screenshot '
                'of text), transcribe that text exactly as written, in its own '
                'language. Otherwise write only %s. No comments and no summary.'
                % (len(pictures), turn_documents.PAGE_MARK % 1, NO_TEXT)
            )
        else:
            prompt = (
                'Transcribe the text of these %d scanned pages exactly as written, '
                'in their own language. Begin each page with a line like "%s", '
                'counting from 1. No comments and no summary.'
                % (len(pictures), turn_documents.PAGE_MARK % 1)
            )
        try:
            code = self.env['ai.agent'].resolve_inference_agent_code(
                self.agent_code or CHATBOO_AGENT_CODE,
            )
            response = self.env['ai.execution.engine'].sudo().chat_completion(
                code,
                [{'role': 'user', 'content': prompt}],
                images=pictures,
                provider_id=self.provider_id or None,
            )
            content = response['choices'][0]['message']['content']
        except Exception:
            _logger.warning(
                'Chatboo async job %s: scanned PDF transcription failed',
                self.id, exc_info=True,
            )
            return []
        if isinstance(content, list):
            content = ''.join(
                part.get('text', '') for part in content if isinstance(part, dict)
            )
        return turn_documents.split_pages(content, len(pictures))

    def _image_documents(self):
        """This turn's photos whose point is their text, kept as documents.

        Each carries the checksum of its file: the recall of earlier pictures
        skips it, so later turns read its text instead of seeing it again.
        """
        import hashlib
        from odoo.addons.pns_base.utils.pdf_io import usable

        try:
            imgs = json.loads(self.images) if self.images else []
            names = json.loads(self.image_names) if self.image_names else []
        except Exception:
            return []
        shots = []
        for idx, data_url in enumerate(imgs):
            mimetype, b64 = file_text.split_data_url(data_url or '')
            if not b64:
                continue
            try:
                raw = base64.b64decode(b64)
            except Exception:
                continue
            shots.append((self._image_name(idx, mimetype, names), raw, data_url))
        texts = self._transcribe_pages([shot[2] for shot in shots], photos=True)
        documents = []
        for (name, raw, _url), text in zip(shots, texts):
            text = (text or '').strip()
            if text == NO_TEXT or not usable(text):
                continue
            documents.append({
                'name': name,
                'pages': [text],
                'checksum': hashlib.sha1(raw).hexdigest(),
            })
        return documents

    def _image_name(self, idx, mimetype, names):
        """The name the turn's picture gets as an attachment."""
        orig = names[idx] if idx < len(names) else None
        orig = (orig or '').strip() or None
        ext = self._IMG_EXT_BY_MIME.get((mimetype or '').lower(), '.png')
        return orig or ('chatboo-%s-%s%s' % (self.id, idx + 1, ext))

    @staticmethod
    def _paged(pages):
        if len(pages) == 1:
            return pages[0]
        return '\n\n'.join(
            '%s\n%s' % (turn_documents.PAGE_MARK % (index + 1), text)
            for index, text in enumerate(pages)
        )

    def _augment_prompt_with_files(self, base_message):
        """Return ``(message, inline_file_text, pictures, documents)``.

        ``self.prompt`` (what the bubble shows) is left alone: the file's text
        goes whole to the model in this turn, every Excel sheet included.
        ``documents`` is that same text, page by page, for the session to keep
        and later turns to read with read_document. A scanned PDF is
        transcribed once; when that fails, its pages come back as pictures for
        this turn only. ``inline_file_text`` is True when at least one file gave
        text or pages (a failed extract is not a reading). The wrapping is in
        English: it is for the model, which answers in the user's language.
        """
        try:
            files = json.loads(self.files) if self.files else []
        except Exception:
            files = []
        if not files:
            return base_message, False, [], []
        blocks = []
        pictures = []
        documents = []
        has_text = False
        for f in files:
            name = (f or {}).get('name') or 'file'
            mimetype = (f or {}).get('mimetype') or ''
            _mt, b64 = file_text.split_data_url((f or {}).get('data') or '')
            reading = self._pdf_reading(b64)
            if reading is not None:
                pages, scans = reading
                if pages:
                    has_text = True
                    documents.append({'name': name, 'pages': pages})
                    blocks.append('[Attachment: %s]\n%s' % (name, self._paged(pages)))
                elif scans:
                    has_text = True
                    pictures.extend(scans)
                    blocks.append(
                        '[Attachment: %s] (scanned PDF: its pages are the attached pictures)' % name
                    )
                else:
                    blocks.append('[Attachment: %s] (no text could be extracted)' % name)
                continue
            text = file_text.file_text(name, mimetype or _mt, b64, ref=self.id)
            if not (text or '').strip():
                blocks.append('[Attachment: %s] (no text could be extracted)' % name)
                continue
            has_text = True
            documents.append({'name': name, 'pages': [text]})
            blocks.append('[Attachment: %s]\n%s' % (name, text))
        if not blocks:
            return base_message, False, [], []
        joined = '\n\n'.join(blocks)
        if (base_message or '').strip():
            return '%s\n\n%s' % (base_message, joined), has_text, pictures, documents
        # A message that is only files: the least the model needs.
        return (
            'Analyse the attached file(s):\n\n%s' % joined,
            has_text, pictures, documents,
        )

    def _persist_turn_files(self):
        """Persiste los ficheros del turno como ir.attachment y devuelve chips.

        Como las imágenes: el fichero se guarda una vez (ligado a la sesión) y el
        mensaje de usuario guarda un chip {name, url, mimetype} para mostrar un
        enlace descargable en la burbuja. El texto extraído lo guarda la
        sesión aparte (remember_documents).
        """
        import base64
        from odoo.addons.pns_ai_mcp.utils.session_download import (
            persist_turn_file,
        )
        try:
            files = json.loads(self.files) if self.files else []
        except Exception:
            files = []
        chips = []
        if not files:
            return chips
        for idx, f in enumerate(files):
            name = (f or {}).get('name') or ('archivo-%s' % (idx + 1))
            mimetype = (f or {}).get('mimetype') or ''
            _mt, b64 = file_text.split_data_url((f or {}).get('data') or '')
            if not b64:
                continue
            try:
                raw = base64.b64decode(b64)
                chip = persist_turn_file(
                    self.env, self.session_id.id, raw, name,
                    mimetype or _mt or 'application/octet-stream',
                )
                if chip:
                    self.session_id._claim_turn_file_chips([chip])
                    chips.append({
                        'name': chip['name'],
                        'url': chip['url'],
                        'mimetype': chip['mimetype'],
                    })
            except Exception:
                _logger.warning(
                    'Chatboo async job %s: no se pudo persistir el fichero %s',
                    self.id, name, exc_info=True,
                )
        return chips

    def _llm_history_for_session(self, done_meta, visible):
        """Historial compacto para el siguiente turno (stubs, no HTML de burbuja).

        El motor lo emite en ``done.history``. Si falta (turno viejo / error),
        se reconstruye aquí para que el cliente no reenvíe tablas enormes.
        """
        meta = done_meta if isinstance(done_meta, dict) else {}
        hist = meta.get('history')
        if isinstance(hist, list) and hist:
            return hist
        try:
            from odoo.addons.pns_ai_mcp.utils.history_compact import (
                append_turn_stub,
                compact_history_for_llm,
            )
            try:
                incoming = json.loads(self.history) if self.history else []
            except Exception:
                incoming = []
            return append_turn_stub(
                compact_history_for_llm(incoming),
                self.prompt or '',
                visible=visible or '',
            )
        except Exception:
            _logger.debug(
                'Chatboo async job %s: could not compact LLM history',
                self.id, exc_info=True,
            )
            return None

    def _save_to_session(self, acc, done_meta, error, incomplete=False, not_started=False, query_code=None, query_data=None, active_skill=_SKILL_STATE_LEAVE, domain_codes=_DOMAIN_CODES_LEAVE, reclaim=False, drop_query_cache=False):
        """Añade el turno (usuario + asistente) al historial de la sesión.

        El contenido del asistente se guarda en crudo (markdown) con el flag
        ``raw``; el cliente lo formatea al recargar (reutiliza su formateador).

        ``incomplete=True`` marca una respuesta recuperada tras un reinicio: se
        guarda lo que se alcanzó a generar con una nota discreta y SIN estilo de
        error rojo (un reinicio no es un fallo del usuario). ``not_started=True``
        distingue el caso de un job que nunca llegó a arrancar (mensaje distinto).

        ``reclaim=True``: ruta ligera al cerrar un job zombie (reinicio Docker /
        worker muerto). No re-persiste base64 de imágenes/ficheros ni busca
        huérfanos: un prompt fallido no puede bloquear la apertura de Chatboo.
        """
        session = self.session_id
        if not session or not session.exists():
            return
        # Lectura fresca: el worker lleva su propia transacción abierta durante
        # toda la inferencia; invalidamos para no partir de un snapshot viejo.
        try:
            session.invalidate_recordset(['messages', 'staged_assistant_files'])
        except AttributeError:
            try:
                session.invalidate_cache(
                    ['messages', 'staged_assistant_files'], ids=session.ids,
                )
            except Exception:
                pass
        messages = session.get_messages()

        elapsed = None
        if self.started_at:
            elapsed = (fields.Datetime.now() - self.started_at).total_seconds()
        wall = self.env['chatboo.session'].format_display_datetime()
        stamp = wall
        if elapsed is not None:
            stamp = '%s (%ds)' % (wall, int(round(elapsed)))

        # Turno de usuario (para que quede persistido aunque el cliente no lo guarde).
        # Las imágenes pegadas se persisten como adjuntos y se referencian por URL
        # (NO se guarda base64 en el blob de la sesión: lo inflaría y se recarga
        # entero cada turno). Así el histórico conserva las capturas y son clicables.
        _user_msg = {
            'role': 'user',
            'content': self.prompt or '',
            'timestamp': wall,
        }
        _user_images = []
        _user_files = []
        if not reclaim:
            _user_images = self._persist_turn_images()
            if _user_images:
                _user_msg['images'] = _user_images
            _user_files = self._persist_turn_files()
            if _user_files:
                _user_msg['files'] = _user_files
        messages.append(_user_msg)

        _assistant_files = []
        _assistant_content = None
        _clip_data = None
        if not reclaim:
            try:
                from odoo.addons.pns_ai_mcp.utils.session_download import (
                    coalesce_download_chips,
                )
            except Exception:
                coalesce_download_chips = lambda *groups: [
                    c for g in groups for c in (g or [])
                    if isinstance(c, dict) and (c.get('url') or c.get('name'))
                ]
            _staged = session._consume_staged_assistant_download_chips()
            _orphans = session.recover_orphan_download_chips(
                messages=messages, since=self.started_at,
            )
            _assistant_files = coalesce_download_chips(
                (done_meta or {}).get('assistant_files'),
                _staged,
                _orphans,
            )
            _clip_data = (done_meta or {}).get('clip_data')
            svg_chips = []
            if (acc or '').strip() and not error:
                try:
                    from odoo.addons.pns_ai_mcp.utils.svg_download import (
                        persist_inline_svgs_from_html,
                    )
                    skill_code = None
                    if isinstance(active_skill, dict):
                        skill_code = active_skill.get('code') or None
                    if not skill_code:
                        skill_code = session.active_skill_code or None
                    svg_chips, acc = persist_inline_svgs_from_html(
                        self.env, session.id, acc,
                        prompt=self.prompt,
                        skill_code=skill_code,
                    )
                    svg_chips = svg_chips or []
                except Exception:
                    _logger.warning(
                        'Chatboo async job %s: no se pudieron persistir SVG inline',
                        self.id, exc_info=True,
                    )
            if svg_chips:
                _assistant_files = list(_assistant_files or []) + list(svg_chips)
                _assistant_content = acc or ''
            if _assistant_files:
                _assistant_files = session._claim_turn_file_chips(_assistant_files)
            _done_show = (done_meta or {}).get('presentation_show_mode')
            if _done_show:
                try:
                    session.write({'presentation_show_mode': _done_show})
                except Exception:
                    pass

        # Historial readline (flechas ↑/↓): persistir el prompt enviado para que
        # sobreviva al recargar la página. Con auto-promoción el cliente ya no
        # re-guarda la sesión (el worker autora el turno), así que si no lo
        # anotamos aquí el input_history se perdería. Dedup del último; el tope
        # (50) lo aplica set_input_history.
        if (self.prompt or '').strip():
            try:
                hist = session.get_input_history()
                if not hist or hist[-1] != self.prompt:
                    hist.append(self.prompt)
                    session.set_input_history(hist)
            except Exception:
                _logger.debug(
                    "Chatboo async: no se pudo actualizar input_history (sesión %s)",
                    session.id, exc_info=True,
                )

        if incomplete:
            # Recuperación tras reinicio: lo generado (si hay) + nota discreta.
            if (acc or '').strip():
                _note = _('(incomplete response: interrupted by a server restart)')
                _content = u"%s\n\n_%s_" % (acc, _note)
            elif not_started:
                _content = u"_%s_" % _(
                    'The request could not be started. Please resend.'
                )
            else:
                _content = u"_%s_" % _(
                    'The response was interrupted by a server restart. Please resend.'
                )
            messages.append({
                'role': 'assistant',
                'content': _content,
                'original_content': acc or '',
                'raw': True,
                'incomplete': True,
                'timestamp': stamp,
                **({'files': _assistant_files} if _assistant_files else {}),
            })
        elif error:
            messages.append({
                'role': 'assistant',
                'content': u"\U0001F6D1 %s\n\n%s" % (_('MCP engine error:'), error),
                'raw': True,
                'is_error': True,
                'timestamp': stamp,
                **({'files': _assistant_files} if _assistant_files else {}),
                **({'clip_data': _clip_data} if _clip_data else {}),
            })
        else:
            # Pie de respuesta: cada stack consume una forma distinta y hay que
            # reproducir AMBAS para que el pie sobreviva al recargar la sesión
            # (antes lo escribía el cliente en vivo; ahora lo autora el worker):
            #   · owl1 -> campos planos + model_details:{model,provider} + sources[]
            #   · owl2 -> objeto meta:{model,provider,context_limit,usage,sources,...}
            # Todo sale del evento 'done' del motor (done_meta), que ya trae
            # model, provider, protocol, context_limit, usage y sources.
            _dm = done_meta or {}
            _model = _dm.get('model') or ''
            _provider = _dm.get('provider') or ''
            _display_currency = _dm.get('display_currency') or ''
            _sources = _dm.get('sources') or []
            _records = _dm.get('records') or []
            _usage = _dm.get('usage') or None
            _ctx_limit = _dm.get('context_limit') or None
            _speed = _dm.get('speed_tps') or 0
            _pspeed = _dm.get('prompt_speed_tps') or 0
            _turn = (_dm.get('turn') or '').strip()
            _user_prompt = (self.prompt or '').strip()
            _local = bool(_dm.get('local_ack'))
            if _local:
                _usage = None
                _ctx_limit = None
                _turn = ''
                _speed = 0
                _pspeed = 0
                _model = _model or 'Chatboo'
                _provider = _provider or 'local'
                for _prev in reversed(messages):
                    if isinstance(_prev, dict) and _prev.get('role') == 'user':
                        _prev['offtopic'] = True
                        break
            _model_details = (
                {
                    'model': _model,
                    'provider': _provider,
                    'display_currency': _display_currency,
                }
                if (_model or _provider) else None
            )
            _meta = {
                'model': _model,
                'provider': _provider,
                'display_currency': _display_currency,
                'protocol': _dm.get('protocol') or '',
                'context_limit': _ctx_limit,
                'usage': _usage,
                'sources': _sources,
                'records': _records,
                'speed_tps': _speed,
                'prompt_speed_tps': _pspeed,
                'turn': _turn,
                'local_ack': _local,
                'user_prompt': _user_prompt,
            }
            messages.append({
                'role': 'assistant',
                'content': acc or '',
                'original_content': acc or '',
                'raw': True,
                # ── owl1 (campos planos que lee chatboo_component_v2.js) ──
                'usage': _usage,
                'context_limit': _ctx_limit,
                'speed_tps': _speed,
                'prompt_speed_tps': _pspeed,
                'turn': _turn,
                'local_ack': _local,
                'user_prompt': _user_prompt,
                'offtopic': _local,
                'model_details': _model_details,
                'sources': _sources,
                'records': _records,
                'backend_history': self._llm_history_for_session(
                    _dm, acc,
                ),
                # ── owl2 (objeto meta que lee chatboo_app.js) ──
                'meta': _meta,
                'timestamp': stamp,
                **({'files': _assistant_files} if _assistant_files else {}),
                **({'clip_data': _clip_data} if _clip_data else {}),
            })

        session.set_messages(messages)
        # Persistir el ancla de reutilización solo cuando hay un código nuevo
        # exitoso (turno normal). En recuperaciones/errores llega None y se
        # conserva el de la última consulta buena.
        if query_code:
            try:
                session.write({'last_query_code': query_code})
            except Exception:
                _logger.debug(
                    "Chatboo async: no se pudo guardar last_query_code (sesión %s)",
                    session.id, exc_info=True,
                )
        # Nivel 2: cachear el dataset (filas) con su marca de tiempo para expirarlo
        # por antigüedad. query_data es None salvo en un turno normal con datos.
        # Un turno que respondió sin filas (informe, prosa) retira la caché:
        # si no, el siguiente «reformatea» reinyecta la tabla de un tema anterior.
        # Error, cancelación y reclaim no pasan drop_query_cache: se conserva.
        if query_data is not None:
            try:
                session.write({
                    'last_query_data': json.dumps(query_data, default=str, ensure_ascii=False),
                    'last_query_data_date': fields.Datetime.now(),
                })
            except Exception:
                _logger.debug(
                    "Chatboo async: no se pudo guardar last_query_data (sesión %s)",
                    session.id, exc_info=True,
                )
        elif (
            drop_query_cache
            and not error
            and not incomplete
            and not not_started
            and not reclaim
        ):
            try:
                session.write({
                    'last_query_data': False,
                    'last_query_data_date': False,
                    'last_query_code': False,
                })
            except Exception:
                _logger.debug(
                    "Chatboo async: no se pudo retirar last_query_data (sesión %s)",
                    session.id, exc_info=True,
                )
        # Skill pegajoso: persistir el estado emitido por el motor. code con
        # valor → fijar/actualizar; code=None → soltar; sentinela → no tocar.
        if active_skill is not _SKILL_STATE_LEAVE:
            try:
                code = (active_skill or {}).get('code')
                if code:
                    session.write({
                        'active_skill_code': code,
                        'active_skill_params': json.dumps(
                            (active_skill or {}).get('params') or {},
                            default=str, ensure_ascii=False,
                        ),
                    })
                else:
                    session.write({
                        'active_skill_code': False,
                        'active_skill_params': False,
                    })
            except Exception:
                _logger.debug(
                    "Chatboo async: no se pudo guardar active_skill (sesión %s)",
                    session.id, exc_info=True,
                )
        if not error and domain_codes is not _DOMAIN_CODES_LEAVE:
            try:
                session.write({
                    'last_domain_codes': (
                        json.dumps(domain_codes, ensure_ascii=False)
                        if domain_codes else False
                    ),
                })
            except Exception:
                _logger.debug(
                    "Chatboo async: no se pudo guardar last_domain_codes "
                    "(sesión %s)",
                    session.id, exc_info=True,
                )
        session.update_last_used()
        # Devuelve los chips persistidos del turno de usuario (imágenes con URL
        # /web/image y ficheros con URL /web/content). El cliente los usa para
        # PARCHEAR en su sitio la burbuja recién enviada, que aún mostraba el
        # base64 (imágenes) y los ficheros sin URL (no clicables). Así se abren en
        # pestaña sin esperar a recargar la sesión.
        result = {
            'user_images': _user_images or [],
            'user_files': _user_files or [],
            'assistant_files': _assistant_files or [],
        }
        if _assistant_content is not None:
            result['assistant_content'] = _assistant_content
        return result

    # ──────────────────────────── Lectura (tail / poll) ────────────────────────────

    def mark_seen(self):
        """Marca el job como entregado a un cliente (evita re-entrega por poll)."""
        own = self if self.env.su else self.search([
            ('id', 'in', self.ids), ('user_id', '=', self.env.uid),
        ])
        for rec in own:
            try:
                with _get_registry(rec.env.cr.dbname).cursor() as cr:
                    cr.execute(
                        "UPDATE chatboo_async_request SET seen=true WHERE id=%s", (rec.id,),
                    )
            except Exception:
                _logger.debug("Chatboo async mark_seen failed (request %s)", rec.id, exc_info=True)

    def _cancel_pending(self):
        """Cerrado antes de arrancar: el aviso queda como respuesta del turno."""
        msg = '⏹ ' + _('Generation cancelled.')
        self.sudo().write({
            'state': 'done',
            'response': msg,
            'partial': msg,
            'finished_at': fields.Datetime.now(),
            'seen': False,
        })
        try:
            self._save_to_session(msg, {}, error=None)
        except Exception:
            _logger.debug(
                "Chatboo async: cancel persist failed (job %s)",
                self.id, exc_info=True,
            )
        try:
            self._notify('async_done')
        except Exception:
            pass

    # ──────────────────────────── Mantenimiento (cron) ────────────────────────────

    def _reclaim_one(self, timeout_ms):
        """En vez de marcarlo como error rojo, RECUPERAMOS lo que se alcanzó a
        generar (``partial``) y lo guardamos en la sesión como respuesta
        incompleta, cerrando el job como 'done' y avisando como info. Así la
        respuesta sobrevive al reinicio. Ruta ``reclaim=True``: sin re-persistir
        base64.
        """
        partial = self.partial or ''
        never_started = self.state == 'pending' and not partial
        _logger.warning(
            "Chatboo async: reclaiming stuck job %s (%s), recovering %s chars",
            self.id, self.state, len(partial),
        )
        # Cerrar YA el estado dentro del savepoint; si el save a
        # sesión falla/timeout, el fallback SQL deja el job done.
        self.sudo().write({
            'state': 'done',
            'response': partial,
            'error': False,
            'finished_at': fields.Datetime.now(),
        })
        if timeout_ms > 0:
            try:
                self.env.cr.execute(
                    "SET LOCAL statement_timeout = %s",
                    (int(timeout_ms),),
                )
            except Exception:
                pass
        try:
            self._save_to_session(
                partial, {}, error=None, incomplete=True,
                not_started=never_started, reclaim=True,
            )
        finally:
            if timeout_ms > 0:
                try:
                    self.env.cr.execute(
                        "SET LOCAL statement_timeout = DEFAULT",
                    )
                except Exception:
                    pass
        try:
            self._notify('async_done')
        except Exception:
            pass

    @api.model
    def cron_maintenance(self):
        """Punto de entrada del cron: reclama colgados y purga viejos."""
        jobs = (self, self.env['chatboo.canvas.job'])
        for model in jobs:
            try:
                model._reclaim_stuck()
            except Exception:
                _logger.exception("Chatboo jobs: cron reclaim failed (%s)", model._name)
        # Liberar locks antes del GC: un reclaim lento no debe retener el
        # ir.cron "busy" mientras purga (otros workers lo saltaban eternamente).
        if not _is_test_mode(self.env):
            try:
                self.env.cr.commit()
            except Exception:
                _logger.debug("Chatboo async: cron commit after reclaim failed", exc_info=True)
        for model in jobs:
            try:
                model._gc_old()
            except Exception:
                _logger.exception("Chatboo jobs: cron GC failed (%s)", model._name)
        # Nivel 2: purgar datasets cacheados obsoletos (por antigüedad) para que
        # no se acumulen en sesiones de larga vida. No debe tumbar el cron.
        try:
            self.env['chatboo.session']._gc_stale_query_data()
        except Exception:
            _logger.debug("Chatboo async: _gc_stale_query_data falló", exc_info=True)
        self.env['chatboo.session']._cleanup_old_sessions()

    # ──────────────────────────── Bus ────────────────────────────

    def _notify(self, action):
        """Avisa al usuario por el bus. Compatible Odoo 14 y 17+.

        El front (componente + systray) ya entiende ``pns_chatboo_sync`` con
        ``action`` in {thinking, async_done, error}.
        """
        self.ensure_one()
        partner = self.user_id.partner_id
        if not partner:
            return
        payload = {
            'type': 'pns_chatboo_sync',
            'action': action,
            'session_id': self.session_id.id,
            'request_id': self.id,
            'is_error': action == 'error',
        }
        bus = self.env['bus.bus']
        try:
            # Odoo 16/17+: _sendone(target, notification_type, message)
            bus._sendone(partner, 'pns_chatboo_sync', payload)
            return
        except (AttributeError, TypeError):
            pass
        try:
            # Odoo 14: sendone(channel, message)
            channel = (self.env.cr.dbname, 'res.partner', partner.id)
            bus.sendone(channel, json.dumps(payload, ensure_ascii=False))
        except Exception:
            _logger.debug("Chatboo async bus notify failed (request %s)", self.id, exc_info=True)
