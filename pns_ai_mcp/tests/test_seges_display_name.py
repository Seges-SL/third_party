# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 Seges
# Seges: parche 40 (F1-2, compatibilidad; test de la fase 2, T1, copiado del laboratorio). Ver
# docs/pendiente/parches_pns_ai.md
"""Parche 40 (F1-2): display_name de ai.provider.model en la 17.

La 17 calcula display_name con _compute_display_name y no llama a name_get
(odoo/models.py:1660-1695): sin el parche, el modelo muestra el slug en lugar
de «título (nombre)», la etiqueta de su name_get (models/ai_provider.py).

Copiado de seges_pruebas_3996/tests/test_display_name_17.py (el [HYPOTHESIS]
de F1-2, test_provider_model_label_from_name_get) como test normal.
"""

from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install', 'pns_ai_mcp', 'seges_t1')
class TestSegesDisplayName(TransactionCase):

    def test_provider_model_label_from_name_get(self):
        rec = self.env['ai.provider.model'].create(
            {'name': 'lab-slug', 'title': 'Lab Title'}
        )
        self.assertEqual((rec.name, rec.title), ('lab-slug', 'Lab Title'))
        self.assertEqual(rec.display_name, 'Lab Title (lab-slug)')
