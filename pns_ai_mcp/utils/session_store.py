# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""Session store for the standalone MCP SSE transport."""

import logging
import threading
import uuid
from datetime import datetime
from queue import Empty, Queue

from .mcp_correlation import new_correlation_id

_logger = logging.getLogger(__name__)


class Session:
    """Sesión SSE: correlaciona stream con peticiones POST."""

    def __init__(self, session_id: str, api_key: str, mcp_user_id: int = None):
        self.session_id = session_id
        self.api_key = api_key
        self.mcp_user_id = mcp_user_id
        self.correlation_id = new_correlation_id()
        self.step_seq = 0
        self.created_at = datetime.utcnow()
        self.closed = False
        self.queue = Queue()


class MCPClientRegistry:
    """
    Registro en memoria del cliente MCP (nombre + versión) por usuario.

    El protocolo MCP solo envía `clientInfo` en el `initialize`; las llamadas
    posteriores (tools/call, resources/list...) no lo repiten. Aquí guardamos la
    etiqueta del cliente tras el initialize para poder rellenar la columna
    "Modelo/Agente" del histórico en TODAS las filas MCP de esa conexión.

    Nota: es un caché de proceso. Con varios workers Odoo el initialize y las
    llamadas posteriores podrían caer en procesos distintos; en modo threaded
    (dev) o con sticky sessions funciona de forma fiable.
    """

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if hasattr(self, '_clients'):
            return
        self._clients = {}
        self._clients_lock = threading.Lock()

    def set(self, user_id, label, env=None, remote_ip=None):
        if not user_id or not label:
            return
        with self._clients_lock:
            self._clients[user_id] = label
        if env is not None:
            try:
                mu = env['ai.mcp.user'].sudo().search(
                    [('user_id', '=', user_id)], limit=1)
                if mu:
                    mu.register_mcp_client(label, remote_ip=remote_ip)
            except Exception as exc:
                _logger.debug('MCPClientRegistry: DB persist failed: %s', exc)

    def get(self, user_id, env=None):
        if not user_id:
            return None
        with self._clients_lock:
            label = self._clients.get(user_id)
        if label:
            return label
        if env is not None:
            try:
                return env['ai.mcp.user'].get_last_mcp_client_label(user_id)
            except Exception:
                pass
        return None


class SessionStore:
    """
    Store en memoria para sesiones SSE standalone.
    Requiere sticky sessions en proxy si Odoo usa múltiples workers.
    """

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if hasattr(self, '_sessions'):
            return
        self._sessions = {}
        self._sessions_lock = threading.Lock()

    def create(self, api_key: str, base_url: str, mcp_user_id: int = None,
               agent_code: str = None) -> tuple:
        """
        Crea sesión SSE.

        Args:
            api_key: API key validada del cliente.
            base_url: URL base (ej. https://ejemplo.com o https://ejemplo.com/odoo)
            mcp_user_id: ID de usuario Odoo (opcional, cache).
            agent_code: Sufijo de agente en ruta MCP (opcional).

        Returns:
            (session_id, message_url)
        """
        session_id = str(uuid.uuid4())
        base = base_url.rstrip('/')
        if agent_code:
            message_url = f"{base}/mcp/{agent_code}/message?session={session_id}"
        else:
            message_url = f"{base}/mcp/message?session={session_id}"

        with self._sessions_lock:
            session = Session(session_id, api_key, mcp_user_id)
            self._sessions[session_id] = session

        _logger.debug("MCP SSE: Session created: %s", session_id[:8])
        return session_id, message_url

    def get(self, session_id: str):
        """Obtiene sesión activa. Retorna None si no existe o está cerrada."""
        with self._sessions_lock:
            session = self._sessions.get(session_id)
        if session is None or session.closed:
            return None
        return session

    def enqueue_response(self, session_id: str, response: dict) -> bool:
        """
        Encola respuesta JSON-RPC para que el stream SSE la emita.

        Returns:
            True si la sesión existe y no está cerrada.
        """
        session = self.get(session_id)
        if session is None:
            return False
        try:
            session.queue.put_nowait(response)
            return True
        except Exception as e:
            _logger.warning("MCP SSE: Error enqueue: %s", e)
            return False

    def get_pending(self, session_id: str, timeout: float):
        """
        Bloquea hasta que haya respuesta en la cola o timeout.

        Args:
            session_id: ID de sesión.
            timeout: Segundos máximos a esperar.

        Returns:
            dict con respuesta JSON-RPC, o None si timeout o sesión cerrada.
        """
        session = self.get(session_id)
        if session is None:
            return None
        try:
            return session.queue.get(timeout=timeout)
        except Empty:
            return None

    def close(self, session_id: str) -> None:
        """Marca sesión como cerrada y la elimina del store."""
        with self._sessions_lock:
            session = self._sessions.get(session_id)
            if session:
                session.closed = True
            self._sessions.pop(session_id, None)
        _logger.debug("MCP SSE: Session closed: %s", session_id[:8] if session_id else "?")

    def cleanup_expired(self, max_age_seconds: int = 3600) -> int:
        """Elimina sesiones inactivas. Retorna número eliminadas."""
        now = datetime.utcnow()
        to_remove = []
        with self._sessions_lock:
            for sid, session in list(self._sessions.items()):
                if session.closed:
                    to_remove.append(sid)
                    continue
                delta = (now - session.created_at).total_seconds()
                if delta > max_age_seconds:
                    to_remove.append(sid)
            for sid in to_remove:
                self._sessions.pop(sid, None)
        if to_remove:
            _logger.info("MCP SSE: Cleaned %d expired sessions", len(to_remove))
        return len(to_remove)
