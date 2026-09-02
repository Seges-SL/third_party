# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""Path resolver for the PAAP cognitive folders (``ai/`` umbrella only).

Cognitive artifacts (contexts, skills) live under a module in:

- ``<module>/ai/<kind>/``  — PAAP umbrella convention (the ONLY valid layout)

``publish`` flattens ``common/`` into the addon root, so a module that ships
``common/ai/contexts`` is deployed as ``<addon>/ai/contexts``.

There is **no legacy fallback**: the old flat ``<module>/<kind>/`` layout is not
scanned. By design we prefer a visible "not loaded" over silent path drift — if
artifacts don't appear, the folder is in the wrong place and must be fixed.
"""
import os

AI_UMBRELLA = 'ai'


def module_kind_dir(module_root, kind, for_write=False):
    """Directory for ``kind`` ('contexts' | 'skills') under ``module_root``.

    Always the PAAP umbrella ``ai/<kind>``; no legacy fallback.

    - Reading (default): returns ``ai/<kind>`` if it exists, else ``None``
      (module has no artifacts of that kind, or they are misplaced → not loaded).
    - Writing (``for_write=True``): returns ``ai/<kind>`` even if it doesn't
      exist yet, so freshly created files adopt the convention.
    """
    if not module_root:
        return None
    ai_dir = os.path.join(module_root, AI_UMBRELLA, kind)
    if for_write or os.path.isdir(ai_dir):
        return ai_dir
    return None
