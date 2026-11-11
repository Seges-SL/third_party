# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""Supervised operation declaration (Box B).

The AI never executes operations directly: it only declares an intent as
data (a list of steps with closed verbs: create/write/copy/unlink/fetch_url/
api_call). That data is stored as a pending operation, the human is notified by
toast, and only when the human clicks Confirm in Odoo does the server run the
plan with fixed, audited code. The AI never sees this code nor can run it.

Danger levels (traffic light):
  - Low:    create, copy, fetch_url (whitelisted or open policy)
  - Medium: write, fetch_url (whitelist_only: admin must add the domain)
  - High:   unlink

fetch_url policy (instance-level, orthogonal to group_ai_external_url):
  - Safe methods only: GET, HEAD, OPTIONS, QUERY (RFC 10008) — no POST/PUT/…
  - Domain in whitelist (kind='web') -> auto-execute.
  - open policy + not listed -> auto-add to whitelist + auto-execute.
  - whitelist_only + not listed + non-admin -> blocked at propose.
  - whitelist_only + not listed + admin -> confirm toast, then add + execute.
"""

import json
import logging
from datetime import timedelta
from odoo import (
    api,
    fields,
    SUPERUSER_ID,
)
from .controller_helpers import check_safe_plan_permissions
from .mcp_decorators import mcp_tool

from .safe_plan_validate import (
    _canonical_op,
    compute_danger_level,
    _plan_display_model,
    _PLAN_GROUPS,
    validate_safe_plan,
)

from .safe_plan_describe import (
    _ack_tr,
    _all_steps_auto_confirmable,
    describe_safe_plan,
)

from .safe_plan_execute import (
    execute_safe_plan,
)

from .safe_plan_ack import (
    attach_verification_chat_hints,
    build_verification_followup_message,
)

_logger = logging.getLogger(__name__)


def _primary_operation_type(steps):
    """Main operation type for the verification (deletion/creation come first)."""
    ops = [_canonical_op(s.get('op')) for s in steps]
    if 'field_required' in ops:
        return 'write'
    if 'action' in ops:
        return 'action'
    if 'unlink' in ops:
        return 'unlink'
    if 'api_call' in ops:
        return 'api_call'
    if 'fetch_url' in ops:
        return 'fetch_url'
    if 'create' in ops or 'copy' in ops:
        return 'create'
    return 'write'


_PROPOSE_SCHEMA = {
    'type': 'object',
    'properties': {
        'steps': {
            'type': 'array',
            'description': (
                "List of declarative operations (NOT code). Each one: "
                "{op, ...}. op='create' -> {model, values{}, ref?}; "
                "op='write' -> {model, ids[] or domain[], values{}}; "
                "op='copy' -> {model, id, overrides{}?, ref?}; "
                "op='unlink' -> {model, ids[] or domain[]}; "
                "op='field_required' -> {model, field, required} "
                "(optional view_id/action_id; view_only=true skips the ORM). "
                "The chat lists views; the human picks them before Confirm. "
                "NEVER op=action view.set_field_required or field.set_required. "
                "op='action' -> {action_code, args{}} (closed codes of "
                "ai.trusted.action). Examples: module.update with args "
                "{module, operation} operation=install|upgrade|uninstall "
                "(NEVER module_ids or button); "
                "view.set_field_readonly|invisible|domain with args "
                "{model, field, view_ids[] or view_id}; "
                "view.reset_field_modifiers; user.add_group / "
                "user.remove_group with args {user_id, group}. "
                "NEVER write/create/unlink on ir.ui.view or ir.model.fields. "
                "op='fetch_url' -> {url, method?} (safe methods: GET default, "
                "HEAD, OPTIONS, or QUERY with body+content_type — RFC 10008; "
                "a whitelisted domain gets a quick confirm 🟢, "
                "any other domain asks for an extra confirm 🔴); "
                "op='api_call' -> {server, tool, arguments{}} (a tool of a "
                "registered external API server: MCP or OpenAPI). "
                "Use fetch_url for ad hoc web reads. HTTP mutations "
                "(POST/…) or unregistered APIs do not go in fetch_url. "
                "To chain steps, set 'ref' on one step and use '$ref' as a value in another "
                "(e.g. ref='contact' then \"partner_id\": \"$contact\")."
            ),
            'items': {'type': 'object'},
        },
        'title': {
            'type': 'string',
            'description': 'Short, readable title of the operation (shown to the human).',
        },
    },
    'required': ['steps'],
}


def capture_safe_plan_log_context(env):
    """Snapshot correlation + origin before nested cursor / tool body.

    ``create_verification`` opens its own cursor; capture here while the live
    HTTP request or AgentEngine env context is still available.
    """
    turn_corr = None
    origin = 'internal'
    client_ip = ''
    ctx = (env.context if env is not None else {}) or {}
    try:
        from odoo.addons.pns_ai_mcp.utils.mcp_logging import (
            known_doors,
            request_log_stamp,
        )
        stamp = request_log_stamp()
        doors = known_doors(env)
    except Exception:
        stamp = {}
        doors = ()
    stamped = ctx.get('mcp_source_channel') or stamp.get('source_channel')
    if stamped in doors:
        origin = stamped
    try:
        from odoo.http import request as http_request
        if http_request:
            if not stamped and getattr(http_request, 'mcp_user_id', None):
                origin = 'mcp_client'
            if hasattr(http_request, 'httprequest'):
                client_ip = http_request.httprequest.remote_addr or ''
            turn_corr = getattr(http_request, 'mcp_turn', None) or None
    except Exception:
        pass
    if not turn_corr:
        turn_corr = ctx.get('mcp_turn') or stamp.get('turn') or None
    return turn_corr, origin, client_ip


def _replace_pending_plan(env, verification_id, steps, title, tool_name,
                          plan_desc, danger, log_origin):
    """Write new steps onto a pending authorisation. Same id.

    A missing or closed row is left alone: the caller creates another.
    """
    vid = str(verification_id or '').strip()
    if not vid:
        return None
    op = env['ai.safe.operation'].sudo().search([
        ('verification_id', '=', vid),
        ('user_id', '=', env.uid),
        ('status', '=', 'pending'),
        ('executed', '=', False),
    ], limit=1)
    if not op:
        return None
    from ..constants import PENDING_OPERATION_TTL_MINUTES

    old = op.get_operation_data() or {}
    operation_data = {
        'plan_steps': steps,
        'title': title,
        'plan': plan_desc,
        'danger_level': danger,
        'log_origin': log_origin or old.get('log_origin') or 'internal',
    }
    for key in ('mcp_agent_code', 'ai_session_ref'):
        if old.get(key):
            operation_data[key] = old[key]
    agent_code = (env.context or {}).get('mcp_agent_code')
    if agent_code:
        operation_data['mcp_agent_code'] = agent_code
    now = fields.Datetime.now()
    op.write({
        'operation_type': _primary_operation_type(steps),
        'model_name': _plan_display_model(steps),
        'records_count': len(steps),
        'changes_info': json.dumps(
            {'plan': plan_desc, 'danger_level': danger}, default=str,
        ),
        'operation_data': json.dumps(operation_data, default=str),
        'danger_level': danger,
        'tool_name': tool_name or op.tool_name,
        'expires_at': now + timedelta(minutes=PENDING_OPERATION_TTL_MINUTES),
    })
    op._notify_safe_plan_hosts()
    return {
        'success': True,
        'verification_id': op.verification_id,
        'plan': plan_desc,
        'danger_level': danger,
        'title': title,
        'user_id': env.uid,
        'replaced_pending': True,
    }


def request_safe_plan(env, steps, title='Supervised operation',
                      tool_name='safe_plan_request', views_locked=False,
                      replace_verification_id=None):
    """Validate + persist a pending ``ai.safe.operation`` (no auto-confirm).

    Used by ``safe_plan_request`` and by skill fast-path CRUD propose_steps.
    Returns a dict with ``success`` True/False; on success includes
    ``verification_id``, ``plan``, ``danger_level``, ``title``.
    ``views_locked`` is only set by the pick-list accept path.
    ``replace_verification_id`` rewrites that pending row when it is still
    this user's and not executed. Same id, new steps.
    """
    ok, err = validate_safe_plan(steps, env)
    if not ok:
        return {'success': False, 'error': err}

    if not views_locked and any(
        isinstance(s, dict) and s.get('op') == 'field_required'
        for s in (steps or [])
    ):
        from ..utils.field_required_plan import create_field_required_choice
        return create_field_required_choice(env, steps, title)

    has_permission, perm_error = check_safe_plan_permissions(
        steps, user=env.user,
    )
    if not has_permission:
        return {
            'success': False,
            'error': perm_error or (
                'Insufficient permissions for safe_plan_request.'
            ),
        }

    ok, policy_error = env['ai.url.whitelist'].check_fetch_url_steps(
        steps, user=env.user,
    )
    if not ok:
        return {'success': False, 'error': policy_error}

    turn_corr, log_origin, client_ip = capture_safe_plan_log_context(env)
    plan_desc = describe_safe_plan(env, steps)
    danger = compute_danger_level(steps, env=env)
    title = title or 'Supervised operation'
    replaced = _replace_pending_plan(
        env, replace_verification_id, steps, title, tool_name,
        plan_desc, danger, log_origin,
    )
    if replaced:
        return replaced

    from ..utils.module_update_heal import steps_fingerprint
    fp = steps_fingerprint(steps)
    now = fields.Datetime.now()
    twins = env['ai.safe.operation'].sudo().search([
        ('user_id', '=', env.uid),
        ('status', '=', 'pending'),
        ('executed', '=', False),
        ('expires_at', '>', now),
    ], order='id desc', limit=15)
    for twin in twins:
        data = twin.get_operation_data() or {}
        if steps_fingerprint(data.get('plan_steps')) != fp:
            continue
        plan_desc = data.get('plan') or describe_safe_plan(env, steps)
        danger = data.get('danger_level') or compute_danger_level(steps, env=env)
        return {
            'success': True,
            'verification_id': twin.verification_id,
            'plan': plan_desc,
            'danger_level': danger,
            'title': data.get('title') or title,
            'user_id': env.uid,
            'reused_pending': True,
        }

    user_id = env.uid

    from ..utils.session_download import resolve_session_ref

    # Own cursor: do not mix the commit with the SSE generator (O14 SERIALIZATION).
    verification_id = None
    nctx = dict(env.context or {})
    if turn_corr:
        nctx['mcp_turn'] = turn_corr
    session_id = resolve_session_ref(env)
    if session_id:
        nctx['ai_session_ref'] = int(session_id)
    with env.registry.cursor() as ncr:
        nenv = api.Environment(ncr, SUPERUSER_ID, nctx)
        first_model = _plan_display_model(steps)
        agent_code = (env.context or {}).get('mcp_agent_code')
        operation_data = {
            'plan_steps': steps, 'title': title,
            'plan': plan_desc, 'danger_level': danger,
            'log_origin': log_origin,
        }
        if agent_code:
            operation_data['mcp_agent_code'] = agent_code
        # Approved later, maybe with the switcher elsewhere: it runs where it was asked.
        from ..utils.one_company import SCREEN_COMPANIES, screen_ids
        screen = screen_ids((env.context or {}).get(SCREEN_COMPANIES))
        if screen:
            operation_data[SCREEN_COMPANIES] = screen
        session_id = resolve_session_ref(env)
        if session_id:
            operation_data['ai_session_ref'] = int(session_id)
        verification = nenv['ai.safe.operation'].create_verification(
            operation_type=_primary_operation_type(steps),
            model_name=first_model,
            records_count=len(steps),
            changes_info={'plan': plan_desc, 'danger_level': danger},
            user_id=user_id,
            tool_name=tool_name,
            operation_data=operation_data,
            request_ip=client_ip,
            turn=turn_corr,
        )
        verification_id = verification.verification_id
        ncr.commit()

    return {
        'success': True,
        'verification_id': verification_id,
        'plan': plan_desc,
        'danger_level': danger,
        'title': title,
        'user_id': user_id,
    }


@mcp_tool(
    name='safe_plan_request',
    description=(
        'Declares a supervised plan in Odoo: create, update, duplicate, '
        'delete, field_required (model + the views the human picks), '
        'READ URLs (fetch_url: GET/HEAD/OPTIONS/QUERY), registered APIs '
        '(api_call) or op=action (closed action_code + args; e.g. '
        'module.update). It does NOT execute: the server shows the Confirm '
        'toast in Odoo and the human clicks it. There is NO PIN and no '
        'confirmation through the chat. Calling this tool IS the proposal; '
        'do not announce the plan in prose. Never write with relaxaicode. '
        'External data: op=fetch_url with the full URL.'
    ),
    is_write=False,
    validate_schema=False,
    input_schema=_PROPOSE_SCHEMA,
    groups=_PLAN_GROUPS,
)
def tool_safe_plan_request(controller, arguments):
    """Create a supervised operation with the declarative plan and notify the human by toast."""
    try:
        steps = arguments.get('steps')
        title = arguments.get('title') or 'Supervised operation'
        if isinstance(steps, str):
            try:
                steps = json.loads(steps)
            except Exception:
                return _text_response({
                    'success': False,
                    'error': "'steps' is not valid JSON.",
                })

        env = controller._get_env_for_operation('read')
        pending = request_safe_plan(env, steps, title=title)
        if not pending.get('success'):
            return _text_response({
                'success': False,
                'error': pending.get('error') or 'safe_plan_request failed',
            })
        if pending.get('status') == 'pending_choice':
            return _text_response(pending)

        verification_id = pending['verification_id']
        plan_desc = pending['plan']
        danger = pending['danger_level']
        user_id = pending['user_id']

        # ── Auto-confirm: trusted read-side plans (no toast) ──
        # NEVER use action_confirm_and_execute here: if the fetch hangs,
        # propose never returns → LLM orchestration stuck (6YR2 / iter tool).
        # Confirm + execute in their own TX with timeouts; if there is no result,
        # we return pending so the LLM goes on (toast/cron finish the job).
        if _all_steps_auto_confirmable(env, steps):
            try:
                exec_result = None
                executed_ok = False
                with env.registry.cursor() as ncr:
                    ncr.execute("SET LOCAL lock_timeout = '5s'")
                    ncr.execute("SET LOCAL statement_timeout = '20s'")
                    nenv = api.Environment(ncr, user_id, dict(env.context or {}))
                    op = nenv['ai.safe.operation'].sudo().search(
                        [('verification_id', '=', verification_id)], limit=1)
                    if op and op.status == 'pending':
                        now = fields.Datetime.now()
                        op.write({
                            'status': 'confirmed',
                            'confirmed_by_uid': user_id,
                            'resolved_at': now,
                        })
                        ncr.commit()
                        results = op.with_user(user_id).execute_plan_now()
                        if results is False:
                            # Another executor; do not block propose.
                            pass
                        elif results is not None:
                            ncr.commit()
                            exec_result = results
                            executed_ok = True
                        else:
                            ncr.commit()
                if executed_ok:
                    _logger.info(
                        "MCP: Auto-confirmed trusted plan %s", verification_id,
                    )
                    presentation = None
                    try:
                        from odoo.addons.pns_ai_mcp.utils.skill_runtime import (
                            try_present,
                        )
                        from odoo.addons.pns_ai_mcp.utils.session_download import (
                            collect_download_chips,
                        )
                        city_names = [
                            s.get('city') or s.get('name') or s.get('label')
                            for s in (steps or [])
                            if isinstance(s, dict) and (
                                s.get('city') or s.get('name') or s.get('label')
                            )
                        ]
                        presentation = try_present(
                            exec_result,
                            steps=steps,
                            meta={'city_names': city_names or None},
                        )
                        if collect_download_chips(exec_result):
                            presentation = None
                    except Exception as fmt_err:
                        _logger.debug(
                            "MCP: skill presenters skipped for %s: %s",
                            verification_id, fmt_err,
                        )
                    if presentation:
                        return _text_response({
                            'success': True,
                            'status': 'confirmed',
                            'verification_id': verification_id,
                            'result': exec_result,
                            'presentation': presentation,
                            'message': (
                                '[DONE] The table is already in the presentation field. '
                                'Do not call tools: the server shows it to the user.'
                            ),
                        })
                    parts = [
                        '[DONE] Show ONLY the results. No explanations.',
                    ]
                    if exec_result:
                        parts.append(json.dumps(
                            exec_result, ensure_ascii=False, default=str,
                        ))
                    return _text_response({
                        'success': True,
                        'status': 'confirmed',
                        'verification_id': verification_id,
                        'result': exec_result,
                        'message': '\n'.join(parts),
                    })
                _logger.warning(
                    "MCP: Auto-confirm %s without a complete execute → toast/cron",
                    verification_id,
                )
            except Exception as auto_err:
                _logger.warning(
                    "MCP: Auto-confirm failed for %s, falling back to toast: %s",
                    verification_id, auto_err,
                )
                # Fall through to pending_confirmation

        return _text_response({
            'success': True,
            'status': 'pending_confirmation',
            'verification_id': verification_id,
            # plan + danger_level: consumed by SSE event → toast rendering
            'plan': plan_desc,
            'danger_level': danger,
            'title': pending.get('title') or title,
            'executed': False,
            # Prescriptive: tell the LLM the ONLY sentence it should say
            'message': (
                '[PENDING] success=true means the confirm toast was created; '
                'the ERP has NOT changed. Tell the user ONLY: '
                '"Confirm in Odoo to continue." Do not say it is done. '
                'Do not call relaxaicode.'
            ),
        })
    except Exception as e:
        _logger.error("MCP: Error in safe_plan_request: %s", e, exc_info=True)
        return _text_response({'success': False, 'error': str(e)})


@mcp_tool(
    name='safe_plan_status',
    description=(
        'Status of a proposed operation: pending/confirmed/executed/cancelled/expired '
        'and, once run, its result. Use it when the user says they ALREADY confirmed in '
        'Odoo. Pass the verification_id if you have it; if not, call it WITHOUT arguments '
        'and it returns your last operation. NEVER propose the operation again: check its '
        'status with this tool.'
    ),
    is_write=False,
    validate_schema=False,
    groups=_PLAN_GROUPS,
    input_schema={
        'type': 'object',
        'properties': {'verification_id': {'type': 'string'}},
        'required': [],
    },
)
def tool_safe_plan_status(controller, arguments):
    """Return the status/result of a supervised operation.

    Robust against models that "forget" the verification_id between turns (the
    cause of talking in circles): with no id, it resolves the user's latest
    operation, preferring a recent confirmed one over a pending one.

    If it is ``confirmed`` and not yet ``executed``, it tries to apply the plan
    here (the toast no longer executes in its own HTTP).
    """
    try:
        verification_id = arguments.get('verification_id')
        env = controller._get_env_for_operation('read')
        Model = env['ai.safe.operation'].sudo()
        # Ids are sequential: a named one is still only the caller's.
        owned = [('user_id', '=', env.uid)]

        if verification_id:
            verif = Model.search(
                [('verification_id', '=', verification_id)] + owned, limit=1)
        else:
            # No id: look for the requester's latest operation (same uid it was
            # created with), within a recent window. Prefer a confirmed one.
            cutoff = fields.Datetime.to_string(
                fields.Datetime.now() - timedelta(hours=2))
            base = owned + [('create_date', '>=', cutoff)]
            verif = Model.search(
                base + [('status', '=', 'confirmed')],
                order='write_date desc', limit=1)
            if not verif:
                verif = Model.search(
                    base + [('status', '=', 'pending')],
                    order='create_date desc', limit=1)
            if not verif:
                verif = Model.search(base, order='create_date desc', limit=1)

        if not verif:
            return _text_response({
                'success': False,
                'error': 'You have no recent operation to check.',
            })
        # The toast only confirms. Retry execute ONLY if it is still confirmed
        # (the toast HTTP did not finish). A failed execute cancels the ticket.
        if verif.status == 'confirmed' and not verif.executed:
            try:
                verif._clear_stale_execute_claims(older_than_seconds=30)
                # The plan writes as the caller: in sudo it would skip ACL and rules.
                applied = env['ai.safe.operation'].browse(verif.id).execute_plan_now()
                verif = Model.browse(verif.id)
                if applied is False:
                    _logger.info(
                        'MCP: safe_plan_status %s execute busy',
                        verif.verification_id,
                    )
            except Exception as apply_exc:
                _logger.warning(
                    'MCP: safe_plan_status apply %s failed: %s',
                    verif.verification_id, apply_exc,
                )
        result = None
        if verif.result_info:
            try:
                result = json.loads(verif.result_info)
            except Exception:
                result = verif.result_info
        presentation = None
        if verif.executed and result:
            try:
                from odoo.addons.pns_ai_mcp.utils.skill_runtime import try_present
                from odoo.addons.pns_ai_mcp.utils.session_download import (
                    collect_download_chips,
                )
                if not collect_download_chips(
                    result if isinstance(result, list) else None
                ):
                    presentation = try_present(result, steps=(
                        result if isinstance(result, list) else None
                    ))
            except Exception:
                presentation = None
        payload = {
            'success': True,
            'verification_id': verif.verification_id,
            'status': verif.status,
            'executed': verif.executed,
            'result': result,
        }
        if presentation:
            payload['presentation'] = presentation
            payload['message'] = (
                '[DONE] Table in presentation. Call no more tools.'
            )
        return _text_response(payload)
    except Exception as e:
        return _text_response({'success': False, 'error': str(e)})


def _text_response(payload):
    """Wrap a dict as an MCP text response (JSON)."""
    return {
        'content': [
            {'type': 'text', 'text': json.dumps(payload, ensure_ascii=False, default=str)}
        ]
    }
