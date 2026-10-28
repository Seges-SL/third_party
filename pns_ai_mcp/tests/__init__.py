# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""Odoo TransactionCase / HttpCase suite for pns_ai_mcp."""

from . import test_bundle_locale
from . import test_mcp_http
from . import test_mcp_agent
from . import test_agent_context_inheritance
from . import test_knowledge_ownership
from . import test_skill_capture_replace
from . import test_set_skill_parameters
from . import test_context_unlink
from . import test_required_context_pin
from . import test_identity_pack_isolation
from . import test_factory_defaults_keep
from . import test_knowledge_composition
from . import test_context_type_tokens
from . import test_relaxaicode_render_locale
from . import test_relaxaicode_model_stamp
from . import test_relaxaicode_imports
from . import test_relaxaicode_sandbox_escapes_e2e
from . import test_required_fields_live
from . import test_safe_plan_atomicity
from . import test_paap_core
from . import test_friendly_skill_error
from . import test_presentation_mode
from . import test_system_action
from . import test_pending_cards
from . import test_change_journal
from . import test_change_journal_menu
from . import test_session_download
from . import test_flow_legend
from . import test_server_identity_detection
# Seges: tests de la entrega E0′ (no regresión de los parches 7 a 10, retirados en 3.1.879). Ver docs/pendiente/parches_pns_ai.md
from . import test_seges_rpc_access
# Seges: tests de la entrega E1′ (parches 12, 13 y 16). Ver docs/pendiente/parches_pns_ai.md
from . import test_seges_user_groups
from . import test_seges_safe_operation
from . import test_seges_verification
# Seges: tests de la entrega E2′ (parches 17, 18, 19, 21 y 22). Ver docs/pendiente/parches_pns_ai.md
from . import test_seges_change_journal
from . import test_seges_sandbox_credentials
from . import test_seges_fetch_redirect
from . import test_seges_import_preview
from . import test_seges_sandbox_side_effects
# Seges: tests de la entrega E2′ (parche 23). Ver docs/pendiente/parches_pns_ai.md
from . import test_seges_sandbox_env
# Seges: tests de la entrega E2′ (parche 23 ampliado y 24). Ver docs/pendiente/parches_pns_ai.md
from . import test_seges_format_guard
from . import test_seges_facade_class
from . import test_seges_identity_su
