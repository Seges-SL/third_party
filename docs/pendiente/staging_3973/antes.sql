-- antes.sql: estado de la BD ANTES del -u de 3.1.879 a 3.1.973 (staging pns_demo).
-- SOLO LECTURA (BEGIN TRANSACTION READ ONLY ... ROLLBACK). Solo columnas que existen en 3.1.879.
-- Uso: psql -X -q -At -F '|' -d <bd> -f antes.sql > antes.txt
-- Sin api_key ni contenido: solo códigos, xml_id, ids, recuentos, estados y nombres de proveedor/modelo.
BEGIN TRANSACTION READ ONLY;

\echo '## versiones (name|latest_version|state)'
SELECT name, latest_version, state FROM ir_module_module
 WHERE name IN ('pns_base', 'pns_ai_mcp', 'pns_ai_chatboo') ORDER BY name;

\echo '## crons de pns_* (xml_id|activo|numbercall|interval_number|interval_type)'
SELECT d.module || '.' || d.name, c.active, c.numbercall, c.interval_number, c.interval_type
  FROM ir_model_data d JOIN ir_cron c ON c.id = d.res_id
 WHERE d.model = 'ir.cron' AND d.module LIKE 'pns\_%'
 ORDER BY 1;

\echo '## crons de purga, consulta del plan «Parche 35» (name|code|activo)'
SELECT d.name, s.code, c.active
  FROM ir_model_data d
  JOIN ir_cron c ON c.id = d.res_id
  JOIN ir_act_server s ON s.id = c.ir_actions_server_id
 WHERE d.module = 'pns_ai_mcp' AND d.model = 'ir.cron'
   AND d.name IN ('ir_cron_ai_fetch_cache_gc', 'ir_cron_ai_api_result_cache_gc')
 ORDER BY d.name;

\echo '## ai_trusted_action (n|max_id)'
SELECT count(*), max(id) FROM ai_trusted_action;

\echo '## ai_skill (code|source_module|owner_id vacío|activa)'
SELECT code, source_module, owner_id IS NULL, active FROM ai_skill ORDER BY code;

\echo '## ai_skill por source_module (source_module|n)'
SELECT coalesce(source_module, ''), count(*) FROM ai_skill GROUP BY 1 ORDER BY 1;

\echo '## las 7 skills retiradas presentes (n)'
SELECT count(*) FROM ai_skill
 WHERE code IN ('annual_billing', 'cash_forecast', 'credit_facility', 'customer_risk_analysis',
                'sys_info', 'users_all', 'users_logged');

\echo '## P-11 (AI Administrators|sin AI Conversational), como docs/pendiente/lab_3973/rama_comprobar.sh:108-119'
WITH g AS (SELECT
    (SELECT res_id FROM ir_model_data WHERE module = 'pns_ai_mcp' AND name = 'group_ai_admin' AND model = 'res.groups') AS adm,
    (SELECT res_id FROM ir_model_data WHERE module = 'pns_ai_mcp' AND name = 'group_ai_conversational' AND model = 'res.groups') AS conv)
SELECT count(*), count(*) FILTER (WHERE NOT EXISTS (
       SELECT 1 FROM res_groups_users_rel r2 WHERE r2.uid = r.uid AND r2.gid = g.conv))
  FROM res_groups_users_rel r, g WHERE r.gid = g.adm;

\echo '## diseños no vacíos (tabla.columna|n)'
SELECT 'chatboo_session.canvas_design', count(*) FROM chatboo_session
 WHERE coalesce(btrim(canvas_design), '') <> ''
UNION ALL
SELECT 'chatboo_canvas_page.design', count(*) FROM chatboo_canvas_page
 WHERE coalesce(btrim(design), '') <> '';

\echo '## chatboo_session con /web/image en canvas_design (id|user_id)'
SELECT id, user_id FROM chatboo_session WHERE canvas_design LIKE '%/web/image%' ORDER BY id;

\echo '## módulos iap, sms, partner_autocomplete y crm (name|state)'
SELECT v.n, coalesce(m.state, '(no existe)')
  FROM (VALUES ('crm'), ('iap'), ('partner_autocomplete'), ('sms')) v(n)
  LEFT JOIN ir_module_module m ON m.name = v.n ORDER BY 1;

\echo '## ai_provider (id|activo|fit_conversation|fit_audio|fit_vision|fit_video|fit_decision|fit_design|model_name|name)'
SELECT id, active, fit_conversation, fit_audio, fit_vision, fit_video, fit_decision, fit_design, model_name, name
  FROM ai_provider ORDER BY id;

\echo '## cadena ai_agent_provider, sin api_key (id|agente|prioridad|activo|skip_sync_fallback|provider_id|proveedor activo)'
SELECT ap.id, a.code, ap.priority, ap.active, ap.skip_sync_fallback, ap.provider_id, p.active
  FROM ai_agent_provider ap
  LEFT JOIN ai_agent a ON a.id = ap.agent_id
  LEFT JOIN ai_provider p ON p.id = ap.provider_id
 ORDER BY a.code, ap.priority, ap.id;

\echo '## ai_safe_operation por status (status|n)'
SELECT coalesce(status, ''), count(*) FROM ai_safe_operation GROUP BY 1 ORDER BY 1;

\echo '## ai_safe_operation pending o confirmed sin ejecutar (id|status|executed|expires_at)'
SELECT id, status, executed, expires_at FROM ai_safe_operation
 WHERE status IN ('pending', 'confirmed') AND NOT coalesce(executed, false)
 ORDER BY id;

\echo '## ai_log (max_id)'
SELECT max(id) FROM ai_log;

\echo '## iap_account (n|max_id)'
SELECT count(*), max(id) FROM iap_account;

ROLLBACK;
