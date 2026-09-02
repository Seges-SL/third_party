# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 Patanegra Soft <https://patanegra.com>
"""When a session file or clip rows exist, an empty bubble is still a turn."""


def done_meta_has_deliverable(done_meta):
    """True if ``done`` carried a download chip or JSON rows for clip icons.

    Named exports hide the on-screen table on purpose (clip_data only). The
    worker must not treat that empty accumulator as a missing-LLM failure.
    """
    meta = done_meta or {}
    files = meta.get('assistant_files')
    if isinstance(files, list) and files:
        return True
    clip = meta.get('clip_data')
    if isinstance(clip, dict) and clip.get('rows'):
        return True
    return False
