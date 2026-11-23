# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""
registry.py — API driver registry (api_type → driver class).

Same pattern as ``lib/llm/drivers/registry.py``: a dict keyed EXACTLY by the
``api_type`` field of ``ai.api.server``, so callers just pass
``server.api_type``. Registration happens at import time in
``drivers/__init__.py``::

    register_api_driver('mcp', MCPDriver)
    register_api_driver('openapi', OpenAPIDriver)

Unlike the LLM registry there is NO fallback: an unknown api_type is a
configuration error, not something to silently reinterpret.
"""

_REGISTRY = {}


def register_api_driver(api_type, driver_cls):
    """Register a driver class for an ``api_type`` string."""
    if not api_type or not isinstance(api_type, str):
        raise ValueError('api_type must be a non-empty string')
    _REGISTRY[api_type] = driver_cls


def get_api_driver(api_type):
    """Instantiate and return a fresh driver for ``api_type``.

    Raises:
        ValueError: if no driver is registered for that type.
    """
    driver_cls = _REGISTRY.get(api_type)
    if driver_cls is None:
        raise ValueError(
            'No API driver registered for api_type %r (known: %s)'
            % (api_type, ', '.join(sorted(_REGISTRY)))
        )
    return driver_cls()


def list_api_driver_types():
    """Sorted list of registered ``api_type`` keys."""
    return sorted(_REGISTRY.keys())
