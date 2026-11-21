# Manual de uso y configuración de los módulos de IA (Odoo 14, 3.1.973 con los parches de Seges)

- **Versión que describe:** `pns_base` 1.2.69, `pns_ai_mcp` 3.1.973 y `pns_ai_chatboo` 2.1.587, con los 24 parches
  activos de Seges (rama `14.0-pns-ai-3973`; la misma que se instaló en LIYBEN el 20/11/2026).
- **Sustituye a** [guia_configuracion_pns_ai.md](guia_configuracion_pns_ai.md), que queda como registro de 3.1.782.
- **Etiquetas de pantalla:** las del español de los módulos (`i18n/es.po`). Donde el módulo no trae traducción, la
  etiqueta sale en inglés y se cita así.
- **Fuentes:** el código de la rama y la documentación del repo; cada parte las lista al final. La web del fabricante
  se compara aparte (Anexo A). Lo que solo se comprueba con Odoo en marcha se comprueba con la prueba automática del
  final.
- **Estado:** borrador por partes (21/11/2026). Parte 1: §0 y Parte I.

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
- Parte II. Funcional y administración *(parte 2)*: grupos; proveedores, roles, cadena, failover, tope y Diseño sin
  rol; agentes; contextos y skills; claves y servidor MCP; lista blanca y servidores externos u OpenAPI; multicompañía;
  registros, consumo y retención; importar y exportar la configuración; ajustes de Chatboo; qué cambia al actualizar;
  problemas típicos.
- Anexo A. La web frente a los módulos *(parte 3)*.
- Anexo B. Qué cambia para el usuario en la versión de Seges *(parte 3)*.
- Etiquetas de pantalla *(parte 3)*.
- Comprobación en ejecución (prueba automática en `lab_pns_ai_3973`) *(parte 3)*.

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

**Se comprueba en ejecución** (prueba automática, parte 3): los menús que ve cada grupo, las etiquetas en español de
las vistas y menús, los nombres y comandos de las 10 skills registradas, el valor por defecto de «Permitir voces
remotas» y el de la retención.
