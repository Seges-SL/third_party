/** @odoo-module **/
// Overlay singleton de Chatboo montado en el árbol OWL principal (O19).
// El estado visible vive en el host (useState) para que OWL re-renderice en O19.

import { Component, onMounted, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import ChatbooApp from "./chatboo_app";

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
            openedViaMenu: false,
            chatMounted: false,
            topOffset: "46px",
        });
        this.overlay.registerHost(this);

        onMounted(() => {
            const navbar = document.querySelector(".o_main_navbar");
            this.state.topOffset = navbar ? `${navbar.offsetHeight}px` : "46px";
            if (navbar && !navbar.dataset.chatbooNavbarBound) {
                navbar.dataset.chatbooNavbarBound = "1";
                navbar.addEventListener("click", (navEv) => {
                    if (navEv.target.closest(".o_chatboo_systray_item")) {
                        return;
                    }
                    if (this.state.visible) {
                        this.hide();
                    }
                }, true);
            }
        });
    }

    async show({ viaMenu = false, context = {} } = {}) {
        if (!this.state.chatMounted) {
            this.state.chatMounted = true;
        }
        this.state.openedViaMenu = viaMenu;
        this.state.visible = true;

        const comp = await this.overlay.waitForApp();
        // Un frame: deja que action_service refleje la vista tras navegar y abrir.
        await new Promise((resolve) => requestAnimationFrame(resolve));
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
        // Tras quitar d-none OWL pinta en el siguiente frame; si no, el
        // textarea sigue oculto y focus() no deja el cursor en el prompt.
        await new Promise((resolve) => requestAnimationFrame(resolve));
        await new Promise((resolve) => requestAnimationFrame(resolve));
        if (comp && typeof comp._focusInput === "function") {
            comp._focusInput();
        } else {
            this._focusInput();
        }
        if (comp && typeof comp._restorePendingVerifications === "function") {
            await comp._restorePendingVerifications();
        }
    }

    hide() {
        this.state.visible = false;
        this.state.openedViaMenu = false;
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

    _focusInput() {
        requestAnimationFrame(() => {
            const overlay = document.getElementById("o_chatboo_persistent_overlay");
            if (!overlay || overlay.classList.contains("d-none")) {
                return;
            }
            const input = overlay.querySelector(
                ".o_chatboo_main_footer textarea.o_chatboo_prompt, textarea.o_chatboo_prompt"
            );
            if (input) {
                input.focus();
            }
        });
    }

    get overlayStyle() {
        return [
            "position:fixed",
            `top:${this.state.topOffset}`,
            "left:0",
            "right:0",
            "bottom:0",
            "z-index:1050",
        ].join(";");
    }
}

export const chatbooOverlayService = {
    start() {
        let host = null;
        let appComponent = null;
        let pendingResolvers = [];

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

        return {
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

            async openFromMenu(context = {}) {
                if (!host) {
                    console.error("Chatboo: overlay host not registered yet");
                    return;
                }
                await host.show({ viaMenu: true, context });
            },

            async openFromTray() {
                if (!host) {
                    console.error("Chatboo: overlay host not registered yet");
                    return;
                }
                if (host.state.openedViaMenu && host.state.visible) {
                    return;
                }
                if (host.state.visible) {
                    host.hide();
                    const currentHash = window.location.hash || "";
                    if (currentHash.indexOf("pns_ai_chatboo") !== -1) {
                        window.location.hash = "#home";
                    }
                    return;
                }
                await host.show({ viaMenu: false });
            },

            close() {
                host?.hide();
            },
        };
    },
};

registry.category("services").add("chatboo_overlay", chatbooOverlayService);

registry.category("main_components").add("pns_ai_chatboo.ChatbooOverlayHost", {
    Component: ChatbooOverlayHost,
});

registry.category("actions").add("chatboo.action", async (env, action) => {
    clearChatbooBadge();
    const ctx = parseActionContext(action);
    await env.services.chatboo_overlay.openFromMenu(ctx);
});
