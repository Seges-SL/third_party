ly_y7() (
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
  sd() { sec "$RD" "$1"; }
  sa() { sec "$RA" "$1"; }
  ver() { echo "-- $2"; sd "$1" | sed 's/^/   /'; }
  igual() { chk "$2, = antes (Y4)" "$(sd "$1" | una)" "$(sa "$1" | una)" ${3:-}; }
  corte() { [ "$F" = 0 ] || { echo "== Y7: $F FALLO(S) en «$1». No se ha seguido: pega la salida."; exit 1; }; }
  web() { docker ps --format '{{.Names}}' | grep -cE '^odoo-dev-14-web' || true; }
  pg() { docker exec -i -e PGOPTIONS='-c default_transaction_read_only=on' odoo-dev-14-db-1 psql -U odoo -d "$1" -X -q -At -F '|' 2>&1; }
  L=~/GitHub/lab_liyben_3973
  D=~/pns_ai_3973/liyben
  BD=liyben_ens_14
  ANTES="$D/y4_antes-20261119-135706.txt"
  HA=ab7571b7ec9f4d8de418abbb8475eb050df3f6ef480c9dcfcf8ecb8f44c0958c
  MK3='== Y3: TODO OK. Corte: pega la salida (y la paridad) antes de Y4.'
  MK5='== Y5: TODO OK. Corte: pega la salida antes de Y6.'
  M=$(date +%Y%m%d-%H%M%S)
  O="$D/y7-$M.txt"
  A="$D/y7_despues-$M.txt"
  [ -d "$D" ] || { echo "No existe $D"; exit 1; }
  { [ ! -e "$O" ] && [ ! -e "$A" ]; } || { echo "Ya existe $O o $A: vuelve a lanzarla dentro de un segundo"; exit 1; }
  {
  echo "== Y7: «después» por SQL sobre $BD (esquema 3.1.973), contra el «antes» de Y4 y el «después» de Y6. Solo lectura. $M"
  echo "== 1. Comprobaciones previas"
  chk "web del kit parado" "$(web)" 0
  E=$(cd "$L" && odoo-dev 14 estado 2>&1)
  chk "contexto activo (BD|repo)" "$(printf '%s\n' "$E" | sed -n 's/^ *BD=//p' | head -1)|$(printf '%s\n' "$E" | sed -n 's/^ *REPO=//p' | head -1)" "lab_liyben_3973_14|$L"
  chk "PostgreSQL del kit en marcha" "$(docker ps --format '{{.Names}}' | grep -cx odoo-dev-14-db-1 || true)" 1
  [ "$F" = 0 ] || echo "   (si el único FALLO es PostgreSQL: lanza «cd $L && odoo-dev 14 bd-lista», que no levanta el web, y repite Y7)"
  corte "comprobaciones previas"
  chk "«antes» de Y4 intacto (huella)" "$(sha256sum "$ANTES" 2>/dev/null | cut -d' ' -f1)" "$HA"
  L3=$(ls -t "$D"/y3-CARGAR-*.txt 2>/dev/null | head -1); L3=${L3:-/dev/null}
  Y5=$(ls -t "$D"/y5-ACTUALIZAR-*.txt 2>/dev/null | head -1); Y5=${Y5:-/dev/null}
  Y6=$(ls -t "$D"/y6-APLICAR_*-*.txt 2>/dev/null | head -1); Y6=${Y6:-/dev/null}
  chk "última Y3 CARGAR ($(basename "$L3")) con TODO OK" "$(grep -cx -- "$MK3" "$L3" 2>/dev/null || true)" 1
  chk "último Y5 ACTUALIZAR ($(basename "$Y5")) con TODO OK y posterior a esa carga" "$(grep -cx -- "$MK5" "$Y5" 2>/dev/null || true)|$( [ "$Y5" -nt "$L3" ] && echo posterior || echo anterior)" "1|posterior"
  chk "último Y6 APLICAR ($(basename "$Y6")) de la v3 con TODO OK y posterior al Y5" "$(grep -cE '^== Y6 v3: TODO OK \(APLICAR_(B|BP|C)\)\. Corte: pega la salida antes de Y7\.$' "$Y6" 2>/dev/null || true)|$( [ "$Y6" -nt "$Y5" ] && echo posterior || echo anterior)" "1|posterior"
  DY6=$(printf '%s' "$Y6" | sed 's#/y6-APLICAR_#/y6_despues-APLICAR_#')
  chk "«después» de ese Y6 ($(basename "$DY6")) completo" "$(grep -cx '## fin' "$DY6" 2>/dev/null || true)" 1
  LU=$(sed -n 's#.*(log: .*/actualizar-\([0-9]\{8\}-[0-9]\{6\}\)\.log)$#\1#p' "$Y5" | head -1)
  T0S=$( [ -n "$LU" ] && date -d "$(printf '%s' "$LU" | sed 's/^\(....\)\(..\)\(..\)-\(..\)\(..\)\(..\)$/\1-\2-\3 \4:\5:\6/')" +%s 2>/dev/null)
  T0U=$( [ -n "$T0S" ] && date -u -d "@$T0S" '+%Y-%m-%d %H:%M:%S')
  chk "inicio del -u de Y5 (del nombre de su log, hora local $LU): leído y entre la carga de Y3 y Y6" "$( [ -n "$T0S" ] && [ "$T0S" -ge "$(stat -c %Y "$L3")" ] && [ "$T0S" -lt "$(stat -c %Y "$Y6")" ] && echo si || echo no)" si
  echo "   inicio del -u en UTC (como guarda Odoo create_date y write_date): $T0U"
  chk "sesión de psql en solo lectura" "$(pg "$BD" <<< 'SHOW transaction_read_only;')" on
  corte "comprobaciones previas"
  RA=$(cat "$ANTES")

  echo "== 2. «Después» (salida SQL completa en $A)"
  RD=$( { printf "\\\\set t0 '%s'\n" "$T0U"; cat <<'SQL'; } | pg "$BD"
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
SQL
)
  printf '%s\n' "$RD" > "$A"
  echo "guardado: $A ($(wc -l < "$A" | tr -d ' ') líneas, SHA-256 $(sha256sum "$A" | cut -d' ' -f1))"
  chk "consultas sin error" "$(printf '%s\n' "$RD" | grep -ciE 'ERROR:|psql: error' || true)" 0
  printf '%s\n' "$RD" | grep -iE 'ERROR:|psql: error' | head -5 | cut -c1-160 | sed 's/^/   /'
  chk "marcador final de la salida SQL" "$(printf '%s\n' "$RD" | grep -cx '## fin' || true)" 1
  corte "consultas"

  echo "== 3. Módulos, AI Administrators y proveedores"
  chk "versiones (nombre|estado|versión): las de la rama" "$(sd versiones | una)" "pns_ai_chatboo|installed|14.0.2.1.587 pns_ai_mcp|installed|14.0.3.1.973 pns_base|installed|14.0.1.2.69"
  chk "módulos a medio instalar o actualizar" "$(sd 'estados a medias')" 0
  chk "módulos instalados, = I0" "$(sd instalados)" 215
  igual dependientes "dependientes de los pns_* (ninguno)"
  chk "AI Administrators (id|activo|Ajustes|contraseña local|AI Conversational): el 2 lo ganó en el -u (D64)" "$(sd 'ai admins' | una)" "2|t|t|t|t 6|t|t|t|t 7|t|t|t|t"
  chk "P-11 (AI Administrators|sin AI Conversational)" "$(sd p11)" "3|0"
  chk "proveedores (id|activo|protocolo|modelo|sin failover externo), = antes sin las fit_*" "$(sd proveedores | una)" "$(sa proveedores | awk -F'|' '{ print $1 "|" $2 "|" $3 "|" $4 "|" $10 }' | una)"
  chk "roles por proveedor (id|activo|modelo|roles): Decisión fuera del 1 y Diseño dentro (D67)" "$(sd 'roles por proveedor' | una)" "1|f|models/gemini-3.5-flash|conversation,vision,design 2|t|Qwen3.5-9B|conversation,vision"
  chk "rol Diseño sin alternativa (xml_id|code|activo|use_fallback|alternativa)" "$(sd 'rol Diseño' | una)" "pns_ai_mcp.ai_provider_role_design|design|t|f|conversation"
  chk "rol Diseño solo en el proveedor 1, inactivo (D62)" "$(sd 'con Diseño' | una)" "1|f|f"
  chk "rol Decisión sin titulares" "$(sd 'con Decisión' | una)" ""
  ver roles "roles (code|activo|use_fallback|alternativa)"
  igual cadena "cadena de proveedores (id|agente|prioridad|activo|skip_sync_fallback|provider_id|proveedor activo)"

  echo "== 4. Crons"
  chk "crons de pns_* (xml_id|activo|intervalo|numbercall): los 6 de antes y el nuevo de la papelera del diario, todos desactivados" "$(sd crons | una)" "pns_ai_chatboo.ir_cron_chatboo_async_maintenance|f|5 minutes|-1 pns_ai_mcp.ir_cron_ai_api_result_cache_gc|f|1 hours|-1 pns_ai_mcp.ir_cron_ai_fetch_cache_gc|f|1 hours|-1 pns_ai_mcp.ir_cron_ai_journal_trash|f|1 days|-1 pns_ai_mcp.ir_cron_ai_log_retention|f|1 days|-1 pns_ai_mcp.ir_cron_ai_safe_operation_expire|f|5 minutes|-1 pns_base.ir_cron_pns_export_purge|f|1 hours|-1"
  chk "crons activos en la copia (todos)" "$(sd 'crons activos')" 0
  chk "crons creados en el -u: el que el kit reactivó y volvió a desactivar (journal_trash_cron.xml, active=True)" "$(sd 'crons creados en el -u' | una)" "pns_ai_mcp.ir_cron_ai_journal_trash"
  echo "INFO    en LIYBEN real los 6 de antes siguen activos (noupdate) y pns_ai_mcp.ir_cron_ai_journal_trash quedará ACTIVO tras el -u: para el documento"
  chk "crons de NUEVO-2 corregidos por el parche 35" "$(sd 'crons nuevo2' | una)" "ir_cron_ai_api_result_cache_gc|model._gc_expired() ir_cron_ai_fetch_cache_gc|model._gc_expired()"

  echo "== 5. Parámetros, operaciones, diario, Chatboo y registro"
  igual parametros "parámetros (clave|valor)"
  chk "parámetro pns_ai_mcp.journal_trash_days (clave|valor)" "$(sd 'parametro papelera' | una)" "" info
  chk "operaciones pending o confirmed sin ejecutar" "$(sd 'operaciones no terminales' | una)" ""
  chk "operaciones no terminales con pasos sobre ai.trusted.action" "$(sd 'operaciones trusted')" 0
  igual 'operaciones por status' "ai_safe_operation por status (status|n)" info
  igual trusted "ai_trusted_action (n|max_id)" info
  chk "servidores ai.api.server (PNS-17)" "$(sd 'servidores api')" 0
  igual diario "diario (filas|unlink en papelera|reescritas por otro)"
  igual chatboo "Chatboo (sesiones|id máximo|primera, mes|usuarios)"
  chk "ai_log (filas|max_id; sin agent_id desde el -u)" "$(sd ai_log)" "0|0"

  echo "== 6. Skills y contextos (P-21)"
  chk "skills (code): 6 retiradas y 6 nuevas, como en el staging" "$(sd skills | cut -d'|' -f1 | una)" "bill_draft billing customer_360 dashboard financial_health forecast pipeline sales_board top_sales users"
  chk "skills activas" "$(sd skills | awk -F'|' '$2 == "t"' | grep -c . || true)" 10
  ver skills "skills (code|activa|sistema|con xml_id)"
  ver 'skills detalle' "skills (id|code|command|source_module|rel_path|activa|write_uid|escrita en el -u)"
  chk "skills que P-21 reescribe (billing, financial_health, forecast) con write_date del -u" "$(sd 'skills reescritas' | una)" "billing financial_health forecast" info
  chk "contextos (total|activos)" "$(sd contextos | cut -d'|' -f1,2)" "59|59"
  echo "INFO    contextos con xml_id: $(sd contextos | cut -d'|' -f3) (antes: $(sa contextos | cut -d'|' -f3))"
  chk "contextos por módulo (source_module|n|activos)" "$(sd 'contextos por modulo' | una)" "pns_ai_chatboo|6|6 pns_ai_mcp|53|53"
  chk "contextos nuevos (code|módulo|rel_path|activo|creado en el -u)" "$(sd 'contextos nuevos' | una)" "discovery_page_tab|pns_ai_chatboo|contexts/discovery/discovery_page_tab.json|t|t discovery_page_tab_es_ES|pns_ai_chatboo|contexts/discovery/discovery_page_tab_es_ES.json|t|t page_tab|pns_ai_chatboo|contexts/domain/page_tab/page_tab.xml|t|t"
  chk "contextos creados antes del -u (los 56 de antes: ninguno retirado)" "$(sd 'contextos de antes')" 56
  chk "contextos escritos en el -u (de los 13 que P-21 reescribe|de los otros 43)" "$(sd 'contextos reescritos')" "13|0" info
  chk "contextos y skills archivados" "$(sd archivadas | una)" ""

  echo "== 7. Idioma, traducciones, tokens e IAP"
  igual 'modulos iap' "módulos crm, iap, partner_autocomplete y sms (name|state)"
  chk "es_ES activo" "$(sd idioma)" "es_ES|t"
  chk "traducciones es_ES, = después de Y6 (la recarga B′ no añade)" "$(sd 'traducciones es_ES')" "$(sec "$(cat "$DY6")" traducciones | cut -d'|' -f1)"
  chk "traducciones fuera de los pns_* (n|huella), = después de Y6" "$(sd 'traducciones fuera de pns')" "$(sec "$(cat "$DY6")" 'traducciones fuera de pns')"
  chk "traducciones de los pns_* (módulo|n), = después de Y6" "$(sd 'traducciones pns' | una)" "$(sec "$(cat "$DY6")" 'traducciones pns' | una)"
  igual tokens "tokens de registro (D50 no se aplica en el ensayo)"
  igual iap "iap_account (filas)"
  if [ "$F" = 0 ]; then echo "== Y7: TODO OK. Corte: pega la salida antes de RESTAURAR."; else echo "== Y7: $F FALLO(S). No sigas: pega la salida."; fi
  } 2>&1 | tee "$O"
  echo "Guardado en $O"
)
ly_y7 "$@"
