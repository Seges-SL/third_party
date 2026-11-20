ld_l4() (
  set -u
  umask 077
  . "$(dirname "$0")/ld_comun.sh" || exit 1
  TANDA="LD L4"
  [ "$(cd "$(dirname "$0")" && pwd)" = "$LD" ] || { echo "Lánzala desde $LD: bash $LD/ld_l4.sh"; exit 1; }
  sudo -v || { echo "FALLO   sudo. No se ha seguido."; exit 1; }
  O=$(nueva "$LD/l4" .txt) || exit 1
  M=${O##*/l4-}; M=${M%.txt}
  US="$LD/u-salida-$M.log"
  LG="$LD/u-$M.log"
  {
  echo "== $TANDA (VPS: D50, checkout de la rama y -u de los tres pns_* en LIYBEN, con el web parado): $(date -u '+%F %T') UTC"
  echo "== 1. Comprobaciones previas (solo lectura)"
  C=$(cat "$LD/commit.txt" 2>/dev/null)
  chk "huellas de $LD" "$(cd "$LD" && sha256sum -c --quiet huellas.txt 2>&1 | wc -l | tr -d ' ')" 0
  L2=$(ultima "$LD/l2-*.txt")
  chk "última L2 (${L2##*/}) con TODO OK" "$(marca "$L2" '== LD L2: TODO OK. Corte: web PARADO. Sigue con L3 en el equipo.')" 1
  chk "marca de copia de L3 (2 líneas, posterior a L2)" "$(wc -l < "$LD/copia_ok" 2>/dev/null | tr -d ' ')|$( [ "$LD/copia_ok" -nt "$L2" ] && echo posterior || echo anterior)" "2|posterior"
  sed 's/^/   /' "$LD/copia_ok" 2>/dev/null
  chk "ningún L4 anterior que pasara del punto 2" "$(grep -l '^== 2\. \[ALTERA LIYBEN\] D50' "$LD"/l4-*.txt 2>/dev/null | grep -v "^$O\$" | grep -c . || true)" 0
  chk "web parado" "$(web)" 0
  chk "odoo14_db en marcha" "$(docker ps --format '{{.Names}}' | grep -cx odoo14_db || true)" 1
  chk "rama|HEAD|status del clon" "$(g rev-parse --abbrev-ref HEAD)|$(g rev-parse --short=7 HEAD)|$(g status --porcelain | wc -l | tr -d ' ')" "$RAMA_ANTES|$COMMIT_ANTES|0"
  chk "origin/$RAMA = commit del documento" "$(g rev-parse -q --verify "refs/remotes/origin/$RAMA" 2>&1)" "$C"
  chk "versiones en LIYBEN (las de antes)" "$(lysql <<< "SELECT string_agg(name || '|' || state || '|' || latest_version, ' ' ORDER BY name) FROM ir_module_module WHERE name IN ('pns_base','pns_ai_mcp','pns_ai_chatboo');")" "pns_ai_chatboo|installed|14.0.2.1.453 pns_ai_mcp|installed|14.0.3.1.782 pns_base|installed|14.0.1.2.32"
  chk "log del servidor legible" "$(test -r "$LOGF" && echo si || echo no)" si
  corte "comprobaciones previas"

  echo "== 2. [ALTERA LIYBEN] D50: d50_vaciar VACIAR (vacía los 8 tokens de registro; COMMIT)"
  R=$( . "$LD/d50_vaciar.sh" && d50_vaciar VACIAR 2>&1 )
  printf '%s\n' "$R" | sed 's/^/   /'
  chk "D50 VACIAR con TODO OK" "$(printf '%s\n' "$R" | grep -cx '== D50 (VACIAR): TODO OK' || true)" 1
  corte "D50 (si la compuerta falló, no se vació nada: decide Sergio)"

  echo "== 3. [ALTERA el clon] checkout -b $RAMA <commit> sin --track, como el UID 101 (§3.2)"
  g101 checkout -q -b "$RAMA" "$C" 2>&1 | sed 's/^/   /'
  chk "rama|HEAD|status del clon" "$(g rev-parse --abbrev-ref HEAD)|$(g rev-parse HEAD)|$(g status --porcelain | wc -l | tr -d ' ')" "$RAMA|$C|0"
  chk "árbol de los pns_* montados (archivos y huella; D58)" "$(arbol "$CLON" | una)" "$ARBOL_RAMA"
  chk "archivos de los pns_* que no son del UID 101" "$(find "$CLON/pns_base" "$CLON/pns_ai_mcp" "$CLON/pns_ai_chatboo" ! -uid 101 | wc -l | tr -d ' ')" 0
  chk "versiones de los manifiestos" "$(for m in pns_base pns_ai_mcp pns_ai_chatboo; do grep -oE "'version': *'[^']+'" "$CLON/$m/__manifest__.py" | grep -oE "[0-9][0-9.]+"; done | una)" "14.0.1.2.69 14.0.3.1.973 14.0.2.1.587"
  chk "rama $RAMA_ANTES sigue en $COMMIT_ANTES (vuelta atrás)" "$(g rev-parse --short=7 "refs/heads/$RAMA_ANTES")" "$COMMIT_ANTES"
  corte "checkout (vuelta atrás: E, punto 1)"

  OFF=$(stat -c %s "$LOGF")
  T0U=$(date -u '+%Y-%m-%d %H:%M:%S')
  printf '%s\n' "$T0U" > "$LD/l4_t0.txt"
  echo "== 4. [ALTERA LIYBEN] -u pns_base,pns_ai_mcp,pns_ai_chatboo, lanzado a las $T0U UTC (1 a 2 minutos sin salida; ensayo: 67-72 s). Log desde el byte $OFF de $LOGF"
  ( cd "$COMPOSE" && docker compose run --rm -T web odoo -u pns_base,pns_ai_mcp,pns_ai_chatboo -d LIYBEN --stop-after-init ) > "$US" 2>&1 < /dev/null
  RC=$?
  echo "terminado a las $(date -u +%T) UTC"
  chk "salida del -u" "$RC" 0
  chk "salida estándar del contenedor (con logfile, vacía o solo avisos de compose)" "$(grep -cE 'Traceback|ERROR|CRITICAL' "$US" || true)" 0
  [ ! -s "$US" ] || { echo "-- salida estándar ($(wc -l < "$US" | tr -d ' ') líneas; 10 como mucho)"; head -10 "$US" | cut -c1-160 | sed 's/^/   /'; }
  N1=$(stat -c %s "$LOGF")
  chk "el log no se ha rotado durante el -u" "$( [ "$N1" -ge "$OFF" ] && echo si || echo no)" si
  tail -c +"$((OFF + 1))" "$LOGF" > "$LG"
  chk "log del -u con contenido" "$( [ -s "$LG" ] && echo si || echo no)" si
  echo "log del -u: $LG ($(wc -l < "$LG" | tr -d ' ') líneas; ensayo: 389)"
  corte "lanzamiento"

  echo "== 5. Log del -u (contra Y5 del ensayo)"
  chk "Traceback, ERROR o CRITICAL" "$(grep -cE 'Traceback|ERROR|CRITICAL' "$LG" || true)" 0
  echo "-- nivel y logger (WARNING/ERROR/CRITICAL), sin el mensaje"
  grep -oE ' (WARNING|ERROR|CRITICAL) [^ ]+ [^ ]+:' "$LG" | sort | uniq -c | sed 's/^/   /'
  chk "módulos que no se importan" "$(grep -cE 'No module named|module .* not (found|installable)' "$LG" || true)" 0
  DEL=$(grep -oE 'Deleting field [A-Za-z0-9_.]+' "$LG" | sed 's/^Deleting field //' | LC_ALL=C sort)
  chk "Deleting field de ai.provider (las 5 fit_* de 3.1.782, sin fit_design)" "$(printf '%s\n' "$DEL" | grep '^ai\.provider\.' | una)" "ai.provider.fit_audio ai.provider.fit_conversation ai.provider.fit_decision ai.provider.fit_video ai.provider.fit_vision"
  chk "otros «Deleting field» (los 7 del ensayo, Y5: documentados, sin pérdida que importe)" "$(printf '%s\n' "$DEL" | grep -v '^ai\.provider\.' | una)" "ai.log.agent_display ai.log.agent_id ai.mcp.user.key_pin ai.mcp.user.key_pin_html ai.mcp.user.key_pin_killed ai.mcp.user.key_pin_used ai.skill.capture.wizard.from_chatboo"
  chk "migraciones" "$(grep -oE 'module [a-z_]+: Running migration \[[^]]*\] [a-z-]+' "$LG" | una)" "module pns_ai_mcp: Running migration [14.0.3.1.973>] post-migrate"
  chk "parche 35, fixed" "$(grep -oE 'Seges patch 35: [A-Za-z0-9_.]+ fixed' "$LG" | LC_ALL=C sort | una)" "Seges patch 35: pns_ai_mcp.ir_cron_ai_api_result_cache_gc fixed Seges patch 35: pns_ai_mcp.ir_cron_ai_fetch_cache_gc fixed"
  chk "parche 35, WARNING" "$(grep 'Seges patch 35' "$LG" | grep -c WARNING || true)" 0
  chk "módulos actualizados («Module … loaded in»)" "$(grep -oE 'Module [a-z0-9_]+ loaded in' "$LG" | awk '{ print $2 }' | LC_ALL=C sort | una)" "pns_ai_chatboo pns_ai_mcp pns_base"
  chk "módulos cargados (I0: 215)" "$(grep -oE '[0-9]+ modules loaded in' "$LG" | tail -1 | awk '{ print $1 }')" 215
  echo "INFO    «DROP leftover» (ensayo, Y5: 22): $(grep -c 'DROP leftover' "$LG" || true)"
  echo "-- WARNING agrupados (mensaje recortado a 90 caracteres)"
  grep ' WARNING ' "$LG" | sed 's/.* WARNING [^ ]* //' | cut -c1-90 | sort | uniq -c | sed 's/^/   /'
  echo "INFO    conocidos: «same label» de ai.log $(grep -c 'Two fields (client_label, client_display) of ai.log' "$LG" || true) (ensayo: 3), de ai.trusted.action $(grep -c 'Two fields (model_name, model_id) of ai.trusted.action' "$LG" || true) (ensayo: 2); «skip retired unlink for pns_ai_mcp» $(grep -c 'skip retired unlink for pns_ai_mcp' "$LG" || true) (ensayo: 2)"
  chk "otros WARNING de los pns_*" "$(grep ' WARNING ' "$LG" | grep -E 'odoo\.addons\.pns_' | grep -v 'skip retired unlink' | wc -l | tr -d ' ')" 0
  grep ' WARNING ' "$LG" | grep -E 'odoo\.addons\.pns_' | grep -v 'skip retired unlink' | sed 's/.* WARNING [^ ]* //' | cut -c1-120 | sort | uniq -c | sed 's/^/   /'


  echo "== 6. Después (solo lectura; el «después» completo es L6)"
  Q=$(lysql <<'SQL'
SELECT string_agg(name || '|' || state || '|' || latest_version, ' ' ORDER BY name) FROM ir_module_module WHERE name IN ('pns_base','pns_ai_mcp','pns_ai_chatboo');
SELECT count(*) FROM ir_module_module WHERE state IN ('to upgrade','to install','to remove');
SELECT count(*) FROM ir_module_module WHERE state = 'installed';
SELECT string_agg(d.name || '|' || s.code, ' ' ORDER BY d.name) FROM ir_model_data d JOIN ir_cron c ON c.id = d.res_id JOIN ir_act_server s ON s.id = c.ir_actions_server_id WHERE d.module = 'pns_ai_mcp' AND d.model = 'ir.cron' AND d.name IN ('ir_cron_ai_fetch_cache_gc', 'ir_cron_ai_api_result_cache_gc');
SELECT count(*) FROM information_schema.columns WHERE table_schema = 'public' AND table_name = 'ai_provider' AND column_name LIKE 'fit\_%';
SELECT (to_regclass('public.ai_provider_role') IS NOT NULL) || '|' || (to_regclass('public.chatboo_canvas_page') IS NOT NULL);
SELECT count(*) FROM res_partner WHERE signup_token IS NOT NULL;
SQL
)
  chk "consultas sin error" "$(printf '%s\n' "$Q" | grep -ciE 'ERROR:|psql: error' || true)" 0
  chk "versiones de la rama" "$(printf '%s\n' "$Q" | sed -n 1p)" "$VERS_RAMA"
  chk "módulos a medio instalar o actualizar" "$(printf '%s\n' "$Q" | sed -n 2p)" 0
  chk "módulos instalados (I0: 215)" "$(printf '%s\n' "$Q" | sed -n 3p)" 215
  chk "crons de NUEVO-2 corregidos por el parche 35" "$(printf '%s\n' "$Q" | sed -n 4p)" "ir_cron_ai_api_result_cache_gc|model._gc_expired() ir_cron_ai_fetch_cache_gc|model._gc_expired()"
  chk "columnas fit_* en ai_provider" "$(printf '%s\n' "$Q" | sed -n 5p)" 0
  chk "tablas de 3.1.973 (ai_provider_role|chatboo_canvas_page)" "$(printf '%s\n' "$Q" | sed -n 6p)" "true|true"
  chk "tokens de registro (D50)" "$(printf '%s\n' "$Q" | sed -n 7p)" 0
  chk "web parado" "$(web)" 0
  fin "Corte: web PARADO. Pega la salida antes de L4b. No arranques el web."
  } 2>&1 | tee "$O"
  echo "Guardado en $O"
)
ld_l4
