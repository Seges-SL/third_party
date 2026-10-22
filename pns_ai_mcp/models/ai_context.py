# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""ai.context — reusable knowledge directives (prompts) for AI agents."""

import os
import re
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
from ..utils import context_roles
from ..utils.knowledge_ownership import (
    apply_create_ownership,
    assert_writer_can_write_records,
    factory_lock_open,
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
        agent = env['ai.agent'].search([('code', '=', 'pns_ai_admin')])
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
            ('own', 'Own'),
            ('imported', 'Imported'),
            ('inserted', 'Inserted'),
            ('extra', 'Extra'),
        ],
        string='Origin',
        compute='_compute_composition_link',
        search='_search_composition_origin',
        help="Why this row is on the current agent. Own: from this agent's module. "
             "Imported: from another module; this agent asks for it. "
             "Inserted: from another module; that module puts it in this agent. "
             "Extra: no module manages it; a person added it. "
             "Empty source_module is extra.",
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
        """Type labels are tokens, never translated."""
        res = super().fields_get(allfields=allfields, attributes=attributes)
        info = res.get('context_type')
        if info and info.get('selection'):
            info['selection'] = list(context_roles.TYPE_SELECTION)
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

    # ── Discover role: domain-index routing composed from DB (locale-aware) ──

    
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
    def _record_context_usage(self, context_code):
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
        The seed flag counts only inside sudo() or as the superuser. A
        context key from RPC is not a grant.
        """
        if not factory_lock_open(self.env):
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

        The seed flag stays open for import, ``-u`` and uninstall hooks
        only when the environment is sudo or the superuser.
        """
        if not factory_lock_open(self.env):
            assert_writer_can_write_records(self, self.env)
            locked = self.filtered(lambda rec: rec._is_shipped_factory_locked())
            if locked:
                raise UserError(_(
                    'This context cannot be deleted. System (core) packs and '
                    'factory files of an installed module stay until the '
                    'module is uninstalled or the source file is removed.'
                ))
        return super(AIContext, self).unlink()

    # Maps discovery left the engine; pns_geo owns discovery_geo*.
    _ENGINE_RETIRED_DISCOVERY_GEO_CODES = (
        'discovery_geo',
        'discovery_geo_es_ES',
    )

    @api.model
    def _unlink_retired_engine_discovery_geo(self):
        """Drop engine-owned map discovery leftover (O14 -u, no 3.1.* migrate)."""
        rows = self.sudo().with_context(
            skip_hardcoded_restrictions=True,
            tracking_disable=True,
            active_test=False,
        ).search([
            ('code', 'in', list(self._ENGINE_RETIRED_DISCOVERY_GEO_CODES)),
            ('source_module', '=', 'pns_ai_mcp'),
            ('owner_id', '=', False),
        ])
        if not rows:
            return self.browse()
        n = len(rows)
        rows.unlink()
        _logger.info(
            'MCP: unlinked leftover engine discovery_geo rows: %s', n,
        )
        return rows

    @api.model
    def _retire_generic_self_row(self):
        """Unlink every agent from retired ``self`` / locale clones and delete.

        Covers ``self``, ``self_es_ES``, ``self_en_US``, ``self_retired``, any
        row whose ``base_code`` is ``self``, and leftovers under
        ``contexts/domain/self/``. Does not touch ``self_chatboo`` / ``self_mcp``.
        """
        from ..utils.agent_identity import is_retired_self_pack_code
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


    


