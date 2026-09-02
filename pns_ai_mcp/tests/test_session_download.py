# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""Unit tests for session download helpers (pure functions)."""

import unittest

from odoo.addons.pns_ai_mcp.utils.session_download import (
    build_binary_stored_meta,
    collect_download_chips,
    filename_from_http,
    is_binary_content_type,
    looks_like_binary_bytes,
    mimetype_from_magic_bytes,
)


class TestSessionDownload(unittest.TestCase):
    def test_binary_content_type_pdf(self):
        self.assertTrue(is_binary_content_type('application/pdf'))

    def test_binary_content_type_attachment(self):
        self.assertTrue(is_binary_content_type('text/plain', 'attachment; filename=a.bin'))

    def test_text_json_not_binary(self):
        self.assertFalse(is_binary_content_type('application/json'))

    def test_mimetype_from_magic_bytes_pdf(self):
        self.assertEqual(
            mimetype_from_magic_bytes(b'%PDF-1.4'),
            'application/pdf',
        )

    def test_looks_like_binary_bytes_pdf_without_content_type(self):
        self.assertTrue(looks_like_binary_bytes(b'%PDF-1.4 trailer'))
        self.assertFalse(is_binary_content_type('text/plain'))
        self.assertTrue(
            looks_like_binary_bytes(b'%PDF-1.4 trailer')
            or is_binary_content_type('text/plain')
        )

    def test_looks_like_binary_bytes_json_text(self):
        self.assertFalse(looks_like_binary_bytes(b'{"ok": true, "items": []}'))

    def test_filename_from_content_disposition(self):
        name = filename_from_http(
            'https://example.com/x',
            'application/pdf',
            'attachment; filename="contrato.pdf"',
        )
        self.assertEqual(name, 'contrato.pdf')

    def test_collect_download_chips(self):
        chips = collect_download_chips([
            {'op': 'fetch_url', 'download_chip': {'url': '/web/content/1', 'name': 'a.pdf'}},
            {'op': 'write'},
        ])
        self.assertEqual(len(chips), 1)
        self.assertEqual(chips[0]['name'], 'a.pdf')

    def test_build_binary_stored_meta_success(self):
        meta = build_binary_stored_meta({
            'ok': True,
            'chip': {
                'name': 'a.pdf',
                'url': '/web/content/1?access_token=t',
                'mimetype': 'application/pdf',
                'size': 100,
            },
        }, 'a.pdf', 100)
        self.assertTrue(meta['stored'])
        self.assertIn('chip', meta)

    def test_build_binary_stored_meta_size_limit(self):
        meta = build_binary_stored_meta({
            'ok': False,
            'reason': 'size_limit',
            'max_bytes': 1024,
        }, 'big.pdf', 2048)
        self.assertFalse(meta['stored'])
        self.assertEqual(meta['reason'], 'size_limit')
        self.assertEqual(meta['max_bytes'], 1024)

    def test_build_binary_stored_meta_no_session(self):
        meta = build_binary_stored_meta({
            'ok': False,
            'reason': 'no_session',
        }, 'a.pdf', 50)
        self.assertFalse(meta['stored'])
        self.assertEqual(meta['reason'], 'no_session')


if __name__ == '__main__':
    unittest.main()
