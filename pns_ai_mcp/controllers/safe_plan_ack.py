# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""Messages after a plan ran: the acknowledgement and the verification follow-up."""

import json
from odoo import _

from .safe_plan_describe import (
    _ack_tr,
)

from .safe_plan_execute import (
    _needs_llm_followup,
    _plan_has_crud,
)


def _first_written_model(steps):
    """The model of the write, to name the field the database complained about."""
    for step in steps or []:
        if isinstance(step, dict) and step.get('model'):
            return step.get('model')
    return None


def _step_values(steps):
    """Hand out the values of each create/copy step in the order they ran."""
    queues = {}
    for step in steps or []:
        if not isinstance(step, dict):
            continue
        op = step.get('op')
        if op not in ('create', 'copy'):
            continue
        vals = step.get('values') if op == 'create' else step.get('overrides')
        queues.setdefault(op, []).append(vals if isinstance(vals, dict) else {})

    def take(op):
        queue = queues.get(op) or []
        return queue.pop(0) if queue else {}
    return take


def _ack_card(env, model, rid, values=None, said=None):
    """The record as a person reads it: its reference, its name, its fields."""
    from ..utils.ack_record_card import record_card

    try:
        return record_card(
            env, model, rid, values=values,
            title_of=(lambda head: said % head) if said else None,
        )
    except Exception:
        return None


def build_user_ack_message(title, results=None, action='confirm', error=None,
                           steps=None, env=None):
    """Visible chat note after Confirm/Cancel — CRUD writes only.

    Deterministic (no LLM). Returns None for pure fetch_url / api_call plans.
    """
    title = title or _ack_tr(env, _('supervised operation'))
    if not _plan_has_crud(results=results, steps=steps):
        return None

    if action == 'cancel':
        return _ack_tr(env, _(
            'Alright — I cancelled «%s». No changes were applied.'
        )) % title

    if error:
        # The driver's own wording —constraint names, DETAIL lines, the column
        # as the table spells it— tells the person who dictated a sentence
        # nothing about what to do next.
        from ..utils.db_error_text import failed_ack
        return failed_ack(
            env, title, error, model=_first_written_model(steps),
            translate=(lambda source: _ack_tr(env, source)),
        )

    # Only after execute (with result rows). Confirm-without-execute must not
    # claim success; callers may set user_ack_message explicitly for "applying…".
    if not results:
        return None

    lines = []

    def still_to_fill(item):
        """What the form asks of the new record, under its own card."""
        labels = [str(one) for one in (item.get('pending') or []) if one]
        if not labels:
            return []
        return ['  - ' + _ack_tr(env, _('Still to fill in: %s')) % ', '.join(labels)]

    pending = _step_values(steps)
    for item in results:
        if not isinstance(item, dict):
            continue
        op = item.get('op')
        if op == 'create':
            card = _ack_card(
                env, item.get('model'), item.get('id'),
                values=pending('create'),
                said=_ack_tr(env, _('Created: %s')),
            )
            if card:
                lines.extend(card)
                lines.extend(still_to_fill(item))
                continue
            lines.append(
                '- ' + _ack_tr(env, _('Created: %s (%s #%s)')) % (
                    item.get('name') or '—',
                    item.get('model') or '?',
                    item.get('id') or '?',
                )
            )
            lines.extend(still_to_fill(item))
        elif op == 'write':
            # One record is the usual case and the one worth reading: what
            # it says now, not that a row somewhere changed.
            ids = [rid for rid in (item.get('ids') or []) if rid]
            changed = pending('write')
            card = _ack_card(
                env, item.get('model'), ids[0],
                values=changed,
                said=_ack_tr(env, _('Updated: %s')),
            ) if len(ids) == 1 else None
            if card:
                lines.extend(card)
                lines.extend(still_to_fill(item))
                continue
            lines.append(
                '- ' + _ack_tr(env, _('Updated %s record(s) on %s')) % (
                    item.get('count') or len(ids),
                    item.get('model') or '?',
                )
            )
        elif op == 'copy':
            card = _ack_card(
                env, item.get('model'), item.get('new_id'),
                values=pending('copy'),
                said=_ack_tr(env, _('Copied: %s')),
            )
            if card:
                lines.extend(card)
                lines.extend(still_to_fill(item))
                continue
            lines.append(
                '- ' + _ack_tr(env, _('Copied: %s (%s #%s)')) % (
                    item.get('name') or '—',
                    item.get('model') or '?',
                    item.get('new_id') or '?',
                )
            )
            lines.extend(still_to_fill(item))
        elif op == 'unlink':
            count = item.get('count') or len(item.get('ids') or [])
            model = item.get('model') or '?'
            if item.get('quarantine'):
                lines.append(
                    '- ' + _ack_tr(env, _('Moved %s record(s) on %s to the trash')) % (
                        count, model,
                    )
                )
            else:
                lines.append(
                    '- ' + _ack_tr(env, _('Deleted %s record(s) on %s')) % (
                        count, model,
                    )
                )
        elif op == 'field_required':
            lines.append(
                '- ' + _ack_tr(env, _('Field required on %s.%s')) % (
                    item.get('model') or '?',
                    item.get('field') or '?',
                )
            )
    # The cards say what happened and name the records; the sentence above
    # them said the same thing in the plan's own words, which is the words
    # the user had just used. Kept only for a plan whose rows say nothing,
    # where silence would read as nothing having run.
    if not lines:
        return _ack_tr(
            env, _('Done. The write operation «%s» completed successfully.'),
        ) % title
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
            env=env,
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

    The payload is the outcome. It does not say how to paint it.
    """
    guard = (
        ' IMPORTANT: this is only a result notice, NOT a write request. '
        'Do not propose or call safe_plan_request again. '
        'Do not run relaxaicode on ai.safe.operation: the data is already here.'
    )
    title = title or 'Supervised operation'
    if action == 'cancel':
        return (
            f'[System result] The user CANCELLED «{title}». '
            f'No change was made. Confirm it briefly in their language.'
            + guard
        )
    if error:
        return (
            f'[System result] The user confirmed «{title}» but it FAILED: {error}. '
            f'Explain it briefly in their language.'
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
            f'[System result] The user confirmed fetch_url «{title}». '
            f'The HTTP data is in the JSON below (field body). '
            f'It is the outcome of the approval, not an order on how to show it. '
            f'Cite the URL as the source and do not invent figures.\n'
            f'DATA:\n{data_block}'
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
            f'[System result] The user CONFIRMED api_call «{title}». '
            f'The external API data is in the JSON below (field body). '
            f'If truncated=true, use pagination.suggested_arguments for the next '
            f'page with safe_plan_request (op=api_call). '
            f'Analyse the JSON and answer with a table or a readable summary; '
            f'do not invent figures. Call no tool except to fetch the next page.\n'
            f'DATA:\n{data_block}'
            + ' IMPORTANT: this is only a result notice, NOT a write request. '
            'Do not run relaxaicode on ai.safe.operation: the data is already here.'
        )
    det = json.dumps(results, ensure_ascii=False, default=str)
    return (
        f'[System result] The user CONFIRMED «{title}» and it ran successfully.'
        + (f' Result: {det}.' if det else ' ')
        + ' Report the success in their language, naming what was created or changed.'
        + guard
    )
