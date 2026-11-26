# Clasificación de los parches `pns_ai` para la 17.0.3.1.996

- **Rama:** `17.0-pns-ai`, sobre `27c8045` ([plan](plan_pns_ai_17.md), fase 0).
- **Fecha:** 23/11/2026; la sección 11, del 23 y 24/11/2026. No se ha aplicado ningún parche. Las secciones 1 a 9 son
  de solo lectura; la 10 instala y prueba los tres módulos en el laboratorio `lab_pns_ai_3996`, y la 11 confirma la
  sección 8 con tests en su módulo `seges_pruebas_3996` (copia en `docs/pendiente/lab_3996/`).
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
  - **Imagen propia (segunda ejecución, 23/11/2026):** `odoo-dev:17-lab_pns_ai_3996` (id `1ffc50661ed6`,
    `User=odoo`, etiqueta `odoo-dev.dockerfile-hash=8237290eb74ee2f9`, 5,19 GB; la común, 3,84 GB), construida desde
    `infra/Dockerfile.17` del laboratorio y activada con `DOCKERFILE="infra/Dockerfile.17"` en `.odoo-dev.conf`.
    - `FROM odoo-dev:17` (la común local) y no copia del `Dockerfile.17` del kit: no descarga un `odoo:17.0` nuevo ni
      cambia el core (se conservan `17.0-20260908` y las librerías de la primera ejecución). Si se reconstruye la
      común, la del laboratorio no cambia hasta reconstruirla desde el laboratorio.
    - Dos capas: Google Chrome estable sin versión fija, registrado como `google-chrome` (158.0.8127.36 el 23/11,
      apuntado en el `CLAUDE.md` del laboratorio), y `websocket-client==1.2.3` con `pip3` (la de `python3-websocket`
      de Jammy; Odoo 17 no la declara). Sin `shm_size`: basta `--disable-dev-shm-usage`, que ya pasa Odoo.
    - Como dependencias de Chrome, apt actualizó `libsystemd0` (249.11-0ubuntu3.22 → 3.23) y `libx11-6`
      (2:1.7.5-1ubuntu0.3 → 0.4): no tocan Python ni el core; se aceptan para el laboratorio.
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
  - El total de Odoo («of N tests») incluye los omitidos: los 249 ya contaban los 4. En `tests-20261123-141538.log`
    hay 251 líneas `Starting`, de las que 249 son tests (`odoo.addons.<módulo>.tests`); en `tests-20261123-141429.log`,
    3 y 1. Las otras dos, «Starting post tests» y «Starting enrich of company», no son tests.
  - **Segunda ejecución, con la imagen propia.** Criterio: un test de navegador solo es bueno si tiene línea
    `Starting`, 0 líneas de omisión o de fallo de Chrome, y 0 fallos y 0 errores (Odoo convierte casi todos los
    fallos de Chrome en omisiones: `odoo/tests/common.py` del core `17.0-20260908` (contenedor): 1197, 1258, 1323,
    1343, 1348 y 1875).
    - `tests pns_base` (`tests-20261123-141429.log`): `TestWebClientStarts.test_backend_starts_without_errors` se
      ejecuta y pasa (Chrome arranca, abre `/web`, «test successful»); 0 líneas de omisión o de fallo de Chrome;
      `0 failed, 0 error(s) of 1 tests`; `analizar_log.py` OK. Es el único test de `pns_base`.
    - `tests pns_base,pns_ai_mcp,pns_ai_chatboo` (`tests-20261123-141538.log`): `0 failed, 0 error(s) of 249 tests`,
      OK (`pns_base` 1, `pns_ai_mcp` 230 con 3 omitidos, `pns_ai_chatboo` 18).
    - Al final, `test_lab_pns_ai_3996_17` no existe y `lab_pns_ai_3996_17` sigue.
- **Omitidos (4), todos por el entorno:**
  - `TestWebClientStarts.test_backend_starts_without_errors`: falta `websocket-client` (y faltaría Chrome);
  - `TestRequiredFieldsLive.test_a_pending_field_is_left_on_the_record_itself`: sin `crm`;
  - dos de `TestSandboxSecretRead` («arrive in Odoo 20»).
  - En la segunda ejecución, 3: `TestRequiredFieldsLive` («crm not installed») y los dos de `TestSandboxSecretRead`
    («arrive in Odoo 20»); `TestWebClientStarts` ya no se omite («Tests»).
- **WARNING de los tests**, a tener en cuenta en los puntos de la sección 8 (ninguno corresponde con claridad a un
  punto concreto):
  - «no read access to res.partner [<id>] for the snapshot»;
  - `DeprecationWarning` en `pns_ai_mcp/utils/field_required_plan.py:69` («use get_combined_arch() instead»);
  - «returns an HTTPException instead of raising it»;
  - «No CSRF validation token provided for path '/chatboo/stream'»;
  - «No X-MCP-LLM or X-MCP-Agent in headers» (×7);
  - «Skill bootstrap failed… MissingError» (~90, de las skills de los tests).
  - Además, en la segunda ejecución (los anteriores se repiten igual; los recuentos son de cada log, y `clear_cache`
    solo sale en el de los tres módulos):
    - «A child process was found, terminating it: … chrome_crashpad … zombie» (×2): limpieza normal al cerrar
      Chrome; es nuevo porque antes el test no corría;
    - `DeprecationWarning` «Deprecated model.clear_cache(), use registry.clear_cache() instead» (×1), de
      `pns_ai_mcp/models/mcp_user.py:382` (`_forget_app_menu_cache`); ya salía antes; observación del fabricante, sin
      parche;
    - `FutureWarning` de `urllib3/poolmanager.py:331` (`'strict'`, ×1): del `requests` 2.25.1 de la imagen común, no
      del fabricante;
    - al instalar, sin marca de tiempo (`analizar_log.py` no los cuenta), ×1: `<string>:38: (ERROR/3) Unexpected
      indentation.` y `<string>:43: (WARNING/2) Block quote ends without a blank line…`. No salen del fabricante:
      aparecen al cargar `mail` (10 de 26), antes que los módulos `pns_*` (que además tienen
      `static/description/index.html`), y también con solo `pns_base`; origen sin identificar, sin seguimiento.
- **Pendiente:**
  1. Imagen propia del laboratorio con `google-chrome-stable` y `websocket-client` (`infra/Dockerfile.17` del
     laboratorio), para el omitido de `pns_base` y el punto 2 (parche 20). **Hecho (23/11/2026):** «Montaje» (imagen
     propia) y «Tests» (segunda ejecución).
  2. Después, los 8 puntos de la sección 8, con pruebas automatizadas siempre que se pueda. **Hecho (24/11/2026):**
     resultados en la sección 11.

## 11. Resultado de la sección 8 (23 y 24/11/2026)

### Punto 8: citas del core

- **Método:** solo lectura. Origen: `git show 6a0efa7:<ruta>` en `/opt/odoo-src/17.0/odoo`, que es el repo del core
  dentro de la referencia (clon superficial de un solo commit; `/opt/odoo-src/17.0` no es un repo). Contenedor: un solo
  `docker run --rm`, sin volúmenes, de `odoo-dev:17-lab_pns_ai_3996`, que lee `/usr/lib/python3/dist-packages/odoo/`
  (`odoo/…` sin el prefijo; `odoo/addons/…` y `addons/…`, bajo `addons/`). Se compara el texto de las líneas citadas
  sin los espacios del final; la sangría cuenta. Las citas abreviadas se atribuyen por el contexto (`:215`, `:180`,
  `res_partner.py:91…`, `iap_account.py:182`…); `base_partner_merge.py` es el de `odoo/addons/base/wizard/`, el único
  de los cuatro que tiene esos métodos.
- **Core del contenedor:** `release.py`, `version_info = (17, 0, 0, 'final', 0, '')` y `version = '17.0-20260908'`.
- **Inventario:** 51 citas del core de la 17 en 28 archivos, que existen todos en el contenedor: 45 de las secciones 4
  y 6, y las 6 de `odoo/tests/common.py` de la sección 10. No se comparan 32 citas del código `pns_*` ni 2 de P14
  (`seges_box_a_cache.py`). Ninguna es ambigua. Tampoco son citas del core las líneas 242–273 del índice de la 14,
  `urllib3/poolmanager.py:331` (librería de la imagen) ni `<string>:38` y `:43` (mensajes del log).
- **Resultado:** 45 iguales y 6 desplazadas; ninguna distinta ni ausente. Los 27 archivos de las secciones 4 y 6 son
  idénticos enteros en los dos sitios.
- **Las 6 desplazadas** son las de la sección 10. Ya se tomaron del contenedor y allí son correctas. En `6a0efa7` el
  mismo texto está 14 líneas más abajo; `6a0efa7` es del 05/10/2026, posterior al core del contenedor (08/09/2026), y
  la referencia no tiene historia para saber qué commit lo desplazó:

  | Línea | Cita (contenedor) | Texto | En `6a0efa7` |
  |---|---|---|---|
  | 330 | `odoo/tests/common.py:1197` | `SkipTest(f'Failed to detect chrome devtools port after …')` | 1211 |
  | 330 | `odoo/tests/common.py:1258` | `SkipTest("%s not found" % cmd[0])` | 1272 |
  | 330 | `odoo/tests/common.py:1323` | `SkipTest("Error during Chrome headless connection")` | 1337 |
  | 331 | `odoo/tests/common.py:1343` | `SkipTest("Error during Chrome connection: never found 'page' target")` | 1357 |
  | 331 | `odoo/tests/common.py:1348` | `SkipTest("Cannot connect to chrome dev tools")` | 1362 |
  | 331 | `odoo/tests/common.py:1875` | `SkipTest("Chrome executable not found")` | 1889 |

- **Conclusión:** no hay correcciones. Las citas del core de las secciones 4 y 6, tomadas de `6a0efa7`, valen tal
  cual para el core del laboratorio (`17.0-20260908`), y las de la sección 10 ya eran del contenedor. Si una cita
  nueva sale de la referencia, hay que confirmarla igualmente: en `odoo/tests/common.py` las dos versiones difieren.

### Punto 2: `window.Chart` (parche 20)

- **Método:** test de navegador (`HttpCase.browser_js`, Chrome headless) en el módulo de pruebas del laboratorio,
  `seges_pruebas_3996` (`~/GitHub/lab_pns_ai_3996/seges_pruebas_3996/`, fuera del repo; copia en
  `docs/pendiente/lab_3996/seges_pruebas_3996/`, idéntica (mismo `sha256sum`) a lo que se ejecutó; el manifest se
  guarda como `__manifest__.py.txt` para que ni el kit ni los linters la tomen por un módulo (hay que renombrarlo para
  ejecutarla)), con `depends` `web` y `pns_ai_chatboo`. Archivo `tests/test_chart_collision.py`, clase
  `TestChatbooChartCollision`. Cada test abre `/web` en una página nueva y carga las dos librerías con el código real:
  `loadBundle("web.chartjs_lib")` de `@web/core/assets` (Odoo) y `loadHeavyLibs()` de
  `@pns_ai_chatboo/js/chatboo_heavy_libs` (la llamada de `chatboo_overlay.js:120` al abrir el chat). Comprueba que
  `window.Chart` es el objeto de Odoo, que su adaptador de fechas es `luxon` y que pinta un gráfico con eje
  `type: "time"`. Cada fallo lleva una etiqueta, `[HYPOTHESIS]` (lo que se comprueba) o `[SETUP]` y `[ERROR]` (el test
  no vale), y termina con la versión y el adaptador de `window.Chart` encontrados.
  - `test_chat_after_odoo_keeps_odoo_chart`: primero el Chart.js de Odoo y después las librerías del chat.
  - `test_chat_before_odoo`: el orden inverso, como testigo de que las comprobaciones no dan falsos rojos.
- **Mecanismo** (core `17.0-20260908`, contenedor): `assets.loadJS` y `assets.getBundle` están memorizados
  (`addons/web/static/src/core/assets.js:30` y `:98`); el UMD de Chart.js 4.4.8 (`chart.umd.min.js`) escribe
  `globalThis.Chart` porque en la 17 no hay `define.amd`; `chartjs-adapter-luxon` se registra sobre el `window.Chart`
  que exista al cargarse (`addons/web/static/lib/chartjs-adapter-luxon/chartjs-adapter-luxon.js:31`). Gana el último
  que carga, y ninguno de los dos vuelve a cargar en la misma página.
- **Ejecución (23/11/2026):** desde el laboratorio, `odoo-dev 17 arrancar` (regenera el `addons_path` con
  `/mnt/cliente/lab_pns_ai_3996`), `paridad seges_pruebas_3996` (se puede instalar, 0 problemas) y
  `tests seges_pruebas_3996` (BD temporal `test_lab_pns_ai_3996_17`). Log `tests-20261123-165834.log`. Chrome
  158.0.8127.36 (`Browser version: Chrome/158.0.8127.36`); es Google Chrome estable sin versión fija, así que puede
  cambiar si se reconstruye la imagen.
- **Resultado:** `1 failed, 0 error(s) of 2 tests`; 2 líneas `Starting`; 0 omisiones y 0 fallos de Chrome;
  `analizar_log.py` da `FALLO`, que es lo esperado.
  - `test_chat_after_odoo_keeps_odoo_chart`, rojo en 5,5 s (timeout de 120 s): `[HYPOTHESIS] window.Chart was
    replaced: expected Odoo's Chart.js 4.3.0 with luxon | found: Chart.js 4.4.8, date adapter undefined`.
  - `test_chat_before_odoo`, verde en 3,0 s (`test successful`).
  - Ningún otro `console.error`, `console.warn` ni excepción de la página. Los únicos WARNING son el `FutureWarning`
    de `urllib3/poolmanager.py:331` (sección 10) y 4 procesos `chrome_crashpad` zombis al cerrar Chrome (2 por cada
    arranque, como en la sección 10).
- **Conclusión:** confirmado. Si el chat se abre después de que Odoo haya cargado `web.chartjs_lib` en la misma página
  (por ejemplo, tras abrir una vista de gráficos), `window.Chart` pasa a ser el Chart.js 4.4.8 del chat, sin
  adaptador de fechas, hasta que se recarga la página. En el orden inverso no pasa nada: Odoo vuelve a escribir su
  Chart.js con luxon y el chat conserva el suyo (`bindEngines`, `chatboo_charts.js:40-47`).
- **Alcance real:** la vista de gráficos de la 17 no usa ejes de fecha (no hay `type: "time"` en
  `addons/web/static/src/views/graph/`); usa el global `Chart` (`graph_renderer.js:63` y `:708`), así que se pintaría
  con 4.4.8 en lugar de 4.3.0. El único del core con ejes de fecha es `spreadsheet`
  (`addons/spreadsheet/static/src/o_spreadsheet/o_spreadsheet.js:8228-8240`): sin luxon escribe un `console.warn` y
  desactiva los ejes de tiempo, sin error visible. Es una degradación silenciosa. No se ha probado con una vista de
  gráficos real ni con `spreadsheet` (decisión de Sergio).
- **Impacto en el port del parche 20:** el parche hace falta en la 17. `test_chat_after_odoo_keeps_odoo_chart` es su
  test de aceptación: con el parche tiene que pasar a verde, y `test_chat_before_odoo` tiene que seguir en verde. En
  la fase 2 del plan, los dos tests pasan a `pns_ai_chatboo` junto con el parche.

### Puntos 3 y 4: revisión de importación y vistas sin Ajustes (parches 21 y 36)

- **Método:** dos `TransactionCase` en `seges_pruebas_3996` (el módulo del punto 2, con la misma copia en
  `docs/pendiente/lab_3996/`), adaptados de los tests de la 14 (`14.0:pns_ai_mcp/tests/`:
  `test_seges_import_preview.py`, de `bc699e7`, y `test_seges_review_views.py`, de `a9e348b`). Los `depends` pasan a
  `web`, `pns_base`, `pns_ai_mcp` y `pns_ai_chatboo`. Cada fallo lleva una etiqueta: `[HYPOTHESIS]`, `[SETUP]` o
  `[GUARD]` (lo que debe cumplirse con el parche y sin él); una excepción inesperada sale como error.
  - `tests/test_import_review.py`, clase `TestImportReview` (punto 3): pulsa «Review» (`action_preview`) en los
    asistentes de usuarios y de servidores, simula el final de la petición con `env.flush_all()` y lee la fila con SQL
    directo: el valor y el `ctid`, que cambia con cada `UPDATE` y vuelve tras `ROLLBACK TO SAVEPOINT` (`write_date` no
    sirve: `now()` es constante en la transacción del test). Antes comprueba (`[SETUP]`) que la importación se ejecutó
    dentro de «Review».
  - `tests/test_review_views.py`, clase `TestReviewViews` (punto 4): pide las dos pantallas con `get_view` y solo
    `form_view_ref`, como el cliente de la 17, con dos AI Administrator sin Ajustes (con y sin
    `base.group_erp_manager`), en los asistentes de usuarios y de servidores. Antes de cada lectura invalida la caché de
    las dos vistas: `arch` es un campo calculado no almacenado y la caché es común a todos los usuarios.
- **Ejecución (23/11/2026):** desde el laboratorio, `paridad seges_pruebas_3996` (se puede instalar, 0 problemas) y
  `tests seges_pruebas_3996` (BD temporal `test_lab_pns_ai_3996_17`, que no queda). Log `tests-20261123-172135.log`.
- **Resultado:** `8 failed, 0 error(s) of 12 tests`; `analizar_log.py` da `FALLO` y todas sus causas son
  `[HYPOTHESIS]`. Ningún `[SETUP]`, `[GUARD]` ni error; los WARNING son los mismos que en el punto 2. El punto 2 sale
  igual: `test_chat_after_odoo_keeps_odoo_chart` en rojo (`[HYPOTHESIS] … Chart.js 4.4.8, date adapter undefined`),
  `test_chat_before_odoo` en verde (`test successful`); Chrome 158.0.8127.36, 0 omisiones y 0 fallos de Chrome.

  | Test | Resultado | Detalle |
  |---|---|---|
  | `test_users_review_writes_nothing` | rojo | `('(0,2)', None)` → `('(0,5)', 'seges-3996-p21')` (`ctid`, etiqueta) |
  | `test_providers_review_writes_nothing` | rojo | `('(0,2)', 0.7)` → `('(0,3)', 0.42)` (`ctid`, temperatura) |
  | `test_users_review_keeps_groups` | rojo | Sin fila en `res_groups_users_rel`, pero `has_group` sigue en `True` |
  | `test_import_still_applies` | verde | `[GUARD]`: la importación sí escribe el campo |
  | `test_precondition_screens_not_readable` | verde | `AccessError` al leer `arch` de las dos vistas sin Ajustes |
  | `test_admin_gets_review_screen` | rojo | `AccessError` en `ir.ui.view`: 2 usuarios × 2 asistentes |
  | `test_admin_gets_result_screen` | rojo | Lo mismo con la pantalla de resultado |
  | `test_admin_users_review_and_result` | rojo | «Review» e importación funcionan; fallan las 2 pantallas, 2 usuarios |
  | `test_admin_servers_review_and_result` | rojo | Lo mismo en servidores |
  | `test_non_admin_still_refused` | verde | `[GUARD]`: sin AI Administrator no abre las pantallas ni el asistente |

- **Conclusión, parche 21:** confirmado en los dos asistentes; ninguno «no aplica». Lo que la importación deja
  pendiente (`import_users_wizard.py:101`, `import_servers_wizard.py:110`) lo escribe el `invalidate_all()` de
  `operation_report_wizard.py:295`, después del `ROLLBACK TO SAVEPOINT` (`:324`), y queda. Los grupos sí se deshacen en
  la BD (`_inverse_ai_group_flag` vuelca dentro del savepoint), pero `has_group` sigue en `True` después de «Review»:
  el ormcache (`res_users.py:1098`) guarda la respuesta de dentro del savepoint y nadie lo limpia.
- **Conclusión, parche 36:** confirmado. Un AI Administrator sin Ajustes, con o sin «Permisos de acceso», recibe
  `AccessError` en `ir.ui.view` al abrir la pantalla de revisión y la de resultado de los dos asistentes, aunque la
  importación en sí funciona. Sin el parche, solo `base.group_system` ve esas pantallas.
- **`config_backup_wizard` (leído, no probado):** su `action_preview`
  (`pns_ai_mcp/wizard/config_backup_wizard.py:109-126`) no usa savepoint ni el del mixin: llama a
  `config_backup.import_config(…, dry_run=True)`, y en cada sección `_should_write`
  (`pns_ai_mcp/utils/config_backup.py:105-114`) devuelve `False` en `dry_run` antes de cualquier `write` o `create`
  (`:507-510`, `:549-552`, `:579-582`, `:604-607`, `:646-647`, `:700-703`, `:743-746`, `:774-775`); la segunda pasada
  se salta (`:353`) y los ajustes solo se leen (`:883-907`; no se ha leído `resolve_import_overlay`). No tiene el fallo
  del parche 21. Sí tiene el del 36: abre las mismas pantallas (`_apply_import_preview` y `_apply_operation_result`,
  `config_backup_wizard.py:119` y `:137`), que pasan por `_inject_screen_arch`.
- **Cita desplazada:** en la sección 4 (L158-159, parche 36), `:327-342` y `:331` son `:329-342`
  (`_inject_screen_arch`) y `:332-333` (`self.env.ref(xmlid)` y `src.arch`). Se anota aquí; la sección 4 no se
  corrige.
- **Impacto en el port:**
  - Parche 21: hace falta. Orientación para el port (se decide en la fase 2): que no quede nada pendiente al hacer el
    `ROLLBACK TO SAVEPOINT` (volcar dentro del savepoint), invalidar después sin volcar (`invalidate_all(flush=False)`:
    la caché aún tiene los valores de dentro, ya deshechos en la BD, y el `invalidate_all()` normal es el que los
    escribe) y limpiar el ormcache con `registry.clear_cache()` (`clear_caches()` no existe en la 17).
    `TestImportReview` es su test de aceptación: los 3 rojos pasan a verde y el `[GUARD]` sigue en verde.
    Decidido en la fase 2 (24/11/2026): esta orientación la sustituye la decisión 153 de
    `docs/pendiente/fase2_pns_ai_17_3996.md` (la semántica de `_FlushingSavepoint`; registro en su sección 7).
  - Parche 36: hace falta. `_inject_screen_arch` tiene que leer la vista con `sudo()` (`:332-333`); `src` también se
    usa en `postprocess_and_fields` (`:337`), y el test dirá si basta. `TestReviewViews` es su test de aceptación: los 4
    rojos pasan a verde y los dos verdes siguen igual. El parche cubre también `config_backup_wizard`, que pasa por el
    mismo `_inject_screen_arch`; el test no lo prueba.
  - En la fase 2 del plan, los dos archivos pasan a `pns_ai_mcp` (donde estaban en la 14) junto con los parches.

### Punto 5: cursores aparte (parches 37 y 38)

- **Método:** `tests/test_side_cursors.py` en `seges_pruebas_3996` (copia en `docs/pendiente/lab_3996/`), adaptado de
  `14.0:pns_ai_mcp/tests/test_seges_box_a_flush.py` (`42432dc`) y `test_seges_side_cursor_commit.py` (`348fa2d`). Sin
  cambios en el manifest. Mismas etiquetas que en los puntos 2 a 4.
  - **`TransactionCase` a propósito:** fuera del modo test, `registry.cursor()` da un `Cursor` real en otra conexión
    (`odoo/modules/registry.py:931-938`), como en producción. En `HttpCase` sería un `TestCursor` sobre la conexión del
    test (`odoo/sql_db.py:540-598`): su `rollback` es `ROLLBACK TO SAVEPOINT`, que deshace también lo que el llamador
    haya volcado después, y el `READ ONLY` de la caja A caería en la transacción compartida.
  - **Qué no reproduce:** la petición HTTP o el worker; el llamador es la transacción del test. Los `commit` del cursor
    aparte son reales: solo filas nuevas con etiqueta en `ai_log` y `ai_api_result_cache`, que se borran con SQL en
    otro cursor en la limpieza.
  - **Prueba de que el escenario se dio:** un espía de `registry.cursor()` comprueba (`[SETUP]`) que los cursores son
    `Cursor` reales, que hubo `rollback` o `commit` y que en el primero lo pendiente del llamador seguía ahí. Un
    `[SETUP]` en `setUp` comprueba que el registro no está en modo test.
- **Clases y casos:**
  - `TestBoxACallerPending` (37), por la herramienta real (`tool_relaxaicode`; cursor en `controller_helpers.py:189`,
    `rollback` y `close` en `tools_relaxaicode.py:273-279`): escritura pendiente, cálculo pendiente (`complete_name`),
    lectura en la caja A de una columna pendiente del llamador (condición a; `[GUARD]`: la caja A lee el valor de la
    BD) y caché y `new()` del llamador.
  - `TestSideCursorCommit` (38): `ai.log` (`ai_log.py:731-858`) con E1 y E2, y `ai.api.result.cache._store`
    (`api_result_cache.py:132`) con E3 (fila bloqueada por el llamador, `lock_timeout` de 3 s en los cursores
    vigilados) y E4 (caché y `new()`).
  - **Salto del `flush_all()` del fabricante en E1 y E2:** `ai_log.py:721-730` vuelca lo del llamador antes de abrir el
    cursor (arreglo para la 14). Se salta solo durante la llamada y solo en el cursor del llamador, para que el `commit`
    aparte encuentre lo pendiente, como en 3.1.973.
  - **`test_log_as_shipped_keeps_caller_write`:** `ai.log` tal como viene, con su `flush`; no se exige nada pendiente
    en el `commit` aparte.
  - **Descartados:** `test_box_a_open_flush_error_no_cursor` (prueba el `flush` del 37), el E3 completo con plan
    confirmado (lo cubre E3 sobre `_store`) y `TestSegesSideEnv` (prueba `seges_side_env.py`).
- **Ejecución (23/11/2026):** `paridad seges_pruebas_3996` (se puede instalar, 0 problemas) y `tests
  seges_pruebas_3996` (BD temporal `test_lab_pns_ai_3996_17`, que no queda). Log `tests-20261123-175740.log`.
- **Resultado:** `8 failed, 0 error(s) of 21 tests`. Los 8 rojos son los `[HYPOTHESIS]` de los puntos 2, 3 y 4, los
  mismos que en `tests-20261123-172135.log`. Los 9 nuevos, en verde. ERROR y WARNING iguales a los de ese log (salvo el
  recuento y los `pid` de Chrome); 0 «store failed», 0 esperas por bloqueo y 0 errores en la limpieza.

  | Test | Resultado |
  |---|---|
  | `TestBoxACallerPending.test_pending_write_survives_box_a_close` | verde |
  | `TestBoxACallerPending.test_pending_compute_survives_box_a_close` | verde |
  | `TestBoxACallerPending.test_box_a_reads_column_pending_in_caller` | verde |
  | `TestBoxACallerPending.test_box_a_close_keeps_caller_cache_and_new` | verde |
  | `TestSideCursorCommit.test_log_does_not_commit_caller_pending_write` (E1) | verde |
  | `TestSideCursorCommit.test_log_keeps_pending_write_on_new_record` (E2) | verde |
  | `TestSideCursorCommit.test_log_as_shipped_keeps_caller_write` | verde |
  | `TestSideCursorCommit.test_store_does_not_wait_for_caller_locked_row` (E3) | verde |
  | `TestSideCursorCommit.test_store_keeps_caller_cache_and_new` (E4) | verde |

- **Conclusión, parche 37:** no aplica (confirmado). El `rollback` y el `close` de la caja A solo vacían la
  `Transaction` de su cursor (`odoo/api.py:518-520`, `odoo/sql_db.py:490-492`): la escritura y el cálculo pendientes,
  la caché y los `new()` del llamador siguen, y la caja A lee de la BD sin intentar volcar nada en el cursor
  `READ ONLY`.
- **Conclusión, parche 38:** no aplica (confirmado). El `commit` de un cursor aparte solo vuelca su `Transaction`
  (`odoo/sql_db.py:481`): no confirma fuera lo pendiente del llamador, no lo pierde en registros creados por él, no
  espera filas que el llamador tiene bloqueadas y no le vacía la caché. Con el `flush` del fabricante, la escritura
  del llamador tampoco sale de su transacción.
- **Alcance:**
  - **probados con cursor real:** la caja A (37), `ai.log` y la caché de API (38);
  - **leídos y no probados**, porque usan el mismo patrón (cursor propio con `registry.cursor()` y `Environment`
    propio, sin volcar lo del llamador): `ai.change.journal` (`_record_failed_plan`, `ai_change_journal.py:398-399`)
    y `chatboo.session` (`_store_design`, `_store_title` y `_store_documents`, `chatboo_session.py:1011`, `:1048` y
    `:1415`). `_store_documents` no estaba en la tabla de aperturas del 38 de la 14;
  - **localizados y no leídos:** las demás aperturas de los archivos de la sección 3 (L56-L82) solo se han localizado
    con `git grep` (`controllers/safe_plan.py:310` y `:409`, `models/ai_skill_param_cache.py:146`,
    `models/key_pin_desk.py:198` y `:222`, `models/safe_operation.py:696`, `:966`, `:1085`, `:1253`, `:1308` y
    `:1590`, `utils/engine_tool_run.py:547`, `utils/field_required_plan.py:248` y `utils/session_download.py:382`,
    todas en `pns_ai_mcp`). No se ha leído su código, así que no se da por comprobado que sigan el mismo patrón.
- **Punto 6 (parche 29), predicción:** la 17 aísla al llamador como la 14 con el 38, así que la adaptación con
  `flush()` de `test_edit_page_without_data` sigue haciendo falta: la escritura de la sesión del test queda pendiente
  y pisaría lo que guarda `_store_design`. Sus tests tienen que seguir en modo test (`HttpCase`): un cursor real no ve
  la sesión del test. Se espera verde con `flush()` y los 3 subtests en rojo sin él, como en 3.1.973.
- **Impacto en el port:** los parches 37 y 38 no se portan; `pns_base/utils/seges_side_env.py` tampoco. La decisión
  se apoya en el mecanismo del core, que vale para cualquier cursor con su propio `Environment`. En la fase 2 se
  revisan las aperturas localizadas y no leídas, por si alguna vuelca o invalida al llamador por su cuenta. El `flush`
  del fabricante en `ai_log.py:721-730` no hace falta en la 17, pero no estorba y se deja.

### Punto 1: caché de secretos en la caja A (parche 18)

- **Qué se buscaba:** si sigue en la 17 el fallo de partida del 18 (un valor en caché se lee sin comprobar) y si la
  invalidación de la parte B pierde lo pendiente del llamador (sección 8, punto 1). Tres casos:
  - (a) la caché de la caja A al abrirse y lo pendiente del llamador. En la 14 la caché era una por hilo: B la vaciaba
    al abrir la caja A (`controller_helpers.py:224-246`, con `_seges_forget_secret_columns` de
    `utils/seges_box_a_cache.py`; `_box_a_clear_cache`, `models/box_a_guard.py:48-63`, era de la rama 3879), y
    NUEVO-1 (PNS-108) era el secreto que el motor dejaba en ella antes de la caja A;
  - (b) un secreto que el código del fabricante lee con `sudo()` dentro de la caja A y que el código del usuario lee
    después;
  - (c) los secretos del core que en la 17 son calculados no guardados, sin caché de por medio.
- **Mecanismo en la 17 (leído en el contenedor, `17.0-20260908`):**
  - el guardián del fabricante solo actúa al ir a la BD: `Field.__get__` → `_fetch_field` →
    `check_field_access_rights` (`odoo/fields.py:1176-1190`, `odoo/models.py:3809` y `:3470`; con `su` sale sin mirar,
    `:3482-3483`), donde engancha `pns_ai_mcp/models/sandbox_secret_read.py:116-126`;
  - un valor que ya está en la caché se devuelve sin comprobar (`odoo/fields.py:1152-1154`), y un campo calculado no
    guardado se calcula sin comprobar (`:1209-1231`);
  - un cursor nuevo no tiene `Transaction` (`odoo/sql_db.py:132`) y el primer `Environment` crea una, con su caché
    (`odoo/api.py:518-520`): la caja A (`controller_helpers.py:189` y `:211`) no comparte caché con el llamador, pero
    un `sudo()` sobre su `env` comparte la de la caja A;
  - `Cache.invalidate` quita el valor y deja la marca de pendiente (`odoo/api.py:1292-1319`, aviso en `:1300-1302`).
- **Método:** `tests/test_box_a_secret_cache.py` en `seges_pruebas_3996` (copia en `docs/pendiente/lab_3996/`). Los
  `depends` suman `auth_signup` y `auth_totp` (los campos de (c)); `_StubController` y `_CursorSpy` se importan de
  `test_side_cursors.py`. Mismas etiquetas que en los puntos anteriores.
  - **`TransactionCase` `post_install` con cursores reales**, como el punto 5 (`[SETUP]`: registro fuera de modo test).
  - **Datos:** en cada test, filas nuevas con etiqueta (`seges_3996_p18_` y 8 hexadecimales), confirmadas en un
    cursor aparte: dos usuarios internos (`asker`, solo `base.group_user`, y `target`), un contacto, un
    `ai.api.server` y el `ai.mcp.user` del `target`, con secretos aleatorios. El servidor va sin URL, así que no crea
    fila en `ai.url.whitelist` (`external_server.py:932-950`), y confirma su fila de detección en `ai.context`
    (`external_server.py:563` → `:821-878`), que se borra en cascada (`ai_context.py:212-216`).
  - **El llamador** (la petición) va en otro `Cursor` real, abierto después de ese `commit`: el del test no vería las
    filas (su instantánea es anterior). La herramienta real (`tool_relaxaicode`) corre como `asker` sobre él.
  - **Limpieza:** antes de sus aserciones, cada test borra las filas en un tercer cursor con `commit` (también
    `ai.context`, `mail_message` y `mail_followers` de esos ids), y un `[GUARD]` comprueba por SQL que no queda
    ninguna, `ai_url_whitelist` incluida.
  - **Secretos:** no se imprimen nunca. El código de la caja A devuelve una huella (16 hexadecimales de SHA-256) y el
    test compara huellas. Solo cuenta como rechazo el texto exacto del guardián del campo
    (`sandbox_secret_read.py:39-45`, lanzado en `:75-76`); el de la puerta de modelos (`validators_base.py:407-413`) y
    el de los parámetros (`sandbox_secret_read.py:46-51`), que comparten el prefijo, dan `[SETUP]`.
  - **Lo que confirma la herramienta (leído):** nada fuera de la caja A. El registro pasa por
    `controller._log_mcp_operation` (`relaxaicode_replies.py:86-102`), que el stub no implementa; los cursores propios
    de Chatboo (`chatboo_session.py:1011`, `:1048` y `:1415`) solo se abren si el código llama a sus helpers de página
    o de adjuntos. El espía de cursores lo comprueba en cada ejecución (`[SETUP]`: 0 `commit`).
- **Clases y casos:**
  - `TestBoxACacheAtOpening` (a): qué hay en la caché de la caja A al abrirse (`[HYPOTHESIS]` solo si hay alguna
    columna secreta o algún valor del llamador; lo demás se anota en el log) y lo pendiente del llamador al abrir y al
    cerrar (pendiente, volcado, que es `[SETUP]`, o perdido); el token que el llamador leyó con `sudo()` (NUEVO-1);
    la parte B de la 14 simulada al abrir; y el `[GUARD]` de `Cache.invalidate` sobre la caché del llamador.
  - `TestBoxASecretReadInside` (b): en cada test, un control sin la vía (rechazo del guardián, `[SETUP]`), la vía sola
    (se alcanza, `[SETUP]`) y la vía seguida de la lectura del secreto.
  - `TestBoxAComputedSecret` (c): un control con un campo no secreto del mismo registro (`login`, `name`; `[SETUP]`
    por su huella) y la lectura del secreto.
- **Ejecución (23/11/2026):** `paridad seges_pruebas_3996` (se puede instalar, 0 problemas; `auth_signup` y
  `auth_totp` ya estaban instalados) y `tests seges_pruebas_3996` (BD temporal, que no queda). Log
  `tests-20261123-184040.log`.
- **Resultado:** `13 failed, 0 error(s) of 30 tests`: los 8 rojos de los puntos 2, 3 y 4, los mismos que en
  `tests-20261123-175740.log`, y 5 `[HYPOTHESIS]` nuevos. Ningún `[SETUP]` ni error; el `[GUARD]` de filas, en verde
  en los 9. 0 secretos en el log. WARNING nuevos: 6 «Large result JSON» de la herramienta y un `DeprecationWarning`
  de `clear_cache` (`pns_ai_mcp/models/mcp_user.py:376` → `:382`, por el `write` del `ai.mcp.user` al preparar los
  datos; la observación del fabricante de la sección 10).

  | Test | Resultado | Detalle |
  |---|---|---|
  | `test_box_a_opens_without_secret_or_caller_values_in_cache` | verde | Caché vacía; lo pendiente sigue al cerrar |
  | `test_caller_cached_token_not_readable_in_box_a` | verde | NUEVO-1 no ocurre: rechazo del guardián |
  | `test_simulated_b_keeps_caller_pending_secret_write` | verde | B no toca al llamador; su `flush` escribe |
  | `test_invalidating_the_callers_cache_drops_its_pending_value` | verde | `[GUARD]`: sin el valor, con la marca |
  | `test_v1_auth_call_preview_then_token` | rojo | Tras `auth_call_preview`, sale la huella del token |
  | `test_v2_user_has_mcp_api_key_then_hash` | rojo | Tras `user_has_mcp_api_key`, sale la huella del hash |
  | `test_synthetic_engine_sudo_read_before_code` | rojo | Sintético: lectura con `sudo()` al abrir; sale la huella |
  | `test_core_totp_secret_without_cache` | rojo | `totp_secret` sale sin caché |
  | `test_core_signup_token_without_cache` | rojo | `signup_token` sale sin caché |

  - **Caché de la caja A al abrirse:** vacía. Transacción y caché propias, 0 campos pendientes, 0 cálculos pendientes,
    ninguna columna secreta, ningún valor del llamador y nada más.
- **Vías reales del caso (b) (leídas y probadas):**
  - V1: `ai.api.server.auth_call_preview` (`external_server.py:211-216`, calculado en `:383-386`) lee
    `self.sudo().auth_token` (`:393`);
  - V2: `ai.mcp.user.user_has_mcp_api_key` (`mcp_user.py:314-322`) busca con `sudo()` (`:318`) y lee
    `mcp_api_key_hash` (`:319`);
  - el usuario llega a los dos registros con `mail.template.preview.new({'resource_ref': …}).resource_ref`, que salta
    la puerta `RELAXAICODE_CREDENTIAL_MODELS` (`validators_base.py:189-206`; ya anotado en la 14:
    `docs/pendiente/parches_pns_ai.md:4754`), y lee el secreto con `rec['campo']`. El atributo literal
    `.auth_token` sí se rechaza por nombre (`validators_base.py:217`).
- **El motor, sin lecturas de secretos (leído):** se buscó `sudo` con `git grep` en
  `pns_ai_mcp/controllers/tools_relaxaicode.py`, `relaxaicode_*.py` y `context_builder.py`, y en
  `pns_ai_mcp/utils/sandbox_helpers.py`, `name_affinity.py` y `field_selection.py`; y `token|secret` en
  `pns_ai_chatboo/models/chatboo_session.py` y `chatboo_canvas.py`. En lo leído, el motor no lee ninguna columna
  secreta con `sudo()` sobre el `env` de la caja A, antes ni durante el código: `web.base.url`
  (`context_builder.py:677`), `env.user` y `env.company` (`:659-660`, `:781-785`), los helpers de Chatboo
  (`sandbox_helpers.py:63-70` → `chatboo_session.py:831-861`; `_read_attachment` lee con `with_user`, `:1349`), y
  `field_selection` y `search_by_affinity`, sin `sudo`. La conclusión vale para lo leído. El caso sintético
  representa el de B2: un helper que leyera un secreto con `sudo()`.
- **Caso (c) (leído y probado):** `res.users.totp_secret` (`groups=NO_ACCESS`) y `res.partner.signup_token`
  (`base.group_erp_manager`) son calculados no guardados que leen por SQL (`addons/auth_totp/models/res_users.py:24` y
  `:177-183`; `addons/auth_signup/models/res_partner.py:27` y `:55-58`). Leerlos los calcula sin pasar por
  `_fetch_field`. `totp_enabled` y `signup_valid` los leen con `sudo()` (`res_users.py:69-72`,
  `res_partner.py:38-43`).
- **Conclusión:**
  - (a) en la 17 la caja A nace con caché propia y vacía: NUEVO-1 lo cierra el core, B no tiene nada que vaciar y, al
    tocar solo la caché de la caja A, no puede perder lo pendiente del llamador. El riesgo de la sección 4 (parche 18)
    solo existiría si B alcanzara la caché del llamador, como mide el `[GUARD]`;
  - (b) el fallo de partida sigue: lo que el código del fabricante lee con `sudo()` dentro de la caja A queda en su
    caché y el código del usuario lo lee sin comprobación. B2 no cierra V1 ni V2, que no son helpers;
  - (c) los secretos calculados del core se leen sin comprobación aunque no haya nada en caché.
- **Decisión 29 (Sergio, 23/11/2026):** sin invalidación B. El parche 18 se porta como O1 ampliado (comprobar al leer
  también con el valor en caché y en los calculados no guardados), con B2 como defensa. Los enganches de O1 van sobre
  lo que existe en el core del contenedor (`check_field_access_rights`, `Field.__get__`, el cálculo de los no
  guardados), no sobre los ganchos «Odoo 17+» del guardián (ver «Al margen»).
- **Impacto en el port:**
  - Tests de aceptación: `TestBoxASecretReadInside` y `TestBoxAComputedSecret` pasan de rojo a verde, y
    `TestBoxACacheAtOpening` sigue en verde.
  - Al pasar los tests de aceptación a `pns_ai_mcp`, `_StubController` y `_CursorSpy` (hoy importados de
    `test_side_cursors.py`, que no se porta) van con ellos.
  - Tests de la 14 (`14.0:pns_ai_mcp/tests/`, `test_seges_box_a_vias.py` y `test_seges_sandbox_credentials.py`, de
    `42432dc`):
    - **adaptados ya** en este punto: V1 y V2 (`*_reachable`, `*_control_getitem_refused` y `*_getitem`) en (b); V3 y
      V4 en (c), donde su control sin cálculo deja de ser control; `test_box_a_engine_cache_before_run` en (a), con
      una fila confirmada en vez de `new()`; y `test_helper_sudo_read_forgotten` en el caso sintético;
    - **para el port:** de `test_seges_box_a_vias.py`, `*_mapped`, `test_decision2_*`, `test_o1_*` (negativos y
      positivos), `test_v3_recordset_as_result`, `test_v1_literal_attr_refused` y los de P-22; de
      `test_seges_sandbox_credentials.py`, `TestSegesSandboxCredentials` (sin la B de `_mark()`),
      `TestSegesOutsideBoxA` y, de `TestSegesBoxAReal`, `test_box_a_reference_secret_refused`,
      `test_sandbox_cannot_reach_sudo`, `test_box_a_cannot_lift_mark` y `test_box_a_cursor_is_marked`;
    - **descartados:** `test_b_open_forgets_secret`, `test_b_open_keeps_non_secret` y
      `test_box_a_icp_cache_before_run`, que miden B; y `test_computed_secret_column_refused` (`password`), que (c)
      sustituye con secretos reales.
- **Al margen:**
  - **Ganchos «Odoo 17+» del guardián (leído):** `_has_field_access` y `_check_field_access`
    (`sandbox_secret_read.py:100-113`) no existen en el core 17.0 del contenedor (no hay ningún `def` con esos nombres
    en `odoo/models.py`). En la 17 protege el gancho comentado como «Odoo 14», `check_field_access_rights`
    (`:116-126`), que es el que llama `_fetch_field`.
  - **Caja A con uid 1 (localizado, no probado):** si el `env` del llamador es del uid 1, el `Environment` de la caja A
    pasa a `su` (`odoo/api.py:507-508`) y el guardián se apaga (`_pns_sandbox_reads`, `sandbox_secret_read.py:69-70`).
    En el port hay que revisar quién puede abrir la caja A con el uid 1.

### Punto 7: métodos con efectos frente al core de la 17 (parches 22 y 39)

- **Qué se buscaba:** si los nombres de los parches 22 y 39 siguen existiendo y llegando a su efecto en la 17, y si
  hay públicos nuevos con efectos fuera de la caja A (sección 8, punto 7). Solo lectura; el test va a la fase 2 del
  plan, con el port.
- **Criterio (el de la 14):** método público de modelo (también `@api.model`, acciones y campos calculados) que sale
  a la red, ejecuta otro código o confirma en un cursor propio sin escribir antes, así que el `READ ONLY` de la caja A
  no lo frena (A, C); se añade también una vía estándar de envío que escriba antes (B, defensa). En la 14:
  `14.0:docs/pendiente/e2_propuesta_3879.md:1230-1309` (barrido del 22, un salto por privados del mismo módulo, 47
  módulos instalados) y `14.0:docs/pendiente/parches_pns_ai.md:5094-5137` (inventario de `get` del 39, todos los
  addons, OCA y `vertical-instaladores`).
- **Caja A de R17 (leído):** un `self.env.cr.commit()` dentro de la caja A no confirma nada: el `commit` de su cursor
  está anulado (`controller_helpers.py:229`). Solo escapan los cursores propios (`self.pool.cursor()`); por eso
  `bus.presence.update_presence` (`addons/bus/models/bus_presence.py:67`, `commit` en `:79`) no tiene efecto.
- **Método:** seis ejecuciones de solo lectura en el contenedor (`17.0-20260908`, sin red ni volúmenes), con scripts
  en línea. Las rutas se citan como en el árbol de fuentes (`addons/<módulo>`; en el contenedor,
  `odoo/addons/<módulo>`):
  - **barrido automático:** los 641 módulos de `addons/`; métodos de clases con `_name` o `_inherit` (sin `tests/` ni
    `migrations/`); el cuerpo y los privados del mismo módulo hasta 3 saltos (la 14, uno), con patrones de
    `smtplib`, `requests`, `urllib`, `http.client`, `socket`/`imaplib`/`poplib`, `xmlrpc`, `subprocess`,
    `iap_jsonrpc`/`_contact_iap`/`iap.account.get`, cursores propios y `commit`, y ejecución de acciones y crons;
    los `compute` con coincidencia directa. 175 candidatos: 57 en los módulos del laboratorio y 118 fuera;
  - **llamadores de `iap.account.get`, `get_credits`, `get_credits_url` y `get_config_account_url`** en todos los
    addons, directos, por variable y por privados del mismo módulo hasta 3 saltos (el método del 39), repetido en la
    quinta ejecución;
  - **revisión a mano:** las cadenas de los nombres del 22 y del 39, y los candidatos de los módulos del laboratorio;
  - **quinta y sexta, antes de escribir esta subsección:** los llamadores de `get` (arriba), las colisiones de nombre
    de los que entran y `get_views` (`odoo/addons/base/models/ir_ui_view.py:2446`, clase `base`), que llama a
    `get_view` del mismo modelo (`:2475`);
  - **los 26 módulos del laboratorio:** no están escritos en el repo. Se derivan de los manifiestos (`depends` y
    `auto_install` desde `pns_base`, `pns_ai_mcp` y `pns_ai_chatboo`), sin consultar la BD; salen 26, como en la
    sección 10: `auth_signup`, `auth_totp`, `auth_totp_mail`, `base`, `base_import`, `base_import_module`,
    `base_install_request`, `base_setup`, `bus`, `google_gmail`, `iap`, `iap_mail`, `mail`, `mail_bot`,
    `partner_autocomplete`, `phone_validation`, `privacy_lookup`, `sms`, `snailmail`, `web`, `web_editor`,
    `web_tour`, `web_unsplash` y los tres `pns_*`.
- **Límites:** no se siguen las llamadas a métodos públicos de otro modelo ni a los genéricos del ORM
  (`odoo/models.py` y la clase `base` de `ir_ui_view.py`), como en la 14, salvo `get_views` → `get_view` y los campos
  calculados; no se han mirado los métodos `@api.onchange` que ejecuta `onchange`. Los patrones dan falsos positivos
  (`ir.attachment.check` e `ir.model.access.check` heredan la coincidencia de `res.users.check`, mismo módulo y
  nombre) y pueden dejar fuera cadenas por un nombre de librería distinto. Los candidatos de fuera del laboratorio no
  se han revisado a mano; no se ha buscado en OCA ni en `vertical-instaladores`. Las colisiones de nombre se cuentan
  en el contenedor.
- **R17 hoy (leído):** la lista global trae del fabricante `send_email`, `build_email`, `send`, `send_mail`,
  `process_email_queue`, `run` y `method_direct_trigger` (`validators_base.py:257-266`); no existe la tabla por
  modelo. La lista se aplica en el AST a las llamadas (`validators_checks.py:478-485`, que da `requires_write`) y en
  tiempo de ejecución solo al nombre dinámico (`context_builder.py:227`); la lectura literal sin llamada no la mira
  (`sandbox_attr`, `:286`). Los nombres que empiezan por `_` se rechazan en el AST (`validators.py:304`,
  `blocked_private_attr`, `validators_base.py:164-170`) y en ejecución (`context_builder.py:210`, `_refuse_attr_name`,
  que usa `sandbox_attr`). El 22 añade 22 nombres, y el 39, 8 y la tabla
  (`14.0:pns_ai_mcp/controllers/validators_base.py:279-334`).
- **Puertas de R17 para los que entran (leído):** ninguna frena sus llamadas. Sus modelos no están en
  `RELAXAICODE_CREDENTIAL_MODELS` (`validators_base.py:189-206`: modelos de `pns_ai_mcp` y `res.users.apikeys`) ni
  en el catálogo (`catalogue_inspect_error`, `validators_base.py:416-428`, antes citado en `:357-364`; AST en
  `validators_checks.py:433-437`). El cierre de columnas secretas (`models/sandbox_secret_read.py`, criterio en
  `utils/sandbox_secrets.py:36-71`) impide leer campos como `account_token`; no se ha comprobado si alcanza a lo que
  estos métodos leen dentro con `sudo()` (punto 1, decisión 48).
- **Nombres del 22 en la 17 (leído):**
  - **igual:** `connect` en `ir.mail_server` (SMTP, `odoo/addons/base/models/ir_mail_server.py:344`; no conecta
    en modo test, `:368`) y en `fetchmail.server` (IMAP o POP, `addons/mail/models/fetchmail.py:150`, `:160`,
    `:163`); `test_smtp_connection` (`ir_mail_server.py:284`); `load_remote_url` (`requests.get` a cualquier URL,
    `addons/web_editor/models/ir_qweb_fields.py:502`, `:511`); `fetch_mail` (IMAP, `fetchmail.py:215`, `:230`);
    `button_confirm_login` (`connect` en `fetchmail.py:184`, antes del `write` de `:185`); `get_credits` (`get` y
    JSON-RPC, `addons/iap/models/iap_account.py:221-222`, `:235`); `send_letter`
    (`addons/snailmail/models/mail_message.py:30-31` → `get('snailmail')`, `snailmail_letter.py:229`);
    `update_notification` (`requests.post`, `addons/mail/models/update.py:83`, `:79`); `upgrade_module`
    (`odoo/addons/base/wizard/base_module_upgrade.py:50`); `action_start_automatic_process` y
    `parent_migration_process_cb` (`base_partner_merge.py:546`, `:570`); `message_process` y `message_route`
    (`addons/mail/models/mail_thread.py:1365`, `:1079`; rebote en `:1220` y `:1269`, B); `get_usd_fx`, método de
    R17 y no del core (sección 4); y, fuera del laboratorio, `action_process_edi_web_services`
    (`addons/account_edi/models/account_move.py:378`);
  - **frenado, como en la 14:** `snailmail_print` escribe antes (`snailmail_letter.py:428-429`);
  - **sin efecto:** `autocomplete`, `enrich_company` y `read_by_vat`, vacíos
    (`addons/partner_autocomplete/models/res_partner.py:73`, `:78`, `:83`), y `start_sync`, vacío
    (`res_partner_autocomplete_sync.py:17-18`);
  - **desaparece:** `install_from_urls`;
  - **pasa a privado:** `execute_callback` (`_execute_callback`, `addons/payment/models/payment_transaction.py:880`),
    que frena el rechazo de los nombres con `_`.
- **`iap.account.get` en la 17 (leído, `iap_account.py:124-171`):** como en la 14, borra con `sudo()` las cuentas sin
  token en un cursor propio que confirma (`:133-143`) y, si no hay cuenta, la crea en otro (`:149-161`) y deja el
  token en la caché (`:164-166`). Cambia: hace `flush_all()` del llamador antes de abrir cada cursor (`:139`, `:155`),
  y en una BD neutralizada la cuenta nueva sale con el token desactivado (`:114-121`).
- **Nombres del 39 en la 17 (leído):**
  - **igual:** `get_credits_url` (`get` si no se le pasa token, `iap_account.py:174`, `:182`);
    `get_config_account_url` (`:208`, `:210`); `redirect_to_buy_autocomplete_credit`
    (`addons/partner_autocomplete/models/res_config_settings.py:15`, `:19`); `sms.resend.action_buy_credits`
    (`addons/sms/wizard/sms_resend.py:116-117`); y, fuera del laboratorio, `action_buy_sms_credits`
    (`addons/mass_mailing_sms/models/mailing_mailing.py:142-143`) y `action_submit` (`get('reveal')`,
    `addons/crm_iap_mine/models/crm_iap_lead_mining_request.py:314`, `:318`, `:240`);
  - **frenados por el `READ ONLY` (pasan de A a B):** `sms.composer.action_send_sms` en modo `numbers`, que crea los
    `sms.sms` (`addons/sms/wizard/sms_composer.py:215`) antes de enviar (`:216`; los modos `comment` y `mass`,
    `:200-204`, no se han leído); `action_send_sms_mass_now` (`write` en `:189` o `action_send_sms` en `:190`); y
    `mailing.sms.test.action_send_sms`, que crea los `sms.sms` (`addons/mass_mailing_sms/wizard/mailing_sms_test.py:35`)
    antes de enviar (`:37`).
  - Ya en la sección 4 y confirmados: `iap.account.action_buy_credits` (`iap_account.py:193`, solo sin token),
    `crm.iap.lead.mining.request.action_buy_credits` (`crm_iap_lead_mining_request.py:356`, `:359`) y
    `res.config.settings.l10n_in_edi_buy_iap` (`addons/l10n_in_edi/models/res_config_settings.py:47`, `:52`), fuera
    del laboratorio. En la 14, `l10n_in_edi_buy_iap` no está en la lista ni en la tabla, y la tabla solo trae
    `action_submit` para `crm.iap.lead.mining.request` (`14.0:pns_ai_mcp/controllers/validators_base.py:333`).
  - Restos conocidos, iguales: `res.config.settings.partner_autocomplete_insufficient_credit`
    (`res_config_settings.py:10-13`, `get_credits` al leerlo) y `crm.lead.iap_enrich`
    (`addons/crm_iap_enrich/models/crm_lead.py:51`, frenado por `FOR UPDATE NOWAIT` en `:58-60` antes de `:90`).
  - **Inventario de llamadores (todos los addons):** 21 métodos públicos llegan a `get`, directos, por variable, por
    privados del mismo módulo o a través de `get_credits`, `get_credits_url` y `get_config_account_url`; todos están
    en esta subsección o en las listas del fabricante y del 22. Tres son nuevos, de la localización india y fuera del
    laboratorio, y solo se alcanzan con 2 o 3 saltos (no se ha revisado a mano si escriben antes):
    `res.config.settings.l10n_in_edi_test` (`addons/l10n_in_edi/models/res_config_settings.py:30` →
    `account_edi_format.py:716`, `:685`, `:686`), `res.config.settings.l10n_in_edi_ewaybill_test`
    (`addons/l10n_in_edi_ewaybill/models/res_config_settings.py:17` → `account_edi_format.py:641`, `:609`, `:610`) y
    `l10n.in.ewaybill.cancel.cancel_ewaybill` (`addons/l10n_in_ewaybill_stock/wizard/l10n_in_ewaybill_cancel.py:20`
    → `tools/ewaybill_api.py:174`, `:112`, `:60`, `:61`). Este último tiene el nombre en común con
    `l10n.in.ewaybill.cancel_ewaybill` (`addons/l10n_in_ewaybill_stock/models/l10n_in_ewaybill.py:234`), que solo
    devuelve la acción que abre el asistente (leído en la referencia).
- **Candidatos nuevos en los módulos del laboratorio (leídos):**
  - `res.partner`: `autocomplete_by_name`, `autocomplete_by_vat`, `enrich_by_duns`, `enrich_by_gst` y
    `enrich_by_domain` (`res_partner.py:91`, `:108`, `:171`, `:178`, `:185`) → `_request_partner_autocomplete` →
    `get` (`iap_autocomplete_api.py:22`) y JSON-RPC (`:34`). Usuario interno; un `def` cada uno;
  - `iap.account.get_services`: JSON-RPC con los tokens de todas las cuentas, leídos con `sudo()`
    (`iap_account.py:95`, `:100`, `:105`), antes de crear (`:110`); `get_view` de tipo `tree`, que lo llama
    (`:46-49`); y `get_views` con una vista `list` o `tree`, que llama a `get_view` (clase `base`,
    `ir_ui_view.py:2475`). Usuario interno; `get_view` tiene 7 `def` (uno en `iap.account`) y `get_views`, 7
    (ninguno en `iap.account`);
  - `base_import.import.execute_import`: HTTP a cualquier URL de una columna de imagen
    (`addons/base_import/models/base_import.py:1329` → `_parse_import_data`, `:1361` → `_import_image_by_url`,
    `:1243`, `:1300`), antes de `load` (`:1380`) y sin control de host (`:1287-1327`). Usuario interno; un `def`;
  - `res.users.authenticate`: cursor propio que confirma en `_login`
    (`odoo/addons/base/models/res_users.py:906`, `:879`, `:884`, `:896`); con un usuario del sistema y
    `base_location`, `set_param` (`:917-927`); también `addons/auth_signup/models/res_users.py:124-127`. Usuario
    interno, con el nombre de la BD y una contraseña; 5 `def` (3 en `res.users`);
  - `res.company.iap_enrich_auto`: IAP por `enrich_by_domain` antes del `write`
    (`addons/partner_autocomplete/models/res_company.py:42`, `:45`, `:63`, `:73`). Solo usuarios del sistema;
    un `def`;
  - `ir.module.module.button_immediate_install_app`: descarga e instala
    (`addons/base_import_module/models/ir_module.py:414-419`). Solo administrador; un `def`;
  - `discuss.channel.rtc.session.action_disconnect`: `requests.post` a la URL guardada del servidor SFU
    (`addons/mail/models/discuss/discuss_channel_rtc_session.py:90`, `:99-106`). ACL de Ajustes; un `def`.
  - **Defensa, fuera del criterio (localizado, no probado):** `res.users.check` (`res_users.py:934-946`) comprueba una
    contraseña en un cursor propio, sin confirmar: no tiene efecto, pero sirve para probar contraseñas desde la caja
    A, como `authenticate`; 10 `def` (uno en `res.users`). Otras vías que comprueban una contraseña no se han revisado.
  - **Fuera del criterio, con motivo:** `ir.module.module.web_search_read`, `web_read` y `search_panel_select_range`
    (`base_import_module/models/ir_module.py:317-320`, `:338-342`, `:497`): `requests.post` a un host fijo
    (`_call_apps`, `:389-391`), solo con `module_type` `industries`, y nombres genéricos; `res.partner.onchange_email`
    (Gravatar, `odoo/addons/base/models/res_partner.py:514`), como en la 14; `bus.presence.update_presence` (arriba);
    las vías B que escriben antes (`message_post`, `message_notify`, `action_send_mail`, `action_resend`,
    `force_send`); y `create`, `write` y `unlink`, que el AST ya trata como escritura.
- **Fuera del laboratorio (barrido automático, sin revisar a mano):** 118 candidatos (por tipo: `commit` 58, `http`
  49, `iap` 16, `exec` 4; un candidato puede tener varios). Los de modelos que un usuario interno lee por ACL, sin
  `create`, `write` ni `unlink`: `account_peppol` (`account.journal.peppol_get_new_documents`,
  `res.partner.button_account_peppol_check_partner_endpoint` y el campo `account_peppol_verification_label`),
  `auth_oauth` (`res.users.auth_oauth`), `base_vat` (campo `res.partner.vies_valid`), `crm`
  (`crm.team.action_assign_leads`), `event` (campo `res.partner.static_map_url_is_valid`), `gamification`
  (`accept_challenge`, `action_check`, `update_goal`), `l10n_eg_edi_eta`, `l10n_es_edi_verifactu`, `l10n_fr_pdp`,
  `l10n_hu_edi`, `l10n_it_edi`, `l10n_my_edi_extended`, `l10n_ro_edi_stock`, `l10n_ro_efactura`,
  `l10n_ro_efactura_synchronize`, `l10n_tr_nilvera`, `l10n_tr_nilvera_einvoice` y `l10n_vn_edi_viettel` (botones de
  EDI de `account.move`, `account.journal`, `res.partner` y `stock.picking`), `microsoft_calendar`
  (`calendar.event.action_mass_archive`), `pos_mercury` (`do_payment`, `do_return`, `do_reversal`, `do_voidsale`),
  `stock` (`procurement.group.run_scheduler`, `stock.picking.action_confirm`), `website` (`configurator_*`) y
  `website_twitter` (`website.fetch_favorite_tweets`). El campo `crm.lead.email_domain_criterion` es un falso
  positivo (`iap_tools` sin red). Quedan como inventario; si un cliente con `l10n_es_edi_verifactu` o
  `account_peppol` instala `pns_ai`, se revisan a mano antes.
- **Conclusión:** las listas del 22 y del 39 hay que actualizarlas para la 17; el criterio de la 14 sigue valiendo.
  - **Alcance:** los 26 módulos del laboratorio y los llamadores de `get` de todos los addons (como el 39, aquí hasta
    3 saltos); el resto de fuera del laboratorio queda como inventario.
  - **Salen (6):** `install_from_urls` (desaparece), `execute_callback` (lo frena el rechazo de los nombres con `_`)
    y los cuatro vacíos de `partner_autocomplete` (`autocomplete`, `enrich_company`, `read_by_vat` y `start_sync`).
  - **Entran en la lista global y en la tabla por modelo (13):** los cinco de `partner_autocomplete` en
    `res.partner`, `get_services` en `iap.account`, `execute_import` en `base_import.import`, `iap_enrich_auto` en
    `res.company`, `button_immediate_install_app` en `ir.module.module`, `action_disconnect` en
    `discuss.channel.rtc.session` y, fuera del laboratorio, `l10n_in_edi_buy_iap`, `l10n_in_edi_test` y
    `l10n_in_edi_ewaybill_test` en `res.config.settings`.
    Decidido en la fase 2 (26/11/2026): con el 41 no van a la tabla; en ella, solo lo de las decisiones 175 y 184.
  - **Entran solo en la tabla por modelo (6):** por colisión de nombre, `get_view` y `get_views` en `iap.account`,
    `authenticate` en `res.users` y, fuera del laboratorio, `cancel_ewaybill` en `l10n.in.ewaybill.cancel`;
    `action_buy_credits` en `crm.iap.lead.mining.request`, fuera del laboratorio (el nombre ya está en la lista
    global); y, como defensa fuera del criterio, `check` en `res.users`.
  - **Cambian de grupo:** `sms.composer.action_send_sms` (en modo `numbers`), `action_send_sms_mass_now` y
    `mailing.sms.test.action_send_sms` pasan de A a B (escriben antes); se mantienen como vía estándar de envío.
  - **Alias (E3, D-2):** sigue igual en R17 (el AST solo ve llamadas y la lista global solo el nombre dinámico). Como
    D40d en la 14, la tabla por modelo cierra también el alias para los que están en ella; la familia de los parches
    15 y 22 sigue pendiente.
    Decidido en la fase 2 (26/11/2026): cerrado en la 17 con el parche 41 (decisiones 172 y 173; registro, sección 9).
- **Impacto en el port:** `test_seges_sandbox_side_effects.py` (`14.0`, `5d0559b`; 15 tests) se adapta:
  - se mantienen `test_names_in_denylist` y `test_ast_flags_literal_call` (con la lista nueva), los de correo, URL,
    acción de servidor y cron, y los cinco de `get` (`test_box_a_iap_get_*`);
  - `test_box_a_iap_refused` pasa de `read_by_vat` (vacío) a `autocomplete_by_name`;
    `test_box_a_module_from_urls_refused` pasa a `button_immediate_install_app`; en
    `test_box_a_iap_get_indirect_refused`, los casos de `action_send_sms` comprueban el rechazo por nombre y que el
    `READ ONLY` los frena;
  - casos nuevos: `get_services`, `get_view` de lista y `get_views` con una vista `list` en `iap.account`,
    `execute_import` con una URL de imagen (con `requests.Session.get` sustituido), los cinco de
    `partner_autocomplete`, `authenticate`, `check`, `iap_enrich_auto` y el alias de cada uno; `iap_jsonrpc` rechaza
    las llamadas en modo test (`addons/iap/tools/iap_tools.py:117-118`), así que los tests deben sustituirlo antes;
  - los candidatos de fuera del laboratorio quedan como inventario para los clientes que instalen esos módulos.
