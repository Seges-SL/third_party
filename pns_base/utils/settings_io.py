# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 Patanegra Soft <https://patanegra.com>
"""Portable ``res.config.settings`` I/O — dynamic fields, fault-tolerant load.

Suite policy (every ``pns_*`` settings backup):

- **Save / export:** discover attributes from the live model
  (``config_parameter`` prefix and/or owning module). No closed key lists.
- **Load / import:** unknown or unloadable keys are skipped with a warning;
  the rest of the file is still applied. Persist one ICP key at a time so
  one failure never blocks the others.

Callers pass ``module`` (e.g. ``pns_geo``) and/or ``icp_prefix``
(e.g. ``pns_geo.``). Domain clamps stay in the module.
"""
from __future__ import annotations

import logging

_logger = logging.getLogger(__name__)

SCHEMA_VERSION = '1.0'

_SKIP_TYPES = frozenset({
    'many2one', 'one2many', 'many2many', 'binary', 'html',
})
_SKIP_NAMES = frozenset({
    'id', 'display_name', '__last_update',
    'create_uid', 'create_date', 'write_uid', 'write_date',
})
_SECRET_TOKENS = ('_key', 'api_key', 'secret', 'token', 'password')


try:
    from odoo import _
except ImportError:
    def _(msg):
        return msg


def _section():
    return {'created': 0, 'updated': 0, 'skipped': 0}


def _field_modules(field):
    modules = set(getattr(field, '_modules', None) or ())
    module = getattr(field, '_module', None)
    if module:
        modules.add(module)
    return modules


def settings_icp_key(field, icp_prefix=None):
    """Return the field's ``config_parameter`` if it matches *icp_prefix*."""
    icp = getattr(field, 'config_parameter', None)
    if not icp:
        return None
    icp = str(icp)
    if icp_prefix and not icp.startswith(icp_prefix):
        return None
    return icp


def portable_key(fname, field, icp_prefix=None):
    """Stable JSON key: ICP when declared, otherwise the field name."""
    return settings_icp_key(field, icp_prefix=icp_prefix) or fname


def is_secret_field(fname, field, icp_prefix=None):
    """True for Char credentials (name / ICP contains key, token, …)."""
    if getattr(field, 'type', None) != 'char':
        return False
    hay = '%s %s' % (fname, settings_icp_key(field, icp_prefix=icp_prefix) or '')
    hay = hay.lower()
    return any(tok in hay for tok in _SECRET_TOKENS)


def iter_settings_fields(model, module=None, icp_prefix=None):
    """Yield ``(fname, field)`` for portable settings on *model*.

    A field is included when its ``config_parameter`` starts with
    *icp_prefix* and/or its owning ``_module`` is *module*.
    """
    if not module and not icp_prefix:
        raise ValueError('iter_settings_fields requires module or icp_prefix')
    fields_map = getattr(model, '_fields', None) or {}
    for fname, field in fields_map.items():
        if fname in _SKIP_NAMES or fname.startswith('_'):
            continue
        if getattr(field, 'related', None) or getattr(field, 'automatic', False):
            continue
        if getattr(field, 'type', None) in _SKIP_TYPES:
            continue
        icp = getattr(field, 'config_parameter', None) or ''
        by_prefix = bool(icp_prefix) and str(icp).startswith(icp_prefix)
        by_module = bool(module) and module in _field_modules(field)
        if by_prefix or by_module:
            yield fname, field


def field_default(field):
    default = getattr(field, 'default', None)
    if default is None:
        ftype = getattr(field, 'type', 'char')
        if ftype == 'boolean':
            return False
        if ftype == 'integer':
            return 0
        if ftype == 'float':
            return 0.0
        return ''
    if callable(default):
        return default(None)
    return default


def value_from_icp(field, raw):
    """Coerce an ICP string (or JSON value) to a settings field value."""
    ftype = getattr(field, 'type', 'char')
    if raw is None or raw is False:
        if ftype == 'char':
            return ''
        return field_default(field)
    if ftype == 'boolean':
        if isinstance(raw, bool):
            return raw
        return str(raw).strip().lower() in ('1', 'true', 'yes', 'on')
    if ftype == 'integer':
        if isinstance(raw, str) and not raw.strip():
            return field_default(field)
        try:
            return int(raw)
        except (TypeError, ValueError):
            return field_default(field)
    if ftype == 'float':
        if isinstance(raw, str) and not raw.strip():
            return field_default(field)
        try:
            return float(raw)
        except (TypeError, ValueError):
            return field_default(field)
    if ftype == 'char':
        return '' if raw is False else str(raw)
    if raw is False:
        return field_default(field)
    return str(raw)


def value_to_icp(field, value):
    """Serialize a settings field value to the ICP string form."""
    ftype = getattr(field, 'type', 'char')
    if ftype == 'boolean':
        return 'True' if value else 'False'
    if ftype == 'integer':
        try:
            return str(int(value or 0))
        except (TypeError, ValueError):
            return str(int(field_default(field) or 0))
    if ftype == 'float':
        try:
            return str(float(value or 0))
        except (TypeError, ValueError):
            return str(float(field_default(field) or 0))
    if value is False or value is None:
        return ''
    return str(value).strip() if ftype == 'char' else str(value)


def jsonify_setting(value, field):
    """JSON-friendly form of a ``get_values()`` entry."""
    ftype = getattr(field, 'type', 'char')
    if ftype == 'boolean':
        return bool(value)
    if ftype == 'integer':
        if value is False or value is None:
            return 0
        return int(value)
    if ftype == 'float':
        if value is False or value is None:
            return 0.0
        return float(value)
    if value is False or value is None:
        return ''
    return value


def read_settings_icp(model, get_param, module=None, icp_prefix=None):
    """Load discovered settings from ICP into ``{field_name: value}``."""
    out = {}
    for fname, field in iter_settings_fields(
        model, module=module, icp_prefix=icp_prefix,
    ):
        icp = settings_icp_key(field, icp_prefix=icp_prefix)
        if not icp:
            continue
        out[fname] = value_from_icp(field, get_param(icp, None))
    return out


def collect_settings_payload(
    values, catalog, include_secrets=True, icp_prefix=None,
):
    """Build the ``settings`` dict for a backup from ``get_values()`` output."""
    out = {}
    for fname, field in catalog:
        if not include_secrets and is_secret_field(
            fname, field, icp_prefix=icp_prefix,
        ):
            continue
        out[portable_key(fname, field, icp_prefix=icp_prefix)] = jsonify_setting(
            values.get(fname), field,
        )
    return out


def catalog_index(catalog, icp_prefix=None):
    """Map portable key *and* field name → ``(fname, field)``."""
    index = {}
    for fname, field in catalog:
        index[fname] = (fname, field)
        key = portable_key(fname, field, icp_prefix=icp_prefix)
        index[key] = (fname, field)
    return index


def _has_stored_value(value, field):
    if getattr(field, 'type', None) == 'boolean':
        return True
    if value is False or value is None:
        return False
    if isinstance(value, str) and not value.strip():
        return False
    return True


def resolve_import_overlay(
    settings_dict, catalog, current, replace_existing=True, icp_prefix=None,
):
    """Match backup keys to current fields.

    Unknown keys and per-key coerce failures become warnings; the rest
    continues. Returns ``(overlay, warnings, skipped, errors)``.
    """
    overlay = {}
    warnings = []
    errors = []
    skipped = 0
    if not isinstance(settings_dict, dict):
        errors.append(_('Invalid backup file: expected a settings object.'))
        return overlay, warnings, skipped, errors
    index = catalog_index(catalog, icp_prefix=icp_prefix)
    for raw_key, raw_val in settings_dict.items():
        hit = index.get(raw_key)
        if not hit:
            warnings.append(_("Unknown setting '%s' skipped.") % raw_key)
            skipped += 1
            continue
        fname, field = hit
        if not replace_existing and _has_stored_value(current.get(fname), field):
            skipped += 1
            continue
        try:
            overlay[fname] = value_from_icp(field, raw_val)
        except Exception as exc:
            warnings.append(
                _("Could not apply setting '%s'; skipped.") % raw_key
            )
            skipped += 1
            _logger.warning(
                'settings_io: skip setting %s: %s', raw_key, exc,
            )
    return overlay, warnings, skipped, errors


def persist_settings_overlay(
    icp, overlay, catalog, values, icp_prefix=None,
):
    """Write each setting on its own. One failure never blocks the others.

    *icp* is ``ir.config_parameter`` (already sudo'd). Returns
    ``(updated, skipped, warnings)``.
    """
    warnings = []
    updated = 0
    skipped = 0
    field_by_name = dict(catalog)
    for fname in overlay:
        field = field_by_name.get(fname)
        icp_key = (
            settings_icp_key(field, icp_prefix=icp_prefix)
            if field is not None else None
        )
        label = (
            portable_key(fname, field, icp_prefix=icp_prefix)
            if field is not None else fname
        )
        if not icp_key:
            warnings.append(_("Unknown setting '%s' skipped.") % label)
            skipped += 1
            continue
        try:
            value = values.get(fname, overlay[fname])
            icp.set_param(icp_key, value_to_icp(field, value))
            updated += 1
        except Exception as exc:
            warnings.append(
                _("Could not apply setting '%s'; skipped.") % label
            )
            skipped += 1
            _logger.warning(
                'settings_io: skip setting %s: %s', label, exc,
            )
    return updated, skipped, warnings


def write_settings_record(
    record, icp, module=None, icp_prefix=None, clamp=None,
):
    """Persist every portable field on *record* (dynamic, per-key, tolerant)."""
    catalog = list(iter_settings_fields(
        record, module=module, icp_prefix=icp_prefix,
    ))
    values = {fname: getattr(record, fname) for fname, _field in catalog}
    if clamp:
        clamp(values, fields_map=getattr(record, '_fields', None))
        for fname, value in values.items():
            if getattr(record, fname) != value:
                setattr(record, fname, value)
    return persist_settings_overlay(
        icp, values, catalog, values, icp_prefix=icp_prefix,
    )


def export_settings(
    env, module=None, icp_prefix=None, include_secrets=True,
    schema_version=SCHEMA_VERSION,
):
    """Return a portable dict with the module's settings (secrets optional)."""
    import datetime as _dt

    Settings = env['res.config.settings']
    catalog = list(iter_settings_fields(
        Settings, module=module, icp_prefix=icp_prefix,
    ))
    values = Settings.get_values()
    return {
        'schema_version': schema_version,
        'exported_at': (
            _dt.datetime.utcnow().replace(microsecond=0).isoformat() + 'Z'
        ),
        'include_secrets': bool(include_secrets),
        'settings': collect_settings_payload(
            values, catalog, include_secrets=include_secrets,
            icp_prefix=icp_prefix,
        ),
    }


def import_settings(
    env, data, module=None, icp_prefix=None, replace_existing=True, clamp=None,
):
    """Restore settings from a portable dict. Unknown keys never abort."""
    report = {'sections': {'settings': _section()}, 'warnings': [], 'errors': []}
    if not isinstance(data, dict):
        report['errors'].append(_('Invalid backup file: expected a JSON object.'))
        return report
    settings_dict = data.get('settings')
    if settings_dict is None:
        report['errors'].append(_("Backup file has no 'settings' section."))
        return report
    Settings = env['res.config.settings']
    try:
        catalog = list(iter_settings_fields(
            Settings, module=module, icp_prefix=icp_prefix,
        ))
    except Exception as exc:
        report['warnings'].append(
            _('Could not read settings fields; nothing was imported.')
        )
        _logger.warning('settings_io: catalog failed: %s', exc)
        return report
    try:
        current = Settings.get_values() or {}
    except Exception as exc:
        current = {}
        report['warnings'].append(
            _('Could not read current settings; applying file values only.')
        )
        _logger.warning('settings_io: get_values failed: %s', exc)
    overlay, warnings, skipped, errors = resolve_import_overlay(
        settings_dict, catalog, current, replace_existing=replace_existing,
        icp_prefix=icp_prefix,
    )
    report['warnings'].extend(warnings)
    report['errors'].extend(errors)
    sec = report['sections']['settings']
    sec['skipped'] = skipped
    if not overlay:
        return report
    merged = {fname: current.get(fname) for fname, _field in catalog}
    merged.update(overlay)
    if clamp:
        clamp(merged, fields_map=Settings._fields)
    updated, persist_skipped, persist_warnings = persist_settings_overlay(
        env['ir.config_parameter'].sudo(),
        overlay,
        catalog,
        merged,
        icp_prefix=icp_prefix,
    )
    sec['updated'] = updated
    sec['skipped'] += persist_skipped
    report['warnings'].extend(persist_warnings)
    return report
