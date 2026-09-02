# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""PNS AI MCP - Agent. PATANEGRA Soft (https://patanegra.com).

Part of Patanegra Soft Suite (`pns_suite`), distributed via Patanegra Soft Hub.
Unified agent orchestrator of the Patanegra Application Agent Protocol (PAAP):
resolves role -> bundle -> context and runs the agent turn.
Licensed under the Apache License 2.0 - see LICENSE.
"""
import logging

from odoo import api, fields, models, _
from odoo.exceptions import UserError

from ..utils import mcp_ui
from ..utils import context_roles
from ..utils.import_export_guard import ensure_ai_admin
from ..utils.ai_agent_registry import MCP_BARE_AGENT_CODE_DEFAULT
from ..utils.portable_io import export_record_dict

_logger = logging.getLogger(__name__)

MCP_BARE_AGENT_CODE = MCP_BARE_AGENT_CODE_DEFAULT

COMPOSITION_ORIGIN_TOKENS = ('native', 'imported', 'pinned', 'extra')
COMPOSITION_ORIGIN_SELECTION = [(tok, tok) for tok in COMPOSITION_ORIGIN_TOKENS]
COMPOSITION_ORIGIN_RANK = {
    tok: i for i, tok in enumerate(COMPOSITION_ORIGIN_TOKENS)
}


class AIAgent(models.Model):
    """AI Agent — unified orchestrator of the PNS AI framework.

    An agent is any AI-powered feature in Odoo: a chatbot (Chatboo),
    an OCR pipeline, an MCP protocol endpoint, etc.

    All agents share the same infrastructure (contexts, providers).
    The ``agent_type`` field captures the only meaningful difference:
    whether the LLM runs internally (inference) or externally (endpoint).

    Architecture::

        ai.provider         →  Infrastructure: LLM endpoint + API key
        ai.agent            →  This model. Has:
                                • agent_type (inference / endpoint)
                                • provider chain (provider_ids)
                                • context_ids (direct)
        ai.context          →  Reusable directive (prompt snippet)

    Context ownership: an agent uses its own ``context_ids``. Core contexts
    (context_type=core) are always injected. Shared knowledge is linked to
    every declaring agent at import time (no agent-to-agent inheritance).

    Typical agents:
        code='pns_ai_chatboo'  →  inference (LLM via internal provider)
        code='pns_ai_mcp'      →  endpoint (context+tools served to external LLM)
        code='pns_ocr'         →  inference (document OCR; shipped by the pns_ocr module)
    """
    _name = 'ai.agent'
    _description = 'AI Agent'
    _order = 'sequence, name'

    name = fields.Char(required=True, translate=True)
    code = fields.Char(
        required=True,
        help="Technical identifier = module name: pns_ai_mcp, pns_ai_chatboo, …",
    )
    agent_type = fields.Selection(
        [('inference', 'Inference (internal LLM)'),
         ('endpoint', 'Endpoint (external LLM)')],
        string='Type',
        default='inference',
        required=True,
        help="inference: the agent runs the LLM via an internal provider (chatboo, ocr).\n"
             "endpoint: the agent serves contexts/tools to an external LLM client (MCP).",
    )
    sequence = fields.Integer(default=10)
    description = fields.Text()
    active = fields.Boolean(default=True)
    origin = fields.Selection(
        [('module', 'Module (protected)'),
         ('user', 'User (dynamic)')],
        string='Origin',
        default='user',
        required=True,
        readonly=True,
        help="'module': created by an installed Odoo module (protected from deletion).\n"
             "'user': created manually in the UI (fully editable and deletable).",
    )
    module_name = fields.Char(
        string='Owner module',
        readonly=True,
        help="Technical name of the module that owns this agent "
             "(e.g. pns_ai_chatboo). Empty for user-created agents.",
    )
    provider_ids = fields.One2many(
        'ai.agent.provider',
        'agent_id',
        string='Providers',
    )
    # ── Context ownership ─────────────────────────────────────────────
    max_agent_rounds = fields.Integer(
        string='Max LLM rounds',
        default=10,
        help="Maximum number of ReAct loop iterations (LLM call → tool execution → "
             "LLM call) before forcing a final answer.\n\n"
             "Powerful models (GPT-4o, Claude, Qwen-72B) typically need 3-5 rounds. "
             "Smaller local models may need more rounds but often loop without "
             "progress — setting a lower limit (5-8) can be better.\n\n"
             "0 or -1 = use the system default (10). Only applies to inference agents.",
    )
    default_context_codes = fields.Text(
        string='Default context codes',
        help='Baseline pull list for factory composition (CSV / newlines). '
             'Entries are context codes and/or @module_name pack refs (all '
             'non-core codes from that source module). Soft: missing codes '
             'are skipped. Seed only — other modules may still link/unlink '
             'contexts on this agent (dynamic bundle). Core system_prompt is '
             'never listed here. Used by Defaults and by import linking.',
    )
    required_context_codes = fields.Text(
        string='Required context codes',
        help='Hard require list (CSV / newlines). Codes only (no @packs). '
             'If a required code exists in the catalog, it stays on this '
             "agent's Contexts list (cannot be removed). Defaults / apply "
             'raises if any required code is missing from the catalog. '
             'Depends of the module should already guarantee hard packs.',
    )
    default_skill_codes = fields.Text(
        string='Default skill codes',
        help='Pull list for factory skills (CSV / newlines). Skill codes '
             'and/or @module_name pack refs (all factory skills from that '
             'source module, unless the skill is exclusive). Soft: missing '
             'codes skipped. Used by Defaults and by import linking.',
    )
    context_ids = fields.Many2many(
        'ai.context',
        'ai_agent_context_rel',
        'agent_id',
        'context_id',
        string='Contexts',
        domain="[('active', '=', True), ('context_type', 'not in', %s), "
               "('link_visible', '=', True)]"
               % (list(context_roles.AGENT_LINK_EXCLUDED_TYPES),),
        help='Domain contexts for this agent. Core contexts '
             '(context_type=core) are injected automatically into every agent. '
             'Discover contexts are engine-only routing, not selectable here.',
    )
    skill_ids = fields.Many2many(
        'ai.skill',
        'ai_agent_skill_rel',
        'agent_id',
        'skill_id',
        string='Skills',
        domain="[('link_visible', '=', True)]",
        help='Skills exposed by this agent. Empty agent_ids still means '
             'global at runtime (get_for_agent). Factory pull uses @module '
             'like contexts.',
    )
    context_ids_shown = fields.Many2many(
        'ai.context',
        compute='_compute_link_ids_shown',
        inverse='_inverse_context_ids_shown',
        string='Contexts',
        domain="[('active', '=', True), ('context_type', 'not in', %s)]"
               % (list(context_roles.AGENT_LINK_EXCLUDED_TYPES),),
    )
    skill_ids_shown = fields.Many2many(
        'ai.skill',
        compute='_compute_link_ids_shown',
        inverse='_inverse_skill_ids_shown',
        string='Skills',
        domain="[('active', '=', True)]",
    )
    link_show_native = fields.Boolean(
        string='native',
        default=True,
        copy=False,
        help='Show native rows (this agent\'s own factory files).',
    )
    link_show_imported = fields.Boolean(
        string='imported',
        default=True,
        copy=False,
        help='Show imported rows (other modules embarked in this agent\'s seed).',
    )
    link_show_pinned = fields.Boolean(
        string='pinned',
        default=True,
        copy=False,
        help='Show pinned rows (other modules pinched onto this agent).',
    )
    link_show_extra = fields.Boolean(
        string='extra',
        default=True,
        copy=False,
        help='Show extra rows (user / slash; not in the recipe).',
    )

    # ── Cache del prompt compilado (delegado al perfil cuando existe) ──
    cached_content = fields.Text(string='Cached content', readonly=True, copy=False)
    cache_locale = fields.Char(string='Cache locale', readonly=True, copy=False)
    cache_updated = fields.Datetime(string='Cache updated', readonly=True, copy=False)
    cache_context_signature = fields.Char(
        readonly=True,
        copy=False,
        help='Hash of context write_dates used to invalidate cache.',
    )

    _sql_constraints = [
        ('code_uniq', 'unique(code)', 'Agent code must be unique.'),
    ]

    # ── Origin-based protections ──────────────────────────────────────

    @api.model
    def create(self, vals):
        """Block dynamic agent creation.

        Only module-created agents (origin='module') are allowed.
        User-created agents are blocked because they would be orphan
        records with no technical coupling to the application.
        """
        # Normalize: O19 passes a list, O14 passes a dict
        if isinstance(vals, list):
            for v in vals:
                self._check_agent_create(v)
            records = super().create(vals)
            records._restore_required_context_links()
            return records
        self._check_agent_create(vals)
        records = super().create(vals)
        records._restore_required_context_links()
        return records

    def write(self, vals):
        hidden_ctx = {}
        hidden_sk = {}
        if not self.env.context.get('_skip_link_filter_merge'):
            if 'context_ids' in vals:
                for rec in self:
                    hidden_ctx[rec.id] = rec._link_ids_hidden('context')
            if 'skill_ids' in vals:
                for rec in self:
                    hidden_sk[rec.id] = rec._link_ids_hidden('skill')
        res = super().write(vals)
        if hidden_ctx or hidden_sk:
            for rec in self:
                payload = {}
                extra_ctx = hidden_ctx.get(rec.id)
                extra_sk = hidden_sk.get(rec.id)
                if extra_ctx:
                    missing = extra_ctx - rec.context_ids
                    if missing:
                        payload['context_ids'] = [(4, rid) for rid in missing.ids]
                if extra_sk:
                    missing = extra_sk - rec.skill_ids
                    if missing:
                        payload['skill_ids'] = [(4, rid) for rid in missing.ids]
                if payload:
                    rec.with_context(
                        _skip_link_filter_merge=True,
                        _skip_required_context_restore=True,
                    ).write(payload)
        if self.env.context.get('_skip_required_context_restore'):
            return res
        if 'context_ids' in vals or 'required_context_codes' in vals:
            self._restore_required_context_links()
        return res

    def _check_agent_create(self, vals):
        """Validate a single vals dict for agent creation rules."""
        if not self.env.context.get('install_mode'):
            origin = vals.get('origin', 'user')
            if origin != 'module':
                raise UserError(_(
                    'Agents can only be created by installed modules. '
                    'Use the agent form to configure existing agents.'
                ))
        if vals.get('origin', 'user') == 'user':
            vals['agent_type'] = 'inference'

    def unlink(self):
        """Prevent deletion of module-owned agents."""
        protected = self.filtered(lambda a: a.origin == 'module')
        if protected:
            names = ', '.join(protected.mapped('name'))
            raise UserError(_(
                'Cannot delete module-managed agents: %s.\n'
                'These agents are owned by their respective modules. '
                'Uninstall the module to remove them.'
            ) % names)
        return super().unlink()

    # ═══════════════════════════════════════════════════════════════════
    # Context compilation & cache (absorbed from former ai.context.bundle)
    # ═══════════════════════════════════════════════════════════════════

    def _resolve_locale(self, user_locale=None):
        if not user_locale:
            user_locale = self.env.context.get('lang') or 'en_US'
        return str(user_locale).replace('-', '_')

    @api.model
    def _system_contexts(self):
        """Core contexts (context_type=core). Injected into ALL agents
        automatically: cross-cutting system rules (protocol, always present)."""
        return self.env['ai.context'].search([
            ('active', '=', True),
            ('context_type', '=', 'core'),
        ])

    def _build_content(self, user_locale=None, active_user=None):
        self.ensure_one()
        user_locale = self._resolve_locale(user_locale)
        shared = self._build_shared_content(user_locale=user_locale)
        user_part = self._build_user_owned_content(
            user_locale=user_locale,
            active_user=active_user,
        )
        if user_part:
            return '%s\n\n%s' % (shared, user_part) if shared else user_part
        return shared

    def _shared_contexts_for_cache(self):
        """Module/import contexts cached on the agent (not user-owned).

        When domain-index inject is ON, contexts whose code/base_code is in
        the composed domain index are excluded from the always-on cache and
        loaded turn-scoped on match instead.
        """
        self.ensure_one()
        effective = (
            self._get_effective_contexts().filtered('active')
            | self._system_contexts()
        )
        shared = effective.filtered(lambda c: not c.owner_id)
        indexed = self._indexed_domain_codes_for_cache()
        if not indexed:
            return shared
        return shared.filtered(
            lambda c: (c.base_code or c.code) not in indexed
            and c.code not in indexed
        )

    def _domain_index_inject_enabled(self):
        from ..utils.domain_index import INJECT_ICP_KEY, icp_flag_enabled
        try:
            ICP = self.env['ir.config_parameter'].sudo()
            raw = ICP.get_param(INJECT_ICP_KEY, 'True')
            return icp_flag_enabled(raw, default=True)
        except Exception:
            return True

    def _indexed_domain_codes_for_cache(self):
        """Codes excluded from always-on cache when inject is enabled.

        Applies to every agent type. Inference (Chatboo) re-injects matched
        packs each turn; endpoint (MCP) re-injects when ``query`` is passed to
        ``prompts/get`` / ``get_context(system_prompt)``, otherwise appends a
        compact index catalog so the client can ``get_context(code)``.
        """
        if not self._domain_index_inject_enabled():
            return set()
        try:
            return self.env['ai.context'].sudo().get_discovery_indexed_codes()
        except Exception:
            _logger.debug(
                'AI agent: could not resolve indexed domain codes',
                exc_info=True,
            )
            return set()

    def domain_index_runtime_tail(self, user_message=None, user_locale=None):
        """Append turn-scoped packs (with query) or a compact catalog (no query).

        Shared by Chatboo (via AgentEngine) and MCP ``system_prompt`` serving.
        """
        self.ensure_one()
        if not self._domain_index_inject_enabled():
            return ''
        from ..utils.agent_engine import AgentEngine
        engine = AgentEngine(self.env)
        msg = (user_message or '').strip()
        if msg:
            return engine._domain_index_runtime_hint(
                msg, user_locale=user_locale,
            ) or ''
        return engine._domain_index_catalog_hint() or ''

    def enrich_with_domain_index(self, content, user_message=None, user_locale=None):
        """Return ``content`` + domain-index tail (inject or catalog)."""
        base = content or ''
        tail = self.domain_index_runtime_tail(
            user_message=user_message, user_locale=user_locale,
        )
        if not tail:
            return base
        return '%s%s' % (base, tail) if base else tail

    def _user_owned_contexts_for_user(self, active_user=None):
        self.ensure_one()
        user = active_user or self.env.user
        Context = self.env['ai.context']
        user_owned = self._get_effective_contexts().filtered(
            lambda c: c.active and c.owner_id,
        )
        return Context.filter_visible_for_user(user_owned, user=user)

    def _build_shared_content(self, user_locale=None):
        self.ensure_one()
        user_locale = self._resolve_locale(user_locale)
        Context = self.env['ai.context']
        shared_contexts = self._shared_contexts_for_cache()
        context_parts = Context.assemble_context_parts(
            shared_contexts,
            user_locale=user_locale,
        )
        lang_directive = Context.build_language_directive(user_locale)
        header = 'Agent=%s | Locale=%s | Contexts=%d\n' % (
            self.code, user_locale, len(context_parts),
        )
        body = '\n\n'.join(context_parts)
        if body:
            return header + body + '\n\n---\n' + lang_directive
        return header + lang_directive

    def _build_user_owned_content(self, user_locale=None, active_user=None):
        self.ensure_one()
        user_locale = self._resolve_locale(user_locale)
        Context = self.env['ai.context']
        user_contexts = self._user_owned_contexts_for_user(active_user=active_user)
        if not user_contexts:
            return ''
        parts = Context.assemble_context_parts(
            user_contexts,
            user_locale=user_locale,
        )
        if not parts:
            return ''
        return '---\n## User knowledge\n' + '\n\n'.join(parts)

    # ── Context resolution ────────────────────────────────────────────

    @api.model
    def _parse_knowledge_tokens(self, raw):
        """Split CSV/newline pull lists into codes and @module pack refs."""
        codes = set()
        packs = set()
        if not raw:
            return codes, packs
        for part in str(raw).replace('\n', ',').replace(';', ',').split(','):
            token = part.strip()
            if not token:
                continue
            if token.startswith('@'):
                mod = token[1:].strip()
                if mod:
                    packs.add(mod)
            else:
                codes.add(token)
        return codes, packs

    def _module_factory_seed(self):
        """Shipped Factory-tab texts for this module-owned agent."""
        self.ensure_one()
        if self.code == MCP_BARE_AGENT_CODE:
            return {
                'default_context_codes': '@pns_ai_mcp',
                'required_context_codes': 'self_mcp',
            }
        return {}

    def _default_context_tokens(self):
        self.ensure_one()
        return self._parse_knowledge_tokens(self.default_context_codes)

    def _required_context_codes_set(self):
        self.ensure_one()
        codes, _packs = self._parse_knowledge_tokens(self.required_context_codes)
        return codes

    def _restore_required_context_links(self):
        """Keep required catalog codes on this agent's Contexts list."""
        if self.env.context.get('_skip_required_context_restore'):
            return self
        Context = self.env['ai.context']
        excluded = list(context_roles.AGENT_LINK_EXCLUDED_TYPES)
        for agent in self:
            codes = agent._required_context_codes_set()
            if not codes:
                continue
            missing = Context.search([
                ('code', 'in', list(codes)),
                ('active', '=', True),
                ('id', 'not in', agent.context_ids.ids),
                ('context_type', 'not in', excluded),
            ])
            if missing:
                agent.with_context(_skip_required_context_restore=True).write({
                    'context_ids': [(4, cid) for cid in missing.ids],
                })
        return self

    def _default_skill_tokens(self):
        self.ensure_one()
        return self._parse_knowledge_tokens(self.default_skill_codes)

    def wants_context_code(
        self, context_code, source_module=None, pack_exclusive=False,
    ):
        """True if this agent's pull list requests the context code/pack.

        ``pack_exclusive``: the pack declared explicit ``agent_codes`` (or
        catalog-only). ``@module`` pull does not attach it unless this
        agent lists the code itself.
        """
        self.ensure_one()
        if not context_code:
            return False
        codes, packs = self._default_context_tokens()
        if context_code in codes:
            return True
        if pack_exclusive:
            return False
        if source_module and source_module in packs:
            return True
        return False

    def wants_skill_code(
        self, skill_code, source_module=None, pack_exclusive=False,
    ):
        """True if this agent's pull list requests the skill code/pack.

        Same contract as ``wants_context_code``: ``@module`` pulls the
        whole factory drawer unless the skill declared exclusive
        ``agent_codes``.
        """
        self.ensure_one()
        if not skill_code:
            return False
        codes, packs = self._default_skill_tokens()
        if skill_code in codes:
            return True
        if pack_exclusive:
            return False
        if source_module and source_module in packs:
            return True
        return False

    @api.model
    def composition_agent_from_env(self):
        """Agent whose form is showing Contexts / Skills (link-origin column)."""
        aid = self.env.context.get('composition_agent_id')
        if not aid and self.env.context.get('active_model') == 'ai.agent':
            aid = self.env.context.get('active_id')
        if not aid:
            return self.browse()
        try:
            aid = int(aid)
        except (TypeError, ValueError):
            return self.browse()
        agent = self.browse(aid)
        return agent if agent.exists() else self.browse()

    def composition_origin_for(self, code, source_module, kind='context'):
        """Classify a live M2M row: native, imported, pinned, or extra.

        native — file of this agent (``source_module`` is ``module_name``/code).
        imported — other module embarked in this agent's XML seed.
        pinned — other module pinched onto the current recipe at install.
        extra — not in the current recipe (user / slash). Empty
        ``source_module`` cannot be native/imported.
        """
        self.ensure_one()
        seed = self._module_factory_seed() or {}
        if kind == 'skill':
            seed_codes, seed_packs = self._parse_knowledge_tokens(
                seed.get('default_skill_codes'),
            )
            seed_req = set()
            cur_codes, cur_packs = self._default_skill_tokens()
            cur_req = set()
        else:
            seed_codes, seed_packs = self._parse_knowledge_tokens(
                seed.get('default_context_codes'),
            )
            seed_req, _unused = self._parse_knowledge_tokens(
                seed.get('required_context_codes'),
            )
            cur_codes, cur_packs = self._default_context_tokens()
            cur_req = self._required_context_codes_set()
        src = (source_module or '').strip()
        in_recipe = (
            code in cur_codes
            or code in cur_req
            or (src and src in cur_packs)
        )
        if not in_recipe or not src:
            return 'extra'
        own = src in {
            (self.module_name or '').strip(),
            (self.code or '').strip(),
        }
        if own:
            return 'native'
        in_seed = (
            code in seed_codes
            or code in seed_req
            or (src and src in seed_packs)
        )
        if in_seed:
            return 'imported'
        return 'pinned'

    def _link_origins_shown(self):
        """Tokens currently checked on the agent form (empty = all)."""
        self.ensure_one()
        shown = []
        if self.link_show_native:
            shown.append('native')
        if self.link_show_imported:
            shown.append('imported')
        if self.link_show_pinned:
            shown.append('pinned')
        if self.link_show_extra:
            shown.append('extra')
        return shown or list(COMPOSITION_ORIGIN_TOKENS)

    def _link_ids_shown(self, kind):
        """Linked rows whose origin is currently toggled on."""
        self.ensure_one()
        records = self.context_ids if kind == 'context' else self.skill_ids
        shown = set(self._link_origins_shown())
        if shown == set(COMPOSITION_ORIGIN_TOKENS):
            return records
        keep = records.browse()
        for rec in records:
            origin = self.composition_origin_for(rec.code, rec.source_module, kind)
            if origin in shown:
                keep |= rec
        return keep

    def _link_ids_hidden(self, kind):
        """Linked rows hidden by the origin toggles."""
        self.ensure_one()
        records = self.context_ids if kind == 'context' else self.skill_ids
        return records - self._link_ids_shown(kind)

    @api.depends(
        'context_ids', 'skill_ids',
        'context_ids.code', 'context_ids.source_module',
        'skill_ids.code', 'skill_ids.source_module',
        'link_show_native', 'link_show_imported',
        'link_show_pinned', 'link_show_extra',
        'default_context_codes', 'required_context_codes',
        'default_skill_codes', 'module_name', 'code',
    )
    def _compute_link_ids_shown(self):
        for rec in self:
            rec.context_ids_shown = rec._link_ids_shown('context')
            rec.skill_ids_shown = rec._link_ids_shown('skill')

    def _inverse_context_ids_shown(self):
        for rec in self:
            hidden = rec._link_ids_hidden('context')
            rec.with_context(_skip_link_filter_merge=True).write({
                'context_ids': [(6, 0, (rec.context_ids_shown | hidden).ids)],
            })

    def _inverse_skill_ids_shown(self):
        for rec in self:
            hidden = rec._link_ids_hidden('skill')
            rec.with_context(_skip_link_filter_merge=True).write({
                'skill_ids': [(6, 0, (rec.skill_ids_shown | hidden).ids)],
            })

    def action_toggle_link_show(self):
        """Flip one origin toggle (tests / RPC). The form JS paints in place."""
        self.ensure_one()
        token = self.env.context.get('link_show_token')
        if token not in COMPOSITION_ORIGIN_TOKENS:
            return True
        field = 'link_show_%s' % token
        self.write({field: not bool(self[field])})
        return True

    def _factory_restore_codes(self, kind='context'):
        """Codes Restore may overwrite: native ∪ imported (XML seed only)."""
        self.ensure_one()
        seed = self._module_factory_seed() or {}
        if kind == 'skill':
            pull = self._parse_knowledge_tokens(seed.get('default_skill_codes'))
            return self.env['ai.skill'].default_skill_codes_for_agent(
                self.code, pull_tokens=pull,
            )
        codes, packs = self._parse_knowledge_tokens(
            seed.get('default_context_codes'),
        )
        req, _unused = self._parse_knowledge_tokens(
            seed.get('required_context_codes'),
        )
        return self.env['ai.context'].default_context_codes_for_agent(
            self.code, pull_tokens=(codes | req, packs),
        )

    @api.model
    def _composition_origin_wanted(self, operator, value):
        tokens = set(COMPOSITION_ORIGIN_TOKENS)
        if isinstance(value, (list, tuple, set)):
            vals = set(value)
        elif value in (True, False, None):
            vals = set()
        else:
            vals = {value}
        vals &= tokens
        if operator in ('=', 'in', '=='):
            return vals
        if operator in ('!=', 'not in', '<>'):
            return tokens - vals
        return tokens

    @api.model
    def _composition_cell_id(self, cell):
        if isinstance(cell, int):
            return cell
        if isinstance(cell, dict):
            return cell.get('id')
        if isinstance(cell, (list, tuple)) and cell:
            try:
                return int(cell[0])
            except (TypeError, ValueError):
                return None
        return None

    def _sorted_composition_cells(self, cells, kind):
        """M2M cells in native → imported → pinned → extra order, then code."""
        self.ensure_one()
        if not cells:
            return cells
        model = 'ai.context' if kind == 'context' else 'ai.skill'
        by_id = {}
        ids = []
        for cell in cells:
            rid = self._composition_cell_id(cell)
            if not rid or rid in by_id:
                continue
            ids.append(rid)
            by_id[rid] = cell
        recs = self.env[model].browse(ids).exists()
        ordered = recs.sorted(
            key=lambda rec: (
                COMPOSITION_ORIGIN_RANK.get(
                    self.composition_origin_for(
                        rec.code, rec.source_module, kind,
                    ),
                    9,
                ),
                (rec.code or '').lower(),
                rec.id,
            ),
        )
        result = [by_id[rid] for rid in ordered.ids if rid in by_id]
        seen = set(ordered.ids)
        result.extend(
            cell for cell in cells
            if self._composition_cell_id(cell) not in seen
        )
        return result

    def _order_composition_in_read_rows(self, rows):
        if not rows:
            return rows
        by_id = {rec.id: rec for rec in self}
        for row in rows:
            agent = by_id.get(row.get('id'))
            if not agent:
                continue
            if 'context_ids' in row:
                row['context_ids'] = agent._sorted_composition_cells(
                    row['context_ids'], 'context',
                )
            if 'skill_ids' in row:
                row['skill_ids'] = agent._sorted_composition_cells(
                    row['skill_ids'], 'skill',
                )
        return rows

    def read(self, fields=None, load='_classic_read'):
        rows = super().read(fields=fields, load=load)
        return self._order_composition_in_read_rows(rows)

    def web_read(self, specification, *args, **kwargs):
        rows = super().web_read(specification, *args, **kwargs)
        if not isinstance(rows, list):
            return rows
        return self._order_composition_in_read_rows(rows)

    def _comodel_origin_search_domain(self, comodel, kind, operator, value):
        """Domain of context/skill ids whose origin matches ``value``."""
        agent = self.composition_agent_from_env()
        if not agent:
            return [(1, '=', 1)]
        wanted = self._composition_origin_wanted(operator, value)
        if not wanted:
            return [('id', '=', False)]
        if wanted == set(COMPOSITION_ORIGIN_TOKENS):
            return [(1, '=', 1)]
        ids = [
            rec.id for rec in comodel.search([])
            if agent.composition_origin_for(
                rec.code, rec.source_module, kind,
            ) in wanted
        ]
        return [('id', 'in', ids)]

    def _comodel_link_visible_search_domain(self, comodel, kind, operator, value):
        """Domain honoring this agent's origin checkboxes."""
        agent = self.composition_agent_from_env()
        if not agent:
            return [(1, '=', 1)]
        shown = set(agent._link_origins_shown())
        visible = True
        if operator in ('=', '=='):
            visible = bool(value)
        elif operator in ('!=', '<>'):
            visible = not bool(value)
        if visible:
            if shown == set(COMPOSITION_ORIGIN_TOKENS):
                return [(1, '=', 1)]
            return self._comodel_origin_search_domain(
                comodel, kind, 'in', list(shown),
            )
        hidden = set(COMPOSITION_ORIGIN_TOKENS) - shown
        return self._comodel_origin_search_domain(
            comodel, kind, 'in', list(hidden),
        )

    @api.model
    def fields_get(self, allfields=None, attributes=None):
        """Keep origin filter checkbox labels as English tokens."""
        res = super().fields_get(allfields=allfields, attributes=attributes)
        for token in COMPOSITION_ORIGIN_TOKENS:
            info = res.get('link_show_%s' % token)
            if info:
                info['string'] = token
        return res

    def _assert_required_contexts_present(self, available_codes):
        """Raise if hard-required context codes are absent from ``available_codes``."""
        self.ensure_one()
        missing = sorted(self._required_context_codes_set() - set(available_codes or []))
        if missing:
            raise UserError(_(
                'Agent %(agent)s requires context code(s) missing from the '
                'catalog: %(codes)s. Install the owning knowledge pack or '
                'remove them from Required context codes.'
            ) % {'agent': self.code, 'codes': ', '.join(missing)})

    def _get_effective_contexts(self):
        """Return this agent's own domain contexts.

        Each agent owns its contexts directly via ``context_ids``. Shared
        knowledge is materialised at import time by dual wire (pack push +
        agent pull); see ``ai.context._resolve_import_agent_codes``.

        Identity packs (``self`` / ``self_*``) of another agent are never
        injected, even if a leftover M2M tick is still present.
        """
        self.ensure_one()
        from ..utils.agent_identity import is_foreign_identity_pack
        return self.context_ids.filtered(
            lambda c: not is_foreign_identity_pack(self.code, c.code)
        )

    def _context_signature(self):
        self.ensure_one()
        contexts = self._shared_contexts_for_cache()
        parts = []
        for ctx in contexts.sorted(lambda c: c.code):
            parts.append('%s:%s' % (ctx.id, ctx.write_date or ''))
        return '|'.join(parts)

    # ── Context bulk selection ───────────────────────────────────────

    def action_select_all_contexts(self):
        """Add ALL active non-core contexts to the agent."""
        all_ctx = self.env['ai.context'].search([
            ('active', '=', True),
            ('context_type', 'not in', context_roles.AGENT_LINK_EXCLUDED_TYPES),
        ])
        self.write({'context_ids': [(6, 0, all_ctx.ids)]})

    def action_select_none_contexts(self):
        """Remove all contexts from the agent."""
        self.write({'context_ids': [(5, 0, 0)]})

    def action_invert_contexts(self):
        """Toggle: add missing contexts and remove existing ones."""
        all_ctx = self.env['ai.context'].search([
            ('active', '=', True),
            ('context_type', 'not in', context_roles.AGENT_LINK_EXCLUDED_TYPES),
        ])
        current = self.context_ids
        inverted = all_ctx - current
        self.write({'context_ids': [(6, 0, inverted.ids)]})

    def action_reset_contexts_to_default(self):
        """Re-add native + imported + pinned (current recipe).

        Does not unlink extra links. Does not edit context *content*.
        """
        self.ensure_one()
        Context = self.env['ai.context']
        codes = Context.default_context_codes_for_agent(self.code)
        catalog_codes = set(Context.search([
            ('active', '=', True),
            ('context_type', 'not in', context_roles.AGENT_LINK_EXCLUDED_TYPES),
        ]).mapped('code'))
        self._assert_required_contexts_present(catalog_codes)
        default_ctx = Context.search([
            ('code', 'in', list(codes)),
            ('active', '=', True),
            ('context_type', 'not in', context_roles.AGENT_LINK_EXCLUDED_TYPES),
        ]) if codes else Context.browse()
        missing = default_ctx - self.context_ids
        if missing:
            self.write({'context_ids': [(4, cid) for cid in missing.ids]})
        self.get_content(force_rebuild=True)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Composition restored'),
                'message': _(
                    '%(n)d default context(s) restored for agent %(code)s.'
                ) % {'n': len(default_ctx), 'code': self.code},
                'type': 'success',
                'sticky': False,
            },
        }

    def action_restore_contexts_from_module(self):
        """Re-import THIS agent's shipped context files from disk (content).

        Scope = native ∪ imported (this agent's XML seed). Pinned and extra
        content is not overwritten. Distinct from Defaults (selection only).
        """
        self.ensure_one()
        ensure_ai_admin(self.env)
        Context = self.env['ai.context']
        codes = self._factory_restore_codes('context')
        if not codes:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Nothing to restore'),
                    'message': _(
                        'Agent %(code)s ships no context files.'
                    ) % {'code': self.code},
                    'type': 'warning',
                    'sticky': False,
                },
            }
        result = Context.with_context(
            skip_hardcoded_restrictions=True,
        )._import_all_from_module(replace_existing=True, only_codes=list(codes))
        self.get_content(force_rebuild=True)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Contexts restored from module'),
                'message': _(
                    '%(i)d imported, %(u)d updated for agent %(code)s.'
                ) % {
                    'i': result.get('imported', 0),
                    'u': result.get('updated', 0),
                    'code': self.code,
                },
                'type': 'success',
                'sticky': False,
            },
        }

    # ── Skill bulk selection & module restore (symmetric to contexts) ──

    def _all_agent_skills(self):
        """Non-global skills selectable for an agent (global ones are auto)."""
        return self.env['ai.skill'].search([('active', '=', True)])

    def action_select_all_skills(self):
        self.write({'skill_ids': [(6, 0, self._all_agent_skills().ids)]})

    def action_select_none_skills(self):
        self.write({'skill_ids': [(5, 0, 0)]})

    def action_invert_skills(self):
        all_sk = self._all_agent_skills()
        self.write({'skill_ids': [(6, 0, (all_sk - self.skill_ids).ids)]})

    def action_reset_skills_to_default(self):
        """Re-add native + imported + pinned (current recipe).

        Imports missing shipped skills from disk first (upsert), then links
        them. Does not unlink extra skills.
        """
        self.ensure_one()
        ensure_ai_admin(self.env)
        Skill = self.env['ai.skill'].with_context(skip_hardcoded_restrictions=True)
        codes = Skill.default_skill_codes_for_agent(self.code)
        stats = {}
        if codes:
            stats = Skill.import_from_files(
                replace_existing=True, only_codes=list(codes),
            )
        default_sk = Skill.search([
            ('active', '=', True),
            '|', ('code', 'in', list(codes)), ('command', 'in', list(codes)),
        ]) if codes else Skill.browse()
        missing_sk = default_sk - self.skill_ids
        if missing_sk:
            self.write({'skill_ids': [(4, sid) for sid in missing_sk.ids]})
        missing = sorted(
            set(codes)
            - set(default_sk.mapped('code'))
            - set(filter(None, default_sk.mapped('command')))
        ) if codes else []
        errors = stats.get('errors') or []
        message = _(
            '%(n)d default skill(s) selected for agent %(code)s.'
        ) % {'n': len(default_sk), 'code': self.code}
        if stats:
            message += ' ' + _(
                'Import: %(c)d created, %(u)d updated.'
            ) % {
                'c': stats.get('created', 0),
                'u': stats.get('updated', 0),
            }
        if missing:
            message += ' ' + _(
                'Missing after import: %(codes)s.'
            ) % {'codes': ', '.join(missing)}
        ntype = 'success'
        if errors or missing:
            ntype = 'warning'
        if errors:
            message += ' ' + '; '.join(errors[:3])
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Skills restored'),
                'message': message,
                'type': ntype,
                'sticky': bool(errors or missing),
            },
        }

    def action_restore_skills_from_module(self):
        """Re-import THIS agent's shipped skill files from disk (content).

        Scope = native ∪ imported (this agent's XML seed). Pinned and extra
        content is not overwritten. Distinct from Defaults (selection only).
        """
        self.ensure_one()
        ensure_ai_admin(self.env)
        Skill = self.env['ai.skill']
        codes = self._factory_restore_codes('skill')
        if not codes:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Nothing to restore'),
                    'message': _(
                        'Agent %(code)s ships no skill files.'
                    ) % {'code': self.code},
                    'type': 'warning',
                    'sticky': False,
                },
            }
        stats = Skill.import_from_files(replace_existing=True, only_codes=list(codes))
        errors = stats.get('errors') or []
        found = Skill.search([
            '|', ('code', 'in', list(codes)), ('command', 'in', list(codes)),
        ])
        missing = sorted(
            set(codes)
            - set(found.mapped('code'))
            - set(filter(None, found.mapped('command')))
        )
        message = _(
            '%(c)d created, %(u)d updated for agent %(code)s.'
        ) % {
            'c': stats.get('created', 0),
            'u': stats.get('updated', 0),
            'code': self.code,
        }
        ntype = 'success'
        if errors or missing:
            ntype = 'warning'
        if missing:
            message += ' ' + _(
                'Still missing: %(codes)s.'
            ) % {'codes': ', '.join(missing)}
        if errors:
            message += ' ' + '; '.join(errors[:3])
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Skills restored from module'),
                'message': message,
                'type': ntype,
                'sticky': bool(errors or missing),
            },
        }

    def action_export_skills_zip(self):
        self.ensure_one()
        ensure_ai_admin(self.env)
        return self.env['ai.skill'].export_agent_skills_to_zip(self)

    def action_open_import_agent_skills_wizard(self):
        self.ensure_one()
        ensure_ai_admin(self.env)
        return {
            'type': 'ir.actions.act_window',
            'name': _('Import agent skills from ZIP'),
            'res_model': 'pns_ai_mcp.agent.skill.import.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_agent_id': self.id},
        }

    # ── Content compilation & cache ─────────────────────────────────

    def get_content(self, user_locale=None, force_rebuild=False, active_user=None):
        """Return compiled prompt text.

        Uses the agent's own contexts plus the always-injected core contexts.
        User-owned contexts are appended per user and are not stored in
        ``cached_content``.
        """
        self.ensure_one()
        user = active_user or self.env.user
        user_locale = self._resolve_locale(user_locale)
        signature = self._context_signature()
        shared_content = None
        if (
            not force_rebuild
            and self.cached_content
            and self.cache_locale == user_locale
            and self.cache_context_signature == signature
        ):
            shared_content = self.cached_content
        else:
            shared_content = self._build_shared_content(user_locale=user_locale)
            if force_rebuild:
                self.sudo().write({
                    'cached_content': shared_content,
                    'cache_locale': user_locale,
                    'cache_updated': fields.Datetime.now(),
                    'cache_context_signature': signature,
                })
            else:
                self._persist_cache_isolated(shared_content, user_locale, signature)
        user_part = self._build_user_owned_content(
            user_locale=user_locale,
            active_user=user,
        )
        if user_part:
            raw = '%s\n\n%s' % (shared_content, user_part) if shared_content else user_part
        else:
            raw = shared_content or ''
        return self._apply_resolved_identity(raw)

    @api.model
    def _host_identity_registry(self):
        """``agent.code`` → display/vendor constants. Owning modules extend.

        The engine ships only the MCP endpoint entry. It does not list
        Chatboo or third-party brands.
        """
        from ..utils.mcp_identity import mcp_host_identity_registry
        return dict(mcp_host_identity_registry())

    def _identity_self_metadata(self):
        """``product_name`` / ``vendor`` from this agent's own ``self_*`` pack."""
        self.ensure_one()
        from ..utils.agent_identity import first_identity_text, own_self_pack_code
        own = own_self_pack_code(self.code)
        if not own:
            return {}
        Context = self.env['ai.context']
        found = {}
        for ctx in self.context_ids.filtered(lambda c: (c.code or '') == own):
            meta = Context._extract_metadata_from_content(
                ctx.content or '', 'pack.xml',
            )
            name = first_identity_text(
                found.get('product_name'),
                meta.get('product_name'),
                meta.get('display_name'),
            )
            if name:
                found['product_name'] = name
            vendor = first_identity_text(found.get('vendor'), meta.get('vendor'))
            if vendor:
                found['vendor'] = vendor
        return found

    def _unlink_foreign_identity_packs(self):
        """Drop retired ``self`` and other agents' ``self_*`` from pins and M2M.

        Pins are rewritten first so ``_restore_required_context_links`` cannot
        re-attach the leftover row.
        """
        from ..utils.agent_identity import (
            drop_pin_tokens,
            ensure_pin_token,
            is_identity_pack_code,
            own_self_pack_code,
            parse_pin_tokens,
        )
        factory_codes = ('pns_ai_mcp', 'pns_ai_chatboo')
        for agent in self:
            own = own_self_pack_code(agent.code)
            drop = {'self'}
            for token in (
                parse_pin_tokens(agent.required_context_codes)
                + parse_pin_tokens(agent.default_context_codes)
            ):
                if is_identity_pack_code(token) and token != own:
                    drop.add(token)
            vals = {}
            new_req = drop_pin_tokens(agent.required_context_codes, drop)
            if agent.code in factory_codes and own:
                new_req = ensure_pin_token(new_req, own)
            if parse_pin_tokens(new_req) != parse_pin_tokens(
                agent.required_context_codes
            ):
                vals['required_context_codes'] = new_req
            new_def = drop_pin_tokens(agent.default_context_codes, drop)
            if parse_pin_tokens(new_def) != parse_pin_tokens(
                agent.default_context_codes
            ):
                vals['default_context_codes'] = new_def
            if vals:
                agent.with_context(_skip_required_context_restore=True).write(vals)
            foreign = agent.context_ids.filtered(
                lambda c, _own=own: is_identity_pack_code(c.code) and c.code != _own
            )
            if foreign:
                agent.with_context(_skip_required_context_restore=True).write({
                    'context_ids': [(3, cid) for cid in foreign.ids],
                })
        return self

    def _module_ficha_author(self):
        """Manifest ``author`` of the owning module (plan C). Empty if none."""
        self.ensure_one()
        if not self.module_name:
            return ''
        try:
            mod = self.env['ir.module.module'].search(
                [('name', '=', self.module_name)], limit=1,
            )
        except Exception:
            return ''
        return (mod.author or '').strip() if mod else ''

    def _resolve_host_identity(self):
        """Cascade: owning-module Python → self_* metadata → module ficha.

        Canonical keys on every rung: ``product_name`` and ``vendor``.
        Plan C maps Odoo fields at the boundary (``ai.agent.name`` /
        ``module_name`` → name; ``ir.module.module.author`` → vendor).
        """
        self.ensure_one()
        from ..utils.agent_identity import first_identity_text
        reg = (self._host_identity_registry() or {}).get(self.code) or {}
        product_name = first_identity_text(
            reg.get('product_name'), reg.get('display_name'),
        )
        vendor = first_identity_text(reg.get('vendor'))
        extra = {
            'vendor_place': first_identity_text(reg.get('vendor_place')) or None,
            'vendor_years': first_identity_text(reg.get('vendor_years')) or None,
            'vendor_url': first_identity_text(reg.get('vendor_url')) or None,
        }
        if not product_name or not vendor:
            meta = self._identity_self_metadata()
            if not product_name:
                product_name = first_identity_text(meta.get('product_name'))
            if not vendor:
                vendor = first_identity_text(meta.get('vendor'))
        if self.origin == 'module':
            if not product_name:
                product_name = first_identity_text(self.name, self.module_name)
            if not vendor:
                vendor = first_identity_text(self._module_ficha_author())
        return {
            'product_name': product_name or None,
            'vendor': vendor or None,
            **extra,
        }

    def _apply_resolved_identity(self, prompt):
        from ..utils.agent_identity import apply_resolved_identity
        return apply_resolved_identity(prompt or '', **self._resolve_host_identity())

    def _persist_cache_isolated(self, content, user_locale, signature):
        """Write cache in an isolated cursor (short commit) to avoid
        serialization failures in long SSE transactions."""
        try:
            with self.env.registry.cursor() as ncr:
                ncr.execute(
                    """UPDATE ai_agent
                          SET cached_content = %s,
                              cache_locale = %s,
                              cache_updated = (now() at time zone 'UTC'),
                              cache_context_signature = %s
                        WHERE id = %s""",
                    (content, user_locale, signature, self.id),
                )
                ncr.commit()
        except Exception:
            _logger.warning(
                "AI: could not persist cache for agent %s", self.id,
                exc_info=True,
            )

    @api.model
    def get_for_agent(self, agent_code, user_locale=None):
        """Resolve agent by code and return its compiled content."""
        agent = self.search([('code', '=', agent_code)], limit=1)
        if not agent:
            return ''
        return agent.get_content(user_locale=user_locale)

    def _sync_composition_and_cache(self):
        """Normalize canonical context_ids and rebuild cache in one step."""
        Context = self.env['ai.context']
        for agent in self:
            if agent.context_ids:
                canonical_ids = Context.normalize_context_ids(agent.context_ids)
                if set(canonical_ids) != set(agent.context_ids.ids):
                    agent.write({'context_ids': [(6, 0, canonical_ids)]})
            agent.get_content(force_rebuild=True)
        return True

    def action_show_stats(self):
        """Open statistics modal: monolithic vs optimized (discovery) for this agent."""
        self.ensure_one()
        Wizard = self.env['pns_ai_mcp.context_stats_wizard']
        wiz = Wizard.create({
            'agent_id': self.id,
            'inject_enabled': self._domain_index_inject_enabled(),
            'show_ktokens': True,
            'stats_html': Wizard._html_for_agent(self, as_ktokens=True),
        })
        return {
            'type': 'ir.actions.act_window',
            'name': _('Agent Statistics'),
            'res_model': 'pns_ai_mcp.context_stats_wizard',
            'res_id': wiz.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def _format_cache_size(self, size_bytes):
        if size_bytes == 0:
            return '0 B'
        kb = size_bytes / 1024.0
        if kb < 1024:
            return '%.2f KB' % kb
        return '%.2f MB' % (kb / 1024.0)

    def action_rebuild_cache(self):
        for agent in self:
            agent.get_content(force_rebuild=True)
        return True

    def action_normalize_composition(self):
        return self._sync_composition_and_cache()

    def action_export_contexts_zip(self):
        self.ensure_one()
        ensure_ai_admin(self.env)
        return self.env['ai.context'].export_agent_contexts_to_zip(self)

    def action_open_import_agent_contexts_wizard(self):
        self.ensure_one()
        ensure_ai_admin(self.env)
        return {
            'type': 'ir.actions.act_window',
            'name': _('Import agent contexts from ZIP'),
            'res_model': 'pns_ai_mcp.agent.context.import.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_agent_id': self.id},
        }

    def _build_agent_import_report_html(self, zip_bytes, replace_existing=False):
        self.ensure_one()
        Context = self.env['ai.context']
        result = Context.import_agent_contexts_zip(
            self, zip_bytes, replace_existing=replace_existing,
        )
        return Context._build_context_zip_import_report_html(result, title=None)

    def _export_agents_json(self, agents):
        """Shared helper: export given agents to JSON download action."""
        Link = self.env['ai.agent.provider']
        export_data = []
        for agent in agents:
            failovers = Link.with_context(active_test=False).search(
                [('agent_id', '=', agent.id)]
            )
            try:
                agent_data = export_record_dict(agent, skip_fields={'id'})
            except Exception:
                agent_data = {'name': agent.name or '?', 'code': agent.code or '?'}
            try:
                agent_data['failovers'] = [
                    {
                        'provider': a.provider_id.name,
                        'priority': a.priority,
                        'active': a.active,
                    }
                    for a in failovers
                ]
            except Exception:
                pass
            export_data.append(agent_data)

        filename = mcp_ui.build_export_filename(self.env, 'ai_agents', 'json')
        attachment = mcp_ui.write_json_attachment(
            self.env, filename, export_data,
        )
        return mcp_ui.open_json_export_wizard(
            self.env,
            dialog_title=_('Export result'),
            summary_text=_('%s agent(s) exported.') % len(export_data),
            count=len(export_data),
            attachment=attachment,
        )

    def action_export_agents(self, *args, **kwargs):
        """Export all AI agents (with their failover chain) to JSON."""
        ensure_ai_admin(self.env)
        agents = self.with_context(active_test=False).search([])
        if not agents:
            return mcp_ui.open_json_export_empty_wizard(
                self.env,
                dialog_title=_('Export'),
                message=_('There are no agents to export.'),
            )
        return self._export_agents_json(agents)

    def action_export_selected(self, *args, **kwargs):
        """Export selected AI agents to JSON (tree multi-select action)."""
        ensure_ai_admin(self.env)
        if not self:
            return mcp_ui.open_json_export_empty_wizard(
                self.env,
                dialog_title=_('Export'),
                message=_('No agents selected for export.'),
            )
        return self._export_agents_json(self)

    def action_import_agents(self, *args, **kwargs):
        """Open wizard to import agents from JSON."""
        ensure_ai_admin(self.env)
        return {
            'type': 'ir.actions.act_window',
            'name': _('Import Agents'),
            'res_model': 'pns_ai_mcp.import_agents_wizard',
            'view_mode': 'form',
            'views': [[False, 'form']],
            'target': 'new',
        }

class AIAgentProvider(models.Model):
    """AI Agent Provider — a prioritized provider of an agent (join model).

    The entity is "one prioritized provider of the agent"; the *failover* is
    the effect of having several of them ordered, not the entity itself.

        - Each agent has N provider entries, ordered by priority (lowest first).
        - When the agent needs an LLM, it tries provider #1; on connection
          failure, it automatically falls back to #2, then #3, etc.
        - This is NOT load balancing: it's a deterministic priority chain.

    Besides the pairing, this join carries the per-pair connection tuning
    (idle/turn timeouts and the non-streaming fallback switch): the same
    provider can be tried aggressively by one agent and patiently by another.

    Fields:
        agent_id     The agent this entry belongs to (required)
        provider_id  The AI provider (LLM endpoint) to use (required)
        priority     Lower = tried first. Drag rows in the UI to reorder.
        ordinal      Computed: human-readable position (1, 2, 3…)
        active       Inactive entries are skipped in the cascade.

    Example — setting up a 2-provider cascade::

        env['ai.agent.provider'].create([
            {'agent_id': chat.id, 'provider_id': ovh.id, 'priority': 0},
            {'agent_id': chat.id, 'provider_id': lemonade.id, 'priority': 10},
        ])
        # ovh is tried first; lemonade is the backup.
    """
    _name = 'ai.agent.provider'
    _description = 'AI provider priority chain per agent'
    _order = 'agent_id, priority, id'

    agent_id = fields.Many2one('ai.agent', required=True, ondelete='cascade')
    provider_id = fields.Many2one('ai.provider', required=True, ondelete='cascade')
    priority = fields.Integer(
        required=True,
        default=0,
        help='Drag rows to reorder. Lower value = tried first; ties broken by '
             'creation order. The ordinal is derived from the row position.',
    )
    ordinal = fields.Integer(
        string='#',
        compute='_compute_ordinal',
        help='Position in the chain (1 = first tried). Derived from row order.',
    )
    active = fields.Boolean(default=True)

    # ── Per-pair connection tuning (moved from ai.provider) ───────────
    llm_idle_timeout = fields.Integer(
        string='Idle timeout (s)',
        default=45,
        help="Seconds without receiving ANY data from the model (between SSE "
             "chunks) before considering the link stalled and failing over to "
             "the next provider in the cascade.\n"
             "• Local providers: 20-30 s (detect hangs fast).\n"
             "• Remote providers: 45-60 s (more patience).\n"
             "0 or -1 = use the system default (45 s).",
    )
    llm_round_timeout = fields.Integer(
        string='Round timeout (s)',
        default=120,
        help="Maximum seconds for a SINGLE LLM round (one request/response) "
             "before cutting it off and failing over to the next provider. "
             "Local models are slow by nature, but this bounds the worst case "
             "so the cascade is not delayed for minutes.\n"
             "• Local providers: 60-90 s.\n"
             "• Remote providers: 120-180 s.\n"
             "0 or -1 = use the system default (120 s).",
    )
    skip_sync_fallback = fields.Boolean(
        string='Skip non-streaming fallback',
        default=False,
        help="When the stream returns no text, by default a non-streaming "
             "completion is retried as a fallback (adds ~30-45 s of latency). "
             "Enable this on slow LOCAL providers to skip that retry and move "
             "to the next provider sooner. Leave OFF for remote providers.",
    )

    @api.depends('priority', 'agent_id', 'agent_id.provider_ids.priority')
    def _compute_ordinal(self):
        for rec in self:
            agent = rec.agent_id
            if not agent:
                rec.ordinal = 0
                continue
            siblings = agent.provider_ids.sorted(
                key=lambda a: (a.priority, a.id if isinstance(a.id, int) else 1 << 62)
            )
            pos = 0
            for idx, sib in enumerate(siblings, start=1):
                if sib == rec:
                    pos = idx
                    break
            rec.ordinal = pos

    @api.model_create_multi
    def create(self, vals_list):
        """Alta idempotente del enlace agente↔proveedor.

        El par (agent_id, provider_id) es único, pero el hook semilla enlaza
        TODOS los proveedores al agente de inferencia, así que desde la UI es
        habitual acabar "añadiendo" un proveedor que ya está en la cadena (o uno
        cuyo enlace quedó archivado y por tanto oculto). En vez de reventar con
        el error crudo del UNIQUE, reutilizamos el enlace existente: lo
        reactivamos si estaba archivado y le aplicamos el resto de valores
        (prioridad, timeouts…). Añadir pasa a ser un no-op seguro.

        Se preserva el orden de entrada para no romper el mapeo de comandos
        x2many (posición ↔ registro devuelto).
        """
        ctx = self.env.context
        result = self.browse()
        for vals in vals_list:
            # Al crear líneas de un o2m desde el formulario del padre, el inverso
            # (agent_id) puede venir en vals o inyectado como default en contexto,
            # según la versión; contemplamos ambos para no saltarnos el dedup.
            agent_id = vals.get('agent_id') or ctx.get('default_agent_id')
            provider_id = vals.get('provider_id')
            link = self.browse()
            if agent_id and provider_id:
                link = self.with_context(active_test=False).search([
                    ('agent_id', '=', agent_id),
                    ('provider_id', '=', provider_id),
                ], limit=1)
            if link:
                upd = {k: v for k, v in vals.items()
                       if k not in ('agent_id', 'provider_id')}
                if not link.active:
                    upd['active'] = True
                if upd:
                    link.write(upd)
                result |= link
            else:
                result |= super().create([vals])
        return result

    _sql_constraints = [
        (
            'agent_provider_uniq',
            'unique(agent_id, provider_id)',
            'A provider can only appear once per agent.',
        ),
    ]
