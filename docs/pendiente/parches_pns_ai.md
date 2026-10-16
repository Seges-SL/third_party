# Parches de compatibilidad con Odoo 14 en los módulos pns_ai

- **Rama:** `14.0-pns-ai-3`
- **Fecha:** 2026-10-13
- **Versión del fabricante parcheada:** `pns_base` 14.0.1.2.32 · `pns_ai_mcp` 14.0.3.1.782 ·
  `pns_ai_chatboo` 14.0.2.1.453
- **Entorno objetivo:** imagen oficial de Odoo 14 (Debian Buster): Python 3.7.3 y Pillow 5.4.1
  (`requirements.txt:34` de Odoo 14 fija `Pillow==5.4.1` con Python ≤ 3.7).
- **Contexto:** `docs/pendiente/seguimiento_informe_pns_ai.md`, PNS-81 y sección «Compatibilidad con
  Odoo 14».

> **Regla:** estos parches no se envían al fabricante como código: se le comunican como hallazgo;
> cuando su versión los corrija, se revierte el commit del parche.
>
> Al sustituir el código por una versión nueva del fabricante, los parches desaparecen con él.
> Antes de probarla en Odoo 14, ejecuta la comprobación de cada entrada. Si alguna sigue dando
> resultado, vuelve a aplicar ese parche (mismo cambio, mismo comentario `# Seges: …`).

Cada cambio lleva junto a él un comentario con el prefijo común
`# Seges: parche de compatibilidad con Odoo 14`, seguido de un paréntesis con el motivo y de
`Ver docs/pendiente/parches_pns_ai.md`. El paréntesis es `(Python 3.7 / Pillow 5.4)` en los parches 1
a 3 y `(API de Odoo 14: Environment sin sudo)` en el 4. El parche 5 no es de Odoo 14 sino de
compatibilidad con Gemini, y su comentario es `# Seges: parche de compatibilidad (Gemini 3 por el
protocolo OpenAI: thought_signature)`; el `grep` lo lista igual. Para listarlos: `grep -rn "Seges: parche de compatibilidad" pns_base pns_ai_mcp pns_ai_chatboo`.

## Parche 1: `pns_ai_mcp/controllers/mcp_decorators.py:171` (antes `:169`)

- **PNS:** PNS-81 (fallo al importar).
- **Qué falla sin él:** con Python < 3.9 (3.7.3 en la imagen de Odoo 14), al importar. La anotación
  de retorno `tuple[bool, Optional[str]]` se evalúa al definir la función y el archivo no tiene
  `from __future__ import annotations`. Lanza `TypeError: 'type' object is not subscriptable`. No se
  importan ni `pns_ai_mcp` ni `pns_ai_chatboo`, y una BD que los tenga instalados no carga.
- **Cambio:**
  ```diff
  -from typing import Any, Callable, Dict, List, Optional, Type, get_type_hints
  +from typing import Any, Callable, Dict, List, Optional, Tuple, Type, get_type_hints
  ...
  -def _validate_arguments(schema: Dict[str, Any], arguments: Dict[str, Any]) -> tuple[bool, Optional[str]]:
  +# Seges: parche de compatibilidad con Odoo 14 (Python 3.7 / Pillow 5.4). Ver docs/pendiente/parches_pns_ai.md
  +# (tuple[...] -> Tuple[...]; Tuple añadido al import de typing de la línea 8)
  +def _validate_arguments(schema: Dict[str, Any], arguments: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
  ```
- **Qué se degrada:** nada. `typing.Tuple` significa lo mismo en todas las versiones, y nadie lee
  esa anotación (la única llamada está en el `wrapper` de `@mcp_tool`).
- **Cómo comprobar si el fabricante ya lo ha corregido:** buscar en los archivos sin
  `from __future__ import annotations` anotaciones de tipos genéricos con minúscula:
  ```sh
  for f in $(grep -rlE "(->|:)\s*(tuple|list|dict|set|frozenset|type)\[" --include=*.py pns_base pns_ai_mcp pns_ai_chatboo); do
    grep -q "from __future__ import annotations" "$f" || grep -nHE "(->|:)\s*(tuple|list|dict|set|frozenset|type)\[" "$f"
  done
  ```
  Si no sale nada, está corregido. La prueba definitiva es
  `odoo-dev 14 paridad pns_base,pns_ai_mcp,pns_ai_chatboo` con 0 «no se importan».

## Parche 2: `pns_base/utils/pdf_io.py:94-111`

- **PNS:** PNS-81 (fallo en ejecución, Pillow).
- **Qué falla sin él:** con Pillow < 6.0 (5.4.1 en la imagen de Odoo 14), `_open_picture` llama a
  `ImageOps.exif_transpose`, que no existe. Lanza `AttributeError`. Todas las funciones de imagen
  (`as_picture`, `picture_size`, `shrink_picture`, `turn_picture`, `picture_pdf`) lo capturan y
  devuelven `None` («no es una imagen»), así que el fallo no avisa:
  - `/pns_ai_mcp/remote_image` responde 404 a todas las imágenes (`utils/remote_image.py:79`);
  - Chatboo reenvía al proveedor las imágenes sin reescalar
    (`pns_ai_chatboo/models/chatboo_async_request.py:1079`, y también `:1341` y `:1415`).
- **Cambio:** se usa la función de Pillow si existe. Si no existe, una equivalente que lee la
  orientación EXIF (0x0112) y aplica la misma tabla que Pillow ≥ 6.0.
  ```diff
       image.load()
  -    return ImageOps.exif_transpose(image), kind
  +    # Seges: parche de compatibilidad con Odoo 14 (Python 3.7 / Pillow 5.4). Ver docs/pendiente/parches_pns_ai.md
  +    transpose = getattr(ImageOps, 'exif_transpose', None) or _exif_transpose_pil5
  +    return transpose(image), kind
  +
  +
  +# Seges: parche de compatibilidad con Odoo 14 (Python 3.7 / Pillow 5.4). Ver docs/pendiente/parches_pns_ai.md
  +def _exif_transpose_pil5(image):
  +    """ImageOps.exif_transpose for Pillow < 6.0 (orientation from _getexif(), JPEG)."""
  +    from PIL import Image
  +    try:
  +        orientation = (image._getexif() or {}).get(0x0112)
  +    except Exception:
  +        orientation = None
  +    method = {
  +        2: Image.FLIP_LEFT_RIGHT, 3: Image.ROTATE_180, 4: Image.FLIP_TOP_BOTTOM,
  +        5: Image.TRANSPOSE, 6: Image.ROTATE_270, 7: Image.TRANSVERSE, 8: Image.ROTATE_90,
  +    }.get(orientation)
  +    return image.transpose(method) if method is not None else image
  ```
  Con Pillow ≥ 6.0 el comportamiento no cambia (se usa `ImageOps.exif_transpose`).
- **Qué se degrada (solo con Pillow < 6.0):**
  - La orientación solo se lee en los formatos que tienen `_getexif()` en Pillow 5.4: en la práctica
    JPEG, el formato de las fotos de móvil. Un PNG o TIFF con etiqueta de orientación (raro) no se
    gira.
  - Con un EXIF corrupto, la imagen se trata como «sin orientación» y no se descarta.
  - A diferencia de Pillow ≥ 6.0, no se borra la etiqueta 0x0112 de la imagen girada. No tiene
    efecto, porque ninguna función de `pdf_io.py` guarda la imagen con `exif=`: la salida no lleva
    EXIF.
- **Avisos del lint (no corregidos a propósito):** C0415 (`import` dentro de la función) y W0718
  (`except Exception`). Siguen el estilo del resto del archivo del fabricante.
- **Cómo comprobar si el fabricante ya lo ha corregido:**
  ```sh
  grep -n "exif_transpose" pns_base/utils/pdf_io.py
  ```
  Está corregido si toda llamada a `ImageOps.exif_transpose` queda protegida (`getattr`/`hasattr` o
  `try/except AttributeError` con giro alternativo). Si la llamada sigue siendo directa, el
  fabricante no lo ha corregido.

## Parche 3: `pns_ai_mcp/utils/relaxaicode_recipe.py:507-509`

- **PNS:** PNS-81 (fallo en ejecución, Python), también §7.3 del informe.
- **Qué falla sin él:** con Python < 3.8 (3.7.3 en la imagen de Odoo 14), `ensure_date_param_coercion`
  llama a `ast.get_source_segment`, que no existe. Lanza `AttributeError`.
  - En el camino principal de `tool_relaxaicode` (`controllers/tools_relaxaicode.py:1867`) no hay
    protección. El `except` general lo convierte en un error de la herramienta.
  - Falla todo código que defina, a nivel de módulo, una función con un parámetro de fecha
    (`date`, `day`, `fecha`, `when`, `dia`…; `_DATE_PARAM_HINTS`). Es el caso típico de las
    consultas por rango de fechas.
  - En la reparación (`tools_relaxaicode.py:1252`) se captura: solo deja un aviso en el log y se
    salta la conversión.
- **Cambio:** se usa `ast.get_source_segment` si existe. Si no existe, se usa todo el código, que es
  la alternativa que el fabricante ya preveía (`or src`).
  ```diff
  -    already = ast.get_source_segment(src, func) or src
  +    # Seges: parche de compatibilidad con Odoo 14 (Python 3.7 / Pillow 5.4). Ver docs/pendiente/parches_pns_ai.md
  +    get_segment = getattr(ast, 'get_source_segment', None)
  +    already = (get_segment and get_segment(src, func)) or src
  ```
- **Qué se degrada (solo con Python < 3.8):**
  - La comprobación «¿ya tiene la conversión?» mira todo el código y no solo la función principal.
  - Si **otra** parte del código ya contiene `fromisoformat(<param>[` con el mismo nombre de
    parámetro, no se inserta la conversión en la función principal. En ese caso puede volver el
    fallo 909E (`.isoformat()` sobre un `str`), que es como estaba antes de esta mejora del
    fabricante.
  - Nunca se inserta de más.
- **Cómo comprobar si el fabricante ya lo ha corregido:**
  ```sh
  grep -rn "get_source_segment\|end_lineno\|end_col_offset" --include=*.py pns_base pns_ai_mcp pns_ai_chatboo
  ```
  Está corregido si no sale nada, o si toda aparición está protegida (`getattr`/`hasattr` o
  `try/except`) con alternativa.

## Parche 4: `pns_ai_mcp/controllers/main.py:1474` y `:1600` (antes `:1473` y `:1598`)

- **Fecha:** 2026-10-14.
- **PNS:** PNS-81 (fallo en ejecución, API de Odoo 14); afecta a la prueba HTTP de PNS-12.
- **Qué falla sin él:** `_mcp_prompts_list` y `_mcp_prompts_get` llaman a `.sudo()` sobre el
  `Environment` que devuelve `_get_mcp_env()` (`request.env(user=<usuario de la clave>)`). En Odoo 14
  `Environment` no tiene `sudo()` (solo `__call__(cr, user, context, su)`, `odoo/api.py:508` de la
  referencia). El `AttributeError` se captura y solo deja un aviso en el log:
  - `prompts/list` devuelve solo `system_prompt`, sin ningún contexto;
  - `prompts/get` de cualquier contexto responde `-32602 Prompt not found`.
  Los clientes MCP externos no reciben ningún contexto por `prompts/*` (comprobado en la fase 3c). En
  3.1.486 no pasaba: esas rutas no tenían `.sudo()`.
- **Cambio:**
  ```diff
  @@ _mcp_prompts_list (línea 1473 del fabricante)
  -            env = self._get_mcp_env().sudo()
  +            # Seges: parche de compatibilidad con Odoo 14 (API de Odoo 14: Environment sin sudo). Ver docs/pendiente/parches_pns_ai.md
  +            env = self._get_mcp_env()(su=True)
  @@ _mcp_prompts_get (línea 1598 del fabricante)
  -            env = self._get_mcp_env().sudo()
  +            # Seges: parche de compatibilidad con Odoo 14 (API de Odoo 14: Environment sin sudo). Ver docs/pendiente/parches_pns_ai.md
  +            env = self._get_mcp_env()(su=True)
  ```
  `env(su=True)` es lo que hace `sudo()` en un recordset de Odoo 14: el mismo uid (el usuario de la
  clave) con el modo superusuario. Así el `env.user` sigue siendo el real y el filtro por propietario
  de PNS-12 (`ownership_read_domain()`) se aplica igual. El comentario desplaza la numeración de
  `main.py`: +1 de la línea 1473 en adelante y +2 de la 1598 en adelante.
- **Qué se degrada:** nada. Con versiones de Odoo cuyo `Environment` tenga `sudo()` el efecto es el
  mismo.
- **Cómo comprobar si el fabricante ya lo ha corregido:** en `_mcp_prompts_list` y
  `_mcp_prompts_get` de `controllers/main.py` no debe quedar `.sudo()` aplicado al resultado de
  `_get_mcp_env()`.
- **Comprobaciones realizadas (2026-10-14):**
  1. Compilación del archivo con Python 3.7.3 dentro de la imagen `odoo-dev:14-lab_pns_ai`, sin Odoo
     (`compile()` del código fuente): correcta.
  2. Servidor del laboratorio reiniciado con `odoo-dev 14 parar` y `odoo-dev 14 arrancar` (desde
     `~/GitHub/lab_pns_ai`; `arrancar` solo no recrea el contenedor si ya está en marcha). Arranque
     sin tracebacks.
  3. Prueba por `/mcp` (2026-10-14, 16:12 UTC; detalle en `verificacion_seguridad_pns_ai.md`,
     «Versión 3.1.782 — parche 4»), con A (interno sin IA, contexto privado) y B
     (`group_ai_conversational`, clave MCP, contexto privado propio):

     | Paso | Llamada (B) | Resultado |
     |---|---|---|
     | 1 | `initialize` | 200, `result` |
     | 2 | `prompts/list` | 200, 21 prompts: los contextos compartidos y el privado de B; no el de A |
     | 3 | `prompts/get` del contexto de B | 200, devuelve su contenido |
     | 4 | `prompts/get` del contexto de A | `-32602 Prompt not found` |

     En el log, ningún `AttributeError` ni traceback.
  - **Resultado:** eficaz. Los datos de prueba se borraron y se comprobó con `SELECT`.

## Parche 5: `pns_ai_mcp/lib/llm/drivers/openai_driver.py:659-667` (`iter_chat`)

- **Fecha:** 2026-10-16.
- **PNS:** ninguno todavía (incompatibilidad con Gemini 3 detectada en staging). Análisis completo en
  [analisis_parche5_gemini.md](analisis_parche5_gemini.md).
- **Qué falla sin él:** con Gemini 3.x configurado con `protocol = openai`
  (`…/v1beta/openai/chat/completions`), todo turno de Chatboo en el que el modelo llama a una
  herramienta falla en la petición siguiente del bucle de herramientas con
  `HTTP 400 … Function call is missing a thought_signature in functionCall parts`. Gemini envía la
  firma en `tool_calls[].extra_content.google.thought_signature` y exige recibirla de vuelta en el
  mismo `tool_call`; `iter_chat` reconstruye cada `tool_call` solo con `id`, `type` y `function` y la
  pierde. «Test Connection» funciona porque no envía herramientas.
- **Cambio:** dentro del bucle `for tc in delta.get('tool_calls') or []:`, tras acumular los
  argumentos, se copia `extra_content` a la fila del `tool_call` si el delta lo trae (de cualquier
  delta, no solo del primero). El motor (`agent_engine.py`) ya reenvía ese mismo dict en la
  siguiente petición, así que no hay que tocar nada más.
  ```diff
                       if fn.get('arguments'):
                           row['function']['arguments'] += fn['arguments']
  +                    # Seges: parche de compatibilidad (Gemini 3 por el protocolo OpenAI:
  +                    # thought_signature). Ver docs/pendiente/parches_pns_ai.md
  +                    # Gemini exige devolver extra_content.google.thought_signature en el
  +                    # tool_call; otros proveedores no lo envían y la fila no cambia.
  +                    extra = tc.get('extra_content')
  +                    if isinstance(extra, dict) and extra:
  +                        merged = dict(row.get('extra_content') or {})
  +                        merged.update(extra)
  +                        row['extra_content'] = merged
           finally:
  ```
- **Qué se degrada:** nada. Los proveedores que no envían `extra_content` (OpenAI, Azure, Ollama,
  vLLM…) reciben exactamente el mismo mensaje que antes. No se cubren (ampliaciones opcionales del
  análisis, no aplicadas): llamadas paralelas de Gemini sin `index` y el fallback de llamadas
  escritas en texto (`agent_engine.py:3215-3240`).
- **Cómo comprobar si el fabricante ya lo ha corregido:**
  ```sh
  grep -n "extra_content" pns_ai_mcp/lib/llm/drivers/openai_driver.py
  ```
  Si, sin el parche, sale alguna línea en `iter_chat` que copie `extra_content` (o
  `thought_signature`) al `tool_call`, está corregido y este parche sobra.
- **Comprobaciones realizadas (2026-10-16):**
  1. `py_compile` del archivo: correcto con el Python del equipo (3.12.3) y con Python 3.7.3 dentro
     de la imagen `odoo-dev:14`.
  2. Prueba del driver sin Odoo ni BD, en la imagen `odoo-dev:14` (Python 3.7.3, `requests` 2.21.0),
     con `requests.post` sustituido por un stream SSE simulado. Se ejecutó con el driver parcheado y
     con el de `HEAD` (sin parche) para comparar:

     | Caso | Resultado |
     |---|---|
     | (a) `tool_call` completo en un delta, con `extra_content` y sin `index` | OK: el mensaje final conserva `extra_content` (sin parche se perdía) |
     | (b) stream clásico troceado, sin `extra_content` | OK: mensaje idéntico al del driver sin parche |
     | (c) `extra_content` en un delta posterior al del `id` | OK: se conserva; `id`, nombre y argumentos intactos |
  - **Pendiente:** prueba en staging con Gemini 3.5, 3.6 y 3.7-flash (plan de prueba del análisis).

## Comprobaciones realizadas (2026-10-13)

1. `python3 -m py_compile` de los tres archivos: correcto con el Python del equipo y con Python
   3.7.3 dentro de la imagen `odoo-dev:14-lab_pns_ai`.
2. `odoo-dev 14 paridad pns_base,pns_ai_mcp,pns_ai_chatboo`, desde `~/GitHub/lab_pns_ai` (solo
   lectura):
   ```
   módulos instalados: 27 · versión igual: 24 · versión distinta: 3 · sin código: 0 · no se importan: 0
   VERSIÓN        pns_ai_chatboo: BD 14.0.2.1.322 · código 14.0.2.1.453
   VERSIÓN        pns_ai_mcp: BD 14.0.3.1.486 · código 14.0.3.1.782
   VERSIÓN        pns_base: BD 14.0.1.2.10 · código 14.0.1.2.32
   RESULTADO: puede cargarla
   ```
   No se importan: 0. La VERSIÓN distinta es normal antes de `actualizar`.
3. Pruebas unitarias en la imagen `odoo-dev:14-lab_pns_ai`, sin Odoo ni BD:
   - Orden: `docker run --rm -i -v <repo>:/src:ro --entrypoint python3 odoo-dev:14-lab_pns_ai -I - < script.py`.
   - Repo montado en solo lectura.
   - `pdf_io.py` y `relaxaicode_recipe.py` se cargan directamente desde su archivo con `importlib`.
   - Entorno: Python 3.7.3 · Pillow 5.4.1 · `ImageOps.exif_transpose` no existe ·
     `ast.get_source_segment` no existe (se ejecuta el código alternativo de los dos parches).
   - **Parche 2:**
     - Imagen de prueba: imagen «derecha» de 40×80 con cuatro cuadrantes de colores distintos.
     - Para cada orientación EXIF del 1 al 8 se guardó como JPEG con la transformación inversa y la
       etiqueta 0x0112.
     - Resultados:

       | Caso | Resultado |
       |---|---|
       | JPEG orientación 1 a 4 (guardada 40×80) | OK: 40×80, cuadrantes en su sitio, `picture_size=(40, 80)`, `as_picture` no es `None` |
       | JPEG orientación 5 a 8 (guardada 80×40) | OK: 40×80, cuadrantes en su sitio, `picture_size=(40, 80)`, `as_picture` no es `None` |
       | JPEG sin EXIF | OK: sin cambios, `shrink_picture` → `image/jpeg` |
       | PNG | OK: sin cambios, `shrink_picture` → `image/png` |
   - **Parche 3:**
     - Código de ejemplo: `def ventas(date_from, date_to)` con docstring, que llama a
       `.isoformat()` sobre los dos parámetros, más `result = ventas('2026-01-01', '2026-01-31')`.
     - 1.ª llamada: inserta **una** conversión por parámetro, tras la docstring.
     - 2.ª llamada sobre el resultado: no cambia nada (código idéntico, una conversión por
       parámetro).
     - El código resultante compila y se ejecuta:
       `result = {'desde': '2026-01-01', 'hasta': '2026-01-31', 'total': 0}`.
   - **Resultado:** 0 fallos.

## Pendiente (fase 3, en el laboratorio con Odoo)

Tras `odoo-dev 14 actualizar pns_base,pns_ai_mcp,pns_ai_chatboo`:

- una respuesta con una imagen externa permitida, que debe mostrarse (no 404): **hecha** en la fase
  3b-2 (`remote_image` devuelve 200 con la imagen re-codificada);
- una consulta del chat que defina una función con un parámetro `date_from`, que debe responder
  sin error de la herramienta: **pendiente para staging** (proveedor saturado en el laboratorio);
- una foto de móvil vertical adjunta en Chatboo, que debe llegar derecha al proveedor: **pendiente
  para staging** (proveedor saturado en el laboratorio).

Las dos pendientes están en la lista de `verificacion_seguridad_pns_ai.md`, «Pruebas pendientes para
staging» de la fase 3b-2.
