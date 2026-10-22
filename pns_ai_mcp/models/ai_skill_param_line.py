# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 Patanegra Soft <https://patanegra.com>
"""Human parameter list for ``ai.skill`` (concept / description / default).

``param_schema`` stays the JSON the engine and ``.md`` packs already read.
These rows are the Settings UI. Factory import does not rebuild them on
every skill write (that nested One2many replace killed the ``-u`` cursor).
Missing rows are filled once after import, or when the form reads them.
"""
from odoo import fields, models


class AISkillParamLine(models.Model):
    _name = 'ai.skill.param.line'
    _description = 'Skill parameter'
    _order = 'sequence, id'

    skill_id = fields.Many2one(
        'ai.skill',
        string='Skill',
        required=True,
        ondelete='cascade',
        index=True,
    )
    sequence = fields.Integer(default=10)
    label = fields.Char(
        string='Concept',
        help='Human label shown on the /slash ? card.',
    )
    desc = fields.Char(
        string='Description',
        help='Output contract for parse (format, not synonyms).',
    )
    default = fields.Char(
        string='Default',
        help='Value used when the slash omits this parameter. '
             'Tokens from the legend expand when the skill runs. '
             'Empty = the default lives in the Code.',
    )
    required = fields.Boolean(
        string='Required',
        default=False,
        help='The slash must provide this parameter (or its Default).',
    )
    key = fields.Char(
        string='Key',
        help='Identifier the Code reads. Hidden; assigned from the Code '
             'or a short IA pass.',
    )
