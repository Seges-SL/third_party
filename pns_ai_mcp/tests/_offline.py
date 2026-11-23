# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 Patanegra Soft <https://patanegra.com>
"""No outside HTTP from the tests, as Odoo 16+ already enforces.

A test database may hold real providers with real keys; on Odoo 14 a test
would send a real prompt. Local addresses stay open for the HTTP tests.
"""
from urllib.parse import urlsplit

import requests

from odoo import release

_LOCAL_HOSTS = ('localhost', '127.0.0.1', '::1')


def _block_outside_http():
    if release.version_info[0] >= 16:
        return
    send = requests.Session.send
    if getattr(send, '_pns_offline', False):
        return

    def offline_send(session, request, **kwargs):
        host = urlsplit(request.url).hostname or ''
        if host not in _LOCAL_HOSTS:
            raise requests.exceptions.ConnectionError(
                'External requests are blocked in tests (%s)' % host,
            )
        return send(session, request, **kwargs)

    offline_send._pns_offline = True
    requests.Session.send = offline_send


_block_outside_http()
