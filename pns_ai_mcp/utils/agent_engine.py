# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""Native agentic engine for Odoo (ReAct loop + tool calling + streaming)."""

import json
import logging
import os
import time
from odoo import SUPERUSER_ID, _
from odoo.exceptions import RedirectWarning, UserError
from .mcp_correlation import claim_turn_step, new_turn_id, open_turn_steps
from .llm_usage import (
    add_usage,
    advertise_cost,
    bind_turn_side_usage,
    bound_turn_side_usage,
    normalize_usage,
    note_turn_side_usage,
    reset_turn_side_usage,
    usage_has_tokens,
    usage_since,
)
from .agent_stream_text import (
    NO_TOOL_FINAL_NUDGE,
    pretool_progress_status,
    recover_displaced_turn_body,
    should_block_no_tool_as_final,
    should_block_progress_as_final,
    strip_think_blocks,
    user_visible_round_text,
)
from .engine_discovery import DiscoveryMixin
from .engine_skills import SkillsMixin
from .engine_presentation import PresentationMixin
from .engine_tool_loop import ToolLoopMixin
from .engine_turn_records import TurnRecordsMixin
from .engine_tool_run import ToolRunMixin
from .engine_direct_delivery import DirectDeliveryMixin
from .engine_turn_close import TurnCloseMixin
from .engine_turn_messages import TurnMessagesMixin

_logger = logging.getLogger(__name__)


class TurnTimeExceeded(Exception):
    """The turn used its wall clock. The provider answered; do not fail over."""

# Límites del bucle ReAct en Chatboo (evita colgues de 15–20 min con OVH/Ollama lentos)
LLM_STREAM_READ_TIMEOUT = 45       # segundos sin datos entre chunks SSE
LLM_ROUND_WALL_TIMEOUT = 120       # segundos máximos por ronda LLM
LLM_AGENT_WALL_TIMEOUT = 300         # segundos máximos para toda la petición del usuario
# Hybrid param JSON only. 512 cut a live reply mid-stream (FWLD).
HYBRID_PARAM_MAX_TOKENS = 4096

# Tope POR DEFECTO (en BYTES serializados) del dataset que se cachea para
# reutilización (Nivel 2). Configurable en caliente por parámetro de sistema
# 'pns_ai_mcp.dataset_cache_max_bytes'; 0 (o negativo) = SIN límite.
# No es un tope de ALMACENAMIENTO (Postgres aguanta de sobra) sino de COSTE POR
# TURNO: el blob se serializa/deserializa y se copia en RAM en cada turno del
# worker, así que un dataset gigante penaliza toda la sesión. El nº de filas no
# se limita (es engañoso: 1000 filas anchas pesan más que 100000 estrechas); lo
# que manda es el tamaño real. Si se supera, NO se cachea (se cae a reutilizar
# solo el código, Nivel 1). Nunca viaja al LLM.
AGENT_DATASET_CACHE_MAX_BYTES = 8 * 1024 * 1024  # 8 MB serializados


# Compat: nombres privados usados por tests / callers antiguos.
_strip_think_blocks = strip_think_blocks
_user_visible_round_text = user_visible_round_text
_pretool_progress_status = pretool_progress_status
_should_block_progress_as_final = should_block_progress_as_final
_should_block_no_tool_as_final = should_block_no_tool_as_final


def _audit_llm_json_result(provider, result):
    """Record usage for ``inference_audit`` when a short LLM call completes."""
    try:
        from .inference_audit import record_inference_usage
        record_inference_usage(
            provider,
            (result or {}).get('usage'),
            content_preview=(result or {}).get('content') or '',
        )
    except Exception:
        _logger.debug('llm_json_completion: inference audit hook failed', exc_info=True)
    return result


def _completion_text(body):
    """Assistant text from a driver response."""
    choices = (body or {}).get('choices') or []
    if not choices:
        return ''
    message = choices[0].get('message') or {}
    content = message.get('content')
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return ''.join(
            part.get('text', '') for part in content
            if isinstance(part, dict)
        )
    return ''


def llm_json_completion_result(provider, system_prompt, user_prompt,
                               max_tokens=512, timeout=None, json_mode=False,
                               images=None, disable_thinking=False):
    """Short non-streaming LLM call; ``{content, usage}`` (empty on error).

    Shared short call (no tools, no streaming): skill ``param_schema``
    holes, Detection trigger synonyms, and a photo read. Images go to the
    driver; this function does not build a provider body.
    """
    try:
        provider.assert_spend_cap()
        from ..lib.llm.drivers import get_llm_driver
        endpoint = provider.endpoint or ''
        if endpoint and not endpoint.startswith('http'):
            endpoint = 'https://' + endpoint
        model_name = (
            (provider.model_id.name if provider.model_id else None)
            or provider.model_name or ''
        )
        if not model_name:
            return {'content': '', 'usage': {}, 'error': 'no model'}
        driver = get_llm_driver(provider.protocol)
        driver.initialize({
            'protocol': provider.protocol,
            'endpoint': endpoint,
            'api_key': provider._api_key_for_inference(),
            'model_name': model_name,
            'temperature': 0,
            'send_temperature': (
                getattr(provider, 'temperature_support', None) != 'no'
            ),
        })
        messages = [
            {'role': 'system', 'content': system_prompt or ''},
            {'role': 'user', 'content': user_prompt or ''},
        ]
        read_timeout = timeout or LLM_STREAM_READ_TIMEOUT

        def _once(use_json):
            return driver.chat_completion(
                messages,
                temperature=0,
                max_tokens=max_tokens,
                timeout=read_timeout,
                json_mode=use_json,
                images=images,
                disable_thinking=bool(disable_thinking),
            )

        try:
            body = _once(bool(json_mode))
        except Exception as exc:
            if not json_mode:
                raise
            _logger.debug('llm_json_completion json mode failed: %s', exc)
            body = _once(False)
        return _audit_llm_json_result(provider, {
            'content': _completion_text(body),
            'usage': normalize_usage((body or {}).get('usage') or {}),
        })
    except Exception as exc:
        _logger.debug('llm_json_completion failed: %s', exc)
        return {'content': '', 'usage': {}, 'error': str(exc)[:300]}


def llm_json_completion(provider, system_prompt, user_prompt,
                        max_tokens=512, timeout=None):
    """Short non-streaming LLM call; returns response text ('' on error)."""
    result = llm_json_completion_result(
        provider, system_prompt, user_prompt,
        max_tokens=max_tokens, timeout=timeout,
    )
    return (result or {}).get('content') or ''


def _is_llm_json_context_overflow(error):
    """True when the prompt exceeds this provider's context window."""
    text = str(error or '').lower()
    markers = (
        'context_length_exceeded',
        'exceed_context_size',
        'exceeds the available context',
        'n_prompt_tokens',
        'maximum context length',
        'context window',
        'ctx_size',
        'context_size',
        'prompt is too long',
        'prompt too long',
    )
    return any(marker in text for marker in markers)


def resolve_providers_for_consumer(
        env, consumer_key='admin', agent_code=None, need=None):
    """Ordered ``ai.provider`` recordset for an inference feature key.

    ``need`` is a ``provider_fit`` role (conversation, decision, …).
    None is a text turn.
    """
    code = env['ai.agent'].resolve_inference_agent_code(
        agent_code, consumer_key=consumer_key,
    )
    return env['ai.execution.engine'].get_providers_for_agent(code, need=need)


def llm_json_completion_for_agent(
        env, system_prompt, user_prompt,
        consumer_key='admin', agent_code=None,
        max_tokens=512, timeout=None, json_mode=False,
        failover_on_overflow=False, max_providers=None, images=None,
        need=None, disable_thinking=False):
    """Short JSON LLM call with the agent's provider failover cascade.

    Uses ``resolve_inference_agent_code`` + ``get_providers_for_agent``. On a
    retriable provider error, logs failover and tries the next provider.
    Context-window overflow aborts without failover by default (same rule as
    ``ai.execution.engine.chat_completion``). Pass
    ``failover_on_overflow=True`` for large one-shot jobs (e.g. OpenAPI
    generation) so a small local model does not stop the cascade.
    ``max_providers`` caps how many failovers are attempted (keeps the
    HTTP request under typical reverse-proxy timeouts).
    """
    code = env['ai.agent'].resolve_inference_agent_code(
        agent_code, consumer_key=consumer_key,
    )
    engine = env['ai.execution.engine']
    if not need:
        need = 'vision' if images else 'conversation'
    try:
        providers = engine.get_providers_for_agent(code, need=need)
    except UserError as exc:
        from .error_ux import exception_user_text
        return {
            'content': '',
            'usage': {},
            'error': exception_user_text(exc) or str(exc),
            'provider': env['ai.provider'],
        }
    if not providers:
        # The caller turns this into a soft notice; the admin needs the row.
        try:
            engine.log_role_without_provider(code, need)
        except Exception:
            _logger.debug(
                'llm_json_completion_for_agent: missing-role log failed',
                exc_info=True,
            )
        return {
            'content': '',
            'usage': {},
            'error': 'No AI provider is configured for agent %s' % code,
            'provider': env['ai.provider'],
        }
    if max_providers is not None:
        try:
            cap = max(1, int(max_providers))
        except (TypeError, ValueError):
            cap = 1
        providers = providers[:cap]

    last_error = None
    failed_provider = None
    last_result = {'content': '', 'usage': {}, 'error': 'no providers tried'}
    for idx, provider in enumerate(providers):
        if idx > 0 and failed_provider:
            try:
                engine.log_provider_failover(
                    code, failed_provider, provider, last_error,
                    source_channel='internal',
                )
            except Exception:
                _logger.debug(
                    'llm_json_completion_for_agent: failover log failed',
                    exc_info=True,
                )
        result = llm_json_completion_result(
            provider, system_prompt, user_prompt,
            max_tokens=max_tokens, timeout=timeout, json_mode=json_mode,
            images=images, disable_thinking=disable_thinking,
        )
        err = ((result or {}).get('error') or '').strip()
        last_result = dict(result or {})
        last_result['provider'] = provider
        if not err:
            return last_result
        last_error = err
        if _is_llm_json_context_overflow(last_error):
            if not failover_on_overflow:
                _logger.warning(
                    'llm_json_completion_for_agent: agent=%s provider=%s '
                    'context overflow; no failover',
                    code, provider.name,
                )
                return last_result
            _logger.warning(
                'llm_json_completion_for_agent: agent=%s provider=%s '
                'context overflow; trying next provider',
                code, provider.name,
            )
        failed_provider = provider
        _logger.warning(
            'llm_json_completion_for_agent: agent=%s provider=%s failed: %s',
            code, provider.name, last_error,
        )
    return last_result


def llm_completion_for_agent(
        env, system_prompt, user_prompt,
        consumer_key='admin', agent_code=None,
        max_tokens=512, timeout=None,
        failover_on_overflow=False, max_providers=None, images=None,
        need=None, disable_thinking=False):
    """Short completion on the agent's providers. No tools, no JSON mode.

    ``agent_code`` only picks the provider chain. A photo is extra parts
    on the user message. The caller opens ``inference_audit`` when the
    shot must leave a turn.
    """
    return llm_json_completion_for_agent(
        env, system_prompt, user_prompt,
        consumer_key=consumer_key, agent_code=agent_code,
        max_tokens=max_tokens, timeout=timeout, json_mode=False,
        failover_on_overflow=failover_on_overflow,
        max_providers=max_providers, images=images, need=need,
        disable_thinking=disable_thinking,
    )


def _resolve_direct_return(tool_result, render_context=None):
    """Texto/HTML para el chat cuando la tool marca retorno directo (__direct_return__)."""
    from .mcp_tool_payload import unwrap_tool_payload

    if not isinstance(tool_result, dict):
        return None
    payload = unwrap_tool_payload(tool_result) or tool_result
    if not (
        payload.get('__direct_return__')
        or payload.get('__return_direct__')
        or payload.get('__return_direct_to_user__')
    ):
        return None
    return (
        _extract_direct_formatted_output(tool_result, render_context=render_context)
        or payload.get('formatted_text')
    )



def _closing_reply_after_probe(config, messages):
    """One tool-less reply when the rounds died on an unmarked lookup.

    The bubble did not get that lookup. The model names an existing record
    or says the create has not been done. Empty string if the call fails.
    """
    from .direct_return_policy import CLOSING_AFTER_PROBE
    from ..lib.llm.drivers import get_llm_driver

    convo = list(messages or [])
    convo.append({'role': 'user', 'content': CLOSING_AFTER_PROBE})
    driver = get_llm_driver(config['protocol'])
    driver.initialize({
        'protocol': config['protocol'],
        'endpoint': config['endpoint'],
        'api_key': config['api_key'],
        'model_name': config.get('model_name') or '',
        'temperature': config['temperature'],
        'extra_headers': config.get('extra_headers') or {},
        'send_temperature': config.get('send_temperature', True),
    })
    parts = []
    for piece in driver.iter_chat(
        convo,
        tools=None,
        temperature=config['temperature'],
        timeout=config['idle_timeout'],
        max_tokens=500,
        disable_thinking=True,
    ):
        bit = piece.get('text') or ''
        if bit:
            parts.append(bit)
        if piece.get('done'):
            msg = piece.get('message') or {}
            if not parts:
                content = msg.get('content') or ''
                if isinstance(content, str) and content.strip():
                    parts.append(content)
            break
    return ''.join(parts).strip()


def _should_show_direct_to_chat(
    payload, *, round_n, max_rounds, tool_name, force_retry=False,
    has_primary=False, user_message=None, user_lang=None,
):
    from .direct_return_policy import should_show_direct_to_chat
    return should_show_direct_to_chat(
        payload,
        round_n=round_n,
        max_rounds=max_rounds,
        tool_name=tool_name,
        force_retry=force_retry,
        has_primary=has_primary,
        user_message=user_message,
        user_lang=user_lang,
    )


def _extract_direct_formatted_output(tool_result, render_context=None):
    """HTML para retorno directo al chat: formatted_text o render bajo demanda."""
    if not isinstance(tool_result, dict):
        return None

    def _postprocess_html(html_content):
        from .relaxaicode_render import wrap_bare_images_clickable
        env = render_context.get('env') if isinstance(render_context, dict) else None
        return wrap_bare_images_clickable(html_content, env=env)

    def _pick_formatted(payload):
        if not isinstance(payload, dict):
            return None
        ft = payload.get('formatted_text')
        if not ft:
            return None
        # Trust boundary: only platform-stamped HTML reaches the chat.
        if payload.get('__fmt_type__') not in (
            'server_side_python', 'author_html', 'local_json', 'local_raw',
        ):
            return None
        return _postprocess_html(ft)

    def _render_if_needed(payload):
        if not isinstance(payload, dict):
            return None
        from .relaxaicode_render import (
            render_for_direct_return, render_result_html, is_tabulable, _result_items,
        )
        rendered = render_for_direct_return(
            payload, payload.get('summary') or '', render_context=render_context,
        )
        if rendered:
            return rendered
        # NO forzar (force=False): respetar la heurística de is_tabulable
        # (mín 5 filas, claves homogéneas). Con force=True se tabulaban
        # respuestas de texto como "¿quién eres?" → tabla ilegible.
        if _result_items(payload) and is_tabulable(payload):
            return render_result_html(
                payload, payload.get('summary') or '', render_context=render_context,
            )
        return None

    def _from_payload(payload):
        # Resultados tabulares "pelados" (lista de dicts en el nivel superior)
        # se envuelven para que el render server-side los detecte como tabla
        # en lugar de volcar el JSON crudo al chat.
        if isinstance(payload, list):
            payload = {'data': payload}
        if not isinstance(payload, dict):
            return None
        direct = _pick_formatted(payload)
        if direct:
            return direct
        return _render_if_needed(payload)

    # Errores recuperables (validación/ejecución del código del LLM): NO renderizar.
    # Deben volver al LLM como salida de tool para que se auto-corrija (bucle ReAct);
    # si los tabuláramos, el usuario vería el error crudo y se cortaría el reintento.
    if tool_result.get('__force_retry__') or tool_result.get('isError'):
        return None

    # El sobre MCP {content:[{type:'text', text:<json>}]} es transporte, no datos.
    # Desenvolvemos SIEMPRE el payload interno antes de renderizar; nunca tabulamos
    # el propio array 'content' (si no, sale una tabla "Type | Text" con el JSON
    # crudo y, además, sombrea el formatted_text bueno de tablas/imágenes).
    blocks = tool_result.get('content')
    if (
        isinstance(blocks, list) and blocks
        and isinstance(blocks[0], dict) and blocks[0].get('type') == 'text'
    ):
        try:
            inner = json.loads(blocks[0].get('text') or '{}')
        except Exception:
            return None
        return _from_payload(inner)

    # No es un sobre MCP: el propio dict ya es el payload.
    return _from_payload(tool_result)


def friendly_skill_fast_path_reason(reason):
    """User-facing fast-path bail. Empty ``result = {}`` is not engine jargon."""
    raw = (reason or '').strip() or 'unknown'
    if raw == 'empty_result' or raw.startswith('no_propose_steps(keys=[]'):
        return _(
            'The skill ran but produced nothing to show '
            '(no table and no query).'
        )
    return raw


def _http_request():
    """Live HTTP request. Importing ``request`` at module load freezes Odoo 14."""
    try:
        from odoo.http import request
        return request
    except Exception:
        return None


class AgentEngine(DiscoveryMixin, SkillsMixin, PresentationMixin, ToolLoopMixin,
                  TurnRecordsMixin, ToolRunMixin, DirectDeliveryMixin,
                  TurnCloseMixin, TurnMessagesMixin):
    def __init__(self, env, source_channel=None, client_label=None,
                 turn_prefix=None, agent_code=None):
        ctx = (env.context if env is not None else {}) or {}
        # Door token (a value of ai.log.origin). Origin on the log
        # is the agent name. The door is never assumed to be Chatboo: a host
        # that wants that token must pass it (or stamp mcp_source_channel).
        self._source_channel = (
            source_channel or ctx.get('mcp_source_channel') or 'internal'
        )
        self._client_label = client_label or ctx.get('mcp_client_label')
        self._agent_code = (
            (agent_code or ctx.get('mcp_agent_code') or '').strip() or None
        )
        self._turn_prefix = turn_prefix or ctx.get('mcp_turn_prefix') or ''
        self._turn_corr = ctx.get('mcp_turn') or None
        stamp = dict(ctx)
        stamp['mcp_source_channel'] = self._source_channel
        if self._agent_code:
            stamp['mcp_agent_code'] = self._agent_code
        if self._client_label:
            stamp['mcp_client_label'] = self._client_label
        if self._turn_prefix:
            stamp['mcp_turn_prefix'] = self._turn_prefix
        if self._turn_corr:
            stamp['mcp_turn'] = self._turn_corr
        self.env = env(context=stamp) if env is not None else env
        # Estado de logging del turno: capturamos UNA correlación y el usuario
        # real una sola vez por turno y los reutilizamos en cada línea del
        # histórico. Durante el streaming SSE el `request` global puede quedar
        # desligado, así que NO dependemos de él en cada log (antes provocaba
        # entradas huérfanas como Administrator y un correlation_id por evento).
        self._turn_uid = env.uid if env is not None else None
        self._turn_step = 0
        self._turn_remote_ip = None
        self._turn_side_usage = {}
        self._turn_effects_done = False
        # Record or tool data reached this turn: outbound plans need a human.
        self._turn_untrusted = False
        self._turn_history = []
        self._prior_domain_codes = []
        self._prior_domain_ages = {}
        self._injected_domain_codes = []
        self._injected_domain_ages = {}
        self._skill_domain_codes = []
        self._held_domain_codes = []
        self._has_prior_query = False
        self._reuse_prior_query = True

    def _begin_turn(self):
        """Snapshot one correlation id + end-user for the whole chat turn."""
        self._turn_uid = self.env.uid
        ctx = self.env.context or {}
        turn = ctx.get('mcp_turn') or self._turn_corr
        req = _http_request()
        if not turn:
            try:
                turn = getattr(req, 'mcp_turn', None)
            except Exception:
                turn = None
        if not turn:
            prefix = getattr(self, '_turn_prefix', None) or ctx.get(
                'mcp_turn_prefix',
            ) or ''
            try:
                turn = new_turn_id(prefix=prefix)
            except TypeError:
                turn = new_turn_id()
        self._turn_corr = turn
        # Garantiza que TODO lector downstream (p. ej. create_verification del
        # safe_plan, que se ejecuta en cursor propio) vea el MISMO turn id
        # del turno. En el streaming SSE el request puede no traer chip y
        # quedaría desincronizado con `self._turn_corr`.
        try:
            if req is not None:
                req.mcp_turn = self._turn_corr
                req.mcp_source_channel = self._source_channel
                if self._agent_code:
                    req.mcp_agent_code = self._agent_code
                if self._client_label:
                    req.mcp_client_label = self._client_label
                if getattr(self, '_turn_prefix', None):
                    req.mcp_turn_prefix = self._turn_prefix
                if not getattr(req, 'mcp_turn_step_counter', None):
                    req.mcp_turn_step_counter = {}
        except Exception:
            pass
        # Context survives nested Environment/cursor better than request attrs.
        ctx = dict(
            ctx,
            mcp_turn=self._turn_corr,
            mcp_source_channel=self._source_channel,
        )
        if self._agent_code:
            ctx['mcp_agent_code'] = self._agent_code
        if self._client_label:
            ctx['mcp_client_label'] = self._client_label
        self.env = self.env(context=ctx)
        self._turn_step = 0
        open_turn_steps(self._turn_corr)
        prev = getattr(self, '_side_usage_token', None)
        if prev is not None:
            try:
                reset_turn_side_usage(prev)
            except Exception:
                pass
        self._side_usage_token = bind_turn_side_usage()
        self._turn_side_usage = {}
        from ..utils.mcp_logging import resolve_remote_ip
        self._turn_remote_ip = resolve_remote_ip()

    def _accumulate_side_usage(self, usage):
        """Fold a satellite LLM call into the parent Chatboo turn.

        No extra ``ai.log`` row (keeps the history readable). The spend lands
        in ``orchestration_summary`` with the turn total. Own-shot headless
        calls use ``inference_audit`` instead — see ``docs/llm_usage_metering.md``.
        """
        piece = normalize_usage(usage) if usage else {}
        if not piece:
            return
        note_turn_side_usage(piece)
        acc = getattr(self, '_turn_side_usage', None)
        if not isinstance(acc, dict):
            acc = {}
        self._turn_side_usage = add_usage(acc, piece)

    def _side_usage(self):
        bound = bound_turn_side_usage()
        if bound:
            return bound
        acc = getattr(self, '_turn_side_usage', None)
        return acc if isinstance(acc, dict) and acc else {}

    def _persist_provider_usage(self, provider, usage):
        """Mark that this provider's replies include usage. No daily table."""
        if not provider or not usage:
            return
        piece = normalize_usage(usage)
        if not usage_has_tokens(piece) and not (piece.get('cost') or 0):
            return
        try:
            if (
                getattr(provider, 'usage_support', 'unknown') == 'unknown'
                and usage_has_tokens(usage)
            ):
                provider._mark_usage_support_yes()
        except Exception:
            _logger.warning(
                'Could not mark usage support for provider %s',
                getattr(provider, 'name', '?'),
                exc_info=True,
            )

    def _next_step(self):
        step = claim_turn_step(self._turn_corr)
        self._turn_step = step or self._turn_step + 1
        return self._turn_step

    def _mcp_log(self, **kwargs):
        """Write one MCP log row for the current turn (shared corr + real user).

        Centraliza el registro del histórico para que TODOS los eventos de un
        turno (petición al LLM, respuesta, herramientas, failover y cierre)
        compartan correlación, paso incremental y el usuario humano correcto.
        """
        if 'ai.log' not in self.env:
            return
        kwargs.setdefault('user_id', self._turn_uid or self.env.uid)
        kwargs.setdefault('turn', self._turn_corr)
        kwargs.setdefault('source_channel', self._source_channel)
        if self._agent_code:
            kwargs.setdefault('agent_code', self._agent_code)
        if self._client_label:
            kwargs.setdefault('client_label', self._client_label)
        kwargs.setdefault('remote_ip', self._turn_remote_ip)
        if not kwargs.get('turn_step'):
            kwargs['turn_step'] = self._next_step()
        try:
            self.env['ai.log'].sudo()._create_log_entry(**kwargs)
        except Exception as exc:
            _logger.warning(
                'AgentEngine: could not write MCP log (%s): %s',
                kwargs.get('tool_name'), exc,
            )

    def log_row(self, **kwargs):
        """One ``ai.log`` row on this engine's turn. No LLM.

        Door events (session, PIN, empty turn) belong on the same thread
        as a spoken turn. Hosts must not write ``_create_log_entry``.
        """
        given = kwargs.get('turn')
        if given:
            self._turn_corr = given
        if not self._turn_corr or self._turn_remote_ip is None:
            self._begin_turn()
        self._mcp_log(**kwargs)

    def _resolve_user_locale(self):
        user = self.env.user
        company = self.env.company.sudo()
        company_lang = company.partner_id.lang if company and company.partner_id else None
        if user and user.id and user.lang and (user.lang != 'en_US' or not company_lang):
            user_lang = user.lang
        elif company_lang:
            user_lang = company_lang
        else:
            user_lang = 'en_US'
        return str(user_lang).replace('-', '_')

    def get_system_prompt(self, agent_code=None, user_message=None):
        """Load cached compiled context for the agent (no cross-agent fallback).

        ``user_message`` is optional: when turn-scoped domain packs are ON,
        a deterministic match logs to Historial IA and appends matched domain
        context bodies to the runtime tail. Indexed codes are excluded from
        ``cached_content`` while the flag is ON
        (see docs/decisions/domain_index_dynamic_load.md).
        """
        prompt_content = ""
        try:
            agent_code = self.env['ai.agent'].resolve_inference_agent_code(agent_code)
            user_lang = self._resolve_user_locale()
            agent = self.env['ai.agent'].search(
                [('code', '=', agent_code)], limit=1,
            )
            if agent:
                prompt_content = agent.get_content(
                    user_locale=user_lang,
                )
            else:
                prompt_content = self.env['ai.agent'].get_for_agent(
                    agent_code, agent_code=agent_code, user_locale=user_lang,
                )
            _logger.info(
                "AgentEngine: agent=%s locale=%s (%d chars)",
                agent_code, user_lang, len(prompt_content or ''),
            )
        except Exception as e:
            _logger.warning("AgentEngine: Failed to load agent context: %s", e)

        if not prompt_content:
            prompt_content = (
                "You are an advanced Odoo Assistant. "
                "You have access to tools to query and manipulate Odoo data."
            )
        # Runtime DATA injection only. All prompt RULES live in the agent's
        # contexts (system_prompt.xml → ai.context), never hardcoded here.
        # What we inject below is live data that cannot be static: the server
        # date, the whitelisted domains and the discovered external MCP tools.
        from datetime import date
        server_today = date.today().isoformat()

        whitelist_hint = ''
        try:
            domains = self.env['ai.url.whitelist'].get_active_domains()
            if domains:
                whitelist_hint = (
                    "\n[fetch_url trusted domains 🟢: "
                    + ", ".join(domains) + "]"
                )
        except Exception:
            pass  # model may not exist yet during install

        # External MCP servers: inject the discovered tool catalogue so the agent
        # calls REAL tool names instead of inventing them (search_read/list_tools).
        external_tools_hint = ''
        try:
            block = self.env['ai.api.server'].get_tools_prompt_block()
            if block:
                external_tools_hint = "\n\n" + block
        except Exception:
            pass  # model may not exist yet during install

        shadow_hint = ''
        try:
            shadow_hint = self._domain_index_runtime_hint(
                user_message, user_locale=user_lang,
            )
        except Exception:
            _logger.debug(
                'AgentEngine: domain_index runtime failed', exc_info=True,
            )

        # Los DATOS de runtime van AL FINAL, no al principio. Así el prefijo
        # grande y estable (system prompt + bundle del rol + reglas) queda
        # byte-idéntico entre turnos (y entre días), lo que habilita el
        # prefix-caching del prompt: reutilización del prefijo de la KV cache en
        # llama.cpp y prefix-cache automático en OpenAI-compatible. Ponerlos
        # delante (la fecha cambia a diario) invalidaría TODO el prefijo cacheado
        # en el token ~5. Ver docs/decisions/cache_estrategia.md.
        runtime_data = (
            f"\n\n---\n[Server date: {server_today}]"
            f"{whitelist_hint}{external_tools_hint}"
            f"{shadow_hint}"
        )
        prompt_content = f"{prompt_content}{runtime_data}"
        return {"role": "system", "content": prompt_content}

    def get_tools_schema(self):
        """
        Obtiene todas las herramientas registradas en Odoo MCP y las convierte
        al formato de OpenAI/Anthropic Functions.
        """
        from ..controllers.mcp_decorators import (
            get_registered_tools,
            tool_visible_to,
        )
        tools_dict = get_registered_tools()
        user = self.env.user

        openai_tools = []
        for name, tool in tools_dict.items():
            if not tool_visible_to(tool, user):
                continue
            openai_tools.append({
                "type": "function",
                "function": {
                    "name": name,
                    "description": tool.get("description", ""),
                    "parameters": tool.get("inputSchema", {})
                }
            })
        return openai_tools

    def run_stream(self, message, history, session_id, agent_code=None, provider=None, consumer_key=None, provider_id=None, prior_query_code=None, prior_query_data=None, screen_context_block=None, prior_active_skill_code=None, prior_active_skill_params=None, prior_domain_codes=None, images=None, recall_images=None, held_domain_codes=None):
        """
        ReAct loop with streaming. Intra-agent provider cascade on connection failure.

        Args:
            provider_id: Optional int. Force a specific provider.
            prior_query_code: Optional str. Code of the last successful data
                query in this session; injected as a hint so reformat/reorder
                follow-ups reuse it instead of re-deriving (reduces variability).
            prior_query_data: Optional list. Rows of the last successful dataset
                in this session; injected as 'previous_result' into the
                relaxaicode namespace so reformat/reorder follow-ups
                transform the SAME data server-side instead of re-querying
                (Level 2, kernel-like reuse; never enters the LLM context).
            screen_context_block: Optional str. Compact [Active screen] block
                from Chatboo UI focus enrichment (runtime data, not a rule).
            prior_domain_codes: Optional list. Domain pack codes injected on
                the previous Chatboo turn. Kept when this sentence matches
                nothing or overlaps them. Dropped when this sentence names
                other packs and shares none.
            held_domain_codes: Optional list. Domain pack codes the host keeps
                open this turn because of its own state. Injected whatever
                the sentence names; never counted as matched by it.
        """
        from ..models.ai_execution_engine import ProviderConnectionError

        # Un único hilo de histórico por turno (correlación + usuario real).
        self._begin_turn()
        self._turn_history = list(history or [])
        self._turn_sent_tabular_to_model = False
        from .domain_index import parse_domain_ages, parse_domain_codes
        self._prior_domain_codes = parse_domain_codes(prior_domain_codes)
        self._prior_domain_ages = parse_domain_ages(prior_domain_codes)
        self._held_domain_codes = parse_domain_codes(held_domain_codes)
        self._injected_domain_codes = []
        self._injected_domain_ages = {}
        self._skill_domain_codes = []
        # Dataset / query-code reuse. Discovery turns this off when the
        # sentence is a new topic so the last rows do not leak into it.
        self._reuse_prior_query = True
        self._has_prior_query = bool(prior_query_data or prior_query_code)
        # Canonical turn utterance for any consumer (glossary gate, formatting…).
        # Prefer an already-set context value; otherwise the engine message.
        _ctx = dict(self.env.context or {})
        if session_id:
            _ctx['ai_session_ref'] = int(session_id)
        if not (_ctx.get('user_message') or '').strip():
            _ctx['user_message'] = message or ''
        if not isinstance(_ctx.get('file_label_by_id'), dict):
            _ctx['file_label_by_id'] = {}
        from .result_page import PAGE_REQUEST_KEY
        if not isinstance(_ctx.get(PAGE_REQUEST_KEY), dict):
            _ctx[PAGE_REQUEST_KEY] = {}
        self.env = self.env(context=_ctx)

        Agent = self.env['ai.agent']
        Engine = self.env['ai.execution.engine']
        agent_code = Agent.resolve_inference_agent_code(agent_code, consumer_key=consumer_key)
        self._agent_code = agent_code
        self.env = self.env(context=dict(
            self.env.context or {},
            mcp_agent_code=agent_code,
        ))
        self._claim_page_turn(message)

        from .conversational import (
            user_may_use_conversational_agent, REFUSED_MESSAGE,
        )
        # Open dialogue only. A short completion does not come through here.
        if not user_may_use_conversational_agent(
            self.env, self.env.user, agent_code=agent_code,
        ):
            yield {'event': 'token', 'content': _(REFUSED_MESSAGE)}
            yield self._done_event(
                session_id, agent_code=agent_code,
                provider=provider, provider_id=provider_id, local=True,
            )
            return

        # --- Slash commands: /skills (lista) y /<code> [args] (invocación) ---
        # Skills se invocan con `/code [args]`. Params: determinista primero;
        # IA híbrida solo si hay ``param_schema`` + texto libre sin resolver.
        # Continuidad mínima: tarjeta HTML sin filas + invocación sin args
        # (o flag ``__await_skill_args__``) → el siguiente mensaje sin slash
        # reanuda ese skill (args = texto). Help nunca espera.
        # Al reanudar, el skill recupera su ``__skill_state__`` de la ronda
        # anterior. Un slash explícito empieza de cero (sin estado heredado).
        resumed_state = {}
        command = self._parse_slash_command(message)
        if command is None and prior_active_skill_code:
            reply = (message or '').strip()
            if reply and not reply.startswith('/'):
                pending = self._resolve_skill(agent_code, prior_active_skill_code)
                if pending:
                    from .skill_runtime import skill_state_from_params
                    command = (prior_active_skill_code, reply)
                    resumed_state = skill_state_from_params(
                        prior_active_skill_params,
                    )
                    _logger.info(
                        'agent_engine: resume pending skill /%s with reply '
                        '(session=%s, state_keys=%s)',
                        prior_active_skill_code, session_id,
                        sorted(resumed_state) or '-',
                    )
        if command is None:
            triggered = self._triggered_skill_command(agent_code, message)
            if triggered:
                command = triggered
                self._mcp_log(
                    operation_type='read',
                    tool_name='skill_trigger',
                    prompt_data={
                        'skill': triggered[0],
                        'arguments': triggered[1],
                    },
                    result_summary=(
                        'Skill from sentence (/%s)' % triggered[0]
                    )[:480],
                    request_type='tool',
                )

        from .slash_domain_codes import slash_releases_domain_codes
        cmd_token = command[0] if command else None
        skill_hit = False
        if cmd_token:
            try:
                skill_hit = bool(self._resolve_skill(agent_code, cmd_token))
            except Exception:
                skill_hit = False
        if slash_releases_domain_codes(cmd_token, skill_resolved=skill_hit):
            self._prior_domain_codes = []
            self._prior_domain_ages = {}

        _stop, message = yield from self._run_slash_command(
            agent_code=agent_code,
            command=command,
            message=message,
            provider=provider,
            provider_id=provider_id,
            resumed_state=resumed_state,
            session_id=session_id,
        )
        if _stop:
            return

        if provider is not None:
            yield from self._run_stream_with_provider(
                message, history, session_id, agent_code, provider,
                prior_query_code=prior_query_code,
                prior_query_data=prior_query_data,
                screen_context_block=screen_context_block,
                images=images,
                recall_images=recall_images,
            )
            return

        # Resolve providers (supports auto-assign + UI override)
        try:
            need = 'vision' if (images or recall_images) else 'conversation'
            providers = Engine.get_providers_for_agent(
                agent_code, need=need,
            )
        except Exception as exc:
            from .error_ux import exception_user_text
            text = exception_user_text(exc)
            yield {
                'event': 'error',
                'content': text,
                'message': text,
            }
            yield self._done_event(
                session_id,
                agent_code=agent_code,
                provider=provider,
                provider_id=provider_id,
            )
            return

        # Build the provider cascade (admin-managed links; readable via sudo in engine)
        cascade_providers = list(providers)

        # UI pick: first among those that fit this function. The rest of
        # that same filtered chain is failover. An id that does not fit
        # (or is not on the agent) is ignored — never the whole chain.
        if provider_id:
            selected = self.env['ai.provider'].browse(provider_id).exists()
            if selected and selected.id in [p.id for p in cascade_providers]:
                cascade_providers = [selected] + [
                    p for p in cascade_providers if p.id != selected.id
                ]

        last_error = None
        failed_provider = None
        provider_errors = []
        self._turn_effects_done = False
        # A form on screen is interface data, not a reason to hold a trusted
        # fetch. The flag turns on after a tool has already returned text.
        self._turn_untrusted = False
        for idx, current in enumerate(cascade_providers):
            if idx > 0 and failed_provider:
                Engine.log_provider_failover(
                    agent_code, failed_provider, current, last_error,
                    user_id=self._turn_uid,
                    turn=self._turn_corr,
                    turn_step=self._next_step(),
                    source_channel=self._source_channel,
                    client_label=self._client_label,
                )
            _emitted_content = False
            try:
                for event in self._run_stream_with_provider(
                    message, history, session_id, agent_code, current,
                    prior_query_code=prior_query_code,
                    prior_query_data=prior_query_data,
                    screen_context_block=screen_context_block,
                    images=images,
                    recall_images=recall_images,
                ):
                    _ev = (event or {}).get('event')
                    if _ev in ('token', 'replace') and (event or {}).get('content'):
                        _emitted_content = True
                    yield event
                return
            except TurnTimeExceeded as exc:
                # The provider already worked this turn. A 300s wall is not
                # "OpenRouter is down": failing over restarts the question
                # on the backup model and throws away the rounds so far.
                _logger.warning(
                    'AgentEngine: turn wall exceeded on %s; not failing over',
                    current.name,
                )
                yield {"event": "token", "content": str(exc)}
                yield self._done_event(
                    session_id,
                    agent_code=agent_code,
                    provider=current,
                    provider_id=current.id,
                )
                return
            except ProviderConnectionError as exc:
                last_error = exc
                failed_provider = current
                provider_errors.append((current.name, str(exc)))
                _logger.warning(
                    'AgentEngine failover: agent=%s provider=%s failed: %s',
                    agent_code, current.name, exc,
                )
                if self._turn_effects_done:
                    # The next provider restarts the turn: it would run the
                    # executed plan (fetch_url, trusted api_call) a second time.
                    if _emitted_content:
                        yield {'event': 'replace', 'content': ''}
                    yield {"event": "token", "content": _(
                        'The AI provider failed after an operation had already '
                        'run, so the turn was not retried on another provider '
                        '(it would run twice). Ask again to continue.'
                    )}
                    yield self._done_event(
                        session_id,
                        agent_code=agent_code,
                        provider=current,
                        provider_id=current.id,
                    )
                    return
                # Si este proveedor YA había emitido contenido visible antes de
                # caer, el consumidor lo tiene acumulado; al reintentar con el
                # siguiente proveedor se generaría de nuevo -> respuesta DUPLICADA.
                # Emitimos un 'replace' vacío para que el consumidor descarte lo
                # parcial antes del reintento (el worker lo interpreta como reset).
                if _emitted_content:
                    yield {'event': 'replace', 'content': ''}
        err = _('All providers failed for agent "%s".') % agent_code
        if provider_errors:
            # Mostrar el fallo de CADA proveedor (no solo el último): así se ve la
            # causa raíz (p. ej. local caído) y no solo el error del fallback.
            err += '\n' + '\n'.join(
                '  • %s: %s' % (name, msg) for name, msg in provider_errors
            )
        # compose-model died after sending rows: tell the user. Do not paint
        # a local table and do not switch compose (failover is providers).
        try:
            from .mcp_tool_payload import append_compose_model_overflow_hint
            err = append_compose_model_overflow_hint(
                err,
                compose=getattr(self, '_turn_compose', None),
                sent_tabular=getattr(self, '_turn_sent_tabular_to_model', False),
                translate=_,
            )
        except Exception:
            pass
        yield {
            'event': 'token',
            'content': '\n\n🛑 **Servidor MCP:** %s\n' % err,
        }
        yield self._done_event(
            session_id,
            agent_code=agent_code,
            provider=provider,
            provider_id=provider_id,
        )

    def _run_slash_command(
            self,
            agent_code,
            command,
            message,
            provider,
            provider_id,
            resumed_state,
            session_id,
    ):
        """Slash command turn: help, axis commands, skill code or prompt. Returns (stop, message)."""
        if command is not None:
            cmd, args = command
            if cmd.lower() in ('skills', 'skill', 'help', 'ayuda', '?'):
                from .skill_dates import skill_args_are_help as _cmd_help
                from .skill_help import builtin_slash_help_meta
                if (args or '').strip() and _cmd_help(args):
                    yield from self._emit_slash_help(
                        builtin_slash_help_meta('skills'),
                        session_id, agent_code, provider, provider_id,
                    )
                    return True, None
                yield {'event': 'token', 'content': self._skills_list_markdown(agent_code)}
                yield self._done_event(
                    session_id,
                    agent_code=agent_code,
                    provider=provider,
                    provider_id=provider_id,
                )
                return True, None
            from .formatting_mode_policy import (
                AXIS_COMMANDS,
                AXIS_FOOTMODE,
                AXIS_COMPOSE,
                AXIS_SHOWMODE,
                COMPOSE_MODEL,
            )
            if cmd.lower() in AXIS_COMMANDS:
                from .skill_dates import skill_args_are_help as _axis_help
                from .skill_help import builtin_slash_help_meta
                if _axis_help(args):
                    yield from self._emit_slash_help(
                        builtin_slash_help_meta(cmd.lower()),
                        session_id, agent_code, provider, provider_id,
                    )
                    return True, None
                axis, value = AXIS_COMMANDS[cmd.lower()]
                ctx = dict(self.env.context or {})
                if axis == AXIS_COMPOSE:
                    ctx['llm_remote_formatting_override'] = (value == COMPOSE_MODEL)
                    ctx['turn_compose'] = value
                    if value == COMPOSE_MODEL:
                        content = _(
                            'compose-model for this turn only — the model '
                            'composes the bubble. Later messages inherit the provider '
                            'unless you prefix with `/compose-model`.'
                        )
                    else:
                        content = _(
                            'compose-agent for this turn only — the agent '
                            'composes tables/charts. Later messages inherit the '
                            'provider unless you prefix with `/compose-agent`.'
                        )
                elif axis == AXIS_FOOTMODE:
                    ctx['turn_footmode'] = value
                    if value == 'foot-laconic':
                        content = _(
                            'Footmode foot-laconic for this turn only — no footer '
                            'after local tables. Later messages inherit the provider '
                            'unless you prefix with `/foot-laconic`.'
                        )
                    else:
                        content = _(
                            'Footmode foot-verbose for this turn only — short warm '
                            'footer after local tables. Later messages inherit the '
                            'provider unless you prefix with `/foot-verbose`.'
                        )
                else:
                    ctx['presentation_show_mode'] = value
                    content = _(
                        'Showmode %s for this session — stays until you switch '
                        'with `/show-table` or `/show-chart`.'
                    ) % value
                self.env = self.env(context=ctx)
                if (args or '').strip():
                    message = (args or '').strip()
                else:
                    yield {'event': 'token', 'content': content}
                    yield self._done_event(
                        session_id,
                        agent_code=agent_code,
                        provider=provider,
                        provider_id=provider_id,
                    )
                    return True, None
            else:
                skill = self._resolve_skill(agent_code, cmd)
                if not skill:
                    content = _('No existe el skill `/%s`.') % cmd
                    yield {'event': 'token', 'content': content}
                    yield self._done_event(
                        session_id,
                        agent_code=agent_code,
                        provider=provider,
                        provider_id=provider_id,
                    )
                    return True, None
                self._remember_skill_domain_codes(skill)
                yield self._domain_codes_event()
                slash = skill.invoke_code()
                from .skill_dates import skill_args_are_help as _skill_args_are_help
                from .skill_help import skill_help_meta
                _help_args = _skill_args_are_help(args)
                _args_policy = self._skill_args_policy(skill)
                if _help_args:
                    self._mcp_log(
                        operation_type='read',
                        tool_name='skill_help_direct',
                        prompt_data={'skill': slash, 'arguments': args},
                        result_summary=('Skill help card (%s)' % slash)[:480],
                        request_type='tool',
                    )
                    yield from self._emit_slash_help(
                        skill_help_meta(skill),
                        session_id, agent_code, provider, provider_id,
                        skill_code=slash,
                    )
                    return True, None
                _need_required = False
                if not (args or '').strip() and _args_policy != 'none':
                    try:
                        from .skill_runtime import (
                            empty_args_need_required_ask,
                            parse_param_schema_txt,
                        )
                        _need_required = empty_args_need_required_ask(
                            parse_param_schema_txt(
                                getattr(skill, 'param_schema', '') or '',
                            ),
                        )
                    except Exception:
                        _need_required = False
                if not (args or '').strip() and (
                    _args_policy == 'ask' or _need_required
                ):
                    self._mcp_log(
                        operation_type='read',
                        tool_name='skill_args_ask',
                        prompt_data={'skill': slash, 'arguments': args},
                        result_summary=('Skill ask args (%s)' % slash)[:480],
                        request_type='tool',
                    )
                    yield from self._emit_slash_help(
                        skill_help_meta(skill),
                        session_id, agent_code, provider, provider_id,
                        skill_code=slash, asking=True,
                    )
                    return True, None
                if (args or '').strip() and _args_policy == 'none':
                    self._mcp_log(
                        operation_type='read',
                        tool_name='skill_args_reject',
                        prompt_data={'skill': slash, 'arguments': args},
                        result_summary=(
                            'Skill args rejected (%s)' % slash
                        )[:480],
                        request_type='tool',
                    )
                    yield from self._emit_slash_help(
                        skill_help_meta(skill),
                        session_id, agent_code, provider, provider_id,
                        skill_code=slash, rejected=True,
                    )
                    return True, None
                # Params: deterministic first; LLM only if param_schema + unresolved
                # free text (hybrid). No sticky session state.
                user_lang = self._resolve_user_locale()
                payload = skill.build_invocation_payload(user_locale=user_lang, arguments=args)

                if (skill.code_body or '').strip():
                    # Skill CON codigo: se resuelve server-side de forma determinista
                    # o compose-model entrega datos al LLM (one-shot, no sticky).
                    from .formatting_mode_policy import (
                        COMPOSE_AGENT,
                        COMPOSE_MODEL,
                        normalize_compose,
                    )
                    from .skill_runtime import (
                        bootstrap_skill_code_body,
                        presentation_from_bootstrap,
                        should_await_skill_args,
                        skill_state_for_await,
                        try_skill_fast_path,
                    )
                    skill_compose = normalize_compose(
                        getattr(skill, 'compose', None) or '',
                    )
                    # Declared params (schema or hint) = the skill takes args.
                    _accepts_args = (
                        _args_policy != 'none'
                        and bool(
                            (getattr(skill, 'param_schema', '') or '').strip()
                            or (getattr(skill, 'arg_hint', '') or '').strip()
                        )
                    )
                    if (
                        skill_compose in (COMPOSE_MODEL, COMPOSE_AGENT)
                        and not (self.env.context or {}).get('turn_compose')
                    ):
                        self.env = self.env(context=dict(
                            self.env.context or {},
                            llm_remote_formatting_override=(
                                skill_compose == COMPOSE_MODEL and not _help_args
                            ),
                            turn_compose=(
                                None if _help_args else skill_compose
                            ),
                        ))
                    norm_params = None
                    if _help_args:
                        # Deterministic help card: no hybrid LLM, no report handoff.
                        _tok = (args or '').strip() or '?'
                        norm_params = {
                            'arguments': _tok,
                            'periodo': _tok,
                            'lugar': _tok,
                        }
                    else:
                        try:
                            norm_params = self._normalize_skill_params(
                                skill, args, agent_code,
                                provider=provider, provider_id=provider_id,
                            )
                        except Exception as exc:
                            _logger.debug(
                                'param normalization skipped for %s: %s',
                                slash, exc,
                            )
                    if (
                        isinstance(norm_params, dict)
                        and norm_params.get('_skill_args_reject')
                    ):
                        self._mcp_log(
                            operation_type='read',
                            tool_name='skill_args_reject',
                            prompt_data={'skill': slash, 'arguments': args},
                            result_summary=(
                                'Skill args rejected (%s)' % slash
                            )[:480],
                            request_type='tool',
                        )
                        yield from self._emit_slash_help(
                            skill_help_meta(skill),
                            session_id, agent_code, provider, provider_id,
                            skill_code=slash,
                            rejected=not norm_params.get('_skill_args_missing'),
                            asking=bool(norm_params.get('_skill_args_missing')),
                        )
                        return True, None
                    # Slots pegajosos: el skill lee ``skill_state`` (vacío en
                    # una invocación nueva) y decide qué le falta todavía.
                    norm_params = dict(norm_params or {})
                    norm_params['skill_state'] = resumed_state
                    boot_diag = {}
                    bootstrap = bootstrap_skill_code_body(
                        self.env, skill.code_body, arguments=args,
                        skill_code=slash, extra_params=norm_params,
                        diag=boot_diag,
                        param_schema=getattr(skill, 'param_schema', None),
                    )
                    if isinstance(bootstrap, dict):
                        _page_card = self._offer_page_card(
                            presentation_from_bootstrap(bootstrap) or bootstrap,
                        )
                        if _page_card:
                            self._mcp_log(
                                operation_type='read',
                                tool_name='skill_report_handoff',
                                prompt_data={
                                    'skill': slash,
                                    'arguments': args,
                                },
                                result_summary=(
                                    'Skill page card (%s)' % slash
                                )[:480],
                                request_type='tool',
                            )
                            yield {'event': 'replace', 'content': _page_card}
                            yield {
                                'event': 'active_skill',
                                'code': None,
                                'params': {},
                            }
                            yield self._done_event(
                                session_id, agent_code=agent_code,
                                provider=provider, provider_id=provider_id,
                                skill_code=slash,
                            )
                            return True, None
                    fp_diag = {}
                    fast = None
                    # Help cards always use fast-path HTML (even on compose-model).
                    if bootstrap is not None and (
                        skill_compose != COMPOSE_MODEL or _help_args
                    ):
                        fast = try_skill_fast_path(
                            self.env, bootstrap,
                            title=skill.name or slash,
                            code=skill.code_body, arguments=args,
                            skill_code=slash, extra_params=norm_params,
                            diag=fp_diag,
                            param_schema=getattr(skill, 'param_schema', None),
                        )
                    if _help_args:
                        _help_html = (fast or {}).get('html') if fast else None
                        if not _help_html and isinstance(bootstrap, dict):
                            _pres = (
                                presentation_from_bootstrap(bootstrap)
                                or bootstrap
                            )
                            _help_html = (
                                (_pres.get('formatted_text') or '').strip()
                                or None
                            )
                        if not _help_html:
                            from .skill_help import build_slash_help_html
                            _help_html = build_slash_help_html(
                                skill_help_meta(skill),
                            )
                        self._mcp_log(
                            operation_type='read',
                            tool_name='skill_help_direct',
                            prompt_data={
                                'skill': slash,
                                'arguments': args,
                            },
                            result_summary=(
                                'Skill help card (%s)' % slash
                            )[:480],
                            request_type='tool',
                        )
                        yield {'event': 'replace', 'content': _help_html}
                        yield {
                            'event': 'active_skill',
                            'code': None,
                            'params': {},
                        }
                        yield self._done_event(
                            session_id, agent_code=agent_code,
                            provider=provider, provider_id=provider_id,
                            skill_code=slash,
                            local=True,
                        )
                        return True, None
                    # compose-model: hand tabular data to the LLM (it owns the UI).
                    # Exception: deterministic cards (help/?, soft errors) that
                    # already ship formatted_text + __return_direct__ without
                    # tabular rows — no LLM (same as compose-agent fast-path).
                    if (
                        skill_compose == COMPOSE_MODEL
                        and isinstance(bootstrap, dict)
                    ):
                        from .mcp_tool_payload import (
                            payload_has_tabular_rows,
                            remote_format_handoff_payload,
                        )
                        pres = presentation_from_bootstrap(bootstrap) or bootstrap
                        _ft = (pres.get('formatted_text') or '').strip()
                        if (
                            _ft
                            and (
                                pres.get('__return_direct__')
                                or pres.get('__stop_after_direct__')
                            )
                            and not payload_has_tabular_rows(pres)
                        ):
                            self._mcp_log(
                                operation_type='read',
                                tool_name='skill_report_direct',
                                prompt_data={
                                    'skill': slash,
                                    'arguments': args,
                                },
                                result_summary=(
                                    'Skill report direct HTML (%s)' % slash
                                )[:480],
                                request_type='tool',
                            )
                            yield {'event': 'replace', 'content': _ft}
                            if should_await_skill_args(
                                pres, arguments=args,
                                is_help=_help_args,
                                accepts_args=_accepts_args,
                                args_policy=_args_policy,
                            ):
                                yield {
                                    'event': 'active_skill',
                                    'code': slash,
                                    'params': {
                                        'awaiting_args': True,
                                        'state': skill_state_for_await(
                                            pres, bootstrap,
                                        ),
                                    },
                                }
                            else:
                                yield {
                                    'event': 'active_skill',
                                    'code': None,
                                    'params': {},
                                }
                            yield self._done_event(
                                session_id, agent_code=agent_code,
                                provider=provider, provider_id=provider_id,
                                skill_code=slash,
                            )
                            return True, None
                        if payload_has_tabular_rows(pres):
                            handoff = remote_format_handoff_payload(pres) or {
                                'remote_format': True,
                                'data_rendered': False,
                                'data': pres.get('data'),
                                'groups': pres.get('groups'),
                                'sections': pres.get('sections'),
                                'tables': pres.get('tables'),
                                'summary': pres.get('summary'),
                                'title': pres.get('title') or skill.name,
                            }
                            # Drop Nones for a cleaner JSON blob.
                            handoff = {
                                k: v for k, v in handoff.items()
                                if v is not None
                            }
                            try:
                                data_json = json.dumps(
                                    handoff, ensure_ascii=False, default=str,
                                )
                            except Exception:
                                data_json = str(handoff)
                            _outline = handoff.get('report_outline')
                            _closing = handoff.get('closing_required')
                            _reco_stub = handoff.get('recommendations_stub')
                            _reco_heading = handoff.get('recommendations_heading')
                            # Persist for post-stream: outline completion + HTML tables.
                            import copy as _copy_pres
                            self._report_contract = {
                                'report_outline': _outline,
                                'closing_required': _closing,
                                'recommendations_stub': _reco_stub,
                                'recommendations_heading': _reco_heading,
                            }
                            self._report_tables_payload = _copy_pres.deepcopy(pres)
                            _contract = ''
                            if isinstance(_outline, (list, tuple)) and _outline:
                                _contract += (
                                    '\nREQUIRED OUTLINE (`report_outline` '
                                    'from the JSON), in this order and with these '
                                    'exact headings:\n%s\n'
                                ) % '\n'.join(
                                    '- %s' % h for h in _outline
                                )
                            if isinstance(_closing, str) and _closing.strip():
                                _contract += (
                                    '\nREQUIRED CLOSING: the LAST section '
                                    'of the report must include this line '
                                    '(copy it verbatim if it is already complete; '
                                    'never leave it out):\n`%s`\n'
                                ) % _closing.strip()
                            message = (
                                'The user invoked the skill `/%s` in report '
                                'mode (this turn only).\n'
                                'NEW REPORT this turn: write the complete '
                                'narrative now. Do not tell the user the report '
                                'is already in a previous message. History stubs '
                                'forbid reprinting table rows, not this outline.\n'
                                '%s\n'
                                'You compose the whole response UI: '
                                'Markdown, HTML, the chat\'s native tables/charts, '
                                'or a mix. Nothing is forbidden. '
                                'If the JSON carries `formatted_text`, that HTML '
                                'has NOT been shown yet: embed it if you want '
                                'native tables/charts (it already carries '
                                'data-ai-dataset).\n\n'
                                'OPEN the report with ONE single H1 (`# …`) '
                                'written from the period/label in the JSON '
                                '(e.g. last 12 months, YTD, a year or a range). '
                                'Do not use `PERIOD=`. '
                                'Right below the H1, if the JSON carries `company`, '
                                'copy that name VERBATIM (untranslated, without '
                                'a Company label).\n\n'
                                'Skill procedure:\n\n%s\n\n'
                                'Deterministic skill data (the ONLY valid '
                                'figures; do not invent any):\n```json\n%s\n```\n\n'
                                'Write the report. FIXED OUTLINE: do not leave out '
                                'any section. Quote figures from the JSON.'
                            ) % (slash, _contract, payload, data_json)
                            self._mcp_log(
                                operation_type='read',
                                tool_name='skill_report_handoff',
                                prompt_data={
                                    'skill': slash,
                                    'arguments': args,
                                },
                                result_summary=(
                                    'Skill report handoff (%s)' % slash
                                )[:480],
                                request_type='tool',
                            )
                            # Resolved period — drop clarification sticky.
                            yield {
                                'event': 'active_skill',
                                'code': None,
                                'params': {},
                            }
                            # Fall through to the LLM provider loop.
                        elif boot_diag.get('bootstrap_error'):
                            yield {
                                'event': 'token',
                                'content': _(
                                    "Could not run the skill '/%s' "
                                    'deterministically.\n\n**Reason:** %s'
                                ) % (
                                    slash,
                                    friendly_skill_fast_path_reason(
                                        boot_diag.get('bootstrap_error'),
                                    ),
                                ),
                            }
                            yield self._done_event(
                                session_id, agent_code=agent_code,
                                provider=provider, provider_id=provider_id,
                                skill_code=slash,
                            )
                            return True, None
                        else:
                            yield {
                                'event': 'token',
                                'content': _(
                                    "Skill '/%s' is in report mode but returned "
                                    'no tabular data to format.'
                                ) % slash,
                            }
                            yield self._done_event(
                                session_id, agent_code=agent_code,
                                provider=provider, provider_id=provider_id,
                                skill_code=slash,
                            )
                            return True, None
                    elif fast and fast.get('html'):
                        self._mcp_log(
                            operation_type='read',
                            tool_name='skill_fast_path',
                            prompt_data={
                                'skill': slash,
                                'arguments': args,
                                'verification_id': fast.get('verification_id'),
                            },
                            result_summary=(
                                'Skill fast-path HTML (%s)' % slash
                            )[:480],
                            request_type='tool',
                        )
                        yield {'event': 'replace', 'content': fast['html']}
                        # CRUD propose_steps: mismo toast que safe_plan_request
                        if fast.get('verification_id'):
                            event = {
                                'event': 'verification',
                                'verification_id': fast['verification_id'],
                                'title': fast.get('title') or skill.name or '',
                                'plan': fast.get('plan') or [],
                                'danger_level': fast.get('danger_level') or 'medium',
                            }
                            token = self._mint_card_token(fast['verification_id'])
                            if token:
                                event['confirm_token'] = token
                            yield event
                        _pres_fp = (
                            presentation_from_bootstrap(bootstrap)
                            or bootstrap
                        ) if isinstance(bootstrap, dict) else {}
                        _await_args = should_await_skill_args(
                            _pres_fp, arguments=args,
                            is_help=_help_args,
                            accepts_args=_accepts_args,
                            args_policy=_args_policy,
                        )
                        if _await_args:
                            yield {
                                'event': 'active_skill',
                                'code': slash,
                                'params': {
                                    'awaiting_args': True,
                                    'state': skill_state_for_await(
                                        _pres_fp, bootstrap,
                                    ),
                                },
                            }
                        else:
                            yield {
                                'event': 'active_skill',
                                'code': None,
                                'params': {},
                            }
                        yield self._done_event(
                            session_id, agent_code=agent_code,
                            provider=provider, provider_id=provider_id,
                            skill_code=slash,
                            sources=fast.get('sources'),
                            clip_data=self._clip_data_from_payload(_pres_fp),
                        )
                        return True, None
                    else:
                        # No se pudo resolver server-side -> ERROR CLARO, sin LLM.
                        reason = (
                            boot_diag.get('bootstrap_error')
                            or fp_diag.get('reason')
                            or 'desconocido'
                        )
                        shown = friendly_skill_fast_path_reason(reason)
                        self._mcp_log(
                            operation_type='read',
                            tool_name='skill_fast_path_error',
                            prompt_data={
                                'skill': slash,
                                'round': fp_diag.get('round'),
                                'reason': reason,
                            },
                            result_summary=(
                                'Skill %s no resuelto server-side: %s'
                                % (slash, reason)
                            )[:480],
                            request_type='tool',
                        )
                        yield {
                            'event': 'token',
                            'content': _(
                                "Could not run the skill '/%s' deterministically."
                                '\n\n**Reason:** %s'
                            ) % (slash, shown),
                        }
                        yield self._done_event(
                            session_id, agent_code=agent_code,
                            provider=provider, provider_id=provider_id,
                            skill_code=slash,
                        )
                        return True, None

                else:
                    # Prompt-only skill (no code_body): the LLM runs the procedure.
                    message = (
                        'The user invoked the skill `/%s`. Follow its '
                        'procedure to the letter:\n\n%s'
                        % (slash, payload)
                    )
        return False, message
