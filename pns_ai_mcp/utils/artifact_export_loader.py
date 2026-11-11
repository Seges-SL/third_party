# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""Load the formatters module and sibling files, also without an Odoo package (unit tests)."""

from __future__ import annotations
import importlib.util
from pathlib import Path


def _load_formatters():
    try:
        return _load_path(
            Path(__file__).resolve().parents[1] / 'controllers' / 'formatters.py',
            '_ae_formatters',
        )
    except Exception:
        return None


def _load_sibling(filename, mod_name):
    return _load_path(Path(__file__).resolve().parent / filename, mod_name)


def _load_path(path, mod_name):
    spec = importlib.util.spec_from_file_location(mod_name, path)
    if spec is None or spec.loader is None:
        raise ImportError('cannot load %s' % path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod
