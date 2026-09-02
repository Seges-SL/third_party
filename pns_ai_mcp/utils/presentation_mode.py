# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""Deterministic Chatboo table/chart presentation layout (showmode).

Session (ICP default + chatboo.session.presentation_show_mode) only
oscillates between the layout pair:

* ``show-table`` — table-first (data view; client auto-charts when eligible)
* ``show-chart`` — chart-first (chart open; table always available)

Updated from ``/show-table`` / ``/show-chart`` or user phrasing
(“gráfico” / “tabla…”) via ``apply_sticky_show_mode``; unchanged until an
explicit rupture. Suspended when painter is painter-free.

Result-only modes (not written by session; not axis slashes):

* ``table`` — no chart toolbar/dataset (opt-out)
* ``dashboard`` — card grid

Client auto-gates (temporal X + money/%/count Y) apply under table-first;
chart-first mounts any analyzable numeric series because the user asked for
a graphic view.
"""

import re

SHOW_MODE_TABLE_CHART = 'show-table'
SHOW_MODE_CHART_TABLE = 'show-chart'
SHOW_MODE_DASHBOARD = 'dashboard'
SHOW_MODE_TABLE = 'table'  # solo tabla, sin toolbar/gráfico
VALID_SHOW_MODES = frozenset({
    SHOW_MODE_TABLE_CHART, SHOW_MODE_CHART_TABLE, SHOW_MODE_DASHBOARD,
    SHOW_MODE_TABLE,
})
DEFAULT_SHOW_MODE = SHOW_MODE_TABLE_CHART

# One-shot DB/HTML leftovers — not user slashes.
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

ICP_CHART_ENGINE = 'pns_ai_chatboo.chart_engine'
ICP_DEFAULT_SHOW_MODE = 'pns_ai_chatboo.default_show_mode'
ICP_LEGACY_DEFAULT_SHOWMODE = 'pns_ai_chatboo.default_showmode'

# Deprecated aliases (read compat only).
SHOWMODE_TABLE_CHART = SHOW_MODE_TABLE_CHART
SHOWMODE_CHART_TABLE = SHOW_MODE_CHART_TABLE
VALID_SHOWMODES = VALID_SHOW_MODES
DEFAULT_SHOWMODE = DEFAULT_SHOW_MODE

# Structural UI vocabulary (not domain-specific).
_CHART_HINTS_ES = (
    r'\bgr[áa]fic[oa]s?\b',
    r'\bdiagrama[s]?\b',
    r'\bvisualiz[aá]\b',
    r'\brepresent[aá]\b',
    r'\bchart[s]?\b',
    r'\bplot[s]?\b',
    r'\bcurva[s]?\b',
    r'\btarta[s]?\b',
    r'\bpastel[es]?\b',
    r'\bhistograma[s]?\b',
)
_TABLE_HINTS_ES = (
    r'\btabla[s]?\b',
    r'\blistado[s]?\b',
    r'\bdetalle[s]?\b',
    r'\bgrid[s]?\b',
    r'\bcuadro[s]?\b',
    r'\bregistro[s]?\b',
    r'\bfila[s]?\b',
)
_CHART_HINTS_EN = (
    r'\bchart[s]?\b',
    r'\bgraph[s]?\b',
    r'\bdiagram[s]?\b',
    r'\bplot[s]?\b',
    r'\bvisuali[sz]e\b',
    r'\bpie\b',
    r'\bbar chart[s]?\b',
    r'\bline chart[s]?\b',
)
_TABLE_HINTS_EN = (
    r'\btable[s]?\b',
    r'\blist[s]?\b',
    r'\bdetail[s]?\b',
    r'\bgrid[s]?\b',
    r'\brows?\b',
    r'\brecord[s]?\b',
)

# Single Y-axis intent (honest comparison of same-unit series).
_SINGLE_AXIS_HINTS = (
    r'\bun\s+solo\s+eje\b',
    r'\beje\s+[uú]nico\b',
    r'\bmisma\s+escala\b',
    r'\buna\s+sola\s+escala\b',
    r'\bsame\s+scale\b',
    r'\bsingle\s+(?:y[- ]?)?axis\b',
    r'\bone\s+(?:y[- ]?)?axis\b',
)
_DUAL_AXIS_HINTS = (
    r'\bdos\s+ejes\b',
    r'\beje\s+doble\b',
    r'\bejes\s+[iy]\b',
    r'\bdual\s+(?:y[- ]?)?axis\b',
    r'\bsecondary\s+(?:y[- ]?)?axis\b',
    r'\bsegundo\s+eje\b',
)


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


def resolve_dual_axis_from_message(text):
    """Detect single/dual Y-axis intent from the user message; else None."""
    if not text or not str(text).strip():
        return DUAL_AXIS_AUTO
    low = str(text).lower()
    for pat in _SINGLE_AXIS_HINTS:
        if re.search(pat, low, flags=re.IGNORECASE):
            return False
    for pat in _DUAL_AXIS_HINTS:
        if re.search(pat, low, flags=re.IGNORECASE):
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


def resolve_dual_axis_for_render(env, result=None, user_message=None):
    """Best-effort dual_axis for HTML (priority: result > user message > auto)."""
    explicit = _result_dual_axis(result)
    if explicit is not DUAL_AXIS_AUTO:
        return explicit
    if not user_message:
        try:
            user_message = (env.context or {}).get('user_message')
        except Exception:
            user_message = None
    return resolve_dual_axis_from_message(user_message)


def _result_show_mode(result):
    if not isinstance(result, dict):
        return None
    return result.get('show_mode') or result.get('showmode')


def _icp_default_show_mode(env):
    try:
        icp = env['ir.config_parameter'].sudo()
        val = icp.get_param(ICP_DEFAULT_SHOW_MODE)
        if not val:
            val = icp.get_param(ICP_LEGACY_DEFAULT_SHOWMODE, DEFAULT_SHOW_MODE)
        return normalize_show_mode(val)
    except Exception:
        return DEFAULT_SHOW_MODE


def _icp_chart_engine(env):
    try:
        val = env['ir.config_parameter'].sudo().get_param(
            ICP_CHART_ENGINE, DEFAULT_CHART_ENGINE,
        )
        return normalize_chart_engine(val)
    except Exception:
        return DEFAULT_CHART_ENGINE


def _session_show_mode(session):
    if not session:
        return None
    return (
        getattr(session, 'presentation_show_mode', None)
        or getattr(session, 'presentation_showmode', None)
    )


def _lang_prefix(user_lang):
    lang = (user_lang or 'en_US').replace('-', '_').lower()
    if lang.startswith('es'):
        return 'es'
    return 'en'


def _hint_score(text, patterns):
    if not text:
        return 0
    score = 0
    for pat in patterns:
        if re.search(pat, text, re.I):
            score += 1
    return score


def resolve_show_mode_from_message(text, user_lang=None, current=None):
    """Detect chart-first vs table-first layout from user text.

    Returns None when no explicit layout signal (keep sticky/current).
    """
    raw = (text or '').strip()
    if not raw:
        return None
    low = raw.lower()
    prefix = _lang_prefix(user_lang)
    if prefix == 'es':
        chart_pats, table_pats = _CHART_HINTS_ES + _CHART_HINTS_EN, _TABLE_HINTS_ES + _TABLE_HINTS_EN
    else:
        chart_pats, table_pats = _CHART_HINTS_EN + _CHART_HINTS_ES, _TABLE_HINTS_EN + _TABLE_HINTS_ES
    chart_score = _hint_score(low, chart_pats)
    table_score = _hint_score(low, table_pats)
    if chart_score == 0 and table_score == 0:
        return None
    if chart_score > table_score:
        return SHOW_MODE_CHART_TABLE
    if table_score > chart_score:
        return SHOW_MODE_TABLE_CHART
    cur = normalize_show_mode(current)
    return cur if cur else DEFAULT_SHOW_MODE


def resolve_show_mode_for_render(env, result=None, user_message=None):
    """Best-effort show_mode for HTML render (priority: result > session > ICP)."""
    explicit = _result_show_mode(result)
    if explicit:
        return normalize_show_mode(explicit)
    session_mode = _show_mode_from_session(env)
    if session_mode:
        return session_mode
    if user_message:
        detected = resolve_show_mode_from_message(
            user_message, _user_lang_from_env(env),
            current=_icp_default_show_mode(env),
        )
        if detected:
            return detected
    return _icp_default_show_mode(env)


def resolve_chart_engine_for_render(env, result=None):
    """Chart library for HTML (priority: result > Chatboo settings ICP)."""
    if isinstance(result, dict) and result.get('chart_engine'):
        return normalize_chart_engine(result.get('chart_engine'))
    return _icp_chart_engine(env)


def apply_sticky_show_mode(session, user_message, user_lang=None):
    """Update session sticky layout when the user signals table vs chart.

    Only writes the layout pair (show-table / show-chart). Never sets
    ``table`` or ``dashboard`` (those are result-only opt-ins).
    """
    if not session or not session.exists():
        return DEFAULT_SHOW_MODE
    current = normalize_show_mode(_session_show_mode(session))
    if not _session_show_mode(session):
        current = _icp_default_show_mode(session.env)
    detected = resolve_show_mode_from_message(
        user_message,
        user_lang or (session.user_id.lang if session.user_id else None),
        current=current,
    )
    if detected and detected != current:
        session.write({'presentation_show_mode': detected})
        return detected
    return current


def _user_lang_from_env(env):
    try:
        return env.user.lang or env.context.get('lang') or 'en_US'
    except Exception:
        return env.context.get('lang') or 'en_US'


def _show_mode_from_session(env):
    session_id = None
    ctx = env.context or {}
    if ctx.get('chatboo_session_id'):
        session_id = int(ctx['chatboo_session_id'])
    if not session_id:
        try:
            from odoo.http import request as http_request
            if http_request and getattr(http_request, 'chatboo_options', None):
                sid = http_request.chatboo_options.get('chatboo_session_id')
                if sid:
                    session_id = int(sid)
        except Exception:
            pass
    if not session_id:
        return None
    try:
        Session = env['chatboo.session'].sudo()
        session = Session.browse(session_id)
        raw = _session_show_mode(session) if session.exists() else None
        if raw:
            return normalize_show_mode(raw)
    except Exception:
        pass
    return None


# Deprecated spellings (compat).
normalize_showmode = normalize_show_mode
resolve_showmode_from_message = resolve_show_mode_from_message
resolve_showmode_for_render = resolve_show_mode_for_render
apply_sticky_showmode = apply_sticky_show_mode
_showmode_from_session = _show_mode_from_session
_icp_default_showmode = _icp_default_show_mode
