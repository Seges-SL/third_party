# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""PNS AI Chatboo - Session. PATANEGRA Soft (https://patanegra.com).

Part of Patanegra Soft Suite (`pns_suite`), distributed via Patanegra Soft Hub.
Session persistence (message and prompt history) for the chat that consumes the
Patanegra Application Agent Protocol (PAAP).
Licensed under the Apache License 2.0 - see LICENSE.
"""

import json
import logging
import re
import uuid
from datetime import timedelta

from odoo import models, fields, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

# Parámetro de retención (días). Propio de Chatboo (antes vivía en pns_ai_mcp).
RETENTION_PARAM = 'pns_ai_chatboo.history_retention_days'

# Frescura (horas) del dataset cacheado para reutilización (Nivel 2). Un dataset
# solo es útil para reformateos INMEDIATOS del mismo listado; pasado este umbral
# se descarta (y un cron lo purga) para que los blobs no se acumulen en sesiones
# de larga vida, independientemente de la retención de la sesión.
QUERY_DATA_TTL_HOURS_PARAM = 'pns_ai_chatboo.query_data_ttl_hours'
DEFAULT_QUERY_DATA_TTL_HOURS = 12


class ChatbooSession(models.Model):
    """Sesión de Chatboo: historial de mensajes y de prompts (readline) por usuario."""
    _name = 'chatboo.session'
    _description = 'Chatboo Session'
    _order = 'last_used_date desc, create_date desc'
    _rec_name = 'name'

    name = fields.Char(
        string='Session Name',
        required=True,
        default=lambda self: _("Session %s") % self.format_display_datetime(),
        help="Descriptive name to identify the session",
    )
    user_id = fields.Many2one(
        'res.users',
        string='User',
        required=True,
        default=lambda self: self.env.user,
        ondelete='cascade',
        index=True,
        help="Owner of the session",
    )
    messages = fields.Text(
        string='Messages',
        help="JSON with the full message history (role, content, timestamp, ...)",
    )
    input_history = fields.Text(
        string='Prompt History',
        help="JSON array with the user's prompt history (readline)",
    )
    conversation_id = fields.Char(
        string='Conversation ID',
        help="Conversation id kept across turns to preserve historical context",
    )
    last_used_date = fields.Datetime(
        string='Last Used',
        default=fields.Datetime.now,
        help="Date and time of the last use of this session",
    )
    last_screen_context = fields.Text(
        string='Last screen context (JSON)',
        help="Last Chatboo overlay screen (action_id, view_type, model).",
    )
    last_query_code = fields.Text(
        string='Last successful data query',
        help="Python code of the last relaxaicode call that produced "
             "data in this session. It is re-injected as a hint on the next "
             "turn so the model REUSES/adapts it for reformat/reorder "
             "follow-ups ('same list but…', 'sort by…') instead of "
             "re-deriving the query from scratch — the main source of "
             "turn-to-turn variability (see docs). Not shown to the user.",
    )
    last_query_data = fields.Text(
        string='Last dataset (cache)',
        help="JSON with the ROWS of the last successful data query in this "
             "session (size-capped). Re-injected as 'previous_result' into the "
             "next relaxaicode namespace so reformat/reorder follow-ups "
             "transform the SAME data server-side instead of re-querying — no "
             "extra tokens, mirroring a code-interpreter kernel. Auto-expired "
             "by age (see query_data_ttl_hours) and purged by cron. Never shown "
             "to the user.",
    )
    last_query_data_date = fields.Datetime(
        string='Dataset cache time',
        help="When last_query_data was cached; used to expire it (freshness "
             "TTL) so stale datasets are not reused nor kept forever.",
    )
    active_skill_code = fields.Char(
        string='Active skill',
        help="Code of the skill kept 'sticky' for this session. While set, a "
             "follow-up (natural language or `/<same code> args`) is judged by "
             "the AI: if it refines the same task, the skill re-runs with merged "
             "params; if it's a new topic, this is cleared. A bare `/<code>` "
             "(no args) starts fresh. Not shown to the user.",
    )
    active_skill_params = fields.Text(
        string='Active skill params',
        help="JSON with the current parameters of active_skill_code. The AI "
             "merges each refinement onto these (add/remove/change) so the "
             "conversation can rotate params over the previous state without a "
             "turn limit. Not shown to the user.",
    )
    staged_assistant_files = fields.Text(
        string='Staged assistant downloads',
        help="Temporary JSON list of download chips until the assistant "
             "message of the current turn is saved. Not shown to the user.",
    )
    @api.model
    def _default_presentation_show_mode(self):
        try:
            from ..utils.chatboo_product_icp import read_product_settings
            return read_product_settings(self.env)['default_show_mode']
        except Exception:
            return 'show-table'

    presentation_show_mode = fields.Char(
        string='Presentation show mode',
        default=_default_presentation_show_mode,
        help="Session showmode: show-table (table first) or show-chart (chart "
             "first). From Chatboo Settings at session start; updated by "
             "/show-table, /show-chart or phrasing. Suspended under painter-free. "
             "Not shown to the user; not an LLM selector.",
    )
    llm_formatting_mode = fields.Selection(
        selection=[
            ('report', 'Report'),
            ('table', 'Table'),
        ],
        string='LLM formatting mode',
        default=False,
        help="Deprecated leftover. Painter is one-shot per turn "
             "(/painter-local /painter-free); empty inherits the provider. "
             "Kept for schema compat and cleared automatically.",
    )

    @api.model
    def format_display_datetime(self, utc_dt=None):
        """Wall clock for Chatboo UI (user tz, else company, else UTC)."""
        from ..utils.chatboo_display_time import format_env_wallclock
        return format_env_wallclock(self.env, utc_dt)

    # -- Serialización --

    def get_messages(self):
        self.ensure_one()
        if not self.messages:
            return []
        try:
            return json.loads(self.messages)
        except (json.JSONDecodeError, TypeError) as e:
            _logger.error("Error deserializing messages of session %s: %s", self.id, e)
            return []

    def get_messages_for_chat(self):
        """Messages for the UI, with turn prompts filled from the MCP log.

        Old sessions stored the assistant without ``user_prompt``. The context
        modal then paired a stray user line (e.g. "hola") with the next
        expensive turn. ``ai.log.user_prompt`` is the prompt that actually
        opened that turn id.
        """
        self.ensure_one()
        return self._annotate_turn_user_prompts(self.get_messages())

    @staticmethod
    def _message_correlation_id(msg):
        if not isinstance(msg, dict):
            return ''
        meta = msg.get('meta') if isinstance(msg.get('meta'), dict) else {}
        return (
            (msg.get('correlation_id') or meta.get('correlation_id') or '')
            .strip()
        )

    @staticmethod
    def _message_user_prompt(msg):
        if not isinstance(msg, dict):
            return ''
        meta = msg.get('meta') if isinstance(msg.get('meta'), dict) else {}
        return (msg.get('user_prompt') or meta.get('user_prompt') or '').strip()

    def _annotate_turn_user_prompts(self, messages):
        if not messages:
            return messages
        missing = []
        for msg in messages:
            if not isinstance(msg, dict) or msg.get('role') != 'assistant':
                continue
            if self._message_user_prompt(msg):
                continue
            corr = self._message_correlation_id(msg)
            if corr:
                missing.append((msg, corr))
        if not missing or 'ai.log' not in self.env:
            return messages
        corr_ids = list({corr for _msg, corr in missing})
        try:
            logs = self.env['ai.log'].search([
                ('user_id', '=', self.env.user.id),
                ('correlation_id', 'in', corr_ids),
                ('user_prompt', '!=', False),
            ], order='id asc')
        except Exception:
            _logger.debug(
                'Chatboo: could not annotate user_prompt from ai.log',
                exc_info=True,
            )
            return messages
        by_corr = {}
        for log in logs:
            cid = (log.correlation_id or '').strip()
            prompt = (log.user_prompt or '').strip()
            if cid and prompt and cid not in by_corr:
                by_corr[cid] = prompt
        if not by_corr:
            return messages
        for msg, corr in missing:
            prompt = by_corr.get(corr)
            if not prompt:
                continue
            msg['user_prompt'] = prompt
            meta = msg.get('meta') if isinstance(msg.get('meta'), dict) else {}
            meta = dict(meta)
            meta['user_prompt'] = prompt
            msg['meta'] = meta
        return messages

    #: Datos del turno que escribe el worker y que un save del cliente no
    #: puede borrar: adjuntos, métricas de consumo y trazas del turno.
    _PRESERVED_ASSISTANT_KEYS = (
        'files',
        'usage',
        'context_limit',
        'model_details',
        'sources',
        'records',
        'speed_tps',
        'prompt_speed_tps',
        'backend_history',
        'original_content',
        'clip_data',
        'correlation_id',
        'local_ack',
        'user_prompt',
    )

    def _merge_attachment_chips(self, previous, incoming):
        """No dejar que un save del cliente borre lo ya persistido.

        El worker guarda chips ``{url,name}`` ligados a ``ir.attachment`` y las
        métricas del turno (usage, tope de contexto, velocidad). El cliente a
        veces re-guarda el array de mensajes sin esas claves y pisaba el
        histórico: tras F5 / History las fotos «desaparecían» aunque el
        filestore siguiera intacto, y los chips de tokens y coste se quedaban
        en blanco aunque el consumo estuviera facturado.
        """
        if not previous or not incoming:
            return incoming
        prev_user = [
            m for m in previous
            if isinstance(m, dict) and m.get('role') == 'user'
        ]
        prev_assistant = [
            m for m in previous
            if isinstance(m, dict) and m.get('role') == 'assistant'
        ]
        ui = 0
        ai = 0
        for msg in incoming:
            if not isinstance(msg, dict):
                continue
            if msg.get('role') == 'user':
                if ui < len(prev_user):
                    prev = prev_user[ui]
                    if not msg.get('images') and prev.get('images'):
                        msg['images'] = prev['images']
                    if not msg.get('files') and prev.get('files'):
                        msg['files'] = prev['files']
                    if prev.get('offtopic') and not msg.get('offtopic'):
                        msg['offtopic'] = True
                # Si ya hay chips persistidos, no guardar base64/HTML de burbuja en
                # content (hincha el JSON y confunde al render del histórico).
                chips = msg.get('images') or msg.get('files')
                content = msg.get('content') or ''
                if chips and isinstance(content, str) and (
                    'data:image' in content
                    or '<img' in content
                    or 'o_chatboo_file_chip' in content
                    or 'o_chatboo_file_banner' in content
                ):
                    plain = re.sub(r'<[^>]+>', ' ', content)
                    plain = re.sub(r'data:image[^\s"\']+', ' ', plain)
                    plain = re.sub(r'\s+', ' ', plain).strip()
                    msg['content'] = plain
                ui += 1
            elif msg.get('role') == 'assistant':
                if ai < len(prev_assistant):
                    prev = prev_assistant[ai]
                    for key in self._PRESERVED_ASSISTANT_KEYS:
                        if not msg.get(key) and prev.get(key):
                            msg[key] = prev[key]
                    msg['meta'] = self._merge_meta(prev.get('meta'), msg.get('meta'))
                    if not msg['meta']:
                        msg.pop('meta', None)
                ai += 1
        return incoming

    def _merge_meta(self, prev_meta, new_meta):
        """Completar el ``meta`` entrante con lo que ya había (sin pisarlo)."""
        if not isinstance(prev_meta, dict):
            return new_meta if isinstance(new_meta, dict) else new_meta or None
        if not isinstance(new_meta, dict):
            return dict(prev_meta)
        merged = dict(prev_meta)
        for key, value in new_meta.items():
            if value not in (None, '', {}, []):
                merged[key] = value
        return merged

    def stage_assistant_download_chips(self, chips):
        """Accumulate download chips until the assistant message is saved."""
        self.ensure_one()
        if not chips:
            return
        existing = []
        if self.staged_assistant_files:
            try:
                existing = json.loads(self.staged_assistant_files) or []
            except (json.JSONDecodeError, TypeError):
                existing = []
        existing.extend(chips)
        self.staged_assistant_files = json.dumps(
            existing, default=str, ensure_ascii=False,
        )

    def consume_staged_assistant_download_chips(self):
        """Return staged download chips and clear the buffer."""
        self.ensure_one()
        # Staging may be committed by execute_safe_plan in another cursor while
        # this worker still holds a stale ORM snapshot of the session row.
        self.env.cr.execute(
            'SELECT staged_assistant_files FROM chatboo_session WHERE id = %s',
            (self.id,),
        )
        row = self.env.cr.fetchone()
        raw = row[0] if row else None
        if not raw:
            return []
        try:
            chips = json.loads(raw) or []
        except (json.JSONDecodeError, TypeError):
            chips = []
        self.write({'staged_assistant_files': False})
        try:
            self.invalidate_recordset(['staged_assistant_files'])
        except AttributeError:
            try:
                self.invalidate_cache(['staged_assistant_files'], self.ids)
            except Exception:
                pass
        return chips

    def apply_assistant_download_chips(self, chips):
        """Append download chips to the last assistant message or stage them."""
        self.ensure_one()
        if not chips:
            return
        messages = self.get_messages()
        if messages and messages[-1].get('role') == 'assistant':
            existing = list(messages[-1].get('files') or [])
            messages[-1]['files'] = existing + list(chips)
            self.set_messages(messages)
        else:
            self.stage_assistant_download_chips(chips)

    def fulfill_client_export(self, filename, mimetype, datas, kind=None):
        """Replace a pending Word/PDF/HTML chip with client-assembled bytes."""
        self.ensure_one()
        import base64
        raw = base64.b64decode(datas or b'')
        if not raw:
            return False
        name = (filename or 'export')[:255]
        kind = (kind or '').strip().lower()
        try:
            from odoo.addons.pns_ai_mcp.utils.session_download import (
                persist_chatboo_session_file,
                notify_chatboo_session_files_updated,
            )
        except ImportError:
            return False
        chip = persist_chatboo_session_file(
            self.env, self.id, raw, name, mimetype=mimetype,
        )
        if not chip:
            return False
        messages = self.get_messages()
        patched = False
        for msg in reversed(messages or []):
            if not isinstance(msg, dict) or msg.get('role') != 'assistant':
                continue
            files = list(msg.get('files') or [])
            for idx, item in enumerate(files):
                if not isinstance(item, dict) or not item.get('pending'):
                    continue
                same_name = item.get('name') == name
                same_kind = bool(kind) and item.get('fulfill') == kind
                if not (same_name or same_kind):
                    continue
                merged = dict(item)
                merged.update(chip)
                merged['pending'] = False
                files[idx] = merged
                msg['files'] = files
                patched = True
                break
            if patched:
                break
        if patched:
            self.set_messages(messages)
        else:
            self.apply_assistant_download_chips([chip])
        try:
            notify_chatboo_session_files_updated(self.env, self.id)
        except Exception:
            pass
        return chip

    def recover_orphan_download_chips(self, messages=None, since=None):
        """Build download chips from session attachments not yet in message history."""
        self.ensure_one()
        messages = messages if messages is not None else self.get_messages()
        referenced = set()
        for msg in messages or []:
            for f in msg.get('files') or []:
                if isinstance(f, dict) and f.get('url'):
                    referenced.add(f['url'])
        domain = [
            ('res_model', '=', 'chatboo.session'),
            ('res_id', '=', self.id),
        ]
        if since:
            domain.append(('create_date', '>=', since))
        chips = []
        for att in self.env['ir.attachment'].sudo().search(domain, order='id asc'):
            token = att.access_token
            if not token:
                gen = getattr(att, 'generate_access_token', None)
                if callable(gen):
                    tokens = gen()
                    token = tokens[0] if tokens else None
                if not token:
                    token = str(uuid.uuid4())
                    att.write({'access_token': token})
            url = '/web/content/%s?access_token=%s' % (att.id, token)
            try:
                from odoo.addons.pns_ai_mcp.utils.session_download import (
                    content_download_url,
                )
                url = content_download_url(
                    att.id, token, att.name, att.mimetype,
                )
            except Exception:
                pass
            if url in referenced:
                continue
            chips.append({
                'name': att.name or 'download',
                'url': url,
                'mimetype': (att.mimetype or 'application/octet-stream').split(';', 1)[0].strip(),
                'size': att.file_size or 0,
                'source': 'download',
            })
        return chips

    def append_local_ack(self, text):
        """Append a Chatboo-local note (no LLM turn). Empty text is a no-op."""
        self.ensure_one()
        body = (text or '').strip()
        if not body:
            return False
        messages = self.get_messages()
        last = messages[-1] if messages else None
        if (
            isinstance(last, dict)
            and last.get('local_ack')
            and (last.get('content') or '').strip() == body
        ):
            return False
        messages.append({
            'role': 'assistant',
            'content': body,
            'timestamp': self.format_display_datetime(),
            'local_ack': True,
            'offtopic': True,
            'meta': {
                'model': 'Chatboo',
                'provider': 'local',
                'local_ack': True,
            },
        })
        self.set_messages(messages)
        self.last_used_date = fields.Datetime.now()
        return True

    def set_messages(self, messages_list):
        self.ensure_one()
        if not messages_list:
            self.messages = None
            return
        try:
            def clean_obj(obj):
                if isinstance(obj, str):
                    return obj.replace('\x00', '')
                if isinstance(obj, dict):
                    return {k: clean_obj(v) for k, v in obj.items()}
                if isinstance(obj, list):
                    return [clean_obj(i) for i in obj]
                return obj

            safe_list = clean_obj(messages_list)
            previous = self.get_messages()
            if previous:
                safe_list = self._merge_attachment_chips(previous, safe_list)
            self.messages = json.dumps(safe_list, default=str, ensure_ascii=False)
        except (TypeError, ValueError) as e:
            _logger.error("Error serializing messages for session %s: %s", self.id, e)
            raise UserError("Error saving messages: %s" % e)

    def get_input_history(self):
        self.ensure_one()
        if not self.input_history:
            return []
        try:
            return json.loads(self.input_history)
        except (json.JSONDecodeError, TypeError) as e:
            _logger.error("Error deserializing prompt history of session %s: %s", self.id, e)
            return []

    def set_input_history(self, history_list):
        self.ensure_one()
        if not history_list:
            self.input_history = None
            return
        try:
            def clean_obj(obj):
                if isinstance(obj, str):
                    return obj.replace('\x00', '')
                if isinstance(obj, list):
                    return [clean_obj(i) for i in obj]
                return obj

            safe_history = clean_obj(history_list)
            limited_history = safe_history[-50:] if len(safe_history) > 50 else safe_history
            self.input_history = json.dumps(limited_history, ensure_ascii=False)
        except (TypeError, ValueError) as e:
            _logger.error("Error serializing prompt history for session %s: %s", self.id, e)
            raise UserError("Error saving history: %s" % e)

    def update_last_used(self):
        self.ensure_one()
        self.last_used_date = fields.Datetime.now()

    # -- Cache de dataset (Nivel 2: reutilización sin re-consultar) --

    @api.model
    def _query_data_ttl_hours(self):
        try:
            return int(self.env['ir.config_parameter'].sudo().get_param(
                QUERY_DATA_TTL_HOURS_PARAM, DEFAULT_QUERY_DATA_TTL_HOURS))
        except Exception:
            return DEFAULT_QUERY_DATA_TTL_HOURS

    def get_fresh_query_data(self):
        """Devuelve las filas cacheadas del último dataset SOLO si siguen frescas
        (dentro del TTL); si no, None. Nunca lanza: ante cualquier problema
        devuelve None y se cae con elegancia a "sin cache"."""
        self.ensure_one()
        if not self.last_query_data or not self.last_query_data_date:
            return None
        ttl = self._query_data_ttl_hours()
        if ttl > 0:
            age = fields.Datetime.now() - self.last_query_data_date
            if age > timedelta(hours=ttl):
                return None
        try:
            return json.loads(self.last_query_data)
        except (json.JSONDecodeError, TypeError):
            return None

    @api.model
    def _gc_stale_query_data(self):
        """Purga los datasets cacheados más antiguos que el TTL de frescura, para
        que los blobs no se queden acumulados en sesiones de larga vida (aparte
        de la retención de la sesión). Robusto: no falla el cron si algo va mal."""
        ttl = self._query_data_ttl_hours()
        if ttl <= 0:
            return
        try:
            cutoff = fields.Datetime.now() - timedelta(hours=ttl)
            stale = self.search([
                ('last_query_data', '!=', False),
                ('last_query_data_date', '<', cutoff),
            ])
            if stale:
                stale.write({'last_query_data': False, 'last_query_data_date': False})
                _logger.info("Chatboo: purgados %s dataset(s) cacheados obsoletos", len(stale))
        except Exception as e:
            _logger.warning("Chatboo: fallo purgando datasets cacheados: %s", e)

    @api.model
    def get_user_sessions(self, limit=50):
        self._cleanup_old_sessions()
        return self.search(
            [('user_id', '=', self.env.user.id)],
            limit=limit, order='last_used_date desc, create_date desc',
        )

    # -- Skill capture from chat (/create-skill) --

    @staticmethod
    def _slugify_skill_code(text):
        text = (text or '').strip().lower()
        text = re.sub(r'[^a-z0-9]+', '-', text)
        return text.strip('-')[:48] or 'captured-skill'

    @classmethod
    def _looks_like_probe_code(cls, code):
        """Heuristic: short relaxaicode snippets used for schema/probe turns."""
        body = (code or '').strip()
        if not body:
            return True
        if len(body) > 400:
            return False
        lowered = body.lower()
        if '__return_direct__' in lowered or '__direct_return__' in lowered:
            return True
        if 'api_call' in lowered and len(body) < 220:
            return True
        return False

    @classmethod
    def _code_has_hardcoded_rows(cls, code):
        """Detect pasted result rows (static list of dicts), not live fetches."""
        from odoo.addons.pns_ai_mcp.utils.skill_live_code import (
            code_has_frozen_result_rows,
        )
        return code_has_frozen_result_rows(code)

    @classmethod
    def _pick_capture_code(cls, session_code, source_log):
        """Choose the best relaxaicode snippet for skill capture."""
        candidates = []
        sc = (session_code or '').strip()
        if sc:
            candidates.append(sc)
        if source_log and source_log.code_to_execute:
            lc = source_log.code_to_execute.strip()
            if lc and lc not in candidates:
                candidates.append(lc)
        if not candidates:
            return ''
        best = candidates[0]
        best_score = -9999
        for code in candidates:
            score = 0
            if cls._looks_like_probe_code(code):
                score -= 90
            if cls._code_has_hardcoded_rows(code):
                score -= 60
            else:
                score += 40
            if 'api_call' in code:
                score += 20
            if any(tok in code for tok in (
                'previous_result', 'get_safe_plan_steps', 'formatted_text',
            )):
                score += 30
            score += min(len(code) // 120, 25)
            if score > best_score:
                best_score = score
                best = code
        return best

    @classmethod
    def _score_relaxaicode_log(cls, log, session_code):
        code = (log.code_to_execute or '').strip()
        if not code:
            return -999
        score = 0
        session_code = (session_code or '').strip()
        if session_code and code == session_code:
            score += 120
        if cls._looks_like_probe_code(code):
            score -= 90
        if cls._code_has_hardcoded_rows(code):
            score -= 35
        if any(tok in code for tok in (
            'previous_result', 'get_safe_plan_steps', 'formatted_text',
        )):
            score += 30
        summary = (log.result_summary or '').lower()
        if summary.startswith('error') or 'traceback' in summary:
            score -= 80
        score += min(len(code) // 120, 25)
        return score

    def _find_best_capture_log(self, session_code):
        Log = self.env['ai.log']
        logs = Log.search([
            ('user_id', '=', self.user_id.id),
            ('origin', '=', 'chatboo'),
            ('endpoint', '=', 'relaxaicode'),
            ('code_to_execute', '!=', False),
        ], limit=80, order='timestamp desc, id desc')
        best = Log.browse()
        best_score = -9999
        for log in logs:
            score = self._score_relaxaicode_log(log, session_code)
            if score > best_score:
                best_score = score
                best = log
        return best if best_score > 0 else Log.browse()

    @staticmethod
    def _normalize_turn_id(turn_id):
        """4-char MCP correlation id. Accepts ``VWVN`` or a step like ``VWVN-3``."""
        raw = (turn_id or '').strip()
        if not raw:
            return ''
        raw = re.sub(r'-\d+$', '', raw).strip()
        if not re.fullmatch(r'[A-Za-z0-9]{4}', raw):
            return ''
        return raw.upper()

    def _find_best_capture_log_for_turn(self, corr_id):
        """Best own ``ai.log`` of a turn (any session), preferring relaxaicode."""
        Log = self.env['ai.log']
        logs = Log.search([
            ('user_id', '=', self.env.user.id),
            ('correlation_id', '=ilike', corr_id),
            ('code_to_execute', '!=', False),
        ], limit=80, order='timestamp desc, id desc')
        if not logs:
            return Log.browse()
        best = logs[0]
        best_score = -9999
        for log in logs:
            score = self._score_relaxaicode_log(log, '')
            if (log.endpoint or '') == 'relaxaicode':
                score += 40
            if score > best_score:
                best_score = score
                best = log
        return best

    @api.model
    def compose_capture_code(self, code_body, corr):
        """Wrap a painter snippet with the turn fetch plan, if any.

        Returns ``(code, note)``. The note is a user-facing warning or None.
        Safe to call again: already-wrapped code is left unchanged.
        """
        from odoo.addons.pns_ai_chatboo.utils.skill_capture_compose import (
            code_needs_prior_plan,
            sanitize_fetch_steps,
            wrap_presentation_with_turn_fetch,
        )
        body = code_body or ''
        if not code_needs_prior_plan(body):
            return body, None
        turn = self._normalize_turn_id(corr) or (corr or '').strip().upper()
        fetch_steps = self._fetch_steps_for_turn(turn) if turn else []
        clean_steps = sanitize_fetch_steps(fetch_steps)
        if clean_steps:
            return wrap_presentation_with_turn_fetch(body, clean_steps), _(
                'This skill will replay the turn fetch '
                '(auto-confirmable api_call / fetch_url), then the '
                'captured painter.'
            )
        return body, _(
            'The captured painter reads previous_result. The source '
            'turn had no auto-confirmable fetch plan, so the slash '
            'will paint empty until propose_steps are added.'
        )

    def _fetch_steps_for_turn(self, corr):
        """Auto-confirmable ``plan_steps`` stored for this MCP turn, if any."""
        from odoo.addons.pns_ai_chatboo.utils.skill_capture_compose import (
            plan_steps_from_operation_data,
            sanitize_fetch_steps,
        )
        domain = [
            ('correlation_id', '=ilike', corr),
            ('user_id', '=', self.env.user.id),
        ]
        ops = self.env['ai.safe.operation'].sudo().search(
            domain, order='id desc', limit=20,
        )
        for op in ops:
            raw = {}
            try:
                raw = op.get_operation_data() or {}
            except Exception:
                raw = op.operation_data
            clean = sanitize_fetch_steps(plan_steps_from_operation_data(raw))
            if clean:
                return clean
        logs = self.env['ai.log'].sudo().search([
            ('user_id', '=', self.env.user.id),
            ('correlation_id', '=ilike', corr),
        ], order='id desc', limit=40)
        for log in logs:
            for blob in (log.result_data, log.additional_info, log.prompt_data):
                clean = sanitize_fetch_steps(
                    plan_steps_from_operation_data(blob),
                )
                if clean:
                    return clean
        return []

    def _last_user_prompt_text(self):
        for msg in reversed(self.get_messages() or []):
            if isinstance(msg, dict) and msg.get('role') == 'user':
                raw = (msg.get('raw') or msg.get('content') or '').strip()
                if raw:
                    return re.sub(r'<[^>]+>', '', raw).strip()
        return ''

    def _default_capture_procedure(self, has_hardcoded_rows=False):
        lines = [
            _("When to use: describe the user request this skill answers."),
            _("Parameters: list the user-facing parameters (e.g. period, employee)."),
            _("Output: explain how to present the result."),
            _(
                "The Code must fetch live data on each run (api_call / "
                "relaxaicode). Do NOT rely on cached session rows "
                "(last_query_data) or pasted row literals."
            ),
            _("Run the captured Code with relaxaicode; do not recompute its logic."),
        ]
        if has_hardcoded_rows:
            lines.insert(
                4,
                _(
                    "WARNING: the captured Code may contain hardcoded row "
                    "literals from a one-off answer. Replace them with live "
                    "api_call fetches before publishing."
                ),
            )
        return '\n'.join(lines)

    def prepare_skill_capture_action(self, skill_code_hint=None, turn_id=None):
        """Open the skill capture wizard pre-filled from a turn.

        Captures query *logic* (relaxaicode log for ``turn_id``), never the
        session row cache (``last_query_data``).

        ``turn_id`` is required: the 4-char MCP ``correlation_id`` of a log
        owned by the current user. The slash name is formatted with the
        instance prefixes from Settings.
        """
        self.ensure_one()
        if self.user_id.id != self.env.user.id:
            raise UserError(_('Access denied to this session.'))
        if not self.env.user.has_group('pns_ai_mcp.group_ai_writer'):
            raise UserError(_(
                'AI Writer permission is required to create skills from Chatboo.'
            ))

        name_hint = (skill_code_hint or '').strip() or None
        raw_turn = (turn_id or '').strip()
        corr = self._normalize_turn_id(raw_turn)
        if not corr:
            raise UserError(_(
                'Turn id is required. Use /create-skill VWVN slash-name '
                '(4-character code from the chip).'
            ))

        source_log = self._find_best_capture_log_for_turn(corr)
        if not source_log:
            raise UserError(_(
                'No MCP log found for turn %s (or it is not yours).'
            ) % corr)
        code_body = self._pick_capture_code(
            source_log.code_to_execute, source_log,
        )
        if not code_body:
            raise UserError(_(
                'No capturable query code found for turn %s.'
            ) % corr)
        code_body, fetch_wrap_note = self.compose_capture_code(code_body, corr)
        user_prompt = (source_log.user_prompt or '').strip()

        if name_hint:
            from odoo.addons.pns_ai_mcp.utils.skill_code_prefix import (
                get_skill_code_prefix,
                get_skill_command_prefix,
                instance_identity,
                slash_slug,
            )
            slug = slash_slug(name_hint)
            _code, command = instance_identity(
                slug,
                get_skill_code_prefix(self.env),
                get_skill_command_prefix(self.env),
            )
            skill_code = command
            skill_name = name_hint.strip()[:48]
        else:
            skill_code = ''
            skill_name = ''

        description = (user_prompt or name_hint or '')[:120]
        has_hardcoded = self._code_has_hardcoded_rows(code_body)
        procedure = self._default_capture_procedure(has_hardcoded)
        if fetch_wrap_note:
            procedure = '%s\n%s' % (procedure, fetch_wrap_note)

        warning = None
        notes = []
        if has_hardcoded:
            notes.append(_(
                'The captured code contains pasted row literals (e.g. data = [{...}, ...]). '
                'Replace that block with live api_call fetches before publishing the skill.'
            ))
        if fetch_wrap_note:
            notes.append(fetch_wrap_note)
        if notes:
            warning = '\n'.join(notes)

        ctx = {
            'form_view_initial_mode': 'edit',
            'capture_from_chatboo': True,
            'default_source_log_id': source_log.id if source_log else False,
            'default_skill_code': skill_code,
            'default_skill_name': skill_name,
            'default_description': description,
            'default_procedure': procedure,
            'default_code_body': code_body,
            'default_from_chatboo': True,
            'default_warn_hardcoded_rows': has_hardcoded,
            'chatboo_session_id': self.id,
            'default_chatboo_session_id': self.id,
        }
        chatboo_agent = self.env['ai.agent'].search(
            [('code', '=', 'pns_ai_chatboo')], limit=1,
        )
        if chatboo_agent:
            ctx['default_agent_ids'] = [(6, 0, chatboo_agent.ids)]

        action = {
            'type': 'ir.actions.act_window',
            'name': _('Capture skill from chat'),
            'res_model': 'pns_ai_mcp.skill.capture.wizard',
            'view_mode': 'form',
            'views': [[False, 'form']],
            'target': 'new',
            'context': ctx,
        }
        return action, warning

    @api.model_create_multi
    def create(self, vals_list):
        self._cleanup_old_sessions()
        return super().create(vals_list)

    def unlink(self):
        """Borra en cascada los adjuntos del chat al eliminar la sesión.

        Las imágenes/ficheros del chat se guardan como ``ir.attachment`` con
        ``res_model='chatboo.session'`` / ``res_id=<sesión>``. Odoo NO los borra
        solo por esa relación (no es una FK), así que al eliminar el histórico
        los borramos aquí para no dejar blobs huérfanos. Robusto: un fallo
        borrando adjuntos no debe impedir eliminar la sesión.

        También pre-borra los ``chatboo.async.request`` ligados (el usuario no
        tiene ACL unlink ahí) con ``lock_timeout`` corto: si un cron/reclaim
        tiene un job zombie bloqueado, fallamos YA con mensaje claro en vez de
        dejar el History colgado (el spinner va en shadow y parece que «no borra»).
        """
        if self.ids:
            # 1) Jobs async primero (FK ON DELETE CASCADE también esperaría el
            #    mismo lock; así controlamos timeout y mensaje).
            try:
                self.env.cr.execute("SET LOCAL lock_timeout = '3s'")
            except Exception:
                pass
            try:
                jobs = self.env['chatboo.async.request'].sudo().search([
                    ('session_id', 'in', self.ids),
                ])
                if jobs:
                    jobs.unlink()
            except Exception as exc:
                msg = str(exc).lower()
                if 'lock' in msg or 'timeout' in msg or 'canceling statement' in msg:
                    raise UserError(_(
                        "Could not delete the session: a background Chatboo job "
                        "still locks related data. Wait a few seconds, or restart "
                        "the Odoo service, then try again."
                    )) from exc
                _logger.warning(
                    "Chatboo: no se pudieron borrar async jobs de sesiones %s: %s",
                    self.ids, exc, exc_info=True,
                )
                # Si no es lock, seguimos: el CASCADE de BD puede bastar.
            finally:
                try:
                    self.env.cr.execute("SET LOCAL lock_timeout = DEFAULT")
                except Exception:
                    pass

            try:
                atts = self.env['ir.attachment'].sudo().search([
                    ('res_model', '=', 'chatboo.session'),
                    ('res_id', 'in', self.ids),
                ])
                if atts:
                    atts.unlink()
            except Exception:
                _logger.warning(
                    "Chatboo: no se pudieron borrar los adjuntos de las sesiones %s",
                    self.ids, exc_info=True,
                )
        try:
            self.env.cr.execute("SET LOCAL lock_timeout = '3s'")
        except Exception:
            pass
        try:
            return super().unlink()
        except Exception as exc:
            msg = str(exc).lower()
            if 'lock' in msg or 'timeout' in msg or 'canceling statement' in msg:
                raise UserError(_(
                    "Could not delete the session: a background Chatboo job "
                    "still locks related data. Wait a few seconds, or restart "
                    "the Odoo service, then try again."
                )) from exc
            raise
        finally:
            try:
                self.env.cr.execute("SET LOCAL lock_timeout = DEFAULT")
            except Exception:
                pass

    @api.model
    def _cleanup_old_sessions(self):
        """Delete the current user's sessions older than the configured retention."""
        try:
            retention_days = int(self.env['ir.config_parameter'].sudo().get_param(RETENTION_PARAM, 30))
            if retention_days <= 0:
                return
            cutoff_date = fields.Datetime.now() - timedelta(days=retention_days)
            old_sessions = self.search([
                ('user_id', '=', self.env.user.id),
                ('last_used_date', '<', cutoff_date),
            ])
            if old_sessions:
                _logger.info(
                    "Cleaning %s old Chatboo sessions for user %s",
                    len(old_sessions), self.env.user.name,
                )
                old_sessions.unlink()
        except Exception as e:
            _logger.error("Error cleaning old sessions: %s", e)
