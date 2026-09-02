# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""One-time migration: plaintext MCP API key -> SHA-256 hash.

Older installs stored the user API key in plaintext in ``ai_mcp_user.mcp_api_key``.
From v3.0.30 we keep only a one-way SHA-256 hash in ``mcp_api_key_hash`` and drop
the plaintext column, so no usable credential is left at rest.

This is safe for existing users: their clients (Cursor, Claude Desktop...) already
hold their copy of the key, and the same key keeps validating against the hash.
"""

import hashlib
import logging

_logger = logging.getLogger(__name__)


def migrate_plaintext_key_to_hash(cr):
    """Hash any existing plaintext keys and drop the legacy plaintext column.

    Idempotent and defensive: does nothing on fresh installs or if already
    migrated (the legacy column is gone).
    """
    cr.execute(
        """
        SELECT column_name FROM information_schema.columns
        WHERE table_name = 'ai_mcp_user'
          AND column_name IN ('mcp_api_key', 'mcp_api_key_hash')
        """
    )
    cols = {row[0] for row in cr.fetchall()}

    if 'mcp_api_key' not in cols:
        # Already migrated (or fresh install where the field never existed).
        return

    # The model load should have created the hash column; be defensive anyway.
    if 'mcp_api_key_hash' not in cols:
        cr.execute("ALTER TABLE ai_mcp_user ADD COLUMN mcp_api_key_hash varchar")

    cr.execute(
        """
        SELECT id, mcp_api_key FROM ai_mcp_user
        WHERE mcp_api_key IS NOT NULL AND mcp_api_key <> ''
        """
    )
    rows = cr.fetchall()
    migrated = 0
    for rec_id, raw in rows:
        key_hash = hashlib.sha256(raw.strip().encode('utf-8')).hexdigest()
        cr.execute(
            """
            UPDATE ai_mcp_user
            SET mcp_api_key_hash = %s
            WHERE id = %s
              AND (mcp_api_key_hash IS NULL OR mcp_api_key_hash = '')
            """,
            (key_hash, rec_id),
        )
        migrated += 1

    # Remove the plaintext column entirely: no usable credential remains at rest.
    cr.execute("ALTER TABLE ai_mcp_user DROP COLUMN mcp_api_key")
    _logger.info(
        "pns_ai_mcp: migrated %s plaintext API key(s) to SHA-256 hash and dropped "
        "the plaintext column.", migrated,
    )
