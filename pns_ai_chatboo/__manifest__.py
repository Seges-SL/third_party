# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
{
    'name': 'Chatboo',
    'version': '2.1.322',
    'category': 'Patanegra AI',
    'summary': 'Conversational chat client (Chatboo) for the PNS AI MCP server.',
    'description': """
Part of Patanegra Soft Suite (pns_suite). Consumes the Patanegra Application Agent Protocol (PAAP).

Chatboo is the conversational front-end for the PNS AI MCP server.

It runs inside Odoo (no external build toolchain) and talks to the MCP
engine (pns_ai_mcp), which owns providers, agents, tools and the agentic
inference loop. Chatboo owns the conversation: session history, the chat
turn endpoint (SSE streaming) and the user interface.
""",
    'author': 'PATANEGRA Soft',
    'website': '/pns_ai_chatboo/static/description/index.html',
    'license': 'Other OSI approved licence',
    # OCR (pns_ocr) es capacidad OPCIONAL, detectada en runtime vía ocr.service.
    # NO es dependencia dura: así chatboo (y su systray) carga aunque pns_ocr no
    # esté desplegado. Con pns_ocr instalado, el clip extrae texto de PDF (Fase 3).
    'depends': ['web', 'mail', 'bus', 'pns_base', 'pns_ai_mcp'],
    'external_dependencies': {
        'python': ['openpyxl'],
    },
    'assets': {
        'web.assets_backend': [
            'pns_ai_chatboo/static/src/css/chatboo_floating.css',
            'pns_ai_chatboo/static/src/css/chatboo_app.css',
            'pns_ai_chatboo/static/src/css/chatboo_dashboard.css',
            'pns_ai_chatboo/static/src/js/chatboo_tts.js',
            'pns_ai_chatboo/static/src/js/chatboo_sse.js',
            'pns_ai_chatboo/static/src/js/chatboo_screen_context.js',
            'pns_ai_chatboo/static/src/js/chatboo_choice_list.js',
            'pns_ai_chatboo/static/src/js/showdown.js',
            'pns_ai_chatboo/static/src/js/jspdf_umd_pre.js',
            'pns_ai_chatboo/static/src/js/jspdf.umd.min.js',
            'pns_ai_chatboo/static/src/js/jspdf.plugin.autotable.min.js',
            'pns_ai_chatboo/static/src/js/jspdf_umd_post.js',
            'pns_ai_chatboo/static/src/js/jspdf_shim.js',
            'pns_ai_chatboo/static/src/js/html2canvas.min.js',
            'pns_ai_chatboo/static/src/js/xlsx.full.min.js',
            'pns_ai_chatboo/static/src/js/chart.umd.min.js',
            'pns_ai_chatboo/static/src/js/echarts.min.js',
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
        'data/ai_agent_data.xml',
        'data/chatboo_context_data.xml',
        'data/chatboo_skill_data.xml',
        'data/chatboo_icp_data.xml',
        'data/chatboo_async_cron.xml',
        'views/res_config_settings_mcp_agents_views.xml',
        'views/chatboo_menus.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
    'uninstall_hook': 'uninstall_hook',
}
