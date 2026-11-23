# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 Patanegra Soft <https://patanegra.com>
"""Legend of ``{year}`` tokens painted in the form arch (not a field widget)."""
from odoo import api, models

from ..utils.skill_param_tokens import fill_skill_param_token_legend_arch


class SkillParamTokenLegendMixin(models.AbstractModel):
    _name = 'ai.skill.param.token.legend.mixin'
    _description = 'Skill parameter default-token legend'

    @api.model
    def fields_view_get(self, view_id=None, view_type='form', toolbar=False,
                        submenu=False):
        res = super().fields_view_get(
            view_id=view_id, view_type=view_type,
            toolbar=toolbar, submenu=submenu,
        )
        if view_type == 'form':
            res['arch'] = fill_skill_param_token_legend_arch(res.get('arch'))
        return res
