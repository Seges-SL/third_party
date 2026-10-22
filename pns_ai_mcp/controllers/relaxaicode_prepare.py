# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""Before relaxaicode runs the code: clean, repair, validate, check access, fill the sandbox."""

import ast
import json
import logging
import re

from .validators import validate_relaxaicode_source_ast
from .validators_base import (
    ast_error_code,
    ast_literal,
    AST_SWITCH_TOOL_CODES,
    REPAIRABLE_AST_CODES,
)
from .relaxaicode_replies import (
    _format_error_response,
    _log_where,
    _relaxaicode_log_prompt,
)
from .relaxaicode_repair import _attempt_syntax_repair

_logger = logging.getLogger(__name__)


def _detect_phase(code):
    # Detecta automáticamente si el código es de extracción o presentación.
    # Args:
    #     code: Código Python a analizar
    # Returns:
    #     str: 'extraction' o 'presentation'
    if not code or not isinstance(code, str):
        return 'auto'
    
    code_lower = code.lower()
    
    # Indicadores de fase de presentación
    presentation_indicators = [
        'previous_result',
        'raw_data',
        'format',
        'formatted',
        'present',
        'display',
        'html',
        'csv',
        'excel',
        'pdf',
        'table',
    ]
    
    # Indicadores de fase de extracción
    extraction_indicators = [
        'search(',
        'browse(',
        'read(',
        'mapped(',
        'filtered(',
        'search_count(',
    ]
    
    # Contar indicadores
    presentation_count = sum(1 for indicator in presentation_indicators if indicator in code_lower)
    extraction_count = sum(1 for indicator in extraction_indicators if indicator in code_lower)
    
    # Si hay indicadores de presentación y no hay búsquedas, es presentación
    if presentation_count > 0 and extraction_count == 0:
        return 'presentation'
    
    # Si hay búsquedas y no hay indicadores de presentación, es extracción
    if extraction_count > 0 and presentation_count == 0:
        return 'extraction'
    
    # Por defecto, asumir extracción si hay búsquedas
    if extraction_count > 0:
        return 'extraction'
    
    # Si no hay indicadores claros, dejar que el sistema decida
    return 'auto'


def _strip_module_literals_or_reject(
    code,
    previous_result,
    context_data,
):
    """Strip pasted module-level datasets or return (code, reject_msg, extracted).

    Returns ``(cleaned_code, None, extracted)`` on success/no-op, or
    ``(code, error_message, {})`` when the paste cannot be recovered.
    *extracted* maps stripped names to recovered Python values when foldable.
    """
    from ..utils.relaxaicode_recipe import (
        bind_stripped_names_from_prior,
        module_level_data_literal_error,
        strip_module_level_data_literals,
    )
    lit_err = module_level_data_literal_error(code)
    if not lit_err:
        return code, None, {}
    cleaned, stripped_names, extracted = strip_module_level_data_literals(code)
    has_prior = bool(previous_result) or bool(
        (context_data or {}).get('previous_result')
        or (context_data or {}).get('raw_data')
    ) or bool(extracted)
    if stripped_names and cleaned is not None:
        preamble = bind_stripped_names_from_prior(stripped_names, extracted)
        candidate = (preamble + '\n\n' + cleaned) if preamble else cleaned
        if not module_level_data_literal_error(candidate):
            return candidate, None, extracted
    msg = lit_err
    if not has_prior:
        msg = (
            lit_err
            + " Pass the prior tool dataset as previous_result "
            "(or reference raw_data) — never paste the rows into code."
        )
    return code, msg, {}


def _agent_llm_label():
    """Who called the tool, for the log: MCP header, user agent or the engine."""
    agent_llm = None
    try:
        from odoo.http import request
        if request:
            agent_llm = request.httprequest.headers.get('X-Mcp-Agent-Llm')
            if not agent_llm and request.httprequest.headers.get('User-Agent'):
                agent_llm = request.httprequest.headers.get('User-Agent')
    except RuntimeError:
        # RuntimeError: object is not bound occurs when the request context has been popped
        # which happens during SSE generator execution.
        agent_llm = "AgentEngine"
    except Exception:
        pass
    return agent_llm


def _strip_pasted_rows(controller, code, previous_result, context_data, agent_llm):
    """Strip rows pasted into the code; a recovered list becomes ``previous_result``.

    Returns ``(code, previous_result, error_response)``.
    """
    code, lit_reject, extracted = _strip_module_literals_or_reject(
        code, previous_result, context_data,
    )
    if lit_reject:
        error_response = _format_error_response(
            -32602, lit_reject, retryable=True,
        )
        controller._log_mcp_operation(
            operation_type='read',
            tool_name='relaxaicode',
            prompt_data=_relaxaicode_log_prompt(
                code, context_data,
            ),
            result_data=error_response,
            result_summary='Reject: module_literal',
            code_to_execute=code,
            agent_llm=agent_llm,
        )
        return code, previous_result, error_response
    if extracted and not previous_result:
        for _v in extracted.values():
            if isinstance(_v, list):
                previous_result = {'data': _v}
                break
    return code, previous_result, None


def _reject_self_recursion(controller, code, context_data, agent_llm):
    """Drop shadow ``def f(): return f()`` wrappers; reject a lone self-call.

    Returns ``(code, error_response)``.
    """
    from ..utils.relaxaicode_recipe import (
        self_recursive_def_error,
        strip_self_recursive_shadow_defs,
    )
    code, _shadow_stripped = strip_self_recursive_shadow_defs(code)
    if _shadow_stripped:
        _logger.info(
            "[%s] stripped self-recursive shadow def(s): %s",
            _log_where(), ', '.join(_shadow_stripped),
        )
    sole_recur = self_recursive_def_error(code)
    if sole_recur:
        error_response = _format_error_response(
            -32602, sole_recur, retryable=True,
        )
        controller._log_mcp_operation(
            operation_type='read',
            tool_name='relaxaicode',
            prompt_data=_relaxaicode_log_prompt(
                code, context_data,
            ),
            result_data=error_response,
            result_summary='Reject: self-recursive def',
            code_to_execute=code,
            agent_llm=agent_llm,
        )
        return code, error_response
    return code, None


def _normalize_code(code):
    """Slips the code always gets fixed for: missing call, dates, escaped newlines."""
    from ..utils.relaxaicode_recipe import (
        ensure_date_param_coercion,
        ensure_module_result_call,
    )
    # LLM often sends a complete def + return and forgets result = name(...).
    code, _ensured = ensure_module_result_call(code)
    code, _coerced = ensure_date_param_coercion(code)

    # Normalizar saltos escapados SOLO si el código llega como un blob
    # de una sola línea (artefacto de transporte JSON). Si ya hay newlines
    # reales, NO tocar \\n: destruiría literales válidos como
    # 'footer': '\\n'.join(footer_lines) → AST EOL.
    if code.count('\n') < 2 and '\\n' in code:
        code = code.replace('\\n', '\n')
        code = code.replace('\\t', '\t').replace('\\r', '\r')

    # Reparar join partido en dos líneas (daño de replace ciego o LLM):
    #   'footer': '<NL>'.join(  →  'footer': '\n'.join(
    code = re.sub(
        r"(['\"])(footer|footer_md|pie)\1\s*:\s*(['\"])\s*\n\s*\3\.join\s*\(",
        r"\1\2\1: \3\\n\3.join(",
        code,
    )
    return code


def _validate_code(controller, code, context_data, phase, return_mode, agent_llm):
    """Soft repairs, then the AST check; one second pass when the error is repairable.

    Returns ``(code, requires_write, error_response)``.
    """
    # ============================================================
    # REPAIR SUAVE + VALIDACIÓN AST
    # ============================================================
    # 0) Quitar `in dir()/locals()/globals()/vars()` (sandbox ya inyecta
    #    previous_result/lugar/fecha). Evita rondas improductivas.
    from .validators_repair import (
        repair_cr_dbname, repair_locals_dir_checks, repair_percent_format_strings,
        repair_registry_models, strip_leaked_tool_markup,
    )
    from .validators_sort import repair_unsafe_sort_keys
    code, _xml_repaired = strip_leaked_tool_markup(code)
    code, _locals_repaired = repair_locals_dir_checks(code)
    code, _sk_repaired = repair_unsafe_sort_keys(code)
    code, _cr_repaired = repair_cr_dbname(code)
    code, _reg_repaired = repair_registry_models(code)
    code, _pct_repaired = repair_percent_format_strings(code)

    is_valid, validation_error, requires_write = validate_relaxaicode_source_ast(code)

    # Second pass: SyntaxError patch and/or leftover AST rewrites.
    # Gate on the stable ASCII code, never on translated/narrative text.
    should_attempt_repair = (
        not is_valid
        and ast_error_code(validation_error) in REPAIRABLE_AST_CODES
    )

    if should_attempt_repair:
        repaired_code, was_repaired = _attempt_syntax_repair(code)
        repaired_code, locals_fix = repair_locals_dir_checks(repaired_code)
        repaired_code, sk_fix = repair_unsafe_sort_keys(repaired_code)
        repaired_code, cr_fix = repair_cr_dbname(repaired_code)
        repaired_code, reg_fix = repair_registry_models(repaired_code)
        repaired_code, pct_fix = repair_percent_format_strings(repaired_code)
        was_repaired = (
            was_repaired or locals_fix or sk_fix or cr_fix or reg_fix or pct_fix
        )
        if was_repaired:
            # Revalidar el código reparado
            is_valid, validation_error, requires_write = validate_relaxaicode_source_ast(repaired_code)
            if is_valid:
                code = repaired_code
            else:
                _logger.warning(f"[{_log_where()}] Reparación no fue suficiente - error persistente: {validation_error[:100]}")

    if not is_valid:
        # EOL HINT only for string/syntax issues — not for lambda/sort bans
        # (that noise drowned the actionable fix in R5YZ/VFDP).
        enhanced_error = validation_error or ''
        _ast_code = ast_error_code(enhanced_error)
        _switch_tool = _ast_code in AST_SWITCH_TOOL_CODES
        if (
            not _switch_tool
            and 'formatted_text' in (code or '')
            and (phase == 'extraction' or phase == 'auto')
        ):
            enhanced_error = (
                '%s. [HINT] If error is "EOL while scanning string literal", '
                'you likely have unescaped newlines in your "formatted_text". '
                'Use \\n instead of literal newlines. "formatted_text" IS '
                'ALLOWED in Phase 1 for Fast Path execution.'
            ) % enhanced_error

        if _switch_tool:
            err_msg = 'AST Validation Error: %s' % enhanced_error
        else:
            err_msg = (
                'AST Validation Error: %s. [REQUIRED] Generate valid Python '
                'syntax. [REQUIRED] Assign output to the result variable. '
                'Follow the relaxaicode coding rules in your system context '
                '(allowed imports, no network — external HTTP goes through '
                'safe_plan_request op=fetch_url, never import '
                'urllib/requests/http).'
            ) % enhanced_error

        error_response = _format_error_response(
            -32602,
            err_msg,
            {
                'error_type': 'ValidationError',
                'validation_error': enhanced_error,
                'ast_code': _ast_code,
                'phase': phase,
            },
            retryable=True,
        )
        # Registrar log de error de validación
        controller._log_mcp_operation(
            operation_type='read',
            tool_name='relaxaicode',
            prompt_data=_relaxaicode_log_prompt(
                code, context_data,
            ),
            result_data=error_response,
            result_summary=f"AST Validation Error: {enhanced_error}",
            additional_info=f"Phase: {phase}, Return: {return_mode}",
            code_to_execute=code,
            agent_llm=agent_llm
        )
        return code, False, error_response
    return code, requires_write, None


def _permission_denied_response(controller, operation_type, code, context_data):
    """The reply when the caller may not run this kind of operation, else None."""
    has_permission, permission_error = controller._check_mcp_permissions(operation_type)
    if not has_permission:
        # Obtener nombre del usuario de forma segura
        env_read = controller._get_env_for_operation('read')
        user_id = env_read.uid

        user_name = "desconocido"
        try:
            user_record = env_read['res.users'].browse(user_id)
            if user_record.exists():
                user_name = user_record.name or user_record.login or "desconocido"
        except Exception:
            pass

        # Mensaje simple igual que en endpoints estáticos
        message = f'Usuario "{user_name}" no tiene permisos de escritura con el servidor MCP. Operación abortada.'

        # Cancelar automáticamente todas las verificaciones pendientes de este usuario
        cancelled_count = controller._cancel_pending_verifications_for_user(user_id, f"falta de permisos de escritura (not in group_ai_writer) para relaxaicode")

        # Usar formato content para que sea visible en la interfaz de la IA (igual que endpoints estáticos)
        error_response = {
            'content': [
                {
                    'type': 'text',
                    'text': json.dumps({
                        'error': True,
                        'code': -32000,
                        'message': message,
                        'tool_name': 'relaxaicode',
                        'user_name': user_name,
                        'user_id': user_id,
                        'cancelled_operations': cancelled_count
                    }, indent=2, default=str)
                }
            ]
        }

        _logger.warning(f"[{_log_where()}] Usuario {user_name} (ID: {user_id}) sin permiso de escritura IA (group_ai_writer) - abortando")

        # Registrar log de error de permisos
        controller._log_mcp_operation(
            operation_type=operation_type,
            tool_name='relaxaicode',
            prompt_data={'code': code[:5000] if len(code) > 5000 else code, 'context': context_data},
            result_data=error_response,
            result_summary="Permission error: not in group_ai_writer for relaxaicode",
            additional_info=f"Usuario {user_name} (ID: {user_id}) intentó ejecutar código que requiere escritura sin permisos. Operación abortada inmediatamente."
        )

        return error_response
    return None


def _read_only_response():
    """Box A only reads: writes go through safe_plan_request."""
    # CAJA A: relaxaicode es SOLO LECTURA (se ejecuta sobre cursor READ ONLY).
    # Cualquier escritura se redirige a la caja B declarativa
    # (safe_plan_request): la IA NO escribe con código.
    return {
        'content': [{'type': 'text', 'text': json.dumps({
            'success': False,
            'requires_write': True,
            'message': (
                'relaxaicode is READ ONLY. To create, update, '
                'duplicate or delete records use the safe_plan_request '
                'tool with declarative operations (not code). Do not '
                'ask for any PIN; the user confirms in Odoo.'
            ),
        }, ensure_ascii=False, indent=2, default=str)}]
    }


def _fill_run_context(safe_context, context_data):
    """Caller variables and locale into the sandbox; env stays. An error reply, else None."""
    # Añadir datos del contexto proporcionado por el cliente
    # Según el estándar MCP, los prompts deben ser solicitados explícitamente
    # mediante prompts/list y prompts/get, no inyectarse automáticamente
    # CRÍTICO: Proteger solo variables de infraestructura (env, odoo_version, odoo_series).
    # Las variables de locale (user_lang, pk_*) NO se protegen para permitir la "virtualización" desde context_data.
    protected_vars = {
        'env', 'odoo_version', 'odoo_series', '__builtins__', '__import__'
    }

    # Verificar que env está presente ANTES de actualizar
    if 'env' not in safe_context:
        _logger.error(f"[{_log_where()}] CRÍTICO: env no está en safe_context después de build_safe_context")
        return _format_error_response(
            -32603,
            'Internal error: env not available in execution context',
            {'error_type': 'ConfigurationError'}
        )


    for key, value in context_data.items():
        if key not in protected_vars:
            safe_context[key] = value
        else:
            pass  # Variable protegida, ignorar sobrescritura

    # Garantizar variables de locale (cascada: default en_US)
    _user_lang = safe_context.get('user_lang') or 'en_US'
    if not isinstance(_user_lang, str):
        _user_lang = 'en_US'
    safe_context['user_lang'] = _user_lang
    safe_context['userlang'] = _user_lang
    safe_context['lang'] = _user_lang
    safe_context['locale'] = _user_lang

    # Verificar que env sigue presente DESPUÉS de actualizar
    if 'env' not in safe_context:
        _logger.error(f"[{_log_where()}] CRÍTICO: env desapareció de safe_context después de update")
        return _format_error_response(
            -32603,
            'Internal error: env lost from execution context',
            {'error_type': 'ConfigurationError'}
        )
    return None


def _holds_no_data(node):
    """True if *node* is fixed text, None or an empty literal container."""
    ok, value = ast_literal(node)
    if ok:
        return value is None or isinstance(value, str)
    if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
        return not node.elts
    if isinstance(node, ast.Dict):
        return not node.keys
    return False


def _is_preventive_code(code):
    """True if the code never reads env and only gives result a message or nothing.

    Language-blind: the shape of the code decides, never the words of the
    message or of its comments.
    """
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return False
    values = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id == 'env':
            return False
        if isinstance(node, ast.Assign):
            if any(isinstance(t, ast.Name) and t.id == 'result' for t in node.targets):
                values.append(node.value)
        elif isinstance(node, (ast.AugAssign, ast.AnnAssign)):
            if isinstance(node.target, ast.Name) and node.target.id == 'result':
                values.append(node.value)
    return bool(values) and all(v is not None and _holds_no_data(v) for v in values)


def _preventive_code_response(code):
    """The reply when the code only says env is missing instead of using it, else None."""
    if _is_preventive_code(code):
        reason = 'a fixed message or an empty result and no env query'
        _logger.warning(f"[{_log_where()}] Código preventivo detectado ({reason}) - no usa env correctamente")
        # NO ejecutar código preventivo - devolver error específico con mensaje MÁS AGRESIVO
        # CRÍTICO: Marcar con __preventive_code_error__ para que el orchestrator lo maneje de forma especial
        error_response = _format_error_response(
            -32602,
            f'[CRITICAL ERROR] You generated preventive code with {reason} instead of using env. This is WRONG. env EXISTS and is ALWAYS available. You MUST use env directly. DO NOT generate error messages. DO NOT add comments suggesting env is unavailable. DO NOT use try/except for env. USE IT DIRECTLY: employees = env["hr.employee"].search([]). Your generated code was: {code[:200]}...',
            {
                'error_type': 'PreventiveCodeError',
                'issue': f'LLM generated code with {reason} instead of using env',
                'expected': 'Code MUST use env directly: employees = env["hr.employee"].search([]); result = [{"id": e.id, "name": e.name} for e in employees]',
                'forbidden': 'DO NOT generate: result = "error message..." OR comments suggesting env is unavailable OR try/except blocks for env',
                'generated': code[:500],
                'action_required': 'Regenerate code using env directly. env is guaranteed to exist. Remove all preventive comments and error handling.',
                '__preventive_code_error__': True,  # Marca especial para el orchestrator
                '__force_retry__': True  # Forzar retry automático
            },
            retryable=True,
        )
        # Añadir marca especial al nivel superior de la respuesta
        error_response['__preventive_code_error__'] = True
        error_response['__force_retry__'] = True
        return error_response
    return None
