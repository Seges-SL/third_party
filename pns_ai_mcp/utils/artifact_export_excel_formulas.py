# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""Excel formulas: the footer sums and the columns computed from other columns."""

from __future__ import annotations
import ast
import functools
import io
import json
import re
import zipfile

from .artifact_export_table import (
    _excel_number,
    _xlsx_col_letter,
)


# xlsx-only: declared templates. Placeholders ``{public column key}`` +
# ``+ - * / ( )`` and numbers. The key is the sheet column (spaces and
# punctuation allowed); outside braces stay arithmetic. Invalid → value.
_EXCEL_FORMULA_KEY_RE = re.compile(r'\{([^{}]+)\}')


_EXCEL_FORMULA_REST_RE = re.compile(r'^[0-9.+\-*/()\s]*$')


_EXCEL_COMPILED_FORMULA_RE = re.compile(
    r'^=(?:[A-Z]{1,3}[1-9][0-9]*|\d+(?:\.\d+)?|[+\-*/()])+$'
)


def _formula_placeholders(template):
    return [
        key.strip()
        for key in _EXCEL_FORMULA_KEY_RE.findall(template or '')
        if key.strip()
    ]


def formula_template_ok(template):
    """True when *template* is ``{key}`` arithmetic (optional leading ``=``)."""
    text = (template or '').strip()
    if text.startswith('='):
        text = text[1:].strip()
    if not text:
        return False
    if not _formula_placeholders(text):
        return False
    stripped = _EXCEL_FORMULA_KEY_RE.sub('0', text)
    return bool(_EXCEL_FORMULA_REST_RE.match(stripped))


def excel_formulas_from_mapping(raw):
    """Sanitize a column→template map. Skip invalid templates."""
    if raw is None:
        return {}
    if isinstance(raw, str):
        text = raw.strip()
        if not text:
            return {}
        try:
            raw = json.loads(text)
        except (TypeError, ValueError):
            return {}
    if not isinstance(raw, dict):
        return {}
    out = {}
    for key, tmpl in raw.items():
        name = str(key or '').strip()
        if not name or name.startswith('_') or not isinstance(tmpl, str):
            continue
        text = tmpl.strip()
        if not formula_template_ok(text):
            continue
        refs = _formula_placeholders(
            text[1:].strip() if text.startswith('=') else text
        )
        if name in refs:
            continue
        out[name] = text if text.startswith('=') else ('=' + text)
    return out


def excel_formulas_from_payload(payload):
    """``__excel_formulas__`` on a skill result (clip may copy ``excel_formulas``)."""
    if not isinstance(payload, dict):
        return {}
    raw = payload.get('__excel_formulas__')
    if raw is None:
        raw = payload.get('excel_formulas')
    return excel_formulas_from_mapping(raw)


def excel_formulas_from_section(spec):
    """Icon / sheet envelope: ``formulas`` / ``excel_formulas`` / dunder."""
    if not isinstance(spec, dict):
        return {}
    for key in ('__excel_formulas__', 'excel_formulas', 'formulas'):
        if spec.get(key) is not None:
            return excel_formulas_from_mapping(spec.get(key))
    return {}


def compile_excel_formula(template, keys, excel_row, col0=1, target_key=None):
    """``={a}-{b}`` + keys ``[a, b]`` + row 2 → ``=A2-B2``. Else None."""
    if not formula_template_ok(template):
        return None
    try:
        excel_row = int(excel_row)
        col0 = int(col0)
    except (TypeError, ValueError):
        return None
    if excel_row < 1 or col0 < 1:
        return None
    text = (template or '').strip()
    if text.startswith('='):
        text = text[1:].strip()
    refs = _formula_placeholders(text)
    if target_key is not None and str(target_key) in refs:
        return None
    index = {str(k): i for i, k in enumerate(keys or [])}
    for ref in refs:
        if ref not in index:
            return None

    def _repl(match):
        letter = _xlsx_col_letter(col0 + index[match.group(1).strip()])
        return '%s%d' % (letter, excel_row)

    compiled = '=' + _EXCEL_FORMULA_KEY_RE.sub(_repl, text)
    compiled = ''.join(compiled.split())
    if not _EXCEL_COMPILED_FORMULA_RE.match(compiled):
        return None
    return compiled


def _xlsx_is_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)


# ── Formulas read from the numbers ─────────────────────────────────────────
# The rows are the truth. A column that is the same arithmetic of columns to
# its left on every row, a subtotal row that is the sum of its block, and a
# last row that is the sum of everything above become live formulas. Each
# cell keeps its value: the formula is written only when it gives that value.

_INFER_MIN_ROWS = 3


_INFER_MAX_COLS = 40


_INFER_MAX_DECIMALS = 6


_FOOTER_FLAGS = ('_tfoot', '_tsub')


def _is_footer(row):
    return isinstance(row, dict) and any(row.get(f) for f in _FOOTER_FLAGS)


def _decimals_of(value):
    if not isinstance(value, float):
        return 0
    text = repr(value)
    if 'e' in text or 'E' in text or '.' not in text:
        return _INFER_MAX_DECIMALS
    return min(len(text.split('.', 1)[1].rstrip('0')), _INFER_MAX_DECIMALS)


def _column_tolerance(values):
    """Half a unit of the finest decimal the column shows."""
    places = max([_decimals_of(v) for v in values] or [0])
    return 0.5 * (10 ** -places)


def _matches(expected, actual, tol):
    if expected is None or actual is None:
        return False
    return abs(expected - actual) <= tol + 1e-9 * max(1.0, abs(actual))


def _numeric_keys(rows, keys):
    out = []
    for key in keys:
        values = [_excel_number(r.get(key)) for r in rows]
        if any(v is not None for v in values):
            out.append(key)
    return out[:_INFER_MAX_COLS]


def _formula_candidates(left):
    """``(template, operand keys)`` over columns left of the target."""
    out = []
    for i, a in enumerate(left):
        for j, b in enumerate(left):
            if a == b:
                continue
            if i < j:
                out.append(('={%s}+{%s}' % (a, b), (a, b)))
                out.append(('={%s}*{%s}' % (a, b), (a, b)))
            out.append(('={%s}-{%s}' % (a, b), (a, b)))
            out.append(('={%s}/{%s}' % (a, b), (a, b)))
            out.append(('={%s}/{%s}*100' % (a, b), (a, b)))
    return out


def _run_candidates(keys, numeric, target):
    """Sums of 3+ adjacent numeric columns left of *target*."""
    numeric = set(numeric)
    pos = keys.index(target)
    out = []
    start = 0
    while start < pos:
        if keys[start] not in numeric:
            start += 1
            continue
        end = start
        while end < pos and keys[end] in numeric:
            end += 1
        block = keys[start:end]
        for i in range(len(block)):
            for j in range(i + 3, len(block) + 1):
                run = block[i:j]
                out.append(('=' + '+'.join('{%s}' % k for k in run), tuple(run)))
        start = end
    return out


@functools.lru_cache(maxsize=4096)
def _arith_program(template):
    """``(tree, {name: key})`` for a ``{key}`` template, or None."""
    text = (template or '').strip()
    if text.startswith('='):
        text = text[1:]
    names = {}

    def _name(match):
        name = '_v%d' % len(names)
        names[name] = match.group(1).strip()
        return name

    try:
        tree = ast.parse(_EXCEL_FORMULA_KEY_RE.sub(_name, text), mode='eval')
    except SyntaxError:
        return None
    return tree.body, names


def _eval_arith(template, values):
    """Value of a ``{key}`` arithmetic template, or None."""
    program = _arith_program(template)
    if not program:
        return None
    tree, names = program
    env = {}
    for name, key in names.items():
        number = _excel_number(values.get(key))
        if number is None:
            return None
        env[name] = float(number)
    return _eval_node(tree, env)


def _eval_node(node, env):
    if isinstance(node, ast.Name):
        return env.get(node.id)
    # Num on 3.7, Constant from 3.8; by name, so neither touches the other's API.
    kind = type(node).__name__
    if kind in ('Constant', 'Num'):
        value = node.value if kind == 'Constant' else node.n
        return float(value) if _xlsx_is_number(value) else None
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
        inner = _eval_node(node.operand, env)
        if inner is None:
            return None
        return -inner if isinstance(node.op, ast.USub) else inner
    if isinstance(node, ast.BinOp):
        left = _eval_node(node.left, env)
        right = _eval_node(node.right, env)
        if left is None or right is None:
            return None
        if isinstance(node.op, ast.Add):
            return left + right
        if isinstance(node.op, ast.Sub):
            return left - right
        if isinstance(node.op, ast.Mult):
            return left * right
        if isinstance(node.op, ast.Div):
            return left / right if right else None
    return None


def _candidate_holds(rows, target, template, operands, tol):
    hits = 0
    for row in rows:
        actual = _excel_number(row.get(target))
        if actual is None:
            continue
        values = {}
        for key in operands:
            number = _excel_number(row.get(key))
            if number is None:
                return False
            values[key] = number
        if not _matches(_eval_arith(template, values), actual, tol):
            return False
        if actual:
            hits += 1
    return hits >= _INFER_MIN_ROWS


def _duplicates_a_column(rows, target, others, tol):
    targets = [(r, _excel_number(r.get(target))) for r in rows]
    targets = [(r, t) for r, t in targets if t is not None]
    if not targets:
        return False
    for other in others:
        if all(_matches(_excel_number(r.get(other)), t, tol) for r, t in targets):
            return True
    return False


def infer_excel_formulas(rows, keys, declared=None):
    """Column → ``{key}`` template read from the numbers of the data rows.

    Operands sit left of the target, so formulas never loop. A column with
    two different explanations, or fewer than three non-zero rows, keeps its
    values. *declared* columns are left alone.
    """
    declared = declared or {}
    data = [r for r in (rows or []) if isinstance(r, dict) and not _is_footer(r)]
    keys = list(keys or [])
    numeric = _numeric_keys(data, keys)
    out = {}
    for target in numeric:
        if target in declared:
            continue
        values = [_excel_number(r.get(target)) for r in data]
        values = [v for v in values if v is not None]
        if len([v for v in values if v]) < _INFER_MIN_ROWS:
            continue
        tol = _column_tolerance(values)
        left = [k for k in numeric if keys.index(k) < keys.index(target)]
        if not left or _duplicates_a_column(data, target, left, tol):
            continue
        found = [
            template
            for template, operands in (
                _formula_candidates(left) + _run_candidates(keys, numeric, target)
            )
            if _candidate_holds(data, target, template, operands, tol)
        ]
        if len(found) == 1:
            out[target] = found[0]
    return out


def _sums_new():
    """Running column sums of a block of rows: ``[row count, {key: (sum, n)}]``."""
    return [0, {}]


def _sums_copy(sums):
    return [sums[0], dict(sums[1])]


def _sums_add(sums, row, numeric):
    sums[0] += 1
    for key in numeric:
        number = _excel_number(row.get(key))
        if number is not None:
            total, count = sums[1].get(key, (0.0, 0))
            sums[1][key] = (total + number, count + 1)


def _is_sum_row(row, sums, numeric, tols):
    """Keys where *row* equals the block sum, when they outnumber the rest."""
    if sums[0] < 2:
        return None
    hit, miss, nonzero = [], [], False
    for key in numeric:
        actual = _excel_number(row.get(key))
        if actual is None:
            continue
        total, count = sums[1].get(key, (0.0, 0))
        if count and _matches(total, actual, tols[key]):
            hit.append(key)
            nonzero = nonzero or bool(actual)
        else:
            miss.append(key)
    if hit and nonzero and len(hit) > len(miss):
        return hit
    return None


def infer_footer_rows(rows, keys):
    """Mark subtotal rows ``_tsub`` and a grand total ``_tfoot`` from the numbers.

    Subtotals count only when the whole list agrees: a grand total that sums
    the data rows, or two or more subtotals with the list ending on one.
    Rows the skill already flagged are left as they are.
    """
    rows = [r for r in (rows or []) if isinstance(r, dict)]
    if len(rows) < 3 or any(_is_footer(r) for r in rows):
        return
    numeric = _numeric_keys(rows, keys)
    if not numeric:
        return
    tols = {
        k: _column_tolerance([_excel_number(r.get(k)) for r in rows])
        for k in numeric
    }
    found = _footer_layout(
        rows, numeric, tols, 0, _sums_new(), _sums_new(), [],
        [_FOOTER_MAX_BRANCHES],
    )
    if not found:
        return
    subs, total = found
    for row, hit in subs:
        row['_tsub'] = True
        row['_tsum'] = hit
    if total:
        rows[-1]['_tfoot'] = True
        rows[-1]['_tsum'] = total


_FOOTER_MAX_BRANCHES = 200


def _footer_layout(rows, numeric, tols, start, block, data, subs, budget):
    """First layout where every subtotal and the grand total add up.

    A row that could be a subtotal is tried as data first, so the plainest
    reading wins and a row that only happens to add up stays data.
    """
    block = _sums_copy(block)
    data = _sums_copy(data)
    last = len(rows) - 1
    for i in range(start, len(rows)):
        row = rows[i]
        if i == last:
            total = _is_sum_row(row, data, numeric, tols)
            if total:
                return subs, total
        hit = _is_sum_row(row, block, numeric, tols)
        if hit:
            budget[0] -= 1
            if budget[0] < 0:
                return None
            if i < last:
                as_data = (_sums_copy(block), _sums_copy(data))
                _sums_add(as_data[0], row, numeric)
                _sums_add(as_data[1], row, numeric)
                found = _footer_layout(
                    rows, numeric, tols, i + 1,
                    as_data[0], as_data[1], subs, budget,
                )
                if found:
                    return found
            with_sub = subs + [(row, hit)]
            if i == last:
                return (with_sub, None) if len(with_sub) >= 2 else None
            return _footer_layout(
                rows, numeric, tols, i + 1, _sums_new(), data, with_sub, budget,
            )
        _sums_add(block, row, numeric)
        _sums_add(data, row, numeric)
    return None


def _plan_xlsx_cells(spec):
    """``{(excel_row, col): (formula, cached)}`` for every live cell of a sheet."""
    keys = spec['keys']
    rows = spec['rows']
    header_row = 2 if spec.get('caption') else 1
    declared = spec.get('formulas') or {}
    inferred = infer_excel_formulas(rows, keys, declared)
    formulas = dict(inferred)
    formulas.update(declared)
    nested = any(isinstance(r, dict) and r.get('_tsub') for r in rows)
    first = header_row + 1
    plan = {}
    block_start = first
    for offset, row in enumerate(rows):
        ridx = first + offset
        if not isinstance(row, dict):
            continue
        cached = {}
        for col, key in enumerate(keys, 1):
            template = formulas.get(key)
            compiled = compile_excel_formula(
                template, keys, ridx, target_key=key,
            ) if template else None
            if compiled:
                operands = (_arith_program(template) or (None, {}))[1].values()
                values = {
                    k: cached.get(k, _excel_number(row.get(k))) for k in operands
                }
                result = _eval_arith(template, values)
                actual = _excel_number(row.get(key))
                if key in declared:
                    value = result if result is not None else actual
                elif _matches(result, actual, _column_tolerance([actual])):
                    value = result
                else:
                    compiled = None
                if compiled:
                    plan[(ridx, col)] = (compiled, value)
                    if value is not None:
                        cached[key] = value
                    continue
            footer = _xlsx_footer_formula(
                rows, row, key, col, ridx, first, block_start, nested,
            )
            if footer:
                plan[(ridx, col)] = footer
                cached[key] = footer[1]
        if row.get('_tsub'):
            block_start = ridx + 1
    return plan


def _xlsx_footer_formula(rows, row, key, col, ridx, first, block_start, nested):
    """``SUM`` / ``SUBTOTAL(9, …)`` for a footer cell that equals it, else None."""
    if not _is_footer(row):
        return None
    actual = _excel_number(row.get(key))
    if actual is None:
        return None
    sums = row.get('_tsum')
    if sums is not None and key not in sums:
        return None
    top = block_start if row.get('_tsub') else first
    if ridx - 1 < top:
        return None
    above = rows[top - first:ridx - first]
    numbers = [
        _excel_number(r.get(key)) for r in above
        if isinstance(r, dict) and not (nested and r.get('_tsub'))
    ]
    numbers = [n for n in numbers if n is not None]
    if not numbers:
        return None
    total = float(sum(numbers))
    if not _matches(total, actual, _column_tolerance([actual])):
        return None
    letter = _xlsx_col_letter(col)
    span = '%s%d:%s%d' % (letter, top, letter, ridx - 1)
    if nested:
        return '=SUBTOTAL(9,%s)' % span, total
    return '=SUM(%s)' % span, total


_XLSX_EMPTY_CACHE_RE = re.compile(
    r'<c r="([A-Z]{1,3}[0-9]+)"([^>]*)><f>([^<]*)</f><v\s*/?>(?:</v>)?</c>'
)


def _xlsx_fill_cached(raw, specs):
    """Write the planned result into each formula cell an openpyxl book left empty."""
    if not raw:
        return raw
    try:
        src = zipfile.ZipFile(io.BytesIO(raw))
    except zipfile.BadZipFile:
        return raw
    out = io.BytesIO()
    with src, zipfile.ZipFile(out, 'w', compression=zipfile.ZIP_DEFLATED) as dst:
        for info in src.infolist():
            data = src.read(info.filename)
            match = re.match(r'xl/worksheets/sheet(\d+)\.xml$', info.filename)
            if match and int(match.group(1)) <= len(specs):
                plan = specs[int(match.group(1)) - 1].get('cells') or {}
                by_ref = {
                    '%s%d' % (_xlsx_col_letter(col), r): value
                    for (r, col), (_f, value) in plan.items()
                }
                data = _XLSX_EMPTY_CACHE_RE.sub(
                    lambda m: _xlsx_cached_cell(m, by_ref), data.decode('utf-8'),
                ).encode('utf-8')
            dst.writestr(info, data)
    return out.getvalue()


def _xlsx_cached_cell(match, by_ref):
    number = _excel_number(by_ref.get(match.group(1)))
    if number is None:
        return match.group(0)
    return '<c r="%s"%s><f>%s</f><v>%s</v></c>' % (
        match.group(1), match.group(2), match.group(3), repr(float(number)),
    )
