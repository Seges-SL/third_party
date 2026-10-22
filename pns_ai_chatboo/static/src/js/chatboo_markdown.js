/* SPDX-License-Identifier: Apache-2.0 */
/* Copyright (C) 2026 Patanegra Soft <https://patanegra.com> */
/**
 * Markdown subset for Chatboo. Linear scan, no nested unbounded regex.
 * Replaces Showdown 2.1.0 (CVE-2024-1899). Output still goes through sanitizeHtml.
 *
 * Covers: headings, bold/italic (mid-word _ stays snake_case), strike,
 * inline/fenced code, links, images, lists, task lists, GFM tables,
 * blockquotes, hr, optional autolinks, optional single newlines as <br>.
 */
(function (root) {
    'use strict';

    function escapeHtml(text) {
        return String(text === null || text === undefined ? '' : text)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#39;');
    }

    function isWord(ch) {
        return !!ch && /[A-Za-z0-9_]/.test(ch);
    }

    function linkAttrs(href, opts) {
        var safe = escapeHtml(href);
        if (opts && opts.openLinksInNewWindow) {
            return ' href="' + safe + '" target="_blank" rel="noopener noreferrer"';
        }
        return ' href="' + safe + '"';
    }

    function inline(text, opts) {
        var out = '';
        var i = 0;
        var n = text.length;
        while (i < n) {
            var c = text.charAt(i);
            if (c === '\\' && i + 1 < n) {
                out += escapeHtml(text.charAt(i + 1));
                i += 2;
                continue;
            }
            if (c === '`') {
                var end = text.indexOf('`', i + 1);
                if (end > i) {
                    out += '<code>' + escapeHtml(text.slice(i + 1, end)) + '</code>';
                    i = end + 1;
                    continue;
                }
            }
            if (c === '!' && text.charAt(i + 1) === '[') {
                var altEnd = text.indexOf(']', i + 2);
                if (altEnd > i && text.charAt(altEnd + 1) === '(') {
                    var urlEnd = text.indexOf(')', altEnd + 2);
                    if (urlEnd > altEnd) {
                        var alt = text.slice(i + 2, altEnd);
                        var href = text.slice(altEnd + 2, urlEnd);
                        out += '<img src="' + escapeHtml(href) + '" alt="' + escapeHtml(alt) + '">';
                        i = urlEnd + 1;
                        continue;
                    }
                }
            }
            if (c === '[') {
                var labelEnd = text.indexOf(']', i + 1);
                if (labelEnd > i && text.charAt(labelEnd + 1) === '(') {
                    var hrefEnd = text.indexOf(')', labelEnd + 2);
                    if (hrefEnd > labelEnd) {
                        var label = inline(text.slice(i + 1, labelEnd), opts);
                        var href = text.slice(labelEnd + 2, hrefEnd);
                        out += '<a' + linkAttrs(href, opts) + '>' + label + '</a>';
                        i = hrefEnd + 1;
                        continue;
                    }
                }
            }
            if (text.slice(i, i + 2) === '~~' && opts && opts.strikethrough) {
                var strikeEnd = text.indexOf('~~', i + 2);
                if (strikeEnd > i) {
                    out += '<del>' + inline(text.slice(i + 2, strikeEnd), opts) + '</del>';
                    i = strikeEnd + 2;
                    continue;
                }
            }
            if (text.slice(i, i + 2) === '**') {
                var boldEnd = text.indexOf('**', i + 2);
                if (boldEnd > i) {
                    out += '<strong>' + inline(text.slice(i + 2, boldEnd), opts) + '</strong>';
                    i = boldEnd + 2;
                    continue;
                }
            }
            if (text.slice(i, i + 2) === '__' && !isWord(text.charAt(i - 1))) {
                var bEnd = text.indexOf('__', i + 2);
                if (bEnd > i && !isWord(text.charAt(bEnd + 2))) {
                    out += '<strong>' + inline(text.slice(i + 2, bEnd), opts) + '</strong>';
                    i = bEnd + 2;
                    continue;
                }
            }
            if (c === '*' && text.charAt(i + 1) !== '*') {
                var emEnd = text.indexOf('*', i + 1);
                if (emEnd > i) {
                    out += '<em>' + inline(text.slice(i + 1, emEnd), opts) + '</em>';
                    i = emEnd + 1;
                    continue;
                }
            }
            if (c === '_' && !isWord(text.charAt(i - 1))) {
                var uEnd = text.indexOf('_', i + 1);
                if (uEnd > i && !isWord(text.charAt(uEnd + 1))) {
                    out += '<em>' + inline(text.slice(i + 1, uEnd), opts) + '</em>';
                    i = uEnd + 1;
                    continue;
                }
            }
            if (opts && opts.simplifiedAutoLink && (text.slice(i, i + 7) === 'http://' || text.slice(i, i + 8) === 'https://')) {
                var j = i;
                while (j < n && !/\s/.test(text.charAt(j)) && text.charAt(j) !== '<') {
                    j++;
                }
                var url = text.slice(i, j).replace(/[),.;!?]+$/, '');
                out += '<a' + linkAttrs(url, opts) + '>' + escapeHtml(url) + '</a>';
                i = i + url.length;
                continue;
            }
            out += escapeHtml(c);
            i += 1;
        }
        return out;
    }

    function splitCells(line) {
        var raw = line.trim();
        if (raw.charAt(0) === '|') {
            raw = raw.slice(1);
        }
        if (raw.charAt(raw.length - 1) === '|') {
            raw = raw.slice(0, -1);
        }
        return raw.split('|').map(function (c) { return c.trim(); });
    }

    function isSepLine(line) {
        return /^\s*\|?[\s:|-]+\|[\s:|-]+\|?\s*$/.test(line);
    }

    function fenceLang(line) {
        var m = /^\s*```([\w+-]*)\s*$/.exec(line);
        return m ? (m[1] || 'text') : null;
    }

    function heading(line) {
        var m = /^(#{1,6})\s+(.+?)\s*#*\s*$/.exec(line);
        if (!m) {
            return null;
        }
        return { level: m[1].length, text: m[2] };
    }

    function listItem(line, opts) {
        var m = /^(\s*)([-*+]|\d+\.)\s+(.*)$/.exec(line);
        if (!m) {
            return null;
        }
        var body = m[3];
        var task = null;
        if (opts && opts.tasklists) {
            var t = /^\[([ xX])\]\s+(.*)$/.exec(body);
            if (t) {
                task = t[1] !== ' ';
                body = t[2];
            }
        }
        return {
            indent: m[1].length,
            ordered: /\d/.test(m[2]),
            task: task,
            text: body,
        };
    }

    function toHtml(src, opts) {
        opts = opts || {};
        src = String(src || '').replace(/\r\n/g, '\n');
        var lines = src.split('\n');
        var html = [];
        var i = 0;
        while (i < lines.length) {
            var line = lines[i];
            var trimmed = line.trim();
            if (!trimmed) {
                i += 1;
                continue;
            }
            var lang = fenceLang(trimmed);
            if (lang !== null) {
                var code = [];
                i += 1;
                while (i < lines.length && !/^\s*```/.test(lines[i])) {
                    code.push(lines[i]);
                    i += 1;
                }
                if (i < lines.length) {
                    i += 1;
                }
                html.push(
                    '<pre><code class="language-' + escapeHtml(lang) + '">'
                    + escapeHtml(code.join('\n')) + '</code></pre>'
                );
                continue;
            }
            var h = heading(trimmed);
            if (h) {
                html.push('<h' + h.level + '>' + inline(h.text, opts) + '</h' + h.level + '>');
                i += 1;
                continue;
            }
            if (/^(\*\s*){3,}$|^(-\s*){3,}$|^(_\s*){3,}$/.test(trimmed)) {
                html.push('<hr/>');
                i += 1;
                continue;
            }
            if (trimmed.charAt(0) === '>') {
                var quote = [];
                while (i < lines.length && lines[i].trim().charAt(0) === '>') {
                    quote.push(lines[i].replace(/^\s*>\s?/, ''));
                    i += 1;
                }
                html.push('<blockquote>' + toHtml(quote.join('\n'), opts) + '</blockquote>');
                continue;
            }
            if (opts.tables !== false && trimmed.indexOf('|') !== -1
                    && i + 1 < lines.length && isSepLine(lines[i + 1])) {
                var heads = splitCells(line);
                i += 2;
                var rows = [];
                while (i < lines.length && lines[i].indexOf('|') !== -1 && lines[i].trim()) {
                    rows.push(splitCells(lines[i]));
                    i += 1;
                }
                var table = ['<table><thead><tr>'];
                heads.forEach(function (cell) {
                    table.push('<th>' + inline(cell, opts) + '</th>');
                });
                table.push('</tr></thead><tbody>');
                rows.forEach(function (row) {
                    table.push('<tr>');
                    heads.forEach(function (_, col) {
                        table.push('<td>' + inline(row[col] || '', opts) + '</td>');
                    });
                    table.push('</tr>');
                });
                table.push('</tbody></table>');
                html.push(table.join(''));
                continue;
            }
            var item = listItem(line, opts);
            if (item) {
                var ordered = item.ordered;
                var items = [];
                while (i < lines.length) {
                    var next = listItem(lines[i], opts);
                    if (!next || next.ordered !== ordered) {
                        break;
                    }
                    items.push(next);
                    i += 1;
                }
                var tag = ordered ? 'ol' : 'ul';
                html.push('<' + tag + '>');
                items.forEach(function (it) {
                    var body = inline(it.text, opts);
                    if (it.task !== null) {
                        body = (it.task ? '[x] ' : '[ ] ') + body;
                    }
                    html.push('<li>' + body + '</li>');
                });
                html.push('</' + tag + '>');
                continue;
            }
            var para = [line];
            i += 1;
            while (i < lines.length) {
                var peek = lines[i];
                if (!peek.trim()) {
                    break;
                }
                if (heading(peek.trim()) || fenceLang(peek.trim()) !== null
                        || listItem(peek, opts) || peek.trim().charAt(0) === '>'
                        || /^(\*\s*){3,}$|^(-\s*){3,}$/.test(peek.trim())) {
                    break;
                }
                if (opts.tables !== false && peek.indexOf('|') !== -1
                        && i + 1 < lines.length && isSepLine(lines[i + 1])) {
                    break;
                }
                para.push(peek);
                i += 1;
            }
            var joined = para.join(opts.simpleLineBreaks ? '\n' : ' ');
            var inner = inline(joined, opts);
            if (opts.simpleLineBreaks) {
                inner = inner.replace(/\n/g, '<br/>');
            }
            html.push('<p>' + inner + '</p>');
        }
        return html.join('\n');
    }

    root.ChatbooMarkdown = { toHtml: toHtml };
}(typeof globalThis !== 'undefined' ? globalThis : this));
