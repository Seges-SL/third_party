# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""Regresión Odoo: render de tablas usa res.lang de la sesión del usuario.

No crea res.users: en O14 los hooks (website_slides, digest, …) rompen el
savepoint del TransactionCase y contagian el resto del suite.
"""
from odoo.tests import tagged, TransactionCase


@tagged('post_install', '-at_install', 'pns_ai_mcp')
class TestRelaxAICodeRenderLocale(TransactionCase):
    """Contrato: locale activo del usuario → separadores + HTML alineado."""

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
        """Usa el usuario del test con lang temporal (rollback del TransactionCase)."""
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
        self.assertIn('o_chatboo_num', html)
        self.assertIn('text-end', html)
        self.assertIn('o_chatboo_data_table', html)
        self.assertIn('o_chatboo_table_block', html)
        self.assertIn('data-chatboo-dataset=', html)
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
        """by_units + by_amount → dos tablas (no sobrescribir la primera)."""
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
        self.assertIn('o_chatboo_namelink', html)
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
        self.assertIn('o_chatboo_namelink', html)

        plain = render_result_html({
            'data': rows,
            '__row_links__': False,
        })
        self.assertNotIn('o_chatboo_namelink', plain)
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
        self.assertIn('o_chatboo_namelink', html)
        self.assertIn('/web#id=99', html)

    def test_fn_column_gets_name_link_not_icon_widget(self):
        """FN (friendly name) enlaza el texto; no columna de icono externa."""
        from odoo.addons.pns_ai_mcp.utils.relaxaicode_render import render_result_html

        html = render_result_html({
            'data': [{
                '__model': 'res.groups',
                'ID': 1,
                'XML': 'base.group_user',
                'FN': 'Tipos de Usuario / Usuario interno',
            }],
        })
        self.assertIn('o_chatboo_namelink', html)
        self.assertIn('/web#id=1', html)
        self.assertIn('Usuario interno', html)
        self.assertNotIn('fa-external-link', html)

    def test_first_textual_column_gets_name_link_not_icon_widget(self):
        """Con una sola fila (cardinalidad empatada), gana la primera textual."""
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
        self.assertIn('o_chatboo_namelink', html)
        self.assertIn('/web#id=33', html)
        self.assertIn('Ana Ejemplo', html)
        self.assertNotIn('fa-external-link', html)
        # Solo la columna elegida es enlace; el resto queda texto plano.
        self.assertNotIn('>ana@example.com</a>', html)
        self.assertNotIn('>Oficina / Ciclo productivo</a>', html)

    def test_high_cardinality_textual_beats_bucket_column(self):
        """Buckets repetidos no enlazan; la etiqueta casi única por fila sí.

        Invariante genérico: preferir columna textual de mayor cardinalidad,
        sin literales de dominio (ni 'Factura' ni 'Horizonte').
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
        self.assertIn('o_chatboo_namelink', html)
        self.assertIn('/web#id=101', html)
        self.assertIn('>DOC/2026/0001</a>', html)
        # Bucket must stay plain text (grouping), not the namelink target.
        self.assertNotIn('>1 mes</a>', html)
        self.assertNotIn('>2 meses</a>', html)

    def test_id_only_row_links_id_never_icon_widget(self):
        """Sin columna label: el id enlaza; nunca columna-widget."""
        from odoo.addons.pns_ai_mcp.utils.relaxaicode_render import render_result_html

        html = render_result_html({
            'data': [{
                '__model': 'res.partner',
                'id': 42,
                'total': 10.0,
            }],
        })
        self.assertIn('o_chatboo_namelink', html)
        self.assertIn('/web#id=42', html)
        self.assertNotIn('fa-external-link', html)
        self.assertNotIn('o_chatboo_rowlink', html)

    def test_no_name_link_hint_allowlist_in_renderer(self):
        """Ancla: no reintroducir allowlists de sinónimos de dominio."""
        import inspect
        from odoo.addons.pns_ai_mcp.utils import relaxaicode_render as rr

        src = inspect.getsource(rr)
        self.assertNotIn('_NAME_LINK_HINTS', src)
        # Sinónimos de negocio no deben volver como tuplas de matching.
        self.assertNotIn("'usuario'", src)
        self.assertNotIn("'producto'", src)
        self.assertNotIn("'empleado'", src)
