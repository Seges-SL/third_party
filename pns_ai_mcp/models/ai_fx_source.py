# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""Deterministic USD FX feeds for cost presentation (not Safe Plan / AST)."""
from __future__ import annotations

import json
import logging
import urllib.request

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

from ..utils.fx_rates import convert_usd_amount, parse_feed_rates

_logger = logging.getLogger(__name__)

ICP_KEY = 'pns_ai_mcp.fx_usd_cache'
_TIMEOUT = 4
_ERROR_MAX = 240


class AiFxSource(models.Model):
    _name = 'ai.fx.source'
    _description = 'AI currency rate source'
    _order = 'sequence, id'

    name = fields.Char(required=True)
    url = fields.Char(
        required=True,
        help="HTTPS JSON feed with a USD-based 'rates' map. "
             "Not subject to the Safe Plan URL whitelist.",
    )
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    fail_count = fields.Integer(
        string='Consecutive failures',
        default=0,
        readonly=True,
        copy=False,
    )
    last_success = fields.Datetime(readonly=True, copy=False)
    last_fail = fields.Datetime(readonly=True, copy=False)
    last_error = fields.Char(readonly=True, copy=False)

    @api.constrains('url')
    def _check_url(self):
        for rec in self:
            url = (rec.url or '').strip()
            if not url.startswith(('https://', 'http://')):
                raise ValidationError(
                    _("Currency rate URL must start with http:// or https://.")
                )

    def _mark_success(self):
        self.sudo().write({
            'fail_count': 0,
            'last_success': fields.Datetime.now(),
            'last_error': False,
        })

    def _mark_fail(self, error):
        msg = str(error or 'fetch failed')[:_ERROR_MAX]
        self.sudo().write({
            'fail_count': (self.fail_count or 0) + 1,
            'last_fail': fields.Datetime.now(),
            'last_error': msg,
        })

    def _fetch_rates(self):
        self.ensure_one()
        url = (self.url or '').strip()
        req = urllib.request.Request(
            url, headers={'User-Agent': 'pns-ai-mcp/fx'},
        )
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
            body = json.loads(resp.read().decode('utf-8'))
        rates = parse_feed_rates(body)
        if not rates:
            raise ValueError('feed has no usable rates')
        return rates

    @api.model
    def get_usd_fx(self):
        """Return ``{base, rates, as_of, source, error}``. Never raises.

        On failure the payload carries empty ``rates`` plus ``error`` so the
        caller can say out loud that it is falling back to USD instead of
        silently pretending the vendor cost was converted.
        """
        today_s = fields.Date.to_string(fields.Date.context_today(self))
        icp = self.env['ir.config_parameter'].sudo()
        raw = icp.get_param(ICP_KEY)
        if raw:
            try:
                data = json.loads(raw)
                if (
                    data.get('as_of') == today_s
                    and isinstance(data.get('rates'), dict)
                    and data['rates']
                ):
                    return data
            except Exception:
                pass
        sources = self.sudo().search([('active', '=', True)], order='sequence, id')
        rates = None
        origin = ''
        errors = []
        for source in sources:
            try:
                rates = source._fetch_rates()
            except Exception as exc:
                _logger.warning('FX feed failed (%s): %s', source.url, exc)
                errors.append('%s: %s' % (source.name or source.url, exc))
                source._mark_fail(exc)
                continue
            source._mark_success()
            origin = source.name or source.url
            break
        if not rates:
            try:
                rates = self._rates_from_odoo_currency()
            except Exception as exc:
                _logger.warning('FX fallback on res.currency failed: %s', exc)
                errors.append('res.currency: %s' % exc)
                rates = None
            if rates:
                origin = 'res.currency'
        if not rates:
            if not sources:
                errors.append('no active currency rate source')
            error = ' | '.join(errors) or 'no usable currency rate'
            _logger.warning(
                'FX unavailable: costs stay in USD (%s)', error,
            )
            return {
                'base': 'USD',
                'rates': {},
                'as_of': today_s,
                'source': '',
                'error': error,
            }
        payload = {
            'base': 'USD',
            'rates': rates,
            'as_of': today_s,
            'source': origin,
            'error': '',
        }
        try:
            icp.set_param(ICP_KEY, json.dumps(payload))
        except Exception:
            _logger.warning('Could not cache FX rates')
        return payload

    @api.model
    def _rates_from_odoo_currency(self):
        """USD-based map from ``res.currency`` when public feeds are unreachable.

        Skips 1:1 quotes (typical unconfigured Odoo rates) so we do not
        pretend 1 USD = 1 EUR.
        """
        Currency = self.env['res.currency'].sudo()
        usd = Currency.search([('name', '=', 'USD')], limit=1)
        if not usd:
            return None
        company = self.env.company
        today = fields.Date.context_today(self)
        out = {'USD': 1.0}
        for cur in Currency.search([('active', '=', True)]):
            code = (cur.name or '').strip().upper()
            if len(code) != 3 or code == 'USD':
                continue
            try:
                if hasattr(usd, '_convert'):
                    amount = usd._convert(1.0, cur, company, today, round=False)
                else:
                    amount = usd.with_context(date=today).compute(1.0, cur, round=False)
            except Exception:
                continue
            try:
                n = float(amount)
            except (TypeError, ValueError):
                continue
            if n > 0 and abs(n - 1.0) > 1e-6:
                out[code] = n
        return out if len(out) > 1 else None

    @api.model
    def convert_usd(self, amount, currency):
        """Convert a vendor USD amount for display. Does not persist."""
        return convert_usd_amount(amount, currency, self.get_usd_fx())
