#!/usr/bin/env bash
# Pruebas con toda la rama: comprobación de P-2 (parche 35, NUEVO-2), P-11 y
# P-14 tras el -u a la rama. SOLO LECTURA: lee el log del -u y consulta la BD con
# psql en una transacción de solo lectura (PGOPTIONS default_transaction_read_only,
# como lab_cdp.py). No arranca Odoo ni escribe nada.
#
# Casos (plan, «Parche 35: código y tests hechos»; D38):
#   a  -u desde 3.1.879 con el 35: en el log, una «module pns_ai_mcp: Running
#      migration [14.0.3.1.973>] post-migrate» y una «Seges patch 35: <xmlid>
#      fixed (gc_expired -> _gc_expired)» por cron; code model._gc_expired().
#   b  -u desde 3.1.879 a la base limpia y después a la rama: ninguna de las
#      líneas en el log del -u a la rama y code model.gc_expired(); con
#      --corregido (tras rama_corregir_p2b.sh), model._gc_expired().
#   c  instalación limpia (lab_pns_ai_3973_14): ninguna línea y
#      model._gc_expired().
# En los tres, ningún WARNING «Seges patch 35:» y versiones de la rama en la BD
# (14.0.1.2.69, 14.0.3.1.973 y 14.0.2.1.587).
#   P-11 (todos los casos): todos los AI Administrators tienen AI Conversational;
#        en a y b, además, seges_p11_admin (plantado por rama_plantar.sh).
#   P-14 (a y b): sin filas de fábrica de las siete skills retiradas (también
#        cash_forecast), sin la fila de caché plantada y con la sesión presente.
#
# Uso: bash rama_comprobar.sh --bd <bd> --caso a|b|c [--corregido] --log <log del -u>
#      El log es el actualizar-*.log que indica la línea «==> actualizar en <bd>
#      (log: …)» del -u a la rama. Necesita el contenedor db en marcha (lo
#      levanta «odoo-dev 14 bd-lista», de solo lectura).
# Códigos: 0 todo OK; 1 algún FALLO; 11 db parado o docker no responde;
# 12 argumentos no válidos (o el log no existe); 15 la BD no existe.
set -uo pipefail

BD= CASO= LOG= CORREGIDO=0
while [ $# -gt 0 ]; do
    case "$1" in
        --bd|--caso|--log)
            [ $# -ge 2 ] || { echo "Falta el valor de $1."; exit 12; }
            case "$1" in --bd) BD=$2 ;; --caso) CASO=$2 ;; --log) LOG=$2 ;; esac
            shift 2 ;;
        --corregido) CORREGIDO=1; shift ;;
        *) echo "Argumento no válido: $1"; exit 12 ;;
    esac
done
[[ "$BD" =~ ^[a-z0-9_]+$ ]] && [[ "$CASO" =~ ^[abc]$ ]] && [ -n "$LOG" ] || {
    echo "Uso: rama_comprobar.sh --bd <bd> --caso a|b|c [--corregido] --log <actualizar-*.log>"; exit 12; }
[ "$CORREGIDO" = 0 ] || [ "$CASO" = b ] || { echo "--corregido solo vale con --caso b."; exit 12; }
[ -f "$LOG" ] && [ -r "$LOG" ] || { echo "No existe o no se puede leer el log: $LOG"; exit 12; }
case "$(basename "$LOG")" in
    actualizar-*.log) ;;
    *) echo "El log no es un actualizar-*.log de odoo-dev: $LOG"; exit 12 ;;
esac
NOMBRES=$(docker ps --format '{{.Names}}' 2>/dev/null) || { echo "«docker ps» no responde."; exit 11; }
printf '%s\n' "$NOMBRES" | grep -qx 'odoo-dev-14-db-1' || {
    echo "El contenedor odoo-dev-14-db-1 no está en marcha: «odoo-dev 14 bd-lista» (solo lectura) lo levanta."; exit 11; }

PSQL=(docker exec -i -e 'PGOPTIONS=-c default_transaction_read_only=on' odoo-dev-14-db-1
      psql -X -q -U odoo -d "$BD" -v ON_ERROR_STOP=1 -At -F '|')
q() { "${PSQL[@]}" -c "$1" 2>/dev/null; }
q 'SELECT 1' >/dev/null || { echo "La BD $BD no existe (o psql no responde)."; exit 15; }

FALLOS=0
punto() {  # punto <ok 0/1> <texto>
    if [ "$1" = 1 ]; then echo "OK     $2"; else echo "FALLO  $2"; FALLOS=$((FALLOS + 1)); fi
}
igual() { [ "$1" = "$2" ] && echo 1 || echo 0; }

CRON_FETCH=pns_ai_mcp.ir_cron_ai_fetch_cache_gc
CRON_API=pns_ai_mcp.ir_cron_ai_api_result_cache_gc
if [ "$CASO" = a ] || { [ "$CASO" = b ] && [ "$CORREGIDO" = 1 ]; } || [ "$CASO" = c ]; then
    CODE_PREVISTO='model._gc_expired()'
else
    CODE_PREVISTO='model.gc_expired()'
fi
echo "== P-2 ($CASO$([ "$CORREGIDO" = 1 ] && echo ', tras la corrección a mano')) en $BD · log $(basename "$LOG")"

# -- El log del -u (solo recuentos; no se imprime ninguna línea) -------------
LINEAS_BD=$(grep -cE "^[0-9-]+ [0-9:,]+ [0-9]+ [A-Z]+ $BD " "$LOG")
OTRAS_BD=$(grep -E '^[0-9-]+ [0-9:,]+ [0-9]+ [A-Z]+ ' "$LOG" | awk -v bd="$BD" '$5 != bd && $5 != "?"' | wc -l)
punto "$( [ "$LINEAS_BD" -gt 0 ] && [ "$OTRAS_BD" = 0 ] && echo 1 || echo 0)" \
    "log del -u de $BD: $LINEAS_BD líneas de $BD, $OTRAS_BD de otras BD"
MIGRA=$(grep -cF 'module pns_ai_mcp: Running migration [14.0.3.1.973>] post-migrate' "$LOG")
FIX_FETCH=$(grep -cF "Seges patch 35: $CRON_FETCH fixed (gc_expired -> _gc_expired)" "$LOG")
FIX_API=$(grep -cF "Seges patch 35: $CRON_API fixed (gc_expired -> _gc_expired)" "$LOG")
FIX_TOTAL=$(grep -cF 'Seges patch 35: ' "$LOG")
AVISOS=$(grep -cE ' WARNING [^ ]+ [^ ]+: Seges patch 35: ' "$LOG")
if [ "$CASO" = a ]; then
    punto "$(igual "$MIGRA" 1)" "«Running migration [14.0.3.1.973>] post-migrate» de pns_ai_mcp: $MIGRA (previsto 1)"
    punto "$( [ "$FIX_FETCH" = 1 ] && [ "$FIX_API" = 1 ] && echo 1 || echo 0)" \
        "«Seges patch 35: … fixed»: fetch_cache $FIX_FETCH, api_result_cache $FIX_API (previsto 1 y 1)"
else
    punto "$(igual "$MIGRA" 0)" "«Running migration [14.0.3.1.973>] post-migrate» de pns_ai_mcp: $MIGRA (previsto 0)"
    punto "$(igual "$FIX_TOTAL" 0)" "líneas «Seges patch 35: …»: $FIX_TOTAL (previsto 0)"
fi
punto "$(igual "$AVISOS" 0)" "WARNING «Seges patch 35: …» (not found / unexpected code): $AVISOS (previsto 0)"

# -- La BD (solo lectura) --------------------------------------------------
VERS=$(q "SELECT string_agg(name || '=' || coalesce(latest_version, '') || '/' || state, ' ' ORDER BY name)
          FROM ir_module_module WHERE name IN ('pns_base', 'pns_ai_mcp', 'pns_ai_chatboo');")
punto "$(igual "$VERS" 'pns_ai_chatboo=14.0.2.1.587/installed pns_ai_mcp=14.0.3.1.973/installed pns_base=14.0.1.2.69/installed')" \
    "versiones en la BD: ${VERS:-sin datos}"
CODES=$(q "SELECT d.name || '=' || btrim(coalesce(s.code, ''))
             FROM ir_model_data d
             JOIN ir_cron c ON c.id = d.res_id
             JOIN ir_act_server s ON s.id = c.ir_actions_server_id
            WHERE d.module = 'pns_ai_mcp' AND d.model = 'ir.cron'
              AND d.name IN ('ir_cron_ai_fetch_cache_gc', 'ir_cron_ai_api_result_cache_gc')
            ORDER BY d.name;")
PREVISTO_CODES=$(printf 'ir_cron_ai_api_result_cache_gc=%s\nir_cron_ai_fetch_cache_gc=%s' "$CODE_PREVISTO" "$CODE_PREVISTO")
punto "$(igual "$CODES" "$PREVISTO_CODES")" "ir_cron.code (previsto $CODE_PREVISTO en los dos): $(echo "$CODES" | paste -sd' ' -)"

GRUPOS="WITH g AS (SELECT
    (SELECT res_id FROM ir_model_data WHERE module = 'pns_ai_mcp' AND name = 'group_ai_admin' AND model = 'res.groups') AS adm,
    (SELECT res_id FROM ir_model_data WHERE module = 'pns_ai_mcp' AND name = 'group_ai_conversational' AND model = 'res.groups') AS conv)"
P11=$(q "$GRUPOS
         SELECT count(*), count(*) FILTER (WHERE NOT EXISTS (
                SELECT 1 FROM res_groups_users_rel r2 WHERE r2.uid = r.uid AND r2.gid = g.conv))
           FROM res_groups_users_rel r, g WHERE r.gid = g.adm;")
P11_ADM=${P11%%|*}
P11_SIN=${P11##*|}
punto "$( [ -n "$P11" ] && [ "$P11_ADM" -gt 0 ] && [ "$P11_SIN" = 0 ] && echo 1 || echo 0)" \
    "P-11: AI Administrators $P11_ADM, sin AI Conversational $P11_SIN (previsto 0)"
P11_PLANTADO=$(q "$GRUPOS
                  SELECT count(*), coalesce(bool_and(EXISTS (
                         SELECT 1 FROM res_groups_users_rel r WHERE r.uid = u.id AND r.gid = g.conv)), false)
                    FROM res_users u, g WHERE u.login = 'seges_p11_admin';")
if [ "$CASO" = c ]; then
    echo "INFO   P-11: seges_p11_admin en la BD: ${P11_PLANTADO%%|*} (no se planta en c)"
else
    punto "$(igual "$P11_PLANTADO" '1|t')" "P-11: seges_p11_admin presente y con AI Conversational (${P11_PLANTADO:-sin datos})"
fi

if [ "$CASO" = c ]; then
    echo "INFO   P-14: no aplica en c (no hay nada plantado)"
else
    RETIRADAS=$(q "SELECT count(*) FROM ai_skill WHERE source_module = 'pns_ai_chatboo' AND owner_id IS NULL
                     AND code IN ('annual_billing', 'cash_forecast', 'credit_facility', 'customer_risk_analysis',
                                  'sys_info', 'users_all', 'users_logged');")
    punto "$(igual "$RETIRADAS" 0)" "P-14: filas de fábrica de las siete skills retiradas: ${RETIRADAS:-sin datos} (previsto 0)"
    CACHE=$(q "SELECT count(*) FROM ai_skill_param_cache WHERE unresolved = 'seges p14 ocho semanas';")
    punto "$(igual "$CACHE" 0)" "P-14: fila de caché plantada de cash_forecast: ${CACHE:-sin datos} (previsto 0, borrada en cascada)"
    SESION=$(q "SELECT count(*), coalesce(bool_and(active_skill_code = 'cash_forecast'), false)
                  FROM chatboo_session WHERE name = 'Seges P-14 cash_forecast activa';")
    punto "$( [ "${SESION%%|*}" = 1 ] && echo 1 || echo 0)" "P-14: sesión plantada presente: ${SESION%%|*} (previsto 1)"
    echo "INFO   P-14: la sesión conserva active_skill_code = cash_forecast: $( [ "${SESION##*|}" = t ] && echo sí || echo no)"
fi

echo
if [ "$FALLOS" = 0 ]; then echo "Resultado: todo OK"; exit 0; fi
echo "Resultado: $FALLOS FALLO"; exit 1
