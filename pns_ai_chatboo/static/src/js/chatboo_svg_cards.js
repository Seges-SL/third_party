/**
 * Chatboo SVG cards — hydrate data-chatboo-card JSON (clock / fact / link).
 * Clock/fact: click opens/downloads the SVG (blob), like a PDF chip.
 * Link: real <a> banner (same gesture as the map card).
 * SPDX-License-Identifier: Apache-2.0
 */
(function (global) {
    "use strict";

    function escapeXml(value) {
        return String(value == null ? "" : value)
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;");
    }

    function parseIso(iso) {
        if (!iso) {
            return null;
        }
        var d = new Date(iso);
        if (isNaN(d.getTime())) {
            return null;
        }
        return d;
    }

    function isoHasOffset(iso) {
        return /(?:Z|[+-]\d{2}:?\d{2})$/i.test(String(iso || ""));
    }

    function wallClockFromIso(iso) {
        var m = String(iso || "").match(/T(\d{2}):(\d{2})(?::(\d{2}))?/);
        if (!m) {
            return null;
        }
        return { h: +m[1], min: +m[2], s: +(m[3] || 0) };
    }

    function clockParts(card) {
        var iso = card && card.iso;
        var tz = card && card.tz;
        if (isoHasOffset(iso)) {
            var wall = wallClockFromIso(iso);
            if (wall) {
                return wall;
            }
        }
        var parsed = iso;
        if (iso && !isoHasOffset(iso) && String(iso).indexOf("T") >= 0) {
            parsed = String(iso) + "Z";
        }
        var d = parseIso(parsed);
        if (!d) {
            return null;
        }
        if (tz) {
            try {
                var fmt = new Intl.DateTimeFormat("en-GB", {
                    timeZone: tz,
                    hour: "2-digit",
                    minute: "2-digit",
                    second: "2-digit",
                    hour12: false,
                });
                var map = {};
                fmt.formatToParts(d).forEach(function (p) {
                    map[p.type] = p.value;
                });
                if (map.hour != null) {
                    return {
                        h: +map.hour,
                        min: +map.minute,
                        s: +(map.second || 0),
                    };
                }
            } catch (e) {
                /* fall through */
            }
        }
        return { h: d.getHours(), min: d.getMinutes(), s: d.getSeconds() };
    }

    function pad2(n) {
        return (n < 10 ? "0" : "") + n;
    }

    function formatClockLabel(parts) {
        return pad2(parts.h) + ":" + pad2(parts.min);
    }

    function clockLocale() {
        var doc = global.document;
        if (doc && doc.documentElement && doc.documentElement.lang) {
            return String(doc.documentElement.lang).replace(/_/g, "-");
        }
        return undefined;
    }

    function formatClockDate(card) {
        var iso = card && card.iso;
        if (!iso) {
            return "";
        }
        var parsed = iso;
        if (!isoHasOffset(iso) && String(iso).indexOf("T") >= 0) {
            parsed = String(iso) + "Z";
        }
        var d = parseIso(parsed);
        var opts = { weekday: "short", day: "numeric", month: "short" };
        if (card.tz) {
            opts.timeZone = card.tz;
        }
        if (d) {
            try {
                return new Intl.DateTimeFormat(clockLocale(), opts).format(d);
            } catch (e) {
                /* fall through */
            }
        }
        var m = String(iso).match(/^(\d{4})-(\d{2})-(\d{2})/);
        return m ? m[3] + "/" + m[2] : "";
    }

    function svgClock(card) {
        var parts = clockParts(card);
        if (!parts) {
            return null;
        }
        var hours = parts.h % 12;
        var minutes = parts.min;
        var seconds = parts.s;
        var hourAng = (hours + minutes / 60) * 30;
        var minAng = (minutes + seconds / 60) * 6;
        var title = escapeXml(card.title || formatClockLabel(parts));
        var value = escapeXml(formatClockLabel(parts));
        var dateLabel = escapeXml(formatClockDate(card));
        var ticks = "";
        var i;
        for (i = 0; i < 12; i++) {
            var a = (i * 30) * Math.PI / 180;
            var x1 = 80 + Math.sin(a) * 48;
            var y1 = 72 - Math.cos(a) * 48;
            var x2 = 80 + Math.sin(a) * 54;
            var y2 = 72 - Math.cos(a) * 54;
            ticks +=
                '<line x1="' + x1.toFixed(1) + '" y1="' + y1.toFixed(1) +
                '" x2="' + x2.toFixed(1) + '" y2="' + y2.toFixed(1) +
                '" stroke="#5b6b7a" stroke-width="2"/>';
        }
        return (
            '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 160 184" ' +
            'width="160" height="184" role="img">' +
            '<rect width="160" height="184" rx="8" fill="#fff"/>' +
            '<circle cx="80" cy="72" r="58" fill="#e8eef8" stroke="#c5d0da" ' +
            'stroke-width="2"/>' +
            ticks +
            '<line x1="80" y1="72" x2="80" y2="44" stroke="#1a1a1a" ' +
            'stroke-width="3.5" stroke-linecap="round" ' +
            'transform="rotate(' + hourAng + ' 80 72)"/>' +
            '<line x1="80" y1="72" x2="80" y2="28" stroke="#0d6efd" ' +
            'stroke-width="2.5" stroke-linecap="round" ' +
            'transform="rotate(' + minAng + ' 80 72)"/>' +
            '<circle cx="80" cy="72" r="4" fill="#1a1a1a"/>' +
            '<text x="80" y="146" text-anchor="middle" fill="#1a1a1a" ' +
            'font-size="13" font-weight="700" font-family="sans-serif">' +
            title + "</text>" +
            '<text x="80" y="162" text-anchor="middle" fill="#5b6b7a" ' +
            'font-size="11" font-family="sans-serif">' + value + "</text>" +
            (dateLabel
                ? '<text x="80" y="176" text-anchor="middle" fill="#5b6b7a" ' +
                  'font-size="10" font-family="sans-serif">' + dateLabel +
                  "</text>"
                : "") +
            "</svg>"
        );
    }

    function svgFact(card) {
        var title = escapeXml(card.title || "");
        var value = String(card.value == null ? "" : card.value);
        if (card.unit) {
            value = value + " " + String(card.unit);
        }
        value = escapeXml(value);
        if (!title && !value) {
            return null;
        }
        return (
            '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 280 120" ' +
            'width="280" height="120" role="img">' +
            '<rect width="280" height="120" rx="8" fill="#fff" stroke="#c5d0da" ' +
            'stroke-width="1"/>' +
            '<rect x="0" y="0" width="8" height="120" rx="4" fill="#0d6efd"/>' +
            '<text x="24" y="42" fill="#5b6b7a" font-size="13" ' +
            'font-family="sans-serif">' + (title || " ") + "</text>" +
            '<text x="24" y="84" fill="#1a1a1a" font-size="28" font-weight="700" ' +
            'font-family="sans-serif">' + (value || " ") + "</text>" +
            "</svg>"
        );
    }

    function safeHref(raw) {
        var href = String(raw == null ? "" : raw).trim();
        if (!href || href.indexOf("//") === 0) {
            return "";
        }
        if (/[\s"'<>]/.test(href)) {
            return "";
        }
        if (href.charAt(0) === "/" && href.indexOf("//") !== 0) {
            return href;
        }
        if (/^[A-Za-z0-9][A-Za-z0-9.-]+\.[A-Za-z]{2,}([/?#].*)?$/.test(href)) {
            href = "https://" + href;
        }
        var lower = href.toLowerCase();
        if (lower.indexOf("https://") !== 0 && lower.indexOf("http://") !== 0) {
            return "";
        }
        return href;
    }

    function hostLabel(href) {
        if (!href) {
            return "";
        }
        if (href.charAt(0) === "/") {
            return href.split("#")[0].slice(0, 48) || "/";
        }
        try {
            var origin = (global.location && global.location.origin) || "https://local.invalid";
            var host = new URL(href, origin).hostname || "";
            if (host.indexOf("www.") === 0) {
                host = host.slice(4);
            }
            return host;
        } catch (e) {
            return "";
        }
    }

    function linkBannerHtml(card) {
        var href = safeHref(card.url || card.href || card.link);
        if (!href) {
            return null;
        }
        var host = hostLabel(href);
        var title = escapeXml(card.title || host || href);
        var sub = escapeXml(card.subtitle || card.value || "");
        if (!sub && host && host !== (card.title || host)) {
            sub = escapeXml(host);
        }
        var mark =
            '<svg class="o_chatboo_link_banner_mark" viewBox="0 0 120 72" ' +
            'aria-hidden="true" focusable="false">' +
            '<rect x="22" y="18" width="44" height="36" rx="8" fill="none" ' +
            'stroke="#0d6efd" stroke-width="3"/>' +
            '<rect x="54" y="18" width="44" height="36" rx="8" fill="none" ' +
            'stroke="#5b6b7a" stroke-width="3"/>' +
            "</svg>";
        return (
            '<a class="o_chatboo_link_banner_card" href="' + escapeXml(href) +
            '" target="_blank" rel="noopener noreferrer" title="' + title + '">' +
            '<span class="o_chatboo_link_banner_preview" aria-hidden="true">' +
            mark + "</span>" +
            '<span class="o_chatboo_link_banner_meta">' +
            '<span class="o_chatboo_link_banner_title">' + title + "</span>" +
            (sub ? '<span class="o_chatboo_link_banner_host">' + sub + "</span>" : "") +
            '<span class="o_chatboo_link_banner_cta">Abrir ' +
            '<i class="fa fa-external-link" aria-hidden="true"></i></span>' +
            "</span></a>"
        );
    }

    function buildSvg(card) {
        if (!card || typeof card !== "object") {
            return null;
        }
        var kind = String(card.kind || "fact").toLowerCase();
        if (kind === "link") {
            return null;
        }
        if (kind === "clock") {
            return svgClock(card);
        }
        return svgFact(card);
    }

    function openSvg(svgMarkup, filename) {
        var blob = new Blob(
            ['<?xml version="1.0" encoding="UTF-8"?>\n', svgMarkup],
            { type: "image/svg+xml;charset=utf-8" }
        );
        var url = URL.createObjectURL(blob);
        var opened = null;
        try {
            opened = global.open(url, "_blank", "noopener");
        } catch (e) {
            opened = null;
        }
        if (!opened) {
            var a = global.document.createElement("a");
            a.href = url;
            a.download = filename || "card.svg";
            a.target = "_blank";
            a.rel = "noopener";
            global.document.body.appendChild(a);
            a.click();
            global.document.body.removeChild(a);
        }
        global.setTimeout(function () {
            URL.revokeObjectURL(url);
        }, 4000);
    }

    function hydrateOne(el) {
        if (!el || el.getAttribute("data-chatboo-card-ready") === "1") {
            return;
        }
        var raw = el.getAttribute("data-chatboo-card");
        if (!raw) {
            return;
        }
        var card;
        try {
            card = JSON.parse(raw);
        } catch (e) {
            return;
        }
        if (String(card.kind || "").toLowerCase() === "link") {
            if (el.querySelector(".o_chatboo_link_banner_card")) {
                el.setAttribute("data-chatboo-card-ready", "1");
                return;
            }
            var banner = linkBannerHtml(card);
            if (!banner) {
                return;
            }
            el.classList.add("o_chatboo_link_banner");
            el.innerHTML = banner;
            el.setAttribute("data-chatboo-card-ready", "1");
            return;
        }
        var svg = buildSvg(card);
        if (!svg) {
            return;
        }
        el.innerHTML = "";
        var btn = global.document.createElement("button");
        btn.type = "button";
        btn.className = "o_chatboo_svg_card_btn";
        btn.setAttribute("aria-label", card.title || "SVG");
        btn.innerHTML = svg;
        btn.addEventListener("click", function (ev) {
            ev.preventDefault();
            ev.stopPropagation();
            var kind = String((card && card.kind) || "card");
            openSvg(svg, kind + ".svg");
        });
        el.appendChild(btn);
        el.setAttribute("data-chatboo-card-ready", "1");
    }

    function hydrateRoot(root) {
        if (!root || !root.querySelectorAll) {
            return;
        }
        var nodes = root.querySelectorAll(".o_chatboo_svg_card[data-chatboo-card]");
        var i;
        for (i = 0; i < nodes.length; i++) {
            hydrateOne(nodes[i]);
        }
    }

    global.ChatbooSvgCards = {
        hydrate: hydrateRoot,
        buildSvg: buildSvg,
    };
})(typeof window !== "undefined" ? window : this);
