# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""Helpers para mapear stats de importación a campos del mixin operation report."""


def context_zip_files_to_result(files, warnings=None):
    """Mapea el dict files de import_contexts_zip al mixin."""
    files = files or {}
    return {
        'created': files.get('imported', 0),
        'updated': files.get('updated', 0),
        'skipped': files.get('skipped', 0),
        'removed': files.get('protocol_skipped', 0),
        'linked': files.get('skipped_manifest', 0),
        'errors': files.get('errors'),
        'warnings': warnings,
    }


def skill_zip_to_result(stats, warnings=None):
    """Mapea el dict stats de import_skills_zip() al mixin operation report."""
    stats = stats or {}
    extra = list(warnings or [])
    if stats.get('missing_contexts'):
        extra.append('Missing contexts: ' + ', '.join(stats['missing_contexts']))
    if stats.get('missing_agents'):
        extra.append('Missing agents: ' + ', '.join(stats['missing_agents']))
    return {
        'created': stats.get('created', 0),
        'updated': stats.get('updated', 0),
        'skipped': stats.get('skipped', 0),
        'errors': stats.get('errors'),
        'warnings': extra,
    }


def agent_pack_to_result(result):
    """Mapea import_agent_zip() al mixin."""
    files = result.get('files') or {}
    comp = result.get('composition') or {}
    warnings = list(result.get('warnings') or [])
    removed = comp.get('removed', 0)
    detail = str(removed) if removed else None
    return {
        'created': files.get('imported', 0),
        'updated': files.get('updated', 0),
        'skipped': files.get('skipped', 0),
        'removed': files.get('protocol_skipped', 0),
        'linked': comp.get('applied', 0),
        'manifest': comp.get('manifest_agent'),
        'errors': files.get('errors'),
        'warnings': warnings,
        'detail': detail,
    }
