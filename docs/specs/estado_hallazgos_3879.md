# Estado de los hallazgos de la evaluación de los módulos de IA (base 3.1.879)

- **Fecha:** 09/11/2026.
- **Revisión:** segunda pasada (09/11/2026). Completa las lecturas que faltaban en la primera y sustituye
  sus dos supuestos por estados explícitos (CF782 y PSD). Cambios al final, en «Cambios respecto a la
  primera pasada».
- **Decisiones registradas (10/11/2026):** las de Sergio del 09/11/2026
  ([hoja de decisiones](../pendiente/decisiones_pendientes_hallazgos_3879.md)). Cambian el estado en §3 de
  las filas de §2 y §2 bis, los recuentos de §1 y «A confirmar» (bloques «Decidido»). §4, §5 y §6 siguen
  como en la segunda pasada.
- **Alta de PNS-103 (12/11/2026):** hallazgo nuevo de la rama `14.0-pns-ai-3973` (fase 2c, parche 36), con
  el mismo código en 3.1.879. Se añade su fila al final de §3.1 y a §6 (C). El alcance (PNS-01 a PNS-102) y
  los recuentos de §1 no se reescriben: la nota fechada de §1 da los nuevos.
- **Alta de PNS-104 (12/11/2026):** hallazgo nuevo de la rama `14.0-pns-ai-3973` (confirmación de la fase 3b), con el
  mismo código en 3.1.879. Se añade su fila al final de §3.1 y a §6 («Alta del 12/11/2026»), con el mismo criterio que
  PNS-103.
- **Alta de PNS-105 (12/11/2026):** hallazgo nuevo de la rama `14.0-pns-ai-3973` (por lectura de código, fase 3b), con
  el mismo patrón en 3.1.879. Fila al final de §3.1 y entrada en §6, con el mismo criterio. PNS-104 pasa a Baja
  (propuesta) el mismo día (nota de §1).
- **Rama y HEAD:** `14.0-pns-ai-3879`, `be934bc` (copia de trabajo limpia).
- **Código comprobado:** `pns_base`, `pns_ai_mcp` y `pns_ai_chatboo` de `8d218ea` (validado en el staging
  `pns_demo` el 09/11/2026; ningún commit posterior toca los módulos).
- **Objeto:** base para el informe al fabricante. Comprueba que cada hallazgo de la evaluación está
  corregido o revisado, con la referencia que lo prueba. No redacta el informe ni cambia ningún otro
  documento.
- **Método:** solo lectura de los documentos del repo y Grep sobre el código. Sin ejecutar nada.
- **Fuentes** (rutas relativas a `docs/`; abreviatura entre paréntesis):
  - `specs/comparacion_pns_ai_3-1-879.md` (**comp**), §1 a §10;
  - `pendiente/e4_hoja_3879.md` (**hoja**), entera: fichas 1 a 38, las dos rondas de decisiones,
    «Comprobaciones en ejecución» y «Candidatas al informe al fabricante»;
  - `pendiente/e4_propuesta_3879.md` (**prop E4′**), tercera y cuarta ronda;
  - `pendiente/plan_correccion_pns_ai_3879.md` (**plan**), §2 (tabla de E4′ incluida), §3, §4 y §5. En
    este documento, **«plan §3.2» es el punto 2 de §3** («Informe al fabricante»);
  - `pendiente/parches_pns_ai.md` (**reg**), índices, entradas 10 a 34, «Para el informe al fabricante»;
  - `pendiente/pns_ai_decisiones.md` (**dec**), N12, decisiones del 23/10/2026, D10, D12, D28 y D29;
  - `pendiente/seguimiento_informe_pns_ai.md` (**seg**): tabla resumen y recuento enteros, fichas PNS-50,
    PNS-51 y PNS-95 a PNS-102 enteras, «Observaciones sin ficha», «Candidatos evaluados y descartados» y
    «Compatibilidad con Odoo 14»;
  - lo comunicado al fabricante (**inf.**): `pendiente/informe_fabricante_pns_ai.md` (08/10/2026; §1.1,
    §6, §7 y §8.4 a §8.6), `pendiente/informe_seguimiento_fabricante_pns_ai.md` (15/10/2026; §1, §2.1,
    §5, §7 y §8) y `pendiente/informe_fabricante_pns_ai_2.md` (16/10/2026, con la cabecera «Borrador»;
    §1, §2, §3.1, §4.2, §5 y §6);
  - las decisiones de Sergio de las propuestas, leídas enteras: `pendiente/e1_propuesta_3879.md`
    (**prop E1′**, 23/10/2026), `pendiente/e2_propuesta_3879.md` (**prop E2′**, tres rondas del 27/10,
    «Propuesta final», revisión del parche 18 y segundo rechazo del 28/10) y
    `pendiente/e3_propuesta_3879.md` (**prop E3′**, «Propuesta final (29/10/2026)», comprobaciones previas
    y revisión B1);
  - apartados G de `pendiente/staging_e2_3879.md`, `staging_e3_3879.md` y `staging_e4_3879.md` (**stE2**,
    **stE3**, **stE4**); `staging_e1_3879.md` no tiene apartado G: su resultado está en
    `pendiente/verificacion_seguridad_pns_ai.md` (**verif**), «Staging — entrega E1′», con
    `pendiente/diagnostico_r6_staging_e1p.md` (**diag R6**), leído entero en esta pasada;
  - laboratorio: `pendiente/lab_e2_3879.md`, `lab_e3_3879.md`, `lab_p29_3879.md`,
    `e3_hallazgo_p8ea_3879.md`; bloques de staging de **verif**;
  - auditoría del fabricante (confidencial): solo los encabezados de ficha, para saber qué fichas da por
    «Resuelto» y cuáles van en «No se hará» (7: PNS-18, 23, 36, 54, 02, 26 y 33). No se copia texto suyo.
- **Alcance del inventario:** PNS-01 a PNS-102; observaciones menores comunicadas (obs.); los problemas de
  compatibilidad sin número del informe del 08/10; §8 de la comparación (rutas, M1 a M16, D1 a D8, F1 a
  F4, C1 y C2); cambios de §9 y §10 (U); fichas 16 a 38 de la hoja; y las observaciones de laboratorio y
  staging de E1′ a E4′ que señalan un defecto. Quedan fuera las «Correcciones del procedimiento» de los
  documentos de staging (son del procedimiento, no del código).
- **Unidad:** una fila por hallazgo. Un mismo hallazgo con varios nombres va en una fila, con los alias en
  la columna de id (p. ej. fichas de la hoja que repiten un PNS o un M). Las 10 rutas nuevas de §8.1 van en
  una sola fila; los problemas de compatibilidad sin número, también.

**Estados:**

- **CS** = CORREGIDO SEGES (parche N; laboratorio y staging, con fecha).
- **CF** = CORREGIDO FABRICANTE: VERIFICADO en la comparación de 3.1.879 (comp §2, §5, §6, §8 o §9).
- **CF782** = CORREGIDO FABRICANTE (3.1.782; no revisado en 3.1.879): seg lo da por CORREGIDO o YA NO
  APLICA en 3.1.782 (o por PARCIAL, en la parte corregida) y comp no lo vuelve a revisar. Comprobado con
  Grep de cada id en comp: de los corregidos en 3.1.782 solo aparece PNS-41 (§5.7, PB-1), que queda en CF.
- **AC** = ACEPTADO: decisión explícita de Sergio, con su referencia («Decidido» de la hoja, dec o las
  propuestas de E1′ a E3′).
- **AI** = AL INFORME: pendiente de comunicar según plan §3.2, reg «Para el informe al fabricante» o la
  lista «Candidatas» de la hoja cuando la ficha tiene decisión explícita.
- **PSD** = PROPUESTA SIN DECISIÓN: ficha de la hoja que solo trae «Propuesta» (aceptar, sin acción o
  informe), sin decisión explícita en la hoja, el plan, dec ni las propuestas. No cuenta como AC ni como
  AI. Lista en §2 bis.
- **SE** = SIN TRATAR / SIN ESTADO CLARO.

Un hallazgo puede tener varios. Rutas de código: las de `8d218ea`, salvo cuando se cita la comparación.

## 1. Resumen

**Filas: 186.** Recuento por estado (una fila cuenta en cada estado que tiene). Actualizado con las
decisiones de Sergio del 09/11/2026 (bloques «Decidido» de §2 y §2 bis); antes: AC 17, AI 29, PSD 19 y
SE 19.

| Estado | Filas |
|---|---|
| CS — corregido por Seges | 33 |
| CF — corregido por el fabricante, verificado en 3.1.879 | 82 |
| CF782 — corregido por el fabricante en 3.1.782, no revisado en 3.1.879 | 33 |
| AC — aceptado | 35 |
| AI — al informe | 56 |
| PSD — propuesta sin decisión | 0 |
| SE — sin tratar o sin estado claro | 1 |

Por gravedad (la de los documentos; si cambia, la última) y estado:

| Gravedad | Filas | CS | CF | CF782 | AC | AI | PSD | SE |
|---|---|---|---|---|---|---|---|---|
| Crítica | 12 | 7 | 3 | 5 | 1 | 5 | 0 | 0 |
| Alta | 34 | 8 | 13 | 15 | 4 | 8 | 0 | 0 |
| Media | 36 | 10 | 24 | 3 | 6 | 9 | 0 | 0 |
| Baja | 33 | 4 | 13 | 10 | 8 | 10 | 0 | 0 |
| Sin gravedad asignada | 71 | 4 | 29 | 0 | 16 | 24 | 0 | 1 (contraseña de `admin` de `pns_demo`: decisión retirada, fuera de alcance) |
| **Total** | **186** | **33** | **82** | **33** | **35** | **56** | **0** | **1** |

- **Marcadores (§4):** los 25 parches vigentes (10 a 34) suman **142** marcadores fuera de tests, igual que
  la comprobación B.4 del staging de E4′ (Grep repetido en esta pasada: 159 líneas en los tres módulos,
  17 de ellas en `tests/`). Cuadran con el registro 23 de 25; el 23 y el 24 no cuadran con el registro
  (desactualizado), sí con el staging de E2′. Parches 1 a 9: **0 marcadores** (retirados).
- **Críticos y Altos:**
  - sin estado: PNS-23 (Alta, «No se hará» del fabricante, sin decisión de Seges sobre el riesgo que queda)
    y el resto funcional de PNS-81 (Alta, sin efecto de seguridad). PNS-101 y PNS-102 tienen SE solo por
    el recuento documental: están corregidos y validados;
  - sin decisión: PNS-18 (aceptado por D10; falta decidir si va al informe) y el resto de PNS-26 (la hoja
    propone el informe, sin «Decidido»);
  - **CF782: 5 Críticas (PNS-03, 04, 05, 06 y 53) y 15 Altas** se dan por corregidas por lo comprobado en
    3.1.782; ningún documento las ha vuelto a mirar en el código de 3.1.879 (§2, «A confirmar»).
- **Tras las decisiones del 09/11/2026:** ningún Crítico ni Alto queda sin estado ni sin decisión. PNS-23
  y el resto de PNS-81 pasan a AC y AI; PNS-18, a AC (D10) y AI; el resto de PNS-26, a AI. PNS-101 y
  PNS-102 pierden el SE documental: sus recuentos (23 y 4) se registran en `parches_pns_ai.md` (hoja de
  decisiones, §4). La revisión de los CF782 queda acotada a las 13 Medias y Bajas («A confirmar»).
  PNS-83 (Alta) suma AC por el resto de la mesa del PIN (decisión 3.2).

> **12/11/2026, alta de PNS-103** (Baja, decidida por Sergio el 12/11; AI). Las tablas de arriba no lo
> incluyen. Con él: **filas 187**; AI 57; Baja 34 (AI 11); el resto de estados y gravedades, sin cambio. En
> 3.1.879 queda sin corregir (el parche 36 es solo de `14.0-pns-ai-3973`), así que aquí no suma CS.

> **12/11/2026, alta de PNS-104** (Alta propuesta, pendiente de la decisión de Sergio; sin estado decidido). Las tablas
> de arriba no lo incluyen. Con PNS-103 y PNS-104: **filas 188**; Alta +1, sin estado hasta que Sergio decida. Sin
> corregir en ninguna rama (propuesta de parche de `flush`, sin número ni implementar).

> **12/11/2026, decisiones de Sergio:** PNS-104 pasa a **Baja (propuesta)**, por ser latente. Alta de **PNS-105** (Alta
> propuesta, sin estado ni parche). Las tablas de arriba no los incluyen. Con PNS-103 a PNS-105: **filas 189**; Alta +1
> (PNS-105) y Baja +1 (PNS-104), los dos sin estado hasta que Sergio decida.

## 2. SIN TRATAR / SIN ESTADO CLARO

Lo que falta para cerrar cada uno:

| # | Id | Grav. | Qué falta | Referencia |
|---|---|---|---|---|
| 1 | PNS-101 (parche 23) | Crítica | Recuento: el registro dice 8 marcadores y el código tiene 23 (los mismos que el staging de E2′, B.4). Actualizar la cabecera de E2′ del registro tras el parche 23 ampliado. El parche está validado (lab 28/10, staging 29/10) | reg:1222-1226; stE2 G, B.4; §4 |
| 2 | PNS-102 (parche 24) | Crítica | Recuento: el registro no da el de este parche; el código tiene 4 (igual que stE2 B.4). Añadirlo al registro | reg:1222-1226, «Parche 24»; stE2 G, B.4 |
| 3 | PNS-99 | Media | `user.remove_group` queda `executed` y el diario `applied` sin quitar el grupo. Registrado como PNS por decisión de Sergio (26/10/2026), posterior a los informes del 15 y 16/10: no comunicado. Sin parche, sin ficha en la hoja, fuera de plan §3.2 y «sin entrega asignada» en seg. Decidir: parche, aceptar o informe | seg PNS-99; diag R6 5.1; verif «Staging — entrega E1′» |
| 4 | PNS-81 (resto) | Alta | Degradación en Python 3.7 de `pns_ai_chatboo/utils/skill_capture_compose.py:319-325` (la captura de skills no reconoce `env['ai.skill']`). Ningún documento de `pendiente/` la trata. Decidir: aceptar o informe | comp §2.4, §3 «Compatibilidad — degradación nueva», §5.6 |
| 5 | PNS-51 | Baja | `platform` permitido en el sandbox. Pedido al fabricante el 15/10 (inf. 15/10 §7.2) y SIN CAMBIOS el 16/10 (inf. 16/10 §3.1); la auditoría no tiene ficha; comp no lo revisa; **sigue en `8d218ea`** (Grep: `pns_ai_mcp/controllers/validators_base.py:95`, `RELAXAICODE_SAFE_MODULES`). D28 sigue con «Decisión: ____». Decidir: aceptar o repetir la petición | seg PNS-51; inf. 15/10 §7.2; dec D28 |
| 6 | PNS-23 | Alta | «No se hará» tras la petición del 15/10 (inf. 15/10 §7.1); la defensa alegada existe (comp §7, VERIFICADO), pero quedan riesgos sin decisión de Seges: paquetes importados sin dueño entran activos para todos; `skill_skip_body_check` salta la ejecución de prueba; tres skills nuevas sin `required_groups` (U15) | comp §7 fila PNS-23; §9.2 U15 |
| 7 | PNS-33 (parte §7) | Media | «No se hará»; comunicado el 15/10 (inf. 15/10 §7.7) y el 16/10 (obs. 2, el prefijo en el log, ya VERIFICADO). Queda que `set_mcp_api_key` acepta una clave elegida o un hash ya calculado (hash sin sal). Sin decisión | comp §7 fila PNS-33 |
| 8 | PNS-28 (salvedad) | Media | En Odoo 14 el `OPTIONS` lo contesta el core: la afirmación del fabricante es falsa en 14 (sin efecto en la seguridad). P-28 no consta hecha y no está en la lista del informe | comp §2.1, §3 «PNS-28», §4.3 P-28 |
| 9 | Petición de §5 (prompt en `ai.log`) | — | PARCIAL: lo que recibe el modelo sigue sin guardarse. Pedido el 16/10 (inf. 16/10 §5, fila PNS-46/PNS-95). Ningún documento de `pendiente/` posterior lo trata | comp §6 y §6.1 |
| 10 | U11 | — | Agente «Decision» huérfano tras el `-u`, no anunciado. P-9d no se hizo («no entraba en el encargo») | comp §9.2 U11, §9.6 |
| 11 | Hoja 26 (casilla AI Conversational) | — | Va al informe (plan §3.2), pero la reproducción en el laboratorio (decisión 5 de la segunda ronda) no consta hecha (Grep en `pendiente/`: ningún registro): sin ella el caso no es reproducible para el fabricante | hoja ficha 26 y decisión 5 |
| 12 | Escritura sin causa en la operación 27 (staging E1′) | — | Escritura de ADM a las 16:47:55, sin efecto y sin causa en el código. Sin decisión | diag R6 §6 (consulta 2) y §7 |
| 13 | Un rechazo de `relaxaicode` sin AI Writer cancela todas las verificaciones pendientes del usuario | — | «Para valorar en E4′»; la hoja no tiene fila para ella | seg «Observaciones sin ficha» |
| 14 | `log_no_page` escribe en `ai_log` en cursor propio desde la caja A | — | Filas que el rollback no deshace (lab E2′, filas 318 y 319; hoja, filas 758 a 761). Solo se decidió conservar las filas, no si es un defecto (escritura fuera de la caja A) | lab_e2 «Resultado (28/10/2026)»; hoja «Comprobaciones en ejecución», nota |
| 15 | Contraseña de `admin` de `pns_demo` (5 caracteres) | — | Entorno, no código: «decide Sergio» (antes o en la limpieza final) | stE4 G, «Observaciones»; plan §4 |
| 16 | Obs. 6 (descargas del chat fuera de la purga de 24 h) | — | Comunicada el 16/10: los adjuntos de `session_download` no llevan la marca de exportación (relacionada con PNS-21). La auditoría no tiene ficha y comp no la revisa. Decidir: repetirla o descartarla | inf. 16/10 §6, obs. 6; seg PNS-21 |
| 17 | Obs. 7 (errores con detalle técnico) | — | Comunicada el 16/10: `_fx_payload` devuelve `str(exc)`. Sin ficha ni revisión en comp | inf. 16/10 §6, obs. 7; seg PNS-71 |
| 18 | Obs. 13 (tests que cambian la clave del administrador) | — | Comunicada el 16/10 (resto menor de PNS-34). Sin ficha ni revisión en comp | inf. 16/10 §6, obs. 13; seg PNS-34 |
| 19 | Compatibilidad sin número (inf. 08/10 §7.1 a §7.4 y §8.5) | — | Ningún documento les da estado. Por Grep en `8d218ea`: §7.1 ya no aplica (`external_dependencies` sin `httpx` ni `pydantic`, `pns_ai_mcp/__manifest__.py:30-34`); §7.4 corregido (`numbercall` -1 en `data/api_result_cache_cron.xml:13`). §7.2 y §8.5 siguen (comp §9.1: no corre ningún script de `migrations/`; el fabricante lo asume y migra en `init()`). §7.3, en PNS-81 y en seg «Compatibilidad con Odoo 14». Decidir si se dan por cerrados o se citan | inf. 08/10 §7 y §8.5; comp §9.1 |

**Decidido (Sergio, 09/11/2026)** ([hoja de decisiones](../pendiente/decisiones_pendientes_hallazgos_3879.md),
§2 y §4; `OK` = se acepta la propuesta de la fila). La tabla de arriba es la de antes de decidir; el estado
nuevo de cada fila está en §3.

| # §2 | Fila de la hoja | Id | Estado nuevo | Lo decidido |
|---|---|---|---|---|
| 1 | §4 | PNS-101 | CS; AI | Recuento documental: 23 marcadores, que se registran en `parches_pns_ai.md` |
| 2 | §4 | PNS-102 | CS; AI | Recuento documental: 4 marcadores, que se registran en `parches_pns_ai.md` |
| 3 | 2.1 | PNS-99 | AC y AI | Aceptar e informe: no lo agrava ningún parche y solo afecta a planes del AI Administrator |
| 4 | 2.2 | PNS-81 (resto) | AC y AI | Aceptar en 3.1.879; al informe como «corregido en 3.1.973». Con el camino C, candidato a parche (unas 8 líneas) |
| 5 | 2.3 | PNS-51 | AC y AI | D28: aceptar y repetir la petición en el informe |
| 6 | 2.4 | PNS-23 | AC y AI | Aceptar, con una regla en la guía de configuración: solo el AI Administrator importa paquetes de skills, y los revisa antes; informe |
| 7 | 2.5 | PNS-33 (parte §7) | AC y AI | Aceptar (las claves se generan con el asistente, N4); informe |
| 8 | 2.6 | PNS-28 (salvedad) | AI | Observación en el informe; P-28 no se hace |
| 9 | 2.7 | Petición de §5 | AI | Repetir la petición en el informe |
| 10 | 2.8 | U11 | AI | Informe sin prueba (P-9d no se hace) |
| 11 | 2.9 | Hoja 26 | AI | Reproducción en el laboratorio (shell y `rollback`, decisión 5) con un usuario que **no** sea AI Administrator, antes del informe. Pendiente de hacer |
| 12 | 2.10 | Escritura en la operación 27 | AC | Cerrar sin acción: sin efecto y sin causa en el código |
| 13 | 2.11 | Cancelación de las verificaciones pendientes | AI | Informe (defecto del fabricante; no cumple el criterio del bloque F) |
| 14 | 2.12 | `log_no_page` en `ai_log` | AI | Es un defecto (escritura fuera de la caja A de solo lectura); al informe junto a PNS-98, sin parche |
| 15 | 2.13 | Contraseña de `admin` de `pns_demo` | SE (sin cambio) | Retirada por estar fuera del alcance; no se registra |
| 16 | 2.14 | Obs. 6 | AI | Repetir en el informe |
| 17 | 2.15 | Obs. 7 | AI | Repetir en el informe |
| 18 | 2.16 | Obs. 13 | AI | Repetir solo si sigue en la versión que se tome como base |
| 19 | 2.17 | Compatibilidad sin número | AC | Cerrar: §7.1 ya no aplica y §7.4 está corregido; §7.3 va con PNS-81; §7.2 y §8.5, cerrados (el fabricante migra en `init()`) |

**A confirmar (no cambian el estado de la tabla):**

- **CF782 sin revisar en 3.1.879:** 33 filas (5 Críticas, 15 Altas) se apoyan solo en seg (código y
  pruebas de 3.1.782). Una regresión en 3.1.879 no estaría vista. Propuesta: lectura dirigida del código
  de `8d218ea` para cada una antes de cerrar el informe (solo lectura).
- **Lista «Candidatas» de la hoja:** no consta aprobada como lista; plan §3.2 copia de ella solo seis
  entradas (§5, fila 7). El AI de PNS-84, M16 y la hoja 21 (fichas con «Decidido: aceptar», sin «al
  informe» expreso) depende de esa lista.
- **Resto de PNS-83 en la mesa del PIN:** `close` y `notify_changed` siguen públicos (P-83b, staging E1′:
  responden). P-83b se dejó «para PNS-84 en E4′», y la ficha 7 de la hoja (PNS-84, aceptada) no los nombra.
- **Pruebas de la comparación sin registro de ejecución** (los hallazgos quedan CF por código): P-60
  (manejadores `data-*`), P-40 (proveedor caído), PNS-32 con dos workers, PNS-95/46 (texto libre del
  modelo), PB-2 con un módulo `web_*` de OCA. P-18, P-26 y P-54a no se hicieron, pero sus hallazgos están
  aceptados, al informe o pendientes de decisión.
- **Decisiones abiertas en `dec`** (no son estados de hallazgo): D9 y PB-2 («Bloqueantes vigentes»,
  ligadas a PNS-31 y PNS-42), D22 (nombres de campo sin valores; PNS-36, comp §7) y D28 (`platform`,
  PNS-51) siguen con «Decisión: ____».
- **Envío del informe del 16/10:** el documento sigue con la cabecera «Borrador»; la auditoría tiene
  fichas de PNS-93 a PNS-96 y de sus observaciones, así que el contenido llegó al fabricante (§5, fila 15).

**Decidido (Sergio, 09/11/2026), sobre «A confirmar»** (hoja de decisiones, §1 y filas 3.1 a 3.4):

- **CF782 (3.1):** la comparación con 3.1.973 (§3.2) ya revisó en nuestra copia las 20 Críticas y Altas:
  19 siguen corregidas y PNS-80 no aplica. Quedan las 13 Medias y Bajas: lectura dirigida, de solo
  lectura, antes de cerrar el informe. Los estados CF782 no cambian hasta esa lectura.
- **Lista «Candidatas» (§1):** aprobada como lista única del informe al fabricante. Confirma el AI de
  PNS-84, M16 y la hoja 21 y cierra la contradicción 7 (§5).
- **Resto de PNS-83 (3.2):** `close` y `notify_changed` de la mesa del PIN, aceptados (mesa sin uso, N4) y
  al informe; 3.1.973 ya hace privado `_close`. La fila de PNS-83 de §3 suma AC por este resto (ya tenía
  AI) y entra en los recuentos de §1.
- **Pruebas sin registro de ejecución (3.3):** sus hallazgos quedan CF por código; no bloquean el informe.
- **Decisiones abiertas en `dec` (3.4):** D9, PB-2 y D22 se deciden aparte (no son estados de hallazgo).
  D28 queda decidida en §2, fila 5.
- **Envío del informe del 16/10:** sin cambio; la decisión 3.5 se retiró por estar fuera del alcance.
- Las decisiones 3.6 a 3.9 (contradicciones 4, 6, 8 y 9 de §5) se registran en `dec`; §5 no se cambia.

## 2 bis. PROPUESTA SIN DECISIÓN

Fichas de la hoja de E4′ que solo traen «Propuesta». Ninguna de las lecturas nuevas (propuestas de E1′ a
E3′, plan, dec) les da una decisión expresa. Lo que falta en todas es la decisión de Sergio.

| # | Ficha (hoja) | Fila de §3 | Grav. | Propuesta de la hoja | Notas | Referencia |
|---|---|---|---|---|---|---|
| 1 | 5 | PNS-61 | Media | Aceptar; comunicar como observación | En «Candidatas» (aceptadas). Ya pedido el 15/10 (inf. 15/10 §7.3) | hoja ficha 5 |
| 2 | 9 | PNS-18 | Alta | Aceptar (D10); al informe | El «aceptar» lo cubre D10 (AC). Falta decidir el informe | hoja ficha 9; dec D10 |
| 3 | 10 | PNS-26 (resto y anexo) | Alta | Informe | Parte en «No se hará» (aud. §7). El anexo de la serialización en `/execute` se añadió a PNS-26 por decisión del 26/10 (diag R6 5.2) | hoja ficha 10 |
| 4 | 11 | PNS-88 | Baja | Sin acción; informe | Sin efecto en staging ni LIYBEN | hoja ficha 11 |
| 5 | 14 | M5 | Baja | Aceptar | En «Candidatas» (aceptadas) | hoja ficha 14 |
| 6 | 16 | Hoja 16 | — | Sin acción | Fuera del parche 18 por la decisión 4 de E2′ (alcance del parche, no aceptación); «No van» al informe | hoja ficha 16; prop E2′ decisiones 4 y 5 (segunda ronda) |
| 7 | 17 | Hoja 17 | Baja | Aceptar; informe | En «Candidatas» (aceptadas) | hoja ficha 17 |
| 8 | 18 | Hoja 18 | — | Informe, sin parche | En «Candidatas» (defectos) | hoja ficha 18 |
| 9 | 19 | Hoja 19 | — | Aceptar | «No van» al informe | hoja ficha 19 |
| 10 | 20 | Hoja 20 | — | Aceptar | «No van» al informe | hoja ficha 20 |
| 11 | 23 | Hoja 23 | — | Sin acción (nota de procedimiento) | «No van» al informe | hoja ficha 23 |
| 12 | 25 | Hoja 25 | — | Sin acción; informe (observación) | En «Candidatas» (aceptadas) | hoja ficha 25 |
| 13 | 28 | Hoja 28 | — | Informe | En «Candidatas» (defectos) | hoja ficha 28 |
| 14 | 30 | PNS-96 (parte «el chat afirma cambios que no hizo») | Baja | Corregir (parche 34) **y mantenerlo en el informe** | La decisión 9 aprueba el parche 34 (CS); no dice nada del informe | hoja ficha 30 y decisión 9 |
| 15 | 31 | Hoja 31 | — | Informe | En «Candidatas» (defectos) | hoja ficha 31 |
| 16 | 32 | Hoja 32 | — | Informe | En «Candidatas» (defectos) | hoja ficha 32 |
| 17 | 35 | Hoja 35 | — | Informe | En «Candidatas» (defectos) | hoja ficha 35 |
| 18 | 36 | Hoja 36 | — | Informe | En «Candidatas» (defectos) | hoja ficha 36 |
| 19 | 37 | Hoja 37 | — | Sin acción | Comportamiento correcto; «No van» al informe | hoja ficha 37 |

**Decidido (Sergio, 09/11/2026)** (hoja de decisiones, §1): las 19 fichas, tal como las propone la hoja, y
la lista «Candidatas» como lista única del informe. Ya no queda ninguna PSD. Estado nuevo en §3:

- **AC y AI:** fichas 5 (PNS-61, como observación), 9 (PNS-18; el AC ya venía de D10), 11 (PNS-88), 14
  (M5: la propuesta es aceptar y la lista «Candidatas» la lleva al informe), 17 y 25.
- **AI:** fichas 10 (PNS-26, resto y anexo), 18, 28, 30 (PNS-96; el parche 34 sigue como CS), 31, 32, 35 y
  36.
- **AC, sin informe:** fichas 16, 19, 20, 23 y 37 («No van» en «Candidatas»).

Criterio: «sin acción» cuenta como AC (decisión expresa de no actuar); «informe» solo, como AI.

Fichas de la hoja que **no** entran aquí porque tienen decisión expresa o un estado de otra fuente: 1, 2, 3,
6, 7, 8 (resto 3: «Decidido»; restos 1 y 2: D12 y D10), 15, 21, 22, 24, 26, 29, 33, 34 y 38 («Decidido» o
decisión del 27/10/2026); 4, 12 y 27 (al informe por plan §3.2); 13 (cerrada por el parche 28).

## 3. Tabla completa

Abreviaturas de origen: **inf.** informes de Seges (PNS-01 a 80, 08/10/2026; 81 a 92, 15/10/2026; 93 a
96, 16/10/2026); **aud.** auditoría del fabricante (sección de su ficha); **comp**; **hoja**; **seg**;
**lab** / **stg** laboratorio / staging. «p N» = parche N.

### 3.1 PNS-01 a PNS-102

| Id (alias) | Origen | Grav. | Título corto | Estado | Referencia | Notas |
|---|---|---|---|---|---|---|
| PNS-01 | inf.; aud. §4 | Crítica | Escalada de grupos por plan | CS (p12 adaptado; lab 23/10; stg 26/10); CF (cúspide) | comp §2.1; reg «Parche 12 adaptado»; plan §5 | Criterio de Seges decidido el 23/10 (prop E1′; dec). No figura en plan §3.2 |
| PNS-02 | inf.; aud. §4 y §7 | Crítica | `apply_*` y quitar grupos | CS (p12 adaptado; lab 23/10; stg 26/10); CF (cúspide) | comp §2.1, §7 «PNS-02 (parte)» | La defensa de su §7 no existe tal como la describe (comp §7, NO CORREGIDO); la cubre el p12 |
| PNS-03 | inf. | Crítica | Dueño cambia `status`/`user_id` de su operación | CF782 | seg tabla (CORREGIDO; 3b-1) | comp no lo revisa |
| PNS-04 | inf. | Crítica | `confirmed_uid` elegido por quien llama | CF782 | seg tabla (CORREGIDO; solo código) | comp no lo revisa |
| PNS-05 | inf. | Crítica | `get_safe_operation_status` sin filtro | CF782 | seg tabla (CORREGIDO; staging, prueba 6) | comp no lo revisa |
| PNS-06 | inf. | Crítica | `code_body` ejecutado al guardar | CF782 | seg tabla (CORREGIDO; 3b-1, en parte) | comp no lo revisa |
| PNS-07 | inf.; aud. §4 | Crítica | Métodos públicos con cursor propio desde el sandbox | CS (p15; lab 23/10; stg 26/10; R8 stg 03/11); CF (privados); AI | comp §2.1, §3; reg «Parche 15»; plan §3.2 | Fabricante PARCIAL |
| PNS-08 | inf. | Alta | Credenciales de `ai.api.server` legibles | CF782 | seg tabla (CORREGIDO; 3b-1) | comp no lo revisa |
| PNS-09 | inf. | Alta | MCP `stdio` | CF782 | seg tabla (CORREGIDO; 3b-1, en parte) | comp no lo revisa |
| PNS-10 | inf. | Alta | `skip_hardcoded_restrictions` por contexto | CF782 | seg tabla (CORREGIDO; 3b-1) | comp no lo revisa |
| PNS-11 | inf. | Alta | Métodos públicos de `ai.skill`/`ai.context` en `sudo` | CF782 | seg tabla (CORREGIDO; 3b-1) | M13 es un caso nuevo del mismo patrón (p14) |
| PNS-12 | inf. | Alta | Contextos privados expuestos | CF782 | seg tabla (CORREGIDO; 3c y staging, prueba 10) | comp no lo revisa |
| PNS-13 | inf. | Alta | `/mcp/message` sin revalidar | CF782 | seg tabla (CORREGIDO; 3b-1) | comp no lo revisa |
| PNS-14 | inf. | Alta | Cachés legibles por todos | CF (resto: PNS-90, VERIFICADO); CF782 (`ai.api.result.cache` y `ai.safe.choice`) | seg tabla (PARCIAL); comp §2.1 PNS-90 | — |
| PNS-15 | inf. | Alta | HTML sin sanear | CF782 | seg tabla (CORREGIDO; solo código) | comp no lo revisa |
| PNS-16 | inf.; aud. §4 | Alta | Prompt injection y autoconfirmación | CF | comp §2.1 | — |
| PNS-17 | inf.; aud. §4 | Alta | Cabeceras en redirecciones (SSRF) | CS (p19; lab 28/10 P-17; stg 29/10 sin prueba propia); CF (parcial) | comp §3; reg «Parche 19»; plan §5; prop E2′ decisiones 5 y 6 | Resto «params/data» en hoja 17. No figura en plan §3.2 |
| PNS-18 | inf.; aud. §6 y §7 | Alta (seg); sin gravedad (comp) | «Sin failover externo» no corta en todos los caminos | AC (D10); AI (09/11) | comp §6.1, §7; hoja ficha 9; dec D10 (ACEPTADA, 19/10/2026) | §2 bis, fila 2. Gravedad distinta entre documentos (§5) |
| PNS-19 | inf.; aud. §4 | Alta | Credenciales alcanzables por relaciones | CS (p18; lab 28/10 P-19; stg 29/10 P-19); CF (parcial) | comp §3; reg «Parche 18»; plan §5; prop E2′ (tres rondas) | Ventana del lienzo mantenida (prop E3′, decisión 5). No figura en plan §3.2 |
| PNS-20 | inf.; aud. §4 y §6 | Alta | Importación que sobrescribe; «Review» escribe | CS (p21; lab 28/10 P-20; stg 29/10 P-20); CF (resto) | comp §2.1, §6.1; reg «Parche 21»; prop E2′ «Resultado de P-20» | Caché del agente durante «Review»: hoja 18. No figura en plan §3.2 |
| PNS-21 | inf. | Alta | Exportaciones sin sesión | CF782 | seg tabla (CORREGIDO; 3c) | Resto comunicado como obs. 6 (§3.2) |
| PNS-22 | inf.; aud. §4 | Media | `is_write` no centralizado | CF | comp §2.1 | Su check no es reproducible |
| PNS-23 | inf.; aud. §7 | Alta | Skills activas sin revisión | AC (regla de importación de paquetes en la guía de configuración) y AI (09/11) | comp §7; inf. 15/10 §7.1 | §2, fila 6 |
| PNS-24 | inf.; aud. §5 | Alta | `module.update` | CF | comp §5.3 | — |
| PNS-25 | inf. | Alta | Doble ejecución tras failover | CF782 | seg tabla (CORREGIDO; solo código) | comp no lo revisa |
| PNS-26 (anexo: serialización en `/execute` de la tarjeta) | inf.; aud. §5 y §7; stg E1′ | Alta (anexo Baja) | `SAVEPOINT` del motor y `commit` de la caja B | AI (09/11) | comp §5.6, §7; hoja ficha 10; diag R6 5.2 | §2 bis, fila 3 |
| PNS-27 | inf. | Alta | jsPDF/SheetJS con CVE | CF782 | seg tabla (CORREGIDO; solo código) | comp no lo revisa |
| PNS-28 | inf.; aud. §4 | Media | CORS y `Origin` | CF; AI (salvedad, como observación; sin P-28; 09/11) | comp §2.1, §3 | §2, fila 8 |
| PNS-29 | inf.; aud. §5 y §6 | Media | Tope de gasto y `month_usage` | CS (p33, resto 3; lab 05/11, script lab 06 y 09/11; stg 09/11); CF (parte); AC (restos 1 y 2: D12, D10); AI | comp §5.5, §6.1; hoja ficha 8 y decisión 1; reg «Parche 33»; plan §3.2 | Alcance real del resto 3: también portal (reg, N33n) |
| PNS-30 | inf.; aud. §4 | Media | `ai.log` modificable a nombre de otro | CF (`_create_log_entry`); CS (p30, vía M11); AI | comp §2.1 salvedad, §8.7 M11 | El VERIFICADO de comp no cubría los `log_*` |
| PNS-31 (obs. 4) | inf.; aud. §5 | Media | Parches globales | CF | comp §5.4, §5.7 | D9 sin decidir (§2) |
| PNS-32 | inf.; aud. §5 | Media | Sincronización de fábrica | CF | comp §5.3 | Dos workers: REQUIERE PRUEBA, sin hacer |
| PNS-33 | inf.; aud. §4 y §7 | Media | Claves MCP | CF (URL y log); AC y AI (parte §7; 09/11) | comp §2.1, §7; inf. 15/10 §7.7 | §2, fila 7 |
| PNS-34 | inf. | Media | Test con commit de una clave | CF782 | seg tabla (CORREGIDO; solo código) | Resto menor comunicado como obs. 13 (§3.2) |
| PNS-35 | inf.; aud. §4 | Media | Fórmulas en XLSX | CF | comp §2.1 | — |
| PNS-36 | inf.; aud. §4 y §7 | Media | Nombre de la BD por `.format` | CS (p23 ampliado; lab 28/10; stg 29/10; test E4′.a 05/11) | comp §3 «Cierre»; hoja ficha 6 y decisión 3; reg «Test de PNS-36» | Nombres de campo sin valores: D22 sin decidir |
| PNS-37 | inf.; aud. §4 y §6 | Media (parte Alta, propuesta) | Papelera del diario y borrado por plan | CS (p17; lab 28/10; stg 29/10, P-37b a mano); CF (resto) | comp §2.1, §6.1; reg «Parche 17»; prop E2′ decisiones 1 y 2 | No figura en plan §3.2 |
| PNS-38 | inf.; aud. §5 | Media | Conocimiento de fábrica | CF | comp §5.5 | — |
| PNS-39 | inf.; aud. §5 | Media | Desviaciones MCP | CF | comp §5.5 | — |
| PNS-40 | inf.; aud. §4 y §5 | Media | Parámetros LLM y endpoint en el error | CF | comp §2.1, §5.5 | P-40 sin hacer |
| PNS-41 | inf. | Media | `website` de todos los módulos | CF | comp §5.7 PB-1 (sigue CERRADA); seg tabla | La única de las corregidas en 3.1.782 que comp revisa |
| PNS-42 | inf.; aud. §5 | Media | Validación global de formularios | CF (alcance) | comp §5.4, §5.7 | PB-2 sin decidir; nuevo `fields_view_get` global |
| PNS-43 | inf.; aud. §5 | Baja | Traducciones duplicadas | CF | comp §5.4 | — |
| PNS-44 | inf. | Baja | Escrituras en `ir.module.module` | CF782 (ya no aplica) | seg tabla | comp no lo revisa |
| PNS-45 | inf. | Baja | `ImportError` silenciado | CF782 | seg tabla (CORREGIDO) | comp no lo revisa |
| PNS-46 | inf.; aud. §5 (con PNS-95) | Baja | Glosario `es_ES` | CF | comp §5.5 | Texto del modelo: REQUIERE PRUEBA, sin hacer |
| PNS-47 | inf. | Baja | Esperas de las fuentes FX | CF782 | seg tabla (CORREGIDO) | comp no lo revisa |
| PNS-48 | inf. | Baja | Menú Settings | CF782 | seg tabla (CORREGIDO) | comp no lo revisa |
| PNS-49 (obs. 12) | inf.; aud. §5 | Baja | Código muerto | CF | comp §5.5 | — |
| PNS-50 | inf.; aud. §5 (con PNS-77) | Baja | Tests no cargados | CF (parcial); AC | comp §5.5, §5.6; dec 23/10 | Tests de Seges (E0′ en adelante); no se piden los `unit_tests/`. La columna «Rama Seges» de seg aún dice «previsto en ET» (§5, fila 2) |
| PNS-51 | inf. | Baja | `platform` en el sandbox | AC y AI (D28: aceptar y repetir la petición; 09/11) | seg PNS-51; inf. 15/10 §7.2; dec D28 | §2, fila 5. Sigue en `validators_base.py:95` |
| PNS-52 | inf. | Baja | `settings_io` | CF782 | seg tabla (CORREGIDO) | comp no lo revisa |
| PNS-53 | inf. | Crítica | XSS almacenado entre usuarios | CF782 | seg tabla (CORREGIDO; 3b-1) | comp no lo revisa |
| PNS-54 (anexo: `missing_token`/`bad_token`) | inf.; aud. §4 y §7; stg E1′ | Crítica | Confirmación sin el usuario | CS (p16; lab 23/10; stg 26/10); AC (opción c, D29); AI | comp §3, §7; reg «Parche 16»; prop E1′ «Decisiones de Sergio»; plan §3.2; diag R6 5.3 | Anexo, Baja (añadido por decisión del 26/10) |
| PNS-55 (D4) | inf.; aud. §4 | Alta | Aislamiento de Chatboo | CF | comp §2.1, §8.3 D4 | — |
| PNS-56 | inf. | Alta | Inyección en el turno de otro | CF782 | seg tabla (CORREGIDO; 3b-1) | comp no lo revisa |
| PNS-57 | inf. | Alta | Turnos por RPC sin clave | CF782 | seg tabla (CORREGIDO; 3b-1) | comp no lo revisa |
| PNS-58 | inf. | Alta | `/chatboo/stream` sin CSRF | CF782 | seg tabla (CORREGIDO; 3b-1) | comp no lo revisa |
| PNS-59 | inf.; aud. §4 | Alta | Imágenes externas | CF | comp §2.1 | — |
| PNS-60 | inf.; aud. §4 | Alta | HTML del asistente sin sanear | CF (código) | comp §2.1, §3 | P-60 sin hacer |
| PNS-61 | inf.; aud. §4 | Media | Historial escrito por el navegador | AC y AI (observación; 09/11) | comp §3; hoja ficha 5 | §2 bis, fila 1 |
| PNS-62 | inf.; aud. §4 | Media | Adjuntos sin límites | CF | comp §2.1 | — |
| PNS-63 | inf. | Media | Retención de sesiones | CF782 | seg tabla (CORREGIDO); aud. obs. 5 | comp no lo revisa (sí la obs. 5) |
| PNS-64 | inf.; aud. §6 | Media | Voces remotas | CF | comp §6 | — |
| PNS-65 | inf.; aud. §4 | Media | Exportaciones del navegador | CF | comp §2.1 | — |
| PNS-66 | inf.; aud. §4 | Media | Skills sin grupo | CF | comp §2.1 | — |
| PNS-67 | inf. | Media | Errores en skills financieras | CF782 | seg tabla (CORREGIDO) | comp no lo revisa |
| PNS-68 | inf.; aud. §5 | Media | Migraciones que borran skills | CF | comp §5.2 | — |
| PNS-69 | inf. | Baja | `SELF_*_FIELDS` como `property` | CF782 | seg tabla (CORREGIDO) | comp no lo revisa |
| PNS-70 | inf.; aud. §5 | Alta (desde 23/10; antes Media) | Chart.js 4 en `window.Chart` | CS (p20; lab 28/10 P-70; stg 29/10 P-70); AI | comp §5.6; reg «Parche 20»; prop E2′ decisión 8; plan §3.2 | Gravedad distinta en seg (§5) |
| PNS-71 | inf. | Baja | `check_health` expone infraestructura | CF782 | seg tabla (CORREGIDO; 3b-1) | Resto comunicado como obs. 7 (§3.2) |
| PNS-72 | inf.; aud. §5 | Baja | Librerías JS en todo el backend | CF | comp §5.4 | — |
| PNS-73 | inf.; aud. §5 | Baja | Sintaxis y `z-index` | CF | comp §5.5 | Quedan capas por encima del modal (nota de comp) |
| PNS-74 (obs. 12) | inf.; aud. §5 | Baja | Código muerto del cliente | CF | comp §5.5 | — |
| PNS-75 | inf. | Baja | TSV sin neutralizar fórmulas | CF782 | seg tabla (CORREGIDO) | comp no lo revisa |
| PNS-76 | inf.; aud. §5 | Baja | Receta del agente | CF | comp §5.2 | — |
| PNS-77 | inf.; aud. §5 (con PNS-50) | Baja | Chatboo sin tests | CF (parcial); AC | comp §5.6; dec 23/10 | Tests de Chatboo de Seges |
| PNS-78 | inf. | Baja | Etiquetas duplicadas en `ai.agent` | CF782 | seg tabla (CORREGIDO) | comp no lo revisa |
| PNS-79 | inf. | Baja | `/mcp/message` con `SUPERUSER_ID` | CF782 | seg tabla (CORREGIDO; 3b-1 no concluyente) | comp no lo revisa |
| PNS-80 | inf. | Alta | `read_progress` | CF782 (ya no aplica) | seg tabla (3c) | comp no lo revisa |
| PNS-81 (parches 1 a 4) | inf. 15/10; aud. §5 | Alta | Incompatibilidades con Odoo 14 | CF (p1-p4 retirados; paridad de la fase 3); AC y AI (resto, «corregido en 3.1.973»; 09/11) | comp §2.2, §2.4, §5.1; reg «Cambio de base» | §2, fila 4 |
| PNS-82 (parche 11) | inf. 15/10; aud. §4 | Alta (resto Baja) | Reclamación y borrado de adjuntos ajenos | CS (p11 adaptado; lab 28/10; stg 29/10 P-82); CF (reclamación) | comp §3; reg «Parche 11 adaptado»; prop E2′ decisión 7 | No figura en plan §3.2 |
| PNS-83 (`collect_pin`) | inf. 15/10; aud. §4 | Alta | Canje de PIN sin límite | CS (p10 adaptado; lab 23/10; stg 26/10); AC (resto: `close` y `notify_changed`, 09/11); AI | comp §3; reg «Parche 10 adaptado»; plan §3.2 | `close` y `notify_changed`: §2, «A confirmar» |
| PNS-84 (hoja 7) | inf. 15/10; aud. §4 | Media | PIN y clave en tránsito | CS (p10, en parte); AC (hoja, decisión 2); AI | comp §3; hoja ficha 7; «Candidatas» | AI solo por «Candidatas» (§2, «A confirmar») |
| PNS-85 (parche 9) | inf. 15/10; aud. §4 | Media | Caché de parámetros de skills | CF (p9 retirado) | comp §2.1, §2.2 | — |
| PNS-86 | inf. 15/10; aud. §4 | Media | Generador OpenAPI | CF | comp §2.1 | — |
| PNS-87 | inf. 15/10; aud. §5 | Baja | Pérdida de datos de consumo al actualizar | CF | comp §5.2 | `agent_id`: fila U9 |
| PNS-88 (hoja 11) | inf. 15/10; aud. §5 | Baja | Renombrados de 3.1.518 que faltan | AC (sin acción) y AI (09/11) | comp §5.6; hoja ficha 11 | §2 bis, fila 4 |
| PNS-89 | inf. 15/10; aud. §4 | Baja | `key_pin/stop` sin CSRF | CF | comp §2.1 | — |
| PNS-90 (parche 7) | inf. 15/10; aud. §4 | Alta | Caché de `fetch_url` | CF (p7 retirado) | comp §2.1, §2.2 | — |
| PNS-91 (parche 8) | inf. 15/10; aud. §4 | Media | `ensure_domain_whitelisted` | CF (p8 retirado) | comp §2.1, §2.2 | — |
| PNS-92 | inf. 15/10; aud. §4 | Media | `set_mcp_api_key` | CF | comp §2.1 | — |
| PNS-93 (parche 5) | inf. 16/10; aud. §5 | Media | `thought_signature` de Gemini 3 | CF (p5 retirado) | comp §2.2, §5.1 | En uso con Gemini en el staging desde E1′ |
| PNS-94 (parche 6) | inf. 16/10; aud. §5 | Alta | Bloqueo de `chatboo_session` | CF (p6 retirado; P-6 ampliada sin bloqueos, fase 3, 23/10) | comp §5.6 | Resto 4 (serialización al cargar): fila «Carga de la sesión» |
| PNS-95 | inf. 16/10; aud. §5 | Baja | Formato de importes | CF (tablas y ficheros) | comp §5.5 | Texto del modelo sin probar |
| PNS-96 (hoja 30; «el chat afirma cambios que no hizo») | inf. 16/10; aud. §6; lab E3′ y p29; stg E4′ | Baja | Calidad con modelos `lite` | CF (enlaces); CS (p34, aviso; lab 06/11; stg 09/11); AI (09/11) | comp §6; hoja ficha 30 y decisión 9; reg «Parche 34», «E4′.b2 y E4′.b3» | §2 bis, fila 14. V3 y F1-t no concluyentes (no bloquean, stE4 G) |
| PNS-97 (hoja 3) | seg (nuevo) | Media | `ai.trusted.action` editable | CS (p32; lab 05/11, script lab 06 y 09/11; stg 09/11); AI | comp §2.3, §3; hoja decisión 1; reg «Parche 32»; plan §3.2 | Ampliado: vía del plan, campos y «confused deputy» |
| PNS-98 (hoja 4) | seg (nuevo) | Baja | Adjuntos huérfanos | AI | comp §2.3, §3; hoja ficha 4; plan §3.2 | Confirmado en la fase 3; seg aún dice «fase posterior» (§5, fila 2) |
| PNS-99 | seg (nuevo, stg E1′) | Media | `remove_group` sin efecto y diario `applied` | AC y AI (09/11) | seg PNS-99; diag R6 5.1 | §2, fila 3 |
| PNS-100 | seg (nuevo, E2′) | Alta | Efectos fuera de la BD desde la caja A | CS (p22; tests lab 27/10; stg 29/10 sin prueba propia); AI | reg «Parche 22»; prop E2′ tercera ronda, decisión 3; plan §3.2 | Gravedad Alta decidida el 27/10 |
| PNS-101 | seg (nuevo, E2′) | Crítica | Entornos reales del hilo desde la caja A | CS (p23 ampliado; lab 28/10 P-101 y P-101′; stg 29/10 P-101); AI | reg «Parche 23»; prop E2′ «Revisión del parche 18», «Enfoque de raíz»; plan §3.2 | §2, fila 1 |
| PNS-102 | seg (nuevo, E2′) | Crítica | `user`/`company` con `su` | CS (p24; lab 28/10 P-102; stg 29/10 sin prueba propia); AI | reg «Parche 24»; plan §3.2 | §2, fila 2. Claves MCP de LIYBEN: regenerar tras el despliegue (plan §3.1) |
| PNS-103 | seg (nuevo, lab 3973, 11/11) | Baja | AI Administrator sin Ajustes: `AccessError` en la revisión y el resultado de las importaciones | AI (12/11) | seg PNS-103; reg «Parche 36» | Alta del 12/11 (§1, nota). Mismo código en 3.1.879 (`_inject_*_arch` sin `sudo`); no se corrige en `14.0-pns-ai-3879` (`pns_demo` lo tiene; se validó con usuarios con Ajustes). Corregido en `14.0-pns-ai-3973` por el p36 |
| PNS-104 | seg (nuevo, batería 3973, 12/11) | Baja (propuesta) | Cerrar la caja A descarta las escrituras pendientes del llamador (`rollback` → `clear_env` → `env.clear()`) | Sin estado (pendiente de decisión) | seg PNS-104; prop fase 3, «Propuesta: parche de `flush`» | Alta del 12/11 (§1, notas). Latente: ningún llamador real pierde datos hoy. Mismo código en 3.1.879; sin corregir en ninguna rama (parche de `flush` previsto en la 3b, como defensa) |
| PNS-105 | seg (nuevo, lectura de código 3973, 12/11) | Alta (propuesta) | Los cursores propios con `commit` (p. ej. `ai.log._create_log_entry`) confirman y descartan las escrituras pendientes de quien los llama (`Cursor.commit` → `flush_env`) | Sin estado (pendiente de decisión) | seg PNS-105; prop fase 3, «Resultado de X1 a X4» | Alta del 12/11 (§1, nota). Sin confirmar en ejecución (test después de la 3b). Mismo patrón en 3.1.879; sin parche |

### 3.2 Observaciones comunicadas, petición de §5 y compatibilidad sin número

«Obs. N» = observación menor N del informe del 16/10 (§6); las 1 a 5 y la 12 ya iban el 15/10 (§7).

| Id | Origen | Grav. | Título corto | Estado | Referencia | Notas |
|---|---|---|---|---|---|---|
| obs. 1 | inf. 15/10 §7.6; aud. §6 | — | `system_prompt` duplicado | CF | comp §6 | — |
| obs. 2 | inf. 15/10 §7.7; aud. §4 | — | Fragmentos de la clave en el log | CF | comp §2.1 | Parte de PNS-33 |
| obs. 3 | inf. 15/10 §7.5; aud. §4 | — | `api_key` con `copy=False` | CF | comp §2.1 | — |
| obs. 4 | inf. 15/10 §7.9; aud. §5 (con PNS-31) | — | Parches globales | CF | comp §5.4 | — |
| obs. 5 | inf. 16/10 §6; aud. §5 | — | Retención de Chatboo | CF | comp §5.2 | Nota sobre PNS-63 |
| obs. 6 | inf. 16/10 §6 | — | Descargas del chat fuera de la purga de 24 h | AI (repetir; 09/11) | seg PNS-21 | §2, fila 16. Sin ficha en la auditoría |
| obs. 7 | inf. 16/10 §6 | — | `_fx_payload` devuelve `str(exc)` | AI (repetir; 09/11) | seg PNS-71 | §2, fila 17. Sin ficha en la auditoría |
| obs. 8 | inf. 16/10 §6; aud. §4 | — | `_choose` privado | CF | comp §2.1 | — |
| obs. 9 | inf. 16/10 §6; aud. §6 | — | Agente sin cadena | CF | comp §6 | Ver PNS-18 |
| obs. 10 | inf. 16/10 §6; aud. §6 | — | Tipos de cambio al abrir Chatboo | CF (lo que dice la ficha) | comp §6 | La descarga sin control de host es M16 |
| obs. 11 | inf. 16/10 §6; aud. §6 | — | Skill retirada borrada en cada `-u` | CF | comp §6 | — |
| obs. 12 | inf. 15/10; aud. §5 (con PNS-49/74) | — | `detect_dangerous_operations` sin uso | CF | comp §5.5 | — |
| obs. 13 | inf. 16/10 §6 | — | Tests que cambian la clave del administrador | AI (repetir solo si sigue en la versión base; 09/11) | seg PNS-34 | §2, fila 18. Sin ficha en la auditoría |
| Petición de §5 | inf. 16/10 §5; aud. §6 | — | El prompt que recibe el modelo, en `ai.log` | AI (repetir; 09/11) | comp §6, §6.1 | §2, fila 9 |
| Compatibilidad sin número (§7.1 a §7.4 y §8.5) | inf. 08/10 | — | `external_dependencies`, migraciones `3.1.x`, APIs de 3.8+, cron sin `numbercall` | AC (cerrada; 09/11) | comp §9.1; seg «Compatibilidad con Odoo 14» | §2, fila 19. Por Grep: §7.1 y §7.4, ya no están en el código |

### 3.3 Superficie nueva y cambios no anunciados (comp §8)

| Id (alias) | Origen | Grav. | Título corto | Estado | Referencia | Notas |
|---|---|---|---|---|---|---|
| §8.1 (10 rutas) | comp §8.1 | — | Rutas nuevas del lienzo, la mesa del PIN y `fulfill_export` | CF | comp §8.1 | Contenido de la página: F1 |
| M1 | comp §8.2 | Media | `paint_canvas` escribe el lienzo ajeno | CS (p25; lab 30/10 P-8c; stg 04/11) | reg «Parche 25»; prop E3′ «Propuesta final», 1; plan §5 | No figura en plan §3.2 |
| M2 | comp §8.2 | Media | `page_html` lee imágenes en `sudo` | CS (p26; lab 30/10 P-8d; stg 04/11) | reg «Parche 26»; prop E3′ «Propuesta final», 2 | Ídem. Efecto visible aceptado: hoja 33 |
| M3 | comp §8.2 | — | `page_url`, `page_edit` | CF (dueño); CS (p26, desde el sandbox) | comp §8.2 y nota del 29/10 | — |
| M4 | comp §8.2 | — | `canvas_public_url` y otros | CF | comp §8.2 | — |
| M5 (hoja 14) | comp §8.2 | Baja | `cron_maintenance` público | AC y AI (09/11) | hoja ficha 14 | §2 bis, fila 5 |
| M6 | comp §8.2 | — | `request_cancel`, `mark_seen` | CF | comp §8.2 | — |
| M7 | comp §8.2 | — | `model_can_archive` | CF | comp §8.2 | — |
| M8 | comp §8.2 | — | Vaciar la papelera | CF | comp §8.2 | — |
| M9 | comp §8.2 | — | `action_revert` y otros | CF | comp §8.2 | — |
| M10 | comp §8.2, §8.7 | Crítica | Plan con la identidad de otro (`create` + `cleanup_stuck_state`) | CS (p13 con p12; lab 23/10; stg 26/10 P-8b); AI | reg «Parche 13»; prop E1′ «Decisiones de Sergio»; plan §3.2 | — |
| M11 (hoja 1) | comp §8.2, §8.7 | Media | `log_*` a nombre de otro | CS (p30; lab 05/11, script lab 06 y 09/11; stg 09/11 P-30); AI | reg «Parche 30»; hoja decisión 1; plan §3.2 | Queda, aceptado: filas a su propio nombre |
| M12 (hoja 2) | comp §8.2, §8.7 | Baja | `chat_completion` directo | CS (p31; ídem; stg 09/11 P-31); AI | reg «Parche 31»; hoja decisión 1; plan §3.2 | — |
| M13 | comp §8.2, §8.7 | Alta | Borrado de contextos de fábrica | CS (p14; lab 23/10; stg 26/10 P-8a); AI | reg «Parche 14»; plan §3.2 | — |
| M14 | comp §8.2 | — | Gemelo de skills | CF | comp §8.2 | — |
| M15 | comp §8.2 | — | Topes de gasto | CF | comp §8.2 | — |
| M16 (hoja 15; obs. 10) | comp §8.2 | Baja | `get_usd_fx` sin control de host | CS (p22, solo en la caja A); AC (hoja, decisión 2); AI | hoja ficha 15; «Candidatas» | Queda el RPC. AI solo por «Candidatas» (§2, «A confirmar») |
| D1 (hoja 13) | comp §8.3 | Baja | Páginas compartidas | CS (p28; lab 30/10 P-8h; stg 03-04/11) | reg «Parche 28»; prop E3′ «Propuesta final», 4 | El AI Administrator lee y borra todas (decisión del 29/10). m3: 0 lectores de portal (lab y stg; LIYBEN en plan §3). No figura en plan §3.2 |
| D2 | comp §8.3 | — | `chatboo.canvas.job` | CF | comp §8.3 | — |
| D3 | comp §8.3 | — | `chatboo.job.mixin` | CF | comp §8.3 | — |
| D5 | comp §8.3 | — | Campos nuevos del lienzo | CF | comp §8.3 | — |
| D6 | comp §8.3 | — | Asistente de consumo | CF | comp §8.3 | — |
| D7 | comp §8.3 | — | Mixin de leyenda | CF | comp §8.3 | — |
| D8 | comp §8.3 | — | Herencias nuevas | CF | comp §8.3 | — |
| F1 (alias: P-8e a) | comp §8.4 | Media | El lienzo saca datos | CS (p27 y p29; lab 30/10 y 03/11; stg 04/11); AC (riesgos del p27 e y del p29; m4) | reg «Parche 27», «Parche 29»; prop E3′ «Propuesta final», 3, y «Revisión (29/10/2026)»; e3_hallazgo_p8ea §5 | Aceptados: autonavegación, WebRTC/DNS, `innerHTML`, comilla simple, páginas guardadas antes, 404 sin `X-Frame-Options` (m4). No figura en plan §3.2 |
| F2 | comp §8.4 | — | Protocolos `openrouter`/`systemone` | CF (sin cambio) | comp §8.4 | — |
| F3 | comp §8.4 | — | Orígenes MCP permitidos | CF | comp §8.4 | — |
| F4 (hoja 12; alias: «HTML crudo en PDF/DOCX») | comp §8.4 (fase 3) | Baja | PDF con el HTML de la tabla como texto | AI | hoja ficha 12; reg «Para el informe»; plan §3.2 | Ver §5, fila 6 |
| C1 | comp §8.5 | — | Ruta `save_raw_for_template` eliminada | CF (no anunciada) | comp §8.5 | — |
| C2 | comp §8.5 | — | Guarda de jobs en el mixin | CF (no anunciada) | comp §8.5 | — |

### 3.4 Actualización e información del paquete (comp §1.4, §9 y §10)

| Id | Origen | Grav. | Título corto | Estado | Referencia | Notas |
|---|---|---|---|---|---|---|
| U9 | comp §9.2, §9.3 | — (datos) | El `-u` borra `ai_log.agent_id` (nota de versión falsa) | AC (no se conserva, dec 23/10); AI | comp §9.6 P-9b; plan §3.1 y §3.2 | — |
| U6 | comp §9.2 | — (datos) | Cinco parámetros renombrados, no anunciado | AC (pérdidas de P-9, condición 4) | comp §9.6; verif E1′ | No figura en plan §3.2 |
| U11 | comp §9.2 | — (datos) | Agente «Decision» huérfano, no anunciado | AI (sin P-9d; 09/11) | comp §9.2, §9.6 | §2, fila 10 |
| U15 | comp §9.2 | — (datos) | Resiembra y tres skills nuevas, no anunciadas | AC (P-9, condición 4) | comp §9.2; verif E1′ | Riesgo de las skills: PNS-23 |
| U16 | comp §9.2 | — (datos) | Historial de Chatboo reescrito, no anunciado | AC (P-9e; R2 de E1′ conforme) | comp §9.6; verif E1′ | — |
| Numeración de `pns_base` 1.2.47 | comp §1.4, §9.1 | — | Número que no casa con el contenido | AI (observación) | plan §3.2 | No se pide el commit (dec 23/10) |
| `unit_tests/` no entregados | comp §1.4 | — | Tests citados que no vienen en el paquete | AC (dec 23/10: no se piden) | dec N12, «Decisiones del 23/10/2026» | — |

### 3.5 Observaciones de E2′ a E4′ (hoja, fichas 16 a 38, salvo alias) y de laboratorio y staging

| Id (alias) | Origen | Grav. | Título corto | Estado | Referencia | Notas |
|---|---|---|---|---|---|---|
| Hoja 16 | prop E2′ | — | Tokens de portal | AC (sin acción; 09/11) | hoja ficha 16 | §2 bis, fila 6 |
| Hoja 17 | prop E2′ (PNS-17) | Baja | Reenvío de `params` y `data` en redirecciones | AC y AI (09/11) | hoja ficha 17 | §2 bis, fila 7 |
| Hoja 18 | prop E2′ (parche 21) | — | Caché del agente confirmada durante «Review» | AI (09/11) | hoja ficha 18 | §2 bis, fila 8 |
| Hoja 19 | prop E2′ | — | `onchange_email` y Gravatar | AC (09/11) | hoja ficha 19 | §2 bis, fila 9 |
| Hoja 20 | prop E2′ | — | `bus.presence.update` en cursor propio | AC (09/11) | hoja ficha 20 | §2 bis, fila 10 |
| Hoja 21 | reg «Parche 18» | Baja (muy baja) | Orden por un campo secreto en la caja A | AC (hoja, decisión 2); AI | hoja ficha 21; «Candidatas» | AI solo por «Candidatas» (§2, «A confirmar») |
| Hoja 22 (`customer_360._iso`) | reg «Parche 23», tests | — | `ensure_module_result_call` añade `result = …` | AI (hoja, decisión 4) | hoja ficha 22; plan §3.2 | — |
| Hoja 23 | stE2 G A.7 | — | «Test Connection» escribe en el proveedor | AC (sin acción; 09/11) | hoja ficha 23 | §2 bis, fila 11 |
| Hoja 24 | stE2 G D.1 | — | Etiqueta MCP del script de E2′ | CS (script de E4′.h, sin parche; lab 06 y 09/11; stg 09/11) | hoja decisión 8; plan, nota del 06/11 | — |
| Hoja 25 | stE2 G D.3 | — | La autenticación MCP no consulta el estado de la clave | AC (sin acción) y AI (09/11) | hoja ficha 25 | §2 bis, fila 12 |
| Hoja 26 | stE2 G D.0 y D.1 | — | Casilla AI Conversational de Usuarios MCP | AI | hoja ficha 26, decisión 5; plan §3.2 | §2, fila 11. Pendiente antes del informe: reproducción en el laboratorio con un usuario que no sea AI Administrator (decisión 5) |
| Hoja 27 | lab E3′ R8 | — | Defecto de `keys` en la muestra para Design | AI | hoja ficha 27; plan §3.2 (05/11) | — |
| Hoja 28 | lab E3′ | — | Nombre de la descarga del lienzo | AI (09/11) | hoja ficha 28 | §2 bis, fila 13 |
| Hoja 29 | lab p29; stE3 G | — | Casilla «Design» en `lite` | AC (hoja, decisión 6) | hoja ficha 29; plan §3.1 y §4 | Laboratorio y staging, hechos; LIYBEN, en §3.1 |
| Hoja 31 | lab p29; stE3 G | — | Varias llamadas a Design por edición | AI (09/11) | hoja ficha 31 | §2 bis, fila 15 |
| Hoja 32 | lab p29 6d; stE4 G (sesión 61) | — | El orquestador reinterpreta peticiones | AI (09/11) | hoja ficha 32 | §2 bis, fila 16 |
| Hoja 33 | stE3 G D.1 | — | «[object Object]» en la tarjeta de `lite` | AC (hoja, decisión 7) | hoja ficha 33; reg «Parche 26», «Qué se degrada» | Efecto del p26 |
| Hoja 34 | stE3 G D.0 | — | `pruebas_e3p_lab.py` no resiste un 503 | CS (script de E4′.h; lab 06 y 09/11; stg 09/11) | hoja decisión 8 | — |
| Hoja 35 | stE3 G D.1 6b | — | `relaxaicode` aunque se pida no consultar | AI (09/11) | hoja ficha 35 | §2 bis, fila 17 |
| Hoja 36 | stE3 G D.1 5c | — | `ai_log` sin el detalle del error del failover | AI (09/11) | hoja ficha 36 | §2 bis, fila 18 |
| Hoja 37 | stE3 G D.1 6e | — | El validador rechaza `dir()` | AC (sin acción; 09/11) | hoja ficha 37 | §2 bis, fila 19. Comportamiento correcto |
| Hoja 38 | plan E4′ | — | `iap.account.account_token` legible | AC (decisión del 27/10; p18 en la caja A) | hoja ficha 38; prop E2′ segunda ronda, decisión 5 | ACL del core |
| Botón Canvas sin aviso (y sin tooltip en el staging) | lab E4′.b2-b3 (06/11); stE4 G | — | El error del botón Canvas no se ve en pantalla | AI | reg «Para el informe»; plan §3.2 (06 y 09/11) | — |
| Nota «incomplete response» invisible | lab E4′.b2-b3 | — | La nota del fabricante no se ve en la burbuja | AI | reg «Para el informe»; plan §3.2 | — |
| Copiar y XLSX con tabla sin prosa | lab E4′.b2-b3 | — | Observación de exportación | AI | reg «Para el informe»; plan §3.2 | — |
| Carga de la sesión sin reintento (alias: resto 4 de PNS-94) | stE4 G (sesión 59) | — | Fallo de serialización al cargar la sesión tras un job | AI | stE4 G «Observaciones»; plan §3.2 (09/11); comp §5.6 punto 4 | — |
| Exportación del staging | stE4 G | — | Prosa y aviso antes de la tabla; solo `Name`; «Word» como `.doc` HTML | AI | stE4 G; plan §3.2 (09/11) | — |
| Escritura en la operación 27 | stg E1′ | — | Escritura sin causa ni efecto | AC (cerrada sin acción; 09/11) | verif E1′; diag R6 §6 y §7 | §2, fila 12 |
| Cancelación de todas las verificaciones pendientes | lab, validación de los scripts de E1′ | — | Un rechazo de escritura cancela todas las del usuario | AI (09/11) | seg «Observaciones sin ficha» | §2, fila 13 |
| `log_no_page` escribe en `ai_log` desde la caja A | lab E2′ (P-19j); hoja | — | Filas en cursor propio que el rollback no deshace | AI (defecto, junto a PNS-98; 09/11) | lab_e2 «Resultado (28/10/2026)»; hoja, nota de procedimiento | §2, fila 14 |
| Valores hostiles de portal en la página | lab p29 (apartado 3) | — | La regla de `account` no protege la ciudad ni la calle | CS (p27 a y p29: escape; lab 03/11; stg 04/11, 5c) | lab_p29 «Observaciones»; e3_hallazgo_p8ea §3.2 | Regla del core |
| Contraseña de `admin` en `pns_demo` | stE4 G | — | 5 caracteres en un staging accesible | SE | stE4 G; plan §4 | §2, fila 15. Entorno, no código |

## 4. Comprobación de marcadores

Grep de `Seges: parche N\b` (con límite de palabra, para no confundir el 1 con el 10 a 19) en `pns_base`,
`pns_ai_mcp` y `pns_ai_chatboo`, todos los tipos de archivo (`.py`, `.js` y `.xml`), sin las carpetas
`tests/`. Fuente del valor esperado: el registro (`reg`); para 23 y 24, también el staging de E2′.
Repetido en la segunda pasada para el total: patrón `Seges: parche (1[0-9]|2[0-9]|3[0-4])\b`, 159 líneas en
47 archivos, de ellas 17 en `tests/` (16 archivos): **142** fuera de tests.

| Parche | PNS / id | Esperado (registro) | Encontrado | Dónde | Resultado |
|---|---|---|---|---|---|
| 10 | PNS-83 | 2 (reg:879-880) | 2 | `models/key_pin_desk.py:193`; `models/mcp_user.py:766` | Cuadra |
| 11 | PNS-82 | 2 (reg:1222-1224) | 2 | `chatboo_session.py:2014, 2055` | Cuadra |
| 12 | PNS-01/02 | 10 (reg:880) | 10 | `ai_system_action.py` (6); `utils/privilege_cusp.py` (4) | Cuadra |
| 13 | M10 | 2 | 2 | `safe_operation.py:531, 1019` | Cuadra |
| 14 | M13 | 2 | 2 | `ai_context_disk.py:745, 758` | Cuadra |
| 15 | PNS-07 | 1 | 1 | `validators_base.py:255` | Cuadra |
| 16 | PNS-54 | 3 | 3 | `safe_operation.py:13, 1780, 2047` | Cuadra |
| 17 | PNS-37 | 5 (reg:1224) | 5 | `ai_change_journal.py` (4); `controllers/safe_plan.py:950` | Cuadra |
| 18 | PNS-19 | 7 | 7 | `box_a_guard.py:3`; `models/__init__.py:44`; `tools_relaxaicode.py:8, 188, 295`; `chatboo_session.py:18, 1229` | Cuadra |
| 19 | PNS-17 | 3 | 3 | `utils/fetch_url_safe.py:104, 115`; `utils/mcp_client.py:103` | Cuadra |
| 20 | PNS-70 | 4 | 4 | `chart.umd.min.js:1, 2`; `chatboo_heavy_libs.js:16, 31` | Cuadra |
| 21 | PNS-20 | 6 | 6 | `pns_base/models/operation_report_wizard.py:7, 293, 298, 320, 326, 332` | Cuadra |
| 22 | PNS-100 | 1 | 1 | `validators_base.py:286` | Cuadra |
| 23 | PNS-101 | **8** (reg:1224, anterior al parche 23 ampliado); 23 en stE2 G, B.4 | **23** | `context_builder.py` (11), `validators.py` (5), `validators_base.py` (3), `tools_relaxaicode.py` (2), `relaxaicode_format_guard.py` (1), `utils/skill_runtime.py` (1) | **No cuadra con el registro** (sí con el staging): SIN ESTADO CLARO, documental |
| 24 | PNS-102 | **sin dato** en el registro; 4 en stE2 G, B.4 | 4 | `context_builder.py:76, 117, 160, 551` | **Sin valor en el registro**: SIN ESTADO CLARO, documental |
| 25 | M1 | 5 (reg:2104-2106) | 5 | `chatboo_canvas.py:1023, 1048`; `chatboo_session.py:14, 1054, 1073` | Cuadra |
| 26 | M2 | 2 | 2 | `chatboo_canvas.py:1008`; `chatboo_session.py:924` | Cuadra |
| 27 | F1 | 13 | 13 | `chatboo_canvas.py` (11); `controllers/chatboo.py:1153, 1246` | Cuadra |
| 28 | D1 | 4 (una en XML) | 4 | `chatboo_canvas_page.py:19, 69, 87`; `security/security.xml:67` | Cuadra |
| 29 | F1 | 14 (reg:2812, 2825) | 14 | `chatboo_canvas.py` (9); `chatboo_session.py` (5) | Cuadra |
| 30 | M11 | 8 (reg:2869, 3085) | 8 | `ai_execution_engine.py:9, 160, 424, 464, 570, 630, 712, 790` | Cuadra |
| 31 | M12 | 1 | 1 | `ai_execution_engine.py:895` | Cuadra |
| 32 | PNS-97 | 5 | 5 | `ai_trusted_action.py:23, 83, 98, 104, 109` | Cuadra |
| 33 | PNS-29 | 3 | 3 | `ai_provider.py:1016, 1053`; `wizard/ai_provider_usage_wizard.py:37` | Cuadra |
| 34 | PNS-96 | 12 (reg:3410) | 12 | `chatboo_canvas.py:20, 29, 653, 661, 679`; `chatboo_async_request.py:12, 20, 143, 503, 1301, 1374, 1375` | Cuadra |
| **10 a 34** | — | 142 (stE4 G, B.4) | **142** | 25 parches | Cuadra con el staging de E4′ |
| **1 a 9** | PNS-81, 93, 94, 90, 91, 85 | 0 (retirados, reg «Cambio de base») | **0** | Patrones `Seges: parche [1-9]\b` y `Seges: parche de compatibilidad` (marcador de 1 a 6) | Retirados |

Recuento por suma de E1′ (20) + E2′ (55: 2, 5, 7, 3, 4, 6, 1, 23, 4) + E3′ (38) + E4′ (29) = 142, igual que la
comprobación B.4 de cada staging (75, 113 y 142).

## 5. Contradicciones entre documentos

| # | Tema | Qué dice cada uno | Efecto |
|---|---|---|---|
| 1 | Marcadores de los parches 23 y 24 | reg:1222-1226: «36 líneas (… 23: 8)», sin el 24. stE2 G, B.4: «75 marcadores; por parche 2, 5, 7, 3, 4, 6, 1, 23, 4». Código: 23 y 4 | El registro no se actualizó tras el parche 23 ampliado y el 24 (28/10) |
| 2 | Columna «Rama Seges» del seguimiento | seg tabla: PNS-17, 19, 20, 37, 82, 100 y 101 «aplicado; tests en verde (27/10)»; PNS-70 «P-70 pendiente»; PNS-102 «validación local»; PNS-30, 89, 92 y 97 «previsto en E4»; PNS-98 «fase posterior»; PNS-36 sin el cierre; PNS-29 y PNS-96 sin los parches 33 y 34; PNS-87 y 88 «E6», PNS-94 «E5» y PNS-50 «ET» (entregas del plan anterior). reg y plan §5: todos validados en staging (29/10, 04/11 y 09/11) | El seguimiento, base del informe, está desfasado desde el staging de E2′ |
| 3 | Gravedad de PNS-70 | seg tabla e inf. 15/10 y 16/10: Media. comp §5.4 y §5.6 y plan E2′: Alta desde el 23/10/2026 (decisión de Sergio) | Vale la última, Alta |
| 4 | Gravedad de PNS-18 | seg tabla e inf. 08/10: Alta. comp §1.3, §6.1 y §10.2: sin gravedad asignada | Sin decisión expresa; se usa Alta en §1 |
| 5 | Gravedad de PNS-37 | seg tabla: Media. comp §1.3 y §6.1: la parte de la papelera, Alta (propuesta) | Se usa Media para la fila; el resto Alta lo cierra el parche 17 |
| 6 | F4 frente a «HTML crudo en PDF/DOCX» | hoja ficha 12: F4, «método sin localizar»; plan §3.2 los lista por separado. reg «Para el informe» localiza el HTML crudo en `extractProseBlocks` (mensajes de una sola tabla, clases sin `_`), que es lo que describe F4 (comp §8.7) | Probablemente el mismo defecto: comunicarlo una vez |
| 7 | Lista del informe | plan §3.2 (05/11) remite a la hoja, «Candidatas al informe al fabricante», pero copia solo seis; las aceptadas (PNS-61, 84, M5, M16, hoja 17, 21 y 25) y la mayoría de los defectos (PNS-26, 88, 18, hoja 18, 28, 30 a 32, 35 y 36) solo están en la hoja, y de ellas solo PNS-84, M16 y la hoja 21 tienen decisión expresa | No hay una lista única del informe; 13 de esas entradas quedan en §2 bis |
| 8 | Numeración de `pns_base` | plan §3.2: va al informe «como observación». dec, «Decisiones del 23/10/2026»: no se pide al fabricante el commit de 1.2.47 | Compatibles solo si se comunica como observación, sin petición |
| 9 | PNS-96 | comp §6: VERIFICADO (enlaces con ids de la herramienta). seg PNS-96 (03/11) y reg «Parche 34»: el chat afirma cambios que no hizo, con el id PNS-96 | El «Resuelto» del fabricante cubre solo la parte de los enlaces |
| 10 | PNS-30 | comp §2.1: VERIFICADO. comp §1.1 y §8.7 (M11): su check sigue dando resultado por los `log_*` | Resuelto en la propia comp con una salvedad; lo cierra el parche 30 |
| 11 | PNS-02 (parte §7) | La auditoría alega que dar o quitar grupos pasa a exigir Ajustes. comp §7: NO CORREGIDO (prohíbe la cúspide a todos, no exige Ajustes) | Lo cubre el parche 12 con el criterio de Seges |
| 12 | U9 | Nota de versión del 20/10 de la auditoría: el `-u` ya no borra `agent_id`. comp §9.2 y §9.6 (P-9b): lo borra el core | Va al informe (plan §3.2) |
| 13 | Alcance del resto 3 de PNS-29 | hoja ficha 8: «cualquier interno». reg «Parche 33» (N33n) y plan §3.2: también portal | Errata ya anotada en el registro; vale la del registro |
| 14 | Estado de E4′ en el plan | plan §2, fila E4′: «E4′.h, pendiente» y «Validada en staging (09/11/2026)» en la misma celda; el párrafo «Estado del plan» del principio abre con «siguiente, E4′.h» | Registro acumulativo; vale lo último (validada el 09/11) |
| 15 | Envío del informe del 16/10 | `informe_fabricante_pns_ai_2.md` abre con «Borrador. Pendiente de revisión interna antes de su envío». La auditoría tiene fichas de PNS-93 a PNS-96 y de las observaciones 1, 5 y 8 a 11 de ese informe | El contenido llegó al fabricante; el documento no se actualizó |
| 16 | PNS-51 y D28 | inf. 15/10 §7.2 ya pide quitar `platform` (y el 16/10 lo da SIN CAMBIOS). dec D28: «Decisión: ____» (opción «Pedirlo» o «Aceptarlo») | La petición se hizo sin decisión registrada; el fabricante no respondió (sin ficha) |
| 17 | Gravedades nuevas en los informes | inf. 15/10 §1: PNS-81 a 92 con 4 Altas; inf. 16/10: 5 Altas con PNS-94. seg: Alta 6 con PNS-100; PNS-101 y 102, Críticas desde el 27/10 (no comunicados) | Sin conflicto; PNS-97 a PNS-102 y la nueva gravedad de PNS-70 aún no se han comunicado |

## 6. Lista AL INFORME, agrupada

Base para el informe; no es su redacción. Entre paréntesis, la fila de §3 y la fuente que lo pone en la
lista.

**A. Seguridad: corregido por Seges (sin código para el fabricante)**

- Críticas: M10 (p13 y p12); PNS-07 (p15); PNS-54 (p16; la opción c, aceptada con D29; anexo Bajo
  `missing_token`/`bad_token`); PNS-101 (p23 ampliado); PNS-102 (p24). Fuente: plan §3.2.
- Altas: M13 (p14); PNS-83, `collect_pin` (p10); PNS-70 (p20); PNS-100 (p22). Fuente: plan §3.2.
- Medias y Bajas: PNS-97 ampliado (p32); M11 (p30), que reabre el check de PNS-30; M12 (p31); PNS-29,
  resto 3 (p33, también portal). Fuente: plan §3.2.

**B. Seguridad: aceptado por Seges (se comunica el riesgo)**

- PNS-84 (PIN y clave legibles por el AI Administrator); M16 (queda el RPC); orden por un campo secreto
  (hoja 21). Decididas «aceptar» en la hoja; su inclusión en el informe sale de «Candidatas».

**C. Defectos del fabricante, sin parche**

- Datos y transacciones: PNS-98 (adjuntos huérfanos); carga de la sesión sin reintento (resto 4 de
  PNS-94). Fuente: plan §3.2.
- Lienzo y Chatboo: defecto de `keys` (hoja 27); el error del botón Canvas no se ve (sin tooltip en el
  staging); nota «incomplete response» invisible. Fuentes: plan §3.2 y reg «Para el informe».
- Exportación: F4 / HTML crudo en PDF y DOCX (§5, fila 6); copiar y XLSX con tabla sin prosa; prosa y
  aviso antes de la tabla, solo la columna `Name`, «Word» como `.doc` HTML. Fuente: plan §3.2.
- Skills y configuración: `customer_360._iso`, causa en `ensure_module_result_call` (hoja 22); casilla AI
  Conversational de Usuarios MCP (hoja 26; falta la reproducción, §2 fila 11). Fuente: plan §3.2.

**D. Actualización y paquete**

- U9: la nota de versión sobre `ai_log.agent_id` es falsa (confirmado en P-9b). Fuente: plan §3.2.
- Numeración de `pns_base` 1.2.47 frente a su contenido (observación, sin petición; §5 fila 8). Fuente:
  plan §3.2.

**E. Candidatos sin registrar (no son AL INFORME hasta que decida Sergio)**

- Corregidos por Seges que no figuran en plan §3.2 ni en la hoja: PNS-01/02 (criterio de grupos), PNS-17,
  PNS-19, PNS-20, PNS-36 (cerrado por el p23), PNS-37, PNS-82, M1, M2, F1 y D1.
- Restos del fabricante sin tratar: PNS-99, PNS-81 (degradación de Chatboo), PNS-51 (petición sin
  respuesta), la salvedad de PNS-28, la petición de §5 y los riesgos de §7 de PNS-23 y PNS-33 (§2).
- Observaciones del 16/10 sin respuesta: obs. 6, 7 y 13 (§2, filas 16 a 18); compatibilidad sin número
  (§2, fila 19).
- Cambios del `-u` no anunciados: U6, U11, U15 y U16 (comp §9.3 y §10.3).
- Observaciones de laboratorio sin valorar: cancelación de todas las verificaciones pendientes y
  `log_no_page` escribiendo en `ai_log` desde la caja A (§2, filas 13 y 14).

**F. Propuestas de la hoja al informe, sin decisión (§2 bis)**

- Aceptadas propuestas, para comunicar el riesgo: PNS-61 (observación), M5, reenvío de `params` y `data`
  (hoja 17), estado de la clave MCP que no se consulta (hoja 25), PNS-18 (la garantía de la casilla exige
  no tener externos activos; el «aceptar» sí está decidido, D10).
- Defectos propuestos: PNS-26 (resto, con el anexo de la serialización en `/execute`); PNS-88; caché del
  agente durante «Review» (hoja 18); nombre de la descarga (hoja 28); el chat afirma cambios que no hizo
  (PNS-96, hoja 30; Seges añade el aviso del parche 34); varias llamadas a Design (hoja 31); el
  orquestador reinterpreta peticiones (hoja 32); `relaxaicode` sin pedir datos (hoja 35); detalle del
  error en el failover (hoja 36).

**Alta del 12/11/2026**

- C, asistentes de importación: PNS-103 (Baja), un AI Administrator sin Ajustes no puede abrir la revisión ni
  el resultado de las importaciones (17 asistentes heredan los dos métodos). Seges lo corrige en 3.1.973
  (p36); en 3.1.879, sin parche. Fuentes: seg PNS-103; reg «Parche 36».
- Caja A: PNS-104 (Baja, propuesta, latente), cerrar la caja A descarta las escrituras pendientes del llamador (de
  cualquier modelo), sus cálculos pendientes y los registros `new()`. Mismo código en 3.1.879 y 3.1.973; sin parche
  (propuesta de `flush` en la 3b, como defensa). Fuentes: seg PNS-104; prop fase 3.
- Transacciones: PNS-105 (Alta, propuesta), los cursores propios con `commit` confirman, fuera de la transacción del
  llamador, sus escrituras pendientes, y pierden las de registros nuevos. Sin confirmar en ejecución; sin parche.
  Fuentes: seg PNS-105; prop fase 3.

## Cambios respecto a la primera pasada

- **Lecturas nuevas:** seg (tabla resumen y fichas PNS-50, 51 y 95 a 102, enteras); los tres informes
  comunicados (no solo cabeceras); las decisiones de Sergio de las propuestas de E1′, E2′ y E3′, enteras;
  plan §2 (tabla de E4′) y §3 punto 2; diag R6 entero.
- **Estados nuevos:** CF782 (33 filas que la primera pasada contaba como CF) y PSD (19 fichas de la hoja:
  10 que eran AC implícita y 9 que eran AI solo por la propia propuesta). CF queda solo para lo verificado
  en comp (82 filas; PNS-14 tiene CF y CF782).
- **Filas nuevas (4, total 186):** obs. 6, obs. 7 y obs. 13 del informe del 16/10 (sin ficha del
  fabricante) y la compatibilidad sin número del informe del 08/10. Las cuatro, SE.
- **Recuentos:** CS 33 → 33; CF 114 → 82 + CF782 33; AC 27 → 17; AI 43 → 29; PSD → 19; SE 15 → 19.
  Gravedades: Crítica 12, Alta 34, Media 36 y Baja 33, sin cambio; sin gravedad 67 → 71.
- **Sin estado claro resueltos:** ninguno de los 15. Aclarados: PNS-51 (pedido el 15/10, sin respuesta,
  sigue en el código), PNS-23 y PNS-33 (pedidos el 15/10), petición de §5 (pedida el 16/10), PNS-99
  (registrado como PNS el 26/10, no comunicado).
- **«A confirmar»:** las aceptaciones implícitas pasan a §2 bis; entran la revisión de los CF782, el
  alcance de «Candidatas», D28 y la cabecera «Borrador» del informe del 16/10.
- **Contradicciones nuevas:** §5, filas 15 a 17; la fila 2 suma las entregas del plan anterior (E4, E5,
  E6, ET) y la 7 se concreta con las decisiones.
- **Marcadores:** total repetido con Grep (142 fuera de tests); sin cambios en §4.
