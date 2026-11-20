ly_y4() (
  set -u
  umask 077
  F=0
  chk() {
    if [ "$2" = "$3" ]; then echo "OK      $1"
    elif [ "${4:-}" = info ]; then echo "INFO    $1: esperado [$3], obtenido [$2] (no bloquea)"
    else echo "FALLO   $1: esperado [$3], obtenido [$2]"; F=$((F + 1)); fi
  }
  una() { tr '\n' ' ' | sed 's/ *$//'; }
  sec() { printf '%s\n' "$1" | awk -v s="## $2" '/^## /{p = ($0 == s); next} p'; }
  sb() { sec "$RB" "$1"; }
  sc() { sec "$RC" "$1"; }
  ver() { echo "-- $2"; sc "$1" | sed 's/^/   /'; }
  corte() { [ "$F" = 0 ] || { echo "== Y4: $F FALLO(S) en «$1». No se ha seguido: pega la salida."; exit 1; }; }
  web() { docker ps --format '{{.Names}}' | grep -cE '^odoo-dev-14-web' || true; }
  pg() { docker exec -i -e PGOPTIONS='-c default_transaction_read_only=on' odoo-dev-14-db-1 psql -U odoo -d "$1" -X -q -At -F '|' 2>&1; }
  L=~/GitHub/lab_liyben_3973
  D=~/pns_ai_3973/liyben
  R=~/GitHub/third_party
  BD=liyben_ens_14
  g() { git --no-optional-locks -C "$R" "$@"; }
  M=$(date +%Y%m%d-%H%M%S)
  O="$D/y4-$M.txt"
  A="$D/y4_antes-$M.txt"
  [ -d "$D" ] || { echo "No existe $D"; exit 1; }
  { [ ! -e "$O" ] && [ ! -e "$A" ]; } || { echo "Ya existe $O o $A: vuelve a lanzarla dentro de un segundo"; exit 1; }
  {
  echo "== Y4: «antes» por SQL sobre $BD (esquema 3.1.782). Solo lectura: no escribe en ninguna BD ni en el repo. $M"
  echo "== 1. Comprobaciones previas"
  chk "web del kit parado" "$(web)" 0
  E=$(cd "$L" && odoo-dev 14 estado 2>&1)
  chk "contexto activo (BD|repo)" "$(printf '%s\n' "$E" | sed -n 's/^ *BD=//p' | head -1)|$(printf '%s\n' "$E" | sed -n 's/^ *REPO=//p' | head -1)" "lab_liyben_3973_14|$L"
  chk "PostgreSQL del kit en marcha" "$(docker ps --format '{{.Names}}' | grep -cx odoo-dev-14-db-1 || true)" 1
  chk "clones fijados (fijados.tsv, 23 repos)" "$(wc -l < "$D/fijados.tsv" 2>/dev/null | tr -d ' ')" 23
  [ "$F" = 0 ] || echo "   (si el único FALLO es PostgreSQL: lanza «cd $L && odoo-dev 14 bd-lista», que no levanta el web, y repite Y4)"
  corte "comprobaciones previas"
  chk "$BD existe" "$(pg postgres <<< "SELECT count(*) FROM pg_database WHERE datname = '$BD';")" 1
  N=$(cd "$L" && odoo-dev 14 estado --bd "$BD" 2>&1 | grep -i 'neutraliz' | head -1)
  echo "estado --bd: $N"
  chk "$BD neutralizada por el kit" "$(printf '%s' "$N" | grep -qi 'NO neutralizada' && echo no || (printf '%s' "$N" | grep -qi 'neutralizada' && echo si || echo no))" si
  chk "sesión de psql en solo lectura" "$(pg "$BD" <<< 'SHOW transaction_read_only;')" on
  corte "comprobaciones previas"

  echo "== 2. A: git de solo lectura en $R: ai/ de 578859b (LIYBEN) frente a c6ec077"
  chk "rama" "$(g rev-parse --abbrev-ref HEAD 2>&1)" 14.0-pns-ai-3973
  chk "HEAD" "$(g rev-parse --short=7 HEAD 2>&1)" c6ec077
  chk "árbol limpio (líneas de status)" "$(g status --porcelain 2>&1 | wc -l | tr -d ' ')" 0
  chk "578859b existe en el clon local" "$(g cat-file -e '578859b^{commit}' 2>/dev/null && echo si || echo no)" si
  DF=$(g diff --no-renames --name-status 578859b c6ec077 -- pns_ai_mcp/ai pns_ai_chatboo/ai 2>&1 | LC_ALL=C sort)
  chk "cambios en ai/ por tipo" "$(printf '%s\n' "$DF" | cut -f1 | LC_ALL=C sort | uniq -c | awk '{printf "%s %s ", $2, $1}' | sed 's/ $//')" "A 15 D 12 M 19"
  chk "huella de la lista de cambios en ai/ (= del fabricante 3.1.782 a 3.1.973)" "$(printf '%s\n' "$DF" | sha256sum | cut -d' ' -f1)" f413c755fcfaf6e0ed7b1f51feb7a62b621323173496d3218f6b43715d8438d4
  [ "$F" = 0 ] || { echo "-- lista obtenida (solo nombres de archivo)"; printf '%s\n' "$DF" | sed 's/^/   /'; }
  corte "A (git)"

  echo "== 3. B: esquema de $BD y correspondencia con los archivos de 3.1.782"
  RB=$(pg "$BD" <<'SQL'
\echo '## columnas'
WITH c(t, col) AS (VALUES
        ('ir_module_module', 'id'),
        ('ir_module_module', 'name'),
        ('ir_module_module', 'state'),
        ('ir_module_module', 'latest_version'),
        ('ir_module_module', 'write_date'),
        ('ir_module_module_dependency', 'module_id'),
        ('ir_module_module_dependency', 'name'),
        ('res_users', 'id'),
        ('res_users', 'active'),
        ('res_users', 'share'),
        ('res_users', 'password'),
        ('res_groups_users_rel', 'uid'),
        ('res_groups_users_rel', 'gid'),
        ('ir_model_data', 'module'),
        ('ir_model_data', 'name'),
        ('ir_model_data', 'model'),
        ('ir_model_data', 'res_id'),
        ('ai_provider', 'id'),
        ('ai_provider', 'active'),
        ('ai_provider', 'protocol'),
        ('ai_provider', 'model_name'),
        ('ai_provider', 'no_external_failover'),
        ('ai_agent_provider', 'id'),
        ('ai_agent_provider', 'agent_id'),
        ('ai_agent_provider', 'priority'),
        ('ai_agent_provider', 'active'),
        ('ai_agent_provider', 'skip_sync_fallback'),
        ('ai_agent_provider', 'provider_id'),
        ('ai_agent', 'id'),
        ('ai_agent', 'code'),
        ('ir_cron', 'id'),
        ('ir_cron', 'active'),
        ('ir_cron', 'interval_number'),
        ('ir_cron', 'interval_type'),
        ('ir_cron', 'numbercall'),
        ('ir_cron', 'ir_actions_server_id'),
        ('ir_act_server', 'id'),
        ('ir_act_server', 'code'),
        ('ir_config_parameter', 'key'),
        ('ir_config_parameter', 'value'),
        ('ai_safe_operation', 'id'),
        ('ai_safe_operation', 'status'),
        ('ai_safe_operation', 'executed'),
        ('ai_safe_operation', 'operation_data'),
        ('ai_trusted_action', 'id'),
        ('ai_api_server', 'id'),
        ('ai_change_journal', 'op'),
        ('ai_change_journal', 'after_json'),
        ('ai_change_journal', 'write_uid'),
        ('ai_change_journal', 'create_uid'),
        ('chatboo_session', 'id'),
        ('chatboo_session', 'create_date'),
        ('chatboo_session', 'user_id'),
        ('ai_log', 'id'),
        ('ai_log', 'agent_id'),
        ('ai_skill', 'id'),
        ('ai_skill', 'code'),
        ('ai_skill', 'command'),
        ('ai_skill', 'active'),
        ('ai_skill', 'is_system'),
        ('ai_skill', 'source_module'),
        ('ai_skill', 'rel_path'),
        ('ai_skill', 'owner_id'),
        ('ai_skill', 'write_date'),
        ('ai_skill', 'write_uid'),
        ('ai_context', 'id'),
        ('ai_context', 'code'),
        ('ai_context', 'active'),
        ('ai_context', 'source_module'),
        ('ai_context', 'rel_path'),
        ('ai_context', 'owner_id'),
        ('ai_context', 'write_date'),
        ('ai_context', 'write_uid'),
        ('ai_context', 'last_used'),
        ('res_lang', 'code'),
        ('res_lang', 'active'),
        ('ir_translation', 'lang'),
        ('res_partner', 'signup_token'),
        ('iap_account', 'id'))
SELECT c.t || '.' || c.col, EXISTS (SELECT 1 FROM information_schema.columns i
        WHERE i.table_schema = 'public' AND i.table_name = c.t AND i.column_name = c.col)
  FROM c ORDER BY 1;
\echo '## columnas fit'
SELECT string_agg(column_name, ' ' ORDER BY column_name) FROM information_schema.columns
 WHERE table_schema = 'public' AND table_name = 'ai_provider' AND column_name LIKE 'fit\_%' AND column_name <> 'fit_chips_html';
\echo '## tablas'
SELECT to_regclass('public.ai_provider') IS NOT NULL,
       (to_regclass('public.ai_provider_role') IS NOT NULL)::int + (to_regclass('public.chatboo_canvas_page') IS NOT NULL)::int;
\echo '## contextos archivos'
WITH f(m, p) AS (VALUES
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
SELECT CASE WHEN c.id IS NULL THEN 'archivo sin fila' WHEN f.m IS NULL THEN 'fila sin archivo' ELSE 'ok' END,
       coalesce(c.id::text, ''), coalesce(c.code, ''), coalesce(c.source_module, f.m, '(vacío)'),
       coalesce(c.rel_path, f.p, '(vacío)'), (c.owner_id IS NOT NULL)
  FROM f FULL JOIN ai_context c ON c.source_module = f.m AND c.rel_path = f.p
 ORDER BY 1, 4, 5;
\echo '## skills archivos'
WITH f(m, p) AS (VALUES
        ('pns_ai_chatboo', 'skills/system/annual_billing.md'),
        ('pns_ai_chatboo', 'skills/system/billing.md'),
        ('pns_ai_chatboo', 'skills/system/credit_facility.md'),
        ('pns_ai_chatboo', 'skills/system/customer_risk_analysis.md'),
        ('pns_ai_chatboo', 'skills/system/dashboard.md'),
        ('pns_ai_chatboo', 'skills/system/financial_health.md'),
        ('pns_ai_chatboo', 'skills/system/forecast.md'),
        ('pns_ai_chatboo', 'skills/system/sys_info.md'),
        ('pns_ai_chatboo', 'skills/system/users_all.md'),
        ('pns_ai_chatboo', 'skills/system/users_logged.md'))
SELECT CASE WHEN s.id IS NULL THEN 'archivo sin fila' WHEN f.m IS NULL THEN 'fila sin archivo' ELSE 'ok' END,
       coalesce(s.id::text, ''), coalesce(s.code, ''), coalesce(s.source_module, f.m, '(vacío)'),
       coalesce(s.rel_path, f.p, '(vacío)'), (s.owner_id IS NOT NULL)
  FROM f FULL JOIN ai_skill s ON s.source_module = f.m AND s.rel_path = f.p
 ORDER BY 1, 4, 5;
\echo '## fin'
SQL
)
  chk "consultas sin error" "$(printf '%s\n' "$RB" | grep -c 'ERROR:' || true)" 0
  printf '%s\n' "$RB" | grep 'ERROR:' | head -5 | sed 's/^/   /'
  chk "marcador final de la salida SQL" "$(printf '%s\n' "$RB" | grep -cx '## fin' || true)" 1
  chk "columnas que usa Y4 (en la lista|presentes)" "$(sb columnas | awk -F'|' '{n++; if ($2 == "t") p++} END {printf "%d|%d\n", n, p}')" "79|79"
  chk "columnas que faltan" "$(sb columnas | awk -F'|' '$2 != "t" {print $1}' | una)" ""
  chk "columnas fit_* de ai_provider (3.1.782: 5, sin fit_design)" "$(sb 'columnas fit')" "fit_audio fit_conversation fit_decision fit_video fit_vision"
  chk "ai_provider existe | tablas de 3.1.973 ya presentes (ai_provider_role, chatboo_canvas_page)" "$(sb tablas)" "t|0"
  cuenta() { sb "$1" | awk -F'|' '{if ($2 != "") f++; if ($1 == "fila sin archivo") s++; if ($1 == "archivo sin fila") a++; if ($6 == "t") d++; if ($1 == "ok") o++} END {printf "%d|%d|%d|%d|%d\n", f, s, a, d, o}'; }
  raros() { sb "$1" | awk -F'|' '$1 != "ok" || $6 == "t"' | head -20 | sed 's/^/   /'; }
  chk "contextos frente a los 56 archivos (filas|sin archivo|archivos sin fila|con dueño|emparejados)" "$(cuenta 'contextos archivos')" "56|0|0|0|56"
  [ -z "$(raros 'contextos archivos')" ] || { echo "-- contextos no emparejados o con dueño (caso|id|code|source_module|rel_path|con dueño; 20 como mucho)"; raros 'contextos archivos'; }
  chk "skills frente a los 10 archivos (filas|sin archivo|archivos sin fila|con dueño|emparejadas)" "$(cuenta 'skills archivos')" "10|0|0|0|10"
  [ -z "$(raros 'skills archivos')" ] || { echo "-- skills no emparejadas o con dueño (caso|id|code|source_module|rel_path|con dueño; 20 como mucho)"; raros 'skills archivos'; }
  corte "B (esquema y correspondencia)"

  echo "== 4. C: «antes» (salida SQL completa en $A, para Y7)"
  RC=$(pg "$BD" <<'SQL'
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
SQL
)
  printf '%s\n' "$RC" > "$A"
  echo "guardado: $A ($(wc -l < "$A" | tr -d ' ') líneas, SHA-256 $(sha256sum "$A" | cut -d' ' -f1))"
  chk "consultas sin error" "$(printf '%s\n' "$RC" | grep -c 'ERROR:' || true)" 0
  printf '%s\n' "$RC" | grep 'ERROR:' | head -5 | sed 's/^/   /'
  chk "marcador final de la salida SQL" "$(printf '%s\n' "$RC" | grep -cx '## fin' || true)" 1
  chk "versiones (nombre|estado|versión), = I0" "$(sc versiones | una)" "pns_ai_chatboo|installed|14.0.2.1.453 pns_ai_mcp|installed|14.0.3.1.782 pns_base|installed|14.0.1.2.32"
  chk "módulos a medio instalar o actualizar" "$(sc 'estados a medias')" 0
  chk "módulos instalados, = I0" "$(sc instalados)" 215
  chk "dependientes de los pns_*" "$(sc dependientes | una)" ""
  chk "fecha del último -u de pns_ai_mcp y pns_ai_chatboo (write_date, UTC: $(sc 'ultimo -u'))" "$(sc 'ultimo -u' | cut -c1-10)" 2026-10-16 info
  chk "AI Administrators (id|activo|Ajustes|contraseña local|AI Conversational), = I0" "$(sc 'ai admins' | una)" "2|t|t|t|f 6|t|t|t|t 7|t|t|t|t"
  chk "P-11 (AI Administrators|sin AI Conversational): el 2 lo ganará en el -u (D64)" "$(sc p11)" "3|1"
  chk "proveedores (id|activo|protocolo|modelo|conv|audio|visión|vídeo|decisión|sin failover externo), = I0" "$(sc proveedores | una)" "1|f|openai|models/gemini-3.5-flash|t|f|t|f|t|t 2|t|openai|Qwen3.5-9B|t|f|t|f|f|f"
  ver cadena "cadena ai_agent_provider, sin api_key (id|agente|prioridad|activo|skip_sync_fallback|provider_id|proveedor activo); para Y7"
  chk "crons de pns_* (xml_id|activo|intervalo|numbercall): los 6 de I0, desactivados por la neutralización" "$(sc crons | una)" "pns_ai_chatboo.ir_cron_chatboo_async_maintenance|f|5 minutes|-1 pns_ai_mcp.ir_cron_ai_api_result_cache_gc|f|1 hours|-1 pns_ai_mcp.ir_cron_ai_fetch_cache_gc|f|1 hours|-1 pns_ai_mcp.ir_cron_ai_log_retention|f|1 days|-1 pns_ai_mcp.ir_cron_ai_safe_operation_expire|f|5 minutes|-1 pns_base.ir_cron_pns_export_purge|f|1 hours|-1"
  echo "INFO    en LIYBEN (I0) esos 6 crons están activos; en la copia los desactivó la neutralización (no bloquea)"
  chk "crons activos en la copia (todos)" "$(sc 'crons activos')" 0
  chk "crons de NUEVO-2 antes del -u (el parche 35 los corregirá), = I0" "$(sc 'crons nuevo2' | una)" "ir_cron_ai_api_result_cache_gc|model.gc_expired() ir_cron_ai_fetch_cache_gc|model.gc_expired()"
  chk "parámetros (clave|valor), = I0" "$(sc parametros | una)" "pns_ai_chatboo.history_retention_days|30 pns_ai_mcp.log_retention_days|30 pns_ai_mcp.url_access_policy|whitelist_only"
  chk "operaciones pending o confirmed sin ejecutar, = I0" "$(sc 'operaciones no terminales' | una)" ""
  chk "operaciones no terminales con pasos sobre ai.trusted.action (parche 32)" "$(sc 'operaciones trusted')" 0
  ver 'operaciones por status' "ai_safe_operation por status (status|n); para Y7"
  ver trusted "ai_trusted_action (n|max_id); para Y7"
  chk "servidores ai.api.server (PNS-17), = I0" "$(sc 'servidores api')" 0
  chk "diario (filas|unlink en papelera|reescritas por otro), = I0" "$(sc diario)" "2|0|0"
  chk "Chatboo (sesiones|id máximo|primera, mes|usuarios), = I0" "$(sc chatboo)" "1|1|2026-10|1"
  chk "ai_log (filas|con agent_id|max_id), = I0" "$(sc ai_log)" "0|0|0"
  chk "skills (code|activa|sistema|con xml_id), = I0" "$(sc skills | una)" "annual_billing|t|t|f billing|t|t|f credit_facility|t|t|f customer_risk_analysis|t|t|f dashboard|t|t|f financial_health|t|t|f forecast|t|t|f sys_info|t|t|f users_all|t|t|f users_logged|t|t|f"
  ver 'skills detalle' "skills (id|code|command|source_module|rel_path|activa|write_uid); para Y7"
  chk "contextos (total|activos|con xml_id), = I0" "$(sc contextos)" "56|56|0"
  chk "contextos por módulo (source_module|n|activos)" "$(sc 'contextos por modulo' | una)" "pns_ai_chatboo|3|3 pns_ai_mcp|53|53"
  ver 'modulos iap' "módulos crm, iap, partner_autocomplete y sms (name|state); para Y7"
  chk "es_ES activo, = I0" "$(sc idioma)" "es_ES|t"
  chk "traducciones es_ES, = I0" "$(sc 'traducciones es_ES')" 45482
  chk "tokens de registro (D50 no se aplica en el ensayo), = I0" "$(sc tokens)" 8
  chk "iap_account (filas), = I0" "$(sc iap)" 1

  echo "== 5. C: P-21 de LIYBEN (qué hará el -u de 3.1.973 con los contextos y skills de fábrica)"
  ver 'p21 contextos reescribe' "contextos que reescribe (módulo:rel_path|estado|id|write_uid)"
  echo "-- contextos que reescribe: resumen (n estado)"; sc 'p21 contextos reescribe' | cut -d'|' -f2 | LC_ALL=C sort | uniq -c | sed 's/^ */   /'
  chk "contextos que reescribe sin edición (con o sin uso posterior al último -u)" "$(sc 'p21 contextos reescribe' | cut -d'|' -f2 | grep -cE '^reescribe sin edición( \(solo uso\))?$' || true)" 13
  echo "INFO    «solo uso»: write_date posterior al último -u pero igual a last_used y write_uid 1 (el UPDATE del contador de uso, ai_context.py:1224-1231 de 3.1.782); no es una edición (no bloquea)"
  chk "contextos nuevos (code|estado)" "$(sc 'p21 contextos nuevos' | una)" "discovery_page_tab|falta: lo crea discovery_page_tab_es_ES|falta: lo crea page_tab|falta: lo crea"
  chk "contextos de fábrica sin archivo en 3.1.973 (los borraría)" "$(sc 'p21 contextos retirados' | una)" ""
  ver 'p21 skills reescribe' "skills que reescribe (code|estado|id|write_uid)"
  chk "skills que reescribe (code|estado)" "$(sc 'p21 skills reescribe' | cut -d'|' -f1,2 | una)" "billing|reescribe sin edición financial_health|reescribe sin edición forecast|reescribe sin edición"
  ver 'p21 skills retiradas' "skills retiradas: las borra (code|id|activa|write_uid)"
  chk "skills retiradas (code)" "$(sc 'p21 skills retiradas' | cut -d'|' -f1 | una)" "annual_billing credit_facility customer_risk_analysis sys_info users_all users_logged"
  chk "skills nuevas que ya existen (se adoptarían o chocarían)" "$(sc 'p21 skills nuevas que ya existen' | una)" ""
  chk "contextos y skills archivados" "$(sc 'p21 archivadas' | una)" ""
  if [ "$F" = 0 ]; then echo "== Y4: TODO OK. Corte: pega la salida antes de Y5."; else echo "== Y4: $F FALLO(S). No sigas: pega la salida."; fi
  } 2>&1 | tee "$O"
  echo "Guardado en $O"
)
ly_y4 "$@"
