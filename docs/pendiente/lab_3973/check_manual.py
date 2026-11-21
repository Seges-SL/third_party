"""Comprueba un .md del informe o del manual contra el árbol de third_party.

Uso: python3 -I check_manual.py <raiz_third_party> <archivo.md> [desde_linea] [hasta_linea]

1. Citas `archivo:línea` (también `:N` y `:N-M` encadenadas, que se refieren al último archivo citado):
   el archivo existe (ruta desde la raíz o sufijo único dentro de los módulos) y las líneas están dentro.
2. Etiquetas «…»: se buscan como msgstr (o msgid) en los tres es.po; las que no aparecen se listan (pueden ser
   citas, frases del usuario o textos marcados «sin traducir», que se revisan a mano).
3. Líneas de más de 120 caracteres que no sean de tabla.
"""
import os
import re
import sys

MODS = ('pns_base', 'pns_ai_mcp', 'pns_ai_chatboo')


def load_po(root):
    strs = set()
    for m in MODS:
        p = os.path.join(root, m, 'i18n', 'es.po')
        if not os.path.exists(p):
            continue
        cur = None
        buf = []
        for line in open(p, encoding='utf-8'):
            line = line.rstrip('\n')
            mm = re.match(r'^(msgid|msgstr) "(.*)"$', line)
            if mm:
                if buf:
                    strs.add(''.join(buf))
                cur, buf = mm.group(1), [mm.group(2)]
            elif line.startswith('"') and cur:
                buf.append(line[1:-1])
            else:
                if buf:
                    strs.add(''.join(buf))
                cur, buf = None, []
        if buf:
            strs.add(''.join(buf))
    return {s.replace('\\"', '"').replace('\\n', '\n') for s in strs}


def index_files(root):
    files = []
    for top in list(MODS) + ['docs', '_fabricante']:
        for d, _, fs in os.walk(os.path.join(root, top)):
            for f in fs:
                files.append(os.path.relpath(os.path.join(d, f), root))
    return files


def resolve(path, files, root, last_mod):
    """Orden: módulo de la cita anterior, los tres módulos, la raíz, sufijo único fuera de _fabricante."""
    tries = ([last_mod + '/' + path] if last_mod else []) + [m + '/' + path for m in MODS] + [path]
    if path.split('/')[0] in MODS or path.startswith(('docs/', '_fabricante/')):
        tries = [path]
    for c in tries:
        if os.path.isfile(os.path.join(root, c)):
            return c
    cands = [f for f in files if f.endswith('/' + path) and not f.startswith('_fabricante/')]
    if last_mod:
        pref = [f for f in cands if f.startswith(last_mod + '/')]
        if len(pref) == 1:
            return pref[0]
    if len(cands) == 1:
        return cands[0]
    return None


def nlines(root, rel, cache={}):
    if rel not in cache:
        with open(os.path.join(root, rel), encoding='utf-8', errors='replace') as fh:
            cache[rel] = sum(1 for _ in fh)
    return cache[rel]


CODE = re.compile(r'`([^`]+)`')
CIT = re.compile(r'^([A-Za-z0-9_./\-*{},]+\.(?:py|xml|js|json|md|po|csv|scss|css|sh|txt))((?::\d+(?:-\d+)?)(?:,\s*\d+(?:-\d+)?)*)?$')
CONT = re.compile(r'^:(\d+)(?:-(\d+))?$')


def main():
    root, md = sys.argv[1], sys.argv[2]
    lo = int(sys.argv[3]) if len(sys.argv) > 3 else 1
    hi = int(sys.argv[4]) if len(sys.argv) > 4 else 10 ** 9
    files = index_files(root)
    po = load_po(root)
    errs, unlabeled, longl, partial = [], [], [], []
    last, last_mod = None, None
    ncit = 0
    for no, line in enumerate(open(md, encoding='utf-8'), 1):
        line = line.rstrip('\n')
        if no < lo or no > hi:
            continue
        if len(line) > 120 and not line.lstrip().startswith('|'):
            longl.append(no)
        for tok in CODE.findall(line):
            tok = tok.strip()
            m = CIT.match(tok)
            if m and '*' not in tok and '{' not in tok:
                path, rng = m.group(1), m.group(2)
                rel = resolve(path, files, root, last_mod)
                if not rel:
                    if '/' in path:
                        errs.append((no, tok, 'archivo no encontrado o ambiguo'))
                    continue
                last = rel
                last_mod = rel.split('/')[0]
                if rng:
                    nums = [int(x) for x in re.findall(r'\d+', rng)]
                    ncit += 1
                    if max(nums) > nlines(root, rel):
                        errs.append((no, tok, 'línea fuera (%d líneas)' % nlines(root, rel)))
                continue
            m = CONT.match(tok)
            if m and last:
                ncit += 1
                top = int(m.group(2) or m.group(1))
                if top > nlines(root, last):
                    errs.append((no, tok + ' (' + last + ')', 'línea fuera'))
        for lab in re.findall(r'«([^«»]+)»', line):
            if lab in po or lab.rstrip('.') in po or lab + '.' in po:
                continue
            if any(s.startswith(lab) for s in po if s):
                partial.append((no, lab))
            else:
                unlabeled.append((no, lab))
    print('citas comprobadas:', ncit)
    print('errores de cita:', len(errs))
    for e in errs:
        print('  L%d %s -> %s' % e)
    print('líneas > 120 fuera de tablas:', longl)
    print('«…» que son el principio de una cadena de los es.po:', len(partial))
    for no, lab in partial:
        print('  L%d «%s»' % (no, lab))
    print('«…» que no están en los es.po:', len(unlabeled))
    for no, lab in unlabeled:
        print('  L%d «%s»' % (no, lab))


if __name__ == '__main__':
    main()
