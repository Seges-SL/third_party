# Instalación en LIYBEN: pns_base 1.2.32, pns_ai_mcp 3.1.782 y pns_ai_chatboo 2.1.453 (Odoo 14)

- **Rama:** `14.0-pns-ai-3` (commit `578859b`) · **Fecha de la instalación:** 2026-10-16, Sergio con
  Claude · **Reunión de seguimiento:** lunes 19/10/2026 (guion en el §5).
- **Entorno:** base de datos **LIYBEN**, servicio **`odoo14_server`** (imagen `odoo-web`) con su
  PostgreSQL **`odoo14_db`**, dominio `https://liyben.com`. Es el VPS del staging (plan de staging, §1).
- **Origen:** [plan de staging](plan_staging_pns_ai.md), §8 (camino A, N6), con las condiciones de N7.
  Configuración según la [guía de configuración](../specs/guia_configuracion_pns_ai.md); este registro
  remite a sus secciones (§) y no las copia.
- **Otras fuentes:** [decisiones](pns_ai_decisiones.md) (N2, N3, N4, N6, N7, N8, D2, D9, D10, D20, D46,
  PB-2), [parches](parches_pns_ai.md) (1 a 6) y [seguimiento](seguimiento_informe_pns_ai.md).
- Lo que no tiene respaldo en lo comprobado está marcado **«Pendiente»** (§6).
- **Sin secretos en este registro:** ni contraseñas, ni claves MCP, ni claves de proveedor, ni PIN.

## Índice

1. Resumen
2. Comprobaciones previas (solo lectura)
3. Ejecución (16/10/2026)
4. Decisiones provisionales (16/10/2026)
5. Guion para la reunión del lunes
6. Pendiente
7. Vuelta atrás

---

## 1. Resumen

Instalación **nueva** (no actualización; los `pns_*` de 3.1.486 se desinstalaron el 15/10/2026) de
`pns_base` 1.2.32, `pns_ai_mcp` 3.1.782 y `pns_ai_chatboo` 2.1.453 con los **parches 1 a 6** (N2
revisada), desplegados con la rama `14.0-pns-ai-3` en el clon de `third_party` del VPS (opción B, §4).

| Paso | Resultado |
|---|---|
| Comprobaciones previas (§2) | CONFORME, con dos observaciones: usuarios de portal activos (§4) y gestor de bases de datos con el valor por defecto (infraestructura, no se toca) |
| Copia previa de la BD y del filestore (§3.1) | HECHA |
| Código: rama `14.0-pns-ai-3` en `578859b` (§3.2) | CONFORME |
| Nginx: `/chatboo/stream` y `/mcp` (§3.3) | CONFORME |
| Instalación y log (§3.4) | CONFORME |
| Retención, política de URL y grupos (§3.5) | CONFORME |
| Claves MCP (§3.5) | **Pendiente** |
| Proveedor y cadena del agente | **Pendiente** (reunión, §5 b) |
| Verificación con el proveedor (parches 5 y 6) | **Pendiente** (reunión, §5 d) |

Hasta que haya proveedor, Chatboo está instalado pero no responde: hay **0 proveedores**.

---

## 2. Comprobaciones previas (solo lectura)

### 2.1 Servicios y base de datos (D9)

- `odoo14_server` (imagen `odoo-web`) y `odoo14_db` (**PostgreSQL 15.18**).
- En `odoo14_db` solo existe la base de datos **LIYBEN**: el parche de `http_patch.py` no alcanza a
  otras bases (D9; guía §3). **Conforme.**

### 2.2 `odoo.conf` (guía §4.3, D15)

| Parámetro | Valor |
|---|---|
| `workers` | 2 |
| `limit_time_real` | 2400 |
| `limit_time_cpu` | 1200 |
| `limit_memory_hard` | ~2 GB |
| `proxy_mode` | `True` |
| `dbfilter` / `list_db` | sin definir |

**Observación de infraestructura (no se toca):** sin `dbfilter` ni `list_db`, con una sola base de
datos, el gestor de bases de datos queda con el valor por defecto.

### 2.3 Código

- `/opt/odoo/addons/custom/third_party` es un **clon propio de `Seges-SL/third_party`**, rama `14.0`
  (`f63d5a1`), limpio, clonado solo con la rama `14.0` (`remote.origin.fetch = refs/heads/14.0`).
- Propietario: **UID 101** (`odoo` dentro del contenedor; en el host se ve como `messagebus`).
- `/opt/odoo` es a su vez un repositorio de infraestructura (`odoo-infra-14`).
- La rama `14.0-pns-ai-3` frente a `f63d5a1`, **fuera de `pns_*` y `docs/`**: solo `.claude/`,
  `.vscode/`, `.pylintrc`, `ruff.toml`, `CLAUDE.md` y `.gitignore`. **Ningún módulo de LIYBEN cambia.**

### 2.4 Módulos y usuarios

- `pns_*` desinstalados desde el 15/10/2026 (plan de staging, §2.4).
- **PB-2:** ningún módulo de LIYBEN (OCA/web, LIYBEN, `vertical-instaladores`) sobrescribe
  `_notifyInvalidFields` ni `_saveMultipleRecords`. **Conforme.**
- **Usuarios de portal activos: 18.** Último acceso del más reciente: 12/2024 (la mayoría, 2023).
  Registro web: `b2b` (solo por invitación). Desviación de N7: ver §4.

### 2.5 Proxy y disco

- Nginx de `liyben.com` (`/etc/nginx/conf.d/odoo.conf`, upstream `odoo`): **no tenía**
  `/chatboo/stream` ni `/mcp`.
- Logs: `/mcp` solo recibía escaneos automáticos (GET 404) y dos 200 aislados sin patrón de cliente
  MCP.
- Disco: **11 GB libres** (86 % ocupado).

---

## 3. Ejecución (16/10/2026)

### 3.1 Copia previa

En `/opt/odoo/backups`:

| Archivo | Tamaño | Comprobación |
|---|---|---|
| `LIYBEN_antes_instalar_pns_20261016.dump` | 46 MB | `pg_restore -l` correcto |
| `LIYBEN_filestore_20261016.tar.gz` | 431 MB | — |

El filestore está en `/opt/odoo/odoo-web-data/.local/share/Odoo/filestore/LIYBEN` (`data_dir` por
defecto).

### 3.2 Código: rama `14.0-pns-ai-3` en el clon (opción B)

1. Todas las órdenes de git **como el UID 101** (`sudo -u messagebus env HOME=/tmp git …`), para no
   cambiar el propietario de los archivos.
2. `fetch` con refspec explícito, porque el clon solo sigue `14.0`:
   `origin 14.0-pns-ai-3:refs/remotes/origin/14.0-pns-ai-3`.
3. `checkout -b 14.0-pns-ai-3 578859b` **sin `--track`** (el `--track` falla por el mismo motivo).
4. Comprobaciones (**conformes**):
   - rama `14.0-pns-ai-3` en `578859b`, `status` limpio;
   - **10 líneas** de «Seges: parche de compatibilidad» (orden de la cabecera de
     [parches_pns_ai.md](parches_pns_ai.md));
   - hashes de árbol de `pns_base`, `pns_ai_mcp` y `pns_ai_chatboo` **iguales a los de `63ee2dc`**
     (lo validado en staging).
5. La rama `14.0` **no se ha tocado**.

### 3.3 Nginx (guía §4.3, D20)

1. Copia: `/etc/nginx/conf.d/odoo.conf.bak-20261016`.
2. En el `server` HTTPS de `liyben.com`, **antes de `location /`**:
   - `location ^~ /chatboo/stream`: `proxy_pass http://odoo`, `proxy_buffering off`,
     `proxy_cache off`, `gzip off`, `proxy_read_timeout 900s`;
   - `location ^~ /mcp { return 404; }` (D20: sin cliente MCP externo).
3. `nginx -t` correcto y recarga (`reload`).
4. Comprobado: `POST /mcp` → 404; `liyben.com/web/login` → 200; `pns.liyben.com/web/login` → 200.

### 3.4 Instalación (guía §6)

1. Reinicio de `odoo14_server` sin errores.
2. Instalación de **AI Engine** y **Chatboo** desde Aplicaciones; nuevo reinicio.
3. Comprobaciones (**conformes**):
   - módulos `installed` en `14.0.1.2.32`, `14.0.3.1.782` y `14.0.2.1.453`;
   - **seis crons activos** con `numbercall` -1 (intervalos 5 min, 1 h, 1 h, 1 día, 5 min, 1 h);
   - 0 proveedores;
   - log sin `Traceback`, `ERROR` ni `CRITICAL`.

### 3.5 Configuración (guía §7, §9 y §11)

| Ajuste | Valor |
|---|---|
| `pns_ai_mcp.log_retention_days` | 30 |
| `pns_ai_chatboo.history_retention_days` | 30 |
| `url_access_policy` | `whitelist_only` |

- **Usuarios:** `fran.odoo@seges.es` y `sguerrero@liyben.com` con `group_system`, `group_ai_admin`,
  `group_ai_writer`, `group_ai_external_url` y `group_ai_conversational`.
- Hay un **tercer `ai.mcp.user`** (`soporte@liyben.com`) sin clave ni PIN.
- **Claves MCP: Pendiente** (§5 a).
- **Ningún PIN generado** (N4).

---

## 4. Decisiones provisionales (16/10/2026)

Decisiones de Sergio, provisionales hasta la reunión (§5 f).

| Tema | Decisión provisional | Impacto | A decidir en la reunión |
|---|---|---|---|
| **Usuarios de portal** (N7) | Se mantienen los 18 | Desviación de la condición «sin portal» de N7 (N3 b; guía §2.1). PNS-83 cubierto porque no se usa la mesa de PIN; **PNS-90 y PNS-91 abiertos** | Propuesta: **archivarlos** (sin acceso desde 12/2024). Antes de la demo, la consulta del §5 e) |
| **Proveedor** (N8, D10) | Gemini `gemini-3.5-flash-lite` | **D10 pendiente:** datos reales de LIYBEN hacia un proveedor externo; condiciones de uso de datos del nivel gratuito por comprobar | Propuesta: clave nueva en otro proyecto de Google y cadena con dos proveedores (`3.5-flash-lite` y, de respaldo, `3.5-flash`) |
| **Despliegue del código** | Rama `14.0-pns-ai-3` en el clon (opción B, §3.2) | El clon no está en `14.0` | Integrar la rama en `14.0` (PR) y volver el clon a `14.0` |

---

## 5. Guion para la reunión del lunes

En este orden. Los pasos a) a d) se hacen en la interfaz de LIYBEN o en el VPS; e) es solo lectura.

**a) Claves MCP.** Si no están generadas, generarlas con el **asistente de la ficha** del usuario MCP
(guía §7.1). **Nunca «Regenerate PIN»** (N4; incidencia del staging, plan de staging §6.1).

**b) Proveedor y cadena del agente (guía §8 y §8.1).**
1. Clave de Gemini (según lo que se decida en el §4).
2. Dos proveedores **creados desde cero**, cada uno con:
   - protocolo `openai`;
   - endpoint `https://generativelanguage.googleapis.com/v1beta/openai/chat/completions`;
   - capacidades **Conversation + Vision**, sin audio;
   - **Test Connection** correcto.
3. Cadena del agente Chatboo: primero **Flash Lite** y después **Flash**.

**c) Lista blanca (guía §9).** Borrar los dos dominios de Open-Meteo de la lista blanca (quedan 2
activos).

**d) Verificación.**
1. Una pregunta con **consulta de datos** (parche 5).
2. Una **imagen pequeña adjunta**, fin de turno **sin recargar** la página, y después esta consulta
   (parche 6). Criterio: **ninguna fila `idle in transaction` ni esperas de lock**.

```bash
docker exec -i odoo14_db sh -c 'psql -U "$POSTGRES_USER" -d LIYBEN' <<'SQL'
SELECT pid, state, xact_start, wait_event_type, wait_event, pg_blocking_pids(pid) AS bloqueado_por, left(query,120) AS query FROM pg_stat_activity WHERE datname='LIYBEN' AND state <> 'idle' ORDER BY xact_start;
SQL
```

**e) Detección de uso por portal antes de la demo.** Filas creadas o modificadas por usuarios de
portal (solo lectura). Criterio: sin filas.

```bash
docker exec -i odoo14_db sh -c 'psql -U "$POSTGRES_USER" -d LIYBEN -At' <<'SQL'
SELECT 'fetch_cache', c.id, c.create_date, c.write_date FROM ai_fetch_cache c JOIN res_users u ON u.id IN (c.create_uid, c.write_uid) WHERE u.share;
SELECT 'whitelist', w.id, w.create_date, w.write_date FROM ai_url_whitelist w JOIN res_users u ON u.id IN (w.create_uid, w.write_uid) WHERE u.share;
SQL
```

**f) Decisiones para el jefe.**
- **D10:** proveedor y datos reales de LIYBEN.
- **D46:** quién tiene acceso.
- **Usuarios de portal** (N7): mantenerlos o archivarlos (§4).
- **Proveedor definitivo:** OVH en estudio (N8).
- **Presupuesto.**
- **Envío del informe al fabricante** (D2).
- **Limpieza del staging** (plan de staging, §9).

Anotar el resultado de cada paso en este documento (§6).

---

## 6. Pendiente

| Tema | Estado | Dónde |
|---|---|---|
| Claves MCP | Pendiente | §5 a |
| Proveedor, clave y cadena del agente | Pendiente | §5 b, §4 |
| Lista blanca (Open-Meteo) | Pendiente | §5 c |
| Verificación de los parches 5 y 6 en LIYBEN | Pendiente | §5 d |
| Uso por portal antes de la demo | Pendiente | §5 e |
| D10, D46, usuarios de portal, proveedor definitivo, presupuesto, D2 | Pendiente (reunión) | §5 f |
| Integrar `14.0-pns-ai-3` en `14.0` (PR) y volver el clon a `14.0` | Pendiente | §4 |
| Limpieza del staging | Pendiente | plan de staging, §9 |
| Resultados de la reunión | | |

---

## 7. Vuelta atrás

Operaciones destructivas: se describen, no se dan listas para pegar. Las decide y hace quien administra
el VPS.

1. **Base de datos:** restaurar `LIYBEN_antes_instalar_pns_20261016.dump` y el filestore de
   `LIYBEN_filestore_20261016.tar.gz` (§3.1); o, como alternativa, desinstalar los módulos.
2. **Código:** `git checkout 14.0` en el clon, **como el UID 101** (§3.2).
3. **Nginx:** restaurar `/etc/nginx/conf.d/odoo.conf.bak-20261016`, comprobar con `nginx -t` y, solo si
   es correcto, recargar.
4. **Odoo:** reiniciar `odoo14_server`.
