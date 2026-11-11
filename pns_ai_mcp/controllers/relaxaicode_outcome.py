# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""What relaxaicode does with the result: caps, row links and pictures, phases, reply."""

import json
import logging

from .relaxaicode_rows import (
    _iter_all_tabular_row_lists,
    _postprocess_images,
    _row_record_id,
    _sanitize_binary_for_llm,
)
from .relaxaicode_models import (
    _backfill_missing_record_ids,
    _build_label_to_record_index,
    _collect_record_refs,
    _count_tabular_id_coverage,
    _infer_id_model_map,
    _models_from_code,
    _norm_label,
    _related_models_from_code,
    _row_string_values,
    _stamp_models,
    _turn_memory_models,
)
from .relaxaicode_replies import (
    _TRUSTED_FMT_TYPES,
    _enforce_result_size_cap,
    _format_error_response,
    _log_relaxaicode_execution,
    _log_where,
    _reject_untrusted_formatted_text,
    _relaxaicode_log_prompt,
)

_logger = logging.getLogger(__name__)


def _result_of(safe_context):
    """The ``result`` the code assigned: a list becomes ``data``, a bare string a hint."""
    # Get the result AFTER a successful exec()
    # exec() changes safe_context directly
    # Check explicitly whether 'result' is in the context
    # CRITICAL: check right after exec() for diagnosis
    result = None
    if 'result' in safe_context:
        result = safe_context['result']
    elif 'output' in safe_context:
        result = safe_context['output']

    # Normalize a top-level list (e.g. the LLM does result = [{...}, ...])
    # into a dict BEFORE phase processing. This normalization used to live
    # INSIDE the `if isinstance(result, dict)` block, so it NEVER ran for
    # lists: the listing came back as raw JSON, the LLM re-formatted it as
    # markdown and pictures (<img>), currency/date format and quartile
    # coloring were lost. Once wrapped, the list goes to the server-side
    # (Python) render.
    if isinstance(result, list):
        result = {"data": result}
    elif isinstance(result, str):
        # Bare strings are never a user-facing answer (tables need rows;
        # writes need safe_plan_request). Keep a preview for the LLM.
        result = {
            '__raw_text__': result[:8000],
            '__force_continue__': True,
            '__hint__': (
                'String results are not shown to the user. Return '
                '{\'data\': [row dicts…]} for tables, or use '
                'safe_plan_request for creates/writes. Answer in prose.'
            ),
        }
    return result


def _too_large_response(controller, result, code, agent_llm, context_data,
                        phase, return_mode):
    """The reply when the output is over the caps, else None."""
    # Anti-DoS cap on the OUTPUT (H4): cuts pathological outputs before
    # post-processing/rendering/logging them. CPU/memory spent DURING the
    # exec is bounded by the Odoo worker (limit_time_*/limit_memory_*).
    _size_err = _enforce_result_size_cap(result)
    if _size_err:
        error_response = _format_error_response(
            -32603,
            'Error executing code: %s' % _size_err,
            {'error_type': 'ResultTooLarge'},
            retryable=True,
        )
        _log_relaxaicode_execution(
            controller, code, error_response, _size_err,
            operation_type='read', agent_llm=agent_llm,
            context_data=context_data,
            phase=phase, return_mode=return_mode,
        )
        return error_response
    return None


def _link_and_picture_rows(controller, result, safe_context, code, agent_llm,
                           context_data, phase, return_mode, env):
    """Stamp each row with its model, fill ids, collect record refs, turn base64 into URLs.

    *env* is the run's real Environment, not ``safe_context['env']`` (the
    sandbox wrapper, which the code may have rebound).

    Returns the reply when tabular rows lost their ids, else None.
    """
    # ============================================================
    # POST-PROCESS PICTURES: base64 → URL /web/image/
    # ============================================================
    if isinstance(result, dict):
        # Infer each row's model WITHOUT relying on the LLM setting
        # __model (fragile): (1) from the live recordsets in the sandbox
        # namespace (id→real model) and (2) as a hint, from the only model
        # referenced as env['x'] in the code. This way pictures (URL
        # /web/image) and clickable links come out deterministically.
        _single_model = None
        _env = None
        # User opt-out ("clean table / no links"): the LLM sets
        # __row_links__=False (or links=False). It turns off ONLY the links
        # (widget column in the table + footer chips); picture thumbnails
        # stay because _stamp_models and _postprocess_images still run
        # (they need __model).
        _links_off = (result.get('__row_links__') is False
                      or result.get('links') is False)
        try:
            _id_model_map = _infer_id_model_map(safe_context)
            _code_models = _models_from_code(code)
            _single_model = (
                next(iter(_code_models)) if len(_code_models) == 1 else None
            )
            _env = env
            _candidates = set(_code_models)
            _candidates |= _related_models_from_code(code, _env, _code_models)
            # Before the stamp: fill the id the LLM left out (links).
            try:
                _backfill_missing_record_ids(
                    result,
                    safe_context,
                    env=_env,
                    candidate_models=_candidates,
                    single_model=_single_model,
                )
            except Exception as bf_err:
                _logger.debug('backfill record ids: %s (no-op)', bf_err)
            _stamp_models(
                result,
                _id_model_map,
                single_model=_single_model,
                env=_env,
                candidate_models=_candidates,
                turn_models=_turn_memory_models(controller),
            )
            # Only if there are rows whose label matches a sandbox recordset
            # (a clear missing id). A non-empty index alone is NOT enough:
            # any leftover browse + a list of meta dicts (diagnosis, logs)
            # would trigger false positives.
            if not _links_off:
                try:
                    _idx = _build_label_to_record_index(safe_context)
                    _total, _missing = _count_tabular_id_coverage(result)
                    _looks_omitted = False
                    if _idx and _total >= 1 and _missing == _total:
                        for _rows in _iter_all_tabular_row_lists(result):
                            for _item in _rows:
                                if not isinstance(_item, dict):
                                    continue
                                if _row_record_id(_item):
                                    continue
                                for _raw in _row_string_values(_item):
                                    if _norm_label(_raw) in _idx:
                                        _looks_omitted = True
                                        break
                                if _looks_omitted:
                                    break
                            if _looks_omitted:
                                break
                    if _looks_omitted:
                        error_response = _format_error_response(
                            -32603,
                            (
                                'Tabular rows are missing record id. When listing '
                                'Odoo records, EVERY row dict MUST include '
                                "'id': record.id (and typically name/display_name). "
                                'Without id the server cannot create form links. '
                                'Fix the code: build rows from the recordset with id.'
                            ),
                            {
                                'error_type': 'MissingRecordId',
                                'rows': _total,
                                'hint': (
                                    "rows.append({'id': r.id, 'name': r.display_name, ...})"
                                ),
                            },
                            retryable=True,
                        )
                        _log_relaxaicode_execution(
                            controller, code, error_response,
                            'Missing record id on tabular rows',
                            operation_type='read', agent_llm=agent_llm,
                            context_data=context_data,
                            phase=phase, return_mode=return_mode,
                        )
                        return error_response
                except Exception as mid_err:
                    _logger.debug('missing-id gate: %s (no-op)', mid_err)
        except Exception as im_err:
            _logger.debug('model inference: %s (no-op)', im_err)
        # Record refs for clickable links in the host: BEFORE
        # _postprocess_images (which consumes the rows' __model). Skipped on
        # opt-out so no footer chips are drawn when the user does not want them.
        if not _links_off:
            try:
                _collect_record_refs(
                    result, model_hint=_single_model, env=_env,
                )
            except Exception as rr_err:
                _logger.debug('_collect_record_refs: %s (no-op)', rr_err)
        try:
            _postprocess_images(result, model_hint=_single_model, env=_env)
        except Exception as pp_err:
            _logger.debug('_postprocess_images: %s (no-op)', pp_err)
    return None


def _present_result(result, safe_context, phase, return_mode, summary, env):
    """Phase flags, the server-side table, and where the result goes (user or model).

    *env* is the run's real Environment, not ``safe_context['env']``.

    Returns the reply for formatted text in Phase 1 without a flag, else None.
    """
    # ============================================================
    # PROCESS TWO-PHASE FLAGS AND RUN PHASE 2 AUTOMATICALLY
    # ============================================================
    # If the result is a dict, process the two-phase flags
    if isinstance(result, dict):
        # Detect whether there is data that needs presentation (automatic Phase 2)
        needs_presentation = False
        raw_data = None

        # Detect whether this is extraction or has data that needs formatting
        # CHANGED: also turn on when return_mode is 'direct_to_user'
        if phase == 'extraction' or result.get('__ready_for_presentation__') or result.get('__extraction_complete__') or return_mode == 'direct_to_user':
            needs_presentation = True
            raw_data = result.get('data', result)
        elif phase == 'auto':
            # Detect automatically whether there is structured data that needs presentation
            # Look for big lists or data structures that should be formatted
            # Look in 'data' first, then in any field of the result
            if 'data' in result and isinstance(result.get('data'), (list, dict)):
                data_content = result.get('data')
                if isinstance(data_content, list) and len(data_content) > 10:
                    needs_presentation = True
                    raw_data = {'data': data_content}
                elif isinstance(data_content, dict):
                    # Look for lists inside the dict
                    for key, value in data_content.items():
                        if isinstance(value, list) and len(value) > 10:
                            needs_presentation = True
                            raw_data = result.get('data', result)
                            break
            else:
                # Look for big lists directly in the result (e.g. 'customers', 'employees', etc.)
                for key, value in result.items():
                    if isinstance(value, list) and len(value) > 10 and not key.startswith('__'):
                        needs_presentation = True
                        raw_data = result
                        break

        # PHASE 1 (EXTRACTION): must NOT have formatted_text - RAW data only
        # EXCEPTION: if there is formatted_text, we assume Fast Path (One-Shot) automatically.
        # No explicit flags required; formatted text is intent enough.
        has_formatted_text_in_extraction = result.get('formatted_text') is not None
        is_one_shot_allowed = (
            has_formatted_text_in_extraction or # IMPLICIT: if there is text, it is valid
            result.get('__ready_for_presentation__') or 
            result.get('ready_for_presentation') or
            result.get('__return_direct__') or 
            result.get('return_direct') or
            return_mode == 'direct_to_user'
        )

        if has_formatted_text_in_extraction and (phase == 'extraction' or phase == 'auto') and not is_one_shot_allowed:
            _logger.error(f"[{_log_where()}] PHASE 1: formatted_text without a completion flag")
            return _format_error_response(
                -32602,
                'PROTOCOL ERROR: formatted_text found in Phase 1. If you want to return the final answer immediately, you MUST also set "ready_for_presentation": True (or "extraction_complete": True) in your result dictionary. usage: result = {"formatted_text": "...", "ready_for_presentation": True}.',
                {'error_type': 'PhaseError', 'phase': 'extraction', 'invalid_field': 'formatted_text'},
                retryable=True,
            )

        # Server-side (Python) render when there is tabular data.
        # (the list→dict normalization was already done above, before this block)
        from odoo.addons.pns_ai_mcp.utils.relaxaicode_render import (
            maybe_attach_formatted_text,
            render_context_from_env,
        )

        # Session locale (res.lang), not fixed US/ES defaults.
        render_env = env
        try:
            render_ctx = (
                render_context_from_env(render_env, result=result)
                if render_env is not None
                else {
                    'pk_decimal_sep': safe_context.get('pk_decimal_sep', ','),
                    'pk_thousands_sep': safe_context.get('pk_thousands_sep', '.'),
                    'pk_date_format': safe_context.get('pk_date_format', '%d/%m/%Y'),
                    'show_mode': 'show-table',
                }
            )
        except Exception:
            render_ctx = {
                'pk_decimal_sep': safe_context.get('pk_decimal_sep', ','),
                'pk_thousands_sep': safe_context.get('pk_thousands_sep', '.'),
                'pk_date_format': safe_context.get('pk_date_format', '%d/%m/%Y'),
                'show_mode': 'show-table',
            }
        maybe_attach_formatted_text(
            result,
            summary=summary,
            render_context=render_ctx,
            force=(
                return_mode == 'direct_to_user'
                or bool(result.get('__return_direct__'))
                or bool(result.get('__ready_for_presentation__'))
                or bool(result.get('__presentation_complete__'))
                or bool(result.get('__satisfied__'))
                or phase == 'presentation'
            ),
        )

        # If it needs presentation and it is not done yet, ASK the LLM for formatting code
        # Like the write confirmation mechanism: ask for code WITHOUT sending data
        if needs_presentation and not result.get('__presentation_complete__') and not result.get('error'):
            if raw_data is None:
                raw_data = result.get('data', result)

            # Mark extraction as done
            result['__phase__'] = 'extraction'
            result['__ready_for_presentation__'] = True
            result['__extraction_complete__'] = True
            # Table already rendered (maybe_attach) with summary → final answer.
            # Without this the orchestrator hid the HTML mid-turn and the LLM
            # described the table in prose without showing it.
            if (
                result.get('formatted_text')
                and result.get('summary')
                and result.get('__fmt_type__') in _TRUSTED_FMT_TYPES
            ):
                result['__phase__'] = 'presentation'
                result['__presentation_complete__'] = True
                result['__satisfied__'] = True
                result['__return_direct__'] = True

            # Visible log of the finished extraction
            data_size = len(str(raw_data))
            if isinstance(raw_data, dict):
                data_keys = list(raw_data.keys())
                # Detect the structure to ask for the right formatting
                data_structure = {}
                for key, value in raw_data.items():
                    if isinstance(value, list) and len(value) > 0:
                        if isinstance(value[0], dict):
                            data_structure[key] = {
                                'type': 'list_of_dicts',
                                'count': len(value),
                                'sample_keys': list(value[0].keys())[:5] if value[0] else []
                            }
                        else:
                            data_structure[key] = {
                                'type': 'list_of_values',
                                'count': len(value)
                            }
            elif isinstance(raw_data, list):
                data_keys = [f"list with {len(raw_data)} items"]
                if len(raw_data) > 0 and isinstance(raw_data[0], dict):
                    data_structure = {
                        'type': 'list_of_dicts',
                        'count': len(raw_data),
                        'sample_keys': list(raw_data[0].keys())[:5] if raw_data[0] else []
                    }
                else:
                    data_structure = {'type': 'list_of_values', 'count': len(raw_data)}
            else:
                data_keys = ["data"]
                data_structure = {'type': 'unknown'}

            _logger.info(f"📊 [PHASE 1: EXTRACTION] Done - Data extracted: {len(data_keys)} fields, size: {data_size} chars. Running Phase 2 (presentation) automatically...")

        if phase == 'presentation':
            # Mark presentation as done
            result['__phase__'] = 'presentation'
            result['__presentation_complete__'] = True
            result['__satisfied__'] = True  # AI satisfied, needs no more processing
            # RAW MODE: mark explicitly for direct return if it has formatted_text
            if result.get('formatted_text'):
                result['__return_direct__'] = True
                result['__raw_mode__'] = True
            # Visible log of the finished presentation, with result info
            result_size = len(str(result))
            result_keys = list(result.keys())
            # Count items if it is a list or a dict with lists
            item_count = 0
            if 'data' in result and isinstance(result['data'], (list, dict)):
                if isinstance(result['data'], list):
                    item_count = len(result['data'])
                elif isinstance(result['data'], dict):
                    # Count items in the first field that is a list
                    for key, value in result['data'].items():
                        if isinstance(value, list):
                            item_count = len(value)
                            break
            _logger.info(f"✅ [PHASE 2: PRESENTATION] Done - Result processed: {len(result_keys)} fields, {item_count} items, size: {result_size} chars. AI satisfied, direct return on.")
            result['__phase__'] = result.get('__phase__', 'extraction')
            _logger.info(f"📋 [AUTO-DETECTED PHASE] Result marked ready for presentation (phase: {result.get('__phase__')})")

        # ============================================================
        # APPLY FINAL ALERT MODE LOGIC
        # ============================================================
        if return_mode == 'direct_to_user':
            result['__return_direct__'] = True
            _logger.info("🚀 [RETURN_MODE] Forcing direct_return on explicit request (direct_to_user)")
        elif return_mode == 'inspect_result':
            # Model chose LLM-only delivery: strip every chat-dump flag the
            # auto-presentation path may have set. Keep formatted_text/data
            # in the tool JSON for the model (skills hybrid / param gaps).
            for _k in (
                '__return_direct__',
                '__direct_return__',
                '__return_direct_to_user__',
                '__presentation_complete__',
                '__satisfied__',
                '__stop_after_direct__',
                '__ready_for_presentation__',
            ):
                result.pop(_k, None)
            if result.get('__phase__') == 'presentation':
                result['__phase__'] = 'extraction'
            _logger.info(
                "↩️ [RETURN_MODE] inspect_result — dataset for LLM only"
            )

        # Contract: direct-to-user only with trusted HTML or tabulable rows.
        if isinstance(result, dict) and (
            result.get('__return_direct__')
            or result.get('__direct_return__')
            or return_mode == 'direct_to_user'
        ):
            _reject_untrusted_formatted_text(
                result,
                after_server_render=True,
            )
            try:
                from odoo.addons.pns_ai_mcp.utils.relaxaicode_render import (
                    is_tabulable,
                )
                _trusted_ft = (
                    bool(result.get('formatted_text'))
                    and result.get('__fmt_type__') in _TRUSTED_FMT_TYPES
                )
                _tabulable = is_tabulable(result, force=True)
            except Exception:
                _trusted_ft = (
                    bool(result.get('formatted_text'))
                    and result.get('__fmt_type__') in _TRUSTED_FMT_TYPES
                )
                _tabulable = False
            if not _trusted_ft and not _tabulable:
                result.pop('__return_direct__', None)
                result.pop('__direct_return__', None)
                result.pop('__return_direct_to_user__', None)
                result['__force_continue__'] = True
                result['__hint__'] = (
                    'This result is not user-facing (no tabulable rows / no '
                    'trusted server HTML). Do NOT paste it into chat. Return '
                    '{\'data\': [row dicts…]} for a server table, or use '
                    'safe_plan_request for writes. Use '
                    'return_mode=inspect_result for probes.'
                )
                _logger.info(
                    "🛡️ [CONTRACT] Blocked direct_return without trusted "
                    "HTML or tabulable rows."
                )
    return None


def _success_response(controller, result, code, context_data, operation_type):
    """The result as MCP content, logged as a successful run."""
    # Serialize the result only once
    # The MCP format needs 'text' to be a JSON string

    try:
        result_json = json.dumps(_sanitize_binary_for_llm(result), default=str, ensure_ascii=False, separators=(',', ':'))
    except (TypeError, ValueError) as json_error:
        _logger.error(f"[{_log_where()}] Error serializing result to JSON: {json_error}")
        result_json = json.dumps({"error": "Result could not be serialized", "original_error": str(json_error), "result_type": str(type(result))}, ensure_ascii=False)


    # Log result size for debugging
    result_json_bytes = len(result_json.encode('utf-8'))
    if result_json_bytes > 1000:
        _logger.warning(f"[{_log_where()}] Large result JSON: {result_json_bytes} bytes")
    else:
        _logger.debug(f"✅ Result JSON: {result_json_bytes} bytes - {result_json[:200] if len(result_json) > 200 else result_json}")

    # Build the reply with the serialized JSON in 'text'
    response = {
        'content': [
            {
                'type': 'text',
                'text': result_json
            }
        ]
    }

    # Log the successful operation
    result_summary = f"Execution successful. Result: {str(result)[:200]}" if result else "Execution successful without result"
    controller._log_mcp_operation(
        operation_type=operation_type,
        tool_name='relaxaicode',
        prompt_data=_relaxaicode_log_prompt(
            code, context_data,
        ),
        result_data=response,
        result_summary=result_summary,
        code_to_execute=code
    )

    return response
