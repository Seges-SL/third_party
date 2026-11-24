# Copyright 2026 Seges
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0).
"""JSON routes and /mcp on the Odoo 17 core (stage F1.2, case 9 and F1-6).

On Odoo 17 there is no http_patch (pns_base/utils/compat.py:28): a POST with
Content-Type application/json to /mcp (type='http') goes through the core
HttpDispatcher (odoo/http.py:2101-2103, always compatible).

- test_mcp_post_json_no_key (1): 401, JSON-RPC error -32000 "API key
  required" and the id sent in the body (the body is read).
- test_mcp_post_json_wrong_key (2): a random key made here gives 401
  "Invalid API key".
- test_mcp_post_json_valid_key (3): a key made here for a user with the
  conversational group; tools/list (no network, no SSE session) gives 200
  with a list of tools. The key never appears in any message.
- test_mcp_single_allow_origin (4, F1-6): one Access-Control-Allow-Origin
  header on the answer to an allowed Origin. The module sets it and the core
  adds cors='*' with headers.extend (odoo/http.py:2055-2061, 1804-1806).
- test_mcp_foreign_origin (5): a foreign Origin gets 403 "Origin not allowed".
- test_mcp_preflight_by_core (6): OPTIONS /mcp is answered by the core with
  204 and its fixed Allow-Headers; the module handler does not run.
- test_json_route_error_format (7): a type='json' route that raises gives
  HTTP 200 and the core JSON-RPC error (odoo/http.py:2222-2256).
- test_json_route_rejects_text_plain (8): a text/plain POST to a json route
  is refused with 400 before authentication (odoo/http.py:1907-1918).
- test_http_post_routes_need_csrf (9): POST without csrf_token to
  /pns_ai_mcp/key_pin/stop and /chatboo/stream gives 400 (odoo/http.py:2117).

Only users, keys and parameters created here; no customer data.

Every failure message starts with a tag:
- [HYPOTHESIS]: the safe behaviour this test asserts did not hold (test 4);
- [CHECK]: the behaviour this test documents did not hold;
- [SETUP]: a precondition failed; says nothing about the routes.
"""

import html
import json
import secrets

from odoo.addons.pns_ai_mcp.utils.api_key import hash_api_key
from odoo.tests import HttpCase, tagged
from odoo.tests.common import new_test_user
from odoo.tools import mute_logger

MCP_AGENT = "pns_ai_mcp"
ALLOWED_ORIGIN = "https://allowed.lab-3996.test"
FOREIGN_ORIGIN = "https://foreign.lab-3996.test"
CORE_ALLOW_HEADERS = "Origin, X-Requested-With, Content-Type, Accept, Authorization"
JSON = {"Content-Type": "application/json"}


@tagged("post_install", "-at_install")
class TestRoutes17(HttpCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.internal = new_test_user(
            cls.env, login="lab3996_routes_internal", groups="base.group_user",
        )
        cls.env["ir.config_parameter"].sudo().set_param(
            "pns_ai_mcp.mcp_allowed_origins", ALLOWED_ORIGIN,
        )

    # ---------------------------------------------------------------- helpers
    def _require_mcp_agent(self):
        agent = self.env["ai.agent"].sudo().search(
            [("code", "=", MCP_AGENT), ("active", "=", True)], limit=1,
        )
        self.assertTrue(agent, f"[SETUP] expected the active agent {MCP_AGENT!r}; found none")

    def _post_mcp(self, req_id, headers=None, method="tools/list"):
        self._require_mcp_agent()
        self.authenticate(None, None)  # session with the test database, no user
        body = json.dumps({"jsonrpc": "2.0", "method": method, "params": {}, "id": req_id})
        return self.url_open("/mcp", data=body, headers=dict(JSON, **(headers or {})))

    def _json(self, resp, what):
        try:
            return resp.json()
        except ValueError:
            self.fail(f"[CHECK] expected JSON from {what}; got {resp.status_code} {resp.text[:300]!r}")

    def _mcp_error(self, resp, what, status, message, req_id):
        data = self._json(resp, what)
        found = (resp.status_code, data.get("id"), data.get("error"))
        expected = (status, req_id, {"code": -32000, "message": message})
        self.assertEqual(found, expected, f"[CHECK] {what}: (status, id, error)")

    # ------------------------------------------------------------- case 9: /mcp
    def test_mcp_post_json_no_key(self):
        resp = self._post_mcp(4242)
        self._mcp_error(resp, "POST /mcp without key", 401, "API key required", 4242)

    def test_mcp_post_json_wrong_key(self):
        resp = self._post_mcp(4243, {"X-MCP-API-Key": secrets.token_urlsafe(32)})
        self._mcp_error(resp, "POST /mcp with an unknown key", 401, "Invalid API key", 4243)

    def test_mcp_post_json_valid_key(self):
        user = new_test_user(
            self.env, login="lab3996_routes_mcp",
            groups="base.group_user,pns_ai_mcp.group_ai_conversational",
        )
        key = secrets.token_urlsafe(32)
        McpUser = self.env["ai.mcp.user"].sudo().with_context(mcp_skip_ensure_all_users=True)
        rec = McpUser.search([("user_id", "=", user.id)], limit=1)
        if rec:
            rec.write({"mcp_api_key_hash": hash_api_key(key)})
        else:
            rec = McpUser.create({"user_id": user.id, "mcp_api_key_hash": hash_api_key(key)})
        self.assertEqual(
            McpUser.search_count([("mcp_api_key_hash", "=", hash_api_key(key))]), 1,
            "[SETUP] expected exactly one ai.mcp.user with the test key",
        )
        self.env.flush_all()
        resp = self._post_mcp(4244, {"X-MCP-API-Key": key})
        data = self._json(resp, "POST /mcp with the test key")
        error = data.get("error") or {}
        self.assertNotEqual(
            error.get("message"), "Conversational AI is not allowed for this user.",
            "[SETUP] expected the test user to pass the conversational door",
        )
        self.assertEqual(
            (resp.status_code, data.get("id"), "error" in data), (200, 4244, False),
            f"[CHECK] POST /mcp tools/list with the test key: (status, id, has error); "
            f"error={error}",
        )
        tools = (data.get("result") or {}).get("tools")
        self.assertIsInstance(tools, list, "[CHECK] expected result.tools to be a list")
        self.assertTrue(tools, "[CHECK] expected at least one tool in result.tools")

    # ------------------------------------------------------- F1-6 and origins
    def test_mcp_single_allow_origin(self):
        resp = self._post_mcp(4245, {"Origin": ALLOWED_ORIGIN})
        self._mcp_error(resp, "POST /mcp from the allowed Origin", 401, "API key required", 4245)
        values = resp.raw.headers.getlist("Access-Control-Allow-Origin")
        self.assertEqual(
            values, [ALLOWED_ORIGIN],
            "[HYPOTHESIS] expected one Access-Control-Allow-Origin with the caller's Origin",
        )

    def test_mcp_foreign_origin(self):
        resp = self._post_mcp(4246, {"Origin": FOREIGN_ORIGIN})
        data = self._json(resp, "POST /mcp from a foreign Origin")
        self.assertEqual(
            (resp.status_code, data.get("error")),
            (403, {"code": -32000, "message": "Origin not allowed"}),
            "[CHECK] POST /mcp from a foreign Origin: (status, error)",
        )

    def test_mcp_preflight_by_core(self):
        self._require_mcp_agent()
        self.authenticate(None, None)
        resp = self.opener.options(self.base_url() + "/mcp", timeout=12, headers={
            "Origin": FOREIGN_ORIGIN,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type,x-mcp-api-key",
        })
        found = (
            resp.status_code,
            resp.headers.get("Access-Control-Allow-Origin"),
            resp.headers.get("Access-Control-Allow-Headers"),
        )
        self.assertEqual(
            found, (204, "*", CORE_ALLOW_HEADERS),
            "[CHECK] OPTIONS /mcp: (status, Allow-Origin, Allow-Headers) of the core",
        )

    # ------------------------------------------------------------ json routes
    def test_json_route_error_format(self):
        self.authenticate(self.internal.login, self.internal.login)
        body = json.dumps({"jsonrpc": "2.0", "method": "call", "params": {}, "id": 7})
        with mute_logger("odoo.http"):
            resp = self.url_open("/chatboo/sessions/load", data=body, headers=JSON)
        data = self._json(resp, "/chatboo/sessions/load without session_id")
        error = data.get("error") or {}
        err_data = error.get("data") or {}
        found = (resp.status_code, data.get("id"), error.get("code"), error.get("message"),
                 err_data.get("name"), "debug" in err_data)
        self.assertEqual(
            found, (200, 7, 200, "Odoo Server Error", "builtins.TypeError", True),
            "[CHECK] json route that raises: (status, id, code, message, data.name, has debug)",
        )

    def test_json_route_rejects_text_plain(self):
        self.authenticate(self.internal.login, self.internal.login)
        route = "/pns_ai_mcp/verification/pending"
        resp = self.url_open(route, data="{}", headers={"Content-Type": "text/plain"})
        expected = (
            f"Request inferred type is compatible with ['http'] but {route!r} is type='json'."
        )
        self.assertEqual(resp.status_code, 400, f"[CHECK] text/plain POST to {route}: status")
        self.assertIn(expected, html.unescape(resp.text), f"[CHECK] text/plain POST to {route}: message")

    def test_http_post_routes_need_csrf(self):
        self.authenticate(self.internal.login, self.internal.login)
        for route, data, headers in (
            ("/pns_ai_mcp/key_pin/stop", {"token": "lab3996"}, None),
            ("/chatboo/stream", json.dumps({"message": "lab3996"}), JSON),
        ):
            resp = self.url_open(route, data=data, headers=headers)
            self.assertEqual(resp.status_code, 400, f"[CHECK] POST {route} without csrf_token: status")
            self.assertIn(
                "Session expired (invalid CSRF token)", html.unescape(resp.text),
                f"[CHECK] POST {route} without csrf_token: message",
            )
