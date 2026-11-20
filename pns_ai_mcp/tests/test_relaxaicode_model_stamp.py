# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 Patanegra Soft <https://patanegra.com>
"""__model stamp: universal formula (display_name + overlap), no domain hardcode."""
import uuid

from odoo.tests import tagged, TransactionCase

from odoo.addons.pns_ai_mcp.controllers.relaxaicode_models import (
    _models_from_code,
    _pick_best_model_fit,
    _related_models_from_code,
    _score_record_fit,
    _stamp_models,
)
from odoo.addons.pns_ai_mcp.controllers.relaxaicode_rows import (
    _coerce_record_id,
    _iter_all_tabular_row_lists,
)


@tagged('post_install', '-at_install', 'pns_ai_mcp')
class TestRelaxAICodeModelStamp(TransactionCase):

    def _unique_partners(self, count):
        """Backfill only fills an unambiguous label, so the names are unique."""
        tag = uuid.uuid4().hex[:8]
        return self.env['res.partner'].create([
            {'name': 'ACME Backfill %s %s' % (n, tag)} for n in range(count)
        ])

    def test_coerce_record_id(self):
        self.assertEqual(_coerce_record_id(12), 12)
        self.assertEqual(_coerce_record_id('42'), 42)
        self.assertEqual(_coerce_record_id(3.0), 3)
        self.assertIsNone(_coerce_record_id(True))
        self.assertIsNone(_coerce_record_id('x'))

    def test_iter_all_sibling_lists(self):
        result = {
            'by_units': [{'id': 1, 'Producto': 'A'}],
            'by_amount': [{'id': 2, 'Producto': 'B'}],
        }
        lists = list(_iter_all_tabular_row_lists(result))
        self.assertEqual(len(lists), 2)

    def test_fit_prefers_record_whose_display_name_is_in_row(self):
        """Same id in two models → the one whose display_name is in the row wins."""
        Partner = self.env['res.partner']
        partner = Partner.search([('name', '!=', False)], limit=1)
        if not partner:
            self.skipTest('no res.partner')
        # Made-up model among candidates: the partner fits by name; a move
        # with the same id (if there is one) will not have that display_name.
        row = {
            'id': partner.id,
            'Cliente': partner.name,
            'Importe Pend.': 123.45,
        }
        candidates = ['res.partner']
        Move = self.env['account.move'] if 'account.move' in self.env else None
        if Move is not None and Move.browse(partner.id).exists():
            candidates.append('account.move')
            partner_score = _score_record_fit(
                self.env, 'res.partner', partner.id, row,
            )
            move_score = _score_record_fit(
                self.env, 'account.move', partner.id, row,
            )
            self.assertGreater(partner_score, move_score)
        best = _pick_best_model_fit(self.env, candidates, partner.id, row)
        self.assertEqual(best, 'res.partner')

    def test_related_models_from_many2one_name(self):
        code = (
            "users = env['res.users'].search([])\n"
            "pid = users[0].partner_id.id\n"
        )
        extras = _related_models_from_code(
            code, self.env, {'res.users'},
        )
        self.assertIn('res.partner', extras)

    def test_stamp_both_sibling_lists_with_env(self):
        partner = self.env.user.partner_id
        result = {
            'by_units': [{
                'id': partner.id,
                'Contact': partner.display_name,
                'Units': 1.0,
            }],
            'by_amount': [{
                'id': partner.id,
                'Contact': partner.display_name,
                'Amount': 9.0,
            }],
        }
        code = (
            "users = env['res.users'].search([])\n"
            "p = users[:1].partner_id\n"
        )
        candidates = _models_from_code(code)
        candidates |= _related_models_from_code(code, self.env, candidates)
        _stamp_models(
            result,
            id_model_map={},
            single_model=None,
            env=self.env,
            candidate_models=candidates,
        )
        self.assertEqual(result['by_units'][0].get('__model'), 'res.partner')
        self.assertEqual(result['by_amount'][0].get('__model'), 'res.partner')

    def test_stamp_partners_by_display_name_when_id_collides(self):
        """Several partners: all linkable even if the id clashes with other models."""
        Partner = self.env['res.partner']
        partners = Partner.search([('name', '!=', False)], limit=3)
        if len(partners) < 2:
            self.skipTest('need ≥2 partners')
        result = {
            'data': [
                {
                    'id': p.id,
                    'Cliente': p.name,
                    'Importe Pend.': 10.0 * (i + 1),
                }
                for i, p in enumerate(partners)
            ],
        }
        candidates = {'account.move', 'res.partner', 'account.move.line'}
        _stamp_models(
            result,
            id_model_map={},
            single_model=None,
            env=self.env,
            candidate_models=candidates,
        )
        for i, p in enumerate(partners):
            self.assertEqual(
                result['data'][i].get('__model'),
                'res.partner',
                'row %s (%s) should link to partner' % (p.id, p.name),
            )

    def test_backfill_id_from_namespace_recordset(self):
        """Rows without id: filled by matching name against the sandbox recordset."""
        from odoo.addons.pns_ai_mcp.controllers.relaxaicode_models import (
            _backfill_missing_record_ids,
            _stamp_models,
        )
        partners = self._unique_partners(2)
        result = {
            'data': [
                {'Cliente': p.name, 'Importe': 10.0 * (i + 1)}
                for i, p in enumerate(partners)
            ],
        }
        namespace = {'partners': partners, 'env': self.env}
        filled = _backfill_missing_record_ids(
            result,
            namespace,
            env=self.env,
            single_model='res.partner',
        )
        self.assertEqual(filled, 2)
        for i, p in enumerate(partners):
            self.assertEqual(result['data'][i].get('id'), p.id)
        _stamp_models(
            result,
            id_model_map={p.id: 'res.partner' for p in partners},
            single_model='res.partner',
            env=self.env,
            candidate_models={'res.partner'},
        )
        for i, p in enumerate(partners):
            self.assertEqual(result['data'][i].get('__model'), 'res.partner')

    def test_backfill_id_via_rec_name_search(self):
        """No recordset in namespace: search by _rec_name if there is only one model."""
        from odoo.addons.pns_ai_mcp.controllers.relaxaicode_models import (
            _backfill_missing_record_ids,
        )
        partner = self._unique_partners(1)
        result = {'data': [{'name': partner.name, 'note': 'x'}]}
        filled = _backfill_missing_record_ids(
            result,
            {'env': self.env},
            env=self.env,
            single_model='res.partner',
        )
        self.assertGreaterEqual(filled, 1)
        self.assertEqual(result['data'][0].get('id'), partner.id)

    def test_stamp_string_id(self):
        partner = self.env['res.partner'].search([], limit=1)
        if not partner:
            self.skipTest('no res.partner')
        result = {'data': [{'id': str(partner.id), 'name': partner.name or 'P'}]}
        _stamp_models(
            result,
            id_model_map={},
            single_model='res.partner',
            env=self.env,
            candidate_models={'res.partner'},
        )
        self.assertEqual(result['data'][0]['id'], partner.id)
        self.assertEqual(result['data'][0]['__model'], 'res.partner')

    def test_stamp_from_what_the_turn_already_read(self):
        """Rows rebuilt from a literal: the id keeps its model from the turn.

        The presentation step does not touch the ORM (no recordset, no
        ``env['x']``), so without the turn memory the row would reach the
        screen with no record behind it and could not be pointed at.
        """
        partner = self.env['res.partner'].search([('name', '!=', False)], limit=1)
        if not partner:
            self.skipTest('no res.partner')
        result = {'data': [{'id': partner.id, 'name': partner.name}]}
        _stamp_models(
            result,
            id_model_map={},
            single_model=None,
            env=self.env,
            candidate_models=set(),
            turn_models={partner.id: 'res.partner'},
        )
        self.assertEqual(result['data'][0].get('__model'), 'res.partner')

    def test_a_remembered_id_does_not_lend_its_link_to_another_row(self):
        """Same number, other thing: without the record's name there is no link."""
        partner = self.env['res.partner'].search([('name', '!=', False)], limit=1)
        if not partner:
            self.skipTest('no res.partner')
        result = {'data': [{'id': partner.id, 'concepto': 'Horas', 'total': 12.0}]}
        _stamp_models(
            result,
            id_model_map={},
            single_model=None,
            env=self.env,
            candidate_models=set(),
            turn_models={partner.id: 'res.partner'},
        )
        self.assertIsNone(result['data'][0].get('__model'))

    def test_stamp_from_xmlid_column(self):
        """Cell XML=module.name → unambiguous __model (avoids id ties)."""
        from odoo.addons.pns_ai_mcp.controllers.relaxaicode_rows import (
            _model_id_from_xmlid_row,
        )

        group = self.env.ref('base.group_user')
        result = {
            'data': [{
                'ID': 999999,  # misleading id on purpose
                'XML': 'base.group_user',
                'FN': group.display_name,
            }],
        }
        model, rid = _model_id_from_xmlid_row(self.env, result['data'][0])
        self.assertEqual(model, 'res.groups')
        self.assertEqual(rid, group.id)
        _stamp_models(
            result,
            id_model_map={},
            env=self.env,
            candidate_models={'res.partner', 'res.groups', 'res.users'},
        )
        self.assertEqual(result['data'][0]['__model'], 'res.groups')
        self.assertEqual(result['data'][0]['id'], group.id)

    def test_a_car_name_in_the_model_column_does_not_steal_the_picture(self):
        """The model column holding the car's name is not fleet.vehicle.

        If the requested field does not exist (logo), the thumbnail comes from
        a picture the record does have, not from a URL with that text.
        """
        from odoo.addons.pns_ai_mcp.controllers.relaxaicode_rows import (
            _postprocess_images,
        )

        Partner = self.env['res.partner']
        partner = Partner.search([('image_128', '!=', False)], limit=1)
        if not partner:
            partner = Partner.search([('name', '!=', False)], limit=1)
        if not partner:
            self.skipTest('no res.partner')
        result = {'data': [{
            'id': partner.id,
            'model': 'KANGOO L1 1.5 BLUE 75 CV',
            'name': partner.name,
            'logo': True,
        }]}
        _stamp_models(
            result,
            id_model_map={partner.id: 'res.partner'},
            single_model='res.partner',
            env=self.env,
            candidate_models={'res.partner'},
        )
        self.assertEqual(result['data'][0].get('__model'), 'res.partner')
        _postprocess_images(result, model_hint='res.partner', env=self.env)
        logo = result['data'][0].get('logo')
        self.assertFalse(str(logo or '').startswith('/web/image/KANGOO'))
        if partner.image_128:
            self.assertEqual(
                logo,
                '/web/image/res.partner/%s/image_128' % partner.id,
            )
