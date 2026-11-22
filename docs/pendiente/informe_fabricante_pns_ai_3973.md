# CONFIDENCIAL — Informe técnico de seguridad, 2.ª entrega: pns_base 1.2.69, pns_ai_mcp 3.1.973 y pns_ai_chatboo 2.1.587 (Odoo 14.0)

> **Borrador.** Pendiente de revisión interna antes de su envío.

| | |
|---|---|
| **Destinatario** | PATANEGRA Soft |
| **Módulos** | `pns_base` 1.2.69 · `pns_ai_mcp` 3.1.973 ("AI Engine") · `pns_ai_chatboo` 2.1.587 ("Chatboo"), descargados de la rama `14.0` de sus repositorios el 2026-11-09 (commits `3f76f58`, `2450983` y `0c2e6e3`) |
| **Plataforma** | Odoo 14.0 |
| **Entregas anteriores** | Informe técnico de seguridad del 2026-10-08 sobre `pns_base` 1.2.10, `pns_ai_mcp` 3.1.486 y `pns_ai_chatboo` 2.1.322 (PNS-01 a PNS-80) · Seguimiento del 2026-10-15 sobre `pns_base` 1.2.32, `pns_ai_mcp` 3.1.782 y `pns_ai_chatboo` 2.1.453 (estado de PNS-01 a PNS-80 y hallazgos nuevos PNS-81 a PNS-92) · Continuación del 2026-10-16, mismas versiones (pruebas con un proveedor de IA real y hallazgos nuevos PNS-93 a PNS-96) |
| **Fecha** | *(fecha de envío)* |
| **Entorno de análisis** | Odoo 14.0 con Python 3.7.3 (imagen oficial de Odoo 14, Debian Buster). Laboratorio con bases de datos de prueba, con dos versiones del core de Odoo 14: la de la imagen (14.0.20231106) y la de nuestros servidores (commit `cc0060e`, 2024-10-22). Entorno de pruebas con datos de demostración, 2 workers y un proveedor de IA real (Google Gemini por el protocolo compatible con OpenAI). Copia de una base de datos de producción de un cliente, para ensayar la actualización desde 3.1.782. |
| **Método** | Revisión del código de 3.1.973 frente a 3.1.879, hallazgo por hallazgo; comprobaciones en el laboratorio sobre 3.1.973 sin ninguna corrección local; batería de tests automáticos sobre los módulos con nuestras correcciones; actualización desde 3.1.879 en el entorno de pruebas y desde 3.1.782 en la copia de producción. Detalle y límites en §7. |
| **Referencias de código** | Las líneas citadas son las del código publicado de estas versiones, sin ninguna corrección local. Este informe no incluye código ni diffs de nuestras correcciones: las describimos con palabras. |

---

## Índice

0. Cabecera (arriba)
1. Resumen
2. Prioridades
3. Estado en 3.1.973 de lo comunicado (PNS-01 a PNS-96, observaciones 1 a 13 y petición de §5 de la entrega del 16/10)
4. Hallazgos nuevos con ficha: PNS-97 a PNS-105 y PNS-107
5. Lo nuevo de 3.1.973 y lo que hemos encontrado al corregir
6. Actualización desde versiones anteriores
7. Qué hemos probado y qué no
8. Observaciones menores

---

## 1. Resumen

1. **Qué es esta entrega.** Es la respuesta a la versión 3.1.973, que es la que tenemos en producción desde el
   2026-11-20. Recoge tres cosas:
   - el estado en 3.1.973 de todo lo que les comunicamos el 08/10, el 15/10 y el 16/10;
   - los hallazgos nuevos que hemos encontrado desde entonces (PNS-97 a PNS-114), casi todos al corregir en nuestra
     instalación lo que seguía abierto;
   - lo que la actualización a 3.1.973 hace con los datos de una instalación existente.
2. **Nuestra instalación.** Entre el 16/10 y hoy hemos corregido en nuestra instalación los hallazgos que seguían
   abiertos y que no podíamos aceptar para producción. Cuando un hallazgo de este informe está «corregido por Seges»,
   significa que lo hemos corregido en nuestra copia de los módulos, no en su código: la petición al fabricante sigue
   en pie. Describimos cada corrección con palabras, para que puedan valorar el criterio, sin código ni diffs.
3. **Estado de lo comunicado (PNS-01 a PNS-96)** frente a 3.1.973:

   | Gravedad | Corregido por el fabricante | Abierto; corregido por Seges en su instalación | Abierto; Seges asume el riesgo | Abierto | Total |
   |---|---|---|---|---|---|
   | Crítica | 5 | 4 | 0 | 0 | 9 |
   | Alta | 24 | 5 | 2 | 1 | 32 |
   | Media | 24 | 2 | 3 | 1 | 30 |
   | Baja | 20 | 1 | 4 | 0 | 25 |
   | **Total** | **73** | **12** | **9** | **2** | **96** |

   - **Críticos abiertos:** PNS-01, PNS-02, PNS-07 y PNS-54. 3.1.973 corrige parte de PNS-01, PNS-02 y PNS-07; PNS-54
     sigue igual.
   - **Observaciones y petición de la entrega del 16/10 (15):** 11 corregidas; siguen abiertas las observaciones 6, 7 y
     13 y la petición de §5 (registrar el prompt que recibe el modelo).
   - **Salvedad:** 53 de los 84 corregidos (hallazgos y observaciones) se dan por corregidos por lo que comprobamos en 3.1.782 o 3.1.879, sin volver a
     revisarlos en 3.1.973, porque 3.1.973 no toca su código o son de gravedad media o baja (§7).
   - Respecto a la entrega del 16/10, PNS-70 pasa de Media a **Alta**: en Odoo 14 rompe los gráficos del propio Odoo
     (§3).
4. **Hallazgos nuevos (PNS-97 a PNS-114).** 18 números. PNS-101 ya lo corrige 3.1.973 (§5); los otros 17 siguen
   abiertos en su código:

   | Gravedad | Abierto; corregido por Seges en su instalación | Abierto | Total |
   |---|---|---|---|
   | Crítica | 1 (PNS-102) | 0 | 1 |
   | Alta | 3 (PNS-100, PNS-105, PNS-108) | 0 | 3 |
   | Media | 1 (PNS-97) | 2 (PNS-99, PNS-113) | 3 |
   | Baja | 4 (PNS-103, PNS-104, PNS-107, PNS-109) | 6 (PNS-98, PNS-106, PNS-110, PNS-111, PNS-112, PNS-114) | 10 |
   | **Total** | **9** | **8** | **17** |

   Además, en §5:
   - tres defectos del lienzo y de las páginas compartidas que hemos corregido en nuestra instalación sin habérselos
     comunicado antes, con una ficha breve cada uno;
   - diez defectos que habíamos encontrado y no les habíamos comunicado, y que 3.1.973 ya corrige (una línea por
     defecto, para cerrar el hilo).
5. **Lo más urgente** (detalle en §2):
   - **La caja A (código generado por el modelo, de solo lectura) sigue dejando salir datos.** Cualquier usuario del chat,
     mediante una inyección de prompt que dicte el código, puede leer como superusuario a través de `user` (PNS-102),
     sacar datos por correo o por HTTP sin escribir en la base de datos (PNS-100) y leer secretos que ya estén en la
     caché del hilo (PNS-108). No hace falta ningún rol de IA.
   - **Los cursores propios con `commit` rompen la transacción de quien los llama** (PNS-105). En un plan confirmado
     pueden dejar un worker esperando un bloqueo hasta que se reinicie el servicio.
   - **La confirmación de operaciones sigue sin ligarse al usuario** (PNS-54), y un AI Administrator con el permiso
     «Permisos de acceso» de Odoo puede darse grupos con un plan que él mismo confirma (resto de PNS-01 y PNS-02).
6. **Lo que mejora 3.1.973.** Queremos dejar constancia de que 3.1.973 corrige bien una parte importante de lo
   comunicado, a veces con un criterio más amplio que el que sugeríamos:
   - el sandbox de la caja A, con lista blanca y bloqueo por clase de cursores y entornos (PNS-101, PNS-36);
   - las columnas secretas cerradas por nombre en todos los modelos (PNS-19, en parte);
   - el código de las skills, que ahora corre en una caja A propia (PNS-06);
   - la protección contra el DNS *rebinding* en `fetch_url` y en las imágenes remotas (PNS-17 y PNS-59);
   - el trabajo en las compañías marcadas en la pantalla (multicompañía);
   - y varios métodos públicos que pasan a privados: la mesa del PIN (PNS-83), los `log_*` y `chat_completion` del
     motor, y la creación de operaciones solo como superusuario (estos últimos no se los habíamos comunicado; §5).

---

## 2. Prioridades

### 2.1 Orden propuesto

| # | Hallazgo | Gravedad | Por qué en este lugar |
|---|---|---|---|
| 1 | PNS-102 | Crítica | Cualquier usuario del chat, por inyección de prompt, lee como superusuario a través de `user` y de sus relaciones (campos sin acceso, como `res.users.totp_secret`, y datos de otros contactos). En 3.1.973 se agrava: la protección nueva de columnas secretas no actúa en lecturas `su` (`pns_ai_mcp/models/sandbox_secret_read.py:65-66`). Comprobado en el laboratorio sobre 3.1.973. |
| 2 | PNS-100 | Alta | Desde la caja A se puede enviar correo o abrir una conexión a cualquier host y puerto sin escribir en la base de datos: salida de cualquier dato que el usuario pueda leer, sin confirmación. 3.1.973 añade 7 nombres a la lista; faltan, entre otros, `connect` y `load_remote_url`. |
| 3 | PNS-108 (con el resto de PNS-19) | Alta | La protección de columnas secretas no cubre los valores que ya están en la caché del hilo: la caja A los devuelve. Confirmado por test, como usuario interno, por cuatro vías que el propio código del sandbox dispara (`auth_token`, `mcp_api_key_hash`, `totp_secret` y `signup_token`). La clave del proveedor que lee el motor solo se alcanza si no hay un `commit` entre medias; en los turnos que hemos revisado lo hay, así que esa parte depende de un efecto lateral. Un campo `Reference` salta además la puerta de los modelos de credenciales. |
| 4 | PNS-105 | Alta | Un cursor propio con `commit` (por ejemplo, el de `ai.log`) confirma lo pendiente de quien lo llama aunque después se deshaga. En la caja B puede dejar el worker esperando un bloqueo que PostgreSQL no detecta como interbloqueo: desde la ficha de la operación, hasta que Odoo mata el worker por `limit_time_real`; desde el chat, por lectura del código, hasta que se reinicia el servicio. Confirmado por test. |
| 5 | PNS-54 | Crítica | La confirmación no exige al usuario (sin contraseña ni token ligado a la interacción), y la tarjeta entrega token a quien puede leer la operación. Requiere código en el navegador del usuario; por eso va detrás de los anteriores. |
| 6 | Resto de PNS-07 | Crítica | 9 de los 28 métodos que señalamos siguen públicos y fuera de la lista del sandbox. Alcanzables por un AI Administrator; algunos, sobre filas de otro AI Administrator. |
| 7 | Resto de PNS-01 y PNS-02 | Crítica | 3.1.973 ejecuta el plan con los permisos de quien lo pidió y escribe los grupos sin `su`: exige al solicitante el permiso «Permisos de acceso» de Odoo y nada a quien confirma. Ya no hay escalada por quien confirma, pero dar o quitar grupos por un plan de IA sigue sin exigir Ajustes. |
| 8 | PNS-82 | Alta | Al borrar una sesión de Chatboo se borran en `sudo` todos sus adjuntos, también los ajenos que la sesión haya reclamado. |
| 9 | PNS-70 | Alta | El Chart.js 4 de Chatboo sustituye en `window.Chart` al Chart.js 2 de Odoo 14: tras abrir el chat, las vistas gráfico de Odoo se pintan con la API 4 y opciones de la 2, con errores, hasta recargar la página. Afecta a cualquier instalación. |
| 10 | PNS-113 | Media | Actualizar el idioma con sobrescritura, necesario para que lleguen los textos cambiados de los `pns_*`, cambia textos de otros módulos en toda la instalación. En la copia de producción, 49 traducciones de otros módulos, 13 con otro texto. Sin copia previa no se puede deshacer. |
| 11 | Resto de PNS-17 y PNS-20 | Alta | En una redirección a otro host se reenvían las cabeceras que no son de autenticación, y el cliente MCP sigue redirecciones (PNS-17). La importación de configuración sobrescribe por defecto, y «Review» deja escritos cambios que nadie ha confirmado: comprobado en el laboratorio con un usuario MCP (PNS-20). |

El resto (los demás abiertos de §3, las fichas de §4 y §5 y las observaciones de §8) es de menor urgencia. Para los
puestos 1 a 4 **les pedimos una fecha prevista de corrección.**

### 2.2 Patrón común de 1 a 3 y corrección propuesta

Los puestos 1 a 3, y también PNS-107 (§4), tienen la misma causa. La caja A se protege con listas de nombres:
atributos del entorno, métodos con efectos fuera de la base de datos y columnas secretas. Cada lista deja fuera lo
que no se previó:
- `user` como superusuario (PNS-102);
- métodos del core que hablan con la red sin escribir (PNS-100) o que confirman en su propio cursor (PNS-107);
- valores que ya están en la caché (PNS-108).

3.1.973 ya ha dado el paso correcto en el entorno del sandbox, al pasar a una lista blanca con bloqueo por clase
(PNS-101). Proponemos extender ese criterio, en este orden:
1. **Identidad sin `su`.** Que `user`, `company` y `companies` del sandbox, y lo que cuelga de ellos, salgan de un
   entorno sin `su`. Es lo que hacemos en nuestra instalación.
2. **Una marca en el cursor de la caja A que respeten los métodos con efectos**, en lugar de una lista de nombres. Si
   se mantiene la lista, que incluya al menos los 28 nombres que sugerimos en PNS-100 y los métodos por modelo de
   PNS-107.
3. **Caché del hilo vacía al abrir la caja A**, o la protección de columnas secretas también sobre los valores en
   caché y en las lecturas `su`.
4. Un test negativo por vía, como los que ya traen para el sandbox.

---

## 3. Estado en 3.1.973 de lo comunicado

### 3.1 Tabla de estado

Estados frente al código publicado de 3.1.973:
- **CORREGIDO:** el cambio cubre el hallazgo y sus puntos de entrada. Incluye los que ya no aplican porque el código
  desapareció.
- **ABIERTO · corregido por Seges:** sigue en su código y lo hemos corregido en nuestra instalación (§3.2). La
  petición sigue en pie.
- **ABIERTO · Seges asume el riesgo:** sigue en su código y, en nuestra instalación, lo gestionamos con configuración
  y procedimiento (§3.3). Repetimos la petición cuando la hay.
- **ABIERTO:** sigue, sin corrección ni aceptación por nuestra parte (§3.4).

Verificación: **3.1.973** indica que se ha revisado sobre el código de 3.1.973. **3.1.879 (sin revisar en 3.1.973)**
o **3.1.782 (sin revisar en 3.1.973)** indica que se dio por corregido en esa versión y no se ha vuelto a revisar,
porque 3.1.973 no toca su código o porque es de gravedad media o baja (§7).

En las entregas anteriores, «PARCIAL» indicaba que quedaba un resto. Aquí los parciales figuran como ABIERTOS, y
en §3.2 a §3.4 describimos solo el resto.

| Hallazgo | Gravedad | Estado en 3.1.973 | Verificación | Nota |
|---|---|---|---|---|
| PNS-01 | Crítica | ABIERTO · corregido por Seges | 3.1.973 | Plan con los permisos de quien lo pide, grupos escritos sin `su`. Resto en §3.2. |
| PNS-02 | Crítica | ABIERTO · corregido por Seges | 3.1.973 | Igual que PNS-01. Resto en §3.2. |
| PNS-03 | Crítica | CORREGIDO | 3.1.973 | — |
| PNS-04 | Crítica | CORREGIDO | 3.1.973 | — |
| PNS-05 | Crítica | CORREGIDO | 3.1.973 | — |
| PNS-06 | Crítica | CORREGIDO | 3.1.973 | Más amplio: el código de las skills corre en una caja A propia. |
| PNS-07 | Crítica | ABIERTO · corregido por Seges | 3.1.973 | 19 de los 28 métodos cerrados. Resto en §3.2. |
| PNS-08 | Alta | CORREGIDO | 3.1.973 | Más amplio. |
| PNS-09 | Alta | CORREGIDO | 3.1.973 | Más amplio. |
| PNS-10 | Alta | CORREGIDO | 3.1.973 | — |
| PNS-11 | Alta | CORREGIDO | 3.1.973 | — |
| PNS-12 | Alta | CORREGIDO | 3.1.973 | — |
| PNS-13 | Alta | CORREGIDO | 3.1.973 | — |
| PNS-14 | Alta | CORREGIDO | 3.1.973 | Más amplio (`ai.safe.choice` de solo lectura; reglas de `ai.skill.param.cache`). |
| PNS-15 | Alta | CORREGIDO | 3.1.973 | — |
| PNS-16 | Alta | CORREGIDO | 3.1.973 | Sigue corregido con el código nuevo. |
| PNS-17 | Alta | ABIERTO · corregido por Seges | 3.1.973 | Mejora: protección contra el DNS *rebinding*. Resto en §3.2. |
| PNS-18 | Alta | ABIERTO · Seges asume el riesgo | 3.1.973 | Resto en §3.3. |
| PNS-19 | Alta | ABIERTO · corregido por Seges | 3.1.973 | Columnas secretas cerradas por nombre en la caja A. Resto en §3.2 y PNS-108 (§5). |
| PNS-20 | Alta | ABIERTO · corregido por Seges | 3.1.973 | Resto en §3.2. |
| PNS-21 | Alta | CORREGIDO | 3.1.973 | — |
| PNS-22 | Media | CORREGIDO | 3.1.879 (sin revisar en 3.1.973) | — |
| PNS-23 | Alta | ABIERTO · Seges asume el riesgo | 3.1.973 | El código de las skills corre ahora en la caja A, lo que acota el efecto. §3.3. |
| PNS-24 | Alta | CORREGIDO | 3.1.973 | Sigue corregido; nuevo `_require_settings`. |
| PNS-25 | Alta | CORREGIDO | 3.1.973 | — |
| PNS-26 | Alta | ABIERTO | 3.1.973 | §3.4, con un anexo. |
| PNS-27 | Alta | CORREGIDO | 3.1.973 | — |
| PNS-28 | Media | ABIERTO | 3.1.973 | §3.4. |
| PNS-29 | Media | ABIERTO · corregido por Seges | 3.1.973 | Resto en §3.2. |
| PNS-30 | Media | CORREGIDO | 3.1.973 | Cubre también lo que añadimos el 16/10 (§2.2 de aquella entrega). |
| PNS-31 | Media | CORREGIDO | 3.1.879 (sin revisar en 3.1.973) | — |
| PNS-32 | Media | CORREGIDO | 3.1.879 (sin revisar en 3.1.973) | — |
| PNS-33 | Media | ABIERTO · Seges asume el riesgo | 3.1.973 | Nuevo: no deja fijar la clave de un administrador de Ajustes a quien no lo es. §3.3. |
| PNS-34 | Media | CORREGIDO | 3.1.782 (sin revisar en 3.1.973) | — |
| PNS-35 | Media | CORREGIDO | 3.1.879 (sin revisar en 3.1.973) | — |
| PNS-36 | Media | CORREGIDO | 3.1.973 | Cerrado con el sandbox nuevo (lista blanca y formateador propio). |
| PNS-37 | Media | ABIERTO · corregido por Seges | 3.1.973 | `_record_failed_plan`, privado. Resto en §3.2. |
| PNS-38 | Media | CORREGIDO | 3.1.879 (sin revisar en 3.1.973) | — |
| PNS-39 | Media | CORREGIDO | 3.1.879 (sin revisar en 3.1.973) | — |
| PNS-40 | Media | CORREGIDO | 3.1.879 (sin revisar en 3.1.973) | — |
| PNS-41 | Media | CORREGIDO | 3.1.879 (sin revisar en 3.1.973) | — |
| PNS-42 | Media | CORREGIDO | 3.1.879 (sin revisar en 3.1.973) | — |
| PNS-43 | Baja | CORREGIDO | 3.1.879 (sin revisar en 3.1.973) | — |
| PNS-44 | Baja | CORREGIDO | 3.1.782 (sin revisar en 3.1.973) | — |
| PNS-45 | Baja | CORREGIDO | 3.1.782 (sin revisar en 3.1.973) | — |
| PNS-46 | Baja | CORREGIDO | 3.1.879 (sin revisar en 3.1.973) | — |
| PNS-47 | Baja | CORREGIDO | 3.1.782 (sin revisar en 3.1.973) | — |
| PNS-48 | Baja | CORREGIDO | 3.1.782 (sin revisar en 3.1.973) | — |
| PNS-49 | Baja | CORREGIDO | 3.1.879 (sin revisar en 3.1.973) | — |
| PNS-50 | Baja | ABIERTO · Seges asume el riesgo | 3.1.973 | Tests nuevos en los tres módulos. §3.3. |
| PNS-51 | Baja | ABIERTO · Seges asume el riesgo | 3.1.973 | §3.3. |
| PNS-52 | Baja | CORREGIDO | 3.1.782 (sin revisar en 3.1.973) | — |
| PNS-53 | Crítica | CORREGIDO | 3.1.973 | — |
| PNS-54 | Crítica | ABIERTO · corregido por Seges | 3.1.973 | §3.2. |
| PNS-55 | Alta | CORREGIDO | 3.1.973 | Sigue corregido; además, la sesión no cambia de dueño fuera de `su`. |
| PNS-56 | Alta | CORREGIDO | 3.1.973 | — |
| PNS-57 | Alta | CORREGIDO | 3.1.973 | — |
| PNS-58 | Alta | CORREGIDO | 3.1.973 | — |
| PNS-59 | Alta | CORREGIDO | 3.1.973 | Sigue corregido, con la comprobación del equipo que contesta en las imágenes remotas. |
| PNS-60 | Alta | CORREGIDO | 3.1.973 | Sigue corregido con el código nuevo. |
| PNS-61 | Media | ABIERTO · Seges asume el riesgo | 3.1.973 | §3.3. |
| PNS-62 | Media | CORREGIDO | 3.1.879 (sin revisar en 3.1.973) | — |
| PNS-63 | Media | CORREGIDO | 3.1.782 (sin revisar en 3.1.973) | — |
| PNS-64 | Media | CORREGIDO | 3.1.879 (sin revisar en 3.1.973) | — |
| PNS-65 | Media | CORREGIDO | 3.1.879 (sin revisar en 3.1.973) | — |
| PNS-66 | Media | CORREGIDO | 3.1.879 (sin revisar en 3.1.973) | — |
| PNS-67 | Media | CORREGIDO | 3.1.973 reescribe la skill de salud financiera (filtra por fecha y compañía) y retira customer-risk-analysis; comprobado en el código (22/11/2026), sin prueba en ejecución | — |
| PNS-68 | Media | CORREGIDO | 3.1.879 (sin revisar en 3.1.973) | — |
| PNS-69 | Baja | CORREGIDO | 3.1.782 (sin revisar en 3.1.973) | — |
| PNS-70 | Alta | ABIERTO · corregido por Seges | 3.1.973 | Gravedad revisada (antes Media). §3.2. |
| PNS-71 | Baja | CORREGIDO | 3.1.782 (sin revisar en 3.1.973) | — |
| PNS-72 | Baja | CORREGIDO | 3.1.879 (sin revisar en 3.1.973) | — |
| PNS-73 | Baja | CORREGIDO | 3.1.879 (sin revisar en 3.1.973) | — |
| PNS-74 | Baja | CORREGIDO | 3.1.879 (sin revisar en 3.1.973) | — |
| PNS-75 | Baja | CORREGIDO | 3.1.782 (sin revisar en 3.1.973) | — |
| PNS-76 | Baja | CORREGIDO | 3.1.879 (sin revisar en 3.1.973) | — |
| PNS-77 | Baja | ABIERTO · Seges asume el riesgo | 3.1.973 | Chatboo trae ya `tests/`. §3.3. |
| PNS-78 | Baja | CORREGIDO | 3.1.782 (sin revisar en 3.1.973) | — |
| PNS-79 | Baja | CORREGIDO | 3.1.782 (sin revisar en 3.1.973) | — |
| PNS-80 | Alta | CORREGIDO | 3.1.973 | Ya no aplica: `read_progress` no existe y el progreso se filtra por usuario. |
| PNS-81 | Alta | CORREGIDO | 3.1.973 | Corregido, también el resto de Python 3.7 (`_static_str`). |
| PNS-82 | Alta | ABIERTO · corregido por Seges | 3.1.973 | §3.2. |
| PNS-83 | Alta | CORREGIDO | 3.1.973 | Más amplio: también `_touch`, `_close` y `_supply` privados. |
| PNS-84 | Media | ABIERTO · Seges asume el riesgo | 3.1.973 | Mesa del PIN con métodos privados. Resto en §3.3. |
| PNS-85 | Media | CORREGIDO | 3.1.879 (sin revisar en 3.1.973) | — |
| PNS-86 | Media | CORREGIDO | 3.1.879 (sin revisar en 3.1.973) | — |
| PNS-87 | Baja | CORREGIDO | 3.1.879 (sin revisar en 3.1.973) | — |
| PNS-88 | Baja | ABIERTO · Seges asume el riesgo | 3.1.973 | §3.3. |
| PNS-89 | Baja | CORREGIDO | 3.1.879 (sin revisar en 3.1.973) | — |
| PNS-90 | Alta | CORREGIDO | 3.1.879 (sin revisar en 3.1.973) | — |
| PNS-91 | Media | CORREGIDO | 3.1.879 (sin revisar en 3.1.973) | — |
| PNS-92 | Media | CORREGIDO | 3.1.879 (sin revisar en 3.1.973) | — |
| PNS-93 | Media | CORREGIDO | 3.1.879 (sin revisar en 3.1.973) | — |
| PNS-94 | Alta | CORREGIDO | 3.1.973 | Sigue corregido con el código nuevo. |
| PNS-95 | Baja | CORREGIDO | 3.1.879 (sin revisar en 3.1.973) | — |
| PNS-96 | Baja | ABIERTO · corregido por Seges | 3.1.973 | §3.2. |
| Obs. 1: `system_prompt` duplicado en `prompts/list` | — | CORREGIDO | 3.1.879 (sin revisar en 3.1.973) | — |
| Obs. 2: Prefijo de la clave MCP en el log | — | CORREGIDO | 3.1.879 (sin revisar en 3.1.973) | — |
| Obs. 3: Copia de la clave al duplicar un proveedor | — | CORREGIDO | 3.1.879 (sin revisar en 3.1.973) | — |
| Obs. 4: El parche de `Root.get_request` afecta a todas las bases de datos | — | CORREGIDO | 3.1.879 (sin revisar en 3.1.973) | — |
| Obs. 5: Retención de sesiones de Chatboo en la primera pasada | — | CORREGIDO | 3.1.879 (sin revisar en 3.1.973) | — |
| Obs. 6: Descargas del chat fuera de la purga de 24 h | — | ABIERTO | 3.1.973 | §3.4. |
| Obs. 7: Errores con detalle técnico (`_fx_payload`) | — | ABIERTO | 3.1.973 | §3.4. |
| Obs. 8: `ai.execution.engine.choose` público | — | CORREGIDO | 3.1.879 (sin revisar en 3.1.973) | — |
| Obs. 9: Agente sin cadena de proveedores | — | CORREGIDO | 3.1.879 (sin revisar en 3.1.973) | — |
| Obs. 10: Consulta de tipos de cambio al abrir Chatboo | — | CORREGIDO | 3.1.879 (sin revisar en 3.1.973) | — |
| Obs. 11: Skill retirada borrada en cada actualización | — | CORREGIDO | 3.1.879 (sin revisar en 3.1.973) | — |
| Obs. 12: `detect_dangerous_operations` sin uso | — | CORREGIDO | 3.1.879 (sin revisar en 3.1.973) | — |
| Obs. 13: Tests que cambian la clave del administrador | — | ABIERTO | 3.1.973 | §3.4. |
| Petición de §5: registrar el prompt que recibe el modelo | — | ABIERTO | 3.1.973 | §3.4. |
| Compatibilidad sin número (entrega del 08/10, §7.1 a §7.4 y §8.5) | — | CORREGIDO | 3.1.973 | Ya no aplica: el código de 3.1.973 no usa esas construcciones. |

**Recuento (111 filas):** CORREGIDO 84 (53 de ellos sin revisar en 3.1.973) · ABIERTO · corregido por Seges 12 ·
ABIERTO · Seges asume el riesgo 9 · ABIERTO 6.

### 3.2 Abiertos y corregidos por Seges en su instalación

Para cada hallazgo: qué sigue en 3.1.973, cómo lo hemos corregido nosotros (sin código) y qué les pedimos. Rutas
relativas a la raíz de los módulos.

**PNS-01 y PNS-02 (Crítica) — Dar o quitar grupos de Odoo con un plan**
- **En 3.1.973:** el plan se ejecuta con los permisos de quien lo pidió y en sus compañías
  (`pns_ai_mcp/models/safe_operation.py:1435-1440`). El alta y la baja de grupos se escriben sin `su` con ese
  usuario (`models/ai_system_action.py:738-742` y `:768-772`). Es una mejora clara: ya no hay escalada por los
  permisos de quien confirma. Pero lo único que se exige al solicitante es el permiso de Odoo «Permisos de acceso»
  (`base.group_erp_manager`), y nada a quien confirma, salvo ser AI Administrator para confirmar el plan de otro.
  Lo hemos comprobado en el laboratorio: sin «Permisos de acceso» el plan falla y no da el grupo; con él, lo da.
- **Corrección de Seges:** dar o quitar un grupo con un plan exige Ajustes (`base.group_system`) al usuario que
  ejecuta, a quien propuso y a quien confirmó. Se suma a la cúspide del fabricante y no la sustituye. Es compatible
  con su cambio: el resultado es el criterio más estricto de los dos.
- **Petición:** exigir Ajustes para las acciones de grupos por plan. El test del fabricante
  `test_paap_i7_cusp_roles_out_of_reach_of_an_ai_admin` (`pns_ai_mcp/tests/test_system_action.py:543-547`) espera
  que un AI Administrator sin Ajustes pueda proponer un grupo normal: con nuestro criterio falla, por diseño.

**PNS-07 (Crítica) — Métodos públicos con cursor propio, alcanzables desde el sandbox**
- **En 3.1.973:** pasan a privados o entran en la lista 19 de los 28 métodos que señalamos. Siguen públicos y fuera
  de la lista estos 9:
  - `mark_seen` (`pns_ai_chatboo/models/chatboo_async_request.py:1535`);
  - `sandbox_helpers` (`pns_ai_chatboo/models/chatboo_session.py:831`);
  - `action_suggest_detection` (`pns_ai_mcp/models/external_server.py:880`);
  - `action_author_params`, `action_author_help` y `action_adapt_code`
    (`pns_ai_mcp/wizard/skill_capture_wizard.py:636-688`);
  - `action_generate_openapi`, `action_generate` y `action_log_generation_usage`
    (`pns_ai_mcp/wizard/openapi_spec_generate_wizard.py:178-302`).

  La puerta de catálogos frena una parte. En el laboratorio, `action_suggest_detection` (por una relación) y los
  tres del asistente OpenAPI son alcanzables por un AI Administrator; los del asistente, también sobre filas de otro
  AI Administrator.
- **Corrección de Seges:** los 9 nombres, en la lista de métodos que el sandbox no deja llamar.
- **Petición:** cerrar esos 9 (privados o en la lista) y, a medio plazo, el criterio de §2.2.

**PNS-17 (Alta) — Redirecciones a otro host**
- **En 3.1.973:** al cambiar de host solo se quitan las cabeceras de `_AUTH_HEADER_NAMES`
  (`pns_ai_mcp/utils/fetch_url_safe.py:122-134`). La cabecera de autenticación propia de un servidor de API (por
  ejemplo, `apikey`) viaja al host nuevo. El cliente MCP por HTTP sigue las redirecciones de `requests`, que solo
  quita `Authorization` (`utils/mcp_client.py:103-108`).
- **Corrección de Seges:** al cambiar de host solo se conservan las cabeceras de una lista corta de cabeceras
  neutras (`Accept`, `Accept-Language`, `Content-Type` y `User-Agent`). El cliente MCP no sigue redirecciones: da
  un error que pide poner la URL final en el servidor.
- **Petición:** una lista de cabeceras permitidas al cambiar de host, en lugar de una lista de cabeceras prohibidas,
  y no seguir redirecciones en el cliente MCP.

**PNS-19 (Alta) — Secretos desde la caja A**
- **En 3.1.973:** el criterio nuevo es bueno y más amplio en modelos que el nuestro. En el cursor de la caja A,
  cualquier columna secreta da `AccessError` al leerla, buscarla, ordenarla o agruparla
  (`pns_ai_mcp/models/sandbox_secret_read.py:55-127`; `utils/sandbox_secrets.py:21-79`). Quedan dos restos:
  - no actúa en lecturas `su` (`sandbox_secret_read.py:65-66`), que es justo lo que da `user` (PNS-102);
  - no cubre los valores que ya están en la caché del hilo (PNS-108, §5).
- **Corrección de Seges:** dentro de la caja A, cada lectura se comprueba con su criterio de columnas secretas y con
  el permiso de lectura del modelo, también si el valor está en caché o se calcula; las columnas secretas se vacían de
  la caché al abrir la caja A y después de cada ayuda del sandbox; y el PIN y las claves de la mesa del PIN y del
  asistente de claves cuentan como columnas secretas.
- **Petición:** la de §2.2 (puntos 1 y 3).

**PNS-20 (Alta) — Importación de configuración**
- **En 3.1.973:** sin cambios (`pns_base/models/operation_report_wizard.py`, `action_preview`, `:305`). «Review»
  importa dentro de un `SAVEPOINT` y lo deshace, pero lo que la importación deja pendiente de escribir se vuelca al
  terminar la petición. En el laboratorio, revisar la importación de un usuario MCP dejó escrita su etiqueta, y la
  de un proveedor dejó una escritura del registro. Sigue además la sobrescritura por defecto.
- **Corrección de Seges:** «Review» vuelca lo pendiente antes de abrir el `SAVEPOINT` y antes de deshacerlo, y
  limpia lo pendiente después. «Review» ya no deja nada escrito.
- **Petición:** la misma corrección; y, como pedimos el 16/10, no sobrescribir por defecto.

**PNS-29 (Media) — Consumo de los proveedores**
- **En 3.1.973:** `ai.provider.month_usage` sigue siendo público y lee en `sudo`
  (`pns_ai_mcp/models/ai_provider.py:1096`). Por RPC, cualquier usuario autenticado, también de portal, obtiene los
  tokens y el coste del mes de cada proveedor. El asistente de uso da las mismas cifras desde `default_get`, sin
  comprobar el ACL (`wizard/ai_provider_usage_wizard.py:37`).
- **Corrección de Seges:** el método, privado (solo lo usa el cálculo del tope, que sigue público y devuelve un
  booleano). El asistente comprueba el ACL antes de leer las cifras.
- **Petición:** la misma. Lo que quedaba del 16/10 (tokens de escritura en la caché de Anthropic) no lo hemos
  comprobado en 3.1.973.

**PNS-37 (Media) — Diario de cambios**
- **En 3.1.973:** `_record_failed_plan` ya es privado (`pns_ai_mcp/models/ai_change_journal.py:375`). Quedan dos
  vías:
  - el AI Administrator y Ajustes crean y escriben filas del diario por RPC (`security/ir.model.access.csv:43-44`,
    `1,1,1,0`; el modelo solo sobrescribe `unlink`). Una fila reescrita como borrado en la papelera la vacía el cron
    de la papelera, que corre como superusuario;
  - el paso `unlink` de un plan, en un modelo con `active`, archiva con solo permiso de escritura
    (`controllers/safe_plan_execute.py:221-226`), y el cron lo borra pasados los días de retención.
- **Corrección de Seges:** el diario solo lo escribe el sistema (crear y escribir fuera de `su` dan `AccessError`),
  y el paso `unlink` exige permiso de borrado sobre los registros aunque archive.
- **Petición:** la misma.

**PNS-54 (Crítica) — Confirmación de la caja B**
- **En 3.1.973:** sin cambios en lo que comunicamos:
  - `action_confirm_and_execute` confirma y ejecuta por RPC sin contraseña
    (`pns_ai_mcp/models/safe_operation.py:1796-1835`);
  - `card_payload` genera token para quien puede leer la operación, no solo para su dueño (`:2034-2063`).

  Es nuevo que la tarjeta reintenta sola una vez tras un rechazo (`too_soon`, `bad_token` o `missing_token`;
  `pns_ai_chatboo/static/src/js/chatboo_component_v2.js`, `_retryRefusedCard`). La espera de 5 s sigue en el
  servidor.
- **Corrección de Seges:** confirmar desde Autorizaciones pide la contraseña, con el mecanismo de identidad de Odoo
  14 (la recuerda 10 minutos). La tarjeta solo genera token para el dueño de la operación.
- **Petición:** la misma, y un token ligado a la interacción para la tarjeta.

**PNS-70 (Alta; comunicado como Media) — `window.Chart`**
- **En 3.1.973:** `chart.umd.min.js` y `chatboo_heavy_libs.js` son idénticos a 3.1.879 (`window.Chart` en
  `pns_ai_chatboo/static/src/js/chatboo_heavy_libs.js:29`). Lo comprobamos en el navegador: al abrir el chat,
  Chart.js 4.4.8 sustituye en `window.Chart` al Chart.js 2 que Odoo ya había cargado. Después, las vistas gráfico de
  Odoo se pintan con la API 4 y opciones de la 2, con errores de escala en la consola, hasta recargar la página. Por
  eso subimos la gravedad.
- **Corrección de Seges:** el Chart.js del chat se publica con otro nombre global y Chatboo lo usa con ese nombre;
  `window.Chart` queda para Odoo. Hay que cambiar el nombre en dos puntos del archivo minificado, porque el UMD
  escribe la global dos veces.
- **Petición:** cargar Chart.js 4 sin tocar `window.Chart` (con un nombre propio o una referencia local).

**PNS-82 (Alta) — Borrado de adjuntos al borrar una sesión**
- **En 3.1.973:** la reclamación de adjuntos es la misma. `unlink` de `chatboo.session` borra en `sudo` todos los
  adjuntos con `res_model='chatboo.session'` de esas sesiones, sean de quien sean, antes de comprobar el acceso
  (`pns_ai_chatboo/models/chatboo_session.py:1976-2033`; la búsqueda, en `:2023-2028`). Es nuevo, y correcto, que la
  sesión no cambie de dueño fuera de `su`.
- **Corrección de Seges:** se comprueba el acceso de borrado al principio. De los adjuntos de la sesión solo se
  borran los de su dueño o sin creador; los demás se desenganchan.
- **Petición:** la misma.

**PNS-96 (Baja) — El chat afirma cambios que no hizo**
- **En 3.1.973:** cuando el lienzo rechaza o falla, `log_no_page` deja la causa en `ai.log` y devuelve una cadena
  vacía para que el turno siga (`pns_ai_chatboo/models/chatboo_canvas.py:587-616`). El modelo responde a menudo «Se ha
  generado la página» sin página nueva. El aviso al usuario solo existe en el botón Canvas
  (`models/chatboo_canvas_job.py:133, 156`).
- **Corrección de Seges:** si en el turno hubo un rechazo del lienzo, el servidor añade al final de la respuesta un
  aviso fijo, en texto llano, de que no se ha podido crear o cambiar la página.
- **Petición:** que el turno reciba el rechazo y lo muestre, como hace ya el botón Canvas.

### 3.3 Abiertos en los que Seges asume el riesgo

Siguen en su código. En nuestra instalación los gestionamos con configuración y procedimiento. Repetimos la petición
salvo donde se indica.

**PNS-18 (Alta) — Datos hacia el proveedor de IA**
- **En 3.1.973:** «Sin failover externo» se aplica después de roles y topes, y con la red de «todos los proveedores
  activos» si la cadena no cubre el rol (`pns_ai_mcp/models/ai_execution_engine.py:256-287`). Es nuevo que, si nadie
  tiene el rol, se pide su alternativa (Parser → Conversación), lo que amplía los candidatos fuera de la cadena
  (`:271-286`). Sigue sin haber lista de modelos o campos que nunca se envían.
- **Petición:** la del 16/10, y que la alternativa de rol respete «Sin failover externo» y la cadena del agente.

**PNS-23 (Alta) — Skills activas sin revisión**
- **En 3.1.973:** la causa sigue:
  - las skills capturadas desde el chat se crean activas (`pns_ai_mcp/wizard/skill_capture_wizard.py:840`);
  - las importadas por ZIP, activas por defecto (`models/ai_skill_zip.py:239`);
  - sigue existiendo `skill_skip_body_check` (`models/ai_skill.py:450`).

  Acota mucho el efecto que el código de las skills corra ahora en la caja A.
- **Petición:** la del 16/10 (inactivas hasta que las revise un AI Administrator).

**PNS-33 (Media) — Claves MCP**
- **En 3.1.973:** `set_mcp_api_key` sigue aceptando una clave elegida o un hash ya calculado
  (`pns_ai_mcp/models/mcp_user.py:456-470`). Es nuevo, y correcto, que no deja fijar la clave de un administrador
  de Ajustes a quien no lo es (`:740-766`).
- **Petición:** la del 16/10 (HMAC con un secreto del servidor y caducidad).

**PNS-50 (Baja) — Tests**
- **En 3.1.973:** hay tests nuevos en los tres módulos. Siguen sin venir los `unit_tests/` que citan las notas de
  versión (§6).
- **Sin petición nueva.**

**PNS-51 (Baja) — `platform` en el sandbox**
- **En 3.1.973:** sigue en la lista de módulos permitidos (`pns_ai_mcp/controllers/validators_base.py:95`).
- **Petición:** quitarlo.

**PNS-61 (Media) — Historial escrito por el navegador**
- **En 3.1.973:** `/chatboo/stream` ya no toma el historial del cuerpo de la petición: lo reconstruye de la sesión
  guardada (`pns_ai_chatboo/controllers/chatboo.py:820-843`; `models/chatboo_session.py:224-244`). Pero los mensajes
  de la sesión los sigue escribiendo el navegador con `/chatboo/sessions/save` (`controllers/chatboo.py:431-458`,
  `set_messages`). Un usuario puede seguir poniendo en su historial turnos del asistente que no existieron. El
  efecto se limita a sus propias sesiones.
- **Petición:** que los mensajes del asistente solo los escriba el servidor al terminar el turno.

**PNS-77 (Baja) — Chatboo sin tests**
- **En 3.1.973:** Chatboo trae `tests/` (`test_chatboo_perimeter.py`, `test_chat_agent_composition.py`).
- **Sin petición nueva.**

**PNS-84 (Media) — PIN y clave MCP en claro**
- **En 3.1.973:** `_touch`, `_close` y `_supply` de la mesa del PIN pasan a privados
  (`pns_ai_mcp/models/key_pin_desk.py:91, 127, 245`). Siguen el PIN y la clave en `ai.key.pin.ask`, que el AI
  Administrator lee (`security/ir.model.access.csv:85`), y `_touch` sigue dando los PIN pendientes a la mesa
  (`key_pin_desk.py:111-124`).
- **Petición:** la del 15/10.

**PNS-88 (Baja) — Renombrados de XML ID**
- **En 3.1.973:** `XMLID_RENAMES` es el mismo (`pns_ai_mcp/utils/schema_fossils.py:73-101`), y sigue sin
  ejecutarse en Odoo 14.
- **Petición:** la del 15/10.

### 3.4 Abiertos

**PNS-26 (Alta) — `commit()` sobre el cursor de quien llama**
- **En 3.1.973:** siguen los `commit()` sobre el cursor del llamador en `execute_plan_now`
  (`pns_ai_mcp/models/safe_operation.py:943, 952, 1455`). El recuento de `.commit()` en `models`, `controllers`,
  `utils` y `lib` pasa de 30 a 31; el nuevo (`utils/engine_tool_run.py:556`) va en cursor propio y con comprobación
  de dueño.
- **Petición:** la del 16/10. Ver también PNS-105 (§4), que es la otra cara del mismo problema: los cursores propios
  que confirman lo pendiente de quien los llama.

**Anexo de PNS-26 (Baja) — Fallo de serialización en «Ejecutar» de la ficha**
- **Qué pasa:** en `/pns_ai_mcp/verification/execute` (`pns_ai_mcp/controllers/verification_ui.py:78-97`), la
  primera consulta de la petición fija la instantánea de la transacción. Después, la ejecución confirma en su
  propio cursor la actualización de la fila de `ai.safe.operation`. Al consumir el token, la petición escribe en esa
  misma fila desde su instantánea antigua, y PostgreSQL da un fallo de serialización (40001). Odoo reintenta la
  petición entera, y el reintento termina bien porque la ejecución es idempotente.
- **Impacto:** el resultado es correcto, pero queda un error en el log en cada ejecución desde la ficha, y la
  corrección depende del reintento de Odoo. Lo vimos en el entorno de pruebas sobre 3.1.879 y lo reproducimos por
  test en 3.1.973. En el entorno de pruebas del 18/11, sobre 3.1.973, una ejecución desde la ficha no lo reprodujo.
- **Corrección sugerida:** consumir el token en el mismo cursor que ejecuta, o refrescar la fila tras la ejecución
  antes de escribirla. No lo hemos corregido: un cambio completo tocaría la caja B más de lo que justifica la
  gravedad.

**PNS-28 (Media) — CORS y `Origin`**
- **En 3.1.973:** las rutas `/mcp*` siguen con `cors='*'` (`pns_ai_mcp/controllers/main.py:242-290`), sin validar
  `Origin`.
- **Petición:** la del 08/10.

**Observación 6 — Descargas del chat fuera de la purga de 24 h.** Los adjuntos de `persist_turn_file`
(`pns_ai_mcp/utils/session_download.py:474`) siguen sin la marca de exportación.

**Observación 7 — Errores con detalle técnico.** `_fx_payload` sigue devolviendo `str(exc)`
(`pns_ai_chatboo/controllers/chatboo.py:1116-1121`).

**Observación 13 — Tests que cambian la clave del administrador.** No hemos localizado cambios. Las notas de
3.1.913 dicen que los tests ya no confirman en un cursor aparte, lo que reduce el riesgo; no lo hemos comprobado.

**Petición de §5 de la entrega del 16/10 — Registrar el prompt que recibe el modelo.** No hemos localizado cambios.
Sigue siendo lo que más nos ayudaría a diagnosticar la calidad de las respuestas (PNS-96 y la reinterpretación de peticiones de §8).

---

## 4. Hallazgos nuevos con ficha: PNS-97 a PNS-105 y PNS-107

Mismo criterio de gravedad que en las entregas anteriores. Los encontramos entre el 21/10 y el 17/11, casi todos al
corregir en nuestra instalación lo que seguía abierto: los primeros sobre 3.1.879 y los últimos sobre 3.1.973. Todos
siguen en el código de 3.1.973. PNS-101 ya lo corrige 3.1.973 (§5.3); PNS-106, PNS-108 y PNS-110 a PNS-112 están en
§5.1, y PNS-109, PNS-113 y PNS-114, en §6.

Rutas relativas a la raíz de los módulos. Las que empiezan por `odoo/` o `addons/` son del core de Odoo 14 de la imagen
oficial (14.0.20231106).

| PNS | Gravedad | Módulos | Título | Verificación | En nuestra instalación |
|---|---|---|---|---|---|
| PNS-97 | Media | pns_ai_mcp | Cualquier AI Administrator puede cambiar el registro de acciones de confianza | Lectura de código (3.1.973) | Corregido |
| PNS-98 | Baja | pns_ai_chatboo, pns_ai_mcp | Adjuntos del chat que quedan huérfanos | Entorno de pruebas (3.1.879); lectura de código (3.1.973) | Sin corregir |
| PNS-99 | Media | pns_base, pns_ai_mcp | `user.remove_group` queda ejecutado y aplicado sin quitar el grupo | Laboratorio (3.1.879); lectura de código (3.1.973) | Sin corregir |
| PNS-100 | Alta | pns_ai_mcp | La caja A permite abrir conexiones y ejecutar acciones sin escribir en la base de datos | Tests (3.1.879); lectura de código (3.1.973) | Corregido |
| PNS-102 | Crítica | pns_ai_mcp | `user` del sandbox como superusuario | Laboratorio (3.1.973) | Corregido |
| PNS-103 | Baja | pns_base | Un AI Administrator sin Ajustes no puede revisar ni aplicar una importación | Laboratorio (3.1.973) | Corregido |
| PNS-104 | Baja | pns_ai_mcp | Cerrar la caja A descarta las escrituras pendientes de quien la abre | Tests (3.1.973) | Corregido |
| PNS-105 | Alta | pns_ai_mcp, pns_ai_chatboo | Los cursores propios con `commit` confirman y descartan lo pendiente de quien los llama | Tests (3.1.973) | Corregido |
| PNS-107 | Baja | pns_ai_mcp | `iap.account.get` crea y borra cuentas IAP desde la caja A | Tests (3.1.973) | Corregido |

### PNS-97 — Cualquier AI Administrator puede cambiar el registro de acciones de confianza (`ai.trusted.action`)

- **Gravedad:** Media (requiere AI Administrator) · **Verificación:** lectura de código en 3.1.973 · **Módulo:**
  pns_ai_mcp (relacionado con PNS-01, PNS-02 y PNS-84)
- **Ubicación:** `pns_ai_mcp/security/ir.model.access.csv:78` (`1,1,1,1` para `group_ai_admin`);
  `models/ai_trusted_action.py:28-148`, sin `create`, `write` ni `unlink` propios (`group_ids`, `:52-57`;
  `_resolve_method`, `:95-115`; `user_has_required_groups`, `:136-148`); `data/trusted_actions_system.xml`.
- **Comportamiento:**
  - El AI Administrator crea, cambia y borra acciones de confianza, por RPC o desde la interfaz.
  - `group_ids` significa «al menos uno de estos grupos», y vacío, «sin restricción adicional» (`ai_trusted_action.py:146-148`): vaciarlo
    deja la acción a cualquier AI Writer.
  - También puede registrar una acción con otro `code` sobre el mismo método (por ejemplo, `_apply_user_add_group`) o
    sobre cualquier otro: `_resolve_method` lo resuelve con `getattr`, sin comprobar que sea uno de los métodos
    previstos (`ai_trusted_action.py:95-115`). El método se llama con los argumentos que traiga el plan.
  - Lo que cambia en 3.1.973, y reduce el efecto: el plan corre con los permisos de quien lo pidió
    (`models/safe_operation.py:1435-1440`); las acciones de vistas y campos exigen Ajustes al usuario real
    (`_require_settings`, `models/ai_system_action.py:120-125`, llamado en `:218, 388, 505`), y las de módulos y grupos
    dejan actuar a la comprobación propia de Odoo (`_apply_module_update`, `:641`; `_apply_user_add_group`,
    `:738-742`; `_apply_user_remove_group`, `:768-772`). Ya no se aprovechan los permisos de quien confirma.
- **Impacto:** el registro no es una barrera frente a un AI Administrator: decide qué grupos usan cada acción de
  confianza y qué método ejecuta cada código. Puede abrir una acción a usuarios con menos privilegios.
- **Cómo comprobarlo:** como AI Administrator sin Ajustes, vaciar «Required groups» de la acción `module.update`, o
  crear por RPC una `ai.trusted.action` con otro `code` y el mismo `apply_method`: se guarda sin error.
- **Corrección sugerida:** en `create`, `write` y `unlink` de `ai.trusted.action`, exigir `base.group_system` fuera de
  `sudo` (los datos XML se cargan como superusuario), sin tocar el ACL.
- **En nuestra instalación:** crear, cambiar o borrar una acción de confianza fuera del sistema exige Ajustes.

### PNS-98 — Adjuntos del chat que quedan huérfanos: PDF, Word, ficheros del clip y SVG en línea

- **Gravedad:** Baja · **Verificación:** entorno de pruebas sobre 3.1.879; lectura de código en 3.1.973 ·
  **Módulos:** pns_ai_chatboo, pns_ai_mcp (relacionado con PNS-82 y PNS-94)
- **Ubicación:** `pns_ai_mcp/utils/session_download.py:365-392` (`_run_on_committed_cursor`) y `:395-480`
  (`persist_turn_file_detail`, `persist_turn_file`); `pns_ai_chatboo/models/chatboo_session.py:546-575`
  (`_fulfill_client_export`) y `:470-508` (`_claim_turn_file_chips`, `exists()` en `:496`);
  `models/chatboo_async_request.py:701-760` (`_finalize`).
- **Comportamiento:** los adjuntos de estas vías se crean con el usuario del turno, pero no se enganchan a la sesión
  (`res_model` y `res_id` vacíos). El Excel del motor sí se engancha.
  - PDF y Word montados en el navegador: el adjunto se crea en un cursor aparte que confirma
    (`_run_on_committed_cursor`), y la reclamación lo busca con el cursor de la petición, que no lo ve por el
    aislamiento `REPEATABLE READ`: `exists()` da falso. El comentario de `_run_on_committed_cursor` ya advierte de que
    esas descargas son invisibles para el cursor que llama (`:368-370`).
  - Ficheros del clip y SVG en línea: se reclaman al guardar el turno en `_finalize`. Si esa escritura falla, la vía de
    respaldo solo escribe el estado del trabajo por SQL (`:746-760`) y no reclama los adjuntos. En el entorno de pruebas,
    sobre 3.1.879, la escritura falló por un conflicto de serialización. `_finalize` cambia en 3.1.973 y no lo hemos
    vuelto a reproducir.
- **Impacto:** sin efecto de seguridad: un adjunto huérfano solo lo leen su creador y los administradores, y el usuario
  sigue descargando sus ficheros. Al borrar la sesión, esos adjuntos no se borran y quedan en la base de datos sin
  caducidad (ver también la observación 6, §3.4).
- **Cómo comprobarlo:** exportar a PDF o Word una respuesta con tabla y consultar el adjunto creado en `ir_attachment`:
  `res_model` vacío. Al borrar la sesión, el adjunto sigue.
- **Corrección sugerida:** reclamar el adjunto en el mismo cursor que lo crea (o crearlo ya con `res_model` y `res_id`
  cuando se conoce la sesión), y que la vía de respaldo de `_finalize` también reclame los adjuntos del turno.

### PNS-99 — `user.remove_group` queda ejecutado y con el diario «Applied» sin que el grupo se quite

- **Gravedad:** Media · **Verificación:** laboratorio sobre 3.1.879; lectura de código en 3.1.973 · **Módulos:**
  pns_base, pns_ai_mcp (relacionado con PNS-37 y con PNS-01 y PNS-02, pero distinto)
- **Ubicación:** `pns_base/utils/compat.py:142-145` (`user_remove_group`); `pns_ai_mcp/models/ai_system_action.py:768-786`
  (`_apply_user_remove_group`); `models/ai_change_journal.py:242-367` (`record_executed_step`, `state='applied'` en
  `:367`).
- **Comportamiento:**
  - si el usuario tiene el grupo también por implicación de otro que conserva, `user_remove_group` escribe `(3, gid)` y
    el `write` de `res.users` de Odoo 14 (`UsersImplied.write`) vuelve a añadir, en la misma escritura, los grupos que
    implican los que quedan;
  - si el grupo no está entre los directos, no se escribe nada (3.1.973 lo comprueba antes, `compat.py:144`);
  - en los dos casos, `_apply_user_remove_group` devuelve `ok: True` sin comprobar el resultado, y el diario registra el
    paso como aplicado;
  - pasa por todas las vías que ejecutan el plan: la tarjeta del chat, Autorizaciones, `safe_plan_status` y el
    reintento del cron.
- **Impacto:** una retirada de permisos pedida y confirmada no ocurre, y la respuesta y el diario dicen lo contrario:
  auditoría falsa. No concede privilegios, y la ficha del usuario sigue mostrando el grupo.
- **Cómo comprobarlo:** plan `user.remove_group` de un grupo que el usuario tiene también porque lo implica otro grupo
  suyo. Tras confirmar: operación ejecutada, resultado `ok`, diario «Applied», y el usuario conserva el grupo.
- **Corrección sugerida:** después del `write`, comprobar si el usuario sigue teniendo el grupo y, si es así, devolver
  un error que diga qué grupo lo implica (o rechazarlo al proponer).

### PNS-100 — La caja A permite abrir conexiones y ejecutar acciones sin escribir en la base de datos

- **Gravedad:** Alta · **Verificación:** tests sobre 3.1.879, con los métodos sustituidos y sin envío real; lectura de
  código en 3.1.973 · **Módulo:** pns_ai_mcp (del mismo tipo que PNS-07)
- **Ubicación:** `pns_ai_mcp/controllers/validators_base.py:229-266` (`RELAXAICODE_SIDE_EFFECT_METHODS`; 3.1.973 añade
  `send_email`, `build_email`, `send`, `send_mail`, `process_email_queue`, `run` y `method_direct_trigger`, `:257-265`).
  Core: `odoo/addons/base/models/ir_mail_server.py:175-249` (`connect`) y `:426-514` (`send_email`);
  `addons/web_editor/models/ir_qweb.py:461-470` (`load_remote_url`).
- **Comportamiento:**
  - la caja A frena las escrituras con una transacción `READ ONLY`, pero no lo que sale a la red o ejecuta otro código
    sin escribir antes;
  - 3.1.973 cierra `send_email` y `run`, pero siguen alcanzables, entre otros:
    - `ir.mail_server.connect(host, port, …)`: conexión SMTP a cualquier host y puerto, también internos, fuera de la
      política de URL de `fetch_url`; `@api.model` y sin ACL;
    - `ir.qweb.field.image.load_remote_url(url)`: `requests.get` a cualquier URL, con redirecciones; modelo abstracto,
      sin ACL;
  - de los 28 nombres que identificamos al barrer los 47 módulos de nuestra instalación, 3.1.973 cubre 6. Faltan 22:
    `connect`, `test_smtp_connection`, `load_remote_url`, `fetch_mail`, `button_confirm_login`, `get_credits`,
    `autocomplete`, `enrich_company`, `read_by_vat`, `start_sync`, `send_letter`, `snailmail_print`,
    `update_notification`, `install_from_urls`, `action_process_edi_web_services`, `get_usd_fx`, `execute_callback`,
    `upgrade_module`, `action_start_automatic_process`, `parent_migration_process_cb`, `message_process` y
    `message_route`. Unos los alcanza cualquier usuario interno y otros solo con más permisos (Ajustes, Facturación);
    todos salen a la red, ejecutan otro código o confirman en un cursor propio.
- **Quién:** cualquier usuario del chat (el motor ejecuta `relaxaicode` para lecturas sin exigir ningún grupo),
  mediante una inyección de prompt que dicte el código. No hace falta AI Administrator ni Ajustes.
- **Impacto:** salida de cualquier dato que el usuario pueda leer hacia un servidor del atacante (SMTP o HTTP) y conexión
  a hosts internos, sin escrituras ni confirmación. Con un usuario con más permisos, otras acciones del core, como
  instalar módulos desde una URL.
- **Cómo comprobarlo:** como usuario interno, código del sandbox que llame a
  `env['ir.qweb.field.image'].load_remote_url('<URL de prueba>')` o a
  `env['ir.mail_server'].connect(host='<host de prueba>', port=25)`: la petición llega al host de prueba. En modo test,
  Odoo no envía ni conecta (`ir_mail_server.py:189-191, 491-494`): hay que probarlo fuera de los tests o sustituyendo el
  método.
- **Corrección sugerida:** la de §2.2, punto 2: una marca en el cursor de la caja A que respeten los métodos con efectos,
  en lugar de una lista de nombres. Mientras tanto, añadir a la lista los 22 nombres que faltan.
- **En nuestra instalación:** los 28 nombres están en la lista de métodos que el sandbox no deja llamar.

### PNS-102 — `user` del sandbox como superusuario: lecturas sin ACL ni reglas

- **Gravedad:** Crítica · **Verificación:** laboratorio sobre 3.1.973 · **Módulo:** pns_ai_mcp (relacionado con PNS-19
  y PNS-108)
- **Ubicación:** `pns_ai_mcp/controllers/context_builder.py:95-97` y `:138-139` (`GuardedSandboxEnv` da `user`,
  `company` y `companies` del entorno real), `:659-660` y `:765-766` (los globales `user` y `company`);
  `models/sandbox_secret_read.py:65-66`. Core: `odoo/api.py:544-548` (`env.user` con `su=True`).
- **Comportamiento:**
  - en Odoo 14, `env.user` devuelve el usuario con `su=True`. El sandbox corre como el usuario que pregunta, pero `user`
    (el global y `env.user`) sale como superusuario, y lo que cuelga de él también: sus relaciones y los registros a los
    que se llega desde ellas se leen sin ACL, reglas ni grupos de campo;
  - en la caja A de 3.1.973, `company` y `companies` ya no salen como superusuario, porque la caja A fija
    `allowed_company_ids` (`utils/one_company.py:66-79`; `controllers/controller_helpers.py:188, 211-217`). Excepción: si
    el usuario no tiene ninguna compañía activa, vuelven a salir de `user`, como superusuario;
  - agravante en 3.1.973: la protección nueva de columnas secretas no actúa en lecturas `su` (`sandbox_secret_read.py:65-66`).
- **Quién:** cualquier usuario del chat, mediante una inyección de prompt.
- **Impacto:** lectura de datos y campos que el usuario no debería ver, con su propia identidad aparente: campos sin
  acceso, como `res.users.totp_secret` de otro usuario, y datos de otros contactos (facturas de un contacto ajeno a
  través de `user.partner_id`).
- **Cómo comprobarlo:** como usuario interno sin privilegios, código del sandbox que lea `totp_secret` de un
  administrador con TOTP a través de `user` (por ejemplo, con `user.browse(<id>)`): se lee sin error. La misma lectura
  con `env['res.users'].browse(<id>)` da `AccessError`.
- **Corrección sugerida:** la de §2.2, punto 1: que `user`, `company` y `companies` del sandbox, y lo que cuelga de
  ellos, salgan de un entorno sin `su`; y que la protección de columnas secretas actúe también en `su` dentro de la caja
  A.
- **En nuestra instalación:** `user`, `company` y `companies` se reconstruyen sin `su`, en el entorno del sandbox y en
  los globales.

### PNS-103 — Un AI Administrator sin Ajustes no puede abrir la revisión ni el resultado de una importación

- **Gravedad:** Baja (funcional, sin efecto de seguridad) · **Verificación:** laboratorio sobre 3.1.973 · **Módulo:**
  pns_base
- **Ubicación:** `pns_base/models/operation_report_wizard.py:349-359` (`_inject_import_preview_arch` y
  `_inject_operation_result_arch`), llamados desde `fields_view_get` (`:371`). Core:
  `odoo/addons/base/security/ir.model.access.csv:34-35`.
- **Comportamiento:** las dos funciones leen la `arch` de `pns_base.view_pns_import_preview_form` y
  `pns_base.view_pns_operation_result_form` con `env.ref(...).arch`, sin `sudo`. El ACL de `base` solo deja leer
  `ir.ui.view` a Ajustes. El resto de `fields_view_get` ya lee las vistas en `sudo`.
- **Quién:** cualquier AI Administrator sin Ajustes, con «Permisos de acceso» o sin ellos.
- **Impacto:** «Review this import» da `AccessError` («You are not allowed to access 'View' (ir.ui.view) records.»), y
  también la vista del resultado. Como «Apply the import» solo está en la revisión, ese usuario no puede importar
  proveedores, usuarios MCP ni nada de lo que pasa por `pns.operation.report.wizard`. No pasaba en 3.1.782: allí la vista
  del resultado se abría por su id, sin leer la `arch`.
- **Cómo comprobarlo:** como AI Administrator sin Ajustes, cargar un archivo de configuración y pulsar «Review this
  import».
- **Corrección sugerida:** leer esas dos vistas en `sudo`, porque son formularios fijos del módulo. La comprobación de
  lectura del asistente ya la hace antes `super().fields_view_get`.
- **En nuestra instalación:** las dos vistas se leen en `sudo`.

### PNS-104 — Cerrar la caja A descarta las escrituras pendientes de quien la abre

- **Gravedad:** Baja (latente) · **Verificación:** tests sobre 3.1.973 · **Módulo:** pns_ai_mcp (relacionado con
  PNS-105)
- **Ubicación:** `pns_ai_mcp/controllers/tools_relaxaicode.py:275` y `utils/skill_runtime.py:262` (`ro_cr.rollback()`
  al cerrar); `controllers/controller_helpers.py:179-238` (`open_readonly_env`, sin `flush` antes de abrir). La abren
  `/mcp` (`controllers/main.py:1648-1650`), el turno de Chatboo (`utils/engine_tool_run.py:28-30`) y las skills
  (`utils/skill_runtime.py:250`). Core: `odoo/sql_db.py:459-468` (`Cursor.rollback` → `clear_env`), `:82-87`;
  `odoo/api.py:620-627, 760-765`.
- **Comportamiento:** en Odoo 14, `Cursor.rollback` vacía la caché, `tocompute` y `towrite` del entorno de ese cursor,
  que son de todo el hilo y no del cursor. `open_readonly_env` no vuelca antes lo pendiente de quien abre la caja A.
- **Impacto:**
  - las escrituras de quien llama que aún no se hayan volcado a la base de datos, de cualquier modelo, se pierden al
    terminar la herramienta, sin error; también los cálculos guardados pendientes y los valores de sus registros
    `new()`;
  - si la caja A lee una columna con una escritura pendiente de quien llama, el `flush` de esa lectura intenta escribirla
    en el cursor `READ ONLY` y falla;
  - hoy ningún llamador real llega a la caja A con escrituras que fueran a durar: el turno de Chatboo deshace su cursor
    al terminar (`pns_ai_chatboo/models/chatboo_async_request.py:531-544`), y `/mcp` y las skills no escriben antes. Por
    eso es latente.
- **Cómo comprobarlo:** en un test, escribir un campo de un registro sin `flush`, abrir y cerrar la caja A
  (`open_readonly_env` y `rollback`) y volcar: el valor nuevo no llega a la base de datos.
- **Corrección sugerida:** `flush()` del entorno de quien llama antes de abrir el cursor de la caja A. Los registros
  `new()` siguen perdiendo sus valores: el `flush` no lo cubre.
- **En nuestra instalación:** se vuelca lo pendiente antes de abrir la caja A, como defensa.

### PNS-105 — Los cursores propios con `commit` confirman y descartan las escrituras pendientes de quien los llama

- **Gravedad:** Alta · **Verificación:** tests sobre 3.1.973 (confirmación de lo pendiente y espera de bloqueo en la
  caja B); la duración de la espera desde el chat, por lectura de código · **Módulos:** pns_ai_mcp, pns_ai_chatboo (la
  otra cara de PNS-26; relacionado con PNS-104)
- **Ubicación:** `pns_ai_mcp/models/ai_log.py:687-856` (`_create_log_entry`: cursor propio con entorno en `:720-722` y
  `commit` en `:847`), llamado en cada `_mcp_log` del motor (`utils/agent_engine.py:703-730`) y en cada
  `_log_mcp_operation` de `/mcp` (`controllers/main.py:111-182`). En la caja B, `models/api_result_cache.py:107-140`
  (`_store`, cursor en `:132-133`) y `utils/session_download.py:365-392` (`_run_on_committed_cursor`, `:382-386`). Core:
  `odoo/sql_db.py:448-457` (`Cursor.commit` → `flush_env`, en `:451`), `:65-80`; `odoo/api.py:760-765`.
- **Comportamiento:**
  - en Odoo 14 la caché, `towrite` y `tocompute` son del conjunto de entornos del hilo, no del cursor. `Cursor.commit`
    hace `flush_env` con el entorno de su cursor: escribe y confirma en su transacción todo lo pendiente del hilo y
    después lo vacía;
  - un cursor propio con `Environment` en el mismo hilo que hace `commit` (por ejemplo, el de `ai.log._create_log_entry`,
    en cada ronda del motor y en cada operación de `/mcp`) tiene tres efectos sobre quien lo llama:
    1. confirma lo pendiente de quien llama, aunque después se deshaga: el `rollback` de `/mcp` al fallar una
       herramienta, el `ROLLBACK TO SAVEPOINT` del motor por herramienta (`utils/engine_tool_run.py:324-358`) y el
       `rollback` final del turno de Chatboo;
    2. pierde sin error lo pendiente sobre registros creados en la transacción de quien llama: el cursor propio no ve la
       fila;
    3. en la caja B, espera de bloqueo. Un paso del plan escribe y deja cálculos guardados pendientes (por ejemplo,
       escribir el correo de un contacto deja pendiente `email_normalized`); un paso `api_call` posterior guarda la
       respuesta con `_store`, y el `commit` de su cursor intenta actualizar una fila que el cursor del plan, en el mismo
       hilo, ya tiene bloqueada. El hilo espera a una transacción que solo él puede terminar, y PostgreSQL no lo detecta
       como interbloqueo. Por lectura, lo mismo puede pasar con las respuestas binarias de `fetch_url` y `api_call`
       (`_run_on_committed_cursor`);
  - hemos contado 24 cursores propios con `Environment` en los módulos; varios siguen este patrón;
  - los tests no lo ven: `_create_log_entry` no escribe con los tests en marcha (`ai_log.py:716`; `utils/compat.py:42-56`).
- **Sin límite en la base de datos:** `_store` no fija `lock_timeout` ni `statement_timeout`; los `SET LOCAL` del cursor
  del plan (`models/safe_operation.py:967-968, 1462-1466`) no actúan mientras su transacción está parada; y con la
  configuración por defecto de PostgreSQL, que es la de nuestros servidores, no hay ningún otro tiempo de espera.
- **Impacto:**
  - efectos 1 y 2: escrituras confirmadas que deberían haberse deshecho, o perdidas sin error;
  - efecto 3, desde «Ejecutar» de la ficha (`controllers/verification_ui.py:78-97`, hilo de la petición HTTP): el worker
    queda bloqueado hasta que Odoo lo mata por `limit_time_real`;
  - efecto 3, desde el chat (autoconfirmación de `safe_plan_request` o `safe_plan_status` en un turno, hilo de
    `pns_ai_chatboo/models/chatboo_job.py:175-226`): por lectura, sin límite hasta que se reinicia el servicio.
    `limit_time_cpu` no cuenta, porque esperar un bloqueo no consume CPU;
  - mientras dura, las filas escritas por el plan siguen bloqueadas y cualquier otra transacción que las toque también
    espera; quedan dos conexiones retenidas y, en el caso HTTP, un worker ocupado. Volver a pedir el plan repite la
    espera;
  - con `idle_in_transaction_session_timeout` activo, PostgreSQL cortaría la conexión del plan; la actualización del
    cursor propio seguiría adelante y se confirmaría fuera del plan (efecto 1).
- **Cómo comprobarlo:**
  - efecto 1: en un test, escribir un campo de un contacto sin `flush`, abrir en el mismo hilo un cursor propio con
    `Environment` y hacer `commit`; deshacer después la transacción del test: el valor está confirmado;
  - efecto 3: plan confirmado con un paso que escribe el correo de un contacto seguido de un paso `api_call` sobre el
    mismo contacto; con un `lock_timeout` corto en la sesión de prueba, la escritura de `_store` termina por tiempo de
    espera; sin él, no termina.
- **Corrección sugerida:** que los cursores propios no compartan con quien los llama el conjunto de entornos del hilo
  (o que escriban por SQL, sin `Environment`), y un `lock_timeout` en los que se abren durante un plan, como ya hace
  `_finalize` de Chatboo.
- **En nuestra instalación:** cada cursor propio trabaja con su propio conjunto de entornos durante su bloque y, al
  salir, se comprueba que no ha cambiado nada de quien lo llama.

### PNS-107 — `iap.account.get` crea y borra cuentas IAP desde la caja A, fuera de su transacción

- **Gravedad:** Baja · **Verificación:** tests sobre 3.1.973 · **Módulo:** pns_ai_mcp, con el módulo `iap` del core (del
  mismo tipo que PNS-07 y PNS-100)
- **Ubicación:** core `odoo/addons/iap/models/iap_account.py:33-77` (`get`, público y `@api.model`): borrado en `sudo`
  en un cursor propio (`:43-53`) y alta en un cursor propio (`:54-73`). `pns_ai_mcp/controllers/validators_base.py:229-266`.
- **Comportamiento:**
  - desde `relaxaicode`, `env['iap.account'].get('<servicio>')` pasa la validación (el nombre `get` es el de `dict.get`,
    que no se puede prohibir en general) y se ejecuta en la caja A; ni el `READ ONLY` ni el `ROLLBACK` de la caja
    alcanzan esos cursores;
  - si hay cuentas del servicio sin token, las borra en `sudo` y confirma; si no hay ninguna, crea una y la confirma, y
    su `account_token` queda en la caché del hilo (`:72-73`; ver PNS-108);
  - llegan también a `get`, sin escribir antes, ocho métodos públicos: `iap.account.get_credits_url` (`:80-87`) y
    `get_config_account_url` (`:126-128`), `res.config.settings.redirect_to_buy_autocomplete_credit`,
    `sms.resend.action_buy_credits`, `mailing.mailing.action_buy_sms_credits`, `sms.composer.action_send_sms` (que
    además envía el SMS) y `action_send_sms_mass_now`, `mailing.sms.test.action_send_sms` y
    `crm.iap.lead.mining.request.action_submit`;
  - por lectura de código, sin probar: leer `res.config.settings.partner_autocomplete_insufficient_credit`
    (`addons/partner_autocomplete/models/res_config_settings.py:9-13`) llama a `get_credits` (`iap_account.py:139`), que
    llama a `get(force_create=False)` (`:140`): borra en `sudo` las cuentas `partner_autocomplete` sin token y, si hay
    cuenta, hace una llamada JSON-RPC a IAP con su token (`:143-153`). Es un campo calculado con efectos al leerlo;
  - `crm.lead.iap_enrich` (`addons/crm_iap_lead_enrich/models/crm_lead.py:49`) también llega a `get`, pero hoy lo frena
    su `SELECT … FOR UPDATE NOWAIT` (`:56-58`) en la transacción `READ ONLY`.
- **Impacto:** cualquier usuario con `relaxaicode` puede crear cuentas IAP vacías fuera del `READ ONLY` de la caja A (el
  ACL del core da el alta a Usuario interno, `1,0,1,0`) y borrar las que no tienen token, que el ACL no le permite. En lo
  que hemos comprobado, sin fuga de secretos ni coste; de ahí la gravedad Baja.
- **Cómo comprobarlo:** en una base de datos sin cuenta IAP de un servicio, código del sandbox, como usuario interno,
  con `env['iap.account'].get('<servicio de prueba>')`: tras el turno, la cuenta existe en `iap_account`.
- **Corrección sugerida:** una lista de métodos por modelo en el sandbox para los métodos del core con nombre común que
  confirman en un cursor propio (`get` de `iap.account`), con sus llamadores públicos, o un inventario de esos métodos;
  y tratar los campos calculados con efectos. A medio plazo, la marca de §2.2, punto 2.
- **En nuestra instalación:** el sandbox rechaza `get` solo sobre `iap.account` y no deja llamar a los ocho métodos
  públicos que llegan a él.

---

## 5. Lo nuevo de 3.1.973 y lo que hemos encontrado al corregir

### 5.1 Hallazgos nuevos (PNS-106, PNS-108, PNS-110, PNS-111 y PNS-112)

Son del código de 3.1.973 o los encontramos al corregir en nuestra instalación y al probarla. PNS-108 es el resto de
PNS-19 con el criterio nuevo de 3.1.973.

| PNS | Gravedad | Módulos | Título | Verificación | En nuestra instalación |
|---|---|---|---|---|---|
| PNS-106 | Baja | pns_ai_chatboo | Imagen del lienzo en un formato que no se reconoce: sale rota | Lectura de código (3.1.973) | Sin corregir |
| PNS-108 | Alta | pns_ai_mcp | La protección de columnas secretas no cubre los valores que ya están en la caché | Tests y laboratorio (3.1.973) | Corregido |
| PNS-110 | Baja | pns_ai_mcp, pns_ai_chatboo | Sin proveedor con el rol Diseño, diseña la cadena de Conversación | Tests y laboratorio con proveedor real (3.1.973) | Configuración |
| PNS-111 | Baja | pns_ai_chatboo, pns_ai_mcp | El botón Canvas no lleva las imágenes a Design | Laboratorio con proveedor real (3.1.973) | Sin corregir |
| PNS-112 | Baja | pns_ai_mcp | Plan que el validador acepta y el core no puede ejecutar, con un resultado que no lo explica | Entorno de pruebas (3.1.973) | Sin corregir |

### PNS-106 — Imagen del lienzo en un formato que `_WEB_IMAGE_RE` no reconoce: sale rota aunque el usuario tenga acceso

- **Gravedad:** Baja · **Verificación:** lectura de código en 3.1.973 · **Módulo:** pns_ai_chatboo (relacionado con
  PNS-111)
- **Ubicación:** `pns_ai_chatboo/models/chatboo_canvas.py:654` (`_WEB_IMAGE_RE`), `:700-711` (`_picture_of`) y
  `:713-738` (`pictures_as_tokens`); CSP de la carcasa, `controllers/chatboo.py:1175-1180`.
- **Comportamiento:** `pictures_as_tokens` solo incrusta como `data:` los valores que `_picture_of` reconoce:
  `/web/image/<modelo>/<id>/<campo>`, `data:image/` o base64. Los demás (`/web/image/<id>`, `/web/image?model=…`,
  `/web/content/…` o una URL absoluta) siguen como texto en la muestra a Design y en `DATA`.
- **Impacto:** si Design pone ese valor en un `<img>`, el marco del lienzo lo pide sin la sesión del usuario (lo medimos
  en el navegador: las peticiones del marco al propio Odoo llegan sin sesión). Sale la imagen rota o la de por defecto,
  aunque el usuario tenga acceso.
- **Cómo comprobarlo:** una página cuyas filas lleven la imagen como `/web/content/<id>` de un adjunto que el usuario
  puede leer: la página la muestra rota.
- **Corrección sugerida:** reconocer también esos formatos (o resolver el adjunto) e incrustarlos como `data:` con los
  permisos del usuario (ver «Imágenes de la página leídas como superusuario», §5.2).

### PNS-108 — La protección de columnas secretas no cubre los valores que ya están en la caché del hilo

- **Gravedad:** Alta (como PNS-19) · **Verificación:** tests sobre 3.1.973, con la caja A real y un usuario interno;
  laboratorio sobre 3.1.973 · **Módulo:** pns_ai_mcp (resto de PNS-19; relacionado con PNS-102 y PNS-107)
- **Ubicación:** `pns_ai_mcp/models/sandbox_secret_read.py:15-16` (el criterio: «Odoo only checks a field when it is not
  in the cache yet»), `:58-63` (sin precarga), `:111-127` (comprobación al leer de la base de datos) y `:50-52`, `:155-163`
  (`_forget_values`, solo para `ir.config_parameter.value`); `controllers/controller_helpers.py:179-238`
  (`open_readonly_env`, sin vaciar la caché). Core: `odoo/fields.py:993-996` (un valor en caché se devuelve sin comprobar
  permisos).
- **Comportamiento:**
  - la protección de 3.1.973 actúa cuando la columna se lee de la base de datos. En Odoo 14, un valor que ya está en la
    caché, o que se calcula en el momento, se devuelve sin comprobar nada; y la caché es una por hilo, para todos los
    cursores;
  - el código que lee una columna secreta en `sudo` la deja en la caché, y la caja A la devuelve después. Lo hemos
    confirmado por cuatro vías que el propio código del sandbox dispara, como usuario interno sin Ajustes ni AI
    Administrator: se lee primero el campo que llena la caché y después la columna secreta, con `rec['campo']` o con
    `mapped` (en V3 y V4, también con `browse(id).campo`):
    - V1: el cálculo de `ai.api.server.auth_call_preview` lee `auth_token` en `sudo` (`models/external_server.py:393`);
      al servidor se llega con un `Reference` (ver abajo);
    - V2: `ai.mcp.user.user_has_mcp_api_key` lee `mcp_api_key_hash` en `sudo` (`models/mcp_user.py:315-322`); también
      con un `Reference`;
    - V3: `res.users.totp_enabled` (core, `auth_totp`) deja `totp_secret`;
    - V4: `res.partner.signup_valid` (core, `auth_signup`) deja `signup_token`;
  - una columna secreta calculada en el momento tampoco pasa por la protección (comprobado con `password` y `new_password`
    de `res.users`);
  - la clave del proveedor que lee el motor: si no hay ningún `commit` ni `rollback` entre esa lectura y la caja A, la
    caja A la devuelve (confirmado en el laboratorio). En los caminos de un turno real que hemos revisado no se alcanza,
    porque el `commit` del registro de cada ronda (`ai.log._create_log_entry`, ver PNS-105) vacía antes la caché. Esa
    protección depende de un efecto lateral. No hemos revisado otros canales (voz), la caché `ormcache` de `get_param`
    ni los métodos con LLM que el propio código de la caja A puede alcanzar;
  - **campo `Reference`:** la puerta de los modelos de credenciales (`RELAXAICODE_CREDENTIAL_MODELS`,
    `controllers/validators_base.py:189-206`) solo mira `env[...]` y `env.get(...)` (`:416-428`). Un `Reference` da un
    registro de cualquiera de esos modelos, por ejemplo `mail.template.preview.new({'resource_ref': '<modelo>,<id>'})`
    (es el camino de V1 y V2). Lo que no sea columna secreta se lee entonces con el ACL del modelo; en la práctica, un AI
    Administrator lee el PIN y la clave de `ai.key.pin.ask` y las claves de `ai.api.key.wizard`, que no tienen nombres de
    columna secreta.
- **Quién:** cualquier usuario del chat, mediante una inyección de prompt (V1 a V4); el `Reference`, con el ACL del modelo
  de credenciales.
- **Impacto:** lectura de credenciales desde la caja A pese a la protección nueva: tokens de servidores de API, el hash de
  la clave MCP, el secreto TOTP y el token de registro de otros usuarios.
- **Cómo comprobarlo:** como usuario interno, código del sandbox que lea `totp_enabled` de un usuario con TOTP y después
  `totp_secret` del mismo usuario: devuelve el valor. Sin la primera lectura, `AccessError`.
- **Corrección sugerida:** la de §2.2, punto 3: comprobar también al leer los valores que están en la caché o que se
  calculan, dentro de la caja A y también en `su`, o vaciar las columnas secretas de la caché al abrir la caja A y después
  de cada lectura en `sudo` hecha dentro de ella. Para los modelos de credenciales, cerrarlos por el modelo del registro,
  no por la forma de llegar a él, o marcar como secretas sus columnas con credenciales.
- **En nuestra instalación:** dentro de la caja A, cada lectura se comprueba con su criterio de columnas secretas y con el
  permiso de lectura del modelo, también si el valor está en caché o se calcula; las columnas secretas se vacían de la
  caché al abrir la caja A y después de cada ayuda del sandbox; y el PIN y las claves de la mesa del PIN y del asistente
  de claves cuentan como columnas secretas.

### PNS-110 — Sin proveedor con el rol Diseño, diseña la cadena de Conversación

- **Gravedad:** Baja (comportamiento) · **Verificación:** tests sobre 3.1.973 y laboratorio con un proveedor real ·
  **Módulos:** pns_ai_mcp, pns_ai_chatboo (relacionado con PNS-18)
- **Ubicación:** `pns_ai_mcp/data/ai_provider_role_data.xml:48-55` (Diseño, con Conversación como alternativa);
  `models/ai_provider_role.py:85-91` (`use_fallback`, activo por defecto) y `:203-208` (`_by_code`, con
  `active_test=False`); `models/ai_execution_engine.py:256-287`; `pns_ai_chatboo/models/chatboo_session.py:1285-1293`
  (`canvas_available`).
- **Comportamiento:**
  - con el rol Diseño sin proveedor, archivado o sin cuota, el motor pide su alternativa y diseña la cadena de
    Conversación del agente de Chatboo o, si ese agente no tiene cadena, cualquier proveedor activo con Conversación o
    sin rol;
  - `canvas_available` es verdadero si alguien cubre Diseño o su alternativa: aparece el botón Canvas aunque no haya
    proveedor de diseño;
  - archivar el rol no sirve: `_by_code` lo sigue encontrando y lee su alternativa. Además, el proveedor pierde el rol y
    entra en la cadena de Conversación como proveedor sin rol;
  - lo único que lo evita es desactivar «Use the fallback» en el rol Diseño. Si el proveedor de Diseño falla en la
    llamada, no se pasa a otro, con o sin alternativa: el failover solo recorre los proveedores con el rol;
  - en una base de datos donde ningún proveedor tenía marcada la casilla «Design» antes de 3.1.973, tras la actualización
    aparece el botón Canvas y diseña el proveedor de conversación. El CHANGELOG anuncia los roles con alternativa, no
    este efecto.
- **Impacto:** el lienzo se diseña con un modelo que el administrador no eligió para eso (por ejemplo, un modelo `lite`,
  con la calidad de PNS-96), sin aviso. Sin efecto de seguridad.
- **Matices:** con la alternativa desactivada y nadie con el rol, la ruta del lienzo acepta la petición aunque no se vea
  el botón y termina sin página, con el motivo «No AI provider is configured for agent pns_ai_chatboo», que es engañoso:
  lo que falta es quien cubra Diseño. La fila de `ai.log` de un diseño fallido no guarda el proveedor ni el modelo
  (`pns_ai_chatboo/models/chatboo_canvas.py:602-613`).
- **Cómo comprobarlo:** sin ningún proveedor con el rol Diseño, abrir Chatboo: aparece el botón Canvas. Pulsarlo en una
  respuesta con tabla: diseña el primer proveedor de Conversación, y el log dice «no provider holds role "design" for
  agent "pns_ai_chatboo"; asking "conversation"».
- **Corrección sugerida:** que la alternativa del rol Diseño venga desactivada, o que la actualización lo avise; que un rol
  archivado no dé su alternativa; y un motivo que diga que falta quien cubra Diseño.
- **En nuestra instalación:** «Use the fallback» desactivado en el rol Diseño y el rol solo en el proveedor que elegimos.

### PNS-111 — El botón Canvas no lleva las imágenes a Design

- **Gravedad:** Baja (funcional) · **Verificación:** laboratorio sobre 3.1.973, con un proveedor real · **Módulos:**
  pns_ai_chatboo, pns_ai_mcp (relacionado con PNS-106)
- **Ubicación:** `pns_ai_mcp/utils/relaxaicode_render_table.py:326-336` (`_chart_dataset_rows`);
  `pns_ai_chatboo/static/src/js/chatboo_charts.js:3070-3076` (el botón llama a `/chatboo/canvas/build`).
- **Comportamiento:** el botón Canvas manda al servidor el `data-ai-dataset` de la tabla, que `_chart_dataset_rows` deja
  sin las columnas de imagen (y sin `id` ni las claves `_…`), porque es el conjunto de datos de los gráficos. Design no
  recibe las fotos y la página sale con iniciales. Una página pedida en el turno del chat sí lleva las imágenes.
- **Impacto:** funcional: «Tabla de 5 contactos con su país y su foto» → Canvas → página sin fotos.
- **Cómo comprobarlo:** con ese mismo ejemplo.
- **Corrección sugerida:** que el botón Canvas mande también las columnas de imagen, como referencia que el servidor
  incruste con los permisos del usuario.

### PNS-112 — Plan que el validador acepta y el core no puede ejecutar, con un resultado que no lo explica

- **Gravedad:** Baja · **Verificación:** entorno de pruebas sobre 3.1.973, con un proveedor real · **Módulo:** pns_ai_mcp
- **Ubicación:** `pns_ai_mcp/controllers/safe_plan_execute.py:184` (`recs.write(vals)`); el resultado, en
  `models/safe_operation.py:1528` → `_release_execute_claim` (`:1297-1320`), que guarda `str(exc)`. Core:
  `addons/mail/models/mail_message.py:598` (`create`) → `:1195` (`_get_reply_to`).
- **Comportamiento:** pedida una nota en el chatter de un contacto, el modelo propuso un `write` sobre `res.partner` con un
  `mail.message` dentro de `message_ids`. El validador lo aceptó y un administrador lo confirmó. La ejecución falló en el
  core: sin `model` en los valores, `records` es un `mail.thread` vacío y a `_notify_get_reply_to(...)[res_id]` le falta la
  clave (`KeyError`).
- **Impacto:** no queda nada a medias (no se crea ningún `mail.message`), pero el resultado guardado es solo `str(e)`
  (`{"error": "14", …}`, el id del contacto): ni el usuario ni el AI Administrator ven por qué falló.
- **Cómo comprobarlo:** un plan con un paso `write` de `res.partner` con `message_ids: [(0, 0, {'body': '…'})]`: el
  validador lo acepta y, al confirmarlo, la operación queda cancelada con el error «<id del contacto>».
- **Corrección sugerida:** que el validador rechace las escrituras de `mail.message` a través de `message_ids` (o las
  reescriba como `create` de `mail.message` con `model` y `res_id`), y que el resultado guarde el tipo de la excepción y un
  mensaje útil.

### 5.2 Defectos que hemos corregido en nuestra instalación y no les habíamos comunicado

Siguen abiertos en el código de 3.1.973. Una ficha breve por defecto.

**Imágenes de la página leídas como superusuario** (Media)
- **Qué pasa:** las imágenes de las filas (`/web/image/<modelo>/<id>/<campo>`) se incrustan en la página leyendo el
  registro con el entorno de la sesión, que viene en `sudo`: `_page_html` (`pns_ai_chatboo/models/chatboo_session.py:937`)
  y `open_page` (`models/chatboo_canvas.py:910`), con la sesión de `_session_of_this_turn` (`:639`). La lectura
  (`_web_image_picture`, `:677-698`, cuyo comentario dice «read as the user») no pasa por ACL, reglas ni grupos de campo.
  `_page_url` y `_page_edit` ya son privados (`chatboo_session.py:891, 962`), pero el código del turno sigue llegando a
  ellos por las ayudas del lienzo.
- **Impacto:** la página muestra imágenes de registros que el usuario no puede leer, también de una compañía que no es
  suya: lo medimos con tres compañías, y 3.1.973 muestra la imagen de la ajena.
- **Corrección sugerida:** leer las imágenes sin `su` y en las compañías de la pantalla. Es lo que hacemos: las imágenes
  de registros que el usuario no puede leer no se incrustan.

**Páginas compartidas: lectores y regla del AI Administrator** (Baja)
- **Qué pasa:** 3.1.973 ya reserva al sistema el alta y la escritura de `design` y `owner_id`
  (`pns_ai_chatboo/models/chatboo_canvas_page.py:71-94`), con un criterio más amplio que el nuestro en `owner_id`. Quedan
  dos cosas:
  - los lectores (`user_ids`) solo se limitan a usuarios internos con el `domain` del campo (`:46-52`), que no actúa por
    RPC: el dueño puede añadir un usuario de portal, que recibe el aviso (por correo, si lo tiene así) aunque no pueda
    abrir la página;
  - la regla del AI Administrator da escritura y alta sobre todas las páginas (`security/security.xml:67-76`): puede
    cambiar el nombre y los lectores de páginas ajenas, y avisar a quien quiera.
- **Impacto:** avisos a usuarios externos con un enlace a una página que no pueden abrir; cambios en páginas ajenas sin
  que lo sepa su dueño.
- **Corrección sugerida:** comprobar en el servidor, también en `sudo`, que los lectores son usuarios internos; y que la
  regla del AI Administrator solo dé lectura y borrado. Es lo que hacemos.

**El lienzo ejecuta lo que traen los valores de las filas y puede pedir al propio Odoo** (Media)
- **Qué pasa:**
  - las filas y el título se escriben dentro de `<script>` con `json.dumps`, que no escapa `<`
    (`pns_ai_chatboo/models/chatboo_canvas.py:1097, 1426, 1439, 1733`; el vigilante de `:2194` cambia `</` por `<\/`, lo
    que no cubre `<!--<script`). Un valor como `</script><script>…` cierra el bloque y ejecuta lo que sigue, dentro del
    marco;
  - Design recibe la muestra de las filas sin escapar (`sample_figures_for_design`, `:829-858`) y puede copiarla en
    `const DATA`. Si un valor corta el `<script>`, el servidor no sustituye `DATA` y se guarda el texto del modelo con el
    valor en crudo: la página guardada no se comprueba (`place_rows_on_page`, `:2062-2105`);
  - **el valor puede venir de fuera:** un usuario de portal lo puso en la ciudad de su ficha («Mi cuenta») y se ejecutó en
    el lienzo de un administrador. La regla de `account` solo impide cambiar el nombre, el NIF y la empresa cuando hay
    facturas; la calle, la ciudad y los demás campos de texto llegan a la página igual;
  - la CSP de 3.1.973 (cabecera de la carcasa, `controllers/chatboo.py:1175-1180`) bloquea lo externo, pero permite
    `'self'` en `img-src` y `connect-src`: el marco puede pedir al propio Odoo (en el navegador, las imágenes llegan sin
    sesión, y el `fetch` sale aunque CORS no deja leer la respuesta). No impide que el marco navegue a una web externa;
  - las dos descargas no llevan CSP (`controllers/chatboo.py:1283-1300, 1306-1328`): abiertas desde el disco, el navegador
    intenta las peticiones externas;
  - el dueño puede escribir cualquier HTML en `canvas_design` de su sesión por RPC y compartirlo: la ruta de compartir crea
    la página en `sudo` con ese diseño (`controllers/chatboo.py:1228`), y se ejecuta en el navegador del otro usuario,
    dentro del marco. 3.1.973 cierra esta vía por la página (`_SYSTEM_FIELDS`), pero no por la sesión.
- **Impacto:** quien pueda poner texto en un registro que acabe en una página, también un usuario de portal, puede
  ejecutar un script en el marco de la página de otro usuario y llevarlo a una web externa, dentro de la carcasa de Odoo.
  Alcanza a las páginas compartidas y a las descargas.
- **Corrección sugerida:** escapar `<`, `>`, `&`, U+2028 y U+2029 en todo JSON escrito dentro de un `<script>`; no
  guardar un `DATA` que no haya escrito el servidor (en su lugar, la tabla de rescate); la misma CSP dentro del documento
  servido y en las descargas, sin `'self'`; y que `canvas_design` de la sesión no se pueda escribir por RPC. Es lo que
  hacemos, salvo lo último: en nuestra instalación la vía de la sesión sigue abierta, con el alcance limitado por la CSP,
  también en las descargas.

### 5.3 Lo que 3.1.973 corrige sin habérselo comunicado

Defectos que habíamos encontrado sin comunicárselos todavía; seis de ellos ya los habíamos corregido en nuestra
instalación. Los hemos comprobado en 3.1.973 y están corregidos. Una línea por defecto, para cerrar el hilo.

| Defecto | Gravedad | Cómo lo corrige 3.1.973 |
|---|---|---|
| PNS-101: la caja A llegaba a los entornos reales del hilo (`env.all`, `env.cache`) y, desde ellos, al cursor de la petición y a entornos con `su` | Crítica | `GuardedSandboxEnv` con lista blanca y bloqueo por clase de cursores, entornos, caché y registro (`pns_ai_mcp/controllers/context_builder.py:71-199`). Comprobado con nuestros tests negativos |
| Plan con la identidad de otro usuario (`create` de `ai.safe.operation` y `cleanup_stuck_state` públicos) | Crítica | `create` solo en `su` (`pns_ai_mcp/models/safe_operation.py:545-551`), `_cleanup_stuck_state` privado (`:1030-1031`) y el plan corre como su solicitante (`:1435-1440`) |
| Borrado de los contextos de fábrica por un método público | Alta | `_unlink_retired_from_module`, privado (`pns_ai_mcp/models/ai_context_disk.py:751`) |
| Un AI Administrator sin Ajustes podía generar, fijar o importar la clave MCP de un administrador de Ajustes | Alta | Corregido en 3.1.972 (`pns_ai_mcp/models/mcp_user.py:740-781`; también en `create`, `write` y la importación de configuración) |
| El asistente de exportación de `pns_base` borraba en `sudo` cualquier adjunto (bastaba crearlo apuntando a él) | Alta | Solo borra adjuntos de exportación del propio usuario (`pns_base/models/export_file_wizard.py:19-27`; 1.2.53) |
| `paint_canvas` público: escritura del lienzo de otro usuario | Media | `_paint_canvas`, privado (`pns_ai_chatboo/models/chatboo_session.py:1066`) |
| Los `log_*` del motor, públicos: filas de historial a nombre de otro usuario | Media | Los seis, privados (`pns_ai_mcp/models/ai_execution_engine.py:425-781`) |
| `chat_completion` del motor, público: llamadas directas al proveedor | Baja | `_chat_completion`, privado (`pns_ai_mcp/models/ai_execution_engine.py:872`) |
| Orden por una columna secreta desde la caja A | Baja | Da `AccessError` (`pns_ai_mcp/models/sandbox_secret_read.py:74-91`) |
| `iap.account.account_token` legible desde la caja A | — | Es columna secreta por su nombre (`pns_ai_mcp/utils/sandbox_secrets.py:21-44`) |

---

## 6. Actualización desde versiones anteriores

Hemos actualizado a 3.1.973 desde 3.1.879 (en el laboratorio, con bases de datos instaladas con 3.1.879, y en el
entorno de pruebas, el 18/11) y desde 3.1.782 (en una copia de una base de datos de producción de un cliente, el 19/11,
y en producción, el 20/11). La actualización en sí termina sin errores en el log en todos los casos. Este apartado recoge lo
que hace con los datos y que conviene corregir o, al menos, anunciar en las notas de versión.

Rutas relativas a la raíz de los módulos, como en §4.

### 6.1 Hallazgos nuevos (PNS-109, PNS-113 y PNS-114)

| PNS | Gravedad | Módulos | Título | Verificación | En nuestra instalación |
|---|---|---|---|---|---|
| PNS-109 | Baja | pns_ai_mcp | Tras actualizar, los dos crons de purga de cachés llaman a un método que ya no existe | Laboratorio, entorno de pruebas y copia de producción (3.1.973) | Corregido |
| PNS-113 | Media | pns_base | Actualizar el idioma con sobrescritura cambia traducciones de otros módulos | Copia de producción (3.1.973) | Procedimiento |
| PNS-114 | Baja | pns_ai_mcp | La conversión de las casillas `fit_*` en roles no comprueba el protocolo | Copia de producción (3.1.973) | Procedimiento |

### PNS-109 — Tras actualizar, los dos crons de purga de cachés llaman a un método que ya no existe

- **Gravedad:** Baja (actualización) · **Verificación:** laboratorio (actualización desde 3.1.879, con y sin nuestra
  corrección), entorno de pruebas y copia de producción, sobre 3.1.973 · **Módulo:** pns_ai_mcp
- **Ubicación:** `pns_ai_mcp/data/fetch_cache_cron.xml:2, 10` y `data/api_result_cache_cron.xml:2, 10` (datos
  `noupdate="1"`, con `model._gc_expired()`); `models/fetch_cache.py:135` y `models/api_result_cache.py:146`
  (`_gc_expired`); `models/api_result_cache.py:58-60` (`init`, que solo revive el cron de esa caché si está gastado).
- **Comportamiento:** en 3.1.879 los dos crons de purga (`ir_cron_ai_fetch_cache_gc` e `ir_cron_ai_api_result_cache_gc`)
  llaman a `model.gc_expired()`. 3.1.973 hace privado el método y cambia el código del cron en los datos, pero los datos
  son `noupdate`: en una base de datos actualizada el cron conserva `model.gc_expired()`, que ya no existe. En una
  instalación nueva los dos crons quedan bien.
- **Impacto:** los dos crons fallan en cada pasada y las cachés de `fetch_url` y de las llamadas a API dejan de purgarse.
  Sin efecto de seguridad.
- **Cómo comprobarlo:** en una base de datos instalada con 3.1.879, actualizar a 3.1.973 y consultar el campo `code` de
  esos dos `ir.cron`: `model.gc_expired()`.
- **Corrección sugerida:** fijar el código de los dos crons por su XML ID en un script de migración o en su `init()`.
- **En nuestra instalación:** un script posterior a la migración corrige el código de los dos crons cuando sigue
  llamando al método antiguo. Comprobado en los tres entornos y en producción.

### PNS-113 — Actualizar el idioma con sobrescritura cambia traducciones de otros módulos

- **Gravedad:** Media (cambia textos de toda la instalación, no solo de los `pns_*`) · **Verificación:** copia de una
  base de datos de producción, con 3.1.973 y el core de nuestros servidores · **Módulo:** pns_base (afecta a los tres
  `pns_*`)
- **Ubicación:** `pns_base/models/ir_translation.py:54-111` (`_pns_dedupe_import_rows`: solo descarta un duplicado
  cuando las dos filas son de módulos `pns*`, `:88-89` y `:97-98`). Core: la importación de traducciones con
  sobrescritura de Odoo 14 (`ON CONFLICT (type, lang, md5(src)) … DO UPDATE`, que el propio docstring de
  `ir_translation.py:6-15` describe).
- **Comportamiento:**
  - en Odoo 14 una traducción de tipo `code` es una sola fila por texto inglés e idioma, la use el módulo que la use;
  - para que los textos que ustedes cambian en los `pns_*` sustituyan a los ya instalados hay que actualizar el idioma con
    sobrescritura (la actualización del módulo no lo hace). Con sobrescritura, el core actualiza la fila existente:
    conserva su `id` y cambia `module` y `value`;
  - cuando un `.po` de los `pns_*` trae un texto inglés que ya tradujo otro módulo, su traducción sustituye a la de ese
    módulo en toda la instalación. La deduplicación de `pns_base` solo actúa entre filas de los propios `pns_*`.
- **Impacto:** en la copia de producción, recargar `es_ES` con sobrescritura para los tres `pns_*` cambió 49
  traducciones de otros módulos: 13 con otro texto (la redacción de los `pns_*` pasa a verse en menús, campos y
  mensajes de otros módulos) y 36 que solo pasan a figurar como de los `pns_*`. Lo mismo pasaría con la recarga completa
  del idioma desde Ajustes. Sin una copia previa de esas filas no se puede deshacer.
- **Cómo comprobarlo:** en una base de datos con otros módulos traducidos al español, guardar `ir_translation` de
  `es_ES` y tipo `code`, actualizar el idioma con sobrescritura y comparar las filas cuyo `module` no empieza por `pns`.
- **Corrección sugerida:** que los `.po` de los `pns_*` no traduzcan con otra redacción textos ingleses de otros
  módulos, o que su importación no sobrescriba filas de otros módulos. Y avisarlo en las notas de versión mientras tanto.
- **En nuestra instalación:** sin corrección en el código. En la actualización, después de recargar el idioma
  restauramos por su `id` las filas de otros módulos que la recarga había cambiado.

### PNS-114 — La conversión de las casillas `fit_*` en roles no comprueba el protocolo

- **Gravedad:** Baja (actualización) · **Verificación:** copia de una base de datos de producción, sobre 3.1.973 ·
  **Módulo:** pns_ai_mcp (relacionado con PNS-110)
- **Ubicación:** `pns_ai_mcp/utils/schema_fossils.py:290-342` (`stash_fit_columns` y `promote_fit_columns`, por SQL);
  `models/ai_provider.py:613-634` (`_check_roles_match_protocol`) y `:665-675` (`_choose`);
  `lib/llm/drivers/systemone_driver.py:17` (`chooses = True`).
- **Comportamiento:** la actualización a 3.1.973 pasa cada casilla `fit_*` al rol del mismo código, por SQL y sin mirar
  el protocolo del proveedor. Un proveedor `openai` con `fit_decision` queda con el rol Decisión, que solo admite un
  driver que elige (`chooses`).
- **Impacto:** cualquier escritura de `role_ids` de ese proveedor da `ValidationError` hasta quitarle Decisión: el
  administrador no puede, por ejemplo, darle el rol Diseño sin quitarle antes Decisión, y el mensaje no dice que el rol
  viene de la actualización. Si el proveedor estuviera activo y el motor le pidiera una decisión, `_choose` daría
  `DecisionCallError`. En la copia de producción le pasó a un proveedor, inactivo.
- **Cómo comprobarlo:** en una base de datos de 3.1.782 o 3.1.879 con un proveedor `openai` con la casilla Decisión,
  actualizar a 3.1.973 y escribir sus roles: `ValidationError`.
- **Corrección sugerida:** que la conversión no asigne Decisión a un proveedor cuyo protocolo no la admite (y lo
  registre en el log), o que la valide como la escritura.
- **En nuestra instalación:** en la actualización quitamos Decisión a ese proveedor en la misma escritura en que le dimos
  Diseño.

### 6.2 Observaciones de la actualización

1. **La nota sobre `ai_log.agent_id` no es cierta.** Su nota del 20/10 dice que la actualización ya no borra la
   columna, y el comentario de 3.1.973 (`pns_ai_mcp/utils/schema_fossils.py:50-52`) dice que se queda hasta que
   alguien la borre. No es así: el campo ya no existe en el modelo desde 3.1.879 (`models/ai_log.py`), y Odoo 14 borra al
   final de la actualización la columna de un campo almacenado que el módulo ya no declara (en el log, «Deleting field
   ai.log.agent_id»). Lo vimos al actualizar desde 3.1.782: en el laboratorio, hacia 3.1.879, se perdió el agente de
   978 de 987 filas; en la copia de producción, hacia 3.1.973, el log muestra el mismo borrado. Desde 3.1.879 ya no
   aplica: la columna la borró la actualización anterior. **Petición:** corregir la nota y el comentario y, si el dato
   importa, conservarlo con un script de migración.
2. **El agente «Decision» queda huérfano.** 3.1.782 sembraba el agente `pns_ai_decision` en datos `noupdate` y tomaba de
   él la cadena de decisión. 3.1.879 y 3.1.973 no lo siembran ni lo usan: la decisión sale de la cadena del agente que
   llama, filtrada por el rol Decisión. Odoo 14 no borra los registros `noupdate`, así que el agente sigue en la base de
   datos y lo configurado en su cadena deja de usarse sin aviso. No figura en las notas de versión. No hemos probado qué
   pasa si ningún proveedor de la cadena del agente tiene el rol. **Petición:** anunciarlo y retirar o archivar el agente
   en la actualización.
3. **Numeración de `pns_base`.** Con 3.1.879, `pns_base` llegaba como 1.2.47, que en su registro de entregas era el
   número de Odoo 19 de aquella entrega. Con 3.1.973, el CHANGELOG etiqueta las publicaciones por pila (`owl1-1.2.69_…`)
   y 1.2.69 es la de Odoo 14 y 15. Queda aclarado; lo anotamos para cerrar el punto, sin petición.
4. **Skills con `required_groups` en 3.1.879.** En una instalación nueva de 3.1.879, las skills `sys_info`, `users_all`
   y `users_logged` de Chatboo no se importaban: declaraban `required_groups`, una capacidad que el motor de 3.1.879 no
   publicaba (`_raise_unpublished_capability`, `pns_ai_mcp/models/ai_skill.py:409` de 3.1.879). La importación lo dejaba
   en un mensaje INFO, con tres errores en cada instalación. 3.1.973 retira esas tres skills y su motor ya lee
   `required_groups` (`models/ai_skill.py:307-309`). Efecto en la actualización: en una base de datos instalada con
   3.1.879 esas tres skills no existen, así que se retiran 4 de las 7 skills de fábrica que 3.1.973 quita; en una que
   venga de antes, las 7 (comprobado en una copia del entorno de pruebas). Sin petición.
5. **`unit_tests/`.** Las notas de versión siguen citando tests en `unit_tests/` que no vienen en el paquete
   (PNS-50, §3.3). Sin petición.

---

## 7. Qué hemos probado y qué no

### 7.1 Salvedad: lo que no hemos vuelto a revisar en 3.1.973

De los 84 corregidos de §3.1, **53 no los hemos vuelto a revisar en 3.1.973**: los dimos por corregidos al comprobarlos
en 3.1.879 (40) o en 3.1.782 (13), y 3.1.973 no toca su código o son de gravedad media o baja. En la tabla de §3.1
figuran con la verificación «3.1.879 (sin revisar en 3.1.973)» o «3.1.782 (sin revisar en 3.1.973)»:
- **3.1.879 (40):** PNS-22, 31, 32, 35, 38 a 43, 46, 49, 62, 64 a 66, 68, 72 a 74, 76, 85 a 87, 89 a 93 y 95, y las
  observaciones 1 a 5 y 8 a 12 de la entrega del 16/10;
- **3.1.782 (13):** PNS-34, 44, 45, 47, 48, 52, 63, 67, 69, 71, 75, 78 y 79.

De las 40, 3.1.973 toca el código de dos y las miramos por encima: PNS-35 sigue corregido (prefijo `'` en
`pns_ai_mcp/utils/artifact_export_table.py:285` y `controllers/formatters.py:73`); en PNS-41, los tres `website`
apuntan fuera, y por lectura la ficha de Aplicaciones deja de mostrar el `index.html` del módulo (sin comprobar en la
interfaz).

Los corregidos críticos y altos sí los revisamos en 3.1.973: los 20 que dimos por corregidos en 3.1.782 y los 9 de
3.1.879 cuyo código cambia. Siguen corregidos, sin regresiones (PNS-80 ya no aplica).

### 7.2 Qué hemos probado

- **Revisión del código** de 3.1.973 frente a 3.1.879, hallazgo por hallazgo, para todo lo que estaba abierto, los
  corregidos de gravedad crítica o alta cuyo código cambia y la superficie nueva (§5).
- **Laboratorio** (Odoo 14 con Python 3.7.3, bases de datos de prueba), con dos versiones del core: la de la imagen
  oficial (14.0.20231106) y la de nuestros servidores (`cc0060e`). Usuarios internos con y sin AI Administrator, Ajustes
  y «Permisos de acceso», usuarios de portal y tres compañías.
- **Sus tests sobre 3.1.973 sin ninguna corrección:** 246 tests, 0 fallos, 0 errores y 4 saltados (uno necesita Chrome).
- **Nuestra batería sobre 3.1.973 con nuestras correcciones** (sus tests más los nuestros, incluidos negativos por vía
  para la caja A): 580 tests, 1 fallo por diseño (`test_paap_i7_cusp_roles_out_of_reach_of_an_ai_admin`, §3.2, PNS-01
  y PNS-02), 0 errores y 6 saltados, igual con los dos cores.
- **Navegador:** el lienzo y su CSP, la tarjeta de confirmación, Chart.js y las exportaciones, en el laboratorio y en el
  entorno de pruebas.
- **Proveedor de IA real:** Google Gemini por el protocolo compatible con OpenAI, en el laboratorio y en el entorno de
  pruebas (2 workers, datos de demostración).
- **Actualización:** desde 3.1.879 en el laboratorio (instalación limpia y bases de datos instaladas con 3.1.879) y en
  el entorno de pruebas; desde 3.1.782 en una copia de una base de datos de producción y en producción (§6).

### 7.3 Lo que no hemos probado o no fue concluyente

| Comprobación | Hallazgo | Situación y motivo |
|---|---|---|
| Huérfanos de la vía de respaldo de `_finalize` en 3.1.973 | PNS-98 | **No reproducido:** lo vimos en 3.1.879; `_finalize` cambia en 3.1.973 y lo damos por lectura. |
| `user.remove_group` en 3.1.973 | PNS-99 | **Por lectura:** probado en el laboratorio sobre 3.1.879; el código de 3.1.973 es el mismo en lo que importa. |
| Salida real a la red desde la caja A | PNS-100 | **Con los métodos sustituidos**, sin envío ni conexión reales (en modo test, Odoo no conecta). |
| Duración de la espera de bloqueo desde el chat | PNS-105 | **Por lectura:** confirmada por test desde la ficha de la operación; desde el chat, deducida del código. |
| Lectura del campo calculado de `partner_autocomplete` y `iap_enrich` | PNS-107 | **Por lectura;** `get` probado por test. |
| Clave del proveedor en un turno real; otros canales (voz), la caché `ormcache` de `get_param` y los métodos con LLM alcanzables desde la caja A | PNS-108 | **No revisados.** En los caminos de un turno que revisamos no se alcanza (§5.1). |
| Tokens de escritura en la caché de prompt de Anthropic | PNS-29 | **No realizada:** solo hemos usado Gemini. |
| Otros protocolos (Anthropic, OpenAI nativo, el de decisión) | — | **No probados** con un proveedor real. |
| Fallo de serialización de «Ejecutar» en la ficha | Anexo de PNS-26 | **Reproducido** por test y en el laboratorio sobre 3.1.973; en el entorno de pruebas del 18/11, una ejecución no lo reprodujo. |
| Carga de la sesión tras un turno | §8, 19 | **No repetido** en 3.1.973: lo vimos en 3.1.879 y el código no cambia. |
| Agente «Decision» sin ningún proveedor con el rol | §6.2, 2 | **No probado.** |
| Medida de PNS-113 en otras bases de datos | PNS-113 | **Solo medido** en la copia de producción. |
| Tests que cambian la clave del administrador; registro del prompt | Obs. 13; petición de §5 | **No localizados cambios;** no comprobado. |
| Voz | PNS-64 | **No probada.** |
| Otras versiones de Odoo | — | **Solo Odoo 14.** Las líneas del core citadas son de la imagen oficial (14.0.20231106), salvo donde se indica. |

Les comunicaremos cualquier resultado posterior que cambie lo dicho en este informe.

---

## 8. Observaciones menores

Sin número. Ninguna es urgente; las recogemos para una próxima versión. Las hemos visto en 3.1.879 o en 3.1.973 y, salvo
donde se indica, el código de 3.1.973 es el mismo.

### 8.1 Riesgos menores

1. **`cron_maintenance` es público** (`pns_ai_chatboo/models/chatboo_async_request.py:1621`, con `commit` del cursor
   de quien llama en `:1639`). Cualquier usuario interno puede, por RPC, adelantar lo que hace el cron: reclamar
   trabajos, purgar con sus reglas y limpiar sesiones con la retención configurada. Nada que el cron no haga. En
   nuestra instalación lo aceptamos. **Sugerimos** hacerlo privado, con el cuidado de PNS-109: el cron está en datos `noupdate`.
2. **`get_usd_fx` descarga sin control de host** (`pns_ai_mcp/models/ai_fx_source.py:87`, público; `_fetch_rates`,
   `:73-84`, con `urllib.request.urlopen`; `_check_url`, `:49-56`, solo exige `http(s)://`). La URL la fija un AI
   Administrator y cualquier usuario interno dispara la descarga por RPC (una vez al día, por la caché). Permite un
   sondeo limitado de la red interna. En nuestra instalación lo cerramos dentro de la caja A y aceptamos el RPC.
   **Sugerimos** usar en `_fetch_rates` `request_public_http` (`utils/fetch_url_safe.py:137`), que ya rechaza hosts no
   públicos y limita el tamaño.
3. **Cuerpo y consulta en las redirecciones** (resto de PNS-17). `request_public_http` conserva `data` y `params`
   (`pns_ai_mcp/utils/fetch_url_safe.py:157-160`) en cada salto, salvo en un 303 (`:188-190`). El host del salto tiene
   que ser público y lo elige el servidor que redirige, que ya recibe esos datos. Aceptado en nuestra instalación.
   **Sugerimos** quitarlos al cambiar de host, como las cabeceras.
4. **La autenticación MCP no consulta el estado de la clave.** Busca por el hash (`pns_ai_mcp/controllers/main.py:480,
   698, 846`), y `mcp_api_key_state` (`models/mcp_user.py:122`) solo es de solo lectura en la vista: un AI
   Administrator puede escribir `not_generated` por RPC dejando el hash, y la clave sigue valiendo aunque la ficha diga
   «sin generar». Requiere AI Administrator, que ya gestiona las claves. **Sugerimos** que el estado se calcule del hash
   o que la autenticación lo compruebe.
5. **Un rechazo de escritura cancela todas las verificaciones pendientes del usuario.** Cuando un usuario sin AI Writer
   intenta escribir con `relaxaicode` o con una herramienta de `/mcp`, se cancelan todas sus verificaciones pendientes,
   no solo la del intento (`pns_ai_mcp/controllers/relaxaicode_prepare.py:363-364`; `controllers/main.py:1293` y
   `:1653-1655`). Solo afecta a las suyas.
6. **`log_no_page` escribe en `ai_log` desde la caja A.** `log_no_page` (`pns_ai_chatboo/models/chatboo_canvas.py:587-616`)
   escribe por `_create_log_entry`, que confirma en su propio cursor (`pns_ai_mcp/models/ai_log.py:687-856`, `commit` en
   `:847`): las filas quedan aunque la caja A o el turno se deshagan. Para un registro puede ser lo que se busca, pero es
   el mismo patrón de PNS-105.
7. **Caché del agente confirmada durante «Review».** Al revisar una importación, `get_content`
   (`pns_ai_mcp/models/ai_agent.py:1213-1245`) guarda la caché del agente con `_persist_cache_isolated`, en un cursor
   propio que confirma (`:1394-1410`). La importación se deshace, pero la caché queda con contenido de la importación;
   `get_content` la descarta si cambia la firma de los contextos (`:1232`). No hemos comprobado si puede esperar por el
   bloqueo de la fila. **Sugerimos** no persistir la caché durante la vista previa de una importación.
8. **Camino real a `too_soon` en la tarjeta.** Si la tarjeta del chat llega sin token (`_mint_card_token` no lo genera,
   `pns_ai_mcp/utils/engine_tool_run.py:539-563`), no entra en `held` (`pns_ai_chatboo/static/src/js/chatboo_component_v2.js:2190-2200`).
   Al volver a abrir el panel, la restauración genera un token y se lo pone a la tarjeta ya pintada sin volver a
   deshabilitar el botón (`:2308-2316`): un clic en los 5 segundos siguientes, en una operación de riesgo alto, da
   `too_soon`. 3.1.973 reintenta solo tras `too_soon` (`_retryRefusedCard`, `:2258-2304`), así que el usuario solo ve una
   espera. **Sugerimos** reiniciar la cuenta atrás de la tarjeta cuando recibe un token nuevo.

### 8.2 Lienzo

9. **`keys` en la muestra para Design.** `sample_figures_for_design` (`pns_ai_chatboo/models/chatboo_canvas.py:829-858`)
   enseña a Design una propiedad `keys` (`:847`) que el `DATA` que escribe el servidor no tiene (`_flat_rows`, `:1408`;
   `_payload_for_const_data`, `:1415`). Los diseños que leen `keys` salen vacíos y los salva la tabla de rescate.
   **Sugerimos** añadir `keys` a lo que escribe el servidor o quitarlo de la muestra.
10. **Nombre de la descarga.** La descarga de la página de una sesión se llama como la conversación, no como la página
    (`download_filename(session.canvas_title, …)`, `pns_ai_chatboo/controllers/chatboo.py:1324`). Cosmético.
11. **Hasta tres llamadas a Design por edición.** `_paint_canvas` (`pns_ai_chatboo/models/chatboo_session.py:1066`)
    pide el cambio (`:1103`) y, si no encaja o las cifras no están centralizadas, vuelve a maquetar la página entera
    (`:1125` y `:1163`). Tiempo y cuota del proveedor de diseño en cada edición.
12. **Librerías externas: el lienzo y la descarga se comportan distinto.** Las reglas que recibe Design
    (`_PAGE_RULES`, `pns_ai_chatboo/models/chatboo_canvas.py:25-81`) no prohíben cargar librerías de un CDN, y la CSP
    del marco (`script-src 'unsafe-inline'`, `controllers/chatboo.py:1175-1180`) las bloquea. Un diseño con una librería
    externa sale sin gráficos en el lienzo y con gráficos en la descarga, que no lleva CSP (§5.2). **Sugerimos** decirlo
    en las reglas.
13. **El error del botón Canvas no se ve.** Cuando el trabajo termina en error («No page was built. The reason is in the
    AI History.», `pns_ai_chatboo/models/chatboo_canvas_job.py:133, 156`), `paintCanvasButton`
    (`static/src/js/chatboo_charts.js:2971-2993`) solo pone el borde del botón en rojo, vuelve a la etiqueta «Canvas» y
    deja el motivo en el `title`. No hay aviso en pantalla; en el entorno de pruebas no salió ni el tooltip.
    **Sugerimos** un aviso en el chat, como el que pedimos en PNS-96. Además, el aviso remite a un «AI History»
    («Historial IA» en español) que no existe como menú: el registro está en «My Activity» y en «Activity», bajo
    Seguridad (`pns_ai_mcp/views/ai_log_views.xml:281-293`), y un usuario con solo AI Conversational no ve ninguno de
    los dos. En nuestra instalación usamos el mismo aviso en la respuesta del chat (PNS-96). **Sugerimos** nombrar el
    menú real o indicar que lo consulte un administrador.
14. **Idioma de las palabras de `page_tab`.** `get_discovery_entries` (`pns_ai_mcp/models/ai_context_discovery.py:59-66`)
    usa las palabras del idioma del usuario y, si no hay variante, las genéricas en inglés
    (`pns_ai_chatboo/ai/contexts/discovery/discovery_page_tab.json`). Un usuario con la interfaz en inglés que escribe en
    español («Hazme una página…») no activa `page_tab`. **Sugerimos** tener en cuenta también el idioma en que se
    escribe, o todas las variantes publicadas.

### 8.3 Chat y exportación

15. **La nota «incomplete response» no se ve.** La nota que se añade a una respuesta recuperada tras un reinicio va en
    `content`, pero `original_content` se queda con el texto sin la nota
    (`pns_ai_chatboo/models/chatboo_async_request.py:1319-1335`). El cliente muestra `original_content` si existe, así
    que la nota no se ve en la burbuja; de verse, saldría con los `_` literales.
16. **El PDF y el Word de un mensaje con una sola tabla muestran el HTML.** `extractProseBlocks`
    (`pns_ai_chatboo/static/src/js/chatboo_export.js:2696-2703`) cae a `markdownToProseBlocks` cuando la prosa queda en
    menos de dos bloques. Como el contenido guardado es HTML, la tabla sale como texto (`class="o_ai_table_block"`) y se
    pierden los `_` y `**`.
17. **Copiar y XLSX no llevan la prosa.** Copiar lee `clip_data` y el XLSX solo exporta las tablas: lo que el mensaje dice
    fuera de la tabla no llega.
18. **Otros detalles de la exportación.** El PDF y el Word ponen la prosa antes de la tabla, también la que en el chat va
    después; en una tabla con `id` y `name`, PDF, Word y XLSX solo llevan `Name` (copiar lleva las dos); y la descarga
    «Word» es un `.doc` con HTML, no un `.docx`.
19. **La carga de la sesión no reintenta.** `/chatboo/sessions/load` (`pns_ai_chatboo/controllers/chatboo.py:310-331`)
    llama a `update_last_used` (`models/chatboo_session.py:751-759`), con `FOR UPDATE SKIP LOCKED`. Si el trabajo del
    turno escribió la sesión después de que empezara la transacción de la carga, PostgreSQL da un fallo de serialización
    en lugar de saltar la fila; la carga lo captura y devuelve un error, sin reintentar. Lo vimos en el entorno de pruebas
    sobre 3.1.879, justo al terminar un turno: la sesión no se recargó.

20. **El límite de subida no admite «sin límite».** La ayuda de «Upload limit (MB)»
    (`pns_ai_chatboo/models/ai_agent.py:65-67`, `models/res_config_settings.py:59-61`,
    `views/res_config_settings_mcp_agents_views.xml:73`) dice «0 = no limit». Con 0, el servidor aplica su valor por
    defecto, 15 MB (`utils/chatboo_product_icp.py:37`, `:46-59` y `:190-193`). Además, el cliente rechaza todo archivo
    de más de 10 MB sea cual sea el ajuste (`static/src/js/chatboo_component_v2.js:4053` y `:4105`): un ajuste por
    encima de 10 MB no tiene efecto en el chat. **Sugerimos** corregir la ayuda y que el cliente use el límite del
    servidor.

### 8.4 Motor, skills y asistentes

21. **`ensure_module_result_call` cambia el resultado de `customer_360`.** La normalización
    (`pns_ai_mcp/utils/relaxaicode_recipe.py:389-469`, llamada desde `controllers/relaxaicode_prepare.py:215` y
    `controllers/relaxaicode_repair.py:236`) añade `result = <última función>(…)` cuando `result` no se asigna en el
    nivel del módulo, aunque se asigne dentro de bloques. En la skill `customer_360` añade `result = _iso(_q)`
    (`pns_ai_chatboo/ai/skills/system/customer_360.py:70`), con `_q` el texto del cliente buscado, y la skill falla con
    `AttributeError: 'str' object has no attribute 'isoformat'`. Por la vía de skills funciona. **Sugerimos** no añadir
    la llamada cuando el código ya asigna `result` en algún punto.
22. **`ai_log` sin el detalle del error del proveedor en el failover.** `_log_provider_failover`
    (`pns_ai_mcp/models/ai_execution_engine.py:462`, llamado desde `utils/agent_engine.py:1076`) guarda el error que
    recibe; en el camino del chat es el `ProviderConnectionError` genérico de `utils/engine_tool_loop.py:615-622` («The
    AI provider could not be reached.»), y el detalle (por ejemplo, un HTTP 429 con su texto) solo va al log de Odoo.
    Dificulta el diagnóstico a los AI Administrators.
23. **`fields_view_get` sin `@api.model`.** La sobrescritura de `pns.operation.report.wizard`
    (`pns_base/models/operation_report_wizard.py:371`) no lleva el decorador del original. Odoo 14 no lo hereda, así que
    `call_kw` la trata como método de registros y una llamada por XML-RPC da `IndexError: tuple index out of range`. La
    interfaz no lo ve, porque pide la vista con `load_views`. Lo anotamos sin petición.

### 8.5 Comportamiento del modelo

Sin código asociado; las anotamos porque afectan al coste y a la calidad, y porque registrar el prompt (petición de §5
de la entrega del 16/10, §3.4) ayudaría a diagnosticarlas.

24. **El orquestador reinterpreta peticiones cortas de edición:** una edición de la página se convierte en una página
    nueva (otra consulta y otro coste). En el entorno de pruebas creó una página aunque se le pidió «No hagas ninguna
    página».
25. **El chat llama a `relaxaicode` aunque se le pida no consultar los datos,** pese a la regla de `page_tab`
    (`pns_ai_chatboo/ai/contexts/domain/page_tab/page_tab.xml:51`). Turnos más lentos y una consulta de más.

### 8.6 Web, comentarios y traducciones

26. **El agente «AI Admin» no exige el grupo AI Administrator.** La web dice que lo exige. En el código, `ai.agent` no
    tiene grupos: lo lee cualquier usuario interno y solo lo modifica AI Administrator
    (`pns_ai_mcp/security/ir.model.access.csv:14` y `:62`). La autoría y la captura de skills, la generación OpenAPI y
    la detección de servidores lo invocan sin comprobar el grupo (`models/ai_skill_authoring.py:139-147`,
    `wizard/skill_capture_wizard.py:347`, `services/openapi_spec_generator.py:613`, `models/external_server.py:742`,
    `:777` y `:802`), de modo que un AI Writer lo usa desde «My Skills». Nos parece coherente con su uso, pero la web
    y el código no dicen lo mismo.
27. **Comentario desfasado en `security.xml`.** `pns_ai_mcp/security/security.xml:12-13` dice que AI Administrator no
    implica Conversational, pero sí lo implica (`security/security_groups.xml:50`); la línea 18 remite a
    `stacks/owl1|owl2/security/security_groups.xml`, que no existe en el módulo entregado.
28. **Referencias huérfanas en `es.po`.** `pns_ai_mcp/i18n/es.po:4441` y `:4442` tienen referencias `#:` a
    `field_ai_external_server__trusted` y `field_ai_mcp_server__trusted`, campos que no existen; el campo es
    `ai.api.server.trusted`. No afecta a la traducción, pero despista a quien busca el campo desde el `es.po`.
