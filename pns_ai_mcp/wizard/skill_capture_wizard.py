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
from odoo.addons.pns_ai_mcp.utils.llm_usage import add_usage
from odoo.addons.pns_ai_mcp.utils.skill_runtime import (
    apply_code_keys_to_rows,
    assign_extracted_keys_to_rows,
    fill_capture_params,
    infer_arg_hint_from_schema,
    infer_param_keys_from_code,
    is_placeholder_skill_help,
    overlay_rows_on_schema,
    param_rows_fingerprint,
    param_rows_to_prose,
    param_schema_to_json,
    parse_param_schema_txt,
    procedure_for_help,
    schema_keys_unread_by_code,
    schema_to_param_rows,
    skill_help_fingerprint,
)


class AISkillCaptureParamLine(models.TransientModel):
    _name = 'ai.skill.capture.param.line'
    _description = 'Skill capture parameter row'
    _order = 'sequence, id'

    wizard_id = fields.Many2one(
        'ai.skill.capture.wizard',
        ondelete='cascade',
        required=True,
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
        help='Empty = the default lives in the Code.',
    )
    required = fields.Boolean(
        string='Required',
        default=False,
        help='The slash must provide this parameter (or its Default).',
    )
    key = fields.Char(string='Key')


class AISkillCaptureWizard(models.TransientModel):
    _name = 'ai.skill.capture.wizard'
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
             '"pack-facturacion"). The catalog id and slash get the '
             'instance prefixes from Settings (snake code, kebab command).',
    )
    skill_name = fields.Char(string='Skill name')
    description = fields.Char(
        string='Help text',
        help='Text shown on the /slash ? help card.',
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
        help='Placeholder shown in Chatboo when typing /<code>. '
             'Filled from the Code when it reads slash args, or from '
             'the parameter list. Edit if you want a clearer example.',
    )
    args_policy = fields.Selection(
        selection=[
            ('default', 'Default (empty runs)'),
            ('ask', 'Ask (empty prompts)'),
            ('none', 'No arguments'),
        ],
        string='Empty-args policy',
        default='default',
        help='What /code with no arguments does. default: run with the '
             'code_body default. ask: show a card and wait. none: the skill '
             'takes no arguments.',
    )
    param_line_ids = fields.One2many(
        'ai.skill.capture.param.line',
        'wizard_id',
        string='Parameters',
        help='Concept, description and default. Empty = no parameters.',
    )
    param_prose = fields.Text(
        string='Parameter description',
        help='Leftover trainer text from /create-skill. Hidden; seeded '
             'into the parameter list when there is no schema yet.',
    )
    param_schema = fields.Text(
        string='Param schema (JSON)',
        help='Filled from the parameter list. Hidden in the wizard; the '
             'JSON lives on the skill.',
    )
    param_author_bundle = fields.Text(
        string='Author bundle',
        help='Last light IA parse (usage + fingerprint + help). Hidden.',
    )
    agent_ids = fields.Many2many(
        'ai.agent',
        relation='ai_skill_capture_wizard_agent_rel',
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
    warn_incomplete_capture = fields.Boolean(
        string='Incomplete capture warning',
        default=False,
        readonly=True,
        help='True when the source turn had several phases but fetch or '
             'transform logic could not be embedded in the Code.',
    )
    existing_skill_id = fields.Many2one(
        'ai.skill',
        string='Existing skill',
        readonly=True,
        help='Set when /create-skill or /edit-skill targets a slash you '
             'already own. Saving updates that skill instead of creating a new one.',
    )
    source_turn_id = fields.Char(
        string='Source turn',
        readonly=True,
        help='MCP turn chip this capture comes from. Not a slash parameter.',
    )
    show_advanced = fields.Boolean(
        string='Show advanced',
        default=False,
        help='Show Help, Procedure and Code. Off by default.',
    )
    _TURN_CHIP_RE = re.compile(r'^[A-Za-z0-9]{4}(?:-\d+)?$')

    @classmethod
    def _is_turn_chip(cls, text):
        return bool(cls._TURN_CHIP_RE.match((text or '').strip()))

    @classmethod
    def _prose_without_turn_chips(cls, text):
        kept = [
            part for part in (text or '').split()
            if not cls._is_turn_chip(part)
        ]
        return ' '.join(kept).strip()

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
        code = res.get('code_body') or ''
        schema = res.get('param_schema') or ''
        hint = res.get('arg_hint') or ''
        if not isinstance(schema, str):
            schema = ''
        if not isinstance(hint, str):
            hint = ''
        schema, hint = fill_capture_params(code, schema, hint)
        if schema and 'param_schema' in fields_list:
            res['param_schema'] = schema
        if hint and 'arg_hint' in fields_list:
            res['arg_hint'] = hint
        if 'param_line_ids' in fields_list and not res.get('param_line_ids'):
            rows = self._rows_from_schema_or_prose(
                schema, res.get('param_prose'),
            )
            res['param_line_ids'] = self._line_commands(rows)
        return res

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._seed_param_lines_if_needed()
        return records

    def _seed_param_lines_if_needed(self):
        for rec in self:
            if rec.param_line_ids:
                continue
            schema, hint = fill_capture_params(
                rec.code_body, rec.param_schema, rec.arg_hint,
            )
            vals = {}
            if schema and not (rec.param_schema or '').strip():
                vals['param_schema'] = schema
            if hint and not (rec.arg_hint or '').strip():
                vals['arg_hint'] = hint
            if vals:
                rec.write(vals)
            rows = rec._rows_from_schema_or_prose(
                rec.param_schema or schema, rec.param_prose,
            )
            if rows:
                rec._replace_param_lines(rows)

    @staticmethod
    def _rows_from_schema_or_prose(schema, prose):
        rows = schema_to_param_rows(schema)
        if rows:
            return rows
        text = AISkillCaptureWizard._prose_without_turn_chips(prose)
        if not text:
            return []
        return [{
            'key': '',
            'label': text.split('\n', 1)[0][:64],
            'desc': text,
            'default': '',
            'required': False,
        }]

    @staticmethod
    def _line_commands(rows):
        cmds = [(5, 0, 0)]
        for i, row in enumerate(rows or []):
            cmds.append((0, 0, {
                'sequence': 10 * (i + 1),
                'label': row.get('label') or row.get('key') or '',
                'desc': row.get('desc') or '',
                'default': row.get('default') or '',
                'required': bool(row.get('required')),
                'key': row.get('key') or '',
            }))
        return cmds

    def _replace_param_lines(self, rows):
        self.ensure_one()
        self.param_line_ids = self._line_commands(rows)

    def _param_rows(self):
        self.ensure_one()
        rows = []
        for line in self.param_line_ids.sorted(key=lambda l: (l.sequence, l.id)):
            label = (line.label or '').strip()
            desc = (line.desc or '').strip()
            default = (line.default or '').strip()
            key = (line.key or '').strip()
            if not label and not desc and not key:
                continue
            rows.append({
                'key': key,
                'label': label or key,
                'desc': desc,
                'default': default,
                'required': bool(line.required),
            })
        return rows

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
        if prompt and not (self.description or '').strip():
            self.description = prompt[:120]
        self._apply_inferred_params()
        if not self.procedure:
            self.procedure = _(
                "When to use: describe the user request this skill answers.\n"
                "Parameters: describe them in Help if the slash takes args.\n"
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

    @api.onchange('code_body')
    def _onchange_code_body(self):
        self._apply_inferred_params()

    def _apply_inferred_params(self):
        schema, hint = fill_capture_params(
            self.code_body, self.param_schema, self.arg_hint,
        )
        if not (self.param_schema or '').strip() and schema:
            self.param_schema = schema
            if not self.param_line_ids:
                self._replace_param_lines(schema_to_param_rows(schema))
        if not (self.arg_hint or '').strip() and hint:
            self.arg_hint = hint

    def _resolve_param_provider(self):
        try:
            from ..utils.agent_engine import resolve_providers_for_consumer
            providers = resolve_providers_for_consumer(
                self.env, consumer_key='admin',
            )
            return providers[:1] if providers else self.env['ai.provider']
        except Exception:
            return self.env['ai.provider']

    def _is_placeholder_description(self, text, *names):
        return is_placeholder_skill_help(text, *names)

    def _author_provider_chip(self, provider):
        if not provider:
            return {}
        rec = provider[:1]
        if not rec:
            return {}
        model = ''
        try:
            model = (
                (rec.model_id.name if rec.model_id else None)
                or rec.model_name or ''
            )
        except Exception:
            model = getattr(rec, 'model_name', None) or ''
        return {
            'model': model or '',
            'provider': rec.name or '',
        }

    def _author_bundle(self):
        raw = (self.param_author_bundle or '').strip()
        if not raw:
            return {}
        try:
            bundle = json.loads(raw)
        except Exception:
            return {}
        return bundle if isinstance(bundle, dict) else {}

    def _last_fingerprint(self):
        return (self._author_bundle().get('fingerprint') or '').strip()

    def _last_help_fingerprint(self):
        return (self._author_bundle().get('help_fingerprint') or '').strip()

    def _help_fingerprint(self, rows):
        return skill_help_fingerprint(
            procedure_for_help(self.procedure),
            self.code_body,
            rows,
        )

    def _reuse_author_bundle(self, fingerprint):
        bundle = self._author_bundle()
        if not bundle or not fingerprint or not (self.param_schema or '').strip():
            return None
        if (bundle.get('fingerprint') or '').strip() != fingerprint:
            return None
        return (
            self.param_schema,
            self.arg_hint or False,
            bundle.get('usage') or {},
            bundle.get('help') or '',
            bundle.get('provider') or {},
        )

    def _author_help_sentence(self, rows, usage, chip, extracted=None):
        """Light IA: Help text from Procedure / Code. Empty sources → no call."""
        help_fp = self._help_fingerprint(rows)
        help_changed = help_fp != self._last_help_fingerprint()
        placeholder = self._is_placeholder_description(
            self.description, self.skill_name, self.skill_code,
        )
        if self.env.context.get('skill_capture_skip_help'):
            # Do not store help_fp: the next wizard step still has to write Help.
            return '', usage, chip, '', False
        if not help_changed and not placeholder:
            return '', usage, chip, help_fp, False
        if (
            not procedure_for_help(self.procedure)
            and not (self.code_body or '').strip()
            and not rows
        ):
            return '', usage, chip, help_fp, False
        help_extracted = self.env.context.get('param_help_extracted')
        provider = None
        if help_extracted is None and extracted is None:
            provider = self._resolve_param_provider()
        help_txt, help_usage = self.env['ai.skill'].author_param_help(
            rows,
            provider=provider,
            extracted=help_extracted,
            procedure=self.procedure,
            code_body=self.code_body,
        )
        usage = add_usage(usage, help_usage)
        if provider:
            chip = chip or self._author_provider_chip(provider)
        return help_txt, usage, chip, help_fp, True

    def _trainer_prose(self, rows):
        prose = param_rows_to_prose(rows)
        leftover = self._prose_without_turn_chips(self.param_prose)
        if leftover and leftover not in prose:
            return (prose + '\n' + leftover).strip() if prose else leftover
        return prose

    def _capture_param_fields(self):
        """List → schema. Empty list = no params. Help from Procedure/Code."""
        Skill = self.env['ai.skill']
        rows = self._param_rows()
        extracted = self.env.context.get('param_author_extracted')
        if not rows:
            help_txt, usage, chip, help_fp, help_wanted = (
                self._author_help_sentence([], {}, {}, extracted)
            )
            return {
                'schema': False,
                'hint': False,
                'usage': usage,
                'help': help_txt,
                'chip': chip,
                'empty': True,
                'rows': [],
                'fingerprint': param_rows_fingerprint([]),
                'help_fingerprint': help_fp,
                'list_changed': False,
                'help_changed': help_wanted,
            }

        code_keys = infer_param_keys_from_code(self.code_body)
        rows = apply_code_keys_to_rows(rows, code_keys)
        fingerprint = param_rows_fingerprint(rows)
        list_changed = fingerprint != self._last_fingerprint()
        force_author = extracted is not None
        need_keys = any(not (r.get('key') or '').strip() for r in rows)

        usage = {}
        chip = {}
        schema_txt = self.param_schema
        hint = self.arg_hint
        prose = self._trainer_prose(rows)

        if need_keys or force_author:
            provider = None
            if extracted is None:
                provider = self._resolve_param_provider()
            schema_txt, hint, usage, _help_from_author = Skill.author_param_schema(
                self.param_schema, prose, self.code_body, self.arg_hint,
                provider=provider, extracted=extracted,
            )
            chip = self._author_provider_chip(provider)
            extracted_map = extracted
            if extracted_map is None:
                extracted_map = parse_param_schema_txt(schema_txt)
            if extracted_map and not extracted_map.get('_reject'):
                rows = assign_extracted_keys_to_rows(
                    rows, extracted_map, code_keys,
                )
                rows = apply_code_keys_to_rows(rows, code_keys)
                for row in rows:
                    spec = extracted_map.get(row.get('key'))
                    if isinstance(spec, dict) and spec.get('desc'):
                        row['desc'] = spec['desc']
            else:
                rows = apply_code_keys_to_rows(rows, code_keys)
            schema_dict = overlay_rows_on_schema(rows, schema_txt)
            schema_txt = param_schema_to_json(schema_dict) or False
            hint = infer_arg_hint_from_schema(schema_dict) or False
        elif not list_changed:
            reused = self._reuse_author_bundle(fingerprint)
            schema_dict = overlay_rows_on_schema(rows, self.param_schema)
            schema_txt = param_schema_to_json(schema_dict) or False
            hint = infer_arg_hint_from_schema(schema_dict) or False
            if reused:
                schema_txt = reused[0] or schema_txt
                hint = reused[1] or hint
                usage = reused[2] or {}
                chip = reused[4] or {}
        else:
            schema_dict = overlay_rows_on_schema(rows, self.param_schema)
            schema_txt = param_schema_to_json(schema_dict) or False
            hint = infer_arg_hint_from_schema(schema_dict) or False

        fingerprint = param_rows_fingerprint(rows)
        help_txt, usage, chip, help_fp, help_wanted = self._author_help_sentence(
            rows, usage, chip, extracted,
        )
        return {
            'schema': schema_txt,
            'hint': hint,
            'usage': usage,
            'help': help_txt,
            'chip': chip,
            'empty': False,
            'rows': rows,
            'fingerprint': fingerprint,
            'help_fingerprint': help_fp,
            'list_changed': list_changed,
            'help_changed': help_wanted,
        }

    def _adapt_code_to_schema(self, schema, usage, rows=None):
        """Rewrite Code when schema keys are unread. Adds rewrite usage."""
        rewritten = self.env.context.get('param_code_rewritten')
        extracted = self.env.context.get('param_author_extracted')
        unread = schema_keys_unread_by_code(schema, self.code_body)
        provider = None
        if unread and rewritten is None and extracted is None:
            provider = self._resolve_param_provider()
        prose = param_rows_to_prose(rows if rows is not None else self._param_rows())
        leftover = self._prose_without_turn_chips(self.param_prose)
        if leftover and leftover not in prose:
            prose = (prose + '\n' + leftover).strip() if prose else leftover
        code, rewrite_usage = self.env['ai.skill'].rewrite_code_for_params(
            self.code_body, schema, prose,
            provider=provider,
            rewritten=rewritten,
        )
        return code, add_usage(dict(usage or {}), rewrite_usage)

    def _reload_form(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'views': [[False, 'form']],
            'target': 'new',
            'context': dict(self.env.context),
        }

    def action_toggle_advanced(self):
        self.ensure_one()
        self.show_advanced = not self.show_advanced
        return self._reload_form()

    def _bundle_json(self, captured):
        return json.dumps({
            'fingerprint': captured.get('fingerprint') or '',
            'help_fingerprint': captured.get('help_fingerprint') or '',
            'usage': captured.get('usage') or {},
            'help': captured.get('help') or '',
            'provider': captured.get('chip') or {},
        }, ensure_ascii=False)

    def _step_reply(self, usage, **extra):
        """JSON for a stepped author RPC. Usage only if the provider sent some."""
        payload = {'ok': True}
        payload.update(extra)
        acc = usage if isinstance(usage, dict) else {}
        if acc:
            payload['usage'] = acc
        return payload

    def _apply_help_vals(self, captured, vals, *extra_names):
        if captured.get('help') and (
            captured.get('help_changed')
            or self._is_placeholder_description(
                self.description, self.skill_name, self.skill_code, *extra_names
            )
        ):
            vals['description'] = captured['help']
        return vals

    def action_author_params(self):
        """Wizard step: list → schema. No Help LLM."""
        self.ensure_one()
        captured = self.with_context(
            skill_capture_skip_help=True,
        )._capture_param_fields()
        if captured['empty']:
            vals = {
                'param_schema': False,
                'arg_hint': False,
                'args_policy': 'none',
                'param_author_bundle': self._bundle_json(captured),
                'param_line_ids': [(5, 0, 0)],
            }
        else:
            vals = {
                'param_schema': captured['schema'] or False,
                'arg_hint': captured['hint'] or False,
                'param_author_bundle': self._bundle_json(captured),
                'param_line_ids': self._line_commands(captured['rows']),
            }
        self.write(vals)
        return self._step_reply(captured.get('usage'), empty=captured['empty'])

    def action_author_help(self):
        """Wizard step: Help sentence from Procedure / Code."""
        self.ensure_one()
        rows = self._param_rows()
        prior = self._author_bundle()
        help_txt, usage, chip, help_fp, help_wanted = (
            self._author_help_sentence(
                rows,
                dict(prior.get('usage') or {}),
                prior.get('provider') or {},
            )
        )
        captured = {
            'help': help_txt,
            'help_changed': help_wanted,
            'help_fingerprint': help_fp,
            'usage': usage,
            'chip': chip,
            'fingerprint': prior.get('fingerprint') or param_rows_fingerprint(rows),
            'rows': rows,
            'empty': not rows,
        }
        vals = {
            'param_author_bundle': self._bundle_json(captured),
        }
        self.write(self._apply_help_vals(captured, vals))
        return self._step_reply(usage)

    def action_adapt_code(self):
        """Wizard step: rewrite Code when schema keys are unread."""
        self.ensure_one()
        prior = self._author_bundle()
        prior_usage = dict(prior.get('usage') or {})
        schema = self.param_schema
        if not (schema or '').strip():
            return self._step_reply(prior_usage)
        code, usage = self._adapt_code_to_schema(schema, prior_usage)
        vals = {
            'param_author_bundle': self._bundle_json({
                'fingerprint': prior.get('fingerprint') or '',
                'help_fingerprint': prior.get('help_fingerprint') or '',
                'usage': usage,
                'help': prior.get('help') or '',
                'chip': prior.get('provider') or {},
            }),
        }
        if code != (self.code_body or ''):
            vals['code_body'] = code
        self.write(vals)
        return self._step_reply(usage)

    def _snapshot_authored_capture(self):
        """Fields already written by the stepped author RPCs."""
        rows = self._param_rows()
        bundle = self._author_bundle()
        return {
            'schema': self.param_schema or False,
            'hint': self.arg_hint or False,
            'usage': bundle.get('usage') or {},
            'help': '',
            'chip': bundle.get('provider') or {},
            'empty': not rows,
            'rows': rows,
            'help_changed': False,
        }

    def _resolve_target_skill(self, raw):
        """Owned skill to replace, or empty to create a new slash."""
        Skill = self.env['ai.skill']
        if self.existing_skill_id:
            token = (
                self.existing_skill_id.command
                or self.existing_skill_id.code
            )
            return Skill._owned_mutable_skill(token)
        _code, _command, existing = Skill.resolve_capture_identity(raw)
        return existing

    def action_create_draft(self):
        self.ensure_one()
        if not self.code_body:
            raise UserError(_('There is no code to capture. Pick a source execution '
                              'or paste the code.'))
        if not (self.skill_name or '').strip():
            raise UserError(_(
                'Enter a skill name before creating the skill.'
            ))
        raw = self._slugify(self.skill_code or self.skill_name)
        Skill = self.env['ai.skill']
        existing = self._resolve_target_skill(raw)
        agent_ids = self._resolve_agent_ids()
        if self.env.context.get('skill_capture_authored'):
            captured = self._snapshot_authored_capture()
            schema = captured['schema']
            hint = captured['hint']
            usage = captured['usage']
            help_txt = captured['help']
            chip = captured['chip']
            code = self.code_body
        else:
            captured = self._capture_param_fields()
            schema = captured['schema']
            hint = captured['hint']
            usage = captured['usage']
            help_txt = captured['help']
            chip = captured['chip']
            if captured['empty']:
                schema = False
                hint = False
                code = self.code_body
            else:
                code, usage = self._adapt_code_to_schema(
                    schema, usage, rows=captured['rows'],
                )
        extra_ctx = {}
        if usage:
            extra_ctx['skill_author_usage'] = usage
        if chip:
            extra_ctx['skill_author_provider'] = chip
        if extra_ctx:
            self = self.with_context(**extra_ctx)
            Skill = self.env['ai.skill']
            existing = self._resolve_target_skill(raw)
        description = self.description or (self.skill_name or raw)
        if help_txt and (
            captured.get('help_changed')
            or self._is_placeholder_description(
                description, self.skill_name, self.skill_code, raw,
            )
        ):
            description = help_txt
        args_policy = (
            'none' if captured['empty'] else (self.args_policy or 'default')
        )
        from odoo.addons.pns_ai_mcp.utils.skill_runtime import (
            check_skill_fast_path_publishable,
        )
        publish_err = self.env['ai.skill']._run_and_undo(
            lambda: check_skill_fast_path_publishable(
                self.env,
                code,
                arguments='',
                args_policy=args_policy,
                param_schema=schema,
                skill_code=raw,
            )
        )
        if publish_err:
            raise UserError(publish_err)
        vals = {
            'name': self.skill_name or (
                existing.code if existing else raw
            ),
            'description': description,
            'content': self.procedure or _(
                'Describe when and how to use this skill.'
            ),
            'code_body': code,
            'arg_hint': hint,
            'param_schema': schema,
            'args_policy': args_policy,
            'agent_ids': [(6, 0, agent_ids)],
        }
        replaced = bool(existing)
        Skill = Skill.with_context(skip_skill_form_author=True)
        if existing:
            existing.with_context(skip_skill_form_author=True).write(vals)
            skill = existing
        else:
            code, command = Skill.allocate_instance_identity(raw)
            vals.update({
                'code': code,
                'command': command,
                'name': self.skill_name or code,
                'description': description or (self.skill_name or code),
                'active': bool(self.from_chatboo),
                'is_system': False,
            })
            skill = Skill.create(vals)
        from odoo.addons.pns_ai_mcp.utils.mcp_ui import client_notification_close

        if replaced:
            message = _(
                'Skill "%(name)s" was updated — use /%(code)s in Chatboo.'
            ) % {'name': skill.name, 'code': skill.invoke_code()}
            title = _('Skill saved')
        elif skill.active:
            message = _(
                'Skill "%(name)s" is ready — use /%(code)s in Chatboo.'
            ) % {'name': skill.name, 'code': skill.invoke_code()}
            title = _('Skill created')
        else:
            message = _(
                'Draft "%(name)s" saved (inactive). Activate it to use /%(code)s in Chatboo.'
            ) % {'name': skill.name, 'code': skill.invoke_code()}
            title = _('Skill created')
        action = client_notification_close(title, message, 'success')
        if self.from_chatboo:
            return action
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
