ld_l0() (
  set -u
  umask 077
  . "$(dirname "$0")/ld_comun.sh" || exit 1
  TANDA="LD L0"
  sb() { sec "$RB" "$1"; }
  sc() { sec "$RC" "$1"; }
  ver() { echo "-- $2"; sc "$1" | sed 's/^/   /'; }
  [ "$(cd "$(dirname "$0")" && pwd)" = "$LD" ] || { echo "Lánzala desde $LD: bash $LD/ld_l0.sh"; exit 1; }
  sudo -v || { echo "FALLO   sudo (hace falta para git como el UID 101). No se ha seguido."; exit 1; }
  O=$(nueva "$LD/l0" .txt) || exit 1
  A=$(nueva "$LD/l0_antes" .txt) || exit 1
  I=$(nueva "$LD/l0_i0" .txt) || exit 1
  {
  echo "== $TANDA (VPS, solo lectura: no escribe en LIYBEN, ni en el clon, ni fuera de $LD): $(date -u '+%F %T') UTC"
  echo "== 1. Tandas y commit"
  chk "huellas de $LD (las que copió E1)" "$(cd "$LD" && sha256sum -c --quiet huellas.txt 2>&1 | wc -l | tr -d ' ')" 0
  C=$(cat "$LD/commit.txt" 2>/dev/null)
  chk "commit a desplegar (40 caracteres hexadecimales)" "$(printf '%s' "$C" | grep -cxE '[0-9a-f]{40}' || true)" 1
  echo "commit: $C"
  corte "tandas"

  echo "== 2. I0 (ly_i0.sh del ensayo, solo lectura; salida completa en $I)"
  bash "$LD/ly_i0.sh" > "$I" 2>&1
  chk "I0 terminó con TODO OK" "$(marca "$I" '== I0: TODO OK')" 1
  grep -E '^(FALLO|INFO) ' "$I" | sed 's/^/   /'
  grep -E '^(tamaño de LIYBEN|módulos instalados|traducciones es_ES|filestore|iap_account)' "$I" | sed 's/^/   /'
  grep -A2 '^== 6\.' "$I" | tail -1 | sed 's/^/   disco: /'
  echo "-- caso b de PNS-82 por modelo y creador (decisión 7; I0 del 19/11: 67/18/2/1)"
  grep -A6 '^-- caso b por modelo' "$I" | grep '^   ' | head -6
  corte "I0"

  echo "== 3. Lo que necesitan L2 a L5"
  chk "web en marcha (se para en L2)" "$(web)" 1
  chk "usuario messagebus = UID 101" "$(id -u messagebus 2>&1)" 101
  chk "propietario del clon" "$(stat -c %u "$CLON")" 101
  chk "sudo sin pedir otra vez la contraseña (sudo -n)" "$(sudo -n true 2>&1 && echo si || echo no)" si
  echo "INFO    origen del clon (esquema y host, sin usuario ni credenciales): $(g remote get-url origin 2>&1 | sed -E 's#^([a-z+]+://)([^@/]*@)?([^/:]+).*#\1\3#; s#^[^@/]+@([^:]+):.*#ssh \1#')"
  echo "INFO    clon superficial: $(g rev-parse --is-shallow-repository 2>&1)"
  RL=$(g101 ls-remote origin "refs/heads/$RAMA" 2>&1)
  chk "ls-remote de $RAMA como el UID 101 (la rama remota está en el commit)" "$(printf '%s\n' "$RL" | cut -f1 | head -1)" "$C"
  [ "$(printf '%s\n' "$RL" | cut -f1 | head -1)" = "$C" ] || printf '%s\n' "$RL" | head -3 | cut -c1-120 | sed 's/^/   /'
  chk "log del servidor legible ($LOGF)" "$(test -r "$LOGF" && echo si || echo no)" si
  echo "INFO    tamaño del log: $(stat -c %s "$LOGF" 2>&1) bytes"
  chk "filestore legible entero (archivos sin lectura | carpetas sin entrada)" "$(find "$FS" -type f ! -readable 2>/dev/null | wc -l | tr -d ' ')|$(find "$FS" -type d ! -executable 2>/dev/null | wc -l | tr -d ' ')" "0|0"
  echo "INFO    filestore: $(find "$FS" -type f 2>/dev/null | wc -l | tr -d ' ') archivos, $(du -sb "$FS" 2>/dev/null | cut -f1) bytes"
  chk "espacio libre en el VPS (al menos 2 GB; L3 no escribe aquí)" "$( [ "$(df --output=avail -B1 / | tail -1 | tr -d ' ')" -ge 2000000000 ] && echo si || echo no)" si
  corte "lo que necesitan L2 a L5"

  echo "== 4. B: esquema de LIYBEN y correspondencia con los archivos de 3.1.782 (l0_b.sql = Y4 B)"
  RB=$(lysql < "$LD/l0_b.sql")
  chk "consultas sin error" "$(printf '%s\n' "$RB" | grep -ciE "ERROR:|psql: error" || true)" 0
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

  echo "== 5. C: «antes» (l0_antes.sql = Y4 C; salida SQL completa en $A, para L6)"
  RC=$(lysql < "$LD/l0_antes.sql")
  printf '%s\n' "$RC" > "$A"
  echo "guardado: $A ($(wc -l < "$A" | tr -d ' ') líneas, SHA-256 $(sha256sum "$A" | cut -d' ' -f1))"
  chk "consultas sin error" "$(printf '%s\n' "$RC" | grep -ciE "ERROR:|psql: error" || true)" 0
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
  ver cadena "cadena ai_agent_provider, sin api_key (id|agente|prioridad|activo|skip_sync_fallback|provider_id|proveedor activo); para L6"
  chk "crons de pns_* (xml_id|activo|intervalo|numbercall): los 6 de I0, activos" "$(sc crons | una)" "pns_ai_chatboo.ir_cron_chatboo_async_maintenance|t|5 minutes|-1 pns_ai_mcp.ir_cron_ai_api_result_cache_gc|t|1 hours|-1 pns_ai_mcp.ir_cron_ai_fetch_cache_gc|t|1 hours|-1 pns_ai_mcp.ir_cron_ai_log_retention|t|1 days|-1 pns_ai_mcp.ir_cron_ai_safe_operation_expire|t|5 minutes|-1 pns_base.ir_cron_pns_export_purge|t|1 hours|-1"
  echo "INFO    crons activos en LIYBEN (todos los módulos; L6 espera uno más): $(sc 'crons activos')"
  chk "crons de NUEVO-2 antes del -u (el parche 35 los corregirá), = I0" "$(sc 'crons nuevo2' | una)" "ir_cron_ai_api_result_cache_gc|model.gc_expired() ir_cron_ai_fetch_cache_gc|model.gc_expired()"
  chk "parámetros (clave|valor), = I0" "$(sc parametros | una)" "pns_ai_chatboo.history_retention_days|30 pns_ai_mcp.log_retention_days|30 pns_ai_mcp.url_access_policy|whitelist_only"
  chk "operaciones pending o confirmed sin ejecutar, = I0" "$(sc 'operaciones no terminales' | una)" ""
  chk "operaciones no terminales con pasos sobre ai.trusted.action (parche 32)" "$(sc 'operaciones trusted')" 0
  ver 'operaciones por status' "ai_safe_operation por status (status|n); para L6"
  ver trusted "ai_trusted_action (n|max_id); para L6"
  chk "servidores ai.api.server (PNS-17), = I0" "$(sc 'servidores api')" 0 info
  chk "diario (filas|unlink en papelera|reescritas por otro), = I0" "$(sc diario)" "2|0|0" info
  chk "Chatboo (sesiones|id máximo|primera, mes|usuarios), = I0" "$(sc chatboo)" "1|1|2026-10|1" info
  chk "ai_log (filas|con agent_id|max_id), = I0" "$(sc ai_log)" "0|0|0" info
  chk "skills (code|activa|sistema|con xml_id), = I0" "$(sc skills | una)" "annual_billing|t|t|f billing|t|t|f credit_facility|t|t|f customer_risk_analysis|t|t|f dashboard|t|t|f financial_health|t|t|f forecast|t|t|f sys_info|t|t|f users_all|t|t|f users_logged|t|t|f"
  ver 'skills detalle' "skills (id|code|command|source_module|rel_path|activa|write_uid); para L6"
  chk "contextos (total|activos|con xml_id), = I0" "$(sc contextos)" "56|56|0"
  chk "contextos por módulo (source_module|n|activos)" "$(sc 'contextos por modulo' | una)" "pns_ai_chatboo|3|3 pns_ai_mcp|53|53"
  ver 'modulos iap' "módulos crm, iap, partner_autocomplete y sms (name|state); para L6"
  chk "es_ES activo, = I0" "$(sc idioma)" "es_ES|t"
  chk "traducciones es_ES, = I0" "$(sc 'traducciones es_ES')" 45482 info
  chk "tokens de registro (los 8 de D50; los vacía L4), = I0" "$(sc tokens)" 8
  chk "iap_account (filas), = I0" "$(sc iap)" 1

  echo "== 5b. P-21 de LIYBEN (qué hará el -u de 3.1.973 con los contextos y skills de fábrica)"
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
  corte "C y P-21"

  echo "== 6. D50 en ensayo (d50_vaciar.sh; termina en ROLLBACK)"
  R=$( . "$LD/d50_vaciar.sh" && d50_vaciar ensayo 2>&1 )
  printf '%s\n' "$R" | sed 's/^/   /'
  chk "D50 ensayo con TODO OK" "$(printf '%s\n' "$R" | grep -cx '== D50 (ensayo): TODO OK (ensayo: LIYBEN sin cambios)' || true)" 1
  fin "Corte: pega la salida. Después L1 (interfaz) y L2, antes de una hora."
  } 2>&1 | tee "$O"
  echo "Guardado en $O"
)
ld_l0
