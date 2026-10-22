# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""Replies for a relaxaicode run that failed: the exception, no result, tool errors."""

import logging
import re

from .relaxaicode_replies import (
    _format_error_response,
    _format_user_facing_response,
    _keyerror_missing_model_response,
    _log_relaxaicode_execution,
    _log_where,
)

_logger = logging.getLogger(__name__)


def _exec_error_response(controller, exec_error, code, safe_context, agent_llm,
                         context_data, phase, return_mode):
    """The reply for an exception raised while the code ran, logged on the turn."""
    from odoo.exceptions import (
        AccessError, MissingError, UserError, ValidationError,
    )
    from odoo.addons.pns_ai_mcp.utils.skill_errors import friendly_skill_error

    error_msg = str(exec_error)
    error_type = type(exec_error).__name__

    from odoo.addons.pns_ai_mcp.utils.error_ux import (
        groupby_stored_field_retry_hint,
        is_groupby_computed_field_error,
    )
    if is_groupby_computed_field_error(error_msg):
        error_response = _format_error_response(
            -32603,
            groupby_stored_field_retry_hint(),
            {'error_type': error_type},
            retryable=True,
        )
        _log_relaxaicode_execution(
            controller, code, error_response,
            f"{error_type}: {error_msg}",
            operation_type='read', agent_llm=agent_llm,
            context_data=context_data,
            phase=phase, return_mode=return_mode,
        )
        return error_response

    # ACL / business denials are NOT code bugs — do not ReAct-retry;
    # show the (already translated) reason and stop.
    if isinstance(
        exec_error,
        (AccessError, MissingError, UserError, ValidationError),
    ):
        try:
            _env = controller._get_env_for_operation('read')
        except Exception:
            _env = getattr(controller, 'env', None)
        user_msg = friendly_skill_error(exec_error, _env)
        _logger.info(
            "[%s] relaxaicode stopped for user-facing %s: %s",
            _log_where(), error_type, error_msg[:240],
        )
        error_response = _format_user_facing_response(user_msg)
        _log_relaxaicode_execution(
            controller, code, error_response,
            f"{error_type}: {error_msg}",
            operation_type='read', agent_llm=agent_llm,
            context_data=context_data,
            phase=phase, return_mode=return_mode,
        )
        return error_response

    # Log adicional para NameError específicamente
    if error_type == 'NameError' and 'env' in error_msg.lower():
        _logger.warning(f"[{_log_where()}] NameError con 'env' - posible contexto corrupto")

    # RecursionError leftover (e.g. intentional recursion that blew the
    # stack). Point the LLM at the common recipe-shadow mistake.
    if isinstance(exec_error, RecursionError) or error_type == 'RecursionError':
        error_response = _format_error_response(
            -32603,
            (
                'Error executing code: maximum recursion depth exceeded. '
                'Likely cause: a function redefined to call itself '
                '(def f(...): return f(...)). Call it with new args: '
                'result = name(...). If you need a new body, rewrite '
                'the function once without a self-call wrapper.'
            ),
            {'error_type': 'RecursionError'},
            retryable=True,
        )
        _log_relaxaicode_execution(
            controller, code, error_response,
            f"Error executing code: {error_msg}",
            operation_type='read', agent_llm=agent_llm,
            context_data=context_data,
            phase=phase, return_mode=return_mode,
        )
        return error_response

    # TypeError: list/dict sobre field.selection callable (cualquier serie).
    if error_type == 'TypeError':
        from ..utils.error_ux import (
            format_bool_membership_hint,
            format_join_sequence_hint,
        )
        from ..utils.field_selection import format_selection_iterable_hint
        sel_hint = (
            format_selection_iterable_hint(error_msg)
            or format_join_sequence_hint(error_msg)
            or format_bool_membership_hint(error_msg)
        )
        if sel_hint:
            error_response = _format_error_response(
                -32603,
                sel_hint,
                {'error_type': 'TypeError'},
                retryable=True,
            )
            _log_relaxaicode_execution(
                controller, code, error_response,
                f"Error executing code: {error_msg}",
                operation_type='read', agent_llm=agent_llm,
                context_data=context_data,
                phase=phase, return_mode=return_mode,
            )
            return error_response

    # KeyError: sugerir modelos del registry (el motor se conoce vía Odoo).
    if error_type == 'KeyError':
        # En Python 3, str(KeyError('x')) es 'x'. No tiene el prefijo "KeyError: "
        model_name = error_msg.strip("'").strip('"')
        if model_name:
            _locale = safe_context.get(
                'user_lang', safe_context.get('userlang', 'en_US'),
            )
            error_response = _keyerror_missing_model_response(
                model_name,
                env=safe_context.get('env'),
                locale=_locale,
            )
            _log_relaxaicode_execution(
                controller, code, error_response,
                f"Error executing code: {error_msg}",
                operation_type='read', agent_llm=agent_llm,
                context_data=context_data,
                phase=phase, return_mode=return_mode,
            )
            return error_response

    # Si hay un error durante exec(), capturarlo y devolverlo
    # CRÍTICO: Si es NameError con 'env', verificar si el código realmente intentó usar env
    if error_type == 'NameError' and 'env' in error_msg.lower():
        # Verificar si el código generado realmente contiene 'env'
        pass  # NameError con env - ya logueado arriba

    # Error de ejecución del código del LLM: devolver al modelo para que
    # lo corrija (retryable). El bucle ReAct está acotado por MAX_ROUNDS.
    if (
        error_type == 'ValueError'
        and 'unsupported format character' in (error_msg or '')
    ):
        error_msg = (
            error_msg
            + '. [HINT] A literal % in a string used with % formatting '
            'is not a conversion. Write %% for a percent sign, or use '
            '.format() / an f-string.'
        )
    if error_type == 'AttributeError':
        from ..utils.error_ux import format_int_id_hint
        id_hint = format_int_id_hint(error_msg)
        if id_hint:
            error_response = _format_error_response(
                -32603,
                id_hint,
                {'error_type': 'AttributeError'},
                retryable=True,
            )
            _log_relaxaicode_execution(
                controller, code, error_response,
                id_hint,
                operation_type='read', agent_llm=agent_llm,
                context_data=context_data,
                phase=phase, return_mode=return_mode,
            )
            return error_response
    error_response = _format_error_response(
        -32603,
        f'Error executing code: {error_msg}',
        {'error_type': error_type},
        retryable=True,
    )
    _log_relaxaicode_execution(
        controller, code, error_response,
        f"Error executing code: {error_msg}",
        operation_type='read', agent_llm=agent_llm,
        context_data=context_data,
        phase=phase, return_mode=return_mode,
    )
    return error_response


def _missing_result_response(controller, code, safe_context, agent_llm,
                             context_data, phase, return_mode):
    """The reply when the code assigned no ``result``."""
    context_keys = [k for k in safe_context.keys() if not k.startswith('__')]
    diagnostic_info = {
        'available_variables': context_keys[:20],
        'code_preview': code[:500] if len(code) > 500 else code,
        'code_repr': repr(code),
        'code_type': str(type(code)),
        'has_result_key': 'result' in safe_context,
        'has_output_key': 'output' in safe_context,
        'all_context_keys': list(safe_context.keys())[:30]  # Todas las claves para diagnóstico completo
    }
    # El diagnóstico se devuelve en la respuesta JSON que el cliente MCP recibe
    # Está en content[0].text como JSON serializado
    error_response = _format_error_response(
        -32602,
        '[MANDATORY:RESULT] Code did not assign value to variable "result". [REQUIRED] Include line: result = {...} at end of code.',
        diagnostic_info,
        retryable=True,
    )
    _log_relaxaicode_execution(
        controller, code, error_response,
        'Code did not assign value to variable "result"',
        operation_type='read', agent_llm=agent_llm,
        context_data=context_data,
        phase=phase, return_mode=return_mode,
    )
    return error_response


def _name_error_response(e):
    """A NameError outside the sandbox run, with a hint for preloaded names."""
    error_msg = str(e)
    # Typo detection for common pre-loaded variables
    preloaded_vars = {
        'pk_datesep': 'pk_thousands_sep',  # Common confusion
        'odooversion': 'odoo_version'
    }

    hint = ""
    for typo, correct in preloaded_vars.items():
        if f"'{typo}' is not defined" in error_msg:
            hint = f" [HINT] You likely meant '{correct}' (with underscore). These variables are pre-loaded in the global scope."
            break

    if "'userlang' is not defined" in error_msg:
        hint = " [HINT] 'userlang' should be available (alias of user_lang). If you see this, report it - the locale fallback may need adjustment."
    elif "'context' is not defined" in error_msg:
        hint = " [HINT] The variable 'context' does NOT exist. Use 'env' directly to access Odoo."
    elif "'date' is not defined" in error_msg:
        hint = (
            " [HINT] 'date' is preloaded (datetime.date). Use date.today() / "
            "date(y, m, d), or datetime.date.today(). Do not import."
        )
    elif "'timedelta' is not defined" in error_msg:
        hint = (
            " [HINT] 'timedelta' is preloaded. Use timedelta(days=…) or "
            "datetime.timedelta(…)."
        )

    return _format_error_response(
        -32602,
        f"{error_msg}{hint}",
        {'error_type': 'NameError'},
        retryable=True,
    )


def _tool_error_response(controller, e):
    """Any other error of the tool itself, with a hint when the message has one."""
    error_msg = str(e)
    error_type = type(e).__name__
    error_data = {'error_type': error_type}

    # KeyError: sugerir modelos del registry instalado.
    if error_type == 'KeyError':
        model_name = error_msg.strip("'").strip('"')
        if model_name:
            try:
                _locale = controller._get_user_locale()
            except Exception:
                _locale = 'en_US'
            try:
                _env = controller._get_env_for_operation('read')
            except Exception:
                _env = None
            return _keyerror_missing_model_response(
                model_name, env=_env, locale=_locale,
            )

    # Add hints for common errors
    if "Non-stored field" in error_msg and "cannot be searched" in error_msg:
         error_msg += " [HINT] You are trying to search on a non-stored field (like 'arch'). Use the stored alternative (like 'arch_db') instead."

    # Add hint for Invalid leaf (incorrect field name in domain)
    if "Invalid leaf" in error_msg:
        field_match = re.search(r"Invalid leaf \('([^']+)'", error_msg)
        field_name = field_match.group(1) if field_match else "unknown"
        error_msg += f" [HINT] The field '{field_name}' in your domain filter is likely invalid for this model. Verify correct field names with get_context or ir.model.fields."

    # Transacción READ ONLY (caja A): el ORM intentó escribir de forma colateral
    if 'read-only' in error_msg.lower() or error_type == 'ReadOnlySqlTransaction':
        error_msg += (
            ' [HINT] The query caused a side-effect write (mail, tracking, '
            'a business method with side effects). Use plain search/read; '
            'to change data use safe_plan_request.'
        )

    return _format_error_response(
        -32603,
        f'Error in relaxaicode: {error_msg}',
        error_data,
        retryable=True,
    )
