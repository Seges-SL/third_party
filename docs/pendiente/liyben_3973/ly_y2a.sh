ly_y2a() (
  set -u
  umask 022
  F=0
  chk() {
    if [ "$2" = "$3" ]; then echo "OK      $1"
    elif [ "${4:-}" = info ]; then echo "INFO    $1: esperado [$3], obtenido [$2] (no bloquea)"
    else echo "FALLO   $1: esperado [$3], obtenido [$2]"; F=$((F + 1)); fi
  }
  D=~/pns_ai_3973/liyben
  L=~/GitHub/lab_liyben_3973
  CC=~/GitHub/third_party/docs/pendiente/lab_3973/Dockerfile.14.cc0060e
  DV="$D/Dockerfile.vps"
  [ -d "$D" ] || { echo "No existe $D"; exit 1; }
  O="$D/y2a-$(date +%Y%m%d-%H%M%S).txt"
  [ ! -e "$O" ] || { echo "Ya existe $O: vuelve a lanzarla dentro de un segundo"; exit 1; }
  {
  echo "== Y2a (carpeta del laboratorio $L; no construye ni arranca): $(date '+%F %T')"
  echo "== 1. Comprobaciones previas"
  chk "no existe $L" "$(test -e "$L" && echo existe || echo no)" no
  chk "Dockerfile.14.cc0060e del repo (huella)" "$(sha256sum "$CC" 2>/dev/null | cut -d' ' -f1)" 8800092a909f73bdecac1e9b1c1379fdb36c3cd65da55f286775732daf50e69a
  chk "bloque del core cc0060e, líneas 67-106 (huella)" "$(sed -n 67,106p "$CC" 2>/dev/null | sha256sum | cut -d' ' -f1)" 2db59ad7e98899546dcbf2244b13e9dd2ff74b864aa2afb9be979ec76a363648
  chk "existe la copia del Dockerfile del VPS (Y0)" "$(test -s "$DV" && echo si || echo no)" si
  [ "$F" = 0 ] || { echo "== Y2a: $F FALLO(S). No se ha creado nada."; exit 1; }
  echo "Dockerfile.vps: $(wc -l < "$DV" | tr -d ' ') líneas, SHA-256 $(sha256sum "$DV" | cut -d' ' -f1)"

  echo "== 2. [ALTERA: crea $L] carpeta, repo git local (sin remoto), CLAUDE.md, .odoo-dev.conf e infra/Dockerfile.14"
  mkdir -p "$L/infra" || exit 1
  git -C "$L" init -q
  printf '# Laboratorio LIYBEN 3973 (ensayo del -u de pns_* sobre una copia de LIYBEN)\n\nVersión de Odoo: 14.0\n' > "$L/CLAUDE.md"
  printf 'COMPARTIDOS="third_party vertical-instaladores LIYBEN"\nDOCKERFILE="infra/Dockerfile.14"\n' > "$L/.odoo-dev.conf"
  { cat "$DV"; printf '\n'; sed -n 67,106p "$CC"; } > "$L/infra/Dockerfile.14"
  chmod 755 "$L" "$L/infra"
  chmod 644 "$L/CLAUDE.md" "$L/.odoo-dev.conf" "$L/infra/Dockerfile.14"

  echo "== 3. Comprobación"
  chk "permisos (carpeta, infra, CLAUDE.md, .odoo-dev.conf, Dockerfile)" "$(stat -c %a "$L" "$L/infra" "$L/CLAUDE.md" "$L/.odoo-dev.conf" "$L/infra/Dockerfile.14" | tr '\n' ' ' | sed 's/ $//')" "755 755 644 644 644"
  chk "repo git sin remoto" "$(git -C "$L" remote | wc -l | tr -d ' ')" 0
  chk "el Dockerfile empieza por el del VPS, entero" "$(head -n "$(wc -l < "$DV")" "$L/infra/Dockerfile.14" | cmp -s - "$DV" && echo si || echo no)" si
  chk "y termina con el bloque del core cc0060e" "$(tail -n 40 "$L/infra/Dockerfile.14" | sha256sum | cut -d' ' -f1)" 2db59ad7e98899546dcbf2244b13e9dd2ff74b864aa2afb9be979ec76a363648
  chk "líneas del Dockerfile (VPS + 1 en blanco + 40)" "$(wc -l < "$L/infra/Dockerfile.14" | tr -d ' ')" "$(( $(wc -l < "$DV") + 41 ))"
  echo "-- .odoo-dev.conf"; sed 's/^/   /' "$L/.odoo-dev.conf"
  echo "-- huellas"
  ( cd "$L" && sha256sum CLAUDE.md .odoo-dev.conf infra/Dockerfile.14 | sed 's/^/   /' )
  if [ "$F" = 0 ]; then echo "== Y2a: TODO OK. Corte: pega la salida antes de construir (Y2b)."; else echo "== Y2a: $F FALLO(S). No sigas: pega la salida."; fi
  } 2>&1 | tee "$O"
  echo "Guardado en $O"
)
ly_y2a
