/** @odoo-module **/
/* SPDX-License-Identifier: Apache-2.0 */
/* Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com> */
/**
 * Chatboo conversational client (OWL2 / Odoo 17+).
 * Reuses the Chatboo backend (sessions + SSE /chatboo/stream).
 */

import { Component, useState, useRef, useEffect, markup, onWillStart, onMounted, onWillUnmount, onPatched, xml } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { useBus } from "@web/core/utils/hooks";
import { rpc } from "@web/core/network/rpc";
import { _t } from "@web/core/l10n/translation";
import { session } from "@web/session";
import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import * as exportUtils from "./chatboo_export";
import {
    getSessionLocale,
    formatWallclock,
    formatContent as sharedFormatContent,
    formatMarkdown as sharedFormatMarkdown,
    sanitizeHtml,
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
const ChatbooTurn = globalThis.ChatbooTurn;

// Default input placeholder; replaced by the skill's argument hint
// (arg_hint) when the user picks or types "/<code> ".
const DEFAULT_INPUT_PLACEHOLDER = _t(
    "Ask Chatboo AI... (/ for commands & skills, ↑↓ for history)"
);

/** Max visible lines for the multiline prompt (future: Settings). */
const CHATBOO_PROMPT_MAX_LINES = 10;

// FontAwesome class (FA4, available in O14–O19) for a file's chip by its
// mimetype/extension. Returns only the specific class (e.g. "fa-file-pdf-o");
// the caller prepends "fa ". Generic fallback "fa-file-o".
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

/** Renders server-side (Python) HTML without going through the t-out sanitizer (O19). */
class ChatbooHtmlRenderer extends Component {
    static template = xml`<div class="o_chatboo_content" t-ref="root"/>`;
    static props = { html: { type: String, optional: true } };

    setup() {
        this.root = useRef("root");
        this._paintedHtml = undefined;
        const paint = (force) => {
            if (!this.root.el) {
                return;
            }
            const html = this.props.html || "";
            if (!force && this._paintedHtml === html) {
                return;
            }
            this._paintedHtml = html;
            if (window.ChatbooDashboard && typeof window.ChatbooDashboard.destroyIn === "function") {
                window.ChatbooDashboard.destroyIn(this.root.el);
            } else if (window.ChatbooCharts && typeof window.ChatbooCharts.destroyIn === "function") {
                window.ChatbooCharts.destroyIn(this.root.el);
            }
            this.root.el.innerHTML = sanitizeHtml(html);
            if (window.ChatbooDashboard && typeof window.ChatbooDashboard.hydrateContent === "function") {
                window.ChatbooDashboard.hydrateContent(this.root.el);
            } else if (window.ChatbooCharts && typeof window.ChatbooCharts.hydrate === "function") {
                window.ChatbooCharts.hydrate(this.root.el);
            }
            if (window.ChatbooSvgCards && typeof window.ChatbooSvgCards.hydrate === "function") {
                window.ChatbooSvgCards.hydrate(this.root.el);
            }
        };
        onMounted(() => paint(true));
        onPatched(() => paint(false));
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
        this._applyResultLabels();

        this.state = useState({
            messages: [],            // {role, content(markup), raw, ts}
            currentInput: "",
            promptNonempty: false,   // DOM prompt text; avoids rebinding full string on each key
            thinking: false,
            canCancel: false,          // a cancellable stream is running
            streamingPreview: null,  // markup | null
            streamingHtml: null,       // raw server-side HTML (innerHTML)
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
            showSeriesStats: false,
            pendingImages: [],       // pasted images (data URLs) to send with the turn
            pendingImageNames: [],   // names aligned by index (null if pasted from the clipboard)
            pendingFiles: [],        // text/data files attached with the clip
            dragActive: false,       // visual overlay while files are dragged over the chat
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
        this.tipSource = _t("Source:");
        this.tipDownloadPdf = _t("Download as PDF");
        this.tipDownloadExcel = _t("Download as Excel");
        this.tipDownloadWord = _t("Download as Word");
        this.tipRestoreCardWidth = _t("Restore default width");
        this.tipDownloadFile = _t("Download");
        this.tipPrepareFile = _t("Prepare and download");
        this.tipCopyContent = _t("Copy content");
        this.tipCopyMarkdown = _t("Copy as Markdown");
        this.tipGoToEnd = _t("Go to end of turn");
        this.tipGoToStart = _t("Go to start of turn");
        this.tipCopyClipboard = _t("Copy to clipboard");
        this.tipOpenImage = _t("Open image");
        this.tipCancel = _t("Cancel");
        this.tipExpandPrompt = _t("Expand prompt");
        this.tipCollapsePrompt = _t("Collapse prompt");
        // Built-in "/" palette. Axis toggles live under /mode (like skills under
        // /skills). Typing /compose-… still finds them via prefix filter.
        this.builtinCommands = [
            { code: "skills", name: "Skills", description: _t("List the available skills"), kind: "builtin", argsPolicy: "none" },
            {
                code: "create-skill",
                name: "Create skill",
                description: _t(
                    "Capture a turn as an instance skill (extra, with you as author). "
                    + "The line starts with the turn chip (filled from the last turn; "
                    + "you can change it). Then the slash name. Settings prefixes apply. "
                    + "If you already own that slash, the wizard replaces it. "
                    + "Words after the name fill the parameter description in the wizard. "
                    + "The turn chip is not a skill parameter. Help: /create-skill ?"
                ),
                argHint: "VWVN slash-name [description…]  |  ? help",
                params: [
                    {
                        name: "turn_id",
                        type: "string",
                        desc: _t("4-character MCP turn chip. Required. Auto-filled from the last turn."),
                        default: "",
                    },
                    {
                        name: "name",
                        type: "string",
                        desc: _t("Slash name. Settings prefix is applied."),
                        default: "",
                    },
                    {
                        name: "description",
                        type: "string",
                        desc: _t("Parameter description in prose. Fills the wizard. Not the turn chip."),
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
                code: "edit-skill",
                name: "Edit skill",
                description: _t(
                    "Open the skill wizard on a skill you created. "
                    + "Empty opens the picker. Stem, prefixed slash, or a word "
                    + "from the name. Help text and parameters are edited in the wizard. "
                    + "Help: /edit-skill ?"
                ),
                argHint: "slash-or-name  |  ? help",
                params: [
                    {
                        name: "name",
                        type: "string",
                        desc: _t("Slash or name of a skill you created. Stem or prefixed."),
                        default: _t("opens picker"),
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
                description: _t("Presentation modes (compose, footer, table/chart)"),
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
                code: "compose-model",
                name: "Compose model",
                description: _t("The model owns the whole bubble this turn"),
                placeholder: _t("Optional question…"),
                kind: "builtin",
                deferArg: true,
                argsPolicy: "none",
                folder: "mode",
            },
            {
                code: "compose-agent",
                name: "Compose Chatboo",
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
        this._paintQueue = [];
        this._appMounted = false;
        onMounted(() => {
            this._appMounted = true;
            this._scrollSoon();
            if (this.inputRef.el) {
                this.inputRef.el.focus();
            }
            if (this.props.onAppReady) {
                this.props.onAppReady(this);
            }
            this._setupRefLinkHandler();
            this._setupFormCardHandler();
            this._setupTtsClickAnchoring();
            this._applyCardWidthRatio(this._cardWidthRatio);
            this._drainPaintQueue();
        });
        onPatched(() => this._drainPaintQueue());
        onWillUnmount(() => {
            this._teardownTtsClickAnchoring();
            if (this._unsubscribeChatbooSync) {
                this._unsubscribeChatbooSync();
                this._unsubscribeChatbooSync = null;
            }
        });

        const busService = this.env.services.bus_service;
        // Odoo 19 dropped the public "notification" event. subscribe() is the
        // channel that still delivers pns_chatboo_sync (Odoo 17 and 19).
        this._chatbooSyncFromSubscribe = typeof busService.subscribe === "function";
        if (this._chatbooSyncFromSubscribe) {
            const onSync = (payload) => {
                this._onChatbooSyncPayload(payload);
            };
            const onSafePlan = (payload) => {
                this._onSafePlanBus(payload);
            };
            busService.subscribe("pns_chatboo_sync", onSync);
            busService.subscribe("pns_safe_plan", onSafePlan);
            this._unsubscribeChatbooSync = () => {
                if (typeof busService.unsubscribe === "function") {
                    busService.unsubscribe("pns_chatboo_sync", onSync);
                    busService.unsubscribe("pns_safe_plan", onSafePlan);
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

    // ──────────────────────────── Health / provider ────────────────────────────

    async _checkHealth() {
        try {
            const res = await rpc("/chatboo/check_health", {});
            this._applyProviderHeader(res);
            this.state.connected = !!res.connected;
            this.state.canSaveRaw = !!res.can_save_raw;
            // Saved even without rates: it carries the failure reason for the chip.
            this._fx = (res && res.fx) ? res.fx : null;
            this._defaultDisplayCurrency = (res && res.display_currency) || "USD";
            this._applyCardWidthRatio(res && res.card_width_ratio);
            this._applyShowSeriesStats(res && res.show_series_stats);
            this._applyCanvas(res && res.canvas_available);
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

    _applyShowSeriesStats(value) {
        const on = !!value;
        this.state.showSeriesStats = on;
        if (window.ChatbooCharts && typeof window.ChatbooCharts.setShowSeriesStats === "function") {
            window.ChatbooCharts.setShowSeriesStats(on);
        }
    }

    _applyResultLabels() {
        const charts = window.ChatbooCharts;
        if (!charts || typeof charts.setLabels !== "function") {
            return;
        }
        charts.setLabels({
            chart: _t("Chart"),
            data: _t("Data"),
            canvas: _t("Canvas"),
            canvasTitle: _t("Lay out the tables of this answer as a page"),
            canvasBuilding: _t("Building the page…"),
            canvasOpen: _t("Open page"),
            canvasFailed: _t("No page was built."),
            canvasCancel: _t("Building the page. Click to cancel."),
        });
    }

    /** Canvas button only when the engine finds someone for the Design role. */
    _applyCanvas(available) {
        const charts = window.ChatbooCharts;
        if (!charts || typeof charts.setCanvas !== "function") {
            return;
        }
        charts.setCanvas(available ? {
            rpc: (route, params) => rpc(route, params),
            sessionId: () => this.state.currentSessionId,
            question: (msgIndex) => this._questionBefore(msgIndex),
            confirmCancel: (yes) => this.dialog.add(ConfirmationDialog, {
                title: _t("Cancel the page?"),
                body: _t("The page being built will be dropped."),
                confirm: yes,
                confirmLabel: _t("Yes, cancel"),
                cancelLabel: _t("Keep waiting"),
            }),
        } : null);
    }

    _questionBefore(msgIndex) {
        const messages = this.state.messages || [];
        for (let i = Math.min(msgIndex, messages.length) - 1; i >= 0; i--) {
            const msg = messages[i];
            if (msg && msg.role === "user") {
                return String(msg.content || "").slice(0, 2000);
            }
        }
        return "";
    }

    async _toggleShowSeriesStats() {
        const on = !this.state.showSeriesStats;
        this._applyShowSeriesStats(on);
        try {
            await rpc("/chatboo/prefs", { show_series_stats: on });
        } catch (e) { /* keep in-memory flag */ }
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
        api.relayoutSoon(root);
    }

    async _saveCardWidth(ratio) {
        const api = window.ChatbooCardWidth;
        const root = this._messagesCanvas();
        const stored = (api && root) ? api.applyRatio(root, ratio) : ratio;
        this._cardWidthRatio = stored;
        if (api) {
            api.relayoutSoon(root);
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
            api.relayoutSoon(root);
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
        let preview = api.previewGuide(root, card, startW);
        const onMove = (e) => {
            preview = api.previewGuide(root, card, startW + (e.clientX - startX));
        };
        const onUp = () => {
            handle.classList.remove("is-dragging");
            document.removeEventListener("pointermove", onMove);
            document.removeEventListener("pointerup", onUp);
            document.removeEventListener("pointercancel", onUp);
            api.hideGuide(root);
            this._saveCardWidth(api.applyPx(root, preview));
        };
        document.addEventListener("pointermove", onMove);
        document.addEventListener("pointerup", onUp);
        document.addEventListener("pointercancel", onUp);
    }

    _initTtsUi() {
        const tts = window.__chatbooTts;
        if (tts && tts.setAllowRemote) {
            tts.setAllowRemote(!!session.pns_chatboo_allow_remote_voices);
        }
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

    // ──────────────────────────── Sessions ────────────────────────────

    /** Run fn once OWL has patched this component (or mounted it). */
    _afterPaint(fn) {
        this._paintQueue.push(fn);
        if (this._appMounted) {
            this.render();
        }
    }

    _drainPaintQueue() {
        for (const fn of this._paintQueue.splice(0)) {
            fn();
        }
    }

    _focusInput() {
        // Focus after the OWL repaint (closing the history modal or loading a
        // session): otherwise focus would go to body.
        const focus = () => {
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
            if (el.disabled) {
                // `thinking` not patched away yet: the browser ignores focus().
                this._paintQueue.push(focus);
                return;
            }
            try {
                el.focus({ preventScroll: true });
            } catch (_) {
                el.focus();
            }
        };
        this._afterPaint(focus);
    }

    async _initSessions() {
        await this._refreshSessions();
        if (this.state.currentSessionId) {
            await this._loadSession(this.state.currentSessionId);
        } else {
            await this._createNewSession(false);
        }

        // Catch-up: async turns that finished while we were not looking (e.g.
        // after an F5 or a restart). The DB is the source of truth; if there are
        // unseen done/error jobs, we reload the active session to show them.
        // Timeout: a stuck poll/reclaim must not block opening.
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
                // Turn IN PROGRESS in this session: the worker is still running on the server.
                // We show "thinking…" and refresh when it ends (the page only
                // re-attaches, it runs nothing).
                const _run = (_poll.running || []).find(
                    (j) => j.session_id === this.state.currentSessionId);
                if (_run) {
                    this._resumeRunningTurn(_run.request_id, this.state.currentSessionId);
                }
            }
        } catch (_e) {
            // not critical
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
            // no sessions: a new one will be created
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
        } catch (e) {
            this.notification.add(_t("Could not load the session."), { type: "danger" });
        }
    }

    _resumeRunningTurn(requestId, sessionId) {
        // After an F5 with a turn in progress: the worker is still working on the
        // server. We show "thinking…" and poll gently until it ends,
        // then refresh the session. The async_done bus does the same if it arrives
        // first; both are idempotent. The page only re-attaches.
        this.state.thinking = true;
        this.state.canCancel = true;
        this._resumeReqId = requestId;
        this._lastStreamRequestId = requestId;
        const poll = async () => {
            if (this._resumeReqId !== requestId) {
                return;  // replaced by a new turn or already resolved
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
            // Finished (or reclaimed): refresh and clean up.
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
        // Keep images/files (ir.attachment chips). Without them a client save
        // overwrote the history and the photos "disappeared" in O14/O19.
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
                .filter((f) => f && (f.url || f.name))
                .map((f) => {
                    const url = f.url || "";
                    if (/^(blob:|data:)/i.test(url)) {
                        return Object.assign({}, f, { url: "" });
                    }
                    return f;
                });
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
            if (m.result_note) {
                out.result_note = true;
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
            // best-effort persistence; does not break the chat
        }
    }

    // ──────────────────────────── Screen focus (artifact under the overlay) ──

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
        // Always re-read on send; the snapshot from the last tray open feeds
        // the chip, but the turn uses the current screen.
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
            ? _t("Covered view ON")
            : _t("Covered view OFF");
    }

    get seriesStatsTitle() {
        return this.state.showSeriesStats
            ? _t("Statistics ON")
            : _t("Statistics OFF");
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

    _promptText() {
        const el = this.inputRef && this.inputRef.el;
        if (el && el.value != null) {
            return el.value;
        }
        return this.state.currentInput || "";
    }

    _syncInputEl() {
        const el = this.inputRef && this.inputRef.el;
        if (el) {
            el.value = this.state.currentInput || "";
        }
    }

    _setPrompt(text) {
        const next = text == null ? "" : String(text);
        this.state.currentInput = next;
        this.state.promptNonempty = !!next.trim();
        this._syncInputEl();
    }

    _syncPromptHeight() {
        const el = this.inputRef && this.inputRef.el;
        if (!el) {
            return;
        }
        const text = el.value != null ? el.value : (this.state.currentInput || "");
        const lines = this._promptNewlineCount(text);
        const multiline = lines > 1;
        if (this.state.promptMultiline !== multiline) {
            this.state.promptMultiline = multiline;
        }
        if (!multiline && this.state.promptCollapsed) {
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
        this._setPrompt(next);
        this._updateSlashSuggestions(next);
        this._syncArgPlaceholder(next);
        el.focus();
        try {
            el.setSelectionRange(start + 1, start + 1);
        } catch (eSel) { /* ignore */ }
        this._syncPromptHeight();
    }

    // ──────────────────────────── Send + SSE streaming ────────────────────────────

    async _sendMessage() {
        const text = (this._promptText() || "").trim();
        const images = (this.state.pendingImages || []).slice();
        const imageNames = (this.state.pendingImageNames || []).slice();
        const files = (this.state.pendingFiles || []).slice();
        if ((!text && !images.length && !files.length) || this.state.thinking) {
            return;
        }

        // Built-in commands (/skills, /create-skill): they are resolved
        // in the client, not sent to the LLM as a turn. Only for plain text.
        if (!images.length && !files.length) {
            const builtin = this._matchBuiltinCommand(text);
            if (builtin) {
                if (this._isDeferredSlash(builtin.code)
                    && !this._slashLineReadyToSend(builtin)) {
                    this._holdIncompleteSlash(builtin);
                    return;
                }
                await this._runBuiltinCommand(builtin);
                return;
            }
        }

        this.state.messages.push({
            role: "user",
            content: this._formatContent(text),
            raw: text,
            // Live {url, name} chips (name=null if pasted from the clipboard);
            // after a reload, the worker returns the same {url, name} shape.
            images: images.map((u, i) => ({ url: u, name: imageNames[i] || null })),
            // Local (name) chips of the live turn; after a reload, the worker
            // returns downloadable {name, url}.
            files: files.map((f) => ({
                name: f.name,
                mimetype: f.mimetype,
                url: f.url || null,
                size: f.size,
            })),
            ts: this._now(),
        });
        if (text) {
            this.inputHistory.push(text);
        }
        this.historyIndex = -1;
        this._setPrompt("");
        this.state.promptMultiline = false;
        this.state.promptCollapsed = false;
        this.state.pendingImages = [];
        this.state.pendingImageNames = [];
        this.state.pendingFiles = [];
        this.state.slashOpen = false;
        this.state.slashItems = [];
        this._resetInputPlaceholder();
        this._syncPromptHeight();

        // The last message (the user one we just added) is sent as
        // `message`, so it is left out of history to avoid duplicating it. Images
        // and files travel only in this turn (they do not enter the history).
        await this._runAssistantTurn(text, {
            excludeTail: 1,
            images: images.length ? images : null,
            image_names: imageNames.length ? imageNames : null,
            files: files.length ? files : null,
        });

        // The prompt is still disabled until Owl repaints without `thinking`.
        this._focusInput();
    }

    // Cancels the running turn (button in the "Thinking…" bubble).
    // Aborts the local SSE preview and asks the worker to stop the job on the server.
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
        // Cancel the server job (also after F5 / re-attach without SSE).
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

    /**
     * Why the server refused the turn, in words the user can act on.
     * @param {Response} resp
     * @returns {Promise<string>}
     */
    async _streamRefusal(resp) {
        return ChatbooTurn.refusal(resp, _t("Your session has changed. Reload the page (F5)."));
    }

    async _runAssistantTurn(messageText, opts) {
        // Runs an AI turn and adds its answer. It adds NO user bubble:
        // it serves both typed messages and the result of a confirmed/cancelled
        // write (option B: the AI reports the result).
        opts = opts || {};
        if (this.state.thinking) {
            return;
        }
        // Local owner of the spinner: the bus (async_done of the previous turn, etc.)
        // must NOT turn off thinking while this SSE runs. See _onBusNotification.
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
            // Idle watchdog + manual cancel: if the provider stays silent for
            // STREAM_IDLE_MS (or a restart leaves the socket hanging), we abort the
            // fetch so the turn does not stay on "Thinking…" forever. The cancel
            // button uses the same AbortController (reason 'user').
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
                const payload = ChatbooTurn.buildPayload({
                    sessionId: this.state.currentSessionId,
                    message: messageText,
                    history: history,
                    providerId: this.state.selectedProviderId,
                    screenContext: this._captureScreenContextForSend(),
                    images: opts.images,
                    imageNames: opts.image_names,
                    files: opts.files,
                    resultNote: !!opts.resultNote,
                });
                const resp = await fetch(ChatbooTurn.streamUrl(odoo.csrf_token), {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    signal: controller.signal,
                    body: JSON.stringify(payload),
                });
                if (!resp.ok || !resp.body) {
                    throw new Error(await this._streamRefusal(resp));
                }
                armIdle();
                await ChatbooTurn.readEvents(resp, (evt) => {
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
                        // Auto-promotion: the worker tells us which job/session is
                        // running this turn. We keep the request_id to later
                        // ignore the bus notice for THIS turn (we already see it live).
                        this._lastStreamRequestId = evt.request_id || null;
                        this._lastStreamSessionId = evt.session_id || this._lastStreamSessionId;
                        if (evt.session_id && !this.state.currentSessionId) {
                            this.state.currentSessionId = evt.session_id;
                        }
                    } else if (evt.event === "done") {
                        lastMeta = evt;
                        if (evt.compose === "compose-model"
                                || evt.compose === "compose-agent") {
                            this.state.effectiveFormattingMode = evt.compose;
                        }
                    } else if (evt.event === "choice" && evt.choice_id) {
                        this._showChoiceList(evt);
                    } else if (evt.event === "verification" && evt.verification_id) {
                        // Box B: the AI proposed a write -> inline confirmation.
                        this._showVerificationUI(evt);
                    }
                }, armIdle);
            } catch (e) {
                if (e && (e.name === 'AbortError' || this._streamAbortReason)) {
                    // Clean abort (manual cancel or watchdog): plain notice, not a
                    // red error, keeping what was already received.
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
            if (lastMeta && lastMeta.local_ack) {
                this._markLastUserOfftopic();
            }
            // Patch the user turn's attachments: the worker already saved the
            // images (URL /web/image) and files (URL /web/content). We replace
            // the base64 (images) and url-less chips (files) of the bubble just
            // sent so they open/download in a tab WITHOUT reloading the session.
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

            // This turn was seen live in this tab: we remember its request_id
            // so the bus notice (async_done) does NOT reload the session on top and
            // wipe what you just saw.
            this._lastLiveRequestId = this._lastStreamRequestId || null;

            window.dispatchEvent(new CustomEvent("chatboo-auth-cue", {
                detail: { notify: false, fallbackUnread: true },
            }));

            // Auto-promotion: if the worker already saved the turn (authored), we do
            // NOT save it again from the client (avoids a double save and the race
            // with the worker). We reload the session to pick up the worker's attachments
            // (user images, API downloads in the assistant bubble, etc.).
            const _authored = !!(lastMeta && lastMeta.authored);
            const kept = (this.state.messages || []).slice();
            if (_authored) {
                const sid = lastMeta.session_id || this._lastStreamSessionId || this.state.currentSessionId;
                if (sid) {
                    await this._loadSession(sid);
                }
                if (kept.length && (this.state.messages || []).length < kept.length) {
                    // Keep the live turn. Do not persist it: that wrote
                    // url-less chips over the row the worker just saved.
                    this.state.messages = kept;
                }
            }
            this._maybeSpeakLastAssistant();
            await this._refreshSessions();
        } finally {
            this._sseOwnsThinking = false;
            this.state.thinking = false;
            this.state.canCancel = false;
        }
    }

    _buildVerificationResultNote(evt, res, action) {
        // Text (user turn, not visible) the AI receives so it reports the
        // result — only for fetch_url (needs_llm_followup). CRUD writes use
        // the local user_ack_message (no LLM).
        const guard = " IMPORTANT: this is only a result notice, NOT a request. " +
            "Call no tool and do not propose or create any new operation " +
            "(ignore any example in the prompt); just write the message to the user.";
        const title = (evt && evt.title) || _t("the operation");
        if (action === "cancel") {
            return "[System result] The user CANCELLED the write operation «" + title +
                "». No change was made. Confirm it briefly and naturally in their language." + guard;
        }
        const ok = res && res.success !== false;
        if (ok) {
            let det = "";
            try { det = res && res.results ? JSON.stringify(res.results) : ""; } catch (e) { det = ""; }
            return "[System result] The user CONFIRMED the operation «" + title +
                "» and it ran SUCCESSFULLY." + (det ? (" Result: " + det + ".") : "") +
                " Tell the user it worked, briefly and naturally in their language, naming what was created or changed." + guard;
        }
        return "[System result] The user CONFIRMED the operation «" + title +
            "» but it FAILED to run. Error: " + ((res && res.error) || _t("unknown")) +
            ". Apologise briefly and explain the problem in their language." + guard;
    }

    /**
     * Local ack (no LLM) after Confirm/Cancel of Safe Plan writes.
     * fetch_url / mcp do not use this: the server sends no user_ack_message.
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
            this._runAssistantTurn(note, { resultNote: true });
        } else if (!ack && action !== "cancel") {
            // Legacy fallback: no server hints, ask the LLM (better than silence).
            this._runAssistantTurn(
                (res && res.followup_message)
                || this._buildVerificationResultNote(evt, res || { success: false }, action),
                { resultNote: true }
            );
        }
    }

    _formatStreamFooter(text) {
        const trimmed = (text || "").trim();
        if (!trimmed) {
            return "";
        }
        // Same pipeline as owl1 (ChatbooMarkdown + unwrap of fences / dumps).
        return sharedFormatMarkdown(trimmed) || "";
    }

    _callJsonRoute(route, params) {
        // Calls an Odoo type='json' route (JSON-RPC wrapper). Returns result.
        return fetch(route, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            credentials: "same-origin",
            body: JSON.stringify({ jsonrpc: "2.0", method: "call", params: params || {} }),
        }).then(function (r) { return r.json(); }).then(function (d) { return d.result; });
    }

    _restorePendingVerifications() {
        // Same SoT as Security → Authorizations: live pending rows, not SSE memory.
        // One at a time: two answers in flight would each sign the same card.
        if (this._restoringCards) {
            return this._restoringCards;
        }
        const self = this;
        this._restoringCards = this._callJsonRoute("/pns_ai_mcp/verification/pending", {
            held: this._heldCardIds(),
        })
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
            })
            .then(function () {
                self._restoringCards = null;
            });
        return this._restoringCards;
    }

    _heldCardIds(except) {
        // Cards this screen paints with their token: the server leaves it alone.
        const ids = [];
        document.querySelectorAll('[id^="pns_verif_"]').forEach(function (el) {
            const id = el.id.slice("pns_verif_".length);
            if (id && id !== except && el.dataset.confirmToken) {
                ids.push(id);
            }
        });
        return ids;
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

    _dropSafePlanCard(verificationId, status) {
        if (!verificationId || status === "pending") {
            return;
        }
        const card = document.getElementById("pns_verif_" + verificationId);
        if (card) {
            card.remove();
        }
    }

    _onSafePlanBus(raw) {
        let payload = raw;
        if (raw && raw.payload !== undefined && raw.verification_id === undefined) {
            payload = raw.payload;
        }
        payload = _busNotificationPayload(payload) || payload;
        if (!payload || payload.type !== "pns_safe_plan") {
            return;
        }
        this._dropSafePlanCard(payload.verification_id, payload.status);
    }

    _retryRefusedCard(evt, card, res, status, enable, again) {
        // The card was refused, not the operation: nothing ran, so the AI is
        // not told (it would propose the write again). The person already
        // pressed Confirm: the card takes a fresh token and confirms once more.
        const err = res && res.error;
        if (err !== "too_soon" && err !== "bad_token" && err !== "missing_token") {
            return false;
        }
        const giveUp = function () {
            status.style.color = "#c62828";
            status.textContent = _t("Could not confirm the operation. Press Confirm again.");
            enable();
        };
        if (!again) {
            giveUp();
            return true;
        }
        // A fresh token restarts the wait the server asks of a high-risk card.
        const wait = evt.danger_level === "high" ? 5500 : 0;
        status.style.color = "#555";
        status.textContent = _t("Confirming…");
        if (err === "too_soon") {
            setTimeout(again, wait || 1000);
            return true;
        }
        const self = this;
        this._callJsonRoute("/pns_ai_mcp/verification/pending", {
            held: this._heldCardIds(evt.verification_id),
        })
            .then(function (fresh) {
                const items = (fresh && fresh.items) || [];
                items.forEach(function (item) {
                    if (item && item.verification_id) {
                        self._showVerificationUI(item);
                    }
                });
                const still = items.some(function (item) {
                    return item && item.verification_id === evt.verification_id;
                });
                if (!still) {
                    status.textContent = _t("This operation is no longer pending.");
                    setTimeout(function () { card.remove(); }, 2500);
                    return;
                }
                setTimeout(again, wait);
            })
            .catch(giveUp);
        return true;
    }

    _showVerificationUI(evt) {
        // Box B: write confirmation panel (plain DOM, does not depend on the bus).
        // Safe: the button calls the auth='user' endpoint; the AI does not have the session.
        const self = this;
        const existing = document.getElementById("pns_verif_" + evt.verification_id);
        if (existing) {
            if (evt.confirm_token) {
                existing.dataset.confirmToken = evt.confirm_token;
            }
            return;
        }

        const card = document.createElement("div");
        card.id = "pns_verif_" + evt.verification_id;
        if (evt.confirm_token) {
            card.dataset.confirmToken = evt.confirm_token;
        }
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
        confirmBtn.style.cssText = "background:#2e7d32;color:#fff;border:none;border-radius:5px;padding:6px 14px;cursor:pointer;font-weight:600;";
        const cancelBtn = document.createElement("button");
        cancelBtn.textContent = _t("Cancel");
        cancelBtn.style.cssText = "background:#eee;color:#333;border:none;border-radius:5px;padding:6px 14px;cursor:pointer;";

        const COOLDOWN_SECS = (evt.danger_level === "high") ? 5 : 0;
        if (COOLDOWN_SECS > 0) {
            confirmBtn.disabled = true;
            confirmBtn.style.opacity = ".5";
            let remaining = COOLDOWN_SECS;
            confirmBtn.textContent = _t("Confirm") + " (" + remaining + "s)";
            const cooldownTimer = setInterval(function () {
                remaining--;
                if (remaining <= 0) {
                    clearInterval(cooldownTimer);
                    confirmBtn.disabled = false;
                    confirmBtn.style.opacity = "1";
                    confirmBtn.textContent = _t("Confirm");
                } else {
                    confirmBtn.textContent = _t("Confirm") + " (" + remaining + "s)";
                }
            }, 1000);
        } else {
            confirmBtn.textContent = _t("Confirm");
        }

        const disable = function () {
            confirmBtn.disabled = true; cancelBtn.disabled = true;
            confirmBtn.style.opacity = ".6"; cancelBtn.style.opacity = ".6";
        };
        const enable = function () {
            confirmBtn.disabled = false; cancelBtn.disabled = false;
            confirmBtn.style.opacity = "1"; cancelBtn.style.opacity = "1";
        };

        const sendConfirm = function (retried) {
            disable();
            status.style.color = "#555";
            status.textContent = _t("Confirming…");
            self._callJsonRoute("/pns_ai_mcp/verification/confirm", {
                verification_id: evt.verification_id,
                confirm_token: card.dataset.confirmToken || evt.confirm_token || "",
            })
                .then(function (res) {
                    const ok = res && res.success !== false;
                    if (!ok && self._retryRefusedCard(
                        evt, card, res, status, enable,
                        retried ? null : function () { sendConfirm(true); })) {
                        return;
                    }
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
                        {
                            verification_id: evt.verification_id,
                            confirm_token: card.dataset.confirmToken || evt.confirm_token || "",
                        }
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
        };
        confirmBtn.addEventListener("click", function () { sendConfirm(false); });

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
                    // Cancel with no server answer: generic local write ack.
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
        // Assistant: always through the shared formatContent → htmlSrc (ChatbooHtmlRenderer
        // hydrates charts). User: plain text in raw (t-esc template).
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
        const usage = (m.usage && typeof m.usage === "object")
            ? m.usage
            : ((meta && meta.usage) || null);
        const hasUsage = !!(usage && Object.keys(usage).length);
        if (hasUsage) {
            meta = Object.assign({}, meta || {}, { usage });
        }
        const mapped = {
            role: m.role,
            content: null,
            htmlSrc,
            raw,
            offtopic: !!(m.offtopic || (localAck && !verifyAck)),
            result_note: !!m.result_note,
            // Saved images of the turn: ir.attachment URLs (/web/image
            // with token) written by the worker. The DB already has them, so they
            // show directly and survive reloads and session switches.
            images: m.images || [],
            // Files attached to the turn: downloadable {name, url} chips.
            files: m.files || [],
            clip_data: m.clip_data || null,
            ts: m.timestamp || "",
            meta,
            usage: hasUsage ? usage : (m.usage || null),
            user_prompt: m.user_prompt || (meta && meta.user_prompt) || "",
            local_ack: localAck,
            verification_ack: verifyAck,
            contextInfo: (m.role === "assistant" && (!localAck || hasUsage))
                ? this._buildContextInfo(meta)
                : null,
            backend_history: m.backend_history || (meta && meta.history) || null,
        };
        mapped.wideCanvas = this.messageWantsWideCanvas(mapped);
        return mapped;
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
        const mapped = {
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
        mapped.wideCanvas = this.messageWantsWideCanvas(mapped);
        return mapped;
    }

    _isOfftopicMessage(m) {
        return ChatbooTurn.isOfftopic(m);
    }

    _messagesForModel(messages, excludeTail) {
        return ChatbooTurn.modelTurns(messages, excludeTail);
    }

    _clipForLlm(text, limit) {
        return ChatbooTurn.clipForLlm(text, limit);
    }

    _contentForLlm(text) {
        return ChatbooTurn.contentForLlm(text);
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
        return `${formatWallclock(startTime)} (${duration} ${_t("seconds")})`;
    }

    /**
     * Same pipeline as owl1 (`formatters.formatContent`), wrapped in markup
     * for t-out when needed. Prefer htmlSrc + ChatbooHtmlRenderer.
     */
    _formatContent(text) {
        return markup(sharedFormatContent(text || "") || "");
    }

    _now() {
        return formatWallclock(new Date());
    }

    _showContextStats() {
        // Same analysis as owl1: model·provider header, session state
        // (live) and per-interaction detail (history). Each turn uses
        // the prompt saved on the assistant, not the last user in the array.
        const all = this.state.messages || [];
        let rows = [];
        const statsPre = window.ChatbooContextStats;
        all.forEach((m, idx) => {
            if (m.role === "assistant" && m.contextInfo) {
                const ci = m.contextInfo;
                const usage = (m.meta && m.meta.usage) || {};
                const turnTokens = ci.turnTokens || usage.total_tokens || 0;
                const q = (statsPre && statsPre.questionForAssistant)
                    ? statsPre.questionForAssistant(all, idx)
                    : String(m.user_prompt || (m.meta && m.meta.user_prompt) || "").trim();
                rows.push({
                    n: rows.length + 1,
                    q: q,
                    used: ci.usedTokens || 0,
                    limit: ci.limitTokens || 0,
                    usedK: ci.usedK,
                    limitK: ci.limitK,
                    percent: parseFloat(ci.usagePercent) || 0,
                    model: ci.model,
                    provider: ci.provider,
                    turnTokens: turnTokens,
                    turnK: ci.turnTokensK || null,
                    turnLabel: (statsPre && statsPre.formatTokensK)
                        ? statsPre.formatTokensK(turnTokens)
                        : (ci.turnLabel || "-"),
                    turn: ci.turn || "",
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
        const latest = rows[rows.length - 1];
        const modelLabel = (latest.model || latest.provider)
            ? [latest.model, latest.provider].filter(Boolean).join(" · ")
            : _t("Unknown model");

        const sessionTurnTokens = rows.reduce((sum, r) => sum + (r.turnTokens || 0), 0);
        const sessionCostUsd = rows.reduce((sum, r) => sum + (r.costUsd || 0), 0);
        const sessionTurnLabel = (sessionTurnTokens > 0 && stats && stats.formatTokensK)
            ? stats.formatTokensK(sessionTurnTokens)
            : null;
        const limitKInt = latest.limit > 0 ? Math.round(latest.limit / 1024) : 0;
        const sessionCost = this._formatCostLabel(
            sessionCostUsd,
            this._currencyForProvider(latest.provider, latest.displayCurrency),
        );
        const sessionCostLabel = sessionCost.label;

        let html = "";
        // Block 1 — conversation (billing).
        html += '<div style="font-size:13px;font-weight:700;color:#334155;margin-bottom:8px;">'
            + esc(_t("Conversation")) + "</div>";
        html += '<div style="display:flex;gap:12px;margin-bottom:6px;">';
        html += '<div style="flex:1;text-align:center;background:#f6f7f9;border-radius:8px;padding:12px;">'
            + '<div style="font-size:11px;color:#888;">' + esc(_t("TURNS")) + "</div>"
            + '<div style="font-size:22px;font-weight:700;color:#0d6efd;">' + rows.length + "</div>"
            + '<div style="font-size:11px;color:#666;">' + esc(_t("Performed")) + "</div></div>";
        if (sessionTurnLabel) {
            html += '<div style="flex:1;text-align:center;background:#f6f7f9;border-radius:8px;padding:12px;">'
                + '<div style="font-size:11px;color:#888;">' + esc(_t("SESSION")) + "</div>"
                + '<div style="font-size:22px;font-weight:700;color:#334155;">' + esc(sessionTurnLabel) + "</div>"
                + '<div style="font-size:11px;color:#666;">' + esc(_t("tokens billed")) + "</div>"
                + "</div>";
        }
        if (sessionCostLabel) {
            html += '<div style="flex:1;text-align:center;background:#f6f7f9;border-radius:8px;padding:12px;">'
                + '<div style="font-size:11px;color:#888;">' + esc(_t("COST")) + "</div>"
                + '<div style="font-size:22px;font-weight:700;color:#334155;">' + esc(sessionCostLabel) + "</div>"
                + '<div style="font-size:11px;color:#666;">' + esc(_t("this session")) + "</div>"
                + "</div>";
        }
        html += "</div>";
        html += '<div style="font-size:11px;color:#888;margin-bottom:14px;">'
            + esc(_t("Billed tokens sum every internal LLM call in each reply (tools, ReAct, etc.)."))
            + "</div>";

        if (limitKInt > 0) {
            html += '<div style="background:#f0fdf4;border-radius:8px;padding:10px 12px;margin-bottom:10px;font-size:11px;">'
                + '<div style="color:#334155;margin-bottom:4px;">'
                + '<span style="font-size:22px;font-weight:700;color:#15803d;">' + esc(String(limitKInt) + "k") + "</span>"
                + '<span style="margin-left:0.35em;">' + esc(_t("maximum per LLM call")) + "</span>"
                + "</div>"
                + '<div style="color:#888;">'
                + esc(_t("Each reply may use several internal calls. This cap is per call, not the chat stored on disk."))
                + "</div></div>";
        }

        // Per-interaction detail.
        const anyTurn = rows.some((r) => r.turnLabel && r.turnLabel !== "-");
        const anyCost = rows.some((r) => r.costLabel && r.costLabel !== "-");
        const anyTurnId = rows.some((r) => r.turn);
        html += '<div style="font-size:13px;font-weight:700;color:#334155;margin:12px 0 8px;">'
            + esc(_t("Detail per turn")) + "</div>";
        const cellPad = "padding:8px 10px;";
        const numPad = "padding:8px 14px;";
        html += '<table style="width:100%;border-collapse:collapse;font-size:12px;table-layout:fixed;">';
        html += "<colgroup>"
            + '<col style="width:4%;">'
            + (anyTurnId ? '<col style="width:8%;">' : "")
            + '<col style="width:auto;">'
            + '<col style="width:17%;">'
            + (anyTurn ? '<col style="width:14%;">' : "")
            + (anyCost ? '<col style="width:13%;">' : "")
            + "</colgroup>";
        html += '<thead><tr style="text-align:left;color:#666;border-bottom:1px solid #ddd;">'
            + '<th style="' + cellPad + '">#</th>'
            + (anyTurnId ? '<th style="' + cellPad + '">Id</th>' : "")
            + '<th style="' + cellPad + '">' + esc(_t("Question")) + "</th>"
            + '<th style="' + numPad + 'text-align:right;">' + esc(_t("% of model limit")) + "</th>"
            + (anyTurn ? '<th style="' + numPad + 'text-align:right;">' + esc(_t("Billed")) + "</th>" : "")
            + (anyCost ? '<th style="' + numPad + 'text-align:right;">' + esc(_t("Cost")) + "</th>" : "")
            + "</tr></thead><tbody>";
        const numCell = numPad + "text-align:right;white-space:nowrap;font-variant-numeric:tabular-nums;";
        rows.forEach((r) => {
            const turnCell = anyTurn
                ? '<td style="' + numCell + '">' + esc(r.turnLabel || "0") + "</td>"
                : "";
            const costCell = anyCost
                ? '<td style="' + numCell + '">'
                    + esc(r.costLabel && r.costLabel !== "-" ? r.costLabel : "—") + "</td>"
                : "";
            const turnTok = stats && stats.safeTurnToken
                ? stats.safeTurnToken(r.turn)
                : String(r.turn || "").replace(/[^A-Za-z0-9_-]/g, "");
            const limitCell = '<td style="' + numPad + 'text-align:right;">'
                + '<div style="font-weight:600;margin-bottom:4px;">' + r.percent.toFixed(1) + "%</div>"
                + (stats ? stats.rowBarHtml(r.percent) : "")
                + "</td>";
            html += '<tr class="o_ctx_turn_row" data-turn="' + esc(turnTok) + '" data-msg-index="' + r.messageIndex + '" style="border-bottom:1px solid #f1f1f1;cursor:pointer;">'
                + '<td style="' + cellPad + 'font-weight:600;">#' + r.n + "</td>"
                + (anyTurnId ? '<td style="' + cellPad + 'font-family:monospace;">' + esc(r.turn || "—") + "</td>" : "")
                + '<td class="o_ctx_turn_q" style="' + cellPad + 'overflow:hidden;text-overflow:ellipsis;white-space:nowrap;color:#007cba;" title="' + esc(r.q) + '">' + esc(r.q) + "</td>"
                + limitCell
                + turnCell
                + costCell
                + "</tr>";
        });
        html += "</tbody>";
        if (sessionTurnLabel || sessionCostLabel) {
            html += '<tfoot><tr style="border-top:1px solid #ddd;font-weight:700;">'
                + '<td style="' + cellPad + '" colspan="' + (anyTurnId ? 3 : 2) + '">' + esc(_t("Session")) + "</td>"
                + '<td style="' + numPad + '"></td>'
                + (anyTurn ? '<td style="' + numCell + '"><strong>'
                    + esc(sessionTurnLabel || "0") + "</strong></td>" : "")
                + (anyCost ? '<td style="' + numCell + '"><strong>'
                    + esc(sessionCostLabel ? sessionCostLabel : "—") + "</strong></td>" : "")
                + "</tr></tfoot>";
        }
        html += "</table>";

        this._openStatsModal(_t("Conversation analysis: %s").replace("%s", modelLabel), html);
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
        card.style.cssText = "background:#fff;border-radius:10px;max-width:920px;width:94%;max-height:82vh;overflow:auto;padding:18px 20px;box-shadow:0 8px 30px rgba(0,0,0,.25);font-family:system-ui,Segoe UI,sans-serif;color:#222;";
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
                const code = row.getAttribute("data-turn") || "";
                const idx = parseInt(row.getAttribute("data-msg-index"), 10);
                close();
                this._scrollToContextTurn(code, idx);
            });
        });
        document.body.appendChild(overlay);
    }

    _scrollToContextTurn(turn, messageIndex) {
        const root = this.messagesRef && this.messagesRef.el;
        const stats = window.ChatbooContextStats;
        const bubble = stats && stats.findTurnBubble
            ? stats.findTurnBubble(root, turn, messageIndex)
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
            const localAck = !!(msg.local_ack || (msg.meta && msg.meta.local_ack));
            const usage = (msg.meta && msg.meta.usage) || msg.usage;
            const hasUsage = !!(usage && Object.keys(usage).length);
            if (localAck && !hasUsage) {
                return Object.assign({}, msg, { contextInfo: null });
            }
            const meta = hasUsage
                ? Object.assign({}, msg.meta || {}, { usage })
                : msg.meta;
            return Object.assign({}, msg, {
                contextInfo: this._buildContextInfo(meta),
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
        const stats = window.ChatbooContextStats;
        if (stats && stats.formatTokensK) {
            return stats.formatTokensK(n);
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
                // No rate means no made-up conversion: charge in USD and warn.
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
        // Cost chip always: - (unknown), 0.00 € or the reported value.
        // The green chip is SESSION occupancy: a skill without LLM inherits
        // used/limit from the last turn that did fill the buffer.
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
        const stats = window.ChatbooContextStats;
        const bufferLevel = showBuffer && stats && stats.bufferLevelOf
            ? stats.bufferLevelOf(pct)
            : (showBuffer ? (pct > 80 ? "danger" : pct > 60 ? "warn" : "ok") : null);
        let colorHex = "#28a745";
        let icon = "fa-bell-o";
        if (bufferLevel === "danger") {
            colorHex = "#dc3545";
            icon = "fa-exclamation-triangle";
        } else if (bufferLevel === "warn") {
            colorHex = "#ffc107";
            icon = "fa-exclamation-circle";
        }
        // Real speed measured in the client: decode = completion_tokens / (end − 1st token).
        // If timing or usage is missing, it stays null (not painted).
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
        // No client timing (message authored by the worker and reloaded):
        // we use the server-measured speed (speed_tps) so the footer is not lost.
        if (speedTps === null && meta && meta.speed_tps) {
            speedTps = Number(meta.speed_tps).toFixed(1);
        }
        const turnLabel = this._formatTurnTokensLabel(usage);
        const cost = this._formatCostLabel(
            this._spendCost(usage),
            this._currencyForProvider(meta && meta.provider, meta && meta.display_currency),
        );
        const turnTokensTitle = _t("Tokens billed this turn (all LLM rounds)");
        const spendLabel = turnLabel + " · " + cost.label;
        const spendTitle = [turnLabel !== "-" ? turnTokensTitle : "", cost.title].filter(Boolean).join(" · ");
        const turn = ((meta && meta.turn) || "").trim();
        return {
            turn,
            turnTitle: _t(
                "Turn id (MCP log). Click to copy. Use with /create-skill.",
            ),
            showBuffer,
            usedK: showBuffer ? (used / 1024).toFixed(2) : null,
            limitK: showBuffer ? (limit / 1024).toFixed(2) : null,
            usedTokens: used,
            limitTokens: limit,
            usagePercent: showBuffer ? pct.toFixed(1) : "0",
            bufferLevel,
            colorHex,
            icon,
            model: (meta && meta.model) || "",
            provider: (meta && meta.provider) || "",
            speedTps,
            ttftMs,
            bufferTitle: _t("Model window · last call vs limit"),
            turnTokensK: turnTokens > 0 ? (turnTokens / 1024).toFixed(2) : null,
            turnTokens: turnTokens || 0,
            turnLabel,
            costLabel: cost.label,
            costTitle: cost.title,
            spendLabel,
            spendTitle,
            speedTitle: _t("Generation speed (tokens/s)"),
        };
    }

    _scrollSoon() {
        if (this._scrollPending) {
            return;
        }
        this._scrollPending = true;
        this._afterPaint(() => {
            this._scrollPending = false;
            const el = this.messagesRef.el;
            if (el) {
                el.scrollTop = el.scrollHeight;
            }
        });
    }

    // Opens ANY chat content link in a new tab (images and attached
    // files /web/image//web/content, record chips /web#id=..., inline
    // markdown record links and http/https sources). ONE delegated handler
    // in the capture phase: it runs BEFORE the web client SPA routing or the
    // systray popover close, which otherwise "ate" the click, so history
    // attachments "opened nothing". Works in O14–O19 and for injected
    // (markup/t-out) or history content.
    _setupRefLinkHandler() {
        const el = this.messagesRef.el;
        if (!el || this._refLinkHandler) {
            return;
        }
        this._refLinkHandler = (ev) => {
            if (this._openViewer(ev)) {
                return;
            }
            const a = ev.target && ev.target.closest ? ev.target.closest("a[href]") : null;
            if (!a || !el.contains(a)) {
                return;
            }
            const href = a.getAttribute("href") || "";
            if (!/^(https?:|\/web|\/odoo|\/chatboo\/|\/pns_ai_mcp\/session_file\/)/.test(href)) {
                return; // internal UI links (#, javascript:) → leave alone
            }
            ev.preventDefault();
            ev.stopPropagation();
            window.open(href, "_blank", "noopener");
        };
        el.addEventListener("click", this._refLinkHandler, true);
    }

    // A ``kind=form`` card: the form opens in a dialog with the proposed
    // values. Closing it discards; only the person's Save writes.
    _setupFormCardHandler() {
        const el = this.messagesRef.el;
        if (!el || this._formCardHandler) {
            return;
        }
        this._formCardHandler = (ev) => {
            ev.stopPropagation();
            this._openFormCard(ev.detail || {});
        };
        el.addEventListener("chatboo-open-form", this._formCardHandler);
    }

    async _openFormCard(card) {
        let res = null;
        try {
            res = await this._callJsonRoute("/chatboo/open-form", card);
        } catch (e) {
            res = null;
        }
        if (!res || res.status !== "ok" || !res.action) {
            this.notification.add(
                (res && res.message) || _t("Could not open the form."),
                { type: "danger" }
            );
            return;
        }
        if (res.dropped && res.dropped.length) {
            this.notification.add(
                _t("Left empty: %s").replace("%s", res.dropped.join(", ")),
                { type: "warning" }
            );
        }
        const overlay = document.getElementById("o_chatboo_persistent_overlay");
        const prevZ = overlay ? overlay.style.zIndex : "";
        if (overlay) {
            overlay.style.zIndex = "1000";
        }
        const restore = () => this._restoreChatbooOverlayZ(overlay, prevZ);
        try {
            await this.action.doAction(res.action, {
                additionalContext: res.context || {},
                onClose: restore,
            });
        } catch (e) {
            restore();
            throw e;
        }
    }

    // A chat image opens full screen with zoom (pns_base); a PDF
    // (card or link) opens in the Chatboo viewer. Ctrl/Shift/middle
    // button still open the tab.
    _openViewer(ev) {
        if (ev.ctrlKey || ev.metaKey || ev.shiftKey || ev.button) {
            return false;
        }
        if (!ev.target.closest || !ev.target.closest(".o_chatboo_messages")) {
            return false;
        }
        let viewer = window.pnsImageViewer;
        let shot = viewer && viewer.optionsFor(ev.target);
        if (!shot) {
            viewer = window.chatbooPdfViewer;
            shot = viewer && viewer.optionsFor(ev.target);
        }
        if (!shot) {
            return false;
        }
        ev.preventDefault();
        ev.stopPropagation();
        viewer.open(shot);
        return true;
    }

    _flushStreamPreview(streamState) {
        const acc = streamState.acc;
        // Same as owl1: always formatContent → htmlSrc (hydrates charts).
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
            if (!payload) {
                continue;
            }
            if (payload.type === "pns_safe_plan") {
                this._dropSafePlanCard(payload.verification_id, payload.status);
                continue;
            }
            if (payload.type !== "pns_chatboo_sync") {
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
                // The turn this tab sees live already controls the indicator via
                // SSE. The bus 'thinking' notice may arrive late (different channel) and
                // bring back a "Thinking…" that nobody clears. We ignore it if it is from
                // our own turn — or if a local SSE already owns the spinner.
                const _rid = payload.request_id || null;
                if (this._sseOwnsThinking) {
                    return;
                }
                if (_rid && (_rid === this._lastStreamRequestId || _rid === this._lastLiveRequestId)) {
                    return;
                }
                this.state.thinking = true;
                // Bus-only thinking (another tab / re-attach): allow Cancel
                // against the server job.
                if (_rid) {
                    this._resumeReqId = _rid;
                    this._lastStreamRequestId = _rid;
                    this.state.canCancel = true;
                }
            } else if (action === "message_received") {
                // Never turn off the spinner of a running SSE turn (e.g. when
                // continuing the conversation a sync of the previous turn arrives).
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
                    await this._updateSlashSuggestions(this._promptText());
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
                // Local SSE running: only _runAssistantTurn turns the spinner off.
                // An async_done of the PREVIOUS turn (renderedLive) must not kill
                // the "Thinking…" of the new turn when the chat continues.
                if (this._sseOwnsThinking) {
                    if (ownInFlight || renderedLive) {
                        return;
                    }
                    // Another job in another session: do not reload over the current stream.
                    return;
                }
                // Reload from the DB ONLY if this turn was not just seen live in
                // this tab. If you already saw it, we do not overwrite it (avoids
                // wiping the content when switching windows).
                if (!renderedLive) {
                    // End of a turn we did not see live (e.g. resumed after
                    // F5): refresh and remove the "thinking…".
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
                    // Already seen live: do not reload, but clean up in case a late
                    // 'thinking' from this same turn left the bubble hanging.
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

    // A pending document is built and stored only when its card is clicked:
    // painting a message must not write to the server on its own.
    _fulfillChipClick(ev) {
        const el = ev.currentTarget;
        const msgIndex = parseInt(el.getAttribute("data-msg-index"), 10);
        const fileIndex = parseInt(el.getAttribute("data-file-index"), 10);
        const msg = this.state.messages[msgIndex];
        if (!msg || !msg.files || typeof exportUtils.fulfillPendingSessionDocuments !== "function") {
            return;
        }
        const chip = msg.files[fileIndex];
        if (!chip || !chip.pending) {
            return;
        }
        let sourceEl = null;
        const root = this.messagesRef && this.messagesRef.el;
        if (root) {
            const node = root.querySelector('[data-msg-index="' + msgIndex + '"]');
            sourceEl = node && (node.querySelector(".o_chatboo_content") || node);
        }
        exportUtils.fulfillPendingSessionDocuments(msg, sourceEl, this._exportCtx(), chip)
            .then(() => {
                if (!chip.pending && chip.url) {
                    const a = document.createElement("a");
                    a.href = this._fileDownloadHref(chip);
                    const name = this._fileDownloadName(chip);
                    if (name) {
                        a.download = name;
                    }
                    document.body.appendChild(a);
                    a.click();
                    a.remove();
                }
            })
            .catch(() => {});
    }

    _copyToClipboard(ev) {
        exportUtils.copyToClipboard(ev, this._exportCtx());
    }

    _scrollTurnEdge(ev) {
        if (ev) {
            ev.preventDefault();
            ev.stopPropagation();
        }
        const btn = ev && (ev.currentTarget || ev.target);
        const bubble = btn && btn.closest ? btn.closest(".o_chatboo_message") : null;
        const container = this.messagesRef && this.messagesRef.el;
        if (!bubble || !container) {
            return;
        }
        const edge = btn.getAttribute("data-edge") || "start";
        const cRect = container.getBoundingClientRect();
        const tRect = bubble.getBoundingClientRect();
        const delta = edge === "end" ? tRect.bottom - cRect.bottom : tRect.top - cRect.top;
        if (typeof container.scrollBy === "function") {
            container.scrollBy({top: delta, behavior: "smooth"});
        } else {
            container.scrollTop += delta;
        }
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

    async _copyTurn(ev, code) {
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

    _skillOriginRank(s) {
        if (s && s.mine) {
            return 0;
        }
        if (s && s.is_system) {
            return 3;
        }
        if (s && s.factory) {
            return 2;
        }
        return 1;
    }

    // Skill items: mine, extras, injected, native; A–Z inside each group.
    // Built-in commands do not go through here: they keep their usability order.
    _skillItems(skills) {
        const sorted = (skills || []).slice().sort((a, b) => {
            const ra = this._skillOriginRank(a);
            const rb = this._skillOriginRank(b);
            if (ra !== rb) {
                return ra - rb;
            }
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
                factory: !!(s.factory || s.is_system),
                badgeLabel,
            };
        });
    }

    // Dynamic placeholder: argument hint (arg_hint) of the skill whose
    // "/<code>" is being typed/picked; otherwise the generic text.
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
        if (this.state.inputPlaceholder !== DEFAULT_INPUT_PLACEHOLDER) {
            this.state.inputPlaceholder = DEFAULT_INPUT_PLACEHOLDER;
        }
    }

    // Built-in commands + skills filtered by fragment (autocomplete while typing).
    // Prefix search includes /mode children so /compose-… still works from root.
    _filterSlashItems(skills, q) {
        const all = [...this._skillItems(skills), ...this._allBuiltinCommands()];
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
        this.state.slashMode = mode === "rename"
            ? "rename"
            : (mode === "edit" ? "edit" : "delete");
        this.state.slashItems = items.slice(0, 50);
        this.state.slashIndex = 0;
        this.state.slashOpen = items.length > 0;
        if (!items.length && !q) {
            const emptyMsg = mode === "rename"
                ? _t("You have no skills to rename.")
                : (mode === "edit"
                    ? _t("You have no skills to edit.")
                    : _t("You have no skills to delete."));
            this.notification.add(emptyMsg, { type: "warning" });
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
        const editPick = /^\/edit-skill(?:\s+(\S*))?\s*$/i.exec(text || "");
        if (editPick && (text || "").includes(" ")) {
            await this._ensureSkills();
            if (this.canWriteSkills) {
                await this._fillOwnedSkillPicker(editPick[1] || "", "edit");
                return;
            }
        }
        const m = /^\/(\S*)$/.exec(text || "");
        if (!m) {
            if (this.state.slashOpen || (this.state.slashItems && this.state.slashItems.length)) {
                this.state.slashOpen = false;
                this.state.slashItems = [];
                this.state.slashMode = "commands";
            }
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
            // Bare "/": commands menu; skills after /skills; modes after /mode.
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

    /**
     * Fill the prompt with a slash line and wait. Selection never runs the
     * command: Enter (or typing args, then Enter) does.
     */
    _stageSlashInput(text, placeholder) {
        let line = String(text || "");
        if (line && !line.endsWith(" ")) {
            line += " ";
        }
        this.state.slashOpen = false;
        this.state.slashItems = [];
        this.state.slashMode = "commands";
        this._setPrompt(line);
        this.state.inputPlaceholder = placeholder || DEFAULT_INPUT_PLACEHOLDER;
        if (this.inputRef.el) {
            this.inputRef.el.focus();
        }
    }

    _argPlaceholder(item) {
        if (!item) {
            return DEFAULT_INPUT_PLACEHOLDER;
        }
        if (item.placeholder) {
            return item.placeholder;
        }
        if (item.argHint) {
            return _t("Arguments, e.g.: %s", item.argHint);
        }
        return DEFAULT_INPUT_PLACEHOLDER;
    }

    /** True when the typed line already has what the command needs to run. */
    _slashLineReadyToSend(builtin) {
        if (!builtin) {
            return false;
        }
        if (builtin.help || this._isHelpArg(builtin.arg)) {
            return true;
        }
        if (builtin.code === "create-skill") {
            return Boolean(builtin.skillCode && builtin.turnId);
        }
        if (builtin.code === "delete-skill") {
            return Boolean(builtin.arg);
        }
        if (builtin.code === "rename-skill") {
            return Boolean(builtin.arg && builtin.arg2);
        }
        if (builtin.code === "edit-skill") {
            return Boolean(builtin.arg);
        }
        return false;
    }

    _isDeferredSlash(code) {
        return (
            code === "create-skill"
            || code === "delete-skill"
            || code === "rename-skill"
            || code === "edit-skill"
        );
    }

    _holdIncompleteSlash(builtin) {
        const code = builtin && builtin.code;
        if (code === "create-skill") {
            this._beginCreateSkillInput(builtin.skillCode, builtin.paramProse);
            return;
        }
        if (code === "delete-skill") {
            this._stageSlashInput(
                builtin.arg ? "/delete-skill " + builtin.arg : "/delete-skill",
                _t("Skill to delete, e.g.: %s", "slash-name"),
            );
            if (!builtin.arg) {
                this._fillOwnedSkillPicker("");
            }
            return;
        }
        if (code === "rename-skill") {
            const line = builtin.arg
                ? "/rename-skill " + builtin.arg
                : "/rename-skill";
            this._stageSlashInput(
                line,
                builtin.arg
                    ? _t("New slash name, then press Enter")
                    : _t("Skill to rename, e.g.: %s", "old-name new-name"),
            );
            if (!builtin.arg) {
                this._fillOwnedSkillPicker("", "rename");
            }
            return;
        }
        if (code === "edit-skill") {
            this._stageSlashInput(
                builtin.arg ? "/edit-skill " + builtin.arg : "/edit-skill",
                _t("Skill to edit, e.g.: %s", "slash-or-name"),
            );
            if (!builtin.arg) {
                this._fillOwnedSkillPicker("", "edit");
            }
        }
    }

    _applySlashSelection(item) {
        if (!item) {
            return;
        }
        if (this.state.slashMode === "delete" && item.kind === "skill") {
            this._stageSlashInput(
                "/delete-skill " + item.code,
                _t("Press Enter to delete /%s", item.code),
            );
            return;
        }
        if (this.state.slashMode === "rename" && item.kind === "skill") {
            this._stageSlashInput(
                "/rename-skill " + item.code,
                _t("New slash name, then press Enter"),
            );
            return;
        }
        if (this.state.slashMode === "edit" && item.kind === "skill") {
            this._stageSlashInput(
                "/edit-skill " + item.code,
                _t("Press Enter to edit /%s", item.code),
            );
            return;
        }
        if (item.kind === "builtin") {
            if (item.code === "skills") {
                this._openSkillsMenu();
                return;
            }
            if (item.code === "mode") {
                this._openModeMenu();
                return;
            }
            if (item.code === "create-skill") {
                this._beginCreateSkillInput();
                return;
            }
            if (item.code === "delete-skill") {
                this._stageSlashInput(
                    "/delete-skill",
                    _t("Skill to delete, e.g.: %s", item.argHint),
                );
                this._fillOwnedSkillPicker("");
                return;
            }
            if (item.code === "rename-skill") {
                this._stageSlashInput(
                    "/rename-skill",
                    _t("Skill to rename, e.g.: %s", item.argHint),
                );
                this._fillOwnedSkillPicker("", "rename");
                return;
            }
            if (item.code === "edit-skill") {
                this._stageSlashInput(
                    "/edit-skill",
                    _t("Skill to edit, e.g.: %s", item.argHint),
                );
                this._fillOwnedSkillPicker("", "edit");
                return;
            }
            this._stageSlashInput("/" + item.code, this._argPlaceholder(item));
            return;
        }
        this._stageSlashInput("/" + item.code, this._argPlaceholder(item));
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
            params.forEach((row) => {
                const bits = [];
                if (row.desc) {
                    bits.push(row.desc);
                }
                if (row.default) {
                    bits.push(`${_t("Default")}: ${row.default}`);
                }
                const tail = bits.length ? ` — ${bits.join(". ")}` : "";
                md += `- \`${row.name}\` (${row.type || "string"})${tail}\n`;
            });
            md += "\n";
        } else {
            md += `${_t("No formal parameters.")}\n\n`;
        }
        const examples = [];
        const seen = {};
        const addEx = (token) => {
            const t = String(token || "").trim();
            const line = t ? `/${code} ${t}` : `/${code}`;
            if (seen[line]) {
                return;
            }
            seen[line] = true;
            examples.push(line);
        };
        if (policy === "default") {
            addEx("");
        }
        String(hint || "").split("|").forEach((part) => addEx(part));
        if (examples.length) {
            md += `**${_t("Examples")}:**\n\n`;
            examples.forEach((ex) => {
                md += `- \`${ex}\`\n`;
            });
            md += "\n";
        }
        if (params.length) {
            md += `${_t("Other wording is mapped onto these parameters.")}\n\n`;
        }
        md += `${policyLine}\n`;
        return md;
    }

    _showBuiltinHelp(code) {
        const item = (this.builtinCommands || []).find((c) => c.code === code) || {
            code, name: code, argsPolicy: "none",
        };
        const md = this._slashHelpMarkdown(item);
        this._setPrompt("");
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

    // Returns { code, arg, arg2 } if the text is a known built-in command.
    _matchBuiltinCommand(text) {
        const trimmed = (text || "").trim();
        const helpMatch = /^\/(\S+)\s+(\S+)\s*$/.exec(trimmed);
        if (helpMatch && this._isHelpArg(helpMatch[2])) {
            const code = helpMatch[1].toLowerCase();
            if (/^(compose-agent|compose-model|foot-verbose|foot-laconic|show-table|show-chart)$/.test(code)) {
                return null;
            }
            if (["skills", "skill", "help", "ayuda", "?"].includes(code)) {
                return { code: "skills", arg: helpMatch[2], help: true };
            }
            if ((this.builtinCommands || []).some((c) => c.code === code)) {
                return { code, arg: helpMatch[2], help: true };
            }
        }
        const createMatch = /^\/create-skill(?:\s+([\s\S]+))?$/i.exec(trimmed);
        if (createMatch) {
            const parsed = this._parseCreateSkillLine(createMatch[1] || "");
            return {
                code: "create-skill",
                arg: parsed.skillCode || parsed.turnId || parsed.paramProse || null,
                skillCode: parsed.skillCode,
                turnId: parsed.turnId,
                paramProse: parsed.paramProse,
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
        const editMatch = /^\/edit-skill(?:\s+([\s\S]+))?$/i.exec(trimmed);
        if (editMatch) {
            const parsed = this._parseEditSkillLine(editMatch[1] || "");
            return {
                code: "edit-skill",
                arg: parsed.token || null,
                paramProse: parsed.paramProse,
            };
        }
        const m = /^\/(\S+)\s*$/.exec(trimmed);
        if (!m) {
            return null;
        }
        const code = m[1].toLowerCase();
        // Axis slashes go to the server (one-shot confirm / strip+query).
        if (/^(compose-agent|compose-model|foot-verbose|foot-laconic|show-table|show-chart)$/.test(code)) {
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
        if (
            code === "create-skill"
            || code === "delete-skill"
            || code === "rename-skill"
            || code === "edit-skill"
        ) {
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
            if (!(builtin && builtin.skillCode && builtin.turnId)) {
                this._beginCreateSkillInput(
                    builtin && builtin.skillCode,
                    builtin && builtin.paramProse,
                );
                return;
            }
            this.state.slashOpen = false;
            this.state.slashItems = [];
            await this._runCreateSkillCommand({
                skillCode: builtin.skillCode,
                turnId: builtin.turnId,
                paramProse: builtin.paramProse,
            });
            return;
        }
        if (code === "delete-skill") {
            this._setPrompt("");
            this.state.slashOpen = false;
            this.state.slashItems = [];
            this._resetInputPlaceholder();
            if (!arg) {
                this._setPrompt("/delete-skill ");
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
                this._setPrompt("/rename-skill ");
                this.state.inputPlaceholder = _t("Skill to rename, e.g.: %s", "old-name new-name");
                await this._fillOwnedSkillPicker("", "rename");
                return;
            }
            if (!arg2) {
                this._setPrompt("/rename-skill " + arg + " ");
                this.state.inputPlaceholder = _t("New slash name, then press Enter");
                return;
            }
            this._setPrompt("");
            this._resetInputPlaceholder();
            await this._runRenameSkill(arg, arg2);
            return;
        }
        if (code === "edit-skill") {
            this.state.slashOpen = false;
            this.state.slashItems = [];
            this._setPrompt("");
            this._resetInputPlaceholder();
            await this._runEditSkill(arg, builtin && builtin.paramProse);
            return;
        }
        if (code === "mode") {
            await this._openModeMenu();
            return;
        }
        // /skills opens the floating MENU (no text is ever dumped into the chat).
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

    async _runEditSkill(token, paramProse) {
        if (!this.state.currentSessionId) {
            this.notification.add(_t("Open a chat session first."), { type: "warning" });
            return;
        }
        try {
            const res = await rpc("/chatboo/edit-skill", {
                token: token || "",
                param_prose: paramProse || "",
                session_id: this.state.currentSessionId,
            });
            if (!res || res.status !== "ok") {
                this.notification.add(
                    (res && res.message) || _t("Could not open the skill wizard."),
                    { type: "danger" },
                );
                return;
            }
            if (res.picks) {
                const items = (res.picks || []).map((s) => ({
                    code: s.code, name: s.name, kind: "skill",
                }));
                this._setPrompt("/edit-skill "
                    + (token ? (token + " ") : ""));
                this.state.slashMode = "edit";
                this.state.slashItems = items.slice(0, 50);
                this.state.slashIndex = 0;
                this.state.slashOpen = items.length > 0;
                if (!items.length) {
                    this.notification.add(
                        _t("You have no skills to edit."),
                        { type: "warning" },
                    );
                }
                return;
            }
            if (!res.action) {
                this.notification.add(_t("Could not open the skill wizard."), {
                    type: "danger",
                });
                return;
            }
            this._setPrompt("");
            this._resetInputPlaceholder();
            await this._openSkillWizard(res.action);
        } catch (e) {
            this.notification.add(
                (e && e.message) || _t("Could not open the skill wizard."),
                { type: "danger" },
            );
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

    _looksLikeSkillName(token) {
        return /^[a-z0-9][a-z0-9-]{0,47}$/i.test(token || "");
    }

    _proseWithoutTurnChips(text) {
        return String(text || "")
            .split(/\s+/)
            .filter((part) => (
                part
                && !this._looksLikeTurnId(part)
                && !part.startsWith("/")
            ))
            .join(" ")
            .trim();
    }

    _parseCreateSkillLine(rest) {
        const parts = (rest || "").trim().split(/\s+/).filter(Boolean);
        if (!parts.length) {
            return { skillCode: null, turnId: null, paramProse: "" };
        }
        let i = 0;
        let turnId = null;
        if (this._looksLikeTurnId(parts[0])) {
            turnId = this._normalizeTurnIdToken(parts[0]);
            i = 1;
        }
        let skillCode = null;
        if (
            i < parts.length
            && this._looksLikeSkillName(parts[i])
            && !this._looksLikeTurnId(parts[i])
        ) {
            skillCode = parts[i];
            i += 1;
        }
        return {
            skillCode,
            turnId,
            paramProse: this._proseWithoutTurnChips(parts.slice(i).join(" ")),
        };
    }

    _parseEditSkillLine(rest) {
        const raw = (rest || "").trim();
        if (!raw) {
            return { token: null, paramProse: "" };
        }
        const parts = raw.split(/\s+/);
        return {
            token: parts[0] || null,
            paramProse: parts.slice(1).join(" ").trim(),
        };
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

    _beginCreateSkillInput(name, prose) {
        const raw = String(this._promptText() || "").trim();
        const createMatch = /^\/create-skill(?:\s+([\s\S]*))?$/i.exec(raw);
        const parsed = createMatch
            ? this._parseCreateSkillLine(createMatch[1] || "")
            : { skillCode: null, turnId: null, paramProse: "" };
        const turn = parsed.turnId || this._lastTurnId();
        const slash = this._cleanCreateSkillName(name || parsed.skillCode || "");
        const extra = this._proseWithoutTurnChips(prose || parsed.paramProse || "");
        let line = "/create-skill";
        if (turn) {
            line += " " + turn;
        }
        if (slash) {
            line += " " + slash;
        }
        if (extra) {
            line += " " + extra;
        }
        const item = (this.builtinCommands || []).find((c) => c.code === "create-skill");
        this._stageSlashInput(line, this._argPlaceholder(item));
    }

    _cleanCreateSkillName(name) {
        const token = String(name || "").trim();
        if (!token || token.startsWith("/") || !this._looksLikeSkillName(token)) {
            return "";
        }
        return token;
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

    _messageTurnId(msg) {
        if (!msg) {
            return "";
        }
        return this._normalizeTurnIdToken(
            msg.turn
            || (msg.meta && msg.meta.turn)
            || (msg.context_info && msg.context_info.turn)
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

    _restoreChatbooOverlayZ(overlay, prevZ) {
        if (!overlay) {
            return;
        }
        overlay.style.zIndex = prevZ || "1039";
    }

    async _openSkillWizard(action) {
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
            await this.action.doAction(action, { onClose: restore });
        } catch (e) {
            restore();
            throw e;
        }
    }

    async _runCreateSkillCommand(opts) {
        if (!this.state.currentSessionId) {
            this.notification.add(_t("No active session."), { type: "warning" });
            return;
        }
        const incoming = opts && typeof opts === "object" ? opts : {};
        const skillCode = incoming.skillCode || "";
        const turn = this._normalizeTurnIdToken(incoming.turnId);
        const paramProse = this._proseWithoutTurnChips(incoming.paramProse || "");
        if (!skillCode || !turn) {
            this._beginCreateSkillInput(skillCode, paramProse);
            return;
        }
        try {
            const params = {
                session_id: this.state.currentSessionId,
                skill_code: skillCode
                    ? this._formatInstanceSlash(skillCode)
                    : "",
                turn_id: turn,
                param_prose: paramProse,
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
            this._setPrompt("");
            this._resetInputPlaceholder();
            await this._openSkillWizard(res.action);
        } catch (e) {
            this.notification.add((e && e.message) || _t("Could not open the skill wizard."), {
                type: "danger",
            });
        }
    }

    // Opens the dropdown with every available skill to pick from.
    async _openSkillsMenu() {
        const skills = await this._ensureSkills(true);
        this.state.slashMode = "skills";
        this._setPrompt("/");
        this.state.slashItems = this._skillItems(skills).slice(0, 50);
        this.state.slashIndex = 0;
        this.state.slashOpen = this.state.slashItems.length > 0;
        if (this.inputRef.el) {
            this.inputRef.el.focus();
        }
    }

    // Opens the display modes dropdown (compose / foot / show-*).
    async _openModeMenu() {
        this.state.slashMode = "mode";
        this._setPrompt("/");
        this.state.slashItems = this._modeBuiltinCommands().slice();
        this.state.slashIndex = 0;
        this.state.slashOpen = this.state.slashItems.length > 0;
        this._resetInputPlaceholder();
        if (this.inputRef.el) {
            this.inputRef.el.focus();
        }
    }

    onInput(ev) {
        const val = ev.target.value || "";
        const nonempty = !!val.trim();
        if (this.state.promptNonempty !== nonempty) {
            this.state.promptNonempty = nonempty;
        }
        this._updateSlashSuggestions(val);
        this._syncArgPlaceholder(val);
        this._syncPromptHeight();
    }

    // Paste an image (Ctrl+V) → it is attached to the turn and goes to the
    // vision model like a normal AI chat. If the clipboard has only text, we keep
    // the native paste.
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

    // FA icon class for a file's chip (by mimetype/extension).
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
        if (typeof msg.wideCanvas === "boolean") {
            return msg.wideCanvas;
        }
        const clip = msg.clip_data;
        const flag = !!(clip && (clip.include_chart || clip.include_table
            || (clip.rows && clip.rows.length)));
        if (flag) {
            msg.wideCanvas = true;
            return true;
        }
        const html = String(msg.htmlSrc || msg.raw || "");
        msg.wideCanvas = /data-ai-show-mode="(?:show-table|show-chart|chart-table|dashboard)"/.test(html)
            || html.indexOf("o_ai_table_block") !== -1
            || html.indexOf("o_ai_dashboard") !== -1
            || /<table[\s>]/i.test(html);
        return msg.wideCanvas;
    }

    _fileBannerCardClass(mfile) {
        return "o_chatboo_file_banner_card o_chatboo_file_banner_" + this._fileBannerTone(mfile);
    }

    _fileLinkType(mfile) {
        return this._fileBannerTone(mfile) === "pdf" ? "application/pdf" : false;
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

    // Form URL for a record {model, id}. Classic deep link valid in
    // O14–O19 (the O17+ /odoo/... scheme lives alongside /web#...). Opens in a
    // new tab (the link has target=_blank), respecting Odoo permissions.
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
            // Keep the name if it comes from a file; null if pasted (clipboard).
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

    // ── Clip: attach files (Phase 1: data/text · Phase 2: images) ─────
    // Opens the file picker (hidden input). Raster images go the
    // multimodal way (pendingImages, same as paste); SVG goes as
    // text (it is XML); the rest as a data file.
    onClipClick() {
        if (this.fileInputRef && this.fileInputRef.el) {
            this.fileInputRef.el.click();
        }
    }

    // Image fit for a vision model: any image/* except SVG (it is XML and
    // vision providers rarely accept it → better as text).
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
        // Allow picking the same file again (change does not fire if nothing changes).
        if (ev.target) {
            ev.target.value = "";
        }
        if (this.inputRef.el) {
            this.inputRef.el.focus();
        }
    }

    // Per-file upload limit, the same number the server checks on the turn
    // (Settings > Chatboo > Upload limit; 0 there lifts it, the message cap stays).
    _uploadMaxBytes() {
        const n = Number(session.pns_chatboo_upload_max_bytes);
        return n > 0 ? n : 15 * 1024 * 1024;
    }

    _refuseIfTooBig(file) {
        const limit = this._uploadMaxBytes();
        if (!(file.size > limit)) {
            return false;
        }
        const mb = Math.max(1, Math.round(limit / (1024 * 1024)));
        this.notification.add(
            _t("File too large (max %s MB):", mb) + " " + file.name, { type: "danger" });
        return true;
    }

    // Routes a list of files (from the picker or drag&drop): vision
    // images → multimodal way (keep their name); the rest → data file.
    async _ingestFiles(files) {
        for (const f of Array.from(files || [])) {
            if (this._refuseIfTooBig(f)) {
                continue;
            }
            if (this._isVisionImage(f)) {
                await this._attachImageFile(f);
            } else {
                await this._attachDataFile(f);
            }
        }
    }

    // ── Drag & drop of files on ANY part of the chat ───────────────────
    // We only react to drags that carry files (not internal text
    // selection). The overlay is only visual (pointer-events:none), so the
    // 'drop' always reaches the root.
    _dragHasFiles(ev) {
        const dt = ev && ev.dataTransfer;
        return !!(dt && Array.from(dt.types || []).indexOf("Files") !== -1);
    }

    _onDragOver(ev) {
        if (!this._dragHasFiles(ev)) {
            return;
        }
        ev.preventDefault();  // required to enable the 'drop'
        this.state.dragActive = true;
    }

    _onDragLeave(ev) {
        // Avoids flicker when passing over children: only turn off when leaving the root.
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
        if (this._refuseIfTooBig(file)) {
            return;
        }
        try {
            const dataUrl = await this._readFileAsDataUrl(file);
            const isPdf = (file.type || "").toLowerCase() === "application/pdf"
                || /\.pdf$/i.test(file.name || "");
            this.state.pendingFiles.push({
                name: file.name,
                mimetype: file.type || "",
                size: file.size,
                data: dataUrl,
                url: isPdf ? URL.createObjectURL(file) : null,
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

    // Sets the placeholder from the "/<code>" at the start of the input (with or
    // without arguments). Uses the skills cache (no RPC); no skill → the generic one.
    _syncArgPlaceholder(text) {
        const m = /^\/(\S+)/.exec((text || "").trim());
        if (!m) {
            this._resetInputPlaceholder();
            return;
        }
        const next = this._placeholderForSkillCode(this.skillsCache || [], m[1]);
        if (this.state.inputPlaceholder !== next) {
            this.state.inputPlaceholder = next;
        }
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
        // Skills dropdown navigation (takes priority over the rest).
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
                // Menu Enter selects (fills "/code "). Send only when the
                // line already has the args that command needs.
                if (ev.key === "Enter") {
                    const builtin = this._matchBuiltinCommand(this._promptText());
                    if (this._slashLineReadyToSend(builtin)) {
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
        // Ctrl/Cmd+Enter: new line (never sends). Enter alone: sends.
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
                this._setPrompt(this.inputHistory[this.inputHistory.length - 1] || "");
                this.state.promptCollapsed = false;
                ev.preventDefault();
                this._syncPromptHeight();
            } else if (this.historyIndex < this.inputHistory.length - 1) {
                this.historyIndex += 1;
                this._setPrompt(this.inputHistory[this.inputHistory.length - 1 - this.historyIndex] || "");
                this.state.promptCollapsed = false;
                ev.preventDefault();
                this._syncPromptHeight();
            }
        } else if (ev.key === "ArrowDown" && this.inputHistory.length && this._promptCaretOnLastLine(ev.target)) {
            if (this.historyIndex > 0) {
                this.historyIndex -= 1;
                this._setPrompt(this.inputHistory[this.inputHistory.length - 1 - this.historyIndex] || "");
                this.state.promptCollapsed = false;
                ev.preventDefault();
                this._syncPromptHeight();
            } else if (this.historyIndex === 0) {
                this.historyIndex = -1;
                this._setPrompt("");
                this.state.promptCollapsed = false;
                ev.preventDefault();
                this._syncPromptHeight();
            }
        }
    }
}

export default ChatbooApp;
