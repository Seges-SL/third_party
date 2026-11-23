# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 Patanegra Soft <https://patanegra.com>
"""What a record needs, told apart by who is asking for it.

The model and the form do not mean the same thing by "required". What the
model demands cannot wait: the create fails and no record is born, so it has
to be settled before anything is proposed. What only the form demands does
not stop the ORM — the record exists and a person can finish it on screen,
which beats dictating a picker out loud.

So the two are kept apart: one blocks, the other is something the record is
still waiting for. Fields the system fills on its own —a default, a computed
or related value— belong to neither: nobody should be asked for them.
"""
from __future__ import annotations

import json
import xml.etree.ElementTree as ElementTree


def _is_empty(value):
    if value is None or value is False:
        return True
    return isinstance(value, (str, list, tuple, dict)) and not value


def _askable(Model, names):
    """Of those fields, the ones a person could be expected to fill in.

    Computed is not the same as out of the user's hands. A stored compute
    that is not readonly is filled in by whoever opens the form and only
    worked out for them when they leave it empty —the subject of a lead is
    exactly that—, and skipping those asked for nothing and let the record
    be born without the one line that says what it is about.
    """
    out = set()
    for name in names:
        field = Model._fields.get(name)
        if field is None:
            continue
        if getattr(field, 'related', None):
            continue
        computed = getattr(field, 'compute', None)
        if computed and not getattr(field, 'inverse', None):
            # Readonly by default: a compute nobody can write is not a
            # question, it is an answer the model gives itself.
            if getattr(field, 'readonly', True):
                continue
        out.add(name)
    return out


def _model_required(Model):
    """Fields the model itself declares mandatory."""
    return _askable(Model, [
        name for name, field in Model._fields.items()
        if getattr(field, 'required', False)
    ])


def _form_required(env, model):
    """Fields the form asks a person for, ignoring conditional ones.

    A field the form hides or locks is not asked of anybody, and a
    ``required`` that depends on other values only holds for some records.

    Locked also means locked on a condition. A field that goes read-only as
    soon as its neighbour is filled in is a field the screen works out from
    that neighbour —the analytic group of a business area is exactly that—,
    and asking for it is asking the same thing a second time.
    """
    try:
        arch = env[model].fields_view_get(view_type='form')['arch']
        root = ElementTree.fromstring(arch)
    except Exception:
        return set()
    inside = set()
    for parent in root.iter('field'):
        for child in parent.iter('field'):
            if child is not parent:
                inside.add(id(child))
    names = set()
    for node in root.iter('field'):
        name = node.get('name')
        if not name or id(node) in inside:
            continue
        try:
            modifiers = json.loads(node.get('modifiers') or '{}')
        except ValueError:
            continue
        if modifiers.get('required') is not True:
            continue
        if modifiers.get('readonly') or modifiers.get('invisible') is True:
            continue
        names.add(name)
    return _askable(env[model], names)


def _label_of(Model, name):
    """The field's name as this user reads it on screen.

    ``_fields[...].string`` is the English written in the source and never
    goes near a translation, so a list built from it comes out in English on
    a Spanish screen while every other label around it is translated.
    """
    field = Model._fields.get(name)
    fallback = (field.string if field is not None else '') or name
    try:
        return Model.fields_get([name])[name]['string'] or fallback
    except Exception:
        return fallback


def _labelled(Model, names):
    return [(name, _label_of(Model, name)) for name in sorted(names)]


def missing_required_fields(env, model, values):
    """Fields the MODEL demands that the plan leaves empty.

    These stop the plan: without them the create raises and nothing is
    written, so there is nothing to finish later.
    """
    if not model or model not in env:
        return []
    Model = env[model]
    given = values if isinstance(values, dict) else {}
    pending = [
        name for name in _model_required(Model)
        if name not in given or _is_empty(given[name])
    ]
    if not pending:
        return []
    try:
        defaults = Model.default_get(pending)
    except Exception:
        defaults = {}
    return _labelled(Model, [
        name for name in pending if _is_empty(defaults.get(name))
    ])


#: What a model implements to add its own conditions to a write from the
#: assistant. Nameless here on purpose: the engine asks, the owner answers.
AGENT_REQUIRED_HOOK = 'ai_required_fields'


def missing_for_agent(env, model, values):
    """Fields the MODEL asks of the assistant, beyond what the ORM demands.

    Some records are useless without a value the column happily leaves
    empty —who a job is for, the day someone has to turn up—, and a rule
    written in a prompt is followed nearly always, which is not the same as
    always. The model that owns the record says what those are, and the plan
    does not get proposed without them.

    Returns ``[(name, label, type)]``; the type is there so a channel that
    knows how to ask for a date can offer its picker.
    """
    if not model or model not in env:
        return []
    Model = env[model]
    hook = getattr(Model, AGENT_REQUIRED_HOOK, None)
    if not callable(hook):
        return []
    given = values if isinstance(values, dict) else {}
    try:
        names = hook(given) or []
    except Exception:  # pragma: no cover - a plan is never worth a traceback
        return []
    out = []
    for name in names:
        field = Model._fields.get(name)
        if field is None or (name in given and not _is_empty(given[name])):
            continue
        out.append((name, _label_of(Model, name), field.type))
    return out


#: Where a field's demand comes from. The caller decides what to do with
#: each: one stops the write, the others are what the record is waiting for.
FROM_MODEL = 'model'
FROM_AGENT = 'agent'
FROM_FORM = 'form'


def fields_wanted(env, model, values=None):
    """Everything this model asks a person for, in one list.

    A channel that wants to collect the data before writing —a script on a
    phone, a form somewhere else— needs the three demands together and needs
    to tell them apart: what the ORM refuses to write empty, what the model
    itself asks of the assistant, and what only the form asks for.

    Each entry carries its type and, for a relation, the model at the other
    end, so the caller can offer the right way to fill it without knowing
    anything about this particular record.

    ``values`` is what the record is already born with, and it is passed on:
    what a model asks of the assistant often depends on what kind of record
    it is, and that is settled before anyone is asked anything.
    """
    if not model or model not in env:
        return []
    Model = env[model]
    given = values if isinstance(values, dict) else {}
    seen = {}

    def add(name, source):
        field = Model._fields.get(name)
        if field is None or name in seen:
            return
        seen[name] = {
            'name': name,
            'label': _label_of(Model, name),
            'type': field.type,
            'relation': getattr(field, 'comodel_name', None) or '',
            'source': source,
        }

    for name, _label in missing_required_fields(env, model, given):
        add(name, FROM_MODEL)
    for name, _label, _type in missing_for_agent(env, model, given):
        add(name, FROM_AGENT)
    for name in sorted(_form_required(env, model)):
        if name in given and not _is_empty(given[name]):
            continue
        add(name, FROM_FORM)
    return list(seen.values())


def form_pending_by_record(env, model, records):
    """What the form still asks for on each record: ``{id: [(name, label)]}``.

    Read from the records themselves, after the write, so whatever the
    instance filled on its own —a default, an onchange, the create— is not
    reported as missing.
    """
    if not model or model not in env or not records:
        return {}
    Model = env[model]
    names = sorted(_form_required(env, model))
    if not names:
        return {}
    out = {}
    for record in records:
        empty = []
        for name in names:
            try:
                if record[name]:
                    continue
            except Exception:
                continue
            empty.append(name)
        if empty:
            out[record.id] = _labelled(Model, empty)
    return out
