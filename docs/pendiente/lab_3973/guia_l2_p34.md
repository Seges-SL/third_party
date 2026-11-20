# Guía del laboratorio L2 del parche 34 en `lab_pns_ai_3973_14` (6.ª versión, 17/11/2026)

- Rama `14.0-pns-ai-3973` en `a746cee`. Diseño aprobado: D20 a D24 y las decisiones del 16 y 17/11.
- **Novedad de la 6.ª versión:** L2 se hace con **`models/gemini-3.5-flash-lite`** (fila 25). La cuota gratuita de
  Gemini es de 20 peticiones al día por modelo y estaba agotada en 3.6 flash y en 3.5 flash (`ai_log` confirma que
  las peticiones siguen a `model_id`). Decisión de Sergio del 17/11: excepción a la decisión 6 de la E3′ («Design» sin
  `lite») solo para este laboratorio, anotada en el registro. Si `lite` también llega a su límite a mitad, el script
  pregunta si continúa (`N`). `p34_modelo.sh` acepta ahora `poner lite`, `poner flash` y `devolver` desde
  cualquiera de los tres modelos conocidos.
- **5.ª versión (superada):** L2 se hace con **`models/gemini-3.5-flash`** (decisión de Sergio del 17/11, para no
  esperar a la cuota de `gemini-3.6-flash`). `p34_modelo.sh` cambia `model_id` del proveedor 2 de 30 a 24 antes del
  laboratorio y lo devuelve después (`model_name` es `related` de `model_id.name`). 3.5 flash no es `lite`: la
  decisión 6 de la E3′ («Design» solo en modelos que no sean `lite`) se cumple.
- Historia de los intentos de hoy: en la 4.ª versión de la guía (`guia_l2_p34.md`).
- **Forma:** orden → resultado esperado → siguiente orden. Si un resultado no es el esperado, no sigas y pásame la
  salida de esa orden: ninguna imprime contenidos.

## SHA-256

| Archivo | SHA-256 | Estado |
|---|---|---|
| `lab_l2_p34_v6.zip` | `5bc82d523433af32c7b085c0fcdc9be44c382ccc381263b1c041f52417a38315` | descarga |
| `p34_modelo.sh` | `f331facfea2d3c34d7ce285b3b990a918b03e5607b57b1d81e2b2871ec18da0c` | 2.ª versión, en el zip; escribe |
| `prueba_p34_modelo.sh` | `b4fbce683a4b85acb1558bb7fffe629b92ca210133e3a407606464af6fbaf97b` | 2.ª versión, en el zip |
| `lab_cdp.py` | `2593fc4e0b5fc6103c97593e6fde3ae5cbcfffd65b0345e5fcdf0e75bfe645eb` | 4.ª versión, ya instalada |
| `lab_auto.sh` | `54dfa24d0ef1c985aa185f0a0531dd2e7cd98a70cdd15594526849b8fcf7646b` | ya instalado |
| `prueba_lab_auto.sh` | `d73022db30855aed57396bcfe7e09dfb28087ea8aad63aac66b38a1d80fb9e03` | ya instalado |
| `p34_plantar.sh` | `d213220e987d5ef46b2e8314d0d370f28437513212fd997f5429e31b3fd41ac3` | ya instalado; escribe |
| `p34_borrar.sh` | `934b7ef1940de86a34d52fe7951972b3009e5fd12db91bf7de5664f4e2b1600f` | ya instalado; escribe |
| `prueba_p34_scripts.sh` | `970fcd7d8a89d42a13a96ed9a6a671cd7edcb1313cbc9b58bc28dd2d0318ef0f` | ya instalado |

Los `p34_modelo.sh` (`3b810247…`) y `prueba_p34_modelo.sh` (`bf904a82…`) anteriores se guardan en `antes_20261117d/`;
el `lab_cdp.py` de la 3.ª versión ya está en `antes_20261117c/`.

## Qué está probado y qué no

- **En el entorno de Claude, sin Odoo:** autoprueba de `lab_cdp.py` 76 PASA (75 sin `--js`); `prueba_lab_auto.sh`
  32 PASA; `prueba_p34_scripts.sh` 15 PASA; `prueba_p34_modelo.sh` 21 PASA (estado, `poner lite`, `poner flash`, `devolver`
  desde `lite`, «ya estaba», modelo de partida desconocido, otra BD, proveedor inactivo, modelo destino ausente, fallo
  del `write`, órdenes no válidas y que tras cada rechazo no quede nada escrito).
- **En tu equipo, en los intentos de hoy:** todo `lab_cdp.py` salvo la pregunta de «proveedor caído», más
  `lab_auto.sh` con `docker ps`, `sqlprueba` y los dos scripts de D24.
- **Validado en tu equipo:** `p34_modelo.sh poner` (1.ª versión) contra `odoo-dev 14 shell`, y que las peticiones
  siguen a `model_id` (`ai_log`). `poner lite` y `devolver` desde `lite`, primer uso real.

## Parte A: instalar y probar (no toca Odoo)

### 1. Comprobar la descarga

```bash
sha256sum ~/Descargas/lab_l2_p34_v6.zip
```

**Esperado:** `5bc82d523433af32c7b085c0fcdc9be44c382ccc381263b1c041f52417a38315`. Si lo descargaste dos veces, el bueno es el que tenga ese SHA-256.

### 2. Guardar los anteriores e instalar (escribe solo en `~/pns_ai_3973/fase4/lab/`)

```bash
cd ~/pns_ai_3973/fase4/lab && mkdir antes_20261117d && cp -p p34_modelo.sh prueba_p34_modelo.sh antes_20261117d/ && unzip -o ~/Descargas/lab_l2_p34_v6.zip -d ~/pns_ai_3973/fase4/lab/ && sha256sum antes_20261117d/* p34_modelo.sh prueba_p34_modelo.sh lab_cdp.py
```

**Esperado:** en `antes_20261117d/`, `3b810247…` y `bf904a82…`; después, `f331facf…`, `b4fbce68…` y `2593fc4e…`.

### 3. Prueba sin Odoo (segundos; `lab_cdp.py` no cambia)

```bash
cd ~/pns_ai_3973/fase4/lab && bash prueba_p34_modelo.sh | tail -1
```

**Esperado:** `Prueba de p34_modelo.sh: 21 PASA`.

## Parte B: preparar el laboratorio

### 4. Estado (solo lectura)

Comprueba antes que el laboratorio anterior terminó (su terminal imprimió `código N`): su «Al acabar» para la BD.

```bash
cd ~/GitHub/lab_pns_ai_3973 && odoo-dev 14 estado | tail -4 && odoo-dev 14 bd-lista
```

**Esperado:** ningún contenedor `web` en marcha (la BD puede estarlo) y `lab_pns_ai_3973_14` en la lista. Ninguna
pestaña de `localhost:8169` en tu navegador normal.

### 5. Plantar el lienzo de D24 (**escribe**: crea una sesión)

```bash
bash ~/pns_ai_3973/fase4/lab/p34_plantar.sh
```

Responde `s`. **Esperado:** `P34 PLANTADA id=<n> usuario=12 canvas_rev=1 bytes=12675`.

### 6. Poner `lite` en el proveedor 2 (**escribe**: `model_id` del proveedor 2)

```bash
bash ~/pns_ai_3973/fase4/lab/p34_modelo.sh poner lite
```

Responde `s`. **Esperado:** `P34 MODELO antes=models/gemini-3.5-flash ahora=models/gemini-3.5-flash-lite model_id=25`
(el proveedor sigue en 3.5 flash desde el intento anterior; si ya lo devolviste, `antes=models/gemini-3.6-flash`).
Con `P34 ERROR: …` no se ha escrito nada: pásame la línea.

### 7. Comprobar consultas y modelo (solo lectura)

```bash
python3 -I ~/pns_ai_3973/fase4/lab/lab_cdp.py sqlprueba; echo "código $?"; bash ~/pns_ai_3973/fase4/lab/p34_modelo.sh estado
```

**Esperado:** once líneas `OK`, con `proveedor 2 … (activo sí, design sí)`, `contacto hostil (D23) … (0)` y
`sesión plantada (D24) … (1)`; `Consultas del escenario p34: todas OK`; `código 0`; y
`P34 MODELO estado proveedor=2 modelo=models/gemini-3.5-flash-lite model_id=25`.

## Parte C: el laboratorio

### 8. Credenciales

```bash
export LAB_LOGIN=seges_int@example.com; read -rsp "Contraseña de seges_int: " LAB_PASSWORD; echo; export LAB_PASSWORD; echo "LAB_LOGIN=$LAB_LOGIN · LAB_PASSWORD con ${#LAB_PASSWORD} caracteres"
```

### 9. Carpeta de salida nueva

```bash
LAB_SALIDA=~/pns_ai_3973/fase4/lab/salida_34_L2_$(date +%Y%m%d-%H%M%S); mkdir "$LAB_SALIDA" && echo "$LAB_SALIDA"
```

### 10. Laboratorio (llama al proveedor; entre 15 y 60 minutos)

```bash
bash ~/pns_ai_3973/fase4/lab/lab_auto.sh "$LAB_SALIDA" --escenario p34 --visible 2>&1 | tee "$LAB_SALIDA/salida.txt"; echo "código ${PIPESTATUS[0]}"
```

| Momento | Qué ves | Qué haces |
|---|---|---|
| Inicio | `Contenedor web parado (docker ps): se arranca.` y `C: OK` | Nada. No uses la ventana del laboratorio |
| Paso 0 | `proveedor 2: activo sí; con «Design» sí`, `sesiones plantadas (D24): 1` | Nada |
| **Pausa 1** | Segunda ventana en el login; la terminal pide tres cosas | (1) entra como administrador; (2) crea el contacto de abajo; (3) en el proveedor 2 quita «Design» y guarda. **No toques el modelo.** Intro |
| T1 y T1b | Por turno: burbuja en vivo y tras recargar, SQL, `page_tab`, log del motor | Nada |
| **Pausa 2** | Volver a marcar «Design» | Márcalo en el proveedor 2 y guarda. Intro |
| V2, 5b′, 6c, 6d′ | Igual; en 6d′, antes, `control (informativo): alert() …` | Nada |
| **Pausa 3** | Archivar el contacto | Acción → Archivar. Intro |
| Final | `== p34 resumen`, `== Al acabar`, `C: OK`, `Código final N: …` | Nada |

**Contacto de D23** (cópialo tal cual en Nombre):

```
Seges P34 </script><script>alert('P34')</script>
```

**Preguntas posibles:**
- `… falló el proveedor … ¿Repetir el paso? (s/N)`: `s` una vez.
- `El proveedor ha fallado en 2 pasos seguidos. ¿Continuar con los pasos que quedan? (s/N)`: `N`. El resto sale
  «NO EJECUTADO (proveedor caído)» y pasa a la limpieza.
- En 6d′, `rechazo por otro motivo (…) … ¿Repetir el paso? (s/N)`: `s`.

**Esperado en el resumen:**

```
  T1      OK              rechazo con aviso en línea llana, en vivo y tras recargar
  T1b     OK              rechazo con aviso en línea llana, en vivo y tras recargar
  V2      OK              página creada y burbuja sin aviso
  5b′     OK              canvas_rev 1; valor hostil escapado; sin alert() ni aviso
  6c      OK              canvas_rev 2; valor hostil escapado; sin alert() ni aviso
  6d′     OK              rechazo por valor en crudo, canvas_rev igual y aviso en línea llana
```

| Código | Significa | Siguiente |
|---|---|---|
| 0 | Los seis pasos, como se prevé | Paso 11 |
| 8 | Algún paso `NO CONCLUYENTE` o `NO EJECUTADO`: depende del modelo o del proveedor | Paso 11; con el resumen decidimos |
| 1 | Alguna `INCIDENCIA`: el aviso o el lienzo no son los previstos | Paso 11 y me pasas el resumen |
| 9 | Una condición o pausa sin confirmar por SQL, o el chat no se pudo manejar | Paso 11 y me pasas el resumen |
| 3 | Otra BD | «Si aparece otra BD» del procedimiento |
| 10 | `web` en marcha o `docker ps` sin responder: no se arrancó nada | «Al acabar» y repetir el paso 10 |

**Pase lo que pase, sigue con la limpieza (pasos 14 a 18).**

### 11. Credenciales fuera (debe imprimir 0)

```bash
unset LAB_LOGIN LAB_PASSWORD; env | grep -c '^LAB_\(LOGIN\|PASSWORD\)='
```

### 12. Resumen del escenario (me lo pegas)

```bash
sed -n '/== p34 paso 0/,$p' "$LAB_SALIDA/salida.txt"
```

### 13. Recuentos del log guardado

```bash
LOG_LAB=$(ls -t ~/odoo-dev/14.0/logs/servidor-*.log | head -1); echo "$(basename "$LOG_LAB")"; wc -l < "$LOG_LAB"; echo "WARNING/ERROR/CRITICAL por nivel, BD y logger:"; grep -oE ",[0-9]{3} [0-9]+ (WARNING|ERROR|CRITICAL) [^ ]+ [^ ]+" "$LOG_LAB" | awk '{print $3, $4, $5}' | sort | uniq -c; echo "Traceback: $(grep -c 'Traceback' "$LOG_LAB")"; echo "bad query: $(grep -c 'bad query' "$LOG_LAB")"; echo "«key=»: $(grep -c 'key=' "$LOG_LAB")"; echo "primera y última hora: $(grep -oE '^[^|]*\| [0-9-]+ [0-9:]+' "$LOG_LAB" | head -1 | grep -oE '[0-9-]+ [0-9:]+$') · $(grep -oE '^[^|]*\| [0-9-]+ [0-9:]+' "$LOG_LAB" | tail -1 | grep -oE '[0-9-]+ [0-9:]+$')"
```

**Esperado:** el log que imprimió «Log guardado:», 0 «bad query» y 0 «key=».

## Parte D: limpieza

### 14. Borrar la sesión plantada (**escribe**)

```bash
bash ~/pns_ai_3973/fase4/lab/p34_borrar.sh
```

Responde `s`. **Esperado:** `P34 BORRADA sesiones=1 quedan=0`.

### 15. Devolver 3.6 flash al proveedor 2 (**escribe**)

```bash
bash ~/pns_ai_3973/fase4/lab/p34_modelo.sh devolver
```

Responde `s`. **Esperado:** `P34 MODELO antes=models/gemini-3.5-flash-lite ahora=models/gemini-3.6-flash model_id=30` (o
`P34 MODELO ya estaba: models/gemini-3.6-flash …`).

### 16. Estado final (solo lectura)

```bash
python3 -I ~/pns_ai_3973/fase4/lab/lab_cdp.py sqlprueba; echo "código $?"; bash ~/pns_ai_3973/fase4/lab/p34_modelo.sh estado
```

**Esperado:** `proveedor 2 … (activo sí, design sí)`, `contacto hostil (D23) … (0)`, `sesión plantada (D24) … (0)`,
`código 0` y `P34 MODELO estado proveedor=2 modelo=models/gemini-3.6-flash model_id=30`.

### 17. D14 después (solo lectura)

```bash
cd ~/GitHub/lab_pns_ai_3973 && odoo-dev 14 shell < ~/pns_ai_3973/fase4/29/d14_medicion.py > "$LAB_SALIDA/d14_despues.txt" 2>&1; grep '^D14' "$LAB_SALIDA/d14_despues.txt"; echo "antes:"; cat ~/pns_ai_3973/fase4/29/d14_resultado.txt
```

**Esperado:** 0 con DATA ilegible. El número de diseños puede subir por las páginas de V2 y 5b′.

### 18. Parar

```bash
cd ~/GitHub/lab_pns_ai_3973 && odoo-dev 14 parar && odoo-dev 14 estado | tail -3
```

**Esperado:** ningún contenedor en marcha.

## Después

- Me pegas las salidas de los pasos 10 (código), 12, 13, 16 y 17.
- Con eso, el prompt del agente para la fila del registro (L2 con `gemini-3.5-flash-lite`, excepción a la decisión 6), el bloque del procedimiento con
  estos SHA-256, la copia de los ocho scripts a `docs/pendiente/lab_3973/` y el `[DOC]`. Los commits, tú con GitHub
  Desktop.
