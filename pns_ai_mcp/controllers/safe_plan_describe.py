# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""What a plan will do, in words: auto-confirm check, values, record targets and the language of the reply."""

from odoo import _

from .safe_plan_validate import (
    _canonical_op,
    _OP_DANGER,
    OP_LABEL,
)


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

    Record or tool text already in this turn may carry injected orders. A
    host on the whitelist still runs: the whitelist is the door. The open
    policy is not that door: a host it lets in waits. A trusted server still
    runs a read. A write on that server waits.
    """
    from urllib.parse import urlparse
    if not steps:
        return False
    untrusted_turn = bool((env.context or {}).get('pns_ai_untrusted_turn'))
    for step in steps:
        op = _canonical_op(step.get('op'))
        if op == 'fetch_url':
            hostname = (urlparse(step.get('url', '')).hostname or '').lower()
            whitelist = env['ai.url.whitelist']
            if not whitelist.is_fetch_url_trusted(hostname):
                return False
            if untrusted_turn and not whitelist.is_domain_whitelisted(hostname, kind='web'):
                return False
        elif op == 'api_call':
            srv = env['ai.api.server'].sudo().search(
                [('code', '=', step.get('server', '')), ('active', '=', True)],
                limit=1)
            if not (srv and srv.trusted):
                return False
            if untrusted_turn and not _api_call_reads_only(srv, step.get('tool', '')):
                return False
        else:
            return False
    return True


def _api_call_reads_only(srv, tool_name):
    """True when the server's driver says *tool_name* changes nothing remote."""
    try:
        from ..lib.api.drivers import get_api_driver
        return bool(get_api_driver(srv.api_type).reads_only(srv, tool_name))
    except Exception:
        return False


# Odoo x2many commands → readable label. Destructive operations
# (replace/remove/clear/delete) carry ⚠️ so the human who confirms sees them
# at a glance: the weak link is not the AI, it is confirming without understanding the plan.
_X2M_CMD = {
    0: 'adds new',
    1: 'updates',
    2: '⚠️ DELETES',
    3: '⚠️ removes',
    4: 'adds',
    5: '⚠️ CLEARS (removes all)',
    6: '⚠️ REPLACES all with',
}


def _names_for(env, comodel, ids):
    """display_name of the ids (best-effort; sudo only to read labels)."""
    if not comodel or not ids:
        return ''
    try:
        recs = env[comodel].sudo().browse([i for i in ids if isinstance(i, int)])
        names = [r.display_name for r in recs if r.exists()]
        return ', '.join(n for n in names if n)
    except Exception:
        return ', '.join(str(i) for i in ids)


def _written_date(env, ftype, value):
    """A date written the way this user writes dates.

    The plan is read to decide in a couple of seconds, and the database
    spelling leaves the reader working out which of the two numbers is the
    month before they can say yes.
    """
    if not value:
        return ''
    try:
        from odoo.tools.misc import format_date, format_datetime
        if ftype == 'date':
            return format_date(env, value)
        return format_datetime(env, value)
    except Exception:
        return ''


def _describe_value(env, field_def, value):
    """Turn a field value into readable words. x2many command tuples are
    explained, and the destructive ones are marked with ⚠️."""
    comodel = getattr(field_def, 'comodel_name', None) if field_def else None
    ftype = getattr(field_def, 'type', None) if field_def else None
    if ftype in ('many2many', 'one2many') and isinstance(value, list):
        parts = []
        for cmd in value:
            if isinstance(cmd, (list, tuple)) and cmd and isinstance(cmd[0], int):
                code = cmd[0]
                label = _(_X2M_CMD[code]) if code in _X2M_CMD else 'op %s' % code
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
        from ..utils.record_label import placed_label
        # Authorising a write means knowing which record is going in, and a
        # bare name does not tell two companies of the same trade apart.
        return '«%s»' % (
            placed_label(env, comodel, value)
            or _names_for(env, comodel, [value])
            or value
        )
    if ftype in ('date', 'datetime'):
        return _written_date(env, ftype, value) or str(value)
    return str(value)


_VALUE_CHARS_MAX = 160


_VALUE_FIELDS_MAX = 12


def _value_lines(env, model, values):
    """One field per line, so a long one cannot push another off the card.

    Strung together they were cut at a fixed length, and what fell off was
    whatever came last —a date, an owner—, which is exactly the part the
    reader is checking before authorising the write.
    """
    if not isinstance(values, dict) or not values:
        return []
    try:
        fields = env[model]._fields
    except Exception:
        fields = {}
    lines = []
    for fname, value in values.items():
        fdef = fields.get(fname)
        label = (getattr(fdef, 'string', None) or fname) if fdef else fname
        shown = _describe_value(env, fdef, value)
        if len(shown) > _VALUE_CHARS_MAX:
            shown = shown[:_VALUE_CHARS_MAX] + '…'
        lines.append('%s: %s' % (label, shown))
    if len(lines) > _VALUE_FIELDS_MAX:
        rest = len(lines) - _VALUE_FIELDS_MAX
        lines = lines[:_VALUE_FIELDS_MAX]
        lines.append(_('and %s more fields') % rest)
    return lines


_DETAIL_GROUP_MAX = 3


_DETAIL_IDS_MAX = 5


def _step_targets(env, model, step):
    """Which records a step aims at, by name while they are few enough to read."""
    ids = step.get('ids')
    if isinstance(ids, list) and ids:
        if len(ids) <= _DETAIL_IDS_MAX:
            return _names_for(env, model, ids) or str(ids)
        return _('%s records') % len(ids)
    domain = step.get('domain')
    return str(domain) if domain else ''


def _crud_step_details(env, op, model, group):
    """What each step carries, under the line that counts them.

    "Create 1 record in Leads" is not something a person can authorise: what
    decides it is the customer, the date and the text going in. Only small
    groups are spelled out — past that the headline already gives the number,
    and a wall of lines would bury the verb and the traffic light.
    """
    if len(group) > _DETAIL_GROUP_MAX:
        return []
    out = []
    for step in group:
        head = ''
        values = None
        if op in ('create', 'copy'):
            if op == 'copy':
                source = _names_for(env, model, [step.get('id')])
                if source:
                    head = _('from «%s»') % source
            values = step.get('values') if op == 'create' else step.get('overrides')
        else:
            target = _step_targets(env, model, step)
            if target:
                head = _('on «%s»') % target
            if op == 'write':
                values = step.get('values')
        if head:
            out.append('   · ' + head)
        for line in _value_lines(env, model, values):
            out.append('   · ' + line)
    return out


def describe_safe_plan(env, steps):
    """Describe the plan in readable words for the confirmation toast.

    Goal: concise and informative — the user decides in 2 seconds.
    Examples:
      🟢 Crear 1 registro en «Contactos»
      🟡 Modificar 2 registros en «Facturas»
      🔴 Borrar 3 registros en «Tareas»
      🔴 Conectarse a example.com (dominio no en lista blanca)
    """
    from urllib.parse import urlparse

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

    # Group CRUD steps by (op, model): the headline counts them, and a small
    # group also spells out what each step carries.
    crud_steps = {}  # (op, model) → [step, …]
    lines = []

    for step in steps:
        op = _canonical_op(step.get('op'))

        if op == 'fetch_url':
            url = step.get('url', '?')
            hostname = (urlparse(url).hostname or '').lower()
            Whitelist = env['ai.url.whitelist']
            status = Whitelist._fetch_url_access_status(hostname, user=env.user)
            if status in ('allowed', 'open_add'):
                lines.append('🟢 ' + _('Connect to %s') % hostname)
            elif status == 'needs_reactivation':
                lines.append('🟡 ' + _(
                    'Connect to %s (domain in the whitelist, deactivated — '
                    'it will be reactivated on confirm)'
                ) % hostname)
            else:
                lines.append('🟡 ' + _(
                    'Connect to %s (add to the whitelist — AI administrator only)'
                ) % hostname)
            continue

        if op == 'api_call':
            server_code = step.get('server', '?')
            tool_name = step.get('tool', '?')
            srv = env['ai.api.server'].sudo().search(
                [('code', '=', server_code), ('active', '=', True)], limit=1)
            srv_name = srv.name if srv else server_code
            lines.append('🟡 ' + _('Call %s → %s') % (srv_name, tool_name))
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
                detail = action._preview(**(step.get('args') or {})) if action else ''
            except Exception as exc:
                detail = _('(preview not available: %s)') % exc
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
                    bits.append(Action._preview_field_set_required(
                        model=step.get('model'), field=step.get('field'),
                        required=required,
                    ))
                except Exception as exc:
                    bits.append(str(exc))
            if view_ids:
                try:
                    bits.append(Action._preview_view_set_field_required(
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
        crud_steps.setdefault((op, model), []).append(step)

    # Emit aggregated CRUD lines
    for (op, model), group in crud_steps.items():
        danger = _OP_DANGER.get(op, 'medium')
        emoji = _danger_emoji.get(danger, '🟡')
        label = _(OP_LABEL[op]) if op in OP_LABEL else op
        can_trash = (
            op == 'unlink'
            and 'ai.change.journal' in env
            and env['ai.change.journal'].model_can_archive(model)
        )
        if can_trash:
            label = _('Move to trash')
        ml = _model_label(model)
        count = len(group)
        if count == 1:
            lines.append('%s %s' % (emoji, _('%s 1 record in «%s»') % (label, ml)))
        else:
            lines.append('%s %s' % (
                emoji, _('%s %s records in «%s»') % (label, count, ml),
            ))
        if op == 'unlink':
            if can_trash:
                lines.append('   · ' + _(
                    'Can be restored from Applied changes until the trash is emptied.'
                ))
            else:
                lines.append('   · ' + _('This delete cannot be undone.'))
        lines.extend(_crud_step_details(env, op, model, group))

    return lines


def _ack_lang(env):
    """Lang of the door env (context), not the public request."""
    if env is None:
        return ''
    ctx = getattr(env, 'context', None) or {}
    lang = (ctx.get('lang') or getattr(env, 'lang', None) or '')
    return lang.strip() if isinstance(lang, str) else ''


def _ack_tr(env, source):
    """Translate an ack msgid with the caller's env (user and language).

    ``from odoo import _`` follows the HTTP request. Secretary is ``auth=none``,
    so that request is public/English. Odoo 14 has no ``env._``; look up
    ``ir.translation`` with the door lang, same as the PWA chrome.
    """
    if not source:
        return source
    if env is not None:
        gettext = getattr(env, '_', None)
        if callable(gettext):
            try:
                out = gettext(source)
                if out and out != source:
                    return out
            except Exception:
                pass
        lang = _ack_lang(env)
        if lang and 'ir.translation' in env:
            try:
                found = env['ir.translation'].sudo()._get_source(
                    None, 'code', lang, source,
                )
                if found:
                    return found
            except Exception:
                pass
    return _(source)
