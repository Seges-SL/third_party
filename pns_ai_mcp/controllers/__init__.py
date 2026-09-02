# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""MCP controllers package."""

from . import main
from . import verification_ui
from . import choice_ui
from . import session_file

# Importar tools para que se registren automáticamente con decoradores
# Esto debe hacerse después de importar main para evitar imports circulares
try:
    from . import tools_system
    from . import tools_relaxaicode
    from . import safe_plan
    from . import tools_context
    from . import tools_context_analytics
    from . import tools_i18n_audit
except ImportError:
    # Si hay error de importación, no fallar (puede ser durante instalación)
    pass

