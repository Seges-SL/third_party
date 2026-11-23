/** @odoo-module **/
/* SPDX-License-Identifier: Apache-2.0 */
/* Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com> */
/**
 * Chatboo overlay singleton on the main OWL tree (Odoo 19).
 * Visible state lives on the host (useState). Intercepts doAction so
 * chatboo.action only calls overlay.show() and does not clear breadcrumbs.
 */

import { Component, onMounted, onPatched, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import ChatbooApp from "./chatboo_app";
import { loadHeavyLibs } from "./chatboo_heavy_libs";

function parseActionContext(action) {
    const raw = action?.context;
    if (!raw) {
        return {};
    }
    if (typeof raw === "object") {
        return {
            new_chat: raw.new_chat === true || raw.new_chat === "True",
            show_history_modal: raw.show_history_modal === true || raw.show_history_modal === "True",
        };
    }
    const ctxStr = String(raw);
    return {
        new_chat: ctxStr.includes("'new_chat': True") || ctxStr.includes('"new_chat": True'),
        show_history_modal: ctxStr.includes("'show_history_modal': True") || ctxStr.includes('"show_history_modal": True'),
    };
}

const CHATBOO_TAGS = new Set([
    "chatboo.action",
    "chatboo.history.action",
    "chatboo.new.action",
]);

function requestLooksLikeChatboo(actionRequest, idSet) {
    if (actionRequest == null) {
        return false;
    }
    if (typeof actionRequest === "number") {
        return idSet.has(actionRequest);
    }
    if (typeof actionRequest === "string") {
        const trimmed = actionRequest.trim();
        if (CHATBOO_TAGS.has(trimmed) || trimmed.includes("action_chatboo_client")) {
            return true;
        }
        const comma = trimmed.split(",");
        if (comma.length === 2) {
            const id = parseInt(comma[1], 10);
            return !Number.isNaN(id) && idSet.has(id);
        }
        const asNum = parseInt(trimmed, 10);
        return String(asNum) === trimmed && idSet.has(asNum);
    }
    if (typeof actionRequest === "object") {
        if (CHATBOO_TAGS.has(actionRequest.tag)) {
            return true;
        }
        if (actionRequest.id != null && idSet.has(actionRequest.id)) {
            return true;
        }
        const xml = actionRequest.xml_id || actionRequest.xmlid || "";
        return String(xml).includes("action_chatboo_client");
    }
    return false;
}

function clearChatbooBadge() {
    const badge = document.querySelector(".o_chatboo_badge");
    if (badge) {
        badge.style.display = "none";
        badge.innerHTML = '<i class="fa fa-bell-o"/>';
        badge.classList.remove("bg-danger", "bg-warning");
    }
    try {
        localStorage.removeItem("chatboo_unread");
    } catch (_) {}
}

class ChatbooOverlayHost extends Component {
    static template = "pns_ai_chatboo.ChatbooOverlayHost";
    static components = { ChatbooApp };
    static props = {};

    setup() {
        this.overlay = useService("chatboo_overlay");
        this.state = useState({
            visible: false,
            chatMounted: false,
            topOffset: "46px",
        });
        this.overlay.registerHost(this);
        this._paintQueue = [];

        onMounted(() => {
            const navbar = document.querySelector(".o_main_navbar");
            this.state.topOffset = navbar ? `${navbar.offsetHeight}px` : "46px";
        });
        onPatched(() => {
            for (const resolve of this._paintQueue.splice(0)) {
                resolve();
            }
        });
    }

    /** Resolves once OWL has patched the host (d-none already gone). */
    _painted() {
        return new Promise((resolve) => {
            this._paintQueue.push(resolve);
            this.render();
        });
    }

    async show({ context = {} } = {}) {
        await loadHeavyLibs();
        if (!this.state.chatMounted) {
            this.state.chatMounted = true;
        }
        window.pnsLayer.claim("chatboo", () => this.hide());
        this.state.visible = true;

        const comp = await this.overlay.waitForApp();
        await this._painted();
        if (comp && comp._refreshScreenFocus) {
            comp._refreshScreenFocus();
        }
        if (comp && !comp.state.currentSessionId && !comp.state.messages.length) {
            await comp._initSessions();
        }
        if (context.new_chat) {
            await comp._createNewSession(true);
        } else if (context.show_history_modal) {
            await comp._showSessions();
        }
        comp._focusInput();
        if (comp && typeof comp._restorePendingVerifications === "function") {
            await comp._restorePendingVerifications();
        }
    }

    hide() {
        this.state.visible = false;
        window.pnsLayer.release("chatboo");
        const comp = this.overlay.getAppComponent && this.overlay.getAppComponent();
        if (comp && comp._closeSlashUi) {
            comp._closeSlashUi();
        } else if (comp && comp.state) {
            comp.state.slashOpen = false;
            comp.state.slashItems = [];
            comp.state.slashMode = "commands";
        }
        if (comp && comp.state) {
            comp.state.screenFocusLabel = "";
            comp.state.screenContextSnapshot = null;
        }
        window.dispatchEvent(new CustomEvent("chatboo-auth-cue", {
            detail: { notify: false, forceHidden: true },
        }));
    }

    onChatbooAppReady(comp) {
        this.overlay.setAppComponent(comp);
    }

    get overlayStyle() {
        return [
            "position:fixed",
            `top:${this.state.topOffset}`,
            "left:0",
            "right:0",
            "bottom:0",
            "z-index:1039",
        ].join(";");
    }
}

export const chatbooOverlayService = {
    dependencies: ["action", "orm"],
    async start(env, { action, orm }) {
        let host = null;
        let appComponent = null;
        let pendingResolvers = [];
        const idSet = new Set();

        async function loadChatbooActionIds() {
            try {
                const rows = await orm.searchRead(
                    "ir.actions.client",
                    [["tag", "in", [...CHATBOO_TAGS]]],
                    ["id"],
                );
                for (const row of rows || []) {
                    if (row.id) {
                        idSet.add(row.id);
                    }
                }
            } catch (_) {
                // Without IDs, the Apps click by number is not recognised; retry on open.
            }
        }

        const notifyReady = () => {
            if (!appComponent) {
                return;
            }
            const resolvers = pendingResolvers.slice();
            pendingResolvers = [];
            for (const resolve of resolvers) {
                resolve(appComponent);
            }
        };

        const waitForApp = (timeoutMs = 15000) => new Promise((resolve, reject) => {
            if (appComponent) {
                resolve(appComponent);
                return;
            }
            const timer = setTimeout(() => {
                pendingResolvers = pendingResolvers.filter((r) => r !== onReady);
                reject(new Error("Chatboo: timeout waiting for ChatbooApp mount"));
            }, timeoutMs);
            const onReady = (comp) => {
                clearTimeout(timer);
                resolve(comp);
            };
            pendingResolvers.push(onReady);
        });

        const api = {
            registerHost(overlayHost) {
                host = overlayHost;
            },

            setAppComponent(comp) {
                appComponent = comp;
                notifyReady();
            },

            getAppComponent() {
                return appComponent;
            },

            waitForApp,

            isHidden() {
                return !host || !host.state.visible;
            },

            async open(context = {}) {
                if (!host) {
                    console.error("Chatboo: overlay host not registered yet");
                    return;
                }
                await host.show({ context });
            },

            async openFromTray() {
                if (!host) {
                    console.error("Chatboo: overlay host not registered yet");
                    return;
                }
                if (host.state.visible) {
                    host.hide();
                    return;
                }
                await host.show();
            },

            close() {
                host?.hide();
            },
        };

        const originalDoAction = action.doAction.bind(action);
        action.doAction = async function (actionRequest, options) {
            if (typeof actionRequest === "number" && !idSet.has(actionRequest) && !idSet.size) {
                await loadChatbooActionIds();
            }
            if (requestLooksLikeChatboo(actionRequest, idSet)) {
                const ctx = typeof actionRequest === "object"
                    ? parseActionContext(actionRequest)
                    : {};
                clearChatbooBadge();
                await api.open(ctx);
                return;
            }
            return originalDoAction(actionRequest, options);
        };

        await loadChatbooActionIds();
        return api;
    },
};

registry.category("services").add("chatboo_overlay", chatbooOverlayService);

registry.category("main_components").add("pns_ai_chatboo.ChatbooOverlayHost", {
    Component: ChatbooOverlayHost,
});
