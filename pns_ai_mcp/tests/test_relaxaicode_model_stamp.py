# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 Patanegra Soft <https://patanegra.com>
"""Stamp de __model: fórmula universal (display_name + solape), sin hardcode de dominio."""
from odoo.tests import tagged, TransactionCase

from odoo.addons.pns_ai_mcp.controllers.tools_relaxaicode import (
    _coerce_record_id,
    _iter_all_tabular_row_lists,
    _models_from_code,
    _pick_best_model_fit,
    _related_models_from_code,
    _score_record_fit,
    _stamp_models,
)


@tagged('post_install', '-at_install', 'pns_ai_mcp')
class TestRelaxAICodeModelStamp(TransactionCase):

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
        """Mismo id en dos modelos → gana el cuyo display_name está en la fila."""
        Partner = self.env['res.partner']
        partner = Partner.search([('name', '!=', False)], limit=1)
        if not partner:
            self.skipTest('no res.partner')
        # Modelo inventado en candidatos: el partner encaja por nombre; un move
        # con el mismo id (si existe) no tendrá ese display_name.
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

    def test_related_models_from_product_id(self):
        code = (
            "lines = env['sale.order.line'].search([])\n"
            "pid = lines[0].product_id.id\n"
        )
        extras = _related_models_from_code(
            code, self.env, {'sale.order.line'},
        )
        self.assertIn('product.product', extras)

    def test_stamp_both_sibling_lists_with_env(self):
        product = self.env['product.product'].search([], limit=1)
        if not product:
            self.skipTest('no product.product')
        result = {
            'by_units': [{
                'id': product.id,
                'Producto': product.display_name,
                'Unidades': 1.0,
            }],
            'by_amount': [{
                'id': product.id,
                'Producto': product.display_name,
                'Importe': 9.0,
            }],
        }
        code = (
            "lines = env['sale.order.line'].search([])\n"
            "Product = env['product.product']\n"
            "p = lines[:1].product_id\n"
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
        self.assertEqual(result['by_units'][0].get('__model'), 'product.product')
        self.assertEqual(result['by_amount'][0].get('__model'), 'product.product')

    def test_stamp_partners_by_display_name_when_id_collides(self):
        """Varios partners: todos enlazables aunque el id choque con otros modelos."""
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
        """Filas sin id: se rellenan emparejando name con el recordset del sandbox."""
        from odoo.addons.pns_ai_mcp.controllers.tools_relaxaicode import (
            _backfill_missing_record_ids,
            _stamp_models,
        )
        Partner = self.env['res.partner']
        partners = Partner.search([('name', '!=', False)], limit=2)
        if len(partners) < 2:
            self.skipTest('need ≥2 partners')
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
        """Sin recordset en namespace: search por _rec_name si hay un solo modelo."""
        from odoo.addons.pns_ai_mcp.controllers.tools_relaxaicode import (
            _backfill_missing_record_ids,
        )
        Partner = self.env['res.partner']
        partner = Partner.search([('name', '!=', False)], limit=1)
        if not partner:
            self.skipTest('no partner')
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

    def test_stamp_from_xmlid_column(self):
        """Celda XML=module.name → __model inequívoco (evita empates de id)."""
        from odoo.addons.pns_ai_mcp.controllers.tools_relaxaicode import (
            _model_id_from_xmlid_row,
        )

        group = self.env.ref('base.group_user')
        result = {
            'data': [{
                'ID': 999999,  # id engañoso a propósito
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
