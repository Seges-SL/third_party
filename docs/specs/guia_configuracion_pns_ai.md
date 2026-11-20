# Guía de configuración de pns_base, pns_ai_mcp y pns_ai_chatboo (Odoo 14)

**Para:** consultor funcional y técnico que preparan el VPS de pruebas (staging) · **Fecha:** 2026-10-15
(actualizada el 2026-10-16 con el staging) · **Rama:** `14.0-pns-ai-3` · **Versiones:** `pns_base`
1.2.32, `pns_ai_mcp` 3.1.782 y `pns_ai_chatboo` 2.1.453 (fabricante: PATANEGRA Soft), con los parches
de compatibilidad 1 a 6 de Seges (N2 revisada; staging 16/10/2026).

> ## ⚠️ VERSIÓN APTA SOLO PARA STAGING: NO APTA PARA PRODUCCIÓN
>
> Decisión **N3** (14/10/2026): la 3.1.782 se puede instalar **solo en el VPS de pruebas**, sin
> usuarios de portal, con usuarios técnicos de confianza y con las mitigaciones de §2. **No se
> instala en ninguna base de datos con usuarios reales** hasta que **PNS-82, PNS-83, PNS-85, PNS-90 y
> PNS-91** y los restos de PNS-01/02 y PNS-07 estén corregidos y se repitan las pruebas (§15). Desde la
> reunión del 19/10/2026 los corrige **Seges** en la rama, que mantiene la 3.1.782 (N11 y N12;
> [../pendiente/plan_correccion_pns_ai.md](../pendiente/plan_correccion_pns_ai.md)).
>
> Excepción: LIYBEN, base de datos interna de Seges con datos antiguos de la empresa, la tiene
> instalada desde el 16/10/2026 por la decisión N7 (condiciones de N3 b); registro en
> [../pendiente/instalacion_liyben_pns_ai.md](../pendiente/instalacion_liyben_pns_ai.md).
>
> Los críticos de la versión anterior (pruebas A-D, F8 y F29) están corregidos o reducidos (D1, D33).
> Lo que bloquea ahora son hallazgos nuevos con el mismo patrón (métodos públicos que trabajan con
> permisos de superusuario sin comprobar grupo): varios los puede aprovechar **cualquier usuario
> interno**, y algunos también un **usuario de portal**. Ningún grupo ni ajuste los corrige del todo.

**Fuentes:** [decisiones](../pendiente/pns_ai_decisiones.md) (sección «Revisión tras la versión
3.1.782» y N1 a N5), [seguimiento del informe](../pendiente/seguimiento_informe_pns_ai.md) (PNS-01 a
PNS-92), [verificación de seguridad](../pendiente/verificacion_seguridad_pns_ai.md) (secciones
«Versión 3.1.782»: fases 3a, 3b-1, 3b-2, 3c y parche 4; «Staging (15-16/10/2026)»), [parches de
compatibilidad](../pendiente/parches_pns_ai.md), [plan de staging](../pendiente/plan_staging_pns_ai.md),
análisis del [parche 5](../pendiente/analisis_parche5_gemini.md) y del
[bloqueo de `chatboo_session`](../pendiente/analisis_bloqueo_chatboo_session.md) e
[inventario de cambios](cambios_pns_ai_3-1-782.md).
«Dn»/«Nn» remiten a las decisiones, «PNS-nn» a los hallazgos del seguimiento y «Fn» a las preguntas de
laboratorio.

**Alcance de lo probado:** la actualización desde 3.1.486, los permisos y los crons están comprobados
en el laboratorio. El chat con un proveedor externo se probó **en parte** en el laboratorio (proveedor
saturado) y las pruebas pendientes se hicieron **en el VPS de staging el 15 y 16/10/2026**
(instalación nueva, Gemini por el protocolo `openai`): resultados en §13, punto 9, y en el
[plan de staging](../pendiente/plan_staging_pns_ai.md), §6.1. Quedan sin probar la 9b (sin
Anthropic) y la secuencia de actualización de §5 (§16).

---

## Índice

1. Aviso previo
2. Estado de la versión 3.1.782 (N3)
3. Para qué sirve cada módulo
4. Requisitos previos
5. Actualización segura desde 3.1.486 (N1)
6. Instalación y configuración paso a paso
7. Grupos, usuarios y claves MCP
8. Proveedores de IA y cadena del agente
9. Política de URL y lista blanca
10. Servidores externos
11. Copias de configuración y retención
12. Otras medidas prudentes para staging
13. Cómo comprobar que funciona
14. Problemas típicos y su solución
15. Lista de reverificación ante una versión corregida
16. Lo que no se ha podido comprobar y lo pendiente de confirmar

---

## 1. Aviso previo

- Los menús se citan **en inglés**, tal como los define el módulo. No se ha comprobado si hay
  traducción al español.
- Las rutas de menú de §6 y §13 están comprobadas contra los 21 menús que definen `pns_ai_mcp` y
  `pns_ai_chatboo` en 3.1.782. Cada usuario ve solo los menús de sus grupos: por ejemplo, Connections,
  Agents y Knowledge solo los ve el AI Administrator, y Settings solo el administrador de Odoo.
- Los módulos son de un tercero. La única excepción a la regla de no modificarlos son los parches de
  compatibilidad 1 a 6 (N2 revisada, §4.1; staging 16/10/2026). Todo lo demás que se describe aquí es configuración.
- Las medidas de esta guía **no corrigen** los hallazgos abiertos de §2: solo reducen la exposición
  mientras se prueba.

---

## 2. Estado de la versión 3.1.782 (N3)

**Decisión N3:** opción b) ahora (apta solo para el VPS de pruebas) y opción a) para producción (no
apta hasta que estén corregidos PNS-82, 83, 85, 90 y 91; desde el 19/10/2026, por Seges en la rama,
N11). Bloqueantes vigentes tras la reunión del 19/10/2026: D1, D9 y PB-2 siempre; D4 fuera de LIYBEN;
con Chatboo, D33 y D46 fuera de LIYBEN. D10 quedó aceptada y D3 CERRADA (N12). **D29 deja de ser bloqueante (staging
16/10/2026):** la prueba 8 salió CORREGIDO en los cuatro casos; queda el riesgo residual del saneador
(PNS-60 sigue PARCIAL), que se decide como riesgo aceptado o no, sin bloquear la instalación. El
staging no cambia N3: los hallazgos nuevos PNS-93 y PNS-94 tienen parche (5 y 6) y PNS-95 y PNS-96
son de calidad (plan de staging, §6.2).

### 2.1 Condiciones para usarla en staging

1. Base de datos **sin usuarios de portal**.
2. Solo **usuarios técnicos de confianza** (de Seges o del cliente).
3. **Datos de demostración** y un proveedor externo para las pruebas pendientes (N5, opción a). Si el
   VPS no está listo, las pruebas se repiten antes en el laboratorio (N5, opción c, como puente).
4. Aplicar todas las mitigaciones de la tabla 2.2.

### 2.2 Riesgos abiertos que bloquean producción y su mitigación

| PNS | Riesgo (descrito, sin procedimiento) | Quién puede aprovecharlo | Mitigación en staging | Hasta dónde llega |
|---|---|---|---|---|
| **PNS-82** | Un usuario puede apropiarse de adjuntos ajenos que no cuelgan de ningún registro: descargas del chat de otros usuarios y copias de configuración (que pueden llevar claves). | Cualquier interno | No exportar copias de configuración con secretos (D8, §11). | Las descargas del chat de otros usuarios siguen expuestas a cualquier interno con Chatboo. Solo se evita sin Chatboo. |
| **PNS-83** | Con la mesa de entrega de claves por PIN abierta, se pueden probar PIN sin límite efectivo y obtener la clave MCP de otro usuario. | Cualquier usuario autenticado, también de portal | **No usar nunca la mesa de PIN ni generar PIN** (N4, §7). Sin portal (§2.1). | Sin mesa abierta, el canje no devuelve claves. Sigue siendo posible bloquear una IP durante una hora, sin efecto si no se usa la mesa. |
| **PNS-85** | Cualquiera puede fijar de antemano los parámetros con que se ejecutarán las skills de todos los usuarios: los resultados salen alterados sin aviso (integridad, no escalada). | Cualquier interno | Ninguna por configuración. Solo usuarios de confianza (§2.1). | **No mitigable**: no depende de ningún grupo. |
| **PNS-90** | La caché de páginas descargadas (`fetch_url`) se puede leer y sobrescribir: se puede leer lo que otro consultó y hacer que la IA de otro usuario reciba un contenido preparado (vía de inyección de instrucciones, PNS-16). | Cualquier usuario autenticado, también de portal (comprobado en 3c) | Sin portal. `group_ai_external_url` solo para quien lo necesite (§7). | **No mitigable**: el grupo solo limita quién recibe el contenido, no quién escribe en la caché. |
| **PNS-91** | Cualquiera puede añadir o reactivar dominios en la lista blanca, lo que anula la política `whitelist_only`. | Cualquier usuario autenticado, también de portal (comprobado en 3c) | Sin portal. `group_ai_external_url` solo para quien lo necesite (§7, §9). | **No mitigable** con configuración. |

Mitigación complementaria (D4): **AI Administrator solo para quien ya es administrador de Odoo**. Cubre
del todo, mientras se respete, el resto de PNS-01/02 (un AI Administrator sin Ajustes puede darse la
administración de Odoo con un plan que él mismo confirma), PNS-84 (el AI Administrator ve PIN y claves
en claro) y PNS-86 (generador OpenAPI, solo AI Administrator).

### 2.3 Lo que no se puede mitigar con configuración

Solo lo corrige el fabricante o no instalar (N3):

- **PNS-90, PNS-91 y PNS-85**, como se indica en la tabla 2.2.
- **PNS-82:** solo se evita sin Chatboo.
- **Restos de PNS-07 y PNS-19:** desde el entorno de ejecución de código de la IA, cualquier usuario
  del chat o de MCP puede llegar a métodos internos, entre ellos el que devuelve la clave del
  proveedor. Solo se evita sin dar acceso al chat ni a MCP.
- **Restos de PNS-54 y PNS-60:** riesgo residual de XSS y confirmación de operaciones sin pasar por la
  tarjeta; dependen del código (D29; la prueba 8 del staging salió CORREGIDO, pero el resto del
  saneador no se ha probado).
- **Resto de PNS-30:** se pueden crear filas del registro de actividad a nombre de otro usuario.
- **PNS-92:** la generación de claves MCP está protegida hoy solo por un efecto lateral; ninguna
  configuración lo refuerza.

---

## 3. Para qué sirve cada módulo

| Módulo | Nombre en Aplicaciones | Qué aporta |
|---|---|---|
| `pns_base` | (dependencia, se instala sola) | Base común de los módulos PNS. Ahora depende también de `mail`. **Sigue afectando a módulos que no son PNS:** cambia el aviso y el resaltado de campos obligatorios vacíos en todos los formularios y listas editables (PB-2, bloqueante), y descarta sin error las traducciones duplicadas al cargar idiomas, ahora con aviso en el asistente (PB-7). Ya **no** reescribe el enlace ni la descripción de los demás módulos (PB-1, cerrada). Trae un cron que borra a las 24 h los archivos de exportación. |
| `pns_ai_mcp` | "AI Engine" | El **motor de IA**, no un chat. Conecta Odoo con proveedores de IA externos o locales, con cadena de respaldo. Guarda el conocimiento para la IA (contextos, skills con código y agentes). La IA consulta en solo lectura y, para escribir, propone una operación supervisada que una persona confirma. Publica Odoo como **servidor MCP** con una clave por usuario. Registra la actividad con retención automática (30 días por defecto) y cuenta tokens y coste, sin topes. Puede usar servidores externos y descargar páginas de una lista blanca. Novedades de 3.1.782: mesa de entrega de claves por PIN (**no se usa**, N4), descarga de imágenes externas por el servidor, generador de especificaciones OpenAPI y exportaciones que preguntan si incluir secretos. Sigue aplicando parches globales sobre Odoo y amplía de 11 a 19 sus extensiones de JavaScript del backend (D9, bloqueante). |
| `pns_ai_chatboo` | "Chatboo" | El **chat de IA dentro del backend** (icono en la barra superior o menú Chatboo). Cada mensaje lo resuelve el motor de "AI Engine". Usa la pantalla abierta como contexto, admite imágenes y ficheros (15 MB por archivo), pinta tablas y gráficos, exporta a PDF, Word y Excel y puede leer las respuestas en voz alta. Las conversaciones de cada usuario ya están aisladas (D33). Tras actualizar quedan **10 skills de fábrica** (se retira la de análisis financiero). Para usarlo hacen falta el grupo **AI Conversational** y una clave MCP (§7). |

---

## 4. Requisitos previos

### 4.1 Imagen del servidor y parches de compatibilidad (lo prepara el técnico)

1. **Python:** 3.7 o superior (con 3.6 los módulos no cargan). La imagen oficial de Odoo 14 trae
   **Python 3.7.3 y Pillow 5.4.1**.
2. **Parches 1 a 4 obligatorios en Odoo 14 (N2, PNS-81).** El código del fabricante no funciona tal
   cual en Odoo 14:
   - **Parche 1** (Python < 3.9): sin él, `pns_ai_mcp` y `pns_ai_chatboo` **no se importan** y una
     base de datos que los tenga instalados **no carga**.
   - **Parche 2** (Pillow < 6): sin él fallan sin aviso las imágenes externas de las respuestas y el
     reescalado de imágenes del chat.
   - **Parche 3** (Python < 3.8): sin él fallan las consultas de la IA con parámetros de fecha.
   - **Parche 4** (API de Odoo 14, **con cualquier versión de Python**): sin él, los clientes MCP
     externos no reciben ningún contexto por `prompts/*`.
3. **Parches 5 y 6 (N2 revisada; validados en staging el 16/10/2026).** No son de Odoo 14 ni de
   PNS-81, pero se gestionan igual que los parches 1 a 4:
   - **Parche 5** (`pns_ai_mcp`, driver `openai`; PNS-93): **necesario con Gemini 3** configurado con el
     protocolo `openai`. Sin él, todo turno de Chatboo en que el modelo usa una herramienta falla en la
     ronda siguiente con `HTTP 400 … missing a thought_signature`; «Test Connection» funciona porque no
     envía herramientas. **Inocuo con otros proveedores**: los que no envían `extra_content` reciben el
     mismo mensaje que antes (la no regresión con otro proveedor compatible con OpenAI no se probó en
     staging, que solo tenía Gemini).
   - **Parche 6** (`pns_ai_chatboo`, fin de turno; PNS-94, gravedad alta): **obligatorio si se instala
     Chatboo.** Sin él, un turno con una imagen adjunta (también si el proveedor devuelve 429) deja el
     hilo del turno esperándose a sí mismo: el navegador no recibe el fin del turno, cada recarga ocupa
     un worker y Odoo se queda **sin servicio** hasta reiniciarlo. Lo puede provocar cualquier usuario
     de Chatboo. **En una instalación sin el parche 6, no adjuntar imágenes en Chatboo.**

   **Versión instalable: 3.1.782 con los parches 1 a 6** (N2 revisada, N7). Por eso se despliega
   **siempre desde la rama `14.0-pns-ai-3`**, que los incluye. Cada versión nueva del fabricante los
   elimina al sustituir el código: antes de probarla hay que repetir la comprobación de cada parche
   descrita en [parches_pns_ai.md](../pendiente/parches_pns_ai.md). Decisión N2, opción c): se
   mantienen en la rama y se pide al fabricante una fecha de corrección.

   **Comprobación del código desplegado (staging 16/10/2026):**
   `grep -rn "Seges: parche de compatibilidad" pns_base pns_ai_mcp pns_ai_chatboo` debe dar
   **10 líneas** (7 de los parches 1 a 5 y 3 del parche 6). Con menos, falta algún parche: no instalar.
4. **Librerías Python:** solo hay que añadir **`openpyxl`** (D3). `httpx` y `pydantic` **ya no hacen
   falta** (si la imagen ya las tiene, no estorban). `requests` y `reportlab` vienen con Odoo 14.
5. **Opcionales:** `xlrd` (ficheros `.xls` antiguos en Chatboo); PyMuPDF o `pdftoppm` (PDF escaneados
   como imágenes para modelos con visión). Sin ellos el módulo funciona con menos capacidad.
6. **Cómo se añaden:** en la **imagen** del cliente (su Dockerfile), nunca a mano en un contenedor en
   marcha.

### 4.2 Red y seguridad de transporte

- **Salida a Internet** hacia el proveedor de IA (si es externo), hacia las fuentes públicas de tipos
  de cambio y, si se mantiene la skill de previsión meteorológica, hacia Open-Meteo (D36). Sin
  Internet, como mucho hay una espera cada 15 minutos por las fuentes de tipos de cambio (D14, PNS-47).
- **HTTPS** obligatorio en la práctica: el botón que copia la clave MCP no funciona sin él y los
  clientes MCP externos lo necesitan.

### 4.3 Configuración de Odoo y del proxy (D15)

| Ajuste | Valor recomendado | Por qué |
|---|---|---|
| `dbfilter` (o una sola base de datos) | **Obligatorio si el servidor tiene varias bases de datos** | Las rutas `/mcp*` son `auth='none'`: no tienen sesión de la que deducir la base de datos. Con varias bases de datos y sin `dbfilter`, la dirección MCP no encuentra la base de datos y responde 404 (F24, D15; observado en la fase 3c). |
| `workers` | Mayor que 0, dimensionado para turnos largos | Cada conversación puede ocupar un proceso hasta 10 minutos. **Staging (16/10/2026):** con 2 workers, unas pocas peticiones bloqueadas (como las del bloqueo de PNS-94 sin parche 6) dejan Odoo sin servicio. Revisar el número para cada cliente (D15). |
| `limit_time_real` | **600 s o más** | Con menos, Odoo puede cortar la respuesta a medias. |
| `limit_time_cpu`, `limit_memory_hard`, `limit_request` | Revisar con el técnico | El código que genera la IA se ejecuta dentro del proceso de Odoo. |
| Proxy: ruta del chat (`/chatboo/stream`) | **Sin buffering** y tiempo de lectura alto (10 min o más). En staging: bloque propio para `/chatboo/stream` sin buffering y `proxy_read_timeout` de **900 s** (staging 15/10/2026) | Chatboo envía la respuesta en directo. |
| Proxy: servidor MCP | Con varios workers, solo `POST /mcp`; no el modo SSE (`/mcp/sse`). En staging: `location = /mcp` solo con `POST` (`GET` da 403) y `/mcp/sse` con 404 (staging 15/10/2026). **Si no hay cliente MCP externo, cerrar `/mcp`** (medida de esta guía) | SSE no funciona con varios procesos (D20). |
| Proxy: `limit_req` de `/web/login` | Revisar el `burst` | **Staging (16/10/2026):** con `burst=5`, recargar varias veces seguidas da 503 (D15). |
| PostgreSQL: `idle_in_transaction_session_timeout` en el rol de Odoo | **A decidir** (por ejemplo 15 min) | Defensa adicional contra bloqueos como el de PNS-94: no corrige el fallo (lo corrige el parche 6) y **afecta a todas las bases de datos del rol** (análisis del bloqueo, §5.2, punto 6; staging 16/10/2026). |
| Contraseña de PostgreSQL | En `odoo.conf` o en una variable de entorno leída por Odoo; **nunca con `--db_password` en la línea de órdenes** | **Staging (16/10/2026):** el entrypoint de la imagen `odoo-web` la pasa así y se ve con `ps`/`docker top` en el host; afecta también a otros servicios con esa imagen (D15). |
| Proxy: CSP | Opcional, como defensa en profundidad (§12) | D39. |

> **Nota sobre `dbfilter` y varias bases de datos:** `dbfilter` decide qué base de datos atiende cada
> petición, pero no aísla el código. En cuanto una base de datos del servidor tiene instalados los
> `pns_*`, su código se carga para todo el proceso de Odoo. Uno de sus parches, el de `http_patch.py`
> (D9, PNS-31), se aplica a todo el proceso al cargarse el módulo y alcanza también a las demás bases
> de datos que sirve ese proceso, aunque no tengan los módulos instalados. (El backport de
> `_process_ondelete`, también en PNS-31, se hace con `_inherit` y solo actúa en las bases de datos
> donde está instalado.) Si esas otras bases de datos no deben verse afectadas, se sirven desde un
> servicio de Odoo distinto.

### 4.4 Cuenta del proveedor de IA

- Una **clave de API** del proveedor elegido.
- Un **límite de gasto en la propia cuenta del proveedor**: el módulo no trae topes de gasto, tokens ni
  turnos, y no cuenta todos los tokens (por ejemplo, los de creación de caché de Anthropic) (D12,
  PNS-29).
- Base legal y contrato de encargado del tratamiento si es externo: no hay filtro por modelo, campo ni
  empresa de lo que se envía (D10, PNS-18). En staging, **solo datos de demostración** (N5).
- Con Gemini (staging 16/10/2026), comprobar antes de enviar datos reales las **condiciones de uso de
  datos del nivel gratuito** (si Google puede usar las peticiones para mejorar sus productos) (D10,
  N8; §8.1). En staging solo se enviaron datos de demostración.
- Modelos: los de Claude ya son viables. Quedan limitaciones conocidas: una temperatura 0 se envía como
  0,7, los modelos de razonamiento de OpenAI pueden rechazar los parámetros y el error que ve el usuario
  incluye la dirección del servicio (D11, PNS-40).

---

## 5. Actualización segura desde 3.1.486 (N1)

Al actualizar se pierden datos sin aviso (PNS-87, PNS-63):

- el cron nuevo del registro de actividad (`ai.log`) borra, en la primera pasada del programador
  (**unos minutos después de arrancar**, no al cabo de un día), todo lo que tenga más días que
  `pns_ai_mcp.log_retention_days` (30 si el parámetro no existe), incluido el historial de consumo y
  coste;
- la primera actualización **elimina la tabla `ai_provider_usage_day`** (histórico diario de tokens y
  coste por proveedor): la versión nueva ya no tiene ese modelo y la incluye entre las tablas antiguas
  que borra en cada actualización, así que la tabla desaparece y no se vuelve a crear;
- el cron de Chatboo (cada 5 minutos) borra las conversaciones de **todos** los usuarios con más días
  que `pns_ai_chatboo.history_retention_days` (30).

**Decisión N1, opción a):** fijar los valores con esta secuencia segura en **cada** base de datos que
se actualice. La hace el técnico; no necesita opciones especiales del servidor.

> **Pendiente de confirmar:** la secuencia está documentada en N1, pero **no se ha probado de principio
> a fin**. Se valida en la primera actualización del VPS de pruebas.

### 5.1 Antes de actualizar (con el servicio todavía en marcha)

1. **Copia de la base de datos.**
2. **Contar lo que se va a perder**, con consultas de solo lectura:
   - filas de `ai_log` con más días que la retención prevista;
   - filas de `ai_provider_usage_day`;
   - sesiones de Chatboo (`chatboo_session`) con `last_used_date` de más días que la retención prevista.
3. **Exportar `ai_provider_usage_day`** si interesa conservar el histórico de costes: la primera
   actualización elimina la tabla y no se vuelve a crear.
4. **Crear `pns_ai_mcp.log_retention_days`** en Ajustes → Técnico → Parámetros → Parámetros del sistema
   (modo desarrollador), con los días elegidos (`0` = no purgar). Este parámetro no tiene registro de
   datos en el módulo, así que crearlo antes no choca con nada, y su cron aún no existe.
   - **No crear antes `pns_ai_chatboo.history_retention_days`:** lo crea el módulo al actualizar con su
     propio XML ID. Uno creado a mano chocaría con la restricción de clave única (según el código; no
     probado).
5. **Revisar las personalizaciones que se van a perder (D17, PNS-88).** Los 38 registros con XML ID
   `mcp_*` de `pns_ai_mcp` (reglas, accesos, menús, acciones y vistas de operaciones supervisadas,
   registro de actividad, contextos y diario de cambios) se borran y se recrean con identificadores
   nuevos. Se pierden los cambios hechos sobre ellos (dominios de regla, menús, vistas, traducciones) y
   los filtros o favoritos guardados sobre esas acciones. Anotarlos para rehacerlos después. En
   `third_party` y `vertical-instaladores` no hay vistas heredadas de ellos.
6. **Revisar el agente de Chatboo (D37).** Anotar los contextos por defecto (`default_context_codes`)
   del agente `pns_ai_chatboo`. Una base de datos que haya pasado por versiones anteriores puede traer
   el contexto `acl_security`, que una instalación nueva no tiene. Si lo trae, igualarlo con una
   instalación nueva, para que el chat se comporte igual en todos los entornos. Referencia de una
   instalación nueva (staging 15/10/2026): «@pns_ai_mcp» y «@pns_ai_chatboo», sin `acl_security`
   (§13, punto 11).
7. **Comprobar el código desplegado:** que la rama incluye los parches 1 a 6 (§4.1; el `grep` debe dar
   10 líneas, staging 16/10/2026) y que la imagen tiene `openpyxl`.

### 5.2 Actualización

8. **Parar el servicio de Odoo.**
9. **Actualizar sin arrancar el servidor**:
   `odoo -c <archivo de configuración> -d <base de datos> -u pns_base,pns_ai_mcp,pns_ai_chatboo --stop-after-init`.
   El proceso termina al acabar y **no ejecuta crons**.
10. **Fijar `pns_ai_chatboo.history_retention_days`** (que ya existe con su XML ID) con `odoo shell`,
    que tampoco ejecuta crons: `env['ir.config_parameter'].set_param('pns_ai_chatboo.history_retention_days', '<días>')`
    seguido de `env.cr.commit()`.
11. **Arrancar el servicio.** En una base de datos neutralizada los crons siguen desactivados; en
    producción se activan y ejecutan las purgas con los valores fijados.

### 5.3 Comprobaciones posteriores

12. **Crons:** en Ajustes → Técnico → Automatización → Acciones planificadas, los seis de los módulos
    `pns_*` deben estar activos (salvo en una base de datos neutralizada) y con **número de llamadas
    `-1` (ilimitado)**:

    | Cron | Intervalo |
    |---|---|
    | `pns_base.ir_cron_pns_export_purge` (nuevo: borra exportaciones de más de 24 h) | 1 hora |
    | `pns_ai_mcp.ir_cron_ai_log_retention` (nuevo: retención del registro de actividad) | 1 día |
    | `pns_ai_mcp.ir_cron_ai_api_result_cache_gc` (la actualización lo repara: pasa de 0 a -1) | 1 hora |
    | `pns_ai_mcp.ir_cron_ai_fetch_cache_gc` | 1 hora |
    | `pns_ai_mcp.ir_cron_ai_safe_operation_expire` | 5 min |
    | `pns_ai_chatboo.ir_cron_chatboo_async_maintenance` (también purga conversaciones antiguas) | 5 min |

    Tras la primera pasada, todos deben tener la siguiente ejecución en el futuro.
13. **Log del servidor:** ningún `Traceback`, `ERROR` ni `CRITICAL` durante la actualización y el
    arranque. Si aparece `TypeError: 'type' object is not subscriptable`, falta el parche 1.
14. **Parámetros:** `pns_ai_mcp.log_retention_days` y `pns_ai_chatboo.history_retention_days` con los
    valores decididos.
15. **`prompts/*` por `/mcp`:** con un cliente MCP y la clave de un usuario de prueba, la lista de
    prompts debe incluir sus contextos y los compartidos, no solo `system_prompt`. Si solo aparece
    `system_prompt`, falta el parche 4. Si `system_prompt` aparece dos veces, es un defecto conocido
    del módulo que se comunicará al fabricante; no impide dar la prueba por buena.
16. **Menús:** abrir uno de cada (operaciones supervisadas, registro de actividad, contextos y diario de
    cambios), y los Ajustes de IA y de Chatboo.
17. **Personalizaciones y agente:** rehacer lo anotado en los pasos 5 y 6.
18. **Ficha de un módulo OCA** en Aplicaciones: su enlace vuelve al de su manifiesto al actualizar la
    lista de aplicaciones (PB-1; inferido del código, sin probar).
19. **Restos inocuos:** quedan 30 tablas `pns_ai_mcp_*` de asistentes antiguos sin modelo (sin impacto
    funcional) y los 5 servidores externos de fábrica, inactivos (§10).

---

## 6. Instalación y configuración paso a paso

Orden para una instalación nueva o tras la actualización de §5. Lo hace un usuario que sea a la vez
**administrador de Odoo (Ajustes)** y **AI Administrator**.

| # | Paso | Ruta de menú | Qué hacer |
|---|---|---|---|
| 1 | Instalar "AI Engine" | Aplicaciones → "AI Engine" → Instalar | Instala `pns_base` y `pns_ai_mcp`. Un administrador de Odoo no ve el menú "AI Engine" hasta tener un grupo de IA. |
| 2 | Grupos de IA | Ajustes → Usuarios y compañías → Usuarios → (usuario) | Asignar según §7. |
| 3 | Proveedor de IA | AI Engine → Connections → Providers | Según §8: clave, modelo, «No external failover» si es local, archivar los que no se usen. |
| 4 | Ajustes de AI Engine | Ajustes → AI Engine (el menú AI Engine → Settings solo lo ve el administrador de Odoo, D5) | Política de URL `whitelist_only` (§9), moneda de costes y fuentes de tipos de cambio. |
| 5 | Lista blanca | AI Engine → Connections → Whitelist | Dejar solo los dominios imprescindibles (§9). |
| 6 | Servidores externos | AI Engine → Connections → External Servers | Ninguno nuevo en staging; los 5 heredados, inactivos (§10). |
| 7 | Instalar Chatboo | Aplicaciones → "Chatboo" → Instalar | Crea el agente de Chatboo, sus contextos, skills de fábrica, parámetros y el cron de mantenimiento. |
| 8 | Cadena del agente de Chatboo | AI Engine → Agents → Chatboo → pestaña "Providers" | **Siempre definida** (§8). |
| 9 | Ajustes de Chatboo | Ajustes → AI Engine → bloque "Chatboo" | **Interface:** «Show Chatboo in systray». **Conversation memory:** «Hidden list copy (MB)» (8; no poner 0, que es «sin límite», D30), «Hours that copy lasts», «Session retention (days)» (30, §11.2), «Download limit (MB)» y «Upload limit (MB)» (15). **Data presentation:** «Chart engine», «Default showmode», «Excel float decimals» y «Excel thousand separators». Estos ajustes se guardan en Parámetros del sistema: cambiarlos aquí equivale a cambiar el parámetro. |
| 10 | Parámetros del sistema | Ajustes → Técnico → Parámetros → Parámetros del sistema | `pns_ai_mcp.log_retention_days` (§11.2), que no está en Ajustes. |
| 11 | Usuarios MCP y claves | AI Engine → Security → Users → (usuario) | Generar la clave con el asistente y marcar el acceso conversacional (§7). **No usar la mesa de PIN** (N4) ni el botón «Regenerate PIN» de la vista de lista, que genera PIN (§7.1, punto 3). |
| 12 | Grupos funcionales para las skills de Chatboo y para las escrituras | Ficha del usuario | Contabilidad para las skills financieras; Ventas para el equipo de ventas en el cuadro de mando. Para un AI Writer, los grupos de Odoo de los modelos en que vaya a escribir (§7, punto 2; staging 16/10/2026). |
| 13 | Acciones planificadas | Ajustes → Técnico → Automatización → Acciones planificadas | Comprobar los seis crons de §5.3, paso 12. |
| 14 | Opcional: cliente MCP externo | Fuera de Odoo | Dirección `https://<servidor>/mcp` y la clave en una **cabecera**, nunca en la URL (D20, PNS-33). No en staging salvo que sea lo que se quiere validar. |

---

## 7. Grupos, usuarios y claves MCP

Grupos de la sección "Artificial Intelligence" de la ficha de usuario. Ninguno se asigna solo.

1. **AI Administrator — solo para quien ya es administrador de Odoo (D4).** Equivale en la práctica a
   administrador de Odoo: un AI Administrator sin Ajustes puede llegar a darse la administración (resto
   de PNS-01/02). Además implica **AI Writer, External URL y External API**, ve los PIN y claves de la
   mesa de PIN (PNS-84) y usa el generador OpenAPI (PNS-86). No implica AI Conversational.
2. **AI Writer — solo para técnicos de confianza (D4, D27).** Su riesgo baja a medio: ya no escala
   permisos al guardar ni escribe en las instrucciones de todos. Sigue pudiendo crear y activar skills
   con código **sin revisión** (PNS-23). Hace falta para que la IA proponga escrituras y para crear,
   borrar y renombrar skills desde el chat.
   **Permisos de Odoo (staging 16/10/2026):** las escrituras confirmadas se ejecutan **con los permisos
   de Odoo del usuario**. Un AI Writer necesita además los grupos de Odoo del modelo en que escribe (por
   ejemplo, «Creación de contactos», `base.group_partner_manager`, para contactos). Sin ellos, el flujo
   es tarjeta → confirmación → `AccessError` de Odoo → operación fallida sin escribir nada.
3. **AI Conversational (`group_ai_conversational`) + clave MCP = acceso al chat (D46).** El grupo es
   nuevo en 3.1.782 y se asigna desde la ficha del usuario MCP (AI Engine → Security → Users), con la
   casilla «AI Conversational». **Confirmado en staging (15/10/2026):** el acceso al chat exige el
   grupo y la clave, ni más ni menos (§13, punto 3). Dar el chat solo a un grupo piloto reducido: cualquier usuario del chat o de MCP puede usar las skills de
   fábrica de censo de usuarios e información del sistema (D36, PNS-66) y llegar a métodos internos
   desde el código de la IA (restos de PNS-07/19).
4. **External URL (`group_ai_external_url`) — solo para quien lo necesite (N3).** Es el que permite
   descargar páginas con `fetch_url`. Limitarlo reduce quién recibe un contenido manipulado de la caché
   (PNS-90) y quién usa los dominios añadidos a la lista blanca (PNS-91), pero no impide ninguna de las
   dos cosas.
5. **External API:** lo implica AI Administrator. No se ha analizado una recomendación propia para este
   grupo (**Pendiente de confirmar**); en staging, sin servidores externos activos (§10), no tiene uso.

### 7.1 Claves MCP

1. Generar la clave **con el asistente** de la ficha del usuario MCP. La clave **solo se ve en ese
   momento** (solo se guarda un resumen del que no se puede recuperar).
2. Entregarla **por un canal propio** y seguro, fuera de Odoo.
3. **Nunca usar la mesa de entrega de claves por PIN (N4):** no abrirla y no generar PIN. Con la mesa
   abierta, cualquier usuario autenticado, también de portal, podría obtener claves de otros (PNS-83);
   el PIN y la clave quedan además en claro en la base de datos y en el navegador (PNS-84).
   **Cuidado con el botón «Regenerate PIN»** de la vista de lista de usuarios MCP (AI Engine →
   Security → Users): **genera PIN**. No usarlo. Si se generan por error, borrarlos con «Delete PIN»
   antes de seguir (incidencia corregida en staging, 15/10/2026; la mesa no se abrió).
4. Revocar las claves que no se usen. Una clave revocada deja de funcionar también en las sesiones MCP
   ya abiertas (PNS-13, corregido).
5. En los clientes MCP externos, la clave va en una cabecera y no en la URL (D20, PNS-33). En
   `POST /mcp` el servidor acepta tres cabeceras: `X-Mcp-Token`, `X-MCP-API-Key` (la que cita D20) y
   `Authorization: Bearer <clave>`. Cualquiera de las tres sirve. Si no llega ninguna, acepta también el
   parámetro `?api_key=` en la URL, que **no se debe usar**. El servidor escribe en su log (nivel INFO)
   los 10 primeros caracteres de la clave en cada petición (PNS-33,
   `pns_ai_mcp/controllers/main.py:863` y `:869`): proteger el acceso al log.
6. Tras generar la clave, el menú de Chatboo ya aparece sin recargar el navegador (PNS-76).

---

## 8. Proveedores de IA y cadena del agente

1. **Cadena del agente siempre definida.** En AI Engine → Agents → Chatboo → "Providers", añadir los
   proveedores que se quieran usar, con su prioridad. **Sin cadena, el motor usa todos los proveedores
   activos por orden de id**, sean cuales sean (observación de PNS-61; fase 3b-2). El usuario ya
   no puede elegir un proveedor fuera de la cadena (D12, PNS-61).
2. **Proveedor:** pegar la clave de API, cargar el catálogo de modelos y elegir el modelo. «Test
   Connection» exige tener un modelo elegido y hace una conversación real con el proveedor (coste
   mínimo). No marcar la capacidad de audio si no se usa: al guardar lanza una prueba de voz hacia el
   proveedor (fase 3b-2).
3. **Proveedores locales: marcar «No external failover» (D10, PNS-18).** Si el proveedor es local, toda
   su cadena debe llevarlo: así, si el local falla, el turno termina en error en lugar de pasar a un
   proveedor externo (comprobado en 3b-2). Es la forma de garantizar que los datos no salen del
   servidor. No añade filtro por modelo, campo ni empresa.
4. **Respaldo de la misma naturaleza:** todo local o todo con contrato, porque el respaldo recibe los
   mismos datos (D10).
5. **Archivar los proveedores de fábrica que no se usen.** Así, aunque una cadena quede vacía, ningún
   texto puede salir hacia ellos (fase 3b-2). En una base de datos actualizada desde 3.1.486 quedaban
   OpenRouter, OVH, Lemonade y Ollama, sin clave. Una instalación nueva de 3.1.782 no crea ningún
   proveedor: todos se dan de alta a mano.
6. **No duplicar proveedores:** la copia **se lleva la clave de API** del original (observación de
   PNS-20). Crear el proveedor nuevo desde cero. Si se duplicó alguno, borrar la copia o vaciar su
   clave.
7. **Cadena con dos proveedores** (medida de esta guía, a partir del staging del 16/10/2026): con
   cuotas diarias por modelo y errores 503 frecuentes como los de §8.1, conviene que la cadena del
   agente tenga dos proveedores (o dos modelos), para repartir la cuota y tener respaldo. Se aplica el
   punto 4: los dos de la misma naturaleza, porque el respaldo recibe los mismos datos (D10).

### 8.1 Gemini (staging 16/10/2026)

Proveedor usado en el staging (N8), en el nivel gratuito y con datos de demostración:

| Aspecto | Qué se observó o hay que hacer |
|---|---|
| Protocolo y dirección | Protocolo **`openai`**, con el endpoint `…/v1beta/openai/chat/completions`. Necesita el **parche 5** (§4.1): sin él, todo turno con herramientas falla con HTTP 400 (PNS-93). |
| Modelos usados | `gemini-3.6-flash`, `gemini-3.5-flash-lite` y `gemini-3.5-flash`. |
| Modelos con problemas | `gemini-3.7-flash` y `gemini-3.8-flash` dieron **503 con frecuencia**; `gemini-2.5-flash` y `gemini-2.5-flash-lite` dan **404** («no longer available to new users») a los usuarios nuevos. |
| Cuota del nivel gratuito | **20 peticiones al día por modelo**; al agotarla, 429 `RESOURCE_EXHAUSTED`. Para un uso real, valorar el nivel de pago (plan de staging, §7.2). |
| Uso de datos | **Antes de enviar datos reales**, comprobar las condiciones de uso de datos del nivel gratuito (si Google puede usar las peticiones para mejorar sus productos) (D10, N8). |
| Calidad de los modelos `lite` | Con `lite` se observó (PNS-96): interpreta mal «empresas», inventa ids en los enlaces, muestra los errores de acceso tal cual y añade «>» de más al formato. Tenerlo en cuenta al elegir el modelo. |

---

## 9. Política de URL y lista blanca (D24)

1. **Política: `whitelist_only`** (valor por defecto). Las direcciones internas ya están protegidas en
   `fetch_url`: rechaza direcciones no públicas, valida cada redirección y corta a 20 MB (PNS-17).
2. **Advertencia mientras no se corrija PNS-91:** `whitelist_only` **no limita de verdad los
   dominios**, porque cualquier usuario autenticado puede añadirlos o reactivarlos en la lista blanca.
   Por eso las condiciones de §2.1 (sin portal, usuarios de confianza) son imprescindibles.
3. **No usar nunca `open`:** con `open` la IA descarga cualquier dirección, el servidor descarga
   imágenes externas de cualquier dominio (resto de PNS-59) y el dominio se añade solo a la lista al
   confirmar.
4. **Lista blanca mínima.** Si no se va a probar la previsión meteorológica de Chatboo, quitar
   `api.open-meteo.com` y `geocoding-api.open-meteo.com` (D36). Los dominios que sobren se
   **borran, no se archivan**: una entrada archivada se puede reactivar (PNS-91), y la lista de
   fábrica solo se carga en la primera instalación, así que lo borrado no vuelve al actualizar
   (medida de esta guía).
5. **Revisar periódicamente la lista blanca** (AI Engine → Connections → Whitelist) en busca de
   dominios que nadie haya autorizado, **incluidos los archivados**: cualquier usuario autenticado puede
   añadir dominios y también reactivar los archivados (PNS-91).
6. Guardar los Ajustes de AI Engine reescribe la política de URL (D9, PNS-31): comprobarla después de
   cada guardado.

---

## 10. Servidores externos (D7)

1. **En staging, no dar de alta ninguno.**
2. **Servidores heredados:** las bases de datos actualizadas desde 3.1.486 conservan **5 servidores de
   fábrica, inactivos**, que Odoo no borra (PNS-88): tres de tipo `stdio` (`mcp_test`,
   `brave_search` y `seq_thinking`) y dos OpenAPI (`sesame` y `cdmon`). **Dejarlos inactivos.** Si se
   borran o no lo decide D7, todavía abierta (**Pendiente de decisión**).
3. **`stdio`, prohibido:** ahora solo un administrador de Ajustes puede crearlo o cambiarlo (PNS-09),
   pero ejecuta comandos en el servidor.
4. **OpenAPI:** no usarlo contra hosts que redirijan; el driver sigue las redirecciones con las
   cabeceras de autenticación (resto de PNS-17).
5. **Ninguno marcado "trusted"** (D25).

---

## 11. Copias de configuración y retención

### 11.1 Copias de configuración (D8)

1. La exportación ya sale **sin secretos por defecto** y pregunta si incluirlos; los archivos se borran
   a las 24 h (PNS-20).
2. **Mientras siga PNS-82, no exportar nunca con secretos:** durante esas 24 h cualquier interno podría
   apropiarse de la copia.
3. **No importar copias de origen desconocido:** la importación sigue sobrescribiendo sin resumen previo
   y puede cambiar proveedores, direcciones o la política de URL (resto de PNS-20).

### 11.2 Retención (D13, D35, N1)

| Parámetro | Por defecto | Dónde se cambia |
|---|---|---|
| `pns_ai_mcp.log_retention_days` (registro de actividad; `0` = no purgar) | 30 días | Solo en Parámetros del sistema (no está en Ajustes). |
| `pns_ai_chatboo.history_retention_days` (conversaciones de todos los usuarios; `0` = no purgar) | 30 días | Ajustes de Chatboo («Session retention (days)», §6 paso 9) o Parámetros del sistema. En una actualización, con el servicio parado (§5 paso 10). |
| `pns_base.export_retention_hours` (archivos de exportación; `0` = no borrar) | 24 h | Parámetros del sistema. |
| `pns_ai_chatboo.download_max_bytes` / `pns_ai_chatboo.upload_max_bytes` | 15 MB | Ajustes de Chatboo («Download limit (MB)» y «Upload limit (MB)») o Parámetros del sistema (en bytes). |

**Al terminar las pruebas, borrar la base de datos de staging** (medida de esta guía): guarda
conversaciones, registro de actividad, resúmenes de claves MCP y claves de proveedor que ya no hacen
falta.

---

## 12. Otras medidas prudentes para staging

| Medida | Qué hacer | Referencia |
|---|---|---|
| Usuarios | Solo personal técnico, sin portal; datos de demostración. | N3, N5 |
| Lectura en voz alta | Ahora prefiere una voz local; si el navegador no la tiene, usa una remota (Google o Microsoft). No hay ajuste global para desactivarla: indicar a los usuarios que no la activen. | D41, PNS-64 |
| Exportaciones del chat | Los documentos se suben solos a Odoo (D42) y, por PNS-82, otros internos pueden llegar a ellos: no generar exportaciones con datos sensibles. | D42, PNS-65, PNS-82 |
| CSP en el proxy | Opcional: limitar las imágenes al propio dominio (más `data:` y `blob:`). Ahora es solo defensa en profundidad, porque las imágenes externas ya pasan por el servidor; no corta la salida desde el servidor. | D39, PNS-59 |
| Tope de datos por turno | Mantener 8 MB (no 0): «Hidden list copy (MB)» en los Ajustes de Chatboo. | D30 |
| Escrituras supervisadas | Los dos caminos de confirmación (aviso del chat y botón de Autorizaciones) comprueban el dueño; la elección es de usabilidad. | D26 |
| Contextos y skills de fábrica | Los cambios sobre ellos se pierden en cada actualización: hacerlos como contextos o skills propios. | D17, D38, PNS-32 |

---

## 13. Cómo comprobar que funciona

Con un usuario que tenga solo AI Conversational y clave MCP (y otro con External URL), datos de
demostración y textos inocuos:

1. **Instalación o actualización:** §5.3 completo.
2. **Proveedor:** "Test Connection" responde correctamente y deja una línea en AI Engine → Security →
   Activity.
3. **Acceso al chat:** el usuario con grupo y clave ve el icono de Chatboo; uno sin ellos no
   (conforme en staging, 15/10/2026).
4. **Consulta de solo lectura** sobre datos de demostración: respuesta en directo, con tabla si
   procede, y una línea nueva en el registro de actividad.
5. **Contexto de pantalla:** con un cliente abierto, preguntar por "este cliente".
6. **Escritura supervisada** con un AI Writer: aparece la tarjeta de confirmación y la operación en
   AI Engine → Security → My Authorizations; tras confirmarla, **un AI Administrator** comprueba que
   el cambio figura en AI Engine → Security → Applied changes (el AI Writer no ve ese menú).
7. **Exportación** a Excel y PDF de una respuesta con tabla.
8. **Conversaciones:** cerrar y abrir el chat; la anterior sigue disponible. Otro usuario no la ve.
9. **Las nueve pruebas pendientes de staging (N5)**, cuyo procedimiento está en la
   [verificación](../pendiente/verificacion_seguridad_pns_ai.md) («Pruebas pendientes para staging») y
   en el [plan de staging](../pendiente/plan_staging_pns_ai.md), §5:

   | # | Qué se comprueba | Resultado esperado |
   |---|---|---|
   | 1 | Consulta por rango de fechas (parche 3, PNS-81) | Responde sin error de la herramienta. |
   | 2 | Foto con orientación EXIF adjunta en el chat (parche 2) | La IA la interpreta derecha. |
   | 3 | Instrucciones ocultas en un registro (PNS-16) | Aparece la tarjeta de confirmación, sin auto-confirmación ni salida al exterior. |
   | 4 | Historial enviado por el navegador (PNS-61) | Un proveedor fuera de la cadena se ignora; un turno inventado en el historial hoy se trata como real (resto conocido). Procedimiento y criterio: plan de staging (fase 5c). |
   | 5 | Creación de un registro sin AI Writer (PNS-22) | Se rechaza. |
   | 6 | Estado de una operación de otro usuario (PNS-05) | Responde que no existe. |
   | 7 | Nombre de la base de datos y campos de un modelo sin acceso (PNS-36) | Se anota si los obtiene (prueba de observación). Procedimiento y criterio: plan de staging (fase 5c). |
   | 8 | Saneado de la respuesta y de su exportación (PNS-60) | Sin contenido activo; si sale bien, D29 deja de bloquear. |
   | 9 | Imágenes externas en el navegador y tokens con Anthropic (PNS-59, PNS-29) | Una imagen de un host no permitido sale como enlace o texto alternativo, sin petición al exterior; los tokens de `ai.log` se comparan con los de la consola del proveedor. Procedimiento y criterio: plan de staging (fase 5c). |

   **Resultado (staging 16/10/2026;** detalle en el plan de staging, §6.1, y en la verificación,
   «Staging (15-16/10/2026)»): 1, 2, 4b, 5, 6, 8 y 10 CORREGIDO; 3 y 9a CORREGIDO en la parte
   principal (con `whitelist_only`), con observaciones NO CONCLUYENTES; 4a y 7, el resto conocido
   (SIN CAMBIOS, previsto); 11 NO CONCLUYENTE (PNS-95); **9b no realizada** (sin Anthropic; queda
   para cuando se use ese proveedor).
10. **Fin de turno con imagen (parche 6, PNS-94; staging 16/10/2026).** Adjuntar una imagen pequeña en
    Chatboo y preguntar por ella:
    - el navegador recibe el fin del turno (desaparece el indicador de espera y se ve la respuesta o
      el error del proveedor) **sin recargar la página**;
    - unos segundos después, en `pg_stat_activity` (consulta de solo lectura) **no hay conexiones
      `idle in transaction`** del worker que llevaba el turno **ni conexiones esperando un lock**
      (`wait_event_type = 'Lock'`).

    Si el turno no termina, **no recargar** (cada recarga ocupa un worker): falta el parche 6 (§4.1,
    §14). Procedimiento completo en el
    [análisis del bloqueo](../pendiente/analisis_bloqueo_chatboo_session.md), §5.1, «Validación del
    parche 6».
11. **Agente de Chatboo en una instalación nueva (D37, referencia; staging 15/10/2026):** el
    `default_context_codes` del agente `pns_ai_chatboo` es «@pns_ai_mcp» y «@pns_ai_chatboo», y no
    existe ningún contexto `acl_security` (ni XML ID ni `code`). Es la referencia con la que comparar el
    agente de una base de datos actualizada (§5.1, paso 6).

---

## 14. Problemas típicos y su solución

| Síntoma | Causa | Solución |
|---|---|---|
| Odoo no carga la base de datos tras sustituir el código; el log muestra `TypeError: 'type' object is not subscriptable` | Falta el parche 1 (PNS-81) | Desplegar desde la rama con los parches 1 a 6 (§4.1). No se arregla con librerías. |
| Odoo no deja instalar "AI Engine" y menciona una librería | Falta `openpyxl` en la imagen | Añadirla a la **imagen** del cliente y reconstruirla (D3). |
| Las imágenes externas de las respuestas no se ven (404) o las fotos llegan sin reescalar | Falta el parche 2 (Pillow 5.4) | Ver §4.1. |
| Las consultas con fechas dan error de la herramienta | Falta el parche 3 | Ver §4.1. |
| Un cliente MCP externo solo ve `system_prompt` y ningún contexto | Falta el parche 4 | Ver §4.1. |
| Con Gemini, «Test Connection» funciona pero las preguntas que consultan datos fallan con `HTTP 400 … missing a thought_signature` | Falta el parche 5 (PNS-93) | Ver §4.1 y §8.1 (staging 16/10/2026). |
| Tras adjuntar una imagen en Chatboo el turno no termina en el navegador; al recargar, Odoo deja de responder | Falta el parche 6 (PNS-94) | Reiniciar el servicio de Odoo y desplegar el parche 6 (§4.1). Mientras no esté, no adjuntar imágenes (staging 16/10/2026). |
| Gemini responde 503, 404 o 429 `RESOURCE_EXHAUSTED` | Modelo saturado, modelo no disponible para usuarios nuevos o cuota diaria del nivel gratuito agotada | Cambiar de modelo o añadir un segundo proveedor a la cadena (§8, punto 7; §8.1) (staging 16/10/2026). |
| Una escritura confirmada por un AI Writer falla con `AccessError` | El usuario no tiene los grupos de Odoo del modelo | Darle el grupo de Odoo que corresponda (§7, punto 2) (staging 16/10/2026). |
| La página de acceso da 503 al recargar varias veces seguidas | `limit_req` del proxy en `/web/login` (`burst=5` en staging) | Revisar el límite del proxy (§4.3) (staging 16/10/2026). |
| La dirección `/mcp` devuelve 404 | Varias bases de datos sin `dbfilter` | Configurar `dbfilter` o usar una sola base de datos (§4.3). |
| Tras actualizar desapareció el registro de actividad antiguo, el histórico de costes o conversaciones antiguas | Purgas de la versión nueva (PNS-87, PNS-63) | Solo se recupera desde la copia previa. Para la siguiente base de datos, seguir §5. |
| Tras actualizar se perdieron cambios en menús, reglas o vistas de AI Engine, o favoritos de esas pantallas | Recreación de los 38 XML ID `mcp_*` (PNS-88) | Rehacerlos con lo anotado en §5.1, paso 5. |
| El chat de una base de datos actualizada se comporta distinto que el de una nueva | Contexto `acl_security` heredado en el agente de Chatboo (D37) | §5.1, paso 6. |
| La IA usa un proveedor que nadie configuró para ese agente | El agente no tiene cadena y se usan todos los activos | Definir la cadena y archivar los proveedores que no se usen (§8). |
| Un proveedor recién creado ya tiene clave | Se creó duplicando otro (PNS-20) | Borrar la copia o vaciar su clave; crear los proveedores desde cero. |
| "Test Connection" da un error sin llegar al proveedor | No hay modelo elegido | Elegir antes el modelo del catálogo. |
| Los gráficos del chat se pintan mal tras abrir una vista gráfico de Odoo | Choque de la librería de gráficos (PNS-70, sin cambios) | Recargar la página. |
| La respuesta aparece de golpe, se corta o queda incompleta | Proxy con buffering o `limit_time_real` bajo | Revisar §4.3. |
| Errores del proveedor con modelos recientes; el usuario ve la dirección del servicio | Parámetros que algunos modelos rechazan (D11, PNS-40) | Elegir otro modelo o informar al fabricante. |
| Se perdió la clave MCP | Solo se muestra al generarla | Generar una nueva con el asistente (§7.1). |

---

## 15. Lista de reverificación ante una versión corregida

Repetir en el laboratorio (base de datos de demostración) con un usuario interno **sin ningún grupo de
IA ni de administración** y un usuario **de portal**, y después las nueve pruebas de staging (§13). El
procedimiento está en la [verificación](../pendiente/verificacion_seguridad_pns_ai.md) y en el
[seguimiento](../pendiente/seguimiento_informe_pns_ai.md); aquí solo figura el resultado esperado.

Antes: comprobar si la versión nueva aún necesita los parches 1 a 6 (§4.1) y actualizar con la
secuencia de §5.

| PNS | Qué se comprueba | Resultado esperado para darlo por corregido |
|---|---|---|
| **PNS-82** | Que un interno no pueda llevarse a su conversación adjuntos de otros usuarios | El adjunto no cambia de dueño; el interno no puede descargarlo. |
| **PNS-83** | Canje de PIN por un usuario sin permisos (interno y portal) | **Error de acceso**; sin mesa abierta no se devuelve ninguna clave; los bloqueos por IP no los gestiona cualquiera. |
| **PNS-85** | Que un usuario sin permisos de escritura fije los parámetros de las skills de otros | **Error de acceso**. |
| **PNS-90** | Lectura y escritura de la caché de páginas descargadas por un interno sin IA y por un portal | **Error de acceso** en ambos casos. |
| **PNS-91** | Ampliación de la lista blanca por un interno sin IA y por un portal | **Error de acceso**; la lista no cambia. |
| Resto de **PNS-01/02** | Un AI Administrator sin Ajustes intenta darse la administración de Odoo | Se rechaza. |
| Resto de **PNS-07/19** | Acceso a métodos internos desde el código de la IA | Bloqueado, incluido el que devuelve la clave del proveedor. |
| **PNS-92** | Generación de la clave MCP de otro usuario sin permisos | Rechazada por un control previo, no por un efecto lateral. |
| **PNS-81** | La versión del fabricante funciona en Odoo 14 sin parches | Se importa y funcionan imágenes, fechas y `prompts/*` sin parches. |
| **PNS-93 / PNS-94** | La versión del fabricante funciona sin los parches 5 y 6 (staging 16/10/2026) | Con Gemini por el protocolo `openai`, varias rondas de herramientas sin 400; un turno con imagen termina sin recargar y sin conexiones colgadas (§13, punto 10). |
| **PNS-87/88** | Pérdida de datos al actualizar | Aviso o migración del histórico; renombrado de XML ID sin perder personalizaciones. |

Si todas dan el resultado esperado, revisar de nuevo N3, D1 y D33.

---

## 16. Lo que no se ha podido comprobar y lo pendiente de confirmar

### 16.1 Pendiente de confirmar (indicaciones de esta guía sin respaldo completo en las fuentes)

- La **secuencia de actualización de §5**, de principio a fin (N1 la documenta; no se ha probado; el
  staging fue una instalación nueva y hoy N1 no aplica a ningún entorno).
- ~~Si **grupo AI Conversational + clave MCP** bastan siempre para el chat (§7, D46).~~ **Resuelto
  (staging 15/10/2026):** el acceso exige el grupo y la clave, ni más ni menos (§7, punto 3; §13,
  punto 3).
- **Recomendación para el grupo External API** (§7).
- **Borrado de los 5 servidores heredados:** pendiente de decisión (D7).
- **Cadena con dos proveedores (§8, punto 7) y cierre de `/mcp` sin cliente MCP externo (§4.3):**
  medidas de esta guía a partir del staging, sin decisión propia en las fuentes.

### 16.2 Sin validar en el laboratorio

- ~~Las **nueve pruebas pendientes de staging** (§13): el proveedor estaba saturado en la fase 3b-2.~~
  **Hechas en staging (16/10/2026)** salvo la **9b** (tokens con Anthropic, PNS-29): sin clave de
  Anthropic; queda para cuando se use ese proveedor (§13, punto 9).
- **Medida real de las purgas** (`ai_log`, `ai_provider_usage_day`, conversaciones): en el laboratorio
  las tablas estaban vacías, y en staging también (instalación nueva sin datos antiguos).
- **Choque del parámetro de retención de Chatboo** si se crea a mano antes de actualizar (inferido del
  código; la secuencia de §5 lo evita).
- **Enlace de los módulos OCA** tras actualizar la lista de aplicaciones (PB-1; en staging no aplicó:
  sin módulos OCA).
- **Python del VPS** del cliente (D3) y comportamiento con una versión distinta de 3.7.3. (El VPS de
  staging tiene Python 3.7.3, como la imagen oficial.)
- **Proveedores concretos** distintos de Gemini (D11) y **proveedor local** con «No external failover»
  en un VPS real. Era la opción b) de N5, que no se eligió: se decidió la a), con la c) como puente.
  Tampoco se probó la no regresión del parche 5 con otro proveedor compatible con OpenAI (§4.1).
- **CSP en el proxy:** efecto en Chatboo y en otros módulos (D39).
- **Turnos más largos que `limit_time_real`** con varios workers (F26, F44) y servidor MCP con clientes
  concretos (D20).
- **Navegadores del cliente** y voces locales disponibles (D40, D41).
- **Conflictos con módulos `web_*` de OCA** por el cambio global de validación de `pns_base` (PB-2).
- **Rendimiento de las skills financieras** con datos reales (F49).
- **D17** (personalizaciones `mcp_*`, PNS-88) y la comparación de **D37** con una base de datos
  actualizada: el staging solo aportó la referencia de una instalación nueva (§13, punto 11).

### 16.3 Pendiente tras el staging (16/10/2026)

Del [plan de staging](../pendiente/plan_staging_pns_ai.md), §7.2:

- **Proveedor para LIYBEN** (N8): se estudia **OVH**. Si fuera Gemini, valorar el **nivel de pago**
  (§8.1).
- **Condiciones de uso de datos del nivel gratuito de Gemini** antes de enviarle datos reales (D10,
  N8; §4.4).
- **LIYBEN instalada el 16/10/2026** con los parches 1 a 6 (rama `14.0-pns-ai-3`, `578859b`); registro
  en [instalacion_liyben_pns_ai.md](../pendiente/instalacion_liyben_pns_ai.md).
- **LIYBEN mantiene 18 usuarios de portal activos** (último acceso, 12/2024), en contra de la condición
  de §2.1: decisión provisional hasta la reunión (PNS-90 y PNS-91 abiertos).
- **Contraseña de PostgreSQL visible en el host** (`--db_password` en la línea de órdenes del
  entrypoint de `odoo-web`; afecta también a `odoo14_server`/LIYBEN): pasarla por `odoo.conf` o por
  variable de entorno (decisión de infraestructura, D15; §4.3).
- **`idle_in_transaction_session_timeout`** en el rol de Odoo de PostgreSQL: a decidir; afecta a todas
  las bases de datos del rol (§4.3).
- **Nginx y workers** (D15): revisar el `limit_req` de `/web/login` (`burst=5`) y el número de workers
  para LIYBEN (§4.3).
- **Informe al fabricante** de PNS-93 a PNS-96, pidiendo la corrección de fondo del bloqueo (no solo la
  1a aplicada como parche 6) ([análisis del bloqueo](../pendiente/analisis_bloqueo_chatboo_session.md),
  §6).
