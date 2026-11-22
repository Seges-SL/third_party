"""Traduce msgid -> msgstr de los es.po de los pns_*. Uso: python3 -I tr.py <raiz> 'Texto 1' 'Texto 2' ..."""
import re, sys, os
root=sys.argv[1]; po={}
for m in ('pns_base','pns_ai_mcp','pns_ai_chatboo'):
    p=os.path.join(root,m,'i18n','es.po')
    txt=open(p,encoding='utf-8').read()
    for mid,mstr in re.findall(r'^msgid ((?:"[^\n]*"\n)+)msgstr ((?:"[^\n]*"\n)+)',txt,re.M):
        k=''.join(re.findall(r'"(.*)"',mid)); v=''.join(re.findall(r'"(.*)"',mstr))
        if k: po.setdefault(k,[]).append((m,v))
for s in sys.argv[2:]:
    r=po.get(s)
    print(f"{s!r} -> {[v for _,v in r] if r else 'NO EN es.po'}")
