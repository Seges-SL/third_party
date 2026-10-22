/* SPDX-License-Identifier: Apache-2.0 */
/* Copyright (C) 2026 Patanegra Soft <https://patanegra.com> */
/**
 * Chatboo turn — what owl1 and owl2 do the same way when they send a turn.
 *
 *   - streamUrl / buildPayload → the POST to /chatboo/stream
 *   - refusal                  → why the server said no, in words
 *   - readEvents               → SSE frames, one parsed event at a time
 *   - modelTurns / clipForLlm / contentForLlm → history sent to the model
 *
 * What each event does on screen stays in each client. So does the
 * Content-Type: Odoo 14 needs text/plain on this http route.
 *
 * Loaded as a plain script after chatboo_sse.js (global ChatbooTurn).
 */
(function (global) {
    "use strict";

    var STREAM_PATH = "/chatboo/stream";
    var USER_CLIP = 4000;
    var FAT_CHARS = 2500;

    function streamUrl(csrfToken) {
        return STREAM_PATH + "?csrf_token=" + encodeURIComponent(csrfToken || "");
    }

    /**
     * Rows ticked in the answer go out with this sentence and are spent by it.
     * @returns {Array}
     */
    function takeRowMarks() {
        var marks = global.ChatbooRowMarks;
        return marks ? marks.take() : [];
    }

    /**
     * @param {Object} turn
     * @param {*} turn.sessionId
     * @param {string} turn.message
     * @param {Array} turn.history
     * @param {*} turn.providerId
     * @param {*} [turn.screenContext]
     * @param {Array} [turn.images]
     * @param {Array} [turn.imageNames]
     * @param {Array} [turn.files]
     * @returns {Object}
     */
    function buildPayload(turn) {
        var payload = {
            session_id: turn.sessionId,
            message: turn.message,
            history: turn.history,
            provider_id: turn.providerId || null,
        };
        if (turn.screenContext) {
            payload.screen_context = turn.screenContext;
        }
        var refs = takeRowMarks();
        if (refs.length) {
            payload.refs = refs;
        }
        if (turn.images && turn.images.length) {
            payload.images = turn.images;
        }
        if (turn.imageNames && turn.imageNames.length) {
            payload.image_names = turn.imageNames;
        }
        if (turn.files && turn.files.length) {
            payload.files = turn.files;
        }
        return payload;
    }

    /**
     * Our own refusals are JSON with ``error``. Odoo's own 400 (a stale
     * CSRF token after the session changed) is an HTML page.
     * @param {Response} resp
     * @param {string} sessionChanged - the client's translated sentence
     * @returns {Promise<string>}
     */
    async function refusal(resp, sessionChanged) {
        var body = null;
        try {
            body = await resp.json();
        } catch (e) {
            body = null;
        }
        if (body && body.error) {
            return String(body.error);
        }
        if (resp.status === 400) {
            return sessionChanged;
        }
        return "HTTP " + resp.status;
    }

    /**
     * Read the SSE body until it ends.
     * @param {Response} resp
     * @param {function(Object)} onEvent - each parsed event, in order
     * @param {function()} [onData] - each chunk received (idle watchdog)
     * @returns {Promise<void>}
     */
    async function readEvents(resp, onEvent, onData) {
        var reader = resp.body.getReader();
        var decoder = new TextDecoder("utf-8");
        var buffer = "";
        for (;;) {
            var step = await reader.read();
            if (step.done) {
                return;
            }
            if (onData) {
                onData();
            }
            buffer += decoder.decode(step.value, { stream: true });
            var sep;
            while ((sep = buffer.indexOf("\n\n")) !== -1) {
                var block = buffer.slice(0, sep);
                buffer = buffer.slice(sep + 2);
                var evt = global.ChatbooSse.parseSseBlock(block);
                if (evt) {
                    onEvent(evt);
                }
            }
        }
    }

    function isOfftopic(m) {
        if (m && (m.verification_ack || (m.meta && m.meta.verification_ack))) {
            return false;
        }
        return !!(m && (m.offtopic || m.local_ack || (m.meta && m.meta.local_ack)));
    }

    /**
     * Messages the model may see: no system lines, no off-topic exchange.
     * @param {Array} messages
     * @param {number} [excludeTail]
     * @returns {Array}
     */
    function modelTurns(messages, excludeTail) {
        var list = messages || [];
        var base = excludeTail ? list.slice(0, -excludeTail) : list.slice();
        return base.filter(function (m) {
            return m && m.role !== "system" && !isOfftopic(m);
        });
    }

    function clipForLlm(text, limit) {
        var s = (text == null) ? "" : String(text);
        if (!limit || s.length <= limit) {
            return s;
        }
        return s.slice(0, Math.max(0, limit - 1)).replace(/\s+$/, "") + "…";
    }

    /**
     * Fallback when backend_history is missing: never replay on-screen
     * tables (cell text saturates prefill). Matches history_compact.py.
     * @param {*} text
     * @param {function(string):string} [toPlain] - HTML to text, if the client wants it
     * @returns {string}
     */
    function contentForLlm(text, toPlain) {
        var s = (text == null) ? "" : String(text);
        if (s.indexOf("[On-screen artifact") === 0) {
            return s;
        }
        var fat = s.length > FAT_CHARS
            || /<table\b/i.test(s)
            || s.indexOf("o_ai_table_block") >= 0
            || s.indexOf("data-ai-dataset") >= 0;
        if (!fat) {
            if (toPlain && s.indexOf("<") >= 0) {
                return (toPlain(s) || s).trim();
            }
            return s;
        }
        return "[On-screen artifact | kind=table | ~" + s.length + " characters]\n"
            + "The full document is already visible to the user. Do not reprint the rows. "
            + "Cached dataset is previous_result if you need to reformat or recompute. "
            + "Use tools for a new query.";
    }

    global.ChatbooTurn = {
        USER_CLIP: USER_CLIP,
        streamUrl: streamUrl,
        buildPayload: buildPayload,
        refusal: refusal,
        readEvents: readEvents,
        isOfftopic: isOfftopic,
        modelTurns: modelTurns,
        clipForLlm: clipForLlm,
        contentForLlm: contentForLlm,
    };
})(typeof globalThis !== "undefined" ? globalThis : typeof window !== "undefined" ? window : this);
