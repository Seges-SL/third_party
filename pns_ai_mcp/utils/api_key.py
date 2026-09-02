# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""API key hashing helpers.

Design decision (see docs/decisions/api_key_hashing.md)
======================================================
The MCP user API key is an *authentication credential verified by us*, so we
store only a one-way **SHA-256 hash** of it, never the plaintext. The endpoint
receives the raw key (from Cursor, Claude Desktop, Chatboo, etc.), hashes it and
compares against the stored hash:

    search([('mcp_api_key_hash', '=', hash_api_key(raw_key))])

Why SHA-256, deterministic, without salt or pepper:
- The lookup only has the key (no username), so the hash MUST be deterministic
  to allow an O(1) indexed search. A per-record random salt would force an
  O(n) scan and is therefore unusable here.
- Keys are 32 random alphanumeric characters (~190 bits of entropy), so a salt
  (whose job is to protect low-entropy passwords from precomputed tables) adds
  nothing. Deterministic SHA-256 of a high-entropy random token is the standard
  way API tokens are stored.
- A deterministic hash is also what makes the credential *portable*: exporting
  and importing the hash lets the very same key keep validating on another
  instance without the clients noticing.
"""

import hashlib

# Length of a lowercase hex SHA-256 digest. Used to tell an already-hashed value
# (new exports) apart from a legacy plaintext key (old exports / manual paste).
SHA256_HEX_LEN = 64


def hash_api_key(raw_key):
    """Return the deterministic SHA-256 hex digest of ``raw_key``.

    Returns an empty string for falsy input so callers can store ``False``
    cleanly (Odoo Char) without special-casing.
    """
    if not raw_key:
        return ''
    if not isinstance(raw_key, str):
        raw_key = str(raw_key)
    raw_key = raw_key.strip()
    if not raw_key:
        return ''
    return hashlib.sha256(raw_key.encode('utf-8')).hexdigest()


def looks_like_hash(value):
    """Heuristic: True if ``value`` is already a SHA-256 hex digest.

    Used on import to accept both new exports (already hashed) and legacy
    exports / manual pastes (plaintext, which we then hash).
    """
    if not value or not isinstance(value, str):
        return False
    value = value.strip().lower()
    if len(value) != SHA256_HEX_LEN:
        return False
    return all(c in '0123456789abcdef' for c in value)


def normalize_to_hash(value):
    """Return the stored hash for an incoming value.

    - If ``value`` already looks like a SHA-256 hash, return it as-is (new
      export / instance-to-instance hash move).
    - Otherwise treat it as a plaintext key and hash it (legacy export or an
      admin pasting a key from a client such as Cursor).
    """
    if looks_like_hash(value):
        return value.strip().lower()
    return hash_api_key(value)
