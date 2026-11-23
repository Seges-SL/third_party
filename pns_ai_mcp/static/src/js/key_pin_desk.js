/** @odoo-module **/
/**
 * Key list for the temporary PIN. The rows stay in this browser tab.
 *
 * SPDX-License-Identifier: Apache-2.0
 * Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
 */
import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";
import { pnsPatch } from "@pns_base/js/pns_patch";
import { ListController } from "@web/views/list/list_controller";
import { FormController } from "@web/views/form/form_controller";
import { onMounted, onWillUnmount } from "@odoo/owl";
import { session } from "@web/session";

const VAULT = "pns.key.pin.vault";
const PINS = "pns.key.pin.pins";
const TOKEN = "pns.key.pin.token";
const inflight = {};
let pinLen = 8;
let timer = null;
let listening = false;
let busRef = null;

function token() {
    let value = "";
    try {
        value = sessionStorage.getItem(TOKEN) || "";
    } catch (e) {
        return "";
    }
    if (!value) {
        value = (window.crypto && crypto.randomUUID)
            ? crypto.randomUUID()
            : String(Date.now()) + Math.random().toString(16).slice(2);
        try {
            sessionStorage.setItem(TOKEN, value);
        } catch (e) {
            return "";
        }
    }
    return value;
}

function vault() {
    try {
        return JSON.parse(sessionStorage.getItem(VAULT) || "{}") || {};
    } catch (e) {
        return {};
    }
}

function saveVault(map) {
    sessionStorage.setItem(VAULT, JSON.stringify(map || {}));
}

function pins() {
    try {
        return JSON.parse(sessionStorage.getItem(PINS) || "{}") || {};
    } catch (e) {
        return {};
    }
}

function savePins(map) {
    sessionStorage.setItem(PINS, JSON.stringify(map || {}));
}

function makePin() {
    const digits = "0123456789";
    let out = "";
    const buf = new Uint32Array(pinLen);
    if (window.crypto && crypto.getRandomValues) {
        crypto.getRandomValues(buf);
        for (let i = 0; i < pinLen; i++) {
            out += digits[buf[i] % 10];
        }
    } else {
        for (let i = 0; i < pinLen; i++) {
            out += digits[Math.floor(Math.random() * 10)];
        }
    }
    return out;
}

function formatPin(raw) {
    const digits = String(raw || "").replace(/\D/g, "");
    return digits.replace(/(.{4})/g, "$1 ").trim();
}

// One PIN per person in the list, minted here. The server never sees a PIN
// until an app spends it, and never stores one.
function ensurePins() {
    const rows = vault();
    const map = pins();
    let changed = false;
    Object.keys(map).forEach((email) => {
        if (!(email in rows)) {
            delete map[email];
            changed = true;
        }
    });
    Object.keys(rows).forEach((email) => {
        if (!map[email]) {
            map[email] = makePin();
            changed = true;
        }
    });
    if (changed) {
        savePins(map);
    }
    return map;
}

function dropPin(pin) {
    const target = String(pin || "").replace(/\D/g, "");
    if (!target) {
        return;
    }
    const map = pins();
    let changed = false;
    Object.keys(map).forEach((email) => {
        if (map[email] === target) {
            delete map[email];
            changed = true;
        }
    });
    if (changed) {
        savePins(map);
        renderPins();
    }
}

function heldCount() {
    return Object.keys(vault()).length;
}

function parseVault(text) {
    const out = {};
    String(text || "").split(/\r?\n/).forEach((line) => {
        const raw = line.trim();
        if (!raw || raw.startsWith("#")) {
            return;
        }
        let parts;
        if (raw.indexOf(",") >= 0) {
            parts = raw.split(",");
        } else if (raw.indexOf(";") >= 0) {
            parts = raw.split(";");
        } else {
            parts = raw.split(/\s+/);
        }
        if (parts.length < 2) {
            return;
        }
        const email = parts[0].trim().toLowerCase();
        const key = parts[1].trim();
        if (!email || email.indexOf("@") < 0 || !key) {
            return;
        }
        out[email] = key;
    });
    return out;
}

function lookup(email, login) {
    const rows = vault();
    const a = String(email || "").trim().toLowerCase();
    const b = String(login || "").trim().toLowerCase();
    return rows[a] || rows[b] || "";
}

function tellList() {
    try {
        window.dispatchEvent(new CustomEvent("pns_key_pin_changed"));
    } catch (e) { /* ignore */ }
}

function jsonCall(url, params) {
    return fetch(url, {
        method: "POST",
        credentials: "same-origin",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
            jsonrpc: "2.0",
            method: "call",
            params: params || {},
            id: Date.now(),
        }),
    }).then((response) => response.json()).then((body) => body && body.result);
}

function answer(payload) {
    if (payload && payload.payload) {
        payload = payload.payload;
    }
    if (!payload || !payload.ask_id || inflight[payload.ask_id]) {
        return;
    }
    let key = "";
    if (payload.pin) {
        const map = pins();
        const email = Object.keys(map).find((e) => map[e] === payload.pin);
        key = email ? (vault()[email] || "") : "";
    } else {
        key = lookup(payload.email, payload.login);
        if (!key) {
            return;
        }
    }
    inflight[payload.ask_id] = true;
    jsonCall("/pns_ai_mcp/key_pin/supply", {
        ask_id: payload.ask_id,
        api_key: key,
    }).finally(() => {
        delete inflight[payload.ask_id];
    });
}

function beat(after) {
    const current = token();
    if (!current || !heldCount()) {
        if (after) {
            after();
        }
        return;
    }
    jsonCall("/pns_ai_mcp/key_pin/desk", { token: current }).then((result) => {
        if (result && result.pin_length >= 4 && result.pin_length <= 12) {
            pinLen = result.pin_length;
        }
        (result && result.asks || []).forEach(answer);
        if (after) {
            after();
        }
    }).catch(() => {
        if (after) {
            after();
        }
    });
}

function subscribe(bus) {
    if (!bus || typeof bus.subscribe !== "function") {
        return;
    }
    busRef = bus;
    if (listening) {
        return;
    }
    listening = true;
    bus.subscribe("pns_key_pin", (payload) => answer(payload));
    bus.subscribe("pns_key_pin_spent", (payload) => {
        if (payload && payload.payload) {
            payload = payload.payload;
        }
        dropPin(payload && payload.pin);
    });
    bus.subscribe("pns_key_pin_changed", () => tellList());
    bus.subscribe("pns_key_pin_presence", () => tellList());
}

function ensureStyle() {
    if (document.getElementById("pns-key-pin-style")) {
        return;
    }
    const style = document.createElement("style");
    style.id = "pns-key-pin-style";
    style.textContent = [
        "#pns-key-pin-layer{position:fixed;inset:0;background:rgba(0,0,0,.35);z-index:2000;",
        "display:flex;align-items:center;justify-content:center}",
        "#pns-key-pin-card{background:#fff;color:#1f1f1f;width:min(640px,92vw);",
        "padding:16px;border-radius:8px;box-shadow:0 8px 28px rgba(0,0,0,.2);",
        "max-height:90vh;display:flex;flex-direction:column}",
        "#pns-key-pin-card>*{flex-shrink:0}",
        "#pns-key-pin-card textarea{width:100%;min-height:220px;font-family:monospace}",
        "#pns-key-pin-card .row{display:flex;gap:8px;justify-content:flex-end;margin-top:12px}",
        "#pns-key-pin-held{position:fixed;right:16px;bottom:16px;z-index:10500;",
        "background:#1a73e8;color:#fff;padding:10px 14px;border-radius:8px;",
        "font-weight:700;box-shadow:0 4px 16px rgba(0,0,0,.28);cursor:pointer;",
        "display:flex;align-items:center;gap:8px;max-width:min(360px,90vw);border:0}",
        "#pns-key-pin-held:hover{background:#1558b0}",
        "#pns-key-pin-held .fa{font-size:16px}",
        ".o_mcp_key_pin_held_chip{margin-left:4px}",
        "#pns-key-pin-card .pins{margin-top:12px;flex:1 1 auto;min-height:0;overflow-y:auto}",
        "#pns-key-pin-card .pins .pinrow{display:flex;align-items:center;gap:8px;",
        "padding:4px 0;border-top:1px solid #e0e0e0}",
        "#pns-key-pin-card .pins .pinmail{flex:1;overflow:hidden;text-overflow:ellipsis}",
        "#pns-key-pin-card .pins .pindigits{font-weight:700;letter-spacing:0.08em}",
    ].join("");
    document.head.appendChild(style);
}

function paintHeld() {
    ensureStyle();
    const count = heldCount();
    let el = document.getElementById("pns-key-pin-held");
    if (!count) {
        if (el) {
            el.remove();
        }
        return;
    }
    if (!el) {
        el = document.createElement("button");
        el.type = "button";
        el.id = "pns-key-pin-held";
        el.title = _t("This browser tab is holding the key list in session storage. Click to open it.");
        el.addEventListener("click", () => openLayer());
        document.body.appendChild(el);
    }
    el.innerHTML = '<i class="fa fa-key" aria-hidden="true"></i><span></span>';
    el.querySelector("span").textContent =
        _t("This tab is holding keys:") + " " + count;
}

function startDesk(bus) {
    if (bus) {
        subscribe(bus);
    } else if (busRef) {
        subscribe(busRef);
    }
    paintHeld();
    // Touch the desk first, then soft-refresh the list (blue pins).
    beat(tellList);
    if (!timer) {
        timer = window.setInterval(() => beat(), 20000);
    }
}

function stopDesk() {
    const current = token();
    if (timer) {
        window.clearInterval(timer);
        timer = null;
    }
    try {
        sessionStorage.removeItem(VAULT);
        sessionStorage.removeItem(PINS);
    } catch (e) { /* ignore */ }
    paintHeld();
    tellList();
    if (current && navigator.sendBeacon) {
        navigator.sendBeacon(
            stopUrl(),
            new Blob([JSON.stringify({ token: current })], { type: "application/json" }),
        );
    }
}

function stopUrl() {
    const csrf = (window.odoo && window.odoo.csrf_token) || "";
    return "/pns_ai_mcp/key_pin/stop?csrf_token=" + encodeURIComponent(csrf);
}

function renderPins() {
    const box = document.querySelector("#pns-key-pin-card .pins");
    if (!box) {
        return;
    }
    const map = ensurePins();
    const emails = Object.keys(map).sort();
    box.innerHTML = "";
    if (!emails.length) {
        return;
    }
    const head = document.createElement("h4");
    head.textContent = _t("PINs in this tab");
    box.appendChild(head);
    const note = document.createElement("p");
    note.className = "hint";
    note.textContent = _t("The PINs live only while this tab holds the list. Clear the list and they are gone.");
    box.appendChild(note);
    emails.forEach((email) => {
        const row = document.createElement("div");
        row.className = "pinrow";
        const mail = document.createElement("span");
        mail.className = "pinmail";
        mail.textContent = email;
        const digits = document.createElement("span");
        digits.className = "pindigits";
        digits.textContent = formatPin(map[email]);
        const copy = document.createElement("button");
        copy.type = "button";
        copy.className = "btn btn-link o_key_pin_copy";
        copy.setAttribute("data-pin", formatPin(map[email]));
        copy.title = _t("Copy to clipboard");
        copy.innerHTML = '<i class="fa fa-copy"></i>';
        const again = document.createElement("button");
        again.type = "button";
        again.className = "btn btn-link";
        again.textContent = _t("New PIN");
        again.addEventListener("click", () => {
            const fresh = pins();
            fresh[email] = makePin();
            savePins(fresh);
            renderPins();
        });
        row.appendChild(mail);
        row.appendChild(digits);
        row.appendChild(copy);
        row.appendChild(again);
        box.appendChild(row);
    });
}

function openLayer(onDone) {
    ensureStyle();
    const old = document.getElementById("pns-key-pin-layer");
    if (old) {
        old.remove();
    }
    const layer = document.createElement("div");
    layer.id = "pns-key-pin-layer";
    layer.innerHTML = [
        '<div id="pns-key-pin-card" role="dialog">',
        "<h3></h3><p></p><textarea></textarea><p class=\"hint\"></p>",
        '<div class="pins"></div>',
        '<div class="row"><button type="button" class="btn btn-secondary" data-act="clear"></button>',
        '<button type="button" class="btn btn-secondary" data-act="close"></button>',
        '<button type="button" class="btn btn-primary" data-act="keep"></button></div>',
        "</div>",
    ].join("");
    const title = layer.querySelector("h3");
    const lead = layer.querySelector("p");
    const hint = layer.querySelector(".hint");
    const area = layer.querySelector("textarea");
    title.textContent = _t("Key list");
    lead.textContent = _t("One row per person: email, API key, name. The name is ignored. Use this list. Closing the box does not keep it.");
    area.placeholder = "ana@example.com, the-api-key, Ana";
    const count = heldCount();
    hint.textContent = count
        ? _t("This tab is holding keys:") + " " + count
        : "";
    layer.querySelector("[data-act=clear]").textContent = _t("Clear");
    layer.querySelector("[data-act=close]").textContent = _t("Close");
    layer.querySelector("[data-act=keep]").textContent = _t("Use this list");
    const rows = vault();
    const lines = Object.keys(rows).map((email) => email + ", " + rows[email]);
    area.value = lines.join("\n");
    function shut() {
        layer.remove();
    }
    layer.querySelector("[data-act=close]").addEventListener("click", shut);
    layer.addEventListener("click", (ev) => {
        if (ev.target === layer) {
            shut();
        }
    });
    layer.querySelector("[data-act=clear]").addEventListener("click", () => {
        stopDesk();
        shut();
        if (onDone) {
            onDone();
        }
    });
    layer.querySelector("[data-act=keep]").addEventListener("click", () => {
        const parsed = parseVault(area.value);
        saveVault(parsed);
        ensurePins();
        startDesk(busRef);
        shut();
        if (onDone) {
            onDone();
        }
    });
    renderPins();
    document.body.appendChild(layer);
    area.focus();
}

function bindDeskClicks() {
    document.addEventListener("click", (ev) => {
        let node = ev.target;
        while (node && node !== document) {
            if (node.classList && node.classList.contains("o_key_pin_copy")) {
                ev.preventDefault();
                ev.stopPropagation();
                const text = node.getAttribute("data-pin") || "";
                if (text && navigator.clipboard && navigator.clipboard.writeText) {
                    navigator.clipboard.writeText(text);
                }
                return;
            }
            node = node.parentNode;
        }
    }, true);

    document.addEventListener("click", (ev) => {
        let node = ev.target;
        while (node && node !== document) {
            if (node.classList && node.classList.contains("o_mcp_key_pin_open")) {
                openLayer();
                return;
            }
            node = node.parentNode;
        }
    }, true);

    window.addEventListener("pagehide", () => {
        const current = token();
        if (!current || !navigator.sendBeacon) {
            return;
        }
        if (!heldCount()) {
            return;
        }
        navigator.sendBeacon(
            stopUrl(),
            new Blob([JSON.stringify({ token: current })], { type: "application/json" }),
        );
    });
}

async function refreshMcpUsers(controller) {
    if (!controller || controller.props.resModel !== "ai.mcp.user") {
        return;
    }
    const root = controller.model && controller.model.root;
    if (root && typeof root.load === "function") {
        await root.load();
        if (typeof controller.render === "function") {
            controller.render(true);
        }
    }
    paintToolbarChip(controller);
}

function paintToolbarChip(controller) {
    const root = controller && controller.el;
    if (!root) {
        return;
    }
    const bar = root.querySelector(".o_control_panel .o_cp_buttons, .o_control_panel_main_buttons");
    if (!bar) {
        return;
    }
    const count = heldCount();
    let chip = bar.querySelector(".o_mcp_key_pin_held_chip");
    if (!count) {
        if (chip) {
            chip.remove();
        }
        return;
    }
    if (!chip) {
        chip = document.createElement("button");
        chip.type = "button";
        chip.className = "btn btn-primary o_mcp_key_pin_held_chip o_mcp_key_pin_open";
        chip.title = _t("This browser tab is holding the key list in session storage. Click to open it.");
        bar.appendChild(chip);
    }
    chip.innerHTML = "<i class='fa fa-key'></i> "
        + _t("This tab is holding keys:") + " " + count;
}

function bindPinRefresh(controller) {
    if (controller.props.resModel !== "ai.mcp.user") {
        return;
    }
    const bus = controller.env.services.bus_service;
    const onChanged = () => refreshMcpUsers(controller);
    onMounted(() => {
        subscribe(bus);
        window.addEventListener("pns_key_pin_changed", onChanged);
        paintToolbarChip(controller);
    });
    onWillUnmount(() => {
        window.removeEventListener("pns_key_pin_changed", onChanged);
    });
}

pnsPatch(ListController.prototype, "pns_ai_mcp.key_pin_desk", {
    setup() {
        super.setup();
        bindPinRefresh(this);
    },
});

pnsPatch(FormController.prototype, "pns_ai_mcp.key_pin_desk", {
    setup() {
        super.setup();
        bindPinRefresh(this);
    },
});

const keyPinDeskService = {
    dependencies: ["bus_service"],
    start(env, { bus_service }) {
        if (!session.pns_is_ai_admin) {
            return;
        }
        bindDeskClicks();
        subscribe(bus_service);
        paintHeld();
        if (heldCount()) {
            startDesk(bus_service);
        }
        window.pnsKeyPinOpen = function (onDone) {
            openLayer(function () {
                startDesk(bus_service);
                if (onDone) {
                    onDone();
                }
            });
        };
        window.pnsKeyPinHeldCount = heldCount;
    },
};

registry.category("services").add("pns_key_pin_desk", keyPinDeskService);
