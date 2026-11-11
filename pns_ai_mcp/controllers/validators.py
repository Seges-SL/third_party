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

_MATCH_CLASS = getattr(ast, 'MatchClass', None)

def validate_relaxaicode_source_ast(code):
    """
    Validates Python code using the full AST.
    Detects dangerous imports, dangerous functions and dynamic code.
    
    Returns:
        tuple: (is_valid, error_message, requires_write)
            - is_valid: True if the code is valid
            - error_message: Error message if not valid, None if valid
            - requires_write: True if the code needs write permissions
    """
    # CRITICAL: Check that code is a string
    if not isinstance(code, str):
        return False, f"Invalid code type: expected string, got {type(code).__name__}. Code must be a Python string.", False
    
    if not code or not code.strip():
        return False, "Code is empty or contains only whitespace", False
    
    try:
        # Parse the code to an AST
        tree = ast.parse(code, '<relaxaicode>', 'exec')
    except SyntaxError as e:
        # Give a more descriptive error message
        error_msg = str(e)
        error_line = getattr(e, 'lineno', None)
        
        # If there is line info, include it in the message
        if error_line:
            # Get the offending line for context
            lines = code.split('\n')
            if error_line <= len(lines):
                problem_line = lines[error_line - 1]
                # Truncate if very long
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

    # Dangerous functions, fully forbidden
    dangerous_functions = {
        'open', 'eval', 'exec', 'compile', '__import__',
        'input', 'raw_input', 'file',
    }

    # Dangerous attributes: SINGLE denylist (DANGEROUS_ATTR_NAMES) shared
    # with the runtime guarded_getattr.
    dangerous_attrs = DANGEROUS_ATTR_NAMES

    # Dangerous variables, fully forbidden
    dangerous_vars = {
        'locals', 'globals', 'vars', 'dir',
    }
    
    # Analyze the full AST
    for node in ast.walk(tree):
        # ============================================================
        # VALIDATE DIRECT IMPORTS
        # ============================================================
        if isinstance(node, ast.Import):
            for alias in node.names:
                module_name = alias.name.split('.')[0]  # Top level only
                
                # Block dangerous modules
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
        # VALIDATE IMPORT FROM
        # ============================================================
        if isinstance(node, ast.ImportFrom):
            if node.module:
                # urllib.parse: pure text functions (quote, urlencode, urlparse,
                # parse_qs, urljoin...) to BUILD/SPLIT URLs. No network or FS.
                # ONLY the form `from urllib.parse import <name>` is allowed, which binds
                # the functions and never the `urllib` package (through which you could reach
                # urllib.request). `import urllib.parse` is still forbidden (see ast.Import).
                if node.module == 'urllib.parse':
                    continue

                module_name = node.module.split('.')[0]  # Top level only

                # Block dangerous modules
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
        # VALIDATE CALLS TO DANGEROUS FUNCTIONS
        # ============================================================
        if isinstance(node, ast.Call):
            # Direct calls: open(), eval(), exec(), print(), etc.
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
            
            # Method calls: obj.open(), obj.eval(), etc.
            if isinstance(node.func, ast.Attribute):
                if node.func.attr in dangerous_functions:
                    return False, (
                        f"[PROHIBITED] Relaxaicode cannot use method '.{node.func.attr}()'. "
                        "This method is prohibited for security reasons."
                    ), False
                # Cursor/transaction methods: raw SQL and transaction control stay
                # outside box A. Writes happen ONLY through box B (ORM verbs).
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
            
            # Block dynamic __import__()
            if isinstance(node.func, ast.Name) and node.func.id == '__import__':
                return False, (
                    "[PROHIBITED] Relaxaicode cannot use '__import__()' dynamically. "
                    "Imports must be static/direct (import module or from module import)."
                ), False

            # Block type(name, bases, dict): it creates CLASSES dynamically, bypassing
            # the 'class' ban. The 1-argument type(x) is kept (type check,
            # legitimate use). 3 args = metaclass → outside box A.
            if isinstance(node.func, ast.Name) and node.func.id == 'type' and len(node.args) == 3:
                return False, (
                    "[PROHIBITED] Relaxaicode cannot use 'type(name, bases, dict)' to create "
                    "classes dynamically. Only type(x) for type checks is allowed."
                ), False
        
        # ============================================================
        # VALIDATE RETURN: only inside def (the script still uses result=)
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
        # VALIDATE COMMON WRONG PATTERNS (self.env, context.get, etc.)
        # ============================================================
        # Detect self.env (Odoo method pattern, does NOT exist in relaxaicode)
        if isinstance(node, ast.Attribute):
            if isinstance(node.value, ast.Name) and node.value.id == 'self' and node.attr == 'env':
                return False, (
                    "[PROHIBITED] DO NOT use 'self.env'. Code executes directly (NOT a method, no 'self'). "
                    "[MANDATORY] Use 'env' directly as a global variable. "
                    "Correct: partners = env['res.partner'].search([]). "
                    "Wrong: partners = self.env['res.partner'].search([])"
                ), False
        
        # Detect context.get('env') or context['env'] (wizard pattern, does NOT exist in relaxaicode)
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
        
        # Detect access to context['env'] or context.get('env')
        if isinstance(node, ast.Subscript):
            if isinstance(node.value, ast.Name) and node.value.id == 'context':
                return False, (
                    "[PROHIBITED] DO NOT use 'context['env']' or 'context['variable']'. Variable 'context' does NOT exist. "
                    "[MANDATORY] Variables are available directly: env, odoo_version, odoo_series. "
                    "Example: result = {'odoo_version': odoo_version}"
                ), False
        
        # ============================================================
        # VALIDATE ACCESS TO DANGEROUS ATTRIBUTES
        # ============================================================
        if isinstance(node, ast.Attribute):
            if node.attr in RELAXAICODE_FORBIDDEN_ORM_ATTRS:
                return False, _external_api_bypass_error(node.attr), False
            if node.attr in RELAXAICODE_PRIVILEGE_ATTRS:
                return False, _privilege_error(node.attr), False
            if blocked_private_attr(node.attr):
                return False, _private_attr_error(node.attr), False
            if node.attr in dangerous_attrs:
                # type(x).__name__ → string label; does not open sandbox introspection.
                if not _is_safe_type_name_access(node):
                    return False, _dangerous_attr_error(node.attr), False
            # string.Formatter().get_field(...) / .vformat(...) return the real
            # OBJECT (not its repr) → class traversal without '.' or getattr. Blocked
            # by name, covering both `string.Formatter` and `import string`.
            if node.attr in DANGEROUS_FORMAT_NAMES:
                return False, format_ast_error(
                    'FORMATTER',
                    "Relaxaicode cannot use '%s' (string.Formatter). "
                    "It returns internal objects and allows sandbox escape."
                    % node.attr,
                ), False
        
        # `case T(attr=x)` reads the attribute in C, past the sandbox's
        # attribute reads. Python 3.10+ only (no node on older series).
        if _MATCH_CLASS is not None and isinstance(node, _MATCH_CLASS):
            return False, (
                "[PROHIBITED] Relaxaicode cannot use class patterns in "
                "'match' (case T(...)). Use isinstance(x, T) and read the "
                "attributes with x.attr."
            ), False

        # ============================================================
        # VALIDATE USE OF DANGEROUS VARIABLES
        # ============================================================
        if isinstance(node, ast.Name):
            if node.id in dangerous_vars:
                # Check whether it is used as a function call
                # Look in the tree whether this Name is inside a Call
                # Since ast.walk does not keep parent-child links, we check
                # whether there is a nearby Call that uses this variable
                # The best way is to check the context: if it is Load and inside a Call
                if isinstance(node.ctx, ast.Load):
                    # No parent map here: any Load of these builtins is blocked.
                    return False, _dangerous_name_error(node.id), False
        
        # ============================================================
        # VALIDATE DIRECT ACCESS TO __BUILTINS__
        # ============================================================
        if isinstance(node, ast.Attribute):
            if isinstance(node.value, ast.Name) and node.value.id == '__builtins__':
                return False, format_ast_error(
                    'BUILTINS',
                    "Relaxaicode cannot access '__builtins__' directly. "
                    "This is blocked for security.",
                ), False
        
        # ============================================================
        # VALIDATE getattr()/setattr()/delattr() WITH DANGEROUS ATTRIBUTES
        # NOTE: this covers fixed names ('__class__', '__cla' + 'ss__'). A name
        # that is only known at run time is blocked by the runtime guarded_getattr
        # in context_builder, which checks the real name against the SAME denylist.
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
        # VALIDATE FORMAT-STRINGS WITH DUNDER ACCESS: "{0.__class__}".format(x)
        # str.format resolves the attribute chain on the REAL object before
        # formatting. Even if it returns its repr (not the object), it leaks introspection
        # and can be chained. Blocked ONLY if the literal accesses a dunder
        # ({...__x__...}); normal use is kept ({0}, {name}, {0.name}).
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
                if fmt_str and re.search(r'\{[^{}]*__[A-Za-z0-9_]*__', fmt_str):
                    return False, format_ast_error(
                        'FORMAT',
                        "Relaxaicode cannot use .format() with dunder attribute "
                        "access ('__...__') in the template. Blocked for security.",
                    ), False
        
        # ============================================================
        # VALIDATE CONSTRUCTS: safe lambda; class forbidden.
        # def/async def: allowed (limits above); the body is validated
        # in this same walk (open/eval/cr/imports…).
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
        # VALIDATE SORT/SORTED/MIN/MAX WITH KEY ARGUMENT
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
    # VALIDATE REAL ASSIGNMENT TO 'result'
    # ============================================================
    assign_ok, assign_err = _validate_result_assignment(tree)
    if not assign_ok:
        return False, assign_err, False
    
    # ============================================================
    # BLOCK EXTERNAL API BYPASS THROUGH THE ORM (Box A → network without Safe Plan)
    # ============================================================
    bypass_err = _detect_external_api_bypass_from_ast(tree)
    if bypass_err:
        return False, bypass_err, False

    # ============================================================
    # DETECT WRITE OPERATIONS (AST, no false positives)
    # ============================================================
    requires_write = _detect_requires_write_from_ast(tree)
    
    # ============================================================
    # VALIDATE THAT ALLOWED MODULES ARE NOT REDEFINED
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
