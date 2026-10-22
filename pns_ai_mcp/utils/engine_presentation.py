# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""How a turn closes on screen: done event, page card, file export."""

import json
import logging

from .llm_usage import add_usage, advertise_cost

_logger = logging.getLogger(__name__)


class PresentationMixin:
    """Part of ``AgentEngine``; only used through it."""

    def _resolve_done_meta(self, agent_code, provider=None, provider_id=None):
        """Modelo/proveedor/límite para eventos ``done`` (también sin ronda LLM)."""
        meta = {
            'model': '',
            'provider': '',
            'protocol': '',
            'context_limit': 0,
            'display_currency': 'USD',
        }
        try:
            if provider is not None:
                p = provider
            else:
                Engine = self.env['ai.execution.engine']
                providers = Engine.get_providers_for_agent(
                    agent_code, provider_id=provider_id,
                )
                p = providers[0] if providers else None
            if not p:
                return meta
            meta['model'] = (
                (p.model_id.name if getattr(p, 'model_id', None) else None)
                or p.model_name
                or p.name
                or ''
            )
            meta['provider'] = p.name or ''
            meta['protocol'] = getattr(p, 'protocol', None) or ''
            meta['context_limit'] = p.context_window or 0
            from .display_currency import get_display_currency
            meta['display_currency'] = get_display_currency(self.env)
        except Exception as exc:
            _logger.debug('done meta resolve failed: %s', exc)
        return meta

    def _clip_data_from_payload(self, payload, rows=None):
        """Bubble clip for icons (xlsx formulas travel here, not in HTML)."""
        try:
            from .artifact_export import clip_data_from_payload
            return clip_data_from_payload(payload, rows)
        except Exception:
            return None

    def _done_event(
        self,
        session_id,
        agent_code=None,
        provider=None,
        provider_id=None,
        usage=None,
        sources=None,
        skill_code=None,
        records=None,
        local=False,
        clip_data=None,
    ):
        """Evento ``done`` completo para que Chatboo pinte modelo/tokens.

        ``local=True``: tarjeta determinista (ayuda / ask / reject). No hay
        inferencia ni ocupación de contexto; Chatboo no la manda al histórico.
        A page or map card is not local: Design or the query already spent
        tokens, time and money, and the footer must show them.
        """
        if local:
            return {
                'event': 'done',
                'session_id': session_id,
                'model': '',
                'provider': 'local',
                'protocol': '',
                'context_limit': 0,
                'display_currency': '',
                'usage': None,
                'sources': [],
                'records': [],
                'compose': '',
                'turn': '',
                'local_ack': True,
            }
        meta = self._resolve_done_meta(
            agent_code, provider=provider, provider_id=provider_id,
        )
        model = meta.get('model') or ''
        if skill_code:
            model = (
                '%s · skill/%s' % (model, skill_code) if model
                else 'skill/%s' % skill_code
            )
        side = self._side_usage()
        self._log_side_usage_close(side, meta.get('model') or '', skill_code)
        if usage is None:
            usage = dict(side) if side else {
                'prompt_tokens': 0,
                'completion_tokens': 0,
                'total_tokens': 0,
                'cost': 0,
            }
        elif side:
            usage = add_usage(dict(usage), side)
        if usage and not usage.get('total_tokens'):
            _p = usage.get('prompt_tokens') or 0
            _c = usage.get('completion_tokens') or 0
            if _p or _c:
                usage = dict(usage, total_tokens=_p + _c)
        if provider is not None:
            try:
                usage = advertise_cost(usage)
            except Exception:
                pass
        self._persist_provider_usage(provider, usage)
        turn = getattr(self, '_turn_corr', None) or (
            (self.env.context or {}).get('mcp_turn')
        )
        ev = {
            'event': 'done',
            'session_id': session_id,
            'model': model,
            'provider': meta.get('provider') or '',
            'protocol': meta.get('protocol') or '',
            'context_limit': meta.get('context_limit') or 0,
            'display_currency': meta.get('display_currency') or 'USD',
            'usage': usage,
            'sources': list(sources or []),
            'records': list(records or []),
            'compose': getattr(self, '_turn_compose', None) or '',
            'turn': turn or '',
        }
        if clip_data:
            ev['clip_data'] = clip_data
        return ev

    def _log_side_usage_close(self, side, model_name, skill_code=None):
        """Turn close for a turn that ends without the tool loop.

        Satellite calls (skill params, …) only fold into the turn; the tool
        loop writes ``orchestration_summary``. A direct skill never reaches
        it, so this writes that row once, with the satellite spend only.
        """
        if not side or not (side.get('total_tokens') or side.get('prompt_tokens')
                            or side.get('completion_tokens') or side.get('cost')):
            return
        turn = getattr(self, '_turn_corr', None)
        if getattr(self, '_side_close_logged_turn', None) == (turn or id(self)):
            return
        self._side_close_logged_turn = turn or id(self)
        usage = dict(side)
        if not usage.get('total_tokens'):
            usage['total_tokens'] = (
                (usage.get('prompt_tokens') or 0)
                + (usage.get('completion_tokens') or 0)
            )
        try:
            usage = advertise_cost(usage)
        except Exception:
            pass
        label = ('skill/%s' % skill_code) if skill_code else 'direct'
        self._mcp_log(
            operation_type='read',
            tool_name='orchestration_summary',
            request_type='LLM',
            agent_llm=model_name or None,
            result_summary='Turn completed · %s · side calls only' % label,
            usage=usage,
            prompt_tokens=usage.get('prompt_tokens'),
            completion_tokens=usage.get('completion_tokens'),
            total_tokens=usage.get('total_tokens'),
        )

    def _claim_page_turn(self, message):
        """Score this sentence now, before a skill writes the bubble.

        Helpers that opted in see ``matched_domain_codes`` and may mark
        the turn as a page. The engine does not name those helpers.
        """
        try:
            from .domain_index import (
                TARGET_KIND_DOMAIN, filter_entries_by_kind, match_domains,
            )
            from .sandbox_helpers import collect_sandbox_helpers
            entries = self._domain_index_entries(
                user_locale=self._resolve_user_locale(),
            ) or []
            matched = list(
                (match_domains(
                    message or '',
                    filter_entries_by_kind(entries, TARGET_KIND_DOMAIN),
                ) or {}).get('codes') or [],
            )
            self.env = self.env(context=dict(
                self.env.context or {},
                matched_domain_codes=matched,
            ))
            collect_sandbox_helpers(self.env)
        except Exception:
            _logger.debug(
                'AgentEngine: early domain match failed', exc_info=True,
            )

    def _offer_page_card(self, payload):
        """Card HTML when the result is a page, else ''."""
        from .result_page import fulfill_waiting_page, has_page_url
        if not isinstance(payload, dict):
            return ''
        fulfill_waiting_page(self.env, payload)
        if not has_page_url(payload):
            return ''
        from .relaxaicode_render import (
            maybe_attach_formatted_text, render_context_from_env,
        )
        maybe_attach_formatted_text(
            payload, render_context=render_context_from_env(self.env, payload),
        )
        return (payload.get('formatted_text') or '').strip()

    def _intercept_session_file_propose(
        self, user_message, session_id, tool_args, rows=None, payload=None,
    ):
        """Block caja B dumps of a named download onto orphan ir.attachment.

        Returns a fake tool result (never creates ``ai.safe.operation``), or
        None when the plan is not a session-file propose. If rows already
        exist, persist the server-serialized chip and ignore LLM bytes.
        """
        try:
            from .artifact_export import (
                requested_named_format,
                is_session_file_propose,
                SESSION_FILE_PROPOSE_ERROR,
                SESSION_FILE_ATTACHED_NOTE,
            )
        except Exception:
            return None
        if not requested_named_format(user_message):
            return None
        steps = None
        if isinstance(tool_args, dict):
            steps = tool_args.get('steps')
        if not is_session_file_propose(steps):
            return None
        attached = False
        chips = []
        refused_tokens = []
        _ex = self._attach_requested_file_export(
            user_message, session_id, rows=rows, payload=payload,
        )
        chip = None
        if _ex and _ex.get('acted'):
            attached = True
            try:
                from .artifact_export import export_result_chips
                chips = export_result_chips(_ex)
            except Exception:
                chips = []
            chip = chips[0] if chips else _ex.get('chip')
            refused_tokens = list(_ex.get('refused_tokens') or [])
            body = {
                'success': True,
                'session_file': True,
                'note': SESSION_FILE_ATTACHED_NOTE,
            }
        else:
            body = {
                'success': False,
                'error': SESSION_FILE_PROPOSE_ERROR,
            }
        return {
            'result': {
                'content': [{
                    'type': 'text',
                    'text': json.dumps(body, ensure_ascii=False),
                }],
            },
            'attached': attached,
            'acted': attached,
            'chip': chip,
            'chips': chips,
            'refused_tokens': refused_tokens,
        }

    def _attach_requested_file_export(
        self, user_message, session_id, rows=None, payload=None,
    ):
        """Serialize known download formats from this turn's rows, if asked.

        Deterministic file-type tokens only (no locale verb list). One
        card per unique kind. Named formats hide the server table unless
        ``__show_table__``. PPT does not serialize. Word uses this
        turn's ``formatted_text`` when ``__rich_doc__`` is set.
        """
        try:
            from .artifact_export import apply_requested_exports
        except Exception:
            return None
        def _persist(raw, filename, mimetype):
            from .session_download import persist_turn_file
            return persist_turn_file(
                self.env, session_id, raw, filename, mimetype=mimetype,
            )
        try:
            result = apply_requested_exports(
                user_message,
                rows=rows,
                payload=payload,
                persist=_persist,
                prompt=user_message,
                env=self.env,
                client_fulfill=bool(session_id),
            )
            return result
        except Exception:
            _logger.warning(
                'AgentEngine: requested file export failed',
                exc_info=True,
            )
            return None
