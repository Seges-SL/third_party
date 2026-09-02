# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""PNS AI MCP - Execution Engine. PATANEGRA Soft (https://patanegra.com).

Part of Patanegra Soft Suite (`pns_suite`), distributed via Patanegra Soft Hub.
Execution engine of the Patanegra Application Agent Protocol (PAAP): resolves
the provider, orchestrates the agent turn and handles failover between LLMs.
Licensed under the Apache License 2.0 - see LICENSE.
"""
import logging

from odoo import models, _
from odoo.exceptions import RedirectWarning, UserError

_logger = logging.getLogger(__name__)


class ProviderConnectionError(Exception):
    """Raised when a provider cannot complete an LLM request (failover candidate)."""


class _LoggedProviderDriver:
    """Proxy: every successful ``chat_completion`` writes LLM log rows via the engine.

    Logging is a property of using a provider through the execution engine —
    callers (ACL, OCR, Chatboo headless) do not opt in or out. Emits the same
    ``llm_orchestration`` + ``llm_response`` pair as Chatboo streaming.
    """

    def __init__(self, driver, engine, provider, agent_code=None):
        self._driver = driver
        self._engine = engine
        self._provider = provider
        self._agent_code = agent_code or ''

    def chat_completion(self, messages, tools=None, **kwargs):
        response = self._driver.chat_completion(
            messages=messages, tools=tools, **kwargs,
        )
        self._engine.log_provider_inference(
            self._provider,
            messages,
            response,
            tools=tools,
            agent_code=self._agent_code,
        )
        return response

    def __getattr__(self, name):
        return getattr(self._driver, name)


_CTX_OVERFLOW_MARKERS = (
    'context_length_exceeded',
    'exceed_context_size',
    'exceeds the available context',
    'n_prompt_tokens',
    'maximum context length',
    'context window',
)


def _is_context_overflow(error):
    """True si el error indica que el prompt excede la ventana de contexto.
    En ese caso el failover es inútil: cualquier proveedor con ventana similar
    fallará igual (y se pierden segundos probándolos). Mejor abortar con un
    mensaje claro orientado a la causa real (imágenes/base64 o historial)."""
    text = str(error or '').lower()
    return any(marker in text for marker in _CTX_OVERFLOW_MARKERS)


class AIExecutionEngine(models.AbstractModel):
    """AI routing engine — resolves agent codes to LLM providers with failover.

    This is an abstract model (no database table) that acts as the orchestrator
    between the application layer and LLM drivers. It implements the full
    provider chain with automatic failover.

    Usage::

        engine = self.env['ai.execution.engine']
        response = engine.chat_completion(
            agent_code='pns_ai_chatboo',
            messages=[{'role': 'user', 'content': 'Hello!'}],
            tools=[...],  # optional MCP tool definitions
        )
        # response is an OpenAI-shaped dict:
        # {'choices': [{'message': {'role': 'assistant', 'content': '...'}}]}

    Failover flow::

        agent 'pns_ai_chatboo' → failovers sorted by priority
          → try provider A (priority=1) → HTTP 500 → log failover
          → try provider B (priority=2) → success → return response

    Special case: context overflow errors (prompt too large) abort WITHOUT
    failover, since any provider with a similar context window will fail too.

    Key methods:
      - chat_completion(): Main entry point, tries providers in order
      - resolve_provider(): Returns the primary provider without calling it
      - _driver_for_provider(): Instantiates driver + universal inference log
      - log_provider_llm_request / log_provider_llm_response: universal LLM log rows
      - log_provider_inference(): headless pair (request+response) via same gate
      - log_provider_failover(): Persists failover events to MCP logs
    """
    _name = 'ai.execution.engine'
    _description = 'AI routing engine (agent → provider chain with failover)'

    def _get_agent(self, agent_code):
        """Resolve an agent code to an ai.agent record.

        Args:
            agent_code: String code (e.g. 'chat', 'code', 'summary').

        Returns:
            ai.agent recordset (single record).

        Raises:
            UserError: If no active agent with the given code exists.
        """
        agent = self.env['ai.agent'].search([
            ('code', '=', agent_code),
            ('active', '=', True),
        ], limit=1)
        if not agent:
            raise UserError(_(
                "AI agent '%s' is not configured. Create it under AI → Agents."
            ) % agent_code)
        return agent

    def get_failovers(self, agent_code):
        """Return active provider failovers for an agent, sorted by priority.

        Args:
            agent_code: Agent code string.

        Returns:
            ai.agent.provider recordset, sorted by (priority, id).
        """
        agent = self._get_agent(agent_code)
        # Failover links are admin-managed infrastructure; inference clients
        # (Chatboo, MCP) must resolve the chain without AI Administrator ACL.
        return agent.sudo().provider_ids.filtered('active').sorted(
            key=lambda a: (a.priority, a.id),
        )

    def get_providers_for_agent(self, agent_code, provider_id=None):
        """Return the ordered list of providers for an agent.

        Provider resolution cascade:
            1. If provider_id is given (user selected in UI) → use it
            2. If agent has explicit failovers → use them in priority order
            3. If there's exactly ONE active provider → use it implicitly
            4. If no providers exist → clear error message
            5. If multiple providers but none assigned → error

        Args:
            agent_code: Agent code string.
            provider_id: Optional int. Explicit provider ID from UI selection.

        Returns:
            ai.provider recordset in priority order.

        Raises:
            UserError: If no provider can be resolved.
        """
        # 1. UI-driven provider selection (ai.provider has no `active` field;
        #    `.exists()` already validates the record).
        if provider_id:
            provider = self.env['ai.provider'].browse(provider_id).exists()
            if provider:
                return provider

        # 2. Explicit failovers
        failovers = self.get_failovers(agent_code)
        if failovers:
            return failovers.mapped('provider_id')

        # 3. Auto-assign: all active providers, auto-create failovers
        all_providers = self.env['ai.provider'].search(
            [], order='id',
        )
        if not all_providers:
            action = self.env.ref('pns_ai_mcp.action_ai_provider', raise_if_not_found=False)
            msg = _(
                "No AI providers configured.\n\n"
                "Create at least one provider with a valid API key "
                "to start using the AI assistant."
            )
            if action:
                raise RedirectWarning(msg, action.id, _('Set up a Provider'))
            raise UserError(msg)

        # Single provider → use directly (no failover record needed)
        if len(all_providers) == 1:
            _logger.info(
                'AI: auto-using sole provider "%s" for agent "%s"',
                all_providers.name, agent_code,
            )
            return all_providers

        # Multiple providers → auto-create failover chain for zero-friction
        agent = self.env['ai.agent'].search(
            [('code', '=', agent_code)], limit=1,
        )
        if agent:
            Link = self.env['ai.agent.provider']
            for idx, provider in enumerate(all_providers):
                Link.sudo().create({
                    'agent_id': agent.id,
                    'provider_id': provider.id,
                    'priority': idx,
                })
            _logger.info(
                'AI: auto-created failover chain for agent "%s" '
                'with %d providers',
                agent_code, len(all_providers),
            )
            return all_providers
        # Fallback: no agent record, just use all in sequence order
        return all_providers

    def _driver_for_provider(self, provider, agent_code=None):
        """Instantiate and configure an LLM driver for a specific provider.

        Creates a driver instance (OpenAIDriver, AnthropicDriver, etc.),
        resolves the model name, endpoint, API key, and any extra headers
        (e.g. X-Mcp-Token for authenticated MCP users), then calls
        driver.initialize() with the full config dict.

        The returned object always logs successful ``chat_completion`` calls
        to ``ai.log`` (universal gate — not an agent/caller choice).

        Args:
            provider: ai.provider record.
            agent_code: Optional agent code for the log row metadata.

        Returns:
            Driver proxy ready for chat_completion() (logs on success).

        Raises:
            UserError: If the provider has no model configured.
        """
        from ..lib.llm.drivers import get_llm_driver

        driver = get_llm_driver(provider.protocol)
        model_name = (provider.model_id.name if provider.model_id else None) or provider.model_name
        if not model_name:
            raise UserError(_('Provider "%s" has no model configured.') % provider.name)

        endpoint = provider.endpoint or ''
        if endpoint and not endpoint.startswith('http'):
            endpoint = 'https://' + endpoint

        # Las tools se ejecutan in-process (ver AgentEngine); la LLM no reentra
        # en /mcp, así que no se propaga X-Mcp-Token. La API key solo se guarda
        # hasheada y no es recuperable para reenviarla.
        extra_headers = {}

        driver.initialize({
            'protocol': provider.protocol,
            'endpoint': endpoint,
            'api_key': provider._api_key_for_inference(),
            'model_name': model_name,
            'temperature': provider.temperature or 0.7,
            'send_temperature': provider.temperature_support != 'no',
            'context_window': provider.context_window or 32768,
            'extra_headers': extra_headers,
        })
        return _LoggedProviderDriver(
            driver, self, provider, agent_code=agent_code,
        )

    def log_provider_failover(self, agent_code, failed_provider, next_provider, error,
                              user_id=None, correlation_id=None, step_seq=None,
                              source_channel='internal'):
        """Persist intra-agent provider failover to MCP logs.

        El llamante (motor de chat) puede pasar el ``user_id`` real del turno y
        su ``correlation_id``/``step_seq`` para que el failover caiga en el mismo
        hilo del histórico y con el usuario humano (no Administrator). Si no se
        pasan, se intenta resolver desde el request (compatibilidad).
        """
        if 'ai.log' not in self.env:
            return
        Log = self.env['ai.log'].sudo()
        err_text = str(error or '')[:500]
        summary = _('ORCH failover: %s failed → %s') % (
            failed_provider.name, next_provider.name,
        )
        model_label = (
            next_provider.model_id.name if next_provider.model_id else None
        ) or next_provider.model_name or next_provider.name
        correlation_id, step_seq = self._resolve_log_threading(
            correlation_id, step_seq,
        )
        try:
            Log.create_log_entry(
                user_id=user_id or self.env.user.id,
                operation_type='read',
                tool_name='provider_failover',
                request_type='LLM',
                result_summary=summary,
                prompt_data={
                    'agent_code': agent_code,
                    'failed_provider': failed_provider.name,
                    'failed_provider_id': failed_provider.id,
                    'next_provider': next_provider.name,
                    'next_provider_id': next_provider.id,
                    'error': err_text,
                },
                agent_llm=model_label,
                correlation_id=correlation_id,
                step_seq=step_seq,
                source_channel=source_channel or 'internal',
            )
        except Exception as exc:
            _logger.warning('AI engine: could not log failover: %s', exc)

    def _resolve_log_threading(self, correlation_id=None, step_seq=None):
        """Fill correlation/step from context or HTTP request when omitted.

        Chatboo turns store ``mcp_correlation_id`` in the env context because
        the SSE request object can be unbound mid-stream; prefer that over
        inventing a new id (which would orphan recipe-cache rows).
        """
        if correlation_id is not None:
            return correlation_id, step_seq
        ctx = self.env.context or {}
        ctx_corr = ctx.get('mcp_correlation_id')
        try:
            from odoo.http import request as http_request
            from ..utils.mcp_correlation import (
                ensure_turn_correlation, next_step_seq,
            )
            if ctx_corr:
                correlation_id = ctx_corr
                try:
                    if http_request is not None:
                        if not getattr(http_request, 'mcp_corr_id', None):
                            http_request.mcp_corr_id = ctx_corr
                        if not getattr(http_request, 'mcp_step_counter', None):
                            http_request.mcp_step_counter = {}
                        step_seq = next_step_seq(http_request, correlation_id)
                except Exception:
                    pass
            else:
                correlation_id = ensure_turn_correlation(http_request)
                step_seq = next_step_seq(http_request, correlation_id)
        except Exception:
            if ctx_corr:
                correlation_id = ctx_corr
        return correlation_id, step_seq

    def _provider_model_label(self, provider, fallback=None):
        if not provider:
            return fallback
        return (
            provider.model_id.name if provider.model_id else None
        ) or provider.model_name or provider.name or fallback

    def log_provider_llm_request(
        self, provider, *, agent_code=None, round_n=None,
        num_messages=0, num_tools=0, model_label=None, prompt_data=None,
        result_summary=None, user_id=None, correlation_id=None, step_seq=None,
        source_channel='internal',
    ):
        """Universal ORCH → LLM request row (endpoint ``llm_orchestration``).

        Streaming (Chatboo) and headless callers use this — they do not write
        ``ai.log`` themselves for provider traffic.
        """
        if 'ai.log' not in self.env:
            return
        Log = self.env['ai.log'].sudo()
        agent_code = agent_code or ''
        model_label = model_label or self._provider_model_label(provider)
        correlation_id, step_seq = self._resolve_log_threading(
            correlation_id, step_seq,
        )
        data = {
            'agent_code': agent_code,
            'provider': provider.name if provider else None,
            'provider_id': provider.id if provider else None,
            'model': model_label,
            'round': round_n,
            'num_messages': num_messages,
            'num_tools': num_tools,
        }
        if prompt_data:
            data.update(prompt_data)
        if result_summary is None:
            result_summary = _('Round %(t)s · %(m)s messages · %(k)s tools') % {
                't': round_n if round_n is not None else '—',
                'm': num_messages,
                'k': num_tools,
            }
        try:
            Log.create_log_entry(
                user_id=user_id or self.env.user.id,
                operation_type='read',
                tool_name='llm_orchestration',
                request_type='LLM',
                result_summary=result_summary,
                prompt_data=data,
                agent_llm=model_label,
                correlation_id=correlation_id,
                step_seq=step_seq,
                source_channel=source_channel or 'internal',
            )
        except Exception as exc:
            _logger.warning('AI engine: could not log LLM request: %s', exc)

    def log_provider_llm_response(
        self, provider, *, agent_code=None, content_preview='',
        tool_names=None, model_label=None, prompt_tokens=None,
        completion_tokens=None, total_tokens=None, result_summary=None,
        result_data=None, user_id=None, correlation_id=None, step_seq=None,
        source_channel='internal',
    ):
        """Universal LLM → ORCH response row (endpoint ``llm_response``)."""
        if 'ai.log' not in self.env:
            return
        Log = self.env['ai.log'].sudo()
        agent_code = agent_code or ''
        model_label = model_label or self._provider_model_label(provider)
        correlation_id, step_seq = self._resolve_log_threading(
            correlation_id, step_seq,
        )
        tools = [n for n in (tool_names or []) if n]
        preview = (content_preview or '').strip()
        if result_summary is None:
            if tools:
                result_summary = 'tool_calls: ' + ', '.join(tools)
            else:
                result_summary = (preview[:300] if preview else '(sin contenido)')
        try:
            Log.create_log_entry(
                user_id=user_id or self.env.user.id,
                operation_type='read',
                tool_name='llm_response',
                request_type='LLM',
                result_summary=result_summary,
                prompt_data={
                    'agent_code': agent_code,
                    'provider': provider.name if provider else None,
                    'provider_id': provider.id if provider else None,
                },
                result_data=result_data if result_data is not None else (
                    {'content': preview[:400]} if preview else None
                ),
                agent_llm=model_label,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens,
                correlation_id=correlation_id,
                step_seq=step_seq,
                source_channel=source_channel or 'internal',
            )
        except Exception as exc:
            _logger.warning('AI engine: could not log LLM response: %s', exc)

    def log_provider_inference(self, provider, messages, response, tools=None,
                               agent_code=None, source_channel='internal',
                               user_id=None, correlation_id=None, step_seq=None):
        """Universal trail for a completed non-stream provider call.

        Writes the same ORCH→LLM / LLM→ORCH pair as streaming, so headless
        callers (OCR, ACL naming) and Chatboo share one logging gate.
        """
        n_msgs = len(messages or [])
        n_tools = len(tools or [])
        model_label = self._provider_model_label(provider)
        self.log_provider_llm_request(
            provider,
            agent_code=agent_code,
            num_messages=n_msgs,
            num_tools=n_tools,
            model_label=model_label,
            prompt_data={'messages': messages},
            user_id=user_id,
            correlation_id=correlation_id,
            step_seq=step_seq,
            source_channel=source_channel,
        )
        # Second row needs its own step when caller passed an explicit first step.
        resp_step = (step_seq + 1) if step_seq is not None else None
        content = ''
        tool_names = []
        usage = {}
        try:
            message = (
                (response or {}).get('choices', [{}])[0]
                .get('message', {}) or {}
            )
            content = message.get('content') or ''
            if isinstance(content, list):
                content = ''.join(
                    part.get('text', '')
                    for part in content
                    if isinstance(part, dict)
                )
            for tc in (message.get('tool_calls') or []):
                name = (tc.get('function') or {}).get('name')
                if name:
                    tool_names.append(name)
            usage = (response or {}).get('usage') or {}
        except Exception:
            content = ''
        content = (content or '').strip()
        ptok = usage.get('prompt_tokens')
        ctok = usage.get('completion_tokens')
        ttok = usage.get('total_tokens') or (
            ((ptok or 0) + (ctok or 0)) or None
        )
        self.log_provider_llm_response(
            provider,
            agent_code=agent_code,
            content_preview=content,
            tool_names=tool_names,
            model_label=model_label,
            prompt_tokens=ptok,
            completion_tokens=ctok,
            total_tokens=ttok,
            user_id=user_id,
            correlation_id=correlation_id,
            step_seq=resp_step,
            source_channel=source_channel,
        )

    def chat_completion(self, agent_code, messages, tools=None, **kwargs):
        """Send a chat completion request, trying providers in priority order.

        Resolves the provider chain via ``get_providers_for_agent`` (auto-wires
        all providers when the agent has no explicit failovers yet — sole
        provider or auto-created ``ai.agent.provider`` rows). Then tries each
        provider until one succeeds. Successful calls are logged by the
        driver proxy (universal — not opt-in per caller).

        Context overflow errors (prompt too large) abort immediately without
        failover.

        :param str agent_code: Agent identifier (e.g. 'chat', 'code').
            Resolved via ai.agent.resolve_inference_agent_code().
        :param list messages: OpenAI-format messages [{role, content}, ...]
        :param list tools: Optional MCP tool definitions
        :param kwargs: Extra args passed to driver.chat_completion().
            ``provider_id`` (optional) forces a single provider from the UI.
        :returns: OpenAI-shaped response dict
        :raises UserError: If all providers fail or context overflow detected
        """
        agent_code = self.env['ai.agent'].resolve_inference_agent_code(agent_code)
        provider_id = kwargs.pop('provider_id', None)
        # Ensures empty agent chains inherit configured providers (zero-friction).
        providers = self.get_providers_for_agent(
            agent_code, provider_id=provider_id,
        )
        last_error = None
        failed_provider = None
        for idx, provider in enumerate(providers):
            if idx > 0 and failed_provider:
                self.log_provider_failover(
                    agent_code, failed_provider, provider, last_error,
                )
            try:
                driver = self._driver_for_provider(
                    provider, agent_code=agent_code,
                )
                _logger.info(
                    'AI engine: agent=%s priority=%s provider=%s',
                    agent_code, idx, provider.name,
                )
                return driver.chat_completion(
                    messages=messages, tools=tools, **kwargs,
                )
            except Exception as exc:
                last_error = exc
                failed_provider = provider
                if _is_context_overflow(exc):
                    _logger.warning(
                        'AI engine: agent=%s provider=%s rechazó por desbordamiento '
                        'de contexto; se aborta SIN failover (inútil).',
                        agent_code, provider.name,
                    )
                    raise UserError(_(
                        'The request exceeds the context window of agent "%s". This '
                        'usually means images/base64 or a very large history were '
                        'included. Return image URLs (/web/image/<model>/<id>/image_128) '
                        'or metadata instead of binary data, or narrow the query. '
                        '(Provider %s)'
                    ) % (agent_code, provider.name)) from exc
                _logger.warning(
                    'AI engine failover: agent=%s provider=%s failed: %s',
                    agent_code, provider.name, exc,
                )
        raise UserError(_(
            'All providers failed for agent "%s". Last error: %s'
        ) % (agent_code, last_error))

    def resolve_provider(self, agent_code):
        """Return the first provider in the chain (for callers that resolve explicitly)."""
        agent_code = self.env['ai.agent'].resolve_inference_agent_code(agent_code)
        providers = self.get_providers_for_agent(agent_code)
        return providers[0]
