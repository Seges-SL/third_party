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
\echo '## ultimo -u'
SELECT max(write_date) AS ultimo_u FROM ir_module_module WHERE name IN ('pns_ai_mcp', 'pns_ai_chatboo') \gset
SELECT :'ultimo_u';
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
SELECT id, active, protocol, model_name, fit_conversation, fit_audio, fit_vision, fit_video, fit_decision, no_external_failover
  FROM ai_provider ORDER BY id;
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
\echo '## crons nuevo2'
SELECT d.name, s.code FROM ir_model_data d JOIN ir_cron c ON c.id = d.res_id JOIN ir_act_server s ON s.id = c.ir_actions_server_id
 WHERE d.module = 'pns_ai_mcp' AND d.model = 'ir.cron'
   AND d.name IN ('ir_cron_ai_fetch_cache_gc', 'ir_cron_ai_api_result_cache_gc') ORDER BY 1;
\echo '## parametros'
SELECT key, value FROM ir_config_parameter
 WHERE key IN ('pns_ai_mcp.log_retention_days','pns_ai_chatboo.history_retention_days','pns_ai_mcp.url_access_policy','pns_ai_mcp.journal_trash_days') ORDER BY key;
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
SELECT count(*), count(agent_id), coalesce(max(id), 0) FROM ai_log;
\echo '## skills'
SELECT s.code, s.active, s.is_system,
       EXISTS (SELECT 1 FROM ir_model_data d WHERE d.model = 'ai.skill' AND d.res_id = s.id)
  FROM ai_skill s ORDER BY s.code;
\echo '## skills detalle'
SELECT id, code, coalesce(command, ''), source_module, rel_path, active, write_uid FROM ai_skill ORDER BY code;
\echo '## contextos'
SELECT count(*), count(*) FILTER (WHERE active),
       count(*) FILTER (WHERE EXISTS (SELECT 1 FROM ir_model_data d WHERE d.model = 'ai.context' AND d.res_id = c.id))
  FROM ai_context c;
\echo '## contextos por modulo'
SELECT coalesce(source_module, ''), count(*), count(*) FILTER (WHERE active) FROM ai_context GROUP BY 1 ORDER BY 1;
\echo '## modulos iap'
SELECT v.n, coalesce(m.state, '(no existe)')
  FROM (VALUES ('crm'), ('iap'), ('partner_autocomplete'), ('sms')) v(n)
  LEFT JOIN ir_module_module m ON m.name = v.n ORDER BY 1;
\echo '## idioma'
SELECT code, active FROM res_lang WHERE code = 'es_ES';
\echo '## traducciones es_ES'
SELECT count(*) FROM ir_translation WHERE lang = 'es_ES';
\echo '## tokens'
SELECT count(*) FROM res_partner WHERE signup_token IS NOT NULL;
\echo '## iap'
SELECT count(*) FROM iap_account;
\echo '## p21 contextos reescribe'
WITH f(m, p) AS (VALUES
        ('pns_ai_chatboo', 'contexts/domain/presentation_grids/presentation_grids.xml'),
        ('pns_ai_chatboo', 'contexts/domain/self_chatboo/self_chatboo.xml'),
        ('pns_ai_chatboo', 'contexts/domain/ui_focus/ui_focus.xml'),
        ('pns_ai_mcp', 'contexts/core/system_prompt.xml'),
        ('pns_ai_mcp', 'contexts/discovery/discovery_business_documents.json'),
        ('pns_ai_mcp', 'contexts/discovery/discovery_business_documents_es_ES.json'),
        ('pns_ai_mcp', 'contexts/domain/business_documents.xml'),
        ('pns_ai_mcp', 'contexts/domain/email.md'),
        ('pns_ai_mcp', 'contexts/domain/geography.xml'),
        ('pns_ai_mcp', 'contexts/domain/invoice_concepts.xml'),
        ('pns_ai_mcp', 'contexts/domain/partners.xml'),
        ('pns_ai_mcp', 'contexts/domain/sale_order_duplicate_workflow.md'),
        ('pns_ai_mcp', 'contexts/domain/self_mcp/self_mcp.xml')),
r AS (
    SELECT f.m, f.p, c.id, c.write_uid,
           CASE WHEN c.id IS NULL THEN 'falta: lo crea'
                WHEN c.owner_id IS NOT NULL THEN 'con dueño: se salta'
                WHEN NOT c.active THEN 'ARCHIVADO: choque code_uniq'
                WHEN c.write_uid IS DISTINCT FROM 1 THEN 'REESCRIBE CON EDICIÓN'
                WHEN c.write_date > :'ultimo_u'::timestamp AND c.write_date IS DISTINCT FROM c.last_used
                     THEN 'REESCRIBE CON EDICIÓN'
                WHEN c.write_date > :'ultimo_u'::timestamp THEN 'reescribe sin edición (solo uso)'
                ELSE 'reescribe sin edición' END AS estado
      FROM f LEFT JOIN ai_context c ON c.source_module = f.m AND c.rel_path = f.p)
SELECT m || ':' || p, estado, coalesce(id::text, ''), coalesce(write_uid::text, '') FROM r ORDER BY 1;
\echo '## p21 contextos nuevos'
WITH f(m, p, code) AS (VALUES
        ('pns_ai_chatboo', 'contexts/discovery/discovery_page_tab.json', 'discovery_page_tab'),
        ('pns_ai_chatboo', 'contexts/discovery/discovery_page_tab_es_ES.json', 'discovery_page_tab_es_ES'),
        ('pns_ai_chatboo', 'contexts/domain/page_tab/page_tab.xml', 'page_tab'))
SELECT f.code,
       CASE WHEN c.id IS NULL THEN 'falta: lo crea'
            WHEN c.owner_id IS NOT NULL THEN 'con dueño: se salta'
            WHEN NOT c.active THEN 'ARCHIVADO: choque code_uniq'
            ELSE 'ya existe: lo reescribe' END
  FROM f LEFT JOIN LATERAL (
       SELECT * FROM ai_context c WHERE c.code = f.code OR (c.source_module = f.m AND c.rel_path = f.p)
        ORDER BY (c.code = f.code) DESC LIMIT 1) c ON TRUE
 ORDER BY 1;
\echo '## p21 contextos retirados'
WITH d(m, p) AS (VALUES
        ('pns_ai_chatboo', 'contexts/discovery/discovery_page_tab.json'),
        ('pns_ai_chatboo', 'contexts/discovery/discovery_page_tab_es_ES.json'),
        ('pns_ai_chatboo', 'contexts/domain/page_tab/page_tab.xml'),
        ('pns_ai_chatboo', 'contexts/domain/presentation_grids/presentation_grids.xml'),
        ('pns_ai_chatboo', 'contexts/domain/self_chatboo/self_chatboo.xml'),
        ('pns_ai_chatboo', 'contexts/domain/ui_focus/ui_focus.xml'),
        ('pns_ai_mcp', 'contexts/core/system_prompt.xml'),
        ('pns_ai_mcp', 'contexts/discovery/discovery_account.json'),
        ('pns_ai_mcp', 'contexts/discovery/discovery_account_es_ES.json'),
        ('pns_ai_mcp', 'contexts/discovery/discovery_accounting_imbalances.json'),
        ('pns_ai_mcp', 'contexts/discovery/discovery_accounting_imbalances_es_ES.json'),
        ('pns_ai_mcp', 'contexts/discovery/discovery_business_documents.json'),
        ('pns_ai_mcp', 'contexts/discovery/discovery_business_documents_es_ES.json'),
        ('pns_ai_mcp', 'contexts/discovery/discovery_cost_accounting.json'),
        ('pns_ai_mcp', 'contexts/discovery/discovery_cost_accounting_es_ES.json'),
        ('pns_ai_mcp', 'contexts/discovery/discovery_fetch_url_recipe.json'),
        ('pns_ai_mcp', 'contexts/discovery/discovery_fetch_url_recipe_es_ES.json'),
        ('pns_ai_mcp', 'contexts/discovery/discovery_filters.json'),
        ('pns_ai_mcp', 'contexts/discovery/discovery_filters_es_ES.json'),
        ('pns_ai_mcp', 'contexts/discovery/discovery_geography.json'),
        ('pns_ai_mcp', 'contexts/discovery/discovery_geography_es_ES.json'),
        ('pns_ai_mcp', 'contexts/discovery/discovery_hr_contracts.json'),
        ('pns_ai_mcp', 'contexts/discovery/discovery_hr_contracts_es_ES.json'),
        ('pns_ai_mcp', 'contexts/discovery/discovery_hr_payroll.json'),
        ('pns_ai_mcp', 'contexts/discovery/discovery_hr_payroll_es_ES.json'),
        ('pns_ai_mcp', 'contexts/discovery/discovery_invoice_concepts.json'),
        ('pns_ai_mcp', 'contexts/discovery/discovery_invoice_concepts_es_ES.json'),
        ('pns_ai_mcp', 'contexts/discovery/discovery_partners.json'),
        ('pns_ai_mcp', 'contexts/discovery/discovery_partners_es_ES.json'),
        ('pns_ai_mcp', 'contexts/discovery/discovery_trial_balance.json'),
        ('pns_ai_mcp', 'contexts/discovery/discovery_trial_balance_es_ES.json'),
        ('pns_ai_mcp', 'contexts/domain/account.xml'),
        ('pns_ai_mcp', 'contexts/domain/accounting_imbalances.xml'),
        ('pns_ai_mcp', 'contexts/domain/business_documents.xml'),
        ('pns_ai_mcp', 'contexts/domain/cost_accounting.xml'),
        ('pns_ai_mcp', 'contexts/domain/dates.xml'),
        ('pns_ai_mcp', 'contexts/domain/email.md'),
        ('pns_ai_mcp', 'contexts/domain/fetch_url_recipe/fetch_url_recipe.xml'),
        ('pns_ai_mcp', 'contexts/domain/filters.xml'),
        ('pns_ai_mcp', 'contexts/domain/geography.xml'),
        ('pns_ai_mcp', 'contexts/domain/hr_contracts/hr_contracts.xml'),
        ('pns_ai_mcp', 'contexts/domain/hr_payroll/hr_payroll.xml'),
        ('pns_ai_mcp', 'contexts/domain/hr_payroll/hr_payroll_accounting_present.xml'),
        ('pns_ai_mcp', 'contexts/domain/hr_payroll/hr_payroll_de_DE.xml'),
        ('pns_ai_mcp', 'contexts/domain/hr_payroll/hr_payroll_en_US.xml'),
        ('pns_ai_mcp', 'contexts/domain/hr_payroll/hr_payroll_es_AR.xml'),
        ('pns_ai_mcp', 'contexts/domain/hr_payroll/hr_payroll_es_ES.xml'),
        ('pns_ai_mcp', 'contexts/domain/hr_payroll/hr_payroll_es_MX.xml'),
        ('pns_ai_mcp', 'contexts/domain/hr_payroll/hr_payroll_fr_FR.xml'),
        ('pns_ai_mcp', 'contexts/domain/hr_payroll/hr_payroll_it_IT.xml'),
        ('pns_ai_mcp', 'contexts/domain/hr_payroll/hr_payroll_pt_BR.xml'),
        ('pns_ai_mcp', 'contexts/domain/invoice_concepts.xml'),
        ('pns_ai_mcp', 'contexts/domain/partners.xml'),
        ('pns_ai_mcp', 'contexts/domain/sale_order_duplicate_workflow.md'),
        ('pns_ai_mcp', 'contexts/domain/self_mcp/self_mcp.xml'),
        ('pns_ai_mcp', 'contexts/domain/trial_balance/trial_balance.xml'),
        ('pns_ai_mcp', 'contexts/domain/trial_balance/trial_balance_es_ES.xml'),
        ('pns_ai_mcp', 'contexts/locale/corporate_terms/corporate_terms.xml'),
        ('pns_ai_mcp', 'contexts/locale/corporate_terms/corporate_terms_es_ES.xml'))
SELECT c.code, c.source_module, c.id, c.active
  FROM ai_context c
 WHERE c.source_module IN ('pns_ai_mcp', 'pns_ai_chatboo')
   AND c.owner_id IS NULL AND c.rel_path IS NOT NULL
   AND NOT EXISTS (SELECT 1 FROM d WHERE d.m = c.source_module AND d.p = c.rel_path)
 ORDER BY 2, 1;
\echo '## p21 skills reescribe'
WITH f(code) AS (VALUES ('billing'), ('financial_health'), ('forecast')),
r AS (
    SELECT f.code AS fcode, s.*
      FROM f LEFT JOIN LATERAL (
           SELECT * FROM ai_skill s
            WHERE (s.source_module = 'pns_ai_chatboo' AND s.rel_path = 'skills/system/' || f.code || '.md')
               OR s.code = f.code OR s.command = f.code
            ORDER BY (s.source_module = 'pns_ai_chatboo' AND s.rel_path = 'skills/system/' || f.code || '.md') DESC
            LIMIT 1) s ON TRUE)
SELECT fcode,
       CASE WHEN id IS NULL THEN 'falta: la crea'
            WHEN owner_id IS NOT NULL THEN 'con dueño: se salta'
            WHEN source_module IS DISTINCT FROM 'pns_ai_chatboo' AND source_module IS NOT NULL
                 THEN 'de otro módulo: se salta'
            WHEN NOT active THEN 'ARCHIVADA: choque code_uniq'
            WHEN write_date > :'ultimo_u'::timestamp OR write_uid IS DISTINCT FROM 1 THEN 'REESCRIBE CON EDICIÓN'
            ELSE 'reescribe sin edición' END,
       coalesce(id::text, ''), coalesce(write_uid::text, '')
  FROM r ORDER BY fcode;
\echo '## p21 skills retiradas'
SELECT s.code, s.id, s.active, s.write_uid
  FROM ai_skill s
 WHERE s.source_module = 'pns_ai_chatboo' AND s.owner_id IS NULL
   AND coalesce(s.rel_path, '') NOT IN ('skills/system/bill_draft.md', 'skills/system/billing.md',
       'skills/system/customer_360.md', 'skills/system/dashboard.md', 'skills/system/financial_health.md',
       'skills/system/forecast.md', 'skills/system/pipeline.md', 'skills/system/sales_board.md',
       'skills/system/top_sales.md', 'skills/system/users.md')
   AND coalesce(s.code, '') NOT IN ('bill_draft', 'billing', 'customer_360', 'dashboard', 'financial_health',
       'forecast', 'pipeline', 'sales_board', 'top_sales', 'users')
   AND coalesce(s.command, '') NOT IN ('bill_draft', 'billing', 'customer_360', 'dashboard', 'financial_health',
       'forecast', 'pipeline', 'sales_board', 'top_sales', 'users')
 ORDER BY 1;
\echo '## p21 skills nuevas que ya existen'
SELECT s.code, s.source_module, s.id,
       CASE WHEN s.owner_id IS NOT NULL THEN 'con dueño: se salta'
            WHEN s.source_module IS DISTINCT FROM 'pns_ai_chatboo' AND s.source_module IS NOT NULL
                 THEN 'de otro módulo: se salta'
            WHEN NOT s.active THEN 'ARCHIVADA: choque code_uniq'
            ELSE 'la adopta y la reescribe' END
  FROM ai_skill s
 WHERE s.code IN ('bill_draft', 'customer_360', 'pipeline', 'sales_board', 'top_sales', 'users')
    OR s.command IN ('bill_draft', 'customer_360', 'pipeline', 'sales_board', 'top_sales', 'users')
    OR (s.source_module = 'pns_ai_chatboo' AND s.rel_path IN ('skills/system/bill_draft.md',
        'skills/system/customer_360.md', 'skills/system/pipeline.md', 'skills/system/sales_board.md',
        'skills/system/top_sales.md', 'skills/system/users.md'))
 ORDER BY 1;
\echo '## p21 archivadas'
SELECT 'ai_skill', coalesce(source_module, ''), count(*) FROM ai_skill WHERE NOT active GROUP BY 2
UNION ALL
SELECT 'ai_context', coalesce(source_module, ''), count(*) FROM ai_context WHERE NOT active GROUP BY 2
ORDER BY 1, 2;
\echo '## fin'
