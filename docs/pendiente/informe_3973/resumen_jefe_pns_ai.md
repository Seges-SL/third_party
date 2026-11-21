# Módulos de IA de PATANEGRA Soft en Odoo 14: qué se encontró, qué ha corregido Seges y dónde estamos

- **Nota interna de Seges. No se envía al fabricante.**
- **Para:** dirección (perfil funcional de Odoo). **De:** Sergio Guerrero. **Fecha:** 21/11/2026.
- **Versiones:** `pns_base` 1.2.69, `pns_ai_mcp` 3.1.973 y `pns_ai_chatboo` 2.1.587, con las correcciones de Seges.
- **Base:** el [inventario de hallazgos](estado_hallazgos_3973.md) y el
  [informe al fabricante](../informe_fabricante_pns_ai_3973.md) (2.ª entrega, pendiente de envío), donde está el
  detalle técnico. Esta nota lo cuenta en términos funcionales.

## 1. En una página

**Qué son.** Tres módulos de PATANEGRA Soft que añaden inteligencia artificial a Odoo:
- **`pns_base`:** utilidades comunes (exportar e importar la configuración, entre otras).
- **AI Engine (`pns_ai_mcp`):** el motor. Habla con los proveedores de IA (Gemini, OVH…) y trabaja con los datos así:
  - la **caja A**, donde el modelo de IA escribe y ejecuta un pequeño programa que **solo lee** datos para contestar;
  - la **caja B**, donde el modelo propone un **plan de cambios** (crear, modificar, borrar, dar permisos) que no se
    aplica hasta que una persona lo **confirma**.
- **Chatboo (`pns_ai_chatboo`):** el chat del backend. Contesta con tablas y gráficos, exporta, lee adjuntos y crea
  páginas visuales («lienzo») que se pueden compartir.

**Qué se encontró.** Desde el 08/10 hemos revisado cuatro versiones (de 3.1.486 a 3.1.973) y numerado 114 hallazgos
(PNS-01 a PNS-114). Lo más grave lo puede provocar **cualquier usuario del chat**, sin ser administrador, con un texto
preparado («inyección de prompt») pegado en el chat o llegado a un registro:
- **la caja A no era de solo lectura de verdad:** leía datos sin permiso, también secretos, y podía sacarlos fuera;
- **la caja B se podía saltar o abusar:** confirmar sin la persona, darse permisos con un plan, borrar adjuntos ajenos;
- **la actualización cambia datos sin avisar:** traducciones de otros módulos, crons rotos, contextos reescritos.

**Qué ha hecho Seges.** El 19/10 se decidió corregirlo nosotros en lugar de esperar al fabricante. Hoy llevamos **24
correcciones** («parches») sobre 3.1.973, cada una con sus tests: todo lo crítico y casi todo lo alto que el fabricante
no ha corregido (los tres altos que quedan se aceptan o se le dejan a él, §7).

**Dónde estamos (21/11/2026):**
- **LIYBEN**, en producción con 3.1.973 y nuestras correcciones **desde el 20/11** (13 minutos de corte, sin errores).
- **El informe al fabricante (2.ª entrega)**, pendiente de revisión y envío. Pide fecha para lo más urgente.
- **Pendiente:** el manual de uso y configuración y, después, la versión para Odoo 17.

**En cifras, con 3.1.973.** De lo comunicado al fabricante (111 puntos): 84 corregidos por él, 12 abiertos que corrige
Seges, 9 abiertos con el riesgo aceptado y 6 abiertos de gravedad media o baja. De los 18 hallazgos nuevos: 1 corregido
por el fabricante, 9 por Seges, 3 cubiertos con configuración o procedimiento y 5 abiertos (media o baja). Detalle en §3.

---

## 2. Cronología

| Fecha | Qué pasó |
|---|---|
| 08/10/2026 | **Primer informe al fabricante** sobre 3.1.486: PNS-01 a PNS-80. |
| 13-16/10 | El fabricante publica **3.1.782**. La revisamos y enviamos dos entregas: el 15/10 (PNS-81 a PNS-92) y el 16/10 (PNS-93 a PNS-96, con pruebas con un proveedor de IA real). Entorno de pruebas (**staging, base de datos `pns_demo`**) montado el 15-16/10. |
| 16/10 | **Instalación en LIYBEN** de 3.1.782, con 6 parches de compatibilidad con Odoo 14 y medidas provisionales. Los usuarios de portal se archivaron el 23/10. |
| 19/10 | **Reunión de seguimiento:** Seges corrige los hallazgos en lugar de esperar al fabricante. Se acepta enviar datos reales a los proveedores de IA, sin tope de gasto por ahora. La 2.ª entrega del informe se envía al final, sin código. |
| 22/10 | El fabricante contesta a nuestro informe con un documento de auditoría y la versión **3.1.879**. |
| 23/10 | Se decide cambiar una sola vez la base de nuestras correcciones a 3.1.879. |
| 26/10-09/11 | **Correcciones sobre 3.1.879** en cuatro entregas, cada una probada en el laboratorio y subida al staging (26/10, 29/10, 03/11 y 09/11). |
| 09-10/11 | El fabricante publica **3.1.973**. Tras compararla, se decide pasar a ella entera: corrige muchas cosas, entre ellas dos fallos de gravedad alta que aún no teníamos corregidos. |
| 11-17/11 | **Correcciones portadas a 3.1.973:** se retiran 6 parches (ya los cubre el fabricante), se adaptan 19 y se añaden 5 nuevos. |
| 18/11 | 3.1.973 con las correcciones, en el **staging `pns_demo`**. |
| 19/11 | **Ensayo** de la actualización sobre una copia de LIYBEN. |
| 20/11 | **LIYBEN pasa de 3.1.782 a 3.1.973** con las correcciones (copia completa antes). Prueba de uso real, integración en la rama principal y limpieza del staging, que se borra. |
| 20-21/11 | Inventario de hallazgos y **2.ª entrega del informe al fabricante** (pendiente de envío). |

---

## 3. Qué se encontró

**Frente a lo comunicado al fabricante** (PNS-01 a PNS-96 y 15 observaciones, 111 en total), con 3.1.973:

| Situación | N.º |
|---|---|
| Corregido por el fabricante | 84 |
| Sigue abierto en su código; corregido por Seges | 12 |
| Sigue abierto; Seges acepta el riesgo | 9 |
| Sigue abierto, sin corrección ni aceptación (gravedad media o baja) | 6 |

**Hallazgos nuevos** (PNS-97 a PNS-114, 18): el fabricante ya ha corregido uno (PNS-101); Seges corrige 9; 3 se cubren
con configuración o con el procedimiento de actualización (PNS-110, PNS-113 y PNS-114), y 5 quedan abiertos (PNS-98,
PNS-99, PNS-106, PNS-111 y PNS-112).

A continuación, agrupado por el efecto práctico. Entre paréntesis, la gravedad y el número del hallazgo, para
buscarlo en el informe.

### 3.1 Permisos: quién puede hacer qué

- **Darse permisos con un plan de la IA** (Crítica, PNS-01 y PNS-02). Un plan de la caja B puede dar o quitar grupos de
  Odoo. En 3.1.973 el plan ya se ejecuta con los permisos de quien lo pidió (antes, con los de quien lo confirmaba),
  pero basta el permiso «Permisos de acceso» de Odoo: no exige ser administrador de Ajustes.
- **Confirmar sin la persona** (Crítica, PNS-54). La confirmación de un plan no pide contraseña ni nada que demuestre
  que la hace el usuario. Si alguien consigue ejecutar código en el navegador de un usuario (un fallo de tipo XSS en
  cualquier pantalla), puede confirmar planes en su nombre.
- **Configuración que cualquier AI Administrator puede tocar:** las «acciones de confianza» del motor (Media, PNS-97), el
  diario de cambios, que sirve para deshacer (Media, PNS-37), y el consumo de los proveedores, que cualquier usuario,
  también de portal, puede leer por la API (Media, PNS-29).
- **Páginas compartidas** (Baja): el dueño puede añadir como lector a un usuario de portal, y un AI Administrator puede
  cambiar páginas ajenas.

### 3.2 Escrituras que nadie ha confirmado, o que se pierden

- **«Review» de la importación de configuración** (Alta, PNS-20): debería ser una vista previa, pero deja escritos parte
  de los cambios.
- **Cambios que se confirman o se pierden por el camino** (Alta, PNS-105; Baja, PNS-104 y PNS-107). Algunas piezas del
  motor guardan cosas por su cuenta (el historial, por ejemplo) y, al hacerlo, confirman o descartan lo que la
  operación en curso tenía a medias. En el peor caso, un plan confirmado deja un proceso de Odoo bloqueado; si viene del
  chat, hasta que se reinicia el servicio.
- **Borrar una sesión del chat borra adjuntos ajenos** (Alta, PNS-82).
- **Planes que dicen haberse aplicado y no** (Media, PNS-99: quitar un grupo queda como hecho sin quitarlo). El chat
  también puede afirmar que ha creado una página que no ha creado (Baja, PNS-96).

### 3.3 Datos que salen

Es lo más importante, porque lo puede provocar **cualquier usuario del chat**, sin ningún rol de IA:
- **La caja A lee como superusuario** (Crítica, PNS-102): a través del usuario actual llega a datos que el usuario no
  puede ver, incluido el secreto del doble factor de otros usuarios.
- **Secretos que ya están en memoria** (Alta, PNS-108, resto de PNS-19): 3.1.973 protege bien las columnas secretas al
  leerlas de la base de datos, pero no si el valor ya está en la memoria del proceso. Comprobado con cuatro tipos de
  secreto.
- **Salida por correo o por la red sin escribir nada** (Alta, PNS-100): desde la caja A se puede mandar un correo o abrir
  una conexión a cualquier servidor, con cualquier dato que el usuario pueda leer, sin confirmación.
- **Métodos del motor alcanzables desde la caja A** (Crítica, resto de PNS-07): 9 de los 28 que señalamos.
- **Cabeceras que viajan a otro servidor** en una redirección (Alta, PNS-17).
- **El lienzo** (Media): un texto malicioso en un registro, como la ciudad que un usuario de portal pone en «Mi cuenta»,
  se ejecuta en la página que genera la IA para otro usuario. La página puede pedir datos al propio Odoo, y las
  descargas no llevan protección. Además, la página muestra imágenes de registros que el usuario no puede ver.
- **Datos hacia el proveedor de IA** (Alta, PNS-18): lo que se pregunta y lo que se lee sale hacia el proveedor (Google,
  OVH). Es la naturaleza del producto; no hay forma de excluir modelos o campos. Aceptado (§7).

### 3.4 Pérdida o cambio de datos al actualizar

- **Traducciones de otros módulos** (Media, PNS-113): para que lleguen los textos nuevos de los `pns_*` hay que recargar
  el idioma con sobrescritura, y eso cambia textos de otros módulos en toda la instalación. En la copia de LIYBEN: 49
  traducciones de otros módulos, 13 con otro texto. Sin copia previa no se puede deshacer.
- **Crons rotos** (Baja, PNS-109): tras actualizar, los dos crons de purga de cachés llaman a una función que ya no
  existe y fallan en cada ejecución.
- **Proveedores con un papel que no admiten** (Baja, PNS-114): la actualización convierte las antiguas casillas de cada
  proveedor en «roles» sin comprobar si el proveedor los admite. Después, guardar los roles de ese proveedor da error.
- **Lo que la actualización reescribe sin anunciarlo:** los contextos de fábrica sin dueño (12 archivos, entre ellos las
  instrucciones generales del asistente), las skills de fábrica (7 se borran y 4 se crean), el historial de Chatboo y
  cinco parámetros que cambian de nombre. Al actualizar desde 3.1.782 se pierde además qué agente hizo cada llamada en
  el historial del motor (en LIYBEN no se perdió nada: ese historial estaba vacío).
- **Cambios de comportamiento:** todo AI Administrator pasa a tener acceso al chat (AI Conversational); el plan se
  ejecuta como quien lo pidió y en las compañías marcadas en la pantalla; si ningún proveedor tiene el rol Diseño, las
  páginas las diseña el proveedor del chat (Baja, PNS-110).

### 3.5 Compatibilidad con Odoo 14

- **Python 3.7** (el de Odoo 14): las primeras versiones no se podían cargar. Lo corregimos con 4 parches, que el
  fabricante integró en 3.1.879 (y el último resto, en 3.1.973).
- **Gráficos de Odoo** (Alta, PNS-70): tras abrir el chat, las vistas gráfico de Odoo (y el tablero de Facturación) se
  pintan mal hasta recargar la página, porque Chatboo sustituye la librería de gráficos de Odoo por una más nueva.
  Afecta a cualquier instalación. 3.1.973 sigue igual.
- **Otros, menores:** renombrados de datos que en Odoo 14 no se ejecutan (Baja, PNS-88) y una imagen del lienzo en un
  formato que no se reconoce (Baja, PNS-106).

---

## 4. Qué ha corregido Seges y por qué

**Criterio** (19/10 y 23/10): lo crítico y lo alto se corrige siempre; lo medio y lo bajo, caso a caso (corregir o
aceptar). Cada corrección lleva número, marcas en el código, tests que fallan si se quita y una nota de cómo comprobar
si el fabricante ya lo ha corregido en una versión nueva. Hoy son **24 parches activos**. En el uso normal el usuario
casi no nota nada; lo que sí nota va marcado con **«Se nota:»**.

**La caja A no lee como superusuario ni saca datos**
- **Parches 24 y 18** (PNS-102, PNS-19 y PNS-108): el usuario de la caja A se construye con sus permisos reales, y cada
  lectura se comprueba con el permiso del modelo y con la lista de columnas secretas, también si el valor ya está en
  memoria. Si una petición intenta leer algo sin permiso, el chat da un error en lugar del dato.
- **Parches 22, 15 y 39** (PNS-100, PNS-07 y PNS-107): una lista de funciones que la caja A no puede llamar: 22 nombres
  más que el fabricante (correo, conexiones, descargas…), los 9 métodos del motor que seguían abiertos y la de cuentas
  IAP.
- **Parche 19** (PNS-17): en una redirección a otro servidor solo viajan las cabeceras neutras, y el cliente MCP no
  sigue redirecciones. **Se nota:** un servidor MCP externo que redirige da un error que pide poner la URL final.

**Permisos y confirmaciones**
- **Parche 12** (PNS-01 y PNS-02): dar o quitar grupos con un plan exige ser administrador de Ajustes a quien pide, a
  quien confirma y a quien ejecuta. Se suma al criterio del fabricante. **Se nota:** un AI Administrator sin Ajustes no
  puede dar ni quitar grupos por el chat.
- **Parche 16** (PNS-54): confirmar desde Autorizaciones pide la contraseña (Odoo la recuerda 10 minutos), y la tarjeta
  del chat solo da la confirmación al dueño del plan. **Se nota:** la contraseña al confirmar desde Autorizaciones.
- **Parches 32, 17 y 33** (PNS-97, PNS-37 y PNS-29): las acciones de confianza exigen Ajustes; el diario de cambios solo
  lo escribe el sistema, y borrar con un plan exige permiso de borrado; el consumo de los proveedores ya no se lee por
  la API. **Se nota:** un AI Administrator sin Ajustes no puede editar las acciones de confianza.

**Lo que no se confirmó no se escribe, y lo pendiente no se pierde**
- **Parches 21, 37 y 38** (PNS-20, PNS-104 y PNS-105): «Review» de la importación es una vista previa de verdad; al
  abrir la caja A se guarda antes lo pendiente; las piezas que guardan por su cuenta trabajan aparte y no tocan lo
  pendiente de quien las llama.
- **Parche 11** (PNS-82): borrar una sesión del chat solo borra los adjuntos de su dueño; los demás se desenganchan.

**El lienzo y las páginas**
- **Parches 25 a 29:** los valores de las filas se escapan antes de entrar en la página; no se guarda una página con
  datos que no haya puesto el servidor; la página y las descargas bloquean todo lo externo y las peticiones al propio
  Odoo; solo se incrustan imágenes que el usuario puede ver; las páginas solo se comparten con usuarios internos, y el
  AI Administrator solo puede leer o borrar las ajenas. **Se nota:** no salen imágenes de registros que el usuario no
  puede ver; la página no carga nada de fuera (tampoco gráficos de librerías externas); no se puede compartir con un
  usuario de portal.
- **Parche 34** (PNS-96): si el lienzo rechaza o falla, el servidor añade al final de la respuesta un aviso fijo.
  **Se nota:** el aviso «no se ha podido crear o cambiar la página».

**Compatibilidad, actualización e importaciones**
- **Parche 20** (PNS-70): la librería de gráficos del chat se carga con otro nombre y no pisa la de Odoo. **Se nota:**
  las vistas gráfico y los tableros de Odoo se ven bien después de abrir el chat.
- **Parche 35** (PNS-109): un script tras la actualización arregla los dos crons de purga.
- **Parche 36** (PNS-103): un AI Administrator sin Ajustes ya puede revisar y aplicar una importación de configuración
  (antes daba error de permisos). **Se nota:** la revisión de importaciones funciona.

**Sin parche, por configuración o por procedimiento de actualización**
- **Rol Diseño (PNS-110):** en LIYBEN está solo en un proveedor elegido, sin alternativa. Hoy ese proveedor está
  inactivo, así que **el botón Canvas no aparece** y nadie diseña páginas hasta que se defina qué proveedor las hace.
- **Traducciones (PNS-113):** en la actualización se recarga el idioma y, en la misma operación, se restauran las
  traducciones de otros módulos que la recarga cambia.
- **Roles de los proveedores (PNS-114):** en la actualización se quita el rol que el proveedor no admite.

---

## 5. Qué ha corregido el fabricante

El fabricante ha respondido a cada entrega con una versión nueva y ha corregido la mayor parte de lo comunicado: **84 de
111**, a veces con un criterio más amplio que el que sugeríamos. Por eso ha habido parches de Seges que han dejado de
hacer falta:
- **Con 3.1.879 (23/10):** los parches 1 a 9 (compatibilidad con Python 3.7, con Gemini 3 y un bloqueo del chat, y tres
  métodos que debían ser privados).
- **Con 3.1.973 (10/11):** los parches 10, 13, 14, 23, 30 y 31.

| Parche retirado | Qué corregía | Cómo lo resuelve 3.1.973 |
|---|---|---|
| 10 | Un método público de la mesa de entrega de claves por PIN (PNS-83) | Los métodos de la mesa pasan a privados |
| 13 | Crear un plan con la identidad de otro usuario | Solo el sistema crea planes, y el plan se ejecuta como quien lo pidió |
| 14 | Borrar los contextos de fábrica con un método público | El método pasa a privado |
| 23 | Escapar de la caja A hacia el entorno real de Odoo (PNS-101, Crítica) | La caja A trabaja con una lista cerrada de lo permitido, más estricta que nuestra corrección |
| 30 | Escribir líneas del historial a nombre de otro usuario | Los métodos del historial pasan a privados |
| 31 | Llamar directamente al proveedor de IA sin pasar por el motor | El método pasa a privado |

**Otras mejoras de 3.1.973 que nos ahorran trabajo:** las columnas secretas cerradas en todos los modelos; el código de
las skills, ejecutado en la caja A; la protección contra el «DNS rebinding» al descargar páginas e imágenes de internet; el trabajo
en las compañías marcadas en la pantalla (multicompañía), y dos fallos de gravedad alta que aún no habíamos corregido:
un AI Administrator sin Ajustes podía fijar la clave MCP de un administrador, y el asistente de exportación borraba
cualquier adjunto. En el informe le reconocemos estas mejoras.

---

## 6. Qué se ha probado

- **Revisión del código** de 3.1.973 frente a 3.1.879, hallazgo por hallazgo: todo lo abierto y todo lo crítico y alto
  cuyo código cambia, sin regresiones.
- **Tests del fabricante** sobre 3.1.973 sin tocar: 246, sin fallos.
- **Nuestra batería** (tests del fabricante más los de Seges) sobre la versión corregida: **580 tests**, con 1 fallo
  esperado y 6 saltados, igual con las dos versiones del núcleo de Odoo 14 (la de la imagen oficial y la de nuestros
  servidores). El fallo es un test del fabricante que supone que un AI Administrator sin Ajustes puede dar grupos: el
  parche 12 lo impide.
- **Laboratorio** (bases de datos de prueba en el equipo): usuarios con y sin AI Administrator, Ajustes y «Permisos de
  acceso», usuarios de portal y tres compañías; proveedor real, Google Gemini.
- **Staging `pns_demo`** (18/11): actualización desde 3.1.879 en 54 s, servicio parado 9 min, 2 procesos de Odoo y
  proveedores reales. Correcto. Un plan que el núcleo de Odoo no pudo ejecutar falló sin dejar nada a medias
  (Baja, PNS-112).
- **Ensayo sobre una copia de LIYBEN** (19/11): la actualización desde 3.1.782, la recarga de traducciones y el rol
  Diseño, con el servidor de LIYBEN reproducido en el equipo.
- **LIYBEN** (20/11): copia completa antes; actualización en 90 s y **13 minutos de corte**; todas las comprobaciones
  correctas y 0 errores en el log. Uso real del chat: dos preguntas y una tabla de los 5 clientes con más facturación,
  respondidas por el proveedor OVH, sin botón Canvas (como se esperaba) y sin errores.

**Salvedad.** De los 84 corregidos por el fabricante, 53 los damos por buenos por lo que comprobamos en 3.1.782 o
3.1.879, sin volver a revisarlos en 3.1.973: el fabricante no ha tocado su código o son de gravedad media o baja. Los
críticos y altos sí se han vuelto a revisar.

**No probado:** otros proveedores (Anthropic, OpenAI nativo), la voz, otras versiones de Odoo (solo la 14) y unos pocos
puntos que se dan por lectura del código. El informe al fabricante lo detalla.

---

## 7. Riesgos aceptados y por qué

- **Datos reales hacia los proveedores de IA** (Alta, PNS-18). Es la función del producto (decisión del 19/10).
  Proveedores: Gemini y OVH. Gemini se usa en el nivel gratuito, en el que Google puede usar el contenido para mejorar
  sus productos. Sin tope de gasto por ahora.
- **Skills nuevas activas sin revisión** (Alta, PNS-23). Su código ya corre en la caja A, de solo lectura, así que el
  efecto queda muy acotado. Se repite la petición: que nazcan inactivas hasta revisarlas.
- **Claves MCP elegidas por el usuario, y PIN y clave legibles por el AI Administrator** (Media, PNS-33 y PNS-84). El
  servidor MCP no está expuesto en LIYBEN (da error 404 desde fuera), no hay ninguna clave MCP (comprobado el 20/11) y
  la mesa de PIN no se usa.
- **El usuario puede manipular el historial de sus propias sesiones del chat** (Media, PNS-61). Solo le afecta a él.
- **Menores:** `platform` en la caja A (PNS-51), tests que no vienen en el paquete (PNS-50 y PNS-77) y renombrados que
  no se ejecutan (PNS-88). Gravedad baja; se repite la petición.
- **Abiertos sin corrección:** el `commit` de la caja B sobre la operación en curso (Alta, PNS-26), que solo arregla
  bien el fabricante, y su anexo (un aviso de error al «Ejecutar» desde la ficha). El resto, de gravedad media o baja:
  CORS en el servidor MCP (PNS-28), quitar un grupo que queda como hecho (PNS-99), adjuntos huérfanos (PNS-98), el plan
  que el núcleo no ejecuta (PNS-112), imágenes del lienzo (PNS-106 y PNS-111) y tres observaciones. Corregirlos tocaría
  la caja B más de lo que justifica el riesgo, o el efecto es solo funcional. Van al fabricante. Mientras, **antes de
  confirmar un plan, revisarlo en la ficha**.
- **Lo que la actualización reescribe sin anunciar** (parámetros renombrados, skills y contextos de fábrica, historial de
  Chatboo). En el staging y en LIYBEN no había ediciones manuales que perder. Se vuelve a comprobar antes de cada
  actualización.
- **Restos conocidos de nuestras correcciones:** por ejemplo, la vía de la sesión del lienzo, abierta con el alcance
  limitado, o algunos campos calculados que llegan a las cuentas IAP (resto de PNS-107). Sin vía de ataque útil
  conocida. Anotados en el registro de parches y en el informe.

**Riesgo de fondo: mantener las correcciones.** Cada versión del fabricante obliga a revisar, adaptar y volver a probar
las correcciones (§8). Con 3.1.973 ha sido algo más de una semana de trabajo (del 11 al 20/11), con 24 parches.
Mientras el fabricante no corrija lo pendiente, ese coste se repite.

---

## 8. Qué queda en manos del fabricante y qué se hace con cada versión nueva

**Lo que le pedimos con prioridad** (con fecha prevista de corrección para los cuatro primeros):
1. que la caja A no lea como superusuario (PNS-102);
2. que no pueda mandar correo ni abrir conexiones (PNS-100);
3. que no devuelva secretos que ya estén en memoria (PNS-108);
4. que las piezas que guardan por su cuenta no confirmen ni descarten lo de la operación en curso (PNS-105);
5. que la confirmación se ligue al usuario (PNS-54);
6. a 11: los 9 métodos abiertos de PNS-07; que dar grupos exija Ajustes; el borrado de adjuntos; los gráficos de Odoo;
   las traducciones de otros módulos, y las redirecciones y la importación.

Le proponemos además un mismo arreglo de fondo para los tres primeros: dejar de proteger la caja A con listas de nombres
y protegerla por construcción.

**Con cada versión nueva** (regla vigente desde el 19/10, confirmada el 10/11):
1. **No se instala sola.** La versión se descarga fuera del repositorio y se compara con la nuestra, buscando sobre todo
   correcciones de seguridad.
2. **Se decide** con esa comparación: quedarse, traer correcciones concretas o pasar a la versión entera, como con
   3.1.973.
3. **Si se pasa a ella:** cada parche dice cómo comprobar si el fabricante ya lo ha corregido. Los que sobran se retiran
   y sus tests se quedan para vigilar que no vuelva el fallo. Los demás se adaptan y se vuelve a probar todo
   (laboratorio, staging, ensayo sobre una copia y producción con copia completa antes).

**Siguiente:** revisar y enviar el informe; el manual de uso y configuración; después, la versión de Odoo 17.

---

## 9. Glosario

| Término | Qué es |
|---|---|
| **Actualización (`-u`)** | Actualizar un módulo en Odoo. En estos módulos transforma datos: roles, contextos, skills y crons. |
| **Ajustes (administrador de)** | El grupo de Odoo «Administración / Ajustes» (`base.group_system`). |
| **AI Administrator, AI Conversational** | Grupos de los módulos: administrar la IA y usar el chat. |
| **Autorizaciones** | Menú del motor donde se revisan y confirman los planes de la caja B. |
| **Caja A** | Pequeño programa que escribe el modelo de IA y ejecuta el motor para **leer** datos y contestar. Debe ser de solo lectura. |
| **Caja B** | Planes de cambio que propone la IA y que no se aplican hasta que alguien los confirma. |
| **Contexto** | Instrucciones que el motor da al modelo según la pantalla o la tarea. |
| **Inyección de prompt** | Texto preparado (pegado en el chat o guardado en un registro) que hace que la IA haga algo que el usuario no ha pedido. |
| **LIYBEN** | Nuestra base de datos interna, en producción, con datos reales de la empresa. |
| **Lienzo (Canvas, Design)** | Página visual que genera la IA a partir de una tabla, en un marco dentro de Odoo. |
| **MCP** | Protocolo para que herramientas externas usen el motor con una clave. |
| **Parche** | Corrección numerada de Seges sobre el código del fabricante, con sus tests. |
| **Proveedor, rol** | Servicio de IA (Gemini, OVH…) y el papel que cumple: conversación, diseño, decisión… |
| **Skill** | Receta empaquetada que el chat sabe usar (por ejemplo, «top de ventas»). |
| **Staging (`pns_demo`)** | Entorno de pruebas en el servidor, con datos de demostración. Borrado el 20/11. |
| **Superusuario** | Lectura o escritura sin comprobar permisos. |
| **Laboratorio** | Bases de datos de prueba en el equipo de desarrollo. |
