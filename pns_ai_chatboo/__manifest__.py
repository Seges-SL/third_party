# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
# Odoo reads this file with ast.literal_eval — no module docstring before `{`.
{
    'name': 'Chatboo — AI Chat Assistant',
    'version': '17.0.2.1.597',
    'images': ['static/description/banner_store.png'],
    'category': 'Productivity',
    'summary': 'Open-source AI chatbot for Odoo Community 14 to 20: ask about your records in plain words with OpenAI, Claude or Ollama, and get tables, charts, PDF or Excel. Each user sees only what they may see.',
    'description': """
Part of Patanegra Soft Suite (pns_suite). Consumes the Patanegra Application Agent Protocol (PAAP).

Chatboo is the conversational front-end for the PNS AI MCP server.

It runs inside Odoo (no external build toolchain) and talks to the MCP
engine (pns_ai_mcp), which owns providers, agents, tools and the agentic
inference loop. Chatboo owns the conversation: session history, the chat
turn endpoint (SSE streaming) and the user interface.
""",
    'author': 'PATANEGRA Soft',
    'website': 'https://www.patanegra.com/chatboo.html',
    # Apache License 2.0 — see LICENSE file
    'license': 'Other OSI approved licence',
    'depends': ['web', 'bus', 'mail', 'pns_base', 'pns_ai_mcp'],
    'external_dependencies': {
        'python': ['openpyxl'],
    },
    'assets': {
        'web.assets_backend': [
            'pns_ai_chatboo/static/src/css/chatboo_floating.css',
            'pns_ai_chatboo/static/src/css/chatboo_app.css',
            'pns_ai_chatboo/static/src/css/chatboo_dashboard.css',
            'pns_ai_chatboo/static/src/css/chatboo_row_marks.css',
            'pns_ai_chatboo/static/src/css/chatboo_pdf_viewer.css',
            'pns_ai_chatboo/static/src/js/chatboo_tts.js',
            'pns_ai_chatboo/static/src/js/chatboo_sse.js',
            'pns_ai_chatboo/static/src/js/chatboo_turn.js',
            'pns_ai_chatboo/static/src/js/chatboo_screen_context.js',
            'pns_ai_chatboo/static/src/js/chatboo_choice_list.js',
            'pns_ai_chatboo/static/src/js/chatboo_row_marks.js',
            'pns_ai_chatboo/static/src/js/chatboo_pdf_viewer.js',
            'pns_ai_chatboo/static/src/js/chatboo_markdown.js',
            'pns_ai_chatboo/static/src/js/chatboo_heavy_libs.js',
            'pns_ai_chatboo/static/src/js/chatboo_dashboard.js',
            'pns_ai_chatboo/static/src/js/chatboo_card_width.js',
            'pns_ai_chatboo/static/src/js/chatboo_charts.js',
            'pns_ai_chatboo/static/src/js/chatboo_svg_cards.js',
            'pns_ai_chatboo/static/src/js/chatboo_formatters.js',
            'pns_ai_chatboo/static/src/js/chatboo_export.js',
            'pns_ai_chatboo/static/src/js/chatboo_context_stats.js',
            'pns_ai_chatboo/static/src/xml/chatboo_app.xml',
            'pns_ai_chatboo/static/src/js/chatboo_app.js',
            'pns_ai_chatboo/static/src/xml/chatboo_overlay.xml',
            'pns_ai_chatboo/static/src/js/chatboo_overlay.js',
            'pns_ai_chatboo/static/src/js/chatboo_systray.js',
            'pns_ai_chatboo/static/src/css/chatboo_systray.css',
            'pns_ai_chatboo/static/src/xml/chatboo_systray.xml',
        ],
    },
    'data': [
        'security/ir.model.access.csv',
        'security/security.xml',
        'data/ai_agent_data.xml',
        'data/ai_agent_conversational.xml',
        'data/chatboo_context_data.xml',
        'data/chatboo_skill_data.xml',
        'data/chatboo_async_cron.xml',
        'views/res_config_settings_mcp_agents_views.xml',
        'views/chatboo_menus.xml',
        'views/chatboo_canvas_page_views.xml',
        'views/ai_log_door_views.xml',
        'views/skill_capture_wizard_views.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
    'uninstall_hook': 'uninstall_hook',
}
