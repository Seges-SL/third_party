# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""LLM provider configuration (OpenAI-compatible HTTP APIs, Anthropic, …)."""
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
    _order = 'maker, name'

    name = fields.Char(required=True)
    provider_id = fields.Many2one('ai.provider', string='Provider', ondelete='cascade')
    title = fields.Char(string='Title')
    maker = fields.Char(string='Maker', index=True)
    context_length = fields.Integer(string='Context length')
    context_label = fields.Char(string='Context')
    max_output_label = fields.Char(string='Max output')
    price_in_label = fields.Char(string='Input / M')
    price_out_label = fields.Char(string='Output / M')
    price_cache_label = fields.Char(string='Cache read / M')
    modality_label = fields.Char(string='Modalities')
    apt_conversation = fields.Boolean(string='Conversation')
    apt_reasoning = fields.Boolean(string='Reasoning')
    apt_batch = fields.Boolean(string='Batch')
    apt_vision = fields.Boolean(string='Vision')
    apt_audio = fields.Boolean(string='Audio')
    apt_transcriptions = fields.Boolean(
        string='Whisper',
        help="Gateway architecture is audio→text with no text input "
             "(file ASR: Whisper and clones). Not guessed from the slug.",
    )
    apt_file = fields.Boolean(string='File')
    apt_decision = fields.Boolean(string='Decision')
    apt_label = fields.Char(
        string='Suitable for',
        compute='_compute_apt_label',
    )

    def _compute_apt_label(self):
        for rec in self:
            parts = []
            if rec.apt_conversation:
                parts.append(_('Conversation'))
            if rec.apt_reasoning:
                parts.append(_('Reasoning'))
            if rec.apt_batch:
                parts.append(_('Batch'))
            if rec.apt_vision:
                parts.append(_('Vision'))
            if rec.apt_audio:
                parts.append(_('Audio'))
            if rec.apt_transcriptions:
                parts.append(_('Whisper'))
            if rec.apt_file:
                parts.append(_('File'))
            if rec.apt_decision:
                parts.append(_('Decision'))
            rec.apt_label = ', '.join(parts)

    def name_get(self):
        result = []
        for rec in self:
            label = rec.title or rec.name
            if rec.title and rec.title != rec.name:
                label = '%s (%s)' % (rec.title, rec.name)
            result.append((rec.id, label))
        return result

    def action_select_for_provider(self):
        """Use this row as the provider's selected model and close the grid.

        The catalogue context length becomes the provider window. Temperature
        support is probed the same way as changing the model on the form.
        """
        self.ensure_one()
        provider = self.provider_id
        if not provider:
            return {'type': 'ir.actions.act_window_close'}
        vals = {'model_id': self.id}
        if self.context_length:
            vals['context_window'] = self.context_length
        # Writing model_id runs the Audio gate (speech probe) in write().
        provider.write(vals)
        if provider._driver_chats():
            provider.temperature_support = provider._probe_temperature_support(
                target_model=self.name, timeout=8,
            )
        return {
            'type': 'ir.actions.act_window',
            'name': provider.name,
            'res_model': 'ai.provider',
            'res_id': provider.id,
            'view_mode': 'form',
            'target': 'current',
        }

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
      - 'openai':     OpenAIDriver     — OpenAI, Azure, any OpenAI-compatible gateway
                                        (incl. local LM Studio / Ollama in OpenAI mode)
      - 'openrouter': OpenRouterDriver — completions chat, own transcription body
      - 'anthropic':  AnthropicDriver  — Anthropic Claude (Messages API)

    Key fields:
      - endpoint:           Full POST URL (e.g. https://api.openai.com/v1/chat/completions)
      - api_key:            LLM gateway credential (admin-only in UI). **Not** the per-user
                            MCP token in ``ai.mcp.user`` — see ``docs/dos_credenciales_api.md``.
                            Server-side reads use ``_api_key_for_inference()`` (private, no RPC).
      - default_model:      Model identifier (e.g. 'gpt-4o', 'claude-sonnet-4-20250514')
      - temperature_support: 'yes'/'no'/'unknown' — auto-detected for Anthropic models
      - stt_support:        'chat'/'transcriptions'/'no'/'unknown' — probed speech verb
      - usage_support:      'yes'/'no'/'unknown' — probed from the completion body
      - model_ids:          Available models discovered via /v1/models endpoint
    """
    _name = 'ai.provider'
    _description = 'AI Provider'
    _rec_name = 'name'
    _pns_secret_fields = ('api_key',)

    name = fields.Char(string='Name', required=True)
    active = fields.Boolean(
        default=True,
        help='Archived providers stay in the database but are skipped by '
             'inference failovers and Chatboo. Prefer Archive over Delete.',
    )
    alias = fields.Char(
        string='Alias',
        help="Optional label shown in Chatboo's provider picker "
             "(e.g. 'Grok 4.5 (normal use)'). When empty, Chatboo shows "
             "the provider name. Does not change the fixed provider/model pair.",
    )
    protocol = fields.Selection([
        ('openai', 'OpenAI / OpenAI-Compatible'),
        ('openrouter', 'OpenRouter'),
        ('anthropic', 'Anthropic (Claude)'),
        ('systemone', 'SystemOne (Choice)'),
    ], string='Protocol', required=True, default='openai',
        help="Transport the driver speaks. "
             "OpenAI-compatible covers OpenAI, Azure and local gateways "
             "(LM Studio, Ollama in OpenAI mode). "
             "OpenRouter is its own driver on the completions URL; "
             "voice uses that driver's transcription. "
             "Anthropic uses the Messages API. "
             "SystemOne answers a closed Choice and does not chat. "
             "What a provider is used for is its ticks, not its protocol.")
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
    decision_min_confidence = fields.Float(
        string='Minimum confidence',
        default=0.7,
        help='Choice answers below this confidence are ignored. '
             'The word list result is kept.',
    )
    fit_conversation = fields.Boolean(
        string='Conversation',
        help='Empty ticks: text only. A tick admits that kind of input '
             'and no other. A photo or a clip never uses a text provider.',
    )
    fit_audio = fields.Boolean(string='Audio')
    fit_vision = fields.Boolean(string='Vision')
    fit_video = fields.Boolean(string='Video')
    fit_decision = fields.Boolean(
        string='Decision',
        help='Answers a closed Choice (yes or none, with a confidence). '
             'The decision agent chain only takes providers with this tick. '
             'The protocol must be able to choose.',
    )
    fit_chips_html = fields.Html(
        string='Fits',
        compute='_compute_fit_chips_html',
        sanitize=False,
        readonly=True,
        help='The ticks as chips, for the list. No tick reads Text.',
    )

    def _fit_flags(self):
        """The ticks keyed like ``provider_fit.FITS``."""
        from ..utils.provider_fit import FITS

        self.ensure_one()
        return {need: bool(self['fit_%s' % need]) for need in FITS}

    def _fits(self, need):
        """True when this provider may take a turn that needs ``need``."""
        from ..utils.provider_fit import provider_fits

        return provider_fits(self._fit_flags(), need)

    def _driver(self):
        from ..lib.llm.drivers import get_llm_driver

        self.ensure_one()
        return get_llm_driver(self.protocol)

    def _driver_chats(self):
        """False when this protocol only answers a closed Choice."""
        return bool(self._driver().chats)

    @api.depends('fit_conversation', 'fit_audio', 'fit_vision', 'fit_video',
                 'fit_decision', 'stt_support')
    def _compute_fit_chips_html(self):
        from odoo.tools import html_escape

        verbs = {
            'chat': _('chat audio'),
            'transcriptions': _('file transcriptions'),
        }
        for rec in self:
            chips = []
            if rec.fit_conversation:
                chips.append(('conversation', _('Conversation'), ''))
            if rec.fit_audio:
                chips.append((
                    'audio', _('Audio'), verbs.get(rec.stt_support or '', ''),
                ))
            if rec.fit_vision:
                chips.append(('vision', _('Vision'), ''))
            if rec.fit_video:
                chips.append(('video', _('Video'), ''))
            if rec.fit_decision:
                chips.append(('decision', _('Decision'), ''))
            if not chips:
                chips.append(('text', _('Text'), ''))
            rec.fit_chips_html = ''.join(
                '<span class="o_pns_fit_chip o_pns_fit_chip--%s"%s>%s</span>' % (
                    key,
                    (' title="%s"' % html_escape(tip)) if tip else '',
                    html_escape(label),
                )
                for key, label, tip in chips
            )

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
    stt_support = fields.Selection(
        [
            ('unknown', 'Unknown'),
            ('chat', 'Chat audio'),
            ('transcriptions', 'File transcriptions'),
            ('no', 'Not supported'),
        ],
        string='Speech API',
        default='unknown',
        readonly=True,
        copy=False,
        help="Which speech HTTP verb this model answers. Probed with a silent "
             "clip on Test Connection and when the model changes. Chat audio "
             "posts input_audio to this endpoint. File transcriptions posts a "
             "file to the sibling /audio/transcriptions URL. Not guessed from "
             "the model name.",
    )
    no_external_failover = fields.Boolean(
        string='No external failover',
        default=False,
        help="When this provider is reached, later providers in the chain "
             "are not tried.",
    )

    footmode = fields.Selection(
        selection=[
            ('foot-verbose', 'foot-verbose'),
            ('foot-laconic', 'foot-laconic'),
        ],
        string='Footmode',
        default='foot-verbose',
        help="Footer after agent-composed (compose-agent) tables.\n\n"
             "Values:\n"
             "• foot-verbose (default) — ask the model for a short warm closing "
             "line after the server-rendered table.\n"
             "• foot-laconic — skip that footer (small models often invent figures "
             "there) and, if the inference server honours it, disable internal "
             "thinking.\n\n"
             "Suspended when compose is compose-model (the model owns the whole "
             "bubble; there is no local table+footer path).\n"
             "Slash this turn only: /foot-verbose or /foot-laconic (does not write "
             "this field).\n"
             "Only applies to this provider, not to others in the failover chain.",
    )
    compose = fields.Selection(
        selection=[
            ('compose-agent', 'compose-agent'),
            ('compose-model', 'compose-model'),
        ],
        string='Compose',
        default='compose-agent',
        help="Who composes the bubble for this provider.\n\n"
             "Values:\n"
             "• compose-agent (default) — the agent paints HTML tables/charts from "
             "structured rows; after a server table the model writes at most a "
             "short footer (see footmode). Non-tabular answers (time, cards, "
             "greetings) are still composed by the model.\n"
             "• compose-model — the model owns the entire bubble (Markdown, HTML, "
             "native charts). footmode and showmode are suspended for that bubble.\n\n"
             "Slash this turn only: /compose-agent or /compose-model (does not "
             "write this field). A skill may set compose for its invocation.\n"
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

    @api.depends('protocol')
    def _compute_endpoint_setup_guide(self):
        openai_tpl = _(
            '<p><strong>URL template</strong> (shape only — replace host and port). '
            'Paste your resolved URL in the field below; Odoo does not modify it on save.</p>'
            '<p><code>https://&lt;url&gt;&lt;:port&gt;/api/v1/chat/completions</code></p>'
            '<p><em>Browse</em> derives <code>…/models</code> from this URL.</p>'
        )
        anthropic_tpl = _(
            '<p><strong>URL template</strong> (shape only — replace host and port). '
            'Paste your resolved URL in the field below; Odoo does not modify it on save.</p>'
            '<p><code>https://&lt;url&gt;&lt;:port&gt;/v1/messages</code></p>'
            '<p><em>Browse</em> derives <code>…/v1/models</code> from this URL.</p>'
        )
        systemone_tpl = _(
            '<p><strong>URL template</strong> (shape only — replace host and port). '
            'Paste your resolved URL in the field below; Odoo does not modify it on save.</p>'
            '<p><code>https://&lt;url&gt;&lt;:port&gt;/api/v1/systemone</code></p>'
            '<p>The call sends the selected model. '
            '<em>Browse</em> fills the selector from this gateway\'s catalogue. '
            'A chat model id is not valid on this URL.</p>'
        )
        for provider in self:
            if provider.protocol == 'anthropic':
                provider.endpoint_setup_guide = anthropic_tpl
            elif provider.protocol == 'systemone':
                provider.endpoint_setup_guide = systemone_tpl
            else:
                provider.endpoint_setup_guide = openai_tpl

    @api.constrains('temperature')
    def _check_temperature(self):
        for record in self:
            if record.temperature < 0.0 or record.temperature > 2.0:
                raise ValidationError("Temperature must be between 0.0 and 2.0 (recommended: 0.0-1.0)")

    def _model_known_fits(self):
        """What the gateway declared for the selected model, or {} if silent."""
        self.ensure_one()
        model = self.model_id
        if not model or not (model.modality_label or '').strip():
            return {}
        return {
            'conversation': bool(model.apt_conversation),
            'audio': bool(model.apt_audio),
            'vision': bool(model.apt_vision),
        }

    @api.constrains('model_id', 'fit_conversation', 'fit_audio', 'fit_vision')
    def _check_model_honours_ticks(self):
        """A tick is the anchor. The model under it must be one that fits."""
        from ..utils.provider_fit import fit_mismatches

        labels = {
            'conversation': _('Conversation'),
            'audio': _('Audio'),
            'vision': _('Vision'),
        }
        for rec in self:
            bad = fit_mismatches(rec._fit_flags(), rec._model_known_fits())
            if bad:
                raise ValidationError(_(
                    'Model %(model)s does not accept %(ticks)s '
                    '(catalogue: %(modality)s). Pick a model that does, '
                    'or clear the tick.'
                ) % {
                    'model': rec.model_id.name,
                    'ticks': ', '.join(labels[need] for need in bad),
                    'modality': rec.model_id.modality_label,
                })

    @api.constrains('fit_decision', 'decision_min_confidence')
    def _check_decision_confidence(self):
        for rec in self:
            if not rec.fit_decision:
                continue
            conf = rec.decision_min_confidence
            if conf is None or conf < 0.0 or conf > 1.0:
                raise ValidationError(_(
                    'Minimum confidence must be between 0 and 1.'
                ))


    @api.onchange('protocol')
    def _onchange_protocol_ticks(self):
        driver = self._driver()
        if not driver.chooses:
            self.fit_decision = False
        if not driver.chats:
            self.fit_conversation = False
            self.fit_audio = False
            self.fit_vision = False
            self.fit_video = False
            self.fit_decision = True

    def _choose(self, state, criteria, instructions, timeout=3):
        """Ask this provider a closed Choice. Raises ``DecisionCallError``."""
        from ..utils.decision_choice import DecisionCallError

        self.ensure_one()
        driver = self._driver()
        if not driver.chooses:
            raise DecisionCallError(
                'protocol %s does not answer a choice' % self.protocol
            )
        driver.initialize({
            'protocol': self.protocol,
            'endpoint': self.endpoint or '',
            'api_key': self._api_key_for_inference(),
            'model_name': (
                (self.model_id.name if self.model_id else '') or self.model_name or ''
            ),
        })
        return driver.choose(state, criteria, instructions, timeout=timeout)

    # Saving one of these with the Audio tick on sends the silent clip.
    _SPEECH_GATE_KEYS = ('model_id', 'fit_audio', 'endpoint', 'protocol', 'api_key')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if 'endpoint' in vals:
                vals['endpoint'] = self._sanitize_endpoint(vals.get('endpoint'))
            self._coerce_compose_vals(vals)
        records = super(AIProvider, self).create(vals_list)
        records._gate_audio_tick_on_save()
        return records

    def write(self, vals):
        if 'endpoint' in vals:
            vals['endpoint'] = self._sanitize_endpoint(vals.get('endpoint'))
        self._coerce_compose_vals(vals)
        res = super(AIProvider, self).write(vals)
        if any(key in vals for key in self._SPEECH_GATE_KEYS):
            self._gate_audio_tick_on_save()
        return res

    def _gate_audio_tick_on_save(self):
        """Audio tick + model that answers no speech verb = the save fails.

        The walkie keeps its failover so nobody is left without a transcript;
        this is where the admin learns the model was wrong, not in the log.
        Network or auth trouble leaves 'unknown' and lets the save through.
        """
        if self.env.context.get('pns_skip_speech_gate'):
            return
        for rec in self:
            if not rec.fit_audio or rec.protocol == 'anthropic':
                continue
            model = (rec.model_id.name if rec.model_id else '') or rec.model_name
            if not model or not rec.endpoint:
                continue
            speech = rec._probe_stt_support(target_model=model, timeout=8)
            if speech == 'no':
                raise ValidationError(_(
                    'Model %s answers neither chat audio nor file transcriptions. '
                    'Pick a speech model, or clear the Audio tick.'
                ) % model)
            if speech != 'unknown' and speech != rec.stt_support:
                rec.with_context(pns_skip_speech_gate=True).stt_support = speech

    @staticmethod
    def _coerce_compose_vals(vals):
        if not vals or 'compose' not in vals or not vals.get('compose'):
            return
        from ..utils.formatting_mode_policy import normalize_compose
        composed = normalize_compose(vals.get('compose'))
        if composed:
            vals['compose'] = composed

    @staticmethod
    def _sanitize_endpoint(endpoint):
        """Trim whitespace only; endpoint is stored exactly as configured."""
        return (endpoint or '').strip()


    def _get_models_json(self, url, headers):
        try:
            response = requests.get(url, headers=headers, timeout=60)
        except requests.exceptions.SSLError as e:
            error_str = str(e)
            if "wrong version number" in error_str:
                raise UserError(_(
                    "SSL Error: It seems you are using HTTPS on a non-SSL port "
                    "(likely port 11434). Please try using 'http://' instead of "
                    "'https://' in your Endpoint URL."
                ))
            raise UserError(_("SSL Error: %s") % safe_error_message(error_str))
        except requests.exceptions.RequestException as e:
            raise UserError(safe_error_message(
                _("Failed to fetch models: %s") % safe_error_message(str(e))
            ))
        if response.status_code != 200:
            response_text = safe_error_message(response.text)
            raise UserError(safe_error_message(
                _("Remote Error %s: %s") % (response.status_code, response_text)
            ))
        try:
            return response.json()
        except ValueError:
            raise UserError(_("Unknown response format: %s") % safe_error_message(
                response.text[:200]
            ))

    def _fetch_model_items(self):
        """GET /models once. The answer is a list, or a dict with ``data``."""
        self.ensure_one()
        from ..utils.model_catalogue import listing_url
        from ..lib.llm.drivers import get_llm_driver

        driver = get_llm_driver(self.protocol)
        url = listing_url(driver.models_url(self.endpoint))
        headers = driver.auth_headers(self.api_key or '')
        data = self._get_models_json(url, headers)
        items = data.get('data') if isinstance(data, dict) else data
        if not isinstance(items, list):
            keys = list(data.keys()) if isinstance(data, dict) else type(data).__name__
            raise UserError(safe_error_message(
                _("Unknown response format: %s") % safe_error_message(str(keys))
            ))
        return items

    def _refresh_model_catalogue(self):
        """GET the provider's list and upsert the catalogue. Returns the items.

        Browse and Copy call this first: the grid shown is the one just
        fetched, never a stale one. A provider that does not answer is an
        error, not an old list. One model back means one row.
        """
        self.ensure_one()
        try:
            items = self._fetch_model_items()
        except UserError:
            raise
        except Exception as e:
            error_str = safe_error_message(str(e))
            raise UserError(safe_error_message(
                _("Failed to fetch models: %s") % error_str
            ))
        models_list = []
        parsed = {}
        for item in items:
            if isinstance(item, dict) and item.get('id'):
                slug = str(item['id']).strip()
                if not slug:
                    continue
                models_list.append(slug)
                parsed[slug] = item
            elif isinstance(item, str) and item.strip():
                slug = item.strip()
                models_list.append(slug)
                parsed[slug] = {'id': slug}
        if not models_list:
            raise UserError(_("No models found in the response."))

        from ..utils.model_catalogue import catalogue_fields

        # Upsert by name. A short answer must not delete the rest of the
        # grid; Whisper/Audio are flags and search filters, not a new list.
        Model = self.env['ai.provider.model']
        listed = list(dict.fromkeys(models_list))  # de-dup, keep order
        existing_by_name = {m.name: m for m in self.available_model_ids}

        chooses = bool(self._driver().chooses)
        for m_name in listed:
            values = catalogue_fields(
                parsed.get(m_name) or {'id': m_name}, chooses=chooses,
            )
            if m_name not in existing_by_name:
                Model.create(dict(values, name=m_name, provider_id=self.id))
            else:
                existing_by_name[m_name].write(values)

        # If nothing selected and list exists, pick first
        if not self.model_id and self.available_model_ids:
            self.model_id = self.available_model_ids[0]
        return items

    def action_copy_model_catalogue(self):
        """Refresh the catalogue, then show the raw list to copy as JSON."""
        self.ensure_one()
        items = self._refresh_model_catalogue()
        payload = json.dumps(items, ensure_ascii=False, indent=2)
        wiz = self.env['ai.provider.catalogue.copy'].create({
            'catalogue_json': payload,
        })
        return {
            'type': 'ir.actions.act_window',
            'name': _('Model catalogue'),
            'res_model': 'ai.provider.catalogue.copy',
            'res_id': wiz.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def action_pick_model(self):
        """Refresh the catalogue, then open its grid for this provider."""
        self.ensure_one()
        self._refresh_model_catalogue()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Models'),
            'res_model': 'ai.provider.model',
            'view_mode': 'tree',
            'views': [
                (self.env.ref('pns_ai_mcp.view_ai_provider_model_tree').id, 'tree'),
                (self.env.ref('pns_ai_mcp.view_ai_provider_model_search').id, 'search'),
            ],
            'domain': [('provider_id', '=', self.id)],
            'context': {'search_default_group_maker': 1},
            'target': 'new',
        }

    @api.onchange('model_id')
    def _onchange_model_id(self):
        if not self._driver_chats():
            return
        self.temperature_support = self._probe_temperature_support(timeout=8)
        self.stt_support = self._probe_stt_support(timeout=8)

    @api.onchange('protocol', 'endpoint')
    def _onchange_reset_temperature_support(self):
        # Cambiar de endpoint/tipo invalida la capacidad cacheada del modelo.
        self.temperature_support = 'unknown'
        self.usage_support = 'unknown'
        self.stt_support = 'unknown'

    def _speech_driver(self, model):
        """Driver for a speech probe: this endpoint, key and model, verb unknown."""
        from ..lib.llm.drivers import get_llm_driver

        endpoint = self.endpoint or ''
        if endpoint and not endpoint.startswith('http'):
            endpoint = 'https://' + endpoint
        driver = get_llm_driver(self.protocol)
        driver.initialize({
            'protocol': self.protocol,
            'endpoint': endpoint,
            'api_key': self._api_key_for_inference() or '',
            'model_name': model,
            'stt_support': 'unknown',
        })
        return driver

    def _probe_stt_support(self, target_model=None, timeout=15):
        """Return chat/transcriptions/no/unknown from a silent clip.

        Best-effort: network or auth leaves 'unknown'. Not a model-name guess.
        """
        self.ensure_one()
        if self.protocol == 'anthropic':
            return 'no'
        model = target_model or (self.model_id.name if self.model_id else None) or self.model_name
        if not model or not self.endpoint:
            return 'unknown'
        try:
            driver = self._speech_driver(model)
            if hasattr(driver, 'probe_stt'):
                return driver.probe_stt(timeout=timeout)
        except Exception as exc:
            _logger.info("Speech probe inconclusive for %s: %s", self.name, exc)
        return 'unknown'

    def _speech_label(self, speech):
        return {
            'chat': _("chat audio"),
            'transcriptions': _("file transcriptions"),
            'no': _("not supported"),
        }.get(speech, speech)

    def _test_speech_connection(self, target_model):
        """Audio-only provider: the test is the speech probe, not a chat.

        A transcription model rejects chat/completions by design; asking it
        to say 'ok' proves nothing. The silent clip finds the verb the model
        answers and stores it. Auth or network errors surface as the error.
        """
        self.ensure_one()
        try:
            driver = self._speech_driver(target_model)
            if not hasattr(driver, 'probe_stt'):
                raise UserError(_(
                    'Protocol %s has no speech API.'
                ) % self.protocol)
            speech = driver.probe_stt(timeout=15)
        except UserError:
            raise
        except Exception as exc:
            _logger.error("AI Provider speech test failed: %s", exc, exc_info=True)
            raise UserError(safe_error_message(
                _("Connection Failed: %s") % safe_error_message(str(exc))
            ))
        self.stt_support = speech
        if speech == 'no':
            raise UserError(_(
                'Model %s answers neither chat audio nor file transcriptions. '
                'Pick a speech model, or clear the Audio tick.'
            ) % target_model)
        try:
            if 'ai.log' in self.env:
                self.env['ai.log'].create_log_entry(
                    user_id=self.env.user.id,
                    operation_type='read',
                    tool_name='Test Connection Web',
                    prompt_data={"model": target_model, "probe": "speech"},
                    result_data={"stt_support": speech},
                    result_summary="Manual Test Speech Connection",
                    request_type='system',
                    agent_llm=target_model,
                    source_channel='internal',
                )
        except Exception as exc:
            _logger.warning("Failed to log speech test connection: %s", exc)
        return mcp_ui.client_notification(
            _("Connection Successful"),
            _("Speech API: %s") % self._speech_label(speech),
            sticky=False,
        )

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

    def _test_decision_connection(self):
        """Probe a decision endpoint with a two-option Choice."""
        self.ensure_one()
        target_model = (self.model_id.name if self.model_id else '') or self.model_name
        if not target_model:
            raise UserError(_(
                'Browse the models and select a decision model.'
            ))
        from ..utils.decision_choice import DecisionCallError
        try:
            answer = self._choose(
                'ping',
                {'yes': 'A ping.', 'no': 'Not a ping.'},
                'Is this a ping?',
                timeout=8,
            )
        except DecisionCallError as exc:
            raise UserError(safe_error_message(
                _('Connection Failed: %s') % safe_error_message(str(exc))
            )) from exc
        usage = answer.get('usage') or {}
        if usage:
            self.usage_support = 'yes'
        try:
            if 'ai.log' in self.env:
                self.env['ai.log'].create_log_entry(
                    user_id=self.env.user.id,
                    operation_type='read',
                    tool_name='Test Connection Web',
                    prompt_data={'model': target_model, 'protocol': self.protocol},
                    result_data=answer,
                    result_summary='Manual Test Decision Connection',
                    request_type='system',
                    agent_llm=answer.get('model') or target_model,
                    source_channel='internal',
                    prompt_tokens=usage.get('input_tokens'),
                    completion_tokens=usage.get('output_tokens'),
                )
        except Exception as exc:
            _logger.warning('Failed to log decision test connection: %s', exc)
        conf = answer.get('confidence')
        conf_txt = ('%.2f' % float(conf)) if conf is not None else '—'
        return mcp_ui.client_notification(
            _('Connection Successful'),
            _('Decision model answered: %s (confidence %s)') % (
                answer.get('choice') or '—', conf_txt,
            ),
            sticky=False,
        )

    def test_connection(self):
        """Test connection to the AI provider using LiteLLM"""
        self.ensure_one()
        if not self._driver_chats():
            return self._test_decision_connection()

        target_model = self.model_id.name or self.model_name
        if not target_model:
            raise UserError(_("Please select a model or enter a Model Name."))
        if self.fit_audio and not self.fit_conversation:
            return self._test_speech_connection(target_model)

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

            speech = self._probe_stt_support(target_model=target_model)
            if speech != 'unknown':
                self.stt_support = speech
                extra += _("\nSpeech API: %s") % self._speech_label(speech)

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
        """Export all AI providers to a JSON file (asks for secrets first)."""
        ensure_ai_admin(self.env)
        if not self.with_context(active_test=False).search_count([]):
            return mcp_ui.open_json_export_empty_wizard(
                self.env,
                dialog_title=_('Export'),
                message=_('There are no providers to export.'),
            )
        return self.env['pns.export.secrets.wizard'].ask(
            self.browse(), '_pns_export_all_providers',
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
        return self.env['pns.export.secrets.wizard'].ask(
            self, '_pns_export_selected_providers',
        )

    def _pns_export_all_providers(self, include_secrets=False):
        ensure_ai_admin(self.env)
        # Include all providers, including archived (active=False).
        providers = self.with_context(active_test=False).search([])
        return providers._export_providers_file('ai_providers', include_secrets)

    def _pns_export_selected_providers(self, include_secrets=False):
        ensure_ai_admin(self.env)
        return self._export_providers_file('ai_providers_selected', include_secrets)

    def _export_providers_file(self, artifact, include_secrets):
        export_data = []
        for server in self:
            try:
                server_data = export_record_dict(
                    server, skip_fields={'id'}, include_secrets=include_secrets,
                )
            except Exception:
                server_data = {'name': server.name or '?'}
            # The model catalogue is fetched again from the provider.
            # The file only names the model this provider uses.
            try:
                server_data['selected_model'] = server.model_id.name if server.model_id else None
            except Exception:
                pass
            export_data.append(server_data)

        filename = mcp_ui.build_export_filename(
            self.env, artifact, 'json', secrets=include_secrets,
        )
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
            'res_model': 'ai.import.servers.wizard',
            'view_mode': 'form',
            'views': [[False, 'form']],
            'target': 'new',
        }

