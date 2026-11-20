ly_y5() (
  set -u
  umask 077
  F=0
  chk() {
    if [ "$2" = "$3" ]; then echo "OK      $1"
    elif [ "${4:-}" = info ]; then echo "INFO    $1: esperado [$3], obtenido [$2] (no bloquea)"
    else echo "FALLO   $1: esperado [$3], obtenido [$2]"; F=$((F + 1)); fi
  }
  una() { tr '\n' ' ' | sed 's/ *$//'; }
  corte() { [ "$F" = 0 ] || { echo "== Y5: $F FALLO(S) en «$1». No se ha seguido: pega la salida."; exit 1; }; }
  MODO=${1:-comprobar}
  case "$MODO" in comprobar|ACTUALIZAR) ;; *) echo "Uso: ly_y5 [comprobar|ACTUALIZAR] (sin argumento: comprobar, que no escribe)"; exit 1 ;; esac
  web() { docker ps --format '{{.Names}}' | grep -cE '^odoo-dev-14-web' || true; }
  pg() { docker exec -i -e PGOPTIONS='-c default_transaction_read_only=on' odoo-dev-14-db-1 psql -U odoo -d "$1" -X -q -At -F '|' 2>&1; }
  L=~/GitHub/lab_liyben_3973
  D=~/pns_ai_3973/liyben
  R=~/GitHub/third_party
  BD=liyben_ens_14
  ANTES="$D/y4_antes-20261119-135706.txt"
  g() { git --no-optional-locks -C "$R" "$@"; }
  arbol() { ( cd "$R" && echo "$(find pns_base pns_ai_mcp pns_ai_chatboo -type f -not -path '*/__pycache__/*' -not -name '*.pyc' | wc -l | tr -d ' ') $(find pns_base pns_ai_mcp pns_ai_chatboo -type f -not -path '*/__pycache__/*' -not -name '*.pyc' -print0 | LC_ALL=C sort -z | xargs -0 sha256sum | sha256sum | cut -d' ' -f1)" ); }
  M=$(date +%Y%m%d-%H%M%S)
  O="$D/y5-$MODO-$M.txt"
  S="$D/y5-actualizar-$M.txt"
  [ -d "$D" ] || { echo "No existe $D"; exit 1; }
  { [ ! -e "$O" ] && [ ! -e "$S" ]; } || { echo "Ya existe $O o $S: vuelve a lanzarla dentro de un segundo"; exit 1; }
  {
  echo "== Y5 ($MODO): -u pns_base,pns_ai_mcp,pns_ai_chatboo sobre $BD (copia de LIYBEN), con el web parado. $M"
  echo "== 1. Comprobaciones previas (solo lectura)"
  chk "web del kit parado" "$(web)" 0
  E=$(cd "$L" && odoo-dev 14 estado 2>&1)
  chk "contexto activo (BD|repo)" "$(printf '%s\n' "$E" | sed -n 's/^ *BD=//p' | head -1)|$(printf '%s\n' "$E" | sed -n 's/^ *REPO=//p' | head -1)" "lab_liyben_3973_14|$L"
  chk "PostgreSQL del kit en marcha" "$(docker ps --format '{{.Names}}' | grep -cx odoo-dev-14-db-1 || true)" 1
  chk "clones fijados (fijados.tsv, 23 repos)" "$(wc -l < "$D/fijados.tsv" 2>/dev/null | tr -d ' ')" 23
  [ "$F" = 0 ] || echo "   (si el único FALLO es PostgreSQL: lanza «cd $L && odoo-dev 14 bd-lista», que no levanta el web, y repite Y5)"
  corte "comprobaciones previas"
  chk "$BD existe" "$(pg postgres <<< "SELECT count(*) FROM pg_database WHERE datname = '$BD';")" 1
  N=$(cd "$L" && odoo-dev 14 estado --bd "$BD" 2>&1 | grep -i 'neutraliz' | head -1)
  echo "estado --bd: $N"
  chk "$BD neutralizada por el kit" "$(printf '%s' "$N" | grep -qi 'NO neutralizada' && echo no || (printf '%s' "$N" | grep -qi 'neutralizada' && echo si || echo no))" si
  Y=$(ls -t "$D"/y4-2*.txt 2>/dev/null | head -1)
  chk "última Y4 ($(basename "${Y:-ninguna}")) con TODO OK" "$(grep -cx '== Y4: TODO OK. Corte: pega la salida antes de Y5.' "$Y" 2>/dev/null || true)" 1
  chk "«antes» de Y4 intacto (huella)" "$(sha256sum "$ANTES" 2>/dev/null | cut -d' ' -f1)" ab7571b7ec9f4d8de418abbb8475eb050df3f6ef480c9dcfcf8ecb8f44c0958c
  chk "versiones en $BD (todavía 3.1.782)" "$(pg "$BD" <<< "SELECT string_agg(name || '|' || state || '|' || latest_version, ' ' ORDER BY name) FROM ir_module_module WHERE name IN ('pns_base','pns_ai_mcp','pns_ai_chatboo');")" "pns_ai_chatboo|installed|14.0.2.1.453 pns_ai_mcp|installed|14.0.3.1.782 pns_base|installed|14.0.1.2.32"
  chk "rama de third_party" "$(g rev-parse --abbrev-ref HEAD 2>&1)" 14.0-pns-ai-3973
  chk "HEAD de third_party" "$(g rev-parse --short=7 HEAD 2>&1)" c6ec077
  chk "árbol limpio (líneas de status)" "$(g status --porcelain 2>&1 | wc -l | tr -d ' ')" 0
  chk "árbol de los tres pns_* = 5d0559b (D58: archivos y huella)" "$(arbol)" "688 0dc381e0ca78b4d46a4c2c4c0b82eec7cedae444beded41b60867b11b411ba7a"
  if [ "$MODO" = comprobar ] || [ "$F" != 0 ]; then
    if [ "$F" = 0 ]; then echo "== Y5: TODO OK (comprobar: no se ha tocado nada)"; else echo "== Y5: $F FALLO(S). No se ha actualizado nada."; fi
    exit 0
  fi

  echo "== 2. [ALTERA $BD] odoo-dev 14 actualizar pns_base,pns_ai_mcp,pns_ai_chatboo --bd $BD, lanzado a las $(date +%H:%M:%S) (varios minutos, sin salida en pantalla; P-15 tardó 72 s con 48 módulos)"
  T0=$(date '+%Y-%m-%d %H:%M:%S')
  ( cd "$L" && odoo-dev 14 actualizar pns_base,pns_ai_mcp,pns_ai_chatboo --bd "$BD" ) > "$S" 2>&1 < /dev/null
  RC=$?
  echo "terminado a las $(date +%H:%M:%S); salida completa del kit en $S ($(wc -l < "$S" | tr -d ' ') líneas)"
  echo "-- salida del kit (40 líneas como mucho)"
  cut -c1-160 "$S" | head -40 | sed 's/^/   /'
  chk "salida de actualizar" "$RC" 0
  chk "resultado del analizador" "$(sed -n 's/^===== RESULTADO: //p' "$S" | head -1)" OK
  chk "bloqueantes del analizador" "$(sed -n 's/^===== actualizar: \([0-9][0-9]*\) bloqueante.*/\1/p' "$S" | head -1)" 0
  LG=$(sed -n "s/^==> actualizar en $BD (log: \(.*\))\$/\1/p" "$S" | head -1)
  chk "log del -u de esta ejecución (existe y es posterior al lanzamiento)" "$( [ -n "$LG" ] && [ -f "$LG" ] && [ -n "$(find "$LG" -newermt "$T0" 2>/dev/null)" ] && echo si || echo no)" si
  corte "lanzamiento"

  echo "== 3. Log del -u ($LG, $(wc -l < "$LG" | tr -d ' ') líneas)"
  chk "Traceback, ERROR o CRITICAL" "$(grep -cE 'Traceback|ERROR|CRITICAL' "$LG" || true)" 0
  echo "-- nivel y logger (WARNING/ERROR/CRITICAL), sin el mensaje"
  grep -oE ' (WARNING|ERROR|CRITICAL) [^ ]+ [^ ]+:' "$LG" | sort | uniq -c | sed 's/^/   /'
  chk "módulos que no se importan" "$(grep -cE 'No module named|module .* not (found|installable)' "$LG" || true)" 0
  DEL=$(grep -oE 'Deleting field [A-Za-z0-9_.]+' "$LG" | sed 's/^Deleting field //' | LC_ALL=C sort)
  chk "Deleting field de ai.provider (las 5 fit_* de 3.1.782, sin fit_design)" "$(printf '%s\n' "$DEL" | grep '^ai\.provider\.' | una)" "ai.provider.fit_audio ai.provider.fit_conversation ai.provider.fit_decision ai.provider.fit_video ai.provider.fit_vision"
  echo "INFO    otros «Deleting field» (lo que da el ensayo; no bloquea): $(printf '%s\n' "$DEL" | grep -vc '^ai\.provider\.' || true)"
  printf '%s\n' "$DEL" | grep -v '^ai\.provider\.' | grep . | sed 's/^/   /'
  chk "migraciones" "$(grep -oE 'module [a-z_]+: Running migration \[[^]]*\] [a-z-]+' "$LG" | una)" "module pns_ai_mcp: Running migration [14.0.3.1.973>] post-migrate"
  chk "parche 35, fixed" "$(grep -oE 'Seges patch 35: [A-Za-z0-9_.]+ fixed' "$LG" | LC_ALL=C sort | una)" "Seges patch 35: pns_ai_mcp.ir_cron_ai_api_result_cache_gc fixed Seges patch 35: pns_ai_mcp.ir_cron_ai_fetch_cache_gc fixed"
  chk "parche 35, WARNING" "$(grep 'Seges patch 35' "$LG" | grep -c WARNING || true)" 0
  chk "módulos actualizados («Module … loaded in»)" "$(grep -oE 'Module [a-z0-9_]+ loaded in' "$LG" | awk '{ print $2 }' | LC_ALL=C sort | una)" "pns_ai_chatboo pns_ai_mcp pns_base"
  chk "módulos cargados (I0: 215)" "$(grep -oE '[0-9]+ modules loaded in' "$LG" | tail -1 | awk '{ print $1 }')" 215
  echo "INFO    «DROP leftover» (lo que da el ensayo; staging 11): $(grep -c 'DROP leftover' "$LG" || true)"
  echo "-- WARNING agrupados (mensaje recortado a 90 caracteres)"
  grep ' WARNING ' "$LG" | sed 's/.* WARNING [^ ]* //' | cut -c1-90 | sort | uniq -c | sed 's/^/   /'
  echo "INFO    conocidos: «same label» de ai.log $(grep -c 'Two fields (client_label, client_display) of ai.log' "$LG" || true) (P-15: 2), de ai.trusted.action $(grep -c 'Two fields (model_name, model_id) of ai.trusted.action' "$LG" || true) (P-15: 1); «skip retired unlink for pns_ai_mcp» $(grep -c 'skip retired unlink for pns_ai_mcp' "$LG" || true) (P-15: 2)"
  chk "otros WARNING de los pns_*" "$(grep ' WARNING ' "$LG" | grep -E 'odoo\.addons\.pns_' | grep -v 'skip retired unlink' | wc -l | tr -d ' ')" 0
  grep ' WARNING ' "$LG" | grep -E 'odoo\.addons\.pns_' | grep -v 'skip retired unlink' | sed 's/.* WARNING [^ ]* //' | cut -c1-120 | sort | uniq -c | sed 's/^/   /'

  echo "== 4. Después (solo lectura; el «después» completo es Y7)"
  chk "web del kit parado (actualizar --bd no lo levanta)" "$(web)" 0
  Q=$(pg "$BD" <<'SQL'
SELECT string_agg(name || '|' || state || '|' || latest_version, ' ' ORDER BY name) FROM ir_module_module WHERE name IN ('pns_base','pns_ai_mcp','pns_ai_chatboo');
SELECT count(*) FROM ir_module_module WHERE state IN ('to upgrade','to install','to remove');
SELECT count(*) FROM ir_module_module WHERE state = 'installed';
SELECT count(*) FROM ir_cron WHERE active;
SELECT string_agg(d.name || '|' || s.code, ' ' ORDER BY d.name) FROM ir_model_data d JOIN ir_cron c ON c.id = d.res_id JOIN ir_act_server s ON s.id = c.ir_actions_server_id WHERE d.module = 'pns_ai_mcp' AND d.model = 'ir.cron' AND d.name IN ('ir_cron_ai_fetch_cache_gc', 'ir_cron_ai_api_result_cache_gc');
SELECT count(*) FROM information_schema.columns WHERE table_schema = 'public' AND table_name = 'ai_provider' AND column_name LIKE 'fit\_%';
SELECT (to_regclass('public.ai_provider_role') IS NOT NULL) || '|' || (to_regclass('public.chatboo_canvas_page') IS NOT NULL);
SELECT to_regclass('public.ai_provider_fit_stash') IS NOT NULL;
SQL
)
  chk "consultas sin error" "$(printf '%s\n' "$Q" | grep -c 'ERROR:' || true)" 0
  chk "versiones de la rama" "$(printf '%s\n' "$Q" | sed -n 1p)" "pns_ai_chatboo|installed|14.0.2.1.587 pns_ai_mcp|installed|14.0.3.1.973 pns_base|installed|14.0.1.2.69"
  chk "módulos a medio instalar o actualizar" "$(printf '%s\n' "$Q" | sed -n 2p)" 0
  chk "módulos instalados (I0: 215)" "$(printf '%s\n' "$Q" | sed -n 3p)" 215
  chk "crons activos (el kit los vuelve a desactivar)" "$(printf '%s\n' "$Q" | sed -n 4p)" 0
  chk "crons de NUEVO-2 corregidos por el parche 35" "$(printf '%s\n' "$Q" | sed -n 5p)" "ir_cron_ai_api_result_cache_gc|model._gc_expired() ir_cron_ai_fetch_cache_gc|model._gc_expired()"
  chk "columnas fit_* en ai_provider" "$(printf '%s\n' "$Q" | sed -n 6p)" 0
  chk "tablas de 3.1.973 (ai_provider_role|chatboo_canvas_page)" "$(printf '%s\n' "$Q" | sed -n 7p)" "true|true"
  echo "INFO    tabla ai_provider_fit_stash existe: $(printf '%s\n' "$Q" | sed -n 8p) (para Y7)"
  if [ "$F" = 0 ]; then echo "== Y5: TODO OK. Corte: pega la salida antes de Y6."; else echo "== Y5: $F FALLO(S). No sigas: pega la salida."; fi
  } 2>&1 | tee "$O"
  echo "Guardado en $O"
)
ly_y5 "$@"
