odoo.define('pns_ai_chatboo.Chatboo', function (require) {
    "use strict";

    const AbstractAction = require('web.AbstractAction');
    const core = require('web.core');
    const _t = core._t;
    const formatters = require('pns_ai_chatboo.formatters');
    const exportUtils = require('pns_ai_chatboo.export');
    const { Component } = owl;
    const { useState, useRef, onMounted, onWillUnmount } = owl.hooks;
    const { xml } = owl.tags;

    function extractUsageCost(usage) {
        if (!usage || typeof usage !== 'object') {
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
            return isFinite(ticks) ? ticks / 1e10 : undefined;
        }
        return undefined;
    }

    function usageHasTokenKey(usage) {
        if (!usage || typeof usage !== 'object') {
            return false;
        }
        return ['total_tokens', 'prompt_tokens', 'completion_tokens', 'input_tokens', 'output_tokens']
            .some(function (k) { return usage[k] != null; });
    }

    function turnTokensValue(usage) {
        if (!usageHasTokenKey(usage)) {
            return null;
        }
        const total = Number(usage.total_tokens);
        if (isFinite(total)) {
            return total;
        }
        return (Number(usage.prompt_tokens) || 0) + (Number(usage.completion_tokens) || 0);
    }

    function formatTurnTokensLabel(usage) {
        const n = turnTokensValue(usage);
        if (n == null) {
            return '-';
        }
        if (n > 0) {
            return (n / 1024).toFixed(2) + 'k';
        }
        return '0';
    }

    function formatCostLabel(usd, currency, fx) {
        if (usd === undefined || usd === null || usd === '') {
            return { label: '-', title: _t('Cost unknown') };
        }
        const n = Number(usd);
        if (!isFinite(n) || n < 0) {
            return { label: '-', title: _t('Cost unknown') };
        }
        let amount = n;
        let code = 'USD';
        let rate = 1;
        let failed = false;
        const want = (currency || 'USD').toUpperCase();
        if (want !== 'USD') {
            const r = Number(fx && fx.rates ? fx.rates[want] : NaN);
            if (isFinite(r) && r > 0) {
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
                style: 'currency',
                currency: code,
                minimumFractionDigits: zero || amount >= 0.01 ? 2 : 4,
                maximumFractionDigits: zero ? 2 : (amount >= 0.01 ? 4 : 6),
            }).format(amount);
        } catch (e) {
            label = code + ' ' + (zero ? amount.toFixed(2) : amount.toFixed(4));
        }
        const asOf = fx && fx.as_of ? fx.as_of : '';
        let title;
        if (failed) {
            label += ' ⚠';
            const why = (fx && fx.error) || _t('no exchange rate available');
            title = _t('Could not convert to %s: shown in USD').replace('%s', want)
                + ' · ' + why;
        } else if (code === 'USD') {
            title = 'USD' + (asOf ? ' · ' + asOf : '');
        } else {
            title = code + ' · 1 USD = ' + rate + (asOf ? ' · ' + asOf : '');
        }
        return { label, title };
    }

    function contextUsedTokens(usage) {
        if (!usage) {
            return 0;
        }
        return usage.context_tokens || usage.total_tokens || usage.prompt_tokens || 0;
    }

    /** Max visible lines for the multiline prompt (future: Settings). */
    const CHATBOO_PROMPT_MAX_LINES = 10;

    /**
     * ChatbooComponent — OWL 1 chat overlay for the PNS AI suite.
     *
     * This is the main UI component for AI conversations in Odoo. It renders
     * as a persistent overlay (systray singleton) or as an action-mounted panel.
     *
     * ═══════════════════════════════════════════════════════════════════════
     * ARCHITECTURE MAP (for AI readers)
     * ═══════════════════════════════════════════════════════════════════════
     *
     * ZONES (by line range — use these as navigation landmarks):
     *
     *  1. SETUP + LIFECYCLE        (setup, mounted, _initSession)
     *  2. SESSION MANAGEMENT       (_loadSessions, _createNewSession, _selectSession, ...)
     *  3. BUS + NOTIFICATIONS      (_setupBusListener, _processNotifications)
     *  4. NETWORK + HEALTH         (_checkHealth, _testConnection, _callJsonRoute)
     *  5. SAFE PLAN VERIFICATION   (_showVerificationUI, _buildVerificationResultNote)
     *  6. CHAT + STREAMING         (_streamChat, _sendMessage, _runResultTurn)
     *  7. SLASH COMMANDS           (_onSlashInput, _updateSlashSuggestions, _applySlashSelection)
     *  8. INPUT HANDLING           (_onInputKeydown — keyboard shortcuts)
     *  9. CONTENT FORMATTING       (_formatContent, _formatMarkdown, _formatCSV, _formatJsonAsTable)
     * 10. CONTEXT CHART            (_showContextChart — token usage visualization)
     * 11. EXPORT (PDF/Excel/Copy)  (_copyToClipboard, _downloadAsPDF, _downloadAsExcel)
     *
     * STATE:
     *   this.state (reactive via useState):
     *     - currentInput:     text in the chat input
     *     - thinking:         true while waiting for LLM response
     *     - disabled:         true → input blocked (during stream/verification)
     *     - currentSessionId: active session ID (server-side)
     *     - sessions:         array of {id, name, last_used_date, ...}
     *     - slashOpen/slashItems/slashIndex: slash-command menu state
     *
     *   this.messages (reactive array via useState):
     *     [{role: 'user'|'assistant', content: string, context_info?: object, ...}]
     *
     * COMMUNICATION WITH BACKEND:
     *   - JSON-RPC via this.props.rpc() → /chatboo/* routes
     *   - SSE streaming via fetch() → /chatboo/stream
     *   - Odoo Bus (pns_chatboo_sync) for multi-tab sync
     *   - Safe Plan verification via /pns_ai_mcp/verification/* routes
     *
     * PROPS (injected by ChatbooAction):
     *   - rpc:          Odoo JSON-RPC function
     *   - notification: Odoo notification service
     *   - context:      Action context ({new_chat, show_history_modal, ...})
     */
    class ChatbooComponent extends Component {
        // Constante configurable: número de decimales para formateo de números
        static DEFAULT_DECIMAL_PLACES = 3;

        // ══════════════════════════════════════════════════════════════════════
        // 1. SETUP + LIFECYCLE
        // ══════════════════════════════════════════════════════════════════════

        /**
         * OWL setup hook. Initializes reactive state, refs, input history,
         * slash-command definitions, and registers the willUnmount cleanup.
         */
        setup() {
            // Helper method to safely get context info values
            this.getContextValue = (ctx, key, defaultValue = '0.00') => {
                return (ctx && ctx[key]) ? ctx[key] : defaultValue;
            };



            // Fix: Inject device into env if missing (prevents isMobile error in templates)
            if (!this.env.device) {
                try {
                    const config = require('web.config');
                    // OWL 1: env is usually read-only, but for root component with null parent it might be just an object
                    // We try to reuse existing device info
                    this.env.device = config.device;
                } catch (e) {
                    console.warn('Could not load web.config for Chatboo device env:', e);
                    this.env.device = { isMobile: false, size_class: 5, sizing: {} };
                }
            }

            // Add CSS styles for list spacing reduction and table styling (global, applies to all messages)
            const style = document.createElement('style');
            style.textContent = `
                .o_chatboo_content ul { 
                    margin-top: 0.3em !important; 
                    margin-bottom: 0.3em !important; 
                    padding-left: 1.5em !important; 
                }
                .o_chatboo_content li { 
                    margin-top: 0.05em !important; 
                    margin-bottom: 0.05em !important; 
                    line-height: 1.2 !important; 
                    padding-top: 0 !important;
                    padding-bottom: 0 !important;
                }
                .o_chatboo_content ol { 
                    margin-top: 0.3em !important; 
                    margin-bottom: 0.3em !important; 
                    padding-left: 1.5em !important; 
                }
                .o_chatboo_copy_btn:hover {
                    opacity: 1 !important;
                }
                /* Tables: monospace + numeric columns align to inline-end (LTR/RTL) */
                .o_chatboo_content table {
                    font-family: ui-monospace, "Cascadia Code", "Fira Code", Consolas, "Courier New", monospace !important;
                    font-size: 1.05em !important;
                    width: 100% !important;
                    margin: 1em 0 !important;
                    border-collapse: collapse !important;
                }
                .o_chatboo_content table thead {
                    background-color: #f8f9fa !important;
                    font-weight: bold !important;
                }
                .o_chatboo_content table th,
                .o_chatboo_content table td {
                    padding: 0.5em 0.75em !important;
                    border: 1px solid #dee2e6 !important;
                    text-align: start;
                }
                .o_chatboo_content table th.o_chatboo_num,
                .o_chatboo_content table td.o_chatboo_num,
                .o_chatboo_content table th.text-end,
                .o_chatboo_content table td.text-end {
                    text-align: end !important;
                    font-variant-numeric: tabular-nums;
                }
                .o_chatboo_content table tbody tr:nth-child(even):not([style*="background-color"]) {
                    background-color: #f8f9fa;
                }
                .o_chatboo_content table tbody tr:hover:not([style*="background-color"]) {
                    background-color: #e9ecef;
                }
            `;
            document.head.appendChild(style);

            this.state = useState({
                currentInput: "",
                thinking: false,
                disabled: false,
                providerName: "Connecting...",
                providerModel: "",
                providerHost: "",
                statusLabel: "",
                connected: false,
                can_save_for_template: false,
                canCancel: false,
                currentSessionId: null,
                sessions: [],
                showSessionModal: false,
                editingSessionId: null,
                editingSessionName: "",
                selectedSessions: [],
                streamingPreview: "",
                slashOpen: false,
                slashItems: [],
                slashIndex: 0,
                slashMode: 'commands', // 'commands' (menú de /) | 'skills' (tras /skills)
                inputPlaceholder: _t('Ask Chatboo... (/ for commands & skills, ↑↓ for history)'),
                // AI Provider selector
                providers: [],
                selectedProviderId: null,
                providerMenuOpen: false,
                effectiveFormattingMode: null,
                screenFocusLabel: '',
                screenFocusEnabled: true,
                screenContextSnapshot: null,
                pendingImages: [],       // imágenes pegadas (data URLs) a enviar en el turno
                pendingImageNames: [],   // nombres alineados por índice (null si es pegado del portapapeles)
                pendingFiles: [],        // ficheros de texto/datos adjuntos con el clip
                dragActive: false,       // overlay visual mientras se arrastran ficheros sobre el chat
                ttsSupported: false,     // Web Speech API disponible
                ttsEnabled: false,       // lectura en voz alta activada por el usuario
                promptMultiline: false,
                promptCollapsed: false,
            });
            this.messages = useState([]);
            this.messagesRef = useRef("messages");
            this.chatInputRef = useRef("chatInput");
            this.promptMaxLines = CHATBOO_PROMPT_MAX_LINES;

            // Input history (like readline)
            this.inputHistory = [];
            this.historyIndex = -1;
            this.currentInputBeforeHistory = "";
            this.skillsCache = null;
            this._skillsLoaded = false;
            this._fx = null;
            this._cardWidthRatio = 0;
            this._defaultDisplayCurrency = 'USD';
            this._sessionOccupancy = { used: 0, limit: 0 };
            this.dropHint = _t('Drop files to attach here');
            this.tipAttach = _t('Attach file');
            this.tipSend = _t('Send');
            this.tipRemoveImage = _t('Remove image');
            this.tipRemoveFile = _t('Remove file');
            this.tipHistoryNav = _t('Arrow keys ↑↓ to navigate the prompt history');
            this.tipExpandPrompt = _t('Expand prompt');
            this.tipCollapsePrompt = _t('Collapse prompt');
            this.tipTestConnection = _t('Test connection');
            this.tipChangeProvider = _t('Change provider');
            this.tipNewChat = _t('New chat');
            this.tipNew = _t('New');
            this.tipHistory = _t('History');
            this.tipDownloadPdf = _t('Download as PDF');
            this.tipDownloadExcel = _t('Download as Excel');
            this.tipDownloadWord = _t('Download as Word');
            this.tipRestoreCardWidth = _t('Restore default width');
            this.tipDownloadFile = _t('Download');
            this.tipCopyContent = _t('Copy content');
            this.tipCopyMarkdown = _t('Copy as Markdown');
            this.tipCopyClipboard = _t('Copy to clipboard');
            this.tipOpenImage = _t('Open image');
            this.tipCancel = _t('Cancel');
            this.tipSave = _t('Save');
            this.tipRenameSession = _t('Rename session');
            this.tipDeleteSession = _t('Delete session');
            this.tipThinking = _t('Thinking…');
            this.tipConnecting = _t('Connecting…');
            this.tipCurrent = _t('Current');
            this.tipMessages = _t('messages');
            this._slashMenuEl = null;
            this.canWriteSkills = false;
            this.skillCommandPrefix = '';
            this.skillCodePrefix = '';
            // Built-in "/" palette. Axis toggles live under /mode (like skills)
            // under /skills). Typing /painter-… still finds them via prefix filter.
            this.builtinCommands = [
                { code: 'skills', name: 'Skills', description: _t('List the available skills'), kind: 'builtin', argsPolicy: 'none' },
                {
                    code: 'create-skill',
                    name: 'Create skill',
                    description: _t(
                        'Capture a turn as an instance skill (extra, with you as author). '
                        + 'Typing /create-skill fills the last chip (you can change it), then the slash name. '
                        + 'Settings prefixes apply. Help: /create-skill ?'
                    ),
                    argHint: 'VWVN slash-name  |  ? help',
                    params: [
                        {
                            name: 'turn_id',
                            type: 'string',
                            desc: _t('4-character MCP turn id (chip). Required.'),
                            default: _t('last turn'),
                        },
                        {
                            name: 'name',
                            type: 'string',
                            desc: _t('Slash name. Settings prefix is applied.'),
                            default: '',
                        },
                    ],
                    kind: 'builtin',
                    deferArg: true,
                    writerOnly: true,
                    argsPolicy: 'ask',
                },
                {
                    code: 'delete-skill',
                    name: 'Delete skill',
                    description: _t(
                        'Delete a skill you created. Empty opens the picker. Help: /delete-skill ?'
                    ),
                    argHint: 'slash-name  |  ? help',
                    params: [
                        {
                            name: 'name',
                            type: 'string',
                            desc: _t('Slash of a skill you created. Stem or prefixed.'),
                            default: _t('opens picker'),
                        },
                    ],
                    kind: 'builtin',
                    deferArg: true,
                    writerOnly: true,
                    argsPolicy: 'ask',
                },
                {
                    code: 'rename-skill',
                    name: 'Rename skill',
                    description: _t(
                        'Rename a skill you created. Empty opens the picker. Help: /rename-skill ?'
                    ),
                    argHint: 'old-name new-name  |  ? help',
                    params: [
                        {
                            name: 'old',
                            type: 'string',
                            desc: _t('Current slash (stem or prefixed).'),
                            default: '',
                        },
                        {
                            name: 'new',
                            type: 'string',
                            desc: _t('New slash name. Instance prefix is applied.'),
                            default: '',
                        },
                    ],
                    kind: 'builtin',
                    deferArg: true,
                    writerOnly: true,
                    argsPolicy: 'ask',
                },
                {
                    code: 'mode',
                    name: 'Mode',
                    description: _t('Presentation modes (painter, footer, table/chart)'),
                    kind: 'builtin',
                    argsPolicy: 'none',
                },
                {
                    code: 'foot-laconic',
                    name: 'Foot laconic',
                    description: _t('No footer after local tables'),
                    placeholder: _t('Optional question…'),
                    kind: 'builtin',
                    deferArg: true,
                    argsPolicy: 'none',
                    folder: 'mode',
                },
                {
                    code: 'foot-verbose',
                    name: 'Foot verbose',
                    description: _t('Warm footer after local tables'),
                    placeholder: _t('Optional question…'),
                    kind: 'builtin',
                    deferArg: true,
                    argsPolicy: 'none',
                    folder: 'mode',
                },
                {
                    code: 'show-table',
                    name: 'Show table',
                    description: _t('Table first (this session)'),
                    placeholder: _t('Optional question…'),
                    kind: 'builtin',
                    deferArg: true,
                    argsPolicy: 'none',
                    folder: 'mode',
                },
                {
                    code: 'show-chart',
                    name: 'Show chart',
                    description: _t('Chart first (this session)'),
                    placeholder: _t('Optional question…'),
                    kind: 'builtin',
                    deferArg: true,
                    argsPolicy: 'none',
                    folder: 'mode',
                },
                {
                    code: 'painter-free',
                    name: 'Painter free',
                    description: _t('The model owns the whole bubble this turn'),
                    placeholder: _t('Optional question…'),
                    kind: 'builtin',
                    deferArg: true,
                    argsPolicy: 'none',
                    folder: 'mode',
                },
                {
                    code: 'painter-local',
                    name: 'Painter local',
                    description: _t('Chatboo composes tables this turn'),
                    placeholder: _t('Optional question…'),
                    kind: 'builtin',
                    deferArg: true,
                    argsPolicy: 'none',
                    folder: 'mode',
                },
            ];

            onWillUnmount(() => {
                this._removeSlashMenu();
            });
        }

        /**
         * OWL mounted lifecycle hook. Scrolls to bottom and sets up
         * context-click handling. Session init is deferred to _initSession()
         * because OWL 1's mounted() is unreliable with async operations.
         */
        async mounted() {
            this.scrollToBottom();
            this._setupContextClickHandling();
            this._setupRefLinkHandler();
            this._setupTtsClickAnchoring();
            // Session loading (_initSession) is called from ChatbooAction.start()
            // because OWL 1 mounted() is unreliable with async operations
        }

        // Abre en pestaña nueva CUALQUIER enlace de contenido del chat: imágenes y
        // ficheros adjuntos (/web/image, /web/content), chips de registro
        // (/web#id=...), enlaces de registro en línea del markdown y fuentes
        // http(s). Handler ÚNICO delegado en fase de CAPTURA sobre el contenedor
        // de mensajes: corre ANTES que el enrutado del web client, así los
        // adjuntos del histórico (t-raw) SÍ abren pestaña/descargan. En O14 esto
        // arregla que "no abrían nada".
        _setupRefLinkHandler() {
            // Anclamos a la RAÍZ del componente (this.el), no a messagesRef.el:
            // en O14 el ref de mensajes puede no estar aún resuelto en mounted()
            // (owl1 es poco fiable ahí) y el handler no se enganchaba nunca → los
            // adjuntos del histórico "no abrían nada". this.el existe siempre al
            // montar y contiene toda la zona de chat.
            const el = this.el || this.messagesRef.el;
            if (!el || this._refLinkHandler) {
                return;
            }
            this._refLinkEl = el;
            this._refLinkHandler = (ev) => {
                const a = ev.target && ev.target.closest ? ev.target.closest('a[href]') : null;
                if (!a || !el.contains(a)) {
                    return;
                }
                const href = a.getAttribute('href') || '';
                if (!/^(https?:|\/web|\/odoo)/.test(href)) {
                    return;
                }
                ev.preventDefault();
                ev.stopPropagation();
                window.open(href, '_blank', 'noopener');
            };
            el.addEventListener('click', this._refLinkHandler, true);
        }

        /**
         * Initialize the chat session on mount.
         *
         * Phases:
         *   0. If context.new_chat → create fresh session (skip loading previous)
         *   1-3. Otherwise → load session list, find active session, load its messages
         *   4. Fallback: restore from sessionStorage (floating chat transfer)
         *   5. Start Odoo Bus listener for multi-tab sync
         *   6. Open history modal if action context requests it
         *   7. Run health check
         */
        async _initSession() {
            let sessionLoaded = false;
            try {
                // FASE 0: Si el contexto pide una sesión nueva, crearla directamente
                // y evitar cargar la sesión previa (esto elimina la condición de carrera
                // que tenía ChatbooNewAction al llamar _createNewSession por fuera).
                if (this.props.context && this.props.context.new_chat) {
                    this.messages.splice(0, this.messages.length);
                    this.inputHistory = [];
                    this.historyIndex = -1;
                    this.currentInputBeforeHistory = '';
                    // Crear la sesión en backend y establecerla como activa
                    try {
                        const newResult = await this.props.rpc({
                            route: '/chatboo/sessions/create',
                            params: {}
                        });
                        if (newResult && newResult.status === 'ok' && newResult.session) {
                            this.state.currentSessionId = newResult.session.id;
                            sessionLoaded = true;
                        }
                    } catch (e) {
                        console.error('Error creating new session in _initSession:', e);
                    }
                    // Actualizar lista de sesiones sin cargar mensajes de la nueva (está vacía)
                    try {
                        const listResult = await this.props.rpc({ route: '/chatboo/sessions/list', params: {} });
                        if (listResult && listResult.status === 'ok') {
                            this.state.sessions = (listResult.sessions || []).map(session => {
                                if (session.last_used_date) {
                                    try { session.formatted_date = new Date(session.last_used_date).toLocaleDateString(formatters.getSessionLocale()); } catch (e) { session.formatted_date = session.last_used_date; }
                                }
                                return session;
                            });
                        }
                    } catch (e) { /* non-fatal */ }
                } else {
                    // FASE 1-3: Comportamiento normal — cargar sesión activa
                    const listResult = await this.props.rpc({ route: '/chatboo/sessions/list', params: {} });

                    if (listResult && listResult.status === 'ok') {
                        this.state.sessions = (listResult.sessions || []).map(session => {
                            if (session.last_used_date) {
                                try { session.formatted_date = new Date(session.last_used_date).toLocaleDateString(formatters.getSessionLocale()); } catch (e) { session.formatted_date = session.last_used_date; }
                            }
                            return session;
                        });

                        const targetId = listResult.active_session_id
                            || (listResult.sessions && listResult.sessions.length > 0 ? listResult.sessions[0].id : null);

                        if (targetId) {
                            // Un único cargador para todas las rutas (arranque,
                            // histórico, reanudación): una copia a mano de esto
                            // se dejó atrás la rehidratación de los chips y el
                            // histórico aparecía sin tokens ni coste.
                            sessionLoaded = await this._loadSession(targetId);
                        }
                    }
                }
            } catch (e) {
                console.error('Error in session init:', e);
            }

            // --- FASE 4: Restaurar Historial desde el Chat Flotante ---
            if (!sessionLoaded) {
                try {
                    const storedHistory = window.sessionStorage.getItem('chatboo_floating_transfer_history');
                    if (storedHistory) {
                        const parsedHistory = JSON.parse(storedHistory);
                        if (parsedHistory && parsedHistory.length > 0) {
                            this.messages.splice(0, this.messages.length);
                            parsedHistory.forEach(msg => {
                                this.messages.push({ role: msg.role, content: msg.content, timestamp: formatters.formatWallclock(new Date()) });
                            });
                            this.scrollToBottom();
                        }
                    }
                } catch (err) {
                    console.error('Chatboo Floating Transfer Error:', err);
                }
            }
            try { window.sessionStorage.removeItem('chatboo_floating_transfer_history'); } catch (_) { }

            // --- FASE 5: Multi-Tab Synchronization (Odoo Bus) ---
            this._setupBusListener();

            // --- FASE 6: Open history modal if requested by action context ---
            if (this.props.context && this.props.context.show_history_modal) {
                await this._showSessions();
            }

            // After session is loaded, check health
            this._checkHealth();

            // Catch-up: turnos asíncronos que terminaron mientras no mirábamos
            // (p.ej. tras un F5). La fuente de verdad es la BD; recargamos.
            // Timeout: un poll/reclaim colgado NUNCA debe dejar el init a medias
            // ni el spinner de Odoo (aunque ya usamos shadow:true).
            try {
                const _poll = await Promise.race([
                    this.props.rpc({ route: '/chatboo/async/poll', params: {} }),
                    new Promise((resolve) => setTimeout(
                        () => resolve({ status: 'timeout', pending: [], running: [] }),
                        5000,
                    )),
                ]);
                if (_poll && _poll.status === 'ok') {
                    if (_poll.pending && _poll.pending.length && this.state.currentSessionId) {
                        await this._loadSession(this.state.currentSessionId);
                    }
                    // Turno EN CURSO en esta sesión: el worker sigue en el servidor.
                    // Mostramos "pensando…" y refrescamos al terminar (la página solo
                    // se re-engancha, no ejecuta nada).
                    const _run = (_poll.running || []).find(
                        j => j.session_id === this.state.currentSessionId);
                    if (_run) {
                        this._resumeRunningTurn(_run.request_id, this.state.currentSessionId);
                    }
                }
            } catch (_e) { /* no crítico */ }

            this._mountedDone = true;
        }


        // ══════════════════════════════════════════════════════════════════════
        // 3. BUS + NOTIFICATIONS — Multi-tab sync via Odoo Bus
        // ══════════════════════════════════════════════════════════════════════

        /**
         * Register listener for Odoo Bus notifications.
         *
         * In Odoo 14: bus_service uses on()/off(), subscribes to 'partner' channel.
         * Fallback: core.bus for environments without bus_service.
         * Cleans up on unmount via _cleanupBusListener().
         */
        _setupBusListener() {
            try {
                // Odoo 14: bus_service exists but uses on()/off(), NOT addEventListener.
                // We also need to subscribe to the partner channel and start polling.
                const busService = this.env && this.env.services && this.env.services.bus_service;
                if (busService) {
                    busService.on('notification', this, this._onBusNotification.bind(this));
                    // Subscribe to the partner channel so we receive pns_chatboo_sync
                    if (busService.addChannel) {
                        busService.addChannel('partner');
                    }
                    if (busService.startPolling) {
                        busService.startPolling();
                    }
                } else {
                    // Fallback: classic core.bus
                    const core = require('web.core');
                    if (core && core.bus) {
                        core.bus.on('notification', this, this._onBusNotification.bind(this));
                    }
                }

                // Listen for async_done events broadcasted by the systray (always active)
                var _core = require('web.core');
                if (_core && _core.bus) {
                    this._coreBusAsyncHandler = async (payload) => {
                        // No pisar el turno que se acaba de ver en vivo en esta pestaña.
                        const _reqId = payload && payload.request_id;
                        if (_reqId && _reqId === this._lastLiveRequestId) {
                            return;
                        }
                        if (payload && payload.session_id) {
                            if (this.state.currentSessionId !== payload.session_id) {
                                this.state.currentSessionId = payload.session_id;
                            }
                            await this._loadSession(payload.session_id);
                        } else if (this.state.currentSessionId) {
                            await this._loadSession(this.state.currentSessionId);
                        }
                    };
                    _core.bus.on('chatboo_async_done', this, this._coreBusAsyncHandler);
                }
            } catch (e) {
                console.warn('Could not setup bus listener for Chatboo synchronization:', e);
            }
        }

        /**
         * Bus notification callback. Filters for 'pns_chatboo_sync' channel
         * and dispatches to _processNotifications.
         * @param {Array} notifications - Raw Odoo Bus notification payloads.
         */
        _onBusNotification(notifications) {
            this._processNotifications(notifications);
        }

        /**
         * Process incoming Odoo Bus notifications for chat synchronization.
         *
         * Notification types handled (via pns_chatboo_sync):
         *   - 'thinking':         Show thinking indicator
         *   - 'message_received': Reload session messages
         *   - 'new_chat':         Update session list, optionally switch
         *   - 'async_done':       Reload session with results
         *
         * Odoo 14 quirk: sendone() double-escapes JSON strings, so we
         * loop JSON.parse up to 3 times until we get an object.
         *
         * @param {Array} notifications - Raw bus notification array
         */
        async _processNotifications(notifications) {
            if (!notifications || !Array.isArray(notifications)) return;

            for (const notif of notifications) {
                let payload = null;
                let type = null;

                if (Array.isArray(notif) && notif.length === 2) {
                    type = notif[0];
                    payload = notif[1];
                    // Odoo 14 sendone(channel_tuple, json_string) format:
                    // type = channel (e.g. [partner_id,'partner']), payload = JSON string or parsed object.
                    // Try to parse if it's a string.
                    if (typeof payload === 'string') {
                        // Odoo 14 sendone double-escapes: JSON string wrapped in JSON string.
                        // Keep parsing until we get an object.
                        try {
                            let parsed = payload;
                            for (let i = 0; i < 3 && typeof parsed === 'string'; i++) {
                                parsed = JSON.parse(parsed);
                            }
                            payload = parsed;
                        } catch (e) { }
                    }
                    // If payload has embedded 'type' field (our sendone format), use that as type.
                    if (typeof payload === 'object' && payload && payload.type === 'pns_chatboo_sync') {
                        type = 'pns_chatboo_sync';
                    }
                } else if (notif && notif.type) {
                    type = notif.type;
                    payload = notif.payload;
                }

                if (type === 'pns_chatboo_sync' && payload) {
                    const action = payload.action;
                    const session_id = payload.session_id;

                    // For session-specific actions (not async_done or new_chat), skip if it's a different session.
                    // async_done notifications must always be shown regardless of current session.
                    // new_chat must update the session list across all tabs.
                    if (action !== 'async_done' && action !== 'new_chat' && action !== 'skills_changed' && this.state.currentSessionId && session_id && this.state.currentSessionId !== session_id) {
                        continue;
                    }

                    if (action === 'thinking') {
                        // El turno que ESTA pestaña atiende en vivo ya controla el
                        // indicador vía SSE (_sendMessage lo pone/quita). El aviso de
                        // bus 'thinking' puede llegar tarde (canal distinto) y, si es
                        // de nuestro propio turno, reactivaría un "Thinking…" que ya
                        // nadie limpia. Lo ignoramos para ese request_id — o si ya
                        // hay un SSE local dueño del spinner.
                        var _rid = payload.request_id;
                        if (this._sseOwnsThinking) {
                            continue;
                        }
                        if (_rid && (_rid === this._lastStreamRequestId || _rid === this._lastLiveRequestId)) {
                            continue;
                        }
                        this.state.thinking = true;
                        this.state.disabled = true;
                        if (_rid) {
                            this._resumeReqId = _rid;
                            this._lastStreamRequestId = _rid;
                            this.state.canCancel = true;
                        }
                    } else if (action === 'message_received') {
                        // Nunca apagar el spinner de un turno SSE en curso (p. ej. al
                        // continuar la conversación llega un sync del turno anterior).
                        if (!this._sseOwnsThinking) {
                            this.state.thinking = false;
                            this.state.disabled = false;
                        }
                        if (session_id) {
                            await this._loadSession(session_id);
                        } else if (this.state.currentSessionId) {
                            await this._loadSession(this.state.currentSessionId);
                        }
                    } else if (action === 'skills_changed') {
                        this._invalidateSkillsCache();
                        if (this.state.slashOpen && this.state.slashMode === 'skills') {
                            await this._openSkillsMenu();
                        }
                        if (
                            payload.confirm
                            && session_id
                            && String(this.state.currentSessionId) === String(session_id)
                        ) {
                            await this._loadSession(this.state.currentSessionId);
                        }
                    } else if (action === 'new_chat') {
                        // Update the session list so the new chat appears in the history modal
                        await this._loadSessions();
                        // Only switch to it and clear messages if this tab is completely idle
                        if (!this.state.currentSessionId) {
                            this.state.currentSessionId = session_id;
                            this.messages.splice(0, this.messages.length);
                            this.inputHistory = [];
                            this.historyIndex = -1;
                            this.currentInputBeforeHistory = "";
                        }
                    } else if (action === 'async_done') {
                        // No pisar el turno que se acaba de ver en vivo en esta pestaña
                        // (evita que al cambiar de ventana se borre el contenido).
                        var _renderedLiveAD = payload.request_id && payload.request_id === this._lastLiveRequestId;
                        var _ownInFlightAD = payload.request_id && payload.request_id === this._lastStreamRequestId;
                        // SSE local en curso: el spinner lo apaga solo _sendMessage /
                        // _runResultTurn. Un async_done del turno ANTERIOR no debe
                        // tumbar el "Thinking…" del turno nuevo al continuar el chat.
                        if (this._sseOwnsThinking) {
                            if (_ownInFlightAD || _renderedLiveAD) {
                                continue;
                            }
                            continue;
                        }
                        if (_renderedLiveAD) {
                            // Ya lo vimos en vivo: no recargar. Pero sí limpiar por si
                            // un 'thinking' tardío de este mismo turno dejó la burbuja.
                            this.state.thinking = false;
                            this.state.disabled = false;
                            continue;
                        }
                        // Fin de un turno que no vimos en vivo (p. ej. reanudado
                        // tras F5): quitar el "pensando…" y parar el sondeo.
                        if (payload.request_id && payload.request_id === this._resumeReqId) {
                            this._resumeReqId = null;
                        }
                        // Recargar la sesion donde se guardó el resultado (siempre, aunque sea diferente a la actual)
                        if (session_id) {
                            if (this.state.currentSessionId !== session_id) {
                                // Cambiamos a la sesión donde el worker guardó el resultado
                                this.state.currentSessionId = session_id;
                            }
                            await this._loadSession(session_id);
                        } else if (this.state.currentSessionId) {
                            await this._loadSession(this.state.currentSessionId);
                        }
                        this.state.thinking = false;
                        this.state.disabled = false;
                        this._maybeSpeakLastAssistant();
                    }
                }
            }
        }

        // ══════════════════════════════════════════════════════════════════════
        // 2. SESSION MANAGEMENT — CRUD, rename, bulk delete
        // ══════════════════════════════════════════════════════════════════════

        /**
         * Load the list of available sessions from the server.
         * Populates this.state.sessions (sorted by last_used_date desc).
         * @returns {Promise<void>}
         */
        async _loadSessions() {
            try {
                const result = await this.props.rpc({
                    route: '/chatboo/sessions/list',
                    params: {}
                });
                if (result.status === 'ok') {
                    // Format dates for display in template
                    this.state.sessions = (result.sessions || []).map(session => {
                        if (session.last_used_date) {
                            try {
                                session.formatted_date = new Date(session.last_used_date).toLocaleDateString(formatters.getSessionLocale());
                            } catch (e) {
                                session.formatted_date = session.last_used_date;
                            }
                        }
                        return session;
                    });
                }
                return result;
            } catch (error) {
                console.error('Error loading sessions:', error);
                return null;
            }
        }

        /**
         * Open session history modal and reload sessions
         */
        _focusChatInput() {
            // Foco diferido a la caja de prompt: tras el repintado (cierre del
            // modal de histórico o carga de sesión) el foco se iría al body; lo
            // devolvemos al input para escribir sin tener que clicar antes.
            requestAnimationFrame(() => {
                const overlay = document.getElementById('o_chatboo_persistent_overlay');
                if (overlay && (
                    overlay.style.display === 'none'
                    || overlay.classList.contains('d-none')
                )) {
                    return;
                }
                const el = this.chatInputRef && this.chatInputRef.el;
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

        async _showSessions() {
            // Clear selection when opening modal
            this.state.selectedSessions = [];
            // Reload sessions before showing modal
            await this._loadSessions();
            // Open modal
            this.state.showSessionModal = true;
        }

        /**
         * Create a new blank session on the server and switch to it.
         * Clears the message list and optionally the UI.
         * @param {boolean} [clearUI=false] - If true, also clears the input field.
         * @returns {Promise<void>}
         */
        async _createNewSession(clearUI = false) {
            try {
                const result = await this.props.rpc({
                    route: '/chatboo/sessions/create',
                    params: {}
                });
                if (result.status === 'ok' && result.session && result.session.id) {
                    this.state.currentSessionId = result.session.id;
                    await this._loadSessions();
                    console.log('✅ New session created:', result.session.id, result.session.name);

                    if (clearUI) {
                        // CLEAR MESSAGES FOR REAL "NEW CHAT" VIA MENU
                        this._resetSessionOccupancy();
                        this.messages.splice(0, this.messages.length);
                        this.inputHistory = [];
                        this.historyIndex = -1;
                        this.currentInputBeforeHistory = "";
                        // Nueva sesión iniciada por el usuario: foco a la caja de prompt.
                        this._focusChatInput();
                    }

                    // Don't load the session (clear messages) - just set it as current
                    // This allows continuing the current conversation in the new session
                } else {
                    console.warn('⚠️ Session creation returned unexpected result:', result);
                }
            } catch (error) {
                console.error('❌ Error creating session:', error);
            }
        }

        /**
         * Load a specific session's messages from the server.
         * Rebuilds the local message array and re-renders the chat.
         * @param {number} sessionId - Server-side session ID to load.
         * @returns {Promise<boolean>} True if the session was loaded successfully.
         */
        async _loadSession(sessionId) {
            try {
                // Guardar la sesión actual antes de cambiar (si es diferente y existe)
                if (this.state.currentSessionId && this.state.currentSessionId !== sessionId && this.messages.length > 0) {
                    this._saveCurrentSession().catch(e => console.warn('Auto-save before switch failed:', e));
                }

                const result = await this.props.rpc({
                    route: '/chatboo/sessions/load',
                    params: { session_id: sessionId }
                });
                if (result.status === 'ok') {
                    const messages = result.session.messages || [];
                    // Convert old HTML context_info to structured data if needed, 
                    // and reconstruct context_info from usage for async/loaded messages
                    this._resetSessionOccupancy();
                    messages.forEach(msg => {
                        if (msg.context_info && typeof msg.context_info === 'string') {
                            msg.context_info = null;
                        }
                        // Adjuntos: el worker guarda chips en msg.images / msg.files
                        // (URLs /web/image|/web/content → ir.attachment). El template
                        // los pinta aparte (como owl2). Aquí solo normalizamos el
                        // texto plano para t-raw; NO mezclar miniaturas en content
                        // (ese enfoque fallaba en O14 y además el save las perdía).
                        if (msg.role === 'user') {
                            msg.images = Array.isArray(msg.images) ? msg.images : [];
                            msg.files = Array.isArray(msg.files) ? msg.files : [];
                            const rawContent = msg.content || '';
                            const looksHtml = /<(img|div|span|a|br)\b/i.test(rawContent);
                            if (!looksHtml) {
                                const _txt = String(rawContent)
                                    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
                                    .replace(/\n/g, '<br/>');
                                msg.content = _txt
                                    ? `<div style="font-family:'Courier New',Courier,monospace;font-size:1.25em;line-height:1.4;">${_txt}</div>`
                                    : '';
                            } else if (msg.images.length || msg.files.length) {
                                // Histórico antiguo: content ya traía <img>/chips
                                // inyectados. Si también hay chips, limpiamos el
                                // HTML de adjuntos del content para no duplicar.
                                let cleaned = rawContent
                                    .replace(/<div[^>]*>\s*(?:<span[^>]*>\s*<a[^>]*>\s*<img[\s\S]*?<\/a>[\s\S]*?<\/span>\s*)+<\/div>/gi, '')
                                    .replace(/<div[^>]*>\s*(?:<a[^>]*class="[^"]*o_chatboo_file_chip[\s\S]*?<\/a>\s*|<span[^>]*class="[^"]*o_chatboo_file_chip[\s\S]*?<\/span>\s*)+<\/div>/gi, '')
                                    .replace(/<(?:div|a)[^>]*class="[^"]*o_chatboo_file_banner[\s\S]*?<\/(?:div|a)>/gi, '');
                                msg.content = cleaned;
                            }
                        }
                        // Asistente: el worker (y el autoguardado) persisten
                        // Markdown/HTML crudo. El servidor no hace markdown→HTML;
                        // hay que formatear SIEMPRE al pintar. Si solo se hace
                        // cuando msg.raw, un save posterior (sin ese flag) deja
                        // ##/** literales en la burbuja.
                        if (msg.role === 'assistant') {
                            const rawText = msg.original_content || msg.content || '';
                            msg.original_content = msg.original_content || rawText;
                            msg.content = this._formatContent(rawText);
                            msg.formatted_html = msg.content;
                            msg.raw = false;
                            msg.files = Array.isArray(msg.files)
                                ? msg.files.filter((f) => f && (f.url || f.pending))
                                : [];
                        }
                        this._rebuildContextInfo(msg);
                    });
                    // Mutate existing proxy to preserve Owl reactivity
                    this.messages.splice(0, this.messages.length);
                    if (messages && messages.length > 0) {
                        this.messages.push(...messages);
                    }

                    this.inputHistory = result.session.input_history || [];
                    this.historyIndex = -1;
                    this.currentInputBeforeHistory = "";
                    this.state.currentSessionId = sessionId;

                    // Modal is handled independently — don't close/open it from here
                    this.scrollToBottom();
                    this._fulfillPendingExportsInView();
                    return true;
                }
            } catch (error) {
                console.error('Error loading session:', error);
            }
            return false;
        }

        /**
         * Reanuda un turno EN CURSO tras un F5: el worker sigue trabajando en el
         * servidor. Mostramos "pensando…" y sondeamos suave hasta que termine,
         * entonces refrescamos la sesión. El bus async_done hace lo mismo si llega
         * antes; ambos son idempotentes. La página solo se re-engancha.
         */
        _resumeRunningTurn(requestId, sessionId) {
            this.state.thinking = true;
            this.state.disabled = true;
            this.state.canCancel = true;
            this._resumeReqId = requestId;
            this._lastStreamRequestId = requestId;
            const poll = async () => {
                if (this._resumeReqId !== requestId) {
                    return;  // reemplazado o ya resuelto
                }
                let res = null;
                try {
                    res = await this.props.rpc({ route: '/chatboo/async/poll', params: { session_id: sessionId } });
                } catch (_e) {
                    setTimeout(poll, 2500);
                    return;
                }
                const stillRunning = ((res && res.running) || []).some(
                    j => j.request_id === requestId);
                if (stillRunning) {
                    setTimeout(poll, 2000);
                    return;
                }
                this._resumeReqId = null;
                if (sessionId === this.state.currentSessionId) {
                    await this._loadSession(sessionId);
                    this.state.thinking = false;
                    this.state.canCancel = false;
                    this.state.disabled = false;
                }
            };
            setTimeout(poll, 1500);
        }

        /**
         * Called when user clicks a session in the history modal.
         * Loads the session and then closes the modal.
         */
        async _selectSession(sessionId) {
            await this._loadSession(sessionId);
            this.state.showSessionModal = false;
            this._focusChatInput();
        }

        /**
         * Persist the current session's messages to the server.
         * Called on session switch, before creating a new session, etc.
         * @returns {Promise<void>}
         */
        _msgImageUrl(mimg) {
            if (!mimg) {
                return '';
            }
            return (typeof mimg === 'object') ? (mimg.url || '') : String(mimg);
        }

        _msgImageName(mimg) {
            if (mimg && typeof mimg === 'object') {
                return mimg.name || '';
            }
            return '';
        }

        _plainUserContent(content) {
            // Al persistir: texto plano, sin base64 ni HTML de miniaturas.
            if (!content || typeof content !== 'string') {
                return content || '';
            }
            if (content.indexOf('<') === -1 && content.indexOf('data:image') === -1) {
                return content;
            }
            let plain = content
                .replace(/<br\s*\/?>/gi, '\n')
                .replace(/<[^>]+>/g, ' ')
                .replace(/data:image[^\s"']+/g, ' ')
                .replace(/&nbsp;/g, ' ')
                .replace(/&amp;/g, '&')
                .replace(/&lt;/g, '<')
                .replace(/&gt;/g, '>')
                .replace(/\s+/g, ' ')
                .trim();
            return plain;
        }

        _messagesForPersist() {
            const messagesArray = Array.isArray(this.messages) ? this.messages : (this.messages || []);
            return messagesArray.map((m) => {
                const out = {
                    role: m.role,
                    content: m.role === 'user' ? this._plainUserContent(m.content) : (m.original_content || m.content || ''),
                    timestamp: m.timestamp || m.ts || '',
                };
                // Fuente cruda para el siguiente load (Showdown). Sin esto el
                // save pisa el raw:true del worker y el historial queda tocho.
                if (m.role === 'assistant') {
                    out.raw = true;
                    if (m.original_content) {
                        out.original_content = m.original_content;
                    }
                }
                if (m.role === 'user') {
                    const imgs = (m.images || []).map((it) => {
                        if (it && typeof it === 'object') {
                            return { url: it.url || '', name: it.name || null };
                        }
                        return { url: String(it || ''), name: null };
                    }).filter((it) => it.url && it.url.indexOf('data:') !== 0);
                    const files = (m.files || []).filter((f) => f && (f.url || f.name));
                    if (imgs.length) {
                        out.images = imgs;
                    }
                    if (files.length) {
                        out.files = files;
                    }
                }
                if (m.usage) {
                    out.usage = m.usage;
                }
                if (m.context_limit) {
                    out.context_limit = m.context_limit;
                }
                if (m.model_details) {
                    out.model_details = m.model_details;
                }
                if (m.sources) {
                    out.sources = m.sources;
                }
                if (m.records) {
                    out.records = m.records;
                }
                if (m.speed_tps != null) {
                    out.speed_tps = m.speed_tps;
                }
                if (m.prompt_speed_tps != null) {
                    out.prompt_speed_tps = m.prompt_speed_tps;
                }
                if (m.local_ack) {
                    out.local_ack = true;
                }
                if (m.verification_ack) {
                    out.verification_ack = true;
                }
                if (m.offtopic) {
                    out.offtopic = true;
                }
                if (m.correlation_id) {
                    out.correlation_id = m.correlation_id;
                }
                const userPrompt = m.user_prompt
                    || (m.meta && m.meta.user_prompt)
                    || '';
                if (userPrompt) {
                    out.user_prompt = userPrompt;
                }
                if (m.meta) {
                    out.meta = m.meta;
                }
                if (m.backend_history && m.backend_history.length) {
                    out.backend_history = m.backend_history;
                }
                if (m.clip_data) {
                    out.clip_data = m.clip_data;
                }
                if (m.role === 'assistant' && m.files && m.files.length) {
                    out.files = m.files;
                }
                return out;
            });
        }

        async _saveCurrentSession() {
            // Create new session if none exists
            if (!this.state.currentSessionId) {
                await this._createNewSession(false); // DO NOT clear UI when saving first message
                // After creating, continue to save (don't return)
                if (!this.state.currentSessionId) {
                    console.warn('⚠️ Failed to create session, cannot save');
                    return;
                }
            }

            try {
                const messagesArray = this._messagesForPersist();
                const inputHistoryArray = Array.isArray(this.inputHistory) ? this.inputHistory : (this.inputHistory || []);

                console.log('💾 Saving session:', this.state.currentSessionId, 'Messages:', messagesArray.length, 'History:', inputHistoryArray.length);

                const result = await this.props.rpc({
                    route: '/chatboo/sessions/save',
                    params: {
                        session_id: this.state.currentSessionId,
                        messages: messagesArray,
                        input_history: inputHistoryArray
                        // conversation_id is managed automatically by backend from Router response
                    }
                });
                if (result.status === 'ok') {
                    await this._loadSessions();
                    console.log('✅ Session saved successfully:', this.state.currentSessionId);
                } else {
                    console.warn('⚠️ Session save returned error:', result);
                }
            } catch (error) {
                console.error('❌ Error saving session:', error);
            }
        }

        /**
         * Delete a session from the server and refresh the session list.
         * If the deleted session is the active one, creates a new session.
         * @param {number} sessionId - Server-side session ID to delete.
         * @returns {Promise<void>}
         */
        async _deleteSession(sessionId) {
            if (sessionId && typeof sessionId === 'object' && sessionId.target) {
                // OWL1 a veces pasa el evento si el binding del template falla.
                return;
            }
            if (!sessionId) {
                return;
            }
            if (!confirm(_t('Delete this chat session?'))) {
                return;
            }
            try {
                const result = await this.props.rpc({
                    route: '/chatboo/sessions/delete',
                    params: { session_id: sessionId }
                });
                if (result && result.status === 'ok') {
                    await this._loadSessions();
                    if (this.state.currentSessionId === sessionId) {
                        // Clear current session if deleted
                        this.state.currentSessionId = null;
                        this.messages.splice(0, this.messages.length);
                        this.inputHistory = [];
                    }
                } else {
                    const msg = (result && result.message) || _t('Could not delete the session.');
                    console.error('Error deleting session:', result);
                    if (this.props.notification) {
                        this.props.notification({ message: msg, type: 'danger' });
                    }
                }
            } catch (error) {
                console.error('Error deleting session:', error);
                if (this.props.notification) {
                    this.props.notification({
                        message: (error && error.message) || _t('Could not delete the session.'),
                        type: 'danger',
                    });
                }
            }
        }

        /**
         * Toggle selection state of a session in the sessions list (for bulk ops).
         * @param {number} sessionId - Session to toggle.
         */
        _toggleSessionSelection(sessionId) {
            const index = this.state.selectedSessions.indexOf(sessionId);
            if (index === -1) {
                this.state.selectedSessions.push(sessionId);
            } else {
                this.state.selectedSessions.splice(index, 1);
            }
        }

        /**
         * Select or deselect all sessions in the list (bulk checkbox handler).
         * @param {Event} e - Change event from the "select all" checkbox.
         */
        _toggleAllSessions(e) {
            if (e.target.checked) {
                this.state.selectedSessions = this.state.sessions.map(s => s.id);
            } else {
                this.state.selectedSessions = [];
            }
        }

        /**
         * Delete all currently selected sessions in bulk.
         * Shows a confirmation dialog before proceeding.
         * @returns {Promise<void>}
         */
        async _bulkDeleteSessions() {
            if (this.state.selectedSessions.length === 0) return;

            if (!confirm(_t('Are you sure you want to delete the selected sessions (%s)?').replace('%s', this.state.selectedSessions.length))) {
                return;
            }

            try {
                const result = await this.props.rpc({
                    route: '/chatboo/sessions/bulk_delete',
                    params: { session_ids: this.state.selectedSessions }
                });
                if (result && result.status === 'ok') {
                    // Check if current session was deleted
                    if (this.state.selectedSessions.includes(this.state.currentSessionId)) {
                        this.state.currentSessionId = null;
                        this.messages.splice(0, this.messages.length);
                        this.inputHistory = [];
                    }
                    this.state.selectedSessions = [];
                    await this._loadSessions();
                } else {
                    const msg = (result && result.message) || _t('Could not delete the sessions.');
                    console.error('Bulk delete returned error:', result);
                    if (this.props.notification) {
                        this.props.notification({ message: msg, type: 'danger', sticky: true });
                    }
                }
            } catch (error) {
                console.error('Error bulk deleting sessions:', error);
                if (this.props.notification) {
                    this.props.notification({
                        message: (error && error.message) || _t('Could not delete the sessions.'),
                        type: 'danger',
                        sticky: true,
                    });
                }
            }
        }

        /**
         * Enter inline rename mode for a session.
         * @param {number} sessionId - Session to rename.
         * @param {string} currentName - Current session name (pre-fills the input).
         */
        _startRenameSession(sessionId, currentName) {
            this.state.editingSessionId = sessionId;
            this.state.editingSessionName = currentName;
        }

        /** Cancel the inline rename and restore the previous name. */
        _cancelRenameSession() {
            this.state.editingSessionId = null;
            this.state.editingSessionName = "";
        }

        /**
         * Save the inline-renamed session name to the server.
         * @returns {Promise<void>}
         */
        async _saveRenameSession() {
            if (!this.state.editingSessionId || !this.state.editingSessionName.trim()) {
                return;
            }

            try {
                const result = await this.props.rpc({
                    route: '/chatboo/sessions/rename',
                    params: {
                        session_id: this.state.editingSessionId,
                        new_name: this.state.editingSessionName.trim()
                    }
                });
                if (result.status === 'ok') {
                    await this._loadSessions();
                    this._cancelRenameSession();
                }
            } catch (error) {
                console.error('Error renaming session:', error);
            }
        }

        /**
         * Handle keydown in the rename input (Enter = save, Escape = cancel).
         * @param {KeyboardEvent} ev
         */
        _onRenameInputKeydown(ev) {
            if (ev.key === 'Enter') {
                this._saveRenameSession();
            } else if (ev.key === 'Escape') {
                this._cancelRenameSession();
            }
        }

        /** OWL willUnmount lifecycle hook. Cleans up bus subscription and intervals. */
        async willUnmount() {
            this._closeSlashUi();
            // Cleanup - no longer needed with reactive template approach
            if (this._refLinkHandler && this._refLinkEl) {
                this._refLinkEl.removeEventListener('click', this._refLinkHandler, true);
                this._refLinkHandler = null;
                this._refLinkEl = null;
            }
            this._teardownTtsClickAnchoring();
        }

        // ══════════════════════════════════════════════════════════════════════
        // 4. NETWORK + HEALTH — Connection testing and JSON-RPC helper
        // ══════════════════════════════════════════════════════════════════════

        /**
         * Setup delegated click handlers for assistant message actions:
         * copy-to-clipboard, download-as-PDF, download-as-Excel buttons.
         * Uses event delegation on the chat container for efficiency.
         */
        _setupContextClickHandling() {
            // This is intentionally empty
        }

        /**
         * Check MCP server health and update the status indicator.
         *
         * Calls /chatboo/health which returns {status, backend, ...}.
         * On success: green indicator + connection details tooltip.
         * On failure: red indicator + error tooltip.
         */
        async _checkHealth() {
            try {
                const result = await this.props.rpc({
                    route: '/chatboo/check_health',
                    params: {}
                });

                if (result.status === 'ok' && result.provider) {
                    this._applyProviderHeader(result);
                    this.state.connected = result.connected !== false;
                } else if (result.provider) {
                    this._applyProviderHeader(result);
                    this.state.connected = false;
                }
                this.state.can_save_for_template = !!result.can_save_raw;
                // Se guarda incluso sin rates: trae el motivo del fallo para el chip.
                this._fx = (result && result.fx) ? result.fx : null;
                this._defaultDisplayCurrency = (result && result.display_currency) || 'USD';
                this._applyCardWidthRatio(result && result.card_width_ratio);
                this._refreshUsageChips();

                if (result.status === 'error') {
                    this.state.disabled = true;
                    this.state.connected = false;
                    this.props.notification({ message: result.message, type: "danger", sticky: true });
                    const errorTime = new Date();
                    this.messages.push({
                        role: "assistant",
                        content: '<span class="text-danger"><i class="fa fa-exclamation-triangle"></i> ' + result.message + '</span>',
                        timestamp: this._formatTimestamp(errorTime),
                        context_info: this._makeContextInfo(null, 0, {}),
                    });
                }
            } catch (error) {
                this.state.providerName = "Connection Error";
                this.state.connected = false;
                this.messages.push({
                    role: "assistant",
                    content: '<span class="text-danger"><i class="fa fa-exclamation-triangle"></i> Connection Error: ' + error.message + '</span>',
                    timestamp: formatters.formatWallclock(new Date()),
                    context_info: this._makeContextInfo(null, 0, {}),
                });
            }
            this._initTtsUi();
            // Load providers for the selector (non-blocking)
            this._loadProviders();
        }

        /**
         * Web Speech API: detect support and restore user preference (localStorage).
         */
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

        /** Read aloud the latest assistant bubble when TTS is on. */
        _maybeSpeakLastAssistant() {
            const tts = window.__chatbooTts;
            if (!tts || !tts.isEnabled()) {
                return;
            }
            for (let i = this.messages.length - 1; i >= 0; i--) {
                const m = this.messages[i];
                if (m.role !== 'assistant') {
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
            const fallback = res.provider || 'Unknown';
            this.state.providerName = fallback;
            if (res.alias) {
                this.state.providerHost = '';
                this.state.providerModel = res.alias;
                return;
            }
            this.state.providerModel = res.model || '';
            this.state.providerHost = res.host || '';
            if (!this.state.providerModel && fallback.includes(' → ')) {
                const parts = fallback.split(' → ');
                this.state.providerHost = parts[0];
                this.state.providerModel = parts.slice(1).join(' → ');
            }
        }

        _syncSelectedProviderHeader() {
            const sel = this.state.providers.find(p => p.id === this.state.selectedProviderId);
            if (!sel) {
                return;
            }
            if (sel.alias) {
                this.state.providerHost = '';
                this.state.providerModel = sel.alias;
            } else {
                this.state.providerModel = sel.model || sel.name || '';
                this.state.providerHost = sel.host || '';
            }
            this.state.providerName = sel.display || this.state.providerName;
        }

        /**
         * Fetch available providers for the header dropdown.
         * Restores previous selection from localStorage if available.
         */
        _currencyForProvider(name, explicit) {
            const want = String(explicit || '').trim().toUpperCase();
            if (want && want.length === 3) {
                return want;
            }
            return this._defaultDisplayCurrency || 'USD';
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
            const extracted = extractUsageCost(usage);
            if (extracted !== undefined) {
                return extracted;
            }
            if (turnTokensValue(usage) === 0) {
                return 0;
            }
            return undefined;
        }

        _chipFields(usage, providerName, displayCurrency) {
            const turnTokens = turnTokensValue(usage);
            const turnK = turnTokens > 0 ? (turnTokens / 1024).toFixed(2) : null;
            const turnLabel = formatTurnTokensLabel(usage);
            const cost = formatCostLabel(
                this._spendCost(usage),
                this._currencyForProvider(providerName, displayCurrency),
                this._fx,
            );
            const turnTitle = _t('Tokens billed this turn (all LLM rounds)');
            const spendLabel = turnLabel + ' · ' + cost.label;
            const spendTitle = [turnLabel !== '-' ? turnTitle : '', cost.title].filter(Boolean).join(' · ');
            return {
                turnCodeTitle: _t('Turn id (MCP log). Click to copy. Use with /create-skill.'),
                bufferTitle: _t('Session context occupancy · provider cap'),
                turnTokensK: turnK,
                turnLabel,
                turnTitle,
                costLabel: cost.label,
                costTitle: cost.title,
                spendLabel,
                spendTitle,
                speedTitle: _t('Generation speed (tokens/s)'),
            };
        }

        _makeContextInfo(usage, contextLimit, extras) {
            extras = extras || {};
            const rawUsed = contextUsedTokens(usage);
            const rawLimit = contextLimit || 0;
            const occupied = (usage || rawLimit)
                ? this._occupyFromUsage(rawUsed, rawLimit)
                : { used: 0, limit: 0 };
            const used = occupied.used;
            const limit = occupied.limit;
            const showBuffer = Boolean(used && limit);
            let usageColor = 'text-success';
            let usageColorHex = '#28a745';
            let usageIcon = 'fa-bell-o';
            let usedK = null;
            let limitK = null;
            let usagePercent = 0;
            if (showBuffer) {
                usedK = (used / 1024).toFixed(2);
                limitK = (limit / 1024).toFixed(2);
                usagePercent = ((used / limit) * 100).toFixed(1);
                if (usagePercent > 80) {
                    usageColor = 'text-danger';
                    usageColorHex = '#dc3545';
                    usageIcon = 'fa-exclamation-triangle';
                } else if (usagePercent > 60) {
                    usageColor = 'text-warning';
                    usageColorHex = '#ffc107';
                    usageIcon = 'fa-bomb';
                }
            }
            const speedTps = extras.speedTps || 0;
            const promptSpeedTps = extras.promptSpeedTps || 0;
            const turnCode = (extras.turnCode || '').trim();
            return {
                turnCode,
                showBuffer,
                usedK,
                limitK,
                freeK: showBuffer ? ((limit - used) / 1024).toFixed(2) : null,
                usagePercent,
                usageColor,
                usageColorHex,
                usageIcon,
                k1_ctx: usedK ? usedK + 'k' : null,
                speedTps: speedTps ? Number(speedTps).toFixed(1) : null,
                promptSpeedTps: promptSpeedTps ? Number(promptSpeedTps).toFixed(0) : null,
                ...this._chipFields(usage, extras.provider || '', extras.currency || ''),
            };
        }

        /**
         * Rehidrata los chips de consumo de un mensaje leído de la BD.
         *
         * El histórico guarda usage / context_limit / velocidad, pero no el
         * bloque pintable: hay que reconstruirlo en TODA ruta de carga. Si solo
         * lo hace una, abrir Chatboo deja el turno sin tokens ni coste aunque el
         * consumo esté facturado y guardado.
         */
        _rebuildContextInfo(msg) {
            if (!msg || msg.role !== 'assistant') {
                return;
            }
            if (msg.local_ack && !msg.usage && !msg.context_limit) {
                return;
            }
            msg.context_info = this._makeContextInfo(msg.usage, msg.context_limit, {
                speedTps: msg.speed_tps || 0,
                promptSpeedTps: msg.prompt_speed_tps || 0,
                provider: (msg.model_details && msg.model_details.provider) || '',
                currency: (msg.model_details && msg.model_details.display_currency) || '',
                turnCode: msg.correlation_id
                    || (msg.meta && msg.meta.correlation_id)
                    || '',
            });
        }

        _refreshUsageChips() {
            this._resetSessionOccupancy();
            (this.messages || []).forEach((msg) => {
                this._rebuildContextInfo(msg);
            });
        }

        _isOfftopicMessage(m) {
            if (m && (m.verification_ack || (m.meta && m.meta.verification_ack))) {
                return false;
            }
            return !!(m && (m.offtopic || m.local_ack || (m.meta && m.meta.local_ack)));
        }

        _lastUserPromptText() {
            const msgs = this.messages || [];
            for (let i = msgs.length - 1; i >= 0; i--) {
                if (msgs[i].role === 'user' && !this._isOfftopicMessage(msgs[i])) {
                    return this._plainUserContent(msgs[i].content || '');
                }
            }
            return '';
        }

        _messagesForModel(messages, excludeTail) {
            const list = messages || [];
            const base = excludeTail ? list.slice(0, -excludeTail) : list.slice();
            return base.filter((m) => m && m.role !== 'system' && !this._isOfftopicMessage(m)).map((m) => {
                if (m.role === 'user') {
                    let text = m.content;
                    if (typeof text === 'string' && text.includes('<')) {
                        const tempDiv = document.createElement('div');
                        tempDiv.innerHTML = text;
                        text = tempDiv.textContent || tempDiv.innerText || text;
                    }
                    return { role: 'user', content: this._clipForLlm(text, 4000) };
                }
                return { role: m.role, content: this._contentForLlm(m.content) };
            });
        }

        _clipForLlm(text, limit) {
            const s = (text == null) ? '' : String(text);
            if (!limit || s.length <= limit) {
                return s;
            }
            return s.slice(0, Math.max(0, limit - 1)).replace(/\s+$/, '') + '…';
        }

        _contentForLlm(text) {
            // Fallback when backend_history is missing: never replay on-screen
            // tables (cell text saturates prefill). Matches history_compact.py.
            const s = (text == null) ? '' : String(text);
            if (s.indexOf('[On-screen artifact') === 0) {
                return s;
            }
            const fat = s.length > 2500
                || /<table\b/i.test(s)
                || s.indexOf('o_chatboo_table_block') >= 0
                || s.indexOf('data-chatboo-dataset') >= 0;
            if (!fat) {
                if (typeof s === 'string' && s.includes('<')) {
                    const tempDiv = document.createElement('div');
                    tempDiv.innerHTML = s;
                    return (tempDiv.textContent || tempDiv.innerText || s).trim();
                }
                return s;
            }
            return '[On-screen artifact | kind=table | ~' + s.length + ' characters]\n'
                + 'The full document is already visible to the user. Do not reprint the rows. '
                + 'Cached dataset is previous_result if you need to reformat or recompute. '
                + 'Use tools for a new query.';
        }

        _markLastUserOfftopic() {
            for (let i = this.messages.length - 1; i >= 0; i--) {
                if (this.messages[i].role === 'user') {
                    this.messages[i].offtopic = true;
                    break;
                }
            }
        }

        async _loadProviders() {
            try {
                const providerRes = await this.props.rpc({ route: '/chatboo/providers', params: {} });
                if (providerRes && providerRes.status === 'ok') {
                    this.state.providers = providerRes.providers || [];
                    this._refreshUsageChips();
                    const savedProvider = parseInt(localStorage.getItem('chatboo_provider_id'), 10);
                    if (savedProvider && this.state.providers.some(p => p.id === savedProvider)) {
                        this.state.selectedProviderId = savedProvider;
                    } else {
                        this.state.selectedProviderId = providerRes.default_provider_id || (this.state.providers[0] || {}).id || null;
                    }
                    this._syncSelectedProviderHeader();
                }
            } catch (e) {
                console.warn('Chatboo: failed to load providers:', e);
            }
        }


        /**
         * Handle provider selector change. Persists to localStorage.
         */
        _noop() {}

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
                localStorage.setItem('chatboo_provider_id', String(id));
            } else {
                localStorage.removeItem('chatboo_provider_id');
            }
            this._syncSelectedProviderHeader();
            this.state.providerMenuOpen = false;
        }

        /**
         * Test the LLM provider connection by sending a trivial prompt.
         * Shows a success/failure notification and updates the UI badge.
         * @returns {Promise<void>}
         */
        async _testConnection() {
            try {
                const result = await this.props.rpc({
                    route: '/chatboo/test_connection',
                    params: {}
                });

                if (result.status === 'success') {
                    // Odoo notification format: { message, type, sticky, title }
                    const notificationMsg = result.title ? `${result.title}: ${result.message}` : result.message;
                    this.props.notification({
                        message: notificationMsg,
                        type: result.type || 'success',
                        sticky: false
                    });
                    this.state.connected = true;
                } else {
                    const notificationMsg = result.title ? `${result.title}: ${result.message || 'Unknown error'}` : (result.message || 'Unknown error');
                    this.props.notification({
                        message: notificationMsg,
                        type: 'danger',
                        sticky: false
                    });
                    this.state.connected = false;
                }
            } catch (error) {
                this.props.notification({
                    message: `Connection Test Failed: ${error.message || 'Unknown error'}`,
                    type: 'danger',
                    sticky: false
                });
                this.state.connected = false;
                const errorTime = new Date();
                this.messages.push({
                    role: "assistant",
                    content: '<span class="text-danger"><i class="fa fa-exclamation-triangle"></i> Connection Error: ' + error.message + '</span>',
                    timestamp: this._formatTimestamp(errorTime),
                    context_info: this._makeContextInfo(null, 0, {}),
                });
            }
        }

        /**
         * Format timestamp with date and duration
         * @param {Date} startTime - Start time
         * @param {Date} endTime - End time (optional, defaults to now)
         * @returns {string} - Formatted timestamp "yyyy-mm-dd hh:mm:ss (X segundos)"
         */
        _formatTimestamp(startTime, endTime = null) {
            if (!endTime) endTime = new Date();
            const duration = Math.round((endTime - startTime) / 1000); // Duration in seconds
            const wall = formatters.formatWallclock(startTime);
            return `${wall} (${duration} segundos)`;
        }

        /**
         * Parse a raw SSE (Server-Sent Events) text chunk into structured events.
         * Handles multi-line data fields and event type annotations.
         * @param {string} raw - Raw SSE text (may contain multiple events).
         * @returns {Array<{event: string, data: string}>} Parsed events.
         */
        /**
         * Make a JSON-RPC call to a chatboo backend route with error handling.
         * Wraps this.props.rpc() with unified error logging and user notification.
         * @param {string} route - Backend route path (e.g. '/chatboo/send').
         * @param {Object} params - JSON body parameters.
         * @returns {Promise<Object>} Server response payload.
         */
        _callJsonRoute(route, params, options) {
            // Llama a una ruta Odoo type='json' (envoltorio JSON-RPC). Devuelve result.
            // options.timeoutMs: aborta el fetch (evita spinner infinito si el worker
            // está bloqueado por un lock de otra sesión, p. ej. caja A MCP).
            options = options || {};
            var timeoutMs = options.timeoutMs;
            var ctrl = (typeof AbortController !== 'undefined') ? new AbortController() : null;
            var timer = null;
            if (ctrl && timeoutMs) {
                timer = setTimeout(function () { ctrl.abort(); }, timeoutMs);
            }
            return fetch(route, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                credentials: 'same-origin',
                body: JSON.stringify({ jsonrpc: '2.0', method: 'call', params: params || {} }),
                signal: ctrl ? ctrl.signal : undefined,
            }).then(function (r) { return r.json(); }).then(function (d) { return d.result; })
            .finally(function () { if (timer) { clearTimeout(timer); } });
        }

        _restorePendingVerifications() {
            // Same SoT as Security → Authorizations: live pending rows, not SSE memory.
            var self = this;
            return this._callJsonRoute('/pns_ai_mcp/verification/pending', {})
                .then(function (res) {
                    var items = (res && res.items) || [];
                    for (var i = 0; i < items.length; i++) {
                        var evt = items[i];
                        if (evt && evt.verification_id) {
                            self._showVerificationUI(evt);
                        }
                    }
                })
                .catch(function () {
                    return undefined;
                });
        }

        // ══════════════════════════════════════════════════════════════════════
        // 5. SAFE PLAN VERIFICATION — Confirm/reject AI operations
        // ══════════════════════════════════════════════════════════════════════

        /**
         * Render the Safe Plan verification card (fixed-position overlay).
         *
         * This is the human-in-the-loop confirmation UI. When the AI proposes
         * a write operation (via propose_safe_operations), the server sends a
         * bus notification that triggers this method.
         *
         * Flow:
         *   1. Server creates pending operation → bus notification
         *   2. This method renders a confirmation card with danger level colors
         *   3. User clicks Confirm → /pns_ai_mcp/verification/confirm
         *   4. User clicks Cancel  → /pns_ai_mcp/verification/cancel
         *   5. CRUD writes → local ack in chat (no LLM). fetch_url → _runResultTurn().
         *
         * Danger levels determine UI treatment (informational only):
         *   🟢 low    (create/copy/url whitelisted) → green border
         *   🟡 medium (write/url not whitelisted)   → amber border
         *   🔴 high   (unlink)                      → red border, 5-second cooldown
         *
         * @param {Object} evt - Verification event from bus
         * @param {string} evt.verification_id - Unique operation ID (e.g. 'WRIT00000042')
         * @param {string} evt.danger_level   - 'low' | 'medium' | 'high'
         * @param {string} [evt.title]         - Operation title
         * @param {string[]} [evt.plan]         - Human-readable step descriptions
         */
        _showChoiceList(evt) {
            const self = this;
            const host = typeof globalThis !== 'undefined' ? globalThis : window;
            if (!host.ChatbooChoiceList) { return; }
            host.ChatbooChoiceList.show(evt, {
                t: _t,
                callJson: function (route, params) {
                    return self._callJsonRoute(route, params);
                },
                onAccepted: function (res) {
                    if (res && res.verification_id) {
                        self._showVerificationUI(res);
                    }
                },
            });
        }

        _showVerificationUI(evt) {
            const self = this;
            this._verificationPending = true;
            if (document.getElementById('pns_verif_' + evt.verification_id)) { return; }

            // ── Danger level → colors ──────────────────────────────────────
            const danger = evt.danger_level || 'medium';
            const COLORS = {
                low:    { border: '#43a047', title: '#2e7d32', emoji: '🟢', label: 'Low risk' },
                medium: { border: '#e0a800', title: '#9a6b00', emoji: '🟡', label: 'Medium risk' },
                high:   { border: '#c62828', title: '#b71c1c', emoji: '🔴', label: 'High risk' },
            };
            const dc = COLORS[danger] || COLORS.medium;

            const card = document.createElement('div');
            card.id = 'pns_verif_' + evt.verification_id;
            card.style.cssText = 'position:fixed;right:24px;bottom:24px;z-index:20000;max-width:420px;background:#fff;border:1px solid ' + dc.border + ';border-left:5px solid ' + dc.border + ';border-radius:8px;box-shadow:0 6px 24px rgba(0,0,0,.18);padding:14px 16px;font-family:system-ui,Segoe UI,sans-serif;font-size:13px;color:#222;';

            const title = document.createElement('div');
            title.style.cssText = 'font-weight:700;margin-bottom:6px;color:' + dc.title + ';';
            title.textContent = dc.emoji + ' ' + _t('Confirm AI operation') + (evt.title ? (' \u2014 ' + evt.title) : '');
            card.appendChild(title);

            // Danger badge
            if (danger !== 'low') {
                const badge = document.createElement('span');
                badge.style.cssText = 'display:inline-block;padding:2px 8px;border-radius:3px;font-size:11px;font-weight:600;color:#fff;background:' + dc.border + ';margin-bottom:8px;';
                badge.textContent = dc.emoji + ' ' + _t(dc.label);
                card.appendChild(badge);
            }

            if (evt.plan && evt.plan.length) {
                const ul = document.createElement('ul');
                ul.style.cssText = 'margin:6px 0 10px 0;padding-left:18px;';
                evt.plan.forEach(function (line) {
                    const li = document.createElement('li');
                    li.style.marginBottom = '2px';
                    li.textContent = line;
                    ul.appendChild(li);
                });
                card.appendChild(ul);
            }

            const msg = document.createElement('div');
            msg.style.cssText = 'margin-bottom:10px;color:#555;';
            msg.textContent = _t('This operation will not run until you confirm it.');
            card.appendChild(msg);

            const status = document.createElement('div');
            status.style.cssText = 'margin-top:8px;font-size:12px;';

            const confirmBtn = document.createElement('button');
            confirmBtn.style.cssText = 'background:#2e7d32;color:#fff;border:none;border-radius:5px;padding:6px 14px;cursor:pointer;font-weight:600;';
            const cancelBtn = document.createElement('button');
            cancelBtn.textContent = _t('Cancel');
            cancelBtn.style.cssText = 'background:#eee;color:#333;border:none;border-radius:5px;padding:6px 14px;cursor:pointer;';

            // ── Cooldown for high-danger operations ────────────────────────
            const COOLDOWN_SECS = (danger === 'high') ? 5 : 0;
            if (COOLDOWN_SECS > 0) {
                confirmBtn.disabled = true;
                confirmBtn.style.opacity = '.5';
                let remaining = COOLDOWN_SECS;
                confirmBtn.textContent = _t('Confirm') + ' (' + remaining + 's)';
                const cooldownTimer = setInterval(function () {
                    remaining--;
                    if (remaining <= 0) {
                        clearInterval(cooldownTimer);
                        confirmBtn.disabled = false;
                        confirmBtn.style.opacity = '1';
                        confirmBtn.textContent = _t('Confirm');
                    } else {
                        confirmBtn.textContent = _t('Confirm') + ' (' + remaining + 's)';
                    }
                }, 1000);
            } else {
                confirmBtn.textContent = _t('Confirm');
            }

            const disable = function () {
                confirmBtn.disabled = true; cancelBtn.disabled = true;
                confirmBtn.style.opacity = '.6'; cancelBtn.style.opacity = '.6';
            };

            confirmBtn.addEventListener('click', function () {
                disable();
                status.style.color = '#555';
                status.textContent = _t('Confirming…');
                // Fase A: solo confirm (rápido). Nunca execute en este HTTP.
                self._callJsonRoute(
                    '/pns_ai_mcp/verification/confirm',
                    { verification_id: evt.verification_id },
                    { timeoutMs: 8000 }
                )
                    .then(function (res) {
                        const ok = res && res.success !== false;
                        const busy = res && res.busy;
                        const idem = res && res.idempotent;
                        const err = (res && res.error) || '';
                        self._verificationPending = false;
                        self.state.thinking = false;
                        self.state.disabled = false;
                        if (self._updateSystrayBadge) { self._updateSystrayBadge(); }
                        if (!ok) {
                            status.style.color = busy ? '#9a6b00' : '#c62828';
                            status.textContent = busy
                                ? _t('Already being confirmed in another window…')
                                : (_t('Error: ') + err);
                            confirmBtn.disabled = false;
                            cancelBtn.disabled = false;
                            confirmBtn.style.opacity = '1';
                            cancelBtn.style.opacity = '1';
                            self._finishVerificationOutcome(
                                evt, res || { success: false }, 'confirm');
                            return;
                        }
                        if (idem || (res && res.status === 'executed')) {
                            status.style.color = '#2e7d32';
                            status.textContent = _t('Already executed');
                            setTimeout(function () { card.remove(); }, 2500);
                            self._finishVerificationOutcome(evt, res, 'confirm');
                            return;
                        }
                        status.style.color = '#2e7d32';
                        status.textContent = _t('Confirmed — applying…');
                        return self._callJsonRoute(
                            '/pns_ai_mcp/verification/execute',
                            { verification_id: evt.verification_id },
                            { timeoutMs: 20000 }
                        ).then(function (ex) {
                            const done = ex && ex.success !== false && ex.status === 'executed';
                            status.style.color = '#2e7d32';
                            status.textContent = done
                                ? _t('Operation executed')
                                : _t('Confirmed — apply pending (Approvals if needed)');
                            setTimeout(function () { card.remove(); }, 2500);
                            self._finishVerificationOutcome(evt, ex || res, 'confirm');
                        }).catch(function () {
                            status.style.color = '#2e7d32';
                            status.textContent = _t('Confirmed — apply pending (Approvals if needed)');
                            setTimeout(function () { card.remove(); }, 2500);
                            self._finishVerificationOutcome(evt, res, 'confirm');
                        });
                    })
                    .catch(function (e) {
                        status.style.color = '#c62828';
                        var msg = (e && e.name === 'AbortError')
                            ? _t('Timeout confirming (server busy). Retry Confirm.')
                            : (_t('Error: ') + e);
                        status.textContent = msg;
                        confirmBtn.disabled = false;
                        cancelBtn.disabled = false;
                        confirmBtn.style.opacity = '1';
                        cancelBtn.style.opacity = '1';
                        self._verificationPending = false;
                        self.state.thinking = false;
                        self.state.disabled = false;
                        if (self._updateSystrayBadge) { self._updateSystrayBadge(); }
                        self._finishVerificationOutcome(
                            evt, { success: false, error: String(e) }, 'confirm');
                    });
            });

            cancelBtn.addEventListener('click', function () {
                disable();
                self._callJsonRoute('/pns_ai_mcp/verification/cancel', { verification_id: evt.verification_id })
                    .then(function (res) {
                        status.style.color = '#555';
                        status.textContent = _t('Operation cancelled');
                        setTimeout(function () { card.remove(); }, 2000);
                        self._verificationPending = false;
                        self.state.thinking = false;
                        self.state.disabled = false;
                        if (self._updateSystrayBadge) { self._updateSystrayBadge(); }
                        self._finishVerificationOutcome(evt, res || {}, 'cancel');
                    })
                    .catch(function () {
                        card.remove();
                        self._verificationPending = false;
                        self.state.thinking = false;
                        self.state.disabled = false;
                        if (self._updateSystrayBadge) { self._updateSystrayBadge(); }
                        self._appendVerificationAck(
                            _t('Alright — I cancelled «%s». No changes were applied.')
                                .replace('%s', (evt && evt.title) || _t('the operation'))
                        );
                    });
            });

            const btnRow = document.createElement('div');
            btnRow.style.cssText = 'display:flex;gap:8px;justify-content:flex-end;';
            btnRow.appendChild(cancelBtn);
            btnRow.appendChild(confirmBtn);
            card.appendChild(btnRow);
            card.appendChild(status);
            document.body.appendChild(card);
            var ov = document.getElementById('o_chatboo_persistent_overlay');
            if (!ov || ov.style.display === 'none') {
                try {
                    var _core = require('web.core');
                    if (_core && _core.bus) {
                        _core.bus.trigger('chatboo_auth_cue', { notify: true });
                    }
                } catch (_) {}
            }
        }

        // ══════════════════════════════════════════════════════════════════════
        // 5b. SCREEN FOCUS — artefacto Odoo debajo del overlay
        // ══════════════════════════════════════════════════════════════════════

        _refreshScreenFocus() {
            const SC = window.ChatbooScreenContext;
            if (!SC || !SC.get) {
                this.state.screenFocusLabel = '';
                this.state.screenContextSnapshot = null;
                return null;
            }
            const ctx = SC.get(this.env);
            this.state.screenFocusLabel = SC.formatChipLabel(ctx) || '';
            this.state.screenContextSnapshot =
                SC.hasSendableContext && SC.hasSendableContext(ctx) ? ctx : null;
            return ctx;
        }

        _captureScreenContextForSend() {
            if (!this.state.screenFocusEnabled) {
                return null;
            }
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

        _screenFocusTitle() {
            return this.state.screenFocusEnabled
                ? _t('Screen context active — click to ignore this chat')
                : _t('Screen context off — click to re-enable');
        }

        _ttsTitle() {
            return this.state.ttsEnabled
                ? _t('Click on the chat to play')
                : _t('Enable read-aloud');
        }

        // ══════════════════════════════════════════════════════════════════════
        // 6. CHAT + STREAMING — Core conversation flow
        // ══════════════════════════════════════════════════════════════════════

        /**
         * Stream a chat turn via SSE (Server-Sent Events).
         *
         * Sends the user message + conversation history to /chatboo/stream
         * and processes the streaming response in real time, updating
         * this.state.streamingPreview as chunks arrive.
         *
         * The SSE response contains events of type:
         *   - 'chunk':     text fragment to append to preview
         *   - 'meta':      token usage, model info (saved in _lastStreamMeta)
         *   - 'timing':    TTFT, total duration (saved in _lastStreamTiming)
         *   - 'error':     error message from server
         *   - 'event: safe_plan_pending': triggers _showVerificationUI
         *
         * Important: Uses 'text/plain' Content-Type to avoid Odoo 14's
         * JsonRequest parser (which would break SSE streaming).
         *
         * @param {string} text - User message text
         * @param {Array} historyForApi - Conversation history [{role, content}, ...]
         * @returns {Promise<string>} Accumulated assistant response text
         * @throws {Error} On network failure or server error
         */
        async _streamChat(text, historyForApi, images, files, imageNames) {
            let acc = "";
            this._lastStreamMeta = null;
            this._lastStreamTiming = null;
            const streamState = ChatbooSse.createStreamState();
            const _t0 = (typeof performance !== "undefined" ? performance.now() : Date.now());
            let _tFirst = null;
            const self = this;
            const formatFooter = function (t) {
                var src = t || '';
                if (typeof ChatbooSse !== 'undefined' && ChatbooSse.prepareMarkdownForDisplay) {
                    src = ChatbooSse.prepareMarkdownForDisplay(src).markdown;
                } else if (typeof ChatbooSse !== 'undefined' && ChatbooSse.normalizeGluedMarkdown) {
                    src = ChatbooSse.normalizeGluedMarkdown(src);
                }
                return formatters.formatMarkdown(src) || '';
            };
            // Watchdog de inactividad + cancelación manual. El servidor manda un
            // 'status' por turno y tokens según llegan, así que un silencio total
            // de STREAM_IDLE_MS significa que el proveedor se colgó (o un reinicio
            // dejó el socket a medias): abortamos el fetch para que el turno no se
            // quede en "Thinking…" eterno. El botón de cancelar usa el mismo
            // AbortController (razón 'user'). Ver docs/arquitectura_streaming_sse.md.
            const STREAM_IDLE_MS = 120000;
            const controller = new AbortController();
            this._streamAbort = controller;
            this._streamAbortReason = null;
            this.state.canCancel = true;
            let idleTimer = null;
            const armIdle = function () {
                if (idleTimer) { clearTimeout(idleTimer); }
                idleTimer = setTimeout(function () {
                    self._streamAbortReason = self._streamAbortReason || 'idle';
                    try { controller.abort(); } catch (e) { /* noop */ }
                }, STREAM_IDLE_MS);
            };
            try {
                const screenContext = this._captureScreenContextForSend();
                const payload = {
                    message: text,
                    history: historyForApi || [],
                    session_id: this.state.currentSessionId || null,
                    provider_id: this.state.selectedProviderId || null,
                };
                if (screenContext) {
                    payload.screen_context = screenContext;
                }
                if (images && images.length) {
                    payload.images = images;
                }
                if (imageNames && imageNames.length) {
                    payload.image_names = imageNames;
                }
                if (files && files.length) {
                    payload.files = files;
                }
                const resp = await fetch('/chatboo/stream', {
                    // Odoo 14 enruta por Content-Type: 'application/json' fuerza un
                    // JsonRequest que choca con la ruta type='http' (BadRequest, body
                    // sin SSE). Con text/plain O14 lo trata como http; el controller
                    // lee el body crudo con json.loads, así que el formato no cambia.
                    method: 'POST',
                    headers: { 'Content-Type': 'text/plain;charset=UTF-8' },
                    credentials: 'same-origin',
                    signal: controller.signal,
                    body: JSON.stringify(payload),
                });
                if (!resp.ok || !resp.body) {
                    throw new Error('HTTP ' + resp.status);
                }
                const reader = resp.body.getReader();
                const decoder = new TextDecoder('utf-8');
                let buffer = "";
                armIdle();
                while (true) {
                    const { done, value } = await reader.read();
                    if (done) break;
                    armIdle();
                    buffer += decoder.decode(value, { stream: true });
                    let sep;
                    while ((sep = buffer.indexOf('\n\n')) !== -1) {
                        const rawEvent = buffer.slice(0, sep);
                        buffer = buffer.slice(sep + 2);
                        const evt = ChatbooSse.parseSseBlock(rawEvent);
                        if (!evt) continue;
                        if (evt.event === 'token' && evt.content) {
                            if (_tFirst === null) {
                                _tFirst = (typeof performance !== "undefined" ? performance.now() : Date.now());
                            }
                            ChatbooSse.applyToken(streamState, evt.content, formatFooter);
                            acc = streamState.acc;
                            const preview = this._formatContent(acc);
                            if (ChatbooSse.hasVisibleContent(acc)) {
                                this.state.streamingPreview = preview;
                            }
                            this.scrollToBottom();
                        } else if (evt.event === 'replace' && evt.content) {
                            if (_tFirst === null) {
                                _tFirst = (typeof performance !== "undefined" ? performance.now() : Date.now());
                            }
                            ChatbooSse.applyReplace(streamState, evt.content);
                            acc = streamState.acc;
                            const preview = this._formatContent(acc);
                            if (ChatbooSse.hasVisibleContent(acc)) {
                                this.state.streamingPreview = preview;
                            }
                            this.scrollToBottom();
                        } else if (evt.event === 'status' && evt.message) {
                            this.state.statusLabel = evt.message;
                        } else if (evt.event === 'meta') {
                            // Auto-promoción: el servidor nos dice qué sesión/job creó/usó
                            // el worker para poder recargarla como fuente de verdad, y el
                            // request_id para ignorar el aviso de bus de ESTE turno.
                            this._lastStreamSessionId = evt.session_id || this._lastStreamSessionId;
                            this._lastStreamRequestId = evt.request_id || null;
                        } else if (evt.event === 'done') {
                            // Metadatos del cierre: modelo/proveedor que respondió y
                            // tokens reales (contexto usado). Los consume el llamador.
                            this._lastStreamMeta = evt;
                            if (evt.painter === 'painter-free'
                                    || evt.painter === 'painter-local') {
                                this.state.effectiveFormattingMode = evt.painter;
                            }
                        } else if (evt.event === 'choice' && evt.choice_id) {
                            this._showChoiceList(evt);
                        } else if (evt.event === 'verification' && evt.verification_id) {
                            // Caja B: la IA ha propuesto una escritura. Mostrar la
                            // confirmación inline (no depende del bus/toast).
                            this._showVerificationUI(evt);
                        } else if (evt.event === 'error') {
                            // Server-side error pushed via SSE — mark as error
                            // so the badge shows the exclamation icon on red.
                            this._lastSendWasError = true;
                            // Also render the error content in the chat bubble
                            if (evt.content) {
                                if (_tFirst === null) {
                                    _tFirst = (typeof performance !== 'undefined' ? performance.now() : Date.now());
                                }
                                acc += evt.content;
                                const preview = this._formatContent(acc);
                                if (preview && String(preview).replace(/<[^>]*>/g, '').trim()) {
                                    this.state.streamingPreview = preview;
                                }
                                this.scrollToBottom();
                            }
                        }
                    }
                }
                const _tEnd = (typeof performance !== "undefined" ? performance.now() : Date.now());
                this._lastStreamTiming = {
                    ttftMs: _tFirst !== null ? Math.round(_tFirst - _t0) : null,
                    genMs: _tFirst !== null ? Math.round(_tEnd - _tFirst) : null,
                };
                return acc;
            } catch (err) {
                // Abort (cancelación manual o watchdog de inactividad): devolvemos
                // lo acumulado (si hay) y marcamos el motivo para que _sendMessage
                // pinte un aviso limpio en vez de un error rojo de "comunicación".
                if (err && (err.name === 'AbortError' || this._streamAbortReason)) {
                    const reason = this._streamAbortReason || 'user';
                    const e = new Error(reason === 'idle'
                        ? _t('No response from the provider (possible hang). Please try again.')
                        : _t('Generation cancelled.'));
                    e.__aborted = reason;
                    e.__partial = acc;
                    throw e;
                }
                throw err;
            } finally {
                if (idleTimer) { clearTimeout(idleTimer); }
                this._streamAbort = null;
                this.state.canCancel = false;
                this.state.streamingPreview = "";
                this.state.statusLabel = "";
            }
        }

        /**
         * Cancela el turno en curso (botón de la burbuja "Thinking…").
         * Aborta el SSE local y pide al worker que pare el job en servidor.
         */
        _cancelStream() {
            const rid = this._lastStreamRequestId || this._resumeReqId || null;
            if (!this._streamAbort && !rid && !this.state.currentSessionId) {
                return;
            }
            if (!confirm(_t(
                'Cancel the response in progress? Any text received so far may be kept in the chat.'
            ))) {
                return;
            }
            this._streamAbortReason = 'user';
            if (this._streamAbort) {
                try { this._streamAbort.abort(); } catch (e) { /* noop */ }
            }
            const sid = this.state.currentSessionId || null;
            const params = {};
            if (rid) { params.request_id = rid; }
            if (sid) { params.session_id = sid; }
            if (rid || sid) {
                this.props.rpc({ route: '/chatboo/async/cancel', params: params }).catch(function () {});
            }
            this._resumeReqId = null;
            if (!this._sseOwnsThinking) {
                this.state.thinking = false;
                this.state.canCancel = false;
                this.state.disabled = false;
            }
        }

        _verificationFollowupNote(evt, res, action) {
            if (res && res.followup_message) {
                return res.followup_message;
            }
            return this._buildVerificationResultNote(evt, res, action);
        }

        /**
         * Local chat ack after Confirm/Cancel of CRUD writes (no LLM round-trip).
         */
        _appendVerificationAck(text, records) {
            if (!text) { return; }
            const start = new Date();
            const formatted = this._formatContent(text);
            const last = [...(this.messages || [])].reverse().find(
                (m) => m && m.role === 'assistant' && m.backend_history
            );
            const prev = last && last.backend_history ? last.backend_history.slice() : [];
            const history = prev.concat([{ role: 'assistant', content: text }]);
            this.messages.push({
                role: 'assistant',
                content: formatted,
                original_content: text,
                formatted_html: formatted,
                timestamp: this._formatTimestamp(start, new Date()),
                local_ack: true,
                verification_ack: true,
                offtopic: false,
                records: records || [],
                backend_history: history,
                model_details: { model: 'Safe Plan', provider: 'local' },
                context_info: this._makeContextInfo(null, 0, { provider: 'local' }),
            });
            this.scrollToBottom();
            if (this.state.currentSessionId) {
                this._saveCurrentSession().catch(function (err) {
                    console.error('Error saving verification ack:', err);
                });
            }
        }

        /**
         * CRUD → user_ack_message in chat. fetch_url → LLM follow-up turn.
         */
        _finishVerificationOutcome(evt, res, action) {
            const ack = res && res.user_ack_message;
            const needsLlm = res && res.needs_llm_followup;
            if (ack) {
                this._appendVerificationAck(ack, (res && res.records) || []);
            }
            if (needsLlm) {
                this._runResultTurn(this._verificationFollowupNote(evt, res, action));
            } else if (!ack && action !== 'cancel') {
                this._runResultTurn(this._verificationFollowupNote(
                    evt, res || { success: false }, action));
            }
        }

        /**
         * Build a hidden note for the LLM after Safe Plan verification.
         * Used only when needs_llm_followup (fetch_url). CRUD uses local ack.
         * @param {Object} evt - The original verification event.
         * @param {Object} res - Server response from the verification endpoint.
         * @param {string} action - User action ('approve' or 'reject').
         * @returns {string} HTML string for the result note.
         */
        _buildVerificationResultNote(evt, res, action) {
            // Texto (turno de usuario, no visible) que recibe la IA para que informe del
            // resultado de la escritura en el idioma del usuario.
            // GUARD: este turno NO es una petición de escritura. Hay que impedir que el
            // modelo "ejecute" ejemplos del prompt o re-proponga operaciones.
            const guard = ' IMPORTANTE: este es solo un aviso de resultado, NO una petición. ' +
                'NO llames a ninguna herramienta y NO propongas ni crees ninguna operación nueva ' +
                '(ignora cualquier ejemplo del prompt); limítate a redactar el mensaje al usuario.';
            const title = (evt && evt.title) || _t('the operation');
            if (action === 'cancel') {
                return '[Resultado del sistema] El usuario ha CANCELADO la operación de escritura «' + title +
                    '». No se ha ejecutado ningún cambio. Confírmaselo de forma breve y natural en su idioma.' + guard;
            }
            const ok = res && res.success !== false;
            if (ok) {
                let det = '';
                try { det = res && res.results ? JSON.stringify(res.results) : ''; } catch (e) { det = ''; }
                return '[Resultado del sistema] El usuario ha CONFIRMADO la operación «' + title +
                    '» y se ha ejecutado CORRECTAMENTE.' + (det ? (' Resultado: ' + det + '.') : '') +
                    ' Informa al usuario del éxito de forma breve y natural en su idioma, mencionando lo que se ha creado o modificado.' + guard;
            }
            return '[Resultado del sistema] El usuario ha CONFIRMADO la operación «' + title +
                ' but it FAILED to run. Error: ' + ((res && res.error) || _t('unknown')) +
                '. Discúlpate brevemente y explica el problema en el idioma del usuario.' + guard;
        }

        /**
         * Build assistant message fields from the last SSE stream (_lastStreamMeta).
         */
        _buildAssistantPayloadFromStream(txt, startTime, endTime) {
            const __meta = this._lastStreamMeta || {};
            const __timing = this._lastStreamTiming || {};
            let __speedTps = 0;
            let __promptSpeedTps = 0;
            if (__meta.usage) {
                const __ct = __meta.usage.completion_tokens || 0;
                const __pt = __meta.usage.prompt_tokens || 0;
                if (__ct && __timing.genMs > 0) {
                    __speedTps = __ct / (__timing.genMs / 1000);
                }
                if (__pt && __timing.ttftMs > 0) {
                    __promptSpeedTps = __pt / (__timing.ttftMs / 1000);
                }
            }
            const formatted = this._formatContent(txt || '');
            const localAck = !!__meta.local_ack;
            const contextInfoData = localAck ? null : this._makeContextInfo(
                __meta.usage, __meta.context_limit, {
                    speedTps: __speedTps,
                    promptSpeedTps: __promptSpeedTps,
                    provider: __meta.provider || '',
                    currency: __meta.display_currency || '',
                    turnCode: __meta.correlation_id || '',
                },
            );
            return {
                role: 'assistant',
                content: formatted,
                original_content: txt || '',
                formatted_html: formatted,
                timestamp: this._formatTimestamp(startTime, endTime),
                usage: localAck ? null : (__meta.usage || null),
                context_limit: localAck ? null : (__meta.context_limit || null),
                correlation_id: localAck ? '' : (__meta.correlation_id || ''),
                user_prompt: __meta.user_prompt || this._lastUserPromptText(),
                local_ack: localAck,
                offtopic: localAck,
                model_details: (__meta.model || __meta.provider)
                    ? {
                        model: __meta.model || '',
                        provider: __meta.provider || '',
                        painter: __meta.painter || '',
                        display_currency: __meta.display_currency || '',
                    }
                    : null,
                sources: __meta.sources || [],
                records: __meta.records || [],
                context_info: contextInfoData,
                speed_tps: localAck ? 0 : __speedTps,
                prompt_speed_tps: localAck ? 0 : __promptSpeedTps,
                backend_history: localAck ? null : (__meta.history || null),
            };
        }

        /**
         * Execute a follow-up turn after a verification action (approve/reject).
         * Sends the verification result note as context to the LLM so it can
         * acknowledge the outcome and continue the conversation.
         * @param {string} noteText - The verification result note to send.
         * @returns {Promise<void>}
         */
        async _runResultTurn(noteText) {
            // Opción B: lanza un turno de la IA con el resultado de una escritura
            // confirmada/cancelada. No añade burbuja de usuario; solo la respuesta.
            if (this.state.thinking) { return; }
            const startTime = new Date();

            let historyForApi = [];
            const lastAssistantWithHistory = [...this.messages].reverse().find(m => m.role === 'assistant' && m.backend_history);
            if (lastAssistantWithHistory && lastAssistantWithHistory.backend_history) {
                historyForApi = [...lastAssistantWithHistory.backend_history];
            } else {
                historyForApi = this._messagesForModel(this.messages);
            }

            // Dueño local del spinner: el bus no debe apagarlo mientras dura el SSE.
            this._sseOwnsThinking = true;
            this.state.thinking = true;
            this.state.canCancel = true;
            this.state.effectiveFormattingMode = null;
            this.state.statusLabel = '';
            this.scrollToBottom();
            try {
                const txt = await this._streamChat(noteText, historyForApi);
                this.messages.push(
                    this._buildAssistantPayloadFromStream(txt, startTime, new Date()),
                );
                this._maybeSpeakLastAssistant();
            } catch (error) {
                this._lastSendWasError = true;
                this.messages.push({
                    role: "assistant",
                    content: `<span class="text-danger">Communication Error: ${error.message || 'Unknown'}</span>`,
                    timestamp: this._formatTimestamp(startTime, new Date()),
                    context_info: this._makeContextInfo(null, 0, {}),
                });
            } finally {
                this._sseOwnsThinking = false;
                this.state.thinking = false;
                this.state.canCancel = false;
                this.scrollToBottom();
                if (this.state.currentSessionId) {
                    this._saveCurrentSession().catch(err => console.error('Error auto-saving session:', err));
                }
                // This IS the final round (post-verification), so show the badge.
                this._verificationPending = false;
                this._updateSystrayBadge();
                this._lastSendWasError = false;
            }
        }

        /**
         * Main entry point for sending a user message.
         *
         * Complete flow:
         *   1. Check for built-in commands (/skills)
         *   2. Add message to input history (readline-style, max 50 entries)
         *   3. Push user message to this.messages
         *   4. Build conversation history for API (last N messages)
         *   5. Call _streamChat() for SSE streaming
         *   6. On success: push assistant message, attach context_info + timing
         *   7. Auto-save session to backend
         *   8. On error: push error message to chat
         *
         * The method also handles:
         *   - Token counter rendering (context_info bar)
         *   - Auto-scroll to bottom after each message
         */
        async _sendMessage() {
            if (this.state.disabled) return;
            const text = this.state.currentInput.trim();
            const images = (this.state.pendingImages || []).slice();
            const imageNames = (this.state.pendingImageNames || []).slice();
            const files = (this.state.pendingFiles || []).slice();
            if (!text && !images.length && !files.length) return;

            // Comandos built-in (/skills, /create-skill): se resuelven
            // en el cliente, no se envían como turno al LLM. Solo aplican a texto puro.
            if (!images.length && !files.length) {
                const builtin = this._matchBuiltinCommand(text);
                if (builtin) {
                    this.state.currentInput = '';
                    this._syncInputEl();
                    await this._runBuiltinCommand(builtin);
                    return;
                }
            }

            const startTime = new Date(); // Save start time for duration calculation

            // Add to input history (like readline)
            if (text && (this.inputHistory.length === 0 || this.inputHistory[this.inputHistory.length - 1] !== text)) {
                this.inputHistory.push(text);
                // Keep only last 50 entries
                if (this.inputHistory.length > 50) {
                    this.inputHistory.shift();
                }
            }
            this.historyIndex = -1;
            this.currentInputBeforeHistory = "";

            // 1. Add User Message (no duration for user messages, just timestamp).
            // Las imágenes (si las hay) se muestran en la burbuja; viajan solo en
            // este turno hacia el modelo de visión, no entran en el historial.
            const userTimestamp = this._formatTimestamp(startTime, startTime); // Duration = 0 for user messages
            const _textHtml = text
                ? `<div style="font-family: 'Courier New', Courier, monospace; font-size: 1.25em; line-height: 1.4;">${text
                    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
                    .replace(/\n/g, "<br/>")}</div>`
                : '';
            // images/files como campos (template owl1); el worker los sustituye
            // por URLs de ir.attachment en meta.user_images / user_files.
            this.messages.push({
                role: "user",
                content: _textHtml,
                images: images.map((u, i) => ({ url: u, name: imageNames[i] || null })),
                files: files.map((f) => ({ name: f.name, mimetype: f.mimetype || null, url: null })),
                timestamp: userTimestamp.replace(' (0 segundos)', ''), // Remove duration for user messages
                startTime: startTime, // Store for duration calculation in assistant response
                usage: null // No usage for user messages
            });

            // Clean history: attempt to use exact backend history if available to preserve tool traces
            let historyForApi = [];
            const lastAssistantWithHistory = [...this.messages].reverse().find(m => m.role === 'assistant' && m.backend_history);

            if (lastAssistantWithHistory && lastAssistantWithHistory.backend_history) {
                historyForApi = [...lastAssistantWithHistory.backend_history];
            } else {
                // Fallback: extract plain text from HTML content.
                // slice(0, -1): excluimos el turno actual (que acabamos de
                // empujar a this.messages). El motor lo añade él mismo —como
                // mensaje MULTIMODAL si hay imágenes—, así que si lo dejáramos
                // aquí iría DUPLICADO y en texto plano (sin imagen). Con visión
                // eso hace que el modelo vea primero una pregunta "sin imagen" y
                // se niegue a analizarla. owl2 ya lo excluye (excludeTail:1).
                historyForApi = this._messagesForModel(this.messages, 1);
            }
            // El turno actual NO se añade al history: el motor lo incorpora como
            // mensaje de usuario (multimodal cuando hay imágenes). Duplicarlo aquí
            // metía una copia en texto plano que "eclipsaba" la imagen y disparaba
            // la negativa del modelo en O14 (backend_history llega hasta el turno
            // anterior; el actual lo pone el motor).

            this.state.currentInput = "";
            this.state.promptMultiline = false;
            this.state.promptCollapsed = false;
            this.state.pendingImages = [];
            this.state.pendingImageNames = [];
            this.state.pendingFiles = [];
            this._syncInputEl();  // vaciar el <textarea> en el DOM (no tiene binding de value)
            this._syncPromptHeight();
            this._resetInputPlaceholder();
            this.state.slashOpen = false;
            this.state.slashItems = [];
            this._syncSlashMenu();
            // Dueño local del spinner: el bus (async_done del turno anterior) NO
            // debe apagar thinking mientras dura este SSE.
            this._sseOwnsThinking = true;
            this.state.thinking = true;
            this.state.canCancel = true;
            this.state.effectiveFormattingMode = null;
            this.state.statusLabel = '';
            this.scrollToBottom();

            try {
                // 2. Call Backend (agnostic - only pass session_id)
                const params = {
                    message: text,
                    conversation_history: historyForApi
                };

                // Pass session_id if available (backend will handle conversation_id automatically)
                if (this.state.currentSessionId) {
                    params.session_id = this.state.currentSessionId;
                }

                // F1: transporte SSE (sustituye al JSON-RPC /chatboo/send).
                const __sseText = await this._streamChat(text, historyForApi, images.length ? images : null, files.length ? files : null, imageNames.length ? imageNames : null);
                const __meta = this._lastStreamMeta || {};
                const __timing = this._lastStreamTiming || {};
                // Velocidad real medida en cliente: decode = completion_tokens / (fin − 1er token);
                // prefill ≈ prompt_tokens / time-to-first-token. Si falta el usage, queda en 0.
                let __speedTps = 0;
                let __promptSpeedTps = 0;
                if (__meta.usage) {
                    const __ct = __meta.usage.completion_tokens || 0;
                    const __pt = __meta.usage.prompt_tokens || 0;
                    if (__ct && __timing.genMs > 0) {
                        __speedTps = __ct / (__timing.genMs / 1000);
                    }
                    if (__pt && __timing.ttftMs > 0) {
                        __promptSpeedTps = __pt / (__timing.ttftMs / 1000);
                    }
                }
                if (__meta.local_ack) {
                    this._markLastUserOfftopic();
                }
                const result = {
                    content: (typeof __meta.assistant_content === 'string')
                        ? __meta.assistant_content
                        : __sseText,
                    usage: __meta.local_ack ? null : (__meta.usage || null),
                    context_limit: __meta.local_ack ? null : (__meta.context_limit || null),
                    correlation_id: __meta.local_ack ? '' : (__meta.correlation_id || ''),
                    local_ack: !!__meta.local_ack,
                    speed_tps: __speedTps,
                    prompt_speed_tps: __promptSpeedTps,
                    model_details: (__meta.model || __meta.provider)
                        ? {
                            model: __meta.model || '',
                            provider: __meta.provider || '',
                            display_currency: __meta.display_currency || '',
                        }
                        : null,
                    sources: __meta.sources || [],
                    records: __meta.records || [],
                    history: null,
                };

                // Auto-promoción: si el worker ya persistió el turno en la sesión
                // (fuente de verdad), recargamos desde BD en vez de autoensamblar
                // aquí. Así la respuesta es idéntica se haya visto en vivo o no, y
                // sobrevive a un F5 sin duplicar mensajes.
                // Parche en vivo: sustituir base64 / chips sin URL por los del worker
                // (aunque luego recarguemos por authored).
                if ((__meta.user_images && __meta.user_images.length)
                        || (__meta.user_files && __meta.user_files.length)) {
                    for (let i = this.messages.length - 1; i >= 0; i--) {
                        const m = this.messages[i];
                        if (m.role === 'user') {
                            if (__meta.user_images && __meta.user_images.length) {
                                m.images = __meta.user_images;
                            }
                            if (__meta.user_files && __meta.user_files.length) {
                                m.files = __meta.user_files;
                            }
                            break;
                        }
                    }
                }
                if (__meta.authored) {
                    const sid = __meta.session_id || this._lastStreamSessionId || this.state.currentSessionId;
                    if (sid) {
                        // El worker ya persistió las imágenes del turno como
                        // ir.attachment; al recargar, _loadSession las deja en
                        // msg.images / msg.files (URLs). No hace falta recordarlas aquí.
                        this.state.currentSessionId = sid;
                        await this._loadSession(sid);
                        this._maybeSpeakLastAssistant();
                    }
                    // Este turno se ha visto en vivo aquí: recordamos su request_id
                    // para que el aviso de bus no lo recargue por encima y borre el
                    // contenido al cambiar de ventana.
                    this._lastLiveRequestId = this._lastStreamRequestId || null;
                    this._lastSendWasError = !!__meta.is_error;
                    this._skipTurnSave = true;  // el worker ya guardó; no re-guardar
                    return;  // el bloque finally hace badge + foco
                }

                // 3. Add Assistant Response
                const endTime = new Date(); // End time for duration calculation
                const timestamp = this._formatTimestamp(startTime, endTime);

                if (result.error) {
                    this._lastSendWasError = true;
                    this.messages.push({
                        role: "assistant",
                        content: `<span class="text-danger">Error: ${result.error}</span>`,
                        timestamp: timestamp,
                    });
                } else if (result.__refresh_session__) {
                    // DIRECT PUSH RECEIVED
                    // Backend has pushed data to DB and signaled us to reload.
                    // We just need to reload the session to see the new message.
                    await this._loadSession(this.state.currentSessionId);
                    this._maybeSpeakLastAssistant();
                    // The new message is already in DB, so _loadSession fetched it.
                    // We don't need to push anything manually here.

                } else {
                    // Store original content (plain text) for copy without formatting
                    let originalContent = result.content || '';

                    // Si el contenido es JSON, formatearlo con saltos de línea entre elementos
                    try {
                        const parsed = JSON.parse(originalContent);
                        if (parsed && typeof parsed === 'object') {
                            originalContent = this._formatJsonWithLineBreaks(parsed);
                        }
                    } catch (e) {
                        // No es JSON válido, mantener original
                    }

                    const formattedHtml = this._formatContent(result.content || '');
                    const mainContent = formattedHtml;
                    const lastUserMsg = this.messages.length > 0 ? this.messages[this.messages.length - 1] : null;
                    const query = (lastUserMsg && lastUserMsg.role === 'user') ? (lastUserMsg.content || '') : '';
                    let hasRawJson = false;
                    let rawSaveData = null;
                    try {
                        const parsed = JSON.parse(result.content || '{}');
                        if (parsed && typeof parsed === 'object' && !parsed.formatted_text) {
                            const hasData = Array.isArray(parsed.data) || (Array.isArray(parsed) && parsed[0] && typeof parsed[0] === 'object');
                            if (hasData) {
                                hasRawJson = true;
                                rawSaveData = { json: result.content, query: query };
                            }
                        }
                    } catch (e) { }

                    const localAck = !!result.local_ack;
                    const contextInfoData = localAck ? null : this._makeContextInfo(
                        result.usage, result.context_limit, {
                            speedTps: result.speed_tps || 0,
                            promptSpeedTps: result.prompt_speed_tps || 0,
                            provider: (result.model_details && result.model_details.provider) || '',
                            currency: (result.model_details && result.model_details.display_currency) || '',
                            turnCode: result.correlation_id || '',
                        },
                    );

                    // Store separately: main content goes in 'content', context info as structured data
                    // Also store original content and formatted HTML for copy buttons
                    this.messages.push({
                        role: "assistant",
                        content: mainContent,
                        original_content: originalContent,
                        formatted_html: formattedHtml,
                        context_info: contextInfoData,
                        timestamp: timestamp,
                        usage: localAck ? null : (result.usage || null),
                        context_limit: localAck ? null : (result.context_limit || null),
                        correlation_id: localAck ? '' : (result.correlation_id || ''),
                        user_prompt: text || '',
                        local_ack: localAck,
                        offtopic: localAck,
                        model_details: result.model_details || null,
                        sources: result.sources || [],
                        records: result.records || [],
                        speed_tps: result.speed_tps || 0,
                        prompt_speed_tps: result.prompt_speed_tps || 0,
                        has_raw_json: hasRawJson,
                        raw_save_data: rawSaveData,
                        backend_history: result.history || null,
                        files: __meta.assistant_files || result.assistant_files || [],
                        clip_data: __meta.clip_data || result.clip_data || null,
                    });
                    this._maybeSpeakLastAssistant();
                    this._fulfillPendingExports(this.messages[this.messages.length - 1]);

                    // conversation_id is managed automatically by backend (agnostic)
                    // Backend will save it to session if provider is Router

                    // Crea la sesión si es el primer mensaje. El guardado de una
                    // sesión EXISTENTE lo hace el bloque finally: así solo se lanza
                    // UN save por turno y no dos escrituras concurrentes sobre la
                    // misma fila chatboo.session (evita SERIALIZATION_FAILURE).
                    if (!this.state.currentSessionId) {
                        // Create new session automatically (first message), then save.
                        this._createNewSession(false).then(() => { // DO NOT clear UI
                            this._saveCurrentSession().catch(err => {
                                console.warn('Auto-save after create failed:', err);
                            });
                        }).catch(err => {
                            console.warn('Auto-create session failed:', err);
                        });
                    }

                    // Context info is now rendered reactively with t-on-click in template
                }

            } catch (error) {
                console.error(error);
                const errorTime = new Date();
                if (error && error.__aborted) {
                    // Cancelación manual o watchdog: aviso sobrio, no error rojo.
                    const partial = (error.__partial || '').trim();
                    const icon = error.__aborted === 'user' ? '⏹' : '⏱';
                    const note = `<span class="text-muted">${icon} ${error.message}</span>`;
                    this.messages.push({
                        role: "assistant",
                        content: partial ? (this._formatContent(partial) + '<br/>' + note) : note,
                        timestamp: this._formatTimestamp(startTime, errorTime),
                        context_info: this._makeContextInfo(null, 0, {}),
                    });
                    this._lastSendWasError = error.__aborted !== 'user';
                } else {
                    this.messages.push({
                        role: "assistant",
                        content: `<span class="text-danger">Communication Error: ${error.message || 'Unknown'}</span>`,
                        timestamp: this._formatTimestamp(startTime, errorTime),
                        context_info: this._makeContextInfo(null, 0, {}),
                    });
                    this._lastSendWasError = true;
                }
            } finally {
                this._sseOwnsThinking = false;
                this.state.thinking = false;
                this.state.canCancel = false;
                this.scrollToBottom();

                // Auto-save session after sending message.
                // Si el worker asíncrono ya persistió el turno, NO re-guardamos
                // (evita sobrescribir la sesión y duplicar mensajes).
                if (this.state.currentSessionId && !this._skipTurnSave) {
                    // Save asynchronously (don't block UI)
                    this._saveCurrentSession().catch(err => console.error('Error auto-saving session:', err));
                }
                this._skipTurnSave = false;

                // Only show badge if this is the FINAL round.
                // If a safe_plan verification is pending, _runResultTurn will
                // fire the badge when the user confirms/cancels and the AI
                // finishes its follow-up response.
                if (!this._verificationPending) {
                    this._updateSystrayBadge();
                }
                this._lastSendWasError = false;

                // Focus chat input after render completes (no setTimeout)
                requestAnimationFrame(() => {
                    if (this.chatInputRef && this.chatInputRef.el) {
                        this.chatInputRef.el.focus();
                    }
                });
            }
        }


        /**
         * Update the systray badge after a conversation turn completes.
         *
         * OWL1 (O14): emits 'chatboo_response_ready' via core.bus → the systray
         * WIDGET handles badge display using this.el.querySelector + native
         * Odoo/BS4 classes (o_notification_counter badge badge-pill).
         *
         * OWL2 (O17+): direct DOM manipulation as fallback.
         */
        _updateSystrayBadge() {
            var _isError = this._lastSendWasError;
            // OWL1: signal the systray widget via core.bus
            try {
                var _core = require('web.core');
                if (_core && _core.bus) {
                    _core.bus.trigger('chatboo_response_ready', {
                        isError: _isError
                    });
                    return; // widget handles the rest
                }
            } catch (_) {}
            // OWL2 fallback: direct DOM
            var _ov = document.getElementById('o_chatboo_persistent_overlay');
            var _overlayHidden = !_ov || _ov.style.display === 'none';
            var _badge = document.querySelector('.o_chatboo_badge');
            if (!_badge) return;
            if (_isError || _overlayHidden) {
                if (_isError) {
                    _badge.innerHTML = '<i class="fa fa-exclamation" style="font-weight:bold;"/>';
                    _badge.classList.add('bg-danger');
                } else {
                    _badge.innerHTML = '<i class="fa fa-bell-o"/>';
                    _badge.classList.remove('bg-danger');
                }
                _badge.style.display = '';
                try {
                    localStorage.setItem('chatboo_unread', _isError ? 'error' : '1');
                } catch (_) {}
            }
        }

        // ──────────── Slash commands (skills) ────────────

        // ══════════════════════════════════════════════════════════════════════
        // 7. SLASH COMMANDS — / menu, skills, built-in commands
        // ══════════════════════════════════════════════════════════════════════

        /** Remove the slash-command suggestion menu from the DOM. */
        _removeSlashMenu() {
            if (this._slashMenuEl && this._slashMenuEl.parentNode) {
                this._slashMenuEl.parentNode.removeChild(this._slashMenuEl);
            }
            this._slashMenuEl = null;
            // Safety: orphan body menus after hide/toggle must never linger.
            const orphan = document.getElementById('o_chatboo_slash_menu');
            if (orphan && orphan.parentNode) {
                orphan.parentNode.removeChild(orphan);
            }
        }

        /**
         * Close slash UI fully (state + body-mounted menu).
         * Call when Chatboo overlay is hidden — the menu lives on document.body,
         * so display:none on the overlay alone leaves it floating over the ERP.
         */
        _closeSlashUi() {
            this.state.slashOpen = false;
            this.state.slashItems = [];
            this.state.slashMode = 'commands';
            this._removeSlashMenu();
        }

        /**
         * Synchronize the slash-command menu position and visibility with the
         * current input caret position. Renders the filtered suggestion list.
         */
        _syncSlashMenu() {
            // OWL1: menú en document.body (evita clipping/recorte del layout absoluto).
            if (!this.state.slashOpen || !this.state.slashItems.length) {
                this._removeSlashMenu();
                return;
            }
            const input = this.chatInputRef && this.chatInputRef.el;
            if (!input) {
                return;
            }
            if (!this._slashMenuEl) {
                const menu = document.createElement('div');
                menu.id = 'o_chatboo_slash_menu';
                menu.className = 'o_chatboo_slash dropdown-menu show p-1';
                menu.style.cssText = [
                    'position:fixed',
                    'z-index:1060',
                    'display:block',
                    'overflow-x:hidden',
                    'overflow-y:auto',
                    'overscroll-behavior:contain',
                    'box-shadow:0 4px 12px rgba(0,0,0,.15)',
                ].join(';');
                menu.addEventListener('mousedown', (ev) => {
                    const btn = ev.target.closest('button[data-slash-code]');
                    if (!btn) {
                        return;
                    }
                    ev.preventDefault();
                    const code = btn.getAttribute('data-slash-code');
                    const item = this.state.slashItems.find((sk) => sk.code === code);
                    if (item) {
                        this._applySlashSelection(item);
                    }
                });
                document.body.appendChild(menu);
                this._slashMenuEl = menu;
            }
            const rect = input.getBoundingClientRect();
            // Grow upward from the input; cap by free viewport space so scroll works.
            const spaceAbove = Math.max(120, Math.floor(rect.top - 12));
            const rowH = 36;
            const maxH = Math.min(spaceAbove, Math.floor(window.innerHeight * 0.6), 448);
            const snapped = Math.max(rowH, Math.floor(maxH / rowH) * rowH) + 8;
            this._slashMenuEl.style.left = rect.left + 'px';
            this._slashMenuEl.style.width = rect.width + 'px';
            this._slashMenuEl.style.top = 'auto';
            this._slashMenuEl.style.bottom = (window.innerHeight - rect.top + 6) + 'px';
            this._slashMenuEl.style.maxHeight = snapped + 'px';

            const items = this.state.slashItems;
            const idx = this.state.slashIndex;
            let html = '';
            for (let i = 0; i < items.length; i++) {
                const sk = items[i];
                const active = i === idx ? ' active' : '';
                const descClass = i === idx ? '' : ' text-muted';
                let badge = '';
                if (sk.kind === 'builtin') {
                    badge = '<span class="badge badge-secondary ml-1" style="font-size:.7em;">command</span>';
                } else if (sk.badgeLabel) {
                    const badgeClass = sk.mine ? 'badge-info o_chatboo_skill_mine' : 'badge-secondary';
                    badge = '<span class="badge ' + badgeClass + ' ml-1" style="font-size:.7em;">'
                        + this._escapeHtml(sk.badgeLabel) + '</span>';
                }
                const check = '<span class="o_chatboo_slash_check" aria-hidden="true"><i class="fa fa-check"></i></span>';
                html += '<button type="button" class="dropdown-item rounded' + active + '" data-slash-code="' + this._escapeHtml(sk.code) + '">'
                    + check
                    + '<span class="font-weight-bold">/' + this._escapeHtml(sk.code) + '</span>'
                    + badge
                    + '<small class="ml-1 o_chatboo_slash_desc' + descClass + '">' + this._escapeHtml(sk.description || '') + '</small>'
                    + '</button>';
            }
            this._slashMenuEl.innerHTML = html;
            // Keep the highlighted row in view when navigating with arrows.
            const activeBtn = this._slashMenuEl.querySelector('.dropdown-item.active');
            if (activeBtn && activeBtn.scrollIntoView) {
                activeBtn.scrollIntoView({ block: 'nearest' });
            }
        }

        /**
         * Synchronize the textarea value with state (OWL1 has no reliable t-att-value).
         * Also refreshes multiline height.
         */
        _syncInputEl() {
            // OWL 1: t-att-value no siempre actualiza el DOM al cambiar state desde JS.
            if (this.chatInputRef && this.chatInputRef.el) {
                this.chatInputRef.el.value = this.state.currentInput || '';
            }
            this._syncPromptHeight();
        }

        _promptNewlineCount(text) {
            return String(text || '').split('\n').length;
        }

        /**
         * Vertical offset of the caret inside a wrapping textarea (mirror div).
         * History ArrowUp/Down only on first/last *visual* line (soft wrap too).
         */
        _textareaCaretTop(el, position) {
            if (!el || typeof position !== 'number') {
                return 0;
            }
            const style = window.getComputedStyle(el);
            const mirror = document.createElement('div');
            const props = [
                'boxSizing', 'width', 'fontSize', 'fontFamily', 'fontWeight',
                'fontStyle', 'letterSpacing', 'textTransform', 'wordSpacing',
                'textIndent', 'paddingTop', 'paddingRight', 'paddingBottom',
                'paddingLeft', 'borderTopWidth', 'borderRightWidth',
                'borderBottomWidth', 'borderLeftWidth', 'lineHeight',
                'whiteSpace', 'wordWrap', 'wordBreak', 'overflowWrap',
                'tabSize',
            ];
            mirror.style.cssText =
                'position:absolute;top:0;left:-9999px;visibility:hidden;'
                + 'white-space:pre-wrap;word-wrap:break-word;overflow-wrap:break-word;';
            for (let i = 0; i < props.length; i++) {
                const p = props[i];
                try {
                    mirror.style[p] = style[p];
                } catch (_e) { /* ignore */ }
            }
            mirror.style.width = el.clientWidth + 'px';
            const text = String(el.value || '');
            mirror.textContent = text.slice(0, position);
            const marker = document.createElement('span');
            marker.textContent = '|';
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
            if (!el || typeof el.selectionStart !== 'number') {
                return true;
            }
            try {
                const lineH = this._promptLineHeight(el);
                const top = this._textareaCaretTop(el, el.selectionStart);
                const top0 = this._textareaCaretTop(el, 0);
                return (top - top0) < lineH * 0.6;
            } catch (_e) {
                const pos = el.selectionStart;
                return String(el.value || '').slice(0, pos).indexOf('\n') === -1;
            }
        }

        _promptCaretOnLastLine(el) {
            if (!el || typeof el.selectionEnd !== 'number') {
                return true;
            }
            try {
                const lineH = this._promptLineHeight(el);
                const top = this._textareaCaretTop(el, el.selectionEnd);
                const topEnd = this._textareaCaretTop(
                    el, String(el.value || '').length,
                );
                return Math.abs(topEnd - top) < lineH * 0.6;
            } catch (_e) {
                const pos = el.selectionEnd;
                return String(el.value || '').slice(pos).indexOf('\n') === -1;
            }
        }

        _syncPromptHeight() {
            const el = this.chatInputRef && this.chatInputRef.el;
            if (!el) {
                return;
            }
            const text = el.value != null ? el.value : (this.state.currentInput || '');
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
            el.style.maxHeight = maxH + 'px';
            if (!multiline || this.state.promptCollapsed) {
                el.style.height = minH + 'px';
                el.style.overflowY = multiline ? 'auto' : 'hidden';
                return;
            }
            el.style.height = 'auto';
            el.style.overflowY = 'hidden';
            const natural = el.scrollHeight;
            el.style.height = Math.min(Math.max(natural, minH), maxH) + 'px';
            el.style.overflowY = natural > maxH ? 'auto' : 'hidden';
        }

        _togglePromptCollapsed() {
            if (!this.state.promptMultiline) {
                return;
            }
            this.state.promptCollapsed = !this.state.promptCollapsed;
            this._syncPromptHeight();
            if (this.chatInputRef && this.chatInputRef.el) {
                this.chatInputRef.el.focus();
            }
        }

        _tipPromptResize() {
            return this.state.promptCollapsed ? this.tipExpandPrompt : this.tipCollapsePrompt;
        }

        _insertPromptNewline(el) {
            if (!el) {
                return;
            }
            const start = typeof el.selectionStart === 'number' ? el.selectionStart : el.value.length;
            const end = typeof el.selectionEnd === 'number' ? el.selectionEnd : start;
            const val = el.value || '';
            const next = val.slice(0, start) + '\n' + val.slice(end);
            this.state.promptCollapsed = false;
            this.state.currentInput = next;
            el.value = next;
            try {
                el.setSelectionRange(start + 1, start + 1);
            } catch (eSel) { /* ignore */ }
            this._syncArgPlaceholder(next);
            this._updateSlashSuggestions(next);
            this._syncPromptHeight();
        }

        // Pegar una imagen (Ctrl+V) → se adjunta al turno y viaja al modelo de
        // visión como un chat de IA normal. Si el portapapeles trae solo texto,
        // dejamos el pegado nativo.
        onPaste(ev) {
            const items = (ev.clipboardData && ev.clipboardData.items) || [];
            const files = [];
            for (const it of items) {
                if (it.kind === 'file' && it.type && it.type.startsWith('image/')) {
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

        // Clase FontAwesome (FA4, disponible en O14–O19) para el chip de un
        // fichero según su mimetype/extensión. Devuelve la clase completa
        // ("fa fa-file-pdf-o"). Fallback genérico "fa fa-file-o".
        _fileIconClass(name, mimetype) {
            const mt = (mimetype || '').toLowerCase();
            const ext = (name || '').toLowerCase().split('.').pop();
            const isExt = (arr) => arr.indexOf(ext) !== -1;
            let ic = 'fa-file-o';
            if (mt.startsWith('image/') || isExt(['png', 'jpg', 'jpeg', 'gif', 'webp', 'bmp', 'svg', 'tif', 'tiff'])) ic = 'fa-file-image-o';
            else if (mt === 'application/pdf' || ext === 'pdf') ic = 'fa-file-pdf-o';
            else if (mt.includes('spreadsheet') || mt.includes('excel') || mt === 'text/csv' || isExt(['xls', 'xlsx', 'ods', 'csv'])) ic = 'fa-file-excel-o';
            else if (mt.includes('word') || mt.includes('wordprocessing') || isExt(['doc', 'docx', 'odt', 'rtf'])) ic = 'fa-file-word-o';
            else if (mt.includes('presentation') || mt.includes('powerpoint') || isExt(['ppt', 'pptx', 'odp'])) ic = 'fa-file-powerpoint-o';
            else if (mt.includes('zip') || mt.includes('compressed') || mt.includes('x-tar') || mt.includes('x-7z') || mt.includes('x-rar') || isExt(['zip', 'rar', '7z', 'tar', 'gz', 'bz2', 'xz'])) ic = 'fa-file-archive-o';
            else if (mt.startsWith('audio/') || isExt(['mp3', 'wav', 'ogg', 'flac', 'm4a', 'aac'])) ic = 'fa-file-audio-o';
            else if (mt.startsWith('video/') || isExt(['mp4', 'mkv', 'avi', 'mov', 'webm', 'wmv'])) ic = 'fa-file-video-o';
            else if (mt.includes('json') || mt.includes('xml') || mt.includes('javascript') || mt.includes('html') || isExt(['json', 'xml', 'js', 'ts', 'py', 'html', 'css', 'sh', 'yml', 'yaml', 'sql'])) ic = 'fa-file-code-o';
            else if (mt.startsWith('text/') || isExt(['txt', 'md', 'log', 'ini', 'cfg'])) ic = 'fa-file-text-o';
            return 'fa ' + ic;
        }

        _fileBannerTone(mfile) {
            const mt = ((mfile && mfile.mimetype) || '').split(';')[0].trim().toLowerCase();
            const name = ((mfile && mfile.name) || '').toLowerCase();
            const ext = name.indexOf('.') !== -1 ? name.split('.').pop() : '';
            if (mt === 'application/pdf' || ext === 'pdf') return 'pdf';
            if (mt === 'application/msword' || mt.indexOf('wordprocessing') !== -1
                || ['doc', 'docx'].indexOf(ext) !== -1) return 'word';
            if (mt.indexOf('spreadsheet') !== -1 || mt.indexOf('excel') !== -1 || mt === 'text/csv'
                || ['xls', 'xlsx', 'ods', 'csv'].indexOf(ext) !== -1) return 'excel';
            if (mt.indexOf('json') !== -1 || mt.indexOf('xml') !== -1 || mt.indexOf('javascript') !== -1
                || mt.indexOf('html') !== -1
                || ['json', 'xml', 'js', 'html', 'css', 'py'].indexOf(ext) !== -1) return 'code';
            if (mt.indexOf('text/') === 0 || ['txt', 'md', 'log', 'markdown'].indexOf(ext) !== -1) return 'text';
            return 'other';
        }

        _messagesCanvas() {
            return this.messagesRef && this.messagesRef.el;
        }

        _applyCardWidthRatio(ratio) {
            const api = window.ChatbooCardWidth;
            const root = this._messagesCanvas();
            const n = Number(ratio);
            this._cardWidthRatio = (isFinite(n) && n > 0) ? n : 0;
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
                await this.props.rpc({
                    route: '/chatboo/prefs',
                    params: { card_width_ratio: stored },
                });
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
            this.props.rpc({
                route: '/chatboo/prefs',
                params: { card_width_ratio: 0 },
            }).catch(() => {});
        }

        _onCardResizeStart(ev) {
            const api = window.ChatbooCardWidth;
            const handle = ev.currentTarget;
            const card = handle && handle.closest && handle.closest('.o_chatboo_message');
            const root = this._messagesCanvas();
            if (!api || !card || !root) {
                return;
            }
            ev.preventDefault();
            ev.stopPropagation();
            handle.classList.add('is-dragging');
            const startX = ev.clientX;
            const startW = card.getBoundingClientRect().width;
            const onMove = (e) => {
                api.applyPx(root, startW + (e.clientX - startX));
                api.relayoutCharts(root);
            };
            const onUp = () => {
                handle.classList.remove('is-dragging');
                document.removeEventListener('pointermove', onMove);
                document.removeEventListener('pointerup', onUp);
                this._saveCardWidth(api.ratioFromRoot(root));
            };
            document.addEventListener('pointermove', onMove);
            document.addEventListener('pointerup', onUp);
        }

        messageWantsWideCanvas(msg) {
            if (!msg || msg.role === 'user') {
                return false;
            }
            var clip = msg.clip_data;
            if (clip && (clip.include_chart || clip.include_table
                || (clip.rows && clip.rows.length))) {
                return true;
            }
            var html = String(msg.formatted_html || msg.content || '');
            if (/data-chatboo-show-mode="(?:show-table|show-chart|chart-table|dashboard)"/.test(html)) {
                return true;
            }
            return html.indexOf('o_chatboo_table_block') !== -1
                || html.indexOf('o_chatboo_dashboard') !== -1
                || /<table[\s>]/i.test(html);
        }

        _fileBannerCardClass(mfile) {
            return 'o_chatboo_file_banner_card o_chatboo_file_banner_' + this._fileBannerTone(mfile);
        }

        _fileSizeLabel(mfile) {
            const n = mfile && mfile.size;
            if (n === undefined || n === null || n === '') return '';
            const num = Number(n);
            if (!isFinite(num) || num < 0) return '';
            if (num < 1024) return num + ' B';
            if (num < 1024 * 1024) return (num / 1024).toFixed(1) + ' KB';
            return (num / (1024 * 1024)).toFixed(1) + ' MB';
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

        // URL de formulario para un registro {model, id}. Deep-link clásico válido
        // en O14–O19. Se abre en pestaña nueva (target=_blank), respetando los
        // permisos Odoo del usuario.
        _recordUrl(rec) {
            if (!rec || !rec.model || !rec.id) {
                return '#';
            }
            return '/web#id=' + rec.id + '&model=' + rec.model + '&view_type=form';
        }

        async _attachImageFile(file) {
            try {
                const dataUrl = await this._readFileAsDataUrl(file);
                this.state.pendingImages.push(dataUrl);
                // Conserva el nombre si viene de fichero; null si es pegado (portapapeles).
                this.state.pendingImageNames.push((file && file.name) || null);
            } catch (e) {
                if (this.props.notification) {
                    this.props.notification({ message: _t('Could not read the image.'), type: 'danger' });
                }
            }
            this._focusChatInput();
        }

        _removePendingImage(index) {
            this.state.pendingImages.splice(index, 1);
            this.state.pendingImageNames.splice(index, 1);
            this._focusChatInput();
        }

        // ── Clip: adjuntar ficheros (Fase 1: datos/texto · Fase 2: imágenes) ──
        // Abre el selector (input file oculto en la plantilla). Las imágenes
        // raster se enrutan a la vía multimodal (pendingImages, igual que el
        // pegado); el SVG va como texto (XML); el resto como fichero de datos.
        onClipClick() {
            const input = this.el && this.el.querySelector('.o_chatboo_file_input');
            if (input) {
                input.click();
            }
        }

        // Imagen apta para visión: cualquier image/* salvo SVG (XML → como texto).
        _isVisionImage(file) {
            const t = (file.type || '').toLowerCase();
            if (t === 'image/svg+xml') {
                return false;
            }
            return t.startsWith('image/');
        }

        async onFilesSelected(ev) {
            const files = Array.from((ev.target && ev.target.files) || []);
            await this._ingestFiles(files);
            if (ev.target) {
                ev.target.value = '';  // permitir re-seleccionar el mismo fichero
            }
            this._focusChatInput();
        }

        // Enruta una lista de ficheros (del selector o de drag&drop): imágenes de
        // visión → vía multimodal (conservan nombre); el resto → fichero de datos.
        async _ingestFiles(files) {
            for (const f of Array.from(files || [])) {
                if (f.size > 10 * 1024 * 1024) {  // tope defensivo 10 MB
                    if (this.props.notification) {
                        this.props.notification({
                            message: _t('File too large (max 10 MB): ') + f.name, type: 'danger',
                        });
                    }
                    continue;
                }
                if (this._isVisionImage(f)) {
                    await this._attachImageFile(f);
                } else {
                    await this._attachDataFile(f);
                }
            }
        }

        // ── Drag & drop de ficheros en CUALQUIER zona del chat ───────────────
        // Solo reaccionamos a arrastres con ficheros (no a selección de texto).
        // El overlay es solo visual (pointer-events:none): el 'drop' llega a la raíz.
        _dragHasFiles(ev) {
            const dt = ev && ev.dataTransfer;
            return !!(dt && Array.from(dt.types || []).indexOf('Files') !== -1);
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
            this._focusChatInput();
        }

        async _attachDataFile(file) {
            if (file.size > 10 * 1024 * 1024) {  // tope defensivo 10 MB
                if (this.props.notification) {
                    this.props.notification({
                        message: _t('File too large (max 10 MB): ') + file.name, type: 'danger',
                    });
                }
                return;
            }
            try {
                const dataUrl = await this._readFileAsDataUrl(file);
                this.state.pendingFiles.push({
                    name: file.name,
                    mimetype: file.type || '',
                    size: file.size,
                    data: dataUrl,
                });
            } catch (e) {
                if (this.props.notification) {
                    this.props.notification({ message: _t('Could not read the file.'), type: 'danger' });
                }
            }
        }

        _removePendingFile(index) {
            this.state.pendingFiles.splice(index, 1);
            this._focusChatInput();
        }

        _readFileAsDataUrl(file) {
            return new Promise((resolve, reject) => {
                const reader = new FileReader();
                reader.onload = () => resolve(reader.result);
                reader.onerror = reject;
                reader.readAsDataURL(file);
            });
        }

        /**
         * Lazy-load the list of available skills from the server.
         * Caches the result in this._skillsCache to avoid repeated RPC calls.
         * @returns {Promise<Array>} Skill records.
         */
        async _ensureSkills(force) {
            if (!force && this._skillsLoaded && this.skillsCache) {
                return this.skillsCache;
            }
            try {
                const res = await this.props.rpc({ route: '/chatboo/skills/list', params: {} });
                this.skillsCache = (res && res.skills) || [];
                this.canWriteSkills = !!(res && res.can_write_skills);
                this.skillCodePrefix = (res && res.skill_code_prefix) || '';
                this.skillCommandPrefix = (res && res.skill_command_prefix) || '';
                this._skillsLoaded = true;
            } catch (e) {
                this.skillsCache = [];
                this.canWriteSkills = false;
                this._skillsLoaded = false;
            }
            return this.skillsCache;
        }

        _visibleBuiltinCommands() {
            // Root `/` menu: hide folder children (they live under /mode).
            return (this.builtinCommands || []).filter((c) => !c.folder);
        }

        _modeBuiltinCommands() {
            return (this.builtinCommands || []).filter((c) => c.folder === 'mode');
        }

        _allBuiltinCommands() {
            return (this.builtinCommands || []).slice();
        }

        _invalidateSkillsCache() {
            this.skillsCache = null;
            this._skillsLoaded = false;
        }

        _ownedSkillItems(skills) {
            return this._skillItems((skills || []).filter((s) => s.mine && !s.is_system));
        }

        _notifySlash(message, type) {
            if (this.props.notification) {
                this.props.notification({ message: message, type: type || 'warning' });
            }
        }

        // Ítems de skill (kebab) para el menú flotante.
        /**
         * Map raw skill records to slash-menu item format.
         * @param {Array} skills - Skill records from the server.
         * @returns {Array<{code, label, description}>} Menu items.
         */
        _skillItems(skills) {
            const sorted = (skills || []).slice().sort((a, b) => {
                const ac = (a.code || '').toLowerCase();
                const bc = (b.code || '').toLowerCase();
                return ac.localeCompare(bc, undefined, { sensitivity: 'base' });
            });
            return sorted.map((s) => {
                let badgeLabel = '';
                if (s.mine) {
                    badgeLabel = _t('mine');
                } else if (s.is_system) {
                    badgeLabel = _t('system');
                }
                return {
                    code: s.code, name: s.name, description: s.description,
                    argHint: s.arg_hint || '', argsPolicy: s.args_policy || '',
                    kind: 'skill',
                    mine: !!s.mine, is_system: !!s.is_system,
                    badgeLabel: badgeLabel,
                };
            });
        }

        // Placeholder por defecto del input (calculado en runtime, i18n-safe).
        _defaultInputPlaceholder() {
            return _t('Ask Chatboo... (/ for commands & skills, ↑↓ for history)');
        }

        _resetInputPlaceholder() {
            this.state.inputPlaceholder = this._defaultInputPlaceholder();
        }

        // Pista de argumentos (arg_hint) del skill cuyo "/<code>" se teclea.
        _syncArgPlaceholder(text) {
            const m = /^\/(\S+)/.exec((text || '').trim());
            if (!m) {
                this._resetInputPlaceholder();
                return;
            }
            const code = m[1].toLowerCase();
            const skills = this.skillsCache || [];
            const s = skills.find((x) => (x.code || '').toLowerCase() === code);
            this.state.inputPlaceholder = (s && s.arg_hint)
                ? _t('Arguments, e.g.: %s').replace('%s', s.arg_hint)
                : this._defaultInputPlaceholder();
        }

        // Comandos built-in + skills filtrados por fragmento (autocompletado al teclear).
        /**
         * Filter slash-menu items by a query string (prefix match on code/label).
         * @param {Array} skills - Full skill list.
         * @param {string} q - User-typed query after the '/'.
         * @returns {Array} Filtered items.
         */
        _filterSlashItems(skills, q) {
            const all = [...this._allBuiltinCommands(), ...this._skillItems(skills)];
            if (!q) return all;
            return all.filter(
                (c) =>
                    (c.code || "").toLowerCase().includes(q) ||
                    (c.name || "").toLowerCase().includes(q) ||
                    (c.description || "").toLowerCase().includes(q)
            );
        }

        async _fillOwnedSkillPicker(query, mode = 'delete') {
            const skills = await this._ensureSkills();
            const q = (query || '').toLowerCase();
            let items = this._ownedSkillItems(skills);
            if (q) {
                items = items.filter(
                    (c) =>
                        (c.code || '').toLowerCase().includes(q) ||
                        (c.name || '').toLowerCase().includes(q)
                );
            }
            this.state.slashMode = mode === 'rename' ? 'rename' : 'delete';
            this.state.slashItems = items.slice(0, 50);
            this.state.slashIndex = 0;
            this.state.slashOpen = items.length > 0;
            this._syncSlashMenu();
            if (!items.length && !q) {
                this._notifySlash(
                    mode === 'rename'
                        ? _t('You have no skills to rename.')
                        : _t('You have no skills to delete.'),
                    'warning',
                );
            }
        }

        /**
         * Handle input events that may trigger the slash-command menu.
         * Detects '/' at the start of input and opens the suggestion list.
         * @param {InputEvent} ev
         */
        _onSlashInput(ev) {
            const text = ev && ev.target ? ev.target.value : this.state.currentInput;
            this.state.currentInput = text;
            this._syncArgPlaceholder(text);
            this._syncPromptHeight();
            this._updateSlashSuggestions(text);
        }

        /**
         * Update the slash-menu suggestions based on current input text.
         * Fetches skills if not cached, filters, and renders the menu.
         * @param {string} text - Current input text.
         * @returns {Promise<void>}
         */
        async _updateSlashSuggestions(text) {
            const deletePick = /^\/delete-skill(?:\s+(\S*))?$/i.exec(text || '');
            if (deletePick && (text || '').includes(' ')) {
                await this._ensureSkills();
                if (this.canWriteSkills) {
                    await this._fillOwnedSkillPicker(deletePick[1] || '');
                    return;
                }
            }
            const renamePick = /^\/rename-skill(?:\s+(\S*))?(?:\s+(\S+))?\s*$/i.exec(text || '');
            if (renamePick && (text || '').includes(' ') && !renamePick[2]) {
                await this._ensureSkills();
                if (this.canWriteSkills) {
                    await this._fillOwnedSkillPicker(renamePick[1] || '', 'rename');
                    return;
                }
            }
            const m = /^\/(\S*)$/.exec(text || '');
            if (!m) {
                this.state.slashOpen = false;
                this.state.slashItems = [];
                this.state.slashMode = 'commands';
                this._syncSlashMenu();
                return;
            }
            const token = m[1].toLowerCase();
            let items;
            await this._ensureSkills(!token || this.state.slashMode === 'skills');
            if (!token) {
                // "/" a secas: menú de comandos; skills tras /skills; modes tras /mode.
                if (this.state.slashMode === 'skills') {
                    items = this._skillItems(this.skillsCache || []);
                } else if (this.state.slashMode === 'mode') {
                    items = this._modeBuiltinCommands().slice();
                } else {
                    items = this._visibleBuiltinCommands().slice();
                }
            } else {
                this.state.slashMode = 'commands';
                items = this._filterSlashItems(this.skillsCache || [], token);
            }
            this.state.slashItems = items.slice(0, 50);
            this.state.slashIndex = 0;
            this.state.slashOpen = items.length > 0;
            this._syncSlashMenu();
        }

        /**
         * Apply a selected slash-command item: replace input text and close menu.
         * @param {Object} item - The selected slash item ({code, label}).
         */
        _applySlashSelection(item) {
            if (!item) return;
            if (this.state.slashMode === 'delete' && item.kind === 'skill') {
                this.state.slashOpen = false;
                this.state.slashItems = [];
                this.state.currentInput = '';
                this._resetInputPlaceholder();
                this._syncInputEl();
                this._syncSlashMenu();
                this._confirmDeleteSkill(item.code);
                return;
            }
            if (this.state.slashMode === 'rename' && item.kind === 'skill') {
                this.state.slashOpen = false;
                this.state.slashItems = [];
                this.state.slashMode = 'commands';
                this.state.currentInput = '/rename-skill ' + item.code + ' ';
                this.state.inputPlaceholder = _t('New slash name, then press Enter');
                this._syncInputEl();
                this._syncSlashMenu();
                if (this.chatInputRef && this.chatInputRef.el) {
                    this.chatInputRef.el.focus();
                }
                return;
            }
            this.state.slashOpen = false;
            this.state.slashItems = [];
            this._syncSlashMenu();
            if (item.kind === 'builtin') {
                if (item.code === 'create-skill') {
                    this._beginCreateSkillInput();
                    return;
                }
                if (item.code === 'delete-skill') {
                    this.state.currentInput = '/delete-skill ';
                    this.state.inputPlaceholder = _t('Skill to delete, e.g.: %s').replace('%s', item.argHint);
                    this._syncInputEl();
                    this._fillOwnedSkillPicker('');
                    if (this.chatInputRef && this.chatInputRef.el) {
                        this.chatInputRef.el.focus();
                    }
                    return;
                }
                if (item.code === 'rename-skill') {
                    this.state.currentInput = '/rename-skill ';
                    this.state.inputPlaceholder = _t('Skill to rename, e.g.: %s').replace('%s', item.argHint);
                    this._syncInputEl();
                    this._fillOwnedSkillPicker('', 'rename');
                    if (this.chatInputRef && this.chatInputRef.el) {
                        this.chatInputRef.el.focus();
                    }
                    return;
                }
                if (item.deferArg) {
                    this.state.slashMode = 'commands';
                    this.state.currentInput = '/' + item.code + ' ';
                    this.state.inputPlaceholder = item.placeholder
                        || (item.argHint
                            ? _t('Arguments, e.g.: %s').replace('%s', item.argHint)
                            : this._defaultInputPlaceholder());
                    this._syncInputEl();
                    if (this.chatInputRef && this.chatInputRef.el) {
                        this.chatInputRef.el.focus();
                    }
                    return;
                }
                this.state.currentInput = '';
                this._syncInputEl();
                this._runBuiltinCommand(item.code);
                return;
            }
            this.state.slashMode = 'commands';
            this.state.currentInput = '/' + item.code + ' ';
            this.state.inputPlaceholder = item.argHint
                ? _t('Arguments, e.g.: %s').replace('%s', item.argHint)
                : this._defaultInputPlaceholder();
            this._syncInputEl();
            if (this.chatInputRef && this.chatInputRef.el) {
                this.chatInputRef.el.focus();
            }
        }

        _isHelpArg(arg) {
            const t = String(arg || '').trim().toLowerCase();
            if (!t) {
                return false;
            }
            return (
                /^[?¿？]+$/.test(t)
                || ['help', 'ayuda', 'options', 'opciones', 'usage', 'uso',
                    '/?', '/help', '/ayuda'].includes(t)
            );
        }

        _escSlash(text) {
            return String(text || '')
                .replace(/&/g, '&amp;')
                .replace(/</g, '&lt;')
                .replace(/>/g, '&gt;')
                .replace(/"/g, '&quot;');
        }

        _slashHelpMarkdown(meta) {
            const code = (meta && meta.code) || 'skill';
            const name = (meta && meta.name) || code;
            const desc = (meta && meta.description) || '';
            const hint = (meta && (meta.argHint || meta.arg_hint)) || '';
            const policy = (meta && (meta.argsPolicy || meta.args_policy)) || 'none';
            const owner = (meta && (meta.ownerName || meta.owner_name)) || '';
            const ownerKind = (meta && (meta.ownerKind || meta.owner_kind)) || '';
            const ownerLine = (ownerKind === 'user' && owner) ? owner : _t('Common');
            let policyLine = _t('This command takes no arguments. Help is deterministic (no AI).');
            if (policy === 'default') {
                policyLine = _t('Empty arguments run with the built-in default. Help is deterministic (no AI).');
            } else if (policy === 'ask') {
                policyLine = _t('This command asks for arguments when none are given. Help is deterministic (no AI).');
            }
            let md = '# /' + code + '\n\n**' + name + '**\n\n';
            if (desc) {
                md += desc + '\n\n';
            }
            md += '**' + _t('Owner') + ':** ' + ownerLine + '\n\n';
            md += '**' + _t('Parameters') + ':**\n\n';
            const params = (meta && meta.params) || [];
            if (params.length) {
                md += '| ' + _t('Name') + ' | ' + _t('Type') + ' | ' + _t('Description') + ' | ' + _t('Default') + ' |\n';
                md += '| --- | --- | --- | --- |\n';
                params.forEach((row) => {
                    md += '| `' + row.name + '` | ' + (row.type || 'string') + ' | ' + (row.desc || '—') + ' | ' + (row.default || '—') + ' |\n';
                });
                md += '\n';
            } else {
                md += _t('No formal parameters.') + '\n\n';
            }
            if (hint) {
                md += '`/' + code + ' ' + hint + '`\n\n';
            }
            md += policyLine + '\n';
            return md;
        }

        _slashHelpHtml(meta) {
            return this._formatMarkdown(this._slashHelpMarkdown(meta));
        }

        _showBuiltinHelp(code) {
            const item = (this.builtinCommands || []).find((c) => c.code === code) || {
                code: code, name: code, argsPolicy: 'none',
            };
            const html = this._formatContent(this._slashHelpMarkdown(item));
            this.state.currentInput = '';
            this._syncInputEl();
            this.messages.push({
                role: 'assistant',
                content: html,
                timestamp: formatters.formatWallclock(new Date()),
                // Ayuda local (sin inferencia): no chips de gasto ni aviso de modelo.
                local_ack: true,
                offtopic: true,
                model_details: { model: 'Chatboo', provider: 'local' },
            });
            if (this.scrollToBottom) {
                this.scrollToBottom();
            }
        }

        // Devuelve { code, arg } si el texto es un comando built-in reconocido.
        _matchBuiltinCommand(text) {
            const trimmed = (text || '').trim();
            const helpMatch = /^\/(\S+)\s+(\S+)\s*$/.exec(trimmed);
            if (helpMatch && this._isHelpArg(helpMatch[2])) {
                const code = helpMatch[1].toLowerCase();
                if (/^(painter-local|painter-free|foot-verbose|foot-laconic|show-table|show-chart)$/.test(code)) {
                    return null;
                }
                if (['skills', 'skill', 'help', 'ayuda', '?'].includes(code)) {
                    return { code: 'skills', arg: helpMatch[2], help: true };
                }
                if ((this.builtinCommands || []).some((c) => c.code === code)) {
                    return { code: code, arg: helpMatch[2], help: true };
                }
            }
            const createMatch = /^\/create-skill(?:\s+(\S+)(?:\s+(\S+))?)?\s*$/i.exec(trimmed);
            if (createMatch) {
                return {
                    code: 'create-skill',
                    arg: createMatch[1] || null,
                    arg2: createMatch[2] || null,
                };
            }
            const deleteMatch = /^\/delete-skill(?:\s+([a-z0-9][a-z0-9-]{0,47}))?\s*$/i.exec(trimmed);
            if (deleteMatch) {
                return {
                    code: 'delete-skill',
                    arg: deleteMatch[1] ? deleteMatch[1].toLowerCase() : null,
                };
            }
            const renameMatch = /^\/rename-skill(?:\s+(\S+)(?:\s+(\S+))?)?\s*$/i.exec(trimmed);
            if (renameMatch) {
                return {
                    code: 'rename-skill',
                    arg: renameMatch[1] ? renameMatch[1].toLowerCase() : null,
                    arg2: renameMatch[2] ? renameMatch[2].toLowerCase() : null,
                };
            }
            const m = /^\/(\S+)\s*$/.exec(trimmed);
            if (!m) return null;
            const code = m[1].toLowerCase();
            // Axis slashes go to the server (one-shot confirm / strip+query).
            if (/^(painter-local|painter-free|foot-verbose|foot-laconic|show-table|show-chart)$/.test(code)) {
                return null;
            }
            if (['skills', 'skill', 'help', 'ayuda', '?'].includes(code)) {
                return { code: 'skills', arg: null };
            }
            return this.builtinCommands.some((c) => c.code === code)
                ? { code, arg: null }
                : null;
        }

        async _runBuiltinCommand(builtin) {
            const code = typeof builtin === 'string' ? builtin : builtin.code;
            const arg = typeof builtin === 'object' ? builtin.arg : null;
            const arg2 = typeof builtin === 'object' ? builtin.arg2 : null;
            if (builtin && typeof builtin === 'object' && (builtin.help || this._isHelpArg(arg))) {
                this._showBuiltinHelp(code);
                return;
            }
            if (code === 'create-skill' || code === 'delete-skill' || code === 'rename-skill') {
                await this._ensureSkills();
                if (!this.canWriteSkills) {
                    this._notifySlash(
                        _t('AI Writer permission is required to manage skills from Chatboo.'),
                        'warning',
                    );
                    return;
                }
            }
            if (code === 'create-skill') {
                await this._runCreateSkillCommand(arg, arg2);
                return;
            }
            if (code === 'delete-skill') {
                this.state.currentInput = '';
                this._syncInputEl();
                if (!arg) {
                    this.state.currentInput = '/delete-skill ';
                    this._syncInputEl();
                    await this._fillOwnedSkillPicker('');
                    return;
                }
                await this._confirmDeleteSkill(arg);
                return;
            }
            if (code === 'rename-skill') {
                if (!arg) {
                    this.state.currentInput = '/rename-skill ';
                    this.state.inputPlaceholder = _t('Skill to rename, e.g.: %s').replace('%s', 'old-name new-name');
                    this._syncInputEl();
                    await this._fillOwnedSkillPicker('', 'rename');
                    return;
                }
                if (!arg2) {
                    this.state.currentInput = '/rename-skill ' + arg + ' ';
                    this.state.inputPlaceholder = _t('New slash name, then press Enter');
                    this._syncInputEl();
                    return;
                }
                this.state.currentInput = '';
                this._resetInputPlaceholder();
                this._syncInputEl();
                await this._runRenameSkill(arg, arg2);
                return;
            }
            if (code === 'mode') {
                this.state.currentInput = '';
                this._syncInputEl();
                await this._openModeMenu();
                return;
            }
            this.state.currentInput = '';
            this._syncInputEl();
            await this._openSkillsMenu();
        }

        async _confirmDeleteSkill(skillCode) {
            if (!skillCode) {
                return;
            }
            if (!window.confirm(_t('Delete skill /%s? This cannot be undone.').replace('%s', skillCode))) {
                return;
            }
            try {
                const res = await this._callJsonRoute('/chatboo/delete-skill', {
                    skill_code: skillCode,
                    session_id: this.state.currentSessionId,
                });
                if (!res || res.status !== 'ok') {
                    this._notifySlash((res && res.message) || _t('Could not delete the skill.'), 'danger');
                    return;
                }
                this._invalidateSkillsCache();
                if (this.state.currentSessionId) {
                    await this._loadSession(this.state.currentSessionId);
                } else {
                    this._notifySlash(_t('Skill /%s deleted.').replace('%s', res.deleted || skillCode), 'success');
                }
            } catch (e) {
                this._notifySlash((e && e.message) || _t('Could not delete the skill.'), 'danger');
            }
        }

        async _runRenameSkill(oldCode, newCode) {
            try {
                const res = await this._callJsonRoute('/chatboo/rename-skill', {
                    old_code: oldCode,
                    new_code: newCode,
                    session_id: this.state.currentSessionId,
                });
                if (!res || res.status !== 'ok') {
                    this._notifySlash((res && res.message) || _t('Could not rename the skill.'), 'danger');
                    return;
                }
                this._invalidateSkillsCache();
                if (this.state.currentSessionId) {
                    await this._loadSession(this.state.currentSessionId);
                } else {
                    this._notifySlash(
                        _t('Skill renamed: /%s → /%s')
                            .replace('%s', res.old || oldCode)
                            .replace('%s', res.new || newCode),
                        'success',
                    );
                }
            } catch (e) {
                this._notifySlash((e && e.message) || _t('Could not rename the skill.'), 'danger');
            }
        }

        _looksLikeTurnId(token) {
            return /^[A-Za-z0-9]{4}(?:-\d+)?$/.test(token || '');
        }

        _normalizeTurnIdToken(token) {
            const raw = String(token || '').trim().replace(/-\d+$/, '');
            if (!/^[A-Za-z0-9]{4}$/.test(raw)) {
                return '';
            }
            return raw.toUpperCase();
        }

        _parseCreateSkillArgs(arg, arg2) {
            const t1 = (arg || '').trim();
            const t2 = (arg2 || '').trim();
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
            const pfx = this.skillCommandPrefix || '';
            let slug = this._slugifySkillCode(name);
            if (pfx) {
                const bare = pfx.replace(/-$/, '');
                if (slug === bare) {
                    return pfx + 'captured-skill';
                }
                if (slug.startsWith(pfx)) {
                    const rest = slug.slice(pfx.length).replace(/^-+/, '');
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
            this.state.slashMode = 'commands';
            if (turn) {
                this.state.currentInput = '/create-skill ' + turn + ' ';
                this.state.inputPlaceholder = _t(
                    'Slash name (instance prefix is applied), then press Enter'
                );
            } else {
                this.state.currentInput = '/create-skill ';
                this.state.inputPlaceholder = _t(
                    'Paste or type the 4-character chip, then the slash name'
                );
                this._notifySlash(
                    _t('Turn id is required. Paste or type the 4-character chip, then the slash name.'),
                    'warning',
                );
            }
            this._syncInputEl();
            this._syncSlashMenu();
            if (this.chatInputRef && this.chatInputRef.el) {
                this.chatInputRef.el.focus();
            }
        }

        _slugifySkillCode(text) {
            const slug = String(text || '')
                .trim()
                .toLowerCase()
                .replace(/[^a-z0-9]+/g, '-')
                .replace(/^-+|-+$/g, '')
                .slice(0, 48);
            return slug || 'captured-skill';
        }

        _plainTextFromChatMessage(msg) {
            const raw = (msg && (msg.raw || msg.content)) || '';
            if (!raw) {
                return '';
            }
            if (typeof document !== 'undefined') {
                const tmp = document.createElement('div');
                tmp.innerHTML = String(raw);
                return (tmp.textContent || tmp.innerText || '').trim();
            }
            return String(raw).replace(/<[^>]+>/g, ' ').trim();
        }

        _messageTurnId(msg) {
            if (!msg) {
                return '';
            }
            return this._normalizeTurnIdToken(
                msg.correlation_id
                || (msg.meta && msg.meta.correlation_id)
                || (msg.context_info && msg.context_info.turnCode)
                || ''
            );
        }

        _lastTurnId() {
            const msgs = this.messages || [];
            for (let i = msgs.length - 1; i >= 0; i--) {
                if (msgs[i].role !== 'assistant') {
                    continue;
                }
                const turn = this._messageTurnId(msgs[i]);
                if (turn) {
                    return turn;
                }
            }
            return '';
        }

        _proposeSkillNameForTurn(turnId) {
            const want = this._normalizeTurnIdToken(turnId);
            const msgs = this.messages || [];
            let assistantIdx = -1;
            if (want) {
                for (let i = msgs.length - 1; i >= 0; i--) {
                    if (msgs[i].role !== 'assistant') {
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
                if (msgs[i].role !== 'user') {
                    continue;
                }
                const plain = this._plainTextFromChatMessage(msgs[i]);
                if (plain && !plain.startsWith('/')) {
                    return this._slugifySkillCode(plain.slice(0, 64));
                }
            }
            return 'captured-skill';
        }

        _promptCreateSkillConfirm(skillCode, turnId, reason) {
            const name = this._formatInstanceSlash(
                skillCode || this._proposeSkillNameForTurn(turnId)
            );
            const turn = this._normalizeTurnIdToken(turnId) || this._lastTurnId();
            const line = turn
                ? ('/create-skill ' + turn + ' ' + name)
                : (name ? ('/create-skill ' + name) : '/create-skill ');
            this.state.currentInput = line;
            this.state.slashOpen = false;
            this.state.slashItems = [];
            this.state.inputPlaceholder = turn
                ? _t('Edit turn id and slash name if needed, then press Enter')
                : _t('Paste or type the 4-character chip, then the slash name');
            this._syncInputEl();
            this._syncSlashMenu();
            let msg;
            if (!turn) {
                msg = _t(
                    'Turn id is required. Paste or type the 4-character chip, then the slash name.'
                );
            } else if (reason === 'need_name') {
                msg = _t(
                    'Proposed slash name from that turn (instance prefix applied). '
                    + 'Edit if needed, then press Enter to open the wizard.'
                );
            } else {
                msg = _t(
                    'Confirm turn id and slash name. Edit if needed, then press Enter '
                    + 'to open the wizard.'
                );
            }
            const html = (
                '<div class="card border-0 shadow-sm o_chatboo_slash_help"><div class="card-body">'
                + '<p class="mb-2">' + this._escSlash(msg) + '</p>'
                + '<p class="mb-0 small"><code>' + this._escSlash(line) + '</code></p>'
                + '</div></div>'
            );
            this.messages.push({
                role: 'assistant',
                content: html,
                timestamp: formatters.formatWallclock(new Date()),
                local_ack: true,
                offtopic: true,
                model_details: { model: 'Chatboo', provider: 'local' },
            });
            if (this.scrollToBottom) {
                this.scrollToBottom();
            }
            if (this.chatInputRef && this.chatInputRef.el) {
                this.chatInputRef.el.focus();
            }
        }

        _restoreChatbooOverlayZ(overlay, prevZ) {
            if (!overlay) {
                return;
            }
            overlay.style.zIndex = prevZ || '1050';
        }

        async _runCreateSkillCommand(skillCodeHint, turnId) {
            if (!this.state.currentSessionId) {
                if (this.props.notification) {
                    this.props.notification({ message: _t('No active session.'), type: 'warning' });
                }
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
                    'need_turn',
                );
                return;
            }
            if (!parsed.skillCode) {
                this._promptCreateSkillConfirm(null, parsed.turnId, 'need_name');
                return;
            }
            try {
                const params = {
                    session_id: this.state.currentSessionId,
                    skill_code: this._formatInstanceSlash(parsed.skillCode),
                    turn_id: parsed.turnId,
                };
                const res = await this._callJsonRoute('/chatboo/create-skill', params);
                if (!res || res.status !== 'ok' || !res.action) {
                    if (this.props.notification) {
                        this.props.notification({
                            message: (res && res.message) || _t('Could not open the skill wizard.'),
                            type: 'danger',
                            sticky: true,
                        });
                    }
                    return;
                }
                if (res.warning && this.props.notification) {
                    this.props.notification({ message: res.warning, type: 'warning', sticky: false });
                }
                const overlay = document.getElementById('o_chatboo_persistent_overlay');
                const prevZ = overlay ? overlay.style.zIndex : '';
                if (overlay) {
                    overlay.style.zIndex = '1000';
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
                const actionOpts = { on_close: restore, onClose: restore };
                try {
                    if (this.props.doAction) {
                        await this.props.doAction(res.action, actionOpts);
                    } else if (this.env && this.env.services && this.env.services.action) {
                        await this.env.services.action.doAction(res.action, actionOpts);
                    } else if (this.props.notification) {
                        restore();
                        this.props.notification({
                            message: _t('Could not open the skill wizard from here. Use AI Skills menu.'),
                            type: 'warning',
                            sticky: true,
                        });
                    }
                } catch (eAct) {
                    restore();
                    throw eAct;
                }
            } catch (e) {
                if (this.props.notification) {
                    this.props.notification({
                        message: (e && e.message) || _t('Could not open the skill wizard.'),
                        type: 'danger',
                        sticky: true,
                    });
                }
            }
        }

        /**
         * Open a full-screen skill selection menu (alternative to slash input).
         * Loads skills, shows a modal/dropdown, and inserts the selected skill.
         * @returns {Promise<void>}
         */
        async _openSkillsMenu() {
            const skills = await this._ensureSkills(true);
            this.state.slashMode = 'skills';
            this.state.currentInput = '/';
            this.state.slashItems = this._skillItems(skills).slice(0, 50);
            this.state.slashIndex = 0;
            this.state.slashOpen = this.state.slashItems.length > 0;
            this._syncInputEl();
            this._syncSlashMenu();
            if (this.chatInputRef && this.chatInputRef.el) {
                this.chatInputRef.el.focus();
            }
        }

        async _openModeMenu() {
            this.state.slashMode = 'mode';
            this.state.currentInput = '/';
            this.state.slashItems = this._modeBuiltinCommands().slice();
            this.state.slashIndex = 0;
            this.state.slashOpen = this.state.slashItems.length > 0;
            this._resetInputPlaceholder();
            this._syncInputEl();
            this._syncSlashMenu();
            if (this.chatInputRef && this.chatInputRef.el) {
                this.chatInputRef.el.focus();
            }
        }

        // ══════════════════════════════════════════════════════════════════════
        // 8. INPUT HANDLING — Keyboard shortcuts
        // ══════════════════════════════════════════════════════════════════════

        /**
         * Handle keyboard events in the chat input.
         *
         * Key bindings:
         *   When slash menu is open:
         *     ↑/↓   Navigate items
         *     Enter/Tab  Select item
         *     Escape     Close menu
         *
         *   Normal mode:
         *     Enter         Send message
         *     Ctrl/Cmd+Enter  New line (never sends)
         *     ↑/↓         Prompt history (only at first/last line)
         *     Any key       Reset history navigation
         *
         * @param {KeyboardEvent} ev
         */
        _onInputKeydown(ev) {
            if (this.state.slashOpen && this.state.slashItems.length) {
                if (ev.which === 40) { // Arrow Down
                    ev.preventDefault();
                    this.state.slashIndex = (this.state.slashIndex + 1) % this.state.slashItems.length;
                    this._syncSlashMenu();
                    return;
                }
                if (ev.which === 38) { // Arrow Up
                    ev.preventDefault();
                    this.state.slashIndex =
                        (this.state.slashIndex - 1 + this.state.slashItems.length) % this.state.slashItems.length;
                    this._syncSlashMenu();
                    return;
                }
                if (ev.which === 13 || ev.which === 9) { // Enter / Tab
                    ev.preventDefault();
                    if (ev.which === 13) {
                        const builtin = this._matchBuiltinCommand(this.state.currentInput);
                        if (builtin && (
                            builtin.code === 'create-skill'
                            || builtin.help
                            || this._isHelpArg(builtin.arg)
                        )) {
                            this.state.slashOpen = false;
                            this.state.slashItems = [];
                            this._syncSlashMenu();
                            this._sendMessage();
                            return;
                        }
                    }
                    this._applySlashSelection(this.state.slashItems[this.state.slashIndex]);
                    return;
                }
                if (ev.which === 27) { // Escape
                    ev.preventDefault();
                    this.state.slashOpen = false;
                    this.state.slashMode = 'commands';
                    this._syncSlashMenu();
                    return;
                }
            }

            // Ctrl/Cmd+Enter: nueva línea (nunca envía). Enter solo: envía.
            if (ev.which === 13 && (ev.ctrlKey || ev.metaKey)) {
                ev.preventDefault();
                this._insertPromptNewline(ev.target);
                return;
            }
            if (ev.which === 13 && !ev.shiftKey && !ev.altKey) {
                ev.preventDefault();
                this._sendMessage();
                return;
            }

            // Arrow Up: previous history — only on first *visual* line.
            if (ev.which === 38 && this.inputHistory.length
                    && this._promptCaretOnFirstLine(ev.target)) {
                if (this.historyIndex === -1) {
                    this.currentInputBeforeHistory = this.state.currentInput;
                }
                if (this.historyIndex < this.inputHistory.length - 1) {
                    this.historyIndex++;
                    this.state.currentInput = this.inputHistory[
                        this.inputHistory.length - 1 - this.historyIndex
                    ];
                    this.state.promptCollapsed = false;
                    ev.preventDefault();
                    this._syncInputEl();
                }
                return;
            }

            // Arrow Down: next history — only on last *visual* line.
            if (ev.which === 40 && this.inputHistory.length
                    && this._promptCaretOnLastLine(ev.target)) {
                if (this.historyIndex > 0) {
                    this.historyIndex--;
                    this.state.currentInput = this.inputHistory[
                        this.inputHistory.length - 1 - this.historyIndex
                    ];
                    this.state.promptCollapsed = false;
                    ev.preventDefault();
                    this._syncInputEl();
                } else if (this.historyIndex === 0) {
                    this.historyIndex = -1;
                    this.state.currentInput = this.currentInputBeforeHistory;
                    this.state.promptCollapsed = false;
                    ev.preventDefault();
                    this._syncInputEl();
                }
                return;
            }

            // Any other key: Reset history navigation
            if (this.historyIndex !== -1 && ev.which !== 38 && ev.which !== 40) {
                this.historyIndex = -1;
                this.currentInputBeforeHistory = '';
            }
        }

        /**
         * Save the raw (pre-formatted) content of a message for use in
         * OWL template rendering. Stores it in a parallel data structure.
         * @param {Object} msg - Message object with role and content.
         * @returns {Promise<void>}
         */
        async _saveRawForTemplate(msg) {
            if (!msg || !msg.raw_save_data) return;
            const { json, query } = msg.raw_save_data;
            try {
                const r = await this.props.rpc({
                    route: '/chatboo/save_raw_for_template',
                    params: { query, result_json: json }
                });
                if (r && r.status === 'ok') {
                    if (this.props.notification) this.props.notification({ message: r.message || _t('Saved'), type: 'success', sticky: false });
                } else {
                    if (this.props.notification) this.props.notification({ message: r.message || _t('Error'), type: 'danger', sticky: true });
                }
            } catch (e) {
                if (this.props.notification) this.props.notification({ message: (e && e.message) || _t('Error while saving'), type: 'danger', sticky: true });
            }
        }

        // ══════════════════════════════════════════════════════════════════════
        // 9. CONTENT FORMATTING — delegated to pns_ai_chatboo.formatters
        // ══════════════════════════════════════════════════════════════════════

        /** @see formatters.isLikelyHtml */
        _isLikelyHtml(content) { return formatters.isLikelyHtml(content); }
        /** @see formatters.formatContent */
        _formatContent(content) { return formatters.formatContent(content); }
        /** @see formatters.formatMarkdown */
        _formatMarkdown(content) { return formatters.formatMarkdown(content); }
        /** @see formatters.formatCSV */
        _formatCSV(lines) { return formatters.formatCSV(lines); }
        /** @see formatters.formatJsonWithLineBreaks */
        _formatJsonWithLineBreaks(obj, indent) { return formatters.formatJsonWithLineBreaks(obj, indent); }
        /** @see formatters.formatNumber */
        _formatNumber(value, locale) { return formatters.formatNumber(value, locale, this.constructor.DEFAULT_DECIMAL_PLACES); }
        /** @see formatters.formatJsonAsTable */
        _formatJsonAsTable(data) { return formatters.formatJsonAsTable(data); }
        /** @see formatters.escapeHtml */
        _escapeHtml(text) { return formatters.escapeHtml(text); }

        /**
         * Show context usage chart modal
         */
        // ══════════════════════════════════════════════════════════════════════
        // 10. CONTEXT CHART — Token usage visualization
        // ══════════════════════════════════════════════════════════════════════

        /**
         * Render a visual context window usage chart for the last message.
         *
         * Shows a stacked bar chart with:
         *   - System prompt tokens (blue)
         *   - Conversation history tokens (green)
         *   - Available headroom (gray)
         *   - Model context window size
         *
         * Data comes from msg.context_info (populated by the streaming endpoint).
         * Rendered as inline HTML + CSS (no charting library).
         */
        _showContextChart() {
            // Get all messages to match questions with responses
            const allMessages = this.messages.filter(m => m.role === 'user' || m.role === 'assistant');
            const assistantMessagesWithUsage = this.messages.filter(m =>
                m.role === 'assistant' && m.usage && m.context_limit
            );

            if (assistantMessagesWithUsage.length === 0) {
                this.props.notification({
                    message: _t('No context information available'),
                    type: 'info',
                    sticky: false
                });
                return;
            }

            // Cabecera: LLM y proveedor que respondió (lo que el usuario quiere ver).
            const latestAssistantMsg = assistantMessagesWithUsage[assistantMessagesWithUsage.length - 1];
            const modelDetails = latestAssistantMsg.model_details || {};
            const _model = modelDetails.model || "";
            const _provider = modelDetails.provider || "";
            const modelLabel = (_model || _provider)
                ? [_model, _provider].filter(Boolean).join(" · ")
                : "Unknown model";

            // Cada asistente con usage se empareja con SU prompt (guardado o
            // usuario anterior), no con el enésimo user del array.
            const usageData = [];
            let totalUsed = 0;
            let maxLimit = 0;
            const statsHelper = window.ChatbooContextStats;

            for (let i = 0; i < this.messages.length; i++) {
                const assistantMsg = this.messages[i];
                if (assistantMsg.role !== 'assistant' || !assistantMsg.usage || !assistantMsg.context_limit) {
                    continue;
                }

                const used = contextUsedTokens(assistantMsg.usage);
                const turnTokens = turnTokensValue(assistantMsg.usage) || 0;
                const providerName = (assistantMsg.model_details && assistantMsg.model_details.provider) || '';
                const displayCurrency = (assistantMsg.model_details && assistantMsg.model_details.display_currency) || '';
                const costUsd = Number(this._spendCost(assistantMsg.usage)) || 0;
                const cost = formatCostLabel(
                    this._spendCost(assistantMsg.usage),
                    this._currencyForProvider(providerName, displayCurrency),
                    this._fx,
                );
                const turnLabel = formatTurnTokensLabel(assistantMsg.usage);
                const limit = assistantMsg.context_limit;
                const percent = limit > 0 ? ((used / limit) * 100).toFixed(1) : 0;

                const _usage = assistantMsg.usage || {};
                let _cached = _usage.cached_tokens;
                if (_cached == null && _usage.prompt_tokens_details) {
                    _cached = _usage.prompt_tokens_details.cached_tokens;
                }
                _cached = _cached || 0;
                const _promptTok = _usage.prompt_tokens || 0;
                const _cachedPct = _promptTok > 0 ? (_cached / _promptTok) * 100 : 0;

                totalUsed += used;
                maxLimit = Math.max(maxLimit, limit);

                let questionText = statsHelper && statsHelper.questionForAssistant
                    ? statsHelper.questionForAssistant(this.messages, i)
                    : (assistantMsg.user_prompt
                        || (assistantMsg.meta && assistantMsg.meta.user_prompt)
                        || '');
                questionText = (statsHelper && statsHelper.stripQuestion)
                    ? statsHelper.stripQuestion(questionText)
                    : String(questionText || '').replace(/<[^>]*>/g, ' ').trim();
                const displayText = questionText.length > 50 ? questionText.substring(0, 50) + '...' : questionText;

                const turnCode = (
                    assistantMsg.correlation_id
                    || (assistantMsg.meta && assistantMsg.meta.correlation_id)
                    || (assistantMsg.context_info && assistantMsg.context_info.turnCode)
                    || ''
                ).trim();
                usageData.push({
                    question: usageData.length + 1,
                    questionText: displayText,
                    questionTextFull: questionText,
                    used: used,
                    limit: limit,
                    percent: parseFloat(percent),
                    usedK: (used / 1024).toFixed(2),
                    limitK: (limit / 1024).toFixed(2),
                    turnTokens: turnTokens,
                    turnK: turnTokens > 0 ? (turnTokens / 1024).toFixed(2) : null,
                    turnLabel: turnLabel,
                    turnCode: turnCode,
                    costUsd: costUsd,
                    costLabel: cost.label,
                    cached: _cached,
                    cachedPct: _cachedPct,
                    messageIndex: i,
                    userMessageIndex: i
                });
            }

            const stats = window.ChatbooContextStats;
            const occupying = stats
                ? stats.occupyingRows(usageData)
                : usageData.filter((d) => (d.used || 0) > 0);
            if (!occupying.length) {
                this.props.notification({
                    message: _t('No context information available'),
                    type: 'info',
                    sticky: false
                });
                return;
            }

            // Calculate global statistics (last occupying turn vs its own cap)
            const latestData = occupying[occupying.length - 1];
            const latestUsed = latestData.used;
            const latestUsedK = latestData.usedK;
            const latestLimitK = latestData.limitK;
            const latestPercentNum = latestData.percent;
            const latestPercent = latestPercentNum.toFixed(1);

            // Caché de prompt del proveedor (prefix/prompt caching): solo se pinta
            // si algún turno la reporta.
            const anyCached = occupying.some(d => (d.cached || 0) > 0);
            const latestCached = latestData.cached || 0;
            const latestCachedPct = latestData.cachedPct || 0;
            const anyTurn = occupying.some(d => d.turnLabel && d.turnLabel !== '-');
            const anyTurnCode = occupying.some(d => d.turnCode);
            const anyCost = occupying.some(d => d.costLabel && d.costLabel !== '-');
            const latestTurnK = latestData.turnK;
            const latestCostLabel = latestData.costLabel;
            const sessionTurnTokens = occupying.reduce((sum, d) => sum + (d.turnTokens || 0), 0);
            const sessionCostUsd = occupying.reduce((sum, d) => sum + (d.costUsd || 0), 0);
            const sessionTurnK = sessionTurnTokens > 0 ? (sessionTurnTokens / 1024).toFixed(2) : null;
            const sessionCost = formatCostLabel(
                sessionCostUsd,
                this._currencyForProvider(
                    (latestAssistantMsg.model_details && latestAssistantMsg.model_details.provider) || '',
                    (latestAssistantMsg.model_details && latestAssistantMsg.model_details.display_currency) || '',
                ),
                this._fx,
            );
            const sessionCostLabel = sessionCost.label;

            // Trend
            let trend = '';
            let trendColor = '';
            if (occupying.length >= 2) {
                const diff = occupying[occupying.length - 1].used - occupying[occupying.length - 2].used;
                const diffK = (diff / 1024).toFixed(2);
                if (diff > 0) {
                    trend = `↑ +${diffK}k tokens vs previous`;
                    trendColor = 'text-warning';
                } else {
                    trend = '→ Stable';
                    trendColor = 'text-muted';
                }
            }

            let chartHtml = `
                <div class="modal fade show" id="contextChartModal" tabindex="-1" style="display: block; background: rgba(0,0,0,0.5);">
                    <div class="modal-dialog modal-xl">
                        <div class="modal-content border-0 shadow-lg" style="border-radius: 12px;">
                            <div class="modal-header bg-light">
                                <h5 class="modal-title"><i class="fa fa-microchip mr-2"></i> Context analysis: <span class="text-primary font-weight-bold">${modelLabel}</span></h5>
                                <button type="button" class="close" onclick="document.getElementById('contextChartModal').remove()">
                                    <span>×</span>
                                </button>
                            </div>
                            <div class="modal-body p-4">
                                <div class="mb-4">
                                    <h6 class="font-weight-bold mb-3"><i class="fa fa-chart-line text-primary"></i> Session status</h6>
                                    <div class="row">
                                        <div class="col">
                                            <div class="card border-0 bg-light shadow-sm h-100">
                                                <div class="card-body text-center p-3">
                                                    <p class="text-muted small mb-1">INTERACTIONS</p>
                                                    <h4 class="font-weight-bold text-primary mb-0">${occupying.length}</h4>
                                                    <p class="small mb-0">Performed</p>
                                                </div>
                                            </div>
                                        </div>
                                        <div class="col">
                                            <div class="card border-0 bg-light shadow-sm h-100">
                                                <div class="card-body text-center p-3">
                                                    <p class="text-muted small mb-1">SENT / PROVIDER CAP</p>
                                                    <h4 class="font-weight-bold ${latestPercentNum > 80 ? 'text-danger' : latestPercentNum > 60 ? 'text-warning' : 'text-success'} mb-0">${latestPercent}%</h4>
                                                    <p class="small mb-0">${latestUsedK}k / ${latestLimitK}k</p>
                                                </div>
                                            </div>
                                        </div>
                                        ${sessionTurnK ? `
                                        <div class="col">
                                            <div class="card border-0 bg-light shadow-sm h-100">
                                                <div class="card-body text-center p-3">
                                                    <p class="text-muted small mb-1">${_t('SESSION')}</p>
                                                    <h4 class="font-weight-bold mb-0">${sessionTurnK}k</h4>
                                                    <p class="small mb-0">${_t('tokens billed')}</p>
                                                    ${latestTurnK ? `<p class="small text-muted mb-0">${_t('last turn')} ${latestTurnK}k</p>` : ''}
                                                </div>
                                            </div>
                                        </div>` : ''}
                                        ${sessionCostLabel ? `
                                        <div class="col">
                                            <div class="card border-0 bg-light shadow-sm h-100">
                                                <div class="card-body text-center p-3">
                                                    <p class="text-muted small mb-1">${_t('COST')}</p>
                                                    <h4 class="font-weight-bold mb-0">${this._escapeHtml(sessionCostLabel)}</h4>
                                                    <p class="small mb-0">${_t('this session')}</p>
                                                    ${latestCostLabel ? `<p class="small text-muted mb-0">${_t('last turn')} ${this._escapeHtml(latestCostLabel)}</p>` : ''}
                                                </div>
                                            </div>
                                        </div>` : ''}
                                    </div>
                                    <div class="mt-4">
                                        <div class="d-flex justify-content-between mb-1 small">
                                            <span>${_t('Last turn · sent vs provider cap')}</span>
                                            <span class="font-weight-bold">${latestPercent}% ${_t('of the %s k cap').replace('%s', latestLimitK)}</span>
                                        </div>
                                        ${stats ? stats.occupancyBarHtml(latestPercentNum, 14) : ''}
                                        <div class="small text-muted mt-2 mb-1">${_t('Occupancy this session')}</div>
                                        ${stats ? stats.sparklineSvg(occupying) : ''}
                                        <div class="d-flex justify-content-between mt-1 small text-muted">
                                            <span>${_t('Context status')}</span>
                                            ${trend ? `<span class="${trendColor}">${trend}</span>` : ''}
                                        </div>
                                        ${anyCached ? `
                                        <div class="d-flex justify-content-between mt-2 small">
                                            <span style="color:#0ea5e9;"><i class="fa fa-bolt"></i> Prompt cache (last turn)</span>
                                            <span class="font-weight-bold" style="color:#0ea5e9;">${latestCachedPct.toFixed(0)}% · ${(latestCached / 1024).toFixed(2)}k tokens reused</span>
                                        </div>` : ''}
                                    </div>
                                </div>
                                
                                <div class="mt-4">
                                    <h6 class="font-weight-bold mb-3"><i class="fa fa-history text-primary"></i> Detail per Interaction</h6>
                                    <div class="table-responsive">
                                        <table class="table table-hover border">
                                            <thead class="bg-light">
                                                <tr>
                                                    <th style="width: 5%;">#</th>
                                                    ${anyTurnCode ? '<th style="width: 8%;">Id</th>' : ''}
                                                    <th style="width: 32%;">Question</th>
                                                    <th style="width: 12%;">Sent</th>
                                                    <th style="width: 8%;">%</th>
                                                    ${anyTurn ? '<th style="width: 10%;">Turn</th>' : ''}
                                                    ${anyCost ? '<th style="width: 12%;">Cost</th>' : ''}
                                                    ${anyCached ? '<th style="width: 8%;">Cache</th>' : ''}
                                                    <th style="width: 18%;">Total Visual Impact</th>
                                                </tr>
                                            </thead>
                                            <tbody>`;

            occupying.forEach(data => {
                const turnTok = stats && stats.safeTurnToken
                    ? stats.safeTurnToken(data.turnCode)
                    : String(data.turnCode || '').replace(/[^A-Za-z0-9_-]/g, '');
                chartHtml += `
                                                <tr class="o_ctx_turn_row" data-turn-code="${this._escapeHtml(turnTok)}" data-msg-index="${data.messageIndex}">
                                                    <td><strong>#${data.n}</strong></td>
                                                    ${anyTurnCode ? `<td style="font-family:monospace;">${this._escapeHtml(data.turnCode || '—')}</td>` : ''}
                                                    <td class="o_ctx_turn_q" style="max-width: 300px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; cursor:pointer; color:#007cba;" title="${this._escapeHtml(data.questionTextFull || data.questionText)}">
                                                        ${this._escapeHtml(data.questionText)}
                                                    </td>
                                                    <td>${data.usedK}k</td>
                                                    <td>${data.percent}%</td>
                                                    ${anyTurn ? `<td>${this._escapeHtml(data.turnLabel || '0')}</td>` : ''}
                                                    ${anyCost ? `<td>${data.costLabel && data.costLabel !== '-' ? this._escapeHtml(data.costLabel) : '—'}</td>` : ''}
                                                    ${anyCached ? `<td style="color:#0ea5e9;">${(data.cached || 0) > 0 ? (data.cachedPct.toFixed(0) + '%') : '—'}</td>` : ''}
                                                    <td>${stats ? stats.rowBarHtml(data.percent) : ''}</td>
                                                </tr>`;
            });

            chartHtml += `
                                            </tbody>
                                            ${(sessionTurnK || sessionCostLabel) ? `
                                            <tfoot class="bg-light">
                                                <tr>
                                                    <td colspan="${anyTurnCode ? 3 : 2}"><strong>${_t('Session')}</strong></td>
                                                    <td></td>
                                                    <td></td>
                                                    ${anyTurn ? `<td><strong>${sessionTurnK ? sessionTurnK + 'k' : '0'}</strong></td>` : ''}
                                                    ${anyCost ? `<td><strong>${sessionCostLabel ? this._escapeHtml(sessionCostLabel) : '—'}</strong></td>` : ''}
                                                    ${anyCached ? '<td></td>' : ''}
                                                    <td></td>
                                                </tr>
                                            </tfoot>` : ''}
                                        </table>
                                    </div>
                                </div>
                            </div>
                            <div class="modal-footer bg-light">
                                <span class="mr-auto text-muted small"><i class="fa fa-microchip"></i> ${modelLabel}</span>
                                <button type="button" class="btn btn-secondary" onclick="document.getElementById('contextChartModal').remove()">Close</button>
                            </div>
                        </div>
                    </div>
                </div>
                <div class="modal-backdrop fade show"></div>`;

            // Remove existing modal if any
            const existingModal = document.getElementById('contextChartModal');
            if (existingModal) {
                existingModal.remove();
                const backdrop = document.querySelector('.modal-backdrop');
                if (backdrop) backdrop.remove();
            }

            // Add modal to body
            document.body.insertAdjacentHTML('beforeend', chartHtml);

            const self = this;
            setTimeout(() => {
                document.querySelectorAll('#contextChartModal tr.o_ctx_turn_row').forEach((row) => {
                    const questionCell = row.querySelector('.o_ctx_turn_q');
                    if (questionCell) {
                        questionCell.addEventListener('mouseenter', () => {
                            questionCell.style.textDecoration = 'underline';
                        });
                        questionCell.addEventListener('mouseleave', () => {
                            questionCell.style.textDecoration = 'none';
                        });
                    }
                    row.addEventListener('click', function (e) {
                        e.preventDefault();
                        e.stopPropagation();
                        const modal = document.getElementById('contextChartModal');
                        if (modal) {
                            modal.remove();
                        }
                        const backdrop = document.querySelector('.modal-backdrop');
                        if (backdrop) {
                            backdrop.remove();
                        }
                        const code = row.getAttribute('data-turn-code') || '';
                        const idx = parseInt(row.getAttribute('data-msg-index'), 10);
                        setTimeout(() => {
                            self._scrollToContextTurn(code, idx);
                        }, 100);
                    });
                });
            }, 200);
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

        scrollToBottom() {
            // requestAnimationFrame fires after next paint — DOM is guaranteed to be updated
            requestAnimationFrame(() => {
                const el = this.messagesRef.el;
                if (el) {
                    if (window.ChatbooDashboard && typeof window.ChatbooDashboard.hydrateContent === 'function') {
                        window.ChatbooDashboard.hydrateContent(el);
                    } else if (window.ChatbooCharts && typeof window.ChatbooCharts.hydrate === 'function') {
                        window.ChatbooCharts.hydrate(el);
                    }
                    if (window.ChatbooSvgCards && typeof window.ChatbooSvgCards.hydrate === 'function') {
                        window.ChatbooSvgCards.hydrate(el);
                    }
                    el.scrollTop = el.scrollHeight;
                }
            });
        }


        // ══════════════════════════════════════════════════════════════════════
        // 11. EXPORT — delegated to pns_ai_chatboo.export
        // ══════════════════════════════════════════════════════════════════════

        /**
         * Build the context object for export functions.
         * @returns {Object} ExportContext with messages, messagesEl, notification
         */
        _exportCtx() {
            return {
                messages: this.messages,
                messagesEl: this.messagesRef.el,
                notification: this.props.notification,
                sessionId: this.state.currentSessionId,
                rpc: (spec) => this.props.rpc(spec),
                onChipFulfilled: (msg) => {
                    if (msg && msg.files) {
                        msg.files = msg.files.slice();
                    }
                    this._saveCurrentSession().catch(() => {});
                },
            };
        }

        _fulfillPendingExports(msg) {
            if (!msg || typeof exportUtils.fulfillPendingSessionDocuments !== 'function') {
                return;
            }
            const pending = (msg.files || []).some((f) => f && f.pending);
            if (!pending) {
                return;
            }
            const run = () => {
                const idx = this.messages.indexOf(msg);
                let sourceEl = null;
                const root = this.messagesRef && this.messagesRef.el;
                if (root && idx >= 0) {
                    const node = root.querySelector('[data-msg-index="' + idx + '"]');
                    sourceEl = node && (node.querySelector('.o_chatboo_content') || node);
                }
                exportUtils.fulfillPendingSessionDocuments(msg, sourceEl, this._exportCtx())
                    .catch(() => {});
            };
            setTimeout(run, 120);
        }

        _fulfillPendingExportsInView() {
            (this.messages || []).forEach((msg) => this._fulfillPendingExports(msg));
        }

        /** @see exportUtils.htmlToMarkdown */
        _htmlToMarkdown(html) { return exportUtils.htmlToMarkdown(html); }
        /** @see exportUtils.tableToMarkdown */
        _tableToMarkdown(table) { return exportUtils.tableToMarkdown(table); }
        /** @see exportUtils.markdownToPDFText */
        _markdownToPDFText(markdown) { return exportUtils.markdownToPDFText(markdown); }
        /** @see exportUtils.markdownToHTML */
        _markdownToHTML(markdown) { return exportUtils.markdownToHTML(markdown); }
        /** @see exportUtils.normalizeFilename */
        _normalizeFilename(text) { return exportUtils.normalizeFilename(text); }
        /** @see exportUtils.extractPlainText */
        _extractPlainText(msg) { return exportUtils.extractPlainText(msg); }
        /** @see exportUtils.generateFilename */
        _generateFilename(msgIndex, extension) { return exportUtils.generateFilename(msgIndex, extension, this._exportCtx()); }
        /** @see exportUtils.copyToClipboard */
        _copyToClipboard(ev) { return exportUtils.copyToClipboard(ev, this._exportCtx()); }
        /** Copy turn correlation id without opening the context modal. */
        async _copyTurnCode(ev) {
            if (ev) {
                ev.stopPropagation();
                if (typeof ev.preventDefault === 'function') {
                    ev.preventDefault();
                }
            }
            const el = ev && (ev.currentTarget || ev.target);
            const text = (
                (el && el.getAttribute && el.getAttribute('data-turn-code'))
                || ''
            ).trim();
            if (!text) {
                return;
            }
            try {
                await navigator.clipboard.writeText(text);
                if (this.props.notification) {
                    this.props.notification({
                        message: _t('Turn id copied.'),
                        type: 'success',
                        sticky: false,
                    });
                }
            } catch (e) {
                if (this.props.notification) {
                    this.props.notification({
                        message: _t('Could not copy.'),
                        type: 'warning',
                        sticky: false,
                    });
                }
            }
        }
        /** @see exportUtils.doCopy */
        _doCopy(textContent, iconElement) { return exportUtils.doCopy(textContent, iconElement, this._exportCtx()); }
        /** @see exportUtils.fallbackCopy */
        _fallbackCopyToClipboard(text, iconElement) { return exportUtils.fallbackCopy(text, iconElement, this._exportCtx()); }
        /** @see exportUtils.downloadAsPDF */
        _downloadAsPDF(ev) { return exportUtils.downloadAsPDF(ev, this._exportCtx()); }
        /** @see exportUtils.generateTextPDF */
        _generateTextPDF(doc, markdown, msgIndex) { return exportUtils.generateTextPDF(doc, markdown, msgIndex, this._exportCtx()); }
        /** @see exportUtils.downloadAsExcel */
        _downloadAsExcel(ev) { return exportUtils.downloadAsExcel(ev, this._exportCtx()); }
        /** @see exportUtils.downloadAsWord */
        _downloadAsWord(ev) { return exportUtils.downloadAsWord(ev, this._exportCtx()); }
    }

    // Inline template (Odoo 14: OWL component templates are not loaded into env.qweb
    // from the module 'qweb' manifest key, so we register it here). The OWL env.qweb
    // translateFn (_t) still translates the static text at render time using the .po,
    // so es/ar keep working.
    ChatbooComponent.template = xml`
        <div class="o_content o_chatboo_container" style="position: absolute; top: 0; bottom: 0; left: 0; right: 0; background: #f8f9fa; display: flex; flex-direction: column;"
             t-on-dragenter="_onDragOver" t-on-dragover="_onDragOver" t-on-dragleave="_onDragLeave" t-on-drop="_onDrop">
            <!-- Overlay al arrastrar ficheros sobre CUALQUIER zona del chat. Solo
                 visual (pointer-events:none): el 'drop' llega a la raíz. -->
            <div t-if="state.dragActive" style="position:absolute;top:0;bottom:0;left:0;right:0;z-index:2000;pointer-events:none;background:rgba(13,110,253,0.08);border:2px dashed #0d6efd;border-radius:8px;display:flex;align-items:center;justify-content:center;">
                <div style="background:#fff;padding:14px 22px;border-radius:8px;box-shadow:0 2px 12px rgba(0,0,0,0.15);color:#0d6efd;font-weight:600;display:flex;flex-direction:column;align-items:center;gap:6px;">
                    <i class="fa fa-cloud-upload fa-2x"/>
                    <span t-esc="dropHint"/>
                </div>
            </div>
            <!-- Header: provider + actions (unified with owl2) -->
            <div class="px-3 py-2 bg-white border-bottom o_chatboo_main_header" style="flex-shrink: 0; z-index: 30; display: flex; justify-content: space-between; align-items: center;">
                <div style="display: flex; align-items: center; gap: 8px; min-width: 0; flex: 1;">
                    <div class="o_chatboo_status text-muted opacity-75" style="font-size: 1.75em; line-height: 1; white-space: nowrap;">
                        <t t-if="state.providerModel">
                            <i t-attf-class="fa fa-plug {{ state.connected ? 'text-success' : 'text-danger' }}" style="cursor: pointer;" t-att-title="tipTestConnection" t-on-click="_testConnection"/> <span class="o_chatboo_provider_pick" t-attf-style="position: relative; display: inline-block; font-size: 0.9em; padding: 1px 6px;{{ state.providers.length > 1 ? ' cursor: pointer;' : '' }}" t-att-title="state.providers.length > 1 ? tipChangeProvider : undefined" t-on-click="_toggleProviderMenu()"><t t-if="state.providerHost"><span class="font-weight-normal" style="opacity:0.75;"><t t-esc="state.providerHost"/> → </span></t><strong t-esc="state.providerModel"/><t t-if="state.providers.length > 1"> <i class="fa fa-caret-down" style="opacity:0.5;font-size:0.6em;vertical-align:middle;"/></t><t t-if="state.providerMenuOpen"><div style="position:fixed;inset:0;z-index:1039;background:transparent;" t-on-click.stop="_closeProviderMenu()"/><ul style="position:absolute;top:100%;inset-inline-start:0;z-index:1040;margin:4px 0 0;padding:4px;list-style:none;background:#fff;border:1px solid rgba(0,0,0,0.15);border-radius:8px;box-shadow:0 6px 20px rgba(0,0,0,0.15);min-width:100%;white-space:nowrap;font-size:0.62em;font-weight:normal;color:#333;" t-on-click.stop="_noop()"><t t-foreach="state.providers" t-as="prov" t-key="prov.id"><li t-attf-style="padding:6px 12px;border-radius:6px;cursor:pointer;line-height:1.3;{{ prov.id === state.selectedProviderId ? 'background:rgba(0,0,0,0.06);font-weight:600;color:#111;' : 'color:#333;' }}" t-on-click.stop="_selectProvider(prov.id)"><t t-esc="prov.display || prov.name"/></li></t></ul></t></span>
                        </t>
                        <t t-elif="state.providerName">
                            <i t-attf-class="fa fa-plug {{ state.connected ? 'text-success' : 'text-danger' }}" style="cursor: pointer;" t-att-title="tipTestConnection" t-on-click="_testConnection"/> <t t-esc="state.providerName"/>
                        </t>
                        <t t-if="!state.providerModel and !state.providerName">
                            <t t-esc="tipConnecting"/>
                        </t>
                    </div>
                </div>
                <div class="d-flex" style="gap: 6px;">
                    <button class="btn btn-sm btn-secondary" t-on-click="_createNewSession(true)" t-att-title="tipNewChat">
                        <i class="fa fa-plus"/> <t t-esc="tipNew"/>
                    </button>
                    <button class="btn btn-sm btn-secondary" t-on-click="_showSessions" t-att-title="tipHistory">
                        <i class="fa fa-history"/> <t t-esc="tipHistory"/>
                    </button>
                </div>
            </div>
            
            <!-- Message list: flex fill so the last card stays above the prompt. -->
            <div class="o_chatboo_messages p-3 bg-100" t-ref="messages" style="flex: 1 1 auto; min-height: 0; overflow-y: auto;">
                <t t-foreach="messages" t-as="msg" t-key="msg_index">
                    <div t-attf-class="d-flex mb-2 {{ msg.role === 'user' ? 'justify-content-end' : 'justify-content-start' }}{{ messageWantsWideCanvas(msg) ? ' o_chatboo_message_row--chart' : '' }}"
                         t-att-data-msg-index="msg_index"
                         t-att-data-turn-code="msg.context_info and msg.context_info.turnCode">
                        <div t-attf-class="o_chatboo_message card border-0 shadow-sm p-2 {{ msg.role === 'user' ? 'bg-primary text-white' : 'bg-white' }}{{ messageWantsWideCanvas(msg) ? ' o_chatboo_message--chart' : '' }}" style="border-radius: 8px; position: relative;">
                            <div t-if="messageWantsWideCanvas(msg)"
                                 class="o_chatboo_card_resize"
                                 t-on-pointerdown="_onCardResizeStart"/>
                            <t t-if="msg.role === 'assistant'">
                                <div t-attf-class="d-flex mb-1 o_chatboo_export_bar {{ messageWantsWideCanvas(msg) ? 'justify-content-between' : 'justify-content-end' }}" style="gap: 4px;">
                                    <i t-if="messageWantsWideCanvas(msg)"
                                       class="fa fa-compress o_chatboo_copy_btn text-muted o_chatboo_card_width_reset"
                                       t-att-title="tipRestoreCardWidth"
                                       t-on-click="_resetCardWidth"/>
                                    <span style="display:flex;gap:4px;">
                                    <i class="fa fa-file-pdf-o o_chatboo_copy_btn text-danger" 
                                       style="cursor: pointer; font-size: 1.09375em; opacity: 0.7; transition: opacity 0.2s;"
                                       t-att-title="tipDownloadPdf"
                                       t-att-data-msg-index="msg_index"
                                       t-on-click="_downloadAsPDF"/>
                                    <i class="fa fa-file-excel-o o_chatboo_copy_btn text-success" 
                                       style="cursor: pointer; font-size: 1.09375em; opacity: 0.7; transition: opacity 0.2s;"
                                       t-att-title="tipDownloadExcel"
                                       t-att-data-msg-index="msg_index"
                                       t-on-click="_downloadAsExcel"/>
                                    <i class="fa fa-file-word-o o_chatboo_copy_btn"
                                       style="cursor: pointer; font-size: 1.09375em; opacity: 0.7; transition: opacity 0.2s; color: #2b579a;"
                                       t-att-title="tipDownloadWord"
                                       t-att-data-msg-index="msg_index"
                                       t-on-click="_downloadAsWord"/>
                                    <i t-attf-class="fa fa-copy o_chatboo_copy_btn text-muted" 
                                       style="cursor: pointer; font-size: 1.09375em; opacity: 0.7; transition: opacity 0.2s;"
                                       t-att-title="tipCopyContent"
                                       t-att-data-msg-index="msg_index"
                                       t-att-data-copy-type="'content'"
                                       t-on-click="_copyToClipboard"/>
                                    <i t-attf-class="fa fa-code o_chatboo_copy_btn text-muted" 
                                       style="cursor: pointer; font-size: 1.09375em; opacity: 0.7; transition: opacity 0.2s;"
                                       t-att-title="tipCopyMarkdown"
                                       t-att-data-msg-index="msg_index"
                                       t-att-data-copy-type="'markdown'"
                                       t-on-click="_copyToClipboard"/>
                                    </span>
                                </div>
                                <t t-if="msg.files and msg.files.length">
                                    <div class="o_chatboo_file_banner_list">
                                        <t t-foreach="msg.files" t-as="mfile" t-key="mfile_index">
                                            <a t-if="mfile.url" t-att-href="_fileDownloadHref(mfile)"
                                               t-att-download="_fileDownloadName(mfile)"
                                               t-att-class="_fileBannerCardClass(mfile)"
                                               t-att-title="mfile.name">
                                                <span class="o_chatboo_file_banner_preview" aria-hidden="true">
                                                    <i t-att-class="_fileIconClass(mfile.name, mfile.mimetype)"/>
                                                </span>
                                                <span class="o_chatboo_file_banner_meta">
                                                    <span class="o_chatboo_file_banner_title" t-esc="mfile.name"/>
                                                    <span t-if="_fileSizeLabel(mfile)" class="o_chatboo_file_banner_size"
                                                          t-esc="_fileSizeLabel(mfile)"/>
                                                    <span class="o_chatboo_file_banner_cta" t-esc="tipDownloadFile"/>
                                                </span>
                                            </a>
                                        </t>
                                    </div>
                                </t>
                            </t>
                            <t t-if="msg.role === 'user'">
                                <div class="d-flex justify-content-end mb-1" style="gap: 4px;">
                                    <i t-attf-class="fa fa-copy o_chatboo_copy_btn text-white" 
                                       style="cursor: pointer; font-size: 1.09375em; opacity: 0.7; transition: opacity 0.2s;"
                                       t-att-title="tipCopyClipboard"
                                       t-att-data-msg-index="msg_index"
                                       t-att-data-copy-type="'content'"
                                       t-on-click="_copyToClipboard"/>
                                </div>
                                <t t-if="msg.images and msg.images.length">
                                    <div class="mb-1" style="display:flex;flex-wrap:wrap;gap:4px;">
                                        <t t-foreach="msg.images" t-as="mimg" t-key="mimg_index">
                                            <span style="display:inline-flex;flex-direction:column;align-items:flex-start;">
                                                <a t-att-href="_msgImageUrl(mimg)" target="_blank" rel="noopener"
                                                   t-att-title="_msgImageName(mimg) || tipOpenImage">
                                                    <img t-att-src="_msgImageUrl(mimg)" t-att-alt="_msgImageName(mimg) || 'image'"
                                                         style="max-width:100%;max-height:220px;border-radius:6px;cursor:zoom-in;"/>
                                                </a>
                                                <t t-if="_msgImageName(mimg)">
                                                    <span style="display:block;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;max-width:220px;font-size:0.72em;color:#e8e8e8;"
                                                          t-esc="_msgImageName(mimg)"/>
                                                </t>
                                            </span>
                                        </t>
                                    </div>
                                </t>
                                <t t-if="msg.files and msg.files.length">
                                    <div class="o_chatboo_file_banner_list">
                                        <t t-foreach="msg.files" t-as="mfile" t-key="mfile_index">
                                            <a t-if="mfile.url" t-att-href="_fileDownloadHref(mfile)"
                                               t-att-download="_fileDownloadName(mfile)"
                                               t-att-class="_fileBannerCardClass(mfile)"
                                               t-att-title="mfile.name">
                                                <span class="o_chatboo_file_banner_preview" aria-hidden="true">
                                                    <i t-att-class="_fileIconClass(mfile.name, mfile.mimetype)"/>
                                                </span>
                                                <span class="o_chatboo_file_banner_meta">
                                                    <span class="o_chatboo_file_banner_title" t-esc="mfile.name"/>
                                                    <span t-if="_fileSizeLabel(mfile)" class="o_chatboo_file_banner_size"
                                                          t-esc="_fileSizeLabel(mfile)"/>
                                                    <span class="o_chatboo_file_banner_cta" t-esc="tipDownloadFile"/>
                                                </span>
                                            </a>
                                            <span t-else="" t-att-class="_fileBannerCardClass(mfile)"
                                                  t-att-title="mfile.name">
                                                <span class="o_chatboo_file_banner_preview" aria-hidden="true">
                                                    <i t-att-class="_fileIconClass(mfile.name, mfile.mimetype)"/>
                                                </span>
                                                <span class="o_chatboo_file_banner_meta">
                                                    <span class="o_chatboo_file_banner_title" t-esc="mfile.name"/>
                                                    <span t-if="_fileSizeLabel(mfile)" class="o_chatboo_file_banner_size"
                                                          t-esc="_fileSizeLabel(mfile)"/>
                                                </span>
                                            </span>
                                        </t>
                                    </div>
                                </t>
                            </t>
                            <div class="o_chatboo_content" t-raw="msg.content"/>
                            <div class="o_chatboo_ts_row">
                                <div class="o_chatboo_ts" t-attf-style="font-size: 1.09375em; color: {{ msg.role === 'user' ? '#ffffff' : '#007cba' }};" t-esc="msg.timestamp"/>
                                <t t-if="msg.role === 'assistant'">
                                    <div class="d-flex o_chatboo_export_bar" style="gap: 4px;">
                                        <i class="fa fa-file-pdf-o o_chatboo_copy_btn text-danger"
                                           style="cursor: pointer; font-size: 1.09375em; opacity: 0.7; transition: opacity 0.2s;"
                                           t-att-title="tipDownloadPdf"
                                           t-att-data-msg-index="msg_index"
                                           t-on-click="_downloadAsPDF"/>
                                        <i class="fa fa-file-excel-o o_chatboo_copy_btn text-success"
                                           style="cursor: pointer; font-size: 1.09375em; opacity: 0.7; transition: opacity 0.2s;"
                                           t-att-title="tipDownloadExcel"
                                           t-att-data-msg-index="msg_index"
                                           t-on-click="_downloadAsExcel"/>
                                        <i class="fa fa-file-word-o o_chatboo_copy_btn"
                                           style="cursor: pointer; font-size: 1.09375em; opacity: 0.7; transition: opacity 0.2s; color: #2b579a;"
                                           t-att-title="tipDownloadWord"
                                           t-att-data-msg-index="msg_index"
                                           t-on-click="_downloadAsWord"/>
                                        <i t-attf-class="fa fa-copy o_chatboo_copy_btn text-muted"
                                           style="cursor: pointer; font-size: 1.09375em; opacity: 0.7; transition: opacity 0.2s;"
                                           t-att-title="tipCopyContent"
                                           t-att-data-msg-index="msg_index"
                                           t-att-data-copy-type="'content'"
                                           t-on-click="_copyToClipboard"/>
                                        <i t-attf-class="fa fa-code o_chatboo_copy_btn text-muted"
                                           style="cursor: pointer; font-size: 1.09375em; opacity: 0.7; transition: opacity 0.2s;"
                                           t-att-title="tipCopyMarkdown"
                                           t-att-data-msg-index="msg_index"
                                           t-att-data-copy-type="'markdown'"
                                           t-on-click="_copyToClipboard"/>
                                    </div>
                                </t>
                            </div>
                            <t t-if="msg.model_details and msg.model_details.model">
                                <div class="text-muted" style="font-size: 0.85em;">
                                    <i class="fa fa-microchip" style="margin-right: 4px;"></i>
                                    <t t-esc="msg.model_details.model"/>
                                    <t t-if="msg.model_details.provider"> · <t t-esc="msg.model_details.provider"/></t>
                                </div>
                            </t>
                            <t t-elif="msg.role === 'assistant' and !msg.model_details and !msg.local_ack">
                                <div style="font-size: 0.85em; color: #dc3545;">
                                    <i class="fa fa-exclamation fw-bold" style="margin-right: 4px;"></i>
                                    <span>Sin información del modelo</span>
                                </div>
                            </t>
                            <t t-if="msg.sources and msg.sources.length">
                                <div class="text-muted" style="font-size: 0.85em;">
                                    <i class="fa fa-globe" style="margin-right: 4px;"></i>
                                    Fuente: <t t-esc="msg.sources.join(', ')"/>
                                </div>
                            </t>
                            <t t-if="msg.records and msg.records.length">
                                <div class="o_chatboo_ack_records">
                                    <t t-foreach="msg.records" t-as="mrec" t-key="mrec_index">
                                        <a t-if="mrec.role == 'document'"
                                           t-att-href="_recordUrl(mrec)" target="_blank" rel="noopener"
                                           class="o_chatboo_ack_doc_card"
                                           t-att-title="mrec.model + ' #' + mrec.id">
                                            <span class="o_chatboo_ack_doc_icon">
                                                <i class="fa fa-file-text-o"/>
                                            </span>
                                            <span class="o_chatboo_ack_doc_body">
                                                <span class="o_chatboo_ack_doc_name" t-esc="mrec.name"/>
                                                <span class="o_chatboo_ack_doc_meta" t-esc="mrec.model + ' #' + mrec.id"/>
                                            </span>
                                            <i class="fa fa-external-link o_chatboo_ack_doc_open"/>
                                        </a>
                                    </t>
                                </div>
                            </t>
                            <t t-if="msg.context_info">
                                <t t-set="ctxColor" t-value="msg.context_info.usageColorHex ? msg.context_info.usageColorHex : '#28a745'"/>
                                <t t-set="ctxIcon" t-value="msg.context_info.usageIcon ? msg.context_info.usageIcon : 'fa-bell-o'"/>
                                <div class="o_chatboo_context_info d-flex justify-content-between align-items-center"
                                     style="font-size: 0.85em; cursor: pointer;"
                                     t-on-click="_showContextChart">
                                    <div class="o_chatboo_usage_chips">
                                        <span t-if="msg.context_info.turnCode" class="o_chatboo_usage_chip"
                                              t-att-title="msg.context_info.turnCodeTitle"
                                              t-att-data-turn-code="msg.context_info.turnCode"
                                              t-on-click.stop="_copyTurnCode">
                                            <t t-esc="msg.context_info.turnCode"/>
                                        </span>
                                        <span t-if="msg.context_info.showBuffer" class="o_chatboo_usage_chip"
                                              t-att-title="msg.context_info.bufferTitle"
                                              t-attf-style="color: {{ ctxColor }};">
                                            <i t-attf-class="fa {{ ctxIcon }}" style="margin-right: 4px;"></i>
                                            <t t-esc="msg.context_info.usedK"/>k / <t t-esc="msg.context_info.limitK"/>k (<t t-esc="msg.context_info.usagePercent"/>%)
                                        </span>
                                        <span class="o_chatboo_usage_chip"
                                              t-att-title="msg.context_info.spendTitle">
                                            <t t-esc="msg.context_info.spendLabel"/>
                                        </span>
                                    </div>
                                    <div t-if="msg.context_info.speedTps > 0" t-att-title="msg.context_info.speedTitle">
                                        <i class="fa fa-bolt" style="margin-right: 4px;"></i>
                                        <t t-esc="msg.context_info.speedTps"/> tok/s
                                    </div>
                                </div>
                            </t>
                        </div>
                    </div>
                </t>
                <t t-if="state.thinking">
                    <div class="d-flex justify-content-start mb-3">
                         <div class="bg-white card border-0 shadow-sm p-3 d-flex flex-column" style="border-radius: 8px; gap: 8px;">
                            <div class="d-flex flex-row align-items-center" style="gap: 10px;">
                                <span class="o_chatboo_typing"><span></span><span></span><span></span></span>
                                <span class="text-muted"><t t-esc="state.statusLabel || tipThinking"/></span>
                                <button t-if="state.canCancel" class="btn btn-sm btn-link text-muted p-0 ml-2"
                                        type="button" t-on-click="_cancelStream"
                                        style="text-decoration: none;" t-att-title="tipCancel">
                                    <i class="fa fa-stop-circle-o"/> <t t-esc="tipCancel"/>
                                </button>
                            </div>
                            <t t-if="state.streamingPreview">
                                <div class="o_chatboo_content" t-raw="state.streamingPreview"/>
                            </t>
                         </div>
                    </div>
                </t>
            </div>
            
            <!-- Input Area: Absolute Bottom (Zero Margins) -->
            <div class="o_chatboo_main_footer bg-white border-top" style="flex-shrink: 0; padding: 12px 16px !important; margin: 0 !important; z-index: 40; overflow: visible;">

                <div t-if="state.screenFocusLabel" class="o_chatboo_screen_focus mb-2">
                    <span t-attf-class="badge {{ state.screenFocusEnabled ? 'badge-primary' : 'badge-secondary' }}"
                          style="font-weight:500;font-size:0.78em;cursor:pointer;"
                          t-on-click="toggleScreenFocus"
                          t-att-aria-label="_screenFocusTitle()">
                        <i class="fa fa-crosshairs"/> <t t-esc="state.screenFocusLabel"/>
                    </span>
                </div>

                <div t-if="state.pendingImages.length" class="d-flex flex-wrap mb-2" style="gap:6px;">
                    <t t-foreach="state.pendingImages" t-as="pimg" t-key="pimg_index">
                        <div class="o_chatboo_pending_image d-inline-flex align-items-center p-1 border rounded"
                             style="gap:6px;background:#f8f9fa;">
                            <img t-att-src="pimg" alt="pasted image"
                                 style="height:40px;width:auto;border-radius:4px;"/>
                            <button type="button" class="btn btn-sm btn-link text-danger p-0"
                                    style="text-decoration:none;" t-att-aria-label="tipRemoveImage"
                                    t-on-click="() => _removePendingImage(pimg_index)">
                                <i class="fa fa-times"/>
                            </button>
                        </div>
                    </t>
                </div>

                <div t-if="state.pendingFiles.length" class="d-flex flex-wrap mb-2" style="gap:6px;">
                    <t t-foreach="state.pendingFiles" t-as="pfile" t-key="pfile_index">
                        <div class="o_chatboo_pending_file d-inline-flex align-items-center px-2 py-1 border rounded"
                             style="gap:6px;background:#f1f3f5;color:#212529;border-color:#ced4da !important;font-size:0.8em;max-width:220px;">
                            <i t-att-class="_fileIconClass(pfile.name, pfile.mimetype)" style="color:#495057;"/>
                            <span class="text-truncate" t-esc="pfile.name"/>
                            <button type="button" class="btn btn-sm btn-link text-danger p-0"
                                    style="text-decoration:none;" t-att-aria-label="tipRemoveFile"
                                    t-on-click="() => _removePendingFile(pfile_index)">
                                <i class="fa fa-times"/>
                            </button>
                        </div>
                    </t>
                </div>

                <input type="file" class="o_chatboo_file_input d-none" multiple="multiple"
                       accept=".txt,.md,.csv,.tsv,.log,.json,.xlsx,.xlsm,.xls,.docx,.doc,.pdf,.png,.jpg,.jpeg,.gif,.bmp,.webp,.svg,.ico,image/*,application/pdf,text/csv,application/json,application/vnd.ms-excel,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,application/vnd.ms-excel.sheet.macroEnabled.12,application/msword,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                       t-on-change="onFilesSelected"/>
                <div class="d-flex align-items-start" style="gap: 12px; margin: 0 !important; padding: 0 !important;">
                    <button t-if="state.ttsSupported"
                            type="button"
                            t-attf-class="btn btn-light border o_chatboo_tts_toggle {{ state.ttsEnabled ? 'o_chatboo_tts_on' : '' }}"
                            t-att-aria-label="_ttsTitle()"
                            t-on-click="_toggleTts"
                            t-att-disabled="state.thinking || state.disabled"
                            style="border-radius: 8px; margin: 0 !important;">
                        <img t-att-src="state.ttsEnabled ? '/pns_ai_chatboo/static/src/img/chatboo_tts_volume_on.svg' : '/pns_ai_chatboo/static/src/img/chatboo_tts_volume_off.svg'"
                             alt="" width="22" height="22"/>
                    </button>
                    <div t-attf-class="o_chatboo_prompt_wrap {{ state.promptMultiline ? 'o_chatboo_prompt_has_toggle' : '' }}"
                         t-att-style="'--o-chatboo-prompt-max-lines:' + promptMaxLines">
                        <textarea class="form-control o_chatboo_prompt" rows="1"
                               t-att-placeholder="state.inputPlaceholder"
                               style="font-family: 'Courier New', Courier, monospace; font-size: 1.25em; border: 1px solid #dee2e6; margin: 0 !important;"
                               t-ref="chatInput"
                               t-on-keydown="_onInputKeydown" t-on-input="_onSlashInput" t-on-paste="onPaste"
                               t-att-aria-label="tipHistoryNav"
                               t-att-disabled="state.thinking || state.disabled"/>
                        <button t-if="state.promptMultiline"
                                type="button"
                                class="btn btn-light border o_chatboo_prompt_resize"
                                t-att-aria-label="_tipPromptResize()"
                                t-on-click="_togglePromptCollapsed">
                            <i t-attf-class="fa {{ state.promptCollapsed ? 'fa-chevron-down' : 'fa-chevron-up' }}"/>
                        </button>
                    </div>
                    <button class="btn btn-light border o_chatboo_composer_btn" type="button"
                            t-att-aria-label="tipAttach" t-on-click="onClipClick"
                            t-att-disabled="state.thinking || state.disabled">
                        <i class="fa fa-paperclip"/>
                    </button>
                    <button class="btn btn-primary o_chatboo_composer_btn" type="button"
                            t-on-click="_sendMessage"
                            t-att-aria-label="tipSend"
                            t-att-disabled="state.thinking || state.disabled">
                        <i class="fa fa-paper-plane"/>
                    </button>
                </div>
            </div>
            
            <!-- Session Modal (diseño portado de O19) -->
            <t t-if="state.showSessionModal">
                <div class="o_chatboo_session_modal_backdrop" t-on-click.self="state.showSessionModal = false">
                    <div class="o_chatboo_session_modal" t-on-click.stop="">
                        <div class="modal-header align-items-center border-bottom px-3 py-2">
                            <h5 class="modal-title m-0">Session History</h5>

                            <t t-if="state.sessions.length > 0">
                                <div class="ml-3 mr-auto d-flex align-items-center" style="gap: 12px; border-left: 1px solid #dee2e6; padding-left: 12px;">
                                    <div class="form-check mb-0">
                                        <input type="checkbox" class="form-check-input" id="checkAllSessions"
                                               t-att-checked="state.selectedSessions.length > 0 and state.selectedSessions.length === state.sessions.length"
                                               t-on-change="_toggleAllSessions"/>
                                        <label class="form-check-label" for="checkAllSessions" style="cursor: pointer; user-select: none;">
                                            Select all
                                        </label>
                                    </div>
                                    <button class="btn btn-sm btn-outline-danger"
                                            t-att-disabled="state.selectedSessions.length === 0"
                                            t-on-click="_bulkDeleteSessions">
                                        <i class="fa fa-trash mr-1"/> Delete (<t t-esc="state.selectedSessions.length"/>)
                                    </button>
                                </div>
                            </t>

                            <button type="button" class="close ml-2" t-on-click="state.showSessionModal = false">
                                <span>×</span>
                            </button>
                        </div>
                        <div class="modal-body overflow-auto p-0">
                            <div class="list-group list-group-flush">
                                <t t-foreach="state.sessions" t-as="session" t-key="session.id">
                                    <div class="list-group-item d-flex align-items-center"
                                         style="cursor: pointer;"
                                         t-on-click="_selectSession(session.id)">

                                        <!-- Checkbox column -->
                                        <div class="mr-3" t-on-click.stop="">
                                            <div class="form-check mb-0">
                                                <input type="checkbox" class="form-check-input" t-att-id="'checkSession_' + session.id"
                                                       t-att-checked="state.selectedSessions.includes(session.id)"
                                                       t-on-change="() => _toggleSessionSelection(session.id)"/>
                                                <label class="form-check-label" t-att-for="'checkSession_' + session.id" style="cursor: pointer;"></label>
                                            </div>
                                        </div>

                                        <t t-if="state.editingSessionId === session.id">
                                            <div class="d-flex flex-grow-1" style="gap: 8px;">
                                                <input type="text" class="form-control form-control-sm"
                                                       t-model="state.editingSessionName"
                                                       t-on-keydown="_onRenameInputKeydown"
                                                       t-on-click.stop=""/>
                                                <button class="btn btn-sm btn-success"
                                                        t-on-click.stop="_saveRenameSession"
                                                        t-att-title="tipSave">
                                                    <i class="fa fa-check"/>
                                                </button>
                                                <button class="btn btn-sm btn-secondary"
                                                        t-on-click.stop="_cancelRenameSession"
                                                        t-att-title="tipCancel">
                                                    <i class="fa fa-times"/>
                                                </button>
                                            </div>
                                        </t>
                                        <t t-if="state.editingSessionId !== session.id">
                                            <div class="flex-grow-1">
                                                <div class="d-flex align-items-center">
                                                    <strong t-esc="session.name"/>
                                                    <t t-if="state.currentSessionId === session.id">
                                                        <span class="badge badge-primary ml-2 text-white"><t t-esc="tipCurrent"/></span>
                                                    </t>
                                                </div>
                                                <small class="text-muted">
                                                    <t t-esc="session.message_count || 0"/> <t t-esc="tipMessages"/>
                                                    <t t-if="session.last_used_date">
                                                        · <t t-esc="session.formatted_date"/>
                                                    </t>
                                                </small>
                                            </div>
                                            <div class="btn-group" t-on-click.stop="">
                                                <button class="btn btn-sm btn-link"
                                                        t-on-click="_startRenameSession(session.id, session.name)"
                                                        t-att-title="tipRenameSession">
                                                    <i class="fa fa-edit"/>
                                                </button>
                                                <button class="btn btn-sm btn-link text-danger"
                                                        t-on-click.stop="_deleteSession(session.id)"
                                                        t-att-title="tipDeleteSession">
                                                    <i class="fa fa-trash"/>
                                                </button>
                                            </div>
                                        </t>
                                    </div>
                                </t>
                                <t t-if="state.sessions.length === 0">
                                    <div class="list-group-item text-muted text-center">
                                        <small>No saved sessions. One will be created automatically when you send the first message.</small>
                                    </div>
                                </t>
                            </div>
                        </div>
                        <div class="modal-footer border-top px-3 py-2">
                            <button type="button" class="btn btn-secondary btn-sm" t-on-click="state.showSessionModal = false">
                                Close
                            </button>
                        </div>
                    </div>
                </div>
            </t>
        </div>
    `;

    // --- AbstractAction Wrapper (Odoo 14 Standard) ---
    const ChatbooAction = AbstractAction.extend({
        hasControlPanel: false,
        contentTemplate: null, // We use OWL
        isHistoryActive: false,
        isNewChatActive: false,

        start: function () {
            var self = this;
            return this._super.apply(this, arguments).then(function () {
                // Ensure el is ready
                if (!self.el) {
                    return;
                }

                // FIX ODOO 14 LAYOUT BUGS
                // 1. Force the Action container to occupy full height relative bounds
                $(self.el).css({
                    'height': '100%',
                    'position': 'relative',
                    'display': 'flex',
                    'flex-direction': 'column',
                    'margin-bottom': '0',
                    'padding-bottom': '0'
                });

                // 2. Hard-hide any phantom Control Panel injected by Odoo Action Manager (the cause of the 400px white space)
                var $cp = $(self.el).closest('.o_action_manager').find('.o_control_panel');
                if ($cp.length) {
                    $cp.css('display', 'none', 'important');
                    $cp.hide();
                }

                // Configurar acción por defecto, pero se pueden sobrescribir desde subclases
                var actionContext = {};

                // Extraer el Action Context para el routing basado estrictamente en el tipo de Acción enlazado al submenú
                if (self.isHistoryActive) {
                    actionContext.show_history_modal = true;
                } else if (self.isNewChatActive) {
                    actionContext.new_chat = true;
                } else if (self.action && self.action.context) {
                    // Cuidado con eval checks
                    if (typeof self.action.context === 'string') {
                        actionContext.show_history_modal = self.action.context.indexOf("'show_history_modal': True") !== -1 || self.action.context.indexOf('"show_history_modal": True') !== -1;
                        actionContext.new_chat = self.action.context.indexOf("'new_chat': True") !== -1 || self.action.context.indexOf('"new_chat": True') !== -1;
                    } else {
                        actionContext.show_history_modal = self.action.context.show_history_modal === true || self.action.context.show_history_modal === 'True';
                        actionContext.new_chat = self.action.context.new_chat === true || self.action.context.new_chat === 'True';
                    }
                }

                // ── ALWAYS use singleton: show existing overlay or trigger
                // systray to create it. Menu access = same as systray click. ──

                // Clear badge dot
                var badge = document.querySelector('.o_chatboo_badge');
                if (badge) { badge.classList.add('d-none'); }

                var overlay = document.getElementById('o_chatboo_persistent_overlay');

                if (overlay) {
                    // Singleton already exists — just show it
                    overlay.style.display = 'flex';
                    self._usingSingleton = true;

                    // Dispatch context commands to the living singleton
                    var comp = window.__chatboo_component;
                    if (comp) {
                        if (actionContext.new_chat && comp._createNewSession) {
                            comp._createNewSession(true); // true = clear UI
                        } else if (actionContext.show_history_modal && comp._showSessions) {
                            comp._showSessions();
                        }
                        window.requestAnimationFrame(function () {
                            window.requestAnimationFrame(function () {
                                if (comp._focusChatInput) {
                                    comp._focusChatInput();
                                }
                            });
                        });
                        if (comp._restorePendingVerifications) {
                            comp._restorePendingVerifications();
                        }
                    }
                    return Promise.resolve();
                }

                // Singleton doesn't exist yet — simulate systray click to create it
                var systrayBtn = document.querySelector('.o_chatboo_systray_item');
                if (systrayBtn) {
                    systrayBtn.click();
                    self._usingSingleton = true;
                    return Promise.resolve();
                }

                // Fallback: no systray available (shouldn't happen), mount inline
                var chatbooRpc = function (params) {
                    return self._rpc(params, {shadow: true});
                };
                self.component = new ChatbooComponent(null, {
                    rpc: chatbooRpc,
                    notification: self.displayNotification.bind(self),
                    doAction: self.do_action.bind(self),
                    context: actionContext
                });
                return self.component.mount(self.el).then(function () {
                    if (self.component && self.component._initSession) {
                        self.component._initSession();
                    }
                    if (self.component && self.component._restorePendingVerifications) {
                        self.component._restorePendingVerifications();
                    }
                });
            });
        },

        destroy: function () {
            // NEVER destroy the singleton — only hide the overlay if present
            if (this._usingSingleton) {
                var overlay = document.getElementById('o_chatboo_persistent_overlay');
                if (overlay) {
                    overlay.style.display = 'none';
                    try {
                        core.bus.trigger('chatboo_auth_cue', { notify: false });
                    } catch (_) {}
                }
            } else if (this.component) {
                // Action-mounted component (not singleton): destroy normally
                this.component.destroy();
            }
            this._super.apply(this, arguments);
        }
    });

    // Subclases estables que no dependen del context de Python
    const ChatbooHistoryAction = ChatbooAction.extend({
        isHistoryActive: true,
        // No polling, no setTimeout. The context flag show_history_modal
        // is checked inside mounted() AFTER the session is loaded.
        // This avoids the race condition where the polling reopens the modal.
    });
    const ChatbooNewAction = ChatbooAction.extend({
        isNewChatActive: true,
        // El contexto new_chat:true es pasado como prop al componente.
        // _initSession lo detecta y crea la sesión directamente, sin cargar la anterior.
        // No hace falta llamar _createNewSession por fuera (eliminaba la condición de carrera).
    });

    core.action_registry.add('chatboo.action', ChatbooAction);
    core.action_registry.add('chatboo.history.action', ChatbooHistoryAction);
    core.action_registry.add('chatboo.new.action', ChatbooNewAction);

    return { ChatbooAction: ChatbooAction, ChatbooComponent: ChatbooComponent };
});
