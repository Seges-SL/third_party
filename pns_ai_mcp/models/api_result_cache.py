# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""Ephemeral cache of full api_call responses (Safe Plan channel)."""

import json
import logging
from datetime import timedelta

from odoo import api, fields, models

from ..utils.api_call_result import API_CALL_CACHE_TTL_SECONDS, cache_key_for_api_call

_logger = logging.getLogger(__name__)


class AIApiResultCache(models.Model):
    """Full-body cache for supervised ``api_call`` results.

    The LLM channel receives a JSON-aware preview (first page). The complete
    response lives here so follow-up turns and pagination can reuse it without
    re-hitting the external API. Short TTL — live data, not immutable docs.
    """
    _name = 'ai.api.result.cache'
    _description = 'AI api_call Result Cache'
    _order = 'fetched_at desc'
    _rec_name = 'cache_key'

    cache_key = fields.Char(
        string='Cache key',
        required=True,
        index=True,
        help='SHA-256 of server + tool + canonical arguments JSON.',
    )
    server_code = fields.Char(string='Server code', index=True)
    tool_name = fields.Char(string='Tool')
    arguments_json = fields.Text(string='Arguments JSON')
    body = fields.Text(string='Full response body')
    body_size = fields.Integer(string='Body size (bytes)')
    fetched_at = fields.Datetime(string='Fetched at', index=True)
    expires_at = fields.Datetime(
        string='Expires at',
        index=True,
        help='After this instant the entry is stale and will be ignored / purged.',
    )

    _sql_constraints = [
        ('cache_key_unique', 'UNIQUE(cache_key)', 'A cache entry for this api_call already exists.'),
    ]

    @api.model
    def _hash_key(self, server, tool, arguments):
        return cache_key_for_api_call(server, tool, arguments)

    @api.model
    def get_cached(self, server, tool, arguments):
        """Return the cached full body if fresh, else None."""
        key = self._hash_key(server, tool, arguments)
        now = fields.Datetime.now()
        rec = self.sudo().search([
            ('cache_key', '=', key),
            ('expires_at', '>', now),
        ], limit=1)
        if not rec:
            return None
        return rec.body or ''

    @api.model
    def store(self, server, tool, arguments, body, ttl_seconds=None):
        """Upsert a fresh cache entry. Best-effort — never breaks the turn."""
        try:
            ttl = int(ttl_seconds or API_CALL_CACHE_TTL_SECONDS)
            if ttl <= 0 or body is None:
                return
            now = fields.Datetime.now()
            expires = now + timedelta(seconds=ttl)
            key = self._hash_key(server, tool, arguments)
            args_text = json.dumps(arguments or {}, sort_keys=True, ensure_ascii=False, default=str)
            vals = {
                'cache_key': key,
                'server_code': server or '',
                'tool_name': tool or '',
                'arguments_json': args_text,
                'body': body,
                'body_size': len(body or ''),
                'fetched_at': now,
                'expires_at': expires,
            }
            existing = self.sudo().search([('cache_key', '=', key)], limit=1)
            if existing:
                existing.write(vals)
            else:
                self.sudo().create(vals)
        except Exception:
            _logger.warning(
                'ai.api.result.cache: store failed for %s/%s',
                server, tool, exc_info=True,
            )

    @api.model
    def gc_expired(self):
        """Cron entry point: delete expired cache rows."""
        now = fields.Datetime.now()
        stale = self.sudo().search([('expires_at', '<=', now)])
        count = len(stale)
        if count:
            stale.unlink()
            _logger.info('ai.api.result.cache: purged %d expired entries', count)
        return count
