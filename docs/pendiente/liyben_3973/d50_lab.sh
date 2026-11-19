d50_lab() (
  set -u
  umask 077
  LAB=~/GitHub/lab_pns_ai_cc0060e
  BD=lab_pns_ai_cc0060e_14
  ESTADO=~/odoo-dev/14.0/estado
  D="$HOME/pns_ai_3973/liyben"
  mkdir -p -m 700 "$D" || exit 1
  O="$D/d50lab-$(date +%Y%m%d-%H%M%S).txt"
  test ! -e "$O" || { echo "Ya existe $O: espera un segundo y repite"; exit 1; }
  {
  echo "== D50 en el laboratorio: signup_cancel frente al UPDATE de A1 ($BD, sin commit)"
  [ "$(sed -n 's/^REPO=//p' "$ESTADO" 2>/dev/null)" = "$LAB" ] || {
    echo "FALLO   el contexto activo de odoo-dev 14 no es lab_pns_ai_cc0060e: no se hace nada"; exit 1; }
  echo "OK      contexto activo lab_pns_ai_cc0060e"
  SALIDA=$({ printf 'BD = "%s"\n' "$BD"; cat <<'PY'; } | odoo-dev 14 shell --bd "$BD" 2>&1
import odoo

UPDATE_A1 = ("UPDATE res_partner SET signup_token = NULL, signup_type = NULL, signup_expiration = NULL"
             " WHERE signup_token IS NOT NULL")

if env.cr.dbname != BD:
    print('D50 ERROR: la BD del shell no es ' + BD)
    raise SystemExit(1)


def huella():
    """Recuentos y md5 de las columnas de signup de res_partner, desde otro cursor y en solo lectura."""
    with odoo.registry(BD).cursor() as cr2:
        cr2.execute('SET TRANSACTION READ ONLY')
        cr2.execute("SELECT count(*), count(signup_token), count(signup_type), count(signup_expiration),"
                    " md5(coalesce(string_agg(concat_ws('|', id, signup_token, signup_type, signup_expiration,"
                    " write_date, write_uid), ',' ORDER BY id), '')) FROM res_partner")
        fila = tuple(cr2.fetchone())
        cr2.rollback()
    return fila


def cols(p):
    env.cr.execute('SELECT signup_token IS NOT NULL, signup_type, signup_expiration FROM res_partner WHERE id = %s',
                   (p.id,))
    return tuple(env.cr.fetchone())


antes = huella()
print('D50 antes: contactos %d, con token %d, con tipo %d, con caducidad %d, huella %s' % (antes[:4] + (antes[4][:12],)))
P = env['res.partner'].search([('active', '=', True), ('user_ids', '=', False)], order='id', limit=2)
if len(P) != 2 or any(cols(p) != (False, None, None) for p in P):
    print('D50 ERROR: no hay dos contactos activos sin usuario y sin datos de signup')
    raise SystemExit(1)
a, b = P[0], P[1]
P.signup_prepare()
env['res.partner'].flush()
env.cr.execute('SELECT count(DISTINCT signup_token), array_agg(DISTINCT signup_type) FROM res_partner WHERE id IN %s',
               (tuple(P.ids),))
n_tok, tipos = env.cr.fetchone()
plantados = n_tok == 2 and tipos == ['signup']
print('D50 plantados con signup_prepare: %d tokens distintos, tipo %s (%s)' % (n_tok, tipos, 'OK' if plantados else 'FALLO'))
a.signup_cancel()
env['res.partner'].flush()
env.cr.execute(UPDATE_A1 + ' AND id = %s', (b.id,))
filas = env.cr.rowcount
P.invalidate_cache()
ca, cb = cols(a), cols(b)
print('D50 columnas (token?, tipo, caducidad): signup_cancel %s; UPDATE de A1 %s (filas %d)' % (ca, cb, filas))
orm = [(bool(p.sudo().signup_token), p.signup_valid, bool(p.signup_url)) for p in (a, b)]
print('D50 ORM (token?, signup_valid, signup_url?): signup_cancel %s; UPDATE de A1 %s' % (orm[0], orm[1]))
iguales = filas == 1 and ca == cb == (False, None, None) and orm[0] == orm[1] == (False, False, False)
env.cr.rollback()
despues = huella()
igual = despues == antes
print('D50 después del rollback: huella %s (%s)' % (despues[4][:12], 'igual' if igual else 'CAMBIÓ'))
print('D50 VEREDICTO ' + ('OK' if plantados and iguales and igual else 'FALLO'))
PY
)
  printf '%s\n' "$SALIDA" | grep '^D50 ' || echo "Sin líneas «D50»: el shell no ejecutó el script."
  if printf '%s\n' "$SALIDA" | grep -qx 'D50 VEREDICTO OK'; then
    echo "== D50 lab: TODO OK (signup_cancel = UPDATE de A1 en cc0060e; nada escrito: el shell se deshace)"
  else
    printf '%s\n' "$SALIDA" | grep -q '^D50 VEREDICTO ' || echo "El shell no terminó. Errores, solo el tipo: $(printf '%s\n' "$SALIDA" | grep -oE '^[A-Za-z_.]+(Error|Exception)' | sort -u | paste -sd, -)"
    echo "== D50 lab: FALLO (pega la salida)"
  fi
  } 2>&1 | tee "$O"
  echo "Guardado en $O"
)
