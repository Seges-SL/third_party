# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 Patanegra Soft <https://patanegra.com>
"""What a provider is for: a role an agent asks for by its code.

Every role comes from a module's data file. The engine ships its own; a
module that needs a new one seeds it and asks for it with ``need=<code>``.
Uninstalling that module takes the role and its ticks with it. A person may
archive a role, turn its fallback off or change the colours of its chip,
nothing else: the name, the help and the order are the module's too, and a
-u writes them again. The module ships a colour; the database's own one
lives apart, so the -u does not take it back.
"""
import logging
import re

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools import html_escape
from odoo.addons.pns_base.utils.compat import ODOO_VERSION

from ..utils import mcp_ui
from ..utils.config_backup import export_roles_with_holders
from ..utils.import_export_guard import ensure_ai_admin

_logger = logging.getLogger(__name__)

# Set by the module that ships the role; agents and failover read them.
_SHIPPED_FIELDS = (
    'code', 'name', 'description', 'sequence', 'accepts', 'fallback_id',
    'module_bg_color', 'module_fg_color',
)

_HEX = re.compile(r'^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})$')
_CHIP_BG = '#6c757d'
_CHIP_FG = '#ffffff'


def _hex(value, default):
    value = (value or '').strip()
    return value if _HEX.match(value) else default


class AiProviderRole(models.Model):
    _name = 'ai.provider.role'
    _description = 'AI Provider Role'
    _order = 'sequence, id'

    code = fields.Char(
        required=True,
        readonly=True,
        help='What an agent asks for (need=code). Set by the module that '
             'ships the role.',
    )
    name = fields.Char(required=True, translate=True, readonly=True)
    description = fields.Text(translate=True, readonly=True)
    sequence = fields.Integer(default=10, readonly=True)
    active = fields.Boolean(
        default=True,
        help='An archived role holds no provider: whoever asks for it gets '
             'its fallback, or nobody.',
    )
    accepts = fields.Selection(
        [
            ('text', 'Text'),
            ('image', 'Image'),
            ('audio', 'Audio'),
            ('video', 'Video'),
        ],
        string='Accepts',
        required=True,
        default='text',
        readonly=True,
        help='What the model has to accept. A tick on a model whose '
             'catalogue does not accept it fails on save.',
    )
    fallback_id = fields.Many2one(
        'ai.provider.role',
        string='Fallback',
        readonly=True,
        ondelete='set null',
        help='When no provider holds this role, whoever asks for it is '
             'served by this one. Empty: nobody.',
    )
    use_fallback = fields.Boolean(
        string='Use the fallback',
        default=True,
        help='Off: when nobody holds this role, nobody answers, even if '
             'it has a fallback. The module sets the fallback; this '
             'database only decides whether to use it.',
    )
    module = fields.Char(
        compute='_compute_module',
        help='The module that ships this role.',
    )
    provider_ids = fields.Many2many(
        'ai.provider',
        'ai_provider_role_rel', 'role_id', 'provider_id',
        string='Held by',
        readonly=True,
    )
    provider_count = fields.Integer(
        string='Providers',
        compute='_compute_provider_count',
    )
    module_bg_color = fields.Char(string='Module background', readonly=True)
    module_fg_color = fields.Char(string='Module text colour', readonly=True)
    own_bg_color = fields.Char(string='Own background')
    own_fg_color = fields.Char(string='Own text colour')
    bg_color = fields.Char(
        string='Background',
        compute='_compute_colors',
        inverse='_inverse_bg_color',
        readonly=False,
        help="The chip's background. The module's colour until this "
             'database picks another.',
    )
    fg_color = fields.Char(
        string='Text colour',
        compute='_compute_colors',
        inverse='_inverse_fg_color',
        readonly=False,
        help="The chip's text. The module's colour until this database "
             'picks another.',
    )
    chip_html = fields.Html(
        string='Chip',
        compute='_compute_chip_html',
        sanitize=False,
        readonly=True,
    )

    if ODOO_VERSION >= 19:
        _code_unique = models.Constraint(
            'unique(code)',
            'A role code must be unique.',
        )
    else:
        _sql_constraints = [
            ('code_unique', 'unique(code)', 'A role code must be unique.'),
        ]

    @api.depends('provider_ids')
    def _compute_provider_count(self):
        for rec in self:
            rec.provider_count = len(rec.provider_ids)

    @api.depends('own_bg_color', 'own_fg_color', 'module_bg_color', 'module_fg_color')
    def _compute_colors(self):
        for rec in self:
            rec.bg_color = _hex(rec.own_bg_color or rec.module_bg_color, _CHIP_BG)
            rec.fg_color = _hex(rec.own_fg_color or rec.module_fg_color, _CHIP_FG)

    def _inverse_bg_color(self):
        for rec in self:
            rec.own_bg_color = rec._own_colour(rec.bg_color, rec.module_bg_color, _CHIP_BG)

    def _inverse_fg_color(self):
        for rec in self:
            rec.own_fg_color = rec._own_colour(rec.fg_color, rec.module_fg_color, _CHIP_FG)

    @staticmethod
    def _own_colour(picked, shipped, default):
        """Empty when the pick is the module's colour, so a -u can move it."""
        picked = (picked or '').strip()
        if not picked or picked.lower() == _hex(shipped, default).lower():
            return False
        return picked

    @api.constrains('own_bg_color', 'own_fg_color')
    def _check_colours(self):
        for rec in self:
            for value in (rec.own_bg_color, rec.own_fg_color):
                if value and not _HEX.match(value.strip()):
                    raise ValidationError(
                        _('A colour is written #RRGGBB: %s') % value
                    )

    def _chip(self, tip=''):
        """The role as a chip, in its own colours."""
        self.ensure_one()
        return '<span class="o_pns_fit_chip" style="background:%s;color:%s;"%s>%s</span>' % (
            self.bg_color,
            self.fg_color,
            (' title="%s"' % html_escape(tip)) if tip else '',
            html_escape(self.name or self.code or ''),
        )

    @api.depends('name', 'bg_color', 'fg_color')
    def _compute_chip_html(self):
        for rec in self:
            rec.chip_html = rec._chip()

    def _compute_module(self):
        data = self.env['ir.model.data'].sudo().search([
            ('model', '=', self._name), ('res_id', 'in', self.ids),
        ])
        by_id = {row.res_id: row.module for row in data}
        for rec in self:
            rec.module = by_id.get(rec.id, '')

    @api.model
    def _by_code(self, code):
        if not code:
            return self.browse()
        return self.sudo().with_context(active_test=False).search(
            [('code', '=', code)], limit=1,
        )

    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.su:
            raise UserError(_('Roles come from the module that uses them.'))
        return super().create(vals_list)

    def write(self, vals):
        if not self.env.su and any(key in vals for key in _SHIPPED_FIELDS):
            raise UserError(_(
                'What a role is, what it accepts and its fallback are set by the '
                'module that ships it.'
            ))
        return super().write(vals)

    def unlink(self):
        if not self.env.su:
            raise UserError(_(
                'A role goes when the module that ships it is uninstalled. '
                'Archive it instead.'
            ))
        return super().unlink()

    def action_export_roles(self, *args, **kwargs):
        """Export every role: this database's choices and who holds it."""
        del args, kwargs
        ensure_ai_admin(self.env)
        roles = self.sudo().with_context(active_test=False).search([])
        rows = export_roles_with_holders(roles)
        filename = mcp_ui.build_export_filename(self.env, 'ai_provider_roles', 'json')
        attachment = mcp_ui.write_json_attachment(self.env, filename, rows)
        return mcp_ui.open_json_export_wizard(
            self.env,
            dialog_title=_('Export result'),
            summary_text=_('%s provider role(s) exported.') % len(rows),
            count=len(rows),
            attachment=attachment,
        )

    def action_import_roles(self, *args, **kwargs):
        """Open the wizard that imports roles from JSON."""
        del args, kwargs
        ensure_ai_admin(self.env)
        return {
            'type': 'ir.actions.act_window',
            'name': _('Import provider roles'),
            'res_model': 'ai.import.provider.roles.wizard',
            'view_mode': 'form',
            'views': [[False, 'form']],
            'target': 'new',
        }

    def _register_hook(self):
        res = super()._register_hook()
        from ..utils.schema_fossils import promote_fit_columns

        try:
            with self.env.cr.savepoint():
                promote_fit_columns(self.env.cr)
        except Exception:
            _logger.exception('pns_ai_mcp: fit ticks not moved to roles yet')
        return res
