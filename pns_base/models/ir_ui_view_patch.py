# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""Single-branch view compatibility for pns_* XML.

pns_* view XML is always written in the old syntax (attrs, <tree>), native
on Odoo 13–16. On 17+ this patch converts attrs to
invisible/readonly/required=\"expression\". On 18+ it also rewrites
<tree> to <list> and view_mode tree→list. It lives in pns_base
so each module does not copy it.

A view is treated as PNS when its record xml_id module is pns_*. Programmatic
create/write without xml_id uses name/model hints. Conversion only runs when
old syntax is present, so an extra hint never rewrites a new-syntax view.

If an attrs cannot be converted, an ERROR is logged and the attrs is left
as-is so the failure is visible on Odoo 17+.
"""

import ast
import html
import re
import logging

from lxml import etree

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


PNS_VIEW_CLASS = 'o_pns_view'


def _add_pns_view_class(arch):
    """Mark the arch root so CSS/JS only touch PNS views."""
    if not arch or not isinstance(arch, str):
        return arch
    if PNS_VIEW_CLASS in arch[:500]:
        return arch
    try:
        root = etree.fromstring(arch.encode('utf-8'))
    except Exception:
        return arch
    cls = root.get('class') or ''
    if PNS_VIEW_CLASS not in cls.split():
        root.set('class', (cls + ' ' + PNS_VIEW_CLASS).strip())
    return etree.tostring(root, encoding='unicode')


def _view_is_pns_owned(view):
    return bool(view) and _is_pns_module(_module_from_xmlid(view.xml_id))


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
    """Replace tree→list in view_mode and nested act_window.view commands (O18+).

    Odoo 17 still uses view_mode 'tree'; 'list' exists from 18. No-op on 17.
    """
    from ..utils.version_gates import applies_tree_to_list
    from ..utils.compat import ODOO_VERSION
    if not applies_tree_to_list(ODOO_VERSION):
        return
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
    de forma nativa en Odoo 13-16. En 17+ convierte attrs a expresion; en 18+
    tambien <tree> a <list>.
    """
    _inherit = 'ir.ui.view'

    @api.model
    def _load_records(self, data_list, update=False):
        """Override: convert attrs→expression and tree→list for PNS views on load (O17+)."""
        from ..utils.compat import ODOO_VERSION
        from ..utils.version_gates import applies_attrs_convert, applies_tree_to_list
        for data in data_list:
            vals = data.get('values', {})
            _alias_groups_vals(vals, self._fields)
        if applies_attrs_convert(ODOO_VERSION):
            for data in data_list:
                vals = data.get('values', {})
                if _record_is_pns(data):
                    _convert_arch_fields(vals, self._auto_convert_attrs)
                    # 'tree' is valid on O17; only drop it on 18+ after <list>.
                    if applies_tree_to_list(ODOO_VERSION) and vals.get('type') == 'tree':
                        vals.pop('type', None)
        return super(IrUiView, self)._load_records(data_list, update)

    @api.model_create_multi
    def create(self, vals_list):
        """Override: convert attrs→expression for programmatically created PNS views (O17+)."""
        from ..utils.compat import ODOO_VERSION
        from ..utils.version_gates import applies_attrs_convert, applies_tree_to_list
        for vals in vals_list:
            _alias_groups_vals(vals, self._fields)
            if applies_attrs_convert(ODOO_VERSION) and _view_vals_look_pns(vals):
                _convert_arch_fields(vals, self._auto_convert_attrs)
                if applies_tree_to_list(ODOO_VERSION) and vals.get('type') == 'tree':
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

    def _compute_arch(self):
        """Convert a file arch before Odoo 19 validates it.

        With ``--dev=xml`` (and on any read of ``arch_fs``), Odoo checks the
        file, not the converted copy stored in ``arch_db``. The file keeps
        ``attrs`` / ``<tree>``. The check then raises "attrs are no longer
        used" even though the write path already rewrote the database copy.
        """
        super(IrUiView, self)._compute_arch()
        from ..utils.compat import ODOO_VERSION
        from ..utils.version_gates import applies_attrs_convert
        if not applies_attrs_convert(ODOO_VERSION):
            return
        for view in self:
            arch = view.arch
            if not arch or ('attrs=' not in arch and '<tree' not in arch):
                continue
            if not (
                _is_pns_module(_module_from_xmlid(view.xml_id))
                or _hint(view.name, _PNS_NAME_HINTS)
                or _hint(view.model, _PNS_MODEL_HINTS)
            ):
                continue
            view.arch = view._auto_convert_attrs(arch)

    @api.model
    def _auto_convert_attrs(self, arch):
        """Core transformer: rewrite old-style XML arch for Odoo 17+ compatibility.

        Transformations applied (in order):
          1. (O17+) ``attrs="{...}"`` → individual ``invisible/readonly/required="expr"``
          2. (O18+) ``<tree>`` → ``<list>``
          3. (O18+) Static ``invisible="1"`` inside ``<list>`` → ``column_invisible="True"``
          4. (O19+) res.config.settings xpath fix for new base form layout

        ``<list>`` and view type/mode 'list' exist from Odoo 18; on Odoo 17
        the list view is still ``<tree>``, so steps 2-3 must not run.

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

        from ..utils.compat import ODOO_VERSION
        from ..utils.version_gates import applies_tree_to_list

        # 2) <tree> -> <list> (O18+; on O17 the list tag is still <tree>).
        if applies_tree_to_list(ODOO_VERSION):
            arch = re.sub(r'<tree\b', '<list', arch)
            arch = arch.replace('</tree>', '</list>')

            # 3) invisible="1" estatico dentro de <list> -> column_invisible="True"
            def replace_invisible_in_list(match):
                """Replace static invisible='1' with column_invisible='True' inside <list> blocks."""
                return match.group(0).replace('invisible="1"', 'column_invisible="True"')
            arch = re.sub(r'<list\b.*?</list>', replace_invisible_in_list, arch, flags=re.DOTALL)

        # 4) res.config.settings en Odoo 19+
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
        """Override: replace 'tree' with 'list' in view_mode for PNS actions (O18+)."""
        for data in data_list:
            vals = data.get('values', {})
            _alias_groups_vals(vals, self._fields)
            if _record_is_pns(data):
                _normalize_act_window_view_modes(vals)
        return super(IrActionsActWindow, self)._load_records(data_list, update)

    @api.model_create_multi
    def create(self, vals_list):
        """Override: replace 'tree' with 'list' in view_mode for new PNS actions (O18+)."""
        for vals in vals_list:
            _alias_groups_vals(vals, self._fields)
            if _action_vals_look_pns(vals):
                _normalize_act_window_view_modes(vals)
        return super(IrActionsActWindow, self).create(vals_list)

    def write(self, vals):
        """Override: replace 'tree' with 'list' in view_mode when updating PNS actions (O18+)."""
        from ..utils.compat import ODOO_VERSION
        from ..utils.version_gates import applies_tree_to_list
        _alias_groups_vals(vals, self._fields)
        if applies_tree_to_list(ODOO_VERSION) and 'view_mode' in vals:
            for record in self:
                if _hint(record.res_model, _PNS_MODEL_HINTS):
                    vals['view_mode'] = vals['view_mode'].replace('tree', 'list')
                    break
        return super(IrActionsActWindow, self).write(vals)


class IrActionsActWindowView(models.Model):
    _inherit = 'ir.actions.act_window.view'

    @api.model
    def _load_records(self, data_list, update=False):
        """The child row stores one mode. Odoo 19 rejects ``tree`` there."""
        from ..utils.compat import ODOO_VERSION
        from ..utils.version_gates import applies_tree_to_list
        if applies_tree_to_list(ODOO_VERSION):
            for data in data_list:
                vals = data.get('values', {})
                if _record_is_pns(data) and vals.get('view_mode') == 'tree':
                    vals['view_mode'] = 'list'
        return super(IrActionsActWindowView, self)._load_records(data_list, update)


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


class Base(models.AbstractModel):
    _inherit = 'base'

    @api.model
    def fields_view_get(self, view_id=None, view_type='form', toolbar=False, submenu=False):
        res = super(Base, self).fields_view_get(
            view_id=view_id, view_type=view_type, toolbar=toolbar, submenu=submenu,
        )
        view = self.env['ir.ui.view'].browse(res.get('view_id'))
        if _view_is_pns_owned(view):
            res['arch'] = _add_pns_view_class(res.get('arch') or '')
        return res
