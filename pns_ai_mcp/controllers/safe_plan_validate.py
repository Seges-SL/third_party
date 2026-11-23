# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""Safe Plan steps: verbs, aliases, validation of a plan and its danger level."""

import logging
from odoo import _
from odoo.exceptions import UserError
from odoo.addons.pns_ai_mcp.utils.fetch_url_safe import validate_fetch_url_step
from .controller_helpers import (
    GROUP_AI_EXTERNAL_API,
    GROUP_AI_EXTERNAL_URL,
    GROUP_AI_WRITER,
)

_logger = logging.getLogger(__name__)


# A plan needs at least one of these (see check_safe_plan_permissions).
_PLAN_GROUPS = (GROUP_AI_WRITER, GROUP_AI_EXTERNAL_URL, GROUP_AI_EXTERNAL_API)


# Historical re-export (docs / imports): canonical source = utils.fetch_url_safe.

# Allowed verbs. Basic CRUD is allowed on any model (Odoo ACLs still apply,
# since it runs as the human user).
# fetch_url: safe http/https methods. Whitelist + policy decide access.
# api_call: tool/operation of a registered external server (ai.api.server,
# mcp/openapi drivers). 'mcp_call' is accepted as a legacy ALIAS (existing
# skills/prompts) and normalized structurally to api_call — see _canonical_op.
# action: only codes pre-registered as ai.trusted.action records (closed
# vocabulary like the CRUD verbs — never a call to an arbitrary method). The
# module that owns the code (e.g. pns_acl_manager) declares the record as data
# (XML), without this module importing a single line of its Python.
ALLOWED_OPS = {
    'create', 'write', 'copy', 'unlink', 'fetch_url', 'api_call',
    'action', 'field_required',
}


# Legacy alias → canonical verb (structural mapping, not a business case):
# kept for one version so skills/prompts that still propose mcp_call do not break.
OP_ALIASES = {'mcp_call': 'api_call'}


OP_LABEL = {
    'create': 'Create',
    'write': 'Modify',
    'copy': 'Duplicate',
    'unlink': 'Delete',
    'fetch_url': 'Fetch URL',
    'api_call': 'External API call',
    'action': 'Action',
    'field_required': 'Field required',
}


def _canonical_op(op):
    """Canonical verb of a step (resolves legacy aliases with a log notice)."""
    if op in OP_ALIASES:
        _logger.info(
            "MCP: legacy safe-plan op %r normalized to %r", op, OP_ALIASES[op],
        )
        return OP_ALIASES[op]
    return op


def normalize_plan_ops(steps):
    """Normalize a plan's alias verbs in place to their canonical form."""
    for step in steps or []:
        if isinstance(step, dict) and step.get('op') in OP_ALIASES:
            step['op'] = _canonical_op(step['op'])
    return steps


def _resolve_refs(value, ref_map):
    """Replace "$ref" markers with the real id created in an earlier step.

    Walks dicts and lists. A string starting with '$' is read as a
    reference to the 'ref' of a previous step (e.g. "$contacto").
    """
    if isinstance(value, str) and value.startswith('$'):
        key = value[1:]
        return ref_map.get(key, value)
    if isinstance(value, dict):
        return {k: _resolve_refs(v, ref_map) for k, v in value.items()}
    if isinstance(value, list):
        return [_resolve_refs(v, ref_map) for v in value]
    return value


def _meta_crud_block_error(model):
    """CRUD on view/field metadata is closed; required uses op=field_required."""
    from ..utils.field_required_plan import field_required_hint
    if model == 'ir.ui.view':
        return (
            "Do not create, write or delete ir.ui.view via CRUD. "
            + field_required_hint()
        )
    if model == 'ir.model.fields':
        return (
            "Do not create, write or delete ir.model.fields via CRUD. "
            + field_required_hint()
        )
    return None


def _owed_to_the_model(env, model, values):
    """What this model asks of the assistant and the plan does not carry.

    Beyond the columns the ORM refuses to write empty: a record can be born
    fine and still be of no use to anyone. The condition belongs to whoever
    owns the model; here it only closes the door.
    """
    from ..utils.required_fields import missing_for_agent

    owed = missing_for_agent(env, model, values)
    if not owed:
        return None
    listed = ', '.join('%s (%s)' % (label, name) for name, label, _t in owed)
    said = (
        '%s needs these before it can be created, and the plan does not '
        'carry them: %s. Ask the user for them in this turn instead of '
        'proposing the write.' % (model, listed)
    )
    if any(ftype in ('date', 'datetime') for _n, _l, ftype in owed):
        # Said out loud a day travels through the transcriber; a channel with
        # a picker should use it rather than take dictation.
        said += (
            ' One of them is a date: ask for it the way your channel asks '
            'for dates, if it has a way.'
        )
    return said


def _plan_display_model(steps):
    """Model label for the authorization list (not fetch_url for actions)."""
    for step in steps or []:
        if not isinstance(step, dict):
            continue
        if step.get('model'):
            return step['model']
        op = _canonical_op(step.get('op'))
        if op == 'action':
            args = step.get('args') or {}
            if isinstance(args, dict) and args.get('model'):
                return args['model']
            return step.get('action_code') or 'action'
        if op == 'fetch_url':
            return 'fetch_url'
        if op == 'api_call':
            return step.get('server') or 'api_call'
    return 'action'


def validate_safe_plan(steps, env):
    """Validate the plan against the closed vocabulary. Returns (ok, error).

    Normalizes legacy aliases (mcp_call → api_call) BEFORE validating, so the
    rest of the pipeline (danger, describe, execute) only sees canonical verbs.
    """
    if not isinstance(steps, list) or not steps:
        return False, "The plan ('steps') must be a non-empty list of operations."
    normalize_plan_ops(steps)
    from ..utils.module_update_heal import module_update_alone_error
    alone_err = module_update_alone_error(steps)
    if alone_err:
        return False, alone_err
    for i, step in enumerate(steps):
        if not isinstance(step, dict):
            return False, f"Step {i + 1}: each operation must be an object."
        op = step.get('op')
        if op not in ALLOWED_OPS:
            return False, (
                f"Step {i + 1}: invalid 'op' ({op!r}). "
                "Allowed: create, write, copy, unlink, fetch_url, api_call, "
                "action, field_required."
            )
        if op == 'field_required':
            step.pop('_views_picked', None)
            if not step.get('model') or not isinstance(step.get('model'), str):
                return False, f"Step {i + 1}: field_required requires 'model'."
            if not step.get('field') or not isinstance(step.get('field'), str):
                return False, f"Step {i + 1}: field_required requires 'field'."
            if env is not None:
                if step['model'] not in env:
                    return False, f"Step {i + 1}: unknown model {step['model']!r}."
                if step['field'] not in env[step['model']]._fields:
                    return False, (
                        f"Step {i + 1}: field {step['field']!r} does not "
                        f"exist on {step['model']}."
                    )
                if not env.user.has_group('pns_ai_mcp.group_ai_admin'):
                    return False, (
                        "Step %s: field_required requires AI Administrator."
                        % (i + 1,)
                    )
                if not env.user.has_group('base.group_system'):
                    return False, (
                        "Step %s: field_required changes views and fields; "
                        "it needs the Settings administrator role." % (i + 1,)
                    )
            continue
        if op == 'action':
            action_code = step.get('action_code')
            from ..utils.field_required_plan import (
                field_required_hint, is_required_atom,
            )
            if is_required_atom(action_code):
                return False, 'Step %s: %s' % (i + 1, field_required_hint())
            action = env['ai.trusted.action']._get(action_code)
            if not action:
                return False, (
                    f"Step {i + 1}: unknown trusted action "
                    f"({action_code!r}). Not a registered action_code."
                )
            if step.get('args') is not None and not isinstance(step.get('args'), dict):
                return False, f"Step {i + 1}: action 'args' must be an object."
            # Extra groups (e.g. AI Administrator for system actions) at
            # propose — same check execute_safe_plan runs before apply.
            if env is not None and not action.user_has_required_groups(env.user):
                return False, (
                    "Step %s: trusted action %r requires a group this user "
                    "does not have (AI Administrator for system actions)."
                    % (i + 1, action.code)
                )
            # Preview is read-only and raises UserError when the plan cannot
            # apply (no view shows the field, unknown module, …). Fail here
            # so we never create a Confirm toast that will bounce.
            if env is not None:
                try:
                    action._preview(**(step.get('args') or {}))
                except UserError as exc:
                    return False, 'Step %s: %s' % (
                        i + 1, exc.args[0] if exc.args else str(exc),
                    )
        # --- CRUD validations (require 'model') ---
        if op in ('create', 'write', 'copy', 'unlink'):
            if not step.get('model') or not isinstance(step.get('model'), str):
                return False, f"Step {i + 1}: missing 'model' (Odoo model name)."
            blocked = _meta_crud_block_error(step.get('model'))
            if blocked:
                return False, 'Step %s: %s' % (i + 1, blocked)
            if env is not None and step['model'] in env:
                from ..utils.privilege_cusp import crud_cusp_error
                cusp = crud_cusp_error(env, step['model'], op, step)
                if cusp:
                    return False, 'Step %s: %s' % (i + 1, cusp)
        if op == 'create' and not isinstance(step.get('values'), dict):
            return False, f"Step {i + 1}: 'create' requires 'values' (field object)."
        if op == 'create' and env is not None:
            from ..utils.required_fields import missing_required_fields

            missing = missing_required_fields(
                env, step.get('model'), step.get('values'),
            )
            if missing:
                listed = ', '.join(
                    '%s (%s)' % (label, name) for name, label in missing
                )
                return False, (
                    f"Step {i + 1}: {step['model']} cannot be created without "
                    f"these fields and the plan leaves them empty: {listed}. "
                    "Ask the user for what is missing — offer candidate rows "
                    "when the field points at a record, so they can tap one "
                    "instead of dictating it. Do not invent a value."
                )
            owed = _owed_to_the_model(env, step.get('model'), step.get('values'))
            if owed:
                return False, owed
        if op == 'write':
            if not isinstance(step.get('values'), dict):
                return False, f"Step {i + 1}: 'write' requires 'values' (field object)."
            if step.get('ids') is None and step.get('domain') is None:
                return False, f"Step {i + 1}: 'write' requires 'ids' or 'domain'."
        if op == 'copy' and step.get('id') is None:
            return False, f"Step {i + 1}: 'copy' requires 'id' (record to duplicate)."
        if op == 'unlink' and step.get('ids') is None and step.get('domain') is None:
            return False, f"Step {i + 1}: 'unlink' requires 'ids' or 'domain'."
        # --- fetch_url validation (safe methods only) ---
        if op == 'fetch_url':
            ok_fetch, err_fetch = validate_fetch_url_step(step, step_index=i)
            if not ok_fetch:
                return False, err_fetch
        # --- api_call validation ---
        if op == 'api_call':
            server = step.get('server', '')
            tool = step.get('tool', '')
            if not isinstance(server, str) or not server:
                return False, f"Step {i + 1}: 'api_call' requires 'server' (API server code)."
            if not isinstance(tool, str) or not tool:
                return False, f"Step {i + 1}: 'api_call' requires 'tool' (tool/operation name)."
            # Exact active code only (no soft-match). Unknown → fail propose
            # so the LLM retries with a catalogue code (trusted auto-confirm).
            if env is not None:
                from ..lib.api.validate_tool_args import UNKNOWN_SERVER_MSG

                Server = env['ai.api.server'].sudo()
                srv = Server.search(
                    [('code', '=', server), ('active', '=', True)], limit=1,
                )
                if not srv:
                    active_codes = Server.search(
                        [('active', '=', True)],
                    ).mapped('code')
                    listed = ', '.join(active_codes[:20]) or '(none)'
                    return False, _(UNKNOWN_SERVER_MSG) % (server, listed)
                schema_err = _api_call_schema_error(
                    srv, tool, step.get('arguments') or {},
                )
                if schema_err:
                    return False, schema_err
    return True, None


# ── Danger level (traffic light) ──────────────────────────────────────────
# Informational only — determines the colour of the confirmation toast but
# does NOT change the confirmation protocol.  Every operation (including
# fetch_url) goes through a simple single-click Confirm/Cancel toast.
# Only 'high' (unlink) adds a 5-second cooldown before the Confirm button
# becomes clickable.

# Base danger per op. fetch_url is dynamic: whitelisted = low, else = medium.
_OP_DANGER = {
    'create': 'low',
    'copy': 'low',
    'fetch_url': 'low',   # default; overridden at runtime if not whitelisted
    'api_call': 'medium',  # external server call
    'write': 'medium',
    'unlink': 'high',
    'field_required': 'medium',
}


def compute_danger_level(steps, env=None):
    """Compute the highest danger level across all steps in the plan.

    The danger level is **informational** (traffic-light colour on the toast).
    It does NOT alter the confirmation protocol: every operation requires a
    simple single-click confirmation, except 'unlink' which adds a 5-second
    cooldown.

    For fetch_url steps, the danger depends on whitelist and url_access_policy:
    whitelisted or open policy → low (green); whitelist_only and admin must
    add a new domain → medium (amber).  Never 'high' (no cooldown for URLs).

    Returns one of: 'low', 'medium', 'high'.
    """
    from urllib.parse import urlparse
    levels = {'low': 0, 'medium': 1, 'high': 2}
    max_level = 0
    for step in (steps or []):
        op = _canonical_op(step.get('op', ''))
        if op == 'fetch_url' and env:
            url = step.get('url', '')
            hostname = (urlparse(url).hostname or '').lower()
            Whitelist = env['ai.url.whitelist']
            status = Whitelist._fetch_url_access_status(hostname, user=env.user)
            danger = 'low' if status == 'allowed' else 'medium'
        elif op == 'api_call' and env:
            server_code = step.get('server', '')
            srv = env['ai.api.server'].sudo().search(
                [('code', '=', server_code), ('active', '=', True)], limit=1)
            if not srv:
                danger = 'high'
            elif srv.trusted:
                danger = 'low'   # trusted server → auto-confirmed, no toast
            else:
                danger = 'medium'
        elif op == 'action':
            action = env['ai.trusted.action']._get(step.get('action_code')) if env else None
            danger = action.danger if action else 'high'
        else:
            danger = _OP_DANGER.get(op, 'medium')
        max_level = max(max_level, levels.get(danger, 1))
    return {0: 'low', 1: 'medium', 2: 'high'}[max_level]


# ── api_call: call a tool/operation on an external API server ─────────────

def _api_call_schema_error(srv, tool_name, arguments):
    """Fail before HTTP when catalogue inputSchema marks nested required keys.

    Unknown tools skip this check (the driver still fails at call time).
    Empty schemas are a no-op. Message is translated; English msgid is LLM-facing.
    """
    from ..lib.api.validate_tool_args import check_tool_arguments

    tool = None
    for item in srv.get_tools_list() or []:
        if isinstance(item, dict) and item.get('name') == tool_name:
            tool = item
            break
    if not tool:
        return None
    schema = tool.get('inputSchema') or tool.get('input_schema') or {}
    issue = check_tool_arguments(schema, arguments)
    if not issue:
        return None
    if issue['kind'] == 'missing':
        return _(
            "Missing required property '%s' at %s (tool inputSchema)."
        ) % (issue['name'], issue['path'])
    return _(
        "Property at %s must be %s (tool inputSchema)."
    ) % (issue['path'], issue['expected'])
