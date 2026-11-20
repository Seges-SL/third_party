lk_v() (
  # Limpieza final (punto 4, D69), VPS. Se lanza en la sesión SSH interactiva, en este orden y con corte entre cada uno:
  #   comprobar  (solo lectura salvo $LK: guarda la foto de lo que no se toca y copia en $LK/salvar los 6 archivos de
  #              /opt/odoo/pns_staging, los 11 /tmp/pns_* y el sitio de Nginx del staging)
  #   CLON       [ALTERA el clon, solo referencias] K1: borra las ramas 14.0-pns-ai-3 y 14.0-pns-ai-3973 (branch -d)
  #              y sus refs/remotes, como el UID 101
  #   DOCKER     [BORRA] K3.1: docker compose down -v en /opt/odoo/pns_staging (pns_demo y sus volúmenes, sin copia, N9)
  #   NGINX      [ALTERA Nginx] K3.2: quita el sitio de pns.liyben.com, nginx -t y recarga (si -t falla, lo repone)
  #   CERT       [BORRA] K3.3: certbot delete del certificado pns.liyben.com
  #   lista      (solo lectura) huella de la lista de $LK, para recoger en el equipo
  #   BORRAR <código de recoger>  [BORRA] K3.4: /opt/odoo/pns_staging, los 11 /tmp/pns_* y $LK (salida solo en pantalla).
  #              El código solo lo da «lk_e.sh recoger» cuando la copia al equipo termina con TODO OK.
  # Uso: bash /tmp/liyben_limpieza/lk_v.sh <modo>
  set -u
  umask 077
  MODO=${1:-}
  TANDA="LK V $MODO"
  LK=/tmp/liyben_limpieza
  COMPOSE=/opt/odoo
  CLON=/opt/odoo/addons/custom/third_party
  LOGF=/opt/odoo/logs/odoo-server.log
  ST=/opt/odoo/pns_staging
  SITE=/etc/nginx/conf.d/pns_liyben_com.conf
  CERT=pns.liyben.com
  M=d9b2e165b6d8069417b6b4e0329fa0f5be36c52b
  C3=578859b
  C3973=3df4307129a44719a27dd30c12dd479ab0335a6b
  ARBOL_RAMA="688 0dc381e0ca78b4d46a4c2c4c0b82eec7cedae444beded41b60867b11b411ba7a"
  REFS_ANTES="refs/heads/14.0 d9b2e16 refs/heads/14.0-pns-ai-3 578859b refs/heads/14.0-pns-ai-3973 3df4307 refs/remotes/origin/14.0 d9b2e16 refs/remotes/origin/14.0-pns-ai-3 578859b refs/remotes/origin/14.0-pns-ai-3973 3df4307"
  REFS_DESPUES="refs/heads/14.0 d9b2e16 refs/remotes/origin/14.0 d9b2e16"
  OTROS="odoo14_server odoo14_db odoo11_refrimar_liyben_com_web odoo11_refrimar_liyben_com_db odoo8_fumihogar_liyben_com_web odoo8_fumihogar_liyben_com_db"
  ST_CONT="odoo14_pns odoo14_pns_db"
  ST_VOL="55490707e8fa3d3d079e58c9efc0f7b3ab7ebe96a250c863db0f184eb0907c89 pns_staging_db-data pns_staging_odoo-data"
  VOL_LIYBEN=4f75fe5b0444ba787af2204b5781ee29e9b37ed18da764faf68cc2e574ca60bb
  ST_SALVAR="diag_bloqueo_20261016.txt diag_bloqueo_20261016_b.txt diag_bloqueo_20261016_b_odoo.log diag_bloqueo_20261016_odoo.log instalacion_1_ai_engine.log instalacion_2_chatboo.log"
  TMP_SALVAR="pns_diff_E1p.txt pns_diff_E2p.txt pns_diff_E4p.txt pns_e2p_diario_antes.txt pns_e2p_linea_base.txt pns_p9_antes_E1p.txt pns_p9_despues_E1p.txt pns_r4_r6_E1p.log pns_u_E1p.log pns_u_E2p.log pns_u_E4p.log"
  # v4 (D69): /web y no /web/login, que tiene limit_req (zona odoo_login, 5r/m por IP, compartida por los tres sitios):
  # las comprobaciones seguidas desde el propio VPS daban 503 (visto el 20/11). Esperados medidos ese día a las 15:35 UTC.
  URLS="https://liyben.com/web https://liyben.com/mcp https://refrimar.liyben.com/web https://fumihogar.liyben.com/web"
  COD_LIYBEN="https://liyben.com/web 303 https://liyben.com/mcp 404"
  COD_OTROS="https://refrimar.liyben.com/web 303 https://fumihogar.liyben.com/web 200"
  FI='{{.Name}}|{{.Config.Image}}|{{.Image}}|{{.State.Status}}|{{.State.StartedAt}}|reinicios={{.RestartCount}}'
  FM='{{range .Mounts}}{{.Type}}:{{.Name}}{{.Source}}>{{.Destination}}{{println}}{{end}}'
  F=0
  chk() {
    if [ "$2" = "$3" ]; then echo "OK      $1"
    elif [ "${4:-}" = info ]; then echo "INFO    $1: esperado [$3], obtenido [$2] (no bloquea)"
    else echo "FALLO   $1: esperado [$3], obtenido [$2]"; F=$((F + 1)); fi
  }
  una() { tr '\n' ' ' | sed 's/ *$//'; }
  corte() { [ "$F" = 0 ] || { echo "== $TANDA: $F FALLO(S) en «$1». No se ha seguido: pega la salida."; exit 1; }; }
  fin() { if [ "$F" = 0 ]; then echo "== $TANDA: TODO OK.${1:+ $1}"; else echo "== $TANDA: $F FALLO(S). No sigas: pega la salida."; fi; }
  g() { git --no-optional-locks -c safe.directory="$CLON" -C "$CLON" "$@"; }
  g101() { sudo -n -u messagebus env HOME=/tmp git -c safe.directory="$CLON" -C "$CLON" "$@"; }
  arbol() {
    ( cd "$1" && find pns_base pns_ai_mcp pns_ai_chatboo -type f -not -path '*/__pycache__/*' -not -name '*.pyc' | wc -l ) | tr -d ' '
    ( cd "$1" && find pns_base pns_ai_mcp pns_ai_chatboo -type f -not -path '*/__pycache__/*' -not -name '*.pyc' -print0 \
        | LC_ALL=C sort -z | xargs -0 sha256sum | sha256sum | cut -d' ' -f1 )
  }
  web() { ( cd "$COMPOSE" && docker compose ps --status running --services 2>/dev/null | grep -cx web || true ); }
  refs() { g for-each-ref --format='%(refname) %(objectname:short)' refs/heads refs/remotes 2>&1 | una; }
  n101() { find "$CLON" -path "$CLON/.git" -prune -o ! -uid 101 -print 2>/dev/null | wc -l | tr -d ' '; }
  certs() { sudo -n certbot certificates 2>/dev/null | awk '/Certificate Name:/{n=$3} /Expiry Date:/{print n"="$3"_"$4}' | LC_ALL=C sort; }
  # docker inspect no da los montajes siempre en el mismo orden (visto en el VPS el 20/11): se ordenan
  foto() { for c in $OTROS; do docker inspect -f "$FI" "$c" 2>&1; docker inspect -f "$FM" "$c" 2>&1 | grep . | LC_ALL=C sort | sed 's/^/  /'; done; echo "volumen $VOL_LIYBEN: $(docker ps -a --filter volume="$VOL_LIYBEN" --format '{{.Names}}' 2>&1 | una)"; docker image inspect -f 'odoo-web:latest {{.Id}}' odoo-web:latest 2>&1; }
  codigos() { for u in $URLS; do printf '%s %s\n' "$u" "$(curl -sS -o /dev/null -w '%{http_code}' "$u" 2>&1)"; done; }
  lista() { ( cd "$LK" && find . -type f -printf '%P\n' | LC_ALL=C sort | xargs -d '\n' sha256sum ); }
  originales() {
    for f in $ST_SALVAR; do printf '%s  pns_staging/%s\n' "$(sha256sum < "$ST/$f" | cut -d' ' -f1)" "$f"; done
    for f in $TMP_SALVAR; do printf '%s  tmp/%s\n' "$(sha256sum < "/tmp/$f" | cut -d' ' -f1)" "$f"; done
  }
  copias() { ( cd "$LK/salvar" && find pns_staging tmp -type f -print | LC_ALL=C sort | while read -r f; do printf '%s  %s\n' "$(sha256sum < "$f" | cut -d' ' -f1)" "$f"; done ); }
  ultima() { ls -t "$LK"/lk_v-"$1"-*.txt 2>/dev/null | head -1; }
  hecho() { local u; u=$(ultima "$1"); if [ -n "$u" ] && grep -q "^== LK V $1: TODO OK" "$u"; then echo si; else echo no; fi; }
  previa() { chk "$1 anterior con TODO OK ($(basename "$(ultima "$1")" 2>/dev/null))" "$(hecho "$1")" si; }
  # D69 (v3, 20/11): el CLON del VPS terminó con un solo FALLO, un 503 puntual de fumihogar (Odoo 8) en los códigos
  # HTTP de después; LIYBEN dio 200 y 404. DOCKER acepta ese CLON y solo ese.
  clon_aceptado() {
    local u; u=$(ultima CLON)
    if [ "$(hecho CLON)" = si ]; then echo si; return; fi
    if [ -n "$u" ] && [ "$(grep -c '^FALLO' "$u")" = 1 ] && grep -qx '== LK V CLON: 1 FALLO(S). No sigas: pega la salida.' "$u" \
       && grep '^FALLO' "$u" | grep -q '^FALLO   códigos HTTP = los de comprobar (LIYBEN, /mcp, refrimar, fumihogar): ' \
       && grep '^FALLO' "$u" | grep -oE 'obtenido \[.*\]$' | grep -qF 'obtenido [https://liyben.com/web/login 200 https://liyben.com/mcp 404 '; then
      echo "si (aceptado: su único FALLO es un código de refrimar o fumihogar; LIYBEN 200 y 404)"; return
    fi
    echo no
  }
  # D69 (v4, 20/11): el NGINX del VPS terminó con un solo FALLO, el /web/login de LIYBEN a 503 por el limit_req de
  # Nginx (zona odoo_login) tras las comprobaciones seguidas desde el propio VPS; /mcp 404; nginx -t, recarga y sitio
  # quitado, OK. CERT acepta ese NGINX y solo ese (y comprueba LIYBEN en /web antes de borrar).
  nginx_aceptado() {
    local u; u=$(ultima NGINX)
    if [ "$(hecho NGINX)" = si ]; then echo si; return; fi
    if [ -n "$u" ] && [ "$(grep -c '^FALLO' "$u")" = 1 ] && grep -qx '== LK V NGINX: 1 FALLO(S). No sigas: pega la salida.' "$u" \
       && grep -qx 'OK      nginx -t sin el sitio' "$u" && grep -qx 'OK      Nginx activo tras recargar' "$u" \
       && grep -qx 'OK      archivos de /etc/nginx que nombran pns.liyben.com' "$u" \
       && grep '^FALLO' "$u" | grep -q '^FALLO   códigos HTTP de LIYBEN = los de comprobar (/web/login, /mcp): ' \
       && grep '^FALLO' "$u" | grep -qF 'obtenido [https://liyben.com/web/login 503 https://liyben.com/mcp 404]'; then
      echo "si (aceptado: su único FALLO es el /web/login de LIYBEN a 503 por limit_req; /mcp 404; sitio quitado y recarga OK)"; return
    fi
    echo no
  }
  no_hecha() { chk "$MODO sin hacer aún (ninguna salida de $MODO con TODO OK)" "$(hecho "$MODO")" no; }
  comun() {
    chk "web de LIYBEN en marcha" "$(web)" 1
    local C; C=$(codigos)
    chk "códigos HTTP de LIYBEN (/web 303, /mcp 404)" "$(printf '%s\n' "$C" | head -2 | una)" "$COD_LIYBEN"
    chk "códigos HTTP de refrimar (/web 303) y fumihogar (/web 200)" "$(printf '%s\n' "$C" | tail -2 | una)" "$COD_OTROS" info
    chk "foto de lo que no se toca = la de comprobar (contenedores, arranques, montajes, volumen de LIYBEN, imagen)" "$(foto | sha256sum | cut -d' ' -f1)" "$(cut -d' ' -f1 "$LK/foto.sha256" 2>&1)"
  }
  log_desde() { OFF=$(stat -c %s "$LOGF" 2>&1); chk "posición del log de LIYBEN" "$(printf '%s' "$OFF" | grep -cxE '[0-9]+' || true)" 1; }
  log_despues() {
    local S; S=$(stat -c %s "$LOGF")
    chk "el log no se ha rotado" "$( [ "$S" -ge "$OFF" ] && echo no || echo si)" no
    chk "ERROR, CRITICAL o Traceback en el log de LIYBEN desde el principio de la tanda" "$(tail -c +"$((OFF + 1))" "$LOGF" | grep -cE ' (ERROR|CRITICAL) |^Traceback' || true)" 0
  }
  case "$MODO" in comprobar|CLON|DOCKER|NGINX|CERT|lista|BORRAR) ;; *) echo "Uso: bash $LK/lk_v.sh comprobar|CLON|DOCKER|NGINX|CERT|lista|BORRAR <huella>"; exit 1 ;; esac
  [ "$(cd "$(dirname "$0")" && pwd)" = "$LK" ] || { echo "Lánzala desde $LK: bash $LK/lk_v.sh $MODO"; exit 1; }
  if [ "$MODO" = lista ]; then
    [ "$(hecho CERT)" = si ] || { echo "== $TANDA: FALLO: falta CERT con TODO OK. No se ha seguido."; exit 1; }
    echo "== $TANDA ($LK): $(lista | wc -l | tr -d ' ') archivos"
    echo "huella de la lista: $(lista | sha256sum | cut -d' ' -f1)"
    echo "== $TANDA: TODO OK. En el equipo: bash ~/Descargas/lk_e.sh recoger <huella>"
    exit 0
  fi
  if [ "$MODO" = BORRAR ]; then
    HL=${2:-}
    printf '%s' "$HL" | grep -qxE '[0-9a-f]{64}' || { echo "Uso: bash $LK/lk_v.sh BORRAR <código que da lk_e.sh recoger>"; exit 1; }
  fi
  sudo -v || { echo "FALLO   sudo. No se ha seguido."; exit 1; }
  O="$LK/lk_v-$MODO-$(date -u +%Y%m%d-%H%M%S).txt"
  [ ! -e "$O" ] || { echo "Ya existe $O: vuelve a lanzarla dentro de un segundo"; exit 1; }
  [ "$MODO" = BORRAR ] && O=/dev/null
  {
  echo "== $TANDA (VPS, limpieza final): $(date -u '+%F %T') UTC"
  case "$MODO" in
  comprobar)
    echo "== 1. Clon de third_party (K1)"
    chk "rama y HEAD del clon" "$(g rev-parse --abbrev-ref HEAD 2>&1)|$(g rev-parse HEAD 2>&1)" "14.0|$M"
    chk "clon limpio y stash vacío" "$(g status --porcelain 2>&1 | wc -l | tr -d ' ')|$(g stash list 2>&1 | wc -l | tr -d ' ')" "0|0"
    chk "refspec del clon (solo 14.0)" "$(g config --get-all remote.origin.fetch 2>&1 | una)" "+refs/heads/14.0:refs/remotes/origin/14.0"
    chk "referencias del clon" "$(refs)" "$REFS_ANTES"
    for b in 14.0-pns-ai-3 14.0-pns-ai-3973; do
      chk "$b es antecesora de HEAD (branch -d la aceptará)" "$(g merge-base --is-ancestor "refs/heads/$b" HEAD 2>/dev/null && echo si || echo no)" si
      chk "$b sin upstream" "$(g rev-parse -q --verify --abbrev-ref "$b@{u}" 2>/dev/null || echo ninguno)" ninguno
    done
    chk "árbol de los módulos montados (archivos y huella)" "$(arbol "$CLON" | una)" "$ARBOL_RAMA"
    chk "propietario de .git/ (archivos que no son del UID 101)" "$(find "$CLON/.git" ! -uid 101 2>/dev/null | wc -l | tr -d ' ')" 0
    sha256sum "$CLON/.git/shallow" > "$LK/shallow.sha256" 2>&1
    n101 > "$LK/n101.txt"
    echo "   .git/shallow $(cut -c1-12 "$LK/shallow.sha256")…; archivos del árbol de trabajo que no son del UID 101: $(cat "$LK/n101.txt")"
    echo "== 2. Lo que no se toca (foto)"
    chk "web de LIYBEN en marcha" "$(web)" 1
    for c in $OTROS; do chk "contenedor $c en marcha" "$(docker inspect -f '{{.State.Status}}' "$c" 2>&1)" running; done
    chk "volumen $VOL_LIYBEN: solo de odoo14_server" "$(docker ps -a --filter volume="$VOL_LIYBEN" --format '{{.Names}}' 2>&1 | una)" odoo14_server
    chk "odoo14_pns usa odoo-web:latest, la imagen de LIYBEN (no se borra ninguna imagen)" "$(docker inspect -f '{{.Image}}' odoo14_pns 2>&1)" "$(docker image inspect -f '{{.Id}}' odoo-web:latest 2>&1)"
    foto > "$LK/foto.txt"; sha256sum "$LK/foto.txt" | cut -d' ' -f1 > "$LK/foto.sha256"
    codigos > "$LK/codigos.txt"
    sed 's/^/   /' "$LK/codigos.txt"
    chk "liyben.com/web y /mcp (D20)" "$(awk 'NR<=2{print $2}' "$LK/codigos.txt" | una)" "303 404"
    df -h / | tail -1 | sed 's/^/   disco: /'
    echo "== 3. Staging (K3)"
    chk "proyecto de Compose en $ST: servicios en marcha" "$( (cd "$ST" && docker compose ps --status running --services 2>&1) | LC_ALL=C sort | una)" "db web" info
    chk "volúmenes declarados en $ST/docker-compose.yml" "$( (cd "$ST" && docker compose config --volumes 2>&1) | LC_ALL=C sort | una)" "db-data odoo-data"
    chk "contenedores del proyecto pns_staging" "$(docker ps -a --filter label=com.docker.compose.project=pns_staging --format '{{.Names}}' 2>&1 | LC_ALL=C sort | una)" "$ST_CONT"
    for v in $ST_VOL; do chk "volumen ${v:0:24}: solo de contenedores del staging" "$(docker ps -a --filter volume="$v" --format '{{.Names}}' 2>&1 | grep -vxE 'odoo14_pns|odoo14_pns_db' | una)" ""; done
    chk "volúmenes de odoo14_pns y odoo14_pns_db" "$(docker inspect -f '{{range .Mounts}}{{if .Name}}{{.Name}} {{end}}{{end}}' $ST_CONT 2>&1 | tr -s ' ' '\n' | grep . | LC_ALL=C sort | una)" "$(printf '%s\n' $ST_VOL | LC_ALL=C sort | una)"
    chk "archivos de $ST que no son de $(id -un) (rm sin sudo)" "$(find "$ST" ! -user "$(id -un)" 2>/dev/null | wc -l | tr -d ' ')" 0
    chk "/tmp/pns_* = los 11 de las entregas de la 3879" "$(cd /tmp && ls -d pns_* 2>/dev/null | LC_ALL=C sort | una)" "$(printf '%s\n' $TMP_SALVAR | LC_ALL=C sort | una)"
    chk "/tmp/pns_* sin carpetas ni enlaces" "$(find /tmp -maxdepth 1 -name 'pns_*' ! -type f | wc -l | tr -d ' ')" 0
    chk "Nginx activo" "$(systemctl is-active nginx 2>&1)" active
    chk "nginx -t" "$(sudo -n nginx -t 2>&1 | grep -c 'test is successful' || true)" 1
    chk "archivos de /etc/nginx que nombran $CERT" "$(sudo -n grep -rl "$CERT" /etc/nginx 2>&1 | una)" "$SITE"
    chk "certificado $CERT en certbot" "$(sudo -n certbot certificates --cert-name "$CERT" 2>/dev/null | grep -c "Certificate Name: $CERT" || true)" 1
    sudo -n certbot certificates 2>/dev/null | grep -E 'Certificate Name' | sed 's/^ */   /'
    corte "comprobaciones"
    echo "== 4. [ESCRIBE solo en $LK/salvar] copias de lo que se borrará y los documentos citan"
    rm -rf -- "$LK/salvar"
    mkdir -p "$LK/salvar/pns_staging" "$LK/salvar/tmp" "$LK/salvar/nginx"
    for f in $ST_SALVAR; do cp -p -- "$ST/$f" "$LK/salvar/pns_staging/"; done
    for f in $TMP_SALVAR; do cp -p -- "/tmp/$f" "$LK/salvar/tmp/"; done
    cp -p -- "$SITE" "$LK/salvar/nginx/"
    chmod -R go-rwx "$LK/salvar"
    chk "copias = originales (17 archivos)" "$(copias | sha256sum | cut -d' ' -f1)|$(copias | wc -l | tr -d ' ')" "$(originales | LC_ALL=C sort -k2 | sha256sum | cut -d' ' -f1)|17"
    chk "copia del sitio de Nginx = el original" "$(sha256sum < "$LK/salvar/nginx/pns_liyben_com.conf" | cut -d' ' -f1)" "$(sha256sum < "$SITE" | cut -d' ' -f1)"
    originales | LC_ALL=C sort -k2 > "$LK/salvar/originales.sha256"
    fin "Corte: pega la salida. Después, CLON antes de una hora."
    ;;
  CLON)
    UC=$(ultima comprobar)
    previa comprobar
    chk "comprobar de hace menos de una hora (si no, repítelo)" "$( [ -n "$UC" ] && [ $(( $(date +%s) - $(stat -c %Y "$UC") )) -lt 3600 ] && echo si || echo no)" si
    no_hecha
    chk "referencias del clon" "$(refs)" "$REFS_ANTES"
    chk "rama, HEAD y status del clon" "$(g rev-parse --abbrev-ref HEAD)|$(g rev-parse HEAD)|$(g status --porcelain | wc -l | tr -d ' ')" "14.0|$M|0"
    comun
    log_desde
    corte "comprobaciones previas"
    echo "== [ALTERA el clon, solo referencias] como el UID 101, a las $(date -u +%T) UTC"
    for b in 14.0-pns-ai-3973 14.0-pns-ai-3; do g101 branch -d "$b" 2>&1 | sed 's/^/   /'; done
    for r in refs/remotes/origin/14.0-pns-ai-3973 refs/remotes/origin/14.0-pns-ai-3; do
      V=$(g rev-parse -q --verify "$r" 2>/dev/null)
      [ -n "$V" ] && g101 update-ref -d "$r" "$V" 2>&1 | sed 's/^/   /'
    done
    echo "== Después (solo lectura)"
    chk "referencias del clon" "$(refs)" "$REFS_DESPUES"
    chk "rama, HEAD y status del clon" "$(g rev-parse --abbrev-ref HEAD)|$(g rev-parse HEAD)|$(g status --porcelain | wc -l | tr -d ' ')" "14.0|$M|0"
    chk "árbol de los módulos montados (archivos y huella)" "$(arbol "$CLON" | una)" "$ARBOL_RAMA"
    chk ".git/shallow sin cambios" "$(sha256sum "$CLON/.git/shallow" 2>&1)" "$(cat "$LK/shallow.sha256")"
    chk "propietario de .git/ (archivos que no son del UID 101)" "$(find "$CLON/.git" ! -uid 101 2>/dev/null | wc -l | tr -d ' ')" 0
    chk "archivos del árbol de trabajo que no son del UID 101: los mismos" "$(n101)" "$(cat "$LK/n101.txt")"
    chk "commits de las ramas borradas aún en el clon (sin gc)" "$(g cat-file -t "$C3973" 2>&1)" commit
    comun
    log_despues
    fin "Corte: pega la salida. Después, DOCKER."
    ;;
  DOCKER)
    A=$(clon_aceptado)
    case "$A" in "si ("*) echo "INFO    CLON ($(basename "$(ultima CLON)")): $A";; esac
    chk "CLON anterior con TODO OK o aceptado (D69, v3)" "${A%% *}" si
    no_hecha
    comun
    log_desde
    corte "comprobaciones previas"
    echo "== [BORRA pns_demo: contenedores, red y volúmenes del staging, sin copia (N9)] a las $(date -u +%T) UTC"
    ( cd "$ST" && docker compose down -v 2>&1 ) | sed 's/^/   /'
    echo "== Después (solo lectura)"
    chk "contenedores del proyecto pns_staging" "$(docker ps -a --filter label=com.docker.compose.project=pns_staging --format '{{.Names}}' 2>&1 | una)" ""
    for v in $ST_VOL; do chk "volumen ${v:0:24} borrado" "$(docker volume inspect "$v" >/dev/null 2>&1 && echo existe || echo no)" no; done
    chk "redes del proyecto pns_staging" "$(docker network ls --filter label=com.docker.compose.project=pns_staging --format '{{.Name}}' 2>&1 | una)" ""
    comun
    log_despues
    echo "   pns.liyben.com/web/login: $(curl -sS -o /dev/null -w '%{http_code}' https://$CERT/web/login 2>&1) (sin servicio; Nginx aún lo publica)"
    fin "Corte: pega la salida. Después, NGINX."
    ;;
  NGINX)
    previa DOCKER
    no_hecha
    chk "copia del sitio en $LK/salvar = el sitio" "$(sha256sum < "$LK/salvar/nginx/pns_liyben_com.conf" 2>&1 | cut -d' ' -f1)" "$(sha256sum < "$SITE" 2>&1 | cut -d' ' -f1)"
    chk "nginx -t antes" "$(sudo -n nginx -t 2>&1 | grep -c 'test is successful' || true)" 1
    comun
    corte "comprobaciones previas"
    echo "== [ALTERA Nginx] quita $SITE, nginx -t y recarga, a las $(date -u +%T) UTC"
    sudo -n rm -- "$SITE"
    if sudo -n nginx -t 2>&1 | grep -q 'test is successful'; then
      chk "nginx -t sin el sitio" ok ok
      sudo -n systemctl reload nginx 2>&1 | sed 's/^/   /'
      chk "Nginx activo tras recargar" "$(systemctl is-active nginx 2>&1)" active
    else
      sudo -n nginx -t 2>&1 | sed 's/^/   /'
      sudo -n install -m 644 -o root -g root "$LK/salvar/nginx/pns_liyben_com.conf" "$SITE"
      chk "nginx -t sin el sitio (falló: sitio repuesto, sin recargar)" falla ok
      chk "sitio repuesto = el original" "$(sha256sum < "$SITE" 2>&1 | cut -d' ' -f1)" "$(sha256sum < "$LK/salvar/nginx/pns_liyben_com.conf" | cut -d' ' -f1)"
    fi
    echo "== Después (solo lectura)"
    chk "archivos de /etc/nginx que nombran $CERT" "$(sudo -n grep -rl "$CERT" /etc/nginx 2>&1 | una)" ""
    sleep 2
    comun
    echo "   pns.liyben.com/web/login: $(curl -sS -o /dev/null -w '%{http_code}' https://$CERT/web/login 2>&1) (sin sitio propio)"
    fin "Corte: pega la salida. Después, CERT."
    ;;
  CERT)
    A=$(nginx_aceptado)
    case "$A" in "si ("*) echo "INFO    NGINX ($(basename "$(ultima NGINX)")): $A";; esac
    chk "NGINX anterior con TODO OK o aceptado (D69, v4)" "${A%% *}" si
    no_hecha
    chk "certificado $CERT en certbot" "$(sudo -n certbot certificates --cert-name "$CERT" 2>/dev/null | grep -c "Certificate Name: $CERT" || true)" 1
    chk "ningún archivo de /etc/nginx nombra $CERT" "$(sudo -n grep -rl "$CERT" /etc/nginx 2>&1 | una)" ""
    OTROS_CERT=$(certs | grep -v "^$CERT=" | una)
    chk "otros certificados (además de $CERT)" "$(printf '%s' "$OTROS_CERT" | wc -w | tr -d ' ')" 3 info
    comun
    corte "comprobaciones previas"
    echo "== [BORRA] certbot delete --cert-name $CERT, a las $(date -u +%T) UTC"
    sudo -n certbot delete --cert-name "$CERT" --non-interactive 2>&1 | sed 's/^/   /'
    echo "== Después (solo lectura)"
    chk "certificado $CERT en certbot" "$(sudo -n certbot certificates 2>/dev/null | grep -c "Certificate Name: $CERT" || true)" 0
    chk "renovación de $CERT" "$(sudo -n test -e "/etc/letsencrypt/renewal/$CERT.conf" && echo existe || echo no)" no
    chk "los demás certificados, iguales (nombre y caducidad)" "$(certs | una)" "$OTROS_CERT"
    chk "nginx -t" "$(sudo -n nginx -t 2>&1 | grep -c 'test is successful' || true)" 1
    comun
    fin "Pega la salida. Después: bash $LK/lk_v.sh lista y, en el equipo, lk_e.sh recoger."
    ;;
  BORRAR)
    previa CERT
    chk "código de recoger = el de la lista de $LK (copia al equipo con TODO OK y nada cambiado desde entonces)" "$(printf '%s recogido\n' "$(lista | sha256sum | cut -d' ' -f1)" | sha256sum | cut -d' ' -f1)" "$HL"
    chk "originales = las copias recogidas" "$(originales | LC_ALL=C sort -k2)" "$(cat "$LK/salvar/originales.sha256")"
    chk "archivos de $ST que no son de $(id -un)" "$(find "$ST" ! -user "$(id -un)" 2>/dev/null | wc -l | tr -d ' ')" 0
    chk "contenedores del proyecto pns_staging (ya bajado)" "$(docker ps -a --filter label=com.docker.compose.project=pns_staging --format '{{.Names}}' 2>&1 | una)" ""
    comun
    corte "comprobaciones previas"
    echo "== [BORRA] $ST, los 11 /tmp/pns_* y $LK, a las $(date -u +%T) UTC"
    rm -rf -- "$ST"
    for f in $TMP_SALVAR; do rm -f -- "/tmp/$f"; done
    chk "$ST borrada" "$(test -e "$ST" && echo existe || echo no)" no
    chk "/tmp/pns_*" "$(cd /tmp && ls -d pns_* 2>/dev/null | una)" ""
    chk "clon: referencias, árbol y status" "$(refs)|$(arbol "$CLON" | una)|$(g status --porcelain | wc -l | tr -d ' ')" "$REFS_DESPUES|$ARBOL_RAMA|0"
    comun
    rm -rf -- "$LK"
    chk "$LK borrada" "$(test -e "$LK" && echo existe || echo no)" no
    df -h / | tail -1 | sed 's/^/   disco: /'
    fin "Limpieza del VPS hecha. Pega la salida; cierra la sesión y, pasados unos minutos, U0 v4 en el equipo."
    ;;
  esac
  } 2>&1 | tee "$O"
  [ "$O" = /dev/null ] || echo "Guardado en $O"
)
lk_v "$@"
