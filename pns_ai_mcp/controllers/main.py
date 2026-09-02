# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""Main HTTP controller for the MCP server."""

import json
import logging
import re
import ast
import os
import builtins as _builtins
from odoo import http
from odoo import SUPERUSER_ID
from odoo.http import request
from odoo.exceptions import AccessError, ValidationError, UserError
from odoo.tools import misc
from odoo.tools.safe_eval import safe_eval
from werkzeug.exceptions import Unauthorized, BadRequest, InternalServerError
from werkzeug.wrappers import Response

# Importar utilidades y clases comunes
from .utils import APIKeyLogFilter, MCPJSONRPCError, _logger
from ..utils.context_utils import strip_xml_metadata, resolve_placeholders  # Importar utilidades de XML


# Importar funciones de formateo
from .formatters import (
    format_currency,
    format_percentage,
    format_data_as_html_table,
    format_data_as_csv,
    format_data_as_xml,
    format_data_as_excel,
    format_data_as_pdf
)

# Import herramientas de contextos
from .tools_context import (
    refuse_foreign_identity_pack,
    tool_get_context,
)

# Importar herramientas de relaxaicode
from .tools_relaxaicode import (
    tool_relaxaicode
)

# Importar utilidades del paquete vendored de drivers/LLM
try:
    from ..lib.llm.utils import extract_user_token_from_request
except ImportError:
    _logger.error("❌ Cannot import extract_user_token_from_request from lib.llm")
    extract_user_token_from_request = None

# Hash determinista para validar la API key entrante contra el hash almacenado.
from ..utils.api_key import hash_api_key
from ..utils.mcp_protocol import (
    client_info_from_params,
    detect_mcp_era,
    discover_result,
    header_protocol_mismatch,
    protocol_version_from_request,
    validate_modern_protocol_version,
    wrap_modern_result,
)

# Importar herramientas de mantenimiento del sistema
from .tools_system import (
    tool_clean_system
)

# Importar herramientas de memoria
from .tools_memory import tool_search_memory
from .tools_context_analytics import tool_get_context_usage_stats

# Importar sistema de decoradores y registro automático
from .mcp_decorators import (
    get_registered_tools,
    get_tool_function,
    get_tool_metadata
)

# Importar funciones de verificación de escritura
from .safe_operation import (
    requires_safe_operation,
    check_massive_operation,
    has_recent_operations,
    record_direct_operation,
    cancel_pending_verifications_for_user
)

# Importar funciones auxiliares del controlador
from .controller_helpers import (
    get_mcp_user_record,
    mcp_user_has_group,
    check_mcp_permissions,
    get_env_for_operation,
    get_readonly_env,
    load_module_manifest
)

# SessionStore para transporte SSE standalone (Antigravity)
from ..utils.session_store import SessionStore
from ..utils.mcp_correlation import (
    ensure_turn_correlation,
    next_step_seq,
    bind_session_correlation,
    next_step_for_session,
)



# Importar funciones de validación
from .validators import (
    validate_relaxaicode_source_ast,
    detect_dangerous_operations
)

# Importar funciones de construcción de contexto
from .context_builder import (
    build_safe_context,
    guarded_import
)


class MCPServerController(http.Controller):
    """Controlador HTTP para servidor MCP según especificación oficial de Anthropic"""
    
    # Nota: Los contextos/prompts se obtienen bajo demanda mediante prompts/list y prompts/get
    # según el estándar MCP. No se mantiene caché ya que los prompts se solicitan explícitamente
    # cuando el cliente los necesita, no se inyectan automáticamente.
    

    def _log_mcp_operation(self, operation_type, tool_name, prompt_data=None, result_data=None, result_summary=None, additional_info=None, code_to_execute=None, request_type=None, payload_type=None, context_type=None, agent_llm=None):
        """
        Registra una operación MCP en el log de Odoo usando el método del modelo robusto.
        """
        try:
            # Obtener usuario
            mcp_user_id = getattr(request, 'mcp_user_id', SUPERUSER_ID)
            env = request.env(user=mcp_user_id)
            
            # CRÍTICO: Extraer agent_llm automáticamente si no se proporciona
            # Debe aparecer en TODAS las peticiones MCP, no solo en relaxaicode
            if agent_llm is None:
                agent_llm = getattr(request, 'mcp_agent_llm', None)
            # Fallback: el cliente MCP externo (Cursor, Claude...) no envía cabecera
            # X-MCP-LLM y el modelo vive en el cliente, no en Odoo. Usamos el nombre
            # del cliente capturado en el initialize para no dejar "Modelo" vacío.
            if agent_llm is None:
                try:
                    from ..utils.session_store import MCPClientRegistry
                    agent_llm = MCPClientRegistry().get(mcp_user_id, env=env)
                except Exception:
                    agent_llm = None
            
            from ..utils.mcp_logging import normalize_remote_ip
            remote_ip = normalize_remote_ip(
                getattr(request.httprequest, 'remote_addr', None)
                if getattr(request, 'httprequest', None) else None)
            # Determinar tipos por defecto si no se especifican
            if not request_type:
                if tool_name in ['tools/list', 'resources/list', 'prompts/list', 'system/initialize']:
                    request_type = 'system'
                else:
                    request_type = 'tool'
            
            # Payload Subtype calculation is handled by create_log_entry if not provided
            
            # context_type calculation can also be handled here or passed to additional info
            # For now, we keep the specific context_type logic or rely on model computation
            
            # Delegate to model method which handles serialization, truncation, and size limits safely.
            # payload_type/context_type are no longer forwarded: ai.log derives its
            # functional category from primitive + endpoint.
            if 'ai.log' in env:
                corr_id, step_seq = self._resolve_mcp_log_correlation()
                env['ai.log'].create_log_entry(
                    user_id=mcp_user_id,
                    operation_type=operation_type,
                    tool_name=tool_name,
                    prompt_data=prompt_data,
                    result_data=result_data,
                    result_summary=result_summary,
                    additional_info=additional_info,
                    code_to_execute=code_to_execute,
                    request_type=request_type,
                    agent_llm=agent_llm,
                    correlation_id=corr_id,
                    step_seq=step_seq,
                    source_channel='mcp_client',
                    remote_ip=remote_ip,
                )
            else:
                 _logger.warning("MCP: Model ai.log not found, skipping log")
                
        except Exception as e:
            _logger.error("MCP: Error registrando log (delegate): %s", str(e))

    def _format_data_as_html_table(self, data, title, columns_config):
        """Formatea datos tabulares como HTML - delega a formatters.py"""
        return format_data_as_html_table(data, title, columns_config)

    def _format_data_as_csv(self, data, columns_config):
        """Formatea datos tabulares como CSV - delega a formatters.py"""
        return format_data_as_csv(data, columns_config)

    def _format_data_as_xml(self, data, root_name, item_name, columns_config):
        """Formatea datos tabulares como XML - delega a formatters.py"""
        return format_data_as_xml(data, root_name, item_name, columns_config)

    def _format_data_as_excel(self, data, columns_config, title="Reporte"):
        """Formatea datos tabulares como Excel - delega a formatters.py"""
        return format_data_as_excel(data, columns_config, title)

    def _format_data_as_pdf(self, data, columns_config, title="Reporte"):
        """Formatea datos tabulares como PDF - delega a formatters.py"""
        return format_data_as_pdf(data, columns_config, title)

    def _get_mcp_env(self):
        """
        Obtiene el entorno de Odoo usando el usuario MCP asociado a la API key.
        Si no hay usuario MCP, usa SUPERUSER_ID.
        """
        mcp_user_id = getattr(request, 'mcp_user_id', SUPERUSER_ID)
        return request.env(user=mcp_user_id)
    
    def _normalize_locale(self, lang_code):
        """Normaliza códigos de idioma a formato Odoo (xx_XX)"""
        if not lang_code:
            return None
        # Convertir guiones a guiones bajos
        code = lang_code.replace('-', '_')
        # Formato xx_XX
        parts = code.split('_')
        if len(parts) == 2:
            return f"{parts[0].lower()}_{parts[1].upper()}"
        return code # Devolver tal cual si no es xx_XX (ej: "es")

    def _get_user_locale(self):
        """
        Resuelve locale solo con cascada intrínseca (ver docs/GESTION_LOCALE_Y_DISCRIMINACION_PAIS.md).

        IA de consumo interno: siempre hay usuario Odoo. Payload y Router (OpenAI, OVH, DeepSeek, etc.)
        no condicionan el locale para evitar que proveedores externos alteren algoritmos dependientes
        del idioma/país del usuario.

        Cascada: User Odoo > Idioma compañía > Default en_US.
        """
        try:
            # 1. User (mcp_user o sesión)
            user = getattr(request, 'mcp_user', None)
            if not user:
                user = request.env.user.sudo()
            if user and user.id and user.lang:
                if user.lang != 'en_US' or not self._get_company_lang():
                    _logger.info(f"MCP LOCALE: [Intrínseco-User] {user.lang} ({user.name})")
                    return user.lang

            # 2. Idioma compañía (instancia Odoo)
            company_lang = self._get_company_lang()
            if company_lang:
                _logger.info(f"MCP LOCALE: [Intrínseco-Compañía] {company_lang}")
                return company_lang

            # 3. Default
            _logger.warning("MCP LOCALE: [Intrínseco-Default] en_US")
            return 'en_US'

        except Exception as e:
            _logger.error(f"MCP: Error crítico obteniendo locale: {e}")
            return 'en_US'
            
    def _get_company_lang(self):
        try:
            return request.env.company.sudo().partner_id.lang
        except:
            return None

    def _resolve_locale_placeholders(self, text_content):
        """
        Reemplaza placeholders dinámicos ({locale}, {odoo_version}, etc.) 
        usando la utilidad compartida.
        """
        return resolve_placeholders(text_content, request.env, controller=self)

    @http.route('/mcp', type='http', auth='none', save_session=False, methods=['OPTIONS'], csrf=False, cors='*')
    def mcp_options(self, **kwargs):
        """
        Maneja peticiones OPTIONS (preflight CORS) para clientes HTTP MCP.
        """
        response = Response()
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS, DELETE'
        response.headers['Access-Control-Allow-Headers'] = (
            'Content-Type, X-MCP-API-Key, Authorization, Accept, '
            'Mcp-Session-Id, MCP-Protocol-Version, Mcp-Method, Mcp-Name'
        )
        response.headers['Access-Control-Expose-Headers'] = 'Mcp-Session-Id'
        response.headers['Access-Control-Max-Age'] = '3600'
        return response

    @http.route('/mcp/sse', type='http', auth='none', save_session=False, methods=['OPTIONS'], csrf=False, cors='*')
    @http.route('/mcp/message', type='http', auth='none', save_session=False, methods=['OPTIONS'], csrf=False, cors='*')
    def mcp_sse_options(self, **kwargs):
        """OPTIONS para endpoints SSE standalone (CORS preflight)."""
        response = Response()
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS, DELETE'
        response.headers['Access-Control-Allow-Headers'] = (
            'Content-Type, X-MCP-API-Key, Authorization, Accept, '
            'Mcp-Session-Id, MCP-Protocol-Version, Mcp-Method, Mcp-Name'
        )
        response.headers['Access-Control-Expose-Headers'] = 'Mcp-Session-Id'
        response.headers['Access-Control-Max-Age'] = '3600'
        return response

    @http.route('/mcp/<string:agent_code>', type='http', auth='none', save_session=False, methods=['OPTIONS'], csrf=False, cors='*')
    def mcp_options_agent(self, agent_code, **kwargs):
        return self.mcp_options(**kwargs)

    @http.route('/mcp/<string:agent_code>/sse', type='http', auth='none', save_session=False, methods=['OPTIONS'], csrf=False, cors='*')
    @http.route('/mcp/<string:agent_code>/message', type='http', auth='none', save_session=False, methods=['OPTIONS'], csrf=False, cors='*')
    def mcp_sse_options_agent(self, agent_code, **kwargs):
        return self.mcp_sse_options(**kwargs)

    @http.route('/mcp/<string:agent_code>/sse', type='http', auth='none', save_session=False, methods=['GET', 'POST'], csrf=False, cors='*')
    def mcp_sse_endpoint_agent(self, agent_code, **kwargs):
        return self.mcp_sse_endpoint(agent_code=agent_code, **kwargs)

    @http.route('/mcp/<string:agent_code>/message', type='http', auth='none', save_session=False, methods=['POST'], csrf=False, cors='*')
    def mcp_message_endpoint_agent(self, agent_code, **kwargs):
        return self.mcp_message_endpoint(agent_code=agent_code, **kwargs)

    @http.route('/mcp/<string:agent_code>', type='http', auth='none', save_session=False, methods=['GET'], csrf=False, cors='*')
    def mcp_endpoint_sse_agent(self, agent_code, **kwargs):
        return self.mcp_endpoint_sse(agent_code=agent_code, **kwargs)

    @http.route('/mcp/<string:agent_code>', type='http', auth='none', save_session=False, methods=['POST'], csrf=False, cors='*')
    def mcp_endpoint_agent(self, agent_code, **kwargs):
        return self.mcp_endpoint(agent_code=agent_code, **kwargs)

    def _mcp_json_http_response(self, body, status=200, extra_headers=None):
        """Respuesta JSON-RPC explícita (Streamable HTTP / Cursor V2)."""
        response = Response(
            json.dumps(body, default=str),
            status=status,
            mimetype='application/json',
        )
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Access-Control-Expose-Headers'] = 'Mcp-Session-Id'
        if extra_headers:
            for key, value in extra_headers.items():
                response.headers[key] = value
        return response

    def _get_mcp_base_url(self):
        """Obtiene la URL base para construir URIs absolutas (SSE endpoint)."""
        try:
            base = request.env['ir.config_parameter'].sudo().get_param('web.base.url', '')
            if base:
                return base.rstrip('/')
        except Exception:
            pass
        try:
            req = request.httprequest
            scheme = req.environ.get('HTTP_X_FORWARDED_PROTO', req.scheme)
            host = req.environ.get('HTTP_X_FORWARDED_HOST', req.host)
            return f"{scheme}://{host}"
        except Exception:
            return 'http://localhost'

    _MCP_RESERVED_PATH_SEGMENTS = frozenset({'sse', 'message'})

    def _bind_mcp_agent(self, agent_code=None):
        """Resolve MCP agent from path; set request.mcp_agent_code. Returns error text or None."""
        if agent_code in self._MCP_RESERVED_PATH_SEGMENTS:
            return 'Invalid MCP agent: reserved path segment.'
        try:
            env = request.env(user=SUPERUSER_ID)
            request.mcp_agent_code = env['ai.agent'].resolve_mcp_agent_code(agent_code)
            return None
        except UserError as e:
            return e.args[0] if e.args else str(e)

    def _get_mcp_agent_code(self):
        return getattr(request, 'mcp_agent_code', None) or ''

    def _resolve_mcp_log_correlation(self, session=None):
        """Return (correlation_id, step_seq) for the current MCP log line."""
        if session is not None:
            corr = bind_session_correlation(request, session)
            step = next_step_for_session(request, session)
            return corr, step
        headers = request.httprequest.headers
        session_id = headers.get('Mcp-Session-Id') or request.params.get('session')
        if session_id:
            sess = SessionStore().get(session_id)
            if sess:
                corr = bind_session_correlation(request, sess)
                step = next_step_for_session(request, sess)
                return corr, step
        corr = ensure_turn_correlation(request)
        return corr, next_step_seq(request, corr)

    def _ensure_mcp_request_correlation(self):
        """Bind turn correlation before tool handlers (Streamable HTTP POST /mcp).

        Without this, ``mcp_corr_id`` was only set when logging *after*
        ``tools/call``, so ``propose_safe_operations`` created
        ``ai.safe.operation`` rows without ``correlation_id``.
        """
        try:
            headers = request.httprequest.headers
            session_id = headers.get('Mcp-Session-Id') or request.params.get('session')
            if session_id:
                sess = SessionStore().get(session_id)
                if sess:
                    return bind_session_correlation(request, sess)
            return ensure_turn_correlation(request)
        except Exception:
            return None

    def _extract_api_key(self):
        """
        Extrae API key de la petición.
        Orden: cabecera (X-MCP-API-Key, Authorization Bearer) primero, luego URL.
        """
        headers = request.httprequest.headers
        api_key = headers.get('X-MCP-API-Key') or headers.get('HTTP_X_MCP_API_KEY')
        if not api_key:
            auth = headers.get('Authorization') or headers.get('HTTP_AUTHORIZATION')
            if auth and str(auth).startswith('Bearer '):
                api_key = str(auth)[7:].strip()
        if not api_key:
            environ = request.httprequest.environ
            api_key = environ.get('HTTP_X_MCP_API_KEY')
            if not api_key:
                auth_env = environ.get('HTTP_AUTHORIZATION') or ''
                if auth_env.startswith('Bearer '):
                    api_key = auth_env[7:].strip()
        if not api_key:
            api_key = request.params.get('api_key') or request.httprequest.args.get('api_key')
        return api_key.strip() if api_key else None

    def _validate_api_key_sse(self):
        """
        Valida API key para SSE. Retorna (api_key, mcp_user_record) o (None, error_response).
        Prioridad: cabecera (X-MCP-API-Key, Authorization Bearer) > URL.
        """
        api_key = self._extract_api_key()

        if not api_key:
            return None, Response(
                'data: {"jsonrpc":"2.0","error":{"code":-32000,"message":"API key required"},"id":null}\n\n',
                mimetype='text/event-stream', status=401
            )

        try:
            env_temp = request.env(user=SUPERUSER_ID)
            if 'ai.mcp.user' not in env_temp:
                return None, Response(
                    'data: {"jsonrpc":"2.0","error":{"code":-32000,"message":"MCP user model not available"},"id":null}\n\n',
                    mimetype='text/event-stream', status=500
                )
            mcp_user_record = env_temp['ai.mcp.user'].search([
                ('mcp_api_key_hash', '=', hash_api_key(api_key))
            ], limit=1)
            if not mcp_user_record or not mcp_user_record.user_id or not mcp_user_record.user_id.active:
                return None, Response(
                    'data: {"jsonrpc":"2.0","error":{"code":-32000,"message":"Invalid API key"},"id":null}\n\n',
                    mimetype='text/event-stream', status=401
                )
            return (api_key, mcp_user_record), None
        except Exception as e:
            return None, Response(
                f'data: {{"jsonrpc":"2.0","error":{{"code":-32000,"message":"{str(e)}"}},"id":null}}\n\n',
                mimetype='text/event-stream', status=500
            )

    def _sse_stream_generator(self, session_id):
        """Generator que emite eventos SSE: endpoint inicial, keep-alive y mensajes."""
        store = SessionStore()
        KEEPALIVE_INTERVAL = 15.0

        session = store.get(session_id)
        if session is None:
            return
        try:
            while True:
                msg = store.get_pending(session_id, KEEPALIVE_INTERVAL)
                if msg is None:
                    yield b': keep-alive\n\n'
                    continue
                if isinstance(msg, dict) and msg.get('_sse_close'):
                    break
                yield b'event: message\n'
                yield ('data: ' + json.dumps(msg, default=str) + '\n\n').encode('utf-8')
        except GeneratorExit:
            pass
        finally:
            store.close(session_id)

    @http.route('/mcp/sse', type='http', auth='none', save_session=False, methods=['GET', 'POST'], csrf=False, cors='*')
    def mcp_sse_endpoint(self, agent_code=None, **kwargs):
        """
        Endpoint SSE para Antigravity.
        GET: stream SSE (event:endpoint + event:message).
        POST: JSON-RPC directo en body (fallback para clientes que POSTean a serverUrl).
        """
        bind_err = self._bind_mcp_agent(agent_code)
        if bind_err:
            err_body = (
                f'data: {{"jsonrpc":"2.0","error":{{"code":-32000,"message":"{bind_err}"}},"id":null}}\n\n'
            )
            resp = Response(err_body, mimetype='text/event-stream', status=404)
            resp.headers['Access-Control-Allow-Origin'] = '*'
            return resp
        if request.httprequest.method == 'POST':
            return self._mcp_sse_post_handler()
        valid, err_resp = self._validate_api_key_sse()
        if err_resp is not None:
            err_resp.headers['Access-Control-Allow-Origin'] = '*'
            return err_resp
        api_key, mcp_user_record = valid
        user = mcp_user_record.user_id
        request.mcp_user = user
        request.mcp_user_id = user.id
        base_url = self._get_mcp_base_url()
        store = SessionStore()
        session_id, message_url = store.create(
            api_key, base_url, user.id, agent_code=self._get_mcp_agent_code() or None,
        )

        def stream():
            yield b'event: endpoint\n'
            yield ('data: ' + json.dumps({'url': message_url}) + '\n\n').encode('utf-8')
            for chunk in self._sse_stream_generator(session_id):
                yield chunk if isinstance(chunk, bytes) else chunk.encode('utf-8')

        response = Response(
            stream(),
            mimetype='text/event-stream',
            direct_passthrough=True
        )
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Cache-Control'] = 'no-cache'
        response.headers['Connection'] = 'keep-alive'
        response.headers['X-Accel-Buffering'] = 'no'
        return response

    def _mcp_sse_post_handler(self):
        """
        Maneja POST a /mcp/sse (Antigravity envía initialize/tools a serverUrl).
        Respuesta JSON-RPC en body, igual que /mcp.
        """
        def _json_error(code, msg, req_id=None):
            r = Response(
                json.dumps({'jsonrpc': '2.0', 'error': {'code': code, 'message': msg}, 'id': req_id}),
                mimetype='application/json', status=200
            )
            r.headers['Access-Control-Allow-Origin'] = '*'
            return r

        try:
            valid, err_resp = self._validate_api_key_sse()
            if err_resp is not None:
                err_resp.headers['Access-Control-Allow-Origin'] = '*'
                return err_resp
            api_key, mcp_user_record = valid
            user = mcp_user_record.user_id
            request.mcp_user = user
            request.mcp_user_id = user.id
            try:
                data = request.httprequest.get_data(as_text=True)
                payload = json.loads(data) if data else {}
            except Exception:
                payload = {}

            if not isinstance(payload, dict) or payload.get('jsonrpc') != '2.0':
                return _json_error(-32600, 'Invalid Request', None)

            method = payload.get('method')
            params = payload.get('params', {})
            request_id = payload.get('id')
            is_notification = request_id is None

            try:
                result = self._handle_mcp_method(method, params, is_notification)
            except MCPJSONRPCError as e:
                return _json_error(e.error_code, e.error_message, request_id)
            except Exception as e:
                _logger.exception("MCP SSE POST: Error in _handle_mcp_method")
                return _json_error(-32603, str(e), request_id)

            if is_notification:
                return Response('', status=204, mimetype='text/plain')

            if 'error' in result:
                jrpc = {'jsonrpc': '2.0', 'id': request_id, 'error': result['error']}
            else:
                jrpc = {'jsonrpc': '2.0', 'id': request_id, 'result': result}
            r = Response(json.dumps(jrpc, default=str), mimetype='application/json')
            r.headers['Access-Control-Allow-Origin'] = '*'
            return r
        except Exception as e:
            _logger.exception("MCP SSE POST: Unhandled error")
            return _json_error(-32603, str(e), None)

    @http.route('/mcp/message', type='http', auth='none', save_session=False, methods=['POST'], csrf=False, cors='*')
    def mcp_message_endpoint(self, agent_code=None, **kwargs):
        """
        Endpoint de mensajes para transporte SSE standalone.
        Recibe JSON-RPC por POST, encola respuesta para el stream SSE, devuelve 202.
        """
        bind_err = self._bind_mcp_agent(agent_code)
        if bind_err:
            r = Response(
                json.dumps({'error': {'code': -32000, 'message': bind_err}}),
                status=404, mimetype='application/json',
            )
            r.headers['Access-Control-Allow-Origin'] = '*'
            return r
        session_id = request.params.get('session') or request.httprequest.args.get('session')
        if not session_id:
            r = Response(
                json.dumps({'error': {'code': -32000, 'message': 'Missing session parameter'}}),
                status=400, mimetype='application/json'
            )
            r.headers['Access-Control-Allow-Origin'] = '*'
            return r
        store = SessionStore()
        session = store.get(session_id)
        if session is None:
            r = Response(
                json.dumps({'error': {'code': -32000, 'message': 'Invalid or expired session'}}),
                status=400, mimetype='application/json'
            )
            r.headers['Access-Control-Allow-Origin'] = '*'
            return r

        try:
            data = request.httprequest.get_data(as_text=True)
            payload = json.loads(data) if data else {}
        except Exception as e:
            r = Response(
                json.dumps({'error': {'code': -32700, 'message': f'Parse error: {str(e)}'}}),
                status=400, mimetype='application/json'
            )
            r.headers['Access-Control-Allow-Origin'] = '*'
            return r

        api_key = self._extract_api_key()
        if not api_key or api_key != session.api_key:
            r = Response(
                json.dumps({'error': {'code': -32000, 'message': 'API key mismatch or missing'}}),
                status=401, mimetype='application/json'
            )
            r.headers['Access-Control-Allow-Origin'] = '*'
            return r

        request.mcp_user_id = session.mcp_user_id or SUPERUSER_ID
        request.mcp_user = request.env['res.users'].browse(request.mcp_user_id)
        bind_session_correlation(request, session)
        headers = request.httprequest.headers
        request.mcp_agent_llm = headers.get('X-MCP-LLM') or headers.get('X-MCP-Agent')
        try:
            mcp_rec = request.env(user=SUPERUSER_ID)['ai.mcp.user'].search([
                ('mcp_api_key_hash', '=', hash_api_key(session.api_key))
            ], limit=1)
            if mcp_rec:
                if mcp_rec.user_id:
                    request.mcp_user_id = mcp_rec.user_id.id
                    request.mcp_user = mcp_rec.user_id
        except Exception:
            pass

        method = payload.get('method')
        params = payload.get('params', {})
        request_id = payload.get('id')
        is_notification = request_id is None

        try:
            result = self._handle_mcp_method(method, params, is_notification)
        except Exception as e:
            result = {'error': {'code': -32603, 'message': str(e)}}

        if not is_notification:
            if 'error' in result:
                jrpc = {'jsonrpc': '2.0', 'id': request_id, 'error': result['error']}
            else:
                jrpc = {'jsonrpc': '2.0', 'id': request_id, 'result': result}
            store.enqueue_response(session_id, jrpc)

        response = Response('', status=202, mimetype='text/plain')
        response.headers['Access-Control-Allow-Origin'] = '*'
        return response

    @http.route('/mcp', type='http', auth='none', save_session=False, methods=['GET'], csrf=False, cors='*')
    def mcp_endpoint_sse(self, agent_code=None, **kwargs):
        """
        Endpoint SSE (Server-Sent Events) para peticiones GET.
        """
        bind_err = self._bind_mcp_agent(agent_code)
        if bind_err:
            response = Response(
                f'data: {{"jsonrpc":"2.0","error":{{"code":-32000,"message":"{bind_err}"}},"id":null}}\n\n',
                mimetype='text/event-stream',
                status=404,
            )
            response.headers['Access-Control-Allow-Origin'] = '*'
            return response
        try:
            # Validar API key
            api_key = None
            headers = request.httprequest.headers
            api_key = headers.get('X-MCP-API-Key')
            if not api_key:
                environ = request.httprequest.environ
                api_key = environ.get('HTTP_X_MCP_API_KEY')
            if not api_key:
                api_key = request.params.get('api_key') or request.httprequest.args.get('api_key')
            
            # Validar API key
            if api_key is None or (isinstance(api_key, str) and not api_key.strip()):
                response = Response(
                    'data: {"jsonrpc":"2.0","error":{"code":-32000,"message":"API key required"},"id":null}\n\n',
                    mimetype='text/event-stream',
                    status=401
                )
                response.headers['Access-Control-Allow-Origin'] = '*'
                return response
            
            api_key = api_key.strip()
            if not api_key or len(api_key) == 0:
                response = Response(
                    'data: {"jsonrpc":"2.0","error":{"code":-32000,"message":"API key required"},"id":null}\n\n',
                    mimetype='text/event-stream',
                    status=401
                )
                response.headers['Access-Control-Allow-Origin'] = '*'
                return response
            
            # Validar usuario
            try:
                env_temp = request.env(user=SUPERUSER_ID)
                if 'ai.mcp.user' not in env_temp:
                    error_msg = 'MCP user model not available'
                    response = Response(
                        f'data: {{"jsonrpc":"2.0","error":{{"code":-32000,"message":"{error_msg}"}},"id":null}}\n\n',
                        mimetype='text/event-stream',
                        status=500
                    )
                    response.headers['Access-Control-Allow-Origin'] = '*'
                    return response
                
                mcp_user_record = env_temp['ai.mcp.user'].search([
                    ('mcp_api_key_hash', '=', hash_api_key(api_key))
                ], limit=1)
                
                if not mcp_user_record or not mcp_user_record.user_id or not mcp_user_record.user_id.active:
                    error_msg = 'Invalid API key'
                    response = Response(
                        f'data: {{"jsonrpc":"2.0","error":{{"code":-32000,"message":"{error_msg}"}},"id":null}}\n\n',
                        mimetype='text/event-stream',
                        status=401
                    )
                    response.headers['Access-Control-Allow-Origin'] = '*'
                    return response
                
                user = mcp_user_record.user_id
                request.mcp_user = user
                request.mcp_user_id = user.id
            except Exception as e:
                error_msg = f'Error validating API key: {str(e)}'
                response = Response(
                    f'data: {{"jsonrpc":"2.0","error":{{"code":-32000,"message":"{error_msg}"}},"id":null}}\n\n',
                    mimetype='text/event-stream',
                    status=500
                )
                response.headers['Access-Control-Allow-Origin'] = '*'
                return response
            
            # Devolver handshake SSE
            response = Response(
                'data: {"jsonrpc":"2.0","result":{"protocolVersion":"2024-11-05","capabilities":{"tools":{"listChanged":false},"prompts":{"listChanged":false},"resources":{"listChanged":false}},"serverInfo":{"name":"pns_ai_mcp","version":"1.0.0"},"instructions":"Use prompts/get(name=\\"system_prompt\\") to load the system knowledge context and start dialogue."},"id":null}\n\n',
                mimetype='text/event-stream'
            )
            response.headers['Access-Control-Allow-Origin'] = '*'
            response.headers['Cache-Control'] = 'no-cache'
            response.headers['Connection'] = 'keep-alive'
            return response
        except Exception as e:
            _logger.exception("MCP: Error procesando petición SSE")
            response = Response(
                f'data: {{"jsonrpc":"2.0","error":{{"code":-32603,"message":"Internal error: {str(e)}"}},"id":null}}\n\n',
                mimetype='text/event-stream',
                status=500
            )
            response.headers['Access-Control-Allow-Origin'] = '*'
            return response

    @http.route('/mcp', type='http', auth='none', save_session=False, methods=['POST'], csrf=False, cors='*')
    def mcp_endpoint(self, agent_code=None, **kwargs):
        """
        Endpoint principal MCP (POST JSON-RPC).
        type='http' + envelope explícito: Odoo 19 type='jsonrpc' no envuelve result y Cursor V2
        (Streamable HTTP) valida result.serverInfo.
        GET SSE: mcp_endpoint_sse.
        """
        bind_err = self._bind_mcp_agent(agent_code)
        if bind_err:
            return self._mcp_json_http_response({
                'jsonrpc': '2.0',
                'id': None,
                'error': {'code': -32000, 'message': bind_err},
            }, status=404)
        api_key = None
        try:
            try:
                raw = request.httprequest.get_data(as_text=True)
                payload = json.loads(raw) if raw else {}
            except Exception:
                payload = {}
            if not isinstance(payload, dict):
                payload = {}
            _logger.info("TRACE_MCP: mcp_endpoint POST method=%s", payload.get('method'))
            
            # FIX: Robustez para clientes que envían JSON como string en payload (o body mal parseado)
            if isinstance(payload, str):
                try:
                    payload = json.loads(payload)
                except Exception:
                    # Si no es JSON válido, mantener como string (fallará abajo controladamente) o dict vacío
                    pass
            elif hasattr(payload, 'read'): # Por si es un stream
                 try:
                    payload = json.loads(payload.read())
                 except Exception:
                    pass
            
            # Validar API key - leer header de múltiples formas
            # El servidor MCP es neutral: valida cualquier token válido, sin importar su origen
            api_key = None
            
            # Obtener headers una sola vez (necesario para todos los métodos)
            headers = request.httprequest.headers
            
            # Extraer agente/LLM de headers para logging (debe aparecer en todas las peticiones MCP)
            agent_llm = headers.get('X-MCP-LLM') or headers.get('X-MCP-Agent') or None
            if agent_llm:
                _logger.info(f"MCP: Agent/LLM detectado en headers: {agent_llm}")
            else:
                _logger.warning("MCP: ⚠️ No se detectó X-MCP-LLM ni X-MCP-Agent en headers - el agente no aparecerá en los logs")
            # Almacenar en request para uso en todos los métodos
            request.mcp_agent_llm = agent_llm
            
            # Método preferido: X-Mcp-Token (header HTTP). Los clientes externos
            # (Cursor, Claude Desktop...) envían aquí la API key EN CLARO; el
            # servidor la hashea y la compara contra mcp_api_key_hash.
            api_key = extract_user_token_from_request(request, server_key=None)
            if not api_key:
                api_key = self._extract_api_key()
            
            if api_key:
                _logger.info(f"MCP Auth: Using X-Mcp-Token: {api_key[:10]}...")
            
            # Fallback para Cursor: query parameter api_key (Cursor no envía headers HTTP)
            if not api_key:
                api_key = request.params.get('api_key') or request.httprequest.args.get('api_key')
                if api_key:
                    _logger.info(f"MCP Auth: Using api_key query parameter: {api_key[:10]}...")
            
            # Validar que la API key esté presente y no esté vacía
            if api_key is None or (isinstance(api_key, str) and not api_key.strip()):
                raise MCPJSONRPCError(-32000, 'API key required', payload.get('id') if payload else None)
            
            # Normalizar API key (eliminar espacios)
            api_key = api_key.strip()
            
            # Validación adicional: asegurar que no esté vacía después de normalizar
            if not api_key or len(api_key) == 0:
                raise MCPJSONRPCError(-32000, 'API key required', payload.get('id') if payload else None)
            
            # Buscar usuario por API key en el modelo ai.mcp.user
            try:
                env_temp = request.env(user=SUPERUSER_ID)
                
                # Verificar que el modelo existe
                if 'ai.mcp.user' not in env_temp:
                    raise MCPJSONRPCError(-32000, 'MCP user model not available', payload.get('id') if payload else None)
                
                mcp_user_record = env_temp['ai.mcp.user'].search([
                    ('mcp_api_key_hash', '=', hash_api_key(api_key))
                ], limit=1)
                
                # Validar que se encontró un registro y que tiene usuario activo
                if not mcp_user_record:
                    raise MCPJSONRPCError(-32000, 'Invalid API key', payload.get('id') if payload else None)
                
                if not mcp_user_record.user_id:
                    raise MCPJSONRPCError(-32000, 'Invalid API key: user not found', payload.get('id') if payload else None)
                
                if not mcp_user_record.user_id.active:
                    raise MCPJSONRPCError(-32000, 'Invalid API key: user inactive', payload.get('id') if payload else None)
                
                # API key válida, asignar usuario
                user = mcp_user_record.user_id
                mcp_user = user
                mcp_user_id = user.id

            except MCPJSONRPCError:
                # Re-lanzar errores MCP tal cual
                raise
            except Exception as e:
                # Error al acceder al modelo (puede no existir o error de base de datos)
                error_msg = f'Error validating API key: {str(e)}'
                raise MCPJSONRPCError(-32000, error_msg, payload.get('id') if payload else None)
            
            # Almacenar usuario MCP en el contexto de la petición
            request.mcp_user = mcp_user
            request.mcp_user_id = mcp_user_id
            # Almacenar flag de escritura desde el registro MCP
            # Validar formato JSON-RPC
            if not isinstance(payload, dict) or payload.get('jsonrpc') != '2.0':
                request_id = payload.get('id') if isinstance(payload, dict) else None
                error_msg_json = 'Invalid Request: JSON-RPC 2.0 required'
                # Log invalid jsonrpc
                try:
                    self._log_mcp_operation(
                        operation_type='read',
                        tool_name='unknown',
                        prompt_data=payload if isinstance(payload, dict) else {'raw': str(payload)[:100]},
                        result_data={'error': error_msg_json},
                        result_summary=f"Error: {error_msg_json}",
                        request_type='system'
                    )
                except: pass
                raise MCPJSONRPCError(-32600, 'Invalid Request', request_id)

            method = payload.get('method')
            params = payload.get('params', {})
            request_id = payload.get('id')

            # Detectar si es una notificación (no tiene id)
            is_notification = request_id is None

            self._ensure_mcp_request_correlation()

            era = detect_mcp_era(method, params, headers)
            request.mcp_protocol_era = era
            http_status = 200

            if era == 'modern':
                mismatch = header_protocol_mismatch(headers, params)
                if mismatch:
                    body = {
                        'jsonrpc': '2.0',
                        'id': request_id,
                        'error': {
                            'code': mismatch['code'],
                            'message': mismatch['message'],
                        },
                    }
                    return self._mcp_json_http_response(body, status=400)

                requested_pv = protocol_version_from_request(params, headers)
                version_err = validate_modern_protocol_version(requested_pv)
                if version_err:
                    body = {
                        'jsonrpc': '2.0',
                        'id': request_id,
                        'error': version_err,
                    }
                    return self._mcp_json_http_response(body, status=400)

                self._register_mcp_client(client_info_from_params(params))

            result = self._handle_mcp_method(method, params, is_notification, era=era)

            if is_notification:
                response = Response('', status=204, mimetype='text/plain')
                response.headers['Access-Control-Allow-Origin'] = '*'
                return response

            extra_headers = {}
            if era == 'legacy' and method == 'initialize' and 'error' not in result and api_key:
                session_id, _msg_url = SessionStore().create(
                    api_key,
                    self._get_mcp_base_url(),
                    getattr(request, 'mcp_user_id', None),
                    agent_code=self._get_mcp_agent_code() or None,
                )
                extra_headers['Mcp-Session-Id'] = session_id

            if 'error' in result:
                err = result['error']
                body = {
                    'jsonrpc': '2.0',
                    'id': request_id,
                    'error': {
                        'code': err.get('code', -32603),
                        'message': err.get('message', 'Unknown error'),
                    },
                }
                if err.get('data') is not None:
                    body['error']['data'] = err['data']
            else:
                if era == 'modern':
                    result = wrap_modern_result(result, method=method)
                body = {'jsonrpc': '2.0', 'id': request_id, 'result': result}

            return self._mcp_json_http_response(body, status=http_status, extra_headers=extra_headers)

        except MCPJSONRPCError as e:
            # Log MCP Error (Auth, Invalid Request, etc)
            try:
                # Intentar registrar el error MCP también
                method_log = payload.get('method', 'unknown') if isinstance(payload, dict) else 'unknown'
                params_log = payload.get('params', {}) if isinstance(payload, dict) else {}
                self._log_mcp_operation(
                    operation_type='read',
                    tool_name=method_log,
                    prompt_data=params_log,
                    result_data={'error': e.error_message, 'code': e.error_code},
                    result_summary=f"MCP Error {e.error_code}: {e.error_message}",
                    request_type='system',
                    additional_info="MCP Protocol Error (Auth or Validation)"
                )
            except:
                pass

            return self._mcp_json_http_response({
                'jsonrpc': '2.0',
                'id': e.request_id,
                'error': {'code': e.error_code, 'message': e.error_message},
            })
        except (Unauthorized, BadRequest, InternalServerError):
            raise

        except Exception as e:
            # -- CENTRALIZED ERROR LOGGING --
            _logger.exception("MCP: Error procesando petición")
            
            # Intentar registrar el error en la base de datos
            try:
                method_log = payload.get('method', 'unknown')
                params_log = payload.get('params', {})
                self._log_mcp_operation(
                    operation_type='read',
                    tool_name=method_log,
                    prompt_data=params_log,
                    result_data={'error': str(e)},
                    result_summary=f"Error: {str(e)}",
                    request_type='system', # Default
                    additional_info=f"Exception: {type(e).__name__}"
                )
            except:
                pass # No fallar si el log de error falla
            # -------------------------------

            request_id = payload.get('id') if 'payload' in locals() and isinstance(payload, dict) else None
            return self._mcp_json_http_response({
                'jsonrpc': '2.0',
                'id': request_id,
                'error': {'code': -32603, 'message': f'Internal error: {str(e)}'},
            })

    def _register_mcp_client(self, client_info):
        """Persist MCP client label from initialize or stateless _meta."""
        try:
            client_info = client_info or {}
            cname = (client_info.get('name') or '').strip()
            cver = (client_info.get('version') or '').strip()
            client_label = (f"{cname} {cver}".strip() if cname else None)
            if not client_label:
                return
            if not getattr(request, 'mcp_agent_llm', None):
                request.mcp_agent_llm = client_label
            from ..utils.session_store import MCPClientRegistry
            mcp_uid = getattr(request, 'mcp_user_id', SUPERUSER_ID)
            remote_ip = None
            try:
                from ..utils.mcp_logging import normalize_remote_ip
                remote_ip = normalize_remote_ip(
                    request.httprequest.remote_addr
                    if getattr(request, 'httprequest', None) else None)
            except Exception:
                pass
            MCPClientRegistry().set(
                mcp_uid, client_label, env=request.env(user=SUPERUSER_ID),
                remote_ip=remote_ip)
        except Exception:
            pass

    def _handle_mcp_method(self, method, params, is_notification=False, era='legacy'):
        """
        Maneja los métodos estándar de MCP según especificación oficial.
        
        Args:
            method: Nombre del método MCP
            params: Parámetros del método
            is_notification: True si es una notificación (no requiere respuesta)
            era: ``legacy`` (initialize handshake) o ``modern`` (stateless 2026-07-28)
        """
        # Manejar notificaciones
        if is_notification:
            if method == 'notifications/initialized':
                # Notificación de inicialización - no requiere respuesta
                _logger.debug("MCP: Notificación de inicialización recibida")
                return {}
            else:
                # Otra notificación desconocida - ignorar sin error
                _logger.debug("MCP: Notificación desconocida ignorada: %s", method)
                return {}
        
        # Manejar métodos (peticiones con respuesta)
        if method == 'server/discover':
            if era != 'modern':
                return {
                    'error': {
                        'code': -32601,
                        'message': f'Method not found: {method}',
                    }
                }
            return self._mcp_server_discover(params)
        elif method == 'initialize':
            return self._mcp_initialize(params)
        elif method == 'tools/list':
            return self._mcp_tools_list(params)
        elif method == 'tools/call':
            return self._mcp_tools_call(params)
        elif method == 'prompts/list':
            return self._mcp_prompts_list(params)
        elif method == 'prompts/get':
            return self._mcp_prompts_get(params)
        elif method == 'resources/list':
            return self._mcp_resources_list(params)
        elif method == 'resources/read':
            return self._mcp_resources_read(params)
        else:
            return {
                'error': {
                    'code': -32601,
                    'message': f'Method not found: {method}'
                }
            }

    def _mcp_server_discover(self, params):
        """Stateless discovery (MCP 2026-07-28)."""
        result = discover_result()
        try:
            self._log_mcp_operation(
                operation_type='read',
                tool_name='server/discover',
                prompt_data=params or {},
                result_data=result,
                result_summary='MCP server/discover',
                request_type='system',
            )
        except Exception:
            pass
        return result

    def _mcp_initialize(self, params):
        """
        Método initialize según especificación MCP.
        Inicializa la conexión y devuelve las capacidades del servidor.
        protocolVersion es obligatorio; sin él Antigravity y otros clientes rechazan la conexión.
        """
        params = params or {}
        client_version = params.get('protocolVersion') or '2024-11-05'
        supported = ('2024-11-05', '2025-03-26', '2025-06-18')
        protocol_version = client_version if client_version in supported else '2024-11-05'

        self._register_mcp_client(params.get('clientInfo') or {})
        result = {
            'protocolVersion': protocol_version,
            'capabilities': {
                'tools': {'listChanged': False},
                'prompts': {'listChanged': False},
                'resources': {'listChanged': False}
            },
            'serverInfo': {
                'name': 'pns_ai_mcp',
                'version': '2.0.0',
            },
            'instructions': 'Use prompts/get(name="system_prompt") to load the system knowledge context and start dialogue. Tools available via tools/list and tools/call.'
        }
        try:
            self._log_mcp_operation(
                operation_type='read',
                tool_name='initialize',
                prompt_data=params,
                result_data=result,
                result_summary="MCP Initialized",
                request_type='system'
            )
        except Exception:
            pass
        return result

    def _mcp_tools_list(self, params):
        """
        Método tools/list según especificación MCP.
        Lista todas las herramientas disponibles.
        Incluye información de permisos del usuario actual.
        """
        # Obtener permisos del usuario MCP autenticado (API key), no request.env.user
        has_write = mcp_user_has_group('pns_ai_mcp.group_ai_writer')
        has_external_url = mcp_user_has_group('pns_ai_mcp.group_ai_external_url')
        has_external_api = mcp_user_has_group('pns_ai_mcp.group_ai_external_api')

        caps = []
        if has_write:
            caps.append('Writer (CRUD)')
        if has_external_url:
            caps.append('External URL')
        if has_external_api:
            caps.append('External API')
        cap_text = ', '.join(caps) if caps else 'solo lectura'

        perm_info_read = (
            " ℹ️ PERMISOS: Lectura siempre permitida. Capacidades activas: %s."
            % cap_text
        )

        perm_info_write = ""
        if not has_write:
            perm_info_write = (
                " ⚠️ PERMISO DENEGADO: requiere AI Writer (group_ai_writer). "
                "Capacidades activas: %s." % cap_text
            )
        else:
            perm_info_write = " ✅ PERMISOS: AI Writer activo."
        
        # Helper para añadir información de permisos a descripciones
        def add_perm_info(desc, is_write=False):
            if is_write:
                return desc + perm_info_write
            return desc + perm_info_read
        
        # Obtener tools del registro automático (decoradores)
        registered_tools = get_registered_tools()
        
        # Construir lista de tools: primero las registradas automáticamente, luego las manuales
        tools = []
        
        # Añadir tools registradas automáticamente (todas las tools están ahora con decoradores)
        for tool_name, tool_data in registered_tools.items():
            tools.append({
                'name': tool_data['name'],
                'description': add_perm_info(tool_data['description'], tool_data['is_write']),
                'inputSchema': tool_data['inputSchema']
            })
        
        # Advertise the available context IDs to the model in a SPEC-LEGAL place:
        # appended to get_context's own `description` (a standard field every MCP
        # client shows the model), instead of a non-standard `availablePrompts`
        # sibling field. This keeps the signal universal without polluting the
        # tool object. Contexts are also published via prompts/list + resources/list
        # for clients that consume those primitives.
        try:
            env = request.env(user=SUPERUSER_ID)
            if 'ai.context' in env:
                context_ids = [
                    (ctx.base_code or ctx.code)
                    for ctx in env['ai.context'].get_listable_for_mcp()
                ]
                if context_ids:
                    hint = (
                        "\n\nAvailable context IDs: " + ", ".join(context_ids)
                        + ". Call get_context(context_name='contexts_index_core') "
                        "for the full registry with descriptions."
                    )
                    for tool in tools:
                        if tool['name'] == 'get_context':
                            tool['description'] = tool['description'] + hint
        except Exception as e:
            _logger.warning("MCP: Error building context hint for tools/list: %s", str(e), exc_info=True)

        result = {
            'tools': tools
        }

        # Log tools list (RESTORED)
        agent_llm = getattr(request, 'mcp_agent_llm', None)
        self._log_mcp_operation(
            operation_type='read',
            tool_name='tools/list',
            prompt_data=params,
            result_data=result, 
            result_summary=f"Listed {len(tools)} tools",
            request_type='system',
            agent_llm=agent_llm
        )
        return result

    def _mcp_tools_call(self, params):
        """
        Método tools/call según especificación MCP.
        Ejecuta una herramienta específica.
        Captura errores y registra prompts completos.
        """
        tool_name = params.get('name')
        arguments = params.get('arguments', {})
        
        # Guardar el prompt completo (params completo) para logging
        # Se pasará directamente y create_log_entry lo serializará
        prompt_data_full = params

        if not tool_name:
            error_response = {
                'error': {
                    'code': -32602,
                    'message': 'Missing required parameter: name'
                }
            }

            return error_response

        # Determinar tipo de operación (por defecto lectura, excepto relaxaicode que se determina dinámicamente)
        operation_type = 'read'
        write_tools = {
            'confirm_write_operation',
            'cancel_write_operation',
        }
        
        if tool_name in write_tools:
            operation_type = 'write'
        elif tool_name == 'relaxaicode':
            # Para relaxaicode, el tipo se determina dentro de la tool
            operation_type = 'read'  # Por defecto, se actualizará dentro de la tool si es escritura
        
        # IMPORTANTE: Verificar permisos ANTES de ejecutar herramientas de escritura
        # Esto evita procesar operaciones innecesarias y consumir tokens cuando no hay permisos
        if operation_type == 'write':
            # Verificar flag group_ai_writer PRIMERO (antes de cualquier otra operación)
            if not mcp_user_has_group('pns_ai_mcp.group_ai_writer'):
                user_id = request.mcp_user_id
                mcp_user = request.mcp_user if hasattr(request, 'mcp_user') else None
                
                # Obtener nombre del usuario para el mensaje de error
                user_name = "desconocido"
                if mcp_user:
                    user_name = mcp_user.name or mcp_user.login or "desconocido"
                elif user_id:
                    try:
                        temp_env = request.env(user=SUPERUSER_ID)
                        user_record = temp_env['res.users'].browse(user_id)
                        if user_record.exists():
                            user_name = user_record.name or user_record.login or "desconocido"
                    except:
                        pass
                
                _logger.warning(f"MCP: Usuario {user_name} (ID: {user_id}) no tiene permiso de escritura con el servidor MCP (not in group_ai_writer) para herramienta {tool_name}. Abortando inmediatamente.")
                
                # Cancelar automáticamente todas las verificaciones pendientes de este usuario
                cancelled_count = self._cancel_pending_verifications_for_user(user_id, f"falta de permisos de escritura (not in group_ai_writer) para herramienta {tool_name}")
                
                # Mensaje de error simple y directo
                message = f'Usuario "{user_name}" no tiene permisos de escritura con el servidor MCP. Operación abortada.'
                
                # Usar formato content para que sea visible en la interfaz de la IA
                error_response = {
                    'content': [
                        {
                            'type': 'text',
                            'text': json.dumps({
                                'error': True,
                                'code': -32000,
                                'message': message,
                                'tool_name': tool_name,
                                'user_name': user_name,
                                'user_id': user_id,
                                'cancelled_operations': cancelled_count
                            }, indent=2, default=str)
                        }
                    ]
                }
                
                # Log de error de permisos (RESTORED)
                self._log_mcp_operation(
                    operation_type='write', # Es un intento de escritura
                    tool_name=tool_name,
                    prompt_data=params,
                    result_data=error_response,
                    result_summary=f"Permission Denied: {message}",
                    request_type='tool',
                    additional_info="Blocked by not in group_ai_writer check"
                )
                
                return error_response
        
        # Ejecutar la herramienta correspondiente con captura de errores
        result = None
        error_occurred = False
        error_message = None
        error_traceback = None
        
        try:
            # Obtener la función del registro automático
            tool_function = get_tool_function(tool_name)
            
            if tool_function:
                # Tool registrada automáticamente con decorador
                tool_metadata = get_tool_metadata(tool_name)
                if tool_metadata and tool_metadata.get('is_write'):
                    operation_type = 'write'
                    
                # Execute tool (Validation is handled inside decorator)
                result = tool_function(self, arguments)

                # [LEGACY ROBUSTNESS] Centralized Logging REMOVED
                # We rely on individual tools to log their own operations.
                pass
            else:
                error_response = {
                    'error': {
                        'code': -32601,
                        'message': f'Unknown tool: {tool_name}'
                    }
                }
                
                # Log de tool desconocida (RESTORED)
                self._log_mcp_operation(
                    operation_type='read',
                    tool_name=tool_name,
                    prompt_data=params,
                    result_data=error_response,
                    result_summary=f"Unknown tool: {tool_name}",
                    request_type='tool'
                )
                
                return error_response
        except Exception as e:
            # Capturar excepción durante la ejecución
            error_occurred = True
            error_message = str(e)
            import traceback
            error_traceback = traceback.format_exc()
            
            # Crear respuesta de error
            result = {
                'error': {
                    'code': -32603,
                    'message': f'Error ejecutando herramienta {tool_name}: {error_message}'
                }
            }
            
            # Log del error ya se registrará más abajo
        
        # Registrar log de operación (excepto para relaxaicode que ya tiene su propio logging)
        pass
        
        return result

    def _mcp_prompts_list(self, params):
        """
        Método prompts/list según especificación MCP.

        Devuelve, como prompts de primera clase: system_prompt (contexto
        compilado dinámicamente), las skills del agente activo y cada contexto
        core/domain (uno por base_code). El cuerpo de cada prompt se sirve bajo
        demanda vía prompts/get; get_context permanece como fallback universal.
        """
        prompts = [{
            'name': 'system_prompt',
            'title': 'System Knowledge Context',
            'description': (
                '[MANDATORY] LOAD FIRST: always-on knowledge (core + locale). '
                'When turn-scoped domain packs are ON, pass optional argument '
                'query with the user question to inject matched domain bodies; '
                'without query a compact DOMAIN_INDEX catalog is appended.'
            ),
            'arguments': [
                {
                    'name': 'query',
                    'description': (
                        'Optional user question / turn text. When set, Odoo '
                        'matches the domain index and injects pack bodies.'
                    ),
                    'required': False,
                },
            ],
        }]

        # Skills (selectable procedures) for the active MCP agent — progressive
        # disclosure: only name + description here, body served by prompts/get.
        try:
            env = self._get_mcp_env()
            skill_agent = self._get_mcp_agent_code()
            if not skill_agent:
                skill_agent = env['ai.agent'].resolve_mcp_agent_code(None)
                request.mcp_agent_code = skill_agent
            if 'ai.skill' in env:
                for skill in env['ai.skill'].get_for_agent(skill_agent):
                    prompts.append({
                        'name': skill.mcp_prompt_name(),
                        'title': skill.name,
                        'description': skill.description or skill.name,
                        'arguments': [],
                    })
        except Exception as e:
            _logger.warning("MCP: Error listing skills for prompts/list: %s", str(e))

        # Contexts as first-class MCP prompts (spec-correct). Body served on
        # demand by prompts/get; get_context stays as a universal fallback for
        # clients with weak prompts support.
        try:
            env = request.env(user=SUPERUSER_ID)
            if 'ai.context' in env:
                for ctx in env['ai.context'].get_listable_for_mcp():
                    prompts.append({
                        'name': ctx.base_code or ctx.code,
                        'title': ctx.base_code or ctx.code,
                        'description': ctx.description or (ctx.base_code or ctx.code),
                        'arguments': [],
                    })
        except Exception as e:
            _logger.warning("MCP: Error listing contexts for prompts/list: %s", str(e))

        result = {'prompts': prompts}
        
        # Log prompts/list
        agent_llm = getattr(request, 'mcp_agent_llm', None)
        self._log_mcp_operation(
            operation_type='read',
            tool_name='prompts/list',
            prompt_data=params,
            result_data=result, 
            result_summary=f"Listed {len(prompts)} prompt (optimized context)",
            request_type='system',
            agent_llm=agent_llm
        )
        
        return result

    def _mcp_prompts_get(self, params):
        """
        Método prompts/get según especificación MCP.
        Obtiene un prompt específico con su contenido y contexto.
        Busca primero en contextos del sistema (context_type=core), luego en el resto.
        """
        prompt_name = params.get('name')
        
        if not prompt_name:
            error_response = {
                'error': {
                    'code': -32602,
                    'message': 'Missing required parameter: name'
                }
            }
            # Registrar log de error
            self._log_mcp_operation(
                operation_type='read',
                tool_name='prompts/get',
                prompt_data=params,
                result_data=error_response,
                additional_info="La petición no incluye el nombre del prompt",
                request_type='tool',
                payload_type='context'
            )
            return error_response
        
        # Special case: system_prompt (contexto compilado dinámicamente)
        if prompt_name == 'system_prompt':
            try:
                env = self._get_mcp_env()
                # CRÍTICO: Usar _get_user_locale() que obtiene el idioma del usuario de la API key
                # en lugar de request.env.context que siempre devuelve en_US
                user_lang = self._get_user_locale()
                
                mcp_agent = self._get_mcp_agent_code()
                if not mcp_agent:
                    mcp_agent = env['ai.agent'].resolve_mcp_agent_code(None)
                    request.mcp_agent_code = mcp_agent
                system_content = env['ai.agent'].get_for_agent(
                    mcp_agent, user_locale=user_lang,
                )
                args = params.get('arguments') or {}
                if not isinstance(args, dict):
                    args = {}
                query = (
                    args.get('query')
                    or args.get('user_message')
                    or args.get('message')
                    or ''
                )
                agent = env['ai.agent'].search(
                    [('code', '=', mcp_agent)], limit=1,
                )
                if agent:
                    system_content = agent.enrich_with_domain_index(
                        system_content,
                        user_message=query,
                        user_locale=user_lang,
                    )
                
                result = {
                    'description': f'System Knowledge Context ({user_lang}, agent={mcp_agent})',
                    'messages': [{
                        'role': 'user',
                        'content': {
                            'type': 'text',
                            'text': system_content
                        }
                    }]
                }
                
                # Log
                self._log_mcp_operation(
                    operation_type='read',
                    tool_name='system_prompt',
                    prompt_data=params,
                    result_data=result,
                    result_summary=f"System prompt generated: {len(system_content)} bytes ({user_lang})",
                    request_type='tool',
                    payload_type='context',
                    context_type='protocol'
                )
                
                return result
            except Exception as e:
                _logger.error(f"MCP: Error generating system prompt: {e}", exc_info=True)
                error_response = {
                    'error': {
                        'code': -32603,
                        'message': f'Error generating system_prompt: {str(e)}'
                    }
                }
                return error_response


        # Skill (selectable procedure) lookup before generic context lookup.
        if prompt_name.startswith('skill.'):
            try:
                env = self._get_mcp_env()
                user_lang = self._get_user_locale()
                skill = env['ai.skill'].get_by_prompt_name(prompt_name)
                if skill:
                    payload = skill.build_prompt_payload(user_locale=user_lang)
                    result = {
                        'description': payload['description'],
                        'messages': [{
                            'role': 'user',
                            'content': {'type': 'text', 'text': payload['text']},
                        }],
                    }
                    self._log_mcp_operation(
                        operation_type='read',
                        tool_name=prompt_name,
                        prompt_data=params,
                        result_data=result,
                        result_summary=f"Skill served: {skill.code} ({user_lang})",
                        request_type='tool',
                        payload_type='context',
                        context_type='protocol'
                    )
                    return result
            except Exception as e:
                _logger.exception("MCP: Error obteniendo skill: %s", str(e))

    # Buscar en base de datos usando virtualización
        try:
            env = request.env(user=SUPERUSER_ID)
            blocked = refuse_foreign_identity_pack(self, env, prompt_name)
            if blocked:
                return blocked
            if 'ai.context' in env:
                # Obtener nombre base (por si acaso la IA pide hr_payroll_ES directamente)
                base_name = env['ai.context'].get_base_context_name(prompt_name)
                
                # CRÍTICO: Calcular idioma del usuario para pasarlo al modelo
                user_lang = self._get_user_locale()
                
                # Usar Smart Loading para obtener la versión correcta según el país del usuario
                context = env['ai.context'].get_context_for_country(base_name, user_locale=user_lang)
                
                if context:
                    _logger.info("MCP: Prompt virtualizado: %s -> %s", prompt_name, context.code)
                    # Registrar uso del contexto (Fase 6: Monitoreo)
                    try:
                        env['ai.context'].record_context_usage(context.code)
                    except Exception as e:
                        _logger.warning("MCP: Error registrando uso de contexto: %s", str(e))
                    
                    # Resolve {locale} placeholders in context content
                    resolved_content = self._resolve_locale_placeholders(context.content)
                    
                    # Clean metadata (headers) to save tokens (peel the onion)
                    resolved_content = strip_xml_metadata(resolved_content)
                    
                    result = {
                        'description': context.description or f'Contexto MCP: {context.code}',
                        'messages': [
                            {
                                'role': 'user',
                                'content': {
                                    'type': 'text',
                                    'text': resolved_content
                                }
                            }
                        ]
                    }
                    
                    # Registrar log de operación exitosa
                    self._log_mcp_operation(
                        operation_type='read',
                        tool_name=prompt_name,
                        prompt_data=params,
                        result_data=result,
                        result_summary=f"Contexto obtenido: {prompt_name} (actual={context.code}, tipo={context.context_type})",
                        request_type='tool',
                        payload_type='context',
                        context_type=context.context_type
                    )
                    
                    return result
                
                _logger.debug("MCP: Contexto no encontrado en BD: %s", prompt_name)
        except Exception as e:
            _logger.exception("MCP: Error obteniendo contexto BD: %s", str(e))
        
        # Si no se encontró en ningún lugar
        error_response = {
            'error': {
                'code': -32602,
                'message': f'Prompt not found: {prompt_name}'
            }
        }
        # Registrar log de error
        self._log_mcp_operation(
            operation_type='read',
            tool_name=prompt_name,
            prompt_data=params,
            result_data=error_response,
            result_summary=f"Prompt no encontrado: {prompt_name}",
            request_type='prompt'
        )
        return error_response

    def _mcp_resources_list(self, params):
        """
        Método resources/list según especificación MCP.

        Expone (a) recursos de sistema (info/version/locale) y (b) cada contexto
        core/domain como recurso legible por URI ``mcp://contexts/<base_code>``.
        Los clientes que respetan `resources` obtienen así el catálogo de forma
        estándar; los que no, siguen teniendo la tool get_context como fallback.
        """
        resources = [
            {
                "uri": "system://info",
                "name": "System Information",
                "description": "USE ONLY IF the user explicitly asks for technical diagnostics, system information, or metadata (like Odoo version, database name, Python version, or MCP Version). DO NOT use this to check the current date or time.",
                "mimeType": "application/json"
            },
            {
                "uri": "system://version",
                "name": "Odoo Version",
                "description": "Odoo version and series information. Use exclusively for queries explicitly requesting the current Odoo version.",
                "mimeType": "application/json"
            },
            {
                "uri": "system://locale",
                "name": "User Locale",
                "description": "Active user language and locale code settings. Use for queries regarding the current interface language or regional configurations.",
                "mimeType": "application/json"
            },
            {
                "uri": "url_whitelist",
                "name": "URL whitelist",
                "description": (
                    "Active egress domains allowed for fetch_url / external "
                    "API. Inspect before proposing fetch_url. Not a user-facing "
                    "results table."
                ),
                "mimeType": "application/json"
            }
        ]

        # Contexts as first-class MCP resources (spec-correct).
        try:
            env = request.env(user=SUPERUSER_ID)
            if 'ai.context' in env:
                for ctx in env['ai.context'].get_listable_for_mcp():
                    base = ctx.base_code or ctx.code
                    resources.append({
                        "uri": "mcp://contexts/%s" % base,
                        "name": base,
                        "description": ctx.description or base,
                        "mimeType": "text/markdown",
                    })
        except Exception as e:
            _logger.warning("MCP: Error listing contexts for resources/list: %s", str(e))

        result = {
            'resources': resources
        }
        
        # Log resources/list (RESTORED)
        agent_llm = getattr(request, 'mcp_agent_llm', None)
        self._log_mcp_operation(
            operation_type='read',
            tool_name='resources/list',
            prompt_data=params,
            result_data=result, 
            result_summary=f"Listed {len(resources)} resources",
            request_type='system',
            agent_llm=agent_llm
        )
        
        return result

    def _mcp_resources_read(self, params):
        """
        Método resources/read según especificación MCP.
        Lee un recurso específico, incluyendo contextos dinámicos.
        """
        uri = params.get('uri')
        
        if not uri:
            error_response = {
                'error': {
                    'code': -32602,
                    'message': 'Missing required parameter: uri'
                }
            }
            # Registrar log de error
            self._log_mcp_operation(
                operation_type='read',
                tool_name='resources/read',
                prompt_data=params,
                result_data=error_response,
                result_summary="Error: Falta parámetro 'uri'",
                additional_info="La petición no incluye el URI del recurso",
                request_type='resource'
            )
            return error_response
        
        
        # Manejar recurso de sistema system://version
        if uri == 'system://version':
            try:
                import odoo.release
                # Clean version strategy: use serie (usually "14.0", "16.0")
                clean_ver = odoo.release.serie
                
                info = {
                    'version': clean_ver,
                    'full_version': odoo.release.version,
                    'serie': odoo.release.serie
                }
                
                result = {
                    'contents': [
                        {
                            'uri': uri,
                            'mimeType': 'application/json',
                            'text': json.dumps(info, indent=2)
                        }
                    ],
                    '__payload_size__': len(json.dumps(info, indent=2)),
                    '__fmt_type__': 'local_json'
                }
                
                self._log_mcp_operation(
                    operation_type='read',
                    tool_name=uri,
                    prompt_data=params,
                    result_data=result,
                    result_summary=f"Version: {clean_ver}",
                    request_type='resource'
                )
                return result
            except Exception as e:
                error_response = {'error': {'code': -32603, 'message': f'Error reading version: {str(e)}'}}
                return error_response

        # Manejar recurso de sistema system://locale
        if uri == 'system://locale':
            try:
                user_lang = self._get_user_locale()
                lang_name = user_lang
                try:
                    env = request.env(user=SUPERUSER_ID)
                    lang_rec = env['res.lang'].search([('code', '=', user_lang)], limit=1)
                    if lang_rec:
                        lang_name = lang_rec.name
                except:
                    pass

                info = {
                    'code': user_lang,
                    'locale': user_lang,  # Alias para clientes que esperan 'locale'
                    'name': lang_name
                }
                
                result = {
                    'contents': [
                        {
                            'uri': uri,
                            'mimeType': 'application/json',
                            'text': json.dumps(info, indent=2)
                        }
                    ],
                    '__payload_size__': len(json.dumps(info, indent=2)),
                    '__fmt_type__': 'local_json'
                }
                
                self._log_mcp_operation(
                    operation_type='read',
                    tool_name=uri,
                    prompt_data=params,
                    result_data=result,
                    result_summary=f"Language: {user_lang}",
                    request_type='resource'
                )
                return result
            except Exception as e:
                error_response = {'error': {'code': -32603, 'message': f'Error reading language: {str(e)}'}}
                return error_response

        # Manejar recurso de sistema system://info
        if uri == 'system://info':
            try:
                from ..utils.system_info import resource_system_info

                env = request.env(user=SUPERUSER_ID)
                info = resource_system_info(env)
                
                result = {
                    'contents': [
                        {
                            'uri': uri,
                            'mimeType': 'application/json',
                            'text': json.dumps(info, indent=2)
                        }
                    ],
                    '__payload_size__': len(json.dumps(info, indent=2)),
                    '__fmt_type__': 'local_json'
                }
                
                # Registrar log
                self._log_mcp_operation(
                    operation_type='read',
                    tool_name=uri,
                    prompt_data=params,
                    result_data=result,
                    result_summary="Recurso de sistema leído",
                    request_type='resource'
                )
                return result
            except Exception as e:
                # Si falla, dejaremos que caiga al error generico o devolvemos error aqui
                _logger.exception("MCP: Error reading system resource: %s", str(e))
                # Fallback to standard error handling below if we re-raise or creating specific error here
                error_response = {
                    'error': {
                        'code': -32603,
                        'message': f'Error reading system resource: {str(e)}'
                    }
                }
                return error_response

        from ..utils.mcp_resources import (
            is_whitelist_uri,
            whitelist_facts,
        )
        if is_whitelist_uri(uri):
            try:
                env = request.env(user=SUPERUSER_ID)
                info = whitelist_facts(env)
                text = json.dumps(info, indent=2, default=str)
                result = {
                    'contents': [
                        {
                            'uri': uri,
                            'mimeType': 'application/json',
                            'text': text,
                        }
                    ],
                    '__payload_size__': len(text),
                    '__fmt_type__': 'local_json',
                }
                self._log_mcp_operation(
                    operation_type='read',
                    tool_name=uri,
                    prompt_data=params,
                    result_data=result,
                    result_summary='URL whitelist (%s)' % info.get('count', 0),
                    request_type='resource',
                )
                return result
            except Exception as e:
                return {
                    'error': {
                        'code': -32603,
                        'message': 'Error reading URL whitelist: %s' % e,
                    }
                }

        # Manejar recursos de contextos dinámicos
        if uri.startswith('mcp://contexts/'):
            context_name = uri.replace('mcp://contexts/', '')
            
            try:
                env = request.env(user=SUPERUSER_ID)
                blocked = refuse_foreign_identity_pack(self, env, context_name)
                if blocked:
                    return blocked
                if 'ai.context' in env:
                    # Resolver por base_code + locale del usuario (igual que prompts/get),
                    # para que mcp://contexts/<base_code> funcione aunque solo existan
                    # variantes locale. Fallback a búsqueda por code exacto.
                    base_name = env['ai.context'].get_base_context_name(context_name)
                    user_lang = self._get_user_locale()
                    context = env['ai.context'].get_context_for_country(base_name, user_locale=user_lang)
                    if not context:
                        context = env['ai.context'].search([
                            ('code', '=', context_name),
                            ('active', '=', True)
                        ], limit=1)

                    if context:
                        # Registrar uso del contexto (Fase 6: Monitoreo)
                        try:
                            env['ai.context'].record_context_usage(context.code)
                        except Exception as e:
                            _logger.warning("MCP: Error registrando uso de contexto: %s", str(e))
                        
                        # Resolve {locale} placeholders in context content
                        resolved_content = self._resolve_locale_placeholders(context.content)
                        
                        # Clean metadata (headers) to save tokens (peel the onion)
                        resolved_content = strip_xml_metadata(resolved_content)
                        
                        result = {
                            'contents': [
                                {
                                    'uri': uri,
                                    'mimeType': 'text/markdown',
                                    'text': resolved_content
                                }
                            ]
                        }
                        
                        # Registrar log de operación exitosa
                        self._log_mcp_operation(
                            operation_type='read',
                            tool_name=uri,
                            prompt_data=params,
                            result_data=result,
                            result_summary=f"Recurso leído: {uri}",
                            request_type='resource'
                        )
                        
                        return result
            except Exception as e:
                _logger.exception("MCP: Error obteniendo contexto desde recurso: %s", str(e))
                error_response = {
                    'error': {
                        'code': -32603,
                        'message': f'Error reading resource: {str(e)}'
                    }
                }
                # Registrar log de error
                self._log_mcp_operation(
                    operation_type='read',
                    tool_name=uri,
                    prompt_data=params,
                    result_data=error_response,
                    result_summary=f"Error leyendo recurso: {str(e)[:200]}",
                    additional_info=f"Traceback: {str(e)}",
                    request_type='resource'
                )
                return error_response
            
            # Contexto no encontrado
            error_response = {
                'error': {
                    'code': -32602,
                    'message': f'Resource not found: {uri}'
                }
            }
            # Registrar log de error
            self._log_mcp_operation(
                operation_type='read',
                tool_name=uri,
                prompt_data=params,
                result_data=error_response,
                result_summary=f"Recurso no encontrado: {uri}",
                request_type='resource'
            )
            return error_response
        
        error_response = {
            'error': {
                'code': -32602,
                'message': f'Resource not found: {uri}. Use mcp://contexts/{{context_name}} for dynamic contexts.'
            }
        }
        # Registrar log de error
        self._log_mcp_operation(
            operation_type='read',
            tool_name=uri,
            prompt_data=params,
            result_data=error_response,
            result_summary=f"Recurso no implementado: {uri}",
            request_type='resource'
        )
        return error_response

    def _get_customers_info_resource(self, resource_type='data'):
        """Resource: clientes = res.partner con ≥1 factura de venta posted."""
        return get_customers_info_resource(self, resource_type)

    def _get_suppliers_info_resource(self, resource_type='data'):
        """Resource: Obtiene información completa de los proveedores (res.partner con supplier_rank > 0)"""
        return get_suppliers_info_resource(self, resource_type)

    def _get_employees_info_resource(self, resource_type='data'):
        """Resource: Obtiene información completa de los empleados (hr.employee)"""
        return get_employees_info_resource(self, resource_type)

    def _get_mcp_info_resource(self, resource_type='data'):
        """Resource: Obtiene información detallada del servidor MCP y su módulo en Odoo"""
        return get_mcp_info_resource(self, resource_type)

    def _get_mcp_user_record(self):
        """Obtiene el registro ai.mcp.user asociado al usuario actual de la petición"""
        return get_mcp_user_record()

    def _check_mcp_permissions(self, operation_type='read'):
        """Verifica los permisos MCP del usuario según el tipo de operación"""
        return check_mcp_permissions(self, operation_type)

    def _get_env_for_operation(self, operation_type='read'):
        """Obtiene el entorno Odoo apropiado según el tipo de operación"""
        return get_env_for_operation(self, operation_type)

    def _get_readonly_env(self):
        """Entorno sobre cursor READ ONLY (caja A) para ejecutar relaxaicode de lectura"""
        return get_readonly_env(self)

    def _load_module_manifest(self, module_name):
        """Lee el manifest de un módulo de forma compatible con versiones anteriores de Odoo"""
        return load_module_manifest(self, module_name)

    def _requires_safe_operation(self, operation_type, model_name, records_count, search_domain=None):
        """Determina si una operación de escritura requiere verificación"""
        return requires_safe_operation(operation_type, model_name, records_count, search_domain)

    def _check_massive_operation(self, operation_type, model_name, tool_name, user_id, records_count=1, time_window_seconds=60):
        """Detecta si una operación es parte de una operación masiva"""
        return check_massive_operation(self, operation_type, model_name, tool_name, user_id, records_count, time_window_seconds)

    def _has_recent_operations(self, operation_type, model_name, tool_name, user_id, time_window_seconds=30):
        """Verifica si hay operaciones recientes para detectar patrones masivos"""
        return has_recent_operations(operation_type, model_name, tool_name, user_id, time_window_seconds)

    def _record_direct_operation(self, operation_type, model_name, tool_name, user_id, records_count):
        """Registra una operación que se ejecutó directamente para detectar patrones masivos"""
        return record_direct_operation(operation_type, model_name, tool_name, user_id, records_count)

    def _cancel_pending_verifications_for_user(self, user_id, reason="falta de permisos"):
        """Cancela automáticamente todas las verificaciones pendientes de un usuario"""
        return cancel_pending_verifications_for_user(user_id, reason)
