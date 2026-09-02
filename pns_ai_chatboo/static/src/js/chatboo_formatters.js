/** @odoo-module **/

import { session } from "@web/session";

/**
 * pns_ai_chatboo.formatters — Pure formatting utilities for Chatboo.
 * Shared pipeline with owl1 (formatContent / formatMarkdown / tables).
 */

/** Default decimal places for number formatting */
var DEFAULT_DECIMAL_PLACES = 3;

/**
 * Locale activo de la sesión Odoo (user_context.lang), BCP47 para Intl.
 * @returns {string} e.g. 'es-ES', 'en-US'
 */
function getSessionLocale() {
    var lang = (
        (session.user_context && session.user_context.lang)
        || session.lang
        || (typeof document !== 'undefined' && document.documentElement.lang)
        || 'en-US'
    );
    return String(lang).replace(/_/g, '-');
}

/**
 * IANA tz of the Odoo user (Preferences). Empty → caller uses browser local.
 */
function getSessionTz() {
    var tz = (
        (session.user_context && session.user_context.tz)
        || session.tz
        || ''
    );
    return String(tz || '').trim();
}

/**
 * Wall clock ``YYYY-MM-DD HH:MM:SS`` in the Odoo user tz (else local).
 */
function formatWallclock(date, tz) {
    var d = date || new Date();
    var opts = {
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
        hourCycle: 'h23',
    };
    var zone = (tz === undefined || tz === null) ? getSessionTz() : tz;
    if (zone) {
        opts.timeZone = zone;
    }
    try {
        return new Intl.DateTimeFormat('sv-SE', opts).format(d).replace('T', ' ');
    } catch (e) {
        delete opts.timeZone;
        return new Intl.DateTimeFormat('sv-SE', opts).format(d).replace('T', ' ');
    }
}

/**
 * Detect if content looks like raw HTML (starts with a tag).
 *
 * @param {string} content - Raw content string
 * @returns {boolean} true if content appears to be HTML
 */
function isLikelyHtml(content) {
    var trimmed = (content || '').trim();
    if (!trimmed) {
        return false;
    }
    if (trimmed.startsWith('<')) {
        return true;
    }
    return /^<(div|table|thead|tbody|tr|td|p|span|ul|pre|caption)\b/i.test(trimmed);
}

/**
 * Escape HTML to prevent XSS.
 *
 * @param {string} text - Raw text to escape
 * @returns {string} HTML-safe string
 */
function escapeHtml(text) {
    var div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

/**
 * Format JSON with line breaks between array elements and object entries.
 * For large payloads (>20KB) skips the regex to avoid UI blocking.
 *
 * @param {*} obj - Parsed JSON object
 * @param {number} [indent=2] - JSON.stringify indentation
 * @returns {string} Formatted JSON string
 */
function formatJsonWithLineBreaks(obj, indent) {
    if (indent === undefined) indent = 2;
    var jsonStr = JSON.stringify(obj, null, indent);
    if (jsonStr.length > 20000) return jsonStr;
    return jsonStr
        .replace(/},\s*{/g, '},\n{')
        .replace(/],\s*\[/g, '],\n[')
        .replace(/},\s*\[/g, '},\n[')
        .replace(/],\s*{/g, '],\n{');
}

/**
 * Format number according to the active session locale (or override).
 *
 * @param {number} value - Number to format
 * @param {string} [locale] - BCP47 locale; defaults to session lang
 * @param {number} [decimalPlaces] - Decimal places (defaults to DEFAULT_DECIMAL_PLACES)
 * @returns {string|*} Formatted number string, or original value if not a number
 */
function formatNumber(value, locale, decimalPlaces) {
    if (typeof value !== 'number') return value;
    if (locale === undefined) locale = getSessionLocale();
    if (decimalPlaces === undefined) decimalPlaces = DEFAULT_DECIMAL_PLACES;
    try {
        return new Intl.NumberFormat(locale, {
            minimumFractionDigits: decimalPlaces,
            maximumFractionDigits: decimalPlaces
        }).format(value);
    } catch (e) {
        var loc = String(locale || '').toLowerCase();
        if (loc === 'es-es' || loc.startsWith('es')) {
            var parts = Math.abs(value).toFixed(decimalPlaces).toString().split('.');
            var intPart = parts[0];
            var decPart = parts[1] || '';
            var intFormatted = intPart.length > 3
                ? intPart.replace(/\B(?=(\d{3})+(?!\d))/g, '.')
                : intPart;
            return (value < 0 ? '-' : '') + (decPart ? intFormatted + ',' + decPart : intFormatted);
        }
        return value.toFixed(decimalPlaces);
    }
}

/**
 * Detect markdown tables whose cells contain long prose and convert
 * them to plain paragraphs. This prevents Showdown from rendering
 * weather forecasts, descriptions, etc. as ugly HTML tables.
 *
 * Heuristic: if ANY data cell in the table exceeds PROSE_THRESHOLD
 * characters of *visible* text, the whole table is "prose in disguise"
 * and gets unwrapped.
 *
 * Visible length ignores Markdown links and bare URLs so remote-LLM
 * tables with Odoo form links (`[COR/…](/web#id=…)`) stay as tables.
 * Server-side HTML tables (`o_chatboo_data_table`) never enter this path.
 *
 * @param {string} md - Raw markdown
 * @returns {string} Cleaned markdown (tables may be replaced with paragraphs)
 */
var PROSE_THRESHOLD = 60;

/** Length that counts toward prose detection (label only, not href/URL). */
function _cellProseLength(cell) {
    var text = String(cell || '').trim();
    if (!text) {
        return 0;
    }
    // [label](url) → label (may repeat)
    text = text.replace(/\[([^\]]*)\]\([^)]*\)/g, '$1');
    // Bare URLs / Odoo hashes should not inflate "prose"
    text = text.replace(/https?:\/\/\S+/gi, '');
    text = text.replace(/\/web#[^\s|]*/gi, '');
    return text.trim().length;
}

/**
 * Remote-LLM ERP grids: Markdown pipe tables with Odoo form links.
 * Must NOT be unwrapped by the weather/prose heuristic (long partner names).
 * Server-side HTML tables never reach this function — local formatting untouched.
 */
function _isRemoteErpMarkdownTable(block) {
    return /\/web#(?:id=|action=)/i.test(block || '')
        || /\(\/web#id=\d+&(?:amp;)?model=[^)]+\)/i.test(block || '');
}

function _stripProseTables(md) {
    // GFM tables may omit the leading/trailing pipe.
    var tableBlockRe = /((?:^[ \t]*\|?.+\|.+\|?[ \t]*$\n?){2,})/gm;
    return md.replace(tableBlockRe, function (block) {
        var lines = block.trim().split('\n');
        // Need at least header + separator + 1 data row
        if (lines.length < 3) return block;

        // Check if the separator row exists (|---|---| or ---|---)
        var sepLine = lines[1];
        if (!/^\s*\|?[\s:|-]+\|[\s:|-]+\|?\s*$/.test(sepLine)) return block;

        // Remote formatting only: keep Odoo-linked grids as tables even when
        // a partner name exceeds PROSE_THRESHOLD. Local HTML path unaffected.
        if (_isRemoteErpMarkdownTable(block)) {
            return block;
        }

        var headerCells = lines[0].split('|').filter(function (c) { return c.trim(); });
        var dataLines = lines.slice(2);
        var hasProse = false;
        var inspect = headerCells.concat([]);
        for (var i = 0; i < dataLines.length; i++) {
            inspect = inspect.concat(
                dataLines[i].split('|').filter(function (c) { return c.trim(); })
            );
        }
        for (var j = 0; j < inspect.length; j++) {
            if (_cellProseLength(inspect[j]) > PROSE_THRESHOLD) {
                hasProse = true;
                break;
            }
        }

        if (!hasProse) {
            var hasNumericOrDate = false;
            var numDateRe = /(?:\d{4}[/-]\d{2}|\d+[.,]\d+|\$|€|£|¥|%|\d{2,})/;
            for (var di = 0; di < dataLines.length && !hasNumericOrDate; di++) {
                var dCells = dataLines[di].split('|').filter(function (c) { return c.trim(); });
                for (var dj = 0; dj < dCells.length; dj++) {
                    if (numDateRe.test(dCells[dj])) {
                        hasNumericOrDate = true;
                        break;
                    }
                }
            }
            if (hasNumericOrDate) return block;
            // One chopped sentence (header or a single text row) → prose.
            if (dataLines.length > 2) return block;
        }

        var paragraphs = [];
        for (var r = 0; r < dataLines.length; r++) {
            var cells = dataLines[r].split('|').filter(function (c) { return c.trim(); });
            var parts = [];
            for (var c = 0; c < cells.length; c++) {
                var cellText = cells[c].trim();
                if (!cellText) continue;
                var header = (headerCells[c] || '').trim();
                if (header && header.length < 30 && header !== cellText) {
                    parts.push('**' + header + ':** ' + cellText);
                } else {
                    parts.push(cellText);
                }
            }
            if (parts.length > 0) {
                paragraphs.push(parts.join('. '));
            }
        }
        if (headerCells.length && _cellProseLength(headerCells.join(' ')) > PROSE_THRESHOLD) {
            paragraphs.unshift(headerCells.map(function (h) { return h.trim(); }).filter(Boolean).join('. '));
        }
        return '\n' + paragraphs.join('\n\n') + '\n';
    });
}

/**
 * Format Markdown content using Showdown.js (if available).
 * Falls back to manual regex-based formatting.
 *
 * Pre-processes the markdown to strip "prose tables" — markdown tables
 * whose cells contain long sentences instead of genuine tabular data.
 *
 * @param {string} content - Markdown source text
 * @returns {string} HTML string
 */
function formatMarkdown(content) {
    if (typeof ChatbooSse !== 'undefined' && ChatbooSse.prepareMarkdownForDisplay) {
        var prep = ChatbooSse.prepareMarkdownForDisplay(content || '');
        content = prep.markdown;
    }
    if (typeof showdown !== 'undefined') {
        try {
            // Pre-process: strip prose tables before Showdown sees them
            content = _stripProseTables(content);

            var converter = new showdown.Converter({
                tables: true,
                strikethrough: true,
                tasklists: true,
                simpleLineBreaks: true,
                openLinksInNewWindow: true,
                emoji: false,
                underline: false,
                headerLevelStart: 1
            });

            var html = converter.makeHtml(content);

            html = html
                .replace(/<table>/g, '<div class="table-responsive" style="margin: 1em 0;"><table class="table table-bordered table-sm" style="width: 100%; font-family: -apple-system, BlinkMacSystemFont, \'Segoe UI\', Roboto, \'Helvetica Neue\', Arial, sans-serif; font-size: 1.125em;">')
                .replace(/<\/table>/g, '</table></div>')
                .replace(/<pre><code/g, '<pre class="bg-light p-3 rounded border" style="overflow-x: auto;"><code class="language-text"')
                .replace(/<code(?! class="language)/g, '<code class="bg-light px-1 rounded" style="font-family: monospace;">')
                .replace(/<blockquote>/g, '<blockquote class="border-left pl-3 ml-3" style="border-left: 4px solid #dee2e6; margin: 1em 0;">')
                .replace(/<a href="([^"]+)"(?! target)/g, '<a href="$1" target="_blank" rel="noopener noreferrer"');

            return '<div class="o_chatboo_prose">' + html + '</div>';
        } catch (error) {
            console.error('Error rendering markdown with Showdown.js:', error);
        }
    }

    // Fallback: Simple manual formatting
    var formatted = escapeHtml(content);

    formatted = formatted.replace(/```(\w+)?\n([\s\S]*?)```/g, function (match, lang, code) {
        var escapedCode = escapeHtml(code.trim());
        return '<pre class="bg-light p-3 rounded border" style="overflow-x: auto;"><code class="language-' + (lang || 'text') + '">' + escapedCode + '</code></pre>';
    });

    formatted = formatted.replace(/^#### (.*$)/gim, '<h4>$1</h4>');
    formatted = formatted.replace(/^### (.*$)/gim, '<h3>$1</h3>');
    formatted = formatted.replace(/^## (.*$)/gim, '<h2>$1</h2>');
    formatted = formatted.replace(/^# (.*$)/gim, '<h1>$1</h1>');
    formatted = formatted.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
    formatted = formatted.replace(/\*([^*]+)\*/g, '<em>$1</em>');
    formatted = formatted.replace(/`([^`]+)`/g, '<code class="bg-light px-1 rounded" style="font-family: monospace;">$1</code>');
    formatted = formatted.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>');
    formatted = formatted.replace(/\n\n+/g, '</p><p>');
    formatted = formatted.replace(/\n/g, '<br/>');

    return formatted;
}

/**
 * Format CSV lines as an HTML table.
 *
 * @param {string[]} lines - Array of CSV lines
 * @returns {string} HTML table string
 */
function formatCSV(lines) {
    var rows = lines.map(function (line) {
        return line.split(',').map(function (cell) { return cell.trim(); });
    });

    if (rows.length === 0) return '';

    var html = '<div class="table-responsive"><table class="table table-sm table-bordered table-striped o_chatboo_data_table">';

    var firstRow = rows[0];
    var numericCols = {};
    if (rows.length > 1) {
        for (var c = 0; c < firstRow.length; c++) {
            var numHits = 0;
            var seen = 0;
            for (var r = 1; r < rows.length; r++) {
                var cell = rows[r][c];
                if (cell === undefined || cell === '') continue;
                seen++;
                if (/^[+-]?\d+(?:[.,]\d+)?$/.test(cell.replace(/\s/g, ''))) numHits++;
            }
            if (seen > 0 && numHits >= Math.max(1, Math.floor(seen * 0.8))) {
                numericCols[c] = true;
            }
        }
    }
    html += '<thead><tr>';
    firstRow.forEach(function (cell, idx) {
        var cls = numericCols[idx] ? ' class="o_chatboo_num text-end"' : '';
        html += '<th' + cls + '>' + escapeHtml(cell) + '</th>';
    });
    html += '</tr></thead>';

    if (rows.length > 1) {
        html += '<tbody>';
        rows.slice(1).forEach(function (row) {
            html += '<tr>';
            row.forEach(function (cell, idx) {
                var cls = numericCols[idx] ? ' class="o_chatboo_num text-end"' : '';
                html += '<td' + cls + '>' + escapeHtml(cell) + '</td>';
            });
            html += '</tr>';
        });
        html += '</tbody>';
    }

    html += '</table></div>';
    return html;
}

/**
 * True only for genuine CSV (aligned short columns), not Spanish/English
 * prose that happens to contain commas on every paragraph line.
 * Bug: "¿Quién eres?" replies were rendered as wide tables because every
 * line included a comma ("Chatboo, el asistente…", "clientes, pedidos…").
 */
function looksLikeCsv(lines) {
    if (!lines || lines.length < 2) {
        return false;
    }
    var joined = lines.join('\n');
    // Prose / markdown markers → never CSV
    if (joined.indexOf('**') !== -1 || joined.indexOf('__') !== -1) {
        return false;
    }
    if (/[¿?¡!]/.test(joined)) {
        return false;
    }
    var rows = lines.map(function (line) {
        return line.split(',').map(function (c) { return c.trim(); });
    });
    var cols = rows[0].length;
    if (cols < 2) {
        return false;
    }
    for (var i = 0; i < rows.length; i++) {
        if (rows[i].length !== cols) {
            return false;
        }
        for (var j = 0; j < rows[i].length; j++) {
            // Real CSV cells are short; long fragments = prose split badly
            if (rows[i][j].length > 80) {
                return false;
            }
        }
    }
    return true;
}

/**
 * Render JSON data as an HTML table or list if the shape is suitable.
 *
 * Handles three cases:
 *   1. Array of objects -> table with headers
 *   2. Simple array -> unordered list
 *   3. Flat object -> key-value table
 *
 * @param {*} data - Parsed JSON data
 * @returns {string|null} HTML string, or null if data is not table-shaped
 */
function formatJsonAsTable(data) {
    if (data && !Array.isArray(data) && typeof data === 'object' && Array.isArray(data.data)) {
        data = data.data;
    }

    // Case 1: Array of Objects -> Table
    if (Array.isArray(data) && data.length > 0 && typeof data[0] === 'object' && data[0] !== null) {
        var keys = new Set();
        data.forEach(function (item) { Object.keys(item || {}).forEach(function (k) { keys.add(k); }); });
        var headers = Array.from(keys);
        if (headers.length === 0) return JSON.stringify(data);

        var numericColumns = new Set();
        var sample = data.slice(0, Math.min(100, data.length));
        sample.forEach(function (item) {
            headers.forEach(function (h) {
                if (typeof item[h] === 'number') numericColumns.add(h);
            });
        });

        var maxRows = 200;
        var displayData = data.slice(0, maxRows);
        var parts = [
            '<div class="table-responsive"><table class="table table-sm table-bordered table-striped table-hover o_chatboo_data_table">',
            '<thead class="thead-light"><tr>'
        ];
        headers.forEach(function (h) {
            var cls = numericColumns.has(h) ? ' class="o_chatboo_num text-end"' : '';
            parts.push('<th' + cls + '>', escapeHtml(h), '</th>');
        });
        parts.push('</tr></thead><tbody>');

        displayData.forEach(function (row) {
            parts.push('<tr>');
            headers.forEach(function (h) {
                var val = row[h];
                if (val === null || val === undefined) val = "";
                else if (typeof val === 'object') val = JSON.stringify(val);
                else if (typeof val === 'number') val = formatNumber(val);
                else val = String(val);
                var cls = numericColumns.has(h) ? ' class="o_chatboo_num text-end"' : '';
                parts.push('<td' + cls + '>', escapeHtml(val), '</td>');
            });
            parts.push('</tr>');
        });
        parts.push('</tbody></table></div>');
        if (data.length > maxRows) {
            parts.push('<p class="text-muted font-italic">... (', String(data.length - maxRows), ' more rows hidden)</p>');
        }
        return parts.join('');
    }

    // Case 2: Simple Array -> List
    if (Array.isArray(data)) {
        var html = '<ul class="list-group list-group-flush">';
        data.forEach(function (item) {
            var displayVal = typeof item === 'number' ? formatNumber(item) : String(item);
            html += '<li class="list-group-item py-1">' + escapeHtml(displayVal) + '</li>';
        });
        html += '</ul>';
        return html;
    }

    // Case 3: Flat Object -> Key-Value Table
    if (data && typeof data === 'object' && data !== null) {
        var html = '<div class="table-responsive"><table class="table table-sm table-bordered o_chatboo_data_table" style="width: auto;">';
        Object.entries(data).forEach(function (_ref) {
            var k = _ref[0], v = _ref[1];
            var valStr;
            var isNumber = false;
            if (typeof v === 'object' && v !== null) {
                valStr = JSON.stringify(v);
            } else if (typeof v === 'number') {
                isNumber = true;
                valStr = formatNumber(v);
            } else {
                valStr = String(v);
            }
            var cls = isNumber ? ' class="o_chatboo_num text-end"' : '';
            html += '<tr><th class="bg-light">' + escapeHtml(k) + '</th><td' + cls + '>' + escapeHtml(valStr) + '</td></tr>';
        });
        html += '</table></div>';
        return html;
    }

    return null;
}

/**
 * Post-process HTML to make standalone images (outside tables) clickable.
 * Wraps bare <img> tags (not already inside <a>) with a link that opens
 * the full-size image in a new tab.
 *
 * For /web/image/ URLs: thumbnail (image_128) as src, full-size (image_1920) as href.
 * For data-URIs / external URLs: links to the same source.
 *
 * @param {string} html - Processed HTML string
 * @returns {string} HTML with clickable standalone images
 */
function _wrapStandaloneImages(html) {
    if (!html || typeof html !== 'string' || html.indexOf('<img') === -1) {
        return html;
    }
    // Use a temporary container to manipulate DOM safely
    var tmp = document.createElement('div');
    tmp.innerHTML = html;
    var images = tmp.querySelectorAll('img');
    for (var i = 0; i < images.length; i++) {
        var img = images[i];
        // Skip if already wrapped in <a> or inside a table cell
        if (img.closest('a') || img.closest('td') || img.closest('th')) {
            continue;
        }
        var src = img.getAttribute('src') || '';
        if (!src) continue;
        // Skip data-URIs: browsers block data: navigation to new tabs (blank page)
        if (src.indexOf('data:') === 0) continue;

        // Derive full-size URL: only replace image_NNN variants (Image mixin).
        // Fields like 'logo' or 'avatar' (plain Binary) are already full-size.
        var fullUrl = src;
        if (src.indexOf('/web/image/') !== -1 && /\/image_\d+$/.test(src)) {
            fullUrl = src.replace(/image_\d+$/, 'image_1920');
        }

        // Wrap with clickable link
        var link = document.createElement('a');
        link.href = fullUrl;
        link.target = '_blank';
        link.title = 'Ver imagen completa';
        img.parentNode.insertBefore(link, img);
        link.appendChild(img);
    }
    return tmp.innerHTML;
}

function _isServerChatbooTable(table) {
    if (!table) {
        return false;
    }
    if (table.classList && table.classList.contains('o_chatboo_data_table')) {
        return true;
    }
    if (table.getAttribute && table.getAttribute('data-chatboo-dataset')) {
        return true;
    }
    if (table.closest && table.closest('.o_chatboo_table_block')) {
        return true;
    }
    return false;
}

function _unwrapHtmlProseTables(root) {
    var tables = root.querySelectorAll('table');
    for (var i = tables.length - 1; i >= 0; i--) {
        var table = tables[i];
        if (_isServerChatbooTable(table)) {
            continue;
        }
        var markup = table.innerHTML || '';
        if (/\/web#/i.test(markup)) {
            continue;
        }
        var cells = table.querySelectorAll('th, td');
        if (!cells.length) {
            continue;
        }
        var hasNumeric = false;
        var hasLong = false;
        var texts = [];
        for (var c = 0; c < cells.length; c++) {
            var t = (cells[c].textContent || '').trim();
            if (t) {
                texts.push(t);
            }
            if (_cellProseLength(t) > PROSE_THRESHOLD) {
                hasLong = true;
            }
            if (/(?:\d{4}[/-]\d{2}|\d+[.,]\d+|\$|€|£|¥|%|\d{2,})/.test(t)) {
                hasNumeric = true;
            }
        }
        var tdCount = table.querySelectorAll('td').length;
        var rowCount = table.querySelectorAll('tr').length;
        if (hasNumeric && !hasLong) {
            continue;
        }
        if (!hasLong && tdCount >= 6 && rowCount >= 4) {
            continue;
        }
        var host = document.createElement('div');
        host.className = 'o_chatboo_prose';
        for (var p = 0; p < texts.length; p++) {
            var para = document.createElement('p');
            para.textContent = texts[p];
            host.appendChild(para);
        }
        var wrap = (table.parentNode && table.parentNode.classList
            && table.parentNode.classList.contains('table-responsive'))
            ? table.parentNode
            : table;
        if (wrap.parentNode) {
            wrap.parentNode.replaceChild(host, wrap);
        }
    }
}

/**
 * Re-render Markdown-looking prose islands inside server HTML
 * (``.pns-result-footer``, stream footer wrappers) so ``#`` headings
 * become real ``&lt;hN&gt;`` instead of literal text.
 *
 * @param {string} html
 * @returns {string}
 */
function enhanceHtmlProse(html) {
    if (!html || typeof html !== 'string') {
        return html || '';
    }
    if (typeof document === 'undefined') {
        return html;
    }
    var root = document.createElement('div');
    root.innerHTML = html;
    _unwrapHtmlProseTables(root);
    // Full-bubble Markdown report (no Chatboo tables): re-parse as Showdown
    // instead of leaving literal "#" in plain nodes.
    if (
        !root.querySelector('.o_chatboo_table_block, table, .o_chatboo_data_table')
        && !root.querySelector('h1, h2, h3, h4, h5, h6, .o_chatboo_prose_h')
        && /#{1,6}\s|\*\*[^*\n]{2,}|^[-*•]\s/m.test(root.textContent || '')
    ) {
        var cloneAll = root.cloneNode(true);
        var brAll = cloneAll.querySelectorAll('br');
        for (var ba = 0; ba < brAll.length; ba++) {
            brAll[ba].parentNode.replaceChild(document.createTextNode('\n'), brAll[ba]);
        }
        var mdAll = (cloneAll.textContent || '').replace(/\n{3,}/g, '\n\n').trim();
        if (typeof ChatbooSse !== 'undefined' && ChatbooSse.normalizeGluedMarkdown) {
            mdAll = ChatbooSse.normalizeGluedMarkdown(mdAll);
        }
        if (mdAll) {
            var renderedAll = formatMarkdown(mdAll);
            if (renderedAll && renderedAll !== mdAll) {
                return renderedAll;
            }
        }
    }
    var nodes = root.querySelectorAll('.pns-result-footer, .o_chatboo_prose_host');
    // Stream footer wrapper: last mt-2 after tables without nested table.
    var allMt = root.querySelectorAll('div.mt-2');
    for (var m = 0; m < allMt.length; m++) {
        var cand = allMt[m];
        if (cand.querySelector('table, .o_chatboo_table_block')) {
            continue;
        }
        if (cand.querySelector('h1, h2, h3, h4, h5, h6, .o_chatboo_prose_h, .o_chatboo_prose_p')) {
            continue;
        }
        var sample = (cand.textContent || '').trim();
        if (/#{1,6}\s/.test(sample) || /\*\*[^*\n]{2,}/.test(sample)) {
            nodes = Array.prototype.slice.call(nodes).concat([cand]);
        }
    }
    var seen = [];
    for (var i = 0; i < nodes.length; i++) {
        var el = nodes[i];
        if (!el || seen.indexOf(el) >= 0) {
            continue;
        }
        seen.push(el);
        if (el.querySelector && el.querySelector('h1, h2, h3, h4, h5, h6, .o_chatboo_prose_h')) {
            // Already structured (server markdownish or prior Showdown).
            el.classList.add('o_chatboo_prose');
            continue;
        }
        // Keep newlines for ATX; do not collapse before detection.
        var rawText = el.textContent || '';
        if (!rawText.trim() || (!/#{1,6}\s/.test(rawText) && rawText.indexOf('**') < 0 && !/^[-*•]\s/m.test(rawText))) {
            continue;
        }
        var clone = el.cloneNode(true);
        var brs = clone.querySelectorAll('br');
        for (var b = 0; b < brs.length; b++) {
            brs[b].parentNode.replaceChild(document.createTextNode('\n'), brs[b]);
        }
        var md = (clone.textContent || '').replace(/\n{3,}/g, '\n\n').trim();
        if (typeof ChatbooSse !== 'undefined' && ChatbooSse.normalizeGluedMarkdown) {
            md = ChatbooSse.normalizeGluedMarkdown(md);
        }
        if (!md) {
            continue;
        }
        var rendered = formatMarkdown(md);
        if (!rendered || rendered === md) {
            continue;
        }
        el.classList.add('o_chatboo_prose');
        el.innerHTML = rendered;
    }
    return root.innerHTML;
}

/**
 * Main content formatting pipeline for assistant messages.
 *
 * Detection order (first match wins):
 *   0. Raw HTML from server -> pass through unchanged
 *   1. JSON object/array -> table or formatted JSON
 *   2. CSV-like lines -> HTML table
 *   3. Markdown (with code blocks, tables, etc.) -> HTML via Showdown
 *   4. Plain text -> escaped HTML with line breaks
 *
 * @param {string} content - Raw content from the assistant
 * @returns {string} HTML string ready for innerHTML
 */
function formatContent(content) {
    if (!content || typeof content !== 'string') {
        return content || '';
    }

    var trimmed = content.trim();

    // Tabla HTML del servidor + pie Markdown del LLM (tras data_rendered).
    // Sin este split, isLikelyHtml traga el bloque entero y el informe queda
    // como tocho con ##/** crudos (p. ej. `...</div>## Análisis…`).
    if (typeof ChatbooSse !== 'undefined' && ChatbooSse.splitHtmlAndMarkdownTail) {
        var split = ChatbooSse.splitHtmlAndMarkdownTail(trimmed);
        if (split) {
            var foot = formatMarkdown(split.md);
            return _wrapStandaloneImages(enhanceHtmlProse(
                ChatbooSse.mergeHtmlWithFooter(split.html, foot)
            ));
        }
    }

    if (isLikelyHtml(trimmed)) {
        return _wrapStandaloneImages(enhanceHtmlProse(content));
    }

    if ((trimmed.startsWith('{') || trimmed.startsWith('[')) && (trimmed.endsWith('}') || trimmed.endsWith(']'))) {
        try {
            var parsed = JSON.parse(trimmed);

            if (parsed && typeof parsed === 'object' && parsed.formatted_text) {
                var ft = parsed.formatted_text;
                if (typeof ft === 'string' && isLikelyHtml(ft.trim())) {
                    return _wrapStandaloneImages(enhanceHtmlProse(ft));
                }
                var hasMarkdown = typeof ft === 'string' && (
                    /^\|.+\|$/m.test(ft) || ft.includes('#') || ft.includes('```') ||
                    ft.includes('**') || /^\s*[-*+]\s/m.test(ft)
                );
                var formattedHtml;
                if (hasMarkdown && typeof showdown !== 'undefined') {
                    formattedHtml = formatMarkdown(ft);
                } else {
                    formattedHtml = escapeHtml(ft).replace(/\n/g, '<br/>');
                }

                var metaHtml = '';
                if (parsed.__payload_size__) {
                    var size = parsed.__payload_size__;
                    var sizeStr = size > 1024 ? (size / 1024).toFixed(1) + 'KB' : size + 'B';
                    var source = 'LLM';
                    if (parsed.__fmt_type__ === 'local_raw') source = 'Local Raw';
                    else if (parsed.__fmt_type__ === 'local_json') source = 'Local JSON';

                    metaHtml = '<div class="d-flex justify-content-end text-muted small mt-1 pt-1 border-top" style="font-size: 0.8em; opacity: 0.7;">' +
                                   '<span class="mr-3" title="Payload size"><i class="fa fa-hdd-o"></i> ' + sizeStr + '</span>' +
                                   '<span title="Formatting source"><i class="fa fa-cogs"></i> ' + source + '</span>' +
                               '</div>';
                }

                var wrapperStyle = hasMarkdown ? '' : "font-family: 'Courier New', Courier, monospace; font-size: 1.1em; line-height: 1.5; white-space: pre-wrap;";
                return _wrapStandaloneImages('<div' + (wrapperStyle ? ' style="' + wrapperStyle + '"' : '') + '>' + formattedHtml + '</div>' + metaHtml);
            }

            // Prefer a real table over a dark JSON dump when rows exist.
            var asTable = formatJsonAsTable(parsed);
            if (asTable && typeof asTable === 'string' && asTable.indexOf('<table') >= 0) {
                return _wrapStandaloneImages(asTable);
            }
            // Diagnostic bags (counts, state tuples…): do not paint as <pre>.
            if (typeof ChatbooSse !== 'undefined' && ChatbooSse.isDiagnosticJsonDump
                    && ChatbooSse.isDiagnosticJsonDump(parsed)) {
                return '<p class="text-muted small"><em>(datos intermedios omitidos — pide de nuevo el listado)</em></p>';
            }

            var formatted = formatJsonWithLineBreaks(parsed);
            return '<pre class="bg-light p-3 rounded border"><code class="language-json">' + escapeHtml(formatted) + '</code></pre>';
        } catch (e) {
            // Not valid JSON
        }
    }

    if (/^<[a-z][\s\S]*>/i.test(trimmed)) {
        return _wrapStandaloneImages(enhanceHtmlProse(content));
    }

    // HTML embebido en texto (p.ej. el LLM devuelve texto + <div class="card">...)
    // Detecta bloques HTML significativos en cualquier posición del texto.
    if (/<(div|table|thead|tbody|tr|td|th|ul|ol|pre|section|article|aside|nav|header|footer|caption)\b/i.test(trimmed)) {
        return _wrapStandaloneImages(enhanceHtmlProse(content));
    }

    if (trimmed.includes(',') && trimmed.split('\n').length > 1) {
        var lines = trimmed.split('\n').filter(function (l) { return l.trim(); });
        var hasMarkdownTable = trimmed.includes('|');
        if (!hasMarkdownTable && looksLikeCsv(lines)) {
            return formatCSV(lines);
        }
    }

    if (typeof showdown !== 'undefined') {
        // Detect actual markdown structure (not just any character).
        // Avoid false positives: a paragraph mentioning "20-30 grados" is NOT markdown.
        var looksLikeMarkdown =
            trimmed.includes('#') ||           // heading
            trimmed.includes('`') ||            // inline code or code block
            trimmed.includes('```') ||          // fenced code block
            trimmed.includes('**') ||           // bold
            trimmed.includes('__') ||           // bold (alt)
            /^\s*[-*+]\s/m.test(trimmed) ||     // unordered list item at line start
            /^\d+\.\s/m.test(trimmed) ||        // ordered list item
            /^\|.+\|$/m.test(trimmed);          // table row: |col1|col2|

        if (looksLikeMarkdown) {
            var markdownResult = formatMarkdown(content);
            if (markdownResult && markdownResult !== content) {
                return _wrapStandaloneImages(markdownResult);
            }
        }
    }

    return escapeHtml(content).replace(/\n/g, '<br/>');
}


export {
    DEFAULT_DECIMAL_PLACES,
    getSessionLocale,
    getSessionTz,
    formatWallclock,
    isLikelyHtml,
    escapeHtml,
    formatContent,
    formatMarkdown,
    enhanceHtmlProse,
    formatCSV,
    formatJsonWithLineBreaks,
    formatNumber,
    formatJsonAsTable,
};
