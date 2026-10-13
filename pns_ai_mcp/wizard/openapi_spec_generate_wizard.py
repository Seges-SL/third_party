# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""Preview and apply an LLM-generated OpenAPI spec (manual servers only)."""

import json

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from ..services.openapi_spec_generator import (
    OpenAPISpecGeneratorError,
    fetch_documentation,
    generate_spec_from_documentation,
)
from ..utils.inference_audit import get_inference_audit, inference_audit


class OpenAPISpecGenerateWizard(models.TransientModel):
    _name = 'ai.openapi.spec.generate.wizard'
    _description = 'Generate OpenAPI Spec from Documentation'

    server_id = fields.Many2one(
        'ai.api.server',
        string='Server',
        required=True,
        ondelete='cascade',
    )
    docs_url = fields.Char(
        string='Documentation URL',
        required=True,
        help='Human-readable API docs (markdown/HTML). Host must be on the web whitelist.',
    )
    base_url = fields.Char(
        related='server_id.base_url',
        readonly=True,
    )
    openapi_gen_prompt = fields.Text(
        string='Doc → OpenAPI system prompt',
        help=(
            'System prompt sent to the model for this conversion. Copied from '
            'the server when the wizard opens; edits here are written back to '
            'the server before generation.'
        ),
    )
    docs_text = fields.Text(
        string='Fetched documentation',
        readonly=True,
        help='Plain text extracted from the documentation page (internal).',
    )
    generation_state = fields.Selection(
        [
            ('idle', 'Idle'),
            ('fetching', 'Fetching'),
            ('generating', 'Generating'),
            ('preview', 'Preview'),
            ('error', 'Error'),
        ],
        default='idle',
        required=True,
    )
    error_message = fields.Text(
        string='Last error',
        readonly=True,
    )
    state = fields.Selection(
        [('draft', 'Draft'), ('preview', 'Preview')],
        default='draft',
        required=True,
    )
    draft_spec_json = fields.Text(
        string='Generated OpenAPI JSON',
        readonly=True,
    )
    tool_count = fields.Integer(
        string='Tools',
        readonly=True,
    )
    warning_message = fields.Text(
        string='Warnings',
        readonly=True,
    )

    @api.model
    def default_get(self, fields_list):
        vals = super().default_get(fields_list)
        server_id = (
            self.env.context.get('default_server_id')
            or vals.get('server_id')
        )
        if server_id:
            server = self.env['ai.api.server'].browse(server_id)
            if server.exists():
                if 'docs_url' in fields_list and not vals.get('docs_url'):
                    vals['docs_url'] = server.docs_url or ''
                if (
                    'openapi_gen_prompt' in fields_list
                    and not vals.get('openapi_gen_prompt')
                ):
                    from ..services.openapi_spec_generator import (
                        resolve_openapi_gen_system_prompt,
                    )
                    vals['openapi_gen_prompt'] = (
                        resolve_openapi_gen_system_prompt(server)
                    )
        return vals

    def _sync_prompt_to_server(self):
        """Persist wizard prompt edits onto the server before LLM call."""
        self.ensure_one()
        text = (self.openapi_gen_prompt or '').strip()
        if text and text != (self.server_id.openapi_gen_prompt or '').strip():
            self.server_id.openapi_gen_prompt = text
        return text

    def action_restore_openapi_gen_prompt(self):
        """Reload factory Doc→OpenAPI prompt into the wizard (and server)."""
        self.ensure_one()
        from ..services.openapi_spec_generator import (
            DEFAULT_OPENAPI_GEN_SYSTEM_PROMPT,
        )
        text = DEFAULT_OPENAPI_GEN_SYSTEM_PROMPT
        self.openapi_gen_prompt = text
        self.server_id.openapi_gen_prompt = text
        return True

    def _check_server(self):
        self.ensure_one()
        server = self.server_id
        if server.api_type != 'openapi':
            raise UserError(_(
                'OpenAPI generation only applies to OpenAPI servers.'))
        if not server.spec_manual:
            raise UserError(_(
                'Enable Manual spec on the server before generating a pasted '
                'OpenAPI document from documentation.'))
        return server

    def _step_reply(self, usage=None, **extra):
        payload = {'ok': True}
        payload.update(extra)
        if usage:
            payload['usage'] = usage
        return payload

    def _openapi_audit_extra(self):
        self.ensure_one()
        server = self.server_id
        return {
            'server_code': server.code or '',
            'docs_url': (self.docs_url or '')[:500],
            'docs_chars': len(self.docs_text or ''),
        }

    def _openapi_audit(self, status='ok'):
        self.ensure_one()
        return inference_audit(
            self.env,
            endpoint='openapi_spec_generate',
            source_channel='internal',
            user_id=self.env.uid,
            user_prompt=(self.docs_url or '')[:2000] or None,
            additional_info=self._openapi_audit_extra(),
            status=status,
        )

    def _raise_generator_error(self, exc, usage=None):
        ctx = get_inference_audit()
        if ctx and usage:
            ctx.status = 'error'
            ctx.record(None, usage)
        self.write({
            'generation_state': 'error',
            'error_message': str(exc),
        })
        raise UserError(_(str(exc))) from exc

    def action_log_generation_usage(self, usage=None, status='cancelled'):
        """RPC from JS after cancel/error with accumulated client usage."""
        self.ensure_one()
        try:
            provider = self.server_id._detection_llm_provider()
        except Exception:
            provider = None
        self.env['ai.execution.engine'].log_llm_inference(
            provider,
            usage or {},
            endpoint='openapi_spec_generate',
            source_channel='internal',
            user_id=self.env.uid,
            user_prompt=(self.docs_url or '')[:2000] or None,
            additional_info=self._openapi_audit_extra(),
            status=status or 'cancelled',
        )
        return {'ok': True}

    def action_fetch_documentation(self):
        """Step 1: download and normalize the documentation page."""
        self.ensure_one()
        self._check_server()
        if not (self.docs_url or '').strip():
            raise UserError(_('Documentation URL is required.'))
        self.write({
            'generation_state': 'fetching',
            'error_message': False,
            'docs_text': False,
            'state': 'draft',
        })
        try:
            text = fetch_documentation(self.env, self.docs_url)
        except OpenAPISpecGeneratorError as exc:
            self._raise_generator_error(exc)
        self.write({'docs_text': text})
        return self._step_reply(docs_chars=len(text or ''))

    def _prepare_generate(self):
        """Validate and mark the wizard as generating (no LLM yet)."""
        self.ensure_one()
        self._check_server()
        self._sync_prompt_to_server()
        if not (self.docs_text or '').strip():
            raise UserError(_(
                'Fetch the documentation before converting to OpenAPI.'))
        self.write({
            'generation_state': 'generating',
            'error_message': False,
        })

    def _keep_llm_json(self, text, usage=None):
        """Persist the model JSON the instant it arrives (own commit)."""
        body = (text or '').strip()
        if not body.startswith('{'):
            return
        self.write({
            'state': 'preview',
            'generation_state': 'preview',
            'draft_spec_json': body,
            'error_message': False,
        })
        cr = getattr(self.env, 'cr', None)
        if cr is not None and getattr(cr, 'commit', None):
            cr.commit()

    def _run_generate_on_cursor(self):
        """One silent RPC: keep the JSON first, then tidy the draft."""
        self.ensure_one()
        server = self._check_server()
        usage = {}
        spec = None
        warnings = []
        with self._openapi_audit():
            try:
                spec, warnings, usage = generate_spec_from_documentation(
                    self.env, server, self.docs_text,
                    after_llm=self._keep_llm_json,
                )
            except OpenAPISpecGeneratorError as exc:
                ctx = get_inference_audit()
                raw = (getattr(exc, 'raw_text', None) or '').strip()
                if ctx and usage:
                    ctx.status = 'error'
                    ctx.record(None, usage, content_preview=raw)
                if raw.startswith('{'):
                    self._keep_llm_json(raw, usage)
                    self.write({
                        'warning_message': str(exc),
                    })
                    return self._step_reply(usage=usage or {}, reload=True)
                self.write({
                    'generation_state': 'error',
                    'error_message': str(exc),
                })
                return self._step_reply(
                    ok=False,
                    error=str(exc),
                    usage=usage or {},
                    reload=True,
                )

        draft = json.dumps(spec, indent=2, ensure_ascii=False)
        tool_count = 0
        try:
            from ..lib.api.drivers.openapi_driver import OpenAPIDriver
            tool_count = len(OpenAPIDriver()._spec_to_tools(spec))
        except Exception:
            pass
        self.write({
            'state': 'preview',
            'generation_state': 'preview',
            'draft_spec_json': draft,
            'tool_count': tool_count,
            'warning_message': '\n'.join(warnings) if warnings else False,
            'error_message': False,
        })
        return self._step_reply(usage=usage or {}, reload=True)

    def action_generate_openapi(self):
        """Step 2: one silent RPC, same as skill-param authoring."""
        self._prepare_generate()
        return self._run_generate_on_cursor()

    def action_generate(self):
        """Legacy single-shot entry (tests); UI uses fetch + generate."""
        self.action_fetch_documentation()
        self._prepare_generate()
        return self._run_generate_on_cursor()

    def action_apply(self):
        self.ensure_one()
        server = self._check_server()
        if self.state != 'preview' or not (self.draft_spec_json or '').strip():
            raise UserError(_(
                'Generate and review the OpenAPI draft before applying it.'))
        try:
            spec = json.loads(self.draft_spec_json)
        except (json.JSONDecodeError, TypeError) as exc:
            raise UserError(_('Generated spec is not valid JSON: %s') % exc)

        from ..services.openapi_spec_generator import validate_openapi_spec
        try:
            spec, warnings = validate_openapi_spec(
                spec, base_url=(server.base_url or '').strip())
        except OpenAPISpecGeneratorError as exc:
            raise UserError(_(str(exc))) from exc

        server.write({
            'docs_url': (self.docs_url or '').strip(),
            'spec_json': json.dumps(spec, indent=2, ensure_ascii=False),
        })
        server.action_discover_tools()
        message = _(
            "'%s': OpenAPI spec applied (%d tool(s))."
        ) % (server.name, self.tool_count or 0)
        extra = list(warnings or [])
        if self.warning_message:
            extra.extend(
                line for line in self.warning_message.splitlines() if line)
        if extra:
            message += '\n' + '\n'.join(extra)
        from ..utils.mcp_ui import client_notification
        return client_notification(
            _('OpenAPI spec applied'),
            message,
            'success',
            sticky=bool(extra),
        )
