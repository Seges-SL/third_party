# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 Patanegra Soft <https://patanegra.com>
"""v3.1.410: rewrite leftover identity pins after capability-prompt split."""
from odoo import api, SUPERUSER_ID


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    if 'ai.agent' not in env:
        return
    Agent = env['ai.agent']
    if hasattr(Agent, '_unlink_foreign_identity_packs'):
        Agent.search([])._unlink_foreign_identity_packs()
