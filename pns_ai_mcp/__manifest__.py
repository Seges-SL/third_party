# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>

{
    'name': 'AI Engine',
    'version': '3.1.486',
    'category': 'Patanegra AI',
    'summary': 'Agent engine for Odoo apps: PAAP roles, providers, skills, governed writes',
    'description': """
        Patanegra AI Engine — core of the Patanegra AI stack for Odoo applications.
        Reference implementation of the Patanegra Application Agent Protocol (PAAP).

        Provides agents, provider chains, contexts, skills, audit log and the
        propose → authorize → execute write boundary (two-box model). Includes an
        MCP server (Anthropic spec) as one inbound transport; Chatboo and domain
        modules build on this engine.

        Highlights:
        - Role → bundle → provider invocation (PAAP)
        - Supervised write plans (no direct AI execution on production data)
        - Per-user MCP bridge keys and ACL-scoped tool access
        - Extensible skills and domain knowledge per module
    """,
    'author': 'PATANEGRA Soft',
    'website': '/pns_ai_mcp/static/description/index.html',
    'license': 'Other OSI approved licence',
    'depends': ['base', 'web', 'mail', 'bus', 'pns_base'],
    'external_dependencies': {
        # LLM drivers (openai_driver.py / anthropic_driver.py) talk raw HTTP via
        # `requests`; the `openai` SDK is NOT used (there is no `import openai`).
        # `pydantic` is used behind a v1/v2 shim -> requires Python 3.6 (real module floor).
        'python': ['openpyxl', 'reportlab', 'requests', 'httpx', 'pydantic'],
    },
    'assets': {
        'web.assets_backend': [
            # CSS
            'pns_ai_mcp/static/src/css/mcp_log_tree.css',
            'pns_ai_mcp/static/src/css/mcp_context.css',
            'pns_ai_mcp/static/src/css/mcp_rtl.css',
            'pns_ai_mcp/static/src/css/mcp_context_list.css',
            'pns_ai_mcp/static/src/css/pns_list.css',
            # Vendor libs
            'pns_ai_mcp/static/src/js/showdown.js',
            'pns_ai_mcp/static/src/js/jspdf.umd.min.js',
            'pns_ai_mcp/static/src/js/xlsx.full.min.js',
            # Widgets (v14)
            'pns_ai_mcp/static/src/js/mcp_api_key_widget_v14.js',
            'pns_ai_mcp/static/src/js/pns_html_readonly_widget_v14.js',
            'pns_ai_mcp/static/src/js/mcp_iso_datetime_widget_v14.js',
            'pns_ai_mcp/static/src/js/mcp_json_compressed_widget_v14.js',
            'pns_ai_mcp/static/src/js/context_window_combo_v14.js',
            'pns_ai_mcp/static/src/js/mcp_log_form_v14.js',
            'pns_ai_mcp/static/src/js/ai_agent_origin_filter_v14.js',
            # Tree views with Operations button (v14)
            'pns_ai_mcp/static/src/js/ai_agent_tree_v14.js',
            'pns_ai_mcp/static/src/js/ai_provider_tree_v14.js',
            'pns_ai_mcp/static/src/js/mcp_user_tree_v14.js',
            'pns_ai_mcp/static/src/js/mcp_context_tree_v14.js',
            'pns_ai_mcp/static/src/js/mcp_skill_tree_v14.js',
            'pns_ai_mcp/static/src/js/mcp_log_tree_v14.js',
            'pns_ai_mcp/static/src/js/whitelist_tree_v14.js',
            'pns_ai_mcp/static/src/js/external_server_tree_v14.js',
            'pns_ai_mcp/static/src/js/safe_operation_tree_v14.js',
            # QWeb templates
            'pns_ai_mcp/static/src/xml/mcp_field_widgets.xml',
        ],
    },
    'data': [
        'views/assets.xml',
        'security/security_groups.xml',
        'security/security.xml',
        'security/ir.model.access.csv',
        'views/mcp_api_key_wizard_views.xml',
        'views/mcp_user_views.xml',
        'views/mcp_safe_operation_views.xml',
        'wizard/operation_result_views.xml',
        'wizard/config_backup_wizard_views.xml',
        'wizard/artifact_bundle_wizard_views.xml',
        'wizard/context_import_wizard_views.xml',
        'wizard/import_servers_wizard_views.xml',
        'wizard/import_agents_wizard_views.xml',
        'wizard/ai_provider_tools_wizard_views.xml',
        'wizard/import_users_wizard_views.xml',
        'wizard/import_whitelist_wizard_views.xml',
        'wizard/import_external_servers_wizard_views.xml',
        'wizard/json_export_wizard_views.xml',
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
        'wizard/mcp_log_tools_wizard_views.xml',
        'wizard/safe_operation_tools_wizard_views.xml',
        'views/ai_context_views.xml',
        'views/ai_domain_index_views.xml',
        'views/mcp_change_journal_views.xml',
        'views/mcp_log_views.xml',
        'views/mcp_log_delete_menu_views.xml',
        'views/ai_provider_views.xml',
        'views/ai_agent_views.xml',
        'views/url_whitelist_views.xml',
        'views/ai_fx_source_views.xml',
        'views/ai_skill_views.xml',
        'views/ai_operator_menus.xml',
        'views/external_server_views.xml',
        'views/res_config_settings_views.xml',
        'data/ai_agent_data.xml',
        'views/ai_menus.xml',
        'data/mcp_data.xml',
        'data/external_server_data.xml',
        'data/fx_source_data.xml',
        'data/fetch_cache_cron.xml',
        'data/api_result_cache_cron.xml',
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

