# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 Patanegra Soft <https://patanegra.com>
"""Browser-tab canvas helpers. Methods live on ``chatboo.session``.

The page the user sees is ours. The model's HTML sits in a sandboxed frame
that does not receive the Odoo session.

``paint_canvas`` is a method of ``chatboo.session``, the class the addon
already loads. A second ``_inherit`` in this file was invisible until
``-u`` listed it, and every ``page_url`` then died with AttributeError
while the pack told the model to blame a missing Design provider.
"""
import ast
import html
import json
import logging
import re
import unicodedata
# Seges: parche 29 (P-8e a, seguridad). Ver docs/pendiente/parches_pns_ai.md
from html.parser import HTMLParser

from odoo import _

_logger = logging.getLogger(__name__)

# Seges: parche 27 (F1, seguridad). Ver docs/pendiente/parches_pns_ai.md
# Inside a <script> the HTML parser ends the block at </script> and reads
# <!-- as a comment: a row must not do either. Line separators break old JS.
_SCRIPT_UNSAFE = (
    ('<', '\\u003c'), ('>', '\\u003e'), ('&', '\\u0026'),
    ('\u2028', '\\u2028'), ('\u2029', '\\u2029'),
)


def _script_safe(text):
    """JSON text that can sit inside a <script>. Exact: JSON keeps those
    characters only inside strings, where the escape means the same."""
    for char, escaped in _SCRIPT_UNSAFE:
        text = text.replace(char, escaped)
    return text


def _script_json(value):
    """``value`` as JSON for a <script>: the one way figures go in."""
    return _script_safe(json.dumps(value, ensure_ascii=False, default=str))


_PAGE_RULES = (
    'You return a reusable HTML template, not a finished report. '
    'The server always replaces const DATA (and const TITLE when you write it) '
    'with this run\'s figures. '
    'A short sample comes with the prompt so you can see the shape; '
    'you may keep that sample or use fictional rows with the same keys. '
    'Write them once as const DATA = the figures JSON from the prompt, '
    'same keys, no renamed columns. '
    'Write the page title once as const TITLE = the title string from the prompt. '
    'Cards, charts, totals, the page title and any chip, button or filter '
    'that names a row or a figure read from DATA. Build those controls '
    'in the script from DATA; do not leave one button per row in the HTML. '
    'Do not write a figure, a row label or the page title\'s numbers as a '
    'literal in the HTML, in CSS, in attributes or in another script. '
    'Do not write a fallback label for a missing field; use the field '
    'from DATA, even when it is empty. '
    'Show a period field as stored. Do not write month names and do '
    'not set a locale. '
    'When the figures change, replace DATA; do not patch the markup. '
    'Do not fetch and do not call APIs. '
    # Seges: parche 27 (F1, seguridad). Ver docs/pendiente/parches_pns_ai.md
    'Do not load external libraries, fonts, stylesheets or images: the page '
    'cannot reach the network. Draw charts with inline SVG or <canvas>. '
    # Seges: parche 29 (P-8e a, seguridad). Ver docs/pendiente/parches_pns_ai.md
    'Put every value from DATA and TITLE on the page with textContent (or '
    'createTextNode): they are plain text. Never insert them with innerHTML, '
    'outerHTML, insertAdjacentHTML or document.write. '
    'Every tab, chip or card you open must already contain its figures. '
    'Do not leave an empty slot. Do not write an em-dash where a figure belongs. '
    'Finish the document: close every tag, include a body, close every script. '
    'You may leave an empty <section id="pns-page-rows"></section> in the body; '
    'the server writes the tables there only if the figures are missing. '
    'If your script draws them, the server keeps a hidden copy there and '
    'shows it only when a script on the page fails. '
    'The prompt says how many rows will replace DATA. The script shows every '
    'row in DATA; do not assume the sample length is the final length. '
    'Every button, filter, chip, tab, search box or other control must work '
    'on the figures of this document: each one changes what shows, and every '
    'element that lists rows follows it. If a control cannot work with these '
    'figures, leave it out; never add one that only looks like it works. '
    'A script only uses elements this document has, and one failing control '
    'must not stop the others. '
    'To hide an element, set its hidden attribute; on screen the page keeps '
    'it hidden whatever display your CSS gives it. '
    'When the prompt names a company, the figures come from its Odoo: show '
    'that name in the page header, unless the instruction says not to or '
    'the figures are not that company\'s own records (a weather forecast, a '
    'web page, a general question). Never write a company name the prompt '
    'does not give. '
    'A value like pns-img:7 is a picture: put it in the src of an <img> '
    'exactly as written; the server swaps it for the picture. '
    'The page already has print and download buttons in the top right '
    'corner; do not add your own and keep that corner clear. '
    'Make the page print: in @media print show every tab panel and hidden '
    'section, and avoid breaking a table row or a card across pages. '
    'Give the page a day theme and a night theme. Write every colour '
    '(text, backgrounds, borders, charts) as a CSS custom property: the day '
    'values on :root, the night values on html[data-theme="dark"]. The '
    'server sets data-theme on the html element before the page shows and '
    'changes it when the user switches; do not add your own switch and do '
    'not set data-theme yourself. A script that draws with colours (a chart, '
    'a canvas) reads them from those properties and draws again when window '
    'fires the pns-theme event. In both themes the text stays readable on '
    'its background.'
)
DESIGN_SYSTEM = (
    'Return one reusable HTML template for a browser tab. '
    'Return only that document. Do not explain it. '
    + _PAGE_RULES
)
EDIT_SYSTEM = (
    'You change an HTML template that is already open in a browser tab. '
    'Answer with the changes only, one block per change, in this form:\n'
    '<<<<<<< FIND\n'
    'text copied exactly from the current page\n'
    '=======\n'
    'the text that takes its place\n'
    '>>>>>>> REPLACE\n'
    'Each FIND must appear exactly once in the current page: copy enough '
    'of it to be unique, and keep it short. To add something, FIND the text '
    'next to where it goes and write it again with the addition. To remove '
    'something, leave the replacement empty. Do not explain the changes. '
    'Only if the change rewrites most of the page, return the whole new '
    'document instead. '
    'New figures, when there are any, come with the instruction, before '
    'the current page. '
    'Read the controls the page already has before you change it. A control '
    'you add joins the same filtering as the ones already there, and every '
    'control that was there still works after your change; if one of them '
    'does not work, fix it or remove it in the same answer. '
    + _PAGE_RULES
)

# The tools float over the frame, whose scrollbar runs under them: the
# right edge leaves room for it plus the gap between the buttons.
_TOOL_STYLE = (
    '{position:fixed;top:12px;right:28px;z-index:2147483647;display:flex;'
    'gap:8px}'
)
_BUTTON_STYLE = (
    '{padding:6px 12px;font:600 13px system-ui,sans-serif;color:#1a1a1a;'
    'background:#f1f3f5;border:1px solid #6c757d;border-radius:6px;'
    'cursor:pointer;text-decoration:none;line-height:1.2;'
    'display:inline-flex;align-items:center;gap:6px}'
)
_BUTTON_ICON_STYLE = (
    '.pns-tool svg,#pns-file-tools button svg{display:block}'
)
_BUTTON_HOVER = '{color:#fff;background:#0d6efd;border-color:#0d6efd}'

# The frame cannot be reached from our page; it prints itself on request.
_PRINT_BRIDGE = (
    '<script id="pns-print-bridge">'
    'window.addEventListener("message",function(e){'
    'if(e.source===window.parent&&e.data==="pns-print"){window.print();}'
    '});</script>'
)

# Day or night is data-theme on the page's html. It is set before the page
# paints, from the system theme; print always goes out in day colours.
_THEME_START = (
    '<script id="pns-theme-start">(function(){var d=document.documentElement;'
    'if(!d.getAttribute("data-theme")){d.setAttribute("data-theme",'
    'window.matchMedia&&window.matchMedia("(prefers-color-scheme: dark)")'
    '.matches?"dark":"light");}})();</script>'
)
_THEME_BRIDGE = (
    '<script id="pns-theme-bridge">(function(){'
    'var d=document.documentElement,kept=null;'
    'function set(t){d.setAttribute("data-theme",t);'
    'try{window.dispatchEvent(new CustomEvent("pns-theme",{detail:t}));}'
    'catch(e){}}'
    'window.pnsTheme=function(){'
    'set(d.getAttribute("data-theme")==="dark"?"light":"dark");};'
    'window.addEventListener("message",function(e){'
    'if(e.source===window.parent&&e.data&&e.data.pnsTheme){'
    'set(e.data.pnsTheme==="dark"?"dark":"light");}});'
    'window.addEventListener("beforeprint",function(){'
    'kept=d.getAttribute("data-theme");if(kept!=="light"){set("light");}});'
    'window.addEventListener("afterprint",function(){'
    'if(kept&&kept!=="light"){set(kept);}kept=null;});'
    '})();</script>'
)
# The frame has no storage of its own (sandbox without same origin): our
# page keeps the choice and tells the frame each time it loads.
_THEME_SCRIPT = (
    '<script id="pns-theme-script">(function(){'
    'var b=document.getElementById("pns-theme");'
    'var f=document.getElementById("pns-frame");if(!b||!f){return;}'
    'var K="pns-canvas-theme",t=null;'
    'try{t=window.localStorage.getItem(K);}catch(e){}'
    'if(t!=="dark"&&t!=="light"){t=window.matchMedia&&'
    'window.matchMedia("(prefers-color-scheme: dark)").matches?"dark":"light";}'
    'function send(){b.setAttribute("aria-pressed",t==="dark"?"true":"false");'
    'if(f.contentWindow){f.contentWindow.postMessage({pnsTheme:t},"*");}}'
    'f.addEventListener("load",send);'
    'b.addEventListener("click",function(){t=t==="dark"?"light":"dark";'
    'try{window.localStorage.setItem(K,t);}catch(e){}send();});'
    'send();})();</script>'
)


# The switch says where a press takes you: by day the moon and "Dark mode",
# by night the sun and "Light mode". Its colours are the other buttons'.
_SVG_OPEN = (
    '<svg viewBox="0 0 24 24" width="14" height="14" fill="none" '
    'stroke="currentColor" stroke-width="2" stroke-linecap="round" '
    'stroke-linejoin="round" aria-hidden="true" focusable="false">'
)
_MOON = _SVG_OPEN + '<path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg>'
_SUN = (
    _SVG_OPEN + '<circle cx="12" cy="12" r="4"/>'
    '<path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41'
    'M2 12h2M20 12h2M4.93 19.07l1.41-1.41M17.66 6.34l1.41-1.41"/></svg>'
)
_SHARE = (
    _SVG_OPEN + '<circle cx="18" cy="5" r="3"/><circle cx="6" cy="12" r="3"/>'
    '<circle cx="18" cy="19" r="3"/><path d="M8.59 13.51l6.83 3.98M15.41 6.51'
    'L8.59 10.49"/></svg>'
)
_PDF = (
    _SVG_OPEN + '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 '
    '2-2V8z"/><path d="M14 2v6h6"/><path d="M8 13h8M8 17h5"/></svg>'
)
_DOWNLOAD = (
    _SVG_OPEN + '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>'
    '<path d="M7 10l5 5 5-5"/><path d="M12 15V3"/></svg>'
)


def _tool_caption(icon, label):
    """Icon plus the button text. The icon is already markup."""
    return icon + html.escape(label)


_THEME_ICON_STYLE = (
    '#pns-theme span{display:inline-flex;align-items:center;gap:6px}'
    '#pns-theme svg{display:block}'
)


def _theme_button(attrs, dark_selector, day_selector):
    """The switch, with the icon and the name of the theme it goes to."""
    return (
        '<style id="pns-theme-icons">' + _THEME_ICON_STYLE
        + dark_selector + ' .pns-to-dark{display:none}'
        + day_selector + ' .pns-to-light{display:none}'
        + '</style>'
        '<button type="button" id="pns-theme" ' + attrs + '>'
        '<span class="pns-to-dark">' + _MOON + html.escape(_('Dark mode')) + '</span>'
        '<span class="pns-to-light">' + _SUN + html.escape(_('Light mode')) + '</span>'
        '</button>'
    )


_STYLE_RE = re.compile(r'<style\b[^>]*>(.*?)</style>', re.I | re.S)
_NIGHT_RULE_RE = re.compile(r'\[\s*data-theme\s*=\s*["\']?dark["\']?\s*\]', re.I)


def has_night_theme(design):
    """True when a style sheet of the page has night colours to switch to."""
    return any(_NIGHT_RULE_RE.search(css) for css in _STYLE_RE.findall(design or ''))


def _with_theme(design):
    if not has_night_theme(design):
        return design
    return _before_body_end(
        _before_every_script(design, _THEME_START), _THEME_BRIDGE,
    )


# A filter hides cards with the hidden attribute; a CSS display on the card
# would beat it and the card would stay. Print keeps Design's own rules.
_HIDDEN_HIDES = (
    '<style id="pns-hidden-hides">'
    '@media screen{html [hidden]{display:none!important}}'
    '</style>'
)


_SHARE_STYLE = (
    '#pns-share-veil{position:fixed;inset:0;z-index:2147483646;'
    'background:rgba(0,0,0,.35)}'
    '#pns-share-veil[hidden]{display:none}'
    '#pns-share-panel{position:fixed;top:52px;right:28px;'
    'z-index:2147483647;width:320px;max-height:70vh;overflow:auto;'
    'padding:12px;background:#fff;border:1px solid #adb5bd;border-radius:8px;'
    'box-shadow:0 6px 24px rgba(0,0,0,.18);font:13px system-ui,sans-serif;'
    'color:#1a1a1a}'
    '#pns-share-panel[hidden]{display:none}'
    '#pns-share-pick[hidden],#pns-share-summary[hidden]{display:none}'
    '.pns-share-head{display:flex;align-items:center;'
    'justify-content:space-between;gap:8px;margin-bottom:8px;'
    'position:sticky;top:0;background:#fff}'
    '.pns-share-title{margin:0;font-weight:700}'
    '#pns-share-panel input{box-sizing:border-box;width:100%;padding:6px 8px;'
    'border:1px solid #adb5bd;border-radius:6px;font:inherit}'
    '#pns-share-found{list-style:none;margin:6px 0;padding:0}'
    '#pns-share-found button{width:100%;text-align:left;padding:5px 8px;'
    'border:0;background:none;font:inherit;cursor:pointer;border-radius:4px}'
    '#pns-share-found button:hover,#pns-share-found button:focus'
    '{background:#e7f1ff}'
    '#pns-share-chosen{display:flex;flex-wrap:wrap;gap:6px;margin:8px 0}'
    '.pns-chip{padding:3px 8px;border:1px solid #0d6efd;border-radius:12px;'
    'background:#e7f1ff;font:inherit;cursor:pointer}'
    '.pns-none{color:#6c757d}'
    '#pns-share-who{margin:0 0 8px;padding-left:18px}'
    '#pns-share-sum-lead{margin:0 0 8px}'
    '#pns-share-row{display:flex;gap:6px;margin-top:8px}'
    '#pns-share-row[hidden]{display:none}'
    '#pns-share-status{margin-top:6px;color:#1a1a1a;font-weight:600}'
)

# Two steps. First you pick people. Share replaces that step with who has
# the page. Close leaves either step. The first Share makes the copy; after
# that the same dialog changes who is on it, so a second press does not
# copy again.
_SHARE_SCRIPT = (
    '<script id="pns-share-script">(function(){'
    'var p=document.getElementById("pns-share-panel");if(!p){return;}'
    'var veil=document.getElementById("pns-share-veil");'
    'var T=JSON.parse(p.getAttribute("data-text"));'
    'var chosen=JSON.parse(p.getAttribute("data-people")||"[]");'
    'var pick=document.getElementById("pns-share-pick");'
    'var summary=document.getElementById("pns-share-summary");'
    'var who=document.getElementById("pns-share-who");'
    'var lead=document.getElementById("pns-share-sum-lead");'
    'var sumTitle=document.getElementById("pns-share-sum-title");'
    'var q=document.getElementById("pns-share-q");'
    'var found=document.getElementById("pns-share-found");'
    'var box=document.getElementById("pns-share-chosen");'
    'var go=document.getElementById("pns-share-go");'
    'var link=document.getElementById("pns-share-link");'
    'var row=document.getElementById("pns-share-row");'
    'var status=document.getElementById("pns-share-status");'
    'var asking=null;'
    'function draw(){box.textContent="";'
    'if(!chosen.length){var e=document.createElement("span");'
    'e.className="pns-none";e.textContent=T.nobody;box.appendChild(e);}'
    'chosen.forEach(function(u){var c=document.createElement("button");'
    'c.type="button";c.className="pns-chip";c.title=T.remove;'
    'c.textContent=u.name+" \\u00d7";'
    'c.addEventListener("click",function(){'
    'chosen=chosen.filter(function(x){return x.id!==u.id;});draw();});'
    'box.appendChild(c);});}'
    'function find(){if(asking){asking.abort();}'
    'asking=new AbortController();'
    'fetch(p.getAttribute("data-find")+"?q="+encodeURIComponent(q.value),'
    '{credentials:"same-origin",signal:asking.signal})'
    '.then(function(r){return r.json();}).then(function(list){'
    'found.textContent="";list.forEach(function(u){'
    'if(chosen.some(function(x){return x.id===u.id;})){return;}'
    'var li=document.createElement("li");'
    'var b=document.createElement("button");b.type="button";'
    'b.textContent=u.name;b.addEventListener("click",function(){'
    'chosen.push(u);q.value="";draw();find();q.focus();});'
    'li.appendChild(b);found.appendChild(li);});})'
    '.catch(function(){});}'
    'function showPick(){summary.hidden=true;pick.hidden=false;}'
    'function closePanel(){p.hidden=true;veil.hidden=true;showPick();'
    'status.textContent="";}'
    'function showSummary(){who.textContent="";'
    'chosen.forEach(function(u){var li=document.createElement("li");'
    'li.textContent=u.name;who.appendChild(li);});'
    'sumTitle.textContent=chosen.length?T.with:T.alone;'
    'who.hidden=!chosen.length;lead.hidden=!chosen.length;'
    'lead.textContent=chosen.length?T.done:"";'
    'pick.hidden=true;summary.hidden=false;status.textContent="";}'
    'q.addEventListener("input",find);'
    'document.getElementById("pns-share").addEventListener("click",function(){'
    'if(!p.hidden){closePanel();return;}'
    'showPick();veil.hidden=false;p.hidden=false;find();q.focus();});'
    'document.getElementById("pns-share-pick-close").addEventListener("click",'
    'closePanel);'
    'document.getElementById("pns-share-sum-close").addEventListener("click",'
    'closePanel);'
    'veil.addEventListener("click",closePanel);'
    'go.addEventListener("click",function(){var f=new FormData();'
    'f.append("csrf_token",p.getAttribute("data-csrf"));'
    'f.append("user_ids",chosen.map(function(u){return u.id;}).join(","));'
    'go.disabled=true;status.textContent="";'
    'fetch(p.getAttribute("data-url"),'
    '{method:"POST",body:f,credentials:"same-origin"})'
    '.then(function(r){if(!r.ok){throw r;}return r.json();})'
    '.then(function(res){go.disabled=false;'
    'p.setAttribute("data-url",res.people_url);'
    'link.value=res.url;row.hidden=false;chosen=res.people;draw();find();'
    'showSummary();})'
    '.catch(function(){go.disabled=false;status.textContent=T.failed;});});'
    'document.getElementById("pns-share-copy").addEventListener("click",'
    'function(){link.select();'
    'if(navigator.clipboard){navigator.clipboard.writeText(link.value);}'
    'else{document.execCommand("copy");}status.textContent=T.copied;});'
    'if(link.value){row.hidden=false;}draw();'
    '})();</script>'
)


def _share_head(title, close_id):
    return (
        '<div class="pns-share-head"><span class="pns-share-title"'
        + (' id="pns-share-sum-title"' if close_id == 'pns-share-sum-close' else '')
        + '>' + html.escape(title) + '</span>'
        '<button type="button" class="pns-tool" id="' + close_id + '">'
        + html.escape(_('Close')) + '</button></div>'
    )


def _share_panel(share_url, people_url, csrf_token, people, link):
    texts = {
        'nobody': _('Nobody yet'),
        'remove': _('Remove'),
        'with': _('Shared with'),
        'done': _('Shared. They have been told in Odoo.'),
        'alone': _('Only you can see it now.'),
        'failed': _('Could not share the page.'),
        'copied': _('Link copied'),
    }
    attr = lambda value: html.escape(value, quote=True)  # noqa: E731
    return (
        '<div id="pns-share-veil" hidden></div>'
        '<div id="pns-share-panel" hidden'
        ' data-url="' + attr(share_url) + '"'
        ' data-find="' + attr(people_url) + '"'
        ' data-csrf="' + attr(csrf_token) + '"'
        ' data-people="' + attr(json.dumps(people or [])) + '"'
        ' data-text="' + attr(json.dumps(texts)) + '">'
        '<div id="pns-share-pick">'
        + _share_head(_('Share'), 'pns-share-pick-close')
        + '<input type="search" id="pns-share-q" autocomplete="off" placeholder="'
        + attr(_('Search people')) + '"/>'
        '<ul id="pns-share-found"></ul>'
        '<div id="pns-share-chosen"></div>'
        '<button type="button" class="pns-tool" id="pns-share-go">'
        + html.escape(_('Share')) + '</button>'
        '</div>'
        '<div id="pns-share-summary" hidden>'
        + _share_head(_('Shared with'), 'pns-share-sum-close')
        + '<ul id="pns-share-who"></ul>'
        '<p id="pns-share-sum-lead"></p>'
        '</div>'
        '<div id="pns-share-row" hidden>'
        '<input type="text" id="pns-share-link" readonly value="'
        + attr(link or '') + '"/>'
        '<button type="button" class="pns-tool" id="pns-share-copy">'
        + html.escape(_('Copy link')) + '</button></div>'
        '<div id="pns-share-status"></div>'
        '</div>'
    )


# Seges: parche 27 (F1, seguridad). Ver docs/pendiente/parches_pns_ai.md
# Added when the page is served, never stored: pages saved before get it too.
_CSP_META = (
    '<meta http-equiv="Content-Security-Policy" content="'
    "default-src 'none'; script-src 'unsafe-inline'; "
    "style-src 'unsafe-inline'; img-src data: blob:; font-src data:; "
    "connect-src 'none'; form-action 'none'; base-uri 'none'; "
    "frame-src 'none'; object-src 'none'; worker-src 'none'"
    '">'
)
# Our own doctype comes first, so the page is in standards mode; the two
# metas right after it open an implied <html> and <head> and are its first
# children. The design follows untouched: its doctype is ignored, and its
# <html> and <head> merge into ours. Nothing of it runs before the policy.
_CSP_PREFIX = '<!DOCTYPE html><meta charset="utf-8">' + _CSP_META


def _with_csp(design):
    """The design served behind our doctype and CSP, from byte 0."""
    return _CSP_PREFIX + (design or '')


def _before_body_end(design, snippet):
    idx = design.lower().rfind('</body>')
    if idx >= 0:
        return design[:idx] + snippet + design[idx:]
    return design + snippet


def downloadable_page(design):
    """The page as a file: it runs without Odoo, so it prints by itself."""
    if not (design or '').strip():
        return design or ''
    buttons = (
        '<style id="pns-print-style">'
        '#pns-file-tools{position:fixed;top:12px;right:12px;'
        'z-index:2147483647;display:flex;gap:8px}'
        + '#pns-file-tools button' + _BUTTON_STYLE
        + '#pns-file-tools button:hover,#pns-file-tools button:focus-visible'
        + _BUTTON_HOVER
        + _BUTTON_ICON_STYLE
        + '@media print{#pns-file-tools{display:none!important}}</style>'
        + '<div id="pns-file-tools">'
        + (
            _theme_button(
                'onclick="window.pnsTheme()"',
                'html[data-theme="dark"] #pns-theme',
                'html:not([data-theme="dark"]) #pns-theme',
            )
            if has_night_theme(design) else ''
        )
        + '<button id="pns-print" type="button" onclick="window.print()">'
        + _tool_caption(_PDF, _('Print / PDF'))
        + '</button></div>'
    )
    # Seges: parche 27 (F1, seguridad). Ver docs/pendiente/parches_pns_ai.md
    return _with_csp(
        _before_body_end(_with_theme(design), _HIDDEN_HIDES + buttons),
    )


_KEBAB_NOISE = re.compile(r'[^a-z0-9]+')
_PAGE_TITLE_RE = re.compile(r'<title>([^<]*)</title>', re.I)
_PAGE_H1_RE = re.compile(r'<h1\b[^>]*>(.*?)</h1>', re.I | re.S)


def _kebab_stem(text):
    text = ' '.join(str(text or '').split())
    if not text:
        return ''
    text = unicodedata.normalize('NFKD', text)
    text = ''.join(ch for ch in text if not unicodedata.combining(ch))
    text = _KEBAB_NOISE.sub('-', text.lower()).strip('-')
    return text[:80]


def _title_in_page(design):
    """Title the document already wrote. Empty if it wrote none."""
    if not design:
        return ''
    match = _PAGE_TITLE_RE.search(design)
    if match:
        return html.unescape(match.group(1)).strip()
    match = _PAGE_H1_RE.search(design)
    if match:
        return html.unescape(re.sub(r'<[^>]+>', '', match.group(1))).strip()
    return ''


def download_filename(title, design=''):
    """Kebab-case file name from the page title. Not a translated UI word."""
    stem = _kebab_stem(title) or _kebab_stem(_title_in_page(design))
    return (stem or 'canvas') + '.html'


def canvas_page(design, title='', download_url='', share_url='', csrf_token='',
                people_url='', people=None, link=''):
    """Our shell. The model's document is the frame, not this page.

    The tab says what the answer was called. No title: Canvas.
    ``allow-modals`` is what lets the frame open the print dialog. The frame
    stays on its own origin, so it still cannot reach the Odoo session.
    The buttons live here, so a page Design laid out cannot hide them.
    Share is two steps: pick names, then a summary of who has the page.
    Close leaves either step. It posts with the CSRF token.
    ``people`` and ``link`` say who already has a shared page and where.
    """
    # Seges: parche 27 (F1, seguridad). Ver docs/pendiente/parches_pns_ai.md
    srcdoc = html.escape(
        _with_csp(_before_body_end(
            _with_theme(design), _HIDDEN_HIDES + _PRINT_BRIDGE,
        ))
        if (design or '').strip() else '',
        quote=True,
    )
    title = html.escape((title or '').strip() or _('Canvas'), quote=True)
    night = has_night_theme(design)
    tools = ''
    if (design or '').strip():
        tools = '<div id="pns-tools">'
        if night:
            tools += _theme_button(
                'class="pns-tool" aria-pressed="false"',
                '#pns-theme[aria-pressed="true"]',
                '#pns-theme[aria-pressed="false"]',
            )
        tools += (
            '<button type="button" class="pns-tool" id="pns-print" '
            'onclick="document.getElementById(\'pns-frame\').contentWindow'
            '.postMessage(\'pns-print\',\'*\')">'
            + _tool_caption(_PDF, _('Print / PDF'))
            + '</button>'
        )
        if download_url:
            tools += (
                '<a class="pns-tool" id="pns-download" download="'
                + html.escape(download_filename(title, design), quote=True)
                + '" href="'
                + html.escape(download_url, quote=True)
                + '">' + _tool_caption(_DOWNLOAD, _('Download HTML')) + '</a>'
            )
        sharing = bool(share_url and csrf_token and people_url)
        if sharing:
            tools += (
                '<button type="button" class="pns-tool" id="pns-share">'
                + _tool_caption(_SHARE, _('Share'))
                + '</button>'
            )
        tools += '</div>'
        if sharing:
            tools += (
                _share_panel(share_url, people_url, csrf_token, people, link)
                + _SHARE_SCRIPT
            )
    return (
        '<!DOCTYPE html><html><head><meta charset="utf-8"><title>'
        + title
        + '</title><style>html,body{margin:0;height:100%;overflow:hidden}'
        'iframe{display:block;border:0;width:100%;height:100%}'
        '#pns-tools' + _TOOL_STYLE
        + '.pns-tool' + _BUTTON_STYLE
        + '.pns-tool:hover,.pns-tool:focus-visible' + _BUTTON_HOVER
        + _BUTTON_ICON_STYLE
        + _SHARE_STYLE
        + '</style></head><body>'
        + tools
        + '<iframe id="pns-frame" sandbox="allow-scripts allow-modals" srcdoc="'
        + srcdoc
        + '"></iframe>'
        + (_THEME_SCRIPT if night else '')
        + '</body></html>'
    )


def strip_fence(text):
    text = (text or '').strip()
    if not text.startswith('```'):
        return text
    lines = text.splitlines()
    lines = lines[1:]
    if lines and lines[-1].strip().startswith('```'):
        lines = lines[:-1]
    return '\n'.join(lines).strip()


def log_no_page(env, reason, session_id=False):
    """Leave the cause in ai.log and answer '' so the turn goes on.

    The user gets a soft notice; whoever can fix it reads the Historial IA.
    The row goes on the same turn thread, in the step where the page was
    asked for: where it sits is what tells you what had already happened.
    """
    _logger.info('Chatboo canvas: %s', reason)
    try:
        from odoo.addons.pns_ai_mcp.models.ai_log import CAPABILITY_SKIPPED
        engine = env['ai.execution.engine']
        turn, turn_step = engine._resolve_log_threading()
        _agent_code, source_channel, client_label = engine._bind_log_identity(
            None, None, None,
        )
        env['ai.log'].sudo()._create_log_entry(
            user_id=env.uid,
            operation_type='read',
            tool_name=CAPABILITY_SKIPPED,
            request_type='LLM',
            result_summary='No page was built: %s' % reason,
            prompt_data={'session_id': session_id or False},
            turn=turn,
            turn_step=turn_step,
            source_channel=source_channel,
            client_label=client_label,
        )
    except Exception:
        _logger.debug('Chatboo canvas: could not log it', exc_info=True)
    return ''


def _session_of_this_turn(sessions):
    """The turn names the session. The page route checks who opens it.

    The id comes from the engine's resolver, the same one the other tools
    use, so a context that lost the key is not fatal. Helpers are published
    with ``sudo()``, which keeps the real uid, so the owner check applies.
    Every way out says why in ``ai.log``.
    """
    from odoo import SUPERUSER_ID
    from odoo.addons.pns_ai_mcp.utils.session_download import resolve_session_ref

    env = sessions.env
    session_id = resolve_session_ref(env)
    try:
        session_id = int(session_id or 0)
    except (TypeError, ValueError):
        session_id = 0
    if not session_id:
        log_no_page(env, 'this turn carries no Chatboo session')
        return sessions.browse()
    session = sessions.sudo().browse(session_id).exists()
    if not session:
        log_no_page(env, 'session %s is gone' % session_id, session_id)
        return sessions.browse()
    uid = env.uid
    if uid and uid != SUPERUSER_ID and session.user_id.id != uid:
        log_no_page(
            env, 'session %s belongs to someone else' % session_id, session_id,
        )
        return sessions.browse()
    return session


IMAGE_TOKEN = 'pns-img:%d'
_IMAGE_TOKEN_RE = re.compile(r'pns-img:(\d+)')
_WEB_IMAGE_RE = re.compile(r'^/web/image/([\w.]+)/(\d+)/(\w+)(?:[/?#].*)?$')
_BASE64_RE = re.compile(r'^[A-Za-z0-9+/=\s]+$')
# What a base64 picture starts with. A PDF or a zip in base64 is not one.
_BASE64_IMAGE_HEADS = (
    ('/9j/', 'image/jpeg'),
    ('iVBOR', 'image/png'),
    ('R0lGOD', 'image/gif'),
    ('UklGR', 'image/webp'),
    ('PHN2Zy', 'image/svg+xml'),
    ('PD94bWwg', 'image/svg+xml'),
)


def _base64_picture(text):
    text = (text or '').strip()
    if len(text) < 64:
        return ''
    for head, mime in _BASE64_IMAGE_HEADS:
        if text.startswith(head) and _BASE64_RE.match(text):
            return 'data:%s;base64,%s' % (mime, ''.join(text.split()))
    return ''


def _web_image_picture(env, url):
    """``/web/image/<model>/<id>/<field>`` read as the user, or ''."""
    match = _WEB_IMAGE_RE.match(url or '')
    if not match or env is None:
        return ''
    model, rec_id, field = match.group(1), int(match.group(2)), match.group(3)
    try:
        if model not in env or field not in env[model]._fields:
            return ''
        if env[model]._fields[field].type not in ('binary', 'image'):
            return ''
        record = env[model].search([('id', '=', rec_id)], limit=1)
        if not record:
            return ''
        value = record[field]
    except Exception:
        _logger.debug('Chatboo canvas: could not read %s', url, exc_info=True)
        return ''
    if isinstance(value, bytes):
        value = value.decode('ascii', 'ignore')
    return _base64_picture(value or '')


def _picture_of(env, value):
    """A data URI when ``value`` is a picture, else ''."""
    if isinstance(value, bytes):
        value = value.decode('ascii', 'ignore')
    if not isinstance(value, str):
        return ''
    if value.startswith('data:image/'):
        # Seges: parche 27 (F1, seguridad). Ver docs/pendiente/parches_pns_ai.md
        return value if _DATA_URI_RE.fullmatch(value) else ''
    if value.startswith('/web/image/'):
        return _web_image_picture(env, value)
    return _base64_picture(value)


def pictures_as_tokens(env, blocks):
    """Blocks Design can read, and the pictures its tokens stand for.

    A photo is 10-20 KB of base64 that Design would have to copy back
    character by character. A token is a dozen.
    """
    images = {}
    out = []
    for block in blocks or []:
        data = []
        for row in block.get('data') or []:
            if not isinstance(row, dict):
                data.append(row)
                continue
            clean = {}
            for key, value in row.items():
                picture = _picture_of(env, value)
                if picture:
                    token = IMAGE_TOKEN % (len(images) + 1)
                    images[token] = picture
                    clean[key] = token
                elif isinstance(value, bytes):
                    continue
                else:
                    clean[key] = value
            data.append(clean)
        out.append(dict(block, data=data))
    return out, images


def swap_pictures(design, images):
    """Put each picture back where Design wrote its token."""
    if not images or not design:
        return design or ''
    return _IMAGE_TOKEN_RE.sub(
        lambda match: images.get(match.group(0), ''), design,
    )


_DATA_URI_RE = re.compile(r'data:image/[\w.+-]+;base64,[A-Za-z0-9+/=]+')


def pictures_out(design, images):
    """The open page with each picture as its token. ``images`` gains them.

    Design changes the same text the server keeps, so a change next to a
    picture still finds its place, and the picture comes back afterwards.
    """
    by_picture = {picture: token for token, picture in images.items()}

    def token_of(match):
        picture = match.group(0)
        token = by_picture.get(picture)
        if not token:
            n = len(images) + 1
            while IMAGE_TOKEN % n in images:
                n += 1
            token = IMAGE_TOKEN % n
            images[token] = picture
            by_picture[picture] = token
        return token

    return _DATA_URI_RE.sub(token_of, design or '')


_EDIT_RE = re.compile(
    r'<{7} FIND\n(.*?)\n={7}\n(.*?)\n?>{7} REPLACE', re.S,
)


def page_edits(text):
    """The FIND / REPLACE pairs of Design's answer, or [] when there are none."""
    return _EDIT_RE.findall((text or '').replace('\r\n', '\n'))


def apply_edits(design, edits):
    """The page with every change, or None if one does not fit exactly once."""
    page = design or ''
    if not edits:
        return None
    for find, replace in edits:
        if not find.strip():
            return None
        if page.count(find) != 1:
            find = find.strip()
            if not find or page.count(find) != 1:
                return None
            replace = replace.strip()
        page = page.replace(find, replace, 1)
    return page


def is_document(text):
    """True when Design answered with a whole page instead of changes."""
    low = (text or '').lower()
    return '<body' in low or '<html' in low or '<!doctype' in low


def figures_for_design(blocks):
    """Every figure as JSON, and how many rows the template will receive."""
    import json

    total = sum(len(block.get('data') or []) for block in blocks)
    try:
        dumped = json.dumps(blocks, ensure_ascii=False, default=str)
    except (TypeError, ValueError):
        dumped = str(blocks)
    return dumped, 'Show all %d rows.' % total


# Enough rows for Design to see the shape. The server replaces DATA
# with the full set; sending every row is what made it bake one button
# per line into the HTML.
_DESIGN_SAMPLE_ROWS = 3


def sample_figures_for_design(blocks):
    """Short sample plus how many rows will replace ``const DATA``."""
    import json

    total = 0
    sample = []
    for block in blocks or []:
        data = list(block.get('data') or [])
        total += len(data)
        keys = []
        for row in data:
            if not isinstance(row, dict):
                continue
            for key in _public_keys(row):
                if key not in keys:
                    keys.append(key)
        sample.append({
            'title': block.get('title') or '',
            'keys': keys,
            'data': data[:_DESIGN_SAMPLE_ROWS],
        })
    try:
        dumped = json.dumps(sample, ensure_ascii=False, default=str)
    except (TypeError, ValueError):
        dumped = str(sample)
    # Seges: parche 29 (P-8e a, seguridad). Ver docs/pendiente/parches_pns_ai.md
    # Design may copy the sample into const DATA: it must not close the script.
    dumped = _script_safe(dumped)
    note = (
        'Show all %d rows: they replace const DATA after you return. '
        'This JSON is a short sample of the shape. '
        'Put the sample or fictional rows with the same keys in const DATA. '
        'The script must render DATA.length, not the sample length.'
    ) % total
    return dumped, note


def page_title(rows, blocks, title=''):
    """The answer's own title, else the first table's. Never invented."""
    candidates = [title]
    if isinstance(rows, dict):
        candidates.append(rows.get('title'))
    candidates.extend(block.get('title') for block in blocks or [])
    for candidate in candidates:
        text = ' '.join(str(candidate or '').split())
        if text:
            return text[:200]
    return ''


def company_name(env):
    """The company the asking user is working in, or '' when there is none."""
    try:
        return ' '.join(str(env.company.name or '').split())
    except Exception:
        return ''


def open_page(sessions, rows, instruction='', new=False, title=''):
    """Url of the page, or '' when there is none. Never raises.

    A page that cannot be laid out is a soft fail, like a geocode miss: the
    turn keeps its rows. The cause is in ``ai.log``, not invented by the
    model.
    """
    session = _session_of_this_turn(sessions)
    if not session:
        return ''
    material = _blocks_for_page(rows)
    if not material:
        try:
            from odoo.addons.pns_ai_mcp.utils.result_page import note_page_waiting
            note_page_waiting(
                sessions.env,
                lambda env, later: open_page(
                    env['chatboo.session'], later, instruction, new=new,
                    title=title,
                ) or '',
            )
        except Exception:
            _logger.debug('Chatboo canvas: could not wait for rows', exc_info=True)
        _logger.info('Chatboo canvas: page waits for rows')
        return ''
    name = page_title(rows, material, title)
    # Seges: parche 26 (M2, seguridad). Ver docs/pendiente/parches_pns_ai.md
    material, images = pictures_as_tokens(sessions.env(su=False), material)
    text = (instruction or '').strip()
    if name:
        text += '\nPage title: ' + name
    company = company_name(sessions.env)
    if company:
        text += '\nCompany: ' + company
    dumped, count_note = sample_figures_for_design(material)
    text = (
        text
        + '\n\n' + count_note
        + '\nSample figures (shape only; the server replaces const DATA):\n'
        + dumped
    ).strip()
    # Seges: parche 25 (M1, seguridad). Ver docs/pendiente/parches_pns_ai.md
    url = session._paint_canvas(
        text, new_page=bool(new) or not session.canvas_open, rows=material,
        title=name, images=images,
    )
    if url and not name:
        _name_it_later(sessions.env, session, url)
    return url


def has_open_page(session):
    """True when ``page_edit`` has a page to change in this session."""
    return bool(session.canvas_open and (session.canvas_design or '').strip())


def edit_page(sessions, instruction, rows=None):
    """Change the open page. Without rows, the figures already on it stay."""
    session = _session_of_this_turn(sessions)
    if not session:
        return ''
    if not has_open_page(session):
        return log_no_page(sessions.env, 'no page is open to change', session.id)
    if _blocks_for_page(rows):
        url = open_page(sessions, rows, instruction, new=False)
    else:
        # Seges: parche 25 (M1, seguridad). Ver docs/pendiente/parches_pns_ai.md
        url = session._paint_canvas(instruction, new_page=False)
    if url:
        try:
            from odoo.addons.pns_ai_mcp.utils.result_page import note_page_wanted
            note_page_wanted(sessions.env)
        except Exception:
            pass
    return url


def _name_it_later(env, session, url):
    """The model names the result after the page is laid out: take that name."""
    try:
        from odoo.addons.pns_ai_mcp.utils.result_page import note_page_untitled
    except Exception:
        return
    path = url.split('?', 1)[0]

    def retitle(_env, href, title):
        if (href or '').split('?', 1)[0].endswith(path):
            session._store_title(title)

    note_page_untitled(env, retitle)


def _blocks_for_page(rows):
    """Titled tables, or one untitled table. Different shapes stay apart."""
    if isinstance(rows, dict):
        try:
            from odoo.addons.pns_ai_mcp.utils.result_page import blocks_on_payload
            blocks = blocks_on_payload(rows)
            if blocks:
                return blocks
        except Exception:
            data = rows.get('data')
            if isinstance(data, list) and data:
                return [{'title': rows.get('title') or rows.get('summary') or '', 'data': list(data)}]
        return []
    if isinstance(rows, (list, tuple)):
        if rows and all(
            isinstance(row, dict) and isinstance(row.get('data'), list)
            for row in rows
        ):
            out = []
            for row in rows:
                if row.get('data'):
                    out.append({
                        'title': row.get('title') or row.get('summary') or '',
                        'data': list(row['data']),
                    })
            return out
        material = [row for row in rows if row or row == 0]
        return [{'title': '', 'data': material}] if material else []
    return []


def _client_cell(value):
    if value is None or isinstance(value, (bool, int, float)):
        return value
    return str(value)


def tables_from_client(tables):
    """The tables a bubble painted, as page blocks. Only scalars survive."""
    out = []
    if not isinstance(tables, list):
        return out
    for table in tables:
        if not isinstance(table, dict) or not isinstance(table.get('rows'), list):
            continue
        data = []
        for row in table['rows']:
            if isinstance(row, dict):
                data.append({
                    str(key): _client_cell(value) for key, value in row.items()
                })
            elif row is None or isinstance(row, (bool, int, float, str)):
                data.append(_client_cell(row))
        if data:
            out.append({
                'title': str(table.get('title') or ''),
                'data': data,
            })
    return out


def _public_keys(row):
    return [
        key for key in row
        if not str(key).startswith('_')
    ]


def _is_picture_token(value):
    return isinstance(value, str) and bool(_IMAGE_TOKEN_RE.fullmatch(value))


def _cell_html(value):
    if _is_picture_token(value):
        return '<td><img src="%s" alt="" style="max-height:64px"></td>' % value
    # Seges: parche 29 (P-8e a, seguridad). Ver docs/pendiente/parches_pns_ai.md
    # Quotes escaped too: a raw " on the page is a value Design copied.
    return '<td>%s</td>' % html.escape(
        '' if value is None else str(value), quote=True,
    )


def _rows_as_table(rows):
    """Visible HTML table of ``rows``. Figures come from the source, not Design."""
    if rows and all(isinstance(row, dict) for row in rows):
        keys = []
        for row in rows:
            for key in _public_keys(row):
                if key not in keys:
                    keys.append(key)
        head = ''.join(
            '<th>%s</th>' % html.escape(str(key)) for key in keys
        )
        body = []
        for row in rows:
            cells = ''.join(_cell_html(row.get(key)) for key in keys)
            body.append('<tr>%s</tr>' % cells)
        return (
            '<table><thead><tr>%s</tr></thead><tbody>%s</tbody></table>'
            % (head, ''.join(body))
        )
    # Seges: parche 29 (P-8e a, seguridad). Ver docs/pendiente/parches_pns_ai.md
    cells = ''.join(
        f'<tr><td>{html.escape(str(row), quote=True)}</td></tr>'
        for row in rows
    )
    return '<table><tbody>%s</tbody></table>' % cells


def _blocks_as_html(blocks):
    parts = []
    for block in blocks:
        title = (block.get('title') or '').strip()
        if title:
            parts.append('<h2>%s</h2>' % html.escape(str(title)))
        parts.append(_rows_as_table(block.get('data') or []))
    return ''.join(parts)


def _page_for_rows(blocks):
    """Complete document the browser can show when Design ships broken HTML."""
    title = ''
    for block in blocks:
        title = (block.get('title') or '').strip()
        if title:
            break
    title = html.escape(title or _('Page'))
    # Seges: parche 27 (F1, seguridad). Ver docs/pendiente/parches_pns_ai.md
    data_js = _script_json(_flat_rows(blocks))
    return (
        '<!DOCTYPE html><html><head><meta charset="utf-8"><title>%s</title>'
        '<style>'
        'body{margin:24px;font:15px/1.45 system-ui,sans-serif;'
        'color:#1b2440;background:#f4f6f9}'
        'h2{margin:1.4em 0 .5em;font-size:1.1rem}'
        'table{border-collapse:collapse;width:100%%;background:#fff;'
        'margin:0 0 1.5em}'
        'th,td{border:1px solid #d5dbe7;padding:.45em .7em;text-align:start}'
        'th{background:#eef1f7}'
        '</style></head><body>'
        '<script>const DATA=%s;</script>'
        '<section id="pns-page-rows">%s</section>'
        '</body></html>'
    ) % (title, data_js, _blocks_as_html(blocks))


def _inside_element(design, idx, tag):
    """True when ``idx`` sits in an unclosed ``<tag>``."""
    text = (design or '').lower()
    needle = '<%s' % tag
    last_open = -1
    pos = 0
    while True:
        found = text.find(needle, pos)
        if found < 0 or found >= idx:
            break
        after = found + len(needle)
        if after >= len(text) or text[after] in ' \t\n\r/>':
            last_open = found
        pos = found + 1
    if last_open < 0:
        return False
    return text.find('</%s>' % tag, last_open, idx) < 0


def _visible_snippet(design, snippet):
    idx = 0
    while True:
        found = (design or '').find(snippet, idx)
        if found < 0:
            return -1
        if not _inside_element(design, found, 'style') and not _inside_element(
            design, found, 'script',
        ):
            return found
        idx = found + 1


def _row_marks(row):
    """Texts that stand for ``row`` on the page. Pictures do not count."""
    if not isinstance(row, dict):
        return [str(row)] if str(row).strip() else []
    marks = []
    for key in _public_keys(row):
        value = row.get(key)
        if value is None or value == '' or isinstance(value, bool):
            continue
        if _is_picture_token(value):
            continue
        marks.append(str(value))
    texts = [mark for mark in marks if not _is_number(mark)]
    return texts or marks


def _is_number(text):
    try:
        float(text)
    except (TypeError, ValueError):
        return False
    return True


def _figure_numbers(blocks):
    """Numeric values of the rows. ``id`` is not a figure."""
    return [
        text for text in _data_texts(blocks)
        if _is_number(text)
    ]


def _data_texts(blocks, title=''):
    """Every value that is data: row fields, block titles, title numbers."""
    texts = []
    for block in blocks or []:
        heading = (block.get('title') or '').strip()
        if heading:
            texts.append(heading)
        for row in block.get('data') or []:
            if not isinstance(row, dict):
                text = str(row).strip()
                if text:
                    texts.append(text)
                continue
            for key in _public_keys(row):
                if str(key).lower() == 'id':
                    continue
                value = row.get(key)
                if value is None or value == '' or isinstance(value, bool):
                    continue
                if _is_picture_token(value):
                    continue
                text = str(value).strip()
                if not text:
                    continue
                if _is_number(text) or len(text) >= 3:
                    texts.append(text)
    for _left, num, _right in _title_number_anchors(title):
        texts.append(num)
    return texts


def _number_in_text(num, text):
    """True when ``num`` stands as its own number, not inside 1000."""
    if not num or not text:
        return False
    alts = {num}
    try:
        number = float(num)
        alts.add(str(number))
        if number == int(number):
            alts.add(str(int(number)))
    except (TypeError, ValueError):
        pass
    for form in alts:
        if re.search(r'(?<![0-9.])%s(?![0-9.])' % re.escape(form), text):
            return True
    return False


def _page_shows_rows(design, blocks, in_scripts=False):
    """True when every row of ``blocks`` is visible HTML.

    Each row is looked up by the text only it has (the plate, the name),
    so ten "Renault" rows are not proved by one "Renault" on the page.
    With ``in_scripts`` a row also counts when only a script carries it.
    """
    def found(form):
        if in_scripts:
            return form in (design or '')
        return _visible_snippet(design, form) >= 0

    for own in _own_marks(blocks):
        # Seges: parche 29 (P-8e a, seguridad). Ver docs/pendiente/parches_pns_ai.md
        if not any(
            found(form)
            for mark in own
            for form in (html.escape(mark, quote=False), html.escape(mark), mark)
        ):
            return False
    return any(_row_marks(row) for block in blocks for row in block.get('data') or [])


def _own_marks(blocks):
    """For each row with text, the marks no other row of its block has."""
    out = []
    for block in blocks:
        rows = block.get('data') or []
        seen = {}
        for row in rows:
            for mark in set(_row_marks(row)):
                seen[mark] = seen.get(mark, 0) + 1
        for row in rows:
            marks = _row_marks(row)
            if marks:
                out.append([mark for mark in marks if seen.get(mark) == 1] or marks)
    return out


# Tags we never rewrite: Design's CSS/JS stay, only visible text follows
# the page title (the slash parameter already landed there).
_CANVAS_CHROME_SKIP_RE = re.compile(
    r'(<script\b[^>]*>.*?</script>)|(<style\b[^>]*>.*?</style>)|(<[^>]+>)',
    re.IGNORECASE | re.DOTALL,
)
_TITLE_COUNT_RE = re.compile(r'(?<![0-9-])(\d+)(?![0-9.])')
_WORD_LEFT_RE = re.compile(r'([^\W\d_]{3,})\s*$', re.UNICODE)
_WORD_RIGHT_RE = re.compile(r'^\s*([^\W\d_]{3,})', re.UNICODE)


def _title_number_anchors(title):
    """Words that sit next to a number in the title. No locale word list."""
    text = title or ''
    anchors = []
    for hit in _TITLE_COUNT_RE.finditer(text):
        left = _WORD_LEFT_RE.search(text[:hit.start()])
        right = _WORD_RIGHT_RE.search(text[hit.end():])
        left_word = left.group(1) if left else ''
        right_word = right.group(1) if right else ''
        if not left_word and not right_word:
            continue
        anchors.append((left_word, hit.group(1), right_word))
    return anchors


def _replace_title_anchor(text, left, num, right):
    """Same words, other number → the title's number."""
    if left and right:
        pattern = re.compile(
            r'(%s)(\s+)(\d+)(\s+)(%s)' % (re.escape(left), re.escape(right)),
        )
        return pattern.sub(
            lambda match: (
                match.group(0) if match.group(3) == num
                else match.group(1) + match.group(2) + num
                + match.group(4) + match.group(5)
            ),
            text,
        )
    if left:
        pattern = re.compile(r'(%s)(\s+)(\d+)\b' % re.escape(left))
        return pattern.sub(
            lambda match: (
                match.group(0) if match.group(3) == num
                else match.group(1) + match.group(2) + num
            ),
            text,
        )
    pattern = re.compile(r'(?<![0-9-])(\d+)(\s+)(%s)' % re.escape(right))
    return pattern.sub(
        lambda match: (
            match.group(0) if match.group(1) == num
            else num + match.group(2) + match.group(3)
        ),
        text,
    )


def sync_canvas_title_phrases(html, title):
    """Copy the title's numbers onto the same phrases in the canvas HTML.

    Design stays free: it paints whatever it wants. The slash already
    named the page (``_page_title``). Visible text that repeats those
    words with another number follows the title. Style, script and
    attributes stay.
    """
    html = html or ''
    title = (title or '').strip()
    if not html or not title:
        return html
    anchors = _title_number_anchors(title)
    if not anchors:
        return html

    def _chunk(text):
        if not text or not any(ch.isdigit() for ch in text):
            return text
        for left, num, right in anchors:
            text = _replace_title_anchor(text, left, num, right)
        return text

    parts = []
    last = 0
    for hit in _CANVAS_CHROME_SKIP_RE.finditer(html):
        parts.append(_chunk(html[last:hit.start()]))
        parts.append(hit.group(0))
        last = hit.end()
    parts.append(_chunk(html[last:]))
    return ''.join(parts)


_SCRIPT_INNER_RE = re.compile(
    r'(<script\b[^>]*>)(.*?)(</script>)', re.IGNORECASE | re.DOTALL,
)


def _row_payloads(blocks):
    """The dict rows of each block, and the public keys they share."""
    out = []
    for block in blocks or []:
        data = [
            row for row in (block.get('data') or [])
            if isinstance(row, dict)
        ]
        if not data:
            continue
        keys = set()
        for row in data:
            keys.update(_public_keys(row))
        if keys:
            out.append((keys, data))
    return out


def _object_arrays_in(text):
    """``[...]`` slices that are a JSON list of objects, outermost only."""
    dec = json.JSONDecoder()
    found = []
    i = 0
    n = len(text or '')
    while i < n:
        if text[i] == '[':
            try:
                val, end = dec.raw_decode(text, i)
            except ValueError:
                i += 1
                continue
            if (
                isinstance(val, list) and val
                and all(isinstance(item, dict) for item in val)
            ):
                found.append((i, end, val))
            i = end
            continue
        i += 1
    return found


def _array_keys(rows):
    keys = set()
    for row in rows:
        if isinstance(row, dict):
            keys.update(_public_keys(row))
    return keys


_CONST_DATA_RE = re.compile(r'\bconst\s+DATA\s*=\s*')


def _flat_rows(blocks):
    rows = []
    for _keys, data in _row_payloads(blocks):
        rows.extend(data)
    return rows


def _payload_for_const_data(old_val, blocks):
    """Same shape Design stored, this run's figures."""
    if (
        isinstance(old_val, list) and old_val
        and all(
            isinstance(item, dict) and isinstance(item.get('data'), list)
            for item in old_val
        )
    ):
        dumped, _note = figures_for_design(blocks)
        # Seges: parche 27 (F1, seguridad). Ver docs/pendiente/parches_pns_ai.md
        return _script_safe(dumped)
    return _script_json(_flat_rows(blocks))


_CONST_TITLE_RE = re.compile(r'\bconst\s+TITLE\s*=\s*')


def bind_const_title(html, title):
    """Replace ``const TITLE = …`` with this run's page title."""
    title = ' '.join(str(title or '').split())
    if not html or not title:
        return html or '', 0
    dec = json.JSONDecoder()
    replaced = [0]
    # Seges: parche 27 (F1, seguridad). Ver docs/pendiente/parches_pns_ai.md
    dumped = _script_json(title)

    def _in_script(inner):
        matches = list(_CONST_TITLE_RE.finditer(inner))
        if not matches:
            return inner
        chunks = []
        last = 0
        for hit in matches:
            start = hit.end()
            try:
                _val, end = dec.raw_decode(inner, start)
            except ValueError:
                continue
            chunks.append(inner[last:start])
            chunks.append(dumped)
            last = end
            replaced[0] += 1
        if not chunks:
            return inner
        chunks.append(inner[last:])
        return ''.join(chunks)

    def _sub(match):
        return match.group(1) + _in_script(match.group(2)) + match.group(3)

    return _SCRIPT_INNER_RE.sub(_sub, html), replaced[0]


def bind_const_data(html, blocks):
    """Replace ``const DATA = …`` with this run's figures. That is the slot."""
    if not html or not _row_payloads(blocks):
        return html or '', 0
    dec = json.JSONDecoder()
    replaced = [0]

    def _in_script(inner):
        matches = list(_CONST_DATA_RE.finditer(inner))
        if not matches:
            return inner
        chunks = []
        last = 0
        for hit in matches:
            start = hit.end()
            try:
                val, end = dec.raw_decode(inner, start)
            except ValueError:
                continue
            chunks.append(inner[last:start])
            chunks.append(_payload_for_const_data(val, blocks))
            last = end
            replaced[0] += 1
        if not chunks:
            return inner
        chunks.append(inner[last:])
        return ''.join(chunks)

    def _sub(match):
        return match.group(1) + _in_script(match.group(2)) + match.group(3)

    return _SCRIPT_INNER_RE.sub(_sub, html), replaced[0]


def _const_data_value(html):
    """The JSON assigned to ``const DATA``, or None if it is missing."""
    dec = json.JSONDecoder()
    for match in _SCRIPT_INNER_RE.finditer(html or ''):
        inner = match.group(2)
        hit = _CONST_DATA_RE.search(inner)
        if not hit:
            continue
        try:
            val, _end = dec.raw_decode(inner, hit.end())
        except ValueError:
            return None
        return val
    return None


# Seges: parche 29 (P-8e a, seguridad). Ver docs/pendiente/parches_pns_ai.md
# Every way a design hands DATA to its script. Only the server writes it.
_DATA_ASSIGN_RE = re.compile(
    r'(?:\b(?:const|let|var)\s+|\bwindow\s*\.\s*)DATA\s*=(?!=)\s*',
)
# ``window.DATA = DATA;`` passes a name on, not figures. Only when nothing
# follows the name: a line break before ``.concat([...])`` is not the end.
_DATA_NAME_RE = re.compile(r'[A-Za-z_$][\w$.]*\s*(?:[;,)]|\Z)')
# A row value with one of these, raw on the page, is markup Design copied.
_MARKUP_UNSAFE = ('<', '>', '"')


def _server_data_values(blocks):
    """What the server writes as DATA for ``blocks``, as plain JSON values."""
    values = [_flat_rows(blocks)]
    values.extend(data for _keys, data in _row_payloads(blocks))
    dumped, _note = figures_for_design(blocks)
    try:
        values.append(json.loads(dumped))
    except ValueError:
        _logger.debug('Chatboo canvas: figures are not JSON', exc_info=True)
    return [
        json.loads(json.dumps(value, ensure_ascii=False, default=str))
        for value in values
    ]


def _model_data_left(page, blocks):
    """True when the page assigns DATA figures the server did not write.

    Read inside each <script> as the server cuts it: a value that closes
    the script leaves JSON that does not parse.
    """
    text = page or ''
    server = _server_data_values(blocks)
    dec = json.JSONDecoder()
    seen = 0
    for match in _SCRIPT_INNER_RE.finditer(text):
        inner = match.group(2)
        for hit in _DATA_ASSIGN_RE.finditer(inner):
            seen += 1
            if _DATA_NAME_RE.match(inner, hit.end()):
                continue
            try:
                val, _end = dec.raw_decode(inner, hit.end())
            except ValueError:
                return True
            if val not in server:
                return True
    return len(_DATA_ASSIGN_RE.findall(text)) > seen


def _markup_values(blocks, title=''):
    """Row values, keys and titles that would be markup if left raw."""
    found = []
    seen = set()

    def walk(value):
        if isinstance(value, dict):
            for key, item in value.items():
                if not str(key).startswith('_'):
                    walk(str(key))
                # Private fields still go to Design's sample and to DATA.
                walk(item)
        elif isinstance(value, (list, tuple)):
            for item in value:
                walk(item)
        elif isinstance(value, str):
            text = value.strip()
            if (
                len(text) >= 3 and text not in seen
                and any(char in text for char in _MARKUP_UNSAFE)
            ):
                seen.add(text)
                found.append(text)

    walk(title or '')
    for block in blocks or []:
        walk(block.get('title') or '')
        walk(block.get('data') or [])
    return found


def _raw_value_left(page, blocks, title=''):
    """The first such value that sits raw in ``page``, or None.

    The server never writes one raw: scripts get ``\\u003c`` and ``\\"``,
    tables get ``&lt;`` and ``&quot;``.
    """
    text = page or ''
    for value in _markup_values(blocks, title):
        forms = [value]
        # Copied into a JS string, " becomes \": look for that form too. It
        # keeps < or > raw, which the server never writes, so no false hit.
        if '<' in value or '>' in value:
            forms.extend(
                json.dumps(value, ensure_ascii=ascii_only)[1:-1]
                for ascii_only in (False, True)
            )
        if any(form in text for form in forms):
            return value
    return None


_VOID_TAGS = frozenset((
    'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input', 'link',
    'meta', 'source', 'track', 'wbr',
))


class _PageRowsText(HTMLParser):
    """Text inside the server's ``#pns-page-rows`` tables, entities decoded."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.depth = 0
        self.texts = []

    def handle_starttag(self, tag, attrs):
        if tag in _VOID_TAGS:
            return
        if self.depth:
            self.depth += 1
        elif dict(attrs).get('id') == 'pns-page-rows':
            self.depth = 1

    def handle_endtag(self, tag):
        if self.depth and tag not in _VOID_TAGS:
            self.depth -= 1

    def handle_data(self, data):
        if self.depth and data.strip():
            self.texts.append(data)


def page_rows_texts(page):
    """The values of the tables the server wrote in ``#pns-page-rows``.

    Only to know what to look for: an empty list means there is nothing to
    check against, never that the page is safe.
    """
    try:
        parser = _PageRowsText()
        parser.feed(page or '')
        parser.close()
    except (AssertionError, NotImplementedError, ValueError):
        _logger.debug('Chatboo canvas: could not read the page rows', exc_info=True)
        return []
    return parser.texts


class _PageMarkupText(_PageRowsText):
    """Text of the whole page, outside scripts and styles, that holds < or >."""

    def handle_starttag(self, tag, attrs):
        if tag in ('script', 'style'):
            self.depth += 1

    def handle_endtag(self, tag):
        if tag in ('script', 'style') and self.depth:
            self.depth -= 1

    def handle_data(self, data):
        if not self.depth and ('<' in data or '>' in data):
            self.texts.append(data)


def page_markup_texts(page):
    """Visible text of ``page`` with < or > once decoded: what an edit must
    not unescape. A change may have moved a value out of ``#pns-page-rows``.
    """
    try:
        parser = _PageMarkupText()
        parser.feed(page or '')
        parser.close()
    except (AssertionError, NotImplementedError, ValueError):
        _logger.debug('Chatboo canvas: could not read the page text', exc_info=True)
        return []
    return parser.texts


def _visible_page_text(html):
    """Text nodes only. Scripts, styles and attributes stay out."""
    parts = []
    last = 0
    for hit in _CANVAS_CHROME_SKIP_RE.finditer(html or ''):
        parts.append(html[last:hit.start()])
        last = hit.end()
    parts.append((html or '')[last:])
    return ' '.join(parts)


def _strip_const_slots(script):
    """Drop ``const DATA`` / ``const TITLE`` JSON. Leftover script is chrome."""
    dec = json.JSONDecoder()
    text = script or ''
    for pattern in (_CONST_DATA_RE, _CONST_TITLE_RE):
        chunks = []
        last = 0
        for hit in pattern.finditer(text):
            start = hit.end()
            try:
                _val, end = dec.raw_decode(text, start)
            except ValueError:
                continue
            chunks.append(text[last:hit.start()])
            last = end
        if chunks:
            chunks.append(text[last:])
            text = ''.join(chunks)
    return text


def _leftover_script_text(html):
    """Script bodies minus DATA, TITLE and the spare-rows watch."""
    parts = []
    for match in _SCRIPT_INNER_RE.finditer(html or ''):
        tag = match.group(1) or ''
        inner = match.group(2) or ''
        if 'pns-page-rows-watch' in tag.lower():
            continue
        parts.append(_strip_const_slots(inner))
    return ' '.join(parts)


# Layout attributes. A data value here is a column class, not a figure.
_LAYOUT_ATTRS = frozenset((
    'class', 'style', 'id', 'src', 'href', 'type', 'hidden', 'role',
    'tabindex', 'width', 'height', 'colspan', 'rowspan', 'for',
    'charset', 'content', 'rel', 'media', 'crossorigin', 'lang',
    'dir', 'spellcheck', 'draggable', 'contenteditable',
    'min', 'max', 'value', 'step', 'low', 'high', 'optimum',
))
_HEX_COLOR_RE = re.compile(r'^#[0-9A-Fa-f]{3,8}$')
_ATTR_VALUE_RE = re.compile(
    r'([^\s=<>/]+)\s*=\s*("[^"]*"|\'[^\']*\')',
)


def _markup_data_attrs(html):
    """Attribute values that can hold a row label (chips, data-*)."""
    values = []
    for hit in re.finditer(r'<[^>]+>', html or ''):
        tag = hit.group(0)
        if tag.startswith('</') or tag.startswith('<!'):
            continue
        low = tag.lower()
        if low.startswith('<script') or low.startswith('<style'):
            continue
        for attr in _ATTR_VALUE_RE.finditer(tag):
            name = attr.group(1).rsplit(':', 1)[-1].lower()
            if name in _LAYOUT_ATTRS:
                continue
            raw = attr.group(2)[1:-1].strip()
            if raw:
                values.append(raw)
    return values


def _is_chrome_literal(text):
    """Slider zeros and CSS colours are not row figures."""
    if not text:
        return True
    if _HEX_COLOR_RE.match(text):
        return True
    if not _is_number(text):
        return False
    try:
        return float(text) == 0
    except (TypeError, ValueError):
        return False


def _text_in_visible(needle, visible):
    """True when a data value stands on its own in the markup."""
    if not needle or not visible:
        return False
    if _is_chrome_literal(needle):
        return False
    if _is_number(needle):
        return _number_in_text(needle, visible)
    if len(needle) < 3:
        return False
    return re.search(
        r'(?<![^\W\d_])%s(?![^\W\d_])' % re.escape(needle),
        visible,
        re.UNICODE,
    ) is not None


def _data_keys(data):
    """Public column names stored in ``const DATA``."""
    keys = set()
    for block_keys, _rows in _row_payloads(_blocks_for_page(_rows_from_const_data(data))):
        keys.update(block_keys)
    return keys


def _data_matches_row_keys(data, blocks):
    """True when DATA uses this run's column names. Values may be a sample."""
    need = set()
    for keys, _rows in _row_payloads(blocks):
        need.update(keys)
    if not need:
        return bool(_rows_from_const_data(data))
    return bool(_data_keys(data) & need)


def _design_label_leaks(html, rows, title=''):
    """Row labels outside ``const DATA``. ``None`` when DATA itself is unusable."""
    blocks = _blocks_for_page(rows)
    literals = list(_data_texts(blocks, title))
    data = _const_data_value(html)
    if blocks:
        if data is None:
            return None
        if not _data_matches_row_keys(data, blocks):
            return None
        literals.extend(
            _data_texts(_blocks_for_page(_rows_from_const_data(data))),
        )
    elif data is not None:
        literals.extend(
            _data_texts(_blocks_for_page(_rows_from_const_data(data))),
        )
    elif not literals:
        return []
    visible = _visible_page_text(html)
    labels = (
        visible
        + ' '
        + ' '.join(_markup_data_attrs(html))
        + ' '
        + _leftover_script_text(html)
    )
    seen = set()
    leaks = []
    for lit in literals:
        if lit in seen or _is_chrome_literal(lit):
            continue
        seen.add(lit)
        haystack = visible if _is_number(lit) else labels
        if _text_in_visible(lit, haystack):
            leaks.append(lit)
    return leaks


def design_figure_leaks(html, rows=None, title=''):
    """Labels that sit outside ``const DATA``. Missing DATA is not a label."""
    faults = _design_label_leaks(html, rows, title)
    return list(faults or [])


def design_figures_centralized(html, rows, title=''):
    """True when Design left every datum only in ``const DATA``.

    Sample or fictional rows in DATA are fine if the keys match. Row
    values, chip labels and title numbers must not sit in the markup
    or in another script: the server always replaces DATA.
    """
    return _design_label_leaks(html, rows, title) == []


def bind_script_row_json(html, blocks):
    """Put this run's rows into ``const DATA``, then any array of those columns.

    Design writes the figures once as ``const DATA``. The next slash
    replaces that assignment. Arrays that already use the same column
    names follow. Returns how many arrays were replaced.
    """
    html, replaced = bind_const_data(html, blocks)
    if replaced:
        return html, replaced
    payloads = _row_payloads(blocks)
    if not html or not payloads:
        return html or '', 0
    count = [0]

    def _in_script(inner):
        chunks = []
        last = 0
        for start, end, arr in _object_arrays_in(inner):
            arr_keys = _array_keys(arr)
            if not arr_keys:
                continue
            need = min(2, len(arr_keys))
            best = None
            best_n = 0
            for keys, data in payloads:
                overlap = len(arr_keys & keys)
                if overlap > best_n:
                    best_n = overlap
                    best = data
            if best is None or best_n < need:
                continue
            chunks.append(inner[last:start])
            # Seges: parche 27 (F1, seguridad). Ver docs/pendiente/parches_pns_ai.md
            chunks.append(_script_json(best))
            last = end
            count[0] += 1
        if not chunks:
            return inner
        chunks.append(inner[last:])
        return ''.join(chunks)

    def _sub(match):
        return match.group(1) + _in_script(match.group(2)) + match.group(3)

    return _SCRIPT_INNER_RE.sub(_sub, html), count[0]


def clear_script_row_json(html):
    """Empty leftover list-of-object arrays in scripts. Not this run's rows."""
    if not html:
        return html

    def _in_script(inner):
        chunks = []
        last = 0
        for start, end, _arr in _object_arrays_in(inner):
            chunks.append(inner[last:start])
            chunks.append('[]')
            last = end
        if not chunks:
            return inner
        chunks.append(inner[last:])
        return ''.join(chunks)

    def _sub(match):
        return match.group(1) + _in_script(match.group(2)) + match.group(3)

    return _SCRIPT_INNER_RE.sub(_sub, html)


def as_page_template(design):
    """The page without that day's tables. The next run brings the figures.

    The empty ``pns-page-rows`` slot is what ``place_rows_on_page`` writes.
    Leftover script arrays and chrome are rebound when the page opens;
    they do not prove that this run's figures are already there.
    """
    design = (design or '').strip()
    if not design:
        return ''
    design = _without_spare_rows(design)
    empty = '<section id="pns-page-rows"></section>'
    filled = _fill_page_rows_slot(design, empty)
    if filled is not None:
        return filled
    idx = design.lower().rfind('</body>')
    if idx >= 0:
        return design[:idx] + empty + design[idx:]
    return design + empty


# Sandbox helpers that ask Design for a page. A captured skill already
# has the HTML; these must not run again.
_DESIGN_PAGE_HELPERS = frozenset(('page_url', 'page_open', 'page_edit'))


def code_touches_page(code):
    """True when the Code calls ``page_url`` / ``page_open`` / ``page_edit`` / ``page_html``."""
    try:
        tree = ast.parse(code or '')
    except SyntaxError:
        return False
    names = _DESIGN_PAGE_HELPERS | {'page_html'}
    return any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id in names
        for node in ast.walk(tree)
    )


def _source_offset(text, lineno, col):
    """Byte offset of ``lineno``/``col`` (1-based line) in ``text``."""
    if lineno < 1:
        return 0
    lines = (text or '').splitlines(True)
    if lineno > len(lines):
        return len(text or '')
    return sum(len(line) for line in lines[:lineno - 1]) + col


def _close_paren(text, open_at):
    """Index of the ``)`` that closes ``text[open_at]``, or ``-1``."""
    return _paren_args(text, open_at)[0]


def _paren_args(text, open_at):
    """``(close, [(start, end), …])``: the ``)`` and each argument's text.

    Text, not ``end_col_offset``: Python 3.7 has no end positions in ``ast``.
    """
    if open_at < 0 or open_at >= len(text or '') or text[open_at] != '(':
        return -1, []
    depth = 0
    i = open_at
    n = len(text)
    cuts = []
    arg_at = open_at + 1
    quote = ''
    triple = False
    while i < n:
        ch = text[i]
        nxt = text[i + 1] if i + 1 < n else ''
        third = text[i + 2] if i + 2 < n else ''
        if quote:
            if ch == '\\' and not triple:
                i += 2
                continue
            if triple and ch == quote[0] and nxt == quote[0] and third == quote[0]:
                quote = ''
                triple = False
                i += 3
                continue
            if not triple and ch == quote:
                quote = ''
            i += 1
            continue
        if ch in ('"', "'"):
            if nxt == ch and third == ch:
                quote = ch * 3
                triple = True
                i += 3
                continue
            quote = ch
            i += 1
            continue
        if ch == '#':
            nl = text.find('\n', i)
            i = n if nl < 0 else nl + 1
            continue
        if ch in '([{':
            depth += 1
        elif ch in ')]}':
            depth -= 1
            if depth == 0:
                cuts.append((arg_at, i))
                return i, [
                    (s, e) for s, e in cuts if text[s:e].strip()
                ]
        elif ch == ',' and depth == 1:
            cuts.append((arg_at, i))
            arg_at = i + 1
        i += 1
    return -1, []


_ROWS_KEYWORD = re.compile(r'\s*rows\s*=(?!=)')


def _page_rows_text(text, call, open_at):
    """Source of the rows handed to ``page_url`` / ``page_open`` / ``page_edit``."""
    _close, args = _paren_args(text, open_at)
    pieces = [text[s:e].strip() for s, e in args]
    for piece in pieces:
        hit = _ROWS_KEYWORD.match(piece)
        if hit:
            return piece[hit.end():].strip()
    pos = 1 if call.func.id == 'page_edit' else 0
    if len(call.args) > pos and len(pieces) > pos:
        return pieces[pos]
    return ''


def without_design_page_calls(code, keep_rows=False):
    """Replace Design-opening helpers with ``''``. The saved page stays.

    ``keep_rows``: the rows that call put on the page go to ``_page_rows``
    first. ``result['data']`` is often a short preview, not the page.
    """
    text = code or ''
    if not text:
        return text
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return text
    holders = {}
    for stmt in ast.walk(tree):
        if not isinstance(stmt, ast.stmt) or hasattr(stmt, 'body'):
            continue
        for sub in ast.walk(stmt):
            if isinstance(sub, ast.Call):
                holders.setdefault(id(sub), stmt)
    spans = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if not isinstance(func, ast.Name) or func.id not in _DESIGN_PAGE_HELPERS:
            continue
        start = _source_offset(text, node.lineno, node.col_offset)
        paren = text.find('(', start)
        end_ln = getattr(node, 'end_lineno', None)
        end_col = getattr(node, 'end_col_offset', None)
        if end_ln is not None and end_col is not None:
            end = _source_offset(text, end_ln, end_col)
        else:
            close = _close_paren(text, paren)
            end = close + 1 if close >= 0 else -1
        if not 0 <= start < end <= len(text):
            continue
        spans.append((start, end, "''"))
        if not keep_rows:
            continue
        expr = _page_rows_text(text, node, paren)
        stmt = holders.get(id(node))
        if not expr or stmt is None:
            continue
        line_at = _source_offset(text, stmt.lineno, 0)
        nl = text.find('\n', line_at)
        line = text[line_at:] if nl < 0 else text[line_at:nl]
        indent = line[:len(line) - len(line.lstrip())]
        spans.append((
            line_at, line_at,
            '%s_page_rows = (%s)\n' % (indent, expr),
        ))
    if not spans:
        return text
    for start, end, piece in sorted(spans, key=lambda s: (s[0], s[1]), reverse=True):
        text = text[:start] + piece + text[end:]
    return text


def _rows_from_const_data(data):
    """The figures stored in ``const DATA``, as rows ``_blocks_for_page`` knows."""
    if (
        isinstance(data, list) and data
        and all(
            isinstance(item, dict) and isinstance(item.get('data'), list)
            for item in data
        )
    ):
        return data
    if isinstance(data, list) and data and all(isinstance(item, dict) for item in data):
        return data
    if isinstance(data, dict) and isinstance(data.get('data'), list):
        return data
    return []


def captured_page_is_reusable(html, rows=None, title=''):
    """True when the stored page can take a later slash's figures.

    The live tables in ``#pns-page-rows`` do not count: they are emptied.
    What remains must have ``const DATA`` and must not copy those figures,
    the title's numbers or chip labels into the visible markup.
    """
    template = as_page_template(html or '')
    if not template:
        return False
    data = _const_data_value(template)
    if data is None:
        return False
    check = rows if _blocks_for_page(rows) else _rows_from_const_data(data)
    if not _blocks_for_page(check):
        return False
    return design_figures_centralized(template, check, title)


def page_from_skill_code(code):
    """The HTML stored as ``_page_template``, or ''."""
    text = code or ''
    if '_page_template' not in text:
        return ''
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return ''
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        names = [
            target.id for target in node.targets
            if isinstance(target, ast.Name)
        ]
        if '_page_template' not in names:
            continue
        value = node.value
        if isinstance(value, ast.Constant) and isinstance(value.value, str):
            return value.value
        if isinstance(value, ast.Str):
            return value.s
    return ''


def wrap_captured_page(code, html, title=''):
    """Keep this run's page. Do not ask Design again.

    Design already painted something worth keeping. The next slash opens
    that same HTML. ``page_html`` writes this run's figures (script
    columns that match, or the tables). Chrome that names the period
    follows ``_page_title``. No new layout.
    """
    if 'page_html(' in (code or ''):
        return without_design_page_calls(code).rstrip()
    code = without_design_page_calls(code or '', keep_rows=True).rstrip()
    html = as_page_template(html)
    if not code or not html:
        return code
    rows = 'result'
    if '_page_rows = (' in code:
        code = '_page_rows = None\n' + code
        rows = '_page_rows if _page_rows is not None else result'
    suffix = (
        '\n\n_page_template = ' + json.dumps(html, ensure_ascii=False)
        + '\n_page_title = ' + json.dumps(title or '', ensure_ascii=False)
        + '\nif result:\n'
        + '    _opened = page_html(_page_template, %s, _page_title)\n' % rows
        + '    if _opened:\n'
        + '        if not isinstance(result, dict):\n'
        + '            result = {"data": result}\n'
        + '        else:\n'
        + '            result = dict(result)\n'
        + '        result["page_url"] = _opened\n'
        + '        if _page_title:\n'
        + '            result["title"] = _page_title\n'
    )
    return code + suffix


# Seges: parche 29 (P-8e a, seguridad). Ver docs/pendiente/parches_pns_ai.md
def place_rows_on_page(design, rows, captured=False, title=''):
    """``_place_rows_on_page``, or the rescue page when that is not safe.

    The rescue page (escaped tables) replaces a design that still assigns
    DATA figures the server did not write, or that has a row value or the
    title with ``<``, ``>`` or ``"`` as raw text.
    """
    page = _place_rows_on_page(design, rows, captured=captured, title=title)
    blocks = _blocks_for_page(rows)
    if not blocks:
        return page
    name = (title or '').strip() or page_title(rows, blocks)
    if _model_data_left(page, blocks):
        reason = 'DATA the server did not write'
    elif _raw_value_left(page, blocks, name) is not None:
        reason = 'a raw row value'
    else:
        return page
    _logger.info('Chatboo canvas: the page kept %s; rescue page', reason)
    return _finish_rescue(_page_for_rows(blocks))


# Seges: parche 29 (P-8e a, seguridad). Ver docs/pendiente/parches_pns_ai.md
def _place_rows_on_page(design, rows, captured=False, title=''):
    """Keep Design's template when DATA can take this run's figures.

    The first turn and a later slash do the same: replace ``const DATA``
    (and ``const TITLE``) and leave the markup alone. Rescue only when
    the document has no body, a script was cut off, or there is no slot.

    A captured skill is yesterday's HTML. Leftover names do not prove
    this run. Script arrays that use the same columns get this run's
    rows; otherwise the tables are the figures.
    """
    blocks = _blocks_for_page(rows)
    design = _strip_unclosed_script(design or '')
    if not blocks:
        return design
    design = _without_spare_rows(design)
    has_body = '<body' in design.lower()
    bound = 0
    if captured:
        name = (title or '').strip() or page_title(rows, blocks)
        design, _title_n = bind_const_title(design, name)
        design, bound = bind_script_row_json(design, blocks)
        if not bound:
            design = clear_script_row_json(design)
    elif _page_shows_rows(design, blocks) and has_body:
        return design
    table = _blocks_as_html(blocks)
    if has_body and (
        (captured and bound)
        or (not captured and _page_shows_rows(design, blocks, in_scripts=True))
    ):
        spare = _keep_spare_rows(design, table, _own_marks(blocks))
        if spare is not None:
            return spare
    block = '<section id="pns-page-rows">%s</section>' % table
    filled = _fill_page_rows_slot(design, block)
    if filled is not None and _page_shows_rows(filled, blocks):
        return _finish_rescue(filled)
    idx = design.lower().rfind('</body>')
    if idx >= 0 and not _inside_element(design, idx, 'style'):
        stitched = design[:idx] + block + design[idx:]
        if _page_shows_rows(stitched, blocks):
            return _finish_rescue(stitched)
    return _finish_rescue(_page_for_rows(blocks))


def _strip_unclosed_script(design):
    """A script cut at max_tokens is a SyntaxError. Drop that tail only."""
    text = design or ''
    low = text.lower()
    start = low.find('<script')
    if start < 0:
        return text
    if low.find('</script>', start) >= 0:
        return text
    return text[:start].rstrip()


def _drop_empty_shells(design):
    """Empty chips/kpis are tabs that Design left for JavaScript."""
    import re
    return re.sub(
        r'<div\b[^>]*\bid=["\'](?:chips|kpis)["\'][^>]*>\s*</div>',
        '',
        design or '',
        flags=re.I,
    )


def _force_rows_visible(design):
    css = (
        '<style id="pns-page-rows-visible">'
        '#pns-page-rows,#pns-page-rows table,#pns-page-rows tbody,'
        '#pns-page-rows tr,#pns-page-rows td,#pns-page-rows th'
        '{display:revert!important;visibility:visible!important;'
        'opacity:1!important;animation:none!important}'
        '</style>'
    )
    idx = (design or '').lower().rfind('</head>')
    if idx >= 0:
        return design[:idx] + css + design[idx:]
    return css + (design or '')


def _finish_rescue(design):
    return _force_rows_visible(_drop_empty_shells(design))


def _fill_page_rows_slot(design, block):
    """Replace Design's empty #pns-page-rows element, or None if it is absent."""
    start = -1
    for quote in ('"', "'"):
        found = design.find('id=%spns-page-rows%s' % (quote, quote))
        if found >= 0:
            start = found
            break
    if start < 0:
        return None
    if _inside_element(design, start, 'style') or _inside_element(
        design, start, 'script',
    ):
        return None
    lt = design.rfind('<', 0, start)
    gt = design.find('>', start)
    if lt < 0 or gt < 0:
        return None
    tag = []
    i = lt + 1
    if i < len(design) and design[i] == '/':
        return None
    while i < start and (design[i].isalnum() or design[i] in '-:_'):
        tag.append(design[i])
        i += 1
    tag = ''.join(tag)
    if not tag:
        return None
    close = '</%s>' % tag
    close_at = design.lower().find(close.lower(), gt)
    if close_at < 0:
        return None
    return design[:lt] + block + design[close_at + len(close):]


def _spare_rows_watch(marks):
    """Script that shows the hidden tables if the page did not draw its rows.

    It runs before every other script so it hears their errors. Errors from
    an <img> or a <link> are not the page breaking; only window errors count.
    After load, every row must have one of its marks in what the page drew
    (scripts, styles and the hidden copy left out), hidden tabs included.
    """
    rows = [[' '.join(mark.split()) for mark in own] for own in marks]
    # Seges: parche 27 (F1, seguridad). Ver docs/pendiente/parches_pns_ai.md
    data = _script_json(rows)
    return (
        '<script id="pns-page-rows-watch">(function(){'
        'var ROWS=%s,broken=false;'
        'function show(){var s=document.getElementById("pns-page-rows");'
        'if(s){s.hidden=false;s.style.setProperty("display","block","important");}}'
        'window.addEventListener("error",function(e){'
        'if(e.target&&e.target!==window)return;broken=true;show();},true);'
        'window.addEventListener("load",function(){'
        'if(broken)return show();'
        'var b=document.body.cloneNode(true);'
        'b.querySelectorAll("script,style,template,#pns-page-rows")'
        '.forEach(function(n){n.remove();});'
        'var t=b.textContent.replace(/\\s+/g," ");'
        'if(ROWS.some(function(r){return !r.some(function(m){'
        'return t.indexOf(m)>=0;});}))show();'
        '});'
        '})();</script>'
    ) % data


def _keep_spare_rows(design, table, marks):
    """Design's page as it is, with ``table`` hidden for when it fails.

    None when there is nowhere to put it; the caller rescues instead.
    """
    section = (
        '<section id="pns-page-rows" hidden style="display:none!important">'
        '%s</section>' % table
    )
    placed = _fill_page_rows_slot(design, section)
    if placed is None:
        idx = design.lower().rfind('</body>')
        if idx < 0 or _inside_element(design, idx, 'style'):
            return None
        placed = design[:idx] + section + design[idx:]
    return _before_every_script(placed, _spare_rows_watch(marks))


def _without_spare_rows(design):
    """The page without a hidden copy left by an earlier pass, slot kept."""
    design = re.sub(
        r'<script id="pns-page-rows-watch">.*?</script>', '', design, flags=re.S,
    )
    return re.sub(
        r'<section id="pns-page-rows" hidden[^>]*>.*?</section>',
        '<section id="pns-page-rows"></section>',
        design,
        flags=re.S,
    )


def _before_every_script(design, script):
    low = design.lower()
    head = low.find('<head>')
    if head < 0:
        head = low.find('<head ')
    if head >= 0 and not _inside_element(design, head, 'script'):
        gt = low.find('>', head)
        return design[:gt + 1] + script + design[gt + 1:]
    first = low.find('<script')
    if first >= 0:
        return design[:first] + script + design[first:]
    return script + design
