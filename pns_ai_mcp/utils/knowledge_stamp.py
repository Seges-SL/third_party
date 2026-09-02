# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 Patanegra Soft <https://patanegra.com>
"""Factory-knowledge stamp: any installed module that ships ``ai/``."""
import os


def module_has_ai_knowledge(module_root):
    """True when ``module_root`` has ``ai/contexts`` or ``ai/skills``."""
    if not module_root:
        return False
    return os.path.isdir(os.path.join(module_root, 'ai', 'contexts')) or os.path.isdir(
        os.path.join(module_root, 'ai', 'skills'),
    )


def format_factory_knowledge_stamp(pairs):
    """``(module_name, version)`` pairs → stable ``name:ver|…`` string."""
    items = sorted((name, version or '') for name, version in (pairs or []) if name)
    return '|'.join('%s:%s' % (name, version) for name, version in items)
