# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""ai.context: compose the context parts, pick the locale variant, composition stats."""

from odoo import (
    models,
    api,
)
from ..utils import context_roles
import logging

_logger = logging.getLogger(__name__)


class AIContextComposition(models.Model):
    _inherit = 'ai.context'

    @api.model
    def get_formatting_conventions(self, user_locale=None):
        """
        Extract technical formatting conventions from the 'corporate_terms'
        context resolved for the user's locale (via get_context_for_country).
        
        Args:
            user_locale (str): Locale code (e.g., 'es_ES', 'de_DE').
            
        Returns:
            dict: {thousands_sep, decimal_sep, date_format, csv_sep, csv_quote}
            or empty dict if not found.
        """
        if not user_locale:
            user_locale = self.env.context.get('lang', 'en_US')
            
        # 1. Search for the translation context for this locale
        context_record = self.get_context_for_country('corporate_terms', user_locale=user_locale)
        
        if not context_record or not context_record.content:
            return {}
            
        content = context_record.content
        import re
        
        # 2. Extract formatting_conventions block for this locale
        # Pattern matches: <formatting_conventions locale="XX_XX"> ... </formatting_conventions>
        block_pattern = f'<formatting_conventions[^>]*locale=["\']{user_locale}["\'][^>]*>(.*?)</formatting_conventions>'
        block_match = re.search(block_pattern, content, re.DOTALL)
        
        if not block_match:
            # Try without locale attribute check if it's the only block
            block_match = re.search(r'<formatting_conventions[^>]*>(.*?)</formatting_conventions>', content, re.DOTALL)
            
        if not block_match:
            return {}
            
        block_content = block_match.group(1)
        
        # 3. Extract individual tags
        result = {}
        patterns = {
            'decimal_sep': r'<decimal_separator[^>]*>(.*?)</decimal_separator>',
            'thousands_sep': r'<thousands_separator[^>]*>(.*?)</thousands_separator>',
            'date_format': r'<date_format[^>]*>(.*?)</date_format>',
            'csv_sep': r'<csv_field_separator[^>]*>(.*?)</csv_field_separator>',
            'csv_quote': r'<csv_quote_char[^>]*>(.*?)</csv_quote_char>',
        }
        
        for key, pattern in patterns.items():
            match = re.search(pattern, block_content, re.DOTALL)
            if match:
                val = match.group(1).strip()
                # Special case for date_format: convert DD/MM/YYYY to %d/%m/%Y for Python
                if key == 'date_format':
                    val = val.replace('DD', '%d').replace('MM', '%m').replace('YYYY', '%Y')
                    val = val.replace('HH', '%H').replace('SS', '%S') # Basic time sync
                    
                result[key] = val
                
        return result

    @api.model
    def get_context_for_country(self, base_code, user_locale=None):
        """
        Smart loading by EXPLICIT fields: locale-specific first, else neutral.

        Resolution keys off the stored ``base_code`` + ``locale`` fields, never
        off the code string. The trailing ``_es_ES`` you may see in a code is
        cosmetic; it is not what selects the variant.

        Args:
            base_code (str): Pristine base identifier (e.g. 'hr_payroll',
                'corporate_terms') — the value stored in the ``base_code`` field.
            user_locale (str, optional): Locale code (es_ES, fr_FR). Auto-detected
                from the user context if None.

        Returns:
            recordset: the record with (base_code, locale=user_locale) if present,
            else the language-neutral record (base_code, locale empty). A lazy
            on-disk lookup sits between the two as a fallback.

        Strategy:
            1. search([('base_code','=',base_code), ('locale','=',user_locale)])
            2. lazy disk discovery (file named base_code_user_locale.xml)
            3. search([('base_code','=',base_code), ('locale','in',[False,''])])

        Example:
            get_context_for_country('hr_payroll', 'es_ES')
            # → record whose locale == 'es_ES', else the neutral hr_payroll.
        """
        # Auto-detect locale from user context
        user_locale = self._normalize_user_locale(user_locale)
        
        # 1. Try locale-specific context via EXPLICIT base_code + locale fields.
        locale_specific = self.search(self.ownership_read_domain() + [
            ('base_code', '=', base_code),
            ('locale', '=', user_locale),
            ('active', '=', True),
        ], limit=1)
        
        if locale_specific:
            return locale_specific
            
        # 1.5 LAZY DISK DISCOVERY (On-Demand)
        # If not in DB, try to find on disk dynamically before falling back using convention.
        # Pattern: ai/contexts/custom/{category}/{base_code}/{base_code}_{user_locale}.xml
        try:
            import os
            from ..utils.ai_paths import module_kind_dir
            _module_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            target_filename = '%s_%s.xml' % (base_code, user_locale)
            _ctx_dir = module_kind_dir(_module_root, 'contexts')
            root_search_path = os.path.join(_ctx_dir, 'custom') if _ctx_dir else None
            found_path = None
            
            if root_search_path and os.path.exists(root_search_path):
                for root, dirs, files in os.walk(root_search_path):
                    if target_filename in files:
                        found_path = os.path.join(root, target_filename)
                        break
            
            if found_path:
                with open(found_path, 'r', encoding='utf-8') as f:
                    raw_content = f.read()
                    from collections import namedtuple
                    VirtualRecord = namedtuple('VirtualRecord', ['code', 'content', 'description'])
                    variant_code = '%s_%s' % (base_code, user_locale)
                    _logger.info("MCP: Lazy Loaded '%s' from disk - %s", variant_code, found_path)
                    return VirtualRecord(code=variant_code, content=raw_content, description="Lazy Loaded %s" % base_code)
        except Exception as e:
            _logger.error("MCP: Error lazy loading on-demand %s: %s", base_code, e)

        # 2. Fallback to the language-neutral base context (explicit fields).
        generic = self.search(self.ownership_read_domain() + [
            ('base_code', '=', base_code),
            ('locale', 'in', [False, '']),
            ('active', '=', True),
        ], limit=1)
        
        # Fallback a contexto pelao (sin locale): válido para cualquier locale
        return generic

    @api.model
    def _normalize_user_locale(self, user_locale=None):
        if not user_locale:
            user_locale = self.env.context.get('lang', 'en_US')
        return str(user_locale).replace('-', '_')

    @api.model
    def get_listable_for_mcp(self):
        """Return the contexts advertised via the standard MCP primitives.

        One record per ``base_code`` (locale variants collapsed), restricted to
        ``core`` + ``domain`` types — the selectable knowledge an MCP client can
        load. ``system_prompt`` is the compiled bundle (``prompts/get``), not a
        second catalogue row. Pure ``locale`` contexts (linguistic glue) are
        internal adaptation, not user-selectable, so they are excluded.

        Shared by ``prompts/list`` so that primitive
        advertises exactly the same catalogue as the ``get_context`` tool index.
        """
        from ..utils.agent_identity import is_identity_pack_code
        contexts = self.search(self.ownership_read_domain() + [
            ('active', '=', True),
            ('context_type', 'in', list(context_roles.MCP_LISTABLE_TYPES)),
        ], order='context_type, code')
        seen = set()
        result = self.browse()
        for ctx in contexts:
            base = ctx.base_code or ctx.code
            if is_identity_pack_code(ctx.code) or is_identity_pack_code(base):
                continue
            if base == 'system_prompt':
                continue
            if base in seen:
                continue
            seen.add(base)
            result |= ctx
        return result

    @api.model
    def _virtual_map_from_contexts(self, contexts):
        """Group contexts by explicit base_code with generic + locale variants."""
        virtual_map = {}
        for ctx in contexts:
            if not ctx.active:
                continue
            # VirtualContext objects (lazy disk discovery) have no context_type/
            # base_code/locale; default gracefully.
            ctx_type = getattr(ctx, 'context_type', None) or 'domain'
            base_code = getattr(ctx, 'base_code', None) or ctx.code
            loc = getattr(ctx, 'locale', None)
            variant_key = loc if loc else 'generic'
            virtual_map.setdefault(base_code, {
                'context_type': ctx_type,
                'variants': {},
            })
            virtual_map[base_code]['variants'][variant_key] = ctx
        return virtual_map

    @api.model
    def _lazy_load_locale_variants(self, virtual_map, user_locale):
        """Add on-disk locale variants for composed bases (domain/locale)."""
        import os
        from ..utils.ai_paths import module_kind_dir

        module_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        _ctx_dir = module_kind_dir(module_root, 'contexts')
        root_search_path = os.path.join(_ctx_dir, 'custom') if _ctx_dir else None
        if not root_search_path or not os.path.exists(root_search_path):
            return

        for base_code, data in virtual_map.items():
            if user_locale in data['variants']:
                continue
            if data['context_type'] not in ('domain', 'locale'):
                continue
            target_filename = '%s_%s.xml' % (base_code, user_locale)
            found_path = None
            for root, dirs, files in os.walk(root_search_path):
                if target_filename in files:
                    found_path = os.path.join(root, target_filename)
                    break
            if not found_path:
                continue
            try:
                with open(found_path, 'r', encoding='utf-8') as f:
                    raw_content = f.read()

                class VirtualContext:
                    def __init__(self, code, content):
                        self.code = code
                        self.content = content

                virtual_code = '%s_%s' % (base_code, user_locale)
                data['variants'][user_locale] = VirtualContext(virtual_code, raw_content)
            except Exception:
                pass

    @api.model
    def _pick_resolved_variant(self, data, user_locale):
        """Return the single winning context for a virtual_map entry."""
        variants = data['variants']
        if user_locale in variants:
            return variants[user_locale]
        if 'generic' in variants:
            return variants['generic']
        if data['context_type'] == 'locale' and 'en_US' in variants:
            return variants['en_US']
        if len(variants) == 1:
            return next(iter(variants.values()))
        return None

    @api.model
    def _resolve_parts_from_virtual_map(self, virtual_map, user_locale):
        """Pick one stripped content part per base_code (locale-aware)."""
        from odoo.addons.pns_ai_mcp.utils.context_utils import strip_xml_metadata

        context_parts = []
        type_priority = ['core', 'locale', 'domain']
        for ctype in type_priority:
            bases_in_type = [
                (base, data) for base, data in virtual_map.items()
                if data['context_type'] == ctype
            ]
            bases_in_type.sort(key=lambda item: item[0])
            for base_code, data in bases_in_type:
                target_ctx = self._pick_resolved_variant(data, user_locale)
                if not target_ctx:
                    continue
                try:
                    context_parts.append(strip_xml_metadata(target_ctx.content))
                except Exception:
                    continue
        return context_parts

    @api.model
    def get_composition_stats(self, contexts, user_locale=None):
        """
        Type sizes/counts aligned with assemble_context_parts (locale dedup).
        Includes library totals for comparison with the raw inventory in DB.
        """
        from odoo.addons.pns_ai_mcp.utils.context_utils import strip_xml_metadata

        user_locale = self._normalize_user_locale(user_locale)
        empty_types = {
            'core': {'count': 0, 'size_raw': 0, 'size_optimized': 0},
            'domain': {'count': 0, 'size_raw': 0, 'size_optimized': 0},
            'locale': {'count': 0, 'size_raw': 0, 'size_optimized': 0},
        }
        stats = {
            'user_locale': user_locale,
            'categories': {k: dict(v) for k, v in empty_types.items()},
            'total_count': 0,
            'total_size_raw': 0,
            'total_size_optimized': 0,
            'library_count': len(contexts),
            'library_size_raw': sum(c.content_size_bytes for c in contexts),
            'library_size_optimized': sum(c.content_size_without_metadata for c in contexts),
        }
        virtual_map = self._virtual_map_from_contexts(contexts)
        self._lazy_load_locale_variants(virtual_map, user_locale)
        for ctype in ['core', 'locale', 'domain']:
            for base_code in sorted(
                base for base, data in virtual_map.items() if data['context_type'] == ctype
            ):
                target_ctx = self._pick_resolved_variant(virtual_map[base_code], user_locale)
                if not target_ctx:
                    continue
                content = target_ctx.content or ''
                raw = len(content.encode('utf-8'))
                try:
                    optimized = len(strip_xml_metadata(content).encode('utf-8'))
                except Exception:
                    optimized = raw
                stats['categories'][ctype]['count'] += 1
                stats['categories'][ctype]['size_raw'] += raw
                stats['categories'][ctype]['size_optimized'] += optimized
                stats['total_count'] += 1
                stats['total_size_raw'] += raw
                stats['total_size_optimized'] += optimized
        return stats

    @api.model
    def assemble_context_parts(self, contexts, user_locale=None):
        """
        Build stripped content parts for a context set with locale deduplication.
        One resolved variant per base_code (same rules as discovery content).
        """
        user_locale = self._normalize_user_locale(user_locale)
        virtual_map = self._virtual_map_from_contexts(contexts)
        self._lazy_load_locale_variants(virtual_map, user_locale)
        return self._resolve_parts_from_virtual_map(virtual_map, user_locale)
