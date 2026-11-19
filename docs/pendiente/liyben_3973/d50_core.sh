d50_core() (
  set -u
  umask 077
  R="${D50_R:-/opt/odoo-src/14.0/odoo}"
  H="${D50_H:-cc0060e889603eb2e47fa44a8a22a70d7d784185}"
  D="$HOME/pns_ai_3973/liyben"
  F=0
  chk() { if [ "$2" = "$3" ]; then echo "OK      $1"; else echo "FALLO   $1 (obtenido «$2», esperado «$3»)"; F=$((F+1)); fi; }
  mkdir -p -m 700 "$D" || exit 1
  O="$D/d50-$(date +%Y%m%d-%H%M%S).txt"
  test ! -e "$O" || { echo "Ya existe $O: espera un segundo y repite"; exit 1; }
  {
  echo "== D50: signup_cancel en el core de referencia ($R), solo lectura"
  echo "== 1. Comprobaciones previas"
  chk "carpeta de referencia" "$(test -d "$R" && echo si || echo no)" si
  [ "$F" = 0 ] || { echo "== D50: FALLO ($F)"; exit 1; }
  chk "HEAD del clon = cc0060e" "$(git -C "$R" rev-parse HEAD 2>/dev/null)" "$H"
  chk "clon sin cambios locales (líneas de status)" "$(git -C "$R" status --porcelain 2>/dev/null | wc -l | tr -d ' ')" 0
  N=$(find "$R" -path '*/addons/auth_signup/models/res_partner.py' | wc -l | tr -d ' ')
  chk "auth_signup/models/res_partner.py (archivos)" "$N" 1
  [ "$F" = 0 ] || { echo "== D50: FALLO ($F). No sigo."; exit 1; }
  P=$(find "$R" -path '*/addons/auth_signup/models/res_partner.py')
  A=$(dirname "$(dirname "$P")")
  echo "INFO    módulo: ${A#$R/} ; res_partner.py $(wc -l < "$P" | tr -d ' ') líneas, sha256 $(sha256sum "$P" | cut -c1-16)…"
  echo "== 2. Líneas de res_partner.py con signup_*, SQL o def (grep -n)"
  grep -nE 'signup_(token|type|expiration|cancel|valid|url)|cr\.execute|SELECT|UPDATE|^ *def |fields\.' "$P"
  echo "== 3. Métodos de res_partner.py que tocan signup_token (completos)"
  awk '
    function flush() { if (buf ~ /signup_token|signup_cancel/) printf "%s", buf; buf = "" }
    /^    @/ { if (!dec) flush(); dec = 1; blk = 1; buf = buf sprintf("%5d  %s\n", NR, $0); next }
    /^    def / { if (!dec) flush(); dec = 0; blk = 1; buf = buf sprintf("%5d  %s\n", NR, $0); next }
    /^    [^ ]/ || /^[^ \t\n]/ { flush(); blk = 0; dec = 0; next }
    blk { buf = buf sprintf("%5d  %s\n", NR, $0) }
    END { flush() }
  ' "$P"
  echo "== 4. auth_signup: otros archivos con signup_token o signup_cancel (n.º de líneas)"
  grep -rcE 'signup_token|signup_cancel' "$A" --include='*.py' --include='*.xml' --include='*.js' | grep -v ':0$' | sed "s|^$R/||" | sort
  echo "== 5. Llamadas a signup_cancel en todo el core (grep -rn)"
  grep -rnE 'signup_cancel' "$R" --include='*.py' --include='*.xml' --include='*.js' | sed "s|^$R/||" | cut -c1-160
  echo "== 6. Fuera de auth_signup: archivos con signup_token (n.º de líneas)"
  grep -rcE 'signup_token' "$R" --include='*.py' --include='*.xml' --include='*.js' --include='*.sql' | grep -v ':0$' | grep -v '/auth_signup/' | sed "s|^$R/||" | sort
  echo "== D50: $( [ "$F" = 0 ] && echo 'TODO OK (lo demás es informativo: pega la salida)' || echo "FALLO ($F)")"
  } 2>&1 | tee "$O"
  echo "Guardado en $O"
)
