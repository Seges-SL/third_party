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
from odoo.exceptions import AccessError

from .chatboo_job import _env_manage, _get_registry, _is_test_mode
from ..utils import file_text, turn_documents
from ..utils.chatboo_product_icp import CHATBOO_AGENT_CODE
from ..utils.turn_deliverable import done_meta_has_deliverable

_logger = logging.getLogger(__name__)

# Sentinel: "leave the session's active skill state alone" on finalize
# (not the same as code=None, which means drop it).
_SKILL_STATE_LEAVE = object()
_DOMAIN_CODES_LEAVE = object()

# How often progress is flushed to the database (seconds). Preview step.
FLUSH_INTERVAL = 0.3
# Attached PDF: pages whose printed text is read, and pages of a scan that
# go as pictures (each one adds weight to the vision call).
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
    """A Chatboo turn run in the background (apart from the HTTP request)."""
    _name = 'chatboo.async.request'
    _inherit = 'chatboo.job.mixin'
    _description = 'Chatboo Async Request'
    _order = 'create_date desc'
    _rec_name = 'id'

    prompt = fields.Text(string='Prompt', required=True)
    # The prompt is the outcome of a confirmed/cancelled write, written by the
    # chat for the AI: it is kept in the history but never painted as the user's.
    result_note = fields.Boolean(string='Result note')
    history = fields.Text(string='History (JSON)')
    agent_code = fields.Char(string='Agent code')
    provider_id = fields.Integer(string='Provider id')
    # Light descriptor taken on the client (model, id, view) as JSON.
    screen_context = fields.Text(string='Screen context (JSON)')
    # Companies ticked in the web switcher when the question was sent (JSON
    # list, active one first). Kept on the job: a reclaimed turn runs there too.
    screen_company_ids = fields.Char(string='Screen companies (JSON)')
    # Pictures of the turn (data URLs, JSON list). The base64 goes to the vision
    # provider ONLY in this turn and is purged with the job (GC 72h); it NEVER
    # enters the history sent to the LLM (anti-overflow rule). To SHOW them,
    # though, they are saved once as ir.attachment linked to the session and the
    # user message keeps only their URL (see _persist_turn_images).
    images = fields.Text(string='Images (JSON)')
    # Original names of the turn's pictures, matched by index with
    # `images` (JSON list). null for clipboard pastes (no name)
    # and the real name for pictures attached as a file. Used to name the
    # ir.attachment and show the name under the thumbnail (see _persist_turn_images).
    image_names = fields.Text(string='Image names (JSON)')
    # Text/data files attached with the clip (JSON list of
    # {name, mimetype, data(dataURL base64)}). Their extracted TEXT is added to
    # THIS turn's message to the LLM (one turn only, not in the history);
    # the file is saved as ir.attachment and the message keeps a
    # download chip (see _persist_turn_files / utils.file_text).
    files = fields.Text(string='Files (JSON)')

    # Visible content so far (tokens/replace) for the preview and the save.
    partial = fields.Text(string='Partial content')
    # Structured non-token events (status, verification, ...) that the tail
    # sends again as they are over SSE. JSON list.
    struct_events = fields.Text(string='Structured events (JSON)')
    # Metadata of the engine's 'done' event (usage, context_limit, speed, ...).
    done_meta = fields.Text(string='Done meta (JSON)')
    response = fields.Text(string='Final response')
    # True when a client already got the result live (SSE) or by poll.
    seen = fields.Boolean(string='Seen by client', default=False, index=True)
    # ──────────────────────────── Queue (controller only) ────────────────────────────

    @api.model
    def _enqueue(self, session_id, message, history=None, agent_code=None,
                 provider_id=None, screen_context=None, images=None, files=None,
                 image_names=None, screen_company_ids=None, result_note=False):
        """Create the job as pending. Does not start the thread (see ``_spawn``)."""
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
            'result_note': bool(result_note),
            'history': json.dumps(history or [], ensure_ascii=False),
            'agent_code': agent_code or False,
            'provider_id': int(provider_id) if provider_id else False,
            'screen_context': sc_json,
            'screen_company_ids': (
                json.dumps(list(screen_company_ids)) if screen_company_ids else False
            ),
            'images': json.dumps(images, ensure_ascii=False) if images else False,
            'image_names': json.dumps(image_names, ensure_ascii=False) if image_names else False,
            'files': json.dumps(files, ensure_ascii=False) if files else False,
            'state': 'pending',
        })

    def _on_crash(self, msg):
        self._finalize('', [], {}, error=msg)

    def _screen_companies(self):
        """What the switcher ticked when the question was sent (may be empty)."""
        from odoo.addons.pns_ai_mcp.utils.one_company import screen_ids
        try:
            return screen_ids(json.loads(self.screen_company_ids or '[]'))
        except (TypeError, ValueError):
            return []

    def _turn_company_ids(self):
        """The companies this turn reads in, after the user's own are checked."""
        from odoo.addons.pns_ai_mcp.utils.one_company import ai_companies
        return ai_companies(self.env, self._screen_companies()).ids

    # ──────────────────────────── Run ────────────────────────────

    def _process(self):
        """Run the engine, flush progress to the database, save to the session and notify."""
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
        # Query reuse anchor (Level 1): we pick up the code of the last
        # successful query the engine emits (event 'query_code') to save it
        # in the session, and we read the previous turn's one so the engine
        # sends it again as a hint (keeps it from rewriting the query on each
        # reformat → main source of drift).
        last_query_code = None
        last_query_data = None
        try:
            prior_query_code = self.session_id.last_query_code or None
        except Exception:
            prior_query_code = None
        # Level 2: previous turn's dataset ONLY if still fresh (TTL). It is
        # sent again as previous_result to reformat without querying again.
        # Rows read in other companies are not this screen's: query again.
        try:
            prior_query_data = self.session_id.get_fresh_query_data(
                self._turn_company_ids())
        except Exception:
            prior_query_data = None
        # Sticky skill: code + params of the session's active skill. The engine
        # uses them to judge (via AI) whether this turn refines the active skill.
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
        # Active skill state the engine emitted this turn (sentinel =
        # untouched → do not rewrite the session).
        active_skill_touched = False
        active_skill_evt = None

        try:
            history = json.loads(self.history) if self.history else []
        except Exception:
            history = []

        # Pictures of the turn (data URLs). For the current turn only: they go
        # to the vision provider as content-parts; they stay out of the history.
        try:
            images = json.loads(self.images) if self.images else []
        except Exception:
            images = []

        # Text/data files attached with the clip: we extract their text and
        # add it to THIS turn's message (not to self.prompt nor to the
        # history). So the LLM sees the file's content only when it is
        # attached, like the pictures (one turn only, anti-overflow).
        message_for_engine, inline_file_text, pdf_pages, turn_docs = (
            self._augment_prompt_with_files(self.prompt or '')
        )
        # A skill slash keeps its words as its arguments; the file's text
        # would land in them. The skill reads it with documents/read_document.
        if turn_docs and self._prompt_runs_a_skill():
            message_for_engine = self.prompt or ''
            inline_file_text = False
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

        # Rows the user marked in the previous answer. They travel WITH the
        # sentence, not only inside the dataset: the engine only reads text, and
        # a dataset narrowed quietly left it free to search for the name
        # again. They are used up by this turn.
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
        # Documents from earlier turns: like the rows of a table, the
        # text stays in the session and the model reads it with read_document.
        # This turn's ones already go whole in the message (or in their photos).
        # A skill slash does not carry the note: its words are the skill's
        # arguments, and the note would be scored as part of the sentence.
        try:
            turn_docs = turn_docs + self._image_documents()
            this_turn = {doc['name'] for doc in turn_docs}
            earlier = [
                doc for doc in self.session_id.get_documents()
                if doc['name'] not in this_turn
            ]
            documents_note = turn_documents.note(earlier)
            if documents_note and not self._prompt_runs_a_skill():
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
        # Limited recall of earlier pictures (1c): we send again, capped and
        # downscaled, the last pictures already seen in the conversation so
        # the model can refer to them (LLMs have no state: a picture
        # is "remembered" only if it is SENT AGAIN). They stay out of the saved
        # history; they are rebuilt each turn from the ir.attachment rows.
        #
        # BUT: if THIS turn ALREADY brings pictures, we do NOT recall older ones.
        # When the user attaches pictures and asks "what is in these?", they
        # mean the ones in the CURRENT prompt; sending old pictures made the
        # model mix in / mention a picture from several turns ago. Recall
        # is for TEXT-only turns that point to something already sent.
        recall_images = [] if images else self._recall_prior_images()

        # Separate HEARTBEAT: another thread refreshes write_date every
        # HEARTBEAT_INTERVAL while the turn lasts, WHATEVER happens to the engine.
        # So a slow model (it may take minutes to emit the first token)
        # is never mistaken for a dead worker, and reclaim does not kill it.
        beat = self._start_heartbeat()

        # Diagnostics: we count what the engine emits. A turn that ends in 0s and
        # blank almost always means the engine never emitted tokens
        # (provider not resolved in the thread, empty endpoint, etc.). This count
        # in the log is what tells "no content" apart from "crash".
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
            from odoo.addons.pns_ai_mcp.utils.one_company import SCREEN_COMPANIES
            engine_env = self.env(context=dict(
                self.env.context or {},
                **{SCREEN_COMPANIES: self._screen_companies()},
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
                turn_file_names=self._turn_file_names(),
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
                    # Internal meta-event: sticky skill state (code+params,
                    # or code=None to drop it). Saved on finalize.
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
                    # Internal meta-event: not content nor a tail event;
                    # we only keep the turn's last successful code.
                    if evt.get('code'):
                        last_query_code = evt['code']
                    continue
                if ev == 'query_data':
                    # Internal meta-event (Level 2): rows of the last successful
                    # dataset, to cache them and reuse them next turn.
                    if evt.get('data') is not None:
                        last_query_data = evt['data']
                    continue
                if ev == 'token' and evt.get('content'):
                    acc += evt['content']
                elif ev == 'replace':
                    # 'replace' sets the content so far. An EMPTY replace is
                    # a reset signal: the engine emits it on failover after
                    # a partial output, so the answer is not DUPLICATED
                    # when the next provider writes it again.
                    acc = evt.get('content') or ''
                elif ev == 'done':
                    done_meta = evt
                elif ev == 'error':
                    if evt.get('content'):
                        acc += evt['content']
                    struct.append(evt)
                else:
                    # status, verification, ... → send again as is in the tail
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
            # Stop and WAIT for the heartbeat BEFORE saving: if it is still alive,
            # its concurrent update to the row collides with _finalize.
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
        except Exception as exc:  # noqa: BLE001 — the engine can fail in many ways
            _logger.exception(
                "Chatboo async job %s failed (events so far=%s, acc_len=%s)",
                self.id, ev_counts, len(acc),
            )
            self._stop_heartbeat(beat)
            beat = None
            self._release_turn_cursor()
            self._finalize(acc, struct, done_meta, error=str(exc) or exc.__class__.__name__)
        finally:
            # Stop the heartbeat whatever happens (success or error).
            self._stop_heartbeat(beat)
            # This cursor holds a REPEATABLE READ snapshot of the WHOLE turn.
            # What must last (session, job, logs, recipes, usage) was already
            # committed on its own cursors. A commit here clashes with the
            # heartbeat/flush (PG 40001) and _spawn() showed "MCP engine error"
            # over a good turn. In tests the TestCursor IS the test's
            # transaction: no rollback.
            if not _is_test_mode(self.env):
                try:
                    self.env.cr.rollback()
                except Exception:
                    pass

    def _flush_progress(self, acc, struct):
        """Flush partial progress to the database on its own cursor (seen by the tail).

        Also refreshes ``write_date`` (heartbeat): that is how a live job
        is told apart from one killed by a restart, which stops beating.
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

    def _prompt_runs_a_skill(self):
        """True when the prompt is a slash that names a skill."""
        try:
            from odoo.addons.pns_ai_mcp.utils.slash_domain_codes import (
                parse_slash_command,
            )
        except Exception:
            return False
        parsed = parse_slash_command(self.prompt)
        return bool(parsed) and self._command_resolves_skill(parsed[0])

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
        """Write the final state, save the turn to the session and notify over the bus."""
        # Safety net against blanks: if the engine ended "fine" but with no
        # content, it is a real failure (provider not resolved in the thread,
        # empty stream, etc.). We never leave a silent blank turn: we mark it
        # as an error with a clear message so the user sees it and it is logged.
        # Exception: a named export (PDF/Excel/…) with the table hidden on
        # purpose — the bubble is empty and the card/clip_data are the result
        # (C8N1: showing "MCP engine error" over a good PDF).
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

        # Save in a FRESH transaction (own cursor), NOT on the worker's main
        # cursor: that cursor carries an old snapshot, and the concurrent
        # writes to this same row (flush every 0.3s, heartbeat) make its
        # final commit fail with "could not serialize access due to
        # concurrent update" (REPEATABLE READ), aborting the transaction and leaving
        # the turn red even though it was generated. A new cursor sees the latest
        # commits and writes without a collision.
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
                            # Copy the saved chips of the user turn into
                            # done_meta (already written in vals): the controller puts
                            # done_meta in the 'done' event and the client patches the
                            # bubble live (base64 → /web/image, clickable files).
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

        # Last resort: write the final state with raw SQL so the job does not hang
        # (the SSE tail still sends the state/error to the client without a session).
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

    # ── Saving the turn's pictures (to SHOW them, not for the LLM) ──────
    _IMG_EXT_BY_MIME = {
        'image/png': '.png', 'image/jpeg': '.jpg', 'image/jpg': '.jpg',
        'image/gif': '.gif', 'image/webp': '.webp', 'image/bmp': '.bmp',
        'image/svg+xml': '.svg', 'image/x-icon': '.ico',
        'image/vnd.microsoft.icon': '.ico',
    }

    def _persist_turn_images(self):
        """Save the turn's pictures as ir.attachment and return chips.

        Revised rule: the base64 NEVER enters the session's JSON blob nor
        the history sent to the LLM. But we DO save each picture once
        as an attachment linked to the session, and the user message keeps a chip
        ``{url, name}`` (/web/image with no token: whoever can read the session opens it). So the
        history keeps the screenshots (multi-device), they open in a tab and
        keep their NAME when attached as a file (clipboard pastes
        have no name → name=None). Deleting the session also unlinks
        the linked ir.attachment rows (res_model/res_id), so they do not pile up.
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
                    'raw': base64.b64decode(b64),
                    'mimetype': mimetype or 'image/png',
                    'res_model': 'chatboo.session',
                    'res_id': self.session_id.id,
                })
                out.append({
                    'url': '/web/image/%s' % att.id,
                    'name': orig,  # None for clipboard pastes
                })
            except Exception:
                _logger.warning(
                    'Chatboo async job %s: could not persist turn image %s',
                    self.id, idx, exc_info=True,
                )
        return out

    # ── Limited recall of earlier pictures (1c) ─────────────────────────────
    # How many earlier session pictures are sent again as context, and the
    # max side they are scaled to (to cap tokens, as ChatGPT/Claude do).
    _RECALL_MAX_IMAGES = 3
    _RECALL_MAX_SIDE = 768
    # RASTER formats that vision models can decode. image/svg+xml is
    # LEFT OUT (and other vector/icon formats): an SVG in the recall made
    # ALL providers reject the turn ("cannot identify image file" /
    # "does not contain a valid JPG, PNG, WebP, or ICO image") and set off
    # failover down the chain until none was left. Also, the session gathers
    # attachments that are not user photos (skill icons like pin.svg, record
    # thumbnails…); filtering by these MIME types avoids sending vector junk.
    _RECALL_VISION_MIMETYPES = (
        'image/jpeg', 'image/jpg', 'image/png',
        'image/gif', 'image/webp', 'image/bmp',
    )

    def _recall_prior_images(self):
        """Data URLs (downscaled) of the last pictures already seen in the session.

        Sends again, CAPPED, the pictures of earlier turns so the model
        can refer to them (LLMs have no state: they only "remember" what
        is sent again). The CURRENT turn's ones are not saved here yet, so
        they are not duplicated. Returns them oldest first.
        """
        if not self.session_id:
            return []
        try:
            # We ask for more than needed so we can DEDUPLICATE by checksum: the same
            # photo attached in several turns makes several identical ir.attachment;
            # sending it again and again wastes context and confuses the model.
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
                raw = bytes(att.raw or b'')
                if not raw:
                    continue
                data_url = self._downscale_image_to_data_url(raw, att.mimetype)
                if data_url:
                    urls.append(data_url)
                if len(urls) >= self._RECALL_MAX_IMAGES:
                    break
            except Exception:
                continue
        urls.reverse()  # oldest to newest
        return urls

    @classmethod
    def _downscale_image_to_data_url(cls, raw, mimetype):
        """Scale a picture down to the max side and return it as a base64 data URL.

        pns_base prepares it (upright, JPEG stays JPEG, the rest PNG). If it
        cannot (odd format, no Pillow), it returns the original picture in
        base64: the cap on COUNT already limits the cost.
        """
        from odoo.addons.pns_base.utils.pdf_io import shrink_picture

        shrunk = shrink_picture(raw, cls._RECALL_MAX_SIDE)
        if shrunk:
            payload, mt = shrunk
            return 'data:%s;base64,%s' % (mt, base64.b64encode(payload).decode('ascii'))
        # Fallback WITHOUT Pillow (or a format it cannot open): we send the original
        # ONLY if it is a raster that vision accepts. NEVER emit SVG or other
        # vector/unknown formats: providers reject them and bring the
        # turn down with failover down the chain.
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
            response = self.env['ai.execution.engine'].sudo()._chat_completion(
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

    def _turn_file_names(self):
        """Names of the files attached to this turn (not the pictures)."""
        try:
            files = json.loads(self.files) if self.files else []
        except Exception:
            files = []
        return tuple(
            f['name'] for f in files
            if isinstance(f, dict) and isinstance(f.get('name'), str) and f['name']
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
        """Save the turn's files as ir.attachment and return chips.

        Like the pictures: the file is saved once (linked to the session) and the
        user message keeps a chip {name, url, mimetype} to show a
        download link in the bubble. The session keeps the extracted text
        on its own (remember_documents).
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
                    'Chatboo async job %s: could not persist file %s',
                    self.id, name, exc_info=True,
                )
        return chips

    def _llm_history_for_session(self, done_meta, visible):
        """Compact history for the next turn (stubs, not bubble HTML).

        The engine emits it in ``done.history``. If missing (old turn / error),
        it is rebuilt here so the client does not send huge tables again.
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
        """Add the turn (user + assistant) to the session history.

        The assistant content is saved raw (markdown) with the flag
        ``raw``; the client formats it on reload (reuses its formatter).

        ``incomplete=True`` marks an answer recovered after a restart: what
        was generated is saved with a quiet note and WITHOUT the red
        error style (a restart is not the user's fault). ``not_started=True``
        marks a job that never got to start (a different message).

        ``reclaim=True``: light path when closing a zombie job (Docker restart /
        dead worker). It does not save image/file base64 again nor look for
        orphans: a failed prompt must not block opening Chatboo.
        """
        session = self.session_id
        if not session or not session.exists():
            return
        # Fresh read: the worker keeps its own transaction open during
        # the whole inference; we invalidate so we do not start from an old snapshot.
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

        # User turn (so it is saved even if the client does not save it).
        # Pasted pictures are saved as attachments and pointed to by URL
        # (NO base64 in the session blob: it would bloat it, and it is reloaded
        # whole each turn). So the history keeps the screenshots and they are clickable.
        _user_msg = {
            'role': 'user',
            'content': self.prompt or '',
            'timestamp': wall,
        }
        if self.result_note:
            _user_msg['result_note'] = True
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
                        'Chatboo async job %s: could not persist inline SVG',
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

        # Readline history (↑/↓ arrows): save the sent prompt so it
        # survives a page reload. With auto-promotion the client no longer
        # saves the session again (the worker writes the turn), so if we do not
        # note it here input_history would be lost. Skip a repeat of the last; the cap
        # (50) is applied by set_input_history.
        if (self.prompt or '').strip():
            try:
                hist = session.get_input_history()
                if not hist or hist[-1] != self.prompt:
                    hist.append(self.prompt)
                    session.set_input_history(hist)
            except Exception:
                _logger.debug(
                    "Chatboo async: could not update input_history (session %s)",
                    session.id, exc_info=True,
                )

        if incomplete:
            # Recovery after a restart: what was generated (if any) + a quiet note.
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
            # Answer footer: each stack reads a different shape and we must
            # write BOTH so the footer survives a session reload
            # (the client used to write it live; now the worker writes it):
            #   · owl1 -> flat fields + model_details:{model,provider} + sources[]
            #   · owl2 -> meta object:{model,provider,context_limit,usage,sources,...}
            # It all comes from the engine's 'done' event (done_meta), which already has
            # model, provider, protocol, context_limit, usage and sources.
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
                # ── owl1 (flat fields read by chatboo_component_v2.js) ──
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
                # ── owl2 (meta object read by chatboo_app.js) ──
                'meta': _meta,
                'timestamp': stamp,
                **({'files': _assistant_files} if _assistant_files else {}),
                **({'clip_data': _clip_data} if _clip_data else {}),
            })

        session.set_messages(messages)
        # Save the reuse anchor only when there is a new successful
        # code (normal turn). On recovery/errors it comes as None and the
        # last good query's one is kept.
        if query_code:
            try:
                session.write({'last_query_code': query_code})
            except Exception:
                _logger.debug(
                    "Chatboo async: could not save last_query_code (session %s)",
                    session.id, exc_info=True,
                )
        # Level 2: cache the dataset (rows) with its timestamp so it expires
        # by age. query_data is None except in a normal turn with data.
        # A turn that answered with no rows (report, prose) drops the cache:
        # otherwise the next "reformat" brings back the table of an older topic.
        # Error, cancel and reclaim do not pass drop_query_cache: it is kept.
        if query_data is not None:
            try:
                session.write({
                    'last_query_data': json.dumps(query_data, default=str, ensure_ascii=False),
                    'last_query_data_date': fields.Datetime.now(),
                    'last_query_company_ids': json.dumps(self._turn_company_ids()),
                })
            except Exception:
                _logger.debug(
                    "Chatboo async: could not save last_query_data (session %s)",
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
                    "Chatboo async: could not drop last_query_data (session %s)",
                    session.id, exc_info=True,
                )
        # Sticky skill: save the state the engine emitted. code with a
        # value → set/update; code=None → drop; sentinel → leave alone.
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
                    "Chatboo async: could not save active_skill (session %s)",
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
                    "Chatboo async: could not save last_domain_codes "
                    "(session %s)",
                    session.id, exc_info=True,
                )
        session.update_last_used()
        # Return the saved chips of the user turn (pictures with a /web/image
        # URL and files with a /web/content URL). The client uses them to
        # PATCH in place the bubble just sent, which still showed the
        # base64 (pictures) and the files with no URL (not clickable). So they
        # open in a tab without waiting for a session reload.
        result = {
            'user_images': _user_images or [],
            'user_files': _user_files or [],
            'assistant_files': _assistant_files or [],
        }
        if _assistant_content is not None:
            result['assistant_content'] = _assistant_content
        return result

    # ──────────────────────────── Read (tail / poll) ────────────────────────────

    def mark_seen(self):
        """Mark the job as delivered to a client (avoids delivering it again by poll)."""
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
        """Closed before it started: the notice stays as the turn's answer."""
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

    # ──────────────────────────── Maintenance (cron) ────────────────────────────

    def _reclaim_one(self, timeout_ms):
        """Instead of marking it as a red error, we RECOVER what was
        generated (``partial``) and save it in the session as an incomplete
        answer, closing the job as 'done' and notifying as info. So the
        answer survives the restart. Path ``reclaim=True``: no saving of
        base64 again.
        """
        partial = self.partial or ''
        never_started = self.state == 'pending' and not partial
        _logger.warning(
            "Chatboo async: reclaiming stuck job %s (%s), recovering %s chars",
            self.id, self.state, len(partial),
        )
        # Close the state RIGHT NOW inside the savepoint; if the save to
        # the session fails/times out, the SQL fallback leaves the job done.
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
        """Cron entry point: reclaims stuck jobs and purges old ones.

        Public because the cron calls it by name; it deletes everyone's old
        sessions, so only the system runs it.
        """
        if not (self.env.su or self.env.user._is_system()):
            raise AccessError(_('Only the system runs Chatboo maintenance.'))
        jobs = (self, self.env['chatboo.canvas.job'])
        for model in jobs:
            try:
                model._reclaim_stuck()
            except Exception:
                _logger.exception("Chatboo jobs: cron reclaim failed (%s)", model._name)
        # Release locks before the GC: a slow reclaim must not hold the
        # ir.cron "busy" while it purges (other workers skipped it forever).
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
        # Level 2: purge stale cached datasets (by age) so they
        # do not pile up in long-lived sessions. Must not bring the cron down.
        try:
            self.env['chatboo.session']._gc_stale_query_data()
        except Exception:
            _logger.debug("Chatboo async: _gc_stale_query_data failed", exc_info=True)
        self.env['chatboo.session']._cleanup_old_sessions()

    # ──────────────────────────── Bus ────────────────────────────

    def _notify(self, action):
        """Notify the user over the bus. Works on Odoo 14 and 17+.

        The front end (component + systray) already understands ``pns_chatboo_sync`` with
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
