#!/usr/bin/env bash
# Prueba de p34_plantar.sh y p34_borrar.sh sin Odoo y sin Docker.
#
# Uso: bash prueba_p34_scripts.sh   (en la carpeta de los dos scripts)
#
# Ejecuta copias de los dos scripts con HOME en una carpeta temporal y un
# «odoo-dev» falso en el PATH, cuyo «shell» ejecuta lo que recibe con un ORM
# mínimo de mentira (estado en un archivo JSON). No toca ~/GitHub, ~/lab_e3p
# ni Docker. La copia de p34_plantar.sh lleva el SHA-256 de un lienzo de
# prueba; el script real no admite otro lienzo.
set -u

AQUI=$(cd "$(dirname "$0")" && pwd)
[ -f "$AQUI/p34_plantar.sh" ] && [ -f "$AQUI/p34_borrar.sh" ] || { echo "Faltan p34_plantar.sh o p34_borrar.sh junto a este script."; exit 2; }
T=$(mktemp -d /tmp/prueba_p34.XXXXXX)
trap 'rm -rf "$T"' EXIT
mkdir -p "$T/bin" "$T/home/lab_e3p" "$T/home/GitHub/lab_pns_ai_3973"
printf '<html><body><script>const DATA = [{"n": "</script><script>alert(1)</script>"}];</script></body></html>' > "$T/home/lab_e3p/p8ea_sesion11.html"
SHA_PRUEBA=$(sha256sum "$T/home/lab_e3p/p8ea_sesion11.html" | cut -d' ' -f1)
sed "s/^SHA=.*/SHA=$SHA_PRUEBA/" "$AQUI/p34_plantar.sh" > "$T/p34_plantar.sh"
cp "$AQUI/p34_borrar.sh" "$T/p34_borrar.sh"

cat > "$T/bin/odoo-dev" <<'DOBLE'
#!/usr/bin/env bash
[ "$2" = shell ] || exit 0
exec python3 -I "$(dirname "$0")/orm_falso.py"
DOBLE
chmod +x "$T/bin/odoo-dev"
cat > "$T/bin/orm_falso.py" <<'DOBLE'
import json, os, sys
RUTA = os.environ['ORM_ESTADO']
E = json.load(open(RUTA)) if os.path.exists(RUTA) else {'sesiones': [], 'sig': 20}
PEND = {'commit': False}

class Reg:
    def __init__(self, d): self.__dict__['d'] = d
    def __getattr__(self, k):
        v = self.d[k]
        return Reg({'id': v}) if k == 'user_id' else v

class Conj(list):
    @property
    def id(self): return self[0].id
    def unlink(self):
        ids = {r.id for r in self}
        E['sesiones'] = [s for s in E['sesiones'] if s['id'] not in ids]

class Sesiones:
    def sudo(self): return self
    def search(self, dom):
        return Conj(Reg(s) for s in E['sesiones'] if s['name'] == dom[0][2])
    def search_count(self, dom): return len(self.search(dom))
    def create(self, v):
        E['sig'] += 1
        v = dict(v, id=E['sig'])
        E['sesiones'].append(v)
        return Reg(v)

class Usuarios:
    def search(self, dom):
        uid = int(os.environ.get('ORM_UID', '12'))
        return Conj([Reg({'id': uid})]) if dom[0][2] == 'seges_int@example.com' else Conj()

class Cr:
    dbname = os.environ.get('ORM_BD', 'lab_pns_ai_3973_14')
    def commit(self):
        json.dump(E, open(RUTA, 'w'))

class Env(dict):
    cr = Cr()

env = Env({'chatboo.session': Sesiones(), 'res.users': Usuarios()})
exec(sys.stdin.read(), {'env': env})
DOBLE

FALLOS=0
N=0
# caso <nombre> <código esperado> <texto esperado> <respuesta> <script> [VAR=valor...]
caso() {
    local nombre=$1 esperado=$2 texto=$3 respuesta=$4 script=$5
    shift 5
    local salida rc
    salida=$(printf '%s\n' "$respuesta" | env -i PATH="$T/bin:/usr/bin:/bin" HOME="$T/home" \
        ORM_ESTADO="$T/estado.json" "$@" bash "$T/$script" 2>&1)
    rc=$?
    N=$((N + 1))
    if [ "$rc" = "$esperado" ] && echo "$salida" | grep -q "$texto"; then
        echo "PASA   $nombre → $esperado"
    else
        echo "FALLA  $nombre → $esperado (código $rc)"; FALLOS=$((FALLOS + 1))
    fi
}
filas() { python3 -I -c "import json,os,sys; p=sys.argv[1]; print(len(json.load(open(p))['sesiones']) if os.path.exists(p) else 0)" "$T/estado.json"; }

caso "plantar: respuesta distinta de s"        10 "No se planta"                 n p34_plantar.sh
caso "plantar: otra BD en el contexto"          1 "P34 ERROR: la BD"             s p34_plantar.sh ORM_BD=otra_14
caso "plantar: seges_int no es el usuario 12"   1 "P34 ERROR: seges_int"         s p34_plantar.sh ORM_UID=7
N=$((N + 1)); if [ "$(filas)" = 0 ]; then echo "PASA   tras los tres rechazos no hay nada escrito"; else echo "FALLA  hay filas escritas"; FALLOS=$((FALLOS + 1)); fi
caso "plantar: bien"                            0 "P34 PLANTADA id=21 usuario=12 canvas_rev=1 bytes=" s p34_plantar.sh
caso "plantar: ya hay una plantada"             1 "P34 ERROR: ya hay"            s p34_plantar.sh
N=$((N + 1)); if [ "$(filas)" = 1 ]; then echo "PASA   queda una sola sesión plantada"; else echo "FALLA  filas: $(filas)"; FALLOS=$((FALLOS + 1)); fi
N=$((N + 1)); if python3 -I -c "
import hashlib, json, sys
s = json.load(open(sys.argv[1]))['sesiones'][0]
ok = (hashlib.sha256(s['canvas_design'].encode()).hexdigest() == sys.argv[2] and s['canvas_open'] is True
      and s['user_id'] == 12 and s['name'] == 'Seges P34 lienzo plantado (D24)')
sys.exit(0 if ok else 1)" "$T/estado.json" "$SHA_PRUEBA"; then echo "PASA   el lienzo guardado es idéntico al archivo (SHA-256), abierto y del usuario 12"; else echo "FALLA  el lienzo guardado no coincide"; FALLOS=$((FALLOS + 1)); fi
caso "borrar: respuesta distinta de s"         10 "No se borra"                  n p34_borrar.sh
caso "borrar: otra BD en el contexto"           1 "P34 ERROR: la BD"             s p34_borrar.sh ORM_BD=otra_14
caso "borrar: bien"                             0 "P34 BORRADA sesiones=1 quedan=0" s p34_borrar.sh
caso "borrar: no había ninguna"                 0 "P34 BORRADA sesiones=0 quedan=0" s p34_borrar.sh
echo x >> "$T/home/lab_e3p/p8ea_sesion11.html"
caso "plantar: SHA-256 del HTML distinto"      12 "no es el previsto"            s p34_plantar.sh
rm "$T/home/lab_e3p/p8ea_sesion11.html"
caso "plantar: falta el HTML"                  12 "No existe"                    s p34_plantar.sh
caso "borrar: falta la carpeta del laboratorio" 13 "No existe"                   s p34_borrar.sh HOME="$T/vacio"

echo
if [ "$FALLOS" = 0 ]; then echo "Prueba de los scripts de D24: $N PASA"; exit 0; fi
echo "Prueba de los scripts de D24: $FALLOS FALLA de $N"; exit 1
