/*
 * Chatboo text-to-speech (Web Speech API).
 *
 * Mode B: icon ON arms TTS. New assistant bubbles auto-read (full text).
 * Click anywhere in the chat anchors reading from that point forward.
 *
 * window.__chatbooTts — preference: localStorage chatboo.tts.enabled
 */
(function () {
    "use strict";

    if (window.__chatbooTts) {
        return;
    }

    var STORAGE_KEY = "chatboo.tts.enabled";
    var IMG_BASE = "/pns_ai_chatboo/static/src/img/";
    var ICON_ON = IMG_BASE + "chatboo_tts_volume_on.svg";
    var ICON_OFF = IMG_BASE + "chatboo_tts_volume_off.svg";
    var MAX_CHARS = 12000;

    var _boundRoots = [];

    function hasApi() {
        return typeof window !== "undefined"
            && "speechSynthesis" in window
            && typeof window.SpeechSynthesisUtterance !== "undefined";
    }

    function readEnabled() {
        try {
            return localStorage.getItem(STORAGE_KEY) === "1";
        } catch (e) {
            return false;
        }
    }

    function writeEnabled(on) {
        try {
            localStorage.setItem(STORAGE_KEY, on ? "1" : "0");
        } catch (e) { /* noop */ }
    }

    function resolveLang() {
        var lang = "";
        try {
            lang = (document.documentElement && document.documentElement.getAttribute("lang"))
                || (document.body && document.body.getAttribute("lang"))
                || "";
        } catch (e) { /* noop */ }
        if (!lang && typeof navigator !== "undefined") {
            lang = navigator.language || navigator.userLanguage || "";
        }
        return (lang || "es-ES").replace("_", "-");
    }

    function pickVoice(lang) {
        if (!hasApi()) {
            return null;
        }
        var voices = window.speechSynthesis.getVoices() || [];
        if (!voices.length) {
            return null;
        }
        var want = (lang || "es").slice(0, 2).toLowerCase();
        for (var i = 0; i < voices.length; i++) {
            var v = voices[i];
            if (v.lang && v.lang.slice(0, 2).toLowerCase() === want) {
                return v;
            }
        }
        for (var j = 0; j < voices.length; j++) {
            if (voices[j].default) {
                return voices[j];
            }
        }
        return voices[0];
    }

    function normalizeText(text) {
        return String(text || "").replace(/\s+/g, " ").trim();
    }

    function capText(text) {
        text = normalizeText(text);
        if (!text || text.length < 2) {
            return "";
        }
        if (text.length > MAX_CHARS) {
            return text.slice(0, MAX_CHARS) + "…";
        }
        return text;
    }

    function stripChrome(root) {
        if (!root || !root.querySelectorAll) {
            return;
        }
        var kill = [
            "script", "style", "button",
            ".o_chatboo_noexport",
            ".o_chatboo_context_info",
            ".o_chatboo_chart_toolbar",
        ];
        kill.forEach(function (sel) {
            var nodes = root.querySelectorAll(sel);
            for (var i = 0; i < nodes.length; i++) {
                nodes[i].remove();
            }
        });
    }

    function extractFullText(html) {
        if (!html || typeof html !== "string") {
            return "";
        }
        var root = document.createElement("div");
        root.innerHTML = html;
        stripChrome(root);
        return capText(root.innerText || root.textContent || "");
    }

    function messageHtml(msg) {
        if (!msg || typeof msg !== "object") {
            return "";
        }
        return msg.formatted_html || msg.htmlSrc || msg.content || "";
    }

    function shouldSkipMessage(msg) {
        if (!msg || msg.role !== "assistant") {
            return true;
        }
        if (msg.local_ack) {
            return true;
        }
        return false;
    }

    function endRangeForRoot(root) {
        var range = document.createRange();
        range.selectNodeContents(root);
        range.collapse(false);
        return range;
    }

    function caretRangeFromPoint(x, y) {
        if (document.caretRangeFromPoint) {
            return document.caretRangeFromPoint(x, y);
        }
        if (document.caretPositionFromPoint) {
            var pos = document.caretPositionFromPoint(x, y);
            if (pos && pos.offsetNode) {
                var range = document.createRange();
                range.setStart(pos.offsetNode, pos.offset || 0);
                range.collapse(true);
                return range;
            }
        }
        return null;
    }

    function textFromRangeToEnd(root, startRange) {
        if (!root) {
            return "";
        }
        var end = endRangeForRoot(root);
        var out = document.createRange();
        try {
            if (startRange && root.contains(startRange.startContainer)) {
                out.setStart(startRange.startContainer, startRange.startOffset);
            } else {
                out.setStart(root, 0);
            }
            out.setEnd(end.endContainer, end.endOffset);
            return capText(out.toString());
        } catch (e) {
            return capText(root.innerText || root.textContent || "");
        }
    }

    function textAfterPointerInInput(input, x, y) {
        if (!input) {
            return "";
        }
        var start = 0;
        if (typeof input.selectionStart === "number" && document.caretRangeFromPoint) {
            var range = caretRangeFromPoint(x, y);
            if (range && (input === range.startContainer || input.contains(range.startContainer))) {
                try {
                    var pre = document.createRange();
                    pre.selectNodeContents(input);
                    pre.setEnd(range.startContainer, range.startOffset);
                    start = pre.toString().length;
                } catch (e2) {
                    start = input.selectionStart || 0;
                }
            } else {
                start = input.selectionStart || 0;
            }
        } else {
            start = input.selectionStart || 0;
        }
        return capText((input.value || "").slice(start));
    }

    function collectForwardFromMessage(messageEl, startRange) {
        if (!messageEl) {
            return "";
        }
        var chunks = [];
        var node = messageEl;
        while (node) {
            var content = node.querySelector
                ? (node.querySelector(".o_chatboo_content") || node)
                : node;
            if (content) {
                var part = node === messageEl
                    ? textFromRangeToEnd(content, startRange)
                    : capText(content.innerText || content.textContent || "");
                if (part) {
                    chunks.push(part);
                }
            }
            node = node.nextElementSibling;
            while (node && !node.classList.contains("o_chatboo_message")) {
                node = node.nextElementSibling;
            }
            if (node && !node.classList.contains("o_chatboo_message")) {
                break;
            }
            if (node && isUserMessageEl(node)) {
                break;
            }
        }
        return capText(chunks.join("\n\n"));
    }

    function isUserMessageEl(el) {
        if (!el || !el.classList) {
            return false;
        }
        return el.classList.contains("o_chatboo_user")
            || (el.classList.contains("bg-primary") && el.classList.contains("text-white"));
    }

    function speakableClickTarget(target) {
        if (!target || !target.closest) {
            return null;
        }
        if (target.closest(".o_chatboo_tts_toggle")) {
            return null;
        }
        if (target.closest("button, a, .dropdown-menu, .o_chatboo_slash")) {
            return null;
        }
        var input = target.closest(".o_chatboo_main_footer input[type='text'], .o_chatboo_main_footer textarea, input.o_chatboo_input");
        if (input) {
            return { kind: "input", el: input };
        }
        var message = target.closest(".o_chatboo_message");
        if (message) {
            return { kind: "message", el: message };
        }
        var content = target.closest(".o_chatboo_content");
        if (content) {
            return { kind: "content", el: content.closest(".o_chatboo_message") || content };
        }
        return null;
    }

    var _voicesHooked = false;

    function ensureVoices() {
        if (!hasApi() || _voicesHooked) {
            return;
        }
        _voicesHooked = true;
        try {
            window.speechSynthesis.onvoiceschanged = function () { /* warm */ };
        } catch (e) { /* noop */ }
    }

    function cancel() {
        if (!hasApi()) {
            return;
        }
        try {
            window.speechSynthesis.cancel();
        } catch (e) { /* noop */ }
    }

    function speakText(text, lang) {
        text = capText(text);
        if (!hasApi() || !text) {
            return false;
        }
        ensureVoices();
        cancel();
        var utter = new window.SpeechSynthesisUtterance(text);
        var useLang = lang || resolveLang();
        utter.lang = useLang;
        var voice = pickVoice(useLang);
        if (voice) {
            utter.voice = voice;
        }
        try {
            window.speechSynthesis.speak(utter);
            return true;
        } catch (e) {
            return false;
        }
    }

    function speakFromEvent(ev) {
        if (!readEnabled()) {
            return false;
        }
        var hit = speakableClickTarget(ev.target);
        if (!hit) {
            return false;
        }
        var x = ev.clientX;
        var y = ev.clientY;
        if (hit.kind === "input") {
            return speakText(textAfterPointerInInput(hit.el, x, y));
        }
        var startRange = caretRangeFromPoint(x, y);
        if (hit.kind === "message") {
            return speakText(collectForwardFromMessage(hit.el, startRange));
        }
        return speakText(textFromRangeToEnd(hit.el, startRange));
    }

    function onRootClick(ev) {
        if (!readEnabled()) {
            return;
        }
        speakFromEvent(ev);
    }

    function bindRoot(root) {
        if (!root || !hasApi()) {
            return;
        }
        for (var i = 0; i < _boundRoots.length; i++) {
            if (_boundRoots[i].root === root) {
                return;
            }
        }
        root.addEventListener("click", onRootClick, true);
        _boundRoots.push({ root: root, fn: onRootClick });
    }

    function unbindRoot(root) {
        for (var i = _boundRoots.length - 1; i >= 0; i--) {
            if (_boundRoots[i].root === root) {
                root.removeEventListener("click", _boundRoots[i].fn, true);
                _boundRoots.splice(i, 1);
            }
        }
    }

    window.__chatbooTts = {
        iconOn: ICON_ON,
        iconOff: ICON_OFF,
        isSupported: function () {
            return hasApi();
        },
        isEnabled: function () {
            return hasApi() && readEnabled();
        },
        setEnabled: function (on) {
            if (!hasApi()) {
                writeEnabled(false);
                return false;
            }
            writeEnabled(!!on);
            if (!on) {
                cancel();
            }
            return readEnabled();
        },
        toggle: function () {
            return this.setEnabled(!readEnabled());
        },
        cancel: cancel,
        bindRoot: bindRoot,
        unbindRoot: unbindRoot,
        extractFullText: extractFullText,
        speakText: speakText,
        speakHtml: function (html, lang) {
            return speakText(extractFullText(html), lang);
        },
        speakFromEvent: speakFromEvent,
        speakMessage: function (msg, lang) {
            if (shouldSkipMessage(msg)) {
                return false;
            }
            return this.speakHtml(messageHtml(msg), lang);
        },
    };
})();
