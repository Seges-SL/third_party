# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""Rewrite the code of a captured skill so it reads its parameters instead of the literals of the turn."""

from __future__ import annotations
import ast
import io
import re
import tokenize
from datetime import date as _date

from .skill_runtime_param_schema import (
    _INT_DEFAULT,
    _is_slash_param_key,
    _schema_as_dict,
    _schema_key_is_year_slot,
    _schema_key_set,
)

from .skill_runtime_help_prompts import (
    inject_unread_param_reads,
    schema_keys_that_need_place,
    schema_keys_unread_by_code,
)


# ``yearall = 2026`` from a captured turn must not overwrite the sandbox.
_LITERAL_ASSIGN_RE = re.compile(
    r'^(\s*)([A-Za-z_][A-Za-z0-9_]*)\s*=\s*'
    r'(-?\d+(?:\.\d+)?|'
    r"'(?:\\.|[^'])*'|"
    r'"(?:\\.|[^"])*"|'
    r'True|False|None)'
    r'\s*(#.*)?$'
)


def drop_schema_literal_assigns(code, schema):
    """Drop ``key = <literal>`` so the sandbox value of that key wins.

    ``key = None`` is the NameError fallback, not a turn literal.
    Only keys that need a place (default, required, or already used).
    """
    keys = set(schema_keys_that_need_place(schema, code))
    if not keys:
        keys = _schema_key_set(schema)
    if not keys or not code:
        return code or ''
    kept = []
    changed = False
    for line in code.splitlines(True):
        raw = line[:-1] if line.endswith('\n') else line
        match = _LITERAL_ASSIGN_RE.match(raw)
        if match and match.group(2) in keys:
            value = (match.group(3) or '').strip()
            if value not in ('None', 'True', 'False'):
                changed = True
                continue
        kept.append(line)
    if not changed:
        return code
    return ''.join(kept)


def bind_code_to_schema_params(code, schema, env=None):
    """NameError reads plus the schema names used in the query and title."""
    return _replace_unique_default_literals(
        drop_schema_literal_assigns(
            inject_unread_param_reads(code, schema),
            schema,
        ),
        schema,
        env,
    )


def _schema_default_int_literal(spec, env=None):
    """Expanded integer default, or None. Tokens stay tokens without ``env``."""
    spec = spec if isinstance(spec, dict) else {}
    raw = spec.get('default')
    if raw in (None, ''):
        return None
    text = str(raw).strip()
    if env is not None:
        from .skill_param_tokens import expand_skill_param_text
        text = expand_skill_param_text(text, env)
    if _INT_DEFAULT.fullmatch(text):
        return text
    return None


def _unique_int_default_map(schema, env=None):
    """``{'12': 'months'}`` when exactly one key has that integer default."""
    parsed = _schema_as_dict(schema)
    hits = {}
    for key in _schema_key_set(parsed):
        lit = _schema_default_int_literal(parsed.get(key), env)
        if lit is None:
            continue
        hits.setdefault(lit, []).append(key)
    return {lit: names[0] for lit, names in hits.items() if len(names) == 1}


def _replace_number_tokens(src, mapping, schema=None):
    """Put the schema name in the parameter's slot, not in every matching number.

    A count (``12``) only replaces ``months=12`` / ``months=-12`` and
    ``else 12`` / ``or 12``. A year also replaces a bare 4-digit NUMBER
    (``date(2026, 1, 1)``). ``if n > 12`` stays.
    """
    if not src or not mapping:
        return src
    parsed = _schema_as_dict(schema)
    year_lits = set()
    for lit, key in mapping.items():
        if _schema_key_is_year_slot(key, parsed.get(key)):
            year_lits.add(lit)
    keys = set(mapping.values())
    try:
        tokens = list(tokenize.generate_tokens(io.StringIO(src).readline))
    except (tokenize.TokenError, IndentationError):
        return src
    spans = []
    n = len(tokens)
    i = 0
    while i < n:
        tok = tokens[i]
        if (
            tok.type == tokenize.NAME
            and tok.string in keys
            and i + 1 < n
            and tokens[i + 1].string == '='
        ):
            j = i + 2
            if j < n and tokens[j].string == '-':
                j += 1
            if j < n and tokens[j].type == tokenize.NUMBER:
                raw = tokens[j].string.lstrip('-')
                if mapping.get(raw) == tok.string:
                    spans.append((tokens[j].start, tokens[j].end, tok.string))
                    i = j + 1
                    continue
        if (
            tok.string in ('else', 'or')
            and i + 1 < n
            and tokens[i + 1].type == tokenize.NUMBER
        ):
            raw = tokens[i + 1].string.lstrip('-')
            name = mapping.get(raw)
            if name and raw not in year_lits:
                spans.append((tokens[i + 1].start, tokens[i + 1].end, name))
                i += 2
                continue
        if tok.type == tokenize.NUMBER:
            raw = tok.string.lstrip('-')
            name = mapping.get(raw)
            if name and raw in year_lits:
                spans.append((tok.start, tok.end, name))
        i += 1
    if not spans:
        return src
    lines = src.splitlines(True)
    for (sr, sc), (er, ec), name in reversed(spans):
        if sr != er or sr < 1 or sr > len(lines):
            continue
        line = lines[sr - 1]
        lines[sr - 1] = line[:sc] + name + line[ec:]
    return ''.join(lines)


# Card title (``result['title']`` / ``summary``) and the wrap ``_page_title``.
_TITLE_LINE_RE = re.compile(
    r'^(\s*(?:'
    r'_page_title\s*=\s*'
    r'|result\s*\[\s*[\'"]title[\'"]\s*\]\s*=\s*'
    r'|[\'"]title[\'"]\s*:\s*'
    r'|[\'"]summary[\'"]\s*:\s*'
    r'))([\'"])(.*)\2(\s*,?\s*)$',
)


_ISO_ASSIGN_RE = re.compile(
    r'^([ \t]*)([A-Za-z_][A-Za-z0-9_]*)\s*=\s*[\'"](\d{4}-\d{2}-\d{2})[\'"][ \t]*$',
    re.M,
)


_ISO_STR_RE = re.compile(r'[\'"](\d{4}-\d{2}-\d{2})[\'"]')


def _is_title_line(line):
    raw = line[:-1] if line.endswith('\n') else line
    return bool(_TITLE_LINE_RE.match(raw))


def _replace_title_literals(line, mapping):
    """Title / summary / ``_page_title`` with ``12`` → ``%s`` % (months,)."""
    raw = line[:-1] if line.endswith('\n') else line
    match = _TITLE_LINE_RE.match(raw)
    if not match or not mapping:
        return line
    prefix, quote, body, suffix = match.groups()
    ordered = sorted(mapping, key=len, reverse=True)
    pattern = re.compile(
        r'(?<![0-9-])(%s)(?![0-9-])' % '|'.join(re.escape(lit) for lit in ordered),
    )
    names = []
    pieces = []
    last = 0
    for hit in pattern.finditer(body):
        pieces.append(body[last:hit.start()].replace('%', '%%'))
        pieces.append('%s')
        names.append(mapping[hit.group(1)])
        last = hit.end()
    if not names:
        return line
    pieces.append(body[last:].replace('%', '%%'))
    fmt = '%s%s%s%s %% (%s,)%s' % (
        prefix, quote, ''.join(pieces), quote, ', '.join(names), suffix,
    )
    if line.endswith('\n'):
        fmt += '\n'
    return fmt


def _parse_iso_day(text):
    parts = (text or '').split('-')
    if len(parts) != 3:
        return None
    try:
        return _date(int(parts[0]), int(parts[1]), int(parts[2]))
    except ValueError:
        return None


def _month_span(start, end):
    if end < start:
        start, end = end, start
    return (end.year - start.year) * 12 + (end.month - start.month)


def _is_calendar_year_window(start, end):
    if start > end:
        start, end = end, start
    return (
        start.month == 1 and start.day == 1
        and end.month == 12 and end.day >= 28
        and start.year == end.year
    )


def _year_slot_key(mapping, schema):
    parsed = _schema_as_dict(schema)
    for _lit, key in mapping.items():
        if _schema_key_is_year_slot(key, parsed.get(key)):
            return key
    for key, spec in parsed.items():
        if _is_slash_param_key(key) and _schema_key_is_year_slot(key, spec):
            return key
    return None


def _count_slot_key(mapping, schema):
    """The months/count hole, even when the captured span is not that default."""
    parsed = _schema_as_dict(schema)
    preferred = []
    others = []
    seen = set()
    names = list(mapping.values())
    for key in parsed:
        if key not in names:
            names.append(key)
    for key in names:
        if not key or key in seen:
            continue
        if not _is_slash_param_key(key):
            continue
        if _schema_key_is_year_slot(key, parsed.get(key)):
            continue
        spec = parsed.get(key) if isinstance(parsed.get(key), dict) else {}
        typ = str(spec.get('type') or '').strip().lower()
        if typ and typ not in ('integer', 'number', 'int'):
            continue
        seen.add(key)
        if (key or '').strip().casefold() in ('months', 'meses'):
            preferred.append(key)
        elif typ in ('integer', 'number', 'int') or key in mapping.values():
            others.append(key)
    return (preferred or others or [None])[0]


def _count_key_for_span(span, mapping, schema):
    parsed = _schema_as_dict(schema)
    for lit, key in mapping.items():
        if _schema_key_is_year_slot(key, parsed.get(key)):
            continue
        try:
            n = int(lit)
        except (TypeError, ValueError):
            continue
        if abs(span - n) <= 1:
            return key
    return _count_slot_key(mapping, schema)


def _iso_assign_hits(head):
    hits = []
    for match in _ISO_ASSIGN_RE.finditer(head or ''):
        day = _parse_iso_day(match.group(3))
        if day:
            hits.append((day, match))
    return hits


def _iso_window_plan(head, mapping, schema):
    """How to bind a captured from/to ISO window, or None."""
    if not head:
        return None
    mapping = mapping or {}
    hits = _iso_assign_hits(head)
    unique = sorted({day for day, _match in hits})
    if not unique:
        found = []
        for match in _ISO_STR_RE.finditer(head):
            if _iso_on_comment_line(head, match.start()):
                continue
            day = _parse_iso_day(match.group(1))
            if day:
                found.append(day)
        unique = sorted(set(found))
        hits = []
    if not unique or len(unique) > 2:
        return None
    start = unique[0]
    end = unique[-1]
    ykey = _year_slot_key(mapping, schema)
    if len(unique) == 1:
        ckey = _count_key_for_span(
            _month_span(start, _date.today()), mapping, schema,
        )
        if not ckey:
            return None
        start_match = hits[0][1] if hits else None
        return {
            'kind': 'year_or_count' if ykey else 'count',
            'key': ckey,
            'year_key': ykey,
            'start_match': start_match,
            'end_match': None,
            'start_iso': start.isoformat(),
            'end_iso': '',
            'start_name': start_match.group(2) if start_match else 'date_from',
            'end_name': '',
        }
    ckey = _count_key_for_span(_month_span(start, end), mapping, schema)
    start_match = end_match = None
    for day, match in hits:
        if day == start:
            start_match = match
        if day == end:
            end_match = match
    base = {
        'start_match': start_match,
        'end_match': end_match,
        'start_iso': start.isoformat(),
        'end_iso': end.isoformat(),
        'start_name': start_match.group(2) if start_match else 'date_from',
        'end_name': end_match.group(2) if end_match else 'date_to',
    }
    if ykey and ckey:
        base.update(kind='year_or_count', key=ckey, year_key=ykey)
        return base
    if _is_calendar_year_window(start, end) and ykey:
        base.update(kind='year', key=ykey, year_key=ykey)
        return base
    if ckey:
        base.update(kind='count', key=ckey)
        return base
    return None


def _leading_ws(line):
    text = line or ''
    i = 0
    while i < len(text) and text[i] in ' \t':
        i += 1
    return text[:i]


def _line_span(text, pos):
    start = (text or '').rfind('\n', 0, pos) + 1
    end = (text or '').find('\n', pos)
    if end < 0:
        end = len(text or '')
    return start, end


def _iso_on_comment_line(text, pos):
    start, end = _line_span(text, pos)
    return (text or '')[start:end].lstrip().startswith('#')


def _insert_before_statement(text, pos):
    """Line start and indent of the statement that contains ``pos``."""
    start, end = _line_span(text, pos)
    cur_start = start
    cur_indent = _leading_ws((text or '')[start:end])
    scan = start
    while scan > 0:
        prev_start = text.rfind('\n', 0, scan - 1) + 1
        pline = text[prev_start:scan].rstrip('\n')
        raw = pline.strip()
        if not raw or raw.startswith('#'):
            scan = prev_start
            continue
        pindent = _leading_ws(pline)
        if len(pindent) < len(cur_indent):
            if raw.endswith(':'):
                return cur_start, cur_indent
            cur_start = prev_start
            cur_indent = pindent
        scan = prev_start
    return cur_start, cur_indent


def _iso_plan_block(plan, indent):
    if plan['kind'] == 'year':
        return _year_iso_block(
            indent, plan['key'], plan['start_name'], plan['end_name'],
        )
    if plan['kind'] == 'year_or_count':
        return _year_or_count_iso_block(
            indent, plan['year_key'], plan['key'],
            plan['start_name'], plan['end_name'],
        )
    return _rolling_iso_block(
        indent, plan['key'], plan['start_name'], plan['end_name'],
    )


def _iso_assign_line_indexes(head, matches):
    indexes = []
    for match in matches:
        if match is None:
            continue
        indexes.append(head[:match.start()].count('\n'))
    return indexes


def _rolling_iso_block(indent, key, start_name, end_name):
    lines = [
        '%s_end = today' % indent,
        '%s_m = int(%s)' % (indent, key),
        '%s_mi = _end.month - 1 - _m' % indent,
        (
            '%s%s = date(_end.year + _mi // 12, _mi %% 12 + 1, 1)'
            '.strftime(\'%%Y-%%m-%%d\')'
        ) % (indent, start_name),
    ]
    if end_name:
        lines.append(
            '%s%s = _end.strftime(\'%%Y-%%m-%%d\')' % (indent, end_name),
        )
    return '\n'.join(lines) + '\n'


def _year_iso_block(indent, key, start_name, end_name):
    lines = [
        '%s%s = \'%%04d-01-01\' %% int(%s)' % (indent, start_name, key),
    ]
    if end_name:
        lines.append(
            '%s%s = \'%%04d-12-31\' %% int(%s)' % (indent, end_name, key),
        )
    return '\n'.join(lines) + '\n'


def _year_or_count_iso_block(indent, year_key, count_key, start_name, end_name):
    """``year`` if the slash set it, otherwise the months count."""
    inner = indent + '    '
    year_body = _year_iso_block(inner, year_key, start_name, end_name)
    count_body = _rolling_iso_block(inner, count_key, start_name, end_name)
    return '%sif %s:\n%s%selse:\n%s' % (
        indent, year_key, year_body, indent, count_body,
    )


def _replace_iso_windows(head, mapping, schema):
    """Turn a captured ``date_from = '2025-11-01'`` window into the param."""
    plan = _iso_window_plan(head, mapping, schema)
    if not plan:
        return head
    indent = ''
    start_match = plan.get('start_match')
    if start_match is not None:
        indent = start_match.group(1)
    elif plan.get('end_match') is not None:
        indent = plan['end_match'].group(1)
    drop = set(_iso_assign_line_indexes(
        head, (plan.get('start_match'), plan.get('end_match')),
    ))
    lines = head.splitlines(True)
    if drop:
        block = _iso_plan_block(plan, indent)
        out = []
        inserted = False
        for idx, line in enumerate(lines):
            if idx in drop:
                if not inserted:
                    out.append(block)
                    inserted = True
                continue
            out.append(line)
        head = ''.join(out)
    else:
        first = None
        for match in _ISO_STR_RE.finditer(head):
            if match.group(1) not in (plan['start_iso'], plan['end_iso']):
                continue
            if _iso_on_comment_line(head, match.start()):
                continue
            first = match
            break
        if first is None:
            return head
        line_start, indent = _insert_before_statement(head, first.start())
        block = _iso_plan_block(plan, indent)
        head = head[:line_start] + block + head[line_start:]
    if plan['start_iso']:
        head = re.sub(
            r'[\'"]%s[\'"]' % re.escape(plan['start_iso']),
            plan['start_name'],
            head,
        )
    if plan['end_iso'] and plan['end_name']:
        head = re.sub(
            r'[\'"]%s[\'"]' % re.escape(plan['end_iso']),
            plan['end_name'],
            head,
        )
    return head


def _replace_unique_default_literals(code, schema, env=None):
    """Use schema names in the query, titles and date window. Not the HTML."""
    mapping = _unique_int_default_map(schema, env)
    if not code:
        return code or ''
    if (
        not mapping
        and not _year_slot_key({}, schema)
        and not _count_slot_key({}, schema)
    ):
        return code or ''
    head, tail = split_page_html_skill_code(code)
    head_out = []
    for line in head.splitlines(True):
        if _is_title_line(line):
            head_out.append(_replace_title_literals(line, mapping))
        else:
            head_out.append(line)
    head = _replace_iso_windows(''.join(head_out), mapping, schema)
    head = _replace_number_tokens(head, mapping, schema)
    kept = []
    for line in tail.splitlines(True):
        if _is_title_line(line):
            kept.append(_replace_title_literals(line, mapping))
        else:
            kept.append(line)
    return head + ''.join(kept)


def _literal_assigns_remain(code, schema):
    keys = set(schema_keys_that_need_place(schema, code))
    if not keys:
        keys = _schema_key_set(schema)
    if not keys:
        return False
    for line in (code or '').splitlines():
        match = _LITERAL_ASSIGN_RE.match(line)
        if not match or match.group(2) not in keys:
            continue
        if (match.group(3) or '').strip() in ('None', 'True', 'False'):
            continue
        return True
    return False


def _unique_default_literals_remain(code, schema, env=None):
    """True when a default still sits in its slot, title or date window."""
    mapping = _unique_int_default_map(schema, env)
    if not mapping or not code:
        return False
    head, tail = split_page_html_skill_code(code)
    title = ''.join(
        line for line in (head + tail).splitlines(True)
        if _is_title_line(line)
    )
    if _iso_window_plan(head, mapping, schema):
        return True
    for lit, key in mapping.items():
        slot = re.compile(
            r'\b%s\s*=\s*-?%s\b' % (re.escape(key), re.escape(lit)),
        )
        if slot.search(head):
            return True
        if title and re.search(
            r'(?<![0-9-])%s(?![0-9-])' % re.escape(lit),
            title,
        ):
            return True
    return False


def schema_params_need_place(code, schema, env=None):
    """True when a default/required key is unread, overwritten, or still a turn literal."""
    if not schema_keys_that_need_place(schema, code):
        return False
    if schema_keys_unread_by_code(schema, code):
        return True
    if _literal_assigns_remain(code, schema):
        return True
    return _unique_default_literals_remain(code, schema, env)


def split_page_html_skill_code(code):
    """``(query head, page tail)``. Tail starts at ``_page_template`` / ``page_html``."""
    text = code or ''
    match = re.search(r'\n_page_template\s*=', text)
    if match:
        return text[:match.start()].rstrip(), text[match.start():]
    idx = text.find('page_html(')
    if idx < 0:
        return text, ''
    line_start = text.rfind('\n', 0, idx) + 1
    return text[:line_start].rstrip(), text[line_start:]


def query_head_for_param_rewrite(code):
    """Query head plus ``_page_title``. The HTML template stays in the tail."""
    head, tail = split_page_html_skill_code(code)
    titles = []
    rest = []
    for line in tail.splitlines(True):
        if _is_title_line(line) or line.lstrip().startswith('_page_title'):
            titles.append(line)
        else:
            rest.append(line)
    if titles:
        block = ''.join(titles)
        if head:
            head = head.rstrip() + '\n' + block
        else:
            head = block
    return head, ''.join(rest)


_CODE_PARAM_REWRITE_SYSTEM = (
    'Rewrite the skill Python so every parameter WITH A DEFAULT exists in '
    'the Code as a sandbox variable and is used in the query, result title '
    'and _page_title. '
    'Return Python only: no markdown fences, no prose, no JSON. '
    'Keep the same models, searches, metrics and result shape. '
    'Do not add a model, field, or filter that is not already in the Code '
    'or named in the trainer description. '
    'For each of those keys, the Code must read the sandbox global with:\n'
    'try:\n'
    '    name = name\n'
    'except NameError:\n'
    '    name = None\n'
    'Replace the turn hardcoded numbers, ISO dates and title text with '
    'those names. Use preloaded date, today and calendar. Do not import '
    'dateutil. A required key has no fallback in the Code (not `else 12`): '
    'empty shows Help. A key with no Default on the skill form MUST keep '
    'a second-level default in the Code (the turn value). A form Default '
    'already fills the sandbox: do not overwrite it. Parameters with no '
    'default that the Code does not use may be omitted.'
)


def build_code_param_rewrite_prompt(code, schema, trainer_text=''):
    """Short Python call: keys with a default must have a place in the Code."""
    unread = schema_keys_unread_by_code(schema, code)
    parsed = _schema_as_dict(schema)
    needed = schema_keys_that_need_place(schema, code)
    optional = [
        k for k in parsed
        if _is_slash_param_key(k) and k not in needed
    ]
    extra = ''
    if unread:
        extra = ' Keys with a default the Code does not read yet: %s.' % (
            ', '.join(unread),
        )
    elif needed:
        extra = (
            ' Keys that must be used (default or already in the Code), '
            'including in _page_title: %s.' % ', '.join(needed)
        )
    parts = []
    if needed:
        parts.append('Parameters that need a place: %s' % ', '.join(needed))
    if optional:
        parts.append(
            'Parameters with no default, unused — omit them: %s'
            % ', '.join(optional)
        )
    desc = (trainer_text or '').strip()
    if desc:
        parts.append('Trainer description:\n%s' % desc)
    parts.append('Code:\n%s' % (code or ''))
    return _CODE_PARAM_REWRITE_SYSTEM + extra, '\n\n'.join(parts)


def parse_rewritten_skill_code(text):
    """Strip markdown fences; return Python source or empty."""
    s = (text or '').strip()
    if not s:
        return ''
    s = re.sub(r'^```(?:python|py)?\s*\n?', '', s, flags=re.IGNORECASE)
    s = re.sub(r'\n?```\s*$', '', s)
    return s.strip()


def accept_rewritten_code(code, schema):
    """Cleaned Python if it parses and reads every schema key; else empty."""
    cleaned = parse_rewritten_skill_code(code)
    if not cleaned:
        return ''
    try:
        ast.parse(cleaned)
    except SyntaxError:
        return ''
    if schema_keys_unread_by_code(schema, cleaned):
        return ''
    return cleaned
