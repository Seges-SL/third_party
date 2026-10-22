# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""Running one tool inside a turn, and what follows it (plan, rows, notices)."""

import json
import logging

from odoo import _
from .relaxaicode_render import render_context_from_env

_logger = logging.getLogger(__name__)


# Mock controlador (algunas tools piden request.env o _get_env_for_operation)
class DummyController:
    def __init__(self, agent_env, engine):
        self.env = agent_env
        self._engine = engine

    def _get_env_for_operation(self, operation_type='read'):
        ok, error = self._check_mcp_permissions(operation_type)
        if not ok:
            from odoo.exceptions import AccessError
            raise AccessError(error)
        return self.env

    def _get_readonly_env(self):
        from ..controllers.controller_helpers import get_readonly_env
        return get_readonly_env(self)

    def _check_mcp_permissions(self, operation_type='read'):
        from ..controllers.controller_helpers import (
            GROUP_AI_WRITER,
        )
        if (
            operation_type == 'write'
            and not self.env.user.has_group(GROUP_AI_WRITER)
        ):
            return False, (
                'Write permission denied: user is not in '
                'the AI Writer group.'
            )
        return True, ""

    def _log_mcp_operation(
        self,
        operation_type='read',
        tool_name='relaxaicode',
        prompt_data=None,
        result_data=None,
        result_summary=None,
        additional_info=None,
        code_to_execute=None,
        request_type=None,
        payload_type=None,
        context_type=None,
        agent_llm=None,
    ):
        # Reutiliza la correlación y el usuario del turno (engine),
        # para que la herramienta caiga en el mismo hilo del histórico.
        self._engine._mcp_log(
            operation_type=operation_type,
            tool_name=tool_name,
            prompt_data=prompt_data,
            result_data=result_data,
            result_summary=result_summary,
            additional_info=additional_info,
            code_to_execute=code_to_execute,
            request_type=request_type or 'tool',
            agent_llm=agent_llm,
        )

    def _get_user_locale(self):
        try:
            return self.env.user.lang or 'en_US'
        except Exception:
            return 'en_US'

    def _get_company_lang(self):
        try:
            return self.env.company.partner_id.lang or False
        except Exception:
            return False

    def _cancel_pending_verifications_for_user(self, user_id, reason="falta de permisos"):
        # Solo se usa en la rama de permiso denegado (no en flujo normal).
        return 0

    def _resolve_locale_placeholders(self, text_content):
        from ..utils.context_utils import resolve_placeholders
        return resolve_placeholders(text_content, self.env, controller=self)


class ToolRunMixin:
    """Part of ``AgentEngine``; only used through it."""

    def _tool_loop_inject_previous_result(self, turn, tool_name, tool_args):
        from .response_anti_echo import code_references_reuse_names

        # Nivel 2: inyectar previous_result si el código AST usa
        # previous_result/raw_data, O si pega un dataset module-level
        # (strip→rebind en tools_relaxaicode). Auto-inyectar siempre
        # colaba datasets de otro tema; el gate de literales cubre el
        # caso de literal de filas (rows=[{…}]) sin nombrar previous_result.
        if (
            tool_name == 'relaxaicode'
            and (turn.turn_query_data or turn.primary_artifact)
            and isinstance(tool_args, dict)
            and not tool_args.get('previous_result')
        ):
            _code = tool_args.get('code') or ''
            _need_prior = code_references_reuse_names(_code)
            if not _need_prior and _code:
                try:
                    from .relaxaicode_recipe import (
                        module_level_data_literal_error,
                    )
                    _need_prior = bool(
                        module_level_data_literal_error(_code)
                    )
                except Exception:
                    _need_prior = False
            if _need_prior:
                if turn.primary_artifact:
                    try:
                        from .primary_artifact import presentation_payload
                        tool_args['previous_result'] = (
                            presentation_payload(turn.primary_artifact)
                        )
                    except Exception:
                        tool_args['previous_result'] = {
                            'data': turn.turn_query_data,
                        }
                elif turn.turn_safe_plan_steps:
                    from .record_delivery_gate import (
                        previous_result_envelope_from_safe_plan,
                    )
                    tool_args['previous_result'] = (
                        previous_result_envelope_from_safe_plan(
                            turn.turn_safe_plan_steps,
                            rows=turn.turn_query_data,
                        )
                        or {'data': turn.turn_query_data}
                    )
                else:
                    tool_args['previous_result'] = {
                        'data': turn.turn_query_data,
                    }

    def _tool_loop_run_tool(
            self,
            MAX_ROUNDS,
            _blocked,
            _orig,
            _try_session_export,
            message,
            remote_llm_format,
            result,
            round_n,
            session_id,
            skip_table_footer,
            tool_args,
            tool_func,
            tool_name,
            turn,
    ):
        """Run one tool the model asked for and turn its answer into the result string."""
        if tool_func:
            try:
                if tool_name == 'safe_plan_request':
                    _blocked = self._intercept_session_file_propose(
                        _orig, session_id, tool_args,
                        rows=turn.turn_query_data,
                        payload=self._payload_for_screen(
                            turn.primary_artifact or turn.last_tabulable_payload,
                        ),
                    )
                if _blocked is not None:
                    result = _blocked['result']
                    if _blocked.get('attached'):
                        self._tool_loop_absorb_blocked(turn, _orig, _blocked)
                else:
                    result = self._tool_loop_call_tool(turn, tool_func, tool_args)
                try:
                    turn._render_ctx = render_context_from_env(
                        self.env,
                        result=turn._payload if isinstance(turn._payload, dict) else None,
                    )
                except Exception:
                    turn._render_ctx = None
                from .mcp_tool_payload import (
                    payload_has_tabular_rows,
                    unwrap_tool_payload,
                )
                turn._payload = unwrap_tool_payload(result) or (
                    result if isinstance(result, dict) else None
                )
                self._tool_loop_fulfill_page(turn, result, tool_args)
                self._harvest_file_labels(turn._payload)
                if tool_name == 'relaxaicode':
                    from .presentation_mode import layout_from_result
                    _layout = layout_from_result(turn._payload)
                    if _layout:
                        self.env = self.env(context=dict(
                            self.env.context or {}, presentation_show_mode=_layout,
                        ))
                _direct, _inspect_hidden, _tool_code = self._tool_loop_direct_candidate(
                    turn, result, tool_args, tool_name, message, round_n,
                    MAX_ROUNDS, remote_llm_format,
                )
                if _direct:
                    self._tool_loop_take_direct(
                        turn, _direct, _tool_code, remote_llm_format, skip_table_footer,
                    )
                self._tool_loop_note_outcome(turn, result, tool_name)
                from .mcp_tool_payload import tool_result_json_for_llm
                result_str = tool_result_json_for_llm(
                    result, remote_llm_format,
                    shown_to_user=not (
                        turn.last_tool_unmarked_probe or _inspect_hidden
                    ),
                )
                if (
                    tool_name == 'relaxaicode'
                    and (
                        (tool_args or {}).get('return_mode') == 'inspect_result'
                        or _inspect_hidden
                    )
                ):
                    turn.inspect_probes = (turn.inspect_probes or 0) + 1
                    from .error_ux import inspect_spin_nudge
                    extra = inspect_spin_nudge(turn.inspect_probes)
                    if extra:
                        result_str = '%s\n\n%s' % (result_str, extra)
                if remote_llm_format and payload_has_tabular_rows(
                    turn._payload if isinstance(turn._payload, dict) else None,
                ):
                    self._turn_sent_tabular_to_model = True
                # Ancla de reutilización: si una consulta de datos se
                # ejecutó BIEN, publicamos su código para que el worker lo
                # guarde en la sesión y lo reinyecte en el próximo turno
                # (ver prior_query_code). Solo el ÚLTIMO éxito del turno
                # cuenta (el worker se queda con el más reciente).
                if (
                    tool_name == 'relaxaicode'
                    and isinstance(result, dict)
                    and not result.get('error')
                    and not result.get('__force_retry__')
                ):
                    yield from self._tool_loop_keep_rows(
                        turn, result, tool_args, _try_session_export,
                    )
            except Exception as e:
                _logger.error(f"Error ejecutando {tool_name}: {e}")
                # Drop this tool's uncommitted writes (savepoint inside
                # _tool_loop_call_tool). Do not roll back the host cursor:
                # Chatboo's worker keeps session/job on it for the whole
                # turn. A caja B plan that already committed itself stays.
                self._drop_failed_tool_writes()
                try:
                    turn.last_retry_error = str(e) or turn.last_retry_error
                except Exception:
                    pass
                result_str = json.dumps({"error": str(e)})
        else:
            result_str = json.dumps({"error": f"Tool '{tool_name}' no encontrada en Odoo."})
        return (
            _blocked,
            result,
            result_str,
        )

    def _tool_loop_absorb_blocked(self, turn, _orig, _blocked):
        """The model proposed the download; it is attached to the session."""
        turn.export_attached = True
        turn.stop_after_direct = True
        self._absorb_export_result(turn, _blocked)
        self._remember_clip_data(turn,
            turn.primary_artifact or turn.last_tabulable_payload,
            turn.turn_query_data,
        )
        try:
            from .artifact_export import (
                export_hides_on_screen_table,
            )
            _hide = export_hides_on_screen_table(
                _orig,
                self._payload_for_screen(
                    turn.primary_artifact
                    or turn.last_tabulable_payload,
                ),
            )
        except Exception:
            _hide = True
        if turn.export_chips and (
            _hide or not turn.direct_formatted
        ):
            if _hide:
                turn.direct_formatted = ''
        elif _hide and not turn.export_chips:
            turn.direct_formatted = _(
                'Could not build the download file.'
            )

    def _drop_failed_tool_writes(self):
        """Drop cached rows the failed tool may have left after the savepoint.

        A TestCursor *is* the test transaction: do not touch it.
        Never ``cr.rollback()`` here — that would undo the Chatboo
        turn (session, job, later tools) sitting on the same cursor.
        """
        if type(self.env.cr).__name__ == 'TestCursor':
            return
        try:
            if hasattr(self.env, 'invalidate_all'):
                self.env.invalidate_all()
            else:
                self.env['base'].invalidate_cache()
        except Exception:
            pass

    def _run_tool_in_savepoint(self, run):
        """Run one tool without rolling back the rest of the turn.

        /mcp is one HTTP request per tool, so a full cursor rollback is
        right there. AgentEngine shares the host cursor for the whole
        turn. A savepoint drops only this tool's uncommitted writes.
        """
        cr = self.env.cr
        if type(cr).__name__ == 'TestCursor':
            return run()
        import uuid
        name = 'pns_tool_%s' % uuid.uuid4().hex
        try:
            cr.execute('SAVEPOINT "%s"' % name)
        except Exception:
            return run()
        try:
            result = run()
        except Exception:
            try:
                cr.execute('ROLLBACK TO SAVEPOINT "%s"' % name)
            except Exception:
                _logger.debug(
                    'AgentEngine: tool savepoint rollback skipped',
                    exc_info=True,
                )
            raise
        try:
            cr.execute('RELEASE SAVEPOINT "%s"' % name)
        except Exception:
            _logger.debug(
                'AgentEngine: tool savepoint release skipped',
                exc_info=True,
            )
        return result

    def _tool_loop_call_tool(self, turn, tool_func, tool_args):
        # Odoo's mcp_tools expect (controller, arguments)
        _ctl = DummyController(
            self.env(context=dict(
                self.env.context, pns_ai_untrusted_turn=True,
            ))
            if self._turn_untrusted else self.env,
            self,
        )
        # Lo que el turno ya colocó en un modelo viaja con la
        # llamada: si este paso rehace las filas sin tocar el
        # ORM, el id sigue sabiendo de quién es.
        from .turn_record_models import known_models
        _ctl.turn_record_models = known_models(
            turn.turn_record_models,
        )

        def _run():
            result = tool_func(_ctl, tool_args)
            self._turn_untrusted = True
            return result

        return self._run_tool_in_savepoint(_run)

    def _tool_loop_fulfill_page(self, turn, result, tool_args):
        """Fill the result page the code left waiting and offer its card."""
        if isinstance(turn._payload, dict):
            try:
                from .mcp_tool_payload import rewrap_tool_payload
                from .result_page import (
                    fulfill_waiting_page, has_page_url,
                    title_untitled_page,
                )
                _had_page = has_page_url(turn._payload)
                fulfill_waiting_page(self.env, turn._payload)
                title_untitled_page(
                    self.env, turn._payload,
                    (tool_args or {}).get('summary')
                    if isinstance(tool_args, dict) else '',
                )
                self._offer_page_card(turn._payload)
                if not _had_page and has_page_url(turn._payload):
                    rewrap_tool_payload(result, turn._payload)
            except Exception:
                _logger.debug(
                    'AgentEngine: waiting page failed',
                    exc_info=True,
                )

    def _tool_loop_note_outcome(self, turn, result, tool_name):
        """Note what the tool result means for the rest of the turn."""
        # Error recuperable (auto-corrección): guardar el texto por si
        # se agotan los turnos sin respuesta final.
        if isinstance(result, dict) and result.get('__force_retry__'):
            try:
                turn.last_retry_error = (result.get('content') or [{}])[0].get('text') or turn.last_retry_error
            except Exception:
                pass
            # Un hermano que pide reintento gana al stop del recurso.
            turn.stop_after_direct = False
        elif (
            tool_name == 'relaxaicode'
            and isinstance(result, dict)
            and not result.get('error')
            and not result.get('__force_retry__')
        ):
            turn.last_retry_error = None
            if isinstance(turn._payload, dict):
                from .report_outline_guard import (
                    contract_from_payload,
                )
                _free_report = contract_from_payload(turn._payload)
                if _free_report:
                    self._report_contract = _free_report
        # Enlaces a registros: refs (model,id,name) que relaxaicode
        # recolecta ANTES de consumir __model. Se leen del PAYLOAD ya
        # desempaquetado (unwrap_tool_payload), no del envoltorio MCP
        # {'content':[{'text':...}]}, donde viajan dentro del texto.
        # Se publican en collected_records → ficha del documento.
        if isinstance(turn._payload, dict) and turn._payload.get('__records__'):
            for _ref in (turn._payload.get('__records__') or []):
                if isinstance(_ref, dict):
                    self._add_record(turn,
                        _ref.get('model'), _ref.get('id'),
                        _ref.get('name'),
                        role=_ref.get('role'),
                    )
        if (
            isinstance(turn._payload, dict)
            and (
                turn._payload.get('__row_links__') is False
                or turn._payload.get('links') is False
            )
        ):
            turn.links_off_turn = True

    def _tool_loop_keep_rows(self, turn, result, tool_args, _try_session_export):
        """Publish the query and keep its rows for the next step and turn."""
        _qc = tool_args.get('code')
        if isinstance(_qc, str) and _qc.strip():
            yield {"event": "query_code", "code": _qc}
        # Guardar payload tabulable del turno (candado 1a).
        try:
            from .record_delivery_gate import first_tabular_rows
            from .relaxaicode_render import is_tabulable
            _src = turn._payload if isinstance(turn._payload, dict) else None
            if _src is None and isinstance(result, list):
                _src = {'data': result}
            if isinstance(_src, dict) and (
                is_tabulable(_src, force=True)
                or first_tabular_rows(_src)
            ):
                turn.last_tabulable_payload = _src
                self._harvest_file_labels(_src)
        except Exception:
            pass
        # Nivel 2: cachear las FILAS crudas del resultado (si las
        # hay) para reutilizarlas como previous_result el próximo
        # turno. Con topes de filas/bytes: si el dataset es enorme
        # no se cachea (se cae a reutilizar solo el código). Nunca
        # viaja al LLM: solo BD → namespace del sandbox.
        try:
            from .record_delivery_gate import first_tabular_rows
            _rows = first_tabular_rows(
                turn._payload if isinstance(turn._payload, dict) else result
            )
        except Exception:
            _rows = result.get('data') if isinstance(result, dict) else None
        if isinstance(_rows, list) and _rows:
            # Which model each id came from is learnt here,
            # before any size limit: the pairs are cheap and
            # a later step may rebuild these rows by hand.
            self._learn_row_models(turn, _rows)
            try:
                _max_bytes = self._dataset_cache_max_bytes()
                _payload_json = json.dumps(
                    _rows, default=str, ensure_ascii=False,
                )
                if (not _max_bytes or _max_bytes <= 0
                        or len(_payload_json.encode('utf-8'))
                        <= _max_bytes):
                    turn.turn_query_data = list(_rows)
                    self._harvest_file_labels(_rows)
                    yield {"event": "query_data", "data": _rows}
            except Exception:
                pass
        # Named download: persist the session chip as soon
        # as rows exist. Do not wait for MAX_ROUNDS or a
        # caja B propose (BHUX).
        _try_session_export()

    def _tool_loop_after_tool(
            self,
            _blocked,
            _try_session_export,
            remote_llm_format,
            result,
            tool_args,
            tool_name,
            turn,
    ):
        """After a tool ran: what the turn shows and what goes back to the model."""
        if (
            tool_name == 'safe_plan_request'
            and isinstance(result, dict)
            and _blocked is None
        ):
            yield from self._tool_loop_after_plan_request(
                turn, result, tool_args, _try_session_export, remote_llm_format,
            )

        # safe_plan_status: recupera resultados de operaciones
        # confirmadas MANUALMENTE (no whitelisted). El payload trae 'result'
        # con la lista de pasos ya ejecutados; de ahí sacamos las fuentes.
        elif tool_name == 'safe_plan_status' and isinstance(result, dict):
            yield from self._tool_loop_after_plan_status(
                turn, result, _try_session_export, remote_llm_format,
            )

    def _mint_card_token(self, verification_id):
        """Plaintext card token for the SSE event. Never put it in tool JSON."""
        vid = (verification_id or '').strip()
        if not vid or 'ai.safe.operation' not in self.env:
            return ''
        try:
            op = self.env['ai.safe.operation'].sudo().search(
                [('verification_id', '=', vid)], limit=1,
            )
            if not op or op.user_id.id != self.env.uid:
                return ''
            return op._mint_confirm_token()
        except Exception:
            _logger.debug(
                'MCP: could not mint card token for %s', vid, exc_info=True,
            )
            return ''

    def _tool_loop_after_plan_request(
            self, turn, result, tool_args, _try_session_export, remote_llm_format,
    ):
        """A proposed plan: choice or confirmation card, or what it already ran."""
        from .agent_engine import (
            _extract_direct_formatted_output,
            _resolve_direct_return,
        )
        try:
            _txt = (result.get('content') or [{}])[0].get('text')
            _info = json.loads(_txt) if _txt else {}
            # Only show the confirmation toast if the operation is
            # actually pending (not auto-confirmed low-risk ops).
            if (_info.get('success')
                    and _info.get('status') == 'pending_choice'
                    and _info.get('choice_id')):
                yield {
                    "event": "choice",
                    "choice_id": _info.get('choice_id'),
                    "title": _info.get('title') or '',
                    "items": _info.get('items') or [],
                }
                turn.stop_after_direct = True
                turn.direct_formatted = _('Pick the views in the chat.')
            elif (_info.get('success')
                    and _info.get('verification_id')
                    and _info.get('status') != 'confirmed'):
                vid = _info.get('verification_id')
                event = {
                    "event": "verification",
                    "verification_id": vid,
                    "title": _info.get('title') or '',
                    "plan": _info.get('plan') or [],
                    "danger_level": _info.get('danger_level') or 'medium',
                }
                token = self._mint_card_token(vid)
                if token:
                    event['confirm_token'] = token
                yield event
                # Do not let the LLM invent "already done" while the
                # toast is still waiting (o14pruebas / module.update).
                turn.stop_after_direct = True
                turn.direct_formatted = _('Confirm in Odoo to continue.')
            # Fuentes externas: cuando el plan se auto-confirma
            # (status='confirmed') se ejecuta AHORA, así que rastreamos
            # los pasos propuestos. Cubre fetch_url (dominio) y api_call
            # (servidor externo). La confirmación manual se rastrea al
            # recuperar el resultado con safe_plan_status.
            if _info.get('success') and _info.get('status') == 'confirmed':
                self._turn_effects_done = True
                self._collect_sources(turn, tool_args.get('steps'))
                self._collect_records_steps(turn, _info.get('result'))
                # Nivel 2: filas de api_call/fetch_url → turn_query_data
                # para que relaxaicode (strip/rebind) no reciba vacío.
                try:
                    from .record_delivery_gate import (
                        rows_from_safe_plan_steps,
                    )
                    turn._steps_res = _info.get('result')
                    # Legacy auto-confirm packed steps only in message.
                    if not isinstance(turn._steps_res, list):
                        _msg = _info.get('message') or ''
                        if isinstance(_msg, str) and '\n[' in _msg:
                            try:
                                turn._steps_res = json.loads(
                                    _msg.split('\n', 1)[1],
                                )
                            except Exception:
                                turn._steps_res = None
                    _api_rows = rows_from_safe_plan_steps(turn._steps_res)
                    if isinstance(turn._steps_res, list) and turn._steps_res:
                        turn.turn_safe_plan_steps = list(turn._steps_res)
                    if isinstance(_api_rows, list) and _api_rows:
                        self._learn_row_models(turn, _api_rows)
                        _max_bytes = self._dataset_cache_max_bytes()
                        _payload_json = json.dumps(
                            _api_rows, default=str, ensure_ascii=False,
                        )
                        if (not _max_bytes or _max_bytes <= 0
                                or len(_payload_json.encode('utf-8'))
                                <= _max_bytes):
                            turn.turn_query_data = list(_api_rows)
                            self._harvest_file_labels(_api_rows)
                            yield {
                                "event": "query_data",
                                "data": _api_rows,
                            }
                except Exception:
                    pass
                self._harvest_file_labels(turn._steps_res)
                if self._absorb_plan_downloads(turn, turn._steps_res):
                    yield {
                        "event": "replace",
                        "content": "",
                    }
                _try_session_export()
                # Presenters genéricos (skill_runtime) → HTML directo.
                _pres = _info.get('presentation')
                try:
                    from .artifact_export import wants_on_screen_blocks
                    if turn.export_chips and not wants_on_screen_blocks(
                        self._payload_for_screen(
                            turn.primary_artifact or turn.last_tabulable_payload,
                        ),
                    ):
                        _pres = None
                except Exception:
                    if turn.export_chips:
                        _pres = None
                if isinstance(_pres, dict) and (
                    _pres.get('data') is not None
                    or _pres.get('groups') is not None
                    or _pres.get('formatted_text')
                ):
                    from .skill_runtime import render_presentation_html
                    _html = render_presentation_html(
                        _pres, env=self.env,
                    ) or _resolve_direct_return(
                        _pres, render_context=turn._render_ctx,
                    ) or _extract_direct_formatted_output(
                        _pres, render_context=turn._render_ctx,
                    )
                    if _html:
                        if remote_llm_format:
                            # Report: do not auto-push; hand data+HTML
                            # to the LLM so it can embed charts.
                            turn.remote_tabular_handoff = _pres
                            turn.direct_formatted = None
                            turn.stop_after_direct = False
                            turn.table_already_delivered = True
                        else:
                            turn.direct_formatted = _html
                            turn.stop_after_direct = True
                            self._basket_push(turn, _pres)
        except Exception:
            pass

    def _tool_loop_after_plan_status(
            self, turn, result, _try_session_export, remote_llm_format,
    ):
        """Steps a human confirmed: sources, records, rows and their paint."""
        from .agent_engine import (
            _extract_direct_formatted_output,
            _resolve_direct_return,
        )
        try:
            _txt = (result.get('content') or [{}])[0].get('text')
            _info = json.loads(_txt) if _txt else {}
            if _info.get('success') and _info.get('executed'):
                _res = _info.get('result')
                if isinstance(_res, list):
                    self._collect_sources(turn, _res)
                    self._collect_records_steps(turn, _res)
                    try:
                        from .record_delivery_gate import (
                            rows_from_safe_plan_steps,
                        )
                        _api_rows = rows_from_safe_plan_steps(_res)
                        if isinstance(_res, list) and _res:
                            turn.turn_safe_plan_steps = list(_res)
                        if isinstance(_api_rows, list) and _api_rows:
                            self._learn_row_models(turn, _api_rows)
                            _max_bytes = self._dataset_cache_max_bytes()
                            _payload_json = json.dumps(
                                _api_rows, default=str,
                                ensure_ascii=False,
                            )
                            if (not _max_bytes or _max_bytes <= 0
                                    or len(_payload_json.encode('utf-8'))
                                    <= _max_bytes):
                                turn.turn_query_data = list(_api_rows)
                                self._harvest_file_labels(_api_rows)
                                yield {
                                    "event": "query_data",
                                    "data": _api_rows,
                                }
                    except Exception:
                        pass
                self._harvest_file_labels(_res)
                _try_session_export()
                if self._absorb_plan_downloads(turn, _res):
                    yield {
                        "event": "replace",
                        "content": "",
                    }
                _pres = _info.get('presentation')
                try:
                    from .artifact_export import wants_on_screen_blocks
                    if turn.export_chips and not wants_on_screen_blocks(
                        self._payload_for_screen(
                            turn.primary_artifact or turn.last_tabulable_payload,
                        ),
                    ):
                        _pres = None
                except Exception:
                    if turn.export_chips:
                        _pres = None
                if not _pres and isinstance(_res, list):
                    _allow_present = True
                    try:
                        from .artifact_export import wants_on_screen_blocks
                        if turn.export_chips and not wants_on_screen_blocks(
                            self._payload_for_screen(
                                turn.primary_artifact
                                or turn.last_tabulable_payload,
                            ),
                        ):
                            _allow_present = False
                    except Exception:
                        _allow_present = not bool(turn.export_chips)
                    if _allow_present:
                        try:
                            from .skill_runtime import try_present
                            _pres = try_present(
                                _res, steps=_res,
                            )
                        except Exception:
                            _pres = None
                if isinstance(_pres, dict) and (
                    _pres.get('data') is not None
                    or _pres.get('groups') is not None
                    or _pres.get('formatted_text')
                ):
                    from .skill_runtime import render_presentation_html
                    _html = render_presentation_html(
                        _pres, env=self.env,
                    ) or _resolve_direct_return(
                        _pres, render_context=turn._render_ctx,
                    ) or _extract_direct_formatted_output(
                        _pres, render_context=turn._render_ctx,
                    )
                    if _html:
                        if remote_llm_format:
                            turn.remote_tabular_handoff = _pres
                            turn.direct_formatted = None
                            turn.stop_after_direct = False
                            turn.table_already_delivered = True
                        else:
                            turn.direct_formatted = _html
                            turn.stop_after_direct = True
                            self._basket_push(turn, _pres)
        except Exception:
            pass

    def _log_agent_tool_step(self, tool_name, tool_args, result_str, model_name):
        # relaxaicode registra en tool_relaxaicode (incl. code_to_execute)
        if (tool_name or '').lower() == 'relaxaicode':
            return
        operation_type = 'read'
        result_summary = '← Tool→ORCH ' + (result_str or '')[:480]
        if (tool_name or '') == 'safe_plan_request':
            operation_type = 'write'
            from .mcp_tool_payload import summarize_safe_plan_request
            result_summary = summarize_safe_plan_request(result_str)
        self._mcp_log(
            operation_type=operation_type,
            tool_name=tool_name,
            prompt_data=tool_args,
            result_summary=result_summary,
            request_type='tool',
            agent_llm=model_name,
        )
