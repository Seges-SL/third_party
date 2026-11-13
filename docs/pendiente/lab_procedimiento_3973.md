# Procedimiento fijo del laboratorio `lab_pns_ai_3973`

- **Fecha:** 13/11/2026. **Rama:** `14.0-pns-ai-3973`. **Laboratorio:** `lab_pns_ai_3973` (BD `lab_pns_ai_3973_14`).
- **Decisión de Sergio (13/11/2026):** la mitigación usada en el laboratorio del parche 38 pasa a ser el procedimiento
  fijo. No se limita el servidor (`dbfilter`/`db_name`) ni se cambia el kit.
- **Antecedentes:** [propuesta_fase3_3973.md](propuesta_fase3_3973.md), «Pendientes fuera de la 3b (12/11/2026)» (crons
  de `lab_pns_ai_3879_14`) y «Laboratorio del parche 38 (13/11/2026)», apartado «Preparación».

## Alcance

- Cada `odoo-dev 14 arrancar` y cada reinicio del servidor por `odoo-dev 14 instalar` o `actualizar` mientras
  `third_party` esté en `14.0-pns-ai-3973`.
- No aplica a `odoo-dev 14 tests` ni a `odoo-dev 14 shell`. Los dos usan un contenedor de un solo uso
  (`dc run --rm`) contra una sola BD y no arrancan el servidor web ni sus crons (`entorno.sh:470`, `:496` y `:506`).
- Sigue vigente la regla del plan: `lab_pns_ai_3879` no se arranca, ni se reinicia, ni se actualiza mientras el repo esté
  en esta rama.

## Por qué

- El kit genera `odoo.conf` sin `dbfilter` ni `db_name`, con `workers = 0` y `list_db = True`
  (`claude-odoo-kit/entorno/entorno.sh:375-386`).
- Con hilos (`workers = 0`), el hilo de crons solo recorre las BD que tienen el registro cargado
  (`Registry.registries`, `odoo/service/server.py:406-413`). Sin `db_name`, al arrancar no hay ninguna.
- El registro de una BD se carga con **cualquier petición** a esa BD: una pestaña abierta, una cookie de sesión de otra
  BD, el selector de BD o un script. Desde ese momento, el servidor ejecuta los crons de esa BD con el código montado,
  que es el de esta rama.
- El 12/11/2026 fue una pestaña abierta: el servidor cargó `lab_pns_ai_3879_14` con el código de 3.1.973 y ejecutó
  sus crons, también dos de `pns_*`.

## El log del servidor (de dónde sale y cómo se guarda)

- `odoo.conf` no tiene `logfile`, así que Odoo escribe el log en la salida del contenedor `web`.
- `odoo-dev 14 log [n]` es `docker compose logs --no-color --tail n web` (`entorno.sh:460-463`). **Lleva el prefijo del
  servicio** que pone `docker compose` (del tipo `web-1  | `) delante de la línea de Odoo
  (`AAAA-MM-DD HH:MM:SS,mmm <pid> <nivel> <bd> <logger>: <mensaje>`, en UTC; `?` cuando el hilo no tiene BD).
  `odoo-dev 14 log all` da el log entero.
- `odoo-dev 14 instalar`/`actualizar` reinician el servidor con `docker compose restart web` (`entorno.sh:483`). El
  contenedor es el mismo, así que su log sigue siendo el de todo el laboratorio, desde el `arrancar`.
- `odoo-dev 14 parar` hace `docker compose down` (`entorno.sh:428`), que **borra el contenedor y su log**. Por eso el log
  se guarda siempre antes de parar.
- Los logs de `instalar`, `actualizar` y `tests` van a archivos propios en `~/odoo-dev/14.0/logs/` (`entorno.sh:468-470`)
  y no forman parte del log del servidor.

## Antes de arrancar

1. `odoo-dev 14 estado` y `odoo-dev 14 bd-lista` (solo lectura).
   - Si `estado` muestra el contenedor `web` en marcha, no se arranca encima: `arrancar` podría reutilizar el
     contenedor y su log no empezaría en este laboratorio. Primero, «Al acabar» (guardar el log, C y `parar`).
2. Una **ventana privada nueva**, solo para el laboratorio, sin otras pestañas de `localhost:8169`.
   - Alternativa: cerrar todas las pestañas de `localhost:8169` y borrar sus cookies.

## Arranque

1. `odoo-dev 14 arrancar`, desde `~/GitHub/lab_pns_ai_3973`. Hora de arranque: la primera línea del log del servidor.
2. Entrada solo por `http://localhost:8169/web/login?db=lab_pns_ai_3973_14`, en la ventana privada. **Nunca por el
   selector de BD** (`/web/database/selector` ni `/web/database/manager`).
3. Los scripts HTTP (`/mcp`) solo con una sesión de `lab_pns_ai_3973_14`. `/mcp` es `auth='none'` y no elige BD en la
   ruta (`pns_ai_mcp/controllers/main.py:759`): la BD sale de la sesión.

## Comprobación C

Solo lectura. Lee el log y solo imprime nombres de BD y recuentos: cuántas líneas tiene cada BD en el log desde el
arranque y cuántos «Starting job» de `ir_cron` (logger `odoo.addons.base.models.ir_cron`, mensaje
«Starting job `<nombre>`.») tiene cada BD. No imprime ninguna línea del log.

**Esperado:**
- BD con líneas: solo `?` y `lab_pns_ai_3973_14`;
- BD con «Starting job»: solo `lab_pns_ai_3973_14`, o ninguna.

**Con el servidor en marcha:**

```bash
odoo-dev 14 log all | python3 -c '
import collections, io, re, sys
pat = re.compile(r"\d{4}-\d\d-\d\d \d\d:\d\d:\d\d,\d{3} \d+ \S+ (\S+) (\S+): (.*)")
lineas = collections.Counter()
crons = collections.Counter()
for linea in io.TextIOWrapper(sys.stdin.buffer, encoding="utf-8", errors="replace"):
    m = pat.search(linea)
    if not m:
        continue
    lineas[m.group(1)] += 1
    if m.group(2) == "odoo.addons.base.models.ir_cron" and m.group(3).startswith("Starting job"):
        crons[m.group(1)] += 1
print("BD con líneas:", ", ".join("%s (%d)" % kv for kv in sorted(lineas.items())) or "ninguna")
print("BD con Starting job:", ", ".join("%s (%d)" % kv for kv in sorted(crons.items())) or "ninguna")
'
```

**Sobre un log guardado:** el mismo `python3 -c '…'`, con `< <archivo>` en lugar de `odoo-dev 14 log all |`.

- `pat.search` encuentra la línea de Odoo detrás del prefijo de `docker compose`. Las líneas de continuación (pilas de
  un Traceback) no tienen ese formato y no cuentan.

**Cuándo:**
1. tras la primera entrada por `/web/login?db=lab_pns_ai_3973_14`;
2. tras cada reinicio por `instalar` o `actualizar`;
3. antes de parar (sobre el log guardado, en «Al acabar»).

## Si aparece otra BD

1. **Parar**, guardando antes el log (órdenes de «Al acabar»).
2. **Anotar**, en el registro de abajo: BD, hora y crons de esa BD (nombre, módulo y resultado, sin datos). Para los
   crons, la orden de «Crons de la otra BD» (abajo), sobre el log guardado.
   - Resultado: «hecho» sin «falló» es `done`. En Odoo 14, un cron que falla en su acción registra «Call from cron …
     failed» y después también «Job … done.» (`_callback` captura la excepción): manda «falló».
   - El módulo no está en el log: se toma del XML ID del cron con una consulta de solo lectura (`ir_model_data`),
     presentada antes, o se deduce del nombre y se anota como deducido.
3. **Esa BD queda no fiable** hasta que Sergio decida qué hacer con ella. No se vuelve a usar ni se compara con ella.
4. **Caso especial, `lab_pns_ai_973_14`:** dejaría de ser la referencia limpia de 3.1.973 (crons ejecutados con el código
   de esta rama). Se avisa a Sergio antes de cualquier comparación con 3.1.973.

**Crons de la otra BD** (solo lectura; imprime hora UTC, BD, suceso y nombre del cron, nada más). Va fuera de la lista
para que el código no lleve sangría al copiarlo:

```bash
python3 -c '
import io, re, sys
permitidas = {"?", "lab_pns_ai_3973_14"}
pat = re.compile(r"(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d),\d{3} \d+ \S+ (\S+) odoo\.addons\.base\.models\.ir_cron: (Starting job|Job|Call from cron|Unexpected exception)(.*)")
for linea in io.TextIOWrapper(sys.stdin.buffer, encoding="utf-8", errors="replace"):
    m = pat.search(linea)
    if not m or m.group(2) in permitidas:
        continue
    hora, bd, suceso, resto = m.groups()
    if suceso == "Unexpected exception":
        print(hora, bd, "excepción inesperada (nombre no impreso)")
    elif suceso == "Call from cron":
        print(hora, bd, "falló:", resto.split(" for server action")[0].strip())
    elif suceso == "Job" and not resto.rstrip().endswith("done."):
        continue
    else:
        n = re.search(r"`(.*?)`", resto)
        print(hora, bd, "inicio" if suceso == "Starting job" else "hecho", n.group(1) if n else "?")
' < <archivo>
```

## Al acabar

1. **Guardar el log** entero, antes de parar, con la orden de «Guardar el log» (abajo). Hora de parada: la última línea
   del log guardado.
2. **C sobre el log guardado:** la orden de C con `< "$LOG_LAB"` en lugar de `odoo-dev 14 log all |`.
3. Cerrar la ventana privada.
4. `odoo-dev 14 parar`.

**Guardar el log.** Va fuera de la lista para que la orden no lleve sangría al copiarla:

```bash
LOG_LAB=~/odoo-dev/14.0/logs/servidor-$(date +%Y%m%d-%H%M%S).log; odoo-dev 14 log all > "$LOG_LAB" && wc -l "$LOG_LAB"
```

El log guardado no se imprime ni se copia a la documentación. Puede llevar datos de la sesión, como el `csrf_token` de
las líneas de `werkzeug` (propuesta, «Pendientes fuera de la 3b»). Solo se cita por su nombre de archivo.

## Líneas esperadas que no son fallo

Las del [anexo de PNS-26](propuesta_fase3_3973.md) («Anexo de PNS-26 (serialización en `/execute`): confirmación en
3.1.973», 13/11/2026). Por cada «Ejecutar» correcto de una ficha (en la interfaz, «Confirmar» encadena `/confirm` y
`/execute`):
- un `ERROR` «bad query» de `odoo.sql_db` sobre `ai_safe_operation`;
- un `INFO` «SERIALIZATION_FAILURE, retry 1/5 in … sec...» (`odoo.service.model`).

Se cuentan, no se imprimen. Con un `/execute` fallido no aparecen. «maximum number of tries reached» sí es fallo.

## Registro de laboratorios

Horas en UTC (las del log). Un bloque por laboratorio; no se reescriben los anteriores.

| Fecha | Arranque | Parada | C (tras la entrada / tras reinicios / log guardado) | Log guardado | Notas |
|---|---|---|---|---|---|
| | | | | | |
