# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""Resolves the provider, runs the agent turn, and failovers between LLMs."""
import json
import logging

from odoo import api, models, _
from odoo.exceptions import RedirectWarning, UserError

from ..utils.llm_usage import (
    advertise_cost,
    normalize_usage,
    usage_log_fields,
)

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


def _logged_tool_calls(tool_calls):
    """Each tool call the model asked for, as ``{name, arguments}``.

    Arguments come as the model wrote them, so a call the tool later
    rejects, repairs or never runs is still on the row.
    """
    calls = []
    for tc in tool_calls or ():
        fn = (tc.get('function') or {}) if isinstance(tc, dict) else {}
        args = fn.get('arguments')
        if isinstance(args, str):
            try:
                args = json.loads(args)
            except ValueError:
                pass
        calls.append({'name': fn.get('name') or '', 'arguments': args})
    return calls


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
            agent_code='pns_ai_admin',
            messages=[{'role': 'user', 'content': 'Hello!'}],
            tools=[...],  # optional MCP tool definitions
        )
        # response is an OpenAI-shaped dict:
        # {'choices': [{'message': {'role': 'assistant', 'content': '...'}}]}

    Failover flow::

        agent 'pns_ai_admin' → failovers sorted by priority
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

    def _bind_log_identity(self, agent_code=None, source_channel=None,
                           client_label=None):
        """Agent / door / label from the caller, else the env / request stamp."""
        ctx = self.env.context or {}
        try:
            from ..utils.mcp_logging import request_log_stamp
            stamp = request_log_stamp()
        except Exception:
            stamp = {}
        code = (
            agent_code
            or ctx.get('mcp_agent_code')
            or stamp.get('agent_code')
            or ''
        ).strip() or None
        door = (
            source_channel
            or ctx.get('mcp_source_channel')
            or stamp.get('source_channel')
            or 'internal'
        )
        label = (
            client_label
            or ctx.get('mcp_client_label')
            or stamp.get('client_label')
        )
        return code, door, label

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

        Skips inactive links and archived ``ai.provider`` records.

        Args:
            agent_code: Agent code string.

        Returns:
            ai.agent.provider recordset, sorted by (priority, id).
        """
        agent = self._get_agent(agent_code)
        # Failover links are admin-managed infrastructure; inference clients
        # (Chatboo, MCP) must resolve the chain without AI Administrator ACL.
        return agent.sudo().provider_ids.filtered(
            lambda link: (
                link.active
                and link.provider_id
                and link.provider_id.active
            ),
        ).sorted(key=lambda a: (a.priority, a.id))

    def get_providers_for_agent(self, agent_code, provider_id=None, need=None):
        """Return the ordered list of providers for an agent.

        Provider resolution cascade:
            1. If provider_id is given (UI) and it is on this agent's chain
               (after ticks and ``no_external_failover``) → use it alone
            2. If agent has explicit failovers → use them in priority order
            3. If the agent has no chain → use every active system provider
               (id order). Same rule for every inference agent.
            4. If no active providers exist → clear error message

        ``need`` (one of ``provider_fit.FITS``) drops providers that do not
        admit it. No ``need`` is a text turn. No ticks: text only. A photo,
        a clip, a video, a closed choice or a design needs its own tick. An
        explicit ``provider_id`` obeys the same ticks.

        A dialogue chain that admits nobody for that role is not a chain for
        it. The active providers that carry the tick are the door, in id
        order. No new failover link is created.

        Runtime use only: never ``Link.create`` the catalogue. Each inference
        agent owns its own failover chain. No agent borrows another agent's
        providers.
        """
        # 2. Explicit failovers on this agent
        failovers = self.get_failovers(agent_code)
        if failovers:
            found = failovers.mapped('provider_id')
        else:
            # 3–4. Active system providers; never Link.create the catalogue.
            found = self.env['ai.provider'].sudo().search(
                [('active', '=', True)], order='id',
            )
            if not found:
                action = self.env.ref(
                    'pns_ai_mcp.action_ai_provider', raise_if_not_found=False,
                )
                msg = _(
                    "No AI providers configured.\n\n"
                    "Create at least one provider with a valid API key "
                    "to start using the AI assistant."
                )
                if action:
                    raise RedirectWarning(msg, action.id, _('Set up a Provider'))
                raise UserError(msg)
            _logger.info(
                'AI: using %s system provider(s) for agent "%s" (no chain)',
                len(found), agent_code,
            )
        fitted = found.filtered(lambda provider: provider._fits(need))
        uncapped = self._without_capped(fitted)
        chain = self._without_external_after_local(uncapped)
        # Text stays on the dialogue chain. A role that chain does not cover
        # uses every active provider that admits it. No new link.
        if not chain and need and need != 'conversation' and failovers:
            found = self.env['ai.provider'].sudo().search(
                [('active', '=', True)], order='id',
            )
            fitted = found.filtered(lambda provider: provider._fits(need))
            uncapped = self._without_capped(fitted)
            chain = self._without_external_after_local(uncapped)
        chain = self._specialists_first(chain, need)
        # 1. A UI pick only narrows the chain; an id off the chain is ignored.
        if provider_id:
            try:
                picked = chain.filtered(lambda p: p.id == int(provider_id))
            except (TypeError, ValueError):
                picked = chain.browse()
            if picked:
                return picked
        if not chain and fitted and not uncapped:
            raise UserError(_(
                'No AI provider has available quota this month.'
            ))
        return chain

    @api.model
    def _specialists_first(self, providers, need):
        """A provider whose only job is this role goes first.

        One tick means a model chosen for that role alone: cheaper and better
        at it than a generalist that also holds the dialogue. Declared
        priority still orders the specialists among themselves, and the
        generalists among themselves.

        The ordinary text turn is left exactly as the human wrote it: there
        is no specialist in talking, and that chain is the one they tune.
        """
        from ..utils.provider_fit import is_specialist

        if not need or need == 'conversation' or len(providers) < 2:
            return providers
        declared = {provider.id: idx for idx, provider in enumerate(providers)}
        ranked = sorted(
            providers,
            key=lambda p: (
                0 if is_specialist(p._fit_flags(), need) else 1,
                declared[p.id],
            ),
        )
        return providers.browse([provider.id for provider in ranked])

    @api.model
    def _without_external_after_local(self, providers):
        """Drop providers that follow one with ``no_external_failover``."""
        kept = []
        stop = False
        for provider in providers:
            if stop:
                continue
            kept.append(provider.id)
            if provider.no_external_failover:
                stop = True
        return providers.browse(kept)

    @api.model
    def _without_capped(self, providers):
        """Skip keys that already hit this month's inference cap."""
        return providers.filtered(lambda provider: not provider.spend_cap_reached())

    def _choose(self, state, criteria, instructions, agent_code, timeout=3):
        """Ask that agent's decision chain a closed Choice, in priority order.

        Returns ``(provider, answer)``. The provider is the one that answered;
        ``answer`` is ``None`` when every provider failed (provider = the
        last one tried) or there is none (empty provider).
        """
        provider = self.env['ai.provider']
        if not agent_code:
            return provider, None
        try:
            chain = self.get_providers_for_agent(agent_code, need='decision')
        except (UserError, RedirectWarning):
            return provider, None
        for provider in chain:
            try:
                return provider, provider._choose(
                    state, criteria, instructions, timeout=timeout,
                )
            except Exception:
                _logger.info(
                    'AI engine: decision provider %s failed', provider.name,
                    exc_info=True,
                )
        return provider, None

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

        provider.assert_spend_cap()
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
            'temperature': provider.temperature_for_inference(),
            'send_temperature': provider.temperature_support != 'no',
            'stt_support': provider.stt_support or 'unknown',
            'context_window': provider.context_window or 32768,
            'extra_headers': extra_headers,
        })
        return _LoggedProviderDriver(
            driver, self, provider, agent_code=agent_code,
        )

    def log_role_without_provider(self, agent_code, need,
                                  user_id=None, turn=None, turn_step=None,
                                  source_channel=None, client_label=None):
        """Persist that no provider carries the tick this call needed.

        The user gets a soft notice inside the turn, but the person who can
        tick the box reads the log. The row lands on the same turn thread,
        so the Historial IA shows what was asked and what was missing.
        """
        if 'ai.log' not in self.env:
            return
        from .ai_log import CAPABILITY_SKIPPED
        Log = self.env['ai.log'].sudo()
        role = need or 'conversation'
        turn, turn_step = self._resolve_log_threading(turn, turn_step)
        agent_code, source_channel, client_label = self._bind_log_identity(
            agent_code, source_channel, client_label,
        )
        try:
            Log._create_log_entry(
                user_id=user_id or self.env.user.id,
                operation_type='read',
                tool_name=CAPABILITY_SKIPPED,
                request_type='LLM',
                result_summary='No active provider carries the %s tick' % role,
                prompt_data={'agent_code': agent_code, 'need': role},
                turn=turn,
                turn_step=turn_step,
                source_channel=source_channel,
                client_label=client_label,
            )
        except Exception as exc:
            _logger.warning(
                'AI engine: could not log the missing %s provider: %s',
                role, exc,
            )

    def log_provider_failover(self, agent_code, failed_provider, next_provider, error,
                              user_id=None, turn=None, turn_step=None,
                              source_channel=None, client_label=None):
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
        summary = 'ORCH failover: %s failed → %s' % (
            failed_provider.name, next_provider.name,
        )
        model_label = (
            next_provider.model_id.name if next_provider.model_id else None
        ) or next_provider.model_name or next_provider.name
        turn, turn_step = self._resolve_log_threading(
            turn, turn_step,
        )
        agent_code, source_channel, client_label = self._bind_log_identity(
            agent_code, source_channel, client_label,
        )
        try:
            Log._create_log_entry(
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
                turn=turn,
                turn_step=turn_step,
                source_channel=source_channel,
                client_label=client_label,
            )
        except Exception as exc:
            _logger.warning('AI engine: could not log failover: %s', exc)

    def _resolve_log_threading(self, turn=None, turn_step=None):
        """Fill turn/step from context or HTTP request when omitted.

        Chatboo turns store ``mcp_turn`` in the env context because
        the SSE request object can be unbound mid-stream; prefer that over
        inventing a new id (which would orphan recipe-cache rows).
        A context turn takes its step from the same counter as the engine,
        so a row written from a job thread (no request) still gets one.
        """
        if turn is not None:
            return turn, turn_step
        ctx = self.env.context or {}
        ctx_turn = ctx.get('mcp_turn')
        try:
            from odoo.http import request as http_request
            from ..utils.mcp_correlation import (
                claim_turn_step, ensure_turn, next_turn_step,
            )
            if ctx_turn:
                turn = ctx_turn
                try:
                    if http_request is not None:
                        if not getattr(http_request, 'mcp_turn', None):
                            http_request.mcp_turn = ctx_turn
                except Exception:
                    pass
                turn_step = claim_turn_step(
                    turn, seed=lambda: self._last_log_step(turn),
                )
            else:
                turn = ensure_turn(http_request)
                turn_step = next_turn_step(http_request, turn)
        except Exception:
            if ctx_turn:
                turn = ctx_turn
        return turn, turn_step

    def _last_log_step(self, turn):
        if not turn or 'ai.log' not in self.env:
            return 0
        last = self.env['ai.log'].sudo().search_read(
            [('turn', '=', turn)], ['turn_step'],
            order='turn_step desc', limit=1,
        )
        return (last[0]['turn_step'] or 0) if last else 0

    def _provider_model_label(self, provider, fallback=None):
        if not provider:
            return fallback
        return (
            provider.model_id.name if provider.model_id else None
        ) or provider.model_name or provider.name or fallback

    def log_provider_llm_request(
        self, provider, *, agent_code=None, round_n=None,
        num_messages=0, num_tools=0, model_label=None, prompt_data=None,
        result_summary=None, user_id=None, turn=None, turn_step=None,
        source_channel=None, client_label=None,
    ):
        """Universal ORCH → LLM request row (endpoint ``llm_orchestration``).

        Streaming (Chatboo) and headless callers use this — they do not write
        ``ai.log`` themselves for provider traffic.
        """
        if 'ai.log' not in self.env:
            return
        Log = self.env['ai.log'].sudo()
        agent_code, source_channel, client_label = self._bind_log_identity(
            agent_code, source_channel, client_label,
        )
        agent_code = agent_code or ''
        model_label = model_label or self._provider_model_label(provider)
        turn, turn_step = self._resolve_log_threading(
            turn, turn_step,
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
            result_summary = 'Round %s · %s messages · %s tools' % (
                round_n if round_n is not None else '—',
                num_messages,
                num_tools,
            )
        try:
            Log._create_log_entry(
                user_id=user_id or self.env.user.id,
                operation_type='read',
                tool_name='llm_orchestration',
                request_type='LLM',
                result_summary=result_summary,
                prompt_data=data,
                agent_llm=model_label,
                turn=turn,
                turn_step=turn_step,
                source_channel=source_channel,
                client_label=client_label,
            )
        except Exception as exc:
            _logger.warning('AI engine: could not log LLM request: %s', exc)

    def log_provider_llm_response(
        self, provider, *, agent_code=None, content_preview='',
        tool_names=None, model_label=None, prompt_tokens=None,
        completion_tokens=None, total_tokens=None, cost_usd=None,
        usage=None, result_summary=None,
        result_data=None, user_id=None, turn=None, turn_step=None,
        source_channel=None, client_label=None, tool_calls=None,
    ):
        """Universal LLM → ORCH response row (endpoint ``llm_response``).

        The row keeps the text and the tool calls (with their arguments)
        the model sent back.
        """
        if 'ai.log' not in self.env:
            return
        Log = self.env['ai.log'].sudo()
        agent_code, source_channel, client_label = self._bind_log_identity(
            agent_code, source_channel, client_label,
        )
        agent_code = agent_code or ''
        model_label = model_label or self._provider_model_label(provider)
        turn, turn_step = self._resolve_log_threading(
            turn, turn_step,
        )
        tools = [n for n in (tool_names or []) if n]
        preview = (content_preview or '').strip()
        if result_summary is None:
            if tools:
                result_summary = 'tool_calls: ' + ', '.join(tools)
            else:
                result_summary = (preview[:300] if preview else '(empty)')
        if result_data is None:
            calls = _logged_tool_calls(tool_calls)
            if preview or calls:
                result_data = {}
                if preview:
                    result_data['content'] = preview
                if calls:
                    result_data['tool_calls'] = calls
        try:
            Log._create_log_entry(
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
                result_data=result_data,
                agent_llm=model_label,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens,
                cost_usd=cost_usd,
                usage=usage,
                turn=turn,
                turn_step=turn_step,
                source_channel=source_channel,
                client_label=client_label,
            )
        except Exception as exc:
            _logger.warning('AI engine: could not log LLM response: %s', exc)

    def log_llm_inference(
        self,
        provider,
        usage,
        *,
        endpoint,
        source_channel=None,
        user_id=None,
        agent_code=None,
        client_label=None,
        log_mode='single',
        turn=None,
        turn_step=None,
        user_prompt=None,
        additional_info=None,
        content_preview='',
        result_summary=None,
        status='ok',
        remote_ip=None,
        prompt_data=None,
        result_data=None,
    ):
        """Universal gate: headless single row or ORCH↔LLM pair with tokens + USD.

        A single row keeps what the model was sent (``prompt_data``) and what
        it answered (``result_data``) when the caller has them.
        """
        if 'ai.log' not in self.env:
            return
        agent_code, source_channel, client_label = self._bind_log_identity(
            agent_code, source_channel, client_label,
        )
        piece = advertise_cost(normalize_usage(usage or {}))
        if log_mode == 'pair':
            self.log_provider_inference(
                provider,
                [{'role': 'user', 'content': user_prompt or ''}],
                {
                    'choices': [{
                        'message': {
                            'content': content_preview or '',
                        },
                    }],
                    'usage': piece,
                },
                agent_code=agent_code,
                source_channel=source_channel,
                client_label=client_label,
                user_id=user_id,
                turn=turn,
                turn_step=turn_step,
            )
            return
        ptok, ctok, ttok, cost_usd = usage_log_fields(piece)
        model_label = self._provider_model_label(provider)
        status = (status or 'ok').strip() or 'ok'
        # Tokens / USD already live in their columns. Result is the payload.
        if not result_summary:
            preview = (content_preview or '').strip()
            result_summary = (preview or status)[:5000]
        extra = dict(additional_info or {})
        if cost_usd is not None:
            extra['cost'] = cost_usd
        extra['status'] = status
        try:
            self.env['ai.log'].sudo()._create_log_entry(
                user_id=user_id or self.env.user.id,
                operation_type='read',
                tool_name=endpoint,
                request_type='llm',
                source_channel=source_channel,
                client_label=client_label,
                provider_id=provider.id if provider else False,
                agent_llm=model_label,
                user_prompt=user_prompt,
                prompt_data=prompt_data,
                result_data=result_data,
                result_summary=result_summary,
                additional_info=json.dumps(extra, ensure_ascii=False) if extra else None,
                prompt_tokens=ptok,
                completion_tokens=ctok,
                total_tokens=ttok,
                cost_usd=cost_usd,
                usage=piece,
                turn=turn,
                turn_step=turn_step,
                remote_ip=remote_ip,
            )
        except Exception as exc:
            _logger.warning(
                'AI engine: could not log inference (%s): %s',
                endpoint, exc,
            )

    def log_provider_inference(self, provider, messages, response, tools=None,
                               agent_code=None, source_channel=None,
                               client_label=None, user_id=None, turn=None,
                               turn_step=None):
        """Universal trail for a completed non-stream provider call.

        Writes the same ORCH→LLM / LLM→ORCH pair as streaming, so headless
        callers (OCR, ACL naming) and Chatboo share one logging gate.
        """
        n_msgs = len(messages or [])
        n_tools = len(tools or [])
        model_label = self._provider_model_label(provider)
        agent_code, source_channel, client_label = self._bind_log_identity(
            agent_code, source_channel, client_label,
        )
        self.log_provider_llm_request(
            provider,
            agent_code=agent_code,
            num_messages=n_msgs,
            num_tools=n_tools,
            model_label=model_label,
            prompt_data={'messages': messages},
            user_id=user_id,
            turn=turn,
            turn_step=turn_step,
            source_channel=source_channel,
            client_label=client_label,
        )
        # Second row needs its own step when caller passed an explicit first step.
        resp_step = (turn_step + 1) if turn_step is not None else None
        content = ''
        tool_names = []
        tool_calls = []
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
            tool_calls = message.get('tool_calls') or []
            for tc in tool_calls:
                name = (tc.get('function') or {}).get('name')
                if name:
                    tool_names.append(name)
            usage = (response or {}).get('usage') or {}
        except Exception:
            content = ''
        content = (content or '').strip()
        piece = advertise_cost(normalize_usage(usage))
        ptok, ctok, ttok, cost_usd = usage_log_fields(piece)
        self.log_provider_llm_response(
            provider,
            agent_code=agent_code,
            content_preview=content,
            tool_names=tool_names,
            tool_calls=tool_calls,
            model_label=model_label,
            prompt_tokens=ptok,
            completion_tokens=ctok,
            total_tokens=ttok,
            cost_usd=cost_usd,
            usage=piece,
            user_id=user_id,
            turn=turn,
            turn_step=resp_step,
            source_channel=source_channel,
            client_label=client_label,
        )

    @api.model
    def get_usage_display_context(self):
        """FX + display currency for usage chips in wizards and banners."""
        from ..utils.display_currency import get_display_currency
        fx = self.env['ai.fx.source'].get_usd_fx()
        return {
            'display_currency': get_display_currency(self.env),
            'fx': {
                'base': fx.get('base') or 'USD',
                'rates': fx.get('rates') or {},
                'as_of': fx.get('as_of') or '',
                'error': fx.get('error') or '',
            },
        }

    def chat_completion(self, agent_code, messages, tools=None, **kwargs):
        """Send a chat completion request, trying providers in priority order.

        Resolves the provider chain via ``get_providers_for_agent`` (explicit
        failovers, else every active system provider; no ``Link.create``).
        Then tries each
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
        need = kwargs.pop('need', None)
        if not need:
            need = 'vision' if kwargs.get('images') else 'conversation'
        # Ensures empty agent chains inherit configured providers (zero-friction).
        providers = self.get_providers_for_agent(agent_code, need=need)
        if provider_id:
            selected = self.env['ai.provider'].browse(provider_id).exists()
            if selected and selected.id in providers.ids:
                providers = selected + providers.filtered(
                    lambda rec: rec.id != selected.id,
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
