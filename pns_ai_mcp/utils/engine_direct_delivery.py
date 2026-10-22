# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""Direct delivery of a turn: tables on screen, session export, delivery gate."""

import json
import logging

from odoo import _
from .relaxaicode_render import (
    maybe_attach_formatted_text,
    render_context_from_env,
    wrap_bare_images_clickable,
)

_logger = logging.getLogger(__name__)


class DirectDeliveryMixin:
    """Part of ``AgentEngine``; only used through it."""

    def _tool_loop_report_outline(
            self, messages, _turn_loop_from, _final, content_buffer, session_id,
    ):
        try:
            from .report_outline_guard import (
                ensure_report_completion,
                recover_turn_report_body,
            )
            _rc = getattr(self, '_report_contract', None) or {}
            _recovered = recover_turn_report_body(
                messages[_turn_loop_from:],
                _final,
                _rc.get('report_outline'),
            )
            _recovered_changed = (
                (_recovered or '').strip()
                != (_final or '').strip()
            )
            if _recovered_changed:
                _final = _recovered
            _patched, _changed = ensure_report_completion(
                _final,
                outline=_rc.get('report_outline'),
                closing=_rc.get('closing_required'),
                recommendations_stub=_rc.get('recommendations_stub'),
                recommendations_heading=_rc.get(
                    'recommendations_heading',
                ),
            )
            if _changed:
                _final = _patched
            if _recovered_changed or _changed:
                content_buffer = _final
                yield {"event": "replace", "content": _final}
                _logger.info(
                    'agent_engine: report outline completed '
                    '(session=%s recovered=%s filled=%s)',
                    session_id,
                    _recovered_changed,
                    _changed,
                )
        except Exception as _outline_exc:
            _logger.debug(
                'report outline guard skipped: %s', _outline_exc,
            )
        return _final, content_buffer

    def _tool_loop_keep_delivered(self, turn, html):
        """Keep in the bubble the table this turn already painted."""
        from .record_delivery_gate import bubble_with_delivered
        return bubble_with_delivered(turn.delivered_html, html)

    def _tool_loop_delivery_gate(
            self, turn, _final, content_buffer, prior_table_fps,
            remote_llm_format, session_id,
    ):
        """Force the table, link the records and drop echoed tables."""
        from .response_anti_echo import (
            extract_dataset_fingerprints,
            strip_echoed_table_blocks,
        )
        _forced_html = None
        try:
            from .record_delivery_gate import (
                should_force_turn_payload,
            )
            from .record_linkify import seal_record_links

            def _seal(text):
                return seal_record_links(
                    text, turn.collected_records,
                    links_off=turn.links_off_turn,
                )

            _final, content_buffer = yield from self._tool_loop_report_tables(
                turn, _final, content_buffer, remote_llm_format, session_id,
            )

            # /compose-agent candado: local HTML when compose-model is off.
            if (
                not remote_llm_format
                and should_force_turn_payload(
                    _final,
                    last_tabulable_payload=turn.last_tabulable_payload,
                    table_already_delivered=turn.table_already_delivered,
                )
            ):
                _forced_html = self._tool_loop_render_forced(turn.last_tabulable_payload)
            # 1b desactivado: nunca forzar prior_query_data a la burbuja.

            if _forced_html:
                turn.table_already_delivered = True
                try:
                    turn.turn_table_fps |= extract_dataset_fingerprints(
                        _forced_html,
                    )
                except Exception:
                    pass
                _prose = _seal(_final)
                if (_prose or '').strip() and not (
                    'o_ai_table_block' in (_prose or '')
                ):
                    _final = _forced_html + '\n\n' + _prose.strip()
                else:
                    _final = _forced_html
                try:
                    _final = strip_echoed_table_blocks(
                        _final,
                        prior_table_fps,
                        allow_fingerprints=turn.turn_table_fps,
                    )
                except Exception:
                    pass
                _final = _seal(self._tool_loop_keep_delivered(turn, _final))
                yield {"event": "replace", "content": _final}
            else:
                try:
                    _stripped = strip_echoed_table_blocks(
                        _final,
                        prior_table_fps,
                        allow_fingerprints=turn.turn_table_fps,
                    )
                except Exception:
                    _stripped = _final
                _final = _seal(self._tool_loop_keep_delivered(turn, _stripped))
                if _final != content_buffer:
                    yield {"event": "replace", "content": _final}
        except Exception as _gate_err:
            _logger.debug(
                'record delivery gate skipped: %s', _gate_err,
            )

    def _tool_loop_render_forced(self, _payload):
        import copy as _copy

        if not isinstance(_payload, dict):
            return None
        _p = _copy.deepcopy(_payload)
        _p.pop('formatted_text', None)
        try:
            _rcx = render_context_from_env(self.env, result=_p)
        except Exception:
            _rcx = None
        maybe_attach_formatted_text(
            _p,
            summary=_p.get('summary') or '',
            render_context=_rcx,
            force=True,
        )
        _ft = _p.get('formatted_text')
        if not _ft:
            return None
        return wrap_bare_images_clickable(_ft, env=self.env)

    def _tool_loop_report_tables(
            self, turn, _final, content_buffer, remote_llm_format, session_id,
    ):
        from .response_anti_echo import extract_dataset_fingerprints

        # Skill report: append bootstrap tables (with charts) after
        # the LLM prose as a fallback. The model may also embed
        # formatted_text itself — duplicate blocks are acceptable
        # vs silently dropping native charts.
        _rtp = getattr(self, '_report_tables_payload', None)
        if remote_llm_format and isinstance(_rtp, dict):
            _rtp = dict(_rtp)
            _rtp['__subtle_zebra__'] = True
            _tables_html = self._tool_loop_render_forced(_rtp)
            self._report_tables_payload = None
            if _tables_html:
                turn.table_already_delivered = True
                try:
                    turn.turn_table_fps |= extract_dataset_fingerprints(
                        _tables_html,
                    )
                except Exception:
                    pass
                _prose = (_final or '').strip()
                # Markdown → HTML so mixed report+tables keep headings.
                if _prose:
                    try:
                        from .relaxaicode_render import (
                            _markdownish_to_html,
                        )
                        _prose_html = _markdownish_to_html(_prose)
                    except Exception:
                        _prose_html = ''
                    if not _prose_html:
                        import html as _html_mod
                        _prose_html = _html_mod.escape(_prose)
                    _host = (
                        '<div class="o_ai_prose_host '
                        'o_ai_prose">%s</div>'
                        % _prose_html
                    )
                    _final = _host + '\n\n' + _tables_html
                else:
                    _final = _tables_html
                content_buffer = _final
                yield {"event": "replace", "content": _final}
                _logger.info(
                    'agent_engine: report tables HTML appended '
                    '(session=%s)',
                    session_id,
                )
        return _final, content_buffer

    def _tool_loop_session_export(
        self, turn, _orig, session_id, messages, round_n, MAX_ROUNDS,
    ):
        """Persist the named download as a session chip; stop ReAct."""
        if turn.export_attached:
            return True
        try:
            from .artifact_export import (
                requested_named_format,
                wants_on_screen_blocks,
                export_hides_on_screen_table,
                tabular_rows,
                has_export_meta,
                SESSION_FILE_META_PROTOCOL,
            )
        except Exception:
            requested_named_format = None
            wants_on_screen_blocks = lambda *_a, **_k: False
            export_hides_on_screen_table = lambda *_a, **_k: False
            tabular_rows = lambda *_a, **_k: None
            has_export_meta = lambda *_a, **_k: True
            SESSION_FILE_META_PROTOCOL = ''
        named = (
            requested_named_format(_orig)
            if requested_named_format else None
        )
        payload = self._payload_for_screen(
            turn.primary_artifact or turn.last_tabulable_payload,
        )
        show_blocks = wants_on_screen_blocks(payload, turn.turn_query_data)
        has_rows = bool(turn.turn_query_data) or bool(
            tabular_rows(payload, turn.turn_query_data)
        )
        if named and has_rows:
            self._remember_clip_data(turn, payload, turn.turn_query_data)
        if (
            named and has_rows
            and not has_export_meta(payload)
            and round_n < MAX_ROUNDS
        ):
            if not turn.export_meta_nudged:
                turn.export_meta_nudged = True
                turn.export_meta_nudge_round = round_n
                if SESSION_FILE_META_PROTOCOL:
                    messages.append({
                        'role': 'system',
                        'content': SESSION_FILE_META_PROTOCOL,
                    })
                return False
            if round_n == turn.export_meta_nudge_round:
                return False
        _ex = self._attach_requested_file_export(
            _orig, session_id,
            rows=turn.turn_query_data,
            payload=payload,
        )
        if _ex and _ex.get('acted'):
            turn.export_attached = True
            chips = self._absorb_export_result(turn, _ex)
            if chips and named and not show_blocks:
                turn.direct_formatted = ''
                turn.stop_after_direct = True
            elif named and not chips and export_hides_on_screen_table(
                _orig, payload,
            ):
                turn.stop_after_direct = True
                turn.direct_formatted = _(
                    'Could not build the download file.'
                )
            elif not show_blocks:
                turn.stop_after_direct = True
            return True
        has_rows = bool(turn.turn_query_data) or bool(
            tabular_rows(payload, turn.turn_query_data)
        )
        if named and has_rows:
            _logger.warning(
                'AgentEngine: named download did not persist a chip'
            )
            if export_hides_on_screen_table(_orig, payload):
                turn.stop_after_direct = True
                turn.direct_formatted = _(
                    'Could not build the download file.'
                )
            elif not show_blocks:
                turn.stop_after_direct = True
        return False

    def _tool_loop_direct_close(
            self,
            MAX_ROUNDS,
            _orig,
            _try_session_export,
            messages,
            prior_table_fps,
            round_n,
            skip_table_footer,
            turn,
    ):
        """Paint the table the tools built; True when the turn ends here."""
        _hide_table = self._tool_loop_prepare_direct(
            turn, _orig, prior_table_fps, _try_session_export,
        )
        self._stamp_refused_note(turn)
        waiting_meta = (
            not turn.export_attached
            and turn.export_meta_nudged
            and round_n == turn.export_meta_nudge_round
        )
        if waiting_meta:
            turn.stop_after_direct = False
            if not _hide_table:
                turn.delivered_html = turn.direct_formatted or ''
                yield {
                    "event": "replace",
                    "content": turn.direct_formatted,
                }
        elif turn.stop_after_direct or skip_table_footer:
            # Skill HTML / lacónico / stop explícito: sin 2.ª vuelta LLM.
            # Si es skill y el proveedor no es lacónico, pie cálido LOCAL
            # (servidor) — humanos lo echan de menos; Sonnet inventaba el año.
            if turn.local_warm_footer and turn.direct_formatted:
                from .mcp_tool_payload import append_local_warm_footer
                turn.direct_formatted = append_local_warm_footer(
                    turn.direct_formatted,
                    footer_text=turn.local_footer_text or _('Here you go. If you need anything else, just tell me.'),
                )
            turn.finished_with_answer = True
            if turn.direct_formatted or (_hide_table and turn.export_chips):
                yield {"event": "replace", "content": turn.direct_formatted or ''}
            return True
        elif round_n >= MAX_ROUNDS:
            # Última ronda permitida: entregar tabla sin exigir pie LLM extra.
            # Un lookup sin marcar (catálogo + registros) no es la respuesta.
            if turn.last_tool_unmarked_probe and not turn.delivered_marked:
                return True
            if turn.local_warm_footer and turn.direct_formatted:
                from .mcp_tool_payload import append_local_warm_footer
                turn.direct_formatted = append_local_warm_footer(
                    turn.direct_formatted,
                    footer_text=turn.local_footer_text or _('Here you go. If you need anything else, just tell me.'),
                )
            elif not skip_table_footer and turn.direct_formatted:
                from .mcp_tool_payload import append_local_warm_footer
                turn.direct_formatted = append_local_warm_footer(
                    turn.direct_formatted,
                    footer_text=_('Here you go. If you need anything else, just tell me.'),
                )
            turn.finished_with_answer = True
            if turn.direct_formatted:
                yield {"event": "replace", "content": turn.direct_formatted}
            return True
        else:
            yield from self._tool_loop_table_then_footer(turn, messages)
        return False

    def _tool_loop_prepare_direct(self, turn, _orig, prior_table_fps, _try_session_export):
        """Drop echoed tables, merge the basket; True when only the file was asked."""
        from .response_anti_echo import (
            extract_dataset_fingerprints,
            strip_echoed_table_blocks,
        )
        try:
            turn.turn_table_fps |= extract_dataset_fingerprints(
                turn.direct_formatted,
            )
            turn.direct_formatted = strip_echoed_table_blocks(
                turn.direct_formatted,
                prior_table_fps,
                allow_fingerprints=turn.turn_table_fps,
            )
        except Exception:
            pass
        # Turn presentation basket: merge N parallel presentable results
        # into one bubble (orthogonal to report vs table formatting).
        _hide_table = False
        try:
            from .artifact_export import export_hides_on_screen_table
            _hide_table = export_hides_on_screen_table(
                _orig,
                self._payload_for_screen(
                    turn.primary_artifact or turn.last_tabulable_payload,
                ),
            )
        except Exception:
            _hide_table = False
        if not _hide_table:
            turn.direct_formatted = self._basket_html_for_replace(turn, turn.direct_formatted)
        _try_session_export()
        try:
            from .artifact_export import wants_on_screen_blocks
            if (
                turn.export_chips
                and not wants_on_screen_blocks(
                    self._payload_for_screen(
                        turn.primary_artifact or turn.last_tabulable_payload,
                    ),
                )
            ):
                _hide_table = True
        except Exception:
            if turn.export_chips:
                _hide_table = True
        if _hide_table and turn.export_chips:
            turn.direct_formatted = ''
        return _hide_table

    def _tool_loop_table_then_footer(self, turn, messages):
        # Modelo capaz: tabla + pie conversacional breve (sin cifras).
        if turn.direct_formatted:
            turn.delivered_html = turn.direct_formatted
            yield {"event": "replace", "content": turn.direct_formatted}
        try:
            _rows = max(0, str(turn.direct_formatted).count('<tr') - 1)
        except Exception:
            _rows = None
        if messages and messages[-1].get('role') == 'tool':
            from .report_outline_guard import followup_note_after_tables
            _row_label = _rows if _rows is not None else '?'
            messages[-1]['content'] = json.dumps({
                'data_rendered': True,
                'rows_rendered': _rows,
                'primary_delivered': True,
                'note': followup_note_after_tables(
                    _row_label,
                    getattr(self, '_report_contract', None),
                ),
            }, ensure_ascii=False)
        turn.direct_formatted = None

    def _tool_loop_remote_handoff(self, turn, messages):
        try:
            from .mcp_tool_payload import (
                remote_format_handoff_payload,
                remote_owns_tabular_presentation,
            )
            if remote_owns_tabular_presentation(
                True, turn.remote_tabular_handoff,
            ):
                _handoff = remote_format_handoff_payload(
                    turn.remote_tabular_handoff,
                )
                if _handoff:
                    messages[-1]['content'] = json.dumps(
                        _handoff, ensure_ascii=False, default=str,
                    )
                    self._turn_sent_tabular_to_model = True
        except Exception:
            pass
        turn.remote_tabular_handoff = None

    def _tool_loop_direct_candidate(
            self, turn, result, tool_args, tool_name, message, round_n,
            MAX_ROUNDS, remote_llm_format,
    ):
        """The HTML this result would paint in the chat, or None."""
        from .agent_engine import (
            _extract_direct_formatted_output,
            _resolve_direct_return,
            _should_show_direct_to_chat,
        )
        from .mcp_tool_payload import local_owns_tabular_paint
        _force_retry = bool(
            isinstance(result, dict) and result.get('__force_retry__')
        )
        _direct = _resolve_direct_return(
            result, render_context=turn._render_ctx,
        )
        if not _direct:
            _direct = _extract_direct_formatted_output(
                result, render_context=turn._render_ctx,
            )
        _tool_code = (
            tool_args.get('code') if isinstance(tool_args, dict) else ''
        ) or ''
        _pa_action = None
        if isinstance(turn._payload, dict):
            try:
                from .primary_artifact import classify_vs_primary
                _pa_action = classify_vs_primary(
                    turn.primary_artifact, turn._payload, code=_tool_code,
                )
            except Exception:
                _pa_action = None
        _um_gate = (
            (self.env.context or {}).get('user_message') or message
        )
        _ulang_gate = None
        try:
            _ulang_gate = self.env.user.lang
        except Exception:
            _ulang_gate = None
        if _direct and not _should_show_direct_to_chat(
            turn._payload,
            round_n=round_n,
            max_rounds=MAX_ROUNDS,
            tool_name=tool_name,
            force_retry=_force_retry,
            has_primary=bool(turn.primary_artifact),
            user_message=_um_gate,
            user_lang=_ulang_gate,
        ):
            _direct = None
        # Catalogue + records in one result is a lookup, not the
        # answer. Do not paint it, even on the last round.
        from .direct_return_policy import is_unmarked_multi_probe
        _unmarked_probe = (
            tool_name == 'relaxaicode'
            and isinstance(turn._payload, dict)
            and is_unmarked_multi_probe(turn._payload)
        )
        if _unmarked_probe:
            _direct = None
            turn.last_tool_unmarked_probe = True
            if not turn.delivered_marked:
                turn.direct_formatted = None
                turn.table_already_delivered = False
        else:
            turn.last_tool_unmarked_probe = False
        _inspect_only = (
            tool_name == 'relaxaicode'
            and isinstance(tool_args, dict)
            and tool_args.get('return_mode') == 'inspect_result'
        )
        # compose-agent + tabla: stub al modelo y pintar aquí
        # aunque el payload no traiga __return_direct__ (V0MJ).
        if not _unmarked_probe and local_owns_tabular_paint(
            remote_llm_format, turn._payload, force_retry=_force_retry,
            inspect_only=_inspect_only,
        ):
            if not _direct and isinstance(turn._payload, dict):
                try:
                    maybe_attach_formatted_text(
                        turn._payload,
                        summary=turn._payload.get('summary') or '',
                        render_context=turn._render_ctx,
                        force=True,
                    )
                except Exception:
                    pass
                _direct = _extract_direct_formatted_output(
                    turn._payload, render_context=turn._render_ctx,
                ) or turn._payload.get('formatted_text')
        _inspect_hidden = _inspect_only and not _direct
        try:
            from .artifact_export import (
                export_hides_on_screen_table,
                wants_on_screen_blocks,
            )
            if (
                _direct
                and export_hides_on_screen_table(
                    _um_gate, self._payload_for_screen(turn._payload),
                )
                and not wants_on_screen_blocks(
                    self._payload_for_screen(turn._payload),
                )
            ):
                _direct = None
            if (
                _direct
                and turn.export_chips
                and not wants_on_screen_blocks(
                    self._payload_for_screen(turn._payload),
                )
            ):
                _direct = None
        except Exception:
            if _direct and turn.export_chips:
                _direct = None
        if (
            _direct
            and _pa_action == 'probe'
            and turn.primary_artifact
        ):
            _direct = None
        return _direct, _inspect_hidden, _tool_code

    def _tool_loop_take_direct(
            self, turn, _direct, _tool_code, remote_llm_format, skip_table_footer,
    ):
        """Hand the table to the remote model or keep it to paint here."""
        from .direct_return_policy import is_chat_deliverable
        from .mcp_tool_payload import is_author_html_payload
        # High-level switch: remote owns ordinary tables;
        # author_html / local path unchanged when flag OFF.
        from .mcp_tool_payload import (
            remote_owns_tabular_presentation,
        )
        if remote_owns_tabular_presentation(
            remote_llm_format, turn._payload,
        ):
            turn.remote_tabular_handoff = (
                turn._payload if isinstance(turn._payload, dict) else None
            )
            # Handoff counts as delivery for candado 1a —
            # otherwise a Markdown answer gets an HTML+chart
            # table re-injected at turn end.
            turn.table_already_delivered = True
        else:
            turn.direct_formatted = _direct
            turn.table_already_delivered = True
            if is_chat_deliverable(turn._payload):
                turn.delivered_marked = True
            self._basket_push(turn, turn._payload, _tool_code)
            # HTML de skill/código (author_html): sin 2.ª vuelta de
            # pie — el modelo inventaba años o cifras.
            # Tablas server_side_python: pie solo si foot-verbose
            # (se decide más abajo con skip_table_footer).
            if is_author_html_payload(turn._payload):
                turn.stop_after_direct = True
                # Humanos quieren pie; el LLM inventaba el año →
                # pie fijo del servidor (traducible), sin 2.ª vuelta.
                # Pero cada skill decide: puede omitirlo (listados
                # con su propio contador) o componer el suyo.
                if not skip_table_footer:
                    from .mcp_tool_payload import (
                        resolve_author_footer,
                    )
                    _suppress, _ftext = resolve_author_footer(
                        turn._payload,
                    )
                    if not _suppress:
                        turn.local_warm_footer = True
                        turn.local_footer_text = _ftext
            elif (turn._payload or {}).get('__stop_after_direct__'):
                turn.stop_after_direct = True
            elif skip_table_footer and (
                (turn._payload or {}).get('__direct_return__')
                or (turn._payload or {}).get('__return_direct__')
            ):
                turn.stop_after_direct = True
