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
