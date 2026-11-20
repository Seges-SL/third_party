\echo '## versiones'
SELECT name, state, latest_version FROM ir_module_module WHERE name IN ('pns_base','pns_ai_mcp','pns_ai_chatboo') ORDER BY name;
\echo '## estados a medias'
SELECT count(*) FROM ir_module_module WHERE state IN ('to upgrade','to install','to remove');
\echo '## instalados'
SELECT count(*) FROM ir_module_module WHERE state = 'installed';
\echo '## dependientes'
SELECT DISTINCT m.name FROM ir_module_module m JOIN ir_module_module_dependency d ON d.module_id = m.id
 WHERE d.name IN ('pns_base','pns_ai_mcp','pns_ai_chatboo') AND m.state = 'installed'
   AND m.name NOT IN ('pns_base','pns_ai_mcp','pns_ai_chatboo') ORDER BY 1;
\echo '## ai admins'
SELECT u.id, u.active,
       EXISTS (SELECT 1 FROM res_groups_users_rel r2 JOIN ir_model_data d2 ON d2.model = 'res.groups' AND d2.res_id = r2.gid
                WHERE r2.uid = u.id AND d2.module = 'base' AND d2.name = 'group_system'),
       coalesce(u.password, '') <> '',
       EXISTS (SELECT 1 FROM res_groups_users_rel r3 JOIN ir_model_data d3 ON d3.model = 'res.groups' AND d3.res_id = r3.gid
                WHERE r3.uid = u.id AND d3.module = 'pns_ai_mcp' AND d3.name = 'group_ai_conversational')
  FROM res_users u
  JOIN res_groups_users_rel r ON r.uid = u.id
  JOIN ir_model_data d ON d.model = 'res.groups' AND d.res_id = r.gid AND d.module = 'pns_ai_mcp' AND d.name = 'group_ai_admin'
 ORDER BY u.id;
\echo '## p11'
WITH g AS (SELECT
    (SELECT res_id FROM ir_model_data WHERE module = 'pns_ai_mcp' AND name = 'group_ai_admin' AND model = 'res.groups') AS adm,
    (SELECT res_id FROM ir_model_data WHERE module = 'pns_ai_mcp' AND name = 'group_ai_conversational' AND model = 'res.groups') AS conv)
SELECT count(*), count(*) FILTER (WHERE NOT EXISTS (
       SELECT 1 FROM res_groups_users_rel r2 WHERE r2.uid = r.uid AND r2.gid = g.conv))
  FROM res_groups_users_rel r, g WHERE r.gid = g.adm;
\echo '## proveedores'
SELECT id, active, protocol, model_name, no_external_failover FROM ai_provider ORDER BY id;
\echo '## roles por proveedor'
SELECT p.id, p.active, p.model_name, coalesce(string_agg(r.code, ',' ORDER BY r.sequence, r.id), '')
  FROM ai_provider p
  LEFT JOIN ai_provider_role_rel rr ON rr.provider_id = p.id
  LEFT JOIN ai_provider_role r ON r.id = rr.role_id
 GROUP BY p.id, p.active, p.model_name ORDER BY p.id;
\echo '## rol Diseño'
SELECT d.module || '.' || d.name, r.code, r.active, r.use_fallback, coalesce(fb.code, '')
  FROM ai_provider_role r
  LEFT JOIN ir_model_data d ON d.model = 'ai.provider.role' AND d.res_id = r.id
  LEFT JOIN ai_provider_role fb ON fb.id = r.fallback_id
 WHERE r.code = 'design';
\echo '## con Diseño'
SELECT p.id, p.active, r.use_fallback
  FROM ai_provider_role r JOIN ai_provider_role_rel rr ON rr.role_id = r.id JOIN ai_provider p ON p.id = rr.provider_id
 WHERE r.code = 'design' ORDER BY p.id;
\echo '## con Decisión'
SELECT p.id, p.active, p.protocol
  FROM ai_provider_role r JOIN ai_provider_role_rel rr ON rr.role_id = r.id JOIN ai_provider p ON p.id = rr.provider_id
 WHERE r.code = 'decision' ORDER BY p.id;
\echo '## roles'
SELECT code, active, use_fallback, coalesce((SELECT f.code FROM ai_provider_role f WHERE f.id = r.fallback_id), '') FROM ai_provider_role r ORDER BY sequence, id;
\echo '## cadena'
SELECT ap.id, a.code, ap.priority, ap.active, ap.skip_sync_fallback, ap.provider_id, p.active
  FROM ai_agent_provider ap
  LEFT JOIN ai_agent a ON a.id = ap.agent_id
  LEFT JOIN ai_provider p ON p.id = ap.provider_id
 ORDER BY a.code, ap.priority, ap.id;
\echo '## crons'
SELECT d.module || '.' || d.name, c.active, c.interval_number || ' ' || c.interval_type, c.numbercall
  FROM ir_model_data d JOIN ir_cron c ON c.id = d.res_id
 WHERE d.model = 'ir.cron' AND d.module IN ('pns_base','pns_ai_mcp','pns_ai_chatboo') ORDER BY 1;
\echo '## crons activos'
SELECT count(*) FROM ir_cron WHERE active;
\echo '## crons creados en el -u'
SELECT coalesce((SELECT d.module || '.' || d.name FROM ir_model_data d WHERE d.model = 'ir.cron' AND d.res_id = c.id LIMIT 1), 'id ' || c.id)
  FROM ir_cron c WHERE c.create_date >= :'t0'::timestamp ORDER BY 1;
\echo '## crons nuevo2'
SELECT d.name, s.code FROM ir_model_data d JOIN ir_cron c ON c.id = d.res_id JOIN ir_act_server s ON s.id = c.ir_actions_server_id
 WHERE d.module = 'pns_ai_mcp' AND d.model = 'ir.cron'
   AND d.name IN ('ir_cron_ai_fetch_cache_gc', 'ir_cron_ai_api_result_cache_gc') ORDER BY 1;
\echo '## parametros'
SELECT key, value FROM ir_config_parameter
 WHERE key IN ('pns_ai_mcp.log_retention_days','pns_ai_chatboo.history_retention_days','pns_ai_mcp.url_access_policy') ORDER BY key;
\echo '## parametro papelera'
SELECT key, value FROM ir_config_parameter WHERE key = 'pns_ai_mcp.journal_trash_days';
\echo '## operaciones no terminales'
SELECT status, coalesce(executed, false), count(*) FROM ai_safe_operation
 WHERE status = 'pending' OR (status = 'confirmed' AND NOT coalesce(executed, false)) GROUP BY 1, 2 ORDER BY 1, 2;
\echo '## operaciones trusted'
SELECT count(*) FROM ai_safe_operation
 WHERE (status = 'pending' OR (status = 'confirmed' AND NOT coalesce(executed, false)))
   AND coalesce(operation_data, '') ~ '"model"\s*:\s*"ai\.trusted\.action"';
\echo '## operaciones por status'
SELECT coalesce(status, ''), count(*) FROM ai_safe_operation GROUP BY 1 ORDER BY 1;
\echo '## trusted'
SELECT count(*), coalesce(max(id), 0) FROM ai_trusted_action;
\echo '## servidores api'
SELECT count(*) FROM ai_api_server;
\echo '## diario'
SELECT count(*), count(*) FILTER (WHERE op = 'unlink' AND position('"quarantine": true' IN coalesce(after_json, '')) > 0),
       count(*) FILTER (WHERE write_uid IS DISTINCT FROM create_uid AND write_uid <> 1)
  FROM ai_change_journal;
\echo '## chatboo'
SELECT count(*), coalesce(max(id), 0), coalesce(to_char(min(create_date), 'YYYY-MM'), '-'), count(DISTINCT user_id) FROM chatboo_session;
\echo '## ai_log'
SELECT count(*), coalesce(max(id), 0) FROM ai_log;
\echo '## skills'
SELECT s.code, s.active, s.is_system,
       EXISTS (SELECT 1 FROM ir_model_data d WHERE d.model = 'ai.skill' AND d.res_id = s.id)
  FROM ai_skill s ORDER BY s.code;
\echo '## skills detalle'
SELECT id, code, coalesce(command, ''), coalesce(source_module, ''), coalesce(rel_path, ''), active, write_uid, (write_date >= :'t0'::timestamp) FROM ai_skill ORDER BY code;
\echo '## skills reescritas'
SELECT code FROM ai_skill WHERE id IN (2, 6, 7) AND write_date >= :'t0'::timestamp ORDER BY code;
\echo '## contextos'
SELECT count(*), count(*) FILTER (WHERE active),
       count(*) FILTER (WHERE EXISTS (SELECT 1 FROM ir_model_data d WHERE d.model = 'ai.context' AND d.res_id = c.id))
  FROM ai_context c;
\echo '## contextos por modulo'
SELECT coalesce(source_module, ''), count(*), count(*) FILTER (WHERE active) FROM ai_context GROUP BY 1 ORDER BY 1;
\echo '## contextos nuevos'
SELECT c.code, c.source_module, c.rel_path, c.active, (c.create_date >= :'t0'::timestamp)
  FROM ai_context c WHERE c.code IN ('discovery_page_tab', 'discovery_page_tab_es_ES', 'page_tab') ORDER BY 1;
\echo '## contextos de antes'
SELECT count(*) FROM ai_context WHERE create_date < :'t0'::timestamp;
\echo '## contextos reescritos'
SELECT count(*) FILTER (WHERE id IN (1, 3, 4, 28, 29, 30, 33, 34, 37, 50, 54, 55, 56)),
       count(*) FILTER (WHERE id NOT IN (1, 3, 4, 28, 29, 30, 33, 34, 37, 50, 54, 55, 56) AND create_date < :'t0'::timestamp)
  FROM ai_context WHERE write_date >= :'t0'::timestamp;
\echo '## archivadas'
SELECT 'ai_skill', coalesce(source_module, ''), count(*) FROM ai_skill WHERE NOT active GROUP BY 2
UNION ALL
SELECT 'ai_context', coalesce(source_module, ''), count(*) FROM ai_context WHERE NOT active GROUP BY 2
ORDER BY 1, 2;
\echo '## modulos iap'
SELECT v.n, coalesce(m.state, '(no existe)')
  FROM (VALUES ('crm'), ('iap'), ('partner_autocomplete'), ('sms')) v(n)
  LEFT JOIN ir_module_module m ON m.name = v.n ORDER BY 1;
\echo '## idioma'
SELECT code, active FROM res_lang WHERE code = 'es_ES';
\echo '## traducciones es_ES'
SELECT count(*) FROM ir_translation WHERE lang = 'es_ES';
\echo '## traducciones fuera de pns'
SELECT count(*), md5(coalesce(string_agg(id || ':' || md5(coalesce(value, '')), ',' ORDER BY id), ''))
  FROM ir_translation WHERE lang = 'es_ES' AND coalesce(module, '') NOT LIKE 'pns\_%';
\echo '## traducciones pns'
SELECT module, count(*) FROM ir_translation WHERE lang = 'es_ES' AND module LIKE 'pns\_%' GROUP BY 1 ORDER BY 1;
\echo '## tokens'
SELECT count(*) FROM res_partner WHERE signup_token IS NOT NULL;
\echo '## iap'
SELECT count(*) FROM iap_account;
\echo '## fin'
