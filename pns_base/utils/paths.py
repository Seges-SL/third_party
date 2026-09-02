# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
# Archivo: utils/paths.py
# Descripción: Resolución de rutas dentro de addons Odoo (ecosistema PNS).

import os

from odoo.modules.module import get_module_path


def addon_subpath(module_name, *parts):
    """Ruta absoluta a un subdirectorio/archivo dentro de un addon instalado.

    Ejemplo: addon_subpath('pns_ai_mcp', 'templates') → .../pns_ai_mcp/templates

    Raises:
        FileNotFoundError: si el addon no está en el path de Odoo.
    """
    root = get_module_path(module_name)
    if not root:
        raise FileNotFoundError(
            "Addon %r not found in Odoo module path." % module_name
        )
    return os.path.join(root, *parts)


def addon_subpath_or_cwd(module_name, *parts, cwd_fallback_parts=None):
    """Como addon_subpath, con fallback relativo a getcwd() (entornos de desarrollo)."""
    try:
        return addon_subpath(module_name, *parts)
    except FileNotFoundError:
        fallback = cwd_fallback_parts or (module_name,) + parts
        return os.path.join(os.getcwd(), *fallback)
