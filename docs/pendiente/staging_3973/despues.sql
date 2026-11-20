-- despues.sql: estado de la BD DESPUÉS del -u a 3.1.973 (staging pns_demo).
-- SOLO LECTURA (BEGIN TRANSACTION READ ONLY ... ROLLBACK). Lo de antes.sql sin las fit_* (3.1.973 las borra)
-- y con el rol Diseño.
-- Rol Diseño en 3.1.973 (rama 14.0-pns-ai-3973):
--   modelo ai.provider.role (pns_ai_mcp/models/ai_provider_role.py:45); registro
--   pns_ai_mcp.ai_provider_role_design, code 'design', alternativa ai_provider_role_conversation
--   (pns_ai_mcp/data/ai_provider_role_data.xml:48-57); use_fallback es del rol, no del proveedor
--   (ai_provider_role.py:85-91), y fallback_id (:77-84); quién lo tiene: Many2many provider_ids/role_ids
--   en ai_provider_role_rel (ai_provider_role.py:96-101; models/ai_provider.py:225-227).
--   fit_design pasa al rol 'design' (utils/schema_fossils.py:270-278, FIT_COLUMNS; stash
--   ai_provider_fit_stash, :279).
-- Uso: psql -X -q -At -F '|' -d <bd> -f despues.sql > despues.txt
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

\echo '## ai_provider (id|activo|model_name|name)'
SELECT id, active, model_name, name FROM ai_provider ORDER BY id;

\echo '## rol Diseño (xml_id|code|activo|use_fallback|alternativa)'
SELECT d.module || '.' || d.name, r.code, r.active, r.use_fallback, fb.code
  FROM ai_provider_role r
  LEFT JOIN ir_model_data d ON d.model = 'ai.provider.role' AND d.res_id = r.id
  LEFT JOIN ai_provider_role fb ON fb.id = r.fallback_id
 WHERE r.code = 'design';

\echo '## proveedores con el rol Diseño (provider_id|proveedor activo|use_fallback del rol)'
SELECT p.id, p.active, r.use_fallback
  FROM ai_provider_role r
  JOIN ai_provider_role_rel rr ON rr.role_id = r.id
  JOIN ai_provider p ON p.id = rr.provider_id
 WHERE r.code = 'design'
 ORDER BY p.id;

\echo '## roles por proveedor (provider_id|proveedor activo|roles)'
SELECT p.id, p.active, coalesce(string_agg(r.code, ',' ORDER BY r.sequence, r.id), '')
  FROM ai_provider p
  LEFT JOIN ai_provider_role_rel rr ON rr.provider_id = p.id
  LEFT JOIN ai_provider_role r ON r.id = rr.role_id
 GROUP BY p.id, p.active ORDER BY p.id;

\echo '## tabla ai_provider_fit_stash (existe)'
SELECT to_regclass('public.ai_provider_fit_stash') IS NOT NULL;

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
