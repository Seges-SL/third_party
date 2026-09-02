# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
# Archivo: models/ir_ui_view_patch.py
# Descripción: Compatibilidad de vistas single-branch para el ecosistema PNS.
#
#   La fuente XML de los módulos pns_* se escribe SIEMPRE en sintaxis antigua
#   (attrs, <tree>), válida de forma nativa en Odoo 13-16. En Odoo 17+ este
#   parche la convierte en runtime a invisible/readonly/required="expresión" y
#   <list>. Vive en pns_base para no duplicarlo en cada módulo.
#
#   Detección de "vista PNS": señal fiable es el módulo del xml_id del <record>
#   (pns_*). Para creación programática sin xml_id se usan pistas de nombre/modelo;
#   la conversión solo actúa si hay sintaxis antigua, así que una pista de más
#   nunca corrompe una vista ya escrita en sintaxis nueva.
#
#   Sin borrado silencioso: si un attrs no se puede convertir se registra ERROR
#   y se deja tal cual, de modo que falle de forma visible en Odoo 17+.

import ast
import html
import re
import logging

from odoo import models, api

_logger = logging.getLogger(__name__)

# Prefijo de los módulos del ecosistema PNS (pns_ai_mcp, pns_environment_ribbon, ...).
_PNS_MODULE_PREFIX = 'pns'

# Pistas de respaldo para create()/write() sin xml_id (creación programática).
_PNS_NAME_HINTS = ('pns', 'inherit.mcp')
_PNS_MODEL_HINTS = ('pns', 'ai.', 'mcp.', 'relaxaicode')

# Modificadores de vista soportados (Odoo 17+ los expresa como atributo con expresión).
_MODIFIER_KEYS = ('invisible', 'readonly', 'required', 'column_invisible')


def _module_from_xmlid(xml_id):
    """Extract the module prefix from an xmlid (e.g. 'pns_ai_mcp.view_form' → 'pns_ai_mcp')."""
    if xml_id and '.' in xml_id:
        return xml_id.split('.', 1)[0]
    return ''


def _is_pns_module(module):
    """True if the module name starts with the PNS prefix ('pns')."""
    return bool(module) and module.startswith(_PNS_MODULE_PREFIX)


def _hint(value, hints):
    """True if *value* contains any of the substring hints (fallback PNS detection)."""
    return bool(value) and any(h in value for h in hints)


def _record_is_pns(data):
    """¿El <record> XML pertenece a un módulo PNS? (xml_id es la señal fiable)."""
    if _is_pns_module(_module_from_xmlid(data.get('xml_id'))):
        return True
    vals = data.get('values') or {}
    return (
        _hint(vals.get('name'), _PNS_NAME_HINTS)
        or _hint(vals.get('model'), _PNS_MODEL_HINTS)
        or _hint(vals.get('res_model'), _PNS_MODEL_HINTS)
    )


def _view_vals_look_pns(vals):
    """Respaldo para ir.ui.view.create()/write() sin xml_id."""
    return _hint(vals.get('name'), _PNS_NAME_HINTS) or _hint(vals.get('model'), _PNS_MODEL_HINTS)


def _action_vals_look_pns(vals):
    """Respaldo para ir.actions.act_window.create()/write() sin xml_id."""
    return _hint(vals.get('name'), _PNS_NAME_HINTS) or _hint(vals.get('res_model'), _PNS_MODEL_HINTS)


def _normalize_act_window_view_modes(vals):
    """Replace tree→list in view_mode and nested act_window.view commands (O17+)."""
    if vals.get('view_mode'):
        vals['view_mode'] = vals['view_mode'].replace('tree', 'list')
    view_ids = vals.get('view_ids')
    if not view_ids:
        return
    normalized = []
    for cmd in view_ids:
        if (
            isinstance(cmd, (list, tuple))
            and len(cmd) >= 3
            and cmd[0] == 0
            and isinstance(cmd[2], dict)
            and cmd[2].get('view_mode') == 'tree'
        ):
            sub = dict(cmd[2])
            sub['view_mode'] = 'list'
            normalized.append((cmd[0], cmd[1], sub))
        else:
            normalized.append(cmd)
    vals['view_ids'] = normalized


def _leaf_to_expr(leaf):
    """Una tupla de dominio ('campo', operador, valor) -> expresión Python (str)."""
    field, op, value = leaf[0], leaf[1], leaf[2]
    if op == '=':
        if value is False:
            return 'not %s' % field
        if value is True:
            return '%s' % field
        return '%s == %r' % (field, value)
    if op == '!=':
        if value is False:
            return '%s' % field
        if value is True:
            return 'not %s' % field
        return '%s != %r' % (field, value)
    if op == 'in':
        return '%s in %r' % (field, value)
    if op == 'not in':
        return '%s not in %r' % (field, value)
    if op in ('>', '>=', '<', '<='):
        return '%s %s %r' % (field, op, value)
    raise ValueError("operador de dominio no soportado: %r" % (op,))


def _domain_to_expr(domain):
    """
    Dominio Odoo (notación prefija con '|','&','!' y AND implícito entre términos)
    -> expresión Python para los modificadores invisible/readonly/required (O17+).
    Conversor general: no depende de una tabla de cadenas conocidas.
    """
    if not domain:
        # Dominio vacío = siempre verdadero en Odoo.
        return 'True'
    tokens = list(domain)
    state = {'i': 0}

    def parse_one():
        """Parse one token from the domain list (leaf, operator, or negation)."""
        tok = tokens[state['i']]
        state['i'] += 1
        if isinstance(tok, str):
            if tok == '!':
                return 'not (%s)' % parse_one()
            if tok == '|':
                a = parse_one()
                b = parse_one()
                return '(%s or %s)' % (a, b)
            if tok == '&':
                a = parse_one()
                b = parse_one()
                return '(%s and %s)' % (a, b)
            raise ValueError("token de dominio no soportado: %r" % (tok,))
        return _leaf_to_expr(tok)

    parts = []
    while state['i'] < len(tokens):
        parts.append(parse_one())
    if len(parts) == 1:
        return parts[0]
    # AND implícito entre términos de primer nivel.
    return ' and '.join('(%s)' % p for p in parts)


def _normalize_domain_tokens(domain):
    """Corrige tokens '&amp;'/'|' etc. si el arch llegó con entidades XML."""
    if not isinstance(domain, (list, tuple)):
        return domain
    out = []
    for tok in domain:
        if tok == '&amp;':
            out.append('&')
        elif isinstance(tok, (list, tuple)) and len(tok) == 3:
            out.append(tuple(tok))
        else:
            out.append(tok)
    return out


def _convert_attrs_match(match):
    """Sustituye un attrs="{...}" por los modificadores con expresión equivalentes."""
    quote = match.group(1)
    # etree puede dejar &amp; en el arch serializado; sin unescape '&' falla.
    dict_str = html.unescape(match.group(2))
    try:
        attrs = ast.literal_eval(dict_str)
        if not isinstance(attrs, dict):
            raise ValueError("attrs no es un dict")
        for key in _MODIFIER_KEYS:
            if key in attrs:
                attrs[key] = _normalize_domain_tokens(attrs[key])
    except Exception as e:
        _logger.error(
            "PNS attrs: no se pudo parsear attrs=%s%s%s (%s); se deja sin convertir "
            "y fallara de forma visible en O17+", quote, dict_str, quote, e)
        return match.group(0)

    parts = []
    for key in _MODIFIER_KEYS:
        if key in attrs:
            try:
                parts.append('%s="%s"' % (key, _domain_to_expr(attrs[key])))
            except Exception as e:
                _logger.error(
                    "PNS attrs: no se pudo convertir %s=%r (%s); se deja sin convertir",
                    key, attrs[key], e)
                return match.group(0)
    for key in attrs:
        if key not in _MODIFIER_KEYS:
            _logger.warning("PNS attrs: modificador no soportado '%s' ignorado", key)
    return ' '.join(parts)


_ATTRS_ATTRIBUTE_TAG_RE = re.compile(
    r'<attribute\s+name=["\']attrs["\']\s*>(\{.*?\})</attribute>',
    re.DOTALL,
)


def _convert_attribute_attrs_tag(match):
    """``<attribute name="attrs">{...}</attribute>`` → one tag per modifier."""
    dict_str = html.unescape(match.group(1))
    try:
        attrs = ast.literal_eval(dict_str)
        if not isinstance(attrs, dict):
            raise ValueError("attrs no es un dict")
        for key in _MODIFIER_KEYS:
            if key in attrs:
                attrs[key] = _normalize_domain_tokens(attrs[key])
    except Exception as e:
        _logger.error(
            "PNS attrs: no se pudo parsear <attribute name=attrs>%s (%s); "
            "se deja sin convertir y fallara de forma visible en O17+",
            dict_str, e)
        return match.group(0)

    parts = []
    for key in _MODIFIER_KEYS:
        if key in attrs:
            try:
                parts.append(
                    '<attribute name="%s">%s</attribute>' % (
                        key, _domain_to_expr(attrs[key]),
                    )
                )
            except Exception as e:
                _logger.error(
                    "PNS attrs: no se pudo convertir <attribute> %s=%r (%s)",
                    key, attrs[key], e)
                return match.group(0)
    for key in attrs:
        if key not in _MODIFIER_KEYS:
            _logger.warning("PNS attrs: modificador no soportado '%s' ignorado", key)
    return ''.join(parts) if parts else match.group(0)


def _convert_arch_fields(vals, converter):
    """Rewrite arch / arch_db in *vals* (Odoo 19 loads inherit views as arch_db)."""
    for key in ('arch', 'arch_db'):
        if key in vals and vals[key]:
            vals[key] = converter(vals[key])


def _alias_groups_vals(vals, fields):
    from ..utils.compat import apply_groups_field_alias
    apply_groups_field_alias(vals, fields)


class IrUiView(models.Model):
    """
    Parche de compatibilidad de vistas single-branch (Odoo 13 -> 19+).

    La fuente XML se escribe SIEMPRE en sintaxis antigua (attrs, <tree>), valida
    de forma nativa en Odoo 13-16. Para Odoo 17+ este parche la convierte en
    runtime a invisible/readonly/required="expresion" y <list>.
    """
    _inherit = 'ir.ui.view'

    @api.model
    def _load_records(self, data_list, update=False):
        """Override: convert attrs→expression and tree→list for PNS views on load (O17+)."""
        from ..utils.compat import ODOO_VERSION
        for data in data_list:
            vals = data.get('values', {})
            _alias_groups_vals(vals, self._fields)
        if ODOO_VERSION >= 17:
            for data in data_list:
                vals = data.get('values', {})
                if _record_is_pns(data):
                    _convert_arch_fields(vals, self._auto_convert_attrs)
                    if vals.get('type') == 'tree':
                        vals.pop('type', None)
        return super(IrUiView, self)._load_records(data_list, update)

    @api.model_create_multi
    def create(self, vals_list):
        """Override: convert attrs→expression for programmatically created PNS views (O17+)."""
        from ..utils.compat import ODOO_VERSION
        for vals in vals_list:
            _alias_groups_vals(vals, self._fields)
            if ODOO_VERSION >= 17 and _view_vals_look_pns(vals):
                _convert_arch_fields(vals, self._auto_convert_attrs)
                if vals.get('type') == 'tree':
                    vals.pop('type', None)
        return super(IrUiView, self).create(vals_list)

    def write(self, vals):
        """Override: convert attrs→expression when arch is updated on a PNS view (O17+)."""
        from ..utils.compat import ODOO_VERSION
        _alias_groups_vals(vals, self._fields)
        if ODOO_VERSION >= 17 and ('arch' in vals or 'arch_db' in vals):
            for record in self:
                if _hint(record.name, _PNS_NAME_HINTS) or _hint(record.model, _PNS_MODEL_HINTS):
                    _convert_arch_fields(vals, self._auto_convert_attrs)
                    break
        return super(IrUiView, self).write(vals)

    @api.model
    def _auto_convert_attrs(self, arch):
        """Core transformer: rewrite old-style XML arch for Odoo 17+ compatibility.

        Transformations applied (in order):
          1. ``attrs="{...}"`` → individual ``invisible/readonly/required="expr"``
          2. ``<tree>`` → ``<list>``
          3. Static ``invisible="1"`` inside ``<list>`` → ``column_invisible="True"``
          4. (O19+) res.config.settings xpath fix for new base form layout

        Args:
            arch: XML arch string.

        Returns:
            Transformed arch string. Returns unchanged if no PNS patterns found.
        """
        if not arch:
            return arch

        # 1) attrs="{...}" -> invisible/readonly/required="expresion" (conversor general).
        if 'attrs=' in arch:
            arch = re.sub(r'''attrs=(["'])(\{.*?\})\1''', _convert_attrs_match, arch, flags=re.DOTALL)
        # 1b) inherit: <attribute name="attrs">{...}</attribute>
        if 'name="attrs"' in arch or "name='attrs'" in arch:
            arch = _ATTRS_ATTRIBUTE_TAG_RE.sub(_convert_attribute_attrs_tag, arch)

        # 2) <tree> -> <list>
        arch = re.sub(r'<tree\b', '<list', arch)
        arch = arch.replace('</tree>', '</list>')

        # 3) invisible="1" estatico dentro de <list> -> column_invisible="True"
        def replace_invisible_in_list(match):
            """Replace static invisible='1' with column_invisible='True' inside <list> blocks."""
            return match.group(0).replace('invisible="1"', 'column_invisible="True"')
        arch = re.sub(r'<list\b.*?</list>', replace_invisible_in_list, arch, flags=re.DOTALL)

        # 4) res.config.settings en Odoo 19+
        from ..utils.compat import ODOO_VERSION
        if ODOO_VERSION >= 19:
            arch = arch.replace(
                '''expr="//div[hasclass('settings')]"''',
                '''expr="//form[hasclass('oe_form_configuration')]"'''
            )

        return arch


class IrActionsActWindow(models.Model):
    _inherit = 'ir.actions.act_window'

    @api.model
    def _load_records(self, data_list, update=False):
        """Override: replace 'tree' with 'list' in view_mode for PNS actions (O17+)."""
        from ..utils.compat import ODOO_VERSION
        for data in data_list:
            vals = data.get('values', {})
            _alias_groups_vals(vals, self._fields)
            if ODOO_VERSION >= 17 and _record_is_pns(data):
                _normalize_act_window_view_modes(vals)
        return super(IrActionsActWindow, self)._load_records(data_list, update)

    @api.model_create_multi
    def create(self, vals_list):
        """Override: replace 'tree' with 'list' in view_mode for new PNS actions (O17+)."""
        from ..utils.compat import ODOO_VERSION
        for vals in vals_list:
            _alias_groups_vals(vals, self._fields)
            if ODOO_VERSION >= 17 and _action_vals_look_pns(vals):
                _normalize_act_window_view_modes(vals)
        return super(IrActionsActWindow, self).create(vals_list)

    def write(self, vals):
        """Override: replace 'tree' with 'list' in view_mode when updating PNS actions (O17+)."""
        from ..utils.compat import ODOO_VERSION
        _alias_groups_vals(vals, self._fields)
        if ODOO_VERSION >= 17 and 'view_mode' in vals:
            for record in self:
                if _hint(record.res_model, _PNS_MODEL_HINTS):
                    vals['view_mode'] = vals['view_mode'].replace('tree', 'list')
                    break
        return super(IrActionsActWindow, self).write(vals)


class IrUiMenu(models.Model):
    _inherit = 'ir.ui.menu'

    @api.model
    def _load_records(self, data_list, update=False):
        for data in data_list:
            _alias_groups_vals(data.get('values', {}), self._fields)
        return super(IrUiMenu, self)._load_records(data_list, update)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            _alias_groups_vals(vals, self._fields)
        return super(IrUiMenu, self).create(vals_list)

    def write(self, vals):
        _alias_groups_vals(vals, self._fields)
        return super(IrUiMenu, self).write(vals)
