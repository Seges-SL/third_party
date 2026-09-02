# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""Chatboo API (chat client) controller.

This module owns its own sessions/history; inference is delegated to the
pns_ai_mcp engine (AgentEngine) and streamed over SSE (Server-Sent Events)
at /chatboo/stream. Auth: Odoo session (auth='user') plus MCP API key
carnet (``ai.mcp.user.mcp_api_key_hash``) enforced server-side on every
route — fail-closed. See pns_ai_mcp/docs/dos_credenciales_api.md.
"""

import json
import logging
import time

from odoo import http, _
from odoo.exceptions import UserError
from odoo.http import request, Response

from ..utils.chatboo_access import user_has_chatboo_access
from ..utils.compat import JSON_ROUTE_TYPE
from ..utils.fx_rates import get_usd_fx

_logger = logging.getLogger(__name__)


class ChatbooController(http.Controller):

    def _user_may_use_chatboo(self):
        return user_has_chatboo_access(request.env)

    def _chatboo_access_denied(self):
        return {
            'status': 'error',
            'message': _('Chatboo access denied. An MCP API key is required.'),
            'show_systray': False,
            'has_api_key': False,
            'connected': False,
        }

    def _chatboo_skill_ctx(self, session_id=None):
        if not session_id:
            return {}
        try:
            session = request.env['chatboo.session'].browse(int(session_id))
        except (TypeError, ValueError):
            return {}
        if not session.exists() or session.user_id.id != request.env.uid:
            return {}
        return {'chatboo_session_id': session.id}

    def _user_card_width_ratio(self):
        try:
            return request.env.user.chatboo_card_width_ratio_value()
        except Exception:
            return 0.0

    def _with_user_prefs(self, payload):
        data = dict(payload or {})
        data['card_width_ratio'] = self._user_card_width_ratio()
        return data

    # ──────────────────────────── Salud / proveedor ────────────────────────────

    @http.route('/chatboo/check_health', type=JSON_ROUTE_TYPE, auth='user')
    def check_health(self):
        """Devuelve el proveedor de IA activo, permisos y diagnóstico de agente/pack.

        Acceso Chatboo: fail-closed. Sin carnet MCP (hash) no hay systray ni
        uso del asistente; un error al comprobar acceso también deniega.
        """
        try:
            can_save_raw = request.env.user.has_group('pns_ai_mcp.group_ai_admin')
        except Exception:
            can_save_raw = False

        try:
            show_systray = request.env['ir.config_parameter'].sudo().get_param(
                'pns_ai_chatboo.show_systray', 'True',
            ) not in ('False', 'false', '0')
        except Exception:
            show_systray = True

        has_api_key = self._user_may_use_chatboo()
        show_systray = bool(show_systray) and has_api_key
        fx = self._fx_payload()
        display_currency = self._global_display_currency()

        # ── Agent / pack diagnostic ──
        try:
            agent_diag = self._diagnose_agent_pack()
        except Exception as e:
            _logger.warning("Chatboo: fallo en el diagnóstico de agente/pack: %s", e)
            agent_diag = {}

        try:
            from urllib.parse import urlparse
            provider = self._resolve_active_provider()
            if not provider:
                return self._with_user_prefs({
                    'status': 'error',
                    'message': _("No AI provider is assigned. Ask an administrator to assign one to the agent."),
                    'provider': 'None',
                    'connected': False, 'can_save_raw': can_save_raw,
                    'has_api_key': has_api_key,
                    'show_systray': show_systray,
                    'fx': fx,
                    'display_currency': display_currency,
                    **agent_diag,
                })
            model = provider.model_name or (provider.model_id.name if provider.model_id else None) or "Unknown Model"
            host = "localhost"
            if provider.endpoint:
                try:
                    parsed = urlparse(provider.endpoint)
                    host = parsed.netloc or (parsed.path.split('/')[0] if parsed.path else "localhost")
                    if ':' in host:
                        host = host.split(':')[0]
                    if not host:
                        host = "localhost"
                except Exception:
                    host = "Unknown Host"
            alias = (getattr(provider, 'alias', None) or '').strip()
            display = alias or f"{host} → {model}"
            return self._with_user_prefs({
                'status': 'ok',
                'provider': display,
                'model': model if not alias else display,
                'host': '' if alias else host,
                'alias': alias or None,
                'connected': True, 'has_api_key': has_api_key, 'can_save_raw': can_save_raw,
                'show_systray': show_systray,
                'fx': fx,
                'display_currency': display_currency,
                **agent_diag,
            })
        except Exception as e:
            _logger.error("Chatboo Health Error: %s", e)
            return self._with_user_prefs({
                'status': 'error', 'message': str(e), 'provider': 'System Error',
                'connected': False, 'can_save_raw': can_save_raw,
                'has_api_key': has_api_key,
                'show_systray': show_systray,
                'fx': fx,
                'display_currency': display_currency,
                **agent_diag,
            })

    @http.route('/chatboo/prefs', type=JSON_ROUTE_TYPE, auth='user')
    def save_prefs(self, card_width_ratio=None, **kwargs):
        """Persist this user's Chatboo card width. Never writes another uid."""
        if not self._user_may_use_chatboo():
            return self._chatboo_access_denied()
        if card_width_ratio is None:
            card_width_ratio = kwargs.get('card_width_ratio')
        try:
            ratio = request.env['res.users'].chatboo_set_own_card_width_ratio(
                card_width_ratio,
            )
            return {'status': 'ok', 'card_width_ratio': ratio}
        except Exception as e:
            _logger.error("Chatboo prefs: %s", e)
            return {'status': 'error', 'message': str(e)}

    @http.route('/chatboo/test_connection', type=JSON_ROUTE_TYPE, auth='user')
    def test_connection(self):
        """Prueba la conexión con el proveedor de IA activo."""
        if not self._user_may_use_chatboo():
            return self._chatboo_access_denied()
        try:
            provider = self._resolve_active_provider()
            if not provider:
                return {'status': 'error', 'title': 'Connection Test Failed',
                        'message': _("No AI provider is assigned. Ask an administrator to assign one to the agent.")}
            try:
                result = provider.test_connection()
                if result and 'params' in result:
                    params = result['params']
                    return {
                        'status': 'success',
                        'title': params.get('title', 'Connection Test'),
                        'message': params.get('message', 'Connection successful'),
                        'type': params.get('type', 'success'),
                    }
                return {'status': 'error', 'title': 'Connection Test Failed', 'message': 'Unexpected response from provider'}
            except Exception as test_error:
                error_msg = getattr(test_error, 'name', None) or str(test_error)
                return {'status': 'error', 'title': 'Connection Test Failed', 'message': error_msg}
        except Exception as e:
            _logger.error("Chatboo Test Connection Error: %s", e)
            return {'status': 'error', 'title': 'Connection Test Failed', 'message': str(e)}

    # ──────────────────────────── Sesiones / histórico ────────────────────────────

    @http.route('/chatboo/sessions/list', type=JSON_ROUTE_TYPE, auth='user')
    def list_sessions(self):
        """Lista las sesiones del usuario. La activa es la más reciente."""
        if not self._user_may_use_chatboo():
            return self._chatboo_access_denied()
        try:
            sessions = request.env['chatboo.session'].get_user_sessions(limit=50)
            active_session_id = sessions[0].id if sessions else None
            return {
                'status': 'ok',
                'active_session_id': active_session_id,
                'sessions': [{
                    'id': s.id,
                    'name': s.name,
                    'create_date': s.create_date.isoformat() if s.create_date else None,
                    'last_used_date': s.last_used_date.isoformat() if s.last_used_date else None,
                    'message_count': len(s.get_messages()),
                } for s in sessions],
            }
        except Exception as e:
            _logger.error("Error listing sessions: %s", e)
            return {'status': 'error', 'message': str(e)}

    @http.route('/chatboo/sessions/create', type=JSON_ROUTE_TYPE, auth='user')
    def create_session(self, name=None):
        if not self._user_may_use_chatboo():
            return self._chatboo_access_denied()
        try:
            if not name:
                session = request.env['chatboo.session'].create({
                    'user_id': request.env.user.id,
                })
            else:
                session = request.env['chatboo.session'].create({
                    'name': name,
                    'user_id': request.env.user.id,
                })
            return {
                'status': 'ok',
                'session': {
                    'id': session.id,
                    'name': session.name,
                    'create_date': session.create_date.isoformat() if session.create_date else None,
                    'last_used_date': session.last_used_date.isoformat() if session.last_used_date else None,
                },
            }
        except Exception as e:
            _logger.error("Error creating session: %s", e)
            return {'status': 'error', 'message': str(e)}

    @http.route('/chatboo/sessions/load', type=JSON_ROUTE_TYPE, auth='user')
    def load_session(self, session_id):
        if not self._user_may_use_chatboo():
            return self._chatboo_access_denied()
        try:
            session = request.env['chatboo.session'].browse(int(session_id))
            if not session.exists():
                return {'status': 'error', 'message': 'Session not found'}
            if session.user_id.id != request.env.user.id:
                return {'status': 'error', 'message': 'Access denied'}
            session.update_last_used()
            return {
                'status': 'ok',
                'session': {
                    'id': session.id,
                    'name': session.name,
                    'messages': session.get_messages_for_chat(),
                    'input_history': session.get_input_history(),
                    'conversation_id': session.conversation_id or None,
                },
            }
        except Exception as e:
            _logger.error("Error loading session: %s", e)
            return {'status': 'error', 'message': str(e)}

    @http.route('/chatboo/sessions/fulfill_export', type=JSON_ROUTE_TYPE, auth='user')
    def fulfill_export(self, session_id, filename, mimetype, datas, kind=None):
        """Persist a client-assembled Word/PDF/HTML and replace the pending chip."""
        if not self._user_may_use_chatboo():
            return self._chatboo_access_denied()
        kind = (kind or '').strip().lower()
        if kind not in ('doc', 'pdf', 'html'):
            return {'status': 'error', 'message': 'Unsupported kind'}
        try:
            session = request.env['chatboo.session'].browse(int(session_id))
            if not session.exists():
                return {'status': 'error', 'message': 'Session not found'}
            if session.user_id.id != request.env.user.id:
                return {'status': 'error', 'message': 'Access denied'}
            chip = session.fulfill_client_export(
                filename, mimetype, datas, kind=kind,
            )
            if not chip:
                return {'status': 'error', 'message': 'Could not store file'}
            return {'status': 'ok', 'chip': chip}
        except Exception as e:
            _logger.error("Error fulfilling export %s: %s", session_id, e)
            return {'status': 'error', 'message': str(e)}

    @http.route('/chatboo/export/xlsx', type=JSON_ROUTE_TYPE, auth='user')
    def export_xlsx(self, sections=None, filename=None):
        """Build an .xlsx with the same server writer as a named Excel download."""
        if not self._user_may_use_chatboo():
            return self._chatboo_access_denied()
        try:
            from odoo.addons.pns_ai_mcp.utils import artifact_export as ae
            payload = ae.icon_xlsx_payload(sections, filename=filename)
        except Exception as e:
            _logger.error("Error building Excel: %s", e)
            return {'status': 'error', 'message': str(e)}
        if not payload:
            return {'status': 'error', 'message': 'Could not build Excel'}
        payload['status'] = 'ok'
        return payload

    @http.route('/chatboo/sessions/save', type=JSON_ROUTE_TYPE, auth='user')
    def save_session(self, session_id, messages, input_history, conversation_id=None):
        """Guarda el estado de una sesión. Auto-renombra con el primer prompt."""
        if not self._user_may_use_chatboo():
            return self._chatboo_access_denied()
        import re
        try:
            session = request.env['chatboo.session'].browse(int(session_id))
            if not session.exists():
                return {'status': 'error', 'message': 'Session not found'}
            if session.user_id.id != request.env.user.id:
                return {'status': 'error', 'message': 'Access denied'}

            if session.name and session.name.startswith('Session '):
                first_user_prompt = None
                if messages and isinstance(messages, list):
                    for msg in messages:
                        if msg.get('role') == 'user' and msg.get('content'):
                            first_user_prompt = msg.get('content')
                            break
                if first_user_prompt:
                    clean_prompt = re.sub(r'<[^>]+>', '', first_user_prompt).strip()
                    new_name = clean_prompt[:40] + ('...' if len(clean_prompt) > 40 else '')
                    if new_name:
                        session.name = new_name[0].upper() + new_name[1:]

            session.set_messages(messages)
            session.set_input_history(input_history)
            if conversation_id:
                session.conversation_id = conversation_id
            session.update_last_used()
            return {'status': 'ok'}
        except Exception as e:
            _logger.error("Error saving session %s: %s", session_id, e)
            return {'status': 'error', 'message': str(e)}

    @http.route('/chatboo/sessions/rename', type=JSON_ROUTE_TYPE, auth='user')
    def rename_session(self, session_id, new_name):
        if not self._user_may_use_chatboo():
            return self._chatboo_access_denied()
        try:
            if not new_name or not new_name.strip():
                return {'status': 'error', 'message': _('Name cannot be empty')}
            session = request.env['chatboo.session'].browse(int(session_id))
            if not session.exists():
                return {'status': 'error', 'message': 'Session not found'}
            if session.user_id.id != request.env.user.id:
                return {'status': 'error', 'message': 'Access denied'}
            session.name = new_name.strip()
            return {'status': 'ok', 'new_name': session.name}
        except Exception as e:
            _logger.error("Error renaming session %s: %s", session_id, e)
            return {'status': 'error', 'message': str(e)}

    @http.route('/chatboo/sessions/delete', type=JSON_ROUTE_TYPE, auth='user')
    def delete_session(self, session_id):
        if not self._user_may_use_chatboo():
            return self._chatboo_access_denied()
        try:
            session = request.env['chatboo.session'].browse(int(session_id))
            if not session.exists():
                return {'status': 'error', 'message': 'Session not found'}
            if session.user_id.id != request.env.user.id:
                return {'status': 'error', 'message': 'Access denied'}
            session.unlink()
            return {'status': 'ok'}
        except Exception as e:
            _logger.error("Error deleting session: %s", e)
            return {'status': 'error', 'message': str(e)}

    @http.route('/chatboo/sessions/bulk_delete', type=JSON_ROUTE_TYPE, auth='user')
    def bulk_delete_sessions(self, session_ids):
        if not self._user_may_use_chatboo():
            return self._chatboo_access_denied()
        try:
            if not session_ids or not isinstance(session_ids, list):
                return {'status': 'error', 'message': _('A list of session IDs is required.')}
            sessions = request.env['chatboo.session'].browse(session_ids)
            if not sessions.exists():
                return {'status': 'error', 'message': _('The requested sessions were not found.')}
            for session in sessions:
                if session.user_id.id != request.env.user.id:
                    return {'status': 'error', 'message': _('Access denied to one or more sessions.')}
            count = len(sessions)
            sessions.unlink()
            return {'status': 'ok', 'deleted_count': count}
        except Exception as e:
            _logger.error("Error bulk deleting sessions: %s", e)
            return {'status': 'error', 'message': str(e)}

    @http.route('/chatboo/save_raw_for_template', type=JSON_ROUTE_TYPE, auth='user')
    def save_raw_for_template(self, query, result_json):
        """Guarda resultado JSON en bruto para crear plantillas. Solo MCP Managers."""
        if not self._user_may_use_chatboo():
            return self._chatboo_access_denied()
        try:
            if not request.env.user.has_group('pns_ai_mcp.group_ai_admin'):
                return {'status': 'error', 'message': 'Solo administradores MCP pueden guardar resultados para plantillas.'}
            if not result_json or not isinstance(result_json, (str, dict)):
                return {'status': 'error', 'message': 'result_json requerido'}
            json_str = result_json if isinstance(result_json, str) else json.dumps(result_json, ensure_ascii=False)
            raw = request.env['pns_ai_mcp.relaxaicode_raw_result'].create({
                'query': (query or '')[:500],
                'result_json': json_str[:500000],
            })
            return {'status': 'ok', 'id': raw.id, 'message': 'Guardado. Ve a Resultados en bruto para crear la plantilla.'}
        except Exception as e:
            _logger.exception("Chatboo save_raw_for_template: %s", e)
            return {'status': 'error', 'message': str(e)}

    @http.route('/chatboo/dismiss_messages', type=JSON_ROUTE_TYPE, auth='user')
    def dismiss_messages(self):
        """Marca como vistos los jobs asíncronos pendientes del usuario."""
        if not self._user_may_use_chatboo():
            return self._chatboo_access_denied()
        try:
            request.env['chatboo.async.request'].search([
                ('user_id', '=', request.env.uid),
                ('seen', '=', False),
            ]).mark_seen()
        except Exception as e:
            _logger.debug("Chatboo dismiss_messages: %s", e)
        return {'status': 'ok'}

    @http.route('/chatboo/async/poll', type=JSON_ROUTE_TYPE, auth='user')
    def async_poll(self, session_id=None):
        """Catch-up: devuelve jobs terminados no vistos (recupera tras F5).

        La fuente de verdad es la BD: el worker ya guardó el resultado en la
        sesión, así que el cliente solo necesita saber qué sesiones recargar.
        """
        if not self._user_may_use_chatboo():
            return self._chatboo_access_denied()
        try:
            # Reclaim inmediato: si hay jobs sin latido (worker muerto por un
            # reinicio Docker/Odoo), cerramos el zombie ANTES de responder.
            # Timeout corto + SKIP LOCKED: un prompt fallido NUNCA cuelga el
            # spinner de Odoo al abrir el elefante.
            try:
                request.env['chatboo.async.request'].sudo().with_context(
                    chatboo_reclaim_timeout_ms=3000,
                )._reclaim_stuck(minutes=1)
            except Exception:
                pass
            domain = [
                ('user_id', '=', request.env.uid),
                ('state', 'in', ('done', 'error')),
                ('seen', '=', False),
            ]
            if session_id:
                domain.append(('session_id', '=', int(session_id)))
            jobs = request.env['chatboo.async.request'].search(domain, order='finished_at asc')
            pending = [{
                'request_id': j.id,
                'session_id': j.session_id.id,
                'is_error': j.state == 'error',
            } for j in jobs]
            jobs.mark_seen()
            # Jobs EN CURSO reales (latido reciente). Tras un F5, el cliente
            # muestra "pensando…" y se re-engancha. Los zombies sin latido ya
            # debieron caer en reclaim; si no, NO los devolvemos como running
            # (evitar thinking/spinner eterno tras reinicio).
            from datetime import timedelta
            from odoo import fields as odoo_fields
            alive_cutoff = odoo_fields.Datetime.now() - timedelta(seconds=60)
            run_domain = [
                ('user_id', '=', request.env.uid),
                ('state', 'in', ('pending', 'running')),
                ('write_date', '>=', alive_cutoff),
            ]
            if session_id:
                run_domain.append(('session_id', '=', int(session_id)))
            run_jobs = request.env['chatboo.async.request'].search(
                run_domain, order='started_at asc')
            running = [{
                'request_id': j.id,
                'session_id': j.session_id.id,
            } for j in run_jobs]
            return {'status': 'ok', 'pending': pending, 'running': running}
        except Exception as e:
            _logger.debug("Chatboo async_poll: %s", e)
            return {'status': 'error', 'message': str(e), 'pending': [], 'running': []}

    @http.route('/chatboo/async/cancel', type=JSON_ROUTE_TYPE, auth='user')
    def async_cancel(self, request_id=None, session_id=None):
        """Cancela un job pending/running (botón Cancelar junto a Thinking…)."""
        if not self._user_may_use_chatboo():
            return self._chatboo_access_denied()
        try:
            Async = request.env['chatboo.async.request']
            job = False
            if request_id:
                job = Async.browse(int(request_id))
                if not job.exists() or job.user_id.id != request.env.uid:
                    job = False
            if not job and session_id:
                job = Async.search([
                    ('user_id', '=', request.env.uid),
                    ('session_id', '=', int(session_id)),
                    ('state', 'in', ('pending', 'running')),
                ], order='id desc', limit=1)
            if not job:
                return {'status': 'ok', 'cancelled': False}
            ok = bool(job.request_cancel())
            return {'status': 'ok', 'cancelled': ok, 'request_id': job.id}
        except Exception as e:
            _logger.debug("Chatboo async_cancel: %s", e)
            return {'status': 'error', 'error': str(e), 'cancelled': False}

    @http.route('/chatboo/skills/list', type=JSON_ROUTE_TYPE, auth='user')
    def skills_list(self, **kwargs):
        """Skills del agente de inferencia, para el autocompletado del `/` en el front."""
        if not self._user_may_use_chatboo():
            return self._chatboo_access_denied()
        try:
            agent_code = request.env['ai.agent'].resolve_inference_agent_code(
                kwargs.get('agent_code'), consumer_key='chatboo',
            )
            Skill = request.env['ai.skill']
            skills = Skill.list_for_agent(agent_code)
            from odoo.addons.pns_ai_mcp.utils.skill_code_prefix import (
                get_skill_code_prefix,
                get_skill_command_prefix,
            )
            return {
                'status': 'ok',
                'skills': skills,
                'can_write_skills': Skill.user_can_author_skills(),
                'skill_code_prefix': get_skill_code_prefix(request.env),
                'skill_command_prefix': get_skill_command_prefix(request.env),
            }
        except Exception as e:
            _logger.error("Chatboo skills_list: %s", e)
            return {'status': 'error', 'message': str(e), 'skills': []}

    @http.route('/chatboo/create-skill', type=JSON_ROUTE_TYPE, auth='user')
    def create_skill(self, session_id, skill_code=None, turn_id=None):
        """Open the skill capture wizard from a Chatboo session (/create-skill)."""
        if not self._user_may_use_chatboo():
            return self._chatboo_access_denied()
        try:
            if not session_id:
                return {'status': 'error', 'message': _('session_id is required.')}
            session = request.env['chatboo.session'].browse(int(session_id))
            if not session.exists():
                return {'status': 'error', 'message': _('Session not found.')}
            if session.user_id.id != request.env.uid:
                return {'status': 'error', 'message': _('Access denied.')}
            action, warning = session.prepare_skill_capture_action(
                skill_code_hint=(skill_code or '').strip() or None,
                turn_id=(turn_id or '').strip() or None,
            )
            payload = {'status': 'ok', 'action': action}
            if warning:
                payload['warning'] = warning
            return payload
        except UserError as e:
            return {'status': 'error', 'message': str(e)}
        except Exception as e:
            _logger.exception("Chatboo create_skill: %s", e)
            return {'status': 'error', 'message': str(e)}

    @http.route('/chatboo/delete-skill', type=JSON_ROUTE_TYPE, auth='user')
    def delete_skill(self, skill_code=None, session_id=None):
        """Delete a skill the current Writer owns (/delete-skill)."""
        if not self._user_may_use_chatboo():
            return self._chatboo_access_denied()
        try:
            result = request.env['ai.skill'].with_context(
                **self._chatboo_skill_ctx(session_id),
            ).action_delete_owned(skill_code)
            return {'status': 'ok', **result}
        except UserError as e:
            return {'status': 'error', 'message': str(e)}
        except Exception as e:
            _logger.exception("Chatboo delete_skill: %s", e)
            return {'status': 'error', 'message': str(e)}

    @http.route('/chatboo/rename-skill', type=JSON_ROUTE_TYPE, auth='user')
    def rename_skill(self, old_code=None, new_code=None, session_id=None):
        """Rename a skill the current Writer owns (/rename-skill old new)."""
        if not self._user_may_use_chatboo():
            return self._chatboo_access_denied()
        try:
            result = request.env['ai.skill'].with_context(
                **self._chatboo_skill_ctx(session_id),
            ).action_rename_owned(
                old_code, new_code,
            )
            return {'status': 'ok', **result}
        except UserError as e:
            return {'status': 'error', 'message': str(e)}
        except Exception as e:
            _logger.exception("Chatboo rename_skill: %s", e)
            return {'status': 'error', 'message': str(e)}

    # ──────────────────────────── Providers ─────────────────────────────────

    @http.route('/chatboo/providers', type=JSON_ROUTE_TYPE, auth='user')
    def list_providers(self):
        """Return the providers in the Chatboo agent's failover chain.

        Also resolves the agent's current default provider so the UI
        can pre-select it. (`ai.provider` has no `active` field.)
        """
        if not self._user_may_use_chatboo():
            return self._chatboo_access_denied()
        try:
            Provider = request.env['ai.provider']
            default_provider_id = None
            providers = Provider.browse()
            try:
                agent_code = request.env['ai.agent'].resolve_inference_agent_code(
                    None, consumer_key='chatboo',
                )
                engine = request.env['ai.execution.engine']
                failovers = engine.get_failovers(agent_code)
                if failovers:
                    provider_ids = []
                    for fo in failovers:
                        p = fo.provider_id
                        if p and p.id not in provider_ids:
                            provider_ids.append(p.id)
                    providers = Provider.browse(provider_ids)
                    if providers:
                        default_provider_id = providers[0].id
                if not providers:
                    providers = Provider.sudo().search([])
                    if len(providers) == 1:
                        default_provider_id = providers[0].id
            except Exception:
                providers = Provider.sudo().search([])
            return {
                'status': 'ok',
                'default_provider_id': default_provider_id,
                'providers': [self._serialize_provider(p) for p in providers],
            }
        except Exception as e:
            _logger.error("Chatboo providers error: %s", e)
            return {'status': 'error', 'providers': [], 'message': str(e)}

    # ──────────────────────────── Inferencia (SSE) ────────────────────────────

    @http.route('/chatboo/stream', type='http', auth='user', methods=['POST'], csrf=False, cors='*')
    def chat_stream(self, **kwargs):
        """Turno de chat con auto-promoción a segundo plano.

        Crea un job (chatboo.async.request) que ejecuta el motor en un hilo con
        cursor propio, guarda el resultado en la sesión y avisa por bus. Este
        endpoint solo hace *tail* del job para el preview en vivo: si cierras o
        recargas, el hilo termina igual y la respuesta queda persistida en BD.
        Body JSON: {session_id, message, history?, agent_code?, provider_id?, screen_context?}.
        """
        if not self._user_may_use_chatboo():
            return self._json_response(
                {'error': _('Chatboo access denied. An MCP API key is required.')},
                status=403,
            )
        try:
            data = json.loads(request.httprequest.data)
            session_id = data.get('session_id')
            message = data.get('message')
            provider_id = data.get('provider_id')
            agent_code = data.get('agent_code')
            history = data.get('history', [])
            screen_context = data.get('screen_context')
            images = data.get('images') or None
            image_names = data.get('image_names') or None
            files = data.get('files') or None
            if not message and not images and not files:
                return self._json_response({'error': _('Message cannot be empty')}, status=400)

            try:
                from odoo.addons.pns_ai_mcp.utils.mcp_correlation import start_new_turn
                start_new_turn(request)
            except Exception:
                pass

            # Aseguramos una sesión: el worker persiste el turno en ella, y es
            # lo que el cliente recarga tras un F5 (catch-up).
            Session = request.env['chatboo.session']
            session = False
            if session_id:
                session = Session.browse(int(session_id))
                if not session.exists() or session.user_id.id != request.env.uid:
                    session = False
            if not session:
                session = Session.create({'user_id': request.env.uid})
            session_id = session.id

            request.chatboo_options = {'chatboo_session_id': session_id}

            # Comprobación rápida de proveedor → mensaje amable inmediato.
            resolved_code = request.env['ai.agent'].resolve_inference_agent_code(
                agent_code, consumer_key='chatboo',
            )
            try:
                _has_provider = bool(request.env['ai.execution.engine'].get_providers_for_agent(
                    resolved_code, provider_id=provider_id,
                ))
            except Exception:
                _has_provider = True  # no bloquear por fallo de comprobación
            if not _has_provider:
                _agent = request.env['ai.agent'].search([('code', '=', resolved_code)], limit=1)
                _label = (_agent.name if _agent else resolved_code) or resolved_code
                _msg = _(
                    'No AI provider is configured for the "%s" agent. '
                    'Assign at least one AI provider to this agent '
                    'before using the assistant.'
                ) % _label

                def _no_provider_stream():
                    yield self._sse_event('token', {'event': 'token', 'content': _msg})
                    yield self._sse_event('done', {'event': 'done', 'session_id': session_id, 'usage': {}})

                return Response(
                    _no_provider_stream(), mimetype='text/event-stream',
                    direct_passthrough=True, headers=self._sse_headers(),
                )

            # Encolar + lanzar worker en segundo plano (sobrevive a la desconexión).
            job = request.env['chatboo.async.request'].enqueue(
                session_id, message, history=history,
                agent_code=agent_code, provider_id=provider_id,
                screen_context=screen_context, images=images, files=files,
                image_names=image_names,
            )
            request.env.cr.commit()  # hacer visible el job al cursor del worker
            job.spawn()

            rid = job.id
            # El generador SSE se itera fuera del 'with request:' (cursor liberado),
            # así que no usamos request.env dentro: capturamos el registry y leemos
            # el progreso del job con cursores propios (patrón del stream original).
            registry = request.env.registry

            def generate_stream():
                sent_len = 0
                sent_struct = 0
                yield self._sse_event('meta', {
                    'event': 'meta', 'request_id': rid, 'session_id': session_id,
                })
                deadline = time.time() + 600  # tope de tail: 10 min
                # Keepalive: si el modelo tarda en emitir (p. ej. Qwen3-Coder-30B),
                # el tail no envía bytes y el proxy inverso corta la conexión
                # ("network error"). Mandamos un comentario SSE cada KEEPALIVE_SECS
                # para mantener viva la conexión; el cliente ignora los comentarios.
                KEEPALIVE_SECS = 15
                last_activity = time.time()
                while True:
                    state = None
                    partial = ''
                    struct = []
                    response = ''
                    err = ''
                    done_meta = {}
                    try:
                        with registry.cursor() as cr:
                            cr.execute(
                                "SELECT state, partial, struct_events, done_meta, response, error "
                                "FROM chatboo_async_request WHERE id=%s", (rid,),
                            )
                            row = cr.fetchone()
                        if row:
                            state, partial, _struct_txt, _done_txt, response, err = row
                            partial = partial or ''
                            response = response or ''
                            struct = json.loads(_struct_txt) if _struct_txt else []
                            done_meta = json.loads(_done_txt) if _done_txt else {}
                    except Exception:
                        state = None
                    if state is not None:
                        while sent_struct < len(struct):
                            _e = struct[sent_struct]
                            yield self._sse_event(_e.get('event', 'status'), _e)
                            sent_struct += 1
                            last_activity = time.time()
                        # '!=' (no '>'): el partial puede MENGUAR si el motor hace
                        # failover tras emitir parcialmente (reset anti-duplicado);
                        # reenviamos el contenido completo para que el preview en
                        # vivo se corrija al instante, no solo al 'done'.
                        if len(partial) != sent_len:
                            yield self._sse_event('replace', {'event': 'replace', 'content': partial})
                            sent_len = len(partial)
                            last_activity = time.time()
                        if state in ('done', 'error'):
                            final = response or partial
                            if final and len(final) != sent_len:
                                yield self._sse_event('replace', {'event': 'replace', 'content': final})
                            done_evt = dict(done_meta or {})
                            done_evt.update({
                                'event': 'done',
                                'session_id': session_id,
                                'authored': True,
                                'is_error': state == 'error',
                            })
                            if state == 'error' and err:
                                done_evt['error'] = err
                            yield self._sse_event('done', done_evt)
                            try:
                                with registry.cursor() as cr:
                                    cr.execute(
                                        "UPDATE chatboo_async_request SET seen=true WHERE id=%s", (rid,),
                                    )
                            except Exception:
                                pass
                            return
                    if time.time() > deadline:
                        return
                    if time.time() - last_activity >= KEEPALIVE_SECS:
                        # bytes, no str: en Odoo 19 werkzeug exige bytes en el
                        # stream ("applications must write bytes").
                        yield b': keepalive\n\n'
                        last_activity = time.time()
                    time.sleep(0.3)

            return Response(
                generate_stream(), mimetype='text/event-stream',
                direct_passthrough=True, headers=self._sse_headers(),
            )
        except json.JSONDecodeError:
            return self._json_response({'error': _('Request body is not valid JSON')}, status=400)
        except Exception as e:
            _logger.exception("Error fatal en /chatboo/stream")
            return self._json_response({'error': str(e)}, status=500)

    def _sse_headers(self):
        return [
            ('Cache-Control', 'no-cache'),
            ('Connection', 'keep-alive'),
            ('X-Accel-Buffering', 'no'),
        ]

    # ──────────────────────────── Utilidades ────────────────────────────

    def _diagnose_agent_pack(self):
        """Diagnostic flags for the inference agent / pack / regional readiness.

        Returns a dict safe to spread into the check_health response:
          has_agent:            bool — chatboo has an inference agent configured
          has_pack:             bool — that agent has a pack (bundle) assigned
          has_regional_context: bool — the pack contains regional contexts for
                                       the user's active lang
        """
        try:
            agent_code = request.env['ai.agent'].resolve_inference_agent_code(
                None, consumer_key='chatboo',
            )
            agent = request.env['ai.agent'].search(
                [('code', '=', agent_code)], limit=1,
            ) if agent_code else request.env['ai.agent'].browse()
            if not agent:
                return {'has_agent': False, 'has_pack': False, 'has_regional_context': False}
            effective = agent._get_effective_contexts()
            if not effective:
                return {'has_agent': True, 'has_pack': False, 'has_regional_context': False}
            user_locale = request.env.context.get('lang', 'en_US')
            has_regional = bool(effective.filtered(
                lambda c: c.context_type == 'locale' and c.locale == user_locale
            ))
            return {
                'has_agent': True,
                'has_pack': True,
                'has_regional_context': has_regional,
            }
        except Exception:
            return {'has_agent': False, 'has_pack': False, 'has_regional_context': False}

    def _provider_host(self, provider):
        from urllib.parse import urlparse
        host = "localhost"
        if provider.endpoint:
            try:
                parsed = urlparse(provider.endpoint)
                host = parsed.netloc or (parsed.path.split('/')[0] if parsed.path else "localhost")
                if ':' in host:
                    host = host.split(':')[0]
                if not host:
                    host = "localhost"
            except Exception:
                host = "Unknown Host"
        return host

    def _serialize_provider(self, provider):
        model = (
            provider.model_name
            or (provider.model_id.name if provider.model_id else None)
            or provider.name
            or "Unknown Model"
        )
        host = self._provider_host(provider)
        alias = (getattr(provider, 'alias', None) or '').strip()
        display = alias or f"{host} → {model}"
        return {
            'id': provider.id,
            'name': provider.name,
            'protocol': provider.protocol,
            'model': model,
            'host': host,
            'alias': alias or None,
            'display': display,
        }

    def _global_display_currency(self):
        try:
            from odoo.addons.pns_ai_mcp.utils.display_currency import (
                get_display_currency,
            )
            return get_display_currency(request.env)
        except Exception:
            return 'USD'

    def _fx_payload(self):
        try:
            return get_usd_fx(request.env)
        except Exception as exc:
            _logger.warning("Chatboo: FX payload failed: %s", exc)
            return {'base': 'USD', 'rates': {}, 'as_of': '', 'error': str(exc)}

    def _resolve_active_provider(self):
        """Proveedor de IA efectivo del agente de inferencia.

        ai.provider no tiene campo `active`: el proveedor se resuelve por la
        cadena del agente (motor de pns_ai_mcp), no por un flag global. Devuelve un
        recordset vacío si no hay proveedor configurado.
        """
        try:
            agent_code = request.env['ai.agent'].resolve_inference_agent_code(
                None, consumer_key='chatboo',
            )
            return request.env['ai.execution.engine'].resolve_provider(agent_code)
        except Exception:
            return request.env['ai.provider'].browse()

    def _json_response(self, data, status=200):
        return request.make_response(
            json.dumps(data, ensure_ascii=False),
            headers=[('Content-Type', 'application/json')],
            cookies=None,
        )

    def _sse_event(self, event_name, data_dict):
        payload = json.dumps(data_dict, ensure_ascii=False)
        return (f"event: {event_name}\ndata: {payload}\n\n").encode('utf-8')
