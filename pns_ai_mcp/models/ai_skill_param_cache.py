# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""Per-skill cache: unresolved slash prose → params the hybrid LLM filled."""

import json
import logging

from odoo import SUPERUSER_ID, api, fields, models, _
from odoo.exceptions import ValidationError
from odoo.tools import config

from ..utils.skill_runtime import (
    normalize_unresolved_key,
    param_cache_payload,
    parse_param_cache_json,
)

_logger = logging.getLogger(__name__)


class AISkillParamCache(models.Model):
    """One learned phrase for one skill.

    Key = leftover text the formal parser did not bind (normalized).
    Value = JSON object the hybrid LLM (or a human) produced for that phrase.
    Instance data — not factory seed, not skill ZIP export.

    Writes use a dedicated cursor: Chatboo rolls back the turn cursor.
    """
    _name = 'ai.skill.param.cache'
    _description = 'Skill param phrase cache'
    _order = 'unresolved, id'
    _rec_name = 'unresolved'

    skill_id = fields.Many2one(
        'ai.skill',
        string='Skill',
        required=True,
        ondelete='cascade',
        index=True,
    )
    unresolved = fields.Text(
        string='Unresolved text',
        required=True,
        help='Slash leftover the formal parser did not bind. Spaces are '
             'collapsed; matching is case-insensitive.',
    )
    key = fields.Text(
        string='Normalized key',
        compute='_compute_key',
        store=True,
        index=True,
        readonly=True,
    )
    params_json = fields.Text(
        string='Generated params',
        required=True,
        default='{}',
        help='JSON object of schema params produced for this phrase.',
    )
    active = fields.Boolean(default=True)

    _sql_constraints = [
        (
            'skill_key_uniq',
            'unique(skill_id, key)',
            'This skill already has a row for that normalized phrase.',
        ),
    ]

    @api.depends('unresolved')
    def _compute_key(self):
        for rec in self:
            rec.key = normalize_unresolved_key(rec.unresolved)

    @api.constrains('params_json')
    def _check_params_json(self):
        for rec in self:
            if parse_param_cache_json(rec.params_json) is None:
                raise ValidationError(
                    _('Generated params must be a JSON object.')
                )

    def _own_cursor_env(self):
        """True when writes must leave the Chatboo turn cursor."""
        if config['test_enable'] and type(self.env.cr).__name__ == 'TestCursor':
            return False
        return True

    # Seges: parche 9 (PNS-85, seguridad). Ver docs/pendiente/parches_pns_ai.md
    @api.model
    def _lookup_for_skill(self, skill_id, leftover):
        """Cached IA params for leftover, or None."""
        key = normalize_unresolved_key(leftover)
        if not skill_id or not key:
            return None
        rec = self.sudo().search([
            ('skill_id', '=', skill_id),
            ('key', '=', key),
            ('active', '=', True),
        ], limit=1)
        if not rec:
            return None
        payload = parse_param_cache_json(rec.params_json)
        if not payload:
            return None
        return payload

    def _create_or_get(self, skill_id, leftover, payload, key):
        existing = self.search([
            ('skill_id', '=', skill_id),
            ('key', '=', key),
        ], limit=1)
        if existing:
            return existing
        display = ' '.join(str(leftover or '').split())
        return self.create({
            'skill_id': skill_id,
            'unresolved': display,
            'params_json': json.dumps(
                payload, ensure_ascii=False, sort_keys=True,
            ),
        })

    # Seges: parche 9 (PNS-85, seguridad). Ver docs/pendiente/parches_pns_ai.md
    @api.model
    def _remember_for_skill(self, skill_id, leftover, norm):
        """Store leftover → IA params. Does not overwrite an existing row.

        Commits on a new cursor so Chatboo's turn rollback does not drop it.
        """
        payload = param_cache_payload(norm)
        key = normalize_unresolved_key(leftover)
        if not skill_id or not key or not payload:
            _logger.info(
                'param cache skip skill=%s leftover=%r payload=%s',
                skill_id, (leftover or '')[:80], bool(payload),
            )
            return self.browse()
        if not self._own_cursor_env():
            return self.sudo()._create_or_get(skill_id, leftover, payload, key)
        new_cr = None
        try:
            new_cr = self.env.registry.cursor()
            env = api.Environment(new_cr, SUPERUSER_ID, {})
            rec = env['ai.skill.param.cache']._create_or_get(
                skill_id, leftover, payload, key,
            )
            new_cr.commit()
            return rec
        except Exception:
            _logger.warning(
                'param cache remember failed skill=%s key=%s',
                skill_id, key, exc_info=True,
            )
            return self.browse()
        finally:
            if new_cr is not None:
                new_cr.close()
