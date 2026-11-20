# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 Seges
# Seges: parche 18 (PNS-19, seguridad). Ver docs/pendiente/parches_pns_ai.md
"""In box A, without su, a field is checked when it is read, not when it is fetched.

Odoo 14 only checks a field when it goes to the database (``_fetch_field`` →
``check_field_access_rights``). A value already in the thread cache, or
computed on the spot, comes back from ``Field.__get__`` without any check.
Engine code that reads a credential as sudo during the run leaves it in that
cache, and sandbox code could then read it by id.

Here the read itself is checked, on box A's cursor and without su:

- the vendor's criterion first (``_pns_hidden_column`` / ``_pns_deny_column``,
  ``models/sandbox_secret_read.py``), row by row on ``ir.config_parameter``;
- then the model's read access (``check_access_rights``), except for ``id``.

Hooks: ``__getitem__`` with a text key (``rec['x']``, ``itemgetter``,
``sorted('x')``, ``name_get``, ``export_data``…) and ``mapped`` with a path
(``filtered('x')``, ``filtered_domain``), field by field. The literal reads and
``getattr`` of the sandbox call the same check from ``_read_attr``
(``controllers/context_builder.py``). Sudo reads of the engine are untouched.
"""

from odoo import models

from ..utils.sandbox_secrets import SANDBOX_CURSOR_FLAG


def seges_box_a_reads(records):
    """True on box A's cursor without su (the vendor's ``_pns_sandbox_reads``).

    The flag is looked up in the cursor's own ``__dict__`` first, where
    ``open_readonly_env`` sets it: ``getattr`` would go through
    ``Cursor.__getattr__`` on every read of every cursor in Odoo.
    """
    if not records.env.cr.__dict__.get(SANDBOX_CURSOR_FLAG):
        return False
    return records._pns_sandbox_reads()


class Base(models.AbstractModel):
    _inherit = 'base'

    def _seges_box_a_check_read(self, name):
        """Refuse reading field ``name`` of ``self`` in box A (no-op elsewhere)."""
        if not seges_box_a_reads(self):
            return
        if self._pns_hidden_column(name):
            self._pns_deny_column(name)
        if name != 'id':
            self.check_access_rights('read')

    def __getitem__(self, key):
        if isinstance(key, str):
            self._seges_box_a_check_read(key)
        return super().__getitem__(key)

    def mapped(self, func):
        if not (func and isinstance(func, str) and seges_box_a_reads(self)):
            return super().mapped(func)
        # Odoo's own loop (BaseModel.mapped), with the check on each hop.
        recs = self
        for name in func.split('.'):
            recs._seges_box_a_check_read(name)
            recs = recs._fields[name].mapped(recs)
        return recs
