# Guía de configuración de pns_base, pns_ai_mcp y pns_ai_chatboo (Odoo 14)

**Para:** consultor funcional que prepara un entorno de pruebas · **Fecha:** 2026-10-09 ·
**Rama:** `14.0-analisis-pns-ai` · **Versiones analizadas:** `pns_ai_mcp` 3.1.486,
`pns_ai_chatboo` 2.1.322 (fabricante: PATANEGRA Soft).

> ## ⚠️ NO APTO PARA BASES DE DATOS CON USUARIOS REALES hasta que el fabricante corrija los hallazgos críticos
>
> Pruebas confirmadas en el laboratorio de Seges (base de datos de demostración):
>
> 1. **Prueba A:** un usuario interno sin ningún permiso y **un usuario de portal** se convirtieron en administradores de Odoo con una sola llamada al servidor.
> 2. **Pruebas B y C (y F2):** se confirmó que cualquier usuario con sesión, también de portal, puede invocar las acciones de sistema (comprobado con la vista previa de instalar o actualizar módulos) y borrar las skills de fábrica. La instalación o desinstalación real de módulos no se probó (F1).
> 3. **Prueba D:** quien propone una escritura supervisada puede confirmársela a sí mismo o pasársela a otro usuario, sin el control humano previsto.
> 4. **F29:** en Chatboo, cualquier usuario interno lee, modifica y borra las conversaciones de otro usuario.
> 5. **F8:** un interno sin grupos de IA lee en claro las credenciales de los servidores externos. **Ningún grupo ni ajuste lo evita:** solo puede corregirlo el fabricante.
>
> Decisiones de despliegue: **D1** y **D33** en [pns_ai_decisiones.md](../pendiente/pns_ai_decisiones.md).
> Esta guía sirve **solo** para un entorno de pruebas sin usuarios reales ni de portal, y para
> reverificar una versión corregida (§8).

**Fuentes:** [análisis de pns_ai_mcp](analisis_pns_ai_mcp.md) (§2-§4), [análisis de
Chatboo](analisis_pns_ai_chatboo.md) (§2, §4), [decisiones](../pendiente/pns_ai_decisiones.md) y
[verificación de seguridad](../pendiente/verificacion_seguridad_pns_ai.md). Los números
"riesgo n.º" remiten a la tabla de riesgos de esos análisis (1-53 de `pns_ai_mcp`, 54-78 de
Chatboo); "Dn" a las decisiones y "Fn" a las preguntas de laboratorio.

**Importante sobre el alcance de lo probado:** en el laboratorio **no se configuró ningún
proveedor de IA** (sin claves). La instalación, los permisos y los crons están comprobados; el
funcionamiento real del chat con un proveedor **no** (ver §9).

---

## 1. Aviso previo para el consultor

- Los menús se citan **en inglés**, tal como los define el módulo. No se ha comprobado si hay
  traducción al español (sin validar).
- Los módulos son de un tercero y **no se modifican**. Todo lo que aquí se describe es
  configuración.
- Ninguna medida de esta guía corrige los críticos confirmados (§5 lo repite donde importa).

---

## 2. Para qué sirve cada módulo

| Módulo | Nombre en Aplicaciones | Qué aporta al usuario |
|---|---|---|
| `pns_base` | (dependencia, se instala sola) | Base común de los módulos PNS. **Afecta también a módulos que no son PNS:** cambia el enlace "Learn More" y la descripción de todos los módulos en Aplicaciones, y el aviso y el resaltado de campos obligatorios vacíos en todos los formularios y listas editables (decisiones PB-1 y PB-2). |
| `pns_ai_mcp` | "AI Engine" | El **motor de IA**, no un chat. Conecta Odoo con proveedores de IA externos (tipo OpenAI o Anthropic) o locales, con cadena de respaldo si uno falla. Guarda el "conocimiento" que se da a la IA (contextos de texto, skills con código y agentes). La IA **consulta** datos en modo solo lectura y, para **escribir**, propone una "operación supervisada" que una persona confirma; los cambios quedan en un diario reversible. Incluye "acciones de sistema" (añadir grupos a usuarios, instalar o desinstalar módulos, cambiar vistas y campos obligatorios). Publica Odoo como **servidor MCP** para herramientas externas (Claude Desktop, Cursor…) con una clave por usuario. Registra toda la actividad y cuenta tokens y coste por día (sin topes). Puede usar servidores externos (APIs) y descargar páginas de una lista blanca. |
| `pns_ai_chatboo` | "Chatboo" | El **chat de IA dentro del backend**: ventana flotante desde un icono de la barra superior o desde el menú Chatboo. Cada mensaje lo resuelve el motor de "AI Engine". Usa la pantalla abierta como contexto, admite imágenes y ficheros (Excel, PDF…), pinta tablas, gráficos y tarjetas, exporta a PDF, Word y Excel y puede leer las respuestas en voz alta. Trae 11 skills de fábrica (análisis financieros, censo de usuarios, información del sistema, previsión meteorológica…). **No tiene grupo propio:** lo ve quien tenga una clave MCP generada. |

---

## 3. Requisitos previos

### 3.1 Imagen del servidor (lo prepara el técnico)

| Requisito | Detalle | Estado |
|---|---|---|
| Versión de Python | 3.7 o superior. Con 3.6 `pns_base` no carga. Con 3.7 algunas funciones (zonas horarias, algunas "recetas" de código de la IA) no están disponibles (riesgo n.º 36). | La versión del VPS está **pendiente** (D3) |
| Librerías obligatorias | `openpyxl`, `httpx` y `pydantic`. Sin ellas Odoo **no deja instalar** "AI Engine". `httpx` y `pydantic` el módulo ni siquiera las usa, pero las exige (riesgo n.º 28). | Confirmado en laboratorio, con `openpyxl` 3.1.2, `httpx` 0.24.1 y `pydantic` 1.10.13 |
| Librerías que ya trae Odoo 14 | `requests` y `reportlab`. Pillow (imágenes del chat). | — |
| Opcional | `xlrd`, para que Chatboo lea ficheros `.xls` antiguos. Node.js solo para servidores MCP de tipo `stdio`, que **no deben usarse** (§5). | — |
| Cómo se añaden | En la **imagen** del cliente (su Dockerfile), nunca instalándolas a mano en un contenedor en marcha. Chatboo no añade librerías obligatorias. | — |

### 3.2 Red y seguridad de transporte

- **Salida a Internet** hacia el proveedor de IA (si es externo), hacia las dos fuentes públicas
  de tipos de cambio que usa el módulo para mostrar costes y, si se mantiene la skill de previsión
  meteorológica, hacia Open-Meteo. Sin Internet: solo proveedor local, y conviene desactivar las
  fuentes de tipos de cambio (cada comprobación de estado espera hasta 8 s; D14, riesgo n.º 48).
- **HTTPS** obligatorio en la práctica: el botón que copia la clave MCP no funciona sin él, y los
  clientes MCP externos lo necesitan.

### 3.3 Configuración de Odoo (archivo de configuración del servidor y proxy)

| Ajuste | Valor recomendado | Por qué |
|---|---|---|
| `workers` | Mayor que 0 (varios procesos), dimensionado para turnos largos | Cada conversación ocupa un proceso hasta 10 minutos (riesgo n.º 35). En modo multihilo (`workers = 0`) el turno escapa del límite de tiempo. |
| `limit_time_real` | **600 s o más** | Con menos, Odoo puede matar el proceso a mitad de respuesta; el turno queda como "respuesta incompleta" (D15). |
| `limit_time_cpu`, `limit_memory_hard`, `limit_request` | Revisar con el técnico | El código que genera la IA se ejecuta dentro del proceso de Odoo y no tiene límites propios. |
| `dbfilter` o una sola base de datos | Obligatorio para el servidor MCP | Con varias bases de datos y sin filtro, la dirección MCP responde con un error 404 (riesgo n.º 43). |
| Proxy inverso: ruta del chat (`/chatboo/stream`) | **Sin buffering** y con tiempo de lectura alto (10 min o más) | Chatboo envía la respuesta en directo; con buffering el usuario no ve nada hasta el final o se corta. |
| Proxy inverso: servidor MCP | Con varios workers, solo el modo "POST `/mcp`"; no el modo SSE (`/mcp/sse`) | SSE no funciona con varios procesos (riesgo n.º 35, D20). |
| Proxy inverso: CSP | Ver §5 (opcional y recomendable) | — |

### 3.4 Cuenta del proveedor de IA

- Una **clave de API** del proveedor elegido (los proveedores precargados vienen sin clave).
- Un **límite de gasto en la propia cuenta del proveedor**: el módulo no trae ningún tope de gasto,
  de tokens ni de turnos, y algunas llamadas no se contabilizan (riesgo n.º 31, D12).
- Base legal y contrato de encargado del tratamiento si es externo: cada consulta puede enviar
  hasta unos 2 MB / 50 000 filas, el registro abierto en pantalla y el texto completo de los
  adjuntos, sin filtro por modelo, campo ni empresa (riesgo n.º 18, D10). En pruebas, solo datos
  de demostración.
- Si se prevé usar modelos muy recientes, ver §7 (errores de protocolo, riesgo n.º 44, D11).

---

## 4. Instalación y configuración paso a paso

Orden unificado de `pns_ai_mcp` y Chatboo. Lo hace un usuario que sea a la vez **administrador de
Odoo (Ajustes)** y, desde el paso 2, **AI Administrator**.

| # | Paso | Ruta de menú | Qué hacer y qué cambia |
|---|---|---|---|
| 1 | Instalar "AI Engine" | Aplicaciones → buscar "AI Engine" → Instalar | Instala `pns_base` y `pns_ai_mcp`. Se crean proveedores de ejemplo (sin clave), servidores externos de ejemplo, la lista blanca de dominios, el agente MCP y tres acciones planificadas. Un administrador de Odoo **no ve el menú "AI Engine"** hasta tener un grupo de IA (paso 2). |
| 2 | Asignar grupos de IA | Ajustes → Usuarios y compañías → Usuarios → (usuario) → sección "Artificial Intelligence" | Grupos: **AI Administrator**, **AI Writer**, **External URL**, **External API**. Ninguno se asigna solo. Para configurar hace falta al menos un usuario con AI Administrator **y** Ajustes. Qué dar a quién: §5. |
| 3 | Proveedor de IA | AI Engine → Connections → Providers → (proveedor) | Pegar la clave de API, pulsar "Fetch Models", elegir el modelo y pulsar "Test Connection". Atención: la prueba hace una conversación real con el proveedor (coste mínimo) y queda en el registro de actividad. |
| 4 | Ajustes de AI Engine | Ajustes → AI Engine (o AI Engine → Settings) | Política de URL (dejar `whitelist_only`, que es el valor por defecto), moneda en que se muestran los costes y fuentes de tipos de cambio ("Manage quote sources"), "Turn-scoped domain packs" y prefijos de las skills propias (`custom_` / `custom-`). Solo entra quien tenga Ajustes **y** AI Administrator. |
| 5 | Lista blanca de dominios | AI Engine → Connections → Whitelist | Revisar los dominios precargados; dejar solo los imprescindibles. Incluye `open-meteo.com` para la previsión meteorológica de Chatboo (D36). |
| 6 | Servidores externos | AI Engine → Connections → External Servers | **En pruebas, no dar de alta ninguno** y dejar inactivos los de ejemplo (§5). Si alguna vez se usan: token, activar, "Discover Tools", y no marcar "trusted". |
| 7 | Instalar Chatboo | Aplicaciones → "Chatboo" → Instalar | Crea el agente de Chatboo, 3 contextos, 11 skills de fábrica, sus parámetros y una acción planificada más. En laboratorio se instaló sin errores (solo dos avisos cosméticos de etiquetas duplicadas). |
| 8 | Proveedores del agente de Chatboo | AI Engine → Agents → Chatboo → pestaña "Providers" | Añadir el proveedor del paso 3 y, si se quiere respaldo, otros con su **prioridad**. Si hay más de un proveedor activo y no se define la cadena, el chat responde "No AI provider is configured". El agente MCP (sin proveedor) no se toca. |
| 9 | Ajustes de Chatboo | Ajustes → AI Engine → bloque "Chatboo" | Mostrar el icono en la barra superior; memoria de conversación (tope de datos por turno, 8 MB por defecto, y horas que se conservan los datos de la última consulta, 12 por defecto); motor de gráficos (ECharts o Chart.js); modo inicial de presentación (tabla). El botón "Configuration" abre el agente del paso 8. |
| 10 | Parámetros del sistema | Ajustes → Técnico → Parámetros → Parámetros del sistema (modo desarrollador) | `pns_ai_chatboo.history_retention_days` (días que se conservan las conversaciones, 30 por defecto; **solo se cambia aquí**) y `pns_ai_chatboo.download_max_bytes` (tamaño máximo de descarga, 15 MB). `pns_ai_mcp.dataset_cache_max_bytes` (8 MB por turno; no poner 0, que es "sin límite", D30). |
| 11 | Usuarios MCP y claves ("carnet") | AI Engine → Security → Users → (usuario) → "Generate API Key" | Al abrir la lista se crea una fila por cada usuario interno activo. La clave **solo se ve en ese momento** (solo se guarda un resumen (hash) del que no se puede recuperar la clave): copiarla y entregarla por un canal seguro. Con la clave, el usuario ve el menú y el icono de Chatboo (puede hacer falta recargar el navegador, §7) y puede usar el servidor MCP. |
| 12 | Grupos funcionales para las skills de Chatboo | Ficha del usuario | AI Writer para crear, borrar y renombrar skills desde el chat; AI Administrator para "guardar resultado en bruto"; Contabilidad para las skills financieras; Ventas para el equipo de ventas en el cuadro de mando. |
| 13 | Acciones planificadas | Ajustes → Técnico → Automatización → Acciones planificadas | Comprobar las cuatro: "AI: purge expired fetch_url cache" (cada hora), "AI: purge expired api_call result cache" (cada hora; **falla, ver §7**), "AI: expire pending supervised operations" (cada 5 min) y "Chatboo: async queue maintenance" (cada 5 min; recupera turnos colgados y borra trabajos de más de 72 h). |
| 14 | Opcional: cliente MCP externo | Fuera de Odoo | Dirección `https://<servidor>/mcp` y la clave del usuario en la cabecera que indique el cliente. **No en la fase de pruebas** salvo que sea lo que se quiere validar (D20). |

---

## 5. Configuración prudente para un entorno de PRUEBAS sin usuarios reales

> **Estas medidas NO corrigen los críticos confirmados** (pruebas A-D, F2, F8, F29): esos fallos no
> dependen de grupos, ajustes ni claves. Solo reducen la exposición a otros riesgos mientras se
> prueba. El requisito de partida es que la base de datos **no tenga usuarios reales ni usuarios
> de portal**; con un solo usuario de portal, la prueba A le permite hacerse administrador.

| Ajuste | Qué hacer | Riesgo que reduce |
|---|---|---|
| Usuarios de la base de datos | Solo personal técnico de Seges o del cliente, sin portal. Datos de demostración o anonimizados. | Limita a quién afectan 1-7, 54-58 (no los corrige) |
| Política de URL | Mantener **`whitelist_only`**; nunca `open` (con `open` la IA descarga cualquier dirección sin confirmación y la añade sola a la lista). Lista blanca mínima. | 16, 17 (D24) |
| Servidores externos | **Ninguno** dado de alta; los de ejemplo, inactivos. **Ningún servidor `stdio`** (ejecuta comandos en el servidor con todo el entorno de Odoo). **Ninguno marcado "trusted"** (sus llamadas se ejecutan sin confirmación humana). | 8, 9, 14, 16, 17, 25 (D6, D7, D25) |
| Claves MCP | Solo a un **grupo piloto** reducido. Revocar las que no se usen. Saber que la clave **no protege** las conversaciones (sin clave también se leen las ajenas). | 13, 40, 55, 58, 67 (D46) |
| AI Writer y AI Administrator | Solo a **técnicos de confianza**. Un Writer puede inyectar instrucciones en el prompt de todos y crear skills con código que se ejecuta al guardarlas; un AI Administrator puede llegar al sistema operativo vía servidores `stdio`. | 6, 9, 10, 23 (D4, D27) |
| Proveedor y cadena de respaldo | Un proveedor principal y, si hay respaldo, **de la misma naturaleza** (todo local o todo con contrato): el respaldo recibe los mismos datos. Límite de gasto en la cuenta del proveedor. Evitar respaldo si se prueban escrituras (posible doble ejecución). | 18, 25, 31, 44 (D10, D11, D12) |
| Retención | Fijar el parámetro de días de conversación (paso 10). Purgar a mano periódicamente el registro de actividad (AI Engine → Security → Activity, asistente de borrado; no hay borrado automático) y las conversaciones de usuarios que ya no usan el chat (solo se purgan cuando el propio usuario vuelve a entrar). Al acabar las pruebas, borrar la base de datos. | 21, 32, 64 (D13, D35) |
| CSP en el proxy | Pedir al técnico una política de contenidos que limite las imágenes al propio dominio (más `data:` y `blob:`). Probar que no rompe otros módulos con imágenes externas. **Reduce la salida de datos por imágenes, no el XSS.** | 60 (D39) |
| Lectura en voz alta | **Indicar a los usuarios que no la activen.** No hay un ajuste global para desactivarla: cada usuario la enciende desde el chat. Puede enviar el texto a servicios de voz de Google o Microsoft. | 65 (D41) |
| Skills de fábrica de Chatboo | Si no se va a probar la previsión meteorológica, quitar `open-meteo.com` de la lista blanca. Las skills de censo de usuarios e información del sistema las puede usar cualquiera con clave: tenerlo en cuenta al repartir claves. | 67 (D36) |
| Tope de datos por turno | Mantener 8 MB (no 0). | 35 (D30) |
| Copias de configuración | No usarlas: la copia completa lleva siempre las claves y la "sin secretos" no las quita todas. | 20 (D8) |
| Tests del módulo | No ejecutarlos nunca sobre una copia de producción (uno deja una clave MCP conocida al administrador). | 38 (D31) |
| Peticiones a la dirección MCP | Si no se usa el servidor MCP, pedir al técnico que el proxy filtre el origen o bloquee `/mcp`. | 30 (D21) |
| Carpeta de módulos | Montada en solo lectura en el servidor. | 34 (D16) |
| Exportaciones del chat | Avisar de que los documentos exportados se descargan con un enlace sin iniciar sesión mientras exista la conversación. No compartir esos enlaces. | 21, 66 (D42) |

---

## 6. Cómo comprobar que funciona

Todo lo que implica respuesta de la IA está **sin validar** (en el laboratorio no hubo proveedor).

1. **Instalación:** en Aplicaciones, "AI Engine" y "Chatboo" aparecen como instalados; el
   administrador con grupo de IA ve el menú "AI Engine".
2. **Proveedor:** en Providers, "Test Connection" responde correctamente; en AI Engine → Security
   → Activity aparece una línea de esa prueba.
3. **Acceso al chat:** un usuario con clave MCP ve el icono de Chatboo en la barra superior (tras
   recargar si hace falta); un usuario sin clave no lo ve.
4. **Consulta:** en el chat, pedir algo de solo lectura sobre datos de demostración (por ejemplo,
   cuántos clientes hay o las cinco últimas facturas). La respuesta aparece en directo, con tabla
   si procede, y queda una línea nueva en el registro de actividad.
5. **Contexto de pantalla:** con un cliente abierto en pantalla, preguntar por "este cliente"; la
   respuesta debe referirse a él.
6. **Escritura supervisada:** con un usuario AI Writer, pedir un cambio inocuo en un registro de
   demostración. Debe aparecer un aviso de confirmación en el chat y la operación pendiente en
   AI Engine → Security → My Authorizations (o Authorizations para el administrador). Tras
   confirmarla, el registro cambia y el cambio figura en AI Engine → Security → Changes.
7. **Exportación:** exportar una respuesta con tabla a Excel y a PDF; los ficheros se abren y
   contienen lo que se veía.
8. **Conversaciones:** cerrar y abrir el chat; la conversación anterior sigue disponible.
9. **Acciones planificadas:** al cabo de unas horas, las de 5 minutos y la de "fetch_url" muestran
   la siguiente ejecución avanzando (la de "api_call", no; §7).

---

## 7. Problemas típicos y su solución

| Síntoma | Causa | Solución |
|---|---|---|
| Odoo no deja instalar "AI Engine" y menciona una librería que falta | La imagen no tiene `openpyxl`, `httpx` o `pydantic` | Añadir las tres a la **imagen** del cliente (no en el contenedor a mano) y reconstruirla. Con Python 3.6 `pns_base` no carga: hace falta 3.7 o superior. |
| La acción "AI: purge expired api_call result cache" aparece inactiva, o activa pero nunca vuelve a ejecutarse | El módulo la crea con **una sola ejecución permitida**: tras la primera, se desactiva y su "siguiente ejecución" se queda congelada. Activarla **no basta** (confirmado, F20). | Avisar al técnico: en la acción, el número de llamadas debe pasar a ilimitado (valor negativo) y la próxima ejecución a la hora actual. Sin validar si se mantiene tras actualizar el módulo; mientras, la caché de respuestas de APIs externas no se purga (con servidores externos inactivos no tiene efecto). Reportado al fabricante. |
| Tras generar la clave MCP, el usuario no ve el menú ni el icono de Chatboo | El navegador conserva los menús en caché | Recargar la página (sin validar, F46). |
| Los gráficos del chat se pintan mal | Tras abrir una vista gráfico de Odoo o el tablero de Contabilidad, Odoo carga otra versión de la librería de gráficos encima de la de Chatboo | Recargar la página. Las vistas de Odoo no se rompen. Efecto sin validar (F39). |
| El chat responde "No AI provider is configured" | El agente de Chatboo no tiene cadena de proveedores y hay más de uno activo | Paso 8: asignar proveedores al agente con su prioridad. |
| Un AI Administrator ve "Settings" en el menú pero recibe un error de acceso | Para entrar hace falta además el grupo Ajustes | Darle Ajustes o que configure otra persona (D5). |
| El administrador de Odoo no ve "AI Engine" | No tiene ningún grupo de IA | Asignarle AI Administrator (paso 2). |
| La respuesta tarda en aparecer de golpe, se corta o queda "respuesta incompleta" | Proxy con buffering o `limit_time_real` bajo | Revisar §3.3 con el técnico. |
| Errores del proveedor con modelos recientes y paso al proveedor de respaldo; el usuario ve la dirección del servicio | El módulo envía siempre parámetros que algunos modelos nuevos rechazan | Elegir otro modelo o informar al fabricante (riesgo n.º 44, D11). |
| Cada carga del backend es lenta en un servidor sin Internet | Las comprobaciones de estado esperan a las fuentes de tipos de cambio | Desactivar las fuentes de tipos de cambio en Ajustes (D14; efecto en Chatboo sin validar, F50). |
| La dirección `/mcp` devuelve "404" | Varias bases de datos sin `dbfilter` | Configurar `dbfilter` o usar una sola base de datos. |
| El botón de copiar la clave MCP no hace nada | Sin HTTPS | Acceder por HTTPS, o copiar la clave a mano en ese momento. |
| Se perdió la clave MCP | Solo se muestra al generarla | Generar una nueva. |
| Los cambios hechos a contextos o skills de fábrica desaparecen tras actualizar | El módulo los reimporta y reactiva en cada actualización | Hacer los cambios como contextos o skills propios (D17, D38). |

---

## 8. Lista de reverificación ante una versión corregida

Repetir en el **laboratorio local** (base de datos de demostración, sin claves de IA), con las
mismas condiciones que la primera vez: un usuario interno **sin ningún grupo de IA ni de
administración**, otro interno igual y un usuario **de portal**. El procedimiento de cada prueba
está en la [verificación de seguridad](../pendiente/verificacion_seguridad_pns_ai.md) y en el
informe al fabricante; aquí solo figura qué se espera.

Antes de las pruebas: la versión nueva se instala limpia (sin bloqueantes, con las mismas
librerías o menos) y Odoo arranca con `hr` y Chatboo instalados.

| Prueba | Qué se comprueba | Resultado esperado para darla por corregida |
|---|---|---|
| **A** | Que un interno sin permisos y un portal no puedan añadirse el grupo de administración | Ambos reciben un **error de acceso**; ninguno gana Ajustes ni Administración. |
| **B** | Acciones de sistema (instalar, actualizar, desinstalar módulos) por un interno sin permisos | **Error de acceso** también en la vista previa; sin ningún cambio en módulos. |
| **C** | Borrado de skills de fábrica por un interno sin permisos | **Error de acceso**; las skills siguen intactas. |
| **D** | Que el propietario cambie el estado de su operación supervisada o la reasigne | El cambio se **rechaza**; el estado solo avanza por el flujo de confirmación previsto. |
| **F2** | Las mismas vistas previas y el borrado de skills, con el usuario de portal | **Error de acceso** en todas. |
| **F8** | Lectura por un interno sin grupos de IA de credenciales de servidores externos, cachés y elecciones de otros usuarios | No ve tokens, variables de entorno ni configuración; no accede a las cachés; no ve las elecciones de otros. |
| **F20** | Acción "AI: purge expired api_call result cache" | Tras instalar, queda con ejecuciones ilimitadas; al cabo de varias horas, la siguiente ejecución sigue avanzando y el registro muestra una ejecución por hora. |
| **F29** | Conversaciones de Chatboo de un interno vistas por otro | El segundo interno **no lee, no modifica y no borra** la conversación del primero. Ampliar a los trabajos en curso y a los adjuntos de la conversación (no se probaron). El portal sigue sin acceso. |
| **F18** (pendiente) | Que las migraciones del módulo se ejecuten al actualizar desde una versión anterior | Al actualizar desde una versión anterior, el registro del servidor muestra la ejecución de los scripts de migración. Requiere disponer del módulo en una versión anterior. |
| **PNS-79** (pendiente) | Que un mensaje al servidor MCP sin usuario asociado no se ejecute con permisos de superusuario | La petición se **rechaza**. Y, relacionado, una clave revocada deja de funcionar de inmediato también en sesiones abiertas antes (F11). |
| **PNS-80** (pendiente) | Que otro usuario (interno o portal) no obtenga el progreso ni la respuesta de un turno de chat ajeno | **Error de acceso** o ningún dato devuelto. |

Si todas dan el resultado esperado, revisar de nuevo D1 y D33 y repetir la batería de tests del
módulo.

---

## 9. Lo que no se ha podido comprobar (sin validar)

- **Todo el funcionamiento con un proveedor de IA real**: respuestas, consultas, escrituras
  supervisadas, exportaciones, lectura en voz alta y coste (§6). En el laboratorio no hubo claves.
- **Traducción al español** de los menús.
- **Versión de Python del VPS** del cliente (D3) y comportamiento con una versión distinta de 3.7.3.
- **Proveedores concretos**: modelos recientes de Anthropic y OpenAI, Azure OpenAI y proveedores
  locales (D11).
- **Solución al cron de purga** de la caché de `api_call` (§7): si se mantiene tras actualizar el
  módulo.
- **CSP en el proxy**: efecto en Chatboo y en otros módulos con imágenes externas (D39).
- **Menú tras generar la clave** sin recargar (F46) y **gráficos tras abrir una vista gráfico**
  (F39).
- **Lentitud sin Internet** en cada carga del backend con Chatboo (F50).
- **Voces de lectura en voz alta** que usan los navegadores del cliente (F51, D40) y
  compatibilidad con navegadores antiguos (F48).
- **Turnos más largos que `limit_time_real`** con varios workers (F26, F44).
- **Servidor MCP** con varias bases de datos, respuesta a preflight y clientes concretos (F24,
  F25, D20).
- **Riesgos de seguridad sin reproducir**, que siguen abiertos: instalar o desinstalar módulos
  por un usuario sin permisos (F1); escaladas a través de las operaciones supervisadas, las skills
  y el código de la IA (F3-F7); prueba de servidores por un interno (F9); inyección de
  instrucciones en el prompt de todos (F10); clave MCP revocada (F11); contextos privados visibles
  (F12); limpieza del sistema sin ser Writer (F13); doble ejecución tras cambio de proveedor (F14);
  XSS en el chat y en tablas (F15, F31, F34, F38); fórmulas en Excel (F16); fallos con fechas en
  Python 3.7 (F17); turnos lanzados sobre conversaciones ajenas o desde otra web (F30, F32, F33);
  salida de datos por imágenes externas (F35); confirmación de operaciones sin el usuario (F36);
  historial inventado (F37); adjuntos generados por el navegador y huérfanos (F40, F42).
- **Rendimiento de las skills financieras con datos reales** (F49) y si la skill de facturación
  anual recibe todo lo que necesita (F47).
- **Conflictos con módulos `web_*` de OCA del cliente** por los cambios globales de `pns_base`
  (PB-2) y con módulos que usen rutas bajo `/mcp` (D9).
