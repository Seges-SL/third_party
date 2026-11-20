/* SPDX-License-Identifier: Apache-2.0
 * Copyright (C) 2026 Patanegra Soft <https://patanegra.com>
 *
 * One full-screen panel at a time over the Odoo app.
 *
 * A panel covers the app below the navbar without navigating, so the app
 * stays mounted under it. Opening a panel hides the one showing; closing it
 * leaves the app as it was. A click in the navbar closes the panel showing,
 * except on an element marked ``data-pns-layer-toggle`` (a panel's own
 * launcher, which opens or closes it itself).
 *
 * Plain script, no module system: the same file runs on Odoo 14 and 17+.
 *
 *   window.pnsLayer.claim(key, hide)   // I am showing; hide() if someone else claims
 *   window.pnsLayer.release(key)       // I hid myself
 */
(function () {
    "use strict";

    var shown = null;

    function claim(key, hide) {
        var previous = shown;
        shown = { key: key, hide: hide };
        if (previous && previous.key !== key) {
            previous.hide();
        }
    }

    function release(key) {
        if (shown && shown.key === key) {
            shown = null;
        }
    }

    document.addEventListener('click', function (ev) {
        var target = ev.target;
        if (!shown || !target || !target.closest) {
            return;
        }
        if (!target.closest('.o_main_navbar') || target.closest('[data-pns-layer-toggle]')) {
            return;
        }
        var current = shown;
        shown = null;
        current.hide();
    }, true);

    window.pnsLayer = { claim: claim, release: release };
})();
