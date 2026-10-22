# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""Turn discovery: domain index, decision pack, topic continuity, skill domains."""

import logging

from odoo.exceptions import RedirectWarning, UserError

_logger = logging.getLogger(__name__)


class DiscoveryMixin:
    """Part of ``AgentEngine``; only used through it."""

    def _domain_index_inject_enabled(self):
        from .domain_index import INJECT_ICP_KEY, icp_flag_enabled
        try:
            ICP = self.env['ir.config_parameter'].sudo()
            raw = ICP.get_param(INJECT_ICP_KEY, 'True')
            return icp_flag_enabled(raw, default=True)
        except Exception:
            return True

    def _domain_index_entries(self, user_locale=None):
        """Routing entries composed from ``ai.context`` discovery rows (DB)."""
        if 'ai.context' not in self.env:
            return []
        return self.env['ai.context'].sudo().get_discovery_entries(user_locale)

    def _domain_index_inject_bodies(self, codes, user_locale=None):
        """Compile locale-aware context bodies for matched domain codes."""
        if not codes or 'ai.context' not in self.env:
            return ''
        Context = self.env['ai.context'].sudo()
        records = Context.browse()
        for code in codes:
            try:
                rec = Context.get_context_for_country(code, user_locale=user_locale)
            except Exception:
                rec = Context.search(Context.ownership_read_domain() + [
                    ('active', '=', True),
                    '|', ('code', '=', code), ('base_code', '=', code),
                ], limit=1)
            if rec:
                records |= rec
        if not records:
            return ''
        parts = Context.assemble_context_parts(
            records, user_locale=user_locale,
        )
        return '\n\n'.join(p for p in (parts or []) if p)

    def _decision_pack_descriptions(self, entries, user_locale=None):
        """Target code → context description. Empty description stays empty."""
        if 'ai.context' not in self.env:
            return {}
        Context = self.env['ai.context'].sudo()
        out = {}
        for entry in entries or []:
            code = str(entry.get('code') or '').strip()
            if not code or code in out:
                continue
            desc = ''
            try:
                rec = Context.get_context_for_country(
                    code, user_locale=user_locale,
                )
            except Exception:
                rec = Context.browse()
            if rec:
                desc = (rec.description or '').strip()
            out[code] = desc
        return out

    def _maybe_decision_pack(self, message, domain_entries, matches, user_locale=None):
        """Choice against the live pack list when this sentence has no unique winner.

        Returns a dict. ``called`` is False when the word list already won,
        no decision provider is configured, or the catalogue is over the cap.
        A failed HTTP call is ``called`` and not ``accepted``.
        """
        import time
        empty = {
            'called': False,
            'accepted': False,
            'choice': None,
            'confidence': None,
            'codes': None,
            'model': None,
            'usage': None,
            'elapsed_ms': 0.0,
        }
        from .domain_index import (
            PACK_CHOICE_INSTRUCTIONS,
            accept_pack_choice,
            build_pack_choice_criteria,
            codes_for_pack_choice,
            sentence_has_unique_winner,
        )
        if sentence_has_unique_winner(matches):
            return empty
        Engine = self.env['ai.execution.engine']
        if not self._agent_code:
            return empty
        try:
            chain = Engine.get_providers_for_agent(
                self._agent_code, need='decision',
            )
        except (UserError, RedirectWarning):
            return empty
        if not chain:
            return empty
        criteria = build_pack_choice_criteria(
            domain_entries,
            self._decision_pack_descriptions(domain_entries, user_locale),
        )
        if not criteria:
            return empty
        t0 = time.perf_counter()
        provider, answer = Engine._choose(
            message or '', criteria, PACK_CHOICE_INSTRUCTIONS,
            self._agent_code,
        )
        elapsed = (time.perf_counter() - t0) * 1000.0
        model = (provider.model_id.name if provider.model_id else '') or (
            provider.model_name or ''
        )
        if answer is None:
            empty.update({
                'called': True,
                'model': model or None,
                'elapsed_ms': elapsed,
            })
            return empty
        chosen = accept_pack_choice(
            answer, criteria, provider.decision_min_confidence,
        )
        reported = answer.get('model') or model
        if not chosen:
            return {
                'called': True,
                'accepted': False,
                'choice': answer.get('choice'),
                'confidence': answer.get('confidence'),
                'codes': None,
                'model': reported,
                'usage': answer.get('usage') or {},
                'elapsed_ms': elapsed,
            }
        return {
            'called': True,
            'accepted': True,
            'choice': chosen,
            'confidence': answer.get('confidence'),
            'codes': codes_for_pack_choice(domain_entries, chosen),
            'model': reported,
            'usage': answer.get('usage') or {},
            'elapsed_ms': elapsed,
        }

    def _maybe_topic_continuity(self, message):
        """Yes/none: does this sentence continue the previous subject?

        Called only when the word list hit nothing and the previous turn
        left packs or a dataset. Yes keeps the sticky list. No (or no
        provider, or a failed call) drops packs and the previous rows.
        """
        import time
        empty = {
            'called': False,
            'accepted': False,
            'choice': None,
            'confidence': None,
            'model': None,
            'usage': None,
            'elapsed_ms': 0.0,
        }
        from .domain_index import (
            TOPIC_CHOICE_CRITERIA,
            TOPIC_CHOICE_INSTRUCTIONS,
            accept_topic_same,
            topic_choice_text,
        )
        Engine = self.env['ai.execution.engine']
        if not self._agent_code:
            return empty
        try:
            chain = Engine.get_providers_for_agent(
                self._agent_code, need='decision',
            )
        except (UserError, RedirectWarning):
            return empty
        if not chain:
            return empty
        t0 = time.perf_counter()
        provider, answer = Engine._choose(
            topic_choice_text(message, getattr(self, '_turn_history', None)),
            TOPIC_CHOICE_CRITERIA, TOPIC_CHOICE_INSTRUCTIONS,
            self._agent_code,
        )
        elapsed = (time.perf_counter() - t0) * 1000.0
        model = (provider.model_id.name if provider.model_id else '') or (
            provider.model_name or ''
        )
        if answer is None:
            empty.update({
                'called': True,
                'model': model or None,
                'elapsed_ms': elapsed,
            })
            return empty
        accepted = accept_topic_same(
            answer, provider.decision_min_confidence,
        )
        return {
            'called': True,
            'accepted': accepted,
            'choice': answer.get('choice'),
            'confidence': answer.get('confidence'),
            'model': answer.get('model') or model,
            'usage': answer.get('usage') or {},
            'elapsed_ms': elapsed,
        }

    def _topic_continuity_without_inject(self, message, user_locale=None):
        """Score the sentence; do not append pack bodies.

        The monolith already has every linked pack in the cache. Discovery
        still decides whether the previous dataset belongs on this turn:
        named other packs with no overlap → drop it; a miss with leftover
        state → same-subject Choice.
        """
        from .domain_index import (
            TARGET_KIND_DOMAIN,
            age_domain_codes,
            discovery_step_summary,
            filter_entries_by_kind,
            hold_domain_codes,
            match_domains,
            needs_topic_continuity,
            needs_topic_switch_check,
            union_domain_codes,
        )
        entries = self._domain_index_entries(user_locale=user_locale) or []
        domain_entries = filter_entries_by_kind(entries, TARGET_KIND_DOMAIN)
        result = match_domains(message, domain_entries)
        word_codes = list(result.get('codes') or [])
        prior = list(getattr(self, '_prior_domain_codes', None) or [])
        topic = {
            'called': False,
            'accepted': False,
            'choice': None,
            'confidence': None,
            'model': None,
            'usage': {},
            'elapsed_ms': 0.0,
        }
        route = 'deterministic'
        declined = False
        if needs_topic_continuity(
            word_codes, prior, getattr(self, '_has_prior_query', False),
        ):
            topic = self._maybe_topic_continuity(message)
            route = 'topic'
            declined = not topic.get('accepted')
            if declined:
                self._prior_domain_codes = []
                self._prior_domain_ages = {}
                self._reuse_prior_query = False
        same_subject = False
        if needs_topic_switch_check(
            word_codes, prior, getattr(self, '_has_prior_query', False),
        ):
            topic = self._maybe_topic_continuity(message)
            route = 'topic'
            same_subject = bool(topic.get('accepted'))
            declined = not same_subject
        merged = union_domain_codes(
            word_codes, getattr(self, '_prior_domain_codes', None) or [],
            keep_disjoint=same_subject,
        )
        if (
            prior
            and (merged.get('mode') or '') == 'injected'
            and not (merged.get('carried') or [])
        ):
            self._reuse_prior_query = False
        elif (
            not prior
            and word_codes
            and getattr(self, '_has_prior_query', False)
        ):
            # Monolith may have rows and no remembered packs. Naming a
            # pack is a new subject for that leftover dataset.
            self._reuse_prior_query = False
        codes = hold_domain_codes(
            merged.get('codes') or [], getattr(self, '_held_domain_codes', None),
        )
        ages = age_domain_codes(
            codes,
            list(merged.get('matched') or []),
            getattr(self, '_prior_domain_ages', None) or {},
        )
        self._injected_domain_codes = list(codes)
        self._injected_domain_ages = dict(ages)
        elapsed_ms = (
            float(result.get('elapsed_ms') or 0.0)
            + float(topic.get('elapsed_ms') or 0.0)
        )
        usage = topic.get('usage') or {}
        summary = discovery_step_summary(
            route,
            'Domains: (none) · Services: (none)',
            elapsed_ms,
            choice=topic.get('choice'),
            confidence=topic.get('confidence'),
            declined=declined,
        )
        try:
            self._mcp_log(
                operation_type='read',
                tool_name='domain_index',
                request_type='system',
                user_prompt=(message or '')[:480],
                agent_llm=topic.get('model') if topic.get('called') else None,
                prompt_tokens=usage.get('input_tokens'),
                completion_tokens=usage.get('output_tokens'),
                prompt_data={
                    'codes': [],
                    'matched': word_codes,
                    'inject': False,
                    'route': route,
                    'choice': topic.get('choice'),
                    'confidence': topic.get('confidence'),
                    'accepted': bool(topic.get('accepted')),
                    'elapsed_ms': round(elapsed_ms, 3),
                },
                result_summary=summary[:480],
            )
        except Exception:
            _logger.debug(
                'AgentEngine: topic log without inject skipped', exc_info=True,
            )
        return ''

    def _domain_index_runtime_hint(self, user_message, user_locale=None):
        """Match + Historial IA + turn-scoped body injection (single flag).

        Domain hits load pack bodies (cap 1–2). ``api_server`` hits append a
        short post-catalogue hint and do not consume that budget.
        """
        if not user_message or not str(user_message).strip():
            self._injected_domain_codes = []
            self._injected_domain_ages = {}
            return ''
        if not self._domain_index_inject_enabled():
            self._injected_domain_codes = []
            self._injected_domain_ages = {}
            # Monolith: every linked pack is already in the cache. Pack
            # routing stays off. Same-subject vs new-subject still matters
            # for the previous dataset, which does not live in that cache.
            return self._topic_continuity_without_inject(
                str(user_message), user_locale=user_locale,
            )
        from .domain_index import (
            DEFAULT_MAX_SERVICES,
            TARGET_KIND_API_SERVER,
            TARGET_KIND_DOMAIN,
            age_domain_codes,
            discovery_step_summary,
            filter_entries_by_kind,
            format_codes_with_age,
            format_inject_header,
            format_service_detect_hint,
            hold_domain_codes,
            match_domains,
            needs_topic_continuity,
            needs_topic_switch_check,
            union_domain_codes,
        )
        entries = self._domain_index_entries(user_locale=user_locale) or []
        msg = str(user_message)
        domain_entries = filter_entries_by_kind(entries, TARGET_KIND_DOMAIN)
        service_entries = filter_entries_by_kind(entries, TARGET_KIND_API_SERVER)
        result = match_domains(msg, domain_entries)
        service_result = match_domains(
            msg, service_entries, max_packs=DEFAULT_MAX_SERVICES,
        )
        word_codes = list(result.get('codes') or [])
        topic = {
            'called': False,
            'accepted': False,
            'choice': None,
            'confidence': None,
            'model': None,
            'usage': {},
            'elapsed_ms': 0.0,
        }
        decision = dict(topic)
        if needs_topic_continuity(
            word_codes,
            getattr(self, '_prior_domain_codes', None),
            getattr(self, '_has_prior_query', False),
        ):
            # Miss + leftover state: refine vs new subject. Not a pack Choice.
            topic = self._maybe_topic_continuity(msg)
            if not topic.get('accepted'):
                self._prior_domain_codes = []
                self._prior_domain_ages = {}
                self._reuse_prior_query = False
        else:
            decision = self._maybe_decision_pack(
                msg, domain_entries, result.get('matches') or [],
                user_locale=user_locale,
            )
        if decision.get('accepted') and decision.get('codes'):
            matched = list(decision['codes'])
        else:
            matched = list(word_codes)
        prior_before = list(getattr(self, '_prior_domain_codes', None) or [])
        same_subject = False
        if needs_topic_switch_check(
            matched, prior_before, getattr(self, '_has_prior_query', False),
        ):
            topic = self._maybe_topic_continuity(msg)
            same_subject = bool(topic.get('accepted'))
        for code in getattr(self, '_skill_domain_codes', None) or []:
            if code not in matched:
                matched.append(code)
        merged = union_domain_codes(
            matched, getattr(self, '_prior_domain_codes', None) or [],
            keep_disjoint=same_subject,
        )
        codes = hold_domain_codes(
            merged.get('codes') or [], getattr(self, '_held_domain_codes', None),
        )
        carried = list(merged.get('carried') or [])
        mode = merged.get('mode') or 'none'
        # Named other packs and shared none: also drop the previous dataset.
        if prior_before and mode == 'injected' and not carried:
            self._reuse_prior_query = False
        ages = age_domain_codes(
            codes,
            list(merged.get('matched') or []),
            getattr(self, '_prior_domain_ages', None) or {},
        )
        self._injected_domain_codes = list(codes)
        self._injected_domain_ages = dict(ages)
        service_codes = list(service_result.get('codes') or [])
        elapsed_ms = (
            float(result.get('elapsed_ms') or 0.0)
            + float(service_result.get('elapsed_ms') or 0.0)
            + float(decision.get('elapsed_ms') or 0.0)
            + float(topic.get('elapsed_ms') or 0.0)
        )
        codes_txt = format_codes_with_age(ages, codes) if codes else '(none)'
        if not codes:
            domain_part = 'Domains: (none)'
            body = ''
        else:
            body = self._domain_index_inject_bodies(codes, user_locale=user_locale)
            if not body:
                mode = 'inject_miss'
            domain_part = 'Domains: %s' % codes_txt
        if service_codes:
            services_txt = ', '.join(service_codes)
            if mode == 'none':
                mode = 'service'
        else:
            services_txt = '(none)'
        domain_part = '%s · Services: %s' % (domain_part, services_txt)
        if topic.get('called'):
            route = 'topic'
            choice = topic.get('choice')
            confidence = topic.get('confidence')
            declined = not topic.get('accepted')
            usage = topic.get('usage') or {}
            model = topic.get('model')
        elif decision.get('called'):
            route = 'decision'
            choice = decision.get('choice')
            confidence = decision.get('confidence')
            declined = not decision.get('accepted')
            usage = decision.get('usage') or {}
            model = decision.get('model')
        else:
            route = 'deterministic'
            choice = None
            confidence = None
            declined = False
            usage = {}
            model = None
        summary = discovery_step_summary(
            route,
            domain_part,
            elapsed_ms,
            choice=choice,
            confidence=confidence,
            declined=declined,
        )
        self._mcp_log(
            operation_type='read',
            tool_name='domain_index',
            request_type='system',
            user_prompt=msg[:480],
            agent_llm=model,
            prompt_tokens=usage.get('input_tokens'),
            completion_tokens=usage.get('output_tokens'),
            prompt_data={
                'codes': codes,
                'ages': ages,
                'matched': list(merged.get('matched') or []),
                'carried': carried,
                'service_codes': service_codes,
                'elapsed_ms': round(elapsed_ms, 3),
                'matches': result.get('matches') or [],
                'service_matches': service_result.get('matches') or [],
                'inject': True,
                'mode': mode,
                'body_chars': len(body or ''),
                'route': route,
                'choice': choice,
                'confidence': confidence,
                'accepted': not declined if route != 'deterministic' else False,
            },
            result_summary=summary[:480],
        )
        if codes or service_codes:
            _logger.info(
                'AgentEngine: domain_index mode=%s codes=%s services=%s '
                'elapsed_ms=%.2f',
                mode, codes, service_codes, elapsed_ms,
            )
        parts = []
        if body:
            parts.append(
                format_inject_header(codes, elapsed_ms, carried=carried) + body
            )
        service_hint = format_service_detect_hint(
            service_result.get('matches') or [],
        )
        if service_hint:
            parts.append(service_hint)
        return ''.join(parts)

    def _skill_context_code_candidates(self, skill):
        """Codes declared on the skill (code + base_code). No catalog list."""
        codes = []
        if not skill:
            return codes
        contexts = skill.context_ids.filtered('active') if skill.context_ids else skill.context_ids
        for rec in contexts:
            for raw in (rec.code, getattr(rec, 'base_code', None) or ''):
                code = (raw or '').strip()
                if code and code not in codes:
                    codes.append(code)
        return codes

    def _remember_skill_domain_codes(self, skill):
        """Keep conversation packs + skill domain context_ids (injectable)."""
        self._skill_domain_codes = []
        if not skill or not self._domain_index_inject_enabled():
            return
        from .domain_index import (
            indexed_codes_from_entries,
            skill_domain_context_codes,
        )
        indexed = indexed_codes_from_entries(
            self._domain_index_entries() or [],
        )
        self._skill_domain_codes = skill_domain_context_codes(
            self._skill_context_code_candidates(skill),
            indexed,
        )
        self._apply_carried_and_skill_domain_union()

    def _apply_carried_and_skill_domain_union(self):
        """Union prior + skill domain codes when this turn skips get_system_prompt."""
        from .domain_index import (
            age_domain_codes,
            hold_domain_codes,
            union_domain_codes,
        )
        extra = list(getattr(self, '_skill_domain_codes', None) or [])
        merged = union_domain_codes(
            extra, getattr(self, '_prior_domain_codes', None) or [],
            keep_disjoint=True,
        )
        codes = hold_domain_codes(
            merged.get('codes') or [], getattr(self, '_held_domain_codes', None),
        )
        ages = age_domain_codes(
            codes,
            list(merged.get('matched') or []),
            getattr(self, '_prior_domain_ages', None) or {},
        )
        self._injected_domain_codes = list(codes)
        self._injected_domain_ages = dict(ages)

    def _domain_codes_event(self):
        return {
            'event': 'domain_codes',
            'codes': list(getattr(self, '_injected_domain_codes', None) or []),
            'ages': dict(getattr(self, '_injected_domain_ages', None) or {}),
        }

    def _domain_index_catalog_hint(self):
        """Compact index listing when MCP has no user query yet."""
        if not self._domain_index_inject_enabled():
            return ''
        from .domain_index import format_index_catalog
        entries = self._domain_index_entries()
        return format_index_catalog(entries)
