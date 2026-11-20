ld_l4b() (
  set -u
  umask 077
  . "$(dirname "$0")/ld_comun.sh" || exit 1
  TANDA="LD L4b"
  MODO=${1:-comprobar}
  case "$MODO" in
    comprobar) OP=- ;;
    APLICAR_BP) OP=BP ;;
    *) echo "Uso: bash $LD/ld_l4b.sh [comprobar|APLICAR_BP] (sin argumento: comprobar, que termina en rollback)"; exit 1 ;;
  esac
  [ "$(cd "$(dirname "$0")" && pwd)" = "$LD" ] || { echo "Lánzala desde $LD: bash $LD/ld_l4b.sh $MODO"; exit 1; }
  BD=LIYBEN
  NT_E=45966
  NF_E=41467
  FINC="Corte (comprobar: rollback, nada escrito). Pega la salida antes de APLICAR_BP."
  FINA="Corte (APLICAR_BP). Pega la salida antes de L5. No arranques el web todavía."
  O=$(nueva "$LD/l4b-$MODO" .txt) || exit 1
  M=${O##*/l4b-$MODO-}; M=${M%.txt}
  SL="$LD/l4b-shell-$MODO-$M.log"
  SLOG="$LD/l4b-log-$MODO-$M.log"
  FA="$LD/l4b_foto_antes-$MODO-$M.txt"
  FD="$LD/l4b_foto_despues-$MODO-$M.txt"
  DA="$LD/l4b_antes-$MODO-$M.txt"
  DD="$LD/l4b_despues-$MODO-$M.txt"
  medida_ext() { awk -F'|' -v etq="$1" '
    function tipo(t) { return (t == "code" || t == "model" || t == "model_terms") ? t : "otro" }
    function pns(m) { return substr(m, 1, 4) == "pns_" }
    NR == FNR { a[$1] = $0; at[$1] = $2; am[$1] = $3; av[$1] = $7; next }
    { d[$1] = $0; dt[$1] = $2; dm[$1] = $3; dv[$1] = $7 }
    END {
      split("code model model_terms otro", T, " ")
      for (i in a) {
        t = tipo(at[i])
        if (pns(am[i])) { k = !(i in d) ? 3 : (d[i] == a[i] ? 1 : 2); pn[t, k]++ }
        else { k = !(i in d) ? 4 : (dv[i] != av[i] ? 3 : (d[i] != a[i] ? 2 : 1)); fu[t, k]++ }
      }
      for (i in d) if (!(i in a)) { t = tipo(dt[i]); if (pns(dm[i])) nu[t, 1]++; else nu[t, 2]++ }
      for (j = 1; j <= 4; j++) { t = T[j]; printf "Y6 MEDIDA %s fuera %s igual=%d origen=%d texto=%d borradas=%d\n", etq, t, fu[t,1], fu[t,2], fu[t,3], fu[t,4]
        so += fu[t,2]; st += fu[t,3]; sb += fu[t,4] }
      for (j = 1; j <= 4; j++) { t = T[j]; printf "Y6 MEDIDA %s pns %s igual=%d cambiadas=%d borradas=%d\n", etq, t, pn[t,1], pn[t,2], pn[t,3]
        pc += pn[t,2]; pb += pn[t,3] }
      for (j = 1; j <= 4; j++) { t = T[j]; printf "Y6 MEDIDA %s nuevas %s pns=%d fuera=%d\n", etq, t, nu[t,1], nu[t,2]
        np += nu[t,1]; nf += nu[t,2] }
      printf "Y6 TOTAL %s fuera_origen=%d fuera_texto=%d fuera_borradas=%d nuevas_fuera=%d pns_cambiadas=%d pns_borradas=%d nuevas_pns=%d\n", etq, so, st, sb, nf, pc, pb, np
    }' "$2" "$3"; }
  cero() { echo "Y6 TOTAL $1 fuera_origen=0 fuera_texto=0 fuera_borradas=0 nuevas_fuera=0 pns_cambiadas=0 pns_borradas=0 nuevas_pns=0"; }
  {
  echo "== $TANDA ($MODO): recarga B′ de es_ES de los tres pns_* (D66 revisada) y rol Diseño en el proveedor 1 sin alternativa, quitándole Decisión (D67), sobre LIYBEN con el web parado (Y6 v3 del ensayo; script l4b.py = el del ensayo). $(date -u '+%F %T') UTC"
  echo "== 1. Comprobaciones previas (solo lectura)"
  chk "huellas de $LD" "$(cd "$LD" && sha256sum -c --quiet huellas.txt 2>&1 | wc -l | tr -d ' ')" 0
  chk "web parado" "$(web)" 0
  L4=$(ultima "$LD/l4-*.txt")
  chk "última L4 (${L4##*/}) con TODO OK" "$(marca "$L4" '== LD L4: TODO OK. Corte: web PARADO. Pega la salida antes de L4b. No arranques el web.')" 1
  chk "ningún L4b APLICAR_BP con commit" "$(grep -lx 'Y6 COMMIT OK' "$LD"/l4b-shell-APLICAR_BP-*.log 2>/dev/null | grep -c . || true)" 0
  if [ "$OP" = BP ]; then
    C=$(ultima "$LD/l4b-comprobar-*.txt")
    chk "último L4b comprobar (${C##*/}) con TODO OK y posterior a L4" "$(marca "$C" "== $TANDA: TODO OK. $FINC")|$( [ -n "$C" ] && [ "$C" -nt "$L4" ] && echo posterior || echo anterior)" "1|posterior"
  fi
  chk "versiones en LIYBEN (las de la rama, tras L4)" "$(lysql <<< "SELECT string_agg(name || '|' || state || '|' || latest_version, ' ' ORDER BY name) FROM ir_module_module WHERE name IN ('pns_base','pns_ai_mcp','pns_ai_chatboo');")" "$VERS_RAMA"
  chk "log del servidor legible" "$(test -r "$LOGF" && echo si || echo no)" si
  corte "compuertas"
  RA=$(lysql < "$LD/l4b_estado.sql")
  printf '%s\n' "$RA" > "$DA"
  chk "consultas sin error (antes)" "$(printf '%s\n' "$RA" | grep -ciE 'ERROR:|psql: error' || true)" 0
  chk "marcador final (antes)" "$(printf '%s\n' "$RA" | grep -cx '## fin' || true)" 1
  chk "rol Diseño, antes (xml_id|code|activo|use_fallback|alternativa)" "$(sec "$RA" 'rol Diseño' | una)" "pns_ai_mcp.ai_provider_role_design|design|t|t|conversation"
  chk "proveedores con el rol Diseño, antes (nadie: 3.1.782 no tenía fit_design)" "$(sec "$RA" 'con Diseño' | una)" ""
  chk "proveedores con el rol Decisión, antes (id|activo|protocolo): el 1, que su protocolo no admite" "$(sec "$RA" 'con Decisión' | una)" "1|f|openai"
  chk "roles por proveedor, antes (id|activo|modelo|roles), de las fit_* de I0" "$(sec "$RA" 'roles por proveedor' | una)" "1|f|models/gemini-3.5-flash|conversation,vision,decision 2|t|Qwen3.5-9B|conversation,vision"
  chk "es_ES activo" "$(sec "$RA" es_ES)" "es_ES|t"
  NT=$(sec "$RA" traducciones | cut -d'|' -f1)
  NF=$(sec "$RA" 'traducciones fuera de pns' | cut -d'|' -f1)
  chk "traducciones es_ES antes (ensayo: $NT_E)" "$NT" "$NT_E" info
  chk "traducciones es_ES fuera de los pns_* antes (ensayo: $NF_E)" "$NF" "$NF_E" info
  echo "INFO    traducciones es_ES antes (n|huella): $(sec "$RA" traducciones); fuera de pns_*: $(sec "$RA" 'traducciones fuera de pns'); de los pns_*: $(sec "$RA" 'traducciones pns' | una)"
  lysql < "$LD/l4b_foto.sql" > "$FA"
  chk "foto de antes (filas sin error = traducciones es_ES)" "$(grep -cvE 'ERROR:|psql: error' "$FA" || true)|$(grep -cE 'ERROR:|psql: error' "$FA" || true)" "$NT|0"
  corte "estado antes"

  case "$OP" in
    -) echo "== 2. Ensayo en odoo shell, sin commit: B, B′ y C (rol), cada uno medido y deshecho con rollback. Lanzado a las $(date -u +%T) UTC" ;;
    BP) echo "== 2. [ALTERA LIYBEN] odoo shell: recarga B′ (B y restauración por id de las filas de fuera de los pns_*) y rol Diseño (D67), un solo commit. Lanzado a las $(date -u +%T) UTC" ;;
  esac
  ESP=""
  [ "$OP" = BP ] && ESP=$(grep "^   Y6 MEDIDA BP \|^   Y6 TOTAL BP " "$C" | sed 's/^   //' | LC_ALL=C sort -u)
  OFF=$(stat -c %s "$LOGF")
  { printf 'BD = "%s"\nOP = "%s"\nESPERADA = """%s"""\n' "$BD" "$OP" "$ESP"; cat "$LD/l4b.py"; } \
    | ( cd "$COMPOSE" && docker compose run --rm -T web odoo shell -d "$BD" ) > "$SL" 2>&1
  RC=$?
  N1=$(stat -c %s "$LOGF")
  tail -c +"$((OFF + 1))" "$LOGF" > "$SLOG"
  echo "terminado a las $(date -u +%T) UTC; salida del shell: $SL ($(wc -l < "$SL" | tr -d ' ') líneas); log: $SLOG ($(wc -l < "$SLOG" | tr -d ' ') líneas)"
  grep '^Y6 bd=\|^Y6 FOTO\|^Y6 TOTAL\|^Y6 BP \|^Y6 MEDIDA = \|^Y6 ROL\|^Y6 ROLLBACK\|^Y6 FIN\|^Y6 COMMIT' "$SL" | sed 's/^/   /'
  chk "salida del shell" "$RC" 0 info
  chk "el log no se ha rotado durante el shell" "$( [ "$N1" -ge "$OFF" ] && echo si || echo no)" si
  chk "shell en $BD y como superusuario" "$(grep -cx "Y6 bd=$BD su=True op=$OP" "$SL" || true)" 1
  chk "foto del shell = foto externa de antes (filas)" "$(sed -n 's/^Y6 FOTO n=//p' "$SL")" "$NT"
  chk "Traceback, ERROR o CRITICAL (salida del shell | log)" "$(grep -cE 'Traceback|ERROR|CRITICAL' "$SL" || true)|$(grep -cE 'Traceback|ERROR|CRITICAL' "$SLOG" || true)" "0|0"
  [ "$(cat "$SL" "$SLOG" | grep -c 'Traceback' || true)" = 0 ] || echo "   tipo de la excepción: $(cat "$SL" "$SLOG" | grep -oE '^[A-Za-z_.]*(Error|Exception)' | sort -u | una)"
  chk "roles en el shell (titulares de Diseño y Decisión, use_fallback y roles del proveedor 1, antes → después)" "$(grep -E '^Y6 ROL (antes|despues):' "$SL" | una)" "Y6 ROL antes: diseno=[] decision=[1] use_fallback=True roles_p1=conversation,vision,decision Y6 ROL despues: diseno=[1] decision=[] use_fallback=False roles_p1=conversation,vision,design"
  echo "-- WARNING del log por logger (sin el mensaje, que lleva textos de traducciones)"
  grep -oE ' WARNING [^ ]+ [^ ]+:' "$SLOG" | sort | uniq -c | sed 's/^/   /'
  echo "INFO    WARNING de pns_base.models.ir_translation: «drop duplicate» $(grep -c 'language import drop duplicate' "$SLOG" || true), «removed … duplicate» $(grep -c 'duplicate translation row' "$SLOG" || true) (ensayo: 9 por recarga)"
  for e in B BP; do
    if grep -q "^Y6 TOTAL $e " "$SL"; then
      echo "-- medida de $e por el módulo y el tipo de antes (fuera: igual / solo origen / texto cambiado / borradas; pns: igual / cambiadas / borradas; nuevas: en pns_* / fuera)"
      grep "^Y6 MEDIDA $e \|^Y6 TOTAL $e " "$SL" | sed 's/^/   /'
    fi
  done
  if [ "$OP" = - ]; then
    chk "B: borradas fuera de los pns_* (el core no borra al importar)" "$(grep -oE '^Y6 TOTAL B .*fuera_borradas=[0-9]+' "$SL" | sed 's/.*fuera_borradas=//')" 0
    chk "B (ensayo: 36 solo origen y 13 texto fuera de los pns_*; 196 cambiadas en los pns_*)" "$(grep -oE '^Y6 TOTAL B fuera_origen=[0-9]+ fuera_texto=[0-9]+' "$SL")|$(grep -oE '^Y6 TOTAL B .*pns_cambiadas=[0-9]+' "$SL" | sed 's/.*pns_cambiadas=//')" "Y6 TOTAL B fuera_origen=36 fuera_texto=13|196" info
    chk "B′: fuera de los pns_* sin ningún cambio" "$(grep -oE '^Y6 TOTAL BP fuera_origen=[0-9]+ fuera_texto=[0-9]+ fuera_borradas=[0-9]+ nuevas_fuera=[0-9]+' "$SL")" "Y6 TOTAL BP fuera_origen=0 fuera_texto=0 fuera_borradas=0 nuevas_fuera=0"
    chk "B′: restauradas por id = las que B cambia fuera de los pns_*" "$(sed -n 's/^Y6 BP guardadas=[0-9]* restauradas=\([0-9]*\) reinsertadas=\([0-9]*\)$/\1|\2/p' "$SL")" "$(grep -oE '^Y6 TOTAL B fuera_origen=[0-9]+ fuera_texto=[0-9]+' "$SL" | awk -F'[= ]' '{ print $5 + $7 "|0" }')"
    chk "B′: guardadas = traducciones fuera de los pns_* antes" "$(sed -n 's/^Y6 BP guardadas=\([0-9]*\) .*/\1/p' "$SL")" "$NF"
    for e in B BP C; do chk "rollback tras $e, en el mismo cursor" "$(grep -cx "Y6 ROLLBACK $e: igual=True" "$SL" || true)" 1; done
    chk "el shell terminó (rollback)" "$(grep -cx 'Y6 FIN comprobar (rollback)' "$SL" || true)" 1
  else
    chk "medida de BP igual a la del último comprobar (${C##*/})" "$(grep "^Y6 MEDIDA BP \|^Y6 TOTAL BP " "$SL" | LC_ALL=C sort -u | una)|$(grep -cx 'Y6 MEDIDA = la del comprobar: True' "$SL" || true)" "$(printf '%s\n' "$ESP" | una)|1"
    chk "B′: fuera de los pns_* sin ningún cambio" "$(grep -oE '^Y6 TOTAL BP fuera_origen=[0-9]+ fuera_texto=[0-9]+ fuera_borradas=[0-9]+ nuevas_fuera=[0-9]+' "$SL")" "Y6 TOTAL BP fuera_origen=0 fuera_texto=0 fuera_borradas=0 nuevas_fuera=0"
    chk "commit hecho" "$(grep -cx 'Y6 COMMIT OK' "$SL" || true)" 1
  fi

  echo "== 3. Después, desde otra sesión de solo lectura"
  chk "web parado (odoo shell va en un contenedor aparte)" "$(web)" 0
  RD=$(lysql < "$LD/l4b_estado.sql")
  printf '%s\n' "$RD" > "$DD"
  chk "consultas sin error (después)" "$(printf '%s\n' "$RD" | grep -ciE 'ERROR:|psql: error' || true)" 0
  chk "marcador final (después)" "$(printf '%s\n' "$RD" | grep -cx '## fin' || true)" 1
  chk "los demás roles, iguales (code|activo|use_fallback)" "$(sec "$RD" roles | grep -v '^design|' | una)" "$(sec "$RA" roles | grep -v '^design|' | una)"
  chk "es_ES activo" "$(sec "$RD" es_ES)" "es_ES|t"
  lysql < "$LD/l4b_foto.sql" > "$FD"
  chk "foto de después sin error" "$(grep -cE 'ERROR:|psql: error' "$FD" || true)" 0
  case "$OP" in -) ET=C ;; *) ET=$OP ;; esac
  MX=$(medida_ext "$ET" "$FA" "$FD")
  echo "-- medida externa (fotos de antes y después desde otra sesión, clasificadas por el módulo y el tipo de antes)"
  printf '%s\n' "$MX" | grep "^Y6 TOTAL " | sed 's/^/   /'
  if [ "$OP" = - ]; then
    chk "foto externa: después = antes (todo deshecho)" "$(cmp -s "$FA" "$FD" && echo igual || echo distinta)" igual
    chk "medida externa: nada cambiado" "$(printf '%s\n' "$MX" | grep '^Y6 TOTAL ')" "$(cero C)"
    chk "rol Diseño, sin cambios" "$(sec "$RD" 'rol Diseño' | una)" "$(sec "$RA" 'rol Diseño' | una)"
    chk "proveedores con el rol Diseño, sin cambios" "$(sec "$RD" 'con Diseño' | una)" ""
    chk "proveedores con el rol Decisión, sin cambios" "$(sec "$RD" 'con Decisión' | una)" "$(sec "$RA" 'con Decisión' | una)"
    chk "roles por proveedor, sin cambios" "$(sec "$RD" 'roles por proveedor' | una)" "$(sec "$RA" 'roles por proveedor' | una)"
    chk "traducciones es_ES, sin cambios (n|huella)" "$(sec "$RD" traducciones)" "$(sec "$RA" traducciones)"
    fin "$FINC"
  else
    if [ "$OP" = C ]; then
      chk "medida externa: traducciones sin ningún cambio (C)" "$(printf '%s\n' "$MX" | grep '^Y6 TOTAL ')" "$(cero C)"
    else
      chk "medida externa = medida del shell (las 13 líneas de $OP)" "$(printf '%s\n' "$MX" | LC_ALL=C sort | una)" "$(grep "^Y6 MEDIDA $OP \|^Y6 TOTAL $OP " "$SL" | LC_ALL=C sort | una)"
    fi
    if [ "$OP" = B ]; then
      echo "INFO    traducciones fuera de los pns_* (n|huella, por el módulo de después): antes $(sec "$RA" 'traducciones fuera de pns'), después $(sec "$RD" 'traducciones fuera de pns') (con B cambian: es lo elegido)"
    else
      chk "traducciones fuera de los pns_*, iguales (n|huella)" "$(sec "$RD" 'traducciones fuera de pns')" "$(sec "$RA" 'traducciones fuera de pns')"
    fi
    chk "rol Diseño sin alternativa (xml_id|code|activo|use_fallback|alternativa)" "$(sec "$RD" 'rol Diseño' | una)" "pns_ai_mcp.ai_provider_role_design|design|t|f|conversation"
    chk "rol Diseño solo en el proveedor 1, inactivo (D62: mientras siga inactivo, nadie diseña)" "$(sec "$RD" 'con Diseño' | una)" "1|f|f"
    chk "rol Decisión sin titulares (el protocolo openai no lo admite; nadie = «no»)" "$(sec "$RD" 'con Decisión' | una)" ""
    chk "roles por proveedor (id|activo|modelo|roles)" "$(sec "$RD" 'roles por proveedor' | una)" "1|f|models/gemini-3.5-flash|conversation,vision,design 2|t|Qwen3.5-9B|conversation,vision"
    echo "INFO    traducciones es_ES (n|huella): antes $(sec "$RA" traducciones), después $(sec "$RD" traducciones); de los pns_*: antes $(sec "$RA" 'traducciones pns' | una), después $(sec "$RD" 'traducciones pns' | una)"
    fin "$FINA"
  fi
  } 2>&1 | tee "$O"
  echo "Guardado en $O"
)
ld_l4b "$@"
