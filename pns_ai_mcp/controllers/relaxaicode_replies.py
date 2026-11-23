# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""What relaxaicode answers: output caps, trusted HTML, error and user replies, log rows."""

import inspect
import json
import logging

_logger = logging.getLogger(__name__)


# ── Anti-DoS caps on the result (H4). They do NOT stop memory allocation
# DURING exec (the Odoo worker bounds that via limit_time_real /
# limit_time_cpu / limit_memory_hard, see docs/seguridad_dos_cajas.md), but they
# do keep a pathological output from flooding the SSE reply, the history and the
# logs. They are O(1) checks (list len / str len), with no full serialization.
# Fixed on purpose (PNS-18): a fuse, not a Settings knob and not an LLM
# privacy cap. compose-model may still send a result that fits. ACL decides
# what can be read; this does not hide fields.
RELAXAICODE_MAX_RESULT_ROWS = 50000      # rows in data/groups
RELAXAICODE_MAX_TEXT_CHARS = 2_000_000   # ~2 MB of text/HTML per reply


# Only these __fmt_type__ values may paint formatted_text into the chat.
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
    """Return an error message if the result goes over the caps; else None.

    Only looks at cheap lengths (row count and text size), never
    serializes the whole structure (so it does not amplify the DoS itself).
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
    """Return the caller's 'module.function' for logs."""
    frame = inspect.currentframe().f_back
    mod = frame.f_globals.get("__name__", "?")
    if "." in mod:
        mod = mod.split(".")[-1]  # tools_relaxaicode instead of the full path
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
    """Log a relaxaicode run (success or error) through the controller."""
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
        _logger.warning(f"[{_log_where()}] Could not record MCP log: {log_err}")


def _format_user_facing_response(user_message, *, alert_class='alert-warning'):
    """Terminal chat message — plain human text, no JSON-RPC / error_type."""
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
    # Format an error in the standard MCP format (content with JSON text).
    # Args:
    #     error_code: JSON-RPC error code
    #     error_message: Error message
    #     additional_data: Dict with extra data (optional)
    #     retryable: True if it is an error in the LLM-generated code (AST
    #         validation, run error, result not assigned...). Then the error
    #         is RETURNED to the model as tool output so it fixes itself
    #         (no __direct_return__ nor formatted_text, so the engine forwards it
    #         to the LLM). The ReAct loop is bounded by MAX_ROUNDS. retryable=False
    #         (default) = terminal error shown straight to the user.
    # Returns:
    #     dict: error response in MCP content format
    msg = f"ERROR ({error_code}): {error_message}"
    if additional_data:
        msg += f"\nDetails: {json.dumps(additional_data, indent=2, default=str)}"

    if retryable:
        # Error in the LLM code: go back to the model so it regenerates the code.
        # No __direct_return__ nor formatted_text, so the engine does NOT dump it on
        # the user and forwards it as a tool result (ReAct self-correction).
        return {
            'content': [{'type': 'text', 'text': msg}],
            'isError': True,
            '__force_retry__': True,
        }

    # Terminal error: a human sentence to the chat (no JSON-RPC code nor "Tipo: …").
    return _format_user_facing_response(error_message)


def _relaxaicode_log_prompt(code, context_data):
    return {
        'code': (code[:5000] if code and len(code) > 5000 else code),
        'context': context_data,
    }


def _keyerror_missing_model_response(model_name, env=None, locale='en_US'):
    """Model KeyError: suggest registry neighbours (no domain context)."""
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
