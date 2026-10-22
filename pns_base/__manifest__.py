# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
# Odoo reads this file with ast.literal_eval — no module docstring before `{`.

{
    'name': 'PNS Base',
    'version': '1.2.47',
    'category': 'Technical',
    'summary': 'PNS ecosystem base layer: single-branch view compatibility and cross-version Odoo utilities (13-19+)',
    'description': """
        Common base module for all pns_* modules (logical dependency).

        Centralizes, without duplicating in each module:
        - Single-branch view compatibility patch (ir.ui.view / ir.actions.act_window):
          XML source is always written in legacy syntax (attrs, <tree>,
          category_id). On 17+ attrs become expressions; on 18+ <tree> becomes
          <list>; on 19+ group category_id becomes privilege_id.
        - Cross-version Odoo compatibility utilities (utils/compat.py):
          active version, res.users group helpers, cache invalidation, etc.
        - PDF and picture files on bytes (utils/pdf_io.py): open, write and turn
          the same on Odoo 14 and 19; printed text, or page pictures for a
          vision model the caller chooses; any picture stood up, shrunk,
          turned or made a PDF page. No AI here.
        - Generic UI feedback (utils/ui_feedback.py): operation report HTML,
          client notifications (sticky by default, no auto-reload).
        - Portable I/O (utils/portable_io.py, utils/settings_io.py):
          dynamic record/settings discovery, JSON/ZIP last-mile, and
          fault-tolerant import.
        - Operation report wizard mixin (models/operation_report_wizard.py).
        - Apps sheet embeds a module's static/description/index.html below the
          Odoo chrome (Update / Uninstall) only when that module's manifest
          points website at it (models/ir_module_module.py). Other vendors'
          links are left alone; the index runs in a sandboxed frame.
        - Exported files (portable_io.write_export_attachment) are deleted
          after pns_base.export_retention_hours (default 24; 0 = keep).
        - One full-screen panel at a time (static/src/js/pns_layer.js):
          panels claim the layer; opening one hides the other.
        - One picture full screen with zoom (static/src/js/pns_image_viewer.js):
          the host opens it with what it has; a larger copy replaces it.
        - Language/PO import guard (Odoo 13-15): dedupe code/model rows that
          would crash overwrite with CardinalityViolation (models/ir_translation.py).
        - List many2one that keeps the row in the breadcrumb (widget
          pns_row_link): opens this row's form, then the linked record.

        Other pns_* modules declare it in 'depends' and reuse these pieces.
    """,
    'author': 'PATANEGRA Soft',
    'website': '/pns_base/static/description/index.html',
    # Apache License 2.0 — see LICENSE file
    'license': 'Other OSI approved licence',
    'depends': ['web', 'mail'],
    'data': [
        'security/ir.model.access.csv',
        'views/assets.xml',
        'views/operation_report_wizard_views.xml',
        'views/export_file_wizard_views.xml',
        'views/export_secrets_wizard_views.xml',
        'views/ir_module_views.xml',
        'data/export_purge_cron.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
