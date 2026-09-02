# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""Native agentic engine for Odoo (ReAct loop + tool calling + streaming)."""

import json
import logging
import os
import time
from odoo import SUPERUSER_ID, _
from odoo.http import request as http_request
from .mcp_correlation import ensure_turn_correlation, new_correlation_id
from .llm_usage import add_usage, advertise_cost, usage_has_tokens
from .agent_stream_text import (
    NO_TOOL_FINAL_NUDGE,
    pretool_progress_status,
    should_block_no_tool_as_final,
    should_block_progress_as_final,
    strip_think_blocks,
    user_visible_round_text,
)

_logger = logging.getLogger(__name__)

# Límites del bucle ReAct en Chatboo (evita colgues de 15–20 min con OVH/Ollama lentos)
LLM_STREAM_READ_TIMEOUT = 45       # segundos sin datos entre chunks SSE
LLM_ROUND_WALL_TIMEOUT = 120       # segundos máximos por ronda LLM
LLM_AGENT_WALL_TIMEOUT = 300         # segundos máximos para toda la petición del usuario

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


def _sse_payload_from_line(line_str):
    """JSON payload from an SSE data line or a raw JSON line (non-SSE gateways)."""
    if not line_str or line_str.startswith(':'):
        return None
    if line_str.startswith('data:'):
        payload = line_str[5:].lstrip()
        return payload if payload else None
    if line_str.startswith('{'):
        return line_str
    return None


# Compat: nombres privados usados por tests / callers antiguos.
_strip_think_blocks = strip_think_blocks
_user_visible_round_text = user_visible_round_text
_pretool_progress_status = pretool_progress_status
_should_block_progress_as_final = should_block_progress_as_final
_should_block_no_tool_as_final = should_block_no_tool_as_final


def _openai_stream_text_tokens(chunk):
    """Extract the assistant's *visible answer* tokens from one stream chunk.

    Only the real ``content`` is returned. Reasoning fields (``reasoning_content``,
    ``reasoning``) are the model's internal thinking (some models emit it
    separately when llama.cpp runs with ``--jinja``) and MUST NOT be shown to the
    user; including them dumps the chain-of-thought into the chat.
    """
    tokens = []
    choices = chunk.get('choices') or []
    if not choices:
        return tokens
    choice = choices[0]
    delta = choice.get('delta') or {}
    if delta.get('content'):
        tokens.append(delta['content'])
    message = choice.get('message') or {}
    if message.get('content'):
        tokens.append(message['content'])
    if choice.get('text'):
        tokens.append(choice['text'])
    return tokens


def _openai_stream_merge_tool_calls(delta, tool_calls_buffer):
    """Accumulate tool_calls deltas into tool_calls_buffer (indexed by tc index)."""
    if 'tool_calls' not in delta:
        return
    for tc in delta['tool_calls']:
        idx = tc.get('index', 0)
        if idx not in tool_calls_buffer:
            tool_calls_buffer[idx] = {
                'id': tc.get('id', ''),
                'type': 'function',
                'function': {'name': '', 'arguments': ''},
            }
        if tc.get('id'):
            tool_calls_buffer[idx]['id'] = tc['id']
        fn = tc.get('function') or {}
        if fn.get('name'):
            tool_calls_buffer[idx]['function']['name'] += fn['name']
        if fn.get('arguments'):
            tool_calls_buffer[idx]['function']['arguments'] += fn['arguments']


def _openai_sync_completion(endpoint, headers, payload):
    """Non-streaming completion; returns content/tool_calls or an explicit error.

    Returns a dict that may carry an ``error`` key so callers can surface the real
    HTTP status (e.g. 400 = prompt larger than the model's loaded ctx_size) instead
    of masking it as an empty response.
    """
    import urllib.request
    import urllib.error
    sync_payload = dict(payload)
    sync_payload['stream'] = False
    # stream_options solo es válido con stream=True (OpenAI). Si queda aquí,
    # OVH Kepler y otros responden 400 y el motor hacía failover en vano.
    sync_payload.pop('stream_options', None)
    req = urllib.request.Request(
        endpoint,
        data=json.dumps(sync_payload).encode('utf-8'),
        headers=headers,
        method='POST',
    )
    try:
        with urllib.request.urlopen(req, timeout=LLM_STREAM_READ_TIMEOUT) as response:
            body = json.loads(response.read().decode('utf-8'))
    except urllib.error.HTTPError as exc:
        error_text = exc.read().decode('utf-8', errors='ignore')
        _logger.error('OpenAI sync fallback HTTP %s (%s): %s', exc.code, endpoint, error_text)
        return {'content': '', 'tool_calls': [], 'error': 'HTTP %s: %s' % (exc.code, error_text[:300])}
    except Exception as exc:
        _logger.warning('OpenAI sync fallback failed (%s): %s', endpoint, exc)
        return {'content': '', 'tool_calls': [], 'error': str(exc)[:300]}
    choices = body.get('choices') or []
    if not choices:
        return {'content': '', 'tool_calls': [], 'usage': body.get('usage')}
    message = choices[0].get('message') or {}
    return {
        'content': message.get('content') or choices[0].get('text') or '',
        'tool_calls': message.get('tool_calls') or [],
        'usage': body.get('usage'),
    }


def _payload_without_tools(payload):
    if 'tools' not in payload:
        return None
    lean = dict(payload)
    lean.pop('tools', None)
    lean.pop('tool_choice', None)
    return lean


def _apply_openai_sync_fallback(endpoint, headers, payload):
    """Try sync completion (with tools, then without). Returns content, tool_calls, error."""
    content = ''
    tool_calls = {}
    last_error = None
    for attempt in (payload, _payload_without_tools(payload)):
        if attempt is None:
            continue
        result = _openai_sync_completion(endpoint, headers, attempt)
        if not result:
            continue
        if result.get('error'):
            last_error = result['error']
        if result.get('content'):
            content = result['content']
        for idx, tc in enumerate(result.get('tool_calls') or []):
            tool_calls[idx] = tc
        if content.strip() or tool_calls:
            return content, tool_calls, None
    return content, tool_calls, last_error


def llm_json_completion(provider, system_prompt, user_prompt,
                        max_tokens=512, timeout=None):
    """Short non-streaming LLM call; returns response text ('' on error).

    Shared short JSON call (no tools, no streaming): skill ``param_schema``
    holes, and Detection trigger synonyms on ``ai.api.server``.
    """
    import urllib.request
    try:
        endpoint = provider.endpoint or ''
        if endpoint and not endpoint.startswith('http'):
            endpoint = 'https://' + endpoint
        model_name = (
            (provider.model_id.name if provider.model_id else None)
            or provider.model_name or 'gpt-4o-mini'
        )
        api_key = provider._api_key_for_inference()
        protocol = provider.protocol
        headers = {'Content-Type': 'application/json'}
        if protocol == 'anthropic':
            if api_key:
                headers['x-api-key'] = api_key
            headers['anthropic-version'] = '2023-06-01'
            payload = {
                'model': model_name,
                'max_tokens': max_tokens,
                'system': system_prompt,
                'messages': [{'role': 'user', 'content': user_prompt}],
                'temperature': 0,
                'stream': False,
            }
            req = urllib.request.Request(
                endpoint, data=json.dumps(payload).encode('utf-8'),
                headers=headers, method='POST',
            )
            with urllib.request.urlopen(
                req, timeout=timeout or LLM_STREAM_READ_TIMEOUT,
            ) as response:
                body = json.loads(response.read().decode('utf-8'))
            parts = body.get('content') or []
            return ''.join(
                p.get('text', '') for p in parts if isinstance(p, dict)
            )
        if api_key:
            headers['Authorization'] = 'Bearer %s' % api_key
        payload = {
            'model': model_name,
            'messages': [
                {'role': 'system', 'content': system_prompt},
                {'role': 'user', 'content': user_prompt},
            ],
            'temperature': 0,
            'max_tokens': max_tokens,
        }
        result = _openai_sync_completion(endpoint, headers, payload)
        if not result or result.get('error'):
            return ''
        return result.get('content') or ''
    except Exception as exc:
        _logger.debug('llm_json_completion failed: %s', exc)
        return ''



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


_TRUSTED_CHAT_FMT_TYPES = frozenset({
    'server_side_python', 'author_html', 'local_json', 'local_raw',
})


def _payload_marked_user_facing(payload):
    from .direct_return_policy import payload_marked_user_facing
    return payload_marked_user_facing(payload)


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
        return wrap_bare_images_clickable(html_content)

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


class AgentEngine:
    def __init__(self, env):
        self.env = env
        # Estado de logging del turno: capturamos UNA correlación y el usuario
        # real una sola vez por turno y los reutilizamos en cada línea del
        # histórico. Durante el streaming SSE el `request` global puede quedar
        # desligado, así que NO dependemos de él en cada log (antes provocaba
        # entradas huérfanas como Administrator y un correlation_id por evento).
        self._turn_uid = env.uid
        self._turn_corr = None
        self._turn_step = 0
        self._turn_remote_ip = None

    def _begin_turn(self):
        """Snapshot one correlation id + end-user for the whole chat turn."""
        self._turn_uid = self.env.uid
        corr = None
        try:
            corr = ensure_turn_correlation(http_request)
        except Exception:
            corr = None
        self._turn_corr = corr or new_correlation_id()
        # Garantiza que TODO lector downstream (p. ej. create_verification del
        # safe_plan, que se ejecuta en cursor propio) vea la MISMA correlación
        # del turno. En el streaming SSE `ensure_turn_correlation` puede no
        # llegar a fijarla en el request y quedaría desincronizada con
        # `self._turn_corr` (filas execute_safe_plan sin código de operación).
        try:
            if http_request is not None:
                http_request.mcp_corr_id = self._turn_corr
                if not getattr(http_request, 'mcp_step_counter', None):
                    http_request.mcp_step_counter = {}
        except Exception:
            pass
        # Context survives nested Environment/cursor better than request attrs.
        self.env = self.env(context=dict(
            self.env.context or {},
            mcp_correlation_id=self._turn_corr,
        ))
        self._turn_step = 0
        from ..utils.mcp_logging import resolve_remote_ip
        self._turn_remote_ip = resolve_remote_ip()

    def _next_step(self):
        self._turn_step += 1
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
        kwargs.setdefault('correlation_id', self._turn_corr)
        kwargs.setdefault('source_channel', 'chatboo')
        kwargs.setdefault('remote_ip', self._turn_remote_ip)
        if not kwargs.get('step_seq'):
            kwargs['step_seq'] = self._next_step()
        try:
            self.env['ai.log'].sudo().create_log_entry(**kwargs)
        except Exception as exc:
            _logger.warning(
                'AgentEngine: could not write MCP log (%s): %s',
                kwargs.get('tool_name'), exc,
            )

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

    def _skill_args_policy(self, skill):
        from .skill_help import normalize_args_policy
        has_params = bool(
            (getattr(skill, 'param_schema', '') or '').strip()
            or (getattr(skill, 'arg_hint', '') or '').strip()
        )
        return normalize_args_policy(
            getattr(skill, 'args_policy', None),
            has_params=has_params,
        )

    def _emit_slash_help(self, meta, session_id, agent_code, provider,
                         provider_id, *, skill_code=None, rejected=False,
                         asking=False, reject_reason=''):
        """Deterministic help / reject / ask card. Never calls the LLM."""
        from .skill_help import build_slash_help_markdown
        card = build_slash_help_markdown(
            meta, rejected=rejected, reject_reason=reject_reason, asking=asking,
        )
        yield {'event': 'replace', 'content': card}
        if asking and skill_code:
            yield {
                'event': 'active_skill',
                'code': skill_code,
                'params': {'awaiting_args': True, 'state': {}},
            }
        else:
            yield {'event': 'active_skill', 'code': None, 'params': {}}
        yield self._done_event(
            session_id, agent_code=agent_code,
            provider=provider, provider_id=provider_id,
            skill_code=skill_code,
            local=True,
        )

    def _normalize_skill_params(self, skill, args, agent_code,
                                provider=None, provider_id=None):
        """LLM fallback for free-text args when deterministic parse leaves holes.

        Opt-in via ``param_schema``. Order:
        1. ``parse_skill_arguments`` + ``clave=valor`` + ordinals onto empty
           schema keys + ``enrich_params_with_dates`` (zero cost)
        2. If schema keys still missing and unbound prose remains → one
           short LLM JSON call
        3. LLM ``_reject`` is not a veto: merge with deterministic fill.
           Reject only when leftover prose still has no formal key
           (caller paints help; never falls through to ReAct)
        Without a formal schema, leftover text travels as ``arguments``.
        """
        raw = (args or '').strip()
        if not raw:
            return None
        # Help/?/ayuda: never call the hybrid LLM.
        from .skill_dates import skill_args_are_help
        from .skill_runtime import skill_args_unmapped
        if skill_args_are_help(raw):
            return {
                'arguments': raw,
                'periodo': raw,
                'lugar': raw,
            }
        policy = self._skill_args_policy(skill)
        if policy == 'none':
            return {'_skill_args_reject': True}
        schema_txt = (getattr(skill, 'param_schema', '') or '').strip()
        schema = None
        if schema_txt:
            try:
                schema = json.loads(schema_txt)
            except Exception:
                _logger.warning(
                    'Skill %s: param_schema is not valid JSON; ignored.',
                    getattr(skill, 'code', '?'),
                )
                schema = None
        if not isinstance(schema, dict) or not schema:
            return None

        from .skill_runtime import (
            _param_value_resolved,
            apply_schema_ordinals,
            build_param_extraction_prompt,
            enrich_params_with_dates,
            leftover_after_ordinals,
            merge_hybrid_params,
            parse_and_validate_params,
            parse_skill_arguments,
            schema_needs_ai_resolution,
        )

        params = parse_skill_arguments(raw)
        enrich_params_with_dates(params)
        params, bound_map = apply_schema_ordinals(params, schema, raw)
        enrich_params_with_dates(params)
        leftover = leftover_after_ordinals(raw, params, bound_map)
        # Deterministic-only extras we can already hand to the sandbox.
        # Temporal keys only win when canonical (YYYY-MM / YYYY-MM-DD) so a
        # leftover phrase never blocks the LLM from resolving it.
        det = {}
        for key in schema.keys():
            if _param_value_resolved(key, params.get(key)):
                det[key] = params[key]
        if not schema_needs_ai_resolution(
            params, schema, raw, leftover=leftover,
        ):
            if skill_args_unmapped(raw, det, schema, policy):
                return {'_skill_args_reject': True}
            return det or None

        prov = provider
        if prov is None:
            try:
                provs = self.env['ai.execution.engine'].get_providers_for_agent(
                    agent_code, provider_id=provider_id,
                )
                prov = provs[0] if provs else None
            except Exception as exc:
                _logger.debug('param norm: no provider for %s: %s', agent_code, exc)
                prov = None
        if prov is None:
            if skill_args_unmapped(raw, det, schema, policy):
                return {'_skill_args_reject': True}
            return det or None

        system_prompt, user_prompt = build_param_extraction_prompt(
            schema, raw, locale=self._resolve_user_locale(),
            arg_hint=(getattr(skill, 'arg_hint', None) or ''),
        )
        text = llm_json_completion(prov, system_prompt, user_prompt)
        norm = parse_and_validate_params(text, schema)
        if (
            not norm
            or (isinstance(norm, dict) and norm.get('_skill_args_reject'))
        ):
            _logger.info(
                'Skill %s: hybrid LLM returned nothing (raw=%r text=%r)',
                getattr(skill, 'code', '?'), raw[:80], (text or '')[:120],
            )
        merged = merge_hybrid_params(det, norm, schema, raw, policy)
        if isinstance(merged, dict) and merged.get('_skill_args_reject'):
            return merged
        _logger.info(
            'Skill %s: params via hybrid (det=%s ai=%s)',
            getattr(skill, 'code', '?'), det, {
                k: v for k, v in (norm or {}).items()
                if isinstance(norm, dict) and k not in det
                and not (isinstance(norm, dict) and norm.get('_skill_args_reject'))
            },
        )
        try:
            self._mcp_log(
                operation_type='read',
                tool_name='skill_param_hybrid',
                prompt_data={
                    'skill': getattr(skill, 'code', '?'),
                    'arguments': raw,
                    'det': det,
                    'ai': {
                        k: v for k, v in (norm or {}).items()
                        if isinstance(norm, dict) and k not in det
                        and not norm.get('_skill_args_reject')
                    } if isinstance(norm, dict) else {},
                    'merged': merged,
                },
                result_summary=(
                    'Skill param hybrid (%s): %s' % (
                        getattr(skill, 'code', '?'),
                        ', '.join(
                            '%s=%s' % (k, (merged or {}).get(k))
                            for k in schema.keys()
                            if (merged or {}).get(k) not in (None, '', [])
                        ) or 'empty',
                    )
                )[:480],
                request_type='tool',
            )
        except Exception:
            pass
        return merged

    def get_system_prompt(self, agent_code=None, screen_context_block=None,
                          user_message=None):
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

        screen_hint = ''
        if screen_context_block and str(screen_context_block).strip():
            screen_hint = '\n\n' + str(screen_context_block).strip()

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
            f"{screen_hint}{shadow_hint}"
        )
        prompt_content = f"{prompt_content}{runtime_data}"
        return {"role": "system", "content": prompt_content}

    def _domain_index_inject_enabled(self):
        from .domain_index import INJECT_ICP_KEY, icp_flag_enabled
        try:
            ICP = self.env['ir.config_parameter'].sudo()
            raw = ICP.get_param(INJECT_ICP_KEY, 'True')
            return icp_flag_enabled(raw, default=True)
        except Exception:
            return True

    def _domain_index_entries(self, user_locale=None):
        """Routing entries composed from ``ai.context`` discovery rows (DB)."""
        if 'ai.context' not in self.env:
            return []
        return self.env['ai.context'].sudo().get_discovery_entries(user_locale)

    def _domain_index_indexed_codes(self, user_locale=None):
        if 'ai.context' not in self.env:
            return set()
        return self.env['ai.context'].sudo().get_discovery_indexed_codes(user_locale)

    def _domain_index_inject_bodies(self, codes, user_locale=None):
        """Compile locale-aware context bodies for matched domain codes."""
        if not codes or 'ai.context' not in self.env:
            return ''
        Context = self.env['ai.context'].sudo()
        records = Context.browse()
        for code in codes:
            try:
                rec = Context.get_context_for_country(code, user_locale=user_locale)
            except Exception:
                rec = Context.search([
                    ('active', '=', True),
                    '|', ('code', '=', code), ('base_code', '=', code),
                ], limit=1)
            if rec:
                records |= rec
        if not records:
            return ''
        parts = Context.assemble_context_parts(
            records, user_locale=user_locale,
        )
        return '\n\n'.join(p for p in (parts or []) if p)

    def _domain_index_runtime_hint(self, user_message, user_locale=None):
        """Match + Historial IA + turn-scoped body injection (single flag).

        Domain hits load pack bodies (cap 1–2). ``api_server`` hits append a
        short post-catalogue hint and do not consume that budget.
        """
        if not user_message or not str(user_message).strip():
            return ''
        if not self._domain_index_inject_enabled():
            return ''
        from .domain_index import (
            DEFAULT_MAX_SERVICES,
            TARGET_KIND_API_SERVER,
            TARGET_KIND_DOMAIN,
            filter_entries_by_kind,
            format_inject_header,
            format_service_detect_hint,
            match_domains,
        )
        entries = self._domain_index_entries(user_locale=user_locale)
        if not entries:
            return ''
        msg = str(user_message)
        domain_entries = filter_entries_by_kind(entries, TARGET_KIND_DOMAIN)
        service_entries = filter_entries_by_kind(entries, TARGET_KIND_API_SERVER)
        result = match_domains(msg, domain_entries)
        service_result = match_domains(
            msg, service_entries, max_packs=DEFAULT_MAX_SERVICES,
        )
        codes = list(result.get('codes') or [])
        service_codes = list(service_result.get('codes') or [])
        elapsed_ms = (
            float(result.get('elapsed_ms') or 0.0)
            + float(service_result.get('elapsed_ms') or 0.0)
        )
        codes_txt = ', '.join(codes) if codes else '(none)'
        if not codes:
            domain_part = 'Domains detected: (none)'
            mode = 'none'
            body = ''
        else:
            body = self._domain_index_inject_bodies(codes, user_locale=user_locale)
            mode = 'injected' if body else 'inject_miss'
            domain_part = (
                'Domains injected: %s' % codes_txt
                if body else
                'Domains detected (no body): %s' % codes_txt
            )
        if service_codes:
            domain_part = '%s · Services detected: %s' % (
                domain_part, ', '.join(service_codes),
            )
            if mode == 'none':
                mode = 'service'
        summary = '%s · %.2f ms' % (domain_part, elapsed_ms)
        self._mcp_log(
            operation_type='read',
            tool_name='domain_index',
            request_type='system',
            user_prompt=msg[:480],
            prompt_data={
                'codes': codes,
                'service_codes': service_codes,
                'elapsed_ms': round(elapsed_ms, 3),
                'matches': result.get('matches') or [],
                'service_matches': service_result.get('matches') or [],
                'inject': True,
                'mode': mode,
                'body_chars': len(body or ''),
            },
            result_summary=summary[:480],
        )
        if codes or service_codes:
            _logger.info(
                'AgentEngine: domain_index mode=%s codes=%s services=%s '
                'elapsed_ms=%.2f',
                mode, codes, service_codes, elapsed_ms,
            )
        parts = []
        if body:
            parts.append(format_inject_header(codes, elapsed_ms) + body)
        service_hint = format_service_detect_hint(
            service_result.get('matches') or [],
        )
        if service_hint:
            parts.append(service_hint)
        return ''.join(parts)

    def _domain_index_catalog_hint(self):
        """Compact index listing when MCP has no user query yet."""
        if not self._domain_index_inject_enabled():
            return ''
        from .domain_index import format_index_catalog
        entries = self._domain_index_entries()
        return format_index_catalog(entries)

    def _domain_index_shadow_hint(self, user_message):
        """Backward-compatible alias."""
        return self._domain_index_runtime_hint(user_message)

    def get_tools_schema(self):
        """
        Obtiene todas las herramientas registradas en Odoo MCP y las convierte
        al formato de OpenAI/Anthropic Functions.
        """
        from ..controllers.mcp_decorators import get_registered_tools
        tools_dict = get_registered_tools()
        
        openai_tools = []
        for name, tool in tools_dict.items():
            openai_tools.append({
                "type": "function",
                "function": {
                    "name": name,
                    "description": tool.get("description", ""),
                    "parameters": tool.get("inputSchema", {})
                }
            })
        return openai_tools

    # ------------------------------------------------------------------
    # Slash commands (skills) — chatboo inference client
    # ------------------------------------------------------------------
    @staticmethod
    def _parse_slash_command(message):
        """Return (command, args_str) if message is a slash command, else None."""
        if not message:
            return None
        text = message.strip()
        if not text.startswith('/'):
            return None
        body = text[1:].strip()
        if not body:
            return None
        parts = body.split(None, 1)
        command = parts[0].strip()
        args = parts[1].strip() if len(parts) > 1 else ''
        return command, args

    def _skills_list_markdown(self, agent_code):
        skills = self.env['ai.skill'].list_for_agent(agent_code)
        lines = []
        if not skills:
            lines.append(_('No skills available for this agent.'))
        else:
            lines.append(_('**Available skills** (use `/<code> [arguments]`):'))
            lines.append('')
            for s in skills:
                lines.append('- `/%s` — %s' % (s['code'], s['description']))
        lines.extend([
            '',
            _('**Presentation axes** (token = value):'),
            '- `/painter-local` · `/painter-free` — who paints this turn',
            '- `/foot-verbose` · `/foot-laconic` — footer after local tables',
            '- `/show-table` · `/show-chart` — session layout (painter-local)',
        ])
        return '\n'.join(lines)

    def _resolve_skill(self, agent_code, command):
        skills = self.env['ai.skill'].get_for_agent(agent_code).filtered('active')

        def _fold(token):
            return (token or '').strip().lower().replace('_', '-')

        folded = _fold(command)
        match = skills.filtered(lambda s: s.invoke_code() == command)
        if not match:
            match = skills.filtered(
                lambda s: _fold(s.invoke_code()) == folded
                or _fold(s.code) == folded
            )
        return match[:1]

    def _resolve_done_meta(self, agent_code, provider=None, provider_id=None):
        """Modelo/proveedor/límite para eventos ``done`` (también sin ronda LLM)."""
        meta = {
            'model': '',
            'provider': '',
            'protocol': '',
            'context_limit': 0,
            'display_currency': 'USD',
        }
        try:
            if provider is not None:
                p = provider
            else:
                Engine = self.env['ai.execution.engine']
                providers = Engine.get_providers_for_agent(
                    agent_code, provider_id=provider_id,
                )
                p = providers[0] if providers else None
            if not p:
                return meta
            meta['model'] = (
                (p.model_id.name if getattr(p, 'model_id', None) else None)
                or p.model_name
                or p.name
                or ''
            )
            meta['provider'] = p.name or ''
            meta['protocol'] = getattr(p, 'protocol', None) or ''
            meta['context_limit'] = p.context_window or 0
            from .display_currency import get_display_currency
            meta['display_currency'] = get_display_currency(self.env)
        except Exception as exc:
            _logger.debug('done meta resolve failed: %s', exc)
        return meta

    def _done_event(
        self,
        session_id,
        agent_code=None,
        provider=None,
        provider_id=None,
        usage=None,
        sources=None,
        skill_code=None,
        records=None,
        local=False,
    ):
        """Evento ``done`` completo para que Chatboo pinte modelo/tokens.

        ``local=True``: tarjeta determinista (ayuda / ask / reject). No hay
        inferencia ni ocupación de contexto; Chatboo no la manda al histórico.
        """
        if local:
            return {
                'event': 'done',
                'session_id': session_id,
                'model': 'Chatboo',
                'provider': 'local',
                'protocol': '',
                'context_limit': 0,
                'display_currency': '',
                'usage': None,
                'sources': [],
                'records': [],
                'painter': '',
                'correlation_id': '',
                'local_ack': True,
            }
        meta = self._resolve_done_meta(
            agent_code, provider=provider, provider_id=provider_id,
        )
        model = meta.get('model') or ''
        if skill_code:
            model = (
                '%s · skill/%s' % (model, skill_code) if model
                else 'skill/%s' % skill_code
            )
        if usage is None:
            usage = {
                'prompt_tokens': 0,
                'completion_tokens': 0,
                'total_tokens': 0,
                'cost': 0,
            }
        elif provider is not None:
            try:
                usage = advertise_cost(
                    usage,
                    bool(getattr(provider, 'is_on_premise', False)),
                )
            except Exception:
                pass
        corr = getattr(self, '_turn_corr', None) or (
            (self.env.context or {}).get('mcp_correlation_id')
        )
        return {
            'event': 'done',
            'session_id': session_id,
            'model': model,
            'provider': meta.get('provider') or '',
            'protocol': meta.get('protocol') or '',
            'context_limit': meta.get('context_limit') or 0,
            'display_currency': meta.get('display_currency') or 'USD',
            'usage': usage,
            'sources': list(sources or []),
            'records': list(records or []),
            'painter': getattr(self, '_turn_painter', None) or '',
            'correlation_id': corr or '',
        }

    def run_stream(self, message, history, session_id, agent_code=None, provider=None, consumer_key=None, provider_id=None, prior_query_code=None, prior_query_data=None, screen_context_block=None, prior_active_skill_code=None, prior_active_skill_params=None, images=None, recall_images=None):
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
        """
        from ..models.ai_execution_engine import ProviderConnectionError

        # Un único hilo de histórico por turno (correlación + usuario real).
        self._begin_turn()
        # Canonical turn utterance for any consumer (glossary gate, formatting…).
        # Prefer an already-set context value; otherwise the engine message.
        _ctx = dict(self.env.context or {})
        if session_id:
            _ctx['chatboo_session_id'] = int(session_id)
        if not (_ctx.get('user_message') or '').strip():
            _ctx['user_message'] = message or ''
        if not isinstance(_ctx.get('file_label_by_id'), dict):
            _ctx['file_label_by_id'] = {}
        self.env = self.env(context=_ctx)

        Agent = self.env['ai.agent']
        Engine = self.env['ai.execution.engine']
        agent_code = Agent.resolve_inference_agent_code(agent_code, consumer_key=consumer_key)

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
                    return
                yield {'event': 'token', 'content': self._skills_list_markdown(agent_code)}
                yield self._done_event(
                    session_id,
                    agent_code=agent_code,
                    provider=provider,
                    provider_id=provider_id,
                )
                return
            from .formatting_mode_policy import (
                AXIS_COMMANDS,
                AXIS_FOOTMODE,
                AXIS_PAINTER,
                AXIS_SHOWMODE,
                PAINTER_FREE,
                _clear_legacy_session_sticky,
                _write_session_showmode,
            )
            if cmd.lower() in AXIS_COMMANDS:
                from .skill_dates import skill_args_are_help as _axis_help
                from .skill_help import builtin_slash_help_meta
                if _axis_help(args):
                    yield from self._emit_slash_help(
                        builtin_slash_help_meta(cmd.lower()),
                        session_id, agent_code, provider, provider_id,
                    )
                    return
                axis, value = AXIS_COMMANDS[cmd.lower()]
                try:
                    if session_id:
                        sess = self.env['chatboo.session'].browse(
                            int(session_id),
                        ).exists()
                        _clear_legacy_session_sticky(sess)
                        if axis == AXIS_SHOWMODE and sess:
                            _write_session_showmode(sess, value)
                except Exception:
                    pass
                ctx = dict(self.env.context or {})
                if axis == AXIS_PAINTER:
                    ctx['llm_remote_formatting_override'] = (value == PAINTER_FREE)
                    ctx['turn_painter'] = value
                    if value == PAINTER_FREE:
                        content = _(
                            'Painter painter-free for this turn only — the model '
                            'composes the bubble. Later messages inherit the provider '
                            'unless you prefix with `/painter-free`.'
                        )
                    else:
                        content = _(
                            'Painter painter-local for this turn only — Chatboo '
                            'composes tables/charts. Later messages inherit the '
                            'provider unless you prefix with `/painter-local`.'
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
                    return
            else:
                skill = self._resolve_skill(agent_code, cmd)
                if not skill:
                    content = _('No existe el skill `/%s`.') % cmd
                    content += '\n\n' + self._skills_list_markdown(agent_code)
                    yield {'event': 'token', 'content': content}
                    yield self._done_event(
                        session_id,
                        agent_code=agent_code,
                        provider=provider,
                        provider_id=provider_id,
                    )
                    return
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
                    return
                if not (args or '').strip() and _args_policy == 'ask':
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
                    return
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
                    return
                # Params: deterministic first; LLM only if param_schema + unresolved
                # free text (hybrid). No sticky session state.
                user_lang = self._resolve_user_locale()
                payload = skill.build_invocation_payload(user_locale=user_lang, arguments=args)

                if (skill.code_body or '').strip():
                    # Skill CON codigo: se resuelve server-side de forma determinista
                    # o painter-free entrega datos al LLM (one-shot, no sticky).
                    from .formatting_mode_policy import (
                        PAINTER_FREE,
                        PAINTER_LOCAL,
                        normalize_painter,
                    )
                    from .skill_runtime import (
                        bootstrap_skill_code_body,
                        presentation_from_bootstrap,
                        should_await_skill_args,
                        skill_state_for_await,
                        try_skill_fast_path,
                    )
                    skill_painter = normalize_painter(
                        getattr(skill, 'painter', None) or '',
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
                        skill_painter in (PAINTER_FREE, PAINTER_LOCAL)
                        and not (self.env.context or {}).get('turn_painter')
                    ):
                        self.env = self.env(context=dict(
                            self.env.context or {},
                            llm_remote_formatting_override=(
                                skill_painter == PAINTER_FREE and not _help_args
                            ),
                            turn_painter=(
                                None if _help_args else skill_painter
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
                            skill_code=slash, rejected=True,
                        )
                        return
                    # Slots pegajosos: el skill lee ``skill_state`` (vacío en
                    # una invocación nueva) y decide qué le falta todavía.
                    norm_params = dict(norm_params or {})
                    norm_params['skill_state'] = resumed_state
                    boot_diag = {}
                    bootstrap = bootstrap_skill_code_body(
                        self.env, skill.code_body, arguments=args,
                        skill_code=slash, extra_params=norm_params,
                        diag=boot_diag,
                    )
                    fp_diag = {}
                    fast = None
                    # Help cards always use fast-path HTML (even on painter-free).
                    if bootstrap is not None and (
                        skill_painter != PAINTER_FREE or _help_args
                    ):
                        fast = try_skill_fast_path(
                            self.env, bootstrap,
                            title=skill.name or slash,
                            code=skill.code_body, arguments=args,
                            skill_code=slash, extra_params=norm_params,
                            diag=fp_diag,
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
                        return
                    # painter-free: hand tabular data to the LLM (it owns the UI).
                    # Exception: deterministic cards (help/?, soft errors) that
                    # already ship formatted_text + __return_direct__ without
                    # tabular rows — no LLM (same as painter-local fast-path).
                    if (
                        skill_painter == PAINTER_FREE
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
                            return
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
                                    '\nESQUELETO OBLIGATORIO (`report_outline` '
                                    'del JSON), en este orden y con estos '
                                    'títulos exactos:\n%s\n'
                                ) % '\n'.join(
                                    '- %s' % h for h in _outline
                                )
                            if isinstance(_closing, str) and _closing.strip():
                                _contract += (
                                    '\nCIERRE OBLIGATORIO: la ÚLTIMA sección '
                                    'del informe debe incluir esta línea '
                                    '(cópiala tal cual si ya viene completa; '
                                    'nunca la omitas):\n`%s`\n'
                                ) % _closing.strip()
                            message = (
                                'El usuario ha invocado el skill `/%s` en modo '
                                'informe (report, solo este turno).\n'
                                'NEW REPORT this turn: write the complete '
                                'narrative now. Do not tell the user the report '
                                'is already in a previous message. History stubs '
                                'forbid reprinting table rows, not this outline.\n'
                                '%s\n'
                                'Tú compones toda la interfaz de respuesta: '
                                'Markdown, HTML, tablas/gráficos nativos de '
                                'Chatboo, o una mezcla. Nada está prohibido. '
                                'Si el JSON trae `formatted_text`, ese HTML '
                                'AÚN no se ha mostrado: incrústalo si quieres '
                                'tablas/gráficos nativos (ya lleva '
                                'data-chatboo-dataset).\n\n'
                                'ABRE el informe con UN solo H1 (`# …`) '
                                'redactado a partir del periodo/label del JSON '
                                '(e.g. last 12 months, YTD, a year or a range). '
                                'No uses `PERIOD=`. '
                                'Justo debajo del H1, si el JSON trae `company`, '
                                'copia ese nombre TAL CUAL (sin traducir, sin '
                                'etiqueta Empresa/Company).\n\n'
                                'Procedimiento del skill:\n\n%s\n\n'
                                'Datos deterministas del skill (ÚNICAS cifras '
                                'válidas; no inventes):\n```json\n%s\n```\n\n'
                                'Escribe el informe. ESQUELETO FIJO: no omitas '
                                'ninguna sección. Cita cifras del JSON.'
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
                                    boot_diag.get('bootstrap_error'),
                                ),
                            }
                            yield self._done_event(
                                session_id, agent_code=agent_code,
                                provider=provider, provider_id=provider_id,
                                skill_code=slash,
                            )
                            return
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
                            return
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
                        # CRUD propose_steps: mismo toast que propose_safe_operations
                        if fast.get('verification_id'):
                            yield {
                                'event': 'verification',
                                'verification_id': fast['verification_id'],
                                'title': fast.get('title') or skill.name or '',
                                'plan': fast.get('plan') or [],
                                'danger_level': fast.get('danger_level') or 'medium',
                            }
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
                        )
                        return
                    else:
                        # No se pudo resolver server-side -> ERROR CLARO, sin LLM.
                        reason = (
                            boot_diag.get('bootstrap_error')
                            or fp_diag.get('reason')
                            or 'desconocido'
                        )
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
                            ) % (slash, reason),
                        }
                        yield self._done_event(
                            session_id, agent_code=agent_code,
                            provider=provider, provider_id=provider_id,
                            skill_code=slash,
                        )
                        return

                else:
                    # Skill solo-prompt (sin code_body): el LLM ejecuta el procedimiento.
                    message = (
                        'El usuario ha invocado el skill `/%s`. Sigue su '
                        'procedimiento al pie de la letra:\n\n%s'
                        % (slash, payload)
                    )

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
            providers = Engine.get_providers_for_agent(
                agent_code, provider_id=provider_id,
            )
        except Exception as exc:
            yield {
                'event': 'token',
                'content': '\n\n🛑 %s\n' % str(exc),
            }
            yield self._done_event(
                session_id,
                agent_code=agent_code,
                provider=provider,
                provider_id=provider_id,
            )
            return

        # Build the provider cascade (admin-managed links; readable via sudo in engine)
        failovers = Engine.get_failovers(agent_code)

        # Determine the list of providers to try
        if failovers:
            cascade_providers = list(failovers.mapped('provider_id'))
        else:
            # Auto-assign case: providers without explicit failovers
            cascade_providers = list(providers)

        # Selección de la UI: probar el proveedor elegido PRIMERO y dejar el
        # resto de la cadena como failover (elegir ≠ desactivar el failover).
        # Solo si el elegido pertenece a la cadena del agente (si no, p. ej.
        # localStorage obsoleto, se ignora: nunca se usa un proveedor ajeno).
        if provider_id:
            selected = self.env['ai.provider'].browse(provider_id).exists()
            if selected and selected.id in [p.id for p in cascade_providers]:
                cascade_providers = [selected] + [
                    p for p in cascade_providers if p.id != selected.id
                ]

        last_error = None
        failed_provider = None
        provider_errors = []
        for idx, current in enumerate(cascade_providers):
            if idx > 0 and failed_provider:
                Engine.log_provider_failover(
                    agent_code, failed_provider, current, last_error,
                    user_id=self._turn_uid,
                    correlation_id=self._turn_corr,
                    step_seq=self._next_step(),
                    source_channel='chatboo',
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
            except ProviderConnectionError as exc:
                last_error = exc
                failed_provider = current
                provider_errors.append((current.name, str(exc)))
                _logger.warning(
                    'AgentEngine failover: agent=%s provider=%s failed: %s',
                    agent_code, current.name, exc,
                )
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

    def _dataset_cache_max_bytes(self):
        """Tope en BYTES serializados del cache de dataset (Nivel 2), configurable
        por parámetro de sistema. 0 o negativo = sin límite. Ante cualquier fallo
        cae al default del módulo."""
        try:
            return int(self.env['ir.config_parameter'].sudo().get_param(
                'pns_ai_mcp.dataset_cache_max_bytes', AGENT_DATASET_CACHE_MAX_BYTES))
        except (TypeError, ValueError):
            return AGENT_DATASET_CACHE_MAX_BYTES

    @staticmethod
    def _estimate_tokens(text):
        # Heurística barata (~4 caracteres por token); no usamos el tokenizer real
        # del modelo, solo necesitamos una cota razonable para recortar historial.
        if not text:
            return 0
        return int(len(str(text)) / 4) + 1

    def _fit_history_to_context(self, system_msg, clean_history, message, tools, context_window):
        """Devuelve el subconjunto MÁS RECIENTE del historial que cabe en la ventana.

        Mantiene fijos system prompt + esquema de herramientas + mensaje nuevo y
        descarta los turnos más antiguos como unidades completas (nunca deja un
        prompt/respuesta a medias). Garantiza que el historial resultante empieza
        por un turno de usuario, para no dejar respuestas/tools huérfanas.
        """
        if not context_window or context_window <= 0:
            return list(clean_history)

        RESPONSE_RESERVE = int(getattr(self, '_gen_max_tokens', None) or 4096)
        SAFETY = 512
        fixed = self._estimate_tokens(
            system_msg.get("content") if isinstance(system_msg, dict) else system_msg
        )
        try:
            if tools:
                fixed += self._estimate_tokens(json.dumps(tools, ensure_ascii=False))
        except Exception:
            pass
        fixed += self._estimate_tokens(message)

        budget = context_window - RESPONSE_RESERVE - SAFETY - fixed
        if budget <= 0:
            # Ni siquiera el contenido fijo cabe; enviamos sin historial (si acaso,
            # el proveedor dará un error claro de desbordamiento).
            return []

        kept_rev = []
        running = 0
        for m in reversed(clean_history):
            t = self._estimate_tokens(m.get("content"))
            if m.get("tool_calls"):
                try:
                    t += self._estimate_tokens(json.dumps(m.get("tool_calls"), ensure_ascii=False))
                except Exception:
                    pass
            if running + t > budget:
                break
            running += t
            kept_rev.append(m)

        kept = list(reversed(kept_rev))
        # Coherencia: el historial debe empezar por un turno de usuario.
        while kept and kept[0].get("role") != "user":
            kept.pop(0)
        return kept

    @staticmethod
    def _coalesce_openai_system(messages):
        """Fold every ``system`` message into a single leading one.

        Strict OpenAI-compatible servers (vLLM / OVH Kepler, some Qwen chat
        templates) reject a ``system`` message that is not the first one
        ("System message must be at the beginning"). We inject turn-specific
        system hints (prior-query reuse, screen context) after the history for
        salience — fine for OpenAI/OpenRouter, but it breaks vLLM. Here we join
        all system contents in order into one leading system message and keep
        every non-system message untouched. Does not mutate the input list.
        """
        system_parts = []
        rest = []
        for m in messages:
            if m.get("role") == "system":
                content = m.get("content") or ""
                if content:
                    system_parts.append(content)
            else:
                rest.append(m)
        if not system_parts:
            return list(messages)
        return [{"role": "system", "content": "\n\n".join(system_parts)}] + rest

    def _run_stream_with_provider(self, message, history, session_id, agent_code, provider, prior_query_code=None, prior_query_data=None, screen_context_block=None, images=None, recall_images=None):
        """Single-provider ReAct stream; raises ProviderConnectionError on LLM connection failure."""
        from ..models.ai_execution_engine import ProviderConnectionError

        engine = self  # alias para el DummyController anidado (log del turno)
        try:
            from .artifact_export import (
                is_refused_export,
                REFUSED_EXPORT_REPLY,
            )
        except Exception:
            is_refused_export = None
            REFUSED_EXPORT_REPLY = ''
        try:
            from .artifact_export import turn_export_utterance
            _orig = turn_export_utterance(self.env, message)
        except Exception:
            _orig = (self.env.context or {}).get('user_message') or message
        if is_refused_export and is_refused_export(_orig):
            yield {
                'event': 'replace',
                'content': _(REFUSED_EXPORT_REPLY),
            }
            yield self._done_event(session_id, local=True)
            return
        # Dataset del turno: empieza con el cache de sesión y se actualiza tras
        # cada RelaxAICode exitosa, para que la 2.ª llamada (pijama/estilo) pueda
        # pedir raw_data/previous_result cuando el código lo referencia (AST).
        turn_query_data = list(prior_query_data) if prior_query_data else None
        try:
            from .session_download import file_labels_from_mapping
            _labels = (self.env.context or {}).get('file_label_by_id')
            if isinstance(_labels, dict) and turn_query_data:
                file_labels_from_mapping(turn_query_data, _labels)
        except Exception:
            pass
        turn_safe_plan_steps = None
        # Anti-eco: huellas de tablas ya mostradas en historial assistant.
        # Las regeneradas este turno (tools) se permiten aunque coincidan.
        from .response_anti_echo import (
            code_references_reuse_names,
            extract_dataset_fingerprints,
            fingerprints_from_history,
            strip_echoed_table_blocks,
        )
        prior_table_fps = set()
        turn_table_fps = set()
        model_name = (provider.model_id.name if provider.model_id else None) or provider.model_name or "gpt-4o-mini"
        
        endpoint = provider.endpoint or ""
        if endpoint and not endpoint.startswith("http"):
            endpoint = "https://" + endpoint

        # El join agente↔provider (ai.agent.provider) aporta el tuning de
        # conexión por pareja (timeouts, fallback) y la política ReAct del
        # agente. Puede no existir (proveedor único autoseleccionado): en ese
        # caso el recordset vacío devuelve 0/False y se usan los defaults.
        agent = self.env['ai.agent'].search([('code', '=', agent_code)], limit=1)
        link = agent.sudo().provider_ids.filtered(
            lambda l: l.provider_id.id == provider.id,
        )[:1]
        remote_override = (self.env.context or {}).get(
            'llm_remote_formatting_override', None,
        )
        # Prefer the original user_message in env.context (slash-stripped
        # engine `message` may drop /painter-*); fall back to `message`.
        try:
            from .formatting_mode_policy import (
                AXIS_FOOTMODE,
                AXIS_PAINTER,
                FOOT_LACONIC,
                PAINTER_FREE,
                parse_axis_slash,
                resolve_footmode,
                resolve_painter,
            )
            orig_prompt = (self.env.context or {}).get('user_message') or message
            axis, axis_value, _remainder = parse_axis_slash(orig_prompt)
            ctx = self.env.context or {}
            turn_painter = ctx.get('turn_painter')
            turn_footmode = ctx.get('turn_footmode')
            if axis == AXIS_PAINTER and not turn_painter:
                turn_painter = axis_value
            if axis == AXIS_FOOTMODE and not turn_footmode:
                turn_footmode = axis_value
            painter = resolve_painter(
                turn_value=turn_painter,
                provider_value=getattr(provider, 'painter', None),
                explicit=remote_override,
            )
            remote_llm_format = painter == PAINTER_FREE
            footmode = resolve_footmode(
                turn_value=turn_footmode,
                provider_value=getattr(provider, 'footmode', None),
            )
        except Exception:
            remote_llm_format = bool(remote_override) if remote_override is not None else False
            painter = 'painter-free' if remote_llm_format else 'painter-local'
            footmode = getattr(provider, 'footmode', None) or 'foot-verbose'
            FOOT_LACONIC = 'foot-laconic'
        if remote_llm_format:
            _logger.info(
                'agent_engine: painter-free ON (session=%s)',
                session_id,
            )
        # painter-free narratives need more completion budget.
        self._gen_max_tokens = 8192 if remote_llm_format else 4096
        self._turn_painter = painter
        self._turn_formatting_mode = painter
        # footmode only applies under painter-local (suspended in painter-free).
        skip_table_footer = (not remote_llm_format) and (footmode == FOOT_LACONIC)

        config = {
            "protocol": provider.protocol,
            "api_key": provider._api_key_for_inference(),
            "model_name": model_name,
            "temperature": provider.temperature or 0.7,
            "endpoint": endpoint,
            # Timeouts por pareja agente↔provider (join). Cualquier valor <= 0
            # (0, -1, vacío) usa el valor por defecto del módulo. Permite que un
            # enlace LOCAL lento dispare la cascada antes, sin penalizar a los
            # proveedores remotos.
            "idle_timeout": (
                link.llm_idle_timeout
                if (link.llm_idle_timeout or 0) > 0
                else LLM_STREAM_READ_TIMEOUT
            ),
            "round_timeout": (
                link.llm_round_timeout
                if (link.llm_round_timeout or 0) > 0
                else LLM_ROUND_WALL_TIMEOUT
            ),
            "skip_sync_fallback": bool(link.skip_sync_fallback),
        }
        
        # Arquitectura (docs/dos_credenciales_api.md): Chatboo/internal infiere aquí
        # in-process; NO reentra en /mcp ni usa ai.mcp.user.mcp_api_key_hash.
        # Las tools van vía tool_func(DummyController(self.env), ...).
        # ai.provider.api_key sí se usa (HTTP al LLM), leída en _api_key_for_inference().
        # X-Mcp-Token del usuario no se propaga al LLM: secreto sin uso en este camino.

        # 2. Preparar Mensajes (Inyección del System Prompt)
        system_msg = self.get_system_prompt(
            agent_code=agent_code,
            screen_context_block=screen_context_block,
            user_message=(
                (self.env.context or {}).get('user_message') or message
            ),
        )

        # 3. Cargar Herramientas
        tools = self.get_tools_schema()

        # Recorte coherente del historial para no desbordar la ventana de contexto
        # del proveedor: system prompt + bundle + herramientas + mensaje nuevo son
        # FIJOS (no se recortan); del historial se descartan los turnos MÁS ANTIGUOS
        # como unidades completas (nunca se corta un prompt o respuesta a medias).
        # Antes de podar por tokens: sustituir artefactos on-screen (tablas HTML)
        # por stubs. La poda por antigüedad no basta — lo gordo es lo reciente.
        from .history_compact import compact_history_for_llm, history_char_count
        incoming_history = [m for m in (history or []) if m.get("role") != "system"]
        clean_history = compact_history_for_llm(incoming_history)
        _in_chars = history_char_count(incoming_history)
        _out_chars = history_char_count(clean_history)
        if _in_chars > _out_chars + 500:
            _logger.info(
                "AgentEngine: historial compactado a stubs "
                "(%s → %s chars, %s msgs)",
                _in_chars, _out_chars, len(clean_history),
            )
        kept_history = self._fit_history_to_context(
            system_msg, clean_history, message, tools, provider.context_window or 0,
        )

        messages = [system_msg]
        messages.extend(kept_history)
        if remote_llm_format:
            # Alternative to local HTML tables: explicit contract for this provider.
            from .mcp_tool_payload import REMOTE_FORMAT_SYSTEM_HINT
            messages.append({
                "role": "system",
                "content": REMOTE_FORMAT_SYSTEM_HINT,
            })
        try:
            prior_table_fps = fingerprints_from_history(kept_history)
        except Exception:
            prior_table_fps = set()
        # Ancla de reutilización: el historial que manda el navegador solo lleva
        # el HTML renderizado, NO el código que lo generó, así que sin esto el
        # modelo reescribe la consulta desde cero en cada turno (fuente principal
        # de variabilidad en los "mismo listado / reordena"). Le devolvemos su
        # última consulta exitosa como pista para que la ADAPTE en vez de
        # reinventarla. Va como 'system' (los proveedores Anthropic lo funden en
        # el system raíz; los OpenAI-compat lo aceptan a media lista).
        # Reutilización entre turnos, EXCLUYENTE (nunca las dos a la vez) para
        # eliminar el doble disparo:
        #   - Nivel 2 (datos frescos): las FILAS del turno anterior están
        #     disponibles SOLO si el código AST referencia previous_result/raw_data
        #     (o el LLM las pasa en args). No se auto-inyectan en toda RelaxAICode.
        #   - Nivel 1 (fallback): SOLO si no hay dataset fresco (caducó o no cupo),
        #     se da el CÓDIGO de la última consulta como receta a adaptar.
        # El historial que manda el navegador solo lleva el HTML renderizado, no el
        # código ni los datos, así que sin esto el modelo reinventa la consulta en
        # cada turno (fuente principal de variabilidad en los "mismo listado").
        if prior_query_data:
            messages.append({
                "role": "system",
                "content": (
                    "[DATOS REUTILIZABLES] Las FILAS del último resultado de esta "
                    "conversación están disponibles para reformateo: pásalas en "
                    "relaxaicode como `previous_result` (dict con 'data') "
                    "o referencia `previous_result` / `raw_data` en el código "
                    "(el servidor las inyecta entonces). Si el usuario pide "
                    "REFORMATEAR, REORDENAR o RE-PRESENTAR EL MISMO listado "
                    "(mismo sujeto y mismo alcance; p. ej. \"mismo listado\", "
                    "\"ordena por…\", \"ahora con negritas\", \"efecto pijama\"), "
                    "transforma directamente `raw_data` (p. ej. `result = "
                    "{'data': sorted(raw_data, key=...)}`): es más rápido, no "
                    "gasta tokens y NO puede cambiar el conjunto de filas.\n\n"
                    "SALVAGUARDA DE ALCANCE — si la nueva petición CAMBIA de "
                    "sujeto/entidad, o AMPLÍA el alcance / pide cobertura TOTAL "
                    "(cuantificadores tipo \"todos/todas\", \"completo\", \"sin "
                    "límite\", \"listado completo\"), IGNORA estos datos y "
                    "RE-CONSULTA la BD desde cero: este dataset es solo el "
                    "subconjunto del turno anterior y usarlo dejaría fuera filas. "
                    "NUNCA pegues en la burbuja el HTML/tabla de un turno anterior."
                ),
            })
        elif prior_query_code and str(prior_query_code).strip():
            messages.append({
                "role": "system",
                "content": (
                    "[CONSULTA REUTILIZABLE] En un turno ANTERIOR de esta misma "
                    "conversación, esta consulta de datos se ejecutó con ÉXITO "
                    "(relaxaicode):\n\n```python\n%s\n```\n\n"
                    "ÚSALA SOLO si el usuario pide REFORMATEAR, REORDENAR o "
                    "RE-PRESENTAR EL MISMO conjunto (mismo sujeto y mismo alcance; "
                    "p. ej. \"mismo listado\", \"ordena por…\", \"ahora con "
                    "negritas\", \"efecto pijama\"): reutiliza esta consulta como "
                    "base y cambia SOLO lo pedido (orden, columnas, estilo), sin "
                    "tocar los FILTROS ni reinventarla, respetando el MISMO conjunto "
                    "de filas (mismo recuento) que ya obtuviste.\n\n"
                    "SALVAGUARDA DE ALCANCE — NO reutilices esta consulta (re-"
                    "derívala desde cero) si la nueva petición (a) CAMBIA de "
                    "sujeto/entidad respecto a la anterior, o (b) AMPLÍA el alcance "
                    "o pide cobertura TOTAL (cuantificadores tipo \"todos/todas\", "
                    "\"completo\", \"sin límite\", \"listado completo\"). Los FILTROS "
                    "cacheados pueden ser MÁS restrictivos de lo que la nueva "
                    "petición necesita (un join o una condición incidental de la "
                    "pregunta anterior) y encogerían el resultado en silencio. Ante "
                    "la duda entre reutilizar y ampliar, AMPLÍA: re-deriva sin "
                    "heredar filtros."
                ) % (str(prior_query_code).strip(),),
            })
        if screen_context_block and str(screen_context_block).strip():
            # Turn-specific focus: inject immediately before the user message so
            # the model sees it after history (more salient than the tail of a
            # huge cached system prompt).
            messages.append({
                "role": "system",
                "content": str(screen_context_block).strip(),
            })
        if recall_images:
            # Recuerdo acotado (1c): reenviamos, como mensaje de usuario aparte
            # JUSTO antes del turno actual, las últimas imágenes ya vistas en la
            # conversación (reescaladas y con tope de nº por el worker). Imita el
            # "recuerda la captura" de ChatGPT/Claude (modelos sin estado: la
            # imagen se ve porque se REENVÍA). No entran en el historial
            # persistido: se recomponen cada turno desde los ir.attachment.
            recall_parts = [{
                "type": "text",
                "text": (
                    "[Imágenes de turnos anteriores de esta conversación, "
                    "reenviadas para que puedas referirte a ellas:]"
                ),
            }]
            for img in recall_images:
                if not img:
                    continue
                url = img if str(img).startswith("data:") else "data:image/png;base64,%s" % img
                recall_parts.append({"type": "image_url", "image_url": {"url": url}})
            if len(recall_parts) > 1:
                messages.append({"role": "user", "content": recall_parts})

        _session_file_protocol = ''
        try:
            from .artifact_export import (
                requested_named_format,
                SESSION_FILE_PROTOCOL,
                SESSION_FILE_REPORT_NOTE,
            )
            if requested_named_format(_orig):
                _rc = getattr(self, '_report_contract', None) or {}
                if isinstance(_rc, dict) and _rc.get('report_outline'):
                    _session_file_protocol = SESSION_FILE_REPORT_NOTE
                else:
                    _session_file_protocol = SESSION_FILE_PROTOCOL
        except Exception:
            _session_file_protocol = ''

        if images:
            # Multimodal turn: send the image(s) inline as OpenAI-style
            # content-parts alongside the text. The OpenAI-compatible driver
            # forwards `messages` verbatim, so a vision model receives them
            # natively. Images ride ONLY in this turn's request; they are never
            # persisted into the session history (anti-overflow doctrine).
            parts = []
            if message:
                parts.append({"type": "text", "text": message})
            if _session_file_protocol:
                parts.append({"type": "text", "text": _session_file_protocol})
            for img in images:
                if not img:
                    continue
                url = img if str(img).startswith("data:") else "data:image/png;base64,%s" % img
                parts.append({"type": "image_url", "image_url": {"url": url}})
            messages.append({"role": "user", "content": parts})
        elif _session_file_protocol:
            messages.append({
                "role": "user",
                "content": (message or '') + '\n\n' + _session_file_protocol,
            })
        else:
            messages.append({"role": "user", "content": message})

        if len(kept_history) < len(clean_history):
            dropped = len(clean_history) - len(kept_history)
            _logger.info(
                "AgentEngine: historial recortado para ajustar al contexto "
                "(%s mensaje(s) antiguo(s) descartado(s); ventana=%s)",
                dropped, provider.context_window or 0,
            )
            yield {"event": "status", "message": "Ajustando el historial al contexto (se descartan turnos antiguos)…"}

        yield {"event": "status", "message": f"Conectando con {model_name} (Tools activas: {len(tools)})..."}

        # --- BUCLE REACT NATIVO ---
        import urllib.request
        import urllib.error
        
        headers = {
            "Content-Type": "application/json"
        }
        
        # Autorización
        if provider.protocol == 'anthropic':
            if config["api_key"]: headers['x-api-key'] = config["api_key"]
            headers['anthropic-version'] = '2023-06-01'
            headers['anthropic-beta'] = 'prompt-caching-2024-07-31'
        elif config["api_key"]:
            headers['Authorization'] = f"Bearer {config['api_key']}"
            
        if "extra_headers" in config:
            headers.update(config["extra_headers"])

        # Política del bucle ReAct: vive en el agente (resuelto arriba). Si no
        # hay agente o el valor es <= 0, usa el default (10).
        MAX_ROUNDS = (agent.max_agent_rounds if (agent and (agent.max_agent_rounds or 0) > 0) else 10)
        round_n = 0
        # Red de seguridad para auto-corrección: si el modelo agota las rondas
        # reintentando código erróneo sin dar respuesta final, mostramos el último
        # error técnico en vez de dejar el chat en blanco.
        finished_with_answer = False
        export_attached = False
        export_chips = []
        export_refused_tokens = []
        stop_after_direct = False
        export_clip_data = None
        export_meta_nudged = False
        export_meta_nudge_round = 0
        last_retry_error = None
        agent_started = time.monotonic()
        # Tokens de la ronda LLM en curso (se resetea cada vuelta).
        usage_info = {}
        # Suma de todas las rondas del turno (pie + histórico diario).
        turn_usage = {}
        last_round_total = 0
        # Fuentes externas consultadas: dominios de fetch_url y servidores API.
        # Sirve tanto para pasos PROPUESTOS (tool_args de propose_safe_operations,
        # auto-confirmados) como para pasos YA EJECUTADOS que se recuperan luego con
        # get_safe_operation_status (confirmación manual). Ambos comparten la misma
        # forma: dicts con 'op' + 'url' (fetch_url) o 'server'/'tool' (api_call).
        external_sources = set()

        def _collect_sources(steps):
            """Añade a external_sources las fuentes de una lista de pasos/resultados."""
            from .skill_runtime import collect_external_sources
            for _src in collect_external_sources(steps):
                external_sources.add(_src)

        # Registros Odoo referenciados en el turno (para pintarlos como enlaces
        # clicables en Chatboo). DETERMINISTA: salen de resultados REALES de
        # herramientas —filas de relaxaicode con id+__model y operaciones
        # CRUD confirmadas del safe plan—, NO de que el modelo los cite bien.
        collected_records = []
        _records_seen = set()
        _RECORDS_MAX = 50
        # Candado de entrega de registros (sin léxico): payload tabulable del
        # turno, si ya se hizo replace con tabla, y nº de RelaxAICode exitosos.
        last_tabulable_payload = None
        direct_formatted = None
        table_already_delivered = False
        relaxai_success_count = 0
        tools_invoked_count = 0
        links_off_turn = False
        # Multi-tool presentable results (same user turn) — see
        # docs/decisions/turn_presentation_basket.md
        turn_presentation_basket = []
        # First complete artifact of the turn (never replaced by a later probe).
        # See docs/decisions/primary_artifact.md
        primary_artifact = None

        def _absorb_export_result(_ex):
            nonlocal export_chips, export_refused_tokens
            if not isinstance(_ex, dict):
                return []
            chips = []
            try:
                from .artifact_export import export_result_chips
                chips = export_result_chips(_ex)
            except Exception:
                chips = []
            if not chips:
                raw_chips = _ex.get('chips')
                if isinstance(raw_chips, list):
                    chips = [
                        c for c in raw_chips
                        if isinstance(c, dict) and (c.get('url') or c.get('name'))
                    ]
                else:
                    chip = _ex.get('chip')
                    if isinstance(chip, dict) and (
                        chip.get('url') or chip.get('name')
                    ):
                        chips = [chip]
            for chip in chips:
                export_chips.append(chip)
            tokens = _ex.get('refused_tokens')
            if isinstance(tokens, (list, tuple)) and tokens:
                export_refused_tokens = list(tokens)
            return chips

        def _harvest_file_labels(*objs):
            labels = (self.env.context or {}).get('file_label_by_id')
            if not isinstance(labels, dict):
                return
            try:
                from .session_download import file_labels_from_mapping
                for obj in objs:
                    if obj is not None:
                        file_labels_from_mapping(obj, labels)
            except Exception:
                pass

        def _absorb_plan_downloads(steps):
            """Session chips from fetch_url/api_call; hide listing tables."""
            nonlocal export_chips, export_attached, direct_formatted
            nonlocal stop_after_direct
            try:
                from .session_download import (
                    collect_download_chips,
                    file_labels_from_steps,
                )
                labels = (self.env.context or {}).get('file_label_by_id')
                if isinstance(labels, dict):
                    file_labels_from_steps(steps, labels)
                chips = collect_download_chips(steps)
            except Exception:
                chips = []
            added = []
            for chip in chips:
                if isinstance(chip, dict) and (chip.get('url') or chip.get('name')):
                    export_chips.append(chip)
                    added.append(chip)
            if not added:
                return False
            export_attached = True
            try:
                from .artifact_export import wants_on_screen_blocks
                _show = wants_on_screen_blocks(
                    primary_artifact or last_tabulable_payload,
                )
            except Exception:
                _show = False
            if _show:
                return False
            direct_formatted = ''
            stop_after_direct = True
            return True

        def _stamp_refused_note():
            nonlocal direct_formatted
            if not export_chips or not export_refused_tokens:
                return
            try:
                from .artifact_export import merge_refused_note
                direct_formatted = merge_refused_note(
                    direct_formatted,
                    export_refused_tokens,
                    note=_(
                        'These file types are not available as a session download: %s. I can send PDF, Excel, Word, text, Markdown, or HTML.'
                    ),
                )
            except Exception:
                pass

        def _payload_for_screen(payload=None):
            """Stamp report_outline onto the payload used for hide/export.

            Lives outside the ReAct loop: a no-tool final answer (skill
            report) still calls this after ``while``, and a loop-local
            ``def`` is an UnboundLocalError.
            """
            try:
                from .artifact_export import payload_has_report_outline
            except Exception:
                payload_has_report_outline = lambda *_a, **_k: False
            outline = None
            rtp = getattr(self, '_report_tables_payload', None)
            if payload_has_report_outline(rtp):
                outline = rtp.get('report_outline')
            else:
                rc = getattr(self, '_report_contract', None) or {}
                if isinstance(rc, dict) and rc.get('report_outline'):
                    outline = rc.get('report_outline')
            if payload_has_report_outline(payload) or not outline:
                return payload
            if isinstance(payload, dict):
                out = dict(payload)
                out['report_outline'] = outline
                return out
            return {'report_outline': outline}

        def _add_record(model, rec_id, name=None, role=None):
            try:
                rec_id = int(rec_id)
            except (TypeError, ValueError):
                return
            # Validar contra el registro: descarta columnas espurias llamadas
            # 'model' que no son un modelo técnico real (p.ej. modelo de vehículo).
            if not model or not isinstance(model, str) or model not in self.env:
                return
            key = (model, rec_id)
            if key in _records_seen or len(collected_records) >= _RECORDS_MAX:
                return
            _records_seen.add(key)
            _nm = name if (name and isinstance(name, str)) else ('%s #%s' % (model, rec_id))
            rec = {'model': model, 'id': rec_id, 'name': _nm[:120]}
            if role:
                rec['role'] = role
            collected_records.append(rec)

        def _collect_records_steps(steps):
            """CRUD results: cite the document header, not a line or catalog row."""
            try:
                from .record_cite import resolve_document_target
            except Exception:
                resolve_document_target = None
            for _s in (steps or []):
                if not isinstance(_s, dict) or _s.get('success') is False:
                    continue
                _model = _s.get('model')
                _name = _s.get('name')
                _rids = []
                if isinstance(_s.get('id'), int):
                    _rids.append(_s.get('id'))
                if isinstance(_s.get('new_id'), int):
                    _rids.append(_s.get('new_id'))
                if isinstance(_s.get('ids'), list):
                    _rids.extend(_s.get('ids'))
                if resolve_document_target is None:
                    continue
                for _i in _rids:
                    tgt = resolve_document_target(_model, _i, env=self.env)
                    if not tgt:
                        continue
                    _lbl = _name if _model == tgt[0] else None
                    _add_record(tgt[0], tgt[1], _lbl, role='document')

        from ..controllers.mcp_decorators import get_tool_function
        # Assistant/tool messages of THIS turn only (history stays below).
        _turn_loop_from = len(messages)
        
        while round_n < MAX_ROUNDS:
            if time.monotonic() - agent_started > LLM_AGENT_WALL_TIMEOUT:
                raise ProviderConnectionError(
                    _('Maximum response time exceeded (%ss). Please try again.')
                    % LLM_AGENT_WALL_TIMEOUT
                )
            round_n += 1
            usage_info = {}
            yield {"event": "status", "message": _("Thinking (round %s)…") % round_n}
            round_started = time.monotonic()
            
            # Formatear payload según el tipo de proveedor
            if config["protocol"] == 'anthropic':
                # Anthropic requiere extraer el system prompt a la raíz y añadir max_tokens
                anthropic_msgs = []
                system_str = ""
                for m in messages:
                    if m["role"] == "system":
                        system_str += m["content"] + "\n"
                    elif m["role"] == "assistant" and "tool_calls" in m:
                        content_blocks = []
                        if m.get("content"):
                            content_blocks.append({"type": "text", "text": m["content"]})
                        for tc in m["tool_calls"]:
                            try:
                                args = json.loads(tc["function"]["arguments"])
                            except:
                                args = {}
                            content_blocks.append({
                                "type": "tool_use",
                                "id": tc["id"],
                                "name": tc["function"]["name"],
                                "input": args
                            })
                        anthropic_msgs.append({"role": "assistant", "content": content_blocks})
                    elif m["role"] == "tool":
                        # En Anthropic, el resultado de tool va en un rol 'user'
                        tool_res = {
                            "type": "tool_result",
                            "tool_use_id": m["tool_call_id"],
                            "content": m.get("content", "")
                        }
                        if anthropic_msgs and anthropic_msgs[-1]["role"] == "user":
                            if isinstance(anthropic_msgs[-1]["content"], list):
                                anthropic_msgs[-1]["content"].append(tool_res)
                            else:
                                anthropic_msgs[-1]["content"] = [{"type": "text", "text": anthropic_msgs[-1]["content"]}, tool_res]
                        else:
                            anthropic_msgs.append({
                                "role": "user",
                                "content": [tool_res]
                            })
                    else:
                        if anthropic_msgs and anthropic_msgs[-1]["role"] == m["role"]:
                            # Unir con el mensaje anterior si es del mismo rol
                            prev_content = anthropic_msgs[-1]["content"]
                            new_content = m.get("content", "")
                            if isinstance(prev_content, list):
                                prev_content.append({"type": "text", "text": new_content})
                            else:
                                anthropic_msgs[-1]["content"] = prev_content + "\n\n" + new_content
                        else:
                            anthropic_msgs.append({"role": m["role"], "content": m.get("content", "")})
                        
                payload = {
                    "model": model_name,
                    "max_tokens": int(getattr(self, '_gen_max_tokens', None) or 4096),
                    "system": [
                        {
                            "type": "text",
                            "text": system_str.strip(),
                            "cache_control": {"type": "ephemeral"}
                        }
                    ],
                    "messages": anthropic_msgs,
                    "temperature": config["temperature"],
                    "stream": True
                }
                if tools:
                    # En anthropic la sintaxis de tools es diferente (input_schema en vez de parameters)
                    anthropic_tools = []
                    for t in tools:
                        anthropic_tools.append({
                            "name": t["function"]["name"],
                            "description": t["function"]["description"],
                            "input_schema": t["function"]["parameters"]
                        })
                    payload["tools"] = anthropic_tools
            else:
                # Formato OpenAI estándar. Consolidamos los `system` al inicio:
                # vLLM/OVH exige que el system sea el primero ("System message
                # must be at the beginning"); Anthropic ya los funde en la raíz.
                payload = {
                    "model": model_name,
                    "messages": self._coalesce_openai_system(messages),
                    "temperature": config["temperature"],
                    "stream": True,
                    "max_tokens": int(getattr(self, '_gen_max_tokens', None) or 4096),
                    # usage en el chunk final (OpenAI/vLLM). OVH Kepler y otros
                    # gateways responden HTTP 400 si llega stream_options → se
                    # reintenta sin él (abajo), no failover al siguiente proveedor.
                    "stream_options": {"include_usage": True},
                }
                if tools:
                    payload["tools"] = tools
                    # Igual que OpenAIDriver: sin tool_choice algunos gateways devuelven stream vacío.
                    payload["tool_choice"] = "auto"
                if (not remote_llm_format) and skip_table_footer:
                    # Apaga thinking interno si el backend lo respeta
                    # (chat_template_kwargs). Quien lo ignore no se ve afectado.
                    # Ver help de ai.provider.footmode (foot-laconic).
                    payload["chat_template_kwargs"] = {"enable_thinking": False}
                
            tool_calls_buffer = {}
            content_buffer = ""
            unparsed_lines = []
            # Con tools activos no streameamos tokens al chat hasta saber si la
            # ronda trae tool_calls. Progreso corto → status; dumps → silenciados.
            # El LLM sí conserva el content en messages.
            _defer_user_tokens = bool(tools)

            # Histórico: petición al modelo (ORCH → LLM) vía gate del motor.
            Engine = self.env['ai.execution.engine']
            Engine.log_provider_llm_request(
                provider,
                agent_code=agent_code,
                round_n=round_n,
                num_messages=len(messages),
                num_tools=len(tools),
                model_label=model_name,
                user_id=self._turn_uid,
                correlation_id=self._turn_corr,
                step_seq=self._next_step(),
                source_channel='chatboo',
            )

            _stream_attempt = 0
            while True:
                _stream_attempt += 1
                try:
                    # urllib: evita deadlocks gevent/httpx en Odoo
                    req = urllib.request.Request(
                        config["endpoint"],
                        data=json.dumps(payload).encode("utf-8"),
                        headers=headers,
                        method="POST"
                    )
                    with urllib.request.urlopen(req, timeout=config["idle_timeout"]) as response:
                        while True:
                            if time.monotonic() - round_started > config["round_timeout"]:
                                raise ProviderConnectionError(
                                    _('Round %s exceeded %ss waiting for the model.')
                                    % (round_n, config["round_timeout"])
                                )
                            line = response.readline()
                            if not line:
                                break
                            line_str = line.decode('utf-8').strip()
                            data_str = _sse_payload_from_line(line_str)
                            if data_str is None:
                                continue
                            if data_str == "[DONE]":
                                break

                            try:
                                chunk = json.loads(data_str)

                                # Formato Anthropic
                                if config["protocol"] == 'anthropic':
                                    event_type = chunk.get("type")
                                    if event_type == "content_block_delta":
                                        delta = chunk.get("delta", {})
                                        if delta.get("type") == "text_delta":
                                            txt = delta.get("text", "")
                                            content_buffer += txt
                                            if not _defer_user_tokens and txt:
                                                yield {"event": "token", "content": txt}
                                        elif delta.get("type") == "input_json_delta":
                                            idx = chunk.get("index", 0)
                                            if idx in tool_calls_buffer:
                                                tool_calls_buffer[idx]["function"]["arguments"] += delta.get("partial_json", "")
                                    elif event_type == "content_block_start":
                                        block = chunk.get("content_block", {})
                                        if block.get("type") == "tool_use":
                                            idx = chunk.get("index", 0)
                                            tool_calls_buffer[idx] = {
                                                "id": block.get("id", ""),
                                                "type": "function",
                                                "function": {
                                                    "name": block.get("name", ""),
                                                    "arguments": "",
                                                },
                                            }
                                    elif event_type == "message_start":
                                        _mu = (chunk.get("message") or {}).get("usage") or {}
                                        if _mu.get("input_tokens"):
                                            usage_info["prompt_tokens"] = _mu.get("input_tokens")
                                        if _mu.get("cache_read_input_tokens"):
                                            usage_info["cached_tokens"] = _mu.get(
                                                "cache_read_input_tokens"
                                            )
                                    elif event_type == "message_delta":
                                        _du = chunk.get("usage") or {}
                                        if _du.get("output_tokens"):
                                            usage_info["completion_tokens"] = _du.get(
                                                "output_tokens"
                                            )

                                # Formato OpenAI
                                else:
                                    _u = chunk.get("usage")
                                    if _u:
                                        usage_info = _u
                                    # chunk final include_usage: choices=[] —
                                    # no indexar a ciegas (IndexError → failover).
                                    _choices = chunk.get("choices") or []
                                    delta = (
                                        _choices[0].get("delta", {}) if _choices else {}
                                    )
                                    for txt in _openai_stream_text_tokens(chunk):
                                        content_buffer += txt
                                        if not _defer_user_tokens and txt:
                                            yield {"event": "token", "content": txt}
                                    _openai_stream_merge_tool_calls(
                                        delta, tool_calls_buffer
                                    )
                            except json.JSONDecodeError:
                                if len(unparsed_lines) < 5:
                                    unparsed_lines.append(line_str[:300])
                    break  # stream OK
                except urllib.error.HTTPError as e:
                    error_text = e.read().decode("utf-8", errors="ignore")
                    # OVH Kepler (y similares): 400 por stream_options aunque
                    # stream=True. Reintentar UNA vez sin ese campo; no cascada.
                    if (
                        e.code == 400
                        and _stream_attempt == 1
                        and payload.pop('stream_options', None) is not None
                        and 'stream_options' in (error_text or '')
                    ):
                        _logger.warning(
                            'LLM %s rechazó stream_options; reintento sin él',
                            config['endpoint'],
                        )
                        tool_calls_buffer = {}
                        content_buffer = ""
                        unparsed_lines = []
                        continue
                    _logger.error(
                        "HTTPError LLM (%s): %s - %s",
                        config['endpoint'], e.code, error_text,
                    )
                    raise ProviderConnectionError(
                        'HTTP %s: %s' % (e.code, error_text[:300])
                    ) from e
                except ProviderConnectionError:
                    raise
                except Exception as e:
                    _logger.error(
                        "Error de conexión LLM (%s): %s",
                        config['endpoint'], e, exc_info=True,
                    )
                    raise ProviderConnectionError(str(e)) from e
                
            # Quitar razonamiento inline (<think>...</think>) si el modelo lo metió
            # dentro de content en vez de en reasoning_content.
            content_buffer = _strip_think_blocks(content_buffer)

            # Fallback de tool-calling: algunos modelos no emiten tool_calls
            # estructuradas, sino que escriben el JSON de la
            # llamada dentro del content. Lo recuperamos y ejecutamos igual,
            # reutilizando el parser del orquestador. Solo aceptamos llamadas a
            # tools realmente disponibles, para no confundir prosa con tool-call.
            if not tool_calls_buffer and content_buffer.strip() and tools:
                try:
                    from ..lib.llm.utils.tool_utils import _extract_from_content
                    _recovered = _extract_from_content(content_buffer) or []
                except Exception:
                    _recovered = []
                if _recovered:
                    _available = set()
                    for _t in (tools or []):
                        _fn = (_t.get('function') or {}) if isinstance(_t, dict) else {}
                        _name = _fn.get('name') or (_t.get('name') if isinstance(_t, dict) else None)
                        if _name:
                            _available.add(_name)
                    _valid = [
                        c for c in _recovered
                        if (c.get('function') or {}).get('name') in _available
                    ]
                    if _valid:
                        _logger.info(
                            "AgentEngine: tool-call recuperada del content (modelo sin "
                            "tool_calls nativas): %s",
                            [(c.get('function') or {}).get('name') for c in _valid],
                        )
                        for _i, _tc in enumerate(_valid):
                            tool_calls_buffer[_tc.get('id') or 'call_fallback_%d' % _i] = _tc
                        content_buffer = ""

            # Analizar el resultado del stream
            sync_error = None
            if not tool_calls_buffer and not content_buffer.strip():
                _logger.warning(
                    "LLM stream sin texto (%s, model=%s, tools=%s). Muestra: %s",
                    config['endpoint'], model_name, len(tools), unparsed_lines,
                )
                if config["protocol"] != 'anthropic' and not config["skip_sync_fallback"]:
                    fb_content, fb_tools, sync_error = _apply_openai_sync_fallback(
                        config['endpoint'], headers, payload,
                    )
                    if fb_content.strip():
                        content_buffer = fb_content
                        # Flush al chat solo si no hay tool_calls (ver abajo).
                        if not _defer_user_tokens:
                            yield {'event': 'token', 'content': fb_content}
                    if fb_tools:
                        tool_calls_buffer.update(fb_tools)

            # Histórico: respuesta del modelo (LLM → ORCH) vía gate del motor.
            _resp_tools = [
                (tc.get('function') or {}).get('name')
                for tc in tool_calls_buffer.values()
            ]
            _ptok = usage_info.get('prompt_tokens') if usage_info else None
            _ctok = usage_info.get('completion_tokens') if usage_info else None
            _ttok = (usage_info.get('total_tokens') if usage_info else None) or (
                (_ptok or 0) + (_ctok or 0)
            ) or None
            Engine.log_provider_llm_response(
                provider,
                agent_code=agent_code,
                content_preview=(content_buffer or '').strip(),
                tool_names=_resp_tools,
                model_label=model_name,
                prompt_tokens=_ptok,
                completion_tokens=_ctok,
                total_tokens=_ttok,
                user_id=self._turn_uid,
                correlation_id=self._turn_corr,
                step_seq=self._next_step(),
                source_channel='chatboo',
            )
            if usage_info:
                add_usage(turn_usage, usage_info)
                last_round_total = int(
                    usage_info.get('total_tokens')
                    or ((_ptok or 0) + (_ctok or 0))
                    or 0
                )

            if not tool_calls_buffer:
                if not content_buffer.strip():
                    if sync_error:
                        # No enmascarar: el servidor sí respondió con un error real.
                        # HTTP 400 suele ser prompt mayor que el ctx_size con que se
                        # cargó el modelo en el servidor de inferencia.
                        raise ProviderConnectionError(
                            _('Provider %s (model %s) rejected the request: %s. '
                              'If it is HTTP 400, the prompt likely exceeds the '
                              'context size the model was loaded with on the '
                              'inference server.')
                            % (config['endpoint'], model_name, sync_error)
                        )
                    raise ProviderConnectionError(
                        _('Provider %s (model %s) returned no content. The model '
                          'may have been loaded with a context size smaller than '
                          'the prompt.')
                        % (config['endpoint'], model_name)
                    )
                # After a retryable tool failure, progress chatter without tools
                # is NOT a final answer (R5YZ: announced a map regen, never called).
                if _should_block_progress_as_final(
                    content_buffer,
                    has_tool_calls=False,
                    has_pending_retry=bool(last_retry_error),
                    rounds_left=(round_n < MAX_ROUNDS),
                ):
                    _progress_only = _pretool_progress_status(content_buffer)
                    messages.append({
                        "role": "assistant",
                        "content": content_buffer,
                    })
                    from .error_ux import retry_nudge_after_tool_error
                    messages.append({
                        "role": "user",
                        "content": retry_nudge_after_tool_error(
                            last_retry_error,
                        ),
                    })
                    if _progress_only:
                        yield {"event": "status", "message": _progress_only}
                    _logger.info(
                        'agent_engine: blocked progress-as-final after tool '
                        'error (session=%s round=%s)',
                        session_id, round_n,
                    )
                    continue
                # Round 1 with tools in the payload and zero tool_calls is not
                # a user answer (NTU0/THKM: announced a Safe Plan, never called).
                if _should_block_no_tool_as_final(
                    has_tool_calls=False,
                    is_first_round=(round_n == 1),
                    rounds_left=(round_n < MAX_ROUNDS),
                    has_tools=bool(tools),
                    content=content_buffer,
                    tool_names=[
                        ((tc.get('function') or {}).get('name') or '')
                        for tc in (tools or [])
                    ],
                    user_message=_orig or message,
                    prior_assistant=[
                        (m.get('content') or '')
                        for m in (history or [])
                        if isinstance(m, dict)
                        and m.get('role') == 'assistant'
                        and (m.get('content') or '').strip()
                    ],
                ):
                    messages.append({
                        "role": "assistant",
                        "content": content_buffer,
                    })
                    messages.append({
                        "role": "user",
                        "content": NO_TOOL_FINAL_NUDGE,
                    })
                    _status = _pretool_progress_status(content_buffer)
                    if _status:
                        yield {"event": "status", "message": _status}
                    _logger.info(
                        'agent_engine: blocked no-tool-as-final '
                        '(session=%s round=%s)',
                        session_id, round_n,
                    )
                    continue
                # Respuesta final: si diferimos tokens (ronda con tools en payload),
                # volcamos ahora el buffer al chat.
                _visible = _user_visible_round_text(content_buffer, has_tool_calls=False)
                if _defer_user_tokens and _visible:
                    yield {"event": "token", "content": _visible}
                messages.append({"role": "assistant", "content": content_buffer})
                # Candado estructural: forzar tabla / linkify si el LLM narró.
                _final = content_buffer or ''
                # Report outline: reuse this turn's earlier narrative if the
                # closer replaced it; then fill a truncated skeleton only.
                if remote_llm_format:
                    try:
                        from .report_outline_guard import (
                            ensure_report_completion,
                            recover_turn_report_body,
                        )
                        _rc = getattr(self, '_report_contract', None) or {}
                        _recovered = recover_turn_report_body(
                            messages[_turn_loop_from:],
                            _final,
                            _rc.get('report_outline'),
                        )
                        _recovered_changed = (
                            (_recovered or '').strip()
                            != (_final or '').strip()
                        )
                        if _recovered_changed:
                            _final = _recovered
                        _patched, _changed = ensure_report_completion(
                            _final,
                            outline=_rc.get('report_outline'),
                            closing=_rc.get('closing_required'),
                            recommendations_stub=_rc.get('recommendations_stub'),
                            recommendations_heading=_rc.get(
                                'recommendations_heading',
                            ),
                        )
                        if _changed:
                            _final = _patched
                        if _recovered_changed or _changed:
                            content_buffer = _final
                            yield {"event": "replace", "content": _final}
                            _logger.info(
                                'agent_engine: report outline completed '
                                '(session=%s recovered=%s filled=%s)',
                                session_id,
                                _recovered_changed,
                                _changed,
                            )
                    except Exception as _outline_exc:
                        _logger.debug(
                            'report outline guard skipped: %s', _outline_exc,
                        )
                _forced_html = None
                try:
                    from .record_delivery_gate import (
                        should_force_turn_payload,
                    )
                    from .record_linkify import linkify_prose
                    from .relaxaicode_render import (
                        maybe_attach_formatted_text,
                        render_context_from_env,
                        wrap_bare_images_clickable,
                    )
                    import copy as _copy

                    def _render_forced(_payload):
                        if not isinstance(_payload, dict):
                            return None
                        _p = _copy.deepcopy(_payload)
                        _p.pop('formatted_text', None)
                        try:
                            _rcx = render_context_from_env(self.env, result=_p)
                        except Exception:
                            _rcx = None
                        maybe_attach_formatted_text(
                            _p,
                            summary=_p.get('summary') or '',
                            render_context=_rcx,
                            force=True,
                        )
                        _ft = _p.get('formatted_text')
                        if not _ft:
                            return None
                        return wrap_bare_images_clickable(_ft)

                    # Skill report: append bootstrap tables (with charts) after
                    # the LLM prose as a fallback. The model may also embed
                    # formatted_text itself — duplicate blocks are acceptable
                    # vs silently dropping native charts.
                    _rtp = getattr(self, '_report_tables_payload', None)
                    if remote_llm_format and isinstance(_rtp, dict):
                        _rtp = dict(_rtp)
                        _rtp['__subtle_zebra__'] = True
                        _tables_html = _render_forced(_rtp)
                        self._report_tables_payload = None
                        if _tables_html:
                            table_already_delivered = True
                            try:
                                turn_table_fps |= extract_dataset_fingerprints(
                                    _tables_html,
                                )
                            except Exception:
                                pass
                            _prose = (_final or '').strip()
                            # Markdown → HTML so mixed report+tables keep headings.
                            if _prose:
                                try:
                                    from .relaxaicode_render import (
                                        _markdownish_to_html,
                                    )
                                    _prose_html = _markdownish_to_html(_prose)
                                except Exception:
                                    _prose_html = ''
                                if not _prose_html:
                                    import html as _html_mod
                                    _prose_html = _html_mod.escape(_prose)
                                _host = (
                                    '<div class="o_chatboo_prose_host '
                                    'o_chatboo_prose">%s</div>'
                                    % _prose_html
                                )
                                _final = _host + '\n\n' + _tables_html
                            else:
                                _final = _tables_html
                            content_buffer = _final
                            yield {"event": "replace", "content": _final}
                            _logger.info(
                                'agent_engine: report tables HTML appended '
                                '(session=%s)',
                                session_id,
                            )

                    # /painter-local candado: local HTML when painter-free is off.
                    if (
                        not remote_llm_format
                        and should_force_turn_payload(
                            _final,
                            last_tabulable_payload=last_tabulable_payload,
                            table_already_delivered=table_already_delivered,
                        )
                    ):
                        _forced_html = _render_forced(last_tabulable_payload)
                    # 1b desactivado: nunca forzar prior_query_data a la burbuja.

                    if _forced_html:
                        table_already_delivered = True
                        try:
                            turn_table_fps |= extract_dataset_fingerprints(
                                _forced_html,
                            )
                        except Exception:
                            pass
                        _prose = linkify_prose(
                            _final, collected_records, links_off=links_off_turn,
                        )
                        if (_prose or '').strip() and not (
                            'o_chatboo_table_block' in (_prose or '')
                        ):
                            _final = _forced_html + '\n\n' + _prose.strip()
                        else:
                            _final = _forced_html
                        try:
                            _final = strip_echoed_table_blocks(
                                _final,
                                prior_table_fps,
                                allow_fingerprints=turn_table_fps,
                            )
                        except Exception:
                            pass
                        yield {"event": "replace", "content": _final}
                    elif (
                        collected_records
                        and not links_off_turn
                        and not table_already_delivered
                    ):
                        _linked = linkify_prose(
                            _final, collected_records, links_off=False,
                        )
                        if _linked != _final:
                            _final = _linked
                        try:
                            _stripped = strip_echoed_table_blocks(
                                _final,
                                prior_table_fps,
                                allow_fingerprints=turn_table_fps,
                            )
                        except Exception:
                            _stripped = _final
                        if _stripped != content_buffer:
                            _final = _stripped
                            yield {"event": "replace", "content": _final}
                    else:
                        try:
                            _stripped = strip_echoed_table_blocks(
                                _final,
                                prior_table_fps,
                                allow_fingerprints=turn_table_fps,
                            )
                        except Exception:
                            _stripped = _final
                        if _stripped != content_buffer:
                            yield {"event": "replace", "content": _stripped}
                except Exception as _gate_err:
                    _logger.debug(
                        'record delivery gate skipped: %s', _gate_err,
                    )
                finished_with_answer = True
                break
                
            # El modelo pidió herramientas. content → historial LLM (razonamiento).
            # Chat bubble: nunca. Status bar: solo si es progreso corto (forma).
            _progress = _pretool_progress_status(content_buffer)
            if _progress:
                yield {"event": "status", "message": _progress}
            messages.append({
                "role": "assistant",
                "content": content_buffer,
                "tool_calls": list(tool_calls_buffer.values())
            })
            
            # Ejecutar herramientas nativamente en Odoo
            direct_formatted = None
            stop_after_direct = False
            # Pie local (servidor) tras HTML de skill: cálido, sin inventar año.
            local_warm_footer = False
            # Texto de pie compuesto por el AUTOR del skill (prioritario sobre
            # el genérico). None = usar el pie cálido por defecto.
            local_footer_text = None
            # Remote formatting: tabular payload to hand to the LLM (no local HTML).
            remote_tabular_handoff = None

            def _basket_push(payload, code=''):
                nonlocal primary_artifact
                try:
                    from .primary_artifact import apply as apply_primary
                    primary_artifact, _action = apply_primary(
                        primary_artifact,
                        turn_presentation_basket,
                        payload,
                        code,
                    )
                except Exception:
                    try:
                        from .turn_presentation_basket import append_presentable
                        append_presentable(turn_presentation_basket, payload)
                    except Exception:
                        pass

            def _basket_html_for_replace(html):
                """Merge presentable results; keep basket so the primary stays."""
                try:
                    from .turn_presentation_basket import render_basket_html
                    merged = render_basket_html(
                        turn_presentation_basket,
                        fallback_html=html,
                        env=self.env,
                    )
                except Exception as _basket_exc:
                    _logger.debug(
                        'turn presentation basket skipped: %s', _basket_exc,
                    )
                    merged = html
                return merged if merged is not None else html

            def _remember_clip_data(payload=None, rows=None):
                nonlocal export_clip_data
                if export_clip_data:
                    return
                try:
                    from .artifact_export import clip_data_from_payload
                    data = clip_data_from_payload(payload, rows)
                except Exception:
                    data = None
                if data:
                    export_clip_data = data

            def _try_session_export():
                """Persist the named download as a session chip; stop ReAct."""
                nonlocal export_attached, stop_after_direct, direct_formatted
                nonlocal export_chips, export_meta_nudged, export_meta_nudge_round
                nonlocal export_clip_data, export_refused_tokens
                if export_attached:
                    return True
                try:
                    from .artifact_export import (
                        requested_named_format,
                        wants_on_screen_blocks,
                        export_hides_on_screen_table,
                        tabular_rows,
                        has_export_meta,
                        SESSION_FILE_META_PROTOCOL,
                    )
                except Exception:
                    requested_named_format = None
                    wants_on_screen_blocks = lambda *_a, **_k: False
                    export_hides_on_screen_table = lambda *_a, **_k: False
                    tabular_rows = lambda *_a, **_k: None
                    has_export_meta = lambda *_a, **_k: True
                    SESSION_FILE_META_PROTOCOL = ''
                named = (
                    requested_named_format(_orig)
                    if requested_named_format else None
                )
                payload = _payload_for_screen(
                    primary_artifact or last_tabulable_payload,
                )
                show_blocks = wants_on_screen_blocks(payload, turn_query_data)
                has_rows = bool(turn_query_data) or bool(
                    tabular_rows(payload, turn_query_data)
                )
                if named and has_rows:
                    _remember_clip_data(payload, turn_query_data)
                if (
                    named and has_rows
                    and not has_export_meta(payload)
                    and round_n < MAX_ROUNDS
                ):
                    if not export_meta_nudged:
                        export_meta_nudged = True
                        export_meta_nudge_round = round_n
                        if SESSION_FILE_META_PROTOCOL:
                            messages.append({
                                'role': 'system',
                                'content': SESSION_FILE_META_PROTOCOL,
                            })
                        return False
                    if round_n == export_meta_nudge_round:
                        return False
                _ex = self._attach_requested_file_export(
                    _orig, session_id,
                    rows=turn_query_data,
                    payload=payload,
                )
                if _ex and _ex.get('acted'):
                    export_attached = True
                    chips = _absorb_export_result(_ex)
                    if chips and named and not show_blocks:
                        direct_formatted = ''
                        stop_after_direct = True
                    elif named and not chips and export_hides_on_screen_table(
                        _orig, payload,
                    ):
                        stop_after_direct = True
                        direct_formatted = _(
                            'Could not build the download file.'
                        )
                    elif not show_blocks:
                        stop_after_direct = True
                    return True
                has_rows = bool(turn_query_data) or bool(
                    tabular_rows(payload, turn_query_data)
                )
                if named and has_rows:
                    _logger.warning(
                        'AgentEngine: named download did not persist a chip'
                    )
                    if export_hides_on_screen_table(_orig, payload):
                        stop_after_direct = True
                        direct_formatted = _(
                            'Could not build the download file.'
                        )
                    elif not show_blocks:
                        stop_after_direct = True
                return False

            for tc in tool_calls_buffer.values():
                # stop_after_direct corta la SIGUIENTE ronda LLM, no los
                # tool_calls ya emitidos en esta (Relaxaicode hermano sigue).
                tool_name = tc["function"]["name"]
                tool_args_str = tc["function"]["arguments"]
                tool_id = tc["id"]
                
                yield {"event": "status", "message": f"Ejecutando {tool_name}..."}
                _logger.info(f"AgentEngine ejecutando tool: {tool_name}")
                tools_invoked_count += 1
                _blocked = None
                result = None

                try:
                    tool_args = json.loads(tool_args_str)
                except Exception as e:
                    tool_args = {}
                    _logger.warning(f"Error decodificando argumentos JSON para {tool_name}: {e}")

                # Nivel 2: inyectar previous_result si el código AST usa
                # previous_result/raw_data, O si pega un dataset module-level
                # (strip→rebind en tools_relaxaicode). Auto-inyectar siempre
                # colaba datasets de otro tema; el gate de literales cubre el
                # caso Sesame (rows=[{…}]) sin nombrar previous_result.
                if (
                    tool_name == 'relaxaicode'
                    and (turn_query_data or primary_artifact)
                    and isinstance(tool_args, dict)
                    and not tool_args.get('previous_result')
                ):
                    _code = tool_args.get('code') or ''
                    _need_prior = code_references_reuse_names(_code)
                    if not _need_prior and _code:
                        try:
                            from .relaxaicode_recipe import (
                                module_level_data_literal_error,
                            )
                            _need_prior = bool(
                                module_level_data_literal_error(_code)
                            )
                        except Exception:
                            _need_prior = False
                    if _need_prior:
                        if primary_artifact:
                            try:
                                from .primary_artifact import presentation_payload
                                tool_args['previous_result'] = (
                                    presentation_payload(primary_artifact)
                                )
                            except Exception:
                                tool_args['previous_result'] = {
                                    'data': turn_query_data,
                                }
                        elif turn_safe_plan_steps:
                            from .record_delivery_gate import (
                                previous_result_envelope_from_safe_plan,
                            )
                            tool_args['previous_result'] = (
                                previous_result_envelope_from_safe_plan(
                                    turn_safe_plan_steps,
                                    rows=turn_query_data,
                                )
                                or {'data': turn_query_data}
                            )
                        else:
                            tool_args['previous_result'] = {
                                'data': turn_query_data,
                            }

                # Histórico: el modelo solicita una herramienta (LLM → ORCH),
                # registrado ANTES de ejecutarla y con sus argumentos.
                self._mcp_log(
                    operation_type='read',
                    tool_name='llm_tool_request',
                    request_type='LLM',
                    agent_llm=model_name,
                    prompt_data=tool_args,
                    result_summary=_('LLM requested tool: %(t)s') % {'t': tool_name},
                )

                tool_func = get_tool_function(tool_name)
                
                # Mock controlador (algunas tools piden request.env o _get_env_for_operation)
                class DummyController:
                    def __init__(self, agent_env):
                        self.env = agent_env
                        
                    def _get_env_for_operation(self, operation_type='read'):
                        return self.env

                    def _get_readonly_env(self):
                        from ..controllers.controller_helpers import get_readonly_env
                        return get_readonly_env(self)
                        
                    def _check_mcp_permissions(self, operation_type):
                        return True, ""
                        
                    def _log_mcp_operation(
                        self,
                        operation_type='read',
                        tool_name='relaxaicode',
                        prompt_data=None,
                        result_data=None,
                        result_summary=None,
                        additional_info=None,
                        code_to_execute=None,
                        request_type=None,
                        payload_type=None,
                        context_type=None,
                        agent_llm=None,
                    ):
                        # Reutiliza la correlación y el usuario del turno (engine),
                        # para que la herramienta caiga en el mismo hilo del histórico.
                        engine._mcp_log(
                            operation_type=operation_type,
                            tool_name=tool_name,
                            prompt_data=prompt_data,
                            result_data=result_data,
                            result_summary=result_summary,
                            additional_info=additional_info,
                            code_to_execute=code_to_execute,
                            request_type=request_type or 'tool',
                            agent_llm=agent_llm,
                        )

                    def _get_user_locale(self):
                        try:
                            return self.env.user.lang or 'en_US'
                        except Exception:
                            return 'en_US'

                    def _get_company_lang(self):
                        try:
                            return self.env.company.partner_id.lang or False
                        except Exception:
                            return False

                    def _cancel_pending_verifications_for_user(self, user_id, reason="falta de permisos"):
                        # Solo se usa en la rama de permiso denegado (no en flujo normal).
                        return 0

                    def _resolve_locale_placeholders(self, text_content):
                        from ..utils.context_utils import resolve_placeholders
                        return resolve_placeholders(text_content, self.env, controller=self)

                if tool_func:
                    try:
                        if tool_name == 'propose_safe_operations':
                            _blocked = self._intercept_session_file_propose(
                                _orig, session_id, tool_args,
                                rows=turn_query_data,
                                payload=_payload_for_screen(
                                    primary_artifact or last_tabulable_payload,
                                ),
                            )
                        if _blocked is not None:
                            result = _blocked['result']
                            if _blocked.get('attached'):
                                export_attached = True
                                stop_after_direct = True
                                _absorb_export_result(_blocked)
                                _remember_clip_data(
                                    primary_artifact or last_tabulable_payload,
                                    turn_query_data,
                                )
                                try:
                                    from .artifact_export import (
                                        export_hides_on_screen_table,
                                    )
                                    _hide = export_hides_on_screen_table(
                                        _orig,
                                        _payload_for_screen(
                                            primary_artifact
                                            or last_tabulable_payload,
                                        ),
                                    )
                                except Exception:
                                    _hide = True
                                if export_chips and (
                                    _hide or not direct_formatted
                                ):
                                    if _hide:
                                        direct_formatted = ''
                                elif _hide and not export_chips:
                                    direct_formatted = _(
                                        'Could not build the download file.'
                                    )
                        else:
                            # Odoo's mcp_tools expect (controller, arguments)
                            result = tool_func(DummyController(self.env), tool_args)
                        try:
                            from .relaxaicode_render import render_context_from_env
                            _render_ctx = render_context_from_env(
                                self.env,
                                result=_payload if isinstance(_payload, dict) else None,
                            )
                        except Exception:
                            _render_ctx = None
                        from .mcp_tool_payload import (
                            is_author_html_payload,
                            unwrap_tool_payload,
                        )
                        _payload = unwrap_tool_payload(result) or (
                            result if isinstance(result, dict) else None
                        )
                        _harvest_file_labels(_payload)
                        _force_retry = bool(
                            isinstance(result, dict) and result.get('__force_retry__')
                        )
                        _direct = _resolve_direct_return(
                            result, render_context=_render_ctx,
                        )
                        if not _direct:
                            _direct = _extract_direct_formatted_output(
                                result, render_context=_render_ctx,
                            )
                        _tool_code = (
                            tool_args.get('code') if isinstance(tool_args, dict) else ''
                        ) or ''
                        _pa_action = None
                        if isinstance(_payload, dict):
                            try:
                                from .primary_artifact import classify_vs_primary
                                _pa_action = classify_vs_primary(
                                    primary_artifact, _payload, code=_tool_code,
                                )
                            except Exception:
                                _pa_action = None
                        _um_gate = (
                            (self.env.context or {}).get('user_message') or message
                        )
                        _ulang_gate = None
                        try:
                            _ulang_gate = self.env.user.lang
                        except Exception:
                            _ulang_gate = None
                        if _direct and not _should_show_direct_to_chat(
                            _payload,
                            round_n=round_n,
                            max_rounds=MAX_ROUNDS,
                            tool_name=tool_name,
                            force_retry=_force_retry,
                            has_primary=bool(primary_artifact),
                            user_message=_um_gate,
                            user_lang=_ulang_gate,
                        ):
                            _direct = None
                        try:
                            from .artifact_export import (
                                export_hides_on_screen_table,
                                wants_on_screen_blocks,
                            )
                            if (
                                _direct
                                and export_hides_on_screen_table(
                                    _um_gate, _payload_for_screen(_payload),
                                )
                                and not wants_on_screen_blocks(
                                    _payload_for_screen(_payload),
                                )
                            ):
                                _direct = None
                            if (
                                _direct
                                and export_chips
                                and not wants_on_screen_blocks(
                                    _payload_for_screen(_payload),
                                )
                            ):
                                _direct = None
                        except Exception:
                            if _direct and export_chips:
                                _direct = None
                        if (
                            _direct
                            and _pa_action == 'probe'
                            and primary_artifact
                        ):
                            _direct = None
                        if _direct:
                            # High-level switch: remote owns ordinary tables;
                            # author_html / local path unchanged when flag OFF.
                            from .mcp_tool_payload import (
                                remote_owns_tabular_presentation,
                            )
                            if remote_owns_tabular_presentation(
                                remote_llm_format, _payload,
                            ):
                                remote_tabular_handoff = (
                                    _payload if isinstance(_payload, dict) else None
                                )
                                # Handoff counts as delivery for candado 1a —
                                # otherwise a Markdown answer gets an HTML+chart
                                # table re-injected at turn end.
                                table_already_delivered = True
                            else:
                                direct_formatted = _direct
                                table_already_delivered = True
                                _basket_push(_payload, _tool_code)
                                # HTML de skill/código (author_html): sin 2.ª vuelta de
                                # pie — el modelo inventaba años o cifras.
                                # Tablas server_side_python: pie solo si foot-verbose
                                # (se decide más abajo con skip_table_footer).
                                if is_author_html_payload(_payload):
                                    stop_after_direct = True
                                    # Humanos quieren pie; el LLM inventaba el año →
                                    # pie fijo del servidor (traducible), sin 2.ª vuelta.
                                    # Pero cada skill decide: puede omitirlo (listados
                                    # con su propio contador) o componer el suyo.
                                    if not skip_table_footer:
                                        from .mcp_tool_payload import (
                                            resolve_author_footer,
                                        )
                                        _suppress, _ftext = resolve_author_footer(
                                            _payload,
                                        )
                                        if not _suppress:
                                            local_warm_footer = True
                                            local_footer_text = _ftext
                                elif (_payload or {}).get('__stop_after_direct__'):
                                    stop_after_direct = True
                                elif skip_table_footer and (
                                    (_payload or {}).get('__direct_return__')
                                    or (_payload or {}).get('__return_direct__')
                                ):
                                    stop_after_direct = True
                        # Error recuperable (auto-corrección): guardar el texto por si
                        # se agotan los turnos sin respuesta final.
                        if isinstance(result, dict) and result.get('__force_retry__'):
                            try:
                                last_retry_error = (result.get('content') or [{}])[0].get('text') or last_retry_error
                            except Exception:
                                pass
                            # Un hermano que pide reintento gana al stop del recurso.
                            stop_after_direct = False
                        elif (
                            tool_name == 'relaxaicode'
                            and isinstance(result, dict)
                            and not result.get('error')
                            and not result.get('__force_retry__')
                        ):
                            last_retry_error = None
                        # Enlaces a registros: refs (model,id,name) que relaxaicode
                        # recolecta ANTES de consumir __model. Se leen del PAYLOAD ya
                        # desempaquetado (unwrap_tool_payload), no del envoltorio MCP
                        # {'content':[{'text':...}]}, donde viajan dentro del texto.
                        # Se publican en collected_records → ficha del documento.
                        if isinstance(_payload, dict) and _payload.get('__records__'):
                            for _ref in (_payload.get('__records__') or []):
                                if isinstance(_ref, dict):
                                    _add_record(
                                        _ref.get('model'), _ref.get('id'),
                                        _ref.get('name'),
                                        role=_ref.get('role'),
                                    )
                        if (
                            isinstance(_payload, dict)
                            and (
                                _payload.get('__row_links__') is False
                                or _payload.get('links') is False
                            )
                        ):
                            links_off_turn = True
                        from .mcp_tool_payload import tool_result_json_for_llm
                        result_str = tool_result_json_for_llm(
                            result, remote_llm_format,
                        )
                        # Ancla de reutilización: si una consulta de datos se
                        # ejecutó BIEN, publicamos su código para que el worker lo
                        # guarde en la sesión y lo reinyecte en el próximo turno
                        # (ver prior_query_code). Solo el ÚLTIMO éxito del turno
                        # cuenta (el worker se queda con el más reciente).
                        if (
                            tool_name == 'relaxaicode'
                            and isinstance(result, dict)
                            and not result.get('error')
                            and not result.get('__force_retry__')
                        ):
                            relaxai_success_count += 1
                            _qc = tool_args.get('code')
                            if isinstance(_qc, str) and _qc.strip():
                                yield {"event": "query_code", "code": _qc}
                            # Guardar payload tabulable del turno (candado 1a).
                            try:
                                from .record_delivery_gate import first_tabular_rows
                                from .relaxaicode_render import is_tabulable
                                _src = _payload if isinstance(_payload, dict) else None
                                if _src is None and isinstance(result, list):
                                    _src = {'data': result}
                                if isinstance(_src, dict) and (
                                    is_tabulable(_src, force=True)
                                    or first_tabular_rows(_src)
                                ):
                                    last_tabulable_payload = _src
                                    _harvest_file_labels(_src)
                            except Exception:
                                pass
                            # Nivel 2: cachear las FILAS crudas del resultado (si las
                            # hay) para reutilizarlas como previous_result el próximo
                            # turno. Con topes de filas/bytes: si el dataset es enorme
                            # no se cachea (se cae a reutilizar solo el código). Nunca
                            # viaja al LLM: solo BD → namespace del sandbox.
                            try:
                                from .record_delivery_gate import first_tabular_rows
                                _rows = first_tabular_rows(
                                    _payload if isinstance(_payload, dict) else result
                                )
                            except Exception:
                                _rows = result.get('data') if isinstance(result, dict) else None
                            if isinstance(_rows, list) and _rows:
                                try:
                                    _max_bytes = self._dataset_cache_max_bytes()
                                    _payload_json = json.dumps(
                                        _rows, default=str, ensure_ascii=False,
                                    )
                                    if (not _max_bytes or _max_bytes <= 0
                                            or len(_payload_json.encode('utf-8'))
                                            <= _max_bytes):
                                        turn_query_data = list(_rows)
                                        _harvest_file_labels(_rows)
                                        yield {"event": "query_data", "data": _rows}
                                except Exception:
                                    pass
                            # Named download: persist the session chip as soon
                            # as rows exist. Do not wait for MAX_ROUNDS or a
                            # caja B propose (BHUX).
                            _try_session_export()
                            # Empty tabular success must NOT wipe turn_query_data:
                            # after api_call→strip recovery, a hollow table would
                            # erase the live dataset and force empty re-tries.
                    except Exception as e:
                        _logger.error(f"Error ejecutando {tool_name}: {e}")
                        result_str = json.dumps({"error": str(e)})
                else:
                    result_str = json.dumps({"error": f"Tool '{tool_name}' no encontrada en Odoo."})

                self._log_agent_tool_step(tool_name, tool_args, result_str, model_name)

                # Caja B: si se ha propuesto una escritura, emitir un evento para que
                # el frontend de chatboo muestre la confirmación INLINE (no depende del
                # bus/toast). Sigue siendo seguro: el endpoint de confirmación es
                # auth='user' y la IA no tiene la sesión del humano.
                if (
                    tool_name == 'propose_safe_operations'
                    and isinstance(result, dict)
                    and _blocked is None
                ):
                    try:
                        _txt = (result.get('content') or [{}])[0].get('text')
                        _info = json.loads(_txt) if _txt else {}
                        # Only show the confirmation toast if the operation is
                        # actually pending (not auto-confirmed low-risk ops).
                        if (_info.get('success')
                                and _info.get('status') == 'pending_choice'
                                and _info.get('choice_id')):
                            yield {
                                "event": "choice",
                                "choice_id": _info.get('choice_id'),
                                "title": _info.get('title') or '',
                                "items": _info.get('items') or [],
                            }
                            stop_after_direct = True
                            direct_formatted = _('Pick the views in Chatboo.')
                        elif (_info.get('success')
                                and _info.get('verification_id')
                                and _info.get('status') != 'confirmed'):
                            yield {
                                "event": "verification",
                                "verification_id": _info.get('verification_id'),
                                "title": _info.get('title') or '',
                                "plan": _info.get('plan') or [],
                                "danger_level": _info.get('danger_level') or 'medium',
                            }
                            # Do not let the LLM invent "already done" while the
                            # toast is still waiting (o14pruebas / module.update).
                            stop_after_direct = True
                            direct_formatted = _('Confirm in Odoo to continue.')
                        # Fuentes externas: cuando el plan se auto-confirma
                        # (status='confirmed') se ejecuta AHORA, así que rastreamos
                        # los pasos propuestos. Cubre fetch_url (dominio) y api_call
                        # (servidor externo). La confirmación manual se rastrea al
                        # recuperar el resultado con get_safe_operation_status.
                        if _info.get('success') and _info.get('status') == 'confirmed':
                            _collect_sources(tool_args.get('steps'))
                            _collect_records_steps(_info.get('result'))
                            # Nivel 2: filas de api_call/fetch_url → turn_query_data
                            # para que relaxaicode (strip/rebind) no reciba vacío.
                            try:
                                from .record_delivery_gate import (
                                    rows_from_safe_plan_steps,
                                )
                                _steps_res = _info.get('result')
                                # Legacy auto-confirm packed steps only in message.
                                if not isinstance(_steps_res, list):
                                    _msg = _info.get('message') or ''
                                    if isinstance(_msg, str) and '\n[' in _msg:
                                        try:
                                            _steps_res = json.loads(
                                                _msg.split('\n', 1)[1],
                                            )
                                        except Exception:
                                            _steps_res = None
                                _api_rows = rows_from_safe_plan_steps(_steps_res)
                                if isinstance(_steps_res, list) and _steps_res:
                                    turn_safe_plan_steps = list(_steps_res)
                                if isinstance(_api_rows, list) and _api_rows:
                                    _max_bytes = self._dataset_cache_max_bytes()
                                    _payload_json = json.dumps(
                                        _api_rows, default=str, ensure_ascii=False,
                                    )
                                    if (not _max_bytes or _max_bytes <= 0
                                            or len(_payload_json.encode('utf-8'))
                                            <= _max_bytes):
                                        turn_query_data = list(_api_rows)
                                        _harvest_file_labels(_api_rows)
                                        yield {
                                            "event": "query_data",
                                            "data": _api_rows,
                                        }
                            except Exception:
                                pass
                            _harvest_file_labels(_steps_res)
                            if _absorb_plan_downloads(_steps_res):
                                yield {
                                    "event": "replace",
                                    "content": "",
                                }
                            _try_session_export()
                            # Presenters genéricos (skill_runtime) → HTML directo.
                            _pres = _info.get('presentation')
                            try:
                                from .artifact_export import wants_on_screen_blocks
                                if export_chips and not wants_on_screen_blocks(
                                    _payload_for_screen(
                                        primary_artifact or last_tabulable_payload,
                                    ),
                                ):
                                    _pres = None
                            except Exception:
                                if export_chips:
                                    _pres = None
                            if isinstance(_pres, dict) and (
                                _pres.get('data') is not None
                                or _pres.get('groups') is not None
                                or _pres.get('formatted_text')
                            ):
                                from .skill_runtime import render_presentation_html
                                _html = render_presentation_html(
                                    _pres, env=self.env,
                                ) or _resolve_direct_return(
                                    _pres, render_context=_render_ctx,
                                ) or _extract_direct_formatted_output(
                                    _pres, render_context=_render_ctx,
                                )
                                if _html:
                                    if remote_llm_format:
                                        # Report: do not auto-push; hand data+HTML
                                        # to the LLM so it can embed charts.
                                        remote_tabular_handoff = _pres
                                        direct_formatted = None
                                        stop_after_direct = False
                                        table_already_delivered = True
                                    else:
                                        direct_formatted = _html
                                        stop_after_direct = True
                                        _basket_push(_pres)
                    except Exception:
                        pass

                # get_safe_operation_status: recupera resultados de operaciones
                # confirmadas MANUALMENTE (no whitelisted). El payload trae 'result'
                # con la lista de pasos ya ejecutados; de ahí sacamos las fuentes.
                elif tool_name == 'get_safe_operation_status' and isinstance(result, dict):
                    try:
                        _txt = (result.get('content') or [{}])[0].get('text')
                        _info = json.loads(_txt) if _txt else {}
                        if _info.get('success') and _info.get('executed'):
                            _res = _info.get('result')
                            if isinstance(_res, list):
                                _collect_sources(_res)
                                _collect_records_steps(_res)
                                try:
                                    from .record_delivery_gate import (
                                        rows_from_safe_plan_steps,
                                    )
                                    _api_rows = rows_from_safe_plan_steps(_res)
                                    if isinstance(_res, list) and _res:
                                        turn_safe_plan_steps = list(_res)
                                    if isinstance(_api_rows, list) and _api_rows:
                                        _max_bytes = self._dataset_cache_max_bytes()
                                        _payload_json = json.dumps(
                                            _api_rows, default=str,
                                            ensure_ascii=False,
                                        )
                                        if (not _max_bytes or _max_bytes <= 0
                                                or len(_payload_json.encode('utf-8'))
                                                <= _max_bytes):
                                            turn_query_data = list(_api_rows)
                                            _harvest_file_labels(_api_rows)
                                            yield {
                                                "event": "query_data",
                                                "data": _api_rows,
                                            }
                                except Exception:
                                    pass
                            _harvest_file_labels(_res)
                            _try_session_export()
                            if _absorb_plan_downloads(_res):
                                yield {
                                    "event": "replace",
                                    "content": "",
                                }
                            _pres = _info.get('presentation')
                            try:
                                from .artifact_export import wants_on_screen_blocks
                                if export_chips and not wants_on_screen_blocks(
                                    _payload_for_screen(
                                        primary_artifact or last_tabulable_payload,
                                    ),
                                ):
                                    _pres = None
                            except Exception:
                                if export_chips:
                                    _pres = None
                            if not _pres and isinstance(_res, list):
                                _allow_present = True
                                try:
                                    from .artifact_export import wants_on_screen_blocks
                                    if export_chips and not wants_on_screen_blocks(
                                        _payload_for_screen(
                                            primary_artifact
                                            or last_tabulable_payload,
                                        ),
                                    ):
                                        _allow_present = False
                                except Exception:
                                    _allow_present = not bool(export_chips)
                                if _allow_present:
                                    try:
                                        from .skill_runtime import try_present
                                        _pres = try_present(
                                            _res, steps=_res,
                                        )
                                    except Exception:
                                        _pres = None
                            if isinstance(_pres, dict) and (
                                _pres.get('data') is not None
                                or _pres.get('groups') is not None
                                or _pres.get('formatted_text')
                            ):
                                from .skill_runtime import render_presentation_html
                                _html = render_presentation_html(
                                    _pres, env=self.env,
                                ) or _resolve_direct_return(
                                    _pres, render_context=_render_ctx,
                                ) or _extract_direct_formatted_output(
                                    _pres, render_context=_render_ctx,
                                )
                                if _html:
                                    if remote_llm_format:
                                        remote_tabular_handoff = _pres
                                        direct_formatted = None
                                        stop_after_direct = False
                                        table_already_delivered = True
                                    else:
                                        direct_formatted = _html
                                        stop_after_direct = True
                                        _basket_push(_pres)
                    except Exception:
                        pass

                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_id,
                    "name": tool_name,
                    "content": result_str
                })
                if remote_llm_format and remote_tabular_handoff is not None:
                    try:
                        from .mcp_tool_payload import (
                            remote_format_handoff_payload,
                            remote_owns_tabular_presentation,
                        )
                        if remote_owns_tabular_presentation(
                            True, remote_tabular_handoff,
                        ):
                            _handoff = remote_format_handoff_payload(
                                remote_tabular_handoff,
                            )
                            if _handoff:
                                messages[-1]['content'] = json.dumps(
                                    _handoff, ensure_ascii=False, default=str,
                                )
                    except Exception:
                        pass
                    remote_tabular_handoff = None

            # ── Direct-formatted result (server-rendered HTML table) ──────────
            # BODY = tabla HTML (replace). FOOTER = 2.ª vuelta LLM solo si el
            # proveedor NO está en modo lacónico (pequeñitos → corte limpio).
            if direct_formatted:
                try:
                    turn_table_fps |= extract_dataset_fingerprints(
                        direct_formatted,
                    )
                    direct_formatted = strip_echoed_table_blocks(
                        direct_formatted,
                        prior_table_fps,
                        allow_fingerprints=turn_table_fps,
                    )
                except Exception:
                    pass
                # Turn presentation basket: merge N parallel presentable results
                # into one bubble (orthogonal to report vs table formatting).
                _hide_table = False
                try:
                    from .artifact_export import export_hides_on_screen_table
                    _hide_table = export_hides_on_screen_table(
                        _orig,
                        _payload_for_screen(
                            primary_artifact or last_tabulable_payload,
                        ),
                    )
                except Exception:
                    _hide_table = False
                if not _hide_table:
                    direct_formatted = _basket_html_for_replace(direct_formatted)
                _try_session_export()
                try:
                    from .artifact_export import wants_on_screen_blocks
                    if (
                        export_chips
                        and not wants_on_screen_blocks(
                            _payload_for_screen(
                                primary_artifact or last_tabulable_payload,
                            ),
                        )
                    ):
                        _hide_table = True
                except Exception:
                    if export_chips:
                        _hide_table = True
                if _hide_table and export_chips:
                    direct_formatted = ''
                _stamp_refused_note()
                waiting_meta = (
                    not export_attached
                    and export_meta_nudged
                    and round_n == export_meta_nudge_round
                )
                if waiting_meta:
                    stop_after_direct = False
                    if not _hide_table:
                        yield {
                            "event": "replace",
                            "content": direct_formatted,
                        }
                elif stop_after_direct or skip_table_footer:
                    # Skill HTML / lacónico / stop explícito: sin 2.ª vuelta LLM.
                    # Si es skill y el proveedor no es lacónico, pie cálido LOCAL
                    # (servidor) — humanos lo echan de menos; Sonnet inventaba el año.
                    if local_warm_footer and direct_formatted:
                        from .mcp_tool_payload import append_local_warm_footer
                        direct_formatted = append_local_warm_footer(
                            direct_formatted,
                            footer_text=local_footer_text or _('Here you go. If you need anything else, just tell me.'),
                        )
                    finished_with_answer = True
                    if direct_formatted or (_hide_table and export_chips):
                        yield {"event": "replace", "content": direct_formatted or ''}
                    break
                elif round_n >= MAX_ROUNDS:
                    # Última ronda permitida: entregar tabla sin exigir pie LLM extra.
                    if local_warm_footer and direct_formatted:
                        from .mcp_tool_payload import append_local_warm_footer
                        direct_formatted = append_local_warm_footer(
                            direct_formatted,
                            footer_text=local_footer_text or _('Here you go. If you need anything else, just tell me.'),
                        )
                    elif not skip_table_footer and direct_formatted:
                        from .mcp_tool_payload import append_local_warm_footer
                        direct_formatted = append_local_warm_footer(
                            direct_formatted,
                            footer_text=_('Here you go. If you need anything else, just tell me.'),
                        )
                    finished_with_answer = True
                    if direct_formatted:
                        yield {"event": "replace", "content": direct_formatted}
                    break
                else:
                    # Modelo capaz: tabla + pie conversacional breve (sin cifras).
                    if direct_formatted:
                        yield {"event": "replace", "content": direct_formatted}
                    try:
                        _rows = max(0, str(direct_formatted).count('<tr') - 1)
                    except Exception:
                        _rows = None
                    if messages and messages[-1].get('role') == 'tool':
                        messages[-1]['content'] = json.dumps({
                            'data_rendered': True,
                            'rows_rendered': _rows,
                            'primary_delivered': True,
                            'note': (
                                'El documento principal YA está en pantalla '
                                '(%s fila(s) renderizadas). Las tools siguientes '
                                'solo pueden MEJORARLO (previous_result / raw_data) '
                                'o añadir un documento menor. PROHIBIDO emitir un '
                                'volcado autónomo que lo sustituya u oculte. Si ese '
                                'número es 0 o MUY inferior a lo pedido (p. ej. te '
                                'pidieron "los 50" y hay 0/unas pocas), NO afirmes '
                                'que estan todos: tu filtro es casi seguro erróneo '
                                '(ojo REGIÓN vs PROVINCIA). Corrige el código y '
                                'VUELVE A LLAMAR a la herramienta. Si las filas '
                                'coinciden con lo pedido, escribe 1–2 frases de '
                                'cierre CÁLIDAS y NO reproduzcas la tabla. PROHIBIDO '
                                'en ese cierre: cifras, importes, fechas, años, '
                                'periodos, nombres propios, totales o "insights" '
                                'numéricos — el artefacto visible es la fuente de '
                                'verdad; el pie solo puede ser acogida u oferta de '
                                'ayuda ("si quieres otro periodo…"), SIN nombrar el '
                                'año ni el periodo.'
                            ) % (_rows if _rows is not None else '¿?'),
                        }, ensure_ascii=False)
                    direct_formatted = None
            
            elif export_attached and stop_after_direct:
                # Named export with hidden table: empty bubble + session chip.
                # Chatboo must treat empty acc + assistant_files/clip_data as
                # success, not "the model returned no content". Partial refuse
                # (PDF + Word) still paints a note in the bubble.
                finished_with_answer = True
                _stamp_refused_note()
                if direct_formatted:
                    yield {
                        "event": "replace",
                        "content": direct_formatted,
                    }
                break

            # Si el turno finalizó habiendo ejecutado tools, el while continuará
            # para enviar los resultados al LLM y obtener la respuesta final.

        if not export_attached:
            _ex = self._attach_requested_file_export(
                _orig, session_id,
                rows=turn_query_data,
                payload=_payload_for_screen(
                    primary_artifact or last_tabulable_payload,
                ),
            )
            if _ex and _ex.get('acted'):
                export_attached = True
                _absorb_export_result(_ex)
                if not export_clip_data:
                    try:
                        from .artifact_export import clip_data_from_payload
                        export_clip_data = clip_data_from_payload(
                            primary_artifact or last_tabulable_payload,
                            turn_query_data,
                        )
                    except Exception:
                        export_clip_data = None

        if export_attached and not finished_with_answer:
            finished_with_answer = True
            _stamp_refused_note()
            _body = ''
            if not export_chips:
                _body = _('Could not build the download file.')
            elif direct_formatted:
                _body = direct_formatted
            if _body:
                yield {
                    "event": "replace",
                    "content": _body,
                }

        # Red de seguridad: se agotaron las rondas (MAX_ROUNDS) sin respuesta final.
        # Nunca volcar ERROR (-NNNN) / Details JSON al usuario.
        if not finished_with_answer and not (
            primary_artifact and table_already_delivered
        ):
            from .error_ux import humanize_exhausted_tool_error

            human, is_perm = humanize_exhausted_tool_error(last_retry_error or '')
            if is_perm and human:
                # Permiso denegado: solo la razón (Odoo/ACL ya habla claro).
                notice = human
            else:
                notice = _(
                    'I could not complete the request after several automatic '
                    'attempts to fix the generated code.'
                )
                if human:
                    notice += '\n\n' + human
            yield {"event": "token", "content": notice}

        # Fin de Stream: adjuntamos qué modelo/proveedor respondió y los tokens
        # del TURNO (suma de rondas). context_tokens = ocupación de la última
        # ronda (el % del buffer). NUNCA exponemos endpoint ni infra.
        usage_out = dict(turn_usage) if turn_usage else {}
        if usage_out and not usage_out.get("total_tokens"):
            _p = usage_out.get("prompt_tokens") or 0
            _c = usage_out.get("completion_tokens") or 0
            if _p or _c:
                usage_out = dict(usage_out, total_tokens=_p + _c)
        if last_round_total:
            usage_out = dict(usage_out, context_tokens=last_round_total)
        # On-premises: advertise cost=0 when the API omitted price.
        try:
            usage_out = advertise_cost(
                usage_out,
                bool(getattr(provider, 'is_on_premise', False)),
            )
        except Exception:
            pass

        try:
            if turn_usage and provider:
                self.env['ai.provider.usage.day'].increment_for_turn(
                    provider, usage_out or turn_usage,
                )
                if (
                    getattr(provider, 'usage_support', 'unknown') == 'unknown'
                    and usage_has_tokens(turn_usage)
                ):
                    provider._mark_usage_support_yes()
        except Exception:
            _logger.warning(
                'Could not persist daily usage for provider %s',
                getattr(provider, 'name', '?'),
                exc_info=True,
            )

        # Histórico: cierre del turno (auditoría) con los tokens del turno.
        self._mcp_log(
            operation_type='read',
            tool_name='orchestration_summary',
            request_type='LLM',
            agent_llm=model_name,
            result_summary=_('Turn completed · %(n)s LLM round(s)') % {'n': round_n},
            prompt_tokens=(usage_out or {}).get('prompt_tokens'),
            completion_tokens=(usage_out or {}).get('completion_tokens'),
            total_tokens=(usage_out or {}).get('total_tokens'),
        )
        try:
            from .display_currency import get_display_currency
            _done_display_currency = get_display_currency(self.env)
        except Exception:
            _done_display_currency = 'USD'
        _visible = direct_formatted or ''
        if not _visible:
            for _m in reversed(messages):
                if _m.get('role') == 'user':
                    break
                if _m.get('role') != 'assistant' or _m.get('tool_calls'):
                    continue
                _cand = _m.get('content') or ''
                if _cand and not str(_cand).lstrip().startswith('[On-screen artifact'):
                    _visible = _cand
                    break
        _payload = None
        if isinstance(primary_artifact, dict):
            _payload = primary_artifact
        elif last_tabulable_payload:
            _payload = last_tabulable_payload
        try:
            from .history_compact import append_turn_stub
            _llm_history = append_turn_stub(
                kept_history, message,
                payload=_payload, visible=_visible,
            )
        except Exception:
            _logger.debug(
                'AgentEngine: could not build LLM history stubs',
                exc_info=True,
            )
            _llm_history = list(kept_history)
        _done = {
            "event": "done",
            "session_id": session_id,
            "model": model_name,
            "provider": provider.name,
            "protocol": provider.protocol,
            "context_limit": provider.context_window or 0,
            "display_currency": _done_display_currency,
            "usage": usage_out or {},
            "sources": sorted(external_sources) if external_sources else [],
            "records": collected_records,
            "painter": getattr(
                self, '_turn_painter', None,
            ) or ('painter-free' if remote_llm_format else 'painter-local'),
            "correlation_id": getattr(self, '_turn_corr', None) or '',
            "history": _llm_history,
        }
        if export_chips:
            try:
                from .session_download import coalesce_download_chips
                _done['assistant_files'] = coalesce_download_chips(
                    export_chips,
                )
            except Exception:
                _done['assistant_files'] = list(export_chips)
        if export_clip_data:
            _done['clip_data'] = export_clip_data
        yield _done

    def _intercept_session_file_propose(
        self, user_message, session_id, tool_args, rows=None, payload=None,
    ):
        """Block caja B dumps of a named download onto orphan ir.attachment.

        Returns a fake tool result (never creates ``ai.safe.operation``), or
        None when the plan is not a session-file propose. If rows already
        exist, persist the server-serialized chip and ignore LLM bytes.
        """
        try:
            from .artifact_export import (
                requested_named_format,
                is_session_file_propose,
                SESSION_FILE_PROPOSE_ERROR,
                SESSION_FILE_ATTACHED_NOTE,
            )
        except Exception:
            return None
        if not requested_named_format(user_message):
            return None
        steps = None
        if isinstance(tool_args, dict):
            steps = tool_args.get('steps')
        if not is_session_file_propose(steps):
            return None
        attached = False
        chips = []
        refused_tokens = []
        _ex = self._attach_requested_file_export(
            user_message, session_id, rows=rows, payload=payload,
        )
        chip = None
        if _ex and _ex.get('acted'):
            attached = True
            try:
                from .artifact_export import export_result_chips
                chips = export_result_chips(_ex)
            except Exception:
                chips = []
            chip = chips[0] if chips else _ex.get('chip')
            refused_tokens = list(_ex.get('refused_tokens') or [])
            body = {
                'success': True,
                'session_file': True,
                'note': SESSION_FILE_ATTACHED_NOTE,
            }
        else:
            body = {
                'success': False,
                'error': SESSION_FILE_PROPOSE_ERROR,
            }
        return {
            'result': {
                'content': [{
                    'type': 'text',
                    'text': json.dumps(body, ensure_ascii=False),
                }],
            },
            'attached': attached,
            'acted': attached,
            'chip': chip,
            'chips': chips,
            'refused_tokens': refused_tokens,
        }

    def _attach_requested_file_export(
        self, user_message, session_id, rows=None, payload=None,
    ):
        """Serialize known download formats from this turn's rows, if asked.

        Deterministic file-type tokens only (no locale verb list). One
        card per unique kind. Named formats hide the server table unless
        ``__show_table__``. PPT does not serialize. Word uses this
        turn's ``formatted_text`` when ``__rich_doc__`` is set.
        """
        try:
            from .artifact_export import apply_requested_exports
        except Exception:
            return None
        def _persist(raw, filename, mimetype):
            from .session_download import (
                persist_chatboo_session_file,
                merge_download_chips_into_session,
            )
            chip = persist_chatboo_session_file(
                self.env, session_id, raw, filename, mimetype=mimetype,
            )
            if chip:
                merge_download_chips_into_session(self.env, session_id, [chip])
            return chip
        try:
            result = apply_requested_exports(
                user_message,
                rows=rows,
                payload=payload,
                persist=_persist,
                prompt=user_message,
                env=self.env,
                client_fulfill=bool(session_id),
            )
            pending = [
                chip for chip in (result or {}).get('chips') or []
                if isinstance(chip, dict) and chip.get('pending')
            ]
            if pending and session_id:
                from .session_download import merge_download_chips_into_session
                merge_download_chips_into_session(
                    self.env, session_id, pending,
                )
            return result
        except Exception:
            _logger.warning(
                'AgentEngine: requested file export failed',
                exc_info=True,
            )
            return None

    def _log_agent_tool_step(self, tool_name, tool_args, result_str, model_name):
        # relaxaicode registra en tool_relaxaicode (incl. code_to_execute)
        if (tool_name or '').lower() == 'relaxaicode':
            return
        operation_type = 'read'
        result_summary = '← Tool→ORCH ' + (result_str or '')[:480]
        if (tool_name or '') == 'propose_safe_operations':
            operation_type = 'write'
            from .mcp_tool_payload import summarize_propose_tool_result
            result_summary = summarize_propose_tool_result(result_str)
        self._mcp_log(
            operation_type=operation_type,
            tool_name=tool_name,
            prompt_data=tool_args,
            result_summary=result_summary,
            request_type='tool',
            agent_llm=model_name,
        )
