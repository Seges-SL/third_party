/** @odoo-module **/
// Chatboo systray launcher (OWL2 / Odoo 17+).
// Singleton floating overlay — aligned with owl1 reference behaviour.

import { Component, onMounted, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { useBus } from "@web/core/utils/hooks";
import { rpc } from "@web/core/network/rpc";
import { _t } from "@web/core/l10n/translation";

class ChatbooSystrayItem extends Component {
    static template = "pns_ai_chatboo.ChatbooSystrayItem";
    static props = {};

    setup() {
        this.state = useState({ visible: false });
        this.chatbooOverlay = useService("chatboo_overlay");
        this.notification = useService("notification");

        onMounted(async () => {
            try {
                const result = await rpc("/chatboo/check_health", {});
                if (result && result.show_systray === false) {
                    // Ocultación intencionada (sin acceso IA): olvida el flag.
                    this.state.visible = false;
                    try { localStorage.removeItem("chatboo_has_access"); } catch (_) {}
                    return;
                }
                this.state.visible = true;
                // Recuerda el acceso para recuperar el icono si un futuro
                // check_health falla (el icono es una función crítica).
                try { localStorage.setItem("chatboo_has_access", "1"); } catch (_) {}
            } catch (_) {
                // Fail-closed: sin confirmación del servidor, no mostrar
                // Chatboo (evita localStorage viejo / error RPC sin carnet MCP).
                this.state.visible = false;
                try { localStorage.removeItem("chatboo_has_access"); } catch (_) {}
            }

            if (this.state.visible) {
                window.addEventListener("chatboo-auth-cue", (ev) => {
                    this._refreshAuthCue((ev && ev.detail) || {});
                });
                const hadAuth = await this._refreshAuthCue({ notify: false });
                if (!hadAuth) {
                    const stored = localStorage.getItem("chatboo_unread");
                    if (stored) {
                        this._showBadge(stored === "error" ? "error" : "info");
                    }
                }
            }
        });

        const busService = useService("bus_service");
        // Odoo 19 dropped the public "notification" event.
        this._chatbooSyncFromSubscribe = typeof busService.subscribe === "function";
        if (this._chatbooSyncFromSubscribe) {
            busService.subscribe("pns_chatboo_sync", (payload) => {
                this._onSyncPayload(payload);
            });
        }
        useBus(busService, "notification", (notifications) => {
            if (this._chatbooSyncFromSubscribe) {
                return;
            }
            this._onBusNotifications(notifications);
        });
    }

    _onSyncPayload(raw) {
        let payload = raw;
        if (raw && raw.payload !== undefined && raw.action === undefined) {
            payload = raw.payload;
        }
        if (typeof payload === "string") {
            try {
                payload = JSON.parse(payload);
            } catch (e) {
                return;
            }
        }
        const isAsyncDone = payload && (
            payload.type === "pns_chatboo_async_done" ||
            (payload.type === "pns_chatboo_sync" &&
                (payload.action === "async_done" || payload.action === "error")) ||
            payload.action === "async_done" || payload.action === "error"
        );
        if (!isAsyncDone) {
            return;
        }
        // Con auto-promoción todos los turnos avisan por bus; solo molestamos
        // (campanita) si el overlay está oculto o si hubo error.
        const isErr = payload.is_error || payload.action === "error";
        if (isErr) {
            this._showBadge("error");
            this._showChatbooNotification();
            return;
        }
        if (this._isOverlayHidden()) {
            this._refreshAuthCue({ notify: true, fallbackUnread: true });
        }
    }

    _onBusNotifications(notifications) {
        if (notifications && notifications.detail !== undefined && !Array.isArray(notifications)) {
            notifications = notifications.detail;
        }
        if (!notifications) {
            return;
        }
        const items = Array.isArray(notifications) ? notifications : [notifications];
        for (const notif of items) {
            let payload = notif;
            if (Array.isArray(notif) && notif.length === 2) {
                payload = notif[1];
            } else if (notif && notif.type && notif.payload !== undefined) {
                // Odoo 17+ entrega {type, payload}: nuestros datos van anidados.
                payload = notif.payload;
            }
            this._onSyncPayload(payload);
        }
    }

    _isOverlayHidden() {
        const ov = document.getElementById("o_chatboo_persistent_overlay");
        return !ov || ov.classList.contains("d-none") || ov.style.display === "none";
    }

    _showChatbooNotification() {
        this.notification.add(_t("New Chatboo response ready"), {
            title: "Chatboo AI",
            type: "info",
            sticky: false,
            className: "o_chatboo_async_toast",
        });
    }

    _showAuthNotification() {
        const now = Date.now();
        if (this._lastAuthToast && now - this._lastAuthToast < 8000) {
            return;
        }
        this._lastAuthToast = now;
        this.notification.add(_t("Chatboo is waiting for your confirmation"), {
            title: "Chatboo AI",
            type: "warning",
            sticky: false,
            className: "o_chatboo_async_toast",
        });
    }

    async _refreshAuthCue({ notify = false, fallbackUnread = false, forceHidden = false } = {}) {
        try {
            const res = await rpc("/pns_ai_mcp/verification/pending", {});
            const items = (res && res.items) || [];
            if (!forceHidden && !this._isOverlayHidden()) {
                return false;
            }
            if (items.length) {
                this._showBadge("auth");
                if (notify) {
                    this._showAuthNotification();
                }
                return true;
            }
            if (fallbackUnread) {
                this._showBadge("info");
                if (notify) {
                    this._showChatbooNotification();
                }
            }
            return false;
        } catch (_) {
            if (fallbackUnread && this._isOverlayHidden()) {
                this._showBadge("info");
                if (notify) {
                    this._showChatbooNotification();
                }
            }
            return false;
        }
    }

    async onClick(ev) {
        ev.preventDefault();
        ev.stopPropagation();
        this._clearBadge();
        try {
            await this.chatbooOverlay.openFromTray();
        } catch (err) {
            console.error("Chatboo: failed to open overlay", err);
        }
    }

    _showBadge(type) {
        const badge = document.querySelector(".o_chatboo_badge");
        if (badge) {
            badge.classList.remove("bg-danger", "bg-warning");
            if (type === "error") {
                badge.innerHTML = '<i class="fa fa-exclamation fw-bold"/>';
                badge.classList.add("bg-danger");
            } else if (type === "auth") {
                badge.innerHTML = '<i class="fa fa-bell-o"/>';
                badge.classList.add("bg-warning");
            } else {
                badge.innerHTML = '<i class="fa fa-bell-o"/>';
            }
            badge.style.display = "";
        }
        if (type !== "auth") {
            try {
                localStorage.setItem("chatboo_unread", type === "error" ? "error" : "1");
            } catch (_) {}
        }
    }

    _clearBadge() {
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
}

registry.category("systray").add("pns_ai_chatboo.ChatbooSystrayItem", {
    Component: ChatbooSystrayItem,
    sequence: 999,
});
