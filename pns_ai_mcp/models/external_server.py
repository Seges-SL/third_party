# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""Registered external API (MCP or OpenAPI) for Safe Plan ``api_call``.

The AI proposes the call; the human confirms; Odoo executes with per-server
trust. ``api_type`` selects the protocol driver (see ``lib/api/drivers``):
  - mcp:     Anthropic Model Context Protocol. Transports:
             sse (HTTP JSON-RPC + SSE streams) or stdio (local subprocess).
  - openapi: OpenAPI/Swagger HTTP API; catalogue from spec_url or pasted
             spec_json when spec_manual is set.

MCP servers keep form fields and config_json (Cursor/Antigravity format)
in sync idempotently.
"""


import json
import logging

from markupsafe import Markup

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from ..utils import mcp_ui
from ..utils.copy_code import next_copy_code
from ..utils.import_export_guard import ensure_ai_admin
from ..utils.portable_io import (
    export_record_dict,
    keep_existing_secrets,
)

_logger = logging.getLogger(__name__)

# Keys used in the JSON config format (Cursor/Antigravity-compatible).
_JSON_KEY_MAP = {
    'type': 'server_type',
    'url': 'url',
    'command': 'command',
    'args': 'command_args',
    'env': 'env_vars',
    'timeout': 'timeout',
}


class ExternalAPIServer(models.Model):
    """External self-documented API that the Odoo AI can call via Safe Plan.

    Protocol drivers (``api_type``):
        - ``mcp``: wraps the MCP client (JSON-RPC over SSE/stdio).
        - ``openapi``: reads the OpenAPI/Swagger spec and exposes every
          ``operationId`` as a callable tool. ``spec_manual`` freezes a
          pasted ``spec_json`` so Discover does not re-download ``spec_url``.

    Dual-representation (MCP only):
        - Form fields (name, code, url, auth_type, ...) for Odoo-native editing.
        - ``config_json`` field with the full JSON config in Cursor/Antigravity
          format for power-user editing.  Both representations are kept in sync:
          editing one automatically updates the other (idempotent).

    Tool discovery:
        Use the "Discover Tools" button: the driver fetches the server's
        self-description (MCP ``tools/list`` or the OpenAPI spec) and stores
        the NORMALIZED catalogue in ``tools_json`` (same shape for both types).

    Example MCP JSON config::

        {
          "web_search": {
            "type": "sse",
            "url": "https://search.example.com/mcp",
            "auth": {"type": "bearer", "token": "sk-abc123"},
            "timeout": 30
          }
        }
    """
    _name = 'ai.api.server'
    _description = 'External API Server'
    _order = 'name'
    _rec_name = 'name'
    # config_json repeats the token and env; the form fields rebuild it.
    _pns_secret_fields = ('auth_token', 'env_vars', 'config_json')

    # ── Identity ──────────────────────────────────────────────────────────
    name = fields.Char(
        string='Name',
        required=True,
        help='Human-readable name (e.g. "Web Search", "Translator").',
    )
    code = fields.Char(
        string='Code',
        required=True,
        index=True,
        help=(
            'Unique identifier used in api_call steps: '
            '{"op": "api_call", "server": "<code>", ...}.'
        ),
    )
    active = fields.Boolean(string='Active', default=True)

    # ── Protocol driver ───────────────────────────────────────────────────
    api_type = fields.Selection(
        [('mcp', 'MCP'), ('openapi', 'OpenAPI / Swagger')],
        string='API Type',
        required=True,
        default='mcp',
        index=True,
        help=(
            'Protocol of the external API. MCP: Anthropic Model Context '
            'Protocol servers. OpenAPI: any HTTP API documented by an '
            'openapi.json / swagger.json spec (FastAPI, etc.).'
        ),
    )

    # ── Transport (MCP) ───────────────────────────────────────────────────
    server_type = fields.Selection(
        [('sse', 'SSE (HTTP remote)'), ('stdio', 'stdio (local process)')],
        string='Transport',
        required=True,
        default='sse',
        help=(
            'MCP only. SSE: HTTP-based, for remote MCP servers. '
            'stdio: subprocess, for locally installed servers.'
        ),
    )

    # SSE fields
    url = fields.Char(
        string='Server URL',
        help='HTTP(S) endpoint for MCP SSE transport (e.g. https://server.com/mcp).',
    )

    # ── OpenAPI fields ────────────────────────────────────────────────────
    spec_url = fields.Char(
        string='Spec URL',
        help=(
            'URL of the OpenAPI JSON document (e.g. '
            'https://api.example.com/openapi.json). Ignored when Manual spec '
            'is set. Otherwise Discover downloads this URL into spec_json.'
        ),
    )
    spec_manual = fields.Boolean(
        string='Manual spec',
        default=False,
        help=(
            'OpenAPI only. When set, spec_json is the source of truth '
            '(pasted or converted). Discover rebuilds tools from that JSON '
            'and never downloads spec_url, so a converted document is not '
            'overwritten or lost on a failed refresh.'
        ),
    )
    docs_url = fields.Char(
        string='Documentation URL',
        help=(
            'OpenAPI manual only. Human-readable API docs (markdown/HTML) used '
            'by Generate OpenAPI from documentation. The host must be on the '
            'web URL whitelist.'
        ),
    )
    openapi_gen_prompt = fields.Text(
        string='Doc to OpenAPI prompt',
        default=lambda self: self._default_openapi_gen_prompt(),
        help=(
            'System prompt sent to the AI when converting the documentation '
            'page into OpenAPI JSON. The page text is the user message only — '
            'no Odoo metadata is injected. Empty rows are filled with the '
            'factory English default on module upgrade. Hidden when Manual '
            'spec is off; the value is kept.'
        ),
    )
    base_url = fields.Char(
        string='Base URL',
        help=(
            'Optional base URL override for OpenAPI calls. Empty = use the '
            "spec's servers[] entry (or the spec URL origin). Required when "
            'Manual spec is set and the pasted document has no servers[].'
        ),
    )
    spec_json = fields.Text(
        string='Cached Spec',
        help=(
            'OpenAPI document used at call time. Filled by Discover from '
            'spec_url, or pasted when Manual spec is set.'
        ),
    )
    auth_type = fields.Selection(
        [('none', 'None'), ('api_key', 'API Key'), ('bearer', 'Bearer Token'),
         ('basic', 'HTTP Basic'), ('custom_header', 'Custom Header')],
        string='Auth Type',
        default='none',
    )
    auth_token = fields.Char(
        string='Default Auth Token',
        groups='pns_ai_mcp.group_ai_admin',
        help=(
            'Default API key or bearer token, used when the calling user has '
            'no personal credential (see the Credentials tab).'
        ),
    )
    auth_header_name = fields.Char(
        string='HTTP header name',
        default='Authorization',
        help=(
            'HTTP request header that carries the token (e.g. apikey, '
            'X-API-Key, Authorization). Discover copies it from a unique '
            'OpenAPI apiKey scheme so it stays visible on this form.'
        ),
    )
    auth_call_preview = fields.Html(
        string='Outbound headers',
        compute='_compute_auth_call_preview',
        sanitize=False,
        help='HTTP header this server will send. Same values as the fields above.',
    )

    # stdio fields
    command = fields.Char(
        string='Command',
        help='Executable to run for stdio transport (e.g. "python", "npx").',
    )
    command_args = fields.Text(
        string='Command Args (JSON)',
        default='[]',
        help='JSON array of arguments: ["-m", "my_server", "--port", "3000"].',
    )
    env_vars = fields.Text(
        string='Environment Variables (JSON)',
        groups='pns_ai_mcp.group_ai_admin',
        default='{}',
        help='JSON object of env vars: {"API_KEY": "sk-..."}.',
    )

    # ── Common ────────────────────────────────────────────────────────────
    timeout = fields.Integer(
        string='Timeout (s)',
        default=30,
        help='Timeout in seconds for each tool call.',
    )
    trusted = fields.Boolean(
        string='Trusted (auto-confirm)',
        default=False,
        help=(
            'When enabled, api_call steps to this server execute IMMEDIATELY '
            'without a Safe Plan confirmation toast (like a whitelisted fetch_url). '
            'SECURITY: grant this ONLY to servers you fully control. An external '
            'API server receives your call arguments and can run arbitrary '
            'operations (including writes on the remote) — far more sensitive than '
            'a safe URL fetch, so this trust is per-server and never shared with '
            'the URL whitelist. Leave OFF for third-party servers.'
        ),
    )

    # ── Dual-representation: raw JSON config ──────────────────────────────
    config_json = fields.Text(
        string='JSON Config',
        groups='pns_ai_mcp.group_ai_admin',
        help=(
            'Full server configuration in Cursor/Antigravity JSON format. '
            'Editing this field updates the form fields and vice versa.'
        ),
    )

    # ── Discovery ─────────────────────────────────────────────────────────
    tools_json = fields.Text(
        string='Discovered Tools',
        readonly=True,
        help='JSON catalogue of tools discovered via MCP tools/list.',
    )
    resources_json = fields.Text(
        string='Discovered Resources',
        readonly=True,
        help='JSON catalogue of resources discovered via MCP resources/list.',
    )
    prompts_json = fields.Text(
        string='Discovered Contexts',
        readonly=True,
        help='JSON catalogue of prompts/contexts discovered via MCP prompts/list.',
    )
    last_discovery = fields.Datetime(
        string='Last Discovery',
        readonly=True,
    )
    tools_count = fields.Integer(
        string='Tools',
        compute='_compute_discovery_counts',
        store=False,
    )
    resources_count = fields.Integer(
        string='Resources',
        compute='_compute_discovery_counts',
        store=False,
    )
    prompts_count = fields.Integer(
        string='Contexts',
        compute='_compute_discovery_counts',
        store=False,
    )
    tools_html = fields.Html(
        string='Tools catalogue',
        compute='_compute_catalog_html',
        sanitize=False,
        store=False,
    )
    resources_html = fields.Html(
        string='Resources catalogue',
        compute='_compute_catalog_html',
        sanitize=False,
        store=False,
    )
    prompts_html = fields.Html(
        string='Contexts catalogue',
        compute='_compute_catalog_html',
        sanitize=False,
        store=False,
    )

    # ── Meta ──────────────────────────────────────────────────────────────
    usage_guide = fields.Text(
        string='Usage guide',
        help=(
            'Free-text hints injected into the agent prompt alongside the '
            'discovered tools: when to use this server, argument conventions, '
            'examples. Complements the auto-discovered catalogue with knowledge '
            'that tools/list cannot express.'
        ),
    )
    detection_context_ids = fields.One2many(
        'ai.context',
        'api_server_id',
        string='Detection',
        help=(
            'Discovery routing rows (locale + triggers). A match hints '
            'api_call with this server code. Never injected as prose. '
            'Archiving or deleting this server deactivates or removes them.'
        ),
    )
    notes = fields.Text(string='Notes')
    added_by = fields.Many2one(
        'res.users',
        string='Added by',
        default=lambda self: self.env.uid,
        readonly=True,
    )

    # ── Outbound credentials (N per server, one per user) ─────────────────
    key_ids = fields.One2many(
        'ai.api.server.key',
        'server_id',
        string='Credentials',
        help=(
            'Per-user credentials for calling this server. At call time the '
            "current user's key is used; without one, the server's default "
            'auth token applies.'
        ),
    )

    _sql_constraints = [
        ('code_unique', 'UNIQUE(code)', 'Server code must be unique.'),
    ]

    def copy(self, default=None):
        """Duplicate with a free ``code`` so UNIQUE(code) does not abort Action Duplicate."""
        self.ensure_one()
        default = dict(default or {})
        if not default.get('code'):
            taken = self.with_context(active_test=False).search([]).mapped('code')
            default['code'] = next_copy_code(self.code, taken)
        if not default.get('name'):
            default['name'] = _('%s (copy)') % (self.name or self.code)
        return super().copy(default)

    # ── Computed ──────────────────────────────────────────────────────────

    @api.depends('auth_type', 'auth_header_name', 'auth_token')
    def _compute_auth_call_preview(self):
        for rec in self:
            rec.auth_call_preview = rec._auth_call_preview_html()

    def _auth_call_preview_html(self):
        """Visible summary of the outbound auth header (no token value)."""
        self.ensure_one()
        if self.auth_type in (False, 'none'):
            return False
        token_state = _('token set') if self.sudo().auth_token else _('no token')
        if self.auth_type == 'bearer':
            header, value = 'Authorization', 'Bearer …'
        elif self.auth_type == 'basic':
            header, value = 'Authorization', 'Basic …'
        elif self.auth_type in ('api_key', 'custom_header'):
            header = (self.auth_header_name or '').strip() or 'Authorization'
            value = '…'
        else:
            return False
        return Markup(
            '<div class="alert alert-info mb-0" role="status">'
            '<strong>%s</strong> <code>%s</code>: %s '
            '<span class="text-muted">(%s)</span></div>'
        ) % (
            _('Outgoing HTTP header'),
            header,
            value,
            token_state,
        )

    @api.depends('tools_json', 'resources_json', 'prompts_json')
    def _compute_discovery_counts(self):
        for rec in self:
            rec.tools_count = rec._count_json(rec.tools_json)
            rec.resources_count = rec._count_json(rec.resources_json)
            rec.prompts_count = rec._count_json(rec.prompts_json)

    @staticmethod
    def _count_json(raw):
        try:
            data = json.loads(raw or '[]')
            return len(data) if isinstance(data, list) else 0
        except (json.JSONDecodeError, TypeError):
            return 0

    @api.depends('tools_json', 'resources_json', 'prompts_json')
    def _compute_catalog_html(self):
        for rec in self:
            rec.tools_html = rec._render_catalog_html(rec.tools_json, 'tool')
            rec.resources_html = rec._render_catalog_html(rec.resources_json, 'resource')
            rec.prompts_html = rec._render_catalog_html(rec.prompts_json, 'prompt')

    @staticmethod
    def _render_catalog_html(raw, kind):
        """Render a discovered catalogue (JSON list) as a readable HTML list.

        ``kind`` is one of 'tool' | 'resource' | 'prompt' and only changes which
        secondary metadata (argument signature, uri, title) is shown.
        Returns ``False`` when there is nothing to render so the field stays empty.
        """
        try:
            items = json.loads(raw or '[]')
        except (json.JSONDecodeError, TypeError):
            items = []
        if not isinstance(items, list) or not items:
            return False

        rows = [Markup('<ul class="list-unstyled mb-0">')]
        for it in items:
            if not isinstance(it, dict):
                continue
            name = str(it.get('name') or it.get('uri') or '?')
            desc = str(it.get('description') or '')
            meta = ''
            if kind == 'tool':
                schema = it.get('inputSchema') or {}
                props = schema.get('properties') if isinstance(schema, dict) else None
                required = schema.get('required') or [] if isinstance(schema, dict) else []
                if isinstance(props, dict) and props:
                    bits = []
                    for pname, pdef in props.items():
                        ptype = (pdef.get('type') if isinstance(pdef, dict) else '') or ''
                        star = '*' if pname in required else ''
                        bits.append('%s%s%s' % (pname, star, (': %s' % ptype) if ptype else ''))
                    meta = ', '.join(bits)
            elif kind == 'resource':
                meta = str(it.get('uri') or '')
            elif kind == 'prompt':
                meta = str(it.get('title') or '')

            row = Markup('<li class="mb-2"><code>%s</code>') % name
            if meta:
                row += Markup(' <small class="text-muted">%s</small>') % meta
            if desc:
                row += Markup('<div class="text-muted small">%s</div>') % desc
            row += Markup('</li>')
            rows.append(row)
        rows.append(Markup('</ul>'))
        return Markup('').join(rows)

    # ── Dual-representation sync ──────────────────────────────────────────

    def _fields_to_json(self):
        """Build the Cursor-compatible JSON dict from form fields."""
        self.ensure_one()
        cfg = {'type': self.server_type}
        if self.server_type == 'sse':
            cfg['url'] = self.url or ''
            if self.auth_type and self.auth_type != 'none':
                cfg['auth'] = {
                    'type': self.auth_type,
                    'token': self.auth_token or '',
                }
                if self.auth_type == 'custom_header' and self.auth_header_name:
                    cfg['auth']['header'] = self.auth_header_name
        elif self.server_type == 'stdio':
            cfg['command'] = self.command or ''
            try:
                args = json.loads(self.command_args or '[]')
            except (json.JSONDecodeError, TypeError):
                args = []
            if args:
                cfg['args'] = args
            try:
                env = json.loads(self.env_vars or '{}')
            except (json.JSONDecodeError, TypeError):
                env = {}
            if env:
                cfg['env'] = env
        if self.timeout and self.timeout != 30:
            cfg['timeout'] = self.timeout
        return {self.code or 'unnamed': cfg}

    def _json_to_fields(self, config_json_str):
        """Parse a JSON config string and return a dict of field values."""
        try:
            raw = json.loads(config_json_str or '{}')
        except (json.JSONDecodeError, TypeError):
            return {}
        if not isinstance(raw, dict) or not raw:
            return {}
        # The JSON has one key: the server code → config dict.
        code = next(iter(raw))
        cfg = raw[code]
        if not isinstance(cfg, dict):
            return {}
        vals = {'code': code}
        vals['server_type'] = cfg.get('type', 'sse')
        vals['url'] = cfg.get('url', '')
        vals['command'] = cfg.get('command', '')
        vals['command_args'] = json.dumps(cfg.get('args', []), ensure_ascii=False)
        vals['env_vars'] = json.dumps(cfg.get('env', {}), ensure_ascii=False)
        vals['timeout'] = cfg.get('timeout', 30)
        auth = cfg.get('auth')
        if isinstance(auth, dict):
            vals['auth_type'] = auth.get('type', 'none')
            vals['auth_token'] = auth.get('token', '')
            vals['auth_header_name'] = auth.get('header', 'Authorization')
        else:
            vals['auth_type'] = 'none'
        return vals

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('config_json') and not vals.get('_from_fields'):
                # JSON was provided → populate fields
                parsed = self._json_to_fields(vals['config_json'])
                for k, v in parsed.items():
                    if k not in vals or not vals[k]:
                        vals[k] = v
            vals.pop('_from_fields', None)
            self._check_may_set_stdio_command(vals)
        records = super().create(vals_list)
        # Ensure config_json is in sync with fields
        for rec in records:
            rec._sync_json_from_fields()
            rec._ensure_server_whitelisted()
            try:
                rec._ensure_identity_detection()
            except Exception:
                _logger.warning(
                    'MCP: server %s created but detection row failed',
                    rec.code,
                    exc_info=True,
                )
            if rec.api_type == 'openapi' and (rec.spec_json or '').strip():
                rec._sync_openapi_tools_from_spec()
        return records

    @api.model
    def _check_may_set_stdio_command(self, vals):
        """The stdio command runs on the Odoo host: Settings admins only.

        AI Administrator alone is not a shell on the server. Checked on the
        real user, so a ``sudo()`` import does not lift it.
        """
        empty = (False, None, '', '[]', '{}')
        if not (vals.get('server_type') == 'stdio' or any(
                (vals.get(k) or '').strip() not in empty
                for k in ('command', 'command_args', 'env_vars') if k in vals)):
            return
        user = self.env.user
        if user._is_superuser() or user.has_group('base.group_system'):
            return
        raise UserError(_(
            'Only a Settings administrator can set up a stdio server: '
            'its command runs on the Odoo host.'
        ))

    def write(self, vals):
        self._check_may_set_stdio_command(vals)
        res = super().write(vals)
        if 'config_json' in vals and not self.env.context.get('_syncing_json'):
            # JSON changed → update fields
            for rec in self:
                parsed = rec._json_to_fields(vals['config_json'])
                if parsed:
                    rec.with_context(_syncing_json=True).write(parsed)
        elif not self.env.context.get('_syncing_json'):
            # Fields changed → update JSON
            field_keys = set(_JSON_KEY_MAP.values()) | {'name', 'code', 'auth_type',
                'auth_token', 'auth_header_name', 'url', 'command', 'command_args',
                'env_vars', 'timeout', 'server_type'}
            if field_keys & set(vals.keys()):
                for rec in self:
                    rec._sync_json_from_fields()
        if not self.env.context.get('_syncing_json') and (
            {'active', 'url', 'spec_url', 'base_url', 'api_type',
             'spec_manual'} & set(vals)
        ):
            for rec in self:
                rec._ensure_server_whitelisted()
        if not self.env.context.get('_syncing_json') and (
            {'code', 'active'} & set(vals)
        ):
            self._sync_detection_contexts()
        if not self.env.context.get('_syncing_json') and (
            {'code', 'name'} & set(vals)
        ):
            self._ensure_identity_detection()
        if (
            not self.env.context.get('_syncing_openapi_tools')
            and 'spec_json' in vals
        ):
            for rec in self:
                if rec.api_type == 'openapi':
                    rec._sync_openapi_tools_from_spec()
        if not self.env.context.get('_syncing_json') and 'docs_url' in vals:
            for rec in self:
                if rec.api_type == 'openapi' and (rec.docs_url or '').strip():
                    rec._ensure_docs_url_whitelisted()
        return res

    def _ensure_identity_detection(self):
        """Neutral Detection row from code + name. No LLM. Merge, never replace."""
        from ..utils.domain_index import identity_detection_triggers
        for srv in self:
            triggers = identity_detection_triggers(srv.code, srv.name)
            srv._upsert_detection_row('', triggers)

    def _sync_detection_contexts(self):
        """Keep server-owned discovery rows aligned (code / active / cascade)."""
        from ..utils.domain_index import (
            TARGET_KIND_API_SERVER,
            detection_row_code,
        )
        Context = self.env['ai.context'].sudo().with_context(
            active_test=False,
            skip_hardcoded_restrictions=True,
            _syncing_detection=True,
        )
        for srv in self:
            ctxs = Context.search([('api_server_id', '=', srv.id)])
            for ctx in ctxs:
                updates = {}
                if ctx.discovery_target != srv.code:
                    updates['discovery_target'] = srv.code
                if ctx.discovery_target_kind != TARGET_KIND_API_SERVER:
                    updates['discovery_target_kind'] = TARGET_KIND_API_SERVER
                if ctx.active != srv.active:
                    updates['active'] = srv.active
                want = detection_row_code(srv.code, ctx.locale or '')
                if ctx.code != want:
                    updates['code'] = want
                if updates:
                    ctx.write(updates)

    @api.model
    def _default_openapi_gen_prompt(self):
        from ..services.openapi_spec_generator import (
            DEFAULT_OPENAPI_GEN_SYSTEM_PROMPT,
        )
        return DEFAULT_OPENAPI_GEN_SYSTEM_PROMPT

    @api.model
    def _fill_empty_openapi_gen_prompts(self):
        """Persist factory English prompt on OpenAPI rows that still have none
        or still hold a prior factory text (unmodified).
        """
        from ..services.openapi_spec_generator import (
            DEFAULT_OPENAPI_GEN_SYSTEM_PROMPT,
            _LEGACY_OPENAPI_GEN_SYSTEM_PROMPTS,
        )
        Server = self.sudo()
        empty = Server.search([
            ('api_type', '=', 'openapi'),
            '|',
            ('openapi_gen_prompt', '=', False),
            ('openapi_gen_prompt', '=', ''),
        ])
        legacy = Server.browse()
        for old in _LEGACY_OPENAPI_GEN_SYSTEM_PROMPTS:
            legacy |= Server.search([
                ('api_type', '=', 'openapi'),
                ('openapi_gen_prompt', '=', old),
            ])
        targets = empty | legacy
        if targets:
            targets.write({
                'openapi_gen_prompt': DEFAULT_OPENAPI_GEN_SYSTEM_PROMPT,
            })
        return len(targets)

    def action_restore_openapi_gen_prompt(self):
        """Replace the Doc→OpenAPI prompt with the current factory English text."""
        from ..services.openapi_spec_generator import (
            DEFAULT_OPENAPI_GEN_SYSTEM_PROMPT,
        )
        for rec in self:
            rec.openapi_gen_prompt = DEFAULT_OPENAPI_GEN_SYSTEM_PROMPT
        # Return True so the form reloads the textarea from the database.
        return True

    def _factory_usage_guide(self):
        """Return pack factory text for ``usage_guide``, or empty.

        Plug: any installed addon may expose
        ``hooks.factory_usage_guide_for_code(code) -> str``. The engine does
        not hardcode pack names; packs that seed servers implement the hook.
        """
        self.ensure_one()
        code = (self.code or '').strip()
        if not code:
            return ''
        Module = self.env['ir.module.module'].sudo()
        for mod in Module.search([('state', '=', 'installed')]):
            name = mod.name
            try:
                hooks = __import__(
                    'odoo.addons.%s.hooks' % name,
                    fromlist=['factory_usage_guide_for_code'],
                )
            except ImportError:
                continue
            fn = getattr(hooks, 'factory_usage_guide_for_code', None)
            if not callable(fn):
                continue
            try:
                text = (fn(code) or '').strip()
            except Exception:
                _logger.debug(
                    'MCP: factory_usage_guide_for_code failed in %s',
                    name, exc_info=True,
                )
                continue
            if text:
                return text
        return ''

    def action_restore_usage_guide(self):
        """Replace ``usage_guide`` with the pack factory text for this server."""
        for rec in self:
            text = (rec._factory_usage_guide() or '').strip()
            if not text:
                raise UserError(_(
                    "No factory usage guide is defined for server '%s'. "
                    "Only pack-seeded servers can restore this field."
                ) % (rec.code or rec.name or rec.id))
            rec.usage_guide = text
        return True

    def _detection_llm_provider(self):
        """First provider on the AI Admin inference chain (presence / chips)."""
        try:
            from ..utils.agent_engine import resolve_providers_for_consumer
            provs = resolve_providers_for_consumer(
                self.env, consumer_key='admin',
            )
            if provs:
                return provs[:1]
        except Exception:
            _logger.debug(
                'detection hybrid: no pns_ai_admin provider', exc_info=True,
            )
        return self.env['ai.provider']

    def _hybrid_detection_triggers(self, locale):
        """Deterministic identity tokens, then one admin-agent LLM fill.

        Same order as skill params: parse for free, LLM only to fill holes
        (spoken synonyms from name / usage_guide). Never browses spec_json.
        """
        from ..utils.agent_engine import (
            llm_json_completion_for_agent,
            resolve_providers_for_consumer,
        )
        from ..utils.domain_index import (
            DETECTION_TRIGGER_SCHEMA,
            build_detection_triggers_prompt,
            identity_detection_triggers,
            merge_trigger_lists,
        )
        from ..utils.skill_runtime import parse_and_validate_params

        self.ensure_one()
        det = identity_detection_triggers(self.code, self.name)
        ai_list = []
        used_llm = False
        audit_ctx = None
        try:
            providers = resolve_providers_for_consumer(
                self.env, consumer_key='admin',
            )
        except Exception:
            providers = self.env['ai.provider']
        if providers:
            system, user = build_detection_triggers_prompt(
                locale=locale or '',
                code=self.code or '',
                name=self.name or '',
                usage_guide=self.usage_guide or '',
                already=det,
            )
            from ..utils.inference_audit import inference_audit
            with inference_audit(
                self.env,
                endpoint='server_detection',
                source_channel='internal',
                user_id=self.env.uid,
                additional_info={
                    'server_code': self.code or '',
                    'locale': locale or '',
                },
            ) as audit_ctx:
                result = llm_json_completion_for_agent(
                    self.env, system, user,
                    consumer_key='admin', max_tokens=400,
                )
                text = (result or {}).get('content') or ''
            used_llm = True
            parsed = parse_and_validate_params(text, DETECTION_TRIGGER_SCHEMA)
            if isinstance(parsed, dict) and not parsed.get('_skill_args_reject'):
                raw = parsed.get('triggers') or []
                if isinstance(raw, (list, tuple)):
                    ai_list = [str(x).strip() for x in raw if str(x).strip()]
        merged = merge_trigger_lists(det, ai_list)
        usage = {}
        if used_llm and audit_ctx is not None:
            usage = dict(audit_ctx.usage_acc or {})
        _logger.info(
            'detection hybrid: server=%s locale=%s det=%s ai=%s llm=%s',
            self.code, locale or '', det, ai_list, used_llm,
        )
        return merged, used_llm, usage

    def _upsert_detection_row(self, locale, triggers):
        """Create or merge the locale Detection row for this server."""
        from ..utils.domain_index import (
            TARGET_KIND_API_SERVER,
            detection_row_code,
            merge_trigger_lists,
        )
        self.ensure_one()
        Context = self.env['ai.context'].sudo().with_context(
            active_test=False,
            skip_hardcoded_restrictions=True,
        )
        locale = (locale or '').strip()
        domain = [('api_server_id', '=', self.id)]
        rec = Context.search(
            domain + [('locale', '=', locale)] if locale
            else domain + ['|', ('locale', '=', False), ('locale', '=', '')],
            limit=1,
        )
        if not rec and locale:
            rec = Context.search(
                domain + ['|', ('locale', '=', False), ('locale', '=', '')],
                limit=1,
            )
        if not rec:
            want = detection_row_code(self.code, locale)
            orphan = Context.search([
                ('code', '=', want),
                '|',
                ('api_server_id', '=', False),
                ('api_server_id', '=', self.id),
            ], limit=1)
            if orphan:
                if not orphan.api_server_id:
                    orphan.write({'api_server_id': self.id})
                rec = orphan
        existing = Context._discovery_parse_triggers(
            rec.discovery_triggers,
        ) if rec else []
        merged = merge_trigger_lists(existing, triggers)
        payload = json.dumps(merged, ensure_ascii=False)
        if rec:
            rec.write({
                'discovery_triggers': payload,
                'discovery_target_kind': TARGET_KIND_API_SERVER,
                'discovery_target': self.code,
            })
            return rec, False
        Context.create({
            'api_server_id': self.id,
            'context_type': 'discovery',
            'discovery_target_kind': TARGET_KIND_API_SERVER,
            'discovery_target': self.code,
            'locale': locale or False,
            'discovery_triggers': payload,
            'discovery_priority': 40,
        })
        return True, True

    def action_suggest_detection(self):
        """Fill Detection rows: identity tokens + one short JSON LLM call."""
        from ..utils.llm_usage import add_usage
        from ..utils.mcp_ui import client_notification
        from ..utils.usage_display import format_usage_chip

        locale = (self.env.user.lang or '').replace('-', '_')
        created = 0
        updated = 0
        llm_used = False
        usage_acc = {}
        for srv in self:
            triggers, used_llm, usage = srv._hybrid_detection_triggers(locale)
            llm_used = llm_used or used_llm
            usage_acc = add_usage(usage_acc, usage)
            _rec, is_new = srv._upsert_detection_row(locale, triggers)
            if is_new:
                created += 1
            else:
                updated += 1
        if llm_used:
            title = _('Detection suggested')
            detail = _(
                'Short JSON extraction (same channel as skill params). '
                '%s new row(s), %s updated. Locale %s.'
            ) % (created, updated, locale or 'neutral')
        else:
            title = _('Detection suggested')
            detail = _(
                'Identity tokens only (no LLM provider). '
                '%s new row(s), %s updated. Locale %s.'
            ) % (created, updated, locale or 'neutral')
        chip = format_usage_chip(self.env, usage_acc)
        if chip:
            detail = '%s\n%s: %s' % (detail, _('LLM usage'), chip)
        action = client_notification(title, detail)
        if usage_acc:
            action['usage'] = usage_acc
        return action

    def _sync_json_from_fields(self):
        """Regenerate config_json from form field values (MCP servers only)."""
        self.ensure_one()
        if self.api_type != 'mcp':
            return
        new_json = json.dumps(self._fields_to_json(), indent=2, ensure_ascii=False)
        if (self.config_json or '').strip() != new_json.strip():
            self.with_context(_syncing_json=True).write({'config_json': new_json})

    # ── Typed URL whitelist coupling ──────────────────────────────────────

    def _server_hostnames(self):
        """Hostnames this server reaches over HTTP (per its api_type)."""
        from urllib.parse import urlparse
        self.ensure_one()
        urls = []
        if self.api_type == 'mcp':
            if self.server_type == 'sse' and self.url:
                urls.append(self.url)
        elif self.api_type == 'openapi':
            if self.spec_manual:
                urls.extend(u for u in (self.base_url,) if u)
            else:
                urls.extend(u for u in (self.spec_url, self.base_url) if u)
        hosts = []
        for u in urls:
            host = (urlparse(u).hostname or '').lower().strip()
            if host and host not in hosts:
                hosts.append(host)
        return hosts

    @api.model
    def _link_orphan_api_discovery(self):
        """Attach factory ``api_server`` discovery rows that missed the server.

        Import may run before the XML shell exists on a first install if file
        order is wrong; this pass is idempotent and does not rewrite triggers.
        """
        if 'ai.context' not in self.env:
            return
        Context = self.env['ai.context'].sudo().with_context(
            active_test=False,
            skip_hardcoded_restrictions=True,
        )
        orphans = Context.search([
            ('context_type', '=', 'discovery'),
            ('discovery_target_kind', '=', 'api_server'),
            ('api_server_id', '=', False),
        ])
        linked = 0
        for ctx in orphans:
            target = (ctx.discovery_target or '').strip()
            if not target:
                continue
            srv = self.with_context(active_test=False).search(
                [('code', '=', target)], limit=1,
            )
            if not srv:
                continue
            ctx.write({'api_server_id': srv.id})
            linked += 1
        if linked:
            _logger.info('MCP: linked %s orphan API discovery row(s)', linked)

    def _ensure_docs_url_whitelisted(self):
        """Register the documentation host on the web whitelist when set."""
        self.ensure_one()
        from urllib.parse import urlparse

        url = (self.docs_url or '').strip()
        if not url:
            return
        parsed = urlparse(url)
        host = parsed.hostname
        if not host:
            return
        try:
            self.env['ai.url.whitelist'].ensure_domain_whitelisted(
                host,
                notes='Documentation URL for external API server "%s"' % self.code,
                kind='web',
            )
        except Exception:
            _logger.warning(
                'MCP: could not whitelist docs host %s for server %s',
                host, self.code, exc_info=True,
            )

    def _openapi_tools_from_spec(self):
        """Derive the normalized tool catalogue from ``spec_json``."""
        self.ensure_one()
        if self.api_type != 'openapi':
            return []
        from ..lib.api.drivers.openapi_driver import OpenAPIDriver, APIDriverError

        driver = OpenAPIDriver()
        try:
            if self.spec_manual:
                spec = driver._resolve_spec(self, fetch=False)
            else:
                spec = driver._load_cached_spec(self)
                if not spec:
                    return []
                spec = driver._as_spec_dict(
                    spec, "cached spec_json of server '%s'" % (self.code or '?'))
        except APIDriverError:
            return []
        return driver._spec_to_tools(spec)

    def _sync_openapi_tools_from_spec(self):
        """Keep ``tools_json`` aligned with ``spec_json`` for OpenAPI servers."""
        self.ensure_one()
        if self.api_type != 'openapi':
            return
        tools = self._openapi_tools_from_spec()
        payload = (
            json.dumps(tools, indent=2, ensure_ascii=False) if tools else False
        )
        if payload == (self.tools_json or False):
            return
        self.with_context(_syncing_openapi_tools=True).write({
            'tools_json': payload,
        })

    def _ensure_server_whitelisted(self):
        """Register the server's domain(s) in the typed URL whitelist.

        Only AI Administrators can configure servers (ACL), so activating one
        IS the admin decision that whitelist_only would otherwise ask for —
        the entry (kind = api_type) is created/reactivated automatically and
        keeps the whitelist as the single audit surface of every egress point.
        stdio servers have no URL and are skipped.
        """
        self.ensure_one()
        if not self.active:
            return
        Whitelist = self.env['ai.url.whitelist']
        for host in self._server_hostnames():
            try:
                Whitelist.ensure_domain_whitelisted(
                    host,
                    notes='Auto-added for external API server "%s"' % self.code,
                    kind=self.api_type,
                )
            except Exception:
                _logger.warning(
                    'MCP: could not whitelist %s for server %s',
                    host, self.code, exc_info=True,
                )

    # ── Actions ───────────────────────────────────────────────────────────

    def _get_driver(self):
        """Fresh protocol driver for this server's api_type."""
        self.ensure_one()
        from ..lib.api.drivers import get_api_driver
        return get_api_driver(self.api_type)

    def _resolve_auth_token(self, user=None):
        """Outbound credential for a call: user's personal key → server default.

        Returns None when neither exists (the driver then sends no auth).
        """
        self.ensure_one()
        user = user or self.env.user
        if user and user.id:
            key = self.env['ai.api.server.key'].sudo().search([
                ('server_id', '=', self.id),
                ('user_id', '=', user.id),
                ('active', '=', True),
            ], limit=1)
            if key and key.token:
                return key.token
        return self.sudo().auth_token or None

    def action_open_openapi_generate_wizard(self):
        """Open the admin wizard that drafts OpenAPI from documentation."""
        self.ensure_one()
        if self.api_type != 'openapi':
            raise UserError(_(
                'OpenAPI generation only applies to OpenAPI servers.'))
        if not self.spec_manual:
            raise UserError(_(
                'Enable Manual spec before generating OpenAPI from '
                'documentation.'))
        return {
            'type': 'ir.actions.act_window',
            'name': _('Generate OpenAPI from documentation'),
            'res_model': 'ai.openapi.spec.generate.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_server_id': self.id,
                'default_docs_url': self.docs_url or '',
            },
        }

    def action_discover_tools(self):
        """Fetch the server's self-description via its protocol driver.

        MCP: handshake + tools/resources/prompts lists (optional lists are
        best-effort). OpenAPI: downloads the spec, caches it in ``spec_json``
        and maps every operation to a normalized tool entry — unless
        ``spec_manual`` is set, in which case tools are rebuilt from the
        pasted ``spec_json`` and that document is never overwritten.
        """
        ensure_ai_admin(self.env)
        self.ensure_one()
        try:
            catalog = self._get_driver().discover(self)
        except Exception as e:
            raise UserError(_("Discovery failed: %s") % str(e))

        tools = catalog.get('tools') or []
        resources = catalog.get('resources') or []
        prompts = catalog.get('prompts') or []

        def _json_catalog(items):
            """Persist discovered lists; leave field empty when the list is empty."""
            if isinstance(items, list) and items:
                return json.dumps(items, indent=2, ensure_ascii=False)
            return False

        vals = {
            'tools_json': _json_catalog(tools),
            'resources_json': _json_catalog(resources),
            'prompts_json': _json_catalog(prompts),
            'last_discovery': fields.Datetime.now(),
        }
        if catalog.get('spec') is not None and not self.spec_manual:
            vals['spec_json'] = json.dumps(
                catalog['spec'], indent=2, ensure_ascii=False)
        vals.update(self._auth_vals_from_openapi_catalog(catalog))
        self.write(vals)

        from ..utils.mcp_ui import client_notification
        message = _("'%s': %d tool(s), %d resource(s), %d context(s)") % (
            self.name, len(tools), len(resources), len(prompts))
        warnings = list(catalog.get('warnings') or [])
        if warnings:
            message += "\n" + "\n".join(warnings)
        return client_notification(
            _("Discovery complete"),
            message,
            'warning' if warnings else 'success',
            sticky=bool(warnings),
        )

    def _openapi_spec_dict(self, catalog=None):
        """Spec dict from a discovery catalog, else the stored ``spec_json``."""
        self.ensure_one()
        spec = (catalog or {}).get('spec')
        if isinstance(spec, dict):
            return spec
        try:
            spec = json.loads(self.spec_json or '')
        except (json.JSONDecodeError, TypeError):
            return {}
        return spec if isinstance(spec, dict) else {}

    def _auth_vals_from_openapi_catalog(self, catalog):
        """Copy a unique OpenAPI apiKey header name onto the form fields.

        The LLM must not be the only writer of outbound headers: Discover
        materialises what the spec already declares so the ficha shows it.
        Never touches ``auth_token``.
        """
        self.ensure_one()
        if self.api_type != 'openapi':
            return {}
        from ..lib.api.drivers.openapi_driver import OpenAPIDriver
        header = OpenAPIDriver.api_key_header_name(
            self._openapi_spec_dict(catalog))
        if not header:
            return {}
        vals = {'auth_header_name': header}
        if self.auth_type in (False, 'none', 'api_key', 'custom_header'):
            vals['auth_type'] = 'api_key'
        return vals

    def action_discover_auth(self):
        """Apply outbound auth from the OpenAPI spec (no LLM, no token write).

        Homologous to Discover Tools: the spec is the source. Chatboo write
        proposals remain the path when the spec is silent or ambiguous.
        """
        self.ensure_one()
        from ..utils.mcp_ui import client_notification
        from ..lib.api.drivers.openapi_driver import OpenAPIDriver
        if self.api_type != 'openapi':
            raise UserError(_("Auth from spec only applies to OpenAPI servers."))
        names = OpenAPIDriver.api_key_header_names(self._openapi_spec_dict())
        vals = self._auth_vals_from_openapi_catalog({})
        if vals:
            self.write(vals)
            return client_notification(
                _("Auth from spec"),
                _("Outgoing header set to `%s` (from spec).") % vals['auth_header_name'],
                'success',
                sticky=False,
            )
        if not names:
            return client_notification(
                _("Auth from spec"),
                _("The spec has no unique apiKey header. Fill Authentication "
                  "by hand, or ask Chatboo to propose a write."),
                'warning',
                sticky=True,
            )
        return client_notification(
            _("Auth from spec"),
            _("The spec declares several apiKey headers: %s. Pick one on the form.")
            % ", ".join(names),
            'warning',
            sticky=True,
        )

    def action_test_connection(self):
        """Quick connectivity test (no full discovery)."""
        ensure_ai_admin(self.env)
        self.ensure_one()
        try:
            summary = self._get_driver().test_connection(self)
        except Exception as e:
            raise UserError(_("Connection failed: %s") % str(e))

        from ..utils.mcp_ui import client_notification
        return client_notification(
            _("Connection OK"),
            _("Server '%s' responded (%s)") % (self.name, summary),
            'success',
            sticky=False,
        )

    def get_tools_list(self):
        """Return the discovered tools as a Python list of dicts."""
        self.ensure_one()
        if self.api_type == 'openapi':
            derived = self._openapi_tools_from_spec()
            if derived:
                return derived
        try:
            return json.loads(self.tools_json or '[]')
        except (json.JSONDecodeError, TypeError):
            return []

    @api.model
    def get_tools_prompt_block(self, max_tools_per_server=40, compact_chunk=24):
        """Render the active external servers + their discovered tools as a
        compact prompt block, so the agent uses REAL tool names (not invented).

        The first ``max_tools_per_server`` tools get a one-line signature +
        description. When the catalogue is larger (typical OpenAPI specs),
        **all remaining tool names** are still listed (names only) so the
        agent cannot wrongly conclude that an endpoint is unavailable.

        Format (one server per group)::

            External API servers callable via safe_plan_request → api_call.
            Use ONLY these exact server codes and tool names; never invent tools.

            • server "produccion" (Producción):
              <usage guide, if any>
              - search_payslips(employee_id, month) — Search payslips
              - get_data(model, domain) — Generic read
              (+ 228 more tools, names only:)
              ListVacationDayOffRequests, ListWorkEntries, ...

        Returns an empty string when no active server has a usable catalogue, so
        the caller can inject it conditionally (like the whitelist hint).
        Inactive/archived records are omitted (Odoo ``active_test``); do not
        delete them just so the agent stops reading them.
        """
        from ..lib.api.tools_prompt_block import format_tools_prompt_block

        servers = self.sudo().search([('active', '=', True)])
        rows = []
        for srv in servers:
            rows.append({
                'code': srv.code,
                'name': srv.name,
                'usage_guide': srv.usage_guide,
                'tools': srv.get_tools_list(),
                'active': True,
            })
        return format_tools_prompt_block(
            rows,
            max_tools_per_server=max_tools_per_server,
            compact_chunk=compact_chunk,
        )


    # ── Export / Import ───────────────────────────────────────────
    # Dynamic via portable_io: every scalar/config field on the model is
    # exported (incl. trusted, discovery caches, usage_guide, …). No curated
    # allow-list — adding a field to the model is enough for it to travel.

    def _export_server_row(self, include_secrets=False):
        """Portable dict for one external API server (dynamic field dump)."""
        self.ensure_one()
        return export_record_dict(self, include_secrets=include_secrets)

    def _keep_secrets_on_import(self, vals):
        """Import *vals* for this server without blanking its token or env.

        ``config_json`` is read into the fields first (on write it would
        overwrite them), then dropped: the fields rebuild it.
        """
        if not self:
            return vals
        raw = vals.pop('config_json', None)
        if raw:
            for key, value in self._json_to_fields(raw).items():
                if not vals.get(key):
                    vals[key] = value
        return keep_existing_secrets(self, vals)

    @api.model
    def _export_servers_summary(self, servers):
        """Human summary: total + active/inactive (seed demos are often inactive)."""
        total = len(servers)
        n_active = len(servers.filtered('active'))
        n_inactive = total - n_active
        return _(
            '%(total)s external server(s) exported '
            '(%(active)s active, %(inactive)s inactive).'
        ) % {
            'total': total,
            'active': n_active,
            'inactive': n_inactive,
        }

    @api.model
    def action_export_external_servers(self, *args, **kwargs):
        """Export all external API server configurations (asks for secrets first).

        Exports ALL servers (including inactive/archived) as a JSON array.
        Each element is a dynamic dump of every portable field on ``ai.api.server``
        (see ``portable_io.export_record_dict``). Relational fields are omitted;
        URL whitelist entries are a separate model and are never mixed in.
        """
        ensure_ai_admin(self.env)
        if not self.with_context(active_test=False).search_count([]):
            return mcp_ui.open_json_export_empty_wizard(
                self.env,
                dialog_title=_('Export'),
                message=_('There are no external API servers to export.'),
            )
        return self.env['pns.export.secrets.wizard'].ask(
            self.browse(), '_pns_export_all_servers',
        )

    def action_export_selected(self, *args, **kwargs):
        """Export selected external API servers to JSON (tree multi-select action)."""
        ensure_ai_admin(self.env)
        if not self:
            return mcp_ui.open_json_export_empty_wizard(
                self.env,
                dialog_title=_('Export'),
                message=_('No external servers selected for export.'),
            )
        return self.env['pns.export.secrets.wizard'].ask(
            self, '_pns_export_selected_servers',
        )

    def _pns_export_all_servers(self, include_secrets=False):
        ensure_ai_admin(self.env)
        servers = self.with_context(active_test=False).search([])
        return servers._export_servers_file('external_api_servers', include_secrets)

    def _pns_export_selected_servers(self, include_secrets=False):
        ensure_ai_admin(self.env)
        servers = self.with_context(active_test=False)
        return servers._export_servers_file(
            'external_api_servers_selected', include_secrets,
        )

    def _export_servers_file(self, artifact, include_secrets):
        export_data = [srv._export_server_row(include_secrets) for srv in self]
        filename = mcp_ui.build_export_filename(
            self.env, artifact, 'json', secrets=include_secrets,
        )
        attachment = mcp_ui.write_json_attachment(
            self.env, filename, export_data,
        )
        return mcp_ui.open_json_export_wizard(
            self.env,
            dialog_title=_('Export result'),
            summary_text=self._export_servers_summary(self),
            count=len(export_data),
            attachment=attachment,
        )

    @api.model
    def action_import_external_servers(self, *args, **kwargs):
        """Open the import wizard for external API server configurations.

        The wizard accepts ``.json`` or ``.zip`` files.  Import is fully
        resilient: unknown keys and fields absent on the destination are
        skipped; per-record errors are collected and never abort the batch.
        Match key: ``code``.

        Returns:
            dict: Odoo action opening ``ai.import.external.servers.wizard``.
        """
        ensure_ai_admin(self.env)
        return {
            'type': 'ir.actions.act_window',
            'name': _('Import External API Servers'),
            'res_model': 'ai.import.external.servers.wizard',
            'view_mode': 'form',
            'views': [[False, 'form']],
            'target': 'new',
        }
