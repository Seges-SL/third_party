# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""ai.skill: parameter lines, the author form and rewriting the code for its parameters."""

import logging

from odoo import api, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class AISkillAuthoring(models.Model):
    _inherit = 'ai.skill'

    def _param_line_vals_from_schema(self, schema_txt):
        from ..utils.skill_runtime import schema_to_param_rows

        vals_list = []
        for i, row in enumerate(schema_to_param_rows(schema_txt)):
            vals_list.append({
                'sequence': 10 * (i + 1),
                'label': row.get('label') or row.get('key') or '',
                'desc': row.get('desc') or '',
                'default': row.get('default') or '',
                'required': bool(row.get('required')),
                'key': row.get('key') or '',
            })
        return vals_list

    def _param_rows_from_lines(self):
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

    def _param_line_sync_allowed(self):
        ctx = self.env.context
        if ctx.get('skip_param_line_schema'):
            return False
        # Module install/-u XML functions: never nest a One2many replace
        # inside each factory write (it closed the cursor on O14).
        if ctx.get('install_mode'):
            return False
        return True

    def _create_param_lines_from_schema(self):
        """Insert UI rows from ``param_schema``. Does not write the skill."""
        Line = self.env['ai.skill.param.line'].sudo()
        for rec in self:
            for vals in rec._param_line_vals_from_schema(rec.param_schema):
                vals['skill_id'] = rec.id
                Line.create(vals)

    def _sync_param_lines_from_schema(self):
        """Replace UI rows from ``param_schema`` without a nested skill.write."""
        Line = self.env['ai.skill.param.line'].sudo()
        for rec in self:
            Line.search([('skill_id', '=', rec.id)]).unlink()
            rec._create_param_lines_from_schema()

    def _fill_missing_param_lines(self):
        """Create rows for skills that have JSON and no list yet.

        Used after factory import. Create-only: no unlink, no skill.write.
        """
        cr = self.env.cr
        try:
            cr.execute(
                "SELECT s.id FROM ai_skill s "
                "WHERE s.param_schema IS NOT NULL "
                "AND TRIM(s.param_schema) != '' "
                "AND NOT EXISTS ("
                "    SELECT 1 FROM ai_skill_param_line l "
                "    WHERE l.skill_id = s.id"
                ")"
            )
            ids = [row[0] for row in cr.fetchall()]
        except Exception:
            _logger.debug('skill param line fill-missing skipped', exc_info=True)
            return self.browse()
        records = self.browse(ids)
        if records:
            records._create_param_lines_from_schema()
        return records

    def _write_schema_from_param_lines(self):
        from ..utils.skill_runtime import (
            apply_code_keys_to_rows,
            infer_arg_hint_from_schema,
            infer_param_keys_from_code,
            param_rows_to_schema,
            param_schema_to_json,
        )

        for rec in self:
            rows = apply_code_keys_to_rows(
                rec._param_rows_from_lines(),
                infer_param_keys_from_code(rec.code_body),
            )
            schema = param_rows_to_schema(rows, rec.param_schema)
            dumped = param_schema_to_json(schema) or False
            vals = {'param_schema': dumped}
            if not schema:
                vals['args_policy'] = 'none'
            else:
                if rec.args_policy == 'none':
                    vals['args_policy'] = 'default'
                if not (rec.arg_hint or '').strip():
                    vals['arg_hint'] = infer_arg_hint_from_schema(schema) or False
            rec.with_context(skip_param_line_schema=True).write(vals)

    def _skill_form_author_allowed(self):
        """IA on the IT form: not install, not wizard, not nested schema writes."""
        ctx = self.env.context
        if ctx.get('skip_skill_form_author'):
            return False
        if ctx.get('skill_capture_authored'):
            return False
        if ctx.get('install_mode'):
            return False
        if ctx.get('skip_param_line_schema'):
            return False
        return True

    def _resolve_inference_provider(self):
        try:
            from ..utils.agent_engine import resolve_providers_for_consumer
            providers = resolve_providers_for_consumer(
                self.env, consumer_key='admin', need='conversation',
            )
            return providers[:1] if providers else self.env['ai.provider']
        except Exception:
            return self.env['ai.provider']

    def _author_form_help_and_params(self):
        """Fill empty Help and missing param keys. Never rewrites Code."""
        from ..utils.skill_runtime import (
            is_placeholder_skill_help,
            param_rows_need_author,
            param_rows_to_prose,
            procedure_for_help,
        )

        for rec in self:
            rows = rec._param_rows_from_lines()
            need_params = param_rows_need_author(rows)
            need_help = is_placeholder_skill_help(
                rec.description, rec.name, rec.code, rec.command,
            ) and bool(
                procedure_for_help(rec.content)
                or (rec.code_body or '').strip()
                or rows
            )
            if not need_params and not need_help:
                continue
            provider = rec._resolve_inference_provider()
            vals = {}
            if need_params and provider:
                try:
                    schema, hint, _usage, _help = rec._author_param_schema(
                        rec.param_schema or '',
                        param_rows_to_prose(rows),
                        code_body=rec.code_body or '',
                        hint=rec.arg_hint or '',
                        provider=provider,
                    )
                    if schema:
                        vals['param_schema'] = schema
                        if rec.args_policy == 'none':
                            vals['args_policy'] = 'default'
                    if hint:
                        vals['arg_hint'] = hint
                except UserError:
                    _logger.info(
                        'skill form param author skipped for %s', rec.code,
                    )
                except Exception:
                    _logger.debug(
                        'skill form param author failed for %s',
                        rec.code, exc_info=True,
                    )
            if need_help:
                try:
                    help_txt, _usage = rec._author_param_help(
                        rows,
                        provider=provider if provider else None,
                        procedure=rec.content,
                        code_body=rec.code_body,
                    )
                    if help_txt:
                        vals['description'] = help_txt
                except Exception:
                    _logger.debug(
                        'skill form help author failed for %s',
                        rec.code, exc_info=True,
                    )
            if vals:
                rec.with_context(skip_skill_form_author=True).write(vals)

    @api.model
    def _author_param_schema(self, existing_txt, prose, code_body='', hint='',
                            provider=None, extracted=None):
        """Fill from Code, then merge trainer prose onto ``param_schema``.

        Empty prose keeps the inferred / authored schema. ``extracted``
        skips the LLM (tests and a wizard that already parsed).

        Returns ``(schema, hint, usage, help)``. ``usage`` is the light
        JSON call (empty when there was no call).
        """
        from ..utils.llm_usage import normalize_usage
        from ..utils.skill_runtime import (
            build_param_author_prompt,
            fill_capture_params,
            infer_arg_hint_from_schema,
            infer_param_keys_from_code,
            merge_authored_param_schema,
            param_schema_to_json,
            parse_param_author_help,
            parse_param_author_json,
            parse_param_schema_txt,
        )

        schema_txt, hint = fill_capture_params(code_body, existing_txt, hint)
        text = (prose or '').strip()
        empty = (schema_txt or False, hint or False, {}, '')
        if not text:
            return empty
        usage = {}
        help_txt = ''
        if extracted is None:
            if not provider:
                raise UserError(_(
                    'An AI provider is required to read the parameter description.'
                ))
            from ..utils.agent_engine import llm_json_completion_for_agent
            from ..utils.inference_audit import inference_audit
            code_keys = infer_param_keys_from_code(code_body)
            lang = self.env.context.get('lang') or self.env.user.lang or 'en_US'
            system, user = build_param_author_prompt(
                text, code_keys, lang=lang,
            )
            with inference_audit(
                self.env,
                endpoint='skill_param_schema',
                source_channel='internal',
                user_id=self.env.uid,
            ):
                result = llm_json_completion_for_agent(
                    self.env, system, user,
                    consumer_key='admin', max_tokens=512,
                    need='conversation',
                )
            usage = normalize_usage((result or {}).get('usage') or {})
            raw = (result or {}).get('content') or ''
            extracted = parse_param_author_json(raw)
            help_txt = parse_param_author_help(raw)
        existing = parse_param_schema_txt(schema_txt)
        if not extracted or extracted.get('_reject'):
            if existing:
                return schema_txt or False, hint or False, usage, help_txt
            raise UserError(_(
                'Could not turn that description into parameters. '
                'Say what is asked (e.g. cities or a date range).'
            ))
        merged = merge_authored_param_schema(existing, extracted, text)
        if not merged:
            raise UserError(_(
                'Could not turn that description into parameters. '
                'Say what is asked (e.g. cities or a date range).'
            ))
        hint = (hint or '').strip()
        if set(existing) != set(merged) or not hint:
            hint = infer_arg_hint_from_schema(merged)
        return param_schema_to_json(merged), hint or False, usage, help_txt

    @api.model
    def _author_param_help(self, rows, provider=None, extracted=None,
                          procedure='', code_body=''):
        """One short slash-help sentence from Procedure and Code.

        Parameter rows are optional context (the card lists them apart).
        No call when the sources are empty or there is no provider.
        ``extracted`` skips the LLM (tests and a wizard that already parsed).
        Returns ``(help, usage)``.
        """
        from ..utils.llm_usage import normalize_usage
        from ..utils.skill_runtime import (
            build_param_help_prompt,
            build_skill_help_user,
            parse_param_author_help,
        )

        user = build_skill_help_user(procedure, code_body, rows)
        if not user:
            return '', {}
        if extracted is not None:
            if isinstance(extracted, str):
                return (extracted or '').strip()[:120], {}
            if isinstance(extracted, dict):
                return (extracted.get('help') or '').strip()[:120], {}
            return '', {}
        if not provider:
            return '', {}
        from ..utils.agent_engine import llm_json_completion_for_agent
        from ..utils.inference_audit import inference_audit
        lang = self.env.context.get('lang') or self.env.user.lang or 'en_US'
        system, _user = build_param_help_prompt(
            rows, procedure=procedure, code_body=code_body, lang=lang,
        )
        with inference_audit(
            self.env,
            endpoint='skill_param_help',
            source_channel='internal',
            user_id=self.env.uid,
        ):
            result = llm_json_completion_for_agent(
                self.env, system, user,
                consumer_key='admin', max_tokens=256,
                need='conversation',
            )
        usage = normalize_usage((result or {}).get('usage') or {})
        help_txt = parse_param_author_help((result or {}).get('content') or '')
        return help_txt, usage

    @api.model
    def _rewrite_code_for_params(self, code_body, schema_txt, prose='',
                                provider=None, rewritten=None):
        """Adapt Code so parameters with a default have a place and are used.

        Unused keys without a default are omitted. Conversation provider
        (not decision). Returns ``(code, usage)``. ``rewritten`` skips the
        LLM. No call when those keys already have their place, or when
        there is no conversation provider.
        """
        from ..controllers.validators import validate_relaxaicode_source_ast
        from ..utils.llm_usage import normalize_usage
        from ..utils.skill_runtime import (
            accept_rewritten_code,
            build_code_param_rewrite_prompt,
            drop_result_param_keys,
            bind_code_to_schema_params,
            parse_param_schema_txt,
            parse_rewritten_skill_code,
            param_schema_to_json,
            query_head_for_param_rewrite,
            schema_keys_unread_by_code,
            schema_params_need_place,
        )

        cleaned = drop_result_param_keys(schema_txt)
        if cleaned != parse_param_schema_txt(schema_txt or ''):
            schema_txt = param_schema_to_json(cleaned) or ''
        code = code_body or ''
        unread = schema_keys_unread_by_code(schema_txt, code)
        bound = bind_code_to_schema_params(code, schema_txt, self.env)

        def _accept(candidate, usage):
            accepted = accept_rewritten_code(candidate, schema_txt)
            if not accepted:
                missing = (
                    schema_keys_unread_by_code(schema_txt, candidate) or unread
                )
                raise UserError(_(
                    'The Code does not read the parameter keys: %s.'
                ) % ', '.join(missing))
            accepted = bind_code_to_schema_params(
                accepted, schema_txt, self.env,
            )
            ok, err, _requires_write = validate_relaxaicode_source_ast(accepted)
            if not ok:
                raise UserError(_(
                    'The adapted Code is not valid: %s'
                ) % (err or ''))
            return accepted, usage

        if rewritten is not None:
            return _accept(rewritten, {})
        if not schema_params_need_place(bound, schema_txt, env=self.env):
            return bound, {}
        if not provider:
            return bound, {}

        from ..utils.agent_engine import llm_json_completion_for_agent
        from ..utils.inference_audit import inference_audit
        head, tail = query_head_for_param_rewrite(bound)
        system, user = build_code_param_rewrite_prompt(
            head, schema_txt, prose,
        )
        with inference_audit(
            self.env,
            endpoint='skill_code_param_rewrite',
            source_channel='internal',
            user_id=self.env.uid,
        ):
            result = llm_json_completion_for_agent(
                self.env, system, user,
                consumer_key='admin', max_tokens=4096,
                need='conversation',
            )
        usage = normalize_usage((result or {}).get('usage') or {})
        raw = parse_rewritten_skill_code((result or {}).get('content') or '')
        if not raw:
            return bound, usage
        candidate = raw
        if tail and 'page_html(' not in raw and '_page_template' not in raw:
            candidate = raw.rstrip() + '\n' + tail
        try:
            return _accept(candidate, usage)
        except UserError:
            return bound, usage
