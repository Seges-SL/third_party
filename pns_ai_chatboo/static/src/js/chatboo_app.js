/** @odoo-module **/
// Chatboo — cliente de chat conversacional (OWL2 / Odoo 17+/19).
// Reaprovecha el backend de pns_ai_chatboo (sesiones + endpoint SSE /chatboo/stream),
// que a su vez delega la inferencia en el motor AgentEngine de pns_ai_mcp.

import { Component, useState, useRef, useEffect, markup, onWillStart, onMounted, onWillUnmount, onPatched, xml } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { useBus } from "@web/core/utils/hooks";
import { rpc } from "@web/core/network/rpc";
import { _t } from "@web/core/l10n/translation";
import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import * as exportUtils from "./chatboo_export";
import {
    getSessionLocale,
    formatWallclock,
    formatContent as sharedFormatContent,
    formatMarkdown as sharedFormatMarkdown,
    isLikelyHtml as sharedIsLikelyHtml,
} from "./chatboo_formatters";

/** Odoo 19 bus: CustomEvent.detail. Odoo 17: array or {type, payload}. */
function _busNotificationList(raw) {
    if (!raw) {
        return [];
    }
    if (raw.detail !== undefined && !Array.isArray(raw)) {
        raw = raw.detail;
    }
    if (!raw) {
        return [];
    }
    return Array.isArray(raw) ? raw : [raw];
}

function _busNotificationPayload(notif) {
    let payload = notif;
    if (notif && typeof notif === "object" && notif.message && typeof notif.message === "object") {
        notif = notif.message;
        payload = notif;
    }
    if (Array.isArray(notif) && notif.length >= 2) {
        payload = notif[1];
    } else if (notif && typeof notif === "object" && notif.type && notif.payload !== undefined) {
        payload = notif.payload;
    }
    if (typeof payload === "string") {
        try {
            let parsed = payload;
            for (let i = 0; i < 3 && typeof parsed === "string"; i++) {
                parsed = JSON.parse(parsed);
            }
            payload = parsed;
        } catch (e) {
            return null;
        }
    }
    if (payload && typeof payload === "object" && !payload.type && notif && notif.type) {
        payload = Object.assign({ type: notif.type }, payload);
    }
    return payload;
}

const ChatbooSse = globalThis.ChatbooSse;

// Placeholder por defecto del input; se sustituye por la pista de argumentos
// (arg_hint) del skill cuando el usuario elige o teclea "/<code> ".
const DEFAULT_INPUT_PLACEHOLDER = _t(
    "Ask Chatboo... (/ for commands & skills, ↑↓ for history)"
);

/** Max visible lines for the multiline prompt (future: Settings). */
const CHATBOO_PROMPT_MAX_LINES = 10;

// Icono (FontAwesome 4, disponible en O14–O19) para el chip de un fichero según
// su mimetype y extensión. Devuelve solo la clase específica (p. ej. "fa-file-pdf-o");
// el consumidor antepone "fa ". Fallback genérico "fa-file-o".
function chatbooFileIcon(mimetype, name) {
    const mt = (mimetype || "").toLowerCase();
    const ext = (name || "").toLowerCase().split(".").pop();
    const isExt = (arr) => arr.indexOf(ext) !== -1;
    if (mt.startsWith("image/") || isExt(["png", "jpg", "jpeg", "gif", "webp", "bmp", "svg", "tif", "tiff"])) return "fa-file-image-o";
    if (mt === "application/pdf" || ext === "pdf") return "fa-file-pdf-o";
    if (mt.includes("spreadsheet") || mt.includes("excel") || mt === "text/csv" || isExt(["xls", "xlsx", "ods", "csv"])) return "fa-file-excel-o";
    if (mt.includes("word") || mt.includes("wordprocessing") || isExt(["doc", "docx", "odt", "rtf"])) return "fa-file-word-o";
    if (mt.includes("presentation") || mt.includes("powerpoint") || isExt(["ppt", "pptx", "odp"])) return "fa-file-powerpoint-o";
    if (mt.includes("zip") || mt.includes("compressed") || mt.includes("x-tar") || mt.includes("x-7z") || mt.includes("x-rar") || isExt(["zip", "rar", "7z", "tar", "gz", "bz2", "xz"])) return "fa-file-archive-o";
    if (mt.startsWith("audio/") || isExt(["mp3", "wav", "ogg", "flac", "m4a", "aac"])) return "fa-file-audio-o";
    if (mt.startsWith("video/") || isExt(["mp4", "mkv", "avi", "mov", "webm", "wmv"])) return "fa-file-video-o";
    if (mt.includes("json") || mt.includes("xml") || mt.includes("javascript") || mt.includes("html") || isExt(["json", "xml", "js", "ts", "py", "html", "css", "sh", "yml", "yaml", "sql"])) return "fa-file-code-o";
    if (mt.startsWith("text/") || isExt(["txt", "md", "log", "ini", "cfg"])) return "fa-file-text-o";
    return "fa-file-o";
}

/** Renderiza HTML server-side (Python) sin pasar por el sanitizador de t-out (O19). */
class ChatbooHtmlRenderer extends Component {
    static template = xml`<div class="o_chatboo_content" t-ref="root"/>`;
    static props = { html: { type: String, optional: true } };

    setup() {
        this.root = useRef("root");
        const paint = () => {
            if (this.root.el) {
                if (window.ChatbooDashboard && typeof window.ChatbooDashboard.destroyIn === "function") {
                    window.ChatbooDashboard.destroyIn(this.root.el);
                } else if (window.ChatbooCharts && typeof window.ChatbooCharts.destroyIn === "function") {
                    window.ChatbooCharts.destroyIn(this.root.el);
                }
                this.root.el.innerHTML = this.props.html || "";
                if (window.ChatbooDashboard && typeof window.ChatbooDashboard.hydrateContent === "function") {
                    window.ChatbooDashboard.hydrateContent(this.root.el);
                } else if (window.ChatbooCharts && typeof window.ChatbooCharts.hydrate === "function") {
                    window.ChatbooCharts.hydrate(this.root.el);
                }
                if (window.ChatbooSvgCards && typeof window.ChatbooSvgCards.hydrate === "function") {
                    window.ChatbooSvgCards.hydrate(this.root.el);
                }
            }
        };
        onMounted(paint);
        onPatched(paint);
    }
}

class ChatbooApp extends Component {
    static template = "pns_ai_chatboo.ChatbooApp";
    static components = { ChatbooHtmlRenderer };
    static props = {
        onAppReady: { type: Function, optional: true },
    };

    setup() {
        this.notification = useService("notification");
        this.dialog = useService("dialog");
        this.action = useService("action");
        this.messagesRef = useRef("messages");
        this.inputRef = useRef("input");
        this.fileInputRef = useRef("fileInput");
        this.slashMenuRef = useRef("slashMenu");

        this.state = useState({
            messages: [],            // {role, content(markup), raw, ts}
            currentInput: "",
            thinking: false,
            canCancel: false,          // hay un stream en curso abortable
            streamingPreview: null,  // markup | null
            streamingHtml: null,       // HTML server-side crudo (innerHTML)
            statusLabel: "",
            provider: _t("Connecting…"),
            providerName: "",
            providerModel: "",
            providerHost: "",
            connected: false,
            providers: [],
            selectedProviderId: null,
            providerMenuOpen: false,
            effectiveFormattingMode: null,
            canSaveRaw: false,
            currentSessionId: null,
            sessions: [],
            showSessionModal: false,
            selectedSessions: [],
            editingSessionId: null,
            editingSessionName: "",
            slashOpen: false,
            slashItems: [],
            slashIndex: 0,
            slashMode: "commands", // 'commands' | 'skills' | 'mode' | 'delete'
            inputPlaceholder: DEFAULT_INPUT_PLACEHOLDER,
            screenFocusLabel: "",
            screenFocusEnabled: true,
            screenContextSnapshot: null,
            pendingImages: [],       // imágenes pegadas (data URLs) a enviar en el turno
            pendingImageNames: [],   // nombres alineados por índice (null si es pegado del portapapeles)
            pendingFiles: [],        // ficheros de texto/datos adjuntos con el clip
            dragActive: false,       // overlay visual mientras se arrastran ficheros sobre el chat
            ttsSupported: false,
            ttsEnabled: false,
            promptMultiline: false,
            promptCollapsed: false,
        });
        useEffect(
            () => {
                this._scrollSlashActive();
            },
            () => [this.state.slashOpen, this.state.slashIndex],
        );

        this.promptMaxLines = CHATBOO_PROMPT_MAX_LINES;
        this.inputHistory = [];
        this.historyIndex = -1;
        this.skillsCache = null;
        this._skillsLoaded = false;
        this._skillsListInflight = null;
        this._skillsListGen = 0;
        this.canWriteSkills = false;
        this.skillCommandPrefix = "";
        this.skillCodePrefix = "";
        this._fx = null;
        this._cardWidthRatio = 0;
        this._defaultDisplayCurrency = "USD";
        this._sessionOccupancy = { used: 0, limit: 0 };
        this.dropHint = _t("Drop files to attach here");
        this.tipAttach = _t("Attach file");
        this.tipSend = _t("Send");
        this.tipRemoveImage = _t("Remove image");
        this.tipRemoveFile = _t("Remove file");
        this.tipTestConnection = _t("Test connection");
        this.tipChangeProvider = _t("Change provider");
        this.tipNewChat = _t("New chat");
        this.tipNew = _t("New");
        this.tipHistory = _t("History");
        this.tipThinking = _t("Thinking…");
        this.tipConnecting = _t("Connecting…");
        this.tipDownloadPdf = _t("Download as PDF");
        this.tipDownloadExcel = _t("Download as Excel");
        this.tipDownloadWord = _t("Download as Word");
        this.tipRestoreCardWidth = _t("Restore default width");
        this.tipDownloadFile = _t("Download");
        this.tipCopyContent = _t("Copy content");
        this.tipCopyMarkdown = _t("Copy as Markdown");
        this.tipCopyClipboard = _t("Copy to clipboard");
        this.tipOpenImage = _t("Open image");
        this.tipCancel = _t("Cancel");
        this.tipExpandPrompt = _t("Expand prompt");
        this.tipCollapsePrompt = _t("Collapse prompt");
        // Built-in "/" palette. Axis toggles live under /mode (like skills under
        // /skills). Typing /painter-… still finds them via prefix filter.
        this.builtinCommands = [
            { code: "skills", name: "Skills", description: _t("List the available skills"), kind: "builtin", argsPolicy: "none" },
            {
                code: "create-skill",
                name: "Create skill",
                description: _t(
                    "Capture a turn as an instance skill (extra, with you as author). "
                    + "Typing /create-skill fills the last chip (you can change it), then the slash name. "
                    + "Settings prefixes apply. Help: /create-skill ?"
                ),
                argHint: "VWVN slash-name  |  ? help",
                params: [
                    {
                        name: "turn_id",
                        type: "string",
                        desc: _t("4-character MCP turn id (chip). Required."),
                        default: _t("last turn"),
                    },
                    {
                        name: "name",
                        type: "string",
                        desc: _t("Slash name. Settings prefix is applied."),
                        default: "",
                    },
                ],
                kind: "builtin",
                deferArg: true,
                writerOnly: true,
                argsPolicy: "ask",
            },
            {
                code: "delete-skill",
                name: "Delete skill",
                description: _t(
                    "Delete a skill you created. Empty opens the picker. Help: /delete-skill ?"
                ),
                argHint: "slash-name  |  ? help",
                params: [
                    {
                        name: "name",
                        type: "string",
                        desc: _t("Slash of a skill you created. Stem or prefixed."),
                        default: _t("opens picker"),
                    },
                ],
                kind: "builtin",
                deferArg: true,
                writerOnly: true,
                argsPolicy: "ask",
            },
            {
                code: "rename-skill",
                name: "Rename skill",
                description: _t(
                    "Rename a skill you created. Empty opens the picker. Help: /rename-skill ?"
                ),
                argHint: "old-name new-name  |  ? help",
                params: [
                    {
                        name: "old",
                        type: "string",
                        desc: _t("Current slash (stem or prefixed)."),
                        default: "",
                    },
                    {
                        name: "new",
                        type: "string",
                        desc: _t("New slash name. Instance prefix is applied."),
                        default: "",
                    },
                ],
                kind: "builtin",
                deferArg: true,
                writerOnly: true,
                argsPolicy: "ask",
            },
            {
                code: "mode",
                name: "Mode",
                description: _t("Presentation modes (painter, footer, table/chart)"),
                kind: "builtin",
                argsPolicy: "none",
            },
            {
                code: "foot-laconic",
                name: "Foot laconic",
                description: _t("No footer after local tables"),
                placeholder: _t("Optional question…"),
                kind: "builtin",
                deferArg: true,
                argsPolicy: "none",
                folder: "mode",
            },
            {
                code: "foot-verbose",
                name: "Foot verbose",
                description: _t("Warm footer after local tables"),
                placeholder: _t("Optional question…"),
                kind: "builtin",
                deferArg: true,
                argsPolicy: "none",
                folder: "mode",
            },
            {
                code: "show-table",
                name: "Show table",
                description: _t("Table first (this session)"),
                placeholder: _t("Optional question…"),
                kind: "builtin",
                deferArg: true,
                argsPolicy: "none",
                folder: "mode",
            },
            {
                code: "show-chart",
                name: "Show chart",
                description: _t("Chart first (this session)"),
                placeholder: _t("Optional question…"),
                kind: "builtin",
                deferArg: true,
                argsPolicy: "none",
                folder: "mode",
            },
            {
                code: "painter-free",
                name: "Painter free",
                description: _t("The model owns the whole bubble this turn"),
                placeholder: _t("Optional question…"),
                kind: "builtin",
                deferArg: true,
                argsPolicy: "none",
                folder: "mode",
            },
            {
                code: "painter-local",
                name: "Painter local",
                description: _t("Chatboo composes tables this turn"),
                placeholder: _t("Optional question…"),
                kind: "builtin",
                deferArg: true,
                argsPolicy: "none",
                folder: "mode",
            },
        ];

        onWillStart(async () => {
            await this._checkHealth();
            await this._loadProviders();
            await this._initSessions();
            await this._ensureSkills();
        });
        onMounted(() => {
            this._scrollSoon();
            if (this.inputRef.el) {
                this.inputRef.el.focus();
            }
            if (this.props.onAppReady) {
                this.props.onAppReady(this);
            }
            this._setupRefLinkHandler();
            this._setupTtsClickAnchoring();
            this._applyCardWidthRatio(this._cardWidthRatio);
        });
        onWillUnmount(() => {
            this._teardownTtsClickAnchoring();
            if (this._unsubscribeChatbooSync) {
                this._unsubscribeChatbooSync();
                this._unsubscribeChatbooSync = null;
            }
        });

        const busService = useService("bus_service");
        // Odoo 19 dropped the public "notification" event. subscribe() is the
        // channel that still delivers pns_chatboo_sync (Odoo 17 and 19).
        this._chatbooSyncFromSubscribe = typeof busService.subscribe === "function";
        if (this._chatbooSyncFromSubscribe) {
            const onSync = (payload) => {
                this._onChatbooSyncPayload(payload);
            };
            busService.subscribe("pns_chatboo_sync", onSync);
            this._unsubscribeChatbooSync = () => {
                if (typeof busService.unsubscribe === "function") {
                    busService.unsubscribe("pns_chatboo_sync", onSync);
                }
            };
        }
        useBus(busService, "notification", (notifications) => {
            if (this._chatbooSyncFromSubscribe) {
                return;
            }
            this._processBusNotifications(notifications);
        });
    }

    // ──────────────────────────── Salud / proveedor ────────────────────────────

    async _checkHealth() {
        try {
            const res = await rpc("/chatboo/check_health", {});
            this._applyProviderHeader(res);
            this.state.connected = !!res.connected;
            this.state.canSaveRaw = !!res.can_save_raw;
            // Se guarda incluso sin rates: trae el motivo del fallo para el chip.
            this._fx = (res && res.fx) ? res.fx : null;
            this._defaultDisplayCurrency = (res && res.display_currency) || "USD";
            this._applyCardWidthRatio(res && res.card_width_ratio);
            this._initTtsUi();
            return res;
        } catch (e) {
            this.state.provider = _t("Offline");
            this.state.providerName = _t("Offline");
            this.state.providerModel = "";
            this.state.providerHost = "";
            this.state.connected = false;
            this._fx = null;
            this._initTtsUi();
            return null;
        }
    }

    _messagesCanvas() {
        return this.messagesRef && this.messagesRef.el;
    }

    _applyCardWidthRatio(ratio) {
        const api = window.ChatbooCardWidth;
        const root = this._messagesCanvas();
        const n = Number(ratio);
        this._cardWidthRatio = (Number.isFinite(n) && n > 0) ? n : 0;
        if (!api || !root) {
            return;
        }
        api.applyRatio(root, this._cardWidthRatio || api.DEFAULT_RATIO);
        api.relayoutCharts(root);
    }

    async _saveCardWidth(ratio) {
        const api = window.ChatbooCardWidth;
        const root = this._messagesCanvas();
        const stored = (api && root) ? api.applyRatio(root, ratio) : ratio;
        this._cardWidthRatio = stored;
        if (api) {
            api.relayoutCharts(root);
        }
        try {
            await rpc("/chatboo/prefs", { card_width_ratio: stored });
        } catch (e) { /* keep in-memory width */ }
    }

    _resetCardWidth(ev) {
        if (ev) {
            ev.preventDefault();
            ev.stopPropagation();
        }
        const api = window.ChatbooCardWidth;
        const root = this._messagesCanvas();
        if (api && root) {
            api.applyRatio(root, api.DEFAULT_RATIO);
            api.relayoutCharts(root);
        }
        this._cardWidthRatio = 0;
        rpc("/chatboo/prefs", { card_width_ratio: 0 }).catch(() => {});
    }

    _onCardResizeStart(ev) {
        const api = window.ChatbooCardWidth;
        const handle = ev.currentTarget;
        const card = handle && handle.closest && handle.closest(".o_chatboo_message");
        const root = this._messagesCanvas();
        if (!api || !card || !root) {
            return;
        }
        ev.preventDefault();
        ev.stopPropagation();
        handle.classList.add("is-dragging");
        const startX = ev.clientX;
        const startW = card.getBoundingClientRect().width;
        const onMove = (e) => {
            api.applyPx(root, startW + (e.clientX - startX));
            api.relayoutCharts(root);
        };
        const onUp = () => {
            handle.classList.remove("is-dragging");
            document.removeEventListener("pointermove", onMove);
            document.removeEventListener("pointerup", onUp);
            this._saveCardWidth(api.ratioFromRoot(root));
        };
        document.addEventListener("pointermove", onMove);
        document.addEventListener("pointerup", onUp);
    }

    _initTtsUi() {
        const tts = window.__chatbooTts;
        this.state.ttsSupported = !!(tts && tts.isSupported());
        this.state.ttsEnabled = this.state.ttsSupported && !!(tts && tts.isEnabled());
    }

    _setupTtsClickAnchoring() {
        const tts = window.__chatbooTts;
        const el = this.el;
        if (!tts || !el || this._ttsRootEl) {
            return;
        }
        this._ttsRootEl = el;
        tts.bindRoot(el);
    }

    _teardownTtsClickAnchoring() {
        const tts = window.__chatbooTts;
        if (tts && this._ttsRootEl) {
            tts.unbindRoot(this._ttsRootEl);
        }
        this._ttsRootEl = null;
    }

    _toggleTts() {
        const tts = window.__chatbooTts;
        if (!tts || !this.state.ttsSupported) {
            return;
        }
        this.state.ttsEnabled = tts.toggle();
    }

    _maybeSpeakLastAssistant() {
        const tts = window.__chatbooTts;
        if (!tts || !tts.isEnabled()) {
            return;
        }
        for (let i = this.state.messages.length - 1; i >= 0; i--) {
            const m = this.state.messages[i];
            if (m.role !== "assistant") {
                continue;
            }
            if (m.local_ack) {
                return;
            }
            tts.speakMessage(m);
            return;
        }
    }

    _applyProviderHeader(res) {
        const fallback = res.provider || _t("Unknown");
        this.state.provider = fallback;
        this.state.providerName = fallback;
        if (res.alias) {
            this.state.providerHost = "";
            this.state.providerModel = res.alias;
            return;
        }
        this.state.providerModel = res.model || "";
        this.state.providerHost = res.host || "";
        if (!this.state.providerModel && fallback.includes(" → ")) {
            const parts = fallback.split(" → ");
            this.state.providerHost = parts[0];
            this.state.providerModel = parts.slice(1).join(" → ");
        }
    }

    _syncSelectedProviderHeader() {
        const sel = this.state.providers.find((p) => p.id === this.state.selectedProviderId);
        if (!sel) {
            return;
        }
        if (sel.alias) {
            this.state.providerHost = "";
            this.state.providerModel = sel.alias;
        } else {
            this.state.providerModel = sel.model || sel.name || "";
            this.state.providerHost = sel.host || "";
        }
        this.state.providerName = sel.display || this.state.providerName;
        this.state.provider = this.state.providerName;
    }

    async _loadProviders() {
        try {
            const providerRes = await rpc("/chatboo/providers", {});
            if (providerRes && providerRes.status === "ok") {
                this.state.providers = providerRes.providers || [];
                this._refreshUsageChips();
                const savedProvider = parseInt(localStorage.getItem("chatboo_provider_id"), 10);
                if (savedProvider && this.state.providers.some((p) => p.id === savedProvider)) {
                    this.state.selectedProviderId = savedProvider;
                } else {
                    this.state.selectedProviderId = providerRes.default_provider_id
                        || (this.state.providers[0] || {}).id
                        || null;
                }
                this._syncSelectedProviderHeader();
            }
        } catch (e) {
            console.warn("Chatboo: failed to load providers:", e);
        }
    }

    async _testConnection() {
        const res = await this._checkHealth();
        if (this.state.connected) {
            this.notification.add(_t("Connection OK."), { type: "success" });
        } else {
            // Server-provided message (single source, shared with OWL1); fall
            // back to a generic one only if the health check itself failed.
            const msg = (res && res.message) || _t("Could not connect to the AI provider.");
            this.notification.add(msg, { type: "danger" });
        }
    }

    _toggleProviderMenu() {
        if (this.state.providers.length <= 1) {
            return;
        }
        this.state.providerMenuOpen = !this.state.providerMenuOpen;
    }

    _closeProviderMenu() {
        this.state.providerMenuOpen = false;
    }

    _selectProvider(id) {
        this.state.selectedProviderId = id || null;
        if (id) {
            localStorage.setItem("chatboo_provider_id", String(id));
        } else {
            localStorage.removeItem("chatboo_provider_id");
        }
        this._syncSelectedProviderHeader();
        this.state.providerMenuOpen = false;
    }

    // ──────────────────────────── Sesiones ────────────────────────────

    _focusInput() {
        // Foco diferido a la caja de prompt: tras el repintado de OWL (cierre del
        // modal de histórico o carga de una sesión) el foco se iría al body; lo
        // devolvemos al input para poder escribir sin tener que clicar antes.
        requestAnimationFrame(() => {
            const overlay = document.getElementById("o_chatboo_persistent_overlay");
            if (overlay && (
                overlay.style.display === "none"
                || overlay.classList.contains("d-none")
            )) {
                return;
            }
            const el = this.inputRef && this.inputRef.el;
            if (!el) {
                return;
            }
            try {
                el.focus({ preventScroll: true });
            } catch (_) {
                el.focus();
            }
        });
    }

    async _initSessions() {
        await this._refreshSessions();
        if (this.state.currentSessionId) {
            await this._loadSession(this.state.currentSessionId);
        } else {
            await this._createNewSession(false);
        }

        // Catch-up: turnos asíncronos que terminaron mientras no mirábamos (p.ej.
        // tras un F5 o un reinicio). La fuente de verdad es la BD; si hay jobs
        // done/error no vistos, recargamos la sesión activa para verlos.
        // Timeout: un poll/reclaim colgado no debe bloquear la apertura.
        try {
            const _poll = await Promise.race([
                rpc("/chatboo/async/poll", {}),
                new Promise((resolve) => setTimeout(
                    () => resolve({ status: "timeout", pending: [], running: [] }),
                    5000,
                )),
            ]);
            if (_poll && _poll.status === "ok") {
                if (_poll.pending && _poll.pending.length && this.state.currentSessionId) {
                    await this._loadSession(this.state.currentSessionId);
                }
                // Turno EN CURSO en esta sesión: el worker sigue en el servidor.
                // Mostramos "pensando…" y refrescamos al terminar (la página solo
                // se re-engancha, no ejecuta nada).
                const _run = (_poll.running || []).find(
                    (j) => j.session_id === this.state.currentSessionId);
                if (_run) {
                    this._resumeRunningTurn(_run.request_id, this.state.currentSessionId);
                }
            }
        } catch (_e) {
            // no crítico
        }
    }

    async _refreshSessions() {
        try {
            const res = await rpc("/chatboo/sessions/list", {});
            if (res.status === "ok") {
                this.state.sessions = (res.sessions || []).map((session) => {
                    const row = { ...session };
                    if (row.last_used_date) {
                        try {
                            row.formatted_date = new Date(row.last_used_date).toLocaleDateString(getSessionLocale());
                        } catch (e) {
                            row.formatted_date = row.last_used_date;
                        }
                    }
                    return row;
                });
                if (!this.state.currentSessionId) {
                    const sessions = res.sessions || [];
                    this.state.currentSessionId = res.active_session_id
                        || (sessions.length ? sessions[0].id : null);
                }
            }
        } catch (e) {
            // sin sesiones: se creará una nueva
        }
    }

    async _loadSession(sessionId) {
        try {
            const res = await rpc("/chatboo/sessions/load", { session_id: sessionId });
            if (res.status !== "ok") {
                return;
            }
            const s = res.session;
            this.state.currentSessionId = s.id;
            this._resetSessionOccupancy();
            this.state.messages = (s.messages || []).map((m) => this._mapStoredMessage(m));
            this.inputHistory = (s.input_history || []).slice();
            this.historyIndex = -1;
            this._scrollSoon();
            this._fulfillPendingExportsInView();
        } catch (e) {
            this.notification.add(_t("Could not load the session."), { type: "danger" });
        }
    }

    _resumeRunningTurn(requestId, sessionId) {
        // Tras un F5 con un turno en curso: el worker sigue trabajando en el
        // servidor. Mostramos "pensando…" y sondeamos suave hasta que termine,
        // entonces refrescamos la sesión. El bus async_done hace lo mismo si
        // llega antes; ambos son idempotentes. La página solo se re-engancha.
        this.state.thinking = true;
        this.state.canCancel = true;
        this._resumeReqId = requestId;
        this._lastStreamRequestId = requestId;
        const poll = async () => {
            if (this._resumeReqId !== requestId) {
                return;  // reemplazado por un nuevo turno o ya resuelto
            }
            let res = null;
            try {
                res = await rpc("/chatboo/async/poll", { session_id: sessionId });
            } catch (_e) {
                setTimeout(poll, 2500);
                return;
            }
            const stillRunning = (res && res.running || []).some(
                (j) => j.request_id === requestId);
            if (stillRunning) {
                setTimeout(poll, 2000);
                return;
            }
            // Terminó (o fue reclamado): refrescar y limpiar.
            this._resumeReqId = null;
            if (sessionId === this.state.currentSessionId) {
                await this._loadSession(sessionId);
                this.state.thinking = false;
                this.state.canCancel = false;
            }
        };
        setTimeout(poll, 1500);
    }

    async _createNewSession(clearUI = false) {
        try {
            const res = await rpc("/chatboo/sessions/create", {});
            if (res.status === "ok") {
                this.state.currentSessionId = res.session.id;
                if (clearUI) {
                    this._resetSessionOccupancy();
                    this.state.messages = [];
                    this.inputHistory = [];
                    this.historyIndex = -1;
                }
                await this._refreshSessions();
                this._focusInput();
            }
        } catch (e) {
            this.notification.add(_t("Could not create the session."), { type: "danger" });
        }
    }

    async _showSessions() {
        this.state.selectedSessions = [];
        await this._refreshSessions();
        this.state.showSessionModal = true;
    }

    _closeSessionsModal() {
        this.state.showSessionModal = false;
    }

    async _selectSession(sessionId) {
        await this._loadSession(sessionId);
        this.state.showSessionModal = false;
        this._focusInput();
    }

    _toggleSessionSelection(sessionId) {
        const idx = this.state.selectedSessions.indexOf(sessionId);
        if (idx === -1) {
            this.state.selectedSessions.push(sessionId);
        } else {
            this.state.selectedSessions.splice(idx, 1);
        }
    }

    _toggleAllSessions(ev) {
        if (ev.target.checked) {
            this.state.selectedSessions = this.state.sessions.map((s) => s.id);
        } else {
            this.state.selectedSessions = [];
        }
    }

    async _bulkDeleteSessions() {
        if (!this.state.selectedSessions.length) {
            return;
        }
        if (!confirm(_t("Are you sure you want to delete the selected sessions (%s)?").replace("%s", this.state.selectedSessions.length))) {
            return;
        }
        try {
            const res = await rpc("/chatboo/sessions/bulk_delete", { session_ids: this.state.selectedSessions });
            if (res.status === "ok") {
                if (this.state.selectedSessions.includes(this.state.currentSessionId)) {
                    this.state.currentSessionId = null;
                    this._resetSessionOccupancy();
                    this.state.messages = [];
                    this.inputHistory = [];
                }
                this.state.selectedSessions = [];
                await this._refreshSessions();
            }
        } catch (e) {
            this.notification.add(_t("Could not delete the sessions."), { type: "danger" });
        }
    }

    _startRenameSession(sessionId, currentName) {
        this.state.editingSessionId = sessionId;
        this.state.editingSessionName = currentName;
    }

    _cancelRenameSession() {
        this.state.editingSessionId = null;
        this.state.editingSessionName = "";
    }

    async _saveRenameSession() {
        if (!this.state.editingSessionId || !this.state.editingSessionName.trim()) {
            return;
        }
        try {
            const res = await rpc("/chatboo/sessions/rename", {
                session_id: this.state.editingSessionId,
                new_name: this.state.editingSessionName.trim(),
            });
            if (res.status === "ok") {
                await this._refreshSessions();
                this._cancelRenameSession();
            }
        } catch (e) {
            this.notification.add(_t("Could not rename the session."), { type: "danger" });
        }
    }

    _onRenameInputKeydown(ev) {
        if (ev.key === "Enter") {
            this._saveRenameSession();
        } else if (ev.key === "Escape") {
            this._cancelRenameSession();
        }
    }

    async _deleteSession(sessionId, ev) {
        if (ev) {
            ev.stopPropagation();
        }
        try {
            await rpc("/chatboo/sessions/delete", { session_id: sessionId });
            const wasCurrent = sessionId === this.state.currentSessionId;
            if (wasCurrent) {
                this.state.currentSessionId = null;
                this._resetSessionOccupancy();
                this.state.messages = [];
                this.inputHistory = [];
            }
            await this._refreshSessions();
            if (wasCurrent) {
                if (this.state.sessions.length) {
                    await this._loadSession(this.state.sessions[0].id);
                } else {
                    await this._createNewSession(true);
                }
            }
        } catch (e) {
            this.notification.add(_t("Could not delete the session."), { type: "danger" });
        }
    }

    async _persist() {
        if (!this.state.currentSessionId) {
            return;
        }
        // Conservar images/files (chips ir.attachment). Sin ellos un save del
        // cliente pisaba el histórico y las fotos «desaparecían» en O14/O19.
        const messages = this.state.messages.map((m) => {
            const out = {
                role: m.role,
                content: m.raw,
                timestamp: m.ts,
                meta: m.meta || null,
            };
            const imgs = (m.images || [])
                .map((it) => (it && typeof it === "object"
                    ? { url: it.url || "", name: it.name || null }
                    : { url: String(it || ""), name: null }))
                .filter((it) => it.url && !String(it.url).startsWith("data:"));
            const files = (m.files || [])
                .map((f) => (f && typeof f === "object"
                    ? {
                        name: f.name || null,
                        url: f.url || "",
                        mimetype: f.mimetype || null,
                        size: f.size || null,
                        pending: !!f.pending,
                        fulfill: f.fulfill || null,
                    }
                    : null))
                .filter((f) => f && (f.url || f.name));
            if (imgs.length) {
                out.images = imgs;
            }
            if (files.length) {
                out.files = files;
            }
            if (m.clip_data) {
                out.clip_data = m.clip_data;
            }
            if (m.offtopic) {
                out.offtopic = true;
            }
            if (m.local_ack) {
                out.local_ack = true;
            }
            if (m.verification_ack || (m.meta && m.meta.verification_ack)) {
                out.verification_ack = true;
            }
            const recs = (m.meta && m.meta.records) || m.records;
            if (recs && recs.length) {
                out.records = recs;
                out.meta = out.meta || {};
                out.meta.records = recs;
            }
            const userPrompt = m.user_prompt || (m.meta && m.meta.user_prompt) || "";
            if (userPrompt) {
                out.user_prompt = userPrompt;
            }
            if (m.backend_history && m.backend_history.length) {
                out.backend_history = m.backend_history;
            }
            return out;
        });
        try {
            await rpc("/chatboo/sessions/save", {
                session_id: this.state.currentSessionId,
                messages: messages,
                input_history: this.inputHistory,
            });
        } catch (e) {
            // persistencia best-effort; no rompe el chat
        }
    }

    // ──────────────────────────── Screen focus (artefacto debajo del overlay) ──

    _refreshScreenFocus() {
        const SC = globalThis.ChatbooScreenContext;
        if (!SC || !SC.get) {
            this.state.screenFocusLabel = "";
            this.state.screenContextSnapshot = null;
            return null;
        }
        const ctx = SC.get(this.env);
        this.state.screenFocusLabel = SC.formatChipLabel(ctx) || "";
        this.state.screenContextSnapshot =
            SC.hasSendableContext && SC.hasSendableContext(ctx) ? ctx : null;
        return ctx;
    }

    _captureScreenContextForSend() {
        if (!this.state.screenFocusEnabled) {
            return null;
        }
        // Siempre re-leer al enviar; el snapshot del último open del tray es la
        // fuente para el chip, pero el turno usa la pantalla actual.
        this._refreshScreenFocus();
        return this.state.screenContextSnapshot;
    }

    toggleScreenFocus() {
        this.state.screenFocusEnabled = !this.state.screenFocusEnabled;
        if (this.state.screenFocusEnabled) {
            this._refreshScreenFocus();
        } else {
            this.state.screenContextSnapshot = null;
        }
    }

    get screenFocusTitle() {
        return this.state.screenFocusEnabled
            ? _t("Screen context active — click to ignore this chat")
            : _t("Screen context off — click to re-enable");
    }

    get ttsTitle() {
        return this.state.ttsEnabled
            ? _t("Click on the chat to play")
            : _t("Enable read-aloud");
    }

    get tipPromptResize() {
        return this.state.promptCollapsed ? this.tipExpandPrompt : this.tipCollapsePrompt;
    }

    _promptNewlineCount(text) {
        return String(text || "").split("\n").length;
    }

    /**
     * Vertical offset of the caret inside a wrapping textarea (mirror div).
     * Used so ArrowUp/Down history only fires on the first/last *visual* line,
     * not merely the first hard ``\\n`` segment.
     */
    _textareaCaretTop(el, position) {
        if (!el || typeof position !== "number") {
            return 0;
        }
        const style = window.getComputedStyle(el);
        const mirror = document.createElement("div");
        const props = [
            "boxSizing", "width", "fontSize", "fontFamily", "fontWeight",
            "fontStyle", "letterSpacing", "textTransform", "wordSpacing",
            "textIndent", "paddingTop", "paddingRight", "paddingBottom",
            "paddingLeft", "borderTopWidth", "borderRightWidth",
            "borderBottomWidth", "borderLeftWidth", "lineHeight",
            "whiteSpace", "wordWrap", "wordBreak", "overflowWrap",
            "tabSize",
        ];
        mirror.style.cssText =
            "position:absolute;top:0;left:-9999px;visibility:hidden;"
            + "white-space:pre-wrap;word-wrap:break-word;overflow-wrap:break-word;";
        for (let i = 0; i < props.length; i++) {
            const p = props[i];
            try {
                mirror.style[p] = style[p];
            } catch (_e) { /* ignore */ }
        }
        mirror.style.width = el.clientWidth + "px";
        const text = String(el.value || "");
        mirror.textContent = text.slice(0, position);
        const marker = document.createElement("span");
        marker.textContent = "|";
        mirror.appendChild(marker);
        document.body.appendChild(mirror);
        const top = marker.offsetTop;
        document.body.removeChild(mirror);
        return top;
    }

    _promptLineHeight(el) {
        const cs = window.getComputedStyle(el);
        let lineH = parseFloat(cs.lineHeight);
        if (!isFinite(lineH) || lineH <= 0) {
            lineH = (parseFloat(cs.fontSize) || 16) * 1.35;
        }
        return lineH;
    }

    _promptCaretOnFirstLine(el) {
        if (!el || typeof el.selectionStart !== "number") {
            return true;
        }
        try {
            const lineH = this._promptLineHeight(el);
            const top = this._textareaCaretTop(el, el.selectionStart);
            const top0 = this._textareaCaretTop(el, 0);
            return (top - top0) < lineH * 0.6;
        } catch (_e) {
            const pos = el.selectionStart;
            return String(el.value || "").slice(0, pos).indexOf("\n") === -1;
        }
    }

    _promptCaretOnLastLine(el) {
        if (!el || typeof el.selectionEnd !== "number") {
            return true;
        }
        try {
            const lineH = this._promptLineHeight(el);
            const top = this._textareaCaretTop(el, el.selectionEnd);
            const topEnd = this._textareaCaretTop(
                el, String(el.value || "").length,
            );
            return Math.abs(topEnd - top) < lineH * 0.6;
        } catch (_e) {
            const pos = el.selectionEnd;
            return String(el.value || "").slice(pos).indexOf("\n") === -1;
        }
    }

    _syncPromptHeight() {
        const el = this.inputRef && this.inputRef.el;
        if (!el) {
            return;
        }
        const text = el.value != null ? el.value : (this.state.currentInput || "");
        const lines = this._promptNewlineCount(text);
        const multiline = lines > 1;
        this.state.promptMultiline = multiline;
        if (!multiline) {
            this.state.promptCollapsed = false;
        }
        const cs = window.getComputedStyle(el);
        const minH = parseFloat(cs.minHeight) || 42;
        let lineH = parseFloat(cs.lineHeight);
        if (!isFinite(lineH) || lineH <= 0) {
            lineH = (parseFloat(cs.fontSize) || 16) * 1.35;
        }
        const padY = (parseFloat(cs.paddingTop) || 0) + (parseFloat(cs.paddingBottom) || 0);
        const borderY = (parseFloat(cs.borderTopWidth) || 0) + (parseFloat(cs.borderBottomWidth) || 0);
        // Cap by real text lines (not the 1-line control chrome height).
        const maxH = borderY + padY + lineH * CHATBOO_PROMPT_MAX_LINES;
        el.style.maxHeight = maxH + "px";
        if (!multiline || this.state.promptCollapsed) {
            el.style.height = minH + "px";
            el.style.overflowY = multiline ? "auto" : "hidden";
            return;
        }
        el.style.height = "auto";
        el.style.overflowY = "hidden";
        const natural = el.scrollHeight;
        el.style.height = Math.min(Math.max(natural, minH), maxH) + "px";
        el.style.overflowY = natural > maxH ? "auto" : "hidden";
    }

    _togglePromptCollapsed() {
        if (!this.state.promptMultiline) {
            return;
        }
        this.state.promptCollapsed = !this.state.promptCollapsed;
        this._syncPromptHeight();
        if (this.inputRef && this.inputRef.el) {
            this.inputRef.el.focus();
        }
    }

    _insertPromptNewline(el) {
        if (!el) {
            return;
        }
        const start = typeof el.selectionStart === "number" ? el.selectionStart : el.value.length;
        const end = typeof el.selectionEnd === "number" ? el.selectionEnd : start;
        const val = el.value || "";
        const next = val.slice(0, start) + "\n" + val.slice(end);
        this.state.promptCollapsed = false;
        this.state.currentInput = next;
        this._updateSlashSuggestions(next);
        this._syncArgPlaceholder(next);
        Promise.resolve().then(() => {
            const node = this.inputRef && this.inputRef.el;
            if (!node) {
                return;
            }
            node.focus();
            const caret = start + 1;
            try {
                node.setSelectionRange(caret, caret);
            } catch (eSel) { /* ignore */ }
            this._syncPromptHeight();
        });
    }

    // ──────────────────────────── Envío + streaming SSE ────────────────────────────

    async _sendMessage() {
        const text = (this.state.currentInput || "").trim();
        const images = (this.state.pendingImages || []).slice();
        const imageNames = (this.state.pendingImageNames || []).slice();
        const files = (this.state.pendingFiles || []).slice();
        if ((!text && !images.length && !files.length) || this.state.thinking) {
            return;
        }

        // Comandos built-in (/skills, /create-skill): se resuelven
        // en el cliente, no se envían como turno al LLM. Solo aplican a texto puro.
        if (!images.length && !files.length) {
            const builtin = this._matchBuiltinCommand(text);
            if (builtin) {
                await this._runBuiltinCommand(builtin);
                return;
            }
        }

        this.state.messages.push({
            role: "user",
            content: this._formatContent(text),
            raw: text,
            // Chips {url, name} en vivo (name=null si es pegado del portapapeles);
            // tras recargar, el worker devuelve la misma forma {url, name}.
            images: images.map((u, i) => ({ url: u, name: imageNames[i] || null })),
            // Chips locales (nombre) del turno en vivo; tras recargar, el worker
            // devuelve {name, url} descargables.
            files: files.map((f) => ({ name: f.name, mimetype: f.mimetype })),
            ts: this._now(),
        });
        if (text) {
            this.inputHistory.push(text);
        }
        this.historyIndex = -1;
        this.state.currentInput = "";
        this.state.promptMultiline = false;
        this.state.promptCollapsed = false;
        this.state.pendingImages = [];
        this.state.pendingImageNames = [];
        this.state.pendingFiles = [];
        this.state.slashOpen = false;
        this.state.slashItems = [];
        this._resetInputPlaceholder();
        Promise.resolve().then(() => this._syncPromptHeight());

        // El último mensaje (el del usuario que acabamos de añadir) se envía como
        // `message`, así que se excluye del history para no duplicarlo. Imágenes y
        // ficheros viajan solo en este turno (no entran en el historial).
        await this._runAssistantTurn(text, {
            excludeTail: 1,
            images: images.length ? images : null,
            image_names: imageNames.length ? imageNames : null,
            files: files.length ? files : null,
        });

        if (this.inputRef.el) {
            this.inputRef.el.focus();
        }
    }

    // Cancela el turno en curso (botón de la burbuja "Thinking…").
    // Corta el preview SSE local y pide al worker que pare el job en servidor.
    _cancelStream() {
        const rid = this._lastStreamRequestId || this._resumeReqId || null;
        if (!this._streamAbort && !rid && !this.state.currentSessionId) {
            return;
        }
        this.dialog.add(ConfirmationDialog, {
            title: _t("Cancel generation?"),
            body: _t(
                "The response in progress will be stopped. Any text received so far may be kept in the chat."
            ),
            confirm: () => this._abortStream(rid),
            confirmLabel: _t("Yes, cancel"),
            cancelLabel: _t("Keep waiting"),
        });
    }

    _abortStream(requestId) {
        const rid = requestId || this._lastStreamRequestId || this._resumeReqId || null;
        this._streamAbortReason = "user";
        if (this._streamAbort) {
            try {
                this._streamAbort.abort();
            } catch (e) {
                /* noop */
            }
        }
        // Cancelar el job del servidor (también tras F5 / reenganche sin SSE).
        const sid = this.state.currentSessionId || null;
        const payload = {};
        if (rid) {
            payload.request_id = rid;
        }
        if (sid) {
            payload.session_id = sid;
        }
        if (rid || sid) {
            rpc("/chatboo/async/cancel", payload).catch(() => {});
        }
        this._resumeReqId = null;
        if (!this._sseOwnsThinking) {
            this.state.thinking = false;
            this.state.canCancel = false;
        }
    }

    async _runAssistantTurn(messageText, opts) {
        // Ejecuta un turno de la IA y añade su respuesta. NO añade burbuja de usuario:
        // sirve tanto para mensajes escritos como para el resultado de una escritura
        // confirmada/cancelada (opción B: la IA informa del resultado).
        opts = opts || {};
        if (this.state.thinking) {
            return;
        }
        // Dueño local del spinner: el bus (async_done del turno anterior, etc.)
        // NO debe apagar thinking mientras dura este SSE. Ver _onBusNotification.
        this._sseOwnsThinking = true;
        this.state.thinking = true;
        this.state.canCancel = true;
        this.state.effectiveFormattingMode = null;
        this.state.streamingPreview = null;
        this.state.streamingHtml = null;
        this.state.statusLabel = "";
        this._scrollSoon();

        let lastMeta = null;
        try {
            const startTime = new Date();
            const history = this._historyForApi(opts.excludeTail || 0);

            let acc = "";
            const streamState = ChatbooSse.createStreamState();
            const _t0 = (typeof performance !== "undefined" ? performance.now() : Date.now());
            let _tFirst = null;
            // Watchdog de inactividad + cancelación manual: si el proveedor se queda
            // mudo STREAM_IDLE_MS (o un reinicio deja el socket colgado), abortamos el
            // fetch para que el turno no se quede en "Thinking…" eterno. El botón de
            // cancelar comparte este AbortController (razón 'user').
            const STREAM_IDLE_MS = 120000;
            const controller = new AbortController();
            this._streamAbort = controller;
            this._streamAbortReason = null;
            this.state.canCancel = true;
            let idleTimer = null;
            const armIdle = () => {
                if (idleTimer) { clearTimeout(idleTimer); }
                idleTimer = setTimeout(() => {
                    this._streamAbortReason = this._streamAbortReason || 'idle';
                    try { controller.abort(); } catch (e) { /* noop */ }
                }, STREAM_IDLE_MS);
            };
            try {
                const screenContext = this._captureScreenContextForSend();
                const payload = {
                    session_id: this.state.currentSessionId,
                    message: messageText,
                    history: history,
                    provider_id: this.state.selectedProviderId || null,
                };
                if (screenContext) {
                    payload.screen_context = screenContext;
                }
                if (opts.images && opts.images.length) {
                    payload.images = opts.images;
                }
                if (opts.image_names && opts.image_names.length) {
                    payload.image_names = opts.image_names;
                }
                if (opts.files && opts.files.length) {
                    payload.files = opts.files;
                }
                const resp = await fetch("/chatboo/stream", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    signal: controller.signal,
                    body: JSON.stringify(payload),
                });
                if (!resp.ok || !resp.body) {
                    throw new Error("HTTP " + resp.status);
                }
                const reader = resp.body.getReader();
                const decoder = new TextDecoder();
                let buffer = "";
                let reading = true;
                armIdle();
                while (reading) {
                    const { done, value } = await reader.read();
                    if (done) {
                        reading = false;
                        break;
                    }
                    armIdle();
                    buffer += decoder.decode(value, { stream: true });
                    let sep;
                    while ((sep = buffer.indexOf("\n\n")) >= 0) {
                        const chunk = buffer.slice(0, sep);
                        buffer = buffer.slice(sep + 2);
                        const evt = ChatbooSse.parseSseBlock(chunk);
                        if (!evt) {
                            continue;
                        }
                        if (evt.event === "token" && evt.content) {
                            if (_tFirst === null) {
                                _tFirst = (typeof performance !== "undefined" ? performance.now() : Date.now());
                            }
                            ChatbooSse.applyToken(streamState, evt.content, (t) => this._formatStreamFooter(t));
                            acc = streamState.acc;
                            this._scheduleStreamPreview(streamState);
                        } else if (evt.event === "replace" && evt.content) {
                            if (_tFirst === null) {
                                _tFirst = (typeof performance !== "undefined" ? performance.now() : Date.now());
                            }
                            ChatbooSse.applyReplace(streamState, evt.content);
                            acc = streamState.acc;
                            this._flushStreamPreview(streamState);
                        } else if (evt.event === "status") {
                            this.state.statusLabel = evt.message || evt.label || "";
                            this._scrollSoon();
                        } else if (evt.event === "meta") {
                            // Auto-promoción: el worker nos dice qué job/sesión está
                            // ejecutando este turno. Guardamos el request_id para luego
                            // ignorar el aviso de bus de ESTE turno (ya lo vemos en vivo).
                            this._lastStreamRequestId = evt.request_id || null;
                            this._lastStreamSessionId = evt.session_id || this._lastStreamSessionId;
                            if (evt.session_id && !this.state.currentSessionId) {
                                this.state.currentSessionId = evt.session_id;
                            }
                        } else if (evt.event === "done") {
                            // Metadatos del cierre: modelo/proveedor que respondió + tokens reales.
                            lastMeta = evt;
                            if (evt.painter === "painter-free"
                                    || evt.painter === "painter-local") {
                                this.state.effectiveFormattingMode = evt.painter;
                            }
                        } else if (evt.event === "choice" && evt.choice_id) {
                            this._showChoiceList(evt);
                        } else if (evt.event === "verification" && evt.verification_id) {
                            // Caja B: la IA propuso una escritura -> confirmación inline.
                            this._showVerificationUI(evt);
                        }
                    }
                }
            } catch (e) {
                if (e && (e.name === 'AbortError' || this._streamAbortReason)) {
                    // Abort limpio (cancelación manual o watchdog): aviso sobrio, no
                    // error rojo, conservando lo ya recibido.
                    const reason = this._streamAbortReason || 'user';
                    const icon = reason === 'user' ? '⏹' : '⏱';
                    const msg = reason === 'idle'
                        ? _t('No response from the provider (possible hang). Please try again.')
                        : _t('Generation cancelled.');
                    acc += (acc ? "\n\n" : "") + icon + " " + msg;
                } else {
                    acc += "\n\n🛑 **Error:** " + (e.message || String(e));
                }
            } finally {
                if (idleTimer) { clearTimeout(idleTimer); }
                this._streamAbort = null;
                this.state.canCancel = false;
            }

            this._clearStreamPreviewSchedule();
            this._flushStreamPreview(streamState);

            this.state.streamingPreview = null;
            this.state.streamingHtml = null;
            this.state.statusLabel = "";
            const _tEnd = (typeof performance !== "undefined" ? performance.now() : Date.now());
            if (lastMeta) {
                lastMeta._timing = {
                    ttftMs: _tFirst !== null ? Math.round(_tFirst - _t0) : null,
                    genMs: _tFirst !== null ? Math.round(_tEnd - _tFirst) : null,
                };
                if (!lastMeta.user_prompt && messageText) {
                    lastMeta.user_prompt = String(messageText).trim();
                }
            }
            this.state.messages.push(this._buildAssistantMessage(acc, lastMeta, startTime));
            this._fulfillPendingExports(this.state.messages[this.state.messages.length - 1]);
            if (lastMeta && lastMeta.local_ack) {
                this._markLastUserOfftopic();
            }
            // Parche de adjuntos del turno de usuario: el worker ya persistió las
            // imágenes (URL /web/image) y los ficheros (URL /web/content). Sustituimos
            // el base64 (imágenes) y los chips sin URL (ficheros) de la burbuja recién
            // enviada para que se abran/descarguen en pestaña SIN recargar la sesión.
            if (lastMeta && ((lastMeta.user_images && lastMeta.user_images.length)
                    || (lastMeta.user_files && lastMeta.user_files.length))) {
                for (let i = this.state.messages.length - 1; i >= 0; i--) {
                    const m = this.state.messages[i];
                    if (m.role === "user") {
                        if (lastMeta.user_images && lastMeta.user_images.length) {
                            m.images = lastMeta.user_images;
                        }
                        if (lastMeta.user_files && lastMeta.user_files.length) {
                            m.files = lastMeta.user_files;
                        }
                        break;
                    }
                }
            }
            this._scrollSoon();

            // Este turno se ha visto en vivo en esta pestaña: recordamos su request_id
            // para que el aviso de bus (async_done) NO recargue la sesión por encima y
            // borre lo que acabas de ver.
            this._lastLiveRequestId = this._lastStreamRequestId || null;

            window.dispatchEvent(new CustomEvent("chatboo-auth-cue", {
                detail: { notify: false, fallbackUnread: true },
            }));

            // Auto-promoción: si el worker ya persistió el turno (authored), NO lo
            // volvemos a guardar desde el cliente (evita doble guardado y la carrera
            // con el worker). Recargamos la sesión para recoger adjuntos del worker
            // (imágenes del usuario, descargas API en la burbuja del asistente, etc.).
            const _authored = !!(lastMeta && lastMeta.authored);
            if (_authored) {
                const sid = lastMeta.session_id || this._lastStreamSessionId || this.state.currentSessionId;
                if (sid) {
                    await this._loadSession(sid);
                }
                this._maybeSpeakLastAssistant();
            } else {
                await this._persist();
                this._maybeSpeakLastAssistant();
            }
            await this._refreshSessions();
        } finally {
            this._sseOwnsThinking = false;
            this.state.thinking = false;
            this.state.canCancel = false;
        }
    }

    _buildVerificationResultNote(evt, res, action) {
        // Texto (turno de usuario, no visible) que recibe la IA para que informe del
        // resultado — solo para fetch_url (needs_llm_followup). Escrituras CRUD usan
        // user_ack_message local (sin LLM).
        const guard = " IMPORTANTE: este es solo un aviso de resultado, NO una petición. " +
            "NO llames a ninguna herramienta y NO propongas ni crees ninguna operación nueva " +
            "(ignora cualquier ejemplo del prompt); limítate a redactar el mensaje al usuario.";
        const title = (evt && evt.title) || _t("the operation");
        if (action === "cancel") {
            return "[Resultado del sistema] El usuario ha CANCELADO la operación de escritura «" + title +
                "». No se ha ejecutado ningún cambio. Confírmaselo de forma breve y natural en su idioma." + guard;
        }
        const ok = res && res.success !== false;
        if (ok) {
            let det = "";
            try { det = res && res.results ? JSON.stringify(res.results) : ""; } catch (e) { det = ""; }
            return "[Resultado del sistema] El usuario ha CONFIRMADO la operación «" + title +
                "» y se ha ejecutado CORRECTAMENTE." + (det ? (" Resultado: " + det + ".") : "") +
                " Informa al usuario del éxito de forma breve y natural en su idioma, mencionando lo que se ha creado o modificado." + guard;
        }
        return "[Resultado del sistema] El usuario ha CONFIRMADO la operación «" + title +
            "» but it FAILED to run. Error: " + ((res && res.error) || _t("unknown")) +
            ". Discúlpate brevemente y explica el problema en el idioma del usuario." + guard;
    }

    /**
     * Acuse local (sin LLM) tras Confirm/Cancel de escrituras Safe Plan.
     * fetch_url / mcp no usan esto: el servidor no envía user_ack_message.
     */
    _appendVerificationAck(text, records) {
        if (!text) {
            return;
        }
        const last = [...(this.state.messages || [])].reverse().find((m) => (
            m && m.role === "assistant"
            && (
                (m.backend_history && m.backend_history.length)
                || (m.meta && m.meta.history && m.meta.history.length)
            )
        ));
        const prev = last
            ? [...(last.backend_history || (last.meta && last.meta.history) || [])]
            : [];
        const history = prev.concat([{ role: "assistant", content: text }]);
        this.state.messages.push(this._buildAssistantMessage(text, {
            model: "Safe Plan",
            provider: "local",
            local_ack: true,
            verification_ack: true,
            records: records || [],
            history,
        }));
        this._scrollSoon();
        this._persist().catch(() => { /* noop */ });
    }

    /** Local ack for CRUD; LLM turn only when server asks (fetch_url body). */
    _finishVerificationOutcome(evt, res, action) {
        const ack = res && res.user_ack_message;
        const needsLlm = res && res.needs_llm_followup;
        if (ack) {
            this._appendVerificationAck(ack, (res && res.records) || []);
        }
        if (needsLlm) {
            const note = (res && res.followup_message)
                || this._buildVerificationResultNote(evt, res, action);
            this._runAssistantTurn(note);
        } else if (!ack && action !== "cancel") {
            // Fallback legacy: sin hints del server, pide al LLM (mejor que callarse).
            this._runAssistantTurn(
                (res && res.followup_message)
                || this._buildVerificationResultNote(evt, res || { success: false }, action)
            );
        }
    }

    _formatStreamFooter(text) {
        const trimmed = (text || "").trim();
        if (!trimmed) {
            return "";
        }
        // Misma tubería que owl1 (Showdown + unwrap de fences / dumps).
        return sharedFormatMarkdown(trimmed) || "";
    }

    _callJsonRoute(route, params) {
        // Llama a una ruta Odoo type='json' (envoltorio JSON-RPC). Devuelve result.
        return fetch(route, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            credentials: "same-origin",
            body: JSON.stringify({ jsonrpc: "2.0", method: "call", params: params || {} }),
        }).then(function (r) { return r.json(); }).then(function (d) { return d.result; });
    }

    _restorePendingVerifications() {
        // Same SoT as Security → Authorizations: live pending rows, not SSE memory.
        const self = this;
        return this._callJsonRoute("/pns_ai_mcp/verification/pending", {})
            .then(function (res) {
                const items = (res && res.items) || [];
                for (let i = 0; i < items.length; i++) {
                    const evt = items[i];
                    if (evt && evt.verification_id) {
                        self._showVerificationUI(evt);
                    }
                }
            })
            .catch(function () {
                return undefined;
            });
    }

    _showChoiceList(evt) {
        const self = this;
        const host = typeof globalThis !== "undefined" ? globalThis : window;
        if (!host.ChatbooChoiceList) {
            return;
        }
        host.ChatbooChoiceList.show(evt, {
            t: _t,
            callJson: (route, params) => self._callJsonRoute(route, params),
            onAccepted: (res) => {
                if (res && res.verification_id) {
                    self._showVerificationUI(res);
                }
            },
        });
    }

    _showVerificationUI(evt) {
        // Caja B: panel de confirmación de escritura (DOM puro, sin depender del bus).
        // Seguro: el botón llama al endpoint auth='user'; la IA no tiene la sesión.
        const self = this;
        if (document.getElementById("pns_verif_" + evt.verification_id)) { return; }

        const card = document.createElement("div");
        card.id = "pns_verif_" + evt.verification_id;
        card.style.cssText = "position:fixed;right:24px;bottom:24px;z-index:20000;max-width:380px;background:#fff;border:1px solid #e0a800;border-left:5px solid #e0a800;border-radius:8px;box-shadow:0 6px 24px rgba(0,0,0,.18);padding:14px 16px;font-family:system-ui,Segoe UI,sans-serif;font-size:13px;color:#222;";

        const title = document.createElement("div");
        title.style.cssText = "font-weight:700;margin-bottom:6px;color:#9a6b00;";
        title.textContent = "\u26a0\ufe0f " + _t("Confirm AI write operation") + (evt.title ? (" \u2014 " + evt.title) : "");
        card.appendChild(title);

        if (evt.plan && evt.plan.length) {
            const ul = document.createElement("ul");
            ul.style.cssText = "margin:6px 0 10px 0;padding-left:18px;";
            evt.plan.forEach(function (line) {
                const li = document.createElement("li");
                li.style.marginBottom = "2px";
                li.textContent = line;
                ul.appendChild(li);
            });
            card.appendChild(ul);
        }

        const msg = document.createElement("div");
        msg.style.cssText = "margin-bottom:10px;color:#555;";
        msg.textContent = _t("This operation will not run until you confirm it.");
        card.appendChild(msg);

        const status = document.createElement("div");
        status.style.cssText = "margin-top:8px;font-size:12px;";

        const confirmBtn = document.createElement("button");
        confirmBtn.textContent = _t("Confirm");
        confirmBtn.style.cssText = "background:#2e7d32;color:#fff;border:none;border-radius:5px;padding:6px 14px;cursor:pointer;font-weight:600;";
        const cancelBtn = document.createElement("button");
        cancelBtn.textContent = _t("Cancel");
        cancelBtn.style.cssText = "background:#eee;color:#333;border:none;border-radius:5px;padding:6px 14px;cursor:pointer;";

        const disable = function () {
            confirmBtn.disabled = true; cancelBtn.disabled = true;
            confirmBtn.style.opacity = ".6"; cancelBtn.style.opacity = ".6";
        };

        confirmBtn.addEventListener("click", function () {
            disable();
            status.style.color = "#555";
            status.textContent = _t("Confirming…");
            self._callJsonRoute("/pns_ai_mcp/verification/confirm", { verification_id: evt.verification_id })
                .then(function (res) {
                    const ok = res && res.success !== false;
                    if (!ok) {
                        status.style.color = "#c62828";
                        status.textContent = _t("Error: ") + ((res && res.error) || "");
                        setTimeout(function () { card.remove(); }, 4500);
                        self._finishVerificationOutcome(
                            evt, res || { success: false }, "confirm");
                        return;
                    }
                    if (res && (res.idempotent || res.status === "executed")) {
                        status.style.color = "#2e7d32";
                        status.textContent = _t("Operation executed");
                        setTimeout(function () { card.remove(); }, 2500);
                        self._finishVerificationOutcome(evt, res, "confirm");
                        return;
                    }
                    status.style.color = "#2e7d32";
                    status.textContent = _t("Confirmed — applying…");
                    return self._callJsonRoute(
                        "/pns_ai_mcp/verification/execute",
                        { verification_id: evt.verification_id }
                    ).then(function (ex) {
                        const done = ex && ex.success !== false && ex.status === "executed";
                        status.textContent = done
                            ? _t("Operation executed")
                            : _t("Confirmed — apply pending (Approvals if needed)");
                        setTimeout(function () { card.remove(); }, 2500);
                        self._finishVerificationOutcome(evt, ex || res, "confirm");
                    }).catch(function () {
                        status.textContent = _t("Confirmed — apply pending (Approvals if needed)");
                        setTimeout(function () { card.remove(); }, 2500);
                        self._finishVerificationOutcome(evt, res, "confirm");
                    });
                })
                .catch(function (e) {
                    status.style.color = "#c62828";
                    status.textContent = _t("Error: ") + e;
                    setTimeout(function () { card.remove(); }, 4500);
                    self._finishVerificationOutcome(
                        evt, { success: false, error: String(e) }, "confirm");
                });
        });

        cancelBtn.addEventListener("click", function () {
            disable();
            self._callJsonRoute("/pns_ai_mcp/verification/cancel", { verification_id: evt.verification_id })
                .then(function (res) {
                    status.style.color = "#555";
                    status.textContent = _t("Operation cancelled");
                    setTimeout(function () { card.remove(); }, 2000);
                    self._finishVerificationOutcome(evt, res || {}, "cancel");
                })
                .catch(function () {
                    card.remove();
                    // Cancel sin respuesta server: acuse local genérico de escritura.
                    self._appendVerificationAck(
                        _t("Alright — I cancelled «%s». No changes were applied.")
                            .replace("%s", (evt && evt.title) || _t("the operation"))
                    );
                });
        });

        const btnRow = document.createElement("div");
        btnRow.style.cssText = "display:flex;gap:8px;justify-content:flex-end;";
        btnRow.appendChild(cancelBtn);
        btnRow.appendChild(confirmBtn);
        card.appendChild(btnRow);
        card.appendChild(status);
        document.body.appendChild(card);
        const ov = document.getElementById("o_chatboo_persistent_overlay");
        const hidden = !ov || ov.classList.contains("d-none") || ov.style.display === "none";
        if (hidden) {
            window.dispatchEvent(new CustomEvent("chatboo-auth-cue", {
                detail: { notify: true },
            }));
        }
    }

    // ──────────────────────────── UI helpers ────────────────────────────

    _mapStoredMessage(m) {
        const raw = m.content || "";
        // Asistente: siempre por formatContent compartido → htmlSrc (ChatbooHtmlRenderer
        // hidrata gráficos). Usuario: texto plano en raw (plantilla t-esc).
        const htmlSrc = m.role === "assistant" ? (sharedFormatContent(raw) || "") : null;
        let meta = m.meta ? Object.assign({}, m.meta) : null;
        const localAck = !!(m.local_ack || (meta && meta.local_ack));
        const verifyAck = !!(m.verification_ack || (meta && meta.verification_ack));
        if (verifyAck) {
            meta = Object.assign({}, meta || {}, { verification_ack: true });
        }
        if ((!meta || !meta.records || !meta.records.length) && m.records && m.records.length) {
            meta = Object.assign({}, meta || {}, { records: m.records });
        }
        return {
            role: m.role,
            content: null,
            htmlSrc,
            raw,
            offtopic: !!(m.offtopic || (localAck && !verifyAck)),
            // Imágenes persistidas del turno: URLs de ir.attachment (/web/image
            // con token) que escribió el worker. La BD ya las trae, así que se
            // muestran directamente y sobreviven a recargas y cambios de sesión.
            images: m.images || [],
            // Ficheros adjuntos del turno: chips {name, url} descargables.
            files: m.files || [],
            clip_data: m.clip_data || null,
            ts: m.timestamp || "",
            meta,
            user_prompt: m.user_prompt || (meta && meta.user_prompt) || "",
            local_ack: localAck,
            verification_ack: verifyAck,
            contextInfo: (m.role === "assistant" && !localAck)
                ? this._buildContextInfo(meta)
                : null,
            backend_history: m.backend_history || (meta && meta.history) || null,
        };
    }

    _buildAssistantMessage(raw, meta, startTime = null) {
        const hasClip = !!(meta && (
            meta.clip_data
            || (meta.assistant_files && meta.assistant_files.length)
        ));
        const src = (meta && typeof meta.assistant_content === "string")
            ? meta.assistant_content
            : (raw || (hasClip ? "" : _t("*(no response)*")));
        const htmlSrc = sharedFormatContent(src) || "";
        const localAck = !!(meta && meta.local_ack);
        const verifyAck = !!(meta && meta.verification_ack);
        return {
            role: "assistant",
            content: null,
            htmlSrc,
            raw: src,
            ts: startTime ? this._formatTimestamp(startTime, new Date()) : this._now(),
            meta: meta || null,
            user_prompt: (meta && meta.user_prompt) || "",
            local_ack: localAck,
            verification_ack: verifyAck,
            contextInfo: localAck && !verifyAck ? null : this._buildContextInfo(meta),
            files: (meta && meta.assistant_files) || [],
            clip_data: (meta && meta.clip_data) || null,
            offtopic: localAck && !verifyAck,
            backend_history: verifyAck
                ? ((meta && meta.history) || null)
                : (localAck ? null : ((meta && meta.history) || null)),
        };
    }

    _isOfftopicMessage(m) {
        if (m && (m.verification_ack || (m.meta && m.meta.verification_ack))) {
            return false;
        }
        return !!(m && (m.offtopic || m.local_ack || (m.meta && m.meta.local_ack)));
    }

    _messagesForModel(messages, excludeTail) {
        const list = messages || [];
        const base = excludeTail ? list.slice(0, -excludeTail) : list.slice();
        return base.filter((m) => m && m.role !== "system" && !this._isOfftopicMessage(m));
    }

    _clipForLlm(text, limit) {
        const s = (text == null) ? "" : String(text);
        if (!limit || s.length <= limit) {
            return s;
        }
        return s.slice(0, Math.max(0, limit - 1)).replace(/\s+$/, "") + "…";
    }

    _contentForLlm(text) {
        const s = (text == null) ? "" : String(text);
        if (s.indexOf("[On-screen artifact") === 0) {
            return s;
        }
        const fat = s.length > 2500
            || /<table\b/i.test(s)
            || s.indexOf("o_chatboo_table_block") >= 0
            || s.indexOf("data-chatboo-dataset") >= 0;
        if (!fat) {
            return s;
        }
        return "[On-screen artifact | kind=table | ~" + s.length + " characters]\n"
            + "The full document is already visible to the user. Do not reprint the rows. "
            + "Cached dataset is previous_result if you need to reformat or recompute. "
            + "Use tools for a new query.";
    }

    _historyForApi(excludeTail) {
        const msgs = this.state.messages || [];
        const last = [...msgs].reverse().find((m) => (
            m && m.role === "assistant"
            && !this._isOfftopicMessage(m)
            && (
                (m.backend_history && m.backend_history.length)
                || (m.meta && m.meta.history && m.meta.history.length)
            )
        ));
        if (last) {
            return [...(last.backend_history || last.meta.history)];
        }
        return this._messagesForModel(msgs, excludeTail).map((m) => ({
            role: m.role,
            content: m.role === "user"
                ? this._clipForLlm(m.raw, 4000)
                : this._contentForLlm(m.raw),
        }));
    }

    _markLastUserOfftopic() {
        const msgs = this.state.messages || [];
        for (let i = msgs.length - 1; i >= 0; i--) {
            if (msgs[i].role === "user") {
                msgs[i].offtopic = true;
                break;
            }
        }
    }

    _formatTimestamp(startTime, endTime = null) {
        if (!startTime) {
            return this._now();
        }
        if (!endTime) {
            endTime = new Date();
        }
        const duration = Math.round((endTime - startTime) / 1000);
        return `${formatWallclock(startTime)} (${duration} segundos)`;
    }

    /** @see chatboo_formatters.isLikelyHtml */
    _isLikelyHtml(text) {
        return sharedIsLikelyHtml(text);
    }

    /**
     * Misma tubería que owl1 (`formatters.formatContent`), envuelta en markup
     * para t-out cuando haga falta. Preferir htmlSrc + ChatbooHtmlRenderer.
     */
    _formatContent(text) {
        return markup(sharedFormatContent(text || "") || "");
    }

    /** @see chatboo_formatters.formatMarkdown */
    _formatMarkdown(src) {
        return markup(sharedFormatMarkdown(src || "") || "");
    }

    _now() {
        return formatWallclock(new Date());
    }

    _showContextStats() {
        // Mismo análisis que owl1: cabecera modelo·proveedor, estado de sesión
        // (lo vivo) y detalle por interacción (lo histórico). Cada turno usa
        // el prompt guardado en el asistente, no el último user del array.
        const all = this.state.messages || [];
        let rows = [];
        const statsPre = window.ChatbooContextStats;
        all.forEach((m, idx) => {
            if (m.role === "assistant" && m.contextInfo) {
                const ci = m.contextInfo;
                const usage = (m.meta && m.meta.usage) || {};
                const q = (statsPre && statsPre.questionForAssistant)
                    ? statsPre.questionForAssistant(all, idx)
                    : String(m.user_prompt || (m.meta && m.meta.user_prompt) || "").trim();
                rows.push({
                    n: rows.length + 1,
                    q: q,
                    used: ci.usedTokens || 0,
                    usedK: ci.usedK,
                    limitK: ci.limitK,
                    percent: parseFloat(ci.usagePercent) || 0,
                    model: ci.model,
                    provider: ci.provider,
                    cached: ci.cachedTokens || 0,
                    cachedPct: ci.cachedPct || 0,
                    turnTokens: ci.turnTokens || usage.total_tokens || 0,
                    turnK: ci.turnTokensK || null,
                    turnLabel: ci.turnLabel || "-",
                    turnCode: ci.turnCode || "",
                    messageIndex: idx,
                    costUsd: Number(usage.cost) || 0,
                    costLabel: ci.costLabel || null,
                    displayCurrency: (m.meta && m.meta.display_currency) || "",
                });
            }
        });
        const stats = window.ChatbooContextStats;
        rows = stats ? stats.occupyingRows(rows) : rows.filter((r) => (r.used || 0) > 0);
        if (!rows.length) {
            return;
        }
        const esc = (s) => (stats && stats.esc)
            ? stats.esc(s)
            : String(s == null ? "" : s)
                .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
        const colorOf = (p) => (stats && stats.colorOf)
            ? stats.colorOf(p)
            : (p > 80 ? "#dc3545" : p > 60 ? "#ffc107" : "#28a745");
        const latest = rows[rows.length - 1];
        const modelLabel = (latest.model || latest.provider)
            ? [latest.model, latest.provider].filter(Boolean).join(" · ")
            : "Unknown model";
        const barColor = colorOf(latest.percent);

        let trend = "";
        if (rows.length >= 2) {
            const diffK = (latest.used - rows[rows.length - 2].used) / 1024;
            trend = diffK > 0 ? "↑ +" + diffK.toFixed(2) + "k tokens vs previous" : "→ Stable";
        }

        let html = "";
        // Estado de sesión (lo vivo): tarjetas + barra.
        html += '<div style="display:flex;gap:12px;margin-bottom:10px;">';
        html += '<div style="flex:1;text-align:center;background:#f6f7f9;border-radius:8px;padding:12px;">'
            + '<div style="font-size:11px;color:#888;">INTERACTIONS</div>'
            + '<div style="font-size:22px;font-weight:700;color:#0d6efd;">' + rows.length + "</div>"
            + '<div style="font-size:11px;color:#666;">Performed</div></div>';
        html += '<div style="flex:1;text-align:center;background:#f6f7f9;border-radius:8px;padding:12px;">'
            + '<div style="font-size:11px;color:#888;">SENT / PROVIDER CAP</div>'
            + '<div style="font-size:22px;font-weight:700;color:' + barColor + ';">' + esc(latest.percent.toFixed(1)) + "%</div>"
            + '<div style="font-size:11px;color:#666;">' + esc(latest.usedK) + "k / " + esc(latest.limitK) + "k</div></div>";
        const sessionTurnTokens = rows.reduce((sum, r) => sum + (r.turnTokens || 0), 0);
        const sessionCostUsd = rows.reduce((sum, r) => sum + (r.costUsd || 0), 0);
        const sessionTurnK = sessionTurnTokens > 0 ? (sessionTurnTokens / 1024).toFixed(2) : null;
        const sessionCost = this._formatCostLabel(
            sessionCostUsd,
            this._currencyForProvider(latest.provider, latest.displayCurrency),
        );
        const sessionCostLabel = sessionCost.label;
        if (sessionTurnK) {
            html += '<div style="flex:1;text-align:center;background:#f6f7f9;border-radius:8px;padding:12px;">'
                + '<div style="font-size:11px;color:#888;">' + esc(_t("SESSION")) + "</div>"
                + '<div style="font-size:22px;font-weight:700;color:#334155;">' + esc(sessionTurnK) + "k</div>"
                + '<div style="font-size:11px;color:#666;">' + esc(_t("tokens billed")) + "</div>"
                + (latest.turnK
                    ? '<div style="font-size:11px;color:#888;">' + esc(_t("last turn")) + " " + esc(latest.turnK) + "k</div>"
                    : "")
                + "</div>";
        }
        if (sessionCostLabel) {
            html += '<div style="flex:1;text-align:center;background:#f6f7f9;border-radius:8px;padding:12px;">'
                + '<div style="font-size:11px;color:#888;">' + esc(_t("COST")) + "</div>"
                + '<div style="font-size:22px;font-weight:700;color:#334155;">' + esc(sessionCostLabel) + "</div>"
                + '<div style="font-size:11px;color:#666;">' + esc(_t("this session")) + "</div>"
                + (latest.costLabel
                    ? '<div style="font-size:11px;color:#888;">' + esc(_t("last turn")) + " " + esc(latest.costLabel) + "</div>"
                    : "")
                + "</div>";
        }
        // Caché de prompt del proveedor: tokens del prompt servidos desde caché
        // (prefix/prompt caching). Solo se pinta si el proveedor lo reporta.
        const cachedNow = latest.cached || 0;
        if (cachedNow > 0) {
            html += '<div style="flex:1;text-align:center;background:#f6f7f9;border-radius:8px;padding:12px;">'
                + '<div style="font-size:11px;color:#888;">PROMPT CACHE</div>'
                + '<div style="font-size:22px;font-weight:700;color:#0ea5e9;">' + esc(latest.cachedPct.toFixed(0)) + "%</div>"
                + '<div style="font-size:11px;color:#666;">' + esc((cachedNow / 1024).toFixed(2)) + "k tokens cached</div></div>";
        }
        html += "</div>";
        html += '<div style="display:flex;justify-content:space-between;font-size:11px;margin-bottom:4px;">'
            + "<span>" + esc(_t("Last turn · sent vs provider cap")) + "</span>"
            + '<span style="font-weight:700;">' + esc(latest.percent.toFixed(1)) + "% "
            + esc(_t("of the %s k cap")).replace("%s", latest.limitK) + "</span></div>";
        html += (stats ? stats.occupancyBarHtml(latest.percent, 14) : "")
            + '<div style="height:6px;"></div>';
        html += '<div style="font-size:11px;color:#888;margin-bottom:2px;">'
            + esc(_t("Occupancy this session")) + "</div>";
        html += stats ? stats.sparklineSvg(rows) : "";
        html += '<div style="display:flex;justify-content:space-between;font-size:11px;color:#888;margin:6px 0 14px;">'
            + "<span>" + esc(_t("Context status")) + "</span><span>" + esc(trend) + "</span></div>";

        // Detalle por interacción (lo histórico).
        const anyCached = rows.some((r) => (r.cached || 0) > 0);
        const anyTurn = rows.some((r) => r.turnLabel && r.turnLabel !== "-");
        const anyCost = rows.some((r) => r.costLabel && r.costLabel !== "-");
        const anyTurnCode = rows.some((r) => r.turnCode);
        html += '<table style="width:100%;border-collapse:collapse;font-size:12px;">';
        html += '<thead><tr style="text-align:left;color:#666;border-bottom:1px solid #ddd;">'
            + '<th style="padding:5px;">#</th>'
            + (anyTurnCode ? '<th style="padding:5px;">Id</th>' : "")
            + '<th style="padding:5px;">Question</th>'
            + '<th style="padding:5px;text-align:right;">Sent</th>'
            + '<th style="padding:5px;text-align:right;">%</th>'
            + (anyTurn ? '<th style="padding:5px;text-align:right;">Turn</th>' : "")
            + (anyCost ? '<th style="padding:5px;text-align:right;">Cost</th>' : "")
            + (anyCached ? '<th style="padding:5px;text-align:right;">Cache</th>' : "")
            + '<th style="padding:5px;width:130px;">Total Visual Impact</th></tr></thead><tbody>';
        rows.forEach((r) => {
            const cacheCell = anyCached
                ? '<td style="padding:5px;text-align:right;color:#0ea5e9;">'
                    + ((r.cached || 0) > 0 ? (r.cachedPct.toFixed(0) + "%") : "—") + "</td>"
                : "";
            const turnCell = anyTurn
                ? '<td style="padding:5px;text-align:right;">' + esc(r.turnLabel || "0") + "</td>"
                : "";
            const costCell = anyCost
                ? '<td style="padding:5px;text-align:right;">' + esc(r.costLabel && r.costLabel !== "-" ? r.costLabel : "—") + "</td>"
                : "";
            const turnTok = stats && stats.safeTurnToken
                ? stats.safeTurnToken(r.turnCode)
                : String(r.turnCode || "").replace(/[^A-Za-z0-9_-]/g, "");
            html += '<tr class="o_ctx_turn_row" data-turn-code="' + esc(turnTok) + '" data-msg-index="' + r.messageIndex + '" style="border-bottom:1px solid #f1f1f1;cursor:pointer;">'
                + '<td style="padding:5px;font-weight:600;">#' + r.n + "</td>"
                + (anyTurnCode ? '<td style="padding:5px;font-family:monospace;">' + esc(r.turnCode || "—") + "</td>" : "")
                + '<td class="o_ctx_turn_q" style="padding:5px;max-width:300px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;color:#007cba;" title="' + esc(r.q) + '">' + esc(r.q) + "</td>"
                + '<td style="padding:5px;text-align:right;">' + esc(r.usedK) + "k</td>"
                + '<td style="padding:5px;text-align:right;">' + r.percent.toFixed(1) + "%</td>"
                + turnCell
                + costCell
                + cacheCell
                + '<td style="padding:5px;">'
                + (stats ? stats.rowBarHtml(r.percent) : "")
                + "</td></tr>";
        });
        html += "</tbody>";
        if (sessionTurnK || sessionCostLabel) {
            html += '<tfoot><tr style="border-top:1px solid #ddd;font-weight:700;">'
                + '<td style="padding:5px;" colspan="' + (anyTurnCode ? 3 : 2) + '">' + esc(_t("Session")) + "</td>"
                + '<td style="padding:5px;"></td><td style="padding:5px;"></td>'
                + (anyTurn ? '<td style="padding:5px;text-align:right;">' + (sessionTurnK ? esc(sessionTurnK) + "k" : "0") + "</td>" : "")
                + (anyCost ? '<td style="padding:5px;text-align:right;">' + (sessionCostLabel ? esc(sessionCostLabel) : "—") + "</td>" : "")
                + (anyCached ? '<td style="padding:5px;"></td>' : "")
                + '<td style="padding:5px;"></td></tr></tfoot>';
        }
        html += "</table>";

        this._openStatsModal("Context analysis: " + modelLabel, html);
    }

    _openStatsModal(title, innerHtml) {
        const old = document.getElementById("pns_ctx_stats");
        if (old) {
            old.remove();
        }
        const esc = (s) => String(s == null ? "" : s)
            .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
        const overlay = document.createElement("div");
        overlay.id = "pns_ctx_stats";
        overlay.style.cssText = "position:fixed;inset:0;z-index:20000;background:rgba(0,0,0,.35);display:flex;align-items:center;justify-content:center;";
        const card = document.createElement("div");
        card.style.cssText = "background:#fff;border-radius:10px;max-width:860px;width:94%;max-height:82vh;overflow:auto;padding:18px 20px;box-shadow:0 8px 30px rgba(0,0,0,.25);font-family:system-ui,Segoe UI,sans-serif;color:#222;";
        card.innerHTML =
            '<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:14px;">'
            + '<h5 style="margin:0;font-size:15px;"><i class="fa fa-microchip" style="margin-right:6px;opacity:.7;"></i>' + esc(title) + "</h5>"
            + '<button type="button" class="o_ctx_close" style="border:0;background:none;font-size:22px;line-height:1;cursor:pointer;color:#888;">&#215;</button>'
            + "</div>"
            + innerHtml;
        overlay.appendChild(card);
        const close = () => overlay.remove();
        overlay.addEventListener("click", (e) => {
            if (e.target === overlay) {
                close();
            }
        });
        const btn = card.querySelector(".o_ctx_close");
        if (btn) {
            btn.addEventListener("click", close);
        }
        card.querySelectorAll("tr.o_ctx_turn_row").forEach((row) => {
            const q = row.querySelector(".o_ctx_turn_q");
            if (q) {
                q.addEventListener("mouseenter", () => {
                    q.style.textDecoration = "underline";
                });
                q.addEventListener("mouseleave", () => {
                    q.style.textDecoration = "none";
                });
            }
            row.addEventListener("click", (e) => {
                e.preventDefault();
                e.stopPropagation();
                const code = row.getAttribute("data-turn-code") || "";
                const idx = parseInt(row.getAttribute("data-msg-index"), 10);
                close();
                this._scrollToContextTurn(code, idx);
            });
        });
        document.body.appendChild(overlay);
    }

    _scrollToContextTurn(turnCode, messageIndex) {
        const root = this.messagesRef && this.messagesRef.el;
        const stats = window.ChatbooContextStats;
        const bubble = stats && stats.findTurnBubble
            ? stats.findTurnBubble(root, turnCode, messageIndex)
            : null;
        if (stats && stats.flashTurnBubble) {
            stats.flashTurnBubble(bubble);
        }
    }

    _currencyForProvider(name, explicit) {
        const want = String(explicit || "").trim().toUpperCase();
        if (want && want.length === 3) {
            return want;
        }
        return this._defaultDisplayCurrency || "USD";
    }

    _resetSessionOccupancy() {
        this._sessionOccupancy = { used: 0, limit: 0 };
    }

    _occupyFromUsage(used, limit) {
        const prev = this._sessionOccupancy || { used: 0, limit: 0 };
        const nextUsed = used || prev.used || 0;
        const nextLimit = limit || prev.limit || 0;
        if (nextUsed && nextLimit) {
            this._sessionOccupancy = { used: nextUsed, limit: nextLimit };
        }
        return { used: nextUsed, limit: nextLimit };
    }

    _spendCost(usage) {
        const extracted = this._extractUsageCost(usage);
        if (extracted !== undefined) {
            return extracted;
        }
        // 0 tokens billed this turn → 0 in the display currency, not "unknown".
        if (this._turnTokensValue(usage) === 0) {
            return 0;
        }
        return undefined;
    }

    _refreshUsageChips() {
        const msgs = this.state.messages || [];
        if (!msgs.length) {
            return;
        }
        this._resetSessionOccupancy();
        this.state.messages = msgs.map((msg) => {
            if (msg.role !== "assistant") {
                return msg;
            }
            return Object.assign({}, msg, {
                contextInfo: this._buildContextInfo(msg.meta),
            });
        });
    }

    _extractUsageCost(usage) {
        if (!usage || typeof usage !== "object") {
            return undefined;
        }
        if (usage.cost != null) {
            return usage.cost;
        }
        if (usage.total_cost != null) {
            return usage.total_cost;
        }
        if (usage.cost_usd != null) {
            return usage.cost_usd;
        }
        if (usage.cost_in_usd_ticks != null) {
            const ticks = Number(usage.cost_in_usd_ticks);
            return Number.isFinite(ticks) ? ticks / 1e10 : undefined;
        }
        return undefined;
    }

    _usageHasTokenKey(usage) {
        if (!usage || typeof usage !== "object") {
            return false;
        }
        return ["total_tokens", "prompt_tokens", "completion_tokens", "input_tokens", "output_tokens"]
            .some((k) => usage[k] != null);
    }

    _turnTokensValue(usage) {
        if (!this._usageHasTokenKey(usage)) {
            return null;
        }
        const total = Number(usage.total_tokens);
        if (Number.isFinite(total)) {
            return total;
        }
        return (Number(usage.prompt_tokens) || 0) + (Number(usage.completion_tokens) || 0);
    }

    _formatTurnTokensLabel(usage) {
        const n = this._turnTokensValue(usage);
        if (n == null) {
            return "-";
        }
        if (n > 0) {
            return (n / 1024).toFixed(2) + "k";
        }
        return "0";
    }

    _formatCostLabel(usd, currency) {
        if (usd === undefined || usd === null || usd === "") {
            return { label: "-", title: _t("Cost unknown") };
        }
        const n = Number(usd);
        if (!Number.isFinite(n) || n < 0) {
            return { label: "-", title: _t("Cost unknown") };
        }
        const fx = this._fx;
        let amount = n;
        let code = "USD";
        let rate = 1;
        let failed = false;
        const want = (currency || "USD").toUpperCase();
        if (want !== "USD") {
            const r = Number(fx && fx.rates ? fx.rates[want] : NaN);
            if (Number.isFinite(r) && r > 0) {
                rate = r;
                amount = n * r;
                code = want;
            } else {
                // Sin tasa no se inventa la conversión: se paga en USD y se avisa.
                failed = true;
            }
        }
        let label;
        const zero = amount === 0;
        try {
            label = new Intl.NumberFormat(undefined, {
                style: "currency",
                currency: code,
                minimumFractionDigits: zero || amount >= 0.01 ? 2 : 4,
                maximumFractionDigits: zero ? 2 : (amount >= 0.01 ? 4 : 6),
            }).format(amount);
        } catch (e) {
            label = code + " " + (zero ? amount.toFixed(2) : amount.toFixed(4));
        }
        const asOf = fx && fx.as_of ? fx.as_of : "";
        let title;
        if (failed) {
            label += " ⚠";
            const why = (fx && fx.error) || _t("no exchange rate available");
            title = _t("Could not convert to %s: shown in USD").replace("%s", want)
                + " · " + why;
        } else if (code === "USD") {
            title = "USD" + (asOf ? " · " + asOf : "");
        } else {
            title = code + " · 1 USD = " + rate + (asOf ? " · " + asOf : "");
        }
        return { label, title };
    }

    _buildContextInfo(meta) {
        // Chip de gasto siempre: - (desconocido), 0,00 € o el valor reportado.
        // El chip verde es ocupación de la SESIÓN: un skill sin LLM hereda
        // used/limit del último turno que sí ocupó el buffer.
        const usage = (meta && meta.usage) || null;
        const rawUsed = usage
            ? (usage.context_tokens || usage.total_tokens || usage.prompt_tokens || 0)
            : 0;
        const rawLimit = (meta && meta.context_limit) || 0;
        const turnTokens = this._turnTokensValue(usage);
        const occupied = (usage || rawLimit)
            ? this._occupyFromUsage(rawUsed, rawLimit)
            : { used: 0, limit: 0 };
        const used = occupied.used;
        const limit = occupied.limit;
        const showBuffer = Boolean(used && limit);
        const pct = showBuffer ? (used / limit) * 100 : 0;
        let colorHex = "#28a745";
        let icon = "fa-bell-o";
        if (showBuffer && pct > 80) {
            colorHex = "#dc3545";
            icon = "fa-exclamation-triangle";
        } else if (showBuffer && pct > 60) {
            colorHex = "#ffc107";
            icon = "fa-exclamation-circle";
        }
        // Velocidad real medida en cliente: decode = completion_tokens / (fin − 1er token).
        // Si no hay timing o usage, queda null (no se pinta).
        let speedTps = null;
        let ttftMs = null;
        const ct = (usage && usage.completion_tokens) || 0;
        const timing = (meta && meta._timing) || null;
        if (timing) {
            ttftMs = timing.ttftMs;
            if (ct && timing.genMs > 0) {
                speedTps = (ct / (timing.genMs / 1000)).toFixed(1);
            }
        }
        // Sin timing de cliente (mensaje autorado por el worker y recargado):
        // usamos la velocidad medida en servidor (speed_tps) para no perder el pie.
        if (speedTps === null && meta && meta.speed_tps) {
            speedTps = Number(meta.speed_tps).toFixed(1);
        }
        // Tokens de prompt servidos desde la caché del proveedor (prefix/prompt cache).
        // El motor normaliza a meta.usage.cached_tokens; toleramos también el
        // formato crudo de OpenAI (prompt_tokens_details.cached_tokens) por si acaso.
        let cachedTokens = usage && usage.cached_tokens;
        if (cachedTokens == null && usage && usage.prompt_tokens_details) {
            cachedTokens = usage.prompt_tokens_details.cached_tokens;
        }
        cachedTokens = cachedTokens || 0;
        const promptTokens = (usage && usage.prompt_tokens) || 0;
        const cachedPct = promptTokens > 0 ? (cachedTokens / promptTokens) * 100 : 0;
        const turnLabel = this._formatTurnTokensLabel(usage);
        const cost = this._formatCostLabel(
            this._spendCost(usage),
            this._currencyForProvider(meta && meta.provider, meta && meta.display_currency),
        );
        const turnTitle = _t("Tokens billed this turn (all LLM rounds)");
        const spendLabel = turnLabel + " · " + cost.label;
        const spendTitle = [turnLabel !== "-" ? turnTitle : "", cost.title].filter(Boolean).join(" · ");
        const turnCode = ((meta && meta.correlation_id) || "").trim();
        return {
            turnCode,
            turnCodeTitle: _t(
                "Turn id (MCP log). Click to copy. Use with /create-skill.",
            ),
            showBuffer,
            usedK: showBuffer ? (used / 1024).toFixed(2) : null,
            limitK: showBuffer ? (limit / 1024).toFixed(2) : null,
            usedTokens: used,
            limitTokens: limit,
            usagePercent: showBuffer ? pct.toFixed(1) : "0",
            colorHex,
            icon,
            model: (meta && meta.model) || "",
            provider: (meta && meta.provider) || "",
            speedTps,
            ttftMs,
            cachedTokens,
            promptTokens,
            cachedPct,
            bufferTitle: _t("Session context occupancy · provider cap"),
            turnTokensK: turnTokens > 0 ? (turnTokens / 1024).toFixed(2) : null,
            turnTokens: turnTokens || 0,
            turnLabel,
            turnTitle,
            costLabel: cost.label,
            costTitle: cost.title,
            spendLabel,
            spendTitle,
            speedTitle: _t("Generation speed (tokens/s)"),
        };
    }

    _scrollSoon() {
        if (this._scrollRaf) {
            return;
        }
        this._scrollRaf = requestAnimationFrame(() => {
            this._scrollRaf = null;
            const el = this.messagesRef.el;
            if (el) {
                el.scrollTop = el.scrollHeight;
            }
        });
    }

    // Abre en pestaña nueva CUALQUIER enlace de contenido del chat (imágenes y
    // ficheros adjuntos /web/image//web/content, chips de registro /web#id=...,
    // enlaces de registro en línea del markdown y fuentes http/https). Handler
    // ÚNICO delegado en fase de captura: se ejecuta ANTES que el enrutado SPA del
    // web client o el cierre del popover del systray, que si no "se comían" el
    // clic y por eso los adjuntos del histórico "no abrían nada". Robusto en
    // O14–O19 y para contenido inyectado (markup/t-out) o del histórico.
    _setupRefLinkHandler() {
        const el = this.messagesRef.el;
        if (!el || this._refLinkHandler) {
            return;
        }
        this._refLinkHandler = (ev) => {
            const a = ev.target && ev.target.closest ? ev.target.closest("a[href]") : null;
            if (!a || !el.contains(a)) {
                return;
            }
            const href = a.getAttribute("href") || "";
            if (!/^(https?:|\/web|\/odoo)/.test(href)) {
                return; // enlaces internos de UI (#, javascript:) → no tocar
            }
            ev.preventDefault();
            ev.stopPropagation();
            window.open(href, "_blank", "noopener");
        };
        el.addEventListener("click", this._refLinkHandler, true);
    }

    _flushStreamPreview(streamState) {
        const acc = streamState.acc;
        // Unificado con owl1: siempre formatContent → htmlSrc (hidrata charts).
        const htmlSrc = sharedFormatContent(acc || "") || "";
        if (ChatbooSse.hasVisibleContent(acc)) {
            this.state.streamingHtml = htmlSrc;
            this.state.streamingPreview = null;
        }
        this._scrollSoon();
    }

    _scheduleStreamPreview(streamState) {
        if (this._streamFlushTimer) {
            return;
        }
        this._streamFlushTimer = setTimeout(() => {
            this._streamFlushTimer = null;
            this._flushStreamPreview(streamState);
        }, 60);
    }

    _clearStreamPreviewSchedule() {
        if (this._streamFlushTimer) {
            clearTimeout(this._streamFlushTimer);
            this._streamFlushTimer = null;
        }
    }

    async _onChatbooSyncPayload(raw) {
        let payload = raw;
        if (raw && raw.payload !== undefined && raw.action === undefined) {
            payload = raw.payload;
        }
        payload = _busNotificationPayload(payload) || payload;
        if (!payload || typeof payload !== "object") {
            return;
        }
        if (payload.type && payload.type !== "pns_chatboo_sync") {
            return;
        }
        await this._handleChatbooSync(payload);
    }

    async _processBusNotifications(notifications) {
        const items = _busNotificationList(notifications);
        if (!items.length) {
            return;
        }
        for (const notif of items) {
            const payload = _busNotificationPayload(notif);
            if (!payload || payload.type !== "pns_chatboo_sync") {
                continue;
            }
            await this._handleChatbooSync(payload);
        }
    }

    async _handleChatbooSync(payload) {
            const action = payload.action;
            const sessionId = payload.session_id;
            if (
                action !== "async_done" && action !== "new_chat"
                && action !== "skills_changed"
                && this.state.currentSessionId && sessionId
                && this.state.currentSessionId !== sessionId
            ) {
                return;
            }
            if (action === "thinking") {
                // El turno que esta pestaña ve en vivo ya controla el indicador vía
                // SSE. El aviso de bus 'thinking' puede llegar tarde (canal aparte) y
                // reactivar un "Thinking…" que ya nadie limpia. Lo ignoramos si es de
                // nuestro propio turno — o si ya hay un SSE local dueño del spinner.
                const _rid = payload.request_id || null;
                if (this._sseOwnsThinking) {
                    return;
                }
                if (_rid && (_rid === this._lastStreamRequestId || _rid === this._lastLiveRequestId)) {
                    return;
                }
                this.state.thinking = true;
                // Bus-only thinking (otra pestaña / reenganche): permitir Cancelar
                // contra el job del servidor.
                if (_rid) {
                    this._resumeReqId = _rid;
                    this._lastStreamRequestId = _rid;
                    this.state.canCancel = true;
                }
            } else if (action === "message_received") {
                // Nunca apagar el spinner de un turno SSE en curso (p. ej. al
                // continuar la conversación llega un sync del turno anterior).
                if (!this._sseOwnsThinking) {
                    this.state.thinking = false;
                }
                if (sessionId) {
                    await this._loadSession(sessionId);
                } else if (this.state.currentSessionId) {
                    await this._loadSession(this.state.currentSessionId);
                }
            } else if (action === "new_chat") {
                await this._refreshSessions();
                if (!this.state.currentSessionId && sessionId) {
                    this.state.currentSessionId = sessionId;
                    this.state.messages.splice(0, this.state.messages.length);
                }
            } else if (action === "skills_changed") {
                this._invalidateSkillsCache();
                if (this.state.slashOpen) {
                    await this._updateSlashSuggestions(this.state.currentInput);
                }
                if (
                    payload.confirm
                    && sessionId
                    && String(this.state.currentSessionId) === String(sessionId)
                ) {
                    await this._loadSession(this.state.currentSessionId);
                }
            } else if (action === "async_done") {
                const reqId = payload.request_id || null;
                const renderedLive = reqId && reqId === this._lastLiveRequestId;
                const ownInFlight = reqId && reqId === this._lastStreamRequestId;
                // SSE local en curso: el spinner lo apaga solo _runAssistantTurn.
                // Un async_done del turno ANTERIOR (renderedLive) no debe tumbar
                // el "Thinking…" del turno nuevo al continuar la conversación.
                if (this._sseOwnsThinking) {
                    if (ownInFlight || renderedLive) {
                        return;
                    }
                    // Otro job en otra sesión: no recargar encima del stream actual.
                    return;
                }
                // Recargar de BD SOLO si este turno no se acaba de ver en vivo en
                // esta pestaña. Si ya lo viste, no lo pisamos (evita el "se borra
                // el contenido" al cambiar de ventana).
                if (!renderedLive) {
                    // Fin de un turno que no vimos en vivo (p. ej. reanudado tras
                    // F5): refrescar y quitar el "pensando…".
                    if (reqId && reqId === this._resumeReqId) {
                        this._resumeReqId = null;
                    }
                    if (sessionId) {
                        this.state.currentSessionId = sessionId;
                        await this._loadSession(sessionId);
                    } else if (this.state.currentSessionId) {
                        await this._loadSession(this.state.currentSessionId);
                    }
                    this.state.thinking = false;
                } else {
                    // Ya visto en vivo: no recargar, pero limpiar por si un 'thinking'
                    // tardío de este mismo turno dejó la burbuja colgada.
                    this.state.thinking = false;
                }
                if (!renderedLive) {
                    this._maybeSpeakLastAssistant();
                }
            }
    }

    _exportCtx() {
        return {
            messages: this.state.messages.map((m) => ({
                role: m.role,
                content: m.htmlSrc || m.raw || "",
                original_content: m.raw || "",
                formatted_html: m.htmlSrc || null,
                clip_data: m.clip_data || null,
                files: m.files || [],
            })),
            messagesEl: this.messagesRef.el,
            notification: (opts) => {
                if (opts && opts.message) {
                    this.notification.add(opts.message, {
                        type: opts.type || "info",
                        sticky: !!opts.sticky,
                    });
                }
            },
            sessionId: this.state.currentSessionId,
            rpc: (spec) => rpc(spec.route, spec.params),
            onChipFulfilled: (msg) => {
                if (msg && msg.files) {
                    msg.files = msg.files.slice();
                }
                this._persist().catch(() => {});
            },
        };
    }

    _fulfillPendingExports(msg) {
        if (!msg || typeof exportUtils.fulfillPendingSessionDocuments !== "function") {
            return;
        }
        const pending = (msg.files || []).some((f) => f && f.pending);
        if (!pending) {
            return;
        }
        const run = () => {
            const idx = this.state.messages.indexOf(msg);
            let sourceEl = null;
            const root = this.messagesRef && this.messagesRef.el;
            if (root && idx >= 0) {
                const node = root.querySelector('[data-msg-index="' + idx + '"]');
                sourceEl = node && (node.querySelector(".o_chatboo_content") || node);
            }
            exportUtils.fulfillPendingSessionDocuments(msg, sourceEl, this._exportCtx())
                .catch(() => {});
        };
        setTimeout(run, 120);
    }

    _fulfillPendingExportsInView() {
        (this.state.messages || []).forEach((msg) => this._fulfillPendingExports(msg));
    }

    _copyToClipboard(ev) {
        exportUtils.copyToClipboard(ev, this._exportCtx());
    }

    _downloadAsPDF(ev) {
        exportUtils.downloadAsPDF(ev, this._exportCtx());
    }

    _downloadAsExcel(ev) {
        exportUtils.downloadAsExcel(ev, this._exportCtx());
    }

    _downloadAsWord(ev) {
        exportUtils.downloadAsWord(ev, this._exportCtx());
    }

    async copyMessage(raw) {
        try {
            await navigator.clipboard.writeText(raw || "");
            this.notification.add(_t("Copied to clipboard."), { type: "success" });
        } catch (e) {
            this.notification.add(_t("Could not copy."), { type: "warning" });
        }
    }

    async _copyTurnCode(ev, code) {
        if (ev) {
            ev.stopPropagation();
            if (typeof ev.preventDefault === "function") {
                ev.preventDefault();
            }
        }
        const text = (code || "").trim();
        if (!text) {
            return;
        }
        try {
            await navigator.clipboard.writeText(text);
            this.notification.add(_t("Turn id copied."), { type: "success" });
        } catch (e) {
            this.notification.add(_t("Could not copy."), { type: "warning" });
        }
    }

    // ──────────────────────────── Slash commands (skills) ────────────────────────────

    async _ensureSkills(force) {
        if (this._skillsListInflight) {
            return this._skillsListInflight;
        }
        if (!force && this._skillsLoaded && this.skillsCache) {
            return this.skillsCache;
        }
        const gen = this._skillsListGen;
        this._skillsListInflight = (async () => {
            try {
                const res = await rpc("/chatboo/skills/list", {});
                if (gen !== this._skillsListGen) {
                    return this.skillsCache || [];
                }
                this.skillsCache = (res && res.skills) || [];
                this.canWriteSkills = !!(res && res.can_write_skills);
                this.skillCodePrefix = (res && res.skill_code_prefix) || "";
                this.skillCommandPrefix = (res && res.skill_command_prefix) || "";
                this._skillsLoaded = true;
            } catch (e) {
                if (gen === this._skillsListGen) {
                    this.skillsCache = [];
                    this.canWriteSkills = false;
                    this._skillsLoaded = false;
                }
            } finally {
                if (gen === this._skillsListGen) {
                    this._skillsListInflight = null;
                }
            }
            return this.skillsCache;
        })();
        return this._skillsListInflight;
    }

    _visibleBuiltinCommands() {
        // Root `/` menu: hide folder children (they live under /mode).
        return (this.builtinCommands || []).filter((c) => !c.folder);
    }

    _modeBuiltinCommands() {
        return (this.builtinCommands || []).filter((c) => c.folder === "mode");
    }

    _allBuiltinCommands() {
        return (this.builtinCommands || []).slice();
    }

    _invalidateSkillsCache() {
        this.skillsCache = null;
        this._skillsLoaded = false;
        this._skillsListInflight = null;
        this._skillsListGen += 1;
    }

    _ownedSkillItems(skills) {
        return this._skillItems((skills || []).filter((s) => s.mine && !s.is_system));
    }

    // Ítems de skill (kebab) para el menú flotante, A–Z por slash.
    // Los comandos built-in no pasan por aquí: siguen el orden de usabilidad.
    _skillItems(skills) {
        const sorted = (skills || []).slice().sort((a, b) => {
            const ac = (a.code || "").toLowerCase();
            const bc = (b.code || "").toLowerCase();
            return ac.localeCompare(bc, undefined, { sensitivity: "base" });
        });
        return sorted.map((s) => {
            let badgeLabel = "";
            if (s.mine) {
                badgeLabel = _t("mine");
            } else if (s.is_system) {
                badgeLabel = _t("system");
            }
            return {
                code: s.code, name: s.name, description: s.description,
                argHint: s.arg_hint || "", argsPolicy: s.args_policy || "",
                kind: "skill",
                mine: !!s.mine, is_system: !!s.is_system,
                badgeLabel,
            };
        });
    }

    // Placeholder dinámico: pista de argumentos (arg_hint) del skill cuyo
    // "/<code>" se está tecleando/eligiendo; por defecto, el texto genérico.
    _placeholderForSkillCode(skills, code) {
        if (!code) {
            return DEFAULT_INPUT_PLACEHOLDER;
        }
        const s = (skills || []).find(
            (x) => (x.code || "").toLowerCase() === code.toLowerCase()
        );
        if (s && s.arg_hint) {
            return _t("Arguments, e.g.: %s", s.arg_hint);
        }
        return DEFAULT_INPUT_PLACEHOLDER;
    }

    _resetInputPlaceholder() {
        this.state.inputPlaceholder = DEFAULT_INPUT_PLACEHOLDER;
    }

    // Comandos built-in + skills filtrados por fragmento (autocompletado al teclear).
    // Prefix search includes /mode children so /painter-… still works from root.
    _filterSlashItems(skills, q) {
        const all = [...this._allBuiltinCommands(), ...this._skillItems(skills)];
        if (!q) {
            return all;
        }
        return all.filter(
            (c) =>
                (c.code || "").toLowerCase().includes(q) ||
                (c.name || "").toLowerCase().includes(q) ||
                (c.description || "").toLowerCase().includes(q)
        );
    }

    async _fillOwnedSkillPicker(query, mode = "delete") {
        const skills = await this._ensureSkills();
        const q = (query || "").toLowerCase();
        let items = this._ownedSkillItems(skills);
        if (q) {
            items = items.filter(
                (c) =>
                    (c.code || "").toLowerCase().includes(q) ||
                    (c.name || "").toLowerCase().includes(q)
            );
        }
        this.state.slashMode = mode === "rename" ? "rename" : "delete";
        this.state.slashItems = items.slice(0, 50);
        this.state.slashIndex = 0;
        this.state.slashOpen = items.length > 0;
        if (!items.length && !q) {
            this.notification.add(
                mode === "rename"
                    ? _t("You have no skills to rename.")
                    : _t("You have no skills to delete."),
                { type: "warning" },
            );
        }
    }

    async _updateSlashSuggestions(text) {
        const deletePick = /^\/delete-skill(?:\s+(\S*))?$/i.exec(text || "");
        if (deletePick && (text || "").includes(" ")) {
            await this._ensureSkills();
            if (this.canWriteSkills) {
                await this._fillOwnedSkillPicker(deletePick[1] || "");
                return;
            }
        }
        const renamePick = /^\/rename-skill(?:\s+(\S*))?(?:\s+(\S+))?\s*$/i.exec(text || "");
        if (renamePick && (text || "").includes(" ") && !renamePick[2]) {
            await this._ensureSkills();
            if (this.canWriteSkills) {
                await this._fillOwnedSkillPicker(renamePick[1] || "", "rename");
                return;
            }
        }
        const m = /^\/(\S*)$/.exec(text || "");
        if (!m) {
            this.state.slashOpen = false;
            this.state.slashItems = [];
            this.state.slashMode = "commands";
            return;
        }
        const token = m[1].toLowerCase();
        let items;
        // O19: bus may not have invalidated yet. Re-read when opening `/`
        // or listing skills — not on every extra letter of the same stroke.
        const opening = !this.state.slashOpen;
        await this._ensureSkills(
            opening || !token || this.state.slashMode === "skills",
        );
        if (!token) {
            // "/" a secas: menú de comandos; skills tras /skills; modes tras /mode.
            if (this.state.slashMode === "skills") {
                items = this._skillItems(this.skillsCache || []);
            } else if (this.state.slashMode === "mode") {
                items = this._modeBuiltinCommands().slice();
            } else {
                items = this._visibleBuiltinCommands().slice();
            }
        } else {
            this.state.slashMode = "commands";
            items = this._filterSlashItems(this.skillsCache || [], token);
        }
        this.state.slashItems = items.slice(0, 50);
        this.state.slashIndex = 0;
        this.state.slashOpen = items.length > 0;
    }

    /**
     * Close slash UI when the overlay is hidden (elephant / navbar).
     * Keeps state consistent even though the menu is inside the overlay DOM.
     */
    _closeSlashUi() {
        this.state.slashOpen = false;
        this.state.slashItems = [];
        this.state.slashMode = "commands";
    }

    _applySlashSelection(item) {
        if (!item) {
            return;
        }
        if (this.state.slashMode === "delete" && item.kind === "skill") {
            this.state.slashOpen = false;
            this.state.slashItems = [];
            this.state.currentInput = "";
            this._resetInputPlaceholder();
            this._confirmDeleteSkill(item.code);
            return;
        }
        if (this.state.slashMode === "rename" && item.kind === "skill") {
            this.state.slashOpen = false;
            this.state.slashItems = [];
            this.state.slashMode = "commands";
            this.state.currentInput = "/rename-skill " + item.code + " ";
            this.state.inputPlaceholder = _t("New slash name, then press Enter");
            if (this.inputRef.el) {
                this.inputRef.el.focus();
            }
            return;
        }
        this.state.slashOpen = false;
        this.state.slashItems = [];
        if (item.kind === "builtin") {
            if (item.code === "create-skill") {
                this._beginCreateSkillInput();
                return;
            }
            if (item.code === "delete-skill") {
                this.state.currentInput = "/delete-skill ";
                this.state.inputPlaceholder = _t("Skill to delete, e.g.: %s", item.argHint);
                this._fillOwnedSkillPicker("");
                if (this.inputRef.el) {
                    this.inputRef.el.focus();
                }
                return;
            }
            if (item.code === "rename-skill") {
                this.state.currentInput = "/rename-skill ";
                this.state.inputPlaceholder = _t("Skill to rename, e.g.: %s", item.argHint);
                this._fillOwnedSkillPicker("", "rename");
                if (this.inputRef.el) {
                    this.inputRef.el.focus();
                }
                return;
            }
            if (item.deferArg) {
                this.state.slashMode = "commands";
                this.state.currentInput = "/" + item.code + " ";
                this.state.inputPlaceholder = item.placeholder
                    || (item.argHint
                        ? _t("Arguments, e.g.: %s", item.argHint)
                        : DEFAULT_INPUT_PLACEHOLDER);
                if (this.inputRef.el) {
                    this.inputRef.el.focus();
                }
                return;
            }
            // Un comando built-in se ejecuta al elegirlo (no se manda al LLM).
            this.state.currentInput = "";
            this._runBuiltinCommand(item.code);
            return;
        }
        // Skill: se inserta "/<code> " para añadir argumentos y enviar con Intro.
        this.state.slashMode = "commands";
        this.state.currentInput = "/" + item.code + " ";
        // Pista de argumentos del skill elegido como placeholder dinámico.
        this.state.inputPlaceholder = item.argHint
            ? _t("Arguments, e.g.: %s", item.argHint)
            : DEFAULT_INPUT_PLACEHOLDER;
        if (this.inputRef.el) {
            this.inputRef.el.focus();
        }
    }

    _isHelpArg(arg) {
        const t = String(arg || "").trim().toLowerCase();
        if (!t) {
            return false;
        }
        return (
            /^[?¿？]+$/.test(t)
            || ["help", "ayuda", "options", "opciones", "usage", "uso",
                "/?", "/help", "/ayuda"].includes(t)
        );
    }

    _escSlash(text) {
        return String(text || "")
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;");
    }

    _slashHelpMarkdown(meta) {
        const code = (meta && meta.code) || "skill";
        const name = (meta && meta.name) || code;
        const desc = (meta && meta.description) || "";
        const hint = (meta && (meta.argHint || meta.arg_hint)) || "";
        const policy = (meta && (meta.argsPolicy || meta.args_policy)) || "none";
        const owner = (meta && (meta.ownerName || meta.owner_name)) || "";
        const ownerKind = (meta && (meta.ownerKind || meta.owner_kind)) || "";
        const ownerLine = (ownerKind === "user" && owner) ? owner : _t("Common");
        let policyLine = _t("This command takes no arguments. Help is deterministic (no AI).");
        if (policy === "default") {
            policyLine = _t("Empty arguments run with the built-in default. Help is deterministic (no AI).");
        } else if (policy === "ask") {
            policyLine = _t("This command asks for arguments when none are given. Help is deterministic (no AI).");
        }
        let md = `# /${code}\n\n**${name}**\n\n`;
        if (desc) {
            md += `${desc}\n\n`;
        }
        md += `**${_t("Owner")}:** ${ownerLine}\n\n`;
        md += `**${_t("Parameters")}:**\n\n`;
        const params = (meta && meta.params) || [];
        if (params.length) {
            md += `| ${_t("Name")} | ${_t("Type")} | ${_t("Description")} | ${_t("Default")} |\n`;
            md += "| --- | --- | --- | --- |\n";
            params.forEach((row) => {
                md += `| \`${row.name}\` | ${row.type || "string"} | ${row.desc || "—"} | ${row.default || "—"} |\n`;
            });
            md += "\n";
        } else {
            md += `${_t("No formal parameters.")}\n\n`;
        }
        if (hint) {
            md += `\`/${code} ${hint}\`\n\n`;
        }
        md += `${policyLine}\n`;
        return md;
    }

    _slashHelpHtml(meta) {
        return this._formatMarkdown(this._slashHelpMarkdown(meta));
    }

    _showBuiltinHelp(code) {
        const item = (this.builtinCommands || []).find((c) => c.code === code) || {
            code, name: code, argsPolicy: "none",
        };
        const md = this._slashHelpMarkdown(item);
        this.state.currentInput = "";
        this.state.slashOpen = false;
        this.state.slashItems = [];
        this._resetInputPlaceholder();
        this.state.messages.push(this._buildAssistantMessage(md, {
            model: "Chatboo",
            provider: "local",
            local_ack: true,
        }));
        this._scrollSoon();
    }

    // Devuelve { code, arg, arg2 } si el texto es un comando built-in reconocido.
    _matchBuiltinCommand(text) {
        const trimmed = (text || "").trim();
        const helpMatch = /^\/(\S+)\s+(\S+)\s*$/.exec(trimmed);
        if (helpMatch && this._isHelpArg(helpMatch[2])) {
            const code = helpMatch[1].toLowerCase();
            if (/^(painter-local|painter-free|foot-verbose|foot-laconic|show-table|show-chart)$/.test(code)) {
                return null;
            }
            if (["skills", "skill", "help", "ayuda", "?"].includes(code)) {
                return { code: "skills", arg: helpMatch[2], help: true };
            }
            if ((this.builtinCommands || []).some((c) => c.code === code)) {
                return { code, arg: helpMatch[2], help: true };
            }
        }
        const createMatch = /^\/create-skill(?:\s+(\S+)(?:\s+(\S+))?)?\s*$/i.exec(trimmed);
        if (createMatch) {
            return {
                code: "create-skill",
                arg: createMatch[1] || null,
                arg2: createMatch[2] || null,
            };
        }
        const deleteMatch = /^\/delete-skill(?:\s+([a-z0-9][a-z0-9-]{0,47}))?\s*$/i.exec(trimmed);
        if (deleteMatch) {
            return { code: "delete-skill", arg: deleteMatch[1] ? deleteMatch[1].toLowerCase() : null };
        }
        const renameMatch = /^\/rename-skill(?:\s+(\S+)(?:\s+(\S+))?)?\s*$/i.exec(trimmed);
        if (renameMatch) {
            return {
                code: "rename-skill",
                arg: renameMatch[1] ? renameMatch[1].toLowerCase() : null,
                arg2: renameMatch[2] ? renameMatch[2].toLowerCase() : null,
            };
        }
        const m = /^\/(\S+)\s*$/.exec(trimmed);
        if (!m) {
            return null;
        }
        const code = m[1].toLowerCase();
        // Axis slashes go to the server (one-shot confirm / strip+query).
        if (/^(painter-local|painter-free|foot-verbose|foot-laconic|show-table|show-chart)$/.test(code)) {
            return null;
        }
        return this.builtinCommands.some((c) => c.code === code) ? { code, arg: null } : null;
    }

    async _runBuiltinCommand(builtin) {
        const code = typeof builtin === "string" ? builtin : builtin.code;
        const arg = typeof builtin === "object" ? builtin.arg : null;
        const arg2 = typeof builtin === "object" ? builtin.arg2 : null;
        if (builtin && typeof builtin === "object" && (builtin.help || this._isHelpArg(arg))) {
            this._showBuiltinHelp(code);
            return;
        }
        if (code === "create-skill" || code === "delete-skill" || code === "rename-skill") {
            await this._ensureSkills();
            if (!this.canWriteSkills) {
                this.notification.add(
                    _t("AI Writer permission is required to manage skills from Chatboo."),
                    { type: "warning" },
                );
                return;
            }
        }
        if (code === "create-skill") {
            this.state.slashOpen = false;
            this.state.slashItems = [];
            await this._runCreateSkillCommand(arg, arg2);
            return;
        }
        if (code === "delete-skill") {
            this.state.currentInput = "";
            this.state.slashOpen = false;
            this.state.slashItems = [];
            this._resetInputPlaceholder();
            if (!arg) {
                this.state.currentInput = "/delete-skill ";
                await this._fillOwnedSkillPicker("");
                return;
            }
            await this._confirmDeleteSkill(arg);
            return;
        }
        if (code === "rename-skill") {
            this.state.slashOpen = false;
            this.state.slashItems = [];
            if (!arg) {
                this.state.currentInput = "/rename-skill ";
                this.state.inputPlaceholder = _t("Skill to rename, e.g.: %s", "old-name new-name");
                await this._fillOwnedSkillPicker("", "rename");
                return;
            }
            if (!arg2) {
                this.state.currentInput = "/rename-skill " + arg + " ";
                this.state.inputPlaceholder = _t("New slash name, then press Enter");
                return;
            }
            this.state.currentInput = "";
            this._resetInputPlaceholder();
            await this._runRenameSkill(arg, arg2);
            return;
        }
        if (code === "mode") {
            await this._openModeMenu();
            return;
        }
        // /skills abre el MENÚ flotante (nunca se vuelca texto al chat).
        await this._openSkillsMenu();
    }

    async _confirmDeleteSkill(skillCode) {
        if (!skillCode) {
            return;
        }
        if (!window.confirm(_t("Delete skill /%s? This cannot be undone.", skillCode))) {
            return;
        }
        try {
            const res = await rpc("/chatboo/delete-skill", {
                skill_code: skillCode,
                session_id: this.state.currentSessionId,
            });
            if (!res || res.status !== "ok") {
                this.notification.add((res && res.message) || _t("Could not delete the skill."), {
                    type: "danger",
                });
                return;
            }
            this._invalidateSkillsCache();
            if (this.state.currentSessionId) {
                await this._loadSession(this.state.currentSessionId);
            } else {
                this.notification.add(_t("Skill /%s deleted.", res.deleted || skillCode), {
                    type: "success",
                });
            }
        } catch (e) {
            this.notification.add((e && e.message) || _t("Could not delete the skill."), {
                type: "danger",
            });
        }
    }

    async _runRenameSkill(oldCode, newCode) {
        try {
            const res = await rpc("/chatboo/rename-skill", {
                old_code: oldCode,
                new_code: newCode,
                session_id: this.state.currentSessionId,
            });
            if (!res || res.status !== "ok") {
                this.notification.add((res && res.message) || _t("Could not rename the skill."), {
                    type: "danger",
                });
                return;
            }
            this._invalidateSkillsCache();
            if (this.state.currentSessionId) {
                await this._loadSession(this.state.currentSessionId);
            } else {
                this.notification.add(
                    _t("Skill renamed: /%s → /%s", res.old || oldCode, res.new || newCode),
                    { type: "success" },
                );
            }
        } catch (e) {
            this.notification.add((e && e.message) || _t("Could not rename the skill."), {
                type: "danger",
            });
        }
    }

    _looksLikeTurnId(token) {
        return /^[A-Za-z0-9]{4}(?:-\d+)?$/.test(token || "");
    }

    _normalizeTurnIdToken(token) {
        const raw = String(token || "").trim().replace(/-\d+$/, "");
        if (!/^[A-Za-z0-9]{4}$/.test(raw)) {
            return "";
        }
        return raw.toUpperCase();
    }

    _parseCreateSkillArgs(arg, arg2) {
        const t1 = (arg || "").trim();
        const t2 = (arg2 || "").trim();
        if (!t1) {
            return { skillCode: null, turnId: null };
        }
        const t1id = this._looksLikeTurnId(t1);
        const t2id = Boolean(t2) && this._looksLikeTurnId(t2);
        if (!t2) {
            if (t1id) {
                return { skillCode: null, turnId: t1 };
            }
            return { skillCode: t1, turnId: null };
        }
        if (t1id && !t2id) {
            return { skillCode: t2, turnId: t1 };
        }
        if (!t1id && t2id) {
            return { skillCode: t1, turnId: t2 };
        }
        return { skillCode: t2, turnId: t1 };
    }

    _formatInstanceSlash(name) {
        const pfx = this.skillCommandPrefix || "";
        let slug = this._slugifySkillCode(name);
        if (pfx) {
            const bare = pfx.replace(/-$/, "");
            if (slug === bare) {
                return pfx + "captured-skill";
            }
            if (slug.startsWith(pfx)) {
                const rest = slug.slice(pfx.length).replace(/^-+/, "");
                if (rest) {
                    slug = rest;
                }
            }
        }
        return (pfx + slug) || slug;
    }

    _beginCreateSkillInput() {
        const turn = this._lastTurnId();
        this.state.slashOpen = false;
        this.state.slashItems = [];
        this.state.slashMode = "commands";
        if (turn) {
            this.state.currentInput = "/create-skill " + turn + " ";
            this.state.inputPlaceholder = _t(
                "Slash name (instance prefix is applied), then press Enter"
            );
        } else {
            this.state.currentInput = "/create-skill ";
            this.state.inputPlaceholder = _t(
                "Paste or type the 4-character chip, then the slash name"
            );
            this.notification.add(
                _t("Turn id is required. Paste or type the 4-character chip, then the slash name."),
                { type: "warning" },
            );
        }
        if (this.inputRef.el) {
            this.inputRef.el.focus();
        }
    }

    _slugifySkillCode(text) {
        const slug = String(text || "")
            .trim()
            .toLowerCase()
            .replace(/[^a-z0-9]+/g, "-")
            .replace(/^-+|-+$/g, "")
            .slice(0, 48);
        return slug || "captured-skill";
    }

    _plainTextFromChatMessage(msg) {
        const raw = (msg && (msg.raw || msg.content)) || "";
        if (!raw) {
            return "";
        }
        if (typeof document !== "undefined") {
            const tmp = document.createElement("div");
            tmp.innerHTML = String(raw);
            return (tmp.textContent || tmp.innerText || "").trim();
        }
        return String(raw).replace(/<[^>]+>/g, " ").trim();
    }

    _messageTurnId(msg) {
        if (!msg) {
            return "";
        }
        return this._normalizeTurnIdToken(
            msg.correlation_id
            || (msg.meta && msg.meta.correlation_id)
            || (msg.context_info && msg.context_info.turnCode)
            || ""
        );
    }

    _lastTurnId() {
        const msgs = this.state.messages || [];
        for (let i = msgs.length - 1; i >= 0; i--) {
            if (msgs[i].role !== "assistant") {
                continue;
            }
            const turn = this._messageTurnId(msgs[i]);
            if (turn) {
                return turn;
            }
        }
        return "";
    }

    _proposeSkillNameForTurn(turnId) {
        const want = this._normalizeTurnIdToken(turnId);
        const msgs = this.state.messages || [];
        let assistantIdx = -1;
        if (want) {
            for (let i = msgs.length - 1; i >= 0; i--) {
                if (msgs[i].role !== "assistant") {
                    continue;
                }
                if (this._messageTurnId(msgs[i]) === want) {
                    assistantIdx = i;
                    break;
                }
            }
        }
        const start = assistantIdx >= 0 ? assistantIdx - 1 : msgs.length - 1;
        for (let i = start; i >= 0; i--) {
            if (msgs[i].role !== "user") {
                continue;
            }
            const plain = this._plainTextFromChatMessage(msgs[i]);
            if (plain && !plain.startsWith("/")) {
                return this._slugifySkillCode(plain.slice(0, 64));
            }
        }
        return "captured-skill";
    }

    _promptCreateSkillConfirm(skillCode, turnId, reason) {
        const name = this._formatInstanceSlash(
            skillCode || this._proposeSkillNameForTurn(turnId)
        );
        const turn = this._normalizeTurnIdToken(turnId) || this._lastTurnId();
        const line = turn
            ? `/create-skill ${turn} ${name}`
            : (name ? `/create-skill ${name}` : "/create-skill ");
        this.state.currentInput = line;
        this.state.slashOpen = false;
        this.state.slashItems = [];
        this.state.inputPlaceholder = turn
            ? _t("Edit turn id and slash name if needed, then press Enter")
            : _t("Paste or type the 4-character chip, then the slash name");
        let msg;
        if (!turn) {
            msg = _t(
                "Turn id is required. Paste or type the 4-character chip, then the slash name."
            );
        } else if (reason === "need_name") {
            msg = _t(
                "Proposed slash name from that turn (instance prefix applied). "
                + "Edit if needed, then press Enter to open the wizard."
            );
        } else {
            msg = _t(
                "Confirm turn id and slash name. Edit if needed, then press Enter "
                + "to open the wizard."
            );
        }
        const html = (
            '<div class="card border-0 shadow-sm o_chatboo_slash_help"><div class="card-body">'
            + `<p class="mb-2">${this._escSlash(msg)}</p>`
            + `<p class="mb-0 small"><code>${this._escSlash(line)}</code></p>`
            + "</div></div>"
        );
        this.state.messages.push(this._buildAssistantMessage(html, {
            model: "Chatboo",
            provider: "local",
            local_ack: true,
        }));
        this._scrollSoon();
        if (this.inputRef.el) {
            this.inputRef.el.focus();
        }
    }

    _restoreChatbooOverlayZ(overlay, prevZ) {
        if (!overlay) {
            return;
        }
        overlay.style.zIndex = prevZ || "1050";
    }

    async _runCreateSkillCommand(skillCodeHint, turnId) {
        if (!this.state.currentSessionId) {
            this.notification.add(_t("No active session."), { type: "warning" });
            return;
        }
        const parsed = this._parseCreateSkillArgs(skillCodeHint, turnId);
        if (!parsed.turnId && !parsed.skillCode) {
            this._beginCreateSkillInput();
            return;
        }
        if (!parsed.turnId) {
            this._promptCreateSkillConfirm(
                parsed.skillCode,
                this._lastTurnId(),
                "need_turn",
            );
            return;
        }
        if (!parsed.skillCode) {
            this._promptCreateSkillConfirm(null, parsed.turnId, "need_name");
            return;
        }
        try {
            const params = {
                session_id: this.state.currentSessionId,
                skill_code: this._formatInstanceSlash(parsed.skillCode),
                turn_id: parsed.turnId,
            };
            const res = await rpc("/chatboo/create-skill", params);
            if (!res || res.status !== "ok" || !res.action) {
                this.notification.add((res && res.message) || _t("Could not open the skill wizard."), {
                    type: "danger",
                });
                return;
            }
            if (res.warning) {
                this.notification.add(res.warning, { type: "warning" });
            }
            // Chatboo overlay is z-index 1050; lower it so the capture wizard is visible.
            const overlay = document.getElementById("o_chatboo_persistent_overlay");
            const prevZ = overlay ? overlay.style.zIndex : "";
            if (overlay) {
                overlay.style.zIndex = "1000";
            }
            let restored = false;
            const restore = () => {
                if (restored) {
                    return;
                }
                restored = true;
                this._restoreChatbooOverlayZ(overlay, prevZ);
                this._invalidateSkillsCache();
                if (this.state.currentSessionId) {
                    this._loadSession(this.state.currentSessionId);
                }
            };
            try {
                await this.action.doAction(res.action, { onClose: restore });
            } catch (e) {
                restore();
                throw e;
            }
        } catch (e) {
            this.notification.add((e && e.message) || _t("Could not open the skill wizard."), {
                type: "danger",
            });
        }
    }

    // Abre el desplegable mostrando todas las skills disponibles para elegir.
    async _openSkillsMenu() {
        const skills = await this._ensureSkills(true);
        this.state.slashMode = "skills";
        this.state.currentInput = "/";
        this.state.slashItems = this._skillItems(skills).slice(0, 50);
        this.state.slashIndex = 0;
        this.state.slashOpen = this.state.slashItems.length > 0;
        if (this.inputRef.el) {
            this.inputRef.el.focus();
        }
    }

    // Abre el desplegable de modos de presentación (painter / foot / show-*).
    async _openModeMenu() {
        this.state.slashMode = "mode";
        this.state.currentInput = "/";
        this.state.slashItems = this._modeBuiltinCommands().slice();
        this.state.slashIndex = 0;
        this.state.slashOpen = this.state.slashItems.length > 0;
        this._resetInputPlaceholder();
        if (this.inputRef.el) {
            this.inputRef.el.focus();
        }
    }

    onInput(ev) {
        this.state.currentInput = ev.target.value;
        this._updateSlashSuggestions(ev.target.value);
        this._syncArgPlaceholder(ev.target.value);
        this._syncPromptHeight();
    }

    // Pegar una imagen (Ctrl+V) → se adjunta al turno y viaja al modelo de visión
    // como un chat de IA normal. Si el portapapeles trae solo texto, dejamos el
    // pegado nativo.
    onPaste(ev) {
        const items = (ev.clipboardData && ev.clipboardData.items) || [];
        const files = [];
        for (const it of items) {
            if (it.kind === "file" && it.type && it.type.startsWith("image/")) {
                const f = it.getAsFile();
                if (f) {
                    files.push(f);
                }
            }
        }
        if (!files.length) {
            return;
        }
        ev.preventDefault();
        for (const f of files) {
            this._attachImageFile(f);
        }
    }

    // Clase de icono FA para el chip de un fichero (por mimetype/extensión).
    _fileIcon(mfile) {
        return chatbooFileIcon((mfile && mfile.mimetype) || "", (mfile && mfile.name) || "");
    }

    _fileBannerTone(mfile) {
        const mt = ((mfile && mfile.mimetype) || "").split(";")[0].trim().toLowerCase();
        const name = ((mfile && mfile.name) || "").toLowerCase();
        const ext = name.includes(".") ? name.split(".").pop() : "";
        if (mt === "application/pdf" || ext === "pdf") return "pdf";
        if (mt === "application/msword" || mt.includes("wordprocessing")
            || ["doc", "docx"].indexOf(ext) !== -1) return "word";
        if (mt.includes("spreadsheet") || mt.includes("excel") || mt === "text/csv"
            || ["xls", "xlsx", "ods", "csv"].indexOf(ext) !== -1) return "excel";
        if (mt.includes("json") || mt.includes("xml") || mt.includes("javascript") || mt.includes("html")
            || ["json", "xml", "js", "html", "css", "py"].indexOf(ext) !== -1) return "code";
        if (mt.startsWith("text/") || ["txt", "md", "log", "markdown"].indexOf(ext) !== -1) return "text";
        return "other";
    }

    messageWantsWideCanvas(msg) {
        if (!msg || msg.role === "user") {
            return false;
        }
        const clip = msg.clip_data;
        if (clip && (clip.include_chart || clip.include_table
            || (clip.rows && clip.rows.length))) {
            return true;
        }
        const html = String(msg.htmlSrc || msg.raw || "");
        if (/data-chatboo-show-mode="(?:show-table|show-chart|chart-table|dashboard)"/.test(html)) {
            return true;
        }
        return html.indexOf("o_chatboo_table_block") !== -1
            || html.indexOf("o_chatboo_dashboard") !== -1
            || /<table[\s>]/i.test(html);
    }

    _fileBannerCardClass(mfile) {
        return "o_chatboo_file_banner_card o_chatboo_file_banner_" + this._fileBannerTone(mfile);
    }

    _fileSizeLabel(mfile) {
        const n = mfile && mfile.size;
        if (n === undefined || n === null || n === "") return "";
        const num = Number(n);
        if (!Number.isFinite(num) || num < 0) return "";
        if (num < 1024) return num + " B";
        if (num < 1024 * 1024) return (num / 1024).toFixed(1) + " KB";
        return (num / (1024 * 1024)).toFixed(1) + " MB";
    }

    _fileDownloadHref(mfile) {
        return exportUtils.sessionFileHref(mfile);
    }

    _fileDownloadName(mfile) {
        if (exportUtils.sessionFileIsInline(mfile)) {
            return false;
        }
        return (mfile && mfile.name) || false;
    }

    // URL de formulario para un registro {model, id}. Deep-link clásico válido en
    // O14–O19 (el esquema /odoo/... de O17+ convive con /web#...). Se abre en
    // pestaña nueva (el enlace lleva target=_blank), respetando los permisos Odoo.
    _recordUrl(rec) {
        if (!rec || !rec.model || !rec.id) {
            return "#";
        }
        return "/web#id=" + rec.id + "&model=" + rec.model + "&view_type=form";
    }

    async _attachImageFile(file) {
        try {
            const dataUrl = await this._readFileAsDataUrl(file);
            this.state.pendingImages.push(dataUrl);
            // Conserva el nombre si viene de fichero; null si es pegado (portapapeles).
            this.state.pendingImageNames.push((file && file.name) || null);
        } catch (e) {
            this.notification.add(_t("Could not read the image."), { type: "danger" });
        }
        if (this.inputRef.el) {
            this.inputRef.el.focus();
        }
    }

    _removePendingImage(index) {
        this.state.pendingImages.splice(index, 1);
        this.state.pendingImageNames.splice(index, 1);
        if (this.inputRef.el) {
            this.inputRef.el.focus();
        }
    }

    // ── Clip: adjuntar ficheros (Fase 1: datos/texto · Fase 2: imágenes) ─────
    // Abre el selector de ficheros (input oculto). Las imágenes raster se enrutan
    // a la vía multimodal (pendingImages, igual que el pegado); el SVG va como
    // texto (es XML); el resto como fichero de datos.
    onClipClick() {
        if (this.fileInputRef && this.fileInputRef.el) {
            this.fileInputRef.el.click();
        }
    }

    // Imagen apta para modelo de visión: cualquier image/* salvo SVG (que es
    // XML y los proveedores de visión no suelen aceptarlo → mejor como texto).
    _isVisionImage(file) {
        const t = (file.type || "").toLowerCase();
        if (t === "image/svg+xml") {
            return false;
        }
        return t.startsWith("image/");
    }

    async onFilesSelected(ev) {
        const files = Array.from((ev.target && ev.target.files) || []);
        await this._ingestFiles(files);
        // Permitir re-seleccionar el mismo fichero (el change no dispara si no cambia).
        if (ev.target) {
            ev.target.value = "";
        }
        if (this.inputRef.el) {
            this.inputRef.el.focus();
        }
    }

    // Enruta una lista de ficheros (del selector o de drag&drop): imágenes de
    // visión → vía multimodal (conservan nombre); el resto → fichero de datos.
    async _ingestFiles(files) {
        for (const f of Array.from(files || [])) {
            if (f.size > 10 * 1024 * 1024) {  // tope defensivo 10 MB
                this.notification.add(
                    _t("File too large (max 10 MB):") + " " + f.name, { type: "danger" });
                continue;
            }
            if (this._isVisionImage(f)) {
                await this._attachImageFile(f);
            } else {
                await this._attachDataFile(f);
            }
        }
    }

    // ── Drag & drop de ficheros en CUALQUIER zona del chat ───────────────────
    // Solo reaccionamos a arrastres que traen ficheros (no a selección de texto
    // interna). El overlay es puramente visual (pointer-events:none), así que el
    // 'drop' siempre llega a la raíz.
    _dragHasFiles(ev) {
        const dt = ev && ev.dataTransfer;
        return !!(dt && Array.from(dt.types || []).indexOf("Files") !== -1);
    }

    _onDragOver(ev) {
        if (!this._dragHasFiles(ev)) {
            return;
        }
        ev.preventDefault();  // imprescindible para habilitar el 'drop'
        this.state.dragActive = true;
    }

    _onDragLeave(ev) {
        // Evita parpadeo al pasar por hijos: solo desactivar al salir de la raíz.
        if (ev.relatedTarget && ev.currentTarget && ev.currentTarget.contains(ev.relatedTarget)) {
            return;
        }
        this.state.dragActive = false;
    }

    async _onDrop(ev) {
        this.state.dragActive = false;
        const dt = ev && ev.dataTransfer;
        if (!(dt && dt.files && dt.files.length)) {
            return;
        }
        ev.preventDefault();
        await this._ingestFiles(dt.files);
        if (this.inputRef.el) {
            this.inputRef.el.focus();
        }
    }

    async _attachDataFile(file) {
        // Tope de tamaño defensivo (10 MB): evita meter binarios enormes en el POST.
        if (file.size > 10 * 1024 * 1024) {
            this.notification.add(
                _t("File too large (max 10 MB):") + " " + file.name, { type: "danger" });
            return;
        }
        try {
            const dataUrl = await this._readFileAsDataUrl(file);
            this.state.pendingFiles.push({
                name: file.name,
                mimetype: file.type || "",
                size: file.size,
                data: dataUrl,
            });
        } catch (e) {
            this.notification.add(_t("Could not read the file."), { type: "danger" });
        }
    }

    _removePendingFile(index) {
        this.state.pendingFiles.splice(index, 1);
        if (this.inputRef.el) {
            this.inputRef.el.focus();
        }
    }

    _readFileAsDataUrl(file) {
        return new Promise((resolve, reject) => {
            const reader = new FileReader();
            reader.onload = () => resolve(reader.result);
            reader.onerror = reject;
            reader.readAsDataURL(file);
        });
    }

    // Fija el placeholder según el "/<code>" del principio del input (con o sin
    // argumentos). Usa la caché de skills (sin RPC); si no hay skill, el genérico.
    _syncArgPlaceholder(text) {
        const m = /^\/(\S+)/.exec((text || "").trim());
        if (!m) {
            this._resetInputPlaceholder();
            return;
        }
        this.state.inputPlaceholder = this._placeholderForSkillCode(
            this.skillsCache || [], m[1]
        );
    }

    /**
     * Keep the highlighted slash row inside the overflow menu (O14 does this
     * in _syncSlashMenu). Arrow keys only change slashIndex; without this the
     * list only moves with the mouse wheel.
     */
    _scrollSlashActive() {
        const menu = this.slashMenuRef && this.slashMenuRef.el;
        if (!menu || !this.state.slashOpen) {
            return;
        }
        const active = menu.querySelector(".dropdown-item.active");
        if (!active) {
            return;
        }
        const menuRect = menu.getBoundingClientRect();
        const rowRect = active.getBoundingClientRect();
        if (rowRect.bottom > menuRect.bottom) {
            menu.scrollTop += rowRect.bottom - menuRect.bottom;
        } else if (rowRect.top < menuRect.top) {
            menu.scrollTop -= menuRect.top - rowRect.top;
        }
    }

    onKeydown(ev) {
        // Navegación del desplegable de skills (tiene prioridad sobre el resto).
        if (this.state.slashOpen && this.state.slashItems.length) {
            if (ev.key === "ArrowDown") {
                ev.preventDefault();
                this.state.slashIndex = (this.state.slashIndex + 1) % this.state.slashItems.length;
                return;
            }
            if (ev.key === "ArrowUp") {
                ev.preventDefault();
                this.state.slashIndex =
                    (this.state.slashIndex - 1 + this.state.slashItems.length) % this.state.slashItems.length;
                return;
            }
            if (ev.key === "Enter" || ev.key === "Tab") {
                ev.preventDefault();
                // /create-skill (and friends with deferArg): Enter must run the
                // command, not just re-insert "/code " from the slash picker.
                if (ev.key === "Enter") {
                    const builtin = this._matchBuiltinCommand(this.state.currentInput);
                    if (builtin && (
                        builtin.code === "create-skill"
                        || builtin.help
                        || this._isHelpArg(builtin.arg)
                    )) {
                        this.state.slashOpen = false;
                        this.state.slashItems = [];
                        this._sendMessage();
                        return;
                    }
                }
                this._applySlashSelection(this.state.slashItems[this.state.slashIndex]);
                return;
            }
            if (ev.key === "Escape") {
                ev.preventDefault();
                this.state.slashOpen = false;
                this.state.slashMode = "commands";
                return;
            }
        }
        // Ctrl/Cmd+Enter: nueva línea (nunca envía). Enter solo: envía.
        if (ev.key === "Enter" && (ev.ctrlKey || ev.metaKey)) {
            ev.preventDefault();
            this._insertPromptNewline(ev.target);
            return;
        }
        if (ev.key === "Enter" && !ev.shiftKey && !ev.altKey) {
            ev.preventDefault();
            this._sendMessage();
            return;
        }
        if (ev.key === "ArrowUp" && this.inputHistory.length && this._promptCaretOnFirstLine(ev.target)) {
            if (this.historyIndex === -1) {
                this.historyIndex = 0;
                this.state.currentInput = this.inputHistory[this.inputHistory.length - 1] || "";
                this.state.promptCollapsed = false;
                ev.preventDefault();
                Promise.resolve().then(() => this._syncPromptHeight());
            } else if (this.historyIndex < this.inputHistory.length - 1) {
                this.historyIndex += 1;
                this.state.currentInput = this.inputHistory[this.inputHistory.length - 1 - this.historyIndex] || "";
                this.state.promptCollapsed = false;
                ev.preventDefault();
                Promise.resolve().then(() => this._syncPromptHeight());
            }
        } else if (ev.key === "ArrowDown" && this.inputHistory.length && this._promptCaretOnLastLine(ev.target)) {
            if (this.historyIndex > 0) {
                this.historyIndex -= 1;
                this.state.currentInput = this.inputHistory[this.inputHistory.length - 1 - this.historyIndex] || "";
                this.state.promptCollapsed = false;
                ev.preventDefault();
                Promise.resolve().then(() => this._syncPromptHeight());
            } else if (this.historyIndex === 0) {
                this.historyIndex = -1;
                this.state.currentInput = "";
                this.state.promptCollapsed = false;
                ev.preventDefault();
                Promise.resolve().then(() => this._syncPromptHeight());
            }
        }
    }
}

export default ChatbooApp;
