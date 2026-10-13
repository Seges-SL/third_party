/* SPDX-License-Identifier: Apache-2.0 */
/* Copyright (C) 2026 Patanegra Soft <https://patanegra.com> */
/**
 * Chatboo PDF viewer — a PDF of the chat opens over the conversation.
 *
 * Odoo ships pdf.js (/web/static/lib/pdfjs, the viewer of the chatter);
 * this layer only frames it full screen with a tab button and a close.
 * Escape, the close button or a click beside the PDF closes it.
 *
 *   window.chatbooPdfViewer.optionsFor(node)  // {pdf, tab, alt} of a PDF link, or null
 *   window.chatbooPdfViewer.open({ pdf, tab, alt })
 *   window.chatbooPdfViewer.close()
 *   window.chatbooPdfViewer.isOpen()
 *
 * A link is a PDF when it says so: type="application/pdf", or a path or a
 * download name ending in .pdf. pdf.js only reads this site, so a PDF of
 * another site keeps opening in a tab.
 *
 * Plain script: the same file serves both UI stacks.
 */
(function (global) {
    "use strict";

    var PDF_VIEWER = "/web/static/lib/pdfjs/web/viewer.html?file=";
    var root = null;
    var frame = null;
    var tabButton = null;
    var current = null;

    function sameOrigin(href) {
        try {
            return new URL(href, global.location.href).origin === global.location.origin;
        } catch (e) {
            return false;
        }
    }

    function isPdfLink(link) {
        var cls = (link.className || "") + "";
        if (cls.indexOf("o_chatboo_file_banner_pdf") !== -1) {
            return true;
        }
        if ((link.getAttribute("type") || "").toLowerCase().split(";")[0].trim() === "application/pdf") {
            return true;
        }
        if (/\.pdf$/i.test((link.getAttribute("download") || "").trim())) {
            return true;
        }
        try {
            return /\.pdf$/i.test(new URL(link.href, global.location.href).pathname);
        } catch (e) {
            return false;
        }
    }

    function optionsFor(target) {
        var link = target && target.closest ? target.closest("a[href]") : null;
        if (!link || !isPdfLink(link)) {
            return null;
        }
        var href = link.href;
        if (!sameOrigin(href) && !/^blob:/i.test(href) && !/^data:application\/pdf/i.test(href)) {
            return null;
        }
        return {
            pdf: href,
            tab: href,
            alt: link.getAttribute("title") || (link.textContent || "").trim(),
        };
    }

    function onKey(ev) {
        if (ev.key === "Escape" || ev.key === "Esc") {
            ev.preventDefault();
            ev.stopPropagation();
            close();
        }
    }

    function onFrameLoad() {
        try {
            frame.contentWindow.addEventListener("keydown", onKey, true);
        } catch (e) { /* Escape still works once focus leaves the frame */ }
    }

    function button(cls, glyph, act) {
        var b = document.createElement("button");
        b.type = "button";
        b.className = cls;
        b.textContent = glyph;
        b.addEventListener("click", function (ev) {
            ev.preventDefault();
            ev.stopPropagation();
            act();
        });
        return b;
    }

    function openTab() {
        if (current && current.tab) {
            global.open(current.tab, "_blank", "noopener");
        }
    }

    function build() {
        root = document.createElement("div");
        root.className = "o_chatboo_pdf_viewer";
        root.hidden = true;
        frame = document.createElement("iframe");
        frame.className = "o_chatboo_pdf_viewer_frame";
        frame.addEventListener("load", onFrameLoad);
        var bar = document.createElement("div");
        bar.className = "o_chatboo_pdf_viewer_bar";
        tabButton = button("o_chatboo_pdf_viewer_tab", "\u2197", openTab);
        bar.appendChild(tabButton);
        bar.appendChild(button("o_chatboo_pdf_viewer_close", "\u2715", close));
        root.appendChild(frame);
        root.appendChild(bar);
        root.addEventListener("click", function (ev) {
            if (ev.target === root) {
                close();
            }
        });
        document.body.appendChild(root);
    }

    function open(opts) {
        if (!opts || !opts.pdf) {
            return;
        }
        if (!root) {
            build();
        }
        current = { tab: opts.tab || "" };
        frame.title = opts.alt || "";
        frame.src = PDF_VIEWER + encodeURIComponent(opts.pdf);
        tabButton.hidden = !current.tab;
        root.hidden = false;
        document.addEventListener("keydown", onKey, true);
    }

    function close() {
        if (!current) {
            return;
        }
        current = null;
        root.hidden = true;
        frame.removeAttribute("src");
        document.removeEventListener("keydown", onKey, true);
    }

    function isOpen() {
        return !!current;
    }

    global.chatbooPdfViewer = { optionsFor: optionsFor, open: open, close: close, isOpen: isOpen };
})(window);
