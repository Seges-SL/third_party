# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""ai.context: discovery entries, the reply-language directive and the per-turn bundle."""

import json
from odoo import (
    models,
    api,
)
from ..utils import context_roles
import logging

_logger = logging.getLogger(__name__)


class AIContextDiscovery(models.Model):
    _inherit = 'ai.context'

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
        rows = self.with_context(active_test=False).search(self.ownership_read_domain() + [
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
            contexts = self.filter_visible_for_user(
                agent.context_ids.filtered('active')
            ).sorted(key=lambda c: (c.context_type or '', c.code))
        else:
            contexts = self.search(
                self.ownership_read_domain()
                + [('active', '=', True),
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
            self.ownership_read_domain() + [
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
