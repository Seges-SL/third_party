# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""chatboo.session — conversation persistence (messages and prompt history)."""

import json
import logging
import re
import time
from datetime import timedelta

from odoo import models, fields, api, _
from odoo.exceptions import RedirectWarning, UserError
# Seges: parche 25 (M1, seguridad). Ver docs/pendiente/parches_pns_ai.md
from odoo.exceptions import AccessError

from odoo.addons.pns_ai_mcp.utils import record_marks
# Seges: parche 18 (PNS-19, seguridad). Ver docs/pendiente/parches_pns_ai.md
from odoo.addons.pns_ai_mcp.models.box_a_guard import _box_a_trusted
from odoo.addons.pns_ai_mcp.utils.markup_rename import rename_stored_markup

from ..utils import turn_documents
from ..utils.chatboo_product_icp import ICP_HISTORY_RETENTION_DAYS

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
    canvas_open = fields.Boolean(string='Canvas open')
    canvas_design = fields.Text(string='Canvas design')
    canvas_rev = fields.Integer(string='Canvas revision', default=0)
    canvas_title = fields.Char(
        string='Canvas title',
        copy=False,
        help="Title of the answer the page was laid out from. The browser "
             "tab shows it.",
    )
    canvas_turn = fields.Char(
        string='Canvas turn',
        copy=False,
        index=True,
        help="Turn chip of the page that is open. /create-skill of that "
             "turn keeps the page.",
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

    # The Canvas button kept its build here before it was a chatboo.canvas.job.
    _FOSSIL_COLUMNS = ('canvas_build_started', 'canvas_build_error')

    def init(self):
        super().init()
        for column in self._FOSSIL_COLUMNS:
            self.env.cr.execute(
                'ALTER TABLE chatboo_session DROP COLUMN IF EXISTS "%s"' % column
            )
        rename_stored_markup(self.env.cr, self._table, 'messages')
        rename_stored_markup(self.env.cr, self._table, 'canvas_design')

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

    def get_model_history(self):
        """History for the next turn, rebuilt from what the server saved.

        The browser's copy is never trusted: no system lines and no
        off-topic/local exchanges, matching what the client used to build.
        """
        out = []
        for msg in self.get_messages():
            if not isinstance(msg, dict) or msg.get('role') == 'system':
                continue
            meta = msg.get('meta') if isinstance(msg.get('meta'), dict) else {}
            if msg.get('verification_ack') or meta.get('verification_ack'):
                out.append(msg)
                continue
            if (
                msg.get('offtopic') or msg.get('local_ack')
                or meta.get('offtopic') or meta.get('local_ack')
            ):
                continue
            out.append(msg)
        return out

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

    def _stage_assistant_download_chips(self, chips):
        """Accumulate download chips until the assistant message is saved."""
        self.ensure_one()
        chips = self._claim_turn_file_chips(chips)
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

    def _apply_assistant_download_chips(self, chips):
        """Append download chips to the last assistant message or stage them."""
        self.ensure_one()
        chips = self._claim_turn_file_chips(chips)
        if not chips:
            return
        messages = self.get_messages()
        if messages and messages[-1].get('role') == 'assistant':
            existing = list(messages[-1].get('files') or [])
            messages[-1]['files'] = existing + list(chips)
            self.set_messages(messages)
        else:
            self._stage_assistant_download_chips(chips)

    def _claim_turn_file_chips(self, chips):
        """Hang engine-created attachments on this session. Return the chips it keeps.

        Only an attachment with no record yet, created by this session's
        owner, is hung here. A chip pointing at anyone else's file is dropped.
        A chip without a file (a pending export) has nothing to take and stays.
        """
        self.ensure_one()
        Attachment = self.env['ir.attachment'].sudo()
        kept = []
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
                kept.append(chip)
                continue
            att = Attachment.browse(int(att_id))
            if not att.exists():
                continue
            if att.res_model == self._name and att.res_id == self.id:
                kept.append(chip)
                continue
            if att.res_model or att.res_id or att.create_uid != self.user_id:
                continue
            att.write({
                'res_model': self._name,
                'res_id': self.id,
            })
            kept.append(chip)
        return kept

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

    # The server decides the stored mimetype from the kind; the client's
    # word is never stored (PNS-65).
    _CLIENT_EXPORT_MIMETYPES = {
        'doc': 'application/msword',
        'html': 'text/html',
        'pdf': 'application/pdf',
    }

    def fulfill_client_export(self, filename, mimetype, datas, kind=None):
        """Replace a pending Word/PDF/HTML chip with client-assembled bytes."""
        self.ensure_one()
        import base64
        raw = base64.b64decode(datas or b'')
        if not raw:
            return False
        name = (filename or 'export')[:255]
        kind = (kind or '').strip().lower()
        mimetype = self._CLIENT_EXPORT_MIMETYPES.get(kind)
        if not mimetype:
            return False
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
            self._apply_assistant_download_chips([chip])
        self.notify_files_updated()
        return chip

    def recover_orphan_download_chips(self, messages=None, since=None):
        """Build download chips from session attachments not yet in message history."""
        self.ensure_one()
        # RPC-callable: only the owner of the session gets its chips.
        if not self.env.su and self.user_id.id != self.env.uid:
            return []
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
        """Stamp the session, unless a turn holds the row: a reload never waits for it."""
        self.ensure_one()
        self.env.cr.execute(
            "SELECT id FROM chatboo_session WHERE id = %s FOR UPDATE SKIP LOCKED",
            (self.id,),
        )
        if self.env.cr.fetchone():
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
        self._claim_page_turn()
        sessions = self

        def _wrap(method_name):
            method = getattr(self, method_name)

            def _fn(*args, **kwargs):
                return method(*args, **kwargs)

            _fn.__name__ = method_name
            return _fn

        def read_document(name, page=None, find=None):
            return sessions._read_document(name, page=page, find=find)

        return {
            'read_document': read_document,
            'page_url': _wrap('page_url'),
            'page_edit': _wrap('page_edit'),
            'page_html': _wrap('page_html'),
        }

    def _claim_page_turn(self):
        """If this sentence asked for a page, the bubble will be only the card."""
        codes = (self.env.context or {}).get('matched_domain_codes') or []
        if 'page_tab' not in codes:
            return
        try:
            from odoo.addons.pns_ai_mcp.utils.result_page import (
                note_page_waiting, note_page_wanted,
            )
        except Exception:
            return
        note_page_wanted(self.env)
        instruction = ((self.env.context or {}).get('user_message') or '').strip()

        def fulfill(env, rows):
            from .chatboo_canvas import open_page
            return open_page(
                env['chatboo.session'], rows, instruction, new=True,
            ) or ''

        note_page_waiting(self.env, fulfill)

    def _held_domain_codes(self):
        """Packs this session keeps on every turn while its page is open.

        A follow-up such as «add a tab with …» names the data, not the page.
        Without ``page_tab`` the model never learns that ``page_edit`` exists.
        """
        self.ensure_one()
        from .chatboo_canvas import has_open_page
        return ['page_tab'] if has_open_page(self) else []

    def page_url(self, rows=None, instruction='', new=False):
        """Url of a page built from ``rows``, or '' when there is none.

        Soft fail, like a geocode miss: an empty string never aborts the
        turn. The cause is in ``ai.log``. The model must not invent one.

        Nothing leaves this method as an exception. A helper that raises into
        the sandbox gets swallowed by the model's own ``try``, and then no
        one can tell why the page never appeared.
        """
        try:
            from .chatboo_canvas import open_page
            return open_page(self, rows, instruction, new=new) or ''
        except Exception as exc:
            try:
                from .chatboo_canvas import log_no_page
                return log_no_page(
                    self.env, '%s: %s' % (type(exc).__name__, exc),
                )
            except Exception:
                _logger.warning('Chatboo canvas failed', exc_info=True)
                return ''

    def page_html(self, html, rows=None, title=''):
        """Open ``html`` as the page and fill ``rows``. No design call.

        A captured skill brings the page that already worked. This stores
        it and returns its url. An empty string never aborts the turn.
        The publish check runs the code and must not leave a page behind.
        """
        try:
            if (self.env.context or {}).get('skill_publish_check'):
                return ''
            from .chatboo_canvas import (
                _blocks_for_page, _session_of_this_turn, log_no_page,
                pictures_as_tokens, place_rows_on_page, swap_pictures,
                sync_canvas_title_phrases,
            )
            html = (html or '').strip()
            if not html:
                return log_no_page(self.env, 'page_html got no document')
            html = sync_canvas_title_phrases(html, title)
            session = _session_of_this_turn(self)
            if not session:
                return ''
            blocks = _blocks_for_page(rows)
            # Seges: parche 26 (M2, seguridad). Ver docs/pendiente/parches_pns_ai.md
            blocks, images = pictures_as_tokens(session.env(su=False), blocks)
            content = swap_pictures(
                place_rows_on_page(
                    html, blocks, captured=True, title=title,
                ), images,
            )
            if not (content or '').strip():
                return log_no_page(
                    session.env, 'page_html produced nothing', session.id,
                )
            name = (title or '').strip()
            rev = session._store_design(
                content, title=name or None,
            )
            return session.canvas_public_url(rev=rev) or ''
        except Exception as exc:
            try:
                from .chatboo_canvas import log_no_page
                return log_no_page(
                    self.env, '%s: %s' % (type(exc).__name__, exc),
                )
            except Exception:
                _logger.warning('Chatboo canvas failed', exc_info=True)
                return ''

    def page_edit(self, instruction='', rows=None):
        """Url of the open page after this change, or '' when there is none.

        Without ``rows`` the figures already on the page stay: no query, and
        Design writes only the changes. Same soft fail as ``page_url``.
        """
        try:
            from .chatboo_canvas import edit_page
            return edit_page(self, instruction, rows) or ''
        except Exception as exc:
            try:
                from .chatboo_canvas import log_no_page
                return log_no_page(
                    self.env, '%s: %s' % (type(exc).__name__, exc),
                )
            except Exception:
                _logger.warning('Chatboo canvas failed', exc_info=True)
                return ''

    def canvas_public_url(self, rev=None):
        self.ensure_one()
        if rev is None:
            rev = self.canvas_rev or 0
        return '/chatboo/canvas/%s?rev=%s' % (self.id, rev)

    def _canvas_agent_code(self):
        code = (self.env.context or {}).get('mcp_agent_code') or ''
        return code or 'pns_ai_chatboo'

    def _store_design(self, content, title=None):
        """Persist the page outside the sandbox cursor. Returns the revision.

        ``title=None`` keeps the tab title the open page already had.

        A relaxaicode read runs on the caja-A READ ONLY cursor, which is
        rolled back when the tool returns. Writing the page there fails, and
        if it did not it would vanish and the url would 404. Same isolated
        writable cursor + commit as ``geo.map.create_from_geojson``.
        """
        self.ensure_one()
        from odoo import SUPERUSER_ID

        turn = self._normalize_turn_id(
            (self.env.context or {}).get('mcp_turn') or '',
        )
        new_cr = self.env.registry.cursor()
        try:
            env_w = api.Environment(new_cr, SUPERUSER_ID, {})
            session = env_w['chatboo.session'].browse(self.id)
            rev = (session.canvas_rev or 0) + 1
            values = {
                'canvas_open': True,
                'canvas_design': content,
                'canvas_rev': rev,
            }
            if turn:
                values['canvas_turn'] = turn
            if title is not None:
                values['canvas_title'] = title or False
            session.write(values)
            new_cr.commit()
            return rev
        except Exception:
            try:
                new_cr.rollback()
            except Exception:
                pass
            raise
        finally:
            try:
                new_cr.close()
            except Exception:
                pass

    def _store_title(self, title):
        """Name the open page when it has none. Same cursor as ``_store_design``."""
        self.ensure_one()
        title = ' '.join(str(title or '').split())
        if not title:
            return False
        from odoo import SUPERUSER_ID

        new_cr = self.env.registry.cursor()
        try:
            env_w = api.Environment(new_cr, SUPERUSER_ID, {})
            session = env_w['chatboo.session'].browse(self.id)
            if (session.canvas_title or '').strip():
                return False
            session.write({'canvas_title': title})
            new_cr.commit()
            return True
        except Exception:
            try:
                new_cr.rollback()
            except Exception:
                pass
            _logger.debug('Chatboo canvas: could not name the page', exc_info=True)
            return False
        finally:
            try:
                new_cr.close()
            except Exception:
                pass

    # Seges: parche 25 (M1, seguridad). Ver docs/pendiente/parches_pns_ai.md
    def _paint_canvas(self, instruction, new_page=False, rows=None, title='',
                      images=None):
        """One design call. Returns the page url, or '' when there is none.

        Lives on this model on purpose: ``page_url`` is already here, and a
        second ``_inherit`` that the stack did not list left every call
        as ``AttributeError`` while Design providers sat unused.

        The tab is the page address, so a refinement reuses it. ``new_page``
        only decides whether the open design is the base of this one. No
        provider carries the Design tick: no page, and no borrowing the one
        that holds the dialogue. The reason is in ``ai.log``.

        A change to the open page asks Design for the changes only: writing
        the whole document again is what takes minutes. Changes that do not
        fit the page exactly get the whole document laid out again.
        """
        self.ensure_one()
        # Seges: parche 25 (M1, seguridad). Ver docs/pendiente/parches_pns_ai.md
        if self.sudo().user_id.id != self.env.uid:
            raise AccessError(_('This canvas belongs to another user.'))
        from .chatboo_canvas import (
            DESIGN_SYSTEM, EDIT_SYSTEM, apply_edits, design_figure_leaks,
            design_figures_centralized, is_document, log_no_page, page_edits,
            pictures_out, place_rows_on_page, strip_fence, swap_pictures,
            sync_canvas_title_phrases,
            # Seges: parche 29 (P-8e a, seguridad). Ver docs/pendiente/parches_pns_ai.md
            _blocks_for_page, _const_data_value, _raw_value_left,
            _rows_from_const_data, page_markup_texts, page_rows_texts,
        )

        instruction = (instruction or '').strip()
        if not instruction and not new_page:
            instruction = 'Update the open canvas.'
        images = dict(images or {})
        page = ''
        if not new_page and (self.canvas_design or '').strip():
            page = pictures_out(self.canvas_design, images)
        # Seges: parche 29 (P-8e a, seguridad). Ver docs/pendiente/parches_pns_ai.md
        # A change without rows keeps the open page's figures: the server
        # writes them again, so Design cannot change or unescape them.
        bind_rows, bind_title, kept_texts = rows, title, []
        if page and not _blocks_for_page(rows):
            bind_rows = _rows_from_const_data(_const_data_value(page))
            bind_title = title or self.canvas_title or ''
            if not _blocks_for_page(bind_rows):
                # No DATA to write again: check the change against the
                # values of the server's own tables, or do not change it.
                kept_texts = page_rows_texts(page)
                if not kept_texts:
                    return log_no_page(
                        self.env,
                        'the open page has no figures to keep; '
                        'change it with its rows',
                        session_id=self.id,
                    )
                # Seges: parche 29 (P-8e a, seguridad). Ver docs/pendiente/parches_pns_ai.md
                # An earlier change may have moved a value out of the table.
                kept_texts += page_markup_texts(page)
        prompt = instruction or 'Open a canvas.'
        if page:
            prompt += '\n\nCurrent page:\n' + page
        try:
            if page:
                result = self._ask_design(EDIT_SYSTEM, prompt, 'changed the page')
                raw = strip_fence((result or {}).get('content') or '')
                edits = page_edits(raw)
                changed = apply_edits(page, edits) if edits else None
                if changed is not None and not design_figures_centralized(
                    changed, rows, title,
                ):
                    _logger.info(
                        'Chatboo canvas: edit mixed figures into the page; '
                        'kept the layout',
                    )
                if changed is not None:
                    result = dict(result, content=changed)
                elif not (result or {}).get('error') and (
                    edits or not is_document(raw)
                ):
                    _logger.info(
                        'Chatboo canvas: %s; laying the page out again',
                        'changes did not fit the page' if edits
                        else 'no changes in the answer',
                    )
                    result = self._ask_design(
                        DESIGN_SYSTEM, prompt, 'laid out the page again',
                    )
            else:
                result = self._ask_design(DESIGN_SYSTEM, prompt, 'laid out the page')
        except (UserError, RedirectWarning) as exc:
            return log_no_page(
                self.env, 'no design provider: %s' % exc, session_id=self.id,
            )
        except Exception as exc:
            return log_no_page(
                self.env,
                'the design call broke: %s: %s' % (type(exc).__name__, exc),
                session_id=self.id,
            )
        err = ((result or {}).get('error') or '').strip()
        raw = strip_fence((result or {}).get('content') or '')
        if raw and not is_document(raw):
            raw = ''
        elif raw and not design_figures_centralized(raw, rows, title):
            leaks = design_figure_leaks(raw, rows, title)
            _logger.info(
                'Chatboo canvas: design mixed figures into the template%s; '
                'asking again',
                (': %s' % ', '.join(leaks[:5])) if leaks else '',
            )
            retry_prompt = prompt
            if leaks:
                retry_prompt += (
                    '\n\nThe previous document baked these values outside '
                    'const DATA: %s. Read them from DATA. Do not write them '
                    'as literals.'
                ) % ', '.join(leaks[:8])
            else:
                retry_prompt += (
                    '\n\nThe previous document was not a reusable template. '
                    'Write figures only as const DATA.'
                )
            again = self._ask_design(
                DESIGN_SYSTEM, retry_prompt, 'laid out the page again',
            )
            raw2 = strip_fence((again or {}).get('content') or '')
            if raw2 and is_document(raw2) and design_figures_centralized(
                raw2, rows, title,
            ):
                raw = raw2
                result = again
            else:
                _logger.info(
                    'Chatboo canvas: design mixed figures into the template; '
                    'kept the layout',
                )
        content = ''
        if raw:
            # Seges: parche 29 (P-8e a, seguridad). Ver docs/pendiente/parches_pns_ai.md
            content = swap_pictures(place_rows_on_page(
                sync_canvas_title_phrases(raw, title),
                bind_rows,
                captured=True,
                title=bind_title,
            ), images)
            # Seges: parche 29 (P-8e a, seguridad). Ver docs/pendiente/parches_pns_ai.md
            if kept_texts and _raw_value_left(
                content, [{'title': '', 'data': kept_texts}],
            ) is not None:
                return log_no_page(
                    self.env,
                    'the change left a value of the page as markup',
                    session_id=self.id,
                )
        if err or not content:
            return log_no_page(
                self.env, err or 'the design model returned nothing',
                session_id=self.id,
            )
        if self._canvas_build_cancelled():
            _logger.info('Chatboo canvas: build cancelled, page dropped (session %s)', self.id)
            return ''
        try:
            rev = self._store_design(
                content, title=title if (title or new_page) else None,
            )
        except Exception as exc:
            return log_no_page(
                self.env, 'could not store the page: %s' % exc,
                session_id=self.id,
            )
        return self.canvas_public_url(rev=rev)

    # Seges: parche 18 (PNS-19, seguridad). Ver docs/pendiente/parches_pns_ai.md
    def _ask_design(self, system, prompt, what):
        """The design call, inside box A too: it reads the provider there.

        Plain strings go in; only the design (content and error) comes out.
        """
        system, prompt, what = str(system or ''), str(prompt or ''), str(what or '')
        with _box_a_trusted(self.env):
            result = self._ask_design_raw(system, prompt, what) or {}
            return {
                'content': str(result.get('content') or ''),
                'error': str(result.get('error') or ''),
            }

    def _ask_design_raw(self, system, prompt, what):
        """One call to the Design chain, metered and logged on the turn."""
        from odoo.addons.pns_ai_mcp.utils.agent_engine import (
            llm_completion_for_agent,
        )
        from odoo.addons.pns_ai_mcp.utils.inference_audit import inference_audit

        turn = (self.env.context or {}).get('mcp_turn') or ''
        started = time.monotonic()
        with inference_audit(
            self.env,
            endpoint='llm_response',
            source_channel='internal',
            agent_code=self._canvas_agent_code(),
            user_prompt=prompt[:480],
            turn=turn,
            additional_info={'need': 'design', 'session_id': self.id},
            require_usage=False,
            log_mode='accumulate' if turn else 'single',
        ) as audit:
            result = llm_completion_for_agent(
                self.env, system, prompt,
                agent_code=self._canvas_agent_code(), need='design',
                max_tokens=32768, timeout=180,
            )
        try:
            from odoo.addons.pns_ai_mcp.utils.llm_usage import (
                note_turn_side_usage,
            )
            note_turn_side_usage((result or {}).get('usage'))
        except Exception:
            pass
        if turn:
            self._log_design_step(
                audit, result, system, prompt, time.monotonic() - started, what,
            )
        return result

    def _log_design_step(self, audit, result, system, prompt, seconds,
                         what='laid out the page'):
        """One row on the turn thread: who laid the page out, and what it cost.

        Its spend is also in the turn total. The row is ``llm_response``,
        which the usage summary does not add twice. It keeps the messages
        the model got and the page it sent back, as written.
        """
        try:
            engine = self.env['ai.execution.engine']
            turn, turn_step = engine._resolve_log_threading()
            result = result or {}
            content = result.get('content') or ''
            err = (result.get('error') or '').strip()
            summary = (
                'Design failed after %.0f s: %s' % (seconds, err) if err
                else 'Design %s in %.0f s (%d chars)'
                % (what, seconds, len(content))
            )
            engine.log_llm_inference(
                getattr(audit, 'provider', None),
                getattr(audit, 'usage_acc', None) or result.get('usage') or {},
                endpoint='llm_response',
                agent_code=self._canvas_agent_code(),
                turn=turn,
                turn_step=turn_step,
                user_prompt=prompt[:480],
                additional_info={'need': 'design', 'session_id': self.id},
                prompt_data={'messages': [
                    {'role': 'system', 'content': system or ''},
                    {'role': 'user', 'content': prompt or ''},
                ]},
                result_data={'content': [{'type': 'text', 'text': content}]}
                if content else None,
                result_summary=summary,
                status='error' if err else 'ok',
            )
        except Exception:
            _logger.debug('Chatboo canvas: could not log the design step', exc_info=True)

    # ── Canvas button: the tables of one answer, laid out as a page ──────
    # The design call outlives an HTTP request, so it runs in a thread and
    # the browser asks for the state. Callers check the owner first.

    @api.model
    def canvas_available(self):
        """True when some provider on this agent's chain has the Design tick."""
        try:
            return bool(self.env['ai.execution.engine'].get_providers_for_agent(
                self._canvas_agent_code(), need='design',
            ))
        except Exception:
            return False

    def _canvas_build_cancelled(self):
        """True when the user cancelled the Canvas job this page is laid out for."""
        job_id = (self.env.context or {}).get('chatboo_canvas_job')
        return bool(job_id) and self.env['chatboo.canvas.job'].browse(job_id)._is_cancel_requested()

    @api.model
    def _read_document(self, name, page=None, find=None):
        session_id = self.env.context.get('ai_session_ref')
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
        """Substantive relaxaicode snippets for a turn, chronological order.

        A step the sandbox refused or that raised is not part of the skill.
        """
        from odoo.addons.pns_ai_chatboo.utils.skill_capture_compose import (
            log_run_failed,
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
            if log_run_failed(log.result_data):
                continue
            code = (log.code_to_execute or '').strip()
            if code and not snippet_is_probe_code(code):
                codes.append(code)
        return codes

    def _turn_user_prompt(self, corr, source_log=None):
        """The human sentence of this turn, not the slash name.

        The best relaxaicode log often has an empty ``user_prompt``; the
        ``llm_response`` / ``domain_index`` row of the same turn still has it.
        """
        prompt = ''
        if source_log:
            prompt = (source_log.user_prompt or '').strip()
        if prompt:
            return prompt
        if not corr:
            return ''
        logs = self.env['ai.log'].search([
            ('user_id', '=', self.env.user.id),
            ('turn', '=ilike', corr),
            ('user_prompt', '!=', False),
        ], limit=20, order='id asc')
        for log in logs:
            prompt = (log.user_prompt or '').strip()
            if prompt:
                return prompt
        return ''

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
        from odoo.addons.pns_ai_chatboo.utils.skill_capture_compose import (
            log_run_failed,
        )
        ran = logs.filtered(lambda log: not log_run_failed(log.result_data))
        if ran:
            logs = ran
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

    def _catalog_skill_for_capture(self, slash):
        """Row that can lend Code to this capture (active or archived)."""
        Skill = self.env['ai.skill']
        if not (slash or '').strip():
            return Skill.browse()
        found = Skill._find_by_invoke_token(slash)
        if found:
            return found
        return Skill.sudo().with_context(active_test=False)._find_by_invoke_token(
            slash,
        )

    def _capture_invoke_command(self, raw):
        """Slash the instance prefixes would store for ``raw``."""
        from odoo.addons.pns_ai_mcp.utils.skill_code_prefix import (
            get_skill_code_prefix,
            get_skill_command_prefix,
            instance_identity,
        )
        token = (raw or '').strip()
        if not token:
            return ''
        _code, command = instance_identity(
            token,
            get_skill_code_prefix(self.env),
            get_skill_command_prefix(self.env),
        )
        return command or ''

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
            return composed, capture_is_incomplete(composed, fetch_steps)
        return composed, pipeline_incomplete

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

    def _wrap_open_page(self, code, corr):
        """The page open in this session is the one the skill will reopen.

        ``corr`` is the chip the person named. The page is whichever is open
        now: that is the one they just looked at. A skill without parameters
        keeps that page as the turn showed it. Parameters still need a
        reusable template at save.

        Only when that turn painted the page or its Code calls a page
        helper. A table turn later in the same session stays a table.
        """
        self.ensure_one()
        design = (self.canvas_design or '').strip()
        if not design:
            return code
        from .chatboo_canvas import code_touches_page, wrap_captured_page
        turn = (self.canvas_turn or '').strip().upper()
        if turn != (corr or '').strip().upper() and not code_touches_page(code):
            return code
        return wrap_captured_page(
            code, design, self.canvas_title or '',
        )

    def prepare_skill_capture_action(self, skill_code_hint=None, turn_id=None,
                                     param_prose=None):
        """Open the skill capture wizard pre-filled from a turn.

        The slash on the line is the new skill (or the one to replace if
        the caller already owns it). A catalog skill the turn ran may
        lend Code when there is no query log; it does not steal the name.

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

        from odoo.addons.pns_ai_chatboo.utils.skill_capture_compose import (
            capture_binds_catalog_slash,
        )
        Skill = self.env['ai.skill']
        catalog_slash = self._catalog_slash_for_turn(corr)
        catalog_skill = self._catalog_skill_for_capture(catalog_slash)
        name_command = self._capture_invoke_command(name_hint)
        catalog_command = self._capture_invoke_command(
            (catalog_skill.invoke_code() if catalog_skill else '')
            or catalog_slash
        )
        binds_catalog = capture_binds_catalog_slash(
            name_hint, catalog_slash, name_command, catalog_command,
        )
        source_log = self.env['ai.log'].browse()
        param_schema = ''
        arg_hint = ''
        capture_incomplete = False
        used_catalog_body = False
        code_body = ''

        if binds_catalog and catalog_skill:
            code_body = (catalog_skill.code_body or '').strip()
            if not code_body:
                raise UserError(_(
                    'Skill /%s has no capturable Code.'
                ) % (catalog_skill.invoke_code() or catalog_slash))
            used_catalog_body = True
            param_schema = catalog_skill.param_schema or ''
            arg_hint = catalog_skill.arg_hint or ''
        else:
            source_log = self._find_best_capture_log_for_turn(corr)
            if source_log:
                code_body = self._pick_capture_code(
                    source_log.code_to_execute, source_log,
                )
            if code_body:
                code_body, capture_incomplete = self.compose_capture_code(
                    code_body, corr,
                )
            elif catalog_skill and (catalog_skill.code_body or '').strip():
                code_body = (catalog_skill.code_body or '').strip()
                used_catalog_body = True
                param_schema = catalog_skill.param_schema or ''
                arg_hint = catalog_skill.arg_hint or ''
            elif catalog_slash and binds_catalog:
                raise UserError(_(
                    'Turn %s ran /%s, but that skill is no longer '
                    'in the catalog.'
                ) % (corr, catalog_slash))
            elif source_log:
                raise UserError(_(
                    'No capturable query code found for turn %s.'
                ) % corr)
            else:
                raise UserError(_(
                    'No MCP log found for turn %s (or it is not yours).'
                ) % corr)

        code_body = self._wrap_open_page(code_body, corr)

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
        elif binds_catalog and catalog_skill:
            token = catalog_skill.invoke_code() or catalog_slash
            _code, command, existing_skill = (
                Skill.resolve_capture_identity(token)
            )
            skill_code = command
            skill_name = (catalog_skill.name or token)[:48]
        else:
            skill_code = ''
            skill_name = ''

        from odoo.addons.pns_ai_mcp.utils.skill_runtime import capture_help_text
        catalog_names = ()
        if catalog_skill:
            catalog_names = (
                catalog_skill.name, catalog_skill.code, catalog_skill.command,
            )
        description = capture_help_text(
            catalog_help=(
                catalog_skill.description
                if used_catalog_body and catalog_skill else ''
            ),
            user_prompt=self._turn_user_prompt(corr, source_log),
            name_hint=name_hint or '',
            turn_id=corr,
            names=catalog_names,
        )
        has_hardcoded = self._code_has_hardcoded_rows(code_body)
        if used_catalog_body and catalog_skill:
            procedure = (catalog_skill.content or '').strip() or (
                self._default_capture_procedure(has_hardcoded)
            )
        else:
            procedure = self._default_capture_procedure(has_hardcoded)

        warning = None
        notes = []
        if binds_catalog and catalog_skill:
            notes.append(_(
                'This turn ran /%s. The wizard has that skill\'s Code '
                'and Procedure (not a new query).'
            ) % (catalog_skill.invoke_code() or catalog_slash))
        elif catalog_slash:
            notes.append(_(
                'This turn ran /%s. The wizard captures it as /%s.'
            ) % (
                catalog_skill.invoke_code() if catalog_skill else catalog_slash,
                skill_code or name_hint or '',
            ))
        if 'page_html(' in (code_body or ''):
            notes.append(_(
                'This skill opens the page from that turn. Each run fills '
                'it with live rows and does not call Design.'
            ))
        if has_hardcoded:
            notes.append(_(
                'The captured code contains pasted row literals (e.g. data = [{...}, ...]). '
                'Replace that block with live api_call fetches before publishing the skill.'
            ))
        if notes:
            warning = '\n'.join(notes)

        ctx = {
            'form_view_initial_mode': 'edit',
            'default_source_log_id': source_log.id if source_log else False,
            'default_skill_code': skill_code,
            'default_skill_name': skill_name,
            'default_description': description,
            'default_procedure': procedure,
            'default_code_body': code_body,
            'default_param_schema': param_schema or False,
            'default_arg_hint': arg_hint or False,
            'default_args_policy': (
                (catalog_skill.args_policy if used_catalog_body and catalog_skill else 'default')
                or 'default'
            ),
            'default_from_chat': True,
            'default_warn_hardcoded_rows': has_hardcoded,
            'default_warn_incomplete_capture': capture_incomplete,
            'default_existing_skill_id': existing_skill.id if existing_skill else False,
            'default_param_prose': ' '.join(
                part for part in (param_prose or '').split()
                if not self._normalize_turn_id(part)
            ).strip(),
            'default_source_turn_id': corr,
            'ai_session_ref': self.id,
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
            'default_skill_code': slash,
            'default_skill_name': skill.name or slash,
            'default_description': skill.description or '',
            'default_procedure': skill.content or '',
            'default_code_body': skill.code_body or '',
            'default_param_schema': skill.param_schema or False,
            'default_arg_hint': skill.arg_hint or False,
            'default_args_policy': skill.args_policy or 'default',
            'default_from_chat': True,
            'default_existing_skill_id': skill.id,
            'default_param_prose': (param_prose or '').strip() or '',
            'ai_session_ref': self.id,
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
            raw_retention = self.env['ir.config_parameter'].sudo().get_param(
                RETENTION_PARAM,
            )
            if raw_retention is None or raw_retention is False or str(raw_retention).strip() == '':
                return
            retention_days = int(raw_retention)
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
