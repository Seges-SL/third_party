# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""MCP tools for relaxaicode."""

from .context_builder import build_safe_context, compile_sandbox
from .mcp_decorators import mcp_tool
from .relaxaicode_replies import (
    _format_error_response,
    _reject_untrusted_formatted_text,
)
from .relaxaicode_prepare import (
    _agent_llm_label,
    _detect_phase,
    _fill_run_context,
    _normalize_code,
    _permission_denied_response,
    _preventive_code_response,
    _read_only_response,
    _reject_self_recursion,
    _strip_pasted_rows,
    _validate_code,
)
from .relaxaicode_failures import (
    _exec_error_response,
    _missing_result_response,
    _name_error_response,
    _tool_error_response,
)
from .relaxaicode_outcome import (
    _link_and_picture_rows,
    _present_result,
    _result_of,
    _success_response,
    _too_large_response,
)


@mcp_tool(
    name='relaxaicode',
    description=(
        '[CRITICAL] Execute Python in Odoo (ORM via env). Use for ALL data/table '
        'queries. Assign "result". A named def is optional; if you use one, call '
        'it: def name(...): …; result = name(...). (def allowed; class forbidden; '
        'return only inside def). Prefer preloaded modules (datetime, date, '
        'timedelta, json, operator, math, re, …). Optional imports ONLY from the '
        'AST whitelist — never os/sys/odoo/subprocess/pickle. Return list-of-dicts '
        'for tables; the server renders HTML. If a value can vary between calls, '
        'pass it as a parameter (same-kind filters → one list, not many positionals).'
    ),
    is_write=True,  # May be a write, depending on the code
    validate_schema=True,  # Enable validation with an explicit schema
    input_schema={
        "type": "object",
        "properties": {
            "code": {
                "type": "string",
                "description": (
                    "Python in global scope. Assign the answer to 'result'. "
                    "A named def is optional; if used, call it: "
                    "def name(...): …; result = name(...). "
                    "If a value can vary between calls, pass it as a parameter "
                    "(same-kind filters → one list arg, not many positionals). "
                    "Prefer preloaded modules; imports only from whitelist."
                ),
            },
            "context": {
                "type": "object",
                "description": "Optional dictionary context variables."
            },
            "phase": {
                "type": "string",
                "enum": ["auto", "extraction", "presentation"],
                "description": "Optional phase indicator: 'auto' (detect automatically), 'extraction' (Fase 1: extract data), 'presentation' (Fase 2: format data). Default: 'auto'."
            },
            "previous_result": {
                "type": "object",
                "description": (
                    "Optional. Fase 2 only, and only when a prior tool call "
                    "in THIS turn already returned rows. Available as "
                    "previous_result / raw_data. Do not start extraction with "
                    "result = previous_result.get('data') or [] — empty prior "
                    "data is [] and result['key'] crashes."
                ),
            },
            "return_mode": {
                "type": "string",
                "enum": ["smart", "direct_to_user", "inspect_result"],
                "description": "Control where the result is sent. 'smart' (default): Use auto-detection (large results -> user). 'direct_to_user': Force direct return to user (avoids LLM overflow, use for Final Answer). 'inspect_result': Force return to LLM (for chaining)."
            },
            "summary": {
                "type": "string",
                "description": "Optional human-readable description of what this data represents (e.g. 'Top 5 Customers by Revenue'). Used as the header for auto-generated tables."
            },
            "format": {
                "type": "string",
                "enum": ["markdown", "csv", "json"],
                "description": "Output format. 'markdown' (default): tables/lists. 'csv': Comma/Semicolon separated values (text). 'json': Pretty-printed JSON string."
            }
        },
        "required": []
    }
)
def tool_relaxaicode(
    controller,
    arguments: dict
):
    # MCP tool: runs native Python code in the relaxaicode environment
    # Isolated "box A" cursor (rollback + close in the finally).
    ro_cr = None
    try:
        code = arguments.get('code')
        phase = arguments.get('phase', 'auto')
        return_mode = arguments.get('return_mode', 'smart')
        summary = arguments.get('summary')
        previous_result = arguments.get('previous_result')
        agent_llm = _agent_llm_label()

        # CRITICAL: make sure code is a string
        # It can arrive as None, dict, list, etc. from badly deserialized JSON
        if code is not None and not isinstance(code, str):
            code = str(code)
        context_data = arguments.get('context') or {}

        # Strip pasted datasets so we never hold a huge rows=[] blob.
        if code and isinstance(code, str):
            code, previous_result, error_response = _strip_pasted_rows(
                controller, code, previous_result, context_data, agent_llm,
            )
            if error_response:
                return error_response

        # Check that code is a non-empty string after all the steps above.
        # Retryable: the model called the tool without code; let it fix itself
        # (ReAct loop bounded by MAX_ROUNDS) instead of stopping and dumping to the user.
        if not code or not isinstance(code, str):
            return _format_error_response(
                -32602,
                "relaxaicode was called with an empty 'code' argument. "
                "Provide the Python code to run in the 'code' parameter (use 'env' "
                "for the ORM and assign the answer to 'result'). Do not call the "
                "tool until the code is ready.",
                retryable=True,
            )

        # Safety net: defs should never carry pasted row snapshots.
        code, previous_result, error_response = _strip_pasted_rows(
            controller, code, previous_result, context_data, agent_llm,
        )
        if error_response:
            return error_response

        code, error_response = _reject_self_recursion(
            controller, code, context_data, agent_llm,
        )
        if error_response:
            return error_response
        code = _normalize_code(code)
        code, requires_write, error_response = _validate_code(
            controller, code, context_data, phase, return_mode, agent_llm,
        )
        if error_response:
            return error_response

        operation_type = 'write' if requires_write else 'read'
        error_response = _permission_denied_response(
            controller, operation_type, code, context_data,
        )
        if error_response:
            return error_response
        if requires_write:
            return _read_only_response()

        if phase == 'auto':
            phase = _detect_phase(code)

        # BOX A: isolated cursor; rollback on close (side-effect writes do not persist).
        ro_env, ro_cr = controller._get_readonly_env()
        safe_context = build_safe_context(
            controller,
            operation_type,
            previous_result=previous_result,
            env_override=ro_env
        )
        error_response = _fill_run_context(safe_context, context_data)
        if error_response:
            return error_response

        try:
            byte_code = compile_sandbox(code, '<relaxaicode>')
        except SyntaxError as e:
            return _format_error_response(
                -32602,
                f'Syntax error in code: {str(e)}',
                {'error_type': 'SyntaxError'},
                retryable=True,
            )
        except Exception as e:
            return _format_error_response(
                -32602,
                f'Compilation error: {str(e)}',
                {'error_type': type(e).__name__},
                retryable=True,
            )

        error_response = _preventive_code_response(code)
        if error_response:
            return error_response

        # Final fallback: locale not resolved (cascade default en_US)
        if 'user_lang' not in safe_context:
            safe_context['user_lang'] = 'en_US'
        if 'userlang' not in safe_context:
            safe_context['userlang'] = safe_context['user_lang']
        if 'lang' not in safe_context:
            safe_context['lang'] = safe_context['user_lang']
        if 'locale' not in safe_context:
            safe_context['locale'] = safe_context['user_lang']

        try:
            # CRITICAL: exec() with the same dict as globals and locals
            # makes sure assignments are stored in safe_context
            exec(byte_code, safe_context, safe_context)
        except Exception as exec_error:
            return _exec_error_response(
                controller, exec_error, code, safe_context, agent_llm,
                context_data, phase, return_mode, env=ro_env,
            )

        result = _result_of(safe_context)
        error_response = _too_large_response(
            controller, result, code, agent_llm, context_data, phase, return_mode,
        )
        if error_response:
            return error_response

        # Contract: free sandbox HTML is never user-facing. Library skills get
        # author_html; server tables stamp server_side_python later.
        # Restyle/pijama amounts and map tip continuity are context rules
        # (system_prompt + geo), not post-exec motor repairs.
        _reject_untrusted_formatted_text(result)

        error_response = _link_and_picture_rows(
            controller, result, safe_context, code, agent_llm,
            context_data, phase, return_mode, env=ro_env,
        )
        if error_response:
            return error_response
        error_response = _present_result(
            result, safe_context, phase, return_mode, summary, env=ro_env,
        )
        if error_response:
            return error_response

        # No result: the code did not assign 'result'
        if result is None:
            return _missing_result_response(
                controller, code, safe_context, agent_llm,
                context_data, phase, return_mode,
            )
        return _success_response(
            controller, result, code, context_data, operation_type,
        )

    except NameError as e:
        return _name_error_response(e)

    except Exception as e:
        return _tool_error_response(controller, e)

    finally:
        # Close the isolated box A cursor (rollback drops any side-effect write).
        if ro_cr is not None:
            try:
                ro_cr.rollback()
            except Exception:
                pass
            try:
                ro_cr.close()
            except Exception:
                pass
