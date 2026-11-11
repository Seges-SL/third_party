# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""ai.skill — selectable procedure exposed over MCP (distinct from context/bundle)."""

import logging
import re

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from odoo.addons.pns_base.utils.compat import ODOO_VERSION, USER_ALL_GROUPS_FIELD
from ..utils.knowledge_ownership import (
    apply_create_ownership,
    assert_writer_can_write_records,
    factory_lock_open,
    filter_visible_records,
)
from ..utils.skill_live_code import code_has_frozen_result_rows
from ..utils.skill_code_prefix import (
    get_skill_command_prefix,
    slash_slug,
    unprefixed_twin_stems,
)
from ..utils.skill_help import slash_list_sort_key

_logger = logging.getLogger(__name__)

SKILL_PROMPT_PREFIX = 'skill.'
EXPORT_FORMAT_VERSION = 1

# Operator slash-menu hides: durable across factory re-seed / i_restore.
# The Boolean on ai.skill is the UI mirror; this ICP is the source of truth.
ICP_SKILLS_SLASH_HIDDEN = 'pns_ai_mcp.skills_slash_hidden'


class _RunUndone(Exception):
    """Raised inside a savepoint so that it always rolls back."""


class AISkill(models.Model):
    """Selectable AI procedure exposed via MCP and the chat '/' menu.

    A Skill is a structured procedure that extends the AI's capabilities.
    Unlike contexts (which are injected automatically), skills are explicitly
    selected by the user (via ``/skill-code`` in chat) or by the AI itself
    (when it determines the user's intent matches a skill's description).

    Dual source: disk → DB sync::

        common/ai/skills/<code>/      ← source of truth (version-controlled)
            skill.md                  ← Markdown content (prose + orchestration)
            code.py                   ← Optional Python code (formulas, logic)
        ↕ action_reload_from_disk()
        ai.skill DB record            ← runtime copy (editable in UI)

    The ``content`` field contains the Markdown orchestration (WHEN to use,
    WHAT it does, HOW to present results). The optional ``code_body``
    field contains executable Python (relaxaicode) that the skill's
    orchestration can reference.

    Exposed over MCP as prompt name ``skill.<command or code>`` and invoked
    in chat as ``/<command or code>``. Catalog identity (``code``, filename)
    is snake_case; the slash (``command``) is kebab-case.

    Key fields:
      - code:          Snake_case catalog id (e.g. 'sample_topic')
      - command:       Kebab slash without leading / (e.g. 'sample-topic');
                       empty = same as code
      - name:          Human-readable name (translatable)
      - description:   Short hint for the AI and the / menu (translatable)
      - content:       Markdown orchestration (WHEN/WHAT/HOW)
      - code_body:     Optional Python code (relaxaicode formulas, logic)
      - agent_ids:     Agents that expose this skill (empty = global)
      - is_system:     True when seeded from module files (ai/skills/system/)
      - rel_path:      Relative module path of the source file
    """
    _name = 'ai.skill'
    _inherit = ['ai.skill.param.token.legend.mixin']
    _description = 'Skill (selectable procedure for MCP)'
    _order = 'sequence, code'

    name = fields.Char(required=True, translate=True)
    code = fields.Char(
        required=True,
        help='Catalog identity (unique, snake_case). Example: sample_topic. '
             'Tenant artefacts may be longer (custom_tenant_topic). Hyphens are '
             'not allowed — the slash lives in Command.',
    )
    command = fields.Char(
        string='Slash command',
        help='Chat invocation without leading slash (kebab-case, e.g. sample-topic → '
             '/sample-topic). Empty = same as Code. MCP prompt is skill.<command or code>.',
    )
    sequence = fields.Integer(default=10)
    description = fields.Char(
        required=True,
        translate=True,
        help='Short selection hint shown in prompts/list. The model uses it to '
             'decide whether to load this skill, so make it precise.',
    )
    content = fields.Text(
        required=True,
        help='PROSE / orchestration (Markdown). Describe WHEN to use the skill, '
             'WHAT it does at a high level, the user-facing parameters, and HOW to '
             'present/interpret the result. Do NOT restate the formulas/logic that '
             'live in "Code" — that causes drift. The Code is the source of truth '
             'for any computation; this field tells the agent when to run it and '
             'what to do with the output.',
    )
    code_body = fields.Text(
        string='Code (relaxaicode)',
        help='Executable Python (relaxaicode) = the deterministic mechanics '
             '(queries, math, scoring). This is the SOURCE OF TRUTH for the '
             'computation; the agent runs it via relaxaicode. Keep it '
             'self-contained and do NOT duplicate here the guidance/presentation '
             'that belongs in "Procedure".',
    )
    agent_ids = fields.Many2many(
        'ai.agent',
        'ai_agent_skill_rel',
        'skill_id',
        'agent_id',
        string='Agents',
        help='Agents that expose this skill. Leave empty for a global skill '
             'available to every agent.',
    )
    context_ids = fields.Many2many(
        'ai.context',
        'ai_skill_context_rel',
        'skill_id',
        'context_id',
        string='Referenced contexts',
        help='Knowledge the skill relies on. Referenced (not duplicated): the '
             'context content is appended when the skill is served.',
    )
    version = fields.Char(help='Free version tag for change tracking.')
    param_schema = fields.Text(
        string='Param schema (JSON)',
        help='Optional JSON documenting skill params, e.g. '
             '{"fecha": {"type": "string", "desc": "YYYY-MM-DD"}}. Enables a '
             'short LLM extraction ONLY when deterministic parsing '
            '(key=value, ISO, relative dates) leaves holes. Types: string, '
            'array, integer, number. Hidden in the form; the parameter '
            'list is the Settings UI.',
    )
    param_line_ids = fields.One2many(
        'ai.skill.param.line',
        'skill_id',
        string='Parameters',
        help='Concept, description and default. Empty = no parameters. '
             'Serialized to Param schema.',
    )
    param_cache_ids = fields.One2many(
        'ai.skill.param.cache',
        'skill_id',
        string='Learned phrases',
        help='Unresolved slash text (spaces collapsed, case-folded) mapped to '
             'the JSON the model produced. The same phrase later uses this row '
             'and does not call the model. Edit or add rows here.',
    )
    arg_hint = fields.Char(
        string='Argument hint',
        help='Short example of the arguments this skill expects, shown as the '
             'input placeholder when the user picks/types the skill in the chat '
             '(e.g. "Sevilla mañana" or "mes=2025-01"). Purely informative; the '
             'hybrid parser (deterministic first, LLM fallback) reads the args.',
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
             'code_body default (e.g. last month with data). ask: show a '
             'card and wait. none: the skill takes no arguments.',
    )
    compose = fields.Selection(
        selection=[
            ('compose-agent', 'compose-agent'),
            ('compose-model', 'compose-model'),
        ],
        string='Compose',
        default=False,
        help='Optional compose override when the skill is invoked via /slash. '
             'Empty = inherit the provider compose. '
             'compose-agent: the agent composes HTML tables/charts. '
             'compose-model: the model owns the entire bubble. '
             'One-shot for that invocation; does not write the provider.',
    )
    triggers = fields.Char(
        string='NL triggers',
        help='Phrases that run this skill from a normal sentence, '
             'comma-separated. One matching skill runs as if the user had '
             'typed the slash; the sentence is the arguments. Several '
             'matches do not run. The slash still works.',
    )
    active = fields.Boolean(default=True)
    show_in_slash = fields.Boolean(
        string='Show in slash menu',
        default=True,
        help='When unchecked, the skill stays installed but is hidden from the '
             'chat "/" autocomplete and /skills list. Exact /command still '
             'works. Stored in ir.config_parameter so factory re-seed / restore '
             'does not put it back in the slash menu.',
    )
    required_group_ids = fields.Many2many(
        'res.groups',
        'ai_skill_required_group_rel',
        'skill_id',
        'group_id',
        string='Required groups',
        help='Groups of which the user must have at least one to see this '
             'skill in the slash menu and to run it. Empty = any user who '
             'can use the agent.',
    )
    is_system = fields.Boolean(
        string='System skill',
        default=False,
        help='System skill seeded from module files (ai/skills/system/). Synced on '
             'module install/update. User skills (custom) live in ai/skills/custom/.',
    )
    source_module = fields.Char(
        string='Source Module',
        readonly=True,
        index=True,
        help='Technical name of the module that shipped this file. '
             'Empty = no module sealed it (user, old ZIP, or pack before '
             'source_module).',
    )
    composition_origin = fields.Selection(
        selection=[
            ('own', 'Own'),
            ('imported', 'Imported'),
            ('inserted', 'Inserted'),
            ('extra', 'Extra'),
        ],
        string='Origin',
        compute='_compute_composition_origin',
        search='_search_composition_origin',
        help="Why this row is on the current agent. Own: from this agent's module. "
             "Imported: from another module; this agent asks for it. "
             "Inserted: from another module; that module puts it in this agent. "
             "Extra: no module manages it; a person added it. "
             "Empty source_module is extra.",
    )
    link_visible = fields.Boolean(
        compute='_compute_composition_origin',
        search='_search_link_visible',
    )
    rel_path = fields.Char(
        string='Source file',
        help='Portable path within the cognitive tree, umbrella-agnostic '
             '(e.g. skills/system/<code>.md). On disk the files live under the '
             'module ai/ umbrella (ai/skills/...).',
    )
    owner_id = fields.Many2one(
        'res.users',
        string='Owner',
        index=True,
        ondelete='set null',
        help='User who owns this skill. Empty for module/import skills.',
    )
    if ODOO_VERSION >= 19:
        _code_uniq = models.Constraint(
            'unique(code)',
            'Skill code must be unique.',
        )
    else:
        _sql_constraints = [
            ('code_uniq', 'unique(code)', 'Skill code must be unique.'),
        ]

    @api.depends('code', 'source_module')
    @api.depends_context('composition_agent_id', 'active_id', 'active_model')
    def _compute_composition_origin(self):
        agent = self.env['ai.agent'].composition_agent_from_env()
        shown = set(agent._link_origins_shown()) if agent else None
        for rec in self:
            if not agent:
                rec.composition_origin = False
                rec.link_visible = True
                continue
            rec.composition_origin = agent.composition_origin_for(
                rec.code, rec.source_module, kind='skill',
            )
            rec.link_visible = rec.composition_origin in shown

    def _search_composition_origin(self, operator, value):
        return self.env['ai.agent']._comodel_origin_search_domain(
            self, 'skill', operator, value,
        )

    def _search_link_visible(self, operator, value):
        return self.env['ai.agent']._comodel_link_visible_search_domain(
            self, 'skill', operator, value,
        )

    @staticmethod
    def _compose_from_meta(meta):
        from ..utils.formatting_mode_policy import normalize_compose
        raw = (meta.get('compose') or '').strip().lower()
        return normalize_compose(raw) or False

    def _required_groups_from_meta(self, meta):
        """Group xmlids named by the file, resolved to records (unknown skipped)."""
        raw = (meta or {}).get('required_groups') or ''
        groups = self.env['res.groups'].browse()
        for xmlid in [p.strip() for p in str(raw).split(',') if p.strip()]:
            group = self.env.ref(xmlid, raise_if_not_found=False)
            if group:
                groups |= group
            else:
                _logger.warning(
                    'MCP: skill file names unknown group %s', xmlid,
                )
        return groups

    @staticmethod
    def _args_policy_from_meta(meta):
        from ..utils.skill_help import normalize_args_policy
        meta = meta or {}
        has_params = bool(
            (meta.get('param_schema') or '').strip()
            or (meta.get('arg_hint') or '').strip()
        )
        return normalize_args_policy(
            meta.get('args_policy'),
            has_params=has_params,
        )

    def invoke_code(self):
        """Slash / MCP short id: Command if set, otherwise Code."""
        self.ensure_one()
        return ((self.command or '').strip() or (self.code or '').strip())

    def _lookup_param_cache(self, leftover):
        """Cached hybrid params for leftover prose, or None."""
        self.ensure_one()
        if not self.id:
            return None
        return self.env['ai.skill.param.cache']._lookup_for_skill(
            self.id, leftover,
        )

    def _remember_param_cache(self, leftover, norm):
        """Store leftover → IA params if this phrase is new."""
        self.ensure_one()
        if not self.id:
            return self.env['ai.skill.param.cache']
        return self.env['ai.skill.param.cache']._remember_for_skill(
            self.id, leftover, norm,
        )

    @api.constrains('code', 'command')
    def _check_code(self):
        for skill in self:
            tokens = [
                t for t in (
                    (skill.code or '').strip(),
                    (skill.command or '').strip(),
                ) if t
            ]
            for token in tokens:
                if token.startswith(SKILL_PROMPT_PREFIX):
                    raise ValidationError(_(
                        'Skill code must not include the "%s" prefix; it is added '
                        'automatically when exposed over MCP.'
                    ) % SKILL_PROMPT_PREFIX)
            cmd = (skill.command or '').strip()
            if cmd:
                clash = self.search([
                    ('id', '!=', skill.id),
                    '|', ('command', '=', cmd), ('code', '=', cmd),
                ], limit=1)
                if clash:
                    raise ValidationError(_(
                        'Slash command "%s" is already used by skill "%s".'
                    ) % (cmd, clash.invoke_code() or clash.code))
            code = (skill.code or '').strip()
            if code and not re.fullmatch(r'[a-z0-9_]+', code):
                raise ValidationError(_(
                    'Skill code must be snake_case (letters, digits, '
                    'underscore). Put the kebab-case slash id in Command.'
                ))
            if cmd and not re.fullmatch(r'[a-z0-9-]+', cmd):
                raise ValidationError(_(
                    'Slash command must be kebab-case (letters, digits, '
                    'hyphens). Do not use underscores in Command.'
                ))

    def _raise_unpublished_capability(self, skill_name, unknown):
        raise ValidationError(_(
            'Skill %s requests engine capability "%s", which this engine '
            'does not provide. Change the skill or propose a nameless '
            'generic mechanism; do not patch the addon.'
        ) % (skill_name or '?', ', '.join(unknown)))

    @api.constrains('code_body', 'content')
    def _check_code_body_contract(self):
        """Enforce the `code_body` contract on save (not only at runtime).

        Goal: good practice applies IMPLICITLY, whether the skill comes from
        capture, import or manual editing. Three layers:

        1. AST (blocking): the same sandbox rules as at run time (forbidden
           imports, dangerous functions, `result` assignment) and no
           writes: a skill reads and proposes (``propose_steps``). Single source
           ``skill_code_refusal``, which is also checked on every run.
        2. Published contract (blocking): ``requires`` / front-matter / dunders
           not listed in ``skill_engine_contract`` → error. The engine is not
           patched for one concrete skill.
        3. Best-effort smoke run (only with the registry ready, never on install),
           inside a savepoint that is always rolled back:
           runs the code_body with empty arguments and, ONLY if it runs clean and
           returns something that is not a dict, blocks with the exact reason. If it
           raises (e.g. it depends on parameters), it does NOT block: the AST
           already covered what matters and we avoid false positives.
        """
        from ..utils.skill_engine_contract import skill_contract_violations
        from ..utils.skill_runtime import (
            bootstrap_skill_code_body,
            check_skill_fast_path_publishable,
            skill_code_refusal,
        )
        for skill in self:
            meta, _body = self._skill_parse_md(skill.content or '')
            code = (skill.code_body or '').strip()
            unknown = skill_contract_violations(meta=meta, code_body=code)
            if unknown:
                self._raise_unpublished_capability(
                    skill.code or skill.name, unknown,
                )
            if not code:
                continue  # prompt-only skill: the LLM runs it, no contract
            refused = skill_code_refusal(code, skill.code or skill.name)
            if refused:
                raise ValidationError(refused)
            if code_has_frozen_result_rows(code):
                raise ValidationError(_(
                    "The code_body of skill «%s» looks like a frozen snapshot "
                    "(data/rows assigned to a list of pasted dicts). "
                    "Query Odoo or an API on each run; do not embed result rows."
                ) % (skill.code or skill.name or '?'))
            # Smoke run: only outside install/upgrade (registry ready).
            # A captured page already ran. Checking it again would open it.
            if not self.env.registry.ready or self.env.context.get(
                'skill_skip_body_check',
            ):
                continue
            diag = {}

            def _smoke(skill=skill, code=code, diag=diag):
                boot = bootstrap_skill_code_body(
                    self.env(context=dict(
                        self.env.context, skill_publish_check=True,
                    )),
                    code, arguments='',
                    skill_code=skill.code or 'skill', diag=diag,
                    param_schema=skill.param_schema,
                )
                publish_err = check_skill_fast_path_publishable(
                    self.env,
                    code,
                    arguments='',
                    args_policy=skill.args_policy,
                    param_schema=skill.param_schema,
                    skill_code=skill.code or skill.name,
                )
                return boot, publish_err

            try:
                boot, publish_err = self._run_and_undo(_smoke)
            except Exception:
                # Run with empty args failed: it may depend on parameters.
                # We do not block (avoids false positives); the AST already checked.
                continue
            if diag.get('result_not_dict'):
                raise ValidationError(_(
                    "The code_body of skill «%s» assigned a %s to `result`. "
                    "The contract requires a dict: {'data': [...]} (table), "
                    "{'formatted_text': '<html>'} (card) or "
                    "{'propose_steps': [...]} (HTTP). Wrap your list, e.g. "
                    "result = {'data': rows, '__return_direct__': True}."
                ) % (skill.code or skill.name or '?', diag.get('result_type', '?')))
            if isinstance(boot, dict):
                unknown = skill_contract_violations(result=boot)
                if unknown:
                    self._raise_unpublished_capability(
                        skill.code or skill.name, unknown,
                    )
            if publish_err:
                raise ValidationError(publish_err)

    def _run_and_undo(self, fn):
        """``fn()`` on this cursor; whatever it wrote is rolled back.

        Saving a skill runs its code once to check the contract. That run is
        the author's, inside the save, and must leave nothing behind.
        """
        out = {}
        try:
            with self.env.cr.savepoint():
                out['value'] = fn()
                raise _RunUndone()
        except _RunUndone:
            pass
        return out['value']

    @api.model_create_multi
    def create(self, vals_list):
        prepared = [
            apply_create_ownership(vals, self.env, module_markers=('is_system', 'source_module'))
            for vals in vals_list
        ]
        records = super(AISkill, self).create(prepared)
        # Factory / ZIP create always defaults True; re-apply operator hides.
        records._apply_slash_hidden_from_icp()
        # Also persist explicit False from vals into ICP.
        if any(not v.get('show_in_slash', True) for v in prepared):
            records.filtered(lambda s: not s.show_in_slash)._sync_slash_hidden_icp()
        if self._param_line_sync_allowed():
            for rec, vals in zip(records, prepared):
                if vals.get('param_line_ids'):
                    rec._write_schema_from_param_lines()
                elif vals.get('param_schema'):
                    rec._create_param_lines_from_schema()
        if self._skill_form_author_allowed():
            records._author_form_help_and_params()
        return records

    def write(self, vals):
        if not factory_lock_open(self.env):
            assert_writer_can_write_records(self, self.env)
            if not self.env.user.has_group('pns_ai_mcp.group_ai_admin'):
                if vals.get('is_system'):
                    raise UserError(_(
                        'System skills are read-only for AI Writers.'
                    ))
                if 'owner_id' in vals:
                    raise UserError(_(
                        'Only administrators can change skill ownership.'
                    ))
        res = super(AISkill, self).write(vals)
        if (
            'show_in_slash' in vals
            and not self.env.context.get('skip_slash_icp_sync')
        ):
            self._sync_slash_hidden_icp()
        if not self._param_line_sync_allowed():
            return res
        if 'param_line_ids' in vals and 'param_schema' not in vals:
            self._write_schema_from_param_lines()
        elif 'param_schema' in vals and 'param_line_ids' not in vals:
            self._sync_param_lines_from_schema()
        if self._skill_form_author_allowed():
            self._author_form_help_and_params()
        return res

    def unlink(self):
        if not factory_lock_open(self.env):
            assert_writer_can_write_records(self, self.env)
            system_skills = self.filtered('is_system')
            if system_skills:
                raise UserError(_(
                    'System skills cannot be deleted.'
                ))
        return super(AISkill, self).unlink()

    @api.model
    def filter_visible_for_user(self, records, user=None):
        return filter_visible_records(records, user=user or self.env.user)

    # ------------------------------------------------------------------
    # MCP exposure
    # ------------------------------------------------------------------

    @api.model
    def get_for_agent(self, agent_code, user=None):
        """Active skills for an agent: agent-specific ones plus global (no agent)."""
        user = user or self.env.user
        agent = (
            self.env['ai.agent'].search([('code', '=', agent_code)], limit=1)
            if agent_code else False
        )
        if agent:
            domain = ['|', ('agent_ids', '=', False), ('agent_ids', 'in', agent.id)]
        else:
            domain = [('agent_ids', '=', False)]
        return self.filter_visible_for_user(self.search(domain), user=user)

    def _resolve_context_text(self, user_locale=None):
        """Resolve referenced contexts to text, honouring locale when possible."""
        self.ensure_one()
        Context = self.env['ai.context']
        parts = []
        visible_contexts = self.env['ai.context'].filter_visible_for_user(
            self.context_ids.filtered('active'),
        )
        for ctx in visible_contexts:
            text = ctx.content or ''
            try:
                base_name = ctx.base_code or ctx.code
                localized = Context.get_context_for_country(
                    base_name, user_locale=user_locale,
                )
                if localized:
                    text = localized.content or text
            except Exception:
                pass
            if text:
                parts.append('### %s\n%s' % (ctx.code, text))
        return '\n\n'.join(parts)

    def build_prompt_payload(self, user_locale=None):
        """Return {description, text} for prompts/get."""
        self.ensure_one()
        sections = ['# Skill: %s' % self.name]
        if self.version:
            sections.append('_v%s_' % self.version)
        if self.content:
            sections.append(self.content)
        if self.code_body:
            sections.append(
                '---\n## Code to execute (relaxaicode)\n'
                'This code is the deterministic source of truth of the skill. '
                'On slash invoke (`/%s`) the server may already have run it '
                '(BOOTSTRAP_RESULT) and even finished via skill fast-path '
                '(propose_steps fetch_url + presentation). If you see '
                'BOOTSTRAP_RESULT, do NOT re-run this code. Otherwise run it '
                'as-is with relaxaicode (adjust only documented '
                'parameters); do NOT recompute its logic by hand.\n'
                'Contract for short paths: result may include propose_steps '
                '(Safe Plan) and/or presentation / __return_direct__ with '
                'data|groups|formatted_text.'
                '\n```python\n%s\n```' % (
                    self.invoke_code() or 'skill',
                    self.code_body.strip(),
                )
            )
        ctx_text = self._resolve_context_text(user_locale=user_locale)
        if ctx_text:
            sections.append('---\n## Referenced knowledge\n%s' % ctx_text)
        return {
            'description': self.description or self.name,
            'text': '\n\n'.join(s for s in sections if s),
        }

    # ------------------------------------------------------------------
    # Slash invocation (inference host)
    # ------------------------------------------------------------------
    def user_may_run(self, user=None):
        """True when *user* (default: current) may list and run this skill."""
        self.ensure_one()
        if not self.required_group_ids:
            return True
        user = user or self.env.user
        return bool(set(self.required_group_ids.ids) & set(user[USER_ALL_GROUPS_FIELD].ids))

    @api.model
    def list_for_agent(self, agent_code):
        """Lightweight serialization of active skills for an agent (autocomplete + /skills)."""
        skills = self.get_for_agent(agent_code).filtered(
            lambda s: s.active and s.show_in_slash and s.user_may_run(),
        )
        twin_stems = unprefixed_twin_stems(
            [
                s.command or s.code
                for s in skills
                if s.source_module and not s.owner_id and not s.is_system
            ],
            get_skill_command_prefix(self.env),
        )
        uid = self.env.uid
        rows = []
        for s in skills:
            token = slash_slug(s.invoke_code(), default='')
            if twin_stems and token in twin_stems:
                continue
            mine = bool(s.owner_id and s.owner_id.id == uid)
            factory = bool(s.source_module or s.is_system)
            rows.append({
                'code': s.invoke_code(),
                'name': s.name,
                'description': s.description or s.name,
                'arg_hint': s._arg_hint_text(),
                'args_policy': s.args_policy or 'default',
                'mine': mine,
                'is_system': bool(s.is_system),
                'factory': factory,
            })
        rows.sort(key=slash_list_sort_key)
        return rows

    @api.model
    def user_can_author_skills(self):
        return self.env.user.has_group('pns_ai_mcp.group_ai_writer')

    @api.model
    def _require_skill_author(self):
        if not self.user_can_author_skills():
            raise UserError(_(
                'AI Writer permission is required to manage skills from the chat.'
            ))
