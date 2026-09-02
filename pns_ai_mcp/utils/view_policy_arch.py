# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""View-inherit arch for AI field-modifier policies — no Odoo import.

Old syntax (``required="1"`` / ``attrs``-era attributes, never owl2
``invisible="condition"`` Python expressions) so the same inherit loads on
owl1 and owl2. The engine never embeds business field names; callers pass
model/field as closed args.
"""
from __future__ import annotations

import re

MODIFIERS = ('required', 'readonly', 'invisible', 'domain')
_FIELD_NAME = re.compile(r'^[A-Za-z_][A-Za-z0-9_]*$')
_MODEL_NAME = re.compile(r'^[A-Za-z_][A-Za-z0-9_.]*$')


def xml_escape(text):
    text = '' if text is None else str(text)
    return (
        text.replace('&', '&amp;')
        .replace('<', '&lt;')
        .replace('>', '&gt;')
        .replace('"', '&quot;')
    )


def check_ident(name, what='field'):
    """Raise ValueError if ``name`` is not a safe XML/ORM identifier."""
    pat = _MODEL_NAME if what == 'model' else _FIELD_NAME
    if not name or not pat.match(str(name)):
        raise ValueError('Invalid %s name: %r' % (what, name))
    return str(name)


def field_xpath(field_name, for_required=False):
    """XPath to ``<field name>`` nodes. ``required`` skips display-only copies.

    Contact forms often repeat the same field in ``oe_read_only`` /
    ``oe_edit_only`` (and a static ``invisible="1"`` twin). Marking every
    node required makes Odoo list the same label N times in
    «Invalid fields». Required only applies to editable, visible widgets.
    """
    check_ident(field_name, 'field')
    base = "//field[@name='%s']" % field_name
    if not for_required:
        return base
    return (
        "%s[not(@invisible='1')]"
        "[not(hasclass('oe_read_only'))]"
        "[not(ancestor::*[hasclass('oe_read_only')])]"
        % base
    )


def arch_contains_field(arch, field_name):
    """True when *arch* already shows ``field`` as a ``<field name="…"`` node.

    XPath ``@name='…'`` in a later inherit does not count (that is a
    modifier, not a display).
    """
    if not arch or not field_name:
        return False
    try:
        check_ident(field_name, 'field')
    except ValueError:
        return False
    return bool(re.search(
        r'''<field\b[^>]*\bname\s*=\s*['"]%s['"]''' % re.escape(field_name),
        str(arch),
    ))


def format_domain(domain):
    """Serialize a domain list to the Python-literal string Odoo stores on views.

    ``False`` / ``None`` / ``[]`` mean “clear the domain” → ``[]``.
    """
    if domain is False or domain is None or domain == [] or domain == '[]':
        return '[]'
    if isinstance(domain, str):
        text = domain.strip()
        if not text:
            return '[]'
        if text[0] not in '([':
            raise ValueError('Invalid domain (must be a list or false)')
        return text
    if not isinstance(domain, (list, tuple)):
        raise ValueError('Invalid domain (must be a list or false)')
    return repr(list(domain))


def build_modifier_arch(field_name, modifier, value, uniform=False):
    """Return inherit ``arch`` XML (data/xpath/attributes) for one modifier.

    *value* is a bool for required/readonly/invisible, or a domain list/str
    (or False to clear) for ``domain``. ``uniform=True`` marks every copy
    of the field (high-level ``field_required``).
    """
    if modifier not in MODIFIERS:
        raise ValueError('Unknown view modifier: %r' % modifier)
    xpath = field_xpath(
        field_name,
        for_required=(modifier == 'required' and not uniform),
    )
    if modifier == 'domain':
        attr_value = xml_escape(format_domain(value))
        inner = '<attribute name="domain">%s</attribute>' % attr_value
    else:
        flag = '1' if value else '0'
        inner = '<attribute name="%s">%s</attribute>' % (modifier, flag)
    return (
        '<?xml version="1.0"?>\n'
        '<data>\n'
        '    <xpath expr="%s" position="attributes">\n'
        '        %s\n'
        '    </xpath>\n'
        '</data>\n'
    ) % (xpath, inner)


def policy_xmlid_name(model, field, modifier, view_id):
    """Stable ``ir.model.data`` name (module ``pns_ai_mcp``) for one inherit."""
    check_ident(model, 'model')
    check_ident(field, 'field')
    if modifier not in MODIFIERS:
        raise ValueError('Unknown view modifier: %r' % modifier)
    raw = 'vp_%s_%s_%s_%s' % (
        model.replace('.', '_'), field, modifier, int(view_id),
    )
    return re.sub(r'[^A-Za-z0-9_]', '_', raw)[:80]
