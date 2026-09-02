# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""Daily usage totals per AI provider (tokens + optional vendor cost)."""
import logging

from odoo import SUPERUSER_ID, api, fields, models

from ..utils.llm_usage import normalize_usage, usage_has_tokens

_logger = logging.getLogger(__name__)


class AIProviderUsageDay(models.Model):
    _name = 'ai.provider.usage.day'
    _description = 'AI Provider daily usage'
    _order = 'date desc, id desc'
    _rec_name = 'date'

    provider_id = fields.Many2one(
        'ai.provider',
        string='Provider',
        required=True,
        ondelete='cascade',
        index=True,
        copy=False,
    )
    date = fields.Date(string='Date', required=True, index=True)
    prompt_tokens = fields.Integer(string='Prompt tokens', default=0)
    completion_tokens = fields.Integer(string='Completion tokens', default=0)
    total_tokens = fields.Integer(string='Total tokens', default=0)
    cost = fields.Float(string='Cost', digits=(16, 8), default=0.0)
    request_count = fields.Integer(string='Requests', default=0)

    _sql_constraints = [
        (
            'provider_date_uniq',
            'unique(provider_id, date)',
            'A daily usage row already exists for this provider and date.',
        ),
    ]

    @api.model
    def increment_for_turn(self, provider, usage):
        """Add one turn's usage to today's row. No-op if usage is empty.

        Writes on a short autonomous cursor (same idea as recipe ``_mark_hit``).
        The Chatboo worker holds a REPEATABLE READ snapshot for the whole turn;
        updating this hot unique row on that cursor collides with other commits
        (PG 40001) and used to paint a false "MCP engine error".
        """
        if not provider:
            return self.browse()
        piece = normalize_usage(usage)
        if not usage_has_tokens(piece) and piece.get('cost') is None:
            return self.browse()
        today = fields.Date.context_today(provider)
        add_prompt = int(piece.get('prompt_tokens') or 0)
        add_completion = int(piece.get('completion_tokens') or 0)
        add_total = int(piece.get('total_tokens') or 0) or (add_prompt + add_completion)
        add_cost = float(piece.get('cost') or 0.0)
        table = self._table
        uid = SUPERUSER_ID
        params_upd = (
            add_prompt, add_completion, add_total, add_cost, uid,
            provider.id, today,
        )
        sql_upd = (
            "UPDATE %s SET "
            "prompt_tokens = COALESCE(prompt_tokens, 0) + %%s, "
            "completion_tokens = COALESCE(completion_tokens, 0) + %%s, "
            "total_tokens = COALESCE(total_tokens, 0) + %%s, "
            "cost = COALESCE(cost, 0) + %%s, "
            "request_count = COALESCE(request_count, 0) + 1, "
            "write_uid = %%s, "
            "write_date = (now() at time zone 'UTC') "
            "WHERE provider_id = %%s AND date = %%s" % table
        )
        sql_ins = (
            "INSERT INTO %s ("
            "provider_id, date, prompt_tokens, completion_tokens, "
            "total_tokens, cost, request_count, "
            "create_uid, write_uid, create_date, write_date"
            ") VALUES ("
            "%%s, %%s, %%s, %%s, %%s, %%s, 1, %%s, %%s, "
            "(now() at time zone 'UTC'), (now() at time zone 'UTC')"
            ")" % table
        )
        try:
            with self.env.registry.cursor() as cr:
                cr.execute("SET LOCAL lock_timeout = '2s'")
                cr.execute(sql_upd, params_upd)
                if not cr.rowcount:
                    try:
                        cr.execute(
                            sql_ins,
                            (
                                provider.id, today, add_prompt, add_completion,
                                add_total, add_cost, uid, uid,
                            ),
                        )
                    except Exception:
                        cr.rollback()
                        cr.execute("SET LOCAL lock_timeout = '2s'")
                        cr.execute(sql_upd, params_upd)
                cr.commit()
        except Exception:
            _logger.debug(
                'ai.provider.usage.day increment skipped for provider %s',
                provider.id, exc_info=True,
            )
        return self.browse()

    @api.model
    def import_missing_days(self, provider, rows):
        """Create only dates that do not already exist for ``provider``."""
        if not provider or not rows:
            return 0
        Day = self.sudo()
        existing = set(Day.search([
            ('provider_id', '=', provider.id),
        ]).mapped('date'))
        created = 0
        for row in rows:
            if not isinstance(row, dict):
                continue
            raw = row.get('date')
            if not raw:
                continue
            try:
                day = fields.Date.from_string(raw) if isinstance(raw, str) else raw
            except Exception:
                continue
            if not day or day in existing:
                continue
            Day.create({
                'provider_id': provider.id,
                'date': day,
                'prompt_tokens': int(row.get('prompt_tokens') or 0),
                'completion_tokens': int(row.get('completion_tokens') or 0),
                'total_tokens': int(row.get('total_tokens') or 0),
                'cost': float(row.get('cost') or 0.0),
                'request_count': int(row.get('request_count') or 0),
            })
            existing.add(day)
            created += 1
        return created

    def to_export_rows(self):
        """Portable list for JSON export (oldest first)."""
        rows = []
        for rec in self.sorted('date'):
            rows.append({
                'date': fields.Date.to_string(rec.date),
                'prompt_tokens': rec.prompt_tokens or 0,
                'completion_tokens': rec.completion_tokens or 0,
                'total_tokens': rec.total_tokens or 0,
                'cost': rec.cost or 0.0,
                'request_count': rec.request_count or 0,
            })
        return rows
