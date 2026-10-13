# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 Patanegra Soft <https://patanegra.com>
"""Required fields read from the models this instance actually has."""
from odoo.tests import tagged, TransactionCase

from odoo.addons.pns_ai_mcp.controllers.safe_plan import (
    execute_safe_plan,
    validate_safe_plan,
)
from odoo.addons.pns_ai_mcp.utils.required_fields import (
    form_pending_by_record,
    missing_required_fields,
)


@tagged('post_install', '-at_install', 'pns_ai_mcp')
class TestRequiredFieldsLive(TransactionCase):

    def test_a_field_with_no_default_is_asked_for(self):
        found = dict(missing_required_fields(self.env, 'res.partner.category', {}))
        self.assertIn('name', found)

    def test_giving_it_is_enough(self):
        self.assertEqual(
            missing_required_fields(
                self.env, 'res.partner.category', {'name': 'Bailén'},
            ),
            [],
        )

    def test_what_the_instance_fills_alone_is_never_asked(self):
        """No model may ask for a field Odoo would have filled by itself."""
        for model in ('res.partner', 'res.partner.category', 'res.users'):
            Model = self.env[model]
            for name, _label in missing_required_fields(self.env, model, {}):
                field = Model._fields[name]
                self.assertFalse(field.related, '%s.%s is related' % (model, name))
                self.assertFalse(
                    field.compute and not field.inverse,
                    '%s.%s is computed' % (model, name),
                )
                self.assertFalse(
                    Model.default_get([name]).get(name),
                    '%s.%s has a default' % (model, name),
                )

    def test_the_plan_never_reaches_a_confirm_without_them(self):
        ok, error = validate_safe_plan(
            [{'op': 'create', 'model': 'res.partner.category', 'values': {}}],
            self.env,
        )
        self.assertFalse(ok)
        self.assertIn('name', error)

    def test_a_complete_plan_goes_through(self):
        ok, error = validate_safe_plan(
            [{
                'op': 'create',
                'model': 'res.partner.category',
                'values': {'name': 'Bailén'},
            }],
            self.env,
        )
        self.assertTrue(ok, error)

    def test_what_only_the_form_asks_for_does_not_hold_the_alta_back(self):
        """A form-only required field lets the record be born, and is pending."""
        partner = self.env['res.partner'].create({'name': 'Ficha a medias'})
        pending = form_pending_by_record(self.env, 'res.partner', partner)
        for name, _label in pending.get(partner.id, []):
            # Whatever is pending was never a reason to block: the record exists.
            self.assertNotIn(
                name,
                dict(missing_required_fields(self.env, 'res.partner', {})),
            )

    def _as_writer(self):
        self.env.user.groups_id |= self.env.ref('pns_ai_mcp.group_ai_writer')

    def test_a_pending_field_is_left_on_the_record_itself(self):
        """The note goes to the chatter, so the hole outlives the conversation."""
        if 'crm.lead' not in self.env:
            self.skipTest('crm not installed')
        self._as_writer()
        row = execute_safe_plan(self.env, [{
            'op': 'create', 'model': 'crm.lead', 'values': {'name': 'Aviso a medias'},
        }])[0]
        if not row.get('pending'):
            self.skipTest('this form asks for nothing beyond the model')
        lead = self.env['crm.lead'].browse(row['id'])
        bodies = ' '.join(lead.message_ids.mapped('body'))
        self.assertIn('Still to fill in', bodies.replace('&nbsp;', ' '))

    def test_a_record_with_nothing_missing_gets_no_note(self):
        self._as_writer()
        row = execute_safe_plan(self.env, [{
            'op': 'create',
            'model': 'res.partner',
            'values': {'name': 'Ficha completa'},
        }])[0]
        if row.get('pending'):
            self.skipTest('this partner form asks for extra fields')
        partner = self.env['res.partner'].browse(row['id'])
        bodies = ' '.join(partner.message_ids.mapped('body') or [])
        self.assertNotIn('Still to fill in', bodies)
