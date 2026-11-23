# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""ir.model.access and ir.rule on Odoo 20, which only has ir.access.

Source security is always the old form: security/ir.model.access.csv and
<record model="ir.rule">. On 20 these two models only keep those rows.
Before each commit that touched them, the ir.access rows they mean are
rebuilt (utils/access_merge.py). Below 20 nothing here is defined.
"""

import logging
from collections import defaultdict

from odoo import SUPERUSER_ID, api, fields, models

from ..utils.access_merge import OPS, merge_model_access
from ..utils.compat import ODOO_VERSION
from ..utils.version_gates import applies_access_merge

_logger = logging.getLogger(__name__)

_SYNC_KEY = 'pns_base.legacy_access_sync'


def _schedule_sync(env):
    """Rebuild the ir.access rows once, before this transaction commits."""
    cr = env.cr
    if cr.precommit.data.get(_SYNC_KEY):
        return
    cr.precommit.data[_SYNC_KEY] = True

    @cr.precommit.add
    def _sync():
        api.Environment(cr, SUPERUSER_ID, {})['ir.model.access']._pns_sync_access()


if applies_access_merge(ODOO_VERSION):

    class IrAccess(models.Model):
        _inherit = 'ir.access'

        pns_legacy = fields.Boolean(readonly=True, copy=False, index=True)

    class IrModelAccess(models.Model):
        _name = 'ir.model.access'
        _description = 'Model Access (old form)'
        _order = 'model_id, group_id, name, id'

        name = fields.Char(required=True, index=True)
        active = fields.Boolean(default=True)
        model_id = fields.Many2one('ir.model', required=True, index=True, ondelete='cascade')
        group_id = fields.Many2one('res.groups', index=True, ondelete='cascade')
        perm_read = fields.Boolean()
        perm_write = fields.Boolean()
        perm_create = fields.Boolean()
        perm_unlink = fields.Boolean()

        @api.model_create_multi
        def create(self, vals_list):
            records = super().create(vals_list)
            _schedule_sync(self.env)
            return records

        def write(self, vals):
            result = super().write(vals)
            _schedule_sync(self.env)
            return result

        def unlink(self):
            _schedule_sync(self.env)
            return super().unlink()

        @api.model
        def _pns_sync_access(self):
            """Replace the ir.access rows built from the old rows.

            While modules load, a later module's models are not in the
            registry yet and Odoo cannot check a domain on them: their rows
            stay as they are until that module's own data runs the sync.
            """
            def loaded(records):
                return records.filtered(lambda rec: rec.model_id.model in self.env)

            Access = self.env['ir.access'].sudo().with_context(active_test=False)
            loaded(Access.search([('pns_legacy', '=', True)])).unlink()

            everyone = self.env.ref('base.group_everyone', raise_if_not_found=False)
            acls = loaded(self.sudo().search([]))
            rules = loaded(self.env['ir.rule'].sudo().search([]))
            by_model = defaultdict(lambda: ([], []))
            for acl in acls:
                group = acl.group_id or everyone
                if not group:
                    _logger.warning('%s: no group and no base.group_everyone; left out', acl.name)
                    continue
                by_model[acl.model_id][0].append({
                    'name': acl.name,
                    'group': group.id,
                    'ops': {op for op, _letter in OPS if acl['perm_' + op]},
                })
            for rule in rules:
                by_model[rule.model_id][1].append({
                    'name': rule.name,
                    'groups': rule.groups.ids,
                    'domain': (rule.domain_force or '').strip(),
                    'ops': {op for op, _letter in OPS if rule['perm_' + op]},
                })

            groups = acls.group_id | rules.groups | (everyone or self.env['res.groups'])
            implied = {group.id: set(group.all_implied_ids.ids) for group in groups}
            vals_list = []
            for model, (model_acls, model_rules) in by_model.items():
                rows, warnings = merge_model_access(model_acls, model_rules, implied)
                for warning in warnings:
                    _logger.warning('%s: %s', model.model, warning)
                vals_list += [{
                    'name': row['name'],
                    'model_id': model.id,
                    'group_id': row['group'] or False,
                    'operation': row['operation'],
                    'domain': row['domain'] or False,
                    'pns_legacy': True,
                } for row in rows if row['operation']]
            Access.create(vals_list)

    class IrRule(models.Model):
        _name = 'ir.rule'
        _description = 'Record Rule (old form)'
        _order = 'model_id, name, id'

        name = fields.Char(index=True)
        active = fields.Boolean(default=True)
        model_id = fields.Many2one('ir.model', required=True, index=True, ondelete='cascade')
        groups = fields.Many2many('res.groups', 'rule_group_rel', 'rule_group_id', 'group_id')
        domain_force = fields.Text()
        perm_read = fields.Boolean(default=True)
        perm_write = fields.Boolean(default=True)
        perm_create = fields.Boolean(default=True)
        perm_unlink = fields.Boolean(default=True)

        @api.model_create_multi
        def create(self, vals_list):
            records = super().create(vals_list)
            _schedule_sync(self.env)
            return records

        def write(self, vals):
            result = super().write(vals)
            _schedule_sync(self.env)
            return result

        def unlink(self):
            _schedule_sync(self.env)
            return super().unlink()
