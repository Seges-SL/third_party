lk_k8() (
  # Limpieza final (punto 4, D69), K8, equipo, sin red: restos del staging y laboratorio cc0060e, tras cerrar la
  # ficha 26 (D70). Modos, con corte entre cada uno; cada uno exige el anterior con TODO OK:
  #   comprobar  (solo lectura) las 2 copias de pns_demo, el laboratorio cc0060e (carpeta, imagen, BD), las BD
  #              p15_pns_demo_14 y p15b_pns_demo_14, y lo necesario para volver a lab_pns_ai_3973. Guarda las BD y
  #              las imágenes que se quedan y las huellas de las copias.
  #   CONTEXTO   [ARRANCA el web de lab_pns_ai_3973 y lo PARA] arrancar + «Al acabar corto» (C sobre
  #              lab_pns_ai_3973_14): el contexto activo deja de ser cc0060e. No abras localhost:8169.
  #   BORRAR     [BORRA] bd-borrar de las 3 BD (desde lab_pns_ai_3973), las 2 copias, ~/GitHub/lab_pns_ai_cc0060e y
  #              la imagen odoo-dev:14-lab_pns_ai_cc0060e. Las salidas de texto se quedan.
  # Uso: bash ~/Descargas/lk_k8.sh comprobar | CONTEXTO | BORRAR
  set -u
  umask 077
  MODO=${1:-}
  TANDA="LK K8 $MODO"
  DL=~/pns_ai_3973/liyben/limpieza
  EST=$DL/k8_comprobar_estado.txt
  REPO=~/GitHub/third_party
  LAB=~/GitHub/lab_pns_ai_cc0060e
  IMG=odoo-dev:14-lab_pns_ai_cc0060e
  VUELTA=~/GitHub/lab_pns_ai_3973
  VUELTA_IMG=odoo-dev:14-lab_pns_ai_3973
  VUELTA_BD=lab_pns_ai_3973_14
  BDS="lab_pns_ai_cc0060e_14 p15_pns_demo_14 p15b_pns_demo_14"
  T3=~/pns_ai_3973/staging/pns_demo_antes_3973-20261118-1744.dump
  T3_TAM=5383981
  P15=~/pns_ai_3973/fase4/cc0060e/p15/pns_demo_20261118-1329.dump
  P15_TAM=5383353
  SALIDAS="$HOME/pns_ai_3973/staging $HOME/pns_ai_3973/fase4/cc0060e"
  N_SALIDAS=74
  DOCKERFILE_SHA=8800092a909f73bdecac1e9b1c1379fdb36c3cd65da55f286775732daf50e69a
  ESTADO=~/odoo-dev/14.0/estado
  LOGS=~/odoo-dev/14.0/logs
  CDP=~/pns_ai_3973/fase4/lab/lab_cdp.py
  WEB=odoo-dev-14-web-1
  F=0
  chk() {
    if [ "$2" = "$3" ]; then echo "OK      $1"
    else echo "FALLO   $1: esperado [$3], obtenido [$2]"; F=$((F + 1)); fi
  }
  una() { tr '\n' ' ' | sed 's/ *$//'; }
  corte() { [ "$F" = 0 ] || { echo "== $TANDA: $F FALLO(S) en «$1». No se ha seguido: pega la salida."; exit 1; }; }
  fin() { if [ "$F" = 0 ]; then echo "== $TANDA: TODO OK.${1:+ $1}"; else echo "== $TANDA: $F FALLO(S). No sigas: pega la salida."; fi; }
  contexto() { sed -n 's/^REPO=//p' "$ESTADO" 2>/dev/null; }
  web() { docker ps --format '{{.Names}}' 2>/dev/null | grep -cx "$WEB" || true; }
  bds() { (cd "$VUELTA" 2>/dev/null && odoo-dev 14 bd-lista 2>&1) | grep -E '^[A-Za-z0-9_]+$' | LC_ALL=C sort; }
  hay_bd() { bds | grep -cx -- "$1" || true; }
  otras_bd() { bds | grep -vxF "$(printf '%s\n' $BDS)" | una; }
  img() { docker image ls -q "$1" 2>/dev/null | wc -l | tr -d ' '; }
  otras_img() { docker image ls --format '{{.Repository}}:{{.Tag}} {{.ID}}' 2>&1 | grep -v "^$IMG " | LC_ALL=C sort | una; }
  lab_archivos() { ( cd "$LAB" 2>/dev/null && find . -path ./.git -prune -o -type f -print | LC_ALL=C sort | una ); }
  n_salidas() { find $SALIDAS -type f 2>/dev/null | wc -l | tr -d ' '; }
  huella() { sha256sum "$1" 2>/dev/null | cut -d' ' -f1; }
  ultima() { ls -t "$DL"/lk_k8-"$1"-*.txt 2>/dev/null | head -1; }
  marca() { if [ -n "$1" ] && [ -f "$1" ]; then grep -cx -- "$2" "$1" || true; else echo 0; fi; }
  dato() { sed -n "s/^$1=//p" "$EST" 2>/dev/null; }
  FIN_C="Corte: pega la salida. Después, CONTEXTO (no abras localhost:8169)."
  FIN_X="Corte: contexto lab_pns_ai_3973 con el web parado. Pega la salida. Después, BORRAR."
  case "$MODO" in comprobar|CONTEXTO|BORRAR) ;; *) echo "Uso: bash $0 comprobar | CONTEXTO | BORRAR"; exit 1 ;; esac
  mkdir -p "$DL" && chmod 700 "$DL" || exit 1
  O="$DL/lk_k8-$MODO-$(date +%Y%m%d-%H%M%S).txt"
  [ ! -e "$O" ] || { echo "Ya existe $O: vuelve a lanzarla dentro de un segundo"; exit 1; }
  {
  echo "== $TANDA (equipo, limpieza final: K8): $(date '+%F %T')"
  case "$MODO" in
    CONTEXTO) U=$(ultima comprobar); chk "último comprobar (${U##*/}) con TODO OK" "$(marca "$U" "== LK K8 comprobar: TODO OK. $FIN_C")" 1 ;;
    BORRAR)   U=$(ultima CONTEXTO); chk "último CONTEXTO (${U##*/}) con TODO OK" "$(marca "$U" "== LK K8 CONTEXTO: TODO OK. $FIN_X")" 1 ;;
  esac
  echo "== 1. odoo-dev 14"
  if [ "$MODO" = BORRAR ]; then chk "contexto activo (ya no es cc0060e)" "$(contexto)" "$VUELTA"
  else chk "contexto activo" "$(contexto)" "$LAB"; fi
  chk "web parado" "$(web)" 0
  echo "== 2. Lo que se borra"
  for B in $BDS; do chk "BD $B existe" "$(hay_bd "$B")" 1; done
  chk "copia de T3: tamaño" "$(stat -c %s "$T3" 2>&1)" "$T3_TAM"
  chk "copia de P-15: tamaño" "$(stat -c %s "$P15" 2>&1)" "$P15_TAM"
  chk "archivos del laboratorio (sin .git)" "$(lab_archivos)" "./.odoo-dev.conf ./CLAUDE.md ./infra/Dockerfile.14"
  chk "infra/Dockerfile.14 = lab_3973/Dockerfile.14.cc0060e del repo (reconstruible)" "$(huella "$LAB/infra/Dockerfile.14")|$(huella "$REPO/docs/pendiente/lab_3973/Dockerfile.14.cc0060e")" "$DOCKERFILE_SHA|$DOCKERFILE_SHA"
  chk "laboratorio sin remoto" "$( [ -d "$LAB/.git" ] && git -C "$LAB" remote 2>&1 | una || echo 'sin .git')" ""
  chk "imagen $IMG existe" "$(img "$IMG")" 1
  chk "contenedores (también parados) con la imagen" "$(docker ps -a --filter ancestor="$IMG" --format '{{.Names}}' 2>&1 | una)" ""
  echo "== 3. Lo que se queda"
  chk "vuelta: carpeta, imagen y BD de lab_pns_ai_3973" "$( [ -f "$VUELTA/.odoo-dev.conf" ] && echo si || echo no)|$(img "$VUELTA_IMG")|$(hay_bd "$VUELTA_BD")" "si|1|1"
  chk "lab_cdp.py" "$( [ -f "$CDP" ] && echo si || echo no)" si
  chk "salidas en staging/ y fase4/cc0060e/ (archivos)" "$(n_salidas)" "$N_SALIDAS"
  if [ "$MODO" = comprobar ]; then
    echo "   BD que se quedan: $(otras_bd)"
    echo "   imágenes que se quedan: $(otras_img | wc -w | awk '{print $1 / 2}')"
  else
    chk "BD que se quedan = las de comprobar" "$(otras_bd)" "$(dato OTRAS_BD)"
    chk "imágenes que se quedan = las de comprobar" "$(otras_img)" "$(dato OTRAS_IMG)"
    chk "copias de T3 y P-15 = las de comprobar (SHA-256)" "$(huella "$T3")|$(huella "$P15")" "$(dato T3_SHA)|$(dato P15_SHA)"
  fi
  corte "comprobaciones"
  case "$MODO" in
  comprobar)
    { echo "OTRAS_BD=$(otras_bd)"; echo "OTRAS_IMG=$(otras_img)"; echo "T3_SHA=$(huella "$T3")"; echo "P15_SHA=$(huella "$P15")"; } > "$EST"
    echo "   guardado: $EST (copias: T3 $(dato T3_SHA | cut -c1-12)…, P-15 $(dato P15_SHA | cut -c1-12)…)"
    fin "$FIN_C"
    ;;
  CONTEXTO)
    echo "== [ARRANCA el web] odoo-dev 14 arrancar desde $VUELTA, a las $(date +%T)"
    ( cd "$VUELTA" && odoo-dev 14 arrancar ) > "$DL/k8_arrancar-$(date +%Y%m%d-%H%M%S).txt" 2>&1
    A=$?
    chk "arrancar: código (salida en $DL/k8_arrancar-*.txt)" "$A" 0
    chk "contexto activo tras arrancar" "$(contexto)" "$VUELTA"
    echo "== Al acabar corto: espera a «HTTP service (werkzeug) running» (máx. 2 min; sin espera si arrancar falló)"
    W=no
    [ "$A" = 0 ] && for i in $(seq 1 40); do
      (cd "$VUELTA" && odoo-dev 14 log 200 2>&1) | grep -q 'HTTP service (werkzeug) running' && { W=si; break; }
      sleep 3
    done
    chk "werkzeug en marcha" "$W" si
    LOG_LAB=$LOGS/servidor-$(date +%Y%m%d-%H%M%S).log
    (cd "$VUELTA" && odoo-dev 14 log all) > "$LOG_LAB" 2>&1
    echo "   log guardado: $LOG_LAB ($(wc -l < "$LOG_LAB" | tr -d ' ') líneas)"
    python3 -I "$CDP" c --lab lab_pns_ai_3973 --bd "$VUELTA_BD" < "$LOG_LAB" 2>&1 | sed 's/^/   /'
    C=${PIPESTATUS[0]}
    chk "C: código" "$C" 0
    ( cd "$VUELTA" && odoo-dev 14 parar ) 2>&1 | tail -3 | sed 's/^/   /'
    echo "== Después (solo lectura)"
    chk "contexto activo" "$(contexto)" "$VUELTA"
    chk "web parado" "$(web)" 0
    echo "   para el registro: primera línea $(grep -oE '[0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}:[0-9]{2}' "$LOG_LAB" | head -1) UTC,"\
         "última $(grep -oE '[0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}:[0-9]{2}' "$LOG_LAB" | tail -1) UTC;"\
         "Starting job: $(grep -c 'ir_cron: Starting job' "$LOG_LAB" || true)"
    fin "$FIN_X"
    ;;
  BORRAR)
    echo "== [BORRA] las 3 BD, las 2 copias, $LAB e imagen $IMG, a las $(date +%T)"
    for B in $BDS; do
      echo "   bd-borrar $B (desde $VUELTA; en la terminal no pregunta)"
      ( cd "$VUELTA" && odoo-dev 14 bd-borrar "$B" ) < /dev/null 2>&1 | tail -2 | sed 's/^/      /'
    done
    rm -f -- "$T3" "$P15"
    rm -rf -- "$LAB"
    docker image rm "$IMG" 2>&1 | tail -2 | sed 's/^/   /'
    echo "== Después (solo lectura)"
    for B in $BDS; do chk "BD $B borrada" "$(hay_bd "$B")" 0; done
    chk "copias de T3 y P-15 borradas" "$(test -e "$T3" && echo existe || echo no)|$(test -e "$P15" && echo existe || echo no)" "no|no"
    chk "$LAB borrada" "$(test -e "$LAB" && echo existe || echo no)" no
    chk "imagen $IMG borrada" "$(img "$IMG")" 0
    chk "BD que se quedan, sin cambios" "$(otras_bd)" "$(dato OTRAS_BD)"
    chk "imágenes que se quedan, sin cambios" "$(otras_img)" "$(dato OTRAS_IMG)"
    chk "salidas de texto, intactas (archivos)" "$(n_salidas)" "$((N_SALIDAS - 2))"
    chk "contexto lab_pns_ai_3973 y web parado" "$(contexto)|$(web)" "$VUELTA|0"
    fin "En GitHub Desktop no cambia nada. Pega la salida: después, el [DOC] de K8."
    ;;
  esac
  } 2>&1 | tee "$O"
  echo "Guardado en $O"
)
lk_k8 "$@"
