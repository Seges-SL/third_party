# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""Rows of a relaxaicode result: record ids, technical models and pictures."""

import logging
import re

_logger = logging.getLogger(__name__)


_B64_IMG_PREFIXES = ('iVBORw', '/9j/', 'R0lGOD', 'UklGR')
_B64_PLACEHOLDER = '[image omitted: return the URL /web/image/<model>/<id>/image_128]'


# Nombres de campo de imagen ESTÁNDAR de Odoo. Con model+id conocidos podemos
# servir la imagen desde /web/image/model/id/campo aunque la celda no traiga el
# base64 (el LLM a veces devuelve un booleano/placeholder). Solo estos nombres
# para no arriesgar 404 con alias raros.
_ODOO_IMAGE_FIELD_RE = re.compile(r'^(image|avatar|logo|photo|picture)(_\w+)?$', re.I)


# Nombre técnico de modelo Odoo (res.partner). Un texto con espacios o mayúsculas
# es una etiqueta de negocio (el modelo del coche), no el modelo del registro.
_TECHNICAL_MODEL_RE = re.compile(r'^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)+$')


def _is_technical_model(name, env=None):
    """True si *name* es un modelo del registro (``fleet.vehicle``), no una etiqueta."""
    if not isinstance(name, str) or not _TECHNICAL_MODEL_RE.match(name):
        return False
    if env is None:
        return True
    try:
        return name in env
    except Exception:
        return False


def _row_technical_model(item, env=None):
    """Modelo técnico ya escrito en la fila (``__model`` o columna ``model``)."""
    if not isinstance(item, dict):
        return None
    for key in ('__model', 'model'):
        name = item.get(key)
        if _is_technical_model(name, env):
            return name
    return None


def _image_field_names(model_cls):
    names = []
    for name, field in (getattr(model_cls, '_fields', None) or {}).items():
        if not _ODOO_IMAGE_FIELD_RE.match(name):
            continue
        if getattr(field, 'type', None) != 'binary':
            continue
        names.append(name)
    return names


def _record_has_image(record, fname):
    try:
        return bool(record[fname])
    except Exception:
        return False


def _picture_target(env, model, rec_id, preferred):
    """(modelo, id, campo) de una imagen que existe.

    El campo pedido, si está en el modelo y tiene datos. Si no, otra imagen
    del propio registro. Si tampoco, la de un many2one (y un salto más), para
    no pintar una URL rota cuando la foto vive en el registro de al lado.
    """
    if not env or not _is_technical_model(model, env) or not rec_id:
        return None
    try:
        rec = env[model].browse(rec_id)
        if not rec.exists():
            return None
    except Exception:
        return None
    preferred = str(preferred or '')
    if (
        preferred in rec._fields
        and _ODOO_IMAGE_FIELD_RE.match(preferred)
        and _record_has_image(rec, preferred)
    ):
        return (model, int(rec_id), preferred)
    for fname in _image_field_names(rec):
        if fname != preferred and _record_has_image(rec, fname):
            return (rec._name, int(rec.id), fname)
    seen = set()

    def walk(record, depth):
        if depth > 2 or not record:
            return None
        key = (record._name, int(record.id))
        if key in seen:
            return None
        seen.add(key)
        for fname, field in record._fields.items():
            if getattr(field, 'type', None) != 'many2one':
                continue
            try:
                other = record[fname]
            except Exception:
                continue
            if not other:
                continue
            for iname in _image_field_names(other):
                if _record_has_image(other, iname):
                    return (other._name, int(other.id), iname)
            found = walk(other, depth + 1)
            if found:
                return found
        return None

    return walk(rec, 0)


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


def _web_image_model_segment(url):
    """Trozo de modelo en ``/web/image/<modelo>/<id>/...``, o ''."""
    if not isinstance(url, str) or not url.startswith('/web/image/'):
        return ''
    parts = url.split('/')
    return parts[3] if len(parts) > 3 else ''


def _postprocess_images(result, model_hint=None, env=None):
    """Convierte campos de imagen a URLs ``/web/image/<modelo técnico>/<id>/<campo>``.

    Una columna llamada ``model`` con el nombre del coche no es el modelo del
    registro. Si el campo pedido no existe, se usa una imagen que sí está
    (en el registro o en un many2one), en vez de una URL que el navegador no abre.
    """
    def _process_items(items, model_hint=None):
        if not items or not isinstance(items, list):
            return
        hint = model_hint if _is_technical_model(model_hint, env) else None
        for item in items:
            if not isinstance(item, dict):
                continue
            rec_id = _coerce_record_id(item.get('id'))
            if not rec_id:
                continue
            # NO consumimos __model (antes .pop): lo dejamos en la fila para que
            # el render de tabla pinte el widget de enlace por fila. Como empieza
            # por '_' no aparece como columna de datos ni se exporta.
            model = _row_technical_model(item, env) or hint
            if not model:
                continue

            # La columna la decide su valor (base64 de imagen) o un nombre de
            # campo de imagen de Odoo; el alias que puso el modelo puede estar
            # en cualquier idioma.
            keys_to_process = [k for k in list(item.keys()) if not k.startswith('_')]
            for key in keys_to_process:
                val = item[key]
                if val is False or val is None or val == '':
                    continue
                if isinstance(val, str) and (val.startswith('http') or val.startswith('/')):
                    segment = _web_image_model_segment(val)
                    if not segment or _is_technical_model(segment):
                        continue
                if not (_is_b64_img(val) or _ODOO_IMAGE_FIELD_RE.match(str(key))):
                    continue
                target = _picture_target(env, model, rec_id, key) if env else None
                if target:
                    url = '/web/image/%s/%d/%s' % target
                    item[key] = url
                    _logger.debug('_postprocess_images: %s → URL', url)
                    continue
                if env is None and _ODOO_IMAGE_FIELD_RE.match(str(key)):
                    url = '/web/image/%s/%d/%s' % (model, rec_id, key)
                    item[key] = url
                    continue
                # Campo inventado (logo en un modelo que no lo tiene) y sin
                # otra imagen: no dejar una ruta que pinta el icono roto.
                if isinstance(val, str) and val.startswith('/web/image/'):
                    item[key] = False

    for rows in _iter_all_tabular_row_lists(result):
        _process_items(rows, model_hint=model_hint)
