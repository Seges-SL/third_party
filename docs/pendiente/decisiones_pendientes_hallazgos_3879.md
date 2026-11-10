# Decisiones pendientes del estado de los hallazgos (base 3.1.879)

- **Fecha:** 09/11/2026.
- **Para:** Sergio. Decide fila a fila. Después, un agente lo registra en los documentos (§5).
- **Origen:** `docs/specs/estado_hallazgos_3879.md` (§2 «Sin estado claro», 19 filas; §2 bis «Propuesta sin
  decisión», 19 filas; «A confirmar»; §5 «Contradicciones»).
- **Columna «3.1.973»:** lo que dice `docs/specs/comparacion_pns_ai_3-1-973.md` (sha256 `ad0ad4dc…`,
  verificada por `odoo-reviewer` en tres partes; pendiente de aplicar sus correcciones). Es un dato para
  decidir, no cambia la decisión sobre la base actual (3.1.879).
- **Decidido (Sergio, 09/11/2026):** todas las propuestas aceptadas (`OK`), salvo 2.13 y 3.5, retiradas por
  estar fuera del alcance (no se registran). Pendiente: registrarlas en los documentos (§5).

## 1. Una sola decisión: las propuestas de la hoja de E4′ (§2 bis, 19 fichas)

Las 19 fichas tienen propuesta en `e4_hoja_3879.md` y casi todas ya figuran en su lista «Candidatas al
informe al fabricante», pero a ninguna se le dio «Decidido». **Propuesta:** aprobar en bloque las 19 tal
como las propone la hoja **y** aprobar la lista «Candidatas» como la lista única del informe al
fabricante. Esto cierra también la contradicción 7 (no hay una lista única) y el punto «Lista Candidatas»
de «A confirmar».

| # | Ficha | Hallazgo | Propuesta de la hoja | 3.1.973 |
|---|---|---|---|---|
| 1.1 | 5 | PNS-61 (historial del navegador) | Aceptar; observación en el informe | Sin cambio |
| 1.2 | 9 | PNS-18 (failover externo) | Aceptar (D10); informe | Sin cambio; la alternativa de rol amplía los candidatos fuera de la cadena |
| 1.3 | 10 | PNS-26 resto y anexo | Informe | Sin cambio |
| 1.4 | 11 | PNS-88 (renombrados de 3.1.518) | Sin acción; informe | Sin cambio |
| 1.5 | 14 | M5 (`cron_maintenance` público) | Aceptar | Sin cambio |
| 1.6 | 16 | Tokens de portal | Sin acción; no va al informe | — |
| 1.7 | 17 | Reenvío de `params` y `data` | Aceptar; informe | Sin cambio; añade la comprobación contra el *rebinding* |
| 1.8 | 18 | Caché del agente en «Review» | Informe | Sin cambio |
| 1.9 | 19 | `onchange_email` y Gravatar | Aceptar; no va | — |
| 1.10 | 20 | `bus.presence.update` | Aceptar; no va | — |
| 1.11 | 23 | «Test Connection» escribe | Sin acción; no va | — |
| 1.12 | 25 | Autenticación MCP y estado de la clave | Sin acción; observación en el informe | Sin cambio |
| 1.13 | 28 | Nombre de la descarga del lienzo | Informe | Sin cambio |
| 1.14 | 30 | PNS-96, el chat afirma cambios que no hizo | Parche 34 (hecho) **y** informe | Sin cambio |
| 1.15 | 31 | Tres llamadas a Design por edición | Informe | Sin cambio |
| 1.16 | 32 | El orquestador reinterpreta ediciones | Informe | Sin dato |
| 1.17 | 35 | `relaxaicode` sin pedir datos | Informe | Sin dato |
| 1.18 | 36 | Detalle del error en el failover | Informe | Sin cambio localizado |
| 1.19 | 37 | El validador rechaza `dir()` | Sin acción; no va | Sin cambio localizado |

**Decisión (Sergio, 09/11/2026):** OK: las 19 como propone la hoja, y «Candidatas» como lista única del
informe.

## 2. Sin estado claro: decisiones una a una (§2 del estado)

Criterio que propongo, el de la decisión 2 de la hoja (bloque F): solo se parchea lo que (1) afecta a lo
que ve o hace un usuario, (2) agravan o hacen visible los parches de Seges y (3) es pequeño y testeable.
Lo demás, aceptar y, si es un defecto del fabricante, al informe.

| # | §2 | Hallazgo | Grav. | Qué hay que decidir | 3.1.973 | Propuesta | Decisión |
|---|---|---|---|---|---|---|---|
| 2.1 | 3 | PNS-99: `user.remove_group` da `executed` y el diario `applied` sin quitar el grupo (solo quita grupos directos) | Media | Parche, aceptar o informe | Sin cambio (P-16) | Aceptar e informe: no lo agrava ningún parche y solo afecta a planes del AI Administrator | OK |
| 2.2 | 4 | PNS-81 resto: la captura de skills no reconoce `env['ai.skill']` en Python 3.7 | Alta (sin efecto de seguridad) | Aceptar o informe | Corregido | Aceptar en 3.1.879 e informe como «corregido en 3.1.973»; si se elige el camino C, es candidato (unas 8 líneas) | OK |
| 2.3 | 5 | PNS-51: `platform` permitido en el sandbox (D28 sin decidir) | Baja | D28: aceptar o repetir la petición | Sin cambio | D28 = aceptar y repetir la petición en el informe | OK |
| 2.4 | 6 | PNS-23 («No se hará»): paquetes importados entran activos, `skill_skip_body_check`, skills sin `required_groups` | Alta | Aceptar el riesgo que queda o parchear | Sin cambio en la causa; acota el efecto (el código de las skills corre en la caja A) | Aceptar, con una regla en la guía de configuración: solo el AI Administrator importa paquetes de skills, y los revisa antes; informe | OK |
| 2.5 | 7 | PNS-33 resto: `set_mcp_api_key` acepta una clave elegida o un hash ya calculado | Media | Aceptar o parchear | Sin cambio (solo endurece la clave de los administradores de Ajustes, NUEVO-3) | Aceptar (las claves se generan con el asistente, N4) e informe | OK |
| 2.6 | 8 | PNS-28 salvedad: en 14 el `OPTIONS` lo contesta el core | Media | Informe o descartar | Sin cambio (no depende del módulo) | Observación en el informe; no hacer P-28 | OK |
| 2.7 | 9 | Petición de §5: el prompt que recibe el modelo no se guarda en `ai.log` | — | Repetir o descartar | Sin cambio localizado | Repetir la petición en el informe | OK |
| 2.8 | 10 | U11: agente «Decision» huérfano tras el `-u` | — | Informe o descartar; hacer P-9d o no | Sin cambio | Informe sin prueba (no hacer P-9d) | OK |
| 2.9 | 11 | Ficha 26, casilla AI Conversational: la reproducción de la decisión 5 no consta hecha | — | Hacer la reproducción antes del informe o enviarlo sin ella | AI Administrator implica AI Conversational: la reproducción tiene que hacerse con un usuario que **no** sea AI Administrator | Hacer la reproducción en el laboratorio (shell y `rollback`, decisión 5) con un usuario no AI Administrator, antes del informe | OK |
| 2.10 | 12 | Escritura sin causa en la operación 27 (staging E1′) | — | Investigar o cerrar | — | Cerrar sin acción: sin efecto y sin causa en el código | OK |
| 2.11 | 13 | Un rechazo de `relaxaicode` sin AI Writer cancela todas las verificaciones pendientes del usuario | — | Parche, aceptar o informe | Sin cambio localizado | Informe (defecto del fabricante; no cumple el criterio del bloque F) | OK |
| 2.12 | 14 | `log_no_page` escribe en `ai_log` en cursor propio desde la caja A | — | ¿Es un defecto? | Sin cambio | Sí: escritura fuera de la caja A de solo lectura. Al informe, junto a PNS-98; sin parche | OK |
| 2.13 | 15 | Contraseña de `admin` de `pns_demo` (5 caracteres) | — | Cuándo cambiarla | — | Cambiarla ya (es un staging publicado en internet) | Retirada (fuera de alcance) |
| 2.14 | 16 | Obs. 6: adjuntos de `session_download` sin la marca de exportación (fuera de la purga de 24 h) | — | Repetir o descartar | Sin cambio | Repetir en el informe | OK |
| 2.15 | 17 | Obs. 7: `_fx_payload` devuelve `str(exc)` | — | Repetir o descartar | Sin cambio | Repetir en el informe | OK |
| 2.16 | 18 | Obs. 13: tests que cambian la clave del administrador | — | Repetir o descartar | Sin cambio localizado (los tests ya no confirman en cursor aparte) | Repetir solo si sigue en la versión que se tome como base | OK |
| 2.17 | 19 | Compatibilidad sin número (inf. 08/10 §7.1 a §7.4 y §8.5) | — | Cerrar o citar | 3.1.973 ya no trae `migrations/` | Cerrar: §7.1 ya no aplica y §7.4 está corregido; §7.3 va con PNS-81; §7.2 y §8.5 se dan por cerrados (el fabricante migra en `init()`) | OK |

Las filas 1 y 2 del §2 (recuentos de marcadores de los parches 23 y 24) son documentales: §4.

## 3. «A confirmar» y contradicciones que piden decisión

| # | Tema | Qué hay que decidir | Propuesta | Decisión |
|---|---|---|---|---|
| 3.1 | CF782: 33 filas corregidas en 3.1.782 y no revisadas en 3.1.879 | Si se revisan antes del informe | La comparación con 3.1.973 (§3.2) ya revisó en nuestra copia las 20 Críticas y Altas: 19 siguen corregidas y PNS-80 no aplica. Quedan 13 Medias y Bajas: una lectura dirigida de solo lectura antes de cerrar el informe | OK |
| 3.2 | Resto de PNS-83: `close` y `notify_changed` de la mesa del PIN siguen públicos | Aceptar o informe | Aceptar (mesa sin uso, N4) e informe; 3.1.973 ya hace privado `_close` | OK |
| 3.3 | Pruebas de la comparación de 3.1.879 sin registro de ejecución (P-60, P-40, PNS-32 con dos workers, PNS-95/46, PB-2 con `web_*` de OCA) | Hacerlas o dar el hallazgo por CF por el código | Dejarlas como CF por código; no bloquean el informe | OK |
| 3.4 | Decisiones abiertas en `dec`: D9 y PB-2 (bloqueantes vigentes), D22 | Decidirlas ahora o aparte | Aparte: no son estados de hallazgo (D28 va en la fila 2.3) | OK |
| 3.5 | Informe del 16/10 con la cabecera «Borrador» | ¿Se envió? ¿En qué fecha? | Si se envió, cambiar la cabecera a «Enviado el …» (contradicción 15) | Retirada (fuera de alcance) |
| 3.6 | Contradicción 4: gravedad de PNS-18 | Alta o sin gravedad | Alta (la del informe del 08/10) | OK |
| 3.7 | Contradicción 6: F4 y «HTML crudo en PDF/DOCX» | ¿Mismo defecto? | Sí: comunicarlo una vez, con la localización del registro (`extractProseBlocks`) | OK |
| 3.8 | Contradicción 8: numeración de `pns_base` | Observación o nada | Nada: con 3.1.973 la numeración queda explicada (etiqueta `owl1`) | OK |
| 3.9 | Contradicción 9: PNS-96 | Cómo comunicarlo | En el informe, aclarar que su «Resuelto» cubre solo los enlaces, no el chat que afirma cambios | OK |

## 4. Documental, sin decisión (lo registra el agente)

- Registro de parches: recuentos de marcadores del parche 23 (23) y del 24 (4), como en el staging de E2′
  (§2 filas 1 y 2; contradicción 1).
- `seguimiento_informe_pns_ai.md` desfasado desde E2′ (contradicción 2): **propuesta**, no actualizarlo;
  dejar una nota en su cabecera que remita a `estado_hallazgos_3879.md` como base del informe.
- Gravedad de PNS-70: Alta (contradicción 3). Alcance del resto 3 de PNS-29: el del registro
  (contradicción 13). Estado de E4′ en el plan: validada el 09/11 (contradicción 14).

## 5. Después de decidir

Un agente (`odoo-architect`, solo documentos) registra las decisiones:
- en `estado_hallazgos_3879.md`: el estado nuevo de cada fila;
- en `e4_hoja_3879.md`: «Decidido» en las fichas de §1;
- en `pns_ai_decisiones.md`: D28 y lo que se decida en §3;
- en `plan_correccion_pns_ai_3879.md` §3.2: la lista única del informe;
- en `parches_pns_ai.md`: los recuentos de §4;
- y guarda esta hoja con las decisiones en `docs/pendiente/`.

Commit `[DOC]` de Sergio.
