# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>

"""
utils/mcp_utils.py - Utilities for MCP tool loading detection
Common logic shared across pns_ai_inference and pns_ai_mcp
"""

import logging
from typing import List, Dict, Optional, Any

logger = logging.getLogger(__name__)

# Empty on purpose: the engine has no business glossary.
# Callers that still want keyword gating pass ``domain_keywords`` themselves.
DEFAULT_DOMAIN_TRIGGER_KEYWORDS: List[str] = []


def should_load_mcp_tools(
    user_message: str,
    messages_dict: List[Dict[str, str]],
    domain_keywords: Optional[List[str]] = None,
    mcp_server_names: Optional[List[str]] = None
) -> bool:
    """
    Detects if the user's query requires MCP tools.
    
    If not required, tools and core prompts are skipped for performance.
    
    Detection considers:
    - Current user message
    - Recent conversation context (prior tool_calls / tool messages)
    - Optional caller-provided domain trigger keywords (never a built-in
      business glossary)
    - MCP server names (optional)
    With no keywords, this does not skip tools (fail-open).
    
    Args:
        user_message: Current user message
        messages_dict: Full message history
        domain_keywords: Optional list of domain trigger keywords (uses defaults if None)
        mcp_server_names: Optional list of MCP server names to check
        
    Returns:
        True if tools should be loaded, False otherwise
    """
    # Use provided keywords or defaults
    keywords = domain_keywords if domain_keywords is not None else DEFAULT_DOMAIN_TRIGGER_KEYWORDS
    
    # Combine current message with recent context
    # Consider last 6 messages
    text_content = user_message.lower()
    context_messages = messages_dict[-6:] if len(messages_dict) > 6 else messages_dict
    
    for msg in context_messages:
        role = msg.get("role", "")
        if role in ["user", "assistant"]:
            content = str(msg.get("content", "")).lower()
            text_content += " " + content
            
            # If assistant used tools recently, context implies capability usage
            if role == "assistant" and msg.get("tool_calls"):
                logger.debug(f"🔍 Context: Assistant used tools recently - implies MCP usage")
                return True
    
    # Check for recent tool messages
    tool_messages = [msg for msg in context_messages if msg.get("role") == "tool"]
    if tool_messages:
        logger.debug(f"🔍 Context: {len(tool_messages)} recent tool messages - implies MCP usage")
        return True
    
    should_load = False
    if keywords:
        should_load = any(keyword in text_content for keyword in keywords)
        if should_load:
            matched_kw = next((k for k in keywords if k in text_content), None)
            logger.info(f"🔍 [DEBUG TRIGGER] Matched keyword: '{matched_kw}'")

    # Dynamic check for configured MCP server names
    if not should_load and mcp_server_names:
        try:
            server_names_lower = [name.lower() for name in mcp_server_names]
            if any(server_name in text_content for server_name in server_names_lower):
                logger.info(f"🔍 Detected MCP server name in query: {mcp_server_names}")
                should_load = True
        except Exception as e:
            logger.warning(f"[RECOMMENDED] Error checking MCP server names: {e}")
    
    if should_load:
        logger.info(f"🔍 Query implies MCP usage - loading tools")
        return True
    if not keywords:
        # No engine glossary: do not skip tools on a word list we do not own.
        return True
    logger.info(f"🔍 Query does NOT imply MCP usage - skipping tools for performance")
    return False


def extract_user_token_from_request(
    request: Any,
    server_key: Optional[str] = None
) -> Optional[str]:
    """
    Extrae el user_token de una petición HTTP de forma determinista.
    
    SOLO busca el header 'X-Mcp-Token' - sin fallbacks ni alternativas.
    
    Args:
        request: Objeto de petición (FastAPI Request, Odoo request, o dict con headers)
        server_key: No usado (mantenido por compatibilidad de firma, ignorado)
        
    Returns:
        user_token si se encuentra en X-Mcp-Token, None si no
    """
    headers = None
    
    # Extraer headers según el tipo de request
    if hasattr(request, 'headers'):
        # FastAPI Request o similar
        headers = request.headers
    elif hasattr(request, 'httprequest') and hasattr(request.httprequest, 'headers'):
        # Odoo request
        headers = request.httprequest.headers
    elif isinstance(request, dict):
        # Dict con headers directamente
        headers = request
    
    if not headers:
        return None
    
    # ÚNICO método: X-Mcp-Token (determinista, sin fallbacks)
    user_token = headers.get('X-Mcp-Token')
    return user_token if user_token else None


def get_locale_settings(request: Any) -> Dict[str, str]:
    """
    Extrae configuraciones de locale y formateo de la petición de forma determinista.
    Prioriza headers X-Pns-* y luego Accept-Language.
    """
    headers = {}
    if hasattr(request, 'headers'):
        headers = request.headers
    elif hasattr(request, 'httprequest') and hasattr(request.httprequest, 'headers'):
        headers = request.httprequest.headers
    elif isinstance(request, dict):
        headers = request

    # Valores por defecto (Standard del proyecto)
    settings = {
        'pk_decimal_sep': ',',
        'pk_thousands_sep': '.',
        'pk_date_format': '%d/%m/%Y',
        'user_lang': 'es_ES'
    }

    if not headers:
        return settings

    # 1. Detectar idioma/locale
    lang = headers.get('X-Pns-Lang') or headers.get('X-Pns-Language') or headers.get('X-User-Lang')
    if not lang:
        accept_lang = headers.get('Accept-Language', '')
        if accept_lang:
            # Simplificado: tomar el primero (ej: es-ES)
            lang = accept_lang.split(',')[0].strip().replace('-', '_')
    
    if lang:
        settings['user_lang'] = lang

    # 2. Detectar separadores explícitos
    d_sep = headers.get('X-Pns-Decimal-Sep') or headers.get('X-Decimal-Sep')
    if d_sep: settings['pk_decimal_sep'] = d_sep

    t_sep = headers.get('X-Pns-Thousands-Sep') or headers.get('X-Thousands-Sep')
    if t_sep: settings['pk_thousands_sep'] = t_sep

    dt_fmt = headers.get('X-Pns-Date-Format') or headers.get('X-Date-Format')
    if dt_fmt: settings['pk_date_format'] = dt_fmt

    return settings


def build_mcp_extra_headers(user_token: Optional[str], request: Any = None) -> Dict[str, str]:
    """
    Construye el diccionario de extra_headers para llamadas MCP a partir de un mcp_api_key.
    Propaga automáticamente el locale si está presente en la request.
    """
    headers = {}
    
    if user_token:
        headers["X-Mcp-Token"] = user_token
    
    if request:
        # 1. Propagar Agente/LLM
        headers_obj = None
        if hasattr(request, 'headers'):
            headers_obj = request.headers
        elif hasattr(request, 'httprequest') and hasattr(request.httprequest, 'headers'):
            headers_obj = request.httprequest.headers
        
        if headers_obj:
            agent_llm = headers_obj.get('X-MCP-LLM') or headers_obj.get('X-MCP-Agent')
            if agent_llm:
                headers["X-MCP-LLM"] = agent_llm
        
        # 2. Propagar Locale Settings de forma transparente
        locale_settings = get_locale_settings(request)
        for key, val in locale_settings.items():
            # Convertir pk_decimal_sep -> X-Pns-Decimal-Sep, etc. para transporte
            header_name = "X-Pns-" + key.replace('pk_', '').replace('_', '-').title()
            if key == 'user_lang': header_name = "X-Pns-Lang"
            headers[header_name] = val
    
    return headers

