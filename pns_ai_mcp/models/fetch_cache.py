# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""Cache of fetch_url results for immutable data."""

import hashlib
import logging
from datetime import timedelta

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class AIFetchCache(models.Model):
    """Exact-URL cache for immutable Safe Plan fetch_url results.

    A row is a single cached GET response keyed by the SHA-256 of the exact
    URL. Entries expire at ``expires_at``; reads ignore expired rows and the
    GC cron removes them. Writes are performed with ``sudo`` so a regular user
    running an agent turn can populate the shared cache.

    This is an OPT-IN cache: it only stores/serves URLs whose domain has a
    positive ``cache_ttl`` in ``ai.url.whitelist``. Live-data domains keep
    ``cache_ttl=0`` and therefore never hit this table.
    """
    _name = 'ai.fetch.cache'
    _description = 'AI Immutable fetch_url Cache'
    _order = 'fetched_at desc'
    _rec_name = 'url'

    url = fields.Char(string='URL', required=True, index=True)
    url_hash = fields.Char(
        string='URL hash',
        required=True,
        index=True,
        help='SHA-256 of the exact URL. Used as the exact-match cache key.',
    )
    status_code = fields.Integer(string='HTTP status')
    content_type = fields.Char(string='Content-Type')
    body = fields.Text(string='Body (truncated)')
    truncated = fields.Boolean(string='Body truncated')
    fetched_at = fields.Datetime(string='Fetched at', index=True)
    expires_at = fields.Datetime(
        string='Expires at',
        index=True,
        help='After this instant the entry is stale and will be ignored / purged.',
    )

    _sql_constraints = [
        ('url_hash_unique', 'UNIQUE(url_hash)', 'A cache entry for this URL already exists.'),
    ]

    # ── keys ──────────────────────────────────────────────────────

    @api.model
    def _hash_url(self, url):
        """SHA-256 hex of the exact URL string (no normalization)."""
        return hashlib.sha256((url or '').encode('utf-8')).hexdigest()

    # ── read / write ──────────────────────────────────────────────

    @api.model
    def get_cached(self, url):
        """Return the cached result dict for ``url`` if fresh, else None.

        The returned dict mirrors the successful ``_execute_fetch_url`` shape
        plus ``_from_cache=True`` so callers/telemetry can tell it was served
        from cache. Expired rows are treated as a miss.
        """
        if not url:
            return None
        now = fields.Datetime.now()
        rec = self.sudo().search([
            ('url_hash', '=', self._hash_url(url)),
            ('expires_at', '>', now),
        ], limit=1)
        if not rec:
            return None
        return {
            'op': 'fetch_url',
            'url': url,
            'success': True,
            'status_code': rec.status_code,
            'content_type': rec.content_type or '',
            'body': rec.body or '',
            'truncated': rec.truncated,
            '_from_cache': True,
        }

    @api.model
    def store(self, url, result, ttl_seconds):
        """Upsert a fresh cache entry for ``url`` from a fetch result dict.

        Only successful results with a positive ``ttl_seconds`` are stored.
        Idempotent per URL: an existing row for the same hash is overwritten.
        Never raises: caching is best-effort and must not break the turn.
        """
        try:
            if not url or not ttl_seconds or ttl_seconds <= 0:
                return
            if not result or not result.get('success'):
                return
            now = fields.Datetime.now()
            expires = now + timedelta(seconds=int(ttl_seconds))
            url_hash = self._hash_url(url)
            vals = {
                'url': url,
                'url_hash': url_hash,
                'status_code': result.get('status_code'),
                'content_type': result.get('content_type') or '',
                'body': result.get('body') or '',
                'truncated': bool(result.get('truncated')),
                'fetched_at': now,
                'expires_at': expires,
            }
            existing = self.sudo().search([('url_hash', '=', url_hash)], limit=1)
            if existing:
                existing.write(vals)
            else:
                self.sudo().create(vals)
        except Exception:
            _logger.warning('ai.fetch.cache: store failed for %s', url, exc_info=True)

    # ── maintenance ───────────────────────────────────────────────

    @api.model
    def gc_expired(self):
        """Cron entry point: delete expired cache rows."""
        now = fields.Datetime.now()
        stale = self.sudo().search([('expires_at', '<=', now)])
        count = len(stale)
        if count:
            stale.unlink()
            _logger.info('ai.fetch.cache: purged %d expired entries', count)
        return count
