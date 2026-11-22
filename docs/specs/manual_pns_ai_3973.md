# Manual de uso y configuración de los módulos de IA (Odoo 14, 3.1.973 con los parches de Seges)

- **Versión que describe:** `pns_base` 1.2.69, `pns_ai_mcp` 3.1.973 y `pns_ai_chatboo` 2.1.587, con los 24 parches
  activos de Seges (rama `14.0-pns-ai-3973`; la misma que se instaló en LIYBEN el 20/11/2026).
- **Sustituye a** [guia_configuracion_pns_ai.md](guia_configuracion_pns_ai.md), que queda como registro de 3.1.782.
- **Etiquetas de pantalla:** las del español de los módulos (`i18n/es.po`). Donde el módulo no trae traducción, la
  etiqueta sale en inglés y se cita así.
- **Fuentes:** el código de la rama y la documentación del repo; cada parte las lista al final. La web del fabricante
  se compara aparte (Anexo A). Lo que solo se comprueba con Odoo en marcha se comprueba con la prueba automática del
  final.
- **Estado:** completo (22/11/2026). Parte 1: §0 y Parte I. Parte 2: Parte II. Parte 3 (22/11/2026): Anexos A y B,
  «Etiquetas de pantalla», «Comprobación en ejecución» y «Fuentes de los anexos».

## Índice

0. [Qué es cada módulo y cómo encajan](#0-qué-es-cada-módulo-y-cómo-encajan)
- [Parte I. Usuario de Chatboo](#parte-i-usuario-de-chatboo)
  1. [Antes de empezar: quién puede usar el chat](#1-antes-de-empezar-quién-puede-usar-el-chat)
  2. [Abrir el chat y las sesiones](#2-abrir-el-chat-y-las-sesiones)
  3. [Preguntar](#3-preguntar)
  4. [Tablas, gráficos, exportar y copiar](#4-tablas-gráficos-exportar-y-copiar)
  5. [Adjuntos, facturas de proveedor y tickets](#5-adjuntos-facturas-de-proveedor-y-tickets)
  6. [Las 10 skills y los comandos](#6-las-10-skills-y-los-comandos)
  7. [Lienzo, páginas en pestaña y páginas compartidas](#7-lienzo-páginas-en-pestaña-y-páginas-compartidas)
  8. [Cambios en los datos: el plan y Confirmar](#8-cambios-en-los-datos-el-plan-y-confirmar)
  9. [Voz](#9-voz)
  10. [Límites](#10-límites)
  - [Fuentes de la Parte I](#fuentes-de-la-parte-i)
- [Parte II. Funcional y administración](#parte-ii-funcional-y-administración)
  11. [Grupos y menús](#11-grupos-y-menús)
  12. [Proveedores, roles, cadena, failover y tope](#12-proveedores-roles-cadena-failover-y-tope)
  13. [Agentes](#13-agentes)
  14. [Contextos y skills](#14-contextos-y-skills)
  15. [Claves MCP y servidor MCP](#15-claves-mcp-y-servidor-mcp)
  16. [Lista blanca, servidores externos y OpenAPI](#16-lista-blanca-servidores-externos-y-openapi)
  17. [Multicompañía](#17-multicompañía)
  18. [Registros, consumo y retención](#18-registros-consumo-y-retención)
  19. [Importar y exportar la configuración](#19-importar-y-exportar-la-configuración)
  20. [Ajustes de Chatboo](#20-ajustes-de-chatboo)
  21. [Qué cambia al actualizar](#21-qué-cambia-al-actualizar)
  22. [Problemas típicos](#22-problemas-típicos)
  - [Fuentes de la Parte II](#fuentes-de-la-parte-ii)
- [Anexo A. La web frente a los módulos](#anexo-a-la-web-frente-a-los-módulos)
- [Anexo B. Qué cambia para el usuario con Seges](#anexo-b-qué-cambia-para-el-usuario-en-la-versión-de-seges)
- [Etiquetas de pantalla](#etiquetas-de-pantalla)
- [Comprobación en ejecución](#comprobación-en-ejecución-prueba-automática-en-lab_pns_ai_3973)
- [Fuentes de los anexos](#fuentes-de-los-anexos)

---

## 0. Qué es cada módulo y cómo encajan

| Módulo | Nombre en Aplicaciones | Versión | Qué hace |
|---|---|---|---|
| `pns_base` | PNS Base | 1.2.69 | Piezas comunes que usan los otros dos: asistentes de exportación e importación, informes de operaciones y trabajos con barra de progreso. No tiene menú propio. |
| `pns_ai_mcp` | PNS AI Engine (menú **«Motor de IA»**) | 3.1.973 | El motor: proveedores de IA, agentes, contextos y skills, la caja de lectura (caja A), los planes de cambio y su confirmación (caja B), el servidor MCP, la lista blanca de URL y los registros de actividad. |
| `pns_ai_chatboo` | Chatboo — AI Chat Assistant (menú **«Chatboo»**) | 2.1.587 | El chat dentro de Odoo: la capa que se abre encima de la pantalla, las sesiones, las tablas y gráficos, las exportaciones, el lienzo y las páginas, y las 10 skills de fábrica. |

**Cómo encajan.** Chatboo no trae IA propia: cada mensaje lo resuelve el motor, que lo envía a los proveedores
configurados en el agente de Chatboo, en el orden de su lista. Instalar Chatboo instala los otros dos. El motor sirve
también sin Chatboo, a clientes MCP externos (Parte II).

**Las dos cajas.** Son la base de la seguridad y se nombran en todo el manual:
- **Caja A (lectura):** el código que la IA escribe para consultar datos se ejecuta con los permisos de quien pregunta,
  en una transacción de solo lectura que se deshace al acabar. Con los parches de Seges, además, no lee como
  superusuario, no ve las columnas secretas y no puede llamar a funciones con efectos fuera de la BD (correo,
  conexiones, descargas).
- **Caja B (cambios):** todo cambio en los datos es un **plan** que una persona confirma (§8). La IA no escribe sola.

**Versión de Seges.** Es la del fabricante con 24 correcciones (parches). En el uso normal casi no se notan; lo que sí
cambia para el usuario se resume en el Anexo B y se señala en su sitio con *(versión de Seges)*.

---

## Parte I. Usuario de Chatboo

### 1. Antes de empezar: quién puede usar el chat

Hacen falta **las dos cosas**, y las da el administrador de IA (Parte II):
- el grupo **«IA Conversacional»**;
- una **clave MCP** generada para el usuario (en *Motor de IA → Seguridad → Usuarios*, botón **«Generate API Key»**).

Sin las dos, no aparecen ni el icono del chat ni la aplicación Chatboo, y si se llega por un enlace el chat responde
«Chatboo access denied. An MCP API key is required.» (mensaje sin traducir).

Lo que se puede hacer depende además de otros grupos:

| Grupo | Qué añade en el chat |
|---|---|
| «IA Conversacional» | Preguntar, leer datos con los propios permisos, skills, exportar, lienzo, voz. |
| «IA Escritor» | Que la IA **proponga cambios** (planes) y confirmarlos; crear, renombrar, editar y borrar skills propias desde el chat. Sin él, el chat solo lee: si la IA intenta proponer un cambio, el turno se corta con un error de permiso. |
| «IA Administrador» | Todo lo anterior y la skill `/users`. Incluye los otros cuatro grupos de IA. |

**Lo que lee el chat es lo que el usuario puede ver en Odoo:** sus permisos, sus reglas de registro y sus compañías. Si
no puede abrir un registro a mano, el chat tampoco lo lee.

### 2. Abrir el chat y las sesiones

**Abrir.** Dos caminos:
- el **icono del elefante** de la barra superior (si el administrador no lo ha quitado con «Mostrar Chatboo en la barra
  del sistema»);
- la aplicación **«Chatboo»** del menú principal.

El chat se abre **encima de la pantalla en la que se está**, sin salir de ella, y se cierra con un clic. Las tarjetas
anchas (tablas y gráficos) se pueden ensanchar; **«Restaurar ancho por defecto»** las devuelve a su tamaño, y Odoo
recuerda el ancho de cada usuario.

**Trabaja aunque se cierre.** Si se cierra el chat a mitad de una respuesta, el turno sigue en el servidor. Cuando
termina, el elefante muestra una campanita y Odoo avisa con **«Nueva respuesta de Chatboo lista»**. Si lo que espera es
una confirmación, el aviso es **«Chatboo espera tu confirmación»**.

**Sesiones.** Cada conversación es una sesión con nombre:
- **«Nuevo chat»** abre una sesión nueva; **«Historial»** lista las anteriores para reabrirlas;
- **«Renombrar sesión»** y **«Eliminar sesión»**; desde el historial se pueden eliminar varias a la vez;
- **cada usuario ve solo sus sesiones.** Ni el administrador de IA ve las de otros desde el chat;
- al eliminar una sesión se borran sus mensajes y los archivos subidos a ella. *(Versión de Seges:)* solo se borran los
  adjuntos del dueño de la sesión; los que fueran de otro usuario se desenganchan, pero no se borran;
- **retención:** si el administrador fija «Retención de sesiones (días)», las sesiones que lleven ese tiempo sin usarse
  se borran solas. Con el valor 0, o sin valor, se conservan.

### 3. Preguntar

**Escribir.** En la caja **«Pregunta a Chatboo IA... (/ para comandos y skills, ↑↓ historial)»**, con **Intro** o
**«Enviar»**. Las flechas ↑↓ recorren las preguntas anteriores. **«Expandir prompt»** y **«Contraer prompt»** agrandan
la caja para textos largos.

**Contexto de pantalla.** El chat sabe qué hay debajo: el modelo, la vista y el registro o los registros abiertos. Se
puede preguntar «¿cuánto nos debe este cliente?» con la ficha del cliente abierta, sin decir cuál. El botón de la vista
tapada lo activa o lo desactiva (**«Vista tapada ON»** / **«Vista tapada OFF»**); viene activado.

**Elegir fila.** Si una respuesta trae una tabla de registros y la pregunta siguiente es sobre uno de ellos, se pincha
la fila (no el enlace, que abre el registro en Odoo). La fila queda marcada y el mensaje siguiente va sobre ese
registro. La marca se gasta con ese mensaje.

**Mientras piensa.** Se ve **«Pensando…»** o **«Conectando…»**. El botón **«Cancelar»** (icono de parar) detiene la
respuesta: lo que ya hubiera llegado se queda en el chat, con una marca ⏹. Si el proveedor no responde, el chat lo
corta solo y lo dice: **«Sin respuesta del proveedor (posible cuelgue). Inténtalo de nuevo.»**

**Pie de la respuesta.** Debajo de cada respuesta salen el modelo y el proveedor que la han dado, las fuentes y, si el
usuario lo despliega, los tokens y el coste del turno («Tokens facturados en este turno (todas las rondas)», «Coste»,
«Velocidad de generación (tokens/s)»). El indicador de la ventana del modelo («Ventana del modelo · última llamada vs
tope») avisa cuando una sesión larga se acerca al límite: conviene entonces abrir un **«Nuevo chat»**.

**El aviso de página.** *(Versión de Seges:)* si la respuesta iba a crear o cambiar una página del lienzo (§7) y no ha
podido, el servidor añade al final una línea fija: **«No se ha creado la página. El motivo está en el Historial IA.»**
No existe ningún menú con ese nombre: el motivo está en *Motor de IA → Seguridad → «My Activity»* (sin traducir), que
solo ven quienes tienen «IA Escritor» o uno de los grupos de URL o API externas. Un usuario con solo «IA
Conversacional» no puede verlo y tiene que pedírselo al administrador.

### 4. Tablas, gráficos, exportar y copiar

**Tablas.** Las celdas con nombre de registro son enlaces que abren ese registro en Odoo. Una tabla se puede pedir
como gráfico, y al revés; una lista sale como lista salvo que se pida un gráfico.

**Gráficos.** Se dibujan en el chat. El selector **«Tipo de gráfico»** cambia entre «Barras», «Barras agrupadas»,
«Apilado», «Horizontal», «Líneas», «Área», «Combinado», «Tarta», «Quesito», «Rosa» y «Radar». Con varias series,
«Usar dos ejes Y (útil si mezclas € y %)» o «Usar un solo eje Y». **«Estadísticas ON»** / **«Estadísticas OFF»**
añade debajo media, mediana, mínimo, máximo, suma y desviación típica de cada serie.

**Orden por defecto en la sesión.** Los comandos `/show-table` («Tabla primero (esta sesión)») y `/show-chart`
(«Gráfico primero (esta sesión)») fijan qué sale primero en esa sesión (§6).

**Exportar una respuesta.** En la burbuja:
- **«Descargar como PDF»**;
- **«Descargar como Excel»** (un `.xlsx` de verdad);
- **«Descargar como Word»**: descarga un archivo `.doc` que **por dentro es HTML**. Word lo abre (puede avisar del
  formato), pero no es un `.docx`. Para editarlo con comodidad, abrirlo en Word y guardarlo como `.docx`;
- si no hay nada que exportar, sale «Nada que exportar».

Cuando la IA prepara un archivo con nombre en la sesión (un PDF, un Excel o un Word que se ha pedido), sale como una
pastilla con **«Preparar y descargar»** o **«Descargar»**. Esas pastillas tienen el tope «Límite de descarga (MB)»
que fija el administrador; el icono de Excel de la burbuja no lo tiene.

**Copiar.** **«Copiar al portapapeles»**, **«Copiar contenido»** y **«Copiar como Markdown»** (para pegar en otro sitio
con el formato). Confirma con «Copiado al portapapeles».

### 5. Adjuntos, facturas de proveedor y tickets

**Adjuntar.** Con **«Adjuntar archivo»**, arrastrando el archivo al chat («Suelta los archivos aquí para adjuntarlos»)
o pegando con Ctrl+V. Se admiten:
- hojas de cálculo (`.xlsx`, `.xlsm`, `.xls`, `.csv`, `.tsv`);
- documentos (`.docx`, `.doc`, `.pdf`) y texto (`.txt`, `.md`, `.json`, `.log`);
- imágenes (`.png`, `.jpg`, `.gif`, `.webp`, `.bmp`, `.svg`, `.ico`).

Las imágenes van al modelo como imagen; el resto, como datos. **Quitar archivo** / **Quitar imagen** los retira antes
de enviar.

**Tamaño:** el chat rechaza cada archivo de más de **10 MB** («Archivo demasiado grande (máx. 10 MB)»), aunque el
administrador haya puesto un límite mayor. El servidor tiene su propio tope por archivo («Límite de subida (MB)», 15 MB
por defecto). Ver §10 para el texto de ayuda de ese ajuste, que no es exacto.

**Archivos adjuntos a un registro de Odoo.** En esta versión **no hay una función para leer los adjuntos de un
registro** (los del chatter, por ejemplo): para preguntar por uno, se descarga y se adjunta al chat. La web del
fabricante sí anuncia esa función, para una versión posterior de Chatboo (Anexo A).

**Facturas de proveedor desde un documento.** Se suelta en el chat la factura de un proveedor (PDF, hoja de cálculo,
o foto o escaneado en jpg, png o webp, también pegados con Ctrl+V) y se dice qué se quiere («regístrala», «¿esta ya
está contabilizada?», «crea el contacto»). Chatboo responde con un plan (§8):
1. **el proveedor:** lo busca por el NIF del documento y después por el nombre; si no existe, el primer paso del plan
   lo crea;
2. **la factura en borrador:** proveedor, fecha, número del proveedor como referencia, moneda si no es la de la
   compañía, una línea por base con los impuestos de compra que reproducen lo impreso y la cuenta de gasto habitual de
   ese proveedor. Si ningún impuesto de la compañía cuadra, la línea va sin impuesto y lo dice;
3. **duplicados:** si ya hay una factura de ese proveedor con ese número, o con el mismo total y fecha, la nombra y no
   propone nada.

Con varios documentos a la vez, sale un plan por documento. **Nada se contabiliza:** el borrador espera al contable.
Hace falta la aplicación de Facturación y permiso para crear facturas de proveedor, porque el plan se ejecuta como
el usuario, y además «IA Escritor».

**Tickets y recibos de datáfono.** Un ticket es una factura de proveedor (el comercio es el proveedor; el número del
ticket, la referencia). Si solo trae el total con el impuesto incluido, saca la base del tipo impreso; si no viene el
tipo, pregunta. Un recibo de datáfono **nunca se contabiliza**: Chatboo busca una factura de ese comercio con ese
importe en esas fechas y dice si está registrada y pagada.

**Coste.** Un PDF con texto cuesta un turno normal. Una foto o un escaneado los transcribe una vez el proveedor con el
rol Visión; sin ese rol, no se pueden leer (Parte II).

### 6. Las 10 skills y los comandos

**Qué es una skill.** Un procedimiento escrito en código que responde siempre igual a lo mismo. Se lanza escribiendo
`/` y eligiéndola, o preguntando con palabras parecidas a las suyas. Las cifras salen del código, no de la IA: una
skill sin argumentos, o con argumentos con nombre (`months=6`), **no llama a la IA**. Con argumentos dichos con
palabras («los dos últimos años») hace una llamada corta para entenderlos. Las skills **solo leen**, en la caja A, con
los permisos del usuario y en la compañía activa.

| Comando | Skill | Qué da |
|---|---|---|
| `/bill-draft` | Bill draft | Con una factura de proveedor adjunta, para un proveedor que ya existe: abre el formulario de factura con el proveedor y la fecha puestos y avisa de un posible duplicado. Las líneas las pone el usuario; nada se guarda hasta pulsar Guardar. |
| `/billing` | Billing by month | Facturas de cliente publicadas por mes, sin impuestos, en un gráfico. Los 12 últimos meses; `months=6` o `year=2025`. |
| `/customer-360` | Customer 360 | Una página con todo de un cliente (por nombre, NIF o correo): ficha, ingresos de 24 meses, facturas abiertas y vencidas, oportunidades, reuniones, actividades, últimos mensajes y una nota de salud de 0 a 100. |
| `/dashboard` | Business dashboard | Nueve tarjetas con gráficos: mes, trimestre y año, por equipo de ventas, mejores clientes y tendencia. |
| `/financial-health` | Financial health | Informe escrito de los 12 últimos meses (`months=24`): ventas y compras frente al año anterior, cobros y pagos pendientes, tesorería, días de cobro y concentración de clientes. **Llama a la IA** para escribir el análisis. |
| `/forecast` | Weather forecast | El tiempo por días de Open-Meteo (sitio de la lista blanca). Por defecto, la ciudad de la compañía y 7 días; `place=…` y `days=…`. Envía el nombre del sitio a Open-Meteo; no llama a la IA. |
| `/pipeline` | Sales pipeline | Una página sobre las oportunidades abiertas del CRM: embudo, previsión ponderada, por comercial, tasa de éxito y oportunidades paradas. |
| `/sales-board` | Sales board | Tarjetas que se arrastran, minimizan, maximizan o cierran, con las ventas de 12 meses. El navegador recuerda cómo se dejan. |
| `/top-sales` | Top sales | Pregunta qué ordenar (clientes, productos o comerciales) y cuántos meses, y dibuja los 10 primeros. `/top-sales 2 6` contesta las dos preguntas a la vez. |
| `/users` | Users | Todos los usuarios, archivados incluidos, con tipo, último acceso y si están conectados. **Solo para «IA Administrador».** |

Los nombres de las skills salen en inglés en el chat y en el menú (*Motor de IA → Conocimiento → «Habilidades»*, que
en el chat se llaman «skills»). Si la skill necesita un dato, lo pide; si el mensaje siguiente va de otra cosa, la
suelta.

**Comandos del chat** (salen en la paleta al escribir `/`):

| Comando | Qué hace | Grupo |
|---|---|---|
| `/skills` | Lista las skills disponibles para el usuario. | Todos |
| `/create-skill` | Guarda un turno como skill nueva del usuario. Empieza por el **id de turno** de 4 caracteres (el chip de cada respuesta: «Id de turno (log MCP). Clic para copiar») y el nombre. Abre un asistente. | «IA Escritor» |
| `/edit-skill`, `/rename-skill`, `/delete-skill` | Editar, renombrar o borrar una skill **que haya creado el usuario**. Sin argumentos, abren un selector. | «IA Escritor» |
| `/mode`, `/foot-laconic`, `/foot-verbose`, `/show-table`, `/show-chart`, `/compose-model`, `/compose-agent` | Modos de presentación: pie tras las tablas, tabla o gráfico primero, y quién compone la burbuja en ese turno. | Todos |

Cualquier comando con `?` (por ejemplo `/create-skill ?`) muestra su ayuda sin llamar a la IA.

**Skills nuevas.** Una skill creada con `/create-skill` queda activa al momento, sin revisión (riesgo aceptado, §10).

### 7. Lienzo, páginas en pestaña y páginas compartidas

**Lienzo.** Cuando una respuesta trae tablas, el botón **«Lienzo»** («Componer las tablas de esta respuesta como una
página») las compone como una página. Mientras se crea, sale «Creando la página. Pulsa para cancelar.» Al acabar, la
burbuja muestra **«Abrir página»**, que la abre en otra pestaña del navegador. La página tiene su propia descarga (un
HTML que se abre sin conexión).
- El botón **solo aparece si hay un proveedor con el rol Diseño**. En LIYBEN hoy no lo hay, y el botón no sale
  (Parte II, «Diseño sin rol»).
- *(Versión de Seges:)* la página no carga nada de fuera: ni imágenes de internet, ni librerías externas de gráficos.
  Solo lleva imágenes de registros **que el usuario puede ver**.

**Página en su propia pestaña.** Si se pide la respuesta «como una página» o «en una pestaña», la IA la prepara
directamente como página y el chat solo muestra la tarjeta para abrirla. El reconocimiento de esas frases depende del
idioma del usuario.

**Compartir.** Desde la página, **«Compartir»** la comparte con otros usuarios, que reciben el aviso «<nombre> ha
compartido una página contigo». La lista de páginas está en *Motor de IA → Seguridad → «Páginas compartidas»*, y
**«Dejar de compartir»** quita a los lectores. *(Versión de Seges:)*
- solo se comparte con **usuarios internos**; con un usuario de portal da el error «A page can only be shared with
  internal users.» (sin traducir);
- el dueño de una página no se puede cambiar;
- el administrador de IA puede abrir, descargar y borrar las páginas de otros, pero no cambiarlas ni dejar de
  compartirlas (en pantalla parecen editables; guardar da error).

El menú «Páginas compartidas» está bajo *Seguridad*, que no ve un usuario con solo «IA Conversacional»: ese usuario
llega a las páginas que le comparten por el aviso.

### 8. Cambios en los datos: el plan y Confirmar

**La IA no escribe sola.** Cuando la pregunta pide un cambio (crear un contacto, una factura en borrador, cambiar un
campo), la IA prepara un **plan** y el chat lo muestra en una tarjeta, **«Confirmar escritura de la IA»**, con los pasos
y el aviso «Esta operación no se ejecutará hasta que la confirmes.».

- **«Confirmar»** ejecuta el plan, **con los permisos del usuario que lo pidió**. **«Cancelar»** lo descarta («De
  acuerdo: he cancelado “…”. No se ha aplicado ningún cambio.»).
- Hace falta «IA Escritor» para que haya plan.
- *(Versión de Seges:)* la tarjeta del chat solo deja confirmar **al dueño del plan**.
- El plan **caduca a los 15 minutos** si nadie lo confirma (estado «Caducado»).
- Si el cambio afecta a varias pantallas (por ejemplo, una vista), sale antes **«Elegir vistas»**: se marcan las
  pantallas y después viene Confirmar.
- Estados que puede mostrar la tarjeta: «Confirmando…», «Confirmado — aplicando…», «Operación ejecutada», «Ya
  ejecutada», y, si no se ha podido aplicar al momento, «Confirmado — aplicación pendiente (Autorizaciones si hace
  falta)»: entonces el estado real se mira en Autorizaciones.

**Autorizaciones.** Todos los planes quedan registrados:
- *Motor de IA → Seguridad → «Mis Autorizaciones»*: los del usuario (para «IA Escritor» y los grupos de URL o API
  externas);
- *Motor de IA → Seguridad → «Autorizaciones»*: todos (para «IA Administrador»).

La ficha de cada plan muestra quién lo pidió, los pasos, el estado («Pendiente», «Confirmado», «Ejecutado»,
«Caducado») y los botones «Confirm» y «Cancel». *(Versión de Seges:)* **confirmar desde la ficha pide la contraseña
de Odoo**, que Odoo recuerda 10 minutos. Un usuario que entra sin contraseña propia de Odoo (con Google o LDAP, por
ejemplo) no puede confirmar desde la ficha.

**Antes de confirmar un plan, revisarlo en la ficha.** Quedan casos sin corregir en los que un plan puede dejar el
cambio a medias o marcarse como hecho sin estarlo (por ejemplo, quitar un grupo). Al «Confirmar» desde la ficha puede
salir un aviso de error aunque el cambio se haya hecho (riesgos aceptados, §10).

**Cambios con permisos especiales** *(versión de Seges)*:
- dar o quitar grupos a un usuario con un plan exige ser administrador de **Ajustes** a quien lo pide, a quien lo
  confirma y a quien lo ejecuta. Un «IA Administrador» sin Ajustes no puede hacerlo por el chat;
- borrar registros con un plan exige el permiso de borrado del modelo.

### 9. Voz

El botón **«Activar lectura en voz alta»** hace que el chat lea las respuestas. Una vez activado, «Clic en el chat para
reproducir». Usa la **voz del navegador**:
- por defecto, solo **voces instaladas en el propio ordenador**. Si no hay ninguna voz local del idioma del usuario,
  lee con otra voz local, que puede ser de otro idioma;
- si el administrador marca **«Permitir voces remotas»**, y no hay voz local del idioma, el navegador puede usar una
  voz de su fabricante (Google, Microsoft…), y entonces **el texto de la respuesta sale a ese servicio**.

La voz no se ha probado en Seges.

### 10. Límites

**Lo que hace y lo que no.**
- No es un chat general: responde sobre los datos de Odoo, con unos pocos tipos de gráfico y de página.
- Solo lee lo que el usuario puede leer, y solo cambia datos con un plan confirmado.
- Lo que se pregunta, y los datos que la IA lee para responder, **van al proveedor de IA** del agente (en LIYBEN, OVH, y
  Google Gemini en su nivel gratuito, en el que Google puede usar el contenido para mejorar sus productos). Es la
  función del producto (riesgo aceptado). Una skill que no llama a la IA no envía nada fuera.

**Tamaños.**
- Adjuntos: 10 MB por archivo en el chat. El servidor tiene además el tope «Límite de subida (MB)», 15 MB por defecto.
  La ayuda del ajuste dice «0 = sin límite», pero no es así: con 0, el servidor usa los 15 MB por defecto.
- Archivos preparados en la sesión: «Límite de descarga (MB)».
- Sesiones largas: el modelo tiene una ventana máxima (§3); al acercarse, abrir un «Nuevo chat».

**Riesgos aceptados que afectan al usuario** (estado del 21/11/2026):
- las skills creadas por usuarios quedan activas sin revisión. Su código corre en la caja A, de solo lectura, así que el
  efecto está acotado;
- un plan puede no ejecutarse o quedar a medias en casos concretos: revisarlo en la ficha antes de confirmar (§8);
- el usuario puede alterar el historial de sus propias sesiones; solo le afecta a él;
- algunas imágenes no salen en el lienzo (direcciones de imagen que no reconoce, o lienzos sin imágenes).

**Sin probar en Seges:** la voz, otros proveedores que no sean Gemini y OVH, y otras versiones de Odoo que no sean la
14.

---

### Fuentes de la Parte I

Código de la rama (`14.0-pns-ai-informe`, `11afeda`; módulos sin cambios desde `52a3a5e`) y documentación del repo.
Cada punto, por sección:

| § | Qué | Dónde |
|---|---|---|
| 0 | Versiones, nombres y dependencias | `pns_*/__manifest__.py` |
| 0 | Parches activos | `docs/pendiente/parches_pns_ai.md`; nota B, §4 |
| 1 | Acceso: grupo y clave | `pns_ai_chatboo/utils/chatboo_access.py:7-31`; `controllers/chatboo.py:37-47`; `models/ir_ui_menu.py` |
| 1 | Grupos y lo que implican | `pns_ai_mcp/security/security_groups.xml` |
| 1 | Plan sin «IA Escritor» | `pns_ai_mcp/controllers/relaxaicode_prepare.py:364-392`; `controllers/main.py:1272-1324` |
| 2 | Menú y acción de Chatboo | `pns_ai_chatboo/views/chatboo_menus.xml` |
| 2 | Icono en la barra | `pns_ai_chatboo/models/res_config_settings.py:23-26`; `controllers/chatboo.py:126-134` |
| 2 | Sesiones propias | `pns_ai_chatboo/security/security.xml:9-19` |
| 2 | Retención | `pns_ai_chatboo/models/chatboo_session.py:2108-2125`; `utils/chatboo_product_icp.py:124-141` |
| 2 | Borrado de adjuntos (parche 11) | `docs/pendiente/parches_pns_ai.md` |
| 2 | Ancho de las tarjetas | `static/src/js/chatboo_card_width.js:1-12`; `chatboo_component_v2.js:344` |
| 3 | Caja de texto, vista tapada, estadísticas, voz | `pns_ai_chatboo/static/src/js/chatboo_component_v2.js:298-306` y `:2558-2591` |
| 3 | Elegir fila | `static/src/js/chatboo_row_marks.js:1-25` |
| 3 | Cancelar | `chatboo_component_v2.js:3348-3362` y `:6155` |
| 3 | Aviso de página (parche 34, D25) | `pns_ai_chatboo/models/chatboo_async_request.py:1359-1371`; `pns_ai_chatboo/i18n/es.po:2213-2214` |
| 3 | Menú «My Activity» | `pns_ai_mcp/views/ai_log_views.xml:99` y `:116`; `pns_ai_mcp/i18n/es.po:4928-4929` y `:4955-4956` |
| 4 | Tipos de gráfico y estadísticas | `static/src/js/chatboo_charts.js` y `chatboo_export.js` (cadenas de `i18n/es.po`) |
| 4 | «Word» es HTML | `static/src/js/chatboo_export.js:3590-3601` (`application/msword`, cuerpo HTML) |
| 4 | Límite de descarga | `pns_ai_chatboo/models/ai_agent.py:49-55` |
| 5 | Tipos admitidos y 10 MB | `chatboo_component_v2.js:6218` y `:4053` |
| 5 | Tope del servidor y «0» | `pns_ai_chatboo/utils/chatboo_product_icp.py:37`, `:46-58` y `:190-193` |
| 5 | Adjuntos de un registro | Grep de `record_attachments` y de lecturas de `ir.attachment` en los módulos: ninguna función de lectura de adjuntos de un registro |
| 5 | Facturas y tickets | `pns_ai_chatboo/README.md:293-307`; `pns_ai_mcp/ai/contexts/domain/business_documents.xml` |
| 6 | Skills | `pns_ai_chatboo/ai/skills/system/*.md` (cabeceras; `required_groups` de `users.md`); `README.md:309-357` |
| 6 | Comandos | `chatboo_component_v2.js:369-545` |
| 7 | Lienzo y botón | `chatboo_component_v2.js:3794-3830`; nota B, §4 (PNS-110) |
| 7 | Página en pestaña | `pns_ai_chatboo/ai/contexts/domain/page_tab/page_tab.xml` |
| 7 | Botón «Compartir» de la página | `pns_ai_chatboo/models/chatboo_canvas.py:445-451` y `:613` |
| 7 | Compartir (parche 28) | `docs/pendiente/parches_pns_ai.md:2359-2407`; `pns_ai_chatboo/models/chatboo_canvas_page.py` |
| 7 | Contenido externo e imágenes (parches 25 a 29) | nota B, §4 |
| 8 | Tarjeta y estados | `chatboo_component_v2.js:2455-2471`; cadenas de `i18n/es.po` |
| 8 | Caducidad | `pns_ai_mcp/constants.py:7`; `models/safe_operation.py:281-285` |
| 8 | Ficha y botones | `pns_ai_mcp/views/safe_operation_views.xml` |
| 8 | Contraseña y tarjeta del dueño (parche 16) | `docs/pendiente/parches_pns_ai.md:1185-1226` |
| 8 | Grupos y borrado (parches 12 y 17) | nota B, §4 |
| 8 | Avisos de la ficha | inventario 3973 (PNS-26 y su anexo, PNS-99); nota B, §7 |
| 9 | Voz y voces remotas | `pns_ai_chatboo/models/ai_agent.py:56-63`; `static/src/js/chatboo_tts.js:60-110`; `utils/chatboo_product_icp.py:152-153` |
| 10 | Riesgos aceptados | nota B, §7; `docs/pendiente/informe_3973/estado_hallazgos_3973.md` |
| — | Menús y grupos de cada menú | los `menuitem` de las vistas de los tres módulos, con su `groups` |

**Se comprueba en ejecución** (procedimiento y resultado en «Comprobación en ejecución (prueba automática en
`lab_pns_ai_3973`)», al final): los menús que ve cada grupo, las etiquetas en español de las vistas y menús, los
nombres y comandos de las 10 skills registradas, el valor por defecto de «Permitir voces remotas» y el de la
retención.

---

## Parte II. Funcional y administración

Para quien configura los módulos: el administrador de IA y, en lo que exige Ajustes, el administrador de Odoo. Las
etiquetas son las del español de los módulos; los textos de ayuda de los campos, que salen al pasar el ratón, no se
citan salvo que digan algo que no es exacto.

### 11. Grupos y menús

**Los cinco grupos de IA** (sección «Inteligencia Artificial» de la ficha del usuario, o las casillas de «Permisos de
IA» en *Motor de IA → Seguridad → Usuarios*). Ninguno se asigna solo al crear un usuario.

| Grupo | Para qué | Implica |
|---|---|---|
| «IA Conversacional» | El chat (con la clave MCP, §1) y los clientes MCP externos. | Usuario interno |
| «IA Escritor» | Que la IA proponga cambios (planes) y confirmarlos; contextos y skills propios (al escribir skills usa el agente «Admin IA», §13). | Usuario interno |
| «IA URL externa» | Que un plan descargue páginas de internet (lista blanca, §16). | Usuario interno |
| «IA API externa» | Que un plan llame a servidores externos MCP u OpenAPI (§16). | Usuario interno |
| «IA Administrador» | Toda la configuración: proveedores, agentes, claves, servidores, lista blanca, registros. | Los otros cuatro |

- **«IA Administrador» no implica Ajustes**, y varias cosas exigen además Ajustes (administrador de Odoo): abrir los
  Ajustes del motor, crear un servidor `stdio` y, *(versión de Seges)*, dar o quitar grupos con un plan o cambiar las
  acciones de confianza (§8).
- **Desde 3.1.973, «IA Administrador» implica «IA Conversacional».** Al actualizar, todo administrador de IA gana el
  acceso al chat, y desmarcar su casilla de «IA Conversacional» no se lo quita (lo da la implicación).
- **Los planes se ejecutan con los permisos de Odoo de quien los pidió.** Un «IA Escritor» que pide crear un contacto
  necesita además el permiso de Odoo para crear contactos; sin él, el plan se confirma y falla con un error de acceso,
  sin escribir nada.
- **Quién debería tener cada grupo** (criterio de Seges desde la guía de 3.1.782, D4, D27 y N3): «IA Administrador»,
  solo quien ya es administrador de Odoo; «IA Escritor», solo técnicos de confianza, porque puede crear skills que
  quedan activas sin revisión (§14); «IA URL externa» e «IA API externa», solo a quien lo necesite.

**Menús de *Motor de IA*** y qué grupo los ve (un menú solo se ve si también se ve el de arriba):

| Menú | Lo ve |
|---|---|
| *Motor de IA* (raíz) | «IA Administrador», «IA Escritor», «IA URL externa», «IA API externa». **No** «IA Conversacional» solo |
| *Agentes* | «IA Administrador» |
| *Conexiones*: «Proveedores», «Roles de proveedor», «Lista Blanca», «Servidores externos» | «IA Administrador» |
| *Conocimiento*: «Contextos», «Habilidades», «Descubrimiento» | «IA Administrador» |
| *Conocimiento*: «Mis contextos», «Mis Habilidades» | «IA Escritor» |
| *Seguridad*: «Usuarios», «Autorizaciones», «Cambios aplicados», «Activity» (sin traducir) | «IA Administrador» |
| *Seguridad*: «Mis Autorizaciones», «My Activity» (sin traducir) | «IA Escritor», «IA URL externa», «IA API externa» |
| *Seguridad*: «Páginas compartidas» | Quien ve *Seguridad* (el menú no tiene grupo propio) |
| «Ajustes» | Ajustes (administrador de Odoo), y dentro solo ve el bloque del motor quien es además «IA Administrador» |
| *Chatboo* (aplicación) | Quien tiene «IA Conversacional» y clave MCP (§1) |

Un usuario con solo «IA Conversacional» no tiene ningún menú del motor: ni sus planes, ni su actividad, ni las páginas
compartidas (las abre desde el aviso).

### 12. Proveedores, roles, cadena, failover y tope

**Proveedor** (*Motor de IA → Conexiones → Proveedores*). Cada proveedor es una clave de API con un modelo:
- **«Protocol»** (sin traducir): «OpenAI / OpenAI-Compatible» (también Azure y pasarelas locales como LM Studio u
  Ollama), «OpenRouter», «Anthropic (Claude)» y «SystemOne (Choice)», que no conversa y solo sirve para el rol Decisión;
- **«URL del endpoint»**: la dirección exacta a la que se envía, tal como la da el proveedor. Si no acaba como espera el
  protocolo, guardar da un error;
- **«Clave API»**: solo la ve el administrador de IA. **Duplicar un proveedor no copia la clave.**
- **«Modelo seleccionado»**: se elige del catálogo del proveedor. **«Probar conexión»** exige un modelo elegido y hace
  una llamada real (coste mínimo).
- Hay ejemplos de proveedores sin clave para cargar con «Importar configuración» (§19): Anthropic, Lemonade, OpenAI,
  OpenRouter y OVH.

**Roles** (*Motor de IA → Conexiones → Roles de proveedor*). Dicen para qué sirve cada proveedor. Sustituyen a las
casillas de 3.1.879 (`fit_*`):

| Rol | Qué hace en estos módulos | Si nadie lo tiene |
|---|---|---|
| «Conversación» | El turno normal del chat. Un proveedor **sin ningún rol** hace lo mismo. | — |
| «Visión» | Leer fotos y páginas escaneadas (facturas, tickets, §5). | No se leen |
| «Decisión» | Responder una elección cerrada (sí o ninguna) al elegir el conocimiento del turno. Solo con el protocolo SystemOne. | Se toma como «no» |
| «Diseño» | Componer la página del lienzo (§7). | Lo hace Conversación (ver «Diseño sin rol») |
| «Parser» | Entender los argumentos de una skill dichos con palabras («los dos últimos años»). | Lo hace Conversación |
| «Audio» | Ningún turno de estos módulos lo pide; al guardar un proveedor con este rol se prueba que el modelo entiende voz. | — |
| «Vídeo» | Ningún turno de estos módulos lo pide. | — |

El administrador puede archivar un rol, desactivar **«Usar el respaldo»** o cambiar sus colores; el nombre, la ayuda,
el orden y el respaldo los pone el módulo y una actualización los vuelve a escribir. Cuando se busca un rol que no es
Conversación, un proveedor que solo tiene ese rol pasa por delante de los que tienen varios.

**Cadena del agente.** En la ficha del agente (§13), pestaña de proveedores, se ponen los proveedores en orden (se
arrastran las filas). Por cada fila:
- «Tiempo de inactividad (s)»: segundos sin recibir nada del modelo antes de pasar al siguiente (45 por defecto);
- «Tiempo de espera por ronda (s)»: tope de una llamada (120 por defecto);
- «Omitir alternativa sin streaming»: para proveedores locales lentos.

Reglas que conviene tener presentes:
- **Sin cadena, el agente usa todos los proveedores activos**, por orden de creación. Por eso hay que definir la cadena
  y **archivar los proveedores que no se usen**.
- **El turno normal solo usa la cadena.** Los demás roles se buscan primero en la cadena y, si nadie de ella los tiene,
  **entre todos los proveedores activos**, estén o no en la cadena.
- **Failover:** si un proveedor falla o no responde a tiempo, se pasa al siguiente de la cadena, y el registro de
  actividad lo anota. Si todos fallan, el turno termina en error.
- **«Sin failover externo»:** marcado en un proveedor, los que vienen detrás en la cadena no se prueban. Es la forma de
  que, si un proveedor local falla, el turno no pase a uno externo. **No es una garantía completa:** los roles se buscan
  fuera de la cadena (punto anterior) y quedan caminos en los que no corta (PNS-18, riesgo aceptado). Si los datos no
  deben salir, no debe haber proveedores externos activos.
- **El respaldo recibe los mismos datos:** la cadena debería ser toda local o toda de proveedores con contrato (D10).

**Tope mensual.** En el proveedor, «Tope mensual (USD)» y «Tope mensual (tokens)» (0 = sin tope). El tope en dinero
solo funciona si el proveedor informa del coste; si no, se usa el de tokens. Al alcanzarlo, ese proveedor deja de
usarse ese mes y se pasa al siguiente; si no queda ninguno, el chat dice «No hay proveedor con cuota disponible este
mes.» El botón **«Este mes»** de la ficha muestra el consumo del mes y lo que queda.

**Diseño sin rol.** El rol Diseño tiene como respaldo Conversación y viene con «Usar el respaldo» activado: si ningún
proveedor activo tiene Diseño, **diseña la cadena de Conversación** y el botón «Lienzo» aparece igual. Archivar el rol
Diseño no lo evita (el respaldo se sigue usando). Para que solo diseñe un proveedor concreto, darle el rol Diseño y
desactivar «Usar el respaldo»; entonces, si ese proveedor está archivado o sin cuota, nadie diseña y el botón no sale,
y si falla en la llamada no pasa a otro. **En LIYBEN** (20/11/2026): Diseño solo en el proveedor 1, hoy inactivo, y sin
respaldo, así que el botón «Lienzo» no aparece (D62). Comunicado al fabricante como PNS-110.

### 13. Agentes

*Motor de IA → Agentes.* Un agente es quien usa los proveedores, con su cadena, sus contextos y sus skills. Los crean
los módulos y no se pueden borrar:

| Agente | Código | Tipo | Para qué |
|---|---|---|---|
| Chatboo | `pns_ai_chatboo` | Inferencia | El chat. Su cadena es la que importa en el uso diario. |
| MCP Server | `pns_ai_mcp` | Endpoint | Sirve contextos y herramientas a clientes MCP externos (§15); la IA corre en el cliente, así que no usa proveedores. |
| «Admin IA» | `pns_ai_admin` | Inferencia | Trabajos internos del motor: generar un OpenAPI desde la documentación, detección de servidores y ayuda al escribir skills. Si se usan, hay que darle su cadena, como a cualquier agente de inferencia. |

`pns_ai_admin` es el código de este agente, no un módulo aparte. El tipo sale sin traducir («Inference (internal
LLM)», «Endpoint (external LLM)»).

**«Admin IA» no exige el grupo «IA Administrador».** Cualquier usuario interno puede leer el agente y solo un «IA
Administrador» puede cambiarlo, pero también lo usa un «IA Escritor»: al escribir sus skills desde «Mis Habilidades» y
con el asistente «Crear o editar skill», la ayuda la redacta este agente con su cadena de proveedores.

En la ficha del agente: los proveedores (§12), «Rondas LLM máx.» (10 por defecto: cuántas veces puede llamar al modelo
en un turno), y los contextos y skills enlazados (§14). La ficha se abre también desde los Ajustes del motor, con el
botón «Configuración» de cada agente. **Cuidado al quitar una fila de proveedores:** se guarda con el agente; si la
cadena queda vacía, el agente pasa a usar todos los proveedores activos (§12).

### 14. Contextos y skills

**Contextos** (*Motor de IA → Conocimiento → Contextos*). Son el conocimiento que se le da al modelo en cada turno, con
cuatro tipos (sin traducir):
- `core`: las instrucciones de base del motor (`system_prompt`). Siempre van;
- `domain`: paquetes de conocimiento de un tema (contabilidad, facturas de proveedor, contactos, nóminas…) y cuatro
  de Chatboo;
- `discovery`: las palabras que deciden qué paquete de dominio entra en un turno, por idioma (con versión en español
  de cada tema del motor);
- `locale`: términos por idioma.

**Los de Chatboo** son 6. Cuatro de dominio: `page_tab` (responder con una página en su propia pestaña),
`presentation_grids` (cómo se presentan las tablas), `self_chatboo` (la identidad del chat; es el de reserva) y
`ui_focus` (la pantalla de Odoo que queda debajo del chat). Y dos de descubrimiento: `discovery_page_tab` y su variante
en español, `discovery_page_tab_es_ES`. Los contextos no tienen nombre traducido: en las listas salen por su código
técnico, y el tipo, sin traducir.

Con «Packs de dominio por turno» activado en los Ajustes del motor (lo está por defecto), un paquete de dominio solo
entra en los turnos que lo necesitan; así el contexto de base es más pequeño. *Motor de IA → Conocimiento →
Descubrimiento* muestra ese índice.

**Contextos y skills de fábrica.** Los que vienen con los módulos no tienen dueño y **cada actualización los vuelve a
escribir**: un cambio hecho a mano en ellos se pierde. Para adaptar uno, crear un contexto o una skill propios.
«Restaurar desde el módulo» los vuelve a cargar desde los archivos (solo «IA Administrador»).

**Skills** (*Conocimiento → «Habilidades»*). Las 10 de Chatboo están en la §6. Cada skill tiene su comando (`/…`),
«Disparadores» (las palabras con las que se lanza sin comando), «Mostrar en menú slash» y «Habilidad de sistema»
(las de fábrica). Algunas exigen un grupo (`/users`, «IA Administrador»).

**Propios de un «IA Escritor»** («Mis contextos» y «Mis Habilidades»): ve los de fábrica y los suyos, y solo crea,
cambia o borra los suyos; no puede tocar los de tipo `core` ni las skills de sistema. El «IA Administrador» ve y cambia
todos.
- **Una skill nueva queda activa al momento, sin revisión**, también si se importa (PNS-23, riesgo aceptado). Su código
  corre en la caja A, de solo lectura y con los permisos de quien la usa, así que el efecto está acotado.
- Los Ajustes del motor fijan «Prefijo del código de skill» y «Prefijo del comando slash» para las skills que se creen
  en esta base de datos.

### 15. Claves MCP y servidor MCP

**Usuarios MCP** (*Motor de IA → Seguridad → Usuarios*, solo «IA Administrador»). La lista sale con todos los usuarios
internos, con sus grupos de IA y el estado de la clave («Generada», «No generada»). En la ficha:
- **«Generar Clave API»** / **«Regenerar Clave API»**: la clave se ve **solo en ese momento**; Odoo guarda un resumen
  del que no se puede recuperar. Si se pierde, se genera otra. Entregarla por un canal propio, fuera de Odoo;
- **«Eliminar API Key»**: la borra y el estado vuelve a «No generada»;
- en el menú Acción, «Import existing API key» (sin traducir) fija una clave conocida (de otra instancia o de un
  cliente). *(3.1.973:)* un «IA Administrador» sin Ajustes no puede generar, fijar ni importar la clave de un
  administrador de Ajustes;
- «Último cliente MCP»: qué cliente usó la clave por última vez y desde dónde.

La clave hace dos cosas: abre el chat (con «IA Conversacional», §1) y autentica a los clientes MCP externos.

**«Pin temporal de clave».** Es una forma de entregar la clave con un PIN de un solo uso, desde «Listado de claves».
Sus ajustes («Cifras del pin», «Intentos de pin por IP», «Bloqueo de pin (horas)», «Soltar bloqueos de pin») están en
los Ajustes del motor. **En Seges no se usa:** el administrador de IA puede leer el PIN y la clave en tránsito (PNS-84,
riesgo aceptado mientras no se use).

**Servidor MCP** (para clientes externos como Claude Desktop o Cursor). Está en `/mcp` (agente MCP Server, §13), y
también en `/mcp/<código de agente>`.
- La clave va **en una cabecera**: `X-MCP-API-Key`, `X-Mcp-Token` o `Authorization: Bearer <clave>`. Nunca en la URL.
- Publica tres herramientas: `relaxaicode` (leer, en la caja A), `safe_plan_request` (pedir un plan) y
  `safe_plan_status` (ver cómo va). Los cambios piden confirmación en Odoo, como en el chat (§8).
- «Orígenes web de MCP» (Ajustes del motor): otras direcciones web que pueden llamar a `/mcp` desde un navegador. Los
  clientes de escritorio no lo necesitan.
- **En LIYBEN el servidor MCP no está expuesto:** el proxy da 404 en `/mcp` (D20) y no hay ninguna clave MCP
  (20/11/2026). Si se expone, tener en cuenta PNS-28 (CORS y cabecera `Origin`, abierto).

### 16. Lista blanca, servidores externos y OpenAPI

**«Política de acceso a URLs»** (Ajustes del motor, bloque «Plan seguro»): **«Solo lista blanca»** (por defecto)
u «Abierto (auto-añadir URLs)». El título del bloque sale en inglés, «URL access policy» (sin traducir). Con la
primera, un plan solo descarga de los dominios de la lista; fuera de ella, un «IA Administrador» puede confirmar que
se añada el dominio. Con «Abierto» se descarga cualquier dirección y el dominio se añade solo: **no usarla.** En los
dos casos se rechazan las direcciones internas y se comprueba cada redirección.

**Lista blanca** (*Conexiones → «Lista Blanca»*). Cada fila tiene «Dominio» (vale también para sus subdominios),
«Tipo» («Web (fetch_url)», «Servidor MCP» o «Servidor OpenAPI»), «Válido desde», «Válido hasta», «Notas» y «Añadido
por». Las de servidores MCP u OpenAPI se añaden solas al activar el servidor. **Solo «IA Administrador» puede cambiar
la lista**; el resto de usuarios internos solo la lee. De fábrica trae los dos dominios de Open-Meteo que usa la skill
`/forecast`; si no se usa, se pueden borrar.

**Servidores externos** (*Conexiones → «Servidores externos»*): servidores MCP o APIs OpenAPI a los que un plan puede
llamar (con «IA API externa»).
- «Tipo de API»: MCP u «OpenAPI / Swagger» (sin traducir); «Transporte» (sin traducir): «SSE (HTTP remote)» o «stdio
  (local process)».
- **`stdio` ejecuta un programa en el servidor de Odoo:** solo un administrador de Ajustes puede crearlo o cambiarlo
  («Solo un administrador de Ajustes puede configurar un servidor stdio: su comando se ejecuta en el servidor de
  Odoo.»). No usarlo.
- **«De confianza (auto-confirmar)»:** las llamadas a ese servidor se ejecutan sin confirmación. Dejarlo siempre
  desmarcado (D25).
- OpenAPI: se da la «URL del spec» o se genera desde la documentación con el agente «Admin IA» (§13).
- *(Versión de Seges:)* al seguir una redirección a otro servidor solo viajan las cabeceras neutras, y las llamadas a
  servidores MCP no siguen redirecciones: un servidor que redirige da un error y hay que poner su dirección final.


### 17. Multicompañía

Desde 3.1.973 la IA trabaja **en las compañías marcadas en el selector de compañías**, con la activa primero:
- **lo que lee el chat** está limitado a esas compañías, con las reglas multicompañía de Odoo. Sin
  pantalla (un cliente MCP externo), la compañía por defecto del usuario. Una compañía que no es del usuario se ignora;
- **un plan se ejecuta en las compañías en que se pidió**, aunque se confirme después con otra compañía en el selector;
- **la copia oculta de la última tabla** (§20) solo se reutiliza si el turno es en las mismas compañías; si no, se
  vuelve a consultar;
- *(versión de Seges)* las imágenes del lienzo y de las páginas solo salen si el usuario puede ver el registro en esas
  compañías.

**La configuración no tiene compañía:** proveedores, roles, agentes, contextos, skills, lista blanca, servidores y
ajustes son comunes a toda la base de datos. El consumo y los topes son por proveedor, no por compañía.

### 18. Registros, consumo y retención

**Registro de actividad** («My Activity» y «Activity», sin traducir, bajo *Seguridad*). Cada turno, consulta,
herramienta y failover deja una línea: usuario, proveedor, modelo, tokens, coste y resultado. Cada usuario ve solo las
suyas; el «IA Administrador» ve todas y puede borrarlas. El usuario con solo «IA Conversacional» no tiene este menú.

**Consumo.** Coste y tokens salen en el pie de cada respuesta (§3), en el registro de actividad y, por proveedor, en el
botón «Este mes» (§12). «Moneda de visualización» (Ajustes del motor) cambia la moneda en que se muestran; los
proveedores informan en dólares y se convierte con el cambio de las fuentes de «Gestionar fuentes de cotización».
*(Versión de Seges:)* el consumo de un proveedor no se puede leer por la API, solo en pantalla.

**Cambios aplicados** (*Seguridad → «Cambios aplicados»*, «IA Administrador»). Diario de todo lo que han escrito los
planes, con el antes y el después. Desde ahí, un «IA Administrador» o un administrador de Ajustes puede **«Revertir»**
un cambio. Lo que un plan borra no se borra en el momento: queda «En la papelera» los días de «Papelera de cambios
(días)» (30 por defecto; 0 = hasta vaciarla a mano con «Vaciar papelera» o «Borrar del todo»).

**Retención:**

| Qué | Dónde se fija | Por defecto | Con 0 o vacío |
|---|---|---|---|
| Registro de actividad | Ajustes del motor, «Retención del registro de actividad (días)» | Vacío | Se conserva todo |
| Sesiones del chat (mensajes, tablas y archivos subidos), por días sin uso | Ajustes de Chatboo, «Retención de sesiones (días)» | 0 | Se conservan |
| Papelera de cambios | Ajustes del motor, «Papelera de cambios (días)» | 30 | Hasta vaciarla |
| Archivos de exportación de `pns_base` | Solo en Parámetros del sistema: `pns_base.export_retention_hours` | 24 horas | No se borran |
| Copia oculta de la última tabla | Ajustes de Chatboo, «Horas que dura esa copia» | 12 horas | Lo que dure la sesión |

**Ojo al actualizar desde 3.1.782:** allí la retención del registro y la de sesiones venían en 30 días (en LIYBEN, la
de sesiones borró el 19/11 una sesión de octubre). Tras actualizar, mirar qué valor queda en los Ajustes y decidirlo.

Todo esto lo hacen siete tareas programadas de los `pns_*` (purga de cachés, del registro, de la papelera y de las
exportaciones, caducidad de planes y mantenimiento de la cola del chat). *(Versión de Seges:)* tras actualizar desde
3.1.879, un script corrige las dos purgas de cachés, que quedaban llamando a un método que ya no existe (PNS-109).

### 19. Importar y exportar la configuración

En los Ajustes del motor:
- **«Copia de seguridad de la configuración»**: «Exportar configuración» e «Importar configuración». Es un JSON con
  proveedores, roles (solo su estado), agentes (solo su configuración), contextos y skills que no son de fábrica,
  servidores, lista blanca, usuarios MCP (sus permisos de IA) y algunos ajustes del motor (política de acceso a URLs,
  packs por turno y prefijos de skills).
- «Partial artifact bundle» (sin traducir) exporta e importa solo una parte («Export selection», «Import bundle»). Hay,
  además, botones de exportar e importar en las listas de cada modelo (por ejemplo, «Exportar seleccionados»).

**Exportar** pregunta antes si se incluyen los secretos («Incluir secretos»): claves de proveedores, credenciales de
servidores y el resumen de las claves MCP (con el resumen, la misma clave sirve en la otra base de datos). **Sin
secretos es lo normal**; con secretos, el archivo es una credencial y se borra a las 24 horas (§18). Los ejemplos de
proveedores (§12) salen sin clave.

**Importar** («Importar configuración de IA»): se sube el «Archivo de copia (.json)» y se elige «Pisar los registros
que ya existen» (desmarcado: solo se crean los que faltan). **«Revisar»** enseña lo que haría sin escribir nada
*(versión de Seges: antes, la revisión dejaba cosas escritas)*. Los agentes solo se actualizan, nunca se crean.
- *(Versión de Seges:)* un «IA Administrador» sin Ajustes puede revisar y aplicar una importación (antes daba un error
  de permisos).
- **No importar copias de origen desconocido:** pueden cambiar proveedores, direcciones o la política de acceso a
  URLs, y las skills importadas quedan activas (§14).

### 20. Ajustes de Chatboo

En *Motor de IA → Ajustes*, bloque «Chatboo» (varios de ellos también están en la ficha del agente Chatboo):

| Ajuste | Por defecto | Qué hace |
|---|---|---|
| «Mostrar Chatboo en la barra del sistema» | Marcado | El icono del elefante (§2). |
| «Permitir voces remotas» | Desmarcado | Si no hay voz local, deja al navegador usar la de su fabricante, y el texto sale a ese servicio (§9). |
| «Copia oculta de la lista (MB)» | 8 | La última tabla se guarda aparte para reordenarla sin volver a consultar, fuera de lo que se envía al modelo. 0 = sin tope. Seges recomienda no ponerlo a 0 (D30). |
| «Horas que dura esa copia» | 12 | §18. |
| «Retención de sesiones (días)» | 0 | §18. |
| «Límite de descarga (MB)» | 15 | Tope de los archivos que prepara la sesión (§4). 0 = sin límite. |
| «Límite de subida (MB)» | 15 | Tope del servidor por archivo subido. **La ayuda dice «0 = sin límite» y no es así:** con 0 se usan 15 MB (y al volver a abrir los Ajustes sale 15). Además, el chat no deja subir más de 10 MB por archivo, así que un valor mayor no tiene efecto (§5). |
| «Motor de gráficos» | ECharts | La librería de los gráficos del chat (ECharts o Chart.js). |
| «Showmode por defecto» | Tabla primero | Si cada conversación empieza con la tabla o con el gráfico (§4). |
| «Decimales» | 2 | Decimales en la tabla, el PDF, el Word y el Excel. Si coincide con los de la moneda de la compañía, sigue a la moneda. |
| «Separador de millares en Excel» | Marcado | En cada celda numérica del Excel. |

Los Ajustes del motor que no salen en otras secciones: los agentes internos y externos con su botón «Configuración»
(§13), «Packs de dominio por turno» (§14) y el bloque «Licencia del módulo».

### 21. Qué cambia al actualizar

**Antes de cada versión nueva del fabricante** (regla vigente desde el 19/10/2026): no se instala sola. Se compara con
la instalada, se decide si se pasa a ella y se adaptan y prueban los parches de Seges (nota B, §8). El procedimiento
de LIYBEN (`docs/pendiente/liyben_3973.md`) es el modelo: ensayo sobre una copia, copia completa de la base de datos y
del filestore antes, y comprobaciones antes y después.

**Lo que hace la actualización a 3.1.973 sin avisar:**
- vuelve a escribir los contextos y skills de fábrica sin dueño (en LIYBEN, 13 contextos y 3 skills), borra las skills
  de fábrica retiradas y crea las nuevas. Lo editado a mano en ellos se pierde (§14);
- pasa las casillas `fit_*` de los proveedores a roles. Un proveedor que no sea SystemOne y tuviera la casilla de
  Decisión queda con ese rol, y al guardarlo da «El protocolo %s no responde un Choice cerrado. Quita el rol
  Decisión.» (PNS-114): hay que quitarle el rol;
- da «IA Conversacional» a todos los «IA Administrador» (§11);
- deja el rol Diseño con respaldo: decidir quién diseña (§12, «Diseño sin rol»);
- si se recarga el español sobrescribiendo, cambia también traducciones de otros módulos (PNS-113). En LIYBEN se
  recargó y, en la misma operación, se restauraron las de fuera de los `pns_*` (D66);
- conserva los valores de retención que ya hubiera (§18).

**Comprobar después:** la cadena de cada agente, los roles (sobre todo Diseño y Decisión), los grupos de IA de los
administradores, la retención, la política de acceso a URLs y que no haya proveedores ni servidores activos que no
se usen.

### 22. Problemas típicos

| Síntoma | Causa | Qué hacer |
|---|---|---|
| «Chatboo access denied. An MCP API key is required.» | Falta la clave MCP o el grupo | §1 y §15. |
| El chat usa un proveedor que nadie configuró para él | El agente no tiene cadena (también si se quitó la última fila) y usa todos los activos | Definir la cadena y archivar los que no se usen (§12). |
| «No hay proveedores configurados.» | Ningún proveedor activo | Crear o activar uno con su clave. |
| «No hay proveedor con cuota disponible este mes.» | Todos los proveedores de la cadena han llegado a su tope mensual | Subir el tope o añadir otro proveedor (§12). |
| El botón «Lienzo» no sale | Nadie activo tiene Diseño y su respaldo está desactivado (en LIYBEN, a propósito) | §12, «Diseño sin rol». |
| El botón «Lienzo» sale y la página la hace un modelo que no se quería | Nadie tiene Diseño y el respaldo está activo | Igual. |
| Las fotos o los escaneados no se leen | Ningún proveedor tiene «Visión» | Dar el rol a un modelo que lea imágenes. |
| Guardar un proveedor da «El protocolo %s no responde un Choice cerrado. Quita el rol Decisión.» | Rol Decisión en un protocolo que no es SystemOne (suele venir de la actualización) | Quitar el rol (§21). |
| Guardar un proveedor da «El modelo %s no responde ni audio en chat ni transcripción de archivo…» | Rol Audio en un modelo sin voz | Quitar el rol Audio. |
| «Probar conexión» falla sin llegar al proveedor | No hay modelo elegido | Elegir el modelo del catálogo. |
| Gemini responde 503, 404 o 429 | Modelo saturado, modelo retirado para usuarios nuevos o cuota diaria del nivel gratuito agotada (staging del 16/10/2026) | Cambiar de modelo o poner un segundo proveedor en la cadena. |
| Un plan confirmado falla con un error de acceso | Quien lo pidió no tiene el permiso de Odoo del modelo | Darle el grupo de Odoo que haga falta (§11). |
| Un «IA Administrador» no puede dar o quitar grupos con el chat | *(Versión de Seges)* exige Ajustes (§8) | Lo hace un administrador de Ajustes. |
| No se ven los Ajustes del motor | Hace falta Ajustes y, para ver el bloque, «IA Administrador» | §11. |
| `/mcp` da 404 | El proxy no lo expone (LIYBEN, a propósito) o hay varias bases de datos sin `dbfilter` | §15. |
| Un servidor MCP externo da error al conectar | *(Versión de Seges)* no se siguen redirecciones | Poner su dirección final (§16). |
| Han desaparecido sesiones antiguas del chat | La retención de sesiones está fijada (en LIYBEN, con 3.1.782, a los 30 días) | §18. |
| Tras actualizar se perdió un cambio en un contexto o una skill de fábrica | La actualización los vuelve a escribir | Rehacerlo como contexto o skill propios (§14). |
| Tras actualizar cambiaron traducciones de otros módulos | Recarga del idioma sobrescribiendo (PNS-113) | §21. |
| Se perdió una clave MCP | Solo se ve al generarla | Regenerarla (§15). |

---

### Fuentes de la Parte II

Código de la rama (`14.0-pns-ai-informe`, `4224bf9`; módulos sin cambios desde `52a3a5e`) y documentación del repo.

| § | Qué | Dónde |
|---|---|---|
| 11 | Grupos, implicaciones y nombres en español | `pns_ai_mcp/security/security_groups.xml:16-50`; `pns_ai_mcp/i18n/es.po:2865`, `:2872`, `:4861`, `:4867` y `:4873` |
| 11 | Menús y sus grupos | `menus.py` (los `menuitem` de los tres módulos); `pns_ai_mcp/views/mcp_user_views.xml:145-170`; `views/res_config_settings_views.xml:10-11` y `:360-365` |
| 11 | Plan con los permisos de quien lo pidió; AI Administrator implica AI Conversational | `docs/specs/comparacion_pns_ai_3-1-973.md`, §6.2 y §6.3 |
| 11 | Criterio de asignación (D4, D27, N3) | `docs/specs/guia_configuracion_pns_ai.md:362-390` |
| 12 | Campos del proveedor | `pns_ai_mcp/models/ai_provider.py:170-200`, `:408-429`; `:626-651` (protocolo y rol, dirección) |
| 12 | Clave no copiada; prueba de conexión | `pns_ai_mcp/models/ai_provider.py:195-200` y `:1200-1202` |
| 12 | Ejemplos de proveedores | `pns_ai_mcp/static/examples/providers/*.json` |
| 12 | Roles y respaldo | `pns_ai_mcp/data/ai_provider_role_data.xml`; `models/ai_provider_role.py:61-91`; `utils/provider_fit.py:17-37` |
| 12 | Quién pide cada rol | `pns_ai_mcp/utils/agent_engine.py:235`; `utils/engine_skills.py:69`; `models/ai_execution_engine.py:357`; `pns_ai_chatboo/models/chatboo_session.py:1330-1337`; `pns_ai_mcp/models/ai_provider.py:708-730` (Audio al guardar) |
| 12 | Cadena, sin cadena, roles fuera de la cadena, sin failover externo, tope | `pns_ai_mcp/models/ai_execution_engine.py:203-344` |
| 12 | Campos de cada fila de la cadena | `pns_ai_mcp/models/ai_agent.py:1580-1630` |
| 12 | Tope y consumo del mes (parche 33) | `pns_ai_mcp/models/ai_provider.py:1129-1146`; `wizard/ai_provider_usage_wizard.py:14-23` |
| 12 | Diseño sin rol (PNS-110) y LIYBEN (D62) | `docs/specs/comparacion_pns_ai_3-1-973.md`, §6.6; `docs/pendiente/liyben_3973.md`, D62 y H |
| 12 | PNS-18 aceptado | nota B, §7; inventario 3973, PNS-18 |
| 13 | Agentes de fábrica | `pns_ai_mcp/data/ai_agent_data.xml:8-37`; `models/ai_agent.py:283-293` (cadena de «Admin IA»); `pns_ai_chatboo/data/ai_agent_data.xml:7-13`; `pns_ai_mcp/models/ai_agent.py:60-110` |
| 13 | «Admin IA» sin grupo propio y quién lo usa | `pns_ai_mcp/data/ai_agent_data.xml:26-36`; `pns_ai_mcp/security/ir.model.access.csv:14` y `:62`; `pns_ai_mcp/models/ai_skill_authoring.py:139-147`; `pns_ai_mcp/wizard/skill_capture_wizard.py:347`; `pns_ai_mcp/security/ir.model.access.csv:30`; `pns_ai_mcp/i18n/es.po:4751-4752` y `:8698-8699` |
| 13 | Cadena vacía tras quitar la fila | `docs/pendiente/liyben_3973.md`, H («Cadena de Chatboo») |
| 14 | Tipos de contexto | `pns_ai_mcp/utils/context_roles.py:31-43`; `pns_ai_mcp/ai/contexts/` |
| 14 | Contextos de Chatboo y su nombre en pantalla | `pns_ai_chatboo/data/chatboo_context_data.xml:5`; `pns_ai_chatboo/ai/contexts/domain/page_tab/page_tab.xml:4`; `pns_ai_chatboo/ai/contexts/domain/presentation_grids/presentation_grids.xml:4`; `pns_ai_chatboo/ai/contexts/domain/self_chatboo/self_chatboo.xml:4` y `:9`; `pns_ai_chatboo/ai/contexts/domain/ui_focus/ui_focus.xml:4`; `pns_ai_chatboo/ai/contexts/discovery/`; `pns_ai_mcp/models/ai_context.py:107` y `:178-186` |
| 14 | Packs por turno | `pns_ai_mcp/models/res_config_settings.py:91-102` |
| 14 | Reglas de dueño (contextos y skills) | `pns_ai_mcp/security/security.xml:25-157` |
| 14 | Restaurar desde el módulo | `pns_ai_mcp/models/ai_context_disk.py:23-60` |
| 14 | Campos de la skill | `pns_ai_mcp/models/ai_skill.py:82-261` |
| 14 | Skills sin revisión (PNS-23) | nota B, §7 |
| 15 | Ficha del usuario MCP | `pns_ai_mcp/views/mcp_user_views.xml:36-100`; `models/mcp_api_key_wizard.py:86-97` y `:113-125` |
| 15 | Clave de un administrador de Ajustes (NUEVO-3) | `docs/specs/diferencias_3-1-973_seges.md`, §3 |
| 15 | PIN | `pns_ai_mcp/views/mcp_user_views.xml:86-94`; `models/res_config_settings.py:128-146`; nota B, §7 (PNS-84) |
| 15 | Cabeceras de la clave y rutas | `pns_ai_mcp/controllers/main.py:438-456`, `:816-820` y `:242-298` |
| 15 | Herramientas publicadas | `pns_ai_mcp/controllers/tools_relaxaicode.py:39-40`; `controllers/safe_plan.py:356-357` y `:527-528`; `controllers/tools_context.py:151-154` (`get_context`, no publicada) |
| 15 | Orígenes web | `pns_ai_mcp/models/res_config_settings.py:80-89` |
| 15 | LIYBEN sin claves y `/mcp` 404 | `docs/pendiente/liyben_3973.md`, D20, D60 y H |
| 16 | Política de acceso a URLs | `pns_ai_mcp/models/res_config_settings.py:103-116`; `pns_ai_mcp/i18n/es.po:2843-2845`, `:2848-2850` y `:6419-6421`; título del bloque: `pns_ai_mcp/views/res_config_settings_views.xml:237`, sin entrada en `es.po` (comprobado en el código, no en pantalla) |
| 16 | Lista blanca: campos, permisos y datos | `pns_ai_mcp/models/url_whitelist.py:40-95`; `security/ir.model.access.csv:6` y `:48`; `data/url_whitelist_data.xml` |
| 16 | Servidores externos, `stdio` y «De confianza (auto-confirmar)» | `pns_ai_mcp/models/external_server.py:104-125`, `:242-254` y `:575-592` |
| 16 | Redirecciones (parche 19) | nota B, §4 |
| 17 | Compañías de la IA | `pns_ai_mcp/utils/one_company.py:48-79`; `docs/specs/comparacion_pns_ai_3-1-973.md`, §5.4 y §6.7 |
| 17 | Copia oculta por compañías | `pns_ai_chatboo/models/chatboo_session.py:122-126` y `:787-800` |
| 18 | Registro de actividad | `pns_ai_mcp/security/security.xml:69-89`; `views/ai_log_views.xml:281-293` |
| 18 | Purga del registro | `pns_ai_mcp/models/ai_log.py:908-932`; `models/res_config_settings.py:62-69` |
| 18 | Cambios aplicados, revertir y papelera | `pns_ai_mcp/models/ai_change_journal.py:40-47` y `:618-630`; `utils/change_journal.py:17` y `:177-182`; `models/res_config_settings.py:71-79` |
| 18 | Retención de sesiones: sin la clave, `read_product_settings` devuelve 0 y la pantalla muestra 0 | `pns_ai_chatboo/utils/chatboo_product_icp.py:124-131` y `:142`; `pns_ai_chatboo/models/res_config_settings.py:46-47` y `:118` |
| 18 | Exportaciones de `pns_base` | `pns_base/models/ir_attachment.py:15-43` |
| 18 | Tareas programadas | `pns_ai_mcp/data/*_cron.xml`; `pns_ai_chatboo/data/chatboo_async_cron.xml`; `pns_base/data/export_purge_cron.xml` |
| 18 | Sesión borrada en LIYBEN | `docs/pendiente/liyben_3973.md`, G («Chatboo 0 sesiones en L0») |
| 19 | Qué lleva la copia y los secretos | `pns_ai_mcp/utils/config_backup.py:5-40`; `models/res_config_settings.py:233-247`; `pns_base/models/export_secrets_wizard.py:16-24` |
| 19 | Asistente de importación | `pns_ai_mcp/wizard/config_backup_wizard.py:40-50`; `wizard/config_backup_wizard_views.xml` |
| 19 | Revisar sin escribir y AI Administrator sin Ajustes (parches 21 y 36) | nota B, §4 |
| 19 | Bloques de los Ajustes | `pns_ai_mcp/views/res_config_settings_views.xml:261-318` |
| 20 | Ajustes de Chatboo | `pns_ai_chatboo/models/res_config_settings.py:23-109`; `pns_ai_mcp/utils/engine_params.py:16-23`; `views/res_config_settings_mcp_agents_views.xml:4-105`; `models/ai_agent.py:18-70` |
| 20 | Límite de subida | `pns_ai_chatboo/utils/chatboo_product_icp.py:37`, `:46-59`, `:145` y `:190-193`; `static/src/js/chatboo_component_v2.js:4053` |
| 21 | Regla ante cada versión nueva | nota B, §8 |
| 21 | Lo que hace la actualización | `docs/specs/comparacion_pns_ai_3-1-973.md`, §7.3; `docs/specs/diferencias_3-1-973_seges.md`, §4; `docs/pendiente/liyben_3973.md`, D66, D67 y G |
| 22 | Problemas | las secciones citadas; `docs/specs/guia_configuracion_pns_ai.md:593-619` (los que siguen valiendo); `docs/pendiente/liyben_3973.md`, H |

**Se comprueba en ejecución** (prueba automática; procedimiento y resultado en «Comprobación en ejecución», al final):
los grupos y sus implicaciones (M2), los menús por grupo (M3), las etiquetas en español de esta parte (M4), los
contextos y skills registrados (M5 y M6), los roles y su uso (M7), los agentes (M8), «Permitir voces remotas» (M9),
las tareas programadas (M10), los ajustes y la retención (M11) y las reglas multicompañía (M12).

---

## Anexo A. La web frente a los módulos

Lo que dice la web del fabricante frente a lo que hacen los módulos instalados (3.1.973 con los parches de Seges).

| Tema | La web | Los módulos (3.1.973 con los parches de Seges) |
|---|---|---|
| Versiones de Odoo | De la 14 a la 20. Describe Chatboo 2.1.597. | Seges solo ha instalado y probado la 14. Este manual describe Chatboo 2.1.587, la instalada (M1). |
| Licencia | Apache-2.0. | `LICENSE` con Apache-2.0 en los tres módulos. El `NOTICE` es de PATANEGRA Soft SL: las marcas PATANEGRA, Chatboo y PAAP no se ceden, y un fork no puede usar esos nombres. Los manifiestos dicen «Other OSI approved licence», porque Odoo 14 no admite Apache-2.0 en ese campo, y llevan la cabecera SPDX Apache-2.0. |
| Roles de proveedor | 8, con audio, vídeo y embedding. | 7, sin embedding. Audio solo sirve para probar la voz al guardar el proveedor, y ningún turno pide vídeo. |
| Ejemplos de proveedores | 10. | 5. |
| Contextos del motor | 28. | 53 registros: 1 `core`, 24 `discovery`, 26 `domain` y 2 `locale`. |
| Contextos de Chatboo | 5, entre ellos `record_attachments`. | 6 (§14), sin `record_attachments`. |
| Skills de Chatboo | 10. | 10 (§6). |
| Herramientas MCP | 3. | 3 (§15); `get_context` no se publica. |
| Protocolos | 4. | 4; el rol Decisión solo lo admite SystemOne. |
| Voz | Sin servicios externos. | «Permitir voces remotas», desmarcado por defecto: si se marca, el navegador puede enviar el texto al servicio de su fabricante (§9). |
| «Admin IA» | Exige AI Administrator. | No lo exige (§13). Lo define `pns_ai_mcp`: no existe un módulo `pns_ai_admin`. Lo usan la autoría y la captura de skills, la generación de OpenAPI y la detección de servidores, también desde un «IA Escritor». |
| Solo lectura | La IA no escribe sola. | 3.1.973 tenía cuatro caminos de escritura desde la ejecución de solo lectura (PNS-100, PNS-104, PNS-105 y PNS-107). Seges los cierra con los parches 22, 37, 38 y 39. |
| Exportar a Word | Word. | Se descarga un `.doc` que por dentro es HTML. |
| Multicompañía | No la cita. | Algunas skills filtran por compañía, pero no hay ninguna regla de registro por compañía: las 27 reglas son por dueño, usuario o grupo (`pns_base` 1, `pns_ai_mcp` 20 y `pns_ai_chatboo` 6). El alcance de compañía de 3.1.973, en §17. |
| Resultados de las skills | — | Confirmado que `customer_360` puede devolver una fecha en lugar del resultado cuando su código pasa por la preparación o la reparación del motor (hoja 22). Importes: el redondeo del formateador es correcto; el texto que redacta el modelo no se ha probado. `/financial-health` filtra por fecha y compañía. |

## Anexo B. Qué cambia para el usuario en la versión de Seges

La versión de Seges es 3.1.973 con 24 parches vigentes. Aquí solo figura lo que se nota en pantalla o en el
comportamiento; el resto se resume al final.

**Se nota siempre**

| Parche | PNS | Qué nota el usuario |
|---|---|---|
| 12 | PNS-01, PNS-02 | Un «IA Administrador» sin Ajustes no puede dar ni quitar grupos por el chat: el plan se rechaza con «Only a Settings administrator can add or remove user groups.» (sin traducir). |
| 16 | PNS-54 | Al confirmar un plan desde Autorizaciones, Odoo pide la contraseña (la recuerda 10 minutos), y la tarjeta del chat solo deja confirmar al dueño del plan. |
| 19 | PNS-17 | Un servidor MCP externo que redirige da un error que pide poner su dirección final. |
| 20 | PNS-70 | Las vistas gráfico y los tableros de Odoo se siguen viendo bien después de abrir el chat. |
| 26 | M2 | En el lienzo y en las páginas no salen imágenes de registros que el usuario no puede ver, ni de compañías no marcadas en el selector. |
| 27 | F1 | La página del lienzo y sus descargas no cargan nada de fuera, tampoco gráficos de librerías externas. |
| 28 | D1 | Una página no se puede compartir con un usuario de portal; el «IA Administrador» puede leer y borrar las páginas ajenas, pero no cambiarlas. |
| 32 | PNS-97 | Un «IA Administrador» sin Ajustes no puede crear ni cambiar acciones de confianza: «Only a Settings administrator can change trusted actions.» (sin traducir). |
| 34 | PNS-96 | Si el lienzo rechaza la página o falla, la respuesta termina con «No se ha creado la página. El motivo está en el Historial IA.» |
| 36 | PNS-103 | Un «IA Administrador» sin Ajustes ya puede revisar y aplicar una importación de configuración (antes daba un error de permisos). |

**Se nota en casos concretos**

| Parche | PNS | Qué nota el usuario |
|---|---|---|
| 18 y 24 | PNS-19, PNS-102 | Si una pregunta intenta leer algo que el usuario no puede ver, el chat da un error en lugar del dato. |
| 21 | PNS-20 | «Revisar», en la importación de configuración, es una vista previa: no escribe nada. |
| 11 | PNS-82 | Al borrar una sesión del chat solo se borran los adjuntos de su dueño; los demás se desenganchan. |
| 17 | PNS-37 | Un plan que borra exige que quien lo pidió tenga permiso de borrado en Odoo. |
| 33 | PNS-29 | El consumo de los proveedores no se puede leer por la API; en pantalla se ve igual. |

**Sin efecto visible.** Los otros ocho parches no cambian lo que se ve: el 15 (PNS-07) y el 22 (PNS-100) impiden que
el código de la IA llame a 9 métodos del motor y a 22 funciones de correo, conexiones y descargas; el 39 (PNS-107), que
cree o borre cuentas IAP; el 25 (M1) escapa los valores de las filas antes de que entren en la página y comprueba el
dueño; el 29 (P-8e a) impide guardar una página con datos que no haya puesto el servidor; el 37 (PNS-104) guarda lo
pendiente antes de abrir la ejecución de solo lectura; el 38 (PNS-105) hace que las piezas que guardan por su cuenta
no toquen lo pendiente de quien las llama, y el 35 (PNS-109, NUEVO-2) corrige, tras actualizar, las dos tareas
programadas de purga.

## Etiquetas de pantalla

Las etiquetas de este manual son las del español de los módulos: el `i18n/es.po` de cada uno (`pns_base`, `pns_ai_mcp`
y `pns_ai_chatboo`), con el idioma `es_ES` cargado. `check_manual.py` (`docs/pendiente/lab_3973/`) busca cada etiqueta
«…» en los tres `es.po` y lista las que no encuentra, que se revisan a mano (frases del usuario, citas o textos sin
traducir).

Salen sin traducir, y el manual las cita así:
- los menús «My Activity» y «Activity» (§18);
- «Chatboo», que es igual en los dos idiomas;
- el título del bloque «URL access policy» de los Ajustes del motor (§16): las opciones sí están en español;
- los tipos de contexto (`core`, `domain`, `discovery`, `locale`) y el código de cada contexto (§14).

La prueba en el laboratorio comprobó 40 de 40 etiquetas de campo de la Parte II (M4, en «Comprobación en ejecución»).

## Comprobación en ejecución (prueba automática en `lab_pns_ai_3973`)

**Qué es.** `docs/pendiente/lab_3973/manual_lab.py` comprueba en una base de datos de laboratorio lo que el manual da
por hecho (bloques M1 a M12) frente a lo previsto en el código de la rama. Es de solo lectura: abre una transacción
`READ ONLY`, comprueba que lo es antes de cada bloque y la deshace al terminar (`rollback`). La salida solo lleva
nombres técnicos, etiquetas y recuentos: nunca datos de registros ni secretos. Termina con «CÓDIGO: <n>»: 0, todo
igual; 1, alguna diferencia; 8, no concluyente (base de datos sin actualizar o sin modelos de los tres módulos); 20,
error interno o escritura rechazada.

**Cómo se ejecuta.** Con el procedimiento del laboratorio (`docs/pendiente/lab_procedimiento_3973.md`), en el entorno
local de Seges, con el servidor web parado:
`odoo-dev 14 shell < docs/pendiente/lab_3973/manual_lab.py`. Antes, se puede comprobar el propio script sin Odoo ni
base de datos con `docs/pendiente/lab_3973/manual_lab_autoprueba.py`.

**Resultado del 22/11/2026** (laboratorio `lab_pns_ai_3973`, base de datos `lab_pns_ai_3973_14`, `es_ES` activo):
**CÓDIGO 0**, todo igual.

| Bloque | Qué comprueba | Iguales | Informativos |
|---|---|---|---|
| M1 | Versiones de los tres módulos | 3 | — |
| M2 | Grupos y sus implicaciones | 17 | — |
| M3 | Menús por grupo | 70 | 7 |
| M4 | Etiquetas de campo en español | 40 | — |
| M5 | Contextos registrados | 7 | — |
| M6 | Skills registradas | 33 | — |
| M7 | Roles y su uso | 9 | 3 |
| M8 | Agentes | 4 | — |
| M9 | «Permitir voces remotas» | 2 | — |
| M10 | Tareas programadas | 22 | 1 (la base de datos no está neutralizada) |
| M11 | Ajustes y retención | 6 | 18 |
| M12 | Reglas multicompañía | 2 | 1 |

Se repite con cada versión nueva del fabricante, después de adaptar los parches y antes de instalarla.

## Fuentes de los anexos

| Parte | Qué | Dónde |
|---|---|---|
| A | Lo que dice la web | Web del fabricante (patanegra.com/es: `capabilities.html`, `ai-engine.html` y `chatboo.html`), leída el 20 y el 21/11/2026; resumen propio, sin copiar su texto; puede haber cambiado después |
| A | Versiones de los módulos | `pns_base/__manifest__.py:8`; `pns_ai_mcp/__manifest__.py:8`; `pns_ai_chatboo/__manifest__.py:7` |
| A | Licencia | `pns_base/LICENSE:1-2`; `pns_base/NOTICE:6-12`; `pns_ai_mcp/NOTICE:7-13`; `pns_ai_chatboo/NOTICE:8-14`; `pns_base/__manifest__.py:2` y `:54-55`; `pns_ai_mcp/__manifest__.py:2` y `:29-30`; `pns_ai_chatboo/__manifest__.py:2` y `:23-24` |
| A | Roles | `pns_ai_mcp/data/ai_provider_role_data.xml:3-59`; `pns_ai_mcp/models/ai_provider_role.py:67-68`; `pns_ai_mcp/models/ai_provider.py:298-301` y `:708-730`; M7 |
| A | Ejemplos de proveedores | `pns_ai_mcp/static/examples/providers/` (5 archivos) |
| A | Contextos del motor | `pns_ai_mcp/ai/contexts/` (`core` 1, `discovery` 24, `domain` 26, `locale` 2) |
| A | Contextos y skills de Chatboo | `pns_ai_chatboo/data/chatboo_context_data.xml:5`; `pns_ai_chatboo/ai/contexts/`; `pns_ai_chatboo/ai/skills/system/` (10 skills) |
| A | Herramientas MCP | `pns_ai_mcp/controllers/tools_relaxaicode.py:39-40`; `pns_ai_mcp/controllers/safe_plan.py:356-357` y `:527-528`; `pns_ai_mcp/controllers/tools_context.py:151-154` |
| A | Protocolos y rol Decisión | `pns_ai_mcp/models/ai_provider.py:170-175` y `:625-639`; `pns_ai_mcp/lib/llm/drivers/systemone_driver.py:17` |
| A | Voz | `pns_ai_chatboo/models/res_config_settings.py:96-97`; `pns_ai_chatboo/utils/chatboo_product_icp.py:152-153`; `pns_ai_chatboo/i18n/es.po:2418-2419` |
| A | «Admin IA» | `pns_ai_mcp/data/ai_agent_data.xml:26-36`; `pns_ai_mcp/security/ir.model.access.csv:14` y `:62`; `pns_ai_mcp/models/ai_skill_authoring.py:139-147`; `pns_ai_mcp/wizard/skill_capture_wizard.py:347`; `pns_ai_mcp/services/openapi_spec_generator.py:613`; `pns_ai_mcp/models/external_server.py:742` |
| A | Caminos de escritura y sus parches | `docs/pendiente/informe_3973/estado_hallazgos_3973.md:183`, `:187`, `:188` y `:268`; `pns_ai_mcp/controllers/validators_base.py:279-315`; `pns_ai_mcp/controllers/controller_helpers.py:189-194`; `pns_ai_mcp/models/ai_log.py:722-725`; `pns_ai_mcp/controllers/context_builder.py:308-326` |
| A | Exportar a Word | `pns_ai_chatboo/static/src/js/chatboo_export.js:3590-3601` y `:3743` |
| A | Reglas de registro | `pns_base/security/progress_job_rules.xml` (1); `pns_ai_mcp/security/security.xml` (20); `pns_ai_chatboo/security/security.xml` (6); ninguna con compañía en `domain_force`; M12 |
| A | Resultados de las skills | `pns_ai_chatboo/ai/skills/system/customer_360.py:70-75` y `:594`; `pns_ai_mcp/utils/relaxaicode_recipe.py:266-277` y `:389`; `pns_ai_mcp/controllers/relaxaicode_prepare.py:215`; `pns_ai_mcp/controllers/relaxaicode_repair.py:236`; `pns_ai_mcp/utils/relaxaicode_render_base.py:344-355`; `pns_ai_chatboo/ai/skills/system/financial_health.py:31-37` |
| B | Parches vigentes y qué se nota | `docs/pendiente/parches_pns_ai.md:240-273` (índice de la rama; el 38, en `:4785-4791`); nota B, §4 (`docs/pendiente/informe_3973/resumen_jefe_pns_ai.md:158-206`) |
| B | 12 | `pns_ai_mcp/utils/privilege_cusp.py:102`; `pns_ai_mcp/models/ai_system_action.py:731` |
| B | 16 | `pns_ai_mcp/models/safe_operation.py:1803-1805` |
| B | 19 | `pns_ai_mcp/utils/mcp_client.py:103-115`; `pns_ai_mcp/utils/fetch_url_safe.py:128-139` |
| B | 20 | `pns_ai_chatboo/static/src/js/chatboo_heavy_libs.js:16` y `:31` |
| B | 26 | `pns_ai_chatboo/models/chatboo_canvas.py:1008`; `pns_ai_chatboo/models/chatboo_session.py:939` |
| B | 27 | `pns_ai_chatboo/models/chatboo_canvas.py:34` y `:76` |
| B | 28 | `pns_ai_chatboo/security/security.xml:67-78`; `pns_ai_chatboo/models/chatboo_canvas_page.py:20` |
| B | 32 | `pns_ai_mcp/models/ai_trusted_action.py:88-101` |
| B | 34 | `pns_ai_chatboo/models/chatboo_async_request.py:1359-1371`; `pns_ai_chatboo/i18n/es.po:2213-2214` |
| B | 36 | `pns_base/models/operation_report_wizard.py:370` y `:379` |
| B | 18 y 24 | `pns_ai_mcp/models/seges_box_a_read.py:3`; `pns_ai_mcp/controllers/context_builder.py:75` y `:120` |
| B | 21 | `pns_base/models/operation_report_wizard.py:7` y `:293` |
| B | 11 | `pns_ai_chatboo/models/chatboo_session.py:2034` y `:2075` |
| B | 17 | `pns_ai_mcp/models/ai_change_journal.py:501` y `:574` |
| B | 33 | `pns_ai_mcp/models/ai_provider.py:1096` y `:1132`; `pns_ai_mcp/wizard/ai_provider_usage_wizard.py:37` |
| B | Sin efecto visible | `pns_ai_mcp/controllers/validators_base.py:266`, `:279` y `:304`; `pns_ai_chatboo/models/chatboo_session.py:1091`; `pns_ai_chatboo/models/chatboo_canvas.py:22`; `pns_ai_mcp/controllers/controller_helpers.py:189-194`; `pns_base/utils/seges_side_env.py:3`; `pns_ai_mcp/migrations/14.0.3.1.973/post-migrate.py:1-42` |
| B | Mensajes de los parches 12 y 32 sin traducir | sin entrada en los tres `es.po` |
| Etiquetas | De dónde salen y cuáles no están traducidas | `pns_base/i18n/es.po`; `pns_ai_mcp/i18n/es.po:4928-4929`, `:4955-4956` y `:2843-2845`; `pns_ai_chatboo/i18n/es.po:659-660`; `pns_ai_mcp/views/res_config_settings_views.xml:237`; `pns_ai_mcp/models/ai_context.py:107` y `:178-186`; `docs/pendiente/lab_3973/check_manual.py:1-10` |
| Comprobación | Script, protección y códigos | `docs/pendiente/lab_3973/manual_lab.py:1-36`; `docs/pendiente/lab_3973/manual_lab_autoprueba.py:1-17` |
| Comprobación | Registro de la ejecución (CÓDIGO 0) | `docs/pendiente/lab_procedimiento_3973.md:504` |
| Comprobación | Recuentos por bloque | Salida guardada fuera del repo (`salida_manual_lab_20261122-0055.txt`, huella registrada en `docs/pendiente/lab_procedimiento_3973.md:504`) |
