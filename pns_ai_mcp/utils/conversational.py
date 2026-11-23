# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 Patanegra Soft <https://patanegra.com>
"""Conversational door: agent identity + user group. No product names."""

GROUP_AI_CONVERSATIONAL = 'pns_ai_mcp.group_ai_conversational'
REFUSED_MESSAGE = 'Conversational AI is not allowed for this user.'


def user_is_ai_conversational(user):
    """True if the user holds the conversational group. Fail-closed."""
    if not user:
        return False
    try:
        return bool(user.sudo().has_group(GROUP_AI_CONVERSATIONAL))
    except Exception:
        return False


def agent_is_conversational(env, agent_code=None, agent=None):
    """True only when the agent row says so. Missing row or flag → False."""
    try:
        rec = agent
        if rec is None:
            code = (agent_code or '').strip()
            if not code or env is None or 'ai.agent' not in env:
                return False
            rec = env['ai.agent'].sudo().search([('code', '=', code)], limit=1)
        if not rec:
            return False
        return bool(rec.is_agent_conversational)
    except Exception:
        return False


def user_may_use_conversational_agent(env, user, agent_code=None, agent=None):
    """Closed jobs (flag off) are not this door. Open dialogue needs the group."""
    if not agent_is_conversational(env, agent_code=agent_code, agent=agent):
        return True
    return user_is_ai_conversational(user)
