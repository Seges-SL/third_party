# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""Suite last-mile for portable export/import (records + files).

One policy for every ``pns_*`` JSON/ZIP backup:

- **Export:** discover attributes from the live model (no closed key lists).
  Callers may pass ``skip_fields`` / ``only_fields`` / ``extra`` for domain
  reasons (audit subsets, denormalized labels, binaries).
- **Import:** unknown or unloadable keys are skipped with a warning; the rest
  of the file is still applied.
- **Files:** JSON or ZIP of JSON. Filename style is a parameter (``geo`` /
  ``mcp``). ZIP member layout stays in the module.

Settings (ICP) stay in ``settings_io`` — same policy, ICP-shaped keys.
"""
from __future__ import annotations

import base64
import datetime
import io
import json
import logging
import re
import zipfile

_logger = logging.getLogger(__name__)

_FILENAME_SAFE = re.compile(r'[^A-Za-z0-9._-]+')
_INTERNAL_FIELDS = frozenset({
    'id', 'create_uid', 'create_date', 'write_uid', 'write_date',
    '__last_update', 'display_name',
})
_RELATIONAL_TYPES = frozenset({'one2many', 'many2many', 'many2one'})
FILENAME_STYLES = frozenset({'geo', 'mcp'})

try:
    from odoo import fields as odoo_fields, _
except ImportError:
    odoo_fields = None

    def _(msg):
        return msg


def _sanitize_part(value, default=''):
    text = _FILENAME_SAFE.sub('-', str(value or '').strip())
    return text or default


def _dt_to_string(val):
    if odoo_fields is not None:
        return odoo_fields.Datetime.to_string(val)
    if hasattr(val, 'strftime'):
        return val.strftime('%Y-%m-%d %H:%M:%S')
    return str(val)


def _date_to_string(val):
    if odoo_fields is not None:
        return odoo_fields.Date.to_string(val)
    if hasattr(val, 'strftime'):
        return val.strftime('%Y-%m-%d')
    return str(val)


def _field_type(field):
    return getattr(field, 'type', None)


def _is_export_computed_skip(field):
    if not getattr(field, 'compute', None):
        return False
    if getattr(field, 'inverse', None):
        return False
    return not getattr(field, 'store', False)


# ── Record mapping ──────────────────────────────────────────────────────────


def export_record_dict(record, skip_fields=None, extra=None, only_fields=None):
    """Export one record using live ``_fields`` (plus optional extras).

    *skip_fields* and *only_fields* are module filters, not a second policy.
    Relational, binary, and unstored computed fields are omitted.
    """
    skip = _INTERNAL_FIELDS | set(skip_fields or ())
    only = set(only_fields) if only_fields is not None else None
    model_fields = record._fields
    data = {}
    names = only if only is not None else list(model_fields)
    for fname in names:
        if fname in skip:
            continue
        field = model_fields.get(fname)
        if field is None:
            continue
        try:
            if _field_type(field) in _RELATIONAL_TYPES:
                continue
            if _is_export_computed_skip(field):
                continue
            if _field_type(field) == 'binary':
                continue
            val = record[fname]
            ftype = _field_type(field)
            if ftype == 'datetime' and val:
                data[fname] = _dt_to_string(val)
            elif ftype == 'date' and val:
                data[fname] = _date_to_string(val)
            elif ftype == 'boolean':
                data[fname] = bool(val)
            elif val is False:
                data[fname] = ''
            else:
                data[fname] = val
        except Exception as exc:
            _logger.debug('portable_io: skip export field %s: %s', fname, exc)
    if extra:
        data.update(extra)
    return data


def import_vals_from_dict(model_env, data, skip_fields=None, key_aliases=None):
    """Build ORM write-vals from a JSON dict. Unknown keys become warnings."""
    skip = _INTERNAL_FIELDS | set(skip_fields or ())
    aliases = key_aliases or {}
    model_fields = model_env._fields
    vals = {}
    warnings = []
    if not isinstance(data, dict):
        warnings.append(_('Expected a JSON object for a record; skipped.'))
        return vals, warnings

    for json_key, value in data.items():
        orm_key = aliases.get(json_key, json_key)
        if orm_key in skip:
            continue
        field = model_fields.get(orm_key)
        if field is None:
            warnings.append(_("Unknown field '%s' skipped.") % json_key)
            continue
        try:
            if _field_type(field) in _RELATIONAL_TYPES:
                continue
            if getattr(field, 'related', None):
                continue
            if getattr(field, 'compute', None) and not getattr(field, 'inverse', None):
                continue
            if _field_type(field) == 'binary':
                continue
            if _field_type(field) == 'boolean':
                vals[orm_key] = bool(value)
            elif _field_type(field) == 'selection':
                sel = getattr(field, 'selection', None)
                if isinstance(sel, (list, tuple)) and value not in [s[0] for s in sel]:
                    warnings.append(
                        _("Invalid value for '%s' skipped.") % json_key
                    )
                    continue
                vals[orm_key] = value
            elif _field_type(field) in ('integer', 'float') and value is not None:
                vals[orm_key] = value
            elif value is None:
                vals[orm_key] = False
            else:
                vals[orm_key] = value
        except Exception as exc:
            warnings.append('%s: %s' % (orm_key, exc))
    return vals, warnings


# ── Filenames ───────────────────────────────────────────────────────────────


def build_export_filename(env, artifact, ext, tag=None, style='mcp'):
    """Compose a filename. *style* is ``mcp`` or ``geo``; artifact stays the caller's.

    - ``mcp``: ``YYYYmmddTHHMMSS_<db>[_tag]_<artifact>.<ext>``
    - ``geo``: ``YYYYmmdd_HHMMSS[_tag]_<artifact>.<ext>``
    """
    style = (style or 'mcp').strip().lower()
    if style not in FILENAME_STYLES:
        style = 'mcp'
    ext = (ext or '').lstrip('.')
    artifact = _sanitize_part(artifact, 'export')
    tag_part = _sanitize_part(tag) if tag else ''
    if style == 'geo':
        ts = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        parts = [ts]
    else:
        ts = datetime.datetime.now().strftime('%Y%m%dT%H%M%S')
        dbname = 'db'
        try:
            dbname = env.cr.dbname or 'db'
        except Exception:
            pass
        parts = [ts, _sanitize_part(dbname, 'db')]
    if tag_part:
        parts.append(tag_part)
    parts.append(artifact)
    return '%s.%s' % ('_'.join(parts), ext)


# ── Read upload ─────────────────────────────────────────────────────────────


def extract_json_from_upload(raw_bytes, *, expect_list=True):
    """Parse an upload as JSON or a ZIP of JSON files.

    ZIP members whose name starts with ``__`` are ignored (manifests).
    A bad member is skipped with a warning; only a totally unreadable
    file raises ``ValueError``.
    """
    warnings = []
    raw_bytes = raw_bytes or b''
    if raw_bytes[:2] == b'PK':
        try:
            zf = zipfile.ZipFile(io.BytesIO(raw_bytes))
            json_files = [
                n for n in zf.namelist()
                if n.lower().endswith('.json') and not n.startswith('__')
            ]
            if not json_files:
                raise ValueError(_('ZIP file does not contain any .json files.'))
            merged = []
            for jf in sorted(json_files):
                try:
                    content = json.loads(zf.read(jf).decode('utf-8'))
                    if isinstance(content, list):
                        merged.extend(content)
                    elif isinstance(content, dict):
                        merged.append(content)
                    else:
                        warnings.append(
                            _("File '%s' in ZIP has unexpected format, skipped.") % jf
                        )
                except (json.JSONDecodeError, UnicodeDecodeError) as exc:
                    warnings.append(
                        _("File '%s' in ZIP could not be parsed: %s") % (jf, exc)
                    )
            if not merged:
                raise ValueError(_('No valid JSON data found in the ZIP file.'))
            return merged, warnings
        except zipfile.BadZipFile:
            pass

    try:
        data = json.loads(raw_bytes.decode('utf-8'))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ValueError(
            _('File is neither valid JSON nor a ZIP archive: %s') % exc
        )

    if expect_list:
        if isinstance(data, dict):
            data = [data]
            warnings.append(
                _('JSON contained a single object; wrapped into a list.')
            )
        elif not isinstance(data, list):
            raise ValueError(
                _('Expected a JSON array, got %s.') % type(data).__name__
            )
    return data, warnings


# ── Write attachment ────────────────────────────────────────────────────────


def write_export_attachment(
    env, filename, raw_bytes, mimetype='application/octet-stream',
    res_model=None, res_id=0,
):
    """Store *raw_bytes* as ``ir.attachment`` and return the record."""
    vals = {
        'name': filename,
        'type': 'binary',
        'datas': base64.b64encode(raw_bytes),
        'mimetype': mimetype,
    }
    if res_model:
        vals['res_model'] = res_model
        vals['res_id'] = res_id or 0
    return env['ir.attachment'].create(vals)


def write_json_attachment(env, filename, data, res_model=None, res_id=0):
    raw = json.dumps(data, indent=2, ensure_ascii=False).encode('utf-8')
    return write_export_attachment(
        env, filename, raw, mimetype='application/json',
        res_model=res_model, res_id=res_id,
    )


def pack_zip_members(members):
    """Build ZIP bytes from ``[(path, dict|list|str|bytes), ...]``.

    The module chooses member paths. Dicts/lists are JSON-encoded
    (compact, ``ensure_ascii=False``).
    """
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        for name, payload in members:
            if isinstance(payload, (dict, list)):
                payload = json.dumps(payload, ensure_ascii=False)
            if isinstance(payload, str):
                payload = payload.encode('utf-8')
            zf.writestr(name, payload)
    return buf.getvalue()


def write_zip_attachment(env, filename, members, res_model=None, res_id=0):
    raw = pack_zip_members(members)
    return write_export_attachment(
        env, filename, raw, mimetype='application/zip',
        res_model=res_model, res_id=res_id,
    )


# ── Download wizard ─────────────────────────────────────────────────────────


def build_json_export_report(count, filename, *, success_text=None):
    from odoo.addons.pns_base.utils import ui_feedback as pns_ui

    success_text = success_text or _('Export completed successfully.')
    footer = (
        '<p class="text-muted" style="font-size:11px;margin-bottom:0;">'
        '<i class="fa fa-download"></i> '
        + _('Click "Download" to choose where to save the file.')
        + '</p>'
    )
    return pns_ui.build_operation_report_html(
        None,
        success_text,
        'alert-success',
        'fa-check-circle',
        rows=[
            (_('Records exported'), count),
            (_('File name'), filename),
        ],
        footer_html=footer,
    )


def open_export_wizard(
    env, *, dialog_title, summary_text, count, attachment,
    wizard_model='pns.export.file.wizard',
):
    html = build_json_export_report(
        count, attachment.name, success_text=summary_text,
    )
    wizard = env[wizard_model].create({
        'result_html': html,
        'attachment_id': attachment.id,
        'export_filename': attachment.name,
    })
    return wizard._reopen_operation_wizard(title=dialog_title)


def open_export_empty_wizard(
    env, *, dialog_title, message, wizard_model='pns.export.file.wizard',
):
    from odoo.addons.pns_base.utils import ui_feedback as pns_ui

    html = pns_ui.build_operation_report_html(
        None,
        message,
        'alert-warning',
        'fa-exclamation-triangle',
        rows=[],
    )
    wizard = env[wizard_model].create({'result_html': html})
    return wizard._reopen_operation_wizard(title=dialog_title)
