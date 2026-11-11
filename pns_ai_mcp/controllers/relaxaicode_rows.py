# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""Rows of a relaxaicode result: record ids, technical models and pictures."""

import logging
import re

_logger = logging.getLogger(__name__)


_B64_IMG_PREFIXES = ('iVBORw', '/9j/', 'R0lGOD', 'UklGR')
_B64_PLACEHOLDER = '[image omitted: return the URL /web/image/<model>/<id>/image_128]'


# STANDARD Odoo image field names. With a known model+id we can
# serve the image from /web/image/model/id/field even if the cell does not carry the
# base64 (the LLM sometimes returns a boolean/placeholder). Only these names,
# so we do not risk a 404 with odd aliases.
_ODOO_IMAGE_FIELD_RE = re.compile(r'^(image|avatar|logo|photo|picture)(_\w+)?$', re.I)


# Technical Odoo model name (res.partner). A text with spaces or capitals
# is a business label (the car's model), not the record's model.
_TECHNICAL_MODEL_RE = re.compile(r'^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)+$')


def _is_technical_model(name, env=None):
    """True if *name* is a registry model (``fleet.vehicle``), not a label."""
    if not isinstance(name, str) or not _TECHNICAL_MODEL_RE.match(name):
        return False
    if env is None:
        return True
    try:
        return name in env
    except Exception:
        return False


def _row_technical_model(item, env=None):
    """Technical model already written in the row (``__model`` or a ``model`` column)."""
    if not isinstance(item, dict):
        return None
    for key in ('__model', 'model'):
        name = item.get(key)
        if _is_technical_model(name, env):
            return name
    return None


def _image_size_rank(name):
    """Smallest variant first (image_128 before image_1920): rows show thumbnails."""
    match = _ODOO_IMAGE_FIELD_RE.match(name)
    prefix = match.group(1).lower()
    size = re.search(r'_(\d+)$', name)
    return (
        int(size.group(1)) if size else float('inf'),
        ('image', 'avatar', 'logo', 'photo', 'picture').index(prefix),
    )


def _image_field_names(model_cls):
    names = []
    for name, field in (getattr(model_cls, '_fields', None) or {}).items():
        if not _ODOO_IMAGE_FIELD_RE.match(name):
            continue
        if getattr(field, 'type', None) != 'binary':
            continue
        names.append(name)
    return sorted(names, key=_image_size_rank)


def _record_has_image(record, fname):
    try:
        return bool(record[fname])
    except Exception:
        return False


def _picture_target(env, model, rec_id, preferred):
    """(model, id, field) of an image that exists.

    The requested field, if it is on the model and has data. If not, another image
    of the record itself. If not that either, one from a many2one (and one more hop), so
    we do not paint a broken URL when the photo lives on the record next door.
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
    """True if the value looks like image base64.
    Accepts str (serialized JSON) and bytes (Odoo Binary field as is)."""
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
    """Replace image base64 blobs with a short placeholder so the
    result sent to the LLM does not overflow the context window (the real cause
    of the "context_length_exceeded" failures). Does not mutate the original nor touch the
    'formatted_text' key (presentation HTML meant for the user)."""

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
    """Normalize a row id to int (accepts a numeric str / whole float)."""
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
    """Row id: accepts ``id`` / ``ID`` (the LLM's usual capitalization)."""
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
    """If a cell is an XMLID (``module.name``), resolve the real model+id.

    Generic (ir.model.data / env.ref), not domain. Avoids stamp failures
    when the same numeric id exists in many models.
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
    """Every list of tabular dicts in the result (multi-criteria included).

    Covers ``data``/``items``, ``groups``/``sections``/``tables`` envelopes and sibling
    lists (e.g. by_units + by_amount). Before, only the first list was checked
    → the 2nd table (and sometimes both if the stamp failed) were left without ``__model``.
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
    """Model part of ``/web/image/<model>/<id>/...``, or ''."""
    if not isinstance(url, str) or not url.startswith('/web/image/'):
        return ''
    parts = url.split('/')
    return parts[3] if len(parts) > 3 else ''


def _postprocess_images(result, model_hint=None, env=None):
    """Turn image fields into ``/web/image/<technical model>/<id>/<field>`` URLs.

    A column named ``model`` holding the car's name is not the record's
    model. If the requested field does not exist, an image that does exist is used
    (on the record or on a many2one), instead of a URL the browser cannot open.
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
            # We do NOT consume __model (it used to be .pop): we leave it in the row so
            # the table render paints the per-row link widget. Since it starts
            # with '_' it does not show up as a data column and is not exported.
            model = _row_technical_model(item, env) or hint
            if not model:
                continue

            # The column is decided by its value (image base64) or by an Odoo image
            # field name; the alias the model gave may be
            # in any language.
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
                # Made-up field (logo on a model that has none) and no
                # other image: do not leave a path that paints the broken icon.
                if isinstance(val, str) and val.startswith('/web/image/'):
                    item[key] = False

    for rows in _iter_all_tabular_row_lists(result):
        _process_items(rows, model_hint=model_hint)
