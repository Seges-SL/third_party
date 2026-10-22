# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""Browser tab that is holding the plaintext key list.

The tab calls in and leaves the reply open via the bus Odoo already
keeps with the backend. A PIN redeem answers that tab with an email.
The tab sends back one key. The key is wiped as soon as it is read.
"""

import logging
import time
from datetime import timedelta

from odoo import SUPERUSER_ID, api, fields, models

from ..utils.key_pin import DESK_TTL_SECONDS, pin_length

_logger = logging.getLogger(__name__)

ASK_WAIT_SECONDS = 20


class KeyPinDesk(models.Model):
    _name = 'ai.key.pin.desk'
    _description = 'Temporary key PIN desk'
    _rec_name = 'token'

    token = fields.Char(required=True, index=True)
    user_id = fields.Many2one('res.users', required=True, index=True)
    last_seen = fields.Datetime(required=True, index=True)

    def _now(self):
        return fields.Datetime.to_datetime(fields.Datetime.now())

    def _cutoff(self):
        return fields.Datetime.to_string(
            self._now() - timedelta(seconds=DESK_TTL_SECONDS),
        )

    @api.model
    def any_open(self):
        return bool(self.sudo().search_count([
            ('last_seen', '>=', self._cutoff()),
        ]))

    def _live(self):
        return self.sudo().search([('last_seen', '>=', self._cutoff())])

    def _admin_partners(self):
        admin = self.env.ref(
            'pns_ai_mcp.group_ai_admin', raise_if_not_found=False,
        )
        partners = admin.users.mapped('partner_id') if admin else self.env['res.partner']
        partners |= self._live().mapped('user_id.partner_id')
        if self.env.user.partner_id:
            partners |= self.env.user.partner_id
        return partners

    def _notify_presence(self):
        self._broadcast(
            self.env,
            self._admin_partners(),
            'pns_key_pin_presence',
            {'open': self.any_open()},
        )
        # Same listeners as pin colour: blue while a desk is open.
        self.notify_changed()

    def _broadcast(self, env, partners, channel, payload):
        bus = env['bus.bus'].sudo()
        sendone = getattr(bus, '_sendone', None)
        legacy = getattr(bus, 'sendone', None)
        for partner in partners:
            if not partner:
                continue
            if sendone:
                sendone(partner, channel, payload)
            elif legacy:
                legacy(
                    (env.cr.dbname, 'res.partner', partner.id),
                    payload,
                )

    def _send(self, env, channel, payload):
        """Ask / handoff: only tabs that registered a desk."""
        partners = env['ai.key.pin.desk'].sudo()._live().mapped('user_id.partner_id')
        self._broadcast(env, partners, channel, payload)

    @api.model
    def touch(self, token, user):
        token = (token or '').strip()
        if not token or not user:
            return {'ok': False}
        self.sudo().search([
            ('last_seen', '<', self._cutoff()),
        ]).unlink()
        was_open = self.any_open()
        rec = self.sudo().search([('token', '=', token)], limit=1)
        now = fields.Datetime.now()
        if rec:
            rec.write({'last_seen': now, 'user_id': user.id})
        else:
            self.sudo().create({
                'token': token,
                'user_id': user.id,
                'last_seen': now,
            })
        if was_open != self.any_open():
            self._notify_presence()
        pending = self.env['ai.key.pin.ask'].sudo().search([
            ('supplied_key', '=', False),
            ('failed', '=', False),
        ])
        return {
            'ok': True,
            'pin_length': pin_length(self.env),
            'asks': [{
                'ask_id': ask.id,
                'email': ask.email or '',
                'login': ask.login or '',
                'pin': ask.pin or '',
            } for ask in pending],
        }

    @api.model
    def close(self, token):
        token = (token or '').strip()
        if not token:
            return False
        rows = self.sudo().search([('token', '=', token)])
        if rows:
            rows.unlink()
        self._notify_presence()
        return True

    @api.model
    def notify_changed(self):
        """Tell AI admins to repaint pins. Does not reload the page."""
        self._broadcast(
            self.env,
            self._admin_partners(),
            'pns_key_pin_changed',
            {'type': 'pns_key_pin_changed'},
        )

    def _notify_ask(self, env, ask):
        self._send(env, 'pns_key_pin', {
            'type': 'pns_key_pin',
            'ask_id': ask.id,
            'email': ask.email or '',
            'login': ask.login or '',
            'pin': ask.pin or '',
        })

    def _notify_pin_spent(self, pin):
        """The app logged in with this PIN: tabs holding it drop it."""
        self._send(self.env, 'pns_key_pin_spent', {
            'type': 'pns_key_pin_spent',
            'pin': pin or '',
        })


class KeyPinAsk(models.Model):
    _name = 'ai.key.pin.ask'
    _description = 'Temporary key PIN ask'

    email = fields.Char()
    login = fields.Char()
    pin = fields.Char(copy=False)
    mcp_user_id = fields.Many2one('ai.mcp.user')
    supplied_key = fields.Char(copy=False)
    failed = fields.Boolean(copy=False)
    refused = fields.Integer(copy=False, default=0)
    desks = fields.Integer(copy=False, default=0)

    @api.model
    def _drop_old(self):
        cutoff = fields.Datetime.to_string(
            fields.Datetime.to_datetime(fields.Datetime.now()) - timedelta(minutes=2),
        )
        self.sudo().search([('create_date', '<', cutoff)]).unlink()

    @api.model
    def collect(self, mcp_user, email, login):
        """Ask every open tab. Return the key, False if it does not match, or None."""
        return self._collect({
            'email': email or '',
            'login': login or '',
            'mcp_user_id': mcp_user.id,
        })

    @api.model
    def collect_pin(self, pin):
        """Ask every open tab whose PIN this is. Return the key it stands for.

        The server does not know the PIN: the tab minted it next to the key.
        False means a tab answered that the PIN is not theirs, None that no
        tab answered in time.
        """
        return self._collect({'pin': pin or ''})

    @api.model
    def _collect(self, vals):
        self._drop_old()
        registry = self.env.registry
        with registry.cursor() as cr:
            env = api.Environment(cr, SUPERUSER_ID, {})
            vals = dict(vals)
            vals['desks'] = len(env['ai.key.pin.desk'].sudo()._live())
            ask = env['ai.key.pin.ask'].sudo().create(vals)
            ask_id = ask.id
            env['ai.key.pin.desk']._notify_ask(env, ask)
        deadline = time.time() + ASK_WAIT_SECONDS
        while time.time() < deadline:
            found = self._take(ask_id)
            if found is not None:
                return found
            time.sleep(0.4)
        return self._take(ask_id, final=True)

    @api.model
    def _take(self, ask_id, final=False):
        """Return the key, False on mismatch, or None if still waiting.

        The row is removed as soon as it has an answer, key included. A PIN
        ask is only refused once every open tab has said the PIN is not
        theirs, or when the wait ends with at least one refusal.
        """
        registry = self.env.registry
        with registry.cursor() as cr:
            env = api.Environment(cr, SUPERUSER_ID, {})
            ask = env['ai.key.pin.ask'].sudo().browse(ask_id)
            if not ask.exists():
                return False
            if ask.failed:
                ask.unlink()
                return False
            if ask.supplied_key:
                key = ask.supplied_key
                ask.unlink()
                return key
            if ask.pin and ask.refused:
                if (ask.desks and ask.refused >= ask.desks) or final:
                    ask.unlink()
                    return False
            if final:
                # The wait is over: drop the row so a key that arrives late
                # has nowhere to land.
                ask.unlink()
        return None

    @api.model
    def supply(self, ask_id, api_key, user):
        from ..utils.api_key import hash_api_key
        api_key = (api_key or '').strip()
        if not ask_id:
            return {'ok': False}
        desk = self.env['ai.key.pin.desk'].sudo().search([
            ('user_id', '=', user.id),
            ('last_seen', '>=', self.env['ai.key.pin.desk']._cutoff()),
        ], limit=1)
        if not desk:
            return {'ok': False}
        ask = self.sudo().browse(int(ask_id))
        if not ask.exists() or ask.supplied_key or ask.failed:
            return {'ok': False}
        if ask.pin and not api_key:
            # A tab answered: this PIN is not theirs. Other tabs may still
            # hold it, so this only counts as one refusal.
            ask.write({'refused': (ask.refused or 0) + 1})
            return {'ok': False, 'error': 'unknown_pin'}
        if not api_key:
            return {'ok': False}
        if ask.mcp_user_id:
            owner = ask.mcp_user_id.sudo()
        else:
            # PIN ask: the tab named no user. The key itself says whose it is.
            owner = self.env['ai.mcp.user'].sudo().search([
                ('mcp_api_key_hash', '=', hash_api_key(api_key)),
            ], limit=1)
        if not owner or hash_api_key(api_key) != (owner.mcp_api_key_hash or ''):
            ask.write({'failed': True, 'supplied_key': False})
            _logger.info(
                'MCP: key list does not match the stored hash for user %s',
                owner.user_id.id if owner else 0,
            )
            return {'ok': False, 'error': 'mismatch'}
        vals = {'supplied_key': api_key}
        if not ask.mcp_user_id:
            vals['mcp_user_id'] = owner.id
        ask.write(vals)
        return {'ok': True}
