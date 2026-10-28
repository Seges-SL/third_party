# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""AST validation of relaxaicode code: the walk that accepts or rejects a snippet."""

import ast
import re

from .validators_base import (
    AST_KIND_SYNTAX,
    DANGEROUS_ATTR_NAMES,
    DANGEROUS_FORMAT_NAMES,
    RELAXAICODE_DANGEROUS_MODULES,
    RELAXAICODE_FORBIDDEN_ORM_ATTRS,
    RELAXAICODE_NETWORK_IMPORT_MODULES,
    RELAXAICODE_PRIVILEGE_ATTRS,
    RELAXAICODE_SAFE_MODULES,
    # Seges: parche 23 (PNS-101, seguridad). Ver docs/pendiente/parches_pns_ai.md
    RELAXAICODE_ENV_STATE_ATTRS,
    RELAXAICODE_ENV_STATE_HINT,
    # Seges: parche 23 ampliado (PNS-101, seguridad). Ver docs/pendiente/parches_pns_ai.md
    sandbox_forbidden_name,
    RELAXAICODE_ENGINE_NAME_HINT,
    engine_name_binding,
    _ast_parent_map,
    _is_inside_function,
    _private_attr_error,
    blocked_private_attr,
    _network_import_error,
    _unsafe_import_error,
    format_ast_error,
)

from .validators_checks import (
    _ast_static_str,
    _check_env_parameter_binding,
    _check_function_def_limits,
    _check_search_domain_not_prior_result,
    _dangerous_attr_error,
    _dangerous_name_error,
    _detect_external_api_bypass_from_ast,
    _detect_requires_write_from_ast,
    _external_api_bypass_error,
    _is_safe_type_name_access,
    _privilege_attr_in_call,
    _privilege_error,
    _validate_result_assignment,
)

from .validators_sort import (
    _SAFE_LAMBDA_MSG,
    _collect_safe_sort_key_refs,
    _is_safe_lambda,
    _is_safe_sort_key_value,
)


def validate_relaxaicode_source_ast(code):
    """
    Valida código Python usando AST completo.
    Detecta imports peligrosos, funciones peligrosas, y código dinámico.
    
    Returns:
        tuple: (is_valid, error_message, requires_write)
            - is_valid: True si el código es válido
            - error_message: Mensaje de error si no es válido, None si es válido
            - requires_write: True si el código requiere permisos de escritura
    """
    # CRÍTICO: Validar que code sea string
    if not isinstance(code, str):
        return False, f"Invalid code type: expected string, got {type(code).__name__}. Code must be a Python string.", False
    
    if not code or not code.strip():
        return False, "Code is empty or contains only whitespace", False
    
    try:
        # Parsear código a AST
        tree = ast.parse(code, '<relaxaicode>', 'exec')
    except SyntaxError as e:
        # Proporcionar mensaje de error más descriptivo
        error_msg = str(e)
        error_line = getattr(e, 'lineno', None)
        
        # Si hay información de línea, incluirla en el mensaje
        if error_line:
            # Obtener la línea problemática para contexto
            lines = code.split('\n')
            if error_line <= len(lines):
                problem_line = lines[error_line - 1]
                # Truncar si es muy larga
                if len(problem_line) > 100:
                    problem_line = problem_line[:97] + '...'
                error_msg = f"Syntax error at line {error_line}: {error_msg}\nProblematic line: {problem_line}"
            else:
                error_msg = f"Syntax error at line {error_line}: {error_msg}"
        
        return False, format_ast_error(
            None, 'Syntax error: %s' % error_msg, kind=AST_KIND_SYNTAX,
        ), False
    except Exception as e:
        return False, format_ast_error(
            None, 'Failed to parse code: %s' % e, kind=AST_KIND_SYNTAX,
        ), False

    safe_sort_key_refs = _collect_safe_sort_key_refs(tree)
    parents = _ast_parent_map(tree)

    nest_ok, nest_err = _check_function_def_limits(tree)
    if not nest_ok:
        return False, nest_err, False

    env_ok, env_err = _check_env_parameter_binding(tree)
    if not env_ok:
        return False, env_err, False

    domain_ok, domain_err = _check_search_domain_not_prior_result(tree)
    if not domain_ok:
        return False, domain_err, False

    dangerous_modules = RELAXAICODE_DANGEROUS_MODULES
    safe_modules = RELAXAICODE_SAFE_MODULES

    # Funciones peligrosas completamente prohibidas
    dangerous_functions = {
        'open', 'eval', 'exec', 'compile', '__import__',
        'input', 'raw_input', 'file',
    }

    # Atributos peligrosos: denylist ÚNICA (DANGEROUS_ATTR_NAMES) compartida
    # con guarded_getattr de runtime.
    dangerous_attrs = DANGEROUS_ATTR_NAMES

    # Variables peligrosas completamente prohibidas
    dangerous_vars = {
        'locals', 'globals', 'vars', 'dir',
    }
    
    # Analizar AST completo
    for node in ast.walk(tree):
        # Seges: parche 23 ampliado (PNS-101, seguridad). Ver docs/pendiente/parches_pns_ai.md
        # Nombres internos del motor (_sandbox_str_attr): se leen, no se ligan.
        engine_name = engine_name_binding(node)
        if engine_name:
            return False, format_ast_error(
                'ENGINE_NAME', RELAXAICODE_ENGINE_NAME_HINT % (engine_name,)), False
        # ============================================================
        # VALIDAR IMPORTS DIRECTOS
        # ============================================================
        if isinstance(node, ast.Import):
            for alias in node.names:
                module_name = alias.name.split('.')[0]  # Solo el primer nivel
                
                # Bloquear módulos peligrosos
                if module_name in dangerous_modules:
                    if module_name == 'odoo':
                        return False, (
                            "[SyntaxError] DO NOT use 'import odoo'. Use global variables directly: "
                            "odoo_version (str), odoo_series (str), env (Odoo Environment). "
                            "Example: result = {'version': odoo_version}"
                        ), False
                    if module_name in RELAXAICODE_NETWORK_IMPORT_MODULES:
                        return False, _network_import_error(module_name), False
                    return False, (
                        f"[SyntaxError] Cannot import '{module_name}'. "
                        "Access models with env['model'] or use available global variables."
                    ), False

                if module_name not in safe_modules:
                    return False, _unsafe_import_error(module_name), False

        # ============================================================
        # VALIDAR IMPORTS FROM
        # ============================================================
        if isinstance(node, ast.ImportFrom):
            if node.module:
                # urllib.parse: funciones puras de texto (quote, urlencode, urlparse,
                # parse_qs, urljoin...) para COMPONER/TROCEAR URLs. No tiene red ni FS.
                # Se permite SOLO la forma `from urllib.parse import <nombre>`, que liga
                # las funciones y nunca el paquete `urllib` (por el que se alcanzaría
                # urllib.request). `import urllib.parse` sigue prohibido (ver ast.Import).
                if node.module == 'urllib.parse':
                    continue

                module_name = node.module.split('.')[0]  # Solo el primer nivel

                # Bloquear módulos peligrosos
                if module_name in dangerous_modules:
                    if module_name in RELAXAICODE_NETWORK_IMPORT_MODULES:
                        return False, _network_import_error(module_name), False
                    return False, (
                        f"[PROHIBITED] Relaxaicode cannot import from '{module_name}' or any of its submodules. "
                        "Use available global variables (env, odoo_version) or access models via env['model']."
                    ), False

                if module_name not in safe_modules:
                    return False, _unsafe_import_error(module_name), False

        # ============================================================
        # VALIDAR LLAMADAS A FUNCIONES PELIGROSAS
        # ============================================================
        if isinstance(node, ast.Call):
            # Llamadas directas: open(), eval(), exec(), print(), etc.
            if isinstance(node.func, ast.Name):
                if node.func.id in dangerous_functions:
                    if node.func.id in ('eval', 'exec', 'compile'):
                        return False, (
                            f"[PROHIBITED] Cannot use '{node.func.id}()'. "
                            "Never probe helpers with eval/exec. "
                            "[MANDATORY] Preloaded helpers (if a module published them) "
                            "are called directly. To test if a name exists: "
                            "try: _ = name\\nexcept NameError: … — never eval('name')."
                        ), False
                    return False, (
                        f"[PROHIBITED] Cannot use '{node.func.id}()'. "
                        "This function is prohibited for security."
                    ), False
            
            # Llamadas a métodos: obj.open(), obj.eval(), etc.
            if isinstance(node.func, ast.Attribute):
                if node.func.attr in dangerous_functions:
                    return False, (
                        f"[PROHIBITED] Relaxaicode cannot use method '.{node.func.attr}()'. "
                        "This method is prohibited for security reasons."
                    ), False
                # Métodos de cursor/transacción: SQL crudo y control de transacción quedan
                # fuera de la caja A. Las escrituras se hacen SOLO vía la caja B (verbos ORM).
                dangerous_cursor_methods = {
                    'execute', 'executemany', 'commit', 'rollback', 'savepoint',
                    'dictfetchall', 'dictfetchone',
                }
                if node.func.attr in dangerous_cursor_methods:
                    return False, (
                        f"[PROHIBITED] Relaxaicode cannot use '.{node.func.attr}()' (raw SQL / "
                        "transaction control). Use the ORM (env['model']) for reads; writes go "
                        "through confirmed write operations, never raw SQL."
                    ), False
            
            # Bloquear __import__() dinámico
            if isinstance(node.func, ast.Name) and node.func.id == '__import__':
                return False, (
                    "[PROHIBITED] Relaxaicode cannot use '__import__()' dynamically. "
                    "Imports must be static/direct (import module or from module import)."
                ), False

            # Bloquear type(name, bases, dict): crea CLASES dinámicamente, saltándose
            # la prohibición de 'class'. Se preserva type(x) de 1 argumento (chequeo
            # de tipo, uso legítimo). 3 args = metaclase → fuera de la caja A.
            if isinstance(node.func, ast.Name) and node.func.id == 'type' and len(node.args) == 3:
                return False, (
                    "[PROHIBITED] Relaxaicode cannot use 'type(name, bases, dict)' to create "
                    "classes dynamically. Only type(x) for type checks is allowed."
                ), False
        
        # ============================================================
        # VALIDAR RETURN: solo dentro de def (el script sigue usando result=)
        # ============================================================
        if isinstance(node, ast.Return):
            if not _is_inside_function(node, parents):
                return False, (
                    "[PROHIBITED] DO NOT use 'return' at module level. "
                    "Code executes as a script (NOT a function). "
                    "[MANDATORY] Assign output to variable 'result'. "
                    "Example: result = {'odoo_version': odoo_version}. "
                    "'return' is only allowed inside a def helper."
                ), False

        # ============================================================
        # VALIDAR PATRONES INCORRECTOS COMUNES (self.env, context.get, etc.)
        # ============================================================
        # Detectar self.env (patrón de métodos de Odoo, NO existe en relaxaicode)
        if isinstance(node, ast.Attribute):
            if isinstance(node.value, ast.Name) and node.value.id == 'self' and node.attr == 'env':
                return False, (
                    "[PROHIBITED] DO NOT use 'self.env'. Code executes directly (NOT a method, no 'self'). "
                    "[MANDATORY] Use 'env' directly as a global variable. "
                    "Correct: partners = env['res.partner'].search([]). "
                    "Wrong: partners = self.env['res.partner'].search([])"
                ), False
        
        # Detectar context.get('env') o context['env'] (patrón de wizards, NO existe en relaxaicode)
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Attribute):
                if isinstance(node.func.value, ast.Name) and node.func.value.id == 'context':
                    if node.func.attr == 'get':
                        if node.args and _ast_static_str(node.args[0]) == 'env':
                            return False, (
                                "[PROHIBITED] DO NOT use 'context.get('env')'. Variable 'context' does NOT exist. "
                                "[MANDATORY] Use 'env' directly as a global variable. "
                                "Correct: partners = env['res.partner'].search([]). "
                                "Wrong: env = context.get('env'); partners = env['res.partner'].search([])"
                            ), False
                    elif node.func.attr == '__getitem__':
                        return False, (
                            "[PROHIBITED] DO NOT use 'context.get()' or 'context[]'. Variable 'context' does NOT exist. "
                            "[MANDATORY] Variables are available directly: env, odoo_version, odoo_series. "
                            "Example: result = {'odoo_version': odoo_version}"
                        ), False
        
        # Detectar acceso a context['env'] o context.get('env')
        if isinstance(node, ast.Subscript):
            if isinstance(node.value, ast.Name) and node.value.id == 'context':
                return False, (
                    "[PROHIBITED] DO NOT use 'context['env']' or 'context['variable']'. Variable 'context' does NOT exist. "
                    "[MANDATORY] Variables are available directly: env, odoo_version, odoo_series. "
                    "Example: result = {'odoo_version': odoo_version}"
                ), False
        
        # ============================================================
        # VALIDAR ACCESO A ATRIBUTOS PELIGROSOS
        # ============================================================
        if isinstance(node, ast.Attribute):
            if node.attr in RELAXAICODE_FORBIDDEN_ORM_ATTRS:
                return False, _external_api_bypass_error(node.attr), False
            if node.attr in RELAXAICODE_PRIVILEGE_ATTRS:
                return False, _privilege_error(node.attr), False
            # Seges: parche 23 (PNS-101, seguridad). Ver docs/pendiente/parches_pns_ai.md
            if node.attr in RELAXAICODE_ENV_STATE_ATTRS:
                return False, format_ast_error(
                    'ENV_STATE', RELAXAICODE_ENV_STATE_HINT % (node.attr,)), False
            if blocked_private_attr(node.attr):
                return False, _private_attr_error(node.attr), False
            if node.attr in dangerous_attrs:
                # type(x).__name__ → string label; no abre introspección de sandbox.
                if not _is_safe_type_name_access(node):
                    return False, _dangerous_attr_error(node.attr), False
            # string.Formatter().get_field(...) / .vformat(...) devuelven el OBJETO
            # real (no su repr) → traversal de clases sin '.' ni getattr. Se bloquea
            # por nombre, cubriendo tanto `string.Formatter` como `import string`.
            if node.attr in DANGEROUS_FORMAT_NAMES:
                return False, format_ast_error(
                    'FORMATTER',
                    "Relaxaicode cannot use '%s' (string.Formatter). "
                    "It returns internal objects and allows sandbox escape."
                    % node.attr,
                ), False
        
        # ============================================================
        # VALIDAR USO DE VARIABLES PELIGROSAS
        # ============================================================
        if isinstance(node, ast.Name):
            if node.id in dangerous_vars:
                # Verificar si se está usando como llamada a función
                # Buscar en el árbol si este Name está dentro de un Call
                # Como ast.walk no mantiene relaciones padre-hijo, verificamos
                # si hay un Call cercano que use esta variable
                # La mejor forma es verificar el contexto: si es Load y está en un Call
                if isinstance(node.ctx, ast.Load):
                    # Sin mapa padre aquí: cualquier Load de estas builtins se bloquea.
                    return False, _dangerous_name_error(node.id), False
        
        # ============================================================
        # VALIDAR ACCESO A __BUILTINS__ DIRECTAMENTE
        # ============================================================
        if isinstance(node, ast.Attribute):
            if isinstance(node.value, ast.Name) and node.value.id == '__builtins__':
                return False, format_ast_error(
                    'BUILTINS',
                    "Relaxaicode cannot access '__builtins__' directly. "
                    "This is blocked for security.",
                ), False
        
        # ============================================================
        # VALIDAR getattr()/setattr()/delattr() CON ATRIBUTOS PELIGROSOS
        # OJO: esto cubre nombres fijos ('__class__', '__cla' + 'ss__'). El nombre
        # que solo se conoce al correr lo bloquea el guarded_getattr de runtime
        # en context_builder, que evalúa el nombre real contra la MISMA denylist.
        # ============================================================
        if isinstance(node, ast.Call):
            privileged = _privilege_attr_in_call(node)
            if privileged:
                return False, _privilege_error(privileged), False
            _getter = node.func.id if isinstance(node.func, ast.Name) else (
                node.func.attr if isinstance(node.func, ast.Attribute) else None)
            if _getter in ('attrgetter', 'methodcaller') and node.args:
                _path = _ast_static_str(node.args[0])
                for _part in (_path or '').split('.'):
                    if blocked_private_attr(_part):
                        return False, _private_attr_error(_part), False
            if isinstance(node.func, ast.Name) and node.func.id in ('getattr', 'setattr', 'delattr'):
                if len(node.args) >= 2:
                    attr_name = _ast_static_str(node.args[1])
                    if attr_name is not None:
                        if blocked_private_attr(attr_name):
                            return False, _private_attr_error(attr_name), False
                        if attr_name in RELAXAICODE_FORBIDDEN_ORM_ATTRS:
                            return False, _external_api_bypass_error(attr_name), False
                        if attr_name in dangerous_attrs:
                            return False, format_ast_error(
                                'DUNDER',
                                "Relaxaicode cannot use %s() to access '%s'. "
                                "This attribute is blocked for security."
                                % (node.func.id, attr_name),
                            ), False

        # ============================================================
        # VALIDAR FORMAT-STRINGS CON ACCESO A DUNDER: "{0.__class__}".format(x)
        # str.format resuelve la cadena de atributos sobre el objeto REAL antes de
        # formatear. Aunque devuelva su repr (no el objeto), es fuga de introspección
        # y puede encadenarse. Se bloquea SOLO si el literal accede a un dunder
        # ({...__x__...}); se preserva el uso normal ({0}, {name}, {0.name}).
        # ============================================================
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if node.func.attr in ('format', 'format_map'):
                fmt_str = _ast_static_str(node.func.value)
                _fmt_parts = [
                    part
                    for field in re.findall(r'\{([^{}]*)\}', fmt_str or '')
                    for part in re.split(r'[.\[!:]', field)
                ]
                _fmt_private = next(
                    (p for p in _fmt_parts if blocked_private_attr(p)), None)
                if _fmt_private:
                    return False, _private_attr_error(_fmt_private), False
                # Seges: parche 23 ampliado (PNS-101, seguridad). Ver docs/pendiente/parches_pns_ai.md
                # Defensa adicional en plantilla LITERAL: filtro completo de campos.
                # El cierre real de la familia es el formateador propio en runtime
                # (relaxaicode_format_guard), que cubre también plantillas en variable.
                _fmt_forbidden = next(
                    (p for p in _fmt_parts if sandbox_forbidden_name(p)), None)
                if _fmt_forbidden:
                    return False, format_ast_error(
                        'FORMAT',
                        f"Relaxaicode cannot use .format() with {_fmt_forbidden!r} "
                        "in the template (blocked name).",
                    ), False
                if fmt_str and re.search(r'\{[^{}]*__[A-Za-z0-9_]*__', fmt_str):
                    return False, format_ast_error(
                        'FORMAT',
                        "Relaxaicode cannot use .format() with dunder attribute "
                        "access ('__...__') in the template. Blocked for security.",
                    ), False
        
        # ============================================================
        # VALIDAR CONSTRUCCIONES: lambda segura; class prohibida.
        # def/async def: permitidos (límites arriba); el cuerpo se valida
        # en este mismo walk (open/eval/cr/imports…).
        # ============================================================
        if isinstance(node, ast.Lambda):
            if not _is_safe_lambda(node, extra_call_names=safe_sort_key_refs):
                return False, _SAFE_LAMBDA_MSG, False

        if isinstance(node, ast.ClassDef):
            return False, (
                "[PROHIBITED] Relaxaicode does NOT allow defining classes. "
                "Use plain dicts/lists and optional def helpers instead."
            ), False

        # ============================================================
        # VALIDAR SORT/SORTED/MIN/MAX CON KEY ARGUMENT
        # ============================================================
        if isinstance(node, ast.Call):
            is_sort_call = False
            if isinstance(node.func, ast.Name) and node.func.id in ('sorted', 'min', 'max'):
                is_sort_call = True
            elif isinstance(node.func, ast.Attribute) and node.func.attr in ('sort', 'sorted'):
                is_sort_call = True
            
            if is_sort_call:
                for keyword in node.keywords:
                    if keyword.arg == 'key':
                        kv = keyword.value
                        if isinstance(kv, ast.Lambda) and not _is_safe_lambda(
                            kv, extra_call_names=safe_sort_key_refs,
                        ):
                            return False, _SAFE_LAMBDA_MSG, False
                        if not _is_safe_sort_key_value(kv, safe_sort_key_refs):
                            return False, _SAFE_LAMBDA_MSG, False
    # ============================================================
    # VALIDAR ASIGNACIÓN REAL A 'result'
    # ============================================================
    assign_ok, assign_err = _validate_result_assignment(tree)
    if not assign_ok:
        return False, assign_err, False
    
    # ============================================================
    # BLOQUEAR BYPASS DE API EXTERNA VÍA ORM (Caja A → red sin Safe Plan)
    # ============================================================
    bypass_err = _detect_external_api_bypass_from_ast(tree)
    if bypass_err:
        return False, bypass_err, False

    # ============================================================
    # DETECTAR OPERACIONES DE ESCRITURA (AST, sin falsos positivos)
    # ============================================================
    requires_write = _detect_requires_write_from_ast(tree)
    
    # ============================================================
    # VALIDAR QUE NO SE REDEFINAN MÓDULOS PERMITIDOS
    # ============================================================
    shadowed = _shadowed_module(tree)
    if shadowed:
        return False, (
            "[PROHIBITED] Do not assign to %r: it is an allowed module "
            "(%s). Use another variable name (for example json_data)."
            % (shadowed, ', '.join(_SHADOW_GUARDED_MODULES))
        ), False

    return True, None, requires_write


_SHADOW_GUARDED_MODULES = ('json', 'datetime', 'math', 'statistics', 're', 'string')


def _shadowed_module(tree):
    """First guarded module name assigned to (``json = …``, ``re, x = …``), or None."""
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            targets = node.targets
        elif isinstance(node, (ast.AnnAssign, ast.AugAssign)):
            targets = [node.target]
        else:
            continue
        for target in targets:
            for name in ast.walk(target):
                if (isinstance(name, ast.Name) and isinstance(name.ctx, ast.Store)
                        and name.id in _SHADOW_GUARDED_MODULES):
                    return name.id
    return None
