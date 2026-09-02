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
    # Apache License 2.0 — see LICENSE file
    'license': 'Other OSI approved licence',
    # OCR (pns_ocr) es capacidad OPCIONAL, detectada en runtime vía ocr.service.
    # NO es dependencia dura: así chatboo (y su systray) carga aunque pns_ocr no
    # esté desplegado. Con pns_ocr instalado, el clip extrae texto de PDF (Fase 3).
    'depends': ['web', 'mail', 'bus', 'pns_base', 'pns_ai_mcp'],
    # openpyxl: extracción de .xlsx adjuntos (también en pns_ai_mcp; lo
    # declaramos aquí para que el deploy de Chatboo no se olvide en O14).
    'external_dependencies': {
        'python': ['openpyxl'],
    },
    'data': [
        'security/ir.model.access.csv',
        'data/ai_agent_data.xml',
        'data/chatboo_context_data.xml',
        'data/chatboo_skill_data.xml',
        'data/chatboo_icp_data.xml',
        'data/chatboo_async_cron.xml',
        'views/res_config_settings_mcp_agents_views.xml',
        'views/assets.xml',
        'views/chatboo_menus.xml',
    ],
    'qweb': [
        'static/src/xml/chatboo_systray.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
    'uninstall_hook': 'uninstall_hook',
}
