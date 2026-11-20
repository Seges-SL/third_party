#!/usr/bin/env python3
# Copyright 2026 Seges
# License Apache-2.0 (https://www.apache.org/licenses/LICENSE-2.0).
"""Cuenta los lienzos y páginas guardados con un DATA que el servidor no puede leer.

Solo lectura. Lee por la entrada estándar una línea JSON por diseño, como la que da
esta consulta de psql (-At):

    SELECT row_to_json(t) FROM (
        SELECT 'chatboo.session' AS m, id, canvas_design AS d
          FROM chatboo_session WHERE canvas_design IS NOT NULL
        UNION ALL
        SELECT 'chatboo.canvas.page', id, design
          FROM chatboo_canvas_page WHERE design IS NOT NULL
    ) t;

Usa la misma comprobación que el fragmento del parche 29 (parches_pns_ai.md): un
``const/let/var DATA =`` o ``window.DATA =`` cuyo JSON no se puede leer dentro de su
propio <script> (cortado como lo corta el servidor), o que queda fuera de cualquier
<script>. Un DATA del modelo que sí es JSON no se distingue del del servidor y no se cuenta.
"""
import json
import re
import sys

SCRIPT = re.compile(r'(<script\b[^>]*>)(.*?)(</script>)', re.I | re.S)
ASSIGN = re.compile(r'(?:\b(?:const|let|var)\s+|\bwindow\s*\.\s*)DATA\s*=(?!=)\s*')
NAME = re.compile(r'[A-Za-z_$][\w$.]*\s*(?:[;,)]|\Z)')
DECODER = json.JSONDecoder()


def data_ilegible(page):
    text, seen = page or '', 0
    for match in SCRIPT.finditer(text):
        inner = match.group(2)
        for hit in ASSIGN.finditer(inner):
            seen += 1
            if NAME.match(inner, hit.end()):
                continue
            try:
                DECODER.raw_decode(inner, hit.end())
            except ValueError:
                return True
    return len(ASSIGN.findall(text)) > seen


def main():
    total, bad = {}, {}
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        row = json.loads(line)
        model = row['m']
        total[model] = total.get(model, 0) + 1
        if data_ilegible(row.get('d')):
            bad.setdefault(model, []).append(row['id'])
    for model in ('chatboo.session', 'chatboo.canvas.page'):
        ids = sorted(bad.get(model, []))
        print('%-20s %4d con diseño; %3d con DATA ilegible: %s'
              % (model, total.get(model, 0), len(ids), ids))


if __name__ == '__main__':
    main()
