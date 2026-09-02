/**
 * Chatboo SSE stream protocol — shared between owl1 and owl2 clients.
 *
 * Handles the contract with pns_ai_mcp AgentEngine:
 *   - token   → incremental LLM text
 *   - replace → server-rendered HTML body (tables from relaxaicode)
 *   - status, done, verification, error → handled by stack-specific UI code
 *
 * Loaded as a plain script (global ChatbooSse). Deploy copies common/ into the
 * stack addon via i.sh before Odoo loads assets.
 */
(function (global) {
    "use strict";

    var FOOTER_OPEN = '<div class="mt-2 o_chatboo_prose_host o_chatboo_prose" style="font-size:0.97em;">';
    var FOOTER_CLOSE = "</div>";

    /**
     * @returns {{ acc: string, replaceBody: string|null, replaceFooter: string }}
     */
    function createStreamState() {
        return {
            acc: "",
            replaceBody: null,
            replaceFooter: "",
        };
    }

    /**
     * Parse one SSE block ("event: …\\ndata: …") into a plain object.
     * @param {string} raw
     * @returns {object|null}
     */
    function parseSseBlock(raw) {
        if (!raw) {
            return null;
        }
        var eventName = "token";
        var dataStr = "";
        var lines = raw.split("\n");
        for (var i = 0; i < lines.length; i++) {
            var line = lines[i];
            if (line.indexOf("event:") === 0) {
                eventName = line.slice(6).trim();
            } else if (line.indexOf("data:") === 0) {
                dataStr += line.slice(5).trim();
            }
        }
        if (!dataStr) {
            return null;
        }
        try {
            var data = JSON.parse(dataStr);
            data.event = data.event || eventName;
            return data;
        } catch (e) {
            return { event: eventName, content: dataStr };
        }
    }

    /**
     * Append a token chunk; after replace, tokens become the summary footer.
     * @param {object} state
     * @param {string} content
     * @param {function(string): string} formatFooterHtml
     * @returns {object} state (mutated)
     */
    function applyToken(state, content, formatFooterHtml) {
        if (state.replaceBody) {
            state.replaceFooter = (state.replaceFooter || "") + content;
            var footerTrimmed = state.replaceFooter.trim();
            if (footerTrimmed) {
                var footerHtml = formatFooterHtml ? formatFooterHtml(footerTrimmed) : footerTrimmed;
                state.acc = state.replaceBody + FOOTER_OPEN + footerHtml + FOOTER_CLOSE;
            } else {
                state.acc = state.replaceBody;
            }
        } else {
            state.acc += content;
        }
        return state;
    }

    /**
     * Replace accumulated text with server-rendered HTML (direct_formatted).
     * @param {object} state
     * @param {string} htmlContent
     * @returns {object} state (mutated)
     */
    function applyReplace(state, htmlContent) {
        state.replaceBody = htmlContent;
        state.replaceFooter = "";
        state.acc = htmlContent;
        return state;
    }

    /**
     * True when acc has non-whitespace visible text (strip HTML tags).
     * @param {string} acc
     * @returns {boolean}
     */
    function hasVisibleContent(acc) {
        return !!(acc && String(acc).replace(/<[^>]*>/g, "").trim());
    }

    /**
     * True if text looks like a Markdown footer (headers, bold lead, list, table).
     * @param {string} t
     * @returns {boolean}
     */
    function looksLikeMarkdownTail(t) {
        var s = (t || "").replace(/^\s+/, "");
        if (!s) {
            return false;
        }
        // Lead markers, or prose prefix + glued heading (e.g. "fuerzo….## Análisis")
        if (/^(#{1,6}\s|\*\*|[-*+]\s|\d+\.\s|\|)/.test(s)) {
            return true;
        }
        var head = s.slice(0, 1200);
        return /#{1,6}\s/.test(head) || /\*\*[^*\n]{2,120}\*\*/.test(head);
    }

    /**
     * Insert newlines before glued ATX headers (e.g. "texto.## Título").
     * Showdown needs a line break; the model often streams without one.
     * Do NOT touch pipe characters: a global "|…|" rewrite shreds Markdown
     * tables (`| Año | Ventas |` → broken rows / stray #).
     * @param {string} md
     * @returns {string}
     */
    function normalizeGluedMarkdown(md) {
        var s = String(md || "").replace(/([^\n])(#{1,6}\s)/g, "$1\n\n$2");
        // Model often emits a lone "#" between sections — drop orphans.
        s = s.replace(/^[ \t]*#{1,6}[ \t]*$/gm, "");
        // "#\nTitle" → "# Title" so ATX parsers see a real heading.
        s = s.replace(/^(#{1,6})[ \t]*\n+([^\n#][^\n]{0,100})$/gm, "$1 $2");
        return s;
    }

    /**
     * True if a fenced body looks like real source code (keep as &lt;pre&gt;).
     * Inverted rule: we do NOT catalog business dump formats — if it is not
     * code, unwrap the fence so Showdown never paints a dark data dump.
     * @param {string} body
     * @returns {boolean}
     */
    function looksLikeSourceCode(body) {
        var s = String(body || "");
        if (!s.trim()) {
            return false;
        }
        if (/^#!\//m.test(s)) {
            return true;
        }
        if (/\b(function|def |class |import |from .+ import |const |let |var |return |package |public |private |protected |#include|using |fn |=>|:=|SELECT|INSERT|UPDATE|DELETE|CREATE|ALTER|DROP)\b/.test(s)) {
            return true;
        }
        // HTML/XML snippet (2+ tags).
        if ((s.match(/<\/?[a-zA-Z][\w:-]*/g) || []).length >= 2) {
            return true;
        }
        // Balanced braces with indentation → likely code.
        var braceOpen = (s.match(/[{]/g) || []).length;
        var braceClose = (s.match(/[}]/g) || []).length;
        if (braceOpen >= 2 && braceClose >= 2 && /^\s{2,}\S/m.test(s)) {
            return true;
        }
        return false;
    }

    /**
     * @deprecated Use !looksLikeSourceCode. Kept as alias for older callers.
     * @param {string} body
     * @returns {boolean}
     */
    function looksLikeBusinessDataDump(body) {
        return !looksLikeSourceCode(body);
    }

    /**
     * True if parsed JSON looks like a list of homogeneous row dicts.
     * @param {*} parsed
     * @returns {boolean}
     */
    function isTabulableJson(parsed) {
        var rows = null;
        if (Array.isArray(parsed) && parsed.length && parsed[0] && typeof parsed[0] === "object"
                && !Array.isArray(parsed[0])) {
            rows = parsed;
        } else if (parsed && typeof parsed === "object" && !Array.isArray(parsed)) {
            if (Array.isArray(parsed.data) && parsed.data.length
                    && parsed.data[0] && typeof parsed.data[0] === "object"
                    && !Array.isArray(parsed.data[0])) {
                rows = parsed.data;
            } else if (Array.isArray(parsed.items) && parsed.items.length
                    && parsed.items[0] && typeof parsed.items[0] === "object"
                    && !Array.isArray(parsed.items[0])) {
                rows = parsed.items;
            }
        }
        return !!(rows && rows.length);
    }

    /**
     * Diagnostic / probe payloads (counts, state tuples…) must never paint as
     * a dark JSON &lt;pre&gt; in the chat — they are intermediate tool junk.
     * @param {*} parsed
     * @returns {boolean}
     */
    function isDiagnosticJsonDump(parsed) {
        if (!parsed || typeof parsed !== "object") {
            return false;
        }
        if (isTabulableJson(parsed)) {
            return false;
        }
        if (parsed.formatted_text || parsed.data_rendered) {
            return false;
        }
        // Bare object with scalars / nested lists of non-dicts → probe.
        if (!Array.isArray(parsed)) {
            return true;
        }
        // Array of non-objects (ids, tuples…) → not a table.
        return !(parsed.length && parsed[0] && typeof parsed[0] === "object"
            && !Array.isArray(parsed[0]));
    }

    /**
     * Unwrap Markdown fences that are not real source code / keep JSON path.
     * Datasets belong in server-rendered HTML (SSE replace), not dark &lt;pre&gt;.
     * @param {string} md
     * @returns {string}
     */
    function unwrapNonCodeFences(md) {
        var out = String(md || "").replace(
            /```([^\n`]*)\r?\n([\s\S]*?)```/g,
            function (full, langRaw, body) {
                var lang = String(langRaw || "").trim().toLowerCase();
                var raw = String(body || "").trim();

                // JSON: drop diagnostic bags; bare tabulable rows for table promote.
                if (!lang || lang === "json" || lang === "javascript" || lang === "js") {
                    if ((raw.charAt(0) === "{" || raw.charAt(0) === "[")
                            && (raw.slice(-1) === "}" || raw.slice(-1) === "]")) {
                        try {
                            var parsed = JSON.parse(raw);
                            if (isDiagnosticJsonDump(parsed)) {
                                return "\n\n";
                            }
                            if (isTabulableJson(parsed)) {
                                return "\n\n" + raw + "\n\n";
                            }
                            // Explicit json lang + non-tabulable object → drop fence noise.
                            if (lang === "json") {
                                return "\n\n";
                            }
                        } catch (e) {
                            // fall through
                        }
                    }
                }

                // Body decides — lang tags are often wrong (```python around dumps).
                if (looksLikeSourceCode(raw)) {
                    return full;
                }
                return "\n\n" + String(body).replace(/^\n+|\n+$/g, "") + "\n\n";
            }
        );
        return out;
    }

    /** @deprecated Alias — prefer unwrapNonCodeFences. */
    function unwrapBusinessDataFences(md) {
        return unwrapNonCodeFences(md);
    }

    /**
     * Prepare model Markdown for display: unwrap non-code fences, normalize headers.
     * Tabular data must arrive via SSE replace (server HTML), not client parsers.
     * @param {string} md
     * @returns {{ markdown: string }}
     */
    function prepareMarkdownForDisplay(md) {
        return {
            markdown: normalizeGluedMarkdown(unwrapNonCodeFences(md || "")),
        };
    }

    /**
     * Split server HTML table + trailing Markdown prose (common after data_rendered).
     * Production pattern: `...</div>## Análisis…` (no newline). Returns null if
     * there is no clear HTML body + markdown tail.
     * @param {string} text
     * @returns {{ html: string, md: string }|null}
     */
    function splitHtmlAndMarkdownTail(text) {
        var s = String(text || "");
        if (s.indexOf("<") < 0) {
            return null;
        }
        if (s.indexOf("<table") < 0 && s.indexOf("table-responsive") < 0
                && s.indexOf("o_chatboo_data_table") < 0) {
            return null;
        }
        var marker = "</div>";
        var lastGood = -1;
        var pos = 0;
        while (true) {
            var i = s.indexOf(marker, pos);
            if (i < 0) {
                break;
            }
            var after = s.slice(i + marker.length);
            if (looksLikeMarkdownTail(after)) {
                lastGood = i + marker.length;
            }
            pos = i + 1;
        }
        if (lastGood < 0) {
            return null;
        }
        var html = s.slice(0, lastGood);
        var md = s.slice(lastGood).replace(/^\s+/, "");
        if (!html || !md) {
            return null;
        }
        return { html: html, md: normalizeGluedMarkdown(md) };
    }

    /**
     * Merge HTML body + markdown footer (same wrapper as live SSE footer).
     * @param {string} html
     * @param {string} footerHtml already converted (or escaped) HTML
     * @returns {string}
     */
    function mergeHtmlWithFooter(html, footerHtml) {
        var foot = (footerHtml || "").trim();
        if (!foot) {
            return html;
        }
        return html + FOOTER_OPEN + foot + FOOTER_CLOSE;
    }

    var api = {
        FOOTER_OPEN: FOOTER_OPEN,
        FOOTER_CLOSE: FOOTER_CLOSE,
        createStreamState: createStreamState,
        parseSseBlock: parseSseBlock,
        applyToken: applyToken,
        applyReplace: applyReplace,
        hasVisibleContent: hasVisibleContent,
        looksLikeMarkdownTail: looksLikeMarkdownTail,
        normalizeGluedMarkdown: normalizeGluedMarkdown,
        looksLikeSourceCode: looksLikeSourceCode,
        looksLikeBusinessDataDump: looksLikeBusinessDataDump,
        isTabulableJson: isTabulableJson,
        isDiagnosticJsonDump: isDiagnosticJsonDump,
        unwrapNonCodeFences: unwrapNonCodeFences,
        unwrapBusinessDataFences: unwrapBusinessDataFences,
        prepareMarkdownForDisplay: prepareMarkdownForDisplay,
        splitHtmlAndMarkdownTail: splitHtmlAndMarkdownTail,
        mergeHtmlWithFooter: mergeHtmlWithFooter,
    };

    global.ChatbooSse = api;
})(typeof globalThis !== "undefined" ? globalThis : typeof window !== "undefined" ? window : this);
