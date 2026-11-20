lu_u5() (
  # U5 del uso real en LIYBEN: las 3 traducciones es_ES de más del despliegue frente al ensayo. Local y de solo lectura:
  # compara por contenido (sin el id) la foto de L4b comprobar (LIYBEN tras el -u) con la de Y6 v3 comprobar (ensayo tras
  # el -u). Las fotos no llevan textos: id|tipo|módulo|md5(name)|state|md5(comments)|md5(value). Escribe solo en
  # ~/pns_ai_3973/liyben/uso/.
  set -u
  umask 077
  TANDA="LU U5"
  U=~/pns_ai_3973/liyben/uso
  FP=~/pns_ai_3973/liyben/despliegue/vps/l4b_foto_antes-comprobar-20261120-105038.txt
  F=0
  chk() {
    if [ "$2" = "$3" ]; then echo "OK      $1"
    elif [ "${4:-}" = info ]; then echo "INFO    $1: esperado [$3], obtenido [$2] (no bloquea)"
    else echo "FALLO   $1: esperado [$3], obtenido [$2]"; F=$((F + 1)); fi
  }
  corte() { [ "$F" = 0 ] || { echo "== $TANDA: $F FALLO(S) en «$1». No se ha seguido: pega la salida."; exit 1; }; }
  fin() { if [ "$F" = 0 ]; then echo "== $TANDA: TODO OK.${1:+ $1}"; else echo "== $TANDA: $F FALLO(S). No sigas: pega la salida."; fi; }
  M=$(date +%Y%m%d-%H%M%S)
  O="$U/u5-$M.txt"
  [ -d "$U" ] && [ ! -e "$O" ] || { echo "Falta $U o ya existe $O"; exit 1; }
  T=$(mktemp -d) || exit 1
  trap 'rm -rf "$T"' EXIT
  {
  echo "== $TANDA (equipo: traducciones es_ES de LIYBEN tras el -u frente al ensayo; local y solo lectura): $(date '+%F %T')"
  echo "== 1. Fotos"
  FE=$(ls ~/pns_ai_3973/liyben/y6_foto_antes-comprobar-20261119-153*.txt 2>/dev/null)
  chk "una sola foto de Y6 v3 comprobar (19/11, 15:3x)" "$(printf '%s' "$FE" | grep -c . || true)" 1
  chk "foto de L4b comprobar (${FP##*/})" "$(test -f "$FP" && echo existe || echo falta)" existe
  corte "fotos"
  echo "   ensayo: ${FE##*/}"
  chk "filas del ensayo (45 966)" "$(wc -l < "$FE" | tr -d ' ')" 45966
  chk "filas de LIYBEN (45 969)" "$(wc -l < "$FP" | tr -d ' ')" 45969
  chk "filas con error en las fotos" "$(cat "$FE" "$FP" | grep -cE 'ERROR:|psql: error' || true)" 0
  chk "formato (7 campos) en las dos" "$(cat "$FE" "$FP" | awk -F'|' 'NF != 7' | grep -c . || true)" 0
  corte "formato"

  echo "== 2. Diferencias por contenido (sin el id)"
  cut -d'|' -f2- "$FE" | LC_ALL=C sort > "$T/e"
  cut -d'|' -f2- "$FP" | LC_ALL=C sort > "$T/p"
  LC_ALL=C comm -13 "$T/e" "$T/p" > "$T/solo_p"
  LC_ALL=C comm -23 "$T/e" "$T/p" > "$T/solo_e"
  NP=$(grep -c . "$T/solo_p" || true); NE=$(grep -c . "$T/solo_e" || true)
  echo "   solo en LIYBEN: $NP; solo en el ensayo: $NE"
  chk "diferencia neta (LIYBEN − ensayo)" "$((NP - NE))" 3
  echo "-- solo en LIYBEN, por tipo|módulo|state (n)"
  cut -d'|' -f1,2,4 "$T/solo_p" | sort | uniq -c | sed 's/^/   /'
  echo "-- solo en el ensayo, por tipo|módulo|state (n)"
  cut -d'|' -f1,2,4 "$T/solo_e" | sort | uniq -c | sed 's/^/   /'
  echo "-- solo en LIYBEN, con su id en LIYBEN (id|tipo|módulo|md5(name)|state); máximo 20"
  awk -F'|' 'NR == FNR { w[$0] = 1; next } { k = $0; sub(/^[^|]*\|/, "", k); if (k in w) print $1 "|" $2 "|" $3 "|" $4 "|" $5 }' "$T/solo_p" "$FP" | head -20 | sed 's/^/   /'
  echo "-- mismas claves (tipo|módulo|md5(name)) en las dos partes: cambio de texto o de estado, no fila nueva"
  cut -d'|' -f1-3 "$T/solo_p" | LC_ALL=C sort -u > "$T/kp"
  cut -d'|' -f1-3 "$T/solo_e" | LC_ALL=C sort -u > "$T/ke"
  echo "   $(LC_ALL=C comm -12 "$T/kp" "$T/ke" | grep -c . || true)"
  fin "Pega la salida."
  } 2>&1 | tee "$O"
  echo "Guardado en $O"
)
lu_u5
