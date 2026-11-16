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

## Laboratorio automatizado

Desde el 16/11/2026 (parche 29, D10). Sirve para laboratorios cortos y sin el modelo real.

**Scripts.** Se usan desde `~/pns_ai_3973/fase4/lab/`. En el repo hay una copia de referencia, sin modificar, en
[lab_3973/](lab_3973/):

| Script | Uso | Copia de referencia | SHA-256 |
|---|---|---|---|
| `lab_cdp.py` | `~/pns_ai_3973/fase4/lab/lab_cdp.py` | [lab_3973/lab_cdp.py](lab_3973/lab_cdp.py) | `4c65f341a9936ef5caf70e532ea42aeba32ebe6046e54be1f38515987965d3f0` |
| `lab_auto.sh` | `~/pns_ai_3973/fase4/lab/lab_auto.sh` | [lab_3973/lab_auto.sh](lab_3973/lab_auto.sh) | `8391b87c83d5425438e95cf8dc00c91ba9e61de79f14dcf0ff604d7f840725ac` |
| `prueba_lab_auto.sh` | `~/pns_ai_3973/fase4/lab/prueba_lab_auto.sh` | [lab_3973/prueba_lab_auto.sh](lab_3973/prueba_lab_auto.sh) | `643c35fd4caf209b232b811b9ba426ea0126c9308f75d33d2e770f76d2e6b55b` |

SHA-256 vigentes desde el 16/11/2026, con la corrección de los tres límites (bloque «Corrección (16/11/2026): los tres
límites», abajo). Los del primer uso (laboratorio del 29) eran `7c5445ac…3f761` (`lab_cdp.py`) y `9287587c…36a3d`
(`lab_auto.sh`).

Antes de usarlos, `sha256sum` de los de `~` debe dar estos valores. Si alguno ha cambiado, se registra el SHA-256 nuevo
y se vuelve a copiar al repo.

**Qué hace `lab_auto.sh`** (descripción del primer uso; desde el 16/11/2026 cambian el orden del principio y los
códigos: ver «Corrección (16/11/2026): los tres límites»):
1. Pregunta si `odoo-dev 14 estado` mostró el contenedor `web` parado. Con otra respuesta que no sea `s` no arranca
   nada y sale con 1.
2. Pone un `trap` de `EXIT`. Pase lo que pase (fin normal, error o Ctrl+C), ese `trap` guarda el log del servidor
   (la orden de «Guardar el log»), hace C sobre el log guardado (`lab_cdp.py c`), ejecuta `odoo-dev 14 parar` e imprime
   el nombre del log guardado.
3. Ejecuta `odoo-dev 14 arrancar` desde `~/GitHub/lab_pns_ai_3973`.
4. Ejecuta `lab_cdp.py navegar`: espera al servidor (`/web/webclient/version_info`, que no carga ninguna BD), entra por
   `/web/login?db=lab_pns_ai_3973_14` con Chrome headless y un perfil temporal, comprueba que la sesión es de
   `lab_pns_ai_3973_14`, hace C sobre el log en vivo y visita las rutas. Durante todo el recorrido bloquea cualquier
   petición a `/web/database/*`, y antes de empezar rechaza las rutas que van a `/web/database` o llevan otra `db=`.
5. Sale con el código de `lab_cdp.py`. La C del `trap` **no cambia el código de salida**: se lee en la salida.

**Qué sigue siendo manual:**
- «Antes de arrancar», punto 1: `odoo-dev 14 estado` y `odoo-dev 14 bd-lista`.
- Ninguna pestaña de `localhost:8169` abierta en el navegador normal. El script no usa ventana privada: usa Chrome
  headless con un perfil temporal que borra al acabar. Una pestaña del navegador normal seguiría pudiendo cargar el
  registro de otra BD.
- Las credenciales, en la misma terminal donde se lanza el script: la contraseña con `read -rsp` y las dos variables
  con `unset` al acabar.
- Una carpeta de salida nueva para cada laboratorio, porque `detalle.txt` se abre en modo de añadir y mezclaría
  laboratorios. En esa carpeta quedan las capturas (`.png`), las descargas (`.html`), `detalle.txt` y
  `chrome_stderr.txt`. Son locales y no se copian a la documentación; de `detalle.txt` solo se citan el nombre y los
  recuentos.
- Los recuentos del log, D14 (si aplica) y la fila del registro.

**Órdenes, en orden** (ejemplo del 16/11/2026; en otro laboratorio cambian `29`, las rutas y el script de D14). Van
fuera de la lista para que no lleven sangría al copiarlas:

```bash
# 1. Credenciales (misma terminal que el resto; solo imprime la longitud de la contraseña, nunca la clave)
export LAB_LOGIN=seges_int@example.com; read -rsp "Contraseña de seges_int: " LAB_PASSWORD; echo; export LAB_PASSWORD; echo "LAB_LOGIN=$LAB_LOGIN · LAB_PASSWORD con ${#LAB_PASSWORD} caracteres"

# 2. Carpeta de salida nueva (mkdir sin -p: falla si ya existe)
LAB_SALIDA=~/pns_ai_3973/fase4/lab/salida_29_$(date +%Y%m%d-%H%M%S); mkdir "$LAB_SALIDA"

# 3. Laboratorio
bash ~/pns_ai_3973/fase4/lab/lab_auto.sh "$LAB_SALIDA" --descarga /chatboo/canvas/8/download /chatboo/canvas/4 /chatboo/canvas/8

# 4. Credenciales fuera (debe imprimir 0; el patrón no cuenta LAB_SALIDA)
unset LAB_LOGIN LAB_PASSWORD; env | grep -c '^LAB_\(LOGIN\|PASSWORD\)='

# 5. Recuentos del log guardado (AAAAMMDD-HHMMSS: el nombre que imprime «Log guardado:» al acabar)
LOG_LAB=~/odoo-dev/14.0/logs/servidor-AAAAMMDD-HHMMSS.log; wc -l < "$LOG_LAB"; echo "WARNING/ERROR/CRITICAL por nivel, BD y logger:"; grep -oE ",[0-9]{3} [0-9]+ (WARNING|ERROR|CRITICAL) [^ ]+ [^ ]+" "$LOG_LAB" | awk '{print $3, $4, $5}' | sort | uniq -c; echo "Traceback: $(grep -c 'Traceback' "$LOG_LAB")"; echo "bad query: $(grep -c 'bad query' "$LOG_LAB")"

# 6. Errores HTTP informativos (solo imprime la ruta medida, el código de estado y la URL sin parámetros)
grep -c "recursos_http" "$LAB_SALIDA/detalle.txt"; grep "recursos_http" "$LAB_SALIDA/detalle.txt" | grep -oE "^\[[^]]*\]|status of [0-9]+|https?://[^ ?#]+"

# 7. D14 después, si aplica (con el web parado; shell vuelve a levantar db). En otro laboratorio cambian el script de
#    medición y sus archivos de resultado
cd ~/GitHub/lab_pns_ai_3973 && odoo-dev 14 shell < ~/pns_ai_3973/fase4/29/d14_medicion.py > ~/pns_ai_3973/fase4/29/d14_despues.txt 2>&1; grep '^D14' ~/pns_ai_3973/fase4/29/d14_despues.txt; diff <(grep '^D14' ~/pns_ai_3973/fase4/29/d14_despues.txt) ~/pns_ai_3973/fase4/29/d14_resultado.txt && echo "D14 después: IGUAL que antes"

# 8. Parar (db sigue en marcha tras el shell)
cd ~/GitHub/lab_pns_ai_3973 && odoo-dev 14 parar
```

- Arranque y parada (UTC) para el registro: la primera y la última hora del log guardado (AAAAMMDD-HHMMSS: el nombre
  que imprime «Log guardado:» al acabar):

```bash
LOG=~/odoo-dev/14.0/logs/servidor-AAAAMMDD-HHMMSS.log; grep -m1 -oE "[0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}:[0-9]{2}" "$LOG" | cut -d' ' -f2
LOG=~/odoo-dev/14.0/logs/servidor-AAAAMMDD-HHMMSS.log; grep -oE "[0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}:[0-9]{2}" "$LOG" | tail -1 | cut -d' ' -f2
```

- Si `lab_cdp.py` da problemas, `python3 -I ~/pns_ai_3973/fase4/lab/lab_cdp.py autoprueba --salida <carpeta nueva>`
  lo valida en el equipo contra un servidor simulado en `127.0.0.1`, sin Odoo y sin BD.

**Códigos de salida de `lab_auto.sh`** (tabla del primer uso, sustituida el 16/11/2026 por la del bloque «Corrección
(16/11/2026): los tres límites»):

| Código | Significado |
|---|---|
| 0 | Todo como se espera: ninguna incidencia en ninguna ruta. |
| 1 | Varias causas (límite conocido): incidencias de medición (detalle en la salida, por ruta); respuesta distinta de `s` a la pregunta inicial (el `trap` aún no está puesto: no se arranca ni se para nada); falta `LAB_LOGIN` o `LAB_PASSWORD` (sale antes de todo, sin arrancar); falla `odoo-dev 14 arrancar` (el `trap` guarda el log y para); una guarda rechaza una ruta, con el mensaje «ruta no válida», «ruta prohibida» o «ruta con otra BD» (el `trap` guarda el log y para); un traceback del propio `lab_cdp.py`. |
| 2 | Abortado: el servidor no responde en 120 s, fallo del login, sesión de otra BD, C con otra BD o error de Chrome (CDP). También puede ser un error de `argparse` en los argumentos, que se distingue por su mensaje (`usage: …` / `error: …`). |
| 130 | Ctrl+C (o `TERM`). El `trap` guarda el log, hace C y para igualmente. |

**Qué mide por ruta:**
- Rutas normales (`/chatboo/canvas/<id>`): si la página carga; en cada marco `srcdoc` del lienzo, imágenes pintadas
  sobre el total y rotas, si hay `<meta>` CSP y si es el 2.º hijo de `<head>`, y el modo del documento (`CSS1Compat`);
  «Refused» de CSP por directiva (consola de Chrome); errores de JS (log, consola y excepciones); recursos con error
  HTTP (informativo, no es incidencia); peticiones a `/web/database` bloqueadas; una captura.
- Descargas (`--descarga /chatboo/canvas/<id>/download`): que la descarga se complete (30 s), una copia en la carpeta
  de salida y, abierta desde el disco (`file://`), las mismas medidas, incluido el documento principal. Las descargas se
  hacen después de todas las rutas normales, sea cual sea el orden de los argumentos.
- Es incidencia: página que no carga, imagen rota, `<meta>` CSP ausente, modo distinto de `CSS1Compat`, ningún marco
  medido, cualquier «Refused», cualquier error de JS, cualquier petición bloqueada a `/web/database` o una descarga no
  completada.

**Qué no cubre:** Compartir, `/chatboo/page/<id>` ni nada con el modelo real. Esos casos siguen siendo manuales, con
el procedimiento de arriba (los del modelo real van con P-13 del parche 34).

**Límites conocidos (16/11/2026, sin corregir todavía):** corregidos el mismo día (bloque siguiente).
- **Medida del login sin resumir:** `lab_cdp.py` abre una medida para el login pero no la resume. Los errores durante el
  login solo quedan en `detalle.txt`; no salen en la salida ni cambian el código de salida.
- **C final sin efecto en el código de salida:** la C que hace el `trap` sobre el log guardado no cambia el código de
  salida de `lab_auto.sh`. Hay que leer «C: OK» en la salida.
- **Código 1 con varias causas:** ver la tabla de códigos de salida; el código solo no dice cuál fue.

Los tres límites (medida del login sin resumir, C final sin efecto en el código de salida y código 1 con varias causas)
se corrigen antes del laboratorio del 34, con su autoprueba.

**Corrección (16/11/2026): los tres límites.** Antes del laboratorio del 34, con su autoprueba. Los scripts de la
tabla de arriba (SHA-256 nuevos) sustituyen a los del primer uso; la copia del repo se actualiza a la vez.

- **Medida del login, resumida:** tras entrar, `lab_cdp.py` espera lo mismo que en cada ruta (2,5 s) y saca un bloque
  `== login` con «Refused», recursos con error HTTP (informativo), errores de JS y peticiones bloqueadas a
  `/web/database`. Es incidencia (código 1) lo mismo que en una ruta, salvo «ningún marco medido», que en el login no se
  exige. En el laboratorio del 29 el login solo dejó un recurso HTTP informativo (el 404 de `/es/website/translations/…`),
  así que con el criterio nuevo habría dado igualmente código 0.
- **La C final cambia el código:** si la C del log guardado da otra BD, el código final es 3; si no se pudo guardar el
  log, si el log no tiene ninguna línea de Odoo o si falla `odoo-dev 14 parar`, es 7. Un log sin líneas de Odoo ya no da
  «C: OK» (antes sí). Excepción: si falló `arrancar` (14), un log sin líneas es lo esperable y no da 7.
- **Un código por causa:** tabla de abajo. El 2 ya no se usa (era el «abortado» de antes y el de `argparse`).
- **Orden nuevo del principio de `lab_auto.sh`:** argumentos → credenciales → guardas de las rutas (`lab_cdp.py rutas`)
  → carpeta del laboratorio → pregunta → `trap` → `arrancar`. Una ruta mal escrita ya no llega a arrancar Odoo.
- **Errores internos:** `lab_cdp.py` captura sus propias excepciones (traceback en la salida de errores) y sale con 20,
  para que no se confundan con el 1.
- **Al acabar,** `lab_auto.sh` imprime dos líneas: `Navegación: N (…) · C del log guardado: M` y `Código final N: <motivo>`.

| Código | Causa | ¿Arranca Odoo? |
|---|---|---|
| 0 | Todo como se espera | Sí |
| 1 | Incidencias de medición (rutas o login; detalle por ruta en la salida) | Sí |
| 3 | Otra BD: sesión, C tras la entrada o C del log guardado | Sí |
| 4 | El servidor no responde en 120 s | Sí |
| 5 | Falla el login | Sí |
| 6 | Error de Chrome (CDP), también si Chrome no arranca | Sí |
| 7 | «Al acabar» incompleto: log no guardado, sin líneas de Odoo o falla `parar` | Sí |
| 10 | Respuesta distinta de `s` a la pregunta inicial | No |
| 11 | Faltan `LAB_LOGIN` o `LAB_PASSWORD` | No |
| 12 | Argumentos o rutas no válidos (guardas y `argparse`) | No |
| 13 | No existe `~/GitHub/lab_pns_ai_3973` | No |
| 14 | Falla `odoo-dev 14 arrancar` (el `trap` guarda el log y para) | Sí |
| 20 | Error interno de `lab_cdp.py` | Sí |
| 130 | Ctrl+C o `TERM` (el `trap` guarda el log, hace C y para) | Sí |

Si coinciden varias causas: 7, después 3, después el código de la navegación.

**Validación de los scripts** (sin Odoo, sin Docker y sin BD; Chrome solo en la primera):

```bash
# Autoprueba de lab_cdp.py contra un servidor simulado (esperado: «Autoprueba: todo PASA», 27 PASA, código 0)
AP=$(mktemp -d /tmp/autoprueba_lab.XXXXXX); python3 -I ~/pns_ai_3973/fase4/lab/lab_cdp.py autoprueba --salida "$AP" | grep -E "PASA|FALLA|Autoprueba"; echo "código ${PIPESTATUS[0]}"

# Prueba de lab_auto.sh con dobles de odoo-dev y de navegar, en una carpeta temporal (esperado: 21 PASA, código 0)
bash ~/pns_ai_3973/fase4/lab/prueba_lab_auto.sh; echo "código $?"
```

`prueba_lab_auto.sh` ejecuta una copia de `lab_auto.sh` con `HOME` en una carpeta temporal y un `odoo-dev` falso en el
`PATH`: no toca `~/GitHub`, `~/odoo-dev` ni Docker, y borra la carpeta temporal al acabar.

**Qué no ha cambiado:** las rutas que mide, lo que es incidencia en una ruta, la guardia de `/web/database`, la C (su
lógica), el `trap`, las órdenes 1 a 8 de arriba y lo que sigue siendo manual.

**Si aparece otra BD** (texto del primer uso; desde el 16/11/2026 el código es 3 y también lo da la C del log
guardado): sigue valiendo «Si aparece otra BD». El script aborta (código 2) si la C tras la entrada da
otra BD, y el `trap` ya guarda el log y para. Si la otra BD aparece solo en la C del `trap` (log guardado), el código
de salida no lo refleja: hay que leer esa C. En los dos casos, anotar y «Crons de la otra BD» sobre el log guardado.

## Registro de laboratorios

Horas en UTC (las del log). Un bloque por laboratorio; no se reescriben los anteriores.

| Fecha | Arranque | Parada | C (tras la entrada / tras reinicios / log guardado) | Log guardado | Notas |
|---|---|---|---|---|---|
| 13/11/2026 | 18:52:45 | 18:57:35 (última línea del log guardado) | cubierta por la del log guardado / sin reinicios / `?` (17), `lab_pns_ai_3973_14` (99); Starting job: `lab_pns_ai_3973_14` (13) | `servidor-20261113-195757.log` | Parche 27 (D5). Primer uso real de C: funciona. Navegador sin errores ni «Refused» en `canvas/8`, su descarga desde el disco, Compartir con `seges_aiadm`, `page/<id>` y su descarga. Log: 1 WARNING `py.warnings`, 0 ERROR. `servidor-20261113-195320.log` (6 líneas), guardado antes de tiempo, sin uso. |
| 16/11/2026 | 10:32:49 | 10:33:02 (última línea del log guardado) | `?` (17), `lab_pns_ai_3973_14` (41) / sin reinicios / `?` (17), `lab_pns_ai_3973_14` (47); Starting job: ninguna | `servidor-20261116-113304.log` | Parche 29 (D10), automatizado y sin LLM. Primer uso real de `lab_cdp.py` y `lab_auto.sh` con Odoo: código 0 («Laboratorio automatizado»). Sesión de `lab_pns_ai_3973_14` (uid 12). `canvas/4`, `canvas/8` y la descarga de la 8 abierta desde el disco: en las tres, imágenes 15/15 pintadas, 0 rotas, `<meta>` CSP como 2.º hijo de `<head>`, CSS1Compat, ningún «Refused», 0 errores de JS; 0 peticiones a `/web/database` bloqueadas. Informativos, fuera del lienzo: un 404 de `/es/website/translations/…` en el login y un 404 de `/es/favicon.ico` en `canvas/4`. Log (66 líneas): 1 WARNING `py.warnings` (`lab_pns_ai_3973_14`), 0 ERROR, 0 CRITICAL, 0 Traceback, 0 «bad query». D14 después igual que antes. |
