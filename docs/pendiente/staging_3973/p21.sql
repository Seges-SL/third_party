-- P-21: contextos y skills de fábrica que reescribe, borra o adopta el -u de 3.1.879 a 3.1.973.
-- SOLO LECTURA (BEGIN TRANSACTION READ ONLY ... ROLLBACK). BD con 3.1.879, antes del -u.
-- Uso: psql -X -q -At -F '|' -d <bd> -f p21.sql
-- Fuente: docs/specs/comparacion_pns_ai_3-1-973.md §7.3 (5 y 6), fila P-21 y resultado del 10/11.
-- Código 3.1.973 (igual en la rama 14.0-pns-ai-3973 en ai/contexts y ai/skills):
--   contextos: pns_ai_mcp/data/mcp_data.xml:5-6 y pns_ai_chatboo/data/chatboo_context_data.xml:4-5
--     (_import_all_from_module, noupdate=0); busca por code (models/ai_context_disk.py:648) y si no,
--     por rel_path (:650-659), ambas sin active_test=False; con owner_id se salta (:666-673);
--     reescribe (:704-716) o crea (:717-724); borra los de fábrica cuyo code ya no está en disco
--     (llamada :738; _unlink_retired_from_module :751-790, comparación por code :779).
--   skills: pns_ai_chatboo/data/chatboo_skill_data.xml:10-11 (import_from_module); rel_path
--     'skills/<scope>/<archivo>' (models/ai_skill_disk.py:253); busca por source_module+rel_path y si no,
--     por code/command (:262-273), sin active_test=False; con owner_id se salta (:279-286); de otro
--     módulo se salta (:287-297); reescribe (:298-305); si no la encuentra, la crea (:306-309);
--     retiradas: source_module, owner_id vacío y sin archivo (:377-422, utils/skill_files.py:58-71).
--   Riesgo de las archivadas: no se encuentran, el alta choca con code_uniq
--     (models/ai_skill.py:272-274; models/ai_context.py:116-118).
-- Archivos que cambian de 3.1.879 a 3.1.973 (diff -rq de pns_fabricante): 12 contextos;
--   skills: reescribe billing, financial_health, forecast; retira annual_billing, cash_forecast,
--   credit_facility, customer_risk_analysis, sys_info, users_all, users_logged; nuevas (adopción si
--   ya existe el code): bill_draft, sales_board, top_sales, users.
-- Esperado en pns_demo (10/11 y p15b): 12 contextos y 3 skills «reescribe sin edición», 7 retiradas,
--   0 adoptar, 0 archivadas, 0 contextos retirados.
BEGIN TRANSACTION READ ONLY;

\echo '## ultimo -u (max write_date de pns_ai_mcp y pns_ai_chatboo)'
SELECT max(write_date) AS ultimo_u FROM ir_module_module
 WHERE name IN ('pns_ai_mcp', 'pns_ai_chatboo') \gset
SELECT :'ultimo_u';

\echo '## contextos que reescribe (code|source_module|id|estado|write_uid)'
WITH f(m, p) AS (VALUES
        ('pns_ai_mcp', 'contexts/core/system_prompt.xml'),
        ('pns_ai_mcp', 'contexts/domain/business_documents.xml'),
        ('pns_ai_mcp', 'contexts/domain/invoice_concepts.xml'),
        ('pns_ai_mcp', 'contexts/domain/email.md'),
        ('pns_ai_mcp', 'contexts/domain/geography.xml'),
        ('pns_ai_mcp', 'contexts/domain/sale_order_duplicate_workflow.md'),
        ('pns_ai_mcp', 'contexts/discovery/discovery_business_documents.json'),
        ('pns_ai_mcp', 'contexts/discovery/discovery_business_documents_es_ES.json'),
        ('pns_ai_chatboo', 'contexts/domain/ui_focus/ui_focus.xml'),
        ('pns_ai_chatboo', 'contexts/domain/presentation_grids/presentation_grids.xml'),
        ('pns_ai_chatboo', 'contexts/discovery/discovery_page_tab.json'),
        ('pns_ai_chatboo', 'contexts/discovery/discovery_page_tab_es_ES.json')),
r AS (
    SELECT f.m, f.p, c.id, c.code, c.write_uid,
           CASE WHEN c.id IS NULL THEN 'falta: lo crea'
                WHEN c.owner_id IS NOT NULL THEN 'con dueño: se salta'
                WHEN NOT c.active THEN 'ARCHIVADO: choque code_uniq'
                WHEN c.write_date > :'ultimo_u'::timestamp THEN 'REESCRIBE CON EDICIÓN'
                ELSE 'reescribe sin edición' END AS estado
      FROM f LEFT JOIN ai_context c ON c.source_module = f.m AND c.rel_path = f.p)
SELECT coalesce(code, '(' || p || ')'), m, id, estado, write_uid FROM r ORDER BY m DESC, p;

\echo '## contextos que reescribe: resumen (estado|n)'
WITH f(m, p) AS (VALUES
        ('pns_ai_mcp', 'contexts/core/system_prompt.xml'),
        ('pns_ai_mcp', 'contexts/domain/business_documents.xml'),
        ('pns_ai_mcp', 'contexts/domain/invoice_concepts.xml'),
        ('pns_ai_mcp', 'contexts/domain/email.md'),
        ('pns_ai_mcp', 'contexts/domain/geography.xml'),
        ('pns_ai_mcp', 'contexts/domain/sale_order_duplicate_workflow.md'),
        ('pns_ai_mcp', 'contexts/discovery/discovery_business_documents.json'),
        ('pns_ai_mcp', 'contexts/discovery/discovery_business_documents_es_ES.json'),
        ('pns_ai_chatboo', 'contexts/domain/ui_focus/ui_focus.xml'),
        ('pns_ai_chatboo', 'contexts/domain/presentation_grids/presentation_grids.xml'),
        ('pns_ai_chatboo', 'contexts/discovery/discovery_page_tab.json'),
        ('pns_ai_chatboo', 'contexts/discovery/discovery_page_tab_es_ES.json'))
SELECT CASE WHEN c.id IS NULL THEN 'falta: lo crea'
            WHEN c.owner_id IS NOT NULL THEN 'con dueño: se salta'
            WHEN NOT c.active THEN 'ARCHIVADO: choque code_uniq'
            WHEN c.write_date > :'ultimo_u'::timestamp THEN 'REESCRIBE CON EDICIÓN'
            ELSE 'reescribe sin edición' END AS estado, count(*)
  FROM f LEFT JOIN ai_context c ON c.source_module = f.m AND c.rel_path = f.p
 GROUP BY 1 ORDER BY 1;

\echo '## contextos de fábrica sin archivo en 3.1.973: los borra (code|source_module|id|activo)'
-- El -u compara por code (ai_context_disk.py:779); aquí, por rel_path contra los 59 archivos de 3.1.973.
WITH d(m, p) AS (VALUES
        ('pns_ai_mcp', 'contexts/core/system_prompt.xml'),
        ('pns_ai_mcp', 'contexts/discovery/discovery_account_es_ES.json'),
        ('pns_ai_mcp', 'contexts/discovery/discovery_accounting_imbalances_es_ES.json'),
        ('pns_ai_mcp', 'contexts/discovery/discovery_accounting_imbalances.json'),
        ('pns_ai_mcp', 'contexts/discovery/discovery_account.json'),
        ('pns_ai_mcp', 'contexts/discovery/discovery_business_documents_es_ES.json'),
        ('pns_ai_mcp', 'contexts/discovery/discovery_business_documents.json'),
        ('pns_ai_mcp', 'contexts/discovery/discovery_cost_accounting_es_ES.json'),
        ('pns_ai_mcp', 'contexts/discovery/discovery_cost_accounting.json'),
        ('pns_ai_mcp', 'contexts/discovery/discovery_fetch_url_recipe_es_ES.json'),
        ('pns_ai_mcp', 'contexts/discovery/discovery_fetch_url_recipe.json'),
        ('pns_ai_mcp', 'contexts/discovery/discovery_filters_es_ES.json'),
        ('pns_ai_mcp', 'contexts/discovery/discovery_filters.json'),
        ('pns_ai_mcp', 'contexts/discovery/discovery_geography_es_ES.json'),
        ('pns_ai_mcp', 'contexts/discovery/discovery_geography.json'),
        ('pns_ai_mcp', 'contexts/discovery/discovery_hr_contracts_es_ES.json'),
        ('pns_ai_mcp', 'contexts/discovery/discovery_hr_contracts.json'),
        ('pns_ai_mcp', 'contexts/discovery/discovery_hr_payroll_es_ES.json'),
        ('pns_ai_mcp', 'contexts/discovery/discovery_hr_payroll.json'),
        ('pns_ai_mcp', 'contexts/discovery/discovery_invoice_concepts_es_ES.json'),
        ('pns_ai_mcp', 'contexts/discovery/discovery_invoice_concepts.json'),
        ('pns_ai_mcp', 'contexts/discovery/discovery_partners_es_ES.json'),
        ('pns_ai_mcp', 'contexts/discovery/discovery_partners.json'),
        ('pns_ai_mcp', 'contexts/discovery/discovery_trial_balance_es_ES.json'),
        ('pns_ai_mcp', 'contexts/discovery/discovery_trial_balance.json'),
        ('pns_ai_mcp', 'contexts/domain/accounting_imbalances.xml'),
        ('pns_ai_mcp', 'contexts/domain/account.xml'),
        ('pns_ai_mcp', 'contexts/domain/business_documents.xml'),
        ('pns_ai_mcp', 'contexts/domain/cost_accounting.xml'),
        ('pns_ai_mcp', 'contexts/domain/dates.xml'),
        ('pns_ai_mcp', 'contexts/domain/email.md'),
        ('pns_ai_mcp', 'contexts/domain/fetch_url_recipe/fetch_url_recipe.xml'),
        ('pns_ai_mcp', 'contexts/domain/filters.xml'),
        ('pns_ai_mcp', 'contexts/domain/geography.xml'),
        ('pns_ai_mcp', 'contexts/domain/hr_contracts/hr_contracts.xml'),
        ('pns_ai_mcp', 'contexts/domain/hr_payroll/hr_payroll_accounting_present.xml'),
        ('pns_ai_mcp', 'contexts/domain/hr_payroll/hr_payroll_de_DE.xml'),
        ('pns_ai_mcp', 'contexts/domain/hr_payroll/hr_payroll_en_US.xml'),
        ('pns_ai_mcp', 'contexts/domain/hr_payroll/hr_payroll_es_AR.xml'),
        ('pns_ai_mcp', 'contexts/domain/hr_payroll/hr_payroll_es_ES.xml'),
        ('pns_ai_mcp', 'contexts/domain/hr_payroll/hr_payroll_es_MX.xml'),
        ('pns_ai_mcp', 'contexts/domain/hr_payroll/hr_payroll_fr_FR.xml'),
        ('pns_ai_mcp', 'contexts/domain/hr_payroll/hr_payroll_it_IT.xml'),
        ('pns_ai_mcp', 'contexts/domain/hr_payroll/hr_payroll_pt_BR.xml'),
        ('pns_ai_mcp', 'contexts/domain/hr_payroll/hr_payroll.xml'),
        ('pns_ai_mcp', 'contexts/domain/invoice_concepts.xml'),
        ('pns_ai_mcp', 'contexts/domain/partners.xml'),
        ('pns_ai_mcp', 'contexts/domain/sale_order_duplicate_workflow.md'),
        ('pns_ai_mcp', 'contexts/domain/self_mcp/self_mcp.xml'),
        ('pns_ai_mcp', 'contexts/domain/trial_balance/trial_balance_es_ES.xml'),
        ('pns_ai_mcp', 'contexts/domain/trial_balance/trial_balance.xml'),
        ('pns_ai_mcp', 'contexts/locale/corporate_terms/corporate_terms_es_ES.xml'),
        ('pns_ai_mcp', 'contexts/locale/corporate_terms/corporate_terms.xml'),
        ('pns_ai_chatboo', 'contexts/discovery/discovery_page_tab_es_ES.json'),
        ('pns_ai_chatboo', 'contexts/discovery/discovery_page_tab.json'),
        ('pns_ai_chatboo', 'contexts/domain/page_tab/page_tab.xml'),
        ('pns_ai_chatboo', 'contexts/domain/presentation_grids/presentation_grids.xml'),
        ('pns_ai_chatboo', 'contexts/domain/self_chatboo/self_chatboo.xml'),
        ('pns_ai_chatboo', 'contexts/domain/ui_focus/ui_focus.xml'))
SELECT c.code, c.source_module, c.id, c.active
  FROM ai_context c
 WHERE c.source_module IN ('pns_ai_mcp', 'pns_ai_chatboo')
   AND c.owner_id IS NULL AND c.rel_path IS NOT NULL
   AND NOT EXISTS (SELECT 1 FROM d WHERE d.m = c.source_module AND d.p = c.rel_path)
 ORDER BY 2, 1;

\echo '## skills que reescribe (code|source_module|id|estado|write_uid)'
WITH f(code) AS (VALUES ('billing'), ('financial_health'), ('forecast')),
r AS (
    SELECT f.code AS fcode, s.*
      FROM f LEFT JOIN LATERAL (
           SELECT * FROM ai_skill s
            WHERE (s.source_module = 'pns_ai_chatboo' AND s.rel_path = 'skills/system/' || f.code || '.md')
               OR s.code = f.code OR s.command = f.code
            ORDER BY (s.source_module = 'pns_ai_chatboo' AND s.rel_path = 'skills/system/' || f.code || '.md') DESC
            LIMIT 1) s ON TRUE)
SELECT fcode, source_module, id,
       CASE WHEN id IS NULL THEN 'falta: la crea'
            WHEN owner_id IS NOT NULL THEN 'con dueño: se salta'
            WHEN source_module IS DISTINCT FROM 'pns_ai_chatboo' AND source_module IS NOT NULL
                 THEN 'de otro módulo: se salta'
            WHEN NOT active THEN 'ARCHIVADA: choque code_uniq'
            WHEN write_date > :'ultimo_u'::timestamp THEN 'REESCRIBE CON EDICIÓN'
            ELSE 'reescribe sin edición' END, write_uid
  FROM r ORDER BY fcode;

\echo '## skills retiradas: las borra (code|source_module|id|activa|write_uid)'
SELECT s.code, s.source_module, s.id, s.active, s.write_uid
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

\echo '## skills nuevas que ya existen (code|source_module|id|estado)'
SELECT s.code, s.source_module, s.id,
       CASE WHEN s.owner_id IS NOT NULL THEN 'con dueño: se salta'
            WHEN s.source_module IS DISTINCT FROM 'pns_ai_chatboo' AND s.source_module IS NOT NULL
                 THEN 'de otro módulo: se salta'
            WHEN NOT s.active THEN 'ARCHIVADA: choque code_uniq'
            ELSE 'la adopta y la reescribe' END
  FROM ai_skill s
 WHERE s.code IN ('bill_draft', 'sales_board', 'top_sales', 'users')
    OR s.command IN ('bill_draft', 'sales_board', 'top_sales', 'users')
    OR (s.source_module = 'pns_ai_chatboo' AND s.rel_path IN ('skills/system/bill_draft.md',
        'skills/system/sales_board.md', 'skills/system/top_sales.md', 'skills/system/users.md'))
 ORDER BY 1;

\echo '## archivadas (tabla|source_module|n)'
SELECT 'ai_skill', coalesce(source_module, ''), count(*) FROM ai_skill WHERE NOT active GROUP BY 2
UNION ALL
SELECT 'ai_context', coalesce(source_module, ''), count(*) FROM ai_context WHERE NOT active GROUP BY 2
ORDER BY 1, 2;

\echo '## resumen P-21 (concepto|n)'
SELECT 'ai_skill total', count(*) FROM ai_skill
UNION ALL SELECT 'ai_skill archivadas', count(*) FROM ai_skill WHERE NOT active
UNION ALL SELECT 'ai_context archivados', count(*) FROM ai_context WHERE NOT active;

ROLLBACK;
