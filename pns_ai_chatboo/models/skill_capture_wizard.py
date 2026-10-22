# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""Chatboo capture: session note + re-apply fetch wrap the wizard onchange strips."""
from odoo import _, api, fields, models
from odoo.exceptions import UserError

from ..utils.chatboo_product_icp import CHATBOO_AGENT_CODE


class SkillCaptureWizard(models.TransientModel):
    _inherit = 'ai.skill.capture.wizard'

    chatboo_session_id = fields.Integer(readonly=True)

    def _resolve_agent_ids(self):
        ids = super()._resolve_agent_ids()
        if ids or not self.chatboo_session_id:
            return ids
        return self.env['ai.agent'].search(
            [('code', '=', CHATBOO_AGENT_CODE)], limit=1,
        ).ids

    def _reapply_turn_fetch_wrap(self, keep_query=False):
        """The MCP onchange copies raw ``code_to_execute`` and drops the wrap.

        After the Code was adapted to parameters, ``keep_query`` keeps that
        rewrite. Recomposing from the turn would put the hardcoded
        literals back.
        """
        self.ensure_one()
        if not self.chatboo_session_id:
            return
        corr = ''
        if self.source_log_id:
            corr = (self.source_log_id.turn or '').strip()
        session = self.env['chatboo.session'].browse(
            self.chatboo_session_id,
        ).exists()
        if keep_query:
            wrapped = self.code_body or ''
            incomplete = self.warn_incomplete_capture
        else:
            wrapped, incomplete = session.compose_capture_code(
                self.code_body, corr,
            ) if session else (self.code_body or '', self.warn_incomplete_capture)
        if session:
            wrapped = session._wrap_open_page(wrapped, corr)
        updates = {}
        if wrapped != (self.code_body or ''):
            updates['code_body'] = wrapped
        if incomplete != self.warn_incomplete_capture:
            updates['warn_incomplete_capture'] = incomplete
        if updates:
            self.update(updates)

    @api.onchange('source_log_id')
    def _onchange_source_log_id(self):
        res = super()._onchange_source_log_id()
        self._reapply_turn_fetch_wrap()
        return res

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        code = res.get('code_body') or ''
        if 'page_html(' not in code:
            return res
        schema, hint, rows = self._schema_without_page_url(
            res.get('param_schema') or '',
            res.get('arg_hint') or '',
        )
        if 'param_schema' in fields_list:
            res['param_schema'] = schema or False
        if 'arg_hint' in fields_list:
            res['arg_hint'] = hint or False
        if 'param_line_ids' in fields_list:
            res['param_line_ids'] = self._line_commands(rows)
        return res

    @api.model
    def _schema_without_page_url(self, schema, hint):
        import json
        try:
            data = json.loads(schema) if str(schema).strip() else {}
        except (TypeError, ValueError):
            data = {}
        if not isinstance(data, dict):
            data = {}
        data.pop('page_url', None)
        schema = json.dumps(data, ensure_ascii=False) if data else ''
        kept = [
            line for line in str(hint or '').splitlines()
            if not line.strip().lower().startswith('page_url')
        ]
        rows = self._rows_from_schema_or_prose(schema, '')
        rows = [
            row for row in rows
            if (row.get('key') or '').strip() != 'page_url'
            and (row.get('label') or '').strip() != 'page_url'
        ]
        return schema, '\n'.join(kept).strip(), rows

    def _opens_saved_page(self):
        """The code already has the page. Nothing to ask a model."""
        return 'page_html(' in (self.code_body or '')

    def _drop_page_url_arg(self):
        """``page_url`` is the result, not a slash argument."""
        import json
        schema = self.param_schema or ''
        try:
            data = json.loads(schema) if schema.strip() else {}
        except (TypeError, ValueError):
            data = {}
        if isinstance(data, dict) and 'page_url' in data:
            data.pop('page_url', None)
            schema = json.dumps(data, ensure_ascii=False) if data else False
            self.param_schema = schema or False
        hint = self.arg_hint or ''
        kept = [
            line for line in hint.splitlines()
            if not line.strip().lower().startswith('page_url')
        ]
        self.arg_hint = '\n'.join(kept).strip() or False
        lines = self.param_line_ids.filtered(
            lambda line: (line.key or '').strip() != 'page_url'
            and (line.label or '').strip() != 'page_url'
        )
        if len(lines) != len(self.param_line_ids):
            self.param_line_ids = lines

    def _page_has_param_rows(self):
        return bool(self._param_rows())

    def action_author_params(self):
        if self.chatboo_session_id:
            self._reapply_turn_fetch_wrap(keep_query=True)
        if self._opens_saved_page():
            self._drop_page_url_arg()
            if not self._page_has_param_rows():
                return self._step_reply({})
        return super().action_author_params()

    def action_author_help(self):
        if self.chatboo_session_id:
            self._reapply_turn_fetch_wrap(keep_query=True)
        if self._opens_saved_page() and not self._is_placeholder_description(
            self.description, self.skill_name, self.skill_code,
        ):
            return self._step_reply({})
        return super().action_author_help()

    def action_adapt_code(self):
        if self.chatboo_session_id:
            self._reapply_turn_fetch_wrap(keep_query=True)
        if self._opens_saved_page() and not self._page_has_param_rows():
            return self._step_reply({})
        result = super().action_adapt_code()
        if self.chatboo_session_id:
            self._reapply_turn_fetch_wrap(keep_query=True)
        return result

    def _assert_captured_page_reusable(self):
        """A mixed page has nowhere for the next slash to write."""
        from .chatboo_canvas import (
            as_page_template, captured_page_is_reusable,
            design_figure_leaks, page_from_skill_code,
        )
        session = self.env['chatboo.session'].browse(
            self.chatboo_session_id,
        ).exists() if self.chatboo_session_id else self.env['chatboo.session']
        rows = None
        if session:
            try:
                rows = session.get_fresh_query_data()
            except Exception:
                rows = None
        html = page_from_skill_code(self.code_body or '')
        if not html:
            return
        title = (session.canvas_title or '') if session else ''
        if not captured_page_is_reusable(html, rows, title):
            leaks = design_figure_leaks(
                as_page_template(html) or html, rows, title,
            )[:5]
            if leaks:
                raise UserError(_(
                    'This page mixed data into the design (%s). '
                    'It cannot be saved as a skill.'
                ) % ', '.join(leaks))
            raise UserError(_(
                'This page mixed data into the design. '
                'It cannot be saved as a skill.'
            ))

    def action_create_draft(self):
        if not self.chatboo_session_id:
            return super().action_create_draft()
        self._reapply_turn_fetch_wrap(keep_query=True)
        if self._opens_saved_page() and self._page_has_param_rows():
            self._assert_captured_page_reusable()
        ctx = {
            'chatboo_confirm_op': (
                'updated' if self.existing_skill_id else 'created'
            ),
            'ai_session_ref': self.chatboo_session_id,
        }
        if self._opens_saved_page():
            # The page and the query are already known. Do not run them,
            # and do not ask a model to rewrite them or to compose the bubble.
            ctx['skill_skip_body_check'] = True
            ctx['skill_compose_fixed'] = 'compose-agent'
        return super(
            SkillCaptureWizard, self.with_context(**ctx),
        ).action_create_draft()
