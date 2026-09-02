# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""MCP tools to analyze context usage."""

import json
import logging
from datetime import datetime, timedelta
from .mcp_decorators import mcp_tool
from .controller_helpers import tool_env

_logger = logging.getLogger(__name__)


@mcp_tool(
    name='get_context_usage_stats',
    description='Obtiene estadísticas de uso de los contextos MCP. Muestra qué contextos se consultan más, cuáles no se usan, y patrones de uso. Útil para optimización continua.',
    is_write=False,
    validate_schema=True
)
def tool_get_context_usage_stats(controller, arguments: dict) -> dict:
    """
    Tool: Obtiene estadísticas de uso de los contextos MCP.
    
    Args:
        controller: Instancia del controlador MCP
        arguments: Diccionario con los argumentos:
            - days (int, opcional): Número de días hacia atrás para analizar (por defecto 30)
            - include_unused (bool, opcional): Incluir contextos no utilizados (por defecto True)
    
    Returns:
        dict: Estadísticas de uso de contextos
    """
    days = arguments.get('days', 30)
    include_unused = arguments.get('include_unused', True)
    
    try:
        env = tool_env(controller, sudo=True)
        if 'ai.context' not in env:
            return {
                'error': {
                    'code': -32603,
                    'message': 'Modelo ai.context no disponible'
                }
            }
        
        # Obtener todos los contextos activos
        contexts = env['ai.context'].search([
            ('active', '=', True)
        ])
        
        # Calcular fecha límite
        date_limit = datetime.now() - timedelta(days=days)
        
        # Clasificar contextos
        most_used = []
        recently_used = []
        never_used = []
        unused_recently = []
        
        i = 0
        while i < len(contexts):
            context = contexts[i]
            usage_count = context.usage_count or 0
            last_used = context.last_used
            
            context_info = {
                'code': context.code,
                'description': context.description or '',
                'usage_count': usage_count,
                'last_used': last_used.strftime('%Y-%m-%d %H:%M:%S') if last_used else None,
                'is_hardcoded': context.context_type == 'core'
            }
            
            if usage_count == 0:
                never_used.append(context_info)
            elif last_used and last_used >= date_limit:
                recently_used.append(context_info)
                most_used.append(context_info)
            else:
                unused_recently.append(context_info)
            
            i = i + 1
        
        # Ordenar por uso descendente
        n = len(most_used)
        j = 0
        while j < n - 1:
            k = 0
            while k < n - j - 1:
                if most_used[k]['usage_count'] < most_used[k + 1]['usage_count']:
                    temp = most_used[k]
                    most_used[k] = most_used[k + 1]
                    most_used[k + 1] = temp
                k = k + 1
            j = j + 1
        
        # Calcular estadísticas generales
        total_contexts = len(contexts)
        total_usage = 0
        i = 0
        while i < len(contexts):
            total_usage = total_usage + (contexts[i].usage_count or 0)
            i = i + 1
        
        result = {
            'period_days': days,
            'summary': {
                'total_contexts': total_contexts,
                'total_consultations': total_usage,
                'never_used_count': len(never_used),
                'recently_used_count': len(recently_used),
                'unused_recently_count': len(unused_recently)
            },
            'most_used': most_used[:10] if len(most_used) >= 10 else most_used,
            'recently_used': recently_used[:20] if len(recently_used) >= 20 else recently_used
        }
        
        if include_unused:
            result['never_used'] = never_used
            result['unused_recently'] = unused_recently
        
        return {
            'content': [
                {
                    'type': 'text',
                    'text': json.dumps(result, indent=2, default=str)
                }
            ]
        }
    except Exception as e:
        _logger.exception("MCP: Error obteniendo estadísticas de uso de contextos")
        return {
            'error': {
                'code': -32603,
                'message': f'Error getting context usage stats: {str(e)}'
            }
        }

