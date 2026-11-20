ly_i0() (
  set -u
  F=0
  chk() {
    if [ "$2" = "$3" ]; then echo "OK      $1"
    elif [ "${4:-}" = info ]; then echo "INFO    $1: esperado [$3], obtenido [$2] (no bloquea)"
    else echo "FALLO   $1: esperado [$3], obtenido [$2]"; F=$((F + 1)); fi
  }
  una() { tr '\n' ' ' | sed 's/ *$//'; }
  oculta() { sed -E 's/((--db_password|--db-password|-w)[= ]+)[^ "]+/\1***/g; s/(password[^ =]*[= ]+)[^ "]+/\1***/Ig'; }
  lysql() { docker exec -i -e PGOPTIONS='-c default_transaction_read_only=on' odoo14_db \
      sh -c 'psql -U "$POSTGRES_USER" -d LIYBEN -X -q -At -F "|"' 2>&1; }
  CLON=/opt/odoo/addons/custom/third_party
  g() { git --no-optional-locks -c safe.directory="$CLON" -C "$CLON" "$@"; }
  echo "== I0 (VPS, LIYBEN): inventario de solo lectura; no escribe nada en el VPS ni en LIYBEN. $(date -u '+%F %T') UTC"

  echo "== 1. Contenedores"
  chk "odoo14_server en marcha" "$(docker ps --format '{{.Names}}' | grep -cx odoo14_server)" 1
  chk "odoo14_db en marcha" "$(docker ps --format '{{.Names}}' | grep -cx odoo14_db)" 1
  [ "$F" = 0 ] || { echo "== I0: $F FALLO(S). No sigas: pega la salida."; exit 1; }
  chk "imagen de odoo14_server" "$(docker inspect -f '{{.Config.Image}}' odoo14_server)" odoo-web info
  for k in odoo14_server odoo14_db; do
    echo "compose de $k (proyecto|servicio|carpeta|archivos): $(docker inspect -f '{{index .Config.Labels "com.docker.compose.project"}}|{{index .Config.Labels "com.docker.compose.service"}}|{{index .Config.Labels "com.docker.compose.project.working_dir"}}|{{index .Config.Labels "com.docker.compose.project.config_files"}}' "$k")"
  done
  echo "reinicio de odoo14_server: $(docker inspect -f '{{.HostConfig.RestartPolicy.Name}}' odoo14_server)"
  echo "puertos de odoo14_server: $(docker port odoo14_server | una)"
  echo "-- montajes de odoo14_server (origen -> destino, rw/ro)"
  docker inspect -f '{{range .Mounts}}{{.Source}} -> {{.Destination}} {{if .RW}}rw{{else}}ro{{end}}{{"\n"}}{{end}}' odoo14_server | sed '/^$/d; s/^/   /'
  echo "-- orden de arranque (contraseñas ocultas)"
  echo "   entrypoint/cmd: $(docker inspect -f '{{json .Config.Entrypoint}} {{json .Config.Cmd}}' odoo14_server | oculta)"
  docker top odoo14_server -o args 2>&1 | sed 1d | oculta | cut -c1-160 | sort | uniq -c | head -8 | sed 's/^/   /'

  echo "== 2. odoo.conf (solo claves sin secretos)"
  RC=$(docker inspect -f '{{range .Config.Env}}{{println .}}{{end}}' odoo14_server | sed -n 's/^ODOO_RC=//p' | head -1)
  CONF=""
  for c in $RC /etc/odoo/odoo.conf /etc/odoo/openerp-server.conf; do
    if docker exec odoo14_server test -r "$c" 2>/dev/null; then CONF=$c; break; fi
  done
  echo "archivo: ${CONF:-no encontrado}"
  if [ -n "$CONF" ]; then
    CF=$(docker exec odoo14_server cat "$CONF" 2>/dev/null | grep -E '^[[:space:]]*(addons_path|workers|max_cron_threads|logfile|log_level|db_name|dbfilter|list_db|proxy_mode|limit_time_real|limit_time_cpu|limit_memory_hard|limit_memory_soft|data_dir|db_host|db_port|db_user|http_port|longpolling_port|server_wide_modules)[[:space:]]*=' | sed 's/[[:space:]]*=[[:space:]]*/ = /')
    printf '%s\n' "$CF" | sed 's/^/   /'
    chk "workers" "$(printf '%s\n' "$CF" | sed -n 's/^ *workers = //p')" 2 info
  fi

  echo "== 3. Bases de datos en odoo14_db (D9: solo LIYBEN)"
  chk "bases de datos" "$(echo "SELECT datname FROM pg_database WHERE NOT datistemplate AND datname <> 'postgres' ORDER BY 1;" | lysql | una)" LIYBEN
  echo "tamaño de LIYBEN: $(echo "SELECT pg_size_pretty(pg_database_size('LIYBEN'));" | lysql)"

  echo "== 4. Clon de third_party ($CLON; git sin escribir: --no-optional-locks)"
  chk "propietario (UID)" "$(stat -c %u "$CLON" 2>&1)" 101
  chk "rama" "$(g rev-parse --abbrev-ref HEAD 2>&1)" 14.0-pns-ai-3
  chk "HEAD" "$(g rev-parse --short=7 HEAD 2>&1)" 578859b
  chk "status (líneas)" "$(g status --porcelain 2>&1 | wc -l | tr -d ' ')" 0
  echo "remote.origin.fetch: $(g config --get-all remote.origin.fetch | una)"
  echo "referencias: $(g for-each-ref --format='%(refname:short)=%(objectname:short)' refs/heads refs/remotes | una)"
  chk "marcadores «Seges: parche de compatibilidad» (§3.2)" "$(cd "$CLON" && grep -rn 'Seges: parche de compatibilidad' pns_base pns_ai_mcp pns_ai_chatboo 2>/dev/null | wc -l | tr -d ' ')" 10 info
  echo "árbol de los tres pns_* (archivos y huella): $( ( cd "$CLON" && find pns_base pns_ai_mcp pns_ai_chatboo -type f -not -path '*/__pycache__/*' -not -name '*.pyc' | wc -l ) | tr -d ' ') $( ( cd "$CLON" && find pns_base pns_ai_mcp pns_ai_chatboo -type f -not -path '*/__pycache__/*' -not -name '*.pyc' -print0 | LC_ALL=C sort -z | xargs -0 sha256sum | sha256sum | cut -d' ' -f1 ) )"
  MODCLON=$(cd "$CLON" && for d in */; do [ -f "$d/__manifest__.py" ] && echo "${d%/}"; done)
  echo "módulos en el clon: $(printf '%s\n' "$MODCLON" | una)"

  echo "== 5. Nginx y respuesta"
  NG=/etc/nginx/conf.d/odoo.conf
  if [ -r "$NG" ]; then
    chk "location /chatboo/stream" "$(grep -cE '^[[:space:]]*location \^~ /chatboo/stream' "$NG")" 1
    chk "location /mcp" "$(grep -cE '^[[:space:]]*location \^~ /mcp' "$NG")" 1
  else
    echo "INFO    $NG no se puede leer (no bloquea)"
  fi
  chk "liyben.com/web/login" "$(curl -sS -o /dev/null -w '%{http_code}' https://liyben.com/web/login 2>&1)" 200
  chk "GET liyben.com/mcp (Nginx, D20)" "$(curl -sS -o /dev/null -w '%{http_code}' https://liyben.com/mcp 2>&1)" 404

  echo "== 6. Disco y copias"
  df -h / /opt/odoo 2>/dev/null | sed 's/^/   /' | uniq
  echo "-- /opt/odoo/backups"
  ls -l /opt/odoo/backups 2>&1 | sed 1d | awk '{print "   " $5 "  " $NF}'
  FS=/opt/odoo/odoo-web-data/.local/share/Odoo/filestore/LIYBEN
  echo "filestore ($FS): $(du -sh "$FS" 2>/dev/null | cut -f1 || true) $( [ -r "$FS" ] || echo '(sin permiso de lectura como este usuario)')"

  echo "== 7. LIYBEN (SQL, sesión en solo lectura; solo recuentos, códigos e ids)"
  R=$(lysql <<'SQL'
\echo '## versiones'
SELECT name, state, latest_version FROM ir_module_module WHERE name IN ('pns_base','pns_ai_mcp','pns_ai_chatboo') ORDER BY name;
\echo '## estados a medias'
SELECT count(*) FROM ir_module_module WHERE state IN ('to upgrade','to install','to remove');
\echo '## instalados'
SELECT name FROM ir_module_module WHERE state = 'installed' ORDER BY name;
\echo '## dependientes'
SELECT DISTINCT m.name FROM ir_module_module m JOIN ir_module_module_dependency d ON d.module_id = m.id
 WHERE d.name IN ('pns_base','pns_ai_mcp','pns_ai_chatboo') AND m.state = 'installed'
   AND m.name NOT IN ('pns_base','pns_ai_mcp','pns_ai_chatboo') ORDER BY 1;
\echo '## usuarios'
SELECT count(*) FILTER (WHERE active AND NOT share), count(*) FILTER (WHERE active AND share) FROM res_users;
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
\echo '## proveedores'
SELECT id, active, protocol, model_name, fit_conversation, fit_audio, fit_vision, fit_video, fit_decision, no_external_failover
  FROM ai_provider ORDER BY id;
\echo '## columnas fit'
SELECT string_agg(column_name, ' ' ORDER BY column_name) FROM information_schema.columns
 WHERE table_name = 'ai_provider' AND column_name LIKE 'fit\_%' AND column_name <> 'fit_chips_html';
\echo '## crons'
SELECT d.module || '.' || d.name, c.active, c.interval_number || ' ' || c.interval_type, c.numbercall
  FROM ir_model_data d JOIN ir_cron c ON c.id = d.res_id
 WHERE d.model = 'ir.cron' AND d.module IN ('pns_base','pns_ai_mcp','pns_ai_chatboo') ORDER BY 1;
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
\echo '## servidores api'
SELECT id, active, api_type, server_type,
       coalesce(substring(url from '^[A-Za-z]+://(?:[^@/]*@)?([^/:?#]+)'), '-'),
       coalesce(substring(base_url from '^[A-Za-z]+://(?:[^@/]*@)?([^/:?#]+)'), '-')
  FROM ai_api_server ORDER BY id;
\echo '## adjuntos pns82'
SELECT CASE
         WHEN res_model IS NOT NULL AND res_model <> '' AND coalesce(res_id, 0) = 0 THEN 'b'
         WHEN (res_model IS NULL OR res_model = '') AND coalesce(res_id, 0) = 0 THEN 'a'
         WHEN (res_model IS NULL OR res_model = '') AND coalesce(res_id, 0) <> 0 THEN 'c'
         ELSE 'd' END,
       count(*), count(*) FILTER (WHERE description = 'pns_base:export')
  FROM ir_attachment WHERE res_field IS NULL GROUP BY 1 ORDER BY 1;
\echo '## adjuntos pns82 b por modelo'
SELECT a.res_model, a.create_uid, count(*) FROM ir_attachment a
 WHERE a.res_field IS NULL AND a.res_model IS NOT NULL AND a.res_model <> '' AND coalesce(a.res_id, 0) = 0
 GROUP BY 1, 2 ORDER BY 3 DESC, 1 LIMIT 10;
\echo '## adjuntos pns82 citados'
SELECT count(*) FROM ir_attachment a
 WHERE a.res_field IS NULL AND a.res_model IS NOT NULL AND a.res_model <> '' AND coalesce(a.res_id, 0) = 0
   AND EXISTS (SELECT 1 FROM chatboo_session s
                WHERE s.messages LIKE '%/' || a.id || '"%' OR s.messages LIKE '%"attachment_id": ' || a.id || '%');
\echo '## diario pns37'
SELECT count(*), count(*) FILTER (WHERE op = 'unlink' AND position('"quarantine": true' IN coalesce(after_json, '')) > 0),
       count(*) FILTER (WHERE write_uid IS DISTINCT FROM create_uid AND write_uid <> 1)
  FROM ai_change_journal;
\echo '## chatboo'
SELECT count(*), coalesce(max(id), 0), coalesce(to_char(min(create_date), 'YYYY-MM'), '-'), count(DISTINCT user_id) FROM chatboo_session;
\echo '## ai_log'
SELECT count(*), count(agent_id) FROM ai_log;
\echo '## skills'
SELECT s.code, s.active, s.is_system,
       EXISTS (SELECT 1 FROM ir_model_data d WHERE d.model = 'ai.skill' AND d.res_id = s.id)
  FROM ai_skill s ORDER BY s.code;
\echo '## contextos'
SELECT count(*), count(*) FILTER (WHERE active),
       count(*) FILTER (WHERE EXISTS (SELECT 1 FROM ir_model_data d WHERE d.model = 'ai.context' AND d.res_id = c.id))
  FROM ai_context c;
\echo '## idioma'
SELECT code, active FROM res_lang WHERE code = 'es_ES';
\echo '## traducciones es_ES'
SELECT count(*) FROM ir_translation WHERE lang = 'es_ES';
\echo '## tokens'
SELECT count(*) FROM res_partner WHERE signup_token IS NOT NULL;
\echo '## iap'
SELECT count(*) FROM iap_account;
\echo '## lienzos'
SELECT count(*) FROM information_schema.tables WHERE table_name = 'chatboo_canvas_page';
\echo '## fin'
SQL
)
  sec() { printf '%s\n' "$R" | awk -v s="## $1" '/^## /{p = ($0 == s); next} p'; }
  ver() { echo "-- $2"; sec "$1" | sed 's/^/   /'; }
  chk "consultas sin error" "$(printf '%s\n' "$R" | grep -c 'ERROR:' || true)" 0
  printf '%s\n' "$R" | grep 'ERROR:' | head -5 | sed 's/^/   /'
  chk "marcador final de la salida SQL" "$(printf '%s\n' "$R" | grep -cx '## fin')" 1
  chk "versiones (nombre|estado|versión)" "$(sec versiones | una)" "pns_ai_chatboo|installed|14.0.2.1.453 pns_ai_mcp|installed|14.0.3.1.782 pns_base|installed|14.0.1.2.32"
  chk "módulos a medio instalar o actualizar" "$(sec 'estados a medias')" 0
  echo "módulos instalados: $(sec instalados | grep -c . || true)"
  chk "dependientes de los pns_* (el -u también los actualizaría)" "$(sec dependientes | una)" ""
  echo "instalados que están en el clon (no pns_*): $(sec instalados | grep -vE '^pns_(base|ai_mcp|ai_chatboo)$' | grep -xF -f <(printf '%s\n' "$MODCLON") | una)"
  chk "usuarios activos (internos|externos)" "$(sec usuarios)" "3|0" info
  ver 'ai admins' "AI Administrators (id|activo|Ajustes|contraseña local|AI Conversational); decisión 10 y parche 16"
  ver proveedores "proveedores (id|activo|protocolo|modelo|conv|audio|visión|vídeo|decisión|sin failover externo)"
  chk "columnas fit_* de ai_provider (3.1.782: sin fit_design)" "$(sec 'columnas fit')" "fit_audio fit_conversation fit_decision fit_video fit_vision" info
  ver crons "crons de pns_* (xml_id|activo|intervalo|numbercall)"
  chk "crons de NUEVO-2 antes del -u" "$(sec 'crons nuevo2' | una)" "ir_cron_ai_api_result_cache_gc|model.gc_expired() ir_cron_ai_fetch_cache_gc|model.gc_expired()" info
  ver parametros "parámetros de configuración (clave|valor)"
  ver 'operaciones no terminales' "operaciones pending o confirmed sin ejecutar (estado|ejecutada|n)"
  chk "operaciones no terminales con pasos sobre ai.trusted.action (parche 32)" "$(sec 'operaciones trusted')" 0
  ver 'servidores api' "servidores ai.api.server (id|activo|tipo|transporte|host de url|host de base_url); PNS-17"
  ver 'adjuntos pns82' "adjuntos sin res_field por caso (a vacíos, b res_model con res_id 0, c res_id sin modelo, d enganchados|n|pns_base:export); PNS-82"
  ver 'adjuntos pns82 b por modelo' "caso b por modelo y creador (res_model|create_uid|n)"
  chk "caso b citado en sesiones de Chatboo (PNS-82)" "$(sec 'adjuntos pns82 citados')" 0 info
  ver 'diario pns37' "diario (filas|unlink en papelera|reescritas por otro); PNS-37"
  ver chatboo "Chatboo (sesiones|id máximo|primera, mes|usuarios)"
  ver ai_log "ai_log (filas|con agent_id, que se pierde en el -u)"
  ver skills "skills (code|activa|sistema|con xml_id)"
  ver contextos "contextos (total|activos|con xml_id)"
  chk "es_ES activo" "$(sec idioma)" "es_ES|t"
  echo "traducciones es_ES: $(sec 'traducciones es_ES')"
  chk "tokens de registro (D50)" "$(sec tokens)" 8 info
  echo "iap_account (filas): $(sec iap)"
  chk "tabla de páginas del lienzo (no existe en 3.1.782: A.6 de E3′ no aplica)" "$(sec lienzos)" 0 info

  echo "== 8. Llamadores en los módulos propios (parches 30 a 33): archivos, sin pns_* ni el core"
  AP=$(printf '%s\n' "${CF:-}" | sed -n 's/^ *addons_path = //p')
  echo "addons_path: ${AP:-no consta}"
  if [ -n "$AP" ]; then
    docker exec odoo14_server sh -c 'IFS=,; for d in $1; do d=$(echo "$d" | tr -d " "); case "$d" in */odoo/addons|*/odoo/addons/) continue;; esac; [ -d "$d" ] && grep -rlE "chat_completion|ai\.trusted\.action|ai_trusted_action|month_usage|log_llm_inference|log_provider_" "$d" --include=*.py --include=*.xml --include=*.js 2>/dev/null; done' _ "$AP" \
      | grep -vE '/pns_(base|ai_mcp|ai_chatboo)/' | sort | head -30 | sed 's/^/   /'
    echo "   (fin de la lista)"
  fi
  if [ "$F" = 0 ]; then echo "== I0: TODO OK"; else echo "== I0: $F FALLO(S). No sigas: pega la salida."; fi
)
ly_i0
