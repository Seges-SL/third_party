# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""MCP controllers package."""

import logging

from . import main
from . import key_pin
from . import verification_ui
from . import choice_ui
from . import session_file
from . import remote_image

_logger = logging.getLogger(__name__)


def _load_tool(name):
    """Register one tool module. A miss is logged and does not hide the rest.

    Install can hit this before the file is importable. A later boot that
    still hits it leaves the same line, with the traceback.
    """
    try:
        __import__(__name__ + '.' + name, fromlist=[name])
    except ImportError:
        _logger.exception('MCP tools: %s did not load', name)


# After main, so these can import it.
_load_tool('tools_relaxaicode')
_load_tool('safe_plan')
_load_tool('tools_context')
