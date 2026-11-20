ly_y0b() (
  set -u
  [ -n "${VPS_PORT:-}" ] && [ -n "${VPS_DEST:-}" ] || { echo "Faltan VPS_PORT y VPS_DEST"; exit 1; }
  echo "== Y0b (solo lectura en el VPS y en el equipo): $(date '+%F %T')"
  echo "== 1. VPS: dos OCA que divergen y los dos repos propios"
  ssh -T -p "$VPS_PORT" "$VPS_DEST" 'bash -s' 2>&1 <<'REMOTO'
for h in /opt/odoo/addons/OCA/server-tools /opt/odoo/addons/OCA/l10n-spain /opt/odoo/addons/custom/LIYBEN /opt/odoo/addons/custom/vertical-instaladores; do
  g() { git --no-optional-locks -c safe.directory="$h" -C "$h" "$@"; }
  echo "-- $h"
  echo "   superficial: $(g rev-parse --is-shallow-repository) · commits en HEAD: $(g rev-list --count HEAD 2>/dev/null) · remoto: $(g remote get-url origin 2>/dev/null | sed -E 's#://[^@/]*@#://#')"
  echo "   seguimiento: $(g status -sb 2>/dev/null | head -1)"
  g log --format='   %h %ci %s' -3 | cut -c1-120
  case "$h" in */custom/*)
    echo "   sin commit (estado y ruta):"
    g status --porcelain | cut -c1-110 | sed 's/^/     /'
    echo "   tamaño del cambio: $(g diff --shortstat 2>/dev/null)"
  esac
done
REMOTO
  echo "== 2. Equipo: los mismos commits"
  for r in server-tools l10n-spain; do
    l=~/odoo-dev/14.0/oca/$r
    echo "-- $l"
    echo "   superficial: $(git -C "$l" rev-parse --is-shallow-repository) · commits en HEAD: $(git -C "$l" rev-list --count HEAD) · seguimiento: $(git -C "$l" status -sb | head -1)"
    git -C "$l" log --format='   %h %ci %s' -1 | cut -c1-120
  done
  for l in ~/GitHub/LIYBEN ~/odoo-dev/14.0/vertical-instaladores ~/GitHub/vertical-instaladores; do
    echo "-- $l"
    if git -C "$l" rev-parse --git-dir >/dev/null 2>&1; then
      echo "   rama: $(git -C "$l" rev-parse --abbrev-ref HEAD) · cambios sin commit: $(git -C "$l" status --porcelain | wc -l)"
      git -C "$l" log --format='   %h %ci %s' -1 | cut -c1-120
    else echo "   no existe o no es un repo"; fi
  done
)
ly_y0b
