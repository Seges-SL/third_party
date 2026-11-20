# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
# Odoo reads this file with ast.literal_eval — no module docstring before `{`.

{
    'name': 'PNS AI Engine',
    'version': '14.0.3.1.973',
    'images': ['static/description/banner_store.png'],
    'category': 'Extra Tools',
    'summary': 'Open-source AI engine and MCP server for Odoo Community 14 to 20: OpenAI, Claude, Ollama or any compatible model, read-only sandbox, every write approved by a person.',
    'description': """
        Patanegra AI Engine — core of the Patanegra AI stack for Odoo applications.
        Reference implementation of the Patanegra Application Agent Protocol (PAAP).

        Provides agents, provider chains, contexts, skills, audit log and the
        propose → authorize → execute write boundary (two-box model). Includes an
        MCP server (Anthropic spec) as one inbound transport; chat, voice and
        domain modules build on this engine.

        Highlights:
        - Role → bundle → provider invocation (PAAP)
        - Supervised write plans (no direct AI execution on production data)
        - Per-user MCP bridge keys and ACL-scoped tool access
        - Extensible skills and domain knowledge per module
    """,
    'author': 'PATANEGRA Soft',
    'website': 'https://www.patanegra.com/ai-engine.html',
    # Apache License 2.0 — see LICENSE file
    'license': 'Other OSI approved licence',
    'depends': ['web', 'pns_base'],
    'external_dependencies': {
        # LLM drivers (openai_driver.py / anthropic_driver.py) talk raw HTTP via
        # `requests`; the `openai` SDK is NOT used (there is no `import openai`).
        'python': ['openpyxl', 'reportlab', 'requests'],
    },
    'data': [
        'views/assets.xml',
        'security/security_groups.xml',
        'security/security.xml',
        'security/ir.model.access.csv',
        'data/ai_provider_role_data.xml',
        'views/mcp_api_key_wizard_views.xml',
        'views/mcp_user_views.xml',
        'views/safe_operation_views.xml',
        'wizard/operation_result_views.xml',
        'wizard/config_backup_wizard_views.xml',
        'wizard/artifact_bundle_wizard_views.xml',
        'wizard/context_import_wizard_views.xml',
        'wizard/import_servers_wizard_views.xml',
        'wizard/import_agents_wizard_views.xml',
        'wizard/ai_provider_tools_wizard_views.xml',
        'wizard/ai_provider_role_tools_wizard_views.xml',
        'wizard/import_provider_roles_wizard_views.xml',
        'wizard/ai_provider_usage_wizard_views.xml',
        'wizard/import_users_wizard_views.xml',
        'wizard/import_whitelist_wizard_views.xml',
        'wizard/import_external_servers_wizard_views.xml',
        'wizard/json_export_wizard_views.xml',
        'wizard/ai_provider_catalogue_copy_views.xml',
        'wizard/context_stats_wizard_views.xml',
        'wizard/mcp_context_tools_wizard_views.xml',
        'wizard/bundle_compose_wizard_views.xml',
        'wizard/bundle_cache_rebuild_wizard_views.xml',
        'wizard/bundle_import_wizard_views.xml',
        'wizard/skill_import_wizard_views.xml',
        'wizard/skill_tools_wizard_views.xml',
        'wizard/skill_capture_wizard_views.xml',
        'wizard/agent_context_import_wizard_views.xml',
        'wizard/agent_skill_import_wizard_views.xml',
        'wizard/ai_agent_tools_wizard_views.xml',
        'wizard/mcp_user_tools_wizard_views.xml',
        'wizard/whitelist_tools_wizard_views.xml',
        'wizard/external_server_tools_wizard_views.xml',
        'wizard/openapi_spec_generate_wizard_views.xml',
        'wizard/mcp_log_tools_wizard_views.xml',
        'wizard/safe_tools_wizard_views.xml',
        'views/ai_context_views.xml',
        'views/ai_domain_index_views.xml',
        'views/ai_change_journal_views.xml',
        'views/ai_log_views.xml',
        'views/mcp_log_delete_menu_views.xml',
        'views/ai_provider_views.xml',
        'views/ai_provider_role_views.xml',
        'views/ai_agent_views.xml',
        'views/url_whitelist_views.xml',
        'views/ai_fx_source_views.xml',
        'views/ai_skill_views.xml',
        'views/ai_operator_menus.xml',
        'views/external_server_views.xml',
        'views/res_config_settings_views.xml',
        'data/ai_agent_data.xml',
        'data/ai_agent_conversational.xml',
        'views/ai_menus.xml',
        'data/mcp_data.xml',
        'data/fx_source_data.xml',
        'data/fetch_cache_cron.xml',
        'data/api_result_cache_cron.xml',
        'data/ai_log_cron.xml',
        'data/journal_trash_cron.xml',
        'data/safe_operation_cron.xml',
        'data/trusted_actions_system.xml',
    ],
    # qweb key removed in Odoo 17+ - QWeb templates now go in assets > web.assets_backend
    'installable': True,
    'application': True,
    'auto_install': False,

    'post_init_hook': 'post_init_hook',
    'uninstall_hook': 'uninstall_hook',
}

