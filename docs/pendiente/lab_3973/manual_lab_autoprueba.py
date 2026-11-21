# -*- coding: utf-8 -*-
"""Autoprueba de manual_lab.py, sin Odoo ni BD (env, cursor y lectura simulados).

Uso (solo lectura, sin red):
    docker run --rm --network none --read-only --tmpfs /tmp \
        -v ~/GitHub/third_party/docs/pendiente/lab_3973:/src:ro \
        --entrypoint python3 odoo-dev:14 -I /src/manual_lab_autoprueba.py

Casos: IGUAL (0), DISTINTO (1), BD desactualizada (8), escritura rechazada (20),
transacción no de solo lectura (20), error de base de datos en M3 (20), M12 sin
modelos de los tres módulos (8) y DISTINTO en M4 con M12 sin modelos (8: manda el
no concluyente). En todos se
comprueba que rollback y close se llaman una sola vez, que la primera orden es
SET TRANSACTION READ ONLY, que hay un SHOW antes de cada bloque ejecutado, que la
última línea es «CÓDIGO: <n>» y que la salida no lleva ningún valor marcado como secreto.
Compatible con Python 3.7.
"""
import copy
import importlib.util
import os
import sys
import types

sys.dont_write_bytecode = True
AQUI = os.path.dirname(os.path.abspath(__file__))
SECRETO = 'SECRETO'

try:  # psycopg2 >= 2.8
    from psycopg2.errors import ReadOnlySqlTransaction as _ROBase
    from psycopg2.errors import UndefinedTable as _UTBase

    class ReadOnlySqlTransaction(_ROBase):
        pass

    class UndefinedTable(_UTBase):
        pass
except ImportError:  # psycopg2 2.7 (Debian buster) o sin psycopg2
    try:
        import psycopg2
        _Int, _Prog = psycopg2.InternalError, psycopg2.ProgrammingError
    except ImportError:
        _Int = _Prog = Exception

    class ReadOnlySqlTransaction(_Int):
        pgcode = '25006'

    class UndefinedTable(_Prog):
        pgcode = '42P01'


def cargar():
    spec = importlib.util.spec_from_file_location(
        'manual_lab', os.path.join(AQUI, 'manual_lab.py'))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


ML = cargar()


# ---------------------------------------------------------------- simulados

class CursorSimulado(object):

    def __init__(self, solo_lectura='on', falla_en=None, error=None):
        self.solo_lectura = solo_lectura
        self.falla_en = falla_en
        self.error = error
        self.ordenes = []
        self.rollbacks = 0
        self.closes = 0
        self._ultima = None

    def execute(self, query, params=None):
        if self.closes:
            raise RuntimeError('cursor cerrado')
        self.ordenes.append(query)
        self._ultima = query
        if self.falla_en and query == '-- ' + self.falla_en:
            raise self.error('%s: mensaje con datos que no debe salir' % SECRETO)

    def fetchone(self):
        if self._ultima == 'SHOW transaction_read_only':
            return (self.solo_lectura,)
        return None

    def commit(self):
        raise AssertionError('commit no permitido')

    def rollback(self):
        self.rollbacks += 1

    def close(self):
        self.closes += 1


class Trampa(object):
    """env.cr del shell: el script no debe tocarlo."""

    def __getattr__(self, name):
        raise AssertionError('se ha usado env.cr del shell (%s)' % name)


class RegistroSimulado(object):

    def __init__(self, cr):
        self.cr = cr
        self.cursores = 0

    def cursor(self):
        self.cursores += 1
        return self.cr


class EnvShell(object):

    def __init__(self, cr):
        self.registry = RegistroSimulado(cr)
        self.cr = Trampa()


class EnvSimulado(object):

    def __init__(self, cr, uid, context):
        self.cr = cr
        self.uid = uid
        self.context = dict(context)


def instalar_odoo_simulado():
    odoo = types.ModuleType('odoo')
    odoo.SUPERUSER_ID = 1
    odoo.api = types.SimpleNamespace(Environment=EnvSimulado)
    sys.modules['odoo'] = odoo


def datos_iguales():
    """Datos que coinciden con lo previsto; los no numéricos llevan la marca SECRETO."""
    contextos = []
    for (mod, ctype), n in ML.M5_RECUENTO.items():
        if mod == 'pns_ai_chatboo':
            continue
        contextos += [(mod, ctype, '%s_%d' % (ctype, i)) for i in range(n)]
    for code in ML.M5_CODIGOS_CHATBOO:
        ctype = 'discovery' if code.startswith('discovery_') else 'domain'
        contextos.append(('pns_ai_chatboo', ctype, code))
    skills = []
    for code, command, name in ML.M6_SKILLS:
        skills.append({'module': 'pns_ai_chatboo', 'code': code,
                       'command': '' if command == code else command, 'name': name,
                       'is_system': True,
                       'groups': set(ML.M6_GRUPOS_USERS) if code == 'users' else set()})
    return {
        'es': True,
        'versions': dict((m, ('installed', v)) for m, v in ML.M1_VERSIONES.items()),
        'xmlids': {
            'res.groups': set(g[0] for g in ML.M2_GRUPOS),
            'ir.ui.menu': set(m[0] for m in ML.M3_MENUS),
            'ir.cron': set(c[0] for c in ML.M10_CRONS),
        },
        'names': {ML.M2_CATEGORIA[0]: ML.M2_CATEGORIA[1]},
        'groups': dict((x, {'name': es, 'implied': set(imp), 'category': ML.M2_CATEGORIA[0]})
                       for x, es, imp in ML.M2_GRUPOS),
        'menus': dict((x, {'name': es, 'parent': p, 'groups': set(g)})
                      for x, es, p, g in ML.M3_MENUS),
        'visibles': [(2, ['pns_ai_chatboo.menu_chatboo_root'])],
        'labels': dict(((m, mo, f), es) for m, mo, f, es, _c in ML.M4_ETIQUETAS),
        'contexts': contextos,
        'skills': skills,
        'roles': dict(ML.M7_ROLES),
        'accepts': tuple(ML.M7_ACCEPTS),
        'agents': dict((x, {'code': c, 'agent_type': t}) for x, c, t in ML.M8_AGENTES),
        'modules': set(ML.MODS),
        'field_meta': {'type': 'boolean', 'default': False},
        # Claves definidas: dos de texto con secreto, una numérica y la marca del kit.
        'params': {
            'pns_ai_mcp.mcp_allowed_origins': SECRETO + '-origenes',
            'pns_ai_mcp.url_access_policy': SECRETO + '-politica',
            'pns_base.export_retention_hours': '48',
            ML.MARCA_NEUTRALIZADA: SECRETO + '-fecha',
        },
        'decimals': 2,
        # Con la marca del kit los crons inactivos no cuentan.
        'crons': dict((x, {'model': mo, 'code': c, 'active': False})
                      for x, mo, c in ML.M10_CRONS),
        'models': ML.M12_MODELOS,
        'rules': [('pns_ai_mcp.ai_log_user_rule', 'ai.log', False),
                  ('pns_ai_chatboo.chatboo_session_user_rule', 'chatboo.session', False)],
    }


class LectorSimulado(object):
    """Misma interfaz que OdooLector; cada lectura pasa por el cursor del env."""

    BLOQUE_XMLIDS = {'res.groups': 'M2', 'ir.ui.menu': 'M3', 'ir.cron': 'M10'}

    def __init__(self, env, datos, registro):
        self.env = env
        self.d = datos
        registro.append(self)

    def _q(self, bloque):
        self.env.cr.execute('-- ' + bloque)

    def lang_active(self, code):
        self._q('PREP')
        return self.d['es'] and code == 'es_ES'

    def versions(self):
        self._q('M1')
        return dict(self.d['versions'])

    def module_exists(self, name):
        self._q('M8')
        return name in self.d['modules']

    def xmlids_of(self, model):
        self._q(self.BLOQUE_XMLIDS[model])
        return set(self.d['xmlids'][model])

    def record_name(self, xmlid):
        self._q('M2')
        return self.d['names'].get(xmlid)

    def group(self, xmlid):
        self._q('M2')
        return copy.deepcopy(self.d['groups'].get(xmlid))

    def menu(self, xmlid):
        self._q('M3')
        return copy.deepcopy(self.d['menus'].get(xmlid))

    def visible_menus(self):
        self._q('M3')
        return list(self.d['visibles'])

    def field_label(self, module, model_us, field):
        self._q('M4')
        return self.d['labels'].get((module, model_us, field))

    def po_label(self, module, model_us, field):
        self._q('M4')
        return self.d['labels'].get((module, model_us, field))

    def contexts(self):
        self._q('M5')
        return list(self.d['contexts'])

    def skills(self):
        self._q('M6')
        return copy.deepcopy(self.d['skills'])

    def roles(self):
        self._q('M7')
        return dict(self.d['roles'])

    def accepts_selection(self):
        self._q('M7')
        return self.d['accepts']

    def agent(self, xmlid):
        self._q('M8')
        return copy.deepcopy(self.d['agents'].get(xmlid))

    def field_meta(self, model, field):
        self._q('M9')
        return dict(self.d['field_meta'])

    def product_settings(self):
        # M9 y M11 la llaman: marcador propio para que el fallo «M11» caiga en M11.
        self._q('ICP')
        p = self.d['params']

        def num(key, default):
            try:
                return int(p[key])
            except (KeyError, ValueError):
                return default
        return {
            'history_retention_days': num('pns_ai_chatboo.history_retention_days', 0),
            'query_data_ttl_hours': num('pns_ai_chatboo.query_data_ttl_hours', 12),
            'dataset_cache_max_mb': num('pns_ai_mcp.dataset_cache_max_bytes', 8),
            'upload_max_mb': num('pns_ai_chatboo.upload_max_bytes', 15),
            'download_max_mb': num('pns_ai.download_max_bytes', 15),
            'xlsx_float_decimals': self.d['decimals'],
            'allow_remote_voices': ML.M9_CLAVE in p,
            # Valores de texto que el script no debe imprimir.
            'chart_engine': SECRETO + '-grafico',
        }

    def param(self, key):
        self._q('ICP')  # M9, M10 y M11
        p = self.d['params']
        return (key in p, p.get(key))

    def currency_decimals(self):
        self._q('M11')  # solo M11 (pns_ai.xlsx_float_decimals sin clave)
        return self.d['decimals']

    def cron(self, xmlid):
        self._q('M10')
        return copy.deepcopy(self.d['crons'].get(xmlid))

    def company_rules(self):
        self._q('M12')
        return self.d['models'], list(self.d['rules'])


# ---------------------------------------------------------------- casos

def ejecutar(datos, cursor):
    instalar_odoo_simulado()
    lectores = []
    lineas = []
    env = EnvShell(cursor)
    codigo = ML.run(env, lineas.append,
                    _lector=lambda e: LectorSimulado(e, datos, lectores))
    return codigo, lineas, env, lectores


def comprobar(nombre, datos, cursor, codigo_previsto, extra=None):
    fallos = []
    codigo, lineas, env, lectores = ejecutar(datos, cursor)
    if codigo != codigo_previsto:
        fallos.append('código %s, previsto %s' % (codigo, codigo_previsto))
    if not lineas or lineas[-1] != 'CÓDIGO: %d' % codigo_previsto:
        fallos.append('última línea distinta de «CÓDIGO: %d»' % codigo_previsto)
    if env.registry.cursores != 1:
        fallos.append('cursores abiertos: %d' % env.registry.cursores)
    if cursor.rollbacks != 1 or cursor.closes != 1:
        fallos.append('rollback %d y close %d (previsto 1 y 1)'
                      % (cursor.rollbacks, cursor.closes))
    if not cursor.ordenes or cursor.ordenes[0] != 'SET TRANSACTION READ ONLY':
        fallos.append('la primera orden no es SET TRANSACTION READ ONLY')
    if any(SECRETO in l for l in lineas):
        fallos.append('la salida lleva un valor marcado como secreto')
    ejecutados = [l.split(' | ')[0] for l in lineas
                  if l.split(' | ')[0] in dict(ML.BLOQUES)]
    shows = cursor.ordenes.count('SHOW transaction_read_only')
    if shows < 1 + len(set(b for b in ejecutados if not _no_ejecutado(lineas, b))):
        fallos.append('falta un SHOW transaction_read_only antes de algún bloque')
    for lector in lectores[1:]:
        if lector.env.cr is not cursor:
            fallos.append('el lector no usa el cursor nuevo')
        if datos['es'] and lector.env.context.get('lang') != 'es_ES':
            fallos.append('el Environment no lleva lang es_ES')
        if lector.env.uid != 1:
            fallos.append('el Environment no es de SUPERUSER_ID')
    if extra:
        fallos += extra(lineas)
    print('CASO %-32s %s (código %s)' % (nombre, 'OK' if not fallos else 'FALLO', codigo))
    for f in fallos:
        print('    - ' + f)
    return not fallos


def _no_ejecutado(lineas, bloque):
    return any(l in ('%s | %s' % (bloque, ML.NO_EJECUTADO),
                     '%s | %s' % (bloque, ML.NO_CONCLUYENTE)) for l in lineas)


def _estado_de(lineas, bloque):
    return [l for l in lineas if l.split(' | ')[0] == bloque]


def extra_igual(lineas):
    f = []
    if any((' | %s' % ML.DISTINTO) in l for l in lineas):
        f.append('hay líneas DISTINTO')
    activos = [l for l in lineas if l.startswith('M10 |') and ' activo |' in l]
    if not activos or not all(ML.INFORMATIVO in l for l in activos):
        f.append('con la marca del kit, «activo» no sale informativo')
    if not any(l.startswith('M11 | pns_base.export_retention_hours | INFORMATIVO | definida · valor 48')
               for l in lineas):
        f.append('no se muestra el valor de la clave numérica definida')
    return f


def extra_distinto(lineas):
    f = []
    d = [l for l in lineas if (' | %s' % ML.DISTINTO) in l]
    if len(d) != 1 or 'group_ai_writer nombre' not in d[0]:
        f.append('se esperaba un solo DISTINTO, el del nombre de group_ai_writer')
    return f


def extra_desactualizada(lineas):
    f = []
    for bloque, _fn in ML.BLOQUES[1:]:
        if _estado_de(lineas, bloque) != ['%s | %s' % (bloque, ML.NO_CONCLUYENTE)]:
            f.append('%s no sale NO CONCLUYENTE' % bloque)
    return f


def extra_error_en(bloque, tipo):
    def extra(lineas):
        f = []
        nombres = [b for b, _fn in ML.BLOQUES]
        i = nombres.index(bloque)
        err = _estado_de(lineas, bloque)
        if not err or not err[-1].startswith('%s | %s | %s' % (bloque, ML.ERROR, tipo)):
            f.append('%s no sale con ERROR y tipo %s' % (bloque, tipo))
        for b in nombres[i + 1:]:
            if _estado_de(lineas, b) != ['%s | %s' % (b, ML.NO_EJECUTADO)]:
                f.append('%s no sale NO EJECUTADO' % b)
        return f
    return extra


def extra_m12_sin_modelos(lineas):
    f = []
    m12 = _estado_de(lineas, 'M12')
    if m12 != ['M12 | modelos de los tres módulos | %s | encontrados 0 · previstos %d'
               % (ML.NO_CONCLUYENTE, ML.M12_MODELOS)]:
        f.append('M12 no sale NO CONCLUYENTE con 0 modelos')
    if any((' | %s' % ML.DISTINTO) in l for l in lineas):
        f.append('hay líneas DISTINTO')
    return f


def extra_m4_distinto_m12_sin_modelos(lineas):
    f = []
    d = [l for l in lineas if (' | %s' % ML.DISTINTO) in l]
    if len(d) != 1 or not d[0].startswith('M4 | pns_ai_chatboo.res_config_settings__'
                                          'chatboo_show_systray | DISTINTO'):
        f.append('se esperaba un solo DISTINTO, en M4 (chatboo_show_systray)')
    if _estado_de(lineas, 'M12') != [
            'M12 | modelos de los tres módulos | %s | encontrados 0 · previstos %d'
            % (ML.NO_CONCLUYENTE, ML.M12_MODELOS)]:
        f.append('M12 no sale NO CONCLUYENTE con 0 modelos')
    return f


def extra_no_solo_lectura(lineas):
    f = []
    for b, _fn in ML.BLOQUES:
        if _estado_de(lineas, b) != ['%s | %s' % (b, ML.NO_EJECUTADO)]:
            f.append('%s no sale NO EJECUTADO' % b)
    return f


def main():
    resultados = []

    resultados.append(comprobar('IGUAL', datos_iguales(), CursorSimulado(), 0, extra_igual))

    d = datos_iguales()
    d['groups']['pns_ai_mcp.group_ai_writer']['name'] = 'Escritor IA'
    resultados.append(comprobar('DISTINTO', d, CursorSimulado(), 1, extra_distinto))

    d = datos_iguales()
    d['versions']['pns_ai_mcp'] = ('installed', '14.0.3.1.879')
    resultados.append(comprobar('BD desactualizada', d, CursorSimulado(), 8,
                                extra_desactualizada))

    resultados.append(comprobar(
        'escritura rechazada (M11)', datos_iguales(),
        CursorSimulado(falla_en='M11', error=ReadOnlySqlTransaction), 20,
        extra_error_en('M11', 'ReadOnlySqlTransaction')))

    resultados.append(comprobar(
        'transacción no de solo lectura', datos_iguales(),
        CursorSimulado(solo_lectura='off'), 20, extra_no_solo_lectura))

    resultados.append(comprobar(
        'error de BD en M3', datos_iguales(),
        CursorSimulado(falla_en='M3', error=UndefinedTable), 20,
        extra_error_en('M3', 'UndefinedTable')))

    d = datos_iguales()
    d['models'] = 0
    resultados.append(comprobar('M12 sin modelos', d, CursorSimulado(), 8,
                                extra_m12_sin_modelos))

    d = datos_iguales()
    d['labels'][('pns_ai_chatboo', 'res_config_settings', 'chatboo_show_systray')] = 'Otra'
    d['models'] = 0
    resultados.append(comprobar('DISTINTO en M4 y M12 sin modelos', d, CursorSimulado(),
                                8, extra_m4_distinto_m12_sin_modelos))

    total = len(resultados)
    bien = sum(1 for r in resultados if r)
    print('RESULTADO: %d de %d casos OK' % (bien, total))
    return 0 if bien == total else 1


if __name__ == '__main__':
    sys.exit(main())
