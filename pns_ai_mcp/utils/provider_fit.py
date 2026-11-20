# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 Patanegra Soft <https://patanegra.com>
"""Which provider may take a turn.

``flags`` are the provider's role codes (``ai.provider.role``), each True.
No roles: a text turn may use it. A photo, a clip, a video, a closed
choice, a design or a parse may not. A role admits only that kind of turn.
"""
from __future__ import annotations


def _ticked(flags):
    return {key for key, on in (flags or {}).items() if on}


def provider_fits(flags, need):
    """True when this provider may take a turn that needs ``need``.

    No ``need`` is a text turn. No roles: text only. A role admits only
    that need.
    """
    if not need or need == 'conversation':
        ticked = _ticked(flags)
        return not ticked or 'conversation' in ticked
    return need in _ticked(flags)


def is_specialist(flags, need):
    """True when ``need`` is the only job this provider was ticked for.

    A model picked for one role alone is cheaper and better at it than a
    generalist that also holds the dialogue, so it is tried first even when
    the human put the generalist earlier in the chain.
    """
    if not need:
        return False
    return _ticked(flags) == {need}


def fit_mismatches(ticks, known):
    """Ticks the catalogue says this model cannot honour.

    ``ticks`` are the provider's roles. ``known`` is what the gateway
    declared for the selected model, keyed the same way; a key that is not
    there is not judged. Empty ``known`` (no architecture) judges nothing:
    the tick is not invented false because the catalogue is silent.
    """
    if not known:
        return []
    return [
        need for need in sorted(_ticked(ticks))
        if need in known and not known[need]
    ]
