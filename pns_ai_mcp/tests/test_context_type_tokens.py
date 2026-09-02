# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 Patanegra Soft <https://patanegra.com>
from odoo.tests import tagged, TransactionCase

from odoo.addons.pns_ai_mcp.utils import context_roles


@tagged('post_install', '-at_install', 'pns_ai_mcp')
class TestContextTypeTokens(TransactionCase):
    """Type dropdown must show hub tokens, not translated Domain/Locale."""

    def test_fields_get_uses_tokens(self):
        info = self.env['ai.context'].fields_get(['context_type'])
        selection = info['context_type']['selection']
        self.assertEqual(selection, list(context_roles.TYPE_SELECTION))
        labels = [label for _key, label in selection]
        self.assertEqual(labels, ['core', 'domain', 'locale', 'discovery'])
        self.assertNotIn('Domain', labels)
        self.assertNotIn('Locale', labels)
        self.assertNotIn('Dominio', labels)
