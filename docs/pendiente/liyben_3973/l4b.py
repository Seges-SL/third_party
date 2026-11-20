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
