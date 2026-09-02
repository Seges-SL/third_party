# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""MCP tools for relaxaicode."""

import inspect
import json
import logging
import re
import csv
import io
from typing import Optional, Dict, Any, List
from odoo import SUPERUSER_ID
from odoo.http import request
from .validators import (
    ast_error_code,
    AST_SWITCH_TOOL_CODES,
    REPAIRABLE_AST_CODES,
    validate_relaxaicode_source_ast,
)
from .context_builder import build_safe_context
from .mcp_decorators import mcp_tool

_logger = logging.getLogger(__name__)

# ── Topes anti-DoS del resultado (H4). NO frenan la asignación en memoria
# DURANTE el exec (eso lo acota el worker de Odoo vía limit_time_real /
# limit_time_cpu / limit_memory_hard, ver docs/seguridad_dos_cajas.md), pero sí
# evitan que una salida patológica inunde la respuesta SSE, el histórico y los
# logs. Son comprobaciones O(1) (len de lista / len de str), sin serializar todo.
RELAXAICODE_MAX_RESULT_ROWS = 50000      # filas en data/groups
RELAXAICODE_MAX_TEXT_CHARS = 2_000_000   # ~2 MB de texto/HTML por respuesta


# Only these __fmt_type__ values may paint formatted_text into Chatboo.
# - server_side_python: set by maybe_attach_formatted_text (trusted renderer)
# - author_html: set by skill_runtime / platform, never by free LLM sandbox
# - local_*: client-side helpers in main.py
_TRUSTED_FMT_TYPES = frozenset({
    'server_side_python',
    'author_html',
    'local_json',
    'local_raw',
})


def _reject_untrusted_formatted_text(result, *, after_server_render=False):
    from odoo.addons.pns_ai_mcp.utils.untrusted_html_contract import (
        reject_untrusted_formatted_text,
    )
    return reject_untrusted_formatted_text(
        result,
        after_server_render=after_server_render,
    )


def _enforce_result_size_cap(result):
    """Devuelve un mensaje de error si el resultado excede los topes; si no, None.

    Sólo mira longitudes baratas (número de filas y tamaño de textos), nunca
    serializa la estructura completa (evita amplificar el propio DoS).
    """
    if isinstance(result, dict):
        for _key in ('data', 'groups'):
            _val = result.get(_key)
            if isinstance(_val, list) and len(_val) > RELAXAICODE_MAX_RESULT_ROWS:
                return (
                    "Result too large: '%s' has %d rows (max %d). Aggregate, filter "
                    "or paginate the query (e.g. read_group / limit)."
                    % (_key, len(_val), RELAXAICODE_MAX_RESULT_ROWS)
                )
        for _key in ('formatted_text', 'text', 'html'):
            _val = result.get(_key)
            if isinstance(_val, str) and len(_val) > RELAXAICODE_MAX_TEXT_CHARS:
                return (
                    "Result too large: '%s' is %d chars (max %d). Summarize or "
                    "paginate the output." % (_key, len(_val), RELAXAICODE_MAX_TEXT_CHARS)
                )
    elif isinstance(result, str) and len(result) > RELAXAICODE_MAX_TEXT_CHARS:
        return (
            "Result too large: %d chars (max %d). Summarize or paginate the output."
            % (len(result), RELAXAICODE_MAX_TEXT_CHARS)
        )
    return None


def _log_where():
    """Devuelve 'modulo.funcion' del llamador para logs."""
    frame = inspect.currentframe().f_back
    mod = frame.f_globals.get("__name__", "?")
    if "." in mod:
        mod = mod.split(".")[-1]  # tools_relaxaicode en vez de ruta completa
    return f"{mod}.{frame.f_code.co_name}"


_B64_IMG_PREFIXES = ('iVBORw', '/9j/', 'R0lGOD', 'UklGR')
_B64_PLACEHOLDER = '[imagen omitida: devuelve la URL /web/image/<model>/<id>/image_128]'
# Pistas de nombre de campo que indican imagen binaria en Odoo.
_IMG_FIELD_HINTS = ('image', 'avatar', 'logo', 'foto', 'photo', 'picture')
# Nombres de campo de imagen ESTÁNDAR de Odoo. Con model+id conocidos podemos
# servir la imagen desde /web/image/model/id/campo aunque la celda no traiga el
# base64 (el LLM a veces devuelve un booleano/placeholder). Solo estos nombres
# para no arriesgar 404 con alias raros.
_ODOO_IMAGE_FIELD_RE = re.compile(r'^(image|avatar|logo|photo|picture)(_\w+)?$', re.I)


def _is_b64_img(value):
    """True si el valor parece base64 de imagen.
    Acepta str (JSON serializado) y bytes (campo Binary de Odoo tal cual)."""
    if isinstance(value, bytes):
        if len(value) < 256:
            return False
        try:
            head = value.decode('ascii', errors='replace')[:20]
        except Exception:
            return False
        return any(head.startswith(prefix) for prefix in _B64_IMG_PREFIXES)
    if not isinstance(value, str) or len(value) < 256:
        return False
    head = value[2:] if value.startswith(("b'", 'b"')) else value
    return any(head.startswith(prefix) for prefix in _B64_IMG_PREFIXES)


def _sanitize_binary_for_llm(obj):
    """Sustituye blobs base64 de imagen por un placeholder corto para que el
    resultado que viaja al LLM no desborde la ventana de contexto (causa real
    de los fallos "context_length_exceeded"). No muta el original ni toca la
    clave 'formatted_text' (HTML de presentación destinado al usuario)."""

    def _walk(node):
        if isinstance(node, dict):
            return {
                key: (val if key == 'formatted_text' else _walk(val))
                for key, val in node.items()
            }
        if isinstance(node, (list, tuple)):
            return [_walk(val) for val in node]
        if _is_b64_img(node):
            return _B64_PLACEHOLDER
        return node

    return _walk(obj)


def _coerce_record_id(value):
    """Normaliza id de fila a int (acepta str numérico / float entero)."""
    if isinstance(value, bool) or value is None or value is False:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value == int(value):
        return int(value)
    if isinstance(value, str):
        text = value.strip()
        if text.isdigit():
            return int(text)
    return None


def _row_record_id(item):
    """id de fila: acepta ``id`` / ``ID`` (capitalización típica del LLM)."""
    if not isinstance(item, dict):
        return None
    for key in ('id', 'ID', 'Id'):
        rid = _coerce_record_id(item.get(key))
        if rid is not None:
            if item.get('id') != rid:
                item['id'] = rid
            return rid
    return None


_XMLID_RE = re.compile(r'^[a-z0-9_]+\.[a-zA-Z0-9_]+$')


def _model_id_from_xmlid_row(env, row):
    """Si una celda es un XMLID (``module.name``), resuelve modelo+id reales.

    Genérico (ir.model.data / env.ref), no de dominio. Evita fallos de stamp
    cuando el mismo id numérico existe en muchos modelos.
    """
    if not env or not isinstance(row, dict):
        return None, None
    for key, val in row.items():
        if not isinstance(val, str):
            continue
        kl = str(key).lower().replace(' ', '_')
        if kl not in (
            'xml', 'xmlid', 'xml_id', 'external_id', 'xid', 'xml_ids',
        ) and 'xmlid' not in kl and kl != 'xml':
            continue
        xid = val.strip()
        if not _XMLID_RE.match(xid):
            continue
        try:
            rec = env.ref(xid, raise_if_not_found=False)
        except Exception:
            rec = None
        if rec is None:
            continue
        model = getattr(rec, '_name', None)
        rid = getattr(rec, 'id', None)
        if model and isinstance(model, str) and isinstance(rid, int):
            return model, rid
    return None, None


def _is_dict_row_list(value):
    return isinstance(value, list) and value and isinstance(value[0], dict)


def _iter_all_tabular_row_lists(result):
    """Todas las listas de dicts tabulables del resultado (multi-criterio incluido).

    Cubre ``data``/``items``, sobres ``groups``/``sections``/``tables`` y listas
    hermanas (p. ej. by_units + by_amount). Antes solo se miraba la primera lista
    → la 2ª tabla (y a veces ambas si el stamp fallaba) quedaban sin ``__model``.
    """
    seen = set()

    def _yield_list(rows):
        if not _is_dict_row_list(rows):
            return
        marker = id(rows)
        if marker in seen:
            return
        seen.add(marker)
        yield rows

    if isinstance(result, list):
        for rows in _yield_list(result):
            yield rows
        return
    if not isinstance(result, dict):
        return

    for key in ('data', 'items'):
        for rows in _yield_list(result.get(key)):
            yield rows

    for envelope in ('groups', 'sections', 'tables'):
        blocks = result.get(envelope)
        if not isinstance(blocks, list):
            continue
        for block in blocks:
            if not isinstance(block, dict):
                continue
            for key in ('data', 'items', 'rows'):
                emitted = False
                for rows in _yield_list(block.get(key)):
                    yield rows
                    emitted = True
                if emitted:
                    break

    for key, val in result.items():
        if str(key).startswith('_') or key in (
            'data', 'items', 'groups', 'sections', 'tables',
            'content', 'messages', 'tool_calls', 'choices', 'propose_steps',
        ):
            continue
        for rows in _yield_list(val):
            yield rows


def _iter_result_rows(result):
    """Primera lista de dicts (compat). Preferir ``_iter_all_tabular_row_lists``."""
    for rows in _iter_all_tabular_row_lists(result):
        return rows
    return None


def _postprocess_images(result, model_hint=None):
    """Convierte campos binarios (base64) a URLs /web/image/<model>/<id>/<field>."""
    def _process_items(items, model_hint=None):
        if not items or not isinstance(items, list):
            return
        for item in items:
            if not isinstance(item, dict):
                continue
            rec_id = _coerce_record_id(item.get('id'))
            if not rec_id:
                continue
            # NO consumimos __model (antes .pop): lo dejamos en la fila para que
            # el render de tabla pinte el widget de enlace por fila. Como empieza
            # por '_' no aparece como columna de datos ni se exporta.
            model = item.get('__model') or item.get('model') or model_hint
            if not model or not isinstance(model, str):
                continue

            keys_to_process = [
                k for k in list(item.keys())
                if any(hint in k.lower() for hint in _IMG_FIELD_HINTS)
                and not k.startswith('_')
            ]
            for key in keys_to_process:
                val = item[key]
                if val is False or val is None or val == '':
                    continue
                if isinstance(val, str) and (val.startswith('http') or val.startswith('/')):
                    continue
                # Con model+id conocidos servimos la imagen por URL (más ligero que
                # el base64 y robusto): si el valor es base64 O el campo es un campo
                # de imagen estándar de Odoo (aunque el valor sea booleano/placeholder).
                if _is_b64_img(val) or _ODOO_IMAGE_FIELD_RE.match(str(key)):
                    url = '/web/image/%s/%d/%s' % (model, rec_id, key)
                    item[key] = url
                    _logger.debug('_postprocess_images: %s/%d/%s → URL', model, rec_id, key)

    for rows in _iter_all_tabular_row_lists(result):
        _process_items(rows, model_hint=model_hint)


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


def _infer_single_model_from_code(code):
    """Modelo único referenciado como ``env['x']`` en el código, o None.

    AGNÓSTICO: extrae el modelo del PROPIO código (no una lista fija). Solo se usa
    como pista cuando hay EXACTAMENTE un modelo referenciado (caso típico de un
    listado de una entidad, p.ej. comprehensions ``for e in env['hr.employee']...``
    que no dejan el recordset en el namespace). Con varios modelos no adivina.
    """
    models = _models_from_code(code)
    if len(models) == 1:
        return next(iter(models))
    return None


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


def _resolve_row_model(rid, row, id_model_map, candidate_models, env, single_model=None):
    """Resuelve el modelo de una fila (fórmula universal).

    1. Un solo candidato con exists() → ese.
    2. Varios → el de mayor encaje (display_name + solape de valores).
    3. Si no hay env/candidatos: mapa id→model del namespace o single_model.
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
    return None


def _stamp_models(result, id_model_map, single_model=None, env=None, candidate_models=None):
    """Estampa ``__model`` en las filas de TODAS las listas tabulares.

    Determinista y agnóstico: recordsets del namespace, modelos env['x'] del código,
    comodeles many2one citados, y comprobación ``exists()`` cuando hay env.
    No sobrescribe un ``__model``/``model`` ya presente.
    """
    candidates = set(candidate_models or ())
    if single_model:
        candidates.add(single_model)
    if not id_model_map and not single_model and not (env and candidates):
        return

    for rows in _iter_all_tabular_row_lists(result):
        for item in rows:
            if not isinstance(item, dict):
                continue
            if item.get('__model') or item.get('model'):
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
        if not item.get('__model') and not item.get('model'):
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
            model = item.get('__model') or item.get('model') or model_hint
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


def _attempt_syntax_repair(code):
    """
    Intenta reparar errores comunes de sintaxis en el código generado por el LLM.
    Esto es un fallback cuando el LLM genera código con errores menores.
    
    Args:
        code: Código Python con posibles errores de sintaxis
    
    Returns:
        tuple: (repaired_code, was_repaired)
            - repaired_code: Código reparado (o original si no se pudo reparar)
            - was_repaired: True si se realizaron reparaciones
    """
    original_code = code
    was_repaired = False
    
    # Intentar reparar cadenas sin cerrar al final de líneas (error común)
    # Patrón: "texto sin cerrar al final de línea
    lines = code.split('\n')
    repaired_lines = []
    
    # 1. Reparación INTELIGENTE para formatted_text multilínea (antes del procesado línea por línea)
    # Detectar: "formatted_text": "Línea 1
    # Línea 2"
    # Solución: Convertir a "formatted_text": "Línea 1\nLínea 2"
    try:
        # Función auxiliar para escapar newlines dentro del match
        def escape_newlines(match):
            prefix = match.group(1)
            content = match.group(2)
            suffix = match.group(3)
            # Solo si detectamos saltos de línea reales
            if '\n' in content:
                escaped_content = content.replace(chr(10), '\\n')
                return f"{prefix}{escaped_content}{suffix}"
            return match.group(0)

        # Patrón Mejorado: Busca el cierre ANCLADO a la estructura del diccionario
        # Busca: "formatted_text": " ... " seguido de , o }
        # Esto evita detenerse en comillas internas falsas
        # Grupo 1: Key y apertura ("formatted_text": ")
        # Grupo 2: Contenido (Greedy/Non-greedy? Usamos non-greedy pero hasta el anchor)
        # Grupo 3: Cierre y separador (" , o " })
        
        # Estrategia: Buscar hasta la última comilla posible que precede a una coma, llave de cierre O UN PUNTO (para chain methods)
        pattern_anchored = r"(['\"]formatted_text['\"]\s*[:=]\s*['\"])([\s\S]*?)((?<!\\)['\"]\s*(?:,|}|\]|\.))"
        
        def escape_newlines_anchored(match):
            prefix = match.group(1)
            content = match.group(2)
            suffix = match.group(3)
            if '\n' in content:
                # Escape newlines to make it a valid single-line string
                escaped = content.replace('\n', '\\n').replace('\r', '')
                return f"{prefix}{escaped}{suffix}"
            return match.group(0)
 
        code = re.sub(pattern_anchored, escape_newlines_anchored, code)

        # 1b. Misma reparación para footer / pie / footer_md.
        pattern_footer = (
            r"(['\"](?:footer|footer_md|pie)['\"]\s*[:=]\s*['\"])"
            r"([\s\S]*?)"
            r"((?<!\\)['\"]\s*(?:,|}|\]|\.))"
        )
        code2 = re.sub(pattern_footer, escape_newlines_anchored, code)
        if code2 != code:
            code = code2
            was_repaired = True

        # 1b2. 'footer': '<NL>'.join( → 'footer': '\n'.join(
        code2b = re.sub(
            r"(['\"])(footer|footer_md|pie)\1\s*:\s*(['\"])\s*\n\s*\3\.join\s*\(",
            r"\1\2\1: \3\\n\3.join(",
            code,
        )
        if code2b != code:
            code = code2b
            was_repaired = True

        # 1c. footer_lines = [ ... ] con newlines rotos dentro de strings.
        try:
            def repair_footer_list(match):
                prefix, content, suffix = match.group(1), match.group(2), match.group(3)
                if '\n' not in content:
                    return match.group(0)
                escaped = content.replace('\n', '\\n').replace('\r', '')
                escaped = re.sub(r'(,\s*)\\n(\s*["\'\[\]#])', r'\1\n\2', escaped)
                escaped = re.sub(r'(\[\s*)\\n(\s*["\'\[\]#])', r'\1\n\2', escaped)
                escaped = re.sub(r'\\n(\s*\])', r'\n\1', escaped)
                return '%s%s%s' % (prefix, escaped, suffix)

            code3 = re.sub(
                r'(footer_lines\s*=\s*\[)([\s\S]*?)(\])',
                repair_footer_list,
                code,
            )
            if code3 != code:
                code = code3
                was_repaired = True
        except Exception as e:
            _logger.warning(
                '[%s] Error en reparación de footer_lines: %s', _log_where(), e,
            )

        # 1d. 'footer': "… sin cerrar en la misma línea → '' (el render meteo
        # sintetiza Comparativa + pie). Descarta líneas huérfanas del literal.
        try:
            flines = code.split('\n')
            out = []
            skipping = False
            changed = False
            footer_open = re.compile(
                r"""^(\s*)(['\"])footer\2\s*:\s*(['\"])(.*)$"""
            )
            for ln in flines:
                if skipping:
                    st = ln.strip()
                    if st.endswith("',") or st.endswith('",') or st in ("'", '"'):
                        skipping = False
                    elif st.endswith('},') or st == '}':
                        skipping = False
                        out.append(ln)
                    continue
                m = footer_open.match(ln)
                if m:
                    indent, _k, quote, rest = m.groups()
                    # Cerrado en la misma línea: quote … quote
                    closed = re.match(
                        r'^(?:\\.|[^\\])*?' + re.escape(quote) + r'\s*,?\s*$',
                        rest,
                    )
                    if not closed:
                        out.append("%s'footer': ''," % indent)
                        skipping = True
                        changed = True
                        continue
                out.append(ln)
            if changed:
                code = '\n'.join(out)
                was_repaired = True
        except Exception as e:
            _logger.warning(
                '[%s] Error en reparación de footer EOL: %s', _log_where(), e,
            )

        # 2. Reparación ESPECÍFICA para formatted_lines (Listas de strings rotas por newlines)
        # Detectar: formatted_lines = [ ... ] y escapar newlines internos
        try:
            def repair_list_newlines(match):
                prefix = match.group(1)
                content = match.group(2)
                suffix = match.group(3)
                
                # 1. Escapar TODOS los newlines en el contenido
                escaped = content.replace('\n', '\\n').replace('\r', '')
                
                # 2. Restaurar newlines ESTRUCTURALES (los que son parte de la sintaxis de lista)
                # Patrón: Restaurar ",\n" -> , \n
                escaped = re.sub(r'(,\s*)\\n(\s*["\'\[\]#])', r'\1\n\2', escaped)
                # Restaurar "[\n" -> [ \n
                escaped = re.sub(r'(\[\s*)\\n(\s*["\'\[\]#])', r'\1\n\2', escaped)
                # Restaurar "\n]" -> \n ] (final de lista)
                escaped = re.sub(r'\\n(\s*\])', r'\n\1', escaped)

                return f"{prefix}{escaped}{suffix}"

            # Regex para capturar el bloque formatted_lines completo
            # (formatted_lines = [) ... (])
            pattern_list = r'(formatted_lines\s*=\s*\[)([\s\S]*?)(\])'
            code = re.sub(pattern_list, repair_list_newlines, code)
            
            if code != original_code:
                was_repaired = True
        except Exception as e:
            _logger.warning(f"[{_log_where()}] Error en reparación de formatted_lines: {e}")

        # 3. Reparación ESPECÍFICA para line continuations rotos
        # Error: unexpected character after line continuation character
        # Causa: El modelo pone backslash (\) al final de la línea seguido de espacio o nada.
        # Solución: Eliminar backslashes que están al final de la línea si causan error
        try:
            if '\\' in code:
                # Buscar backslash seguido de espacio o nada antes del newline
                # O simplemente eliminar backslashes al final de la linea si no son necesarios
                # Python moderno permite paréntesis para multilínea, los backslashes son riesgosos.
                
                # Cuidado: no romper strings que terminan en backslash (raro)
                
                def remove_broken_line_continuation(match):
                    # match.group(1) es el contenido de la linea antes del backslash
                    return match.group(1) + " " 
                
                # Patrón: Cualquier cosa que no sea backslash, seguido de backslash, espacios opcionales, newline
                # pattern = r'(.*)\\[ \t]*\n'
                # code = re.sub(pattern, remove_broken_line_continuation, code)
                
                # MÉTODO MÁS SEGURO: Si detectamos que falla por esto, limpiamos TODOS los backslashes de fin de linea
                # fuera de strings. (Dificil con regex simple).
                
                # Heurística simple: Reemplazar " \n" o "\n" por " " si parece un statement roto?
                # Mejor: Reemplazar " \ " seguido de newline por nada.
                
                if re.search(r'\\[ \t]*\n', code):
                    # Reemplazar backslash+whitespace+newline por un solo espacio (unir líneas)
                    code = re.sub(r'\\[ \t]*\n', ' ', code)
                    if code != original_code:
                        was_repaired = True

                # Caso especial: Backslash al FINAL DEL ARCHIVO (EOF)
                if code.strip().endswith('\\'):
                    code = code.strip()[:-1]
                    was_repaired = True

        except Exception as e:
            _logger.warning(f"[{_log_where()}] Error en reparación de line continuations: {e}")

    except Exception as e:
        _logger.warning(f"[{_log_where()}] Error intentando reparación regex: {e}")

            
    # 4. Reparación para IMPLICIT RESULT (Falta de asignación result = ...)
    try:
        from ..utils.relaxaicode_recipe import (
            ensure_date_param_coercion,
            ensure_module_result_call,
            strip_self_recursive_shadow_defs,
        )
        code2, shadow_stripped = strip_self_recursive_shadow_defs(code)
        if shadow_stripped:
            code = code2
            was_repaired = True
        code2, ensured = ensure_module_result_call(code)
        if ensured:
            code = code2
            was_repaired = True
        code2, coerced = ensure_date_param_coercion(code)
        if coerced:
            code = code2
            was_repaired = True
    except Exception as e:
        _logger.warning(
            '[%s] Error en ensure_module_result_call: %s', _log_where(), e,
        )

    # 4b. Reuse distance() origin on map_pins_* when origin= was omitted
    try:
        from ..utils.relaxaicode_recipe import (
            inject_map_pins_origin_from_distance,
        )
        code2, injected = inject_map_pins_origin_from_distance(code)
        if injected:
            code = code2
            was_repaired = True
    except Exception as e:
        _logger.warning(
            '[%s] Error en inject_map_pins_origin_from_distance: %s',
            _log_where(), e,
        )

    try:
        # Check basic heuristics: 'result =' missing
        if 'result' not in code or ('=' not in code and '.search' in code):
            # [NUEVO] Detección de uso de previous_result sin asignación a result
            # Si el código usa previous_result pero no asigna result, asumimos que quiere devolver previous_result
            if 'previous_result' in code and 'result =' not in code and 'result=' not in code:
                 code += "\nresult = previous_result"
                 was_repaired = True
            
            # [NUEVO] Detección de formatted_text sin asignación a result
            elif 'formatted_text' in code and 'result =' not in code and 'result=' not in code:
                 # Si 'formatted_text' está asignado a una variable
                 if re.search(r'formatted_text\s*=', code):
                     # Never grant trust to sandbox HTML; force a proper result shape.
                     code += (
                         '\nresult = {"__untrusted_html_preview__": formatted_text, '
                         '"__force_continue__": True, "__hint__": '
                         '"Do not assign bare formatted_text; return '
                         '{\'data\': [rows]} or use propose_safe_operations."}'
                     )
                     was_repaired = True

            else:
                lines_clean = [l for l in code.split('\n') if l.strip() and not l.strip().startswith('#')]
                if lines_clean:
                    last_line = lines_clean[-1]
                    # Si la última línea parece una expresión
                    stripped_line = last_line.strip()
                    should_wrap = False
                    unwrap_print = False
                    
                    if (
                        stripped_line.startswith('env') or 
                        stripped_line.startswith('rec') or 
                        stripped_line.startswith('sorted') or 
                        stripped_line.startswith('system') or
                        stripped_line.startswith('[') or 
                        stripped_line.startswith('{')
                    ):
                        should_wrap = True
                    elif stripped_line.startswith('print(') and stripped_line.endswith(')'):
                        # Special case: print(x) -> result = x
                        should_wrap = True
                        unwrap_print = True
                    
                    if should_wrap:
                        # Find the index of the last non-empty line
                        idx_last = -1
                        current_lines = code.split('\n')
                        for i in range(len(current_lines)-1, -1, -1):
                            if current_lines[i].strip() and not current_lines[i].strip().startswith('#'):
                                idx_last = i
                                break
                        
                        if idx_last != -1:
                            indent = len(current_lines[idx_last]) - len(current_lines[idx_last].lstrip())
                            indent_str = current_lines[idx_last][:indent]
                            content = current_lines[idx_last].lstrip()
                            
                            if unwrap_print:
                                content_inner = content[6:-1] # Remove print( and )
                                current_lines[idx_last] = f"{indent_str}result = {content_inner}"
                            else:
                                current_lines[idx_last] = f"{indent_str}result = {content}"
                            
                            code = '\n'.join(current_lines)
                            was_repaired = True

    except Exception as e:
        _logger.warning(f"[{_log_where()}] Error en reparación de implicit result: {e}")

    # 5. Quitar línea suelta `result` al final (idiosincrasia REPL en snippets de contexto)
    try:
        lines = code.rstrip().split('\n')
        while lines and lines[-1].strip() == 'result':
            lines.pop()
            was_repaired = True
        if was_repaired:
            code = '\n'.join(lines)
            if code and not code.endswith('\n'):
                code += '\n'
    except Exception as e:
        _logger.warning(f"[{_log_where()}] Error eliminando result suelto final: {e}")

    # 6. result.append/extend sin result = [] previo (patrón trial_balance muy frecuente)
    try:
        if re.search(r'\bresult\.(append|extend)\s*\(', code):
            assigns_before_append = False
            out_lines = []
            for line in code.split('\n'):
                stripped = line.strip()
                if stripped and not stripped.startswith('#'):
                    if re.match(r'result\s*(?:\+)?=', stripped):
                        assigns_before_append = True
                    if (
                        re.search(r'\bresult\.(append|extend)\s*\(', line)
                        and not assigns_before_append
                    ):
                        indent = len(line) - len(line.lstrip())
                        indent_str = line[:indent]
                        out_lines.append(f"{indent_str}result = []")
                        assigns_before_append = True
                        was_repaired = True
                out_lines.append(line)
            if was_repaired:
                code = '\n'.join(out_lines)
    except Exception as e:
        _logger.warning(f"[{_log_where()}] Error en reparación result.append sin init: {e}")

    if was_repaired:
        lines = code.split('\n')
    
    for i, line in enumerate(lines):
        repaired_line = line
        
        # Detectar cadenas sin cerrar: línea que termina con comilla simple o doble sin cerrar
        # Pero solo si no es un comentario y tiene una comilla de apertura
        if not line.strip().startswith('#'):
            # Contar comillas simples y dobles
            single_quotes = line.count("'") - line.count("\\'")
            double_quotes = line.count('"') - line.count('\\"')
            
            # Si hay un número impar de comillas, la cadena no está cerrada
            # Intentar cerrarla si la línea termina con texto (no con operador, etc.)
            if (single_quotes % 2 == 1 or double_quotes % 2 == 1) and line.strip():
                # Verificar si la línea parece ser parte de una asignación a result
                if 'result' in line and 'formatted_text' in line:
                    # Si termina con comilla sin cerrar, intentar cerrarla
                    if line.rstrip().endswith('"') and double_quotes % 2 == 1:
                        # Ya tiene comilla al final, pero está mal formada
                        # Podría ser que falta cerrar antes de un salto de línea
                        pass
                    elif not line.rstrip().endswith(('"', "'")):
                        # La línea no termina con comilla, añadirla
                        if double_quotes % 2 == 1:
                            repaired_line = line.rstrip() + '"'
                            was_repaired = True
                        elif single_quotes % 2 == 1:
                            repaired_line = line.rstrip() + "'"
                            was_repaired = True
        
        repaired_lines.append(repaired_line)
    
    if was_repaired:
        repaired_code = '\n'.join(repaired_lines)
        # Validar que el código reparado sea sintácticamente válido
        try:
            import ast
            ast.parse(repaired_code, '<relaxaicode>', 'exec')
            return repaired_code, True
        except SyntaxError:
            _logger.warning(f"[{_log_where()}] Reparación automática falló - código aún inválido")
            return original_code, False
    
    return original_code, False


def _detect_phase(code):
    # Detecta automáticamente si el código es de extracción o presentación.
    # Args:
    #     code: Código Python a analizar
    # Returns:
    #     str: 'extraction' o 'presentation'
    if not code or not isinstance(code, str):
        return 'auto'
    
    code_lower = code.lower()
    
    # Indicadores de fase de presentación
    presentation_indicators = [
        'previous_result',
        'raw_data',
        'format',
        'formatted',
        'present',
        'display',
        'html',
        'csv',
        'excel',
        'pdf',
        'table',
    ]
    
    # Indicadores de fase de extracción
    extraction_indicators = [
        'search(',
        'browse(',
        'read(',
        'mapped(',
        'filtered(',
        'search_count(',
    ]
    
    # Contar indicadores
    presentation_count = sum(1 for indicator in presentation_indicators if indicator in code_lower)
    extraction_count = sum(1 for indicator in extraction_indicators if indicator in code_lower)
    
    # Si hay indicadores de presentación y no hay búsquedas, es presentación
    if presentation_count > 0 and extraction_count == 0:
        return 'presentation'
    
    # Si hay búsquedas y no hay indicadores de presentación, es extracción
    if extraction_count > 0 and presentation_count == 0:
        return 'extraction'
    
    # Por defecto, asumir extracción si hay búsquedas
    if extraction_count > 0:
        return 'extraction'
    
    # Si no hay indicadores claros, dejar que el sistema decida
    return 'auto'


def _log_relaxaicode_execution(
    controller,
    code,
    result_data,
    result_summary,
    operation_type='read',
    agent_llm=None,
    context_data=None,
    phase=None,
    return_mode=None,
):
    """Registra ejecución relaxaicode (éxito o error) vía el controlador."""
    try:
        additional_info = None
        if phase is not None or return_mode is not None:
            additional_info = f"Phase: {phase}, Return: {return_mode}"
        controller._log_mcp_operation(
            operation_type=operation_type,
            tool_name='relaxaicode',
            prompt_data={
                'code': code[:5000] if code and len(code) > 5000 else code,
                'context': context_data,
            },
            result_data=result_data,
            result_summary=result_summary,
            additional_info=additional_info,
            code_to_execute=code,
            agent_llm=agent_llm,
        )
    except Exception as log_err:
        _logger.warning(f"[{_log_where()}] No se pudo registrar log MCP: {log_err}")


def _format_user_facing_response(user_message, *, alert_class='alert-warning'):
    """Terminal Chatboo message — plain human text, no JSON-RPC / error_type."""
    import html

    text = (user_message or '').strip()
    if not text:
        text = 'Something went wrong.'
    escaped = html.escape(text).replace('\n', '<br/>\n')
    formatted = (
        f'<div class="alert {alert_class} mb-0" role="alert">{escaped}</div>'
    )
    return {
        'content': [{'type': 'text', 'text': text}],
        'isError': False,
        '__direct_return__': True,
        '__stop_after_direct__': True,
        '__no_footer__': True,
        '__fmt_type__': 'author_html',
        'formatted_text': formatted,
    }


def _format_error_response(error_code, error_message, additional_data=None, retryable=False):
    # Formatea un error en el formato MCP estándar (content con text JSON).
    # Args:
    #     error_code: Código de error JSON-RPC
    #     error_message: Mensaje de error
    #     additional_data: Diccionario con datos adicionales (opcional)
    #     retryable: True si es un error del código generado por el LLM (validación
    #         AST, error de ejecución, result no asignado...). En ese caso el error
    #         se DEVUELVE al modelo como salida de tool para que se auto-corrija
    #         (no lleva __direct_return__ ni formatted_text, así el motor lo reenvía
    #         al LLM). El bucle ReAct está acotado por MAX_ROUNDS. retryable=False
    #         (por defecto) = error terminal que se muestra directamente al usuario.
    # Returns:
    #     dict: Respuesta de error en formato MCP content
    msg = f"ERROR ({error_code}): {error_message}"
    if additional_data:
        msg += f"\nDetails: {json.dumps(additional_data, indent=2, default=str)}"

    if retryable:
        # Error del código del LLM: volver al modelo para que regenere el código.
        # Sin __direct_return__ ni formatted_text para que el motor NO lo vuelque al
        # usuario y lo reenvíe como resultado de tool (auto-corrección ReAct).
        return {
            'content': [{'type': 'text', 'text': msg}],
            'isError': False,
            '__force_retry__': True,
        }

    # Error terminal: frase humana al chat (sin código JSON-RPC ni "Tipo: …").
    return _format_user_facing_response(error_message)


def _relaxaicode_log_prompt(code, context_data):
    return {
        'code': (code[:5000] if code and len(code) > 5000 else code),
        'context': context_data,
    }


def _keyerror_missing_model_response(model_name, env=None, locale='en_US'):
    """KeyError de modelo: sugerir vecinos del registry (sin contexto de dominio)."""
    from ..utils.model_name_suggest import (
        format_missing_model_hint,
        suggest_model_names,
    )
    available = ()
    try:
        if env is not None:
            available = list(getattr(env, 'registry', None) or env)
    except Exception:
        available = ()
    suggestions = suggest_model_names(model_name, available)
    enhanced_msg = format_missing_model_hint(
        model_name, suggestions, locale=locale or 'en_US',
    )
    details = {
        'error_type': 'KeyError',
        'model_name': model_name,
        'suggested_action': 'use_suggested_model' if suggestions else 'list_registry',
    }
    if suggestions:
        details['suggested_models'] = suggestions
    else:
        details['suggested_action'] = 'consult_contexts'
        details['suggested_contexts'] = [
            'contexts_index_core',
            f'corporative_terms_{locale or "en_US"}',
        ]
    return _format_error_response(
        -32603,
        enhanced_msg,
        details,
        retryable=True,
    )


def _strip_module_literals_or_reject(
    code,
    previous_result,
    context_data,
):
    """Strip pasted module-level datasets or return (code, reject_msg, extracted).

    Returns ``(cleaned_code, None, extracted)`` on success/no-op, or
    ``(code, error_message, {})`` when the paste cannot be recovered.
    *extracted* maps stripped names to recovered Python values when foldable.
    """
    from ..utils.relaxaicode_recipe import (
        bind_stripped_names_from_prior,
        module_level_data_literal_error,
        strip_module_level_data_literals,
    )
    lit_err = module_level_data_literal_error(code)
    if not lit_err:
        return code, None, {}
    cleaned, stripped_names, extracted = strip_module_level_data_literals(code)
    has_prior = bool(previous_result) or bool(
        (context_data or {}).get('previous_result')
        or (context_data or {}).get('raw_data')
    ) or bool(extracted)
    if stripped_names and cleaned is not None:
        preamble = bind_stripped_names_from_prior(stripped_names, extracted)
        candidate = (preamble + '\n\n' + cleaned) if preamble else cleaned
        if not module_level_data_literal_error(candidate):
            return candidate, None, extracted
    msg = lit_err
    if not has_prior:
        msg = (
            lit_err
            + " Pass the prior tool dataset as previous_result "
            "(or reference raw_data) — never paste the rows into code."
        )
    return code, msg, {}


@mcp_tool(
    name='relaxaicode',
    description=(
        '[CRITICAL] Execute Python in Odoo (ORM via env). Use for ALL data/table '
        'queries. Assign "result". A named def is optional; if you use one, call '
        'it: def name(...): …; result = name(...). (def allowed; class forbidden; '
        'return only inside def). Prefer preloaded modules (datetime, date, '
        'timedelta, json, operator, math, re, …). Optional imports ONLY from the '
        'AST whitelist — never os/sys/odoo/subprocess/pickle. Return list-of-dicts '
        'for tables; the server renders HTML. If a value can vary between calls, '
        'pass it as a parameter (same-kind filters → one list, not many positionals).'
    ),
    is_write=True,  # Puede ser escritura según el código
    validate_schema=True,  # Habilitar validación con equema explícito
    input_schema={
        "type": "object",
        "properties": {
            "code": {
                "type": "string",
                "description": (
                    "Python in global scope. Assign the answer to 'result'. "
                    "A named def is optional; if used, call it: "
                    "def name(...): …; result = name(...). "
                    "If a value can vary between calls, pass it as a parameter "
                    "(same-kind filters → one list arg, not many positionals). "
                    "Prefer preloaded modules; imports only from whitelist."
                ),
            },
            "context": {
                "type": "object",
                "description": "Optional dictionary context variables."
            },
            "phase": {
                "type": "string",
                "enum": ["auto", "extraction", "presentation"],
                "description": "Optional phase indicator: 'auto' (detect automatically), 'extraction' (Fase 1: extract data), 'presentation' (Fase 2: format data). Default: 'auto'."
            },
            "previous_result": {
                "type": "object",
                "description": "Optional result from previous execution (for Fase 2: presentation). Will be available as 'previous_result' and 'raw_data' in context."
            },
            "return_mode": {
                "type": "string",
                "enum": ["smart", "direct_to_user", "inspect_result"],
                "description": "Control where the result is sent. 'smart' (default): Use auto-detection (large results -> user). 'direct_to_user': Force direct return to user (avoids LLM overflow, use for Final Answer). 'inspect_result': Force return to LLM (for chaining)."
            },
            "summary": {
                "type": "string",
                "description": "Optional human-readable description of what this data represents (e.g. 'Top 5 Customers by Revenue'). Used as the header for auto-generated tables."
            },
            "format": {
                "type": "string",
                "enum": ["markdown", "csv", "json"],
                "description": "Output format. 'markdown' (default): tables/lists. 'csv': Comma/Semicolon separated values (text). 'json': Pretty-printed JSON string."
            }
        },
        "required": []
    }
)
def tool_relaxaicode(
    controller,
    arguments: dict
):
    # Herramienta MCP: Ejecuta código Python nativo bajo entorno relaxaicode
    # Cursor aislado de la "caja A" (rollback + close en el finally).
    ro_cr = None
    try:
        # Extraer parámetros del diccionario de argumentos
        code = arguments.get('code')
        context = arguments.get('context')
        phase = arguments.get('phase', 'auto')
        return_mode = arguments.get('return_mode', 'smart')

        summary = arguments.get('summary')
        fmt = arguments.get('format')
        if not fmt:
            fmt = 'markdown'  # Enforce default

        previous_result = arguments.get('previous_result')

        # Capture Agent LLM for logging
        agent_llm = None
        try:
            from odoo.http import request
            if request:
                agent_llm = request.httprequest.headers.get('X-Mcp-Agent-Llm')
                if not agent_llm and request.httprequest.headers.get('User-Agent'):
                    agent_llm = request.httprequest.headers.get('User-Agent')
        except RuntimeError:
            # RuntimeError: object is not bound occurs when the request context has been popped
            # which happens during SSE generator execution.
            agent_llm = "Chatboo-Generator"
        except Exception:
            pass
        
        # CRÍTICO: Asegurar que code sea string
        # Puede venir como None, dict, list, etc. desde JSON deserializado incorrectamente
        if code is not None and not isinstance(code, str):
            code = str(code)
        
        # Normalizar contexto recibido (puede ser None)
        context_data = context or {}
        
        # Strip pasted datasets so we never hold a huge rows=[] blob.
        if code and isinstance(code, str):
            code, lit_reject, extracted = _strip_module_literals_or_reject(
                code, previous_result, context_data,
            )
            if lit_reject:
                error_response = _format_error_response(
                    -32602, lit_reject, retryable=True,
                )
                controller._log_mcp_operation(
                    operation_type='read',
                    tool_name='relaxaicode',
                    prompt_data=_relaxaicode_log_prompt(
                        code, context_data,
                    ),
                    result_data=error_response,
                    result_summary='Reject: module_literal',
                    code_to_execute=code,
                    agent_llm=agent_llm,
                )
                return error_response
            if extracted and not previous_result:
                for _v in extracted.values():
                    if isinstance(_v, list):
                        previous_result = {'data': _v}
                        break

        # Validar que code sea string no vacío después de todas las operaciones.
        # Reintentable: el modelo llamó a la tool sin el código; que se autocorrija
        # (bucle ReAct acotado por MAX_ROUNDS) en vez de cortar y volcar al usuario.
        if not code or not isinstance(code, str):
            return _format_error_response(
                -32602,
                "relaxaicode was called with an empty 'code' argument. "
                "Provide the Python code to run in the 'code' parameter (use 'env' "
                "for the ORM and assign the answer to 'result'). Do not call the "
                "tool until the code is ready.",
                retryable=True,
            )

        # Safety net: defs should never carry pasted row snapshots.
        code, lit_reject, extracted = _strip_module_literals_or_reject(
            code, previous_result, context_data,
        )
        if lit_reject:
            error_response = _format_error_response(
                -32602, lit_reject, retryable=True,
            )
            controller._log_mcp_operation(
                operation_type='read',
                tool_name='relaxaicode',
                prompt_data=_relaxaicode_log_prompt(
                    code, context_data,
                ),
                result_data=error_response,
                result_summary='Reject: module_literal',
                code_to_execute=code,
                agent_llm=agent_llm,
            )
            return error_response
        if extracted and not previous_result:
            for _v in extracted.values():
                if isinstance(_v, list):
                    previous_result = {'data': _v}
                    break

        # Anti-pattern: real def + later ``def f(): return f()`` shadow.
        from ..utils.relaxaicode_recipe import (
            ensure_date_param_coercion,
            ensure_module_result_call,
            self_recursive_def_error,
            strip_self_recursive_shadow_defs,
        )
        code, _shadow_stripped = strip_self_recursive_shadow_defs(code)
        if _shadow_stripped:
            _logger.info(
                "[%s] stripped self-recursive shadow def(s): %s",
                _log_where(), ', '.join(_shadow_stripped),
            )
        sole_recur = self_recursive_def_error(code)
        if sole_recur:
            error_response = _format_error_response(
                -32602, sole_recur, retryable=True,
            )
            controller._log_mcp_operation(
                operation_type='read',
                tool_name='relaxaicode',
                prompt_data=_relaxaicode_log_prompt(
                    code, context_data,
                ),
                result_data=error_response,
                result_summary='Reject: self-recursive def',
                code_to_execute=code,
                agent_llm=agent_llm,
            )
            return error_response

        # LLM often sends a complete def + return and forgets result = name(...).
        code, _ensured = ensure_module_result_call(code)
        code, _coerced = ensure_date_param_coercion(code)

        # Normalizar saltos escapados SOLO si el código llega como un blob
        # de una sola línea (artefacto de transporte JSON). Si ya hay newlines
        # reales, NO tocar \\n: destruiría literales válidos como
        # 'footer': '\\n'.join(footer_lines) → AST EOL.
        if code.count('\n') < 2 and '\\n' in code:
            code = code.replace('\\n', '\n')
            code = code.replace('\\t', '\t').replace('\\r', '\r')

        # Reparar join partido en dos líneas (daño de replace ciego o LLM):
        #   'footer': '<NL>'.join(  →  'footer': '\n'.join(
        code = re.sub(
            r"(['\"])(footer|footer_md|pie)\1\s*:\s*(['\"])\s*\n\s*\3\.join\s*\(",
            r"\1\2\1: \3\\n\3.join(",
            code,
        )

        # ============================================================
        # DETECCIÓN TEMPRANA: formatted_text en código (Fase 1)
        # ============================================================
        # Detectar si el código contiene formatted_text ANTES de validar AST
        # Esto es crítico porque formatted_text en Fase 1 causa errores de sintaxis
        if phase == 'extraction' or phase == 'auto':
            # Buscar patrones de formatted_text en el código
            if 'formatted_text' in code and ('result' in code or '=' in code):
                # Verificar si está en una asignación a result (no solo en comentarios)
                # Buscar asignaciones a result que contengan formatted_text
                result_assignments = re.findall(r'result\s*=\s*\{[^}]*formatted_text', code, re.DOTALL)
                
                # EXCEPCIÓN: Permitir si se detectan flags de Fast Path (One-Shot)
                # Si el código tiene formatted_text pero también ready_for_presentation (con o sin __), es válido
                # Regex simple para detectar la presencia de la clave
                is_fast_path = (
                    '__ready_for_presentation__' in code or 
                    'ready_for_presentation' in code or 
                    '__return_direct__' in code or 
                    'return_direct' in code or
                    (return_mode == 'direct_to_user')
                )
                
                if result_assignments and not is_fast_path:
                    pass  # Permitir Fast Path implícito
                    # NO retornamos error, permitimos que continúe
                    # return _format_error_response(...)

        # ============================================================
        # REPAIR SUAVE + VALIDACIÓN AST
        # ============================================================
        # 0) Quitar `in dir()/locals()/globals()/vars()` (sandbox ya inyecta
        #    previous_result/lugar/fecha). Evita rondas improductivas.
        from .validators import (
            repair_cr_dbname, repair_locals_dir_checks, repair_percent_format_strings,
            repair_registry_models, repair_unsafe_sort_keys,
        )
        code, _locals_repaired = repair_locals_dir_checks(code)
        code, _sk_repaired = repair_unsafe_sort_keys(code)
        code, _cr_repaired = repair_cr_dbname(code)
        code, _reg_repaired = repair_registry_models(code)
        code, _pct_repaired = repair_percent_format_strings(code)

        is_valid, validation_error, requires_write = validate_relaxaicode_source_ast(code)

        # Second pass: SyntaxError patch and/or leftover AST rewrites.
        # Gate on the stable ASCII code, never on translated/narrative text.
        should_attempt_repair = (
            not is_valid
            and ast_error_code(validation_error) in REPAIRABLE_AST_CODES
        )

        if should_attempt_repair:
            repaired_code, was_repaired = _attempt_syntax_repair(code)
            repaired_code, locals_fix = repair_locals_dir_checks(repaired_code)
            repaired_code, sk_fix = repair_unsafe_sort_keys(repaired_code)
            repaired_code, cr_fix = repair_cr_dbname(repaired_code)
            repaired_code, reg_fix = repair_registry_models(repaired_code)
            repaired_code, pct_fix = repair_percent_format_strings(repaired_code)
            was_repaired = (
                was_repaired or locals_fix or sk_fix or cr_fix or reg_fix or pct_fix
            )
            if was_repaired:
                # Revalidar el código reparado
                is_valid, validation_error, requires_write = validate_relaxaicode_source_ast(repaired_code)
                if is_valid:
                    code = repaired_code
                else:
                    _logger.warning(f"[{_log_where()}] Reparación no fue suficiente - error persistente: {validation_error[:100]}")
        
        if not is_valid:
            # EOL HINT only for string/syntax issues — not for lambda/sort bans
            # (that noise drowned the actionable fix in R5YZ/VFDP).
            enhanced_error = validation_error or ''
            _ast_code = ast_error_code(enhanced_error)
            _switch_tool = _ast_code in AST_SWITCH_TOOL_CODES
            if (
                not _switch_tool
                and 'formatted_text' in (code or '')
                and (phase == 'extraction' or phase == 'auto')
            ):
                enhanced_error = (
                    '%s. [HINT] If error is "EOL while scanning string literal", '
                    'you likely have unescaped newlines in your "formatted_text". '
                    'Use \\n instead of literal newlines. "formatted_text" IS '
                    'ALLOWED in Phase 1 for Fast Path execution.'
                ) % enhanced_error

            if _switch_tool:
                err_msg = 'AST Validation Error: %s' % enhanced_error
            else:
                err_msg = (
                    'AST Validation Error: %s. [REQUIRED] Generate valid Python '
                    'syntax. [REQUIRED] Assign output to the result variable. '
                    'Follow the relaxaicode coding rules in your system context '
                    '(allowed imports, no network — external HTTP goes through '
                    'propose_safe_operations op=fetch_url, never import '
                    'urllib/requests/http).'
                ) % enhanced_error

            error_response = _format_error_response(
                -32602,
                err_msg,
                {
                    'error_type': 'ValidationError',
                    'validation_error': enhanced_error,
                    'ast_code': _ast_code,
                    'phase': phase,
                },
                retryable=True,
            )
            # Registrar log de error de validación
            controller._log_mcp_operation(
                operation_type='read',
                tool_name='relaxaicode',
                prompt_data=_relaxaicode_log_prompt(
                    code, context_data,
                ),
                result_data=error_response,
                result_summary=f"AST Validation Error: {enhanced_error}",
                additional_info=f"Phase: {phase}, Return: {return_mode}",
                code_to_execute=code,
                agent_llm=agent_llm
            )
            return error_response
        
        # Verificar permisos según el tipo de operación detectada
        operation_type = 'write' if requires_write else 'read'
        has_permission, permission_error = controller._check_mcp_permissions(operation_type)
        if not has_permission:
            # Obtener nombre del usuario de forma segura
            env_read = controller._get_env_for_operation('read')
            user_id = env_read.uid
            
            user_name = "desconocido"
            try:
                user_record = env_read['res.users'].browse(user_id)
                if user_record.exists():
                    user_name = user_record.name or user_record.login or "desconocido"
            except Exception:
                pass
            
            # Mensaje simple igual que en endpoints estáticos
            message = f'Usuario "{user_name}" no tiene permisos de escritura con el servidor MCP. Operación abortada.'
            
            # Cancelar automáticamente todas las verificaciones pendientes de este usuario
            cancelled_count = controller._cancel_pending_verifications_for_user(user_id, f"falta de permisos de escritura (not in group_ai_writer) para relaxaicode")
            
            # Usar formato content para que sea visible en la interfaz de la IA (igual que endpoints estáticos)
            error_response = {
                'content': [
                    {
                        'type': 'text',
                        'text': json.dumps({
                            'error': True,
                            'code': -32000,
                            'message': message,
                            'tool_name': 'relaxaicode',
                            'user_name': user_name,
                            'user_id': user_id,
                            'cancelled_operations': cancelled_count
                        }, indent=2, default=str)
                    }
                ]
            }
            
            _logger.warning(f"[{_log_where()}] Usuario {user_name} (ID: {user_id}) sin permiso de escritura IA (group_ai_writer) - abortando")
            
            # Registrar log de error de permisos
            controller._log_mcp_operation(
                operation_type=operation_type,
                tool_name='relaxaicode',
                prompt_data={'code': code[:5000] if len(code) > 5000 else code, 'context': context_data},
                result_data=error_response,
                result_summary=f"Error de permisos: not in group_ai_writer para relaxaicode",
                additional_info=f"Usuario {user_name} (ID: {user_id}) intentó ejecutar código que requiere escritura sin permisos. Operación abortada inmediatamente."
            )
            
            return error_response
        
        # ============================================================
        # DETECTAR OPERACIONES PELIGROSAS QUE REQUIEREN VERIFICACIÓN
        # ============================================================
        if requires_write:
            # CAJA A: relaxaicode es SOLO LECTURA (se ejecuta sobre cursor READ ONLY).
            # Cualquier escritura se redirige a la caja B declarativa
            # (propose_safe_operations): la IA NO escribe con código.
            return {
                'content': [{'type': 'text', 'text': json.dumps({
                    'success': False,
                    'requires_write': True,
                    'message': (
                        'relaxaicode es SOLO LECTURA. Para crear, modificar, '
                        'duplicar o borrar registros usa la herramienta '
                        'propose_safe_operations con operaciones declarativas (no '
                        'código). No pidas ningún PIN; el usuario confirma en Odoo.'
                    ),
                }, ensure_ascii=False, indent=2, default=str)}]
            }

        # ============================================================
        # DETECTAR FASE SI ES NECESARIO
        # ============================================================
        if phase == 'auto':
            phase = _detect_phase(code)
        
        # ============================================================
        # CONSTRUIR CONTEXTO SEGURO
        # ============================================================
        # Si hay previous_result, pasarlo al contexto para Fase 2
        # CAJA A: cursor aislado; rollback al cerrar (escrituras colaterales no persisten).
        if operation_type == 'read':
            ro_env, ro_cr = controller._get_readonly_env()
            safe_context = build_safe_context(
                controller,
                operation_type,
                previous_result=previous_result,
                env_override=ro_env
            )
        else:
            safe_context = build_safe_context(
                controller,
                operation_type,
                previous_result=previous_result
            )
        
        # Añadir datos del contexto proporcionado por el cliente
        # Según el estándar MCP, los prompts deben ser solicitados explícitamente
        # mediante prompts/list y prompts/get, no inyectarse automáticamente
        # CRÍTICO: Proteger solo variables de infraestructura (env, odoo_version, odoo_series).
        # Las variables de locale (user_lang, pk_*) NO se protegen para permitir la "virtualización" desde context_data.
        protected_vars = {
            'env', 'odoo_version', 'odoo_series', '__builtins__', '__import__'
        }
        
        # Verificar que env está presente ANTES de actualizar
        if 'env' not in safe_context:
            _logger.error(f"[{_log_where()}] CRÍTICO: env no está en safe_context después de build_safe_context")
            return _format_error_response(
                -32603,
                'Internal error: env not available in execution context',
                {'error_type': 'ConfigurationError'}
            )
        
        
        for key, value in context_data.items():
            if key not in protected_vars:
                safe_context[key] = value
            else:
                pass  # Variable protegida, ignorar sobrescritura
        
        # Garantizar variables de locale (cascada: default en_US)
        _user_lang = safe_context.get('user_lang') or 'en_US'
        if not isinstance(_user_lang, str):
            _user_lang = 'en_US'
        safe_context['user_lang'] = _user_lang
        safe_context['userlang'] = _user_lang
        safe_context['lang'] = _user_lang
        safe_context['locale'] = _user_lang
        
        # Verificar que env sigue presente DESPUÉS de actualizar
        if 'env' not in safe_context:
            _logger.error(f"[{_log_where()}] CRÍTICO: env desapareció de safe_context después de update")
            return _format_error_response(
                -32603,
                'Internal error: env lost from execution context',
                {'error_type': 'ConfigurationError'}
            )
        
        
        # ============================================================
        # COMPILAR Y EJECUTAR CÓDIGO
        # ============================================================
        try:
            # Compilar código (Python estándar, sin transformaciones)
            byte_code = compile(code, '<relaxaicode>', 'exec')
        except SyntaxError as e:
            return _format_error_response(
                -32602,
                f'Syntax error in code: {str(e)}',
                {'error_type': 'SyntaxError'},
                retryable=True,
            )
        except Exception as e:
            return _format_error_response(
                -32602,
                f'Compilation error: {str(e)}',
                {'error_type': type(e).__name__},
                retryable=True,
            )
        
        # VALIDACIÓN CRÍTICA: Detectar código preventivo que no usa env o tiene comentarios preventivos
        # Si el código solo asigna un mensaje de error a result sin usar env, es código preventivo
        # También detectar comentarios que sugieren que env no está disponible
        code_stripped = code.strip()
        code_lower = code.lower()
        
        # Detectar mensajes de error directos
        is_preventive_message = (
            code_stripped.startswith('result = "') or 
            code_stripped.startswith("result = '") or
            ('result = "No se puede' in code_stripped) or
            ('result = "Error:' in code_stripped) or
            ('result = "No es posible' in code_stripped)
        ) and 'env' not in code
        
        # Detectar comentarios preventivos que sugieren que env no está disponible
        preventive_comments = [
            "unable to access 'env'",
            "unable to access env",
            "cannot access env",
            "env is not available",
            "env not available",
            "fallback approach",
            "different method",
            "try to get",
            "let's try",
            "since we're",
            "consistently unable",
            "having issues with env"
        ]
        
        has_preventive_comment = any(comment in code_lower for comment in preventive_comments)
        
        # Si tiene comentarios preventivos pero NO usa env directamente, es código preventivo
        is_preventive = is_preventive_message or (has_preventive_comment and 'env[' not in code and 'env.' not in code)
        
        if is_preventive:
            reason = "mensaje de error" if is_preventive_message else "comentarios preventivos que sugieren que env no está disponible"
            _logger.warning(f"[{_log_where()}] Código preventivo detectado ({reason}) - no usa env correctamente")
            # NO ejecutar código preventivo - devolver error específico con mensaje MÁS AGRESIVO
            # CRÍTICO: Marcar con __preventive_code_error__ para que el orchestrator lo maneje de forma especial
            error_response = _format_error_response(
                -32602,
                f'[CRITICAL ERROR] You generated preventive code with {reason} instead of using env. This is WRONG. env EXISTS and is ALWAYS available. You MUST use env directly. DO NOT generate error messages. DO NOT add comments suggesting env is unavailable. DO NOT use try/except for env. USE IT DIRECTLY: employees = env["hr.employee"].search([]). Your generated code was: {code[:200]}...',
                {
                    'error_type': 'PreventiveCodeError',
                    'issue': f'LLM generated code with {reason} instead of using env',
                    'expected': 'Code MUST use env directly: employees = env["hr.employee"].search([]); result = [{"id": e.id, "name": e.name} for e in employees]',
                    'forbidden': 'DO NOT generate: result = "error message..." OR comments suggesting env is unavailable OR try/except blocks for env',
                    'generated': code[:500],
                    'action_required': 'Regenerate code using env directly. env is guaranteed to exist. Remove all preventive comments and error handling.',
                    '__preventive_code_error__': True,  # Marca especial para el orchestrator
                    '__force_retry__': True  # Forzar retry automático
                },
                retryable=True,
            )
            # Añadir marca especial al nivel superior de la respuesta
            error_response['__preventive_code_error__'] = True
            error_response['__force_retry__'] = True
            return error_response
        
        # Fallback final: locale no resuelto (cascada default en_US)
        if 'user_lang' not in safe_context:
            safe_context['user_lang'] = 'en_US'
        if 'userlang' not in safe_context:
            safe_context['userlang'] = safe_context['user_lang']
        if 'lang' not in safe_context:
            safe_context['lang'] = safe_context['user_lang']
        if 'locale' not in safe_context:
            safe_context['locale'] = safe_context['user_lang']

        # Ejecutar código
        try:
            # CRÍTICO: exec() con el mismo diccionario como globals y locals
            # garantiza que las asignaciones se guarden en safe_context
            # Verificar que env es accesible justo antes de exec
            test_env = safe_context.get('env')
            if test_env is None:
                _logger.error(f"[{_log_where()}] CRÍTICO: env es None en safe_context antes de exec")
            
            exec(byte_code, safe_context, safe_context)
        except Exception as exec_error:
            from odoo.exceptions import (
                AccessError, MissingError, UserError, ValidationError,
            )
            from odoo.addons.pns_ai_mcp.utils.skill_errors import friendly_skill_error

            error_msg = str(exec_error)
            error_type = type(exec_error).__name__

            # ACL / business denials are NOT code bugs — do not ReAct-retry;
            # show the (already translated) reason and stop.
            if isinstance(
                exec_error,
                (AccessError, MissingError, UserError, ValidationError),
            ):
                try:
                    _env = controller._get_env_for_operation('read')
                except Exception:
                    _env = getattr(controller, 'env', None)
                user_msg = friendly_skill_error(exec_error, _env)
                _logger.info(
                    "[%s] relaxaicode stopped for user-facing %s: %s",
                    _log_where(), error_type, error_msg[:240],
                )
                error_response = _format_user_facing_response(user_msg)
                _log_relaxaicode_execution(
                    controller, code, error_response,
                    f"{error_type}: {error_msg}",
                    operation_type='read', agent_llm=agent_llm,
                    context_data=context_data,
                    phase=phase, return_mode=return_mode,
                )
                return error_response

            # Log adicional para NameError específicamente
            if error_type == 'NameError' and 'env' in error_msg.lower():
                _logger.warning(f"[{_log_where()}] NameError con 'env' - posible contexto corrupto")

            # RecursionError leftover (e.g. intentional recursion that blew the
            # stack). Point the LLM at the common recipe-shadow mistake.
            if isinstance(exec_error, RecursionError) or error_type == 'RecursionError':
                error_response = _format_error_response(
                    -32603,
                    (
                        'Error executing code: maximum recursion depth exceeded. '
                        'Likely cause: a function redefined to call itself '
                        '(def f(...): return f(...)). Call it with new args: '
                        'result = name(...). If you need a new body, rewrite '
                        'the function once without a self-call wrapper.'
                    ),
                    {'error_type': 'RecursionError'},
                    retryable=True,
                )
                _log_relaxaicode_execution(
                    controller, code, error_response,
                    f"Error executing code: {error_msg}",
                    operation_type='read', agent_llm=agent_llm,
                    context_data=context_data,
                    phase=phase, return_mode=return_mode,
                )
                return error_response

            # TypeError: list/dict sobre field.selection callable (cualquier serie).
            if error_type == 'TypeError':
                from ..utils.field_selection import format_selection_iterable_hint
                sel_hint = format_selection_iterable_hint(error_msg)
                if sel_hint:
                    error_response = _format_error_response(
                        -32603,
                        sel_hint,
                        {'error_type': 'TypeError'},
                        retryable=True,
                    )
                    _log_relaxaicode_execution(
                        controller, code, error_response,
                        f"Error executing code: {error_msg}",
                        operation_type='read', agent_llm=agent_llm,
                        context_data=context_data,
                        phase=phase, return_mode=return_mode,
                    )
                    return error_response

            # KeyError: sugerir modelos del registry (el motor se conoce vía Odoo).
            if error_type == 'KeyError':
                # En Python 3, str(KeyError('x')) es 'x'. No tiene el prefijo "KeyError: "
                model_name = error_msg.strip("'").strip('"')
                if model_name:
                    _locale = safe_context.get(
                        'user_lang', safe_context.get('userlang', 'en_US'),
                    )
                    error_response = _keyerror_missing_model_response(
                        model_name,
                        env=safe_context.get('env'),
                        locale=_locale,
                    )
                    _log_relaxaicode_execution(
                        controller, code, error_response,
                        f"Error executing code: {error_msg}",
                        operation_type='read', agent_llm=agent_llm,
                        context_data=context_data,
                        phase=phase, return_mode=return_mode,
                    )
                    return error_response
            
            # Si hay un error durante exec(), capturarlo y devolverlo
            # CRÍTICO: Si es NameError con 'env', verificar si el código realmente intentó usar env
            if error_type == 'NameError' and 'env' in error_msg.lower():
                # Verificar si el código generado realmente contiene 'env'
                pass  # NameError con env - ya logueado arriba
            
            # Error de ejecución del código del LLM: devolver al modelo para que
            # lo corrija (retryable). El bucle ReAct está acotado por MAX_ROUNDS.
            if (
                error_type == 'ValueError'
                and 'unsupported format character' in (error_msg or '')
            ):
                error_msg = (
                    error_msg
                    + '. [HINT] A literal % in a string used with % formatting '
                    'is not a conversion. Write %% for a percent sign, or use '
                    '.format() / an f-string.'
                )
            error_response = _format_error_response(
                -32603,
                f'Error executing code: {error_msg}',
                {'error_type': error_type},
                retryable=True,
            )
            _log_relaxaicode_execution(
                controller, code, error_response,
                f"Error executing code: {error_msg}",
                operation_type='read', agent_llm=agent_llm,
                context_data=context_data,
                phase=phase, return_mode=return_mode,
            )
            return error_response
        
        # Obtener resultado DESPUÉS de exec() exitoso
        # exec() modifica safe_context directamente
        # Verificar explícitamente si 'result' está en el contexto
        # CRÍTICO: Verificar inmediatamente después de exec() para diagnóstico
        result = None
        if 'result' in safe_context:
            result = safe_context['result']
        elif 'output' in safe_context:
            result = safe_context['output']

        # Normalizar lista de nivel superior (p. ej. el LLM hace result = [{...}, ...])
        # a dict ANTES del procesado de fases. Hasta ahora esta normalización vivía
        # DENTRO del bloque `if isinstance(result, dict)` y por eso NUNCA corría para
        # listas: el listado se devolvía como JSON crudo, el LLM lo re-formateaba en
        # markdown y se perdían imágenes (<img>), formato de moneda/fecha y coloreado
        # por cuartiles. Con la lista envuelta entra al render server-side (Python).
        if isinstance(result, list):
            result = {"data": result}
        elif isinstance(result, str):
            # Bare strings are never a user-facing answer (tables need rows;
            # writes need propose_safe_operations). Keep a preview for the LLM.
            result = {
                '__raw_text__': result[:8000],
                '__force_continue__': True,
                '__hint__': (
                    'String results are not shown to the user. Return '
                    '{\'data\': [row dicts…]} for tables, or use '
                    'propose_safe_operations for creates/writes. Answer in prose.'
                ),
            }

        # Tope anti-DoS de la SALIDA (H4): corta salidas patológicas antes de
        # post-procesarlas/renderizarlas/loguearlas. El gasto de CPU/memoria
        # DURANTE el exec lo acota el worker de Odoo (limit_time_*/limit_memory_*).
        _size_err = _enforce_result_size_cap(result)
        if _size_err:
            error_response = _format_error_response(
                -32603,
                'Error executing code: %s' % _size_err,
                {'error_type': 'ResultTooLarge'},
                retryable=True,
            )
            _log_relaxaicode_execution(
                controller, code, error_response, _size_err,
                operation_type='read', agent_llm=agent_llm,
                context_data=context_data,
                phase=phase, return_mode=return_mode,
            )
            return error_response

        # Contract: free sandbox HTML is never user-facing. Library skills get
        # author_html; server tables stamp server_side_python later.
        # Restyle/pijama amounts and map tip continuity are context rules
        # (system_prompt + geo), not post-exec motor repairs.
        _reject_untrusted_formatted_text(result)

        # ============================================================
        # POST-PROCESAR IMÁGENES: base64 → URL /web/image/
        # ============================================================
        if isinstance(result, dict):
            # Inferir el modelo de cada fila SIN depender de que el LLM ponga
            # __model (frágil): (1) de los recordsets vivos en el namespace del
            # sandbox (id→model real) y (2) como pista, del único modelo
            # referenciado como env['x'] en el código. Así las fotos (URL
            # /web/image) y los enlaces clicables salen de forma determinista.
            _single_model = None
            _env = None
            # Opt-out del usuario ("tabla limpia / sin enlaces"): el LLM pone
            # __row_links__=False (o links=False). Desactiva SOLO los enlaces
            # (columna-widget en la tabla + chips del pie); las miniaturas de
            # imagen siguen porque _stamp_models y _postprocess_images se ejecutan
            # igual (necesitan __model).
            _links_off = (result.get('__row_links__') is False
                          or result.get('links') is False)
            try:
                _id_model_map = _infer_id_model_map(safe_context)
                _code_models = _models_from_code(code)
                _single_model = (
                    next(iter(_code_models)) if len(_code_models) == 1 else None
                )
                _env = safe_context.get('env')
                _candidates = set(_code_models)
                _candidates |= _related_models_from_code(code, _env, _code_models)
                # Antes del stamp: rellenar id omitido por el LLM (enlaces).
                try:
                    _backfill_missing_record_ids(
                        result,
                        safe_context,
                        env=_env,
                        candidate_models=_candidates,
                        single_model=_single_model,
                    )
                except Exception as bf_err:
                    _logger.debug('backfill record ids: %s (no-op)', bf_err)
                _stamp_models(
                    result,
                    _id_model_map,
                    single_model=_single_model,
                    env=_env,
                    candidate_models=_candidates,
                )
                # Solo si hay filas cuya etiqueta encaja con un recordset del
                # sandbox (omisión clara de id). Un índice no vacío por sí solo
                # NO basta: cualquier browse residual + lista de dicts meta
                # (diagnóstico, logs) dispararía falsos positivos.
                if not _links_off:
                    try:
                        _idx = _build_label_to_record_index(safe_context)
                        _total, _missing = _count_tabular_id_coverage(result)
                        _looks_omitted = False
                        if _idx and _total >= 1 and _missing == _total:
                            for _rows in _iter_all_tabular_row_lists(result):
                                for _item in _rows:
                                    if not isinstance(_item, dict):
                                        continue
                                    if _row_record_id(_item):
                                        continue
                                    for _raw in _row_string_values(_item):
                                        if _norm_label(_raw) in _idx:
                                            _looks_omitted = True
                                            break
                                    if _looks_omitted:
                                        break
                                if _looks_omitted:
                                    break
                        if _looks_omitted:
                            error_response = _format_error_response(
                                -32603,
                                (
                                    'Tabular rows are missing record id. When listing '
                                    'Odoo records, EVERY row dict MUST include '
                                    "'id': record.id (and typically name/display_name). "
                                    'Without id the server cannot create form links. '
                                    'Fix the code: build rows from the recordset with id.'
                                ),
                                {
                                    'error_type': 'MissingRecordId',
                                    'rows': _total,
                                    'hint': (
                                        "rows.append({'id': r.id, 'name': r.display_name, ...})"
                                    ),
                                },
                                retryable=True,
                            )
                            _log_relaxaicode_execution(
                                controller, code, error_response,
                                'Missing record id on tabular rows',
                                operation_type='read', agent_llm=agent_llm,
                                context_data=context_data,
                                phase=phase, return_mode=return_mode,
                            )
                            return error_response
                    except Exception as mid_err:
                        _logger.debug('missing-id gate: %s (no-op)', mid_err)
            except Exception as im_err:
                _logger.debug('inferencia de modelo: %s (no-op)', im_err)
            # Refs de registros para enlaces clicables en Chatboo: ANTES de
            # _postprocess_images (que consume __model de las filas). Se omiten en
            # opt-out para no pintar chips del pie cuando el usuario no los quiere.
            if not _links_off:
                try:
                    _collect_record_refs(
                        result, model_hint=_single_model, env=_env,
                    )
                except Exception as rr_err:
                    _logger.debug('_collect_record_refs: %s (no-op)', rr_err)
            try:
                _postprocess_images(result, model_hint=_single_model)
            except Exception as pp_err:
                _logger.debug('_postprocess_images: %s (no-op)', pp_err)

        # ============================================================
        # PROCESAR FLAGS DE DOS FASES Y EJECUTAR FASE 2 AUTOMÁTICAMENTE
        # ============================================================
        # Si el resultado es un dict, procesar flags de dos fases
        if isinstance(result, dict):
            # Detectar si hay datos que necesitan presentación (Fase 2 automática)
            needs_presentation = False
            raw_data = None
            
            # Detectar si es extracción o tiene datos que necesitan formateo
            # MODIFICADO: También activar si return_mode es 'direct_to_user'
            if phase == 'extraction' or result.get('__ready_for_presentation__') or result.get('__extraction_complete__') or return_mode == 'direct_to_user':
                needs_presentation = True
                raw_data = result.get('data', result)
            elif phase == 'auto':
                # Detectar automáticamente si hay datos estructurados que necesitan presentación
                # Buscar listas grandes o estructuras de datos que deberían formatearse
                # Primero buscar en 'data', luego en cualquier campo del resultado
                if 'data' in result and isinstance(result.get('data'), (list, dict)):
                    data_content = result.get('data')
                    if isinstance(data_content, list) and len(data_content) > 10:
                        needs_presentation = True
                        raw_data = {'data': data_content}
                    elif isinstance(data_content, dict):
                        # Buscar listas dentro del dict
                        for key, value in data_content.items():
                            if isinstance(value, list) and len(value) > 10:
                                needs_presentation = True
                                raw_data = result.get('data', result)
                                break
                else:
                    # Buscar listas grandes directamente en el resultado (ej: 'customers', 'employees', etc.)
                    for key, value in result.items():
                        if isinstance(value, list) and len(value) > 10 and not key.startswith('__'):
                            needs_presentation = True
                            raw_data = result
                            break
            
            # FASE 1 (EXTRACCIÓN): NO debe tener formatted_text - solo datos RAW
            # EXCEPCIÓN: Si hay formatted_text, asumimos Fast Path (One-Shot) automáticamente.
            # No exigimos flags explícitos, la presencia de texto formateado es suficiente intención.
            has_formatted_text_in_extraction = result.get('formatted_text') is not None
            is_one_shot_allowed = (
                has_formatted_text_in_extraction or # IMPLÍCITO: Si hay texto, es válido
                result.get('__ready_for_presentation__') or 
                result.get('ready_for_presentation') or
                result.get('__return_direct__') or 
                result.get('return_direct') or
                return_mode == 'direct_to_user'
            )
            
            if has_formatted_text_in_extraction and (phase == 'extraction' or phase == 'auto') and not is_one_shot_allowed:
                _logger.error(f"[{_log_where()}] FASE 1: formatted_text sin flag de finalización")
                return _format_error_response(
                    -32602,
                    'PROTOCOL ERROR: formatted_text found in Phase 1. If you want to return the final answer immediately, you MUST also set "ready_for_presentation": True (or "extraction_complete": True) in your result dictionary. usage: result = {"formatted_text": "...", "ready_for_presentation": True}.',
                    {'error_type': 'PhaseError', 'phase': 'extraction', 'invalid_field': 'formatted_text'},
                    retryable=True,
                )
            
            # Render server-side (Python) cuando hay datos tabulares.
            # (la normalización lista→dict ya se hizo arriba, antes de este bloque)
            from odoo.addons.pns_ai_mcp.utils.relaxaicode_render import (
                maybe_attach_formatted_text,
                render_context_from_env,
            )

            # Locale de la sesión (res.lang), no defaults fijos US/ES.
            render_env = safe_context.get('env')
            try:
                render_ctx = (
                    render_context_from_env(render_env, result=result)
                    if render_env is not None
                    else {
                        'pk_decimal_sep': safe_context.get('pk_decimal_sep', ','),
                        'pk_thousands_sep': safe_context.get('pk_thousands_sep', '.'),
                        'pk_date_format': safe_context.get('pk_date_format', '%d/%m/%Y'),
                        'show_mode': 'show-table',
                    }
                )
            except Exception:
                render_ctx = {
                    'pk_decimal_sep': safe_context.get('pk_decimal_sep', ','),
                    'pk_thousands_sep': safe_context.get('pk_thousands_sep', '.'),
                    'pk_date_format': safe_context.get('pk_date_format', '%d/%m/%Y'),
                    'show_mode': 'show-table',
                }
            maybe_attach_formatted_text(
                result,
                summary=summary,
                render_context=render_ctx,
                force=(
                    return_mode == 'direct_to_user'
                    or bool(result.get('__return_direct__'))
                    or bool(result.get('__ready_for_presentation__'))
                    or bool(result.get('__presentation_complete__'))
                    or bool(result.get('__satisfied__'))
                    or phase == 'presentation'
                ),
            )

            # Si necesita presentación y no está ya completada, SOLICITAR código de formateo al LLM
            # Similar al mecanismo de confirmación de escrituras: solicitar código SIN enviar datos
            if needs_presentation and not result.get('__presentation_complete__') and not result.get('error'):
                if raw_data is None:
                    raw_data = result.get('data', result)
                
                # Marcar como extracción completada
                result['__phase__'] = 'extraction'
                result['__ready_for_presentation__'] = True
                result['__extraction_complete__'] = True
                # Tabla ya renderizada (maybe_attach) con summary → respuesta final.
                # Sin esto el orquestador ocultaba el HTML mid-turn y el LLM
                # describía la tabla en prosa sin mostrarla (Sesame/puntualidad).
                if (
                    result.get('formatted_text')
                    and result.get('summary')
                    and result.get('__fmt_type__') in _TRUSTED_FMT_TYPES
                ):
                    result['__phase__'] = 'presentation'
                    result['__presentation_complete__'] = True
                    result['__satisfied__'] = True
                    result['__return_direct__'] = True

                # Log visible de extracción completada
                data_size = len(str(raw_data))
                if isinstance(raw_data, dict):
                    data_keys = list(raw_data.keys())
                    # Detectar estructura para solicitar formateo apropiado
                    data_structure = {}
                    for key, value in raw_data.items():
                        if isinstance(value, list) and len(value) > 0:
                            if isinstance(value[0], dict):
                                data_structure[key] = {
                                    'type': 'list_of_dicts',
                                    'count': len(value),
                                    'sample_keys': list(value[0].keys())[:5] if value[0] else []
                                }
                            else:
                                data_structure[key] = {
                                    'type': 'list_of_values',
                                    'count': len(value)
                                }
                elif isinstance(raw_data, list):
                    data_keys = [f"lista con {len(raw_data)} elementos"]
                    if len(raw_data) > 0 and isinstance(raw_data[0], dict):
                        data_structure = {
                            'type': 'list_of_dicts',
                            'count': len(raw_data),
                            'sample_keys': list(raw_data[0].keys())[:5] if raw_data[0] else []
                        }
                    else:
                        data_structure = {'type': 'list_of_values', 'count': len(raw_data)}
                else:
                    data_keys = ["datos"]
                    data_structure = {'type': 'unknown'}
                
                _logger.info(f"📊 [FASE 1: EXTRACCIÓN] Completada - Datos extraídos: {len(data_keys)} campos, tamaño: {data_size} chars. Ejecutando Fase 2 (presentación) automáticamente...")
                
            # EJECUTAR AUTOMÁTICAMENTE FASE 2: PRESENTACIÓN -> DESACTIVADO
            # En su lugar, marcamos para retorno directo y dejamos que el cliente renderice el JSON
            if False: # RESERVADO PARA FUTURO RENDERIZADO SERVER-SIDE
                _logger.info(f"✅ [FASE 2 SKIP] Omitiendo generación Markdown pesada. Retornando RAW JSON para renderizado cliente.")
                
                result['__phase__'] = 'presentation'
                result['__presentation_complete__'] = True
                result['__satisfied__'] = True
                # Solo direct return si es masivo (> 5000 chars)
                if len(str(result)) > 5000:
                    result['__return_direct__'] = True
                result['__fmt_type__'] = 'local_raw'

            elif phase == 'presentation':
                # Marcar como presentación completada
                result['__phase__'] = 'presentation'
                result['__presentation_complete__'] = True
                result['__satisfied__'] = True  # IA satisfecha, no necesita más procesamiento
                # MODO RAW: Marcar explícitamente para direct return si tiene formatted_text
                if result.get('formatted_text'):
                    result['__return_direct__'] = True
                    result['__raw_mode__'] = True
                # Log visible de presentación completada con información del resultado
                result_size = len(str(result))
                result_keys = list(result.keys())
                # Contar elementos si es una lista o dict con listas
                item_count = 0
                if 'data' in result and isinstance(result['data'], (list, dict)):
                    if isinstance(result['data'], list):
                        item_count = len(result['data'])
                    elif isinstance(result['data'], dict):
                        # Contar elementos en el primer campo que sea lista
                        for key, value in result['data'].items():
                            if isinstance(value, list):
                                item_count = len(value)
                                break
                _logger.info(f"✅ [FASE 2: PRESENTACIÓN] Completada - Resultado procesado: {len(result_keys)} campos, {item_count} elementos, tamaño: {result_size} chars. IA satisfecha, direct return activado.")
                result['__phase__'] = result.get('__phase__', 'extraction')
                _logger.info(f"📋 [FASE AUTO-DETECTADA] Resultado marcado como listo para presentación (fase: {result.get('__phase__')})")
        
            # ============================================================
            # APLICAR LOGICA FINAL DE ALERT MODE
            # ============================================================
            if return_mode == 'direct_to_user':
                result['__return_direct__'] = True
                _logger.info("🚀 [RETURN_MODE] Forzando direct_return por solicitud explícita (direct_to_user)")
            elif return_mode == 'inspect_result':
                # Model chose LLM-only delivery: strip every chat-dump flag the
                # auto-presentation path may have set. Keep formatted_text/data
                # in the tool JSON for the model (skills hybrid / param gaps).
                for _k in (
                    '__return_direct__',
                    '__direct_return__',
                    '__return_direct_to_user__',
                    '__presentation_complete__',
                    '__satisfied__',
                    '__stop_after_direct__',
                    '__ready_for_presentation__',
                ):
                    result.pop(_k, None)
                if result.get('__phase__') == 'presentation':
                    result['__phase__'] = 'extraction'
                _logger.info(
                    "↩️ [RETURN_MODE] inspect_result — dataset for LLM only"
                )

            # Contract: direct-to-user only with trusted HTML or tabulable rows.
            if isinstance(result, dict) and (
                result.get('__return_direct__')
                or result.get('__direct_return__')
                or return_mode == 'direct_to_user'
            ):
                _reject_untrusted_formatted_text(
                    result,
                    after_server_render=True,
                )
                try:
                    from odoo.addons.pns_ai_mcp.utils.relaxaicode_render import (
                        is_tabulable,
                    )
                    _trusted_ft = (
                        bool(result.get('formatted_text'))
                        and result.get('__fmt_type__') in _TRUSTED_FMT_TYPES
                    )
                    _tabulable = is_tabulable(result, force=True)
                except Exception:
                    _trusted_ft = (
                        bool(result.get('formatted_text'))
                        and result.get('__fmt_type__') in _TRUSTED_FMT_TYPES
                    )
                    _tabulable = False
                if not _trusted_ft and not _tabulable:
                    result.pop('__return_direct__', None)
                    result.pop('__direct_return__', None)
                    result.pop('__return_direct_to_user__', None)
                    result['__force_continue__'] = True
                    result['__hint__'] = (
                        'This result is not user-facing (no tabulable rows / no '
                        'trusted server HTML). Do NOT paste it into chat. Return '
                        '{\'data\': [row dicts…]} for a server table, or use '
                        'propose_safe_operations for writes. Use '
                        'return_mode=inspect_result for probes.'
                    )
                    _logger.info(
                        "🛡️ [CONTRACT] Blocked direct_return without trusted "
                        "HTML or tabulable rows."
                    )
        
        # Si no hay resultado, el código no asignó 'result'
        if result is None:
            context_keys = [k for k in safe_context.keys() if not k.startswith('__')]
            diagnostic_info = {
                'available_variables': context_keys[:20],
                'code_preview': code[:500] if len(code) > 500 else code,
                'code_repr': repr(code),
                'code_type': str(type(code)),
                'has_result_key': 'result' in safe_context,
                'has_output_key': 'output' in safe_context,
                'all_context_keys': list(safe_context.keys())[:30]  # Todas las claves para diagnóstico completo
            }
            # El diagnóstico se devuelve en la respuesta JSON que el cliente MCP recibe
            # Está en content[0].text como JSON serializado
            error_response = _format_error_response(
                -32602,
                '[MANDATORY:RESULT] Code did not assign value to variable "result". [REQUIRED] Include line: result = {...} at end of code.',
                diagnostic_info,
                retryable=True,
            )
            _log_relaxaicode_execution(
                controller, code, error_response,
                'Code did not assign value to variable "result"',
                operation_type='read', agent_llm=agent_llm,
                context_data=context_data,
                phase=phase, return_mode=return_mode,
            )
            return error_response
        
        # Serializar resultado una sola vez
        # El formato MCP requiere que 'text' sea una cadena JSON
        # 1. Recuperar env para uso en lógica posterior
        env = safe_context.get('env')
        
        try:
            result_json = json.dumps(_sanitize_binary_for_llm(result), default=str, ensure_ascii=False, separators=(',', ':'))
        except (TypeError, ValueError) as json_error:
            _logger.error(f"[{_log_where()}] Error serializing result to JSON: {json_error}")
            result_json = json.dumps({"error": "Result could not be serialized", "original_error": str(json_error), "result_type": str(type(result))}, ensure_ascii=False)

        
        # Log result size for debugging
        result_json_bytes = len(result_json.encode('utf-8'))
        if result_json_bytes > 1000:
            _logger.warning(f"[{_log_where()}] Large result JSON: {result_json_bytes} bytes")
        else:
            _logger.debug(f"✅ Result JSON: {result_json_bytes} bytes - {result_json[:200] if len(result_json) > 200 else result_json}")
        
        # Crear respuesta con el JSON serializado en 'text'
        response = {
            'content': [
                {
                    'type': 'text',
                    'text': result_json
                }
            ]
        }
        
        # Registrar log de operación exitosa
        result_summary = f"Execution successful. Result: {str(result)[:200]}" if result else "Execution successful without result"
        controller._log_mcp_operation(
            operation_type=operation_type,
            tool_name='relaxaicode',
            prompt_data=_relaxaicode_log_prompt(
                code, context_data,
            ),
            result_data=response,
            result_summary=result_summary,
            code_to_execute=code
        )

        return response
            
    except NameError as e:
        error_msg = str(e)
        # Typo detection for common pre-loaded variables
        preloaded_vars = {
            'pk_datesep': 'pk_thousands_sep',  # Common confusion
            'odooversion': 'odoo_version'
        }
        
        hint = ""
        for typo, correct in preloaded_vars.items():
            if f"'{typo}' is not defined" in error_msg:
                hint = f" [HINT] You likely meant '{correct}' (with underscore). These variables are pre-loaded in the global scope."
                break
        
        if "'userlang' is not defined" in error_msg:
            hint = " [HINT] 'userlang' should be available (alias of user_lang). If you see this, report it - the locale fallback may need adjustment."
        elif "'context' is not defined" in error_msg:
            hint = " [HINT] The variable 'context' does NOT exist. Use 'env' directly to access Odoo."
        elif "'date' is not defined" in error_msg:
            hint = (
                " [HINT] 'date' is preloaded (datetime.date). Use date.today() / "
                "date(y, m, d), or datetime.date.today(). Do not import."
            )
        elif "'timedelta' is not defined" in error_msg:
            hint = (
                " [HINT] 'timedelta' is preloaded. Use timedelta(days=…) or "
                "datetime.timedelta(…)."
            )
            
        return _format_error_response(
            -32602,
            f"{error_msg}{hint}",
            {'error_type': 'NameError'},
            retryable=True,
        )

    except Exception as e:
        error_msg = str(e)
        error_type = type(e).__name__
        error_data = {'error_type': error_type}
        
        # KeyError: sugerir modelos del registry instalado.
        if error_type == 'KeyError':
            model_name = error_msg.strip("'").strip('"')
            if model_name:
                try:
                    _locale = controller._get_user_locale()
                except Exception:
                    _locale = 'en_US'
                try:
                    _env = controller._get_env_for_operation('read')
                except Exception:
                    _env = None
                return _keyerror_missing_model_response(
                    model_name, env=_env, locale=_locale,
                )
        
        # Add hints for common errors
        if "Non-stored field" in error_msg and "cannot be searched" in error_msg:
             error_msg += " [HINT] You are trying to search on a non-stored field (like 'arch'). Use the stored alternative (like 'arch_db') instead."
        
        # Add hint for Invalid leaf (incorrect field name in domain)
        if "Invalid leaf" in error_msg:
            field_match = re.search(r"Invalid leaf \('([^']+)'", error_msg)
            field_name = field_match.group(1) if field_match else "unknown"
            error_msg += f" [HINT] The field '{field_name}' in your domain filter is likely invalid for this model. Verify correct field names with get_context or ir.model.fields."
        
        # Transacción READ ONLY (caja A): el ORM intentó escribir de forma colateral
        if 'read-only' in error_msg.lower() or error_type == 'ReadOnlySqlTransaction':
            error_msg += (
                ' [HINT] La consulta provocó una escritura colateral (mail, tracking, '
                'método de negocio con efecto secundario). Usa search/read puros; '
                'para cambiar datos usa propose_safe_operations.'
            )

        return _format_error_response(
            -32603,
            f'Error in relaxaicode: {error_msg}',
            error_data,
            retryable=True,
        )

    finally:
        # Cerrar el cursor aislado de la caja A (rollback descarta cualquier escritura colateral).
        if ro_cr is not None:
            try:
                ro_cr.rollback()
            except Exception:
                pass
            try:
                ro_cr.close()
            except Exception:
                pass
