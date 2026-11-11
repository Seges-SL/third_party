# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""Which Odoo model each row of a relaxaicode result is: stamp, missing ids, record refs."""

import re
from .relaxaicode_rows import (
    _is_technical_model,
    _iter_all_tabular_row_lists,
    _model_id_from_xmlid_row,
    _row_record_id,
    _row_technical_model,
)


def _infer_id_model_map(namespace):
    """Map {id: model} from the live recordsets in the sandbox namespace.

    DETERMINISTIC and AGNOSTIC: it does not guess or hardcode models; it reads the REAL
    model of the recordsets the code created (e.g. ``emps = env['hr.employee'].search``).
    That way the server knows which model each row belongs to without relying on the
    LLM adding ``__model``. Ambiguous ids (same id in two models) are dropped.
    """
    id_model = {}
    ambiguous = set()
    for key, val in (namespace or {}).items():
        if str(key).startswith('_'):
            continue
        model = getattr(val, '_name', None)
        ids = getattr(val, 'ids', None)
        # Odoo recordset: _name (str) + ids (list of int) + _ids marker.
        if (not model or not isinstance(model, str)
                or not isinstance(ids, (list, tuple))
                or not hasattr(val, '_ids')):
            continue
        for rid in ids:
            if not isinstance(rid, int):
                continue
            prev = id_model.get(rid)
            if prev is not None and prev != model:
                ambiguous.add(rid)
            else:
                id_model[rid] = model
    for rid in ambiguous:
        id_model.pop(rid, None)
    return id_model


_ENV_MODEL_RE = re.compile(r"""env\s*\[\s*['"]([a-zA-Z_][a-zA-Z0-9_.]*)['"]\s*\]""")


def _models_from_code(code):
    """Every ``env['x']`` model referenced in the code."""
    if not code or not isinstance(code, str):
        return set()
    return set(_ENV_MODEL_RE.findall(code))


def _related_models_from_code(code, env, base_models):
    """Many2one comodels cited in the code (e.g. product_id → product.product).

    No domain hardcode: reads ``_fields`` of the base model and the field name
    in the source itself. That way a ranking by product from sale lines can
    link to ``product.product`` even if the namespace recordset holds lines.
    """
    extras = set()
    if not env or not code or not base_models:
        return extras
    for model in base_models:
        try:
            if model not in env:
                continue
            Model = env[model]
            fields_map = getattr(Model, '_fields', None) or {}
        except Exception:
            continue
        for fname, field in fields_map.items():
            if getattr(field, 'type', None) != 'many2one':
                continue
            if not re.search(r'\b%s\b' % re.escape(fname), code):
                continue
            comodel = getattr(field, 'comodel_name', None)
            if comodel and isinstance(comodel, str):
                extras.add(comodel)
    return extras


def _norm_label(text):
    return ' '.join(str(text or '').casefold().split())


def _row_cell_values(row):
    """Comparable cell values (no meta): the row's texts and numbers."""
    texts = []
    nums = []
    if not isinstance(row, dict):
        return texts, nums
    for key, val in row.items():
        if str(key).startswith('_') or str(key).lower() in ('id', 'model', '__model'):
            continue
        if val is None or isinstance(val, bool):
            continue
        if isinstance(val, (int, float)):
            nums.append(float(val))
            continue
        text = str(val).strip()
        if len(text) < 2:
            continue
        compact = text.replace('.', '').replace(',', '').replace(' ', '')
        if compact.isdigit():
            try:
                nums.append(float(compact))
            except ValueError:
                pass
            continue
        texts.append(_norm_label(text))
    return texts, nums


def _labels_match(a, b):
    if not a or not b:
        return False
    return a == b or a in b or b in a


def _technical_key_bonus(model, row):
    """Bonus if the technical model name appears in a column key.

    Universal: uses only tokens of ``model`` (e.g. partner_id ↔ res.partner),
    no ES/EN domain dictionaries.
    """
    if not isinstance(row, dict) or not model:
        return 0
    parts = [p for p in str(model).lower().replace('_', '.').split('.') if len(p) >= 3]
    if not parts:
        return 0
    bonus = 0
    for key in row.keys():
        kl = str(key).lower().replace(' ', '_')
        for part in parts:
            if part in kl:
                bonus += 8
                break
    return bonus


# Minimum score to trust the turn memory: a cell has to
# say the record name (100 display_name / 80 name). The column-name
# bonus alone is not enough.
_TURN_MEMORY_MIN_FIT = 80


def _score_record_fit(env, model, rid, row):
    """Record↔row match score (universal formula, no domain hardcode).

    1) display_name / name match some text of the row (strong).
    2) Value overlap: record fields vs cells (medium).
    3) Bonus if a technical model token is in the column name (weak).
    """
    if not env or not model or not rid:
        return -1
    try:
        if model not in env:
            return -1
        rec = env[model].browse(rid)
        if not rec.exists():
            return -1
    except Exception:
        return -1

    texts, nums = _row_cell_values(row)
    score = 0
    dname = _norm_label(rec.display_name or '')
    name = ''
    try:
        if 'name' in rec._fields and isinstance(rec.name, str):
            name = _norm_label(rec.name)
    except Exception:
        name = ''

    for lab in texts:
        if _labels_match(lab, dname):
            score += 100
        elif _labels_match(lab, name):
            score += 80

    # Field↔cell overlap (bounded: do not walk huge catalogs).
    fields_map = getattr(rec, '_fields', None) or {}
    checked = 0
    for fname, field in fields_map.items():
        if checked >= 50:
            break
        if not fname or fname.startswith('_'):
            continue
        ftype = getattr(field, 'type', None)
        if ftype not in (
            'char', 'text', 'html', 'selection',
            'integer', 'float', 'monetary', 'many2one',
        ):
            continue
        if getattr(field, 'store', True) is False and ftype != 'many2one':
            continue
        checked += 1
        try:
            fval = rec[fname]
        except Exception:
            continue
        if fval is None or fval is False:
            continue
        if ftype == 'many2one':
            try:
                rel_name = _norm_label(fval.display_name or '')
            except Exception:
                rel_name = ''
            for lab in texts:
                if _labels_match(lab, rel_name):
                    score += 15
            continue
        if ftype in ('integer', 'float', 'monetary'):
            try:
                fn = float(fval)
            except (TypeError, ValueError):
                continue
            for n in nums:
                if abs(fn - n) < 1e-6:
                    score += 4
            continue
        fs = _norm_label(fval if isinstance(fval, str) else str(fval))
        if len(fs) < 2:
            continue
        for lab in texts:
            if _labels_match(lab, fs):
                score += 12

    score += _technical_key_bonus(model, row)
    return score


def _pick_best_model_fit(env, models, rid, row):
    """Pick the best-matching candidate; strict tie → None (do not guess)."""
    if not models:
        return None
    models = list(models)
    if len(models) == 1:
        return models[0]
    scored = []
    for model in models:
        scored.append((_score_record_fit(env, model, rid, row), model))
    scored.sort(key=lambda item: (-item[0], item[1]))
    best_score, best_model = scored[0]
    if best_score <= 0:
        return None
    if len(scored) > 1 and scored[1][0] == best_score:
        return None
    return best_model


def _model_exists(env, model, rid):
    if not env or not model or not rid:
        return False
    try:
        if model not in env:
            return False
        return bool(env[model].browse(rid).exists())
    except Exception:
        return False


def _resolve_row_model(
    rid, row, id_model_map, candidate_models, env, single_model=None,
    turn_models=None,
):
    """Resolve the model of a row (universal formula).

    1. A single candidate with exists() → that one.
    2. Several → the best match (display_name + value overlap).
    3. No env/candidates: the namespace id→model map or single_model.
    4. Last resort: the model this turn already gave that id, and only if the
       row still says that record's name.
    No domain dictionaries (partner/product/cliente…).
    """
    mapped = (id_model_map or {}).get(rid) if rid else None
    matches = []
    if env and candidate_models:
        for model in candidate_models:
            if _model_exists(env, model, rid):
                matches.append(model)
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        best = _pick_best_model_fit(env, matches, rid, row)
        if best:
            return best
        # Tie or score 0: only accept the namespace map if it also matches.
        if mapped and mapped in matches:
            mapped_score = _score_record_fit(env, mapped, rid, row)
            if mapped_score > 0:
                return mapped
        return None
    if mapped:
        return mapped
    if single_model and env and _model_exists(env, single_model, rid):
        return single_model
    if single_model and not env:
        return single_model
    # Turn memory: the id was already read from the ORM in an earlier step. The
    # row must name that record; an id repeated in another model does not
    # inherit the link.
    remembered = (turn_models or {}).get(rid)
    if remembered:
        if not env:
            return remembered
        if _score_record_fit(env, remembered, rid, row) >= _TURN_MEMORY_MIN_FIT:
            return remembered
    return None


def _turn_memory_models(controller):
    """Ids this turn already placed in a model, as the engine passes them."""
    memory = getattr(controller, 'turn_record_models', None)
    if not isinstance(memory, dict):
        return {}
    out = {}
    for rid, model in memory.items():
        if not model or not isinstance(model, str):
            continue
        try:
            rid = int(rid)
        except (TypeError, ValueError):
            continue
        if rid > 0:
            out[rid] = model
    return out


def _stamp_models(
    result, id_model_map, single_model=None, env=None, candidate_models=None,
    turn_models=None,
):
    """Stamp ``__model`` on the rows of ALL tabular lists.

    Deterministic and agnostic: namespace recordsets, env['x'] models in the code,
    cited many2one comodels, and an ``exists()`` check when there is an env.
    Does not overwrite a technical model already present. A ``model`` column with
    free text (the name of a car) does not count: it is not ``fleet.vehicle``.
    """
    candidates = set(candidate_models or ())
    if single_model:
        candidates.add(single_model)
    if (
        not id_model_map and not single_model and not turn_models
        and not (env and candidates)
    ):
        return

    for rows in _iter_all_tabular_row_lists(result):
        for item in rows:
            if not isinstance(item, dict):
                continue
            declared = _row_technical_model(item, env)
            if declared:
                if not _is_technical_model(item.get('__model'), env):
                    item['__model'] = declared
                continue
            # 0) XMLID in the row → unambiguous model+id (e.g. res.groups).
            if env:
                xm, xid = _model_id_from_xmlid_row(env, item)
                if xm and xid:
                    item['__model'] = xm
                    item['id'] = xid
                    continue
            rid = _row_record_id(item)
            if not rid:
                continue
            model = _resolve_row_model(
                rid, item, id_model_map, candidates, env, single_model=single_model,
                turn_models=turn_models,
            )
            if model:
                item['__model'] = model


def _iter_namespace_recordsets(namespace):
    """Live Odoo recordsets in the sandbox namespace (model, recordset)."""
    for key, val in (namespace or {}).items():
        if str(key).startswith('_'):
            continue
        model = getattr(val, '_name', None)
        ids = getattr(val, 'ids', None)
        if (
            not model or not isinstance(model, str)
            or not isinstance(ids, (list, tuple))
            or not ids
            or not hasattr(val, '_ids')
        ):
            continue
        yield model, val


def _row_string_values(item):
    """Text values of a row (candidate label), longest first."""
    vals = []
    for key, val in (item or {}).items():
        kl = str(key).lower()
        if str(key).startswith('_') or kl in ('id', 'model', '__model'):
            continue
        if isinstance(val, str) and val.strip():
            vals.append(val.strip())
        elif (
            isinstance(val, (list, tuple))
            and len(val) == 2
            and isinstance(val[1], str)
            and val[1].strip()
        ):
            vals.append(val[1].strip())
    vals.sort(key=len, reverse=True)
    return vals


def _build_label_to_record_index(namespace):
    """``label_norm → (model, id)`` only if the label is unique in the namespace."""
    buckets = {}
    for model, rs in _iter_namespace_recordsets(namespace):
        for rec in rs:
            labels = set()
            try:
                dn = rec.display_name
                if isinstance(dn, str) and dn.strip():
                    labels.add(_norm_label(dn))
            except Exception:
                pass
            try:
                if 'name' in rec._fields:
                    nm = rec.name
                    if isinstance(nm, str) and nm.strip():
                        labels.add(_norm_label(nm))
            except Exception:
                pass
            try:
                rn = getattr(rec, '_rec_name', None) or 'name'
                if rn not in ('display_name', 'name') and rn in rec._fields:
                    rv = rec[rn]
                    if isinstance(rv, str) and rv.strip():
                        labels.add(_norm_label(rv))
            except Exception:
                pass
            for lab in labels:
                if len(lab) < 2:
                    continue
                buckets.setdefault(lab, []).append((model, int(rec.id)))
    index = {}
    for lab, refs in buckets.items():
        uniq = list({(m, i) for m, i in refs})
        if len(uniq) == 1:
            index[lab] = uniq[0]
    return index


def _count_tabular_id_coverage(result):
    """(total_dict_rows, rows_without_id)."""
    total = 0
    missing = 0
    for rows in _iter_all_tabular_row_lists(result):
        for item in rows:
            if not isinstance(item, dict):
                continue
            total += 1
            if not _row_record_id(item):
                missing += 1
    return total, missing


def _backfill_missing_record_ids(
    result, namespace, env=None, candidate_models=None, single_model=None,
):
    """Fill in ``id`` (and ``__model``) when the LLM forgot the id in record rows.

    Structural / Principle 0:
    1) Match cell labels with display_name/name/_rec_name of the recordsets
       live in the sandbox (unambiguous matches only).
    2) If a gap remains and there is a single candidate model: exact ``search`` on
       the model's ``_rec_name``.
    Returns how many rows it filled.
    """
    if not isinstance(result, dict):
        return 0
    filled = 0
    index = _build_label_to_record_index(namespace)

    def _apply(item, model, rid):
        nonlocal filled
        item['id'] = int(rid)
        if not _row_technical_model(item, env):
            item['__model'] = model
        filled += 1

    for rows in _iter_all_tabular_row_lists(result):
        for item in rows:
            if not isinstance(item, dict) or _row_record_id(item):
                continue
            for raw in _row_string_values(item):
                lab = _norm_label(raw)
                ref = index.get(lab)
                if ref:
                    _apply(item, ref[0], ref[1])
                    break
            if _row_record_id(item):
                continue
            # Soft unique match (substring) only if a single ref matches.
            hits = []
            for raw in _row_string_values(item):
                lab = _norm_label(raw)
                for key, ref in index.items():
                    if _labels_match(lab, key):
                        hits.append(ref)
            uniq = list({h for h in hits})
            if len(uniq) == 1:
                _apply(item, uniq[0][0], uniq[0][1])

    model = single_model
    if not model and candidate_models and len(set(candidate_models)) == 1:
        model = next(iter(candidate_models))
    if env and model and model in env:
        Model = env[model]
        rec_name = getattr(Model, '_rec_name', None) or 'name'
        if rec_name in Model._fields:
            for rows in _iter_all_tabular_row_lists(result):
                for item in rows:
                    if not isinstance(item, dict) or _row_record_id(item):
                        continue
                    for raw in _row_string_values(item):
                        if len(raw) < 2:
                            continue
                        try:
                            found = Model.search([(rec_name, '=', raw)], limit=2)
                        except Exception:
                            found = Model.browse()
                        if len(found) == 1:
                            _apply(item, model, found.id)
                            break
    return filled


def _collect_record_refs(result, model_hint=None, env=None):
    """Record citation: one document, not a wall of rows.

    If the result already carries ``__records__``, it is kept (stamp of a header).
    If not, tabular ids are harvested and only published when there is a single
    record. Cell links do not depend on this list.
    """
    try:
        from odoo.addons.pns_ai_mcp.utils.record_cite import document_cite_refs
    except Exception:
        from ...utils.record_cite import document_cite_refs
    existing = result.get('__records__')
    if isinstance(existing, list) and existing:
        cited = document_cite_refs(existing, env=env)
        if cited:
            result['__records__'] = cited
        else:
            result.pop('__records__', None)
        return
    refs = []
    seen = set()
    for rows in _iter_all_tabular_row_lists(result):
        for item in rows:
            if not isinstance(item, dict):
                continue
            rid = _row_record_id(item)
            model = _row_technical_model(item, env) or (
                model_hint if _is_technical_model(model_hint, env) else None
            )
            if not rid or not model or not isinstance(model, str):
                continue
            key = (model, rid)
            if key in seen or len(refs) >= 50:
                continue
            seen.add(key)
            try:
                from odoo.addons.pns_ai_mcp.utils.relaxaicode_render import (
                    row_label_for_record,
                )
                name = row_label_for_record(item)
            except Exception:
                name = item.get('display_name') or item.get('name')
                if name is not None and not isinstance(name, str):
                    name = None
            refs.append({
                'model': model,
                'id': rid,
                'name': name if isinstance(name, str) else None,
            })
    cited = document_cite_refs(refs, env=env)
    if cited:
        result['__records__'] = cited
    else:
        result.pop('__records__', None)
