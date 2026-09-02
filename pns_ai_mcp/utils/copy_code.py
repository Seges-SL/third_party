# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""Unique ``{base}_copy`` / ``{base}_copyN`` codes for ORM duplicate."""


def next_copy_code(base, taken):
    """First code derived from ``base`` that is not in ``taken``.

    ``cdmon`` → ``cdmon_copy``; if that exists, ``cdmon_copy2``, …
    """
    root = (base or 'server').strip() or 'server'
    taken = set(taken or ())
    n = 1
    while True:
        candidate = '%s_copy' % root if n == 1 else '%s_copy%d' % (root, n)
        if candidate not in taken:
            return candidate
        n += 1
