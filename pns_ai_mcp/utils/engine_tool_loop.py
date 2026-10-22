# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""The tool loop of one provider: model rounds, tool calls, closing reply."""

import functools
import json
import logging
import time

from odoo import _
from .llm_usage import add_usage
from .agent_stream_text import (
    pretool_progress_status as _pretool_progress_status,
    strip_think_blocks as _strip_think_blocks,
)

_logger = logging.getLogger(__name__)


class _TurnState:
    """What the tool loop and its inner helpers change together in one turn."""

    __slots__ = (
        '_payload',
        '_records_seen',
        '_render_ctx',
        '_steps_res',
        'collected_records',
        'delivered_html',
        'delivered_marked',
        'direct_formatted',
        'export_attached',
        'export_chips',
        'export_clip_data',
        'export_meta_nudge_round',
        'export_meta_nudged',
        'export_refused_tokens',
        'external_sources',
        'finished_with_answer',
        'inspect_probes',
        'last_retry_error',
        'last_tabulable_payload',
        'last_tool_unmarked_probe',
        'links_off_turn',
        'local_footer_text',
        'local_warm_footer',
        'primary_artifact',
        'remote_tabular_handoff',
        'stop_after_direct',
        'table_already_delivered',
        'turn_presentation_basket',
        'turn_query_data',
        'turn_record_models',
        'turn_safe_plan_steps',
        'turn_table_fps',
    )

    def __init__(self):
        # Red de seguridad para auto-corrección: si el modelo agota las rondas
        # reintentando código erróneo sin dar respuesta final, mostramos el último
        # error técnico en vez de dejar el chat en blanco.
        self.finished_with_answer = False
        self.inspect_probes = 0
        self.last_tool_unmarked_probe = False
        self.delivered_marked = False
        self.export_attached = False
        self.export_chips = []
        self.export_refused_tokens = []
        self.stop_after_direct = False
        self.export_clip_data = None
        self.export_meta_nudged = False
        self.export_meta_nudge_round = 0
        self.last_retry_error = None
        # Fuentes externas consultadas: dominios de fetch_url y servidores API.
        # Sirve tanto para pasos PROPUESTOS (tool_args de safe_plan_request,
        # auto-confirmados) como para pasos YA EJECUTADOS que se recuperan luego con
        # safe_plan_status (confirmación manual). Ambos comparten la misma
        # forma: dicts con 'op' + 'url' (fetch_url) o 'server'/'tool' (api_call).
        self.external_sources = set()
        # Registros Odoo referenciados en el turno (para pintarlos como enlaces
        # clicables en Chatboo). DETERMINISTA: salen de resultados REALES de
        # herramientas —filas de relaxaicode con id+__model y operaciones
        # CRUD confirmadas del safe plan—, NO de que el modelo los cite bien.
        self.collected_records = []
        self._records_seen = set()
        # Qué modelo tenía cada id ya identificado en ESTE turno. Un paso de
        # presentación suele rehacer las filas desde un literal: mismos ids,
        # ningún recordset vivo que diga de dónde salieron.
        self.turn_record_models = {}
        # Candado de entrega de registros (sin léxico): payload tabulable del
        # turno y si ya se hizo replace con tabla.
        # ``delivered_html`` es lo que el cliente tiene ya en la burbuja: un
        # replace la fija entera, así que el cierre no puede mandar prosa a
        # secas sin borrar la tabla que este turno pintó.
        self.delivered_html = ''
        self.last_tabulable_payload = None
        self.direct_formatted = None
        self.table_already_delivered = False
        self.links_off_turn = False
        # Multi-tool presentable results (same user turn) — see
        # docs/decisions/turn_presentation_basket.md
        self.turn_presentation_basket = []
        # First complete artifact of the turn (never replaced by a later probe).
        # See docs/decisions/primary_artifact.md
        self.primary_artifact = None


class ToolLoopMixin:
    """Part of ``AgentEngine``; only used through it."""

    def _dataset_cache_max_bytes(self):
        """Tope en BYTES serializados del cache de dataset (Nivel 2), configurable
        por parámetro de sistema. 0 o negativo = sin límite. Ante cualquier fallo
        cae al default del módulo."""
        from .agent_engine import AGENT_DATASET_CACHE_MAX_BYTES
        try:
            return int(self.env['ir.config_parameter'].sudo().get_param(
                'pns_ai_mcp.dataset_cache_max_bytes', AGENT_DATASET_CACHE_MAX_BYTES))
        except (TypeError, ValueError):
            return AGENT_DATASET_CACHE_MAX_BYTES

    def _run_stream_with_provider(self, message, history, session_id, agent_code, provider, prior_query_code=None, prior_query_data=None, screen_context_block=None, images=None, recall_images=None):
        """Single-provider ReAct stream; raises ProviderConnectionError on LLM connection failure."""
        turn = _TurnState()
        from .agent_engine import (
            LLM_AGENT_WALL_TIMEOUT,
            TurnTimeExceeded,
        )

        try:
            from .artifact_export import (
                is_refused_export,
                REFUSED_EXPORT_REPLY,
            )
        except Exception:
            is_refused_export = None
            REFUSED_EXPORT_REPLY = ''
        try:
            from .artifact_export import turn_export_utterance
            _orig = turn_export_utterance(self.env, message)
        except Exception:
            _orig = (self.env.context or {}).get('user_message') or message
        if is_refused_export and is_refused_export(_orig):
            yield {
                'event': 'replace',
                'content': _(REFUSED_EXPORT_REPLY),
            }
            yield self._done_event(session_id, local=True)
            return
        # Dataset del turno: empieza con el cache de sesión y se actualiza tras
        # cada RelaxAICode exitosa, para que la 2.ª llamada (pijama/estilo) pueda
        # pedir raw_data/previous_result cuando el código lo referencia (AST).
        turn.turn_query_data = list(prior_query_data) if prior_query_data else None
        try:
            from .session_download import file_labels_from_mapping
            _labels = (self.env.context or {}).get('file_label_by_id')
            if isinstance(_labels, dict) and turn.turn_query_data:
                file_labels_from_mapping(turn.turn_query_data, _labels)
        except Exception:
            pass
        turn.turn_safe_plan_steps = None
        # Anti-eco: huellas de tablas ya mostradas en historial assistant.
        # Las regeneradas este turno (tools) se permiten aunque coincidan.
        from .response_anti_echo import (
            fingerprints_from_history,
        )
        prior_table_fps = set()
        turn.turn_table_fps = set()
        (
            agent, config, model_name, remote_llm_format, skip_table_footer,
        ) = self._tool_loop_provider_config(
            agent_code=agent_code,
            message=message,
            provider=provider,
            session_id=session_id,
        )
        
        # Arquitectura (docs/dos_credenciales_api.md): Chatboo/internal infiere aquí
        # in-process; NO reentra en /mcp ni usa ai.mcp.user.mcp_api_key_hash.
        # Las tools van vía tool_func(DummyController(self.env), ...).
        # ai.provider.api_key sí se usa (HTTP al LLM), leída en _api_key_for_inference().
        # X-Mcp-Token del usuario no se propaga al LLM: secreto sin uso en este camino.

        # 2. Preparar Mensajes (Inyección del System Prompt)
        system_msg = self.get_system_prompt(
            agent_code=agent_code,
            user_message=(
                (self.env.context or {}).get('user_message') or message
            ),
        )
        if not getattr(self, '_reuse_prior_query', True):
            prior_query_data = None
            prior_query_code = None
            turn.turn_query_data = None
        yield self._domain_codes_event()

        # 3. Cargar Herramientas
        (
            _turn_shown_start, clean_history, kept_history, messages,
            prior_table_fps, tools,
        ) = self._tool_loop_messages(
            _orig=_orig,
            fingerprints_from_history=fingerprints_from_history,
            history=history,
            images=images,
            message=message,
            prior_query_code=prior_query_code,
            prior_query_data=prior_query_data,
            prior_table_fps=prior_table_fps,
            provider=provider,
            recall_images=recall_images,
            remote_llm_format=remote_llm_format,
            screen_context_block=screen_context_block,
            system_msg=system_msg,
        )

        if len(kept_history) < len(clean_history):
            dropped = len(clean_history) - len(kept_history)
            _logger.info(
                "AgentEngine: historial recortado para ajustar al contexto "
                "(%s mensaje(s) antiguo(s) descartado(s); ventana=%s)",
                dropped, provider.context_window or 0,
            )
            yield {"event": "status", "message": _('Fitting the history to the context (older turns are dropped)…')}

        yield {"event": "status", "message": _('Connecting to %s (active tools: %s)…') % (model_name, len(tools))}

        # --- BUCLE REACT NATIVO ---
        # Política del bucle ReAct: vive en el agente (resuelto arriba). Si no
        # hay agente o el valor es <= 0, usa el default (10).
        MAX_ROUNDS = (agent.max_agent_rounds if (agent and (agent.max_agent_rounds or 0) > 0) else 10)
        round_n = 0
        agent_started = time.monotonic()
        # Tokens de la ronda LLM en curso (se resetea cada vuelta).
        usage_info = {}
        # Suma de todas las rondas del turno (pie + histórico diario).
        turn_usage = {}
        side_at_start = dict(self._side_usage())
        add_usage(turn_usage, side_at_start)
        last_round_total = 0
        # Las filas que el cliente reinyecta ya pasaron por una pantalla y
        # dicen de qué modelo son: un turno que las rehaga sin tocar el ORM
        # sigue sabiendo a qué registro apunta cada id.
        if prior_query_data:
            from .turn_record_models import remember_rows
            remember_rows(turn.turn_record_models, prior_query_data)

        from ..controllers.mcp_decorators import get_tool_function
        # Assistant/tool messages of THIS turn only (history stays below).
        _turn_loop_from = len(messages)
        
        while round_n < MAX_ROUNDS:
            if time.monotonic() - agent_started > LLM_AGENT_WALL_TIMEOUT:
                raise TurnTimeExceeded(
                    _('Maximum response time exceeded (%ss). Please try again.')
                    % LLM_AGENT_WALL_TIMEOUT
                )
            round_n += 1
            usage_info = {}
            yield {"event": "status", "message": _("Thinking (round %s)…") % round_n}
            (
                _defer_user_tokens,
                content_buffer,
                last_round_total,
                live_status,
                sync_error,
                tool_calls_buffer,
            ) = yield from self._tool_loop_model_round(
                agent_code=agent_code,
                config=config,
                last_round_total=last_round_total,
                messages=messages,
                model_name=model_name,
                provider=provider,
                round_n=round_n,
                skip_table_footer=skip_table_footer,
                tools=tools,
                turn_usage=turn_usage,
                usage_info=usage_info,
            )

            if not tool_calls_buffer:
                if (yield from self._tool_loop_final_answer(
                    MAX_ROUNDS=MAX_ROUNDS,
                    _defer_user_tokens=_defer_user_tokens,
                    _orig=_orig,
                    _turn_loop_from=_turn_loop_from,
                    config=config,
                    content_buffer=content_buffer,
                    history=history,
                    message=message,
                    messages=messages,
                    model_name=model_name,
                    prior_table_fps=prior_table_fps,
                    remote_llm_format=remote_llm_format,
                    round_n=round_n,
                    session_id=session_id,
                    sync_error=sync_error,
                    tools=tools,
                    turn=turn,
                )):
                    continue
                break
                
            # El modelo pidió herramientas. content → historial LLM (razonamiento).
            # Chat bubble: nunca. Status bar: solo si es progreso corto (forma).
            _progress = _pretool_progress_status(content_buffer)
            if _progress and _progress != live_status:
                yield {"event": "status", "message": _progress}
            messages.append({
                "role": "assistant",
                "content": content_buffer,
                "tool_calls": list(tool_calls_buffer.values())
            })
            
            # Ejecutar herramientas nativamente en Odoo
            turn.direct_formatted = None
            turn.stop_after_direct = False
            # Pie local (servidor) tras HTML de skill: cálido, sin inventar año.
            turn.local_warm_footer = False
            # Texto de pie compuesto por el AUTOR del skill (prioritario sobre
            # el genérico). None = usar el pie cálido por defecto.
            turn.local_footer_text = None
            # Remote formatting: tabular payload to hand to the LLM (no local HTML).
            turn.remote_tabular_handoff = None

            _try_session_export = functools.partial(
                self._tool_loop_session_export, turn, _orig, session_id,
                messages, round_n, MAX_ROUNDS,
            )

            for tc in tool_calls_buffer.values():
                # stop_after_direct corta la SIGUIENTE ronda LLM, no los
                # tool_calls ya emitidos en esta (Relaxaicode hermano sigue).
                tool_name = tc["function"]["name"]
                tool_args_str = tc["function"]["arguments"]
                tool_id = tc["id"]
                
                yield {"event": "status", "message": _('Running %s…') % tool_name}
                _logger.info(f"AgentEngine ejecutando tool: {tool_name}")
                _blocked = None
                result = None

                try:
                    tool_args = json.loads(tool_args_str)
                except Exception as e:
                    tool_args = {}
                    _logger.warning(f"Error decodificando argumentos JSON para {tool_name}: {e}")

                self._tool_loop_inject_previous_result(turn, tool_name, tool_args)

                tool_func = get_tool_function(tool_name)
                
                _blocked, result, result_str = yield from self._tool_loop_run_tool(
                    MAX_ROUNDS=MAX_ROUNDS,
                    _blocked=_blocked,
                    _orig=_orig,
                    _try_session_export=_try_session_export,
                    message=message,
                    remote_llm_format=remote_llm_format,
                    result=result,
                    round_n=round_n,
                    session_id=session_id,
                    skip_table_footer=skip_table_footer,
                    tool_args=tool_args,
                    tool_func=tool_func,
                    tool_name=tool_name,
                    turn=turn,
                )

                self._log_agent_tool_step(tool_name, tool_args, result_str, model_name)

                # Caja B: si se ha propuesto una escritura, emitir un evento para que
                # el frontend de chatboo muestre la confirmación INLINE (no depende del
                # bus/toast). Sigue siendo seguro: el endpoint de confirmación es
                # auth='user' y la IA no tiene la sesión del humano.
                yield from self._tool_loop_after_tool(
                    _blocked=_blocked,
                    _try_session_export=_try_session_export,
                    remote_llm_format=remote_llm_format,
                    result=result,
                    tool_args=tool_args,
                    tool_name=tool_name,
                    turn=turn,
                )

                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_id,
                    "name": tool_name,
                    "content": result_str
                })
                if remote_llm_format and turn.remote_tabular_handoff is not None:
                    self._tool_loop_remote_handoff(turn, messages)

            # ── Direct-formatted result (server-rendered HTML table) ──────────
            # BODY = tabla HTML (replace). FOOTER = 2.ª vuelta LLM solo si el
            # proveedor NO está en modo lacónico (pequeñitos → corte limpio).
            if turn.direct_formatted:
                if (yield from self._tool_loop_direct_close(
                    MAX_ROUNDS=MAX_ROUNDS,
                    _orig=_orig,
                    _try_session_export=_try_session_export,
                    messages=messages,
                    prior_table_fps=prior_table_fps,
                    round_n=round_n,
                    skip_table_footer=skip_table_footer,
                    turn=turn,
                )):
                    break
            
            elif turn.export_attached and turn.stop_after_direct:
                # Named export with hidden table: empty bubble + session chip.
                # Chatboo must treat empty acc + assistant_files/clip_data as
                # success, not "the model returned no content". Partial refuse
                # (PDF + Word) still paints a note in the bubble.
                turn.finished_with_answer = True
                self._stamp_refused_note(turn)
                if turn.direct_formatted:
                    yield {
                        "event": "replace",
                        "content": turn.direct_formatted,
                    }
                break

            # Si el turno finalizó habiendo ejecutado tools, el while continuará
            # para enviar los resultados al LLM y obtener la respuesta final.

        yield from self._tool_loop_close_turn(
            turn, _orig, session_id, config, messages,
        )

        # Fin de Stream: adjuntamos qué modelo/proveedor respondió y los tokens
        # del TURNO (suma de rondas). context_tokens = ocupación de la última
        # ronda (el % del buffer). NUNCA exponemos endpoint ni infra.
        _done = self._tool_loop_done_event(
            _turn_shown_start=_turn_shown_start,
            collected_records=turn.collected_records,
            direct_formatted=turn.direct_formatted,
            export_chips=turn.export_chips,
            export_clip_data=turn.export_clip_data,
            external_sources=turn.external_sources,
            kept_history=kept_history,
            last_round_total=last_round_total,
            last_tabulable_payload=turn.last_tabulable_payload,
            message=message,
            messages=messages,
            model_name=model_name,
            primary_artifact=turn.primary_artifact,
            provider=provider,
            remote_llm_format=remote_llm_format,
            round_n=round_n,
            session_id=session_id,
            side_at_start=side_at_start,
            turn_usage=turn_usage,
        )
        yield _done

        # Empty tabular success must NOT wipe turn_query_data:
        # after api_call→strip recovery, a hollow table would
        # erase the live dataset and force empty re-tries.

    def _tool_loop_model_round(
            self,
            agent_code,
            config,
            last_round_total,
            messages,
            model_name,
            provider,
            round_n,
            skip_table_footer,
            tools,
            turn_usage,
            usage_info,
    ):
        """One model round: send the messages, stream the reply, collect tool calls and usage."""
        round_started = time.monotonic()
            
        tool_calls_buffer = {}
        content_buffer = ""
        unparsed_lines = []
        self._round_had_reasoning = False
        # Con tools activos no soltamos el texto al chat hasta saber si la
        # ronda trae tool_calls. El modelo conserva el content en messages.
        _defer_user_tokens = bool(tools)

        # Historico: peticion al modelo (ORCH a LLM) via gate del motor.
        Engine = self.env['ai.execution.engine']
        Engine.log_provider_llm_request(
            provider,
            agent_code=agent_code,
            round_n=round_n,
            num_messages=len(messages),
            num_tools=len(tools),
            model_label=model_name,
            user_id=self._turn_uid,
            turn=self._turn_corr,
            turn_step=self._next_step(),
            source_channel=self._source_channel,
            client_label=self._client_label,
        )

        content_buffer, usage_info, live_status = yield from self._tool_loop_stream(
            config, provider, model_name, messages, tools, round_n,
            skip_table_footer, round_started, _defer_user_tokens,
            tool_calls_buffer, content_buffer, usage_info,
        )

        # Quitar razonamiento inline (<think>...</think>) si el modelo lo metió
        # dentro de content en vez de en reasoning_content.
        if content_buffer and '<think>' in content_buffer.lower():
            self._round_had_reasoning = True
        content_buffer = _strip_think_blocks(content_buffer)

        # Fallback de tool-calling: algunos modelos no emiten tool_calls
        # estructuradas, sino que escriben el JSON de la
        # llamada dentro del content. Lo recuperamos y ejecutamos igual,
        # reutilizando el parser del orquestador. Solo aceptamos llamadas a
        # tools realmente disponibles, para no confundir prosa con tool-call.
        content_buffer = self._tool_loop_recover_tool_calls(
            tool_calls_buffer, content_buffer, tools,
        )

        # Analizar el resultado del stream
        sync_error = None
        if not tool_calls_buffer and not content_buffer.strip():
            _logger.warning(
                "LLM stream sin texto (%s, model=%s, tools=%s). Muestra: %s",
                config['endpoint'], model_name, len(tools), unparsed_lines,
            )
        _ptok, _ctok = self._tool_loop_log_response(
            provider, agent_code, content_buffer, tool_calls_buffer,
            model_name, usage_info,
        )
        if usage_info:
            add_usage(turn_usage, usage_info)
            last_round_total = int(
                usage_info.get('total_tokens')
                or ((_ptok or 0) + (_ctok or 0))
                or 0
            )
        return (
            _defer_user_tokens,
            content_buffer,
            last_round_total,
            live_status,
            sync_error,
            tool_calls_buffer,
        )

    def _tool_loop_stream(
            self, config, provider, model_name, messages, tools, round_n,
            skip_table_footer, round_started, _defer_user_tokens,
            tool_calls_buffer, content_buffer, usage_info,
    ):
        """Stream the model reply; status while tools may follow."""
        from ..models.ai_execution_engine import ProviderConnectionError

        live_status = None
        try:
            from ..lib.llm.drivers import get_llm_driver
            driver = get_llm_driver(config['protocol'])
            driver.initialize({
                'protocol': config['protocol'],
                'endpoint': config['endpoint'],
                'api_key': config['api_key'],
                'model_name': model_name,
                'temperature': config['temperature'],
                'extra_headers': config.get('extra_headers') or {},
                'send_temperature': (
                    getattr(provider, 'temperature_support', None) != 'no'
                ),
            })
            for piece in driver.iter_chat(
                messages,
                tools=tools or None,
                temperature=config['temperature'],
                timeout=config['idle_timeout'],
                max_tokens=int(getattr(self, '_gen_max_tokens', None) or 4096),
                disable_thinking=bool(skip_table_footer),
            ):
                if time.monotonic() - round_started > config['round_timeout']:
                    raise ProviderConnectionError(
                        _('Round %s exceeded %ss waiting for the model.')
                        % (round_n, config['round_timeout'])
                    )
                if piece.get('reasoning'):
                    self._round_had_reasoning = True
                bit = piece.get('text') or ''
                if bit:
                    content_buffer += bit
                    if not _defer_user_tokens:
                        yield {'event': 'token', 'content': bit}
                    else:
                        status = _pretool_progress_status(content_buffer)
                        if status and status != live_status:
                            live_status = status
                            yield {'event': 'status', 'message': status}
                if piece.get('done'):
                    # Do not assign to ``message``: that name is the user
                    # prompt. Shadowing it stored the model dict as the
                    # next turn's user line.
                    llm_message = piece.get('message') or {}
                    if not content_buffer:
                        content_buffer = llm_message.get('content') or ''
                        if not isinstance(content_buffer, str):
                            content_buffer = ''
                    for idx, tc in enumerate(llm_message.get('tool_calls') or []):
                        tool_calls_buffer[idx] = tc
                    usage_info = piece.get('usage') or {}
        except ProviderConnectionError:
            raise
        except Exception as e:
            _logger.error(
                'Error de conexion LLM (%s): %s',
                config['endpoint'], e, exc_info=True,
            )
            raise ProviderConnectionError(
                _('The AI provider could not be reached.')
            ) from e
        return content_buffer, usage_info, live_status

    def _tool_loop_recover_tool_calls(self, tool_calls_buffer, content_buffer, tools):
        if not tool_calls_buffer and content_buffer.strip() and tools:
            try:
                from ..lib.llm.utils.tool_utils import _extract_from_content
                _recovered = _extract_from_content(content_buffer) or []
            except Exception:
                _recovered = []
            if _recovered:
                _available = set()
                for _t in (tools or []):
                    _fn = (_t.get('function') or {}) if isinstance(_t, dict) else {}
                    _name = _fn.get('name') or (_t.get('name') if isinstance(_t, dict) else None)
                    if _name:
                        _available.add(_name)
                _valid = [
                    c for c in _recovered
                    if (c.get('function') or {}).get('name') in _available
                ]
                if _valid:
                    _logger.info(
                        "AgentEngine: tool-call recuperada del content (modelo sin "
                        "tool_calls nativas): %s",
                        [(c.get('function') or {}).get('name') for c in _valid],
                    )
                    for _i, _tc in enumerate(_valid):
                        tool_calls_buffer[_tc.get('id') or 'call_fallback_%d' % _i] = _tc
                    content_buffer = ""
        return content_buffer

    def _tool_loop_log_response(
            self, provider, agent_code, content_buffer, tool_calls_buffer,
            model_name, usage_info,
    ):
        Engine = self.env['ai.execution.engine']
        # Histórico: respuesta del modelo (LLM → ORCH) vía gate del motor.
        _resp_tools = [
            (tc.get('function') or {}).get('name')
            for tc in tool_calls_buffer.values()
        ]
        _ptok = usage_info.get('prompt_tokens') if usage_info else None
        _ctok = usage_info.get('completion_tokens') if usage_info else None
        _ttok = (usage_info.get('total_tokens') if usage_info else None) or (
            (_ptok or 0) + (_ctok or 0)
        ) or None
        Engine.log_provider_llm_response(
            provider,
            agent_code=agent_code,
            content_preview=(content_buffer or '').strip(),
            tool_names=_resp_tools,
            tool_calls=list(tool_calls_buffer.values()),
            model_label=model_name,
            prompt_tokens=_ptok,
            completion_tokens=_ctok,
            total_tokens=_ttok,
            usage=usage_info if usage_info else None,
            user_id=self._turn_uid,
            turn=self._turn_corr,
            turn_step=self._next_step(),
            source_channel=self._source_channel,
            client_label=self._client_label,
        )
        return _ptok, _ctok

