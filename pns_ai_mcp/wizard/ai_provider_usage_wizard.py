# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 Patanegra Soft <https://patanegra.com>
"""This month's inference spend for one provider."""

from odoo import api, fields, models, _


class AIProviderUsageWizard(models.TransientModel):
    _name = 'ai.provider.usage.wizard'
    _description = 'Provider usage this month'

    provider_id = fields.Many2one(
        'ai.provider', string='Provider', required=True, readonly=True,
        ondelete='cascade',
    )
    period_label = fields.Char(string='Period', readonly=True)
    prompt_tokens = fields.Integer(string='Input tokens', readonly=True)
    completion_tokens = fields.Integer(string='Output tokens', readonly=True)
    total_tokens = fields.Integer(string='Total tokens', readonly=True)
    cost_display = fields.Char(string='Cost', readonly=True)
    cap_label = fields.Char(string='Cap', readonly=True)
    remaining_label = fields.Char(string='Remaining', readonly=True)

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        provider_id = self.env.context.get('default_provider_id')
        if not provider_id:
            return res
        provider = self.env['ai.provider'].browse(provider_id).exists()
        if not provider:
            return res
        from ..utils.provider_spend import cap_is_set
        from ..utils.usage_display import format_cost_label, format_turn_tokens_label

        usage = provider.month_usage()
        cost = format_cost_label(self.env, usage.get('cost') or None)
        cap_usd = provider.spend_cap_usd
        cap_tokens = provider.spend_cap_tokens
        if cap_is_set(cap_usd):
            cap_txt = format_cost_label(self.env, cap_usd)['label']
            if usage.get('cost'):
                left = max(0.0, float(cap_usd) - float(usage['cost']))
                remain = format_cost_label(self.env, left)['label']
            else:
                remain = _('No cost reported; token cap applies if set')
        elif cap_is_set(cap_tokens):
            cap_txt = format_turn_tokens_label({'total_tokens': cap_tokens})
            left = max(0, int(cap_tokens) - int(usage.get('total_tokens') or 0))
            remain = format_turn_tokens_label({'total_tokens': left})
        else:
            cap_txt = _('None')
            remain = _('No cap')
        res.update({
            'provider_id': provider.id,
            'period_label': _('This month (since %s)') % (usage.get('since') or ''),
            'prompt_tokens': usage.get('prompt_tokens') or 0,
            'completion_tokens': usage.get('completion_tokens') or 0,
            'total_tokens': usage.get('total_tokens') or 0,
            'cost_display': cost['label'],
            'cap_label': cap_txt,
            'remaining_label': remain,
        })
        return res

    def action_open_log(self):
        self.ensure_one()
        start = self.provider_id._spend_month_start()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Inference log'),
            'res_model': 'ai.log',
            'view_mode': 'tree,form',
            'domain': [
                ('provider_id', '=', self.provider_id.id),
                ('timestamp', '>=', start),
            ],
        }
