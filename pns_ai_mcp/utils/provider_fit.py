# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 Patanegra Soft <https://patanegra.com>
"""Which provider may take a turn.

No ticks: a text turn may use it. A photo, a clip, a video or a closed
choice may not. A tick admits only that kind of turn.
"""
from __future__ import annotations

FITS = ('conversation', 'audio', 'vision', 'video', 'decision')


def provider_fits(flags, need):
    """True when this provider may take a turn that needs ``need``.

    ``flags`` keys are the ``FITS``. No ``need`` is a text turn.
    All false: text only. A set flag admits only that need.
    """
    if not need or need == 'conversation':
        flags = flags or {}
        if not any(bool(flags.get(key)) for key in FITS):
            return True
        return bool(flags.get('conversation'))
    return bool((flags or {}).get(need))


def fit_mismatches(ticks, known):
    """Ticks the catalogue says this model cannot honour.

    ``ticks`` are the provider's flags. ``known`` is what the gateway
    declared for the selected model, keyed the same way; a key that is not
    there is not judged. Empty ``known`` (no architecture) judges nothing:
    the tick is not invented false because the catalogue is silent.
    """
    if not known:
        return []
    ticks = ticks or {}
    return [
        need for need in FITS
        if ticks.get(need) and need in known and not known[need]
    ]
