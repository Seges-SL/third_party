"""Menús de los tres módulos pns_* con su padre, sus grupos y su nombre en es.po.

Uso: python3 -I menus.py <raiz_third_party>
Solo lee. Imprime: xmlid | nombre en | nombre es | padre | grupos | archivo:línea
"""
import os
import re
import sys
import xml.etree.ElementTree as ET

MODS = ('pns_base', 'pns_ai_mcp', 'pns_ai_chatboo')


def po_map(root):
    out = {}
    for m in MODS:
        p = os.path.join(root, m, 'i18n', 'es.po')
        if not os.path.exists(p):
            continue
        txt = open(p, encoding='utf-8').read()
        for mid, mstr in re.findall(r'^msgid ((?:"[^\n]*"\n)+)msgstr ((?:"[^\n]*"\n)+)', txt, re.M):
            k = ''.join(re.findall(r'"(.*)"', mid))
            v = ''.join(re.findall(r'"(.*)"', mstr))
            if k and v:
                out.setdefault(k, v)
    return out


def main():
    root = sys.argv[1]
    po = po_map(root)
    rows = []
    for m in MODS:
        for d, _, fs in os.walk(os.path.join(root, m)):
            if '/tests' in d or '/migrations' in d:
                continue
            for f in fs:
                if not f.endswith('.xml'):
                    continue
                p = os.path.join(d, f)
                src = open(p, encoding='utf-8').read()
                if '<menuitem' not in src:
                    continue
                lines = src.split('\n')
                try:
                    tree = ET.parse(p)
                except ET.ParseError:
                    continue
                for el in tree.iter('menuitem'):
                    mid = el.get('id')
                    ln = next((i + 1 for i, l in enumerate(lines) if 'id="%s"' % mid in l), 0)
                    name = el.get('name') or ''
                    rows.append((m + '.' + mid if '.' not in mid else mid, name, po.get(name, '(sin traducir)' if name else ''),
                                 el.get('parent') or '-', el.get('groups') or '-',
                                 os.path.relpath(p, root) + ':' + str(ln)))
    for r in rows:
        print(' | '.join(r))


if __name__ == '__main__':
    main()
