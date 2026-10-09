# pns_ai_mcp, pns_ai_chatboo y pns_base — Decisiones pendientes

**Fecha:** 2026-10-08 (ampliado con Chatboo y con el cierre de la fase 2 el 2026-10-09) · **Rama:** `14.0-analisis-pns-ai` · **Odoo:** 14.0
**Para:** responsable de Seges que decide el despliegue.
**Fuentes:** [análisis consolidado](../specs/analisis_pns_ai_mcp.md) (§4 riesgos, §5 contradicciones,
§6 preguntas), [consolidado de Chatboo](../specs/analisis_pns_ai_chatboo.md) (§4 riesgos 54-78,
§6 preguntas), [verificación de seguridad](verificacion_seguridad_pns_ai.md), [análisis de
pns_base](../specs/analisis_pns_base.md), los bloques 1-8 del análisis de `pns_ai_mcp` y los
bloques C1-C3 de `pns_ai_chatboo`.

## Resumen

1. `pns_ai_mcp` ("AI Engine", PATANEGRA Soft) es el motor de IA de la familia PNS: conecta Odoo con proveedores de IA, publica Odoo como servidor MCP y deja que la IA consulte datos y proponga cambios que un humano confirma. Necesita `pns_base`, que además cambia el comportamiento de módulos que no son PNS.
2. `pns_ai_chatboo` 2.1.322 ("Chatboo") es el chat de IA dentro del backend: cada mensaje lo resuelve `pns_ai_mcp`, y lo ve quien tenga clave MCP generada (no tiene grupo propio).
3. `pns_ai_mcp` se ha probado en un laboratorio local (base de datos de demostración, usuarios de prueba, sin claves de IA). En la fase 2 (2026-10-09) se instaló también Chatboo y se resolvieron F2, F8, F19, F20, F23, F29 y F45 (ver el anexo); la prueba de F18 resultó no concluyente. El resto de Chatboo solo se ha analizado leyendo el código.
4. **Prueba A:** un usuario interno sin ningún permiso de IA **y un usuario de portal** se convirtieron en administradores de Odoo con una sola llamada.
5. **Pruebas B y C:** el mismo usuario puede invocar las acciones de sistema (instalar o desinstalar módulos) y el borrado de las skills de fábrica (solo se probaron la vista previa y un nombre inexistente).
6. **Prueba D:** quien propone una operación supervisada puede confirmársela a sí mismo o pasársela a otro usuario, sin el control humano previsto.
7. **Fase 2, confirmado:** un usuario de portal también invoca las vistas previas de las acciones de sistema y el borrado de skills (F2); un interno sin grupos de IA lee los tokens de los servidores externos, las cachés y las elecciones de otros (F8); cualquier interno lee, cambia y borra las conversaciones de Chatboo de otro (F29); el cron de purga de la caché de `api_call` deja de ejecutarse tras la primera vez (F20); los tests del módulo fallan, en parte por el entorno (F23). **Descartado:** que Odoo no arranque con `hr` y Chatboo (F45). Chatboo se instala sin errores (F19). **No concluyente:** que las migraciones no se ejecuten al actualizar (F18); se instaló y actualizó con la misma versión, así que la prueba no lo demuestra. Sigue verificado en el código del cargador de Odoo.
8. Ninguna asignación de grupos lo evita: los fallos están en el código del fabricante y solo él puede corregirlos (los módulos no se modifican).
9. `pns_ai_mcp`: además, fugas de claves de servicios externos (confirmadas en la fase 2), posible XSS en el chat y envío de datos de negocio al proveedor de IA sin filtros (52 riesgos: 7 críticos, 20 altos).
10. Chatboo añade 25 riesgos (2 críticos, 6 altos): cualquier interno lee, cambia y borra las conversaciones de otros (confirmado en la fase 2) y puede plantar en ellas código que se ejecuta al abrir el chat la víctima, y cualquier XSS del chat puede confirmar operaciones supervisadas sin el usuario.
11. Chatboo pinta casi todo lo que responde la IA como HTML sin sanear: además del XSS, permite sacar datos sin ningún clic mediante imágenes externas.
12. Con la imagen común no se instala: faltan `openpyxl`, `httpx` y `pydantic` (Chatboo no añade librerías obligatorias).
13. Conclusión técnica: **ninguno de los dos módulos es apto para una base de datos con usuarios reales** hasta que el fabricante corrija los críticos; las decisiones **BLOQUEANTE** van antes de cualquier instalación.

## Cómo leer este documento

- **Riesgo n.º 1-53** remite a la tabla §4 del [consolidado](../specs/analisis_pns_ai_mcp.md#4-riesgos-consolidados-sin-duplicados-por-gravedad).
  **Riesgo n.º 54-78** remite a §4.1 del [consolidado de Chatboo](../specs/analisis_pns_ai_chatboo.md#41-riesgos-nuevos-de-chatboo),
  que continúa la misma numeración; su §4.2 indica qué riesgos 1-53 confirma, agrava o mitiga Chatboo.
  **Riesgo pns_base X** remite a §13 del [análisis de pns_base](../specs/analisis_pns_base.md#13-riesgos-dudas-y-lo-que-no-se-puede-saber-sin-ejecutar).
- **D1-D32** son las decisiones del §6.2 del consolidado y **D33-D46** las del §6.2 del
  consolidado de Chatboo. **PB-n** es la pregunta abierta n.º n de `pns_base` (la PB-4 ya está
  resuelta y no se incluye; la PB-3 va con D3, la PB-6 con D8 y la PB-9 con D2).
- **BLOQUEANTE:** hay que decidirla antes de instalar en cualquier base de datos con usuarios
  reales (también el VPS de pruebas si tiene usuarios reales o de portal). **BLOQUEANTE si se
  instala Chatboo:** solo lo es cuando Chatboo forma parte de la instalación (D18).

| Tema | Decisiones | Bloqueantes |
|---|---|---|
| 1. Despliegue y bloqueo | D1, D33, D18, D17, D38, D19, D20, D23, D26, D29, D31 | D1; con Chatboo: D33, D29 |
| 2. Permisos y grupos | D4, D46, D5, D22, D24, D25, D27, D36 | D4; con Chatboo: D46 |
| 3. Datos hacia el proveedor de IA (RGPD) | D10, D11, D12, D13, D35, D41, D42 | D10 |
| 4. Secretos y copias | D6, D7, D8 + PB-6 | — |
| 5. Infraestructura del VPS | D3 + PB-3, D14, D15, D16, D21, D30, D39, D40 | D3 |
| 6. Comunicación con el fabricante | D2 + PB-9, D28, D32, D34, D37, D44, D45 | — |
| 7. Efectos de pns_base (y Chatboo) en módulos que no son PNS | D9, D43, PB-1, PB-2, PB-5, PB-7, PB-8 | D9, PB-1, PB-2 |

---

## 1. Despliegue y bloqueo

### D1 — ¿Se bloquea todo despliegue hasta que el fabricante corrija los fallos confirmados A-D? — **BLOQUEANTE**

**Contexto:** las pruebas A-D demostraron que cualquier usuario con sesión, incluido uno de
portal, puede hacerse administrador de Odoo y saltarse la supervisión humana de las escrituras.
Ningún paso de configuración (grupos, ajustes) lo evita. Chatboo hereda estos fallos y añade dos
críticos propios, sin reproducir (n.º 54 y 55); su bloqueo específico se decide en D33.

**Opciones:**
1. **Bloquear todo despliegue**, también el VPS de pruebas con usuarios reales o de portal, hasta
   recibir una versión corregida y repetir las pruebas A-D. — *Impacto:* no se puede usar la IA
   hasta entonces; ningún usuario queda expuesto a los críticos.
2. **Bloquear producción y permitir el VPS de pruebas**. — *Impacto:* se valida el funcionamiento
   con datos reales, pero en ese VPS cualquier usuario (y cualquier portal) puede hacerse
   administrador de esa base de datos y de sus datos.
3. **No bloquear.** — *Impacto:* va contra la conclusión técnica del análisis; la escalada a
   administrador queda abierta en producción.

**Riesgos relacionados:** n.º 1, 2, 3, 4, 5, 6, 7, 54, 55.

Decisión: ____ / Fecha: ____

### D33 — ¿Se bloquea Chatboo hasta que el fabricante aísle las conversaciones de cada usuario? — **BLOQUEANTE si se instala Chatboo**

**Contexto:** Chatboo no tiene reglas de registro: cualquier usuario interno, tenga o no clave
MCP, puede leer, modificar y borrar por RPC las conversaciones, los adjuntos (con su enlace de
descarga) y los trabajos en curso de cualquier otro usuario, también de un administrador.
Escribiendo en la conversación de otro puede dejar código que se ejecuta en su navegador cuando
abre Chatboo; con una víctima administradora equivale a hacerse administrador. También puede
alterar lo que la IA reutiliza en el siguiente turno de la víctima o lanzar turnos sobre su
conversación. Ningún grupo ni ajuste lo evita. Amplía D1.

**Fase 2 (2026-10-09), F29: CONFIRMADO.** Un interno sin grupos de IA ni clave MCP leyó,
modificó y borró por RPC la conversación de otro usuario. Un usuario de portal no accede (lo
frena el ACL de usuario interno). Siguen sin probar los trabajos en curso y los adjuntos, así
como el código plantado (F30-F32).

**Opciones:**
1. **Bloquear Chatboo**, también en el VPS de pruebas con usuarios reales, hasta recibir una
   versión con reglas de registro y saneado, y repetir F29-F32. — *Impacto:* sin chat;
   `pns_ai_mcp` sigue sujeto a D1.
2. **Permitirlo solo en el VPS de pruebas con pocos usuarios de confianza técnica.** — *Impacto:*
   cualquiera de ellos puede leer o manipular las conversaciones de los demás y atacar a un
   administrador que use el chat.
3. **No bloquear.** — *Impacto:* fuga de conversaciones entre todos los internos y escalada a
   administrador abierta en producción.

**Riesgos relacionados:** n.º 54, 55, 56, 57, 58.

Decisión: ____ / Fecha: ____

### D18 — ¿Qué otros módulos `pns_*` con conocimiento de IA se instalarán?

**Contexto:** `pns_ai_mcp` es infraestructura: el chat lo aporta `pns_ai_chatboo`, y hay otros
(geo, ACL, `presentation_grids`). Cada uno añade skills y contextos. El análisis de código de
Chatboo ya está hecho (25 riesgos nuevos, n.º 54-78) y agrava varios de `pns_ai_mcp`.

**Fase 2 (2026-10-09):** Chatboo **se instala sin errores** (F19; solo dos avisos cosméticos de
etiquetas duplicadas en `ai.agent`, que vienen de `pns_ai_mcp`). **Descartado** el riesgo de
que Odoo no arranque con `hr` y Chatboo (F45). **Confirmada** la falta de aislamiento entre
conversaciones (F29), lo que mantiene la opción 2 sujeta a D33.

**Opciones:**
1. **Solo `pns_base` + `pns_ai_mcp`.** — *Impacto:* sin chat para el usuario final; solo uso por
   cliente MCP externo (D20).
2. **Además `pns_ai_chatboo`.** — *Impacto:* añade los críticos n.º 54 y 55 (código plantado en
   conversaciones ajenas y confirmación de operaciones sin el usuario), conversaciones legibles
   por cualquier interno (n.º 56), el XSS del chat (n.º 15, 61), la salida de datos por imágenes
   externas (n.º 60), exportaciones que se suben solas (n.º 21, 66) y 7 librerías JS más (n.º 27,
   73). Exige decidir antes D33, D29 y D46.
3. **Además geo, ACL o `presentation_grids`.** — *Impacto:* más skills de fábrica expuestas al
   borrado de la prueba C (n.º 11; con Chatboo ya son 11 skills) y más conocimiento sincronizado
   en cada arranque (n.º 34).

**Riesgos relacionados:** n.º 11, 15, 21, 27, 34, 54-61, 66, 73.

Decisión: ____ / Fecha: ____

### D17 — ¿Se han editado a mano contextos de fábrica en la base de datos del cliente?

**Contexto:** en cada cambio de versión el módulo sobrescribe y reactiva los contextos de fábrica
que haya editado el administrador. Es información que debe aportar el cliente. Con Chatboo ocurre
lo mismo con sus 3 contextos y 11 skills de fábrica (ver D38).

**Opciones:**
1. **Sí.** — *Impacto:* esas ediciones se perderán en la próxima actualización; hay que
   localizarlas y guardarlas antes.
2. **No.** — *Impacto:* ninguno.

**Riesgos relacionados:** n.º 34.

Decisión: ____ / Fecha: ____

### D38 — ¿Deben conservarse los cambios de un administrador en los contextos y skills de fábrica de Chatboo?

**Contexto:** en cada actualización del módulo Chatboo reimporta con sobrescritura sus 3 contextos
y sus 11 skills de fábrica, y las reactiva. Cualquier ajuste hecho desde la interfaz (texto,
parámetros, desactivar una skill) se pierde. Enlaza con D17 y con D36.

**Opciones:**
1. **Aceptar la sobrescritura** y hacer los cambios como skills o contextos propios. —
   *Impacto:* no se puede desactivar de forma duradera una skill de fábrica.
2. **Pedir al fabricante que respete las ediciones** (o que permita desactivarlas). — *Impacto:*
   depende de una versión nueva.

**Riesgos relacionados:** n.º 34, 67.

Decisión: ____ / Fecha: ____

### D19 — ¿Qué idiomas tienen los usuarios?

**Contexto:** el prompt se guarda en una caché por agente e idioma que se recompila a menudo, y
probablemente el glosario en español no llega a la parte fija del prompt.

**Opciones:**
1. **Solo español.** — *Impacto:* una caché por agente; sigue la duda del glosario (F19).
2. **Varios idiomas.** — *Impacto:* una caché por idioma y más recompilaciones.

**Riesgos relacionados:** n.º 47.

Decisión: ____ / Fecha: ____

### D20 — ¿Qué cliente MCP externo se usará?

**Contexto:** el servidor MCP permite que herramientas externas consulten Odoo con la clave de
cada usuario. Necesita HTTPS, una sola base de datos o `dbfilter` y, con varios workers, solo
POST `/mcp` (sin SSE).

**Opciones:**
1. **Claude Desktop** (con `mcp-remote`).
2. **Claude Code.**
3. **Cursor** u otro.

*Impacto común:* cada usuario con clave MCP obtiene el esquema de cualquier modelo y el nombre de
la base de datos (D22); las sesiones antiguas siguen activas con una clave revocada (n.º 13).

**Riesgos relacionados:** n.º 13, 37, 40, 43.

Decisión: ____ / Fecha: ____

### D23 — ¿Hay módulos del cliente con acciones de ventana sobre asistentes `pns_ai_mcp.*`?

**Contexto:** la herramienta `clean_system` borra acciones de ventana de esos asistentes y hoy se
puede ejecutar sin ser AI Writer.

**Opciones:**
1. **Sí, hay.** — *Impacto:* `clean_system` podría borrarlas.
2. **No hay.** — *Impacto:* ninguno.

**Riesgos relacionados:** n.º 22.

Decisión: ____ / Fecha: ____

### D26 — ¿Cómo se confirmarán las operaciones supervisadas: con el aviso del chat o con el botón de Autorizaciones?

**Contexto:** las escrituras que propone la IA se confirman con un aviso emergente en el chat
(lo puede confirmar el dueño o cualquier AI Administrator) o desde el menú de Autorizaciones.
Ninguno de los dos caminos evita la manipulación de la prueba D. En Chatboo, la espera de 5
segundos antes de confirmar un borrado es solo visual, y cualquier código inyectado en el chat
puede confirmar y ejecutar la operación sin que el usuario pulse nada (n.º 55).

**Opciones:**
1. **Aviso del chat.** — *Impacto:* un AI Administrator puede confirmar operaciones ajenas; hay una
   carrera en la que la IA, al consultar el estado, ejecuta la operación con permisos de
   superusuario (n.º 5); un XSS en el chat confirma en nombre del usuario (n.º 55).
2. **Botón de Autorizaciones.** — *Impacto:* los botones comprueban el dueño; el resto de caminos
   (RPC y el XSS del chat) siguen abiertos (n.º 3, 4, 55).

**Riesgos relacionados:** n.º 3, 4, 5, 55.

Decisión: ____ / Fecha: ____

### D29 — ¿Se acepta el riesgo de XSS hasta que lo corrija el fabricante? — **BLOQUEANTE si se instala Chatboo**

**Contexto:** las respuestas de la IA y algunos datos (celdas de tablas, textos de skills) se
pintan en el navegador sin sanear. Un dato manipulado o una respuesta inducida podría ejecutar
código en la sesión del usuario que lee el chat. El análisis de Chatboo lo confirma leyendo su
código (sigue sin reproducir): casi todo lo que responde la IA llega a la pantalla como HTML sin
sanear, y se ejecuta ya durante la escritura de la respuesta, en cada recarga, al leerla en voz
alta y al exportarla. Ese código puede confirmar operaciones supervisadas en nombre del usuario
(n.º 55) y sacar datos sin clic con imágenes externas (n.º 60). Además, por la falta de aislamiento
de D33 basta escribir en la conversación de otro, sin pasar por la IA (n.º 54). Con Chatboo
instalado, aceptar el XSS equivale a aceptar que un usuario pueda actuar como el administrador que
use el chat; por eso pasa a ser bloqueante.

**Opciones:**
1. **Aceptarlo hasta la corrección.** — *Impacto:* cualquier usuario del chat queda expuesto,
   incluidos los administradores; una CSP en el proxy (D39) reduce la salida de datos, no el XSS.
2. **No aceptarlo.** — *Impacto:* no se usa el chat hasta que el fabricante sanee la salida.

**Riesgos relacionados:** n.º 15, 16, 54, 55, 60, 61.

Decisión: ____ / Fecha: ____

### D31 — ¿Se ejecutarán alguna vez los tests del módulo sobre una copia de producción?

**Contexto:** uno de los tests guarda de forma permanente una clave MCP predecible para el
administrador.

**Opciones:**
1. **No, solo en bases de datos de tests desechables.** — *Impacto:* ninguno.
2. **Sí.** — *Impacto:* el administrador de esa base de datos queda con una clave MCP conocida y
   activa.

**Riesgos relacionados:** n.º 38.

Decisión: ____ / Fecha: ____

---

## 2. Permisos y grupos

### D4 — ¿Quién tendrá AI Administrator y AI Writer en producción? — **BLOQUEANTE**

**Contexto:** un AI Writer puede escribir en el prompt que reciben todos los usuarios y crear
código que se ejecuta al guardarlo, con el que podría hacerse administrador. Un AI Administrator
puede ejecutar comandos del sistema operativo mediante servidores `stdio`. Esta decisión no
protege de las pruebas A-D (ver D1). En Chatboo, AI Writer permite además crear, borrar y
renombrar skills desde el chat, y AI Administrator guardar resultados en bruto; el acceso al
chat no depende de estos grupos sino de la clave MCP (D46).

**Opciones:**
1. **Solo administradores de Odoo de confianza técnica** reciben ambos grupos. — *Impacto:* los
   usuarios funcionales no pueden proponer escrituras ni crear skills.
2. **AI Writer también a usuarios funcionales.** — *Impacto:* cada Writer puede inyectar
   instrucciones en el prompt de todos (n.º 10), crear y activar skills con código (n.º 23) y,
   según el análisis, escalar a administrador al guardar una skill (n.º 6).

**Riesgos relacionados:** n.º 6, 9, 10, 23.

Decisión: ____ / Fecha: ____

### D46 — ¿A qué usuarios se generará la clave MCP para usar Chatboo? — **BLOQUEANTE si se instala Chatboo**

**Contexto:** Chatboo no tiene grupo propio: la clave MCP ("carnet") que se genera por usuario
abre a la vez el chat, las 11 skills de fábrica (censo de usuarios, información del sistema,
análisis financieros si tiene Contabilidad) y el servidor MCP para clientes externos (D20, D22).
La clave no protege los datos: sin ella también se leen las conversaciones ajenas (D33). Tras
generarla puede hacer falta recargar el navegador para ver el menú. Enlaza con D4.

**Opciones:**
1. **Solo un grupo piloto reducido.** — *Impacto:* menos exposición al XSS del chat y a las
   skills de fábrica, y menos coste de proveedor.
2. **Todos los usuarios internos que lo pidan.** — *Impacto:* máxima exposición a los riesgos
   del chat; cada usuario puede elegir proveedor (D34) y consultar el censo de usuarios (D36).

**Riesgos relacionados:** n.º 13, 40, 55, 58, 67, 77.

Decisión: ____ / Fecha: ____

### D5 — ¿Quién debe poder abrir AI Engine → Settings?

**Contexto:** hoy hace falta tener a la vez Ajustes (administrador de Odoo) y AI Administrator; el
menú se muestra a un AI Administrator aunque luego no pueda entrar.

**Opciones:**
1. **Mantenerlo así.** — *Impacto:* solo administradores de Odoo con el grupo de IA configuran;
   menú visible pero inaccesible para el resto de AI Administrators.
2. **Pedir al fabricante que baste AI Administrator.** — *Impacto:* más personas pueden cambiar la
   política de URL y otros ajustes globales.

**Riesgos relacionados:** n.º 49.

Decisión: ____ / Fecha: ____

### D22 — ¿Se expone a todos los usuarios con clave MCP el esquema de modelos y la información del sistema?

**Contexto:** por MCP, cualquier usuario con clave puede ver la estructura de cualquier modelo
(aunque no pueda leerlo) y el nombre de la base de datos, la URL y las versiones.

**Opciones:**
1. **Aceptarlo.** — *Impacto:* información técnica de la instalación al alcance de cualquier
   usuario con clave.
2. **Pedir al fabricante que lo restrinja.** — *Impacto:* dependemos de una versión nueva.

**Riesgos relacionados:** n.º 40.

Decisión: ____ / Fecha: ____

### D24 — ¿Qué política de acceso a URL tendrá el cliente?

**Contexto:** la IA puede descargar páginas web. Por defecto solo de una lista blanca; con la
política abierta, cualquier dirección se acepta sin humano y se añade sola a la lista. No hay
protección para direcciones internas (el propio servidor, la base de datos, la red local). La
lista blanca solo controla lo que descarga el servidor: no protege lo que pide el navegador al
pintar una respuesta de Chatboo con imágenes externas (n.º 60, ver D39).

**Opciones:**
1. **`whitelist_only` (por defecto).** — *Impacto:* solo dominios aprobados; aun así una
   redirección desde un dominio permitido puede llevar a una dirección interna.
2. **`open`.** — *Impacto:* acceso sin humano a cualquier URL, incluidas las internas; un texto
   malicioso leído por la IA puede provocarlo.

**Riesgos relacionados:** n.º 16, 17, 60.

Decisión: ____ / Fecha: ____

### D25 — ¿Habrá servidores externos marcados como "de confianza" (`trusted`)?

**Contexto:** las llamadas de la IA a un servidor de confianza se ejecutan sin confirmación humana,
incluidas las que modifican datos en ese servicio.

**Opciones:**
1. **Sí.** — *Impacto:* llamadas sin humano, inducibles por texto malicioso; si el proveedor de IA
   falla a mitad de turno, la llamada puede repetirse.
2. **No.** — *Impacto:* cada llamada externa la confirma una persona.

**Riesgos relacionados:** n.º 16, 25.

Decisión: ____ / Fecha: ____

### D27 — Skills con código: ¿quién puede crearlas y activarlas, y con qué revisión?

**Contexto:** un AI Writer crea y activa skills con código Python. Al guardarlas, el código se
ejecuta sin modo de solo lectura. Las capturadas desde el chat y las importadas por ZIP quedan
activas sin revisión.

**Opciones:**
1. **Mantener el comportamiento actual.** — *Impacto:* un Writer puede ejecutar código con efectos
   permanentes al guardar, y quien invoque la skill la ejecuta con sus propios permisos.
2. **Pedir que la captura desde el chat y la importación ZIP dejen la skill inactiva**
   (`active=False`) hasta que la revise un administrador. — *Impacto:* más trabajo de revisión;
   no evita la ejecución al guardar.
3. **Pedir además que la ejecución de prueba al guardar sea de solo lectura.** — *Impacto:* cierra
   la escalada al guardar; depende del fabricante.

**Riesgos relacionados:** n.º 6, 23.

Decisión: ____ / Fecha: ____

### D36 — ¿Se limita quién puede ejecutar las skills de usuarios y sistema de Chatboo? ¿Se mantiene la previsión meteorológica?

**Contexto:** cualquier usuario con clave MCP puede ejecutar `users-all` (todos los usuarios,
incluidos los archivados, con su último acceso), `users-logged` (quién está conectado) y
`sys-info` (nombre de la base de datos, URL, versiones, número de usuarios y módulos). Son datos
que un interno podría leer en parte, pero aquí van agregados y al proveedor de IA. La skill
`forecast` envía la ciudad de la empresa a Open-Meteo (dominio ya incluido en la lista blanca).
Las skills se reactivan en cada actualización (D38). Enlaza con D14.

**Opciones:**
1. **Pedir al fabricante que estas skills exijan un grupo** (p. ej. administrador). — *Impacto:*
   depende de una versión nueva.
2. **Aceptarlas para todos los usuarios con clave.** — *Impacto:* datos de usuarios y de la
   instalación al alcance de cualquiera con chat.
3. **Quitar `open-meteo.com` de la lista blanca.** — *Impacto:* `forecast` deja de funcionar; no
   sale la ciudad de la empresa.

**Riesgos relacionados:** n.º 11, 67.

Decisión: ____ / Fecha: ____

---

## 3. Datos que salen hacia el proveedor de IA (RGPD)

### D10 — ¿Son aceptables los proveedores de IA externos y el envío de datos de negocio? — **BLOQUEANTE**

**Contexto:** cada respuesta de una consulta puede enviar al proveedor hasta unos 2 MB / 50 000
filas, y el registro abierto en pantalla se envía en cada turno. No hay filtro por modelo, campo
ni empresa. Si el proveedor principal falla, el de respaldo recibe lo mismo. Marcar un proveedor
como "on premise" solo cambia el coste mostrado. Además el módulo consulta fuentes públicas de
tipos de cambio. Chatboo envía también, en cada turno, la pantalla abierta (modelo, registro,
vista y URL) y el texto completo de los ficheros adjuntos (todas las hojas de un Excel).

**Opciones:**
1. **Proveedores externos aceptados.** — *Impacto:* datos personales y de negocio salen hacia el
   proveedor; requiere base legal y contrato de encargado del tratamiento.
2. **Solo proveedor local** (Ollama o Lemonade), **con toda la cadena de respaldo también local**.
   — *Impacto:* los datos no salen; hace falta hardware y un modelo local; si un respaldo es
   externo, recibe los mismos datos.
3. **Mixto** (local con respaldo externo). — *Impacto:* equivale a la opción 1 cada vez que el
   local falle.

*Sub-decisión:* ¿se aceptan las fuentes públicas de tipos de cambio? (ver D14).

**Riesgos relacionados:** n.º 18, 19, 16, 63.

Decisión: ____ / Fecha: ____

### D11 — ¿Qué proveedor, modelo y clave se configurarán?

**Contexto:** el módulo envía siempre parámetros que algunos modelos recientes rechazan; cuando
eso ocurre, pasa al proveedor de respaldo y el usuario ve un error con la dirección del servicio.

**Opciones:**
1. **Modelos Claude recientes.** — *Impacto:* `temperature` siempre enviada; imágenes en un formato
   que Anthropic no acepta.
2. **Modelos de razonamiento de OpenAI.** — *Impacto:* `max_tokens` en lugar de
   `max_completion_tokens`.
3. **Azure OpenAI.** — *Impacto:* sin información específica en el análisis; probar en laboratorio.
4. **Proveedor local** (ver D10).

**Riesgos relacionados:** n.º 44.

Decisión: ____ / Fecha: ____

### D12 — ¿Hace falta un tope de gasto o restringir la elección de proveedor?

**Contexto:** no hay tope de gasto, de tokens ni de turnos; algunas llamadas no se contabilizan, y
el usuario puede elegir proveedor desde la interfaz. En Chatboo el navegador puede pedir
**cualquier** proveedor dado de alta, no solo los del agente del chat (D34), y no hay tope de
tamaño para imágenes ni para el texto extraído de los adjuntos.

**Opciones:**
1. **Sí.** — *Impacto:* el módulo no lo trae; hay que pedirlo al fabricante o controlarlo en la
   cuenta del proveedor.
2. **No.** — *Impacto:* coste sin límite y contabilidad incompleta.

**Riesgos relacionados:** n.º 31, 62, 63.

Decisión: ____ / Fecha: ____

### D13 — ¿Qué retención se quiere para el registro de actividad, las cachés y las exportaciones del chat?

**Contexto:** `ai.log` guarda preguntas, respuestas, código y resultados sin borrado automático, y
el AI Administrator puede modificar sus filas. Las exportaciones del chat se descargan por URL con
token sin iniciar sesión y solo se borran al borrar la sesión de chat. Chatboo solo purga las
conversaciones de quien vuelve a usarlo, así que las de usuarios inactivos o archivados no se
borran nunca (detalle en D35).

**Opciones:**
1. **Definir un plazo de retención.** — *Impacto:* el módulo no lo trae; hay que implementarlo o
   pedirlo.
2. **Conservar indefinidamente.** — *Impacto:* acumulación de datos personales y de negocio;
   exportaciones accesibles por enlace mientras exista la sesión.

*Sub-decisión:* ¿es aceptable que el AI Administrator modifique filas del registro?

**Riesgos relacionados:** n.º 21, 32, 64.

Decisión: ____ / Fecha: ____

### D35 — Retención de Chatboo: ¿hace falta un cron que purgue conversaciones, adjuntos y trabajos?

**Contexto:** las conversaciones se purgan a los 30 días (parámetro
`pns_ai_chatboo.history_retention_days`), pero solo cuando el propio usuario vuelve a usar
Chatboo. Las de usuarios inactivos o archivados conservan para siempre mensajes, datos de
consultas y adjuntos con enlace de descarga que no caduca. Los trabajos en curso guardan imágenes
y ficheros completos durante 72 horas. Todo ello es legible por cualquier interno mientras no se
corrija D33. Amplía D13.

**Opciones:**
1. **Pedir al fabricante un cron de retención** y, mientras, que un administrador purgue
   periódicamente las conversaciones antiguas. — *Impacto:* trabajo manual hasta la corrección.
2. **Aceptarlo.** — *Impacto:* acumulación de datos personales y de negocio accesibles por enlace
   y por cualquier interno.

*Sub-decisión:* plazo de retención (30 días por defecto).

**Riesgos relacionados:** n.º 21, 56, 64.

Decisión: ____ / Fecha: ____

### D41 — ¿Se acepta que el texto de las respuestas pueda salir hacia servicios de voz de Google o Microsoft?

**Contexto:** la lectura en voz alta de Chatboo usa las voces del navegador y no da preferencia a
las locales. En Chrome y Edge algunas voces funcionan en servidores de Google o Microsoft; si el
navegador elige una de ellas, el texto de la respuesta (con datos de negocio) sale hacia ese
servicio. Cada usuario la activa desde el chat. Pendiente comprobar qué voces usan los
navegadores del cliente (F51, D40).

**Opciones:**
1. **Aceptarlo** avisando a los usuarios. — *Impacto:* posible transferencia de datos a un tercero
   sin contrato de encargado.
2. **Pedir al fabricante que use solo voces locales o permita desactivar la función**, e indicar
   a los usuarios que no la activen mientras tanto. — *Impacto:* depende de una versión nueva y
   de que los usuarios sigan la indicación.

**Riesgos relacionados:** n.º 65.

Decisión: ____ / Fecha: ____

### D42 — ¿Es aceptable que Chatboo suba documentos a Odoo sin acción del usuario?

**Contexto:** algunos documentos de una respuesta (PDF, Word, HTML) se generan en el navegador y
se suben solos a Odoo como adjuntos de la conversación, con enlace de descarga. El Word incluye el
HTML de la respuesta tal cual (al abrirlo en Windows puede pedir recursos remotos) y las
exportaciones pueden incluir columnas de datos que no se veían en pantalla.

**Opciones:**
1. **Aceptarlo.** — *Impacto:* más adjuntos con datos de negocio sujetos a D33 y D35.
2. **Pedir al fabricante que la subida sea a petición del usuario.** — *Impacto:* depende de una
   versión nueva.

**Riesgos relacionados:** n.º 21, 66.

Decisión: ____ / Fecha: ____

---

## 4. Secretos y copias

### D6 — Servidores externos: ¿se acepta que cualquier interno lea sus credenciales?

**Contexto:** los tokens y variables de entorno de los servidores externos los puede leer
cualquier usuario interno. Los servidores de ejemplo incluyen `cdmon` y `sesame` (fichajes). Las
respuestas cacheadas de un usuario se sirven a otro durante 10 minutos.

**Fase 2 (2026-10-09), F8: CONFIRMADO.** Un interno sin grupos de IA leyó en claro el token,
las variables de entorno y la configuración de un servidor de prueba, tuvo acceso a ambas
cachés y leyó las elecciones de otro usuario. Que la caché sirva a un usuario lo obtenido por
otro sigue verificado solo en el código: no se probó porque no hay servidores reales.

**Opciones:**
1. **No dar de alta servidores externos** hasta la corrección. — *Impacto:* sin integraciones.
2. **Darlos de alta aceptando la exposición.** — *Impacto:* cualquier interno puede llevarse las
   credenciales; si `sesame` se usa, datos de fichajes compartidos entre usuarios por la caché.
3. **Usar credenciales por usuario.** — *Impacto:* también se exponen y la caché las mezcla.

**Riesgos relacionados:** n.º 8, 14.

Decisión: ____ / Fecha: ____

### D7 — ¿Se usarán servidores `stdio` u OpenAPI con `base_url` vacío?

**Contexto:** un servidor `stdio` ejecuta un comando libre en el servidor con todo el entorno de
Odoo; un OpenAPI sin `base_url` deja que la especificación remota elija a dónde enviar la
credencial.

**Opciones:**
1. **Sí.** — *Impacto:* AI Administrator equivale a acceso al sistema operativo; credenciales
   enviadas a un host que decide un tercero.
2. **No: dejar inactivos los tres servidores de ejemplo y documentar `stdio` como prohibido.** —
   *Impacto:* ninguno funcional si no se necesitan.

**Riesgos relacionados:** n.º 9, 17.

Decisión: ____ / Fecha: ____

### D8 (+ PB-6) — ¿Se usarán las copias de configuración? ¿Quién las genera y custodia?

**Contexto:** la copia completa lleva siempre las claves; la opción "sin secretos" no las quita
todas; los adjuntos generados no se borran nunca (también los de `pns_base`). Importar una copia
sobrescribe la configuración y puede abrir la política de URL.

**Opciones:**
1. **No usarlas.** — *Impacto:* la configuración se rehace a mano.
2. **Usarlas, solo por una persona designada**, borrando los adjuntos después. — *Impacto:* las
   claves quedan en un fichero que hay que custodiar.

**Riesgos relacionados:** n.º 20; pns_base 6.

Decisión: ____ / Fecha: ____

---

## 5. Infraestructura del VPS

### D3 (+ PB-3) — Imagen y versión de Python — **BLOQUEANTE**

**Contexto:** sin `openpyxl`, `httpx` y `pydantic` Odoo no deja instalar el módulo; las dos
últimas no se usan en el código. `pns_base` no carga con Python 3.6, y con 3.7 algunas funciones
del módulo (zonas horarias, recetas de código) no están disponibles.

**Opciones:**
1. **Añadir las tres librerías al Dockerfile del cliente.** — *Impacto:* se instala ya; dos
   librerías innecesarias en la imagen.
2. **Pedir al fabricante que quite `httpx` y `pydantic`** y añadir solo `openpyxl`. —
   *Impacto:* imagen más limpia; depende del fabricante.

*Información necesaria:* versión exacta de Python del VPS (3.6 impide cargar `pns_base`).

**Riesgos relacionados:** n.º 28, 36; pns_base 8.

Decisión: ____ / Fecha: ____

### D14 — ¿Hay salida a Internet desde el servidor?

**Contexto:** sin Internet, cada comprobación de estado espera hasta 8 segundos por las fuentes de
tipos de cambio. Chatboo hace esa comprobación en cada carga del backend; si es el mismo chequeo,
sin Internet cada carga podría tardar hasta 8 segundos más (F50). Su skill `forecast` necesita
salir a Open-Meteo (D36).

**Opciones:**
1. **Sí.** — *Impacto:* funcionan proveedores externos, fuentes de tipos de cambio y `forecast`
   (ver D10, D36).
2. **No: desactivar las fuentes de tipos de cambio.** — *Impacto:* sin esperas; solo proveedor
   local; `forecast` no funciona.

**Riesgos relacionados:** n.º 48, 67, 73.

Decisión: ____ / Fecha: ____

### D15 — Configuración de Odoo en el VPS (workers, límites, proxy, HTTPS)

**Contexto:** cada conversación del chat ocupa un worker hasta 10 minutos; con varios workers el
límite de tiempo puede matar el proceso a mitad de turno; el transporte SSE del servidor MCP no
funciona con varios workers. El botón de copiar la clave MCP necesita HTTPS. Chatboo responde en
directo (streaming): con varios workers necesita `limit_time_real` de al menos 600 s, y el proxy
sin *buffering* y con un tiempo de lectura alto; si un turno supera el límite, queda como
"respuesta incompleta" (F44).

**Opciones:**
1. **Varios workers (`workers > 0`) y solo POST `/mcp` (sin SSE).** — *Impacto:* hay que
   dimensionar `workers` y `limit_time_real` para turnos largos.
2. **Multihilo (`workers = 0`).** — *Impacto:* el turno escapa del límite de tiempo.

*Además:* `limit_time_cpu`, `limit_memory_hard`, `limit_request`, proxy, `dbfilter`, HTTPS y si
el código que genera la IA tendrá límites de CPU/memoria propios o los del worker.

**Riesgos relacionados:** n.º 35, 43.

Decisión: ____ / Fecha: ____

### D16 — ¿La carpeta de módulos está montada en solo lectura?

**Contexto:** la sincronización del conocimiento de fábrica puede borrar carpetas
`ai/contexts/domain/self/` en disco.

**Opciones:**
1. **Sí.** — *Impacto:* el borrado no ocurre.
2. **No.** — *Impacto:* el módulo puede borrar carpetas del código desplegado.

**Riesgos relacionados:** n.º 34.

Decisión: ____ / Fecha: ____

### D21 — ¿Se acepta que cualquier web cree filas en el registro de actividad?

**Contexto:** el servidor MCP acepta peticiones de cualquier origen y registra las no
autenticadas; una web abierta en el navegador de un usuario puede llenar `ai.log`.

**Opciones:**
1. **Aceptarlo.** — *Impacto:* crecimiento del registro y ruido.
2. **Filtrar `Origin` o limitar `/mcp` en el proxy.** — *Impacto:* configuración adicional del
   proxy.

**Riesgos relacionados:** n.º 30.

Decisión: ____ / Fecha: ____

### D30 — ¿Qué tope tendrá la caché de datos de cada turno (`pns_ai_mcp.dataset_cache_max_bytes`)?

**Contexto:** por defecto 8 MB por turno; con 0 no hay límite, con consumo de memoria y CPU del
worker.

**Opciones:**
1. **Mantener 8 MB.** — *Impacto:* consumo acotado.
2. **0 (sin límite).** — *Impacto:* turnos con varios MB en memoria y CPU.

**Riesgos relacionados:** n.º 35.

Decisión: ____ / Fecha: ____

### D39 — ¿Se configura una política de seguridad de contenidos (CSP) en el proxy para frenar la salida de datos por imágenes?

**Contexto:** si una respuesta del chat incluye una imagen de un dominio externo, el navegador la
pide sin que el usuario haga clic, y la dirección puede llevar datos de la pantalla. Basta que la
IA lo haga inducida por un texto malicioso leído en un registro o en un documento. Ni Odoo 14 ni
Chatboo ponen una CSP en `/web`, y la lista blanca de URL solo controla al servidor (D24).

**Opciones:**
1. **Añadir en el proxy del cliente una CSP que limite `img-src`** al propio dominio (y `data:` /
   `blob:`). — *Impacto:* corta este canal; hay que probar que no rompe otros módulos que muestren
   imágenes externas (mapas, web, correo).
2. **No añadirla.** — *Impacto:* canal abierto hasta que el fabricante filtre las imágenes.

**Riesgos relacionados:** n.º 17, 60.

Decisión: ____ / Fecha: ____

### D40 — ¿Qué navegadores (y versiones) usan los usuarios del cliente?

**Contexto:** Chatboo añade al JavaScript común del backend sintaxis reciente sin adaptar, y
estilos que solo funcionan en navegadores actuales; según el análisis (sin comprobar), un
navegador antiguo podría tener problemas para cargar el backend. La lectura en voz alta depende
de las voces de cada navegador (D41). Es información que debe aportar el cliente.

**Opciones:**
1. **Chrome, Edge o Firefox actuales.** — *Impacto:* ninguno conocido; queda D41.
2. **Navegadores antiguos o variados.** — *Impacto:* probarlos antes en el laboratorio (F48).

**Riesgos relacionados:** n.º 65, 74.

Decisión: ____ / Fecha: ____

---

## 6. Comunicación con el fabricante

### D2 (+ PB-9) — ¿Qué se comunica al fabricante, con qué prioridad y quién lo envía?

**Contexto:** el código no se modifica; la corrección solo puede venir de PATANEGRA Soft. Hay un
borrador de informe técnico en [informe_fabricante_pns_ai.md](informe_fabricante_pns_ai.md), ya
ampliado con los hallazgos de `pns_ai_chatboo` (PNS-53 en adelante) y con los resultados de la
fase 2 (reproducidos PNS-08, PNS-14, PNS-55 y §7.4; PNS-69 rebajado; nuevo PNS-78). Tras la
revisión de exactitud del 2026-10-09, §7.2 figura como verificado en código (no reproducido),
PNS-22 baja de Alta a Media y se añaden PNS-79 (Baja) y PNS-80 (Alta), ambos pendientes de
prueba. Totales: 9 críticos, 26 altos, 25 medios y 20 bajos (80 hallazgos).

**Opciones:**
1. **Solo los fallos confirmados A-D y los críticos.** — *Impacto:* corrección más rápida de lo
   urgente; el resto queda sin comunicar.
2. **El informe completo** (críticos, altos y defectos de código medios y bajos, más
   compatibilidad con Odoo 14). — *Impacto:* más trabajo para el fabricante; cubre la lista
   mínima del §6.2 (D2).
3. **Mantener un parche local en lugar de informar** (PB-9). — *Impacto:* contradice la regla de
   no modificar código de terceros; hay que mantenerlo en cada actualización.

**Riesgos relacionados:** todos; en especial n.º 1-7.

Decisión: ____ / Fecha: ____

### D28 — ¿Se pide corregir `platform` en el sandbox y el anuncio de `zoneinfo` en el prompt?

**Contexto:** el código de la IA puede leer datos del sistema operativo del contenedor; el prompt
anuncia una función de zonas horarias que no existe en Python 3.7.

**Opciones:**
1. **Pedirlo.** — *Impacto:* ninguno para nosotros.
2. **Aceptarlo.** — *Impacto:* fugas menores de información del sistema y errores del código
   generado con fechas.

**Riesgos relacionados:** n.º 36, 52.

Decisión: ____ / Fecha: ____

### D32 — ¿Se pide actualizar jsPDF y SheetJS?

**Contexto:** se cargan en todo el backend versiones con vulnerabilidades conocidas; `pns_ai_mcp`
no las usa. El análisis de Chatboo precisa: Chatboo carga otra copia de las mismas versiones;
usa jsPDF con datos que pueden venir de la respuesta (las vulnerabilidades de jsPDF sí le
aplican), pero no usa SheetJS. Showdown se trata en D44.

**Opciones:**
1. **Pedirlo.** — *Impacto:* ninguno para nosotros.
2. **Aceptarlo.** — *Impacto:* SheetJS, riesgo bajo mientras nadie lo use; jsPDF, posible
   bloqueo del navegador al exportar una respuesta manipulada.

**Riesgos relacionados:** n.º 27, 73.

Decisión: ____ / Fecha: ____

### D34 — ¿Se pide al fabricante que el chat solo use el proveedor y el agente configurados?

**Contexto:** Chatboo acepta del navegador el proveedor (cualquiera dado de alta, no solo la
cadena del agente del chat) y el agente (cualquiera activo). También acepta un historial de la
conversación enviado por el navegador, que el usuario puede inventar. Enlaza con D12 y D10.

**Opciones:**
1. **Pedirlo.** — *Impacto:* ninguno para nosotros; depende de una versión nueva.
2. **Aceptarlo.** — *Impacto:* un usuario con clave puede usar un proveedor externo aunque el chat
   esté configurado con uno local (D10), con su coste (D12), y fabricar turnos previos.

**Riesgos relacionados:** n.º 31, 62.

Decisión: ____ / Fecha: ____

### D37 — ¿Es intencionado que las bases de datos actualizadas y las nuevas tengan una receta distinta del agente Chatboo? (pregunta al fabricante)

**Contexto:** en una base de datos que viene de versiones anteriores, el agente Chatboo incluye el
contexto `acl_security` en sus contextos por defecto; en una instalación nueva, no. El chat
podría comportarse distinto en el VPS de pruebas y en producción si una se instaló de cero y la
otra se actualizó.

**Opciones:**
1. **Preguntarlo al fabricante** e igualar la configuración del agente en ambas. — *Impacto:*
   ninguno.
2. **Ignorarlo.** — *Impacto:* diferencias de comportamiento difíciles de explicar entre entornos.

**Riesgos relacionados:** n.º 77.

Decisión: ____ / Fecha: ____

### D44 — ¿Se pide al fabricante un plan para showdown y jsPDF?

**Contexto:** Chatboo convierte las respuestas con showdown 2.1.0, que no sanea por diseño, tiene
una vulnerabilidad de XSS publicada sin versión corregida y otra de denegación de servicio
(CVE-2024-1899), y parece sin mantenimiento. jsPDF 2.5.1 tiene vulnerabilidades de denegación de
servicio con imágenes, corregidas en 3.0.2. Amplía D32.

**Opciones:**
1. **Pedir sustituir showdown por un convertidor mantenido seguido de un saneador**, y actualizar
   jsPDF a 3.0.2 o superior. — *Impacto:* ninguno para nosotros; depende de una versión nueva.
2. **Aceptarlo.** — *Impacto:* se mantiene la vía de XSS de D29 aunque el resto se corrija.

**Riesgos relacionados:** n.º 27, 61.

Decisión: ____ / Fecha: ____

### D45 — Código muerto o heredado del cliente web de Chatboo: ¿se comunica o se documenta como inocuo?

**Contexto:** el JavaScript de Chatboo incluye funciones sin uso, llamadas a servicios que no
existen en Odoo 14 (con el error capturado) y textos que muestran "#undefined". No tiene impacto de
seguridad conocido, salvo un enlace que abre ventanas sin `noopener`.

**Opciones:**
1. **Comunicarlo** (ya figura en el borrador del informe). — *Impacto:* ninguno.
2. **Documentarlo como inocuo** y no comunicarlo. — *Impacto:* ninguno a corto plazo.

**Riesgos relacionados:** n.º 75.

Decisión: ____ / Fecha: ____

---

## 7. Efectos de pns_base (y de pns_ai_mcp y Chatboo) sobre módulos que no son PNS

### D9 — ¿Se aceptan los parches globales de `pns_ai_mcp` sobre Odoo? — **BLOQUEANTE**

**Contexto:** el módulo cambia cómo Odoo atiende todas las peticiones (`Root.get_request`),
modifica el borrado de opciones de selección para todos los modelos y añade parches de interfaz
en todo el backend. Hay que saber si algún módulo del cliente usa rutas bajo `/mcp`. Chatboo
añade una capa flotante y estilos globales, escuchas en la barra de navegación y en las ventanas
de chat de Discuss, y redefine un atributo de `res.users` de forma que, según el orden de carga
de los módulos, Odoo podría no arrancar (pendiente probar con `hr`, F45).

**Fase 2 (2026-10-09), F45: DESCARTADO.** Con `hr` y Chatboo instalados, Odoo arranca y carga
el registro sin errores ni avisos. El riesgo n.º 70 queda como defecto de código de baja
gravedad y deja de pesar en esta decisión. Los parches globales de `pns_ai_mcp` (riesgo n.º 33)
siguen igual.

**Opciones:**
1. **Aceptarlos.** — *Impacto:* cualquier fallo de estos parches afecta a módulos que no son PNS.
2. **No aceptarlos.** — *Impacto:* no se puede instalar el módulo.

**Riesgos relacionados:** n.º 33, 70.

Decisión: ____ / Fecha: ____

### D43 — ¿Se acepta que Chatboo cargue sus 7 librerías JavaScript en todo el backend?

**Contexto:** todos los usuarios internos, usen o no el chat, descargan en cada carga del backend
7 librerías (3 repetidas con `pns_ai_mcp` y una, SheetJS, sin uso). Su librería de gráficos choca
con la que Odoo 14 carga en las vistas gráfico y en el tablero de Contabilidad: tras abrir una de
ellas, los gráficos del chat se pintan mal hasta recargar la página (las vistas de Odoo no se
rompen). Cada carga del backend, además, llama a la comprobación de estado (D14).

**Opciones:**
1. **Aceptarlo.** — *Impacto:* más peso en cada carga y gráficos del chat inestables.
2. **Pedir al fabricante que cargue las librerías solo al abrir el chat y sin duplicados.** —
   *Impacto:* depende de una versión nueva.

**Riesgos relacionados:** n.º 33, 71, 73.

Decisión: ____ / Fecha: ____

### PB-1 — ¿Se acepta que `pns_base` reescriba la web y la descripción de todos los módulos? — **BLOQUEANTE**

**Contexto:** en cada arranque cambia el enlace "Learn More" de todos los módulos con
documentación (OCA, core y Seges) y muestra su documentación en un marco sin sanear, con la
sesión del administrador que abre la ficha.

**Opciones:**
1. **Aceptarlo.** — *Impacto:* cambio visible en Aplicaciones; un módulo con JavaScript en su
   documentación se ejecutaría con permisos del administrador.
2. **No aceptarlo.** — *Impacto:* no se puede instalar ningún módulo PNS (`pns_base` es dependencia
   obligatoria).

**Riesgos relacionados:** pns_base 1 y 4.

Decisión: ____ / Fecha: ____

### PB-2 — ¿Se acepta el cambio global de validación de formularios y listas? — **BLOQUEANTE**

**Contexto:** `pns_base` cambia el aviso de campos obligatorios vacíos en todos los formularios y
listas de edición múltiple, y los resalta en otro color. Puede chocar con módulos `web_*` de OCA
del cliente.

**Opciones:**
1. **Aceptarlo** (tras comprobar que no hay módulos `web_*` que sobrescriban `_saveMultipleRecords`
   u `_onSetDirty`). — *Impacto:* cambio visible para todos los usuarios.
2. **No aceptarlo.** — *Impacto:* no se puede instalar ningún módulo PNS.

**Riesgos relacionados:** pns_base 1 y 7.

Decisión: ____ / Fecha: ____

### PB-5 — ¿Hay módulos registrados en la base de datos sin código en el servidor?

**Contexto:** `pns_base` recorre todos los módulos en cada arranque y genera un aviso por cada uno
sin código. Información que debe aportar el cliente (se puede comprobar con `paridad`).

**Opciones:**
1. **Sí.** — *Impacto:* avisos en el log en cada arranque.
2. **No.** — *Impacto:* ninguno.

**Riesgos relacionados:** pns_base (compatibilidad §12.2).

Decisión: ____ / Fecha: ____

### PB-7 — ¿Se cargarán idiomas con "Sobrescribir" en producción?

**Contexto:** `pns_base` descarta en silencio las traducciones duplicadas de cualquier módulo al
cargar un idioma con sobrescritura (solo deja un aviso en el log).

**Opciones:**
1. **Sí, aceptando el descarte.** — *Impacto:* traducciones duplicadas perdidas sin error visible.
2. **No.** — *Impacto:* ninguno.

**Riesgos relacionados:** pns_base 2.

Decisión: ____ / Fecha: ____

### PB-8 — ¿Se acepta que cualquier interno cree resultados de exportación con HTML sin sanear?

**Contexto:** el asistente de exportación de `pns_base` admite HTML sin sanear y lo puede crear
cualquier usuario interno; podría enviar el enlace a otro usuario. Ningún módulo del repo lo usa
directamente.

**Opciones:**
1. **Aceptarlo** (riesgo bajo). — *Impacto:* posible HTML malicioso visto por otro usuario.
2. **Pedir al fabricante que lo sanee o lo restrinja.** — *Impacto:* depende de una versión nueva.

**Riesgos relacionados:** pns_base 5.

Decisión: ____ / Fecha: ____

---

## Anexo — Preguntas que se resolverán ejecutando en el laboratorio (F1-F51)

No requieren decisión: se responden con pruebas en el laboratorio local, con base de datos de
demostración y nunca con datos de producción (salvo F49, cuya copia de producción la decide el
usuario). Detalle de F1-F28 en el §6.1 del
[consolidado](../specs/analisis_pns_ai_mcp.md#61-se-resuelven-ejecutando-fase-2-solo-en-local-con-odoo-dev-14-e-imagen-de-laboratorio-nunca-con-datos-de-producción)
y de F29-F51 en el §6.1 del [consolidado de Chatboo](../specs/analisis_pns_ai_chatboo.md#6-preguntas-abiertas-unificadas).

| # | Pregunta (resumen) | Riesgo | Cómo se resuelve |
|---|---|---|---|
| F1 | `apply_module_update` con interno sin permisos y portal; desinstalar una dependencia | 2, 24 | Laboratorio |
| F2 | Resto de `apply_*`, `preview_*` y borrado de skills con portal | 2, 11 | **Resuelta (fase 2): CONFIRMADO.** El portal invoca `preview_user_add_group`, `preview_module_update` y `unlink_named_factory_skills` sin `AccessError`. Los `apply_*` no se invocaron con portal; quedan en F1. |
| F3 | Escalada con operación propia + `resolve_execute(confirmed_uid=…)` | 4 | Laboratorio |
| F4 | `get_safe_operation_status` ejecuta en superusuario y ve operaciones ajenas | 5 | Laboratorio |
| F5 | Persistencia desde el sandbox con `getattr` a `resolve_*` y similares | 7 | Laboratorio |
| F6 | Escalada de un Writer guardando una skill | 6 | Laboratorio |
| F7 | Lectura de secretos con `sudo()` desde el sandbox | 19 | Laboratorio |
| F8 | Lectura por un interno de tokens, cachés y elecciones ajenas | 8, 14 | **Resuelta (fase 2): CONFIRMADO.** Lee `auth_token`, `env_vars` y `config_json`, accede a ambas cachés y lee `ai.safe.choice` ajenas. |
| F9 | Prueba/descubrimiento de servidores y lista blanca por un interno | 9 | Laboratorio |
| F10 | `skip_hardcoded_restrictions` con un Writer; fuga por `discovery` | 10, 12 | Laboratorio |
| F11 | Clave MCP revocada + sesión antigua | 13 | Laboratorio |
| F12 | Contexto privado visible por MCP a otro usuario | 12 | Laboratorio |
| F13 | `clean_system` desde el chat sin AI Writer | 22 | Laboratorio |
| F14 | Doble ejecución tras failover | 25 | Laboratorio |
| F15 | XSS en chat, celdas base64 y `author_html` | 15 | Laboratorio |
| F16 | Inyección de fórmulas en Excel | 39 | Laboratorio |
| F17 | Fallo en Python 3.7 con parámetro de fecha | 36 | Laboratorio |
| F18 | Las migraciones no se ejecutan al actualizar | 29 | **Fase 2: NO CONCLUYENTE** (corrige un primer "CONFIRMADO"). No hubo ningún "Running migration" en el log, pero se instaló y actualizó con la misma versión (3.1.486), y así no se ejecuta ningún script. Evidencia: verificado en código (`migration.py`). Para reproducirlo: instalar una versión anterior (por ejemplo 3.1.483) y actualizar a 3.1.486. Laboratorio |
| F19 | Instalación limpia: hook, vistas, contextos, caché en español | 34, 47 | **Resuelta (fase 2): CONFIRMADO, instalación limpia** de Chatboo (0 bloqueantes; 3 contextos y 11 skills). Dos etiquetas duplicadas en `ai.agent` (PNS-78 del informe). |
| F20 | Cron de caché inactivo tras su primera ejecución | 45 | **Resuelta (fase 2): CONFIRMADO** (corrige un primer "no se reproduce"). Una sola ejecución del programador; queda con `numbercall=0` y `nextcall` congelado. |
| F21 | Usuario solo AI Administrator en Settings; grupos en la ficha | 49 | Laboratorio |
| F22 | Guardar Ajustes de otro módulo con opciones de IA en conflicto | 33 | Laboratorio |
| F23 | Ejecución de los tests del módulo | 51 | **Resuelta (fase 2): CONFIRMADO parcialmente.** 125 tests: 110 OK, 4 saltados, 11 con fallo o error. Dependen del entorno los de `product`, `comment` nulo y agente o proveedor sin configurar; no dependen los de AI Writer en `test_safe_plan_atomicity`. |
| F24 | `/mcp` con varias bases de datos y sin `dbfilter` | 43 | Laboratorio |
| F25 | Respuesta a `OPTIONS` de las rutas MCP | 30, 43 | Laboratorio |
| F26 | Turno más largo que `limit_time_real` con workers | 35 | Laboratorio |
| F27 | URL con token de descargas hacia el proveedor; usuario del motor al exportar | 21 | Laboratorio (trazado estático) |
| F28 | Análisis de `pns_ai_chatboo` y repos del cliente: **Chatboo ya analizado**; queda solo el uso de cabeceras extra hacia el proveedor (`extra_headers`) y los repos del cliente | 15, 21, 27 | Análisis de código |
| F29 | Dos internos: leer, modificar y borrar por RPC conversaciones y trabajos ajenos; descargar un adjunto de una conversación ajena | 56 | **Resuelta (fase 2): CONFIRMADO** para conversaciones (leer, modificar y borrar); el portal no accede. Trabajos y adjuntos no probados. |
| F30 | Interno sin clave MCP: crear un trabajo sobre una conversación ajena y lanzarlo por RPC; ¿se escribe en la de la víctima y se cobra? | 58 | Laboratorio |
| F31 | XSS almacenado entre usuarios escribiendo los mensajes de otro (también de un administrador) por RPC | 54 | Laboratorio |
| F32 | Inyección en el siguiente turno de la víctima modificando la última consulta y la skill activa de su conversación | 57 | Laboratorio |
| F33 | Turnos lanzados desde otra web con la sesión del usuario (`/chatboo/stream` sin CSRF) en Firefox y Safari | 59 | Laboratorio |
| F34 | Enlaces con esquema `javascript:` en la respuesta convertida por showdown, por navegador | 15, 61 | Laboratorio |
| F35 | Salida de datos sin clic con una imagen externa, durante la respuesta y al recargar | 60 | Laboratorio |
| F36 | ¿Comprueba el servidor algo más antes de confirmar una operación de riesgo alto? ¿Se confirma y ejecuta con un script sin interacción? | 55 | Laboratorio |
| F37 | ¿Puede `/chatboo/sessions/save` sustituir el historial interno de mensajes existentes? ¿Acepta el motor un historial inventado? | 62 | Laboratorio |
| F38 | ¿Controla la IA las claves de columna y los nombres de serie de los gráficos? ¿Salen columnas ocultas en PDF, Word y Excel? | 61, 66 | Laboratorio |
| F39 | Gráfico del chat tras abrir una vista gráfico o el tablero de Contabilidad sin recargar | 71 | Laboratorio |
| F40 | Usuario y tipo MIME del adjunto creado por `fulfill_export` (¿HTML servido como `text/html`?) | 66 | Laboratorio |
| F41 | ¿Son idénticas las copias de showdown, jsPDF y SheetJS de Chatboo y de MCP? | 27, 73 | Laboratorio (comparación de ficheros) |
| F42 | ¿Quedan adjuntos con enlace al borrar un usuario o al desinstalar Chatboo? | 64 | Laboratorio |
| F43 | El aviso de fin de turno por el bus resincroniza la pantalla | — (funcional) | Laboratorio |
| F44 | Con varios workers, ¿un turno más largo que `limit_time_real` acaba como "respuesta incompleta"? Amplía F26 | 35 | Laboratorio |
| F45 | ¿Arranca Odoo con `hr` instalado junto a Chatboo? | 70 | **Resuelta (fase 2): DESCARTADO.** Arranca y carga el registro sin errores ni avisos. |
| F46 | ¿Aparece el menú Chatboo tras generar la clave MCP sin recargar? | 77 | Laboratorio |
| F47 | ¿Recibe la skill `annual-billing` todas las variables que usa, o falla? | 68 | Laboratorio |
| F48 | Compatibilidad del JS de Chatboo con el OWL 1 de Odoo 14 en el navegador | 74 | Laboratorio |
| F49 | Rendimiento de las skills financieras con datos reales | 68 | Copia de producción (cargarla lo decide el usuario) |
| F50 | ¿Es la comprobación de estado de Chatboo la que espera a las fuentes de tipos de cambio? ¿Cuánto tarda cada carga sin Internet? | 48, 73 | Laboratorio |
| F51 | Voces que ofrece cada navegador (locales o remotas) y cuál usa la lectura en voz alta | 65 | Laboratorio (navegadores del cliente, D40) |
