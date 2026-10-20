# CONFIDENCIAL — Seguimiento del informe técnico de seguridad (continuación de la entrega del 15/10): pns_base 1.2.32, pns_ai_mcp 3.1.782 y pns_ai_chatboo 2.1.453 (Odoo 14.0)

> **Borrador.** Pendiente de revisión interna antes de su envío.

| | |
|---|---|
| **Destinatario** | PATANEGRA Soft |
| **Módulos** | `pns_base` 1.2.32 · `pns_ai_mcp` 3.1.782 ("AI Engine") · `pns_ai_chatboo` 2.1.453 ("Chatboo") |
| **Plataforma** | Odoo 14.0 |
| **Informe anterior** | Informe técnico de seguridad del 2026-10-08 sobre `pns_base` 1.2.10, `pns_ai_mcp` 3.1.486 y `pns_ai_chatboo` 2.1.322 (PNS-01 a PNS-80) |
| **Entrega intermedia** | Seguimiento del 2026-10-15 (PNS-01 a PNS-92). Esta entrega añade los resultados de las pruebas funcionales con un proveedor de IA externo que aquella dejaba pendientes y los hallazgos nuevos PNS-93 a PNS-96. |
| **Fecha** | 2026-10-16 |
| **Entorno de análisis** | Odoo 14.0 con Python 3.7.3 y Pillow 5.4.1 (imagen oficial de Odoo 14, Debian Buster). Entorno de laboratorio con bases de datos de prueba, y entorno de pruebas con datos de demostración, PostgreSQL 15, 2 workers y un proveedor de IA real (Google Gemini por el protocolo compatible con OpenAI). |
| **Método** | Revisión del código de las versiones nuevas frente a las del informe anterior, hallazgo por hallazgo; comprobación en el entorno de laboratorio (control de acceso por RPC, actualización de una base de datos desde 3.1.486, compatibilidad con Odoo 14); y pruebas funcionales con el proveedor real en el entorno de pruebas. Para poder cargar y usar los módulos en Odoo 14 se aplicaron en ambos entornos correcciones mínimas equivalentes a las que sugerimos para PNS-81, PNS-93 y PNS-94. |
| **Referencias de código** | Todas las líneas citadas son las del código publicado de estas versiones, sin ninguna corrección local. |

---

## Índice

1. Resumen
2. Prioridades
3. Respuesta a la primera entrega (PNS-01 a PNS-80)
4. Hallazgos PNS-81 a PNS-96 (4.1 Hallazgos nuevos: PNS-93 a PNS-96 · 4.2 Hallazgos comunicados el 15/10: PNS-81 a PNS-92)
5. Qué hemos probado y qué no
6. Observaciones menores

---

## 1. Resumen

1. Esta entrega continúa la del 2026-10-15, en la que les enviamos el estado de los 80 hallazgos del
   informe anterior y los hallazgos nuevos PNS-81 a PNS-92, y en la que dejamos pendientes las pruebas
   funcionales con un proveedor de IA externo (§8 de aquella entrega). Ahora añadimos los resultados de
   esas pruebas y cuatro hallazgos nuevos (PNS-93 a PNS-96). Las versiones revisadas son las mismas que
   el 15/10.
2. **Entorno.** Odoo 14.0 con Python 3.7.3 y Pillow 5.4.1, que son las versiones de la imagen oficial de
   Odoo 14 (Odoo 14 fija `Pillow==5.4.1` con Python ≤ 3.7 en su `requirements.txt:34`).
3. **Método.** Tres niveles, indicados en cada hallazgo:
   - **Código:** revisión del código publicado.
   - **Laboratorio:** entorno de laboratorio con bases de datos de prueba: llamadas por RPC con usuarios
     internos, de portal y con distintos grupos de IA, actualización de una base de datos desde 3.1.486
     y carga de los módulos en Odoo 14. El proveedor de IA estuvo saturado durante esta fase, y las
     pruebas con IA se completaron en el entorno de pruebas.
   - **Entorno de pruebas:** instalación nueva con datos de demostración y un proveedor de IA real.
     Turnos de Chatboo con varios usuarios de prueba (solo chat, con escritura, con URL externas).

   En la entrega del 15/10, «entorno de pruebas» designaba lo que aquí llamamos laboratorio.
4. **Estado de los 80 hallazgos del informe anterior** (sin cambios de estado desde el 15/10): **31
   corregidos, 33 parciales, 13 sin cambios, 2 ya no aplican y 1 dudoso.** Respecto al informe anterior
   hay **16 hallazgos nuevos** (PNS-81 a PNS-96): 9 en código nuevo o modificado de esta versión
   (PNS-81 a PNS-89) y 3 en código que ya existía y que el informe anterior no citaba (PNS-90 a PNS-92),
   comunicados el 15/10, y 4 observados en el entorno de pruebas con el proveedor real (PNS-93 a
   PNS-96), nuevos en esta entrega.

   | Gravedad | Corregido | Parcial | Sin cambios | Ya no aplica | Dudoso | Nuevo | Total |
   |---|---|---|---|---|---|---|---|
   | Crítica | 5 | 4 | 0 | 0 | 0 | 0 | 9 |
   | Alta | 13 | 11 | 1 | 1 | 0 | 5 | 31 |
   | Media | 4 | 12 | 9 | 0 | 0 | 6 | 31 |
   | Baja | 9 | 6 | 3 | 1 | 1 | 5 | 25 |
   | **Total** | **31** | **33** | **13** | **2** | **1** | **16** | **96** |

   **Respecto a la entrega del 15/10:** 4 hallazgos nuevos (PNS-93 a PNS-96: 1 de gravedad alta, 1 media
   y 2 bajas). Ningún hallazgo cambia de estado; 10 cambian de verificación o de resultado con las
   pruebas funcionales (PNS-05, PNS-12, PNS-16, PNS-22, PNS-36, PNS-46, PNS-59, PNS-60, PNS-61 y
   PNS-81), señalados con «Desde el 15/10» en §3.1, §4.2 y §5.

5. **Críticos del informe anterior.** Se han repetido en el laboratorio las pruebas A-D del informe
   anterior; las vías que reproducían están cerradas. Corregidos: PNS-03, PNS-04, PNS-05 (confirmado
   ahora con turnos reales), PNS-06 y PNS-53. Parciales, con el resto acotado: PNS-01 y PNS-02 (un AI
   Administrator sin permisos de Ajustes sigue pudiendo conceder o quitar grupos de Odoo con un plan que
   él mismo confirma), PNS-07 (el sandbox no bloquea los métodos privados) y PNS-54 (confirmación sin
   token ligado a la interacción).
6. **Qué pedimos con prioridad** (detalle y justificación en §2):
   1. El mismo patrón que causó PNS-01 (métodos públicos que trabajan en `sudo` sin comprobar grupo ni
      propiedad) sigue en cinco hallazgos explotables hoy, cuatro de ellos comprobados en el
      laboratorio y tres también por un usuario de portal: PNS-83, PNS-90, PNS-82, PNS-85 y PNS-91.
   2. PNS-94 (nuevo en esta entrega): cualquier usuario de Chatboo deja Odoo sin servicio con solo adjuntar una imagen.
   3. PNS-81: en Odoo 14 con Python 3.7 o 3.8, `pns_ai_mcp` no se importa y la base de datos deja de
      cargar. **Pedimos una fecha prevista de corrección.**
   4. Los restos de PNS-01/02 y PNS-07/19.
   5. PNS-87 y PNS-88: pérdida de datos no avisada en la primera actualización.

---

## 2. Prioridades

### 2.1 Orden propuesto

| # | Hallazgo | Gravedad | Por qué en este lugar |
|---|---|---|---|
| 1 | PNS-83 | Alta | Cualquier usuario autenticado, también de portal, puede obtener la clave MCP de otro usuario (que puede ser un AI Administrator) probando PIN sin límite real. |
| 2 | PNS-90 | Alta | Cualquier usuario, también de portal, fija el contenido que recibe la herramienta `fetch_url` de los demás: prompt injection entre usuarios. Comprobado en el laboratorio. |
| 3 | PNS-82 | Alta | Cualquier usuario interno lee o borra adjuntos ajenos, incluidas copias de configuración que pueden llevar secretos. Comprobado en el laboratorio. |
| 4 | PNS-85 | Media | Un usuario sin permisos de escritura altera en silencio los parámetros con que se ejecutan las skills de los demás. Comprobado en el laboratorio. |
| 5 | PNS-91 | Media | Cualquier usuario, también de portal, amplía la lista blanca de URL y anula la política restringida en la que se apoyan las correcciones de PNS-16, PNS-59 y PNS-86. Comprobado en el laboratorio. |
| 6 | PNS-94 | Alta | Denegación de servicio en el uso normal del chat, al alcance de cualquier usuario de Chatboo, sin privilegios y sin querer. Observado dos veces en el entorno de pruebas. |
| 7 | PNS-81 | Alta | Sin corregir, sustituir el código en un servidor Odoo 14 con Python 3.7 o 3.8 deja la base de datos sin cargar. Las correcciones son de una o dos líneas. |
| 8 | Restos de PNS-01/02 | Crítica | Un AI Administrator sin permisos de Ajustes puede darse `base.group_system`. Requiere un rol de IA, por eso va detrás de los anteriores. |
| 9 | Restos de PNS-07/19 | Crítica / Alta | El sandbox de la Caja A permite llamar a métodos privados con cursor propio y commit, y a uno que devuelve la clave del proveedor. Requiere que el LLM genere ese código. |
| 10 | PNS-87 y PNS-88 | Baja | Pérdida de datos no avisada (registro de actividad, histórico de consumo, personalizaciones) en la primera actualización. Gravedad baja, pero irreversible y en cada instalación que actualice. |

Respecto al orden propuesto el 15/10 cambian dos cosas: entra PNS-94 (nuevo) en el puesto 6, y los
restos de PNS-01/02 y PNS-07/19 pasan detrás de PNS-81, porque requieren un rol de IA o que el LLM
genere ese código.

El resto de peticiones (los demás parciales de §3 y las observaciones de §6) es de menor urgencia.

### 2.2 Patrón común de 1 a 5 y corrección propuesta

En Odoo 14, `call_kw` permite invocar por RPC cualquier método cuyo nombre no empiece por `_` a
cualquier usuario autenticado, también a uno de portal, sin comprobar el ACL del modelo: solo lo
comprueban los métodos ORM, y estos métodos trabajan en `sudo()` o con un cursor propio de
superusuario. Es la causa de PNS-01 y PNS-11 del informe anterior, que la versión 3.1.782 ha corregido
correctamente en `ai.system.action` y `ai.trusted.action` (métodos privados) y en `ai.skill`
(`_require_bootstrap()`).

El mismo patrón sigue presente en estos métodos:

| Hallazgo | Gravedad | Métodos | Quién puede llamarlos hoy |
|---|---|---|---|
| PNS-83 | Alta | `ai.mcp.user.redeem_key_pin`; `ai.key.pin.block.release_all`, `note_failure`, `is_blocked` | Cualquier usuario autenticado, incluido portal |
| PNS-90 | Alta | `ai.fetch.cache.get_cached`, `store` | Cualquier usuario autenticado, incluido portal |
| PNS-82 | Alta | `chatboo.session.claim_turn_file_chips` (y `apply_assistant_download_chips`) | Cualquier usuario interno |
| PNS-85 | Media | `ai.skill.param.cache.remember_for_skill`, `lookup_for_skill`; `ai.skill.remember_param_cache`, `lookup_param_cache` | Cualquier usuario autenticado (comprobado con un interno) |
| PNS-91 | Media | `ai.url.whitelist.ensure_domain_whitelisted` | Cualquier usuario autenticado, incluido portal |
| PNS-92 | Media | `ai.mcp.user.set_mcp_api_key`, `action_generate_mcp_api_key` | Hoy sin efecto por un motivo indirecto (entrega del 15/10, §6) |
| PNS-30 (resto) | Media | `ai.log.create_log_entry` | Cualquier usuario autenticado (comprobado con un interno) |
| PNS-37 (resto) | Media | `ai.change.journal.record_failed_plan` | Cualquier usuario autenticado |

**Corrección propuesta**, en este orden de preferencia:

1. Hacer privados (`_metodo`) los métodos que solo llama el propio motor o el flujo de confirmación, como
   se hizo con `ai.system.action`. Es el caso de PNS-90, PNS-91, PNS-85, PNS-30, PNS-37 y de
   `redeem_key_pin` (PNS-83), que no tiene llamador en los tres módulos.
2. Si el método debe seguir siendo público, comprobar al principio, antes de cualquier `sudo()`, el grupo
   y la propiedad sobre el usuario real (`ensure_ai_admin`, o la regla de propietario), como ya hace la
   versión nueva en `action_test_connection` y `action_discover_tools` (PNS-09).
3. No confiar en el ACL del modelo ni en efectos laterales (PNS-92) como control de acceso de un método
   público.
4. Añadir un test negativo por método con un usuario interno sin grupos de IA y otro de portal, como los
   nuevos de `pns_ai_mcp/tests/test_system_action.py:429-456`.

---

## 3. Respuesta a la primera entrega (PNS-01 a PNS-80)

### 3.1 Tabla de estado

Estados: **CORREGIDO** (el cambio cubre el hallazgo y sus puntos de entrada) · **PARCIAL** (cubre una
parte; queda un resto concreto, en §3.2) · **SIN CAMBIOS** (en §3.3) · **YA NO APLICA** (el código
desapareció) · **DUDOSO** (no se puede decidir sin una prueba adicional; ver §5).

Verificación: **Código** (revisión del código) · **Laboratorio** (comprobado en el entorno de
laboratorio) · **Entorno de pruebas** (comprobado en el entorno de pruebas con datos de demostración y
proveedor real). «(parte)» indica que solo se probó la parte corregida o solo una de las vías; «resto
reproducido», que la prueba confirmó el resto pendiente.

Desde el 15/10: **Sí** indica que la verificación o el resultado cambian respecto a la entrega del
15/10, casi siempre porque entonces la prueba quedaba pendiente de un proveedor real; «—», sin cambios.
Ningún estado cambia.

| PNS | Gravedad | Estado | Verificación | Nota | Desde el 15/10 |
|---|---|---|---|---|---|
| PNS-01 | Crítica | PARCIAL | Laboratorio (parte) | Vía RPC cerrada (métodos privados). Resto en §3.2. | — |
| PNS-02 | Crítica | PARCIAL | Laboratorio (parte) | Todos los `apply_*`/`preview_*` privados. Resto en §3.2. | — |
| PNS-03 | Crítica | CORREGIDO | Laboratorio | `write` fuera de `sudo` rechazado; sin creación directa por RPC. | — |
| PNS-04 | Crítica | CORREGIDO | Código | `confirmed_uid` ignorado; `_can_resolve()` en todas las transiciones. La variante privada que recibe uid es resto de PNS-07. | — |
| PNS-05 | Crítica | CORREGIDO | Entorno de pruebas | Un usuario no obtiene ningún dato de la operación de otro; la operación confirmada se ejecuta con los permisos de su dueño. | Sí: comprobado (pendiente el 15/10) |
| PNS-06 | Crítica | CORREGIDO | Laboratorio (parte) | Ejecución de prueba en savepoint revertido; código de escritura rechazado al guardar (comprobado). Comparte el resto del sandbox de PNS-07. | — |
| PNS-07 | Crítica | PARCIAL | Código | Resto en §3.2. | — |
| PNS-08 | Alta | CORREGIDO | Laboratorio | Campos secretos solo para AI Administrator y vaciados en la exportación. | — |
| PNS-09 | Alta | CORREGIDO | Laboratorio (parte) | `stdio` solo para administrador de Ajustes; entorno mínimo y timeout; `ensure_ai_admin` (comprobado en `action_test_connection`). | — |
| PNS-10 | Alta | CORREGIDO | Laboratorio | La bandera solo vale en `sudo` o para el superusuario. | — |
| PNS-11 | Alta | CORREGIDO | Laboratorio | `_require_bootstrap()` en los cinco métodos; `record_context_usage` privado. | — |
| PNS-12 | Alta | CORREGIDO | Laboratorio y entorno de pruebas | Filtro por propietario en el modelo y en los turnos del chat. Por MCP solo se pudo comprobar con la corrección 4 de PNS-81 aplicada. | Sí: comprobado en los turnos del chat |
| PNS-13 | Alta | CORREGIDO | Laboratorio | Clave y usuario revalidados en cada mensaje; sesiones con caducidad. | — |
| PNS-14 | Alta | PARCIAL | Laboratorio (resto reproducido) | Reglas nuevas en `ai.api.result.cache` y `ai.safe.choice`. Resto: PNS-90. | — |
| PNS-15 | Alta | CORREGIDO | Código | Saneado o escape en todas las vías citadas. | — |
| PNS-16 | Alta | PARCIAL | Entorno de pruebas (parte) | Sin auto-confirmación ni salida con las dos políticas de URL. Resto en §3.2. | Sí: probado; la reinyección, no concluyente |
| PNS-17 | Alta | PARCIAL | Código | `fetch_url` protegido salto a salto y con tope. Resto en §3.2. | — |
| PNS-18 | Alta | PARCIAL | Laboratorio (parte) | `no_external_failover` comprobado. Resto en §3.2. | — |
| PNS-19 | Alta | PARCIAL | Código | `sudo` y el cursor bloqueados en el sandbox. Resto en §3.2. | — |
| PNS-20 | Alta | PARCIAL | Código | Exportación sin secretos por defecto y purga de 24 h. Resto en §3.2. | — |
| PNS-21 | Alta | CORREGIDO | Laboratorio | `auth='user'` y URL sin token. Ver PNS-82. | — |
| PNS-22 | Media | PARCIAL | Entorno de pruebas (parte) | Puerta `group_ai_writer` en el motor, comprobada por Chatboo. Resto en §3.2. | Sí: comprobado por Chatboo; `/mcp`, sin probar |
| PNS-23 | Alta | SIN CAMBIOS | Código | §3.3. | — |
| PNS-24 | Alta | PARCIAL | Código | Ejecución con el usuario real y veto de cascadas. Resto en §3.2. | — |
| PNS-25 | Alta | CORREGIDO | Código | Sin failover tras ejecutar efectos; ejecución idempotente. | — |
| PNS-26 | Alta | PARCIAL | Código | `rollback` en `/mcp` si falla la herramienta. Resto en §3.2. | — |
| PNS-27 | Alta | CORREGIDO | Código | Fuera SheetJS y las copias duplicadas; jsPDF 4.2.1. Ver PNS-60 (Showdown). | — |
| PNS-28 | Media | PARCIAL | Laboratorio (parte) | Sin filas de `ai.log` para peticiones sin usuario. Resto en §3.2. | — |
| PNS-29 | Media | PARCIAL | Laboratorio (parte) | El uso de las llamadas cortas se registra. Resto en §3.2. | — (sigue pendiente; §5) |
| PNS-30 | Media | PARCIAL | Laboratorio (resto reproducido) | `ondelete='set null'`, ACL sin escritura y retención. Resto en §3.2. Ver PNS-87. | — |
| PNS-31 | Media | SIN CAMBIOS | Código | §3.3. | — |
| PNS-32 | Media | PARCIAL | Código | Sin borrados en disco. Resto en §3.2. | — |
| PNS-33 | Media | SIN CAMBIOS | Código | §3.3. | — |
| PNS-34 | Media | CORREGIDO | Código | Clave aleatoria por clase y restaurada al desmontar. | — |
| PNS-35 | Media | SIN CAMBIOS | Código | §3.3. | — |
| PNS-36 | Media | PARCIAL | Entorno de pruebas (resto reproducido) | Fuera `resources/*` y `system://info`. Resto en §3.2. | Sí: resto reproducido |
| PNS-37 | Media | SIN CAMBIOS | Código | §3.3. | — |
| PNS-38 | Media | SIN CAMBIOS | Código | §3.3. | — |
| PNS-39 | Media | PARCIAL | Código | 202 en `/mcp/message` y negociación de versión. Resto en §3.2. | — |
| PNS-40 | Media | PARCIAL | Laboratorio (resto reproducido) | `temperature` omitible e imágenes en el formato de Anthropic. Resto en §3.2. | — |
| PNS-41 | Media | CORREGIDO | Código | Sin reescritura de `website`; `iframe` con `sandbox` sin scripts. | — |
| PNS-42 | Media | SIN CAMBIOS | Código | §3.3. | — |
| PNS-43 | Baja | PARCIAL | Código | Aviso en el asistente de idioma. Resto en §3.2. | — |
| PNS-44 | Baja | YA NO APLICA | Código | Sin escrituras en `ir.module.module` durante la carga. | — |
| PNS-45 | Baja | CORREGIDO | Código | Cada fallo de carga de herramienta se registra con traza. | — |
| PNS-46 | Baja | DUDOSO | Laboratorio y entorno de pruebas (no concluyente) | Ver §5 y PNS-95. | Sí: probado; sigue no concluyente |
| PNS-47 | Baja | CORREGIDO | Código | El fallo de las fuentes de divisas se recuerda 15 minutos. | — |
| PNS-48 | Baja | CORREGIDO | Código | Menú Settings con `base.group_system`; sin acciones duplicadas. | — |
| PNS-49 | Baja | PARCIAL | Código | Resto en §3.2. | — |
| PNS-50 | Baja | PARCIAL | Código | Tests negativos nuevos. Resto en §3.2. | — |
| PNS-51 | Baja | SIN CAMBIOS | Código | §3.3. | — |
| PNS-52 | Baja | CORREGIDO | Código | Defaults con recordset vacío y selecciones validadas. | — |
| PNS-53 | Crítica | CORREGIDO | Laboratorio | Reglas por `user_id` y HTML saneado en el historial y el streaming. | — |
| PNS-54 | Crítica | PARCIAL | Código | La tarjeta solo actúa para el dueño. Resto en §3.2. | — |
| PNS-55 | Alta | PARCIAL | Laboratorio (parte) | Aislamiento de sesiones y trabajos comprobado. Resto en §3.2. | — |
| PNS-56 | Alta | CORREGIDO | Laboratorio | La vía entre usuarios dependía de PNS-55, ya cerrada. | — |
| PNS-57 | Alta | CORREGIDO | Laboratorio | `_spawn` privado; trabajos solo sobre sesión propia. | — |
| PNS-58 | Alta | CORREGIDO | Laboratorio | `/chatboo/stream` con CSRF y sin `cors`. | — |
| PNS-59 | Alta | PARCIAL | Laboratorio y entorno de pruebas (parte) | Con la política restringida, ni el navegador ni el servidor salen al exterior. Resto en §3.2. | Sí: comprobado con la política restringida |
| PNS-60 | Alta | PARCIAL | Laboratorio y entorno de pruebas (parte) | Saneado comprobado en el mensaje del usuario y en la respuesta (en directo, tras recargar, PDF y Word). Resto en §3.2. | Sí: comprobadas la respuesta y la exportación |
| PNS-61 | Media | PARCIAL | Laboratorio y entorno de pruebas (resto reproducido) | Agente y proveedor fijados por el servidor (comprobado). Resto en §3.2. | Sí: resto reproducido |
| PNS-62 | Media | PARCIAL | Laboratorio (parte) | Tope por archivo comprobado. Resto en §3.2. | — |
| PNS-63 | Media | CORREGIDO | Código | Purga global por cron. Ver la nota de actualización en §6. | — |
| PNS-64 | Media | PARCIAL | Código | Se prefiere voz local. Resto en §3.2. | — |
| PNS-65 | Media | PARCIAL | Código | HTML saneado y servido con `nosniff`. Resto en §3.2. | — |
| PNS-66 | Media | SIN CAMBIOS | Laboratorio | §3.3. | — |
| PNS-67 | Media | CORREGIDO | Código | `financial-health` y `customer-risk-analysis` corregidas; `analisis-financiero` retirada. | — |
| PNS-68 | Media | SIN CAMBIOS | Código | §3.3. | — |
| PNS-69 | Baja | CORREGIDO | Código | Listas de clase ampliadas en `__init__`. | — |
| PNS-70 | Media | SIN CAMBIOS | Código | §3.3. | — |
| PNS-71 | Baja | CORREGIDO | Laboratorio | `check_health` con clave y sin datos de infraestructura; estados HTTP correctos. | — |
| PNS-72 | Baja | PARCIAL | Código | Fuera SheetJS y duplicados. Resto en §3.2. | — |
| PNS-73 | Baja | SIN CAMBIOS | Código | §3.3. | — |
| PNS-74 | Baja | PARCIAL | Código | `noopener` añadido. Resto en §3.2. | — |
| PNS-75 | Baja | CORREGIDO | Código | Celdas con `=`, `+`, `-`, `@` prefijadas como texto. | — |
| PNS-76 | Baja | PARCIAL | Código | Caché de menús vaciada al generar la clave. Resto en §3.2. | — |
| PNS-77 | Baja | SIN CAMBIOS | Código | §3.3. | — |
| PNS-78 | Baja | CORREGIDO | Código | Etiquetas distintas. | — |
| PNS-79 | Baja | CORREGIDO | Código (prueba no concluyente) | Sin valor por defecto `SUPERUSER_ID`; usuario de la clave revalidado. | — |
| PNS-80 | Alta | YA NO APLICA | Laboratorio | `read_progress` desaparece; el sondeo filtra por usuario (comprobado con un usuario con acceso a Chatboo sobre la sesión de otro). | — |

**Recuento de PNS-01 a PNS-80:** CORREGIDO 31 · PARCIAL 33 · SIN CAMBIOS 13 · YA NO APLICA 2 ·
DUDOSO 1.

### 3.2 Parciales: resto pendiente y corrección sugerida

Rutas relativas a la raíz de los módulos. Solo se describe lo que falta; lo corregido está en la tabla.

**PNS-01 (Crítica) — Escalada a `base.group_system`**
- **Resto:** la acción de confianza `user.add_group` solo exige `group_ai_admin`
  (`pns_ai_mcp/data/trusted_actions_system.xml:84`), y `_apply_user_add_group` resuelve usuario y grupo
  en `sudo` (`pns_ai_mcp/models/ai_system_action.py:674-697, 718`) y escribe con
  `pns_base/utils/compat.py:113-116`. Un AI Administrator que no sea administrador de Odoo puede, con un
  plan que él mismo confirma, darse `base.group_system`.
- **Corrección sugerida:** exigir también `base.group_system`, comprobado sobre el usuario real, como ya
  hace la versión nueva para los servidores `stdio` (`pns_ai_mcp/models/external_server.py:548,
  567-587`).

**PNS-02 (Crítica) — Resto de `apply_*` sin control de permisos**
- **Resto:** `user.remove_group` tiene el mismo límite
  (`pns_ai_mcp/data/trusted_actions_system.xml:94`; `models/ai_system_action.py:748`;
  `pns_base/utils/compat.py:119-122`): basta `group_ai_admin` para quitar grupos de Ajustes a un
  administrador de Odoo. Las acciones de vista y obligatoriedad (`view.*`, `field.set_required`)
  también se quedan en `group_ai_admin`; lo consideramos una decisión de diseño aceptable.
- **Corrección sugerida:** la misma que PNS-01.

**PNS-07 (Crítica) — Sandbox y métodos con cursor propio**
- **Resto:** `guarded_getattr` aplica una lista negra de 15 nombres públicos
  (`pns_ai_mcp/controllers/context_builder.py:123-155`; `controllers/validators.py:178-194`) y, según su
  docstring, permite los métodos con `_`. Quedan alcanzables métodos con cursor propio y commit de
  `ai.safe.operation`: `_execute_plan_with_timeouts` (que además recibe el uid ejecutor,
  `pns_ai_mcp/models/safe_operation.py:866-888`), `_retry_confirmed_not_executed` (`:974-1012`),
  `_claim_execute` (`:1136-1205`), `_release_execute_claim` (`:1207`), `_clear_stale_execute_claims`
  (`:1246-1260`) y `_heal_module_update_after_registry_reset` (`:1457-1556`); y los públicos nuevos
  `redeem_key_pin` (`models/mcp_user.py:819-860`) y `remember_for_skill`
  (`models/ai_skill_param_cache.py:125-154`), que no están en la lista. Hay además cursores propios en
  `ai_log.py`, `ai_change_journal.py`, `ai_provider.py`, `ai_agent.py`, `ai_context.py` y
  `ai_skill_param_cache.py` que no hemos revisado uno a uno.
- **Corrección sugerida:** bloquear en el sandbox los métodos que empiezan por `_`, con excepciones de
  solo lectura (`_name`, `_fields`…), y pasar a una lista de métodos permitidos.

**PNS-14 (Alta) — Cachés legibles por todos**
- **Resto:** `ai.fetch.cache.get_cached` y `store` (`pns_ai_mcp/models/fetch_cache.py:63-89, 91-123`) son
  públicos y en `sudo`: el ACL nuevo no los cubre. Tiene número propio: PNS-90.
- **Corrección sugerida:** la de PNS-90.

**PNS-16 (Alta) — Prompt injection y auto-confirmación**
- **Resto:**
  - El código y las filas de la consulta del turno anterior se reinyectan con rol `system`
    (`pns_ai_mcp/utils/agent_engine.py:2712-2760`, `[DATOS REUTILIZABLES]` y `[CONSULTA REUTILIZABLE]`),
    y la marca de turno no confiable se reinicia en cada turno: un contenido inducido en un turno vuelve
    con autoridad de sistema en el siguiente. En el entorno de pruebas no se manifestó con la política
    `open` y no fue concluyente con la restringida (§5).
  - Con la política `open`, al confirmar se sigue añadiendo el dominio a la lista blanca
    (`pns_ai_mcp/controllers/safe_plan.py:749-754`).
  - La política restringida no limita los hosts mientras cualquier usuario pueda ampliar la lista
    blanca (PNS-91).
- **Corrección sugerida:** reinyectar los datos reutilizados como mensajes `user`/`tool` delimitados y
  marcados como datos, no como `system`; conservar la marca de no confiable mientras esos datos sigan
  en el contexto; no ampliar la lista blanca de forma implícita al confirmar.

**PNS-17 (Alta) — SSRF**
- **Resto:**
  - El generador OpenAPI nuevo descarga sin la protección de `fetch_url`: tiene número propio (PNS-86).
  - El driver OpenAPI sigue redirecciones con sus cabeceras de autenticación y sin límite de tamaño
    (`pns_ai_mcp/lib/api/drivers/openapi_driver.py:74-81, 387-394`).
  - Menor: entre la comprobación DNS y la conexión hay una segunda resolución, que no protege frente a
    DNS rebinding.
- **Corrección sugerida:** en el driver OpenAPI, `allow_redirects=False` y validar cada salto con
  `non_public_host_error`, no reenviar las cabeceras de autenticación a otro host y leer con
  `stream=True` y tope, como ya hace `fetch_url` (`controllers/safe_plan.py:1528-1585`).

**PNS-18 (Alta) — Datos hacia el proveedor LLM**
- **Resto:** no hay lista de modelos o campos excluidos ni anonimización, y el tope de filas hacia el
  LLM es el mismo que el de la herramienta (`RELAXAICODE_MAX_RESULT_ROWS = 50000`,
  `pns_ai_mcp/controllers/tools_relaxaicode.py:31`).
- **Corrección sugerida:** una lista configurable de modelos y campos que nunca se envían y un tope de
  filas hacia el LLM independiente del de la herramienta.

**PNS-19 (Alta) — Secretos desde el sandbox**
- **Resto:** `ai.provider._api_key_for_inference()` devuelve la clave del proveedor leída en `sudo`
  (`pns_ai_mcp/models/ai_provider.py:200-208`) y es alcanzable por el resto de PNS-07. Además, no se
  bloquean por modelo los secretos que el propio usuario puede leer (por ejemplo,
  `ir.config_parameter` para un administrador), que el motor reenviaría al proveedor.
- **Corrección sugerida:** la de PNS-07, y bloquear en el sandbox los modelos con secretos
  (`ai.provider`, `ir.config_parameter`, `ai.mcp.user`, `res.users.apikeys`).

**PNS-20 (Alta) — Copias de configuración**
- **Resto:** la importación sigue sobrescribiendo por defecto (`replace_existing`,
  `pns_ai_mcp/wizard/config_backup_wizard.py:41-46`) y aplica sin resumen previo (`:48-63`). Un fichero
  ajeno puede cambiar proveedores, endpoints o la política de URL.
- **Corrección sugerida:** `replace_existing=False` por defecto y un resumen de cambios que el
  administrador confirme antes de aplicar. Ver también §6 (`copy=False` en la clave del proveedor).

**PNS-22 (Media) — `is_write` no centralizado**
- **Resto:** `tools/call` sigue decidiendo la puerta de escritura por una lista de dos nombres que no son
  herramientas registradas (`pns_ai_mcp/controllers/main.py:1295-1311`), y la marca `is_write` solo se
  lee después de la puerta (`:1380-1383`), sin efecto. Hoy la única herramienta con `is_write=True`
  decide dentro (`controllers/tools_relaxaicode.py:1671`); una herramienta de escritura futura
  dependerá otra vez de pedir el entorno correcto.
- **Corrección sugerida:** exigir `group_ai_writer` en `tools/call` para toda herramienta con
  `is_write=True`, igual que ya hace el `DummyController` del motor.

**PNS-24 (Alta) — `module.update`**
- **Resto:** `button_immediate_*` sigue haciendo commit y recargando el registro. La «curación»
  posterior (`pns_ai_mcp/models/safe_operation.py:1370-1378`; `utils/module_update_heal.py`) no impide
  combinar `module.update` con otros pasos en el mismo plan, así que la atomicidad no se garantiza en
  ese caso.
- **Corrección sugerida:** rechazar planes que mezclen `module.update` con otros pasos, o documentar que
  esos pasos no se revierten.

**PNS-26 (Alta) — Commits fuera del flujo transaccional**
- **Resto:** siguen los `commit()` sobre el cursor del llamador en `pns_ai_mcp/models/safe_operation.py`
  (`resolve_confirm_and_execute`, `:850, 859`; `execute_plan_now`, `:1366, 1410`;
  `_clear_stale_execute_claims`, `:1260`), y no consta un rollback equivalente al de `/mcp` en la ruta
  del motor de Chatboo cuando falla una herramienta.
- **Corrección sugerida:** un savepoint por herramienta también en el motor, y evitar `commit()` sobre
  el cursor del llamador.

**PNS-28 (Media) — CORS y `Origin`**
- **Resto:** todas las rutas `/mcp*` siguen con `cors='*'` y `Access-Control-Allow-Origin: *`
  (`pns_ai_mcp/controllers/main.py:240-295, 487, 599, 693, 800`), sin validación de `Origin`.
- **Corrección sugerida:** validar `Origin` contra una lista configurable, como pide la especificación
  MCP.

**PNS-29 (Media) — Consumo**
- **Resto:** no hay topes de gasto, de tokens ni de turnos, y `normalize_usage` no suma
  `cache_creation_input_tokens` de Anthropic (`pns_ai_mcp/utils/llm_usage.py:94-99`): la escritura en
  caché, que el proveedor factura, no se registra.
- **Corrección sugerida:** sumar `cache_creation_input_tokens` y ofrecer un tope de gasto configurable.

**PNS-30 (Media) — `ai.log`**
- **Resto:** `create_log_entry` sigue siendo público (`pns_ai_mcp/models/ai_log.py:668-669`), crea la fila
  con un cursor propio como `SUPERUSER_ID` (`:706-708`) y con el `user_id` que recibe. Comprobado en el
  laboratorio: un interno sin grupos de IA crea filas a nombre de otro. El tope de 100 000 caracteres por
  campo sigue (`:739`).
- **Corrección sugerida:** hacerlo privado (§2.2).

**PNS-32 (Media) — Sincronización de fábrica**
- **Resto:** la sincronización sigue en `_register_hook` (`pns_ai_mcp/models/ai_context.py:413-429`) e
  importa con `replace_existing=True` (`pns_ai_mcp/hooks.py:183-219`): un contexto de fábrica editado por
  el administrador se sobrescribe al cambiar el sello. No hay bloqueo entre workers
  (`maybe_sync_factory_knowledge`, `hooks.py:243-260`).
- **Corrección sugerida:** una marca de «modificado» que respete las ediciones locales y un bloqueo
  (por ejemplo `pg_try_advisory_xact_lock`) para serializar la sincronización.

**PNS-36 (Media) — Nombre de la base de datos y esquema**
- **Resto:** el sandbox, que usa cualquier usuario del chat o de MCP, precarga el nombre de la base de
  datos como `dbname`, `db_name` y `database` (`pns_ai_mcp/controllers/context_builder.py:436-438,
  550-552`), y ningún validador bloquea `fields_get` sobre un modelo sin permiso de lectura. Reproducido
  en el entorno de pruebas: un usuario solo de chat obtuvo el nombre de la base de datos y la lista de
  campos de un modelo al que no tiene acceso (sin valores).
- **Corrección sugerida:** no precargar el nombre de la base de datos y comprobar
  `check_access_rights('read')` antes de `fields_get`.

**PNS-39 (Media) — Especificación MCP**
- **Resto:** las notificaciones a `/mcp` siguen con 204 (`pns_ai_mcp/controllers/main.py:586, 984`), los
  errores de autenticación salen con 200 (`:1031-1039`) e `isError` solo aparece como `False`
  (`controllers/tools_relaxaicode.py:1535, 1568`).
- **Corrección sugerida:** 202 en notificaciones, 401 en errores de autenticación e `isError: true` en
  los errores de herramienta.

**PNS-40 (Media) — Parámetros del LLM y endpoint en el error**
- **Resto:** `temperature = 0` sigue pasando a 0,7 (`pns_ai_mcp/utils/agent_engine.py:2625`), el driver
  OpenAI no usa `max_completion_tokens` (`lib/llm/drivers/openai_driver.py:590-592`) y el error al
  usuario incluye el endpoint (`agent_engine.py:3289-3299`) y el fallo de cada proveedor (`:2412-2418`).
  Reproducido en el laboratorio: el chat mostró host, puerto, URL y el cuerpo de un 503 del proveedor.
- **Corrección sugerida:** respetar `temperature = 0`, usar `max_completion_tokens` donde corresponda y
  mostrar al usuario un mensaje genérico (el detalle, solo en el log).

**PNS-43 (Baja) — Traducciones duplicadas**
- **Resto:** el descarte sigue aplicándose a cualquier módulo (`pns_base/models/ir_translation.py:55-115`);
  fuera del asistente de idioma (`base.update.translations`, `-u` con `--i18n-overwrite`) solo queda el
  WARNING del log.
- **Corrección sugerida:** limitarlo a módulos PNS.

**PNS-49 (Baja) — Código muerto**
- **Resto:** `pns_ai_mcp/controllers/moe_controller.py` (no se importa); `cleanup_stuck_state`
  (`models/safe_operation.py:938`); `web_read` (`models/ai_agent.py:871`); `search_fetch`
  (`models/mcp_user.py:572`); `ActionManager.include` (`static/src/js/mcp_log_tree_v14.js:137`);
  `_onToggleBoolean` (`static/src/js/mcp_user_tree_v14.js:129`); el driver `ollama`, registrado
  (`lib/llm/drivers/registry.py:19`) pero no seleccionable en `ai.provider.protocol`. Además,
  `detect_dangerous_operations` (`controllers/validators.py:2330-2337`) se importa y no se llama (ver §6).
- **Corrección sugerida:** eliminarlo.

**PNS-50 (Baja) — Tests**
- **Resto:** `test_change_journal.py` sigue sin importarse (`pns_ai_mcp/tests/__init__.py`), y
  `test_presentation_mode` y `test_session_download` siguen siendo `unittest.TestCase`
  (`tests/test_presentation_mode.py:19-20`, `tests/test_session_download.py:20-21`) con un `@tagged` que
  no incluye `standard`, así que Odoo 14 los descarta. No hay cobertura del motor LLM.
- **Corrección sugerida:** importar el primero y pasar los otros dos a `TransactionCase` con la etiqueta
  `standard` (o `post_install`).

**PNS-54 (Crítica) — Confirmación de la Caja B**
- **Resto:** `/pns_ai_mcp/verification/confirm` y `/execute`
  (`pns_ai_mcp/controllers/verification_ui.py:37-62`) siguen exigiendo solo sesión y propiedad: sin token
  de un solo uso ligado a la interacción, sin reautenticación y sin espera en servidor para
  `danger_level = 'high'`. Además, `resolve_confirm_and_execute` (`models/safe_operation.py:831-863`) y
  `confirm_by_user` (`:513-547`) siguen siendo públicos por RPC para el dueño, así que un script en la
  página puede confirmar sin pasar por la tarjeta.
- **Corrección sugerida:** un token de un solo uso emitido al pintar la tarjeta y exigido en
  `confirm`/`execute`; la espera para riesgo alto aplicada en servidor; y los métodos de modelo
  privados o condicionados a ese token.

**PNS-55 (Alta) — Aislamiento en Chatboo**
- **Resto:**
  - El ACL de trabajos sigue con `write` y `create` para el usuario
    (`pns_ai_chatboo/security/ir.model.access.csv:3`, `1,1,1,0`).
  - `claim_turn_file_chips`, nuevo en esta versión, permite apropiarse de adjuntos ajenos: tiene número
    propio (PNS-82).
  - `recover_orphan_download_chips(messages=…)` (`pns_ai_chatboo/models/chatboo_session.py:521-552`)
    lista en `sudo` nombres y tamaños de adjuntos de una sesión si se le pasan los mensajes, sin leer la
    sesión (fuga menor; la descarga sí se deniega).
- **Corrección sugerida:** ACL de trabajos de solo lectura (el servidor los crea en `sudo`) y
  comprobación de dueño en `recover_orphan_download_chips`.

**PNS-59 (Alta) — Imágenes externas**
- **Resto:** el navegador ya no contacta con terceros, pero el servidor descarga la imagen si el host está
  en la lista blanca con entrada `web` o si la política es `open`
  (`pns_ai_mcp/models/url_whitelist.py:168-176`). Con `open`, una imagen inducida por prompt injection con
  datos en la URL sigue saliendo sin clic, ahora desde el servidor; con la restringida, la lista blanca
  es ampliable por cualquier usuario (PNS-91). La prueba con `open` no fue concluyente (§5).
- **Corrección sugerida:** no servir por `remote_image` imágenes de hosts que no estén expresamente en la
  lista blanca, sea cual sea la política, y corregir PNS-91.

**PNS-60 (Alta) — Saneado en el cliente de Chatboo**
- **Resto:** `escapeHtml` sigue sin escapar comillas (`pns_ai_chatboo/static/src/js/chatboo_formatters.js:105-109`)
  y se usa en atributos (`static/src/js/chatboo_component_v2.js:3464`, `data-slash-code`); el saneador es
  una lista negra de etiquetas (`chatboo_formatters.js:111-320`); Showdown 2.1.0 sigue incluido
  (`static/src/js/showdown.js`), sin mantenimiento aparente y con una vulnerabilidad de denegación de
  servicio publicada (CVE-2024-1899), aunque su salida pasa ya por el saneador.
- **Corrección sugerida:** escapar `"` y `'` en `escapeHtml`, pasar el saneador a lista blanca de
  etiquetas y atributos, y sustituir Showdown por un convertidor mantenido.

**PNS-61 (Media) — Historial elegido por el navegador**
- **Resto:** el `history` del cuerpo de `/chatboo/stream` sigue llegando del navegador
  (`pns_ai_chatboo/controllers/chatboo.py:738`), se guarda en el trabajo
  (`models/chatboo_async_request.py:242`) y es el historial que recibe el motor (`:418, 605`).
  Reproducido en el entorno de pruebas: el asistente trató como real un turno inventado y ese historial
  falso quedó guardado en la sesión.
- **Corrección sugerida:** reconstruir el historial en el servidor a partir de la sesión guardada.

**PNS-62 (Media) — Tamaño de adjuntos**
- **Resto:** el tope es por archivo (`pns_ai_chatboo/controllers/chatboo.py:770-786`); no hay tope de
  número de archivos ni del cuerpo total, y con el parámetro a 0 no hay límite
  (`utils/chatboo_product_icp.py:22, 64-97`).
- **Corrección sugerida:** topes de número de archivos y de tamaño total del cuerpo, y un valor mínimo no
  desactivable.

**PNS-64 (Media) — Voces remotas**
- **Resto:** si no hay voz local, se usa la remota (`pns_ai_chatboo/static/src/js/chatboo_tts.js:76-79`),
  y no hay ajuste para desactivar la función.
- **Corrección sugerida:** no usar voces remotas salvo que el administrador lo permita.

**PNS-65 (Media) — Exportaciones en el navegador**
- **Resto:** `src` de imágenes concatenado sin escapar en Word
  (`pns_ai_chatboo/static/src/js/chatboo_export.js:3150, 3235`); se exportan todas las claves del dataset
  salvo las que empiezan por `_` (`:2197-2232`); `/chatboo/sessions/fulfill_export` guarda el `mimetype`
  del cliente (`controllers/chatboo.py:301-322` → `models/chatboo_session.py:471-490`); los documentos
  pendientes se suben solos al pintar el mensaje (`static/src/js/chatboo_component_v2.js:5625-5648`).
- **Corrección sugerida:** escapar los atributos, exportar solo las columnas visibles, fijar el
  `mimetype` en el servidor y subir los documentos solo a petición del usuario.

**PNS-72 (Baja) — Librerías para todos los internos**
- **Resto:** siguen seis librerías de terceros en `web.assets_backend` (showdown, jsPDF, autotable,
  html2canvas, Chart.js y ECharts; `pns_ai_chatboo/views/assets.xml:17-23`), y cada carga del cliente
  llama a `check_health` (`static/src/js/chatboo_systray.js:45`).
- **Corrección sugerida:** cargarlas bajo demanda al abrir el chat.

**PNS-74 (Baja) — Código muerto en el cliente**
- **Resto:** `chatboo_floating_transfer_history`
  (`pns_ai_chatboo/static/src/js/chatboo_component_v2.js:724-739`), `_saveRawForTemplate` (`:5224`), la
  rama `result.error` (`:3161`), `mail_service`, que no existe en 14
  (`static/src/js/chatboo_systray.js:202`), y `chatboo_has_access`, que se escribe y no se lee (`:50-61`).
- **Corrección sugerida:** eliminarlo.

**PNS-76 (Baja) — Receta del agente**
- **Resto:** las migraciones `2.1.217`/`2.1.237` siguen añadiendo `acl_security` al agente
  `pns_ai_chatboo` (`pns_ai_chatboo/migrations/2.1.237/post-migrate.py:12, 21`) y los datos no lo llevan
  (`data/ai_agent_data.xml:16-17`); la limpieza nueva solo actúa sobre el agente `pns_ai_mcp`
  (`pns_ai_mcp/models/ai_agent.py:251-274`). En Odoo 14 esas migraciones no se ejecutan, así que solo
  afecta a bases de datos que las hayan ejecutado en otra versión.
- **Corrección sugerida:** extender la limpieza al agente `pns_ai_chatboo`.

### 3.3 Sin cambios: situación actual y corrección sugerida

**PNS-23 (Alta) — Skills activadas sin revisión**
- **Situación:** la captura desde Chatboo crea la skill activa (`'active': bool(self.from_chatboo)`,
  `pns_ai_mcp/wizard/skill_capture_wizard.py:834`), con `from_chatboo` tomado del contexto (`:196-197`),
  aunque el docstring de cabecera dice «DRAFT (active=False)». La importación ZIP y desde ficheros
  mantiene `active` del fichero, `True` por defecto (`models/ai_skill.py:1782, 1998-2013`). La ejecución
  al guardar ya es de solo lectura (PNS-06), lo que reduce el riesgo.
- **Corrección sugerida:** que ambas vías dejen la skill inactiva hasta que la revise un AI
  Administrator.

**PNS-31 (Media) — Parches globales**
- **Situación:** el backport de `_process_ondelete` sigue siendo global
  (`pns_ai_mcp/models/ir_model_fields_selection.py:23-43`); `set_values` de Ajustes reescribe la política
  de URL en cada guardado (`models/res_config_settings.py:297-303`); los `include` del cliente web pasan
  de 11 a 19, con uno nuevo sobre `WebClient` que arranca el sondeo del bus para todo usuario del backend
  (`static/src/js/key_pin_desk_v14.js:349-364`); siguen el oyente global de clics y el
  `MutationObserver` de todo el documento (`static/src/js/ai_agent_origin_filter_v14.js:330, 375-379`) y
  se añaden dos oyentes globales más (`key_pin_desk_v14.js:285, 301`). Ver también §6 (parche de
  `Root.get_request`).
- **Corrección sugerida:** acotar cada parche a los modelos, vistas o usuarios PNS (por ejemplo, arrancar
  el sondeo de la mesa de PIN solo para AI Administrator).

**PNS-33 (Media) — Claves MCP**
- **Situación:** se sigue aceptando la clave como `?api_key=` (`pns_ai_mcp/controllers/main.py:421, 716,
  867`), se registran sus 10 primeros caracteres a nivel INFO en cada petición (`:863, 869`) y el hash
  sigue siendo SHA-256 sin sal y sin caducidad (`utils/api_key.py:35-48`). Relacionado: PNS-84.
- **Corrección sugerida:** aceptar la clave solo en cabecera, no registrar ninguna parte de ella (o un
  identificador no derivado de la clave), usar HMAC con un secreto del servidor y añadir caducidad.

**PNS-35 (Media) — Fórmulas en XLSX**
- **Situación:** las dos vías openpyxl escriben el texto tal cual: `str(value)`
  (`pns_ai_mcp/controllers/formatters.py:452`) y `_excel_value` → `_xlsx_plain_text`, que solo quita
  caracteres de control (`utils/artifact_export.py:2152, 2228-2236, 2307-2313`). openpyxl trata como
  fórmula cualquier cadena que empiece por `=`. La exportación XLSX del chat (`inlineStr`) no está
  afectada.
- **Corrección sugerida:** prefijar como texto las celdas que empiecen por `=`, `+`, `-` o `@`, como ya se
  hace en la copia TSV (PNS-75).

**PNS-37 (Media) — Diario de cambios**
- **Situación:** `intended_values` se guarda sin redactar en los planes fallidos
  (`pns_ai_mcp/models/ai_change_journal.py:377`); la reversión solo cubre `create`, `copy` y `write`
  (`:411-455`); la redacción por nombre no cubre `env_vars` ni `config_json`
  (`utils/change_journal.py:30-38`). **Punto de entrada no citado en el informe anterior (ya existía):**
  `record_failed_plan` (`models/ai_change_journal.py:342-400`) es público, escribe con un cursor propio
  como `SUPERUSER_ID` (`:360-362`) y toma `user_id` y `confirmed_by_uid` del contexto de la llamada
  (`:381-382`): cualquier usuario autenticado puede crear entradas falsas del diario a nombre de otro.
- **Corrección sugerida:** `_record_failed_plan` (§2.2), redactar también los planes fallidos y
  documentar qué es reversible.

**PNS-38 (Media) — Conocimiento de fábrica**
- **Situación:** el prompt de sistema sigue explicando cómo proponer `module.update` y cambios de grupos
  (`pns_ai_mcp/ai/contexts/core/system_prompt.xml:142-144`) y anima a usar `fetch_url` (`:21-26`); siguen
  campos inexistentes en Odoo 14: `pns_delivery_status` (`ai/contexts/domain/email.md:4-87`) y
  `calendar.event.customer_id` (`ai/contexts/domain/partners.xml:38`).
- **Corrección sugerida:** revisar el conocimiento por versión de Odoo y no sugerir acciones de sistema
  por defecto.

**PNS-42 (Media) — JS de validación y CSS globales**
- **Situación:** `BasicController.include` sigue sustituyendo `_notifyInvalidFields` en todos los
  formularios y listas (`pns_base/static/src/js/pns_invalid_fields_dedupe.js:44-96`) y el CSS de
  obligatorios sigue siendo global (`static/src/css/pns_required_readonly.css:4-13`), sin opción para
  desactivarlo.
- **Corrección sugerida:** activarlo solo en vistas PNS o hacerlo opcional.

**PNS-51 (Baja) — `platform` en el sandbox**
- **Situación:** sigue en la lista de módulos permitidos (`pns_ai_mcp/controllers/validators.py:94`).
- **Corrección sugerida:** quitarlo.

**PNS-66 (Media) — Skills de fábrica sin control de grupo**
- **Situación:** `list_for_agent` solo filtra por `active` y `show_in_slash`
  (`pns_ai_mcp/models/ai_skill.py:897-929`) y `ai.skill` no tiene campo de grupos. Siguen `users-all`
  (archivados y último acceso, `pns_ai_chatboo/ai/skills/system/users_all.py:6, 14`), `users-logged`,
  `sys-info` (base de datos, URL y versiones, `sys_info.py:8-21`) y `forecast`, que pide datos externos
  por ciudad (`forecast.py:7, 77`). Comprobado en el laboratorio: un usuario sin grupos de IA obtiene el
  censo completo con `/users-all`.
- **Corrección sugerida:** permitir declarar grupos requeridos por skill y aplicarlos al listar y al
  ejecutar.

**PNS-68 (Media) — Migraciones que borran skills**
- **Situación:** `pns_ai_chatboo/migrations/2.1.296/post-migrate.py:20-35` y
  `migrations/2.1.300/post-migrate.py:26-36` siguen borrando por `code`, `command` o `rel_path` sin
  filtrar el dueño. En Odoo 14 no se ejecutan (formato de versión; ver PNS-88), pero sí en otras
  versiones.
- **Corrección sugerida:** usar `unlink_named_factory_skills`, como ya hace la migración `2.1.343`.

**PNS-70 (Media) — `window.Chart`**
- **Situación:** se sigue eligiendo el motor y creando el gráfico con la global (`typeof global.Chart`,
  `new global.Chart(...)`, `pns_ai_chatboo/static/src/js/chatboo_charts.js:1617-1636, 1983`), con
  Chart.js 4.4.8 en `web.assets_backend` (`views/assets.xml:22`).
- **Corrección sugerida:** guardar una referencia local a la librería al cargarla.

**PNS-73 (Baja) — Sintaxis y apilamiento**
- **Situación:** sigue el campo `static` de clase
  (`pns_ai_chatboo/static/src/js/chatboo_component_v2.js:183`) y `setup()` en el componente OWL (`:193`),
  y la capa con `z-index: 1050` (`static/src/js/chatboo_systray.js:432`;
  `static/src/css/chatboo_floating.css:1251`).
- **Corrección sugerida:** transpilar al nivel soportado por Odoo 14 y revisar el apilamiento con los
  diálogos del core.

**PNS-77 (Baja) — Sin tests**
- **Situación:** `pns_ai_chatboo` sigue sin carpeta `tests/`. Las reglas nuevas de aislamiento (PNS-53,
  PNS-55) no tienen tests propios.
- **Corrección sugerida:** tests negativos de aislamiento entre usuarios (PNS-53, PNS-55, PNS-57, PNS-82)
  y de saneado (PNS-60).

---

## 4. Hallazgos PNS-81 a PNS-96

Mismo criterio de gravedad que el informe anterior.

### 4.1 Hallazgos nuevos (PNS-93 a PNS-96)

Observados en el entorno de pruebas con el proveedor real. No figuraban en la entrega del 15/10.

| PNS | Gravedad | Módulo | Título | Verificación |
|---|---|---|---|---|
| PNS-93 | Media | pns_ai_mcp | El driver `openai` pierde la `thought_signature` de Gemini 3 | Entorno de pruebas |
| PNS-94 | Alta | pns_ai_chatboo | Bloqueo de `chatboo_session` tras un turno con adjunto: denegación de servicio | Entorno de pruebas |
| PNS-95 | Baja | pns_ai_chatboo, pns_ai_mcp | Formato de importes inconsistente y redondeo erróneo con usuarios `es_ES` | Entorno de pruebas |
| PNS-96 | Baja | pns_ai_chatboo, pns_ai_mcp | Calidad de las respuestas con modelos `lite` | Entorno de pruebas |

### PNS-93 — El driver `openai` pierde la `thought_signature` de Gemini 3 y todo turno con herramientas falla

- **Gravedad:** Media · **Verificación:** entorno de pruebas · **Módulo:** pns_ai_mcp
- **Ubicación:** `pns_ai_mcp/lib/llm/drivers/openai_driver.py:645-657` (`iter_chat`, reconstrucción de
  cada `tool_call`) y `:661-664` (mensaje final); `models/ai_provider.py:995-997` («Test Connection» sin
  herramientas); `utils/agent_engine.py:3215-3240` (llamadas escritas en texto).
- **Comportamiento:**
  - Con Gemini 3.x configurado con `protocol = openai` (endpoint compatible con OpenAI de Google), Gemini
    envía en cada `tool_call` el campo `extra_content.google.thought_signature` y exige recibirlo de vuelta
    en el mismo `tool_call` en la petición siguiente del turno.
  - `iter_chat` reconstruye cada `tool_call` solo con `id`, `type` y `function` y descarta
    `extra_content`. La segunda ronda del bucle de herramientas recibe `HTTP 400 … Function call is
    missing a thought_signature in functionCall parts`.
  - «Test Connection» funciona porque no envía herramientas, así que el fallo no se ve al configurar el
    proveedor.
  - El 400 se convierte en `ProviderConnectionError` y dispara el failover; con un solo proveedor, el
    usuario ve el error.
  - En la misma zona: la fila se indexa con `tc.get('index', 0)` (`:646`). Según los ejemplos públicos,
    Gemini no siempre envía `index`; dos llamadas paralelas que lleguen en deltas distintos caerían en la
    misma fila y se concatenarían. No lo hemos observado (§5). Las llamadas que el motor recupera del
    texto (`agent_engine.py:3215-3240`) tampoco llevan firma y darían el mismo 400.
- **Impacto:** con Gemini 3 por el protocolo OpenAI, Chatboo no puede responder ninguna pregunta que
  necesite consultar datos. No es un problema de seguridad ni de Odoo 14.
- **Cómo comprobarlo:** proveedor Gemini 3.x con protocolo `openai` y cualquier pregunta en Chatboo que
  obligue a consultar datos: la primera ronda devuelve el `tool_call` y la segunda recibe el 400.
- **Resultado con la corrección sugerida aplicada** (entorno de pruebas, con `gemini-3.6-flash`,
  `gemini-3.5-flash` y `gemini-3.5-flash-lite`): varias rondas de herramientas en el mismo turno y un
  segundo turno en la misma conversación, sin 400.
- **Corrección sugerida:** en `iter_chat`, conservar en la fila del `tool_call` el `extra_content` que
  traiga cualquier delta de esa llamada (no solo el primero); el motor ya reenvía ese mismo diccionario en
  la petición siguiente, y los proveedores que no envían el campo no se ven afectados. Además, abrir una
  fila nueva cuando un delta sin `index` traiga un `id` distinto, y documentar el caso de las llamadas
  recuperadas del texto.

### PNS-94 — Bloqueo de `chatboo_session` tras un turno con adjunto: denegación de servicio por cualquier usuario de Chatboo

- **Gravedad:** Alta · **Verificación:** entorno de pruebas (dos incidentes) · **Módulo:**
  pns_ai_chatboo
- **Ubicación:** `pns_ai_chatboo/models/chatboo_async_request.py:252-303` (`_spawn`, cursor del hilo en
  `:280`), `:507-519` (commit de las escrituras de sesión y excepción tragada), `:556-562` (escritura de
  `last_screen_context` tras ese commit), `:697` y `:712` (llamadas a `_finalize`), `:724` (`rollback` en
  el `finally`), `:835-918` (`_finalize`, segundo cursor en `:885-887`), `:1723` (`set_input_history`);
  `controllers/chatboo.py:286` (`update_last_used` en cada recarga).
- **Comportamiento:**
  - El turno se ejecuta en un hilo dentro del worker HTTP con un cursor propio (A) que mantiene la
    transacción abierta durante todo el turno.
  - Al terminar, `_finalize` abre en el mismo hilo otro cursor (B) y escribe la misma fila de
    `chatboo_session` (`input_history`, mensajes, adjuntos).
  - Si A tiene un lock sobre esa fila, B espera a A, y A no se cerrará nunca: su `rollback` está en el
    `finally`, después de `_finalize`, en el mismo hilo. PostgreSQL no lo detecta como interbloqueo (B
    espera a A y A está «idle in transaction») y ningún límite de Odoo (`limit_time_real`) afecta a un
    hilo de fondo.
  - El comentario de `:507-511` ya describe la colisión, y el commit de `:514` la evita solo en parte:
    cualquier escritura en la sesión por A después de ese commit la reabre. Nuestra hipótesis, según el
    código y los registros, es la escritura de `last_screen_context` (`:556-562`), que en los turnos con
    imagen llega a SQL por A en un flush durante el motor. No hemos confirmado la sentencia exacta (§5).
    Descartamos que el origen sea un fallo del commit de `:514`: los registros no contienen «could not
    commit the session writes».
  - Se reproduce siempre al adjuntar una imagen, también cuando el proveedor devuelve error (429). Los
    turnos de solo texto no lo provocan.
- **Impacto:**
  - El trabajo no llega a `done` y el navegador sigue esperando.
  - Cada recarga ejecuta `update_last_used()` sobre la misma fila, sin límite de espera, y ocupa un
    worker. Con 2 workers bastan unas pocas para dejar Odoo sin servicio HTTP.
  - Las conexiones quedan abiertas en PostgreSQL hasta reiniciar el proceso (PostgreSQL 15 no comprueba,
    por defecto, si el cliente sigue conectado mientras espera un lock); con varios incidentes se puede
    agotar el número de conexiones, que puede ser compartido con otras bases de datos.
  - **Cualquier usuario de Chatboo** (grupo conversacional y clave MCP propia, sin privilegios) puede
    provocarlo en el uso normal, sin querer.
- **Cómo comprobarlo:** en una sesión nueva de Chatboo, adjuntar una imagen pequeña y enviar una pregunta.
  Tras el turno, una consulta de solo lectura a `pg_stat_activity` muestra una conexión «idle in
  transaction» y otra esperando un lock `transactionid` en `UPDATE chatboo_session SET input_history=…`,
  bloqueada por la primera; el navegador no recibe el fin del turno.
- **Resultado con la corrección 1a aplicada** (entorno de pruebas, cinco casos: imagen con respuesta,
  imagen con error del proveedor, solo texto, cancelación y turno siguiente que recupera el contexto de
  pantalla): el navegador recibe el fin de turno, sin conexiones colgadas ni avisos en el registro. Como
  efecto conocido, el `last_screen_context` de un turno con imagen se pierde si A ya lo había enviado, y
  el turno siguiente usa el anterior guardado.
- **Corrección sugerida**, por orden de importancia:
  1. No escribir en `chatboo_session` con un segundo cursor mientras el cursor del hilo sigue abierto:
     (a) cerrar la transacción de A (`rollback`, conservando las escrituras ORM pendientes que deba
     guardar `_finalize`) inmediatamente antes de las llamadas de `:697` y `:712`; o, mejor, (b) que toda
     escritura en la sesión durante el turno, incluida la de `last_screen_context`, se haga en cursores
     cortos que confirmen en el acto, como ya hacen el progreso y el latido.
  2. No tragarse un commit fallido (`:512-519`): hacer `rollback` y abortar el turno de forma controlada.
  3. Acotar las esperas sobre la fila de sesión con `SET LOCAL lock_timeout` en `_finalize` y en las rutas
     que escriben la sesión (`load_session`, `save_session`…), como ya se hace en
     `pns_ai_mcp/models/ai_provider.py:1063-1065` y `models/ai_context.py:1222-1223`.
  4. No ejecutar trabajo largo en hilos dentro de los workers prefork (una cola procesada por cron, o
     como mínimo `statement_timeout`/`idle_in_transaction_session_timeout` en el cursor A).
  5. Si `_finalize` no obtiene el lock en N segundos, registrar un error claro y cerrar el trabajo por SQL
     corto, para que el navegador reciba el fin.

  Como defensa adicional en el servidor (no corrige el fallo), puede documentarse
  `idle_in_transaction_session_timeout` para el rol de Odoo.

### PNS-95 — Formato de importes inconsistente y redondeo erróneo con usuarios `es_ES`

- **Gravedad:** Baja · **Verificación:** entorno de pruebas · **Módulos:** pns_ai_chatboo, pns_ai_mcp
  (relacionado con PNS-46)
- **Ubicación:** sin localizar en el código. El formato lo produce el modelo; la parte fija del prompt no
  incluye el glosario `corporate_terms_es_ES` (composición en `pns_ai_mcp/models/ai_context.py:818-826`;
  ver PNS-46).
- **Comportamiento:** con un usuario `es_ES`, las respuestas con importes usan unas veces `1,234.50` y
  otras `1.234,50`, y en una misma respuesta el texto y la tabla se contradicen. Además, un importe de
  `1493,745` aparece como `1.493,74` en la tabla; puede venir de la representación en coma flotante
  (`1493,745` no es exacto en binario), sin comprobar.
- **Impacto:** cifras ambiguas o incorrectas en respuestas financieras para usuarios españoles.
- **Cómo comprobarlo:** con un usuario `es_ES`, pedir varias veces un resumen con importes con decimales
  y comparar el formato entre ejecuciones y entre texto y tabla.
- **Corrección sugerida:** formatear los importes en el servidor según el idioma del usuario (o incluir de
  forma fiable el glosario y el formato en el prompt) y redondear con `Decimal` o con la precisión de la
  moneda; guardar el prompt de los turnos en `ai.log` para poder auditarlo (§5).

### PNS-96 — Calidad de las respuestas con modelos `lite`

- **Gravedad:** Baja (observación de calidad; depende en parte del modelo) · **Verificación:** entorno de
  pruebas · **Módulos:** pns_ai_chatboo, pns_ai_mcp
- **Ubicación:** sin localizar en el código.
- **Comportamiento:** con modelos `lite` (en las pruebas, `gemini-3.5-flash-lite`), el asistente
  interpreta mal «empresas», inventa ids en los enlaces a registros (el enlace llevaba a otro registro),
  muestra al usuario los errores de acceso tal cual (relacionado con PNS-40) y añade «>» de más al
  formato.
- **Impacto:** enlaces que llevan a otro registro o a ninguno, y mensajes de error técnicos en el chat.
  Sin efecto de seguridad observado: los accesos se siguen comprobando en Odoo.
- **Cómo comprobarlo:** con un modelo `lite`, preguntar por registros concretos y comprobar que el id de
  cada enlace coincide con el devuelto por la herramienta.
- **Corrección sugerida:** construir los enlaces a partir de los ids devueltos por la herramienta, no del
  texto del modelo; traducir los errores de acceso a un mensaje para el usuario; y documentar los modelos
  mínimos recomendados.

### 4.2 Hallazgos comunicados el 15/10 (PNS-81 a PNS-92)

El detalle, el impacto y la corrección sugerida de cada uno están en la entrega del 15/10 (§2, §3, §4 y
§6 de aquella). Aquí solo se indica su estado actual y lo que ha cambiado desde entonces. Estado
**ABIERTO**: sin corregir en las versiones revisadas, que son las mismas que el 15/10.

| PNS | Gravedad | Título | Estado actual | Desde el 15/10 |
|---|---|---|---|---|
| PNS-81 | Alta | Incompatibilidades con Odoo 14: el módulo no se importa y tres funciones fallan en ejecución | ABIERTO | **Sí:** correcciones 2 y 3 comprobadas con turnos reales (ver abajo) |
| PNS-82 | Alta | `claim_turn_file_chips` se apropia de adjuntos ajenos | ABIERTO | — (entrega del 15/10, §2.4 y §6) |
| PNS-83 | Alta | `redeem_key_pin` entrega claves MCP sin grupo y sin límite efectivo de intentos | ABIERTO | — (entrega del 15/10, §2.2 y §6) |
| PNS-84 | Media | PIN y clave MCP en claro en la base de datos y en el navegador | ABIERTO | — (entrega del 15/10, §6) |
| PNS-85 | Media | Caché de parámetros de skills escribible por cualquier usuario | ABIERTO | — (entrega del 15/10, §2.5 y §6) |
| PNS-86 | Media | Generador OpenAPI sin control de hosts no públicos, redirecciones ni tamaño | ABIERTO | — (entrega del 15/10, §6) |
| PNS-87 | Baja | Pérdida de datos de consumo al actualizar | ABIERTO | — (entrega del 15/10, §4.1 y §6) |
| PNS-88 | Baja | Renombrados de XML ID que no se ejecutan en Odoo 14 y servidores heredados | ABIERTO | — (entrega del 15/10, §4.2 y §6) |
| PNS-89 | Baja | `/pns_ai_mcp/key_pin/stop` sin CSRF | ABIERTO | — (entrega del 15/10, §6) |
| PNS-90 | Alta | Caché de `fetch_url` legible y sobrescribible por cualquier usuario | ABIERTO | — (entrega del 15/10, §2.3 y §6) |
| PNS-91 | Media | Lista blanca de URL ampliable sin control de grupo | ABIERTO | — (entrega del 15/10, §2.6 y §6) |
| PNS-92 | Media | Clave MCP escrita en `sudo` sin control previo | ABIERTO | — (entrega del 15/10, §6) |

**PNS-81 — Qué cambia desde el 15/10.** Las correcciones 2 y 3, que el 15/10 quedaban pendientes de un
turno real, se han comprobado con el proveedor real. Con las cuatro correcciones sugeridas aplicadas:

- la consulta por rango de fechas con una función con parámetros de fecha responde sin error
  (corrección 2, entorno de pruebas);
- una foto con orientación EXIF adjunta en el chat llega derecha al modelo (corrección 3, laboratorio y
  entorno de pruebas);
- `prompts/list` y `prompts/get` sirven los contextos compartidos y el privado del usuario, no los de
  otros usuarios (corrección 4, ahora también en el entorno de pruebas).

Las correcciones sugeridas no cambian. Seguimos pendientes de una fecha prevista para la versión que
corrija PNS-81.

**Recuento final:** 96 hallazgos. De PNS-01 a PNS-80: CORREGIDO 31 · PARCIAL 33 · SIN CAMBIOS 13 · YA NO
APLICA 2 · DUDOSO 1, sin cambios de estado desde el 15/10. Nuevos respecto al informe anterior: 16 (Alta
5, Media 6, Baja 5): 12 comunicados el 15/10 (PNS-81 a PNS-92, abiertos) y 4 nuevos en esta entrega
(PNS-93 a PNS-96).

---

## 5. Qué hemos probado y qué no

Las pruebas en el entorno de pruebas se hicieron con datos de demostración, textos inocuos y usuarios
internos (sin portal; el portal solo se usó en el laboratorio).

De las 12 comprobaciones que la entrega del 15/10 dejaba pendientes (§8 de aquella), se completaron 7:
PNS-05, PNS-12, PNS-36, PNS-61, PNS-81 (correcciones 2 y 3) y PNS-60 (respuesta y exportación). Cuatro
dieron un resultado parcial o no concluyente (PNS-16, PNS-22, PNS-46 y PNS-59) y una no se hizo (PNS-29).

Estas comprobaciones no se hicieron o no fueron concluyentes. «Desde el 15/10» indica si la situación
cambia respecto a aquella entrega:

| Comprobación | Hallazgo | Situación y motivo | Desde el 15/10 |
|---|---|---|---|
| Tokens de escritura en la caché de prompt de Anthropic, frente a la consola del proveedor | PNS-29 | **No realizada:** el entorno de pruebas usaba Gemini. El resto se deduce del código (`llm_usage.py:94-99`). | Sin cambios: sigue pendiente |
| Reinyección del turno anterior como `system` con la política de URL restringida | PNS-16 | **No concluyente.** Con `open` no se manifestó (la tarjeta apareció también en el turno de reutilización). El resto se deduce del código. | Cambia: probada (pendiente el 15/10) |
| Imágenes externas en las respuestas con la política `open` | PNS-59 | **No concluyente:** el modelo no incluyó la imagen en la respuesta. | Cambia: probada (pendiente el 15/10) |
| Llamadas paralelas de Gemini sin `index` | PNS-93 | **No observadas** en las pruebas; el riesgo se deduce del código y de ejemplos públicos. Tampoco probamos la ausencia de regresión con otro proveedor compatible con OpenAI. | Nueva |
| Origen exacto del lock en los turnos con imagen | PNS-94 | **No confirmado:** no se activó el registro de sentencias de PostgreSQL. La corrección sugerida no depende de cuál sea la sentencia. | Nueva |
| Secuencia completa de actualización desde 3.1.486 con datos reales | PNS-87, PNS-88, PNS-63 | **Solo en el laboratorio**, con una base de datos de prueba. El entorno de pruebas fue una instalación nueva. | Sin cambios |
| Medida real de las purgas al actualizar (`ai.log`, `ai_provider_usage_day`, sesiones de Chatboo) | PNS-87, PNS-63 | **No medida:** las tablas estaban vacías. Se observó que los crons se ejecutan en la primera pasada; el volumen se deduce del código. | Sin cambios |
| Personalizaciones sobre los 38 registros `mcp_*` | PNS-88 | **No probada:** la base de datos de prueba no tenía personalizaciones; se observó el borrado y la recreación con ids nuevos. | Sin cambios |
| Presencia del glosario `es_ES` en lo que recibe el modelo | PNS-46, PNS-95 | **No concluyente:** `prompt_data` de `ai.log` no guarda el prompt de los turnos de Chatboo (el bucle de herramientas registra la petición sin él, `agent_engine.py:3134-3146`). En el laboratorio, la parte fija reconstruida no contenía el glosario para ningún idioma. Pedimos poder registrar el prompt. | Cambia: probada (pendiente el 15/10) |
| Escritura pedida por un usuario sin AI Writer por `/mcp` | PNS-22 | **No probada** (sí por Chatboo, corregido). El resto de `tools/call` se deduce del código. | Cambia: probada por Chatboo |
| AI Administrator sin Ajustes que se concede `base.group_system` | PNS-01, PNS-02 | **No probada** a propósito; la verificaremos con la versión corregida. | Sin cambios |
| Llamada a métodos privados desde el sandbox | PNS-07, PNS-19 | **No probada;** se deduce del código y del docstring de `guarded_getattr`. | Sin cambios |
| Aceptación en servidor de `confirm`/`execute` sin espera para riesgo alto | PNS-54 | **No probada;** se deduce del código. | Sin cambios |
| `escapeHtml` sin comillas, lista negra del saneador y Showdown | PNS-60 | **No probados;** la parte probada (mensaje y respuesta, exportación) está corregida. | Cambia: probadas la respuesta y la exportación |
| `/mcp/message` con una sesión sin usuario | PNS-79 | **No concluyente:** no hemos encontrado un camino que cree una sesión sin usuario. | Sin cambios |
| Clave en `ai.key.pin.ask` tras vencer la espera | PNS-84 | **No probada;** no se abrió la mesa de entrega. | Sin cambios |
| Parámetro de retención de Chatboo creado a mano antes de actualizar | PNS-63 | **No probado:** según el código chocaría con `key_uniq` (§6). | Sin cambios |
| Batería de tests de `pns_ai_mcp` en 3.1.782 | PNS-50 | **No ejecutada** en esta versión. | Sin cambios |
| Avisos publicados para jsPDF 4.2.1 y versión de `jspdf.plugin.autotable.min.js` | PNS-27 | **No revisados.** | Sin cambios |
| Cursores propios en `ai_log.py`, `ai_change_journal.py`, `ai_provider.py`, `ai_agent.py`, `ai_context.py` y `ai_skill_param_cache.py` | PNS-07 | **No revisados uno a uno.** | Sin cambios |

Les comunicaremos cualquier resultado posterior que cambie lo dicho en este informe.

---

## 6. Observaciones menores

Sin número. Ninguna es urgente; las recogemos para una próxima versión. Las 1 a 5 y la 12 ya figuraban
en la entrega del 15/10; las demás son nuevas.

1. **`system_prompt` duplicado en `prompts/list`.** Una vez corregido el fallo 4 de PNS-81,
   `system_prompt` aparece dos veces: la entrada fija del controlador
   (`pns_ai_mcp/controllers/main.py:1448`) y el contexto core cuyo `code` es también `system_prompt`.
   Nombres duplicados pueden confundir a los clientes MCP. **Petición:** omitir uno o darles nombres
   distintos.
2. **Prefijo de la clave MCP en el log** (resto de PNS-33). Se registran a nivel INFO los 10 primeros
   caracteres de la clave en cada petición (`pns_ai_mcp/controllers/main.py:863, 869`). **Petición:** no
   registrar ninguna parte de la clave.
3. **Copia de la clave al duplicar un proveedor** (PNS-20). El campo `api_key` no lleva `copy=False`
   (`pns_ai_mcp/models/ai_provider.py:194-198`): duplicar un proveedor copia su clave. Solo puede duplicar
   quien ya lee la clave, así que no hay ganancia de privilegio, pero la clave se multiplica en registros
   que quizá no se revisen. Ya existía en 3.1.486. **Petición:** `copy=False`.
4. **El parche de `Root.get_request` afecta a todas las bases de datos del proceso** (PNS-31). Está
   acotado a las rutas `/mcp`, pero no a la base de datos: sustituye `odoo.http.Root.get_request` al
   importar el módulo (`pns_ai_mcp/http_patch.py:22-35`, importado desde `pns_ai_mcp/__init__.py:15`), con
   la única condición de la versión de Odoo (`NEEDS_ROOT_GET_REQUEST_PATCH`,
   `pns_base/utils/compat.py:20`). Afecta a todas las bases de datos que sirve el mismo proceso, tengan o
   no instalado `pns_ai_mcp`; en la práctica solo cambia el tratamiento de las peticiones `POST` JSON a
   `/mcp` y `/mcp/*`. **Sugerimos** documentarlo o aplicarlo solo cuando la base de datos de la petición
   tenga el módulo instalado.
5. **Retención de sesiones de Chatboo en la primera pasada tras actualizar** (nota sobre PNS-63). La purga
   global es la corrección pedida y está bien resuelta
   (`pns_ai_chatboo/models/chatboo_session.py:1360-1381`, llamada cada 5 minutos desde
   `models/chatboo_async_request.py:2167`). Pero, igual que en PNS-87, en la primera pasada tras
   actualizar borra todas las sesiones (y sus adjuntos) de más de 30 días. El parámetro
   `pns_ai_chatboo.history_retention_days` se crea con un registro de datos `noupdate="1"` que no existía
   en 2.1.322 (`data/chatboo_icp_data.xml:8-11`); según el código, si un administrador lo crea a mano
   antes de actualizar, la carga de ese registro chocaría con la restricción `key_uniq`. **Petición:**
   avisarlo en las notas de versión y crear el parámetro por código solo si no existe.
6. **Descargas del chat fuera de la purga de 24 h** (PNS-21). Los adjuntos de `session_download` no llevan
   la marca de exportación, así que no entran en la purga de 24 h que sí tienen las copias de
   configuración.
7. **Errores con detalle técnico.** `_fx_payload` devuelve `str(exc)` si falla el cálculo de divisas
   (`pns_ai_chatboo/controllers/chatboo.py:1024-1029`); ver también PNS-40 y PNS-96.
8. **`ai.execution.engine.choose` es público** (`pns_ai_mcp/models/ai_execution_engine.py:266-285`).
   Cualquier usuario autenticado puede lanzar por RPC una pregunta de elección cerrada a la cadena de
   decisión con la clave de la empresa; el resultado no se serializa y la llamada acaba en error, pero el
   coste ya se ha producido. Impacto marginal; relacionado con PNS-29 y §2.2.
9. **Agente sin cadena de proveedores.** Si el agente de Chatboo no tiene cadena, sirve cualquier
   proveedor activo (`pns_ai_mcp/models/ai_execution_engine.py:210-226`). Es una decisión de
   configuración, pero conviene documentarla: puede enviar datos a un proveedor externo que no se pensaba
   usar para el chat.
10. **Consulta de tipos de cambio al abrir Chatboo.** La hace el servidor dentro de `check_health`
    (`pns_ai_chatboo/controllers/chatboo.py:101` → `pns_ai_mcp/models/ai_fx_source.py:72-78`), con el
    resultado guardado un día. Conviene documentar esta salida a Internet; ya cubierto en lo demás por
    PNS-47 y PNS-72.
11. **Skill retirada borrada en cada actualización.** La semilla `pns_ai_chatboo/data/chatboo_skill_data.xml:9-10`,
    cargada en cada actualización, llama a `unlink_named_factory_skills` con `analisis_financiero` y
    `analisis-financiero`. Es correcto (solo borra las de fábrica), pero se ejecuta siempre; podría
    limitarse a una vez.
12. **`detect_dangerous_operations` sin uso y con un fallo latente**
    (`pns_ai_mcp/controllers/validators.py:2330-2337`). Se importa (`controllers/main.py:91`) pero no se
    llama; en Python 3.7 sus comparaciones de `.slice` no coinciden y la rama de `:2335` lanzaría
    `AttributeError` en cualquier asignación que no sea una llamada. Conviene borrarla o corregirla.
13. **Tests que cambian la clave del administrador** (PNS-34, corregido). Si la ejecución se corta entre
    el montaje y el desmontaje, el administrador se queda con una clave aleatoria (no conocida). Menor.
