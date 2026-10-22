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
    """Mapa {id: model} a partir de los recordsets vivos en el namespace del sandbox.

    DETERMINISTA y AGNÓSTICO: no adivina ni hardcodea modelos; lee el modelo REAL
    de los recordsets que el código creó (p.ej. ``emps = env['hr.employee'].search``).
    Así el servidor sabe a qué modelo pertenece cada fila sin depender de que el
    LLM añada ``__model``. Los ids ambiguos (mismo id en dos modelos) se descartan.
    """
    id_model = {}
    ambiguous = set()
    for key, val in (namespace or {}).items():
        if str(key).startswith('_'):
            continue
        model = getattr(val, '_name', None)
        ids = getattr(val, 'ids', None)
        # Recordset Odoo: _name (str) + ids (lista de int) + marcador _ids.
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
    """Todos los modelos ``env['x']`` referenciados en el código."""
    if not code or not isinstance(code, str):
        return set()
    return set(_ENV_MODEL_RE.findall(code))


def _related_models_from_code(code, env, base_models):
    """Comodelos de many2one citados en el código (p. ej. product_id → product.product).

    Sin hardcode de dominio: lee ``_fields`` del modelo base y el nombre del campo
    en el propio fuente. Así un ranking por producto desde líneas de venta puede
    enlazar a ``product.product`` aunque el recordset del namespace sea de líneas.
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
    """Valores de celda comparables (sin meta): textos y números de la fila."""
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
    """Bonus si el nombre técnico del modelo aparece en una clave de columna.

    Universal: usa solo tokens de ``model`` (p. ej. partner_id ↔ res.partner),
    sin diccionarios de dominio ES/EN.
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


# Puntuación mínima para creer a la memoria del turno: una celda tiene que
# decir el nombre del registro (100 display_name / 80 name). El bonus por
# nombre de columna solo no basta.
_TURN_MEMORY_MIN_FIT = 80


def _score_record_fit(env, model, rid, row):
    """Puntuación de encaje registro↔fila (fórmula universal, sin hardcode de dominio).

    1) display_name / name coinciden con algún texto de la fila (fuerte).
    2) Solape de valores: campos del registro vs celdas (medio).
    3) Bonus si un token técnico del modelo está en el nombre de columna (débil).
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

    # Solape campo↔celda (acotado: no recorrer catálogos enormes).
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
    """Elige el candidato con mejor encaje; empate estricto → None (no adivinar)."""
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
    """Resuelve el modelo de una fila (fórmula universal).

    1. Un solo candidato con exists() → ese.
    2. Varios → el de mayor encaje (display_name + solape de valores).
    3. Si no hay env/candidatos: mapa id→model del namespace o single_model.
    4. Último recurso: el modelo que este turno ya dio a ese id, y solo si la
       fila sigue diciendo el nombre de ese registro.
    Sin diccionarios de dominio (partner/product/cliente…).
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
        # Empate o score 0: solo aceptar el mapa del namespace si también encaja.
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
    # Memoria del turno: el id ya se leyó del ORM en un paso anterior. Se exige
    # que la fila nombre a ese registro; un id repetido en otro modelo no
    # hereda el enlace.
    remembered = (turn_models or {}).get(rid)
    if remembered:
        if not env:
            return remembered
        if _score_record_fit(env, remembered, rid, row) >= _TURN_MEMORY_MIN_FIT:
            return remembered
    return None


def _turn_memory_models(controller):
    """Ids que este turno ya colocó en un modelo, tal como los pasa el motor."""
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
    """Estampa ``__model`` en las filas de TODAS las listas tabulares.

    Determinista y agnóstico: recordsets del namespace, modelos env['x'] del código,
    comodeles many2one citados, y comprobación ``exists()`` cuando hay env.
    No sobrescribe un modelo técnico ya presente. Una columna ``model`` con
    texto libre (el nombre de un coche) no cuenta: no es ``fleet.vehicle``.
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
            # 0) XMLID en la fila → modelo+id inequívocos (p. ej. res.groups).
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
    """Recordsets Odoo vivos en el namespace del sandbox (modelo, recordset)."""
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
    """Valores textuales de una fila (etiqueta candidata), más largos primero."""
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
    """``label_norm → (model, id)`` solo si la etiqueta es única en el namespace."""
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
    """(total_filas_dict, filas_sin_id)."""
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
    """Rellena ``id`` (y ``__model``) cuando el LLM olvidó el id en filas-registro.

    Estructural / Principio 0:
    1) Emparejar etiquetas de celda con display_name/name/_rec_name de recordsets
       vivos en el sandbox (solo matches inequívocos).
    2) Si queda hueco y hay un único modelo candidato: ``search`` exacto por
       ``_rec_name`` del modelo.
    Devuelve cuántas filas rellenó.
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
            # Soft unique match (substring) solo si un único ref encaja.
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
    """Cita de ficha: un documento, no un mural de filas.

    Si el resultado ya trae ``__records__``, se respeta (stamp de un header).
    Si no, se cosechan ids tabulares y solo se publica cuando hay un único
    registro. Los enlaces de celda no dependen de esta lista.
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
