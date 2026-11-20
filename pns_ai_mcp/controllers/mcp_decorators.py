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

# Global tool registry
_MCP_TOOLS_REGISTRY: Dict[str, Dict[str, Any]] = {}

def _python_type_to_json_schema_type(python_type: Type) -> Dict[str, Any]:
    """
    Turn a Python type into a JSON schema type.
    Supports basic types and some advanced ones.
    """
    # Basic types
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
    
    # Optional[T] -> T or null
    origin = get_origin(python_type)
    if origin is Optional or (hasattr(python_type, '__origin__') and python_type.__origin__ is type(None)):
        args = get_args(python_type)
        if args:
            # Optional[T] -> the type T
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
    
    # By default, treat as string if not recognized
    _logger.warning(f"MCP: Unrecognized Python type for JSON schema: {python_type}, defaulting to 'string'")
    return {'type': 'string'}


def _extract_schema_from_function(func: Callable) -> Dict[str, Any]:
    """
    Extract the inputSchema JSON schema from a function's type hints.
    For functions using the standard form (controller, arguments), it looks
    for type hints in the function body or in the docstring.
    """
    try:
        # Get the signature
        sig = inspect.signature(func)
        
        # Check whether the function has parameters besides controller and arguments
        has_explicit_params = False
        for param_name in sig.parameters:
            if param_name not in ('self', 'controller', 'arguments'):
                has_explicit_params = True
                break
        
        # If the function has explicit parameters, extract from them
        if has_explicit_params:
            hints = get_type_hints(func, include_extras=True)
            properties = {}
            required = []
            
            for param_name, param in sig.parameters.items():
                # Skip 'self', 'controller', 'arguments': they are internal parameters
                if param_name in ('self', 'controller', 'arguments'):
                    continue
                
                # Get the parameter type
                param_type = hints.get(param_name, Any)
                
                # If it is Any or has no type, use 'object' by default
                if param_type == Any or param_type not in hints:
                    # FIX: Default to str instead of dict (Object) to avoid JSON parsing errors
                    # when the parameter is expected to be a code string.
                    param_type = str
                
                # Convert to JSON schema
                param_schema = _python_type_to_json_schema_type(param_type)
                
                # Get the description from the docstring if there is one
                description = None
                if func.__doc__:
                    # Look for the parameter description in the docstring
                    doc_lines = func.__doc__.split('\n')
                    for i, line in enumerate(doc_lines):
                        if f':param {param_name}:' in line or f':param {param_name} ' in line:
                            description = line.split(':', 1)[1].strip() if ':' in line else None
                            break
                
                # If there is no description, use the parameter name
                if not description:
                    description = f"Parameter {param_name}"
                
                param_schema['description'] = description
                properties[param_name] = param_schema
                
                # If it has no default, it is required
                if param.default == inspect.Parameter.empty:
                    required.append(param_name)
            
            return {
                'type': 'object',
                'properties': properties,
                'required': required
            }
        else:
            # The function uses the standard form (controller, arguments)
            # Try to extract parameters from the docstring or source code
            # For now, return an empty schema (could improve by parsing the code)
            return {
                'type': 'object',
                'properties': {},
                'required': []
            }
    except Exception as e:
        _logger.warning(f"MCP: Error extracting schema from {func.__name__}: {str(e)}")
        # Return an empty schema by default
        return {
            'type': 'object',
            'properties': {},
            'required': []
        }


def _validate_arguments(schema: Dict[str, Any], arguments: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    """
    Validate the arguments against the schema.
    Returns (is_valid, error_message)
    """
    if not isinstance(arguments, dict):
        return False, "Arguments must be a dictionary"
    
    properties = schema.get('properties', {})
    required = schema.get('required', [])
    
    # Check required fields
    for field in required:
        if field not in arguments:
            return False, f"Missing required parameter: {field}"
    
    # Validate basic types (simple validation)
    for field, value in arguments.items():
        if field not in properties:
            # Allow extra fields (could be stricter)
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
    input_schema: Optional[Dict[str, Any]] = None,
    expose_mcp: bool = True,
    groups: Optional[tuple] = None,
):
    """
    Decorator that registers a function as an MCP tool.
    
    Args:
        name: Tool name (default: the function name)
        description: Tool description (default: the function docstring)
        is_write: Whether the tool needs write permissions
        validate_schema: Whether the schema is validated automatically
        input_schema: Explicit JSON schema (optional; if left out, it is extracted from the function)
        expose_mcp: If False, the tool stays in the sack (internal hosts / AgentEngine)
            but is not published in /mcp tools/list. tools/call still
            runs it if a host asks for it.
        groups: group xmlids. If there are any, the model only sees the tool
            when the user has at least one (``tool_visible_to``). The
            tool still checks its permissions when it runs.
    
    Example:
        @mcp_tool(
            name='relaxaicode',
            description='Runs Python code in the relaxaicode environment',
            is_write=True
        )
        def tool_relaxaicode(controller, arguments: dict) -> dict:
            code: str = arguments.get('code', '')
            # ...
    """
    def decorator(func: Callable) -> Callable:
        # Work out the tool name
        tool_name = name or func.__name__
        
        # Get the description
        tool_description = description or (func.__doc__ or '').strip()
        if tool_description:
            # Clean the docstring (drop extra spaces)
            tool_description = ' '.join(tool_description.split())
        
        # Work out the schema: use the explicit one if any, else extract it
        final_schema = input_schema
        if final_schema is None:
            final_schema = _extract_schema_from_function(func)
        
        # Register the tool

        
        _logger.info(
            "MCP: Tool registrada: %s (write=%s, expose_mcp=%s)",
            tool_name, is_write, expose_mcp,
        )
        
        # Wrapper that validates the schema when enabled
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
            
            # Check whether the function has explicit parameters besides controller
            sig = inspect.signature(func)
            has_explicit_params = False
            explicit_params = {}
            for param_name, param in sig.parameters.items():
                if param_name not in ('self', 'controller', 'arguments'):
                    has_explicit_params = True
                    # Take the value from arguments if it is there
                    if param_name in arguments:
                        explicit_params[param_name] = arguments[param_name]
                    elif param.default != inspect.Parameter.empty:
                        # Use the default value if there is one
                        explicit_params[param_name] = param.default
                    # If it has no default and is not in arguments, validate_schema already checked it
            
            # Call the original function
            if has_explicit_params:
                # Pass explicit parameters as kwargs (without arguments)
                return func(controller, **explicit_params)
            else:
                # Standard form (controller, arguments)
                return func(controller, arguments)
        
        # Store metadata on the wrapper
        wrapper._mcp_tool_name = tool_name
        # wrapper._mcp_tool_metadata assignment removed as it depends on registry
        
        # Register the tool (USING THE WRAPPER)
        # This is CRUCIAL so logging and validation run
        _MCP_TOOLS_REGISTRY[tool_name] = {
            'name': tool_name,
            'description': tool_description,
            'inputSchema': final_schema,
            'is_write': is_write,
            'expose_mcp': bool(expose_mcp),
            'groups': tuple(groups or ()),
            'function': wrapper, # [FIX] Register wrapper, NOT func
            'validate_schema': validate_schema
        }
        
        return wrapper
    
    return decorator


def get_registered_tools() -> Dict[str, Dict[str, Any]]:
    """
    Get every registered tool.
    Returns a dict with each tool's metadata (without the function).
    """
    result = {}
    for tool_name, tool_data in _MCP_TOOLS_REGISTRY.items():
        result[tool_name] = {
            'name': tool_data['name'],
            'description': tool_data['description'],
            'inputSchema': tool_data['inputSchema'],
            'is_write': tool_data['is_write'],
            'expose_mcp': tool_data.get('expose_mcp', True),
            'groups': tool_data.get('groups', ()),
        }
    return result


def tool_visible_to(tool_data: Dict[str, Any], user) -> bool:
    """True when *user* may be offered the tool (no groups = everyone)."""
    groups = tool_data.get('groups') or ()
    return not groups or any(user.has_group(g) for g in groups)


def list_registered_tools_for_mcp() -> Dict[str, Dict[str, Any]]:
    """Subset published on MCP ``tools/list``. Internal hosts use the full sack."""
    return {
        name: data
        for name, data in get_registered_tools().items()
        if data.get('expose_mcp', True)
    }


def get_tool_function(tool_name: str) -> Optional[Callable]:
    """
    Get the function of a registered tool.
    """
    if tool_name in _MCP_TOOLS_REGISTRY:
        return _MCP_TOOLS_REGISTRY[tool_name]['function']
    return None


def get_tool_metadata(tool_name: str) -> Optional[Dict[str, Any]]:
    """
    Get the metadata of a registered tool (without the function).
    """
    if tool_name in _MCP_TOOLS_REGISTRY:
        tool_data = _MCP_TOOLS_REGISTRY[tool_name].copy()
        tool_data.pop('function', None)  # Do not include the function
        return tool_data
    return None

