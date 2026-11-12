# Pruebas manuales de la fase 2c (parche 36) — rama 14.0-pns-ai-3973

- **Laboratorio:** `lab_pns_ai_3973`, BD `lab_pns_ai_3973_14`, http://localhost:8169
- **Origen:** plan 3973 («Fase 2c — Parche 36») y registro de parches («Parche 36: vistas de revisión y de
  resultado para el AI Administrator sin Ajustes (PNS-103)»).
- **Usuarios:** los de la siembra de la fase 2 ([guía de la fase 2](lab_fase2_3973.md), 1.3 y 1.4), con la
  misma contraseña de laboratorio:

  | Usuario | Grupos | Aquí |
  |---|---|---|
  | `seges_aiadm` | Usuario interno y AI Administrator, sin Ajustes ni Permisos de acceso | positivo |
  | `seges_access` | Usuario interno, Permisos de acceso y AI Administrator, sin Ajustes | positivo |
  | `seges_int` | Usuario interno, AI Conversational, AI Writer y Ventas, sin AI Administrator | negativo |

> **12/11/2026:** el login real de `seges_int` (usuario 12) es `seges_int@example.com`: cambió al poner el
> correo a mano el 11/11 ([guía de la fase 2](lab_fase2_3973.md), 1.3). No se cambia en la BD; los scripts lo
> reciben como argumento.

- **Datos:** solo ficticios. Ningún proveedor importado tiene clave, roles ni un endpoint que salga a la red. No
  exportes ni importes el proveedor de Gemini.

## 1. Preparación (con tu aprobación)

**1.1 Cargar el parche 36 en el laboratorio.** El parche solo cambia el cuerpo de dos métodos Python (sin
campos, vistas, datos ni manifest), así que basta con reiniciar el servidor, sin `-u`. `arrancar` solo no
sirve: hace `docker compose up -d`, que no reinicia un contenedor que ya está en marcha. Por eso se usa
`parar` y después `arrancar`, desde la carpeta del laboratorio para que el contexto siga siendo el suyo:

```sh
cd ~/GitHub/lab_pns_ai_3973 && odoo-dev 14 parar && odoo-dev 14 arrancar
```

- `parar` hace `docker compose down` sin `-v`: las BD (también las de los otros laboratorios) siguen en el
  volumen de PostgreSQL y no se modifican. Solo dejan de estar accesibles durante unos segundos.
- Se espera `==> Odoo 14.0 en http://localhost:8169 · base de datos: lab_pns_ai_3973_14`, con `third_party`
  como copia de trabajo en la rama `14.0-pns-ai-3973`.
- Comprobación: `odoo-dev 14 log 100`, sin `ERROR` al cargar el registro de la BD (al arrancar o, si no
  se precarga, tras la primera petición a la interfaz).
- La BD no está neutralizada: el kit no toca sus crons ni su correo.

**1.2 Archivos JSON, fuera del repo** (por ejemplo, en `~/p36_lab/`; se borran al terminar):

`proveedor_aiadm.json`
```json
[{"name": "Seges P-36 aiadm", "temperature": 0.36,
  "endpoint": "http://127.0.0.1:9/v1/chat/completions"}]
```

`proveedor_access.json`: igual, con `"name": "Seges P-36 access"`.

`usuarios_aiadm.json`
```json
[{"login": "demo", "last_mcp_client_label": "P-36 aiadm"}]
```

`usuarios_access.json`: igual, con `"last_mcp_client_label": "P-36 access"`.

Los proveedores no llevan `roles`: sin un rol de audio no se hace la prueba de voz al guardar (no hay red).

**1.3 Estado antes** (solo lectura):

```sh
docker exec -i odoo-dev-14-db-1 psql -U odoo -d lab_pns_ai_3973_14 <<'SQL'
BEGIN TRANSACTION READ ONLY;
SELECT id, name, active, temperature, write_date FROM ai_provider WHERE name LIKE 'Seges P-36%';
SELECT m.id, u.login, m.last_mcp_client_label, m.write_date
  FROM ai_mcp_user m JOIN res_users u ON u.id = m.user_id WHERE u.login = 'demo';
ROLLBACK;
SQL
```

Se espera: ningún proveedor «Seges P-36» y la fila de `demo` con su etiqueta actual (anótala).

## 2. Positivo: `seges_aiadm`, y después `seges_access`

Cada uno con sus archivos (`*_aiadm.json` o `*_access.json`).

**2.1 Proveedores.** AI Engine → Providers → **Import JSON** → subir `proveedor_<usuario>.json` → **Review this
import**.
- Se espera: se abre la revisión, con «No data has been written» y «Seges P-36 <usuario>» en «Will create». Sin el
  parche, aquí salía «You are not allowed to access 'View' (ir.ui.view) records.».
- Ejecuta la consulta de 1.3: todavía no hay ningún proveedor «Seges P-36 <usuario>» (parche 21).
- **Apply the import.** Se espera que se abra el resultado: «Operation completed successfully.» y 1 en creados.
  La consulta muestra el proveedor, `active` verdadero y `temperature` 0.36.

**2.2 Usuarios MCP.** AI Engine → Security → Users → **Import JSON** → subir `usuarios_<usuario>.json` →
**Review this import**.
- Se espera: se abre la revisión, con `demo` en «Will replace». La etiqueta de `demo` no cambia.
- **Apply the import.** Se espera que se abra el resultado con 1 actualizado. La consulta muestra
  `last_mcp_client_label` = `P-36 <usuario>`.

## 3. Negativo: `seges_int`

- El menú AI Engine → Providers / Security no muestra Import JSON (no es AI Administrator).
- Abre por URL `http://localhost:8169/web#model=ai.import.servers.wizard&view_type=form` y después
  `http://localhost:8169/web#model=ai.import.users.wizard&view_type=form`.
- Se espera, en los dos casos, un error de acceso al modelo del asistente («…not allowed to access…»). El parche
  no amplía nada: la comprobación del asistente se hace antes de leer la vista.

## 4. Qué queda escrito en `lab_pns_ai_3973_14` y cómo dejarlo

| Qué | Dónde | Cómo dejarlo |
|---|---|---|
| Proveedores «Seges P-36 aiadm» y «Seges P-36 access», activos | `ai_provider` | **Archivarlos** como `seges_aiadm`: Providers → marcarlos → Acción → Archivar. Activos podrían entrar en la cadena del chat (sin cadena, el agente usa los activos por orden de id). |
| Etiqueta `P-36 access` en `demo` (la última importación) | `ai_mcp_user.last_mcp_client_label` | Inofensiva: la sobrescribe la siguiente conexión MCP de `demo`. Si quieres dejar la anotada en 1.3, impórtala como `seges_aiadm` con un JSON igual y esa etiqueta. |
| Asistentes de importación y sus JSON adjuntos | tablas `ai_import_*_wizard` e `ir_attachment` | Nada: son transitorios y los borra el vaciado automático de Odoo. |

Al terminar:
- Ejecuta la consulta de 1.3: los dos proveedores con `active` falso.
- Borra `~/p36_lab/` y las copias en Descargas.
- Anota el resultado en el registro de parches, en un bloque fechado nuevo debajo de la entrada del 36 (no
  reescribas los anteriores).

> **Resultado (12/11/2026):** validado. La sección 2 se hizo a mano con `seges_aiadm`. `seges_access` y el
> negativo (sección 3, con `seges_int@example.com`) se hicieron por RPC: 32 OK y 0 FALLO por JSON-RPC.
> Detalle en el [registro](parches_pns_ai.md), «Prueba en el laboratorio del parche 36 (12/11/2026)».
> - Estado final de la sección 4: proveedores 4 y 6 archivados; la etiqueta de `demo` queda en «P-36 access».
> - Falta borrar `~/p36_lab/` y las copias en Descargas.
