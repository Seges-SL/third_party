# Traspaso: módulos de IA `pns_*` — cierre de la fase 3 y fase 5 en curso

Fecha: 14/10/2026 (19:30) · Repo: `third_party` (Odoo 14.0) · Rama: `14.0-pns-ai-3` · Kit: v2.4.1

Continúa `traspaso_pns_ai_nueva_version.md` (13/10/2026). Este documento permite seguir en una
conversación nueva. Se guarda en `docs/pendiente/` de la rama y en el proyecto de claude.ai.

---

## 1. Dónde lo dejamos

**Versión en análisis:** `pns_base` 1.2.32 · `pns_ai_mcp` 3.1.782 · `pns_ai_chatboo` 2.1.453, con los
parches de compatibilidad 1 a 4 aplicados en la rama.

**Fases:**

| Fase | Estado |
|---|---|
| 0. Rama y laboratorio | Hecha (13/10) |
| 1. Inventario de cambios | Hecha (13/10), corregida tras la fase 3a |
| 2. Seguimiento del informe | Hecha (13/10), actualizada con el laboratorio y la revisión |
| 3a. Actualización en el laboratorio | Hecha (14/10) |
| 3b-1. Permisos sin IA | Hecha (14/10) |
| 3b-2. Funcionales con proveedor (Gemini) | **Parcial**: proveedor saturado (503); 9 pruebas pendientes para staging |
| 4. Revisión independiente (`odoo-reviewer`) | Hecha (14/10): salieron PNS-90 a 92 y varias correcciones |
| 3c. Pruebas complementarias tras la revisión | Hecha (14/10) |
| Parche 4 (`prompts/*` en Odoo 14) | Aplicado y probado (14/10) |
| 5a. Revisión de decisiones | Hecha (14/10): N1 a N5 decididas |
| 5b. Guía de configuración | **Siguiente** |
| 5c. Plan de staging | Pendiente |
| 5d. Informe de seguimiento al fabricante + revisión | Pendiente |

**Resultado en una línea:** de los 80 hallazgos del informe, 31 corregidos, 33 parciales, 13 sin
cambios, 2 ya no aplican y 1 dudoso; 12 nuevos (PNS-81 a 92). Los críticos de las pruebas A-D están
cerrados, pero PNS-82, 83, 85, 90 y 91 (mismo patrón que PNS-01: métodos públicos en `sudo` sin
control de grupo) son explotables por cualquier interno, y 83, 90 y 91 también por un usuario de
portal. La versión es apta solo para staging (N3).

## 2. Documentos de la rama y su estado

| Documento | Estado |
|---|---|
| `docs/specs/cambios_pns_ai_3-1-782.md` | Inventario de la fase 1, con las correcciones de la fase 3a |
| `docs/pendiente/seguimiento_informe_pns_ai.md` | Estado de PNS-01 a 92 con columna «Laboratorio»; recuento 31/33/13/2/1 + 12 nuevos; compatibilidad con Odoo 14 |
| `docs/pendiente/verificacion_seguridad_pns_ai.md` | Fases 1-2 (versión anterior) y secciones «Versión 3.1.782»: 3a, 3b-1, 3b-2, 3c y parche 4. Incluye la lista de pruebas pendientes para staging (3b-2) |
| `docs/pendiente/parches_pns_ai.md` | Parches 1 a 4, con cómo comprobar si el fabricante ya lo ha corregido |
| `docs/pendiente/pns_ai_decisiones.md` | Sección «Revisión tras la versión 3.1.782» (tabla, bloqueantes) y N1 a N5 |
| `docs/specs/guia_configuracion_pns_ai.md` | **Desfasada**: se actualiza en la fase 5b |
| `docs/pendiente/informe_fabricante_pns_ai.md` | Informe original (PNS-01 a 80). No se toca: el seguimiento va en un documento aparte (5d) |

**Último commit pendiente de comprobar:** los dos ajustes de `pns_ai_decisiones.md` (N1: secuencia
del kit marcada como no probada; nota en «Resumen») y su commit «pns_ai: decisiones revisadas tras
la versión 3.1.782 (N1 a N5)». Si `git status` muestra ese archivo modificado, revisar y hacer el
commit antes de empezar.

## 3. Decisiones tomadas hoy (Sergio, 14/10/2026)

- **Tabla de decisiones D1-D46 y PB:** aceptada completa (10 CERRADA, 31 CAMBIA, 10 SIGUE ABIERTA).
- **Bloqueantes vigentes:** siempre D1, D3, D4, D9, D10 y PB-2; con Chatboo, D33 y D46; D29
  condicionada a la prueba 8 de staging.
- **N1, retención:** a), con la secuencia segura: exportar `ai_provider_usage_day`; crear
  `pns_ai_mcp.log_retention_days` antes; parar → `-u … --stop-after-init` → fijar
  `pns_ai_chatboo.history_retention_days` con `odoo shell` (+ `env.cr.commit()`) → arrancar.
- **N2, parches:** c), mantener los parches 1-4 y pedir al fabricante una fecha de corrección.
- **N3, aptitud:** b) ahora (solo VPS de pruebas, sin portal, usuarios técnicos, mitigaciones) y a)
  para producción (no apta hasta que se corrijan PNS-82, 83, 85, 90 y 91).
- **N4, mesa de PIN:** a), no se usa.
- **N5, pruebas pendientes:** a) VPS de pruebas con datos de demostración y proveedor externo; c)
  laboratorio como puente.
- **Severidades nuevas:** PNS-90 Alta, PNS-91 Media, PNS-92 Media (defensa en profundidad).
- **Candidatos sin número:** pérdida de `ai_provider_usage_day` → PNS-87; purga global de Chatboo →
  es la corrección de PNS-63; duplicar proveedor copia la clave → observación en PNS-20; tipos de
  cambio → PNS-47/72.

## 4. Estado del laboratorio

- `~/GitHub/lab_pns_ai`, BD `lab_pns_ai_14` (no neutralizada) con las tres versiones nuevas y el
  parche 4 cargado. Limpia: sin usuarios ni registros de prueba (verificado con `SELECT`).
- Proveedores de fábrica 1 a 4 activos; «Gemini lab» (id 5) archivado y **con la clave vaciada**.
- `admin` sin grupos de IA.
- Copia previa a la actualización: `~/odoo-dev/14.0/copias/lab_pns_ai_14_antes_3-1-782.dump`.
- El servidor web puede seguir en marcha: `odoo-dev 14 parar` si no se va a usar.
- **Comprobar:** que la clave de Gemini está revocada en Google AI Studio.

## 5. Reglas que siguen vigentes

- No se modifica el código del fabricante salvo los parches de compatibilidad documentados (N2).
- Nada de `pip` en contenedores. Sin reglas de permisos permanentes.
- Escrituras en BD solo con autorización explícita y solo en `lab_pns_ai_14`.
- Pruebas de permisos y funcionamiento: nunca cargas ni pasos de explotación, ni en documentos ni en
  el informe; los textos de prueba se describen, no se copian.
- Lo que se envíe al fabricante no menciona rutas locales, el kit, el laboratorio, clientes ni
  personas. `verificacion_seguridad_pns_ai.md` es interno y **no se envía**.
- Los agentes no hacen commit ni push: ramas, commits y push los hace Sergio con GitHub Desktop.
- Entre fases, `/clear` en VS Code; en claude.ai se revisa cada resultado antes de seguir.

## 6. Siguiente: fase 5b (guía de configuración)

En VS Code, `~/GitHub/third_party` (rama `14.0-pns-ai-3`), `/clear` y pega:

```
Fase 5b: actualizar docs/specs/guia_configuracion_pns_ai.md a la versión 3.1.782 (único archivo que puedes modificar; sin código ni BD).

Fuentes: docs/pendiente/pns_ai_decisiones.md (sección «Revisión tras la versión 3.1.782» y N1 a N5), docs/pendiente/seguimiento_informe_pns_ai.md, docs/pendiente/verificacion_seguridad_pns_ai.md (secciones 3.1.782), docs/pendiente/parches_pns_ai.md y docs/specs/cambios_pns_ai_3-1-782.md. Consulta con Grep; no leas los documentos enteros si no hace falta.

1. Lee la guía actual y dime en una lista breve qué secciones quedan desfasadas con la versión nueva.
2. Actualízala. Debe cubrir, como mínimo:
   - Requisitos: Odoo 14 con Python 3.7/3.8 o Pillow < 6 → parches 1 a 4 obligatorios (N2); librerías: solo openpyxl (httpx y pydantic ya no hacen falta); dbfilter para que /mcp* (auth='none') encuentre la BD en servidores con varias BD.
   - Actualización segura desde 3.1.486 (N1): copia de la BD; contar ai_log, ai_provider_usage_day y sesiones de Chatboo antiguas; exportar ai_provider_usage_day; crear antes pns_ai_mcp.log_retention_days; parar el servicio → -u con --stop-after-init → fijar pns_ai_chatboo.history_retention_days con odoo shell (y commit) → arrancar; revisar las personalizaciones sobre los 38 XML ID mcp_* (PNS-88) y default_context_codes del agente Chatboo (D37). Comprobaciones posteriores: crons de pns_* con numbercall=-1, sin tracebacks, y prompts/* por /mcp.
   - Grupos y usuarios: AI Administrator solo para administradores de Odoo (D4); AI Writer; group_ai_conversational + clave MCP para el chat (D46); group_ai_external_url solo para quien lo necesite; claves generadas con el asistente y entregadas por canal propio, nunca con la mesa de PIN (N4).
   - Proveedores: cadena del agente siempre definida (sin cadena se usan todos los proveedores activos); «No external failover» en proveedores locales (D10); archivar los proveedores de fábrica que no se usen; no duplicar proveedores (copian la clave).
   - Política de URL y lista blanca (D24): whitelist_only por defecto, con la advertencia de PNS-91 mientras no se corrija; no usar open.
   - Copias de configuración: sin secretos mientras siga PNS-82 (D8).
   - Servidores externos: los 5 de fábrica heredados, inactivos; decidir si se borran (D7).
   - Estado de la versión: apta solo para staging, no para producción, hasta que se corrijan PNS-82, 83, 85, 90 y 91 (N3), con las mitigaciones de N3 y lo que no se puede mitigar.
3. Estilo: español, pasos numerados, sin rutas locales del equipo ni del laboratorio. Cita las decisiones (D/N) y los PNS cuando una indicación venga de ellos.
Al terminar, muéstrame el índice de secciones de la guía, la lista del punto 1 y `git diff --stat`.
```

**Qué me pasas en claude.ai:** el índice, la lista de secciones desfasadas y el `diff --stat`.

## 7. Después: fase 5c (plan de staging)

Prompt orientativo (se afina en claude.ai tras revisar la guía):

```
Fase 5c: crear docs/pendiente/plan_staging_pns_ai.md (único archivo que puedes crear; sin código ni BD). Fuentes: guía de configuración actualizada, pns_ai_decisiones.md (N1-N5, D3, D7, D15, D17, D37, PB-1), verificacion_seguridad_pns_ai.md («Plan para el VPS de pruebas» de la 3a, «Pruebas pendientes para staging» de la 3b-2 y la sección del parche 4) y parches_pns_ai.md.

Estructura:
1. Objetivo y condiciones (N3 b: sin usuarios de portal, usuarios técnicos, datos de demostración; N5 a: proveedor externo; N4: sin mesa de PIN).
2. Preparación del VPS: Dockerfile con openpyxl, rama con los parches 1-4 (comprobar con el grep de parches_pns_ai.md), dbfilter, workers y limit_time_real (D15), copia de la BD.
3. Actualización con la secuencia de N1 y comprobaciones posteriores (crons, log, prompts/* por /mcp, ficha de un módulo OCA para PB-1, default_context_codes del agente para D37, personalizaciones mcp_* para D17).
4. Configuración: proveedor con la cadena del agente definida, grupos, clave MCP con el asistente.
5. Pruebas pendientes: las 9 de la 3b-2, cada una con usuario, qué hacer (descrito, sin cargas) y resultado esperado si está CORREGIDO; más el resto de PNS-01/02 con un AI Administrator sin Ajustes si se decide probarlo.
6. Registro de resultados (tabla vacía PNS · resultado · fecha) y criterio para revisar N3 y D29.
Al terminar, muéstrame el índice y la tabla de pruebas.
```

## 8. Después: fase 5d (informe de seguimiento al fabricante)

Prompt orientativo:

```
Fase 5d: redactar docs/pendiente/informe_seguimiento_fabricante_pns_ai.md (único archivo que puedes crear; sin código ni BD). Es para enviar al fabricante: NO menciones rutas locales, el kit, el laboratorio, clientes, personas ni nombres de BD; describe entornos como «entorno de pruebas con Odoo 14 (Python 3.7.3, Pillow 5.4.1)». Mismo idioma y tono que docs/pendiente/informe_fabricante_pns_ai.md. Sin cargas, código de ataque ni pasos de explotación: comportamientos y archivo:línea del código del fabricante (sus líneas, no las de la rama con parches).

Fuentes: seguimiento_informe_pns_ai.md, parches_pns_ai.md y pns_ai_decisiones.md (D2: prioridades; D27, D28, D34, D44: peticiones).

Estructura:
1. Resumen: versión revisada, recuento por estado y gravedad, valoración general (los críticos del informe anterior están corregidos o reducidos; quedan los del patrón de métodos públicos en sudo).
2. Prioridad 1: PNS-83, 90, 82, 85 y 91, el patrón común y la corrección propuesta; restos de PNS-01/02 y PNS-07/19.
3. Compatibilidad con Odoo 14 (PNS-81): los cuatro fallos con la corrección mínima de cada uno; petición de fecha de corrección (N2).
4. Pérdida de datos al actualizar (PNS-87, 88) y la nota de PNS-63.
5. Tabla de estado de PNS-01 a 92 (estado y una línea), sin la columna de laboratorio; donde se haya comprobado, «comprobado en entorno de pruebas».
6. Hallazgos nuevos PNS-81 a 92 con detalle.
7. Peticiones menores y observaciones (D27, D28, D34, D44; copy=False en la clave del proveedor; system_prompt duplicado en prompts/list; PNS-92).
8. Pendiente de comprobar por nuestra parte (las pruebas de staging), sin detalles del entorno.
Al terminar, muéstrame el índice y el resumen (sección 1).
```

Después, revisión independiente con `@odoo-reviewer` sobre ese informe (exactitud de estados y
citas, que no se filtre nada interno, sin cargas). El envío lo decide Sergio.

## 9. Pendientes fuera de esta tarea

- **Kit (otro día, con su propio análisis):** `odoo-dev arrancar` con el stack en marcha no recrea el
  contenedor ni recarga el código Python (hizo falta `parar` + `arrancar` para el parche 4); no está
  en el MANUAL. Además, comprobar si `parar` detiene también la BD y si `actualizar` y `shell` la
  levantan solos (afecta a la secuencia local de N1).
- **Staging:** ejecutar el plan de la fase 5c cuando el VPS esté listo.

## 10. Cómo empezar la conversación nueva

1. Conversación nueva en el proyecto **claude-odoo-kit** de claude.ai. Este traspaso está en el
   proyecto como `claude/traspaso_pns_ai_fase5.md`.
2. Primer mensaje, por ejemplo: *«Lee `claude/traspaso_pns_ai_fase5.md`. Seguimos con la fase 5b;
   este es el resultado del agente: …»*.
3. Si `git status` mostraba `pns_ai_decisiones.md` modificado, dilo para revisarlo antes.
