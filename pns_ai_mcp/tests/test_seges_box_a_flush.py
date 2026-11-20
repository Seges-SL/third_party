# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 Seges
# Seges: parche 37 (tests de la fase 3b sobre 3.1.973: flush antes de abrir la caja A). Ver docs/pendiente/parches_pns_ai.md
"""Parche 37 (PNS-104): lo pendiente del llamador no se pierde al cerrar la caja A.

Al cerrar, tool_relaxaicode hace rollback del cursor de la caja A (tools_relaxaicode.py:275).
En Odoo 14, Cursor.rollback llama a clear_env (odoo/sql_db.py:462), que hace env.clear() del
entorno de ese cursor (sql_db.py:82-87): vacía la caché, tocompute y towrite
(odoo/api.py:620-627), que son de todo el hilo. El parche hace flush() del llamador en
open_readonly_env antes de abrir el cursor.

Sin datos confirmados nuevos: la herramienta corre como base.user_admin y el contacto es el
suyo; todo se deshace con la transacción del test.
"""

import json
import secrets

from odoo.tests import TransactionCase, tagged

from odoo.addons.pns_ai_mcp.controllers.controller_helpers import open_readonly_env
from odoo.addons.pns_ai_mcp.controllers.tools_relaxaicode import tool_relaxaicode
from odoo.addons.pns_ai_mcp.tests.seges_common import _StubController

RUN_OK = "result = {'data': [{'v': sum([1, 2, 3])}]}\n"


class _SegesFlushBoom(Exception):
    """Error propio del flush parcheado (test_box_a_open_flush_error_no_cursor)."""


@tagged('post_install', '-at_install', 'pns_ai_mcp', 'seges_e2p')
class TestSegesBoxACallerWrites(TransactionCase):

    def setUp(self):
        super().setUp()
        self.admin = self.env.ref('base.user_admin')
        self.partner = self.admin.partner_id
        self.env['base'].flush()

    def _tool(self, code=RUN_OK):
        stub = _StubController(self.env(user=self.admin))
        return json.dumps(tool_relaxaicode(stub, {'code': code}), default=str)

    def _pending(self, fname):
        towrite = self.env.all.towrite.get('res.partner', {})
        return fname in towrite.get(self.partner.id, {})

    def test_pending_write_survives_box_a_close(self):
        partner = self.partner
        marker = f'seges-3b-pendiente-{secrets.token_hex(4)}'
        partner.write({'comment': marker})
        # Precondición: la escritura está pendiente, no en la BD.
        self.assertIn(partner.id, self.env.all.towrite.get('res.partner', {}))
        text = self._tool()
        self.assertFalse('"isError": true' in text, 'la caja A no corre')
        self.env['base'].flush()
        self.env.cr.execute('SELECT comment FROM res_partner WHERE id = %s', (partner.id,))
        self.assertEqual(
            self.env.cr.fetchone()[0], marker,
            'la escritura pendiente del llamador se perdió al cerrar la caja A')

    def test_pending_compute_survives_box_a_close(self):
        """Un cálculo guardado pendiente (display_name) no se pierde al cerrar.

        Solo el cálculo queda pendiente: name se cambia con SQL directo (write() y
        flush(['name']) ya recalculan display_name en este contacto) y display_name se marca
        con env.add_to_compute (odoo/api.py:702-706).
        """
        partner = self.partner
        new_name = f'Seges 3b nombre {secrets.token_hex(4)}'
        self.env.cr.execute(
            'UPDATE res_partner SET name = %s WHERE id = %s', (new_name, partner.id))
        partner.invalidate_cache(['name'], partner.ids)
        display_name = partner._fields['display_name']
        self.env.add_to_compute(display_name, partner)
        self.assertIn(
            partner, self.env.records_to_compute(display_name),
            'precondición: display_name no está pendiente de calcular')
        text = self._tool()
        self.assertFalse('"isError": true' in text, 'la caja A no corre')
        # Solo SQL: un flush o una lectura del ORM aquí calcularía lo que siguiera pendiente.
        self.env.cr.execute('SELECT display_name FROM res_partner WHERE id = %s', (partner.id,))
        stored = self.env.cr.fetchone()[0] or ''
        self.assertTrue(
            new_name in stored,
            'el cálculo pendiente del llamador se perdió al cerrar la caja A')

    def test_pending_write_box_a_reads_column(self):
        """Condición a: la caja A lee una columna con una escritura pendiente del llamador.

        Sin el valor en la caché (invalidate_cache no hace flush en Odoo 14,
        models.py:5762-5779), la lectura de la caja A va a _read → flush (models.py:3096),
        que escribiría lo pendiente en el cursor READ ONLY.
        """
        partner = self.partner
        marker = f'seges-3b-pendiente-{secrets.token_hex(4)}'
        partner.write({'comment': marker})
        partner.invalidate_cache(['comment'], partner.ids)
        self.assertTrue(self._pending('comment'), 'precondición: comment no está pendiente')
        self.assertFalse(
            self.env.cache.contains(partner, partner._fields['comment']),
            'precondición: comment sigue en la caché')
        text = self._tool(
            f"v = env['res.partner'].browse({partner.id}).comment\n"
            "result = {'data': [{'v': bool(v)}]}\n")
        self.assertFalse('"isError": true' in text, 'la caja A no puede leer la columna')
        self.env['base'].flush()
        self.env.cr.execute('SELECT comment FROM res_partner WHERE id = %s', (partner.id,))
        self.assertEqual(
            self.env.cr.fetchone()[0], marker,
            'la escritura pendiente del llamador se perdió')

    def test_box_a_open_flush_error_no_cursor(self):
        """Si el flush falla, su excepción llega sin convertir y no se abre ningún cursor."""
        base_cls = type(self.env['base'])
        real_flush = base_cls.flush

        def _flush(model, fnames=None, records=None):
            # Solo el flush completo (el del parche); los parciales de Odoo siguen.
            if fnames is None and records is None:
                raise _SegesFlushBoom()
            return real_flush(model, fnames, records)

        registry_cls = type(self.env.registry)
        real_cursor = registry_cls.cursor
        opened = []

        def _cursor(registry):
            cr = real_cursor(registry)
            opened.append(cr)
            return cr

        self.patch(base_cls, 'flush', _flush)
        self.patch(registry_cls, 'cursor', _cursor)
        try:
            with self.assertRaises(_SegesFlushBoom):
                open_readonly_env(self.env(user=self.admin))
        finally:
            for cr in opened:
                cr.rollback()
                cr.close()
        self.assertFalse(opened, 'se abrió un cursor de caja A')
