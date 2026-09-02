# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""
registry.py — Driver registry (protocol → driver class).

This module implements a simple dict-based registry that maps ``protocol``
strings (like ``'openai'``, ``'anthropic'``, ``'ollama'``) to their driver
classes. The orchestrator calls ``get_llm_driver(protocol)`` to get a
fresh driver instance.

The registry key is exactly the value of the ``protocol`` field on the
``ai.provider`` Odoo model, so callers just pass ``provider.protocol``.

Registration happens at import time in ``drivers/__init__.py``::

    register_llm_driver('openai', OpenAIDriver)
    register_llm_driver('anthropic', AnthropicDriver)
    register_llm_driver('ollama', OllamaDriver)

Unknown protocols fall back to ``'openai'`` (since most providers
use the OpenAI-compatible API). This means you can configure any
OpenAI-compatible gateway without creating a new driver — just use
``protocol='openai'`` and set the endpoint.
"""

_REGISTRY = {}


def register_llm_driver(protocol, driver_cls):
    """Register a driver class for a ``protocol`` string.

    Args:
        protocol: Registry key (e.g. ``'openai'``, ``'anthropic'``).
            This is the value of the ``protocol`` field on the
            ``ai.provider`` Odoo model.
        driver_cls: The driver class (subclass of ``LLMDriver``).
            Will be instantiated fresh on each call to ``get_llm_driver()``.

    Example::

        from .my_driver import MyCustomDriver
        register_llm_driver('my_provider', MyCustomDriver)
    """
    if not protocol or not isinstance(protocol, str):
        raise ValueError('protocol must be a non-empty string')
    _REGISTRY[protocol] = driver_cls


def get_llm_driver(protocol):
    """Instantiate and return a fresh driver for the given ``protocol``.

    If ``protocol`` is not registered, falls back to ``'openai'``
    (since most LLM gateways are OpenAI-compatible).

    Args:
        protocol: Registry key (e.g. ``'openai'``, ``'anthropic'``),
            i.e. the ``ai.provider.protocol`` field value.

    Returns:
        A new ``LLMDriver`` instance (never shared between calls).

    Raises:
        RuntimeError: If neither the requested protocol nor ``'openai'`` is
            registered (should never happen in normal operation).

    Example::

        driver = get_llm_driver('anthropic')
        driver.initialize({...})
        response = driver.chat_completion(messages)
    """
    key = protocol or 'openai'
    driver_cls = _REGISTRY.get(key)
    if driver_cls is None:
        driver_cls = _REGISTRY.get('openai')
    if driver_cls is None:
        raise RuntimeError(
            'No LLM driver registered for %r and no openai fallback' % protocol
        )
    return driver_cls()


def list_llm_driver_types():
    """Return sorted list of registered ``protocol`` keys.

    Useful for diagnostics and for building UI selection dropdowns.

    Returns:
        List of strings, e.g. ``['anthropic', 'ollama', 'openai']``.
    """
    return sorted(_REGISTRY.keys())
