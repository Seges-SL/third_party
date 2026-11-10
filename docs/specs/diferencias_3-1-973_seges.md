# Diferencias: módulos del fabricante 3.1.973 frente a la versión corregida por Seges

- **Comparado:** `pns_base` 1.2.69, `pns_ai_mcp` 3.1.973 y `pns_ai_chatboo` 2.1.587 (fabricante) frente a
  la rama `14.0-pns-ai-3879`, módulos de `8d218ea` (3.1.879 con los parches de Seges 10 a 34).
- **Fuente:** `docs/specs/comparacion_pns_ai_3-1-973.md` (sha256 `a7cc03a9…`, con las 23 correcciones de
  la verificación independiente aplicadas el 10/11/2026), §3, §4, §6 y §7. Sin análisis nuevo: cada fila
  remite a su sección.
- **«Encaje»:** cómo quedaría el parche sobre el código de 3.1.973: aplica igual, con ajustes o hay que
  reescribirlo.

## 1. Corregido por Seges y también por 3.1.973 (parches que sobran)

| Parche | Hallazgo | Cómo lo corrige 3.1.973 | Frente al parche | Ref. |
|---|---|---|---|---|
| 10 | PNS-83 (`collect_pin`) | `_collect_pin` privado; además `_touch`, `_close` y `_supply` | Mismo criterio, más amplio | §3.1, §4 |
| 13 | M10 (plan con la identidad de otro) | `create` solo en `su`; `_cleanup_stuck_state` privado; el plan corre como quien lo pidió | Mismo criterio | §3.1, §4 |
| 14 | M13 (borrado de contextos de fábrica) | `_unlink_retired_from_module` privado | Mismo criterio | §3.1, §4 |
| 23 | PNS-101 y PNS-36 (escape del sandbox) | `GuardedSandboxEnv` con lista blanca, bloqueo por clase de cursores y registros, lectura de atributos reescrita en el AST, formateador propio | Otro criterio, más amplio. Restos sin vía de ataque conocida: `itemgetter` nativo, `Markup` con campos simples, `with_context`/`with_company` envueltos. Parte de los tests de Seges no queda cubierta (§9, P-6) | §3.1, §3.7, §4 |
| 30 | M11 (`log_*` a nombre de otro) | Los seis `log_*`, privados | Otro criterio: cierra la llamada por nombre (RPC, portal y caja A); no comprueba el `user_id` por dentro, sin llamador afectado | §3.5, §4 |
| 31 | M12 (`chat_completion` directo) | `_chat_completion` privado | Ídem | §3.5, §4 |

## 2. Corregido por Seges y no, o solo en parte, por 3.1.973 (parches que siguen haciendo falta)

| Parche | Hallazgo | Qué sigue abierto en 3.1.973 | Encaje | Ref. |
|---|---|---|---|---|
| 11 | PNS-82 | `unlink` de la sesión de Chatboo borra en `sudo` todos sus adjuntos | Con ajustes | §3.1, §4 |
| 12 | PNS-01/02 (grupos por plan) | **En parte, otro criterio:** 3.1.973 exige al solicitante el permiso de Odoo «Permisos de acceso» y nada a quien confirma; Seges exige Ajustes a quien ejecuta, propone y confirma. Compatibles: gana el más estricto | Con ajustes | §3.1, §6.3 |
| 15 | PNS-07 | **En parte:** 19 de los 28 métodos cerrados; 9 siguen públicos y fuera de la lista (parte los frena la puerta de catálogos) | Con ajustes | §3.1, §3.7 |
| 16 | PNS-54 | `action_confirm_and_execute` sin contraseña; `card_payload` da token a quien puede leer la operación. Nuevo: la tarjeta reintenta sola tras un rechazo (no choca con el parche) | Con ajustes | §3.1, §6.1 |
| 17 | PNS-37 (papelera del diario) | `ai_change_journal.py` idéntico; el paso `unlink`, movido a `safe_plan_execute.py` | Aplica igual (ese paso, con ajustes) | §3.5, §4 |
| 18 | PNS-19 (columnas secretas en la caja A) | **En parte, otro criterio:** 3.1.973 cierra por nombre las columnas secretas de todos los modelos (más amplio en modelos), pero no en lecturas `su` ni con valores ya en caché (NUEVO-1). Seges: solo campos de identificación de 11 modelos, también en `sudo`, y vacía la caché al abrir la caja A | **Reescribir:** la marca tendría que ir en `open_readonly_env` (las skills pasan por ahí) | §3.1, §3.4, §4 |
| 19 | PNS-17 | En una redirección a otro host se reenvían las cabeceras que no son de autenticación; el cliente MCP sigue redirecciones | Con ajustes | §3.1, §4 |
| 20 | PNS-70 (Chart.js) | Archivos idénticos a 3.1.879 | Aplica igual | §3.1, §4 |
| 21 | PNS-20 | `action_preview` igual | Aplica igual | §3.1, §4 |
| 22 | PNS-100 | **En parte:** 3.1.973 añade 7 nombres a la lista del sandbox; faltan 21 de los 28 de Seges | Con ajustes | §3.1, §4 |
| 24 | PNS-102 (`env.user` como superusuario) | `user` y lo que cuelga de él siguen como superusuario; con un agravante: el guardián de columnas secretas no actúa en `su`. `company` y `companies` ya no, salvo si el usuario no tiene compañía activa (entonces vuelven a salir como superusuario) | Con ajustes | §3.1, §4 |
| 25 | M1 (`paint_canvas`) | **En parte:** `_paint_canvas` privado, pero sin comprobación de dueño dentro | Con ajustes | §3.5, §4 |
| 26 | M2 (imágenes en `sudo`) | `pictures_as_tokens` sigue en `sudo` | Con ajustes | §3.5, §4 |
| 27 | F1 (lienzo) | **En parte:** CSP del fabricante en la cabecera HTTP (otra política; abre imágenes y conexiones al propio origen); datos dentro de `<script>` sin escapar; descargas sin CSP | Con ajustes en el modelo; reescribir la parte de las rutas | §3.5, §3.7, §4 |
| 28 | D1 (páginas compartidas) | **En parte:** `owner_id` lo cierra el fabricante (más amplio); siguen sin comprobación los lectores internos y la regla del AI Administrator con escritura y alta | Con ajustes | §3.5, §4 |
| 29 | F1, P-8e a | Muestra para Design sin escapar; la página guardada no se comprueba | Con ajustes | §3.5, §4 |
| 32 | PNS-97 (acciones de confianza) | CRUD del AI Administrator igual; nuevo `_require_settings`, pero solo en tres métodos `_apply_*` | Con ajustes | §3.5, §6.4 |
| 33 | PNS-29 resto 3 | `month_usage` público; asistente sin comprobación de ACL | Con ajustes | §3.5, §4 |
| 34 | PNS-96 (aviso del lienzo) | `log_no_page` sigue sin aviso al turno | Con ajustes | §3.5, §4 |

Tests de Seges que tocan código movido o reescrito: §4.1 (7 archivos tocan código reescrito; 8 si se
cuenta `test_seges_chatboo_canvas.py`, afectado en parte por la CSP del fabricante). Cinco archivos de
test de los parches 23 y 24 importan `_StubController` de un módulo que depende del parche 18: sin el 18
no cargan.

## 3. Corregido por 3.1.973 y no por Seges

| Qué | Hallazgo | Gravedad | Ref. |
|---|---|---|---|
| Un AI Administrator sin Ajustes ya no puede generar, fijar o importar la clave MCP de un administrador de Ajustes (también por `create`/`write` del hash y por la importación de configuración) | NUEVO-3 | Alta | §3.4 |
| El asistente de exportación de `pns_base` solo borra adjuntos de exportación del propio usuario. En nuestra versión, cualquier interno borra cualquier adjunto, aunque sea solo creando el asistente (la limpieza de transitorios lo borra como superusuario) | NUEVO-4 | Alta | §3.4 |
| `_static_str` funciona en Python 3.7 | PNS-81 resto | Alta (funcional) | §3.1 |
| Comprobación del equipo que contesta, contra el DNS *rebinding* (`fetch_url_safe`, `remote_image`) | PNS-17 y PNS-59 (resto menor) | — | §3.1, §3.3 |
| El código de las skills corre en una caja A propia, de solo lectura | PNS-06 (más amplio) | — | §3.2 |
| Columnas secretas cerradas en la caja A, también para ordenar y agrupar | Hoja 21; `iap.account.account_token` | Baja | §3.5 |
| `command_args` con grupo; `ensure_ai_admin` en `action_suggest_detection` | PNS-08/09 (más amplio) | — | §3.2 |
| `ai.safe.choice` de solo lectura para internos; reglas de `ai.skill.param.cache` | PNS-14 (más amplio) | — | §3.2, §7.3 |
| La sesión de Chatboo no cambia de dueño fuera de `su` | PNS-55, PNS-56 | — | §3.2 |
| Asistente «¿incluir secretos?» de `pns_base`: no deja cambiar modelo, ids ni método | Endurecimiento | — | §3.4 |
| `_touch`, `_close` y `_supply` de la mesa del PIN, privados | PNS-84 (en parte) | — | §3.5 |
| **Multicompañía:** la IA trabaja en las compañías marcadas en la pantalla. En nuestra versión no se fija `allowed_company_ids`: lee todas las compañías del usuario y crea en la de por defecto, salvo los planes confirmados desde Autorizaciones, que usan la compañía activa de quien confirma | Alcance de compañía | — (funcional) | §5.4, §6.7 |

## 4. Lo que 3.1.973 cambia o abre de nuevo

**Hallazgos nuevos de 3.1.973**

| Id | Gravedad | Qué | Ref. |
|---|---|---|---|
| NUEVO-1 | Alta | La protección de columnas secretas no cubre valores ya en la caché del hilo (en nuestra versión lo cubre el parche 18). REQUIERE PRUEBA | §3.4 |
| NUEVO-2 | Baja | Tras el `-u`, los dos crons de purga siguen llamando a `gc_expired`, que ya no existe | §3.4 |
| NUEVO-5 | Baja | Sin proveedor con el rol Diseño, diseña la cadena de Conversación (la alternativa viene activa) y aparece el botón Canvas | §7.2 |

**Cambios de comportamiento**

| Cambio | Efecto frente a nuestra versión | Ref. |
|---|---|---|
| AI Administrator implica AI Conversational | El `-u` da acceso conversacional a todos los AI Administrators existentes | §6.2 |
| El plan se ejecuta como quien lo pidió y en sus compañías | Cambia quién necesita permisos (ver parche 12) | §6.3 |
| La tarjeta de confirmación reintenta sola una vez | Un Confirmar pulsado antes de los 5 s acaba confirmando sin segundo clic | §6.1 |
| Roles de proveedor en lugar de las casillas `fit_*` | `fit_design` desaparece; el `-u` pasa las casillas a roles; «Design solo en X» exige además desactivar la alternativa del rol Diseño | §6.6 |
| `_require_settings` en acciones de vistas y campos | Aplicarlas exige Ajustes al usuario real | §6.4 |
| El env del sandbox ya no expone `is_admin`, `is_system` ni `su` | Puede afectar a código que los use | §4 (parche 23) |

**Lo que hace el `-u` desde nuestra versión** (§7.3): casillas `fit_*` → roles (tabla temporal, columnas
borradas); tablas y columnas nuevas (roles, `pns.progress.job`, compañías en Chatboo, `result_note`);
AI Conversational propagado a los AI Administrators; `ai.safe.choice` de solo lectura; el asistente
«¿incluir secretos?» pierde el alta; reglas nuevas; se borran las 7 skills de fábrica retiradas sin dueño
(con su caché) y se crean 4; **se reescriben los contextos de fábrica sin dueño de 12 archivos, entre ellos
`core/system_prompt.xml`**; crons de NUEVO-2. Ningún script de `migrations/` se ejecuta.

**Funciones nuevas** (§5): facturas de proveedor desde un adjunto y `/bill-draft`; `/sales-board`,
`top_sales` y `users`; roles de proveedor con alternativa; multicompañía; marca «generado por IA»; pegar
imágenes con Ctrl+V; `pns.progress.job` (sin uso en los tres módulos).

## 5. Abierto en las dos versiones (sin parche de Seges ni corrección del fabricante)

| Hallazgo | Gravedad | Situación en la rama de Seges | Ref. |
|---|---|---|---|
| PNS-26 (`commit()` sobre el cursor del llamador) | Alta | Al informe | §3.1 |
| PNS-23 (skills importadas activas, `skill_skip_body_check`) | Alta | Aceptado | §3.1 |
| PNS-18 (failover fuera de la cadena) | Alta | Aceptado (D10). En 3.1.973, la alternativa de rol amplía además los candidatos | §3.1 |
| PNS-99 (`remove_group` da `ok` sin quitar el grupo) | Media | Aceptado | §3.5 |
| PNS-33 resto (clave MCP elegida o hash) | Media | Aceptado | §3.5 |
| PNS-61, PNS-28 | Media | Aceptados u observación | §3.5 |
| PNS-84 resto (PIN y clave legibles por el AI Administrator) | Media | Aceptado | §3.5 |
| PNS-98 (adjuntos en cursor propio) | Baja | Al informe | §3.5 |
| M5, M16, PNS-51, PNS-88, F4, hoja 17 | Baja | Aceptados o al informe | §3.5 |
