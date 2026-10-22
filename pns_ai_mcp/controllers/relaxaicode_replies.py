# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""What relaxaicode answers: output caps, trusted HTML, error and user replies, log rows."""

import inspect
import json
import logging

_logger = logging.getLogger(__name__)


# ── Topes anti-DoS del resultado (H4). NO frenan la asignación en memoria
# DURANTE el exec (eso lo acota el worker de Odoo vía limit_time_real /
# limit_time_cpu / limit_memory_hard, ver docs/seguridad_dos_cajas.md), pero sí
# evitan que una salida patológica inunde la respuesta SSE, el histórico y los
# logs. Son comprobaciones O(1) (len de lista / len de str), sin serializar todo.
# Fixed on purpose (PNS-18): a fuse, not a Settings knob and not an LLM
# privacy cap. compose-model may still send a result that fits. ACL decides
# what can be read; this does not hide fields.
RELAXAICODE_MAX_RESULT_ROWS = 50000      # filas en data/groups
RELAXAICODE_MAX_TEXT_CHARS = 2_000_000   # ~2 MB de texto/HTML por respuesta


# Only these __fmt_type__ values may paint formatted_text into Chatboo.
# - server_side_python: set by maybe_attach_formatted_text (trusted renderer)
# - author_html: set by skill_runtime / platform, never by free LLM sandbox
# - local_*: client-side helpers in main.py
_TRUSTED_FMT_TYPES = frozenset({
    'server_side_python',
    'author_html',
    'local_json',
    'local_raw',
})


def _reject_untrusted_formatted_text(result, *, after_server_render=False):
    from odoo.addons.pns_ai_mcp.utils.untrusted_html_contract import (
        reject_untrusted_formatted_text,
    )
    return reject_untrusted_formatted_text(
        result,
        after_server_render=after_server_render,
    )


def _enforce_result_size_cap(result):
    """Devuelve un mensaje de error si el resultado excede los topes; si no, None.

    Sólo mira longitudes baratas (número de filas y tamaño de textos), nunca
    serializa la estructura completa (evita amplificar el propio DoS).
    """
    if isinstance(result, dict):
        for _key in ('data', 'groups'):
            _val = result.get(_key)
            if isinstance(_val, list) and len(_val) > RELAXAICODE_MAX_RESULT_ROWS:
                return (
                    "Result too large: '%s' has %d rows (max %d). Aggregate, filter "
                    "or paginate the query (e.g. read_group / limit)."
                    % (_key, len(_val), RELAXAICODE_MAX_RESULT_ROWS)
                )
        for _key in ('formatted_text', 'text', 'html'):
            _val = result.get(_key)
            if isinstance(_val, str) and len(_val) > RELAXAICODE_MAX_TEXT_CHARS:
                return (
                    "Result too large: '%s' is %d chars (max %d). Summarize or "
                    "paginate the output." % (_key, len(_val), RELAXAICODE_MAX_TEXT_CHARS)
                )
    elif isinstance(result, str) and len(result) > RELAXAICODE_MAX_TEXT_CHARS:
        return (
            "Result too large: %d chars (max %d). Summarize or paginate the output."
            % (len(result), RELAXAICODE_MAX_TEXT_CHARS)
        )
    return None


def _log_where():
    """Devuelve 'modulo.funcion' del llamador para logs."""
    frame = inspect.currentframe().f_back
    mod = frame.f_globals.get("__name__", "?")
    if "." in mod:
        mod = mod.split(".")[-1]  # tools_relaxaicode en vez de ruta completa
    return f"{mod}.{frame.f_code.co_name}"


def _log_relaxaicode_execution(
    controller,
    code,
    result_data,
    result_summary,
    operation_type='read',
    agent_llm=None,
    context_data=None,
    phase=None,
    return_mode=None,
):
    """Registra ejecución relaxaicode (éxito o error) vía el controlador."""
    try:
        additional_info = None
        if phase is not None or return_mode is not None:
            additional_info = f"Phase: {phase}, Return: {return_mode}"
        controller._log_mcp_operation(
            operation_type=operation_type,
            tool_name='relaxaicode',
            prompt_data={
                'code': code[:5000] if code and len(code) > 5000 else code,
                'context': context_data,
            },
            result_data=result_data,
            result_summary=result_summary,
            additional_info=additional_info,
            code_to_execute=code,
            agent_llm=agent_llm,
        )
    except Exception as log_err:
        _logger.warning(f"[{_log_where()}] No se pudo registrar log MCP: {log_err}")


def _format_user_facing_response(user_message, *, alert_class='alert-warning'):
    """Terminal Chatboo message — plain human text, no JSON-RPC / error_type."""
    import html

    text = (user_message or '').strip()
    if not text:
        text = 'Something went wrong.'
    escaped = html.escape(text).replace('\n', '<br/>\n')
    formatted = (
        f'<div class="alert {alert_class} mb-0" role="alert">{escaped}</div>'
    )
    return {
        'content': [{'type': 'text', 'text': text}],
        'isError': True,
        '__direct_return__': True,
        '__stop_after_direct__': True,
        '__no_footer__': True,
        '__fmt_type__': 'author_html',
        'formatted_text': formatted,
    }


def _format_error_response(error_code, error_message, additional_data=None, retryable=False):
    # Formatea un error en el formato MCP estándar (content con text JSON).
    # Args:
    #     error_code: Código de error JSON-RPC
    #     error_message: Mensaje de error
    #     additional_data: Diccionario con datos adicionales (opcional)
    #     retryable: True si es un error del código generado por el LLM (validación
    #         AST, error de ejecución, result no asignado...). En ese caso el error
    #         se DEVUELVE al modelo como salida de tool para que se auto-corrija
    #         (no lleva __direct_return__ ni formatted_text, así el motor lo reenvía
    #         al LLM). El bucle ReAct está acotado por MAX_ROUNDS. retryable=False
    #         (por defecto) = error terminal que se muestra directamente al usuario.
    # Returns:
    #     dict: Respuesta de error en formato MCP content
    msg = f"ERROR ({error_code}): {error_message}"
    if additional_data:
        msg += f"\nDetails: {json.dumps(additional_data, indent=2, default=str)}"

    if retryable:
        # Error del código del LLM: volver al modelo para que regenere el código.
        # Sin __direct_return__ ni formatted_text para que el motor NO lo vuelque al
        # usuario y lo reenvíe como resultado de tool (auto-corrección ReAct).
        return {
            'content': [{'type': 'text', 'text': msg}],
            'isError': True,
            '__force_retry__': True,
        }

    # Error terminal: frase humana al chat (sin código JSON-RPC ni "Tipo: …").
    return _format_user_facing_response(error_message)


def _relaxaicode_log_prompt(code, context_data):
    return {
        'code': (code[:5000] if code and len(code) > 5000 else code),
        'context': context_data,
    }


def _keyerror_missing_model_response(model_name, env=None, locale='en_US'):
    """KeyError de modelo: sugerir vecinos del registry (sin contexto de dominio)."""
    from ..utils.model_name_suggest import (
        format_missing_model_hint,
        suggest_model_names,
    )
    available = ()
    try:
        if env is not None:
            available = list(getattr(env, 'registry', None) or env)
    except Exception:
        available = ()
    suggestions = suggest_model_names(model_name, available)
    enhanced_msg = format_missing_model_hint(
        model_name, suggestions, locale=locale or 'en_US',
    )
    details = {
        'error_type': 'KeyError',
        'model_name': model_name,
        'suggested_action': 'use_suggested_model' if suggestions else 'list_registry',
    }
    if suggestions:
        details['suggested_models'] = suggestions
    else:
        details['suggested_action'] = 'consult_contexts'
        details['suggested_contexts'] = [
            'contexts_index_core',
            f'corporative_terms_{locale or "en_US"}',
        ]
    return _format_error_response(
        -32603,
        enhanced_msg,
        details,
        retryable=True,
    )
