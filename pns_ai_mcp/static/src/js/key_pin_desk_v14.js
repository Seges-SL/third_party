/**
 * Key list for the temporary PIN (Odoo 14). The rows stay in this browser tab.
 *
 * SPDX-License-Identifier: Apache-2.0
 * Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
 */
odoo.define('pns_ai_mcp.key_pin_desk', function (require) {
    "use strict";

    var WebClient = require('web.WebClient');
    var ajax = require('web.ajax');
    var core = require('web.core');
    var _t = core._t;

    var VAULT = 'pns.key.pin.vault';
    var TOKEN = 'pns.key.pin.token';
    var inflight = {};
    var timer = null;

    function token() {
        var value = '';
        try {
            value = sessionStorage.getItem(TOKEN) || '';
        } catch (e) {
            return '';
        }
        if (!value) {
            value = String(Date.now()) + Math.random().toString(16).slice(2);
            try {
                sessionStorage.setItem(TOKEN, value);
            } catch (e2) {
                return '';
            }
        }
        return value;
    }

    function vault() {
        try {
            return JSON.parse(sessionStorage.getItem(VAULT) || '{}') || {};
        } catch (e) {
            return {};
        }
    }

    function saveVault(map) {
        sessionStorage.setItem(VAULT, JSON.stringify(map || {}));
    }

    function heldCount() {
        return Object.keys(vault()).length;
    }

    function parseVault(text) {
        var out = {};
        String(text || '').split(/\r?\n/).forEach(function (line) {
            var raw = line.trim();
            if (!raw || raw.charAt(0) === '#') {
                return;
            }
            var parts;
            if (raw.indexOf(',') >= 0) {
                parts = raw.split(',');
            } else if (raw.indexOf(';') >= 0) {
                parts = raw.split(';');
            } else {
                parts = raw.split(/\s+/);
            }
            if (parts.length < 2) {
                return;
            }
            var email = parts[0].trim().toLowerCase();
            var key = parts[1].trim();
            if (!email || email.indexOf('@') < 0 || !key) {
                return;
            }
            out[email] = key;
        });
        return out;
    }

    function lookup(email, login) {
        var rows = vault();
        var a = String(email || '').trim().toLowerCase();
        var b = String(login || '').trim().toLowerCase();
        return rows[a] || rows[b] || '';
    }

    function tellList() {
        core.bus.trigger('pns_key_pin_changed');
    }

    function answer(payload) {
        if (payload && payload.payload) {
            payload = payload.payload;
        }
        if (!payload || !payload.ask_id || inflight[payload.ask_id]) {
            return;
        }
        var key = lookup(payload.email, payload.login);
        if (!key) {
            return;
        }
        inflight[payload.ask_id] = true;
        var done = function () {
            delete inflight[payload.ask_id];
        };
        var req = ajax.jsonRpc('/pns_ai_mcp/key_pin/supply', 'call', {
            ask_id: payload.ask_id,
            api_key: key,
        });
        if (req && typeof req.finally === 'function') {
            req.finally(done);
        } else if (req && typeof req.always === 'function') {
            req.always(done);
        } else {
            Promise.resolve(req).then(done, done);
        }
    }

    function beat(after) {
        var current = token();
        if (!current || !heldCount()) {
            if (after) {
                after();
            }
            return;
        }
        ajax.jsonRpc('/pns_ai_mcp/key_pin/desk', 'call', {
            token: current,
        }).then(function (result) {
            ((result && result.asks) || []).forEach(answer);
            if (after) {
                after();
            }
        }, function () {
            if (after) {
                after();
            }
        });
    }

    function ensureStyle() {
        if (document.getElementById('pns-key-pin-style')) {
            return;
        }
        var style = document.createElement('style');
        style.id = 'pns-key-pin-style';
        style.textContent = [
            '#pns-key-pin-layer{position:fixed;inset:0;background:rgba(0,0,0,.35);z-index:2000;',
            'display:flex;align-items:center;justify-content:center}',
            '#pns-key-pin-card{background:#fff;color:#1f1f1f;width:640px;max-width:92vw;',
            'padding:16px;border-radius:8px}',
            '#pns-key-pin-card textarea{width:100%;min-height:220px;font-family:monospace}',
            '#pns-key-pin-card .row{margin-top:12px;text-align:right}',
            '#pns-key-pin-card .row button{margin-left:8px}',
            '#pns-key-pin-held{position:fixed;right:16px;bottom:16px;z-index:10500;',
            'background:#1a73e8;color:#fff;padding:10px 14px;border-radius:8px;',
            'font-weight:700;box-shadow:0 4px 16px rgba(0,0,0,.28);cursor:pointer;',
            'display:flex;align-items:center;gap:8px;max-width:min(360px,90vw)}',
            '#pns-key-pin-held:hover{background:#1558b0}',
            '#pns-key-pin-held .fa{font-size:16px}',
            '.o_mcp_key_pin_held_chip{margin-left:4px}',
        ].join('');
        document.head.appendChild(style);
    }

    function paintHeld() {
        ensureStyle();
        var count = heldCount();
        var el = document.getElementById('pns-key-pin-held');
        if (!count) {
            if (el && el.parentNode) {
                el.parentNode.removeChild(el);
            }
            return;
        }
        if (!el) {
            el = document.createElement('button');
            el.type = 'button';
            el.id = 'pns-key-pin-held';
            el.title = _t('This browser tab is holding the key list in session storage. Click to open it.');
            el.addEventListener('click', function () {
                openLayer();
            });
            document.body.appendChild(el);
        }
        el.innerHTML = '<i class="fa fa-key" aria-hidden="true"></i><span></span>';
        el.querySelector('span').textContent =
            _t('This tab is holding keys:') + ' ' + count;
    }

    function startDesk() {
        paintHeld();
        // Touch the desk first, then soft-refresh the list (blue pins).
        beat(tellList);
        if (!timer) {
            timer = window.setInterval(function () {
                beat();
            }, 20000);
        }
    }

    function stopDesk() {
        var current = token();
        if (timer) {
            window.clearInterval(timer);
            timer = null;
        }
        try {
            sessionStorage.removeItem(VAULT);
        } catch (e) { /* ignore */ }
        paintHeld();
        tellList();
        if (current && navigator.sendBeacon) {
            navigator.sendBeacon(
                '/pns_ai_mcp/key_pin/stop',
                new Blob([JSON.stringify({token: current})], {type: 'application/json'})
            );
        }
    }

    function openLayer(onDone) {
        ensureStyle();
        var old = document.getElementById('pns-key-pin-layer');
        if (old) {
            old.parentNode.removeChild(old);
        }
        var layer = document.createElement('div');
        layer.id = 'pns-key-pin-layer';
        layer.innerHTML = [
            '<div id="pns-key-pin-card" role="dialog">',
            '<h3></h3><p></p><textarea></textarea><p class="hint"></p>',
            '<div class="row">',
            '<button type="button" class="btn btn-secondary" data-act="clear"></button>',
            '<button type="button" class="btn btn-secondary" data-act="close"></button>',
            '<button type="button" class="btn btn-primary" data-act="keep"></button>',
            '</div></div>',
        ].join('');
        layer.querySelector('h3').textContent = _t('Key list');
        layer.querySelector('p').textContent = _t('One row per person: email, API key, name. The name is ignored. Use this list. Closing the box does not keep it.');
        var area = layer.querySelector('textarea');
        area.placeholder = 'ana@example.com, the-api-key, Ana';
        var count = heldCount();
        layer.querySelector('.hint').textContent = count
            ? _t('This tab is holding keys:') + ' ' + count
            : '';
        layer.querySelector('[data-act=clear]').textContent = _t('Clear');
        layer.querySelector('[data-act=close]').textContent = _t('Close');
        layer.querySelector('[data-act=keep]').textContent = _t('Use this list');
        var rows = vault();
        area.value = Object.keys(rows).map(function (email) {
            return email + ', ' + rows[email];
        }).join('\n');
        function shut() {
            if (layer.parentNode) {
                layer.parentNode.removeChild(layer);
            }
        }
        layer.querySelector('[data-act=close]').addEventListener('click', shut);
        layer.addEventListener('click', function (ev) {
            if (ev.target === layer) {
                shut();
            }
        });
        layer.querySelector('[data-act=clear]').addEventListener('click', function () {
            stopDesk();
            shut();
            if (onDone) {
                onDone();
            }
        });
        layer.querySelector('[data-act=keep]').addEventListener('click', function () {
            saveVault(parseVault(area.value));
            startDesk();
            shut();
            if (onDone) {
                onDone();
            }
        });
        document.body.appendChild(layer);
        area.focus();
    }

    document.addEventListener('click', function (ev) {
        var node = ev.target;
        while (node && node !== document) {
            if (node.classList && node.classList.contains('o_key_pin_copy')) {
                ev.preventDefault();
                ev.stopPropagation();
                var text = node.getAttribute('data-pin') || '';
                if (text && navigator.clipboard && navigator.clipboard.writeText) {
                    navigator.clipboard.writeText(text);
                }
                return;
            }
            node = node.parentNode;
        }
    }, true);

    document.addEventListener('click', function (ev) {
        var node = ev.target;
        while (node && node !== document) {
            if (node.classList && node.classList.contains('o_mcp_key_pin_open')) {
                openLayer();
                return;
            }
            node = node.parentNode;
        }
    }, true);

    window.pnsKeyPinOpen = openLayer;
    window.pnsKeyPinHeldCount = heldCount;

    window.addEventListener('pagehide', function () {
        var current = token();
        if (!current || !navigator.sendBeacon || !heldCount()) {
            return;
        }
        navigator.sendBeacon(
            '/pns_ai_mcp/key_pin/stop',
            new Blob([JSON.stringify({token: current})], {type: 'application/json'})
        );
    });

    function onBus(notifications) {
        (notifications || []).forEach(function (notif) {
            var payload = Array.isArray(notif) ? notif[1] : (notif && notif.payload);
            if (typeof payload === 'string') {
                try {
                    payload = JSON.parse(payload);
                } catch (e) {
                    payload = null;
                }
            }
            if (
                payload
                && (payload.type === 'pns_key_pin_changed'
                    || payload.type === 'pns_key_pin_presence')
            ) {
                core.bus.trigger('pns_key_pin_changed');
            }
            if (payload && (payload.type === 'pns_key_pin' || payload.ask_id)) {
                answer(payload);
            }
        });
    }

    WebClient.include({
        start: function () {
            var self = this;
            return this._super.apply(this, arguments).then(function () {
                try {
                    self.call('bus_service', 'on', 'notification', self, onBus);
                    self.call('bus_service', 'addChannel', 'partner');
                    self.call('bus_service', 'startPolling');
                } catch (e) { /* backend without bus */ }
                paintHeld();
                if (heldCount()) {
                    startDesk();
                }
            });
        },
    });

    return {openLayer: openLayer, heldCount: heldCount};
});
