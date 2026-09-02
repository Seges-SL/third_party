# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""Common utilities and classes for the MCP server."""

import json
import logging
import re

# Aplicar el filtro al logger del módulo
_logger = logging.getLogger(__name__)


class APIKeyLogFilter(logging.Filter):
    """Filtro para eliminar API keys de los logs"""
    
    def filter(self, record):
        """Filtra cualquier mención de api_key=VALOR en los mensajes de log"""
        if hasattr(record, 'msg') and record.msg:
            # Convertir a string si no lo es
            msg = str(record.msg)
            # Patrón para api_key=VALOR (con cualquier valor)
            # Reemplazar api_key=VALOR por api_key=***
            msg = re.sub(
                r'(?i)(api[_-]?key\s*=\s*)([^\s&"\'\)]+)',
                r'\1***',
                msg
            )
            # Patrón para api_key en query strings
            msg = re.sub(
                r'(?i)([?&]api[_-]?key=)([^&\s"]+)',
                r'\1***',
                msg
            )
            record.msg = msg
        
        # También filtrar en args si existen
        if hasattr(record, 'args') and record.args:
            filtered_args = []
            for arg in record.args:
                if isinstance(arg, str):
                    arg = re.sub(
                        r'(?i)(api[_-]?key\s*=\s*)([^\s&"\'\)]+)',
                        r'\1***',
                        arg
                    )
                    arg = re.sub(
                        r'(?i)([?&]api[_-]?key=)([^&\s"]+)',
                        r'\1***',
                        arg
                    )
                filtered_args.append(arg)
            record.args = tuple(filtered_args)
        
        return True


# Aplicar el filtro al logger
_logger.addFilter(APIKeyLogFilter())


class MCPJSONRPCError(Exception):
    """Excepción personalizada para errores MCP con formato JSON-RPC"""
    def __init__(self, error_code, error_message, request_id=None):
        self.error_code = error_code
        self.error_message = error_message
        self.request_id = request_id
        # Crear la respuesta JSON-RPC completa como string
        error_response = {
            'jsonrpc': '2.0',
            'error': {
                'code': error_code,
                'message': error_message
            },
            'id': request_id
        }
        self.jsonrpc_response = json.dumps(error_response)
        super().__init__(error_message)

