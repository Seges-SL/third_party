# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""Decorator system that auto-registers MCP tools with schema validation."""

import inspect
import logging
from typing import Any, Callable, Dict, List, Optional, Tuple, Type, get_type_hints
from functools import wraps

# Polyfill for Python < 3.8
try:
    from typing import get_origin, get_args
except ImportError:
    def get_origin(tp):
        if hasattr(tp, "__origin__"):
            return tp.__origin__
        return None

    def get_args(tp):
        if hasattr(tp, "__args__"):
            return tp.__args__
        return ()

_logger = logging.getLogger(__name__)

# Registro global de tools
_MCP_TOOLS_REGISTRY: Dict[str, Dict[str, Any]] = {}

def _python_type_to_json_schema_type(python_type: Type) -> Dict[str, Any]:
    """
    Convierte un tipo de Python a un tipo de esquema JSON.
    Soporta tipos básicos y algunos tipos avanzados.
    """
    # Tipos básicos
    if python_type == str:
        return {'type': 'string'}
    elif python_type == int:
        return {'type': 'integer'}
    elif python_type == float:
        return {'type': 'number'}
    elif python_type == bool:
        return {'type': 'boolean'}
    elif python_type == dict:
        return {'type': 'object'}
    elif python_type == list:
        return {'type': 'array'}
    elif python_type == type(None) or python_type == None:
        return {'type': 'null'}
    
    # Optional[T] -> T o null
    origin = get_origin(python_type)
    if origin is Optional or (hasattr(python_type, '__origin__') and python_type.__origin__ is type(None)):
        args = get_args(python_type)
        if args:
            # Optional[T] -> el tipo T
            return _python_type_to_json_schema_type(args[0])
        return {'type': 'null'}
    
    # List[T], Dict[K, V], etc.
    if origin is list:
        args = get_args(python_type)
        if args:
            return {
                'type': 'array',
                'items': _python_type_to_json_schema_type(args[0])
            }
        return {'type': 'array'}
    
    if origin is dict:
        args = get_args(python_type)
        if len(args) >= 2:
            return {
                'type': 'object',
                'additionalProperties': _python_type_to_json_schema_type(args[1])
            }
        return {'type': 'object'}
    
    # Por defecto, tratar como string si no se reconoce
    _logger.warning(f"MCP: Tipo Python no reconocido para esquema JSON: {python_type}, usando 'string' por defecto")
    return {'type': 'string'}


def _extract_schema_from_function(func: Callable) -> Dict[str, Any]:
    """
    Extrae el esquema JSON del inputSchema desde los type hints de una función.
    Para funciones que usan el formato estándar (controller, arguments), busca
    type hints en el cuerpo de la función o en el docstring.
    """
    try:
        # Obtener signature
        sig = inspect.signature(func)
        
        # Verificar si la función tiene parámetros además de controller y arguments
        has_explicit_params = False
        for param_name in sig.parameters:
            if param_name not in ('self', 'controller', 'arguments'):
                has_explicit_params = True
                break
        
        # Si la función tiene parámetros explícitos, extraer de ellos
        if has_explicit_params:
            hints = get_type_hints(func, include_extras=True)
            properties = {}
            required = []
            
            for param_name, param in sig.parameters.items():
                # Saltar 'self', 'controller', 'arguments' que son parámetros internos
                if param_name in ('self', 'controller', 'arguments'):
                    continue
                
                # Obtener tipo del parámetro
                param_type = hints.get(param_name, Any)
                
                # Si es Any o no tiene tipo, usar 'object' por defecto
                if param_type == Any or param_type not in hints:
                    # FIX: Default to str instead of dict (Object) to avoid JSON parsing errors
                    # when the parameter is expected to be a code string.
                    param_type = str
                
                # Convertir a esquema JSON
                param_schema = _python_type_to_json_schema_type(param_type)
                
                # Obtener descripción del docstring si está disponible
                description = None
                if func.__doc__:
                    # Buscar descripción del parámetro en el docstring
                    doc_lines = func.__doc__.split('\n')
                    for i, line in enumerate(doc_lines):
                        if f':param {param_name}:' in line or f':param {param_name} ' in line:
                            description = line.split(':', 1)[1].strip() if ':' in line else None
                            break
                
                # Si no hay descripción, usar el nombre del parámetro
                if not description:
                    description = f"Parámetro {param_name}"
                
                param_schema['description'] = description
                properties[param_name] = param_schema
                
                # Si no tiene default, es requerido
                if param.default == inspect.Parameter.empty:
                    required.append(param_name)
            
            return {
                'type': 'object',
                'properties': properties,
                'required': required
            }
        else:
            # Función usa formato estándar (controller, arguments)
            # Intentar extraer parámetros del docstring o código fuente
            # Por ahora, devolver esquema vacío (se puede mejorar parseando el código)
            return {
                'type': 'object',
                'properties': {},
                'required': []
            }
    except Exception as e:
        _logger.warning(f"MCP: Error extrayendo esquema de {func.__name__}: {str(e)}")
        # Devolver esquema vacío por defecto
        return {
            'type': 'object',
            'properties': {},
            'required': []
        }


def _validate_arguments(schema: Dict[str, Any], arguments: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    """
    Valida los argumentos contra el esquema.
    Retorna (es_valido, mensaje_error)
    """
    if not isinstance(arguments, dict):
        return False, "Arguments must be a dictionary"
    
    properties = schema.get('properties', {})
    required = schema.get('required', [])
    
    # Verificar campos requeridos
    for field in required:
        if field not in arguments:
            return False, f"Missing required parameter: {field}"
    
    # Validar tipos básicos (validación simple)
    for field, value in arguments.items():
        if field not in properties:
            # Permitir campos adicionales (podría ser más estricto)
            continue
        
        field_schema = properties[field]
        field_type = field_schema.get('type')
        
        if field_type == 'string' and not isinstance(value, str):
            return False, f"Parameter '{field}' must be a string"
        elif field_type == 'integer' and not isinstance(value, int):
            return False, f"Parameter '{field}' must be an integer"
        elif field_type == 'number' and not isinstance(value, (int, float)):
            return False, f"Parameter '{field}' must be a number"
        elif field_type == 'boolean' and not isinstance(value, bool):
            return False, f"Parameter '{field}' must be a boolean"
        elif field_type == 'object' and not isinstance(value, dict):
            return False, f"Parameter '{field}' must be an object"
        elif field_type == 'array' and not isinstance(value, list):
            return False, f"Parameter '{field}' must be an array"
    
    return True, None


def mcp_tool(
    name: Optional[str] = None,
    description: Optional[str] = None,
    is_write: bool = False,
    validate_schema: bool = True,
    input_schema: Optional[Dict[str, Any]] = None
):
    """
    Decorador para registrar una función como herramienta MCP.
    
    Args:
        name: Nombre de la herramienta (por defecto: nombre de la función)
        description: Descripción de la herramienta (por defecto: docstring de la función)
        is_write: Si la herramienta requiere permisos de escritura
        validate_schema: Si se debe validar el esquema automáticamente
        input_schema: Esquema JSON explícito (opcional, si se omite se extrae de la función)
    
    Ejemplo:
        @mcp_tool(
            name='relaxaicode',
            description='Ejecuta código Python bajo entorno relaxaicode',
            is_write=True
        )
        def tool_relaxaicode(controller, arguments: dict) -> dict:
            code: str = arguments.get('code', '')
            # ...
    """
    def decorator(func: Callable) -> Callable:
        # Determinar nombre de la tool
        tool_name = name or func.__name__
        
        # Obtener descripción
        tool_description = description or (func.__doc__ or '').strip()
        if tool_description:
            # Limpiar docstring (quitar espacios extra)
            tool_description = ' '.join(tool_description.split())
        
        # Determinar esquema: usar el explícito si existe, sino extraerlo
        final_schema = input_schema
        if final_schema is None:
            final_schema = _extract_schema_from_function(func)
        
        # Registrar la tool

        
        _logger.info(f"MCP: Tool registrada: {tool_name} (write={is_write})")
        
        # Wrapper que valida esquema si está habilitado
        @wraps(func)
        def wrapper(controller, arguments: Dict[str, Any]) -> Any:
            _logger.info(f"TRACE_MCP: Decorator Wrapper executed for {tool_name}")
            if validate_schema:
                is_valid, error_msg = _validate_arguments(final_schema, arguments)
                if not is_valid:
                    return {
                        'error': {
                            'code': -32602,
                            'message': f'Invalid arguments: {error_msg}'
                        }
                    }
            
            # Verificar si la función tiene parámetros explícitos además de controller
            sig = inspect.signature(func)
            has_explicit_params = False
            explicit_params = {}
            for param_name, param in sig.parameters.items():
                if param_name not in ('self', 'controller', 'arguments'):
                    has_explicit_params = True
                    # Extraer el valor de arguments si existe
                    if param_name in arguments:
                        explicit_params[param_name] = arguments[param_name]
                    elif param.default != inspect.Parameter.empty:
                        # Usar valor por defecto si existe
                        explicit_params[param_name] = param.default
                    # Si no tiene default y no está en arguments, se validó antes en validate_schema
            
            # Llamar a la función original
            if has_explicit_params:
                # Pasar parámetros explícitos como kwargs (sin arguments)
                return func(controller, **explicit_params)
            else:
                # Formato estándar (controller, arguments)
                return func(controller, arguments)
        
        # Guardar metadata en el wrapper
        wrapper._mcp_tool_name = tool_name
        # wrapper._mcp_tool_metadata assignment removed as it depends on registry
        
        # Registrar la tool (USANDO EL WRAPPER)
        # Esto es CRUCIAL para que el logging y validación se ejecuten
        _MCP_TOOLS_REGISTRY[tool_name] = {
            'name': tool_name,
            'description': tool_description,
            'inputSchema': final_schema,
            'is_write': is_write,
            'function': wrapper, # [FIX] Register wrapper, NOT func
            'validate_schema': validate_schema
        }
        
        return wrapper
    
    return decorator


def get_registered_tools() -> Dict[str, Dict[str, Any]]:
    """
    Obtiene todas las tools registradas.
    Retorna un diccionario con la metadata de cada tool (sin la función).
    """
    result = {}
    for tool_name, tool_data in _MCP_TOOLS_REGISTRY.items():
        result[tool_name] = {
            'name': tool_data['name'],
            'description': tool_data['description'],
            'inputSchema': tool_data['inputSchema'],
            'is_write': tool_data['is_write']
        }
    return result


def get_tool_function(tool_name: str) -> Optional[Callable]:
    """
    Obtiene la función de una tool registrada.
    """
    if tool_name in _MCP_TOOLS_REGISTRY:
        return _MCP_TOOLS_REGISTRY[tool_name]['function']
    return None


def get_tool_metadata(tool_name: str) -> Optional[Dict[str, Any]]:
    """
    Obtiene la metadata de una tool registrada (sin la función).
    """
    if tool_name in _MCP_TOOLS_REGISTRY:
        tool_data = _MCP_TOOLS_REGISTRY[tool_name].copy()
        tool_data.pop('function', None)  # No incluir la función
        return tool_data
    return None

