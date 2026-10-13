/* SPDX-License-Identifier: Apache-2.0
 * Copyright (C) 2026 Patanegra Soft <https://patanegra.com>
 *
 * One picture, full screen, with zoom.
 *
 * The host says what it has; the viewer only shows it. What is already on
 * screen appears at once; a larger copy replaces it when it arrives. Wheel,
 * pinch and double click zoom; dragging moves a zoomed picture. Escape, the
 * close button or a click beside the picture closes it.
 *
 *   window.pnsImageViewer.open({ src, full, tab, alt, onClose })
 *       src    the picture already on screen
 *       full   a larger copy: an address, or a Promise of one
 *       tab    what the "open in a tab" button opens; empty, no button
 *   window.pnsImageViewer.close()
 *   window.pnsImageViewer.isOpen()
 *   window.pnsImageViewer.optionsFor(img)   // what a picture on the page offers, or null
 *
 * A picture inside a link that also carries words (a card, a record name)
 * belongs to that link, so optionsFor gives null and the link keeps working.
 * A larger copy is only asked of this site: a picture from another site was
 * already brought through the server, and the page does not call that site.
 *
 * Plain script, no module system: the same file runs on Odoo 14, 17+ and in
 * pages outside the web client.
 */
(function () {
    "use strict";

    var MAX_SCALE = 6;
    var STEP = 1.2;
    var root = null;
    var picture = null;
    var tabButton = null;
    var current = null;
    var view = { scale: 1, x: 0, y: 0 };
    var points = {};
    var pinch = null;
    var pan = null;
    var moved = false;

    function sameOrigin(href) {
        try {
            return new URL(href, window.location.href).origin === window.location.origin;
        } catch (e) {
            return false;
        }
    }

    function optionsFor(target) {
        if (!target || target.tagName !== 'IMG') {
            return null;
        }
        var src = target.currentSrc || target.getAttribute('src') || '';
        if (!src) {
            return null;
        }
        var link = target.closest ? target.closest('a[href]') : null;
        if (link && ((link.textContent || '').trim() || link.querySelectorAll('img').length > 1)) {
            return null;
        }
        var href = link ? link.href : '';
        return {
            src: src,
            full: href && sameOrigin(href) ? href : '',
            tab: href || (/^data:image\//.test(src) ? src : ''),
            alt: target.getAttribute('alt') || '',
        };
    }

    function paint() {
        var shifted = view.scale !== 1 || view.x || view.y;
        picture.style.transform = shifted
            ? 'translate(' + view.x + 'px,' + view.y + 'px) scale(' + view.scale + ')'
            : '';
        root.classList.toggle('is-zoomed', view.scale > 1);
    }

    function reset() {
        view = { scale: 1, x: 0, y: 0 };
        points = {};
        pinch = null;
        pan = null;
        moved = false;
        if (picture) {
            paint();
        }
    }

    function zoomAt(cx, cy, scale) {
        var next = Math.min(MAX_SCALE, Math.max(1, scale));
        if (next === 1) {
            view = { scale: 1, x: 0, y: 0 };
        } else {
            var px = cx - window.innerWidth / 2;
            var py = cy - window.innerHeight / 2;
            var k = next / view.scale;
            view = {
                scale: next,
                x: px - (px - view.x) * k,
                y: py - (py - view.y) * k,
            };
        }
        paint();
    }

    function held() {
        return Object.keys(points);
    }

    function gap() {
        var keys = held();
        var a = points[keys[0]];
        var b = points[keys[1]];
        return Math.max(1, Math.hypot(a.x - b.x, a.y - b.y));
    }

    function middle() {
        var keys = held();
        var a = points[keys[0]];
        var b = points[keys[1]];
        return { x: (a.x + b.x) / 2, y: (a.y + b.y) / 2 };
    }

    function onDown(ev) {
        points[ev.pointerId] = { x: ev.clientX, y: ev.clientY };
        if (held().length >= 2) {
            pinch = { d: gap(), scale: view.scale };
            pan = null;
            return;
        }
        moved = false;
        pan = { x: ev.clientX - view.x, y: ev.clientY - view.y, from: { x: ev.clientX, y: ev.clientY } };
    }

    function onMove(ev) {
        if (!points[ev.pointerId]) {
            return;
        }
        points[ev.pointerId] = { x: ev.clientX, y: ev.clientY };
        if (pinch && held().length >= 2) {
            var at = middle();
            zoomAt(at.x, at.y, pinch.scale * (gap() / pinch.d));
            moved = true;
            return;
        }
        if (!pan || view.scale <= 1) {
            return;
        }
        if (Math.abs(ev.clientX - pan.from.x) + Math.abs(ev.clientY - pan.from.y) > 4) {
            moved = true;
        }
        view.x = ev.clientX - pan.x;
        view.y = ev.clientY - pan.y;
        paint();
    }

    function onUp(ev) {
        delete points[ev.pointerId];
        if (held().length < 2) {
            pinch = null;
        }
        if (!held().length) {
            pan = null;
        }
    }

    function onWheel(ev) {
        ev.preventDefault();
        zoomAt(ev.clientX, ev.clientY, view.scale * (ev.deltaY < 0 ? STEP : 1 / STEP));
    }

    function onDouble(ev) {
        if (ev.target !== picture) {
            return;
        }
        if (view.scale > 1) {
            zoomAt(ev.clientX, ev.clientY, 1);
        } else {
            zoomAt(ev.clientX, ev.clientY, 2.5);
        }
    }

    function onClick(ev) {
        if (moved) {
            moved = false;
            return;
        }
        if (ev.target !== picture) {
            close();
        }
    }

    function onKey(ev) {
        if (ev.key === 'Escape' || ev.key === 'Esc') {
            ev.preventDefault();
            ev.stopPropagation();
            close();
        }
    }

    function sameBytes(a, b) {
        if (!a || !b || a.byteLength !== b.byteLength || !a.byteLength) {
            return false;
        }
        var left = new Uint8Array(a);
        var right = new Uint8Array(b);
        for (var i = 0; i < left.length; i++) {
            if (left[i] !== right[i]) {
                return false;
            }
        }
        return true;
    }

    // Odoo answers a missing picture with this file and a success status.
    // The copy already on screen stays when the "full" link is that file.
    var emptyImage = null;

    function emptyImageBytes() {
        if (emptyImage) {
            return Promise.resolve(emptyImage);
        }
        var paths = [
            '/web/static/src/img/placeholder.png',
            '/web/static/img/placeholder.png',
        ];
        function at(i) {
            if (i >= paths.length) {
                return Promise.resolve(null);
            }
            return fetch(paths[i], { credentials: 'same-origin' }).then(function (resp) {
                if (!resp.ok) {
                    return at(i + 1);
                }
                return resp.arrayBuffer().then(function (buf) {
                    if (!buf || !buf.byteLength) {
                        return at(i + 1);
                    }
                    emptyImage = buf;
                    return buf;
                });
            }).catch(function () {
                return at(i + 1);
            });
        }
        return at(0);
    }

    function releaseBlob() {
        if (current && current.blob) {
            URL.revokeObjectURL(current.blob);
            current.blob = '';
        }
    }

    function useLarger(url, token, shown) {
        return fetch(url, { credentials: 'same-origin' }).then(function (resp) {
            if (!current || current.token !== token) {
                return;
            }
            if (!resp.ok || /\/placeholder\.png(?:$|\?)/.test(resp.url || '')) {
                current.tab = shown;
                return;
            }
            return resp.arrayBuffer().then(function (buf) {
                return emptyImageBytes().then(function (empty) {
                    if (!current || current.token !== token) {
                        return;
                    }
                    if (sameBytes(buf, empty)) {
                        current.tab = shown;
                        return;
                    }
                    releaseBlob();
                    current.blob = URL.createObjectURL(new Blob([buf]));
                    picture.src = current.blob;
                });
            });
        });
    }

    function dataBlobUrl(url) {
        var found = /^data:([^;,]+);base64,(.*)$/.exec(url);
        if (!found) {
            return '';
        }
        var bin = window.atob(found[2]);
        var bytes = new Uint8Array(bin.length);
        for (var i = 0; i < bin.length; i++) {
            bytes[i] = bin.charCodeAt(i);
        }
        return URL.createObjectURL(new Blob([bytes], { type: found[1] }));
    }

    function openTab() {
        var url = current && current.tab;
        if (!url) {
            return;
        }
        if (/^data:/.test(url)) {
            url = dataBlobUrl(url);
        }
        if (url) {
            window.open(url, '_blank', 'noopener');
        }
    }

    function button(cls, glyph, act) {
        var b = document.createElement('button');
        b.type = 'button';
        b.className = cls;
        b.textContent = glyph;
        b.addEventListener('pointerdown', function (ev) { ev.stopPropagation(); });
        b.addEventListener('click', function (ev) {
            ev.preventDefault();
            ev.stopPropagation();
            act();
        });
        return b;
    }

    function build() {
        root = document.createElement('div');
        root.className = 'pns-image-viewer';
        root.hidden = true;
        picture = document.createElement('img');
        picture.className = 'pns-image-viewer-picture';
        picture.draggable = false;
        var bar = document.createElement('div');
        bar.className = 'pns-image-viewer-bar';
        tabButton = button('pns-image-viewer-tab', '\u2197', openTab);
        bar.appendChild(tabButton);
        bar.appendChild(button('pns-image-viewer-close', '\u2715', close));
        root.appendChild(picture);
        root.appendChild(bar);
        root.addEventListener('wheel', onWheel, { passive: false });
        root.addEventListener('pointerdown', onDown);
        root.addEventListener('pointermove', onMove);
        root.addEventListener('pointerup', onUp);
        root.addEventListener('pointercancel', onUp);
        root.addEventListener('dblclick', onDouble);
        root.addEventListener('click', onClick);
        document.body.appendChild(root);
    }

    function open(opts) {
        if (!opts || !opts.src) {
            return;
        }
        if (current) {
            close();
        }
        if (!root) {
            build();
        }
        var token = {};
        current = { tab: opts.tab || '', onClose: opts.onClose, token: token };
        reset();
        picture.src = opts.src;
        picture.alt = opts.alt || '';
        tabButton.hidden = !current.tab;
        root.hidden = false;
        document.addEventListener('keydown', onKey, true);
        if (!opts.full) {
            return Promise.resolve();
        }
        return Promise.resolve(opts.full).then(function (url) {
            if (!url || url === opts.src || !current || current.token !== token) {
                return;
            }
            return useLarger(url, token, opts.src);
        }).catch(function () { /* the picture already on screen stays */ });
    }

    function close() {
        if (!current) {
            return;
        }
        var done = current.onClose;
        releaseBlob();
        current = null;
        root.hidden = true;
        picture.removeAttribute('src');
        document.removeEventListener('keydown', onKey, true);
        reset();
        if (typeof done === 'function') {
            done();
        }
    }

    function isOpen() {
        return !!current;
    }

    window.pnsImageViewer = { open: open, close: close, isOpen: isOpen, optionsFor: optionsFor };
})();
