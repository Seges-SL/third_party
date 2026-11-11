# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 Patanegra Soft <https://patanegra.com>
"""The web client starts with this module's assets and no JavaScript error.

Installing a module never runs its JavaScript: Odoo builds the bundles the
first time a browser asks for them. An import or a patch() that this series
does not accept only shows here. Without Chrome, Odoo skips the test.
"""

from odoo.tests import HttpCase, tagged

_STARTED = """
(function wait(left) {
    if (document.querySelector('.o_action_manager')) {
        console.log('test successful');
    } else if (left <= 0) {
        console.error('the web client did not start');
    } else {
        setTimeout(function () { wait(left - 1); }, 250);
    }
})(120);
"""


@tagged('post_install', '-at_install', 'pns_base')
class TestWebClientStarts(HttpCase):

    def test_backend_starts_without_errors(self):
        self.browser_js('/web', _STARTED, login='admin', timeout=60)
