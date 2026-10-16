# Análisis: bloqueo de `chatboo_session` tras un turno con imagen (pns_ai_chatboo 2.1.453 / pns_ai_mcp 3.1.782, Odoo 14)

- Fecha: 16/10/2026. Análisis estático, SOLO LECTURA (no se ha escrito en ninguna BD).
- **Estado: Aplicado (corrección 1a, parche 6), pendiente de validar en staging.** Ver
  [parches_pns_ai.md](parches_pns_ai.md), «Parche 6», y la validación en §5.1.
- Observado en staging (2 workers, `limit_time_real` 900 s, PostgreSQL 15), sesión id 9.
- Síntoma: el turno termina (`ai_log` «Turn completed»), pero el navegador sigue esperando el fin.
  En `pg_stat_activity`:
  - **A**: «idle in transaction», última consulta un `SELECT` sobre `chatboo_async_request`;
  - **B**: esperando un lock `transactionid` en `UPDATE chatboo_session SET input_history=…`;
  - recargas posteriores en cola: `UPDATE chatboo_session SET last_used_date=… WHERE id IN (9)`,
    una por worker, hasta dejar Odoo sin servicio. Se resolvió reiniciando.
- Datos añadidos por el usuario: se reproduce siempre al adjuntar una imagen, también cuando el
  proveedor devuelve 429 (el turno falla); los turnos de solo texto no lo provocan; los bloqueos
  superan los 900 s y no se liberan solos.

## Resumen

Es un **interbloqueo dentro de un mismo hilo de Python que PostgreSQL no puede detectar**.
El turno se ejecuta en un `threading.Thread` lanzado desde el worker HTTP, con un cursor propio
(**A**) que mantiene la transacción abierta durante todo el turno. Al terminar, `_finalize`
abre **en el mismo hilo** un segundo cursor (**B**) y escribe la misma fila de `chatboo_session`.
Si A tiene un lock sobre esa fila, B espera a A. A no terminará nunca, porque el único código que
la cerraría (el `rollback` del `finally` de `_process`) se ejecuta en ese mismo hilo, que está
bloqueado esperando a B. Para PostgreSQL no hay ciclo (B espera a A, y A no espera a nadie: está
«idle in transaction»), así que el detector de interbloqueos no actúa. Ningún límite de Odoo
afecta a un hilo de fondo, así que la situación dura hasta que muere el proceso que lo aloja.

Los pasos de A y B encajan con lo observado: A queda «idle in transaction» después de leer
`chatboo_async_request`, y B se queda en el `UPDATE … input_history` de `_save_to_session`. Como B
nunca hace commit, el job no pasa a `done`, el tail SSE no envía `done` y el navegador sigue
esperando. Cada recarga ejecuta `update_last_used()` sobre la misma fila sin `lock_timeout`, y
se queda encolada ocupando un worker.

El mecanismo está confirmado en el código. Lo que **no se ha podido fijar solo leyendo código**
es qué sentencia concreta deja el lock de la fila 9 en A cuando el turno lleva imagen; hay dos
hipótesis (§2.3) y una prueba en staging que las distingue (§5.1).

## 1. Recorrido de un turno con adjunto

### 1.1 Rutas HTTP (`pns_ai_chatboo/controllers/chatboo.py`)

No hay una ruta de subida separada: las imágenes (`images`, `image_names`) y los ficheros
(`files`) viajan como data URL dentro del JSON de `/chatboo/stream`.

| Paso | Referencia |
|---|---|
| Ruta `/chatboo/stream` (`type='http'`, POST) | `chatboo.py:717-916` |
| Lectura de `images`/`image_names`/`files` del cuerpo | `chatboo.py:740-742` |
| Sesión: `browse` o `create`; `remember_marks` (escribe la sesión si llegan `refs`) | `chatboo.py:754-766` |
| Límite de tamaño de adjuntos | `chatboo.py:770-787` |
| `_enqueue` (crea el job `pending` con las imágenes en JSON) | `chatboo.py:818-823` |
| `request.env.cr.commit()` y `job._spawn()` | `chatboo.py:824-825` |
| Tail SSE: bucle con `registry.cursor()` nuevo en cada vuelta, `SELECT` del job, `time.sleep(0.3)`, tope de 600 s | `chatboo.py:833-911` (cursor 854, tope 839, sleep 911) |
| Al ver `done`/`error`: `UPDATE chatboo_async_request SET seen=true` | `chatboo.py:896-902` |
| `/chatboo/sessions/load` → `update_last_used()` (las recargas en cola) | `chatboo.py:276-299` (línea 286) |
| `/chatboo/sessions/save` → `set_input_history` + `update_last_used` | `chatboo.py:343-377` (370, 373) |
| `/chatboo/async/poll` → `_reclaim_stuck(minutes=1)` con `statement_timeout` de 3 s | `chatboo.py:467-524` (482-484) |
| `/chatboo/async/cancel` | `chatboo.py:526-550` |

### 1.2 `chatboo.async.request` (`pns_ai_chatboo/models/chatboo_async_request.py`)

| Paso | Referencia | Cursor |
|---|---|---|
| Creación: `_enqueue` | `:227-250` | petición HTTP |
| `_spawn`: `threading.Thread(daemon=True)`, `with db_registry.cursor() as cr`, `api.Environment(cr, uid, context)` y `_process()` | `:252-303` (cursor 280-282, hilo 300-303) | **A** |
| `_process`: `state='running'` + commit | `:349-350` | A |
| Escrituras en la sesión antes del motor: modo de presentación (`:395`, `:397`, `:402`), marcas (`:476-482`), documentos (`:492-501`) | | A (perezosas, ver §2.2) |
| **Solo con imagen:** `_image_documents()` → `_transcribe_pages()` → `ai.execution.engine.chat_completion(images=…)`, una llamada de visión adicional | `:492` → `:1408-1442` → `:1361-1405` (llamada en `:1389`) | A |
| Commit de las escrituras de sesión; si falla, solo se registra y el turno sigue | `:507-519` | A |
| Recuerdo de imágenes previas (solo en turnos **sin** imagen) | `:531` | A |
| Hilo de latido (`UPDATE … write_date` cada 10 s, cursor propio) | `:537`, `:728-757` | propio |
| **Escritura en la sesión después del commit**: `session.sudo().write({'last_screen_context': …})` | `:556-562` | **A** |
| Motor: `AgentEngine(engine_env)` con `engine_env = self.env(context=…)`, que usa el mismo cursor A | `:579-617` | A |
| Progreso (`_flush_progress`) y cancelación (`_is_cancel_requested`), cada uno con cursor propio | `:772-787`, `:1993-2005` | propios |
| Parar el latido y `_finalize` (éxito, `:697`; excepción, `:712`) | `:692-712` | — |
| `finally`: `self.env.cr.rollback()` de A (**nunca se alcanza si `_finalize` se bloquea**) | `:713-726` | A |
| `_finalize`: `with _get_registry(dbname).cursor() as cr` → `job.write(vals)` → `_save_to_session` → `cr.commit()` | `:835-918` (cursor 885-887, commit 916) | **B** |
| `_save_to_session`: `_persist_turn_images` (crea `ir.attachment` con `res_id` = sesión), `_persist_turn_files` | `:1648`, `:1651`, `:959-1009` | B |
| `_save_to_session`: **escribe `input_history`** | `:1715-1728` (línea 1723) | B |
| Cierre forzado de jobs colgados: `_reclaim_stuck` (cron y poll) | `:2009-2131` | cron / poll |
| GC de jobs terminados | `:2133-2141` | cron |

### 1.3 Dónde se escriben `input_history` y `last_used_date` (`pns_ai_chatboo/models/chatboo_session.py`)

- `set_input_history`: `chatboo_session.py:650-665`. La llaman `_save_to_session`
  (`chatboo_async_request.py:1723`, cursor B) y `save_session` (`chatboo.py:370`).
- `update_last_used`: `chatboo_session.py:670-672`. La llaman `load_session` (`chatboo.py:286`)
  y `save_session` (`chatboo.py:373`).
- `append_local_ack` también escribe `last_used_date` (`chatboo_session.py:613`).
- Ninguna usa `lock_timeout`, `NOWAIT` ni `SKIP LOCKED`.

## 2. Cursores nuevos y mecanismo del bloqueo

### 2.1 Cursores que abre un turno

En el hilo del worker conviven:

- **A**: el cursor del hilo (`chatboo_async_request.py:280`), con la transacción abierta desde el
  commit de `:514` hasta el `rollback` de `:724`. Todo el motor usa A.
- **B**: el de `_finalize` (`:886`), en el mismo hilo, mientras A sigue abierta. Escribe el job
  y la sesión (`input_history`, `messages`, adjuntos…).
- Cursores cortos, solo con SQL crudo: latido (`:744`), progreso (`:779`), cancelación
  (`:1996`), `_job_already_finished` (`:102`).
- Cursores cortos con ORM dentro del motor (pns_ai_mcp): `ai_log.py:706` (cada entrada del
  histórico), `session_download.py:390` (descargas), `safe_plan.py:2143/2237`,
  `field_required_plan.py:248`, `ai_skill_param_cache.py:143`, `ai_change_journal.py:360`.
  Otros sí se protegen con `SET LOCAL lock_timeout = '2s'` (`ai_provider.py:1063-1065`,
  `ai_context.py:1222-1223`), así que el fabricante ya conoce el patrón. `_finalize` no lo aplica.

El propio fabricante describe la colisión A/B en el comentario de `chatboo_async_request.py:507-511`
(«Finalize writes the same session row on a fresh cursor. The two updates collide»). Su solución
fue el commit de `:514`. Esa solución es incompleta por dos motivos:
1. cualquier escritura en la sesión por A **después** de ese commit vuelve a crear el problema
   (la de `:556-562` es una);
2. si el commit de `:514` falla, la excepción se registra y el turno continúa con la transacción
   de A abierta y sus locks puestos (`:515-519`).

### 2.2 Particularidades de Odoo 14 que intervienen

- **Escrituras perezosas.** `write()` deja los valores en `env.all.towrite`. El `UPDATE` solo se
  ejecuta en un *flush*: commit (`odoo/sql_db.py:449-457` → `flush_env`, `:65-80`), un
  `cr.savepoint()` con `flush=True` (`sql_db.py:115-121`, que vacía **todo** lo pendiente antes del
  `SAVEPOINT`, así que el `UPDATE` queda en la transacción principal aunque luego se deshaga el
  savepoint), búsquedas sobre ese modelo o un `flush()` explícito.
- **Caché y `towrite` compartidos entre cursores del mismo hilo.** En Odoo 14, todos los
  `Environment` creados dentro del mismo `Environment.manage()` comparten `cache` y `all`
  (`odoo/api.py:472-475`). Las escrituras pendientes hechas con A pueden acabar ejecutándose con
  otro cursor del mismo hilo (B, o el de `ai_log`) y al revés, según quién haga antes el flush.
  Por eso, qué cursor acaba ejecutando el `UPDATE chatboo_session` depende del orden de los flush,
  que cambia según el camino que siga el turno.
- **`commit()` vacía la caché** (`flush_env(clear=True)`). Por eso, después de `:514`, cualquier
  acceso a un campo del job (por ejemplo `self.agent_code`/`self.provider_id` en el log de
  `:686-689`) relanza un `SELECT … FROM chatboo_async_request` por A. Eso explica que la última
  consulta de A sea un `SELECT` sobre esa tabla.

### 2.3 ¿Produce el bloqueo observado? ¿Por qué solo con imágenes?

**Sí, el mecanismo produce exactamente lo observado** si A tiene un lock de fila sobre
`chatboo_session` id 9 cuando se llama a `_finalize`:

1. A ejecuta un `UPDATE chatboo_session … WHERE id = 9` (directo o en un flush) y no hace commit.
2. A lee el job (`SELECT … chatboo_async_request`) y queda «idle in transaction».
3. `_finalize` abre B en el mismo hilo; `_save_to_session` lanza
   `UPDATE chatboo_session SET input_history=…` → espera el `transactionid` de A.
4. A no se cerrará: su `rollback` (`:724`) está después de `_finalize` en el mismo hilo.
5. El job nunca llega a `done` (el `job.write(vals)` está en B, `:889`, y su commit en `:916`),
   así que el tail SSE (`chatboo.py:882`) no envía `done`: el navegador sigue esperando.
6. Cada recarga hace `load_session` → `update_last_used()` → `UPDATE … last_used_date … WHERE
   id IN (9)`, que se encola detrás de A sin límite de espera.

Con un 429 también ocurre porque el motor no lanza la excepción: emite eventos `error` y se
llama igualmente a `_finalize(… error=…)` (`:697` o `:712`), que escribe `input_history` igual
(`:1715-1728`).

**Qué cambia con una imagen** (diferencias de código entre un turno de texto y uno con imagen):

- Antes del commit de `:514` se hace una **llamada de visión adicional** con el cursor A
  (`_image_documents` → `_transcribe_pages`, `:1389`), con su cascada de proveedores y sus
  failovers (con 429 se recorren todos). Por el camino se crean entradas de `ai_log` con un
  cursor ORM propio en el mismo hilo (`ai_log.py:706-837`).
- El motor resuelve la cadena con `need='vision'` y monta un mensaje multimodal
  (`agent_engine.py:2300`, `:2815-2830`), así que puede seguir otro camino de proveedores y de logs.
- No se ejecuta `_recall_prior_images()` (`:531`), que en los turnos de texto hace un `search`
  sobre `ir.attachment` con A.
- En B, `_persist_turn_images` crea `ir.attachment` ligados a la sesión antes de escribir
  `input_history` (`:1648`).

Hipótesis sobre cómo queda el lock en A (no se distinguen solo leyendo el código):

- **H1 (la más probable):** la escritura perezosa de `last_screen_context` por A después del
  commit (`:556-562`, se ejecuta siempre que el cliente envía `screen_context`) llega a SQL **por
  el cursor A** en un flush durante el motor. En un turno de texto, ese pendiente lo vacía antes
  otro cursor del mismo hilo (por ejemplo, el commit de una entrada de `ai_log`, gracias al
  `towrite` compartido) o B: el `UPDATE` sale por un cursor que hace commit y no hay bloqueo. Con
  imagen, el camino de visión cambia el orden de los flush y el pendiente sale por A. Cualquier
  `cr.savepoint()` sobre A durante el motor (`ai_skill.py:488`, `ai_context.py:1735`,
  `safe_operation.py:1649`) o un flush completo bastan para provocarlo.
- **H2:** el commit de `:514` falla durante el flush, después de haber ejecutado ya el
  `UPDATE chatboo_session` de las escrituras previas (marcas, documentos, modo de presentación).
  La excepción se traga (`:515-519`) y A sigue abierta con el lock puesto durante todo el turno.
  Si fuera así, el log mostraría «Chatboo async job N: could not commit the session writes».

**Dato nuevo (16/10/2026):** en los logs de Odoo de los dos incidentes de staging no aparece
ningún «could not commit the session writes». **H2 queda descartada y H1 es la hipótesis de
trabajo.** La corrección 1a (§5.2) no depende de cuál sea la sentencia exacta: el `rollback` de A
antes de `_finalize` libera cualquier lock que A tenga, venga de donde venga.

Las dos hipótesis tienen la misma causa de fondo y la misma corrección (§5.2). La prueba de §5.1
dice cuál es: `log_statement='mod'` muestra qué `UPDATE chatboo_session` ejecutó el PID de A, y
`py-spy dump` muestra el hilo `chatboo-async-<id>` parado dentro de `_finalize`.

## 3. `FOR UPDATE`, escrituras previas y esperas activas

- **`SELECT … FOR UPDATE` sobre `chatboo_session`: no hay ninguno.** Los `FOR UPDATE` del módulo
  son sobre `chatboo_async_request` y con `SKIP LOCKED` (`chatboo_async_request.py:2047-2053`).
- **Escrituras previas sobre `chatboo_session` en la petición HTTP:** `remember_marks`
  (`chatboo.py:766`, solo si llegan `refs`) y el `create` de la sesión (`:761`). Se confirman con
  el commit de `chatboo.py:824` antes de lanzar el hilo, así que **no** forman parte del bloqueo.
  En el hilo: las de `chatboo_async_request.py:395-501` (antes del commit de `:514`) y la de
  `:556-562` (después).
- **Esperas activas que mantienen una transacción abierta:**
  - Tail SSE (`chatboo.py:846-911`): bucle con `sleep(0.3)` hasta 600 s. Abre y cierra un cursor
    por vuelta, así que **no** retiene ninguna transacción, pero **ocupa un worker HTTP** hasta
    10 min por pestaña.
  - El hilo del worker mantiene A abierta durante **toda la inferencia** (minutos, por diseño;
    lo dice el comentario de `:716-721`). Ese es el problema de fondo.
  - `_stop_heartbeat` hace `join` hasta 12 s (`:759-770`): acotado, no bloquea.
  - En pns_ai_mcp hay esperas con `sleep` (`key_pin_desk.py:190`, `controllers/safe_operation.py:112`)
    que no intervienen en este caso.
- **Esperas sin límite sobre la fila de sesión:** `update_last_used` (`chatboo.py:286`, `:373`),
  `set_input_history` (`chatboo.py:370`; `chatboo_async_request.py:1723`) y el resto de escrituras
  de las rutas de sesión (`rename`, `delete`…). Solo `_reclaim_stuck` acota su espera
  (`statement_timeout`, `:2083-2089`).

## 4. Impacto

- **Disponibilidad.**
  - El hilo bloqueado y sus dos conexiones (A y B) **no tienen límite de tiempo**:
    `limit_time_real` solo lo aplica el proceso maestro al bucle principal de cada worker
    (`odoo/service/server.py:779-787`, latido en `:1015-1016`). Un hilo daemon no tiene
    watchdog, y el worker que lo aloja sigue latiendo con normalidad mientras está libre.
  - Cada recarga del usuario ocupa un worker en `UPDATE … last_used_date`. Pasados 900 s, el
    maestro mata ese worker con SIGKILL y lanza otro, pero **el backend de PostgreSQL que esperaba
    el lock sigue en `pg_stat_activity`**: mientras espera un lock no comprueba si el cliente sigue
    conectado (`client_connection_check_interval` vale 0 por defecto en PG 15). Por eso se ven
    transacciones de más de 900 s que «no se liberan solas».
  - El lock solo se libera si muere el proceso que aloja el hilo (SIGKILL del watchdog porque ese
    mismo worker se bloqueó en otra petición, `limit_memory_*`, `limit_request` o un reinicio).
    Con mala suerte, eso no pasa nunca.
  - Con 2 workers bastan dos recargas, o una recarga y una pestaña con el tail SSE (hasta 600 s),
    para dejar Odoo sin servicio HTTP.
- **Otros usuarios.** La fila bloqueada es la sesión del propio usuario (`chatboo_session.user_id`),
  así que otros usuarios no esperan ese lock. Pero sí se quedan sin servicio cuando los workers
  están ocupados. Además, cada incidente deja conexiones abiertas (A, B y los backends huérfanos):
  con varios incidentes se puede agotar `db_maxconn` o `max_connections` de PostgreSQL, que puede
  ser compartido con otras BD del mismo servidor.
- **Cron.** `cron_maintenance` → `_reclaim_stuck` acota su espera con `statement_timeout` (8 s por
  defecto), así que no se cuelga. Pero cuando el latido se para, el job parece muerto; el reclaim
  falla una y otra vez sobre la misma fila y lo marca con el SQL de último recurso (`:2108-2131`).
- **¿Puede provocarlo a voluntad un usuario sin privilegios?** **Sí.** Basta con acceso a Chatboo:
  grupo conversacional y clave MCP propia (`pns_ai_chatboo/utils/chatboo_access.py:7-29`), sin
  permisos de administración. Según las observaciones se reproduce siempre al adjuntar una imagen
  (ni siquiera hace falta que el proveedor responda), y luego basta con recargar varias veces.
  Puede pasar sin querer en el uso normal, y también se puede provocar a propósito: es una
  **denegación de servicio a disposición de cualquier usuario de Chatboo**. Gravedad
  propuesta: **alta**.

## 5. Reproducción controlada y corrección sugerida

### 5.1 Reproducción en staging (sin datos sensibles; la decide el usuario)

Preparación (en la BD de staging, por quien administra el VPS):
1. Activar en PostgreSQL, solo durante la prueba: `log_lock_waits = on`, `deadlock_timeout = 1s`
   y `log_statement = 'mod'` (o `log_min_duration_statement = 0`) para la BD de staging.
2. Tener a mano `py-spy` en el contenedor de Odoo (`py-spy dump --pid <pid>` es solo lectura).
3. Usar un usuario de pruebas con acceso a Chatboo y una sesión nueva. Para no depender de la
   cuota del proveedor, sirve un proveedor que devuelva 429 o un endpoint inexistente: según las
   observaciones, el bloqueo se produce igual.

Pasos:
1. Abrir Chatboo, adjuntar una imagen PNG pequeña y enviar «¿qué ves?».
2. Comprobar con esta consulta (solo lectura):
   ```sql
   SELECT pid, state, xact_start, wait_event_type, wait_event,
          pg_blocking_pids(pid) AS bloqueado_por, left(query, 120) AS query
     FROM pg_stat_activity
    WHERE datname = current_database() AND state <> 'idle'
    ORDER BY xact_start;
   ```
   Lo esperado: B con `wait_event = transactionid` y `bloqueado_por = {pid de A}`; A
   «idle in transaction».
3. En el log de PostgreSQL, buscar el `UPDATE chatboo_session` ejecutado por el PID de A (eso
   decide entre H1 y H2). En el log de Odoo, buscar «could not commit the session writes» (H2).
4. Localizar el proceso de Odoo dueño de A (`client_port` de A → `ss -tnp | grep <puerto>`) y
   ejecutar `py-spy dump --pid <pid>`. Lo esperado: el hilo `chatboo-async-<id>` parado en
   `_finalize` (`chatboo_async_request.py:886-916`) dentro de `cursor.execute`.
5. Repetir con el mismo mensaje sin imagen (y con y sin `screen_context`) para confirmar que no
   se bloquea.
6. Liberar sin reiniciar: `SELECT pg_terminate_backend(<pid de A>);`. Es una acción de
   administración sobre la BD de staging y la decide el usuario. B debería terminar enseguida y
   el turno aparecer en la sesión.
7. Devolver la configuración de PostgreSQL a su estado anterior.

No hace falta probar la saturación de workers (recargas repetidas): ya está observada y deja
staging sin servicio.

#### Validación del parche 6

Se hace en staging tras actualizar `pns_ai_chatboo` con el parche 6 (lo decide y lo ejecuta quien
administra el VPS). Preparación:
- la misma configuración temporal de PostgreSQL que la reproducción (`log_lock_waits`,
  `deadlock_timeout = 1s`, `log_statement = 'mod'`);
- un usuario de pruebas con acceso a Chatboo y una sesión nueva para cada caso.

Casos:

| # | Caso | Cómo |
|---|---|---|
| 1 | Turno con imagen y proveedor que responde | adjuntar un PNG pequeño, «¿qué ves?», con un proveedor con cuota y visión |
| 2 | Turno con imagen y proveedor con 429 | lo mismo, con un proveedor sin cuota (o que devuelva 429) |
| 3 | Turno de solo texto | un mensaje sin adjuntos, desde una pantalla de Odoo (con `screen_context`) |
| 4 | Cancelación de un turno en curso | un turno largo (con imagen y proveedor que responde), y pulsar «detener» mientras genera |
| 5 | Turno siguiente al de la imagen | justo después del caso 1, en la misma sesión, un mensaje de texto que aluda a la pantalla actual |

Comprobaciones en cada caso:
1. **El navegador recibe el fin del turno:** desaparece el indicador de espera y se ve la respuesta,
   el error del proveedor (caso 2) o «⏹ Generation cancelled.» (caso 4). Sin recargar.
2. **Ninguna conexión colgada.** Con la consulta del paso 2 de la reproducción, ejecutada unos
   segundos después del fin del turno, no deben aparecer:
   - conexiones `idle in transaction` del worker que llevaba el turno;
   - conexiones con `wait_event_type = 'Lock'` o con `bloqueado_por` no vacío.

   En el log de PostgreSQL no debe haber `still waiting for ShareLock on transaction` sobre
   `chatboo_session`.
3. **La sesión guarda el turno.** Al recargar la página y abrir la sesión, se ven el mensaje del
   usuario (con la miniatura de la imagen en los casos 1, 2 y 4) y la respuesta o el error. El
   texto enviado aparece en el historial de entrada (flecha arriba en el cuadro de mensaje). Desde
   la BD (solo lectura):
   ```sql
   SELECT id, state, finished_at, left(error, 80) AS error
     FROM chatboo_async_request WHERE session_id = <id de la sesión> ORDER BY id;
   SELECT id, last_used_date, length(messages) AS messages, length(input_history) AS input_history,
          left(last_screen_context, 80) AS last_screen_context
     FROM chatboo_session WHERE id = <id de la sesión>;
   ```
   El job debe estar en `done` (casos 1, 3, 4 y 5) o en `error` (caso 2), con `finished_at`, y
   `messages` e `input_history` deben haber crecido respecto al turno anterior (anotar los valores
   antes de cada caso).
4. **Log de Odoo limpio.** Durante el turno no debe aparecer ninguna de estas trazas:
   - «could not roll back the worker cursor»;
   - `MissingError`;
   - «_finalize fresh-cursor failed», «_finalize raw fallback failed» o
     «failed to persist turn to session»;
   - «could not commit the session writes».
5. **Solo en el caso 5:** el turno funciona igual que los demás (comprobaciones 1 a 4) y la
   respuesta usa el contexto de pantalla:
   - en el log, «screen_context enriched (N chars)» para ese job;
   - la respuesta se refiere a la pantalla actual y no a la del turno con imagen.

   Si el cliente no enviara `screen_context`, el motor usaría `last_screen_context` de la sesión,
   que puede ser el del turno anterior al de la imagen (degradación conocida del parche 6). En ese
   caso, anotar qué pantalla usa.

Si algún caso con imagen sigue dejando una conexión esperando lock, se ha dado el riesgo residual
del parche 6: el lock lo tiene otro cursor del hilo, no A. Hay que identificar el PID con
`pg_blocking_pids`, ejecutar `py-spy dump` (paso 4 de la reproducción) y liberar con el paso 6.
Al terminar, devolver la configuración de PostgreSQL a su estado anterior.

### 5.2 Corrección que sugeriríamos al fabricante

Por orden de importancia. La 1a está aplicada en local como **parche 6** (variante: `rollback`
conservando las escrituras ORM pendientes; ver «Parche 6» en [parches_pns_ai.md](parches_pns_ai.md)).
Las demás no se han aplicado.

1. **No escribir en `chatboo_session` con un segundo cursor mientras el cursor del hilo sigue
   abierto.** Dos opciones:
   - (a) Cerrar la transacción de A **antes** de `_finalize`: `self.env.cr.rollback()` (o commit,
     si hay algo que conservar) inmediatamente antes de las llamadas de `:697` y `:712`, en vez de
     hacerlo en el `finally`. Así A no puede tener locks cuando B escribe.
   - (b) Mejor aún: que **toda** la escritura en la sesión durante el turno se haga en cursores
     cortos que hagan commit en el acto (como ya hacen `_flush_progress` y el latido), incluida la
     de `last_screen_context` (`:556-562`). Así A queda como cursor de solo lectura para el motor.
2. **No tragarse un commit fallido** (`:512-519`): si el commit falla, hacer `rollback` y abortar
   el turno de forma controlada; nunca seguir con la transacción abierta.
3. **Acotar las esperas sobre la fila de sesión.** `SET LOCAL lock_timeout` (2-5 s) en `_finalize`
   y en las rutas que escriben la sesión (`load_session`, `save_session`, `rename`…), igual que ya
   se hace en `ai_provider.py:1063-1065` y `ai_context.py:1222-1223`. `update_last_used` en
   `load_session` es secundario: puede hacerse con `NOWAIT`/`SKIP LOCKED` o en segundo plano, y
   omitirse si la fila está bloqueada.
4. **No ejecutar trabajo largo en hilos dentro de los workers prefork.** Un hilo daemon dentro de
   un worker HTTP no tiene `limit_time_real`, muere si el worker se recicla y escapa del watchdog.
   Lo adecuado es una cola procesada por cron o `queue_job`, o como mínimo un tope de tiempo
   propio con `statement_timeout`/`idle_in_transaction_session_timeout` en el cursor A.
5. **Detección:** si `_finalize` no consigue el lock en N segundos, registrar un error claro y
   cerrar el job por SQL corto (como ya hace el fallback de `:922-933`), de modo que el tail SSE
   envíe `done`/`error` y el navegador no se quede esperando.
6. Como defensa en profundidad, configurar en el servidor
   `idle_in_transaction_session_timeout` para el rol de Odoo (por ejemplo 15 min) y
   `client_connection_check_interval` (PG 14+). No corrige el fallo, pero evita que dure
   indefinidamente.

## 6. Estado y decisiones pendientes

- H1/H2: los logs de Odoo de los dos incidentes de staging no tienen ningún «could not commit the
  session writes» → **H2 descartada; H1 es la hipótesis de trabajo** (16/10/2026). La
  reproducción de §5.1 sigue siendo útil para confirmar qué `UPDATE chatboo_session` sale por A.
- Pendiente: pasar el informe al fabricante.
- **Corrección 1a (§5.2): aplicada como parche 6** (aprobada por Sergio, 16/10/2026), pendiente de
  validar en staging (§5.1, «Validación del parche 6»). El informe al fabricante debe seguir
  pidiendo la corrección de fondo (1b y 2-6).
- Mientras tanto, en producción y en staging con usuarios reales: **no adjuntar imágenes en
  Chatboo**. Si hace falta una contención técnica sin tocar el código del fabricante, hay que
  valorar `idle_in_transaction_session_timeout` en el servidor PostgreSQL. Lo decide el usuario y
  afecta a todas las BD del rol.
