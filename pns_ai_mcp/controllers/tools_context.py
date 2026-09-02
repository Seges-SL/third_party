# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""MCP tool to query contexts; the system_prompt case returns the discovery bundle."""

import json
import logging
from .mcp_decorators import mcp_tool
from .controller_helpers import tool_env
from ..utils.agent_identity import foreign_identity_on_demand_message
from ..utils.system_info import resource_system_info

_logger = logging.getLogger(__name__)


def _current_mcp_agent_code(controller, env=None):
    code = ''
    if hasattr(controller, '_get_mcp_agent_code'):
        code = controller._get_mcp_agent_code() or ''
    if not code and env and 'ai.agent' in env:
        try:
            code = env['ai.agent'].resolve_mcp_agent_code(None) or ''
        except Exception:
            code = ''
    return code or 'pns_ai_mcp'


def refuse_foreign_identity_pack(controller, env, context_code):
    """MCP error dict if ``context_code`` is another agent's identity pack."""
    msg = foreign_identity_on_demand_message(
        _current_mcp_agent_code(controller, env),
        context_code,
    )
    if not msg:
        return None
    return {
        'error': {
            'code': -32602,
            'message': msg,
        }
    }


def generate_contexts_index_core(available_contexts, max_desc_len=200):
    """
    Genera un índice compacto de contextos disponibles con estructura por prioridades.
    
    Args:
        available_contexts: Lista de registros de contextos (mcp_context)
        max_desc_len: Longitud máxima de descripción por contexto (por defecto 80)
    
    Returns:
        str: Índice compacto en formato texto estructurado
    """
    lines = ["=== CONTEXTOS DISPONIBLES ==="]
    lines.append("Usa get_context(context_name='...') para obtener el contenido completo de un contexto.")
    lines.append("Alternativa: puedes usar prompts/get directamente si prefieres el método estándar MCP.")
    lines.append("")
    
    # Separar contextos por nivel de directiva
    mandatory = []
    prohibited = []
    required = []
    recommended = []
    optional = []
    others = []
    
    seen_bases = set()
    for context in available_contexts:
        context_code = context.code
        
        # FILTRAR VARIANTES por el campo explícito base_code (no por regex del code)
        base_name = context.base_code or context_code
        
        if base_name in seen_bases:
            continue
        seen_bases.add(base_name)
        
        description = context.description or f'Contexto: {base_name}'
        
        # Add auto-resolve hint if it's a base for multiple variants
        if base_name != context_code:
            description += " [AUTO-RESOLVED]"
        
        # Truncar descripción si es necesario
        if len(description) > max_desc_len:
            truncated = description[:max_desc_len - 3]
            last_space = truncated.rfind(' ')
            if last_space > max_desc_len * 0.7:
                truncated = truncated[:last_space]
            description = truncated + "..."
        
        entry = f"- [ID]: {base_name} | {description}"
        
        # Detectar nivel de directiva desde la descripción (buscar tags exactos)
        desc_upper = description.upper()
        if '[MANDATORY]' in desc_upper:
            mandatory.append(entry)
        elif '[PROHIBITED]' in desc_upper:
            prohibited.append(entry)
        elif '[REQUIRED]' in desc_upper:
            required.append(entry)
        elif '[RECOMMENDED]' in desc_upper:
            recommended.append(entry)
        elif '[OPTIONAL]' in desc_upper:
            optional.append(entry)
        else:
            others.append(entry)
    
    # Generar índice estructurado siguiendo jerarquía
    lines.append("Para Consultar: use get_context(context_name='ID')")
    lines.append("")

    if mandatory:
        lines.append("[MANDATORY]:")
        lines.extend(mandatory)
        lines.append("")
        
    if prohibited:
        lines.append("[PROHIBITED]:")
        lines.extend(prohibited)
        lines.append("")
    
    if required:
        lines.append("[REQUIRED]:")
        lines.extend(required)
        lines.append("")

    if recommended:
        lines.append("[RECOMMENDED]:")
        lines.extend(recommended)
        lines.append("")

    if optional:
        lines.append("[OPTIONAL]:")
        lines.extend(optional)
        lines.append("")
        
    if others:
        lines.append("NO TAG / OTHERS:")
        lines.extend(others)
    
    lines.append("")
    lines.append("--- FINAL DEL ÍNDICE ---")
    return "\n".join(lines)



# Import shared utility for metadata stripping (canonical implementation)
from ..utils.context_utils import strip_xml_metadata


@mcp_tool(
    name='get_context',
    description='[MANDATORY] Retrieves the content of a specific context on demand. ⚠️ CRITICAL: Use this tool to list or load knowledge packs. Relaxaicode on ai.context is rejected. FIRST, call get_context(context_name="contexts_index_core") to see the REGISTRY of available IDs. Then, call this tool with a real ID from that list. DO NOT GUESS names. DO NOT USE PLACEHOLDERS. Do not dump pack XML; answer from what is already injected, in prose.',
    is_write=False,
    validate_schema=True,
    input_schema={
        "type": "object",
        "properties": {
            "context_name": {
                "type": "string",
                "description": "Name of the context to retrieve (e.g. 'contexts_index_core'). ALWAYS use a real ID from the index registry. Special: system_prompt = agent always-on bundle; pass optional query to inject domain packs."
            },
            "query": {
                "type": "string",
                "description": "Optional. When context_name is system_prompt, user question for domain-index match and pack injection."
            }
        },
        "required": ["context_name"]
    }
)
def tool_get_context(controller, arguments: dict) -> dict:
    """
    Tool: Obtiene el contenido de un contexto específico bajo demanda.
    
    Args:
        controller: Instancia del controlador MCP
        arguments: Diccionario con los argumentos:
            - context_name (str, requerido): Nombre del contexto a consultar
                Ejemplos: 'relaxaicode_accounting_searches', 'relaxaicode_calendar_events', 
                'corporative_terms', 'relaxaicode_filters', etc.
    
    Returns:
        dict: Contenido del contexto solicitado en formato MCP estándar
    """
    context_name = arguments.get('context_name')
    
    if not context_name:
        return {
            'error': {
                'code': -32602,
                'message': 'Missing required parameter: context_name'
            }
        }
    
    # Special case: contexts_index dynamic generation or generic query
    # Detect synonyms and common hallucinated placeholders
    lc_name = context_name.lower()
    is_index_request = any(keyword in lc_name for keyword in ['index', 'list', 'core', 'menu', 'directory'])
    is_placeholder = lc_name in ['context_name', 'name', 'example', '...']
    
    if is_index_request or is_placeholder:
        try:
            env = tool_env(controller, sudo=True)
            if 'ai.context' in env:
                available_contexts = env['ai.context'].get_listable_for_mcp()
                index_content = generate_contexts_index_core(available_contexts)
                # Clear instructions for the LLM
                header = f"### [INDEX: Available MCP Contexts]\n"
                instruction = "CHOOSE ONE 'base_name' from the list below and call get_context(context_name='the_name') to load it.\n"
                return {
                    'content': [
                        {
                            'type': 'text',
                            'text': f"{header}{instruction}\n{index_content}"
                        }
                    ]
                }
        except Exception as e:
            _logger.error("MCP: Error generating contexts index: %s", str(e))

    # Special case: system://info bridge
    # Some LLMs try to access the resource via get_context. bridging detailed system info.
    if context_name == 'system://info':
        try:
            env = tool_env(controller, sudo=True)
            info = resource_system_info(env)
            return {
                'content': [
                    {
                        'type': 'text',
                        'text': f"### [Resource: system://info]\n{json.dumps(info, indent=2)}"
                    }
                ]
            }
        except Exception as e:
             _logger.error("MCP: Error getting system info in tool: %s", str(e))
             # Fallback to standard error

    # Special case: system_prompt = Discovery Bundle
    # El Router carga prompts críticos vía get_context; prompts/get usa otra ruta.
    # Ambas deben devolver el mismo bundle (core+locale+domain según locale).
    if context_name == 'system_prompt':
        try:
            env = tool_env(controller, sudo=True)
            if 'ai.context' not in env:
                raise ValueError("mcp_context model not available")
            # Siempre cascada intrínseca (User > Compañía > Default). No payload/router.
            user_lang = controller._get_user_locale()
            mcp_agent = controller._get_mcp_agent_code() if hasattr(controller, '_get_mcp_agent_code') else ''
            if not mcp_agent:
                mcp_agent = env['ai.agent'].resolve_mcp_agent_code(None)
            bundled_content = env['ai.agent'].get_for_agent(
                mcp_agent, user_locale=user_lang,
            )
            query = (
                arguments.get('query')
                or arguments.get('user_message')
                or arguments.get('message')
                or ''
            )
            agent = env['ai.agent'].search([('code', '=', mcp_agent)], limit=1)
            if agent:
                bundled_content = agent.enrich_with_domain_index(
                    bundled_content,
                    user_message=query,
                    user_locale=user_lang,
                )
            _logger.info(
                "MCP: system_prompt bundle via get_context (agent=%s, locale=%s, %d chars)",
                mcp_agent, user_lang, len(bundled_content),
            )
            return {
                'content': [
                    {
                        'type': 'text',
                        'text': f"### [System Knowledge Context - Locale: {user_lang}]\n{bundled_content}"
                    }
                ]
            }
        except Exception as e:
            _logger.exception("MCP: Error getting system_prompt bundle: %s", str(e))
            return {
                'error': {
                    'code': -32603,
                    'message': f'Error generating system_prompt bundle: {str(e)}'
                }
            }

    # Smart loading: Use get_context_for_country for automatic country/locale resolution
    try:
        env = tool_env(controller, sudo=True)
        blocked = refuse_foreign_identity_pack(controller, env, context_name)
        if blocked:
            return blocked
        if 'ai.context' in env:
            # Siempre cascada intrínseca (User > Compañía > Default). No payload/router.
            user_lang = controller._get_user_locale()

            # Extract base name (remove _ES, _FR, _es_ES, etc. if present)
            base_name = env['ai.context'].get_base_context_name(context_name)
            
            # Use smart loading to get country/locale-specific context
            # Pass user_locale explicitly to allow virtualization
            context = env['ai.context'].get_context_for_country(base_name, user_locale=user_lang)
            
            if context:
                _logger.info("MCP: Context resolved: %s → %s (smart loading)", context_name, context.code)
                
                # Record usage
                try:
                    env['ai.context'].record_context_usage(context.code)
                except Exception as e:
                    _logger.warning("MCP: Error recording context usage: %s", str(e))
                
                # Resolve {locale} placeholders
                resolved_content = controller._resolve_locale_placeholders(context.content)
                
                # Strip metadata to save tokens
                cleaned_content = strip_xml_metadata(resolved_content)

                return {
                    'content': [
                        {
                            'type': 'text',
                            'text': f"### [Context: {context_name}]\n{cleaned_content}"
                        }
                    ]
                }
            
            _logger.debug("MCP: Contexto no encontrado: %s", context_name)
    except Exception as e:
        _logger.exception("MCP: Error obteniendo contexto: %s", str(e))
        return {
            'error': {
                'code': -32603,
                'message': f'Error getting context: {str(e)}',
                'suggestion': 'Check the available contexts index in the system prompt or use prompts/list.'
            }
        }
    
    # Si no se encontró en ningún lugar - mensaje de error mejorado con HINT semántico
    return {
        'error': {
            'code': -32602,
            'message': f'Context not found: {context_name}',
            'suggestion': 'Check the available contexts index in the system prompt or use prompts/list.',
            'system_hint': "SYSTEM HINT: The requested documentation context does not exist. You MUST use 'relaxaicode' to query the Odoo database directly for this information."
        }
    }


@mcp_tool(
    name='get_corporative_terms',
    description='Gets corporate terms glossary automatically detecting user language. Returns context based on Odoo user language preference (e.g., corporative_terms_es_ES, corporative_terms_en_US). [REQUIRED] Use this instead of get_context("corporative_terms_{locale}") where {locale} is user_lang.',
    is_write=False,
    validate_schema=True
)
def tool_get_corporative_terms(controller, arguments: dict) -> dict:
    """
    Tool: Gets corporate terms glossary with automatic language detection.
    
    Automatically detects the Odoo user's language preference and returns the appropriate
    corporative_terms context (ES for Spanish, EN for English).
    
    Args:
        controller: MCP controller instance
        arguments: Dictionary (empty, no parameters required)
    
    Returns:
        dict: Content of the corporative_terms context in the user's language
    """
    try:
        # Use the same locale resolution logic as _resolve_locale_placeholders
        # This provides proper fallback: MCP user -> request.env.user -> 'en_US'
        user_lang = controller._get_user_locale()
        
        # Use user_lang directly to construct context name (e.g., 'es_ES' -> 'corporate_terms_es_ES')
        # This works with the {locale} resolution system and uses the same fallback logic
        context_code = f'corporate_terms_{user_lang}'
        
        # Detect language for logging
        if user_lang.startswith('en'):
            detected_lang = 'English'
        else:
            detected_lang = 'Spanish'
        
        _logger.info("MCP: Detected user language: %s, using context: %s", user_lang, context_code)
        
        # Use get_context internally with the detected context code
        # The {locale} placeholder will be resolved automatically when serving the context
        return tool_get_context(controller, {'context_name': context_code})
        
    except Exception as e:
        _logger.exception("MCP: Error in get_corporative_terms: %s", str(e))
        # Fallback uses the same logic (will default to 'en_US' via _get_user_locale)
        try:
            fallback_lang = controller._get_user_locale()
        except:
            fallback_lang = 'en_US'  # Ultimate fallback
        return tool_get_context(controller, {'context_name': f'corporative_terms_{fallback_lang}'})