/* SPDX-License-Identifier: Apache-2.0 */
/* Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com> */
/**
 * Chatboo wide-card width — ratio of the messages canvas.
 * Persistence is the Odoo user row (RPC), not localStorage.
 * Viewport/device wins over the stored ratio (phone/tablet).
 */
(function (global) {
    "use strict";

    var DEFAULT_RATIO = 2 / 3;
    var MIN_PX = 100;

    function deviceMaxPx() {
        var vv = global.visualViewport;
        var vw = (vv && vv.width) || global.innerWidth || 0;
        return vw > 0 ? vw : 0;
    }

    function canvasCapPx(root) {
        var canvas = (root && root.clientWidth) || 0;
        var surface = 0;
        if (root && root.closest) {
            var box = root.closest(
                ".o_chatboo_persistent_overlay, .o_chatboo_app, .o_chatboo_floating"
            );
            if (box) {
                surface = box.clientWidth || 0;
            }
        }
        var device = deviceMaxPx();
        var caps = [canvas, surface, device].filter(function (n) {
            return n > 0;
        });
        if (!caps.length) {
            return 0;
        }
        return Math.min.apply(null, caps);
    }

    function minPxForCap(cap) {
        if (!(cap > 0)) {
            return MIN_PX;
        }
        return Math.min(MIN_PX, cap);
    }

    function clampRatio(ratio, canvasW) {
        var r = (typeof ratio === "number" && isFinite(ratio) && ratio > 0)
            ? ratio
            : DEFAULT_RATIO;
        r = Math.min(1, Math.max(0, r));
        var w = canvasW || 0;
        var floor = minPxForCap(w);
        if (w > 0 && r * w < floor) {
            r = Math.min(1, floor / w);
        }
        return r;
    }

    function applyRatio(root, ratio) {
        if (!root || !root.style) {
            return clampRatio(ratio, 0);
        }
        var cap = canvasCapPx(root);
        var r = clampRatio(ratio, cap);
        root.style.setProperty("--o-chatboo-card-width", (r * 100) + "%");
        return r;
    }

    function clampPx(root, px) {
        var cap = canvasCapPx(root);
        var floor = minPxForCap(cap);
        var n = Number(px);
        if (!isFinite(n)) {
            n = cap > 0 ? cap * DEFAULT_RATIO : MIN_PX;
        }
        if (cap > 0) {
            n = Math.max(floor, Math.min(cap, n));
        }
        return n;
    }

    function applyPx(root, px) {
        var n = clampPx(root, px);
        var cap = canvasCapPx(root);
        var r = cap > 0 ? n / cap : DEFAULT_RATIO;
        return applyRatio(root, r);
    }

    function previewGuide(root, card, px) {
        if (!root || !card || !root.appendChild) {
            return clampPx(root, px);
        }
        var n = clampPx(root, px);
        var guide = root._chatbooResizeGuide;
        if (!guide) {
            guide = global.document.createElement("div");
            guide.className = "o_chatboo_card_resize_guide";
            guide.setAttribute("aria-hidden", "true");
            root.appendChild(guide);
            root._chatbooResizeGuide = guide;
            root.classList.add("o_chatboo_card_resizing");
        }
        var rootRect = root.getBoundingClientRect();
        var cardRect = card.getBoundingClientRect();
        var rtl = false;
        try {
            rtl = global.getComputedStyle(root).direction === "rtl";
        } catch (eDir) { /* LTR */ }
        var visH = root.clientHeight || 0;
        if (visH > 0) {
            guide.style.top = (root.scrollTop || 0) + "px";
            guide.style.height = visH + "px";
        }
        var x = rtl
            ? (cardRect.right - rootRect.left) - n + (root.scrollLeft || 0)
            : (cardRect.left - rootRect.left) + n + (root.scrollLeft || 0);
        guide.style.left = x + "px";
        return n;
    }

    function hideGuide(root) {
        if (!root) {
            return;
        }
        var guide = root._chatbooResizeGuide;
        if (guide && guide.parentNode) {
            guide.parentNode.removeChild(guide);
        }
        root._chatbooResizeGuide = null;
        if (root.classList) {
            root.classList.remove("o_chatboo_card_resizing");
        }
    }

    function relayoutCharts(root) {
        var api = global.ChatbooCharts;
        if (!api || !root) {
            return;
        }
        try {
            if (typeof api.softResize === "function") {
                api.softResize(root);
            } else if (typeof api.relayout === "function") {
                api.relayout(root);
            }
        } catch (e) { /* chart not mounted yet */ }
    }

    var _relayoutRaf = 0;
    var _relayoutRoot = null;

    function relayoutSoon(root) {
        if (root) {
            _relayoutRoot = root;
        }
        if (_relayoutRaf) {
            return;
        }
        var kick = function () {
            _relayoutRaf = 0;
            var target = _relayoutRoot;
            _relayoutRoot = null;
            relayoutCharts(target);
        };
        _relayoutRaf = global.requestAnimationFrame(kick);
    }

    global.ChatbooCardWidth = {
        DEFAULT_RATIO: DEFAULT_RATIO,
        applyRatio: applyRatio,
        applyPx: applyPx,
        previewGuide: previewGuide,
        hideGuide: hideGuide,
        relayoutSoon: relayoutSoon,
    };
})(typeof window !== "undefined" ? window : this);
