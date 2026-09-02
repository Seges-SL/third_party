# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""Capture a successful relaxaicode operation (from the log) and create a DRAFT
skill (active=False) for administrator review. The working code is kept as
code_body (source of truth); the administrator writes the Procedure.
"""

import json
import re

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class AISkillCaptureWizard(models.TransientModel):
    _name = 'pns_ai_mcp.skill.capture.wizard'
    _description = 'Capture a successful execution as a draft skill'

    source_log_id = fields.Many2one(
        'ai.log',
        string='Source execution',
        domain="[('endpoint', '=', 'relaxaicode'), ('code_to_execute', '!=', False)]",
        help='A successful relaxaicode execution to crystallize as a skill. Its '
             'code becomes the deterministic Code; its user prompt seeds the hint.',
    )
    skill_code = fields.Char(
        string='Skill code',
        help='Chat slash without leading / (e.g. "facturacion" or '
             '"occ-facturacion"). The catalog id and slash get the '
             'instance prefixes from Settings (snake code, kebab command).',
    )
    skill_name = fields.Char(string='Skill name')
    description = fields.Char(
        string='Selection hint',
        help='Short, precise hint the model uses to decide whether to load this skill.',
    )
    procedure = fields.Text(
        string='Procedure',
        help='Orchestration prose: WHEN to use it, parameters, HOW to present the '
             'result. Do NOT restate the Code logic here.',
    )
    code_body = fields.Text(
        string='Code (relaxaicode)',
        help='The deterministic mechanics that ran successfully. Source of truth.',
    )
    arg_hint = fields.Char(
        string='Argument hint',
        help='Placeholder shown in Chatboo when typing /<code> '
             '(e.g. "ytd" or "mes=2026-06"). Required if the skill accepts args.',
    )
    param_schema = fields.Text(
        string='Param schema (JSON)',
        help='JSON object of parameters for hybrid resolution: deterministic '
             'first, short LLM extraction only when free text is unresolved. '
             'Example: {"periodo": {"type": "string", "desc": "..."}}. '
             'Leave empty if the skill takes no arguments.',
    )
    agent_ids = fields.Many2many(
        'ai.agent',
        relation='pns_ai_mcp_skill_capture_wizard_agent_rel',
        column1='wizard_id',
        column2='agent_id',
        string='Agents',
        help='Agents that will expose the skill. Leave empty for a global skill.',
    )
    from_chatboo = fields.Boolean(
        string='From Chatboo',
        default=False,
        readonly=True,
        help='Set when opened via the /create-skill Chatboo command.',
    )
    warn_hardcoded_rows = fields.Boolean(
        string='Hardcoded rows warning',
        default=False,
        readonly=True,
        help='True when the captured code may contain pasted row literals.',
    )

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if not res.get('agent_ids') and (
            self.env.context.get('capture_from_chatboo')
            or self.env.context.get('default_from_chatboo')
        ):
            agent = self._chatboo_agent()
            if agent and 'agent_ids' in fields_list:
                res['agent_ids'] = [(6, 0, agent.ids)]
        return res

    @api.model
    def _chatboo_agent(self):
        try:
            from odoo.addons.pns_ai_mcp.utils.ai_agent_registry import (
                CHATBOO_AGENT_CODE,
            )
            code = CHATBOO_AGENT_CODE
        except Exception:
            code = 'pns_ai_chatboo'
        return self.env['ai.agent'].search([('code', '=', code)], limit=1)

    def _resolve_agent_ids(self):
        self.ensure_one()
        if self.agent_ids:
            return self.agent_ids.ids
        if self.from_chatboo:
            agent = self._chatboo_agent()
            return agent.ids if agent else []
        return []

    @staticmethod
    def _slugify(text):
        text = (text or '').strip().lower()
        text = re.sub(r'[^a-z0-9]+', '-', text)
        return text.strip('-')[:48] or 'captured-skill'

    @api.onchange('source_log_id')
    def _onchange_source_log_id(self):
        log = self.source_log_id
        if not log:
            return
        self.code_body = log.code_to_execute or ''
        prompt = (log.user_prompt or '').strip()
        if prompt:
            self.description = prompt[:120]
            if not self.skill_name:
                self.skill_name = prompt[:48]
            if not self.skill_code:
                self.skill_code = self._slugify(prompt)
        if not self.procedure:
            self.procedure = _(
                "When to use: describe the user request this skill answers.\n"
                "Parameters (hybrid): list user-facing args; prefer key=value / "
                "ISO / relative dates in the Code. Declare param_schema so free "
                "text can fall back to a short LLM extraction only when needed.\n"
                "Output: explain how to present the result.\n"
                "Run the Code with relaxaicode; do not recompute its logic.\n"
                "\n"
                "Code habits (sandbox AST — save will reject otherwise):\n"
                "- sorted/min/max key=: only operator.itemgetter('field') or "
                "lambda x: x['field']. Precompute complex sort keys as a field.\n"
                "- Helpers: flat defs (nesting depth max 2). No classes.\n"
                "- Params: try/except NameError; never invent dates if required.\n"
                "- External data: propose_steps (fetch_url / api_call), never requests."
            )

    def action_create_draft(self):
        self.ensure_one()
        if not self.code_body:
            raise UserError(_('There is no code to capture. Pick a source execution '
                              'or paste the code.'))
        if not (self.skill_code or '').strip() and not (self.skill_name or '').strip():
            raise UserError(_(
                'Enter a skill code or name before creating the skill.'
            ))
        raw = self._slugify(self.skill_code or self.skill_name)
        code, command = self.env['ai.skill'].allocate_instance_identity(raw)
        agent_ids = self._resolve_agent_ids()
        schema = (self.param_schema or '').strip()
        if schema:
            try:
                parsed = json.loads(schema)
            except Exception:
                raise UserError(_(
                    'Param schema must be valid JSON '
                    '(e.g. {"mes": {"type": "string", "desc": "YYYY-MM"}}).'
                ))
            if not isinstance(parsed, dict):
                raise UserError(_('Param schema must be a JSON object.'))
            schema = json.dumps(parsed, ensure_ascii=False, separators=(',', ':'))
        else:
            schema = False
        hint = (self.arg_hint or '').strip() or False
        if schema and not hint:
            raise UserError(_(
                'When param_schema is set, also provide arg_hint '
                '(Chatboo placeholder for /<code> arguments).'
            ))
        skill = self.env['ai.skill'].create({
            'code': code,
            'command': command,
            'name': self.skill_name or code,
            'description': self.description or (self.skill_name or code),
            'content': self.procedure or _('Describe when and how to use this skill.'),
            'code_body': self.code_body,
            'arg_hint': hint,
            'param_schema': schema,
            'agent_ids': [(6, 0, agent_ids)],
            'active': bool(self.from_chatboo),
            'is_system': False,
        })
        from odoo.addons.pns_ai_mcp.utils.mcp_ui import client_notification_close

        if skill.active:
            message = _(
                'Skill "%(name)s" is ready — use /%(code)s in Chatboo.'
            ) % {'name': skill.name, 'code': skill.invoke_code()}
        else:
            message = _(
                'Draft "%(name)s" saved (inactive). Activate it to use /%(code)s in Chatboo.'
            ) % {'name': skill.name, 'code': skill.invoke_code()}
        action = client_notification_close(_('Skill created'), message, 'success')
        action['params']['next'] = {
            'type': 'ir.actions.act_window',
            'name': skill.name,
            'res_model': 'ai.skill',
            'res_id': skill.id,
            'view_mode': 'form',
            'views': [[False, 'form']],
            'target': 'current',
        }
        return action
