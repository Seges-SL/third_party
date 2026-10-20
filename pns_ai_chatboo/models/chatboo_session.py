# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""chatboo.session — conversation persistence (messages and prompt history)."""

import json
import logging
import re
from datetime import timedelta

from odoo import models, fields, api, _
from odoo.exceptions import UserError

from odoo.addons.pns_ai_mcp.utils import record_marks

from ..utils import turn_documents
from ..utils.chatboo_product_icp import (
    DEFAULT_HISTORY_RETENTION_DAYS,
    ICP_HISTORY_RETENTION_DAYS,
)

_logger = logging.getLogger(__name__)

# Parámetro de retención (días). Propio de Chatboo (antes vivía en pns_ai_mcp).
RETENTION_PARAM = ICP_HISTORY_RETENTION_DAYS

# Frescura (horas) del dataset cacheado para reutilización (Nivel 2). Un dataset
# solo es útil para reformateos INMEDIATOS del mismo listado; pasado este umbral
# se descarta (y un cron lo purga) para que los blobs no se acumulen en sesiones
# de larga vida, independientemente de la retención de la sesión.
QUERY_DATA_TTL_HOURS_PARAM = 'pns_ai_chatboo.query_data_ttl_hours'
DEFAULT_QUERY_DATA_TTL_HOURS = 12

_ATTACHMENT_ID_IN_URL = re.compile(
    r'/(?:web/content|web/image|pns_ai_mcp/session_file)/(\d+)')


class ChatbooSession(models.Model):
    """Sesión de Chatboo: historial de mensajes y de prompts (readline) por usuario."""
    _name = 'chatboo.session'
    _description = 'Chatboo Session'
    _order = 'last_used_date desc, create_date desc'
    _rec_name = 'name'
    _sandbox_helper_provider = True

    name = fields.Char(
        string='Session Name',
        required=True,
        default=lambda self: _("Session %s") % self.format_display_datetime(),
        help="Descriptive name to identify the session",
    )
    user_id = fields.Many2one(
        'res.users',
        string='User',
        default=lambda self: self.env.user,
        ondelete='set null',
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
    attached_documents = fields.Text(
        string='Attached documents (text)',
        copy=False,
        help="JSON with the text of the files the user attached in this "
             "session, page by page. Later turns get a short note and the "
             "model reads the part it needs with read_document. Not shown "
             "to the user.",
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
    last_domain_codes = fields.Text(
        string='Last domain packs',
        help="JSON object of domain pack codes injected last Chatboo turn "
             "and how many turns each has been on the table ({code: n}). "
             "A legacy JSON list is still read. The next turn unions them "
             "with this sentence's discovery hits. A skill invoke adds "
             "the skill's domain context packs when it has any. "
             "Slashes never clear the list. Cleared on a new session. "
             "Not shown to the user.",
    )
    pending_param_skill_id = fields.Many2one(
        'ai.skill',
        string='Pending parameter skill',
        ondelete='set null',
        help="Unused. Kept so existing databases keep the column. "
             "Parameter prose lives in the skill wizard.",
    )
    staged_assistant_files = fields.Text(
        string='Staged assistant downloads',
        help="Temporary JSON list of download chips until the assistant "
             "message of the current turn is saved. Not shown to the user.",
    )
    marked_refs = fields.Text(
        string='Marked records',
        help="JSON list of {model, id, label} for the rows the user ticked "
             "in the last answer. They travel with the next sentence so the "
             "model takes them as its subject instead of searching the name "
             "again. Spent by the turn that carries them. Not shown.",
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
             "/show-table, /show-chart or phrasing. Suspended under compose-model. "
             "Not shown to the user; not an LLM selector.",
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
    def _message_turn(msg):
        if not isinstance(msg, dict):
            return ''
        meta = msg.get('meta') if isinstance(msg.get('meta'), dict) else {}
        return (
            (msg.get('turn') or meta.get('turn') or '')
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
            turn = self._message_turn(msg)
            if turn:
                missing.append((msg, turn))
        if not missing or 'ai.log' not in self.env:
            return messages
        corr_ids = list({corr for _msg, corr in missing})
        try:
            logs = self.env['ai.log'].search([
                ('user_id', '=', self.env.user.id),
                ('turn', 'in', corr_ids),
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
            cid = (log.turn or '').strip()
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
        'turn',
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

    # Seges: parche 11 (PNS-82, seguridad). Ver docs/pendiente/parches_pns_ai.md
    def _stage_assistant_download_chips(self, chips):
        """Accumulate download chips until the assistant message is saved."""
        self.ensure_one()
        if not chips:
            return
        self._claim_turn_file_chips(chips)
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

    # Seges: parche 11 (PNS-82, seguridad). Ver docs/pendiente/parches_pns_ai.md
    def _consume_staged_assistant_download_chips(self):
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

    # Seges: parche 11 (PNS-82, seguridad). Ver docs/pendiente/parches_pns_ai.md
    def _apply_assistant_download_chips(self, chips):
        """Append download chips to the last assistant message or stage them."""
        self.ensure_one()
        if not chips:
            return
        self._claim_turn_file_chips(chips)
        messages = self.get_messages()
        if messages and messages[-1].get('role') == 'assistant':
            existing = list(messages[-1].get('files') or [])
            messages[-1]['files'] = existing + list(chips)
            self.set_messages(messages)
        else:
            # Seges: parche 11 (PNS-82, seguridad). Ver docs/pendiente/parches_pns_ai.md
            self._stage_assistant_download_chips(chips)

    # Seges: parche 11 (PNS-82, seguridad). Ver docs/pendiente/parches_pns_ai.md
    def _claim_turn_file_chips(self, chips):
        """Hang engine-created attachments on this session."""
        self.ensure_one()
        # Seges: parche 11 (PNS-82, seguridad). Ver docs/pendiente/parches_pns_ai.md
        uid = self.env.uid
        if self.sudo().user_id.id != uid:
            return
        Attachment = self.env['ir.attachment'].sudo()
        for chip in chips or []:
            if not isinstance(chip, dict):
                continue
            att_id = chip.get('attachment_id')
            if not att_id:
                url = chip.get('url') or ''
                match = re.search(
                    r'/(?:web/content|pns_ai_mcp/session_file)/(\d+)',
                    url,
                )
                if match:
                    att_id = int(match.group(1))
            if not att_id:
                continue
            att = Attachment.browse(int(att_id))
            if not att.exists():
                continue
            if att.res_model and att.res_id:
                continue
            # Seges: parche 11 (PNS-82, seguridad). Ver docs/pendiente/parches_pns_ai.md
            if att.create_uid.id != uid:
                continue
            att.write({
                'res_model': self._name,
                'res_id': self.id,
            })

    def notify_files_updated(self):
        """Ask open Chatboo clients to reload this session's messages."""
        self.ensure_one()
        try:
            partner = self.user_id.partner_id
            if not partner:
                return
            payload = {
                'type': 'pns_chatboo_sync',
                'action': 'message_received',
                'session_id': self.id,
            }
            bus = self.env['bus.bus']
            sendone = getattr(bus, '_sendone', None)
            if sendone:
                sendone(partner, 'pns_chatboo_sync', payload)
                return
            import json as _json
            channel = (self.env.cr.dbname, 'res.partner', partner.id)
            legacy = getattr(bus, 'sendone', None)
            if legacy:
                legacy(channel, _json.dumps(payload, ensure_ascii=False))
        except Exception:
            _logger.debug(
                'Chatboo: could not notify session files update (session %s)',
                self.id, exc_info=True,
            )

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
                persist_turn_file,
            )
        except ImportError:
            return False
        chip = persist_turn_file(
            self.env, self.id, raw, name, mimetype=mimetype,
        )
        if not chip:
            return False
        # Seges: parche 11 (PNS-82, seguridad). Ver docs/pendiente/parches_pns_ai.md
        self._claim_turn_file_chips([chip])
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
            # Seges: parche 11 (PNS-82, seguridad). Ver docs/pendiente/parches_pns_ai.md
            self._apply_assistant_download_chips([chip])
        self.notify_files_updated()
        return chip

    def recover_orphan_download_chips(self, messages=None, since=None):
        """Build download chips from session attachments not yet in message history."""
        self.ensure_one()
        messages = messages if messages is not None else self.get_messages()
        from odoo.addons.pns_ai_mcp.utils.session_download import (
            content_download_url,
        )
        # Older history keeps token URLs: the attachment id is what matches.
        referenced = set()
        for msg in messages or []:
            for f in msg.get('files') or []:
                if isinstance(f, dict) and f.get('url'):
                    found = _ATTACHMENT_ID_IN_URL.search(f['url'])
                    if found:
                        referenced.add(int(found.group(1)))
        domain = [
            ('res_model', '=', 'chatboo.session'),
            ('res_id', '=', self.id),
        ]
        if since:
            domain.append(('create_date', '>=', since))
        chips = []
        for att in self.env['ir.attachment'].sudo().search(domain, order='id asc'):
            if att.id in referenced:
                continue
            chips.append({
                'name': att.name or 'download',
                'url': content_download_url(att.id, att.name, att.mimetype),
                'mimetype': (att.mimetype or 'application/octet-stream').split(';', 1)[0].strip(),
                'size': att.file_size or 0,
                'source': 'download',
            })
        return chips

    def append_local_ack(self, text, usage=None, provider_meta=None,
                         user_prompt=None):
        """Append a Chatboo-local note. ``usage`` is a light IA call, if any."""
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
        prompt = (user_prompt or '').strip()
        if prompt:
            prev_user = None
            for msg in reversed(messages):
                if isinstance(msg, dict) and msg.get('role') == 'user':
                    prev_user = msg
                    break
            if not (
                prev_user
                and (prev_user.get('content') or '').strip() == prompt
            ):
                messages.append({
                    'role': 'user',
                    'content': prompt,
                    'timestamp': self.format_display_datetime(),
                    'local_ack': True,
                    'offtopic': True,
                })
        chip = provider_meta if isinstance(provider_meta, dict) else {}
        usage = usage if isinstance(usage, dict) else {}
        meta = {
            'model': (chip.get('model') or '').strip() or 'Chatboo',
            'provider': (chip.get('provider') or '').strip() or 'local',
            'local_ack': True,
        }
        if usage:
            meta['usage'] = usage
        if prompt:
            meta['user_prompt'] = prompt
        msg = {
            'role': 'assistant',
            'content': body,
            'timestamp': self.format_display_datetime(),
            'local_ack': True,
            'offtopic': True,
            'meta': meta,
        }
        if usage:
            msg['usage'] = usage
        if prompt:
            msg['user_prompt'] = prompt
        messages.append(msg)
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

    def get_last_domain_payload(self):
        """Ages ``{code: n}`` when stored; otherwise the code list."""
        self.ensure_one()
        try:
            from odoo.addons.pns_ai_mcp.utils.domain_index import (
                parse_domain_ages,
                parse_domain_codes,
            )
            ages = parse_domain_ages(self.last_domain_codes)
            if ages:
                return ages
            return parse_domain_codes(self.last_domain_codes)
        except Exception:
            return []

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

    # ── Documentos adjuntos (texto, como las filas de una tabla) ──────────

    def get_documents(self):
        self.ensure_one()
        try:
            return turn_documents.clean(json.loads(self.attached_documents or '[]'))
        except (json.JSONDecodeError, TypeError):
            return []

    def remember_documents(self, documents):
        """Keep the text of this turn's files for the next turns."""
        self.ensure_one()
        if not documents:
            return
        kept = turn_documents.merge(self.get_documents(), documents)
        self.write({
            'attached_documents': json.dumps(kept, ensure_ascii=False) if kept else False,
        })

    @api.model
    def sandbox_helpers(self):
        """``read_document`` for the sandbox of a Chatboo turn."""
        sessions = self

        def read_document(name, page=None, find=None):
            return sessions._read_document(name, page=page, find=find)

        return {'read_document': read_document}

    @api.model
    def _read_document(self, name, page=None, find=None):
        session_id = self.env.context.get('chatboo_session_id')
        session = self.sudo().browse(int(session_id)).exists() if session_id else None
        if not session or session.user_id.id != self.env.uid:
            return turn_documents.read([], name)
        return turn_documents.read(session.get_documents(), name, page=page, find=find)

    # ── Registros marcados en la respuesta ────────────────────────────────
    # Marcar una fila es nombrar un registro sin deletrearlo. El motor solo
    # lee texto, así que la marca sale como frase junto al mensaje; estrechar
    # el dataset por sí solo dejaba al modelo libre para buscar el nombre.

    def get_marks(self):
        """Records the user ticked, as ``{model, id, label}``."""
        self.ensure_one()
        try:
            marks = json.loads(self.marked_refs or '[]')
        except (json.JSONDecodeError, TypeError):
            return []
        return marks if isinstance(marks, list) else []

    def remember_marks(self, refs):
        """Keep what the user pointed at. ``None`` leaves the marks alone."""
        self.ensure_one()
        if refs is None:
            return self.get_marks()
        marks = record_marks.clean_marks(refs)
        self.write({
            'marked_refs': json.dumps(marks, ensure_ascii=False) if marks else False,
        })
        return marks

    def forget_marks(self):
        """The tick belonged to the sentence it went out with: it is spent."""
        self.ensure_one()
        if self.marked_refs:
            self.write({'marked_refs': False})
        return True

    def marks_sentence(self):
        """The tick, said out loud for the engine. Empty when nothing is marked."""
        self.ensure_one()
        return record_marks.marks_sentence(self.get_marks())

    def narrow_query_data(self, rows):
        """The marked rows of the cached dataset, or all of them."""
        self.ensure_one()
        return record_marks.narrow_rows(self.get_marks(), rows)

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
        return self.search(
            [('user_id', '=', self.env.user.id)],
            limit=limit, order='last_used_date desc, create_date desc',
        )

    # -- Skill capture from chat (/create-skill) --

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
        from odoo.addons.pns_ai_chatboo.utils.skill_capture_compose import (
            score_capture_snippet,
        )
        best = candidates[0]
        best_score = -9999
        for code in candidates:
            score = score_capture_snippet(code)
            if cls._looks_like_probe_code(code):
                score -= 90
            if cls._code_has_hardcoded_rows(code):
                score -= 60
            else:
                score += 40
            if 'api_call' in code:
                score += 20
            if score > best_score:
                best_score = score
                best = code
        return best

    @classmethod
    def _score_relaxaicode_log(cls, log, session_code, relaxaicode_count=1):
        from odoo.addons.pns_ai_chatboo.utils.skill_capture_compose import (
            score_capture_snippet,
        )
        code = (log.code_to_execute or '').strip()
        if not code:
            return -999
        score = score_capture_snippet(code, relaxaicode_count=relaxaicode_count)
        session_code = (session_code or '').strip()
        if session_code and code == session_code:
            score += 120
        if cls._looks_like_probe_code(code):
            score -= 90
        if cls._code_has_hardcoded_rows(code):
            score -= 35
        summary = (log.result_summary or '').lower()
        if summary.startswith('error') or 'traceback' in summary:
            score -= 80
        return score

    @staticmethod
    def _normalize_turn_id(turn_id):
        """4-char MCP turn id. Accepts ``VWVN`` or a step like ``VWVN-3``."""
        raw = (turn_id or '').strip()
        if not raw:
            return ''
        raw = re.sub(r'-\d+$', '', raw).strip()
        if not re.fullmatch(r'[A-Za-z0-9]{4}', raw):
            return ''
        return raw.upper()

    def _relaxaicode_codes_for_turn(self, corr_id):
        """Substantive relaxaicode snippets for a turn, chronological order."""
        from odoo.addons.pns_ai_chatboo.utils.skill_capture_compose import (
            snippet_is_probe_code,
        )
        Log = self.env['ai.log'].sudo()
        logs = Log.search([
            ('user_id', '=', self.env.user.id),
            ('turn', '=ilike', corr_id),
            ('endpoint', '=', 'relaxaicode'),
            ('code_to_execute', '!=', False),
        ], order='id asc', limit=80)
        codes = []
        for log in logs:
            code = (log.code_to_execute or '').strip()
            if code and not snippet_is_probe_code(code):
                codes.append(code)
        return codes

    def _find_best_capture_log_for_turn(self, corr_id):
        """Best own ``ai.log`` of a turn (any session), preferring relaxaicode."""
        Log = self.env['ai.log']
        logs = Log.search([
            ('user_id', '=', self.env.user.id),
            ('turn', '=ilike', corr_id),
            ('code_to_execute', '!=', False),
        ], limit=80, order='timestamp desc, id desc')
        if not logs:
            return Log.browse()
        relaxaicode_count = len(self._relaxaicode_codes_for_turn(corr_id))
        best = logs[0]
        best_score = -9999
        for log in logs:
            score = self._score_relaxaicode_log(
                log, '', relaxaicode_count=relaxaicode_count,
            )
            if (log.endpoint or '') == 'relaxaicode':
                score += 40
            if score > best_score:
                best_score = score
                best = log
        return best

    def _catalog_slash_for_turn(self, corr_id):
        """Slash of a catalog-skill execution on this turn, or ``''``."""
        from odoo.addons.pns_ai_chatboo.utils.skill_capture_compose import (
            slash_from_skill_turn_logs,
        )
        logs = self.env['ai.log'].search([
            ('user_id', '=', self.env.user.id),
            ('turn', '=ilike', corr_id),
        ], limit=80, order='timestamp desc, id desc')
        return slash_from_skill_turn_logs(
            [(log.tool_name, log.prompt_data) for log in logs],
        )

    @api.model
    def compose_capture_code(self, code_body, corr):
        """Compose fetch + multi-phase relaxaicode into one capturable body.

        Returns ``(code, incomplete)``. Safe to call again on wizard edits.
        """
        from odoo.addons.pns_ai_chatboo.utils.skill_capture_compose import (
            capture_is_incomplete,
            compose_capture_pipeline,
        )
        turn = self._normalize_turn_id(corr) or (corr or '').strip().upper()
        relaxaicode_codes = (
            self._relaxaicode_codes_for_turn(turn) if turn else []
        )
        if not relaxaicode_codes and (code_body or '').strip():
            relaxaicode_codes = [(code_body or '').strip()]
        fetch_steps = self._fetch_steps_for_turn(turn) if turn else []
        composed, pipeline_incomplete = compose_capture_pipeline(
            relaxaicode_codes, fetch_steps,
        )
        if not composed:
            composed = code_body or ''
        incomplete = pipeline_incomplete or capture_is_incomplete(
            composed, fetch_steps,
        )
        return composed, incomplete

    def _fetch_steps_for_turn(self, corr):
        """Auto-confirmable fetch steps from every safe plan in this turn."""
        from odoo.addons.pns_ai_chatboo.utils.skill_capture_compose import (
            merge_fetch_steps,
            plan_steps_from_operation_data,
            sanitize_fetch_steps,
        )
        domain = [
            ('turn', '=ilike', corr),
            ('user_id', '=', self.env.user.id),
        ]
        ops = self.env['ai.safe.operation'].sudo().search(
            domain, order='id asc', limit=20,
        )
        step_lists = []
        for op in ops:
            raw = {}
            try:
                raw = op.get_operation_data() or {}
            except Exception:
                raw = op.operation_data
            steps = plan_steps_from_operation_data(raw)
            if steps:
                step_lists.append(steps)
        merged = merge_fetch_steps(step_lists)
        if merged:
            return merged
        logs = self.env['ai.log'].sudo().search([
            ('user_id', '=', self.env.user.id),
            ('turn', '=ilike', corr),
        ], order='id desc', limit=40)
        for log in logs:
            for blob in (log.result_data, log.additional_info, log.prompt_data):
                clean = sanitize_fetch_steps(
                    plan_steps_from_operation_data(blob),
                )
                if clean:
                    return clean
        return []

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

    def prepare_skill_capture_action(self, skill_code_hint=None, turn_id=None,
                                     param_prose=None):
        """Open the skill capture wizard pre-filled from a turn.

        If the turn already ran a catalog skill, prefills that record's
        Code/Procedure (no fetch wrap, no template). Otherwise captures
        query *logic* (relaxaicode log for ``turn_id``), never the
        session row cache (``last_query_data``).

        ``turn_id`` is required (the 4-character chip on the line).
        The slash name is formatted with the instance prefixes from Settings.
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
                'The turn chip is required: /create-skill VWVN slash-name'
            ))

        Skill = self.env['ai.skill']
        catalog_slash = self._catalog_slash_for_turn(corr)
        catalog_skill = Skill.browse()
        source_log = self.env['ai.log'].browse()
        user_prompt = ''
        param_schema = ''
        arg_hint = ''
        capture_incomplete = False

        if catalog_slash:
            catalog_skill = Skill._find_by_invoke_token(catalog_slash)
            if not catalog_skill:
                raise UserError(_(
                    'Turn %s ran /%s, but that skill is no longer '
                    'in the catalog.'
                ) % (corr, catalog_slash))
            code_body = (catalog_skill.code_body or '').strip()
            if not code_body:
                raise UserError(_(
                    'Skill /%s has no capturable Code.'
                ) % (catalog_skill.invoke_code() or catalog_slash))
            param_schema = catalog_skill.param_schema or ''
            arg_hint = catalog_skill.arg_hint or ''
        else:
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
            code_body, capture_incomplete = self.compose_capture_code(
                code_body, corr,
            )
            user_prompt = (source_log.user_prompt or '').strip()

        if code_body:
            from odoo.addons.pns_ai_mcp.utils.skill_runtime import (
                fill_capture_params,
            )
            param_schema, arg_hint = fill_capture_params(
                code_body, param_schema, arg_hint,
            )

        existing_skill = Skill.browse()
        if name_hint:
            _code, command, existing_skill = (
                Skill.resolve_capture_identity(name_hint)
            )
            skill_code = command
            skill_name = name_hint.strip()[:48]
        elif catalog_skill:
            token = catalog_skill.invoke_code() or catalog_slash
            _code, command, existing_skill = (
                Skill.resolve_capture_identity(token)
            )
            skill_code = command
            skill_name = (catalog_skill.name or token)[:48]
        else:
            skill_code = ''
            skill_name = ''

        description = (
            (catalog_skill.description if catalog_skill else '')
            or user_prompt
            or name_hint
            or ''
        )[:120]
        has_hardcoded = self._code_has_hardcoded_rows(code_body)
        if catalog_skill:
            procedure = (catalog_skill.content or '').strip() or (
                self._default_capture_procedure(has_hardcoded)
            )
        else:
            procedure = self._default_capture_procedure(has_hardcoded)

        warning = None
        notes = []
        if catalog_skill:
            notes.append(_(
                'This turn ran /%s. The wizard has that skill\'s Code '
                'and Procedure (not a new query).'
            ) % (catalog_skill.invoke_code() or catalog_slash))
        if has_hardcoded:
            notes.append(_(
                'The captured code contains pasted row literals (e.g. data = [{...}, ...]). '
                'Replace that block with live api_call fetches before publishing the skill.'
            ))
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
            'default_param_schema': param_schema or False,
            'default_arg_hint': arg_hint or False,
            'default_args_policy': (
                (catalog_skill.args_policy if catalog_skill else 'default')
                or 'default'
            ),
            'default_from_chatboo': True,
            'default_warn_hardcoded_rows': has_hardcoded,
            'default_warn_incomplete_capture': capture_incomplete,
            'default_existing_skill_id': existing_skill.id if existing_skill else False,
            'default_param_prose': ' '.join(
                part for part in (param_prose or '').split()
                if not self._normalize_turn_id(part)
            ).strip(),
            'default_source_turn_id': corr,
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
            'res_model': 'ai.skill.capture.wizard',
            'view_mode': 'form',
            'views': [[False, 'form']],
            'target': 'new',
            'context': ctx,
        }
        return action, warning

    def prepare_skill_edit_action(self, token=None, param_prose=None):
        """Open the capture wizard on an owned extra, or return picker rows."""
        self.ensure_one()
        if self.user_id.id != self.env.user.id:
            raise UserError(_('Access denied to this session.'))
        if not self.env.user.has_group('pns_ai_mcp.group_ai_writer'):
            raise UserError(_(
                'AI Writer permission is required to edit skills from Chatboo.'
            ))
        Skill = self.env['ai.skill']
        hits, kind = Skill.resolve_owned_for_params(token)
        if kind == 'picks' or len(hits) != 1:
            return None, Skill.owned_skill_picks(hits)
        skill = hits
        slash = ''
        if hasattr(skill, 'invoke_code'):
            slash = (skill.invoke_code() or '').strip()
        if not slash:
            slash = (skill.command or skill.code or '').strip()
        ctx = {
            'form_view_initial_mode': 'edit',
            'capture_from_chatboo': True,
            'default_skill_code': slash,
            'default_skill_name': skill.name or slash,
            'default_description': skill.description or '',
            'default_procedure': skill.content or '',
            'default_code_body': skill.code_body or '',
            'default_param_schema': skill.param_schema or False,
            'default_arg_hint': skill.arg_hint or False,
            'default_args_policy': skill.args_policy or 'default',
            'default_from_chatboo': True,
            'default_existing_skill_id': skill.id,
            'default_param_prose': (param_prose or '').strip() or '',
            'chatboo_session_id': self.id,
            'default_chatboo_session_id': self.id,
        }
        chatboo_agent = self.env['ai.agent'].search(
            [('code', '=', 'pns_ai_chatboo')], limit=1,
        )
        if chatboo_agent:
            ctx['default_agent_ids'] = [(6, 0, chatboo_agent.ids)]
        elif skill.agent_ids:
            ctx['default_agent_ids'] = [(6, 0, skill.agent_ids.ids)]
        action = {
            'type': 'ir.actions.act_window',
            'name': _('Edit skill'),
            'res_model': 'ai.skill.capture.wizard',
            'view_mode': 'form',
            'views': [[False, 'form']],
            'target': 'new',
            'context': ctx,
        }
        return action, None

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
        # Seges: parche 11 (PNS-82, seguridad). Ver docs/pendiente/parches_pns_ai.md
        self.check_access_rights('unlink')
        self.check_access_rule('unlink')
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
                    # Seges: parche 11 (PNS-82, seguridad). Ver docs/pendiente/parches_pns_ai.md
                    owner = {s.id: s.user_id.id for s in self.sudo()}
                    own = atts.filtered(
                        lambda a: a.create_uid.id in (False, owner.get(a.res_id)))
                    (atts - own).write({'res_model': False, 'res_id': False})
                    own.unlink()
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
        """Cron: delete every user's sessions older than the configured retention.

        Sessions whose user was deleted (``user_id`` empty) go the same way.
        """
        try:
            retention_days = int(self.env['ir.config_parameter'].sudo().get_param(
                RETENTION_PARAM, DEFAULT_HISTORY_RETENTION_DAYS,
            ))
            if retention_days <= 0:
                return
            cutoff_date = fields.Datetime.now() - timedelta(days=retention_days)
            old_sessions = self.sudo().search([
                ('last_used_date', '<', cutoff_date),
            ])
            if old_sessions:
                _logger.info(
                    "Cleaning %s Chatboo session(s) older than %s days",
                    len(old_sessions), retention_days,
                )
                old_sessions.unlink()
        except Exception as e:
            _logger.error("Error cleaning old sessions: %s", e)
