# Inventario de hallazgos sobre 3.1.973: base de la 2.ª entrega del informe al fabricante

- **Fecha:** 20/11/2026.
- **Objeto:** estado de cada hallazgo de la evaluación frente a lo que se entrega ahora: los módulos del fabricante
  `pns_base` 1.2.69, `pns_ai_mcp` 3.1.973 y `pns_ai_chatboo` 2.1.587, y la rama de Seges (`14.0`, con
  `14.0-pns-ai-informe`; sin cambios en los módulos desde `52a3a5e`). Dice qué va a cada sección del
  [informe al fabricante](../informe_fabricante_pns_ai_3973.md) y de la [nota interna](resumen_jefe_pns_ai.md). No es
  la redacción del informe.
- **Rama al hacerlo:** `14.0-pns-ai-informe`, HEAD `24fa109`, con push.
- **Método:** solo lectura de documentos, sin volver a mirar el código ni ejecutar nada. Cada fila combina:
  - el [inventario sobre 3.1.879](../../specs/estado_hallazgos_3879.md), §3 (**est** y número de línea), con las
    decisiones de Sergio del 09/11/2026 ya aplicadas;
  - el veredicto en 3.1.973 de la [comparación](../../specs/comparacion_pns_ai_3-1-973.md), §3.1 a §3.5 (**comp** y
    número de línea);
  - el índice de la rama 3973 del [registro de parches](../parches_pns_ai.md) («Índice de la rama `14.0-pns-ai-3973`»):
    parches retirados (10, 13, 14, 23, 30 y 31) y aplicados;
  - para lo posterior al 10/11/2026: [seguimiento](../seguimiento_informe_pns_ai.md) (fichas PNS-103 a PNS-107 y
    «Observaciones sin ficha»), [plan de la 3973](../plan_correccion_pns_ai_3973.md) y registro, «Para el informe al
    fabricante» (fases 3b y 4).
- **Lo que no se ha vuelto a revisar en 3.1.973** (lo dice la propia comparación, §1, «Límites»): las filas CF782
  Medias y Bajas (13) y las filas solo CF cuyo código no toca 3.1.973. En la columna «3.1.973» figuran como «CF782 (no
  revisado en 3.1.973)» o «CF (verificado en 3.1.879; no revisado en 3.1.973)». En el informe van como corregidas, con
  esa salvedad en «Qué hemos probado y qué no».
- **Ficha 26 (casilla AI Conversational):** fuera del informe (D70, 20/11/2026).

**Columnas:**

- **3.1.973 (fabricante):** CORREGIDO · PARCIAL · SIN CAMBIO · NO APLICA, con la precisión de la comparación. «CORREGIDO
  (sigue en 3.1.973)»: fila CF cuyo código toca 3.1.973 y la comparación da por todavía corregida (comp §3.3).
- **Rama de Seges:** parche que lo corrige en la rama (`pN`), retirado o «—» (sin parche).
- **Informe:** sección del informe al fabricante.
  - **§3 corregido:** comunicado y corregido por el fabricante. Va en la tabla, sin comentario.
  - **§3 abierto · corregido en la rama de Seges:** comunicado, sigue en 3.1.973 y Seges lo corrige en su instalación.
    Se describe la corrección sin código (D2) y se pide al fabricante.
  - **§3 abierto · aceptado por Seges:** comunicado y sigue. Seges acepta el riesgo (se repite la petición si la fila
    tiene AI).
  - **§3 abierto:** comunicado y sigue, sin parche ni aceptación.
  - **§4:** hallazgo con número no comunicado (PNS-97 a PNS-107, salvo PNS-101 y PNS-106), con ficha.
  - **§5:** hallazgos de 3.1.973 y de la rama 3973, y los corregidos por Seges que no se habían comunicado.
  - **§6:** actualización desde versiones anteriores.
  - **§8:** observación menor.
  - **«—»:** fuera del informe, con el motivo. Los que van a la nota interna lo dicen.

## 1. Resumen

| Grupo | Filas |
|---|---|
| Comunicados (08/10, 15/10 y 16/10): PNS-01 a PNS-96, obs. 1 a 13, petición de §5 y compatibilidad sin número | 111 |
| · corregidos por el fabricante | 84 |
| · abiertos y corregidos en la rama de Seges | 12 |
| · abiertos y aceptados por Seges | 9 |
| · abiertos, sin parche ni aceptación | 6 |
| No comunicados, del inventario sobre 3.1.879 | 78 |
| · al informe (§4, §5, §6 y §8) | 37 |
| · fuera (cerrados, corregidos por 3.1.973, aceptados, no aplican o D70) | 41 |
| Altas posteriores al inventario sobre 3.1.879 (§4 de este documento) | 18 |

Las filas «— lo corrige 3.1.973» (8) entran en el informe en una tabla de una línea del §5 (decisión 2).

## 2. Comunicados al fabricante

| Id | Grav. | Título corto | 3.1.973 (fabricante) | Rama de Seges | Informe | Fuente |
|---|---|---|---|---|---|---|
| PNS-01 | Crítica | Escalada de grupos por plan | PARCIAL | p12 | §3 abierto · corregido en la rama de Seges | est 311; comp 267 |
| PNS-02 | Crítica | `apply_*` y quitar grupos | PARCIAL | p12 | §3 abierto · corregido en la rama de Seges | est 312; comp 268 |
| PNS-03 | Crítica | Dueño cambia `status`/`user_id` de su operación | CORREGIDO | — | §3 corregido | est 313; comp 299 |
| PNS-04 | Crítica | `confirmed_uid` elegido por quien llama | CORREGIDO | — | §3 corregido | est 314; comp 300 |
| PNS-05 | Crítica | `get_safe_operation_status` sin filtro | CORREGIDO | — | §3 corregido | est 315; comp 301 |
| PNS-06 | Crítica | `code_body` ejecutado al guardar | CORREGIDO, más amplio | — | §3 corregido | est 316; comp 302 |
| PNS-07 | Crítica | Métodos públicos con cursor propio desde el sandbox | PARCIAL | p15 (9 nombres que siguen públicos) | §3 abierto · corregido en la rama de Seges | est 317; comp 269 |
| PNS-08 | Alta | Credenciales de `ai.api.server` legibles | CORREGIDO, más amplio | — | §3 corregido | est 318; comp 304 |
| PNS-09 | Alta | MCP `stdio` | CORREGIDO, más amplio | — | §3 corregido | est 319; comp 305 |
| PNS-10 | Alta | `skip_hardcoded_restrictions` por contexto | CORREGIDO | — | §3 corregido | est 320; comp 306 |
| PNS-11 | Alta | Métodos públicos de `ai.skill`/`ai.context` en `sudo` | CORREGIDO | — | §3 corregido | est 321; comp 307 |
| PNS-12 | Alta | Contextos privados expuestos | CORREGIDO | — | §3 corregido | est 322; comp 308 |
| PNS-13 | Alta | `/mcp/message` sin revalidar | CORREGIDO | — | §3 corregido | est 323; comp 309 |
| PNS-14 | Alta | Cachés legibles por todos | CORREGIDO, más amplio | — | §3 corregido | est 324; comp 310, 326 |
| PNS-15 | Alta | HTML sin sanear | CORREGIDO | — | §3 corregido | est 325; comp 311 |
| PNS-16 | Alta | Prompt injection y autoconfirmación | CORREGIDO (sigue en 3.1.973) | — | §3 corregido | est 326; comp 327 |
| PNS-17 | Alta | Cabeceras en redirecciones (SSRF) | SIN CAMBIO (el resto principal) | p19 | §3 abierto · corregido en la rama de Seges | est 327; comp 274 |
| PNS-18 | Alta (seg); sin gravedad (comp) | «Sin failover externo» no corta en todos los caminos | SIN CAMBIO | — | §3 abierto · aceptado por Seges | est 328; comp 275 |
| PNS-19 | Alta | Credenciales alcanzables por relaciones | PARCIAL | p18 rehecho (O1, B y B2; ampliado por P-22) | §3 abierto · corregido en la rama de Seges | est 329; comp 276 |
| PNS-20 | Alta | Importación que sobrescribe; «Review» escribe | SIN CAMBIO | p21 | §3 abierto · corregido en la rama de Seges | est 330; comp 277 |
| PNS-21 | Alta | Exportaciones sin sesión | CORREGIDO | — | §3 corregido | est 331; comp 312 |
| PNS-22 | Media | `is_write` no centralizado | CF (verificado en 3.1.879; no revisado en 3.1.973) | — | §3 corregido | est 332 |
| PNS-23 | Alta | Skills activas sin revisión | SIN CAMBIO (la causa) | — | §3 abierto · aceptado por Seges | est 333; comp 278 |
| PNS-24 | Alta | `module.update` | CORREGIDO (sigue en 3.1.973); nuevo `_require_settings` | — | §3 corregido | est 334; comp 328 |
| PNS-25 | Alta | Doble ejecución tras failover | CORREGIDO | — | §3 corregido | est 335; comp 313 |
| PNS-26 (anexo: serialización en `/execute` de la tarjeta) | Alta (anexo Baja) | `SAVEPOINT` del motor y `commit` de la caja B | SIN CAMBIO | — (anexo: tests, sin parche) | §3 abierto | est 336; comp 279 |
| PNS-27 | Alta | jsPDF/SheetJS con CVE | CORREGIDO | — | §3 corregido | est 337; comp 314 |
| PNS-28 | Media | CORS y `Origin` | SIN CAMBIO | — | §3 abierto | est 338; comp 363 |
| PNS-29 | Media | Tope de gasto y `month_usage` | SIN CAMBIO | p33 | §3 abierto · corregido en la rama de Seges | est 339; comp 364 |
| PNS-30 | Media | `ai.log` modificable a nombre de otro | CORREGIDO | p30 retirado: lo cubre 3.1.973 | §3 corregido | est 340; comp 365 |
| PNS-31 (obs. 4) | Media | Parches globales | CF (verificado en 3.1.879; no revisado en 3.1.973) | — | §3 corregido | est 341 |
| PNS-32 | Media | Sincronización de fábrica | CF (verificado en 3.1.879; no revisado en 3.1.973) | — | §3 corregido | est 342 |
| PNS-33 | Media | Claves MCP | SIN CAMBIO | — | §3 abierto · aceptado por Seges | est 343; comp 366 |
| PNS-34 | Media | Test con commit de una clave | CF782 (no revisado en 3.1.973) | — | §3 corregido | est 344 |
| PNS-35 | Media | Fórmulas en XLSX | CF (verificado en 3.1.879; no revisado en 3.1.973) | — | §3 corregido | est 345 |
| PNS-36 | Media | Nombre de la BD por `.format` | CORREGIDO (P-6, §9) | p23 retirado: lo cubre 3.1.973 | §3 corregido | est 346; comp 367 |
| PNS-37 | Media (parte Alta, propuesta) | Papelera del diario y borrado por plan | SIN CAMBIO | p17 | §3 abierto · corregido en la rama de Seges | est 347; comp 368 |
| PNS-38 | Media | Conocimiento de fábrica | CF (verificado en 3.1.879; no revisado en 3.1.973) | — | §3 corregido | est 348 |
| PNS-39 | Media | Desviaciones MCP | CF (verificado en 3.1.879; no revisado en 3.1.973) | — | §3 corregido | est 349 |
| PNS-40 | Media | Parámetros LLM y endpoint en el error | CF (verificado en 3.1.879; no revisado en 3.1.973) | — | §3 corregido | est 350 |
| PNS-41 | Media | `website` de todos los módulos | CF (verificado en 3.1.879; no revisado en 3.1.973) | — | §3 corregido | est 351 |
| PNS-42 | Media | Validación global de formularios | CF (verificado en 3.1.879; no revisado en 3.1.973) | — | §3 corregido | est 352 |
| PNS-43 | Baja | Traducciones duplicadas | CF (verificado en 3.1.879; no revisado en 3.1.973) | — | §3 corregido | est 353 |
| PNS-44 | Baja | Escrituras en `ir.module.module` | CF782 (no revisado en 3.1.973) | — | §3 corregido | est 354 |
| PNS-45 | Baja | `ImportError` silenciado | CF782 (no revisado en 3.1.973) | — | §3 corregido | est 355 |
| PNS-46 | Baja | Glosario `es_ES` | CF (verificado en 3.1.879; no revisado en 3.1.973) | — | §3 corregido | est 356 |
| PNS-47 | Baja | Esperas de las fuentes FX | CF782 (no revisado en 3.1.973) | — | §3 corregido | est 357 |
| PNS-48 | Baja | Menú Settings | CF782 (no revisado en 3.1.973) | — | §3 corregido | est 358 |
| PNS-49 (obs. 12) | Baja | Código muerto | CF (verificado en 3.1.879; no revisado en 3.1.973) | — | §3 corregido | est 359 |
| PNS-50 | Baja | Tests no cargados | PARCIAL (mejora) | — | §3 abierto · aceptado por Seges | est 360; comp 386 |
| PNS-51 | Baja | `platform` en el sandbox | SIN CAMBIO | — | §3 abierto · aceptado por Seges | est 361; comp 394 |
| PNS-52 | Baja | `settings_io` | CF782 (no revisado en 3.1.973) | — | §3 corregido | est 362 |
| PNS-53 | Crítica | XSS almacenado entre usuarios | CORREGIDO | — | §3 corregido | est 363; comp 303 |
| PNS-54 (anexo: `missing_token`/`bad_token`) | Crítica | Confirmación sin el usuario | SIN CAMBIO | p16 | §3 abierto · corregido en la rama de Seges | est 364; comp 270 |
| PNS-55 (D4) | Alta | Aislamiento de Chatboo | CORREGIDO (sigue en 3.1.973) | — | §3 corregido | est 365; comp 329 |
| PNS-56 | Alta | Inyección en el turno de otro | CORREGIDO | — | §3 corregido | est 366; comp 315 |
| PNS-57 | Alta | Turnos por RPC sin clave | CORREGIDO | — | §3 corregido | est 367; comp 316 |
| PNS-58 | Alta | `/chatboo/stream` sin CSRF | CORREGIDO | — | §3 corregido | est 368; comp 317 |
| PNS-59 | Alta | Imágenes externas | CORREGIDO (sigue en 3.1.973), con mejora | — | §3 corregido | est 369; comp 330 |
| PNS-60 | Alta | HTML del asistente sin sanear | CORREGIDO (sigue en 3.1.973) | — | §3 corregido | est 370; comp 331 |
| PNS-61 | Media | Historial escrito por el navegador | SIN CAMBIO | — | §3 abierto · aceptado por Seges | est 371; comp 369 |
| PNS-62 | Media | Adjuntos sin límites | CF (verificado en 3.1.879; no revisado en 3.1.973) | — | §3 corregido | est 372 |
| PNS-63 | Media | Retención de sesiones | CF782 (no revisado en 3.1.973) | — | §3 corregido | est 373 |
| PNS-64 | Media | Voces remotas | CF (verificado en 3.1.879; no revisado en 3.1.973) | — | §3 corregido | est 374 |
| PNS-65 | Media | Exportaciones del navegador | CF (verificado en 3.1.879; no revisado en 3.1.973) | — | §3 corregido | est 375 |
| PNS-66 | Media | Skills sin grupo | CF (verificado en 3.1.879; no revisado en 3.1.973) | — | §3 corregido | est 376 |
| PNS-67 | Media | Errores en skills financieras | CF782 (no revisado en 3.1.973) | — | §3 corregido | est 377 |
| PNS-68 | Media | Migraciones que borran skills | CF (verificado en 3.1.879; no revisado en 3.1.973) | — | §3 corregido | est 378 |
| PNS-69 | Baja | `SELF_*_FIELDS` como `property` | CF782 (no revisado en 3.1.973) | — | §3 corregido | est 379 |
| PNS-70 | Alta (desde 23/10; antes Media) | Chart.js 4 en `window.Chart` | SIN CAMBIO | p20 | §3 abierto · corregido en la rama de Seges | est 380; comp 280 |
| PNS-71 | Baja | `check_health` expone infraestructura | CF782 (no revisado en 3.1.973) | — | §3 corregido | est 381 |
| PNS-72 | Baja | Librerías JS en todo el backend | CF (verificado en 3.1.879; no revisado en 3.1.973) | — | §3 corregido | est 382 |
| PNS-73 | Baja | Sintaxis y `z-index` | CF (verificado en 3.1.879; no revisado en 3.1.973) | — | §3 corregido | est 383 |
| PNS-74 (obs. 12) | Baja | Código muerto del cliente | CF (verificado en 3.1.879; no revisado en 3.1.973) | — | §3 corregido | est 384 |
| PNS-75 | Baja | TSV sin neutralizar fórmulas | CF782 (no revisado en 3.1.973) | — | §3 corregido | est 385 |
| PNS-76 | Baja | Receta del agente | CF (verificado en 3.1.879; no revisado en 3.1.973) | — | §3 corregido | est 386 |
| PNS-77 | Baja | Chatboo sin tests | PARCIAL (mejora) | — | §3 abierto · aceptado por Seges | est 387; comp 387 |
| PNS-78 | Baja | Etiquetas duplicadas en `ai.agent` | CF782 (no revisado en 3.1.973) | — | §3 corregido | est 388 |
| PNS-79 | Baja | `/mcp/message` con `SUPERUSER_ID` | CF782 (no revisado en 3.1.973) | — | §3 corregido | est 389 |
| PNS-80 | Alta | `read_progress` | CF782 (no revisado en 3.1.973) | — | §3 corregido | est 390 |
| PNS-81 (parches 1 a 4) | Alta | Incompatibilidades con Odoo 14 | CORREGIDO (también el resto de Python 3.7) | p1 a p4 retirados (corregido por el fabricante) | §3 corregido | est 391; comp 281, 332 |
| PNS-82 (parche 11) | Alta (resto Baja) | Reclamación y borrado de adjuntos ajenos | SIN CAMBIO | p11 | §3 abierto · corregido en la rama de Seges | est 392; comp 282 |
| PNS-83 (`collect_pin`) | Alta | Canje de PIN sin límite | CORREGIDO | p10 retirado (lo cubre 3.1.973) | §3 corregido | est 393; comp 283 |
| PNS-84 (hoja 7) | Media | PIN y clave en tránsito | PARCIAL (mejora) | p10 retirado (cubierto); resto aceptado | §3 abierto · aceptado por Seges | est 394; comp 370 |
| PNS-85 (parche 9) | Media | Caché de parámetros de skills | CF (verificado en 3.1.879; no revisado en 3.1.973) | p9 retirado (lo corrigió el fabricante) | §3 corregido | est 395 |
| PNS-86 | Media | Generador OpenAPI | CF (verificado en 3.1.879; no revisado en 3.1.973) | — | §3 corregido | est 396 |
| PNS-87 | Baja | Pérdida de datos de consumo al actualizar | CF (verificado en 3.1.879; no revisado en 3.1.973) | — | §3 corregido | est 397 |
| PNS-88 (hoja 11) | Baja | Renombrados de 3.1.518 que faltan | SIN CAMBIO | — | §3 abierto · aceptado por Seges | est 398; comp 391 |
| PNS-89 | Baja | `key_pin/stop` sin CSRF | CF (verificado en 3.1.879; no revisado en 3.1.973) | — | §3 corregido | est 399 |
| PNS-90 (parche 7) | Alta | Caché de `fetch_url` | CF (verificado en 3.1.879; no revisado en 3.1.973) | p7 retirado (lo corrigió el fabricante) | §3 corregido | est 400 |
| PNS-91 (parche 8) | Media | `ensure_domain_whitelisted` | CF (verificado en 3.1.879; no revisado en 3.1.973) | p8 retirado (lo corrigió el fabricante) | §3 corregido | est 401 |
| PNS-92 | Media | `set_mcp_api_key` | CF (verificado en 3.1.879; no revisado en 3.1.973) | — | §3 corregido | est 402 |
| PNS-93 (parche 5) | Media | `thought_signature` de Gemini 3 | CF (verificado en 3.1.879; no revisado en 3.1.973) | p5 retirado (lo corrigió el fabricante) | §3 corregido | est 403 |
| PNS-94 (parche 6) | Alta | Bloqueo de `chatboo_session` | CORREGIDO (sigue en 3.1.973) (por código) | p6 retirado (lo corrigió el fabricante) | §3 corregido | est 404; comp 333 |
| PNS-95 | Baja | Formato de importes | CF (verificado en 3.1.879; no revisado en 3.1.973) | — | §3 corregido | est 405 |
| PNS-96 (hoja 30; «el chat afirma cambios que no hizo») | Baja | Calidad con modelos `lite` | SIN CAMBIO | p34 (opción A: aviso fijo en línea llana) | §3 abierto · corregido en la rama de Seges | est 406; comp 382 |
| obs. 1 | — | `system_prompt` duplicado | CF (verificado en 3.1.879; no revisado en 3.1.973) | — | §3 corregido | est 423 |
| obs. 2 | — | Fragmentos de la clave en el log | CF (verificado en 3.1.879; no revisado en 3.1.973) | — | §3 corregido | est 424 |
| obs. 3 | — | `api_key` con `copy=False` | CF (verificado en 3.1.879; no revisado en 3.1.973) | — | §3 corregido | est 425 |
| obs. 4 | — | Parches globales | CF (verificado en 3.1.879; no revisado en 3.1.973) | — | §3 corregido | est 426 |
| obs. 5 | — | Retención de Chatboo | CF (verificado en 3.1.879; no revisado en 3.1.973) | — | §3 corregido | est 427 |
| obs. 6 | — | Descargas del chat fuera de la purga de 24 h | SIN CAMBIO | — | §3 abierto | est 428; comp 433 |
| obs. 7 | — | `_fx_payload` devuelve `str(exc)` | SIN CAMBIO | — | §3 abierto | est 429; comp 434 |
| obs. 8 | — | `_choose` privado | CF (verificado en 3.1.879; no revisado en 3.1.973) | — | §3 corregido | est 430 |
| obs. 9 | — | Agente sin cadena | CF (verificado en 3.1.879; no revisado en 3.1.973) | — | §3 corregido | est 431 |
| obs. 10 | — | Tipos de cambio al abrir Chatboo | CF (verificado en 3.1.879; no revisado en 3.1.973) | — | §3 corregido | est 432 |
| obs. 11 | — | Skill retirada borrada en cada `-u` | CF (verificado en 3.1.879; no revisado en 3.1.973) | — | §3 corregido | est 433 |
| obs. 12 | — | `detect_dangerous_operations` sin uso | CF (verificado en 3.1.879; no revisado en 3.1.973) | — | §3 corregido | est 434 |
| obs. 13 | — | Tests que cambian la clave del administrador | SIN CAMBIO localizado | — | §3 abierto | est 435; comp 435 |
| Petición de §5 | — | El prompt que recibe el modelo, en `ai.log` | SIN CAMBIO localizado | — | §3 abierto | est 436 |
| Compatibilidad sin número (§7.1 a §7.4 y §8.5) | — | `external_dependencies`, migraciones `3.1.x`, APIs de 3.8+, cron sin `numbercall` | NO APLICA | — | §3 corregido | est 437; comp 408 |

## 3. No comunicados, del inventario sobre 3.1.879

| Id | Grav. | Título corto | 3.1.973 (fabricante) | Rama de Seges | Informe | Fuente |
|---|---|---|---|---|---|---|
| PNS-97 (hoja 3) | Media | `ai.trusted.action` editable | PARCIAL | p32 | §4 | est 407; comp 371 |
| PNS-98 (hoja 4) | Baja | Adjuntos huérfanos | SIN CAMBIO | — | §4 | est 408; comp 389 |
| PNS-99 | Media | `remove_group` sin efecto y diario `applied` | SIN CAMBIO (REQUIERE PRUEBA) | — | §4 | est 409; comp 372 |
| PNS-100 | Alta | Efectos fuera de la BD desde la caja A | PARCIAL | p22 (22 nombres más en la lista del sandbox) | §4 | est 410; comp 284 |
| PNS-101 | Crítica | Entornos reales del hilo desde la caja A | CORREGIDO (P-6, §9) | p23 retirado (lo cubre 3.1.973) | — lo corrige 3.1.973 (mención en §5) | est 411; comp 272 |
| PNS-102 | Crítica | `user`/`company` con `su` | SIN CAMBIO | p24 | §4 | est 412; comp 273 |
| PNS-103 | Baja | AI Administrator sin Ajustes: `AccessError` en la revisión y el resultado de las importaciones | SIN CAMBIO (mismo código) | p36 | §4 | est 413 |
| PNS-104 | Baja | Cerrar la caja A descarta las escrituras pendientes del llamador (`rollback` → `clear_env` → `env.clear()`) | SIN CAMBIO (mismo código) | p37 (`flush` antes de la caja A) | §4 | est 414 |
| PNS-105 | Alta (propuesta) | Los cursores propios con `commit` (p. ej. `ai.log._create_log_entry`) confirman y descartan las escrituras pendientes de quien los llama (`Cursor.commit` → `flush_env`) | SIN CAMBIO (mismo patrón) | p38 (cursores propios con su conjunto de entornos) | §4 | est 415 |
| §8.1 (10 rutas) | — | Rutas nuevas del lienzo, la mesa del PIN y `fulfill_export` | CF (verificado en 3.1.879; no revisado en 3.1.973) | — | — cerrado en 3.1.879, sin defecto que comunicar | est 443 |
| M1 | Media | `paint_canvas` escribe el lienzo ajeno | CORREGIDO (más estrecho) | p25 (solo la comprobación de dueño) | — lo corrige 3.1.973 (mención en §5) | est 444; comp 373 |
| M2 | Media | `page_html` lee imágenes en `sudo` | SIN CAMBIO | p26 | §5 (decisión 1) | est 445; comp 374 |
| M3 | — | `page_url`, `page_edit` | PARCIAL | p26 (desde el sandbox) | §5 con M2 (decisión 1) | est 446; comp 400 |
| M4 | — | `canvas_public_url` y otros | CF (verificado en 3.1.879; no revisado en 3.1.973) | — | — cerrado en 3.1.879, sin defecto que comunicar | est 447 |
| M5 (hoja 14) | Baja | `cron_maintenance` público | SIN CAMBIO | — | §8 | est 448; comp 392 |
| M6 | — | `request_cancel`, `mark_seen` | CF (verificado en 3.1.879; no revisado en 3.1.973) | — | — cerrado en 3.1.879, sin defecto que comunicar | est 449 |
| M7 | — | `model_can_archive` | CF (verificado en 3.1.879; no revisado en 3.1.973) | — | — cerrado en 3.1.879, sin defecto que comunicar | est 450 |
| M8 | — | Vaciar la papelera | CF (verificado en 3.1.879; no revisado en 3.1.973) | — | — cerrado en 3.1.879, sin defecto que comunicar | est 451 |
| M9 | — | `action_revert` y otros | CF (verificado en 3.1.879; no revisado en 3.1.973) | — | — cerrado en 3.1.879, sin defecto que comunicar | est 452 |
| M10 | Crítica | Plan con la identidad de otro (`create` + `cleanup_stuck_state`) | CORREGIDO | p13 retirado (lo cubre 3.1.973); la parte del p12 sigue | — lo corrige 3.1.973 (mención en §5) | est 453; comp 271 |
| M11 (hoja 1) | Media | `log_*` a nombre de otro | CORREGIDO | p30 retirado: lo cubre 3.1.973 | — lo corrige 3.1.973 (mención en §5) | est 454; comp 375 |
| M12 (hoja 2) | Baja | `chat_completion` directo | CORREGIDO | p31 retirado: lo cubre 3.1.973 | — lo corrige 3.1.973 (mención en §5) | est 455; comp 383 |
| M13 | Alta | Borrado de contextos de fábrica | CORREGIDO | p14 retirado: lo cubre 3.1.973 | — lo corrige 3.1.973 (mención en §5) | est 456; comp 285 |
| M14 | — | Gemelo de skills | CF (verificado en 3.1.879; no revisado en 3.1.973) | — | — cerrado en 3.1.879, sin defecto que comunicar | est 457 |
| M15 | — | Topes de gasto | CF (verificado en 3.1.879; no revisado en 3.1.973) | — | — cerrado en 3.1.879, sin defecto que comunicar | est 458 |
| M16 (hoja 15; obs. 10) | Baja | `get_usd_fx` sin control de host | SIN CAMBIO | p22 (solo en la caja A) | §8 | est 459; comp 385 |
| D1 (hoja 13) | Baja | Páginas compartidas | PARCIAL | p28 (sin la parte de `owner_id`, que cubre el fabricante) | §5 (decisión 1) | est 460; comp 384 |
| D2 | — | `chatboo.canvas.job` | CF (verificado en 3.1.879; no revisado en 3.1.973) | — | — cerrado en 3.1.879, sin defecto que comunicar | est 461 |
| D3 | — | `chatboo.job.mixin` | CF (verificado en 3.1.879; no revisado en 3.1.973) | — | — cerrado en 3.1.879, sin defecto que comunicar | est 462 |
| D5 | — | Campos nuevos del lienzo | SIN CAMBIO: abierta en las dos (comp 3.7) | p27 limita el alcance; no cierra la vía | §5 con F1 (decisión 1) | est 463 |
| D6 | — | Asistente de consumo | CF (verificado en 3.1.879; no revisado en 3.1.973) | — | — cerrado en 3.1.879, sin defecto que comunicar | est 464 |
| D7 | — | Mixin de leyenda | CF (verificado en 3.1.879; no revisado en 3.1.973) | — | — cerrado en 3.1.879, sin defecto que comunicar | est 465 |
| D8 | — | Herencias nuevas | CF (verificado en 3.1.879; no revisado en 3.1.973) | — | — cerrado en 3.1.879, sin defecto que comunicar | est 466 |
| F1 (alias: P-8e a) | Media | El lienzo saca datos | PARCIAL | p27 (a, a′, b y c) y p29 | §5 (decisión 1) | est 467; comp 376 |
| F2 | — | Protocolos `openrouter`/`systemone` | CF (verificado en 3.1.879; no revisado en 3.1.973) | — | — cerrado en 3.1.879, sin defecto que comunicar | est 468 |
| F3 | — | Orígenes MCP permitidos | CF (verificado en 3.1.879; no revisado en 3.1.973) | — | — cerrado en 3.1.879, sin defecto que comunicar | est 469 |
| F4 (hoja 12; alias: «HTML crudo en PDF/DOCX») | Baja | PDF con el HTML de la tabla como texto | SIN CAMBIO | — | §8 | est 470; comp 390 |
| C1 | — | Ruta `save_raw_for_template` eliminada | CF (verificado en 3.1.879; no revisado en 3.1.973) | — | — cerrado en 3.1.879, sin defecto que comunicar | est 471 |
| C2 | — | Guarda de jobs en el mixin | CF (verificado en 3.1.879; no revisado en 3.1.973) | — | — cerrado en 3.1.879, sin defecto que comunicar | est 472 |
| U9 | — (datos) | El `-u` borra `ai_log.agent_id` (nota de versión falsa) | NO APLICA a un `-u` desde 3.1.879 | — | §6 | est 478; comp 403 |
| U6 | — (datos) | Cinco parámetros renombrados, no anunciado | SIN CAMBIO | — | — aceptado (nota interna) | est 479; comp 417 |
| U11 | — (datos) | Agente «Decision» huérfano, no anunciado | SIN CAMBIO | — | §6 | est 480; comp 419 |
| U15 | — (datos) | Resiembra y tres skills nuevas, no anunciadas | SIN CAMBIO (mismo mecanismo) | — | — aceptado (nota interna) | est 481; comp 418 |
| U16 | — (datos) | Historial de Chatboo reescrito, no anunciado | SIN CAMBIO | — | — aceptado (nota interna) | est 482 |
| Numeración de `pns_base` 1.2.47 | — | Número que no casa con el contenido | CORREGIDO (dato: 1.2.69) | — | §6 | est 483 |
| `unit_tests/` no entregados | — | Tests citados que no vienen en el paquete | SIN CAMBIO (no vienen) | — | — aceptado (nota interna) | est 484; comp 420 |
| Hoja 16 | — | Tokens de portal | NO APLICA (core) | — | — no aplica | est 490 |
| Hoja 17 | Baja | Reenvío de `params` y `data` en redirecciones | SIN CAMBIO | — | §8 | est 491; comp 393 |
| Hoja 18 | — | Caché del agente confirmada durante «Review» | SIN CAMBIO | — | §8 | est 492; comp 427 |
| Hoja 19 | — | `onchange_email` y Gravatar | NO APLICA (core) | — | — no aplica | est 493 |
| Hoja 20 | — | `bus.presence.update` en cursor propio | NO APLICA (core) | — | — no aplica | est 494 |
| Hoja 21 | Baja (muy baja) | Orden por un campo secreto en la caja A | CORREGIDO con el criterio del fabricante | — | — lo corrige 3.1.973 (mención en §5) | est 495; comp 388 |
| Hoja 22 (`customer_360._iso`) | — | `ensure_module_result_call` añade `result = …` | SIN CAMBIO | — | §8 | est 496; comp 421 |
| Hoja 23 | — | «Test Connection» escribe en el proveedor | SIN CAMBIO | — | — aceptado (nota interna) | est 497; comp 428 |
| Hoja 24 | — | Etiqueta MCP del script de E2′ | NO APLICA (script de Seges) | — | — no aplica | est 498 |
| Hoja 25 | — | La autenticación MCP no consulta el estado de la clave | SIN CAMBIO | — | §8 | est 499; comp 429 |
| Hoja 26 | — | Casilla AI Conversational de Usuarios MCP | SIN CAMBIO localizado; no reproducida en 3.1.973 (20/11) | — | — fuera (D70) | est 500; comp 422 |
| Hoja 27 | — | Defecto de `keys` en la muestra para Design | SIN CAMBIO | — | §8 | est 501; comp 423 |
| Hoja 28 | — | Nombre de la descarga del lienzo | SIN CAMBIO | — | §8 | est 502; comp 430 |
| Hoja 29 | — | Casilla «Design» en `lite` | NO APLICA tal cual | — | — no aplica | est 503; comp 404 |
| Hoja 31 | — | Varias llamadas a Design por edición | SIN CAMBIO | — | §8 | est 504; comp 431 |
| Hoja 32 | — | El orquestador reinterpreta peticiones | NO APLICA (sin código) | — | §8 (comportamiento del modelo) | est 505 |
| Hoja 33 | — | «[object Object]» en la tarjeta de `lite` | NO APLICA | — | — no aplica | est 506; comp 405 |
| Hoja 34 | — | `pruebas_e3p_lab.py` no resiste un 503 | NO APLICA (script de Seges) | — | — no aplica | est 507 |
| Hoja 35 | — | `relaxaicode` aunque se pida no consultar | NO APLICA (sin código) | — | §8 (comportamiento del modelo) | est 508 |
| Hoja 36 | — | `ai_log` sin el detalle del error del failover | SIN CAMBIO localizado | — | §8 | est 509 |
| Hoja 37 | — | El validador rechaza `dir()` | SIN CAMBIO localizado | — | — aceptado (nota interna) | est 510 |
| Hoja 38 | — | `iap.account.account_token` legible | CORREGIDO con el criterio del fabricante | — (lo cubre el criterio del fabricante) | — lo corrige 3.1.973 (mención en §5) | est 511; comp 401 |
| Botón Canvas sin aviso (y sin tooltip en el staging) | — | El error del botón Canvas no se ve en pantalla | SIN CAMBIO | — | §8 | est 512 |
| Nota «incomplete response» invisible | — | La nota del fabricante no se ve en la burbuja | SIN CAMBIO | — | §8 | est 513 |
| Copiar y XLSX con tabla sin prosa | — | Observación de exportación | SIN CAMBIO | — | §8 | est 514 |
| Carga de la sesión sin reintento (alias: resto 4 de PNS-94) | — | Fallo de serialización al cargar la sesión tras un job | SIN CAMBIO localizado (REQUIERE PRUEBA) | — | §8 | est 515; comp 425 |
| Exportación del staging | — | Prosa y aviso antes de la tabla; solo `Name`; «Word» como `.doc` HTML | SIN CAMBIO | — | §8 | est 516 |
| Escritura en la operación 27 | — | Escritura sin causa ni efecto | NO APLICA (entorno) | — | — no aplica | est 517 |
| Cancelación de todas las verificaciones pendientes | — | Un rechazo de escritura cancela todas las del usuario | SIN CAMBIO localizado | — | §8 | est 518; comp 437 |
| `log_no_page` escribe en `ai_log` desde la caja A | — | Filas en cursor propio que el rollback no deshace | SIN CAMBIO | — | §8 | est 519 |
| Valores hostiles de portal en la página | — | La regla de `account` no protege la ciudad ni la calle | SIN CAMBIO (sin escape en `<script>`) | p27, p29 | §5 con F1 (decisión 1) | est 520; comp 416 |
| Contraseña de `admin` en `pns_demo` | — | 5 caracteres en un staging accesible | NO APLICA (entorno) | — | — no aplica | est 521 |

## 4. Altas posteriores al inventario sobre 3.1.879

Hallazgos y observaciones de la comparación con 3.1.973 y de la rama 3973 (fases 2 a 4, pruebas con toda la rama,
staging del 18/11 y ensayo de LIYBEN) que no tienen fila en el inventario sobre 3.1.879. Los números de PNS-108 en
adelante y las gravedades «(propuesta)» quedan decididos (§5, 20/11/2026).

| Id | Grav. | Título corto | 3.1.973 (fabricante) | Rama de Seges | Informe | Fuente |
|---|---|---|---|---|---|---|
| PNS-106 | Baja (propuesta) | URL de imagen que `_WEB_IMAGE_RE` no reconoce: imagen rota en el lienzo aunque el usuario tenga acceso | SIN CAMBIO (es de 3.1.973) | — (decisión de Sergio, 13/11/2026) | §5 | seg «Observaciones sin ficha»; reg «Para el informe al fabricante (fase 4)» |
| PNS-107 | Baja | `iap.account.get` crea o borra cuentas IAP en cursor propio desde la caja A; restos: campo calculado de `partner_autocomplete` e `iap_enrich` | SIN CAMBIO | p39 | §4 | seg PNS-107; reg «Parche 39» |
| PNS-108 (NUEVO-1) | Alta (propuesta) | La protección de columnas secretas no cubre valores ya en la caché del hilo; vías V1 a V4 (`auth_token`, `mcp_api_key_hash`, `totp_secret`, `signup_token`) confirmadas por test | ABIERTO (es de 3.1.973) | p18 rehecho (O1, B y B2) | §5, con PNS-19 | comp §3.4, §9 (P-1); prop fase 3, «Confirmación de V1 a V4»; reg «Parche 18 en 3.1.973» |
| `Reference` y modelos de credenciales | — (observación) | Un campo `Reference` salta la puerta de `RELAXAICODE_CREDENTIAL_MODELS`, que solo mira `env[...]` | ABIERTO | p18 ampliado por P-22 (solo las credenciales) | §5, con PNS-108 | reg «Para el informe al fabricante (fase 3b)»; est §6 «Alta del 12/11/2026» |
| PNS-109 (NUEVO-2) | Baja | Tras el `-u`, los dos crons de purga siguen llamando a `gc_expired`, que ya no existe (D39 del plan de la 3973) | ABIERTO | p35 (`post-migrate`) | §6 | comp §3.4; seg nota del 17/11/2026; reg «Parche 35» |
| NUEVO-3 | Alta | Un AI Administrator sin Ajustes fija la clave MCP de un administrador de Ajustes | CORREGIDO en 3.1.972 | — (no hace falta) | — lo corrige 3.1.973 (mención en §5) | comp §3.4 |
| NUEVO-4 | Alta | El asistente de exportación de `pns_base` borra en `sudo` cualquier adjunto | CORREGIDO en 1.2.69 | — (no hace falta) | — lo corrige 3.1.973 (mención en §5) | comp §3.4 |
| PNS-110 (NUEVO-5) | Baja | Sin proveedor con el rol Diseño, diseña la cadena de Conversación (alternativa activa por defecto) y aparece el botón Canvas; archivar el rol no basta | ABIERTO (es de 3.1.973) | — | §5 (decisión 3) | comp §7.2, §6.6, §9 (P-10) |
| PNS-111 | Baja (propuesta) | Canvas sin imágenes: el botón Canvas manda la tabla sin columnas de imagen y Design no recibe fotos | ABIERTO (igual en 3.1.973) | — | §5 | `lab_fase2_3973.md`, 3.5; reg «Para el informe al fabricante (fase 4)» |
| Librerías externas en el lienzo | — (observación) | El prompt no prohíbe librerías de CDN y la CSP del marco las bloquea: gráficos en la descarga y no en el lienzo | ABIERTO | — | §8 | reg «Para el informe al fabricante (fase 4)» |
| Camino real a `too_soon` | — (observación) | Una tarjeta pintada sin token recibe uno al restaurar el panel sin volver a deshabilitar el botón: un clic en los 5 s siguientes da `too_soon` | ABIERTO | — (p16 no lo toca) | §8 (decisión 3) | plan 3973, «Caminos reales hacia `too_soon`» |
| Idioma de `page_tab` | — (observación) | Con un usuario `en_US`, las palabras de `page_tab` son solo las genéricas en inglés: «Hazme una página…» no lo activa | ABIERTO | — | §8 (decisión 3) | `lab_fase2_3973.md`, 3.5 |
| Skills de 3.1.879 con `required_groups` | — (observación) | `sys_info`, `users_all` y `users_logged` piden una capacidad que el motor 3.1.879 no publica: no se importan (3 errores en INFO en cada instalación) | NO APLICA en 3.1.973 (las retira) | — | §6 (decisión 3) | plan 3973, pruebas con toda la rama, c) |
| `fields_view_get` sin `@api.model` | — (observación) | En `pns.operation.report.wizard`; solo se ve por RPC | ABIERTO | — (no se corrige) | §8 | plan 3973, fase 2c; reg «Prueba en el laboratorio del parche 36» |
| PNS-112 | Baja (propuesta) | Plan que el validador acepta y el core no puede ejecutar (`write` de `res.partner` con un `mail.message` en `message_ids`); el resultado guarda solo `str(e)` | ABIERTO | — | §5 (decisión 4) | seg «Observaciones sin ficha»; `staging_3973.md`, G, operación 35 |
| PNS-113 | Media (propuesta) | La recarga de traducciones de los `pns_*` con sobrescritura reescribe términos `code` de otros módulos (49 filas en la copia de LIYBEN, 13 con otro texto) | ABIERTO | — (en LIYBEN, B′ en el despliegue) | §6 (decisión 4) | seg «Observaciones sin ficha»; `liyben_3973.md`, Anexo A, Y6 |
| PNS-114 | Baja (propuesta) | La conversión `fit_*` → roles del `-u` no valida contra el protocolo: un proveedor `openai` queda con Decisión y su `write` de roles da `ValidationError` | ABIERTO | — (en LIYBEN, D67) | §6 (decisión 4) | seg «Observaciones sin ficha»; `liyben_3973.md`, Y6 v1 |
| Anexo de PNS-26 | Baja | 40001 en `/verification/execute`; en el staging del 18/11 no se reprodujo | SIN CAMBIO | — (tests, dos con skip) | §3, con PNS-26 | traspaso de la fase 4; plan 3973, staging |

Antes de numerar PNS-112 a PNS-114 se buscaron en `docs/` sus síntomas (`_notify_get_reply_to`, `KeyError: 14`,
`md5(src)`, `promote_fit_columns`, `_check_roles_match_protocol`): solo aparecen en las observaciones citadas, en el
staging, en el ensayo de LIYBEN y en análisis sin hallazgo. PNS-43 (descarte de traducciones duplicadas) es otro
defecto.

## 5. Decisiones de Sergio (20/11/2026, 21:38: las recomendaciones de Claude)

Decididas las cinco tal como se recomendaban. Los números de PNS-106 y PNS-108 a PNS-114 y sus gravedades quedan
fijados; en el §4, «(propuesta)» se lee como decidido.

1. **Corregidos por Seges, nunca comunicados y abiertos en 3.1.973** (M2 con M3, D1, F1 con «valores hostiles de
   portal» y D5). **Recomendación:** al §5, cada uno con una ficha breve (qué pasa, impacto y corrección sugerida, sin
   código). Siguen abiertos en el código del fabricante.
2. **Lo que 3.1.973 corrige sin habérselo comunicado** (PNS-101, M1, M10 a M13, hojas 21 y 38, NUEVO-3 y NUEVO-4).
   **Recomendación:** una tabla de una línea por fila en el §5 («lo comprobamos y está corregido»), sin fichas. Cierra
   el hilo con el fabricante sin alargar el informe.
3. **Sin decisión previa registrada:** PNS-110 (NUEVO-5), el camino a `too_soon`, el idioma de `page_tab` y las skills
   de 3.1.879 con `required_groups`. **Recomendación:** incluirlas: PNS-110 al §5 y las otras tres como observaciones
   (§8 y §6).
4. **Numeración.** Corrige lo que se aprobó a las 21:24: el seguimiento ya proponía **PNS-106** para la URL de imagen
   que no se reconoce (no para Canvas sin imágenes). **Recomendación:**
   - PNS-106: URL de imagen;
   - PNS-108: NUEVO-1; PNS-109: NUEVO-2; PNS-110: NUEVO-5; PNS-111: Canvas sin imágenes;
   - PNS-112 a PNS-114: la operación 35, las traducciones `code` y la conversión `fit_*` → roles, que eran
     «candidatas sin numerar» a la espera de la búsqueda en `docs/` (hecha, arriba).
   El marcador «PNS-106» que se usó en una batería del 13/11 (`propuesta_fase3_3973.md`) fue provisional y se cambió
   por «anexo de PNS-26»: no choca.
5. **Gravedades propuestas:** PNS-106, PNS-109, PNS-110, PNS-111, PNS-112 y PNS-114, Baja; PNS-108, Alta (como
   PNS-19); PNS-113, Media (cambia textos de toda la instalación, no solo de los `pns_*`).

## 6. Cambios respecto al inventario sobre 3.1.879

- Base: 3.1.973 en lugar de 3.1.879. Parches retirados por cubrirlos el fabricante: 10, 13, 14, 23, 30 y 31. Parches
  nuevos de la rama 3973: 35 a 39.
- Altas: PNS-103 a PNS-105 (ya en el inventario sobre 3.1.879 como notas fechadas) y las 18 filas del §4.
- La ficha 26 sale (D70).

## 7. Erratas detectadas al redactar el informe (21/11/2026)

- **PNS-80 (§2):** figura como «CF782 (no revisado en 3.1.973)», pero la comparación (§3.2) lo revisó en 3.1.973: NO
  APLICA (`read_progress` no existe). Por eso el informe dice 53 corregidos sin revisar en 3.1.973, no 54.
- **PNS-100 (§3):** la comparación (§3.1, §4 y §7.4) y `diferencias_3-1-973_seges.md` (§2) dicen que faltan 21 de los
  28 nombres (y §3.1, «7 de 28»). 3.1.973 cubre 6 de los 28 (el séptimo nombre que añade, `build_email`, no está en la
  lista de Seges): faltan 22, como dicen este inventario y el informe.
