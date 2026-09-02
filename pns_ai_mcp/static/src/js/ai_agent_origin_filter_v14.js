odoo.define('pns_ai_mcp.ai_agent_origin_filter', function (require) {
    "use strict";

    var TOKENS = ['native', 'imported', 'pinned', 'extra'];
    var STORE = 'pns_origin_filter_';
    var flagsByAgent = {};

    function tokenOf(btn) {
        var fromData = btn.getAttribute('data-token');
        if (TOKENS.indexOf(fromData) !== -1) {
            return fromData;
        }
        var i;
        for (i = 0; i < TOKENS.length; i++) {
            if (btn.classList.contains('o_pns_tok_' + TOKENS[i])) {
                return TOKENS[i];
            }
        }
        var text = (btn.textContent || '').trim();
        return TOKENS.indexOf(text) !== -1 ? text : '';
    }

    function formRoot(el) {
        return el.closest('.o_form_view') || el.closest('form') || document;
    }

    function agentId(form) {
        var named = form.querySelector('[name="id"]');
        if (named) {
            var input = named.querySelector('input');
            var raw = input ? input.value : named.textContent;
            var n = parseInt(raw, 10);
            if (n) {
                return n;
            }
        }
        var href = window.location.href || '';
        var match = href.match(/(?:[?&#]id=)(\d+)/);
        return match ? parseInt(match[1], 10) : 0;
    }

    function flagsFromFields(form) {
        var flags = {native: true, imported: true, pinned: true, extra: true};
        TOKENS.forEach(function (token) {
            var el = form.querySelector('[name="link_show_' + token + '"]');
            if (!el) {
                return;
            }
            var input = el.querySelector('input[type="checkbox"]');
            if (input) {
                flags[token] = input.checked;
            }
        });
        return flags;
    }

    function flagsFromStore(id) {
        if (!id || !window.sessionStorage) {
            return null;
        }
        try {
            var raw = sessionStorage.getItem(STORE + id);
            return raw ? JSON.parse(raw) : null;
        } catch (e) {
            return null;
        }
    }

    function rememberFlags(id, flags) {
        if (!id) {
            return;
        }
        flagsByAgent[id] = flags;
        try {
            sessionStorage.setItem(STORE + id, JSON.stringify(flags));
        } catch (e) {
            /* private mode */
        }
    }

    function originFromRow(row) {
        var cell = row.querySelector(
            '[name="composition_origin"], [data-name="composition_origin"]',
        );
        if (cell) {
            return (cell.textContent || '').trim();
        }
        var tds = row.querySelectorAll('td');
        var i;
        for (i = 0; i < tds.length; i++) {
            var text = (tds[i].textContent || '').trim();
            if (TOKENS.indexOf(text) !== -1) {
                return text;
            }
        }
        return '';
    }

    function listBox(el) {
        return (
            el.closest('.o_field_x2many') ||
            el.closest('.o_field_one2many') ||
            el.closest('.o_field_many2many') ||
            el.closest('.o_list_view')
        );
    }

    function fieldNameOf(box) {
        var el = box;
        while (el) {
            var name = el.getAttribute && el.getAttribute('name');
            if (name === 'context_ids' || name === 'skill_ids') {
                return name;
            }
            el = el.parentElement;
        }
        return 'x2m';
    }

    function originHeader(box) {
        var named;
        var cell;
        var td;
        var row;
        var idx;
        if (!box) {
            return null;
        }
        named = box.querySelector(
            'th[data-name="composition_origin"], th[data-id="composition_origin"]',
        );
        if (named) {
            return named;
        }
        cell = box.querySelector(
            '[name="composition_origin"], [data-name="composition_origin"]',
        );
        if (!cell) {
            return null;
        }
        td = cell.closest('td') || cell;
        row = td.parentElement;
        if (!row) {
            return null;
        }
        idx = Array.prototype.indexOf.call(row.children, td);
        if (idx < 0) {
            return null;
        }
        return box.querySelectorAll('thead th')[idx] || null;
    }

    function rankOf(token) {
        var i = TOKENS.indexOf(token);
        return i === -1 ? 9 : i;
    }

    function sortStoreKey(box) {
        var href = window.location.href || '';
        var match = href.match(/(?:[?&#]id=)(\d+)/);
        var id = match ? match[1] : String(agentId(formRoot(box)) || '0');
        return STORE + 'sort_' + id + '_' + fieldNameOf(box);
    }

    function sortDirForBox(box) {
        var raw;
        if (!box) {
            return 'asc';
        }
        if (box.getAttribute('data-pns-origin-sort') === 'desc' ||
                box.getAttribute('data-pns-origin-sort') === 'asc') {
            return box.getAttribute('data-pns-origin-sort');
        }
        try {
            raw = sessionStorage.getItem(sortStoreKey(box));
            if (raw === 'desc' || raw === 'asc') {
                box.setAttribute('data-pns-origin-sort', raw);
                return raw;
            }
        } catch (e) {
            /* private mode */
        }
        return 'asc';
    }

    function rememberSortBox(box, dir) {
        if (!box) {
            return;
        }
        box.setAttribute('data-pns-origin-sort', dir);
        try {
            sessionStorage.setItem(sortStoreKey(box), dir);
        } catch (e) {
            /* private mode */
        }
    }

    function sortOriginRows(box, dir) {
        var tbody = box.querySelector('tbody');
        if (!tbody) {
            return;
        }
        var rows = Array.prototype.slice.call(
            tbody.querySelectorAll('tr.o_data_row, tr[data-id]'),
        );
        var desc = dir === 'desc';
        rows.sort(function (a, b) {
            var da = rankOf(originFromRow(a));
            var db = rankOf(originFromRow(b));
            return desc ? db - da : da - db;
        });
        rows.forEach(function (row) {
            tbody.appendChild(row);
        });
        var th = originHeader(box);
        if (th) {
            th.classList.add('o_pns_origin_sortable');
            th.setAttribute('aria-sort', desc ? 'descending' : 'ascending');
        }
    }

    function shownSet(flags) {
        var on = TOKENS.filter(function (token) {
            return flags[token];
        });
        return on.length ? on : TOKENS;
    }

    function scroller() {
        return document.querySelector('.o_content') || document.scrollingElement;
    }

    function keepListHeight(box, before) {
        var after = box.getBoundingClientRect().height;
        var prev = parseFloat(box.getAttribute('data-pns-min-height') || '0') || 0;
        var keep = Math.max(before, after, prev);
        box.setAttribute('data-pns-min-height', String(keep));
        box.style.minHeight = keep + 'px';
    }

    function paintOriginFilter(root, flags, lockHeight) {
        if (!root) {
            return;
        }
        var shown = shownSet(flags);
        root.querySelectorAll('.o_pns_origin_filter').forEach(function (btn) {
            var on = shown.indexOf(tokenOf(btn)) !== -1;
            btn.classList.toggle('btn-primary', on);
            btn.classList.toggle('btn-secondary', !on);
        });
        root.querySelectorAll('.o_field_x2many').forEach(function (box) {
            var rows = box.querySelectorAll('tbody tr[data-id], tbody tr.o_data_row');
            var hasOrigin = false;
            rows.forEach(function (row) {
                if (TOKENS.indexOf(originFromRow(row)) !== -1) {
                    hasOrigin = true;
                }
            });
            if (!hasOrigin) {
                return;
            }
            var before = lockHeight ? box.getBoundingClientRect().height : 0;
            rows.forEach(function (row) {
                var origin = originFromRow(row);
                row.classList.toggle(
                    'o_pns_origin_hidden',
                    Boolean(origin) && shown.indexOf(origin) === -1,
                );
            });
            if (lockHeight) {
                keepListHeight(box, before);
            }
            sortOriginRows(box, sortDirForBox(box));
        });
    }

    function flagsFor(form) {
        var id = agentId(form);
        if (id && flagsByAgent[id]) {
            return flagsByAgent[id];
        }
        var stored = flagsFromStore(id);
        if (stored) {
            flagsByAgent[id] = stored;
            return stored;
        }
        var flags = flagsFromFields(form);
        if (id) {
            flagsByAgent[id] = flags;
        }
        return flags;
    }

    function paintVisibleForms() {
        document.querySelectorAll('.o_form_view').forEach(function (form) {
            if (!form.querySelector('.o_pns_origin_filter_bar')) {
                return;
            }
            paintOriginFilter(form, flagsFor(form), false);
        });
    }

    document.addEventListener('click', function (ev) {
        var closest = ev.target.closest && ev.target.closest.bind(ev.target);
        var th = closest ? closest('th') : null;
        var box = th ? listBox(th) : null;
        var originTh = originHeader(box);
        if (th && originTh && th === originTh) {
            var formTh = formRoot(th);
            if (!formTh.querySelector('.o_pns_origin_filter_bar')) {
                return;
            }
            ev.preventDefault();
            ev.stopPropagation();
            if (ev.stopImmediatePropagation) {
                ev.stopImmediatePropagation();
            }
            var next = sortDirForBox(box) === 'asc' ? 'desc' : 'asc';
            rememberSortBox(box, next);
            sortOriginRows(box, next);
            return;
        }
        var btn = closest ? closest('.o_pns_origin_filter') : null;
        if (!btn) {
            return;
        }
        ev.preventDefault();
        ev.stopPropagation();
        var token = tokenOf(btn);
        if (TOKENS.indexOf(token) === -1) {
            return;
        }
        var form = formRoot(btn);
        var id = agentId(form);
        var flags = Object.assign({}, flagsFor(form));
        flags[token] = !flags[token];
        rememberFlags(id, flags);
        var el = scroller();
        var y = el ? el.scrollTop : 0;
        var x = el ? el.scrollLeft : 0;
        paintOriginFilter(form, flags, true);
        if (el) {
            el.scrollTop = y;
            el.scrollLeft = x;
        }
    }, true);

    var observer = new MutationObserver(function () {
        window.clearTimeout(paintVisibleForms._t);
        paintVisibleForms._t = window.setTimeout(paintVisibleForms, 50);
    });
    observer.observe(document.documentElement, {childList: true, subtree: true});

    return {};
});
