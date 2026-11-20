# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 Patanegra Soft <https://patanegra.com>
"""A dictated sentence, split among the fields that were asked for.

Which of the asked fields a spoken phrase belongs to is a question about
language, and the only way to answer it inside the code is a list of words
in one tongue —«if they say this, it goes there»—, which is wrong the day
someone phrases it differently and does not exist at all in another
language. So it is asked, in the smallest way there is: the fields that were
asked for go in, values come back, and nothing else happens. No tools, no
memory, no conversation.

What comes back is text, not a record: the value of a relation is resolved
against the model afterwards, where a wrong guess cannot happen.
"""
from __future__ import annotations

import json
import logging
import re

_logger = logging.getLogger(__name__)

#: Only the part of the answer we know what to do with. Anything else the
#: model decides to say is dropped without comment.
_JSON_BLOCK = re.compile(r'\{.*\}', re.S)
#: A finished ``"key": "value"``. An object cut mid-field is not this.
_COMPLETE_PAIR = re.compile(
    r'"((?:\\.|[^"\\])*)"\s*:\s*"((?:\\.|[^"\\])*)"',
)
_MAX_VALUE_CHARS = 200
#: Thinking models used to eat this budget and return half an object.
_MAX_TOKENS = 2048
_RETRY_TOKENS = 4096

_SYSTEM = (
    'You split a dictated sentence among the fields of a form.\n'
    'You are given the fields that are being asked for and one sentence.\n'
    'Answer with a JSON object and nothing else: the keys are field names '
    'from the list, the values are what the speaker said for that field.\n'
    'Rules:\n'
    '- Only fields from the list. Never invent a field.\n'
    '- Only what the sentence is about. A field the sentence says nothing '
    'about is left out; do not fill it with an example.\n'
    '- The speaker may name a field before saying its value, using the '
    'name in brackets or one of the other names given for it. When that '
    'happens, what follows the name is that field\'s value and the name '
    'itself is not part of it.\n'
    '- When nothing is named, work out which field each part of the '
    'sentence is about from what it says.\n'
    '- When a field lists its options, answer with one of them, exactly as '
    'written. Pick the one the sentence is about even if the speaker used '
    'other words for it; if none of them fits, leave the field out.\n'
    '- For a relation with no options listed, answer with the words that '
    'identify it —a name, a town, a reference—, never an id.\n'
    '- For a date, answer in ISO form (YYYY-MM-DD), working out days said '
    'relative to today. If the sentence says no day, leave it out.\n'
    '- A field that already has something in it is shown as "now". The '
    'speaker may be changing one of those —"the salesperson is Ann, not '
    'Bob"—: answer with the value that stands, never with the one being '
    'taken back, and leave out the fields that are not being changed.\n'
    '- A field that says several names are allowed may hold more than one; '
    'separate them with | and nothing else.\n'
    '- If the sentence means everyone and the field lists words that mean '
    'everyone, answer with one of those words and nothing else.\n'
    '- An empty object is a correct answer.'
)

#: Listing a whole table is neither useful nor affordable; past this the
#: field is resolved by looking the words up instead.
OPTIONS_MAX = 40


def _field_lines(fields, filled=None):
    """The form as the smallest thing that can be answered against.

    ``filled`` is what each field holds right now, readable. Without it a
    correction is unreadable: «the salesperson is Ann, not Bob» is only a
    correction to someone who can see that Bob is what is in there.
    """
    now = filled or {}
    out = []
    for field in fields or []:
        name = (field or {}).get('name')
        if not name:
            continue
        line = '- %s (%s)' % (name, field.get('label') or name)
        # The screen has one word for it and the office has others; a field
        # known by one word only is a field that never gets filled in.
        also = [str(word) for word in (field.get('also') or []) if word]
        if also:
            line += ', also called %s' % ' or '.join(also)
        ftype = field.get('type') or ''
        if ftype:
            line += ' [%s]' % ftype
        if field.get('relation'):
            line += ' -> %s' % field['relation']
        options = [str(o) for o in (field.get('options') or []) if o]
        if options and len(options) <= OPTIONS_MAX:
            # The whole answer, written out. Choosing from a closed list is
            # a far smaller question than naming something from nothing.
            line += '\n  one of: %s' % ' | '.join(options)
        if field.get('many'):
            line += '\n  several names allowed, separated by |'
        everyone = [
            str(word) for word in (field.get('everyone') or []) if word
        ]
        if everyone:
            line += '\n  these words mean everyone: %s' % ' | '.join(everyone)
        held = _as_text(now.get(name))
        if held:
            line += '\n  now: %s' % held
        out.append(line)
    return '\n'.join(out)


def _when(today):
    """Today, so a day said relative to it is a day and not a phrase."""
    if not today:
        return ''
    return 'Today is %s.\n\n' % today


def _as_text(value):
    if isinstance(value, bool) or value is None:
        return ''
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, (list, tuple)):
        value = ' '.join(str(part) for part in value)
    return str(value).strip()[:_MAX_VALUE_CHARS]


def _object_text(payload):
    """The JSON object inside what the model said, or the whole string."""
    text = (payload or '').strip()
    if not text:
        return ''
    if text.startswith('{'):
        return text
    found = _JSON_BLOCK.search(text)
    return found.group(0) if found else text


def _load_object(text):
    try:
        data = json.loads(text or '{}')
    except ValueError:
        return None
    return data if isinstance(data, dict) else None


def _pairs_that_closed(text):
    """Fields the model finished writing before the answer was cut off."""
    out = {}
    for match in _COMPLETE_PAIR.finditer(text or ''):
        try:
            piece = json.loads('{%s}' % match.group(0))
        except ValueError:
            continue
        if isinstance(piece, dict):
            out.update(piece)
    return out


def unfinished_answer(payload):
    """True when there is an object that does not parse: cut off, not empty."""
    text = _object_text(payload)
    if not text or '{' not in text:
        return False
    return _load_object(text) is None


def read_answer(payload, fields):
    """The model's answer, kept to the fields that were actually asked.

    Split out so the shape can be tested without a provider behind it: a
    model that answers with prose around the object, with a field nobody
    asked for or with a number where text was wanted is the normal case,
    not the exception. An object cut mid-field keeps the pairs that closed.
    """
    wanted = {
        (field or {}).get('name'): field
        for field in (fields or []) if (field or {}).get('name')
    }
    text = _object_text(payload)
    if not text:
        return {}
    data = _load_object(text)
    if data is None:
        data = _pairs_that_closed(text)
    out = {}
    for name, value in (data or {}).items():
        if name not in wanted:
            continue
        said = _as_text(value)
        if said:
            out[name] = said
    return out


def split_sentence(env, fields, said, today=None, agent_code=None,
                   consumer_key='admin', filled=None):
    """``{field: what was said for it}``. Empty when nothing can be placed.

    Never raises. The caller is a screen in the middle of being filled in,
    and a provider that is down should leave the same field still owed —
    which is visible and can be said again— rather than a broken request.
    """
    sentence = (said or '').strip()
    if not sentence or not fields:
        return {}
    lines = _field_lines(fields, filled=filled)
    if not lines:
        return {}
    from .agent_engine import llm_json_completion_for_agent
    from .inference_audit import inference_audit

    user_prompt = '%sFields:\n%s\n\nSentence:\n%s' % (
        _when(today), lines, sentence,
    )

    def _ask(max_tokens):
        return llm_json_completion_for_agent(
            env,
            _SYSTEM,
            user_prompt,
            consumer_key=consumer_key,
            agent_code=agent_code,
            max_tokens=max_tokens,
            json_mode=True,
            disable_thinking=True,
        )

    try:
        with inference_audit(
            env,
            endpoint='spoken_fields',
            source_channel='internal',
            user_id=env.uid if env is not None and env.user else None,
            agent_code=agent_code,
            user_prompt=sentence,
        ):
            result = _ask(_MAX_TOKENS)
            if (result or {}).get('error'):
                return {}
            content = (result or {}).get('content')
            placed = read_answer(content, fields)
            if placed or not unfinished_answer(content):
                return placed
            _logger.warning('spoken_fields: answer was cut off; asking again')
            again = _ask(_RETRY_TOKENS)
            if (again or {}).get('error'):
                return placed
            return read_answer((again or {}).get('content'), fields) or placed
    except Exception:
        _logger.warning('spoken_fields: nothing placed', exc_info=True)
        return {}
