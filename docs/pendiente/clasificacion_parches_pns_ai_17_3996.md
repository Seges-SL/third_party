# Clasificación de los parches `pns_ai` para la 17.0.3.1.996

- **Rama:** `17.0-pns-ai`, sobre `27c8045` ([plan](plan_pns_ai_17.md), fase 0).
- **Fecha:** 23/11/2026. Solo lectura: no se ha aplicado, instalado ni probado nada.
- **Alcance:** qué parches de la 14 hacen falta en la 17 y por qué. Cómo se adapta cada uno se decide después (fase 2
  del plan).

## 1. Propósito y partida

- **Base (R17):** `/home/soporte/pns_fabricante/17.0_17.0.3.1.996`, idéntica a los tres módulos de `17.0-pns-ai`
  (`diff -rq` sin diferencias; 64 + 477 + 129 archivos). Según su `ORIGEN.txt` (rama 17.0, descargada el 23/11/2026):

  | Módulo | Versión | Commit |
  |---|---|---|
  | `pns_base` | 17.0.1.2.92 | `9272e5d40426fc14a53dd8031d0f8954ca5c3dd3` |
  | `pns_ai_mcp` | 17.0.3.1.996 | `1f63e0a2f372ded02e3f6bb53a458992817d3465` |
  | `pns_ai_chatboo` | 17.0.2.1.597 | `48a1e92a224a3d92f917898e7a9480dc578216bf` |

- **Referencia de la 14 (R14):** `/home/soporte/pns_fabricante/3.1.973` (14.0.1.2.69, 14.0.3.1.973 y 14.0.2.1.587),
  sin parches. Con parches (P14): rama `14.0` del repo, leída con `git show 14.0:<ruta>`.
- **Índice de parches:** `docs/pendiente/parches_pns_ai.md` de `14.0` (5654 líneas, SHA-256
  `bc29f0dd8d4b81e580fc536a7af2e44ecb2b19cbe98fc6323bef18591a5320f5`); índice de 3.1.973 en las líneas 242–273 y
  entradas «Parches de la rama 14.0-pns-ai-3973».
- **Citas del core de Odoo 17:** de la referencia `/opt/odoo-src/17.0` (commit `6a0efa7`, del 05/10/2026). El
  laboratorio usa la imagen `odoo-dev:17` (Odoo 17.0 del 08/09/2026, `ODOO_RELEASE=20260908`): las líneas se
  confirman en el contenedor (sección 8).
- **14.0.3.1.996 del fabricante:** no se descargó. Los cuatro «cambiado» lo son por el cambio de serie (API de Odoo
  17), no de versión, y esa copia no los aclararía.

## 2. Método

1. Archivos parcheados: R14 frente a P14 en los tres módulos (distintos, solo en P14, solo en R14), con los marcadores
   `Seges: parche N` de P14 para saber qué parche toca cada trozo.
2. Por archivo: si existe en R17, si es idéntico al de R14 y qué da la diferencia R14→P14 aplicada a R17 con
   `patch --dry-run` (limpio, con desplazamiento o fuzz, o falla).
3. Por parche vivo, con su entrada del índice y el código de R17 alrededor de lo parcheado:
   - **igual:** se pasa tal cual;
   - **igual\*:** se pasa tal cual, pero su contenido es una lista de nombres del core que hay que repasar en la 17;
   - **cambiado:** el código de R17 cambia; decidir si el fabricante lo corrigió o hay que adaptar el parche;
   - **desaparecido:** el código parcheado ya no está;
   - **no aplica:** la causa no existe en la 17.
4. Retirados: comprobar en R17 la corrección del fabricante. Lo que adaptaba `4e1ebcc` ya lo trae la 17.0.3.1.996
   (`utils/version_gates.py` y `security_groups.xml`).

## 3. Archivos

R14 tiene 657 archivos y P14, 688; ninguno está solo en R14. Fuera de la tabla: 25 `tests/test_seges_*.py`,
`pns_ai_chatboo/tests/common.py`, `pns_ai_mcp/tests/seges_common.py` (sección 7) y los dos `tests/__init__.py`
(idénticos en R14 y R17; aplican limpio).

| Archivo | +/− | Parches | R14 = R17 | `patch --dry-run` sobre R17 |
|---|---|---|---|---|
| `pns_ai_chatboo/models/chatboo_async_request.py` | +25 −2 | 34 | no | aplica: 4 desplazados, 1 con fuzz 2 (de 5) |
| `pns_ai_chatboo/models/chatboo_canvas.py` | +327 −13 | 26, 27, 29, 34 | sí | limpio (20) |
| `pns_ai_chatboo/models/chatboo_canvas_page.py` | +10 | 28 | sí | limpio (2) |
| `pns_ai_chatboo/models/chatboo_session.py` | +101 −49 | 11, 25, 26, 29, 38 | no | aplica: 8 desplazados (de 9) |
| `pns_ai_chatboo/security/security.xml` | +4 −2 | 28 | sí | limpio (1) |
| `pns_ai_chatboo/static/src/js/chart.umd.min.js` | +4 −2 | 20 | sí | limpio (2) |
| `pns_ai_chatboo/static/src/js/chatboo_heavy_libs.js` | +5 −2 | 20 | no | falla 2 de 2 |
| `pns_ai_mcp/controllers/context_builder.py` | +93 −2 | 18, 24, 39 | sí | limpio (7) |
| `pns_ai_mcp/controllers/controller_helpers.py` | +29 | 18, 37 | sí | limpio (2) |
| `pns_ai_mcp/controllers/safe_plan.py` | +6 −2 | 38 | sí | limpio (3) |
| `pns_ai_mcp/controllers/safe_plan_execute.py` | +3 | 17 | sí | limpio (1) |
| `pns_ai_mcp/controllers/validators_base.py` | +68 | 15, 22, 39 | sí | limpio (1) |
| `pns_ai_mcp/models/__init__.py` | +2 | 18 | sí | limpio (1) |
| `pns_ai_mcp/models/ai_change_journal.py` | +23 −3 | 17, 38 | no | aplica: 4 desplazados (de 5) |
| `pns_ai_mcp/models/ai_log.py` | +129 −124 | 38 | no | falla 1 de 2 |
| `pns_ai_mcp/models/ai_provider.py` | +4 −2 | 33 | sí | limpio (2) |
| `pns_ai_mcp/models/ai_skill_param_cache.py` | +22 −18 | 38 | sí | limpio (2) |
| `pns_ai_mcp/models/ai_system_action.py` | +22 | 12 | sí | limpio (6) |
| `pns_ai_mcp/models/ai_trusted_action.py` | +34 −2 | 32 | sí | limpio (2) |
| `pns_ai_mcp/models/api_result_cache.py` | +4 −1 | 38 | sí | limpio (2) |
| `pns_ai_mcp/models/key_pin_desk.py` | +11 −2 | 18, 38 | sí | limpio (5) |
| `pns_ai_mcp/models/mcp_api_key_wizard.py` | +2 | 18 | sí | limpio (1) |
| `pns_ai_mcp/models/safe_operation.py` | +14 −4 | 16, 38 | sí | limpio (6) |
| `pns_ai_mcp/utils/engine_tool_run.py` | +4 −1 | 38 | sí | limpio (2) |
| `pns_ai_mcp/utils/fetch_url_safe.py` | +10 −1 | 19 | sí | limpio (1) |
| `pns_ai_mcp/utils/field_required_plan.py` | +4 −1 | 38 | sí | limpio (2) |
| `pns_ai_mcp/utils/mcp_client.py` | +8 | 19 | sí | limpio (1) |
| `pns_ai_mcp/utils/privilege_cusp.py` | +27 −2 | 12 | sí | limpio (3) |
| `pns_ai_mcp/utils/sandbox_helpers.py` | +20 −1 | 18 | sí | limpio (2) |
| `pns_ai_mcp/utils/session_download.py` | +4 −1 | 38 | sí | limpio (1) |
| `pns_ai_mcp/wizard/ai_provider_usage_wizard.py` | +3 −1 | 33 | sí | limpio (1) |
| `pns_base/models/operation_report_wizard.py` | +27 −3 | 21, 36 | no | falla 4 de 4 |
| `pns_ai_mcp/models/seges_box_a_read.py` (nuevo) | +67 | 18 | — | no existe en R17 |
| `pns_ai_mcp/utils/seges_box_a_cache.py` (nuevo) | +71 | 18 | — | no existe en R17 |
| `pns_base/utils/seges_side_env.py` (nuevo) | +107 | 38 | — | no existe en R17 |
| `pns_ai_mcp/migrations/14.0.3.1.973/post-migrate.py` (nuevo) | +42 | 35 | — | R17 no tiene `migrations/` |

En `ai_log.py`, el +129 −124 es casi todo sangrado (el `with` del 38 envuelve el bloque).

Cruce con el índice de 3.1.973: coinciden, con tres matices:

- `pns_ai_mcp/models/__init__.py` lleva el marcador del 18, pero no está en su fila del índice (sí en la entrada y en
  la fila de la rama 3879).
- La fila del 25 cita `chatboo_canvas.py`, que no lleva marcador del 25: es lo que dice la propia fila («solo la
  comprobación del dueño, en `chatboo_session.py`»).
- Los dos `tests/__init__.py` no están en el índice (solo registran los tests).

## 4. Parches vivos

| N.º | PNS / id | Módulo | Clasificación | Motivo |
|---|---|---|---|---|
| 11 | PNS-82 | chatboo | igual | Lo nuevo de R17 en `chatboo_session.py` (`sandbox_helpers`, `:851`; documentos, `:1305-1434`) queda fuera de lo parcheado |
| 12 | PNS-01, PNS-02 | mcp | igual | Archivos idénticos; `has_group` y `AccessError(UserError)` siguen en la 17 (`odoo/exceptions.py:74`) |
| 15 | PNS-07 | mcp | igual | `validators_base.py` idéntico; los nombres son del fabricante |
| 16 | PNS-54 | mcp | igual | `safe_operation.py` idéntico; `check_identity` sigue (`odoo/addons/base/models/res_users.py:139`) |
| 17 | PNS-37 | mcp | igual | R17 solo añade en `ai_change_journal.py:222-227` (`snapshot_records`), fuera de los trozos del 17 |
| 18 | PNS-19 | mcp | cambiado | Serie: la parte B supone `towrite` aparte de la caché (detalle abajo) |
| 19 | PNS-17 | mcp | igual | Archivos idénticos |
| 20 | PNS-70 | chatboo | cambiado | `chatboo_heavy_libs.js` reescrito como módulo ES (detalle abajo) |
| 21 | PNS-20 | base | cambiado | Archivo adaptado a la 17; el fallo sigue (detalle abajo) |
| 22 | PNS-100 | mcp | igual\* | Aplica limpio; `install_from_urls` desaparece, `execute_callback` pasa a privado y hay 5 públicos nuevos en la 17 (detalle abajo) |
| 24 | PNS-102 | mcp | igual | `context_builder.py` idéntico; `env.user` sigue con `su` (`odoo/api.py:628`) |
| 25 | M1 | chatboo | igual | Su trozo de `chatboo_session.py` aplica desplazado |
| 26 | M2 | chatboo | igual | `chatboo_canvas.py` idéntico; el trozo de la sesión aplica desplazado |
| 27 | F1 | chatboo | igual | `chatboo_canvas.py` idéntico |
| 28 | D1 | chatboo | igual | `chatboo_canvas_page.py` y `security.xml` idénticos |
| 29 | F1 (P-8e a) | chatboo | igual | Aplica; su adaptación de tests con `flush()` depende del 38 (sección 6) |
| 32 | PNS-97 | mcp | igual | Archivo idéntico |
| 33 | PNS-29 | mcp | igual | Archivos idénticos |
| 34 | PNS-96 | chatboo | igual | R17 solo cambia imports y lectura de PDF (`:20-37`, `:908-931`); el fuzz cae en el import |
| 35 | PNS-109 | mcp | no aplica | Migración atada a 14.0.3.1.973 (sección 6) |
| 36 | PNS-103 | base | cambiado | La inyección de la vista cambia; el fallo sigue (detalle abajo) |
| 37 | PNS-104 | mcp | no aplica (probable) | La causa es el conjunto de entornos por hilo de Odoo 14 (sección 6) |
| 38 | PNS-105 | base, mcp, chatboo | no aplica (probable) | La misma causa; `api.Environments` no existe en la 17 (sección 6) |
| 39 | PNS-107 | mcp | igual\* | Aplica limpio; hay públicos nuevos en la 17 que llegan a `iap.account.get` (detalle abajo) |

Recuento: 15 igual, 2 igual\* (22 y 39), 4 cambiado (18, 20, 21 y 36), 3 no aplica (35, 37 y 38), 0 desaparecido.

### Parche 18 (cambiado, serie)

- Archivos idénticos y aplica limpio. El guardián del fabricante (`pns_ai_mcp/models/sandbox_secret_read.py`) solo
  cambia los mensajes (`SECRET_DENIED_PREFIX`): el fallo de partida (un valor en caché se lee sin comprobar) es
  probable que siga en la 17.
- Riesgo de la parte B: `seges_box_a_cache.py` (P14, `:18` y `:52`) invalida columnas secretas suponiendo que lo
  pendiente vive en `towrite` y se conserva. En la 17 lo pendiente está en la caché, y `Cache.invalidate` lo tira
  (`odoo/api.py:1300-1302`, «drops the value to be written»).
- Los ganchos de `seges_box_a_read.py` citan `name_get` y `_fetch_field` de la 14.

### Parche 20 (cambiado)

- R17: `chatboo_heavy_libs.js` usa `loadJS` de `@web/core/assets` (`:7`) y `window.Chart` (`:27`); los 2 trozos fallan.
- `chart.umd.min.js` es idéntico (Chart.js 4.4.8): la parte de los tokens aplica.
- Odoo 17 carga su propio Chart.js en `web.chartjs_lib` (`addons/web/__manifest__.py:458-460`, con
  `chartjs-adapter-luxon`): es probable que la colisión con `window.Chart` siga.

### Parche 21 (cambiado; el fallo sigue)

- Fallan los 4 trozos (3 del 21 y 1 del 36): el archivo usa `get_view`, `form_view_ref` e `invalidate_all`.
- R17 no vuelca lo pendiente antes del `SAVEPOINT` (`pns_base/models/operation_report_wizard.py:315`).
- `_invalidate_after_preview_rollback` hace `self.env.invalidate_all()` (`:295`), que por defecto vuelca lo pendiente
  (`odoo/api.py:719-728`) después del `ROLLBACK TO SAVEPOINT`: puede escribir lo de la importación fuera del
  savepoint.
- `registry.clear_caches()` del parche no existe en la 17 (`odoo/modules/registry.py:716`, `clear_cache`).

### Parche 36 (cambiado; el fallo sigue)

- R17 inyecta la vista en `_inject_screen_arch` (`operation_report_wizard.py:327-342`) con `self.env.ref(xmlid)` y
  `src.arch` sin `sudo` (`:331`).
- En la 17, `ir.ui.view` solo lo lee `base.group_system` (`odoo/addons/base/security/ir.model.access.csv:34-35`).

### Parche 22 (igual\*)

| Nombre | Modelo en la 14 | En la 17 |
|---|---|---|
| `connect` | `ir.mail_server`; `fetchmail.server` | igual; `fetchmail.server` pasa de `fetchmail` a `mail` (`addons/mail/models/fetchmail.py:150`) |
| `test_smtp_connection` | `ir.mail_server` | igual (`odoo/addons/base/models/ir_mail_server.py:284`) |
| `load_remote_url` | `ir.qweb.field.image` | igual, en `addons/web_editor/models/ir_qweb_fields.py:502` |
| `fetch_mail` | `fetchmail.server`; `ir.mail_server` (`l10n_it_edi`) | `fetchmail.server` en `mail` (`:215`); el de `l10n_it_edi` desaparece |
| `button_confirm_login` | `fetchmail.server` | igual, en `mail` (`:180`) |
| `get_credits` | `iap.account` | igual (`addons/iap/models/iap_account.py:221`) |
| `autocomplete`, `enrich_company`, `read_by_vat` | `res.partner` | existen, pero vacíos («Deprecated since DnB», `addons/partner_autocomplete/models/res_partner.py:72-83`) |
| `start_sync` | `res.partner.autocomplete.sync` | existe, vacío (`res_partner_autocomplete_sync.py:17-18`) |
| `send_letter` | `mail.message` | igual (`addons/snailmail/models/mail_message.py:30`) |
| `snailmail_print` | `snailmail.letter` | igual (`snailmail_letter.py:428`) |
| `update_notification` | `publisher_warranty.contract` | igual (`addons/mail/models/update.py:83`) |
| `install_from_urls` | `ir.module.module` | **desaparece** (ni en el core ni en los addons) |
| `action_process_edi_web_services` | `account.move`; `account.payment` | `account.move` (`addons/account_edi/models/account_move.py:378`); el de `account.payment` desaparece |
| `get_usd_fx` | `pns_ai_mcp` (no es del core) | igual en R17 (`pns_ai_mcp/models/ai_fx_source.py:87`; `pns_ai_chatboo/utils/fx_rates.py:12`) |
| `execute_callback` | `payment.transaction` | **pasa a privado**: `_execute_callback` (`addons/payment/models/payment_transaction.py:880`) |
| `upgrade_module` | `base.module.upgrade` | igual (`odoo/addons/base/wizard/base_module_upgrade.py:50`) |
| `action_start_automatic_process`, `parent_migration_process_cb` | `base.partner.merge.automatic.wizard` | igual (`base_partner_merge.py:546`, `:570`) |
| `message_process`, `message_route` | `mail.thread` | igual (`addons/mail/models/mail_thread.py:1365`, `:1079`) |

- Públicos nuevos de la 17 que llegan a `iap.account.get` sin escribir (por `_request_partner_autocomplete` →
  `iap.autocomplete.api._contact_iap`, `iap_autocomplete_api.py:22`): `autocomplete_by_name`, `autocomplete_by_vat`,
  `enrich_by_duns`, `enrich_by_gst` y `enrich_by_domain` (`res_partner.py:91, 108, 171, 178, 185`). Sustituyen a los
  tres vacíos.

### Parche 39 (igual\*)

- `iap.account.get` sigue (`addons/iap/models/iap_account.py:124`). Los 8 públicos del grupo A existen en la 17, en
  sus modelos (`crm.iap.lead.mining.request` pasa a `crm_iap_mine`, `action_submit` en `:318`).
- Públicos de la 17 que no están entre los 8:
  - `res.config.settings.l10n_in_edi_buy_iap` (`addons/l10n_in_edi/models/res_config_settings.py:47`) →
    `get_credits_url` (`:52`) → `get` (`iap_account.py:182`), sin escribir antes;
  - `action_buy_credits` en `iap.account` (`iap_account.py:193`, solo llega a `get` si la cuenta no tiene token) y en
    `crm.iap.lead.mining.request` (`crm_iap_mine/models/crm_iap_lead_mining_request.py:355`, sin token): el nombre ya
    está en la lista global por `sms.resend`, pero no en `RELAXAICODE_SIDE_EFFECT_MODEL_METHODS` para esos modelos;
  - los cinco de `partner_autocomplete` del parche 22 (arriba).
- Frenados por el READ ONLY antes de `get`, como en la 14 (grupo B): `crm.lead.iap_enrich`
  (`addons/crm_iap_enrich/models/crm_lead.py:59`, `FOR UPDATE NOWAIT`) y `l10n.in.ewaybill.generate_ewaybill`
  (`addons/l10n_in_ewaybill_stock/models/l10n_in_ewaybill.py:228` → `_lock_ewaybill`, `:390`). El asistente
  `l10n.in.ewaybill.cancel.cancel_ewaybill` escribe antes (`wizard/l10n_in_ewaybill_cancel.py:25`).
- Privados o no alcanzables: las cadenas de `l10n_in_edi` y `l10n_in_edi_ewaybill` (`account.edi.format`), el
  controlador de `mail_plugin` y `iap_mail._send_no_credit_notification`.

## 5. Retirados

Los seis siguen corregidos en R17:

| N.º | PNS / id | En R17 |
|---|---|---|
| 10 | PNS-83 | `_collect_pin` (`pns_ai_mcp/models/key_pin_desk.py:185`) y `_redeem_key_pin` (`models/mcp_user.py:785`) |
| 13 | M10 | `create` y `write` solo con `su` (`models/safe_operation.py:546-556`); `_cleanup_stuck_state` (`:1031`) |
| 14 | M13 | `_unlink_retired_from_module` (`models/ai_context_disk.py:751`) |
| 23 | PNS-101 | `controllers/context_builder.py` idéntico a R14 |
| 30 | M11 | `log_*` privados (`models/ai_execution_engine.py:425-781`) |
| 31 | M12 | `_chat_completion` (`models/ai_execution_engine.py:872`); el `chat_completion` de `:38` es del envoltorio del driver |

Restos conocidos del 23, iguales en R17: la fachada solo sustituye `attrgetter` y `methodcaller`
(`context_builder.py:468-471`), con `itemgetter` nativo, y un `Markup` admite campos simples en `format` (`:328`).

## 6. No aplica

- **35 (PNS-109):** como migración, no. La causa sigue en los datos: los dos crons están en `noupdate="1"`
  (`pns_ai_mcp/data/fetch_cache_cron.xml:2,10`; `data/api_result_cache_cron.xml:2,9`) y llaman a
  `model._gc_expired()` (`models/fetch_cache.py:135`; `models/api_result_cache.py:146`). En la 17 no hay BD con los
  módulos; solo importaría en una migración de 14 a 17 de una BD con el código antiguo del cron.
- **37 (PNS-104), probable:** en Odoo 14 el `rollback` de la caja A vaciaba lo pendiente del llamador porque todos los
  entornos del hilo compartían `towrite`. En la 17 cada cursor tiene su `Transaction` (`odoo/api.py:518-520`) y el
  `rollback` solo limpia la suya (`odoo/sql_db.py:490-492`).
- **38 (PNS-105), probable:** la misma causa. `seges_side_env.py` usa `api.Environments` y `Environment.envs`, que no
  existen en la 17. En R17 no hay nada general equivalente; solo un `flush` del llamador en `ai_log.py:720-730`
  (nuevo en 3.1.996, comentado para Odoo 14), que es por lo que falla su trozo. De sus 11 archivos, 8 están igual en
  R17; cambian `ai_log.py`, `ai_change_journal.py` y `chatboo_session.py`.
- **Dependencia del 29:** en 3.1.973 sus tests se adaptaron con `flush()` porque el 38 aísla al llamador (entrada del
  29, «Escrituras del llamador y cursor aparte»). Sin el 38, esa adaptación se revisa.

## 7. Tests de la 14

| Archivo | Parche |
|---|---|
| `pns_ai_chatboo/tests/test_seges_chatboo_access.py` | 11 |
| `pns_ai_chatboo/tests/test_seges_chatboo_canvas.py` | 25, 27, 29, 34 |
| `pns_ai_chatboo/tests/test_seges_chatboo_export.py` | 15 |
| `pns_ai_chatboo/tests/test_seges_chatboo_smoke.py` | sin parche (esqueleto de E0′) |
| `pns_ai_chatboo/tests/test_seges_skill_env.py` | 23 (retirado; no regresión) |
| `pns_ai_mcp/tests/test_seges_box_a_flush.py` | 37 |
| `pns_ai_mcp/tests/test_seges_box_a_vias.py` | 18 |
| `pns_ai_mcp/tests/test_seges_change_journal.py` | 17 |
| `pns_ai_mcp/tests/test_seges_e4p.py` | 33; 30 y 31 (retirados) |
| `pns_ai_mcp/tests/test_seges_facade_class.py` | 23 (retirado) |
| `pns_ai_mcp/tests/test_seges_fetch_redirect.py` | 19 |
| `pns_ai_mcp/tests/test_seges_format_guard.py` | 23 (retirado) |
| `pns_ai_mcp/tests/test_seges_identity_su.py` | 24 |
| `pns_ai_mcp/tests/test_seges_import_preview.py` | 21 |
| `pns_ai_mcp/tests/test_seges_migration_gc_crons.py` | 35 (no aplica) |
| `pns_ai_mcp/tests/test_seges_review_views.py` | 36 |
| `pns_ai_mcp/tests/test_seges_rpc_access.py` | 10, 14 y anteriores (retirados) |
| `pns_ai_mcp/tests/test_seges_safe_operation.py` | 13 (retirado) |
| `pns_ai_mcp/tests/test_seges_sandbox_credentials.py` | 18 |
| `pns_ai_mcp/tests/test_seges_sandbox_env.py` | 23 (retirado) |
| `pns_ai_mcp/tests/test_seges_sandbox_side_effects.py` | 22, 39 |
| `pns_ai_mcp/tests/test_seges_side_cursor_commit.py` | 38 |
| `pns_ai_mcp/tests/test_seges_user_groups.py` | 12, 32 |
| `pns_ai_mcp/tests/test_seges_verification.py` | 16 |
| `pns_ai_mcp/tests/test_seges_verify_execute_40001.py` | sin parche (anexo de PNS-26) |

Más `pns_ai_chatboo/tests/common.py` (`SegesChatbooCase`) y `pns_ai_mcp/tests/seges_common.py`. Sin test propio
identificado: 20 (prueba manual P-70), 26 y 28. El parche de cada test se toma de su marcador; si no lo lleva, de las
menciones del propio test (así `test_seges_rpc_access.py`) o de la entrada del índice.

## 8. Por confirmar en el laboratorio de la 17

1. 18: si la invalidación de la parte B pierde escrituras pendientes del llamador en la 17, y si el fallo de partida
   (valor en caché sin comprobar) sigue.
2. 20: si cargar el chat cambia `window.Chart` de Odoo y rompe sus gráficos (`web.chartjs_lib`).
3. 21: si la revisión de una importación deja escrito algo, con el `invalidate_all()` de R17.
4. 36: si un AI Administrator sin Ajustes abre las vistas de revisión y de resultado (`AccessError` en `ir.ui.view`).
5. 37 y 38: sus tests (`test_seges_box_a_flush.py`, `test_seges_side_cursor_commit.py`) adaptados a la 17, sin parche,
   para confirmar «no aplica».
6. 29: sus tests sin el 38.
7. 22 y 39: las listas frente al core de la 17 (sección 4, parches 22 y 39), y si hay otros públicos con efectos
   fuera de la BD.
8. Citas del core: las líneas de este documento son de `/opt/odoo-src/17.0` (`6a0efa7`); confirmarlas en el
   contenedor de `odoo-dev 17` (Odoo 17.0 del 08/09/2026).

## 9. Referencias antiguas del índice de la 14 (no se corrigen)

- La rama `14.0-pns-ai-3973` ya no existe; su trabajo está en `14.0` (cabeza actual `9cbb303`).
- La ruta `_fabricante/3.1.973/ORIGEN.txt` es hoy `/home/soporte/pns_fabricante/3.1.973/ORIGEN.txt`.
- `pns_ai_mcp/models/__init__.py` no está en la fila del 18 del índice de 3.1.973 (sección 3).

## 10. Resultado del laboratorio `lab_pns_ai_3996` (23/11/2026)

- **Montaje:** carpeta `~/GitHub/lab_pns_ai_3996`, fuera del repo (`.git` local sin commits ni remoto; `CLAUDE.md` y
  `.odoo-dev.conf` con `COMPARTIDOS="third_party"`). Imagen común `odoo-dev:17`, sin Dockerfile propio (la de los VPS;
  Python 3.10.12, Ubuntu Jammy). BD `lab_pns_ai_3996_17`, creada por `instalar` (datos de demostración, solo `en_US`) y
  **no neutralizada**: sus 7 crons `pns_*` están activos; ninguno usa la red. `third_party` es esta copia de trabajo en
  `17.0-pns-ai` (probado con HEAD `a35e4fd`). En la imagen faltan solo `pypdf` y `PyMuPDF` (opcionales), y no hay Chrome
  ni `websocket-client`.
- **Instalación:** `paridad pns_base,pns_ai_mcp,pns_ai_chatboo`: se pueden instalar (9 comprobados, 0 problemas).
  `instalar`: OK, 26 módulos, 0 ERROR. WARNING:
  - «skip retired unlink… (no skill files on disk)» (×3), informativo;
  - etiquetas de campo repetidas en `ai.log` («Client»: `client_label`/`client_display`, ×3) y en
    `ai.trusted.action` («Model»: `model_name`/`model_id`, ×2): defectos menores del fabricante; observación, sin
    parche.
- **Tests** (`tests`, BD temporal `test_<bd>`, `--test-tags` por módulo): 249 tests, 0 fallos, 0 errores
  (`pns_base` 1, `pns_ai_mcp` 230, `pns_ai_chatboo` 18). Las cifras de `odoo.tests.stats` (3/298/24) cuentan también
  las fases de preparación; el recuento válido es el de las líneas `Starting` o la línea final. Corrió el test de
  intrusión (5 de 5).
- **Omitidos (4), todos por el entorno:**
  - `TestWebClientStarts.test_backend_starts_without_errors`: falta `websocket-client` (y faltaría Chrome);
  - `TestRequiredFieldsLive.test_a_pending_field_is_left_on_the_record_itself`: sin `crm`;
  - dos de `TestSandboxSecretRead` («arrive in Odoo 20»).
- **WARNING de los tests**, a tener en cuenta en los puntos de la sección 8 (ninguno corresponde con claridad a un
  punto concreto):
  - «no read access to res.partner [<id>] for the snapshot»;
  - `DeprecationWarning` en `pns_ai_mcp/utils/field_required_plan.py:69` («use get_combined_arch() instead»);
  - «returns an HTTPException instead of raising it»;
  - «No CSRF validation token provided for path '/chatboo/stream'»;
  - «No X-MCP-LLM or X-MCP-Agent in headers» (×7);
  - «Skill bootstrap failed… MissingError» (~90, de las skills de los tests).
- **Pendiente:**
  1. Imagen propia del laboratorio con `google-chrome-stable` y `websocket-client` (`infra/Dockerfile.17` del
     laboratorio), para el omitido de `pns_base` y el punto 2 (parche 20).
  2. Después, los 8 puntos de la sección 8, con pruebas automatizadas siempre que se pueda.
