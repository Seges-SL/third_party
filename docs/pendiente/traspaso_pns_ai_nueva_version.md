# Traspaso: módulos de IA `pns_*` de `third_party` — nueva versión del fabricante

Fecha: 13/10/2026 · Repo: `third_party` (Odoo 14.0) · Kit: v2.4.1

Este documento permite seguir en una conversación nueva desde donde se dejó el análisis. Se guarda en `docs/pendiente/` de la rama y en el proyecto de claude.ai.

---

## 1. Dónde lo dejamos

**Versión analizada (la anterior):** `pns_base` 1.2.10 · `pns_ai_mcp` 3.1.486 · `pns_ai_chatboo` 2.1.322.

**Rama:** `14.0-analisis-pns-ai`. La documentación tiene commit hecho (09/10/2026):

| Documento | Qué contiene |
|---|---|
| `docs/specs/analisis_pns_base.md` | Análisis de `pns_base` |
| `docs/specs/analisis_pns_ai_mcp.md` (+ bloques `_1_` a `_8_`) | Consolidado de `pns_ai_mcp`: riesgos 1-53, funcionalidades F1-F28, decisiones D1-D32 |
| `docs/specs/analisis_pns_ai_chatboo.md` (+ `_1_servidor`, `_2_componente`, `_3_cliente`) | Consolidado de `pns_ai_chatboo`: riesgos 54-78, F29-F51, D33-D46 |
| `docs/specs/guia_configuracion_pns_ai.md` | Guía de configuración (pensada para cuando llegase una versión corregida) |
| `docs/pendiente/verificacion_seguridad_pns_ai.md` | Verificación en el laboratorio, fases 1 y 2 |
| `docs/pendiente/pns_ai_decisiones.md` | Decisiones pendientes |
| `docs/pendiente/informe_fabricante_pns_ai.md` | Informe al fabricante: 80 hallazgos PNS-01 a PNS-80 (9 críticos, 26 altos, 25 medios, 20 bajos) |
| `docs/pendiente/revision_informe_pns_ai.md` | Revisión independiente del informe |

**Laboratorio** (`~/GitHub/lab_pns_ai`, carpeta git local sin remoto, MANUAL 6.7):
- `CLAUDE.md` con `Versión de Odoo: 14.0`.
- `.odoo-dev.conf` con `COMPARTIDOS="third_party"` y `DOCKERFILE="infra/Dockerfile.14"`.
- `infra/Dockerfile.14`: la imagen común más `openpyxl==3.1.2`, `httpx==0.24.1` y `pydantic==1.10.13`.
- Imagen `odoo-dev:14-lab_pns_ai` y BD `lab_pns_ai_14`, **NO neutralizada**, con `pns_ai_mcp` instalado (27 módulos).
- Es el contexto activo de la 14 tras la última validación.

**Kit v2.4.1, lo que importa aquí:**
- Hay **un contexto por versión**: el del último `arrancar`. Si ejecutas un comando desde un repo que no está en ese contexto, avisa.
- `paridad <mod>` comprueba un módulo antes de instalarlo y separa los que ya están instalados.
- `estado --bd <bd>` dice si cualquier BD está neutralizada.

## 2. Reglas que siguen vigentes

- No se modifica el código del fabricante: solo se analiza y se prueba.
- Nada de `pip` en contenedores. Si la versión nueva pide otra librería, va a `~/GitHub/lab_pns_ai/infra/Dockerfile.14` y después `odoo-dev 14 construir`.
- No se añaden reglas de permisos permanentes a Claude Code.
- Escrituras en BD: solo con autorización explícita y solo en `lab_pns_ai_14`. Nunca en `lumisol_v14_14`, `novocuadro_14` ni `third_party_14`.
- Las pruebas son de **permisos y de funcionamiento**: nunca se redactan cargas ni pasos de explotación, ni en los documentos ni en el informe.
- Lo que se envíe al fabricante no menciona rutas locales, el kit, el laboratorio ni clientes.
- Los agentes no hacen commit ni push: ramas, commits y push los hace Sergio con GitHub Desktop.

## 3. Plan

| Fase | Quién | Resultado |
|---|---|---|
| 0. Preparar la rama y el laboratorio | Sergio (GitHub Desktop + terminal) | Rama con la versión nueva en un commit aparte |
| 1. Inventario de cambios | Agente (solo lectura) | `docs/specs/cambios_pns_ai_<version>.md` |
| 2. Seguimiento del informe (PNS-01…80 + nuevos) | Agente (solo lectura), en 3 bloques | `docs/pendiente/seguimiento_informe_pns_ai.md` |
| 3. Actualizar el laboratorio y verificar | Agente, con escritura **solo** en `lab_pns_ai_14` | Sección nueva en `verificacion_seguridad_pns_ai.md` |
| 4. Revisión independiente | `odoo-reviewer` (no escribe) | Observaciones; las aplica la conversación principal |
| 5. Cierre | Conversación principal + Sergio | Decisiones, guía y, si procede, informe de seguimiento al fabricante |

En la conversación de claude.ai se revisa el resultado de cada fase antes de pasar a la siguiente. Entre fases, `/clear` en VS Code.

---

## 4. Fase 0 — Preparar la rama y el laboratorio (Sergio)

**Por qué una rama desde `14.0-analisis-pns-ai`:** contiene el código analizado y la documentación. Al sustituir los módulos encima, el diff de esa rama es exactamente lo que ha cambiado el fabricante, y los agentes pueden contrastarlo con los documentos.

1. **GitHub Desktop:** en `third_party`, con `14.0-analisis-pns-ai` activa y sin cambios pendientes, **Branch → New Branch** con el nombre `14.0-pns-ai-<version>`, por ejemplo `14.0-pns-ai-mcp-3-2`. Debe empezar por `14.0` para que el kit monte tu copia.

2. **Ver qué trae la versión nueva** (solo lectura; cambia `<carpeta_nueva>` por donde la tengas):
   ```bash
   ls <carpeta_nueva>
   for m in <carpeta_nueva>/*/__manifest__.py; do echo "$m: $(grep -E "['\"]version['\"]" "$m")"; done
   ```
   Esperado: las carpetas de los módulos con su versión. Si hay módulos nuevos (otro `pns_*`), tenlo en cuenta en el paso 3.

3. **Sustituir los módulos.** ⚠️ Esto **altera la copia de trabajo** de `third_party`. Primero se borran las carpetas, para que también se vean los archivos eliminados:
   ```bash
   cd ~/GitHub/third_party
   rm -rf pns_base pns_ai_mcp pns_ai_chatboo
   cp -r <carpeta_nueva>/pns_base <carpeta_nueva>/pns_ai_mcp <carpeta_nueva>/pns_ai_chatboo .
   find pns_base pns_ai_mcp pns_ai_chatboo -name __pycache__ -prune -exec rm -rf {} +
   git status --short | head -30 ; git diff --stat | tail -3
   ```
   Esperado:
   - solo cambios dentro de esas tres carpetas (más los módulos nuevos si los hay);
   - `git diff --stat` termina con «N files changed, X insertions, Y deletions».

4. **GitHub Desktop:** commit «pns_ai: versión <x> del fabricante, sin cambios propios» y **Publish branch**. Así el código del fabricante queda en un commit propio, separado de lo que generen los agentes.

5. **Laboratorio:** lo deja preparado, pero no instala nada.
   ```bash
   cd ~/GitHub/lab_pns_ai && odoo-dev 14 arrancar && odoo-dev 14 estado
   ```
   Esperado:
   - `third_party: copia de trabajo … (rama 14.0-pns-ai-<version>)`;
   - `BD=lab_pns_ai_14`;
   - `NO neutralizada`;
   - imagen `odoo-dev:14-lab_pns_ai`.

---

## 5. Fase 1 — Inventario de cambios (prompt para VS Code)

Abre VS Code en `~/GitHub/third_party` (rama nueva), haz `/clear` y pega:

```
Analiza los cambios de la nueva versión del fabricante de pns_base, pns_ai_mcp y pns_ai_chatboo respecto a la versión ya analizada. SOLO LECTURA: no modifiques código, no instales ni actualices módulos y no escribas en ninguna BD. El único archivo que puedes crear es docs/specs/cambios_pns_ai_<version>.md (sustituye <version> por la de pns_ai_mcp).

Contexto: la versión anterior (pns_base 1.2.10, pns_ai_mcp 3.1.486, pns_ai_chatboo 2.1.322) está analizada en docs/specs/analisis_pns_*.md, y el informe al fabricante con los hallazgos PNS-01 a PNS-80 está en docs/pendiente/informe_fabricante_pns_ai.md. No leas esos documentos enteros: consúltalos con Grep cuando necesites un dato.

1. Cambios: `git diff --stat 14.0-analisis-pns-ai..HEAD` y, por módulo, `git diff 14.0-analisis-pns-ai..HEAD -- <modulo>`. Si el diff es muy grande, trabaja por archivo.
2. Para cada módulo: versión anterior y nueva del manifest; depends y external_dependencies (añadidas o quitadas); archivos nuevos, eliminados y modificados; carpeta migrations/ (versiones y si se ejecutarán con el esquema de versión del manifest, que en la versión anterior no se ejecutaba con 3.1.x).
3. Cambios con impacto en seguridad o datos: modelos y campos nuevos, ir.model.access.csv, record rules, grupos, rutas HTTP (auth y csrf), uso de sudo(), crons, parámetros del sistema, llamadas a servicios externos y almacenamiento de claves. Cita archivo:línea. Describe el comportamiento, no cómo aprovecharlo.
4. Desde ~/GitHub/lab_pns_ai: `odoo-dev 14 paridad pns_base,pns_ai_mcp,pns_ai_chatboo` (solo lectura) y anota el resultado (librerías nuevas que falten en la imagen del laboratorio, módulos sin código…).
5. Lista de los PNS-xx a los que afectan los cambios (solo los identificadores y el archivo tocado; el detalle es de la fase 2).

Estructura del documento: Resumen (5-10 líneas) · Versiones · Dependencias y librerías · Archivos por módulo · Cambios con impacto · Migraciones · Paridad · PNS afectados.
Al terminar, muéstrame solo el Resumen y las secciones Dependencias y librerías, Migraciones y Paridad.
```

**Qué me pasas en claude.ai:** lo que muestre al terminar (o el documento si es corto).

---

## 6. Fase 2 — Seguimiento del informe (tres prompts, con `/clear` entre ellos)

**2a. Críticos y altos.** Haz `/clear` y pega:

```
Seguimiento del informe al fabricante sobre la nueva versión de pns_base, pns_ai_mcp y pns_ai_chatboo. SOLO LECTURA de código y BD. El único archivo que puedes crear o modificar es docs/pendiente/seguimiento_informe_pns_ai.md.

Fuentes: docs/pendiente/informe_fabricante_pns_ai.md (hallazgos), docs/specs/cambios_pns_ai_<version>.md (inventario de la fase 1) y el código actual. El diff respecto a la versión analizada: git diff 14.0-analisis-pns-ai..HEAD.

En este bloque, SOLO los hallazgos de severidad CRÍTICA y ALTA (35). Para cada uno:
- Estado: CORREGIDO · PARCIAL · SIN CAMBIOS · YA NO APLICA (el código desapareció) · DUDOSO (requiere prueba en el laboratorio).
- Evidencia: archivo:línea en la versión nueva y, si cambió, qué cambió. No basta con que el archivo se haya modificado: comprueba que el cambio cubre el hallazgo entero y todos sus puntos de entrada.
- Prueba en el laboratorio: sí/no, y qué comportamiento habría que observar (permisos y funcionamiento; sin redactar cargas ni pasos de explotación).

Crea el documento con: Cabecera (versiones comparadas, fecha) · Tabla resumen (PNS, severidad, estado) · Detalle por hallazgo. Deja preparadas las secciones "Medios y bajos" y "Hallazgos nuevos" vacías.
Al terminar, muéstrame solo la tabla resumen y el recuento por estado.
```

**2b. Medios y bajos.** Haz `/clear` y pega el mismo prompt cambiando el bloque:

```
Continúa docs/pendiente/seguimiento_informe_pns_ai.md (léelo antes). SOLO LECTURA de código y BD; solo puedes modificar ese documento. Mismas fuentes y mismo criterio que el bloque de críticos y altos (estado, evidencia archivo:línea, prueba sí/no sin cargas de explotación), ahora para los hallazgos de severidad MEDIA y BAJA (45). Rellena la sección "Medios y bajos", añádelos a la tabla resumen y actualiza el recuento.
Al terminar, muéstrame solo las filas nuevas de la tabla y el recuento total por estado.
```

**2c. Hallazgos nuevos.** Haz `/clear` y pega:

```
Continúa docs/pendiente/seguimiento_informe_pns_ai.md (léelo antes). SOLO LECTURA de código y BD; solo puedes modificar ese documento.
Revisa ÚNICAMENTE el código nuevo o modificado en git diff 14.0-analisis-pns-ai..HEAD (no todo el módulo) buscando problemas que no estén en el informe: permisos (ACL sin grupo, record rules, sudo), rutas HTTP (auth, csrf), datos personales y claves, crons, rendimiento evidente y errores funcionales. Numera los nuevos desde PNS-81, con severidad, archivo:línea y descripción del comportamiento (sin cargas ni pasos de explotación). Antes de añadir uno, comprueba con Grep que no está ya en el informe.
Rellena la sección "Hallazgos nuevos" y añade a la tabla resumen.
Al terminar, muéstrame solo la lista de nuevos (PNS, severidad, una línea) y el recuento total.
```

**Qué me pasas en claude.ai:** lo que muestre cada bloque. Con eso decidimos qué se prueba en la fase 3.

---

## 7. Fase 3 — Actualizar el laboratorio y verificar

Este prompt lo afino en claude.ai con el resultado de la fase 2, porque depende de qué hallazgos queden DUDOSOS o CORREGIDOS. Su forma será esta:

```
Desde ~/GitHub/lab_pns_ai. Te AUTORIZO a escribir SOLO en la BD lab_pns_ai_14 (actualizar módulos y crear y borrar usuarios de prueba). Ninguna otra BD. Sin reglas de permisos permanentes y sin pip.
1. `odoo-dev 14 estado` (BD=lab_pns_ai_14; si sale el aviso de contexto, para y avísame) y `odoo-dev 14 paridad pns_base,pns_ai_mcp,pns_ai_chatboo`. Si falta alguna librería, para: va al Dockerfile del laboratorio.
2. `odoo-dev 14 actualizar pns_base,pns_ai_mcp,pns_ai_chatboo` y resume el resultado del analizador (y si se ejecutaron las migraciones).
3. Repite las pruebas de permisos y funcionamiento de docs/pendiente/verificacion_seguridad_pns_ai.md para los hallazgos <lista de la fase 2>, y anota el resultado en una sección nueva "Versión <x>" de ese documento.
4. Borra los usuarios de prueba que crees y confirma que lab_pns_ai_14 queda como estaba (salvo los módulos actualizados).
```

## 8. Fases 4 y 5 — Revisión y cierre

- **Revisión:** `@odoo-reviewer` sobre `seguimiento_informe_pns_ai.md` y la sección nueva de la verificación, igual que se hizo con el informe. Busca falsos «CORREGIDO», líneas mal citadas y pruebas no concluyentes, como la de F18. El prompt te lo preparo con el resultado de la fase 3.
- **Cierre**, en la conversación principal:
  - actualizar `pns_ai_decisiones.md` y `guia_configuracion_pns_ai.md`;
  - si procede, un **informe de seguimiento** para el fabricante, con los estados por PNS y los nuevos, sin rutas locales, el kit, el laboratorio ni clientes.
- **Decisión tuya:** si la versión es apta para instalarla en algún cliente. Antes, `paridad` en el repo de ese cliente y su Dockerfile con las librerías.

## 9. Cómo empezar la conversación nueva

1. Abre una conversación nueva en el proyecto **claude-odoo-kit** de claude.ai. Este traspaso está en el proyecto como `claude/traspaso_pns_ai_nueva_version.md`.
2. Primer mensaje, por ejemplo: *«Lee `claude/traspaso_pns_ai_nueva_version.md`. He terminado la fase 0: la versión nueva es pns_ai_mcp <x>, pns_ai_chatboo <y>, pns_base <z>, y estos son los resultados de los pasos 2 y 5: …»*
3. Después, fase a fase, pega lo que te muestre cada agente al terminar.

---

## 10. Estado al cierre del 13/10/2026

- Fase 0 hecha: rama `14.0-pns-ai-3` con pns_base 1.2.32, pns_ai_mcp 3.1.782 y pns_ai_chatboo 2.1.453 (commit propio del fabricante) y el traspaso en `docs/pendiente/`.
- Fase 1 hecha: `docs/specs/cambios_pns_ai_3-1-782.md`. Bloqueo: la versión no se importa en Odoo 14 (Python 3.7).
- Fase 2 hecha: `docs/pendiente/seguimiento_informe_pns_ai.md`. 80 PNS: 32 corregidos, 32 parciales, 13 sin cambios, 2 ya no aplican y 1 dudoso. Nuevos: PNS-81 a PNS-89. Sección «Compatibilidad con Odoo 14»: 1 fallo al importar y 2 en ejecución.
- Decisión de Sergio: parchear en la propia rama `14.0-pns-ai-3` (destino: staging), en un commit propio y documentado en `docs/pendiente/parches_pns_ai.md`. Parche aplicado y probado (`paridad`: 0 no se importan; pruebas de imagen y de receta correctas), con commit y push hechos.
- **Siguiente:** fase 3a (sección 11): copia de `lab_pns_ai_14`, actualización y análisis del log. Pendiente de decidir: si hay un proveedor de LLM con clave para las pruebas funcionales en el laboratorio, o si se dejan para staging. Después, la fase 3b (pruebas de permisos), la 4 (revisión) y la 5 (cierre e informe de seguimiento).
- El laboratorio está parado (`odoo-dev 14 parar`) y su contexto sigue siendo el activo de la 14.

## 11. Fase 3a — prompt listo (copia, actualización y análisis)

La actualización **no se puede deshacer** (borra tablas obsoletas y XML ID `mcp_*`, y activa la purga de logs), por eso empieza con una copia de la BD del laboratorio. En VS Code, abre `~/GitHub/third_party` (rama `14.0-pns-ai-3`), haz `/clear` y pega:

```
Fase 3a: actualizar los módulos pns_* en el LABORATORIO. Te AUTORIZO a escribir SOLO en la BD lab_pns_ai_14 (actualizar módulos). Ninguna otra BD. Sin reglas de permisos permanentes, sin pip y sin commit.

1. Desde ~/GitHub/lab_pns_ai: `odoo-dev 14 estado`. Debe mostrar BD=lab_pns_ai_14, third_party como copia de trabajo en la rama 14.0-pns-ai-3 y ningún aviso de contexto. Si no, PARA y avísame.
2. Copia de seguridad (solo lectura sobre la BD):
   mkdir -p ~/odoo-dev/14.0/copias && docker exec odoo-dev-14-db-1 pg_dump -U odoo -Fc lab_pns_ai_14 > ~/odoo-dev/14.0/copias/lab_pns_ai_14_antes_3-1-782.dump && ls -lh ~/odoo-dev/14.0/copias/
   Si el archivo pesa 0 bytes o hay error, PARA.
3. Estado previo (solo lectura, SELECT): versiones instaladas de pns_*, número de crons activos, número de XML ID de pns_ai_mcp que empiezan por mcp_, número de registros de ai_log y su fecha más antigua.
4. `odoo-dev 14 actualizar pns_base,pns_ai_mcp,pns_ai_chatboo`. Si necesita el stack en marcha, ejecuta antes `odoo-dev 14 arrancar` desde ~/GitHub/lab_pns_ai.
5. Resume el resultado del analizador (BLOQUEANTES y AVISOS) y busca en el log de esa operación (~/odoo-dev/14.0/logs/): "Running migration" (esperado 0), "DROP leftover" o borrado de tablas, errores al borrar XML ID mcp_*, "Failed to load", tracebacks y cualquier AttributeError.
6. Estado posterior (mismas consultas del paso 3, solo SELECT), más: crons de pns_* (nombre, activo, numbercall, próxima ejecución), si existen los XML ID ai_* equivalentes a los mcp_* que había, y si quedan los 3 servidores externos de fábrica y la skill analisis_financiero.
7. `odoo-dev 14 estado` y `odoo-dev 14 log 100`: el servidor debe arrancar sin tracebacks.

Anota todo en una sección nueva "Versión 3.1.782 — actualización en el laboratorio (fase 3a)" de docs/pendiente/verificacion_seguridad_pns_ai.md (es el único archivo que puedes modificar). Compara el estado previo y el posterior, y relaciona lo observado con PNS-81, PNS-87, PNS-88 y la sección de migraciones de docs/specs/cambios_pns_ai_3-1-782.md (confirma o corrige sus inferencias).
Al terminar, muéstrame: el resultado del analizador, la tabla antes/después y cualquier error o sorpresa.
```

- Permisos: acepta el `pg_dump`, el `actualizar` y las consultas (escribir en `lab_pns_ai_14` está autorizado). La BD del laboratorio no está neutralizada: no saldrá el mensaje de crons desactivados.
- Si algo sale mal, la copia permite volver atrás. Ojo: `bd-cargar --reemplazar` neutraliza la BD al cargarla.

**Decisión pendiente para la fase 3b:** las pruebas de permisos (RPC con usuarios de prueba) no necesitan IA. Las funcionales (consulta por fechas, imágenes en Chatboo, PNS-16, 59 y 60) necesitan un proveedor de LLM configurado en el laboratorio: clave de API, algo de coste y salida de datos de demostración hacia el proveedor. Alternativa: dejarlas para staging.
