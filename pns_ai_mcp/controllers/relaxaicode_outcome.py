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
    # Obtener resultado DESPUÉS de exec() exitoso
    # exec() modifica safe_context directamente
    # Verificar explícitamente si 'result' está en el contexto
    # CRÍTICO: Verificar inmediatamente después de exec() para diagnóstico
    result = None
    if 'result' in safe_context:
        result = safe_context['result']
    elif 'output' in safe_context:
        result = safe_context['output']

    # Normalizar lista de nivel superior (p. ej. el LLM hace result = [{...}, ...])
    # a dict ANTES del procesado de fases. Hasta ahora esta normalización vivía
    # DENTRO del bloque `if isinstance(result, dict)` y por eso NUNCA corría para
    # listas: el listado se devolvía como JSON crudo, el LLM lo re-formateaba en
    # markdown y se perdían imágenes (<img>), formato de moneda/fecha y coloreado
    # por cuartiles. Con la lista envuelta entra al render server-side (Python).
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
    # Tope anti-DoS de la SALIDA (H4): corta salidas patológicas antes de
    # post-procesarlas/renderizarlas/loguearlas. El gasto de CPU/memoria
    # DURANTE el exec lo acota el worker de Odoo (limit_time_*/limit_memory_*).
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
                           context_data, phase, return_mode):
    """Stamp each row with its model, fill ids, collect record refs, turn base64 into URLs.

    Returns the reply when tabular rows lost their ids, else None.
    """
    # ============================================================
    # POST-PROCESAR IMÁGENES: base64 → URL /web/image/
    # ============================================================
    if isinstance(result, dict):
        # Inferir el modelo de cada fila SIN depender de que el LLM ponga
        # __model (frágil): (1) de los recordsets vivos en el namespace del
        # sandbox (id→model real) y (2) como pista, del único modelo
        # referenciado como env['x'] en el código. Así las fotos (URL
        # /web/image) y los enlaces clicables salen de forma determinista.
        _single_model = None
        _env = None
        # Opt-out del usuario ("tabla limpia / sin enlaces"): el LLM pone
        # __row_links__=False (o links=False). Desactiva SOLO los enlaces
        # (columna-widget en la tabla + chips del pie); las miniaturas de
        # imagen siguen porque _stamp_models y _postprocess_images se ejecutan
        # igual (necesitan __model).
        _links_off = (result.get('__row_links__') is False
                      or result.get('links') is False)
        try:
            _id_model_map = _infer_id_model_map(safe_context)
            _code_models = _models_from_code(code)
            _single_model = (
                next(iter(_code_models)) if len(_code_models) == 1 else None
            )
            _env = safe_context.get('env')
            _candidates = set(_code_models)
            _candidates |= _related_models_from_code(code, _env, _code_models)
            # Antes del stamp: rellenar id omitido por el LLM (enlaces).
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
            # Solo si hay filas cuya etiqueta encaja con un recordset del
            # sandbox (omisión clara de id). Un índice no vacío por sí solo
            # NO basta: cualquier browse residual + lista de dicts meta
            # (diagnóstico, logs) dispararía falsos positivos.
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
            _logger.debug('inferencia de modelo: %s (no-op)', im_err)
        # Refs de registros para enlaces clicables en Chatboo: ANTES de
        # _postprocess_images (que consume __model de las filas). Se omiten en
        # opt-out para no pintar chips del pie cuando el usuario no los quiere.
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


def _present_result(result, safe_context, phase, return_mode, summary):
    """Phase flags, the server-side table, and where the result goes (user or model).

    Returns the reply for formatted text in Phase 1 without a flag, else None.
    """
    # ============================================================
    # PROCESAR FLAGS DE DOS FASES Y EJECUTAR FASE 2 AUTOMÁTICAMENTE
    # ============================================================
    # Si el resultado es un dict, procesar flags de dos fases
    if isinstance(result, dict):
        # Detectar si hay datos que necesitan presentación (Fase 2 automática)
        needs_presentation = False
        raw_data = None

        # Detectar si es extracción o tiene datos que necesitan formateo
        # MODIFICADO: También activar si return_mode es 'direct_to_user'
        if phase == 'extraction' or result.get('__ready_for_presentation__') or result.get('__extraction_complete__') or return_mode == 'direct_to_user':
            needs_presentation = True
            raw_data = result.get('data', result)
        elif phase == 'auto':
            # Detectar automáticamente si hay datos estructurados que necesitan presentación
            # Buscar listas grandes o estructuras de datos que deberían formatearse
            # Primero buscar en 'data', luego en cualquier campo del resultado
            if 'data' in result and isinstance(result.get('data'), (list, dict)):
                data_content = result.get('data')
                if isinstance(data_content, list) and len(data_content) > 10:
                    needs_presentation = True
                    raw_data = {'data': data_content}
                elif isinstance(data_content, dict):
                    # Buscar listas dentro del dict
                    for key, value in data_content.items():
                        if isinstance(value, list) and len(value) > 10:
                            needs_presentation = True
                            raw_data = result.get('data', result)
                            break
            else:
                # Buscar listas grandes directamente en el resultado (ej: 'customers', 'employees', etc.)
                for key, value in result.items():
                    if isinstance(value, list) and len(value) > 10 and not key.startswith('__'):
                        needs_presentation = True
                        raw_data = result
                        break

        # FASE 1 (EXTRACCIÓN): NO debe tener formatted_text - solo datos RAW
        # EXCEPCIÓN: Si hay formatted_text, asumimos Fast Path (One-Shot) automáticamente.
        # No exigimos flags explícitos, la presencia de texto formateado es suficiente intención.
        has_formatted_text_in_extraction = result.get('formatted_text') is not None
        is_one_shot_allowed = (
            has_formatted_text_in_extraction or # IMPLÍCITO: Si hay texto, es válido
            result.get('__ready_for_presentation__') or 
            result.get('ready_for_presentation') or
            result.get('__return_direct__') or 
            result.get('return_direct') or
            return_mode == 'direct_to_user'
        )

        if has_formatted_text_in_extraction and (phase == 'extraction' or phase == 'auto') and not is_one_shot_allowed:
            _logger.error(f"[{_log_where()}] FASE 1: formatted_text sin flag de finalización")
            return _format_error_response(
                -32602,
                'PROTOCOL ERROR: formatted_text found in Phase 1. If you want to return the final answer immediately, you MUST also set "ready_for_presentation": True (or "extraction_complete": True) in your result dictionary. usage: result = {"formatted_text": "...", "ready_for_presentation": True}.',
                {'error_type': 'PhaseError', 'phase': 'extraction', 'invalid_field': 'formatted_text'},
                retryable=True,
            )

        # Render server-side (Python) cuando hay datos tabulares.
        # (la normalización lista→dict ya se hizo arriba, antes de este bloque)
        from odoo.addons.pns_ai_mcp.utils.relaxaicode_render import (
            maybe_attach_formatted_text,
            render_context_from_env,
        )

        # Locale de la sesión (res.lang), no defaults fijos US/ES.
        render_env = safe_context.get('env')
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

        # Si necesita presentación y no está ya completada, SOLICITAR código de formateo al LLM
        # Similar al mecanismo de confirmación de escrituras: solicitar código SIN enviar datos
        if needs_presentation and not result.get('__presentation_complete__') and not result.get('error'):
            if raw_data is None:
                raw_data = result.get('data', result)

            # Marcar como extracción completada
            result['__phase__'] = 'extraction'
            result['__ready_for_presentation__'] = True
            result['__extraction_complete__'] = True
            # Tabla ya renderizada (maybe_attach) con summary → respuesta final.
            # Sin esto el orquestador ocultaba el HTML mid-turn y el LLM
            # describía la tabla en prosa sin mostrarla.
            if (
                result.get('formatted_text')
                and result.get('summary')
                and result.get('__fmt_type__') in _TRUSTED_FMT_TYPES
            ):
                result['__phase__'] = 'presentation'
                result['__presentation_complete__'] = True
                result['__satisfied__'] = True
                result['__return_direct__'] = True

            # Log visible de extracción completada
            data_size = len(str(raw_data))
            if isinstance(raw_data, dict):
                data_keys = list(raw_data.keys())
                # Detectar estructura para solicitar formateo apropiado
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
                data_keys = [f"lista con {len(raw_data)} elementos"]
                if len(raw_data) > 0 and isinstance(raw_data[0], dict):
                    data_structure = {
                        'type': 'list_of_dicts',
                        'count': len(raw_data),
                        'sample_keys': list(raw_data[0].keys())[:5] if raw_data[0] else []
                    }
                else:
                    data_structure = {'type': 'list_of_values', 'count': len(raw_data)}
            else:
                data_keys = ["datos"]
                data_structure = {'type': 'unknown'}

            _logger.info(f"📊 [FASE 1: EXTRACCIÓN] Completada - Datos extraídos: {len(data_keys)} campos, tamaño: {data_size} chars. Ejecutando Fase 2 (presentación) automáticamente...")

        if phase == 'presentation':
            # Marcar como presentación completada
            result['__phase__'] = 'presentation'
            result['__presentation_complete__'] = True
            result['__satisfied__'] = True  # IA satisfecha, no necesita más procesamiento
            # MODO RAW: Marcar explícitamente para direct return si tiene formatted_text
            if result.get('formatted_text'):
                result['__return_direct__'] = True
                result['__raw_mode__'] = True
            # Log visible de presentación completada con información del resultado
            result_size = len(str(result))
            result_keys = list(result.keys())
            # Contar elementos si es una lista o dict con listas
            item_count = 0
            if 'data' in result and isinstance(result['data'], (list, dict)):
                if isinstance(result['data'], list):
                    item_count = len(result['data'])
                elif isinstance(result['data'], dict):
                    # Contar elementos en el primer campo que sea lista
                    for key, value in result['data'].items():
                        if isinstance(value, list):
                            item_count = len(value)
                            break
            _logger.info(f"✅ [FASE 2: PRESENTACIÓN] Completada - Resultado procesado: {len(result_keys)} campos, {item_count} elementos, tamaño: {result_size} chars. IA satisfecha, direct return activado.")
            result['__phase__'] = result.get('__phase__', 'extraction')
            _logger.info(f"📋 [FASE AUTO-DETECTADA] Resultado marcado como listo para presentación (fase: {result.get('__phase__')})")

        # ============================================================
        # APLICAR LOGICA FINAL DE ALERT MODE
        # ============================================================
        if return_mode == 'direct_to_user':
            result['__return_direct__'] = True
            _logger.info("🚀 [RETURN_MODE] Forzando direct_return por solicitud explícita (direct_to_user)")
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
    # Serializar resultado una sola vez
    # El formato MCP requiere que 'text' sea una cadena JSON

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

    # Crear respuesta con el JSON serializado en 'text'
    response = {
        'content': [
            {
                'type': 'text',
                'text': result_json
            }
        ]
    }

    # Registrar log de operación exitosa
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
