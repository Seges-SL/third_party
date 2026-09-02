# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""MCP tool: runtime i18n translation-parity audit."""

import os
import json
import logging
from .mcp_decorators import mcp_tool

_logger = logging.getLogger(__name__)

BASE_LANG = 'en_US'


def _extract(token):
    """Return the content inside the leading/trailing double quotes of a PO token."""
    token = token.strip()
    if len(token) >= 2 and token.startswith('"') and token.endswith('"'):
        return token[1:-1]
    return token


def _parse_po(path):
    """Minimal PO parser -> {msgid: msgstr}. Skips the header (empty msgid).

    Handles multi-line msgid/msgstr (continuation lines that are bare strings).
    Escapes are kept verbatim; we only need consistent parsing for comparison.
    """
    entries = {}
    cur_id = []
    cur_str = []
    mode = None  # 'id' | 'str' | None

    def flush():
        mid = ''.join(cur_id)
        mstr = ''.join(cur_str)
        if mid:
            entries[mid] = mstr

    with open(path, 'r', encoding='utf-8') as fh:
        for raw in fh:
            s = raw.strip()
            if not s or s.startswith('#'):
                if not s and mode is not None:
                    flush()
                    cur_id, cur_str, mode = [], [], None
                continue
            if s.startswith('msgid '):
                if mode == 'str':
                    flush()
                    cur_id, cur_str = [], []
                mode = 'id'
                cur_id.append(_extract(s[6:]))
            elif s.startswith('msgstr '):
                mode = 'str'
                cur_str.append(_extract(s[7:]))
            elif s.startswith('"'):
                if mode == 'id':
                    cur_id.append(_extract(s))
                elif mode == 'str':
                    cur_str.append(_extract(s))
        flush()
    return entries


@mcp_tool(
    name='audit_translations',
    description=(
        'Audit i18n parity for a module: lists base (English) terms that are missing '
        'or untranslated in each active non-English language (e.g. es_ES, ar_001). '
        'Reads the module .po files and res.lang. Use this instead of writing python '
        'to inspect translations.'
    ),
    is_write=False,
    validate_schema=True,
    input_schema={
        "type": "object",
        "properties": {
            "module": {
                "type": "string",
                "description": "Module technical name (default: pns_ai_mcp)."
            },
            "languages": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Language codes to audit (default: active res.lang except en_US)."
            },
            "max_samples": {
                "type": "integer",
                "description": "Max sample terms reported per language (default 25)."
            }
        },
        "required": []
    }
)
def tool_audit_translations(controller, arguments):
    """Tool: report missing / untranslated base terms per active language."""
    try:
        import odoo

        module = (arguments.get('module') or 'pns_ai_mcp').strip()
        max_samples = int(arguments.get('max_samples') or 25)
        env = controller._get_env_for_operation('read')

        langs = arguments.get('languages')
        if not langs:
            active = env['res.lang'].search([('active', '=', True)])
            langs = [lang.code for lang in active if lang.code != BASE_LANG]

        module_path = odoo.modules.get_module_path(module)
        if not module_path:
            return {'error': {'code': -32602, 'message': f'Module path not found: {module}'}}

        i18n_dir = os.path.join(module_path, 'i18n')
        po_files = {}
        if os.path.isdir(i18n_dir):
            for fn in os.listdir(i18n_dir):
                if fn.endswith('.po'):
                    po_files[fn[:-3]] = _parse_po(os.path.join(i18n_dir, fn))

        # Base terms = union of every msgid declared across the module .po files.
        base_terms = set()
        for entries in po_files.values():
            base_terms.update(entries.keys())

        report = {
            'module': module,
            'i18n_dir_found': os.path.isdir(i18n_dir),
            'known_base_terms': len(base_terms),
            'languages': {},
        }

        for code in langs:
            # Odoo 14 loads es.po for es_ES (get_iso_codes collapses es_ES → es).
            entries = dict(po_files.get(code, {}))
            present = code in po_files
            if '_' in code:
                base = code.split('_')[0]
                if base in po_files:
                    merged = dict(po_files[base])
                    merged.update(entries)
                    entries = merged
                    present = True
            missing = []
            untranslated = []
            for term in sorted(base_terms):
                val = entries.get(term)
                if val is None or val == '':
                    missing.append(term)
                elif val == term:
                    untranslated.append(term)
            report['languages'][code] = {
                'po_file_present': present,
                'po_aliases': sorted(
                    k for k in ((code,) + ((code.split('_')[0],) if '_' in code else ()))
                    if k in po_files
                ),
                'translated': len(base_terms) - len(missing) - len(untranslated),
                'missing_count': len(missing),
                'untranslated_count': len(untranslated),
                'missing_samples': missing[:max_samples],
                'untranslated_samples': untranslated[:max_samples],
            }

        return {'content': [{'type': 'text', 'text': json.dumps(report, indent=2, ensure_ascii=False)}]}

    except Exception as e:
        _logger.exception("MCP: Error auditing translations")
        return {'error': {'code': -32603, 'message': str(e)}}
