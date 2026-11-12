# Pruebas manuales de la fase 2 (2a y 2b) — rama 14.0-pns-ai-3973

- **Laboratorio:** `lab_pns_ai_3973`, BD `lab_pns_ai_3973_14`, http://localhost:8169
- **Origen:** plan 3973 («Pruebas posteriores», punto 1) y registro de parches («Pendiente de la fase 2a»,
  «P-5 con el 12», «Pendiente de la fase 2b»). P-7 ya está hecha (N19f y N19m).
- **Estado:** pruebas hechas el 11/11/2026. Resultados en el registro de parches, «Pruebas manuales de la fase 2
  en `lab_pns_ai_3973` (11/11/2026)». Esta guía lleva ya las correcciones de lo visto en ellas.
- **Archivos:** `sembrar_fase2.py`, `p5_plan.py` y `comprobar.sql`, fuera del repo, en el scratchpad de la
  sesión: `/tmp/claude-1000/-home-soporte-GitHub-third-party/5a7f5de3-00e0-4160-a9cb-f48013e29a11/scratchpad/fase2/`.
- `comprobar.sql` es de solo lectura (`BEGIN TRANSACTION READ ONLY` … `ROLLBACK`):
  `docker exec -i odoo-dev-14-db-1 psql -U odoo -d lab_pns_ai_3973_14 < /tmp/claude-1000/-home-soporte-GitHub-third-party/5a7f5de3-00e0-4160-a9cb-f48013e29a11/scratchpad/fase2/comprobar.sql`

## 0. Estado del laboratorio (11/11/2026, solo lectura)

- Módulos `pns_*` actualizados el 11/11/2026 a las 15:44 (paso 1.1). Regla
  `pns_ai_chatboo.chatboo_canvas_page_admin_rule` con `perm_write` y `perm_create` en falso.
- BD sin neutralizar. Antes de 1.2: `base`, `mail` y los tres `pns_*` (23 módulos), **sin ninguna vista
  gráfico**.
- Usuarios: `admin` (Ajustes, **sin ningún grupo de IA**), `demo` (interno, sin IA) y `portal` (Joel Willis).
- Vacío: proveedores, sesiones de Chatboo, páginas compartidas, usuarios MCP, operaciones y diario. Las 9
  acciones de confianza del fabricante (`user.add_group` = id 8).

## 1. Preparación (en este orden; cada paso, con tu aprobación)

**1.1 Actualizar los módulos. Hecho** (11/11/2026, `actualizar-20261111-164257.log`: 0 ERROR, 0 Traceback).

**1.2 Instalar `sale_management`** (vista gráfico para P-70; con los datos de demo de la BD):

```sh
cd ~/GitHub/lab_pns_ai_3973 && odoo-dev 14 instalar sale_management
```

**1.3 Sembrar usuarios y datos, una sola vez** (`sembrar_fase2.py`, con C1; termina con `commit`):

```sh
cd ~/GitHub/lab_pns_ai_3973 && odoo-dev 14 shell < /tmp/claude-1000/-home-soporte-GitHub-third-party/5a7f5de3-00e0-4160-a9cb-f48013e29a11/scratchpad/fase2/sembrar_fase2.py
```

Si el shell no acepta la entrada redirigida, abre `odoo-dev 14 shell` y pega el contenido del archivo. Anota
los ids que imprime: se usan en 2.1, 2.5 y 2.6.

> **Aviso:** no repitas la siembra después de 2.1. `usuario()` reescribe los grupos con `(6, 0, …)` y le
> quitaría a `seges_target` el grupo que le da el caso (d).

> **Correo:** los `seges_*` necesitan correo. Al compartir una página (2.6) se publica un aviso con el dueño
> como autor y, sin correo, sale un `UserError`. La siembra pone `<login>@example.com` a los que no lo tienen
> (en las pruebas del 11/11/2026 se puso a mano en `seges_int`).
>
> **12/11/2026:** al poner el correo a mano en el formulario, el login de `seges_int` (usuario 12) pasó a
> ser `seges_int@example.com` (consulta de solo lectura de Sergio). No se cambia en la BD: para entrar, por la
> interfaz o por RPC, se usa `seges_int@example.com`. En esta guía, «`seges_int`» sigue nombrando a ese usuario.

| Usuario | Grupos exactos | Para |
|---|---|---|
| `seges_sys` | Usuario interno, Ajustes (`base.group_system`, implica Permisos de acceso), AI Administrator | P-5 positivo y quien confirma; 32 positivo; crea el proveedor real |
| `seges_aiadm` | Usuario interno, AI Administrator (sin Ajustes ni Permisos de acceso) | P-5 (a); quien confirma y es rechazado; 32 y 33; 21 solo hasta «Review», que no abre sin el parche 36; 28 (AI Administrator que no es dueño) |
| `seges_access` | Usuario interno, Administración / Permisos de acceso (`base.group_erp_manager`), AI Administrator; sin Ajustes | P-5 (b) |
| `seges_target` | Usuario interno | Destino del grupo en P-5 |
| `seges_int` | Usuario interno, AI Conversational, AI Writer y, con `sale_management` instalado, Ventas / Usuario: todos los documentos | Dueño de la sesión (11) y de la página (28); 33 negativo; P-70, 25 y 26. AI Writer solo para que vea el menú AI Engine → Security → Shared pages |
| `demo` (existe) | Usuario interno, sin IA | 33 negativo por consola; lector de la página (28); creador del adjunto ajeno (11) |
| `portal` (existe) | Portal | 28 negativo |

AI Administrator implica AI Conversational, AI Writer, AI External URL y AI External API.

Datos que crea:
- **Proveedor** «Seges ficticio (sin red)»: protocolo `openai`, endpoint `http://127.0.0.1:9/v1/chat/completions`,
  sin clave, sin roles, `temperature` 0.7. Nunca sale a la red; sirve para 33 y 21 y se archiva en 2.8.
- **Sesión** «Seges P-11» de `seges_int` con dos mensajes y dos adjuntos: `p11_propio.txt` (creado por
  `seges_int`) y `p11_ajeno.txt` (creado como `demo`: `with_user(demo).sudo()`, `create_uid` = id de `demo`).
- **Página compartida** «Seges P-28» de `seges_int`, en `su` (como la ruta de compartir), **sin compartir**.

**1.4 Contraseñas (interfaz):** como `admin`, Ajustes → Usuarios → marcar los cinco `seges_*` → Acción →
Cambiar contraseña. Usa una contraseña de laboratorio.

**1.5 Claves MCP (interfaz):** como `seges_sys`, AI Engine → Security → Users (al abrirlo se crean las filas
que faltan). En `seges_sys`, `seges_aiadm`, `seges_access` y `seges_int`: abrir → Generate key → copiar. La
de `seges_int` no la usa ningún script: Chatboo solo exige que exista (AI Conversational más clave MCP
generada, `pns_ai_chatboo/utils/chatboo_access.py`). No hace falta guardarla. Sin ella, `seges_int` no puede
usar Chatboo (2.5, 2.7 y sección 3).

En la terminal, sin que quede en el historial:

```sh
read -rs P5_KEY_SYS && export P5_KEY_SYS      # pega la de seges_sys
read -rs P5_KEY_AIADM && export P5_KEY_AIADM  # seges_aiadm
read -rs P5_KEY_ACCESS && export P5_KEY_ACCESS
export P5_TARGET=<id de seges_target, de la salida de la siembra>
```

## 2. Pruebas sin proveedor

Antes de cada una, lanza `comprobar.sql` y guarda la salida («antes»).

### 2.1 P-5 con el 12 (y 16: Confirmar pide la contraseña)

Grupo que se pide: `base.group_partner_manager` («Creación de contactos»), un grupo normal. No está en la
cúspide del fabricante (no implica `group_system` ni `group_erp_manager`), y la acción de confianza 8 solo
admite proponentes AI Administrator: el resultado depende solo del 12. Los comandos se lanzan desde la carpeta
de los scripts:
`cd /tmp/claude-1000/-home-soporte-GitHub-third-party/5a7f5de3-00e0-4160-a9cb-f48013e29a11/scratchpad/fase2`

| Caso | Quién propone | Comando | Se espera |
|---|---|---|---|
| (a) | `seges_aiadm` | `P5_KEY=$P5_KEY_AIADM python3 -I p5_plan.py` | `isError: False` y, en la respuesta, `success` false con el mensaje del 12 («Only a Settings administrator can add or remove user groups.»). Ninguna fila nueva en `ai_safe_operation` |
| (b) | `seges_access` | `P5_KEY=$P5_KEY_ACCESS python3 -I p5_plan.py` | Igual que (a). Sin el 12, el fabricante lo dejaría pasar (con Permisos de acceso) |
| (c) | `seges_sys` | `P5_KEY=$P5_KEY_SYS python3 -I p5_plan.py` | `isError: False`, con `verification_id`. Una operación pendiente (SAFE00000001) |
| (d) | `seges_sys` | el mismo comando, **después de confirmar (c) en el paso 1** | Una operación pendiente nueva (SAFE00000002). Si se lanza con (c) aún pendiente, devuelve la misma operación |

Confirmación en la interfaz (AI Engine → Security → Authorizations):
1. **Operación de (c), como `seges_aiadm`** (AI Administrator sin Ajustes, puede resolver la de otro): Confirmar.
   - **16:** sale «Control de seguridad» y pide la contraseña de `seges_aiadm`. Tras ponerla, Odoo no la vuelve
     a pedir en 10 minutos.
   - **12 (quien confirma):** el plan se ejecuta como `seges_sys` (el solicitante, con Ajustes), pero con
     `seges_aiadm` como quien confirma en el contexto. El 12 lo rechaza: «Execution result {"error": "Only a
     Settings administrator can add or remove user groups."}».
     - Operación `cancelled`; diario `user.add_group` `failed`; `seges_target` sin el grupo.
     - En el log, un `ERROR … execute_plan_now … failed` con su traza: es esperado.
     - Sin el 12 se aplicaría, porque el fabricante solo comprueba al solicitante. Lo cubre
       `test_context_identities_checked` (falla en N12).
2. **Lanzar (d) y confirmar su operación como `seges_sys`:** Confirmar → contraseña (16) → se ejecuta.
   - Operación `executed`; diario `user.add_group` `applied`; `seges_target` con «Creación de contactos».

Si `/mcp` responde con un error HTTP, mira AI Engine → Settings (MCP activo) antes de seguir.

### 2.2 Parche 32: acciones de confianza

Las acciones no tienen menú; se abren por URL.
1. Como `seges_aiadm`: `http://localhost:8169/web?debug=1#model=ai.trusted.action&id=8&view_type=form`.
   Editar la etiqueta (añadir « x») → Guardar.
   - **Se espera:** «Only a Settings administrator can change trusted actions.». `write_date` de la fila 8 sin
     cambios.
2. (Opcional, positivo) Como `seges_sys`, lo mismo: guarda. Deja la etiqueta como estaba (el próximo `-u` la
   restaura también, el XML no es `noupdate`).

### 2.3 Parche 33: «This month» del proveedor

1. Como `seges_aiadm`: AI Engine → Connections → Providers → «Seges ficticio (sin red)» → botón **This
   month**.
   - **Se espera:** el asistente abre con «This month (since …)», 0 tokens, Cap «None», Remaining «No cap».
2. Como `demo` (sin IA), en la consola del navegador (F12), con el id del proveedor:
   ```js
   fetch('/web/dataset/call_kw', {method: 'POST', headers: {'Content-Type': 'application/json'},
     body: JSON.stringify({jsonrpc: '2.0', method: 'call', params: {model: 'ai.provider.usage.wizard',
       method: 'default_get', args: [['provider_id']], kwargs: {context: {default_provider_id: ID}}}})})
     .then(r => r.json()).then(r => console.log(r.error ? r.error.data.name + ': ' + r.error.data.message : r.result));
   ```
   - **Se espera:** `odoo.exceptions.AccessError`. Con `model: 'ai.provider', method: 'month_usage',
     args: [[ID]]` sale `AttributeError` (el nombre público ya no existe).
3. Como `seges_int` (interno con AI Writer, sin AI Administrator): en AI Engine no aparece Connections →
   Providers. Abrir por URL `http://localhost:8169/web#model=ai.provider&id=ID&view_type=form` → **This month**.
   - **Se espera:** error de acceso (`AccessError` del 33, `check_access_rights('create')` del asistente). No se
     abre el asistente ni se ven tokens ni costes.

### 2.4 Parche 21: «Review» de una importación no deja nada escrito

`seges_sys` (Ajustes y AI Administrator) hace las dos partes. Con `seges_aiadm`, «Review» no abre: es un defecto
del fabricante. La vista de revisión se lee sin `sudo` y `ir.ui.view` solo lo lee Ajustes (`AccessError` en
`load_views`). Afecta a cualquier AI Administrator sin Ajustes, en proveedores y en usuarios MCP. Se corrige con el
parche 36 (fase 2c); hasta entonces, esta prueba se hace con `seges_sys`. JSON fuera del repo (por ejemplo,
`~/p21_lab/`); se borra al terminar.
1. **Proveedores:** Providers → marcar «Seges ficticio» → **Export selected** → guardar el JSON. Cambiar solo
   `temperature` 0.7 → **0.43**. Botón **Import JSON** del listado → subir → **Review** → cerrar sin Confirmar.
2. **Usuarios MCP (el caso de grupos, nuevo en 3.1.973):** Security → Users → marcar `demo` → Export selected.
   Cambiar `is_ai_writer` a `true` y `last_mcp_client_label` a **`P-21 preview`**. Import JSON → Review → cerrar.
- **Se espera** (`comprobar.sql` antes, después de «Review» y después de cerrar):
  - Review muestra «No data has been written» y el nombre en «Will replace», y no escribe nada.
  - Proveedor: `temperature` 0.7 y el mismo `write_date`.
  - Usuario `demo`: **sin `group_ai_writer`** en `grupos_pns` y, en Ajustes → Usuarios → demo → Permisos de
    acceso, «AI Writer» sin marcar. `last_mcp_client_label` vacío y el mismo `write_date` en `ai_mcp_user`.
  - En N21 de los tests, sin el parche, el grupo quedaba dado.

### 2.5 Parche 11: borrar una sesión con adjuntos

1. Como `seges_int`: abrir Chatboo → Historial → borrar «Seges P-11». El chat avisará de que no hay proveedor;
   el historial debe funcionar igual.
- **Se espera** (`comprobar.sql`, con los ids de la siembra):
  - la sesión desaparece de `chatboo_session`;
  - `p11_propio.txt` (`create_uid` = id de `seges_int`) desaparece de `ir_attachment`;
  - `p11_ajeno.txt` (`create_uid` = id de `demo`) **sigue**, con `res_model` vacío y `res_id` **0**: ya no
    apunta a la sesión borrada.
  - Código: `pns_ai_chatboo/models/chatboo_session.py:2030-2040`. Busca en `sudo` los adjuntos de la sesión
    (`:2030`); son propios los de `create_uid` vacío o igual al dueño (`:2036-2038`); a los ajenos les pone
    `res_model` y `res_id` a `False` (`:2039`; `res_id` queda en 0) y borra solo los propios (`:2040`).
- Si el historial no carga sin proveedor, en la consola de `seges_int`: `call_kw` de `chatboo.session`,
  `unlink`, `args: [[ID de la sesión]]` (mismo `fetch` que en 2.3).

### 2.6 Parche 28: página compartida

1. Como `seges_int` (dueño): AI Engine → Security → Shared pages → «Seges P-28» → Shared with: añadir **Marc
   Demo** → Guardar.
   - **Se espera:** se guarda; `demo` recibe el aviso en la bandeja.
   - El widget no ofrece usuarios portal (dominio `share = False`). La restricción del 28 se prueba por
     consola, como `seges_int`: `write` de `chatboo.canvas.page`,
     `args: [[ID de la página], {user_ids: [[4, ID de portal]]}]` (los dos ids, de la salida de la siembra) →
     `ValidationError` «A page can only be shared with internal users.».
2. Como `demo`: abrir el enlace del aviso (`/chatboo/page/<id>`). **Se espera:** ve la página.
3. Como `seges_aiadm` (AI Administrator, no es el dueño): Shared pages → ve la página.
   - Cambiar el título → Guardar: **error de acceso** (regla «Chatboo shared page: owner writes»).
   - **Stop sharing** (lista o formulario): también **error de acceso**. El botón (`type="object"`,
     `pns_ai_chatboo/views/chatboo_canvas_page_views.xml:17, 31`) llama a `action_unshare`
     (`pns_ai_chatboo/models/chatboo_canvas_page.py:185-186`), que hace `self.write({'user_ids': [(5, 0, 0)]})`
     **como el usuario, sin `sudo`**. `user_ids` no es campo de sistema (`:94-95`), así que lo paran las reglas:
     la del dueño no se aplica y la del AI Administrator tiene `perm_write` en falso. La página sigue compartida
     con `demo`.
   - Al final, Acción → Eliminar: **se borra**.

### 2.7 P-70 (parche 20), parte sin proveedor

Como `seges_int`, recarga sin caché (Ctrl+Mayús+R). En la consola, antes y después de abrir Chatboo:

```js
[window.Chart && window.Chart.version, !!(window.Chart && window.Chart.helpers),
 window.PnsChatbooChart && window.PnsChatbooChart.version]
```

- **Se espera:** antes, `[undefined, false, undefined]`; después de abrir el chat,
  `[undefined, false, "4.4.8"]`. Lo importante: `window.Chart` **no** pasa a 4.4.8. En Red,
  `chart.umd.min.js?seges=20`.
- Odoo solo carga su Chart 2.x al abrir una vista gráfico: el `true` de `Chart.helpers` y el caso 1 completo,
  en 3.3.

### 2.8 Antes de la sección 3: archivar el proveedor ficticio

> **Hecho el 11/11/2026** desde el shell, con aprobación de Sergio: proveedor 1 `active` false. Comprobado con una
> consulta de solo lectura.

Como `seges_aiadm`: Providers → «Seges ficticio (sin red)» → Acción → Archivar. Sin roles cuenta como «solo
texto», y sin cadena de proveedores el agente usa los activos por orden de id: sería el primero del chat. Los
proveedores archivados no entran en ninguna cadena.

## 3. Pruebas con proveedor real (Gemini)

**Requisitos:** 2.8 hecho y `sale_management` instalado (1.2) antes de la siembra (1.3), para que
`seges_int` tenga «Ventas / Usuario: todos los documentos».

**3.1 Rol Design (como `seges_sys`):** AI Engine → Connections → Provider roles → **Design** → desmarcar
**use_fallback** → Guardar. Sin el fallback, si no hay proveedor de Design, no hay página, en lugar de pasar a
Conversation. **Hecho el 11/11/2026** desde el shell, con aprobación de Sergio: rol Design (id 6) `use_fallback`
false, comprobado con una consulta de solo lectura.

**3.2 Proveedor (lo crea Sergio como `seges_sys`; la clave la pone él):** AI Engine → Connections → Providers →
Crear.
- Name: `Gemini lab` · Active: sí · Protocol: `OpenAI / OpenAI-Compatible`.
- Endpoint: `https://generativelanguage.googleapis.com/v1beta/openai/chat/completions`.
- API Key: la pone Sergio. Guardar.
- Model: **Browse** → el que admita Conversation y Design. Si el catálogo no lo admite, al guardar sale
  «Model … does not accept …». En staging, el rol Design irá solo en `3.5-flash` (plan, «Tras el `-u`»).
- Roles: **Conversation** y **Design**.
- **Monthly cap, recomendado:** un tope en USD o en tokens.
- Guardar → **Test Connection**.

**3.3 P-70 caso 1 completo (20), como `seges_int`:** recarga sin caché → Ventas → Pedidos → vista **gráfico**
de los pedidos (el menú Informes es solo del responsable de ventas; `seges_int` no lo ve). En la consola, la línea de 2.7: `[undefined, true, undefined]`. Abrir Chatboo → «Gráfico de barras del
importe de pedidos de venta por cliente» → se pinta. Volver sin F5 a la vista gráfico → barras → líneas →
circular. En la consola: `[undefined, true, "4.4.8"]`, sin errores `xAxes`/`yAxes`.

**3.4 Parche 25 (job del botón Canvas), como `seges_int`:**
- En una respuesta con tabla («Tabla de 5 contactos con su país y su foto»), botón **Canvas** → la página se
  abre en una pestaña.
- En `odoo-dev 14 log`, ni «This canvas belongs to another user» ni «no design provider».

**3.5 Parche 26, positivo:** **el botón Canvas no sirve.** Manda al servidor el `data-ai-dataset` de la tabla,
que `_chart_dataset_rows` deja sin columnas de imagen (`pns_ai_mcp/utils/relaxaicode_render_table.py:326-336`;
igual en el fabricante). Design no recibe fotos y la página sale con iniciales.
- Para probar el 26 desde la interfaz, la página tiene que salir del turno del chat (`page_url` del código del
  turno, `chatboo_session.py:854` y `:891`, o el dominio `page_tab`). Con `seges_int` en inglés (`en_US`), las
  palabras de `page_tab` son solo las genéricas (`canvas`, `page`, `a page`…; `ai_context_discovery.py:59-66`):
  «Hazme una página…» no lo activa. Hay que pedirlo en inglés («Make a page with 5 contacts, their country and
  their photo») o poner a `seges_int` en español.
- El 11/11/2026 no hubo positivo desde la interfaz (las dos páginas, 3 y 4, salieron del botón Canvas). El 26
  queda cubierto por `repro_26.py` (shell, sin commit) y `TestSegesCanvasPictures`.

## 4. Al terminar

- Anota en el registro de parches, debajo de «Pendiente de la fase 2b», un bloque fechado con el resultado
  de cada prueba (no reescribas los anteriores).
- Los usuarios, el proveedor ficticio y los datos sembrados se pueden quedar: `lab_pns_ai_3973_14` solo cubre
  el caso (c) de P-2 (crons), que no los usa.
- Borra los JSON de 2.4 (`~/p21_lab/` y la copia en Descargas).
- En la terminal: `unset P5_KEY_SYS P5_KEY_AIADM P5_KEY_ACCESS P5_TARGET`.
- No exportes el proveedor de Gemini en ningún JSON (Export selected ni copia de configuración).
