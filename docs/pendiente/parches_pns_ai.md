# Parches de Seges en los módulos pns_ai

- **Ramas:** `14.0-pns-ai-3` (parches 1 a 6) · `14.0-pns-ai-correcciones` (parches 7 en adelante,
  [plan de corrección](plan_correccion_pns_ai.md)) · desde el 23/10/2026, `14.0-pns-ai-3879` (base
  3.1.879: parches 10 y 12 adaptados y 13 en adelante,
  [plan sobre 3.1.879](plan_correccion_pns_ai_3879.md)); `14.0-pns-ai-correcciones` queda como
  referencia
- **Fecha:** 2026-10-13 (parches 1 a 3) · actualizado el 2026-10-20 (N11 y N12), el 2026-10-21
  (staging de E2), el 2026-10-23 (cambio de base a 3.1.879 y E1′) el 2026-10-26 (staging de E1′) y el 2026-10-27 (repetición de R8; E2′: parches 11 adaptado y 17 a 22) y el 2026-10-29 (E3′: parches 25 a 28)
- **Versión del fabricante, base propia de Seges desde el 20/10/2026 (N12):** `pns_base` 14.0.1.2.32 ·
  `pns_ai_mcp` 14.0.3.1.782 · `pns_ai_chatboo` 14.0.2.1.453
- **Desde el 23/10/2026 (N12, b′), en `14.0-pns-ai-3879`:** `pns_base` 14.0.1.2.47 · `pns_ai_mcp`
  14.0.3.1.879 · `pns_ai_chatboo` 14.0.2.1.538. El staging `pns_demo` está en esta base desde el
  26/10/2026; LIYBEN sigue con 3.1.782 y los parches 1 a 6 hasta recibirlo todo de una vez
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

> **Cambio de base (N12, b′; 22/10/2026, mantenido el 23/10/2026):** Seges cambia **una sola vez** de
> base a 3.1.879, en la rama `14.0-pns-ai-3879`. Solo para este cambio, y como excepción a «los parches
> son permanentes», se retiran los parches 1 a 9 (los cubre el fabricante) y el 10, el 11 y el 12 se
> adaptan con el mismo número ([decisiones](pns_ai_decisiones.md), N12). A partir de ahí la regla de
> arriba sigue igual, con 3.1.879 como base propia: vigilancia de versiones, sin incorporar versiones
> nuevas.

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
| 10 (adaptado) | PNS-83 | seguridad | `pns_ai_mcp/models/key_pin_desk.py`, `pns_ai_mcp/models/mcp_user.py` | E1′ | Validado en staging (26/10/2026) |
| 12 (adaptado) | PNS-01, PNS-02 | seguridad | `pns_ai_mcp/models/ai_system_action.py`, `pns_ai_mcp/utils/privilege_cusp.py` | E1′ | Validado en staging (26/10/2026) |
| 13 | M10 | seguridad | `pns_ai_mcp/models/safe_operation.py` | E1′ | Validado en staging (26/10/2026) |
| 14 | M13 | seguridad | `pns_ai_mcp/models/ai_context_disk.py` | E1′ | Validado en staging (26/10/2026) |
| 15 | PNS-07 | seguridad | `pns_ai_mcp/controllers/validators_base.py` | E1′ | Validado en staging (26/10/2026); R8 (lienzo) no concluyente por el proveedor (27/10/2026): se valida en E3′ |
| 16 | PNS-54 | seguridad | `pns_ai_mcp/models/safe_operation.py` | E1′ | Validado en staging (26/10/2026) |
| 11 (adaptado) | PNS-82 | seguridad | `pns_ai_chatboo/models/chatboo_session.py` | E2′ | Aplicado; tests en verde (27/10/2026) |
| 17 | PNS-37 | seguridad | `pns_ai_mcp/models/ai_change_journal.py`, `pns_ai_mcp/controllers/safe_plan.py` | E2′ | Aplicado; tests en verde (27/10/2026); P-37 y P-37b pendientes |
| 18 | PNS-19 | seguridad | `pns_ai_mcp/models/box_a_guard.py` (nuevo), `pns_ai_mcp/models/__init__.py`, `pns_ai_mcp/controllers/tools_relaxaicode.py`, `pns_ai_chatboo/models/chatboo_session.py` (ventana del lienzo) | E2′ | Aplicado; rechazado en la revisión y corregido (27/10/2026: alias, ids, caché); tests en verde; P-19 pendiente |
| 19 | PNS-17 | seguridad | `pns_ai_mcp/utils/fetch_url_safe.py`, `pns_ai_mcp/utils/mcp_client.py` | E2′ | Aplicado; tests en verde (27/10/2026); P-17 manual pendiente |
| 20 | PNS-70 | compatibilidad | `pns_ai_chatboo/static/src/js/chart.umd.min.js`, `pns_ai_chatboo/static/src/js/chatboo_heavy_libs.js` | E2′ | Aplicado (27/10/2026); sin test Python; P-70 pendiente |
| 21 | PNS-20 | seguridad | `pns_base/models/operation_report_wizard.py` | E2′ | Aplicado; `clear_caches()` tras la revisión; tests en verde (27/10/2026); P-20 repetida pendiente |
| 22 | PNS-100 | seguridad | `pns_ai_mcp/controllers/validators_base.py` | E2′ | Aplicado; tests en verde (27/10/2026) |
| 23 | PNS-101 | seguridad | `pns_ai_mcp/controllers/validators_base.py`, `pns_ai_mcp/controllers/validators.py`, `pns_ai_mcp/controllers/context_builder.py` | E2′ | Aplicado; tests en verde (27/10/2026); P-101 pendiente |
| 25 | M1 | seguridad | `pns_ai_chatboo/models/chatboo_session.py`, `pns_ai_chatboo/models/chatboo_canvas.py` | E3′ | Aplicado; aprobado en revisión (29/10/2026); P-8c pendiente |
| 26 | M2 | seguridad | `pns_ai_chatboo/models/chatboo_session.py`, `pns_ai_chatboo/models/chatboo_canvas.py` | E3′ | Aplicado; aprobado en revisión (29/10/2026); P-8d pendiente |
| 27 | F1 | seguridad | `pns_ai_chatboo/models/chatboo_canvas.py`, `pns_ai_chatboo/controllers/chatboo.py` | E3′ | Aplicado; aprobado en revisión (29/10/2026; el 27 b, rehecho tras B1); P-8e pendiente |
| 28 | D1 | seguridad | `pns_ai_chatboo/models/chatboo_canvas_page.py`, `pns_ai_chatboo/security/security.xml` | E3′ | Aplicado; aprobado en revisión (29/10/2026); P-8h pendiente |

Parches 11 adaptado y 17 a 22 (E2′, 27/10/2026): aplicados, con tests y neutralización hechos; pruebas
manuales del laboratorio pendientes ([lab_e2_3879.md](lab_e2_3879.md)). Tras la revisión del mismo día:
parche 18 corregido, cambio en el 21 y parche 23 nuevo (PNS-101), con tests y neutralización
(«Revisión de E2′ (27/10/2026)», al final de la sección). Entradas más abajo, en «Parches
de la rama 14.0-pns-ai-3879 (E2′)».

Parches 10, 12 y 13 a 16 (E1′): validados en laboratorio el 23/10/2026 y en el staging `pns_demo` el 26/10/2026, con el cambio de base
(commit `0366231`; [staging_e1_3879.md](staging_e1_3879.md) y
[verificación](verificacion_seguridad_pns_ai.md), «Staging — entrega E1′ (26/10/2026)»).

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
- **Staging (26/10/2026):** conforme. Prueba 7 (P-83a): I y P reciben `AttributeError` con
  `collect_pin` y `AccessError` con `_collect_pin`, sin mesa abierta, en menos de 1 s. Prueba 8 (P-83b,
  observación): igual que la referencia del laboratorio ([verificación](verificacion_seguridad_pns_ai.md), «Staging — entrega E1′»).

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
- **Staging (26/10/2026):** conforme. Pruebas 2 (propuesta de AA por `/mcp`), 2b (plan de ADM
  confirmado por AA: rechazo en la ejecución, `cancelled`, T conserva el grupo) y 3 (CRUD en
  `res.groups` con AA-ERP; el control de ADM pasa). R6: con Ajustes, la operación 27 quitó el grupo a T
  y lo registró en el diario ([verificación](verificacion_seguridad_pns_ai.md), «Staging — entrega E1′»).

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
- **Staging (26/10/2026):** conforme. Prueba 1 (P-8b): AA no crea operaciones por `create`,
  `create_verification` ni `copy`, y no llega a `cleanup_stuck_state` ni a `_cleanup_stuck_state`;
  `ai_safe_operation` y C sin cambios ([verificación](verificacion_seguridad_pns_ai.md), «Staging — entrega E1′»).

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
- **Staging (26/10/2026):** conforme. Prueba 6 (P-8a): I y P reciben `AttributeError` y
  `AccessError`; contextos de fábrica, 53 antes y después ([verificación](verificacion_seguridad_pns_ai.md), «Staging — entrega E1′»).

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
- **Colisiones de nombre con otros modelos (comprobación, 26/10/2026):** la lista bloquea por
  nombre, sea cual sea el objeto: en el AST, cualquier llamada `x.<nombre>(...)`
  (`validators_checks.py:484`); en `guarded_getattr`, cualquier `getattr` (`context_builder.py:165`).
  Las llamadas internas de Odoo (`self.get_content()` dentro del ORM) no pasan por el sandbox y no
  se ven afectadas. Búsqueda de `def <nombre>(` para los 28 nombres en `/opt/odoo-src/14.0/odoo`,
  `/opt/odoo-src/14.0/oca`, los demás módulos de este repo y, además, `vertical-instaladores` (sin
  coincidencias):

  | Nombre | Dónde | Modelo | ¿Lo usaría una skill? | Decisión |
  |---|---|---|---|---|
  | `get_content` | OCA `knowledge/document_page_reference` | `document.page` | Poco: renderiza la página con Mako. Para leer, la skill tiene el campo `content_parsed` (lo calcula con `get_content`) o `content` | Aceptar |
  | `test_connection` | OCA `server-tools/upgrade_analysis` | `upgrade.comparison.config` | No: conecta por RPC a otro Odoo con credenciales guardadas | Aceptar (mejor bloqueado) |
  | `test_connection` | `auto_database_backup` (este repo) | `db.backup.configure` | No: abre SFTP/FTP o nube con las credenciales de la copia | Aceptar (mejor bloqueado) |
  | `test_connection` | OCA `l10n-spain/delivery_seur` | ninguno: clase Python `SeurRequest` | No: no se alcanza desde `env`; envía SOAP a SEUR | Aceptar |
  | `action_generate` | OCA `account-invoicing/stock_picking_invoicing` | `stock.invoice.onshipping` (asistente) | No: crea facturas; en la Caja A ya fallaría por solo lectura | Aceptar (mejor bloqueado) |
  | `action_generate` | core `l10n_ph` | `l10n_ph_2307.wizard` (asistente) | No: genera un XLS fiscal de Filipinas | Aceptar |
  | `collect` | core `base/models/ir_ui_view.py:887` | ninguno: función anidada en `_postprocess_on_change` | No se alcanza como atributo | No es colisión |

  Ningún nombre se saca de la lista: las coincidencias son conexiones externas o asistentes que
  escriben (que conviene que sigan bloqueados) o lecturas con alternativa por campo. Si un cliente
  necesitara `document.page.get_content` desde una skill, la salida es leer `content_parsed`, no
  quitar el nombre.
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
- **Staging (26/10/2026):** conforme. Prueba 5 (P-07): U1, por `relaxaicode`, rechazado con el nombre
  literal y con el compuesto; 0 adjuntos nuevos. R3 (Excel y PDF por la vía normal) y R7 (`search_count`)
  conformes. R8 (lienzo) **no concluyente** por el modelo `lite` (PNS-96): se repite el 27/10/2026
  (decisión 3) ([verificación](verificacion_seguridad_pns_ai.md), «Staging — entrega E1′»).
- **Staging, repetición de R8 (27/10/2026):** no concluyente por el proveedor. Gemini 3.6 flash dio 503 y
  3.5 flash, fallo de conexión; tras el failover, `gemini-3.5-flash-lite` afirmó haber creado la página
  y no la creó (sesiones 46 y 47 de U1 con `canvas_rev` = 0; 0 filas nuevas en `chatboo_canvas_page`;
  PNS-96). Sin indicios de un error de Seges. R8 se valida en E3′ (decisión de Sergio del 27/10/2026)
  ([verificación](verificacion_seguridad_pns_ai.md), «Repetición de R8 (27/10/2026)»).

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
- **Comprobación previa al despliegue en LIYBEN (26/10/2026):** consulta de solo lectura en LIYBEN
  (`odoo14_db`). Los dos AI Administrators (`fran.odoo@seges.es` y `sguerrero@liyben.com`) están activos
  y tienen contraseña local, así que `check_identity` no les impide confirmar. **Confirmado
  (26/10/2026):** Sergio confirma que los dos conocen esa contraseña. En `pns_demo`, la misma
  comprobación está en
  [staging_e1_3879.md](staging_e1_3879.md), A.6.
- **Staging (26/10/2026):** conforme. En `pns_demo`, el único AI Administrator activo (`admin`) tiene
  contraseña local (A.6). Pruebas 4 (UW y ADM: `res.users.identitycheck`, la operación sigue `pending`)
  y 4b (sin `confirm_token` para ADM); la 2b pidió la contraseña de AA. R4: la tarjeta del dueño ejecutó
  la operación 21. R5: Autorizaciones pide la contraseña una vez. Los `missing_token`, `bad_token` y el
  error de serialización de la tarjeta son del fabricante, también sin el parche
  ([diagnóstico](diagnostico_r6_staging_e1p.md), 5.2 y 5.3) ([verificación](verificacion_seguridad_pns_ai.md), «Staging — entrega E1′»).

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

### Cómo se validó E1′ en el laboratorio (23/10/2026) y reinicio del servidor web (26/10/2026)

**Validación del 23/10/2026: solo con el ejecutor de tests, en proceso propio.** Sale de los logs del
kit (`~/odoo-dev/14.0/logs`) y de los registros de arriba:
- Ese día solo hay logs `tests-*` (de `tests-20261023-174554.log` a `tests-20261023-193409.log`); ni
  `instalar` ni `actualizar`. El último `actualizar` es del 22/10 (`actualizar-20261022-173831.log`,
  sobre `pns_demo_p9`).
- Cada `odoo-dev 14 tests` corre en un contenedor nuevo (`odoo-dev-14-web-run-…`), con una BD de tests
  nueva (`test_lab_pns_ai_3879_14`) y su propio servicio HTTP. Las llamadas RPC de los tests `HttpCase`
  de E1′ (`TestSegesVerification` y `TestSegesRpcAccess`) van contra ese servicio, con el código del
  momento.
- No consta ninguna prueba por RPC contra el servidor web del laboratorio (`odoo-dev-14-web-1`) ese día.
  Su log no se conserva: el contenedor se recreó el 26/10/2026.

**26/10/2026:** al validar los scripts del staging (`~/staging_e1p`) contra el laboratorio, se detectó
que el servidor web llevaba en marcha desde el 22/10 con código anterior a E1′. Se reinició y las
pruebas de D.1 ([staging_e1_3879.md](staging_e1_3879.md)) por RPC dieron lo esperado.

**Regla para las entregas siguientes:** tras aplicar un parche, reiniciar el contexto del laboratorio
antes de cualquier prueba por RPC contra el servidor web. Los tests de `odoo-dev tests` no lo
necesitan (contenedor nuevo cada vez).

## Parches de la rama 14.0-pns-ai-3879 (E2′)

- **Fecha:** 27/10/2026. **Entrega:** E2′ del [plan sobre 3.1.879](plan_correccion_pns_ai_3879.md).
- **Propuesta, comprobaciones y decisiones de Sergio:** [e2_propuesta_3879.md](e2_propuesta_3879.md),
  «Propuesta final». HEAD de partida del código: `c639fa8`.
- **Rutas:** de 3.1.879 con E1′ y E2′. Sin tocar `version`, `depends`, `external_dependencies`, `i18n`,
  `LICENSE` ni `NOTICE`. Mensajes nuevos en inglés, sin traducir (D-6).
- **Marcadores:**
  `grep -rn "Seges: parche \(11\|1[7-9]\|2[0-3]\) (" pns_base pns_ai_mcp pns_ai_chatboo --include=*.py --include=*.js`,
  sin tests: 36 líneas (11: 2; 17: 5; 18: 7; 19: 3; 20: 4; 21: 6; 22: 1; 23: 8), tras la revisión del
  27/10/2026 (antes, 26). En la librería minificada de
  Chart.js el marcador va como `/* … */` en la cabecera.
- **Pruebas manuales del laboratorio** (preparadas, las ejecuta Sergio): [lab_e2_3879.md](lab_e2_3879.md).

### Comprobaciones previas a implementar (27/10/2026)

Solo lectura (código, core de Odoo 14 de referencia, OCA, `vertical-instaladores` y `SELECT` en
`lab_pns_ai_3879_14`).

1. **(f) Qué lee la caja A.** `build_safe_context` y la serialización (`_link_and_picture_rows`,
   `_present_result`, `_success_response`) solo leen `web.base.url`, que el parche 18 deja legible.
   **Cambió el diseño:** los helpers que `pns_ai_chatboo` publica en el sandbox (`page_url`, `page_edit`) se
   construyen sobre el entorno de la caja A y llaman a `paint_canvas` → `_ask_design` →
   `llm_completion_for_agent(self.env)`, que lee `ai.provider` (cadena del agente y clave del driver); al
   salir, `inference_audit` lo vuelve a leer para registrar el consumo. Con el control independiente de
   `su`, el lienzo pedido desde `relaxaicode` habría fallado en silencio (`paint_canvas` captura el error y
   devuelve `''`). Sergio eligió la **ventana en `_ask_design`** (ver el parche 18). La página «en espera» se
   completa fuera de la caja A (`utils/engine_tool_run.py:393`) y no le afecta.
2. **`auto_join` hacia los modelos cerrados:** ninguno en el core 14, OCA, `vertical-instaladores` ni en
   los tres módulos.
3. **Colisiones de los 28 nombres del parche 22** (`def <nombre>(` en core, OCA, este repo y
   `vertical-instaladores`, sin tests ni migraciones): todas las coincidencias envían, conectan o
   ejecutan. Por ejemplo `send_email` en 5 módulos OCA de `social` (sobrescrituras de `ir.mail_server`),
   `connect` en `fetchmail.server` y en el cliente MCP (clase Python, no alcanzable desde `env`), `send` en
   `mail.mail`, `sms.sms` y TicketBAI/FACe de `l10n-spain`, `run` en 53 sitios (acciones de servidor,
   aprovisionamiento, asistentes contables y de cobro, hilos y CLI fuera del ORM), `send_mail` en
   asistentes del compositor, `method_direct_trigger` en `queue_job_cron`. Ninguna es una lectura sin
   alternativa: no se saca ningún nombre. Ninguno aparece como atributo en `ai/` ni `data/` de los tres
   módulos.
4. **Inventario de PNS-07 reafirmado:** el código de los módulos no cambia desde `ee74c08` (tests de
   E1′). `cursor_scan.py` de E1′, repetido: los mismos 54 métodos públicos; solo desaparecen
   `collect_pin` y `cleanup_stuck_state`, ya privados en E1′.
5. **Parche 21: `precommit` antes del `SAVEPOINT`.** En la petición de «Review» no hay trabajo pendiente
   en `cr.precommit` al entrar en `action_preview`: en Odoo 14 el formulario guarda el asistente en una
   petición aparte (`saveRecord`, `web/static/src/js/views/form/form_controller.js:454-480`) y
   `/web/dataset/call_button` → `_call_kw_multi` (`odoo/api.py:386-392`) solo hace `browse` y llama al
   método. Los asistentes son transitorios sin `mail.thread`. Por eso `precommit.clear()` tras el
   `ROLLBACK` solo descarta lo de la vista previa (`cr.savepoint()` de Odoo, en cambio, hace
   `precommit.run()` antes del `SAVEPOINT`, `odoo/sql_db.py:113-120`).
6. **Parche 18: firmas.** Las de Odoo 14 (`odoo/models.py`): `_fetch_field(field)` (`:3063`),
   `read(fields=None, load='_classic_read')` (`:3006`), `_read(fields)` (`:3087`),
   `_read_group_raw(domain, fields, groupby, offset=0, limit=None, orderby=False, lazy=True)` (`:2286`),
   `_search(args, offset=0, limit=None, order=None, count=False, access_rights_uid=None)` (`:4527`) y
   `ir.config_parameter.get_param(key, default=False)`. Las sobrescrituras del parche pasan
   `*args/**kwargs` a `super()` (`read` usa la firma exacta, como pide pylint-odoo). Las que ya había por
   encima son compatibles: `ai.mcp.user._search(domain, *args, **kwargs)`, tres `read(fields=None,
   load=…)` (`ai.context`, `ai.safe.operation`, `ai.agent`), `res.users._read`, `ir.attachment._read` y
   `mail.message._read_group_raw`, todas con la firma estándar.

### Parche 11 adaptado a 3.1.879: el `unlink` de la sesión no borra adjuntos de otros creadores (PNS-82)

- **Qué falla sin él:** `chatboo.session.unlink` borra en `sudo` todos los adjuntos con
  `res_model='chatboo.session'` de esas sesiones, sean de quien sean, antes de que `super().unlink()`
  compruebe el acceso. Sobre una sesión propia, se lleva adjuntos de otros creadores que cuelguen de
  ella. El cron `_cleanup_old_sessions` pasa por el mismo `unlink`.
- **Cambio** (`pns_ai_chatboo/models/chatboo_session.py`, `unlink`, `:1959`): `check_access_rights` y
  `check_access_rule('unlink')` al principio (el superusuario y el cron pasan); de los adjuntos colgados
  solo se borran los del dueño de cada sesión o sin `create_uid`; el resto se desengancha (`res_model` y
  `res_id` a `False`). Es el cambio del parche 11 original (`14.0-pns-ai-correcciones`), sin el resto del
  parche: el enganche ya lo corrige 3.1.879.
- **Criterio de enganche (decisión 7):** el del fabricante, sin cambios en `_claim_turn_file_chips`: solo
  se enganchan los huérfanos con `res_model` y `res_id` vacíos. Confirmado por el recuento del laboratorio
  y del staging (los únicos con `res_id = 0` son bundles de estáticos del sistema).
- **Qué se degrada:** al borrar una sesión, un adjunto ajeno que colgara de ella queda huérfano de su
  creador en vez de borrarse.
- **Cómo comprobar si el fabricante ya lo ha corregido:**
  ```sh
  grep -n "check_access_rule\|create_uid" pns_ai_chatboo/models/chatboo_session.py
  ```
  Corregido si `unlink` comprueba el acceso antes del borrado en `sudo` y no borra adjuntos de otros
  creadores.
- **Tests:** `pns_ai_chatboo/tests/test_seges_chatboo_access.py`: `test_unlink_own_session_keeps_foreign`
  y `test_cron_unlink_sudo_keeps_foreign` (portados de E2), y el caso (d) de
  `test_claim_filters_in_python` (el adjunto propio con `res_model` y `res_id = 0` no se engancha).

### Parche 17: el diario solo lo escribe el sistema; borrar con un plan exige permiso de borrado (PNS-37)

- **Qué falla sin él (comparación §6.1, PNS-37, Alta propuesta):**
  - (a) `ai.change.journal` solo sobrescribía `unlink`: AI Administrator y Ajustes crean y escriben filas
    por RPC (ACL `1,1,1,0`). Una fila reescrita como borrado en papelera la vacía el cron
    `_cron_empty_journal_trash`, que corre como superusuario.
  - (b) El paso `unlink` de un plan, en un modelo con `active`, archiva con solo permiso de escritura, y
    el cron lo borra pasados los días de retención.
- **Cambio:**
  - `models/ai_change_journal.py`: `create` (`@api.model_create_multi`, `:639`) y `write` (`:647`) dan
    `AccessError` («Only the system can write the AI change journal.») si no es `self.env.su`, como el
    parche 13 en `ai.safe.operation`. Las dos escrituras que corrían como quien pulsa pasan a `sudo()`:
    `action_revert` (`:498`) y `_empty_rows` (`:571`); antes ya se comprueba `_ensure_journal_manager`, y
    el borrado de `_empty_rows` sigue con los permisos de quien pulsa.
  - `controllers/safe_plan.py`, paso `unlink` (`:950`): `check_access_rights('unlink')` y
    `check_access_rule('unlink')` antes de archivar.
  - El cron no se toca; el ACL tampoco (`ir.model.access.csv` no admite el marcador).
- **Inventario de escrituras del diario** (decisión 1; [propuesta](e2_propuesta_3879.md), «PNS-37
  (decisiones 1 y 2)»): solo cambian las vías 6 y 7 (dos `sudo()`); las demás ya escribían como
  superusuario. Un test de no regresión por vía.
- **Qué se degrada:** nadie corrige a mano una fila del diario (no hay botón que lo haga). Un plan de
  borrado sobre un registro que el usuario no puede borrar falla, en vez de archivarlo.
- **Cómo comprobar si el fabricante ya lo ha corregido:**
  ```sh
  grep -n "def create\|def write\|env.su" pns_ai_mcp/models/ai_change_journal.py
  grep -n "check_access_rights('unlink')" pns_ai_mcp/controllers/safe_plan.py
  ```
- **Tests:** `pns_ai_mcp/tests/test_seges_change_journal.py` (11):
  - negativos: `test_ai_admin_write_refused`, `test_ai_admin_create_refused`,
    `test_plan_unlink_requires_unlink_right`;
  - no regresión, por vía del inventario: 1 `test_applied_row_as_ai_writer`, 2 `test_heal_shape_creates_row`,
    6 `test_revert_still_works_for_ai_admin`, 7 `test_empty_one_and_settings_still_work_for_ai_admin`,
    8 `test_cron_empties_old_row`, 9 `test_related_verification_id_recompute`;
  - `TestSegesFailedPlanRow` (cursor propio, sin `enter_test_mode` ni `HttpCase`, `base.user_admin`,
    limpieza en un cursor propio): 3 `test_failed_plan_row_survives_rollback` (decisión 2) y 4
    `test_rejected_plan_journals_failed_row`, que necesita el rechazo de (b) y por eso falla al
    neutralizar.
  - `test_failed_execute_journals_outside_rollback` (fabricante) sigue aceptado como desfasado.

### Parche 18: en la caja A, los modelos de credenciales solo dan sus campos de identificación (PNS-19)

- **Qué falla sin él (comparación §3, PNS-19, Alta):** el sandbox solo cierra la puerta `env[...]`. Los
  recordsets del ORM son los reales: `ai.log.provider_id.api_key`, `env.ref(<agente>)` y su cadena de
  proveedores, `new()` con un many2one, los campos `Reference` del core
  (`mail.template.preview.resource_ref`), `read`, `read_group` y los dominios con camino (oráculo)
  llegan a los secretos, también los de `ir.mail_server` o `ir.config_parameter` si el usuario los
  puede leer.
- **Cambio** (opción B, rediseño por campos; decisiones de la segunda y tercera ronda):
  - `pns_ai_mcp/models/box_a_guard.py` (nuevo; `_inherit = 'base'`, y `_inherit = 'ir.config_parameter'`
    para `get_param`). En `_fetch_field`, `read`, `_read`, `_read_group_raw` y `_search`, primero la marca
    del cursor (fuera de la caja A, `super()` de inmediato) y después el modelo. No mira `su` ni `sudo`.
  - 11 modelos con sus campos permitidos: `ai.provider`, `ai.api.server`, `ir.mail_server` y
    `fetchmail.server` (`id`, `display_name`, `name`); `ai.api.server.key` y `ai.mcp.user` (`…`,
    `user_id`); `ai.key.pin.ask` y `ai.api.key.wizard` (`id`, `display_name`); `ai.key.pin.desk` (solo
    `id`: su `_rec_name` es el token); `iap.account` (`…`, `service_name`); `ir.config_parameter` (`…`,
    `key`, y `value` en lectura solo si todos los ids del recordset son enteros (`int`, no `bool`; de un
    `NewId`, su `origin`) y ninguna de esas filas tiene una clave bloqueada; nunca en un dominio ni en
    `read_group`, ni como campo ni como agregado).
  - Clave bloqueada de `ir.config_parameter`: contiene `secret`, `password`, `passwd`, `token`,
    `api_key`, `apikey` o `private` (incluye `database.secret`). `get_param` la rechaza antes del
    `ormcache` de `_get_param`.
  - `read()` sin campos devuelve solo los permitidos; con campos no permitidos, `AccessError`. La
    precarga de `_fetch_field` va sin `prefetch_fields`: lo que lee la caja A no trae la clave a la
    caché. Eso no basta, porque en Odoo 14 la caché es una por hilo, no por cursor: lo que el motor lee
    con su cursor (`_api_key_for_inference`, la llamada de diseño) la caja A lo recibe sin pasar por
    `_fetch_field`. Por eso se vacía (tercer cierre, abajo).
  - `controllers/tools_relaxaicode.py`: `ro_cr._seges_box_a = True` justo después de abrir la caja A
    (`:187`), seguido de `_box_a_clear_cache(ro_env)`, y `False` en el `finally`, antes del `rollback`
    (`:291`).
  - `models/__init__.py`: importa `box_a_guard`.
  - **Tres cierres tras el rechazo de la revisión (27/10/2026)**, con los scripts del revisor:
    1. **`read_group` con alias.** `'display_name:max(value)'` leía `value` con el nombre de un campo
       permitido. `_read_group_raw` analiza cada campo de `fields` con `models.regex_field_agg`, como el
       core, y comprueba el alias y el campo entre paréntesis (`_agg_field_names`). `value` de
       `ir.config_parameter` se rechaza también como agregado. `groupby` no admite alias en el 14
       (`_read_group_process_groupby` toma la parte anterior a `:` y exige un campo guardado; lo de
       después es la granularidad de fecha): se mantiene `_field_names`. `orderby` solo acepta campos
       agrupados o agregados (`_read_group_prepare`), ya comprobados.
    2. **Ids que no son enteros.** `browse(7.0)`, `browse('7')` y `new(origin=browse(7.0))` llegan a la
       misma fila en SQL, y el filtro anterior (`isinstance(i, int)`) los dejaba fuera de la comprobación
       de claves. `_box_a_blocked_icp_rows` toma el `origin` de cada `NewId` (sin `origin`, no hay fila) y
       trata el recordset como bloqueado si algún id no es exactamente `int`.
    3. **Caché.** `_box_a_clear_cache(env)` invalida en `env.cache` los campos no permitidos de los 11
       modelos y `value` de `ir.config_parameter` (`env.cache.invalidate([(campo, None), …])`; vale para
       todos los entornos del hilo). Se llama al poner la marca (`tools_relaxaicode.py`) y en el `finally`
       de `_box_a_trusted`, al volver a ponerla.
- **Excepción documentada: la ventana del lienzo** (comprobación (f), decisión de Sergio del 27/10/2026).
  - **Motivo:** `page_url` y `page_edit` (helpers de `pns_ai_chatboo` en el sandbox) llaman a la cadena
    de diseño con el entorno de la caja A, que lee `ai.provider`. Sin la ventana, el lienzo desde
    `relaxaicode` dejaría de funcionar (R8, que se valida en E3′).
  - **Cambio:** `pns_ai_chatboo/models/chatboo_session.py`. `_ask_design` (`:1189`) pasa a ser la
    envoltura y el cuerpo original queda sin cambios en `_ask_design_raw` (`:1202`). La envoltura:
    1. convierte a `str` `system`, `prompt` y `what` antes de abrir la ventana (lo demás que usa el cuerpo,
       `mcp_turn` y el agente, sale del contexto del motor, no del sandbox);
    2. abre `_box_a_trusted(self.env)` (`box_a_guard.py`, función privada a nivel de módulo: quita la
       marca y la restaura en `finally`, también si la llamada falla, y vacía de la caché lo que la llamada
       dejó; recibe el entorno, y no el cursor, desde el tercer cierre);
    3. devuelve solo `{'content': str, 'error': str}`: ni el recordset del proveedor ni `usage` salen de la
       ventana. `paint_canvas`, el único llamador, solo usa esas dos claves.
  - `_box_a_trusted` no es alcanzable desde el sandbox: nombre con `_`, fuera de `build_safe_context` y
    de los helpers; `import`, `cr` y los atributos con `_` están bloqueados
    (`test_box_a_cannot_lift_mark`).
  - **Nota para E3′:** al corregir el lienzo (M1, M2 y F1), revisar si la ventana sigue haciendo falta o
    si la llamada de diseño puede salir de la caja A (por ejemplo, como la página «en espera», que se
    completa fuera, en `utils/engine_tool_run.py:393`).
  - **Ventana revisada en E3′ (29/10/2026): se mantiene** (decisión 5 de Sergio;
    [e3_propuesta_3879.md](e3_propuesta_3879.md), I5 y «Propuesta final»). Motivos:
    1. sacar solo `page_url` (con filas) de la caja A no la elimina, porque `page_edit` sin filas la sigue
       necesitando, y cambia el comportamiento (la URL llega al resultado después, las filas serían las del
       resultado y no las que pasó el código);
    2. quitarla del todo exige cambiar el contrato de `fulfill_waiting_page` en `pns_ai_mcp` (ejecutar el
       `fulfill` sin filas) y sustituir los 6 tests de `test_seges_canvas_box_a.py`;
    3. está acotada (texto plano de entrada; solo `content` y `error` de salida; marca restaurada y caché
       vaciada al cerrar) y validada en staging (29/10/2026);
    4. con el parche 26 no da más acceso: las imágenes se leen sin `su` antes de la ventana, que solo
       envuelve la llamada al proveedor.
- **Qué se degrada:** en la caja A no se lee ningún campo de esos modelos salvo los de identificación,
  ni por relación ni en `sudo`. `read()` de otros modelos sigue dando sus many2one como `(id, nombre)`.
  El código interno de Odoo que corra con la marca y necesite otro campo de esos modelos dará
  `AccessError` (la batería completa no ha encontrado ninguno, aparte del lienzo).
- **Observaciones:**
  - `search_by_affinity(model, …, fields=[…])` (helper del sandbox) usa el `env` sin la puerta de catálogos:
    sin el parche, `search_by_affinity('ai.provider', [...], fields=['api_key'])` servía de oráculo de la
    clave. El parche lo cierra (`_search`).
  - El orden (`order='api_key'`) no se filtra: ordenar por la clave entre filas existentes es un oráculo
    muy débil. Para la hoja de E4′.
  - `read_group` sin `fields` usa los campos guardados con `group_operator` (numéricos): en los 11
    modelos, ninguno es una credencial (puertos, temperatura, costes). No se filtra.
  - Desde la caja A se llegaba a `env.cache` y a `env.all` (los entornos reales del hilo): lo cierra el
    parche 23 (PNS-101), no este.
- **Cómo comprobar si el fabricante ya lo ha corregido:**
  ```sh
  grep -rn "_seges_box_a\|box_a" pns_ai_mcp/controllers/tools_relaxaicode.py pns_ai_mcp/models/
  ```
  Corregido si la caja A deja leer solo campos de identificación de los modelos de credenciales por
  cualquier vía (relación, `new()`, `Reference`, `read_group`, dominios), sin depender de `sudo`.
- **Tests:**
  - `pns_ai_mcp/tests/test_seges_sandbox_credentials.py` (31): la marca se pone en el cursor del test y
    `addCleanup` la quita. Desde el 27/10/2026, `_mark()` hace lo mismo que `tool_relaxaicode`
    (`_box_a_clear_cache`) y el `setUp` ya no vacía la caché: llega llena (`create` deja la clave en
    ella). Se lee con `rec.campo` y los negativos comprueban el mensaje («cannot be read from the
    RelaxAICode sandbox»);
    - negativos por vía: `test_env_ref_agent_provider_key`, `test_new_many2one`, `test_reference_field`,
      `test_sudo_does_not_lift`, `test_read_group`, `test_related_field`, `test_search_oracle`,
      `test_prefetch_no_secret`, `test_mail_server_secret`, `test_icp_blocked_key`,
      `test_icp_cached_get_param`, `test_icp_value_search_refused` y `test_provider_read_no_fields`;
    - cierres nuevos: `test_read_group_alias_provider` y `test_read_group_alias_icp` (alias y campo
      agregado), `test_icp_float_id`, `test_icp_str_id` y `test_icp_new_origin` (`origin` entero y
      decimal); controles `test_read_group_alias_allowed` y `test_icp_int_id_allowed_key`;
    - no regresión: `test_gate_env_getitem`, `test_display_name`, `test_log_read_no_fields`,
      `test_log_search_read_no_fields`, `test_message_search_read_no_fields`, `test_icp_allowed_key` y,
      sin marca, `test_outside_box_a_chatboo_reads_provider` (usuario de chat: el motor lee la clave);
    - `TestSegesBoxAReal`, con la herramienta real y la caja A real como `base.user_admin` (Ajustes, sin
      AI Administrator: el secreto es `database.secret`, sin conceder ni confirmar grupos):
      `test_box_a_reference_secret_refused`, `test_box_a_cursor_is_marked`,
      `test_marker_cleared_after_box_a` (código correcto y código que falla),
      `test_box_a_cannot_lift_mark` (importar `_box_a_trusted`, `import odoo`, `env.cr._seges_box_a` y
      `getattr(getattr(env, 'c' + 'r'), '_seges' + '_box_a')`, que cae por el `getattr` compuesto y no
      por un `env.cr` literal; con control positivo) y `test_box_a_engine_cache_before_run` (el motor lee
      la clave con `_api_key_for_inference` en el mismo hilo y después la caja A real la pide por
      `ai.log.new({'provider_id': …})`).
  - `pns_ai_chatboo/tests/test_seges_canvas_box_a.py` (6), la ventana con el driver simulado (lee la
    clave como el real): `test_design_call_reads_provider_in_box_a`, `test_only_design_leaves_the_window`,
    `test_window_takes_plain_strings`, `test_mark_restored_when_design_fails` (el driver falla),
    `test_guard_still_closed_after_window` (desde el 27/10/2026, sin vaciar la caché y con `rec.api_key`
    además de `read`) y `test_cache_closed_after_window_prefetch` (el driver lee otros campos del
    proveedor y la precarga deja la clave en la caché; después de la ventana, `rec.api_key` se rechaza).
    El `setUp` pone la marca como `tool_relaxaicode`, sin vaciar la caché a mano.

### Parche 19: al cambiar de host solo siguen las cabeceras permitidas; el cliente MCP no sigue redirecciones (PNS-17)

- **Qué falla sin él (comparación §3, PNS-17, Alta):** `request_public_http` solo quitaba las cabeceras de
  `_AUTH_HEADER_NAMES` al cambiar de host; la cabecera personalizada del servidor (`auth_header_name`, p.
  ej. `apikey` u `Ocp-Apim-Subscription-Key`) viajaba al host nuevo. El cliente MCP por HTTP
  (`utils/mcp_client.py`) seguía las redirecciones de `requests`, que solo quita `Authorization`.
- **Cambio:**
  - `utils/fetch_url_safe.py` (`:104-119`): `_strip_auth_headers` conserva solo `accept`,
    `accept-language`, `content-type` y `user-agent` (`_CROSS_HOST_HEADER_NAMES`). `_AUTH_HEADER_NAMES`
    queda definida y sin uso.
  - `utils/mcp_client.py`, `_http_post` (`:103-117`): `allow_redirects=False` y, si la respuesta es una
    redirección, `MCPClientError` («MCP server '…' answered with a redirect to …. Set the final URL in
    the server.») (decisión 5).
- **Qué se degrada:** una API que redirige a otro host y espera allí una cabecera propia no la recibe. Un
  servidor MCP con URL que redirige deja de conectar, con ese error. **Antes de LIYBEN:** comprobar que
  sus URLs MCP son las finales ([plan](plan_correccion_pns_ai_3879.md), §3).
- **Cómo comprobar si el fabricante ya lo ha corregido:**
  ```sh
  grep -n "_AUTH_HEADER_NAMES\|_CROSS_HOST_HEADER_NAMES" pns_ai_mcp/utils/fetch_url_safe.py
  grep -n "allow_redirects" pns_ai_mcp/utils/mcp_client.py
  ```
- **Tests:** `pns_ai_mcp/tests/test_seges_fetch_redirect.py` (3, sin red: `requests` y
  `non_public_host_error` sustituidos): `test_custom_auth_header_dropped_on_other_host`,
  `test_same_host_keeps_header` (control) y `test_mcp_client_redirect_refused`.

### Parche 20: Chart.js 4 del chat como `PnsChatbooChart`, sin tocar `window.Chart` (PNS-70)

- **Qué falla sin él:** al abrir el chat, `chart.umd.min.js` (Chart.js 4.4.8) sustituye en `window.Chart`
  a la 2.9.3 de Odoo, que pinta después con la API 4 y opciones de la 2
  ([diagnóstico](pns70_diagnostico_3879.md)).
- **Cambio (decisión 8):**
  - `pns_ai_chatboo/static/src/js/chart.umd.min.js`: **dos** tokens, `.Chart=e()` → `.PnsChatbooChart=e()`
    (cabecera UMD; desplazamiento 584 en 3.1.879) y `window.Chart=An` → `window.PnsChatbooChart=An`
    (fábrica; desplazamiento 206491). Un marcador por token en comentarios `/* … */` aparte, en las dos
    primeras líneas (sin el texto literal de los tokens, para que el `grep` no los cuente). `An.Chart=An`
    no se toca. Original: md5 `45f5b4f17f83d6d21847ec6e14f91674`, 206 553 caracteres.
  - `pns_ai_chatboo/static/src/js/chatboo_heavy_libs.js`: la URL pasa a
    `chart.umd.min.js?seges=20` (`:18`; carga por URL fija con `ajax.loadJS` y una semana de caché de
    `/static`) y `bindEngines` recibe `window.PnsChatbooChart` (`:32`).
- **`grep` de comprobación** (27/10/2026, con el resultado esperado):
  ```sh
  grep -o 'PnsChatbooChart=e()\|window\.PnsChatbooChart=An\|\.Chart=e()\|window\.Chart=An' \
    pns_ai_chatboo/static/src/js/chart.umd.min.js | sort | uniq -c
  #       1 PnsChatbooChart=e()
  #       1 window.PnsChatbooChart=An        (ninguno de los antiguos)
  grep -rn "window\.Chart\b\|chart\.umd\.min\.js" pns_base pns_ai_mcp pns_ai_chatboo --include=*.js --include=*.xml | grep -v "chart.umd.min.js:"
  # pns_ai_chatboo/static/src/js/chatboo_heavy_libs.js:18: …/chart.umd.min.js?seges=20
  ```
- **Qué se degrada:** nada. Una versión nueva de la librería deshace el cambio: se vigila con el `grep`.
- **Cómo comprobar si el fabricante ya lo ha corregido:** el primer `grep` sin `.Chart=e()` ni
  `window.Chart=An` en la librería que traiga, o `chatboo_heavy_libs.js` sin leer `window.Chart`.
- **Tests:** sin test Python (JS de carga diferida). Validación con P-70, casos 1 a 5
  ([lab_e2_3879.md](lab_e2_3879.md), §5).

### Parche 21: «Review» no deja nada escrito (PNS-20)

- **Qué falla sin él (P-20, 27/10/2026, CONFIRMADO):** `action_preview` hace `SAVEPOINT`, importa,
  `ROLLBACK TO SAVEPOINT` e `invalidate_cache()`, que no vacía `towrite`. Lo que la importación deja
  pendiente se vuelca al final de la petición: en usuarios MCP, la etiqueta importada; en proveedores, un
  `UPDATE` de `model_id` con `write_date` nuevo ([propuesta](e2_propuesta_3879.md), «Parche 21: por qué
  los dos asistentes se comportan distinto»).
- **Cambio** (`pns_base/models/operation_report_wizard.py`):
  - `action_preview` (`:314`): `self.env['base'].flush()` antes del `SAVEPOINT` y antes de cada
    `ROLLBACK TO SAVEPOINT`. En el camino normal, el `flush` va dentro del `try`, justo después de la
    importación y antes de `_preview_snapshot()` (cambio del 27/10/2026, tras la revisión): si falla, lo
    recoge el camino de excepción. En ese camino, con `contextlib.suppress` (puede fallar por lo mismo que
    la importación, y el `ROLLBACK` lo deshace; se relanza la excepción original);
  - `_invalidate_after_preview_rollback` (`:292`, se mantiene por si alguien lo hereda; se llama en los dos
    caminos): `cr.precommit.clear()` y `env.clear()`, como `cr.savepoint()`, y desde el 27/10/2026
    `self.env.registry.clear_caches()`: el `ROLLBACK` no deshace el `ormcache`, y `has_group` (y las
    reglas y permisos que dependen de él) seguía dando los grupos que la vista previa había escrito.
  - Comprobación previa: en la petición de «Review» no hay `precommit` pendiente antes del `SAVEPOINT`
    (ver «Comprobaciones previas», 5).
- **Qué no cubre:** lo que la importación confirme en cursores propios o envíe fuera. De los 15 asistentes,
  `bundle_import_wizard` guarda la caché del agente con `_persist_cache_isolated` (cursor propio): hoja de
  E4′.
- **Cómo comprobar si el fabricante ya lo ha corregido:**
  ```sh
  grep -n "flush()\|env.clear()\|precommit" pns_base/models/operation_report_wizard.py
  ```
- **Tests:** `pns_ai_mcp/tests/test_seges_import_preview.py` (4; `pns_base` no tiene `tests/`). El final de
  la petición se simula con un `flush`; un `UPDATE` se detecta por el `ctid` de la fila:
  `test_users_preview_keeps_value`, `test_providers_preview_no_update`, `test_users_preview_keeps_groups`
  (el many2many va directo a la tabla de relación y el `ROLLBACK` ya lo deshacía; desde el 27/10/2026
  comprueba además `self.user.has_group(...)` después de la vista previa, que falla sin
  `clear_caches()`) y `test_import_still_applies` (control).

### Parche 22: métodos con efectos fuera de la BD, en la lista del sandbox (PNS-100)

- **Qué falla sin él (PNS-100, Alta, nuevo):** la caja A frena las escrituras con `READ ONLY`, pero no lo
  que sale a la red o ejecuta otro código sin escribir antes. Cualquier usuario de chat, con una inyección
  de prompt, puede enviar correo a cualquier host (`ir.mail_server.send_email` con `smtp_server`), abrir
  SMTP a cualquier host y puerto (`connect`) o pedir cualquier URL (`ir.qweb.field.image.load_remote_url`);
  con más permisos, ejecutar acciones de servidor y crons (`run`, `method_direct_trigger`).
- **Cambio:** 28 nombres en un bloque nuevo de `RELAXAICODE_SIDE_EFFECT_METHODS`
  (`controllers/validators_base.py:286-316`), que usan el AST y `guarded_getattr`, como el parche 15:
  `send_email`, `connect`, `test_smtp_connection`, `load_remote_url`, `send`, `process_email_queue`,
  `fetch_mail`, `button_confirm_login`, `get_credits`, `autocomplete`, `enrich_company`, `read_by_vat`,
  `start_sync`, `send_letter`, `snailmail_print`, `update_notification`, `install_from_urls`,
  `action_process_edi_web_services`, `get_usd_fx`, `run`, `method_direct_trigger`, `execute_callback`,
  `upgrade_module`, `action_start_automatic_process`, `parent_migration_process_cb`, `send_mail`,
  `message_process` y `message_route`. Origen: barrido de los 47 módulos instalados
  ([propuesta](e2_propuesta_3879.md), «PNS-100: barrido…»). Fuera, con motivo: `update` (bloquearía
  `dict.update`) y `onchange_email` (Gravatar, hoja de E4′).
- **Colisiones de nombre:** ver «Comprobaciones previas», 3. Bloquea también `x.send(...)` de un
  generador, que el sandbox no necesita.
- **Qué se degrada:** el código del sandbox no llama a esos métodos como atributo (antes enviaban o
  ejecutaban fuera de la caja A).
- **Cómo comprobar si el fabricante ya lo ha corregido:**
  ```sh
  grep -n "send_email\|load_remote_url\|method_direct_trigger" pns_ai_mcp/controllers/validators_base.py
  ```
- **Tests:** `pns_ai_mcp/tests/test_seges_sandbox_side_effects.py` (10): `test_names_in_denylist` y
  `test_ast_flags_literal_call` (los 28), y la herramienta real como `base.user_admin` (sin AI
  Administrator en una BD nueva), con el método de cada vía sustituido en la clase del registro para ver
  si se llega a llamar, y `smtplib.SMTP` y `requests.get` sustituidos: `test_box_a_send_email_refused`,
  `test_box_a_connect_refused`, `test_box_a_load_remote_url_refused`,
  `test_box_a_server_action_run_refused`, `test_box_a_cron_trigger_refused`,
  `test_box_a_mail_queue_refused` (`process_email_queue` y `send`), `test_box_a_iap_refused`
  (`get_credits` y `read_by_vat`) y `test_box_a_module_from_urls_refused`.

### Parche 23: el `env` de la caja A no lleva a los entornos reales del hilo (PNS-101)

- **Qué falla sin él (PNS-101, nuevo; gravedad propuesta Crítica, la decide Sergio):** en Odoo 14 la caché
  y el conjunto de entornos son uno por hilo (`api.Environments`: `env.cache`, `env.all`, `envs`), y la
  caja A abre su cursor en el mismo hilo que la petición. `GuardedSandboxEnv.__getattr__` daba cualquier
  atributo público del entorno, y ni el AST ni `guarded_getattr` bloqueaban `cache` ni `all`. Desde el
  sandbox, `env.all` da los `Environment` reales: el del cursor de la petición (sin la marca del parche 18,
  sin `READ ONLY`, con commit al final) y otros con `su=True`; `env.cache.get(...)` da lo que cualquiera de
  ellos leyó; `env.all.towrite` es el diccionario de escrituras pendientes del hilo. Reproducción de solo
  lectura con la caja A real como `base.user_admin` (27/10/2026, en `lab_pns_ai_3879_14`, con rollback):
  desde el entorno del cursor principal se lee `database.secret`; `env.cache.get` lo devuelve si el motor
  lo leyó antes; `towrite` es alcanzable (no se escribió en él) ([propuesta](e2_propuesta_3879.md),
  «Revisión del parche 18 y PNS-101»).
- **Cambio** (opción A, decisión de Sergio del 27/10/2026):
  - `controllers/validators_base.py`: `RELAXAICODE_ENV_STATE_ATTRS` (`cache`, `all`, `envs`, `towrite`,
    `tocompute`, `protected`) y su mensaje (`:338-345`).
  - `controllers/validators.py` (`:307`): el AST los rechaza como **atributo** (`ast.Attribute`), nunca
    como nombre: `all([...])` y una variable `cache` siguen funcionando.
  - `controllers/context_builder.py`: `guarded_getattr` (`:178`) los rechaza al correr, y con él
    `attrgetter` y `methodcaller`, que pasan por la misma función. `GuardedSandboxEnv` (`:90` y `:129`) da
    solo una lista de atributos y rechaza el resto: `uid`, `su`, `user`, `company`, `companies`, `context`,
    `lang`, `ref`, `is_superuser`, `is_admin`, `is_system`, `with_context` y `with_company` para el código
    del sandbox; `cr` y `registry` para el motor, que recibe este mismo envoltorio después de la ejecución
    (`relaxaicode_render._t` usa `rcx['env'].cr`; `relaxaicode_replies._keyerror_missing_model_response`,
    `getattr(env, 'registry', None)`), y que el código del sandbox no puede nombrar (el AST y
    `guarded_getattr` rechazan `cr` y `registry`). `__getitem__`, `get`, `__contains__` y `__call__`
    siguen como estaban.
- **Inventario de atributos del `env` usados por el código legítimo** (antes de fijar la lista):
  - `ai/` y `data/` de `pns_base`, `pns_ai_mcp` y `pns_ai_chatboo`: `env.company` (10) y `env.user` (3), en
    las skills de `pns_ai_chatboo/ai/skills/system/`; `env.registry` y `env.pool` solo en el texto de la regla
    que los prohíbe (`system_prompt.xml:86`).
  - Código del motor que inyecta o recibe el `env` del sandbox: `build_safe_context` y sus helpers usan el
    entorno real, no el envoltorio. Reciben el envoltorio `render_context_from_env` y `_t`
    (`user`, `lang`, `context`, `cr`), `presentation_mode` (`context`), `engine_params.xlsx_float_decimals`
    (`company`), `_largest_image_url` y `_related_models_from_code` (`in` y `[...]`),
    `_keyerror_missing_model_response` (`registry`), y `relaxaicode_models` (`_name` e `ids` como sondas con
    `hasattr`, que ya daban `AttributeError`).
  - Helpers de módulos (`sandbox_helpers`, solo `chatboo.session`): entorno real, sin el envoltorio.
  - Tests de fábrica del sandbox (`test_relaxaicode_*`): `env.cr` y `env.sudo` como negativos, `env.user`.
  - Inventario dinámico: los tests de los tres módulos con un registro temporal en `__getattr__` (retirado):
    `user`, `context`, `_name` e `ids`.
  - Fuera de la lista, sin uso legítimo encontrado: `values` e `items` (darían todos los modelos sin la
    puerta de catálogos), `clear`, `protecting`, `add_to_compute`, `args`, `uid_origin`…
- **Qué se degrada:** `x.cache`, `x.all`, `x.envs`, `x.towrite`, `x.tocompute` y `x.protected` no se pueden
  usar como atributo de ningún objeto en el sandbox; único campo afectado en el core, `pos.cache.cache`
  (binario del TPV). `env.<otro>` fuera de la lista da `AttributeError` con un mensaje propio.
- **Cómo comprobar si el fabricante ya lo ha corregido:**
  ```sh
  grep -n "cache\|'all'" pns_ai_mcp/controllers/validators_base.py pns_ai_mcp/controllers/context_builder.py
  ```
  Corregido si desde `relaxaicode` no se llega a `env.cache`, `env.all` ni `Environment.envs`.
- **Tests:**
  - `pns_ai_mcp/tests/test_seges_sandbox_env.py` (13), con la herramienta real como `base.user_admin`:
    negativos `test_env_cache`, `test_env_cache_get_warm` (con la caché caliente por el motor),
    `test_env_all`, `test_alias_all` (`x = env; x.all`), `test_state_attrs`, `test_composite_getattr`,
    `test_attrgetter`, `test_walk_to_other_environment` y `test_wrapper_allowlist`; positivos
    `test_builtin_all_and_cache_name` (`all([...])` y una variable `cache`), `test_allowed_attrs` y
    `test_engine_attrs_on_wrapper` (`cr` y `registry` para el motor).
  - `pns_ai_chatboo/tests/test_seges_skill_env.py` (1): la skill de fábrica `customer_360.py` (`env.user`,
    `env.company`, `env['res.partner']`, `'modelo' in env`) corre en la caja A real sin error. Sin cliente:
    con uno, falla en esta BD por un error propio de la skill (`_iso` recibe una fecha como `str`), ajeno
    al parche.

### Línea base de E2′ (27/10/2026)

**Comprobaciones:**

1. `py_compile` con Python 3.7.3 en la imagen `odoo-dev:14-lab_pns_ai_3879`, repo montado en solo lectura:
   los 19 `.py` tocados o nuevos, correctos.
2. `python3 ~/.claude/hooks/odoo_lint.py --revisar --base c639fa8 pns_base/ pns_ai_mcp/ pns_ai_chatboo/`:
   0 incidencias nuevas y 530 preexistentes. En los tests, `invalid-commit` va desactivado en la línea
   (limpieza fuera de la transacción).
3. `odoo-dev 14 tests pns_base,pns_ai_mcp,pns_ai_chatboo` (log `tests-20261027-124454.log`): 319 tests,
   18 F y 32 E.

| Módulo | Tests | Fallos | Errores | Saltados | Línea base E1′ |
|---|---|---|---|---|---|
| `pns_base` | 0 (sin `tests/`) | — | — | — | — |
| `pns_ai_mcp` | 293 | 18 | 32 | 3 | 241 · 18 F · 32 E · 3 saltados |
| `pns_ai_chatboo` | 26 | 0 | 0 | 0 | 19 · 0 · 0 |

**Diferencias con E1′, test a test:**
- **Tests nuevos (59), todos en verde:** `test_seges_change_journal.py` 11, `test_seges_sandbox_credentials.py`
  24, `test_seges_fetch_redirect.py` 3, `test_seges_import_preview.py` 4,
  `test_seges_sandbox_side_effects.py` 10, `test_seges_canvas_box_a.py` 5 y, en
  `test_seges_chatboo_access.py`, los 2 de `unlink`. El caso (d) de `test_claim_filters_in_python` se
  amplía (no es un test nuevo).
- **Resto:** los 18 F y 32 E de E1′ son los mismos, por nombre. Los 3 saltados también.
- Una primera ejecución (log `tests-20261027-124149.log`) dio 9 F más, todos de tests nuevos de caja A
  real: el test buscaba `"requires_write": true` en el JSON escapado y `ERROR (` en errores de ejecución,
  que llegan como `"isError": true`. Corregida la comprobación del test, no el código.

**Neutralización (27/10/2026):** cada parche retirado desde una copia en el scratchpad, sin git, y
restaurado después; el `git diff` final es idéntico al de antes (mismo md5).

| Ejecución | Parches retirados | Log | Resultado | Fallan (nuevos) |
|---|---|---|---|---|
| N1 | 11, 17, 18 (guardián: `_in_box_a` siempre falso), 19, 21 y 22 | `tests-20261027-124735.log` | 319 · 55 F · 32 E | 37, ver abajo; los 50 aceptados, iguales |
| N2 | 18, ventana (`_box_a_trusted` no quita la marca) | `tests-20261027-125017.log` (solo Chatboo) | 26 · 0 F · 4 E | `test_design_call_reads_provider_in_box_a`, `test_only_design_leaves_the_window`, `test_window_takes_plain_strings`, `test_guard_still_closed_after_window`: la llamada de diseño da `AccessError` |
| N3 | 18, conversión a `str` y filtrado de la salida | `tests-20261027-125158.log` (solo Chatboo) | 26 · 2 F | `test_window_takes_plain_strings`, `test_only_design_leaves_the_window` |
| N4 | 18, `finally` de la ventana | `tests-20261027-125349.log` (solo Chatboo) | 26 · 1 F | `test_mark_restored_when_design_fails` |
| — | 20 | — | Manual | Caso 1 de P-70 con la librería original ([lab_e2_3879.md](lab_e2_3879.md), §5) |

En N1 fallan, por parche:
- **11:** `test_unlink_own_session_keeps_foreign`, `test_cron_unlink_sudo_keeps_foreign`.
- **17:** `test_ai_admin_write_refused`, `test_ai_admin_create_refused`,
  `test_plan_unlink_requires_unlink_right` y `test_rejected_plan_journals_failed_row` (depende del rechazo
  de (b)).
- **18:** 13 de `TestSegesSandboxCredentials` (los negativos y `test_provider_read_no_fields`: sin el
  parche, `read()` devuelve todos los campos), `test_box_a_reference_secret_refused`,
  `test_box_a_cursor_is_marked`, y en Chatboo `test_guard_still_closed_after_window` y
  `test_design_call_reads_provider_in_box_a` (con el guardián apagado, la ventana no ve marca que quitar:
  efecto de la neutralización; la ventana se neutraliza aparte en N2 a N4).
- **19:** `test_custom_auth_header_dropped_on_other_host`, `test_mcp_client_redirect_refused`.
- **21:** `test_users_preview_keeps_value`, `test_providers_preview_no_update` (por `ctid`, como en P-20).
- **22:** los 10 de `test_seges_sandbox_side_effects.py`.

Pasan con y sin parche (no regresión): los 7 de no regresión de `test_seges_change_journal.py`, los 7 de
`TestSegesSandboxCredentials` y `TestSegesOutsideBoxA` citados arriba, `test_marker_cleared_after_box_a`,
`test_box_a_cannot_lift_mark` (comprueba el sandbox, no el guardián), `test_same_host_keeps_header`,
`test_users_preview_keeps_groups`, `test_import_still_applies` y, en Chatboo,
`test_mark_restored_when_design_fails` (salvo en N4) y los de `test_seges_chatboo_access.py` anteriores.

**Pendiente en el laboratorio** (lo ejecuta Sergio, tras reiniciar el contexto): P-19, P-37, P-37b, P-17
manual, P-70 casos 1 a 5 y P-20 repetida ([lab_e2_3879.md](lab_e2_3879.md)).

### Revisión de E2′ (27/10/2026): rechazo del parche 18, parche 23 y nueva línea base

- **Revisión (`odoo-reviewer`):** rechaza el parche 18 y aprueba el resto con observaciones menores.
  Scripts de reproducción del revisor (sin secretos), en el scratchpad de su sesión:
  `/tmp/claude-1000/-home-soporte-GitHub-third-party/8a8812e6-9f03-4729-b6f8-d3064fb95b17/scratchpad/`
  (`p18_check.py`, `p18_b.py`, `p18_c.py`, `p18_real.py`).
- **Cambios** (detalle en las entradas de los parches 18, 21 y 23):
  - parche 18: alias en `read_group`, ids que no son enteros y caché del hilo;
  - parche 21: `flush` del camino normal dentro del `try` y `registry.clear_caches()`;
  - parche 23 (PNS-101, nuevo): al comprobar si el sandbox llega a la caché resultó que llega a `env.cache`
    y a `env.all`. Sergio eligió la opción A, como parche propio;
  - tests (punto 6 de la revisión): `assertRaisesRegex` con el mensaje en los negativos del 18 y en
    `test_plan_unlink_requires_unlink_right` (17); control positivo en `test_box_a_cannot_lift_mark`.

**Comprobaciones:**

1. `py_compile` con Python 3.7.3 en la imagen `odoo-dev:14-lab_pns_ai_3879`, repo montado en solo lectura:
   los 23 `.py` tocados o nuevos, correctos.
2. `python3 ~/.claude/hooks/odoo_lint.py --revisar --base c639fa8 pns_base/ pns_ai_mcp/ pns_ai_chatboo/`:
   0 incidencias nuevas y 706 preexistentes.
3. `odoo-dev 14 tests pns_base,pns_ai_mcp,pns_ai_chatboo` (log `tests-20261027-162742.log`): 341 tests,
   18 F y 32 E; los mismos, por nombre, que antes de la revisión (log `tests-20261027-151148.log`).

| Módulo | Tests | Fallos | Errores | Línea base E2′ anterior |
|---|---|---|---|---|
| `pns_ai_mcp` | 313 | 18 | 32 | 293 · 18 F · 32 E |
| `pns_ai_chatboo` | 28 | 0 | 0 | 26 · 0 · 0 |

Tests nuevos (22), todos en verde: `test_seges_sandbox_credentials.py` 7, `test_seges_sandbox_env.py` 13,
`test_seges_canvas_box_a.py` 1 y `test_seges_skill_env.py` 1. Una primera ejecución dio 4 F de tests nuevos
(el JSON de la respuesta va escapado dos veces; el proveedor creado en el test no existe para el cursor de
la caja A; la skill con cliente falla por su `_iso`): corregidos los tests, no el código.

**Neutralización (27/10/2026):** script `neutralizar.py` en el scratchpad de esta sesión
(`/tmp/claude-1000/-home-soporte-GitHub-third-party/5b6a0dd0-041a-4357-ae79-6549a6ce09ac/scratchpad/`):
copia, cambio, batería completa, restauración y comprobación del SHA-256 de cada archivo (iguales).

| Ejecución | Qué se retira | Resultado | Fallan (de E2′) |
|---|---|---|---|
| N0 | nada | 341 · 18 F · 32 E | — |
| N1 | 18, guardián (`_box_a_allowed` siempre `None`) | 40 F · 35 E | los negativos del 18, también los nuevos (alias, `float`, `str`, `new(origin=…)`), `test_box_a_engine_cache_before_run` y los de Chatboo que dependen del guardián |
| N2 | 18, ventana (`_box_a_trusted` no quita la marca) | 18 F · 37 E | 5 de `test_seges_canvas_box_a.py` (la llamada de diseño da `AccessError`) |
| N3 | 18, alias (vuelve `_field_names` en `fields`) | 20 F · 34 E | `test_read_group_alias_provider` (2 subtests) y `test_read_group_alias_icp` (`display_name:max(value)` y `key:max(value)`) |
| N4 | 18, ids (vuelve `isinstance(i, int)`) | 21 F · 32 E | `test_icp_float_id`, `test_icp_str_id` y `test_icp_new_origin` con `origin` decimal |
| N5a | 18, caché al poner la marca (`tools_relaxaicode.py`) | 19 F · 32 E | `test_box_a_engine_cache_before_run` |
| N5b | 18, caché al cerrar la ventana | 19 F · 32 E | `test_guard_still_closed_after_window` |
| N6 | 21, `registry.clear_caches()` | 19 F · 32 E | `test_users_preview_keeps_groups` |
| N7a | 23 entero (lista de `GuardedSandboxEnv`, AST y `guarded_getattr`) | 43 F · 32 E | todos los negativos de `test_seges_sandbox_env.py` (con subtests) |
| N7b | 23, solo la lista de `GuardedSandboxEnv` | 29 F · 32 E | `test_wrapper_allowlist` (11 subtests); el AST y `guarded_getattr` siguen cerrando el resto |
| N7c | 23, solo el AST y `guarded_getattr` | 32 F · 32 E | los negativos con el mensaje de estado del ORM: la lista de `GuardedSandboxEnv` sigue rechazando, con otro mensaje |

- N3: `value:max(key)` sigue rechazado sin el cierre (el alias `value` ya lo cogía `_field_names`).
- N4: con `origin` entero el caso ya estaba cubierto antes (se lee por el `origin`).
- N6: la importación de usuarios escribe el grupo con `write`, que vacía el `ormcache`; el valor viejo
  aparece si algo pregunta `has_group` durante la vista previa (como `ai.mcp.user._export_user_dict`). El
  test lo simula envolviendo `_preview_snapshot`; sin esa llamada, el test pasaba con y sin el cambio.
- Pasan con y sin cada cierre (no regresión): `test_read_group_alias_allowed`, `test_icp_int_id_allowed_key`,
  `test_builtin_all_and_cache_name`, `test_allowed_attrs`, `test_engine_attrs_on_wrapper` y
  `test_customer_360_runs`.

**Scripts del revisor** (`odoo-dev 14 shell`, solo lectura, con rollback):
- `p18_check.py`: A (`browse` decimal, también con `read`) y B (alias), rechazo. **C sigue dando
  `True`**: el script pone la marca con `setattr` sobre un cursor ya usado y no pasa por `tool_relaxaicode`,
  que es donde se vacía la caché. Por la herramienta real, el mismo caso (`p18_real_c.py`, en el scratchpad
  de esta sesión) da rechazo, y lo cubre `test_box_a_engine_cache_before_run`.
- `p18_b.py` (alias en `ir.config_parameter`) y `p18_c.py` (alias en `ai.provider`, con un proveedor con
  clave): rechazo.
- `p18_real.py` (caja A real): `control`, `A_float` y `B_alias`, rechazo del guardián (se comprobó el
  mensaje).
- Reproducción de PNS-101 repetida con el parche 23: `env.cache`, `env.all`, alias, `getattr` compuesto y
  `towrite`, rechazados; ningún entorno visible desde el sandbox.

**Pendiente en el laboratorio** (lo ejecuta Sergio, tras reiniciar el contexto): lo anterior, más P-19 h,
i y j y P-101 ([lab_e2_3879.md](lab_e2_3879.md)).

### Segundo rechazo de E2′ (28/10/2026): C1/V1/V2 y C2 — cierre por la raíz

`odoo-reviewer` **rechaza** la propuesta E2′ por fugas del sandbox de relaxaicode
que **no introduce** E2′ (están en 3.1.782 y en LIYBEN). Confirmadas por la
herramienta real: **C1** (`.format` con la plantilla en una variable llega a
`odoo.tools.config` y saca `admin_passwd` / `db_password`), **C2** (`user` /
`company` con `su=True` saltan ACL y record rules); y por lectura de código
**V1** (`string.Formatter` por import) y **V2** (`type()` de un `attrgetter`),
que devuelven el objeto Python real y, por `__globals__` → `__builtins__` →
`__import__`, permiten probablemente ejecutar código.

**Decisión de diseño (Sergio, 27–28/10/2026):** cortar la raíz, no tapar
ejemplos. C1, V1, V2 y variantes comparten causa: el sandbox resuelve un nombre
que lleva a un dunder (o al objeto que lo porta) por una vía que el AST no ve
(nombre partido, método en variable, `format` / `Formatter` / `attrgetter`).
Se impide resolver esos nombres **por ninguna vía**, en el punto donde se
resuelve el acceso, no en el AST que mira literales. Gravedad **Crítica** las dos
(C1/V1/V2 y C2).

**Inventario (fase 1) de puntos de resolución de nombres en runtime** y si pasan
por un filtro común:

| Punto | Dónde | ¿Filtro común antes? |
|---|---|---|
| `guarded_getattr` (builtin `getattr`) | `context_builder.py` | Sí (privado/PRIVILEGE/ENV_STATE/ORM/DANGEROUS/dunder) |
| `attrgetter` / `methodcaller` → `_check_attr_path` | `context_builder.py` | Sí (vía `guarded_getattr`) |
| `SafeModuleFacade._module_facade_rejects` | `context_builder.py` | Parcial — **faltaba** `DANGEROUS_FORMAT_NAMES` (hueco V1) |
| `str.format` / `format_map` con plantilla no literal | **no había formateador propio** | **No** (hueco C1 y variantes) |
| `type(x)` (1 arg), clases crudas (`date`…) | builtins/globales | Devuelven objeto real; su único canal dunder es `format`/literal |

**Enfoque de raíz:** predicado único `sandbox_forbidden_name` (dunder + privado +
PRIVILEGE + ENV_STATE + FORBIDDEN_ORM + ORM_WRITE + SIDE_EFFECT + DANGEROUS_ATTR
+ DANGEROUS_FORMAT + `format`/`format_map`), aplicado en `guarded_getattr`,
`_check_attr_path`, `_module_facade_rejects` y el formateador propio. El AST con
el filtro ampliado es defensa adicional, no la única capa.

#### Parche 23 ampliado (PNS-101): formateador propio de `str.format` / `format_map`

- **Causa de C1/V1/V2:** `str.format` es un método en C: resuelve la cadena de
  atributos de la plantilla sobre el objeto real sin pasar por `guarded_getattr`,
  y con la plantilla en variable el AST no la ve. Un `str` guardado en los
  builtins no sirve (los literales son `str` nativo). El punto de enganche es el
  **acceso a `.format` / `.format_map`**, que el AST ve siempre, sea cual sea el
  receptor.
- **Cambio:**
  - `controllers/relaxaicode_format_guard.py` (**nuevo**): `_FormatAttrRewriter`
    (`ast.NodeTransformer`) reescribe todo `ast.Attribute` con
    `attr in {'format','format_map'}` y `ctx=Load` como
    `_sandbox_str_attr(<receptor>, '<attr>')` — sobre el `Attribute`, para cubrir
    `f = t.format`. `compile_sandbox_code` parsea, reescribe y compila el AST
    **directamente** (sin `ast.unparse`, que es 3.9+; el objetivo es 3.7.3).
    `SandboxFormatter(string.Formatter)` parte el campo con
    `_string.formatter_field_name_split` y resuelve cada `.atributo` por
    `guarded_getattr` y cada `[clave]` por `getitem` (los atributos son el vector,
    ya cubiertos); las especificaciones anidadas (`'{0:{1.x}}'`) pasan por el
    mismo `get_field`. `_sandbox_str_attr`: `isinstance(Markup)` **antes** que la
    rama `str` (si no, perdería el autoescape) → `AttributeError` con el mismo
    estilo que los nombres prohibidos; `str` → `format`/`format_map` del
    `SandboxFormatter`; el tipo `str` → re-despacho sobre la plantilla; cualquier
    otro receptor → `guarded_getattr` (y como `format`/`format_map` están en
    `sandbox_forbidden_name`, rechaza).
  - `controllers/tools_relaxaicode.py`: compila con `compile_sandbox_code` e
    inyecta `_sandbox_str_attr` en `safe_context`.
  - `controllers/validators_base.py`: `sandbox_forbidden_name`,
    `RELAXAICODE_STR_FORMAT_NAMES`, `_is_dunder`.
  - `controllers/context_builder.py`: `guarded_getattr` y `_module_facade_rejects`
    usan `sandbox_forbidden_name` (cierra V1: `from string import Formatter`).
  - `controllers/validators.py`: filtro de campos de la plantilla **literal**
    ampliado a `sandbox_forbidden_name` (defensa adicional).
- **Markup:** hoy no es alcanzable como receptor en el sandbox (no es módulo
  permitido; los campos `Html` de Odoo 14 dan `str`; ningún helper devuelve
  `Markup`). Se **rechaza** por defensa en profundidad. El formateador con escape
  se reabre solo si aparece un uso legítimo (ver
  [pns_ai_decisiones.md](pns_ai_decisiones.md) / nota de pendiente).
- **Qué se degrada:** `.format` / `.format_map` dinámicos (`getattr(t,'format')`,
  `attrgetter('format')`, `methodcaller('format',…)`) y sobre objetos no-`str` se
  rechazan. Inventario de fábrica (`ai/`, `data/`): 0 usos de `str.format` Python
  (las 28 coincidencias son `Intl.NumberFormat` de JS embebido). Plantilla literal
  y en variable con campos públicos siguen funcionando.
- **Tests:** `pns_ai_mcp/tests/test_seges_format_guard.py` (negativos: payload
  exacto de C1, plantilla en variable / concatenada / de llamada, `f=t.format`,
  `str.format(t,user)`, `getattr`/`attrgetter`/`methodcaller`, spec anidada,
  `format_map` con dunder, V1, V2, Markup; positivos: `{0.login}`, `{:,.2f}`,
  `format_map` con dict, plantilla traducida en variable, `{0[k]}`, control del
  sandbox).

#### Parche 24 (PNS-102): `user` / `company` / `companies` del sandbox SIN su

- **Qué falla sin él (C2):** `env.user` / `env.company` / `env.companies` del ORM
  fuerzan `su=True` (`api.py`: `return self(su=True)[...]`). El sandbox corre como
  el usuario, pero por el registro `user` inyectado (y los globales) se leían
  campos `NO_ACCESS` (`res.users.totp_secret`) y datos de terceros saltándose ACL
  y record rules.
- **Cambio** (`controllers/context_builder.py`): helper `_identity_no_su` que
  reconstruye `user` = `env['res.users'].browse(env.uid)`, `company` =
  `env['res.company'].browse(env.company.id)`, `companies` =
  `env['res.company'].browse(env.companies.ids)`, **sin** su. Se usa en
  `GuardedSandboxEnv.__getattr__` (`user`/`company`/`companies`) y en los globales
  `user`/`company` de `build_safe_context`.
- **Comprobado:** las skills de fábrica que usan `env.company` (10) y `env.user`
  (3) leen `.id`/`.name`/`.lang` del propio usuario/compañía, válido sin su.
- **Tests:** `pns_ai_mcp/tests/test_seges_identity_su.py` (identidad sin su en el
  wrapper, el helper y los globales; positivo de lectura propia; C2: `totp_secret`
  por `user` y por `env[...]` da `AccessError`, con `skipTest` si `auth_totp` no
  está).

#### A1/S1 (dentro del parche 23 ampliado)

- `GuardedSandboxEnv`: se retiran `with_context` / `with_company` de `_ATTRS` y
  `_WRAP_METHODS` (`_WRAP_METHODS = ()`) y del docstring; el código del modelo usa
  `recordset.with_context(...)`, que no pasa por el wrapper (comprobado:
  `users_all.py`, `sys_info.py`). Comentario de `cr`/`registry` corregido.

#### Blindaje de los nombres internos del motor (dentro del parche 23 ampliado, 28/10/2026)

Sugerencia de la revisión acotada de E2′ (28/10/2026), **aprobada por Sergio** el mismo día.

- **Qué cubre:** el motor inyecta `_sandbox_str_attr` en el contexto del sandbox, y el código reescrito
  lo llama. Un script podía sombrearlo (`_sandbox_str_attr = …`). Hoy no es explotable: lo que el script
  ponga en su lugar sigue sin alcanzar el `str.format` nativo (`format`/`format_map` están en
  `sandbox_forbidden_name` por todas las vías). Se cierra para que la reescritura llame siempre al
  formateador del motor.
- **Nombres internos:** `RELAXAICODE_ENGINE_NAMES = {'_sandbox_str_attr'}`, el único que inyecta
  `relaxaicode_format_guard` (`tools_relaxaicode.py`: `safe_context['_sandbox_str_attr']`). Se leen, no
  se ligan.
- **Cambio:**
  - `controllers/validators_base.py`: `RELAXAICODE_ENGINE_NAMES`, `RELAXAICODE_ENGINE_NAME_HINT` y
    `engine_name_binding(node)`, que devuelve el nombre interno que liga un nodo: `Name` con `Store` o
    `Del` (asignación, asignación aumentada, desempaquetado y destinos de `for`, comprensión y `with … as`),
    `global`/`nonlocal`, argumento (`ast.arg`: posicional, `*args`, solo nombre, `**kwargs` y lambda),
    nombre de `def`/`class`, destino de `import`/`from … import` (`asname` o el primer componente) y
    `except … as`.
  - `controllers/validators.py`: primer chequeo del recorrido del AST, con el mismo estilo que los
    nombres prohibidos: `(False, format_ast_error('ENGINE_NAME', …), False)` →
    `[PROHIBITED:ENGINE_NAME] RelaxAICode cannot bind '_sandbox_str_attr': …`.
- **Tests** (`test_seges_format_guard.py`, clase nueva `TestSegesEngineNames`, separada para no superar
  20 métodos públicos por clase): un test negativo por forma, `test_engine_name_store`, `_del`,
  `_global`, `_nonlocal`, `_argument`, `_def_class`, `_import`, `_for`, `_with` y `_except`, y
  `test_engine_name_shadow_tool` por la herramienta real (rechazo sin ejecutar nada). Los positivos de
  `TestSegesFormatGuard` confirman que leer el nombre (la reescritura) sigue funcionando.
- **Comprobaciones (28/10/2026):**
  1. `python3 ~/.claude/hooks/odoo_lint.py --revisar --base c639fa8 pns_ai_mcp/ pns_ai_chatboo/ pns_base/`:
     **0 incidencias nuevas** y 705 preexistentes.
  2. `odoo-dev 14 tests pns_ai_mcp` (BD de test nueva, Python 3.7 del contenedor): **348 tests, 18 F y
     32 E**. Los 50 que fallan son, por nombre, los mismos que en la línea base de E2′ (ninguno es
     `TestSeges*`). Los **11 tests nuevos** de `TestSegesEngineNames` están en verde, y también los 146
     `TestSeges*` de `pns_ai_mcp`.

#### LIYBEN

Claves MCP **revocadas el 27/10/2026** hasta el despliegue final de E2′. Paso
pendiente: **volver a generarlas tras el despliegue** (ver plan §3 y §4, y el
seguimiento PNS-101/PNS-102).

**Comprobaciones (28/10/2026):**

1. `compile()` con Python 3.7.3 en la imagen `odoo-dev:14-lab_pns_ai_3879` (repo montado en solo
   lectura): los 7 `.py` tocados o nuevos, correctos (en especial `relaxaicode_format_guard.py`, que
   compila el AST directamente, sin `ast.unparse`).
2. `python3 ~/.claude/hooks/odoo_lint.py --revisar --base c639fa8 pns_ai_mcp/ pns_ai_chatboo/ pns_base/`:
   **0 incidencias nuevas** y 705 preexistentes.
3. `odoo-dev 14 tests pns_ai_mcp` (BD de test nueva): **337 tests, 18 F y 32 E**; el conjunto de los 50
   que fallan es idéntico, por nombre, al de la línea base de E2′ (sin regresión). Los **24 tests nuevos**
   (`test_seges_format_guard.py` 19, `test_seges_identity_su.py` 5) en verde. (`auth_totp` instalado en la
   BD, así que el test C2 de `totp_secret` corre, no se salta.)

**Neutralización (28/10/2026):** script `neutralizar_e2amp.sh` en el scratchpad de esta sesión
(copia → parcheo → batería completa → restauración y SHA-256). Cada cierre, por separado, es
load-bearing; los tres archivos quedan idénticos (SHA-256 IGUAL):

| Ejecución | Qué se retira | Resultado | Fallan (de E2′ ampliado) |
|---|---|---|---|
| N0 | nada | 337 · 18 F · 32 E | — |
| NEU-A | formateador (compila sin reescribir `.format`) | 23 F · 32 E | `test_c1_exact_payload`, `test_template_in_variable`, `test_template_concatenated`, `test_str_format_unbound`, `test_format_map_dunder` (plantillas no literales que el AST no ve) |
| NEU-B | predicado sin `DANGEROUS_FORMAT_NAMES`/`format`/`format_map` | 21 F · 32 E | `test_getattr_format` (subtests), `test_attrgetter_methodcaller_format` (obtienen el método nativo) |
| NEU-C | parche 24 (`user`/`company`/`companies` con su) | 24 F · 32 E | `test_wrapper_user_not_su`, `test_wrapper_company_not_su`, `test_identity_helper_not_su`, `test_c2_no_access_field_via_user` |

**NEU-D (28/10/2026, tras el blindaje de nombres internos):** script `neutralizar_neu_d.sh` en el
scratchpad de la sesión, con el mismo procedimiento. Cambia `engine_name = engine_name_binding(node)` por
`engine_name = None` en `validators.py`, ejecuta la batería (log `tests-20261028-120613.log`), restaura y
calcula el SHA-256. `validators.py` y `validators_base.py` quedan IGUAL que antes.

| Ejecución | Qué se retira | Resultado | Fallan (de E2′ ampliado) |
|---|---|---|---|
| N0 | nada | 348 · 18 F · 32 E | — |
| NEU-D | chequeo `engine_name_binding` del recorrido del AST | 33 F · 32 E | Los **11** de `TestSegesEngineNames` (`test_engine_name_store`, `_del`, `_global`, `_nonlocal`, `_argument` con sus 4 subtests, `_def_class`, `_import`, `_for`, `_with`, `_except` y `_shadow_tool`). Los 15 F de más son esos 11 tests más los 4 subtests de `_argument` |

**Scripts del revisor** (`odoo-dev 14 shell`, solo lectura, con rollback), todos pasan a **rechazo**:
- `c1_config.py`: `reach_config_object` y `reach_config_options` → `AttributeError '__func__'` (isError);
  `leak_admin_passwd` y `leak_db_password` → `error/rechazo`, `hash_matches_server: None` (no filtran),
  `server_key_set: True` (el servidor sí tiene esas claves).
- `v1_formatter.py`: `from string import Formatter` e `import string; string.Formatter` → rechazo.
- `v2_type_attrgetter.py`: `type(attrgetter(...))` + `.format` con `__init__.__globals__` → rechazo.
- `c2_noaccess.py`: `control_demo_directo` y `exploit_via_su` → `AccessError (NO entrega)`.

### Segunda vuelta de E2′ (28/10/2026): clase nativa de las fachadas y vía de skills

`odoo-reviewer`, al revisar la propuesta anterior, confirma dos evasiones que las
tablas de la primera vuelta no cubrían (siguen dentro del parche 23 ampliado,
PNS-101; no son parches nuevos):

- **CRÍTICO 1 — clase nativa de las fachadas.** `guarded_attrgetter` /
  `guarded_methodcaller` validaban la ruta pero devolvían una instancia real de
  `operator.attrgetter` / `operator.methodcaller`. Con `type()` permitido se
  obtenía la **clase nativa** (`type(attrgetter('id'))`) y con ella se construía
  un getter nuevo que ya no pasaba por `_check_attr_path`, llegando a los dunders
  del objeto. Esto **corrige el diagnóstico de la primera vuelta**: la fila
  «`v2_type_attrgetter.py` → rechazo» de los *Scripts del revisor* se refería a
  `type(attrgetter('id')(user))` (la clase del **resultado**, un recordset), no a
  `type(attrgetter('id'))` (la clase del **getter**), que era la vía abierta.
- **CRÍTICO 2 — vía de skills.** `bootstrap_skill_code_body` (las skills con `/`)
  compilaba con `compile()` normal, sin la reescritura de `.format`; una plantilla
  C1 en variable se resolvía con `str.format` nativo.

**Decisión (Sergio, 28/10/2026):** cerrar la raíz en los dos puntos y, por
consistencia, cerrar también `itemgetter`, que la fachada devolvía nativo.

#### Cierre de las fachadas de `operator` (CRÍTICO 1)

- `controllers/context_builder.py`: `guarded_attrgetter`, `guarded_methodcaller`
  y el nuevo `guarded_itemgetter` devuelven una **función** (no el objeto de
  `operator`). `type()` sobre el resultado da `function`; su «constructor» no
  sirve para recorrer atributos. Helper `_resolve_attr_path` (un `guarded_getattr`
  por tramo). `SafeModuleFacade.__getattr__` intercepta los tres nombres.
  - `attrgetter`: valida cada ruta con `_check_attr_path` y resuelve por
    `guarded_getattr`; una ruta → valor, varias → tupla; conserva las rutas con
    punto y el uso como `key=`.
  - `methodcaller`: resuelve el método por `guarded_getattr` y lo llama con los
    argumentos ligados.
  - `itemgetter`: resuelve **subíndice** (`obj[k]`), no atributos (no es vía a
    dunders); se cierra solo para que `type()` no dé la clase nativa. Conserva el
    subíndice y el `key=`.

#### Helper único `run_sandbox_code` (CRÍTICO 2)

- `controllers/relaxaicode_format_guard.py`: `compile_sandbox_code` devuelve un
  `SandboxCode`; `run_sandbox_code(ctx, code, filename)` es la **única** entrada
  para ejecutar código del sandbox. Compila con la reescritura de `.format` (o
  acepta un `SandboxCode` ya compilado), inyecta `_sandbox_str_attr` **después**
  de los valores del llamante (ningún parámetro lo sombrea) y hace el `exec`.
  Rechaza un objeto de código hecho con `compile()` normal.
- `controllers/tools_relaxaicode.py` y `utils/skill_runtime.py`: las dos vías
  ejecutan con `run_sandbox_code`. Solo se unifica la compilación y la inyección;
  cada vía conserva sus globals y su gestión de errores (relaxaicode compila antes
  para responder `-32602` ante `SyntaxError`; las skills compilan dentro de su
  `try` y devuelven un error amigable).

#### Inventario del punto 6 (rehecho, 28/10/2026)

Construido el `safe_context` real (81 entradas, 50 builtins): para cada
builtin/fachada, si `type()` sobre el objeto da una clase nativa con constructor
o ruta dunder peligrosa.

| Categoría | `type()` da | ¿Vector? |
|---|---|---|
| fachada `attrgetter` / `methodcaller` | `function` | Cerrado (antes: clase nativa que resolvía atributos en C) |
| fachada `itemgetter` | `function` | Cerrado (residual: solo subíndice, no dunders; cerrado por consistencia) |
| builtins tipo (`int/str/list/dict/tuple/set/type/bytes`…) | clases nativas construibles | No: su único canal a atributos es `getattr` (guardado) o `.format` (reescrito) |
| `date/timedelta/timezone/ZoneInfo`, excepciones | clases construibles | No: sin ruta a dunder fuera de `guarded_getattr` |

Tras el cierre, ninguna entrada del `safe_context` resuelve atributos en C.

#### Tests (segunda vuelta)

- `pns_ai_mcp/tests/test_seges_facade_class.py` (**nuevo**): negativos
  `test_type_attrgetter_class`, `test_type_methodcaller_class`,
  `test_type_itemgetter_class` (la clase nativa de la fachada ya no abre la vía) y
  `test_skill_format_blocked` (plantilla C1 en variable por
  `bootstrap_skill_code_body`); positivos de no regresión
  `test_attrgetter_sorted_key`, `test_attrgetter_multiple_paths`,
  `test_attrgetter_dotted_path`, `test_methodcaller_legit`,
  `test_itemgetter_legit`, `test_skill_format_ok`.
- Las comprobaciones de no filtración leen `database.secret` en tiempo de test y
  usan `assertFalse(secreto in texto, 'filtra')`: ni el secreto ni la respuesta
  entera entran en el mensaje del assert. Se corrige el mismo patrón en los tests
  previos `test_seges_format_guard.py` (`_refused`) y
  `test_seges_sandbox_credentials.py` (`test_box_a_reference_secret_refused`).

#### Neutralización NEU-E / NEU-F / NEU-G (28/10/2026)

Scripts `neutralizar_neu_ef.sh` y `neutralizar_neu_g.sh` en el scratchpad de la
sesión (backup → quitar el cierre → batería → restaurar → SHA-256). N0 = 358 ·
18 F · 32 E (356 anteriores + 2 de itemgetter). Cada cierre es load-bearing; los
archivos quedan IGUAL (SHA-256).

| Ejecución | Qué se retira | Resultado | Fallan (de los nuevos) | Archivo |
|---|---|---|---|---|
| NEU-E | fachadas vuelven a devolver `attrgetter`/`methodcaller` nativo | 20 F · 32 E | `test_type_attrgetter_class`, `test_type_methodcaller_class` | `context_builder.py` IGUAL |
| NEU-F | la vía de skills vuelve a `compile()` + `exec` sin reescritura | 19 F · 32 E | `test_skill_format_blocked` | `skill_runtime.py` IGUAL |
| NEU-G | la fachada deja de interceptar `itemgetter` | 19 F · 32 E | `test_type_itemgetter_class` | `context_builder.py` IGUAL |

**Aclaración de NEU-D (recuento 11 + 4 = 15):** en el log de NEU-D
(`tests-20261028-120613.log`) hay 33 F, es decir 15 más que los 18 de la línea
base. Son los **11** tests de `TestSegesEngineNames` más los **4** subtests de
`test_engine_name_argument` (que el runner cuenta aparte). El total es 15, no 14:
`test_engine_name_argument` falla además por su cuenta (la forma `lambda`, fuera
de los subtests), de modo que aparece como test y como 4 subtests.

## Parches de la rama 14.0-pns-ai-3879 (E3′)

- **Fecha:** 29/10/2026. **Entrega:** E3′ (lienzo: M1, M2, F1 y D1) del
  [plan sobre 3.1.879](plan_correccion_pns_ai_3879.md).
- **Propuesta, comprobaciones previas y decisiones de Sergio:** [e3_propuesta_3879.md](e3_propuesta_3879.md),
  «Propuesta final (29/10/2026)». HEAD de partida: `59f8980`.
- **Rutas:** de 3.1.879 con E1′, E2′ y E3′ (copia de trabajo del 29/10/2026). Sin tocar `version`,
  `depends`, `external_dependencies`, `i18n`, `LICENSE` ni `NOTICE`. Mensajes nuevos en inglés, sin
  traducir. Solo cambia `pns_ai_chatboo`.
- **Marcadores:**
  `grep -rn "Seges: parche 2[5-8] (" pns_ai_chatboo --include=*.py --include=*.xml | grep -v /tests/`:
  24 líneas (25: 5; 26: 2; 27: 13; 28: 4, una de ellas en XML).
- **Pruebas manuales del laboratorio** (preparadas, las ejecuta Sergio): [lab_e3_3879.md](lab_e3_3879.md).

### Parche 25: `paint_canvas` pasa a privado y comprueba el dueño (M1)

- **Qué falla sin él (comparación §8.2 y §8.7, M1, Media):** `chatboo.session.paint_canvas` es público.
  Por `/web/dataset/call_kw`, `_call_kw_multi` hace `browse(ids)` sin comprobar el acceso, así que
  cualquier interno pide un diseño sobre **cualquier** sesión, y `_store_design` la sobrescribe como
  `SUPERUSER_ID` en un cursor propio con `commit` (P-8c). El dueño, además, gasta inferencia de diseño sin
  pasar por el acceso de Chatboo ni por la clave MCP.
- **Cambio** (`pns_ai_chatboo/models/chatboo_session.py`, `pns_ai_chatboo/models/chatboo_canvas.py`):
  - `paint_canvas` pasa a `_paint_canvas` (`chatboo_session.py:1055`). Odoo 14 rechaza por RPC los nombres
    con `_` (`check_method_name`). Llamadores: `open_page` (`chatboo_canvas.py:990`) y `edit_page`
    (`:1015`), los únicos (paso 0).
  - Al empezar, después de `ensure_one`, `_paint_canvas` lee la sesión en `sudo` y, si su `user_id` no es
    `self.env.uid`, da `AccessError` antes de leer el diseño o de llamar al proveedor (`:1073-1074`).
    **Sin** la excepción de uid 1 de `_session_of_this_turn`.
  - Import de `AccessError` (`chatboo_session.py:14-15`).
  - La lista del parche 15 (`validators_base.py:264`, `'paint_canvas'`) y su test
    (`test_seges_chatboo_export.py:40`) **no se tocan** (decisión 1): siguen como defensa por nombre.
- **Qué se degrada:**
  - nadie pide diseños por RPC, ni siquiera el dueño: el lienzo sigue por el chat (botón Canvas, página
    en espera) y por los helpers del sandbox;
  - un turno o un job que corra como `__system__` (uid 1) sobre la sesión de otro deja de pintar: da
    `AccessError`, que `page_url`/`page_edit` convierten en `log_no_page`. Chatboo usa el uid del usuario,
    así que no se espera ninguno.
- **Lint:** las tres incidencias de la línea del `def` (C901 19 > 16, R0912 21/12, R0915 61/50) son las
  del `paint_canvas` del fabricante (18 > 16, 20/12 y 59/50 en `59f8980`, `:1051`). Salen como nuevas
  porque el cambio de nombre toca esa línea; la comprobación del parche suma una rama y dos sentencias.
- **Cómo comprobar si el fabricante ya lo ha corregido:**
  ```sh
  grep -n "def paint_canvas\|def _paint_canvas\|user_id.id != self.env.uid" pns_ai_chatboo/models/chatboo_session.py
  ```
  Corregido si su versión no publica `paint_canvas` o si comprueba el dueño dentro del método.
- **Tests** (`pns_ai_chatboo/tests/test_seges_chatboo_canvas.py`, `TestSegesPaintCanvas`, 4):
  `test_rpc_public_name_gone` (`call_kw` de `paint_canvas` → `AttributeError`, método inexistente),
  `test_rpc_private_name_refused` (`call_kw` de `_paint_canvas` → `AccessError`, privado),
  `test_foreign_session_refused` (`_paint_canvas` sobre la sesión de otro usuario → `AccessError`;
  `canvas_design` y `canvas_rev` sin cambios; el driver no se llama) y `test_own_session_paints` (la
  propia se pinta: revisión 1 y la URL de la carcasa).

### Parche 26: `page_html` y `open_page` leen las imágenes sin `su` (M2)

- **Qué falla sin él (comparación §8.2 y §8.7, M2, Media; nota del 29/10/2026 en M3):** los helpers del
  sandbox se publican en `sudo` (`pns_ai_mcp/utils/sandbox_helpers.py:68-70`). `page_html` pasa a
  `pictures_as_tokens` `session.env` (sesión leída en `sudo` por `_session_of_this_turn`), y `open_page`,
  que usan `page_url` y `page_edit` con filas, `sessions.env` (el `self` del helper, en `sudo`). Para cada
  `/web/image/<modelo>/<id>/<campo>` de las filas, `_web_image_picture` hace `search` y lee el campo **sin
  ACL, reglas ni grupos de campo**, y la imagen queda incrustada en la página (P-8d).
- **Cambio:** `pictures_as_tokens(session.env(su=False), …)` en `page_html` (`chatboo_session.py:924-925`)
  y `pictures_as_tokens(sessions.env(su=False), …)` en `open_page` (`chatboo_canvas.py:974-975`). Mismo
  cursor, uid y contexto; solo cae `su`. `_session_of_this_turn` no se toca: la comprobación del dueño
  sigue leyendo la sesión en `sudo`.
- **Qué se degrada:** desaparecen de la página las imágenes de registros que el usuario no puede leer (la
  celda se queda con la ruta `/web/image/…` como texto); las de los registros que ve, igual. Las skills de
  fábrica que usan `page_html` (`cash_forecast`, `customer_360`, `pipeline`) apuntan a registros del
  usuario. En la caja A sigue mandando además el guardián del parche 18.
- **Cómo comprobar si el fabricante ya lo ha corregido:**
  ```sh
  grep -n "pictures_as_tokens(" pns_ai_chatboo/models/chatboo_session.py pns_ai_chatboo/models/chatboo_canvas.py
  ```
  Corregido si `pictures_as_tokens` recibe un entorno sin `su` (o con el usuario real) en las dos
  llamadas.
- **Tests** (`TestSegesCanvasPictures`, 5): un contacto de otra compañía, sin usuario (la regla
  multicompañía de `res.partner` lo oculta), y otro sin compañía; ambos con imagen. Llamada **a través de
  los helpers publicados** (`collect_sandbox_helpers`, en `sudo`) con `ai_session_ref`:
  `test_user_cannot_read_hidden` (control de la premisa), `test_page_html_hidden_picture` y
  `test_page_url_hidden_picture` (sin `data:image` en `canvas_design`), y los controles
  `test_page_html_visible_picture` y `test_page_url_visible_picture` (sí aparece
  `data:image/png;base64,`). `page_url` con el driver de diseño simulado.

### Parche 27: el lienzo no deja salir datos (F1)

- **Qué falla sin él (comparación §8.4 y §8.7, F1, Media; inventario I3 de la propuesta):**
  - las filas y el título se escriben dentro de `<script>` con `json.dumps(…, ensure_ascii=False)`, que no
    escapa `<`: un valor `</script><script>…` cierra el bloque y ejecuta lo que sigue dentro del marco
    (P-8e, a). El vigilante del fabricante (`</` → `<\/`) no cubre `<!--<script`;
  - el marco no tiene CSP: el diseño puede cargar librerías, fuentes, hojas e imágenes de cualquier host
    y sacar datos con `fetch`, `sendBeacon`, `WebSocket` o una imagen (P-8e, b). El prompt solo dice «Do not
    fetch»;
  - la carcasa no lleva `X-Frame-Options`: otra web puede enmarcarla;
  - `_picture_of` aceptaba cualquier valor que empezara por `data:image/`, y `swap_pictures` lo vuelve a
    meter sin escapar en `DATA` y en `<img src="…">` (punto nuevo del paso 0).
- **Cambio** (`pns_ai_chatboo/models/chatboo_canvas.py`, `pns_ai_chatboo/controllers/chatboo.py`):
  - **a) Función única** `_script_json(valor)` (`:42`): `json.dumps(valor, ensure_ascii=False,
    default=str)` y después `_script_safe` (`:34`), que cambia `<`, `>`, `&`, U+2028 y U+2029 por `\u003c`,
    `\u003e`, `\u0026`, `\u2028` y `\u2029`. Es exacto: en JSON esos caracteres solo aparecen dentro de
    cadenas, donde el escape significa lo mismo, y `json.loads` devuelve el valor original. Se usa en los
    cinco puntos de I3 (b): página de rescate (`_page_for_rows`, `:1164-1165`), `const DATA`
    (`_payload_for_const_data`, `:1501-1503`), otras matrices (`bind_script_row_json`, `:1811-1812`),
    `const TITLE` (`bind_const_title`, `:1516-1517`) y el vigilante (`_spare_rows_watch`, `:2271-2272`).
    En la rama de bloques de `const DATA`, `figures_for_design` no se toca y su texto pasa por
    `_script_safe` (decisión del paso 0: si `json.dumps` falla devuelve `str(blocks)`, que no es JSON, igual
    que hoy, pero ya no puede cerrar el `<script>`).
  - **a′) Imágenes** (decisión del paso 0): en `_picture_of` (`:770-771`), un valor `data:image/` solo
    cuenta como imagen si es exactamente `data:image/<tipo>;base64,<base64>` (`_DATA_URI_RE.fullmatch`);
    si no, se queda como texto y lo serializa `_script_json`.
  - **b) CSP en `<meta>` al servir** (versión rechazada en la revisión, B1; sustituida el 29/10/2026 por
    el prefijo fijo: ver «Revisión de E3′ (29/10/2026)» al final): `_CSP_META` (`:457`) y `_with_csp` (`:472-474`), que la pone la primera
    dentro del `<head>` del diseño. Si el documento no empieza (tras BOM, comentarios, `<!doctype>` y
    `<html>`) por `<head>`, se crea un `<head>` con la `<meta>` delante: así ningún script del diseño corre
    antes que ella, y el analizador mete en ese `<head>` los elementos de cabecera del diseño. La aplican
    `canvas_page` al `srcdoc` (`:572`; `/chatboo/canvas/<id>` y `/chatboo/page/<id>`) y
    `downloadable_page` (`:520`; las dos descargas), **al servir**: no se guarda, así que vale también para
    los diseños guardados antes. Política: `default-src 'none'; script-src 'unsafe-inline'; style-src
    'unsafe-inline'; img-src data: blob:; font-src data:; connect-src 'none'; form-action 'none'; base-uri
    'none'; frame-src 'none'; object-src 'none'; worker-src 'none'`.
  - **c) Regla nueva en `_PAGE_RULES`** (`:67-69`), en inglés: «Do not load external libraries, fonts,
    stylesheets or images: the page cannot reach the network. Draw charts with inline SVG or <canvas>.»
    Llega a `DESIGN_SYSTEM` y a `EDIT_SYSTEM`.
  - **d) `X-Frame-Options: SAMEORIGIN`** en `GET /chatboo/canvas/<session_id>` (`chatboo.py:1153-1159`) y
    `GET /chatboo/page/<page_id>` (`:1246-1252`). Nada enmarca la carcasa (paso 0).
- **e) Riesgo aceptado** (decisión 3 e, I3 d):
  - **autonavegación del marco** (`location = …`, `<meta http-equiv="refresh">`, un enlace sin `target`):
    ninguna directiva CSP implantada la limita y el documento nuevo ya no tiene la `<meta>`;
  - **WebRTC** (`RTCPeerConnection` con STUN/TURN propio) y **DNS** (`dns-prefetch`, `preconnect`): sin
    directiva CSP que los cierre en todos los navegadores;
  - **imágenes `http(s)` externas de las filas**: dejan de verse en el lienzo (`img-src data: blob:`). Las
    de `/web/image` siguen, porque se incrustan en `data:`;
  - **respuestas 404 de la carcasa sin `X-Frame-Options`** (observación m4 de la revisión, aceptada el
    29/10/2026): `request.not_found()` devuelve el 404 genérico de werkzeug, sin la cabecera y sin nada del
    diseño. Sin sesión, Odoo redirige al login.
- **Qué se degrada:**
  - un diseño que use una librería, una fuente o una hoja de un CDN deja de cargarla: los gráficos tienen
    que ser SVG o `<canvas>` (lo dice ya la regla c). Los diseños guardados con CDN se ven sin ese recurso;
  - `fetch`, formularios, marcos y workers dentro del diseño, bloqueados;
  - una imagen `data:image/` que no sea base64 (SVG en texto, por ejemplo) ya no se trata como imagen
    (hoy ya rompía el JSON por las comillas);
  - la descarga se abre en local con la misma CSP.
- **Cómo comprobar si el fabricante ya lo ha corregido:**
  ```sh
  grep -n "Content-Security-Policy\|u003c\|X-Frame-Options\|external librar" pns_ai_chatboo/models/chatboo_canvas.py pns_ai_chatboo/controllers/chatboo.py
  ```
  Corregido si los datos van escapados dentro de `<script>` (`<` incluido), el marco y la descarga llevan
  una CSP sin red y la carcasa no se puede enmarcar desde otro origen.
- **Tests** (`TestSegesCanvasScriptJson`, 8, y `TestSegesCanvasShell`, 8), con valores
  `</script><script>alert(…)</script>`, `<!--<script>`, `R&D`, `>` y U+2028:
  - a: `test_const_data`, `test_const_data_blocks_shape` (rama de `figures_for_design`),
    `test_const_title`, `test_other_arrays`, `test_rescue_page`, `test_rows_watch` y `test_whole_page`
    (`place_rows_on_page` completo, con título): sin `</script><script>alert` ni `<!--<script` en el HTML, y
    `json.loads` del texto serializado devuelve el valor original;
    `test_picture_only_base64_data_uri` (a′);
  - b: `test_canvas_shell` y `test_page_shell` (`srcdoc` de la carcasa desescapado) y `test_canvas_download`
    y `test_page_download`: la `<meta>` CSP es lo primero de `<head>` y no hay ningún script antes, con un
    diseño guardado sin `<meta>` (`test_stored_design_has_no_csp` lo comprueba); `test_csp_without_head`
    (sin `<head>`, con un script antes de `<head>` y solo `<body>`) y `test_csp_policy`;
  - c: `test_design_rule` (en `_PAGE_RULES`, `DESIGN_SYSTEM` y `EDIT_SYSTEM`);
  - d: `X-Frame-Options: SAMEORIGIN` en `test_canvas_shell` y `test_page_shell`.
- **Errata (30/10/2026):** restituidas las secuencias de escape perdidas al escribir.

### Parche 28: páginas compartidas — dueño fijo, solo internos y el AI Administrator solo lee y borra (D1)

- **Qué falla sin él (comparación §8.3 y §8.7, D1, Baja; inventario I4):**
  - `write` no limita campos y Odoo 14 comprueba la regla **antes** de escribir: el dueño puede pasar la
    página a otro usuario cambiando `owner_id` (P-8h); con `user_ids` en el mismo `write`, el aviso sale
    como «<nuevo dueño> shared a page with you»;
  - el `domain` de `user_ids` (`share = False`) solo se aplica en la interfaz: por ORM entra un usuario de
    portal, que recibe la notificación (por correo, si es su preferencia) aunque no pueda leer la página;
  - la regla del AI Administrator (`[(1, '=', 1)]` con los cuatro permisos) le deja cambiar `design` o
    `name` de páginas ajenas (los lectores ven el HTML nuevo en la URL de Odoo), cambiar `owner_id`, avisar
    a quien quiera y crear páginas a nombre de cualquiera.
- **Cambio** (`pns_ai_chatboo/models/chatboo_canvas_page.py`, `pns_ai_chatboo/security/security.xml`):
  - `write` (`:86-93`): si `owner_id` está en los valores, no es `sudo` y cambia en alguna página,
    `AccessError` («Only the system can change the owner of a shared page.»). Escribir el mismo dueño no es
    un cambio. Nadie lo cambia fuera de `sudo`, tampoco el AI Administrator.
  - Constraint `_check_user_ids_internal` (`:69-75`): `user_ids` solo admite usuarios internos, también en
    `sudo` y en `create`, `ValidationError` («A page can only be shared with internal users.»). Odoo valida
    dentro de `create` y `write`, antes de `_tell_new_readers`: no sale ningún aviso.
  - Regla `chatboo_canvas_page_admin_rule` (`security.xml:67-78`): `perm_write` y `perm_create` pasan a
    `False`; quedan lectura y borrado. Está en `<data noupdate="0">` y `ir_model_data.noupdate` es falso
    (paso 0): el `-u` la cambia en las BD existentes. El dueño sigue escribiendo y creando las suyas por la
    regla del dueño.
  - Import de `AccessError` y `ValidationError` (`:19-20`).
- **Qué se degrada:**
  - el AI Administrator ya no corrige ni retira lectores de páginas ajenas: «Stop sharing» y guardar el
    formulario de una ajena dan `AccessError` (las vistas no cambian, decisión 4; en pantalla parece
    editable). Puede abrirlas, descargarlas y borrarlas;
  - pasar una página a otro dueño solo se puede con `sudo` (código del sistema), no desde la interfaz ni
    por RPC;
  - el docstring del modelo («The AI administrator sees, changes and deletes every page», `:9`) es del
    fabricante y ya no es exacto; no se toca.
- **Observación m3 de la revisión (29/10/2026):** en Odoo 14 el `domain=[('share', '=', False)]` de
  `user_ids` se aplica también al leer: un lector de portal ya guardado no se ve, ni en `sudo`. El
  constraint funciona porque lee la caché que deja el propio `create` o `write`; en datos existentes no
  rompe nada (añadir un interno a una página que tiene un portal da OK), pero tampoco lo detecta ni lo
  limpia. No se cambia el código. Se mide con `SELECT` en el laboratorio
  ([lab_e3_3879.md](lab_e3_3879.md), 8b), en el staging y en LIYBEN:
  `SELECT count(*) FROM chatboo_canvas_page_user_rel r JOIN res_users u ON u.id = r.user_id WHERE u.share;`
- **Cómo comprobar si el fabricante ya lo ha corregido:**
  ```sh
  grep -n "owner_id' in vals\|constrains('user_ids')" pns_ai_chatboo/models/chatboo_canvas_page.py; grep -n -A9 'chatboo_canvas_page_admin_rule' pns_ai_chatboo/security/security.xml
  ```
  Corregido si `owner_id` no se puede cambiar por ORM, `user_ids` rechaza usuarios de portal en el servidor
  y la regla del AI Administrator no da escritura ni alta.
- **Tests** (`TestSegesSharedPage`, 9): `test_owner_cannot_change_owner`, `test_ai_admin_cannot_change_owner`
  (en su página y en una ajena), `test_sudo_changes_owner` (control), `test_same_owner_is_not_a_change`,
  `test_portal_reader_refused` (por `write`, por `create` y en `sudo`), `test_internal_reader_allowed`
  (control), `test_ai_admin_reads_and_deletes`, `test_ai_admin_cannot_write_foreign` (`write` y
  `action_unshare`) y `test_ai_admin_cannot_create_for_other`.

### Comprobaciones de E3′ (29/10/2026)

1. `py_compile` con Python 3.7.3 en la imagen `odoo-dev:14-lab_pns_ai_3879`, repo montado en solo lectura:
   los 6 `.py` tocados o nuevos, correctos.
2. `python3 ~/.claude/hooks/odoo_lint.py --revisar --base 59f8980 pns_base/ pns_ai_mcp/ pns_ai_chatboo/`:
   3 incidencias en líneas cambiadas, las tres en la línea del `def` de `_paint_canvas` y heredadas del
   fabricante (parche 25, «Lint»); 358 preexistentes. Ninguna en el código nuevo.
3. Línea base antes de cambiar nada (log `tests-20261029-160733.log`): **386 tests, 18 F y 32 E**
   (`pns_ai_mcp` 358, `pns_ai_chatboo` 28). Con E3′ (log `tests-20261029-163136.log`): **420 tests, 18 F
   y 32 E**; los 50 que fallan son, por nombre, los mismos; los **34 nuevos**, en verde. Una primera
   ejecución dio 4 E en `TestSegesCanvasShell`: el test usaba `self.session`, que en `HttpCase` es la
   sesión HTTP; se corrigió el test, no el código.

| Módulo | Tests | Fallos | Errores | Línea base (29/10/2026) |
|---|---|---|---|---|
| `pns_ai_mcp` | 358 | 18 | 32 | 358 · 18 F · 32 E |
| `pns_ai_chatboo` | 62 | 0 | 0 | 28 · 0 · 0 |

**Neutralización (29/10/2026):** script `neutralizar_e3.py` en el scratchpad de la sesión
(`/tmp/claude-1000/-home-soporte-GitHub-third-party/35a25973-48f1-42e9-b83a-108e4c834740/scratchpad/`),
con el método de E2′: copia, cambio, batería completa, restauración y SHA-256 de cada archivo (**IGUAL** en
los 10). Referencia N0: 420 · 18 F · 32 E (log `tests-20261029-163136.log`). En ningún caso desaparece un
F o E de la línea base.

| Ejecución | Qué se retira | Resultado | Fallan (de E3′) |
|---|---|---|---|
| N25a | 25, comprobación del dueño en `_paint_canvas` | 19 F · 32 E | `test_foreign_session_refused` |
| N25b | 25, vuelve el nombre público `paint_canvas` (y sus dos llamadores) | 19 F · 34 E | `test_rpc_public_name_gone` (F); `test_foreign_session_refused` y `test_own_session_paints` (E: `_paint_canvas` no existe) |
| N26 | 26, `pictures_as_tokens` con `session.env` / `sessions.env` (en `sudo`) | 20 F · 32 E | `test_page_html_hidden_picture`, `test_page_url_hidden_picture` |
| N27a | 27 a, `_script_safe` sin escape | 25 F · 32 E | `test_const_data`, `test_const_data_blocks_shape`, `test_const_title`, `test_other_arrays`, `test_rescue_page`, `test_rows_watch`, `test_whole_page` |
| N27img | 27 a′, `data:image/` sin exigir base64 | 19 F · 32 E | `test_picture_only_base64_data_uri` |
| N27b | 27 b, `_with_csp` devuelve el diseño sin `<meta>` | 23 F · 32 E | `test_canvas_shell`, `test_page_shell`, `test_canvas_download`, `test_page_download`, `test_csp_without_head` |
| N27d | 27 d, sin `X-Frame-Options` | 20 F · 32 E | `test_canvas_shell`, `test_page_shell` |
| N28o | 28, `owner_id` modificable | 20 F · 32 E | `test_owner_cannot_change_owner`, `test_ai_admin_cannot_change_owner` (en su propia página; en la ajena sigue frenando la regla) |
| N28u | 28, sin el constraint de `user_ids` | 19 F · 32 E | `test_portal_reader_refused` |
| N28r | 28, regla del AI Administrator con escritura y alta | 20 F · 32 E | `test_ai_admin_cannot_write_foreign`, `test_ai_admin_cannot_create_for_other` |

- La regla de diseño (27 c) no se neutraliza: es un texto del prompt y lo comprueba `test_design_rule`.
- Pasan con y sin cada cierre (controles): `test_rpc_private_name_refused`, `test_own_session_paints` (salvo
  N25b), `test_user_cannot_read_hidden`, `test_page_html_visible_picture`, `test_page_url_visible_picture`,
  `test_stored_design_has_no_csp`, `test_csp_policy`, `test_sudo_changes_owner`,
  `test_same_owner_is_not_a_change`, `test_internal_reader_allowed` y `test_ai_admin_reads_and_deletes`.

### Revisión de E3′ (29/10/2026): B1 del parche 27 b y nueva versión

- **Revisión (`odoo-reviewer`):** RECHAZADO por un bloqueante, **B1**; el resto, conforme o con
  observaciones menores (m1 a m4). Los scripts de html5lib de las dos revisiones están en el repo:
  [scripts_e3/csp_prefijo.py](scripts_e3/csp_prefijo.py) (incluye los 23 casos de esta primera revisión)
  y [scripts_e3/csp_adversario.py](scripts_e3/csp_adversario.py).
- **B1:** la primera versión de `_with_csp` buscaba el principio del documento y su `<head>` con
  expresiones regulares (`_DOC_START_RE`, `_HEAD_OPEN_RE`) que no siguen el tokenizador de HTML5.
  Comprobado con html5lib 1.1 en el equipo (la imagen no lo tiene) en 23 casos: con `<!-->`, `<!--->` o
  `--!>` un script del diseño corría antes que la CSP; con BOM (en el `srcdoc`), NBSP o VT iniciales,
  `<html-x>`/`<head-x>` o un atributo con `>`, la `<meta>` acababa en `<body>` (sin efecto) o dentro de un
  atributo; con `<?xml …?>` delante del doctype, la descarga pasaba a modo quirks.
- **Decisión de Sergio (29/10/2026):** no se aplica la corrección del revisor (otro analizador del
  principio del documento). `_with_csp` deja de analizar el diseño.
- **Cambio** (`pns_ai_chatboo/models/chatboo_canvas.py:465-474`, mismo marcador del parche 27):
  `_CSP_PREFIX = '<!DOCTYPE html><meta charset="utf-8">' + _CSP_META`, y `_with_csp(design)` devuelve
  `_CSP_PREFIX + design`, sin quitarle al diseño su doctype, su BOM ni nada. Se aplica como **último paso**
  al servir: en `canvas_page`, después de `_with_theme`, `_HIDDEN_HIDES` y `_PRINT_BRIDGE` y antes del
  escape de atributo del `srcdoc`; en `downloadable_page`, después de los botones de la descarga. Vale para
  la carcasa (`/chatboo/canvas/<id>`, `/chatboo/page/<id>`), las dos descargas y los diseños guardados
  antes. Se eliminan `_DOC_START_RE`, `_HEAD_OPEN_RE` y la búsqueda del `<head>`.
- **Por qué funciona (reglas de HTML5):**
  1. el primer token es nuestro doctype: el documento queda en **modo estándar** («no quirks»), sea cual sea
     lo que traiga el diseño;
  2. la `<meta charset>` que sigue, en el modo «before html», abre `<html>` y `<head>` implícitos; las dos
     `<meta>` son sus **dos primeros hijos**: la CSP es el segundo, justo detrás de la de `charset`, y antes
     que cualquier cosa del diseño;
  3. lo que viene del diseño se lee con la CSP ya en vigor: su doctype se ignora (error de análisis), los
     atributos de su `<html>` se fusionan con el nuestro, su `<head>` se ignora y sus elementos de cabecera
     siguen dentro de nuestro `<head>`; un BOM o cualquier texto cierra el `<head>` y abre `<body>`, con
     la CSP ya dentro de `<head>`.
- **Coste aceptado:** un diseño **sin doctype** pasa de modo quirks a estándar y puede verse algo distinto
  (cajas, alturas de tablas o de imágenes en línea). Los diseños con `<!DOCTYPE html>`, que es lo que pide
  el prompt, no cambian de modo. Se revisa en la comprobación visual del laboratorio
  ([lab_e3_3879.md](lab_e3_3879.md), apartado 2).
- **Discrepancia con el texto de la decisión:** se pidió comprobar que la `<meta>` CSP es «el primer hijo de
  `<head>`». Con el prefijo aprobado es el **segundo**: la `<meta charset>` va delante. No cambia nada para
  la seguridad (la de `charset` no carga ni ejecuta nada) y es lo que comprueban el script y los tests.
- **Comprobación con html5lib (en el equipo, fuera de los tests):** script
  [scripts_e3/csp_prefijo.py](scripts_e3/csp_prefijo.py), sobre los 23 casos de la primera revisión y los 14 de
  `B1_DESIGNS` del test: **37 casos, 0 MAL**. En la descarga y en el `srcdoc` (desescapado), los dos
  primeros hijos de `<head>` son la `<meta charset>` y la CSP, ningún script va antes de la CSP, lo servido
  empieza exactamente por el prefijo y el modo es «no quirks» en todos (también con BOM, `<?xml …?>`,
  comentarios raros y sin doctype). Control: con `_with_csp` sin prefijo (`c._with_csp = lambda d: d`
  tras `load()`), 37 de 37 MAL.
- **Tests cambiados** (`test_seges_chatboo_canvas.py`):
  - m1: `_assert_csp_first` (buscaba `<head` con una expresión) se sustituye por `_assert_csp_served`:
    lo servido **empieza** exactamente por `_CSP_PREFIX` y lo que sigue es el documento sin cambios (hasta
    el `</body>` del diseño, donde el servidor añade lo suyo). Se usa en `test_canvas_shell`,
    `test_page_shell`, `test_canvas_download` y `test_page_download` (diseño guardado antes del parche,
    sin `<meta>`). `test_csp_without_head` pasa a `test_csp_prefix_cases`, con 14 subtests
    (`B1_DESIGNS`): `<!-->`, `<!--->`, `--!>`, BOM, NBSP, VT, `<html-x>`/`<head-x>`, atributos con `>`,
    `<?xml …?>` y doctype, `<script>` antes del `<head>`, mayúsculas con una `<meta http-equiv>` propia,
    sin doctype, solo `<body>` y sin `<body>`. `test_csp_policy` comprueba además el prefijo exacto;
  - m2: `test_foreign_session_refused` usa `assertRaisesRegex(AccessError, 'belongs to another user')`.
- **m3** (lectores de portal guardados): observación en la entrada del parche 28 y `SELECT` en
  [lab_e3_3879.md](lab_e3_3879.md), 8b, en el staging y en LIYBEN. **m4** (404 sin `X-Frame-Options`):
  aceptada, en la entrada del parche 27 (riesgo aceptado).
- **Script del laboratorio:** `scripts_e3/pruebas_e3p_lab.py` comprueba ahora que lo servido empieza por el
  prefijo (antes buscaba la `<meta>` detrás del `<head>` del diseño).

**Comprobaciones (29/10/2026):**

1. `py_compile` con Python 3.7.3 en la imagen (repo en solo lectura): `chatboo_canvas.py`, el test y el
   script del laboratorio, correctos.
2. `odoo_lint.py --revisar` de `chatboo_canvas.py` y del test: 0 incidencias nuevas.
3. Batería completa (log `tests-20261029-172402.log`): **420 tests, 18 F y 32 E**; los 50 que fallan, los
   mismos por nombre que en la línea base; los 34 de E3′, en verde.
4. Neutralización del 27 b, con el mismo método (copia, cambio, batería, restauración y SHA-256):

| Ejecución | Qué se retira | Resultado | Fallan (de E3′) | SHA-256 |
|---|---|---|---|---|
| N27b′ | `_with_csp` devuelve el diseño sin el prefijo (log `tests-20261029-172642.log`) | 36 F · 32 E | `test_canvas_shell`, `test_page_shell`, `test_canvas_download`, `test_page_download` y los **14 subtests** de `test_csp_prefix_cases` (4 + 14 = 18 F de más) | IGUAL |

La fila N27b de la tabla anterior es de la primera versión (rechazada).

#### Segunda revisión de E3′ (29/10/2026): APROBADA

- **Revisión acotada (`odoo-reviewer`)** de lo cambiado tras el rechazo (B1, m1 y m2): **APROBADO**, sin
  bloqueantes. Batería del revisor (log `tests-20261029-173855.log`): 420 tests, 18 F y 32 E, los mismos 50
  por nombre que la línea base; los 34 de E3′, en verde. Lint: 0 incidencias nuevas en lo revisado (las 3
  de `_paint_canvas` son las del fabricante, parche 25).
- **Lo que comprobó:**
  - el prefijo es el **último** paso en las cuatro salidas (`downloadable_page`, `:511-513`; `canvas_page`,
    `:563-569`, antes del escape de atributo); tema, ocultos, puente de impresión y botones quedan detrás;
    ningún otro camino sirve `design` ni `canvas_design` (rutas, vistas y JS); no quedan `_DOC_START_RE` ni
    `_HEAD_OPEN_RE` en los tres módulos;
  - **html5lib 1.1, 37 + 41 casos, 0 MAL**, en la descarga y en el `srcdoc` desescapado:
    [scripts_e3/csp_prefijo.py](scripts_e3/csp_prefijo.py) (37) y
    [scripts_e3/csp_adversario.py](scripts_e3/csp_adversario.py) (41: el diseño empieza por `</head>`,
    `</html>`, `<body>`, `<frameset>`, `<template>`, `<noscript>`, `<base>`, `<plaintext>`, `<xmp>`,
    `<textarea>`, `<title>`/`<style>`/`<script>` sin cerrar, texto suelto, NUL, comentario sin cerrar, CDATA,
    SVG, MathML, tablas, `<select>`, `<iframe>`, `<object>`, comillas, CR/LF, FF, `<` suelto, otra
    `<meta charset>`, una CSP más laxa, doctype de modo quirks o basura, BOM, `<?xml?>`, `<html manifest>` y
    tema de noche). En todos, los primeros nodos son `html`, `head`, la `<meta charset>` y la CSP: la CSP es
    el **segundo hijo de `<head>`**, detrás solo de la de `charset`, y el modo es **no-quirks**. En la
    descarga, html5lib elige utf-8 aunque el diseño traiga otro `charset`;
  - el diseño no puede anular la CSP: otra CSP se suma y solo endurece; `<base>` lo bloquea `base-uri
    'none'`; quitar la `<meta>` con un script no revoca la política. Lo que la CSP no cubre (autonavegación,
    WebRTC, DNS) sigue como riesgo aceptado del parche 27;
  - **m1 y m2:** la neutralización del 27 b falla en `assertTrue(served.startswith(prefix))`, con el
    documento sin prefijo en el mensaje. Variantes rotas a propósito de `_with_csp` contra
    `_assert_csp_served` y `B1_DESIGNS` (original 0/30; sin prefijo 30/30; quitando el doctype del diseño
    16/30; quitando BOM y espacios 2/30; CSP tras el doctype del diseño 30/30; prefijo sin `<meta charset>`
    30/30): los tests las detectan. El texto de m2 («belongs to another user») solo lo da
    `chatboo_session.py:1075`.
- **Observaciones aceptadas** (decisión de Sergio del 29/10/2026):
  - **m-a** (`chatboo_canvas.py:486-487`): `downloadable_page('   ')` devuelve el texto en blanco sin
    prefijo. No se llega: las cuatro rutas dan 404 si el diseño está vacío y `canvas_page` deja vacío el
    `srcdoc`;
  - **m-b** (`test_seges_chatboo_canvas.py:83-89`): el test comprueba el prefijo literal, no el árbol HTML5
    (la imagen no tiene html5lib; lo cubren los dos scripts). Si algún caso de `B1_DESIGNS` llevara tema de
    noche, la comprobación de «documento sin cambios» dejaría de coincidir, porque `_THEME_START` se
    inserta antes de cada script.
  - **m-c** (errata de la línea de `_with_csp` en la entrada del parche 27): corregida.
- **Estado de los parches 25 a 28:** aplicados; aprobados en revisión (29/10/2026). Siguiente: los commits y
  las pruebas manuales del laboratorio ([lab_e3_3879.md](lab_e3_3879.md)).

### Parche 29: el lienzo no guarda un DATA que no escribió el servidor (P-8e a)

- **Fecha:** 30/10/2026. **Origen:** prueba P-8e a del laboratorio, sobre el parche 27 a. Análisis,
  opciones y decisiones de Sergio: [e3_hallazgo_p8ea_3879.md](e3_hallazgo_p8ea_3879.md), apartados 5 y 7.
  HEAD de partida: `58885ce`.
- **Qué falla sin él (P-8e a, gravedad alta):**
  - Design recibe la muestra de las filas sin escapar (`sample_figures_for_design`) y puede copiarla en
    `const DATA`. Si un valor lleva `</script`, `_SCRIPT_INNER_RE` corta el script ahí, `raw_decode`
    falla y el servidor **no sustituye** DATA: se guarda el texto del modelo, con el valor en crudo.
  - Pasa lo mismo cuando DATA no es JSON, cuando se asigna con `let`, `var` o `window.DATA`, o cuando la
    repetición de Design falla y se queda el primer documento (`chatboo_session.py:1161-1166`).
  - En la edición sin filas no se volvían a meter las filas: el modelo podía desescapar las de la página
    abierta.
  - Impacto: quien puede poner nombre a un registro puede ejecutar un script en el marco de la página de
    otro usuario y navegarlo a una web externa (apartado 3.2 del hallazgo).
- **Cambio** (`pns_ai_chatboo/models/chatboo_canvas.py`, `pns_ai_chatboo/models/chatboo_session.py`):
  - **A y B, en un único punto:** una envoltura nueva, `place_rows_on_page` (`chatboo_canvas.py:2324`). La
    función del fabricante pasa a llamarse `_place_rows_on_page` (`:2347`), con su cuerpo sin cambios. Por la
    envoltura pasan `_paint_canvas` (y con él la repetición fallida) y `page_html` (skill capturada, caso h).
    Si hay bloques, la envoltura cambia el resultado por la página de rescate (`_finish_rescue(_page_for_rows(blocks))`,
    ya escapada) en dos casos, y deja una línea `_logger.info` sin los valores:
    - **A:** `_model_data_left` (`:1626`) recorre las asignaciones `const`/`let`/`var DATA =` y `window.DATA =`
      (`_DATA_ASSIGN_RE`, `:1601`) dentro de cada `<script>`, tal como lo corta el servidor. Va al rescate si
      alguna no es JSON legible, si su valor no es uno de los que escribe el servidor
      (`_server_data_values`, `:1611`: las filas planas, las de cada bloque o los bloques) o si hay
      asignaciones fuera de los scripts. No cuenta una asignación que solo pasa un nombre
      (`window.DATA = DATA;`, `_DATA_NAME_RE`, `:1606`): el nombre debe ir seguido de `;`, `,`, `)` o del
      final del script (`\Z`, sin `re.M`; aviso m1 de la revisión: con `$` y `re.M` bastaba un salto de
      línea para seguir con `.concat([…])` en la línea siguiente). Es la única coincidencia de una expresión
      regular que lleva a conservar el diseño, y solo excluye lo que no puede llevar cifras.
    - **B:** `_raw_value_left` (`:1682`) busca en crudo en el documento los valores (`_markup_values`, `:1651`)
      que, tras `strip`, tienen 3 caracteres o más y llevan `<`, `>` o `"` (`_MARKUP_UNSAFE`). Son las
      cadenas de las filas, recorridas en profundidad (también las que cuelgan de claves `_…`, que van en la
      muestra y en DATA: observación m3 de la revisión); sus claves públicas; el título de cada bloque, y el
      título de la página (`title` o `page_title`, el mismo que liga `const TITLE`). Sin repetidos, con un
      conjunto auxiliar (m8).
      Para los que llevan `<` o `>` busca también su forma de cadena JSON
      (`json.dumps(valor, ensure_ascii=…)[1:-1]`, con `False` y con `True`): copiado en una cadena JS, `"`
      pasa a `\"` y `ñ` puede pasar a `\u00f1`. Las dos formas conservan `<` o `>` en crudo, que el servidor
      nunca escribe: no dan falsos positivos (decisión de Sergio del 30/10/2026, tras la neutralización N29a).
    - **Sin falsos positivos con lo que escribe el servidor:** en los scripts, `_script_safe` escapa `<`, `>` y
      `&`, y `json.dumps`, `"`. En las tablas, `html.escape` escapa `<` y `>`, y ahora también `"`.
  - **Comilla en las tablas de rescate:** `_cell_html` (`:1117`) y `_rows_as_table` (`:1142`) pasan de
    `quote=False` a `quote=True`, para que B no salte con la tabla del propio servidor. `_page_shows_rows`
    (`:1315`) acepta también la forma `&quot;`. En pantalla no cambia nada. La premisa de la decisión
    («`&quot;` en el rescate») solo se cumplía en las cabeceras.
  - **C1:** `sample_figures_for_design` (`:916`) pasa la muestra por `_script_safe`. Si Design la copia tal
    cual, va escapada. `json.loads` devuelve los mismos valores.
  - **D:** en `_paint_canvas` (`chatboo_session.py:1095-1098`), si hay página abierta y no llegan filas, se
    leen las del `const DATA` de la página (`_rows_from_const_data(_const_data_value(page))`, después de
    `pictures_out`, así que las imágenes vuelven como `pns-img:N`). El título es `title` o
    `canvas_title`. Los dos se pasan a `place_rows_on_page` (`:1197`). La comprobación de centralización y
    la repetición siguen con las filas y el título del turno, como antes. Importaciones en `:1082-1083`.
  - **D, página abierta sin DATA legible de filas** (bloqueante B1 de la revisión; decisión de Sergio del
    30/10/2026, opción a con cierre; `chatboo_session.py:1096-1113` y `:1201-1210`):
    1. con DATA legible de filas, D como arriba;
    2. sin él, pero con la tabla del servidor en `#pns-page-rows` (diseño que no escribió DATA, o filas que
       no son diccionarios): `page_rows_texts` (`chatboo_canvas.py:1734`, con `_PageRowsText`, `:1709`, un
       `html.parser.HTMLParser` de la biblioteca estándar) extrae los textos de esa tabla, con las entidades
       decodificadas. Después de pintar, B se aplica con esos valores; si alguno queda en crudo, la
       edición se rechaza (`log_no_page`, «the change left a value of the page as markup») y la página
       anterior se queda;
    3. sin DATA legible ni tabla, o si la extracción falla o sale vacía: la edición sin filas se rechaza
       **antes** de llamar a Design («the open page has no figures to keep; change it with its rows»).
    - **Valores movidos fuera de la tabla** (observación n1 de la segunda revisión; decisión de Sergio del
      30/10/2026, opción b): en el caso 2 se añade a los valores que se comparan todo el texto visible de la
      página abierta, fuera de scripts y estilos, que ya decodificado lleva `<` o `>`
      (`page_markup_texts`, `chatboo_canvas.py:1766`, con `_PageMarkupText`, `:1750`; llamada en
      `chatboo_session.py:1113`). Pasa por el mismo `_markup_values` que B: 3 caracteres o más tras
      `strip`. Así, si una edición anterior sacó un valor de `#pns-page-rows` (escapado en su propio HTML),
      la siguiente no lo puede desescapar. El rechazo previo del caso 3 sigue dependiendo solo de la tabla.
    - `html.parser` solo sirve para saber qué valores buscar: una lista vacía no concluye que la página
      sea segura, sino que no hay con qué comprobar, y entonces se rechaza. Los elementos vacíos (`<img>`
      de las celdas con imagen, `<br>`…) no cuentan para la profundidad. Las excepciones del analizador
      con entradas raras (`AssertionError`, `NotImplementedError`, `ValueError`; por ejemplo `<![bogus`,
      comprobado con Python 3.7.3) dan lista vacía.
  - **Regla nueva en `_PAGE_RULES`** (`chatboo_canvas.py:73-75`), en inglés: «Put every value from DATA and
    TITLE on the page with textContent (or createTextNode): they are plain text. Never insert them with
    innerHTML, outerHTML, insertAdjacentHTML or document.write.» Llega a `DESIGN_SYSTEM` y a `EDIT_SYSTEM`.
- **Qué se degrada:**
  - un diseño cuyo DATA no se puede sustituir (no es JSON, `let`/`var`/`window.DATA` con otras columnas,
    filas que no son diccionarios) se cambia por la página de rescate, en lugar de guardarse con DATA
    vacío o con los datos del modelo;
  - un diseño que copia en crudo un valor de las filas o el título con `<`, `>` o `"` (3 caracteres o
    más) también va al rescate, aunque el valor sea inofensivo (`x > 5` en un rótulo). El mínimo de 3
    caracteres evita que `>` o `<5` coincidan con el propio HTML. Con 1 o 2 caracteres no se puede
    cerrar un `<script>` ni abrir `<!--`;
  - en una edición sin filas, el modelo ya no cambia los datos: DATA vuelve a ser el de la página abierta
    (lo que ya decía `edit_page`: «the figures already on it stay»). TITLE vuelve a ser el título de la
    pestaña, y la copia oculta y su vigilante se regeneran. Si la página abierta no tiene un DATA legible
    de filas, la edición sin filas solo se guarda si no deja en crudo ningún valor de la tabla del
    servidor; si tampoco hay tabla, se rechaza y hay que pedir el cambio con las filas (`page_url` o
    `page_edit` con `rows`). Una página guardada **antes** del parche cuya tabla tenga un valor con `"`
    (entonces se escribía con `quote=False`) rechazará también una edición inocente que la conserve;
  - **integridad de las cifras sin DATA** (observación n1): en una página sin DATA legible de filas, si el
    modelo vacía o cambia la tabla de `#pns-page-rows` en una edición, una edición sin filas posterior
    puede cambiar las cifras de esa tabla: el servidor no tiene las filas para volver a escribirlas. Es
    integridad de los datos, no seguridad. El cierre de n1 protege los valores con `<` o `>` que siguen en
    el texto visible de la página; **no cubre** los que una edición anterior dejó en un atributo, un
    comentario, un `<script>`, un `<style>` o codificados (observación o1 de la revisión acotada; residual
    de m6, en «Riesgos residuales»);
  - **texto con `<` o `>` en crudo en la página abierta** (por el cierre de n1): en una página sin DATA
    legible de filas, un texto visible de 3 caracteres o más con `<` o `>` escrito en crudo (`a > b`) se
    compara también; si la edición lo conserva tal cual, se rechaza (observación o2 de la revisión
    acotada: «Ver más ->» o «Total > 100» en un botón o un rótulo; con `&gt;` se guarda). Solo afecta al
    caso 2 de B1, la edición sin filas sobre una página sin DATA legible de filas: las guardadas antes del
    parche y las que, ya con él, salen sin DATA de filas (un diseño que no escribe DATA y se conserva tras
    la repetición, o filas que no son diccionarios). Las páginas cuyo DATA sustituye el servidor, que son
    el caso normal, van por el caso 1 y no se ven afectadas;
  - la página de rescate escribe `&quot;` en las celdas, sin cambio visible;
  - **falsos positivos de B** (observación m5 de la revisión): la búsqueda es por subcadena en todo el
    documento, también en el CSS y el JavaScript del diseño. Un valor `x > 5` coincide con un
    `if (x > 5)` del script, y un valor `<br>` con cualquier `<br>` del diseño: esos diseños van al rescate
    aunque el modelo no haya copiado el valor;
  - **valores que empiezan por `"` y no llevan otra comilla** (observación m4), por ejemplo `"Pepe`: van
    siempre al rescate, porque el DATA del servidor y el `ROWS` del vigilante los escriben como `\"Pepe`,
    que contiene `"Pepe`. No se corrige ignorando las apariciones precedidas de `\`: en un atributo HTML,
    `\"` **sí** cierra el valor (la barra no escapa nada en HTML), así que `data-x="\"Pepe…"` sería
    un falso negativo. Se prefiere el falso positivo.
- **Observación n2 de la segunda revisión (sin consecuencias):** `html.parser` no se comporta igual en
  Python 3.7.3 (el de la imagen) y en 3.12. Con 3.7.3, `<![bogus` o `<a b="` sin cerrar hacen que
  `page_rows_texts` devuelva `[]`, y la edición se rechaza antes de Design; un `<!--` sin cerrar sigue
  extrayendo la tabla (más valores de los que muestra el navegador: más estricto). Con 3.12, `<![bogus`
  extrae los valores y el rechazo llega después de Design. En ningún caso se acepta una edición hostil.
- **Riesgos residuales (aceptados, decisiones de Sergio del 30/10/2026):**
  - **`innerHTML` en el código del diseño:** `_script_json` solo protege al analizador HTML. Si el
    JavaScript del diseño pinta un valor con `innerHTML`, `insertAdjacentHTML`, `outerHTML` o
    `document.write`, un nombre como `<img src=x onerror=…>` se ejecuta en el marco. El servidor no puede
    garantizarlo leyendo el JavaScript. Lo reducen la regla nueva y la contención actual (sandbox y CSP
    del parche 27); el impacto es el del apartado 3.2 del hallazgo;
  - **comilla simple en atributos:** B no revisa `'`. Un valor con `'` copiado en crudo en un atributo
    entre comillas simples puede añadir un manejador en línea. Mismo impacto y misma contención;
  - **páginas ya guardadas antes del parche:** el parche actúa al pintar y al guardar, no al servir. Un
    `canvas_design` o un `design` de página compartida guardado antes, con DATA del modelo, se sigue
    sirviendo igual (con la CSP del parche 27) hasta que se vuelva a pintar. Se miden con el fragmento
    del final de esta entrada;
  - un valor inventado por el modelo (que no está en las filas), fuera de cualquier asignación de DATA y
    escrito en el HTML o en otro script: no lo detecta ni A ni B;
  - **copias modificadas de un valor real** (observación m6): el modelo lo cambia de mayúsculas o de
    espacios, lo recorta, lo parte en trozos que el JavaScript concatena o pasa sus entidades a crudo
    (`&lt;` → `<`). B solo reconoce el valor exacto y sus dos formas JSON. En DATA lo cubre A; fuera de
    DATA, no. Tampoco lo cubre el cierre de n1 cuando una edición anterior sacó el valor de la tabla y lo
    dejó en un atributo, un comentario, un `<script>`, un `<style>` o codificado (por ejemplo, en base64),
    y una edición posterior lo desescapa (observación o1; comprobado en 5 casos de html5lib). Mismo
    impacto y misma contención que `innerHTML`;
  - **HTML del código del orquestador en `page_html`** (observación m7, preexistente y fuera del alcance de
    P-8e a): el helper `page_html(html, rows)` (`chatboo_session.py:901`) guarda el HTML que escribe el
    código del turno. A y B solo comprueban las filas y el título: el HTML que el propio código trae
    (sin pasar por Design) se guarda tal cual, con la CSP del parche 27;
  - las etiquetas reales del prompt de repetición y del log (`chatboo_session.py:1140-1152`) y las líneas
    `Page title:` y `Company:` del prompt siguen en crudo. No es HTML.
- **Cómo comprobar si el fabricante ya lo ha corregido:**
  ```sh
  grep -n "def sample_figures_for_design" -A30 pns_ai_chatboo/models/chatboo_canvas.py | grep -n "u003c\|_script_safe"; grep -n "def place_rows_on_page" -A25 pns_ai_chatboo/models/chatboo_canvas.py | grep -n "rescue\|_page_for_rows"
  ```
  Corregido si la muestra a Design va escapada y si un diseño cuyo DATA no se puede sustituir no se guarda
  tal cual.
- **Tests** (`TestSegesCanvasModelData`, 15, `test_seges_chatboo_canvas.py:488`). El simulador de Design
  devuelve una lista de respuestas, en orden:
  - `test_sample_copied_evil_first` y `test_sample_copied_comment_first`: Design copia la muestra en
    `const DATA`, sin escapar, con `EVIL` y `EVIL_COMMENT` en los dos órdenes y una fila inventada; la
    repetición devuelve lo mismo (cubre `:1161-1166`). Resultado: 2 llamadas, rescate sin ruptura, DATA
    con las filas reales;
  - `test_sample_copied_retry_error`: la repetición da `HTTP 503`, como en el laboratorio. Resultado:
    rescate;
  - `test_data_not_written_by_server` (5 subtests, filas inocentes): DATA sin comillas en las claves,
    fila inventada con `</script>`, `let DATA` y `window.DATA` con otras columnas, y `var DATA = JSON.parse(…)`.
    Resultado: rescate (solo A);
  - `test_data_forms_bound_kept` (control, 2 subtests): `window.DATA = DATA;` y un `let DATA` que el
    servidor sí sustituye. Resultado: se conserva el diseño;
  - `test_raw_value_in_markup` (7 subtests): DATA sustituible con `EVIL`, `EVIL_COMMENT`, una `"` copiada
    en un atributo, o el título en `<title>`, en crudo en el HTML; o, fuera de DATA, un `const SAMPLE = […]`
    con `EVIL` (`ensure_ascii=False`) o con `Señor <b>"P29"</b>` (`ensure_ascii=True`). Resultado: rescate.
    Con `R&D Ltd` en crudo, se conserva el diseño;
  - `test_page_html_hostile_template`: skill capturada (`page_html`) con la muestra copiada. Resultado:
    rescate;
  - `test_edit_rebinds_rows` (D): edición sin filas cuyo DATA lleva `EVIL_COMMENT` en crudo. Resultado: se
    conserva el diseño y DATA vuelve a tener las filas de la página;
  - `test_edit_unescaped_data` y `test_edit_raw_value_in_markup` (D con A y B): `EVIL` en crudo en DATA o
    en el HTML. Resultado: rescate con las filas de la página;
  - `test_edit_page_without_data` (B1 y n1, 6 subtests, `:643`): página abierta sin DATA legible de filas,
    generada con `place_rows_on_page` (premisa comprobada: sin filas en DATA y con `EVIL` en la tabla). (2)
    inocente: una edición que cambia el fondo y conserva la tabla escapada se guarda (revisión 2). (2)
    hostil, sobre un diseño sin DATA y sobre un rescate de filas escalares: `EVIL` en crudo en el HTML. Se
    rechaza: sin URL, revisión 1 y la página sin cambios. (3) sin DATA ni tabla: se rechaza sin llamar a
    Design. n1, en dos pasos: la edición 1 vacía la tabla y lleva `EVIL`, escapado, a su propio `<p>` (se
    guarda, revisión 2); la 2 lo desescapa y se rechaza (revisión 2, página del paso 1). Control inocente:
    la 2 cambia el fondo y conserva el valor escapado, y se guarda (revisión 3);
  - `test_design_prompt_escaped` (C1): el prompt no lleva `</script` ni `<!--<script`, y la muestra se
    decodifica con los valores originales;
  - `test_normal_design_kept` (control): filas inocentes. Resultado: una sola llamada, diseño conservado,
    DATA = filas;
  - `test_hostile_rows_design_kept` (control de falsos positivos): filas con `EVIL`, `EVIL_COMMENT`, `R&D`,
    `&amp; Co`, `O'Brien`, `Seges "P29"` y `x > y`, título con `EVIL` y comillas. Resultado: se conserva el
    diseño. Además, A y B no saltan con la página de rescate;
  - `test_design_rule_text_content`: la regla está en `_PAGE_RULES`, `DESIGN_SYSTEM` y `EDIT_SYSTEM`.

**Comprobaciones (30/10/2026):**

1. `py_compile` con Python 3.7.3 en la imagen `odoo-dev:14-lab_pns_ai_3879` (repo en solo lectura):
   `chatboo_canvas.py`, `chatboo_session.py` y el test, correctos.
2. `python3 ~/.claude/hooks/odoo_lint.py --revisar` de los tres archivos: **0 incidencias nuevas** (101 y 150
   preexistentes en los modelos). Para no añadir ninguna, la línea de `_rows_as_table` pasa a f-string y la
   de `_page_shows_rows` usa una tupla.
3. Batería completa (`odoo-dev 14 tests pns_ai_mcp,pns_ai_chatboo`, log `tests-20261030-160902.log`):
   **434 tests, 18 F y 32 E**. Los 50 que fallan son, por nombre, los mismos que en la línea base de E3′
   (`tests-20261029-172402.log`: 420 · 18 F · 32 E); los **14 nuevos**, en verde. El `ERROR` de `ir_attachment`
   (`create_uid` 186) también está en la línea base.
4. Marcadores: `grep -rn "Seges: parche 29 (" pns_ai_chatboo --include=*.py | grep -v /tests/` da **11 líneas**
   (8 en `chatboo_canvas.py` y 3 en `chatboo_session.py`).
5. Neutralización por partes: script `neutralizar_p29.py` en el scratchpad de la sesión
   (`/tmp/claude-1000/-home-soporte-GitHub-third-party/abe8eb70-5464-4d0f-8f3d-4311258d195a/scratchpad/`), con el
   método de E3′ (copia, cambio, batería completa, restauración y SHA-256). **Tabla sustituida el 30/10/2026**
   tras la revisión (aviso m2: la primera tabla era anterior a la ampliación de B). Todas las ejecuciones
   sobre el código final, con B1, m1, m3 y m8. Referencia: **435 · 18 F · 32 E** (log
   `tests-20261030-170201.log`). En ninguna desaparece un F o un E de la línea base, y el SHA-256 de cada
   archivo restaurado es **IGUAL** en las siete.

| Ejecución | Qué se retira | Log | Resultado | Fallan (del parche 29) |
|---|---|---|---|---|
| N29a | A (`_model_data_left` no se consulta) | `tests-20261030-170443.log` | 23 F · 32 E | los 5 subtests de `test_data_not_written_by_server`. `test_edit_unescaped_data` ya no falla: lo detecta la forma JSON de B |
| N29b | B (`_raw_value_left` no se consulta en la envoltura) | `-170727` | 25 F · 32 E | 6 subtests de `test_raw_value_in_markup` (el de `R&D Ltd` pasa, es control); `test_edit_raw_value_in_markup` |
| N29ab | A y B | `-171020` | 35 F · 32 E | los 11 subtests anteriores; `test_sample_copied_evil_first`, `test_sample_copied_comment_first`, `test_sample_copied_retry_error`, `test_page_html_hostile_template`, `test_edit_unescaped_data`, `test_edit_raw_value_in_markup` |
| N29c1 | C1 (muestra sin `_script_safe`) | `-171306` | 19 F · 32 E | `test_design_prompt_escaped` |
| N29d | D entero (edición sin filas sin volver a meter las filas; arrastra B1) | `-171546` | 24 F · 32 E | `test_edit_rebinds_rows`, `test_edit_unescaped_data`, `test_edit_raw_value_in_markup`; 3 subtests de `test_edit_page_without_data`: (2) hostil, (2) hostil con filas escalares y (3) |
| N29e | B1 (`if not _blocks_for_page(bind_rows):` pasa a `if False:`) | `-171833` | 21 F · 32 E | los 3 subtests de `test_edit_page_without_data`: (2) hostil, (2) hostil con filas escalares y (3); el (2) inocente pasa |
| N29f | cierre de n1 (`kept_texts += page_markup_texts(page)` pasa a `kept_texts += []`) | `tests-20261030-174048.log` | 19 F · 32 E | el subtest «dos pasos, hostil» de `test_edit_page_without_data`; «dos pasos, inocente» pasa |
| N29q | `_cell_html` vuelve a `quote=False` | `-172129` | 20 F · 32 E | `test_hostile_rows_design_kept` y el subtest de control `R&D Ltd` de `test_raw_value_in_markup` (las filas de ese test llevan otros valores con `"`, que la tabla deja en crudo: falso positivo de B con su propia tabla) |

- La regla de `textContent` no se neutraliza: es un texto, y la comprueba `test_design_rule_text_content`.
- Pasan con y sin cada cierre (controles): `test_data_forms_bound_kept`, `test_normal_design_kept`,
  `test_hostile_rows_design_kept` (salvo N29q), `test_design_rule_text_content`, el subtest de `R&D Ltd`
  (salvo N29q) y el subtest (2) inocente de `test_edit_page_without_data`.

**Observación de la neutralización N29a (decidida el 30/10/2026: opción 2, aplicada; ver el bloque del final):**

- **Problema:** B busca cada valor tal cual. Cuando el modelo copia un valor con `"` dentro de una cadena
  JavaScript o JSON, ese valor aparece con `\"`, no literal. Por eso, con A retirado, B no detecta el `EVIL`
  copiado en el DATA de la edición (`test_edit_unescaped_data`).
- **Con A activo, el caso queda cerrado:** el script cortado deja un DATA ilegible y la página va al rescate.
  Es un hueco de B **como defensa en profundidad**: queda sin cubrir, por ejemplo, un `const SAMPLE = […]`
  (caso f) con un valor de las filas que lleva `</script` y comillas.
- **Reproducción:** retirar A (`if False:` en lugar de `if _model_data_left(page, blocks):`) y ejecutar
  `test_edit_unescaped_data`.
- **Opciones:**
  1. aceptarlo como está (A lo cubre en DATA);
  2. que B, para los valores con `<` o `>`, busque también su forma de cadena JSON
     (`json.dumps(valor, ensure_ascii=False)[1:-1]`). No da falsos positivos con lo que escribe el
     servidor, que escapa `<` y `>` como `\u003c` y `\u003e`. Coste: una línea en `_raw_value_left` y un
     subtest.
     - Para los valores que solo tienen `"`, la forma JSON (`\"`) coincide con el DATA del servidor y daría
       siempre rescate. Por eso quedan fuera.
- **Recomendación:** la opción 2.

**Fragmento de solo lectura para medir las páginas ya guardadas** (`odoo-dev 14 shell` en el laboratorio;
en el staging y en LIYBEN, en su `odoo shell`). Lleva sus propios patrones, así que funciona también donde no
está el parche 29. Cuenta, con sus ids, los diseños con alguna asignación de DATA (`const`/`let`/`var`/`window`)
que no es JSON legible dentro de su `<script>`. No escribe nada y termina con `rollback`.

```python
import json, re
SCRIPT = re.compile(r'(<script\b[^>]*>)(.*?)(</script>)', re.I | re.S)
ASSIGN = re.compile(r'(?:\b(?:const|let|var)\s+|\bwindow\s*\.\s*)DATA\s*=(?!=)\s*')
NAME = re.compile(r'[A-Za-z_$][\w$.]*\s*(?:[;,)]|\Z)')
dec = json.JSONDecoder()

def data_ilegible(page):
    text, seen = page or '', 0
    for match in SCRIPT.finditer(text):
        inner = match.group(2)
        for hit in ASSIGN.finditer(inner):
            seen += 1
            if NAME.match(inner, hit.end()):
                continue
            try:
                dec.raw_decode(inner, hit.end())
            except ValueError:
                return True
    return len(ASSIGN.findall(text)) > seen

for model, field in (('chatboo.session', 'canvas_design'), ('chatboo.canvas.page', 'design')):
    recs = env[model].sudo().with_context(active_test=False).search([(field, '!=', False)])
    ids = [rec.id for rec in recs if data_ilegible(rec[field])]
    print(model, field, len(recs), 'con diseño;', len(ids), 'con DATA ilegible:', ids)
env.cr.rollback()
```

Mide lo que mide A sin las filas. Un DATA del modelo que sí es JSON (la muestra copiada sin `</script`) no
se puede distinguir del del servidor sin las filas de ese turno, así que no se cuenta.

**Ampliación de B tras la observación de N29a (decisión de Sergio del 30/10/2026, opción 2):**

- **Cambio:** `_raw_value_left` (`chatboo_canvas.py:1682-1700`) busca, para los valores con `<` o `>`, también
  `json.dumps(valor, ensure_ascii=False)[1:-1]` y `json.dumps(valor, ensure_ascii=True)[1:-1]`.
- **Tests:** dos subtests nuevos en `test_raw_value_in_markup` (`const SAMPLE` fuera de DATA, con `EVIL` y con
  un valor no ASCII escrito con `ensure_ascii=True`). Resultado: rescate. Siguen siendo 14 tests.
- **Comprobaciones:** `py_compile` con 3.7.3 y lint `--revisar` (0 nuevas). Batería completa (log
  `tests-20261030-163625.log`): **434 tests, 18 F y 32 E**, los mismos 50 por nombre que la línea base; los 14
  del parche 29, en verde.
- **Neutralización N29b repetida** (log `tests-20261030-163859.log`, SHA-256 IGUAL): **25 F · 32 E**. Fallan los
  **6** subtests de rescate de `test_raw_value_in_markup` (los 4 anteriores y los 2 de `const SAMPLE`; el de
  `R&D Ltd` pasa, es control) y `test_edit_raw_value_in_markup`. Superada por la neutralización completa
  tras la revisión (tabla del punto 5).

#### Revisión del parche 29 (30/10/2026): B1 y avisos m1 a m8

- **Revisión (`odoo-reviewer`): RECHAZADO** por un bloqueante, **B1**: edición sin filas sobre una página sin
  `const DATA` legible de filas, sin A ni B (detalle y corrección en «Cambio», D). Arnés html5lib del revisor:
  56 casos y 3 de datos reales; con el parche, 44 BIEN y 12 MAL (2 de B1, 7 residuales y 3 falsos
  positivos); con `58885ce`, 45 MAL de 56. La copia real de la sesión 11 (`~/lab_e3p/p8ea_sesion11.html`)
  da BIEN en sus tres modos.
- **Decisiones de Sergio (30/10/2026):** B1, opción a con cierre; m1, m3 y m8, aplicados; m4, m5, m6 y m7,
  documentados en «Qué se degrada» y «Riesgos residuales»; m2, neutralización completa repetida (tabla del
  punto 5, sustituida).
- **Comprobaciones:**
  1. `py_compile` con Python 3.7.3 en la imagen: los tres archivos, correctos.
  2. Lint `--revisar` de los tres archivos: **0 incidencias nuevas**. El `except` de `page_rows_texts` se
     limita a `AssertionError`, `NotImplementedError` y `ValueError`.
  3. Batería completa (log `tests-20261030-170201.log`): **435 tests, 18 F y 32 E**, los mismos 50 por nombre
     que la línea base (`tests-20261029-172402.log`); los **15** del parche 29, en verde.
  4. Marcadores: `grep -rn "Seges: parche 29 (" pns_ai_chatboo --include=*.py | grep -v /tests/` da **13
     líneas** (9 en `chatboo_canvas.py`, con la importación de `HTMLParser`, y 4 en `chatboo_session.py`).
  5. Neutralización completa: tabla del punto 5.

#### Segunda revisión del parche 29 (30/10/2026): APROBADO CON OBSERVACIONES; cierre de n1

- **Segunda revisión (`odoo-reviewer`):** APROBADO CON OBSERVACIONES, sin bloqueantes. B1, en 41 casos de
  html5lib (`b1_p29.py`): 40 BIEN y 1 MAL, que es n1. Arnés completo: 47 BIEN y 9 MAL, todos residuales o
  falsos positivos documentados (m4, m5 y m6), salvo uno que es del propio arnés. Batería del revisor (log
  `tests-20261030-172540.log`): 435 · 18 F · 32 E, los mismos 50.
- **Decisiones de Sergio (30/10/2026):** n1, opción b (cierre en «Cambio», D); n2, observación sin
  consecuencias; integridad de las cifras sin DATA, en «Qué se degrada».
- **Comprobaciones del cierre de n1:**
  1. `py_compile` con Python 3.7.3: los tres archivos, correctos. Lint `--revisar`: 0 incidencias nuevas.
  2. Batería completa (log `tests-20261030-173803.log`): **435 tests, 18 F y 32 E**, los mismos 50 por nombre
     que la línea base; los 15 del parche 29, en verde.
  3. Marcadores: **14 líneas** (9 en `chatboo_canvas.py` y 5 en `chatboo_session.py`).
  4. Neutralización N29f: fila nueva de la tabla del punto 5. Las demás filas se ejecutaron antes de este
     cierre y no se han repetido. El código nuevo está dentro de la rama que retiran N29d y N29e, y
     ninguna otra ejecución lo toca.

#### Revisión acotada del cierre de n1 (30/10/2026): APROBADO CON OBSERVACIONES

- **Revisión (`odoo-reviewer`):** solo el cierre de n1, su test y N29f. Sin bloqueantes.
  - Arnés de B1 (`b1_p29.py`): 41 BIEN y 0 MAL. Sin el cierre, «dos pasos, paso 2» vuelve a MAL.
  - Casos del cierre (`n1_cierre.py`): 17 casos, 12 BIEN y 5 MAL. Los 5 son o1. Página grande (212 KB):
    0,17 s de extracción y 1,9 s de edición. Entradas raras con Python 3.7.3: ninguna excepción sin capturar.
  - Confirma que las demás filas de neutralización no hacía falta repetirlas (simulado en una copia aislada).
  - Batería del revisor (log `tests-20261030-174458.log`): 435 · 18 F · 32 E, los mismos 50; los 15 del
    parche 29, en verde. Lint: 0 incidencias nuevas. Marcadores: 14.
- **Observaciones:**
  - **o1:** el registro describía el cierre como más amplio de lo que es. Corregido en «Qué se degrada» y
    añadido a m6 en «Riesgos residuales».
  - **o2:** falso positivo con `->` o `>` en crudo en el texto. Precisado en «Qué se degrada».
- **Decisión de Sergio (30/10/2026):** opción a, solo documentación; sin cambios de código.

- **Estado:** parche 29 **aprobado** el 30/10/2026. Pendiente del commit y de las pruebas del laboratorio
  ([lab_p29_3879.md](lab_p29_3879.md); [e3_hallazgo_p8ea_3879.md](e3_hallazgo_p8ea_3879.md), apartado 6).
