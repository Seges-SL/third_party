# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
# Archivo: __manifest__.py
# Descripción: Manifiesto del módulo pns_base - capa común del ecosistema PNS

{
    'name': 'PNS Base',
    'version': '1.2.20',
    'category': 'Technical',
    'summary': 'PNS ecosystem base layer: single-branch view compatibility and cross-version Odoo utilities (13-19+)',
    'description': """
        Common base module for all pns_* modules (logical dependency).

        Centralizes, without duplicating in each module:
        - Single-branch view compatibility patch (ir.ui.view / ir.actions.act_window):
          XML source is always written in legacy syntax (attrs, <tree>), natively valid
          on Odoo 13-16, and on Odoo 17+ this module converts it at runtime to
          invisible/readonly/required="expression" and <list>.
        - Cross-version Odoo compatibility utilities (utils/compat.py):
          active version, res.users group helpers, cache invalidation, etc.
        - Generic UI feedback (utils/ui_feedback.py): operation report HTML,
          client notifications (sticky by default, no auto-reload).
        - Addon path helpers (utils/paths.py).
        - Portable I/O (utils/portable_io.py, utils/settings_io.py):
          dynamic record/settings discovery, JSON/ZIP last-mile, and
          fault-tolerant import.
        - Operation report wizard mixin (models/operation_report_wizard.py).
        - Apps enlace points at each module's own static/description/index.html
          (models/ir_module_module.py). The standard sheet embeds that index
          below the Odoo chrome (Update / Uninstall).

        Other pns_* modules declare it in 'depends' and reuse these pieces.
    """,
    'author': 'PATANEGRA Soft',
    'website': '/pns_base/static/description/index.html',
    # Apache License 2.0 — see LICENSE file
    'license': 'Other OSI approved licence',
    'depends': ['base', 'web'],
    'assets': {
        'web.assets_backend': [
            'pns_base/static/src/css/pns_required_readonly.css',
            'pns_base/static/src/css/pns_module_index.css',
            'pns_base/static/src/js/pns_invalid_fields_dedupe.js',
            'pns_base/static/src/js/pns_module_index.js',
        ],
    },
    'data': [
        'security/ir.model.access.csv',
        'views/operation_report_wizard_views.xml',
        'views/export_file_wizard_views.xml',
        'views/ir_module_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
