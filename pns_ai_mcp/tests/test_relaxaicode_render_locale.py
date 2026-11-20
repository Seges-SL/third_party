# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""Odoo regression: table render uses the session user's res.lang.

Does not create res.users: on O14 hooks (website_slides, digest, …) break
the TransactionCase savepoint and poison the rest of the suite.
"""
from odoo.tests import tagged, TransactionCase

from odoo.addons.pns_ai_mcp.tests._helpers import SKIP_CONTACT_ORIGIN


@tagged('post_install', '-at_install', 'pns_ai_mcp')
class TestRelaxAICodeRenderLocale(TransactionCase):
    """Contract: the user's active locale → separators + aligned HTML."""

    def setUp(self):
        super().setUp()
        self.env = self.env(context=dict(self.env.context, **SKIP_CONTACT_ORIGIN))

    def _require_lang(self, code, decimal_point, thousands_sep, date_format):
        Lang = self.env['res.lang'].with_context(active_test=False)
        lang = Lang.search([('code', '=', code)], limit=1)
        if not lang:
            self.skipTest('Idioma %s no instalado en esta BD de pruebas' % code)
        lang.write({
            'active': True,
            'decimal_point': decimal_point,
            'thousands_sep': thousands_sep,
            'date_format': date_format,
        })
        return lang

    def _env_for_lang(self, lang_code, decimal_point, thousands_sep, date_format):
        """Use the test user with a temporary lang (TransactionCase rollback)."""
        self._require_lang(lang_code, decimal_point, thousands_sep, date_format)
        self.env.user.write({'lang': lang_code})
        return self.env(user=self.env.user)

    def test_render_context_from_env_follows_user_lang_es(self):
        from odoo.addons.pns_ai_mcp.utils.relaxaicode_render import (
            render_context_from_env,
            fallback_table_html,
        )

        env = self._env_for_lang('es_ES', ',', '.', '%d/%m/%Y')
        ctx = render_context_from_env(env)
        self.assertEqual(ctx['pk_decimal_sep'], ',')
        self.assertEqual(ctx['pk_thousands_sep'], '.')
        self.assertEqual(ctx['user_lang'], 'es_ES')

        rows = [
            {'codigo': 1, 'cuenta': 'Grupo 1', 'debe': 69960.48, 'saldo': -332132.55},
            {'codigo': 5, 'cuenta': 'Grupo 5', 'debe': 11148960.17, 'saldo': -242368.37},
        ]
        html = fallback_table_html(
            {'data': rows, 'title': 'Balance'},
            summary='Balance 2025',
            render_context=ctx,
        )
        self.assertIn('11.148.960,17', html)
        self.assertIn('o_ai_num', html)
        self.assertIn('text-end', html)
        self.assertIn('o_ai_data_table', html)
        self.assertIn('o_ai_table_block', html)
        self.assertIn('data-ai-dataset=', html)
        self.assertIn('Grupo 1', html)
        self.assertNotIn('11,148,960.17', html)

    def test_render_context_from_env_follows_user_lang_en(self):
        from odoo.addons.pns_ai_mcp.utils.relaxaicode_render import (
            render_context_from_env,
            fallback_table_html,
        )

        env = self._env_for_lang('en_US', '.', ',', '%Y-%m-%d')
        ctx = render_context_from_env(env)
        self.assertEqual(ctx['pk_decimal_sep'], '.')
        self.assertEqual(ctx['pk_thousands_sep'], ',')

        rows = [
            {'cuenta': 'Group 5', 'debe': 11148960.17},
        ]
        html = fallback_table_html(
            {'data': rows},
            summary='Trial balance',
            render_context=ctx,
        )
        self.assertIn('11,148,960.17', html)
        self.assertNotIn('11.148.960,17', html)

    def test_format_number_helpers_follow_locale(self):
        from odoo.addons.pns_ai_mcp.utils.relaxaicode_render import (
            format_amount,
            format_number,
        )

        self.assertEqual(
            format_number(1234.5, decimals=2, decimal_sep=',', thousands_sep='.'),
            '1.234,50',
        )
        self.assertEqual(
            format_amount(854545.0, decimals=2, decimal_sep=',', thousands_sep='.'),
            u'854.545,00 €',
        )
        self.assertEqual(
            format_number(11148960.17, decimals=2, decimal_sep='.', thousands_sep=','),
            '11,148,960.17',
        )

    def test_multi_ranking_sibling_lists_render_both_tables(self):
        """by_units + by_amount → two tables (do not overwrite the first one)."""
        from odoo.addons.pns_ai_mcp.utils.relaxaicode_render import (
            render_result_html,
            _result_groups,
        )

        result = {
            'by_units': [
                {
                    '__model': 'product.template',
                    'id': 1,
                    'Producto': 'Alpha',
                    'Unidades': 10.0,
                    'Importe': 100.0,
                },
            ],
            'by_amount': [
                {
                    '__model': 'product.template',
                    'id': 2,
                    'Producto': 'Beta',
                    'Unidades': 1.0,
                    'Importe': 999.0,
                },
            ],
        }
        groups = _result_groups(result)
        self.assertEqual(len(groups), 2)
        html = render_result_html(result)
        self.assertIn('By units', html)
        self.assertIn('By amount', html)
        self.assertIn('Alpha', html)
        self.assertIn('Beta', html)
        self.assertIn('o_ai_namelink', html)
        self.assertIn('/web#id=1', html)
        self.assertNotIn('fa-external-link', html)

    def test_tables_envelope_and_name_link_opt_out(self):
        from odoo.addons.pns_ai_mcp.utils.relaxaicode_render import render_result_html

        rows = [{
            '__model': 'res.partner',
            'id': 42,
            'name': 'Acme',
            'total': 10.0,
        }]
        html = render_result_html({
            'tables': [
                {'title': 'Uno', 'data': rows},
                {'title': 'Dos', 'data': rows},
            ],
        })
        self.assertIn('Uno', html)
        self.assertIn('Dos', html)
        self.assertIn('o_ai_namelink', html)

        plain = render_result_html({
            'data': rows,
            '__row_links__': False,
        })
        self.assertNotIn('o_ai_namelink', plain)
        self.assertNotIn('fa-external-link', plain)

    def test_name_link_accepts_string_id(self):
        from odoo.addons.pns_ai_mcp.utils.relaxaicode_render import render_result_html

        html = render_result_html({
            'data': [{
                '__model': 'res.partner',
                'id': '99',
                'name': 'StringId',
                'total': 1.0,
            }],
        })
        self.assertIn('o_ai_namelink', html)
        self.assertIn('/web#id=99', html)

    def test_fn_column_gets_name_link_not_icon_widget(self):
        """FN (friendly name) links the text; no external icon column."""
        from odoo.addons.pns_ai_mcp.utils.relaxaicode_render import render_result_html

        html = render_result_html({
            'data': [{
                '__model': 'res.groups',
                'ID': 1,
                'XML': 'base.group_user',
                'FN': 'Tipos de Usuario / Usuario interno',
            }],
        })
        self.assertIn('o_ai_namelink', html)
        self.assertIn('/web#id=1', html)
        self.assertIn('Usuario interno', html)
        self.assertNotIn('fa-external-link', html)

    def test_first_textual_column_gets_name_link_not_icon_widget(self):
        """With a single row (tied cardinality), the first textual column wins."""
        from odoo.addons.pns_ai_mcp.utils.relaxaicode_render import render_result_html

        html = render_result_html({
            'data': [{
                '__model': 'res.users',
                'id': 33,
                'Usuario': 'Ana Ejemplo',
                'Login': 'ana@example.com',
                'Rol': 'Oficina / Ciclo productivo',
            }],
        })
        self.assertIn('o_ai_namelink', html)
        self.assertIn('/web#id=33', html)
        self.assertIn('Ana Ejemplo', html)
        self.assertNotIn('fa-external-link', html)
        # Only the chosen column is a link; the rest stays plain text.
        self.assertNotIn('>ana@example.com</a>', html)
        self.assertNotIn('>Oficina / Ciclo productivo</a>', html)

    def test_high_cardinality_textual_beats_bucket_column(self):
        """Repeated buckets do not link; the almost-unique label per row does.

        Generic invariant: prefer the textual column with the highest
        cardinality, with no domain literals (no 'Factura', no 'Horizonte').
        """
        from odoo.addons.pns_ai_mcp.utils.relaxaicode_render import render_result_html

        rows = [
            {
                '__model': 'account.move',
                'id': 101,
                'Bucket': '1 mes',
                'Label': 'DOC/2026/0001',
                'Due': '2026-09-01',
            },
            {
                '__model': 'account.move',
                'id': 102,
                'Bucket': '1 mes',
                'Label': 'DOC/2026/0002',
                'Due': '2026-09-05',
            },
            {
                '__model': 'account.move',
                'id': 103,
                'Bucket': '2 meses',
                'Label': 'DOC/2026/0003',
                'Due': '2026-10-01',
            },
            {
                '__model': 'account.move',
                'id': 104,
                'Bucket': '2 meses',
                'Label': 'DOC/2026/0004',
                'Due': '2026-10-10',
            },
        ]
        html = render_result_html({'data': rows})
        self.assertIn('o_ai_namelink', html)
        self.assertIn('/web#id=101', html)
        self.assertIn('>DOC/2026/0001</a>', html)
        # Bucket must stay plain text (grouping), not the namelink target.
        self.assertNotIn('>1 mes</a>', html)
        self.assertNotIn('>2 meses</a>', html)

    def test_id_only_row_links_id_never_icon_widget(self):
        """No label column: the id links; never a widget column."""
        from odoo.addons.pns_ai_mcp.utils.relaxaicode_render import render_result_html

        html = render_result_html({
            'data': [{
                '__model': 'res.partner',
                'id': 42,
                'total': 10.0,
            }],
        })
        self.assertIn('o_ai_namelink', html)
        self.assertIn('/web#id=42', html)
        self.assertNotIn('fa-external-link', html)
        self.assertNotIn('o_chatboo_rowlink', html)

    def test_no_name_link_hint_allowlist_in_renderer(self):
        """Anchor: do not bring back allowlists of domain synonyms."""
        from pathlib import Path
        from odoo.addons.pns_ai_mcp.utils import relaxaicode_render as rr

        folder = Path(rr.__file__).parent
        src = '\n'.join(
            p.read_text(encoding='utf-8')
            for p in sorted(folder.glob('relaxaicode_render*.py'))
        )
        self.assertNotIn('_NAME_LINK_HINTS', src)
        # Business synonyms must not come back as matching tuples.
        self.assertNotIn("'usuario'", src)
        self.assertNotIn("'producto'", src)
        self.assertNotIn("'empleado'", src)
