d50_vaciar() (
  set -u
  case "${1:-ensayo}" in
    ensayo) MODO=ensayo; FIN=ROLLBACK; QUEDAN=8 ;;
    VACIAR) MODO=VACIAR; FIN=COMMIT; QUEDAN=0 ;;
    *) echo "Uso: d50_vaciar [ensayo|VACIAR] (sin argumento: ensayo, que termina en ROLLBACK)"; exit 1 ;;
  esac
  F=0
  chk() { if [ "$2" = "$3" ]; then echo "OK      $1"; else echo "FALLO   $1 (obtenido «$2», esperado «$3»)"; F=$((F+1)); fi; }
  echo "== D50 ($MODO): vaciar los tokens de registro de LIYBEN ($(date -u +%H:%M:%S) UTC); termina en $FIN"
  echo "== 1. Comprobaciones previas"
  chk "odoo14_db en marcha" "$(docker ps --format '{{.Names}}' | grep -cx odoo14_db)" 1
  [ "$F" = 0 ] || { echo "== D50 ($MODO): FALLO ($F). No se ha tocado nada."; exit 1; }
  echo "== 2. Transacción: compuerta, UPDATE y comprobación; después $FIN"
  R=$(docker exec -i -e D50_FIN="$FIN" odoo14_db \
        sh -c 'psql -U "$POSTGRES_USER" -d LIYBEN -At -v ON_ERROR_STOP=1 -v fin="$D50_FIN"' 2>&1 <<'SQL'
BEGIN;
DO $$
DECLARE
  esperado CONSTANT text := 'externo_archivado|reset|sin_caducidad|activo|1;'
                         || 'externo_archivado|signup|sin_caducidad|activo|2;'
                         || 'interno_activo|reset|caducado|activo|1;'
                         || 'portal_archivado|signup|sin_caducidad|activo|3;'
                         || 'sin_usuario|reset|sin_caducidad|activo|1';
  n int; perfil text; ni int; rc int; queda int;
BEGIN
  SELECT count(*) INTO n FROM res_partner WHERE signup_token IS NOT NULL;
  WITH portal AS (
    SELECT res_id AS gid FROM ir_model_data
     WHERE module = 'base' AND name = 'group_portal' AND model = 'res.groups'
  ), u AS (
    SELECT ru.partner_id,
           bool_or(NOT ru.share AND ru.active) AS int_act,
           bool_or(NOT ru.share) AS int_any,
           bool_or(ru.share AND ru.active) AS ext_act,
           bool_or(ru.share AND rel.uid IS NOT NULL) AS portal
      FROM res_users ru
      LEFT JOIN res_groups_users_rel rel ON rel.uid = ru.id AND rel.gid IN (SELECT gid FROM portal)
     GROUP BY ru.partner_id
  ), f AS (
    SELECT CASE WHEN u.partner_id IS NULL THEN 'sin_usuario'
                WHEN u.int_act THEN 'interno_activo'
                WHEN u.int_any THEN 'interno_archivado'
                WHEN u.ext_act THEN 'externo_activo'
                WHEN u.portal THEN 'portal_archivado'
                ELSE 'externo_archivado' END AS cat,
           coalesce(p.signup_type, '(vacío)') AS tipo,
           CASE WHEN p.signup_expiration IS NULL THEN 'sin_caducidad'
                WHEN p.signup_expiration < (now() AT TIME ZONE 'UTC') THEN 'caducado'
                ELSE 'vigente' END AS cad,
           CASE WHEN p.active THEN 'activo' ELSE 'archivado' END AS con
      FROM res_partner p
      LEFT JOIN u ON u.partner_id = p.id
     WHERE p.signup_token IS NOT NULL
  )
  SELECT string_agg(l, ';' ORDER BY l COLLATE "C") INTO perfil
    FROM (SELECT cat || '|' || tipo || '|' || cad || '|' || con || '|' || count(*) AS l
            FROM f GROUP BY cat, tipo, cad, con) g;
  SELECT count(*) INTO ni FROM res_partner p
   WHERE p.signup_token IS NOT NULL
     AND (p.signup_expiration IS NULL OR p.signup_expiration >= (now() AT TIME ZONE 'UTC'))
     AND EXISTS (SELECT 1 FROM res_users ru WHERE ru.partner_id = p.id AND NOT ru.share);
  RAISE NOTICE 'D50 antes: % tokens; perfil %', n, coalesce(perfil, '(ninguno)');
  RAISE NOTICE 'D50 tokens vigentes o sin caducidad de usuarios internos: %', ni;
  IF ni <> 0 THEN
    RAISE EXCEPTION 'D50 COMPUERTA: % token(s) vigente(s) de usuarios internos (cambio de contraseña en curso)', ni;
  END IF;
  IF n <> 8 OR perfil IS DISTINCT FROM esperado THEN
    RAISE EXCEPTION 'D50 COMPUERTA: el perfil no es el del 19/11/2026 (8 tokens, 5 filas)';
  END IF;
  UPDATE res_partner SET signup_token = NULL, signup_type = NULL, signup_expiration = NULL
   WHERE signup_token IS NOT NULL;
  GET DIAGNOSTICS rc = ROW_COUNT;
  SELECT count(*) INTO queda FROM res_partner
   WHERE signup_token IS NOT NULL OR signup_type IS NOT NULL OR signup_expiration IS NOT NULL;
  RAISE NOTICE 'D50 vaciados: % (esperado 8); con token, tipo o caducidad: % (esperado 0)', rc, queda;
  IF rc <> 8 OR queda <> 0 THEN
    RAISE EXCEPTION 'D50 COMPUERTA: el UPDATE no dejó lo esperado';
  END IF;
END $$;
\echo D50 cierre :fin
:fin;
SQL
  ); RC=$?
  printf '%s\n' "$R" | sed 's/^NOTICE:  //'
  chk "psql terminó sin error" "$RC" 0
  chk "compuerta superada" "$(printf '%s\n' "$R" | grep -c 'D50 COMPUERTA')" 0
  chk "vaciados 8 dentro de la transacción" "$(printf '%s\n' "$R" | grep -c '^NOTICE:  D50 vaciados: 8 (esperado 8); con token, tipo o caducidad: 0 ')" 1
  chk "transacción cerrada con $FIN" "$(printf '%s\n' "$R" | grep -cx "$FIN")" 1
  echo "== 3. Después (solo lectura, otra sesión)"
  N=$(docker exec -i -e PGOPTIONS='-c default_transaction_read_only=on' odoo14_db \
        sh -c 'psql -U "$POSTGRES_USER" -d LIYBEN -At -v ON_ERROR_STOP=1' 2>&1 <<'SQL'
SELECT count(*) FROM res_partner WHERE signup_token IS NOT NULL;
SQL
  )
  chk "tokens en LIYBEN tras $FIN" "$N" "$QUEDAN"
  if [ "$F" = 0 ]; then
    echo "== D50 ($MODO): TODO OK$( [ "$MODO" = ensayo ] && echo ' (ensayo: LIYBEN sin cambios)')"
  else
    echo "== D50 ($MODO): FALLO ($F). Si psql no terminó, la transacción no se confirmó: pega la salida."
  fi
)
