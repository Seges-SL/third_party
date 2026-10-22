# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""Deterministic table/chart presentation layout (showmode).

Context ``presentation_show_mode`` (the chat client sets it) and the
ICP default oscillate between the layout pair:

* ``show-table`` — table-first (data view; client auto-charts when eligible)
* ``show-chart`` — chart-first (chart open; table always available)

The host updates it from ``/show-table`` / ``/show-chart``. When the user
asks in words, the model sets ``show_mode`` on its result and the engine
hands that back to the host at the end of the turn. The engine never reads
the user's words. Suspended when compose is compose-model.

Result-only modes (not written by session; not axis slashes):

* ``table`` — no chart toolbar/dataset (opt-out)
* ``dashboard`` — card grid

Client auto-gates (temporal X + money/%/count Y) apply under table-first;
chart-first mounts any analyzable numeric series because the user asked for
a graphic view.
"""

from . import engine_params

SHOW_MODE_TABLE_CHART = 'show-table'
SHOW_MODE_CHART_TABLE = 'show-chart'
SHOW_MODE_DASHBOARD = 'dashboard'
SHOW_MODE_TABLE = 'table'  # solo tabla, sin toolbar/gráfico
VALID_SHOW_MODES = frozenset({
    SHOW_MODE_TABLE_CHART, SHOW_MODE_CHART_TABLE, SHOW_MODE_DASHBOARD,
    SHOW_MODE_TABLE,
})
DEFAULT_SHOW_MODE = SHOW_MODE_TABLE_CHART

# PAAP §14.3 spellings. A payload that uses them reads as the host pair;
# ``dashboard`` is spelled the same. Not user slashes.
_SHOW_MODE_LEGACY = {
    'table-chart': SHOW_MODE_TABLE_CHART,
    'chart-table': SHOW_MODE_CHART_TABLE,
}

CHART_ENGINE_ECHARTS = 'echarts'
CHART_ENGINE_CHARTJS = 'chartjs'
VALID_CHART_ENGINES = frozenset({CHART_ENGINE_ECHARTS, CHART_ENGINE_CHARTJS})
DEFAULT_CHART_ENGINE = CHART_ENGINE_ECHARTS

# Chart Y-axis mode: None = client auto; False = single; True = dual.
DUAL_AXIS_AUTO = None

# Deprecated aliases (read compat only).
SHOWMODE_TABLE_CHART = SHOW_MODE_TABLE_CHART
SHOWMODE_CHART_TABLE = SHOW_MODE_CHART_TABLE
VALID_SHOWMODES = VALID_SHOW_MODES
DEFAULT_SHOWMODE = DEFAULT_SHOW_MODE


def normalize_show_mode(value):
    """Return a valid show_mode or the default."""
    if not value:
        return DEFAULT_SHOW_MODE
    val = str(value).strip().lower()
    val = _SHOW_MODE_LEGACY.get(val, val)
    if val in VALID_SHOW_MODES:
        return val
    return DEFAULT_SHOW_MODE


def normalize_chart_engine(value):
    """Return a valid chart engine or the default."""
    if not value:
        return DEFAULT_CHART_ENGINE
    val = str(value).strip().lower()
    if val in VALID_CHART_ENGINES:
        return val
    return DEFAULT_CHART_ENGINE


def normalize_dual_axis(value):
    """Return True/False/None (auto) for chart dual Y-axis."""
    if value is None:
        return DUAL_AXIS_AUTO
    if isinstance(value, bool):
        return value
    val = str(value).strip().lower()
    if not val or val in ('auto', 'default', 'none'):
        return DUAL_AXIS_AUTO
    if val in ('0', 'false', 'off', 'single', 'one', 'no'):
        return False
    if val in ('1', 'true', 'on', 'dual', 'two', 'yes'):
        return True
    return DUAL_AXIS_AUTO


def _result_dual_axis(result):
    if not isinstance(result, dict):
        return DUAL_AXIS_AUTO
    if 'dual_axis' in result:
        return normalize_dual_axis(result.get('dual_axis'))
    if 'dualAxis' in result:
        return normalize_dual_axis(result.get('dualAxis'))
    return DUAL_AXIS_AUTO


def resolve_dual_axis_for_render(env, result=None):
    """dual_axis for HTML: what the result says, else the client decides."""
    return _result_dual_axis(result)


def _result_show_mode(result):
    if not isinstance(result, dict):
        return None
    return result.get('show_mode') or result.get('showmode')


def layout_from_result(result):
    """The layout pair value a result asks for, else None.

    ``table`` and ``dashboard`` stay on that answer; they never move the session.
    """
    raw = _result_show_mode(result)
    if not raw:
        return None
    val = str(raw).strip().lower()
    val = _SHOW_MODE_LEGACY.get(val, val)
    if val in (SHOW_MODE_TABLE_CHART, SHOW_MODE_CHART_TABLE):
        return val
    return None


def _icp_default_show_mode(env):
    try:
        return normalize_show_mode(engine_params.raw_default_show_mode(env))
    except Exception:
        return DEFAULT_SHOW_MODE


def _icp_chart_engine(env):
    try:
        return normalize_chart_engine(engine_params.chart_engine(env))
    except Exception:
        return DEFAULT_CHART_ENGINE


def resolve_show_mode_for_render(env, result=None):
    """show_mode for HTML render (priority: result > session > ICP)."""
    explicit = _result_show_mode(result)
    if explicit:
        return normalize_show_mode(explicit)
    session_mode = _show_mode_from_session(env)
    if session_mode:
        return session_mode
    return _icp_default_show_mode(env)


def resolve_chart_engine_for_render(env, result=None):
    """Chart library for HTML (priority: result > Chatboo settings ICP)."""
    if isinstance(result, dict) and result.get('chart_engine'):
        return normalize_chart_engine(result.get('chart_engine'))
    return _icp_chart_engine(env)


def _show_mode_from_session(env):
    """Layout the chat client put in context, if any."""
    ctx = getattr(env, 'context', None) or {}
    raw = ctx.get('presentation_show_mode') or ctx.get('presentation_showmode')
    if raw:
        return normalize_show_mode(raw)
    return None


# Deprecated spellings (compat).
normalize_showmode = normalize_show_mode
resolve_showmode_for_render = resolve_show_mode_for_render
_showmode_from_session = _show_mode_from_session
_icp_default_showmode = _icp_default_show_mode
