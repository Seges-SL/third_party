# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
import json
import logging
from .mcp_decorators import mcp_tool
import re
from datetime import datetime

_logger = logging.getLogger(__name__)

def _normalize_text(text):
    """Normalize text for fuzzy search: lowercase, strip accents."""
    if not text:
        return ""
    # Simple normalization: lower case. Ideally use unidecode for accents if available, 
    # but strictly python libraries in Odoo standard might be limited.
    # We'll use a simple char replacement map for common spanish accents if needed,
    # or just lower() for now as 'ilike' in postgres does.
    # For in-memory filtering of JSON:
    text = text.lower()
    replacements = {
        'á': 'a', 'é': 'e', 'í': 'i', 'ó': 'o', 'ú': 'u',
        'à': 'a', 'è': 'e', 'ì': 'i', 'ò': 'o', 'ù': 'u',
        'ñ': 'n', 'ü': 'u'
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text

@mcp_tool(
    name='search_memory',
    description='[MEMORY] Search through long-term conversation history. Returns paginated results to prevent large payload errors.',
    is_write=False,
    validate_schema=True,
    input_schema={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Keywords to search for (e.g., 'project phoenix'). Implicit AND logic."
            },
            "date_from": {
                "type": "string",
                "description": "Optional start date (ISO format YYYY-MM-DD)"
            },
            "date_to": {
                "type": "string",
                "description": "Optional end date (ISO format YYYY-MM-DD)"
            },
            "limit": {
                "type": "integer",
                "description": "Max results per page (max 50, default 20)",
                "default": 20
            },
            "offset": {
                "type": "integer",
                "description": "Pagination offset (default 0)",
                "default": 0
            }
        },
        "required": ["query"]
    }
)
def tool_search_memory(controller, arguments: dict):
    """
    Search conversation history with pagination.
    """
    query = arguments.get('query', '')
    date_from = arguments.get('date_from')
    date_to = arguments.get('date_to')
    limit = int(arguments.get('limit', 20))
    offset = int(arguments.get('offset', 0))
    
    # Safe limits
    if limit > 50: limit = 50
    if limit < 1: limit = 1
    
    if not query:
        return {'content': [{'type': 'text', 'text': "Error: Query parameter is required."}]}
        
    env = controller._get_env_for_operation('read')
    user_id = env.user.id
    
    # 1. Fetch relevant sessions
    domain = [('user_id', '=', user_id)]
    if date_from: domain.append(('last_used_date', '>=', date_from))
    if date_to: domain.append(('create_date', '<=', date_to))
        
    # Optimization: fetch a reasonable window of sessions to scan in memory.
    sessions = env['chatboo.session'].search(domain, order='last_used_date desc', limit=100)
    
    normalized_query_terms = _normalize_text(query).split()
    results = []
    total_matches_scanned = 0
    
    # 2. Iterate and Filter in Memory
    for session in sessions:
        messages = session.get_messages()
        if not messages: continue
            
        for i, msg in enumerate(messages):
            role = msg.get('role')
            content = msg.get('content', '')
            
            if role == 'system' or not content: continue
                
            normalized_content = _normalize_text(content)
            all_terms_match = all(term in normalized_content for term in normalized_query_terms)
            
            if all_terms_match:
                total_matches_scanned += 1
                
                # Check pagination window
                if total_matches_scanned <= offset:
                    continue  # Skip until offset reached
                
                if len(results) >= limit:
                    break
                
                # Build Context Window
                context_window = []
                if i > 0:
                    prev = messages[i-1]
                    if prev.get('content'):
                        context_window.append(f"[{prev.get('role', 'unknown')}] {prev.get('content')[:200]}...")
                
                context_window.append(f"[{role}] {content}")
                
                if i < len(messages) - 1:
                    nxt = messages[i+1]
                    if nxt.get('content'):
                        context_window.append(f"[{nxt.get('role', 'unknown')}] {nxt.get('content')[:200]}...")
                
                chunk = {
                    "session_id": session.id,
                    "date": session.last_used_date.isoformat(),
                    "content": "\n".join(context_window)
                }
                results.append(chunk)

        if len(results) >= limit:
            break

    # Metadata response
    response_data = {
        "query": query,
        "showing_matches": len(results),
        "offset_used": offset,
        "limit_used": limit,
        "has_more": len(results) >= limit,
        "next_offset": offset + len(results) if len(results) >= limit else None,
        "memories": results
    }
    
    if not results:
        return {'content': [{'type': 'text', 'text': f"No memories found for query: '{query}'."}]}

    return {
        'content': [{
            'type': 'text',
            'text': json.dumps(response_data, indent=2, ensure_ascii=False)
        }]
    }
