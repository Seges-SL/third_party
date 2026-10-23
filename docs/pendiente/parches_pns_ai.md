# Parches de Seges en los módulos pns_ai

- **Ramas:** `14.0-pns-ai-3` (parches 1 a 6) · `14.0-pns-ai-correcciones` (parches 7 en adelante,
  [plan de corrección](plan_correccion_pns_ai.md))
- **Fecha:** 2026-10-13 (parches 1 a 3) · actualizado el 2026-10-20 (N11 y N12) y el 2026-10-21
  (staging de E2)
- **Versión del fabricante, base propia de Seges desde el 20/10/2026 (N12):** `pns_base` 14.0.1.2.32 ·
  `pns_ai_mcp` 14.0.3.1.782 · `pns_ai_chatboo` 14.0.2.1.453
- **Licencia:** Apache-2.0 (`LICENSE` y `NOTICE` de cada módulo, que se conservan sin cambios).
- **Entorno objetivo:** imagen oficial de Odoo 14 (Debian Buster): Python 3.7.3 y Pillow 5.4.1
  (`requirements.txt:34` de Odoo 14 fija `Pillow==5.4.1` con Python ≤ 3.7).
- **Contexto:** [decisiones](pns_ai_decisiones.md) N11 y N12 (§10);
  [seguimiento](seguimiento_informe_pns_ai.md), PNS-81 y «Compatibilidad con Odoo 14».

> **Regla (N11 y N12, 20/10/2026):**
> - Seges corrige en la rama los hallazgos PNS (seguridad, robustez y compatibilidad; lo funcional,
>   después) y mantiene la 3.1.782 como base propia. **Los parches son permanentes**: no se retiran
>   por una versión del fabricante, porque no se adoptan sus versiones.
> - Cambio mínimo, sin dependencias nuevas, sin tocar `version`, `depends` ni
>   `external_dependencies` de los manifest, ni `i18n`; `ir.model.access.csv` solo si no hay otra
>   forma (no admite el marcador).
> - Un parche por PNS, salvo causa común documentada en el propio parche (como el 12, PNS-01/02);
>   un commit por parche y un commit para los tests de cada entrega.
> - Nada se envía al fabricante como código. La 2.ª entrega del informe se envía al final del plan de
>   corrección, sin diffs (D2).
>
> Sustituye a la regla anterior («cuando su versión los corrija, se revierte el commit del parche»).

## Marcadores

Cada cambio lleva junto a él un comentario que empieza por `Seges: parche`, y todos se listan con:

```sh
grep -rn "Seges: parche" pns_base pns_ai_mcp pns_ai_chatboo
```

| Parches | Marcador |
|---|---|
| 1 a 3 | `# Seges: parche de compatibilidad con Odoo 14 (Python 3.7 / Pillow 5.4). Ver docs/pendiente/parches_pns_ai.md` |
| 4 | `# Seges: parche de compatibilidad con Odoo 14 (API de Odoo 14: Environment sin sudo). Ver docs/pendiente/parches_pns_ai.md` |
| 5 | `# Seges: parche de compatibilidad (Gemini 3 por el protocolo OpenAI: thought_signature)` |
| 6 | `# Seges: parche de compatibilidad (bloqueo de chatboo_session)` |
| 7 en adelante | `# Seges: parche N (PNS-XX, <tipo>). Ver docs/pendiente/parches_pns_ai.md`, con `PNS-XX` = el PNS o, si no tiene, el id de la [comparación con 3.1.879](../specs/comparacion_pns_ai_3-1-879.md) (`M10`, `M13`…; desde el 23/10/2026), y `<tipo>` = `seguridad`, `robustez`, `compatibilidad` o `funcional`; `// …` en JS y `<!-- … -->` en XML |

Los marcadores de los parches 1 a 6 no se cambian: la ruta de este documento tampoco, porque la citan.

## Índice de parches

| N.º | PNS | Tipo | Archivos | Entrega | Commit | Estado |
|---|---|---|---|---|---|---|
| 1 | PNS-81 | compatibilidad | `pns_ai_mcp/controllers/mcp_decorators.py` | — | `ce6790b` | En LIYBEN |
| 2 | PNS-81 | compatibilidad | `pns_base/utils/pdf_io.py` | — | `ce6790b` | En LIYBEN |
| 3 | PNS-81 | compatibilidad | `pns_ai_mcp/utils/relaxaicode_recipe.py` | — | `ce6790b` | En LIYBEN |
| 4 | PNS-81 | compatibilidad | `pns_ai_mcp/controllers/main.py` | — | rama `14.0-pns-ai-3` | En LIYBEN |
| 5 | PNS-93 | compatibilidad | `pns_ai_mcp/lib/llm/drivers/openai_driver.py` | — | `27cadbb` | En LIYBEN |
| 6 | PNS-94 | robustez | `pns_ai_chatboo/models/chatboo_async_request.py` | — | `63ee2dc` | En LIYBEN |
| 7 | PNS-90 | seguridad | `pns_ai_mcp/models/fetch_cache.py`, `pns_ai_mcp/controllers/safe_plan.py`, `pns_ai_mcp/controllers/validators.py` | E1 | (ver `git log`) | Validado en staging |
| 8 | PNS-91 | seguridad | `pns_ai_mcp/models/url_whitelist.py`, `pns_ai_mcp/controllers/safe_plan.py`, `pns_ai_mcp/models/safe_operation.py`, `pns_ai_mcp/models/external_server.py`, `pns_ai_mcp/controllers/validators.py` | E1 | (ver `git log`) | Validado en staging |
| 9 | PNS-85 | seguridad | `pns_ai_mcp/models/ai_skill_param_cache.py`, `pns_ai_mcp/models/ai_skill.py`, `pns_ai_mcp/utils/agent_engine.py`, `pns_ai_mcp/controllers/validators.py` | E1 | `ba9e9d8` | Validado en staging |
| 10 | PNS-83 | seguridad | `pns_ai_mcp/models/mcp_user.py`, `pns_ai_mcp/models/key_pin_block.py`, `pns_ai_mcp/models/res_config_settings.py`, `pns_ai_mcp/controllers/validators.py` | E1 | `fae47d7` | Validado en staging |
| 11 | PNS-82 | seguridad | `pns_ai_chatboo/models/chatboo_session.py`, `pns_ai_chatboo/models/chatboo_async_request.py`, `pns_ai_mcp/controllers/validators.py` | E2 | `2cb5343` | Validado en staging |
| 12 | PNS-01, PNS-02 | seguridad | `pns_ai_mcp/models/ai_system_action.py` | E2 | `1cac02c` | Validado en staging |

Estados: Pendiente → Aplicado → Validado en laboratorio → Validado en staging → En LIYBEN.
Tests de cada entrega: E1 `2bb4f51`; E2 `422d2d7` y `792481c` (test del cron).
LIYBEN recibe los parches 7 en adelante de una vez, al terminar el plan de corrección (decisión del
20/10/2026).

## Versiones nuevas del fabricante (vigilancia, N12)

Las versiones nuevas **no se incorporan al repo**. Cuando el fabricante publique una:

1. Se descomprime **fuera del repo** (por ejemplo, `~/pns_fabricante/<versión>/`).
2. Un agente compara esa carpeta con la base (`git show` de los archivos de `14.0` o un `diff -ru`
   contra la copia de trabajo, descontando los parches de Seges) y busca **solo correcciones de
   seguridad**: comprobaciones de grupo o propiedad nuevas, métodos que pasan a privados, saneado,
   controles de URL, sandbox. No se buscan funciones nuevas.
3. Resultado en `docs/pendiente/vigilancia_pns_ai_<versión>.md`: candidatas, con archivo y línea, y
   si alguna corresponde a un PNS ya parcheado por Seges. Para estas, el apartado «Cómo comprobar si el fabricante ya lo
   ha corregido» de cada parche sigue sirviendo: dice si su versión trae una corrección equivalente.
4. Las que se aprueben se traen como parches nuevos de este documento, con el motivo «traída de la
   versión X.Y.Z del fabricante».

## Cambio de base a 3.1.879 (23/10/2026)

- **Rama `14.0-pns-ai-3879`:** los parches 1 a 9 quedan retirados (los cubre el fabricante); el 10, el
  11 y el 12 se adaptan con el mismo número.
- **`14.0-pns-ai-correcciones`, staging y LIYBEN:** siguen aplicados hasta el cambio de base.
- Plan, numeración y seguimiento: [plan de corrección sobre 3.1.879](plan_correccion_pns_ai_3879.md).

### Índice de la rama `14.0-pns-ai-3879`

| N.º | PNS / id | Tipo | Archivos | Entrega | Estado |
|---|---|---|---|---|---|
| 10 (adaptado) | PNS-83 | seguridad | `pns_ai_mcp/models/key_pin_desk.py`, `pns_ai_mcp/models/mcp_user.py` | E1′ | Validado en laboratorio (23/10/2026) |
| 12 (adaptado) | PNS-01, PNS-02 | seguridad | `pns_ai_mcp/models/ai_system_action.py`, `pns_ai_mcp/utils/privilege_cusp.py` | E1′ | Validado en laboratorio (23/10/2026) |
| 13 | M10 | seguridad | `pns_ai_mcp/models/safe_operation.py` | E1′ | Validado en laboratorio (23/10/2026) |
| 14 | M13 | seguridad | `pns_ai_mcp/models/ai_context_disk.py` | E1′ | Validado en laboratorio (23/10/2026) |
| 15 | PNS-07 | seguridad | `pns_ai_mcp/controllers/validators_base.py` | E1′ | Validado en laboratorio (23/10/2026) |
| 16 | PNS-54 | seguridad | `pns_ai_mcp/models/safe_operation.py` | E1′ | Validado en laboratorio (23/10/2026) |

Propuesta, comprobaciones previas y decisiones de E1′: [e1_propuesta_3879.md](e1_propuesta_3879.md).
Las entradas de esta rama están más abajo, en «Parches de la rama 14.0-pns-ai-3879 (E1′)».

## Cambios en tests del fabricante

Datos de prueba de tests del fabricante que en Odoo 14 no podían pasar. No corrigen el código de los
módulos, así que no llevan número de parche ni entran en el índice. Solo en la rama `14.0-pns-ai-3879`.

- **Marcador:** `# Seges: parche de tests E0′ (datos de prueba). Ver docs/pendiente/parches_pns_ai.md`,
  junto a cada cambio. Va sin PNS: el más cercano, PNS-50 («Tests no cargados o descartados; sin tests
  de seguridad negativa», [seguimiento](seguimiento_informe_pns_ai.md)), trata de tests que no se
  cargan, no de datos de prueba incompletos.
- **Origen:** [fase 3, parte 1](fase3_lab_pns_ai_3879.md), paso 3 (tabla «Nuevos frente a la línea
  base»), y la [comparación](../specs/comparacion_pns_ai_3-1-879.md), §5.5 (fila PNS-50 y PNS-77).
- **Entrega:** E0′ del [plan sobre 3.1.879](plan_correccion_pns_ai_3879.md).

| Archivo | Test | Causa | Cambio |
|---|---|---|---|
| `pns_ai_mcp/tests/test_change_journal.py` | `test_create_write_sequence_and_revert`, `test_unlink_archives_then_revert_and_empty_trash` (E) | `_exec` ejecuta el plan como usuario 1, que no está en `AI Writer`; `execute_safe_plan` lo exige (`controllers/controller_helpers.py:102`) | Función `_set_superuser_ai_writer`, llamada al principio de `_exec`: da `pns_ai_mcp.group_ai_writer` al usuario 1 en la transacción del test, que se deshace al terminar |
| `pns_ai_mcp/tests/test_paap_core.py` | `test_paap_i1_a_proposal_changes_nothing_and_hands_out_no_credential` (E) | `request_safe_plan` crea la operación en un cursor propio con commit (`controllers/safe_plan.py:2197` y siguientes), que no ve al usuario creado en la transacción del test: `IntegrityError` en `ai_safe_operation_user_id_fkey` | En `setUp`, `registry.enter_test_mode(self.cr)` con `leave_test_mode` en `addCleanup`, como hace `HttpCase` en Odoo 14 (`odoo/tests/common.py:1400-1404`): el cursor propio pasa a ser un `TestCursor` sobre la transacción del test (`odoo/modules/registry.py:698-706`) y no se confirma nada |

- **No se toca `test_failed_execute_journals_outside_rollback`** (F; queda como en el fabricante):
  - Probado en el laboratorio el 23/10/2026: dar `AI Writer` al usuario 1 en el cursor con commit del
    test no basta.
  - El plan lo frena otra comprobación del fabricante (`_meta_crud_block_error`, `controllers/safe_plan.py:878-880`:
    «Do not create, write or delete ir.model.fields via CRUD»), así que el test espera un texto antiguo
    (`base fields`).
  - La fila `failed` se escribe en un cursor con commit (`_record_failed_plan`), pero el test la busca
    con la transacción `REPEATABLE READ` del `TransactionCase`, que empezó antes y no la ve.
  - Además, el grupo confirmado contaminó otros tests: con él,
    `TestSafePlanAtomicity.test_normal_execution_marks_executed_and_applies_mutation` dejó de dar
    error, y volvió a darlo al retirarlo. Se deduce que la revocación en `addCleanup` no surtió
    efecto; la causa no se ha investigado.
  - Arreglarlo es rediseñar el test, no completar sus datos: pendiente de decisión de Sergio.
- **Cómo comprobar si el fabricante ya lo ha corregido:**
  ```sh
  grep -n "group_ai_writer\|enter_test_mode\|new_test_user" pns_ai_mcp/tests/test_change_journal.py pns_ai_mcp/tests/test_paap_core.py
  ```
  Corregido si sus versiones preparan un usuario con `AI Writer` en `test_change_journal` y evitan el
  cursor propio (o el usuario sin confirmar) en `test_paap_core`.

### Test del fabricante que falla por diseño con el parche 12 (E1′, 23/10/2026)

- **Test:** `pns_ai_mcp/tests/test_system_action.py`,
  `TestSystemTrustedActions.test_paap_i7_cusp_roles_out_of_reach_of_an_ai_admin` (F).
- **Decisión de Sergio (23/10/2026):** se acepta como F por diseño y **no se toca**. La línea base
  pasa a 18 F.
- **Dónde falla:** solo en la última comprobación (`:510-514`), que espera que un AI Administrator
  sin Ajustes pueda proponer un grupo que no es cúspide. Con el criterio de Seges (parche 12) se
  rechaza: «Only a Settings administrator can add or remove user groups.».
- **Lo anterior del test pasa:** la cúspide, la acción de confianza y los cinco pasos CRUD. La
  comprobación de Seges va detrás de la del fabricante, que da primero su mensaje
  («maximum-privilege»).
- **Comprobado:** con el parche 12 neutralizado, el test vuelve a pasar.

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
- **Estado:** **validado en staging (16/10/2026)** (comprobación 3).
- **PNS:** PNS-93 del [seguimiento](seguimiento_informe_pns_ai.md) (incompatibilidad con Gemini 3
  detectada en staging). Análisis completo en [analisis_parche5_gemini.md](analisis_parche5_gemini.md).
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
  3. **Staging (16/10/2026): validado.** Desplegado con el commit `27cadbb` (huella comprobada;
     `diff -rq` con solo `openai_driver.py`). Gemini por el protocolo `openai`, con
     `gemini-3.6-flash`, `gemini-3.5-flash-lite` y `gemini-3.5-flash` (`3.7-flash` daba 503 con
     frecuencia):

     | Caso | Resultado |
     |---|---|
     | Turno con varias rondas de herramientas (`relaxaicode`) | OK: sin 400 (antes, 400 en la segunda ronda) |
     | Segundo turno en la misma conversación | OK: sin 400 |
     | Llamadas paralelas en la misma ronda | no observadas: la ampliación 1 del análisis sigue sin aplicar |
     | No regresión con otro proveedor OpenAI-compatible | no probada: en staging solo había Gemini |

## Parche 6: `pns_ai_chatboo/models/chatboo_async_request.py` (`_process`, `:697-698` y `:714-715`; método nuevo `_release_worker_cursor`, `:839-866`)

- **Fecha:** 2026-10-16.
- **Estado:** **validado en staging (16/10/2026)** (comprobación 3).
- **PNS:** PNS-94 del [seguimiento](seguimiento_informe_pns_ai.md) (bloqueo detectado en staging).
  Análisis completo en [analisis_bloqueo_chatboo_session.md](analisis_bloqueo_chatboo_session.md)
  (corrección 1a de §5.2).
- **Qué falla sin él:** al terminar un turno de Chatboo con una imagen adjunta (también cuando el
  proveedor devuelve 429), el hilo del turno se queda esperándose a sí mismo:
  - el cursor del hilo (A) conserva un lock sobre la fila de `chatboo_session` (hipótesis H1: el
    `UPDATE … last_screen_context` de `:556-562`, enviado por A en un flush durante el motor);
  - `_finalize` abre en el mismo hilo otro cursor (B) y se queda esperando ese lock en
    `UPDATE chatboo_session SET input_history=…`;
  - el `rollback` que cerraría A está en el `finally`, después de `_finalize`, en el mismo hilo.

  PostgreSQL no lo detecta como interbloqueo y ningún límite de Odoo afecta al hilo. El job no
  llega a `done`, el navegador sigue esperando y cada recarga (`update_last_used`) ocupa un worker
  hasta dejar Odoo sin servicio.
- **Cambio:** justo antes de cada una de las dos llamadas a `_finalize` (éxito y excepción) se
  llama a `_release_worker_cursor()`. Este método hace `rollback` de A, lo que libera cualquier lock
  que A tenga, venga de la sentencia que venga, y conserva las escrituras ORM pendientes. En Odoo 14,
  `towrite` y `tocompute` son comunes a todos los cursores del hilo (`odoo/api.py:472-475`), y
  `cr.rollback()` los vacía (`api.py:628-635`). Se copian antes y se restauran después, con el
  mismo patrón que `Environment.clear_upon_failure` (`api.py:638-662`), para que las siga guardando
  B, como hoy. En modo test no hace nada (el TestCursor es la transacción del test).
  ```diff
               domain_codes_out = last_domain_codes
               if domain_codes_out is _DOMAIN_CODES_LEAVE and releases_domain_codes:
                   domain_codes_out = []
  +            # Seges: parche de compatibilidad (bloqueo de chatboo_session). Ver docs/pendiente/parches_pns_ai.md
  +            self._release_worker_cursor()
               self._finalize(
  ...
               self._stop_heartbeat(beat)
               beat = None
  +            # Seges: parche de compatibilidad (bloqueo de chatboo_session). Ver docs/pendiente/parches_pns_ai.md
  +            self._release_worker_cursor()
               self._finalize(acc, struct, done_meta, error=str(exc) or exc.__class__.__name__)
  ...
  +    def _release_worker_cursor(self):
  +        """Cierra la transacción del cursor del hilo antes de ``_finalize``. (…)"""
  +        # Seges: parche de compatibilidad (bloqueo de chatboo_session). Ver docs/pendiente/parches_pns_ai.md
  +        if _is_test_mode(self.env):
  +            return
  +        envs = self.env.all
  +        tocompute = {field: set(ids) for field, ids in envs.tocompute.items()}
  +        towrite = {
  +            model: {rid: dict(vals) for rid, vals in id_vals.items()}
  +            for model, id_vals in envs.towrite.items()
  +        }
  +        try:
  +            self.env.cr.rollback()
  +        except Exception:
  +            _logger.warning(
  +                "Chatboo async job %s: could not roll back the worker cursor",
  +                self.id, exc_info=True,
  +            )
  +        envs.tocompute.update(tocompute)
  +        for model, id_vals in towrite.items():
  +            for rid, vals in id_vals.items():
  +                envs.towrite[model][rid].update(vals)
  ```
- **Qué se degrada:**
  - **`last_screen_context` en los turnos con imagen.** Si A ya había enviado ese `UPDATE` a la
    BD, el valor del turno se pierde con el `rollback`, como pasaría hoy con el `rollback` del
    `finally`. Si el turno siguiente llega sin `screen_context`, el motor usa el valor anterior
    guardado en la sesión (`:585-589`). `input_history`, los mensajes, los adjuntos y el resto de lo
    que guarda `_finalize` no cambian. Conservarlo exigiría escribirlo en un cursor corto
    (corrección 1b del análisis, no aplicada).
  - **Turnos de solo texto, 429, cancelación y cron:** el resultado en la BD es el mismo que antes.
    Se descarta lo mismo que descartaba el `rollback` del `finally` y se conserva lo mismo que
    guardaba `_finalize`. El `rollback` del `finally` queda sobre una transacción vacía o de solo
    lectura.
  - **Riesgo residual:** si el lock lo tuviera otro cursor del mismo hilo distinto de A (uno que
    no se cerrara), el parche no lo resolvería. La validación en staging lo mostraría:
    `pg_stat_activity` seguiría con una conexión esperando lock.
- **Cómo comprobar si el fabricante ya lo ha corregido:**
  ```sh
  grep -n "_finalize(\|cr.rollback()\|cr.commit()" pns_ai_chatboo/models/chatboo_async_request.py
  ```
  Está corregido si, sin el parche, en `_process` se cierra la transacción del cursor del hilo
  (`rollback` o `commit`) antes de las llamadas a `_finalize`, o si toda la escritura en la sesión
  durante el turno (incluida la de `last_screen_context`) se hace en cursores cortos que confirman
  en el acto (corrección 1b). En ese caso, este parche sobra. En caso de duda, repite la prueba con
  imagen de la validación.
- **Comprobaciones realizadas (2026-10-16):**
  1. `py_compile` del archivo: correcto con el Python del equipo (3.12.3) y con Python 3.7.3 dentro
     de la imagen `odoo-dev:14` (sin red y con el repo montado en solo lectura).
  2. `grep -rn "Seges: parche de compatibilidad" pns_base pns_ai_mcp pns_ai_chatboo`: las 7 líneas
     de los parches 1-5 y las 3 del parche 6.
  3. **Staging (16/10/2026): validado** con los 5 casos del análisis (§5.1, «Validación del parche
     6»). Desplegado con el commit `63ee2dc` (huella comprobada; `diff -rq` con solo
     `chatboo_async_request.py`).

     | # | Caso | Resultado |
     |---|---|---|
     | 1 | Turno con imagen y proveedor que responde | OK |
     | 2 | Turno con imagen y error del proveedor | OK |
     | 3 | Turno de solo texto | OK |
     | 4 | Cancelación de un turno en curso | OK |
     | 5 | Turno siguiente al de la imagen | OK: recupera el contexto de pantalla |

     En todos: sin conexiones colgadas (ni `idle in transaction` ni esperas de lock) y sin avisos en
     el log. El riesgo residual (lock en otro cursor del hilo) no se dio.

## Parche 7: `ai.fetch.cache.get_cached` y `store` pasan a privados (`_get_cached`, `_store`)

- **Fecha:** 2026-10-20.
- **Estado:** **validado en staging (20/10/2026)**, con el commit `2bb4f51` ([verificación](verificacion_seguridad_pns_ai.md), «Staging — entrega E1»). En LIYBEN se desplegará al terminar el [plan de corrección](plan_correccion_pns_ai.md).
- **PNS:** PNS-90 del [seguimiento](seguimiento_informe_pns_ai.md). Spec: [spec E1](../specs/correcciones_pns_ai_entrega1.md) (entrega E1).
- **Qué falla sin él:** cualquier usuario autenticado (interno o de portal) lee y escribe por RPC (`/web/dataset/call_kw`, `/jsonrpc`, `/xmlrpc/*`) la caché global de `fetch_url`: ambos métodos trabajan en `sudo()` sin comprobar grupo. Se puede envenenar la caché (que el motor sirva un cuerpo falso a todos) o leer respuestas cacheadas.
- **Cambio:** los dos métodos se renombran con `_` (el core rechaza por RPC los nombres privados con `AccessError`) y se actualizan sus 3 llamadores en `controllers/safe_plan.py` (`_execute_fetch_url`). `ai.api.result.cache.get_cached`/`store` (otro modelo, `safe_plan.py:1815` y `:1871`) no se tocan. Se añaden además a `RELAXAICODE_SIDE_EFFECT_METHODS` (`controllers/validators.py`) los nombres nuevos, con su marcador, para que el sandbox de relaxaicode no los alcance (el sandbox deja llamar a métodos con un guion bajo). Diff completo: [spec E1](../specs/correcciones_pns_ai_entrega1.md), §5.4.
- **Qué se degrada:** nada en la interfaz ni en el motor. Un cliente externo que usara la caché por RPC dejaría de poder (no se conoce ninguno). En el sandbox tampoco se pueden usar `res.lang._get_cached` ni `website._get_cached`, que coinciden en el nombre.
- **Cómo comprobar si el fabricante ya lo ha corregido:**
  ```sh
  grep -nE "def _?(get_cached|store)\b" pns_ai_mcp/models/fetch_cache.py
  ```
  Corregido si solo salen `_get_cached`/`_store`, o si `get_cached`/`store` empiezan con
  `ensure_ai_admin`/`has_group`. No confundirlo con `models/api_result_cache.py` (otro modelo).
- **Comprobaciones realizadas (2026-10-20):**
  1. `py_compile` de los archivos cambiados con Python 3.7.3, en la imagen `odoo-dev:14-lab_pns_ai`.
  2. `odoo_lint.py --revisar --base 14.0-pns-ai-3 pns_ai_mcp/`: sin incidencias nuevas (salvo la que
     se indica en la nota general de la entrega E1, más abajo).
  3. `odoo-dev 14 tests pns_ai_mcp` (contexto `lab_pns_ai`): 198 tests, 18 nuevos en verde
     (`test_seges_rpc_access.py`) y el resto igual que la línea base (14 fallos y 31 errores, mismos
     nombres).
  4. `grep` de llamadores del §5.4 de la spec: vacío. `grep -rn "Seges: parche [0-9]* (PNS-" pns_ai_mcp`:
     30 líneas (parche 7: 6; parche 8: 9; parche 9: 7; parche 10: 8).

## Parche 8: `ai.url.whitelist.ensure_domain_whitelisted` pasa a privado (`_ensure_domain_whitelisted`)

- **Fecha:** 2026-10-20.
- **Estado:** **validado en staging (20/10/2026)**, con el commit `2bb4f51` ([verificación](verificacion_seguridad_pns_ai.md), «Staging — entrega E1»). En LIYBEN se desplegará al terminar el [plan de corrección](plan_correccion_pns_ai.md).
- **PNS:** PNS-91 del [seguimiento](seguimiento_informe_pns_ai.md). Spec: [spec E1](../specs/correcciones_pns_ai_entrega1.md) (entrega E1).
- **Qué falla sin él:** cualquier usuario autenticado (también portal) puede añadir dominios a la lista blanca de `fetch_url` o reactivar los archivados por RPC: el método usa `sudo()` sin comprobar grupo, con lo que se salta el ACL (solo AI Administrator escribe).
- **Cambio:** el método se renombra con `_` y se actualizan sus 7 llamadores: `controllers/safe_plan.py` (`_ensure_fetch_url_whitelist`, 2), `models/safe_operation.py` (`_maybe_auto_whitelist`, 2; `action_add_to_whitelist`, 1) y `models/external_server.py` (2). Los llamadores ya deciden la política antes de llamarlo. Se añaden además a `RELAXAICODE_SIDE_EFFECT_METHODS` (`controllers/validators.py`) los nombres nuevos, con su marcador, para que el sandbox de relaxaicode no los alcance (el sandbox deja llamar a métodos con un guion bajo). Diff completo: [spec E1](../specs/correcciones_pns_ai_entrega1.md), §5.4.
- **Qué se degrada:** nada. El AI Administrator sigue gestionando la lista por la interfaz y con el botón «Whitelist». El alta automática con la política `open` y al confirmar no cambia.
- **Cómo comprobar si el fabricante ya lo ha corregido:**
  ```sh
  grep -n "def _\?ensure_domain_whitelisted" pns_ai_mcp/models/url_whitelist.py
  ```
  Corregido si es privado, o si público comprueba `group_ai_admin` (o la política `open` más el
  grupo de URL externa) antes del `sudo()`.
- **Comprobaciones realizadas (2026-10-20):**
  1. `py_compile` de los archivos cambiados con Python 3.7.3, en la imagen `odoo-dev:14-lab_pns_ai`.
  2. `odoo_lint.py --revisar --base 14.0-pns-ai-3 pns_ai_mcp/`: sin incidencias nuevas (salvo la que
     se indica en la nota general de la entrega E1, más abajo).
  3. `odoo-dev 14 tests pns_ai_mcp` (contexto `lab_pns_ai`): 198 tests, 18 nuevos en verde
     (`test_seges_rpc_access.py`) y el resto igual que la línea base (14 fallos y 31 errores, mismos
     nombres).
  4. `grep` de llamadores del §5.4 de la spec: vacío. `grep -rn "Seges: parche [0-9]* (PNS-" pns_ai_mcp`:
     30 líneas (parche 7: 6; parche 8: 9; parche 9: 7; parche 10: 8).

## Parche 9: `ai.skill.param.cache` y `ai.skill`: `remember_for_skill`, `lookup_for_skill`, `remember_param_cache`, `lookup_param_cache` pasan a privados

- **Fecha:** 2026-10-20.
- **Estado:** **validado en staging (20/10/2026)**, con el commit `2bb4f51` ([verificación](verificacion_seguridad_pns_ai.md), «Staging — entrega E1»). En LIYBEN se desplegará al terminar el [plan de corrección](plan_correccion_pns_ai.md).
- **PNS:** PNS-85 del [seguimiento](seguimiento_informe_pns_ai.md). Spec: [spec E1](../specs/correcciones_pns_ai_entrega1.md) (entrega E1).
- **Qué falla sin él:** cualquier usuario autenticado (también portal) escribe por RPC en la caché de parámetros de skills (`remember_*`, con cursor propio de superusuario y commit) o lee sus filas (`lookup_*`, en `sudo()`), sin comprobar grupo ni propiedad de la skill.
- **Cambio:** los cuatro métodos se renombran con `_`; se actualizan la delegación de `ai.skill` a `ai.skill.param.cache` (`models/ai_skill.py`) y las dos referencias por nombre en `utils/agent_engine.py` (`getattr(skill, '_lookup_param_cache', None)` y `'_remember_param_cache'`: si no se actualizaran fallarían en silencio). Se añaden además a `RELAXAICODE_SIDE_EFFECT_METHODS` (`controllers/validators.py`) los nombres nuevos, con su marcador, para que el sandbox de relaxaicode no los alcance (el sandbox deja llamar a métodos con un guion bajo). Diff completo: [spec E1](../specs/correcciones_pns_ai_entrega1.md), §5.4.
- **Qué se degrada:** nada funcional. La caché sigue siendo global por skill y frase, y gana la primera fila (diseño del fabricante). La edición manual por ORM (`param_cache_ids`) no cambia.
- **Cómo comprobar si el fabricante ya lo ha corregido:**
  ```sh
  grep -nE "def _?(remember_for_skill|lookup_for_skill)\b" pns_ai_mcp/models/ai_skill_param_cache.py
  grep -nE "def _?(remember|lookup)_param_cache\b" pns_ai_mcp/models/ai_skill.py
  grep -n "param_cache'" pns_ai_mcp/utils/agent_engine.py
  ```
  Corregido si los cuatro son privados, o si públicos comprueban AI Writer o AI Administrator y la
  lectura de la skill antes del cursor de superusuario.
- **Comprobaciones realizadas (2026-10-20):**
  1. `py_compile` de los archivos cambiados con Python 3.7.3, en la imagen `odoo-dev:14-lab_pns_ai`.
  2. `odoo_lint.py --revisar --base 14.0-pns-ai-3 pns_ai_mcp/`: sin incidencias nuevas (salvo la que
     se indica en la nota general de la entrega E1, más abajo).
  3. `odoo-dev 14 tests pns_ai_mcp` (contexto `lab_pns_ai`): 198 tests, 18 nuevos en verde
     (`test_seges_rpc_access.py`) y el resto igual que la línea base (14 fallos y 31 errores, mismos
     nombres).
  4. `grep` de llamadores del §5.4 de la spec: vacío. `grep -rn "Seges: parche [0-9]* (PNS-" pns_ai_mcp`:
     30 líneas (parche 7: 6; parche 8: 9; parche 9: 7; parche 10: 8).

## Parche 10: `ai.mcp.user.redeem_key_pin` y `ai.key.pin.block.release_all`, `note_failure`, `is_blocked` pasan a privados

- **Fecha:** 2026-10-20.
- **Estado:** **validado en staging (20/10/2026)**, con el commit `2bb4f51` ([verificación](verificacion_seguridad_pns_ai.md), «Staging — entrega E1»). En LIYBEN se desplegará al terminar el [plan de corrección](plan_correccion_pns_ai.md).
- **PNS:** PNS-83 del [seguimiento](seguimiento_informe_pns_ai.md). Spec: [spec E1](../specs/correcciones_pns_ai_entrega1.md) (entrega E1).
- **Qué falla sin él:** cualquier usuario autenticado (también portal) puede canjear un PIN de clave API por RPC con la IP que indique (`redeem_key_pin`, `sudo`), bloquear la IP que quiera (`note_failure`, denegación de servicio), consultar el estado de cualquier IP (`is_blocked`) o levantar todos los bloqueos (`release_all`).
- **Cambio:** los cuatro métodos se renombran con `_`; se actualizan `models/mcp_user.py` (2 llamadas), `models/key_pin_block.py` (1 llamada interna) y `models/res_config_settings.py` (`action_key_pin_release`, que sigue público y comprueba `ensure_ai_admin`). `redeem_key_pin` no tenía llamador. Se añaden además a `RELAXAICODE_SIDE_EFFECT_METHODS` (`controllers/validators.py`) los nombres nuevos, con su marcador, para que el sandbox de relaxaicode no los alcance (el sandbox deja llamar a métodos con un guion bajo). Diff completo: [spec E1](../specs/correcciones_pns_ai_entrega1.md), §5.4.
- **Qué se degrada:** el canje de PIN se queda sin ningún punto de entrada (no tenía llamador; encaja con N4 a: no usar la mesa de entrega). El botón «Release PIN blocks» sigue funcionando.
- **Cómo comprobar si el fabricante ya lo ha corregido:**
  ```sh
  grep -nE "def _?(redeem_key_pin|consume_key_pin)\b" pns_ai_mcp/models/mcp_user.py
  grep -nE "def _?(release_all|note_failure|is_blocked)\b" pns_ai_mcp/models/key_pin_block.py
  ```
  Corregido si son privados, o si el canje pasa a un controlador que toma la IP de la petición y no
  del llamador, y `release_all` comprueba `ensure_ai_admin`.
- **Comprobaciones realizadas (2026-10-20):**
  1. `py_compile` de los archivos cambiados con Python 3.7.3, en la imagen `odoo-dev:14-lab_pns_ai`.
  2. `odoo_lint.py --revisar --base 14.0-pns-ai-3 pns_ai_mcp/`: sin incidencias nuevas (salvo la que
     se indica en la nota general de la entrega E1, más abajo).
  3. `odoo-dev 14 tests pns_ai_mcp` (contexto `lab_pns_ai`): 198 tests, 18 nuevos en verde
     (`test_seges_rpc_access.py`) y el resto igual que la línea base (14 fallos y 31 errores, mismos
     nombres).
  4. `grep` de llamadores del §5.4 de la spec: vacío. `grep -rn "Seges: parche [0-9]* (PNS-" pns_ai_mcp`:
     30 líneas (parche 7: 6; parche 8: 9; parche 9: 7; parche 10: 8).

### Notas de la entrega E1 (parches 7 a 10)

- **Lista del sandbox:** `controllers/validators.py` lleva un bloque con marcador por parche dentro
  de `RELAXAICODE_SIDE_EFFECT_METHODS`. Vigilancia: si el fabricante bloquea de forma general los
  métodos con `_` en `guarded_getattr` y en el AST, esa parte sobra:
  ```sh
  grep -n "RELAXAICODE_SIDE_EFFECT_METHODS\|startswith('_')" pns_ai_mcp/controllers/validators.py pns_ai_mcp/controllers/context_builder.py
  ```
- **Hueco que no cierra E1:** el alias sin llamada (`f = m._metodo; f()`) sigue sin bloquearse, como con
  los 15 nombres previos; queda para E3 (D-2).
- **Lint:** el renombrado de `_redeem_key_pin` marca como «nueva» una incidencia ya existente de esa
  línea de `def` (`R0911 too-many-return-statements`, 8/6). Es el mismo método y no se refactoriza.
- **Test de la caché de parámetros:** `test_skill_param_cache_roundtrip` fuerza `_own_cursor_env` a
  `False`, porque `TransactionCase` de Odoo 14 usa un cursor real y la escritura haría commit en un
  cursor propio.
- **Test de control:** `test_control_session_ok` usa `res.users.context_get` (cambio aprobado
  respecto al §9.1 de la spec, que proponía `is_domain_whitelisted`).
- **Pruebas:** `odoo-dev 14 tests pns_ai_mcp` en el contexto `lab_pns_ai`: 198 tests. Resultado: 148
  pasados, 5 saltados, 14 fallidos y 31 errores (línea base 130/5/14/31 más los 18 tests nuevos).

- **Staging (20/10/2026):** validados los cuatro parches con el commit `2bb4f51`: pruebas 1 a 6 de
  seguridad CORREGIDO (también con portal y por `/jsonrpc`) y no regresión R1 a R7 con Gemini. Detalle
  en la [verificación](verificacion_seguridad_pns_ai.md), «Staging — entrega E1».

## Parche 11: `chatboo.session`: el flujo de chips de descarga pasa a privado y solo engancha adjuntos del dueño (PNS-82)

- **Fecha:** 2026-10-20.
- **Estado:** **validado en staging (21/10/2026)**, con el commit `792481c` ([verificación](verificacion_seguridad_pns_ai.md), «Staging — entrega E2»). En LIYBEN se desplegará al terminar el [plan de corrección](plan_correccion_pns_ai.md).
- **PNS:** PNS-82 del [seguimiento](seguimiento_informe_pns_ai.md). Spec: [spec E2](../specs/correcciones_pns_ai_entrega2.md) (entrega E2).
- **Qué falla sin él:** `claim_turn_file_chips` (y `apply_`/`stage_`/`consume_*_chips`) engancha en `sudo` a una sesión cualquier adjunto huérfano (sin `res_model` o sin `res_id`), sea de quien sea, incluidas las copias de configuración exportadas por un administrador. Después `/pns_ai_mcp/session_file` y `/web/content` lo sirven, y el borrado de la sesión lo borra. Se podía hacer por RPC directo (también con portal) o, sin método público, con el búfer `staged_assistant_files` más `request_cancel`.
- **Cambio:**
  - `models/chatboo_session.py`: los cuatro métodos se renombran con `_` (`_claim_turn_file_chips`, `_apply_assistant_download_chips`, `_stage_assistant_download_chips`, `_consume_staged_assistant_download_chips`) y se actualizan sus llamadores. `_claim_turn_file_chips` no hace nada si la sesión no es del usuario real (`self.env.uid`, que en `sudo` sigue siendo el real) y solo engancha adjuntos con `create_uid` igual a ese usuario. `unlink` comprueba `check_access_rights` y `check_access_rule('unlink')` antes de borrar en `sudo`, y de los adjuntos colgados solo borra los creados por el dueño de la sesión (o sin `create_uid`); los demás se desenganchan (`res_model` y `res_id` a `False`).
  - `models/chatboo_async_request.py`: tres llamadores actualizados (`_persist_turn_files`, `_save_to_session` y su consumo del búfer).
  - `controllers/validators.py` (`pns_ai_mcp`): los nombres nuevos se añaden a `RELAXAICODE_SIDE_EFFECT_METHODS`, con su marcador.
  - Diff completo: [spec E2](../specs/correcciones_pns_ai_entrega2.md), §5.5.
- **Qué se degrada:** un adjunto creado por un usuario distinto del dueño de la sesión ya no se engancha a ella (los flujos actuales no lo hacen). Al borrar una sesión, los adjuntos ajenos que colgaran de ella se desenganchan en vez de borrarse y quedan como huérfanos de su creador. Cuatro nombres más en la lista negra del sandbox.
- **Cómo comprobar si el fabricante ya lo ha corregido:**
  ```sh
  grep -nE "def _?(claim_turn_file_chips|apply_assistant_download_chips|stage_assistant_download_chips|consume_staged_assistant_download_chips)\b" pns_ai_chatboo/models/chatboo_session.py
  grep -n "create_uid\|check_access_rule" pns_ai_chatboo/models/chatboo_session.py
  ```
  Corregido si `claim` (público o privado) compara el `create_uid` del adjunto con el usuario real y
  comprueba que la sesión es suya antes de escribir en `sudo`, y el `unlink` no borra en `sudo`
  adjuntos de otros creadores. No basta con que los métodos sean privados (búfer y `request_cancel`).
- **Comprobaciones realizadas (2026-10-20):**
  1. `py_compile` de los archivos cambiados y nuevos con Python 3.7.3, en la imagen `odoo-dev:14-lab_pns_ai`.
  2. `odoo_lint.py --revisar --base 14.0-pns-ai-3 pns_ai_mcp/ pns_ai_chatboo/`: sin incidencias nuevas
     (salvo la R0911 de `mcp_user.py` ya aceptada en E1).
  3. `odoo-dev 14 tests pns_ai_chatboo` (contexto `lab_pns_ai`): 15 tests nuevos
     (`test_seges_chatboo_access.py`, incluido `test_cron_unlink_sudo_keeps_foreign`), todos en verde. Con el filtro de dueño/creador y el de `unlink`
     neutralizados temporalmente, 4 de ellos fallan (comprobado y restaurado).
  4. `odoo-dev 14 tests pns_ai_mcp`: 205 tests, sin cambios en los fallos de la línea base (ver parche 12).
  5. `grep` de llamadores del §5.5 de la spec: vacío. `grep -rn "Seges: parche 1[12] (PNS-" pns_ai_mcp pns_ai_chatboo`:
     20 líneas (parche 11: 15; parche 12: 5).
- **Staging (21/10/2026):** PNS-82 CORREGIDO por RPC directo (interno y portal), por la vía del búfer
  con `request_cancel` y en la descarga; al borrar una sesión, el adjunto propio se borra y el ajeno
  enganchado (simulado por SQL) se desengancha y su creador lo sigue descargando. Sin regresión en las
  descargas del chat. Los adjuntos del PDF, el Word, el clip y el SVG quedan huérfanos por causas del
  fabricante, no de este parche (PNS-98 del [seguimiento](seguimiento_informe_pns_ai.md)).

## Parche 12: `ai.system.action`: dar o quitar grupos nativos exige `base.group_system` (PNS-01 y PNS-02, resto)

- **Fecha:** 2026-10-20.
- **Estado:** **validado en staging (21/10/2026)**, con el commit `792481c` ([verificación](verificacion_seguridad_pns_ai.md), «Staging — entrega E2»). En LIYBEN se desplegará al terminar el [plan de corrección](plan_correccion_pns_ai.md).
- **PNS:** PNS-01 y PNS-02 (resto común) del [seguimiento](seguimiento_informe_pns_ai.md). Un solo parche para los dos (misma causa y mismo archivo; excepción a «un parche por PNS» aprobada, D-11 de la spec). Spec: [spec E2](../specs/correcciones_pns_ai_entrega2.md) (entrega E2).
- **Qué falla sin él:** `user.add_group` y `user.remove_group` solo exigen `group_ai_admin`, y `_apply_user_add_group` / `_apply_user_remove_group` resuelven y escriben en `sudo`. Un AI Administrator sin Ajustes se puede dar `base.group_system` (o quitárselo a un administrador) con un plan que él mismo confirma.
- **Cambio:** método nuevo `_check_may_change_user_groups()` en `models/ai_system_action.py` (superusuario o `has_group('base.group_system')` sobre `self.env.user`, y si no `UserError`), llamado al principio de `_preview_user_add_group`, `_apply_user_add_group`, `_preview_user_remove_group` y `_apply_user_remove_group`, antes de resolver usuario y grupo en `sudo`. La comprobación va en Python (no en `data/trusted_actions_system.xml`: el AI Administrator edita `ai.trusted.action` y `group_ids` significa «al menos uno»). Diff completo: [spec E2](../specs/correcciones_pns_ai_entrega2.md), §5.5.
- **Qué se degrada:** un AI Administrator sin Ajustes ya no puede dar ni quitar ningún grupo por un plan, tampoco los de IA (para esos tiene los indicadores de `ai.mcp.user`). El mensaje nuevo («Only a Settings administrator can add or remove user groups.») sale en inglés sin traducir (no se toca `i18n`, D-6). El prompt del sistema no cambia (D-7). `view.*` y `field_required` no cambian.
- **Cómo comprobar si el fabricante ya lo ha corregido:**
  ```sh
  grep -nE "group_system|_is_system|is_system\(\)" pns_ai_mcp/models/ai_system_action.py pns_ai_mcp/models/ai_trusted_action.py
  grep -n "group_system" pns_ai_mcp/data/trusted_actions_system.xml
  ```
  Corregido si `_apply_user_add_group` / `_apply_user_remove_group` (o `_resolve_user`) comprueban
  `base.group_system` sobre `self.env.user` antes del `sudo()`. No vale añadir `base.group_system` a
  `group_ids` en el XML ni `self.env.is_system()` (es `True` en `sudo`).
- **Comprobaciones realizadas (2026-10-20):**
  1. `py_compile` de los archivos cambiados y nuevos con Python 3.7.3, en la imagen `odoo-dev:14-lab_pns_ai`.
  2. `odoo_lint.py --revisar --base 14.0-pns-ai-3 pns_ai_mcp/ pns_ai_chatboo/`: sin incidencias nuevas
     (salvo la R0911 de `mcp_user.py` ya aceptada en E1).
  3. `odoo-dev 14 tests pns_ai_mcp` (contexto `lab_pns_ai`): 205 tests, 7 nuevos en verde
     (`test_seges_user_groups.py`) y el resto igual que la línea base: 155 pasados, 5 saltados, 14
     fallidos y 31 errores, con los mismos nombres. `test_user_group_preview` sigue igual.
  4. `grep -rn "_check_may_change_user_groups" pns_ai_mcp --include=*.py` (sin tests): 5 líneas.
     `grep -rn "Seges: parche [0-9]* (PNS-" pns_ai_mcp`: 36 líneas; en `pns_ai_chatboo`: 14.
- **Staging (21/10/2026):** un AI Administrator sin Ajustes es rechazado al proponer (por `/mcp`) y al
  confirmar un plan propuesto por `admin`, al dar y al quitar grupos; `admin`, con Ajustes, quita y
  vuelve a poner un grupo; `view.set_field_readonly` sigue disponible sin Ajustes.

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
  sin error de la herramienta: **hecha en staging** (16/10/2026, prueba 1: CORREGIDO);
- una foto de móvil vertical adjunta en Chatboo, que debe llegar derecha al proveedor: **hecha en
  staging** (16/10/2026, prueba 2: CORREGIDO).

Detalle en `verificacion_seguridad_pns_ai.md`, «Staging (15-16/10/2026)».

## Línea base de E0′ sobre 3.1.879 (23/10/2026)

- **Rama:** `14.0-pns-ai-3879`, código del fabricante 3.1.879 sin cambios en los módulos más los tests
  de E0′ ([plan](plan_correccion_pns_ai_3879.md)).
- **Contexto:** `odoo-dev 14` `lab_pns_ai_3879` (imagen `odoo-dev:14-lab_pns_ai_3879`).
- **Referencia:** fase 3, parte 1 (`odoo-dev 14 tests pns_ai_mcp`, log `tests-20261022-164729.log`).
- **Cambios en los tests:**
  - [cambios en tests del fabricante](#cambios-en-tests-del-fabricante);
  - `pns_ai_mcp/tests/test_seges_rpc_access.py` portado y adaptado (18 tests);
  - `pns_ai_chatboo/tests/` nuevo: `common.py` (`SegesChatbooCase`), `test_seges_chatboo_smoke.py`
    (2 tests) y `test_seges_chatboo_access.py` (12 de los 15 tests de E2).

**Comprobaciones:**

1. `py_compile` con Python 3.7.3 en la imagen `odoo-dev:14-lab_pns_ai_3879`, repo montado en solo
   lectura: los 8 archivos tocados, correctos.
2. `python3 ~/.claude/hooks/odoo_lint.py --revisar` sobre los archivos tocados: 0 incidencias nuevas
   (15 preexistentes en los archivos del fabricante, sin tocar).
3. `odoo-dev 14 tests pns_base,pns_ai_mcp,pns_ai_chatboo` (log `tests-20261023-175029.log`): 234 tests,
   17 fallos y 32 errores.

| Módulo | Tests | Fallos | Errores | Saltados | Fase 3, parte 1 |
|---|---|---|---|---|---|
| `pns_base` | 0 (sin `tests/`) | — | — | — | — |
| `pns_ai_mcp` | 220 | 17 | 32 | 3 | 202 · 17 F · 35 E · 5 saltados en el log |
| `pns_ai_chatboo` | 14 | 0 | 0 | 0 | sin tests |

**Diferencias con la fase 3, test a test (`pns_ai_mcp`):**

- **Pasan, antes E (3):** `TestChangeJournal.test_create_write_sequence_and_revert`,
  `TestChangeJournal.test_unlink_archives_then_revert_and_empty_trash` y
  `TestPaapCore.test_paap_i1_a_proposal_changes_nothing_and_hands_out_no_credential` (datos de prueba).
- **Tests nuevos (18):** los de `test_seges_rpc_access.py`, todos en verde.
- **Ya no se saltan (2):** `TestKnowledgeComposition.test_chatboo_mcp_pack_is_imported` y
  `test_default_skill_codes_at_module_includes_empty_agent_codes`. Se saltaban porque `pns_ai_chatboo`
  no estaba instalado (`test_knowledge_composition.py:51` y `:213`); ahora pasan.
- **El resto de fallos y errores (17 F y 32 E):** los mismos tests que en la fase 3. Uno de ellos es
  `TestChangeJournal.test_failed_execute_journals_outside_rollback` (F), que no se arregla con datos de
  prueba (ver el apartado de cambios en tests del fabricante).

La fase 3 anotó 4 saltados; el log de esa ejecución tiene 5 tests distintos con `skipped`.

## Parches de la rama 14.0-pns-ai-3879 (E1′)

- **Fecha:** 23/10/2026. **Entrega:** E1′ del [plan sobre 3.1.879](plan_correccion_pns_ai_3879.md).
- **Propuesta, comprobaciones previas (a) a (e) y decisiones de Sergio:**
  [e1_propuesta_3879.md](e1_propuesta_3879.md).
- **Rutas:** de 3.1.879. Sin tocar `version`, `depends`, `external_dependencies`, `i18n`, `LICENSE` ni
  `NOTICE`. Mensajes nuevos en inglés, sin traducir (D-6).
- **Marcadores:** `grep -rn "Seges: parche 1[0-6] (" pns_ai_mcp pns_ai_chatboo --include=*.py`, sin
  tests: 20 líneas (10: 2; 12: 10; 13: 2; 14: 2; 15: 1; 16: 3).

### Parche 10 adaptado a 3.1.879: `ai.key.pin.ask.collect_pin` pasa a privado (PNS-83)

- **Qué falla sin él:** `collect_pin(pin)` (`models/key_pin_desk.py:193-201`) es público en 3.1.879 y
  no existía en 3.1.782. Lo puede llamar cualquier usuario autenticado, también portal:
  - canjea un PIN sin límite por IP ni grupo;
  - abre un cursor de superusuario y espera 20 s si no hay ninguna pestaña abierta, así que unas
    pocas llamadas en paralelo dejan sin workers al servidor;
  - con el PIN correcto, devuelve la clave en claro.
  Lo que cubría el parche 10 en 3.1.782 ya lo trae el fabricante (§2.2 de la comparación).
- **Cambio:** renombrado a `_collect_pin`; se actualiza su único llamador,
  `_redeem_key_pin` (`models/mcp_user.py:766`). El sandbox lo bloquea por empezar por `_`.
- **Qué se degrada:** nada; no tenía otros llamadores en Python, JS ni XML.
- **Cómo comprobar si el fabricante ya lo ha corregido:**
  ```sh
  grep -nE "def _?collect_pin\b" pns_ai_mcp/models/key_pin_desk.py
  ```
  Corregido si es privado, o si comprueba grupo y bloqueo por IP antes de `_collect`.
- **Tests:** en `test_seges_rpc_access.py`, `test_collect_pin_refused` (interno y portal por RPC) y
  `test_redeem_key_pin_counts_through_collect_pin`; además, entra en `RENAMED` (`test_public_names_gone`)
  y en `test_no_caller_uses_public_names`.

### Parche 12 adaptado a 3.1.879: solo `base.group_system` da o quita grupos con un plan (PNS-01 y PNS-02)

- **Qué falla sin él:** 3.1.879 prohíbe la cúspide a todos (`_resolve_group_below_cusp`,
  `models/ai_system_action.py:700-708`) y deja libre cualquier otro grupo. Un AI Administrator sin
  Ajustes da o quita por un plan cualquier grupo que no sea cúspide, también los de gestión. Por CRUD
  (`crud_cusp_error`, `utils/privilege_cusp.py`), quien pueda escribir en `res.groups` sin Ajustes
  (Permisos de acceso) cambia `users` o `implied_ids` de un grupo normal.
- **Criterio (Sergio, 23/10/2026):** el de Seges, con la cúspide del fabricante dentro.
- **Cambio:**
  - `utils/privilege_cusp.py`, función nueva `settings_admin_error(env)`: exige superusuario o
    `base.group_system` al usuario del entorno. Si el contexto trae `ai_journal_user_id` o
    `ai_journal_confirmed_by_uid` (los pone `execute_plan_now` desde la fila), lo exige también a
    quien propuso y a quien confirmó. Esas claves solo añaden rechazos.
  - `crud_cusp_error` la llama para `res.groups`, después de las comprobaciones de la cúspide del
    fabricante. Cubre la propuesta y la ejecución, con el mismo `PermissionError`.
  - `models/ai_system_action.py`: `_check_may_change_user_groups()` (`UserError`) al principio de
    `_preview_user_add_group`, `_apply_user_add_group`, `_preview_user_remove_group` y
    `_apply_user_remove_group`. Va después de `_resolve_group_below_cusp`, para que la cúspide dé
    primero su mensaje, y antes de la escritura en `sudo`.
- **Qué se degrada:**
  - un AI Administrator sin Ajustes ya no da ni quita ningún grupo por un plan, tampoco los de IA
    (sigue teniendo los indicadores de `ai.mcp.user`);
  - cualquier paso CRUD sobre `res.groups` exige Ajustes, también renombrar un grupo normal.
  - El test del fabricante `test_paap_i7_cusp_roles_out_of_reach_of_an_ai_admin` falla por diseño
    (ver «Cambios en tests del fabricante»).
- **Cómo comprobar si el fabricante ya lo ha corregido:**
  ```sh
  grep -nE "group_system" pns_ai_mcp/models/ai_system_action.py pns_ai_mcp/utils/privilege_cusp.py
  ```
  Corregido si dar o quitar un grupo que no es cúspide, por la acción y por CRUD en `res.groups`,
  exige `base.group_system` a quien ejecuta el plan. No basta la cúspide.
- **Tests:** `pns_ai_mcp/tests/test_seges_user_groups.py`, reescrito con
  `base.group_partner_manager`. 11 tests:
  - rechazo al proponer y al ejecutar, también tras editar el registro de acciones de confianza o
    con `sudo`;
  - quien tiene Ajustes da y quita, pero no la cúspide;
  - identidades del contexto;
  - CRUD en `res.groups`, rechazado sin Ajustes y aceptado con él;
  - acciones de vista sin cambios.

### Parche 13: solo el sistema crea `ai.safe.operation`; `cleanup_stuck_state` pasa a privado (M10)

- **Qué falla sin él (comparación §8.7, M10, Crítica):**
  - `ai.safe.operation` no sobrescribe `create`, y el AI Administrator tiene permiso de crear.
  - Por RPC da de alta una operación ya `confirmed`, con `confirmed_by_uid` y plan a su elección (o
    usa `create_verification`, también público, con otro `user_id`).
  - Después llama a `cleanup_stuck_state`, que la ejecuta y la confirma con la identidad de ese
    usuario. Confirmado en P-8b, también creando un `ir.cron` que corre como el administrador.
- **Comprobaciones previas (23/10/2026):**
  - `create_verification` crea con `self.create`;
  - los únicos que crean operaciones corren como superusuario: `request_safe_plan` con `SUPERUSER_ID`
    y `record_direct_operation` con `request.env(user=SUPERUSER_ID)` (sin llamadores; en Odoo 14,
    uid 1 activa `su`);
  - `cleanup_stuck_state` no tiene llamadores en Python, JS ni XML (tampoco cron).
- **Cambio:** `create` (`@api.model_create_multi`) da `AccessError` si `not self.env.su`, con el mismo
  criterio que el `write` del fabricante. Cierra `create`, `create_verification` y `copy` por RPC.
  `cleanup_stuck_state` pasa a `_cleanup_stuck_state` (decisión de Sergio).
- **Qué se degrada:** nada en los flujos; `cleanup_stuck_state` deja de poder llamarse por RPC.
- **Cómo comprobar si el fabricante ya lo ha corregido:**
  ```sh
  grep -nE "def create\b|def _?cleanup_stuck_state\b" pns_ai_mcp/models/safe_operation.py
  ```
  Corregido si `create` rechaza a quien no es el sistema (o fuerza `status='pending'` y
  `confirmed_by_uid` vacío, y `user_id` igual al usuario real) y la reejecución no es pública.
- **Tests:** `pns_ai_mcp/tests/test_seges_safe_operation.py` (4) y, en `test_seges_rpc_access.py`,
  `test_cleanup_stuck_state_refused` y la entrada en `RENAMED`.

### Parche 14: `ai.context.unlink_retired_from_module` pasa a privado (M13)

- **Qué falla sin él (comparación §8.7, M13, Alta):** el método es nuevo en 3.1.879, `@api.model`, y
  trabaja en `sudo` con `skip_hardcoded_restrictions`. Cualquier usuario autenticado, también
  portal, borra todos los contextos de fábrica de un módulo, `core` incluidos, con la lista de
  códigos que él mismo pasa (P-8a: 53 → 0).
- **Cambio:** renombrado a `_unlink_retired_from_module`; se actualiza su único llamador
  (`models/ai_context_disk.py:745`, dentro de la importación, que exige AI Administrator). El gemelo
  de `ai.skill` no se toca: ya exige superusuario.
- **Qué se degrada:** nada.
- **Cómo comprobar si el fabricante ya lo ha corregido:**
  ```sh
  grep -nE "def _?unlink_retired_from_module\b" pns_ai_mcp/models/ai_context_disk.py
  ```
- **Tests:** en `test_seges_rpc_access.py`, `test_unlink_retired_refused` (interno y portal; el
  recuento de contextos de fábrica no cambia) y la entrada en `RENAMED`.

### Parche 15: métodos públicos con cursor propio, en la lista del sandbox (PNS-07)

- **Qué falla sin él (comparación §3, PNS-07, Crítica):** la Caja A corre en una transacción
  `READ ONLY` con `cr.commit()` bloqueado (`controllers/controller_helpers.py:184-250`). Pero un
  método público que abre un cursor nuevo (`registry.cursor()`, que en Odoo 14 confirma al salir
  del `with`) escribe fuera de ella. El ejemplo es `chatboo.session.fulfill_client_export` →
  `persist_turn_file`. Lo aprovecha el modelo con una inyección de prompt, o una skill en su
  ejecución de prueba.
- **Inventario (comprobación d, 23/10/2026):** análisis AST de los tres módulos (puntos con
  `registry.cursor()`, `commit()`, `_run_on_committed_cursor` y `persist_turn_file`) y de los métodos
  públicos que llegan a ellos, revisado a mano. Entran en la lista los 28 que llegan a un cursor
  propio:
  - **Chatboo:** `fulfill_client_export`, `mark_seen` (`UPDATE` en cursor propio).
  - **Lienzo:** `sandbox_helpers`, `page_url`, `page_html`, `page_edit`, `paint_canvas`
    (`_store_design`, `log_no_page`). El sandbox los usa como funciones sueltas (`page_html(...)`),
    no como atributos: las skills siguen funcionando.
  - **Agentes:** `get_content` y `get_for_agent`, de `ai.agent` (`_persist_cache_isolated`).
  - **Motor (M11 y M12):** `chat_completion`, `log_role_without_provider`, `log_provider_failover`,
    `log_provider_llm_request`, `log_provider_llm_response`, `log_llm_inference` y
    `log_provider_inference` (`_create_log_entry` en cursor propio).
  - **Proveedores y skills:** `test_connection`, `author_param_schema`, `author_param_help` y
    `rewrite_code_for_params` (pasan por el motor).
  - **PIN:** `collect` (`_collect`).
  - **Servidores externos y asistentes:** `action_suggest_detection`, `action_author_params`,
    `action_author_help`, `action_adapt_code`, `action_generate_openapi`, `action_generate` y
    `action_log_generation_usage`.
- **Fuera de la lista, con motivo:**
  - **Ya estaban o ya son privados:** `cleanup_stuck_state`, `execute_plan_now`,
    `action_confirm_and_execute` y `action_execute_plan`; ahora también `collect_pin`.
  - **Solo confirman el cursor del llamador**, que en la Caja A está bloqueado: `cron_maintenance`,
    `request_cancel`, `set_values`, `action_rebuild_cache`, `action_reset_contexts_to_default`,
    `action_restore_contexts_from_module`, `import_agent_zip`, los asistentes de composición e
    importación, y `action_preview` de `pns_base` (`SAVEPOINT`).
  - **Solo leen** en cursor propio: `_is_cancel_requested` y `_job_already_finished`.
  - **Sin cursor propio:** `domain_index_runtime_tail` y `enrich_with_domain_index` llaman al
    proveedor de decisión sin registrar en un cursor propio; `canvas_public_url` y
    `ai.api.server.action_test_connection` tampoco abren cursor. Quedan fuera del criterio.
  - **Sin cadena confirmada:** `action_create_draft` (ejecuta la skill; modelo cerrado en `env[...]`).
- **Ningún código de skill ni de contexto** (`ai/skills`, `ai/contexts`, `data/`) llama a estos
  nombres como atributo. Un nombre marcado lleva a `requires_write` y de ahí a
  `_read_only_response()`: se rechaza y no se ejecuta.
- **Cambio:** los 28 nombres se añaden a `RELAXAICODE_SIDE_EFFECT_METHODS`
  (`controllers/validators_base.py`), en un bloque con marcador. La lista la usan el AST
  (`validators_checks.py:478`) y `guarded_getattr` (`context_builder.py:165`).
- **Qué se degrada:** el código del sandbox no puede llamar a esos métodos como atributo (antes
  escribían fuera de la Caja A). Las funciones del lienzo siguen disponibles como funciones.
- **Cómo comprobar si el fabricante ya lo ha corregido:**
  ```sh
  grep -n "fulfill_client_export\|_run_on_committed_cursor\|caja_a" pns_ai_mcp/controllers/validators_base.py pns_ai_mcp/utils/session_download.py
  ```
  Corregido si los cursores propios se niegan a escribir desde la Caja A (marca en el cursor, no en
  el contexto) o si estos nombres están en su lista.
- **Tests:** `pns_ai_chatboo/tests/test_seges_chatboo_export.py`, `TransactionCase` sin
  `enter_test_mode` ni `HttpCase`:
  - `test_names_in_denylist` y `test_ast_flags_literal_call`, sobre los 28 nombres;
  - `test_control_own_cursor_commits`: control de que `persist_turn_file` confirma en un cursor
    propio;
  - `test_box_a_leaves_no_attachment`: código real en la Caja A (`get_readonly_env` y
    `build_safe_context`) como `base.user_admin`, con el nombre compuesto (`'fulfill_' +
    'client_export'`). Se cuenta desde un cursor nuevo. Con el parche neutralizado: `1 != 0`;
  - `test_fulfill_client_export_claims_own`, portado de E2 (sin efecto de seguridad: comprueba que
    no hay regresión).
  - Lo que se escapa se borra en un cursor propio al terminar.
  - El usuario tiene que estar guardado en la BD: uno creado en la transacción del test no existe
    para el cursor propio, `_run_on_committed_cursor` vuelve al entorno del llamador y el defecto se
    esconde.

### Parche 16: Autorizaciones pide la contraseña; token de la tarjeta solo para el dueño (PNS-54)

- **Qué falla sin él (comparación §3, PNS-54, Crítica):**
  - `action_confirm_and_execute` y su alias `action_execute_plan` son públicos: el dueño o un AI
    Administrator confirman y ejecutan por RPC sin token ni espera.
  - `card_payload(mint_token=True)` genera y rota el token de operaciones ajenas para quien pueda
    leerlas.
- **Cambio:**
  - `@check_identity` de Odoo 14 (`odoo/addons/base/models/res_users.py:97-132`) en
    `action_confirm_and_execute`. Por RPC devuelve el asistente `res.users.identitycheck` y no
    ejecuta; el botón pide la contraseña, que Odoo recuerda 10 minutos.
  - `action_execute_plan` no se toca: llama a `self.action_confirm_and_execute()`, que pasa por el
    decorador (comprobación e; cubierto por el test).
  - `card_payload` solo genera token si `self.user_id == self.env.user`.
- **Decisión de Sergio (23/10/2026):** (a) y (b). La opción (c), pedir la contraseña en la tarjeta del
  chat para `high`, no se aplica. Queda como riesgo aceptado ligado a D29, porque requiere antes un
  XSS en la página del dueño ([decisiones](pns_ai_decisiones.md), D29;
  [seguimiento](seguimiento_informe_pns_ai.md), PNS-54).
- **Qué se degrada:**
  - el botón Confirmar de Autorizaciones pide la contraseña una vez cada 10 minutos;
  - **comprobar en el staging y en LIYBEN** que nadie entra sin contraseña local (OAuth o LDAP):
    `check_identity` valida con `_check_credentials`.
- **Cómo comprobar si el fabricante ya lo ha corregido:**
  ```sh
  grep -nE "check_identity|def action_confirm_and_execute|mint_token and" pns_ai_mcp/models/safe_operation.py
  ```
- **Tests:** `pns_ai_mcp/tests/test_seges_verification.py` (`HttpCase`):
  - `test_confirm_and_execute_requires_identity`: dueño y AI Administrator, los dos métodos por
    `call_kw`; la operación sigue `pending` y el contacto sin tocar;
  - `test_card_payload_mint_only_owner`.

### Línea base de E1′ (23/10/2026)

**Comprobaciones:**

1. `py_compile` con Python 3.7.3 en la imagen `odoo-dev:14-lab_pns_ai_3879`, repo montado en solo
   lectura: los 7 archivos de los módulos, correctos.
2. `python3 ~/.claude/hooks/odoo_lint.py --revisar --base 64d2e4c`: 0 incidencias nuevas y 369
   preexistentes. En los tests, `invalid-commit` y `exec-used` van desactivados en la línea, con su
   motivo: limpieza fuera de la transacción y ejecución como `tool_relaxaicode`.
3. `odoo-dev 14 tests pns_base,pns_ai_mcp,pns_ai_chatboo` (log `tests-20261023-193409.log`): 260 tests,
   18 F y 32 E.

| Módulo | Tests | Fallos | Errores | Saltados | Línea base E0′ |
|---|---|---|---|---|---|
| `pns_base` | 0 (sin `tests/`) | — | — | — | — |
| `pns_ai_mcp` | 241 | 18 | 32 | 3 | 220 · 17 F · 32 E · 3 saltados |
| `pns_ai_chatboo` | 19 | 0 | 0 | 0 | 14 · 0 · 0 |

**Diferencias con E0′, test a test:**

- **Tests nuevos (26), todos en verde:**
  - `test_seges_user_groups.py`: 11;
  - `test_seges_safe_operation.py`: 4;
  - `test_seges_verification.py`: 2;
  - `test_seges_rpc_access.py`: 4 (`test_collect_pin_refused`, `test_unlink_retired_refused`,
    `test_cleanup_stuck_state_refused` y `test_redeem_key_pin_counts_through_collect_pin`);
  - `test_seges_chatboo_export.py`: 5.
- **Pasa a F (1), aceptado por diseño:**
  `TestSystemTrustedActions.test_paap_i7_cusp_roles_out_of_reach_of_an_ai_admin`.
- **Resto:** los 17 F y 32 E de E0′ son los mismos, por nombre. Los 3 saltados también.

**Neutralización (23/10/2026):** los seis parches neutralizados a la vez desde una copia en el
scratchpad, sin git, y restaurados después.
- Resultado (log `tests-20261023-192837.log`): 260 tests, 37 F y 33 E.
- Fallan los 21 tests negativos de E1′, cada uno por su parche:
  - **10:** `test_collect_pin_refused`, `test_redeem_key_pin_counts_through_collect_pin`,
    `test_public_names_gone` y `test_no_caller_uses_public_names`;
  - **12:** 7 de `test_seges_user_groups.py`;
  - **13:** los 3 negativos de `test_seges_safe_operation.py` y `test_cleanup_stuck_state_refused`;
  - **14:** `test_unlink_retired_refused`;
  - **15:** los 3 negativos de `test_seges_chatboo_export.py` (`test_box_a_leaves_no_attachment`:
    `1 != 0`);
  - **16:** los 2 de `test_seges_verification.py`.
- `test_paap_i7` vuelve a pasar.
- La primera neutralización (log `tests-20261023-192506.log`) mostró que cuatro tests caían por otra
  causa, antes de llegar a lo que debían comprobar. Se corrigieron antes de la segunda:
  - dos de M10 no traían `expires_at`, y era la BD, no el parche, la que rechazaba la fila;
  - `_assert_refused` no detectaba una llamada aceptada que devuelve `None`;
  - el test de la Caja A no contaba el adjunto si la llamada fallaba después.
