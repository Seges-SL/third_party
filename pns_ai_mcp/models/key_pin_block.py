# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""Per-IP pause after too many temporary-PIN failures.

A correct API key does not come through here. Once the pause has started,
a right PIN and a wrong PIN are both refused until the hour ends or an
admin releases every pause from settings.
"""

from datetime import timedelta

from odoo import api, fields, models

from ..utils.key_pin import failure_starts_block, pin_attempts, pin_block_hours


class KeyPinBlock(models.Model):
    _name = 'ai.key.pin.block'
    _description = 'Temporary key PIN block'
    _rec_name = 'ip'
    _order = 'ip'

    ip = fields.Char(string='IP', required=True, index=True)
    failures = fields.Integer(string='Failures', default=0)
    blocked_until = fields.Datetime(string='Blocked until')

    def _now(self):
        return fields.Datetime.to_datetime(fields.Datetime.now())

    def _until_of(self, record):
        if not record or not record.blocked_until:
            return None
        return fields.Datetime.to_datetime(record.blocked_until)

    @api.model
    def is_blocked(self, ip):
        ip = (ip or '').strip()
        if not ip:
            return False
        rec = self.sudo().search([('ip', '=', ip)], limit=1)
        until = self._until_of(rec)
        return bool(until and until > self._now())

    @api.model
    def note_failure(self, ip):
        """Count one missed PIN. Return True when this IP is now paused."""
        ip = (ip or '').strip()
        if not ip:
            return False
        if self.is_blocked(ip):
            return True
        rec = self.sudo().search([('ip', '=', ip)], limit=1)
        if not rec:
            rec = self.sudo().create({'ip': ip, 'failures': 0})
        failures = (rec.failures or 0) + 1
        vals = {'failures': failures}
        paused = failure_starts_block(failures, pin_attempts(self.env))
        if paused:
            hours = pin_block_hours(self.env)
            vals['blocked_until'] = fields.Datetime.to_string(
                self._now() + timedelta(hours=hours),
            )
            vals['failures'] = 0
        rec.write(vals)
        return paused

    @api.model
    def release_all(self):
        rows = self.sudo().search([])
        if rows:
            rows.write({'failures': 0, 'blocked_until': False})
        return len(rows)
