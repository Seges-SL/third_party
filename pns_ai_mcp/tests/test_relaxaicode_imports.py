# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""Contrato del sandbox RelaxAICode sobre imports de red.

`urllib.parse` son funciones puras de texto (quote, urlencode, urlparse...) para
COMPONER/TROCEAR URLs, sin red ni FS: se permite SOLO la forma
`from urllib.parse import <nombre>`. Todo lo demás de red sigue prohibido, y
`import urllib.parse` también (ligaría el paquete `urllib`, desde el que se
alcanzaría urllib.request).
"""
from odoo.tests import tagged, TransactionCase

from odoo.addons.pns_ai_mcp.controllers.validators import (
    validate_relaxaicode_source_ast,
)
from odoo.addons.pns_ai_mcp.controllers.context_builder import guarded_import


@tagged('post_install', '-at_install', 'pns_ai_mcp')
class TestRelaxAICodeImports(TransactionCase):
    """Frontera de red del sandbox: urllib.parse sí (from-import), red no."""

    def _ok(self, code):
        is_valid, err, _req = validate_relaxaicode_source_ast(code)
        return is_valid, err

    def test_from_urllib_parse_import_is_allowed(self):
        for code in (
            "from urllib.parse import quote\nresult = quote('Nueva York')",
            "from urllib.parse import urlencode, urlparse\nresult = urlencode({'a': 1})",
        ):
            is_valid, err = self._ok(code)
            self.assertTrue(is_valid, "Debería permitirse: %s (%s)" % (code, err))

    def test_bare_and_network_urllib_forms_are_blocked(self):
        for code in (
            "import urllib\nresult = 1",
            "import urllib.parse\nresult = 1",
            "from urllib import parse\nresult = 1",
            "from urllib.request import urlopen\nresult = 1",
            "import requests\nresult = 1",
            "import os\nresult = 1",
        ):
            is_valid, _err = self._ok(code)
            self.assertFalse(is_valid, "Debería bloquearse: %s" % code)

    def test_guarded_import_only_allows_urllib_parse_from_form(self):
        # from urllib.parse import quote -> permitido y funcional
        mod = guarded_import('urllib.parse', None, None, ['quote'], 0)
        self.assertEqual(mod.quote('Nueva York'), 'Nueva%20York')

        # import urllib.parse (fromlist vacío) -> bloqueado
        with self.assertRaises(ImportError):
            guarded_import('urllib.parse', None, None, None, 0)

        # red / paquete urllib -> bloqueado
        for name, fromlist in (
            ('urllib', None),
            ('urllib.request', None),
            ('urllib.request', ['urlopen']),
            ('os', None),
        ):
            with self.assertRaises(ImportError):
                guarded_import(name, None, None, fromlist, 0)
