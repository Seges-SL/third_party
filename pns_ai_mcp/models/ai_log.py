# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""One row per AI/MCP operation (read or write). Audit trail."""

from odoo import models, fields, api, SUPERUSER_ID, _
from odoo.tools import config, html_escape
from ..utils import mcp_ui
from ..utils.import_export_guard import ensure_ai_admin
from ..utils.portable_io import export_record_dict
import json
import re
import logging

_logger = logging.getLogger(__name__)

LOG_RETENTION_PARAM = 'pns_ai_mcp.log_retention_days'
DEFAULT_LOG_RETENTION_DAYS = 30


class AILog(models.Model):
    """One row per AI/MCP operation, read or write.

    Every request that flows through the MCP layer leaves a row here, whether
    it comes from the in-house Chatboo UI, an external MCP client (Cursor,
    Claude, Antigravity...) or an internal process. Write operations are the
    most important: they let us reconstruct altered, damaged or deleted records.

    The row carries three orthogonal axes so the history is easy to read:

    * ``origin``    -- door token (in-house UI / MCP client / internal).
    * ``agent_id`` / ``agent_display`` -- the agent that owned the turn.
    * ``primitive`` + ``category`` -- WHAT kind of operation it was.
    * ``flow`` + ``flow_label``    -- the step's DIRECTION within the turn.

    For external MCP clients Odoo does not run the model (it lives on the client),
    so those rows only ever show tool/resource/prompt calls -- there is no
    internal orchestration to display.
    """
    _name = 'ai.log'
    _description = 'AI Operation Log'
    # Desempate por turn_step: los pasos de un mismo turno comparten timestamp
    # (granularidad de segundo), así que sin este desempate Postgres los devuelve
    # en orden arbitrario y el turno se ve "descolocado" (8,7,2,6,5,...).
    _order = 'timestamp desc, turn_step desc'
    _rec_name = 'display_name'

    # ── Who / where ──────────────────────────────────────────────────
    user_id = fields.Many2one(
        'res.users',
        string='Log user',
        readonly=True,
        index=True,
        ondelete='set null',
    )
    origin = fields.Selection(
        [
            ('chatboo', 'Chatboo'),
            ('mcp_client', 'MCP Client'),
            ('internal', 'Internal'),
        ],
        string='Door',
        readonly=True,
        index=True,
        help='Which door the request used: Chatboo screen, an MCP client '
             '(Cursor, Claude), or an internal process (walkie, cron).',
    )
    agent_id = fields.Many2one(
        'ai.agent',
        string='Agent',
        readonly=True,
        index=True,
        ondelete='set null',
        help='Agent that owned this turn. The Agent column shows this name.',
    )
    agent_display = fields.Char(
        string='Agent',
        compute='_compute_agent_display',
        help='Agent that owned this turn. If no agent was bound, shows the door label.',
    )
    remote_ip = fields.Char(
        string='IP',
        readonly=True,
        index=True,
        help='Remote IP address of the caller, when available.',
    )
    client_label = fields.Char(
        string='Client',
        readonly=True,
        index=True,
        help='Program that called: Cursor, Claude, Chatboo, the walkie. '
             'If the host sends no name, this copies the agent.',
    )

    # ── When ─────────────────────────────────────────────────────────
    timestamp = fields.Datetime(
        string='Date/Time',
        required=True,
        readonly=True,
        default=fields.Datetime.now,
        index=True,
        help='Operation timestamp (same source as create_date: Odoo/UTC time).',
    )

    # ── What ─────────────────────────────────────────────────────────
    access_mode = fields.Selection(
        [
            ('read', 'Read'),
            ('write', 'Supervised'),
        ],
        string='Access',
        required=True,
        readonly=True,
        index=True,
        help='Read, or a supervised step (human confirm: write, action, API, URL…).',
    )
    primitive = fields.Selection(
        [
            ('system', 'System'),
            ('tool', 'Tool'),
            ('resource', 'Resource'),
            ('prompt', 'Prompt'),
            ('llm', 'LLM'),
        ],
        string='Primitive',
        required=True,
        readonly=True,
        index=True,
        help='MCP primitive: protocol handshake (system), tool execution, '
             'resource/prompt fetch, or internal LLM orchestration.',
    )
    endpoint = fields.Char(
        string='Endpoint',
        required=True,
        readonly=True,
        index=True,
        help='Name of the executed MCP tool, resource URI or prompt.',
    )
    # Project-wide the executed tool is referred to as ``tool_name`` (the
    # create_log_entry parameter, ai.safe.operation, AI-authored relaxaicode).
    # The stored column here is ``endpoint``; this read-only related alias keeps
    # ``tool_name`` valid to avoid AttributeError in code that uses that name.
    tool_name = fields.Char(
        related='endpoint',
        string='Tool name',
        readonly=True,
    )
    category = fields.Selection(
        [
            ('protocol', 'Protocol'),
            ('query', 'Query'),
            ('code', 'Code'),
            ('context', 'Context'),
            ('verification', 'Verification'),
            ('maintenance', 'Maintenance'),
            ('analytics', 'Analytics'),
        ],
        string='Category',
        compute='_compute_category',
        store=True,
        readonly=True,
        index=True,
        help='Functional category, derived from the primitive and endpoint.',
    )
    model_name = fields.Char(
        string='LLM model',
        readonly=True,
        index=True,
        help='Model that processed the request (e.g. ollama/llama3.1_8B). For '
             'external MCP clients, the client name (the model runs on their side).',
    )

    # ── Turn threading ───────────────────────────────────────────────
    turn = fields.Char(
        string='Turn',
        readonly=True,
        index=True,
        help='Short id (<=8 chars) grouping all rows of the same conversation turn.',
    )
    turn_step = fields.Integer(
        string='Step',
        readonly=True,
        default=0,
        help='Step number within the turn (1, 2, 3...). 0 = no sequence assigned.',
    )
    # ── Flow (computed, honest per origin) ───────────────────────────
    flow = fields.Selection(
        [
            ('llm_request',  'AI Engine -> LLM'),
            ('llm_response', 'LLM -> AI Engine'),
            ('tool_call',    'AI Engine -> Tool'),
            ('tool_result',  'Tool -> AI Engine'),
            ('domain_index', 'Discovery'),
            ('turn_done',    'Turn completed'),
            ('failover',     'Provider failover'),
            ('external',     'MCP client -> Odoo'),
            ('other',        'Other'),
        ],
        string='Flow type',
        compute='_compute_flow',
        store=True,
        readonly=True,
        help='Direction of this step within the turn.',
    )
    flow_label = fields.Char(
        string='Flow',
        compute='_compute_flow',
        store=True,
        readonly=True,
        help='Human-readable flow: who sends what to whom.',
    )
    flow_legend_html = fields.Html(
        string='Color legend',
        compute='_compute_flow_legend_html',
        sanitize=False,
        readonly=True,
        help='Color legend for the history (single source, shared with the '
             'list-view legend bar).',
    )
    flow_icon_html = fields.Html(
        string='Icon',
        compute='_compute_flow_icon_html',
        sanitize=False,
        readonly=True,
        help='Negotiation-state icon (same drawings as the color legend). '
             'Supervised steps use the flag, matching the red row.',
    )

    # ── Payloads ─────────────────────────────────────────────────────
    prompt_data = fields.Text(
        string='Prompt/Args',
        readonly=True,
        help='Arguments or code sent to the tool (JSON serialized).',
    )
    result_data = fields.Text(
        string='Result',
        readonly=True,
        help='Result returned by the tool (JSON serialized).',
    )
    result_summary = fields.Text(
        string='Result Summary',
        readonly=True,
        help='Result summary for quick search.',
    )
    prompt_data_compressed = fields.Char(
        string='Prompt/Args (Short)',
        compute='_compute_compressed_fields',
        store=False,
        readonly=True,
    )
    result_summary_compressed = fields.Char(
        string='Result (Short)',
        compute='_compute_compressed_fields',
        store=False,
        readonly=True,
    )
    additional_info = fields.Text(
        string='Additional Info',
        readonly=True,
        help='Additional information such as errors, warnings, etc.',
    )
    user_prompt = fields.Text(
        string='User Prompt',
        readonly=True,
        help='Original user prompt (without system prompts).',
    )
    code_to_execute = fields.Text(
        string='Code to Execute',
        readonly=True,
        help='Python code to execute (for relaxaicode).',
    )

    # ── Sizes / tokens ───────────────────────────────────────────────
    request_size_bytes = fields.Integer(
        string='Size (In)',
        readonly=True,
        help='Request size in bytes (prompt_data).',
    )
    response_size_bytes = fields.Integer(
        string='Size (Out)',
        readonly=True,
        help='Response size in bytes (result_data).',
    )
    prompt_tokens = fields.Integer(
        string='Prompt Tokens',
        readonly=True,
        help='Number of tokens in the prompt.',
    )
    completion_tokens = fields.Integer(
        string='Completion Tokens',
        readonly=True,
        help='Number of tokens in the model response.',
    )
    total_tokens = fields.Integer(
        string='Total Tokens',
        readonly=True,
        help='Total tokens used in the request.',
    )
    cost_usd = fields.Float(
        string='Cost (USD)',
        digits=(16, 8),
        readonly=True,
        help='USD cost reported by the provider for this LLM step (when available).',
    )
    cost_display = fields.Char(
        string='Cost',
        compute='_compute_cost_display',
        help='Provider cost in the configured display currency.',
    )

    # ── Display ──────────────────────────────────────────────────────
    display_name = fields.Char(
        string='Name',
        compute='_compute_display_name',
        store=True,
    )

    # ── Computes ─────────────────────────────────────────────────────

    @api.depends('cost_usd')
    def _compute_cost_display(self):
        from ..utils.usage_display import format_cost_label
        for rec in self:
            if not rec.cost_usd:
                rec.cost_display = ''
            else:
                rec.cost_display = format_cost_label(rec.env, rec.cost_usd)['label']

    @api.depends('user_id', 'timestamp', 'endpoint', 'access_mode')
    def _compute_display_name(self):
        for record in self:
            user_name = record.user_id.name if record.user_id else 'No user'
            endpoint = record.endpoint or 'No endpoint'
            access = dict(record._fields['access_mode'].selection).get(
                record.access_mode, record.access_mode)
            ts = record.timestamp.strftime('%Y-%m-%d %H:%M:%S') if record.timestamp else 'No date'
            record.display_name = f"{user_name} - {access} - {endpoint} - {ts}"

    @api.model
    def _category_for(self, primitive, endpoint):
        """Deterministic functional category from the primitive and endpoint.

        Pure mapping (no DB lookups) so it is safe to call from anywhere,
        including the safe-logging cursor.
        """
        endpoint = endpoint or ''
        if primitive == 'system':
            return 'protocol'
        if primitive == 'tool':
            if endpoint == 'relaxaicode':
                return 'code'
            if endpoint == 'get_context':
                return 'context'
            if endpoint in ('confirm_write_operation', 'cancel_write_operation',
                            'test_write_confirmation',
                            'safe_plan_request', 'safe_plan_status',
                            'propose_safe_operations', 'get_safe_operation_status'):
                return 'verification'
            if endpoint == 'clean_system':
                return 'maintenance'
            if endpoint == 'get_context_usage_stats':
                return 'analytics'
            return 'query'
        if primitive == 'resource':
            return 'context' if endpoint.startswith('mcp://contexts/') else 'query'
        if primitive == 'prompt':
            return 'context'
        return 'query'

    @api.depends('primitive', 'endpoint')
    def _compute_category(self):
        for rec in self:
            rec.category = self._category_for(rec.primitive, rec.endpoint)

    @staticmethod
    def _humanize_endpoint(endpoint):
        return (endpoint.replace('relaxaicode', 'Python')
                        .replace('get_context', 'context')
                        .replace('safe_plan_request', 'plan')
                        .replace('safe_plan_status', 'plan status')
                        .replace('propose_safe_operations', 'plan')
                        .replace('get_safe_operation_status', 'plan status')
                        .replace('fetch_native_mcp_resource', 'resource')
                        .replace('audit_translations', 'i18n')
                        .replace('get_corporative_terms', 'glossary')
                        .replace('get_context_usage_stats', 'analytics')
                        .replace('clean_system', 'maintenance')
                        .replace('search_memory', 'memory')
                        .replace('domain_index', 'domains'))

    @api.depends('agent_id', 'agent_id.name', 'origin')
    def _compute_agent_display(self):
        labels = dict(self._fields['origin'].selection or [])
        for rec in self:
            name = (rec.agent_id.name or '').strip()
            rec.agent_display = name or labels.get(rec.origin) or rec.origin or ''

    @api.depends('origin', 'primitive', 'endpoint', 'access_mode', 'category', 'result_summary')
    def _compute_flow(self):
        for rec in self:
            origin = rec.origin or ''
            prim = rec.primitive or ''
            ep = rec.endpoint or ''
            cat = rec.category or ''
            rs = rec.result_summary or ''

            # External MCP clients run their own model; Odoo only sees the
            # primitive call. Be honest: there is no local orchestrator here.
            if origin == 'mcp_client':
                verb = {
                    'tool': 'Tool',
                    'resource': 'Resource',
                    'prompt': 'Prompt',
                    'system': 'Protocol',
                    'llm': 'Model',
                }.get(prim, prim)
                rec.flow = 'external'
                rec.flow_label = 'MCP client -> %s: %s' % (verb, ep)
                continue

            # Internal orchestration (Chatboo / internal processes).
            if ep == 'provider_failover':
                rec.flow = 'failover'
                rec.flow_label = rs or 'Provider failover'
            elif ep == 'domain_index':
                rec.flow = 'domain_index'
                # Keep English: debug terminology shared with AIs / logs.
                rec.flow_label = rs or 'Discovery'
            elif ep == 'llm_tool_request':
                rec.flow = 'llm_response'
                rec.flow_label = 'LLM -> AI Engine (tool call)'
            elif ep == 'llm_response_hdr':
                rec.flow = 'llm_response'
                rec.flow_label = 'LLM -> AI Engine (intro/outro)'
            elif ep == 'orchestration_summary':
                # Logged with primitive='llm'; must win over the generic llm branch.
                rec.flow = 'turn_done'
                rec.flow_label = 'Turn completed'
            elif prim == 'llm':
                if ep == 'llm_response':
                    rec.flow = 'llm_response'
                    rec.flow_label = 'LLM -> AI Engine (response)'
                elif ep == 'llm_orchestration':
                    rec.flow = 'llm_request'
                    rec.flow_label = 'AI Engine -> LLM (request)'
                else:
                    rec.flow = 'llm_request'
                    rec.flow_label = 'AI Engine -> LLM (%s)' % ep
            elif prim == 'tool':
                tl = self._humanize_endpoint(ep)
                rec.flow = 'tool_call'
                if cat == 'code':
                    rec.flow_label = 'AI Engine -> Tool: %s (code)' % tl
                elif rec.access_mode == 'write':
                    rec.flow_label = 'AI Engine -> Tool: %s (supervised)' % tl
                else:
                    rec.flow_label = 'AI Engine -> Tool: %s' % tl
            elif prim in ('resource', 'prompt', 'system'):
                rec.flow = 'tool_call'
                rec.flow_label = 'AI Engine -> %s (context)' % ep
            else:
                rec.flow = 'other'
                rec.flow_label = '%s / %s' % (prim, ep)

    # ── Color legend (SINGLE SOURCE) ─────────────────────────────────
    # Canonical legend for the history colors. This is the ONLY place the
    # chips (color + label + icon) are defined; both the list-view legend
    # bar (JS) and the form-view banner render from here (via
    # ``render_flow_legend``), so grid and form never drift again.
    #   (background, text_color, label, italic, icon_key)
    # Icons: clean paths from pns_suite/design/AI/icons (no C2PA metadata).
    # Order = Chatboo negotiation start → end, then outliers (failover, MCP).
    _FLOW_WRENCH = (
        '<path d="M20.6 3.9a5.4 5.4 0 0 0-7.2 7.0L5.1 19.2a2.1 2.1 0 0 0 '
        '3.0 3.0l8.3-8.3a5.4 5.4 0 0 0 7.0-7.2l-3.3 3.3-2.8-2.8 3.3-3.3z" '
        'fill="currentColor" stroke="none"/>'
    )
    _FLOW_ICON_INNER = {
        'discovery': (
            '<circle cx="10" cy="10" r="6.4"/>'
            '<line x1="14.9" y1="14.9" x2="21" y2="21"/>'
        ),
        'engine_to_llm_request': (
            '<line x1="4" y1="20" x2="19" y2="5"/>'
            '<polyline points="10,5 19,5 19,14"/>'
        ),
        'llm_to_engine_response': (
            '<line x1="20" y1="4" x2="5" y2="19"/>'
            '<polyline points="14,19 5,19 5,10"/>'
        ),
        'engine_to_tool': _FLOW_WRENCH,
        'safe_plan': (
            '<line x1="6.5" y1="3" x2="6.5" y2="21"/>'
            '<polygon points="6.5,4.5 18.5,8.2 6.5,11.9"/>'
        ),
        'turn_completed': (
            '<polyline points="4,13 9.5,18.5 20,6"/>'
        ),
        'provider_failover': (
            '<line x1="3" y1="9" x2="21" y2="9"/>'
            '<polyline points="17,5 21,9 17,13"/>'
            '<line x1="21" y1="16" x2="3" y2="16"/>'
            '<polyline points="7,12 3,16 7,20"/>'
        ),
        'mcp_client_to_odoo': (
            # Same silhouette as Chatboo's fa-plug, rotated 90° CW so
            # the prongs do not read as cat ears at 15px.
            '<g transform="rotate(90 12 12)">'
            '<line x1="9" y1="3" x2="9" y2="8"/>'
            '<line x1="15" y1="3" x2="15" y2="8"/>'
            '<rect x="6" y="8" width="12" height="8" rx="1.8"/>'
            '<path d="M12 16v2.2c0 2 2.4 2 2.4 4.2"/>'
            '</g>'
        ),
    }
    # flow selection → icon key. 'other' has no drawing (do not invent).
    _FLOW_ICON_BY_TYPE = {
        'llm_request': 'engine_to_llm_request',
        'llm_response': 'llm_to_engine_response',
        'tool_call': 'engine_to_tool',
        'tool_result': 'engine_to_tool',
        'domain_index': 'discovery',
        'turn_done': 'turn_completed',
        'failover': 'provider_failover',
        'external': 'mcp_client_to_odoo',
    }
    _FLOW_LEGEND = [
        ('#1565c0', '#ffffff', 'Discovery', False, 'discovery'),
        ('#00a09d', '#ffffff', 'AI Engine \u2192 LLM (request)', False,
         'engine_to_llm_request'),
        ('#1e7e34', '#ffffff', 'LLM \u2192 AI Engine (response)', False,
         'llm_to_engine_response'),
        ('#e67e00', '#ffffff', 'AI Engine \u2192 Tool', False, 'engine_to_tool'),
        ('#c0392b', '#ffffff', 'Supervised', False, 'safe_plan'),
        ('#37474f', '#ffffff', 'Turn completed', False, 'turn_completed'),
        ('#7b1fa2', '#ffffff', 'Provider failover', False, 'provider_failover'),
        ('#039BE5', '#ffffff', 'MCP client \u2192 Odoo', False,
         'mcp_client_to_odoo'),
    ]

    @classmethod
    def _flow_chip_icon_html(cls, icon_key):
        inner = cls._FLOW_ICON_INNER.get(icon_key)
        if not inner:
            return ''
        return (
            '<svg class="o_mcp_flow_chip_icon" width="15" height="15" '
            'viewBox="0 0 24 24" fill="none" stroke="currentColor" '
            'stroke-width="2.35" stroke-linecap="round" '
            'stroke-linejoin="round" aria-hidden="true">%s</svg>' % inner
        )

    @api.model
    def render_flow_legend(self, layout='form'):
        """Build the color-legend HTML from the single source ``_FLOW_LEGEND``.

        ``layout='grid'`` returns the list-view bar (control-panel width, spend
        chip slot on the right, ``o_mcp_log_legend_bar`` for CSS);
        ``layout='form'`` returns the in-sheet banner. Both share the same chips.
        """
        chips = []
        for bg, fg, label, italic, icon_key in self._FLOW_LEGEND:
            style = (
                'background:%s;color:%s;padding:3px 8px;border-radius:3px;'
                'white-space:nowrap;display:inline-flex;align-items:center;'
                'gap:4px;' % (bg, fg)
            )
            if italic:
                style += 'font-style:italic;'
            chips.append(
                '<span class="o_mcp_flow_chip" style="%s">%s%s</span>'
                % (style, self._flow_chip_icon_html(icon_key), label)
            )
        chips_html = ''.join(chips)
        if layout == 'grid':
            return (
                '<div class="o_mcp_log_legend_bar">'
                '<div class="o_mcp_log_legend_chips">%s</div>'
                '<span class="o_mcp_log_usage_chip" hidden="hidden" '
                'role="status"></span>'
                '</div>'
                % chips_html
            )
        return (
            '<div style="display:flex;flex-wrap:wrap;gap:6px;'
            'padding:6px 0 10px 0;font-size:11px;line-height:1.4;">%s</div>'
            % chips_html
        )

    def _compute_flow_legend_html(self):
        legend = self.env['ai.log'].render_flow_legend(layout='form')
        for rec in self:
            rec.flow_legend_html = legend

    @classmethod
    def _icon_key_for_row(cls, flow, access_mode):
        if access_mode == 'write':
            return 'safe_plan'
        return cls._FLOW_ICON_BY_TYPE.get(flow or '')

    @api.depends('flow', 'access_mode', 'flow_label')
    def _compute_flow_icon_html(self):
        for rec in self:
            key = rec._icon_key_for_row(rec.flow, rec.access_mode)
            icon = rec._flow_chip_icon_html(key) if key else ''
            if not icon:
                rec.flow_icon_html = False
                continue
            rec.flow_icon_html = (
                '<span class="o_mcp_flow_row_icon" title="%s">%s</span>'
                % (html_escape(rec.flow_label or ''), icon)
            )

    @api.depends('prompt_data', 'result_summary')
    def _compute_compressed_fields(self):
        """Compressed versions of JSON fields for the list view."""
        for record in self:
            if record.prompt_data:
                try:
                    data = None
                    try:
                        data = json.loads(record.prompt_data)
                        if isinstance(data, str):
                            try:
                                data = json.loads(data)
                            except Exception:
                                pass
                    except json.JSONDecodeError:
                        try:
                            cleaned = record.prompt_data.replace('\\n', '\n').replace('\\"', '"').replace('\\t', '\t')
                            data = json.loads(cleaned)
                            if isinstance(data, str):
                                data = json.loads(data)
                        except Exception:
                            raise
                    compressed = json.dumps(data, separators=(',', ':'), ensure_ascii=False)
                    compressed = re.sub(r'\s+', ' ', compressed).strip()
                    record.prompt_data_compressed = (
                        compressed[:47] + '...' if len(compressed) > 50 else compressed)
                except Exception:
                    text = record.prompt_data.strip()
                    try:
                        if text.startswith('"') and text.endswith('"'):
                            unescaped = json.loads(text)
                            if isinstance(unescaped, str):
                                text = unescaped
                    except Exception:
                        pass
                    text = text.replace('\\n', ' ').replace('\\"', '"').replace('\\t', ' ')
                    text = text.replace('\\r', ' ').replace('\\\\', '\\')
                    text = re.sub(r'\s+', ' ', text)
                    record.prompt_data_compressed = (
                        text[:47] + '...' if len(text) > 50 else text)
            else:
                record.prompt_data_compressed = ''

            if record.result_summary:
                text = record.result_summary.strip()
                text = text.replace('\\n', ' ').replace('\\"', '"')
                text = re.sub(r'\s+', ' ', text)
                record.result_summary_compressed = (
                    text[:147] + '...' if len(text) > 150 else text)
            else:
                record.result_summary_compressed = ''

    # ── Logging entry point ──────────────────────────────────────────

    @api.model
    def create_log_entry(self, user_id, operation_type, tool_name, prompt_data=None,
                         result_data=None, result_summary=None, additional_info=None,
                         user_prompt=None, code_to_execute=None, agent_llm=None,
                         request_size_bytes=None, response_size_bytes=None,
                         request_type=None, prompt_tokens=None, completion_tokens=None,
                         total_tokens=None, cost_usd=None, usage=None,
                         turn=None, turn_step=None,
                         source_channel=None, remote_ip=None, client_label=None,
                         agent_code=None,
                         **legacy):
        """Create a log entry safely, on its own cursor, committing immediately.

        Parameter names are kept stable for callers; they map onto the model
        fields (``operation_type`` -> ``access_mode``, ``request_type`` ->
        ``primitive``, ``tool_name`` -> ``endpoint``, ``agent_llm`` ->
        ``model_name``, ``source_channel`` -> ``origin``). ``category`` is
        computed, so callers no longer pass a payload subtype.

        Args:
            user_id: ID of the user who executed the operation.
            operation_type: 'read' or 'write'.
            tool_name: MCP tool name, resource URI or prompt.
            request_type: MCP primitive ('system'/'tool'/'resource'/'prompt'/'llm').
            source_channel: 'chatboo', 'mcp_client' or 'internal' (door).
            agent_code: ``ai.agent.code`` for the Origin column (agent name).
            agent_llm: Model that processed the request.

        Returns:
            ai.log record, or None on error (logging never breaks operations).
        """
        # Skip only when truly inside a test (TestCursor), not merely because the
        # server was started with --test-enable (which stays True for the whole
        # process life and would otherwise disable the whole history).
        if config['test_enable'] and type(self.env.cr).__name__ == 'TestCursor':
            return None
        try:
            _logger.info(f"TRACE_MCP: create_log_entry START - Endpoint: {tool_name}, User: {user_id}")
            new_cr = self.env.registry.cursor()
            try:
                env_log = api.Environment(new_cr, SUPERUSER_ID, {})

                primitive = (request_type or 'tool')
                if primitive == 'LLM':
                    primitive = 'llm'

                prompt_json = None
                if prompt_data is not None:
                    try:
                        prompt_json = json.dumps(prompt_data, indent=2, default=str, ensure_ascii=False)
                    except Exception as e:
                        prompt_json = f"Error serializing prompt: {str(e)}\nData: {str(prompt_data)[:1000]}"

                result_json = None
                if result_data is not None:
                    try:
                        if isinstance(result_data, dict) and 'content' in result_data:
                            content = result_data.get('content', [])
                            if content and isinstance(content, list) and len(content) > 0:
                                first_item = content[0]
                                if isinstance(first_item, dict) and 'text' in first_item and isinstance(first_item['text'], str):
                                    result_json = first_item['text']
                                else:
                                    result_json = json.dumps(result_data, indent=2, default=str, ensure_ascii=False)
                            else:
                                result_json = json.dumps(result_data, indent=2, default=str, ensure_ascii=False)
                        else:
                            result_json = json.dumps(result_data, indent=2, default=str, ensure_ascii=False)
                    except Exception as e:
                        result_json = f"Error serializing result: {str(e)}\nData: {str(result_data)[:1000]}"

                max_length = 100000  # ~100KB per field
                if prompt_json and len(prompt_json) > max_length:
                    prompt_json = prompt_json[:max_length] + "\n... (truncated)"
                if result_json and len(result_json) > max_length:
                    result_json = result_json[:max_length] + "\n... (truncated)"

                if request_size_bytes is None:
                    request_size_bytes = len(prompt_json.encode('utf-8')) if prompt_json else 0
                if response_size_bytes is None:
                    response_size_bytes = len(result_json.encode('utf-8')) if result_json else 0

                user_prompt_limited = None
                if user_prompt:
                    user_prompt_limited = user_prompt[:max_length] if len(user_prompt) > max_length else user_prompt

                code_to_execute_limited = None
                if code_to_execute:
                    code_to_execute_limited = code_to_execute[:max_length] if len(code_to_execute) > max_length else code_to_execute

                if usage:
                    from ..utils.llm_usage import usage_log_fields
                    _pt, _ct, _tt, _cost = usage_log_fields(usage)
                    if prompt_tokens is None:
                        prompt_tokens = _pt
                    if completion_tokens is None:
                        completion_tokens = _ct
                    if total_tokens is None:
                        total_tokens = _tt
                    if cost_usd is None:
                        cost_usd = _cost

                # Capture remote IP centrally when the caller did not provide it.
                from ..utils.mcp_logging import (
                    normalize_remote_ip,
                    request_log_stamp,
                    resolve_client_label,
                    resolve_log_agent,
                )
                remote_ip = normalize_remote_ip(remote_ip)
                ctx = self.env.context or {}
                stamp = request_log_stamp()
                if not source_channel:
                    source_channel = (
                        ctx.get('mcp_source_channel')
                        or stamp.get('source_channel')
                    )
                if not client_label:
                    client_label = (
                        ctx.get('mcp_client_label')
                        or stamp.get('client_label')
                    )
                origin = source_channel or 'internal'
                if origin not in ('chatboo', 'mcp_client', 'internal'):
                    origin = 'internal'
                # Isolated cursor has empty context — take the code from the
                # caller env / request stamp / prompt before searching ai.agent.
                if not agent_code:
                    agent_code = (
                        ctx.get('mcp_agent_code')
                        or stamp.get('agent_code')
                    )
                if not agent_code and isinstance(prompt_data, dict):
                    agent_code = prompt_data.get('agent_code')
                agent = resolve_log_agent(env_log, agent_code)
                client_label = resolve_client_label(
                    env_log, user_id, origin,
                    explicit=client_label, agent_code=agent_code,
                )

                log_entry = env_log['ai.log'].create({
                    'user_id': user_id,
                    'timestamp': fields.Datetime.now(),
                    'access_mode': operation_type,
                    'primitive': primitive,
                    'endpoint': tool_name,
                    'prompt_data': prompt_json,
                    'result_data': result_json,
                    'result_summary': result_summary[:5000] if result_summary and len(result_summary) > 5000 else result_summary,
                    'additional_info': additional_info[:5000] if additional_info and len(additional_info) > 5000 else additional_info,
                    'user_prompt': user_prompt_limited,
                    'code_to_execute': code_to_execute_limited,
                    'model_name': agent_llm[:255] if agent_llm and len(agent_llm) > 255 else agent_llm,
                    'request_size_bytes': request_size_bytes,
                    'response_size_bytes': response_size_bytes,
                    'prompt_tokens': prompt_tokens,
                    'completion_tokens': completion_tokens,
                    'total_tokens': total_tokens,
                    'cost_usd': cost_usd,
                    'turn': turn[:8] if turn else None,
                    'turn_step': turn_step or 0,
                    'origin': origin,
                    'agent_id': agent.id if agent else False,
                    'remote_ip': remote_ip,
                    'client_label': client_label[:255] if client_label else None,
                })

                log_id = log_entry.id
                if new_cr:
                    new_cr.commit()
                _logger.info(f"MCP: create_log_entry SUCCESS - ID: {log_id}")
                return log_entry
            finally:
                if new_cr:
                    new_cr.close()
        except Exception as e:
            # Never let a logging failure break the actual operation.
            _logger.exception("TRACE_MCP: CRITICAL FAILURE creating log entry (Safe Transaction): %s", str(e))
            return None

    # ── Maintenance ──────────────────────────────────────────────────

    @api.model
    def _delete_oldest_logs(self, keep_count=None):
        """Delete the oldest logs, keeping the most recent ones.

        Args:
            keep_count: Number of most recent logs to keep. If None, deletes all.

        Returns:
            dict: Notification action with the result.
        """
        total_count = self.sudo().search_count([])
        if total_count == 0:
            return mcp_ui.client_notification(
                _('Information'),
                _('No logs to delete.'),
                notification_type='info',
                sticky=False,
                reload=True,
            )

        if keep_count is None:
            logs_to_delete = self.sudo().search([])
            deleted_count = len(logs_to_delete)
            logs_to_delete.unlink()
            message = _('All logs deleted (%s record(s))') % deleted_count
        else:
            recent_logs = self.sudo().search([], order='timestamp desc', limit=keep_count)
            recent_ids = recent_logs.ids
            logs_to_delete = self.sudo().search([('id', 'not in', recent_ids)])
            deleted_count = len(logs_to_delete)
            logs_to_delete.unlink()
            message = _('%(deleted)s old log(s) deleted, keeping the %(kept)s most recent') % {
                'deleted': deleted_count, 'kept': keep_count,
            }

        return mcp_ui.client_notification(
            _('Log Deletion'),
            message,
            sticky=False,
            reload=True,
        )

    @api.model
    def _cron_purge_old_logs(self):
        """Delete rows older than ``pns_ai_mcp.log_retention_days`` (0 = keep)."""
        from datetime import timedelta
        raw = self.env['ir.config_parameter'].sudo().get_param(
            LOG_RETENTION_PARAM, DEFAULT_LOG_RETENTION_DAYS,
        )
        try:
            days = int(raw)
        except (TypeError, ValueError):
            days = DEFAULT_LOG_RETENTION_DAYS
        if days <= 0:
            return 0
        cutoff = fields.Datetime.now() - timedelta(days=days)
        old = self.sudo().search([('timestamp', '<', cutoff)])
        count = len(old)
        if count:
            old.unlink()
            _logger.info('ai.log: purged %d row(s) older than %d days', count, days)
        return count

    # Round-level endpoints already rolled into ``orchestration_summary``.
    # Counting them again would double Chatboo turn spend.
    _USAGE_SUMMARY_EXCLUDE_ENDPOINTS = (
        'llm_orchestration',
        'llm_response',
        'llm_tool_request',
        'llm_response_hdr',
        'provider_failover',
    )

    @api.model
    def get_user_usage_summary(self, domain=None, days=30):
        """Aggregate LLM spend for rows matching ``domain`` (Activity list filter).

        When ``domain`` is passed (from the list search model), totals reflect
        the current filter plus ``ir.rule``. Round-level endpoints are still
        excluded to avoid double-counting turn spend — see
        ``docs/llm_usage_metering.md``.

        Legacy callers without ``domain`` keep the old 30-day / own-user window.
        """
        from datetime import timedelta

        from odoo.osv import expression

        from ..utils.display_currency import get_display_currency
        from ..utils.usage_display import format_usage_chip

        exclude = [
            ('endpoint', 'not in', list(self._USAGE_SUMMARY_EXCLUDE_ENDPOINTS)),
        ]
        window = None
        if domain is not None:
            base = list(domain)
        else:
            try:
                window = max(1, min(int(days or 30), 366))
            except (TypeError, ValueError):
                window = 30
            since = fields.Datetime.now() - timedelta(days=window)
            base = [
                ('user_id', '=', self.env.uid),
                ('primitive', '=', 'llm'),
                ('timestamp', '>=', since),
            ]
        merged = expression.AND([base, exclude])
        groups = self.read_group(merged, ['total_tokens', 'cost_usd'], [])
        total_tokens = 0
        cost_usd = 0.0
        if groups:
            row = groups[0]
            total_tokens = int(row.get('total_tokens') or 0)
            cost_usd = float(row.get('cost_usd') or 0.0)
        usage = {}
        if total_tokens:
            usage['total_tokens'] = total_tokens
        if cost_usd:
            usage['cost'] = cost_usd
        chip = format_usage_chip(self.env, usage) if usage else ''
        return {
            'days': window,
            'total_tokens': total_tokens,
            'cost_usd': cost_usd,
            'display_currency': get_display_currency(self.env),
            'spend_label': chip,
            'filtered': domain is not None,
        }

    # ── Export ───────────────────────────────────────────────────────

    _LOG_EXPORT_ONLY = (
        'timestamp', 'origin', 'agent_id', 'access_mode', 'primitive', 'endpoint',
        'category', 'flow', 'flow_label', 'turn', 'turn_step',
        'model_name', 'result_summary',
    )

    @api.model
    def action_export_logs(self, *args, **kwargs):
        """Export all AI operation log entries to a downloadable JSON file.

        Export-only (logs are operational data, not config). Bodies and
        token payloads stay out via ``only_fields``.
        """
        ensure_ai_admin(self.env)
        logs = self.search([])
        if not logs:
            return mcp_ui.open_json_export_empty_wizard(
                self.env,
                dialog_title=_('Export'),
                message=_('There are no log entries to export.'),
            )
        export_data = [
            export_record_dict(
                rec,
                only_fields=self._LOG_EXPORT_ONLY,
                extra={'user': rec.user_id.name or ''},
            )
            for rec in logs
        ]
        filename = mcp_ui.build_export_filename(self.env, 'ai_logs', 'json')
        attachment = mcp_ui.write_json_attachment(
            self.env, filename, export_data,
        )
        return mcp_ui.open_json_export_wizard(
            self.env,
            dialog_title=_('Export result'),
            summary_text=_('%s log entry(ies) exported.') % len(export_data),
            count=len(export_data),
            attachment=attachment,
        )
