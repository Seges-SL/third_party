# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 Patanegra Soft <https://patanegra.com>
"""chatboo.canvas.page — a fixed copy of a canvas, shared with named users.

The session canvas changes with every new page, so its link cannot be
shared. This copy does not change. Its owner and the users it names read
it; only the owner changes or deletes it (``security/security.xml``).
The AI administrator sees, changes and deletes every page.
Someone added to it gets a message in their Discuss inbox, which stays
there, and a toast on the bus if Odoo is open.
"""
import json
import logging

from markupsafe import Markup

from odoo import api, fields, models, _
# Seges: parche 28 (D1, seguridad). Ver docs/pendiente/parches_pns_ai.md
from odoo.exceptions import AccessError, ValidationError

from odoo.addons.pns_ai_mcp.utils.markup_rename import rename_stored_markup

_logger = logging.getLogger(__name__)


class ChatbooCanvasPage(models.Model):
    _name = 'chatboo.canvas.page'
    _inherit = ['mail.thread']
    _description = 'Chatboo shared page'
    _order = 'create_date desc, id desc'

    name = fields.Char(
        string='Title',
        required=True,
        default=lambda self: _('Canvas'),
    )
    design = fields.Text(string='Page', required=True, copy=False)
    owner_id = fields.Many2one(
        'res.users',
        string='Owner',
        required=True,
        default=lambda self: self.env.user,
        ondelete='cascade',
        index=True,
    )
    user_ids = fields.Many2many(
        'res.users',
        'chatboo_canvas_page_user_rel',
        'page_id',
        'user_id',
        string='Shared with',
        domain=[('share', '=', False)],
    )
    url = fields.Char(string='Link', compute='_compute_url')

    def init(self):
        super().init()
        rename_stored_markup(self.env.cr, self._table, 'design')

    @api.depends()
    def _compute_url(self):
        base = (
            self.env['ir.config_parameter'].sudo().get_param('web.base.url') or ''
        ).rstrip('/')
        for page in self:
            page.url = '%s/chatboo/page/%s' % (base, page.id) if page.id else ''

    # Seges: parche 28 (D1, seguridad). Ver docs/pendiente/parches_pns_ai.md
    @api.constrains('user_ids')
    def _check_user_ids_internal(self):
        if self.mapped('user_ids').filtered('share'):
            raise ValidationError(
                _('A page can only be shared with internal users.'),
            )

    @api.model_create_multi
    def create(self, vals_list):
        pages = super(ChatbooCanvasPage, self.with_context(
            mail_create_nolog=True, mail_create_nosubscribe=True,
        )).create(vals_list).with_env(self.env)
        for page in pages:
            page._tell_new_readers(page.user_ids)
        return pages

    def write(self, vals):
        # Seges: parche 28 (D1, seguridad). Ver docs/pendiente/parches_pns_ai.md
        if 'owner_id' in vals and not self.env.su and any(
            page.owner_id.id != (vals['owner_id'] or False) for page in self
        ):
            raise AccessError(
                _('Only the system can change the owner of a shared page.'),
            )
        before = {
            page.id: page.user_ids for page in self
        } if 'user_ids' in vals else {}
        result = super().write(vals)
        for page in self:
            if page.id in before:
                page._tell_new_readers(page.user_ids - before[page.id])
        return result

    def _tell_new_readers(self, users):
        """Each user just added gets an inbox message and a bus toast.

        The owner is not told.
        """
        self.ensure_one()
        users = users - self.owner_id
        if not users:
            return
        self._notify_inbox(users.mapped('partner_id'))
        if 'bus.bus' not in self.env:
            return
        payload = {
            'type': 'pns_chatboo_sync',
            'action': 'page_shared',
            'page_id': self.id,
            'title': self.name or '',
            'owner': self.owner_id.name or '',
            'url': self.page_path(),
        }
        bus = self.env['bus.bus']
        for partner in users.mapped('partner_id'):
            try:
                sendone = getattr(bus, '_sendone', None)
                if sendone:
                    sendone(partner, 'pns_chatboo_sync', payload)
                    continue
                channel = (self.env.cr.dbname, 'res.partner', partner.id)
                bus.sendone(channel, json.dumps(payload, ensure_ascii=False))
            except Exception:
                _logger.debug(
                    'Chatboo: could not tell %s about page %s',
                    partner.id, self.id, exc_info=True,
                )

    def _notify_inbox(self, partners):
        """One Discuss message per language, so each reader gets their own."""
        for lang in set(partners.mapped('lang')):
            readers = partners.filtered(lambda partner: partner.lang == lang)
            page = self.with_context(lang=lang or self.env.lang)
            page.message_notify(
                partner_ids=readers.ids,
                subject=page.name or '',
                body=page._inbox_note(),
            )

    def _inbox_note(self):
        return Markup(
            '<p>%s</p><p><a href="%s" target="_blank">%s</a></p>'
        ) % (
            _('%s shared a page with you') % (self.owner_id.name or ''),
            self.url,
            _('Open page'),
        )

    @api.model
    def people_matching(self, text, limit=20):
        """Internal users whose name has ``text``, for the share box."""
        users = self.env['res.users'].search([
            ('share', '=', False),
            ('id', '!=', self.env.uid),
            ('name', 'ilike', (text or '').strip()),
        ], limit=limit, order='name')
        return [{'id': user.id, 'name': user.name} for user in users]

    @api.model
    def people_named(self, ids_text):
        """The internal users in ``1,2,3``. Anything else is dropped."""
        ids = [int(part) for part in str(ids_text or '').split(',')
               if part.strip().isdigit()]
        users = self.env['res.users'].browse(ids).exists()
        return users.filtered(lambda user: not user.share)

    def people(self):
        self.ensure_one()
        return [{'id': user.id, 'name': user.name} for user in self.user_ids]

    def action_unshare(self):
        self.write({'user_ids': [(5, 0, 0)]})

    def page_path(self):
        self.ensure_one()
        return '/chatboo/page/%s' % self.id

    def action_open_page(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_url',
            'url': self.page_path(),
            'target': 'new',
        }
