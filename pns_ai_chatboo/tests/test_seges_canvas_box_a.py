# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 Seges
# Seges: parche 18 (tests de la entrega E2′). Ver docs/pendiente/parches_pns_ai.md
"""Parche 18 (PNS-19), excepción del lienzo: ``_ask_design`` lee el proveedor
dentro de la caja A (``page_url`` y ``page_edit`` lo llaman desde el sandbox).

La ventana (``_box_a_trusted``) quita la marca solo durante la llamada de
diseño: entra texto plano, sale solo el diseño (``content`` y ``error``) y la
marca vuelve también si la llamada falla. El driver está sustituido: lee la
clave del proveedor, como el real, sin red.

La caché es una por hilo: lo que la llamada de diseño deja en ella se vacía al
cerrar la ventana. Por eso aquí no se vacía a mano: la marca se pone como en
``tool_relaxaicode`` y la lectura posterior es ``rec.campo``, como en el sandbox.
"""

from unittest import mock

from odoo.exceptions import AccessError
from odoo.tests import TransactionCase, tagged

from odoo.addons.pns_ai_mcp.models.box_a_guard import BOX_A_MARK, _box_a_clear_cache

API_KEY = 'sk-seges-e2p-19-design'
LLM = 'odoo.addons.pns_ai_mcp.utils.agent_engine.llm_completion_for_agent'
REFUSED = 'cannot be read from the RelaxAICode sandbox'


@tagged('post_install', '-at_install', 'pns_ai_chatboo', 'seges_e2p')
class TestSegesCanvasBoxA(TransactionCase):

    def setUp(self):
        super().setUp()
        self.provider = self.env['ai.provider'].sudo().create({
            'name': 'Seges E2p 19 design', 'api_key': API_KEY,
            'endpoint': 'https://seges.invalid/v1/chat/completions',
        })
        self.session = self.env['chatboo.session'].create({'name': 'Seges E2p 19'})
        self.env['base'].flush()
        # Como tool_relaxaicode al abrir la caja A.
        setattr(self.env.cr, BOX_A_MARK, True)
        self.addCleanup(setattr, self.env.cr, BOX_A_MARK, False)
        _box_a_clear_cache(self.env)
        self.seen = []

    def _driver(self, env, system, prompt, **kwargs):
        """Como el driver real: lee la clave del proveedor con el entorno recibido."""
        self.seen.append((system, prompt, getattr(env.cr, BOX_A_MARK, False)))
        key = env['ai.provider'].sudo().browse(self.provider.id).api_key
        return {
            'content': '<html>seges</html>', 'error': '',
            'usage': {'total_tokens': 1}, 'provider': self.provider,
            'api_key': key,
        }

    def _driver_prefetch(self, env, system, prompt, **kwargs):
        """Lee otro campo del proveedor: la precarga deja también la clave en la caché."""
        provider = env['ai.provider'].sudo().browse(self.provider.id)
        self.seen.append((provider.name, provider.endpoint,
                          getattr(env.cr, BOX_A_MARK, False)))
        return {'content': '<html>seges</html>', 'error': '',
                'usage': {'total_tokens': 1}, 'provider': provider}

    def test_design_call_reads_provider_in_box_a(self):
        with mock.patch(LLM, side_effect=self._driver):
            result = self.session._ask_design('system', 'prompt', 'laid out')
        self.assertEqual(result['content'], '<html>seges</html>')
        # Dentro de la ventana no había marca; fuera, vuelve.
        self.assertFalse(self.seen[0][2])
        self.assertTrue(getattr(self.env.cr, BOX_A_MARK))

    def test_only_design_leaves_the_window(self):
        with mock.patch(LLM, side_effect=self._driver):
            result = self.session._ask_design('system', 'prompt', 'laid out')
        self.assertEqual(set(result), {'content', 'error'})
        self.assertTrue(all(isinstance(v, str) for v in result.values()))
        self.assertNotIn(API_KEY, repr(result))

    def test_window_takes_plain_strings(self):
        partner = self.env['res.partner'].browse(self.env.user.partner_id.id)
        with mock.patch(LLM, side_effect=self._driver):
            self.session._ask_design(partner, partner, partner)
        system, prompt, _mark = self.seen[0]
        self.assertIsInstance(system, str)
        self.assertIsInstance(prompt, str)

    def test_mark_restored_when_design_fails(self):
        def _broken(env, system, prompt, **kwargs):
            raise RuntimeError('seges e2p 19 driver down')

        with mock.patch(LLM, side_effect=_broken):
            with self.assertRaises(RuntimeError):
                self.session._ask_design('system', 'prompt', 'laid out')
        self.assertTrue(getattr(self.env.cr, BOX_A_MARK))

    def test_guard_still_closed_after_window(self):
        with mock.patch(LLM, side_effect=self._driver):
            self.session._ask_design('system', 'prompt', 'laid out')
        provider = self.env['ai.provider'].sudo().browse(self.provider.id)
        with self.assertRaisesRegex(AccessError, REFUSED):
            self.assertFalse(bool(provider.api_key))
        with self.assertRaisesRegex(AccessError, REFUSED):
            provider.read(['api_key'])

    def test_cache_closed_after_window_prefetch(self):
        """Tras un page_url: el driver precargó el proveedor y la clave no queda a mano."""
        field = self.provider._fields['api_key']
        with mock.patch(LLM, side_effect=self._driver_prefetch):
            self.session._ask_design('system', 'prompt', 'laid out')
        self.assertFalse(self.seen[0][2])
        self.assertFalse(self.env.cache.contains(self.provider, field))
        provider = self.env['ai.provider'].sudo().browse(self.provider.id)
        self.assertEqual(provider.name, 'Seges E2p 19 design')
        with self.assertRaisesRegex(AccessError, REFUSED):
            self.assertFalse(bool(provider.api_key))
