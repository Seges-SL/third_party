# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""Session store for the standalone MCP SSE transport."""

import logging
import threading
import uuid
from datetime import datetime
from queue import Empty, Queue

from .mcp_correlation import new_turn_id

_logger = logging.getLogger(__name__)


class Session:
    """SSE session: ties the stream to POST requests."""

    def __init__(self, session_id: str, api_key: str, mcp_user_id: int = None):
        self.session_id = session_id
        self.api_key = api_key
        self.mcp_user_id = mcp_user_id
        self.turn = new_turn_id()
        self.turn_step = 0
        self.created_at = datetime.utcnow()
        self.touched_at = self.created_at
        self.closed = False
        self.queue = Queue()


class MCPClientRegistry:
    """
    In-memory record of the MCP client (name + version) per user.

    The MCP protocol only sends `clientInfo` on `initialize`; later calls
    (tools/call, prompts/list…) do not repeat it. Here we keep the client
    label after initialize so we can fill the history column
    "Modelo/Agente" on ALL MCP rows of that connection.

    Note: it is a process cache. With several Odoo workers, initialize and the
    later calls could land in different processes; in threaded mode
    (dev) or with sticky sessions it works reliably.
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
                    mu._register_mcp_client(label, remote_ip=remote_ip)
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
                return env['ai.mcp.user']._get_last_mcp_client_label(user_id)
            except Exception:
                pass
        return None


class SessionStore:
    """
    In-memory store for standalone SSE sessions.
    Needs sticky sessions on the proxy if Odoo runs several workers.
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
        Create an SSE session.

        Args:
            api_key: the client's validated API key.
            base_url: base URL (e.g. https://example.com or https://example.com/odoo)
            mcp_user_id: Odoo user ID (optional, cache).
            agent_code: agent suffix in the MCP path (optional).

        Returns:
            (session_id, message_url)
        """
        self.cleanup_expired()
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

    def get(self, session_id: str, max_age_seconds: int = 3600):
        """Get an active session. None if it does not exist, is closed or idle too long."""
        with self._sessions_lock:
            session = self._sessions.get(session_id)
            if session is not None and not session.closed and (
                    datetime.utcnow() - session.touched_at
            ).total_seconds() > max_age_seconds:
                session.closed = True
                self._sessions.pop(session_id, None)
        if session is None or session.closed:
            return None
        return session

    def enqueue_response(self, session_id: str, response: dict) -> bool:
        """
        Queue a JSON-RPC reply for the SSE stream to emit.

        Returns:
            True if the session exists and is not closed.
        """
        session = self.get(session_id)
        if session is None:
            return False
        session.touched_at = datetime.utcnow()
        try:
            session.queue.put_nowait(response)
            return True
        except Exception as e:
            _logger.warning("MCP SSE: Error enqueue: %s", e)
            return False

    def get_pending(self, session_id: str, timeout: float):
        """
        Block until there is a reply in the queue or a timeout.

        Args:
            session_id: session ID.
            timeout: max seconds to wait.

        Returns:
            dict with the JSON-RPC reply, or None on timeout or closed session.
        """
        session = self.get(session_id)
        if session is None:
            return None
        # The live stream waits here in a loop: that is what keeps it alive.
        session.touched_at = datetime.utcnow()
        try:
            return session.queue.get(timeout=timeout)
        except Empty:
            return None

    def close(self, session_id: str) -> None:
        """Mark the session closed and drop it from the store."""
        with self._sessions_lock:
            session = self._sessions.get(session_id)
            if session:
                session.closed = True
            self._sessions.pop(session_id, None)
        _logger.debug("MCP SSE: Session closed: %s", session_id[:8] if session_id else "?")

    def cleanup_expired(self, max_age_seconds: int = 3600) -> int:
        """Drop idle sessions. Returns how many were dropped."""
        now = datetime.utcnow()
        to_remove = []
        with self._sessions_lock:
            for sid, session in list(self._sessions.items()):
                if session.closed:
                    to_remove.append(sid)
                    continue
                delta = (now - session.touched_at).total_seconds()
                if delta > max_age_seconds:
                    to_remove.append(sid)
            for sid in to_remove:
                self._sessions.pop(sid, None)
        if to_remove:
            _logger.info("MCP SSE: Cleaned %d expired sessions", len(to_remove))
        return len(to_remove)
