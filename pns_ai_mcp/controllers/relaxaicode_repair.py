# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""Second-pass repair of relaxaicode source that does not parse."""

import logging
import re
from .relaxaicode_replies import _log_where

_logger = logging.getLogger(__name__)


def _attempt_syntax_repair(code):
    """
    Intenta reparar errores comunes de sintaxis en el código generado por el LLM.
    Esto es un fallback cuando el LLM genera código con errores menores.
    
    Args:
        code: Código Python con posibles errores de sintaxis
    
    Returns:
        tuple: (repaired_code, was_repaired)
            - repaired_code: Código reparado (o original si no se pudo reparar)
            - was_repaired: True si se realizaron reparaciones
    """
    original_code = code
    was_repaired = False
    
    # Intentar reparar cadenas sin cerrar al final de líneas (error común)
    # Patrón: "texto sin cerrar al final de línea
    lines = code.split('\n')
    repaired_lines = []
    
    # 1. Reparación INTELIGENTE para formatted_text multilínea (antes del procesado línea por línea)
    # Detectar: "formatted_text": "Línea 1
    # Línea 2"
    # Solución: Convertir a "formatted_text": "Línea 1\nLínea 2"
    try:
        # Función auxiliar para escapar newlines dentro del match
        def escape_newlines(match):
            prefix = match.group(1)
            content = match.group(2)
            suffix = match.group(3)
            # Solo si detectamos saltos de línea reales
            if '\n' in content:
                escaped_content = content.replace(chr(10), '\\n')
                return f"{prefix}{escaped_content}{suffix}"
            return match.group(0)

        # Patrón Mejorado: Busca el cierre ANCLADO a la estructura del diccionario
        # Busca: "formatted_text": " ... " seguido de , o }
        # Esto evita detenerse en comillas internas falsas
        # Grupo 1: Key y apertura ("formatted_text": ")
        # Grupo 2: Contenido (Greedy/Non-greedy? Usamos non-greedy pero hasta el anchor)
        # Grupo 3: Cierre y separador (" , o " })
        
        # Estrategia: Buscar hasta la última comilla posible que precede a una coma, llave de cierre O UN PUNTO (para chain methods)
        pattern_anchored = r"(['\"]formatted_text['\"]\s*[:=]\s*['\"])([\s\S]*?)((?<!\\)['\"]\s*(?:,|}|\]|\.))"
        
        def escape_newlines_anchored(match):
            prefix = match.group(1)
            content = match.group(2)
            suffix = match.group(3)
            if '\n' in content:
                # Escape newlines to make it a valid single-line string
                escaped = content.replace('\n', '\\n').replace('\r', '')
                return f"{prefix}{escaped}{suffix}"
            return match.group(0)
 
        code = re.sub(pattern_anchored, escape_newlines_anchored, code)

        # 1b. Misma reparación para footer / pie / footer_md.
        pattern_footer = (
            r"(['\"](?:footer|footer_md|pie)['\"]\s*[:=]\s*['\"])"
            r"([\s\S]*?)"
            r"((?<!\\)['\"]\s*(?:,|}|\]|\.))"
        )
        code2 = re.sub(pattern_footer, escape_newlines_anchored, code)
        if code2 != code:
            code = code2
            was_repaired = True

        # 1b2. 'footer': '<NL>'.join( → 'footer': '\n'.join(
        code2b = re.sub(
            r"(['\"])(footer|footer_md|pie)\1\s*:\s*(['\"])\s*\n\s*\3\.join\s*\(",
            r"\1\2\1: \3\\n\3.join(",
            code,
        )
        if code2b != code:
            code = code2b
            was_repaired = True

        # 1c. footer_lines = [ ... ] con newlines rotos dentro de strings.
        try:
            def repair_footer_list(match):
                prefix, content, suffix = match.group(1), match.group(2), match.group(3)
                if '\n' not in content:
                    return match.group(0)
                escaped = content.replace('\n', '\\n').replace('\r', '')
                escaped = re.sub(r'(,\s*)\\n(\s*["\'\[\]#])', r'\1\n\2', escaped)
                escaped = re.sub(r'(\[\s*)\\n(\s*["\'\[\]#])', r'\1\n\2', escaped)
                escaped = re.sub(r'\\n(\s*\])', r'\n\1', escaped)
                return '%s%s%s' % (prefix, escaped, suffix)

            code3 = re.sub(
                r'(footer_lines\s*=\s*\[)([\s\S]*?)(\])',
                repair_footer_list,
                code,
            )
            if code3 != code:
                code = code3
                was_repaired = True
        except Exception as e:
            _logger.warning(
                '[%s] Error en reparación de footer_lines: %s', _log_where(), e,
            )

        # 1d. 'footer': "… sin cerrar en la misma línea → '' (el render meteo
        # sintetiza Comparativa + pie). Descarta líneas huérfanas del literal.
        try:
            flines = code.split('\n')
            out = []
            skipping = False
            changed = False
            footer_open = re.compile(
                r"""^(\s*)(['\"])footer\2\s*:\s*(['\"])(.*)$"""
            )
            for ln in flines:
                if skipping:
                    st = ln.strip()
                    if st.endswith("',") or st.endswith('",') or st in ("'", '"'):
                        skipping = False
                    elif st.endswith('},') or st == '}':
                        skipping = False
                        out.append(ln)
                    continue
                m = footer_open.match(ln)
                if m:
                    indent, _k, quote, rest = m.groups()
                    # Cerrado en la misma línea: quote … quote
                    closed = re.match(
                        r'^(?:\\.|[^\\])*?' + re.escape(quote) + r'\s*,?\s*$',
                        rest,
                    )
                    if not closed:
                        out.append("%s'footer': ''," % indent)
                        skipping = True
                        changed = True
                        continue
                out.append(ln)
            if changed:
                code = '\n'.join(out)
                was_repaired = True
        except Exception as e:
            _logger.warning(
                '[%s] Error en reparación de footer EOL: %s', _log_where(), e,
            )

        # 2. Reparación ESPECÍFICA para formatted_lines (Listas de strings rotas por newlines)
        # Detectar: formatted_lines = [ ... ] y escapar newlines internos
        try:
            def repair_list_newlines(match):
                prefix = match.group(1)
                content = match.group(2)
                suffix = match.group(3)
                
                # 1. Escapar TODOS los newlines en el contenido
                escaped = content.replace('\n', '\\n').replace('\r', '')
                
                # 2. Restaurar newlines ESTRUCTURALES (los que son parte de la sintaxis de lista)
                # Patrón: Restaurar ",\n" -> , \n
                escaped = re.sub(r'(,\s*)\\n(\s*["\'\[\]#])', r'\1\n\2', escaped)
                # Restaurar "[\n" -> [ \n
                escaped = re.sub(r'(\[\s*)\\n(\s*["\'\[\]#])', r'\1\n\2', escaped)
                # Restaurar "\n]" -> \n ] (final de lista)
                escaped = re.sub(r'\\n(\s*\])', r'\n\1', escaped)

                return f"{prefix}{escaped}{suffix}"

            # Regex para capturar el bloque formatted_lines completo
            # (formatted_lines = [) ... (])
            pattern_list = r'(formatted_lines\s*=\s*\[)([\s\S]*?)(\])'
            code = re.sub(pattern_list, repair_list_newlines, code)
            
            if code != original_code:
                was_repaired = True
        except Exception as e:
            _logger.warning(f"[{_log_where()}] Error en reparación de formatted_lines: {e}")

        # 3. Reparación ESPECÍFICA para line continuations rotos
        # Error: unexpected character after line continuation character
        # Causa: El modelo pone backslash (\) al final de la línea seguido de espacio o nada.
        # Solución: Eliminar backslashes que están al final de la línea si causan error
        try:
            if '\\' in code:
                # Buscar backslash seguido de espacio o nada antes del newline
                # O simplemente eliminar backslashes al final de la linea si no son necesarios
                # Python moderno permite paréntesis para multilínea, los backslashes son riesgosos.
                
                # Cuidado: no romper strings que terminan en backslash (raro)
                
                def remove_broken_line_continuation(match):
                    # match.group(1) es el contenido de la linea antes del backslash
                    return match.group(1) + " " 
                
                # Patrón: Cualquier cosa que no sea backslash, seguido de backslash, espacios opcionales, newline
                # pattern = r'(.*)\\[ \t]*\n'
                # code = re.sub(pattern, remove_broken_line_continuation, code)
                
                # MÉTODO MÁS SEGURO: Si detectamos que falla por esto, limpiamos TODOS los backslashes de fin de linea
                # fuera de strings. (Dificil con regex simple).
                
                # Heurística simple: Reemplazar " \n" o "\n" por " " si parece un statement roto?
                # Mejor: Reemplazar " \ " seguido de newline por nada.
                
                if re.search(r'\\[ \t]*\n', code):
                    # Reemplazar backslash+whitespace+newline por un solo espacio (unir líneas)
                    code = re.sub(r'\\[ \t]*\n', ' ', code)
                    if code != original_code:
                        was_repaired = True

                # Caso especial: Backslash al FINAL DEL ARCHIVO (EOF)
                if code.strip().endswith('\\'):
                    code = code.strip()[:-1]
                    was_repaired = True

        except Exception as e:
            _logger.warning(f"[{_log_where()}] Error en reparación de line continuations: {e}")

    except Exception as e:
        _logger.warning(f"[{_log_where()}] Error intentando reparación regex: {e}")

            
    # 4. Reparación para IMPLICIT RESULT (Falta de asignación result = ...)
    try:
        from ..utils.relaxaicode_recipe import (
            ensure_date_param_coercion,
            ensure_module_result_call,
            strip_self_recursive_shadow_defs,
        )
        code2, shadow_stripped = strip_self_recursive_shadow_defs(code)
        if shadow_stripped:
            code = code2
            was_repaired = True
        code2, ensured = ensure_module_result_call(code)
        if ensured:
            code = code2
            was_repaired = True
        code2, coerced = ensure_date_param_coercion(code)
        if coerced:
            code = code2
            was_repaired = True
    except Exception as e:
        _logger.warning(
            '[%s] Error en ensure_module_result_call: %s', _log_where(), e,
        )

    # 4b. Reuse distance() origin on map_pins_* when origin= was omitted
    try:
        from ..utils.relaxaicode_recipe import (
            inject_map_pins_origin_from_distance,
        )
        code2, injected = inject_map_pins_origin_from_distance(code)
        if injected:
            code = code2
            was_repaired = True
    except Exception as e:
        _logger.warning(
            '[%s] Error en inject_map_pins_origin_from_distance: %s',
            _log_where(), e,
        )

    try:
        # Check basic heuristics: 'result =' missing
        if 'result' not in code or ('=' not in code and '.search' in code):
            # [NUEVO] Detección de uso de previous_result sin asignación a result
            # Si el código usa previous_result pero no asigna result, asumimos que quiere devolver previous_result
            if 'previous_result' in code and 'result =' not in code and 'result=' not in code:
                 code += "\nresult = previous_result"
                 was_repaired = True
            
            # [NUEVO] Detección de formatted_text sin asignación a result
            elif 'formatted_text' in code and 'result =' not in code and 'result=' not in code:
                 # Si 'formatted_text' está asignado a una variable
                 if re.search(r'formatted_text\s*=', code):
                     # Never grant trust to sandbox HTML; force a proper result shape.
                     code += (
                         '\nresult = {"__untrusted_html_preview__": formatted_text, '
                         '"__force_continue__": True, "__hint__": '
                         '"Do not assign bare formatted_text; return '
                         '{\'data\': [rows]} or use safe_plan_request."}'
                     )
                     was_repaired = True

            else:
                lines_clean = [l for l in code.split('\n') if l.strip() and not l.strip().startswith('#')]
                if lines_clean:
                    last_line = lines_clean[-1]
                    # Si la última línea parece una expresión
                    stripped_line = last_line.strip()
                    should_wrap = False
                    unwrap_print = False
                    
                    if (
                        stripped_line.startswith('env') or 
                        stripped_line.startswith('rec') or 
                        stripped_line.startswith('sorted') or 
                        stripped_line.startswith('system') or
                        stripped_line.startswith('[') or 
                        stripped_line.startswith('{')
                    ):
                        should_wrap = True
                    elif stripped_line.startswith('print(') and stripped_line.endswith(')'):
                        # Special case: print(x) -> result = x
                        should_wrap = True
                        unwrap_print = True
                    
                    if should_wrap:
                        # Find the index of the last non-empty line
                        idx_last = -1
                        current_lines = code.split('\n')
                        for i in range(len(current_lines)-1, -1, -1):
                            if current_lines[i].strip() and not current_lines[i].strip().startswith('#'):
                                idx_last = i
                                break
                        
                        if idx_last != -1:
                            indent = len(current_lines[idx_last]) - len(current_lines[idx_last].lstrip())
                            indent_str = current_lines[idx_last][:indent]
                            content = current_lines[idx_last].lstrip()
                            
                            if unwrap_print:
                                content_inner = content[6:-1] # Remove print( and )
                                current_lines[idx_last] = f"{indent_str}result = {content_inner}"
                            else:
                                current_lines[idx_last] = f"{indent_str}result = {content}"
                            
                            code = '\n'.join(current_lines)
                            was_repaired = True

    except Exception as e:
        _logger.warning(f"[{_log_where()}] Error en reparación de implicit result: {e}")

    # 5. Quitar línea suelta `result` al final (idiosincrasia REPL en snippets de contexto)
    try:
        lines = code.rstrip().split('\n')
        while lines and lines[-1].strip() == 'result':
            lines.pop()
            was_repaired = True
        if was_repaired:
            code = '\n'.join(lines)
            if code and not code.endswith('\n'):
                code += '\n'
    except Exception as e:
        _logger.warning(f"[{_log_where()}] Error eliminando result suelto final: {e}")

    # 6. result.append/extend sin result = [] previo (patrón trial_balance muy frecuente)
    try:
        if re.search(r'\bresult\.(append|extend)\s*\(', code):
            assigns_before_append = False
            out_lines = []
            for line in code.split('\n'):
                stripped = line.strip()
                if stripped and not stripped.startswith('#'):
                    if re.match(r'result\s*(?:\+)?=', stripped):
                        assigns_before_append = True
                    if (
                        re.search(r'\bresult\.(append|extend)\s*\(', line)
                        and not assigns_before_append
                    ):
                        indent = len(line) - len(line.lstrip())
                        indent_str = line[:indent]
                        out_lines.append(f"{indent_str}result = []")
                        assigns_before_append = True
                        was_repaired = True
                out_lines.append(line)
            if was_repaired:
                code = '\n'.join(out_lines)
    except Exception as e:
        _logger.warning(f"[{_log_where()}] Error en reparación result.append sin init: {e}")

    if was_repaired:
        lines = code.split('\n')
    
    for i, line in enumerate(lines):
        repaired_line = line
        
        # Detectar cadenas sin cerrar: línea que termina con comilla simple o doble sin cerrar
        # Pero solo si no es un comentario y tiene una comilla de apertura
        if not line.strip().startswith('#'):
            # Contar comillas simples y dobles
            single_quotes = line.count("'") - line.count("\\'")
            double_quotes = line.count('"') - line.count('\\"')
            
            # Si hay un número impar de comillas, la cadena no está cerrada
            # Intentar cerrarla si la línea termina con texto (no con operador, etc.)
            if (single_quotes % 2 == 1 or double_quotes % 2 == 1) and line.strip():
                # Verificar si la línea parece ser parte de una asignación a result
                if 'result' in line and 'formatted_text' in line:
                    # Si termina con comilla sin cerrar, intentar cerrarla
                    if line.rstrip().endswith('"') and double_quotes % 2 == 1:
                        # Ya tiene comilla al final, pero está mal formada
                        # Podría ser que falta cerrar antes de un salto de línea
                        pass
                    elif not line.rstrip().endswith(('"', "'")):
                        # La línea no termina con comilla, añadirla
                        if double_quotes % 2 == 1:
                            repaired_line = line.rstrip() + '"'
                            was_repaired = True
                        elif single_quotes % 2 == 1:
                            repaired_line = line.rstrip() + "'"
                            was_repaired = True
        
        repaired_lines.append(repaired_line)
    
    if was_repaired:
        repaired_code = '\n'.join(repaired_lines)
        # Validar que el código reparado sea sintácticamente válido
        try:
            import ast
            ast.parse(repaired_code, '<relaxaicode>', 'exec')
            return repaired_code, True
        except SyntaxError:
            _logger.warning(f"[{_log_where()}] Reparación automática falló - código aún inválido")
            return original_code, False
    
    return original_code, False
