# Plan de corrección de los módulos pns_ai por Seges

- **Rama de trabajo:** `14.0-pns-ai-correcciones`, desde `14.0-pns-ai-3` · **Fecha:** 20/10/2026
- **Origen:** reunión del 19/10/2026; [decisiones](pns_ai_decisiones.md) N11 (Seges corrige) y N12
  (se mantiene la 3.1.782, con vigilancia de las versiones del fabricante), §10.
- **Registro de los cambios en el código:** [parches_pns_ai.md](parches_pns_ai.md).
- **Estado de cada hallazgo:** [seguimiento](seguimiento_informe_pns_ai.md). Pruebas y resultados en
  la [verificación](verificacion_seguridad_pns_ai.md).
- **Estado del plan:** E0 y E1 hechas (20/10/2026); siguiente, E2.

## 1. Cómo se trabaja

**Cada entrega:**
1. **Arquitecto** (`odoo-architect`): spec en `docs/specs/correcciones_pns_ai_entregaN.md`, con el
   inventario de llamadores, la corrección por método, los tests y el plan de staging. Para hasta la
   aprobación de Sergio.
2. **Programador** (`odoo-coder`): aplica la spec, compila con Python 3.7.3, pasa los tests y
   `--revisar --base 14.0-pns-ai-3` sin incidencias nuevas, y añade las entradas a
   `parches_pns_ai.md`.
3. **Revisor** (`odoo-reviewer`): veredicto APROBADO o RECHAZADO, con la comparación con la línea base
   de tests.
4. **Sergio:** un commit por parche y otro para los tests (GitHub Desktop).
5. **Staging** (`pns_demo`): despliegue con huella y `diff -rq`, igual que los parches 5 y 6, y el plan
   de prueba de la spec. Resultado en la verificación.
6. **LIYBEN:** no se actualiza en cada entrega. Recibe todas las correcciones **de una vez, al
   terminar el plan**, con todo validado en el staging (decisión de Sergio del 20/10/2026; §3).
7. **Documentos:** estado del parche en `parches_pns_ai.md`, columna «Rama Seges» del seguimiento y
   estado de la entrega en este plan.

**Pruebas en local:** contexto `cd ~/GitHub/lab_pns_ai && odoo-dev 14 arrancar` (imagen con
`openpyxl`, `httpx` y `pydantic`; `third_party` montado como copia de trabajo) y VS Code abierto en
`~/GitHub/third_party`.

**Línea base de tests** (3.1.782 con parches 1-6; verificación, «Línea base de tests (3.1.782,
parches 1-6)»): `pns_ai_mcp` 180 tests, 130 pasados, 5 saltados, 14 fallidos y 31 errores;
`pns_ai_chatboo` sin tests. Criterio de cada entrega: los tests nuevos pasan y el resto queda igual que
en la línea base. **Tras E1:** 198 tests, 148 / 5 / 14 / 31 (los 18 de `test_seges_rpc_access.py` en
verde).

**Staging:** los scripts de E1 (`preparar_e1.py`, `pruebas_e1_rpc.py` y `pruebas_e1_mcp.py`, solo con la
biblioteca estándar) sirven de modelo para preparar datos y repetir pruebas por RPC y por `/mcp` sin
gastar cuota del proveedor. Con `whitelist_only`, solo un AI Administrator puede proponer un
`fetch_url` a un dominio fuera de la lista. En Chrome, el staging pierde la sesión cada minuto (cookie
compartida con `liyben.com`, probable): usar otro navegador o una ventana de incógnito.

**Límites comunes:** los de N11 (cambio mínimo, Python 3.7.3, sin dependencias nuevas, sin tocar
`version`/`depends`/`external_dependencies`, `i18n` ni, salvo necesidad, `ir.model.access.csv`;
marcador en cada cambio; sin commit ni push por los agentes).

## 2. Entregas

Esfuerzos orientativos, con agentes, revisión y validación.

| Entrega | Contenido | Parches | Riesgo | Esfuerzo | Se da por buena con | Estado |
|---|---|---|---|---|---|---|
| **E0** | N11 y N12; documentos; licencia; rama; línea base de tests | — | Nulo | ½ día | Línea base registrada y documentos subidos | Hecha (20/10/2026) |
| **E1** | Patrón común (informe 2, §2.2) en `pns_ai_mcp`: PNS-90, 91, 85 y 83, y los métodos que pasen a privados añadidos a la lista negra del sandbox | 7-10 | Medio-bajo: un llamador sin actualizar rompería la caché de `fetch_url`, el alta de dominios o la caché de skills | 1-1½ días | Tests nuevos en verde y resto como la línea base; revisor APROBADO; staging: pruebas de 3b-1 (83, 85) y 3c (1, 2) CORREGIDO y sin regresión con Gemini | Hecha: validada en staging el 20/10/2026 (commit `2bb4f51`) |
| **E2** | PNS-82 (adjuntos de Chatboo; tests nuevos en `pns_ai_chatboo/tests/`) y restos de PNS-01/02 (`base.group_system`, además de AI Administrator, para dar o quitar grupos) | 11-12 | Medio: las descargas propias del chat deben seguir funcionando | 1 día | B no reclama el adjunto de A y A lo sigue descargando; un AI Administrator sin Ajustes es rechazado; staging: descargas del chat | Pendiente |
| **ET** | Batería de tests al día: los 33 desfasados respecto a 3.1.782, los 2 con datos de prueba incompletos y los 5 que no encajan con Odoo 14 (revisión caso a caso); PNS-50 (los tres que no se ejecutan). Solo tests, sin código del producto | — | Bajo | 1 día | Batería en verde salvo los ambientales documentados | Pendiente (aprobada el 20/10/2026) |
| **E3** | Restos de PNS-07/19: el sandbox bloquea los métodos privados (con lista de permitidos), incluido `_api_key_for_inference` | 13 | Alto: puede rechazar código legítimo del LLM | 1½-2 días | Tests del sandbox (del fabricante y de Seges) y batería de consultas relaxaicode en staging | Pendiente |
| **Hito: producción (N3)** | — | — | — | — | E1, E2 y E3 validados en staging; D1, D4, D9 y PB-2 decididas (y D33 y D46 con Chatboo; D3 CERRADA) | — |
| **E4** | Resto del patrón común: PNS-92, restos de PNS-30 y PNS-37, PNS-89 (CSRF) y los métodos de D-3 de la spec E1 (`consume_key_pin`; `ai.key.pin.desk.touch`/`close`/`any_open`/`notify_changed`; `ai.key.pin.ask.collect`/`supply`; `ai.api.result.cache.get_cached`/`store`; los dos `gc_expired`) | 14-17 | Bajo-medio: `create_log_entry` tiene muchos llamadores | 1 día | Tests negativos; la auditoría sigue registrando | Pendiente |
| **E5** | PNS-94 de fondo: `lock_timeout` en las escrituras de la sesión, no tragar un commit fallido, detectar y cerrar un job colgado | 18+ | Medio-alto: concurrencia | 1½ días | Staging: los 5 casos del parche 6 y un lock forzado | Pendiente |
| **E6** | PNS-87/88: sin código. Solo afectan a quien actualiza desde 3.1.486 (N1: ningún entorno); la retención se fija con un parámetro (D13, guía) | — | — | — | Se reabre si aparece una actualización desde versiones anteriores | Sin código |
| **Después** | Restos de fondo de seguridad (54/60, 59 con la política `open`, 86, 84, 55, 61, 36, 40, ampliaciones de 93) y, al terminar, **lo funcional** (PNS-67, 95, skills que se ofrecen sin su módulo, como `annual_billing` sin `account`…), como fase aparte | — | — | — | Se priorizan al terminar E5 | Pendiente |

**Por qué ET va antes de E3:** con N12 la batería de tests es de Seges, y con 45 fallos y errores no
detecta regresiones. E3 es la entrega de más riesgo y la que más se apoya en los tests del sandbox.
E1 y E2 llevan tests propios y no dependen de ET.

**Por qué E3 no va al final:** la corrección preferida del patrón común (hacer privado un método)
cierra el RPC, pero el sandbox de relaxaicode permite llamar a métodos privados (resto de PNS-07). E1
añade a la lista negra del sandbox los métodos que privatiza; E3 cierra el resto.

## 3. Al terminar

1. **LIYBEN:** desplegar de una vez todos los parches validados (clon del VPS como el UID 101 y
   reinicio de `odoo14_server`; `-u` solo si alguna spec lo pide), con copia previa y el plan de
   prueba conjunto de las entregas. Registro en [instalacion_liyben_pns_ai.md](instalacion_liyben_pns_ai.md).
2. Staging: limpieza según el [plan de staging](plan_staging_pns_ai.md), §9, y revocar su clave de
   Gemini.
3. Integrar la rama en `14.0` con merge commit y volver el clon del VPS a `14.0`.
4. Actualizar y enviar la 2.ª entrega del informe al fabricante (D2), sin código.
5. Guía de configuración: mitigaciones que dejan de hacer falta y versión instalada.
