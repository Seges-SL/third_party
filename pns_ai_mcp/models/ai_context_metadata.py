# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""ai.context: read the metadata header of a context file (code, type, locale, discovery)."""

import json
import re
from odoo import (
    models,
    api,
)


class AIContextMetadata(models.Model):
    _inherit = 'ai.context'

    @api.model
    def _infer_explicit_locale(self, code, content, metadata=None):
        """Resolve the explicit locale for a context record (DB field ``locale``).

        Priority: metadata ``<locale_code>`` / front-matter → suffix in ``code``
        (``foo_es_ES``) → inner ``locale="xx_XX"`` on translation blocks (only
        when not a language-neutral fallback). Never guesses from filename alone.
        """
        metadata = metadata or {}
        if metadata.get('is_fallback'):
            return False
        loc = (metadata.get('locale') or '').strip()
        if loc:
            return str(loc).replace('-', '_')

        code = (code or '').strip()
        m = re.match(r'^.+_([a-z]{2})_([A-Z]{2})$', code)
        if m:
            return '%s_%s' % (m.group(1), m.group(2))

        text = content or ''
        cat = (metadata.get('tipo') or '').lower()
        if cat == 'locale' or 'term_mapping_definitions' in text:
            for pattern in (
                r'<mapping[^>]*\slocale=["\']([a-z]{2}_[A-Z]{2})["\']',
                r'<formatting_conventions[^>]*\slocale=["\']([a-z]{2}_[A-Z]{2})["\']',
            ):
                inner = re.search(pattern, text)
                if inner:
                    return inner.group(1)
        return False

    @api.model
    def _extract_metadata_from_content(self, content, filename):
        """
        Extracts metadata from the file content.
        For .py: looks for structured comments in the header.
        For .md: looks for YAML front matter.
        
        Returns a dictionary with: description, author, version, date_created, date_modified, created_by, modified_by, active, is_core
        """
        metadata = {
            'contexto': None,  # Context code from metadata
            'description': None,
            'author': None,
            'version': None,
            'date_created': None,
            'date_modified': None,
            'created_by': None,
            'modified_by': None,
            'active': None,
            'category': None,
            'locale': None,   # EXPLICIT locale (file attribute, not from the name)
            'is_fallback': None,
            'product_name': None,
            'vendor': None,
        }
        
        if filename.endswith('.py'):
            # For Python: look for structured comments in the header
            # Expected format:
            # # -*- coding: utf-8 -*-
            # # Archivo: name.py
            # # Creado: YYYY-MM-DD [HH:mm:ss]
            # # Modificado: YYYY-MM-DD [HH:mm:ss]
            # # Descripción: descriptive text
            # # Autor: author name
            # # Versión: version number
            lines = content.split('\n')
            
            for line in lines[:30]:  # First 30 lines
                line = line.strip()
                if not line.startswith('#'):
                    # A line that is not a comment means the header is over
                    break
                
                comment = line[1:].strip()
                if not comment:
                    continue
                
                # Look for structured fields in "Field: value" format
                if ':' in comment:
                    key, value = comment.split(':', 1)
                    key = key.strip().lower()
                    value = value.strip()
                    
                    if key in ('descripción', 'description'):
                        metadata['description'] = value
                    elif key == 'autor' or key == 'author':
                        metadata['author'] = value
                    elif key == 'versión' or key == 'version':
                        metadata['version'] = value
                    elif key in ('creado', 'fecha de creación', 'date_created', 'created'):
                        # Keep only the date (YYYY-MM-DD) if there is a time
                        date_str = value.split()[0] if value else None
                        if date_str:
                            metadata['date_created'] = date_str
                    elif key in ('modificado', 'fecha de modificación', 'date_modified', 'modified', 'actualizado', 'updated'):
                        # Keep only the date (YYYY-MM-DD) if there is a time
                        date_str = value.split()[0] if value else None
                        if date_str:
                            metadata['date_modified'] = date_str
                    elif key in ('creado por', 'created_by', 'created by', 'creador'):
                        metadata['created_by'] = value
                    elif key in ('modificado por', 'modified_by', 'modified by', 'modificador'):
                        metadata['modified_by'] = value
                    elif key in ('activo', 'active'):
                        # Convert to boolean
                        metadata['active'] = value.lower() in ('true', '1', 'yes', 'sí', 'si', 'verdadero')
                    elif key == 'tipo':
                        metadata['tipo'] = value.lower()
                    elif key in ('locale', 'locale_code', 'idioma'):
                        metadata['locale'] = value
                    elif key in ('is_fallback', 'fallback', 'es_fallback'):
                        metadata['is_fallback'] = value.lower() in ('true', '1', 'yes', 'sí', 'si', 'verdadero')
                    elif key in ('product_name', 'display_name', 'displayname'):
                        metadata['product_name'] = value
                    elif key == 'vendor':
                        metadata['vendor'] = value
        
        elif filename.endswith('.md'):
            # For Markdown: look for YAML front matter
            # Expected format:
            # ---
            # contexto: context_name
            # descripción: descriptive text
            # autor: author name
            # fecha_creacion: YYYY-MM-DD
            # fecha_modificacion: YYYY-MM-DD
            # version: version number
            # ---
            lines = content.split('\n')
            
            if lines and lines[0].strip() == '---':
                # There is YAML front matter
                yaml_lines = []
                i = 1
                while i < len(lines) and lines[i].strip() != '---':
                    yaml_lines.append(lines[i])
                    i += 1
                
                # Parse simple YAML (no external library)
                for line in yaml_lines:
                    line = line.strip()
                    if ':' in line:
                        key, value = line.split(':', 1)
                        key = key.strip().lower()
                        value = value.strip().strip('"').strip("'")
                        
                        if key in ('contexto', 'code', 'codigo'):
                            metadata['contexto'] = value
                        elif key in ('descripción', 'descripcion', 'description'):
                            metadata['description'] = value
                        elif key in ('autor', 'author'):
                            metadata['author'] = value
                        elif key in ('versión', 'version'):
                            metadata['version'] = value
                        elif key in ('fecha_creacion', 'fecha_creación', 'date_created', 'created', 'creado'):
                            metadata['date_created'] = value
                        elif key in ('fecha_modificacion', 'fecha_modificación', 'date_modified', 'modified', 'modificado', 'actualizado', 'updated'):
                            metadata['date_modified'] = value
                        elif key in ('creado_por', 'creado por', 'created_by', 'created by', 'creador'):
                            metadata['created_by'] = value
                        elif key in ('modificado_por', 'modificado por', 'modified_by', 'modified by', 'modificador'):
                            metadata['modified_by'] = value
                        elif key in ('activo', 'active'):
                            # Convert to boolean
                            metadata['active'] = value.lower() in ('true', '1', 'yes', 'sí', 'si', 'verdadero')
                        elif key == 'tipo':
                            metadata['tipo'] = value.lower()
                        elif key in ('locale', 'locale_code', 'idioma'):
                            metadata['locale'] = value
                        elif key in ('is_fallback', 'fallback', 'es_fallback'):
                            metadata['is_fallback'] = value.lower() in ('true', '1', 'yes', 'sí', 'si', 'verdadero')
                        elif key in ('is_global', 'global', 'universal'):
                            metadata['is_global'] = value.lower() in ('true', '1', 'yes', 'sí', 'si', 'verdadero')
                        elif key in ('agent_codes', 'agent_code', 'agentes'):
                            metadata['agent_codes'] = value
                        elif key in ('product_name', 'display_name', 'displayname'):
                            metadata['product_name'] = value
                        elif key == 'vendor':
                            metadata['vendor'] = value
            
            # No front matter: use the first heading or paragraph as description
            if not metadata['description']:
                for line in lines[:30]:
                    line = line.strip()
                    if line.startswith('#'):
                        title = line.lstrip('#').strip()
                        if title:
                            metadata['description'] = title
                            break
                    elif line and not line.startswith('```') and not line.startswith('---'):
                        if len(line) > 10:
                            metadata['description'] = line[:200]
                            break
        
        elif filename.endswith('.xml'):
            # For XML: look for tags inside <metadata>
            import re
            
            # Find the <metadata>...</metadata> block (flexible with attributes)
            metadata_match = re.search(r'<metadata[^>]*>(.*?)</metadata>', content, re.DOTALL)
            if metadata_match:
                metadata_block = metadata_match.group(1)
                
                # Extract common tags (flexible with attributes)
                patterns = {
                    'contexto': r'<code[^>]*>(.*?)</code>',
                    'description': r'<description[^>]*>(.*?)</description>',
                    'author': r'<author[^>]*>(.*?)</author>',
                    'version': r'<version[^>]*>(.*?)</version>',
                    'date_created': r'<created_at[^>]*>(.*?)</created_at>',
                    'date_modified': r'<modified_at[^>]*>(.*?)</modified_at>',
                    'created_by': r'<created_by[^>]*>(.*?)</created_by>',
                    'modified_by': r'<modified_by[^>]*>(.*?)</modified_by>',
                    'active': r'<active[^>]*>(.*?)</active>',
                    'tipo': r'<tipo[^>]*>(.*?)</tipo>',
                    'locale': r'<locale(?:_code)?[^>]*>(.*?)</locale(?:_code)?>',
                    'is_fallback': r'<is_fallback[^>]*>(.*?)</is_fallback>',
                    'agent_codes': r'<agent_codes[^>]*>(.*?)</agent_codes>',
                    'agent_code': r'<agent_code[^>]*>(.*?)</agent_code>',
                    'product_name': r'<product_name[^>]*>(.*?)</product_name>',
                    'display_name': r'<display_name[^>]*>(.*?)</display_name>',
                    'vendor': r'<vendor[^>]*>(.*?)</vendor>',
                }
                
                for key, pattern in patterns.items():
                    match = re.search(pattern, metadata_block, re.DOTALL)
                    if match:
                        value = match.group(1).strip()
                        if key == 'active':
                            metadata[key] = value.lower() in ('true', '1', 'yes', 'sí', 'si', 'verdadero')
                        elif key == 'tipo':
                            metadata[key] = value.lower()
                        elif key in ('is_fallback', 'fallback'):
                             metadata['is_fallback'] = value.lower() in ('true', '1', 'yes', 'sí', 'si', 'verdadero')
                        else:
                            metadata[key] = value
                if not metadata.get('product_name') and metadata.get('display_name'):
                    metadata['product_name'] = metadata['display_name']

        elif filename.endswith('.json'):
            # Discovery routing rows: a single JSON object with target + triggers.
            # {"code","target","tipo":"discovery","triggers":[...],
            #  "priority":int,"soft_depends":[...],"locale_code","source_module"}
            try:
                data = json.loads(content or '{}')
            except (ValueError, TypeError):
                data = {}
            if isinstance(data, dict):
                if data.get('code'):
                    metadata['contexto'] = data['code']
                if data.get('description'):
                    metadata['description'] = data['description']
                if data.get('tipo'):
                    metadata['tipo'] = str(data.get('tipo')).lower()
                loc = data.get('locale') or data.get('locale_code')
                if loc:
                    metadata['locale'] = loc
                if data.get('source_module'):
                    metadata['source_module'] = data['source_module']
                if data.get('active') is not None:
                    metadata['active'] = bool(data['active'])
                metadata['discovery_target'] = data.get('target') or ''
                metadata['discovery_target_kind'] = (
                    data.get('target_kind') or 'domain'
                )
                triggers = data.get('triggers') or []
                if isinstance(triggers, str):
                    triggers = [t.strip() for t in triggers.split(',') if t.strip()]
                metadata['discovery_triggers'] = json.dumps(
                    [str(t).strip() for t in triggers if str(t).strip()],
                    ensure_ascii=False,
                )
                metadata['discovery_priority'] = int(data.get('priority') or 0)
                soft = data.get('soft_depends') or []
                if isinstance(soft, str):
                    soft = [s.strip() for s in soft.split(',') if s.strip()]
                metadata['discovery_soft_depends'] = ','.join(
                    str(s).strip() for s in soft if str(s).strip()
                )

        return metadata
