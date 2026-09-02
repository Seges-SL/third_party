# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""PNS AI MCP - Safe Plan (Box B). PATANEGRA Soft (https://patanegra.com).

Part of Patanegra Soft Suite (`pns_suite`), distributed via Patanegra Soft Hub.
Supervised operation declaration of the Patanegra Application Agent Protocol
(PAAP). The AI NEVER executes operations directly: it only DECLARES an intent as
data (a list of steps with closed verbs: create/write/copy/unlink/fetch_url/
api_call). That data is stored as a pending operation, the human is notified by
toast, and ONLY when the human clicks Confirm in Odoo does the server run the
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
Licensed under the Apache License 2.0 - see LICENSE.
"""

import hashlib
import json
import logging
import re
from datetime import timedelta

from odoo import _, api, fields, SUPERUSER_ID
from odoo.exceptions import UserError
from odoo.addons.pns_base.utils.compat import normalize_model_write_values
from odoo.addons.pns_ai_mcp.utils.fetch_url_safe import (
    FETCH_URL_SAFE_METHODS,
    normalize_fetch_url_method,
    validate_fetch_url_step,
)
from .controller_helpers import check_safe_plan_permissions
from .mcp_decorators import mcp_tool

_logger = logging.getLogger(__name__)

# Re-export histórico (docs / imports): fuente canónica = utils.fetch_url_safe.

# Verbos permitidos. El CRUD básico se permite sobre cualquier modelo (las ACL de
# Odoo siguen aplicando al ejecutar como el usuario humano).
# fetch_url: métodos safe http/https. Whitelist + política deciden acceso.
# api_call: tool/operación de un servidor externo registrado (ai.api.server,
# drivers mcp/openapi). 'mcp_call' se acepta como ALIAS legado (skills/prompts
# existentes) y se normaliza estructuralmente a api_call — ver _canonical_op.
# action: solo códigos pre-registrados como registros ai.trusted.action (vocabulario
# cerrado igual que los verbos CRUD — nunca una llamada a método arbitraria). El
# módulo dueño del código (p. ej. pns_acl_manager) declara el registro por datos
# (XML), sin que este módulo importe una sola línea de Python suya.
ALLOWED_OPS = {
    'create', 'write', 'copy', 'unlink', 'fetch_url', 'api_call',
    'action', 'field_required',
}

# Alias legado → verbo canónico (mapeo estructural, no un caso de negocio):
# se mantiene una versión para no romper skills/prompts que aún proponen mcp_call.
OP_ALIASES = {'mcp_call': 'api_call'}

OP_LABEL = {
    'create': 'Crear',
    'write': 'Modificar',
    'copy': 'Duplicar',
    'unlink': 'Borrar',
    'fetch_url': 'Consultar URL',
    'api_call': 'Llamada API externa',
    'action': 'Acción',
    'field_required': 'Campo obligatorio',
}


def _canonical_op(op):
    """Verbo canónico de un paso (resuelve alias legados con aviso en log)."""
    if op in OP_ALIASES:
        _logger.info(
            "MCP: legacy safe-plan op %r normalized to %r", op, OP_ALIASES[op],
        )
        return OP_ALIASES[op]
    return op


def normalize_plan_ops(steps):
    """Normaliza in-place los verbos alias de un plan a su forma canónica."""
    for step in steps or []:
        if isinstance(step, dict) and step.get('op') in OP_ALIASES:
            step['op'] = _canonical_op(step['op'])
    return steps


def _resolve_refs(value, ref_map):
    """Sustituye marcadores "$ref" por el id real creado en un paso anterior.

    Recorre dicts y listas. Un string que empiece por '$' se interpreta como
    referencia al 'ref' de un paso previo (p. ej. "$contacto").
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
    """Valida el plan contra el vocabulario cerrado. Devuelve (ok, error).

    Normaliza los alias legados (mcp_call → api_call) ANTES de validar, de modo
    que el resto del pipeline (danger, describe, execute) solo ve verbos canónicos.
    """
    if not isinstance(steps, list) or not steps:
        return False, "The plan ('steps') must be a non-empty list of operations."
    normalize_plan_ops(steps)
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
                    action.preview(**(step.get('args') or {}))
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
        if op == 'create' and not isinstance(step.get('values'), dict):
            return False, f"Step {i + 1}: 'create' requires 'values' (field object)."
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


def _all_steps_auto_confirmable(env, steps):
    """True when every step can run WITHOUT human confirmation.

    Auto-confirmable steps:
      • fetch_url to a trusted/whitelisted domain (safe methods), or
      • api_call to an active external server explicitly flagged ``trusted``.

    Any CRUD step, untrusted URL or untrusted/unknown API server makes the whole
    plan require a confirmation toast (returns False). Trust for API servers is
    intentionally NOT shared with the URL whitelist: an external server gets
    the call arguments and can invoke arbitrary operations, so it is far more
    delicate than a safe web fetch and must be trusted per-server.
    """
    from urllib.parse import urlparse
    if not steps:
        return False
    Whitelist = env['ai.url.whitelist']
    Server = env['ai.api.server'].sudo()
    for step in steps:
        op = _canonical_op(step.get('op'))
        if op == 'fetch_url':
            hostname = (urlparse(step.get('url', '')).hostname or '').lower()
            if not Whitelist.is_fetch_url_trusted(hostname):
                return False
        elif op == 'api_call':
            srv = Server.search(
                [('code', '=', step.get('server', '')), ('active', '=', True)],
                limit=1)
            if not (srv and srv.trusted):
                return False
        else:
            return False
    return True


# Comandos x2many de Odoo → etiqueta legible. Las operaciones destructivas
# (reemplazar/quitar/vaciar/borrar) llevan ⚠️ para que el humano que confirma las
# vea de un vistazo: el eslabón débil no es la IA, es confirmar sin entender el plan.
_X2M_CMD = {
    0: 'añade nuevo',
    1: 'actualiza',
    2: '⚠️ BORRA',
    3: '⚠️ quita',
    4: 'añade',
    5: '⚠️ VACÍA (quita todos)',
    6: '⚠️ REEMPLAZA todos por',
}


def _names_for(env, comodel, ids):
    """display_name de los ids (best-effort; sudo solo para leer etiquetas)."""
    if not comodel or not ids:
        return ''
    try:
        recs = env[comodel].sudo().browse([i for i in ids if isinstance(i, int)])
        names = [r.display_name for r in recs if r.exists()]
        return ', '.join(n for n in names if n)
    except Exception:
        return ', '.join(str(i) for i in ids)


def _describe_value(env, field_def, value):
    """Traduce el valor de un campo a lenguaje legible. Las tuplas-comando x2many
    se explican y las destructivas se marcan con ⚠️."""
    comodel = getattr(field_def, 'comodel_name', None) if field_def else None
    ftype = getattr(field_def, 'type', None) if field_def else None
    if ftype in ('many2many', 'one2many') and isinstance(value, list):
        parts = []
        for cmd in value:
            if isinstance(cmd, (list, tuple)) and cmd and isinstance(cmd[0], int):
                code = cmd[0]
                label = _X2M_CMD.get(code, 'op %s' % code)
                if code in (2, 3, 4) and len(cmd) >= 2:
                    parts.append('%s «%s»' % (label, _names_for(env, comodel, [cmd[1]]) or cmd[1]))
                elif code == 6 and len(cmd) >= 3:
                    parts.append('%s «%s»' % (label, _names_for(env, comodel, cmd[2]) or cmd[2]))
                elif code == 5:
                    parts.append(label)
                elif code in (0, 1):
                    parts.append('%s %s' % (label, cmd[-1]))
                else:
                    parts.append(label)
            else:
                parts.append(str(cmd))
        return '; '.join(parts)
    if ftype == 'many2one' and isinstance(value, int):
        return '«%s»' % (_names_for(env, comodel, [value]) or value)
    return str(value)


def _describe_values(env, model, values):
    """Resumen legible de un dict de valores (traduce tuplas y resuelve nombres)."""
    if not isinstance(values, dict) or not values:
        return '{}'
    try:
        fields = env[model]._fields
    except Exception:
        fields = {}
    bits = []
    for fname, value in values.items():
        fdef = fields.get(fname)
        label = (getattr(fdef, 'string', None) or fname) if fdef else fname
        bits.append('%s: %s' % (label, _describe_value(env, fdef, value)))
    return '; '.join(bits)


def describe_safe_plan(env, steps):
    """Describe el plan en lenguaje legible para el toast de confirmación.

    Goal: concise and informative — the user decides in 2 seconds.
    Examples:
      🟢 Crear 1 registro en «Contactos»
      🟡 Modificar 2 registros en «Facturas»
      🔴 Borrar 3 registros en «Tareas»
      🔴 Conectarse a example.com (dominio no en lista blanca)
    """
    from urllib.parse import urlparse
    from collections import Counter

    _danger_emoji = {'low': '🟢', 'medium': '🟡', 'high': '🔴'}

    def _model_label(model_name):
        """Friendly model name (translated)."""
        try:
            m = env['ir.model'].sudo().search([('model', '=', model_name)], limit=1)
            if m and m.name:
                return m.name
        except Exception:
            pass
        return model_name

    # Group CRUD steps by (op, model) to aggregate counts
    crud_counts = Counter()  # (op, model) → count
    lines = []

    for step in steps:
        op = _canonical_op(step.get('op'))

        if op == 'fetch_url':
            url = step.get('url', '?')
            hostname = (urlparse(url).hostname or '').lower()
            Whitelist = env['ai.url.whitelist']
            status = Whitelist._fetch_url_access_status(hostname, user=env.user)
            if status == 'allowed':
                lines.append(f"🟢 Conectarse a {hostname}")
            elif status == 'needs_reactivation':
                lines.append(
                    f"🟡 Conectarse a {hostname} "
                    f"(dominio en lista blanca, desactivado — se reactivará al confirmar)"
                )
            elif status == 'open_add':
                lines.append(f"🟢 Conectarse a {hostname}")
            else:
                lines.append(
                    f"🟡 Conectarse a {hostname} "
                    f"(añadir a lista blanca — solo administrador IA)"
                )
            continue

        if op == 'api_call':
            server_code = step.get('server', '?')
            tool_name = step.get('tool', '?')
            srv = env['ai.api.server'].sudo().search(
                [('code', '=', server_code), ('active', '=', True)], limit=1)
            srv_name = srv.name if srv else server_code
            lines.append(f"🟡 Llamar a {srv_name} → {tool_name}")
            continue

        if op == 'action':
            action = env['ai.trusted.action']._get(step.get('action_code'))
            emoji = _danger_emoji.get(action.danger if action else 'high', '🔴')
            # action.label is the raw (English) msgid stored on the owning
            # addon's XML data record — translate it here, now, with the
            # current request's language (same msgid is normally already a
            # translated string elsewhere, e.g. the matching UI button).
            label = _(action.label) if action else step.get('action_code')
            try:
                detail = action.preview(**(step.get('args') or {})) if action else ''
            except Exception as exc:
                detail = f"(vista previa no disponible: {exc})"
            lines.append(f"{emoji} {label}: {detail}" if detail else f"{emoji} {label}")
            continue

        if op == 'field_required':
            Action = env['ai.system.action']
            required = step.get('required', True)
            view_only = step.get('view_only')
            view_ids = step.get('view_ids') or []
            bits = []
            if not view_only:
                try:
                    bits.append(Action.preview_field_set_required(
                        model=step.get('model'), field=step.get('field'),
                        required=required,
                    ))
                except Exception as exc:
                    bits.append(str(exc))
            if view_ids:
                try:
                    bits.append(Action.preview_view_set_field_required(
                        model=step.get('model'), field=step.get('field'),
                        required=required, view_ids=view_ids,
                    ))
                except Exception as exc:
                    bits.append(str(exc))
            elif view_only:
                bits.append(_('No views selected'))
            lines.append('🟡 ' + ('; '.join(bits) if bits else _('Field required')))
            continue

        # CRUD: aggregate by (op, model)
        model = step.get('model') or '?'
        crud_counts[(op, model)] += 1

    # Emit aggregated CRUD lines
    for (op, model), count in crud_counts.items():
        danger = _OP_DANGER.get(op, 'medium')
        emoji = _danger_emoji.get(danger, '🟡')
        label = OP_LABEL.get(op, op)
        ml = _model_label(model)
        if count == 1:
            lines.append(f"{emoji} {label} 1 registro en «{ml}»")
        else:
            lines.append(f"{emoji} {label} {count} registros en «{ml}»")

    return lines


def _select_records(Model, step, ref_map):
    """Selecciona el recordset destino de un write/unlink por ids o por domain."""
    if step.get('ids') is not None:
        ids = _resolve_refs(step['ids'], ref_map)
        if isinstance(ids, int):
            ids = [ids]
        return Model.browse([int(x) for x in ids])
    domain = step.get('domain') or []
    return Model.search(domain)


def _ensure_fetch_url_whitelist(env, step):
    """Add or reactivate whitelist row before fetch_url executes."""
    from urllib.parse import urlparse
    Whitelist = env['ai.url.whitelist']
    hostname = (urlparse(step.get('url', '')).hostname or '').lower()
    if not hostname:
        return
    if Whitelist.is_url_access_open():
        Whitelist.ensure_domain_whitelisted(
            hostname,
            notes='Auto-added on fetch_url (open URL policy)',
        )
        return
    entry = Whitelist._match_whitelist_entry(hostname)
    if entry and not entry.active:
        Whitelist.ensure_domain_whitelisted(
            hostname,
            notes='Reactivated on fetch_url confirm',
        )


def execute_safe_plan(env, steps):
    """Ejecuta el plan (Safe Plan / Caja B) con verbos fijos. Atómico: lo llama el
    endpoint de confirmación dentro de su transacción; si algo falla, el llamador
    hace rollback.

    Se ejecuta con el `env` del usuario HUMANO de la sesión: sus permisos y reglas de
    registro de Odoo siguen aplicando como última capa de seguridad.
    """
    has_permission, perm_error = check_safe_plan_permissions(steps, user=env.user)
    if not has_permission:
        raise PermissionError(perm_error or 'Insufficient permissions to execute safe plan.')

    ok, policy_error = env['ai.url.whitelist'].check_fetch_url_steps(steps, user=env.user)
    if not ok:
        raise PermissionError(policy_error)

    from ..utils.session_download import resolve_chatboo_session_id
    _sid = resolve_chatboo_session_id(env)
    _ctx = dict(env.context or {})
    if _sid:
        _ctx['chatboo_session_id'] = int(_sid)
    labels = _ctx.get('file_label_by_id')
    if not isinstance(labels, dict):
        labels = {}
        _ctx['file_label_by_id'] = labels
    env = env(context=_ctx)

    ref_map = {}
    results = []
    journal_seq = 0
    for step in steps:
        op = _canonical_op(step['op'])
        if op == 'fetch_url':
            _ensure_fetch_url_whitelist(env, step)
            result = _execute_fetch_url(env, step)
            results.append(result)
            continue
        if op == 'api_call':
            result = _execute_api_call(env, step)
            try:
                from ..utils.session_download import file_labels_from_steps
                file_labels_from_steps([result], labels)
            except Exception:
                pass
            results.append(result)
            continue
        if op == 'field_required':
            Action = env['ai.system.action']
            model = step.get('model')
            field = step.get('field')
            required = step.get('required', True)
            view_only = step.get('view_only')
            view_ids = list(step.get('view_ids') or [])
            if step.get('view_id') not in (None, False, ''):
                view_ids.append(int(step['view_id']))
            if view_only and not view_ids:
                raise UserError(_('view_only requires at least one selected view.'))
            row = {'op': 'field_required', 'model': model, 'field': field}
            if not view_only:
                row['orm'] = Action.apply_field_set_required(
                    model=model, field=field, required=required,
                )
            if view_ids:
                row['views'] = Action.apply_view_set_field_required(
                    model=model, field=field, required=required,
                    view_ids=view_ids, uniform=True,
                )
            results.append(row)
            journal_seq += 1
            _record_change_journal(env, step, op, row, None, journal_seq)
            continue
        if op == 'action':
            action = env['ai.trusted.action']._get(step.get('action_code'))
            if not action:
                raise ValueError('Unknown trusted action %r' % step.get('action_code'))
            from ..utils.field_required_plan import is_required_atom
            if is_required_atom(action.code):
                from ..utils.field_required_plan import field_required_hint
                raise UserError(field_required_hint())
            if not action.user_has_required_groups(env.user):
                raise PermissionError(
                    'Missing required group for trusted action %r' % action.code
                )
            args = _resolve_refs(step.get('args') or {}, ref_map)
            result = action.apply(**args)
            row = {'op': 'action', 'action_code': action.code, 'result': result}
            results.append(row)
            journal_seq += 1
            _record_change_journal(env, step, op, row, None, journal_seq)
            continue
        model = step['model']
        blocked = _meta_crud_block_error(model)
        if blocked:
            raise UserError(blocked)
        Model = env[model]
        if op == 'create':
            vals = normalize_model_write_values(
                model, _resolve_refs(step.get('values') or {}, ref_map), env)
            rec = Model.create(vals)
            if step.get('ref'):
                ref_map[step['ref']] = rec.id
            row = {'op': 'create', 'model': model, 'id': rec.id, 'name': rec.display_name}
            results.append(row)
            journal_seq += 1
            _record_change_journal(env, step, op, row, None, journal_seq)
        elif op == 'write':
            vals = normalize_model_write_values(
                model, _resolve_refs(step.get('values') or {}, ref_map), env)
            recs = _select_records(Model, step, ref_map)
            before = _journal_snapshot(env, recs, list(vals.keys()))
            recs.write(vals)
            row = {'op': 'write', 'model': model, 'ids': recs.ids, 'count': len(recs)}
            results.append(row)
            journal_seq += 1
            _record_change_journal(env, step, op, row, before, journal_seq)
        elif op == 'copy':
            rid = int(_resolve_refs(step.get('id'), ref_map))
            overrides = _resolve_refs(step.get('overrides') or {}, ref_map)
            new = Model.browse(rid).copy(overrides)
            if step.get('ref'):
                ref_map[step['ref']] = new.id
            row = {'op': 'copy', 'model': model, 'source_id': rid,
                   'new_id': new.id, 'name': new.display_name}
            results.append(row)
            journal_seq += 1
            _record_change_journal(env, step, op, row, None, journal_seq)
        elif op == 'unlink':
            recs = _select_records(Model, step, ref_map)
            ids = recs.ids
            before = _journal_snapshot(env, recs, None)
            recs.unlink()
            row = {'op': 'unlink', 'model': model, 'ids': ids, 'count': len(ids)}
            results.append(row)
            journal_seq += 1
            _record_change_journal(env, step, op, row, before, journal_seq)
    from ..utils.session_download import (
        resolve_chatboo_session_id,
        collect_download_chips,
        merge_download_chips_into_session,
    )
    session_id = resolve_chatboo_session_id(env)
    if session_id:
        chips = collect_download_chips(results)
        if chips:
            merge_download_chips_into_session(env, session_id, chips)
    return results


def _journal_snapshot(env, recs, field_names):
    """Best-effort before snapshot; never blocks the plan if the model is missing."""
    if 'ai.change.journal' not in env or not recs:
        return None
    return env['ai.change.journal'].sudo().snapshot_records(recs, field_names=field_names)


def _record_change_journal(env, step, op, result, before_records, step_seq):
    """Permanent journal row in the same transaction as the mutation."""
    if 'ai.change.journal' not in env:
        return
    env['ai.change.journal'].sudo().record_executed_step(
        env, step, op, result, before_records, step_seq,
    )


_CRUD_OPS = frozenset({'create', 'write', 'copy', 'unlink', 'field_required'})


def _plan_has_crud(results=None, steps=None):
    """True when the plan/results include Odoo writes (not only fetch_url/mcp)."""
    for item in results or []:
        if isinstance(item, dict) and item.get('op') in _CRUD_OPS:
            return True
    for step in steps or []:
        if isinstance(step, dict) and step.get('op') in _CRUD_OPS:
            return True
    return False


def _needs_llm_followup(results=None, steps=None, action='confirm'):
    """LLM follow-up for fetch_url / api_call bodies; writes use local chat ack."""
    if action == 'cancel':
        return False
    for item in results or []:
        if isinstance(item, dict) and item.get('op') in ('fetch_url', 'api_call', 'mcp_call'):
            return True
    if not results:
        for step in steps or []:
            if isinstance(step, dict) and step.get('op') in ('fetch_url', 'api_call', 'mcp_call'):
                return True
    return False


def build_user_ack_message(title, results=None, action='confirm', error=None,
                           steps=None):
    """Visible Chatboo note after Confirm/Cancel — CRUD writes only.

    Deterministic (no LLM). Returns None for pure fetch_url / api_call plans.
    """
    from odoo import _

    title = title or _('supervised operation')
    if not _plan_has_crud(results=results, steps=steps):
        return None

    if action == 'cancel':
        return _(
            'Alright — I cancelled «%s». No changes were applied.'
        ) % title

    if error:
        return _(
            'The operation «%s» was confirmed but failed: %s'
        ) % (title, error)

    # Only after execute (with result rows). Confirm-without-execute must not
    # claim success; callers may set user_ack_message explicitly for "applying…".
    if not results:
        return None

    lines = [
        _('Done. The write operation «%s» completed successfully.') % title,
    ]
    for item in results:
        if not isinstance(item, dict):
            continue
        op = item.get('op')
        if op == 'create':
            lines.append(
                '- ' + _('Created: %s (%s #%s)') % (
                    item.get('name') or '—',
                    item.get('model') or '?',
                    item.get('id') or '?',
                )
            )
        elif op == 'write':
            lines.append(
                '- ' + _('Updated %s record(s) on %s') % (
                    item.get('count') or len(item.get('ids') or []),
                    item.get('model') or '?',
                )
            )
        elif op == 'copy':
            lines.append(
                '- ' + _('Copied: %s (%s #%s)') % (
                    item.get('name') or '—',
                    item.get('model') or '?',
                    item.get('new_id') or '?',
                )
            )
        elif op == 'unlink':
            lines.append(
                '- ' + _('Deleted %s record(s) on %s') % (
                    item.get('count') or len(item.get('ids') or []),
                    item.get('model') or '?',
                )
            )
        elif op == 'field_required':
            lines.append(
                '- ' + _('Field required on %s.%s') % (
                    item.get('model') or '?',
                    item.get('field') or '?',
                )
            )
    return '\n'.join(lines)


def _ack_field_lookup(env):
    def lookup(model, fname):
        if env is None or not model or model not in env:
            return None
        field = env[model]._fields.get(fname)
        if field is None:
            return None
        return (field.type, getattr(field, 'comodel_name', None) or None)
    return lookup


def _ack_name_of(env):
    def name_of(model, rid):
        if env is None or not model or model not in env or not rid:
            return None
        rec = env[model].browse(rid)
        if rec.exists():
            return rec.display_name
        return None
    return name_of


def attach_verification_chat_hints(payload, title, results=None, action='confirm',
                                   error=None, steps=None, env=None, lookup=None):
    """Add user_ack_message / needs_llm_followup / records to a verification payload."""
    from ..utils.verification_ack_records import attach_ack_records

    out = dict(payload or {})
    if not out.get('user_ack_message'):
        ack = build_user_ack_message(
            title, results=results, action=action, error=error, steps=steps,
        )
        if ack:
            out['user_ack_message'] = ack
    # Drop explicit None placeholders from callers.
    if out.get('user_ack_message') is None:
        out.pop('user_ack_message', None)
    out['needs_llm_followup'] = _needs_llm_followup(
        results=results, steps=steps, action=action,
    )
    if action == 'confirm' and not error and results:
        field_lookup = lookup if lookup is not None else _ack_field_lookup(env)
        out = attach_ack_records(
            out, results, steps=steps, lookup=field_lookup,
            name_of=_ack_name_of(env) if env is not None else None,
            env=env,
        )
    return out


def build_verification_followup_message(title, results=None, action='confirm', error=None):
    """Hidden user turn for the LLM after manual Safe Plan confirm/cancel.

    For fetch_url plans embeds the HTTP body so the model can format tables
    without calling tools again (avoids blind re-propose / relaxaicode).
    """
    guard = (
        ' IMPORTANTE: este es solo un aviso de resultado, NO una petición de escritura. '
        'NO propongas ni vuelvas a llamar propose_safe_operations. '
        'NO uses relaxaicode sobre ai.safe.operation: los datos ya están aquí.'
    )
    title = title or 'Operación supervisada'
    if action == 'cancel':
        return (
            f'[Resultado del sistema] El usuario ha CANCELADO «{title}». '
            f'No se ejecutó ningún cambio. Confírmalo brevemente en su idioma.'
            + guard
        )
    if error:
        return (
            f'[Resultado del sistema] El usuario confirmó «{title}» pero FALLÓ: {error}. '
            f'Explícalo brevemente en su idioma.'
            + guard
        )
    results = results or []
    fetch_items = [
        r for r in results
        if isinstance(r, dict) and r.get('op') == 'fetch_url'
    ]
    api_items = [
        r for r in results
        if isinstance(r, dict) and r.get('op') in ('api_call', 'mcp_call')
    ]
    crud_items = [
        r for r in results
        if isinstance(r, dict)
        and r.get('op') not in ('fetch_url', 'api_call', 'mcp_call')
    ]
    if fetch_items and not crud_items and not api_items:
        payloads = []
        for item in fetch_items:
            if item.get('success'):
                payloads.append(json.dumps({
                    'url': item.get('url'),
                    'status_code': item.get('status_code'),
                    'content_type': item.get('content_type'),
                    'body': item.get('body') or '',
                    'truncated': item.get('truncated', False),
                }, ensure_ascii=False))
            else:
                payloads.append(json.dumps(item, ensure_ascii=False, default=str))
        data_block = '\n'.join(payloads)
        return (
            f'[Resultado del sistema] El usuario CONFIRMÓ fetch_url «{title}». '
            f'Los datos HTTP están en el JSON siguiente (campo body). '
            f'Analiza ese JSON/texto y responde al usuario con tabla o resumen legible; '
            f'cita la URL como fuente y NO inventes cifras. '
            f'NO llames herramientas: usa SOLO los datos embebidos.\n'
            f'DATOS:\n{data_block}'
            + guard
        )
    if api_items and not crud_items:
        payloads = []
        for item in api_items:
            if item.get('success'):
                payloads.append(json.dumps({
                    'server': item.get('server'),
                    'tool': item.get('tool'),
                    'body': item.get('body') or '',
                    'truncated': item.get('truncated', False),
                    'pagination': item.get('pagination'),
                    'cache_key': item.get('cache_key'),
                }, ensure_ascii=False))
            else:
                payloads.append(json.dumps(item, ensure_ascii=False, default=str))
        data_block = '\n'.join(payloads)
        return (
            f'[Resultado del sistema] El usuario CONFIRMÓ api_call «{title}». '
            f'Los datos de la API externa están en el JSON siguiente (campo body). '
            f'Si truncated=true, usa pagination.suggested_arguments para la siguiente '
            f'página con propose_safe_operations (op=api_call). '
            f'Analiza el JSON y responde con tabla o resumen legible; '
            f'NO inventes cifras. NO llames herramientas salvo paginar.\n'
            f'DATOS:\n{data_block}'
            + guard
        )
    det = json.dumps(results, ensure_ascii=False, default=str)
    return (
        f'[Resultado del sistema] El usuario CONFIRMÓ «{title}» y se ejecutó correctamente.'
        + (f' Resultado: {det}.' if det else ' ')
        + ' Informa del éxito en su idioma, mencionando lo creado o modificado.'
        + guard
    )


# ── fetch_url: safe methods; whitelist + policy gate access ───────────────

def _cache_ttl_from_headers(headers, max_ttl=604800):
    """Derive a cache TTL (seconds) from standard HTTP response headers.

    The ORIGIN decides — exactly like browsers, CDNs and proxies. We never
    invent a TTL: an immutable geocoding API advertises a long ``max-age`` and
    gets cached; a live weather API sends ``no-cache`` / ``max-age=0`` and is
    never cached. No per-domain configuration to maintain.

    Rules (RFC 7234, simplified):
        - ``Cache-Control: no-store | no-cache | private`` → 0 (never cache).
        - ``Cache-Control: s-maxage=N`` (preferred) or ``max-age=N`` → N.
        - else ``Expires`` header → seconds until that instant.
        - else → 0 (no explicit permission = don't cache).
    Result is clamped to ``[0, max_ttl]`` so a bogus huge max-age can't pin a
    stale entry for months.
    """
    try:
        cc = (headers.get('Cache-Control') or '').lower()
        if 'no-store' in cc or 'no-cache' in cc or 'private' in cc:
            return 0
        m = re.search(r's-maxage\s*=\s*(\d+)', cc) or re.search(r'max-age\s*=\s*(\d+)', cc)
        if m:
            return max(0, min(int(m.group(1)), max_ttl))
        exp = headers.get('Expires')
        if exp:
            from email.utils import parsedate_to_datetime
            import datetime as _dt
            dt = parsedate_to_datetime(exp)
            if dt is not None:
                now = _dt.datetime.now(dt.tzinfo) if dt.tzinfo else _dt.datetime.utcnow()
                return max(0, min(int((dt - now).total_seconds()), max_ttl))
        return 0
    except Exception:
        return 0


def _label_fetch_url_result(result, step):
    """Copia city/name/label del step al resultado (también tras hit de caché)."""
    if not isinstance(result, dict) or not isinstance(step, dict):
        return result
    out = dict(result)
    for _k in ('city', 'name', 'label'):
        if step.get(_k):
            out[_k] = step.get(_k)
            break
    return out


def _binary_fetch_url_result(env, url, resp, step):
    """Store binary fetch_url bodies on the Chatboo session when available."""
    import json as _json
    from ..utils.session_download import (
        resolve_chatboo_session_id,
        filename_from_http,
        persist_chatboo_session_file_detail,
        build_binary_stored_meta,
        PERSIST_REASON_NO_BYTES,
        is_binary_content_type,
        mimetype_from_magic_bytes,
    )

    content_type = resp.headers.get('Content-Type', '')
    content_disposition = resp.headers.get('Content-Disposition', '')
    raw = resp.content or b''
    if not is_binary_content_type(content_type, content_disposition):
        inferred = mimetype_from_magic_bytes(raw)
        if inferred:
            content_type = inferred
    filename = filename_from_http(url, content_type, content_disposition)
    session_id = resolve_chatboo_session_id(env)
    persist_detail = (
        persist_chatboo_session_file_detail(
            env, session_id, raw, filename, content_type,
        )
        if raw else {'ok': False, 'reason': PERSIST_REASON_NO_BYTES}
    )
    chip = persist_detail.get('chip') if persist_detail.get('ok') else None
    stored_meta = build_binary_stored_meta(persist_detail, filename, len(raw))
    result = {
        'op': 'fetch_url',
        'url': url,
        'success': True,
        'status_code': resp.status_code,
        'content_type': content_type,
        'body': _json.dumps(stored_meta, ensure_ascii=False),
        'binary': True,
    }
    if chip:
        result['download_chip'] = chip
    return _label_fetch_url_result(result, step)


def _binary_api_call_result(env, server_code, tool_name, raw_response, url='',
                            arguments=None):
    """Store binary api_call bodies on the Chatboo session when available."""
    import json as _json
    from ..utils.session_download import (
        resolve_chatboo_session_id,
        filename_from_http,
        persist_chatboo_session_file_detail,
        build_binary_stored_meta,
        preferred_download_filename,
        PERSIST_REASON_NO_BYTES,
    )

    content_type = raw_response.get('content_type') or ''
    content_disposition = raw_response.get('content_disposition') or ''
    raw = raw_response.get('content') or b''
    labels = (env.context or {}).get('file_label_by_id')
    filename = preferred_download_filename(
        raw_response.get('filename')
        or filename_from_http(
            url or '%s/%s' % (server_code, tool_name),
            content_type,
            content_disposition,
        ),
        arguments=arguments,
        labels=labels if isinstance(labels, dict) else None,
    )
    session_id = resolve_chatboo_session_id(env)
    persist_detail = (
        persist_chatboo_session_file_detail(
            env, session_id, raw, filename, content_type,
        )
        if raw else {'ok': False, 'reason': PERSIST_REASON_NO_BYTES}
    )
    chip = persist_detail.get('chip') if persist_detail.get('ok') else None
    stored_meta = build_binary_stored_meta(persist_detail, filename, len(raw))
    result = {
        'op': 'api_call',
        'server': server_code,
        'tool': tool_name,
        'success': True,
        'body': _json.dumps(stored_meta, ensure_ascii=False),
        'binary': True,
    }
    if chip:
        result['download_chip'] = chip
    return result


def _fetch_cache_key(url, method, body):
    """Cache key: the exact URL, extended with the body hash for QUERY.

    RFC 10008 guidance: a QUERY response is cacheable and its cache key MUST
    include the request content — same URL with a different query body is a
    different resource representation.
    """
    if method == 'QUERY' and body:
        digest = hashlib.sha256(body.encode('utf-8')).hexdigest()
        return '%s#query-sha256=%s' % (url, digest)
    return url


def _headers_summary_for_llm(resp_headers):
    """Compact header dump for HEAD/OPTIONS (no response body by design)."""
    prefer = (
        'allow', 'content-type', 'content-length', 'content-disposition',
        'cache-control', 'expires', 'etag', 'last-modified', 'location',
        'server', 'www-authenticate', 'access-control-allow-origin',
        'access-control-allow-methods', 'access-control-allow-headers',
    )
    out = {}
    lower_map = {k.lower(): (k, v) for k, v in (resp_headers or {}).items()}
    for key in prefer:
        if key in lower_map:
            orig, val = lower_map[key]
            out[orig] = val
    if not out:
        # Fallback: first headers only (avoid dumping huge sets).
        for i, (k, v) in enumerate((resp_headers or {}).items()):
            if i >= 20:
                break
            out[k] = v
    return out


def _execute_fetch_url(env, step):
    """Execute a fetch_url step with a safe HTTP method to an allowed domain.

    Allowed: GET, HEAD, OPTIONS, QUERY (RFC 10008). QUERY carries the query in
    the request body (mandatory Content-Type). Access was validated at
    propose/confirm time (user permission + whitelist policy). Under open
    policy the domain is added to the global whitelist before the request
    (see ``_ensure_fetch_url_whitelist``).
    """
    import requests as _requests
    url = step['url']
    method = normalize_fetch_url_method(step.get('method'))
    if method not in FETCH_URL_SAFE_METHODS:
        # Defensa en profundidad: propose ya valida; no salir a la red.
        return {
            'success': False,
            'op': 'fetch_url',
            'url': url,
            'error': (
                "fetch_url solo permite métodos safe "
                "(GET, HEAD, OPTIONS, QUERY); recibido: %r" % method
            ),
        }
    body = step.get('body') if method == 'QUERY' else None

    # Caché de INMUTABLES dirigida por el ORIGEN (cabeceras HTTP), no por config
    # manual: si hay una entrada fresca para esta clave exacta la servimos sin
    # salir a la red (para QUERY la clave incluye el hash del body). El TTL lo
    # decide el servidor con Cache-Control/Expires (igual que navegadores/CDN);
    # si no autoriza caché, no se guarda. Ver _cache_ttl_from_headers.
    cache_key = _fetch_cache_key(url, method, body)
    try:
        cached = env['ai.fetch.cache'].get_cached(cache_key)
        if cached is not None:
            # La etiqueta (ciudad) vive en el step, no en la caché HTTP.
            cached['url'] = url
            return _label_fetch_url_result(cached, step)
    except Exception:
        pass

    try:
        headers = {'User-Agent': 'PNS-AI-SafePlan/1.0'}
        request_kwargs = {}
        if method == 'QUERY':
            # RFC 10008: el Content-Type del body es obligatorio (validado al
            # proponer); sin él la petición debe fallar en el servidor.
            headers['Content-Type'] = step.get('content_type') or 'application/json'
            request_kwargs['data'] = (body or '').encode('utf-8')
        # (connect, read): un DNS/TLS colgado no debe bloquear propose/orquestación.
        resp = _requests.request(
            method,
            url,
            timeout=(3, 12),
            allow_redirects=True,
            headers=headers,
            **request_kwargs,
        )

        content_type = resp.headers.get('Content-Type', '')
        content_disposition = resp.headers.get('Content-Disposition', '')
        raw = resp.content or b''

        # HEAD/OPTIONS: no useful body; return selected response headers.
        if method in ('HEAD', 'OPTIONS'):
            hdrs = _headers_summary_for_llm(resp.headers)
            result = {
                'op': 'fetch_url',
                'url': url,
                'method': method,
                'success': True,
                'status_code': resp.status_code,
                'content_type': content_type,
                'headers': hdrs,
                'body': json.dumps(hdrs, ensure_ascii=False),
                'truncated': False,
            }
            result = _label_fetch_url_result(result, step)
            if resp.status_code == 200:
                ttl = _cache_ttl_from_headers(resp.headers)
                if ttl > 0:
                    cache_payload = {
                        k: v for k, v in result.items()
                        if k not in ('city', 'name', 'label')
                    }
                    env['ai.fetch.cache'].store(cache_key, cache_payload, ttl)
            return result

        from ..utils.session_download import (
            is_binary_content_type,
            looks_like_binary_bytes,
        )
        if (
            is_binary_content_type(content_type, content_disposition)
            or looks_like_binary_bytes(raw)
        ):
            return _binary_fetch_url_result(env, url, resp, step)

        body_raw = resp.text[:10240] if resp.text else ''

        # SPA detection: if HTML, strip tags and check visible text length
        is_html = 'text/html' in content_type
        if is_html and resp.status_code == 200:
            # Remove <script>, <style>, <head> blocks, then all tags
            stripped = re.sub(r'<(script|style|head)[^>]*>.*?</\1>', '', body_raw,
                              flags=re.DOTALL | re.IGNORECASE)
            stripped = re.sub(r'<[^>]+>', ' ', stripped)
            stripped = re.sub(r'\s+', ' ', stripped).strip()
            if len(stripped) < 200:
                return {
                    'op': 'fetch_url',
                    'url': url,
                    'success': False,
                    'status_code': resp.status_code,
                    'error': (
                        'SPA detected: the page is rendered by JavaScript and '
                        'contains almost no readable text in the raw HTML. '
                        'Try a JSON API endpoint instead.'
                    ),
                    'visible_text_length': len(stripped),
                }

        result = {
            'op': 'fetch_url',
            'url': url,
            'success': True,
            'status_code': resp.status_code,
            'content_type': content_type,
            'body': body_raw,
            'truncated': len(resp.text) > 10240 if resp.text else False,
        }
        result = _label_fetch_url_result(result, step)
        # Cacheamos SOLO el payload HTTP (sin etiqueta de step): la ciudad se
        # reinyecta en cada hit. Así un fetch sin name no «quema» el título.
        if resp.status_code == 200:
            ttl = _cache_ttl_from_headers(resp.headers)
            if ttl > 0:
                cache_payload = {
                    k: v for k, v in result.items()
                    if k not in ('city', 'name', 'label')
                }
                env['ai.fetch.cache'].store(cache_key, cache_payload, ttl)
        return result
    except _requests.RequestException as e:
        return {
            'op': 'fetch_url',
            'url': url,
            'success': False,
            'error': str(e),
        }


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


def _execute_api_call(env, step):
    """Execute an api_call step on a configured external API server.

    The server must be registered in ai.api.server and active; its
    ``api_type`` selects the protocol driver (mcp / openapi). The outbound
    credential is resolved per user: the caller's ai.api.server.key if any,
    else the server's default auth token.

    Full responses are cached server-side (``ai.api.result.cache``). The LLM
    channel receives a JSON-aware preview plus pagination hints when needed.
    """
    from ..lib.api.drivers import APIDriverError, get_api_driver
    from ..utils.api_call_result import (
        API_CALL_CACHE_TTL_SECONDS,
        cache_key_for_api_call,
        format_api_call_body_for_llm,
    )

    server_code = step.get('server', '')
    tool_name = step.get('tool', '')
    arguments = step.get('arguments') or {}
    if not isinstance(arguments, dict):
        arguments = {}

    # Find the server record
    srv = env['ai.api.server'].sudo().search(
        [('code', '=', server_code), ('active', '=', True)], limit=1)
    if not srv:
        return {
            'op': 'api_call',
            'server': server_code,
            'tool': tool_name,
            'success': False,
            'error': f"External API server '{server_code}' not found or inactive.",
        }

    schema_error = _api_call_schema_error(srv, tool_name, arguments)
    if schema_error:
        return {
            'op': 'api_call',
            'server': server_code,
            'tool': tool_name,
            'success': False,
            'error': schema_error,
        }

    cache_key = cache_key_for_api_call(server_code, tool_name, arguments)
    Cache = env['ai.api.result.cache']

    try:
        cached_body = Cache.get_cached(server_code, tool_name, arguments)
        if cached_body is not None:
            body = cached_body
            from_cache = True
        else:
            driver = get_api_driver(srv.api_type)
            auth_token = srv._resolve_auth_token(env.user)
            body = driver.call(srv, tool_name, arguments, auth_token=auth_token)
            from_cache = False
            if isinstance(body, dict) and body.get('_binary'):
                return _binary_api_call_result(
                    env, server_code, tool_name, body,
                    url=body.get('url') or '',
                    arguments=arguments,
                )
            if isinstance(body, str) and body.strip():
                from ..utils.session_download import try_extract_binary_payload
                extracted = try_extract_binary_payload(
                    body,
                    tool_name=tool_name,
                    server_code=server_code,
                    arguments=arguments,
                )
                if extracted:
                    return _binary_api_call_result(
                        env, server_code, tool_name, {
                            '_binary': True,
                            'content': extracted['content'],
                            'content_type': extracted['content_type'],
                            'content_disposition': extracted['content_disposition'],
                            'filename': extracted.get('filename'),
                            'url': extracted.get('url') or '',
                        },
                        url=extracted.get('url') or '',
                        arguments=arguments,
                    )
    except (APIDriverError, ValueError) as e:
        return {
            'op': 'api_call',
            'server': server_code,
            'tool': tool_name,
            'success': False,
            'error': str(e),
        }
    except Exception as e:
        return {
            'op': 'api_call',
            'server': server_code,
            'tool': tool_name,
            'success': False,
            'error': f"Unexpected error: {e}",
        }

    body = body or ''
    if not from_cache:
        try:
            Cache.store(
                server_code, tool_name, arguments, body,
                ttl_seconds=API_CALL_CACHE_TTL_SECONDS,
            )
        except Exception:
            pass

    llm_body, truncated, pagination = format_api_call_body_for_llm(body, arguments)

    result = {
        'op': 'api_call',
        'server': server_code,
        'tool': tool_name,
        'success': True,
        'body': llm_body,
        'truncated': truncated,
        'cache_key': cache_key,
        '_from_cache': from_cache,
    }
    if pagination:
        result['pagination'] = pagination
    return result


def _primary_operation_type(steps):
    """Tipo de operación principal para la verificación (prioriza borrado/creación)."""
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
                "Lista de operaciones declarativas (NO código). Cada una: "
                "{op, ...}. op='create' -> {model, values{}, ref?}; "
                "op='write' -> {model, ids[] o domain[], values{}}; "
                "op='copy' -> {model, id, overrides{}?, ref?}; "
                "op='unlink' -> {model, ids[] o domain[]}; "
                "op='field_required' -> {model, field, required} "
                "(optional view_id/action_id; view_only=true skips the ORM). "
                "Chatboo lists views; the human picks them before Confirm. "
                "NEVER op=action view.set_field_required or field.set_required. "
                "op='action' -> {action_code, args{}} (códigos cerrados "
                "ai.trusted.action). Ejemplos: module.update con args "
                "{module, operation} operation=install|upgrade|uninstall "
                "(NUNCA module_ids ni button); "
                "view.set_field_readonly|invisible|domain con args "
                "{model, field, view_ids[] o view_id}; "
                "view.reset_field_modifiers; user.add_group / "
                "user.remove_group con args {user_id, group}. "
                "NUNCA write/create/unlink de ir.ui.view ni ir.model.fields. "
                "op='fetch_url' -> {url, method?} (safe methods: GET default, "
                "HEAD, OPTIONS, or QUERY with body+content_type — RFC 10008; "
                "si el dominio está en la whitelist se confirma rápido 🟢, "
                "si no está se pide confirmación extra 🔴); "
                "op='api_call' -> {server, tool, arguments{}} (tool de un "
                "servidor API externo registrado: MCP u OpenAPI). "
                "Usa fetch_url para lectura web ad hoc. Mutaciones HTTP "
                "(POST/…) o APIs no registradas: no van en fetch_url. "
                "Para encadenar pasos usa 'ref' en un paso y '$ref' como valor en otro "
                "(p. ej. ref='contacto' y luego \"partner_id\": \"$contacto\")."
            ),
            'items': {'type': 'object'},
        },
        'title': {
            'type': 'string',
            'description': 'Título corto y legible de la operación (para el aviso al humano).',
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
    try:
        from odoo.http import request as http_request
        if http_request:
            if getattr(http_request, 'mcp_user_id', None):
                origin = 'mcp_client'
            if getattr(http_request, 'chatboo_options', None):
                origin = 'chatboo'
            if hasattr(http_request, 'httprequest'):
                client_ip = http_request.httprequest.remote_addr or ''
            turn_corr = getattr(http_request, 'mcp_corr_id', None) or None
    except Exception:
        pass
    if not turn_corr:
        turn_corr = (env.context or {}).get('mcp_correlation_id') or None
    if origin == 'internal' and turn_corr and (env.context or {}).get(
        'mcp_correlation_id'
    ):
        origin = 'chatboo'
    return turn_corr, origin, client_ip


def create_pending_safe_operation(env, steps, title='Operación supervisada',
                                  tool_name='propose_safe_operations',
                                  views_locked=False):
    """Validate + persist a pending ``ai.safe.operation`` (no auto-confirm).

    Used by ``propose_safe_operations`` and by skill fast-path CRUD propose_steps.
    Returns a dict with ``success`` True/False; on success includes
    ``verification_id``, ``plan``, ``danger_level``, ``title``.
    ``views_locked`` is only set by the Chatboo choice accept path.
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
                'Insufficient permissions for propose_safe_operations.'
            ),
        }

    ok, policy_error = env['ai.url.whitelist'].check_fetch_url_steps(
        steps, user=env.user,
    )
    if not ok:
        return {'success': False, 'error': policy_error}

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
    plan_desc = describe_safe_plan(env, steps)
    danger = compute_danger_level(steps, env=env)
    title = title or 'Operación supervisada'

    turn_corr, log_origin, client_ip = capture_safe_plan_log_context(env)

    from ..utils.session_download import resolve_chatboo_session_id

    # Cursor propio: no mezclar commit con el generador SSE (O14 SERIALIZATION).
    verification_id = None
    nctx = dict(env.context or {})
    if turn_corr:
        nctx['mcp_correlation_id'] = turn_corr
    session_id = resolve_chatboo_session_id(env)
    if session_id:
        nctx['chatboo_session_id'] = int(session_id)
    with env.registry.cursor() as ncr:
        nenv = api.Environment(ncr, SUPERUSER_ID, nctx)
        first_model = _plan_display_model(steps)
        operation_data = {
            'plan_steps': steps, 'title': title,
            'plan': plan_desc, 'danger_level': danger,
            'log_origin': log_origin,
        }
        session_id = resolve_chatboo_session_id(env)
        if session_id:
            operation_data['chatboo_session_id'] = int(session_id)
        verification = nenv['ai.safe.operation'].create_verification(
            operation_type=_primary_operation_type(steps),
            model_name=first_model,
            records_count=len(steps),
            changes_info={'plan': plan_desc, 'danger_level': danger},
            user_id=user_id,
            tool_name=tool_name,
            operation_data=operation_data,
            request_ip=client_ip,
            correlation_id=turn_corr,
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
    name='propose_safe_operations',
    description=(
        'Declara un plan supervisado en Odoo: crear, modificar, duplicar, '
        'borrar, field_required (modelo + vistas que el humano elige), '
        'CONSULTAR URLs (fetch_url: GET/HEAD/OPTIONS/QUERY), APIs '
        'registradas (api_call) u op=action (action_code cerrado + args; '
        'p. ej. module.update). NO ejecuta: el servidor muestra el toast '
        'Confirmar en Odoo y el humano pulsa. NO hay PIN ni confirmación por '
        'chat. Llamar esta tool ES la propuesta; no anuncies el plan en prosa. '
        'Escrituras nunca con relaxaicode. Datos externos: op=fetch_url con URL '
        'completa.'
    ),
    is_write=False,
    validate_schema=False,
    input_schema=_PROPOSE_SCHEMA,
)
def tool_propose_safe_operations(controller, arguments):
    """Crea una operación supervisada con el plan declarativo y avisa al humano por toast."""
    try:
        steps = arguments.get('steps')
        title = arguments.get('title') or 'Operación supervisada'
        if isinstance(steps, str):
            try:
                steps = json.loads(steps)
            except Exception:
                return _text_response({
                    'success': False,
                    'error': "El parámetro 'steps' no es JSON válido.",
                })

        env = controller._get_env_for_operation('read')
        pending = create_pending_safe_operation(env, steps, title=title)
        if not pending.get('success'):
            return _text_response({
                'success': False,
                'error': pending.get('error') or 'propose_safe_operations failed',
            })
        if pending.get('status') == 'pending_choice':
            return _text_response(pending)

        verification_id = pending['verification_id']
        plan_desc = pending['plan']
        danger = pending['danger_level']
        user_id = pending['user_id']

        # ── Auto-confirm: trusted read-side plans (no toast) ──
        # NUNCA usar action_confirm_and_execute aquí: si el fetch se cuelga,
        # propose no vuelve → orquestación LLM atascada (6YR2 / iter tool).
        # Confirm + execute en TX propia con timeouts; si no hay resultado,
        # devolvemos pending para que el LLM continúe (toast/cron terminan).
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
                            # Otro ejecutor; no bloquear propose.
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
                                '[DONE] La tabla ya está en el campo presentation. '
                                'NO llames tools: el servidor la mostrará al usuario.'
                            ),
                        })
                    parts = [
                        '[DONE] Presenta SOLO los resultados. Sin explicaciones.',
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
                    "MCP: Auto-confirm %s sin execute completo → toast/cron",
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
        _logger.error("MCP: Error en propose_safe_operations: %s", e, exc_info=True)
        return _text_response({'success': False, 'error': str(e)})


@mcp_tool(
    name='get_safe_operation_status',
    description=(
        'Consulta el estado de una operación propuesta: pending/confirmed/cancelled/expired '
        'y, si se ejecutó, el resultado. Úsalo cuando el usuario diga que YA ha confirmado en '
        'Odoo. Pasa el verification_id si lo tienes; si no lo recuerdas, llámalo SIN argumentos '
        'y te devuelve tu última operación. NUNCA vuelvas a proponer la operación: comprueba su '
        'estado con esta tool.'
    ),
    is_write=False,
    validate_schema=False,
    input_schema={
        'type': 'object',
        'properties': {'verification_id': {'type': 'string'}},
        'required': [],
    },
)
def tool_get_safe_operation_status(controller, arguments):
    """Devuelve el estado/resultado de una operación supervisada.

    Robusto frente a modelos que "olvidan" el verification_id entre turnos (causa
    del diálogo de besugos): si no se pasa id, resuelve la última operación del
    usuario, priorizando una confirmada reciente sobre una pendiente.

    Si está ``confirmed`` y aún no ``executed``, intenta aplicar el plan aquí
    (el toast ya no ejecuta en su HTTP).
    """
    try:
        verification_id = arguments.get('verification_id')
        env = controller._get_env_for_operation('read')
        Model = env['ai.safe.operation'].sudo()

        if verification_id:
            verif = Model.search(
                [('verification_id', '=', verification_id)], limit=1)
        else:
            # Sin id: buscar la última operación del solicitante (mismo uid con el
            # que se creó), dentro de una ventana reciente. Preferir confirmada.
            uid = env.uid
            cutoff = fields.Datetime.to_string(
                fields.Datetime.now() - timedelta(hours=2))
            base = [('user_id', '=', uid), ('create_date', '>=', cutoff)]
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
                'error': 'No hay ninguna operación reciente tuya que consultar.',
            })
        # Toast solo confirma. Reintentar execute SOLO si sigue confirmed
        # (el HTTP del toast no terminó). Un execute fallido cancela el ticket.
        if verif.status == 'confirmed' and not verif.executed:
            try:
                verif._clear_stale_execute_claims(older_than_seconds=30)
                # Invalidar cache tras clear SQL.
                verif = Model.browse(verif.id)
                applied = verif.execute_plan_now()
                verif = Model.browse(verif.id)
                if applied is False:
                    _logger.info(
                        'MCP: get_safe_operation_status %s execute busy',
                        verif.verification_id,
                    )
            except Exception as apply_exc:
                _logger.warning(
                    'MCP: get_safe_operation_status apply %s failed: %s',
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
                '[DONE] Tabla en presentation. NO llames más tools.'
            )
        return _text_response(payload)
    except Exception as e:
        return _text_response({'success': False, 'error': str(e)})


def _text_response(payload):
    """Envuelve un dict como respuesta MCP de texto (JSON)."""
    return {
        'content': [
            {'type': 'text', 'text': json.dumps(payload, ensure_ascii=False, default=str)}
        ]
    }
