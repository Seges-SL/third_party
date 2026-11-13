# Propuesta de la fase 3 sobre 3.1.973 (parches 24 y 18; tests del 23)

- **Fecha:** 12/11/2026. **Rama:** `14.0-pns-ai-3973`. **Laboratorio:** `lab_pns_ai_3973` (BD `lab_pns_ai_3973_14`).
- **Plan:** [plan_correccion_pns_ai_3973.md](plan_correccion_pns_ai_3973.md), decisiones 3 y 5, «Fase 3», «Tests».
- **Registro:** [parches_pns_ai.md](parches_pns_ai.md), parches 18, 23 y 24 de la rama 3879 (E2′ y sus revisiones) y
  secciones de la rama 3973 (fases 2a, 2b y 2c).
- **Estado:** propuesta presentada el 12/11/2026; decisiones de Sergio del mismo día (abajo). La 3a se implementa;
  la 3b espera al inventario de la decisión 2 y a la aprobación del script de P-22.

## Decisiones de Sergio (12/11/2026)

1. **División:** 3a y 3b. Se empieza solo por la 3a.
2. **B2 sí** (vaciado de las columnas secretas al terminar cada helper de módulo). Antes de la 3b: inventario
   (archivo:línea) del código del motor que, durante la ejecución en la caja A, lee una columna secreta en `sudo`
   fuera de los helpers (`related` con `related_sudo`, `compute_sudo`, métodos públicos de modelos permitidos). Si sale
   alguna vía, se presenta antes de decidir. Test nuevo: `related` no guardado que acaba en un secreto, rechazado, y
   después `browse(id).<secreto>` del modelo destino, que no debe dar el secreto.
3. **`value` de `ir.config_parameter` sí**, con la cita de por qué `_pns_hidden_column('value')` sobre un recordset
   vacío da verdadero (abajo, «Parche 18»).
4. **«Caché de otros modelos»**, como resto conocido en el registro, con su alcance exacto.
5. Esta propuesta se guarda aquí.

**Condiciones:**
- a) Escrituras pendientes: `test_pending_writes_survive_box_a` lee la columna en `sudo` dentro de la caja A antes de
  comprobar que la escritura llega al cursor del llamador. Para la 3b, valorar un `flush` de las columnas secretas con
  el `env` del llamador antes de invalidar, y presentarlo (no se aplica sin aprobación).
- b) `test_sudo_does_not_lift` no se quita sin sustituto (ver «Tests de la 3b»).
- c) Antes de la batería de la 3a, `auth_totp` en la BD de tests; si `test_c2_no_access_field_via_user` se salta, parar
  y avisar.
- d) Tests por nombre y recuento recalculado (abajo).
- e) Una neutralización que dé E en vez de F se documenta por nombre, sin cambiar el test.
- f) P-22: el script se presenta antes de ejecutarlo; `ai.key.pin.ask` y `ai.api.key.wizard` se deciden con el
  resultado.

## Orden

- **3a:** `pns_ai_mcp/tests/seges_common.py` (`_StubController`), parche 24, `test_seges_identity_su` y los tests del
  23 (`test_seges_sandbox_env`, `test_seges_format_guard`, `test_seges_facade_class`, `test_seges_skill_env`).
- **3b:** parche 18 (B y B2), `test_seges_sandbox_credentials` reescrito y P-22 justo después.
- **Motivo:** los tests del 23 no dependen del 18 y usan el mismo arnés que el 24. El 18 es la única parte con el
  diseño abierto, y P-22 o el inventario pueden llevar a la opción A: en ese caso solo se rehace la 3b.

## Parche 24 (3a)

`pns_ai_mcp/controllers/context_builder.py`, 4 marcadores, como en la rama 3879:
- `_identity_no_su(env, name)` antes de `class GuardedSandboxEnv`;
- `_IDENTITY_NO_SU = ('user', 'company', 'companies')` junto a `_ALLOWED_ENV_ATTRS`;
- en `__getattr__`, antes de devolver un nombre de `_ALLOWED_ENV_ATTRS`, la rama que devuelve `_identity_no_su`. Vale
  también para lo que devuelven `with_context`, `with_company` y `env(context=…)`, que vuelven a pasar por el
  envoltorio;
- los globales `user` y `company` de `build_safe_context`.

Qué cubre el fabricante: la lista cerrada de `GuardedSandboxEnv` (`sudo`, `with_user` y `env` fuera). Qué no:
`env.user`/`env.company`/`env.companies` llevan `su` (`odoo/api.py:548`). Con `su`, su guardián de columnas secretas no
mira (`_pns_sandbox_reads`, `models/sandbox_secret_read.py:65-66`), ni tampoco los permisos de acceso, las reglas de
registro y los grupos de campo, en toda la cadena de relaciones. Se degrada lo mismo que en la rama 3879.

## Parche 18, opción B + B2 (3b; propuesta, sin aplicar)

- `pns_ai_mcp/controllers/controller_helpers.py`: función privada `_seges_forget_secret_columns(env)`.
  - Los pares `(modelo, campo)` con `env[m].browse()._pns_hidden_column(f)` verdadero, guardados por registro (nombres, no
    objetos `Field`, que se recrean en cada carga de modelos).
  - `env.cache.invalidate([(campo, None), …])`: la caché es una por hilo (`odoo/api.py:472, 769`), así que vale para
    todos los entornos del hilo.
  - Se llama en `open_readonly_env` justo después de crear el `env` (`:211-217`) y antes de anular el `commit`
    (`:220`). Si falla, la caja A no se abre (`rollback`, `close`, `UserError`, como `:195-209`).
- **B2** (`controllers/context_builder.py`, `collect_sandbox_helpers`, `:972-975` en 3.1.973 limpia): si
  `sandbox_cursor(env.cr)`, cada helper de módulo se envuelve en `try/finally`, que vacía lo mismo al terminar. Cierra el
  caso de `page_url`/`page_edit`: la llamada de diseño lee la clave del proveedor en `sudo`
  (`models/ai_provider.py:210`) dentro de la caja A.
- **Criterio (decisión 3):** el del fabricante, `_pns_hidden_column`. Sobre un recordset vacío da lo mismo que
  `secret_column` (`models/sandbox_secret_read.py:68-69`) más `value` de `ir.config_parameter`:
  - `IrConfigParameter._pns_hidden_column` (`models/sandbox_secret_read.py:138-141`): `if name == 'value' and
    self._pns_secret_rows(): return True`;
  - `_pns_secret_rows` (`:143-151`): `if not self: return True` (`:145-146`), «True for a search over the model»: el
    recordset vacío cuenta como búsqueda sobre todo el modelo.
- **Escrituras pendientes:** Odoo 14 las guarda en `env.all.towrite` (`odoo/api.py:773`), aparte de la caché.
  `Cache.invalidate(spec)` (`odoo/api.py:904-916`) no las toca, y la siguiente lectura las escribe antes de leer
  (`_read` → `flush(fields, self)`, `odoo/models.py:3101-3103`). **Pero** (condición a): si la caja A lee esa columna
  (también en `sudo`, desde un helper) con una escritura pendiente del llamador, ese `flush` la escribe en el cursor
  `READ ONLY` de la caja A: falla y la cola de ese modelo ya se ha sacado (`odoo/models.py:5473-5530`, `towrite.pop`).
  Es del fabricante y no lo cambia el vaciado; `test_pending_writes_survive_box_a` lo mide. Para la 3b se presentará el
  `flush` previo (abajo).
- **Flush previo (condición a, para presentar):** en `open_readonly_env`, antes de invalidar, `flush` de las columnas
  secretas con pendientes en `towrite`, en el cursor del llamador (`base_env`, en `su` para no depender de sus
  permisos). Así la caja A no encuentra nada pendiente de esas columnas. Efectos: el `flush(fnames)` de Odoo 14 escribe
  todos los pendientes del modelo afectado, no solo la columna secreta, y adelanta esas escrituras (y sus errores) a la
  apertura de la caja A. No cubre otras columnas pendientes del llamador que la caja A lea (mismo defecto del
  fabricante, fuera del alcance del 18).
- **Qué se degrada:** el motor vuelve a leer esas columnas de la BD (una `SELECT`); los registros `new()` del llamador
  pierden el valor secreto en caché (ningún llamador de la caja A los tiene); los campos no secretos de los 11 modelos de
  la rama 3879 vuelven a poder leerse (P-22).

## Inventario de la decisión 2 (12/11/2026, solo lectura)

**Mecanismo** (Odoo 14): `Field.__get__` devuelve lo que haya en la caché sin comprobar nada (`odoo/fields.py:992-993`).
Un campo calculado no guardado se calcula en `__get__` sin pasar por `check_field_access_rights`
(`odoo/fields.py:1036-1047`, `compute_value` en `:1181-1203`); los `related` se calculan en `sudo` por defecto
(`odoo/fields.py:345-349`). El guardián del fabricante solo actúa en `check_field_access_rights` y `_flush_search`
(`models/sandbox_secret_read.py:111-127`). Por tanto, todo lo que lea una columna secreta en `sudo` **durante** la
ejecución la deja en la caché del hilo, y el sandbox la puede leer después por id. El vaciado al abrir (B) no lo cubre;
B2 solo lo cubre si la lectura sale de un helper de módulo.

**Vías encontradas** (por lectura de código; **ninguna comprobada en ejecución**):

| Id | Dónde | Qué deja en la caché | Quién llega |
|---|---|---|---|
| V1 | `pns_ai_mcp/models/external_server.py:211-216` (`auth_call_preview`, no guardado), `:383-386` (compute), `:388-393` (`self.sudo().auth_token`) | `ai.api.server.auth_token` | lectura de `ai.api.server` para `base.group_user` (`security/ir.model.access.csv:7`); el modelo es catálogo para `env[...]`, pero se llega por relación o `Reference`. El atributo literal `.auth_token` lo rechaza el fabricante por nombre (`controllers/validators_base.py:217`); `rec['auth_token']` y `mapped('auth_token')` no pasan por ese filtro |
| V2 | `pns_ai_mcp/models/mcp_user.py:314-321` (`user_has_mcp_api_key`, `@api.model`, público) | `ai.mcp.user.mcp_api_key_hash` de cualquier usuario (`sudo().search`) | modelo de credenciales para `env[...]` (`validators_base.py:190`), alcanzable por `Reference`; el hash está en `_pns_secret_fields` (`mcp_user.py:76`) |
| V3 | core `auth_totp/models/res_users.py:56-59` (`_compute_totp_enabled`, no guardado) | `res.users.totp_secret` de cualquier usuario (`self.sudo()`) | cualquier interno: `totp_enabled` no tiene grupos. Después, `browse(id).totp_secret` desde la caché. Semilla TOTP: **crítica** si se confirma. No depende de la versión del fabricante (también en la rama 3879 y en LIYBEN) |
| V4 | core `auth_signup/models/res_partner.py:38-43` (`_compute_signup_valid`) y `:45-53` (`_compute_signup_url`, que lee en `sudo` antes de su propia comprobación de escritura) | `res.partner.signup_token` | cualquier interno que lea el contacto. Token de invitación o de cambio de contraseña: toma de cuenta si hay uno vigente. Igual que V3, no depende del fabricante |
| V5 | `related` no guardados que acaban en un secreto (con `related_sudo`): ninguno en `pns_*`; en el core solo `website` (`res_config_settings.py:34, 68`), `website_twitter` (`:30, 34`) | el valor lo devuelve el propio campo, sin pasar por el guardián | solo si esos módulos están instalados (no en la BD de tests ni en el laboratorio; LIYBEN, por comprobar). `pad_key`, `google_analytics_key` y `website_slide_google_app_key` no son secretos con el criterio del fabricante |

- **Sin vía** (revisados): `ai.provider.test_connection` (en la lista de efectos del fabricante); `_api_key_for_inference`,
  `_resolve_auth_token`, `_fields_to_json`, `_touch`, `_take`, `_supply`, `_build_headers`, `_stdio_start` (privados);
  `mcp_user.clear_mcp_api_key` y `mcp_api_key_wizard.action_generate` (escriben: fallan en el cursor `READ ONLY`; el
  primero lee como el usuario, con control); `mcp_api_key_wizard._compute_has_api_key` (lee como el usuario: el guardián
  lo rechaza). Ningún `compute_sudo=True` ni `related` a un secreto en `pns_*`.
- **Nota sobre `totp_secret`:** en la rama 3879, la lectura directa de `totp_secret` sin `su` sí pasaba por
  `check_field_access_rights` (log `tests-20261028-093749.log`, «Access Denied by ACLs … fields: totp_secret»); no he
  localizado por qué, siendo un campo calculado no guardado. V3 no usa esa ruta: lee de la caché tras `totp_enabled`.
  - **Corrección (12/11/2026, Sergio):** en el Odoo del laboratorio (imagen con `odoo` 14.0.20231106) `totp_secret`
    es un `Char` **guardado** con `groups=NO_ACCESS` (`auth_totp/models/res_users.py:27`); el calculado no guardado
    es `totp_enabled` (`:28`, `_compute_totp_enabled` en `:53-55`). Por eso la lectura directa pasa por
    `_fetch_field`, que llama a `check_field_access_rights`. V3 entra por la caché que deja `totp_enabled`.
  - El error vino de la referencia `/opt/odoo-src/14.0`, que es una 14.0 posterior: en ella `totp_secret` es calculado
    con SQL (`_compute_totp_secret`, `:162-165`) y las líneas de V3 son `:56-59`. **Aviso:** en un servidor con esa 14.0
    posterior, la lectura directa de `totp_secret` no pasaría por `_fetch_field` (se calcula en `__get__`). Antes del
    staging y de LIYBEN conviene comprobar qué versión de `odoo` tienen.
- **Test de la decisión 2:** en la BD de tests no hay ningún `related` no guardado que acabe en un secreto (V5 solo
  existe con `website`). Opciones, para decidir: (i) el mismo test con V3 o V4 (cálculo en `sudo` y después
  `browse(id).<secreto>`); (ii) un campo manual `x_` relacionado creado en el test (recarga el registro: frágil);
  (iii) esperar a tener un módulo con uno.

**Opciones para cerrar V1 a V5 (para decidir; nada aplicado):**
- **O1, comprobar al acceder:** en la caja A y sin `su`, rechazar la lectura de una columna con `_pns_hidden_column`
  verdadero, venga de la caché o no: `_read_attr` (`controllers/context_builder.py:247-261`, lecturas literales y
  `getattr`) y `__getitem__`/`mapped` de `base`. Cierra V1 a V5, también los `related`. Quedan otras rutas que usan
  `__get__` por dentro (`filtered`/`sorted` con nombre, `export_data`): inventario aparte.
- **O2, vaciar tras cada cálculo:** sobrescribir `_compute_field_value` en `base` para vaciar las columnas secretas en el
  cursor de la caja A. Cierra el resto en caché de V1 a V4, no V5.
  - **Corrección (12/11/2026, Sergio):** O2 tampoco cubre V2: `user_has_mcp_api_key` es un método, no un cálculo, y
    no pasa por `_compute_field_value`. O2 cubre V1, V3 y V4.
- **O3:** solo B y B2, y V1 a V5 como restos conocidos. No recomendado para V3 y V4.
- **Recomendación:** comprobar antes V1 a V4 con un script de solo lectura (`odoo-dev 14 shell`, con `rollback`, que no
  imprime valores, solo «filtra / no filtra»), presentado antes de ejecutarlo; después, O1 con B y B2 como defensa.

## Tests (condición d)

**3a, por nombre** (fase 0 → 3a):
- `test_seges_identity_su` (5 → 5): `test_wrapper_user_not_su`, `test_wrapper_company_not_su`,
  `test_identity_helper_not_su`, `test_positive_reads_own_user_company`, `test_c2_no_access_field_via_user` (acepta
  también «holds a credential»).
- `test_seges_sandbox_env` (**12** → 12; el registro de E2′ lista 12 y dice 13: son 12, y la propuesta repitió el 13 por
  error): negativos sin mensaje `test_env_cache`, `test_env_cache_get_warm`, `test_env_all`, `test_alias_all`,
  `test_state_attrs`, `test_composite_getattr`, `test_attrgetter`, `test_walk_to_other_environment`,
  `test_wrapper_allowlist`; sin cambios `test_builtin_all_and_cache_name`; invertidos `test_allowed_attrs` y
  `test_engine_attrs_on_wrapper`, que pasa a llamarse `test_engine_attrs_refused_on_wrapper`.
- `test_seges_format_guard` (31 → **19**): `TestSegesFormatGuard` tenía 20 (19 tras quitar `test_markup_rejected_unit`) y
  `TestSegesEngineNames` 11 (se quita entera). Quedan `test_c1_exact_payload`, `test_template_in_variable`,
  `test_template_concatenated`, `test_template_from_call`, `test_bound_method_in_variable`, `test_str_format_unbound`,
  `test_getattr_format`, `test_attrgetter_methodcaller_format`, `test_nested_spec_dunder`, `test_format_map_dunder`,
  `test_pns36_cr_dbname`, `test_v1_import_formatter`, `test_v2_type_attrgetter`, `test_literal_attr`,
  `test_numeric_spec`, `test_format_map_dict`, `test_translated_template_in_variable`, `test_getitem_mapping` y
  `test_control_sandbox_ok`.
- `test_seges_facade_class` (10 → 9): sin `test_type_itemgetter_class`.
- `test_seges_skill_env` (1 → 1): `test_customer_360_runs`.

**3b, `test_seges_sandbox_credentials`** (fase 0: **32**; el registro dice 31 porque es de antes de un test posterior;
por nombre son 32): 26 en `TestSegesSandboxCredentials`, 1 en `TestSegesOutsideBoxA` y 5 en `TestSegesBoxAReal`.
- Se quita `test_marker_cleared_after_box_a`.
- `test_sudo_does_not_lift` se sustituye (condición b) por `test_sandbox_cannot_reach_sudo`: por la herramienta real,
  `rec.sudo()`, `getattr(rec, 'su' + 'do')()`, `rec.with_user(1)`, `env(su=True)` y `env.su`, rechazados y sin el
  secreto. El fabricante cubre `env.sudo()`, `getattr(env.user, 'su' + 'do')()` y `env(su=True)`
  (`test_relaxaicode_sandbox_escapes_e2e.py:65-68`), pero no un registro cualquiera, `with_user` ni `env.su`.
- Nuevos: `test_box_a_icp_cache_before_run`, `test_pending_writes_survive_box_a` (con la lectura en `sudo` de la
  condición a), `test_new_records_survive_box_a`, `test_helper_sudo_read_forgotten` (B2) y el de la decisión 2.
- Resultado: 32 − 1 + 5 = **36**.

**Recuento:**

| Tras | Batería |
|---|---|
| 3a | 388 + 5 + 12 + 19 + 9 + 1 = **434** (no 435) |
| 3b | 434 + 36 = **470** (no 468/469), sin contar lo que decidas para V1 a V5 |

Ningún test de la batería actual se quita. Esperado en las dos: 1 F (`test_paap_i7`, por diseño), 0 E y 4 saltados.

## Neutralización

| Prueba | Cambio | Deben fallar (F) |
|---|---|---|
| N24a | `_identity_no_su` devuelve `env.user`/`env.company`/`env.companies` | `test_wrapper_user_not_su`, `test_wrapper_company_not_su`, `test_identity_helper_not_su` (3 subtests) y `test_c2_no_access_field_via_user` |
| N24b | sin la rama de `__getattr__` | `test_wrapper_user_not_su` y `test_wrapper_company_not_su` |
| N24c | globales `env.user`/`env.company` | `test_c2_no_access_field_via_user` |
| N18, N18i, N18w, N18h | (3b) sin vaciado, sin `value`, caché entera, sin B2 | según la propuesta del 12/11/2026; se fijan al presentar la 3b |

Los tests del 23 no se neutralizan: no hay código de Seges detrás.

## P-22 (3b)

Script de solo lectura (metadatos de `_fields` y `ir_model_access` con `SELECT`, `rollback` al final, sin leer filas),
presentado antes de ejecutarlo (condición f). Para los 11 modelos de `box_a_guard`: cada campo fuera de su lista
permitida, con tipo, `store`, `related`, `groups`, `prefetch`, `secret_column`, `_pns_hidden_column` y grupos con lectura.
`ai.key.pin.ask` (`pin`, `supplied_key`) y `ai.api.key.wizard` (`generated_key`, `manual_key`) se deciden con el
resultado.

## Implementación de la 3a (12/11/2026)

- Hecha. Detalle en el [registro](parches_pns_ai.md), «Parches de la rama 14.0-pns-ai-3973 (fase 3a)». Resultado: 434
  tests, 1 F (`test_paap_i7`), 0 E y 4 saltados; N24a, N24b y N24c, como en la tabla de «Neutralización».
- **Corrección a «Parche 24 (3a)»:** en Odoo 14 solo `env.user` lleva `su` siempre (`odoo/api.py:548`).
  `env.company` y `env.companies` lo llevan solo cuando no hay `allowed_company_ids`; la caja A de 3.1.973 siempre los
  pone, así que en ella ya van sin `su`. El 24 sigue siendo necesario por `user`.
- **Cambio en un test no previsto en la propuesta:** `test_seges_identity_su` ejecuta la herramienta como
  `base.user_admin` en lugar de un usuario creado en el test. El cursor de la caja A no lo ve, y `env.company` sin `su`
  daba «Access to unauthorized or invalid companies». Lo mismo pasaba con el código del fabricante.
- `test_allowed_attrs` no comprueba `env.with_context`: no existe en el `Environment` de Odoo 14.


## V3 en las dos variantes de Odoo 14 y cómo las cubre O1 (12/11/2026, solo lectura de código)

Citas de Odoo: las del contenedor (`odoo` 14.0.20231106, `/usr/lib/python3/dist-packages/odoo`), salvo en la variante
posterior, que cita `/opt/odoo-src/14.0`. Nada se ha ejecutado.

### Variante del contenedor (los tests corren en ella)

- `totp_secret` es un `Char` guardado con `groups=NO_ACCESS` (`addons/auth_totp/models/res_users.py:27`).
- **Lectura directa** sin `su`: con la caché vacía va a `_fetch_field` (`odoo/fields.py:1015-1020`), que llama a
  `check_field_access_rights` (`odoo/models.py:3056-3060`), donde salta el guardián del fabricante. Se rechaza.
- **Vía V3, por la caché:** `totp_enabled` (`res_users.py:28`, cálculo en `:53-55`) lee `totp_secret` en `sudo` y lo
  deja en la caché del hilo. Después `browse(id).totp_secret` lo encuentra en `odoo/fields.py:993` y lo devuelve sin
  comprobar nada.

### Variante 14.0 posterior (`/opt/odoo-src/14.0`)

- `totp_secret` pasa a ser un campo calculado no guardado (`res_users.py:28`). Su cálculo `_compute_totp_secret`
  (`:162-165`) hace `SELECT totp_secret FROM res_users` directamente en el cursor, sin pasar por el ORM.
- Un campo calculado no guardado no se calcula en `sudo` por defecto (`odoo/fields.py:341`), así que el cálculo corre
  como el usuario del sandbox. Pero `__get__` (`odoo/fields.py:974` y siguientes) no llama a
  `check_field_access_rights` ni mira `groups`:
  - el guardián del fabricante (`models/sandbox_secret_read.py:111-127`) no llega a ejecutarse y `NO_ACCESS` no se aplica;
  - el `SELECT` funciona en el cursor `READ ONLY` de la caja A;
  - `browse(id)` no comprueba permisos.
- **Conclusión:** `browse(id).totp_secret` desde el sandbox **filtraría directamente**, sin pasar por `totp_enabled` y
  aunque el parche 24 esté aplicado. Basta el id de un usuario con TOTP activado. `read(['totp_secret'])` sí se
  rechaza, porque `read` comprueba los campos.
- **Consecuencia para los tests:** con esta variante, `test_c2_no_access_field_via_user` fallaría incluso con el
  parche 24. En el contenedor pasa solo porque el campo está guardado.
- **Antes del staging y de LIYBEN:** comprobar qué versión de `odoo` tienen. Con la posterior, V3 es una lectura
  directa por id, sin pasar por la caché.

### Cómo cubre O1 las dos variantes

Comprueba en el momento de leer, antes de llegar a `Field.__get__`. Así da igual que el valor venga de la caché
(variante del contenedor) o de un cálculo con SQL (variante posterior).

- **Condición:** el recordset está en el cursor de la caja A sin `su` (`_pns_sandbox_reads`) y
  `self._pns_hidden_column(nombre)` es verdadero. Entonces se rechaza con `_pns_deny_column`, el mensaje del fabricante.
- **Criterio, el del fabricante:**
  - `field_is_secret` marca `totp_secret` por el nombre en las dos variantes (es `char` y contiene `secret`);
  - también marca `signup_token` (V4), `auth_token` (V1), `mcp_api_key_hash` (V2, en `_pns_secret_fields`) y los
    `related` de V5;
  - para `ir.config_parameter` decide fila a fila.
- **Puntos de enganche:**
  1. `_read_attr` (`controllers/context_builder.py:247-261` en 3.1.973 limpia), por donde pasan las lecturas literales
     `rec.x` (`sandbox_attr`) y `getattr`, `attrgetter` y `methodcaller`.
  2. `__getitem__` de `base` con clave de texto (Odoo: `odoo/models.py:5702-5716`). Cubre `rec['x']`, `sorted('x')`
     (que usa `itemgetter`, `odoo/models.py:5452`) y `name_get` (`record[_rec_name]`).
  3. `mapped` de `base` con ruta de texto, comprobando cada tramo (Odoo: `odoo/models.py:5285-5293`). `Field.mapped`
     lee de la caché sin pasar por `__getitem__` (`odoo/fields.py:1085-1112`). Cubre también `filtered('x')`
     (`odoo/models.py:5328`).
- **Lo que no cambia:** las lecturas en `sudo` del motor siguen funcionando, porque el control no mira en `su`. Como el
  rechazo es en el acceso, B y B2 pasarían a ser una defensa adicional, no la única barrera.
- **Lo que queda fuera:** código Python del propio Odoo o de los módulos que, ya dentro de un método, lee el campo con
  `rec.x` y luego devuelve el valor al sandbox (por ejemplo, un método público que devuelva `self.sudo().totp_secret`).
  Necesita un inventario aparte de métodos públicos que devuelvan secretos; V2 ya es un ejemplo, aunque devuelve un
  booleano.
- **Tests propuestos:**
  - V3 en la variante del contenedor: `totp_enabled` y después `browse(id).totp_secret`, `rec['totp_secret']` y
    `mapped('totp_secret')`;
  - la variante posterior no se puede probar aquí; queda cubierta por el mismo punto de control.

## Datos de LIYBEN (12/11/2026, comprobados por Sergio con consultas de solo lectura)

LIYBEN es el entorno de la prueba final. Responde al aviso «Antes del staging y de LIYBEN» de la sección anterior.

- **Core de Odoo que corre:** el del commit `cc0060e889603eb2e47fa44a8a22a70d7d784185` (22/10/2024), montado sobre
  `/usr/lib/python3/dist-packages/odoo`. El `dpkg-query` de su imagen dice 14.0.20231106, pero no es lo que corre.
  **La versión se comprueba en el código montado, no con `dpkg`.**
- **`totp_secret`:** calculado por SQL (`auth_totp/models/res_users.py:28`). LIYBEN tiene la **variante posterior**:
  V3 es allí una lectura directa por id, sin pasar por la caché (ver «Variante 14.0 posterior»).
- **Datos expuestos hoy:**
  - 0 usuarios con TOTP: V3 no tiene hoy ninguna semilla que dar en LIYBEN, pero la tendrá en cuanto alguien active
    TOTP;
  - 7 tokens de registro vigentes sin caducidad (V4): 6 de usuarios de portal archivados y 1 de un contacto sin
    usuario; ninguno de un usuario interno.
- **Consecuencia para las pruebas:** la batería del laboratorio corre en la variante del contenedor (`totp_secret`
  guardado). Lo que se pruebe allí no demuestra el comportamiento de LIYBEN para V3; ver la preparación de la 3b.
- **Referencia = LIYBEN (comprobado por Sergio, 12/11/2026):** `/opt/odoo-src/14.0/odoo` está en el mismo commit
  `cc0060e889603eb2e47fa44a8a22a70d7d784185` que el core montado de LIYBEN (`/opt/odoo/odoo-core`). Coinciden los
  SHA-256 (16 primeros caracteres) de los cuatro archivos que importan aquí, en la referencia y en LIYBEN:

  | Archivo | SHA-256 (16) |
  |---|---|
  | `addons/auth_totp/models/res_users.py` | `a8bb617ffd88f3b8` |
  | `addons/auth_signup/models/res_partner.py` | `c848abd85790cadd` |
  | `odoo/fields.py` | `f915e7114ceb705d` |
  | `odoo/models.py` | `aae6b5a0c3027136` |

  Para estas citas, la referencia `/opt/odoo-src/14.0` **es** el Odoo de LIYBEN. Las citas de la «variante posterior»
  valen para LIYBEN.

## `signup_url` y `signup_get_auth_param`: comportamiento del core, sin parche (12/11/2026)

Junto a la ficha 16, «Tokens de portal», de la [hoja de E4′](e4_hoja_3879.md) (`:90` y `:415-422`; decidido el
09/11/2026: sin acción, no va al informe).

- **`res.partner.signup_url`** (`auth_signup`, campo calculado no guardado y sin grupos): la URL lleva el token
  (contenedor: `addons/auth_signup/models/res_partner.py:96-99`; la construye `_get_signup_url_for_action` en `sudo`).
  La comprobación de escritura de `_compute_signup_url` solo mira los usuarios activos del contacto. Por eso un usuario
  interno la lee para un contacto sin usuario o con usuarios archivados, siempre que el token tenga `signup_type`.
- **`res.partner.signup_get_auth_param`** (método público, contenedor `:106-123`): devuelve `auth_signup_token` a un
  usuario interno si el alcance de registro es `b2c`.
- **Decisión de Sergio (12/11/2026):** las dos son comportamiento del core. El mismo usuario interno las alcanza por
  RPC: el sandbox no da más acceso. Quedan **sin parche y fuera de O1/O1b**. Solo entrarían si se demuestra que desde el
  sandbox se llega más lejos que por RPC con el mismo usuario.
- **V4 sigue siendo `signup_token`**: grupo `base.group_erp_manager`; en LIYBEN, calculado por SQL. Por RPC no se lee.
  Desde el sandbox se lee por la caché que deja `signup_valid` (contenedor) o directamente (LIYBEN).
- **LIYBEN hoy:** sus 7 tokens (6 de usuarios de portal archivados y 1 de un contacto sin usuario) son alcanzables por
  `signup_url` para cualquier interno si tienen `signup_type`. Es una observación del core, no un hallazgo del sandbox.

## Decisiones de Sergio sobre V1 a V5 y la 3b (12/11/2026)

1. Lecturas P1, P2 y P3 aprobadas.
2. **Confirmación de V1 a V4:** `pns_ai_mcp/tests/test_seges_box_a_vias.py` (22 tests), en un bloque nuevo de Seges de
   `tests/__init__.py`, con la batería de los tres módulos en una BD de tests desechable. Si F y E no coinciden con lo
   esperado, se informa sin cambiar el test.
3. **Pérdida de escrituras al cerrar la caja A** (`sql_db.py:307` → `clear_env`, `:82-87` → `env.clear()`,
   `api.py:620-627`): con el resultado del test se prepara la propuesta de un parche propio (número de Sergio):
   `flush()` del `env` del llamador antes de abrir la caja A, en `open_readonly_env`. Por ahí pasan los tres sitios que
   la abren (`controllers/main.py:1648-1650` y `utils/engine_tool_run.py:28-30` por `get_readonly_env`;
   `utils/skill_runtime.py:250` directamente). Se anota también como hallazgo para el seguimiento del informe al
   fabricante. Sin implementar.
4. **Diseño, aprobado en principio:**
   - O1 con el cuarto enganche (`mapped`, `compute_value` y `determine_value` sobre objetos `Field`, en `_read_attr`);
   - criterio del fabricante (`_pns_hidden_column`/`_pns_deny_column`) más `check_access_rights('read')` del modelo;
   - **sin** `check_field_access_rights`;
   - B y B2 como defensa.

   O1b queda como salida si aparecen métodos que lean sin `su` y devuelvan el valor. Los que hoy no lo hacen quedan como
   resto conocido. Se prepara la propuesta de implementación de la 3b (parche 18 con O1, B y B2), sin implementar.
5. **Laboratorio con el core de LIYBEN** (`DOCKERFILE` propio): aplazado a «Con toda la rama», antes de la prueba en
   LIYBEN.
6. Estas decisiones, aquí.

**Hallazgos de P1 a P3 (12/11/2026, solo lectura):**
- P1: los tres sitios que abren la caja A pasan por `open_readonly_env` (`controller_helpers.py:179`). Ninguno hace
  `flush` antes.
- P2: `iap.account.get` (`iap/models/iap_account.py:33-74`, contenedor) no devuelve un recordset en `sudo`. Pero, si
  hay cuentas sin token, las borra en `sudo` en un cursor propio (`:44-54`); si no hay cuenta, crea una y la
  **confirma en un cursor propio** (`:55-71`), y deja `account_token` en la caché (`:72-73`). Desde la caja A es una escritura que se escapa (familia de los parches 15 y 22). El token nuevo en caché lo
  cierra O1. El nombre `get` no puede ir a la lista de efectos (rompería `dict.get`). Pendiente de decisión aparte.
- P3: módulos de la BD de tests: `auth_signup`, `auth_totp`, `base`, `base_import`, `base_setup`, `bus`, `fetchmail`,
  `iap`, `mail`, `mail_bot`, `partner_autocomplete`, `phone_validation`, `sms`, `snailmail`, `web`, `web_editor`,
  `web_tour`, `web_unsplash` y los tres `pns_*`. Ni `website` (V5) ni `payment`, `google_*` o `microsoft_*`.
- P2, decisión de Sergio (12/11/2026): pendiente de decisión, **fuera de la 3b**.

## Confirmación de V1 a V4 (12/11/2026)

- **Tests:** `pns_ai_mcp/tests/test_seges_box_a_vias.py`, 22, en el bloque nuevo de Seges de `tests/__init__.py`.
  Secretos con prefijo (`seges-3b-totp-`, `seges-3b-st-`, `seges-3b-tok-` y `seges-3b-h-`) más 32 hexadecimales
  aleatorios. Lint: 0 incidencias nuevas.
- **Batería de los tres módulos** (log `tests-20261112-131534.log`): **456 tests, 14 F, 0 E y 4 saltados** (los de la
  línea base). Coincide por nombre con lo esperado. Las 14 F son 13 tests: `test_computed_secret_column_refused` cuenta
  2, uno por subtest (`password` y `new_password`).

  | Esperado | Resultado |
  |---|---|
  | `test_paap_i7_cusp_roles_out_of_reach_of_an_ai_admin` (por diseño) | F |
  | `test_decision2_v3_browse`, `test_v3_getitem`, `test_v3_mapped` | F («filtra»): **V3 confirmada** |
  | `test_decision2_v4_browse`, `test_v4_getitem`, `test_v4_mapped` | F («filtra»): **V4 confirmada** |
  | `test_v1_getitem`, `test_v1_mapped` | F («filtra»): **V1 confirmada** |
  | `test_v2_getitem`, `test_v2_mapped` | F («filtra»): **V2 confirmada** |
  | `test_computed_secret_column_refused` (2 subtests) | F («no se rechaza»): el camino del cálculo no pasa por el guardián |
  | `test_pending_write_survives_box_a_close` | F: **la escritura pendiente del llamador se pierde al cerrar la caja A** |
  | 4 controles, 4 positivos, `test_v1_literal_attr_refused`, `test_v3_recordset_as_result` | pasan |

- **Secretos en el log:** `grep -c "seges-3b-[a-z]*-\?[0-9a-f]\{32\}"` = **0**.
- **Limpieza:** ninguna línea de `tearDownClass` ni «limpieza incompleta».
- **Origen:** `addons paths` con `/mnt/compartidos/third_party`. Falta comprobar en el contenedor que no hay `pns_*` en
  las demás rutas (regla del 11/11/2026).
- Logs que no son F ni E: los conocidos (`odoo.http` de los negativos por RPC, `ir_attachment_create_uid_fkey` de
  `claims_own`, `snapshot read failed`).

## Propuesta: parche de `flush` antes de abrir la caja A (sin implementar; número de Sergio)

**Problema** (del fabricante, igual en 3.1.879 y 3.1.973; confirmado por `test_pending_write_survives_box_a_close`):
- al cerrar la caja A se hace `ro_cr.rollback()` (`tools_relaxaicode.py:275`, `skill_runtime.py:262`);
- en Odoo 14, `Cursor.rollback` llama a `clear_env(self)` (`sql_db.py:307`), que hace `env.clear()` del entorno de ese
  cursor (`sql_db.py:82-87`);
- `env.clear()` vacía la caché, `tocompute` y `towrite` (`api.py:620-627`), que son de todo el hilo (`api.py:760-765`);
- se pierden las escrituras pendientes del llamador (de cualquier modelo) y los cálculos guardados pendientes, sin
  error;
- `open_readonly_env` (`controller_helpers.py:179-238`) no hace `flush` antes de abrir, y los tres sitios que abren la
  caja A pasan por ella: `/mcp` (`controllers/main.py:1648-1650`), turno de Chatboo
  (`utils/engine_tool_run.py:28-30`) y skills (`utils/skill_runtime.py:250`).

**Cambio:** en `open_readonly_env`, antes de `base_env.registry.cursor()` (`controller_helpers.py:189`),
`base_env['base'].flush()`, con su marcador. Va antes de abrir el cursor: si el `flush` falla, no queda ningún cursor
abierto.

**Qué cubre:**
- `towrite`: lo pendiente se escribe en el cursor del llamador antes de abrir la caja A; al cerrar no queda nada que
  perder;
- `tocompute`: `flush()` sin campos hace `recompute()` (`models.py:5483-5486`), así que los cálculos guardados
  pendientes tampoco se pierden;
- condición a: la caja A ya no encuentra escrituras pendientes del llamador. Su `_read` → `flush(fields)`
  (`models.py:3101-3103`) no intenta escribir en el cursor `READ ONLY`. Sustituye al «flush previo» de solo columnas
  secretas, que no cubría la pérdida.

**Qué no cubre:**
- la caché del llamador sigue vaciándose al cerrar (`api.py:624`): solo cuesta volver a leer;
- **los registros `new()` del llamador pierden sus valores al cerrar**: viven solo en la caché. El
  `test_new_records_survive_box_a` previsto para la 3b no puede pasar sin cambiar el cierre. Queda como resto
  conocido del fabricante.

**Qué se degrada:**
- las escrituras pendientes, y sus errores (restricciones, SQL), se adelantan a la apertura de la caja A: un error que
  antes salía más tarde sale al llamar a la herramienta;
- un `flush` por apertura, normalmente vacío;
- si una caja A se abriera con un `base_env` que ya es de otra caja A (anidada) y tuviera pendientes, el `flush`
  fallaría en `READ ONLY`. No hay ningún caso hoy (P1).

**¿Llegan los llamadores reales con escrituras pendientes?** Por determinar con lecturas. El turno de Chatboo envuelve
cada herramienta en un `SAVEPOINT` crudo, sin `flush` (`engine_tool_run.py:324-358`, `_run_tool_in_savepoint`), sobre el
cursor del turno, que guarda sesión y trabajo. Cualquier escritura del motor aún sin `flush` antes de la herramienta se
perdería. En `/mcp` y en las skills hay que leer qué se escribe antes.

**Tests** (archivo propio del parche; `TestSegesBoxACallerWrites` pasa ahí):
- `test_pending_write_survives_box_a_close` (ya existe; hoy F);
- `test_pending_compute_survives_box_a_close`: el `name` de un contacto pendiente; tras la caja A, el `display_name`
  guardado en la BD es el nuevo (hoy se pierde la recomputación);
- `test_pending_write_box_a_reads_column` (condición a): con `comment` pendiente, la caja A lee `comment` del mismo
  contacto sin error, y tras cerrar la BD del llamador tiene el valor nuevo;
- `test_box_a_open_flush_error_no_cursor`: si el `flush` falla, no queda ningún cursor de caja A abierto.

**Neutralización:** N-flush (sin la línea): F en los tres primeros; el cuarto, F o E según el error.

**Hallazgo para el seguimiento del informe:** ficha nueva (número por comprobar con `grep` antes de darlo, como
PNS-103): «Cerrar la caja A descarta las escrituras pendientes del llamador», gravedad propuesta Media (pérdida
silenciosa de datos del turno). Pendiente de que Sergio apruebe la búsqueda y el alta.

## Propuesta de implementación de la 3b: parche 18 con O1, B y B2 (sin implementar)

Marcador: `# Seges: parche 18 (PNS-19, seguridad). Ver docs/pendiente/parches_pns_ai.md`. Citas de 3.1.973 con la 3a
aplicada.

**Comprobación común** (archivo propio, `pns_ai_mcp/models/seges_box_a_read.py`, importado con marcador en
`models/__init__.py`), en `base`:
- `_seges_box_a_check_read(name)`: si el cursor es el de la caja A y no hay `su`, rechaza con `_pns_deny_column` cuando
  `_pns_hidden_column(name)` es verdadero (criterio del fabricante, fila a fila en `ir.config_parameter`). Después,
  `check_access_rights('read')` del modelo.
- La marca se mira con `cr.__dict__.get(SANDBOX_CURSOR_FLAG)`, no con `getattr`. Fuera de la caja A, `getattr` pasaría
  por `Cursor.__getattr__` (`sql_db.py:315-317`) y por una excepción en cada `__getitem__` de todo Odoo. El valor es el
  mismo, porque la marca se pone en la instancia (`controller_helpers.py:194`).

**Enganches:**

| N.º | Dónde | Qué |
|---|---|---|
| 1 | `controllers/context_builder.py`, `_read_attr` (`:271-285`), antes de `getattr` (`:278`) | si `obj` es un recordset y `name` es un campo: `obj._seges_box_a_check_read(name)`. Cubre `rec.x`, `getattr`, `attrgetter`, `methodcaller` y los campos de `str.format` |
| 2 | `seges_box_a_read.py`, `__getitem__` de `base` con clave de texto (Odoo `models.py:5702-5716`) | la comprobación en el registro y después `super()`. Cubre `rec['x']`, `itemgetter` nativo, `sorted('x')` (`:5452`), `name_get` y lecturas del motor (`_score_record_fit`) |
| 3 | `seges_box_a_read.py`, `mapped` de `base` con ruta de texto (Odoo `:5285-5293`) | en la caja A, el bucle de Odoo tramo a tramo con la comprobación sobre los registros de cada tramo (fila a fila). Fuera, `super()`. Cubre `filtered('x')` (`:5328`) |
| 4 | `_read_attr`, objetos `Field` | rechaza `mapped`, `compute_value` y `determine_value` (decisión 4; el último, si existe en Odoo 14, a comprobar). `rec._fields` está permitido y `Field.mapped` lee la caché sin `__get__` (`fields.py:1085-1112`) |

**B** (`controllers/controller_helpers.py`, `open_readonly_env`, después de crear el `env` (`:211-217`) y antes de
anular el `commit` (`:220`)):
- `_seges_forget_secret_columns(env)`, en un archivo propio `utils/seges_box_a_cache.py`;
- los pares `(modelo, campo)` con `_pns_hidden_column` verdadero sobre el recordset vacío se guardan por registro, por
  nombre;
- `env.cache.invalidate([(campo, None), …])` (`api.py:896-916`);
- si falla, la caja A no se abre (`rollback`, `close` y `UserError`, como `:195-209`).

**B2** (`controllers/context_builder.py`, `:998-1003`): si el cursor es el de la caja A, cada helper de módulo se envuelve
en una función propia con `try/finally` que vacía lo mismo al terminar (sin `functools.wraps`, para no dejar
`__wrapped__`).

**Tests:**
- **Confirmación** (`test_seges_box_a_vias.py`, 22): con O1 deben pasar los 12 de vía (14 F de hoy).
  `test_pending_write_survives_box_a_close` sigue en F hasta el parche de `flush`.
- **Diseño, en `test_seges_box_a_vias.py`** (12 nuevos):
  - negativos: `itemgetter('totp_secret')`, `sorted('totp_secret')`, `filtered('totp_secret')`,
    `u._fields['totp_secret'].mapped(u)` y `'{0.totp_secret}'.format(u)`, tras el cálculo;
  - ACL del modelo: el motor lee en `sudo` un campo no secreto de `ai.mcp.user` antes de la caja A, y desde el sandbox
    `m['user_id']` se rechaza (el usuario no tiene ACL de `ai.mcp.user`);
  - positivos del motor en `sudo` dentro de la caja A real: `_api_key_for_inference` de un proveedor confirmado (prefijo
    `seges-3b-pk-`) y `get_param('web.base.url')`;
  - positivos fuera de la caja A: `_api_key_for_inference` y `_resolve_auth_token` siguen dando el valor;
  - `ir.config_parameter` fila a fila (como `base.user_admin`): `.value` y `mapped('value')` de `web.base.url`
    funcionan;
  - `sorted('name')`, `filtered('name')`, `itemgetter('name')` y `mapped('partner_id.name')` funcionan;
  - B al abrir: un secreto en caché del llamador no está en la caché tras `open_readonly_env`;
  - B selectivo: un valor no secreto en caché del llamador sigue en caché tras abrir (antes de cerrar).
- **`test_seges_sandbox_credentials.py`** (rama 3879: 32 → **33**):
  - reescrito al criterio del fabricante;
  - sin `test_marker_cleared_after_box_a`;
  - `test_sudo_does_not_lift` → `test_sandbox_cannot_reach_sudo` (condición b);
  - nuevos `test_box_a_icp_cache_before_run` (B, `value`) y `test_helper_sudo_read_forgotten` (B2, unidad del
    envoltorio);
  - sin `test_pending_writes_survive_box_a` (pasa al parche de `flush`), sin `test_new_records_survive_box_a` (no puede
    pasar: el cierre vacía la caché, resto conocido) y sin el de la decisión 2 (ya está en `test_seges_box_a_vias`).

**Neutralización por enganche** (una cada vez, batería completa, SHA-256 al restaurar):

| Prueba | Cambio | Deben fallar (F) |
|---|---|---|
| N18a | sin el enganche 1 | `test_decision2_v3_browse`, `test_decision2_v4_browse`, `test_computed_secret_column_refused` (2), el de `str.format` |
| N18g | sin el enganche 2 | `test_v1/v2/v3/v4_getitem`, `itemgetter`, `sorted` |
| N18m | sin el enganche 3 | `test_v1/v2/v3/v4_mapped`, `filtered` |
| N18f | sin el enganche 4 | `_fields[...].mapped` |
| N18acl | sin `check_access_rights` | ACL del modelo (`m['user_id']`) |
| N18b | sin B | B al abrir, `test_box_a_icp_cache_before_run` |
| N18i | B sin `value` de `ir.config_parameter` | `test_box_a_icp_cache_before_run` |
| N18w | B con la caché entera | B selectivo |
| N18h | sin B2 | `test_helper_sudo_read_forgotten` |

**Recuento:**

| Tras | Batería | Esperado |
|---|---|---|
| Hoy (confirmación) | 456 | 14 F (13 tests), 0 E, 4 saltados |
| 3b (O1, B, B2) | 456 + 12 + 33 = **501** | 2 F: `test_paap_i7` y `test_pending_write_survives_box_a_close` |
| 3b + parche de `flush` | 501 + 3 = **504** | 1 F: `test_paap_i7` |

**Restos conocidos (registro):**
- métodos que hoy no leen sin `su` ni devuelven el valor (O1b, como salida si aparecen);
- otros métodos de `Field` fuera de los tres nombres;
- `iap.account.get` (P2, aparte);
- V5 sin test (no hay `website` en la BD de tests);
- registros `new()` del llamador al cerrar la caja A.

P-22 sigue justo después de la 3b, con su script presentado antes.

## Ajustes del 12/11/2026 (decisiones de Sergio, tras la confirmación)

- **Comprobaciones:**
  - ningún `pns_*` fuera de `/mnt/compartidos/third_party` en el contenedor (0 en
    `/usr/lib/python3/dist-packages/odoo/addons`, `/var/lib/odoo/addons/14.0` y `/mnt/oca/*`);
  - PNS-104 estaba libre;
  - `determine_value` no existe en Odoo 14: solo hay `compute_value` (`fields.py:1180` y `:2045`). El enganche 4 queda
    con `mapped` y `compute_value`.
- **PNS-104** dado de alta en el [seguimiento](seguimiento_informe_pns_ai.md) (pérdida de escrituras pendientes del
  llamador al cerrar la caja A). Gravedad propuesta Alta, que decide Sergio. Sin número de parche todavía.
- **`test_new_records_survive_box_a`, fuera del plan de la 3b:** los `new()` del llamador quedan como resto conocido
  del fabricante (PNS-104). Sustituye a lo dicho en «Tests (condición d)», que se conserva como registro.
  `test_seges_sandbox_credentials` pasa de 32 a **33**: −1 (`test_marker_cleared_after_box_a`), +2
  (`test_box_a_icp_cache_before_run` y `test_helper_sudo_read_forgotten`). `test_pending_writes_survive_box_a` pasa al
  parche de `flush`, y el test de la decisión 2 ya está en `test_seges_box_a_vias.py`.
- **Recuento**, igual que en la tabla de la propuesta de implementación: 456 hoy · **501** tras la 3b (2 F:
  `test_paap_i7` y `test_pending_write_survives_box_a_close`) · **504** con el parche de `flush` (1 F: `test_paap_i7`).
- `test_seges_box_a_vias.py` y su bloque de `tests/__init__.py` quedan sin commit hasta los tests de la 3b.

## Parche de `flush`: ¿llegan los llamadores reales con escrituras pendientes? (12/11/2026, lecturas L1-L4 y S1-S7)

Completa el apartado del mismo nombre de la propuesta del parche, que se conserva. Solo lectura; sin valores.

**Turno de Chatboo** (`pns_ai_chatboo/models/chatboo_async_request.py`, `_process`, `:149` y siguientes):
- `:160-161`: `state`/`started_at` del trabajo y `commit` antes de nada: hasta ahí no queda nada pendiente.
- **Candidato descartado:** los eventos `query_code` y `query_data` del motor solo guardan variables locales
  (`:452-462`). La sesión se escribe después del motor, en `_finalize` → `_save_to_session` (`:516`, `:713`,
  `:1438-1506`), cuando ya no hay caja A abierta.
- **Candidato nuevo:** `chatboo.session.presentation_show_mode`, escrito **después** del `commit` y antes del motor si el
  mensaje empieza por `/show-table` o `/show-chart` (`:209-214`). El motor se crea en `:391-419` y corre en `:420`. Si
  la primera caja A del turno se abre antes de cualquier `flush` o `commit`, esa escritura se pierde. El turno no lo
  nota, porque el motor recibe el valor en el contexto (`:396-398`), pero no queda guardado para los turnos siguientes.
  **Por confirmar** (X1 a X3).
- **Lo que lo taparía en producción:** cada `_mcp_log` del motor (`utils/agent_engine.py:703-730`) llama a
  `ai.log._create_log_entry` (`models/ai_log.py`), que crea la fila en un **cursor propio** y hace `commit`. Si
  `Cursor.commit` vuelca los pendientes del hilo (`flush_env`, como `TestCursor.commit`, `sql_db.py`; por confirmar en
  X1), ese `commit` escribe y confirma las escrituras pendientes del llamador **en el cursor del registro, fuera de su
  transacción**. En los tests no pasa: `_create_log_entry` no hace nada si hay tests en marcha (`test_is_running`). Por
  eso el test ve la pérdida y producción quizá no.

**`/mcp`** (`pns_ai_mcp/controllers/main.py`):
- `mcp_endpoint` (`:760-900`) valida la clave con `search` en `sudo` (solo lectura) y guarda el usuario en `request`.
- `_mcp_tools_call` (`:1237-1397`) llama a la herramienta (`tool_function(self, arguments)`) sin escribir antes en el
  camino de lectura.
- `_log_mcp_operation` (`:111-182`) también usa `_create_log_entry` (cursor propio).
- **No se pierde nada** en lo leído: no hay escrituras pendientes antes de la caja A.

**Skills** (`pns_ai_mcp/utils/agent_engine.py:1300-1390`; `skill_runtime.py:171`, `:250`, `:514`):
- antes de `bootstrap_skill_code_body` solo hay `_mcp_log` (cursor propio) y lecturas (`build_invocation_payload`);
- en un turno de Chatboo, heredan lo pendiente del turno (el candidato de arriba).
- **Nada propio pendiente** en lo leído.

**Hallazgo secundario, por confirmar (X1):** si `Cursor.commit` vuelca los pendientes del hilo, cada `_create_log_entry`
confirma, en su propio cursor, las escrituras pendientes de quien llama:
- quedan aunque después la transacción del llamador se deshaga (por ejemplo, el `rollback` de `/mcp` al fallar una
  herramienta, en el `except` de `_mcp_tools_call`, `main.py:1237-1397`);
- las de registros creados en esa misma transacción, que el cursor del registro no ve, se pierden: `flush` →
  `_write` → `MissingError` → `exists()` vacío (`models.py:5471-5480`).

Se presentaría a Sergio como ampliación de PNS-104 o como ficha aparte.

## Resultado de X1 a X4 (12/11/2026, solo lectura)

Odoo del contenedor (`/usr/lib/python3/dist-packages/odoo`).

**Mecanismo, confirmado por lectura:**
- `Cursor.commit` llama a `flush_env(self)` antes del `COMMIT` (`sql_db.py:294-302`, en `:296`).
- `flush_env(cr)` busca un entorno de ese cursor con `uid` entero y le hace `['base'].flush()` y después `clear()`
  (`sql_db.py:65-80`).
- `flush()` sin campos hace `recompute()` y vacía **todo** `towrite` con ese entorno (`models.py:5462` y siguientes).
  `towrite`, `tocompute` y la caché son del hilo, no del cursor (`api.py:760-765`).
- Por tanto, **cualquier cursor propio con un `Environment` que haga `commit` en el mismo hilo escribe y confirma, en
  su transacción, las escrituras pendientes de quien lo llama**, y luego vacía la caché y lo pendiente del hilo.
- Un cursor propio sin `Environment` no lo hace: `_flush_progress` (`chatboo_async_request.py:546-561`) usa SQL a
  pelo y `flush_env` no encuentra entorno.
- `_create_log_entry` (`models/ai_log.py`) abre un cursor propio, crea `env_log = api.Environment(new_cr, SUPERUSER_ID,
  {})` y hace `new_cr.commit()`: es este caso. Sale de cada `_mcp_log` del motor (`agent_engine.py:703-730`; primer
  uso en `run_stream`, `:983`) y de cada `_log_mcp_operation` de `/mcp` (`controllers/main.py:111-182`). **No se ejecuta
  en los tests** (`test_is_running`, `utils/compat.py:42-54`): la batería no puede verlo.

**`presentation_show_mode` (Chatboo): descartado como pérdida por la caja A**, con una condición.
- Se escribe en el cursor del turno (`chatboo_async_request.py:209-214`), y ese cursor **se deshace siempre al terminar
  el turno** (`finally`, `:530-541`: «What must last … was already committed on its own cursors»). Lo que dura se
  escribe en cursores propios, en `_finalize` → `_save_to_session`. `presentation_show_mode` vuelve a escribirse allí
  cuando el turno trae el modo (`:1298`).
- En producción, el `_mcp_log` de `run_stream` (`agent_engine.py:983`) vuelca y confirma esa escritura en el cursor
  del registro antes de la primera herramienta. Si siempre se ejecuta antes de la primera caja A (no lo he leído:
  lectura X5), la caja A no encuentra nada pendiente.
- **Consecuencia para PNS-104:** en Chatboo, lo escrito en el cursor del turno no dura de todas formas. En `/mcp` y en
  las skills no hay escrituras pendientes antes de la caja A (lecturas S6 y S7). **Ningún llamador real pierde datos
  hoy por la caja A**; el defecto queda latente: cualquier llamador que llegue con escrituras pendientes, más la
  condición a.
- Sin test con el flujo real de eventos: no hay pérdida que medir. Si X5 mostrara que la primera caja A puede ir
  antes del primer `_mcp_log`, se propondría.

**Hallazgo aparte, confirmado por lectura (sin parche; Sergio decide si amplía PNS-104 o va en ficha aparte):
«Los cursores propios con `commit` confirman y descartan las escrituras pendientes de quien los llama».**
- **Qué se confirma fuera de la transacción del llamador:** todas las escrituras pendientes del hilo (`towrite`) y los
  cálculos guardados pendientes (`recompute`), en el momento del `commit` del cursor propio. Quedan confirmadas aunque
  después el llamador deshaga su transacción:
  - el `rollback` de `/mcp` al fallar una herramienta (`except` de `_mcp_tools_call`, `main.py:1237-1397`);
  - el `ROLLBACK TO SAVEPOINT` del motor por herramienta (`engine_tool_run.py:324-358`);
  - el `rollback` del cursor del turno de Chatboo (`:530-541`).

  En la caja B, un `_mcp_log` o un registro en cursor propio entre pasos confirmaría pasos que el plan después
  deshace. **Sin comprobar.**
- **Qué se pierde con registros nuevos:** las escrituras pendientes sobre registros creados en la transacción del
  llamador, que el cursor propio no ve. El `UPDATE` no encuentra la fila, `process` reintenta con `exists()`, que da
  vacío (`models.py:5471-5480`), y el `clear()` posterior vacía la caché del hilo: se pierden sin error. Si el
  `recompute` falla en el cursor propio, `_create_log_entry` se traga la excepción (`except Exception` → `return None`),
  y lo ya sacado de `towrite` también se pierde.
- **Desde qué caminos:**
  - todo `_mcp_log` del motor (Chatboo y skills) y `_log_mcp_operation` de `/mcp`;
  - y, con el mismo mecanismo, cualquier cursor propio del fabricante con `Environment` y `commit` en el hilo del
    llamador: `_mint_card_token` (`engine_tool_run.py:539-562`), `_run_on_committed_cursor` (`session_download.py`),
    `iap.account.get` (P2), `_finalize` de Chatboo, entre otros.

  Inventario completo pendiente (grep de `registry.cursor()` + `Environment` + `commit`, a presentar).
- **Test propuesto** (`pns_ai_mcp/tests/test_seges_side_cursor_commit.py`, `TransactionCase`, sin implementar):
  1. `test_log_commits_caller_pending_write`:
     - parchear `odoo.addons.pns_ai_mcp.models.ai_log.test_is_running` a `False` (`self.patch`);
     - escribir `comment` (marcador sin secreto) en un contacto **confirmado**, comprobar que está en `towrite`, y
       llamar a `env['ai.log'].sudo()._create_log_entry(user_id=…, operation_type='read', tool_name='seges_3b_probe')`;
     - con un cursor aparte, `SELECT comment` da el marcador (confirmado fuera de la transacción del test);
     - `self.env.cr.rollback()` no lo deshace: otro `SELECT` desde un cursor aparte sigue dando el marcador.
  2. `test_log_drops_pending_write_on_new_record`:
     - crear un contacto en la transacción del test y escribirle `comment` (pendiente);
     - llamar a `_create_log_entry`;
     - `flush()` y `SELECT comment` en el cursor del test: no está el marcador (se perdió).
  3. **Limpieza:** `addCleanup` con un cursor nuevo que restaura `comment` del contacto confirmado y borra la fila de
     `ai.log` con `endpoint = 'seges_3b_probe'`, con `commit` (`# pylint: disable=invalid-commit`). BD de tests
     desechable.
  4. Hoy los dos dan F si el hallazgo es cierto. Son la prueba de la ficha, no de un parche.

**Gravedad propuesta (la decide Sergio):**
- **PNS-104: Baja.** Pérdida silenciosa, pero latente. Ningún llamador real llega hoy a la caja A con escrituras que
  fueran a durar:
  - Chatboo deshace el cursor del turno, y el primer `_mcp_log` vuelca lo pendiente;
  - `/mcp` y las skills no tienen pendientes.

  Subiría si aparece un llamador con pendientes, o si se cuenta la condición a como fallo visible.
- **Hallazgo aparte: Alta, por confirmar con el test.** Rompe la atomicidad que el código del fabricante da por hecha:
  - los `rollback` de `/mcp`, del motor por herramienta y del turno no deshacen lo ya volcado por un registro;
  - pierde sin error escrituras sobre registros nuevos;
  - los tests no lo ven, porque el registro está apagado en ellos (`test_is_running`);
  - si se confirma en la caja B, afecta a la garantía de «confirmar antes de escribir».

## Cierre de los llamadores reales y decisiones de Sergio (12/11/2026, tras X5)

**X5** (`pns_ai_mcp/utils/agent_engine.py:960-1000`): el `_mcp_log` de `:983` **solo se ejecuta si una frase dispara
una skill** (`_triggered_skill_command`, `:980-995`). No va siempre antes de la primera herramienta. La condición del
bloque anterior no se cumple. El descarte de `presentation_show_mode` se mantiene por el otro motivo:
- el cursor del turno se deshace siempre al terminar (`chatboo_async_request.py:530-541`);
- lo que tiene que durar se escribe en cursores propios (`_save_to_session`; el modo, en `:1298`).

Que la caja A lo pierda antes no cambia el resultado final.

**Llamadores reales: cerrado.**

| Llamador | Abre la caja A en | ¿Escrituras pendientes antes? | ¿Se pierde algo que fuera a durar? |
|---|---|---|---|
| Turno de Chatboo | `utils/engine_tool_run.py:28-30` → `get_readonly_env` | Solo `chatboo.session.presentation_show_mode` con `/show-table` o `/show-chart` (`chatboo_async_request.py:209-214`) | No: el cursor del turno se deshace al terminar (`:530-541`) |
| `/mcp` | `controllers/main.py:1648-1650` → `get_readonly_env` | No (`:760-900`, `:1237-1397`) | No |
| Skills | `utils/skill_runtime.py:250` → `open_readonly_env` | No propias (`agent_engine.py:1300-1390`); en un turno de Chatboo, las del turno | No |

**Decisiones de Sergio:**
1. **PNS-104:** gravedad **Baja (propuesta)**, latente. Actualizadas la fila, la nota y la ficha del seguimiento y
   `docs/specs/estado_hallazgos_3879.md`.
2. **Parche de `flush`:** se mantiene en la 3b, **como defensa** (pérdida latente y condición a). Número de Sergio.
   Sin test del flujo real de Chatboo: no hay pérdida que medir.
3. **PNS-105** (PNS-105 libre, comprobado con Grep): «Los cursores propios con `commit` confirman y descartan las
   escrituras pendientes de quien los llama», **Alta (propuesta)**, sin estado y sin parche. Dado de alta en los mismos
   sitios que PNS-104. **Fuera de la 3b.**
4. Llamadores reales, cerrado (tabla de arriba).

**Pendiente de PNS-105 (después de la 3b y antes del staging):**
- **Test de confirmación:** `pns_ai_mcp/tests/test_seges_side_cursor_commit.py`, con los dos tests del bloque «Resultado
  de X1 a X4» (escritura confirmada fuera de la transacción y que sobrevive a su `rollback`; escritura perdida sobre un
  registro nuevo), y su limpieza.
- **Caso de la caja B:** un registro con cursor propio entre pasos de un plan que después se deshace. Comprobar si los
  pasos anteriores quedan confirmados.
- **Inventario completo** de cursores propios del fabricante con `Environment` y `commit` en el hilo del llamador
  (`registry.cursor()`, `pool.cursor()`), con archivo:línea. El `grep` se presenta antes de ejecutarlo.

**Test de confirmación de PNS-105 (12/11/2026):**
- **Archivo:** `pns_ai_mcp/tests/test_seges_side_cursor_commit.py` (`TestSegesSideCursorCommit`, 2 tests), importado en
  el bloque de Seges de `pns_ai_mcp/tests/__init__.py`. Sin commit, como `test_seges_box_a_vias` hasta la 3b.
- **Diseño final:**
  - `test_is_running` se parchea en `ai_log.py` con `lambda *args, **kwargs: False`. La firma real es
    `test_is_running(env)` (`utils/compat.py:42-54`). Se importa por nombre en `ai_log.py:9` y se llama como
    `test_is_running(self.env)` en `:716`.
  - Contacto confirmado: `base.main_partner`. Usuario del registro: `base.user_admin`. `_create_log_entry` usa
    `tool_name='seges_3b_probe'`, que se guarda en la columna `endpoint` (`ai_log.py:823`).
  - Los cursores aparte (comprobaciones y limpieza) usan solo SQL, sin `Environment`, para que su `commit` no vuelque lo
    pendiente del test. Los de comprobación cierran con `rollback`, sin `commit`.
  - Precondiciones con mensaje `PRECONDITION (not the PNS-105 result): …`:
    - `comment` está en `env.all.towrite` antes de la llamada;
    - `_create_log_entry` devuelve un registro;
    - la fila de la sonda (por `id` y `endpoint`) se ve desde un cursor aparte.
  - Limpieza (`addCleanup`, registrada antes de la llamada):
    - empieza con `self.env.cr.rollback()`, para soltar cualquier bloqueo de fila del test;
    - en un cursor nuevo, restaura `comment` (solo en el test 1) y borra las filas de `ai_log` con
      `endpoint = 'seges_3b_probe'`;
    - termina con `commit` (`# pylint: disable=invalid-commit`).
  - `self.env['base'].flush()` en `setUp`, para que `towrite` empiece vacío.
  - `write_date` y `write_uid` de `base.main_partner` no se restauran (BD de tests desechable).
- **Citas del contenedor** (`odoo` 14.0.20231106) corregidas en este paso, frente a la referencia:
  - `towrite`: `odoo/api.py:765` (`Environments` en `:757-765`);
  - `_write` → `MissingError`: `odoo/models.py:3777-3780`;
  - `flush` → `recs.exists()._write(vals)`: `models.py:5479-5482`;
  - `res.partner.write`: `odoo/addons/base/models/res_partner.py:543-587`.

  Leídas para el siguiente paso de PNS-105:
  - `Cursor.__enter__` / `__exit__`: `odoo/sql_db.py:136-153` (`__exit__` hace `commit()` si no hubo excepción, y
    después `close()`);
  - `savepoint(flush=True)`: `sql_db.py:115-134` (al entrar y al salir bien, `flush_env(clear=False)` y
    `precommit.run()`; con excepción, `clear_env`, `precommit.clear()` y `ROLLBACK TO SAVEPOINT`).
- **Resultado** (`odoo-dev 14 tests pns_base,pns_ai_mcp,pns_ai_chatboo`, log `tests-20261112-175130.log`):
  - **512 tests, 3 F, 0 E y 4 saltados**. Las F son `test_paap_i7_cusp_roles_out_of_reach_of_an_ai_admin`,
    `test_log_commits_caller_pending_write` y `test_log_drops_pending_write_on_new_record`.
  - `test_log_commits_caller_pending_write` (`base.main_partner`): pasan las dos observaciones.
    > `PNS-105: the pending write was committed outside the test transaction; the pending write survived the test
    > transaction's rollback`
  - `test_log_drops_pending_write_on_new_record`: se lee `None` en lugar del marcador.
    > `PNS-105: the pending write on a record created in the test transaction was lost (flushed on the side cursor,
    > which cannot see the row, then cleared)`
  - Precondiciones sin fallos (`_create_log_entry` creó las filas 28 y 29 de `ai.log`). Sin líneas ERROR ni WARNING de
    la limpieza.
  - Traceback: 58 (los 56 de `tests-20261112-165632.log` más los 2 de las F nuevas).
  - `grep -c`: 0 secretos (`seges-3b-[a-z0-9-]*[0-9a-f]{32}`) y 0 UUID4. `seges-pns105-`: 1 (el marcador, en el
    mensaje de la F del test 2).
- **PNS-105 confirmado por test. Faltan el inventario y la caja B; el parche y el estado se deciden después.**

## Inventario de cursores propios y caja B (12/11/2026, solo lectura)

Fuente: los cuatro `grep` presentados (G1 cursores, G2 entornos, G3 `commit`, G4 hilos; `--exclude-dir=tests`, sobre
`pns_base`, `pns_ai_mcp` y `pns_ai_chatboo`) y lectura de cada apertura. Nada ejecutado aparte de los `grep`. Citas del
core: contenedor (`odoo` 14.0.20231106), con la errata de citas aplicada: `Cursor.__enter__`/`__exit__`
`sql_db.py:136-153` (`__exit__` hace `commit()` si no hubo excepción y después `close()`); `commit` `:448-457` (`flush_env`
en `:451`); `rollback` `:459-468` (`clear_env` en `:462`); `savepoint(flush=True)` `:115-134`; `flush_env` `:65-80`;
`clear_env` `:82-87`.

Fuera del inventario, como se pidió: `hooks.py`, `controller_helpers.py:195/217` (caja A) y los `self.env.cr.commit()`
(solo se cuentan).

**Cursores propios con `Environment`** (24). En todos, el `commit` (explícito o implícito por `with`) vuelca y confirma
lo pendiente del hilo (`towrite`, `tocompute`) y después lo vacía. Ninguna apertura lleva marcador de Seges: **todas son
del fabricante**. «(sin grep)»: llamador deducido del nombre, del docstring o de este documento, sin `grep` de llamadores.

| # | Apertura | `Environment` | `commit` | Hilo | Quién lo alcanza | ¿Pendientes del llamador? |
|---|---|---|---|---|---|---|
| 1 | `pns_ai_mcp/models/ai_log.py:720` `_create_log_entry` | `:722` | explícito `:847` (sin `with`; `close` `:852`) | mismo | `_mcp_log` del motor (Chatboo, skills); `_log_mcp_operation` de `/mcp`; `_log_safe_plan_execution` de la caja B (`safe_operation.py:1703`) | **sí** (PNS-105, confirmado por test). En la caja B, después del `commit` del plan (`:1501`). No corre en tests (`:716`) |
| 2 | `models/ai_skill_param_cache.py:146` `_remember_for_skill` | `:147` | `:151` | mismo | skills, relleno híbrido de parámetros (sin grep) | sí, en turno. No se abre con `TestCursor` (`:88-92`) |
| 3 | `models/ai_change_journal.py:392` `_record_failed_plan` | `:393` | `:440` + `with` | mismo | caja B: `except` de `execute_plan_now` (`safe_operation.py:1534`) | no: después del `rollback` (`:1509`, `clear_env`) |
| 4 | `models/key_pin_desk.py:203` `_collect` | `:204` | `with` | mismo | flujo del PIN (`_collect_pin`, `:190`; sin grep) | según llamador |
| 5 | `models/key_pin_desk.py:227` `_take` | `:228` | `with` (también en los `return`) | mismo | ídem; en bucle cada 0,4 s (`:211-216`) | ídem |
| 6 | `models/api_result_cache.py:132` `_store` | `:133` (vía `sudo()` del recordset) | `with` | mismo | **caja B**, `api_call` (`controllers/safe_plan_http.py:518`); otros, sin grep | **sí: pasos anteriores del plan**. Sin guarda de tests |
| 7 | `utils/engine_tool_run.py:547` `_mint_card_token` | `:549` | `:556` + `with` | mismo | turno, tras `safe_plan_request` (`_tool_loop_after_plan_request`, `:564`) | sí: lo que la herramienta dejó en el cursor del turno |
| 8 | `utils/field_required_plan.py:248` `create_field_required_choice` | `:249` | `:258` + `with` | mismo | `request_safe_plan` (`controllers/safe_plan.py:243`), desde `/mcp`, turno y atajo de skills | posible |
| 9 | `utils/session_download.py:382` `_run_on_committed_cursor` | `:383` | `:385` + `with` (si falla, `:392` repite en el `env` del llamador) | mismo | `persist_turn_file_detail` (`:460`) ← **caja B**, `fetch_url`/`api_call` binarios (`safe_plan_http.py:95-100`, `:145-150`); otros, sin grep | **sí en la caja B** |
| 10 | `controllers/safe_plan.py:310` `request_safe_plan` | `:311` | `:341` + `with` | mismo | `safe_plan_request` (`/mcp`, turno), atajo de skills | sí: lo del turno |
| 11 | `controllers/safe_plan.py:409` autoconfirmación | `:412` | `:422`, `:428`, `:432` + `with` | mismo | `safe_plan_request` con pasos autoconfirmables. Es **cursor del plan** | en la rama de `_replace_pending_plan`, el `op.write` (`:198`) queda pendiente y lo confirma `:422`. En la otra, `:341` ya lo vació |
| 12 | `models/safe_operation.py:698` `_resolve_confirm` | `:702` | `:760`, `:779`, `:781` + `with` | mismo | botón «Confirmar» del aviso; `_resolve_confirm_and_execute` | no en lo leído (antes solo lee, `:689-696`) |
| 13 | `models/safe_operation.py:968` `_execute_plan_with_timeouts` | `:971` | `:983` + `with` (dentro, `:1457` y `:1501`) | mismo | `_resolve_execute` ← ejecución del aviso o `_resolve_confirm_and_execute`. **Cursor del plan** | no en lo leído (`:830-833` solo lee e invalida; `:945` hace `commit` antes) |
| 14 | `models/safe_operation.py:1087` `_retry_confirmed_not_executed` | `:1090` | `:1095` + `with` | mismo | cron, vía `_cleanup_stuck_state` (`:1057`). **Cursor del plan** | no: antes solo hay `search` |
| 15 | `models/safe_operation.py:1592` `_heal_module_update_after_registry_reset` (`Registry`, `:1570`) | `:1593` | `:1647` + `with` | mismo | `except` de `execute_plan_now` (`:1514`) | no: después de `:1509` |
| 16 | `pns_base/models/progress_job.py:147` `runner` | `:148` | `with` | **hilo propio** (`:170-172`), con `env_manage()` (`:145`): pendientes propios del hilo | `_launch` (sin grep) | no: el llamador ya hizo `commit` (`:110`) |
| 17 | `pns_base/models/progress_job.py:153` | `:154` | `:157` + `with` | hilo propio | ídem. Es el cursor del trabajo | — |
| 18 | `pns_base/models/progress_job.py:162` | `:163` | `with` | hilo propio | ídem | posible (H2) |
| 19 | `pns_ai_chatboo/models/chatboo_job.py:205` `_runner` | `:206` | `with` | **hilo propio** (`:223-226`), con `_env_manage` (`:203`) | turno de Chatboo y trabajo de Canvas (`_spawn`, desde `controllers/chatboo.py:918` y `chatboo_canvas_job.py:69`) | — (la petición hizo `commit` antes: `:917`, `:68`) |
| 20 | `chatboo_job.py:247` `_record_crash` | `:248` | `with` (`return` dentro) | hilo del worker, `manage` nuevo (`:246`) | `except` del `runner` (`:221`) | no: pendientes del hilo nuevos |
| 21 | `models/chatboo_async_request.py:703` `_finalize` | `:705` | `:741` + `with`; `savepoint` `:712` | hilo del worker (el `manage` anidado comparte los pendientes) | `_process` (`:514`, `:530`) | no fuera de tests: antes va `_release_turn_cursor` (`:590`, `rollback`). **En tests sí**: `:587-588` no hace nada |
| 22 | `models/chatboo_canvas_job.py:144` `_close` | `:145` | `with` | hilo del worker | `_process` (`:103`, `:135`) | en `:135`, lo que dejó `open_page` (el cursor del trabajo lo confirmaría igual al salir) |
| 23 | `models/chatboo_session.py:1008` `_store_design` | `:1010` | `:1023` | mismo | helpers de página **dentro de la caja A** (docstring `:997-1000`), en turno o en Canvas | con el parche 37, lo del turno ya se volcó antes; queda H3 |
| 24 | `models/chatboo_session.py:1045` `_store_title` | `:1047` | `:1052` | mismo | ídem | ídem |

**Sin `Environment` (solo SQL):** `flush_env` no encuentra ningún entorno de ese cursor y no vuelca nada.

| Apertura | Qué hace |
|---|---|
| `pns_ai_mcp/models/ai_context.py:541` | `UPDATE` de uso, `commit` `:553` |
| `models/ai_agent.py:1400` | `UPDATE` de caché, `:1410` |
| `models/ai_provider.py:1300` | `UPDATE usage_support`, `:1309` |
| `models/safe_operation.py:1255` `_claim_execute` | `UPDATE` de la reserva; `:1292` o `rollback` `:1284` |
| `models/safe_operation.py:1310` `_release_execute_claim` | `:1332` |
| `pns_base/models/progress_job.py:47` `ProgressReporter.step` | `UPDATE`, dentro del hilo |
| `pns_ai_chatboo/models/chatboo_job.py` `:87`, `:254`, `:289` (hilo del latido), `:342` | `SELECT`/`UPDATE` |
| `models/chatboo_async_request.py` `:553`, `:569`, `:753`, `:1542` | `UPDATE` |
| `controllers/chatboo.py` `:947`, `:990` | `SELECT`/`UPDATE` desde el generador SSE |

No son aperturas: `pns_base/utils/thread_env.py:26` y `chatboo_job.py:58-66` (obtienen el `Registry`);
`validators_base.py:267` y `validators_repair.py:294`/`:380` (comentarios); `MCPClientRegistry` (3 sitios). Los
`with_env` de G2 (`utils/skill_runtime.py:163`, `chatboo_canvas_page.py:89`, `chatboo_canvas_job.py:66`) usan el mismo
cursor.

**`self.env.cr.commit()`** (confirman la transacción de quien llama): **12**. `progress_job.py:110`;
`safe_operation.py:945`, `:954`, `:1352`, `:1457`, `:1501`; `chatboo_canvas_job.py:68`; `controllers/chatboo.py:917`
(`request.env.cr.commit()`); `chatboo_async_request.py:161`, `:329`, `:1639`; `wizard/openapi_spec_generate_wizard.py:242`.

**Caja B, 3.1: dónde y con qué frontera.**
- Son la caja B (docstring de `controllers/safe_plan.py:1-23`): `safe_plan.py` (propuesta y autoconfirmación),
  `safe_operation.py` (confirmación, reserva y ejecución), `controllers/safe_plan_execute.py` (`execute_safe_plan`) y
  `ai_change_journal.py` (diario).
- **Pasos:** bucle de `safe_plan_execute.py:94-241`. Después de cada paso que escribe, el diario añade su fila en la
  **misma transacción** (`record_executed_step` → `self.create`, `ai_change_journal.py:242-372`).
- **Frontera del paso:** ninguna. Ni `SAVEPOINT` a pelo ni `cr.savepoint()`. El `SAVEPOINT` de
  `engine_tool_run.py:324-358` es del turno, no del plan.
- **Frontera del plan:** la transacción del cursor de quien llama a `execute_plan_now` (`:968`, `safe_plan.py:409`,
  `:1087`; `safe_plan_status`, sin leer): `commit` `safe_operation.py:1457` → `execute_safe_plan` (`:1483`) → `flush`
  (`:1491`) → `UPDATE executed` (`:1493`) → `commit` `:1501`.
- **Cuándo se deshace:** ante cualquier excepción de un paso, de ese `flush` o del `UPDATE`: `rollback` (`:1509`),
  `_release_execute_claim(error)` (cancela la autorización) y `_record_failed_plan` (`:1534`). Un `fetch_url` o un
  `api_call` que falla devuelve un diccionario de error y no deshace el plan (`safe_plan_http.py:316`, `:439-513`). El
  docstring (`:1363-1388`) promete atomicidad y da por hecho que «los llamadores llegan sin trabajo pendiente».

**Caja B, 3.2: qué corre entre pasos con cursor propio y qué puede quedar pendiente.**
- **`api_call`:** tras la respuesta del driver, si no venía de la caché, `Cache._store` (`safe_plan_http.py:516-523` →
  `api_result_cache.py:132-138`): cursor propio con `Environment` y `commit` implícito al salir del `with`
  (`sql_db.py:148-153` → `:451`).
- **Respuesta binaria** de `fetch_url` (`:355`) o de `api_call` (`:472-497`): `_run_on_committed_cursor`
  (`session_download.py:382-386`).
- `ai.fetch.cache._store` (`:344`, `:400`) escribe en el cursor del plan (no aparece en G1).
- Ni `_mcp_log` ni `_log_mcp_operation` corren dentro del plan. `_create_log_entry` solo después del `commit` (`:1544`).
  `_record_failed_plan` y `_heal…` van después del `rollback`: no encuentran nada pendiente.
- **Lo que queda sin volcar del paso anterior:**
  - la escritura directa de `create`/`write`/`copy`/`unlink`, normalmente no: `snapshot_records` hace `recs.read(...)`
    (`ai_change_journal.py:221`) y `_read` → `flush` (`models.py:3096`) saca todo lo pendiente de ese modelo, que queda
    en el cursor del plan sin confirmar. Si esa lectura falla (`:222-224`), no se vuelca;
  - sí pueden quedar cálculos guardados que esa lectura no pide: de la misma fila o de otras; el `verification_id`
    (`related` guardado, `:77-80`) de la fila del diario recién creada; y lo que escriben los pasos `action` y
    `field_required`, para los que el diario no lee registros (`:284-295`).
- **Qué pasa en el `commit` de `_store`, según la fila pendiente:**

  | Fila pendiente | Efecto |
  |---|---|
  | (a) ya existía y el plan no la ha bloqueado | se confirma fuera del plan y sobrevive al `rollback` de `:1509` |
  | (b) creada en el plan | la otra conexión no la ve: `MissingError` → `exists()` vacío (`models.py:3777-3780`, `:5479-5482`); **se pierde**, también si el plan termina bien (p. ej., el diario sin `verification_id`) |
  | (c) ya actualizada por el plan | el `UPDATE` del cursor propio espera al cursor del plan, en el mismo hilo; `_store` no pone `lock_timeout`: **el worker se cuelga** |

- Por lectura, (c) es lo más probable en un `write` normal (por ejemplo, `commercial_company_name` o `email_normalized`
  de la misma fila). **Sin comprobar:** depende de tres puntos del core que no están citados del contenedor:
  `BaseModel.recompute(fnames, records)` (si recalcula todos los pendientes de esos campos), `Field.write` (si descarta
  los valores iguales a los de la caché) y los cálculos guardados de `res.partner`.

**Diseño del test de la caja B (propuesta, sin aprobar; pendiente de citar el core).**
- **Archivo:** `pns_ai_mcp/tests/test_seges_side_cursor_commit.py`, clase nueva `TestSegesSideCursorBoxB`
  (`TransactionCase`), en el bloque de Seges existente. Un test: `test_box_b_store_between_steps`.
- **Datos confirmados en `setUpClass`** (cursor propio, prefijo `seges-pns105-b-`): un contacto empresa P con un contacto
  hijo Q; un `ai.api.server` activo; un `ai.safe.operation` con `status='confirmed'`, `executed=False`, usuario
  `base.user_admin` y `plan_steps`: (1) `write` de `{'name': marcador}` sobre P; (2) `api_call` a ese servidor.
- **Parches:**
  - `lib.api.drivers.get_api_driver` → stub cuyo `call` hace de **espía**: guarda solo modelo, campo e ids de
    `env.all.towrite` y de lo pendiente de calcular, y devuelve un JSON fijo;
  - `controllers.safe_plan_http._api_call_schema_error` → `None`;
  - `utils.api_call_result.format_api_call_body_for_llm` → lanza una excepción, para que el paso 2 falle **después** de
    `_store`;
  - **guarda contra el cuelgue:** se envuelve `registry.cursor` para que, mientras dura el paso 2 (lo activa el espía),
    cada cursor nuevo empiece con `SET LOCAL lock_timeout = '3s'`. Solo cambia tiempos.
- **Precondiciones** (`PRECONDITION (not the PNS-105 result): …`): `towrite` vacío al empezar (`flush` en `setUp`); el
  admin tiene los grupos de plan y de `api_call`; el espía se ejecutó y vio al menos una entrada pendiente;
  `_execute_plan_with_timeouts` devuelve `status == 'error'`.
- **Comprobaciones** (cursor aparte, solo SQL, `rollback` al final; solo booleanos, sin valores):
  - control: `P.name` sigue siendo el original;
  - variante «bloqueo»: `assertLogs` del logger de `api_result_cache` con «store failed» y excepción
    `LockNotAvailable`/`55P03`;
  - variante «confirmado fuera del plan»: el marcador aparece en `P.commercial_company_name`, `Q.display_name` o
    `Q.commercial_company_name`.
- **Limpieza** (`addCleanup`, registrado antes): `self.env.cr.rollback()`; en un cursor nuevo, borrar las filas de
  `ai_change_journal` de esa operación (incluidas las `failed`), la operación, `ai_api_result_cache` por `server_code`,
  el servidor, Q y P; `commit` (`# pylint: disable=invalid-commit`).
- **Resultado esperado hoy:** F, con más probabilidad por bloqueo (en producción, cuelgue sin límite). Si el espía no ve
  nada pendiente, la lectura de 3.2 está mal y se informa.
- **Antes de escribirlo:** citar del contenedor `BaseModel.recompute`, `Field.write`/`Cache.get_records_different_from`,
  los `_compute_*` guardados de `res.partner` y `Cursor.close` (este último, para H2).

**Vistas de paso, sin seguimiento:**
- **H2:** si `_my_work` falla, puede que `close()` no vacíe los pendientes del hilo, y el `commit` de
  `progress_job.py:162` confirmaría trabajo a medias.
- **H3:** si el sandbox pudiera hacer un `write` diferido en la caja A, el `commit` de `_store_design`
  (`chatboo_session.py:1023`) lo escribiría en un cursor de escritura.

**Riesgo para el diseño del parche de PNS-105:**
- **H4:** en Chatboo, el `op.write` de `_replace_pending_plan` (`safe_plan.py:198`) solo dura gracias a un `commit`
  lateral posterior (`:422` o el de `_mint_card_token`), porque el cursor del turno se deshace al terminar
  (`chatboo_async_request.py:530-541`). Un parche que impida a los cursores propios volcar lo pendiente del llamador
  haría que esa sustitución se perdiera.

## Citas del core para la caja B (12/11/2026)

Fuente: `docker run --rm -i --network none --read-only --tmpfs /tmp` sobre la imagen `odoo-dev:14` (Python 3.7.3,
`odoo` 14.0-20231106), con `inspect` para las funciones y `ast` para los campos. Sin red, sin volúmenes y sin BD. Salida
en el scratchpad de la sesión (`core14_pns105_cajab.txt`). El primer intento, solo con `--read-only`, falló al importar
`odoo`: `config.py:187` necesita un directorio temporal. Se repitió con `--tmpfs /tmp`, aprobado por Sergio.

**Funciones del ORM y del cursor:**

| Función | Dónde | Qué hace |
|---|---|---|
| `BaseModel.recompute` | `odoo/models.py:5914-5958` | Sin `fnames`, recalcula todos los campos pendientes del hilo (`:5942-5945`). Con `fnames` y `records`, sale si ninguno de esos registros está pendiente (`:5949-5954`); si alguno lo está, procesa **todos** los registros pendientes de esos campos, no solo `records` (`process`, `:5921`, y `:5956-5958`). Ante un `MissingError`, recalcula solo los que existen y da por calculados los demás (`:5930-5937`) |
| `Field.recompute` | `odoo/fields.py:1157-1178` | Recorre los pendientes del campo (`env.all.tocompute`, `:1161`) y llama a `compute_value` por lotes (`:1171-1178`) |
| `Field.__set__` | `odoo/fields.py:1114-1150` | En un registro que se está calculando (protegido), solo llama a `Field.write`, sin lógica de negocio (`:1127-1130`). En el resto, un `write()` completo (`:1146-1150`) |
| `Field.write` | `odoo/fields.py:939-966` | Quita el campo de los pendientes de cálculo (`:947`) y **descarta los registros cuyo valor en caché ya es el nuevo** (`:952-954`). Para los demás, actualiza la caché (`:955`) y, si el campo es guardado, lo deja en `towrite` (`:958-964`) |
| `Cache.get_records_different_from` | `odoo/api.py:853-867` | Devuelve los registros sin ese valor en caché. Un registro **sin valor en caché cuenta como distinto** (`KeyError`, `:862-863`) |
| `Cursor.close` | `odoo/sql_db.py:364-366` (`inspect` lo atribuye a `<decorator-gen-6>` por `@check`; la numeración encaja con `_close` en `:368`) | `return self._close(False)` |
| `Cursor._close` | `odoo/sql_db.py:368-402` | Cierra el cursor de psycopg2 (`:382`) y después llama a `self.rollback()` (`:392`) → `clear_env` (`:462`) → `env.clear()` del primer entorno de ese cursor |

**Consecuencias:**
- **Un cursor propio con `Environment` vacía lo pendiente del hilo también cuando falla.** Si el bloque `with` lanza una
  excepción, `__exit__` solo hace `close()` (`sql_db.py:148-153`) → `rollback` (`:392`) → `clear_env` → `env.clear()`:
  las escrituras pendientes del llamador se descartan sin confirmarse. Ya no hace falta que haya `commit` para perderlas.
- **H2** (`progress_job.py:162`, apuntada en el bloque anterior): **descartada**. Si `_my_work` falla, el `with` de
  `:153` cierra el cursor y `clear_env` vacía lo pendiente antes de llegar a `:162`. Se pierde; no se confirma.

**Cálculos guardados de `res.partner`** en la BD de tests (base, sus mixins y los 18 módulos):
- Modelos de la cadena: `res.partner`, `format.address.mixin`, `image.mixin`, `mail.activity.mixin`, `mail.thread`,
  `mail.thread.blacklist`, `mail.thread.phone` y `phone.validation.mixin`.
- Campos guardados calculados o `related`:
  - `base/models/res_partner.py`:
    - `display_name` (`:156`, `_compute_display_name`, `:241`, depende de `is_company`, `name`, `parent_id.display_name`,
      `type`, `company_name` y `commercial_company_name`);
    - `partner_share` (`:220`, `:259`, depende de `user_ids.share` y `user_ids.active`);
    - `commercial_partner_id` (`:227`, `:293`, depende de `is_company` y `parent_id.commercial_partner_id`);
    - `commercial_company_name` (`:229`, `:301`, depende de `company_name`, `parent_id.is_company` y
      `commercial_partner_id.name`);
  - `base/models/image_mixin.py:16-19`: `image_1024`, `image_512`, `image_256` e `image_128`, `related` de `image_1920`;
  - `mail/models/mail_thread_blacklist.py:33`: `email_normalized` (`_compute_email_normalized`, `:46`; sus `depends` no
    son literales);
  - `phone_validation/models/mail_thread_phone.py:30`: `phone_sanitized` (`:46`; `depends` tampoco literales).
- Ningún `pns_*` hereda `res.partner` (comprobado con Read):
  - los `models/__init__.py` de los tres módulos no importan ningún `res_partner`;
  - `pns_ai_chatboo/models/res_users.py:31` hereda `res.users` y solo añade un `Float` y un `Boolean` sin cálculo;
  - las extensiones de `base` (`sandbox_secret_read.py:56`, `seges_box_a_read.py:43`, `secret_native_export.py:29`) no
    declaran campos.

**Qué deja pendiente un `write` de `name` sobre un contacto P:**
- `display_name` de P y de todos los contactos cuyo `display_name` dependa de él (hijos, por `parent_id.display_name`).
  **No quedan pendientes al llegar al paso 2.** `snapshot_records` lee `['name', 'display_name']`, y `recompute` con
  `fnames` procesa **todos** los registros pendientes de `display_name` (`:5921`, `:5956-5958`).
- `commercial_company_name` de P (cuando `commercial_partner_id` es P: empresa o contacto sin padre, `:293`) y de los
  contactos cuyo `commercial_partner_id` es P (`:301`). **Pueden quedar pendientes:** el diario no los lee, y solo se
  calculan antes si el cálculo de `display_name` los lee (`name_get`, sin citar).
- **No dependen de `name`:** `partner_share`, `commercial_partner_id`, `email_normalized`, `phone_sanitized`, `image_*`.
- **Fuera de la cadena,** sin revisar: campos guardados de otros modelos que dependan de `res.partner.name`; por ejemplo,
  `res.company.name`, si P fuera el contacto de una compañía.

**Estado de las variantes de 3.2** (en el `commit` de `_store`, entre el paso 1 y el paso 2):

| Variante | Estado | Por qué |
|---|---|---|
| (a) se confirma fuera del plan una fila ya existente que el plan no ha bloqueado | **Descartada para `res.partner`; abierta para otros modelos y para los pasos `action`/`field_required`** | Lo pendiente que deja un `write` de `res.partner` cae en filas que el propio paso ya ha volcado y bloqueado (P y los contactos cuyo `display_name` se recalculó). Queda una cita pendiente: que el `flush(fnames)` de `_read` (`models.py:3096`) vuelque todo `res.partner`. La rama `fnames` de `flush` no está en esta salida |
| (b) se pierde lo pendiente de una fila creada en el plan | **Abierta** | Si la fila del diario tiene `verification_id` pendiente, se pierde: `MissingError` → `exists()` vacío (`:5930-5937`, `:5479-5482`). Que lo tenga pendiente depende de `create`, sin citar |
| (c) el cursor propio espera una fila que el plan ya ha actualizado | **Abierta, la más probable** | Todo lo que viene después del pendiente está citado: `recompute()` lo calcula (`:5942-5945`) → `Field.write` lo deja en `towrite` si el valor cambia o no estaba en caché (`:952-964`, `api.py:862-863`) → el `UPDATE` del cursor de `_store` espera al cursor del plan, que está en el mismo hilo. Falta que haya un pendiente así; lo comprueba el test |

**Diseño revisado del test de la caja B (propuesta, sin aprobar).** Sustituye al diseño del bloque anterior.
- **Archivo y clase:** `pns_ai_mcp/tests/test_seges_side_cursor_commit.py`, clase nueva `TestSegesSideCursorBoxB`
  (`TransactionCase`), en el bloque de Seges. Un test: `test_box_b_side_cursor_waits_for_plan_row`.
- **Variante elegida: (c), con un `write` de `email` en lugar de `name`.** Su pendiente (`email_normalized`, misma fila)
  no depende de `name_get` ni de si P es empresa, y no lo lee nada del paso 1. `name` dejaría el resultado entre (a) y (c)
  según `name_get`.
- **Datos confirmados en `setUpClass`** (cursor propio; prefijo `seges-pns105-b-`):
  - un contacto P sin padre ni hijos, con un correo inicial;
  - un `ai.api.server` activo;
  - un `ai.safe.operation` con `status='confirmed'`, `executed=False`, usuario `base.user_admin` y `plan_steps`:
    1. `write` de `{'email': 'seges-pns105-b-<hex>@example.com'}` sobre P;
    2. `api_call` a ese servidor.
- **Parches:**
  - `lib.api.drivers.get_api_driver` → stub cuyo `call` hace de **espía**: con `srv.env.all`, anota solo nombres e ids
    (`towrite` y `tocompute`, `api.py:760-765`) y devuelve un JSON fijo;
  - `controllers.safe_plan_http._api_call_schema_error` → `None`;
  - `utils.api_call_result.format_api_call_body_for_llm` → lanza `RuntimeError`. Así el paso 2 falla **después** de
    `_store`;
  - guarda: mientras el espía la tiene activada, `registry.cursor` devuelve cada cursor nuevo con
    `SET LOCAL lock_timeout = '3s'`. Solo cambia tiempos, y convierte el cuelgue en un error medible.
- **Precondiciones** (`PRECONDITION (not the PNS-105 result): …`):
  - `towrite` vacío al empezar (`self.env['base'].flush()` en `setUp`);
  - el admin tiene los grupos de plan y de `api_call`;
  - en el espía: P ya no tiene `email` en `towrite['res.partner']`, porque el paso 1 lo volcó en el cursor del plan;
  - en el espía: P está en `tocompute` de `email_normalized`;
  - `_execute_plan_with_timeouts` devuelve `status == 'error'`.
- **Única comprobación del resultado:** `assertLogs` del logger `odoo.addons.pns_ai_mcp.models.api_result_cache`. El test
  pasa si no hay ningún «store failed» cuya excepción sea `LockNotAvailable` (`pgcode` `55P03`). Se mira solo el nombre de
  la clase o el `pgcode`; no se imprime nada más.
- **Control, no es el resultado** (cursor aparte, solo SQL, `rollback` al final; booleanos): `email` y `email_normalized`
  de P siguen con sus valores iniciales después del `rollback` del plan.
- **Limpieza** (`addCleanup`, registrada antes):
  - `self.env.cr.rollback()`;
  - en un cursor nuevo, borrar las filas de `ai_change_journal` de esa operación (incluidas las `failed`), la operación,
    `ai_api_result_cache` por `server_code`, el servidor y P;
  - `commit` (`# pylint: disable=invalid-commit`).
- **Resultado esperado hoy (uno solo):** **F**, con el mensaje «PNS-105 (box B): step 2's own cursor waited for a row
  the plan cursor had already updated (lock timeout in the test; `_store` sets none, so in production the worker
  hangs)».
- Si falla una precondición, no es el resultado. Se informa sin cambiar el test. Por ejemplo, que `email_normalized` ya
  no esté pendiente querría decir que algo del paso 1 lo calcula.
- **Citas que aún faltan** (no cambian el resultado esperado si las precondiciones se cumplen): la rama `fnames` de
  `flush`, el marcado de cálculos en `create` y los `depends` de `email_normalized` (`mail_thread_blacklist.py:44-46`).

## Test de la caja B (12/11/2026)

Test de confirmación de PNS-105 en la caja B, sin parche y sin tocar código del fabricante:
`pns_ai_mcp/tests/test_seges_side_cursor_commit.py`, clase `TestSegesSideCursorBoxB` (`:193`), test
`test_box_b_side_cursor_waits_for_plan_row` (`:361`). **Resultado: F, la esperada.** La espera de la variante (c)
queda **confirmada en ejecución**.

**Citas del core** (contenedor `odoo-dev:14`: Python 3.7.3, `odoo` 14.0-20231106; `docker run --rm -i --network none
--read-only --tmpfs /tmp`, la misma forma del bloque anterior; salida `core14_pns105_c3.txt` en el scratchpad de la
sesión). Completan las «Citas que aún faltan» del diseño revisado:
- **C1, `BaseModel.flush` con `fnames`** (`odoo/models.py:5461-5531`):
  - primero recalcula solo esos campos (`:5492`);
  - con `records`, sale si ninguno tiene esos campos en `towrite` (`:5495-5502`);
  - si algún registro del modelo tiene en `towrite` alguno de los `fnames`, hace `towrite.pop(model_name)` y vuelca
    **todo** el `towrite` del modelo: todos los campos y todos los registros (`:5518-5525`);
  - no calcula lo pendiente de otros campos.
  - Con eso queda resuelta la cita pendiente de la variante (a): el `flush(fnames)` de `_read` vuelca todo
    `res.partner` cuando alguno de los campos leídos está pendiente.
- **C2, cálculos guardados en `create`:**
  - los marca `_create`, con `records.modified(self._fields, create=True)` (`:4044`, y `:4057` para los campos que no
    son columna), dentro de `env.protecting` (`:4042`);
  - `modified` los pasa a `add_to_compute` (`:5843-5846`), menos los protegidos (`:5840`; los calculados no
    `readonly` que vienen en `vals`, `:3867-3869`);
  - ni `create` (`:3791-3933`) ni `_create` (`:3935-4079`) llaman a `flush` ni a `recompute`, así que **quedan
    pendientes** mientras nada los lea. Salvedad, sin citar: una restricción de `_validate_fields` (`:4065`) que los lea.
  - El `verification_id` del diario es `related` guardado (`pns_ai_mcp/models/ai_change_journal.py:77-80`), así que una
    fila creada en el plan lo deja pendiente. La variante (b) no la comprueba este test.
- **C3, `email_normalized`:**
  - `_primary_email = 'email'` (`addons/mail/models/mail_thread_blacklist.py:31`); ninguno de estos tres archivos lo
    redefine: `mail/models/res_partner.py`, `base/models/res_partner.py` y `phone_validation/models/mail_thread_phone.py`;
  - el campo está en `:33-36` (`store=True`, `compute_sudo=True`);
  - `@api.depends(lambda self: [self._primary_email])` (`:46`), que en `res.partner` da `['email']`;
  - un `write` de `email` lo deja en `tocompute` (`models.py:5846`).
- **C4, entorno:**
  - `psycopg2` 2.7.7, **sin `psycopg2.errors`**, con `errorcodes.LOCK_NOT_AVAILABLE = '55P03'`;
  - `sql_db.Cursor` sin `__slots__`;
  - `unittest` **sin `assertNoLogs`** (Python 3.7);
  - `Cursor.execute` (`odoo/sql_db.py:292-333`) registra en ERROR «bad query» en `odoo.sql_db` y relanza (`:302-305`);
  - `Registry.cursor` (`odoo/modules/registry.py:698-706`) solo devuelve un `TestCursor` en el modo de pruebas de
    `HttpCase` (`:702-705`); en un `TransactionCase`, cada cursor es una conexión nueva (`:706`).

**Citas del repo** (con Read):
- **R1, `pns_ai_mcp/models/api_result_cache.py`:**
  - `_logger = logging.getLogger(__name__)` (`:15`);
  - `_store` (`:106-143`) abre `with self.env.registry.cursor() as cr` (`:132`) con un `api.Environment` propio y
    `sudo()` (`:133`);
  - el `try` (`:114`) envuelve todo, `with` incluido;
  - `except Exception` (`:139-143`) registra un WARNING «ai.api.result.cache: store failed for %s/%s», con
    `exc_info=True` y sin relanzar.
- **R2, `pns_ai_mcp/controllers/safe_plan_http.py`, `_execute_api_call` (`:411-539`):**
  - `_api_call_schema_error` (`:447`) va fuera de cualquier `try`;
  - un `try` (`:461-497`) envuelve `_get_cached`, `get_api_driver`, `_resolve_auth_token` y `driver.call` (`:469`); sus
    `except` (`:498-513`) devuelven un diccionario de error sin relanzar;
  - `Cache._store` va en `try/except Exception: pass` (`:517-523`);
  - **`format_api_call_body_for_llm` (`:525`) no tiene `try`**, y `execute_safe_plan` tampoco envuelve el paso
    (`safe_plan_execute.py:103-111`);
  - contrato de `driver.call` (`lib/api/drivers/base.py:85-100`): `call(server, tool_name, arguments=None,
    auth_token=None)`, que devuelve `str`. Un cuerpo con claves de fichero se trata como binario
    (`utils/session_download.py:588-637`).
- **R3, `pns_ai_mcp/models/safe_operation.py`:**
  - `_execute_plan_with_timeouts` (`:960-1030`) pone en `cr2` `lock_timeout = '5s'` y `statement_timeout = '15s'`
    (`:969-970`). Se pierden en el `commit` de `:1457` y se reponen en `:1467-1468`. No hay alarma ni hilo;
  - ante una excepción, `execute_plan_now` (`:1502-1541`) hace `rollback`, libera el claim, registra el plan fallido y
    relanza;
  - `_execute_plan_with_timeouts` la captura (`:984`) y devuelve `status: 'error'` (`:1001-1010`) sin relanzar;
  - el plan se ejecuta con `op.user_id` (`:1439`).
- **R4, destino de los parches:**
  - `get_api_driver` y `format_api_call_body_for_llm` se importan dentro de la función en cada llamada
    (`safe_plan_http.py:422-427`), así que se parchean en `lib.api.drivers` (que lo reexporta,
    `drivers/__init__.py:9`) y en `utils.api_call_result`;
  - `_api_call_schema_error` se importa por nombre al cargar el módulo (`:18-20`), así que se parchea en
    `controllers.safe_plan_http`.

**Cambios frente al «Diseño revisado del test de la caja B»** (decididos por Sergio el 12/11/2026):
- **A. Guarda y comprobación:**
  - `self.patch` sobre `Registry.cursor` (`:318-339`). Con la guarda activa, cada cursor nuevo recibe
    `SET LOCAL lock_timeout = '3s'` y un envoltorio de `execute` como atributo de la instancia (C4: sin `__slots__`);
  - ante un `psycopg2.Error` con `pgcode == errorcodes.LOCK_NOT_AVAILABLE`, el envoltorio anota la tabla de la
    plantilla SQL (`_table_of`, `:54`; nunca los parámetros) y relanza;
  - la guarda la activa el espía y la desactivan el stub de `format_api_call_body_for_llm` (`:341-344`), el `finally`
    de la llamada y la limpieza;
  - la única comprobación es `assertFalse(esperas)` (`:399-403`).
  - **Por qué:** con psycopg2 2.7.7 no existe la clase `LockNotAvailable`, así que se mira el `pgcode`. Y `assertLogs`
    falla si no hay ningún log; en Python 3.7 no hay `assertNoLogs`. No se usa ni `assertLogs` ni un handler del logger.
- **B. Llamada al plan:** dentro de `try/except Exception` (`:373-382`), que solo guarda el nombre de la clase para el
  mensaje. Es `_execute_plan_with_timeouts(op.id, admin_uid, {}, op.verification_id, title)`.
- **C. Precondiciones y control:**
  - el `status == 'error'` y el control van solo en el mensaje;
  - precondiciones: `towrite` vacío, grupos del admin, el espía se ejecutó, `email` de P fuera de `towrite` y P en
    `tocompute` de `email_normalized`;
  - se añadió una más: que el espía no fallara al anotar (`:387-390`).
- **D. Parches:** en los destinos de R4 (`:306-308`). El espía devuelve `'{"ok": true}'`.
- **E. Operación** (decisión de Sergio): `create_verification` + `_confirm_by_user`, como el flujo real y
  `test_safe_plan_atomicity`, con:
  - `operation_type='write'`, `model_name='res.partner'`, `records_count=2`, `changes_info` y `operation_data`
    (`plan_steps`, `title`, `plan`, `danger_level: 'low'`), `tool_name='seges_pns105_b'`;
  - la confirma el admin, que es su dueño (`op.with_user(admin)._confirm_by_user()`, `:254`), porque `_can_resolve`
    (`safe_operation.py:345-352`) pide ser el dueño o `group_ai_admin`;
  - ninguno de los dos abre cursores propios ni hace `commit` (`:476-541`, `:604-643`, `:1729-1745`, `:1938-1984`).
- **F. Datos y limpieza:**
  - datos con el ORM, en un cursor propio con `commit` (`odoo.registry(get_db_name())`, como en
    `test_seges_box_a_vias.py:93`), con el prefijo `seges-pns105-b-`;
  - grupos: se dan los que falten con `grant_groups` y se quitan con `revoke_groups` (decisión de Sergio). Los dos solo
    implican `base.group_user`;
  - limpieza (`:263-297`): borrado por SQL en savepoints y `commit`. `revoke_groups` usa el ORM y va en un cursor
    propio, después del SQL.

**Ejecución:**
- **Primera batería** (`tests-20261112-184842.log`): **E en `setUpClass`**, por un fallo del test (`cls.registry` no
  existe en un `TransactionCase` de Odoo 14). Se informó sin cambiarlo. Corrección aprobada: `odoo.registry(get_db_name())`.
- **Segunda batería** (`odoo-dev 14 tests pns_base,pns_ai_mcp,pns_ai_chatboo`, log `tests-20261112-190050.log`):
  - lint 0 incidencias nuevas; compilación con Python 3.7.3 correcta;
  - **513 tests, 4 F, 0 E y 4 saltados.** Las F: `test_paap_i7_cusp_roles_out_of_reach_of_an_ai_admin`,
    `test_log_commits_caller_pending_write`, `test_log_drops_pending_write_on_new_record` y el nuevo;
  - mensaje del nuevo: «PNS-105 (box B): step 2's own cursor waited for a row the plan cursor had already updated (lock
    timeout in the test; _store sets none, so in production the worker hangs). Waits on: res_partner; plan:
    status=error; control: email kept=True, email_normalized kept=True». Ninguna precondición falló.
- **Recuentos del log:**

  | Qué | Recuento |
  |---|---|
  | «store failed» | 1, del test nuevo (WARNING) |
  | «bad query» | 2: el `UPDATE "res_partner"` del test nuevo, con «canceling statement due to lock timeout», y el `INSERT INTO "ir_attachment"` de `TestSegesChatbooExportOwn.test_fulfill_client_export_claims_own`, de la línea base |
  | Errores del plan | `safe_operation.py:1503`: 1; `:984`: 1 |
  | Traceback | 62, frente a 58 de la línea base. Los 4 de más son del test nuevo: «store failed», `:1503`, `:984` y la F |
  | `seges-pns105-` | 3: el «bad query» y el «store failed» (`seges-pns105-b-`, 2) y la F de `test_log_drops_pending_write_on_new_record` |
  | Secretos `seges-3b-…` | 0 |
  | UUID4 | 0 |

  «incomplete cleanup» no aparece. La BD de tests se borra al acabar, así que no se pudo comprobar con un `SELECT` que
  no quedara nada; la limpieza no registró ningún error.
- **Qué confirma:**
  - el paso 1 vuelca `email` de P en el cursor del plan y deja `email_normalized` pendiente;
  - el `commit` del cursor propio de `_store` lo calcula y hace el `UPDATE` de P en su transacción;
  - ese `UPDATE` espera al cursor del plan, que está en el mismo hilo;
  - en el test lo corta el `lock_timeout` de 3 s, y `_store` se traga el error;
  - en producción `_store` no pone ningún límite: el worker se queda esperando hasta el `statement_timeout` de su
    propio cursor, si lo tiene. Esto no se ha comprobado.

## Decisiones de Sergio (12/11/2026, revisión de las dos propuestas)

Sobre «Propuesta: parche de `flush` antes de abrir la caja A» y «Propuesta de implementación de la 3b».

1. **Parche de `flush`:** número **37** (PNS-104, tipo `datos`). Va en `open_readonly_env`, antes de
   `base_env.registry.cursor()`. Sustituye al «flush previo» de columnas secretas de «Parche 18, opción B + B2», que no
   se implementa.
2. **PNS-104:** gravedad **Baja** (decidida). Estado: el mismo término que el seguimiento usa para un hallazgo del
   fabricante con un parche de Seges aplicado en la rama, como PNS-103. Detalle en «Implementación de la 3b».
3. **Excepción del `flush`:** llega al llamador sin convertir. Si falla, no se abre ningún cursor.
4. **`id`** queda fuera de la comprobación de ACL de O1.
5. **Negativos nuevos:** `compute_value` (sobre `totp_enabled`) y `export_data(['totp_secret'])`.
6. **Batería en dos puntos de control:** tras el 18 y tras el 37.
7. **Laboratorio de la 3b:** script presentado antes de ejecutarlo.
8. **Fuera de la 3b:** PNS-105, `iap.account.get` (P2), los registros `new()` del llamador (resto conocido) y el
   laboratorio con el core de LIYBEN.

## Decisiones de Sergio sobre la fase 0 de la 3b (12/11/2026)

1. **Positivo de la lectura genérica del motor:** `test_o1_score_fit_after_secret_cached` (`_score_record_fit`,
   `controllers/relaxaicode_models.py:153-232`, lee `rec[fname]` en `:205` en la caja A sin `su`).
2. **`export_data`** exige `base.group_allow_export` (`odoo/models.py:958-959`): el `asker` de
   `test_seges_box_a_vias` lo recibe en `setUpClass`. El `setUp` comprueba que lo tiene y que no tiene Ajustes, Access
   Rights ni AI Administrator.
3. **B2** en `utils/sandbox_helpers.py`, dentro de `collect_sandbox_helpers` (`:89` de 3.1.973). La propuesta citaba
   `controllers/context_builder.py:998-1003`, que es la llamada.
4. **Enganche 4, siempre en el sandbox** (no solo en la caja A): un objeto `Field` no tiene `env`. Desviación anotada en
   el registro.
5. **Errata de citas:** se corrigen contra el contenedor (abajo, «Errata de citas»).
6. **`test_read_group_alias_icp`:** `value:max(key)` pasa a positivo. Se comprueba con `assertTrue`/`assertFalse` que el
   resultado no contiene el valor de ningún parámetro secreto.
7. **Enganche 4 en lista cerrada** (cambio de diseño):
   - en el sandbox, de un objeto `Field` se rechaza cualquier atributo cuyo valor sea invocable, salvo
     `get_description`. Los atributos de metadatos siguen permitidos;
   - cierra `mapped`, `compute_value`, `read`, `recompute` y `convert_to_*` (incluido `Many2one.convert_to_read`, que
     da `value.sudo().display_name` de cualquier registro, `odoo/fields.py:2688-2695`);
   - test nuevo `test_o1_field_callable_refused`, con subtests `read` (Binary con adjunto), `recompute` y
     `convert_to_read` (Many2one). Entra en N18f;
   - restos en el registro: valores de otros registros en caché fuera de las reglas de registro («caché de otros
     modelos», ya registrado) y `selection` invocable rechazada.
8. **`database.secret`:** en la fase 3 se cuentan sus apariciones en los logs sin imprimirlo.

Recuento fijado: **505** tras el 18 (2 F: `test_paap_i7_cusp_roles_out_of_reach_of_an_ai_admin` y
`test_pending_write_survives_box_a_close`) y **508** tras el 37 (1 F: `test_paap_i7`); 0 E y 4 saltados en los dos.

## Decisiones de Sergio sobre las fases 1 a 3 de la 3b (12/11/2026)

- **Fase 1:**
  - `test_icp_str_id` acepta solo dos `AccessError`: el del fabricante («holds a credential») y el de Odoo («Database
    fetch misses ids … extra ids»). Sigue comprobando que el valor no llega;
  - el positivo `value:max(key)` de `test_read_group_alias_icp` se agrupa por `key`, no por `id`;
  - los imports de B van dentro de `open_readonly_env` (desviación anotada en el registro).
- **Fase 2:** `test_pending_compute_survives_box_a_close` deja pendiente solo el cálculo:
  - `UPDATE` directo de `name` en el cursor del test, invalidación de `name` y `env.add_to_compute(display_name, …)`;
  - precondición con `env.records_to_compute`;
  - comprobación final solo con SQL (`SELECT display_name`), sin `flush` ni lectura del ORM.
- **Fase 3:** el recuento de UUID4 sustituye al de `database.secret` (detalle abajo).
- **Redacción:** lo que la propuesta llamaba «los 12 de vía» son **10 tests de vía más
  `test_computed_secret_column_refused` (2 subtests)**. Las 14 F de la confirmación (log `tests-20261112-131534.log`)
  son esas 12 más `test_paap_i7` y `test_pending_write_survives_box_a_close`.

## Errata de citas (12/11/2026)

Citas de Odoo comprobadas contra el contenedor (`odoo` 14.0.20231106, `/usr/lib/python3/dist-packages/odoo`). El texto
de arriba no se reescribe; las citas correctas son estas:

| Cita en este documento | Dónde | Correcta |
|---|---|---|
| `sql_db.py:307` (`Cursor.rollback` → `clear_env`) | «Decisiones de Sergio sobre V1 a V5», punto 3; «Propuesta: parche de `flush`» | `sql_db.py:462` (`rollback` en `:459-468`) |
| `sql_db.py:294-302`, en `:296` (`Cursor.commit` → `flush_env`) | «Resultado de X1 a X4» | `sql_db.py:448-457`, en `:451` |
| `sql_db.py:315-317` (`Cursor.__getattr__`) | «Propuesta de implementación de la 3b» | `sql_db.py:470-472` (con `@check`, `:97-101`) |
| `models.py:3101-3103` (`_read` → `flush(fields, self)`) | «Parche 18, opción B + B2»; «Propuesta: parche de `flush`» | `models.py:3096` (`_read` en `:3080`) |

Las demás citas de esos pasajes coinciden con el contenedor: `sql_db.py:65-80` y `:82-87`, `api.py:620-627` y
`:760-765`, `models.py:5462` y `:5471-5480`. La misma errata se anota en las fichas de PNS-104 y PNS-105 del
[seguimiento](seguimiento_informe_pns_ai.md) y en [estado_hallazgos_3879.md](../specs/estado_hallazgos_3879.md).

## Implementación de la 3b (12/11/2026)

Detalle de cada parche en el [registro](parches_pns_ai.md), «Parches de la rama 14.0-pns-ai-3973 (fase 3b)».

**Código:**
- **Parche 18** (O1, B y B2): `models/seges_box_a_read.py` (nuevo; comprobación común y enganches 2 y 3),
  `models/__init__.py`, `controllers/context_builder.py` (enganches 1 y 4 en `_read_attr`), `utils/seges_box_a_cache.py`
  (nuevo; B y el envoltorio de B2), `controllers/controller_helpers.py` (B en `open_readonly_env`) y
  `utils/sandbox_helpers.py` (B2).
- **Parche 37:** `controllers/controller_helpers.py`, `base_env['base'].flush()` antes de `registry.cursor()`.

**Tests:**
- `test_seges_box_a_vias.py`: 22 → 38 en la fase 1 (16 nuevos) y 37 en la fase 2 (sale `TestSegesBoxACallerWrites`).
- `test_seges_sandbox_credentials.py` (33).
- `test_seges_box_a_flush.py` (4).

**Baterías** (tres módulos; BD de tests desechable `test_lab_pns_ai_3973_14`, en el contexto de `lab_pns_ai_3973`, que
monta esta copia de trabajo):

| Punto | Log | Tests | F | E | Saltados |
|---|---|---|---|---|---|
| Tras el 18, primera | `tests-20261112-143204.log` | 505 | 3: las dos esperadas y `test_icp_str_id` | 1: `test_read_group_alias_icp` | 4 |
| Tras el 18 | `tests-20261112-144029.log` | **505** | **2**: `test_paap_i7_cusp_roles_out_of_reach_of_an_ai_admin` y `test_pending_write_survives_box_a_close` | **0** | **4** |
| Tras el 37, primera | `tests-20261112-144518.log` | 508 | 2: `test_paap_i7` y `test_pending_compute_survives_box_a_close` (precondición) | 0 | 4 |
| Tras el 37 | `tests-20261112-152957.log` | **508** | **1**: `test_paap_i7` | **0** | **4** |

- Las dos primeras de cada punto se informaron sin cambiar los tests y se corrigieron con las decisiones de arriba.
  Ninguna era una fuga:
  - `test_icp_str_id`: la lectura con id de texto la corta la comprobación de tipos de id de Odoo dentro del guardián
    del fabricante;
  - `test_read_group_alias_icp`: agrupar por `id` con el alias da `ORDER BY "id" is ambiguous` en Odoo 14
    (`odoo/models.py:2385`);
  - `test_pending_compute_survives_box_a_close`: `write` y `flush(['name'])` ya recalculaban `display_name`.
- `auth_totp` está en la BD de tests (log `tests-20261112-143204.log:107`) y `test_c2_no_access_field_via_user` se
  ejecuta en todas.
- Saltados: los 4 de la línea base.
- Origen: `addons paths` con `/mnt/compartidos/third_party`.

**Neutralización** (una cada vez; copia, cambio con coincidencia única, batería completa, restauración y SHA-256). En
todas: 508 tests, 0 E, 4 saltados, `test_paap_i7` en F y SHA-256 igual al restaurar. Todas coinciden con lo previsto.

| Prueba | Cambio | Log | F, además de `test_paap_i7` |
|---|---|---|---|
| N18a | sin el enganche 1 | `tests-20261112-153358.log` | `test_decision2_v3_browse`, `test_decision2_v4_browse`, `test_computed_secret_column_refused` (`password`, `new_password`), `test_o1_str_format_refused` |
| N18g | sin el enganche 2 | `tests-20261112-153729.log` | `test_v1_getitem`, `test_v2_getitem`, `test_v3_getitem`, `test_v4_getitem`, `test_o1_itemgetter_refused`, `test_o1_sorted_refused`, `test_o1_export_data_refused`, `test_o1_acl_cached_field_refused` |
| N18m | sin el enganche 3 | `tests-20261112-154048.log` | `test_v1_mapped`, `test_v2_mapped`, `test_v3_mapped`, `test_v4_mapped`, `test_o1_filtered_refused` |
| N18f | sin el enganche 4 | `tests-20261112-154415.log` | `test_o1_field_mapped_refused`, `test_o1_field_compute_value_refused`, `test_o1_field_callable_refused` (`read`, `recompute`, `convert_to_read`) |
| N18acl | sin `check_access_rights` | `tests-20261112-154741.log` | `test_o1_acl_cached_field_refused` |
| N18b | sin B | `tests-20261112-155107.log` | `test_b_open_forgets_secret`, `test_box_a_icp_cache_before_run` |
| N18i | B sin `value` de `ir.config_parameter` | `tests-20261112-155432.log` | `test_box_a_icp_cache_before_run` |
| N18w | B con la caché entera | `tests-20261112-155757.log` | `test_b_open_keeps_non_secret` |
| N18h | sin B2 | `tests-20261112-160133.log` | `test_helper_sudo_read_forgotten` |
| N-flush | sin la línea del 37 | `tests-20261112-160458.log` | `test_pending_write_survives_box_a_close`, `test_pending_compute_survives_box_a_close`, `test_pending_write_box_a_reads_column`, `test_box_a_open_flush_error_no_cursor` |

Ninguna dio E en lugar de F, y ningún fallo de la línea base desapareció.

**Comprobaciones finales** (sobre el código final):
- **Lint del kit** (`odoo_lint.py --revisar pns_ai_mcp/`): 0 incidencias nuevas (178 preexistentes).
- **Compilación con Python 3.7.3** (contenedor): los 10 archivos cambiados.
- **Secretos con prefijo `seges-3b-`** en los 14 logs de la 3b (de `tests-20261112-143204.log` a
  `tests-20261112-160458.log`): **0**.
- **`database.secret`:** no se pudo contar con su valor:
  - cada batería crea su propia BD de tests, con un `database.secret` nuevo, y `odoo-dev 14 tests` la borra al acabar;
    ninguno de los 14 valores se podía leer ya;
  - sustituto aprobado por Sergio: contar en los logs las cadenas con formato UUID4
    (`[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}`, `grep -c -E`, sin imprimir nada). Odoo 14
    genera `database.secret` con `uuid.uuid4()` (`base/models/ir_config_parameter.py:20`);
  - resultado: **0 en los 14 logs**.
- **Marcadores fuera de tests:** 66 en los tres módulos (55 tras la 3a; +10 del 18 y +1 del 37).

**Recuento por archivo** (tras el 37): 434 de la 3a sin cambios, `test_seges_box_a_vias` 37,
`test_seges_sandbox_credentials` 33, `test_seges_box_a_flush` 4: **508**.

**Desviaciones frente a la propuesta de implementación:**
- enganche 4 siempre en el sandbox y en lista cerrada, con `test_o1_field_callable_refused`;
- B2 en `utils/sandbox_helpers.py`;
- imports de B dentro de `open_readonly_env`;
- `test_o1_score_fit_after_secret_cached` (positivo de la fase 0);
- `test_box_a_cannot_lift_mark` sin el intento con `_box_a_trusted` y sin los dos asserts de mensaje del parche 23
  (no existen en 3.1.973);
- tests de la 3b con 16 nuevos en vías, no 12: los 12 de la propuesta, los dos negativos de la revisión, el de la lista
  cerrada y el positivo de `_score_record_fit`.

## Laboratorio de la 3b (12/11/2026)

`lab_pns_ai_3973` (BD `lab_pns_ai_3973_14`) con los commits de la 3b. Scripts de solo lectura en el scratchpad de la
sesión, fuera del repo. Solo imprimen «rechazado/OK» o metadatos, nunca valores.

- **Reinicio sin `-u`:** `odoo-dev 14 parar` y `arrancar` desde `~/GitHub/lab_pns_ai_3973`. Inicio: 15:22:59 UTC (16:22:59
  hora local). En el log desde esa hora: 47 módulos cargados en `lab_pns_ai_3973_14`, 0 ERROR, 0 CRITICAL y 0 Traceback.
  Solo el `DeprecationWarning` de jinja2 al arrancar.
- **`p18_lab.py`** (`odoo-dev 14 shell`, herramienta `relaxaicode` real como `seges_int@example.com`, usuario 12;
  `rollback` al final):

  | Caso | Resultado |
  |---|---|
  | V3, variante del contenedor: tras `totp_enabled` del admin, `browse(id).totp_secret` | rechazado: credencial (fabricante) |
  | `rec['totp_secret']` | rechazado: credencial (fabricante) |
  | `mapped('totp_secret')` | rechazado: credencial (fabricante) |
  | `_fields['totp_secret'].mapped(u)` | rechazado: objeto `Field` (enganche 4) |
  | contactos (`search` y `name`), usuarios (`name` y `login`), `sorted`/`filtered`/`mapped` por nombre, `read()` de un contacto | OK |

  - Usuarios con TOTP: 0. El rechazo no depende de que haya una semilla.
  - `ai_log`: 61 filas antes y 61 después. El camino de la herramienta solo registra por
    `controller._log_mcp_operation`, que el stub de los tests no implementa (`tests/seges_common.py:42-43`). Sin
    `_create_log_entry` ni cursores propios: no hay escrituras PNS-105.
- **Dos turnos de Chatboo** (Sergio, como `seges_int@example.com`, `gemini-3.6-flash`):

  | Turno | Job | Resultado |
  |---|---|---|
  | «List 5 of my contacts with their email» | 9 (15:28:29–15:28:42 UTC) | `relaxaicode` como usuario 12; respuesta renderizada en el servidor; sin errores |
  | «Make a page with 5 of my contacts and their email» | 10 (15:29:24–15:31:32 UTC) | dominio `page_tab`; la llamada de diseño sale del helper de página dentro de `relaxaicode` (B2) y tarda unos 2 minutos; sin errores. Sergio comprobó que la página `/chatboo/canvas/8?rev=1` («Contacts Overview») se abre con los 5 contactos, su correo y sus fotos |

  - En el tramo: 0 Traceback, 0 ERROR, ningún 503 ni 429 del proveedor.
  - `ai_log` 62 a 74: las 13 del usuario 12, sin «error» en el resumen ni «Traceback» en el resultado. Comprobado con un
    `SELECT` de booleanos en una transacción de solo lectura.
- **Resultado:** O1, B y B2 validados en el laboratorio con la herramienta real y con Chatboo.

## P-22 (12/11/2026)

**Script** `p22_lab.py` (`odoo-dev 14 shell`; solo metadatos de `_fields` y `SELECT` de `ir_model_access`; no lee ninguna
fila de los modelos; `rollback` al final).
- Lista permitida de la 3879: `BOX_A_FIELD_ALLOW`, copiado tal cual de
  `~/pns_ai_3973/fase0/modulos_3879/pns_ai_mcp/models/box_a_guard.py:21-35`.
- **Fuente:** la elipsis «`…`» de [parches_pns_ai.md](parches_pns_ai.md):1437-1443 no basta como fuente. Mi primera
  versión del script la interpretó como `id, display_name, name` y no coincidía en `ai.api.server.key`, `ai.mcp.user`,
  `iap.account` e `ir.config_parameter`. La fuente literal es `box_a_guard.py:21-35` de la copia de la 3879.

**Resultado** (resumen; la salida completa, campo a campo, quedó en el scratchpad de la sesión):

| Modelo | Puerta `env[...]` | Lista de credenciales del fabricante | Grupos con lectura | Ocultos por el fabricante | Fuera de la lista de la 3879 y legibles en 3.1.973 |
|---|---|---|---|---|---|
| `ai.provider` | abierta | no | `base.group_user`, `group_ai_admin` | `api_key` | 25 (`endpoint`, `alias`, `model_id`, `temperature`, `spend_cap_*`…) |
| `ai.api.server` | cerrada | no | `base.group_user`, `group_ai_admin` | `auth_token`, `command_args`, `config_json`, `env_vars` | 32 (`base_url`, `url`, `auth_header_name`, `spec_json`, `tools_json`…) |
| `ai.api.server.key` | abierta | no | `base.group_user`, `group_ai_admin` | `token` | `active`, `notes`, `server_id` |
| `ai.mcp.user` | cerrada | sí | `group_ai_admin` | `mcp_api_key_hash` | 13 (`email`, `login`, `name`, `last_mcp_client_*`, `mcp_api_key_state`…) |
| `ai.key.pin.ask` | cerrada | sí | `group_ai_admin` | ninguno | **`pin`, `supplied_key`**, `email`, `login`, `mcp_user_id`, `failed`, `refused`, `desks` |
| `ai.key.pin.desk` | cerrada | sí | `group_ai_admin` | `token` | **`display_name`** (sale del token), `last_seen`, `user_id` |
| `ai.api.key.wizard` | cerrada | sí | `group_ai_admin` | ninguno | **`generated_key`, `manual_key`**, `mcp_user_id`, `confirmed`, `is_clear`, `is_import`, `has_api_key` |
| `ir.mail_server` | abierta | no | `base.group_system` | `smtp_pass` | `smtp_host`, `smtp_port`, `smtp_user`, `smtp_encryption`… |
| `fetchmail.server` | abierta | no | `base.group_system` | `password` | `server`, `port`, `user`, `configuration`, `script`… |
| `iap.account` | abierta | no | `base.group_system`, `base.group_user` | `account_token` | `company_ids` |
| `ir.config_parameter` | abierta | no | `base.group_system` | `value` (en la 3879, condicional por fila) | — |

**Hallazgo:** credenciales en claro que el criterio del fabricante no oculta.
- `ai.key.pin.ask.pin` y `.supplied_key`: filas confirmadas en cursor propio. Viven como mucho unos 20 segundos o
  2 minutos (`key_pin_desk.py`).
- `ai.api.key.wizard.generated_key` y `.manual_key`: transitorio, escritas en claro (`mcp_api_key_wizard.py:116`), nunca
  vaciadas. Duran hasta el limpiado de transitorios, 1 hora por defecto.
- El `display_name` de `ai.key.pin.desk`: su `_rec_name` es el token, así que el `display_name` es el token entero
  (`name_get`, contenedor `odoo/models.py:1736`, `:1746` y `:1750`). Con él, otro AI Administrator puede tomar el desk
  (`/pns_ai_mcp/key_pin/desk` → `_touch`) o cerrarlo (`/pns_ai_mcp/key_pin/stop` → `_close`). No da claves: `_supply`
  busca el desk por usuario.
- El fabricante cierra esos modelos en su puerta (`env[...]`, `RELAXAICODE_CREDENTIAL_MODELS`), pero un campo `Reference`
  la salta (`mail.template.preview.resource_ref`, el mismo camino de V2). Con O1 solo quedaba la ACL del modelo, que
  tiene el AI Administrator. No hay reglas de registro (Odoo 14 no tiene regla implícita para transitorios).

**Decisión de Sergio (12/11/2026): opción 3(b), como ampliación del parche 18** (mismo marcador):
- `_pns_secret_fields` en `ai.key.pin.ask` (`pin`, `supplied_key`) y `ai.api.key.wizard` (`generated_key`,
  `manual_key`);
- y, para el desk, `display_name` (opción 2 de la pregunta sobre el desk);
- se aceptan sus efectos fuera de la caja A: la exportación nativa y la portable dejan vacíos esos cinco campos.

**Comprobaciones previas por lectura:**
- `field_is_secret` da verdadero para cualquier nombre de `_pns_secret_fields` antes de mirar el tipo
  (`utils/sandbox_secrets.py:61-62`), también para un calculado no guardado como `display_name`. Así,
  `_pns_hidden_column('display_name')` es verdadero en el desk.
- El flujo del PIN (`_collect`, `_take`, `_supply`, en `sudo` y con cursores propios) y el asistente de claves (lectura
  del cliente web) no pasan por la caja A.

**Doble barrera en el desk:**
- el criterio de `token` en el cálculo: `name_get` lee `record['token']`, que O1 rechaza;
- la entrada `display_name`, para el valor ya en la caché, que no pasa por `name_get`.

La primera N18p (log `tests-20261112-165002.log`) dio 4 F y no 5: el subtest del desk leía `display_name` sin caché y lo
rechazaba el criterio de `token`. Por decisión de Sergio, el subtest pasa a medir el valor en caché.

## Implementación de P-22 (12/11/2026)

- **Código** (marcador del 18):
  - `pns_ai_mcp/models/key_pin_desk.py:28-30` (desk, `display_name`) y `:170-171` (`ai.key.pin.ask`);
  - `pns_ai_mcp/models/mcp_api_key_wizard.py:19-20`.
- **Tests** (`test_seges_box_a_vias.py`, 37 → 39):
  - `setUpClass` confirma, con prefijo `seges-3b-p22-`, un AI Administrator (sin Ajustes), una fila de
    `ai.key.pin.ask`, un desk y un `ai.api.key.wizard`, con su limpieza;
  - `test_o1_p22_credential_models_refused`, como AI Administrator (con ACL, comprobada) y por `Reference`. Cinco
    subtests (`pin`, `supplied_key`, `generated_key`, `manual_key` y `desk display_name`) que esperan «holds a
    credential». En el del desk, un stub (`_WarmDeskStub`) carga el `display_name` en la caché con una lectura en `sudo`
    sobre el `env` de la caja A, después de B. La precondición `env.cache.contains` se comprueba sin imprimir. Entre ese
    punto y la lectura solo corren `build_safe_context`, `_fill_run_context` y la compilación
    (`tools_relaxaicode.py:178-200`): mide O1, no B;
  - `test_o1_p22_wizard_shows_key_outside_box_a` (positivo aparte): fuera de la caja A, el asistente sigue mostrando la
    clave generada a quien la genera.
- **Batería** (log `tests-20261112-165632.log`): **510 tests, 1 F** (`test_paap_i7_cusp_roles_out_of_reach_of_an_ai_admin`),
  **0 E y 4 saltados**. Traceback en el log: 56, los mismos que en `tests-20261112-152957.log`.
- **N18p** (sin las tres entradas de `_pns_secret_fields`; log `tests-20261112-170001.log`): F en los 5 subtests de
  `test_o1_p22_credential_models_refused` (el del desk, por «filtra») y SHA-256 igual al restaurar en los dos archivos.
- **Comprobaciones finales:**
  - lint (`--revisar pns_ai_mcp/`): 0 incidencias nuevas (185 preexistentes; entran los dos modelos del fabricante
    tocados);
  - Python 3.7.3: 12 de 12 archivos;
  - secretos y UUID4: 0 en los 28 logs de tests del 12/11/2026;
  - marcadores fuera de tests: 69.
- **Patrón de secretos ampliado:** desde aquí, `seges-3b-[a-z0-9-]*[0-9a-f]{32}`. El anterior
  (`seges-3b-[a-z]*-\?[0-9a-f]\{32\}`) no detectaba `seges-3b-p22-…` (dígitos en el prefijo). Con el patrón ampliado se
  repasaron también los logs anteriores del día: 0.
- **Contenedores:** P-22 se probó sin el servidor web. Solo se levantaron PostgreSQL y los contenedores de un solo uso de
  los tests, y se pararon al acabar. `name_get` se confirmó con un contenedor de un solo uso de la imagen
  (`docker run --rm`).
- **Recuento por archivo:** 434 de la 3a, `test_seges_box_a_vias` 39, `test_seges_sandbox_credentials` 33,
  `test_seges_box_a_flush` 4: **510**.

## Pendientes fuera de la 3b (12/11/2026)

- **Servidor del laboratorio sin `dbfilter` ni `db_name`:** ejecuta los crons de todas las BD de Odoo 14. El 12/11/2026,
  al reiniciar, cargó `lab_pns_ai_3879_14` con el código de 3.1.973 (sin `-u`; la carga la provocó una pestaña abierta en
  esa BD) y ejecutó sus crons:

  | Hora (UTC) | Cron | Módulo | Resultado |
  |---|---|---|---|
  | 15:24:13 | Post process payment transactions | `payment` (core) | done |
  | 15:26:13 y 15:31:13 | AI: expire pending supervised operations (`model.cleanup_expired()`) | `pns_ai_mcp` | done |
  | 15:26:13 y 15:31:13 | Chatboo: async queue maintenance (`model.cron_maintenance()`) | `pns_ai_chatboo` | done |

  Pendiente de decidir:
  - si se limita el servidor a la BD del laboratorio;
  - si `lab_pns_ai_3879_14` sigue siendo fiable antes de volver a usarla: dos crons de `pns_*` corrieron con código de
    3.1.973 sobre ella y pudieron escribir.
- **`csrf_token` impreso por error** en la salida del agente al filtrar el log de los turnos de Chatboo (dos líneas de
  `werkzeug`). Es de la sesión del laboratorio y no tiene consecuencias. Desde entonces se filtra antes de imprimir.
