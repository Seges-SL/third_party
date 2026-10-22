# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""Closing a turn: final answer, blocked replies, the done event."""

import logging

from odoo import _
from .llm_usage import add_usage, advertise_cost, usage_since
from .agent_stream_text import (
    NO_TOOL_FINAL_NUDGE,
    PROGRESS_FILLER_NUDGE,
    pretool_progress_status as _pretool_progress_status,
    recover_displaced_turn_body,
    should_block_no_tool_as_final as _should_block_no_tool_as_final,
    should_block_progress_as_final as _should_block_progress_as_final,
    user_visible_round_text as _user_visible_round_text,
)

_logger = logging.getLogger(__name__)


class TurnCloseMixin:
    """Part of ``AgentEngine``; only used through it."""

    def _tool_loop_close_turn(self, turn, _orig, session_id, config, messages):
        from .agent_engine import _closing_reply_after_probe

        if not turn.export_attached:
            _ex = self._attach_requested_file_export(
                _orig, session_id,
                rows=turn.turn_query_data,
                payload=self._payload_for_screen(
                    turn.primary_artifact or turn.last_tabulable_payload,
                ),
            )
            if _ex and _ex.get('acted'):
                turn.export_attached = True
                self._absorb_export_result(turn, _ex)

        if not turn.export_clip_data:
            try:
                from .artifact_export import clip_data_from_payload
                turn.export_clip_data = clip_data_from_payload(
                    turn.primary_artifact or turn.last_tabulable_payload,
                    turn.turn_query_data,
                )
            except Exception:
                turn.export_clip_data = None

        if turn.export_attached and not turn.finished_with_answer:
            turn.finished_with_answer = True
            self._stamp_refused_note(turn)
            _body = ''
            if not turn.export_chips:
                _body = _('Could not build the download file.')
            elif turn.direct_formatted:
                _body = turn.direct_formatted
            if _body:
                yield {
                    "event": "replace",
                    "content": _body,
                }

        # Rondas agotadas sobre un lookup (catálogo + registros). Eso no es
        # el alta. Una frase, sin la tabla y sin «Aquí lo tienes».
        if (
            not turn.finished_with_answer
            and turn.last_tool_unmarked_probe
            and not turn.delivered_marked
        ):
            prose = ''
            try:
                prose = _closing_reply_after_probe(config, messages)
            except Exception:
                _logger.exception(
                    'AgentEngine: closing reply after unmarked probe failed'
                )
            if not (prose or '').strip():
                prose = _('I have not created or changed anything yet.')
            turn.finished_with_answer = True
            yield {"event": "replace", "content": prose}

        # Red de seguridad: se agotaron las rondas (MAX_ROUNDS) sin respuesta final.
        # Nunca volcar ERROR (-NNNN) / Details JSON al usuario.
        if not turn.finished_with_answer and not (
            turn.primary_artifact and turn.table_already_delivered
        ):
            from .error_ux import humanize_exhausted_tool_error

            human, is_perm = humanize_exhausted_tool_error(turn.last_retry_error or '')
            if is_perm and human:
                # Permiso denegado: solo la razón (Odoo/ACL ya habla claro).
                notice = human
            else:
                notice = _(
                    'I could not complete the request after several automatic '
                    'attempts to fix the generated code.'
                )
                if human:
                    notice += '\n\n' + human
            yield {"event": "token", "content": notice}

    def _tool_loop_final_answer(
        self, *,
        MAX_ROUNDS,
        _defer_user_tokens,
        _orig,
        _turn_loop_from,
        config,
        content_buffer,
        history,
        message,
        messages,
        model_name,
        prior_table_fps,
        remote_llm_format,
        round_n,
        session_id,
        sync_error,
        tools,
        turn,
    ):
        """The model answered without tools; True = ask it again."""
        if not content_buffer.strip():
            self._tool_loop_raise_empty(config, model_name, sync_error)
        # After a retryable tool failure, progress chatter without tools
        # is NOT a final answer (R5YZ: announced a map regen, never called).
        if (yield from self._tool_loop_blocked_progress(
                turn, content_buffer, messages, round_n, MAX_ROUNDS, session_id,
        )):
            return True
        # Round 1 with tools in the payload and zero tool_calls is not
        # a user answer (NTU0/THKM: announced a Safe Plan, never called).
        if (yield from self._tool_loop_blocked_no_tool(
                content_buffer, messages, tools, history, _orig, message,
                round_n, MAX_ROUNDS, session_id,
        )):
            return True
        # Respuesta final: si diferimos tokens (ronda con tools en payload),
        # volcamos ahora el buffer al chat.
        _visible = _user_visible_round_text(content_buffer, has_tool_calls=False)
        if _defer_user_tokens and _visible:
            yield {"event": "token", "content": _visible}
        messages.append({"role": "assistant", "content": content_buffer})
        # Candado estructural: forzar tabla / linkify si el LLM narró.
        _final = content_buffer or ''
        # Report outline: reuse this turn's earlier narrative if the
        # closer replaced it; then fill a truncated skeleton only.
        if remote_llm_format:
            _final, content_buffer = yield from self._tool_loop_report_outline(
                messages, _turn_loop_from, _final, content_buffer, session_id,
            )
        _displaced = recover_displaced_turn_body(
            messages[_turn_loop_from:], _final,
        )
        if (_displaced or '').strip() != (_final or '').strip():
            _final = self._tool_loop_keep_delivered(turn, _displaced)
            content_buffer = _final
            yield {"event": "replace", "content": _final}
            _logger.info(
                'agent_engine: recovered displaced turn body '
                '(session=%s)',
                session_id,
            )
        yield from self._tool_loop_delivery_gate(
            turn, _final, content_buffer, prior_table_fps,
            remote_llm_format, session_id,
        )
        turn.finished_with_answer = True
        return False

    def _tool_loop_raise_empty(self, config, model_name, sync_error):
        from ..models.ai_execution_engine import ProviderConnectionError

        if sync_error:
            _logger.warning(
                'Provider %s (model %s) rejected the request: %s',
                config['endpoint'], model_name, sync_error,
            )
            raise ProviderConnectionError(
                _('The AI provider rejected the request. '
                  'If it is HTTP 400, the prompt likely exceeds the '
                  'context size the model was loaded with.')
            )
        _logger.warning(
            'Provider %s (model %s) returned no content.',
            config['endpoint'], model_name,
        )
        raise ProviderConnectionError(
            _('The AI provider returned no content. The model '
              'may have been loaded with a context size smaller than '
              'the prompt.')
        )

    def _tool_loop_blocked_progress(
            self, turn, content_buffer, messages, round_n, MAX_ROUNDS, session_id,
    ):
        if _should_block_progress_as_final(
            content_buffer,
            has_tool_calls=False,
            has_pending_retry=bool(turn.last_retry_error),
            rounds_left=(round_n < MAX_ROUNDS),
            has_hidden_reasoning=bool(
                getattr(self, '_round_had_reasoning', False)
            ),
        ):
            _progress_only = _pretool_progress_status(content_buffer)
            messages.append({
                "role": "assistant",
                "content": content_buffer,
            })
            if turn.last_retry_error:
                from .error_ux import retry_nudge_after_tool_error
                nudge = retry_nudge_after_tool_error(turn.last_retry_error)
            else:
                nudge = PROGRESS_FILLER_NUDGE
            messages.append({
                "role": "user",
                "content": nudge,
            })
            if _progress_only:
                yield {"event": "status", "message": _progress_only}
            _logger.info(
                'agent_engine: blocked progress-as-final '
                '(session=%s round=%s retry=%s reasoning=%s)',
                session_id, round_n, bool(turn.last_retry_error),
                bool(getattr(self, '_round_had_reasoning', False)),
            )
            return True
        return False

    def _tool_loop_blocked_no_tool(
            self, content_buffer, messages, tools, history, _orig, message,
            round_n, MAX_ROUNDS, session_id,
    ):
        if _should_block_no_tool_as_final(
            has_tool_calls=False,
            is_first_round=(round_n == 1),
            rounds_left=(round_n < MAX_ROUNDS),
            has_tools=bool(tools),
            content=content_buffer,
            tool_names=[
                ((tc.get('function') or {}).get('name') or '')
                for tc in (tools or [])
            ],
            user_message=_orig or message,
            prior_assistant=[
                (m.get('content') or '')
                for m in (history or [])
                if isinstance(m, dict)
                and m.get('role') == 'assistant'
                and (m.get('content') or '').strip()
            ],
            inline_file_text=bool(
                (self.env.context or {}).get('inline_file_text')
            ),
        ):
            messages.append({
                "role": "assistant",
                "content": content_buffer,
            })
            messages.append({
                "role": "user",
                "content": NO_TOOL_FINAL_NUDGE,
            })
            _status = _pretool_progress_status(content_buffer)
            if _status:
                yield {"event": "status", "message": _status}
            _logger.info(
                'agent_engine: blocked no-tool-as-final '
                '(session=%s round=%s)',
                session_id, round_n,
            )
            return True
        return False

    def _tool_loop_done_event(
            self,
            _turn_shown_start,
            collected_records,
            direct_formatted,
            export_chips,
            export_clip_data,
            external_sources,
            kept_history,
            last_round_total,
            last_tabulable_payload,
            message,
            messages,
            model_name,
            primary_artifact,
            provider,
            remote_llm_format,
            round_n,
            session_id,
            side_at_start,
            turn_usage,
    ):
        """Turn usage, orchestration log and the done event of this provider's turn."""
        add_usage(turn_usage, usage_since(self._side_usage(), side_at_start))
        usage_out = dict(turn_usage) if turn_usage else {}
        if usage_out and not usage_out.get("total_tokens"):
            _p = usage_out.get("prompt_tokens") or 0
            _c = usage_out.get("completion_tokens") or 0
            if _p or _c:
                usage_out = dict(usage_out, total_tokens=_p + _c)
        if last_round_total:
            usage_out = dict(usage_out, context_tokens=last_round_total)
        try:
            usage_out = advertise_cost(usage_out)
        except Exception:
            pass

        self._persist_provider_usage(provider, usage_out or turn_usage)

        # Histórico: cierre del turno (auditoría) con los tokens del turno.
        self._mcp_log(
            operation_type='read',
            tool_name='orchestration_summary',
            request_type='LLM',
            agent_llm=model_name,
            result_summary='Turn completed · %s LLM round(s)' % round_n,
            usage=usage_out or None,
            prompt_tokens=(usage_out or {}).get('prompt_tokens'),
            completion_tokens=(usage_out or {}).get('completion_tokens'),
            total_tokens=(usage_out or {}).get('total_tokens'),
        )
        try:
            from .display_currency import get_display_currency
            _done_display_currency = get_display_currency(self.env)
        except Exception:
            _done_display_currency = 'USD'
        _visible = direct_formatted or ''
        if not _visible:
            from .history_compact import turn_shown_text
            _visible = turn_shown_text(messages, _turn_shown_start)
        if not _visible:
            for _m in reversed(messages):
                if _m.get('role') == 'user':
                    break
                if _m.get('role') != 'assistant' or _m.get('tool_calls'):
                    continue
                _cand = _m.get('content') or ''
                if _cand and not str(_cand).lstrip().startswith('[On-screen artifact'):
                    _visible = _cand
                    break
        _payload = None
        if isinstance(primary_artifact, dict):
            _payload = primary_artifact
        elif last_tabulable_payload:
            _payload = last_tabulable_payload
        _utterance = (self.env.context or {}).get('user_message') or ''
        if not isinstance(_utterance, str):
            _utterance = ''
        _utterance = _utterance.strip()
        if not _utterance and isinstance(message, str):
            _utterance = message
        try:
            from .history_compact import append_turn_stub
            _llm_history = append_turn_stub(
                kept_history, _utterance,
                payload=_payload, visible=_visible,
            )
        except Exception:
            _logger.debug(
                'AgentEngine: could not build LLM history stubs',
                exc_info=True,
            )
            _llm_history = list(kept_history)
        _done = {
            "event": "done",
            "session_id": session_id,
            "model": model_name,
            "provider": provider.name,
            "protocol": provider.protocol,
            "context_limit": provider.context_window or 0,
            "display_currency": _done_display_currency,
            "usage": usage_out or {},
            "sources": sorted(external_sources) if external_sources else [],
            "records": collected_records,
            "compose": getattr(
                self, '_turn_compose', None,
            ) or ('compose-model' if remote_llm_format else 'compose-agent'),
            "turn": getattr(self, '_turn_corr', None) or '',
            "history": _llm_history,
        }
        if export_chips:
            try:
                from .session_download import coalesce_download_chips
                _done['assistant_files'] = coalesce_download_chips(
                    export_chips,
                )
            except Exception:
                _done['assistant_files'] = list(export_chips)
        _ctx_show = (self.env.context or {}).get('presentation_show_mode')
        if _ctx_show:
            _done['presentation_show_mode'] = _ctx_show
        if export_clip_data:
            _done['clip_data'] = export_clip_data
        return _done
