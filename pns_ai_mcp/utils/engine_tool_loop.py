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
        # Safety net for self-correction: if the model uses up the rounds
        # retrying broken code without a final answer, we show the last
        # technical error instead of leaving the chat blank.
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
        # External sources consulted: fetch_url domains and API servers.
        # Used both for PROPOSED steps (tool_args of safe_plan_request,
        # auto-confirmed) and for ALREADY EXECUTED steps recovered later with
        # safe_plan_status (manual confirmation). Both share the same
        # shape: dicts with 'op' + 'url' (fetch_url) or 'server'/'tool' (api_call).
        self.external_sources = set()
        # Odoo records referenced in the turn (to paint them as clickable
        # links in the host). DETERMINISTIC: they come from REAL tool
        # results —relaxaicode rows with id+__model and confirmed safe plan
        # CRUD operations—, NOT from the model citing them correctly.
        self.collected_records = []
        self._records_seen = set()
        # The model of each id already identified in THIS turn. A
        # presentation step often rebuilds the rows from a literal: same ids,
        # no live recordset saying where they came from.
        self.turn_record_models = {}
        # Record delivery lock (no lexicon): tabulable payload of the
        # turn and whether a replace with a table already happened.
        # ``delivered_html`` is what the client already has in the bubble: a
        # replace pins it whole, so the close cannot send bare prose
        # without wiping the table this turn painted.
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
        """Cap in serialized BYTES of the dataset cache (Level 2), configurable
        through a system parameter. 0 or negative = no limit. On any failure it
        falls back to the module default."""
        from .agent_engine import AGENT_DATASET_CACHE_MAX_BYTES
        try:
            return int(self.env['ir.config_parameter'].sudo().get_param(
                'pns_ai_mcp.dataset_cache_max_bytes', AGENT_DATASET_CACHE_MAX_BYTES))
        except (TypeError, ValueError):
            return AGENT_DATASET_CACHE_MAX_BYTES

    def _skill_result_events(self, code_body, payload):
        """What a skill resolved outside the loop leaves the session (see
        ``record_delivery_gate.skill_result_events``)."""
        from .record_delivery_gate import skill_result_events
        yield from skill_result_events(
            code_body, payload, self._dataset_cache_max_bytes(),
        )

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
        # Turn dataset: starts with the session cache and is updated after
        # each successful RelaxAICode, so the 2nd call (pyjama/style) can
        # ask for raw_data/previous_result when the code references it (AST).
        turn.turn_query_data = list(prior_query_data) if prior_query_data else None
        try:
            from .session_download import file_labels_from_mapping
            _labels = (self.env.context or {}).get('file_label_by_id')
            if isinstance(_labels, dict) and turn.turn_query_data:
                file_labels_from_mapping(turn.turn_query_data, _labels)
        except Exception:
            pass
        turn.turn_safe_plan_steps = None
        # Anti-echo: fingerprints of tables already shown in the assistant history.
        # Those regenerated this turn (tools) are allowed even if they match.
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
        
        # Architecture (docs/dos_credenciales_api.md): the internal host infers here
        # in-process; it does NOT re-enter /mcp nor use ai.mcp.user.mcp_api_key_hash.
        # Tools go through tool_func(DummyController(self.env), ...).
        # ai.provider.api_key IS used (HTTP to the LLM), read in _api_key_for_inference().
        # The user's X-Mcp-Token is not passed to the LLM: an unused secret on this path.

        # 2. Prepare Messages (System Prompt injection)
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

        # 3. Load Tools
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
                "AgentEngine: history trimmed to fit the context "
                "(%s old message(s) dropped; window=%s)",
                dropped, provider.context_window or 0,
            )
            yield {"event": "status", "message": _('Fitting the history to the context (older turns are dropped)…')}

        yield {"event": "status", "message": _('Connecting to %s (active tools: %s)…') % (model_name, len(tools))}

        # --- NATIVE REACT LOOP ---
        # ReAct loop policy: lives in the agent (resolved above). If there is
        # no agent or the value is <= 0, use the default (10).
        MAX_ROUNDS = (agent.max_agent_rounds if (agent and (agent.max_agent_rounds or 0) > 0) else 10)
        round_n = 0
        agent_started = time.monotonic()
        # Tokens of the current LLM round (reset on every loop).
        usage_info = {}
        # Sum of all rounds of the turn (footer + daily history).
        turn_usage = {}
        side_at_start = dict(self._side_usage())
        add_usage(turn_usage, side_at_start)
        last_round_total = 0
        # The rows the client re-injects already went through a screen and
        # say which model they belong to: a turn that rebuilds them without the ORM
        # still knows which record each id points to.
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
                
            # The model asked for tools. content → LLM history (reasoning).
            # Chat bubble: never. Status bar: only if it is short progress (shape).
            _progress = _pretool_progress_status(content_buffer)
            if _progress and _progress != live_status:
                yield {"event": "status", "message": _progress}
            messages.append({
                "role": "assistant",
                "content": content_buffer,
                "tool_calls": list(tool_calls_buffer.values())
            })
            
            # Run tools natively in Odoo
            turn.direct_formatted = None
            turn.stop_after_direct = False
            # Local (server) footer after skill HTML: warm, no invented year.
            turn.local_warm_footer = False
            # Footer text written by the skill AUTHOR (takes priority over
            # the generic one). None = use the default warm footer.
            turn.local_footer_text = None
            # Remote formatting: tabular payload to hand to the LLM (no local HTML).
            turn.remote_tabular_handoff = None

            _try_session_export = functools.partial(
                self._tool_loop_session_export, turn, _orig, session_id,
                messages, round_n, MAX_ROUNDS,
            )

            for tc in tool_calls_buffer.values():
                # stop_after_direct cuts the NEXT LLM round, not the
                # tool_calls already emitted in this one (a sibling Relaxaicode goes on).
                tool_name = tc["function"]["name"]
                tool_args_str = tc["function"]["arguments"]
                tool_id = tc["id"]
                
                yield {"event": "status", "message": _('Running %s…') % tool_name}
                _logger.info(f"AgentEngine running tool: {tool_name}")
                _blocked = None
                result = None

                try:
                    tool_args = json.loads(tool_args_str)
                except Exception as e:
                    tool_args = {}
                    _logger.warning(f"Error decoding JSON arguments for {tool_name}: {e}")

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

                # Box B: if a write was proposed, emit an event so that
                # the host frontend shows the confirmation INLINE (does not depend on
                # bus/toast). Still safe: the confirmation endpoint is
                # auth='user' and the AI does not have the human's session.
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
            # BODY = HTML table (replace). FOOTER = 2nd LLM round only if the
            # provider is NOT in laconic mode (small ones → clean cut).
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
                # The host must treat empty acc + assistant_files/clip_data as
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

            # If the turn ended having run tools, the while goes on
            # to send the results to the LLM and get the final answer.

        yield from self._tool_loop_close_turn(
            turn, _orig, session_id, config, messages,
        )

        # End of Stream: we attach which model/provider answered and the tokens
        # of the TURN (sum of rounds). context_tokens = usage of the last
        # round (the buffer %). We NEVER expose endpoint or infra.
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
        # With tools active we do not release the text to the chat until we know if
        # the round brings tool_calls. The model keeps the content in messages.
        _defer_user_tokens = bool(tools)

        # History: request to the model (ORCH to LLM) via the engine gate.
        Engine = self.env['ai.execution.engine']
        Engine._log_provider_llm_request(
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

        # Strip inline reasoning (<think>...</think>) if the model put it
        # inside content instead of reasoning_content.
        if content_buffer and '<think>' in content_buffer.lower():
            self._round_had_reasoning = True
        content_buffer = _strip_think_blocks(content_buffer)

        # Tool-calling fallback: some models do not emit structured
        # tool_calls, but write the JSON of the
        # call inside the content. We recover it and run it anyway,
        # reusing the orchestrator parser. We only accept calls to
        # tools that really exist, so prose is not mistaken for a tool-call.
        content_buffer = self._tool_loop_recover_tool_calls(
            tool_calls_buffer, content_buffer, tools,
        )

        # Analyze the stream result
        sync_error = None
        if not tool_calls_buffer and not content_buffer.strip():
            _logger.warning(
                "LLM stream without text (%s, model=%s, tools=%s). Sample: %s",
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
                        "AgentEngine: tool-call recovered from content (model without "
                        "native tool_calls): %s",
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
        # History: model reply (LLM → ORCH) via the engine gate.
        _resp_tools = [
            (tc.get('function') or {}).get('name')
            for tc in tool_calls_buffer.values()
        ]
        _ptok = usage_info.get('prompt_tokens') if usage_info else None
        _ctok = usage_info.get('completion_tokens') if usage_info else None
        _ttok = (usage_info.get('total_tokens') if usage_info else None) or (
            (_ptok or 0) + (_ctok or 0)
        ) or None
        Engine._log_provider_llm_response(
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

