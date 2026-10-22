# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""Skills in a turn: slash command, resolve, args policy, parameter normalization."""

import json
import logging

from .llm_usage import add_usage, normalize_usage

_logger = logging.getLogger(__name__)


class SkillsMixin:
    """Part of ``AgentEngine``; only used through it."""

    def _skill_args_policy(self, skill):
        from .skill_help import normalize_args_policy
        has_params = bool(
            (getattr(skill, 'param_schema', '') or '').strip()
            or (getattr(skill, 'arg_hint', '') or '').strip()
        )
        return normalize_args_policy(
            getattr(skill, 'args_policy', None),
            has_params=has_params,
        )

    def _emit_slash_help(self, meta, session_id, agent_code, provider,
                         provider_id, *, skill_code=None, rejected=False,
                         asking=False, reject_reason=''):
        """Deterministic help / reject / ask card. Never calls the LLM."""
        from .skill_help import build_slash_help_markdown
        card = build_slash_help_markdown(
            meta, rejected=rejected, reject_reason=reject_reason, asking=asking,
        )
        yield {'event': 'replace', 'content': card}
        if asking and skill_code:
            yield {
                'event': 'active_skill',
                'code': skill_code,
                'params': {'awaiting_args': True, 'state': {}},
            }
        else:
            yield {'event': 'active_skill', 'code': None, 'params': {}}
        yield self._done_event(
            session_id, agent_code=agent_code,
            provider=provider, provider_id=provider_id,
            skill_code=skill_code,
            local=True,
        )

    def _param_provider_chain(self, provider, agent_code):
        """Turn provider first, then the agent's conversation chain by priority."""
        chain = [provider] if provider is not None else []
        try:
            provs = self.env['ai.execution.engine'].get_providers_for_agent(
                agent_code, need='conversation',
            )
        except Exception as exc:
            _logger.debug('param norm: no provider chain for %s: %s', agent_code, exc)
            provs = []
        seen = {getattr(p, 'id', None) for p in chain}
        for p in provs or []:
            pid = getattr(p, 'id', None)
            if pid in seen:
                continue
            seen.add(pid)
            chain.append(p)
        return chain

    def _normalize_skill_params(self, skill, args, agent_code,
                                provider=None, provider_id=None):
        """LLM fallback for free-text args when deterministic parse leaves holes.

        Opt-in via ``param_schema``. Order:
        1. ``parse_skill_arguments`` + ``clave=valor`` + ordinals onto empty
           schema keys + ``enrich_params_with_dates`` (zero cost)
        2. If schema keys still missing and unbound prose remains → one
           short LLM JSON call
        3. LLM ``_reject`` is not a veto: merge with deterministic fill.
           Reject only when leftover prose still has no formal key
           (caller paints help; never falls through to ReAct)
        Without a formal schema, leftover text travels as ``arguments``.
        """
        raw = (args or '').strip()
        # Help/?/ayuda: never call the hybrid LLM.
        from .skill_dates import skill_args_are_help
        from .skill_runtime import finalize_skill_params, skill_args_unmapped
        if skill_args_are_help(raw):
            return {
                'arguments': raw,
                'periodo': raw,
                'lugar': raw,
            }
        policy = self._skill_args_policy(skill)
        if policy == 'none':
            return {'_skill_args_reject': True} if raw else None
        schema_txt = (getattr(skill, 'param_schema', '') or '').strip()
        schema = None
        if schema_txt:
            try:
                schema = json.loads(schema_txt)
            except Exception:
                _logger.warning(
                    'Skill %s: param_schema is not valid JSON; ignored.',
                    getattr(skill, 'code', '?'),
                )
                schema = None
        if not isinstance(schema, dict) or not schema:
            return None
        if not raw:
            return finalize_skill_params({}, schema, env=self.env)

        from .skill_runtime import (
            apply_schema_ordinals,
            attach_schema_choices,
            build_param_extraction_prompt,
            deterministic_schema_hits,
            enrich_params_with_dates,
            leftover_after_ordinals,
            hybrid_unresolved_text,
            finalize_skill_params,
            merge_hybrid_params,
            parse_and_validate_params,
            parse_skill_arguments,
            schema_needs_ai_resolution,
        )

        params = parse_skill_arguments(raw)
        enrich_params_with_dates(params)
        params, bound_map = apply_schema_ordinals(params, schema, raw)
        enrich_params_with_dates(params)
        leftover = leftover_after_ordinals(raw, params, bound_map, schema)
        unresolved = hybrid_unresolved_text(raw, leftover, bound_map)
        # Deterministic-only extras we can already hand to the sandbox.
        # Temporal keys only win when canonical (YYYY-MM / YYYY-MM-DD) so a
        # leftover phrase never blocks the LLM from resolving it.
        det = deterministic_schema_hits(params, schema, raw)
        if not schema_needs_ai_resolution(
            params, schema, raw, leftover=leftover,
        ):
            if skill_args_unmapped(raw, det, schema, policy):
                return {'_skill_args_reject': True}
            return finalize_skill_params(det or {}, schema, env=self.env) or None

        cached = None
        lookup = getattr(skill, '_lookup_param_cache', None)
        if unresolved and callable(lookup):
            try:
                cached = lookup(unresolved)
            except Exception as exc:
                _logger.debug(
                    'param cache lookup skipped for %s: %s',
                    getattr(skill, 'code', '?'), exc,
                )
                cached = None
        if cached is not None:
            merged = merge_hybrid_params(
                det, cached, schema, raw, policy, env=self.env,
            )
            if isinstance(merged, dict) and merged.get('_skill_args_reject'):
                return merged
            still_ai = schema_needs_ai_resolution(
                merged, schema, raw, leftover=unresolved,
            )
            if not still_ai:
                try:
                    self._mcp_log(
                        operation_type='read',
                        tool_name='skill_param_cache',
                        prompt_data={
                            'skill': getattr(skill, 'code', '?'),
                            'arguments': raw,
                            'leftover': unresolved,
                            'cached': cached,
                            'merged': merged,
                        },
                        result_summary=(
                            'Skill param cache (%s): %s' % (
                                getattr(skill, 'code', '?'),
                                unresolved[:80],
                            )
                        )[:480],
                        request_type='tool',
                    )
                except Exception:
                    pass
                return finalize_skill_params(merged, schema, env=self.env)
            det = dict(merged or {})

        chain = self._param_provider_chain(provider, agent_code)
        if not chain:
            if skill_args_unmapped(raw, det, schema, policy):
                return {'_skill_args_reject': True}
            return finalize_skill_params(det or {}, schema, env=self.env) or None

        attach_schema_choices(schema, self.env)
        from .agent_engine import HYBRID_PARAM_MAX_TOKENS, llm_json_completion_result
        system_prompt, user_prompt = build_param_extraction_prompt(
            schema, unresolved, locale=self._resolve_user_locale(),
        )
        # First provider whose reply parses wins. An empty or unreadable
        # reply goes to the next one; a ``_reject`` is an answer.
        prov = None
        norm = None
        text = ''
        piece = {}
        tried = []
        for cand in chain:
            result = llm_json_completion_result(
                cand, system_prompt, user_prompt,
                max_tokens=HYBRID_PARAM_MAX_TOKENS,
            )
            spent = normalize_usage((result or {}).get('usage') or {})
            self._accumulate_side_usage(spent)
            piece = add_usage(piece, spent) if spent else piece
            text = (result or {}).get('content') or ''
            tried.append(getattr(cand, 'name', '') or '')
            norm = parse_and_validate_params(text, schema)
            if norm is not None:
                prov = cand
                break
        if (
            not norm
            or (isinstance(norm, dict) and norm.get('_skill_args_reject'))
        ):
            _logger.info(
                'Skill %s: hybrid LLM returned nothing (raw=%r text=%r)',
                getattr(skill, 'code', '?'), raw[:80], (text or '')[:120],
            )
        merged = merge_hybrid_params(
            det, norm, schema, raw, policy, env=self.env,
        )
        if isinstance(merged, dict) and merged.get('_skill_args_reject'):
            return merged
        merged = finalize_skill_params(merged, schema, env=self.env)
        if isinstance(merged, dict) and merged.get('_skill_args_reject'):
            return merged
        remember = getattr(skill, '_remember_param_cache', None)
        if unresolved and callable(remember):
            try:
                remember(unresolved, norm)
            except Exception as exc:
                _logger.warning(
                    'param cache remember skipped for %s: %s',
                    getattr(skill, 'code', '?'), exc,
                )
        _logger.info(
            'Skill %s: params via hybrid (det=%s ai=%s)',
            getattr(skill, 'code', '?'), det, {
                k: v for k, v in (norm or {}).items()
                if isinstance(norm, dict) and k not in det
                and not (isinstance(norm, dict) and norm.get('_skill_args_reject'))
            },
        )
        try:
            self._mcp_log(
                operation_type='read',
                tool_name='skill_param_hybrid',
                prompt_data={
                    'skill': getattr(skill, 'code', '?'),
                    'arguments': raw,
                    'leftover': unresolved,
                    'det': det,
                    'ai': {
                        k: v for k, v in (norm or {}).items()
                        if isinstance(norm, dict) and k not in det
                        and not norm.get('_skill_args_reject')
                    } if isinstance(norm, dict) else {},
                    'ai_raw': (text or '')[:800],
                    'merged': merged,
                    'provider': getattr(prov, 'name', '') or '',
                    'tried': tried,
                    'usage': piece or {},
                },
                result_summary=(
                    'Skill param hybrid (%s): %s' % (
                        getattr(skill, 'code', '?'),
                        ', '.join(
                            '%s=%s' % (k, (merged or {}).get(k))
                            for k in schema.keys()
                            if (merged or {}).get(k) not in (None, '', [])
                        ) or 'empty',
                    )
                )[:480],
                request_type='tool',
            )
        except Exception:
            pass
        return merged

    # ------------------------------------------------------------------
    # Slash commands (skills) — chatboo inference client
    # ------------------------------------------------------------------
    @staticmethod
    def _parse_slash_command(message):
        """Return (command, args_str) if message is a slash command, else None."""
        if not message:
            return None
        text = message.strip()
        if not text.startswith('/'):
            return None
        body = text[1:].strip()
        if not body:
            return None
        parts = body.split(None, 1)
        command = parts[0].strip()
        args = parts[1].strip() if len(parts) > 1 else ''
        return command, args

    def _skills_list_markdown(self, _agent_code):
        from .skill_help import build_builtin_commands_markdown
        return build_builtin_commands_markdown()

    def _triggered_skill_command(self, agent_code, message):
        """One skill whose own phrases hit this sentence, or None.

        Same invocation as the slash. The engine does not list skills.
        """
        try:
            skills = self.env['ai.skill'].get_for_agent(agent_code).filtered(
                lambda s: s.active and s.user_may_run()
                and (s.triggers or '').strip()
            )
        except Exception:
            _logger.debug(
                'agent_engine: skill trigger lookup skipped', exc_info=True,
            )
            return None
        from .skill_trigger_match import match_one_skill
        rows = [
            {'command': skill.invoke_code(), 'triggers': skill.triggers}
            for skill in skills
        ]
        return match_one_skill(message, rows)

    def _resolve_skill(self, agent_code, command):
        skills = self.env['ai.skill'].get_for_agent(agent_code).filtered(
            lambda s: s.active and s.user_may_run()
        )

        def _fold(token):
            return (token or '').strip().lower().replace('_', '-')

        folded = _fold(command)
        match = skills.filtered(lambda s: s.invoke_code() == command)
        if not match:
            match = skills.filtered(
                lambda s: _fold(s.invoke_code()) == folded
                or _fold(s.code) == folded
            )
        return match[:1]
