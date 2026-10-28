# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 Seges
# Seges: parche 23 ampliado (PNS-101, seguridad). Ver docs/pendiente/parches_pns_ai.md
"""Formateador propio del sandbox para ``str.format`` / ``str.format_map``.

``str.format`` es un método en C: resuelve la cadena de atributos de la plantilla
sobre el objeto real (``'{0.mapped.__func__.__globals__[config]}'.format(user)``)
sin pasar por ``guarded_getattr``. Un ``str`` guardado en los builtins no sirve,
porque los literales son siempre ``str`` nativo. El punto de enganche es el
acceso al atributo ``.format`` / ``.format_map``, que el AST ve SIEMPRE sea cual
sea el receptor (literal, variable, concatenación o llamada):

  1. En compilación, ``_FormatAttrRewriter`` reescribe todo ``ast.Attribute`` con
     ``attr in {'format', 'format_map'}`` y ``ctx=Load`` como
     ``_sandbox_str_attr(<receptor>, '<attr>')``. Sobre el ``Attribute`` (no solo
     sobre el ``Call``), para que ``f = t.format`` también quede cubierto.
  2. En runtime, ``_sandbox_str_attr`` devuelve el ``format`` / ``format_map``
     ligado a un ``SandboxFormatter``, cuyo ``get_field`` resuelve cada ``.atributo``
     por ``guarded_getattr`` (es decir, por ``sandbox_forbidden_name``).
  3. ``format`` / ``format_map`` están en ``sandbox_forbidden_name``, así que
     ``getattr`` / ``attrgetter`` / ``methodcaller`` no alcanzan el método nativo.

Se compila el AST transformado DIRECTAMENTE con ``compile(tree, …)``; NO se usa
``ast.unparse`` (Python 3.9+), porque el objetivo es Python 3.7.3 (Odoo 14).

No importa ``context_builder`` de forma perezosa ni este módulo es importado por
él: ``context_builder`` se carga sin tocar este módulo, así que el import relativo
de ``guarded_getattr`` de nivel superior no crea ciclo.
"""
import ast
import string as _string_mod
from _string import formatter_field_name_split

from .context_builder import guarded_getattr

try:  # Markup del motor; no es módulo del sandbox (la allowlist lo bloquea).
    from markupsafe import Markup as _Markup
except ImportError:  # pragma: no cover - markupsafe siempre está en Odoo 14
    _Markup = None


class SandboxFormatter(_string_mod.Formatter):
    """``string.Formatter`` cuyos campos pasan por el filtro del sandbox.

    ``get_field`` parte el campo con ``formatter_field_name_split`` y resuelve el
    primer elemento con ``get_value``, cada ``.atributo`` con ``guarded_getattr``
    (``sandbox_forbidden_name``) y cada ``[clave]`` con el ``getitem`` normal (el
    vector de escape son los atributos, ya cubiertos). Las especificaciones
    anidadas (``'{0:{1.x}}'``) pasan por este mismo ``get_field`` porque
    ``vformat`` recurre sobre el ``format_spec``.
    """

    def get_field(self, field_name, args, kwargs):
        first, rest = formatter_field_name_split(field_name)
        obj = self.get_value(first, args, kwargs)
        for is_attr, i in rest:
            if is_attr:
                obj = guarded_getattr(obj, i)
            else:
                obj = obj[i]
        return obj, first


def _bound_format(template):
    def _format(*args, **kwargs):
        return SandboxFormatter().vformat(template, args, kwargs)
    return _format


def _bound_format_map(template):
    def _format_map(mapping):
        return SandboxFormatter().vformat(template, (), mapping)
    return _format_map


def _refuse_format(attr):
    raise AttributeError(
        f"Access to attribute {attr!r} is not allowed in RelaxAICode (sandbox)."
    )


def _sandbox_str_attr(receiver, attr):
    """Resuelve ``receiver.format`` / ``receiver.format_map`` para el sandbox.

    * ``Markup`` (subclase de ``str``): se comprueba ANTES que ``str`` para que no
      caiga en la rama de ``str`` y pierda el autoescape; se rechaza (el
      formateador con escape se reabre solo si aparece un uso legítimo, ver
      docs/pendiente). Misma excepción y estilo que los nombres prohibidos.
    * instancia de ``str``: ``format`` / ``format_map`` ligados al ``SandboxFormatter``.
    * el tipo ``str`` (``str.format(t, …)``): re-despacha sobre la plantilla real
      ``t``, que vuelve a pasar por los chequeos de Markup / str.
    * cualquier otro receptor: ``guarded_getattr`` (y como ``format`` /
      ``format_map`` están en ``sandbox_forbidden_name``, rechaza).
    """
    if _Markup is not None and isinstance(receiver, _Markup):
        _refuse_format(attr)
    if isinstance(receiver, str):
        return _bound_format(receiver) if attr == 'format' else _bound_format_map(receiver)
    if receiver is str:
        if attr == 'format':
            return lambda template, *a, **k: _sandbox_str_attr(template, 'format')(*a, **k)
        return lambda template, mapping: _sandbox_str_attr(template, 'format_map')(mapping)
    return guarded_getattr(receiver, attr)


class _FormatAttrRewriter(ast.NodeTransformer):
    """``x.format`` / ``x.format_map`` (Load) → ``_sandbox_str_attr(x, '<attr>')``."""

    def visit_Attribute(self, node):
        self.generic_visit(node)
        if node.attr in ('format', 'format_map') and isinstance(node.ctx, ast.Load):
            call = ast.Call(
                func=ast.Name(id='_sandbox_str_attr', ctx=ast.Load()),
                args=[node.value, ast.Constant(value=node.attr)],
                keywords=[],
            )
            return ast.copy_location(call, node)
        return node


def rewrite_format_attrs(tree):
    """Aplica la reescritura in situ y recoloca posiciones. Devuelve el árbol."""
    _FormatAttrRewriter().visit(tree)
    ast.fix_missing_locations(tree)
    return tree


class SandboxCode:
    """Código compilado por ``compile_sandbox_code`` (ya lleva la reescritura).

    ``run_sandbox_code`` solo acepta esto o el texto fuente: un objeto de código
    hecho con ``compile()`` normal no se puede ejecutar por esa vía.
    """
    __slots__ = ('code',)

    def __init__(self, code):
        self.code = code


def compile_sandbox_code(code, filename='<relaxaicode>'):
    """Compila el código del sandbox con la reescritura de ``.format``.

    Parsea, reescribe los accesos a ``.format`` / ``.format_map`` y compila el
    AST DIRECTAMENTE (sin ``ast.unparse``). ``SyntaxError`` se propaga igual que
    ``compile(code, …)`` para que ``tool_relaxaicode`` lo trate como antes.
    Devuelve un ``SandboxCode`` para ``run_sandbox_code``.
    """
    tree = ast.parse(code, filename, 'exec')
    rewrite_format_attrs(tree)
    return SandboxCode(compile(tree, filename, 'exec'))


def run_sandbox_code(ctx, code, filename='<relaxaicode>'):
    """Única entrada para ejecutar código del sandbox (relaxaicode y skills).

    ``code`` es el texto fuente (se compila aquí con ``compile_sandbox_code``) o
    lo que ya devolvió ``compile_sandbox_code``. Inyecta ``_sandbox_str_attr``
    justo antes de ``exec``, después de todos los valores del llamante, para que
    ningún parámetro lo sombree. Solo unifica la compilación y la inyección: los
    globals (``ctx``) y la gestión de errores son de cada vía.
    """
    if isinstance(code, str):
        code = compile_sandbox_code(code, filename)
    elif not isinstance(code, SandboxCode):
        raise TypeError('run_sandbox_code needs source text or compile_sandbox_code output')
    ctx['_sandbox_str_attr'] = _sandbox_str_attr
    # Único exec del sandbox: el código ya pasó el AST y la reescritura.
    exec(code.code, ctx, ctx)  # pylint: disable=exec-used
