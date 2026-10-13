# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 Patanegra Soft <https://patanegra.com>
"""Tell the person reloading a language when duplicate rows were skipped."""

from odoo import _, models


class BaseLanguageInstall(models.TransientModel):
    _inherit = 'base.language.install'

    def lang_install(self):
        Translation = self.env['ir.translation']
        type(Translation)._pns_rows_dropped = 0
        res = super().lang_install()
        dropped = getattr(type(Translation), '_pns_rows_dropped', 0) or 0
        if not dropped:
            return res
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Translations'),
                'message': _(
                    '%s duplicate translation rows were skipped so the language could load.'
                ) % dropped,
                'type': 'warning',
                'sticky': True,
                'next': res,
            },
        }
