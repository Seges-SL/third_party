# Spec: correcciones_pns_ai_entrega1 (Odoo 14.0)

- **Entrega:** E1 del [plan de corrección](../pendiente/plan_correccion_pns_ai.md) · **Parches:** 7 a 10
- **Rama:** `14.0-pns-ai-correcciones` · **Fecha:** 20/10/2026 · **Estado:** aprobada por
  Sergio (20/10/2026). Implementada; revisión APROBADO (20/10/2026)
- **Módulo afectado:** solo `pns_ai_mcp` (3.1.782, Apache-2.0, base propia de Seges por N12)
- **Decisiones de las que parte:** N3, N4, N11 y N12 ([decisiones](../pendiente/pns_ai_decisiones.md))
- **Versión:** Odoo 14.0 (`CLAUDE.md` del repo). Imagen de pruebas `odoo-dev:14-lab_pns_ai`
  (Python 3.7.3)
- **Código de referencia consultado:** `/opt/odoo-src/14.0/odoo` y
  `/opt/odoo-src/14.0/vertical-instaladores`. Del módulo, solo los archivos locales del repo (no
  `/opt/odoo-src/14.0/third_party`)

## 1. Objetivo y reglas de negocio

### 1.1 Objetivo

Corregir en `pns_ai_mcp` el patrón común del informe 2 (§2.2) en cuatro hallazgos: métodos
públicos (sin `_`) que trabajan en `sudo()` o con un cursor de superusuario y no comprueban grupo
ni propiedad. Hoy cualquier usuario autenticado, también de portal, los invoca por RPC.

| PNS | Métodos | Estado hoy | Prueba que lo demuestra |
|---|---|---|---|
| PNS-90 | `ai.fetch.cache.get_cached`, `store` | VULNERABLE | fase 3c, prueba 1 |
| PNS-91 | `ai.url.whitelist.ensure_domain_whitelisted` | VULNERABLE | fase 3c, prueba 2 |
| PNS-85 | `ai.skill.param.cache.remember_for_skill`, `lookup_for_skill`; `ai.skill.remember_param_cache`, `lookup_param_cache` | VULNERABLE | fase 3b-1, grupo b |
| PNS-83 | `ai.mcp.user.redeem_key_pin`; `ai.key.pin.block.release_all`, `note_failure`, `is_blocked` | VULNERABLE | fase 3b-1, grupo b |

Además, los métodos que pasen a privados se añaden a la lista negra del sandbox de relaxaicode
(`RELAXAICODE_SIDE_EFFECT_METHODS`), porque el sandbox deja llamar a métodos con un guion bajo
(resto de PNS-07). El resto de PNS-07 queda para E3.

### 1.2 Reglas

1. **R1:** ningún usuario sin el rol adecuado puede leer ni escribir la caché de `fetch_url`,
   ampliar la lista blanca, escribir o leer la caché de parámetros de skills, canjear PIN, ni
   tocar los bloqueos de PIN por `/web/dataset/call_kw`, `/web/dataset/call_button`,
   `/web/dataset/call`, `/jsonrpc` ni `/xmlrpc/*`. Tras el intento la BD no cambia.
2. **R2:** los flujos internos que usan esos métodos funcionan igual:
   - la caché de `fetch_url`;
   - el alta y la reactivación de dominios desde el plan, el botón «➕ Whitelist» y los servidores
     externos;
   - la caché de parámetros de las skills;
   - el botón «Release PIN blocks» de Ajustes.
3. **R3:** el código de relaxaicode (caja A) no puede invocar los métodos que pasan a privados,
   ni literalmente ni por `getattr`, `attrgetter` o `methodcaller`.
4. **R4 (límites de N11):**
   - cambio mínimo;
   - Python 3.7.3;
   - sin dependencias nuevas;
   - sin tocar `version`, `depends`, `external_dependencies`, `i18n`, `LICENSE`, `NOTICE` ni
     `ir.model.access.csv`;
   - no se tocan los parches 1 a 6;
   - marcador `# Seges: parche N (PNS-XX, seguridad). Ver docs/pendiente/parches_pns_ai.md` junto
     a cada cambio.

   Esta entrega no añade mensajes nuevos visibles para el usuario. Si hiciera falta alguno, iría en
   inglés y con `_()`.

## 2. Soluciones existentes evaluadas (OCA / core / repo común) y conclusión

### 2.1 Qué rechaza en Odoo 14 los nombres que empiezan por `_`

El rechazo lo hace una única función del core, `check_method_name`, y solo la llaman los puntos de
entrada RPC. El ORM (`odoo.api.call_kw`) **no** la aplica.

| Pieza | Archivo:línea (`/opt/odoo-src/14.0/odoo/…`) | Qué hace |
|---|---|---|
| `regex_private = re.compile(r'^(_.*\|init)$')` | `odoo/models.py:114` | Patrón de nombre privado: empieza por `_` o es `init` |
| `check_method_name(name)` | `odoo/models.py:116-119` | `AccessError('Private methods (such as %s) cannot be called remotely.')` |
| `DataSet._call_kw` | `addons/web/controllers/main.py:1360-1362` | Llama a `check_method_name(method)` (`:1361`) y después a `odoo.api.call_kw` |
| `/web/dataset/call` | `addons/web/controllers/main.py:1364-1366` | Pasa por `_call_kw` |
| `/web/dataset/call_kw` y `/web/dataset/call_kw/<path>` | `addons/web/controllers/main.py:1368-1370` | Pasa por `_call_kw` (`auth="user"`: interno o portal) |
| `/web/dataset/call_button` | `addons/web/controllers/main.py:1372-1377` | Pasa por `_call_kw` (botones `type="object"`) |
| `/xmlrpc/<service>`, `/xmlrpc/2/<service>`, `/jsonrpc` | `odoo/addons/base/controllers/rpc.py:71-96` | `dispatch_rpc(service, method, params)` |
| `dispatch_rpc` | `odoo/http.py:117-142` | Para `service == 'object'` usa `odoo.service.model.dispatch` (`:140-141`) |
| `service.model.dispatch` | `odoo/service/model.py:25-42` | Solo admite `execute` y `execute_kw` (`:35-36`); comprueba las credenciales (`:37`) |
| `execute_kw` → `execute` | `odoo/service/model.py:167-178` | `check_method_name(method)` en `:174`, antes de `execute_cr` |
| `odoo.api.call_kw` | `odoo/api.py:395-408` | **No** comprueba el nombre. Si el método no existe: `AttributeError("The method '…' does not exist on the model '…'")` (`:397-399`) |

Consecuencias para el diseño:

- Un método renombrado a `_metodo` queda cerrado para cualquier usuario por las cinco rutas RPC.
  Invocar el nombre antiguo da `AttributeError` y el privado da `AccessError`.
- Cualquier código que llame a `odoo.api.call_kw` con un nombre que venga del cliente se salta la
  barrera. **En los tres `pns_*` no hay ninguno.** Se buscó `call_kw`, `check_method_name`,
  `execute_kw` y `getattr(<modelo>, <nombre variable>)`. La única aparición es
  `ai.trusted.action._resolve_method` (`models/ai_trusted_action.py:93-110`), que toma el nombre
  de datos XML (`data/trusted_actions_system.xml`), con métodos ya privados y ninguno de esta
  entrega.
- `ir.actions.server`, `ir.cron` y el código Python pueden seguir llamando a métodos privados: los
  llamadores internos funcionan si se actualizan.

### 2.2 Otras soluciones

- **OCA / core / repo común:** no aplican. Es una corrección del código de un tercero (N11), no
  una funcionalidad. No existe un módulo que «cierre» métodos de otro módulo: un `_inherit` que
  sobrescribiera los métodos públicos para lanzar `AccessError` dejaría el código original intacto
  y duplicaría la lógica. Se descarta.
- **Corrección del informe 2, §2.2:** en orden de preferencia:
  1. privado;
  2. si debe seguir siendo público, comprobar grupo o propiedad antes de cualquier `sudo()`;
  3. no confiar en el ACL ni en efectos laterales;
  4. un test negativo por método.

  Es el mismo patrón que la 3.1.782 aplicó en `ai.system.action`/`ai.trusted.action` (PNS-01). Se
  sigue.

**Conclusión:** opción 1 (privado) para los once métodos (justificación por método en el §5.2).

## 3. Manifest (depends, orden de data, licencia, autor)

**Sin cambios.** No se toca `__manifest__.py` (ni `version`, ni `depends`, ni
`external_dependencies`, ni `data`). Licencia del módulo: Apache-2.0 (Patanegra Soft). Los cambios
son solo de Python. No hay datos, vistas ni campos nuevos, así que **no hace falta `-u`**: basta con
reiniciar el servidor (ver el §9.3).

## 4. Modelos y campos

No hay modelos ni campos nuevos, ni cambios de herencia. Solo se renombran métodos:

| Modelo | Herencia | Método antes | Método después | Decorador | PNS / parche |
|---|---|---|---|---|---|
| `ai.fetch.cache` | `_name` (propio) | `get_cached(url)` | `_get_cached(url)` | `@api.model` | PNS-90 / 7 |
| `ai.fetch.cache` | `_name` | `store(url, result, ttl_seconds)` | `_store(url, result, ttl_seconds)` | `@api.model` | PNS-90 / 7 |
| `ai.url.whitelist` | `_name` | `ensure_domain_whitelisted(hostname, notes='', kind='web')` | `_ensure_domain_whitelisted(…)` | `@api.model` | PNS-91 / 8 |
| `ai.skill.param.cache` | `_name` | `remember_for_skill(skill_id, leftover, norm)` | `_remember_for_skill(…)` | `@api.model` | PNS-85 / 9 |
| `ai.skill.param.cache` | `_name` | `lookup_for_skill(skill_id, leftover)` | `_lookup_for_skill(…)` | `@api.model` | PNS-85 / 9 |
| `ai.skill` | `_name` | `remember_param_cache(leftover, norm)` | `_remember_param_cache(…)` | (de registro) | PNS-85 / 9 |
| `ai.skill` | `_name` | `lookup_param_cache(leftover)` | `_lookup_param_cache(…)` | (de registro) | PNS-85 / 9 |
| `ai.mcp.user` | `_name` | `redeem_key_pin(raw, ip=None)` | `_redeem_key_pin(…)` | `@api.model` | PNS-83 / 10 |
| `ai.key.pin.block` | `_name` | `release_all()` | `_release_all()` | `@api.model` | PNS-83 / 10 |
| `ai.key.pin.block` | `_name` | `note_failure(ip)` | `_note_failure(ip)` | `@api.model` | PNS-83 / 10 |
| `ai.key.pin.block` | `_name` | `is_blocked(ip)` | `_is_blocked(ip)` | `@api.model` | PNS-83 / 10 |

Comprobado que ningún nombre nuevo choca con un método de `BaseModel` ni de otro modelo del core
14 con el mismo `_name`. Solo existen `_get_cached` en `res.lang`
(`odoo/addons/base/models/res_lang.py:241`) y en `website` (`addons/website/models/website.py:1043`),
que son modelos distintos: no hay conflicto de herencia. Sí afecta a la lista negra del sandbox,
que trabaja por nombre (ver el §5.3 y la duda D-1).

**Ojo, mismo nombre en otro modelo:** `ai.api.result.cache.get_cached`/`store`
(`models/api_result_cache.py:86-129`) **no** se renombran. Sus llamadores
`controllers/safe_plan.py:1815` y `:1871` (`Cache = env['ai.api.result.cache']`) **no se tocan**.
Ver la duda D-3.

## 5. Métodos

### 5.1 Inventario de llamadores

Búsqueda (Grep) de los once nombres en:
- `pns_base`, `pns_ai_mcp` y `pns_ai_chatboo`: Python, JS, XML, datos, `ai/` (packs de skills y
  contextos), crons y acciones de servidor;
- `/opt/odoo-src/14.0/vertical-instaladores` (rama 14.0 de referencia).

Resultados:
- **JS:** ninguna llamada `rpc`/`_rpc`/`session.rpc`/`ajax.jsonRpc` con `method:` igual a uno de
  estos nombres. `key_pin_desk_v14.js` solo llama a rutas propias (`/pns_ai_mcp/key_pin/desk`,
  `/supply` y `/stop`).
- **XML:** ningún botón `type="object"`, acción de servidor ni cron con estos nombres.
- **vertical-instaladores (14.0):** 0 coincidencias. Tampoco usa `pns_*`, `ai.*` ni `pns_ai`. La
  copia de trabajo `/home/soporte/GitHub/vertical-instaladores` está en la rama `17.0` y tampoco da
  coincidencias.
- **Tests del fabricante:** ninguno llama a estos métodos.

| Método | Llamador (archivo:línea) | Contexto | Usuario con que se ejecuta | ¿RPC desde el navegador? |
|---|---|---|---|---|
| `ai.fetch.cache.get_cached` | `controllers/safe_plan.py:1619` (`_execute_fetch_url`) | Paso `fetch_url` de `execute_safe_plan` (`:797`); este lo llama `safe_operation.execute_plan_now` (`:1392`) desde `controllers/safe_plan.py:2251`, `:2416`, `safe_operation.py:878` y `:999`, y `utils/skill_runtime.py:2455` | Usuario real (quien pide o confirma el plan; `SUPERUSER_ID` solo como último recurso en `_retry_confirmed_not_executed`, `:988-992`). Env **sin** `sudo`; el `sudo` está dentro del método | No (Python). **Dentro de `try/except: pass` (`:1618-1625`): si no se actualiza, falla en silencio (sin caché)** |
| `ai.fetch.cache.store` | `controllers/safe_plan.py:1667` (HEAD/OPTIONS) y `:1723` (cuerpo) | Mismo `_execute_fetch_url` | Igual | No. **Sin `try` alrededor: si no se actualiza, `AttributeError` y falla el paso del plan** |
| `ai.url.whitelist.ensure_domain_whitelisted` | `controllers/safe_plan.py:750` y `:757` (`_ensure_fetch_url_whitelist`) | Paso `fetch_url` de `execute_safe_plan` (`:796`): alta con política `open`, reactivación con `whitelist_only` | Usuario real del plan; env sin `sudo` (`Whitelist = env['ai.url.whitelist']`) | No |
| ″ | `models/safe_operation.py:1069` y `:1076` (`_maybe_auto_whitelist`) | Al confirmar: `confirm_by_user` (`:546`) y `resolve_confirm` (`:682`) | Quien confirma (dueño o AI Administrator, `_can_resolve`); `Whitelist = …sudo()`; `:1076` solo si es AI Administrator (`:1074`) | No (lo invoca un método público que ya comprueba). **Sin `try`: si no se actualiza, falla la confirmación** |
| ″ | `models/safe_operation.py:1107` (`action_add_to_whitelist`) | Botón «➕ Whitelist» / «Add domain to whitelist» (`views/safe_operation_views.xml:45`, `:76`) | AI Administrator (comprobado en `:1084`); `Whitelist = …sudo()` | **El botón sí es RPC** (`call_button` de `action_add_to_whitelist`, que sigue público y comprueba el grupo). La llamada a `ensure_…` es Python |
| ″ | `models/external_server.py:1018` (`_ensure_docs_url_whitelisted`) | `ai.api.server.write` con `docs_url` (`:624-627`) | Quien escribe el servidor: AI Administrator por ACL, o superusuario al instalar o importar. Sin `sudo` en el env | No. **Dentro de `try/except` con aviso: si no se actualiza, solo deja un `warning`** |
| ″ | `models/external_server.py:1080` (`_ensure_server_whitelisted`) | `ai.api.server.create` (`:553`) y `write` (`:608`) | Igual | No. **Igual: falla en silencio con aviso** |
| `ai.skill.param.cache.lookup_for_skill` | `models/ai_skill.py:334` (`lookup_param_cache`) | Delegación interna | El del registro `ai.skill` (usuario del turno) | No |
| `ai.skill.param.cache.remember_for_skill` | `models/ai_skill.py:343` (`remember_param_cache`) | Delegación interna. Fuera de los tests abre un cursor propio de `SUPERUSER_ID` con commit (`ai_skill_param_cache.py:141-148`) | Usuario del turno; la escritura, como superusuario | No |
| `ai.skill.lookup_param_cache` | `utils/agent_engine.py:785` (`getattr(skill, 'lookup_param_cache', None)`) | `AgentEngine._normalize_skill_params` (`:709`), llamado desde `:1896` en la invocación de una skill con `/` | Usuario real del turno (Chatboo o `/mcp`). `skill` sale de `_resolve_skill` → `ai.skill.get_for_agent` (`:1415-1428`, `ai_skill.py:822-833`), en el env del usuario, sin `sudo` | No. **Por nombre en una cadena, con `callable()` y `try/except`: si no se actualiza, la caché deja de usarse en silencio** |
| `ai.skill.remember_param_cache` | `utils/agent_engine.py:868` | Igual, tras la llamada al LLM híbrido | Igual | No. **Igual: falla en silencio (solo un `warning`)** |
| `ai.mcp.user.redeem_key_pin` | **ninguno** | — | — | — (solo era alcanzable por RPC) |
| `ai.key.pin.block.release_all` | `models/res_config_settings.py:349` (`action_key_pin_release`) | Botón «Release PIN blocks» de Ajustes (`views/res_config_settings_views.xml:198`) | Quien pasa `ensure_ai_admin` (`:348`); después, `sudo()` | **El botón es RPC** (`call_button` de `action_key_pin_release`, que sigue público y comprueba el grupo). La llamada a `release_all` es Python |
| `ai.key.pin.block.note_failure` | `models/mcp_user.py:839` | Dentro de `redeem_key_pin` (`Block = …sudo()`, `:830`) | `sudo` | No |
| `ai.key.pin.block.is_blocked` | `models/mcp_user.py:831`; `models/key_pin_block.py:51` | Dentro de `redeem_key_pin` y de `note_failure` | `sudo` | No |

**Conclusión del inventario:**
- Ningún método tiene un llamador legítimo por RPC: todos los llamadores son Python del propio
  módulo.
- Los dos botones (`action_add_to_whitelist`, `action_key_pin_release`) son métodos públicos
  distintos, que ya comprueban el grupo y no cambian.
- `redeem_key_pin` no tiene llamador.

### 5.2 Corrección por método (informe 2, §2.2)

| Método | Opción | Justificación |
|---|---|---|
| `get_cached`, `store` (PNS-90) | **1: privado** | Solo los llama `_execute_fetch_url` (Python). La caché es global e interna del motor; nadie necesita leerla ni escribirla por RPC. El ACL del modelo (solo AI Administrator) sigue cubriendo la lectura por ORM desde la interfaz. Es la corrección que propone el seguimiento. |
| `ensure_domain_whitelisted` (PNS-91) | **1: privado** | Todos sus llamadores son Python. Ya deciden la política antes de llamarlo: política `open`, AI Administrator en `_maybe_auto_whitelist` y en `action_add_to_whitelist`, servidores externos creados por un AI Administrator. Un AI Administrator sigue dando de alta dominios por la interfaz (ACL `1,1,1,1`) o con el botón. |
| `remember_for_skill`, `lookup_for_skill`, `remember_param_cache`, `lookup_param_cache` (PNS-85) | **1: privado** | Solo los usa el motor (`agent_engine.py`) y la delegación entre `ai.skill` y `ai.skill.param.cache`. La edición manual de la caché ya va por ORM (`param_cache_ids` en la vista de la skill, ACL de AI Writer y AI Administrator) y no cambia. |
| `redeem_key_pin` (PNS-83) | **1: privado** | Sin llamador. Por diseño lo usaría una app **sin** sesión, así que la opción 2 (comprobar un grupo) no tiene sentido: ningún grupo representa a «quien tiene el PIN». Si algún día se usa la mesa (N4 dice que no), el punto de entrada correcto es un controlador propio que tome la IP de `request.httprequest.remote_addr`, no un `call_kw`. |
| `release_all` (PNS-83) | **1: privado** | Su único llamador es el botón de Ajustes, que ya comprueba `ensure_ai_admin` antes del `sudo()`. |
| `note_failure`, `is_blocked` (PNS-83) | **1: privado** | Solo los usa `redeem_key_pin`. Público, `note_failure` permite bloquear la IP que se quiera (denegación de servicio) e `is_blocked` deja consultar el estado de cualquier IP. |

Ningún método queda público, así que la opción 2 no se usa. **Los llamadores que cambian** son
18 líneas en 8 archivos, más la lista del sandbox. Están en el §5.4.

| Archivo | Líneas |
|---|---|
| `safe_plan.py` | 750, 757, 1619, 1667, 1723 |
| `safe_operation.py` | 1069, 1076, 1107 |
| `external_server.py` | 1018, 1080 |
| `ai_skill.py` | 334, 343 |
| `agent_engine.py` | 785, 868 |
| `mcp_user.py` | 831, 839 |
| `key_pin_block.py` | 51 |
| `res_config_settings.py` | 349 |

### 5.3 Sandbox de relaxaicode (lo que toca a E1 del resto de PNS-07)

Cómo funciona hoy:

1. **AST, antes de ejecutar** (`controllers/validators.py`):
   - `_detect_requires_write_from_ast` (`:1151-1210`) marca `requires_write = True` si encuentra:
     - una **llamada** `x.<nombre>(…)` con `<nombre>` en `RELAXAICODE_SIDE_EFFECT_METHODS`
       (`:1169-1172`);
     - `getattr(x, '<nombre>')`, también con el nombre concatenado de forma estática
       (`'_st' + 'ore'`, `_ast_static_str`, `:1135-1148`);
     - `attrgetter`/`methodcaller` con ese nombre (`:1178-1197`).
   - `validate_relaxaicode_source_ast` devuelve ese indicador (`:2270-2282`).
   - Con `requires_write`, `tools_relaxaicode.py` no ejecuta el código:
     - sin AI Writer devuelve un error de permisos y cancela las verificaciones pendientes del
       usuario (`:2014-2065`, comportamiento previo);
     - con AI Writer devuelve «relaxaicode es SOLO LECTURA…» (`:2070-2085`).
2. **En ejecución** (`controllers/context_builder.py`):
   - `guarded_getattr` sustituye al `getattr` del sandbox (`:417`) y rechaza los nombres de la
     lista con `AttributeError` (`:150-154`). Cubre los nombres construidos en ejecución
     (`''.join([...])`).
   - `guarded_attrgetter` y `guarded_methodcaller` (`:291-301`) aplican la misma comprobación
     (`_check_attr_path`, `:275-280`).
3. **Hueco que permite llegar a los métodos nuevos:**
   - `GuardedSandboxEnv` solo cierra `ai.api.server`, `ai.context` y `ai.skill`
     (`catalogue_inspect_error`, `validators.py:1055-1063`). `env['ai.fetch.cache']`,
     `env['ai.url.whitelist']`, `env['ai.skill.param.cache']`, `env['ai.mcp.user']` y
     `env['ai.key.pin.block']` son alcanzables.
   - Un registro `ai.skill` también lo es por relación
     (`env['ai.skill.param.cache'].search([]).skill_id`: los internos tienen lectura).
   - El docstring de `guarded_getattr` dice que los métodos de un guion están permitidos
     (`context_builder.py:134-135`).
   - La caja A corre en una transacción `READ ONLY` (`controller_helpers.py:184-208`), así que las
     escrituras en el mismo cursor fallan. Pero:
     - `_remember_for_skill` y `_redeem_key_pin` (este a través de `ai.key.pin.ask.collect`,
       `key_pin_desk.py:175-184`) abren **cursores propios con commit**;
     - `_get_cached`, `_lookup_*`, `_is_blocked` y `_redeem_key_pin` **leen en `sudo`** datos que
       el usuario no puede leer por ACL.

**Comprobación: ¿añadirlos a `RELAXAICODE_SIDE_EFFECT_METHODS` los bloquea?** Sí, en las formas
que la lista ya cubre:

| Forma en el código del LLM | ¿Bloqueado al añadir el nombre? | Por qué |
|---|---|---|
| `env['ai.fetch.cache']._store(…)` (llamada literal) | **Sí** | AST → `requires_write` → no se ejecuta |
| `getattr(m, '_store')(…)` / `getattr(m, '_st' + 'ore')(…)` | **Sí** | AST (cadena estática) → `requires_write` |
| `getattr(m, ''.join(['_st', 'ore']))(…)` | **Sí** | `guarded_getattr` en ejecución → `AttributeError` |
| `operator.methodcaller('_store', …)` / `attrgetter` | **Sí** | AST y `guarded_methodcaller`/`guarded_attrgetter` |
| `f = m._store` y después `f(…)` (alias sin llamada en el mismo nodo) | **No** | El AST solo mira llamadas `x.nombre(...)`, y el acceso con punto no pasa por `guarded_getattr`. **Ya pasa hoy con los 15 nombres de la lista.** Es el resto general de PNS-07 y se cierra en E3, que bloquea todos los métodos con `_` |

**Decisión:** se añaden los 11 nombres privados a `RELAXAICODE_SIDE_EFFECT_METHODS`, con un
marcador por parche (diffs en el §5.4). No se toca ninguna otra lógica del validador. El hueco del
alias se documenta como resto para E3 (duda D-2).

Efecto en la interfaz: si el LLM usa uno de estos nombres, recibe el mensaje que ya existe («Method
%r writes outside RelaxAICode's rollback…» o «relaxaicode es SOLO LECTURA»). Para los de lectura
(`_get_cached`, `_lookup_*`, `_is_blocked`) el texto no es exacto, pero no se añaden mensajes nuevos
(cambio mínimo). Ningún pack de skills ni contexto de fábrica usa estos nombres: el Grep sobre `ai/`
no dio coincidencias.

### 5.4 Diffs propuestos (por parche y archivo)

Las líneas son las del fabricante, antes de aplicar nada, como en el parche 4. Cada marcador añade
una línea y desplaza las siguientes. Indentación exacta a la del archivo. No hay cambios de estilo.

`controllers/validators.py` lo tocan los cuatro parches. Cada uno añade su bloque (ver «Lista del
sandbox», al final) y Sergio lo confirma con su commit seleccionando líneas en GitHub Desktop
(duda D-7).

#### Parche 7 — PNS-90 (`ai.fetch.cache`)

`pns_ai_mcp/models/fetch_cache.py`
```diff
@@ -63,2 +63,3 @@
+    # Seges: parche 7 (PNS-90, seguridad). Ver docs/pendiente/parches_pns_ai.md
     @api.model
-    def get_cached(self, url):
+    def _get_cached(self, url):
@@ -91,2 +92,3 @@
+    # Seges: parche 7 (PNS-90, seguridad). Ver docs/pendiente/parches_pns_ai.md
     @api.model
-    def store(self, url, result, ttl_seconds):
+    def _store(self, url, result, ttl_seconds):
```

`pns_ai_mcp/controllers/safe_plan.py` (`_execute_fetch_url`)
```diff
@@ -1619 @@
-        cached = env['ai.fetch.cache'].get_cached(cache_key)
+        # Seges: parche 7 (PNS-90, seguridad). Ver docs/pendiente/parches_pns_ai.md
+        cached = env['ai.fetch.cache']._get_cached(cache_key)
@@ -1667 @@
-                    env['ai.fetch.cache'].store(cache_key, cache_payload, ttl)
+                    # Seges: parche 7 (PNS-90, seguridad). Ver docs/pendiente/parches_pns_ai.md
+                    env['ai.fetch.cache']._store(cache_key, cache_payload, ttl)
@@ -1723 @@
-                env['ai.fetch.cache'].store(cache_key, cache_payload, ttl)
+                # Seges: parche 7 (PNS-90, seguridad). Ver docs/pendiente/parches_pns_ai.md
+                env['ai.fetch.cache']._store(cache_key, cache_payload, ttl)
```
**No tocar** `safe_plan.py:1815` ni `:1871` (`ai.api.result.cache`).

#### Parche 8 — PNS-91 (`ai.url.whitelist`)

`pns_ai_mcp/models/url_whitelist.py`
```diff
@@ -235,2 +235,3 @@
+    # Seges: parche 8 (PNS-91, seguridad). Ver docs/pendiente/parches_pns_ai.md
     @api.model
-    def ensure_domain_whitelisted(self, hostname, notes='', kind='web'):
+    def _ensure_domain_whitelisted(self, hostname, notes='', kind='web'):
```

`pns_ai_mcp/controllers/safe_plan.py` (`_ensure_fetch_url_whitelist`)
```diff
@@ -750 @@
-        Whitelist.ensure_domain_whitelisted(
+        # Seges: parche 8 (PNS-91, seguridad). Ver docs/pendiente/parches_pns_ai.md
+        Whitelist._ensure_domain_whitelisted(
@@ -757 @@
-        Whitelist.ensure_domain_whitelisted(
+        # Seges: parche 8 (PNS-91, seguridad). Ver docs/pendiente/parches_pns_ai.md
+        Whitelist._ensure_domain_whitelisted(
```

`pns_ai_mcp/models/safe_operation.py` (`_maybe_auto_whitelist`, `action_add_to_whitelist`)
```diff
@@ -1069 @@
-            Whitelist.ensure_domain_whitelisted(
+            # Seges: parche 8 (PNS-91, seguridad). Ver docs/pendiente/parches_pns_ai.md
+            Whitelist._ensure_domain_whitelisted(
@@ -1076 @@
-        Whitelist.ensure_domain_whitelisted(
+        # Seges: parche 8 (PNS-91, seguridad). Ver docs/pendiente/parches_pns_ai.md
+        Whitelist._ensure_domain_whitelisted(
@@ -1107 @@
-        Whitelist.ensure_domain_whitelisted(
+        # Seges: parche 8 (PNS-91, seguridad). Ver docs/pendiente/parches_pns_ai.md
+        Whitelist._ensure_domain_whitelisted(
```

`pns_ai_mcp/models/external_server.py`
```diff
@@ -1018 @@
-            self.env['ai.url.whitelist'].ensure_domain_whitelisted(
+            # Seges: parche 8 (PNS-91, seguridad). Ver docs/pendiente/parches_pns_ai.md
+            self.env['ai.url.whitelist']._ensure_domain_whitelisted(
@@ -1080 @@
-                Whitelist.ensure_domain_whitelisted(
+                # Seges: parche 8 (PNS-91, seguridad). Ver docs/pendiente/parches_pns_ai.md
+                Whitelist._ensure_domain_whitelisted(
```

#### Parche 9 — PNS-85 (`ai.skill.param.cache` y `ai.skill`)

`pns_ai_mcp/models/ai_skill_param_cache.py`
```diff
@@ -91,2 +91,3 @@
+    # Seges: parche 9 (PNS-85, seguridad). Ver docs/pendiente/parches_pns_ai.md
     @api.model
-    def lookup_for_skill(self, skill_id, leftover):
+    def _lookup_for_skill(self, skill_id, leftover):
@@ -125,2 +126,3 @@
+    # Seges: parche 9 (PNS-85, seguridad). Ver docs/pendiente/parches_pns_ai.md
     @api.model
-    def remember_for_skill(self, skill_id, leftover, norm):
+    def _remember_for_skill(self, skill_id, leftover, norm):
```

`pns_ai_mcp/models/ai_skill.py`
```diff
@@ -329 @@
-    def lookup_param_cache(self, leftover):
+    # Seges: parche 9 (PNS-85, seguridad). Ver docs/pendiente/parches_pns_ai.md
+    def _lookup_param_cache(self, leftover):
@@ -334 @@
-        return self.env['ai.skill.param.cache'].lookup_for_skill(
+        return self.env['ai.skill.param.cache']._lookup_for_skill(
@@ -338 @@
-    def remember_param_cache(self, leftover, norm):
+    # Seges: parche 9 (PNS-85, seguridad). Ver docs/pendiente/parches_pns_ai.md
+    def _remember_param_cache(self, leftover, norm):
@@ -343 @@
-        return self.env['ai.skill.param.cache'].remember_for_skill(
+        return self.env['ai.skill.param.cache']._remember_for_skill(
```
(Un marcador por método cubre el cambio de su cuerpo, a tres o cuatro líneas.)

`pns_ai_mcp/utils/agent_engine.py` (`_normalize_skill_params`)
```diff
@@ -785 @@
-        lookup = getattr(skill, 'lookup_param_cache', None)
+        # Seges: parche 9 (PNS-85, seguridad). Ver docs/pendiente/parches_pns_ai.md
+        lookup = getattr(skill, '_lookup_param_cache', None)
@@ -868 @@
-        remember = getattr(skill, 'remember_param_cache', None)
+        # Seges: parche 9 (PNS-85, seguridad). Ver docs/pendiente/parches_pns_ai.md
+        remember = getattr(skill, '_remember_param_cache', None)
```

#### Parche 10 — PNS-83 (`ai.mcp.user` y `ai.key.pin.block`)

`pns_ai_mcp/models/mcp_user.py`
```diff
@@ -819,2 +819,3 @@
+    # Seges: parche 10 (PNS-83, seguridad). Ver docs/pendiente/parches_pns_ai.md
     @api.model
-    def redeem_key_pin(self, raw, ip=None):
+    def _redeem_key_pin(self, raw, ip=None):
@@ -831 @@
-        if Block.is_blocked(ip):
+        # Seges: parche 10 (PNS-83, seguridad). Ver docs/pendiente/parches_pns_ai.md
+        if Block._is_blocked(ip):
@@ -839 @@
-            paused = Block.note_failure(ip)
+            # Seges: parche 10 (PNS-83, seguridad). Ver docs/pendiente/parches_pns_ai.md
+            paused = Block._note_failure(ip)
```

`pns_ai_mcp/models/key_pin_block.py`
```diff
@@ -36,2 +36,3 @@
+    # Seges: parche 10 (PNS-83, seguridad). Ver docs/pendiente/parches_pns_ai.md
     @api.model
-    def is_blocked(self, ip):
+    def _is_blocked(self, ip):
@@ -45,2 +46,3 @@
+    # Seges: parche 10 (PNS-83, seguridad). Ver docs/pendiente/parches_pns_ai.md
     @api.model
-    def note_failure(self, ip):
+    def _note_failure(self, ip):
@@ -51 @@
-        if self.is_blocked(ip):
+        if self._is_blocked(ip):
@@ -68,2 +70,3 @@
+    # Seges: parche 10 (PNS-83, seguridad). Ver docs/pendiente/parches_pns_ai.md
     @api.model
-    def release_all(self):
+    def _release_all(self):
```
(La línea 51 queda dentro de `_note_failure`, cuyo marcador está tres líneas antes.)

`pns_ai_mcp/models/res_config_settings.py` (`action_key_pin_release`)
```diff
@@ -349 @@
-        self.env['ai.key.pin.block'].sudo().release_all()
+        # Seges: parche 10 (PNS-83, seguridad). Ver docs/pendiente/parches_pns_ai.md
+        self.env['ai.key.pin.block'].sudo()._release_all()
```

#### Lista del sandbox (parches 7 a 10)

`pns_ai_mcp/controllers/validators.py` (`RELAXAICODE_SIDE_EFFECT_METHODS`, `:178-194`)
```diff
     'button_immediate_install',
     'button_immediate_upgrade',
     'button_immediate_uninstall',
+    # Seges: parche 7 (PNS-90, seguridad). Ver docs/pendiente/parches_pns_ai.md
+    '_get_cached', '_store',
+    # Seges: parche 8 (PNS-91, seguridad). Ver docs/pendiente/parches_pns_ai.md
+    '_ensure_domain_whitelisted',
+    # Seges: parche 9 (PNS-85, seguridad). Ver docs/pendiente/parches_pns_ai.md
+    '_remember_for_skill', '_lookup_for_skill',
+    '_remember_param_cache', '_lookup_param_cache',
+    # Seges: parche 10 (PNS-83, seguridad). Ver docs/pendiente/parches_pns_ai.md
+    '_redeem_key_pin', '_release_all', '_note_failure', '_is_blocked',
 })
```
`context_builder.py` no cambia: importa la misma lista (`:16-28` y `:44`).

**Comprobación de que no queda ningún llamador** (la hace el programador y la repite el revisor):
```sh
grep -rnE "\['ai\.fetch\.cache'\]\.(get_cached|store)\(|\.ensure_domain_whitelisted\(|\.(remember_for_skill|lookup_for_skill)\(|'(lookup|remember)_param_cache'|\.(redeem_key_pin|release_all|note_failure|is_blocked)\(" \
  pns_base pns_ai_mcp pns_ai_chatboo --include=*.py --include=*.js --include=*.xml \
  | grep -v "tests/test_seges_rpc_access.py"
```
Resultado esperado: vacío. Además, `grep -rn "Seges: parche [0-9]* (PNS-" pns_ai_mcp` debe listar
los marcadores de los parches 7 a 10: 30 líneas en total (parche 7: 6; parche 8: 9; parche 9:
7; parche 10: 8). El del registro en `tests/__init__.py` no entra en esa expresión (empieza por
«Seges: parches 7 a 10»), pero sí en `grep -rn "Seges: parche"`.

## 6. Vistas

**Sin cambios.** Verificado que ninguna vista llama por nombre a un método renombrado. Los botones
relacionados llaman a métodos públicos que no cambian:
- `action_add_to_whitelist` (`views/safe_operation_views.xml:45`, `:76`);
- `action_key_pin_release` (`views/res_config_settings_views.xml:198`);
- `action_key_pin_regenerate`/`clear_key_pin` (`views/mcp_user_views.xml:25-26`, `:56`, `:61`).

## 7. Seguridad

- **Grupos:** sin cambios.
- **`ir.model.access.csv`:** **sin cambios**. No hace falta tocarlo: la causa no es el ACL (estos
  métodos lo esquivan con `sudo()`), sino que sean públicos. ACL vigentes, como referencia:
  - `ai.fetch.cache`: solo AI Administrator (`:50`);
  - `ai.url.whitelist`: lectura para internos (`:6`) y CRUD para AI Administrator (`:47`);
  - `ai.skill.param.cache`: lectura para internos (`:16`) y CRUD para AI Writer y AI Administrator
    (`:21-22`);
  - `ai.key.pin.block`: AI Administrator (`:78`);
  - `ai.mcp.user`: AI Administrator (`:39`).
- **Record rules:** sin cambios. Observación: `ai.skill.param.cache` no tiene regla de registro;
  cualquier interno lee todas sus filas por ORM (ACL `1,0,0,0`). Tras el parche 9, la lectura por
  `lookup_*` queda cerrada también para portal, que no tiene ACL. La lectura por ORM de los
  internos es del diseño del fabricante y no se cambia.
- **Comprobación en Python:** con la opción 1 no hace falta. Los métodos públicos que envuelven a
  los privados ya comprueban el grupo:
  - `action_add_to_whitelist`, en `safe_operation.py:1084`;
  - `action_key_pin_release`, en `res_config_settings.py:347-348`;
  - `_maybe_auto_whitelist`, en `safe_operation.py:1074`, para `whitelist_only`.

## 8. Datos

Sin secuencias, crons ni datos nuevos o modificados. El cron de purga de `ai.fetch.cache`
(`data/fetch_cache_cron.xml`) llama a `gc_expired`, que no cambia.

## 9. Tests previstos

### 9.1 Archivo nuevo `pns_ai_mcp/tests/test_seges_rpc_access.py`

Registro en `pns_ai_mcp/tests/__init__.py` (al final):
```diff
 from . import test_server_identity_detection
+# Seges: parches 7 a 10 (tests de la entrega E1). Ver docs/pendiente/parches_pns_ai.md
+from . import test_seges_rpc_access
```

**Cabecera:** igual que la de los archivos del módulo, con Seges como autor (licencia: duda D-4):
```python
# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 Seges
# Seges: parches 7 a 10 (tests de la entrega E1). Ver docs/pendiente/parches_pns_ai.md
```

**Reglas para no chocar con la línea base** (45 fallos y errores conocidos):
- **Skills:** ninguna con `code_body`. Se crean como en `test_factory_defaults_keep.py:48-53`, que
  pasa: `code`, `name`, `description` y `content`.
- **Grupos:** nada depende de `group_ai_conversational`, de `/mcp`, de un `ai.provider` ni de
  `pns_ai_chatboo`. Ningún usuario necesita AI Writer.
- **Etiquetas:** `@tagged('post_install', '-at_install', 'pns_ai_mcp', 'seges_e1')`. Las clases
  heredan de `HttpCase`/`TransactionCase` (`BaseCase` lleva la etiqueta `standard`), así que no
  repiten el problema de PNS-50 con `unittest.TestCase`.
- **Python 3.7:** sin walrus, sin `list[...]`/`tuple[...]` evaluados y sin f-strings con `=`.
- **Errores esperados por HTTP:** van dentro de `mute_logger('odoo.http')`. `AccessError` se
  registra como `warning` y `AttributeError` como `exception` (`odoo/http.py:657-661`).
- **Red:** sin acceso a la red. `_fetch_url_request` se sustituye con `unittest.mock.patch`.

#### Clase 1 — `TestSegesRpcAccess(HttpCase)`: negativos por RPC real

**`setUp`** (como superusuario, `self.env`):
- **U:** `new_test_user(self.env, login='seges_e1_internal', groups='base.group_user',
  password='seges_e1_internal')`.
- **P:** `new_test_user(self.env, login='seges_e1_portal', groups='base.group_portal',
  password='seges_e1_portal')`.
- **Datos de apoyo** creados con `create` en `sudo`, sin usar los métodos parcheados:
  - fila de `ai.fetch.cache`:
    - `url = 'https://seges-e1.invalid/seed'`;
    - `url_hash = sha256(url)`;
    - `body = 'seges-e1-seed-body'`, `status_code = 200`;
    - `fetched_at` = ahora, `expires_at` = ahora + 1 h;
  - fila de `ai.url.whitelist`: `domain = 'seges-e1-archived.invalid'`, `kind = 'web'`,
    `active = False`;
  - skill `seges_e1_skill`, sin `code_body` y sin `owner_id`;
  - fila de `ai.skill.param.cache` para esa skill: `unresolved = 'seges e1 seed'`,
    `params_json = '{"seed": "1"}'`;
  - fila de `ai.key.pin.block`: `ip = '198.51.100.1'`, `failures = 0`,
    `blocked_until` = ahora + 1 h.

**Utilidades:**
- `_rpc(login, model, method, args, kwargs=None)`:
  - `self.authenticate(login, login)`;
  - `self.url_open('/web/dataset/call_kw/%s/%s' % (model, method), data=json.dumps(payload),
    headers={'Content-Type': 'application/json'})`;
  - payload `{'jsonrpc': '2.0', 'method': 'call', 'id': 1, 'params': {'model': …, 'method': …,
    'args': …, 'kwargs': …}}`;
  - devuelve `resp.json()`. Mismo patrón que `test_mcp_http.py:40-42`.
- `_assert_refused(res, private)`:
  - `'result' not in res`;
  - `res['error']['data']['name']` es `'odoo.exceptions.AccessError'` si `private`, y si no
    `'builtins.AttributeError'`, el error de `odoo/api.py:399` porque el método ya no existe.
- `_snapshot()`:
  - `self.env['base'].flush()`;
  - `SELECT` ordenados con `self.cr` de `ai_fetch_cache (id, url_hash, body, expires_at)`,
    `ai_url_whitelist (id, domain, kind, active, notes)`,
    `ai_skill_param_cache (id, skill_id, key, params_json)` y
    `ai_key_pin_block (id, ip, failures, blocked_until)`;
  - en modo de pruebas la petición HTTP usa el mismo cursor (`registry.enter_test_mode`,
    `odoo/tests/common.py:1400-1404`), así que lo que escribiera se vería.

**Tests** (cada uno con U y con P; la BD debe ser idéntica antes y después):

| Test | Llamadas (args) | Esperado |
|---|---|---|
| `test_control_session_ok` | `ai.url.whitelist.is_domain_whitelisted('seges-e1-archived.invalid')` | `result == False`, para U y P. Control: la sesión y la ruta funcionan, así que los rechazos siguientes no son de sesión |
| `test_fetch_cache_refused` | `get_cached(URL)`; `store(URL, {'success': True, 'status_code': 200, 'body': 'seges-e1-poison'}, 600)`; `store('https://seges-e1.invalid/new', …)`; `_get_cached(URL)`; `_store(URL, …)` | Públicos → `AttributeError`; privados → `AccessError`. Ninguna respuesta contiene `seges-e1-seed-body`. Instantánea igual: el cuerpo sigue siendo el de la semilla y no hay fila nueva |
| `test_url_whitelist_refused` | `ensure_domain_whitelisted('seges-e1-new.invalid', 'x', 'web')`; `ensure_domain_whitelisted('seges-e1-archived.invalid', 'x', 'web')`; `_ensure_domain_whitelisted(…)` | Rechazadas. Sin fila `seges-e1-new.invalid` y la archivada sigue con `active = False` y las mismas notas |
| `test_skill_param_cache_refused` | `ai.skill.param.cache.remember_for_skill(skill.id, 'seges e1 phrase', {'k': 'v'})`; `lookup_for_skill(skill.id, 'seges e1 seed')`; `ai.skill.remember_param_cache([skill.id], 'seges e1 phrase', {'k': 'v'})`; `ai.skill.lookup_param_cache([skill.id], 'seges e1 seed')`; las cuatro en privado | Rechazadas. Ninguna respuesta contiene `"seed"`. Sin filas nuevas |
| `test_key_pin_refused` | `ai.mcp.user.redeem_key_pin('12345678', '203.0.113.9')`; `ai.key.pin.block.release_all()`; `note_failure('203.0.113.9')`; `is_blocked('198.51.100.1')`; las cuatro en privado | Rechazadas. La fila `198.51.100.1` sigue bloqueada y no existe fila `203.0.113.9` |
| `test_public_names_gone` | (Python) `hasattr(type(self.env[m]), nombre)` para los 11 nombres antiguos y los 11 nuevos | Antiguos `False`, nuevos `True`. Mismo estilo que `test_system_action.py:436-438` |

Los tests negativos **fallan sin los parches** (las llamadas públicas responden con `result`), así
que demuestran la corrección. Las llamadas con `_` ya se rechazan hoy: documentan la barrera del
core.

#### Clase 2 — `TestSegesInternalFlows(TransactionCase)`: positivos (el flujo interno sigue funcionando)

Usuario U (interno sin IA) creado igual, con `env_u = self.env(user=U)`.

| Test | Qué hace | Esperado |
|---|---|---|
| `test_fetch_cache_roundtrip` | `env_u['ai.fetch.cache']._store(url, {'success': True, 'status_code': 200, 'content_type': 'text/plain', 'body': 'b'}, 600)` y después `_get_cached(url)` | Devuelve `body == 'b'` y `_from_cache is True`. Así funciona aunque el usuario no tenga ACL |
| `test_execute_fetch_url_serves_cache` | Siembra con `_store`. `patch('odoo.addons.pns_ai_mcp.controllers.safe_plan._fetch_url_request', side_effect=AssertionError)` y `_execute_fetch_url(env_u, {'op': 'fetch_url', 'url': url})` | `success` y `_from_cache` a `True`, sin llamar a la red. **Sin el cambio de `safe_plan.py:1619` falla**: el `except: pass` haría salir a la red y saltaría el `AssertionError` |
| `test_execute_fetch_url_stores_cacheable` | `_fetch_url_request` sustituido por un objeto falso: `status_code = 200`; `headers` = `requests.structures.CaseInsensitiveDict({'Content-Type': 'application/json', 'Cache-Control': 'max-age=600'})`; `content = b'{"a": 1}'`; `text = '{"a": 1}'`. Dos llamadas seguidas a `_execute_fetch_url` con la misma URL | 1.ª: `success`, la red una vez y una fila `ai_fetch_cache` para el hash de la URL. 2.ª: `_from_cache`, sin una segunda llamada a la red. Cubre `safe_plan.py:1723` y `:1619` |
| `test_whitelist_internal_paths` | (a) `env_u['ai.url.whitelist']._ensure_domain_whitelisted('seges-e1-flow.invalid', 'n', 'web')`. (b) Con `pns_ai_mcp.url_access_policy = 'whitelist_only'`, una entrada archivada y `_ensure_fetch_url_whitelist(env_u, {'url': 'https://seges-e1-archived.invalid/x'})`. (c) Con la política `open`, `_ensure_fetch_url_whitelist(env_u, {'url': 'https://seges-e1-open.invalid/'})` | (a) `True` y fila activa. (b) Reactivada. (c) Fila creada. Cubre `safe_plan.py:750` y `:757` |
| `test_skill_param_cache_roundtrip` | `skill.with_user(U)._remember_param_cache('Seges  E1   frase', {'k': 'v'})` y `skill.with_user(U)._lookup_param_cache('seges e1 FRASE')`. Después, `_remember_param_cache` con la misma frase y `{'k': 'otro'}` | Fila creada. La búsqueda devuelve `{'k': 'v'}` (clave normalizada). La segunda no sobrescribe: el primero gana, como en el fabricante |
| `test_agent_engine_uses_private_names` | `inspect.getsource(AgentEngine._normalize_skill_params)` | Contiene `'_lookup_param_cache'` y `'_remember_param_cache'`, y no contiene `getattr(skill, 'lookup_param_cache'` ni `getattr(skill, 'remember_param_cache'`. Es una guarda estática a propósito: ese llamador falla en silencio (`getattr` + `callable` + `try`) y montar un turno con LLM híbrido no es viable sin proveedor |
| `test_no_caller_uses_public_names` | Recorre los `.py` y `.xml` de `pns_ai_mcp` (sin `tests/`) y de `pns_ai_chatboo` si está en el `addons_path`, con las expresiones regulares del §5.4 | Ninguna coincidencia. Guarda contra un llamador olvidado (`safe_operation.py`, `external_server.py`), sobre todo los que fallan en silencio |
| `test_key_pin_block_flow` | Con `ICP pns_ai_mcp.key_pin_attempts = 1`, `Block = self.env['ai.key.pin.block'].sudo()`: dos veces `Block._note_failure('203.0.113.20')`, después `Block._is_blocked(…)`. Después, un usuario `base.group_user,base.group_system,pns_ai_mcp.group_ai_admin`: `self.env['res.config.settings'].with_user(admin).create({}).action_key_pin_release()` | `True` en la 2.ª: bloqueado. Tras el botón, `_is_blocked` es `False` y devuelve la notificación. Cubre `res_config_settings.py:349` y `key_pin_block.py:51` |
| `test_redeem_key_pin_python` | `self.env['ai.mcp.user']._redeem_key_pin('abc')`; `_redeem_key_pin('12345678', '203.0.113.21')` | `{'ok': False, 'error': 'invalid', 'counted': False}`; después `counted: True` y una fila `ai.key.pin.block` con `failures == 1`. Cubre `mcp_user.py:831` y `:839`. Sin mesa ni PIN reales (N4) |

#### Clase 3 — `TestSegesSandboxDenylist(TransactionCase)`: sandbox (lo de E1 del resto de PNS-07)

`NEW = ('_get_cached', '_store', '_ensure_domain_whitelisted', '_remember_for_skill',
'_lookup_for_skill', '_remember_param_cache', '_lookup_param_cache', '_redeem_key_pin',
'_release_all', '_note_failure', '_is_blocked')`

| Test | Esperado |
|---|---|
| `test_names_in_denylist` | Cada nombre en `RELAXAICODE_SIDE_EFFECT_METHODS` (`odoo.addons.pns_ai_mcp.controllers.validators`) |
| `test_guarded_getattr_and_methodcaller` | `guarded_getattr(object(), name)` y `guarded_methodcaller(name)` (`controllers/context_builder.py`) lanzan `AttributeError` |
| `test_ast_flags_literal_and_static_getattr` | Para cada nombre, `validate_relaxaicode_source_ast("x = env['ai.fetch.cache'].%s('a')\nresult = {'data': 1}\n" % name)` → `(True, None, True)`. Con `getattr(env['ai.fetch.cache'], '_st' + 'ore')('a')`, también `requires_write`. Control: `"x = env['res.partner'].search_count([])\nresult = {'data': x}\n"` → `requires_write == False` |

El alias (`f = m._store; f()`) **no** se prueba como bloqueado porque no lo está. Es el resto para
E3 (duda D-2).

#### Criterio de aceptación local

- `odoo-dev 14 tests pns_ai_mcp` (contexto `lab_pns_ai`): **los tests nuevos en verde** (unos 18) y
  el resto **igual que la línea base**: 130 pasados, 5 saltados, 14 fallidos y 31 errores, con los
  mismos nombres de test. Total esperado: 180 + tests nuevos.
- `python3 ~/.claude/hooks/odoo_lint.py --revisar --base 14.0-pns-ai-3`: sin incidencias nuevas.
  No se corrigen avisos previos del fabricante.
- `py_compile` de los 14 archivos tocados con Python 3.7.3, en la imagen `odoo-dev:14-lab_pns_ai`.
- El `grep` de llamadores del §5.4, vacío.

### 9.2 Entradas en `docs/pendiente/parches_pns_ai.md` (las escribe el programador)

Una por parche, con el formato de los parches 5 y 6:
- fecha, estado, PNS;
- «Qué falla sin él», «Cambio» (el diff), «Qué se degrada» y «Cómo comprobar si el fabricante ya
  lo ha corregido» (los dos del §10);
- «Comprobaciones realizadas».

En el índice, la fila «7-10 (previsto)» se sustituye por cuatro filas.

### 9.3 Plan de prueba en staging (`pns_demo`)

**Despliegue** (plan de staging, §2.2, punto 4, igual que los parches 5 y 6):
1. Clon del VPS en el commit de Sergio. Huella de los archivos y `diff -rq` con el despliegue
   anterior: solo deben aparecer los 12 archivos de Python del §11 y los dos de `tests/`.
2. Reiniciar `odoo14_pns`. **No hace falta `-u`**: no hay campos, vistas ni datos.
3. Log del arranque sin tracebacks.

**Preparación** (con la autorización de Sergio para crear y borrar los usuarios de prueba):
- **A:** interno sin grupos de IA.
- **P:** portal. Ver la duda D-5: el staging se montó sin portal.
- **UW, U1, U3 y ADM:** los usuarios del staging del 15-16/10.
- **Línea base con `SELECT`:** `count(*)` y huella `md5(string_agg(...))` de `ai_fetch_cache`,
  `ai_url_whitelist`, `ai_skill_param_cache` y `ai_key_pin_block`.
- **Sin pendientes:** ninguna verificación pendiente de UW ni de U1 (ver el punto 5 de la tabla
  siguiente).

Llamadas por JSON-RPC (contraseñas y claves no se anotan):
```sh
curl -s -c a.txt -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","method":"call","params":{"db":"pns_demo","login":"<A>","password":"<…>"}}' \
  https://pns.liyben.com/web/session/authenticate
curl -s -b a.txt -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","method":"call","params":{"model":"ai.fetch.cache","method":"store","args":["https://e1.invalid/x",{"success":true,"status_code":200,"body":"e1"},600],"kwargs":{}}}' \
  https://pns.liyben.com/web/dataset/call_kw
```
Resultado esperado de cada llamada:
- nombre público → `error.data.name = builtins.AttributeError`;
- nombre con `_` → `odoo.exceptions.AccessError` («Private methods … cannot be called remotely»).

| # | Prueba (origen) | Quién | Llamadas | Resultado esperado |
|---|---|---|---|---|
| 1 | **3c, prueba 1 (PNS-90)** | A y P | `store`, `get_cached`, `_store`, `_get_cached` (URL `.invalid`) | Todas rechazadas. `SELECT` de `ai_fetch_cache` idéntico. **CORREGIDO** |
| 2 | **3c, prueba 2 (PNS-91)** | A y P | `ensure_domain_whitelisted('e1-a.invalid', 'e1', 'web')`. Con una entrada archivada por ADM: el mismo método para reactivarla. Control: `search_read` de A funciona y `create` de A da `AccessError` | Rechazadas. Sin fila nueva y la archivada sigue archivada. **CORREGIDO** |
| 3 | **3b-1 (PNS-85)** | A | `remember_for_skill(<skill de fábrica>, 'frase e1', {'lab': 'x'})`, `lookup_for_skill`, `ai.skill.remember_param_cache([id], …)`, `lookup_param_cache` | Rechazadas. `ai_skill_param_cache` sin cambios. **CORREGIDO** |
| 4 | **3b-1 (PNS-83)** | A y P | `redeem_key_pin('<8 dígitos>')`, `release_all()`, `note_failure('203.0.113.10')`, `is_blocked('203.0.113.10')` y sus versiones con `_` | Rechazadas. `ai_key_pin_block` sin cambios. **CORREGIDO** |
| 5 | **Sandbox (PNS-85/PNS-07, parte de E1)** | UW, con su clave MCP, por `/mcp` | `tools/call` `relaxaicode` con:<br>(a) `x = env['ai.skill.param.cache']._remember_for_skill(<id>, 'e1', {'a': 1})` + `result = {'data': 1}`;<br>(b) `getattr(env['ai.fetch.cache'], '_get_' + 'cached')('x')`;<br>(c) `getattr(env['ai.fetch.cache'], ''.join(['_get', '_cached']))('x')` | (a) y (b): «relaxaicode es SOLO LECTURA», sin ejecutar. (c): error «… writes outside RelaxAICode's rollback …». En los tres, `ai_skill_param_cache` sin cambios. Se usa UW porque, sin AI Writer, el rechazo cancela las verificaciones pendientes del usuario (comportamiento previo, `tools_relaxaicode.py:2033`) |
| 6 | **R1 por `/jsonrpc` (PNS-90)** | A | `POST /jsonrpc` con `{"jsonrpc":"2.0","method":"call","params":{"service":"object","method":"execute_kw","args":["pns_demo",<uid de A>,"<contraseña>","ai.fetch.cache","_store",["https://e1.invalid/x",{"success":true,"status_code":200,"body":"e1"},600]]}}` | `odoo.exceptions.AccessError` («Private methods … cannot be called remotely»). `SELECT` de `ai_fetch_cache` idéntico. **CORREGIDO** |

**No regresión con Gemini:**

| # | Caso | Quién | Pasos | Resultado esperado |
|---|---|---|---|---|
| R1 | `fetch_url` dos veces con la misma URL | U3 (`group_ai_external_url`) | Antes, con `curl -sI <url>`: elegir una URL de un dominio de la lista con `Cache-Control: max-age>0`; si no está en la lista, la añade ADM en R2. Dos turnos que piden lo mismo | 1.º: fila nueva en `ai_fetch_cache` (`url`, `fetched_at` T1). 2.º: `fetched_at` sigue en T1 y el resultado de la herramienta en `ai_log` lleva `_from_cache`. Sin `AttributeError` en el log |
| R2 | Plan que da de alta un dominio | ADM, política `whitelist_only` | (a) Turno con `fetch_url` a un dominio fuera de la lista → tarjeta → Confirmar. (b) En otra operación de `fetch_url`, botón «➕ Whitelist». (c) Archivar el dominio de (a) y repetir el turno → confirmar. (d) Activar o editar un servidor OpenAPI de fábrica inactivo con `docs_url` | (a) Fila en `ai_url_whitelist` con la nota «Added by AI Administrator on confirm of …» (`safe_operation.py:1076`). (b) Notificación «added/reactivated» (`:1107`). (c) Fila reactivada. (d) Activar o editar (escribir `docs_url`) un servidor OpenAPI de fábrica inactivo: su dominio entra en `ai_url_whitelist` y en el log no sale `could not whitelist` (`external_server.py:1018` y `:1078`) |
| R3 | Skill con parámetros cacheados | U1 | Elegir una skill con `param_schema`: `SELECT code FROM ai_skill WHERE active AND param_schema IS NOT NULL`. Invocar `/<skill> <frase libre estable>` dos veces; la frase debe ser un nombre o un código, no una fecha relativa, que no se cachea | 1.ª: fila nueva en `ai_skill_param_cache`. 2.ª: fila de `ai_log` con `tool_name = 'skill_param_cache'` y sin llamada híbrida (es la comprobación válida: `param cache lookup skipped` se escribe con nivel DEBUG y no aparece en el log) |
| R4 | Turno con imagen (no regresión del parche 6) | U1 | Caso 1 del parche 6 | Respuesta completa. `SELECT pid, state, wait_event_type, left(query, 80) FROM pg_stat_activity WHERE datname = 'pns_demo' AND (state = 'idle in transaction' OR wait_event_type = 'Lock');` → 0 filas |
| R5 | Botón «Release PIN blocks» | ADM | Ajustes → Release PIN blocks (sin generar PIN ni abrir la mesa, N4) | Notificación «PIN blocks released.», sin error |
| R6 | Log | — | `grep -E "get_cached\|ensure_domain_whitelisted\|param_cache\|redeem_key_pin\|is_blocked\|note_failure\|release_all\|AttributeError\|could not whitelist\|param cache remember skipped"` sobre el log del intervalo | Solo los rechazos provocados en las pruebas 1 a 4 y 6 |
| R7 | Consulta normal de relaxaicode (control positivo del sandbox) | UW, con su clave MCP, por `/mcp` | `tools/call` `relaxaicode` con `x = env['res.partner'].search_count([]); result = {'data': x}` | Devuelve el número de contactos, sin «relaxaicode es SOLO LECTURA» |

**Limpieza:**
- borrar A y P;
- borrar las filas creadas en R1 a R3 y en las pruebas 1 a 4 y 6 (comprobar con `SELECT` contra la
  línea base);
- dejar la política en `whitelist_only`.

Resultado en la verificación: apartado nuevo «Staging — entrega E1».

**LIYBEN** (cuando Sergio lo decida): `git pull` como el UID 101 y reinicio de `odoo14_server`,
**sin `-u`**.

## 10. Riesgos y preguntas abiertas

### 10.1 Qué se degrada (por parche)

- **Parche 7:**
  - Ningún flujo de la interfaz ni del motor. Un cliente externo que leyera o escribiera la caché
    de `fetch_url` por RPC deja de poder hacerlo; no se conoce ninguno.
  - En el sandbox, el código del LLM tampoco puede usar `res.lang._get_cached` ni
    `website._get_cached`, que coinciden en el nombre (duda D-1).
- **Parche 8:** ninguno. El AI Administrator sigue gestionando la lista desde la interfaz (ACL
  `1,1,1,1`) y con el botón «➕ Whitelist». El alta automática con la política `open` y al
  confirmar no cambia.
- **Parche 9:** ninguno funcional. La caché sigue siendo global por skill y frase, y gana la
  primera fila (diseño del fabricante, sin cambios).
- **Parche 10:**
  - El canje de PIN se queda sin ningún punto de entrada. Ya no tenía llamador en los tres módulos;
    el único acceso era RPC. La mesa de entrega no puede entregar claves, lo que encaja con N4 a)
    (no usarla).
  - El botón «Release PIN blocks» sigue funcionando.
- **Sandbox (los cuatro):**
  - El código del LLM que use alguno de los 11 nombres se rechaza con el mensaje existente, que
    para los de lectura habla de «escrituras».
  - Si el usuario no es AI Writer, ese rechazo cancela sus verificaciones pendientes
    (comportamiento previo de cualquier código marcado como escritura).

### 10.2 Riesgos de regresión

| Riesgo | Efecto | Mitigación |
|---|---|---|
| Un llamador sin actualizar en `safe_plan.py:1619`, `agent_engine.py:785`/`:868` o `external_server.py:1018`/`:1080` | **Silencioso:** sin caché de `fetch_url` (sale a la red cada vez), sin caché de parámetros de skills o sin alta del dominio de un servidor (solo un aviso) | Tests `test_execute_fetch_url_serves_cache`, `test_agent_engine_uses_private_names` y `test_no_caller_uses_public_names`; `grep` del §5.4; R1, R2 y R3 en staging |
| Un llamador sin actualizar en `safe_plan.py:1667`/`:1723`, `:750`/`:757`, `safe_operation.py:1069`/`:1076`/`:1107` o `res_config_settings.py:349` | `AttributeError`: falla el paso `fetch_url`, la confirmación del plan, el botón «➕ Whitelist» o «Release PIN blocks» | Tests positivos de la clase 2; R2 y R5 |
| Renombrar por error `ai.api.result.cache.get_cached`/`store` (`safe_plan.py:1815`, `:1871`) | Rompería la caché de `api_call` | Aviso en el §4 y el §5.4. El `grep` del §5.4 no busca `Cache.get_cached(` |
| Falsos positivos del sandbox por nombre (`_get_cached`, `_store`, `_is_blocked`…) en código legítimo | Una consulta de relaxaicode se rechaza | Probabilidad baja: son nombres internos que el LLM no usa para leer datos de negocio. Se vigila en R6 y en E3 (lista de permitidos) |
| Clientes externos de LIYBEN que llamen a estos métodos por XML-RPC | Dejarían de funcionar | No consta ninguno (D-6) |
| Hueco del alias en el sandbox (`f = m._remember_for_skill; f(…)`) | Sigue abierta la escritura con commit propio desde la caja A para quien tenga acceso al chat o a MCP | Previo. Lo cierra E3; hasta entonces, mismo criterio de producción que N3 (E1 a E3) |

### 10.3 Cómo comprobar si el fabricante ya lo ha corregido (vigilancia, N12)

En la carpeta de la versión nueva, fuera del repo. Criterio común: el método ya no es público, o
lo es pero comprueba grupo o propiedad sobre `self.env.user` **antes** del primer `sudo()` o del
cursor propio. La prueba definitiva es pasar `test_seges_rpc_access.py` contra esa versión: si los
negativos pasan sin los parches de Seges, está corregido.

- **Parche 7 (PNS-90):**
  ```sh
  grep -nE "def _?(get_cached|store)\b" pns_ai_mcp/models/fetch_cache.py
  ```
  Corregido si solo salen `_get_cached`/`_store`, o si `get_cached`/`store` empiezan con
  `ensure_ai_admin`/`has_group`. Ojo: no confundirlo con `models/api_result_cache.py`, que es otro
  modelo.
- **Parche 8 (PNS-91):**
  ```sh
  grep -n "def _\?ensure_domain_whitelisted" pns_ai_mcp/models/url_whitelist.py
  ```
  Corregido si es privado, o si público comprueba `group_ai_admin` (o la política `open` más el
  grupo de URL externa) antes del `sudo()`.
- **Parche 9 (PNS-85):**
  ```sh
  grep -nE "def _?(remember_for_skill|lookup_for_skill)\b" pns_ai_mcp/models/ai_skill_param_cache.py
  grep -nE "def _?(remember|lookup)_param_cache\b" pns_ai_mcp/models/ai_skill.py
  grep -n "param_cache'" pns_ai_mcp/utils/agent_engine.py
  ```
  Corregido si los cuatro son privados, o si públicos comprueban AI Writer o AI Administrator y la
  lectura de la skill antes del cursor de superusuario.
- **Parche 10 (PNS-83):**
  ```sh
  grep -nE "def _?(redeem_key_pin|consume_key_pin)\b" pns_ai_mcp/models/mcp_user.py
  grep -nE "def _?(release_all|note_failure|is_blocked)\b" pns_ai_mcp/models/key_pin_block.py
  ```
  Corregido si son privados, o si el canje pasa a un controlador que toma la IP de la petición y no
  del llamador, y `release_all` comprueba `ensure_ai_admin`.
- **Sandbox:**
  ```sh
  grep -n "RELAXAICODE_SIDE_EFFECT_METHODS\|startswith('_')" pns_ai_mcp/controllers/validators.py pns_ai_mcp/controllers/context_builder.py
  ```
  Si el fabricante bloquea de forma general los métodos con `_` en `guarded_getattr` y en el AST,
  la parte de la lista de estos parches sobra; en ese caso, revisar también E3.

### 10.4 Dudas y decisiones para Sergio

- **D-1 — Nombres privados:**
  - **Recomendado:** usar los del seguimiento y el informe (`_get_cached`, `_store`,
    `_ensure_domain_whitelisted`…), más fáciles de seguir en la vigilancia.
  - **Alternativa:** nombres únicos (`_fetch_cache_get`, `_fetch_cache_store`) para que la lista
    negra del sandbox, que es por nombre, no bloquee `res.lang._get_cached` ni
    `website._get_cached`. Impacto bajo en los dos casos.

  Respuesta (20/10/2026): nombres del informe.
- **D-2 — Hueco del alias en el sandbox** (`f = m._metodo; f()`):
  - **a) Dejarlo para E3 (recomendado):** E3 bloquea todos los métodos con `_`, y producción exige
    E1 a E3 (N3).
  - **b) Ampliar ahora `_detect_requires_write_from_ast`** para marcar cualquier `ast.Attribute`
    con un nombre de la lista, aunque no sea una llamada. Una condición más en el validador, pero
    toca la lógica del resto de PNS-07 y afecta a los 15 nombres existentes.

  Respuesta (20/10/2026): a), el alias queda para E3.
- **D-3 — Métodos del mismo patrón fuera del alcance de E1** (no están en la lista del §2.2):
  - `ai.mcp.user.consume_key_pin` (público, `sudo`; por RPC falla porque espera un registro);
  - `ai.key.pin.desk.touch`, `close`, `any_open` y `notify_changed`, y `ai.key.pin.ask.collect` y
    `supply` (públicos, `sudo`; con un token o un registro);
  - `ai.api.result.cache.get_cached`/`store` (públicos, `sudo`, pero la clave incluye el uid de
    quien llama, así que cada usuario solo lee y escribe lo suyo);
  - `ai.fetch.cache.gc_expired` y `ai.api.result.cache.gc_expired` (borran filas caducadas).

  **Propuesta:** registrarlos en el seguimiento como resto de PNS-83 y del patrón común, y decidir
  si entran en E4 junto con PNS-92, 30 y 37. No se tocan en E1.

  Respuesta (20/10/2026): se registran como resto de PNS-83 y del patrón común, y van a
  E4.
- **D-4 — Licencia y cabecera del test nuevo:** Apache-2.0 con «Copyright (C) 2026 Seges» (como el
  módulo, recomendado) o AGPL-3 (licencia de los módulos propios del repo). Mezclar licencias
  dentro de un módulo Apache-2.0 complica la redistribución.

  Respuesta (20/10/2026): Apache-2.0 con «Copyright (C) 2026 Seges».
- **D-5 — Portal en staging:** el staging del 15-16/10 se hizo sin portal. ¿Se autoriza crear un
  usuario de portal temporal en `pns_demo` para repetir las pruebas 1, 2 y 4 con portal? Si no, el
  portal queda cubierto solo por los tests locales.

  Respuesta (20/10/2026): sí, un portal temporal en `pns_demo` que se borra al terminar.
- **D-6 — Integraciones externas en LIYBEN:** confirmar que ningún script o app llama por
  XML-RPC/JSON-RPC a estos métodos. No consta ninguno: no hay mesa de PIN (N4) y no se conocen
  clientes de la caché.

  Respuesta (20/10/2026): sin integraciones RPC en LIYBEN (`odoo-access.log` de Nginx
  desde el 10/10/2026: ninguna petición a `/xmlrpc` ni `/jsonrpc`).
- **D-7 — Commits:** `controllers/validators.py` lo tocan los cuatro parches (un bloque de dos
  líneas cada uno). ¿Se seleccionan líneas en GitHub Desktop para mantener un commit por parche, o
  se acepta que la lista del sandbox vaya en el commit del parche 10, con los cuatro marcadores?

  Respuesta (20/10/2026): un commit por parche, seleccionando líneas.
- **D-8 — Política `open`:** con `open`, `_maybe_auto_whitelist` sigue añadiendo dominios cuando
  confirma cualquier usuario con `group_ai_external_url`. Es diseño del fabricante y no lo cambia
  E1; confirmar que se acepta (la guía recomienda `whitelist_only`).

  Respuesta (20/10/2026): aceptada (LIYBEN y staging en `whitelist_only`).

## 11. Árbol de archivos

Módulo existente: no se crea `readme/`, `README.rst` ni `static/description/`.

```
pns_ai_mcp/
├── controllers/
│   ├── safe_plan.py              (parches 7 y 8: líneas 750, 757, 1619, 1667, 1723)
│   └── validators.py             (parches 7 a 10: RELAXAICODE_SIDE_EFFECT_METHODS)
├── models/
│   ├── fetch_cache.py            (parche 7)
│   ├── url_whitelist.py          (parche 8)
│   ├── safe_operation.py         (parche 8: líneas 1069, 1076, 1107)
│   ├── external_server.py        (parche 8: líneas 1018, 1080)
│   ├── ai_skill_param_cache.py   (parche 9)
│   ├── ai_skill.py               (parche 9: líneas 329, 334, 338, 343)
│   ├── mcp_user.py               (parche 10: líneas 819-820, 831, 839)
│   ├── key_pin_block.py          (parche 10)
│   └── res_config_settings.py    (parche 10: línea 349)
├── utils/
│   └── agent_engine.py           (parche 9: líneas 785, 868)
└── tests/
    ├── __init__.py               (registro del test nuevo)
    └── test_seges_rpc_access.py  (NUEVO)
docs/pendiente/parches_pns_ai.md  (entradas de los parches 7 a 10: programador)
```

Sin cambios en `__manifest__.py`, `security/ir.model.access.csv`, vistas, datos, `i18n/`,
`LICENSE`, `NOTICE`, `pns_base`, `pns_ai_chatboo` ni en los parches 1 a 6.

## Notas de implementación

- **Test de control:** `test_control_session_ok` usa `res.users.context_get` (disponible para
  interno y portal) en lugar de `ai.url.whitelist.is_domain_whitelisted` (§9.1).
- **Cabecera del test:** sin la línea `# -*- coding: utf-8 -*-` del §9.1 (UP009: innecesaria en
  Python 3).
- **Lint:** `R0911 too-many-return-statements` en `mcp_user.py` aceptado: es un aviso previo del
  fabricante que sale como nuevo por la línea `def` renombrada (`_redeem_key_pin`).
- **`_own_cursor_env`:** se simula en `test_skill_param_cache_roundtrip`; el camino real con
  cursor propio lo cubre R3 en staging.
