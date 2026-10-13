/* SPDX-License-Identifier: Apache-2.0 */
/* Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com> */
/**
 * Chatboo row marks — point at a row instead of spelling the name again.
 *
 * A table row that links a record answers "which one?" by itself. Clicking
 * the row (not the link, which still opens Odoo) marks it; the next message
 * carries {model, id, label} so the engine takes those records as its
 * subject. Marks are spent by the sentence that carries them.
 *
 * Plain script: the same file serves both UI stacks. No copy of its own —
 * what a mark is for is said by the turn that puts the table on screen.
 */
(function (global) {
    "use strict";

    var ROW_SELECTOR = "table.o_chatboo_data_table tbody tr";
    var LINK_SELECTOR = "a.o_chatboo_namelink[href*='/web#']";
    var NO_MARK = "a, button, input, select, textarea, label";

    // key -> {model, id, label, row}
    var marked = new Map();

    /** The record a row points at, read from the Odoo deep link it carries. */
    function rowRecord(row) {
        var link = row.querySelector(LINK_SELECTOR);
        if (!link) {
            return null;
        }
        var hash = (link.getAttribute("href") || "").split("#")[1] || "";
        var params = new URLSearchParams(hash);
        var id = parseInt(params.get("id"), 10);
        var model = params.get("model") || "";
        if (!model || !(id > 0)) {
            return null;
        }
        return {
            model: model,
            id: id,
            label: (link.textContent || "").trim(),
        };
    }

    function toggle(row) {
        var rec = rowRecord(row);
        if (!rec) {
            return;
        }
        var key = rec.model + ":" + rec.id;
        if (marked.has(key)) {
            marked.delete(key);
            row.classList.remove("o_chatboo_marked");
            return;
        }
        rec.row = row;
        marked.set(key, rec);
        row.classList.add("o_chatboo_marked");
    }

    function onClick(ev) {
        var target = ev.target;
        if (!target || !target.closest) {
            return;
        }
        if (target.closest(NO_MARK)) {
            return;  // the link still opens the record
        }
        var row = target.closest(ROW_SELECTOR);
        if (!row) {
            return;
        }
        var selection = global.getSelection && global.getSelection();
        if (selection && String(selection).trim()) {
            return;  // the user is copying a cell, not picking a row
        }
        toggle(row);
    }

    function forget() {
        marked.forEach(function (rec) {
            if (rec.row && rec.row.classList) {
                rec.row.classList.remove("o_chatboo_marked");
            }
        });
        marked.clear();
    }

    /**
     * The marks to send with this message, and they are spent.
     *
     * A row that left the screen (new session, answer redrawn) is not a pick
     * any more: the user cannot see it, so it does not narrow anything.
     */
    function take() {
        var refs = [];
        marked.forEach(function (rec) {
            if (rec.row && rec.row.isConnected) {
                refs.push({
                    model: rec.model,
                    id: rec.id,
                    label: rec.label,
                });
            }
        });
        forget();
        return refs;
    }

    if (global.document && !global.ChatbooRowMarks) {
        global.document.addEventListener("click", onClick, true);
    }

    global.ChatbooRowMarks = {
        take: take,
        clear: forget,
        count: function () {
            return marked.size;
        },
    };
})(typeof window !== "undefined" ? window : this);
