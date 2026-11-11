# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""Main HTTP controller for the MCP server."""

import hmac
import json
import logging
import re
import ast
import os
import builtins as _builtins
from odoo import _, http
from odoo import SUPERUSER_ID
from odoo.http import request
from odoo.exceptions import AccessError, ValidationError, UserError
from odoo.tools import misc
from odoo.tools.safe_eval import safe_eval
from werkzeug.exceptions import Unauthorized, BadRequest, InternalServerError
from werkzeug.wrappers import Response

# Import common utilities and classes
from .utils import APIKeyLogFilter, MCPJSONRPCError, _logger
from ..utils.context_utils import strip_xml_metadata, resolve_placeholders  # Import XML utilities


# Import context tools
from .tools_context import (
    refuse_foreign_identity_pack,
    tool_get_context,
)

# Import relaxaicode tools
from .tools_relaxaicode import (
    tool_relaxaicode
)

# Import utilities from the vendored drivers/LLM package
try:
    from ..lib.llm.utils import extract_user_token_from_request
except ImportError:
    _logger.error("❌ Cannot import extract_user_token_from_request from lib.llm")
    extract_user_token_from_request = None

# Deterministic hash to check the incoming API key against the stored hash.
from ..utils.api_key import hash_api_key
from ..utils.mcp_origin import ICP_MCP_ALLOWED_ORIGINS, origin_allowed
from ..utils.mcp_protocol import (
    client_info_from_params,
    detect_mcp_era,
    discover_result,
    header_protocol_mismatch,
    protocol_version_from_request,
    validate_modern_protocol_version,
    wrap_modern_result,
)

# Import the decorator system and automatic registry
from .mcp_decorators import (
    list_registered_tools_for_mcp,
    get_tool_function,
    get_tool_metadata,
    tool_visible_to,
)

# Import write-check functions
from .safe_operation import (
    cancel_pending_verifications_for_user
)

# Import controller helper functions
from .controller_helpers import (
    mcp_user_has_group,
    check_mcp_permissions,
    get_env_for_operation,
    get_readonly_env,
)

# SessionStore for the standalone SSE transport (Antigravity)
from ..utils.session_store import SessionStore
from ..utils.mcp_correlation import (
    ensure_turn,
    next_turn_step,
    bind_session_turn,
    next_turn_step_for_session,
)



# Import context-building functions
from .context_builder import (
    build_safe_context,
    guarded_import
)


def _session_is_callers(sess):
    """The SSE session was opened with the key of the user making this call."""
    caller = getattr(request, 'mcp_user_id', None)
    return bool(caller) and getattr(sess, 'mcp_user_id', None) == caller


class MCPServerController(http.Controller):
    """HTTP controller for the MCP server, per the official Anthropic spec"""
    
    # Note: contexts/prompts are fetched on demand through prompts/list and prompts/get
    # as the MCP standard says. There is no cache, since the client asks for prompts
    # explicitly when it needs them; they are not injected automatically.
    

    def _log_mcp_operation(self, operation_type, tool_name, prompt_data=None, result_data=None, result_summary=None, additional_info=None, code_to_execute=None, request_type=None, payload_type=None, context_type=None, agent_llm=None):
        """
        Log an MCP operation in the Odoo log using the robust model method.
        """
        try:
            mcp_user_id = getattr(request, 'mcp_user_id', None)
            if not mcp_user_id:
                # No key, no user: nothing to attribute the row to.
                _logger.info(
                    "MCP: unauthenticated %s (%s) not stored in ai.log",
                    tool_name, result_summary or '',
                )
                return
            env = request.env(user=mcp_user_id)
            
            # CRITICAL: extract agent_llm automatically if it is not given
            # It must appear in ALL MCP requests, not only in relaxaicode
            if agent_llm is None:
                agent_llm = getattr(request, 'mcp_agent_llm', None)
            # Fallback: the external MCP client (Cursor, Claude...) sends no
            # X-MCP-LLM header and the model lives in the client, not in Odoo. We use the
            # client name captured at initialize so "Modelo" is not left empty.
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
            # Set default types when none are given
            if not request_type:
                if tool_name in ['tools/list', 'prompts/list', 'system/initialize']:
                    request_type = 'system'
                else:
                    request_type = 'tool'
            
            # Payload Subtype calculation is handled by _create_log_entry if not provided
            
            # context_type calculation can also be handled here or passed to additional info
            # For now, we keep the specific context_type logic or rely on model computation
            
            # Delegate to model method which handles serialization, truncation, and size limits safely.
            # payload_type/context_type are no longer forwarded: ai.log derives its
            # functional category from primitive + endpoint.
            if 'ai.log' in env:
                turn_id, turn_step = self._resolve_mcp_log_turn()
                env['ai.log']._create_log_entry(
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
                    turn=turn_id,
                    turn_step=turn_step,
                    source_channel='mcp_client',
                    remote_ip=remote_ip,
                )
            else:
                 _logger.warning("MCP: Model ai.log not found, skipping log")
                
        except Exception as e:
            _logger.error("MCP: Error recording log (delegate): %s", str(e))


    def _get_mcp_env(self):
        """
        Get the Odoo environment using the MCP user tied to the API key.
        No MCP user, no environment: never the superuser.
        """
        mcp_user_id = getattr(request, 'mcp_user_id', None)
        if not mcp_user_id:
            raise AccessError('MCP request without an authenticated user.')
        return request.env(user=mcp_user_id)


    def _get_user_locale(self):
        """
        Resolve the locale with the intrinsic cascade only (see docs/GESTION_LOCALE_Y_DISCRIMINACION_PAIS.md).

        AI for internal use: there is always an Odoo user. Payload and Router (OpenAI, OVH, DeepSeek, etc.)
        do not drive the locale, so external providers cannot change algorithms that depend
        on the user's language/country.

        Cascade: Odoo user > Company language > Default en_US.
        """
        try:
            # 1. User (mcp_user or session)
            user = getattr(request, 'mcp_user', None)
            if not user:
                user = request.env.user.sudo()
            if user and user.id and user.lang:
                if user.lang != 'en_US' or not self._get_company_lang():
                    _logger.info(f"MCP LOCALE: [Intrinsic-User] {user.lang} ({user.name})")
                    return user.lang

            # 2. Company language (Odoo instance)
            company_lang = self._get_company_lang()
            if company_lang:
                _logger.info(f"MCP LOCALE: [Intrinsic-Company] {company_lang}")
                return company_lang

            # 3. Default
            _logger.warning("MCP LOCALE: [Intrinsic-Default] en_US")
            return 'en_US'

        except Exception as e:
            _logger.error(f"MCP: Critical error getting locale: {e}")
            return 'en_US'
            
    def _get_company_lang(self):
        try:
            return request.env.company.sudo().partner_id.lang
        except:
            return None

    def _resolve_locale_placeholders(self, text_content):
        """
        Replace dynamic placeholders ({locale}, {odoo_version}, etc.) 
        with the shared utility.
        """
        return resolve_placeholders(text_content, request.env, controller=self)

    @http.route('/mcp', type='http', auth='none', save_session=False, methods=['OPTIONS'], csrf=False, cors='*')
    def mcp_options(self, **kwargs):
        """
        Handle OPTIONS requests (CORS preflight) for MCP HTTP clients.
        """
        if not self._mcp_origin_ok():
            return Response(status=403)
        response = Response()
        response.headers['Access-Control-Allow-Origin'] = self._mcp_cors_origin()
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
        """OPTIONS for standalone SSE endpoints (CORS preflight)."""
        if not self._mcp_origin_ok():
            return Response(status=403)
        response = Response()
        response.headers['Access-Control-Allow-Origin'] = self._mcp_cors_origin()
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

    @http.route('/mcp/<string:agent_code>/sse', type='http', auth='none', save_session=False, readonly=False, methods=['GET', 'POST'], csrf=False, cors='*')
    def mcp_sse_endpoint_agent(self, agent_code, **kwargs):
        return self.mcp_sse_endpoint(agent_code=agent_code, **kwargs)

    @http.route('/mcp/<string:agent_code>/message', type='http', auth='none', save_session=False, readonly=False, methods=['POST'], csrf=False, cors='*')
    def mcp_message_endpoint_agent(self, agent_code, **kwargs):
        return self.mcp_message_endpoint(agent_code=agent_code, **kwargs)

    @http.route('/mcp/<string:agent_code>', type='http', auth='none', save_session=False, methods=['GET'], csrf=False, cors='*')
    def mcp_endpoint_sse_agent(self, agent_code, **kwargs):
        return self.mcp_endpoint_sse(agent_code=agent_code, **kwargs)

    @http.route('/mcp/<string:agent_code>', type='http', auth='none', save_session=False, readonly=False, methods=['POST'], csrf=False, cors='*')
    def mcp_endpoint_agent(self, agent_code, **kwargs):
        return self.mcp_endpoint(agent_code=agent_code, **kwargs)

    def _mcp_request_origin(self):
        try:
            return request.httprequest.headers.get('Origin')
        except Exception:
            return None

    def _mcp_origin_ok(self):
        origin = self._mcp_request_origin()
        if not origin:
            return True
        try:
            icp = request.env['ir.config_parameter'].sudo()
            allowed = icp.get_param(ICP_MCP_ALLOWED_ORIGINS, '')
            base = icp.get_param('web.base.url', '')
        except Exception:
            allowed, base = '', ''
        return origin_allowed(origin, allowed, base)

    def _mcp_origin_error(self):
        return self._mcp_json_http_response({
            'jsonrpc': '2.0',
            'error': {'code': -32000, 'message': 'Origin not allowed'},
            'id': None,
        }, status=403)

    def _mcp_cors_origin(self):
        # Entry points have already rejected a disallowed Origin; echo the
        # caller's own Origin instead of '*'. No Origin (desktop clients)
        # keeps '*'.
        return self._mcp_request_origin() or '*'

    def _mcp_json_http_response(self, body, status=200, extra_headers=None):
        """Explicit JSON-RPC response (Streamable HTTP / Cursor V2)."""
        response = Response(
            json.dumps(body, default=str),
            status=status,
            mimetype='application/json',
        )
        response.headers['Access-Control-Allow-Origin'] = self._mcp_cors_origin()
        response.headers['Access-Control-Expose-Headers'] = 'Mcp-Session-Id'
        if extra_headers:
            for key, value in extra_headers.items():
                response.headers[key] = value
        return response

    def _get_mcp_base_url(self):
        """Get the base URL to build absolute URIs (SSE endpoint)."""
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

    def _mcp_conversational_denied(self, user):
        """English error if the bound agent is conversational and the user is not.

        Closed jobs (flag off) skip this door. Missing bind already 404s.
        """
        from ..utils.conversational import (
            user_may_use_conversational_agent, REFUSED_MESSAGE,
        )
        env = request.env(user=SUPERUSER_ID)
        if user_may_use_conversational_agent(
            env, user, agent_code=self._get_mcp_agent_code(),
        ):
            return None
        return REFUSED_MESSAGE

    def _mcp_sse_jsonrpc_error(self, message, status):
        response = Response(
            'data: {"jsonrpc":"2.0","error":{"code":-32000,"message":%s},"id":null}\n\n'
            % json.dumps(message),
            mimetype='text/event-stream',
            status=status,
        )
        response.headers['Access-Control-Allow-Origin'] = self._mcp_cors_origin()
        return response

    def _resolve_mcp_log_turn(self, session=None):
        """Return (turn, turn_step) for the current MCP log line."""
        if session is not None:
            turn = bind_session_turn(request, session)
            step = next_turn_step_for_session(request, session)
            return turn, step
        headers = request.httprequest.headers
        session_id = headers.get('Mcp-Session-Id') or request.params.get('session')
        if session_id:
            sess = SessionStore().get(session_id)
            if sess and _session_is_callers(sess):
                turn = bind_session_turn(request, sess)
                step = next_turn_step_for_session(request, sess)
                return turn, step
        turn = ensure_turn(request)
        return turn, next_turn_step(request, turn)

    def _ensure_mcp_request_turn(self):
        """Bind turn id before tool handlers (Streamable HTTP POST /mcp).

        Without this, ``mcp_turn`` was only set when logging *after*
        ``tools/call``, so ``safe_plan_request`` created
        ``ai.safe.operation`` rows without ``turn``.
        """
        try:
            headers = request.httprequest.headers
            session_id = headers.get('Mcp-Session-Id') or request.params.get('session')
            if session_id:
                sess = SessionStore().get(session_id)
                if sess and _session_is_callers(sess):
                    return bind_session_turn(request, sess)
            return ensure_turn(request)
        except Exception:
            return None

    def _extract_api_key(self):
        """
        Extract the API key from the request. Headers only:
        X-MCP-API-Key or Authorization Bearer. The key never travels in the URL.
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
        return api_key.strip() if api_key else None

    def _validate_api_key_sse(self):
        """
        Validate the API key for SSE. Returns (api_key, mcp_user_record) or (None, error_response).
        The key only comes in a header (X-MCP-API-Key, Authorization Bearer).
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
            denied = self._mcp_conversational_denied(mcp_user_record.user_id)
            if denied:
                return None, self._mcp_sse_jsonrpc_error(denied, 403)
            return (api_key, mcp_user_record), None
        except Exception:
            _logger.exception('MCP: SSE API key validation failed')
            return None, Response(
                'data: {"jsonrpc":"2.0","error":{"code":-32000,"message":"Error validating API key"},"id":null}\n\n',
                mimetype='text/event-stream', status=500
            )

    def _sse_stream_generator(self, session_id):
        """Generator that emits SSE events: initial endpoint, keep-alive and messages."""
        store = SessionStore()
        KEEPALIVE_INTERVAL = 15.0

        session = store.get(session_id)
        if session is None:
            return
        try:
            while True:
                msg = store.get_pending(session_id, KEEPALIVE_INTERVAL)
                if msg is None:
                    if store.get(session_id) is None:
                        break
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

    @http.route('/mcp/sse', type='http', auth='none', save_session=False, readonly=False, methods=['GET', 'POST'], csrf=False, cors='*')
    def mcp_sse_endpoint(self, agent_code=None, **kwargs):
        """
        SSE endpoint for Antigravity.
        GET: stream SSE (event:endpoint + event:message).
        POST: JSON-RPC straight in the body (fallback for clients that POST to serverUrl).
        """
        if not self._mcp_origin_ok():
            return self._mcp_origin_error()
        bind_err = self._bind_mcp_agent(agent_code)
        if bind_err:
            err_body = (
                f'data: {{"jsonrpc":"2.0","error":{{"code":-32000,"message":"{bind_err}"}},"id":null}}\n\n'
            )
            resp = Response(err_body, mimetype='text/event-stream', status=404)
            resp.headers['Access-Control-Allow-Origin'] = self._mcp_cors_origin()
            return resp
        if request.httprequest.method == 'POST':
            return self._mcp_sse_post_handler()
        valid, err_resp = self._validate_api_key_sse()
        if err_resp is not None:
            err_resp.headers['Access-Control-Allow-Origin'] = self._mcp_cors_origin()
            return err_resp
        api_key, mcp_user_record = valid
        user = mcp_user_record.user_id
        denied = self._mcp_conversational_denied(user)
        if denied:
            return self._mcp_sse_jsonrpc_error(denied, 403)
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
        response.headers['Access-Control-Allow-Origin'] = self._mcp_cors_origin()
        response.headers['Cache-Control'] = 'no-cache'
        response.headers['Connection'] = 'keep-alive'
        response.headers['X-Accel-Buffering'] = 'no'
        return response

    def _mcp_sse_post_handler(self):
        """
        Handle POST to /mcp/sse (Antigravity sends initialize/tools to serverUrl).
        JSON-RPC response in the body, same as /mcp.
        """
        def _json_error(code, msg, req_id=None, status=200):
            r = Response(
                json.dumps({'jsonrpc': '2.0', 'error': {'code': code, 'message': msg}, 'id': req_id}),
                mimetype='application/json', status=status
            )
            r.headers['Access-Control-Allow-Origin'] = self._mcp_cors_origin()
            return r

        try:
            valid, err_resp = self._validate_api_key_sse()
            if err_resp is not None:
                err_resp.headers['Access-Control-Allow-Origin'] = self._mcp_cors_origin()
                return err_resp
            api_key, mcp_user_record = valid
            user = mcp_user_record.user_id
            denied = self._mcp_conversational_denied(user)
            if denied:
                return self._mcp_sse_jsonrpc_error(denied, 403)
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
                return _json_error(
                    e.error_code, e.error_message, request_id,
                    status=e.http_status,
                )
            except Exception as e:
                _logger.exception("MCP SSE POST: Error in _handle_mcp_method")
                return _json_error(-32603, str(e), request_id)

            if is_notification:
                return Response('', status=202, mimetype='text/plain')

            if 'error' in result:
                jrpc = {'jsonrpc': '2.0', 'id': request_id, 'error': result['error']}
            else:
                jrpc = {'jsonrpc': '2.0', 'id': request_id, 'result': result}
            r = Response(json.dumps(jrpc, default=str), mimetype='application/json')
            r.headers['Access-Control-Allow-Origin'] = self._mcp_cors_origin()
            return r
        except Exception as e:
            _logger.exception("MCP SSE POST: Unhandled error")
            return _json_error(-32603, str(e), None)

    @http.route('/mcp/message', type='http', auth='none', save_session=False, readonly=False, methods=['POST'], csrf=False, cors='*')
    def mcp_message_endpoint(self, agent_code=None, **kwargs):
        """
        Message endpoint for the standalone SSE transport.
        Takes JSON-RPC by POST, queues the reply for the SSE stream, returns 202.
        """
        if not self._mcp_origin_ok():
            return self._mcp_origin_error()
        bind_err = self._bind_mcp_agent(agent_code)
        if bind_err:
            r = Response(
                json.dumps({'error': {'code': -32000, 'message': bind_err}}),
                status=404, mimetype='application/json',
            )
            r.headers['Access-Control-Allow-Origin'] = self._mcp_cors_origin()
            return r
        session_id = request.params.get('session') or request.httprequest.args.get('session')
        if not session_id:
            r = Response(
                json.dumps({'error': {'code': -32000, 'message': 'Missing session parameter'}}),
                status=400, mimetype='application/json'
            )
            r.headers['Access-Control-Allow-Origin'] = self._mcp_cors_origin()
            return r
        store = SessionStore()
        session = store.get(session_id)
        if session is None:
            r = Response(
                json.dumps({'error': {'code': -32000, 'message': 'Invalid or expired session'}}),
                status=400, mimetype='application/json'
            )
            r.headers['Access-Control-Allow-Origin'] = self._mcp_cors_origin()
            return r

        try:
            data = request.httprequest.get_data(as_text=True)
            payload = json.loads(data) if data else {}
        except Exception as e:
            r = Response(
                json.dumps({'error': {'code': -32700, 'message': f'Parse error: {str(e)}'}}),
                status=400, mimetype='application/json'
            )
            r.headers['Access-Control-Allow-Origin'] = self._mcp_cors_origin()
            return r

        api_key = self._extract_api_key()
        if not api_key or not hmac.compare_digest(
                str(api_key), str(session.api_key or '')):
            r = Response(
                json.dumps({'error': {'code': -32000, 'message': 'API key mismatch or missing'}}),
                status=401, mimetype='application/json'
            )
            r.headers['Access-Control-Allow-Origin'] = self._mcp_cors_origin()
            return r

        # The stream may live for hours: a revoked key or a user switched off
        # stops here, on the next message, not when the stream ends.
        mcp_rec = request.env(user=SUPERUSER_ID)['ai.mcp.user'].search([
            ('mcp_api_key_hash', '=', hash_api_key(api_key))
        ], limit=1)
        user = mcp_rec.user_id
        if (not user or not user.active or user.id != session.mcp_user_id
                or self._mcp_conversational_denied(user)):
            store.close(session_id)
            r = Response(
                json.dumps({'error': {'code': -32000, 'message': 'Invalid API key'}}),
                status=401, mimetype='application/json'
            )
            r.headers['Access-Control-Allow-Origin'] = self._mcp_cors_origin()
            return r
        request.mcp_user_id = user.id
        request.mcp_user = user
        bind_session_turn(request, session)
        headers = request.httprequest.headers
        request.mcp_agent_llm = headers.get('X-MCP-LLM') or headers.get('X-MCP-Agent')

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
        response.headers['Access-Control-Allow-Origin'] = self._mcp_cors_origin()
        return response

    @http.route('/mcp', type='http', auth='none', save_session=False, methods=['GET'], csrf=False, cors='*')
    def mcp_endpoint_sse(self, agent_code=None, **kwargs):
        """GET /mcp offers no server stream.

        Streamable HTTP opens this GET and parses every SSE event as
        JSON-RPC. A result with a null id is rejected and the client drops
        the server. 405 means there is no stream; the client keeps POST.
        The key is still required on POST. ``/mcp/sse`` is the other channel.
        """
        if not self._mcp_origin_ok():
            return self._mcp_origin_error()
        if agent_code is not None:
            bind_err = self._bind_mcp_agent(agent_code)
            if bind_err:
                response = Response(status=404)
                response.headers['Access-Control-Allow-Origin'] = self._mcp_cors_origin()
                return response
        response = Response(status=405)
        response.headers['Allow'] = 'POST, OPTIONS'
        response.headers['Access-Control-Allow-Origin'] = self._mcp_cors_origin()
        return response

    @http.route('/mcp', type='http', auth='none', save_session=False, readonly=False, methods=['POST'], csrf=False, cors='*')
    def mcp_endpoint(self, agent_code=None, **kwargs):
        """
        Main MCP endpoint (POST JSON-RPC).
        type='http' + explicit envelope: Odoo 19 type='jsonrpc' does not wrap result and Cursor V2
        (Streamable HTTP) checks result.serverInfo.
        GET /mcp is 405: that client drops a result whose id is null.
        """
        if not self._mcp_origin_ok():
            return self._mcp_origin_error()
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
            
            # FIX: robustness for clients that send JSON as a string in payload (or a badly parsed body)
            if isinstance(payload, str):
                try:
                    payload = json.loads(payload)
                except Exception:
                    # If it is not valid JSON, keep it as a string (fails below in a controlled way) or empty dict
                    pass
            elif hasattr(payload, 'read'): # In case it is a stream
                 try:
                    payload = json.loads(payload.read())
                 except Exception:
                    pass
            
            # Validate the API key - read the header in several ways
            # The MCP server is neutral: it accepts any valid token, whatever its origin
            api_key = None
            
            # Read headers only once (needed by every method)
            headers = request.httprequest.headers
            
            # Extract agent/LLM from headers for logging (must appear in every MCP request)
            agent_llm = headers.get('X-MCP-LLM') or headers.get('X-MCP-Agent') or None
            if agent_llm:
                _logger.info(f"MCP: Agent/LLM detected in headers: {agent_llm}")
            else:
                _logger.warning("MCP: ⚠️ No X-MCP-LLM or X-MCP-Agent in headers - the agent will not appear in the logs")
            # Store on request for use in every method
            request.mcp_agent_llm = agent_llm
            
            # Preferred method: X-Mcp-Token (HTTP header). External clients
            # (Cursor, Claude Desktop...) send the API key here IN CLEAR; the
            # server hashes it and compares it against mcp_api_key_hash.
            api_key = extract_user_token_from_request(request, server_key=None)
            if not api_key:
                api_key = self._extract_api_key()
            
            if api_key:
                _logger.info("MCP Auth: API key received in a header")

            # Check that the API key is present and not empty
            if api_key is None or (isinstance(api_key, str) and not api_key.strip()):
                raise MCPJSONRPCError(-32000, 'API key required', payload.get('id') if payload else None)
            
            # Normalize the API key (strip spaces)
            api_key = api_key.strip()
            
            # Extra check: make sure it is not empty after normalizing
            if not api_key or len(api_key) == 0:
                raise MCPJSONRPCError(-32000, 'API key required', payload.get('id') if payload else None)
            
            # Look up the user by API key in the ai.mcp.user model
            try:
                env_temp = request.env(user=SUPERUSER_ID)
                
                # Check that the model exists
                if 'ai.mcp.user' not in env_temp:
                    raise MCPJSONRPCError(-32000, 'MCP user model not available', payload.get('id') if payload else None)
                
                mcp_user_record = env_temp['ai.mcp.user'].search([
                    ('mcp_api_key_hash', '=', hash_api_key(api_key))
                ], limit=1)
                
                # Check that a record was found and has an active user
                if not mcp_user_record:
                    raise MCPJSONRPCError(-32000, 'Invalid API key', payload.get('id') if payload else None)
                
                if not mcp_user_record.user_id:
                    raise MCPJSONRPCError(-32000, 'Invalid API key: user not found', payload.get('id') if payload else None)
                
                if not mcp_user_record.user_id.active:
                    raise MCPJSONRPCError(-32000, 'Invalid API key: user inactive', payload.get('id') if payload else None)
                
                # Valid API key, assign the user
                user = mcp_user_record.user_id
                denied = self._mcp_conversational_denied(user)
                if denied:
                    raise MCPJSONRPCError(
                        -32000, denied, payload.get('id') if payload else None,
                    )
                mcp_user = user
                mcp_user_id = user.id

            except MCPJSONRPCError:
                # Re-raise MCP errors as they are
                raise
            except Exception:
                # Error reaching the model (it may not exist, or a database
                # error). The caller is not known yet: no detail goes out.
                _logger.exception('MCP: API key validation failed')
                raise MCPJSONRPCError(
                    -32000, 'Error validating API key',
                    payload.get('id') if payload else None,
                )
            
            # Store the MCP user in the request context
            request.mcp_user = mcp_user
            request.mcp_user_id = mcp_user_id
            # Store the write flag from the MCP record
            # Validate the JSON-RPC format
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

            # Detect whether it is a notification (no id)
            is_notification = request_id is None

            self._ensure_mcp_request_turn()

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
                response = Response('', status=202, mimetype='text/plain')
                response.headers['Access-Control-Allow-Origin'] = self._mcp_cors_origin()
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
                # Try to log the MCP error too
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
            }, status=e.http_status)
        except (Unauthorized, BadRequest, InternalServerError):
            raise

        except Exception as e:
            # -- CENTRALIZED ERROR LOGGING --
            _logger.exception("MCP: Error processing request")
            
            # Try to log the error in the database
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
                pass # Do not fail if logging the error fails
            # -------------------------------

            request_id = payload.get('id') if 'payload' in locals() and isinstance(payload, dict) else None
            _logger.exception('MCP: internal error')
            message = (
                'Internal error: %s' % e if getattr(request, 'mcp_user_id', None)
                else 'Internal error'
            )
            return self._mcp_json_http_response({
                'jsonrpc': '2.0',
                'id': request_id,
                'error': {'code': -32603, 'message': message},
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
            mcp_uid = getattr(request, 'mcp_user_id', None)
            if not mcp_uid:
                return
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
        Handle the standard MCP methods per the official spec.
        
        Args:
            method: MCP method name
            params: method parameters
            is_notification: True if it is a notification (needs no reply)
            era: ``legacy`` (initialize handshake) or ``modern`` (stateless 2026-07-28)
        """
        # Handle notifications
        if is_notification:
            if method == 'notifications/initialized':
                # Initialization notification - needs no reply
                _logger.debug("MCP: Initialization notification received")
                return {}
            else:
                # Other unknown notification - ignore it without error
                _logger.debug("MCP: Unknown notification ignored: %s", method)
                return {}
        
        # Handle methods (requests that expect a reply)
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
        initialize method per the MCP spec.
        Opens the connection and returns the server capabilities.
        protocolVersion is required; without it Antigravity and other clients refuse the connection.
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
        tools/list method per the MCP spec.
        Lists every available tool.
        Includes the current user's permission info.
        """
        # Get the permissions of the authenticated MCP user (API key), not request.env.user
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
        cap_text = ', '.join(caps) if caps else 'read only'

        perm_info_read = (
            " ℹ️ PERMISSIONS: reading is always allowed. Active capabilities: %s."
            % cap_text
        )

        perm_info_write = ""
        if not has_write:
            perm_info_write = (
                " ⚠️ PERMISSION DENIED: requires AI Writer (group_ai_writer). "
                "Active capabilities: %s." % cap_text
            )
        else:
            perm_info_write = " ✅ PERMISSIONS: AI Writer active."
        
        # Helper to add permission info to descriptions
        def add_perm_info(desc, is_write=False):
            if is_write:
                return desc + perm_info_write
            return desc + perm_info_read
        
        # Automatic registry; expose_mcp=False (e.g. get_context) is not listed here.
        # Internal hosts read the whole set through AgentEngine.get_tools_schema.
        registered_tools = list_registered_tools_for_mcp()
        mcp_user = self._get_mcp_env().user
        tools = []
        for tool_name, tool_data in registered_tools.items():
            if not tool_visible_to(tool_data, mcp_user):
                continue
            tools.append({
                'name': tool_data['name'],
                'description': add_perm_info(tool_data['description'], tool_data['is_write']),
                'inputSchema': tool_data['inputSchema']
            })

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
        tools/call method per the MCP spec.
        Runs one specific tool.
        Catches errors and logs full prompts.
        """
        tool_name = params.get('name')
        arguments = params.get('arguments', {})
        
        # Keep the full prompt (all params) for logging
        # It is passed as is and _create_log_entry serializes it
        prompt_data_full = params

        if not tool_name:
            error_response = {
                'error': {
                    'code': -32602,
                    'message': 'Missing required parameter: name'
                }
            }

            return error_response

        # Get the operation type from the tool registry, not
        # from a list of names. relaxaicode declares is_write but
        # decides inside whether the code writes: it applies the group gate
        # itself when it detects a write.
        operation_type = 'read'
        tool_metadata = get_tool_metadata(tool_name) if tool_name else None
        if tool_metadata and tool_metadata.get('is_write') and tool_name != 'relaxaicode':
            operation_type = 'write'

        # IMPORTANT: check permissions BEFORE running write tools
        # This avoids useless work and token spend when there are no permissions
        if operation_type == 'write':
            # Check the group_ai_writer flag FIRST (before any other operation)
            if not mcp_user_has_group('pns_ai_mcp.group_ai_writer'):
                user_id = request.mcp_user_id
                mcp_user = request.mcp_user if hasattr(request, 'mcp_user') else None
                
                # Get the user name for the error message
                user_name = _("unknown")
                if mcp_user:
                    user_name = mcp_user.name or mcp_user.login or _("unknown")
                elif user_id:
                    try:
                        temp_env = request.env(user=SUPERUSER_ID)
                        user_record = temp_env['res.users'].browse(user_id)
                        if user_record.exists():
                            user_name = user_record.name or user_record.login or _("unknown")
                    except:
                        pass
                
                _logger.warning(f"MCP: User {user_name} (ID: {user_id}) has no write permission on the MCP server (not in group_ai_writer) for tool {tool_name}. Aborting immediately.")
                
                # Automatically cancel all pending checks of this user
                cancelled_count = self._cancel_pending_verifications_for_user(user_id, f"missing write permission (not in group_ai_writer) for tool {tool_name}")
                
                # Plain, direct error message
                message = _('User "%s" has no write permission on the MCP server. Operation aborted.') % user_name
                
                # Use the content format so the AI interface shows it
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
                
                # Permission error log (RESTORED)
                self._log_mcp_operation(
                    operation_type='write', # It is a write attempt
                    tool_name=tool_name,
                    prompt_data=params,
                    result_data=error_response,
                    result_summary=f"Permission Denied: {message}",
                    request_type='tool',
                    additional_info="Blocked by not in group_ai_writer check"
                )
                
                return error_response
        
        # Run the matching tool, catching errors
        result = None
        error_occurred = False
        error_message = None
        error_traceback = None
        
        try:
            # Get the function from the automatic registry
            tool_function = get_tool_function(tool_name)
            
            if tool_function:
                # Tool registered automatically by the decorator
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
                
                # Unknown tool log (RESTORED)
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
            # Catch an exception during execution
            error_occurred = True
            error_message = str(e)
            import traceback
            error_traceback = traceback.format_exc()
            # The request ends in a commit: half a failed tool must not land.
            # What the tool already committed itself (a confirmed plan) stays.
            request.env.cr.rollback()
            if not hasattr(request.env, 'invalidate_all'):
                request.env['base'].invalidate_cache()
            
            # Build the error response
            result = {
                'error': {
                    'code': -32603,
                    'message': f'Error running tool {tool_name}: {error_message}'
                }
            }
            
            # The error is logged further below
        
        # Log the operation (except relaxaicode, which has its own logging)
        pass
        
        return result

    def _mcp_prompts_list(self, params):
        """
        prompts/list method per the MCP spec.

        Returns, as first-class prompts: system_prompt (context
        compiled on the fly) and each core/domain context (one per
        base_code). Skills are /slash in the Odoo chat host — not listed
        here (an MCP client cannot invoke them). The body is served on
        demand through prompts/get; get_context stays as a fallback.
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

        # Contexts as first-class MCP prompts (spec-correct). Body served on
        # demand by prompts/get; get_context stays as a universal fallback for
        # clients with weak prompts support.
        try:
            # su keeps the caller's uid: private contexts stay their owner's.
            # An Environment has no sudo(); that is the recordset method.
            env = self._get_mcp_env()(su=True)
            if 'ai.context' in env:
                for ctx in env['ai.context'].get_listable_for_mcp():
                    name = ctx.base_code or ctx.code
                    if name == 'system_prompt':
                        continue
                    prompts.append({
                        'name': name,
                        'title': name,
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
        prompts/get method per the MCP spec.
        Gets one specific prompt with its content and context.
        Looks first in system contexts (context_type=core), then in the rest.
        """
        prompt_name = params.get('name')
        
        if not prompt_name:
            error_response = {
                'error': {
                    'code': -32602,
                    'message': 'Missing required parameter: name'
                }
            }
            # Log the error
            self._log_mcp_operation(
                operation_type='read',
                tool_name='prompts/get',
                prompt_data=params,
                result_data=error_response,
                additional_info="The request does not include the prompt name",
                request_type='tool',
                payload_type='context'
            )
            return error_response
        
        # Special case: system_prompt (context compiled on the fly)
        if prompt_name == 'system_prompt':
            try:
                env = self._get_mcp_env()
                # CRITICAL: use _get_user_locale(), which gets the user language from the API key
                # instead of request.env.context, which always returns en_US
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

    # Look it up in the database using virtualization
        try:
            env = self._get_mcp_env()(su=True)
            blocked = refuse_foreign_identity_pack(self, env, prompt_name)
            if blocked:
                return blocked
            if 'ai.context' in env:
                # Get the base name (in case the AI asks for hr_payroll_ES directly)
                base_name = env['ai.context'].get_base_context_name(prompt_name)
                
                # CRITICAL: compute the user language to pass it to the model
                user_lang = self._get_user_locale()
                
                # Use Smart Loading to get the right version for the user's country
                context = env['ai.context'].get_context_for_country(base_name, user_locale=user_lang)
                
                if context:
                    _logger.info("MCP: Prompt virtualizado: %s -> %s", prompt_name, context.code)
                    # Log context use (Phase 6: Monitoring)
                    try:
                        env['ai.context']._record_context_usage(context.code)
                    except Exception as e:
                        _logger.warning("MCP: Error recording context usage: %s", str(e))
                    
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
                    
                    # Log the successful operation
                    self._log_mcp_operation(
                        operation_type='read',
                        tool_name=prompt_name,
                        prompt_data=params,
                        result_data=result,
                        result_summary=f"Context fetched: {prompt_name} (current={context.code}, type={context.context_type})",
                        request_type='tool',
                        payload_type='context',
                        context_type=context.context_type
                    )
                    
                    return result
                
                _logger.debug("MCP: Context not found in DB: %s", prompt_name)
        except Exception as e:
            _logger.exception("MCP: Error getting DB context: %s", str(e))
        
        # If it was not found anywhere
        error_response = {
            'error': {
                'code': -32602,
                'message': f'Prompt not found: {prompt_name}'
            }
        }
        # Log the error
        self._log_mcp_operation(
            operation_type='read',
            tool_name=prompt_name,
            prompt_data=params,
            result_data=error_response,
            result_summary=f"Prompt not found: {prompt_name}",
            request_type='prompt'
        )
        return error_response


    def _check_mcp_permissions(self, operation_type='read'):
        """Check the user's MCP permissions for the operation type"""
        return check_mcp_permissions(self, operation_type)

    def _get_env_for_operation(self, operation_type='read'):
        """Get the right Odoo environment for the operation type"""
        return get_env_for_operation(self, operation_type)

    def _get_readonly_env(self):
        """Environment on a READ ONLY cursor (box A) to run read-only relaxaicode"""
        return get_readonly_env(self)


    def _cancel_pending_verifications_for_user(self, user_id, reason="missing permissions"):
        """Automatically cancel all pending checks of a user"""
        return cancel_pending_verifications_for_user(user_id, reason)
