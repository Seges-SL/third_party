# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 Patanegra Soft <https://patanegra.com>
"""In the AI sandbox a secret column cannot be read, searched or sorted.

The sandbox runs as the asking user on its own read-only cursor, marked by
``get_readonly_env``. On that cursor a column ``utils/sandbox_secrets.py``
calls secret answers like a field of a group the user lacks: reading it
(attribute, ``read``, ``mapped``) or naming it in a domain, an order or a
group by raises AccessError. The rest of the row stays readable. A system
parameter whose key is secret keeps its value out the same way. ``sudo()``
reads (the engine's own helpers) are not touched; the sandbox cannot reach
``sudo()``.

Odoo only checks a field when it is not in the cache yet, so a secret column
is never prefetched: it is read only when someone names it.

Odoo 14 checks fields in ``check_field_access_rights`` and ``_flush_search``;
Odoo 17+ in ``_has_field_access`` / ``_check_field_access``. Each version
calls only its own hooks.
"""

from odoo import api, models
from odoo.exceptions import AccessError

from odoo.addons.pns_base.utils.compat import ODOO_VERSION

from ..utils.sandbox_secrets import (
    cached_setting_params,
    field_is_secret,
    sandbox_cursor,
    secret_column,
    secret_param_key,
)

_COLUMN_DENIED = (
    "RelaxAICode cannot read %s.%s: it holds a credential (key, password or "
    "token), which only a person handles. The rest of the row is readable: "
    "leave this column out of fields, domains, order and group by, and say "
    "that the assistant does not read it. Do not retry another way."
)
_PARAM_DENIED = (
    "RelaxAICode cannot read the system parameter %r: its key names a "
    "credential, which only a person handles. Other parameters are readable "
    "one by one (get_param(key) or record.value); say that the assistant "
    "does not read this one. Do not retry another way."
)


def _forget_values(params):
    forget = getattr(params, 'invalidate_model', None) or params.invalidate_cache
    forget(['value'])


class Base(models.AbstractModel):
    _inherit = 'base'

    def _register_hook(self):
        result = super()._register_hook()
        for name, field in self._fields.items():
            if field.prefetch and field_is_secret(self, name):
                field.prefetch = False
        return result

    def _pns_sandbox_reads(self):
        return sandbox_cursor(self.env.cr) and not self.env.su

    def _pns_hidden_column(self, name):
        return secret_column(self, name)

    def _pns_deny_column(self, name):
        raise AccessError(_COLUMN_DENIED % (self._name, name))

    def _pns_check_search_columns(self, domain, fields, order):
        paths = [
            leaf[0] for leaf in domain or ()
            if isinstance(leaf, (list, tuple)) and leaf and isinstance(leaf[0], str)
        ]
        paths += [f.split(':')[0] for f in fields or () if isinstance(f, str)]
        for part in (order or '').split(','):
            words = part.split()
            if words:
                paths.append(words[0].strip('"'))
        for path in paths:
            model = self.browse()
            for name in path.split('.'):
                field = model._fields.get(name)
                if field is None:
                    break
                if model._pns_hidden_column(name):
                    model._pns_deny_column(name)
                if not field.comodel_name:
                    break
                model = self.env[field.comodel_name]

    # Odoo 17+
    @api.model
    def _has_field_access(self, field, operation):
        if (operation == 'read' and self._pns_sandbox_reads()
                and self._pns_hidden_column(field.name)):
            return False
        return super()._has_field_access(field, operation)

    @api.model
    def _check_field_access(self, field, operation):
        if (operation == 'read' and self._pns_sandbox_reads()
                and self._pns_hidden_column(field.name)):
            self._pns_deny_column(field.name)
        return super()._check_field_access(field, operation)

    # Odoo 14
    @api.model
    def check_field_access_rights(self, operation, fields):
        if operation != 'read' or not self._pns_sandbox_reads():
            return super().check_field_access_rights(operation, fields)
        for name in fields or ():
            if self._pns_hidden_column(name):
                self._pns_deny_column(name)
        allowed = super().check_field_access_rights(operation, fields)
        if fields:
            return allowed
        return [name for name in allowed if not self._pns_hidden_column(name)]

    def _flush_search(self, domain, fields=None, order=None, seen=None):
        if seen is None and self._pns_sandbox_reads():
            self._pns_check_search_columns(domain, fields, order)
        return super()._flush_search(domain, fields=fields, order=order, seen=seen)


class IrConfigParameter(models.Model):
    _inherit = 'ir.config_parameter'

    def _register_hook(self):
        result = super()._register_hook()
        self._fields['value'].prefetch = False
        return result

    def _pns_hidden_column(self, name):
        if name == 'value' and self._pns_secret_rows():
            return True
        return super()._pns_hidden_column(name)

    def _pns_secret_rows(self):
        """True for a search over the model, or when a row's key is secret."""
        if not self:
            return True
        setting_keys = cached_setting_params(self.env)
        return any(
            secret_param_key(key, setting_keys)
            for key in self.sudo().mapped('key')
        )

    def _pns_read_param(self, read, key, default):
        if not sandbox_cursor(self.env.cr):
            return read(key, default)
        if not secret_param_key(key, cached_setting_params(self.env)):
            return read(key, default)
        if not self.env.su:
            raise AccessError(_PARAM_DENIED % (key,))
        # A sudo helper on the sandbox cursor must not leave the value behind.
        value = read(key, default)
        _forget_values(self)
        return value

    @api.model
    def get_param(self, key, default=False):
        return self._pns_read_param(super().get_param, key, default)


if ODOO_VERSION >= 20:

    class BaseCheck(models.AbstractModel):
        """Odoo 20 checks fields in check_field_access; _check_field_access is a dead alias."""
        _inherit = 'base'

        @api.model
        def check_field_access(self, field, operation):
            if (operation == 'read' and self._pns_sandbox_reads()
                    and self._pns_hidden_column(field.name)):
                self._pns_deny_column(field.name)
            return super().check_field_access(field, operation)

    class IrConfigParameterTyped(models.Model):
        """Odoo 20 reads and sets parameters by type; none hands out a secret.

        Odoo 20 also remembers per environment that a field was readable once
        and then skips every check. Whether ``value`` is readable depends on
        the row, so in the sandbox it is checked each time and never remembered.
        """
        _inherit = 'ir.config_parameter'

        def _pns_row_checked(self, field, operation):
            return (operation == 'read' and field.name == 'value'
                    and self._pns_sandbox_reads())

        @api.model
        def has_field_access(self, field, operation):
            if self._pns_row_checked(field, operation):
                return self._has_field_access(field, operation)
            return super().has_field_access(field, operation)

        @api.model
        def check_field_access(self, field, operation):
            if self._pns_row_checked(field, operation):
                if not self._has_field_access(field, operation):
                    self._pns_deny_column(field.name)
                return None
            return super().check_field_access(field, operation)

        @api.model
        def get_str(self, key, default=''):
            return self._pns_read_param(super().get_str, key, default)

        @api.model
        def get_int(self, key, default=0):
            return self._pns_read_param(super().get_int, key, default)

        @api.model
        def get_float(self, key, default=0.0):
            return self._pns_read_param(super().get_float, key, default)

        @api.model
        def get_bool(self, key, default=False):
            return self._pns_read_param(super().get_bool, key, default)

        # A setter returns the old value straight from SQL, before writing.
        @api.model
        def set_str(self, key, value):
            return self._pns_read_param(super().set_str, key, value)

        @api.model
        def set_int(self, key, value):
            return self._pns_read_param(super().set_int, key, value)

        @api.model
        def set_float(self, key, value):
            return self._pns_read_param(super().set_float, key, value)

        @api.model
        def set_bool(self, key, value):
            return self._pns_read_param(super().set_bool, key, value)


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    def get_values(self):
        values = super().get_values()
        if not self._pns_sandbox_reads():
            return values
        return {
            name: value for name, value in values.items()
            if not (name in self._fields and self._pns_hidden_column(name))
        }
