# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""
Context utilities for MCP system.
Shared functions for processing context content.
"""

import re


def strip_xml_metadata(content):
    """
    Remove all non-semantic content from XML context before sending to LLM:
    - <metadata>...</metadata> block (author, version, dates — admin only)
    - <?xml ...?> declaration (meaningless to LLM)
    - <context>...</context> root wrapper (adds no semantic value)
    - Excessive blank lines (collapsed to max 1)

    This is the canonical implementation used by both:
    - Model layer (for size calculations)
    - Controller layer (when sending to LLM)
    """
    if not content:
        return content

    cleaned = content

    # 1. Remove XML declaration
    cleaned = re.sub(r'<\?xml[^?]*\?>\s*', '', cleaned)

    # 2. Remove <metadata>...</metadata> block (admin fields: author, version, dates)
    cleaned = re.sub(r'<metadata\b[^>]*>.*?</metadata>\s*', '', cleaned, flags=re.DOTALL)

    # 3. Unwrap root <context> element (keep children, discard wrapper)
    cleaned = re.sub(r'^\s*<context>\s*', '', cleaned)
    cleaned = re.sub(r'\s*</context>\s*$', '', cleaned)

    # 4. Collapse 3+ consecutive blank lines into 1
    cleaned = re.sub(r'\n{3,}', '\n\n', cleaned)

    # 5. Strip leading/trailing whitespace
    cleaned = cleaned.strip()

    return cleaned


def resolve_placeholders(content, env, controller=None):
    """
    Resolve dynamic placeholders like {locale}, {odoo_version}, etc.
    
    Args:
        content (str): Text with placeholders
        env: Odoo Environment
        controller: Optional controller instance (to reuse its cached locale logic)
        
    Returns:
        str: Resolved content
    """
    if not content:
        return content
        
    resolved = content

    # 1. Locale Resolution
    if '{locale}' in resolved or '{lang}' in resolved or '{user_lang}' in resolved:
        try:
            # Try to get locale from controller or env
            user_lang = env.context.get('lang', 'en_US')
            if controller and hasattr(controller, '_get_user_locale'):
                user_lang = controller._get_user_locale()
            
            resolved = resolved.replace('{locale}', user_lang)
            resolved = resolved.replace('{lang}', user_lang)
            resolved = resolved.replace('{user_lang}', user_lang)
        except:
            pass

    # 2. Version Resolution
    if '{odoo_version}' in resolved or '{odoo_series}' in resolved:
        try:
            import odoo.release
            version_str = odoo.release.version
            series_str = odoo.release.serie
            
            resolved = resolved.replace('{odoo_version}', version_str)
            resolved = resolved.replace('{odoo_series}', series_str)
        except:
            pass

    return resolved
