# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 Seges
# Seges: parche 38 (PNS-105, datos). Ver docs/pendiente/parches_pns_ai.md
"""Isolate a side cursor's Environment from the caller's (PNS-105).

In Odoo 14, ``Cursor.commit`` and ``Cursor.rollback`` flush or clear every
Environment of the thread's set (``flush_env``/``clear_env`` walk
``Environment.envs``), and the cache, ``towrite`` and ``tocompute`` belong to
that set. A side cursor with its own Environment therefore committed or
dropped the caller's pending work.

``seges_side_env()`` puts a new ``api.Environments`` in the thread for the
duration of the block and restores the previous one on exit (as a stack, so
nested blocks work). Use it before opening the cursor, so the cursor exits
first and its commit or close only sees the temporary set::

    with seges_side_env(), registry.cursor() as cr:
        env = api.Environment(cr, uid, context)
        ...

On entry, if a request has its cursor open and the thread has a set,
``request.env`` is created in the caller's set. On exit it checks that no
Environment on a caller's cursor was created inside the block and that the
caller's pending writes and computes did not change. If they did, it always
logs (ERROR in tests, WARNING otherwise) and, in tests, also raises an
``AssertionError`` unless an exception is already in flight. Messages carry
counts only, never data.
"""

import contextlib
import logging
import threading

from odoo import api, http
from odoo.modules import module as odoo_module

_logger = logging.getLogger(__name__)
_MISSING = object()
_TAG = 'seges_side_env: '


def _in_tests():
    return bool(getattr(threading.current_thread(), 'testing', False)
                or odoo_module.current_test)


def _request_with_cursor():
    req = http._request_stack.top
    if req is None or getattr(req, '_cr', None) is None:
        return None
    return req


def _pending_keys(envs):
    keys = set()
    for model_name, by_id in envs.towrite.items():
        for record_id, values in by_id.items():
            for fname in values:
                keys.add(('w', model_name, record_id, fname))
    for field, ids in envs.tocompute.items():
        for record_id in ids:
            keys.add(('c', field.model_name, record_id, field.name))
    return keys


def _check_only_side_envs(temp, caller_crs, prev, prev_keys, failed):
    created = sum(1 for env in temp if id(env.cr) in caller_crs)
    changed = prev is not _MISSING and _pending_keys(prev) != prev_keys
    if not created and not changed:
        return
    message = (f'{_TAG}{created} caller environment(s) created inside the block; '
               f"caller pending writes/computes changed: {'yes' if changed else 'no'}")
    # Always logged: the caller's own except clause may swallow the AssertionError.
    in_tests = _in_tests()
    _logger.log(logging.ERROR if in_tests else logging.WARNING, message, stack_info=True)
    if in_tests and not failed:
        raise AssertionError(message)


@contextlib.contextmanager
def seges_side_env():
    """Run the block on a new thread set of Environments; see the module doc."""
    local = api.Environment._local
    prev = getattr(local, 'environments', _MISSING)
    req = _request_with_cursor()
    if req is not None and prev is not _MISSING:
        # Forced in the caller's set; the cursor is already open.
        req.env  # noqa: B018  # pylint: disable=pointless-statement
    caller_crs = {id(env.cr) for env in (() if prev is _MISSING else prev)}
    if req is not None:
        caller_crs.add(id(req._cr))
    prev_keys = set() if prev is _MISSING else _pending_keys(prev)
    local.environments = api.Environments()
    failed = False
    try:
        yield
    except BaseException:
        failed = True
        raise
    finally:
        temp = local.environments
        if prev is _MISSING:
            if hasattr(local, 'environments'):
                del local.environments
        else:
            local.environments = prev
        _check_only_side_envs(temp, caller_crs, prev, prev_keys, failed)
