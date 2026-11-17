#!/usr/bin/env bash
# Prueba de p34_modelo.sh sin Odoo y sin Docker.
#
# Uso: bash prueba_p34_modelo.sh   (en la carpeta del script)
#
# Ejecuta una copia del script con HOME en una carpeta temporal y un «odoo-dev»
# falso cuyo «shell» ejecuta lo que recibe con un ORM mínimo de mentira (estado
# en un archivo JSON; model_name sigue a model_id como el related real).
set -u

AQUI=$(cd "$(dirname "$0")" && pwd)
[ -f "$AQUI/p34_modelo.sh" ] || { echo "Falta p34_modelo.sh junto a este script."; exit 2; }
T=$(mktemp -d /tmp/prueba_p34m.XXXXXX)
trap 'rm -rf "$T"' EXIT
mkdir -p "$T/bin" "$T/home/GitHub/lab_pns_ai_3973"
cp "$AQUI/p34_modelo.sh" "$T/p34_modelo.sh"

cat > "$T/bin/odoo-dev" <<'DOBLE'
#!/usr/bin/env bash
[ "$2" = shell ] || exit 0
exec python3 -I "$(dirname "$0")/orm_falso.py"
DOBLE
chmod +x "$T/bin/odoo-dev"
cat > "$T/bin/orm_falso.py" <<'DOBLE'
import json, os, sys
RUTA = os.environ['ORM_ESTADO']
MODELOS = {24: 'models/gemini-3.5-flash', 25: 'models/gemini-3.5-flash-lite', 30: 'models/gemini-3.6-flash',
           40: 'models/otro'}
E = json.load(open(RUTA)) if os.path.exists(RUTA) else {'model_id': int(os.environ.get('ORM_INICIAL', '30')), 'escrituras': 0}

class Modelo:
    def __init__(self, i):
        self.id, self.name = i, MODELOS.get(i, False)

class Conj(list):
    @property
    def id(self): return self[0].id

class Proveedor:
    name = 'Gemini lab'
    active = os.environ.get('ORM_ACTIVO', '1') == '1'
    @property
    def model_id(self): return Modelo(E['model_id'])
    @property
    def model_name(self): return MODELOS.get(E['model_id'], False)
    def exists(self): return self
    def __bool__(self): return True
    def write(self, v):
        if os.environ.get('ORM_WRITE_FALLA'):
            raise ValueError('falla simulada')
        E['model_id'] = v['model_id']
        E['escrituras'] += 1

class Proveedores:
    def browse(self, i): return Proveedor()

class Modelos:
    def search(self, dom):
        nombre = dom[1][2]
        if os.environ.get('ORM_SIN_DESTINO'):
            return Conj()
        return Conj(Modelo(i) for i, n in MODELOS.items() if n == nombre)

class Cr:
    dbname = os.environ.get('ORM_BD', 'lab_pns_ai_3973_14')
    def commit(self):
        json.dump(E, open(RUTA, 'w'))

class Env(dict):
    cr = Cr()

env = Env({'ai.provider': Proveedores(), 'ai.provider.model': Modelos()})
try:
    exec(sys.stdin.read(), {'env': env})
except SystemExit as e:
    sys.exit(e.code)
DOBLE

FALLOS=0
N=0
# caso <nombre> <código esperado> <texto esperado> <respuesta> <orden> [VAR=valor...]
caso() {
    local nombre=$1 esperado=$2 texto=$3 respuesta=$4 orden=$5
    shift 5
    local salida rc
    salida=$(printf '%s\n' "$respuesta" | env -i PATH="$T/bin:/usr/bin:/bin" HOME="$T/home" \
        ORM_ESTADO="$T/estado.json" "$@" bash "$T/p34_modelo.sh" $orden 2>&1)
    rc=$?
    N=$((N + 1))
    if [ "$rc" = "$esperado" ] && echo "$salida" | grep -q "$texto"; then
        echo "PASA   $nombre → $esperado"
    else
        echo "FALLA  $nombre → $esperado (código $rc)"; FALLOS=$((FALLOS + 1))
    fi
}
valor() { python3 -I -c "import json,os,sys; p=sys.argv[1]; d=json.load(open(p)) if os.path.exists(p) else {'model_id': 30, 'escrituras': 0}; print(d['model_id'], d['escrituras'])" "$T/estado.json"; }
comprobar() {
    N=$((N + 1))
    if [ "$(valor)" = "$2" ]; then echo "PASA   $1"; else echo "FALLA  $1 (estado: $(valor))"; FALLOS=$((FALLOS + 1)); fi
}

caso "sin orden"                               12 "Uso:"                                  s ""
caso "orden desconocida"                       12 "Uso:"                                  s "otra"
caso "poner sin modelo"                        12 "Uso:"                                  s "poner"
caso "poner con modelo desconocido"            12 "Uso:"                                  s "poner pro"
caso "estado (solo lee, sin pregunta)"          0 "P34 MODELO estado proveedor=2 modelo=models/gemini-3.6-flash model_id=30" "" estado
caso "poner lite: respuesta distinta de s"     10 "No se cambia"                          n "poner lite"
caso "poner lite: otra BD en el contexto"       1 "P34 ERROR: la BD"                      s "poner lite" ORM_BD=otra_14
caso "poner lite: proveedor 2 inactivo"         1 "P34 ERROR: el proveedor 2"             s "poner lite" ORM_ACTIVO=0
caso "poner lite: no existe el modelo destino"  1 "P34 ERROR: no hay exactamente"         s "poner lite" ORM_SIN_DESTINO=1
caso "poner lite: falla el write"               1 "P34 ERROR: al escribir: ValueError"    s "poner lite" ORM_WRITE_FALLA=1
comprobar "tras los rechazos no hay nada escrito (model_id 30, 0 escrituras)" "30 0"
caso "devolver estando ya en 3.6 flash"         0 "P34 MODELO ya estaba: models/gemini-3.6-flash" s devolver
caso "poner flash: bien (desde 3.6)"            0 "P34 MODELO antes=models/gemini-3.6-flash ahora=models/gemini-3.5-flash model_id=24" s "poner flash"
caso "poner lite: bien (desde 3.5 flash, como hoy)" 0 "P34 MODELO antes=models/gemini-3.5-flash ahora=models/gemini-3.5-flash-lite model_id=25" s "poner lite"
comprobar "model_id 25 tras poner lite (2 escrituras)" "25 2"
caso "poner lite otra vez: ya estaba"           0 "P34 MODELO ya estaba: models/gemini-3.5-flash-lite" s "poner lite"
caso "estado tras poner lite"                   0 "modelo=models/gemini-3.5-flash-lite model_id=25" "" estado
caso "devolver: bien (desde lite)"              0 "P34 MODELO antes=models/gemini-3.5-flash-lite ahora=models/gemini-3.6-flash model_id=30" s devolver
comprobar "model_id 30 tras devolver (3 escrituras)" "30 3"
rm -f "$T/estado.json"
caso "modelo de partida desconocido"            1 "P34 ERROR: el modelo actual no es uno de los conocidos" s "poner lite" ORM_INICIAL=40
caso "falta la carpeta del laboratorio"        13 "No existe"                             s estado HOME="$T/vacio"

echo
if [ "$FALLOS" = 0 ]; then echo "Prueba de p34_modelo.sh: $N PASA"; exit 0; fi
echo "Prueba de p34_modelo.sh: $FALLOS FALLA de $N"; exit 1
