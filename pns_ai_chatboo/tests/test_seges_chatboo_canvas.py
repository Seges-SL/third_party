# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 Seges
# Seges: parches 25 a 29 (tests de la entrega E3′) y 34 (E4′.b). Ver docs/pendiente/parches_pns_ai.md
# Seges: fase 2b sobre 3.1.973, solo los casos de los parches 25, 26 y 28 (los de 27, 29 y 34 vuelven en la fase 4). Ver docs/pendiente/parches_pns_ai.md
"""Entrega E3′, el lienzo (docs/pendiente/e3_propuesta_3879.md, «Propuesta final»).

En la rama 14.0-pns-ai-3973 (fase 2b) solo están los casos de:

- Parche 25 (M1): ``_paint_canvas`` comprueba el dueño (3.1.973 ya lo hizo privado).
- Parche 26 (M2): ``page_html`` y ``open_page`` leen las imágenes sin ``su``.
- Parche 28 (D1): ``user_ids`` solo internos y el AI Administrator solo lee y borra
  páginas ajenas. ``owner_id`` y el alta fuera de ``su`` los cierra ya el fabricante
  (``_SYSTEM_FIELDS`` y ``create``): esos casos quedan como no regresión.

Base ``HttpCase`` (``SegesChatbooCase``): los cursores propios de ``_store_design``
comparten la transacción del test. El driver de diseño está sustituido: sin red.
"""

import base64
import io
from unittest import mock

from PIL import Image

from odoo.exceptions import AccessError, ValidationError
from odoo.tests import tagged
from odoo.tests.common import new_test_user
from odoo.tools import mute_logger

from odoo.addons.pns_ai_mcp.utils.sandbox_helpers import collect_sandbox_helpers

from .common import SegesChatbooCase

LLM = 'odoo.addons.pns_ai_mcp.utils.agent_engine.llm_completion_for_agent'
ROW_NAME = 'Seges E3 fila'
DESIGN = (
    '<!DOCTYPE html><html><head><title>Seges E3</title></head><body>'
    '<div id="out"></div>'
    '<script>const DATA = [{"name": "a", "photo": "b"}];'
    'document.getElementById("out").textContent = DATA.length;</script>'
    '</body></html>'
)


def _png_base64():
    buf = io.BytesIO()
    Image.new('RGB', (16, 16), (200, 30, 30)).save(buf, 'PNG')
    return base64.b64encode(buf.getvalue())



class _SegesCanvasCase(SegesChatbooCase):
    """Dos usuarios internos con su sesión y el driver de diseño simulado."""

    def setUp(self):
        super().setUp()
        self.user_a = new_test_user(
            self.env, login='seges_e3_a', groups='base.group_user',
            password='seges_e3_a',
        )
        self.user_b = new_test_user(
            self.env, login='seges_e3_b', groups='base.group_user',
            password='seges_e3_b',
        )
        Session = self.env['chatboo.session']
        self.session_a = Session.with_user(self.user_a).create({'name': 'Seges E3 a'})
        self.session_b = Session.with_user(self.user_b).create({'name': 'Seges E3 b'})
        self.design_calls = []

    def _driver(self, env, system, prompt, **kwargs):
        self.design_calls.append(prompt)
        return {'content': DESIGN, 'error': '', 'usage': {'total_tokens': 1}}

    def _fresh(self, session):
        session.invalidate_cache()
        return session.sudo()


@tagged('post_install', '-at_install', 'pns_ai_chatboo', 'seges_e3p')
class TestSegesPaintCanvas(_SegesCanvasCase):
    """Parche 25 (M1)."""

    def setUp(self):
        super().setUp()
        self._chat_user('seges_e3_rpc')

    def test_rpc_public_name_gone(self):
        res = self._rpc(
            'seges_e3_rpc', 'chatboo.session', 'paint_canvas',
            [[self.session_b.id], 'Seges E3'],
        )
        self._assert_refused(res, private=False)

    def test_rpc_private_name_refused(self):
        res = self._rpc(
            'seges_e3_rpc', 'chatboo.session', '_paint_canvas',
            [[self.session_b.id], 'Seges E3'],
        )
        self._assert_refused(res, private=True)

    def test_foreign_session_refused(self):
        before = self._fresh(self.session_b)
        design, rev = before.canvas_design, before.canvas_rev
        with mock.patch(LLM, side_effect=self._driver):
            with self.assertRaisesRegex(AccessError, 'belongs to another user'):
                self.session_b.with_user(self.user_a)._paint_canvas(
                    'Seges E3', new_page=True,
                )
        after = self._fresh(self.session_b)
        self.assertEqual(after.canvas_design, design)
        self.assertEqual(after.canvas_rev, rev)
        self.assertFalse(self.design_calls)

    def test_own_session_paints(self):
        with mock.patch(LLM, side_effect=self._driver):
            url = self.session_a.with_user(self.user_a)._paint_canvas(
                'Seges E3', new_page=True,
            )
        session = self._fresh(self.session_a)
        self.assertEqual(url, f'/chatboo/canvas/{session.id}?rev=1')
        self.assertEqual(session.canvas_rev, 1)
        self.assertIn('document.getElementById("out")', session.canvas_design)


@tagged('post_install', '-at_install', 'pns_ai_chatboo', 'seges_e3p')
class TestSegesCanvasPictures(_SegesCanvasCase):
    """Parche 26 (M2): imágenes con los permisos del usuario, también en sudo."""

    def setUp(self):
        super().setUp()
        other = self.env['res.company'].create({'name': 'Seges E3 otra'})
        png = _png_base64()
        Partner = self.env['res.partner']
        # Contacto de otra compañía, sin usuario: la regla multicompañía lo oculta.
        self.hidden = Partner.create({
            'name': 'Seges E3 oculto', 'company_id': other.id, 'image_1920': png,
        })
        self.visible = Partner.create({
            'name': 'Seges E3 visible', 'company_id': False, 'image_1920': png,
        })
        self.env['base'].flush()
        self.helpers = collect_sandbox_helpers(self.env(
            user=self.user_a.id, context={'ai_session_ref': self.session_a.id},
        ))

    def _rows(self, partner):
        return [{
            'name': ROW_NAME,
            'photo': f'/web/image/res.partner/{partner.id}/image_128',
        }]

    def _page_html(self, partner):
        url = self.helpers['page_html'](DESIGN, rows=self._rows(partner))
        self.assertTrue(url)
        return self._fresh(self.session_a).canvas_design

    def _page_url(self, partner):
        with mock.patch(LLM, side_effect=self._driver):
            url = self.helpers['page_url'](self._rows(partner), 'Seges E3')
        self.assertTrue(url)
        return self._fresh(self.session_a).canvas_design

    def test_user_cannot_read_hidden(self):
        partner = self.hidden.with_user(self.user_a)
        self.assertFalse(partner.search([('id', '=', self.hidden.id)]))

    def test_page_html_hidden_picture(self):
        self.assertNotIn('data:image', self._page_html(self.hidden))

    def test_page_url_hidden_picture(self):
        self.assertNotIn('data:image', self._page_url(self.hidden))

    def test_page_html_visible_picture(self):
        self.assertIn('data:image/png;base64,', self._page_html(self.visible))

    def test_page_url_visible_picture(self):
        self.assertIn('data:image/png;base64,', self._page_url(self.visible))


@tagged('post_install', '-at_install', 'pns_ai_chatboo', 'seges_e3p')
class TestSegesSharedPage(_SegesCanvasCase):
    """Parche 28 (D1)."""

    def setUp(self):
        super().setUp()
        self.admin = new_test_user(
            self.env, login='seges_e3_aiadmin',
            groups='base.group_user,pns_ai_mcp.group_ai_admin',
        )
        self.portal = new_test_user(
            self.env, login='seges_e3_portal', groups='base.group_portal',
        )
        # Seges: adaptado a 3.1.973 (el alta es solo en su, como la ruta de compartir). Ver docs/pendiente/parches_pns_ai.md
        Page = self.env['chatboo.canvas.page'].sudo()
        self.page = Page.create({
            'name': 'Seges E3 de a', 'design': DESIGN, 'owner_id': self.user_a.id,
        }).with_user(self.user_a)
        self.admin_page = Page.create({
            'name': 'Seges E3 del admin', 'design': DESIGN,
            'owner_id': self.admin.id,
        }).with_user(self.admin)

    def test_owner_cannot_change_owner(self):
        with self.assertRaises(AccessError):
            self.page.with_user(self.user_a).write({'owner_id': self.user_b.id})
        self.assertEqual(self.page.owner_id, self.user_a)

    def test_ai_admin_cannot_change_owner(self):
        with self.assertRaises(AccessError):
            self.admin_page.with_user(self.admin).write({'owner_id': self.user_b.id})
        with self.assertRaises(AccessError):
            self.page.with_user(self.admin).write({'owner_id': self.admin.id})
        self.assertEqual(self.page.owner_id, self.user_a)

    def test_sudo_changes_owner(self):
        self.page.with_user(self.user_a).sudo().write({'owner_id': self.user_b.id})
        self.assertEqual(self.page.owner_id, self.user_b)

    # Seges: adaptado a 3.1.973 (el fabricante rechaza owner_id fuera de su, aunque no cambie). Ver docs/pendiente/parches_pns_ai.md
    def test_same_owner_refused_too(self):
        with self.assertRaises(AccessError):
            self.page.with_user(self.user_a).write({
                'owner_id': self.user_a.id, 'name': 'Seges E3 renombrada',
            })
        self.assertEqual(self.page.name, 'Seges E3 de a')

    def test_portal_reader_refused(self):
        with mute_logger('odoo.models'), self.assertRaises(ValidationError):
            self.page.with_user(self.user_a).write({'user_ids': [(4, self.portal.id)]})
        # Seges: adaptado a 3.1.973 (el alta es solo en su, como la ruta de compartir). Ver docs/pendiente/parches_pns_ai.md
        with self.assertRaises(ValidationError):
            self.env['chatboo.canvas.page'].sudo().create({
                'design': DESIGN, 'owner_id': self.user_a.id,
                'user_ids': [(6, 0, [self.portal.id])],
            })
        with self.assertRaises(ValidationError):
            self.page.sudo().write({'user_ids': [(4, self.portal.id)]})

    def test_internal_reader_allowed(self):
        self.page.with_user(self.user_a).write({'user_ids': [(4, self.user_b.id)]})
        self.assertEqual(self.page.user_ids, self.user_b)

    def test_ai_admin_reads_and_deletes(self):
        page = self.page.with_user(self.admin)
        self.assertEqual(page.name, 'Seges E3 de a')
        page.unlink()
        self.assertFalse(self.page.exists())

    def test_ai_admin_cannot_write_foreign(self):
        page = self.page.with_user(self.admin)
        with self.assertRaises(AccessError):
            page.write({'name': 'Seges E3 cambiada'})
        with self.assertRaises(AccessError):
            page.action_unshare()
        self.assertEqual(self.page.name, 'Seges E3 de a')

    def test_ai_admin_cannot_create_for_other(self):
        with self.assertRaises(AccessError):
            self.env['chatboo.canvas.page'].with_user(self.admin).create({
                'design': DESIGN, 'owner_id': self.user_a.id,
            })
