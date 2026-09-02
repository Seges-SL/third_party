# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
# ai.context — reusable knowledge directives (prompts) for AI agents.

import json
import os
import re
import zipfile
import io
from datetime import datetime
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
from ..utils import mcp_ui as pns_ui
from ..utils import context_roles
from ..utils.import_export_guard import ensure_ai_admin
from ..utils.knowledge_ownership import (
    apply_create_ownership,
    assert_writer_can_write_records,
    filter_visible_records,
    ownership_read_domain,
)
from ..utils.orm_domain import (
    alias_name_leaves,
    domain_has_my_locale_filter,
    rewrite_my_locale_domain,
)
import logging

_logger = logging.getLogger(__name__)


class AIContext(models.Model):
    """AI Context — reusable knowledge directive for LLM agents.

    Part of the 3-model architecture:
        ai.provider  →  LLM infrastructure (endpoint, API key)
        ai.agent     →  Orchestrator (provider cascade + context set)
        ai.context   →  **This model.** A snippet of knowledge or instruction
                         that can be assigned to one or more agents.

    What a context is:
        A single, self-contained piece of information that an LLM needs to know.
        Examples: HR payroll rules, accounting glossary, formatting conventions,
        corporate terminology, system prompt protocol.

    Context types (single dimension):
        context_type='core'        →  System contexts. Auto-injected into ALL
                                      agents. Not editable by users.
                                      Examples: system_prompt, protocol.
        context_type='domain'      →  Domain knowledge + behavioural rules.
                                      Assigned to agents/profiles via M2M.
                                      MAY have locale variants (explicit
                                      ``locale`` field) when the *content itself*
                                      differs by country (e.g., different tax rules,
                                      different algorithms, different ERP
                                      artefacts). This is NOT translation —
                                      it is localized business logic.
                                      Examples: accounting, hr_payroll_es_ES.
        context_type='locale'      →  Pure linguistic adaptation: terminology
                                      mappings, formatting conventions, number
                                      and date formats. ALWAYS regional.
                                      The knowledge is the same; only the
                                      language/expression changes.
                                      Examples: corporate_terms_es_ES.

    IMPORTANT — Domain locale ≠ Locale (linguistic):
        Both scope content to a locale, but solve different problems:
        • domain + locale = different CONTENT per country (rules, artefacts)
        • locale          = same content expressed in another LANGUAGE
        This is NOT duplication. Do not merge them.

    Explicit locale (no magic parsing):
        The locale is an EXPLICIT attribute (``locale`` field), sourced from the
        file metadata (``<locale_code>`` / front-matter ``locale``). It is never
        inferred by regex-parsing the code suffix. ``base_code`` is derived
        deterministically from ``code`` + ``locale``. Mixing files therefore
        never creates ambiguity: each file declares its own locale.

    Locale resolution:
        Variants sharing a ``base_code`` are collapsed to one: the record whose
        ``locale`` matches the user wins, else the language-neutral one
        (``locale`` empty). Language-neutral contexts are always included.

    Key fields:
        code          Unique identifier (snake_case). Locale-agnostic identity.
        locale        Explicit locale (e.g. es_ES) or empty for neutral.
        base_code     Pristine base without locale (derived, stored).
        content       The actual text/markdown injected into the LLM prompt.
        context_type  'core' | 'domain' | 'locale'

    Key methods:
        assemble_context_parts(contexts, user_locale) → list[str]
            Resolve locale, deduplicate, order by priority, return text parts.
        get_formatting_conventions(user_locale) → str
            Return locale-specific formatting rules.

    Example — creating a context and assigning it to an agent::

        ctx = env['ai.context'].create({
            'code': 'hr_vacation_policy',
            'content': 'Employees get 22 vacation days per year...',
            'context_type': 'domain',
        })
        agent = env['ai.agent'].search([('code', '=', 'pns_ai_chatboo')])
        agent.write({'context_ids': [(4, ctx.id)]})
    """
    _name = 'ai.context'
    _description = 'AI Context'
    _rec_name = 'code'
    _order = 'code'
    
    _sql_constraints = [
        ('code_uniq', 'unique (code)', 'Code must be unique!'),
    ]

    code = fields.Char(
        string='Code',
        required=True,
        help='Unique identifier in snake_case (e.g.: glossary_accounting). Locale is '
             'NOT inferred from the code: it lives in the explicit "locale" field. '
             'A trailing _aa_AA is still allowed for readability (e.g.: '
             'decimals_and_separators_es_ES) but is not what determines the locale.'
    )

    description = fields.Text(
        string='Description',
        help='Context description and usage instructions'
    )
    
    author = fields.Char(
        string='Author',
        help='Context author (extracted from file metadata)'
    )
    
    version = fields.Char(
        string='Version',
        help='Context version (extracted from file metadata)'
    )
    
    date_modified = fields.Date(
        string='Date Modified',
        help='Last modification date (extracted from file metadata)'
    )
    
    content = fields.Text(
        string='Content',
        required=True,
        help='Prompt/Context content (Markdown or Python format)'
    )

    active = fields.Boolean(
        string='Active',
        default=True,
        help='If unchecked, it will not be used in MCP responses'
    )

    # Authoritative agent↔context relation: the reverse of ai.agent.context_ids
    # (same M2M table). A context can compose the prompt of several agents.
    agent_ids = fields.Many2many(
        'ai.agent',
        'ai_agent_context_rel',
        'context_id',
        'agent_id',
        string='Agents',
        help='Agents that include this context in their prompt composition.',
    )

    # ── Context type (single dimension taxonomy) ──
    # context_type is a COMPOSITION ROLE, not just an injection policy.
    # core/domain/locale inject their content; ``discovery`` never injects: the
    # engine reads it as the routing map that builds the dynamic bundle.
    # Role values live in ``utils/context_roles.py`` — the single source of
    # truth for inject/assemble/agent-link decisions. Keep labels here.
    context_type = fields.Selection(
        selection=context_roles.TYPE_SELECTION,
        string='Type',
        default=context_roles.DOMAIN,
        required=True,
        help='Stored and shown as the English hub token: core / domain / '
             'locale / discovery. Not a translated label (those collide with '
             'other fields named Domain / Locale).',
    )

    # ── Discovery role fields (only meaningful for context_type='discovery') ──
    # A discovery row is one routing entry: which target to apply when the user
    # message matches ``discovery_triggers``. Effect depends on target_kind.
    discovery_target_kind = fields.Selection(
        [
            ('domain', 'Domain pack'),
            ('api_server', 'External API server'),
            ('url_whitelist', 'URL whitelist'),
        ],
        string='Discovery target kind',
        default='domain',
        required=True,
        help='What a trigger hit does: load a domain pack (cap 1–2), hint '
             'api_call for an external server (cheap), or (phase 2) hint a '
             'whitelisted URL. Same channel; different payload.',
    )
    discovery_target = fields.Char(
        string='Discovery target',
        index=True,
        help='Target code for this routing entry: a DOMAIN context code, an '
             'ai.api.server code, or (phase 2) a whitelist id. Domain targets '
             'must not be core.',
    )
    api_server_id = fields.Many2one(
        'ai.api.server',
        string='External API server',
        ondelete='cascade',
        index=True,
        help='When set, this Discovery row is owned by the server: archived '
             'or deleted with it. target_kind is api_server; target is the '
             'server code.',
    )
    discovery_triggers = fields.Text(
        string='Discovery triggers',
        help='JSON array or one trigger per line (locale-specific vocabulary). '
             'Matched case-insensitively, accent-folded, whole-word-ish.',
    )
    discovery_priority = fields.Integer(
        string='Discovery priority',
        default=0,
        help='Tie-break when trigger scores are equal (higher wins).',
    )
    discovery_soft_depends = fields.Char(
        string='Discovery soft depends',
        help='Comma-separated extra domain codes loaded alongside the target '
             'on a match (same turn budget).',
    )

    # Localización: atributo EXPLÍCITO (no se infiere del code).
    # Se puebla desde el metadato <locale_code> del fichero on-disk / front-matter.
    # Así el locale viaja CON el contenido: mezclar ficheros no crea ambigüedad.
    locale = fields.Char(
        string='Locale',
        index=True,
        help='Explicit locale of this context (e.g. es_ES). Empty = language-neutral. '
             'Sourced from the file metadata (<locale_code>), never inferred from the code.',
    )

    # Base prístina sin locale (e.g. corporate_terms). Derivada de forma
    # DETERMINISTA de code + locale explícito (no hay regex que "adivine" el locale).
    base_code = fields.Char(
        string='Base code',
        compute='_compute_base_code',
        store=True,
        index=True,
        help='Pristine base identifier without the locale suffix (e.g. corporate_terms). '
             'Derived deterministically from code + explicit locale.',
    )

    @api.depends('code', 'locale')
    def _compute_base_code(self):
        for record in self:
            code = record.code or ''
            loc = record.locale or ''
            if loc and code.endswith('_' + loc):
                record.base_code = code[: -(len(loc) + 1)]
            else:
                record.base_code = code

    @api.depends('code', 'source_module')
    @api.depends_context('composition_agent_id', 'active_id', 'active_model')
    def _compute_composition_link(self):
        agent = self.env['ai.agent'].composition_agent_from_env()
        locked = agent._required_context_codes_set() if agent else set()
        shown = set(agent._link_origins_shown()) if agent else None
        for rec in self:
            if not agent:
                rec.composition_origin = False
                rec.composition_locked = False
                rec.link_visible = True
                continue
            rec.composition_origin = agent.composition_origin_for(
                rec.code, rec.source_module, kind='context',
            )
            rec.composition_locked = rec.code in locked
            rec.link_visible = rec.composition_origin in shown

    def _search_composition_origin(self, operator, value):
        return self.env['ai.agent']._comodel_origin_search_domain(
            self, 'context', operator, value,
        )

    def _search_link_visible(self, operator, value):
        return self.env['ai.agent']._comodel_link_visible_search_domain(
            self, 'context', operator, value,
        )

    # Module that contributed this context (for factory reset per module)
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
        compute='_compute_composition_link',
        search='_search_composition_origin',
        help='Why this row is on the current agent. native: this agent file. '
             'imported: other module in the XML seed. pinned: other module '
             'pinched onto this agent. extra: not in the recipe (user / slash). '
             'Empty source_module is extra.',
    )
    link_visible = fields.Boolean(
        compute='_compute_composition_link',
        search='_search_link_visible',
    )
    composition_locked = fields.Boolean(
        string='Locked',
        compute='_compute_composition_link',
        help='Required on this agent; Defaults and unlink put it back.',
    )

    owner_id = fields.Many2one(
        'res.users',
        string='Owner',
        index=True,
        ondelete='set null',
        help='User who owns this context. Empty for module/import knowledge.',
    )
    @api.model
    def fields_get(self, allfields=None, attributes=None):
        """Type and origin labels are tokens, never translated."""
        res = super().fields_get(allfields=allfields, attributes=attributes)
        info = res.get('context_type')
        if info and info.get('selection'):
            info['selection'] = list(context_roles.TYPE_SELECTION)
        origin = res.get('composition_origin')
        if origin and origin.get('selection'):
            from .ai_agent import COMPOSITION_ORIGIN_SELECTION
            origin['selection'] = list(COMPOSITION_ORIGIN_SELECTION)
        return res

    @api.model
    def ownership_read_domain(self, user=None):
        return ownership_read_domain(user or self.env.user)

    @api.model
    def filter_visible_for_user(self, records, user=None):
        return filter_visible_records(records, user=user or self.env.user)

    @api.model_create_multi
    def create(self, vals_list):
        prepared = []
        for vals in vals_list:
            vals = dict(vals)
            self._apply_detection_defaults(vals)
            prepared.append(
                apply_create_ownership(vals, self.env, module_markers=('source_module',))
            )
        return super(AIContext, self).create(prepared)

    @api.model
    def _apply_detection_defaults(self, vals):
        """Fill discovery identity when a row targets an API server.

        ``api_server_id`` may be omitted: a propose-create from Chatboo only
        has the catalogue ``code`` (``discovery_target``). Looking up the
        server here keeps RelaxAICode off ``ai.api.server``.
        """
        from ..utils.domain_index import (
            TARGET_KIND_API_SERVER,
            detection_row_code,
        )
        server = None
        server_id = vals.get('api_server_id')
        if server_id:
            server = self.env['ai.api.server'].browse(server_id)
            if not server.exists():
                server = None
        kind = (vals.get('discovery_target_kind') or '').strip()
        target = (vals.get('discovery_target') or '').strip()
        if (
            server is None
            and kind == TARGET_KIND_API_SERVER
            and target
            and 'ai.api.server' in self.env
        ):
            server = self.env['ai.api.server'].sudo().search(
                [('code', '=', target)], limit=1,
            )
            if server:
                vals['api_server_id'] = server.id
        if not server:
            return vals
        vals.setdefault('context_type', context_roles.DISCOVERY)
        vals.setdefault('discovery_target_kind', TARGET_KIND_API_SERVER)
        vals.setdefault('discovery_target', server.code)
        vals.setdefault('active', server.active)
        vals['code'] = detection_row_code(server.code, vals.get('locale') or '')
        if not (vals.get('content') or '').strip():
            vals['content'] = (
                '[discovery routing — not injected]\n'
                'target_kind: api_server\n'
                'target: %s\n' % (server.code or '')
            )
        if not vals.get('description'):
            vals['description'] = (
                'Discovery routing for external server %s' % (server.code or '')
            )
        return vals

    def _register_hook(self):
        """After ``-u``, re-seed factory knowledge when module versions change.

        ``post_init_hook`` only runs on install. Registry load compares a stamp
        of knowledge-module versions and calls the same sync (factory overwrite,
        user-owned rows skipped).
        """
        super()._register_hook()
        try:
            from odoo.addons.pns_ai_mcp import hooks as mcp_hooks
            mcp_hooks.maybe_sync_factory_knowledge(
                self.env, reason='registry_hook',
            )
        except Exception:
            _logger.warning(
                'MCP: factory knowledge registry hook failed', exc_info=True,
            )

    @api.model
    def _factory_discovery_stems_on_disk(self):
        """JSON stems under ``ai/contexts/discovery/`` of installed addons."""
        import os

        stems = set()
        for _mod, ctx_dir in self._get_context_source_paths():
            disc = os.path.join(ctx_dir, 'discovery')
            if not os.path.isdir(disc):
                continue
            for filename in os.listdir(disc):
                if filename.endswith('.json'):
                    stems.add(os.path.splitext(filename)[0])
        return stems

    @api.model
    def _default_import_agent(self):
        """Fallback agent used to attach imported contexts when none is given."""
        agent = self.env.ref('pns_ai_mcp.ai_agent_mcp', raise_if_not_found=False)
        if not agent:
            agent = self.env.ref('pns_ai_chatboo.ai_agent_chatboo', raise_if_not_found=False)
        if agent:
            return agent
        return self.env['ai.agent'].search([], limit=1, order='sequence')

    # Size fields for token optimization visibility
    content_size_bytes = fields.Integer(
        string='Size (bytes)',
        compute='_compute_content_sizes',
        store=False,
        help='Total size of content including metadata'
    )
    
    content_size_without_metadata = fields.Integer(
        string='Size without Metadata (bytes)',
        compute='_compute_content_sizes',
        store=False,
        help='Size sent to LLM (metadata stripped)'
    )
    
    metadata_overhead_bytes = fields.Integer(
        string='Metadata Overhead (bytes)',
        compute='_compute_content_sizes',
        store=False,
        help='Token savings from metadata stripping'
    )
    
    @api.depends('content')
    def _compute_content_sizes(self):
        """
        Calculate content size metrics.
        Uses shared utility to ensure exact match with what LLM receives.
        """
        from odoo.addons.pns_ai_mcp.utils.context_utils import strip_xml_metadata
        
        for record in self:
            if not record.content:
                record.content_size_bytes = 0
                record.content_size_without_metadata = 0
                record.metadata_overhead_bytes = 0
                continue
            
            # Total size (with metadata)
            total_size = len(record.content.encode('utf-8'))
            record.content_size_bytes = total_size
            
            # Size without metadata (EXACT - what LLM actually receives)
            cleaned_content = strip_xml_metadata(record.content)
            size_without_metadata = len(cleaned_content.encode('utf-8'))
            record.content_size_without_metadata = size_without_metadata
            
            # Overhead (metadata bytes)
            record.metadata_overhead_bytes = total_size - size_without_metadata

    @api.model
    def get_formatting_conventions(self, user_locale=None):
        """
        Extract technical formatting conventions from the 'corporate_terms'
        context resolved for the user's locale (via get_context_for_country).
        
        Args:
            user_locale (str): Locale code (e.g., 'es_ES', 'de_DE').
            
        Returns:
            dict: {thousands_sep, decimal_sep, date_format, csv_sep} or empty dict if not found.
        """
        if not user_locale:
            user_locale = self.env.context.get('lang', 'en_US')
            
        # 1. Search for the translation context for this locale
        context_record = self.get_context_for_country('corporate_terms', user_locale=user_locale)
        
        if not context_record or not context_record.content:
            return {}
            
        content = context_record.content
        import re
        
        # 2. Extract formatting_conventions block for this locale
        # Pattern matches: <formatting_conventions locale="XX_XX"> ... </formatting_conventions>
        block_pattern = f'<formatting_conventions[^>]*locale=["\']{user_locale}["\'][^>]*>(.*?)</formatting_conventions>'
        block_match = re.search(block_pattern, content, re.DOTALL)
        
        if not block_match:
            # Try without locale attribute check if it's the only block
            block_match = re.search(r'<formatting_conventions[^>]*>(.*?)</formatting_conventions>', content, re.DOTALL)
            
        if not block_match:
            return {}
            
        block_content = block_match.group(1)
        
        # 3. Extract individual tags
        result = {}
        patterns = {
            'decimal_sep': r'<decimal_separator[^>]*>(.*?)</decimal_separator>',
            'thousands_sep': r'<thousands_separator[^>]*>(.*?)</thousands_separator>',
            'date_format': r'<date_format[^>]*>(.*?)</date_format>',
            'csv_sep': r'<csv_field_separator[^>]*>(.*?)</csv_field_separator>',
        }
        
        for key, pattern in patterns.items():
            match = re.search(pattern, block_content, re.DOTALL)
            if match:
                val = match.group(1).strip()
                # Special case for date_format: convert DD/MM/YYYY to %d/%m/%Y for Python
                if key == 'date_format':
                    val = val.replace('DD', '%d').replace('MM', '%m').replace('YYYY', '%Y')
                    val = val.replace('HH', '%H').replace('SS', '%S') # Basic time sync
                    
                result[key] = val
                
        return result

    @api.model
    def get_context_for_country(self, base_code, user_locale=None):
        """
        Smart loading by EXPLICIT fields: locale-specific first, else neutral.

        Resolution keys off the stored ``base_code`` + ``locale`` fields, never
        off the code string. The trailing ``_es_ES`` you may see in a code is
        cosmetic; it is not what selects the variant.

        Args:
            base_code (str): Pristine base identifier (e.g. 'hr_payroll',
                'corporate_terms') — the value stored in the ``base_code`` field.
            user_locale (str, optional): Locale code (es_ES, fr_FR). Auto-detected
                from the user context if None.

        Returns:
            recordset: the record with (base_code, locale=user_locale) if present,
            else the language-neutral record (base_code, locale empty). A lazy
            on-disk lookup sits between the two as a fallback.

        Strategy:
            1. search([('base_code','=',base_code), ('locale','=',user_locale)])
            2. lazy disk discovery (file named base_code_user_locale.xml)
            3. search([('base_code','=',base_code), ('locale','in',[False,''])])

        Example:
            get_context_for_country('hr_payroll', 'es_ES')
            # → record whose locale == 'es_ES', else the neutral hr_payroll.
        """
        # Auto-detect locale from user context
        user_locale = self._normalize_user_locale(user_locale)
        
        # 1. Try locale-specific context via EXPLICIT base_code + locale fields.
        locale_specific = self.search([
            ('base_code', '=', base_code),
            ('locale', '=', user_locale),
            ('active', '=', True),
        ], limit=1)
        
        if locale_specific:
            return locale_specific
            
        # 1.5 LAZY DISK DISCOVERY (On-Demand)
        # If not in DB, try to find on disk dynamically before falling back using convention.
        # Pattern: ai/contexts/custom/{category}/{base_code}/{base_code}_{user_locale}.xml
        try:
            import os
            from ..utils.ai_paths import module_kind_dir
            _module_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            target_filename = '%s_%s.xml' % (base_code, user_locale)
            _ctx_dir = module_kind_dir(_module_root, 'contexts')
            root_search_path = os.path.join(_ctx_dir, 'custom') if _ctx_dir else None
            found_path = None
            
            if root_search_path and os.path.exists(root_search_path):
                for root, dirs, files in os.walk(root_search_path):
                    if target_filename in files:
                        found_path = os.path.join(root, target_filename)
                        break
            
            if found_path:
                with open(found_path, 'r', encoding='utf-8') as f:
                    raw_content = f.read()
                    from collections import namedtuple
                    VirtualRecord = namedtuple('VirtualRecord', ['code', 'content', 'description'])
                    variant_code = '%s_%s' % (base_code, user_locale)
                    _logger.info("MCP: Lazy Loaded '%s' from disk - %s", variant_code, found_path)
                    return VirtualRecord(code=variant_code, content=raw_content, description="Lazy Loaded %s" % base_code)
        except Exception as e:
            _logger.error("MCP: Error lazy loading on-demand %s: %s", base_code, e)

        # 2. Fallback to the language-neutral base context (explicit fields).
        generic = self.search([
            ('base_code', '=', base_code),
            ('locale', 'in', [False, '']),
            ('active', '=', True),
        ], limit=1)
        
        # Fallback a contexto pelao (sin locale): válido para cualquier locale
        return generic

    @api.model
    def _normalize_user_locale(self, user_locale=None):
        if not user_locale:
            user_locale = self.env.context.get('lang', 'en_US')
        return str(user_locale).replace('-', '_')

    @api.model
    def get_listable_for_mcp(self):
        """Return the contexts advertised via the standard MCP primitives.

        One record per ``base_code`` (locale variants collapsed), restricted to
        ``core`` + ``domain`` types — the selectable knowledge an MCP client can
        load. Pure ``locale`` contexts (linguistic glue) are internal adaptation,
        not user-selectable, so they are excluded.

        Shared by ``prompts/list`` and ``resources/list`` so both primitives
        advertise exactly the same catalogue as the ``get_context`` tool index.
        """
        from ..utils.agent_identity import is_identity_pack_code
        contexts = self.search([
            ('active', '=', True),
            ('context_type', 'in', list(context_roles.MCP_LISTABLE_TYPES)),
        ], order='context_type, code')
        seen = set()
        result = self.browse()
        for ctx in contexts:
            base = ctx.base_code or ctx.code
            if is_identity_pack_code(ctx.code) or is_identity_pack_code(base):
                continue
            if base in seen:
                continue
            seen.add(base)
            result |= ctx
        return result

    @api.model
    def _virtual_map_from_contexts(self, contexts):
        """Group contexts by explicit base_code with generic + locale variants."""
        virtual_map = {}
        for ctx in contexts:
            if not ctx.active:
                continue
            # VirtualContext objects (lazy disk discovery) have no context_type/
            # base_code/locale; default gracefully.
            ctx_type = getattr(ctx, 'context_type', None) or 'domain'
            base_code = getattr(ctx, 'base_code', None) or ctx.code
            loc = getattr(ctx, 'locale', None)
            variant_key = loc if loc else 'generic'
            virtual_map.setdefault(base_code, {
                'context_type': ctx_type,
                'variants': {},
            })
            virtual_map[base_code]['variants'][variant_key] = ctx
        return virtual_map

    @api.model
    def _lazy_load_locale_variants(self, virtual_map, user_locale):
        """Add on-disk locale variants for composed bases (domain/locale)."""
        import os
        from ..utils.ai_paths import module_kind_dir

        module_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        _ctx_dir = module_kind_dir(module_root, 'contexts')
        root_search_path = os.path.join(_ctx_dir, 'custom') if _ctx_dir else None
        if not root_search_path or not os.path.exists(root_search_path):
            return

        for base_code, data in virtual_map.items():
            if user_locale in data['variants']:
                continue
            if data['context_type'] not in ('domain', 'locale'):
                continue
            target_filename = '%s_%s.xml' % (base_code, user_locale)
            found_path = None
            for root, dirs, files in os.walk(root_search_path):
                if target_filename in files:
                    found_path = os.path.join(root, target_filename)
                    break
            if not found_path:
                continue
            try:
                with open(found_path, 'r', encoding='utf-8') as f:
                    raw_content = f.read()

                class VirtualContext:
                    def __init__(self, code, content):
                        self.code = code
                        self.content = content

                virtual_code = '%s_%s' % (base_code, user_locale)
                data['variants'][user_locale] = VirtualContext(virtual_code, raw_content)
            except Exception:
                pass

    @api.model
    def _pick_resolved_variant(self, data, user_locale):
        """Return the single winning context for a virtual_map entry."""
        variants = data['variants']
        if user_locale in variants:
            return variants[user_locale]
        if 'generic' in variants:
            return variants['generic']
        if data['context_type'] == 'locale' and 'en_US' in variants:
            return variants['en_US']
        if len(variants) == 1:
            return next(iter(variants.values()))
        return None

    @api.model
    def _resolve_parts_from_virtual_map(self, virtual_map, user_locale):
        """Pick one stripped content part per base_code (locale-aware)."""
        from odoo.addons.pns_ai_mcp.utils.context_utils import strip_xml_metadata

        context_parts = []
        type_priority = ['core', 'locale', 'domain']
        for ctype in type_priority:
            bases_in_type = [
                (base, data) for base, data in virtual_map.items()
                if data['context_type'] == ctype
            ]
            bases_in_type.sort(key=lambda item: item[0])
            for base_code, data in bases_in_type:
                target_ctx = self._pick_resolved_variant(data, user_locale)
                if not target_ctx:
                    continue
                try:
                    context_parts.append(strip_xml_metadata(target_ctx.content))
                except Exception:
                    continue
        return context_parts

    @api.model
    def get_composition_stats(self, contexts, user_locale=None):
        """
        Type sizes/counts aligned with assemble_context_parts (locale dedup).
        Includes library totals for comparison with the raw inventory in DB.
        """
        from odoo.addons.pns_ai_mcp.utils.context_utils import strip_xml_metadata

        user_locale = self._normalize_user_locale(user_locale)
        empty_types = {
            'core': {'count': 0, 'size_raw': 0, 'size_optimized': 0},
            'domain': {'count': 0, 'size_raw': 0, 'size_optimized': 0},
            'locale': {'count': 0, 'size_raw': 0, 'size_optimized': 0},
        }
        stats = {
            'user_locale': user_locale,
            'categories': {k: dict(v) for k, v in empty_types.items()},
            'total_count': 0,
            'total_size_raw': 0,
            'total_size_optimized': 0,
            'library_count': len(contexts),
            'library_size_raw': sum(c.content_size_bytes for c in contexts),
            'library_size_optimized': sum(c.content_size_without_metadata for c in contexts),
        }
        virtual_map = self._virtual_map_from_contexts(contexts)
        self._lazy_load_locale_variants(virtual_map, user_locale)
        for ctype in ['core', 'locale', 'domain']:
            for base_code in sorted(
                base for base, data in virtual_map.items() if data['context_type'] == ctype
            ):
                target_ctx = self._pick_resolved_variant(virtual_map[base_code], user_locale)
                if not target_ctx:
                    continue
                content = target_ctx.content or ''
                raw = len(content.encode('utf-8'))
                try:
                    optimized = len(strip_xml_metadata(content).encode('utf-8'))
                except Exception:
                    optimized = raw
                stats['categories'][ctype]['count'] += 1
                stats['categories'][ctype]['size_raw'] += raw
                stats['categories'][ctype]['size_optimized'] += optimized
                stats['total_count'] += 1
                stats['total_size_raw'] += raw
                stats['total_size_optimized'] += optimized
        return stats

    @api.model
    def assemble_context_parts(self, contexts, user_locale=None):
        """
        Build stripped content parts for a context set with locale deduplication.
        One resolved variant per base_code (same rules as discovery content).
        """
        user_locale = self._normalize_user_locale(user_locale)
        virtual_map = self._virtual_map_from_contexts(contexts)
        self._lazy_load_locale_variants(virtual_map, user_locale)
        return self._resolve_parts_from_virtual_map(virtual_map, user_locale)

    # ── Discover role: domain-index routing composed from DB (locale-aware) ──

    @api.model
    def _discovery_parse_triggers(self, raw):
        """Trigger list from a discovery row (JSON array, or csv fallback)."""
        if not raw:
            return []
        try:
            data = json.loads(raw)
            if isinstance(data, list):
                return [str(t).strip() for t in data if str(t).strip()]
        except (ValueError, TypeError):
            pass
        text = str(raw)
        if '\n' in text:
            return [t.strip() for t in text.splitlines() if t.strip()]
        return [t.strip() for t in text.split(',') if t.strip()]

    @api.model
    def _discovery_core_codes(self):
        """Codes/base_codes that are core → never a valid discovery target."""
        core = self.with_context(active_test=False).search([
            ('context_type', '=', context_roles.CORE),
        ])
        codes = set()
        for c in core:
            codes.add(c.code)
            if c.base_code:
                codes.add(c.base_code)
        return codes

    @api.model
    def _active_api_server_codes(self):
        """Codes of active external servers (empty if the model is missing)."""
        if 'ai.api.server' not in self.env:
            return set()
        return set(
            self.env['ai.api.server'].sudo().search([('active', '=', True)]).mapped('code')
        )

    @api.model
    def get_discovery_entries(self, user_locale=None):
        """Compose the routing index from ``context_type='discovery'`` rows.

        One entry per ``base_code``. Priority and ``soft_depends`` come from
        the locale row when it exists, else the generic (English / technical)
        row. Triggers of a spoken locale variant (shipped: ``es_ES``) are
        **unioned** with the generic set so both ``mapa`` and ``geocode``
        fire; other locales (``en_US``, ``fr_FR``, …) hear only the generic
        set. Domain targets resolving to ``core`` and ``api_server`` targets
        whose server is missing/inactive are skipped.
        Output::

            [{'code': <target>, 'target_kind': 'domain'|'api_server'|...,
              'triggers': [...], 'priority': int, 'soft_depends': [...]}, ...]
        """
        from ..utils.domain_index import (
            TARGET_KIND_DOMAIN,
            compose_discovery_entries,
            merge_trigger_lists,
        )
        user_locale = self._normalize_user_locale(user_locale)
        rows = self.with_context(active_test=False).search([
            ('context_type', '=', context_roles.DISCOVERY),
            ('active', '=', True),
        ])
        by_base = {}
        for rec in rows:
            base = rec.base_code or rec.code
            by_base.setdefault(base, {})[rec.locale or 'generic'] = rec
        core_codes = self._discovery_core_codes()
        collapsed = []
        for base in sorted(by_base):
            variants = by_base[base]
            generic = variants.get('generic')
            spoken = variants.get(user_locale) if user_locale else None
            rec = spoken or generic or next(iter(variants.values()))
            target = (rec.discovery_target or '').strip()
            kind = rec.discovery_target_kind or TARGET_KIND_DOMAIN
            if kind == TARGET_KIND_DOMAIN and target in core_codes:
                _logger.warning(
                    'discovery: %s targets core code %s — skipped',
                    rec.code, target,
                )
            soft = [
                c.strip()
                for c in (rec.discovery_soft_depends or '').split(',')
                if c.strip()
            ]
            rec_triggers = self._discovery_parse_triggers(rec.discovery_triggers)
            if spoken and generic:
                gen_triggers = self._discovery_parse_triggers(
                    generic.discovery_triggers,
                )
                triggers = merge_trigger_lists(gen_triggers, rec_triggers)
            else:
                triggers = rec_triggers
            collapsed.append({
                'target': target,
                'target_kind': kind,
                'triggers': triggers,
                'priority': int(rec.discovery_priority or 0),
                'soft_depends': soft,
                'source_module': rec.source_module or '',
            })
        return compose_discovery_entries(
            collapsed,
            core_codes=core_codes,
            active_server_codes=self._active_api_server_codes(),
        )

    @api.model
    def get_discovery_indexed_codes(self, user_locale=None):
        """All turn-scoped domain codes (targets + soft_depends) from discovery."""
        from ..utils.domain_index import indexed_codes_from_entries
        return indexed_codes_from_entries(self.get_discovery_entries(user_locale))

    @api.model
    def get_canonical_contexts_for_agent(self, agent=None):
        """One library record per base_code; prefer the neutral one (locale empty).

        If ``agent`` is given, scope to its composed contexts (the M2M
        ``agent.context_ids``); otherwise consider the whole active catalog.
        """
        if agent:
            contexts = agent.context_ids.filtered('active').sorted(
                key=lambda c: (c.context_type or '', c.code)
            )
        else:
            contexts = self.search(
                [('active', '=', True),
                 ('context_type', '!=', context_roles.DISCOVERY)],
                order='context_type, code',
            )
        by_base = {}
        for ctx in contexts:
            base = ctx.base_code or ctx.code
            if base not in by_base:
                by_base[base] = ctx
                continue
            current = by_base[base]
            if not current.locale and ctx.locale:
                continue
            if current.locale and not ctx.locale:
                by_base[base] = ctx
        return self.browse([ctx.id for ctx in by_base.values()])

    @api.model
    def normalize_context_ids(self, context_ids):
        """Collapse locale siblings to one canonical record per base_code."""
        contexts = context_ids.filtered('active') if hasattr(context_ids, 'filtered') else self.browse(context_ids)
        if not contexts:
            return []
        by_base = {}
        for ctx in contexts:
            base = ctx.base_code or ctx.code
            by_base.setdefault(base, self.env['ai.context'])
            by_base[base] |= ctx
        canonical_ids = []
        for base, members in by_base.items():
            generic = members.filtered(lambda c: not c.locale)
            if generic:
                canonical_ids.append(generic[0].id)
                continue
            if len(members) == 1:
                canonical_ids.append(members[0].id)
                continue
            # No generic among the members: look up the canonical generic
            # (code == base) in the active catalog, else pick deterministically.
            catalog_generic = self.search(
                [('active', '=', True), ('code', '=', base)], limit=1,
            )
            if catalog_generic:
                canonical_ids.append(catalog_generic.id)
            else:
                canonical_ids.append(sorted(members, key=lambda c: c.code)[0].id)
        return canonical_ids

    def family_context_ids(self):
        """All active contexts sharing this record's base_code."""
        self.ensure_one()
        base = self.base_code or self.code
        active_contexts = self.search([('active', '=', True)])
        return active_contexts.filtered(
            lambda c: (c.base_code or c.code) == base
        ).ids
    
    # Locale → human-readable language name (written in that language). Used to
    # resolve the single dynamic language directive shared across assemblers.
    _LOCALE_LANG_NAMES = {
        'es_ES': 'español', 'es_MX': 'español (México)', 'es_AR': 'español (Argentina)',
        'es_CO': 'español (Colombia)', 'en_US': 'English', 'en_GB': 'English',
        'fr_FR': 'français', 'de_DE': 'Deutsch', 'it_IT': 'italiano',
        'pt_PT': 'português', 'pt_BR': 'português (Brasil)', 'nl_NL': 'Nederlands',
        'ca_ES': 'català', 'eu_ES': 'euskara', 'gl_ES': 'galego',
    }

    @api.model
    def build_language_directive(self, user_locale):
        """Single source for the runtime language directive.

        This is DATA injection (the resolved user language), not a hardcoded
        context rule: the canonical LANGUAGE rule lives in system_prompt.xml.
        We only resolve the human-readable language name for the current
        locale so weaker models get an explicit, unambiguous instruction.
        Placed LAST by callers so it benefits from recency bias.
        """
        lang_name = self._LOCALE_LANG_NAMES.get(user_locale, user_locale)
        return (
            f"MANDATORY LANGUAGE RULE: You MUST always respond in {lang_name} "
            f"({user_locale}). This rule applies to ALL your messages, tool "
            f"descriptions, explanations, errors, and any other output. Never "
            f"switch to another language unless the user explicitly writes to "
            f"you in that language first."
        )

    @api.model
    def _injectable_active_contexts(self):
        """Active contexts whose content can enter a prompt (never ``discovery``)."""
        return self.search(
            [
                ('active', '=', True),
                ('context_type', 'in', list(context_roles.INJECTABLE_TYPES)),
            ],
            order='context_type, code',
        )

    @api.model
    def _domain_index_inject_enabled(self):
        from ..utils.domain_index import INJECT_ICP_KEY, icp_flag_enabled
        try:
            raw = self.env['ir.config_parameter'].sudo().get_param(
                INJECT_ICP_KEY, 'True',
            )
            return icp_flag_enabled(raw, default=True)
        except Exception:
            return True

    @api.model
    def split_contexts_by_domain_index(self, contexts=None, user_locale=None):
        """Split injectable contexts into always-on vs turn-scoped sets.

        When domain-index inject is OFF, ``turn_scoped`` is empty and
        ``always_on`` is the full injectable set (legacy monolithic cache).
        """
        contexts = contexts if contexts is not None else self._injectable_active_contexts()
        contexts = contexts.filtered(
            lambda c: c.active and context_roles.is_injectable(c.context_type),
        )
        inject = self._domain_index_inject_enabled()
        indexed = set()
        if inject:
            indexed = self.get_discovery_indexed_codes(user_locale)
        if not indexed:
            return contexts, self.browse(), set(), inject

        def _is_indexed(ctx):
            return (ctx.base_code or ctx.code) in indexed or ctx.code in indexed

        always_on = contexts.filtered(lambda c: not _is_indexed(c))
        turn_scoped = contexts.filtered(_is_indexed)
        return always_on, turn_scoped, indexed, inject

    @api.model
    def build_bundle_payload(self, contexts, user_locale=None):
        """Assemble a discovery-shaped payload (header + parts + language rule)."""
        user_locale = self._normalize_user_locale(user_locale)
        context_parts = self.assemble_context_parts(contexts, user_locale=user_locale)
        lang_directive = self.build_language_directive(user_locale)
        header = (
            f"System Configuration: Locale={user_locale} | "
            f"Contexts={len(context_parts)}\n"
        )
        return header + "\n\n".join(context_parts) + "\n\n---\n" + lang_directive

    @api.model
    def get_bundle_payload_size(self, contexts, user_locale=None):
        """UTF-8 byte size of ``build_bundle_payload``."""
        return len(self.build_bundle_payload(contexts, user_locale).encode('utf-8'))

    @api.model
    def get_monolithic_content(self, user_locale=None):
        """Monolithic knowledge bundle (all injectable actives, locale-deduped).

        Legacy max payload. With domain-index inject ON, agent caches are smaller
        (always-on only); use ``split_contexts_by_domain_index`` +
        ``build_bundle_payload`` for the min/max pair in statistics.
        """
        return self.build_bundle_payload(
            self._injectable_active_contexts(),
            user_locale=user_locale,
        )

    @api.model
    def get_stats_by_ids(self, context_ids):
        """
        Composition stats for filtered contexts + always-on / monolithic sizes.
        Used by the tree statistics button.
        """
        user_locale = self.env.context.get('lang', 'en_US')

        if not context_ids:
            contexts = self._injectable_active_contexts()
        else:
            contexts = self.browse(context_ids).filtered(
                lambda c: c.active and context_roles.is_injectable(c.context_type),
            )

        always_on, turn_scoped, indexed, inject = self.split_contexts_by_domain_index(
            contexts, user_locale=user_locale,
        )
        stats = self.get_composition_stats(always_on, user_locale=user_locale)
        stats['cache_size'] = 0
        stats['always_on_cache_size'] = 0
        stats['monolithic_cache_size'] = 0
        stats['inject_enabled'] = inject
        stats['turn_scoped_codes'] = sorted(indexed)
        stats['cache_error'] = False

        try:
            always_size = self.get_bundle_payload_size(always_on, user_locale)
            mono_size = self.get_bundle_payload_size(
                always_on | turn_scoped, user_locale,
            )
            stats['cache_size'] = always_size
            stats['always_on_cache_size'] = always_size
            stats['monolithic_cache_size'] = mono_size
            if always_size == 0 and mono_size == 0:
                stats['cache_error'] = (
                    f"Cache vacío generado para locale {user_locale}"
                )
        except Exception as e:
            _logger.warning(f"Error calculating cache size: {e}")
            stats['cache_size'] = 0
            stats['cache_error'] = str(e)

        return stats
    
    @api.model
    def get_base_context_name(self, code):
        """
        Heuristic strip of a trailing locale from a RAW code STRING.

        Scope: resolving INCOMING request names that have no record yet — e.g.
        the MCP client / LLM asks for 'hr_payroll_ES' and we want the base
        'hr_payroll' to look it up. It is NOT the source of a record's locale:
        stored records expose the explicit ``base_code`` field (use that when
        you hold a record). Kept as a best-effort convenience, not the taxonomy.

        Pattern: removes a trailing _XX, _xx_XX or _xx-XX.
        """
        if not code:
            return code
            
        import re
        
        # Pattern: _ followed by 2 chars, OR _ followed by 2 chars + (_ or -) + 2 chars
        # Supports: _es, _ES, _es_ES, _en_US, _es-ES, etc.
        # Enforced to be at the END of the string.
        pattern = r'_([a-zA-Z]{2}(?:[_-][a-zA-Z]{2})?)$'
        base = re.sub(pattern, '', code)
        
        return base
    
    rel_path = fields.Char(
        string='Relative Path',
        help='Portable path within the cognitive tree, umbrella-agnostic '
             '(e.g. contexts/custom/locale/file.md). On disk the files '
             'live under the module ai/ umbrella (ai/contexts/...).'
    )
    
    # Campos de estadísticas de uso (Fase 6: Monitoreo)
    usage_count = fields.Integer(
        string='Times Consulted',
        default=0,
        readonly=True,
        help='Number of times this context has been consulted via prompts/get or get_context'
    )
    
    last_used = fields.Datetime(
        string='Last Consulted',
        readonly=True,
        help='Date and time when this context was last consulted'
    )

    @api.model
    def _auto_init(self):
        """Load owl1 ``assets.xml`` (Odoo 14 has no manifest assets key)."""
        res = super(AIContext, self)._auto_init()
        from ..utils.compat import load_odoo14_assets_if_needed
        load_odoo14_assets_if_needed(self.env)
        return res

    @api.model
    def _build_module_restore_report_html(self, result, title=None):
        errors = result.get('errors') or []
        imported = result.get('imported', 0)
        updated = result.get('updated', 0)
        title = title or _('System contexts — restore from module')
        status_class, status_icon, status_text, _ntype = pns_ui.derive_operation_status(
            errors,
            imported + updated,
            failed_text=_('Contexts restore failed.'),
            warnings_text=_('Contexts restore completed with warnings.'),
            success_text=_('Contexts restore completed.'),
        )
        return pns_ui.build_operation_report_html(
            title,
            status_text,
            status_class,
            status_icon,
            rows=[
                (_('Contexts imported'), imported),
                (_('Contexts updated'), updated),
                (_('Contexts skipped (not overwritten)'), result.get('skipped', 0)),
            ],
            errors=errors,
        )

    def action_restore_from_module(self, replace_existing=True):
        """
        Restore ALL contexts (system and custom defaults) from module. 
        Only accessible for group_ai_admin.

        replace_existing=True: sobreescribe los contextos cuyo código coincide.
        replace_existing=False: solo añade los que no existen. En ningún caso se
        borra nada de la BD (import = upsert + recuperar; nunca eliminar).
        """
        # Check permissions
        if not self.env.user.has_group('pns_ai_mcp.group_ai_admin'):
            raise UserError(
                _('Only administrators can restore contexts from the module.')
            )
        
        _logger.warning("MCP: Starting manual restoration from module...")
        
        # Call the unified import method with special context to allow overwriting
        result = self.with_context(skip_hardcoded_restrictions=True)._import_all_from_module(
            replace_existing=replace_existing,
        )

        errors = result.get('errors') or []
        _sc, _si, _st, ntype = pns_ui.derive_operation_status(
            errors,
            result['imported'] + result['updated'],
            failed_text=_('Restore failed.'),
            warnings_text=_('Restore completed with warnings.'),
            success_text=_('Restore completed.'),
        )
        message = pns_ui.build_plain_operation_message(
            _('Restore completed'),
            [
                (_("Imported"), result['imported']),
                (_("Updated"), result['updated']),
                (_("Skipped (not overwritten)"), result.get('skipped', 0)),
            ],
            errors=errors,
        )
        return pns_ui.client_notification(
            _("Restore from module"),
            message,
            notification_type=ntype if ntype != 'danger' else 'warning',
        )

    def get_global_stats(self, domain=None):
        """
        Calcula estadísticas detalladas para el diálogo de estadísticas.
        Args:
            domain: Dominio de búsqueda actual (filtros activos en la vista)
        """
        # Si no se pasa dominio, usar uno por defecto (ej: activo por defecto)
        search_domain = domain or []
        
        # 1. Obtener contextos que cumplen el filtro (o todos si no hay filtro activo)
        # Nota: Asumimos que el usuario quiere ver estadísticas de lo que está filtrando
        current_contexts = self.search(search_domain)
        
        # Asegurarnos de que solo contamos activos para las estadísticas REALES de uso
        active_contexts = current_contexts.filtered(lambda r: r.active)
        
        stats = {
            'total_count': len(active_contexts),
            'total_size_raw': 0,
            'total_size_optimized': 0,
            'categories': {
                'core': {'count': 0, 'size_raw': 0, 'size_optimized': 0},
                'domain': {'count': 0, 'size_raw': 0, 'size_optimized': 0},
                'locale': {'count': 0, 'size_raw': 0, 'size_optimized': 0},
            }
        }
        
        for ctx in active_contexts:
            cat = ctx.context_type
            if cat not in stats['categories']:
                cat = 'domain' # Fallback
            
            # Sumar contadores
            stats['categories'][cat]['count'] += 1
            stats['categories'][cat]['size_raw'] += (ctx.content_size_bytes or 0)
            stats['categories'][cat]['size_optimized'] += (ctx.content_size_without_metadata or 0)
            
            # Sumar totales globales
            stats['total_size_raw'] += (ctx.content_size_bytes or 0)
            stats['total_size_optimized'] += (ctx.content_size_without_metadata or 0)

        return stats

    def action_export_selected_zip(self):
        """
        Export selected contexts as ZIP file.
        Can be called from tree view with selected records.
        """
        ensure_ai_admin(self.env)
        if not self:
            return pns_ui.warning_notification(
                _('Export contexts'),
                _('Please select at least one context to export.'),
            )
        
        # Create ZIP in memory
        zip_buffer = io.BytesIO()
        
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            for record in self:
                # Determine extension
                extension = '.md'
                if self._is_python_content(record.content):
                    extension = '.py'
                elif record.content and record.content.strip().startswith('<') and '>' in record.content:
                    extension = '.xml'
                
                filename = f"{record.code}{extension}"
                export_content = self._build_export_content(record, extension)
                
                # Determine folder based on context type (core = system)
                folder = 'system' if record.context_type == 'core' else 'custom'
                zip_path = f"{folder}/{filename}"
                
                zip_file.writestr(zip_path, export_content.encode('utf-8'))
        
        # Create temporary attachment
        zip_buffer.seek(0)
        zip_data = zip_buffer.read()
        zip_buffer.close()
        
        count = len(self)
        zip_filename = pns_ui.build_export_filename(
            self.env, f"contexts_{count}selected", 'zip')
        
        attachment = pns_ui.write_export_attachment(
            self.env, zip_filename, zip_data, 'application/zip',
            res_model='ai.context', res_id=0,
        )
        
        return pns_ui.open_json_export_wizard(
            self.env,
            dialog_title=_('Export selected contexts'),
            summary_text=_('%s context(s) exported to ZIP.') % count,
            count=count,
            attachment=attachment,
        )

    @api.model
    def record_context_usage(self, context_code):
        """Increment usage_count on a short cursor (best-effort).

        Must not write on the Chatboo/ReAct REPEATABLE READ snapshot: other
        MCP clients bump the same rows, and a late flush raises PG 40001.
        """
        if not context_code:
            return
        try:
            with self.env.registry.cursor() as cr:
                cr.execute("SET LOCAL lock_timeout = '2s'")
                cr.execute(
                    """
                    UPDATE ai_context
                       SET usage_count = COALESCE(usage_count, 0) + 1,
                           last_used = (now() at time zone 'UTC'),
                           write_date = (now() at time zone 'UTC')
                     WHERE code = %s
                    """,
                    (context_code,),
                )
                cr.commit()
        except Exception as e:
            _logger.warning(
                "MCP: Error registrando uso de contexto %s: %s",
                context_code, str(e),
            )
    
    @api.model
    def _is_list_domain(self, domain):
        """True when domain is a classic prefix list (not O19 DomainBool/Domain)."""
        return isinstance(domain, (list, tuple))

    @api.model
    def _domain_has_my_locale_filter(self, domain):
        """True when the search-view 'My language' filter chip is active."""
        return domain_has_my_locale_filter(domain)

    @api.model
    def _search(self, domain, *args, **kwargs):
        """
        Sobrescribe _search para:
        1. Respetar active_test del contexto.
        2. Resolver el filtro 'My language' SOLO cuando el usuario lo tiene
           activo en la barra de búsqueda (no por search_default_* en el
           contexto de la acción, que persiste aunque se desactive el chip).
        3. Alias estructural: leaf ``name`` → ``_rec_name`` (este modelo no
           tiene campo name; el LLM / search box suelen usarlo igual).
        """
        # O19+ passes DomainBool/Domain during fields_get groupability probes.
        if not self._is_list_domain(domain):
            return super(AIContext, self)._search(domain, *args, **kwargs)

        domain = alias_name_leaves(
            domain,
            rec_name=self._rec_name or 'code',
            has_name_field='name' in self._fields,
        )

        # Do not strip ('active', …) leaves here: removing a leaf and leaving
        # its ``|``/``&`` breaks prefix arity (Discovery + My language crash).
        # Sustituir el dominio del XML (context.get('lang') no evalúa bien
        # en todos los stacks) por el idioma real — solo si el chip sigue
        # activo. Recovers when Active/No-locale chips leave a short OR-tree.
        if self._domain_has_my_locale_filter(domain):
            user_lang = self._normalize_user_locale(self.env.context.get('lang'))
            domain = rewrite_my_locale_domain(domain, user_lang)

        return super(AIContext, self)._search(domain, *args, **kwargs)

    @api.model
    def action_open_stats_wizard(self):
        """Lanza el wizard de estadísticas globales"""
        return self.env.ref('pns_ai_mcp.action_mcp_context_stats').read()[0]

    @api.model
    def action_import_from_zip(self):
        """Abre el wizard de importación de contextos desde ZIP"""
        ensure_ai_admin(self.env)
        return self.env.ref('pns_ai_mcp.action_context_import_wizard').read()[0]

    @api.constrains('code')
    def _check_code_snake_case(self):
        """Valida que el código esté en formato snake_case con excepción para códigos de locale al final"""
        # Snake_case estándar: solo minúsculas, números y guiones bajos
        # Excepción: permite patrón _aa_AA al final para códigos de locale (ej: _es_ES, _en_US)
        snake_case_standard = re.compile(r'^[a-z][a-z0-9_]*$')
        snake_case_with_locale = re.compile(r'^[a-z][a-z0-9_]*_[a-z]{2}_[A-Z]{2}$')
        for record in self:
            if record.code:
                if not (snake_case_standard.match(record.code) or snake_case_with_locale.match(record.code)):
                    raise ValidationError(
                        'El código debe estar en formato snake_case: '
                        'solo letras minúsculas, números y guiones bajos, empezando con letra. '
                        'Excepción: permite patrón _aa_AA al final para códigos de locale '
                        '(ej: glosario_contabilidad o decimals_and_separators_es_ES)'
                    )

    @api.constrains('code')
    def _check_code_unique(self):
        """Valida que el código sea único"""
        for record in self:
            if record.code:
                duplicates = self.search([
                    ('code', '=', record.code),
                    ('id', '!=', record.id)
                ])
                if duplicates:
                    raise ValidationError(
                        f'El código "{record.code}" ya existe. '
                        'Debe ser único.'
                    )

    def write(self, vals):
        """
        Sobrescribe write para evitar modificar registros hardcodeados.
        Muestra una notificación amigable en lugar de bloquear la acción.
        Permite saltarse la restricción si el contexto tiene skip_hardcoded_restrictions=True
        (usado en procesos de importación/exportación).
        """
        if not self.env.context.get('skip_hardcoded_restrictions'):
            assert_writer_can_write_records(self, self.env)
            if not self.env.user.has_group('pns_ai_mcp.group_ai_admin'):
                if vals.get('context_type') == 'core':
                    raise UserError(_(
                        'Core contexts are read-only for AI Writers.'
                    ))
                if 'owner_id' in vals:
                    raise UserError(_(
                        'Only administrators can change context ownership.'
                    ))
            hardcoded_records = self.filtered(lambda c: c.context_type == 'core')
            if hardcoded_records:
                raise UserError(
                    '⚠️ Registro de solo lectura\n\n'
                    'No se pueden modificar los contextos del sistema (hardcodeados). '
                    'Estos contextos se sincronizan automáticamente desde el código del módulo.'
                )
        res = super(AIContext, self).write(vals)
        if (
            not self.env.context.get('_syncing_detection')
            and {'locale', 'api_server_id'} & set(vals)
        ):
            self._refresh_detection_identity()
        return res

    def _refresh_detection_identity(self):
        """Keep server-owned discovery rows aligned with the linked server."""
        from ..utils.domain_index import (
            TARGET_KIND_API_SERVER,
            detection_row_code,
        )
        for rec in self:
            server = rec.api_server_id
            if not server:
                continue
            updates = {}
            if rec.discovery_target != server.code:
                updates['discovery_target'] = server.code
            if rec.discovery_target_kind != TARGET_KIND_API_SERVER:
                updates['discovery_target_kind'] = TARGET_KIND_API_SERVER
            want = detection_row_code(server.code, rec.locale or '')
            if rec.code != want:
                updates['code'] = want
            if updates:
                rec.with_context(
                    _syncing_detection=True,
                    skip_hardcoded_restrictions=True,
                ).write(updates)
    
    def _factory_source_file_exists(self):
        """True if this row still has a source file under an installed addon."""
        self.ensure_one()
        from odoo.modules.module import get_module_path
        from ..utils.ai_paths import module_kind_dir

        source = (self.source_module or '').strip()
        if not source:
            return False
        mod_path = get_module_path(source)
        if not mod_path:
            return False
        rel = (self.rel_path or '').replace('\\', '/').lstrip('/')
        ctx_dir = module_kind_dir(mod_path, 'contexts')
        candidates = []
        if rel:
            candidates.append(os.path.join(mod_path, rel))
            candidates.append(os.path.join(mod_path, 'ai', rel))
            if ctx_dir:
                ai_dir = os.path.dirname(ctx_dir)
                candidates.append(os.path.join(ai_dir, rel))
                if rel.startswith('contexts/'):
                    candidates.append(
                        os.path.join(ctx_dir, rel[len('contexts/'):])
                    )
                else:
                    candidates.append(os.path.join(ctx_dir, rel))
        if any(os.path.isfile(path) for path in candidates):
            return True
        code = (self.code or '').strip()
        if self.context_type == 'discovery' and code:
            return code in self._factory_discovery_stems_on_disk()
        if ctx_dir and code:
            for root, _dirs, files in os.walk(ctx_dir):
                for filename in files:
                    if os.path.splitext(filename)[0] == code:
                        return True
        return False

    def _is_shipped_factory_locked(self):
        """Core, or factory row of an installed module whose file is still on disk."""
        self.ensure_one()
        if (self.context_type or '') == 'core':
            return True
        if self.owner_id:
            return False
        if self.api_server_id:
            return False
        source = (self.source_module or '').strip()
        if not source:
            return False
        installed = self.env['ir.module.module'].sudo().search_count([
            ('name', '=', source),
            ('state', '=', 'installed'),
        ])
        if not installed:
            return False
        return bool(self._factory_source_file_exists())

    def unlink(self):
        """Block core and live factory files; leftovers and user rows may go.

        ``skip_hardcoded_restrictions`` stays open for import, ``-u`` and
        uninstall hooks.
        """
        if not self.env.context.get('skip_hardcoded_restrictions'):
            assert_writer_can_write_records(self, self.env)
            locked = self.filtered(lambda rec: rec._is_shipped_factory_locked())
            if locked:
                raise UserError(_(
                    'This context cannot be deleted. System (core) packs and '
                    'factory files of an installed module stay until the '
                    'module is uninstalled or the source file is removed.'
                ))
        return super(AIContext, self).unlink()

    @api.model
    def _purge_retired_self_source_files(self):
        """Delete leftover ``ai/contexts/domain/self/`` on installed addons.

        Git already dropped those files; a flatten/publish copy can leave
        ``self.xml`` / ``self_es_ES.xml`` on the runtime module path, and the
        next import would recreate the DB rows.
        """
        import os
        import shutil

        removed = []
        for source_mod, ctx_dir in self._get_context_source_paths():
            leftover = os.path.join(ctx_dir, 'domain', 'self')
            if not os.path.isdir(leftover):
                continue
            if os.path.basename(os.path.normpath(leftover)) != 'self':
                continue
            try:
                shutil.rmtree(leftover)
            except OSError:
                _logger.warning(
                    'MCP: could not remove leftover identity folder %s (%s)',
                    leftover, source_mod, exc_info=True,
                )
                continue
            removed.append(leftover)
            _logger.info(
                'MCP: removed leftover identity folder %s (%s)',
                leftover, source_mod,
            )
        return removed

    @api.model
    def _retire_generic_self_row(self):
        """Unlink every agent from retired ``self`` / locale clones and delete.

        Covers ``self``, ``self_es_ES``, ``self_en_US``, ``self_retired``, any
        row whose ``base_code`` is ``self``, and leftovers under
        ``contexts/domain/self/``. Does not touch ``self_chatboo`` / ``self_mcp``.
        """
        from ..utils.agent_identity import is_retired_self_pack_code
        try:
            self._purge_retired_self_source_files()
        except Exception:
            _logger.warning(
                'MCP: could not purge leftover domain/self folders',
                exc_info=True,
            )
        Context = self.with_context(
            skip_hardcoded_restrictions=True,
            active_test=False,
        )
        old = Context.search([
            '|', '|',
            ('code', 'in', ['self', 'self_retired', 'self_es_ES', 'self_en_US']),
            ('base_code', '=', 'self'),
            ('rel_path', '=like', 'contexts/domain/self/%'),
        ])
        old = old.filtered(
            lambda r: is_retired_self_pack_code(r.code)
            or (r.base_code or '') == 'self'
            or (r.rel_path or '').startswith('contexts/domain/self/')
        )
        keep = {'self_chatboo', 'self_mcp'}
        old = old.filtered(lambda r: (r.code or '') not in keep)
        if not old:
            return self.browse()
        Agent = self.env['ai.agent']
        for agent in Agent.search([('context_ids', 'in', old.ids)]):
            agent.with_context(_skip_required_context_restore=True).write({
                'context_ids': [(3, cid) for cid in old.ids],
            })
        xmlids = self.env['ir.model.data'].search([
            ('model', '=', 'ai.context'),
            ('res_id', 'in', old.ids),
        ])
        if xmlids:
            xmlids.unlink()
        try:
            old.unlink()
        except Exception:
            for rec in old:
                code = rec.code or 'self'
                if code.startswith('self_retired'):
                    alias = code
                elif code == 'self':
                    alias = 'self_retired'
                elif code.startswith('self'):
                    alias = 'self_retired' + code[4:]
                else:
                    alias = 'self_retired'
                rec.write({'active': False, 'code': alias})
        return old
    
    def toggle_active(self):
        """Alterna el estado activo/inactivo"""
        for record in self:
            if record.context_type == 'core':
                continue  # No permitir cambiar estado de hardcodeados
            record.active = not record.active
        return True

    def read(self, fields=None, load='_classic_read'):
        """
        Sobrescribe read para leer los prompts hardcodeados desde la BD.
        Los prompts hardcodeados ahora están en la BD, así que se leen normalmente.
        """
        return super(AIContext, self).read(fields=fields, load=load)
    
    @api.model
    def _get_module_path(self):
        """Legacy: returns pns_ai_mcp module path only.
        Prefer _get_context_source_paths() for multi-module scanning."""
        import os
        from odoo.modules.module import get_module_path
        module_path = get_module_path('pns_ai_mcp')
        if module_path and os.path.exists(module_path):
            return module_path
        current_file = os.path.abspath(__file__)
        return os.path.dirname(os.path.dirname(current_file))

    @api.model
    def _get_context_source_paths(self):
        """Return list of (module_name, contexts_dir) for all installed modules
        that have a contexts/ directory.

        This enables multi-module context contribution:
        - pns_ai_mcp contributes context_type=core (protocol, execution rules)
        - pns_ai_chatboo contributes chatboo-specific contexts
        - Any future agent module can contribute its own contexts

        Returns:
            list of tuples: [(module_name, absolute_path_to_contexts_dir), ...]
        """
        from odoo.modules.module import get_module_path
        from ..utils.ai_paths import module_kind_dir
        result = []
        installed = self.env['ir.module.module'].sudo().search([
            ('state', 'in', ('installed', 'to upgrade', 'to install')),
        ])
        for mod in installed:
            mod_path = get_module_path(mod.name)
            if not mod_path:
                continue
            # Dual-path: prefer ai/contexts (PAAP umbrella), fall back to contexts.
            ctx_dir = module_kind_dir(mod_path, 'contexts')
            if ctx_dir:
                result.append((mod.name, ctx_dir))
                _logger.debug('Context source found: %s → %s', mod.name, ctx_dir)
        return result

    @staticmethod
    def _is_python_content(content):
        python_markers = ('def ', 'class ', 'import ', 'from ')
        content = content or ''
        return any(marker in content for marker in python_markers)

    @staticmethod
    def _format_datetime_value(value):
        if not value:
            return ''
        return fields.Datetime.to_string(value)

    def _build_export_content(self, record, extension):
        content = record.content or ''
        filename = f"{record.code}{extension}"

        if extension == '.py':
            header_lines = ['# -*- coding: utf-8 -*-', f'# Archivo: {filename}']
            if record.description:
                header_lines.append(f'# Descripción: {record.description}')
            if record.author:
                header_lines.append(f'# Autor: {record.author}')
            if record.version:
                header_lines.append(f'# Versión: {record.version}')
            if record.date_modified:
                header_lines.append(f'# Modificado: {record.date_modified}')
            header_lines.append(f'# Tipo: {record.context_type}')
            if record.locale:
                header_lines.append(f'# Locale: {record.locale}')
            header_lines.append(f'# Activo: {str(record.active).lower()}')
            header_lines.append('')
            return '\n'.join(header_lines) + (content or '')

        if extension == '.xml':
            xml_lines = ['<!--', f'contexto: {record.code}']
            if record.description:
                xml_lines.append(f'descripción: {record.description}')
            xml_lines.append(f'tipo: {record.context_type}')
            xml_lines.append(f'activo: {str(record.active).lower()}')
            xml_lines.append('-->')
            xml_lines.append('')
            return '\n'.join(xml_lines) + content

        yaml_lines = ['---', f'contexto: {record.code}']
        if record.description:
            yaml_lines.append(f'descripción: {record.description}')
        yaml_lines.append(f'tipo: {record.context_type}')
        if record.locale:
            yaml_lines.append(f'locale: {record.locale}')
        if record.author:
            yaml_lines.append(f'autor: {record.author}')
        if record.version:
            yaml_lines.append(f'versión: {record.version}')
        if record.date_modified:
            yaml_lines.append(f'fecha_modificacion: {record.date_modified}')
        yaml_lines.append(f'activo: {str(record.active).lower()}')
        yaml_lines.append('---')
        yaml_lines.append('')
        return '\n'.join(yaml_lines) + content

    @api.model
    def import_system_from_files(self):
        """
        Public method to trigger context import manually (e.g. from UI button).
        Falls back to _import_all_from_module to ensure consistent behavior.
        """
        ensure_ai_admin(self.env)
        _logger.info("MCP: import_system_from_files called via UI/Action - Triggering full module sync.")
        return self._import_all_from_module()
    


    @api.model
    def normalize_code(self, code_candidate):
        """
        Normaliza una cadena para convertirla en un código válido.
        ALGORITMO CENTRALIZADO:
        1. Detecta sufijos de locale (_es_ES).
        2. Preserva casing del sufijo.
        3. Convierte el resto a minúsculas y limpia caracteres inválidos.
        """
        import re
        
        if not code_candidate:
            return ""
            
        code_candidate = str(code_candidate).strip()
        # Locale suffix: accept any casing (_es_ES, _ES_es, …) → canonical _es_ES
        locale_pattern = re.compile(
            r'^(?P<prefix>.*)(_(?P<lang>[a-zA-Z]{2})_(?P<country>[a-zA-Z]{2}))$'
        )
        match = locale_pattern.match(code_candidate)
        
        if match:
            prefix = match.group('prefix').lower().strip()
            prefix = re.sub(r'[^a-z0-9_]', '_', prefix)
            prefix = re.sub(r'_+', '_', prefix)
            suffix = '_%s_%s' % (
                match.group('lang').lower(),
                match.group('country').upper(),
            )
            return prefix + suffix
        else:
            code = code_candidate.lower().strip()
            code = re.sub(r'[^a-z0-9_]', '_', code)
            code = re.sub(r'_+', '_', code)
            return code

    @api.model
    def generate_code_from_name(self, filename_or_path):
        """
        Genera el código único a partir de un nombre de archivo.
        Usa normalize_code para garantizar consistencia.
        """
        import os
        
        # 1. Obtener solo el nombre de archivo sin ruta
        filename = os.path.basename(filename_or_path)
        
        # 2. Quitar extensión
        name_no_ext = os.path.splitext(filename)[0]
        
        # 3. Delegar en normalizador central
        return self.normalize_code(name_no_ext)


    @api.model
    def _invalidate_agent_caches_after_import(self):
        """Tras restore/import de contextos, vaciar cachés compiladas de agentes.

        SQL inmediato con ``FOR UPDATE SKIP LOCKED``: si el Odoo vivo (workers/
        crons) tiene filas de ``ai_agent`` bloqueadas —p. ej. durante ``t.sh -u``—
        no esperamos lock_timeout ni tumba el registry. El ``write()`` ORM
        difería el SQL al ``flush()`` de ``call_kw``, fuera de cualquier try.

        Siempre en savepoint: un ``could not serialize access`` de Postgres
        aborta la transacción actual; sin savepoint, el ``except`` solo traga
        el error Python y el ``-u`` siguiente (cron XML, etc.) muere con
        ``current transaction is aborted``.
        """
        cr = self.env.cr
        try:
            with cr.savepoint():
                cr.execute(
                    """
                    UPDATE ai_agent
                       SET cached_content = NULL,
                           cache_locale = NULL,
                           cache_context_signature = NULL,
                           write_uid = %s,
                           write_date = (now() at time zone 'UTC')
                     WHERE id IN (
                           SELECT id FROM ai_agent FOR UPDATE SKIP LOCKED
                     )
                    """,
                    [self.env.uid],
                )
                updated = cr.rowcount
            try:
                from odoo.addons.pns_ai_mcp.utils.compat import (
                    invalidate_recordset_fields,
                )
                invalidate_recordset_fields(
                    self.env['ai.agent'].sudo().search([]),
                    ['cached_content', 'cache_locale', 'cache_context_signature'],
                )
            except Exception:
                pass
            if updated is not None:
                _logger.info(
                    'MCP: agent caches invalidated after import (%s row(s))',
                    updated,
                )
        except Exception as exc:
            _logger.warning(
                'MCP: could not invalidate agent caches after import: %s', exc,
            )

    @api.model
    def _module_ships_context_code(self, module_name, code):
        """True when ``module_name`` still has a file for this context code."""
        from ..utils.context_code_scan import codes_in_contexts_dir

        if not module_name or not code:
            return False
        for source_mod, contexts_dir in self._get_context_source_paths():
            if source_mod != module_name:
                continue
            return code in codes_in_contexts_dir(contexts_dir)
        return False

    @api.model
    def _import_all_from_module(self, replace_existing=True, module_name=None,
                                core_only=False, only_codes=None):
        """Import contexts from all installed modules that ship a contexts dir.

        Scans each module's ``ai/contexts/`` directory recursively.
        Subdirectories named ``system/`` yield context_type=core contexts;
        everything else yields domain/locale contexts.

        Args:
            replace_existing: True = overwrite matching codes (upsert) when the
                              DB row has no ``owner_id`` (factory). User-owned
                              rows (``owner_id`` set) are always skipped.
                              False = additive only (no overwrite).
                              Never deletes DB records absent from source.
            module_name:      If set, only import from this specific module.
            core_only:        True = only refresh core/system contexts.
            only_codes:       Optional iterable of context codes. When set, only
                              those codes are imported/updated (no pruning).

        Returns:
            dict with keys: imported, updated, skipped, deleted, errors.
        """
        import os
        import re

        sources = self._get_context_source_paths()
        if module_name:
            sources = [(mn, cd) for mn, cd in sources if mn == module_name]
            if not sources:
                from odoo.modules.module import get_module_path
                from ..utils.ai_paths import module_kind_dir
                path = get_module_path(module_name)
                ctx_dir = module_kind_dir(path, 'contexts') if path else None
                if ctx_dir:
                    sources = [(module_name, ctx_dir)]

        try:
            self._purge_retired_self_source_files()
        except Exception:
            _logger.warning(
                'MCP: could not purge leftover domain/self folders',
                exc_info=True,
            )

        total_imported = 0
        total_updated = 0
        total_skipped = 0
        total_deleted = 0
        total_errors = []

        for source_mod, contexts_dir in sources:
            _logger.info('MCP: importing contexts from module %s (%s)', source_mod, contexts_dir)
            result = self._import_contexts_from_dir(
                contexts_dir, source_mod, replace_existing,
                core_only=core_only, only_codes=only_codes,
            )
            total_imported += result['imported']
            total_updated += result['updated']
            total_skipped += result['skipped']
            total_deleted += result['deleted']
            total_errors.extend(result['errors'])

        # Legacy fallback: if no sources found via registry, try pns_ai_mcp directly
        if not sources and not module_name:
            from ..utils.ai_paths import module_kind_dir
            fallback_dir = module_kind_dir(self._get_module_path(), 'contexts')
            if fallback_dir and os.path.isdir(fallback_dir):
                _logger.warning('MCP: no modules found via registry, fallback to pns_ai_mcp')
                result = self._import_contexts_from_dir(
                    fallback_dir, 'pns_ai_mcp', replace_existing,
                    core_only=core_only, only_codes=only_codes,
                )
                total_imported += result['imported']
                total_updated += result['updated']
                total_skipped += result['skipped']
                total_deleted += result['deleted']
                total_errors.extend(result['errors'])

        _logger.info(
            'MCP: Import complete. %d imported, %d updated, %d skipped, '
            '%d deleted, %d errors (from %d modules)',
            total_imported, total_updated, total_skipped,
            total_deleted, len(total_errors), len(sources),
        )
        try:
            self._retire_generic_self_row()
        except Exception:
            _logger.warning(
                'MCP: could not retire leftover generic self rows after import',
                exc_info=True,
            )
        try:
            Agent = self.env['ai.agent']
            if hasattr(Agent, '_unlink_foreign_identity_packs'):
                Agent.search([])._unlink_foreign_identity_packs()
        except Exception:
            _logger.warning(
                'MCP: could not rewrite leftover identity pins after import',
                exc_info=True,
            )
        self._invalidate_agent_caches_after_import()
        return {
            'imported': total_imported,
            'updated': total_updated,
            'skipped': total_skipped,
            'deleted': total_deleted,
            'errors': total_errors,
        }

    @api.model
    def _explicit_agent_codes_from_metadata(self, metadata):
        """Exclusive ``agent_codes`` list, or None if the pack is not exclusive.

        None — no tag (own-module / default push; ``@module`` pull allowed).
        [] — ``none`` / ``catalog`` (catalog only; pull only if the code is listed).
        ['pns_ai_mcp', …] — exclusive to those agents.
        """
        metadata = metadata or {}
        raw = metadata.get('agent_codes') or metadata.get('agent_code') or ''
        if not str(raw).strip():
            return None
        normalized = str(raw).strip().lower()
        if normalized in ('none', 'false', '-', 'catalog'):
            return []
        return [c.strip() for c in str(raw).split(',') if c.strip()]

    @api.model
    def _resolve_import_agent_codes(self, metadata, source_mod, context_type='domain'):
        """Agent codes to link after import (push side of dual wire).

        Dual wire (see docs/decisions/context_code_owners.md):

        - **Push (this method):** explicit ``agent_codes`` in the pack file;
          otherwise own-module agents (``ai.agent.module_name == source_mod``);
        - **Pull:** agents whose ``default_context_codes`` list the code /
          ``@source_mod`` — applied in ``_link_context_after_import``.
          Explicit ``agent_codes`` makes ``@module`` pull exclusive.

        ``agent_codes: none`` / ``catalog`` = catalog only (no push).
        Core contexts are never linked via context_ids.
        """
        exclusive = self._explicit_agent_codes_from_metadata(metadata)
        if exclusive is not None:
            return list(exclusive)
        if context_type == 'core':
            return []
        codes = []
        # Own-module push: pack that ships the agent links its knowledge to it.
        if source_mod:
            own = self.env['ai.agent'].search([
                ('module_name', '=', source_mod),
            ])
            codes.extend(own.mapped('code'))
        if source_mod == 'pns_ai_mcp':
            if 'pns_ai_mcp' not in codes:
                codes.append('pns_ai_mcp')
        return codes

    def _pull_agent_codes_for_context(
        self, context_code, source_mod, pack_exclusive=False,
    ):
        """Agents that pull this context via default_context_codes."""
        if not context_code:
            return []
        codes = []
        for agent in self.env['ai.agent'].search([]):
            if agent.wants_context_code(
                context_code,
                source_module=source_mod,
                pack_exclusive=pack_exclusive,
            ):
                codes.append(agent.code)
        return codes

    def _link_context_after_import(self, record, push_agent_codes, source_mod=None):
        """Link context via push codes ∪ pull lists (dual wire)."""
        # ``core`` is auto-injected; ``discovery`` is engine-consumed routing —
        # neither is ever wired to an agent's context_ids.
        if not record or record.context_type in context_roles.AGENT_LINK_EXCLUDED_TYPES:
            return
        source_mod = source_mod or record.source_module
        metadata = self._extract_metadata_from_content(
            record.content or '', 'pack.xml',
        )
        pack_exclusive = self._explicit_agent_codes_from_metadata(metadata) is not None
        codes = list(push_agent_codes or [])
        for code in self._pull_agent_codes_for_context(
            record.code, source_mod, pack_exclusive=pack_exclusive,
        ):
            if code not in codes:
                codes.append(code)
        self._link_context_to_import_agents(record, codes)

    def _link_context_to_import_agents(self, record, agent_codes):
        """Wire a non-core context to the agents declared at import time."""
        if (
            not record
            or record.context_type in context_roles.AGENT_LINK_EXCLUDED_TYPES
            or not agent_codes
        ):
            return
        Agent = self.env['ai.agent']
        for code in agent_codes:
            agent = Agent.search([('code', '=', code)], limit=1)
            if agent:
                agent.context_ids = [(4, record.id)]

    @api.model
    def default_context_codes_for_agent(self, agent_code, pull_tokens=None):
        """Shipped default composition for an agent (pull ∪ push).

        Read-only scan of on-disk context files plus the agent's
        ``default_context_codes`` pull list. ``core`` contexts are excluded.
        ``pull_tokens`` overrides the live recipe (used by factory restore
        to expand only the XML seed).
        """
        import os

        codes = set()
        if not agent_code:
            return codes
        Agent = self.env['ai.agent']
        agent = Agent.search([('code', '=', agent_code)], limit=1)
        if pull_tokens is not None:
            pull_codes, pull_packs = pull_tokens
        else:
            pull_codes, pull_packs = (
                agent._default_context_tokens() if agent else (set(), set())
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
        for source_mod, contexts_dir in self._get_context_source_paths():
            if not contexts_dir or not os.path.isdir(contexts_dir):
                continue
            pack_pull = source_mod in pull_packs
            for root, _dirs, files in os.walk(contexts_dir):
                for filename in files:
                    if not filename.endswith(('.md', '.py', '.xml', '.json')):
                        continue
                    filepath = os.path.join(root, filename)
                    if not os.path.isfile(filepath):
                        continue
                    rel = os.path.relpath(filepath, contexts_dir).replace('\\', '/')
                    is_system = rel.startswith('system/') or rel.startswith('core/')
                    # Discovery rows are engine-consumed routing, never part of an
                    # agent's default composition.
                    if rel.startswith('discovery/') or rel.startswith('discover/'):
                        continue
                    try:
                        with open(filepath, 'r', encoding='utf-8') as f:
                            content = f.read()
                        if not content.strip():
                            continue
                        metadata = self._extract_metadata_from_content(content, filename)
                        code = self.generate_code_from_name(filepath)
                        if metadata.get('contexto'):
                            code = self.normalize_code(metadata['contexto'])
                        elif metadata.get('code'):
                            code = self.normalize_code(metadata['code'])
                        _cat = metadata.get('tipo') or ''
                        if _cat == context_roles.DISCOVERY:
                            continue
                        ctype = context_roles.canonical_type(
                            _cat, is_system=is_system,
                        )
                        # ``core`` + ``discovery`` are never hand-wired to agents.
                        if ctype in context_roles.AGENT_LINK_EXCLUDED_TYPES:
                            continue
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
                            exclusive = self._explicit_agent_codes_from_metadata(
                                metadata,
                            )
                            if exclusive is not None and agent_code not in exclusive:
                                continue
                            codes.add(code)
                            continue
                        agent_codes = self._resolve_import_agent_codes(
                            metadata, source_mod, context_type=ctype,
                        )
                        if agent_code in agent_codes:
                            codes.add(code)
                    except Exception:
                        _logger.warning(
                            'MCP: default-composition scan failed for %s',
                            filepath, exc_info=True,
                        )
        return codes

    def _discovery_vals_from_metadata(self, metadata):
        """Map parsed JSON short keys onto ORM discovery fields."""
        return {
            'discovery_target': metadata.get('discovery_target') or '',
            'discovery_target_kind': metadata.get('discovery_target_kind') or 'domain',
            'discovery_triggers': metadata.get('discovery_triggers') or '[]',
            'discovery_priority': metadata.get('discovery_priority') or 0,
            'discovery_soft_depends': metadata.get('discovery_soft_depends') or False,
        }

    @api.model
    def _import_contexts_from_dir(self, contexts_dir, source_mod, replace_existing=True,
                                  core_only=False, only_codes=None):
        """Import contexts from a single module's ai/contexts/ directory.

        Args:
            contexts_dir: Absolute path to the module's ai/contexts/ directory.
            source_mod: Technical name of the contributing module.
            replace_existing: True = overwrite matching. False = additive.
                              Never deletes (no pruning).
            core_only: True = process only system/core files, skipping
                       user-editable domain/locale contexts.
            only_codes: Optional set/list of codes to import; skips prune.

        Returns:
            dict with keys: imported, updated, skipped, deleted, errors.
        """
        import os
        import re

        from ..utils.agent_identity import (
            is_retired_self_pack_code,
            is_retired_self_source_path,
        )

        imported_count = 0
        updated_count = 0
        skipped_count = 0
        errors = []
        found_codes = []
        system_codes_in_files = []
        only_codes_set = set(only_codes) if only_codes else None

        if not os.path.exists(contexts_dir):
            return {'imported': 0, 'updated': 0, 'skipped': 0, 'deleted': 0, 'errors': []}

        module_dir = os.path.dirname(contexts_dir)

        for root, dirs, files in os.walk(contexts_dir):
            for filename in files:
                if not filename.endswith(('.md', '.py', '.xml', '.json')):
                    continue

                filepath = os.path.join(root, filename)
                if not os.path.isfile(filepath):
                    continue

                rel_path_from_contexts = os.path.relpath(filepath, contexts_dir).replace('\\', '/')
                rel_path_from_module = os.path.relpath(filepath, module_dir).replace('\\', '/')

                is_system = (
                    rel_path_from_contexts.startswith('system/')
                    or rel_path_from_contexts.startswith('core/')
                )
                is_discovery = (
                    rel_path_from_contexts.startswith('discovery/')
                    or rel_path_from_contexts.startswith('discover/')
                )
                is_custom = not is_system  # Everything non-system is agent-contributed

                # core_only: refresh shipped protocol (core) contexts only,
                # leaving user-editable domain/locale contexts untouched.
                # only_codes may still target domain files explicitly.
                if core_only and not is_system and not only_codes_set:
                    continue

                try:
                    code = self.generate_code_from_name(filepath)

                    with open(filepath, 'r', encoding='utf-8') as f:
                        content = f.read()

                    if not content.strip():
                        errors.append(f"{rel_path_from_contexts}: empty file")
                        continue

                    metadata = self._extract_metadata_from_content(content, filename)

                    if metadata.get('contexto'):
                        code = self.normalize_code(metadata['contexto'])
                    elif metadata.get('code'):
                        code = self.normalize_code(metadata['code'])
                    if is_discovery:
                        code = context_roles.canonical_discovery_code(code)

                    if only_codes_set is not None and code not in only_codes_set:
                        continue

                    if (
                        is_retired_self_pack_code(code)
                        or is_retired_self_source_path(rel_path_from_contexts)
                        or is_retired_self_source_path(rel_path_from_module)
                    ):
                        skipped_count += 1
                        _logger.info(
                            'MCP: skip retired identity pack %s (%s/%s)',
                            code, source_mod, rel_path_from_contexts,
                        )
                        continue

                    found_codes.append(code)
                    if is_system:
                        system_codes_in_files.append(code)

                    description = metadata.get('description') or f"Context imported from {source_mod}/{rel_path_from_contexts}"

                    _cat = metadata.get('tipo') or ''
                    _ctype = context_roles.canonical_type(
                        _cat,
                        discovery_folder=is_discovery,
                        is_system=is_system,
                    )
                    # Discovery rows are engine-consumed routing, not agent content.
                    if context_roles.is_discovery(_ctype):
                        agent_codes = []
                    else:
                        agent_codes = self._resolve_import_agent_codes(
                            metadata, source_mod, context_type=_ctype,
                        )
                    vals = {
                        'code': code,
                        'description': description,
                        'context_type': _ctype,
                        'content': content,
                        'rel_path': rel_path_from_module,
                        'source_module': source_mod,
                        'locale': self._infer_explicit_locale(
                            code, content, metadata,
                        ) or False,
                        'active': metadata.get('active', True) if metadata.get('active') is not None else True,
                    }

                    if metadata.get('author'):
                        vals['author'] = metadata['author']
                    if metadata.get('version'):
                        vals['version'] = metadata['version']
                    if metadata.get('date_modified'):
                        vals['date_modified'] = metadata['date_modified']

                    if context_roles.is_discovery(_ctype):
                        vals.update(self._discovery_vals_from_metadata(metadata))

                    existing = self.search([('code', '=', code)], limit=1)

                    if not existing:
                        existing_by_path = self.search([
                            ('rel_path', '=', rel_path_from_module),
                            ('context_type', '=' if is_system else '!=', 'core'),
                        ], limit=1)
                        if existing_by_path:
                            _logger.info('MCP: code rename detected for %s: %s → %s',
                                         rel_path_from_module, existing_by_path.code, code)
                            existing = existing_by_path

                    if existing:
                        if not replace_existing:
                            skipped_count += 1
                            continue
                        # User-created knowledge (owner_id set) is never overwritten
                        # by module files — factory rows have empty owner.
                        if existing.owner_id:
                            skipped_count += 1
                            _logger.info(
                                'MCP: skip factory overwrite of user-owned '
                                'context %s (owner=%s)',
                                existing.code, existing.owner_id.login,
                            )
                            continue
                        # One code → one owner. Incoming may take over only
                        # when the current owner no longer ships that code.
                        if (
                            existing.source_module
                            and existing.source_module != source_mod
                        ):
                            from ..utils.context_code_scan import (
                                factory_row_blocks_incoming,
                            )
                            owner_ships = self._module_ships_context_code(
                                existing.source_module, code,
                            )
                            if factory_row_blocks_incoming(
                                existing.source_module, source_mod, owner_ships,
                            ):
                                _logger.warning(
                                    'MCP: skip content write for context %s '
                                    '(owner=%s, attempted=%s); linking only',
                                    code, existing.source_module, source_mod,
                                )
                                self._link_context_after_import(
                                    existing, agent_codes, source_mod=source_mod,
                                )
                                skipped_count += 1
                                continue
                            _logger.info(
                                'MCP: factory context %s owner %s → %s '
                                '(previous owner no longer ships it)',
                                code, existing.source_module, source_mod,
                            )
                        if existing.code != code:
                            vals['code'] = code
                        existing.with_context(
                            tracking_disable=True, skip_hardcoded_restrictions=True,
                        ).write(vals)
                        self._link_context_after_import(
                            existing, agent_codes, source_mod=source_mod,
                        )
                        updated_count += 1
                        _logger.info('MCP: updated context %s from %s/%s',
                                     code, source_mod, rel_path_from_contexts)
                    else:
                        record = self.with_context(tracking_disable=True).create(vals)
                        self._link_context_after_import(
                            record, agent_codes, source_mod=source_mod,
                        )
                        imported_count += 1
                        _logger.info('MCP: imported context %s from %s/%s',
                                     code, source_mod, rel_path_from_contexts)

                except Exception as e:
                    error_msg = f"{source_mod}/{rel_path_from_contexts}: {e}"
                    errors.append(error_msg)
                    _logger.error('MCP: error importing %s: %s', filepath, e, exc_info=True)

        # No pruning by design: an import is upsert + recover only. Records
        # present in the DB but absent from the source are never deleted
        # (unified no-delete rule for all imports). A renamed shipped file
        # therefore leaves the old code as a duplicate until removed by hand.
        deleted_count = 0

        return {
            'imported': imported_count,
            'updated': updated_count,
            'skipped': skipped_count,
            'deleted': deleted_count,
            'errors': errors,
        }
    
    @api.model
    def _import_system_from_files_internal(self):
        """
        Método interno que importa contextos.
        [REFACTOR CENTRALIZACIÓN]
        Anteriormente tenía su propia lógica, lo que causaba inconsistencias (casing, locales).
        Ahora delega DIRECTAMENTE en _import_all_from_module() para asegurar que
        HAYA UNA ÚNICA FORMA DE IMPORTAR, sea manual o por código.
        """
        _logger.info("MCP: _import_system_from_files_internal -> Delegando a lógica unificada _import_all_from_module")
        return self._import_all_from_module()

    @api.model
    def _import_from_files_internal(self):
        """
        Método interno que importa contextos desde archivos.
        [REFACTOR CENTRALIZACIÓN]
        Delega en _import_all_from_module.
        """
        _logger.info("MCP: _import_from_files_internal -> Delegando a lógica unificada _import_all_from_module")
        return self._import_all_from_module()
    @api.model
    def _contexts_zip_filename(self, scope_label):
        return pns_ui.build_export_filename(
            self.env, 'contexts_%s' % (scope_label or 'all'), 'zip')

    def _zip_path_for_record(self, record):
        ext = '.md'
        if context_roles.is_discovery(record.context_type):
            ext = '.json'
        elif record.content and (
            record.content.startswith('# -*-')
            or 'import odoo' in record.content
            or 'def ' in record.content
        ):
            ext = '.py'
        elif record.content and record.content.strip().startswith('<') and '>' in record.content:
            ext = '.xml'

        zip_path = None
        if record.rel_path:
            cleaned_path = record.rel_path.replace('\\', '/')
            if cleaned_path.startswith('contexts/'):
                zip_path = cleaned_path[9:]
            else:
                zip_path = cleaned_path
        if not zip_path:
            folder = record.context_type if record.context_type in context_roles.ALL_TYPES else 'domain'
            zip_path = '%s/%s%s' % (folder, record.code, ext)
        return zip_path, ext

    def _export_content_for_record(self, record, ext):
        content_to_write = record.content or ''
        # Discovery rows are raw JSON routing; never wrap in md front-matter.
        if context_roles.is_discovery(record.context_type) or ext == '.json':
            return content_to_write
        if ext == '.md' and not content_to_write.startswith('---'):
            agent_code = record.agent_ids[:1].code or 'pns_ai_mcp'
            metadata_block = (
                '---\n'
                'code: %s\n'
                'description: %s\n'
                'tipo: %s\n'
                'locale: %s\n'
                'agent_code: %s\n'
                'active: %s\n'
                '---\n\n'
            ) % (
                record.code,
                record.description or '',
                record.context_type or '',
                record.locale or '',
                agent_code,
                str(record.active),
            )
            content_to_write = metadata_block + content_to_write
        return content_to_write

    def _build_export_manifest(self, records, scope_label, agent=None):
        manifest = {
            'format_version': 1,
            'exported_at': fields.Datetime.now().isoformat(),
            'scope': scope_label,
            'contexts': [],
        }
        if agent:
            manifest['agent'] = {
                'code': agent.code,
                'name': agent.name,
                'context_codes': records.sorted(
                    key=lambda c: (c.context_type or '', c.code),
                ).mapped('code'),
            }
        for record in records:
            manifest['contexts'].append({
                'code': record.code,
                'context_type': record.context_type,
                'locale': record.locale or False,
                'agent_code': record.agent_ids[:1].code or False,
                'active': record.active,
                'rel_path': record.rel_path,
            })
        return manifest

    @api.model
    def import_context_file(
        self, filename, content, zip_path=None, replace_existing=False, force_agent=None,
    ):
        """Import or update one context file. Match key: code + rel_path."""
        ensure_ai_admin(self.env)
        metadata = self._extract_metadata_from_content(content, filename)

        raw_code_meta = metadata.get('contexto') or metadata.get('context') or metadata.get('code')
        if raw_code_meta:
            original_code = self.normalize_code(raw_code_meta)
        else:
            original_code = self.generate_code_from_name(filename)

        description = (
            metadata.get('descripción') or metadata.get('descripcion')
            or metadata.get('description') or _('Imported from %s') % filename
        )
        _cat = metadata.get('tipo') or 'domain'
        _folder_probe = (zip_path or filename or '').replace('\\', '/')
        discovery_folder = 'discovery' in _folder_probe.strip('/').split('/')
        context_type = context_roles.canonical_type(
            _cat, discovery_folder=discovery_folder,
        )
        source_mod = metadata.get('source_module') or 'pns_ai_mcp'
        if context_roles.is_discovery(context_type):
            agent_codes = []
        else:
            agent_codes = self._resolve_import_agent_codes(
                metadata, source_mod, context_type=context_type,
            )
        if force_agent:
            agent = force_agent
            agent_codes = [force_agent.code] if force_agent else agent_codes
        else:
            agent = False

        if zip_path:
            if not zip_path.startswith('contexts/'):
                if zip_path.startswith(('custom/', 'system/')):
                    rel_path = 'contexts/%s' % zip_path
                else:
                    rel_path = 'contexts/custom/%s' % zip_path
            else:
                rel_path = zip_path
        else:
            rel_path = 'contexts/custom/%s' % filename
        rel_path = (rel_path or '').replace('\\', '/').strip()

        existing = self.search([
            ('code', '=', original_code),
            ('rel_path', '=', rel_path or ''),
        ], limit=1)

        if existing and existing.context_type == 'core':
            return {'action': 'protocol_skipped', 'code': original_code}
        if context_type == 'core':
            return {'action': 'protocol_skipped', 'code': original_code}

        if existing:
            if not replace_existing:
                return {'action': 'skipped', 'code': original_code}
            existing.write({
                'content': content,
                'description': description,
                'context_type': context_type,
                'rel_path': rel_path,
                'locale': self._infer_explicit_locale(
                    original_code, content, metadata,
                ) or False,
                **(
                    self._discovery_vals_from_metadata(metadata)
                    if context_roles.is_discovery(context_type) else {}
                ),
            })
            self._link_context_after_import(
                existing, agent_codes, source_mod=source_mod,
            )
            if agent and not agent_codes:
                agent.context_ids = [(4, existing.id)]
            return {'action': 'updated', 'code': original_code}

        record = self.create({
            'code': original_code,
            'content': content,
            'description': description,
            'context_type': context_type,
            'active': True,
            'rel_path': rel_path,
            'locale': self._infer_explicit_locale(
                original_code, content, metadata,
            ) or False,
            **(
                self._discovery_vals_from_metadata(metadata)
                if context_roles.is_discovery(context_type) else {}
            ),
        })
        self._link_context_after_import(
            record, agent_codes, source_mod=source_mod,
        )
        if agent and not agent_codes:
            agent.context_ids = [(4, record.id)]
        return {'action': 'imported', 'code': original_code}

    @api.model
    def _tally_import_result(self, stats, result):
        action = result.get('action')
        if action == 'imported':
            stats['imported'] += 1
        elif action == 'updated':
            stats['updated'] += 1
        elif action == 'skipped':
            stats['skipped'] += 1
        elif action == 'protocol_skipped':
            stats['protocol_skipped'] += 1
        elif action == 'error':
            stats['errors'].append(result.get('message', ''))

    @api.model
    def _read_zip_manifest(self, zip_buffer):
        try:
            with zipfile.ZipFile(zip_buffer, 'r') as zf:
                if 'manifest.json' not in zf.namelist():
                    return {}
                return json.loads(zf.read('manifest.json').decode('utf-8'))
        except Exception:
            return {}

    @api.model
    def _resolve_import_code(self, content, filename):
        metadata = self._extract_metadata_from_content(content, filename)
        raw_code_meta = (
            metadata.get('contexto') or metadata.get('context') or metadata.get('code')
        )
        if raw_code_meta:
            return self.normalize_code(raw_code_meta)
        return self.generate_code_from_name(filename)

    @api.model
    def import_contexts_from_zip_buffer(
        self, zip_buffer, replace_existing=False, force_agent=None, allowed_codes=None,
    ):
        """Import context files from a ZIP buffer."""
        stats = {
            'imported': 0, 'updated': 0, 'skipped': 0,
            'protocol_skipped': 0, 'skipped_manifest': 0, 'errors': [],
        }
        with zipfile.ZipFile(zip_buffer, 'r') as zf:
            for file_info in zf.infolist():
                if not file_info.filename.endswith(('.txt', '.md', '.xml')):
                    continue
                if file_info.filename.startswith('__MACOSX') or '/.' in file_info.filename:
                    continue
                try:
                    content = zf.read(file_info.filename).decode('utf-8')
                    if allowed_codes is not None:
                        code = self._resolve_import_code(content, file_info.filename)
                        if code not in allowed_codes:
                            stats['skipped_manifest'] += 1
                            continue
                    zip_path = file_info.filename.replace('\\', '/')
                    result = self.import_context_file(
                        file_info.filename, content, zip_path=zip_path,
                        replace_existing=replace_existing, force_agent=force_agent,
                    )
                    self._tally_import_result(stats, result)
                except Exception as exc:
                    stats['errors'].append('%s: %s' % (file_info.filename, exc))
        return stats

    @api.model
    def import_contexts_zip(
        self, zip_bytes, replace_existing=False, force_agent=None,
        require_selected_scope=False,
    ):
        """Import contexts from a ZIP export (reads manifest.json when present)."""
        ensure_ai_admin(self.env)
        zip_buffer = io.BytesIO(zip_bytes)
        manifest = self._read_zip_manifest(zip_buffer)
        scope = (manifest or {}).get('scope', '')
        warnings = []
        allowed_codes = None

        if require_selected_scope:
            if not scope.startswith('sel-'):
                raise UserError(_(
                    'ZIP must come from "Export selected contexts to ZIP" '
                    '(manifest scope sel-*).'
                ))
            allowed_codes = {
                c['code'] for c in manifest.get('contexts', []) if c.get('code')
            }
            if not allowed_codes:
                warnings.append(_('Manifest lists no context codes.'))

        agent_manifest = (manifest or {}).get('agent') or {}
        if force_agent and agent_manifest.get('code') and agent_manifest['code'] != force_agent.code:
            warnings.append(_(
                'Manifest agent is "%s"; contexts were assigned to target agent "%s".'
            ) % (agent_manifest['code'], force_agent.code))

        zip_buffer.seek(0)
        file_stats = self.import_contexts_from_zip_buffer(
            zip_buffer,
            replace_existing=replace_existing,
            force_agent=force_agent,
            allowed_codes=allowed_codes,
        )
        return {
            'files': file_stats,
            'manifest': {
                'scope': scope,
                'context_count': len(manifest.get('contexts', [])),
            },
            'warnings': warnings,
        }

    @api.model
    def import_agent_contexts_zip(self, agent, zip_bytes, replace_existing=False):
        """Import an agent contexts export ZIP into the target agent."""
        ensure_ai_admin(self.env)
        agent.ensure_one()
        return self.import_contexts_zip(
            zip_bytes,
            replace_existing=replace_existing,
            force_agent=agent,
        )

    @api.model
    def _build_context_zip_import_report_html(self, result, title=None):
        files = result['files']
        manifest = result.get('manifest') or {}
        warnings = result.get('warnings') or []
        errors = files.get('errors') or []
        success_count = files['imported'] + files['updated']
        status_class, status_icon, status_text, _ntype = pns_ui.derive_operation_status(
            errors,
            success_count,
            failed_text=_('Import failed.'),
            warnings_text=_('Import completed with warnings.'),
            success_text=_('Import completed successfully.'),
            extra_warnings=warnings,
        )
        sections = []
        if manifest.get('scope'):
            manifest_rows = [(_('Scope'), manifest['scope'])]
            if manifest.get('context_count'):
                manifest_rows.append(
                    (_('Contexts in manifest'), manifest['context_count']),
                )
            sections.append({'title': _('Manifest'), 'rows': manifest_rows})
        sections.append({
            'title': _('Context files'),
            'rows': [
                (_('Created'), files['imported']),
                (_('Updated'), files['updated']),
                (_('Skipped (existing, not replaced)'), files['skipped']),
                (_('Skipped (not in manifest)'), files.get('skipped_manifest', 0)),
                (_('Protocol (protected)'), files['protocol_skipped']),
            ],
        })
        return pns_ui.build_operation_report_html(
            title,
            status_text,
            status_class,
            status_icon,
            sections=sections,
            errors=errors,
            warnings=warnings,
        )

    def action_open_import_zip_wizard(self):
        ensure_ai_admin(self.env)
        return self._action_open_context_import_wizard('zip')

    def action_open_import_selected_zip_wizard(self):
        ensure_ai_admin(self.env)
        return self._action_open_context_import_wizard('zip_selected')

    @api.model
    def _action_open_context_import_wizard(self, import_mode):
        titles = {
            'zip': _('Import contexts from ZIP'),
            'zip_selected': _('Import selected contexts from ZIP'),
        }
        return {
            'type': 'ir.actions.act_window',
            'name': titles.get(import_mode, _('Import contexts')),
            'res_model': 'pns_ai_mcp.context_import_wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_import_mode': import_mode},
        }

    @api.model
    def import_agent_zip(
        self, agent, zip_bytes, replace_existing=False, replace_composition=True,
    ):
        """Import a context pack ZIP into the target agent (files + composition)."""
        ensure_ai_admin(self.env)
        agent.ensure_one()
        zip_buffer = io.BytesIO(zip_bytes)
        manifest = {}
        warnings = []

        with zipfile.ZipFile(zip_buffer, 'r') as zf:
            if 'manifest.json' in zf.namelist():
                try:
                    manifest = json.loads(
                        zf.read('manifest.json').decode('utf-8'),
                    )
                except Exception as exc:
                    warnings.append(_('Invalid manifest.json: %s') % exc)

        zip_buffer.seek(0)
        file_stats = self.import_contexts_from_zip_buffer(
            zip_buffer,
            replace_existing=replace_existing,
            force_agent=None,
        )

        composition_stats = {
            'applied': 0, 'missing_codes': [], 'removed': 0, 'manifest_agent': None,
        }
        agent_manifest = (manifest or {}).get('agent') or {}
        composition_stats['manifest_agent'] = agent_manifest.get('code')
        context_codes = agent_manifest.get('context_codes') or []

        if agent_manifest.get('code') and agent_manifest.get('code') != agent.code:
            warnings.append(_(
                'Manifest agent is "%s"; composition is applied to "%s".'
            ) % (agent_manifest['code'], agent.code))

        if replace_composition and context_codes:
            before_ids = set(agent.context_ids.ids)
            contexts = self.search([
                ('code', 'in', context_codes),
                ('active', '=', True),
            ])
            found_codes = set(contexts.mapped('code'))
            composition_stats['missing_codes'] = sorted(
                set(context_codes) - found_codes,
            )
            canonical_ids = self.normalize_context_ids(contexts)
            agent.write({'context_ids': [(6, 0, canonical_ids)]})
            composition_stats['applied'] = len(canonical_ids)
            composition_stats['removed'] = len(before_ids - set(canonical_ids))
            agent._sync_composition_and_cache()
        elif context_codes and not replace_composition:
            warnings.append(_(
                'Composition from manifest was not applied (replace composition is off).'
            ))

        return {
            'files': file_stats,
            'composition': composition_stats,
            'warnings': warnings,
        }

    def _build_contexts_zip_bytes(self, records, scope_label, agent=None):
        """Build contexts export ZIP payload (no UI). Returns None if empty."""
        records = records.exists()
        if not records:
            return None
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            manifest = self._build_export_manifest(
                records, scope_label, agent=agent,
            )
            zip_file.writestr(
                'manifest.json',
                json.dumps(manifest, indent=2, ensure_ascii=False),
            )
            for record in records:
                zip_path, ext = self._zip_path_for_record(record)
                zip_file.writestr(
                    zip_path,
                    self._export_content_for_record(record, ext),
                )
        zip_buffer.seek(0)
        return zip_buffer.getvalue()

    def _export_records_to_zip(self, records, scope_label, agent=None, title='Export'):
        records = records.exists()
        if not records:
            return pns_ui.open_json_export_empty_wizard(
                self.env,
                dialog_title=title,
                message=_('No contexts to export.'),
            )

        zip_filename = self._contexts_zip_filename(scope_label)
        payload = self._build_contexts_zip_bytes(records, scope_label, agent=agent)
        attachment = pns_ui.write_export_attachment(
            self.env, zip_filename, payload, 'application/zip',
        )
        return pns_ui.open_json_export_wizard(
            self.env,
            dialog_title=title,
            summary_text=_('%s context(s) exported to ZIP.') % len(records),
            count=len(records),
            attachment=attachment,
        )

    @api.model
    def export_all_to_zip(self):
        """Export all contexts to ZIP with manifest."""
        ensure_ai_admin(self.env)
        return self._export_records_to_zip(self.search([]), 'all', title='Export All')

    def action_export_selected(self):
        """Export selected list rows to ZIP."""
        ensure_ai_admin(self.env)
        active_ids = self.env.context.get('active_ids') or self.ids
        records = self.browse(active_ids).exists()
        if not records:
            raise UserError(_('Select at least one context to export.'))
        return records._export_records_to_zip(
            records, 'sel-%d' % len(records), title='Export Selected',
        )

    @api.model
    def export_agent_contexts_to_zip(self, agent):
        """Export all contexts composed by an AI agent (its M2M members)."""
        ensure_ai_admin(self.env)
        records = agent.context_ids
        return self._export_records_to_zip(
            records, 'agent-%s' % agent.code, agent=agent, title='Export Agent Contexts',
        )

    def action_export_selected_to_zip(self):
        """Export the selected context records to a ZIP file.

        Designed to be called from a server action bound to the tree view
        (binding_view_types='list'), so ``self`` contains only the records
        the user checked.
        """
        ensure_ai_admin(self.env)
        if not self:
            raise UserError(_('No contexts selected for export.'))
        return self._export_records_to_zip(
            self, 'selected', title=_('Export Selected Contexts'),
        )

    @api.model
    def export_agent_to_zip(self, agent):
        """Export agent manifest plus referenced contexts."""
        ensure_ai_admin(self.env)
        records = agent.context_ids
        return self._export_records_to_zip(
            records,
            'agent-%s' % agent.code,
            agent=agent,
            title='Export Bundle',
        )

    @api.model
    def import_custom_bootstrap(self):
        """
        Método interno para cargar archivos custom SOLO si no existen en BD.
        Usado por el hook post-init para inicializar ejemplos sin sobrescribir cambios del usuario.
        """
        ensure_ai_admin(self.env)
        import os
        import re
        
        from ..utils.ai_paths import module_kind_dir
        module_dir = self._get_module_path()
        _ctx_dir = module_kind_dir(module_dir, 'contexts')
        custom_dir = os.path.join(_ctx_dir, 'custom') if _ctx_dir else None
        
        imported_count = 0
        errors = []
        
        if custom_dir and os.path.exists(custom_dir):
            for root, dirs, files in os.walk(custom_dir):
                for filename in files:
                    if not filename.endswith(('.md', '.py')):
                        continue
                
                try:
                    code = os.path.splitext(filename)[0]
                    
                    # Verificar si YA existe (importante: bootstraps solo crean, no actualizan)
                    existing = self.search([('code', '=', code)], limit=1)
                    if existing:
                        continue
                        
                    filepath = os.path.join(root, filename)
                    # Relativo para guardar
                    rel_path = os.path.relpath(filepath, custom_dir)
                    with open(filepath, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    if not content.strip():
                        continue
                    
                    metadata = self._extract_metadata_from_content(content, filename)
                    _ctype = context_roles.canonical_type(metadata.get('tipo') or '')
                    vals = {
                        'code': code,
                        'description': metadata.get('description') or f"Contexto base: {filename}",
                        'content': content,
                        'context_type': _ctype,
                        'active': metadata.get('active', True),
                        'rel_path': rel_path,
                        'locale': self._infer_explicit_locale(
                            code, content, metadata,
                        ) or False,
                    }
                    
                    self.create(vals)
                    imported_count += 1
                    _logger.info("MCP: Bootstrap custom context: %s", code)
                    
                except Exception as e:
                    _logger.error("MCP: Error bootstrap custom %s: %s", filename, str(e))
                    errors.append(f"{filename}: {str(e)}")
                    
        return {'imported': imported_count, 'errors': errors}
    
    @api.model
    def _infer_explicit_locale(self, code, content, metadata=None):
        """Resolve the explicit locale for a context record (DB field ``locale``).

        Priority: metadata ``<locale_code>`` / front-matter → suffix in ``code``
        (``foo_es_ES``) → inner ``locale="xx_XX"`` on translation blocks (only
        when not a language-neutral fallback). Never guesses from filename alone.
        """
        metadata = metadata or {}
        if metadata.get('is_fallback'):
            return False
        loc = (metadata.get('locale') or '').strip()
        if loc:
            return str(loc).replace('-', '_')

        code = (code or '').strip()
        m = re.match(r'^.+_([a-z]{2})_([A-Z]{2})$', code)
        if m:
            return '%s_%s' % (m.group(1), m.group(2))

        text = content or ''
        cat = (metadata.get('tipo') or '').lower()
        if cat == 'locale' or 'term_mapping_definitions' in text:
            for pattern in (
                r'<mapping[^>]*\slocale=["\']([a-z]{2}_[A-Z]{2})["\']',
                r'<formatting_conventions[^>]*\slocale=["\']([a-z]{2}_[A-Z]{2})["\']',
            ):
                inner = re.search(pattern, text)
                if inner:
                    return inner.group(1)
        return False

    @api.model
    def _backfill_explicit_locale(self):
        """Fill empty ``locale`` on existing records (legacy imports without metadata)."""
        updated = 0
        for rec in self.with_context(active_test=False).search([
            ('locale', 'in', [False, '']),
        ]):
            meta = self._extract_metadata_from_content(
                rec.content or '', rec.rel_path or rec.code or '',
            )
            inferred = self._infer_explicit_locale(rec.code, rec.content or '', meta)
            if inferred:
                rec.with_context(skip_hardcoded_restrictions=True).write({
                    'locale': inferred,
                })
                updated += 1
        return updated

    @api.model
    def _extract_metadata_from_content(self, content, filename):
        """
        Extrae metadatos del contenido del archivo.
        Para .py: busca comentarios estructurados en la cabecera.
        Para .md: busca front matter YAML.
        
        Retorna un diccionario con: description, author, version, date_created, date_modified, created_by, modified_by, active, is_core
        """
        metadata = {
            'contexto': None,  # Código del contexto desde metadatos
            'description': None,
            'author': None,
            'version': None,
            'date_created': None,
            'date_modified': None,
            'created_by': None,
            'modified_by': None,
            'active': None,
            'category': None,
            'locale': None,   # Locale EXPLÍCITO (atributo del fichero, no del nombre)
            'is_fallback': None,
            'product_name': None,
            'vendor': None,
        }
        
        if filename.endswith('.py'):
            # Para Python: buscar comentarios estructurados en la cabecera
            # Formato esperado:
            # # -*- coding: utf-8 -*-
            # # Archivo: nombre.py
            # # Creado: YYYY-MM-DD [HH:mm:ss]
            # # Modificado: YYYY-MM-DD [HH:mm:ss]
            # # Descripción: texto descriptivo
            # # Autor: nombre del autor
            # # Versión: número de versión
            lines = content.split('\n')
            
            for line in lines[:30]:  # Primeras 30 líneas
                line = line.strip()
                if not line.startswith('#'):
                    # Si encontramos una línea que no es comentario, hemos terminado la cabecera
                    break
                
                comment = line[1:].strip()
                if not comment:
                    continue
                
                # Buscar campos estructurados con formato "Campo: valor"
                if ':' in comment:
                    key, value = comment.split(':', 1)
                    key = key.strip().lower()
                    value = value.strip()
                    
                    if key in ('descripción', 'description'):
                        metadata['description'] = value
                    elif key == 'autor' or key == 'author':
                        metadata['author'] = value
                    elif key == 'versión' or key == 'version':
                        metadata['version'] = value
                    elif key in ('creado', 'fecha de creación', 'date_created', 'created'):
                        # Extraer solo la fecha (YYYY-MM-DD) si hay hora
                        date_str = value.split()[0] if value else None
                        if date_str:
                            metadata['date_created'] = date_str
                    elif key in ('modificado', 'fecha de modificación', 'date_modified', 'modified', 'actualizado', 'updated'):
                        # Extraer solo la fecha (YYYY-MM-DD) si hay hora
                        date_str = value.split()[0] if value else None
                        if date_str:
                            metadata['date_modified'] = date_str
                    elif key in ('creado por', 'created_by', 'created by', 'creador'):
                        metadata['created_by'] = value
                    elif key in ('modificado por', 'modified_by', 'modified by', 'modificador'):
                        metadata['modified_by'] = value
                    elif key in ('activo', 'active'):
                        # Convertir a booleano
                        metadata['active'] = value.lower() in ('true', '1', 'yes', 'sí', 'si', 'verdadero')
                    elif key == 'tipo':
                        metadata['tipo'] = value.lower()
                    elif key in ('locale', 'locale_code', 'idioma'):
                        metadata['locale'] = value
                    elif key in ('is_fallback', 'fallback', 'es_fallback'):
                        metadata['is_fallback'] = value.lower() in ('true', '1', 'yes', 'sí', 'si', 'verdadero')
                    elif key in ('product_name', 'display_name', 'displayname'):
                        metadata['product_name'] = value
                    elif key == 'vendor':
                        metadata['vendor'] = value
        
        elif filename.endswith('.md'):
            # Para Markdown: buscar front matter YAML
            # Formato esperado:
            # ---
            # contexto: nombre_del_contexto
            # descripción: texto descriptivo
            # autor: nombre del autor
            # fecha_creacion: YYYY-MM-DD
            # fecha_modificacion: YYYY-MM-DD
            # version: número de versión
            # ---
            lines = content.split('\n')
            
            if lines and lines[0].strip() == '---':
                # Hay front matter YAML
                yaml_lines = []
                i = 1
                while i < len(lines) and lines[i].strip() != '---':
                    yaml_lines.append(lines[i])
                    i += 1
                
                # Parsear YAML simple (sin usar librería externa)
                for line in yaml_lines:
                    line = line.strip()
                    if ':' in line:
                        key, value = line.split(':', 1)
                        key = key.strip().lower()
                        value = value.strip().strip('"').strip("'")
                        
                        if key in ('contexto', 'code', 'codigo'):
                            metadata['contexto'] = value
                        elif key in ('descripción', 'descripcion', 'description'):
                            metadata['description'] = value
                        elif key in ('autor', 'author'):
                            metadata['author'] = value
                        elif key in ('versión', 'version'):
                            metadata['version'] = value
                        elif key in ('fecha_creacion', 'fecha_creación', 'date_created', 'created', 'creado'):
                            metadata['date_created'] = value
                        elif key in ('fecha_modificacion', 'fecha_modificación', 'date_modified', 'modified', 'modificado', 'actualizado', 'updated'):
                            metadata['date_modified'] = value
                        elif key in ('creado_por', 'creado por', 'created_by', 'created by', 'creador'):
                            metadata['created_by'] = value
                        elif key in ('modificado_por', 'modificado por', 'modified_by', 'modified by', 'modificador'):
                            metadata['modified_by'] = value
                        elif key in ('activo', 'active'):
                            # Convertir a booleano
                            metadata['active'] = value.lower() in ('true', '1', 'yes', 'sí', 'si', 'verdadero')
                        elif key == 'tipo':
                            metadata['tipo'] = value.lower()
                        elif key in ('locale', 'locale_code', 'idioma'):
                            metadata['locale'] = value
                        elif key in ('is_fallback', 'fallback', 'es_fallback'):
                            metadata['is_fallback'] = value.lower() in ('true', '1', 'yes', 'sí', 'si', 'verdadero')
                        elif key in ('is_global', 'global', 'universal'):
                            metadata['is_global'] = value.lower() in ('true', '1', 'yes', 'sí', 'si', 'verdadero')
                        elif key in ('agent_codes', 'agent_code', 'agentes'):
                            metadata['agent_codes'] = value
                        elif key in ('product_name', 'display_name', 'displayname'):
                            metadata['product_name'] = value
                        elif key == 'vendor':
                            metadata['vendor'] = value
            
            # Si no hay front matter, buscar primer título o párrafo como descripción
            if not metadata['description']:
                for line in lines[:30]:
                    line = line.strip()
                    if line.startswith('#'):
                        title = line.lstrip('#').strip()
                        if title:
                            metadata['description'] = title
                            break
                    elif line and not line.startswith('```') and not line.startswith('---'):
                        if len(line) > 10:
                            metadata['description'] = line[:200]
                            break
        
        elif filename.endswith('.xml'):
            # Para XML: buscar etiquetas dentro de <metadata>
            import re
            
            # Buscar el bloque <metadata>...</metadata> (flexible con atributos)
            metadata_match = re.search(r'<metadata[^>]*>(.*?)</metadata>', content, re.DOTALL)
            if metadata_match:
                metadata_block = metadata_match.group(1)
                
                # Extraer etiquetas comunes (flexibles con atributos)
                patterns = {
                    'contexto': r'<code[^>]*>(.*?)</code>',
                    'description': r'<description[^>]*>(.*?)</description>',
                    'author': r'<author[^>]*>(.*?)</author>',
                    'version': r'<version[^>]*>(.*?)</version>',
                    'date_created': r'<created_at[^>]*>(.*?)</created_at>',
                    'date_modified': r'<modified_at[^>]*>(.*?)</modified_at>',
                    'created_by': r'<created_by[^>]*>(.*?)</created_by>',
                    'modified_by': r'<modified_by[^>]*>(.*?)</modified_by>',
                    'active': r'<active[^>]*>(.*?)</active>',
                    'tipo': r'<tipo[^>]*>(.*?)</tipo>',
                    'locale': r'<locale(?:_code)?[^>]*>(.*?)</locale(?:_code)?>',
                    'is_fallback': r'<is_fallback[^>]*>(.*?)</is_fallback>',
                    'agent_codes': r'<agent_codes[^>]*>(.*?)</agent_codes>',
                    'agent_code': r'<agent_code[^>]*>(.*?)</agent_code>',
                    'product_name': r'<product_name[^>]*>(.*?)</product_name>',
                    'display_name': r'<display_name[^>]*>(.*?)</display_name>',
                    'vendor': r'<vendor[^>]*>(.*?)</vendor>',
                }
                
                for key, pattern in patterns.items():
                    match = re.search(pattern, metadata_block, re.DOTALL)
                    if match:
                        value = match.group(1).strip()
                        if key == 'active':
                            metadata[key] = value.lower() in ('true', '1', 'yes', 'sí', 'si', 'verdadero')
                        elif key == 'tipo':
                            metadata[key] = value.lower()
                        elif key in ('is_fallback', 'fallback'):
                             metadata['is_fallback'] = value.lower() in ('true', '1', 'yes', 'sí', 'si', 'verdadero')
                        else:
                            metadata[key] = value
                if not metadata.get('product_name') and metadata.get('display_name'):
                    metadata['product_name'] = metadata['display_name']

        elif filename.endswith('.json'):
            # Discovery routing rows: a single JSON object with target + triggers.
            # {"code","target","tipo":"discovery","triggers":[...],
            #  "priority":int,"soft_depends":[...],"locale_code","source_module"}
            try:
                data = json.loads(content or '{}')
            except (ValueError, TypeError):
                data = {}
            if isinstance(data, dict):
                if data.get('code'):
                    metadata['contexto'] = data['code']
                if data.get('description'):
                    metadata['description'] = data['description']
                if data.get('tipo'):
                    metadata['tipo'] = str(data.get('tipo')).lower()
                loc = data.get('locale') or data.get('locale_code')
                if loc:
                    metadata['locale'] = loc
                if data.get('source_module'):
                    metadata['source_module'] = data['source_module']
                if data.get('active') is not None:
                    metadata['active'] = bool(data['active'])
                metadata['discovery_target'] = data.get('target') or ''
                metadata['discovery_target_kind'] = (
                    data.get('target_kind') or 'domain'
                )
                triggers = data.get('triggers') or []
                if isinstance(triggers, str):
                    triggers = [t.strip() for t in triggers.split(',') if t.strip()]
                metadata['discovery_triggers'] = json.dumps(
                    [str(t).strip() for t in triggers if str(t).strip()],
                    ensure_ascii=False,
                )
                metadata['discovery_priority'] = int(data.get('priority') or 0)
                soft = data.get('soft_depends') or []
                if isinstance(soft, str):
                    soft = [s.strip() for s in soft.split(',') if s.strip()]
                metadata['discovery_soft_depends'] = ','.join(
                    str(s).strip() for s in soft if str(s).strip()
                )

        return metadata
    
    @api.model
    def _extract_description_from_content(self, content, filename):
        """
        Extrae una descripción del contenido del archivo.
        Usa _extract_metadata_from_content y retorna solo la descripción.
        """
        metadata = self._extract_metadata_from_content(content, filename)
        if metadata['description']:
            return metadata['description']
        
        # Fallback: usar nombre del archivo
        return f"Contexto importado desde {filename}"

