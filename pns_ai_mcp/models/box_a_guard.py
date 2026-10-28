# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 Seges
# Seges: parche 18 (PNS-19, seguridad). Ver docs/pendiente/parches_pns_ai.md
"""Credentials out of reach of box A (relaxaicode's read-only cursor).

``tool_relaxaicode`` marks the box A cursor. On that cursor, the models
below only give out their identification fields, whatever the way in:
a relation, ``env.ref``, ``new()``, a ``Reference`` field, ``read``,
``read_group`` or a domain. Nothing here looks at ``su`` or ``sudo``.
"""
import re
from contextlib import contextmanager

from odoo import _, api, models
from odoo.exceptions import AccessError
from odoo.models import NewId, regex_field_agg

BOX_A_MARK = '_seges_box_a'

# Fields each closed model gives out in box A: id, display_name and _rec_name.
BOX_A_FIELD_ALLOW = {
    'ai.provider': frozenset({'id', 'display_name', 'name'}),
    'ai.api.server': frozenset({'id', 'display_name', 'name'}),
    'ai.api.server.key': frozenset({'id', 'display_name', 'user_id'}),
    'ai.mcp.user': frozenset({'id', 'display_name', 'user_id'}),
    'ai.key.pin.ask': frozenset({'id', 'display_name'}),
    # Its _rec_name is the token itself: not even display_name.
    'ai.key.pin.desk': frozenset({'id'}),
    'ai.api.key.wizard': frozenset({'id', 'display_name'}),
    'ir.mail_server': frozenset({'id', 'display_name', 'name'}),
    'fetchmail.server': frozenset({'id', 'display_name', 'name'}),
    'iap.account': frozenset({'id', 'display_name', 'service_name'}),
    # value: only for rows whose key is not blocked, and never in a domain.
    'ir.config_parameter': frozenset({'id', 'display_name', 'key', 'value'}),
}
_ICP_BLOCKED_KEY = re.compile(
    r'secret|password|passwd|token|api_key|apikey|private', re.IGNORECASE)


def _in_box_a(cr):
    return bool(getattr(cr, BOX_A_MARK, False))


def _icp_key_blocked(key):
    return bool(key) and bool(_ICP_BLOCKED_KEY.search(key))


def _box_a_clear_cache(env):
    """Drop what box A may not read from the cache, for every env.

    The cache is one per thread, not per cursor: what the engine read on
    its own cursor would be served to box A without a ``_fetch_field``.
    """
    spec = []
    for model_name, allowed in BOX_A_FIELD_ALLOW.items():
        if model_name not in env.registry:
            continue
        fields = env.registry[model_name]._fields
        spec.extend(
            (field, None) for name, field in fields.items()
            if name not in allowed or (
                model_name == 'ir.config_parameter' and name == 'value'))
    env.cache.invalidate(spec)


@contextmanager
def _box_a_trusted(env):
    """Lift the mark for engine code that must read a provider in box A.

    Only for code that runs no sandbox code and takes plain data (the
    Chatboo canvas design call). The mark comes back on any way out, and
    what the call left in the cache goes with it.
    """
    cr = env.cr
    marked = _in_box_a(cr)
    if marked:
        setattr(cr, BOX_A_MARK, False)
    try:
        yield
    finally:
        if marked:
            setattr(cr, BOX_A_MARK, True)
            _box_a_clear_cache(env)


def _field_names(specs):
    """Field names in read/read_group specs ('amount:sum', 'date:month')."""
    if isinstance(specs, str):
        specs = [specs]
    names = []
    for spec in specs or ():
        if isinstance(spec, str):
            names.append(spec.split(':', 1)[0].split('.', 1)[0].strip())
    return names


def _agg_field_names(specs):
    """Names in read_group fields: the alias and the field ('x:max(y)')."""
    if isinstance(specs, str):
        specs = [specs]
    names = []
    for spec in specs or ():
        # Odoo skips these two; anything it cannot parse, it refuses.
        if not isinstance(spec, str) or spec in ('sequence', '__count'):
            continue
        match = regex_field_agg.match(spec)
        if not match:
            continue
        name, func, fname = match.groups()
        names.append(name)
        if func:
            names.append(fname or name)
    return names


def _domain_field_names(domain):
    names = []
    for leaf in domain or ():
        if isinstance(leaf, (list, tuple)) and len(leaf) == 3 \
                and isinstance(leaf[0], str):
            names.append(leaf[0].split('.', 1)[0])
    return names


class Base(models.AbstractModel):
    _inherit = 'base'

    def _box_a_allowed(self):
        """Allowed fields when this model is closed in box A, else ``None``."""
        if not _in_box_a(self.env.cr):
            return None
        return BOX_A_FIELD_ALLOW.get(self._name)

    def _box_a_refuse(self, fname):
        raise AccessError(_(
            'Field %(field)s of %(model)s cannot be read from the RelaxAICode '
            'sandbox.', field=fname, model=self._name))

    def _box_a_blocked_icp_rows(self):
        if self._name != 'ir.config_parameter':
            return False
        ids = []
        for rid in self._ids:
            if isinstance(rid, NewId):
                rid = rid.origin
                if rid is None:
                    continue
            # browse(7.0) or browse('7') reach the same row in SQL.
            if type(rid) is not int:  # pylint: disable=unidiomatic-typecheck
                return True
            ids.append(rid)
        if not ids:
            return False
        ids = tuple(ids)
        # SQL, not the ORM: reading the key here must not come back to _read.
        self.env.cr.execute(
            'SELECT key FROM ir_config_parameter WHERE id IN %s', (ids,))
        return any(_icp_key_blocked(key) for key, in self.env.cr.fetchall())

    def _box_a_check_read(self, allowed, fnames):
        for fname in fnames:
            if fname not in allowed:
                self._box_a_refuse(fname)
            if fname == 'value' and self._box_a_blocked_icp_rows():
                self._box_a_refuse(fname)

    def _box_a_check_query(self, allowed, fnames):
        for fname in fnames:
            if fname not in allowed or (
                    self._name == 'ir.config_parameter' and fname == 'value'):
                self._box_a_refuse(fname)

    def _fetch_field(self, field):
        allowed = self._box_a_allowed()
        if allowed is None:
            return super()._fetch_field(field)
        self._box_a_check_read(allowed, [field.name])
        # Without the prefetch: the other columns (api_key…) stay unread.
        return super(Base, self.with_context(prefetch_fields=False))._fetch_field(
            field)

    def read(self, fields=None, load='_classic_read'):
        allowed = self._box_a_allowed()
        if allowed is not None:
            if fields:
                self._box_a_check_read(allowed, _field_names(fields))
            else:
                fields = [name for name in self._fields if name in allowed]
                if 'value' in fields and self._box_a_blocked_icp_rows():
                    fields.remove('value')
        return super().read(fields, load=load)

    def _read(self, fields, *args, **kwargs):
        allowed = self._box_a_allowed()
        if allowed is not None:
            self._box_a_check_read(allowed, _field_names(fields))
        return super()._read(fields, *args, **kwargs)

    @api.model
    def _read_group_raw(self, domain, fields, groupby, *args, **kwargs):
        allowed = self._box_a_allowed()
        if allowed is not None:
            # The domain goes through _where_calc, not _search.
            self._box_a_check_query(allowed, _domain_field_names(domain))
            self._box_a_check_query(allowed, _agg_field_names(fields))
            # groupby has no alias: 'date:month' names the field.
            self._box_a_check_query(allowed, _field_names(groupby))
        return super()._read_group_raw(domain, fields, groupby, *args, **kwargs)

    @api.model
    def _search(self, args, *rest, **kwargs):
        allowed = self._box_a_allowed()
        if allowed is not None:
            self._box_a_check_query(allowed, _domain_field_names(args))
        return super()._search(args, *rest, **kwargs)


class IrConfigParameter(models.Model):
    _inherit = 'ir.config_parameter'

    @api.model
    def get_param(self, key, *args, **kwargs):
        # Before the ormcache of _get_param, which would skip _read.
        if _in_box_a(self.env.cr) and _icp_key_blocked(key):
            self._box_a_refuse('value')
        return super().get_param(key, *args, **kwargs)
