/** @odoo-module **/
/**
 * Origin toggles on the agent form. Pure client filter: no write to the
 * open record (that remounts the form) and the list keeps its height so
 * hiding rows does not yank the sheet upward.
 */
const TOKENS = ["native", "imported", "pinned", "extra"];
const STORE = "pns_origin_filter_";
const flagsByAgent = {};

function tokenOf(btn) {
    const fromData = btn.getAttribute("data-token") || btn.dataset.token;
    if (TOKENS.includes(fromData)) {
        return fromData;
    }
    for (const token of TOKENS) {
        if (btn.classList.contains("o_pns_tok_" + token)) {
            return token;
        }
    }
    const text = (btn.textContent || "").trim();
    return TOKENS.includes(text) ? text : "";
}

function formRoot(el) {
    return (
        el.closest(".o_form_view") ||
        el.closest(".o_form_renderer") ||
        el.closest("form") ||
        document
    );
}

function agentId(form) {
    const named = form.querySelector('[name="id"]');
    if (named) {
        const input = named.querySelector("input");
        const raw = input ? input.value : named.textContent;
        const n = parseInt(raw, 10);
        if (n) {
            return n;
        }
    }
    const href = window.location.href || "";
    const match = href.match(/(?:[?&#]id=|ai\.agent\/)(\d+)/);
    return match ? parseInt(match[1], 10) : 0;
}

function flagsFromFields(form) {
    const flags = {native: true, imported: true, pinned: true, extra: true};
    for (const token of TOKENS) {
        const el = form.querySelector('[name="link_show_' + token + '"]');
        if (!el) {
            continue;
        }
        const input = el.querySelector('input[type="checkbox"]');
        if (input) {
            flags[token] = input.checked;
        }
    }
    return flags;
}

function flagsFromStore(id) {
    if (!id) {
        return null;
    }
    try {
        const raw = sessionStorage.getItem(STORE + id);
        return raw ? JSON.parse(raw) : null;
    } catch {
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
    } catch {
        /* private mode */
    }
}

function originFromRow(row) {
    const cell = row.querySelector(
        '[name="composition_origin"], [data-name="composition_origin"]',
    );
    if (cell) {
        return (cell.textContent || "").trim();
    }
    for (const td of row.querySelectorAll("td, .o_data_cell")) {
        const text = (td.textContent || "").trim();
        if (TOKENS.includes(text)) {
            return text;
        }
    }
    return "";
}

function listBox(el) {
    return (
        el.closest(".o_field_x2many") ||
        el.closest(".o_field_one2many") ||
        el.closest(".o_field_many2many") ||
        el.closest(".o_list_renderer")
    );
}

function fieldNameOf(box) {
    let el = box;
    while (el) {
        const name = el.getAttribute && el.getAttribute("name");
        if (name === "context_ids" || name === "skill_ids") {
            return name;
        }
        el = el.parentElement;
    }
    return "x2m";
}

function originHeader(box) {
    if (!box) {
        return null;
    }
    const named = box.querySelector(
        'th[data-name="composition_origin"], th[data-id="composition_origin"]',
    );
    if (named) {
        return named;
    }
    const cell = box.querySelector(
        '[name="composition_origin"], [data-name="composition_origin"]',
    );
    if (!cell) {
        return null;
    }
    const td = cell.closest("td") || cell;
    const row = td.parentElement;
    if (!row) {
        return null;
    }
    const idx = Array.prototype.indexOf.call(row.children, td);
    if (idx < 0) {
        return null;
    }
    return box.querySelectorAll("thead th")[idx] || null;
}

function rankOf(token) {
    const i = TOKENS.indexOf(token);
    return i === -1 ? 9 : i;
}

function sortStoreKey(box) {
    const href = window.location.href || "";
    const match = href.match(/(?:[?&#]id=|ai\.agent\/)(\d+)/);
    const id = match ? match[1] : String(agentId(formRoot(box)) || "0");
    return STORE + "sort_" + id + "_" + fieldNameOf(box);
}

function sortDirForBox(box) {
    if (!box) {
        return "asc";
    }
    const local = box.dataset.pnsOriginSort;
    if (local === "desc" || local === "asc") {
        return local;
    }
    try {
        const raw = sessionStorage.getItem(sortStoreKey(box));
        if (raw === "desc" || raw === "asc") {
            box.dataset.pnsOriginSort = raw;
            return raw;
        }
    } catch {
        /* private mode */
    }
    return "asc";
}

function rememberSortBox(box, dir) {
    if (!box) {
        return;
    }
    box.dataset.pnsOriginSort = dir;
    try {
        sessionStorage.setItem(sortStoreKey(box), dir);
    } catch {
        /* private mode */
    }
}

function sortOriginRows(box, dir) {
    const tbody = box.querySelector("tbody");
    if (!tbody) {
        return;
    }
    const rows = Array.from(
        tbody.querySelectorAll("tr.o_data_row, tr[data-id]"),
    );
    const desc = dir === "desc";
    rows.sort((a, b) => {
        const da = rankOf(originFromRow(a));
        const db = rankOf(originFromRow(b));
        return desc ? db - da : da - db;
    });
    rows.forEach((row) => tbody.appendChild(row));
    const th = originHeader(box);
    if (th) {
        th.classList.add("o_pns_origin_sortable");
        th.setAttribute("aria-sort", desc ? "descending" : "ascending");
    }
}

function shownSet(flags) {
    const on = TOKENS.filter((token) => flags[token]);
    return new Set(on.length ? on : TOKENS);
}

function scroller() {
    return (
        document.querySelector(".o_action_manager .o_content") ||
        document.querySelector(".o_content") ||
        document.scrollingElement
    );
}

function keepListHeight(box, before) {
    const after = box.getBoundingClientRect().height;
    const prev = parseFloat(box.dataset.pnsMinHeight || "0") || 0;
    const keep = Math.max(before, after, prev);
    box.dataset.pnsMinHeight = String(keep);
    box.style.minHeight = keep + "px";
}

function paintOriginFilter(root, flags, lockHeight) {
    if (!root) {
        return;
    }
    const shown = shownSet(flags);
    root.querySelectorAll(".o_pns_origin_filter").forEach((btn) => {
        const on = shown.has(tokenOf(btn));
        btn.classList.toggle("btn-primary", on);
        btn.classList.toggle("btn-secondary", !on);
    });
    root.querySelectorAll(".o_field_x2many").forEach((box) => {
        const rows = box.querySelectorAll("tbody tr.o_data_row, tbody tr[data-id]");
        let hasOrigin = false;
        rows.forEach((row) => {
            if (TOKENS.includes(originFromRow(row))) {
                hasOrigin = true;
            }
        });
        if (!hasOrigin) {
            return;
        }
        const before = lockHeight ? box.getBoundingClientRect().height : 0;
        rows.forEach((row) => {
            const origin = originFromRow(row);
            row.classList.toggle(
                "o_pns_origin_hidden",
                Boolean(origin) && !shown.has(origin),
            );
        });
        if (lockHeight) {
            keepListHeight(box, before);
        }
        sortOriginRows(box, sortDirForBox(box));
    });
}

function flagsFor(form) {
    const id = agentId(form);
    if (id && flagsByAgent[id]) {
        return flagsByAgent[id];
    }
    const stored = flagsFromStore(id);
    if (stored) {
        flagsByAgent[id] = stored;
        return stored;
    }
    const flags = flagsFromFields(form);
    if (id) {
        flagsByAgent[id] = flags;
    }
    return flags;
}

function paintVisibleForms() {
    document.querySelectorAll(".o_form_view, .o_form_renderer").forEach((form) => {
        if (!form.querySelector(".o_pns_origin_filter_bar")) {
            return;
        }
        paintOriginFilter(form, flagsFor(form), false);
    });
}

document.addEventListener(
    "click",
    function (ev) {
        const th = ev.target.closest("th");
        const box = th ? listBox(th) : null;
        const originTh = originHeader(box);
        if (th && originTh && th === originTh) {
            const form = formRoot(th);
            if (!form.querySelector(".o_pns_origin_filter_bar")) {
                return;
            }
            ev.preventDefault();
            ev.stopPropagation();
            ev.stopImmediatePropagation();
            const next = sortDirForBox(box) === "asc" ? "desc" : "asc";
            rememberSortBox(box, next);
            sortOriginRows(box, next);
            return;
        }
        const btn = ev.target.closest(".o_pns_origin_filter");
        if (!btn) {
            return;
        }
        ev.preventDefault();
        ev.stopPropagation();
        const token = tokenOf(btn);
        if (!TOKENS.includes(token)) {
            return;
        }
        const form = formRoot(btn);
        const id = agentId(form);
        const flags = Object.assign({}, flagsFor(form));
        flags[token] = !flags[token];
        rememberFlags(id, flags);
        const el = scroller();
        const y = el ? el.scrollTop : 0;
        const x = el ? el.scrollLeft : 0;
        paintOriginFilter(form, flags, true);
        if (el) {
            el.scrollTop = y;
            el.scrollLeft = x;
        }
    },
    true,
);

const observer = new MutationObserver(function () {
    window.clearTimeout(paintVisibleForms._t);
    paintVisibleForms._t = window.setTimeout(paintVisibleForms, 50);
});
observer.observe(document.documentElement, {childList: true, subtree: true});
