/**
 * Chatboo context-occupancy stats — shared between owl1 and owl2.
 *
 * The analysis modal only shows turns that occupy the provider buffer
 * (used > 0). No inferred “fixed load vs history”: one bar = last occupying
 * turn vs its cap; the sparkline is sent/cap % across those turns.
 *
 * Loaded as a plain script (global ChatbooContextStats). Deploy copies
 * common/ into the stack addon via i.sh before Odoo loads assets.
 */
(function (global) {
    "use strict";

    function esc(s) {
        return String(s == null ? "" : s)
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;");
    }

    function colorOf(percent) {
        var p = Number(percent) || 0;
        if (p > 80) {
            return "#dc3545";
        }
        if (p > 60) {
            return "#ffc107";
        }
        return "#28a745";
    }

    function stripQuestion(text) {
        return String(text == null ? "" : text)
            .replace(/<[^>]*>/g, " ")
            .replace(/&nbsp;/g, " ")
            .replace(/&amp;/g, "&")
            .replace(/&lt;/g, "<")
            .replace(/&gt;/g, ">")
            .replace(/\s+/g, " ")
            .trim();
    }

    function isSystemUserNote(text) {
        return /^\[Resultado del sistema\]/i.test(stripQuestion(text));
    }

    function isOfftopicUser(msg) {
        return !!(msg && (
            msg.offtopic
            || msg.local_ack
            || (msg.meta && msg.meta.local_ack)
        ));
    }

    function isLocalAssistant(msg) {
        return !!(msg && (
            msg.local_ack
            || (msg.meta && msg.meta.local_ack)
        ));
    }

    function storedUserPrompt(msg) {
        if (!msg) {
            return "";
        }
        var meta = msg.meta || {};
        var info = msg.context_info || msg.contextInfo || {};
        return stripQuestion(
            msg.user_prompt
            || meta.user_prompt
            || info.userPrompt
            || ""
        );
    }

    /**
     * Question that belongs to this assistant turn.
     *
     * Prefer the prompt stored on the assistant (worker / live turn). Fallback:
     * nearest preceding real user, without crossing another non-local assistant.
     * Do NOT FIFO-pair “every user with the next occupying assistant”: a stray
     * “hola” without usage steals the next expensive turn’s label.
     */
    function questionForAssistant(messages, asstIndex) {
        var list = messages || [];
        var asst = list[asstIndex];
        var stored = storedUserPrompt(asst);
        if (stored) {
            return stored;
        }
        var i;
        var m;
        var text;
        for (i = asstIndex - 1; i >= 0; i--) {
            m = list[i];
            if (!m) {
                continue;
            }
            if (m.role === "assistant") {
                if (!isLocalAssistant(m)) {
                    break;
                }
                continue;
            }
            if (m.role === "user" && !isOfftopicUser(m)) {
                text = stripQuestion(m.raw || m.content || "");
                if (text && !isSystemUserNote(text)) {
                    return text;
                }
            }
        }
        return "";
    }

    function occupyingRows(rows) {
        var src = rows || [];
        var out = [];
        var i;
        var r;
        for (i = 0; i < src.length; i++) {
            if ((Number(src[i].used) || 0) > 0) {
                r = {};
                Object.keys(src[i]).forEach(function (k) {
                    r[k] = src[i][k];
                });
                r.n = out.length + 1;
                r.percent = Number(r.percent) || 0;
                out.push(r);
            }
        }
        return out;
    }

    function lastOccupying(rows) {
        var occ = occupyingRows(rows);
        return occ.length ? occ[occ.length - 1] : null;
    }

    function occupancyWidthPct(percent) {
        var p = Number(percent) || 0;
        if (p <= 0) {
            return 0;
        }
        return Math.min(100, p);
    }

    function occupancyBarHtml(percent, height) {
        var h = height || 14;
        var w = occupancyWidthPct(percent);
        var c = colorOf(percent);
        return '<div style="display:flex;background:#eee;border-radius:5px;height:'
            + h + 'px;overflow:hidden;">'
            + '<div style="height:100%;width:' + w + "%;background:" + c
            + ';"></div></div>';
    }

    function rowBarHtml(percent) {
        var w = occupancyWidthPct(percent);
        var c = colorOf(percent);
        return '<div style="display:flex;background:#eee;border-radius:4px;height:10px;overflow:hidden;">'
            + '<div style="height:100%;width:' + w + "%;background:" + c
            + ';"></div></div>';
    }

    function sparklineSvg(rows) {
        var occ = occupyingRows(rows);
        if (!occ.length) {
            return "";
        }
        var W = 640;
        var H = 56;
        var padL = 10;
        var padR = 10;
        var padT = 8;
        var padB = 8;
        var innerW = W - padL - padR;
        var innerH = H - padT - padB;
        var maxP = 100;
        var i;
        for (i = 0; i < occ.length; i++) {
            if (occ[i].percent > maxP) {
                maxP = occ[i].percent;
            }
        }
        function xy(idx, pct) {
            var x = padL + (occ.length === 1
                ? innerW / 2
                : (idx / (occ.length - 1)) * innerW);
            var y = padT + innerH * (1 - ((Number(pct) || 0) / maxP));
            return {x: x, y: y};
        }
        var pts = [];
        for (i = 0; i < occ.length; i++) {
            pts.push(xy(i, occ[i].percent));
        }
        var line = pts.map(function (p) {
            return p.x.toFixed(1) + "," + p.y.toFixed(1);
        }).join(" ");
        var y100 = xy(0, 100).y;
        var svg = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 '
            + W + " " + H + '" width="100%" height="' + H
            + '" preserveAspectRatio="xMidYMid meet" role="img">';
        svg += '<line x1="' + padL + '" y1="' + y100.toFixed(1)
            + '" x2="' + (W - padR) + '" y2="' + y100.toFixed(1)
            + '" stroke="#cbd5e1" stroke-dasharray="4 3" stroke-width="1"/>';
        if (pts.length > 1) {
            svg += '<polyline fill="none" stroke="#64748b" stroke-width="1.75" points="'
                + line + '"/>';
        }
        for (i = 0; i < pts.length; i++) {
            var last = i === pts.length - 1;
            var r = last ? 4.5 : 3;
            var fill = colorOf(occ[i].percent);
            var title = "#" + occ[i].n
                + (occ[i].turnCode ? " · " + occ[i].turnCode : "")
                + " · " + (occ[i].usedK || "?") + "k · "
                + occ[i].percent.toFixed(1) + "%";
            svg += '<circle cx="' + pts[i].x.toFixed(1) + '" cy="'
                + pts[i].y.toFixed(1) + '" r="' + r + '" fill="' + fill + '">'
                + "<title>" + esc(title) + "</title></circle>";
        }
        svg += "</svg>";
        return svg;
    }

    function safeTurnToken(code) {
        return String(code == null ? "" : code).replace(/[^A-Za-z0-9_-]/g, "");
    }

    function findTurnBubble(root, turnCode, messageIndex) {
        if (!root) {
            return null;
        }
        var token = safeTurnToken(turnCode);
        var el = null;
        if (token) {
            el = root.querySelector('[data-turn-code="' + token + '"]');
        }
        if (!el && messageIndex !== undefined && messageIndex !== null && messageIndex !== "") {
            el = root.querySelector('[data-msg-index="' + String(messageIndex) + '"]');
        }
        if (!el) {
            return null;
        }
        return el.closest(".o_chatboo_message") || el.closest(".d-flex") || el;
    }

    function flashTurnBubble(bubble) {
        if (!bubble) {
            return;
        }
        if (bubble.scrollIntoView) {
            bubble.scrollIntoView({behavior: "smooth", block: "center"});
        }
        var prev = bubble.style.boxShadow;
        bubble.style.transition = "box-shadow 0.3s";
        bubble.style.boxShadow = "0 0 0 3px #0d6efd";
        setTimeout(function () {
            bubble.style.boxShadow = prev || "";
        }, 2000);
    }

    global.ChatbooContextStats = {
        occupyingRows: occupyingRows,
        lastOccupying: lastOccupying,
        colorOf: colorOf,
        occupancyWidthPct: occupancyWidthPct,
        occupancyBarHtml: occupancyBarHtml,
        rowBarHtml: rowBarHtml,
        sparklineSvg: sparklineSvg,
        esc: esc,
        stripQuestion: stripQuestion,
        storedUserPrompt: storedUserPrompt,
        questionForAssistant: questionForAssistant,
        safeTurnToken: safeTurnToken,
        findTurnBubble: findTurnBubble,
        flashTurnBubble: flashTurnBubble,
    };
})(typeof globalThis !== "undefined" ? globalThis : typeof window !== "undefined" ? window : this);
