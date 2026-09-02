# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
# ai.skill — selectable procedure exposed over MCP (distinct from context/bundle).

import io
import json
import logging
import os
import re
import shlex
import zipfile
from datetime import datetime

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from odoo.addons.pns_base.utils import paths as pns_paths
from ..utils import mcp_ui as pns_ui
from ..utils.import_export_guard import ensure_ai_admin
from ..utils.knowledge_ownership import (
    apply_create_ownership,
    assert_writer_can_write_records,
    filter_visible_records,
)
from ..utils.portable_io import export_record_dict
from ..utils.skill_files import (
    skill_code_body_path,
    snake_catalog_id,
    split_skill_identity,
)
from ..utils.skill_live_code import code_has_frozen_result_rows
from ..utils.skill_code_prefix import (
    get_skill_code_prefix,
    get_skill_command_prefix,
    instance_identity,
    invoke_lookup_tokens,
    is_auto_prefixed_code,
    leftover_twin_action,
    reserved_slash_commands,
    slash_slug,
    stem_for_reapply,
    uniquify_catalog_code,
    unprefixed_twin_stems,
)

_logger = logging.getLogger(__name__)

SKILL_PROMPT_PREFIX = 'skill.'
EXPORT_FORMAT_VERSION = 1

# Operator slash-menu hides: durable across factory re-seed / i_restore.
# The Boolean on ai.skill is the UI mirror; this ICP is the source of truth.
ICP_SKILLS_SLASH_HIDDEN = 'pns_ai_mcp.skills_slash_hidden'


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
             'array, integer, number.',
    )
    arg_hint = fields.Char(
        string='Argument hint',
        help='Short example of the arguments this skill expects, shown as the '
             'input placeholder when the user picks/types the skill in Chatboo '
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
    painter = fields.Selection(
        selection=[
            ('painter-local', 'painter-local'),
            ('painter-free', 'painter-free'),
        ],
        string='Painter',
        default=False,
        help='Optional painter override when the skill is invoked via /slash. '
             'Empty = inherit the provider painter. '
             'painter-local: Chatboo composes HTML tables/charts. '
             'painter-free: the model owns the entire bubble. '
             'One-shot for that invocation; does not write the provider.',
    )
    triggers = fields.Char(
        string='NL triggers (deprecated)',
        help='DEPRECATED: natural-language routing was removed in explicit mode. '
             'Skills are invoked only via /slash. Kept for backward '
             'compatibility of existing data; it is no longer used for routing.',
    )
    active = fields.Boolean(default=True)
    show_in_slash = fields.Boolean(
        string='Show in slash menu',
        default=True,
        help='When unchecked, the skill stays installed but is hidden from the '
             'Chatboo "/" autocomplete and /skills list. Exact /command still '
             'works. Stored in ir.config_parameter so factory re-seed / restore '
             'does not put it back in the slash menu.',
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
            ('native', 'native'),
            ('imported', 'imported'),
            ('pinned', 'pinned'),
            ('extra', 'extra'),
        ],
        string='Origin',
        compute='_compute_composition_origin',
        search='_search_composition_origin',
        help='Why this row is on the current agent. native: this agent file. '
             'imported: other module in the XML seed. pinned: other module '
             'pinched onto this agent. extra: not in the recipe (user / slash). '
             'Empty source_module is extra.',
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

    @api.model
    def fields_get(self, allfields=None, attributes=None):
        """Origin tokens stay English (same contract as context_type)."""
        res = super().fields_get(allfields=allfields, attributes=attributes)
        origin = res.get('composition_origin')
        if origin and origin.get('selection'):
            from .ai_agent import COMPOSITION_ORIGIN_SELECTION
            origin['selection'] = list(COMPOSITION_ORIGIN_SELECTION)
        return res

    @staticmethod
    def _painter_from_meta(meta):
        from ..utils.formatting_mode_policy import normalize_painter
        raw = (
            (meta.get('painter') or meta.get('formatting_mode') or '')
            .strip().lower()
        )
        return normalize_painter(raw) or False

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
        """Hace cumplir el contrato del `code_body` al guardar (no solo en runtime).

        Objetivo: que las buenas prácticas se apliquen de forma IMPLÍCITA, venga
        el skill de captura, import o edición manual. Tres capas:

        1. AST (bloqueante): mismas reglas del sandbox que en ejecución (imports
           prohibidos, funciones peligrosas, asignación de `result`). Fuente única
           reutilizada: ``validate_relaxaicode_source_ast``.
        2. Contrato publicado (bloqueante): ``requires`` / front-matter / dunders
           no listados en ``skill_engine_contract`` → error. El motor no se
           parchea por un skill concreto.
        3. Smoke-run best-effort (solo con el registry listo, nunca en install):
           ejecuta el code_body con argumentos vacíos y, SOLO si corre limpio y
           devuelve algo que no es un dict, bloquea con el motivo exacto. Si lanza
           excepción (p. ej. depende de parámetros), NO bloquea: el AST ya cubrió
           lo importante y evitamos falsos positivos.
        """
        from ..controllers.validators import validate_relaxaicode_source_ast
        from ..utils.skill_engine_contract import skill_contract_violations
        from ..utils.skill_runtime import bootstrap_skill_code_body
        for skill in self:
            meta, _body = self._skill_parse_md(skill.content or '')
            code = (skill.code_body or '').strip()
            unknown = skill_contract_violations(meta=meta, code_body=code)
            if unknown:
                self._raise_unpublished_capability(
                    skill.code or skill.name, unknown,
                )
            if not code:
                continue  # skill solo-prompt: lo ejecuta el LLM, no hay contrato
            ok, err, _requires_write = validate_relaxaicode_source_ast(code)
            if not ok:
                raise ValidationError(_(
                    "El code_body del skill «%s» no cumple las reglas del "
                    "sandbox:\n\n%s"
                ) % (skill.code or skill.name or '?', err))
            if code_has_frozen_result_rows(code):
                raise ValidationError(_(
                    "The code_body of skill «%s» looks like a frozen snapshot "
                    "(data/rows assigned to a list of pasted dicts). "
                    "Query Odoo or an API on each run; do not embed result rows."
                ) % (skill.code or skill.name or '?'))
            # Smoke-run: solo fuera de install/upgrade (registry listo).
            if not self.env.registry.ready:
                continue
            diag = {}
            try:
                boot = bootstrap_skill_code_body(
                    self.env, code, arguments='',
                    skill_code=skill.code or 'skill', diag=diag,
                )
            except Exception:
                # Ejecución con args vacíos falló: puede depender de parámetros.
                # No bloqueamos (evita falsos positivos); el AST ya validó.
                continue
            if diag.get('result_not_dict'):
                raise ValidationError(_(
                    "El code_body del skill «%s» asignó a `result` un %s. "
                    "El contrato exige un dict: {'data': [...]} (tabla), "
                    "{'formatted_text': '<html>'} (tarjeta) o "
                    "{'propose_steps': [...]} (HTTP). Envuelve tu lista, p. ej. "
                    "result = {'data': filas, '__return_direct__': True}."
                ) % (skill.code or skill.name or '?', diag.get('result_type', '?')))
            if isinstance(boot, dict):
                unknown = skill_contract_violations(result=boot)
                if unknown:
                    self._raise_unpublished_capability(
                        skill.code or skill.name, unknown,
                    )

    @api.model
    def _slash_hidden_codes(self):
        """Catalog codes hidden from the slash menu (ICP source of truth)."""
        ICP = self.env['ir.config_parameter'].sudo()
        raw = ICP.get_param(ICP_SKILLS_SLASH_HIDDEN, '[]') or '[]'
        try:
            data = json.loads(raw)
        except (TypeError, ValueError):
            data = []
        if not isinstance(data, list):
            return set()
        return {str(x).strip() for x in data if str(x).strip()}

    @api.model
    def _set_slash_hidden_codes(self, codes):
        ICP = self.env['ir.config_parameter'].sudo()
        ICP.set_param(
            ICP_SKILLS_SLASH_HIDDEN,
            json.dumps(sorted(set(codes)), ensure_ascii=False),
        )

    def _sync_slash_hidden_icp(self):
        """Mirror show_in_slash → ICP for the current records' codes."""
        hidden = self._slash_hidden_codes()
        for rec in self:
            code = (rec.code or '').strip()
            if not code:
                continue
            if rec.show_in_slash:
                hidden.discard(code)
            else:
                hidden.add(code)
        self._set_slash_hidden_codes(hidden)

    def _apply_slash_hidden_from_icp(self):
        """Force show_in_slash=False when the skill code is listed in ICP."""
        hidden = self._slash_hidden_codes()
        if not hidden:
            return
        to_hide = self.filtered(
            lambda s: (
                ((s.code or '').strip() in hidden
                 or (s.command or '').strip() in hidden)
                and s.show_in_slash
            ),
        )
        if to_hide:
            to_hide.with_context(skip_slash_icp_sync=True).write({
                'show_in_slash': False,
            })

    @api.model
    def sync_slash_hidden_from_field(self):
        """One-shot: seed ICP from existing show_in_slash=False rows."""
        Skill = self.sudo().with_context(active_test=False)
        codes = Skill.search([('show_in_slash', '=', False)]).mapped('code')
        codes = [c.strip() for c in codes if c and c.strip()]
        if not codes:
            return 0
        hidden = self._slash_hidden_codes()
        before = len(hidden)
        hidden.update(codes)
        self._set_slash_hidden_codes(hidden)
        return len(hidden) - before

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
        return records

    def write(self, vals):
        if not self.env.context.get('skip_hardcoded_restrictions'):
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
        return res

    def unlink(self):
        if not self.env.context.get('skip_hardcoded_restrictions'):
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
    def mcp_prompt_name(self):
        """Name used to expose this skill over MCP prompts/*."""
        self.ensure_one()
        return '%s%s' % (SKILL_PROMPT_PREFIX, self.invoke_code())

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

    @api.model
    def get_by_prompt_name(self, prompt_name, user=None):
        """Resolve a skill from its MCP prompt name ("skill.<code>")."""
        if not prompt_name or not prompt_name.startswith(SKILL_PROMPT_PREFIX):
            return self.browse()
        code = prompt_name[len(SKILL_PROMPT_PREFIX):]
        skill = self.search([
            '|', ('command', '=', code), ('code', '=', code),
        ], limit=1)
        if not skill:
            return skill
        user = user or self.env.user
        return self.filter_visible_for_user(skill, user=user)

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
    # Slash invocation (chatboo inference client)
    # ------------------------------------------------------------------
    @api.model
    def list_for_agent(self, agent_code):
        """Lightweight serialization of active skills for an agent (autocomplete + /skills)."""
        skills = self.get_for_agent(agent_code).filtered(
            lambda s: s.active and s.show_in_slash,
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
            rows.append({
                'code': s.invoke_code(),
                'name': s.name,
                'description': s.description or s.name,
                'arg_hint': s._arg_hint_text(),
                'args_policy': s.args_policy or 'default',
                'mine': bool(s.owner_id and s.owner_id.id == uid),
                'is_system': bool(s.is_system),
            })
        return rows

    @api.model
    def user_can_author_skills(self):
        return self.env.user.has_group('pns_ai_mcp.group_ai_writer')

    @api.model
    def _require_skill_author(self):
        if not self.user_can_author_skills():
            raise UserError(_(
                'AI Writer permission is required to manage skills from Chatboo.'
            ))

    @api.model
    def _find_by_invoke_token(self, token):
        tokens = invoke_lookup_tokens(
            token,
            get_skill_code_prefix(self.env),
            get_skill_command_prefix(self.env),
        )
        if not tokens:
            return self.browse()
        conds = []
        for tok in tokens:
            conds.append(('command', '=', tok))
            conds.append(('code', '=', tok))
        domain = conds if len(conds) == 1 else (['|'] * (len(conds) - 1) + conds)
        return self.search(domain, limit=1)

    @api.model
    def _owned_mutable_skill(self, token):
        """Resolve a skill the current Writer may delete or rename."""
        self._require_skill_author()
        skill = self._find_by_invoke_token(token)
        if not skill:
            raise UserError(_('There is no skill named "%s".') % token)
        if skill.is_system:
            raise UserError(_(
                'System skills cannot be changed from Chatboo.'
            ))
        if not skill.owner_id or skill.owner_id.id != self.env.uid:
            raise UserError(_('You can only change skills you created.'))
        return skill

    @api.model
    def allocate_instance_identity(self, raw, exclude_id=None):
        """Catalog ``code`` (snake) + ``command`` (kebab) for a user skill."""
        code_prefix = get_skill_code_prefix(self.env)
        command_prefix = get_skill_command_prefix(self.env)
        slug = slash_slug(raw, default='')
        if not slug:
            raise UserError(_(
                'Enter a valid skill name (letters, numbers, hyphens).'
            ))
        code, command = instance_identity(slug, code_prefix, command_prefix)
        if command in reserved_slash_commands():
            raise UserError(_(
                'The slash "/%s" is reserved. Choose another name.'
            ) % command)
        taken_domain = [('code', '=like', code + '%')]
        if exclude_id:
            taken_domain = [('id', '!=', exclude_id)] + taken_domain
        taken = set(self.search(taken_domain).mapped('code'))
        code = uniquify_catalog_code(code, taken)
        clash = self.search([
            ('id', '!=', exclude_id or 0),
            '|', '|',
            ('command', '=', command),
            ('code', '=', command),
            ('command', '=', command.replace('-', '_')),
        ], limit=1)
        if clash:
            raise UserError(_(
                'The slash "/%s" is already used by skill "%s". '
                'Choose another name.'
            ) % (command, clash.invoke_code() or clash.code))
        return code, command

    @api.model
    def reapply_source_module_prefixes(
        self, source_module, old_code_prefixes=(), old_command_prefixes=(),
    ):
        """Rewrite pack skills to the current instance prefixes.

        ``source_module`` selects the rows. ``old_*_prefixes`` are stripped
        before the current ICP prefixes are applied. Does not touch
        user-owned skills. Does not steal a slash from another pack or a
        builtin. Returns ``{updated, skipped, errors}``.
        """
        source_module = (source_module or '').strip()
        stats = {'updated': 0, 'skipped': 0, 'errors': []}
        if not source_module:
            return stats
        code_pfx = get_skill_code_prefix(self.env)
        cmd_pfx = get_skill_command_prefix(self.env)
        code_olds = list(old_code_prefixes or ())
        cmd_olds = list(old_command_prefixes or ())
        if code_pfx:
            code_olds.append(code_pfx)
        if cmd_pfx:
            cmd_olds.append(cmd_pfx)
        reserved = set(reserved_slash_commands())
        rows = self.sudo().search([
            ('source_module', '=', source_module),
            ('owner_id', '=', False),
        ])
        pack_ids = set(rows.ids)
        taken_codes = set(self.search([]).mapped('code'))
        for skill in rows:
            stem = stem_for_reapply(
                skill.code, skill.command, code_olds, cmd_olds,
            )
            if not stem:
                stats['skipped'] += 1
                continue
            new_code, new_command = instance_identity(
                stem, code_pfx, cmd_pfx,
            )
            if (
                new_code == (skill.code or '')
                and (new_command or '') == (skill.command or '')
            ):
                stats['skipped'] += 1
                continue
            if new_command in reserved:
                stats['errors'].append(
                    '/%s is reserved (%s)' % (new_command, skill.code)
                )
                continue
            clash = self.search([
                ('id', 'not in', list(pack_ids) or [0]),
                '|', '|',
                ('command', '=', new_command),
                ('code', '=', new_command),
                ('command', '=', new_command.replace('-', '_')),
            ], limit=1)
            if clash:
                stats['errors'].append(
                    '/%s is used by %s' % (
                        new_command, clash.invoke_code() or clash.code,
                    )
                )
                continue
            others = (taken_codes - {skill.code}) | {
                r.code for r in rows if r.id != skill.id
            }
            new_code = uniquify_catalog_code(new_code, others)
            try:
                skill.with_context(skip_hardcoded_restrictions=True).write({
                    'code': new_code,
                    'command': new_command,
                })
            except Exception as exc:
                stats['errors'].append('%s: %s' % (skill.code, exc))
                continue
            taken_codes.discard(skill.code)
            taken_codes.add(new_code)
            stats['updated'] += 1
        stats['hidden_twins'] = self.hide_unprefixed_slash_twins()
        return stats

    @api.model
    def _factory_skill_rel_paths_on_disk(self):
        """``skills/<scope>/<file>.md`` paths that still exist in addons."""
        found = set()
        for _mod, base in self._get_skill_source_paths():
            for scope in ('system', 'custom'):
                scope_dir = os.path.join(base, scope)
                if not os.path.isdir(scope_dir):
                    continue
                for filename in os.listdir(scope_dir):
                    if filename.endswith('.md'):
                        found.add('skills/%s/%s' % (scope, filename))
        return found

    @api.model
    def hide_unprefixed_slash_twins(self):
        """Delete leftover slashes that duplicate a prefixed factory command.

        Instance prefix + factory ``/<prefix><stem>`` → unlink ``/<stem>``
        (user, orphan, factory or system). No archive. Product slashes that
        are not a stem of a prefixed factory row stay.
        """
        pfx = get_skill_command_prefix(self.env)
        if not pfx:
            return 0
        Skill = self.sudo().with_context(
            active_test=False,
            skip_hardcoded_restrictions=True,
        )
        factory = Skill.search([
            ('source_module', '!=', False),
            ('owner_id', '=', False),
        ])
        factory_cmds = [s.command or s.code for s in factory]
        if not unprefixed_twin_stems(factory_cmds, pfx):
            return 0
        on_disk = self._factory_skill_rel_paths_on_disk()
        to_unlink = Skill.browse()
        for rec in Skill.search([]):
            is_factory = bool(
                not rec.owner_id and (rec.source_module or rec.is_system)
            )
            action = leftover_twin_action(
                rec.invoke_code(), factory_cmds, pfx,
                rec.rel_path or '', on_disk, is_factory,
            )
            if action == 'unlink':
                to_unlink |= rec
        if not to_unlink:
            return 0
        _logger.info(
            'MCP: unlink unused unprefixed slash twins %s',
            to_unlink.mapped('code'),
        )
        n = len(to_unlink)
        to_unlink.unlink()
        return n

    @api.model
    def action_delete_owned(self, token):
        skill = self._owned_mutable_skill(token)
        name = skill.invoke_code() or skill.code
        skill.unlink()
        return {'deleted': name}

    @api.model
    def action_rename_owned(self, old_token, new_token):
        skill = self._owned_mutable_skill(old_token)
        code_prefix = get_skill_code_prefix(self.env)
        command_prefix = get_skill_command_prefix(self.env)
        new_slash = slash_slug(new_token, default='')
        if not new_slash:
            raise UserError(_(
                'Enter a valid new skill name (letters, numbers, hyphens).'
            ))
        old_slash = skill.invoke_code() or skill.code
        if is_auto_prefixed_code(
            skill.code, old_slash, code_prefix, command_prefix,
        ):
            code, command = self.allocate_instance_identity(
                new_slash, exclude_id=skill.id,
            )
        else:
            command = new_slash
            code = skill.code
            clash = self.search([
                ('id', '!=', skill.id),
                '|', '|',
                ('command', '=', command),
                ('code', '=', command),
                ('command', '=', command.replace('-', '_')),
            ], limit=1)
            if clash:
                raise UserError(_(
                    'The slash "/%s" is already used by skill "%s". '
                    'Choose another name.'
                ) % (command, clash.invoke_code() or clash.code))
        skill.write({
            'code': code,
            'command': command,
        })
        return {
            'old': old_token,
            'new': skill.invoke_code() or skill.code,
        }

    def _arg_hint_text(self):
        """Placeholder de argumentos para el input del `/skill`.

        Prioriza el ``arg_hint`` autorado (ejemplo real de uso). Si falta,
        deriva una pista discreta con las claves declaradas en ``param_schema``
        (solo nombres, p. ej. ``clave1=… clave2=…``). Nunca inventa valores.
        """
        self.ensure_one()
        hint = (self.arg_hint or '').strip()
        if hint:
            return hint
        schema_txt = (self.param_schema or '').strip()
        if schema_txt:
            try:
                schema = json.loads(schema_txt)
            except Exception:
                schema = None
            if isinstance(schema, dict) and schema:
                return ' '.join('%s=…' % k for k in schema.keys())
        return ''

    @staticmethod
    def _substitute_arguments(text, arguments):
        """Replace $ARGUMENTS / $0 / $1... placeholders (Claude-style)."""
        arguments = arguments or ''
        try:
            parts = shlex.split(arguments)
        except ValueError:
            parts = arguments.split()

        def _positional(match):
            idx = int(match.group(1))
            return parts[idx] if idx < len(parts) else ''

        result = re.sub(r'\$(\d+)', _positional, text)
        result = result.replace('$ARGUMENTS', arguments)
        return result

    def build_invocation_payload(self, user_locale=None, arguments=''):
        """Prompt text to inject when the skill is invoked via /<code> [args].

        Substitutes $ARGUMENTS/$N when present; otherwise appends them (like
        Claude Code) so the model always sees what the user typed.
        """
        self.ensure_one()
        text = self.build_prompt_payload(user_locale=user_locale)['text']
        arguments = (arguments or '').strip()
        if '$ARGUMENTS' in text or re.search(r'\$\d', text):
            text = self._substitute_arguments(text, arguments)
        elif arguments:
            text += '\n\nARGUMENTS: %s' % arguments
        return text

    # ------------------------------------------------------------------
    # Export / import (ZIP) — Phase 3
    # ------------------------------------------------------------------
    def _skills_zip_filename(self, scope_label):
        return pns_ui.build_export_filename(
            self.env, 'ai_skills_%s' % (scope_label or 'all'), 'zip')

    def _build_skills_zip_bytes(self, records, scope_label):
        """Build skills export ZIP payload (no UI). Returns None if empty."""
        records = records.exists()
        if not records:
            return None
        skills_meta = []
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            for skill in records:
                content_file = 'skills/%s.md' % skill.code
                zip_file.writestr(content_file, (skill.content or '').encode('utf-8'))
                code_file = None
                if skill.code_body:
                    code_file = 'code/%s.py' % skill.code
                    zip_file.writestr(code_file, skill.code_body.encode('utf-8'))
                try:
                    meta = export_record_dict(skill, skip_fields={
                        'id', 'content', 'code_body', 'show_in_slash',
                    })
                except Exception:
                    meta = {'code': skill.code, 'name': skill.name or '?'}
                meta['content_file'] = content_file
                meta['code_file'] = code_file
                try:
                    meta['agent_codes'] = skill.agent_ids.mapped('code')
                except Exception:
                    pass
                try:
                    meta['context_codes'] = skill.context_ids.mapped('code')
                except Exception:
                    pass
                skills_meta.append(meta)
            manifest = {
                'type': 'ai.skill.export',
                'format_version': EXPORT_FORMAT_VERSION,
                'scope': scope_label,
                'exported_at': datetime.now().isoformat(),
                'skills': skills_meta,
            }
            zip_file.writestr(
                'manifest.json',
                json.dumps(manifest, indent=2, ensure_ascii=False),
            )
        zip_buffer.seek(0)
        return zip_buffer.getvalue()

    def _export_skills_to_zip(self, records, scope_label, title='Export skills'):
        records = records.exists()
        if not records:
            return pns_ui.open_json_export_empty_wizard(
                self.env,
                dialog_title=title,
                message=_('No skills to export.'),
            )
        payload = self._build_skills_zip_bytes(records, scope_label)
        attachment = pns_ui.write_export_attachment(
            self.env, self._skills_zip_filename(scope_label),
            payload, 'application/zip',
        )
        return pns_ui.open_json_export_wizard(
            self.env,
            dialog_title=title,
            summary_text=_('%s skill(s) exported to ZIP.') % len(records),
            count=len(records),
            attachment=attachment,
        )

    @api.model
    def export_all_to_zip(self):
        """Export all skills to ZIP with manifest."""
        ensure_ai_admin(self.env)
        return self._export_skills_to_zip(
            self.search([]), 'all', title=_('Export all skills'),
        )

    def action_export_selected(self):
        """Export selected list rows to ZIP."""
        ensure_ai_admin(self.env)
        active_ids = self.env.context.get('active_ids') or self.ids
        records = self.browse(active_ids).exists()
        if not records:
            raise UserError(_('Select at least one skill to export.'))
        return records._export_skills_to_zip(
            records, 'sel-%d' % len(records), title=_('Export selected skills'),
        )

    @api.model
    def action_open_import_wizard(self):
        ensure_ai_admin(self.env)
        return {
            'type': 'ir.actions.act_window',
            'name': _('Import skills from ZIP'),
            'res_model': 'pns_ai_mcp.skill.import.wizard',
            'view_mode': 'form',
            'target': 'new',
        }

    @api.model
    def export_agent_skills_to_zip(self, agent):
        """Export the skills exposed by an AI agent (its ``skill_ids``)."""
        ensure_ai_admin(self.env)
        agent.ensure_one()
        return self._export_skills_to_zip(
            agent.skill_ids, 'agent-%s' % agent.code,
            title=_('Export agent skills'),
        )

    @api.model
    def import_agent_skills_zip(self, agent, zip_bytes, replace_existing=False):
        """Import a skills export ZIP into the target agent (linked to it)."""
        ensure_ai_admin(self.env)
        agent.ensure_one()
        return self.import_skills_zip(
            zip_bytes, replace_existing=replace_existing, force_agent=agent,
        )

    @api.model
    def action_export_skills(self):
        """Cog-menu entry point: export all skills to ZIP."""
        ensure_ai_admin(self.env)
        return self.export_all_to_zip()

    @api.model
    def action_import_skills(self):
        """Cog-menu entry point: open the import wizard."""
        ensure_ai_admin(self.env)
        return self.action_open_import_wizard()

    @api.model
    def import_skills_zip(self, zip_bytes, replace_existing=False, force_agent=None):
        """Recreate skills from a ZIP export. Contexts are linked only if they exist.

        force_agent: when set, every imported/updated skill is also linked to
        that agent (added to its ``agent_ids`` and to the agent's ``skill_ids``).
        Used by the per-agent import scope.
        """
        ensure_ai_admin(self.env)
        Agent = self.env['ai.agent']
        Context = self.env['ai.context']
        stats = {
            'created': 0, 'updated': 0, 'skipped': 0,
            'missing_contexts': [], 'missing_agents': [], 'errors': [],
        }
        try:
            with zipfile.ZipFile(io.BytesIO(zip_bytes), 'r') as zf:
                manifest = json.loads(zf.read('manifest.json').decode('utf-8'))
                for entry in manifest.get('skills', []):
                    raw_code = (entry.get('code') or '').strip()
                    if not raw_code:
                        stats['errors'].append(_('Skill without code skipped.'))
                        continue
                    code = snake_catalog_id(raw_code)
                    command = (entry.get('command') or '').strip()
                    if not command and raw_code != code:
                        command = raw_code
                    content = entry.get('content', '') or ''
                    content_file = entry.get('content_file')
                    if content_file:
                        try:
                            content = zf.read(content_file).decode('utf-8')
                        except KeyError:
                            pass
                    code_body = entry.get('code_body', '') or ''
                    code_file = entry.get('code_file')
                    if code_file:
                        try:
                            code_body = zf.read(code_file).decode('utf-8')
                        except KeyError:
                            pass
                    agent_codes = entry.get('agent_codes')
                    if agent_codes is None:
                        single = entry.get('agent_code')
                        agent_codes = [single] if single else []
                    agents = Agent.browse()
                    for ac in agent_codes:
                        found_agent = Agent.search([('code', '=', ac)], limit=1)
                        if found_agent:
                            agents |= found_agent
                        elif ac not in stats['missing_agents']:
                            stats['missing_agents'].append(ac)
                    if force_agent:
                        agents |= force_agent
                    ctx_codes = entry.get('context_codes') or []
                    contexts = (
                        Context.search([('code', 'in', ctx_codes)])
                        if ctx_codes else Context.browse()
                    )
                    found = set(contexts.mapped('code'))
                    for missing in ctx_codes:
                        if missing not in found and missing not in stats['missing_contexts']:
                            stats['missing_contexts'].append(missing)
                    values = {
                        'code': code,
                        'name': entry.get('name') or code,
                        'description': entry.get('description') or code,
                        'content': content,
                        'code_body': code_body or False,
                        'agent_ids': [(6, 0, agents.ids)],
                        'version': entry.get('version') or False,
                        'sequence': entry.get('sequence', 10),
                        'active': entry.get('active', True),
                        'context_ids': [(6, 0, contexts.ids)],
                        'command': command if command and command != code else False,
                    }
                    existing = self.search([
                        '|', '|',
                        ('code', '=', code),
                        ('code', '=', command or code),
                        ('command', '=', command or code),
                    ], limit=1)
                    if existing:
                        if replace_existing:
                            # Slash visibility lives in ICP, not in the ZIP.
                            existing.write(values)
                            existing._apply_slash_hidden_from_icp()
                            stats['updated'] += 1
                        else:
                            stats['skipped'] += 1
                    else:
                        values['code'] = code
                        self.create(values)
                        stats['created'] += 1
        except KeyError:
            raise UserError(_('Invalid ZIP: manifest.json not found.'))
        except (zipfile.BadZipFile, ValueError) as exc:
            raise UserError(_('Could not read skills ZIP: %s') % exc)
        return stats

    # ------------------------------------------------------------------
    # File sync (parallel to mcp_context): ai/skills/system & ai/skills/custom
    # ------------------------------------------------------------------
    @api.model
    def _get_module_path(self):
        """Absolute path of the pns_ai_mcp module (dev or installed)."""
        try:
            from odoo.modules.module import get_module_path
            path = get_module_path('pns_ai_mcp')
            if path and os.path.exists(path):
                return path
        except Exception:
            pass
        return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    @api.model
    def _skill_parse_md(self, text):
        """Parse skills/<scope>/<code>.md front-matter: returns (meta_dict, body)."""
        meta = {}
        lines = (text or '').split('\n')
        if lines and lines[0].strip() == '---':
            i = 1
            while i < len(lines) and lines[i].strip() != '---':
                if ':' in lines[i]:
                    key, _, val = lines[i].partition(':')
                    meta[key.strip()] = val.strip()
                i += 1
            body = '\n'.join(lines[i + 1:])
            if body.startswith('\n'):
                body = body[1:]
            return meta, body
        return meta, text or ''

    @api.model
    def _get_skill_source_paths(self, module_name=None):
        """Return [(module_name, skills_dir)] for addons that ship ``ai/skills/``.

        Includes ``to upgrade`` / ``to install``: during a module's own ``-u``
        Odoo has already left ``installed``, so a seed that only scanned that
        state saw zero files and neither upserted nor pruned.

        Pass ``module_name`` to resolve that addon from disk even if its
        ``ir.module.module`` row is missing or in another state.
        """
        from odoo.modules.module import get_module_path
        from ..utils.ai_paths import module_kind_dir
        result = []
        want = (module_name or '').strip()
        Module = self.env['ir.module.module'].sudo()
        if want:
            mods = Module.search([('name', '=', want)])
        else:
            mods = Module.search([
                ('state', 'in', ('installed', 'to upgrade', 'to install')),
            ])
        seen = set()
        for mod in mods:
            mod_path = get_module_path(mod.name)
            if not mod_path:
                continue
            skills_dir = module_kind_dir(mod_path, 'skills')
            if skills_dir:
                result.append((mod.name, skills_dir))
                seen.add(mod.name)
        if want and want not in seen:
            mod_path = get_module_path(want)
            skills_dir = module_kind_dir(mod_path, 'skills') if mod_path else None
            if skills_dir:
                result.append((want, skills_dir))
        return result

    @api.model
    def import_from_files(
        self, replace_existing=True, only_codes=None, module_name=None,
        scopes=None,
    ):
        """Sync skills from module files (ai/skills/system & ai/skills/custom)
        into DB.

        Scans installed modules that ship an ``ai/skills/`` dir. Pass
        ``module_name`` to seed one addon (install/-u of that module).
        ``scopes`` defaults to both drawers; the engine factory seed
        passes ``('system',)`` so ``custom/`` is never planted here.

        replace_existing=True (default): overwrite skills whose code already
        exists (upsert). replace_existing=False: additive only — create the
        missing ones and skip matches. In **no** case are DB records deleted
        (unified no-delete rule: import = upsert + recover only).

        only_codes: optional iterable of skill codes to restrict the import to
        (used for the per-agent "restore from module" scope). Other files are
        skipped.
        """
        ensure_ai_admin(self.env)
        # Siembra módulo→BD: vía autorizada (ensure_ai_admin ya validó). Las
        # guardas de write() (is_system read-only, ownership) están pensadas para
        # ediciones de AI Writers en la UI, no para el seeding; las saltamos con
        # el mismo flag que usa el import de contextos. Sin esto, un restore por
        # `odoo-bin shell` (env.user = superusuario, NO group_ai_admin) falla con
        # "System skills are read-only for AI Writers".
        self = self.with_context(skip_hardcoded_restrictions=True)
        Agent = self.env['ai.agent']
        Context = self.env['ai.context']
        only_codes_set = set(only_codes) if only_codes else None
        stats = {
            'created': 0, 'updated': 0, 'skipped': 0, 'errors': [], 'pruned': 0,
            'missing_contexts': [], 'missing_agents': [],
        }
        want_mod = (module_name or '').strip()
        allowed = {
            str(s).strip() for s in (scopes or ('system', 'custom')) if s
        }
        walk = tuple(s for s in ('system', 'custom') if s in allowed)
        for source_mod, base in self._get_skill_source_paths(
            module_name=want_mod or None,
        ):
            for scope in walk:
                scope_dir = os.path.join(base, scope)
                if not os.path.isdir(scope_dir):
                    continue
                is_system = scope == 'system'
                for filename in sorted(os.listdir(scope_dir)):
                    if not filename.endswith('.md'):
                        continue
                    try:
                        with open(os.path.join(scope_dir, filename), 'r',
                                  encoding='utf-8') as fobj:
                            meta, body = self._skill_parse_md(fobj.read())
                        code, command = split_skill_identity(filename, meta)
                        invoke = command or code
                        if not code:
                            continue
                        if only_codes_set is not None and code not in only_codes_set:
                            if invoke not in only_codes_set:
                                continue
                        command_val = command or False
                        code_body = ''
                        py_path = skill_code_body_path(
                            scope_dir, filename, code, command or None,
                        )
                        if py_path and os.path.isfile(py_path):
                            with open(py_path, 'r', encoding='utf-8') as fobj:
                                code_body = fobj.read()
                        from ..utils.skill_engine_contract import (
                            skill_contract_violations,
                        )
                        unknown = skill_contract_violations(
                            meta=meta, code_body=code_body,
                        )
                        if unknown:
                            self._raise_unpublished_capability(code, unknown)
                        exclusive = self.env[
                            'ai.context'
                        ]._explicit_agent_codes_from_metadata(meta)
                        agent_codes = list(exclusive) if exclusive else []
                        agents = Agent.browse()
                        for ac in agent_codes:
                            found_agent = Agent.search([('code', '=', ac)], limit=1)
                            if found_agent:
                                agents |= found_agent
                            elif ac not in stats['missing_agents']:
                                stats['missing_agents'].append(ac)
                        # Pull: same as contexts — explicit codes, or @module
                        # for the whole drawer unless the skill is exclusive.
                        for agent in Agent.search([]):
                            if agent.wants_skill_code(
                                code,
                                source_module=source_mod,
                                pack_exclusive=exclusive is not None,
                            ):
                                agents |= agent
                        ctx_codes = [
                            c.strip() for c in (meta.get('context_codes') or '').split(',')
                            if c.strip()
                        ]
                        contexts = (
                            Context.search([('code', 'in', ctx_codes)])
                            if ctx_codes else Context.browse()
                        )
                        found = set(contexts.mapped('code'))
                        for missing in ctx_codes:
                            if missing not in found and missing not in stats['missing_contexts']:
                                stats['missing_contexts'].append(missing)
                        try:
                            sequence = int(meta.get('sequence') or 10)
                        except (TypeError, ValueError):
                            sequence = 10
                        active = str(meta.get('active', 'true')).strip().lower() != 'false'
                        body = (body or '').rstrip('\n')
                        vals = {
                            'name': meta.get('name') or code,
                            'description': meta.get('description') or code,
                            'content': body or (meta.get('description') or code),
                            'code_body': code_body or False,
                            'agent_ids': [(6, 0, agents.ids)],
                            'version': meta.get('version') or False,
                            'param_schema': (meta.get('param_schema') or '').strip() or False,
                            'arg_hint': (meta.get('arg_hint') or '').strip() or False,
                            'args_policy': self._args_policy_from_meta(meta),
                            'painter': self._painter_from_meta(meta),
                            'triggers': (meta.get('triggers') or '').strip() or False,
                            'sequence': sequence,
                            'active': active,
                            'is_system': is_system,
                            'source_module': source_mod,
                            'rel_path': 'skills/%s/%s' % (scope, filename),
                            'context_ids': [(6, 0, contexts.ids)],
                            'command': command_val,
                            'code': code,
                        }
                        rel_path = vals['rel_path']
                        existing = self.search([
                            ('source_module', '=', source_mod),
                            ('rel_path', '=', rel_path),
                        ], limit=1)
                        if not existing:
                            existing = self.search([
                                '|', '|',
                                ('code', '=', code),
                                ('code', '=', invoke),
                                ('command', '=', invoke),
                            ], limit=1)
                        if existing:
                            if not replace_existing:
                                stats['skipped'] += 1
                                continue
                            # User-owned skills are never overwritten by module files.
                            if existing.owner_id:
                                stats['skipped'] += 1
                                _logger.info(
                                    'MCP: skip factory overwrite of user-owned '
                                    'skill %s (owner=%s)',
                                    existing.code, existing.owner_id.login,
                                )
                                continue
                            if (
                                existing.source_module
                                and existing.source_module != source_mod
                            ):
                                stats['skipped'] += 1
                                _logger.warning(
                                    'MCP: skip skill %s (owner=%s, attempted=%s)',
                                    code, existing.source_module, source_mod,
                                )
                                continue
                            # Keep operator slash visibility across factory re-seed
                            # (Boolean + ICP). Never write show_in_slash from files.
                            write_vals = {
                                k: v for k, v in vals.items()
                                if k != 'show_in_slash'
                            }
                            existing.write(write_vals)
                            existing._apply_slash_hidden_from_icp()
                            stats['updated'] += 1
                        else:
                            vals['code'] = code
                            self.create(vals)
                            stats['created'] += 1
                    except Exception as exc:
                        stats['errors'].append('%s: %s' % (filename, exc))
        # Re-apply ICP hides in case create defaulted True after a full re-seed.
        try:
            hidden = self._slash_hidden_codes()
            if hidden:
                self.search([
                    '|',
                    ('code', 'in', list(hidden)),
                    ('command', 'in', list(hidden)),
                ])._apply_slash_hidden_from_icp()
        except Exception:
            _logger.debug(
                'MCP: could not re-apply slash-hidden ICP after skill import',
                exc_info=True,
            )
        # No pruning: import = upsert + recover only. System skills whose .md
        # was removed/renamed are kept (never deleted); remove leftovers by
        # hand if ever needed.
        _logger.info('MCP: skills import_from_files: %s', stats)
        self._after_factory_skill_import(stats)
        return stats

    @api.model
    def _skill_disk_index_for_module(self, module_name):
        """rel_path / code / command shipped by one addon's ``ai/skills/``."""
        from ..utils.skill_files import split_skill_identity
        rels, codes, commands = set(), set(), set()
        want = (module_name or '').strip()
        if not want:
            return rels, codes, commands
        for source_mod, base in self._get_skill_source_paths(module_name=want):
            if source_mod != want:
                continue
            for scope in ('system', 'custom'):
                scope_dir = os.path.join(base, scope)
                if not os.path.isdir(scope_dir):
                    continue
                for filename in os.listdir(scope_dir):
                    if not filename.endswith('.md'):
                        continue
                    rels.add('skills/%s/%s' % (scope, filename))
                    try:
                        with open(
                            os.path.join(scope_dir, filename),
                            encoding='utf-8',
                        ) as handle:
                            meta, _body = self._skill_parse_md(handle.read())
                    except OSError:
                        continue
                    code, command = split_skill_identity(filename, meta)
                    if code:
                        codes.add(code)
                    if command:
                        commands.add(command)
                    elif code:
                        commands.add(code)
        return rels, codes, commands

    @api.model
    def _skill_rel_paths_for_module(self, module_name):
        """``skills/<scope>/<file>.md`` paths shipped by one addon."""
        rels, _codes, _commands = self._skill_disk_index_for_module(module_name)
        return rels

    @api.model
    def unlink_retired_from_module(self, module_name):
        """Unlink factory rows of this addon whose ``.md`` is gone from disk.

        User-owned rows stay. Does nothing if the addon has no skill files
        (avoids wiping the catalog when the overlay is missing). A claimed
        leftover with a stale ``rel_path`` is kept if its code or slash
        still names a file on disk (import failed this pass ≠ retired).
        """
        from ..utils.skill_files import factory_row_on_disk
        name = (module_name or '').strip()
        if not name:
            return 0
        on_disk, disk_codes, disk_commands = self._skill_disk_index_for_module(
            name,
        )
        if not on_disk:
            _logger.warning(
                'MCP: skip retired unlink for %s (no skill files on disk)',
                name,
            )
            return 0
        Skill = self.sudo().with_context(
            active_test=False,
            skip_hardcoded_restrictions=True,
        )
        rows = Skill.search([
            ('source_module', '=', name),
            ('owner_id', '=', False),
        ])
        gone = Skill.browse()
        for rec in rows:
            if factory_row_on_disk(
                rec.rel_path, rec.code, rec.command,
                on_disk, disk_codes, disk_commands,
            ):
                continue
            gone |= rec
        if not gone:
            return 0
        codes = gone.mapped('code')
        gone.unlink()
        _logger.info(
            'MCP: unlinked retired factory skills of %s: %s', name, codes,
        )
        return len(codes)

    @api.model
    def unlink_named_factory_skills(self, names):
        """Unlink factory rows by code/command/rel_path. No owner.

        Used by an addon's XML seed so a ``-u`` drops product leftovers
        even when a one-shot migrate already ran.
        """
        names = [n for n in (names or []) if n]
        if not names:
            return 0
        paths = ['skills/system/%s.md' % n for n in names]
        Skill = self.sudo().with_context(
            active_test=False,
            skip_hardcoded_restrictions=True,
        )
        rows = Skill.search([
            '&',
            ('owner_id', '=', False),
            '|', '|',
            ('code', 'in', names),
            ('command', 'in', names),
            ('rel_path', 'in', paths),
        ])
        if not rows:
            return 0
        codes = rows.mapped('code')
        rows.unlink()
        _logger.info('MCP: unlinked named factory skills %s', codes)
        return len(codes)

    @api.model
    def import_from_module(self, module_name, scopes=None):
        """Seed one addon's skills on install/-u. Does not scan neighbors.

        Upserts from that module's ``ai/skills/``, then drops factory leftovers
        whose ``.md`` is gone. ``scopes`` defaults to system+custom (owner
        pack). The engine passes ``('system',)`` so it never plants ``custom/``.
        """
        name = (module_name or '').strip()
        if not name:
            raise UserError(_('Skill import requires a module name.'))
        stats = self.import_from_files(
            replace_existing=True,
            module_name=name,
            scopes=scopes,
        )
        retired = self.unlink_retired_from_module(name)
        if isinstance(stats, dict):
            stats['retired'] = retired
        return stats

    def _after_factory_skill_import(self, stats):
        """Hook after file→DB sync. Tenant packs re-apply instance prefixes.

        ``import_from_files`` writes on-disk identity (filename + ``skill:``).
        A pack that seeds catalog/slash prefixes must rewrite its rows here
        so a ``-u`` of that pack does not leave disk codes as the live slash.
        """
        hidden = self.hide_unprefixed_slash_twins()
        if isinstance(stats, dict):
            stats['hidden_twins'] = hidden
        return stats

    @api.model
    def default_skill_codes_for_agent(self, agent_code, pull_tokens=None):
        """Shipped default skill set for an agent (pull ∪ push).

        Pull: ``ai.agent.default_skill_codes`` (codes and ``@module`` packs).
        ``@module`` includes every factory skill of that ``source_module``
        unless the skill declared exclusive ``agent_codes``. Empty
        ``agent_codes`` is included by ``@``. Push: explicit ``agent_codes``.
        ``pull_tokens`` overrides the live recipe (factory restore = seed).
        """
        codes = set()
        if not agent_code:
            return codes
        Agent = self.env['ai.agent']
        Context = self.env['ai.context']
        agent = Agent.search([('code', '=', agent_code)], limit=1)
        if pull_tokens is not None:
            pull_codes, pull_packs = pull_tokens
        else:
            pull_codes, pull_packs = (
                agent._default_skill_tokens() if agent else (set(), set())
            )
        codes |= pull_codes
        restrict_to_seed = pull_tokens is not None
        own_mods = set()
        if restrict_to_seed and agent:
            own_mods = {
                (agent.module_name or '').strip(),
                (agent.code or '').strip(),
            }
            own_mods.discard('')
        for source_mod, base in self._get_skill_source_paths():
            pack_pull = source_mod in pull_packs
            for scope in ('system', 'custom'):
                scope_dir = os.path.join(base, scope)
                if not os.path.isdir(scope_dir):
                    continue
                for filename in sorted(os.listdir(scope_dir)):
                    if not filename.endswith('.md'):
                        continue
                    try:
                        with open(os.path.join(scope_dir, filename), 'r',
                                  encoding='utf-8') as fobj:
                            meta, _body = self._skill_parse_md(fobj.read())
                    except Exception:
                        continue
                    code, _command = split_skill_identity(filename, meta)
                    if not code:
                        continue
                    exclusive = Context._explicit_agent_codes_from_metadata(
                        meta,
                    )
                    if (
                        restrict_to_seed
                        and source_mod not in pull_packs
                        and source_mod not in own_mods
                        and code not in pull_codes
                    ):
                        continue
                    if code in pull_codes:
                        codes.add(code)
                        continue
                    if pack_pull:
                        if (
                            exclusive is not None
                            and agent_code not in exclusive
                        ):
                            continue
                        codes.add(code)
                        continue
                    if exclusive and agent_code in exclusive:
                        codes.add(code)
        return codes

    @api.model
    def _build_module_reload_report_html(self, stats, title=None):
        errors = stats.get('errors') or []
        created = stats.get('created', 0)
        updated = stats.get('updated', 0)
        title = title or _('Skills — reload from module files')
        status_class, status_icon, status_text, _ntype = pns_ui.derive_operation_status(
            errors,
            created + updated,
            failed_text=_('Skills reload failed.'),
            warnings_text=_('Skills reload completed with warnings.'),
            success_text=_('Skills reload completed.'),
        )
        return pns_ui.build_operation_report_html(
            title,
            status_text,
            status_class,
            status_icon,
            rows=[
                (_('Skills created'), created),
                (_('Skills updated'), updated),
                (_('Skills skipped (not overwritten)'), stats.get('skipped', 0)),
            ],
            errors=errors,
        )

    @api.model
    def reload_from_server(self, replace_existing=True):
        """UI entry-point: resync skills from module files into DB, then notify.

        replace_existing controls whether code matches are overwritten (True) or
        skipped, leaving the DB rows untouched (False)."""
        ensure_ai_admin(self.env)
        stats = self.import_from_files(replace_existing=replace_existing)
        errors = stats.get('errors') or []
        _sc, _si, _st, ntype = pns_ui.derive_operation_status(
            errors,
            stats.get('created', 0) + stats.get('updated', 0),
            failed_text=_('Reload failed.'),
            warnings_text=_('Reload completed with warnings.'),
            success_text=_('Reload completed.'),
        )
        message = pns_ui.build_plain_operation_message(
            _('Reload completed'),
            [
                (_("Created"), stats.get('created', 0)),
                (_("Updated"), stats.get('updated', 0)),
                (_("Skipped (not overwritten)"), stats.get('skipped', 0)),
            ],
            errors=errors,
        )
        return pns_ui.client_notification(
            _("Reload from server"),
            message,
            notification_type=ntype if ntype != 'danger' else 'warning',
        )

    @api.model
    def _build_skills_import_report_html(self, zip_bytes, replace_existing=False):
        stats = self.import_skills_zip(zip_bytes, replace_existing=replace_existing)
        extra_warnings = []
        if stats['missing_contexts']:
            extra_warnings.append(
                '%s %s' % (
                    _('Missing contexts (not linked):'),
                    ', '.join(stats['missing_contexts']),
                )
            )
        if stats['missing_agents']:
            extra_warnings.append(
                '%s %s' % (
                    _('Missing agents (skill set global):'),
                    ', '.join(stats['missing_agents']),
                )
            )
        status_class, status_icon, status_text, _ntype = pns_ui.derive_operation_status(
            stats['errors'],
            stats['created'] + stats['updated'],
            failed_text=_('Import failed.'),
            warnings_text=_('Import completed with warnings.'),
            success_text=_('Import completed successfully.'),
            extra_warnings=extra_warnings,
        )
        footer = (
            '<p class="text-muted" style="font-size:11px;margin-bottom:0;">'
            + _('Existing skills (same code) are updated only if "Replace existing" '
                'is checked. Referenced contexts are linked only if they already '
                'exist; missing ones are reported, not created.')
            + '</p>'
        )
        return pns_ui.build_operation_report_html(
            None,
            status_text,
            status_class,
            status_icon,
            rows=[
                (_('Created'), stats['created']),
                (_('Updated'), stats['updated']),
                (_('Skipped (existing, not replaced)'), stats['skipped']),
            ],
            errors=stats['errors'],
            footer_html=footer,
        )
