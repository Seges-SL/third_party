# Guía de las pruebas con toda la rama `14.0-pns-ai-3973`

- **Fecha:** 17/11/2026. **Plan:** [plan_correccion_pns_ai_3973.md](../plan_correccion_pns_ai_3973.md), «Pruebas
  posteriores», punto 4. **Procedimiento fijo:** [lab_procedimiento_3973.md](../lab_procedimiento_3973.md): vale para cada
  `arrancar` de esta guía, también en las carpetas nuevas.
- **Decisiones:** D41 a D47 de Sergio (17/11/2026) y sus respuestas al paso 0 (mismo día), en el plan.
- **Qué cubre:** P-2 (a, b y c, con D38 y D43), P-11, P-14, el parche 39 en el laboratorio, `_require_settings` con y
  sin el 32 (D46) y el reintento de la tarjeta (D47).
- **Bloques, en este orden:** 0 (preparación), 3, 1, 2, 4, «Al acabar» y limpieza final.
- **Datos de demostración:** las BD de P-2 (`lab_p2a_879_14` y `lab_p2b_879_14`) se instalan con ellos: el kit no pasa
  `--without-demo`. Aceptado por Sergio (17/11/2026).
- **Salidas:** nada de lo que imprimen los scripts lleva datos ni secretos; los logs se citan por su nombre de archivo.

## Contextos de `odoo-dev 14`

El contexto es el del último `arrancar` (MANUAL del kit, 6.7). Cada orden dice desde qué carpeta se lanza.

| Contexto | Carpeta | Imagen | Código de `pns_*` | Para qué |
|---|---|---|---|---|
| `lab_pns_ai_879` | `~/GitHub/lab_pns_ai_879` | `odoo-dev:14-lab_pns_ai_879` | 3.1.879 (`modulos_3879`) | Instalar 3.1.879 en las dos BD de P-2 y plantar |
| `lab_pns_ai_973f` | `~/GitHub/lab_pns_ai_973f` | `odoo-dev:14-lab_pns_ai_973f` | Base limpia 3.1.973 (`33ca68c`) | Primer `-u` de P-2 (b) |
| `lab_pns_ai_3973` | `~/GitHub/lab_pns_ai_3973` | `odoo-dev:14-lab_pns_ai_3973` | La rama (`third_party`) | Todo `-u` a la rama, comprobaciones y bloques 3 y 4 |

- **Cambiar de contexto** es `arrancar` desde la carpeta, que levanta también el servidor web. Por eso, tras cada
  `arrancar` que solo sirve para cambiar de contexto, se hace enseguida el «Al acabar corto» (abajo), sin abrir ninguna
  pestaña de `localhost:8169`.
- **Antes de cada `-u`** se comprueba, en solo lectura, el contexto y que el web está parado (orden «Comprobar el
  contexto», abajo). Cada `-u` se lanza con el web parado.
- **Todo `-u` a la rama** se lanza desde `lab_pns_ai_3973` con `--bd` y nombra los tres módulos (D38):
  `-u pns_base,pns_ai_mcp,pns_ai_chatboo`.

### Órdenes que se repiten

Van fuera de las listas para que no lleven sangría al copiarlas. `<carpeta>` y `<bd>` cambian en cada uso.

**Comprobar el contexto** (solo lectura; antes de cada `-u` y de cada script):

```bash
C=<carpeta>; [ "$(sed -n 's/^REPO=//p' ~/odoo-dev/14.0/estado)" = "$HOME/GitHub/$C" ] && ! docker ps --format '{{.Names}}' | grep -qx odoo-dev-14-web-1 && echo "CONTEXTO $C Y WEB PARADO: OK" || echo "NO: contexto distinto o web en marcha; no seguir"
```

Esperado: `CONTEXTO <carpeta> Y WEB PARADO: OK`.

**Al acabar corto** (tras un `arrancar` que solo cambia el contexto; procedimiento, «Al acabar»):

```bash
cd ~/GitHub/<carpeta> && LOG_LAB=~/odoo-dev/14.0/logs/servidor-$(date +%Y%m%d-%H%M%S).log; odoo-dev 14 log all > "$LOG_LAB" && wc -l "$LOG_LAB"; python3 -I ~/pns_ai_3973/fase4/lab/lab_cdp.py c --lab <carpeta> --bd <bd> < "$LOG_LAB"; echo "C: código $?"; odoo-dev 14 parar
```

Esperado: «BD con líneas: ? (N)» (ninguna BD: nadie ha entrado), «BD con Starting job: ninguna», «C: OK», `C: código 0`.
Si sale otra BD: «Si aparece otra BD» del procedimiento. Cada `arrancar` lleva su fila en el registro de laboratorios.

**`-u` a la rama y su log** (D38; desde `lab_pns_ai_3973`, tras «Comprobar el contexto»):

```bash
cd ~/GitHub/lab_pns_ai_3973 && odoo-dev 14 actualizar pns_base,pns_ai_mcp,pns_ai_chatboo --bd <bd> 2>&1 | tee ~/pns_ai_3973/fase4/rama/u_<bd>.txt; echo "código ${PIPESTATUS[0]}"
LOG_U=$(sed -n 's/^==> actualizar en <bd> (log: \(.*\))$/\1/p' ~/pns_ai_3973/fase4/rama/u_<bd>.txt); echo "LOG_U=$LOG_U"
```

Esperado: `OK` u `OK CON AVISOS` (análisis del kit) y código 0; `LOG_U` es el `actualizar-*.log` de la línea «==> actualizar
en `<bd>` (log: …)». Ese log es el `--log` de `rama_comprobar.sh`. `u_<bd>.txt` es local: no se copia a la documentación.

**`$LOG_U` y `$LOG_U973F` viven en la terminal.** Cada `-u` y su `rama_comprobar.sh` se lanzan en la misma terminal. En
otra terminal (o tras cerrarla), se recuperan de `u_<bd>.txt`, que guarda la línea «==> actualizar en …»:

```bash
LOG_U=$(sed -n 's/^==> actualizar en <bd> (log: \(.*\))$/\1/p' ~/pns_ai_3973/fase4/rama/u_<bd>.txt); echo "LOG_U=$LOG_U"
LOG_U973F=$(sed -n 's/^==> actualizar en lab_p2b_879_14 (log: \(.*\))$/\1/p' ~/pns_ai_3973/fase4/rama/u_lab_p2b_879_14_973f.txt); echo "LOG_U973F=$LOG_U973F"
```

`$LOG_U` cambia en cada `-u` a la rama: tras el bloque 2, el de `lab_pns_ai_3973_14` y el de `lab_p2a_879_14` solo
salen ya de su `u_<bd>.txt`.

## Bloque 0: preparación

1. Los scripts se usan desde `~/pns_ai_3973/fase4/lab/`, como los del laboratorio automatizado. Copia y comprobación
   (la tabla de SHA-256 está al final de esta guía):

   ```bash
   mkdir -p ~/pns_ai_3973/fase4/rama && cd ~/GitHub/third_party/docs/pendiente/lab_3973 && cp lab_auto.sh lab_cdp.py prueba_lab_auto.sh rama_carpetas.sh rama_plantar.sh rama_comprobar.sh rama_crons.sh rama_corregir_p2b.sh p39_lab.sh rama_require_settings.sh tarjeta_plantar.sh tarjeta_borrar.sh ~/pns_ai_3973/fase4/lab/ && cd ~/pns_ai_3973/fase4/lab && sha256sum lab_auto.sh lab_cdp.py prueba_lab_auto.sh rama_*.sh p39_lab.sh tarjeta_*.sh
   ```

   Esperado: los SHA-256 de la tabla.
2. Validación sin Odoo:

   ```bash
   bash ~/pns_ai_3973/fase4/lab/prueba_lab_auto.sh; echo "código $?"
   ```

   Esperado: «Prueba de lab_auto.sh: 49 PASA», código 0.
3. «Antes de arrancar» del procedimiento: `odoo-dev 14 estado` y `odoo-dev 14 bd-lista` (solo lectura). Esperado: web
   parado; no existen `lab_p2a_879_14` ni `lab_p2b_879_14`.
4. Carpetas de laboratorio (D41, D42). **Escribe** en `~/GitHub` (pide «s/N»):

   ```bash
   bash ~/pns_ai_3973/fase4/lab/rama_carpetas.sh; echo "código $?"
   ```

   Esperado: código 0 y estas líneas (los SHA-256 de `SHA256SUMS.txt` son deterministas: contenido y rutas de los
   módulos):
   - `modulos_3879: 711 archivos, todos con el SHA-256 de sha256_copias.tsv, ninguno de más`;
   - `commit de la 1b: 33ca68c054b5a6faff937bfd32123358f136efc2 (657 archivos de los tres módulos)`;
   - `lab_pns_ai_879: 711 archivos de módulos; SHA256SUMS.txt e37be4488f2b086a38ff8e6f04baf2f5464a880efd5d241b442909d10fcd1844`;
   - `lab_pns_ai_973f: 657 archivos de módulos (blobs de 33ca68c); SHA256SUMS.txt 4c5b1cd294de9ddb074f8e78a3b4416968bb9e36d6670063d5382fc24fae6c53`;
   - `Dockerfile.14 en las dos: cfc58aed82d52734706dca9b28bef12dfbe42d5db6288f224ec2a481a9f4c348`.

## Bloque 3: P-2 (c) y el parche 39 en `lab_pns_ai_3973_14`

Contexto `lab_pns_ai_3973` (el de siempre). Si el último `arrancar` no fue desde esa carpeta: `arrancar` desde
`~/GitHub/lab_pns_ai_3973` y «Al acabar corto» con `--lab lab_pns_ai_3973 --bd lab_pns_ai_3973_14`.

1. «Comprobar el contexto» con `C=lab_pns_ai_3973`.
2. `-u` a la rama con `<bd>` = `lab_pns_ai_3973_14`. Esperado: `OK` u `OK CON AVISOS`.
3. Comprobación de P-2 (c) y P-11 (solo lectura):

   ```bash
   bash ~/pns_ai_3973/fase4/lab/rama_comprobar.sh --bd lab_pns_ai_3973_14 --caso c --log "$LOG_U"; echo "código $?"
   ```

   Esperado: código 0, todo `OK`: log solo de `lab_pns_ai_3973_14`; «Running migration …» 0; líneas «Seges patch 35:» 0;
   WARNING del 35 0; versiones `14.0.2.1.587`, `14.0.3.1.973` y `14.0.1.2.69`; `model._gc_expired()` en los dos crons;
   P-11, ningún AI Administrator sin AI Conversational. P-14: «no aplica en c».
4. Siguiente pasada (D43). **Escribe** (GC de las cachés y `lastcall`; pide «s/N»):

   ```bash
   bash ~/pns_ai_3973/fase4/lab/rama_crons.sh --bd lab_pns_ai_3973_14; echo "código $?"
   ```

   Esperado: los dos crons con `"model._gc_expired()"` y «sin error»; «ValueError en la salida del shell: 0»;
   «Resultado: OK», código 0.
5. Parche 39 (solo lectura; sin commit):

   ```bash
   bash ~/pns_ai_3973/fase4/lab/p39_lab.sh; echo "código $?"
   ```

   Esperado, cada caso con su clase (cabecera del script, con las citas) y «→ rechazado como se prevé»:
   - `iap.account.get('seges_lab39')`: «bloqueado por el 39» (en ejecución, `_read_attr` →
     `_seges_check_model_method`, `context_builder.py:309-334`);
   - `get_credits_url('seges_lab39')`: `requires_write` (el AST la ve en la lista global, `validators_base.py:307`;
     `validators_checks.py:464-484`);
   - `f = …get_config_account_url; f()`: «bloqueado por el 39» (lectura sin llamada; `validators_base.py:326`);
   - `sms.resend.new({}).action_buy_credits()`: `requires_write` (`validators_base.py:310`).

   Además: control `sin error → OK`; `iap_account` antes y después iguales («sin cambios»); «P39 FIN previstos 4/4,
   excepciones 0, control OK, iap_account igual» y «P39 VEREDICTO OK»; código 0.
   - Código 1 (FALLO): un caso con «otro error», «sin error» u otra clase de rechazo distinta de la prevista, el control
     con error o `iap_account` cambiada.
   - Código 8 (NO CONCLUYENTE): alguna llamada lanzó una excepción. No cuenta como rechazo; se informa a Sergio.
   - Código 16: falta `sms` o `iap`; no se ha llamado a la herramienta; se informa a Sergio.

## Bloque 1: P-2 (a), P-11 y P-14 en `lab_p2a_879_14`

1. Contexto 3.1.879. Desde `~/GitHub/lab_pns_ai_879`: `odoo-dev 14 arrancar` (la primera vez construye
   `odoo-dev:14-lab_pns_ai_879`). Esperado: compartidos ninguno, cliente `~/GitHub/lab_pns_ai_879`. Sin abrir ninguna
   pestaña: «Al acabar corto» con `--lab lab_pns_ai_879 --bd lab_p2a_879_14`.
2. «Comprobar el contexto» con `C=lab_pns_ai_879`.
3. Paridad (solo lectura) e instalación de 3.1.879 (crea la BD, con datos de demostración):

   ```bash
   cd ~/GitHub/lab_pns_ai_879 && odoo-dev 14 paridad pns_base,pns_ai_mcp,pns_ai_chatboo --bd lab_p2a_879_14
   cd ~/GitHub/lab_pns_ai_879 && odoo-dev 14 instalar pns_base,pns_ai_mcp,pns_ai_chatboo --bd lab_p2a_879_14; echo "código $?"
   ```

   Esperado: la paridad no dice `FALLARÁ` (si lo dice, se para y se informa); la instalación `OK` u `OK CON AVISOS`.
4. Foto y plantado de P-11 y P-14. **Escribe** tras la foto (pide «s/N»):

   ```bash
   bash ~/pns_ai_3973/fase4/lab/rama_plantar.sh --bd lab_p2a_879_14; echo "código $?"
   ```

   Esperado en la foto: `pns_base` `14.0.1.2.47`, `pns_ai_mcp` `14.0.3.1.879` y `pns_ai_chatboo` `14.0.2.1.538`
   instalados, y el código montado con las mismas versiones; los dos crons con `"model.gc_expired()"`; las siete skills
   retiradas con su fila de fábrica; «ya plantado: usuario 0, sesión 0, caché 0». Tras «s»: `RAMA PLANTADO usuario=…
   sesion=… skill=… cache=…`, código 0.
5. Contexto de la rama. Desde `~/GitHub/lab_pns_ai_3973`: `odoo-dev 14 arrancar` y «Al acabar corto» con
   `--lab lab_pns_ai_3973 --bd lab_pns_ai_3973_14`.
6. «Comprobar el contexto» con `C=lab_pns_ai_3973` y `-u` a la rama con `<bd>` = `lab_p2a_879_14`.
7. Comprobación de P-2 (a), P-11 y P-14 (solo lectura):

   ```bash
   bash ~/pns_ai_3973/fase4/lab/rama_comprobar.sh --bd lab_p2a_879_14 --caso a --log "$LOG_U"; echo "código $?"
   ```

   Esperado: código 0, todo `OK`: «Running migration [14.0.3.1.973>] post-migrate» 1; «Seges patch 35: … fixed» 1 y 1;
   WARNING del 35 0; versiones de la rama; `model._gc_expired()` en los dos; P-11, todos los AI Administrators con AI
   Conversational y `seges_p11_admin` también; P-14, 0 filas de fábrica de las retiradas, 0 en la caché plantada y la
   sesión presente.
8. Siguiente pasada (D43), **escribe**: `rama_crons.sh --bd lab_p2a_879_14`. Esperado como en el bloque 3, punto 4.

## Bloque 2: P-2 (b), P-11 y P-14 en `lab_p2b_879_14`

1. Contexto 3.1.879: desde `~/GitHub/lab_pns_ai_879`, `odoo-dev 14 arrancar` y «Al acabar corto» con
   `--lab lab_pns_ai_879 --bd lab_p2b_879_14`.
2. «Comprobar el contexto» con `C=lab_pns_ai_879`; paridad e instalación como en el bloque 1, punto 3, con
   `--bd lab_p2b_879_14`.
3. Foto y plantado, **escribe**: `rama_plantar.sh --bd lab_p2b_879_14`. Esperado como en el bloque 1, punto 4.
4. Contexto de la base limpia: desde `~/GitHub/lab_pns_ai_973f`, `odoo-dev 14 arrancar` (la primera vez construye
   `odoo-dev:14-lab_pns_ai_973f`; compartidos ninguno, cliente `~/GitHub/lab_pns_ai_973f`) y «Al acabar corto» con
   `--lab lab_pns_ai_973f --bd lab_p2b_879_14`.
5. «Comprobar el contexto» con `C=lab_pns_ai_973f` y primer `-u`, a la base limpia (no es a la rama):

   ```bash
   cd ~/GitHub/lab_pns_ai_973f && odoo-dev 14 actualizar pns_base,pns_ai_mcp,pns_ai_chatboo --bd lab_p2b_879_14 2>&1 | tee ~/pns_ai_3973/fase4/rama/u_lab_p2b_879_14_973f.txt; echo "código ${PIPESTATUS[0]}"
   LOG_U973F=$(sed -n 's/^==> actualizar en lab_p2b_879_14 (log: \(.*\))$/\1/p' ~/pns_ai_3973/fase4/rama/u_lab_p2b_879_14_973f.txt); echo "Running migration: $(grep -cF 'module pns_ai_mcp: Running migration' "$LOG_U973F") · Seges patch 35: $(grep -cF 'Seges patch 35' "$LOG_U973F")"
   ```

   Esperado: `OK` u `OK CON AVISOS`; «Running migration: 0 · Seges patch 35: 0» (la base limpia no trae
   `migrations/`).
6. Contexto de la rama: desde `~/GitHub/lab_pns_ai_3973`, `odoo-dev 14 arrancar` y «Al acabar corto» con
   `--lab lab_pns_ai_3973 --bd lab_pns_ai_3973_14`.
7. «Comprobar el contexto» con `C=lab_pns_ai_3973` y `-u` a la rama con `<bd>` = `lab_p2b_879_14`.
8. Comprobación de P-2 (b) antes de corregir (solo lectura):

   ```bash
   bash ~/pns_ai_3973/fase4/lab/rama_comprobar.sh --bd lab_p2b_879_14 --caso b --log "$LOG_U"; echo "código $?"
   ```

   Esperado: código 0: «Running migration …» 0 y «Seges patch 35:» 0 (el `-u` no cruza 3.1.973); los dos crons con
   `model.gc_expired()`; P-11 y P-14 como en el bloque 1 (los hizo el `-u` a la base limpia).
8b. Control negativo de D43, antes de la corrección (pide «s/N»; no deja nada escrito):

   ```bash
   bash ~/pns_ai_3973/fase4/lab/rama_crons.sh --bd lab_p2b_879_14; echo "código $?"
   ```

   Esperado: los dos crons con `"model.gc_expired()"` y «falló con ValueError»; «RAMA CRONS sin error 0 de 2 (commit
   hecho)»; «ValueError en la salida del shell: 2» (o más); «Resultado: FALLO», código 1. Con el código antiguo,
   `safe_eval` envuelve el `AttributeError` en `ValueError` (`odoo/tools/safe_eval.py:346-347` de la imagen). No queda
   nada escrito aunque el script haga commit:
   - `method_direct_trigger` solo escribe `lastcall` después de `run()` (`odoo/addons/base/models/ir_cron.py:83-84`), así
     que no llega a escribirlo;
   - cada cron va en su `savepoint` (`rama_crons.sh`), que deshace lo que hubiera hecho la acción antes de fallar.
9. Corrección a mano (decisión 5 del 17/11/2026). **Escribe** (muestra el code y pide «s/N»):

   ```bash
   bash ~/pns_ai_3973/fase4/lab/rama_corregir_p2b.sh --bd lab_p2b_879_14; echo "código $?"
   ```

   Esperado: los dos con `"model.gc_expired()"`, «por corregir: 2»; tras «s», «RAMA CORREGIDOS 2; ahora: … 
   "model._gc_expired()" …», código 0.
10. Comprobación tras la corrección (solo lectura): la misma orden del punto 8 con `--corregido`. Esperado: código 0 y
    `model._gc_expired()` en los dos.
11. Siguiente pasada (D43), **escribe**: `rama_crons.sh --bd lab_p2b_879_14`. Esperado como en el bloque 3, punto 4.

## Bloque 4: `_require_settings` y reintento de la tarjeta en `lab_pns_ai_3973_14`

Contexto `lab_pns_ai_3973` (el del final del bloque 2).

1. «Comprobar el contexto» con `C=lab_pns_ai_3973`.
2. D46 con el 32 (sin commit; savepoints deshechos):

   ```bash
   bash ~/pns_ai_3973/fase4/lab/rama_require_settings.sh; echo "código $?"
   ```

   Esperado: «parche 32 activo en el código cargado» y cuatro líneas `→ OK`:
   - sin Ajustes, campo: propuesta «rechazada en la validación» (`safe_plan_validate.py:198-202`), operación
     `confirmed`, ejecución «AccessError de _require_settings»;
   - sin Ajustes, vista: propuesta «aceptada», operación `confirmed`, ejecución «AccessError de _require_settings»;
   - con Ajustes, vista: propuesta «aceptada», operación `confirmed`, ejecución «ok (comment readonly en la vista de
     prueba: antes no, después sí; vistas heredadas 1)»;
   - con Ajustes, campo: propuesta «aceptada», operación `confirmed`, ejecución «ok (required en el registro: antes no,
     después sí; ir.model.fields no persistido (campo de módulo))».

   «ok» exige el valor de éxito y el efecto, mirado dentro del savepoint; sin el efecto sale «ok SIN EFECTO» (DISTINTO).
   Un error devuelto en lugar de lanzado se clasifica igual que la excepción.

   «D46 FIN 4/4 como se espera (con el 32 …)», código 0.
3. D46 con N32 (el script cambia `pns_ai_mcp/models/ai_trusted_action.py` en la copia de trabajo durante la pasada y lo
   restaura; el archivo debe estar sin cambios en git):

   ```bash
   bash ~/pns_ai_3973/fase4/lab/rama_require_settings.sh --sin-32; echo "código $?"
   ```

   Esperado: «N32 aplicada: SHA-256 antes 11d9877f96a230285e8cfb1aba7dd22c791bd152d388e1e659195959d75d33d1, con N32 …»;
   «parche 32 NEUTRALIZADO (N32) en el código cargado»; las mismas cuatro líneas `→ OK`; «D46 FIN 4/4 … (con N32 …)»;
   «N32 restaurada: SHA-256 11d9877f…33d1, IGUAL al de antes»; código 0. Después, `git -C ~/GitHub/third_party status
   --short pns_ai_mcp/models/ai_trusted_action.py` no muestra nada.
4. Reintento de la tarjeta (D47). **Camino forzado:** una tarjeta `high` deja «Confirmar» deshabilitado 5 s desde que se
   pinta (`chatboo_component_v2.js:2373-2393`); una persona no puede pulsar antes. El escenario solo quita `disabled` al
   botón y lanza el clic sobre él (pasa por el manejador normal, `:2494`).
   1. Consultas del escenario (solo lectura). Antes, `bd-lista` (solo lectura) levanta `db` si estaba parado:

      ```bash
      cd ~/GitHub/lab_pns_ai_3973 && odoo-dev 14 bd-lista
      python3 -I ~/pns_ai_3973/fase4/lab/lab_cdp.py sqlprueba --escenario tarjeta; echo "código $?"
      ```

      Esperado: «Consultas del escenario tarjeta: todas OK», «operaciones seges_lab47 OK (0 filas)», código 0.
   2. Plantar, con el web parado. **Escribe** (pide «s/N»):

      ```bash
      bash ~/pns_ai_3973/fase4/lab/tarjeta_plantar.sh; echo "código $?"
      ```

      Esperado: `P47 PLANTADA op=… contacto=… usuario=12 …`, la hora de creación y la de caducidad (UTC y local),
      código 0. **El escenario se lanza antes de 15 min desde el plantado** (`pns_ai_mcp/constants.py:7`); el
      escenario lo comprueba y no pulsa nada si queda menos de 1 min (código 9).
   3. Credenciales, carpeta de salida y escenario (órdenes 1 a 4 del laboratorio automatizado del procedimiento):

      ```bash
      export LAB_LOGIN=seges_int@example.com; read -rsp "Contraseña de seges_int: " LAB_PASSWORD; echo; export LAB_PASSWORD; echo "LAB_LOGIN=$LAB_LOGIN · LAB_PASSWORD con ${#LAB_PASSWORD} caracteres"
      LAB_SALIDA=~/pns_ai_3973/fase4/lab/salida_tarjeta_$(date +%Y%m%d-%H%M%S); mkdir "$LAB_SALIDA"
      bash ~/pns_ai_3973/fase4/lab/lab_auto.sh "$LAB_SALIDA" --escenario tarjeta
      unset LAB_LOGIN LAB_PASSWORD; env | grep -c '^LAB_\(LOGIN\|PASSWORD\)='
      ```

      Esperado del bloque `== escenario tarjeta`:
      - «SQL antes: operación … pendiente, high, del uid 12, sin ejecutar; caduca en … s»;
      - «clic FORZADO: botón deshabilitado antes del clic sí; con cuenta atrás sí»;
      - en `== tarjeta (peticiones)`: «tarjeta pintada por /verification/pending (con token): sí»; «tras el clic:
        /confirm 2, /execute 1, /pending sin peek 0, /pending con peek N (bandeja, informativo), otras 0»; «primer
        /confirm: too_soon, a X s del pintado» con X < 5; «segundo /confirm: éxito, Y s después del rechazo» con Y entre
        5,4 y 7,0 (`_retryRefusedCard`, `chatboo_component_v2.js:2275-2281`, espera 5,5 s); «mismo token en los dos
        /confirm y en la tarjeta pintada: sí»; «/execute: executed»;
      - «SQL después: estado executed, ejecutada sí, confirmada por el usuario de la sesión sí; contacto 1, comentario
        escrito sí»;
      - log: «bad query» sobre `ai_safe_operation` y «retry 1/5», previsto 1 y 1 (anexo de PNS-26: no son fallo);
        «retry 2/5» o más y «maximum number of tries reached», 0;
      - «escenario tarjeta: como se espera»; «Código final 0: todo como se espera».

      Las peticiones con `peek` son de la bandeja: tras cada respuesta de `/confirm`, `_updateSystrayBadge`
      (`chatboo_component_v2.js:2426` → `:3410-3419`) avisa a la bandeja, que pide `/verification/pending` con
      `peek: true` (`chatboo_systray.js:67-73` → `:262-268`). Solo cuentan, no generan token: se informan, no son fallo.
      Fallo sería un `/verification/pending` **sin** `peek` tras el clic.
   4. Recuentos del log guardado (orden 5 del procedimiento, con el nombre que imprime «Log guardado:»).
   5. Borrado, con el web parado (lo deja así `lab_auto.sh`). **Escribe** (pide «s/N»):

      ```bash
      bash ~/pns_ai_3973/fase4/lab/tarjeta_borrar.sh; echo "código $?"
      ```

      Esperado: «P47 BORRADA operaciones=1 contactos=1 quedan=0», código 0.

## Al acabar

- Cada `arrancar` de la guía, con su fila en el registro de laboratorios del procedimiento (hora de arranque y parada,
  C, log guardado). El de `lab_auto.sh` lo hace el propio script (guardar el log, C y `parar`).
- Resultados al plan y al registro de parches: por punto, OK/FALLO y los recuentos; los logs, solo por su nombre.

## Limpieza final

Borrar BD es decisión de Sergio (`bd-borrar` pide confirmación).

```bash
cd ~/GitHub/lab_pns_ai_3973 && odoo-dev 14 bd-borrar lab_p2a_879_14 && odoo-dev 14 bd-borrar lab_p2b_879_14 && odoo-dev 14 bd-lista
rm -rf ~/GitHub/lab_pns_ai_879 ~/GitHub/lab_pns_ai_973f
docker image rm odoo-dev:14-lab_pns_ai_879 odoo-dev:14-lab_pns_ai_973f
cd ~/GitHub/lab_pns_ai_3973 && odoo-dev 14 arrancar
```

Después del último `arrancar`, «Al acabar corto» con `--lab lab_pns_ai_3973 --bd lab_pns_ai_3973_14`. Esperado: en
`bd-lista` ya no están las dos BD; `docker image ls` ya no muestra las dos imágenes; el contexto vuelve a ser
`lab_pns_ai_3973` (`odoo-dev 14 estado`).

## Scripts y SHA-256

Copias de referencia en esta carpeta; se usan desde `~/pns_ai_3973/fase4/lab/` y antes de usarlos `sha256sum` debe dar
estos valores.

| Archivo | Uso | SHA-256 |
|---|---|---|
| `lab_auto.sh` | Laboratorio automatizado; `--lab`, `--bd` (D44) y `--escenario tarjeta` (D47) | `322a9adec5f3d61790a026181b252407441e7e8b5af9ae1217af7d1044a5180d` |
| `lab_cdp.py` | CDP, C y SQL; `--lab`/`--bd` y el escenario tarjeta | `1520b3425da299ddbbd8305f21e7a1a9246a1b231adba0b0982e63d2372b940d` |
| `prueba_lab_auto.sh` | Prueba de `lab_auto.sh` sin Odoo (49 PASA) | `a5aace954d88687e9d3af645df32422a691ac126054e36c33b9fb9f910f882b3` |
| `rama_carpetas.sh` | Bloque 0: carpetas de laboratorio (escribe en `~/GitHub`) | `e1101f0307256c2ef2bc497c615a92a0bd8bbd7b25c11b2ded4ffdee16cbb215` |
| `rama_plantar.sh` | Bloques 1 y 2: foto y P-11/P-14 (escribe) | `85764a11adb6afc602e5df4a5b1b96e5cec137de1f47f6d97760249d88c91019` |
| `rama_comprobar.sh` | P-2, P-11 y P-14 (solo lectura) | `5e09c67926543713f55cbda5e5d409d25958585af24571c6ecad1ed5be2d9435` |
| `rama_crons.sh` | D43, siguiente pasada (escribe) | `95d55e713ee56a959664acdc50b6efc55f008bad6fbd836d9faa175549a10c18` |
| `rama_corregir_p2b.sh` | P-2 (b), corrección a mano (escribe) | `943c7d8777834c7d34bee83a492b3c04850e66adcb2d440eca5d4fb8811e074a` |
| `p39_lab.sh` | Bloque 3: parche 39 (sin commit) | `b9673941724e0145b829efb117223f43f9053a121bb2b2c164b7160c31f3bffb` |
| `rama_require_settings.sh` | Bloque 4: D46, con y sin el 32 (sin commit) | `022c571fc9144f9953297ea201f8031750dceb4d731cacd0898be80219ef3ab7` |
| `tarjeta_plantar.sh` | Bloque 4: D47, plantar (escribe) | `bd12a0a2d827ac4c809c1a4c73873c57fc615c71b5b771c08639cdb38e436cb5` |
| `tarjeta_borrar.sh` | Bloque 4: D47, borrar (escribe) | `094432e7df11ad3ea8b8aa420c8197b56a5ee2993f4dea13e11eee641784493d` |
