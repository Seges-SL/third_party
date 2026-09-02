# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""PNS AI MCP - Provider. PATANEGRA Soft (https://patanegra.com).

Part of Patanegra Soft Suite (`pns_suite`), distributed via Patanegra Soft Hub.
LLM provider configuration (OpenAI-compatible drivers, Anthropic, etc.) for the
Patanegra Application Agent Protocol (PAAP).
Licensed under the Apache License 2.0 - see LICENSE.
"""
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from ..utils import mcp_ui
from ..utils.import_export_guard import ensure_ai_admin
from ..utils.portable_io import export_record_dict
import logging
import json

_logger = logging.getLogger(__name__)

def safe_error_message(msg):
    """Convierte un mensaje a ASCII seguro para evitar problemas de codificación en UserError"""
    if isinstance(msg, bytes):
        msg = msg.decode('utf-8', errors='replace')
    return str(msg).encode('ascii', errors='replace').decode('ascii')


import requests

_logger = logging.getLogger(__name__)

class AIProviderModel(models.Model):
    _name = 'ai.provider.model'
    _description = 'AI Provider Model'
    _order = 'name'

    name = fields.Char(required=True)
    provider_id = fields.Many2one('ai.provider', string='Provider', ondelete='cascade')

class AIProvider(models.Model):
    """LLM gateway configuration — one record per API endpoint.

    An AIProvider represents a single LLM API connection (e.g. an OpenAI key,
    an Anthropic account, a local Ollama instance). It stores the endpoint URL,
    API key, model selection, and provider-specific quirks.

    Relationship chain (how a user message reaches an LLM)::

        User message
          → ai.agent (e.g. 'chat', 'code', 'summary')
            → ai.agent.provider (priority-ordered list)
              → ai.provider (this model — gateway + credentials)
                → LLM driver (openai_driver / anthropic_driver / ollama_driver)
                  → HTTP POST to the LLM API

    The ai.execution.engine orchestrates this chain with failover: if the
    primary provider fails, it tries the next entry in priority order.

    Protocols and their drivers:
      - 'openai':    OpenAIDriver    — OpenAI, Azure, any OpenAI-compatible gateway
                                       (incl. local LM Studio / Ollama in OpenAI mode)
      - 'anthropic': AnthropicDriver — Anthropic Claude (Messages API)

    Key fields:
      - endpoint:           Full POST URL (e.g. https://api.openai.com/v1/chat/completions)
      - api_key:            LLM gateway credential (admin-only in UI). **Not** the per-user
                            MCP token in ``ai.mcp.user`` — see ``docs/dos_credenciales_api.md``.
                            Server-side reads use ``_api_key_for_inference()`` (private, no RPC).
      - default_model:      Model identifier (e.g. 'gpt-4o', 'claude-sonnet-4-20250514')
      - temperature_support: 'yes'/'no'/'unknown' — auto-detected for Anthropic models
      - usage_support:      'yes'/'no'/'unknown' — probed from the completion body
      - model_ids:          Available models discovered via /v1/models endpoint
    """
    _name = 'ai.provider'
    _description = 'AI Provider'
    _rec_name = 'name'

    name = fields.Char(string='Name', required=True)
    alias = fields.Char(
        string='Alias',
        help="Optional label shown in Chatboo's provider picker "
             "(e.g. 'Grok 4.5 (normal use)'). When empty, Chatboo shows "
             "host -> model. Does not change the fixed provider/model pair.",
    )
    protocol = fields.Selection([
        ('openai', 'OpenAI / OpenAI-Compatible'),
        ('anthropic', 'Anthropic (Claude)'),
    ], string='Protocol', required=True, default='openai',
        help="Protocolo de transporte / dialecto de API que habla el driver. "
             "OpenAI-compatible cubre OpenAI, Azure y gateways locales "
             "(LM Studio, Ollama en modo OpenAI); Anthropic usa la Messages API.")
    endpoint = fields.Char(
        string='Endpoint URL',
        help="URL POST exacta que usa el driver (chat/completions o messages). "
             "Pégala tal cual desde la documentación de tu gateway; no se "
             "reescribe al guardar.",
    )
    endpoint_setup_guide = fields.Html(
        string='Endpoint setup guide',
        compute='_compute_endpoint_setup_guide',
        sanitize=False,
    )
    api_key = fields.Char(
        string='API Key',
        help="Clave de autenticación que se envía al proveedor de IA.",
        groups="pns_ai_mcp.group_ai_admin",
    )

    def _api_key_for_inference(self):
        """Return provider API key for server-side LLM calls (private).

        The field is admin-only in UI; inference clients (Chatboo, MCP) must
        still authenticate to external LLMs on behalf of permitted users.
        Not a public RPC entry point — leading underscore blocks call_kw.
        """
        self.ensure_one()
        return self.sudo().api_key or ''

    # Model Selection
    model_name = fields.Char(
        related='model_id.name', string='Model', readonly=True, store=True,
        help="Nombre efectivo del modelo; refleja el modelo seleccionado (no editable).",
    )
    model_id = fields.Many2one('ai.provider.model', string='Selected Model', domain="[('provider_id', '=', id)]")
    available_model_ids = fields.One2many('ai.provider.model', 'provider_id', string='Available Models')

    # Creativity Configuration
    temperature = fields.Float(
        string='Temperature',
        default=0.7,
        help="Control de creatividad del modelo (0.0 - 1.0):\n"
             "- 0.0: Determinista (siempre la misma respuesta)\n"
             "- 0.1-0.3: Preciso (código, SQL, datos)\n"
             "- 0.4-0.7: Equilibrado (conversación natural) - Recomendado\n"
             "- 0.8-1.0: Creativo (lluvia de ideas, redacción)",
    )
    temperature_support = fields.Selection(
        [
            ('unknown', 'Unknown'),
            ('yes', 'Supported'),
            ('no', 'Not supported'),
        ],
        string='Temperature support',
        default='unknown',
        readonly=True,
        copy=False,
        help="Indica si el modelo seleccionado acepta el parámetro `temperature`. "
             "Se detecta con una sonda mínima al seleccionar un modelo o probar la "
             "conexión. Si es 'No soportado', el parámetro se omite en cada "
             "petición (algunos modelos recientes lo rechazan).",
    )
    usage_support = fields.Selection(
        [
            ('unknown', 'Unknown'),
            ('yes', 'Supported'),
            ('no', 'Not supported'),
        ],
        string='Usage in response',
        default='unknown',
        readonly=True,
        copy=False,
        help="Whether the completion body includes a usage object (tokens, "
             "and cost when the vendor sends it). Probed on Test Connection "
             "and upgraded unknown→yes on a live chat turn. A missing usage "
             "on one turn does not downgrade yes→no.",
    )
    is_on_premise = fields.Boolean(
        string='On premises',
        default=False,
        help="Self-hosted / own-server inference (Lemonade, Ollama, vLLM, …).\n\n"
             "When checked: if the API omits cost, Chatboo advertises 0 so the "
             "chip shows 0,00 € (or display currency) instead of \"-\". "
             "If the gateway does report a cost (e.g. estimated electricity), "
             "that value is kept.\n\n"
             "When unchecked (cloud): missing cost stays unknown (\"-\").",
    )

    footmode = fields.Selection(
        selection=[
            ('foot-verbose', 'foot-verbose'),
            ('foot-laconic', 'foot-laconic'),
        ],
        string='Footmode',
        default='foot-verbose',
        help="Footer after Chatboo-composed (painter-local) tables.\n\n"
             "Values:\n"
             "• foot-verbose (default) — ask the model for a short warm closing "
             "line after the server-rendered table.\n"
             "• foot-laconic — skip that footer (small models often invent figures "
             "there) and, if the inference server honours it, disable internal "
             "thinking.\n\n"
             "Suspended when painter is painter-free (the model owns the whole "
             "bubble; there is no local table+footer path).\n"
             "Slash this turn only: /foot-verbose or /foot-laconic (does not write "
             "this field).\n"
             "Only applies to this provider, not to others in the failover chain.",
    )
    painter = fields.Selection(
        selection=[
            ('painter-local', 'painter-local'),
            ('painter-free', 'painter-free'),
        ],
        string='Painter',
        default='painter-local',
        help="Who composes the Chatboo bubble for this provider.\n\n"
             "Values:\n"
             "• painter-local (default) — Chatboo paints HTML tables/charts from "
             "structured rows; after a server table the model writes at most a "
             "short footer (see footmode). Non-tabular answers (time, cards, "
             "greetings) are still composed by the model.\n"
             "• painter-free — the model owns the entire UI (Markdown, HTML, "
             "native charts). footmode and showmode are suspended for that bubble.\n\n"
             "Slash this turn only: /painter-local or /painter-free (does not write "
             "this field). A skill may set painter for its invocation.\n"
             "Only applies to this provider, not to others in the failover chain.",
    )

    context_window = fields.Integer(
        string='Context Window (Tokens)',
        default=32768,
        help="Ventana de contexto física del modelo de este proveedor (en tokens): "
             "la memoria máxima de conversación que envía el orquestador de "
             "inferencia. Solo aplica en modo cliente de inferencia (Chatboo, OCR); "
             "no tiene efecto cuando un cliente MCP externo (Cursor, Claude Desktop) "
             "gobierna el modelo.\n\n"
             "DEBE ser <= al contexto real con el que el backend cargó el modelo "
             "(p. ej. LEMONADE_CTX_SIZE de Lemonade). Si se pone MÁS ALTO, los "
             "prompts grandes desbordan el modelo y la petición hace failover al "
             "siguiente proveedor de la cadena.\n\n"
             "Cuando se supera el límite, el orquestador descarta primero los "
             "turnos MÁS ANTIGUOS; el system prompt y la composición de contextos "
             "del agente se conservan SIEMPRE (nunca se recortan).",
    )

    context_window_display = fields.Char(
        string='Context window',
        compute='_compute_context_window_display',
        help="Ventana de contexto legible (K = 1024 tokens, M = 1024K).",
    )

    context_window_tokens = fields.Char(
        string='Context tokens',
        compute='_compute_context_window_tokens',
        help="Ventana de contexto en tokens, como texto plano para copiar/pegar "
             "en configuraciones de inferencia (LEMONADE_CTX_SIZE, --ctx-size, "
             "num_ctx…).",
    )

    usage_day_ids = fields.One2many(
        'ai.provider.usage.day',
        'provider_id',
        string='Daily usage',
        copy=False,
        help="Daily token and cost totals for this provider. Duplicating the "
             "provider does not copy this history.",
    )

    agent_provider_ids = fields.One2many(
        'ai.agent.provider',
        'provider_id',
        string='Agent links',
        help="Enlaces agente↔proveedor (ai.agent.provider) que referencian a "
             "este proveedor. Cada enlace coloca al proveedor en la cadena de "
             "failover de un agente con una prioridad.",
    )

    @api.depends('context_window')
    def _compute_context_window_tokens(self):
        for provider in self:
            n = int(provider.context_window or 0)
            provider.context_window_tokens = str(n) if n > 0 else ''

    @api.depends('context_window')
    def _compute_context_window_display(self):
        for provider in self:
            provider.context_window_display = self._humanize_tokens(provider.context_window)

    @staticmethod
    def _humanize_tokens(value):
        n = int(value or 0)
        if n <= 0:
            return ''
        mega = 1024 * 1024
        kilo = 1024
        if n >= mega:
            return ('%.1f' % (n / mega)).rstrip('0').rstrip('.') + 'M'
        if n >= kilo:
            return ('%.1f' % (n / kilo)).rstrip('0').rstrip('.') + 'K'
        return str(n)
    agent_ids = fields.Many2many(
        'ai.agent',
        compute='_compute_agent_ids',
        string='Agents',
    )
    
    @api.depends('agent_provider_ids.agent_id')
    def _compute_agent_ids(self):
        for provider in self:
            provider.agent_ids = provider.agent_provider_ids.mapped('agent_id')

    @api.depends('protocol')
    def _compute_endpoint_setup_guide(self):
        openai_tpl = _(
            '<p><strong>URL template</strong> (shape only — replace host and port). '
            'Paste your resolved URL in the field below; Odoo does not modify it on save.</p>'
            '<p><code>https://&lt;url&gt;&lt;:port&gt;/api/v1/chat/completions</code></p>'
            '<p><em>Fetch Models</em> derives <code>…/models</code> from this URL.</p>'
        )
        anthropic_tpl = _(
            '<p><strong>URL template</strong> (shape only — replace host and port). '
            'Paste your resolved URL in the field below; Odoo does not modify it on save.</p>'
            '<p><code>https://&lt;url&gt;&lt;:port&gt;/v1/messages</code></p>'
            '<p><em>Fetch Models</em> derives <code>…/v1/models</code> from this URL.</p>'
        )
        for provider in self:
            if provider.protocol == 'anthropic':
                provider.endpoint_setup_guide = anthropic_tpl
            else:
                provider.endpoint_setup_guide = openai_tpl

    @api.constrains('temperature')
    def _check_temperature(self):
        for record in self:
            if record.temperature < 0.0 or record.temperature > 2.0:
                raise ValidationError("Temperature must be between 0.0 and 2.0 (recommended: 0.0-1.0)")
    
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if 'endpoint' in vals:
                vals['endpoint'] = self._sanitize_endpoint(vals.get('endpoint'))
        return super(AIProvider, self).create(vals_list)

    def write(self, vals):
        if 'endpoint' in vals:
            vals['endpoint'] = self._sanitize_endpoint(vals.get('endpoint'))
        return super(AIProvider, self).write(vals)

    @staticmethod
    def _sanitize_endpoint(endpoint):
        """Trim whitespace only; endpoint is stored exactly as configured."""
        return (endpoint or '').strip()

    @staticmethod
    def _derive_models_url(endpoint, protocol):
        """Build a /models URL from the configured POST endpoint (read-only helper)."""
        if protocol == 'anthropic':
            if not endpoint:
                return 'https://api.anthropic.com/v1/models'
            base = endpoint.rstrip('/')
            for path in ('/v1/messages', '/api/v1/chat/completions', '/v1/chat/completions', '/chat/completions'):
                if path in base:
                    base = base.split(path)[0].rstrip('/')
            if base.endswith('/v1'):
                return '%s/models' % base
            return '%s/v1/models' % base

        if not endpoint:
            return 'https://api.openai.com/v1/models'
        base = endpoint.rstrip('/')
        for path in ('/api/v1/chat/completions', '/v1/chat/completions', '/chat/completions'):
            if path in base:
                base = base.split(path)[0].rstrip('/')
                break
        if base.endswith('/api/v1'):
            return '%s/models' % base
        if base.endswith('/v1'):
            return '%s/models' % base
        if '/api/v1/' in endpoint or endpoint.rstrip('/').endswith('/api/v1'):
            return '%s/api/v1/models' % base
        return '%s/v1/models' % base

    def action_fetch_models(self):
        """Fetch models from the provider's endpoint."""
        self.ensure_one()
        from ..lib.llm.drivers import get_llm_driver

        driver = get_llm_driver(self.protocol)
        url = driver.models_url(self.endpoint)
        headers = driver.auth_headers(self.api_key or '')
            
        try:
            # 1. Try Fetching
            response = requests.get(url, headers=headers, timeout=10)
            
            # 2. Parse Response
            models_list = []
            if response.status_code == 200:
                data = response.json()
                
                # OpenAI Format: {"data": [{"id": "model-name", ...}]}
                if 'data' in data and isinstance(data['data'], list):
                     models_list = [item['id'] for item in data['data']]
                else:
                    keys_str = safe_error_message(str(list(data.keys())))
                    error_final = safe_error_message(_("Unknown response format: %s") % keys_str)
                    raise UserError(error_final)
            else:
                 response_text = safe_error_message(response.text)
                 error_final = safe_error_message(_("Remote Error %s: %s") % (response.status_code, response_text))
                 raise UserError(error_final)

            if not models_list:
                raise UserError(_("No models found in the response."))

            # 3. Upsert models by name — preserve existing records, add the newly
            # listed ones, drop the stale ones. The list feeds the model selector.
            Model = self.env['ai.provider.model']
            listed = list(dict.fromkeys(models_list))  # de-dup, keep order
            existing_by_name = {m.name: m for m in self.available_model_ids}

            added = 0
            for m_name in listed:
                if m_name not in existing_by_name:
                    Model.create({'name': m_name, 'provider_id': self.id})
                    added += 1

            stale = self.available_model_ids.filtered(lambda m: m.name not in listed)
            removed = len(stale)
            if stale:
                stale.unlink()

            # If nothing selected and list exists, pick first
            if not self.model_id and self.available_model_ids:
                 self.model_id = self.available_model_ids[0]

            return mcp_ui.client_notification(
                _("Models Refreshed"),
                _("%s model(s): %s new, %s removed.") % (len(listed), added, removed),
                sticky=False,
            )
            
        except requests.exceptions.SSLError as e:
            error_str = str(e)
            if "wrong version number" in error_str:
                 raise UserError(_("SSL Error: It seems you are using HTTPS on a non-SSL port (likely port 11434). Please try using 'http://' instead of 'https://' in your Endpoint URL."))
            raise UserError(_("SSL Error: %s") % safe_error_message(error_str))
        except Exception as e:
            # Asegurar que el mensaje de error esté en ASCII para evitar problemas de codificación
            error_str = safe_error_message(str(e))
            error_msg = safe_error_message(_("Failed to fetch models: %s") % error_str)
            raise UserError(error_msg)

    @api.onchange('model_id')
    def _onchange_model_id(self):
        # Sondear la temperatura al seleccionar un LLM (best-effort, no bloquea
        # el formulario ante fallos: deja 'unknown' si no se puede determinar).
        self.temperature_support = self._probe_temperature_support(timeout=8)

    @api.onchange('protocol', 'endpoint')
    def _onchange_reset_temperature_support(self):
        # Cambiar de endpoint/tipo invalida la capacidad cacheada del modelo.
        self.temperature_support = 'unknown'
        self.usage_support = 'unknown'

    def _probe_temperature_support(self, target_model=None, timeout=15):
        """Devuelve 'yes'/'no'/'unknown' según si el modelo acepta `temperature`.

        Solo aplica a Anthropic; para el resto se asume 'yes'. Best-effort: si
        no hay datos suficientes o la red falla, devuelve 'unknown' (no lanza).
        """
        self.ensure_one()
        model = target_model or (self.model_id.name if self.model_id else None) or self.model_name
        if not model:
            return 'unknown'
        if self.protocol != 'anthropic':
            return 'yes'
        if not self.endpoint:
            return 'unknown'
        try:
            from ..lib.llm.drivers import get_llm_driver

            endpoint = self.endpoint or ''
            if endpoint and not endpoint.startswith('http'):
                endpoint = 'https://' + endpoint
            driver = get_llm_driver(self.protocol)
            driver.initialize({
                'protocol': self.protocol,
                'endpoint': endpoint,
                'api_key': self.api_key or '',
                'model_name': model,
                'temperature': self.temperature or 0.0,
            })
            if hasattr(driver, 'probe_temperature'):
                return 'yes' if driver.probe_temperature(timeout=timeout) else 'no'
        except Exception as e:
            _logger.info("Temperature probe inconclusive for %s: %s", self.name, e)
        return 'unknown'

    def test_connection(self):
        """Test connection to the AI provider using LiteLLM"""
        self.ensure_one()
        
        target_model = self.model_id.name or self.model_name
        if not target_model:
            raise UserError(_("Please select a model or enter a Model Name."))

        try:
            from ..lib.llm.drivers import get_llm_driver

            driver = get_llm_driver(self.protocol)
            config = {
                "protocol": self.protocol,
                "endpoint": self.endpoint,
                "api_key": self.api_key or "dummy-key-for-local",
                "model_name": target_model,
                "temperature": 0.0,
                "send_temperature": self.temperature_support != 'no',
            }
            
            # La API key solo se guarda hasheada; no se propaga X-Mcp-Token a la
            # LLM (las tools se ejecutan in-process, la LLM no reentra en /mcp).
            config["extra_headers"] = {}
                
            driver.initialize(config)

            messages = [{"role": "user", "content": "Just say 'ok' represent it in exactly 2 letters"}]
            
            response = driver.chat_completion(messages=messages, tools=None)
            
            if "choices" in response and response["choices"]:
                content = response["choices"][0].get("message", {}).get("content", "")
            else:
                content = str(response)
            
            # LOG INTO DB ORCHESTRATOR
            try:
                if 'ai.log' in self.env:
                    self.env['ai.log'].create_log_entry(
                        user_id=self.env.user.id,
                        operation_type='read',
                        tool_name='Test Connection Web',
                        prompt_data={"model": target_model, "messages": messages},
                        result_data=response,
                        result_summary="Manual Test LLM Connection",
                        request_type='system',
                        agent_llm=target_model,
                        source_channel='internal',
                    )
            except Exception as e:
                _logger.warning(f"Failed to log test connection to DB: {e}")

            # Sonda de temperatura: detecta y cachea si el modelo acepta el
            # parámetro. Best-effort; no convierte un test correcto en fallo.
            support = self._probe_temperature_support(target_model=target_model)
            extra = ""
            if support != 'unknown':
                self.temperature_support = support
                extra = _("\nTemperature: %s") % (
                    _("supported") if support == 'yes' else _("not supported (omitted)")
                )

            # Sonda de consumo: forma del JSON de completion, no el host.
            from ..utils.llm_usage import classify_usage_support
            usage_flag = classify_usage_support(response)
            if usage_flag != 'unknown':
                self.usage_support = usage_flag
                extra += _("\nUsage in response: %s") % (
                    _("yes") if usage_flag == 'yes' else _("no")
                )

            return mcp_ui.client_notification(
                _("Connection Successful"),
                _("Provider responded: %s%s") % (content, extra),
                sticky=False,
            )
        except Exception as e:
            _logger.error(f"AI Provider Test Failed: {e}", exc_info=True)
            error_str = safe_error_message(str(e))
            error_msg = safe_error_message(_("Connection Failed: %s") % error_str)
            raise UserError(error_msg)

    def _mark_usage_support_yes(self):
        """Best-effort unknown→yes on a short cursor (not the ReAct txn)."""
        self.ensure_one()
        if (self.usage_support or 'unknown') != 'unknown':
            return
        pid = self.id
        try:
            with self.env.registry.cursor() as cr:
                cr.execute("SET LOCAL lock_timeout = '2s'")
                cr.execute(
                    "UPDATE ai_provider "
                    "SET usage_support = 'yes', "
                    "write_date = (now() at time zone 'UTC') "
                    "WHERE id = %s AND usage_support = 'unknown'",
                    (pid,),
                )
                cr.commit()
        except Exception:
            _logger.debug(
                'ai.provider usage_support probe skipped for id=%s',
                pid, exc_info=True,
            )

    def action_export_providers(self, *args, **kwargs):
        """Export all AI providers to a JSON file."""
        ensure_ai_admin(self.env)
        # Incluir todos los servidores, incluso los inactivos
        servers = self.with_context(active_test=False).search([])
        if not servers:
            return mcp_ui.open_json_export_empty_wizard(
                self.env,
                dialog_title=_('Export'),
                message=_('There are no providers to export.'),
            )
        
        export_data = []
        for server in servers:
            try:
                server_data = export_record_dict(server, skip_fields={'id'})
            except Exception:
                server_data = {'name': server.name or '?'}
            # Relational extras (need explicit handling)
            try:
                server_data['available_models'] = [m.name for m in server.available_model_ids]
            except Exception:
                pass
            try:
                server_data['selected_model'] = server.model_id.name if server.model_id else None
            except Exception:
                pass
            try:
                server_data['failovers'] = [
                    {
                        'agent_code': a.agent_id.code,
                        'agent_name': a.agent_id.name,
                        'priority': a.priority,
                        'active': a.active,
                    }
                    for a in server.agent_provider_ids
                ]
            except Exception:
                pass
            try:
                server_data['usage_days'] = server.usage_day_ids.to_export_rows()
            except Exception:
                pass
            export_data.append(server_data)
        
        filename = mcp_ui.build_export_filename(self.env, 'ai_providers', 'json')
        attachment = mcp_ui.write_json_attachment(
            self.env, filename, export_data,
        )
        
        return mcp_ui.open_json_export_wizard(
            self.env,
            dialog_title=_('Export result'),
            summary_text=_('%s provider(s) exported.') % len(export_data),
            count=len(export_data),
            attachment=attachment,
        )

    def action_export_selected(self, *args, **kwargs):
        """Export selected AI providers to JSON (tree multi-select action)."""
        ensure_ai_admin(self.env)
        if not self:
            return mcp_ui.open_json_export_empty_wizard(
                self.env,
                dialog_title=_('Export'),
                message=_('No providers selected for export.'),
            )
        export_data = []
        for server in self:
            try:
                server_data = export_record_dict(server, skip_fields={'id'})
            except Exception:
                server_data = {'name': server.name or '?'}
            try:
                server_data['available_models'] = [m.name for m in server.available_model_ids]
            except Exception:
                pass
            try:
                server_data['selected_model'] = server.model_id.name if server.model_id else None
            except Exception:
                pass
            try:
                server_data['failovers'] = [
                    {
                        'agent_code': a.agent_id.code,
                        'agent_name': a.agent_id.name,
                        'priority': a.priority,
                        'active': a.active,
                    }
                    for a in server.agent_provider_ids
                ]
            except Exception:
                pass
            try:
                server_data['usage_days'] = server.usage_day_ids.to_export_rows()
            except Exception:
                pass
            export_data.append(server_data)

        filename = mcp_ui.build_export_filename(self.env, 'ai_providers_selected', 'json')
        attachment = mcp_ui.write_json_attachment(
            self.env, filename, export_data,
        )
        return mcp_ui.open_json_export_wizard(
            self.env,
            dialog_title=_('Export result'),
            summary_text=_('%s provider(s) exported.') % len(export_data),
            count=len(export_data),
            attachment=attachment,
        )

    def action_import_providers(self, *args, **kwargs):
        """Open wizard to import AI providers from JSON."""
        ensure_ai_admin(self.env)
        return {
            'type': 'ir.actions.act_window',
            'name': _('Import AI Providers'),
            'res_model': 'pns_ai_mcp.import_servers_wizard',
            'view_mode': 'form',
            'views': [[False, 'form']],
            'target': 'new',
        }

