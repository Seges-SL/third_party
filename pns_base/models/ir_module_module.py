# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""Apps "Learn More" must not pull the admin out of Odoo.

The Apps kanban shows "Learn More" (→ manifest ``website``, an external site)
and only falls back to the useful local "Module Info" when ``website`` is
empty. Result: clicking a module's link opens the vendor homepage instead of
the documentation the module itself ships in ``static/description/index.html``.

This override points ``website`` at the module's own shipped index page
(``/<module>/static/description/index.html``, served by Odoo itself) for every
module that actually ships one — including an empty ``website``. Generic, no
per-module or per-vendor list. Modules without a local index keep their
external URL (or empty field) untouched.

Runs after every Apps-list refresh and on registry load (idempotent), so a
later ``-u`` refreshing values from manifests cannot silently revert it.
"""

import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


def _has_local_index(module_name):
    """True when the module ships static/description/index.html (13→19+)."""
    try:
        from odoo.tools import file_path  # Odoo 17+
    except ImportError:
        file_path = None
    if file_path is not None:
        try:
            return bool(
                file_path('%s/static/description/index.html' % module_name)
            )
        except (FileNotFoundError, ValueError):
            return False
    from odoo.modules.module import get_module_resource
    return bool(get_module_resource(
        module_name, 'static', 'description', 'index.html',
    ))


class IrModuleModule(models.Model):
    _inherit = 'ir.module.module'

    pns_index_url = fields.Char(
        compute='_compute_pns_index_url',
        string='Index',
        help='Local Apps index (static/description/index.html) when the module ships one.',
    )

    @api.depends('name')
    def _compute_pns_index_url(self):
        for rec in self:
            if rec.name and _has_local_index(rec.name):
                rec.pns_index_url = '/%s/static/description/index.html' % rec.name
            else:
                rec.pns_index_url = False

    @api.model
    def update_list(self):
        res = super().update_list()
        try:
            self._pns_localize_websites()
        except Exception:
            _logger.warning(
                'pns_base: could not localize module websites', exc_info=True,
            )
        return res

    def _register_hook(self):
        # Registry load runs after update_list during -i/-u (which resets
        # website from the manifests with only base's class loaded), so this
        # re-localizes in the same boot. Idempotent: no-op once rewritten.
        super()._register_hook()
        try:
            self.env['ir.module.module'].sudo()._pns_localize_websites()
        except Exception:
            _logger.warning(
                'pns_base: could not localize module websites', exc_info=True,
            )

    @api.model
    def _pns_localize_websites(self):
        """Point ``website`` at the module's own shipped index.html."""
        mods = self.sudo().with_context(active_test=False).search([])
        changed = 0
        for mod in mods:
            if not _has_local_index(mod.name):
                continue
            local = '/%s/static/description/index.html' % mod.name
            if mod.website == local:
                continue
            mod.write({'website': local})
            changed += 1
        if changed:
            _logger.info(
                'pns_base: pointed %s module website(s) at their local '
                'static/description/index.html', changed,
            )
        return changed
