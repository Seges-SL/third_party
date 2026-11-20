ly_y6() (
  set -u
  umask 077
  F=0
  chk() {
    if [ "$2" = "$3" ]; then echo "OK      $1"
    elif [ "${4:-}" = info ]; then echo "INFO    $1: esperado [$3], obtenido [$2] (no bloquea)"
    else echo "FALLO   $1: esperado [$3], obtenido [$2]"; F=$((F + 1)); fi
  }
  una() { tr '\n' ' ' | sed 's/ *$//'; }
  sec() { printf '%s\n' "$1" | awk -v s="## $2" '/^## /{p = ($0 == s); next} p'; }
  corte() { [ "$F" = 0 ] || { echo "== Y6 v3: $F FALLO(S) en «$1». No se ha seguido: pega la salida."; exit 1; }; }
  MODO=${1:-comprobar}
  case "$MODO" in
    comprobar) OP=- ;;
    APLICAR_B) OP=B ;;
    APLICAR_BP) OP=BP ;;
    APLICAR_C) OP=C ;;
    *) echo "Uso: ly_y6 [comprobar|APLICAR_B|APLICAR_BP|APLICAR_C] (sin argumento: comprobar, que termina en rollback)"; exit 1 ;;
  esac
  web() { docker ps --format '{{.Names}}' | grep -cE '^odoo-dev-14-web' || true; }
  pg() { docker exec -i -e PGOPTIONS='-c default_transaction_read_only=on' odoo-dev-14-db-1 psql -U odoo -d "$1" -X -q -At -F '|' 2>&1; }
  L=~/GitHub/lab_liyben_3973
  D=~/pns_ai_3973/liyben
  BD=liyben_ens_14
  NT=45966
  NF=41467
  MK3='== Y3: TODO OK. Corte: pega la salida (y la paridad) antes de Y4.'
  MK5='== Y5: TODO OK. Corte: pega la salida antes de Y6.'
  MKC='== Y6 v3: TODO OK (comprobar: rollback, nada escrito). Corte: pega la salida y elige B, B′ o C.'
  M=$(date +%Y%m%d-%H%M%S)
  O="$D/y6-$MODO-$M.txt"
  SL="$D/y6-shell-$MODO-$M.log"
  FA="$D/y6_foto_antes-$MODO-$M.txt"
  FD="$D/y6_foto_despues-$MODO-$M.txt"
  [ -d "$D" ] || { echo "No existe $D"; exit 1; }
  { [ ! -e "$O" ] && [ ! -e "$SL" ]; } || { echo "Ya existe $O o $SL: vuelve a lanzarla dentro de un segundo"; exit 1; }
  estado_sql() { pg "$BD" <<'SQL'
\echo '## rol Diseño'
SELECT d.module || '.' || d.name, r.code, r.active, r.use_fallback, coalesce(fb.code, '')
  FROM ai_provider_role r
  LEFT JOIN ir_model_data d ON d.model = 'ai.provider.role' AND d.res_id = r.id
  LEFT JOIN ai_provider_role fb ON fb.id = r.fallback_id
 WHERE r.code = 'design';
\echo '## con Diseño'
SELECT p.id, p.active, r.use_fallback
  FROM ai_provider_role r
  JOIN ai_provider_role_rel rr ON rr.role_id = r.id
  JOIN ai_provider p ON p.id = rr.provider_id
 WHERE r.code = 'design' ORDER BY p.id;
\echo '## con Decisión'
SELECT p.id, p.active, p.protocol
  FROM ai_provider_role r
  JOIN ai_provider_role_rel rr ON rr.role_id = r.id
  JOIN ai_provider p ON p.id = rr.provider_id
 WHERE r.code = 'decision' ORDER BY p.id;
\echo '## roles por proveedor'
SELECT p.id, p.active, p.model_name, coalesce(string_agg(r.code, ',' ORDER BY r.sequence, r.id), '')
  FROM ai_provider p
  LEFT JOIN ai_provider_role_rel rr ON rr.provider_id = p.id
  LEFT JOIN ai_provider_role r ON r.id = rr.role_id
 GROUP BY p.id, p.active, p.model_name ORDER BY p.id;
\echo '## roles'
SELECT code, active, use_fallback FROM ai_provider_role ORDER BY sequence, id;
\echo '## es_ES'
SELECT code, active FROM res_lang WHERE code = 'es_ES';
\echo '## traducciones'
SELECT count(*), md5(coalesce(string_agg(id || ':' || md5(coalesce(value, '')), ',' ORDER BY id), ''))
  FROM ir_translation WHERE lang = 'es_ES';
\echo '## traducciones fuera de pns'
SELECT count(*), md5(coalesce(string_agg(id || ':' || md5(coalesce(value, '')), ',' ORDER BY id), ''))
  FROM ir_translation WHERE lang = 'es_ES' AND coalesce(module, '') NOT LIKE 'pns\_%';
\echo '## traducciones pns'
SELECT module, count(*) FROM ir_translation WHERE lang = 'es_ES' AND module LIKE 'pns\_%' GROUP BY 1 ORDER BY 1;
\echo '## fin'
SQL
  }
  # foto por id, sin textos: id|tipo|módulo|md5(name)|state|md5(comments)|md5(value)
  foto_sql() { pg "$BD" <<'SQL'
SELECT id, coalesce(type, ''), coalesce(module, ''), md5(coalesce(name, '')), coalesce(state, ''), md5(coalesce(comments, '')), md5(coalesce(value, ''))
  FROM ir_translation WHERE lang = 'es_ES' ORDER BY id;
SQL
  }
  # la misma medida que el shell, desde las dos fotos (cada fila, por su módulo y tipo de antes; las nuevas, por los de después)
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
  echo "== Y6 v3 ($MODO): medida de la recarga de es_ES de los tres pns_* por el módulo de antes (B, B′ y C) y rol Diseño en el proveedor 1 sin alternativa, quitándole Decisión (D67), sobre $BD con el web parado. $M"
  echo "== 1. Comprobaciones previas (solo lectura)"
  chk "web del kit parado" "$(web)" 0
  E=$(cd "$L" && odoo-dev 14 estado 2>&1)
  chk "contexto activo (BD|repo)" "$(printf '%s\n' "$E" | sed -n 's/^ *BD=//p' | head -1)|$(printf '%s\n' "$E" | sed -n 's/^ *REPO=//p' | head -1)" "lab_liyben_3973_14|$L"
  chk "PostgreSQL del kit en marcha" "$(docker ps --format '{{.Names}}' | grep -cx odoo-dev-14-db-1 || true)" 1
  [ "$F" = 0 ] || echo "   (si el único FALLO es PostgreSQL: lanza «cd $L && odoo-dev 14 bd-lista», que no levanta el web, y repite Y6)"
  corte "comprobaciones previas"
  N=$(cd "$L" && odoo-dev 14 estado --bd "$BD" 2>&1 | grep -i 'neutraliz' | head -1)
  chk "$BD neutralizada por el kit" "$(printf '%s' "$N" | grep -qi 'NO neutralizada' && echo no || (printf '%s' "$N" | grep -qi 'neutralizada' && echo si || echo no))" si
  L3=$(ls -t "$D"/y3-CARGAR-*.txt 2>/dev/null | head -1); L3=${L3:-/dev/null}
  chk "última Y3 CARGAR ($(basename "$L3")) con TODO OK: la carga a la que se refiere todo lo demás" "$(grep -cx -- "$MK3" "$L3" 2>/dev/null || true)" 1
  Y=$(ls -t "$D"/y5-ACTUALIZAR-*.txt 2>/dev/null | head -1); Y=${Y:-/dev/null}
  chk "último Y5 ACTUALIZAR ($(basename "$Y")) con TODO OK y posterior a esa carga" "$(grep -cx -- "$MK5" "$Y" 2>/dev/null || true)|$( [ "$Y" -nt "$L3" ] && echo posterior || echo anterior)" "1|posterior"
  chk "ningún Y6 APLICAR con commit posterior a esa carga" "$(find "$D" -maxdepth 1 -name 'y6-shell-APLICAR*.log' -newer "$L3" -exec grep -lx 'Y6 COMMIT OK' {} + 2>/dev/null | grep -c . || true)" 0
  echo "INFO    Y6 APLICAR con commit anteriores a esa carga (de la copia borrada; se ignoran): $(find "$D" -maxdepth 1 -name 'y6-shell-APLICAR*.log' ! -newer "$L3" -exec grep -lx 'Y6 COMMIT OK' {} + 2>/dev/null | grep -c . || true)"
  if [ "$OP" != - ]; then
    C=$(ls -t "$D"/y6-comprobar-*.txt 2>/dev/null | head -1); C=${C:-/dev/null}
    chk "último Y6 comprobar ($(basename "$C")) de la v3 con TODO OK y posterior al Y5" "$(grep -cx -- "$MKC" "$C" 2>/dev/null || true)|$( [ "$C" -nt "$Y" ] && echo posterior || echo anterior)" "1|posterior"
  fi
  chk "versiones en $BD (las de la rama, tras Y5)" "$(pg "$BD" <<< "SELECT string_agg(name || '|' || latest_version, ' ' ORDER BY name) FROM ir_module_module WHERE name IN ('pns_base','pns_ai_mcp','pns_ai_chatboo') AND state = 'installed';")" "pns_ai_chatboo|14.0.2.1.587 pns_ai_mcp|14.0.3.1.973 pns_base|14.0.1.2.69"
  corte "compuertas"
  RA=$(estado_sql)
  printf '%s\n' "$RA" > "$D/y6_antes-$MODO-$M.txt"
  chk "consultas sin error (antes)" "$(printf '%s\n' "$RA" | grep -ciE 'ERROR:|psql: error' || true)" 0
  chk "marcador final (antes)" "$(printf '%s\n' "$RA" | grep -cx '## fin' || true)" 1
  chk "rol Diseño, antes (xml_id|code|activo|use_fallback|alternativa)" "$(sec "$RA" 'rol Diseño' | una)" "pns_ai_mcp.ai_provider_role_design|design|t|t|conversation"
  chk "proveedores con el rol Diseño, antes (nadie: 3.1.782 no tenía fit_design)" "$(sec "$RA" 'con Diseño' | una)" ""
  chk "proveedores con el rol Decisión, antes (id|activo|protocolo): el 1, que su protocolo no admite" "$(sec "$RA" 'con Decisión' | una)" "1|f|openai"
  chk "roles por proveedor, antes (id|activo|modelo|roles), de las fit_* de I0" "$(sec "$RA" 'roles por proveedor' | una)" "1|f|models/gemini-3.5-flash|conversation,vision,decision 2|t|Qwen3.5-9B|conversation,vision"
  chk "es_ES activo" "$(sec "$RA" es_ES)" "es_ES|t"
  chk "traducciones es_ES antes (las de la primera pasada)" "$(sec "$RA" traducciones | cut -d'|' -f1)" "$NT"
  chk "traducciones es_ES fuera de los pns_* antes (las de la primera pasada)" "$(sec "$RA" 'traducciones fuera de pns' | cut -d'|' -f1)" "$NF"
  echo "INFO    traducciones es_ES antes (n|huella): $(sec "$RA" traducciones); fuera de pns_*: $(sec "$RA" 'traducciones fuera de pns'); de los pns_*: $(sec "$RA" 'traducciones pns' | una)"
  foto_sql > "$FA"
  chk "foto de antes (filas sin error = traducciones es_ES)" "$(grep -cvE 'ERROR:|psql: error' "$FA" || true)|$(grep -cE 'ERROR:|psql: error' "$FA" || true)" "$NT|0"
  corte "estado antes"

  case "$OP" in
    -) echo "== 2. Ensayo en odoo shell, sin commit: B, B′ y C (rol), cada uno medido y deshecho con rollback. Lanzado a las $(date +%H:%M:%S)" ;;
    B) echo "== 2. [ALTERA $BD] odoo shell: recarga B (solo pns_*, con sobrescritura) y rol Diseño (D67), un solo commit. Lanzado a las $(date +%H:%M:%S)" ;;
    BP) echo "== 2. [ALTERA $BD] odoo shell: recarga B′ (B y restauración por id de las filas de fuera de los pns_*) y rol Diseño (D67), un solo commit. Lanzado a las $(date +%H:%M:%S)" ;;
    C) echo "== 2. [ALTERA $BD] odoo shell: sin recarga (C); solo rol Diseño (D67), un solo commit. Lanzado a las $(date +%H:%M:%S)" ;;
  esac
  ESP=""
  [ "$OP" = B ] || [ "$OP" = BP ] && ESP=$(grep "^   Y6 MEDIDA $OP \|^   Y6 TOTAL $OP " "$C" | sed 's/^   //' | LC_ALL=C sort -u)
  { printf 'BD = "%s"\nOP = "%s"\nESPERADA = """%s"""\n' "$BD" "$OP" "$ESP"; cat <<'PY'; } | ( cd "$L" && odoo-dev 14 shell --bd "$BD" ) > "$SL" 2>&1
PNS = ('pns_base', 'pns_ai_mcp', 'pns_ai_chatboo')
TIPOS = ('code', 'model', 'model_terms', 'otro')


def foto():
    env.cr.execute("SELECT id, coalesce(type, ''), coalesce(module, ''), md5(coalesce(name, '')), coalesce(state, ''), md5(coalesce(comments, '')), md5(coalesce(value, '')) FROM ir_translation WHERE lang = 'es_ES'")
    return {r[0]: tuple(r[1:]) for r in env.cr.fetchall()}


def tipo(t):
    return t if t in TIPOS[:3] else 'otro'


def es_pns(m):
    return m.startswith('pns_')


def medida(etq, a, d):
    fu = {t: [0, 0, 0, 0] for t in TIPOS}
    pn = {t: [0, 0, 0] for t in TIPOS}
    nu = {t: [0, 0] for t in TIPOS}
    for i, r in a.items():
        t = tipo(r[0])
        x = d.get(i)
        if es_pns(r[1]):
            pn[t][2 if x is None else (0 if x == r else 1)] += 1
        else:
            fu[t][3 if x is None else (2 if x[5] != r[5] else (1 if x != r else 0))] += 1
    for i, x in d.items():
        if i not in a:
            nu[tipo(x[0])][0 if es_pns(x[1]) else 1] += 1
    lin = ['Y6 MEDIDA %s fuera %s igual=%d origen=%d texto=%d borradas=%d' % ((etq, t) + tuple(fu[t])) for t in TIPOS]
    lin += ['Y6 MEDIDA %s pns %s igual=%d cambiadas=%d borradas=%d' % ((etq, t) + tuple(pn[t])) for t in TIPOS]
    lin += ['Y6 MEDIDA %s nuevas %s pns=%d fuera=%d' % ((etq, t) + tuple(nu[t])) for t in TIPOS]
    lin.append('Y6 TOTAL %s fuera_origen=%d fuera_texto=%d fuera_borradas=%d nuevas_fuera=%d pns_cambiadas=%d pns_borradas=%d nuevas_pns=%d' % (
        etq, sum(fu[t][1] for t in TIPOS), sum(fu[t][2] for t in TIPOS), sum(fu[t][3] for t in TIPOS),
        sum(nu[t][1] for t in TIPOS), sum(pn[t][1] for t in TIPOS), sum(pn[t][2] for t in TIPOS), sum(nu[t][0] for t in TIPOS)))
    for l in lin:
        print(l)
    return lin


def deshacer(etq, f0):
    env.cr.rollback()
    env.clear()
    env.registry.clear_caches()
    print('Y6 ROLLBACK %s: igual=%s' % (etq, foto() == f0))


def recarga_b():
    mods = env['ir.module.module'].search([('name', 'in', list(PNS)), ('state', '=', 'installed')])
    if len(mods) != 3:
        raise Exception('Y6: no están los tres pns_* instalados (%d)' % len(mods))
    mods._update_translations('es_ES', True)
    env['base'].flush()


def recarga_bp():
    env['base'].flush()
    env.cr.execute(r"CREATE TEMP TABLE y6_fuera ON COMMIT DROP AS SELECT * FROM ir_translation WHERE lang = 'es_ES' AND coalesce(module, '') NOT LIKE 'pns\_%'")
    env.cr.execute("SELECT count(*) FROM y6_fuera")
    guardadas = env.cr.fetchone()[0]
    recarga_b()
    env.cr.execute("""WITH u AS (
        UPDATE ir_translation t
           SET name = s.name, res_id = s.res_id, src = s.src, type = s.type, value = s.value,
               module = s.module, state = s.state, comments = s.comments
          FROM y6_fuera s
         WHERE t.id = s.id
           AND (t.name, t.res_id, t.src, t.type, t.value, t.module, t.state, t.comments)
               IS DISTINCT FROM (s.name, s.res_id, s.src, s.type, s.value, s.module, s.state, s.comments)
        RETURNING 1) SELECT count(*) FROM u""")
    restauradas = env.cr.fetchone()[0]
    env.cr.execute("""WITH i AS (
        INSERT INTO ir_translation SELECT s.* FROM y6_fuera s
         WHERE NOT EXISTS (SELECT 1 FROM ir_translation t WHERE t.id = s.id)
        RETURNING 1) SELECT count(*) FROM i""")
    reinsertadas = env.cr.fetchone()[0]
    env.cr.execute("DROP TABLE y6_fuera")
    env['ir.translation'].clear_caches()
    env.clear()
    print('Y6 BP guardadas=%d restauradas=%d reinsertadas=%d' % (guardadas, restauradas, reinsertadas))


def titulares(code):
    env.cr.execute("SELECT rr.provider_id FROM ai_provider_role_rel rr JOIN ai_provider_role r ON r.id = rr.role_id WHERE r.code = %s ORDER BY 1", (code,))
    return [r[0] for r in env.cr.fetchall()]


def roles_p1():
    env.cr.execute("SELECT coalesce(string_agg(r.code, ',' ORDER BY r.sequence, r.id), '') FROM ai_provider_role_rel rr JOIN ai_provider_role r ON r.id = rr.role_id WHERE rr.provider_id = 1")
    return env.cr.fetchone()[0]


def uso_fallback():
    env.cr.execute("SELECT use_fallback FROM ai_provider_role WHERE code = 'design'")
    return env.cr.fetchone()[0]


def rol():
    role = env.ref('pns_ai_mcp.ai_provider_role_design')
    dec = env.ref('pns_ai_mcp.ai_provider_role_decision')
    prov = env['ai.provider'].browse(1).exists()
    if not prov or prov.model_name != 'models/gemini-3.5-flash' or prov.active:
        raise Exception('Y6: el proveedor 1 no es el esperado')
    di, de, uf, rp = titulares('design'), titulares('decision'), uso_fallback(), roles_p1()
    print('Y6 ROL antes: diseno=%s decision=%s use_fallback=%s roles_p1=%s' % (di, de, uf, rp))
    prov.write({'role_ids': [(3, dec.id), (4, role.id)]})
    role.write({'use_fallback': False})
    env['base'].flush()
    di, de, uf, rp = titulares('design'), titulares('decision'), uso_fallback(), roles_p1()
    print('Y6 ROL despues: diseno=%s decision=%s use_fallback=%s roles_p1=%s' % (di, de, uf, rp))


print('Y6 bd=%s su=%s op=%s' % (env.cr.dbname, env.su, OP))
if env.cr.dbname != BD or not env.su:
    raise Exception('Y6: shell en otra BD o sin superusuario')
f0 = foto()
print('Y6 FOTO n=%d' % len(f0))
if OP == '-':
    recarga_b()
    medida('B', f0, foto())
    deshacer('B', f0)
    recarga_bp()
    medida('BP', f0, foto())
    deshacer('BP', f0)
    rol()
    deshacer('C', f0)
    print('Y6 FIN comprobar (rollback)')
else:
    if OP == 'B':
        recarga_b()
    elif OP == 'BP':
        recarga_bp()
    if OP in ('B', 'BP'):
        lin = medida(OP, f0, foto())
        iguales = sorted(set(lin)) == sorted(set(ESPERADA.split('\n')))
        print('Y6 MEDIDA = la del comprobar: %s' % iguales)
        if not iguales:
            raise Exception('Y6: la medida de %s no es la del último comprobar; no se escribe nada' % OP)
    rol()
    env.cr.commit()
    print('Y6 COMMIT OK')
PY
  RC=$?
  echo "terminado a las $(date +%H:%M:%S); log del shell: $SL ($(wc -l < "$SL" | tr -d ' ') líneas)"
  grep '^Y6 bd=\|^Y6 FOTO\|^Y6 TOTAL\|^Y6 BP \|^Y6 MEDIDA = \|^Y6 ROL\|^Y6 ROLLBACK\|^Y6 FIN\|^Y6 COMMIT' "$SL" | sed 's/^/   /'
  chk "salida del shell" "$RC" 0 info
  chk "shell en $BD y como superusuario" "$(grep -cx "Y6 bd=$BD su=True op=$OP" "$SL" || true)" 1
  chk "foto del shell = foto externa de antes (filas)" "$(sed -n 's/^Y6 FOTO n=//p' "$SL")" "$NT"
  N0=$(grep -n '^Y6 bd=' "$SL" | head -1 | cut -d: -f1)
  echo "INFO    antes del script (arranque del shell): Traceback $(head -n "$(( ${N0:-1} - 1 ))" "$SL" | grep -c '^Traceback' || true); registros con traza (hora nivel logger): $(head -n "$(( ${N0:-1} - 1 ))" "$SL" | awk '/^Traceback/ && prev ~ / (DEBUG|INFO|WARNING|ERROR|CRITICAL) / { split(prev, a, " "); print a[4] " " a[6] } { prev = $0 }' | sort | uniq -c | sed 's/^ *//' | una) (en el ensayo, el filestore ausente, D53; no bloquea)"
  chk "Traceback, ERROR o CRITICAL en el shell, desde el primer marcador Y6" "$(tail -n +"${N0:-1}" "$SL" | grep -cE 'Traceback|ERROR|CRITICAL' || true)" 0
  [ "$(tail -n +"${N0:-1}" "$SL" | grep -c 'Traceback' || true)" = 0 ] || echo "   tipo de la excepción: $(tail -n +"${N0:-1}" "$SL" | grep -oE '^[A-Za-z_.]*(Error|Exception)' | sort -u | una)"
  chk "roles en el shell (titulares de Diseño y Decisión, use_fallback y roles del proveedor 1, antes → después)" "$(grep -E '^Y6 ROL (antes|despues):' "$SL" | una)" "Y6 ROL antes: diseno=[] decision=[1] use_fallback=True roles_p1=conversation,vision,decision Y6 ROL despues: diseno=[1] decision=[] use_fallback=False roles_p1=conversation,vision,design"
  echo "-- WARNING del shell por logger (sin el mensaje, que lleva textos de traducciones)"
  grep -oE ' WARNING [^ ]+ [^ ]+:' "$SL" | sort | uniq -c | sed 's/^/   /'
  echo "INFO    WARNING de pns_base.models.ir_translation: «drop duplicate» $(grep -c 'language import drop duplicate' "$SL" || true), «removed … duplicate» $(grep -c 'duplicate translation row' "$SL" || true) (Y6 APLICAR de la copia borrada: 9 en total)"
  for e in B BP; do
    if grep -q "^Y6 TOTAL $e " "$SL"; then
      echo "-- medida de $e por el módulo y el tipo de antes (fuera: igual / solo origen / texto cambiado / borradas; pns: igual / cambiadas / borradas; nuevas: en pns_* / fuera)"
      grep "^Y6 MEDIDA $e \|^Y6 TOTAL $e " "$SL" | sed 's/^/   /'
    fi
  done
  if [ "$OP" = - ]; then
    chk "B: borradas fuera de los pns_* (el core no borra al importar)" "$(grep -oE '^Y6 TOTAL B .*fuera_borradas=[0-9]+' "$SL" | sed 's/.*fuera_borradas=//')" 0
    chk "B′: fuera de los pns_* sin ningún cambio" "$(grep -oE '^Y6 TOTAL BP fuera_origen=[0-9]+ fuera_texto=[0-9]+ fuera_borradas=[0-9]+ nuevas_fuera=[0-9]+' "$SL")" "Y6 TOTAL BP fuera_origen=0 fuera_texto=0 fuera_borradas=0 nuevas_fuera=0"
    chk "B′: restauradas por id = las que B cambia fuera de los pns_*" "$(sed -n 's/^Y6 BP guardadas=[0-9]* restauradas=\([0-9]*\) reinsertadas=\([0-9]*\)$/\1|\2/p' "$SL")" "$(grep -oE '^Y6 TOTAL B fuera_origen=[0-9]+ fuera_texto=[0-9]+' "$SL" | awk -F'[= ]' '{ print $5 + $7 "|0" }')"
    chk "B′: guardadas = traducciones fuera de los pns_* antes" "$(sed -n 's/^Y6 BP guardadas=\([0-9]*\) .*/\1/p' "$SL")" "$NF"
    for e in B BP C; do chk "rollback tras $e, en el mismo cursor" "$(grep -cx "Y6 ROLLBACK $e: igual=True" "$SL" || true)" 1; done
    chk "el shell terminó (rollback)" "$(grep -cx 'Y6 FIN comprobar (rollback)' "$SL" || true)" 1
  else
    if [ "$OP" != C ]; then
      chk "medida de $OP igual a la del último comprobar ($(basename "$C"))" "$(grep "^Y6 MEDIDA $OP \|^Y6 TOTAL $OP " "$SL" | LC_ALL=C sort -u | una)|$(grep -cx 'Y6 MEDIDA = la del comprobar: True' "$SL" || true)" "$(printf '%s\n' "$ESP" | una)|1"
    fi
    [ "$OP" = BP ] && chk "B′: fuera de los pns_* sin ningún cambio" "$(grep -oE '^Y6 TOTAL BP fuera_origen=[0-9]+ fuera_texto=[0-9]+ fuera_borradas=[0-9]+ nuevas_fuera=[0-9]+' "$SL")" "Y6 TOTAL BP fuera_origen=0 fuera_texto=0 fuera_borradas=0 nuevas_fuera=0"
    chk "commit hecho" "$(grep -cx 'Y6 COMMIT OK' "$SL" || true)" 1
  fi

  echo "== 3. Después, desde otra sesión de solo lectura"
  chk "web del kit parado (shell --bd no lo levanta)" "$(web)" 0
  RD=$(estado_sql)
  printf '%s\n' "$RD" > "$D/y6_despues-$MODO-$M.txt"
  chk "consultas sin error (después)" "$(printf '%s\n' "$RD" | grep -ciE 'ERROR:|psql: error' || true)" 0
  chk "marcador final (después)" "$(printf '%s\n' "$RD" | grep -cx '## fin' || true)" 1
  chk "los demás roles, iguales (code|activo|use_fallback)" "$(sec "$RD" roles | grep -v '^design|' | una)" "$(sec "$RA" roles | grep -v '^design|' | una)"
  chk "es_ES activo" "$(sec "$RD" es_ES)" "es_ES|t"
  foto_sql > "$FD"
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
    if [ "$F" = 0 ]; then echo "$MKC"; else echo "== Y6 v3: $F FALLO(S). No sigas: pega la salida."; fi
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
    if [ "$F" = 0 ]; then echo "== Y6 v3: TODO OK ($MODO). Corte: pega la salida antes de Y7."; else echo "== Y6 v3: $F FALLO(S). No sigas: pega la salida."; fi
  fi
  } 2>&1 | tee "$O"
  echo "Guardado en $O"
)
ly_y6 "$@"
