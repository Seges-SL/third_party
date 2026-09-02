/** @odoo-module **/
import { _t } from "@web/core/l10n/translation";

/**
 * pns_ai_chatboo.export — Export utilities for Chatboo messages.
 */

    /** jsPDF UMD namespace (`{ jsPDF }`). Odoo 19 only has it after the classic pre/UMD/post load. */
    function jspdfNamespace() {
        var g = typeof globalThis !== "undefined" ? globalThis : window;
        var ns = g && g.jspdf;
        return ns && ns.jsPDF ? ns : null;
    }

    function jspdfCtor() {
        var ns = jspdfNamespace();
        return ns ? ns.jsPDF : null;
    }

    // ═══════════════════════════════════════════════════════════════════════
    // HTML ↔ Markdown conversion (pure, no ctx needed)
    // ═══════════════════════════════════════════════════════════════════════

    /**
     * Convert an HTML table DOM node to Markdown table syntax.
     *
     * @param {HTMLTableElement} table - DOM table element
     * @returns {string} Markdown table string
     */
    function tableToMarkdown(table) {
        var rows = table.querySelectorAll('tr');
        if (rows.length === 0) return '';

        var markdownRows = [];
        var isFirstRow = true;

        rows.forEach(function (row) {
            var cells = Array.from(row.querySelectorAll('th, td')).filter(function (cell) {
                return !(cell.classList && cell.classList.contains('o_chatboo_noexport'));
            });
            var rowData = cells.map(function (cell) {
                return cell.textContent.trim().replace(/\|/g, '\\|');
            });

            if (isFirstRow) {
                markdownRows.push('| ' + rowData.join(' | ') + ' |');
                markdownRows.push('| ' + rowData.map(function () { return '---'; }).join(' | ') + ' |');
                isFirstRow = false;
            } else {
                markdownRows.push('| ' + rowData.join(' | ') + ' |');
            }
        });

        return markdownRows.join('\n');
    }

    /**
     * Convert HTML content to Markdown.
     *
     * Recursively processes DOM nodes: tables → Markdown tables,
     * headings → # syntax, lists → - / 1. syntax, code → backticks.
     *
     * @param {string} html - HTML string to convert
     * @returns {string} Markdown string
     */
    function htmlToMarkdown(html) {
        if (!html) return '';

        var tempDiv = document.createElement('div');
        tempDiv.innerHTML = html;

        var markdown = '';

        var processNode = function (node) {
            if (node.nodeType === Node.TEXT_NODE) {
                return node.textContent;
            }

            if (node.nodeType !== Node.ELEMENT_NODE) {
                return '';
            }

            var tagName = node.tagName.toLowerCase();
            var children = Array.from(node.childNodes).map(processNode).join('');

            switch (tagName) {
                case 'table':
                    return tableToMarkdown(node) + '\n\n';
                case 'ul':
                case 'ol':
                    var items = node.querySelectorAll('li');
                    var listMarkdown = '';
                    items.forEach(function (item, index) {
                        var prefix = tagName === 'ol' ? (index + 1) + '. ' : '- ';
                        var itemText = Array.from(item.childNodes)
                            .map(processNode)
                            .join('')
                            .trim()
                            .replace(/\n/g, ' ');
                        listMarkdown += prefix + itemText + '\n';
                    });
                    return listMarkdown + '\n';
                case 'pre':
                    var codeElement = node.querySelector('code');
                    if (codeElement) {
                        var codeText = codeElement.textContent;
                        var language = codeElement.className.match(/language-(\w+)/);
                        var lang = language ? language[1] : '';
                        return '```' + lang + '\n' + codeText + '\n```\n\n';
                    }
                    return '```\n' + node.textContent + '\n```\n\n';
                case 'code':
                    if (node.parentElement.tagName.toLowerCase() !== 'pre') {
                        return '`' + node.textContent + '`';
                    }
                    return node.textContent;
                case 'strong': case 'b':
                    return '**' + children + '**';
                case 'em': case 'i':
                    return '*' + children + '*';
                case 'p':
                    return children + '\n\n';
                case 'br':
                    return '\n';
                case 'div':
                    if (node.querySelector('table')) {
                        return children;
                    }
                    return children + '\n';
                case 'h1': return '# ' + children + '\n\n';
                case 'h2': return '## ' + children + '\n\n';
                case 'h3': return '### ' + children + '\n\n';
                case 'h4': return '#### ' + children + '\n\n';
                case 'h5': return '##### ' + children + '\n\n';
                case 'h6': return '###### ' + children + '\n\n';
                default:
                    return children;
            }
        };

        Array.from(tempDiv.childNodes).forEach(function (node) {
            markdown += processNode(node);
        });

        markdown = markdown.replace(/\n{3,}/g, '\n\n');
        return markdown.trim();
    }

    /**
     * Convert Markdown to formatted text for PDF text rendering.
     * Strips formatting marks, indents code, formats tables as plain text.
     *
     * @param {string} markdown - Markdown source
     * @returns {string} Plain-text suitable for jsPDF
     */
    function markdownToPDFText(markdown) {
        if (!markdown) return '';

        var lines = markdown.split('\n');
        var output = [];
        var inCodeBlock = false;
        var codeBlockLang = '';
        var inTable = false;
        var tableRows = [];

        lines.forEach(function (line) {
            if (line.trim().startsWith('```')) {
                if (inCodeBlock) {
                    inCodeBlock = false;
                    output.push('');
                } else {
                    codeBlockLang = line.trim().substring(3).trim();
                    inCodeBlock = true;
                    output.push('[Code' + (codeBlockLang ? ': ' + codeBlockLang : '') + ']');
                }
                return;
            }

            if (inCodeBlock) {
                output.push('  ' + line);
                return;
            }

            if (line.includes('|') && line.trim().startsWith('|')) {
                if (!inTable) {
                    inTable = true;
                    tableRows = [];
                }
                if (!line.match(/^\|\s*[-:]+/)) {
                    var cells = line.split('|').map(function (c) { return c.trim(); }).filter(function (c) { return c; });
                    tableRows.push(cells);
                }
                return;
            } else if (inTable) {
                inTable = false;
                if (tableRows.length > 0) {
                    var headers = tableRows[0];
                    output.push(headers.join(' | '));
                    output.push('-'.repeat(headers.join(' | ').length));
                    tableRows.slice(1).forEach(function (row) {
                        output.push(row.join(' | '));
                    });
                    output.push('');
                }
                tableRows = [];
            }

            if (line.startsWith('# ')) {
                output.push(line.substring(2).toUpperCase()); output.push('');
            } else if (line.startsWith('## ')) {
                output.push(line.substring(3).toUpperCase()); output.push('');
            } else if (line.startsWith('### ')) {
                output.push(line.substring(4)); output.push('');
            } else if (line.startsWith('#### ')) {
                output.push(line.substring(5)); output.push('');
            } else if (line.startsWith('##### ')) {
                output.push(line.substring(6)); output.push('');
            } else if (line.startsWith('###### ')) {
                output.push(line.substring(7)); output.push('');
            } else if (line.match(/^\d+\.\s/)) {
                output.push('  ' + line);
            } else if (line.startsWith('- ') || line.startsWith('* ')) {
                output.push('  • ' + line.substring(2));
            } else {
                output.push(line
                    .replace(/\*\*(.*?)\*\*/g, '$1')
                    .replace(/\*(.*?)\*/g, '$1')
                    .replace(/`(.*?)`/g, '$1'));
            }
        });

        if (inTable && tableRows.length > 0) {
            var headers = tableRows[0];
            output.push(headers.join(' | '));
            output.push('-'.repeat(headers.join(' | ').length));
            tableRows.slice(1).forEach(function (row) {
                output.push(row.join(' | '));
            });
        }

        return output.join('\n');
    }

    /**
     * Convert Markdown into ordered segments for PDF text rendering, tagging
     * each run as monospace (tables, code) or proportional (prose). Same parse
     * rules as markdownToPDFText, but keeps the tabular/prose distinction so the
     * caller can pick a fixed-width font that lines up columns.
     *
     * @param {string} markdown - Markdown source
     * @returns {Array<{text: string, mono: boolean}>}
     */
    function markdownToPDFSegments(markdown) {
        if (!markdown) return [];

        var lines = markdown.split('\n');
        var segments = [];
        var emit = function (text, mono) {
            var last = segments[segments.length - 1];
            if (last && last.mono === mono) {
                last.text += '\n' + text;
            } else {
                segments.push({ text: text, mono: mono });
            }
        };

        var inCodeBlock = false;
        var codeBlockLang = '';
        var inTable = false;
        var tableRows = [];

        var flushTable = function () {
            if (tableRows.length > 0) {
                var headers = tableRows[0];
                emit(headers.join(' | '), true);
                emit('-'.repeat(headers.join(' | ').length), true);
                tableRows.slice(1).forEach(function (row) {
                    emit(row.join(' | '), true);
                });
                emit('', true);
            }
            tableRows = [];
        };

        lines.forEach(function (line) {
            if (line.trim().startsWith('```')) {
                if (inCodeBlock) {
                    inCodeBlock = false;
                    emit('', true);
                } else {
                    codeBlockLang = line.trim().substring(3).trim();
                    inCodeBlock = true;
                    emit('[Code' + (codeBlockLang ? ': ' + codeBlockLang : '') + ']', true);
                }
                return;
            }

            if (inCodeBlock) {
                emit('  ' + line, true);
                return;
            }

            if (line.includes('|') && line.trim().startsWith('|')) {
                if (!inTable) {
                    inTable = true;
                    tableRows = [];
                }
                if (!line.match(/^\|\s*[-:]+/)) {
                    var cells = line.split('|').map(function (c) { return c.trim(); }).filter(function (c) { return c; });
                    tableRows.push(cells);
                }
                return;
            } else if (inTable) {
                inTable = false;
                flushTable();
            }

            if (line.startsWith('# ')) {
                emit(line.substring(2).toUpperCase(), false); emit('', false);
            } else if (line.startsWith('## ')) {
                emit(line.substring(3).toUpperCase(), false); emit('', false);
            } else if (line.startsWith('### ')) {
                emit(line.substring(4), false); emit('', false);
            } else if (line.startsWith('#### ')) {
                emit(line.substring(5), false); emit('', false);
            } else if (line.startsWith('##### ')) {
                emit(line.substring(6), false); emit('', false);
            } else if (line.startsWith('###### ')) {
                emit(line.substring(7), false); emit('', false);
            } else if (/^#{1,6}\s*$/.test(line.trim())) {
                // Orphan heading mark — skip
            } else if (line.match(/^\d+\.\s/)) {
                emit('  ' + line, false);
            } else if (line.startsWith('- ') || line.startsWith('* ')) {
                emit('  • ' + line.substring(2), false);
            } else {
                emit(line
                    .replace(/\*\*(.*?)\*\*/g, '$1')
                    .replace(/\*(.*?)\*/g, '$1')
                    .replace(/`(.*?)`/g, '$1'), false);
            }
        });

        if (inTable && tableRows.length > 0) {
            flushTable();
        }

        return segments;
    }

    /**
     * Convert Markdown to HTML (legacy helper for copy/export paths).
     * Uses Showdown if available, falls back to basic regex conversion.
     *
     * @param {string} markdown - Markdown source
     * @returns {string} HTML string
     */
    function markdownToHTML(markdown) {
        if (!markdown) return '';

        if (typeof showdown !== 'undefined') {
            try {
                var converter = new showdown.Converter({
                    tables: true,
                    strikethrough: true,
                    tasklists: true,
                    simpleLineBreaks: false,
                    openLinksInNewWindow: true
                });
                return converter.makeHtml(markdown);
            } catch (e) {
                console.warn('Error converting Markdown with Showdown, using fallback:', e);
            }
        }

        var html = markdown
            .replace(/^### (.*$)/gim, '<h3>$1</h3>')
            .replace(/^## (.*$)/gim, '<h2>$1</h2>')
            .replace(/^# (.*$)/gim, '<h1>$1</h1>')
            .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
            .replace(/\*(.*?)\*/g, '<em>$1</em>')
            .replace(/```(\w+)?\n([\s\S]*?)```/g, '<pre><code>$2</code></pre>')
            .replace(/`([^`]+)`/g, '<code>$1</code>')
            .replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2">$1</a>')
            .replace(/\n\n/g, '</p><p>')
            .replace(/\n/g, '<br/>');

        if (!html.startsWith('<')) {
            html = '<p>' + html + '</p>';
        }
        return html;
    }

    /**
     * Normalize a filename: remove accents/diacritics, keep ASCII-safe chars.
     *
     * @param {string} text - Raw text for filename
     * @returns {string} Sanitized filename fragment
     */
    function normalizeFilename(text) {
        if (!text) return '';
        return text
            .normalize('NFD')
            .replace(/[\u0300-\u036f]/g, '')
            .replace(/ñ/g, 'n')
            .replace(/Ñ/g, 'N')
            .replace(/[^a-zA-Z0-9\s_-]/g, ' ')
            .replace(/[\s-]+/g, '_')
            .replace(/_+/g, '_')
            .replace(/^_|_$/g, '')
            .toLowerCase()
            .substring(0, 50);
    }

    var AXIS_SLASHES = {
        'painter-local': 1, 'painter-free': 1,
        'foot-verbose': 1, 'foot-laconic': 1,
        'show-table': 1, 'show-chart': 1,
    };
    var FUNCTION_WORDS = {
        a: 1, an: 1, the: 1, el: 1, la: 1, los: 1, las: 1, un: 1, una: 1,
        de: 1, del: 1, al: 1, y: 1, o: 1, en: 1, con: 1, por: 1, para: 1,
        me: 1, te: 1, se: 1, mi: 1, que: 1, como: 1, please: 1, can: 1,
        quiero: 1, puedes: 1, haz: 1, hazme: 1, dame: 1, make: 1, draw: 1,
        paint: 1, pinta: 1, pintas: 1, pintame: 1, dibuja: 1, dibujas: 1,
        show: 1, need: 1, necesito: 1, esto: 1, eso: 1,
    };
    var FORMAT_WORDS = {
        svg: 1, pdf: 1, png: 1, jpg: 1, jpeg: 1, gif: 1, html: 1,
        xlsx: 1, xls: 1, csv: 1, zip: 1, file: 1, archivo: 1, imagen: 1,
        image: 1, drawing: 1, dibujo: 1, export: 1, download: 1,
    };

    function contentFilename(prompt, extension, skillCode) {
        var rest = (prompt || '').replace(/^\s+/, '');
        var skill = (skillCode || '').replace(/^\/+/, '');
        while (rest.charAt(0) === '/') {
            var body = rest.slice(1).replace(/^\s+/, '');
            var sp = body.search(/\s/);
            var token = (sp < 0 ? body : body.slice(0, sp)).replace(/[.,;:!?]+$/, '');
            rest = sp < 0 ? '' : body.slice(sp).replace(/^\s+/, '');
            var low = token.toLowerCase();
            if (AXIS_SLASHES[low]) {
                continue;
            }
            if (!skill) {
                skill = token;
            }
            break;
        }
        var explicit = rest.match(
            /([A-Za-z0-9][A-Za-z0-9._-]{0,80})\.(svg|pdf|png|jpe?g|gif|webp|xlsx?|csv|zip|docx?)\b/i
        );
        var stem = '';
        if (explicit) {
            stem = normalizeFilename(explicit[1]);
        } else {
            var slugged = normalizeFilename(rest);
            var parts = slugged.split('_');
            var kept = [];
            for (var i = 0; i < parts.length; i++) {
                var tok = parts[i];
                if (!tok || FUNCTION_WORDS[tok] || FORMAT_WORDS[tok] || /^\d+$/.test(tok)) {
                    continue;
                }
                kept.push(tok);
            }
            stem = kept.join('_').substring(0, 50);
        }
        if (!stem && skill) {
            stem = normalizeFilename(skill);
        }
        if (!stem) {
            stem = 'response';
        }
        return stem + '.' + extension;
    }

    /**
     * Extract plain text content from a message object.
     *
     * @param {Object} msg - Message object with content / original_content
     * @returns {string} Plain text
     */
    function extractPlainText(msg) {
        if (msg.original_content) {
            return msg.original_content;
        }
        var tempDiv = document.createElement('div');
        if (msg.content) {
            tempDiv.innerHTML = msg.content;
        } else {
            return '';
        }
        return tempDiv.textContent || tempDiv.innerText || '';
    }

    // ═══════════════════════════════════════════════════════════════════════
    // Context-dependent functions (need ctx.messages, ctx.notification, etc.)
    // ═══════════════════════════════════════════════════════════════════════

    /**
     * Filename from clip title / session chip, else the user prompt.
     *
     * @param {number} msgIndex - Index in ctx.messages
     * @param {string} extension - File extension (pdf, xlsx)
     * @param {ExportContext} ctx - Component context
     * @returns {string} Filename
     */
    function generateFilename(msgIndex, extension, ctx) {
        var msg = ctx.messages[msgIndex];
        if (!msg) {
            return 'chatboo.' + extension;
        }
        var titled = clipDataTitle(msg.clip_data);
        if (titled) {
            return normalizeFilename(titled) + '.' + extension;
        }
        var files = msg.files;
        if (files && files.length && files[0] && files[0].name) {
            var stem = String(files[0].name).replace(/\.[^.]+$/, '');
            var slug = normalizeFilename(stem);
            if (slug) {
                return slug + '.' + extension;
            }
        }

        var userPrompt = '';
        for (var i = msgIndex - 1; i >= 0; i--) {
            if (ctx.messages[i].role === 'user') {
                var userMsg = ctx.messages[i];
                if (userMsg.original_content) {
                    userPrompt = userMsg.original_content;
                } else if (userMsg.content) {
                    var tempDiv = document.createElement('div');
                    tempDiv.innerHTML = userMsg.content;
                    userPrompt = tempDiv.textContent || tempDiv.innerText || '';
                }
                break;
            }
        }

        return contentFilename(userPrompt, extension, ctx.activeSkillCode);
    }

    function sessionFileIsInline(file) {
        var name = String((file && file.name) || '').toLowerCase();
        var mt = String((file && file.mimetype) || '').toLowerCase();
        return mt.indexOf('svg') !== -1 || /\.svg$/i.test(name);
    }

    function sessionFileHref(file) {
        var url = (file && file.url) || '';
        if (!url || sessionFileIsInline(file)) {
            return url;
        }
        var name = String((file && file.name) || 'download').replace(/[\\/]/g, '_');
        var encoded = encodeURIComponent(name);
        var m = url.match(/^(.*\/web\/content\/)(\d+)(?:\/[^?]*)?(\?[^#]*)?(#.*)?$/);
        if (!m) {
            if (url.indexOf('download=') === -1) {
                url += (url.indexOf('?') >= 0 ? '&' : '?') + 'download=true';
            }
            return url;
        }
        var query = m[3] || '';
        if (!query) {
            query = '?download=true';
        } else if (!/[?&]download=/.test(query)) {
            query += '&download=true';
        } else {
            query = query.replace(/([?&])download=[^&]*/g, '$1download=true');
        }
        return m[1] + m[2] + '/' + encoded + query + (m[4] || '');
    }

    /**
     * Perform the clipboard write via modern API, with icon feedback.
     *
     * @param {string} textContent - Text to copy
     * @param {HTMLElement} iconElement - Icon to toggle for visual feedback
     * @param {ExportContext} ctx - Component context (notification)
     */
    function doCopy(textContent, iconElement, ctx) {
        if (navigator.clipboard && navigator.clipboard.writeText) {
            navigator.clipboard.writeText(textContent).then(function () {
                var originalClass = iconElement.className;
                iconElement.className = 'fa fa-check text-success';
                iconElement.style.opacity = '1';
                setTimeout(function () {
                    iconElement.className = originalClass;
                    iconElement.style.opacity = '0.7';
                }, 2000);

                if (ctx.notification) {
                    ctx.notification({
                        message: _t('Copied to clipboard'),
                        type: 'success',
                        sticky: false
                    });
                }
            }).catch(function (err) {
                console.error('Error copying to clipboard:', err);
                fallbackCopy(textContent, iconElement, ctx);
            });
        } else {
            fallbackCopy(textContent, iconElement, ctx);
        }
    }

    /**
     * Fallback copy method for older browsers (execCommand).
     *
     * @param {string} text - Text to copy
     * @param {HTMLElement} iconElement - Icon for feedback
     * @param {ExportContext} ctx - Component context (notification)
     */
    function fallbackCopy(text, iconElement, ctx) {
        var textArea = document.createElement('textarea');
        textArea.value = text;
        textArea.style.position = 'fixed';
        textArea.style.left = '-999999px';
        textArea.style.top = '-999999px';
        document.body.appendChild(textArea);
        textArea.focus();
        textArea.select();

        try {
            var successful = document.execCommand('copy');
            if (successful) {
                var originalClass = iconElement.className;
                iconElement.className = 'fa fa-check text-success';
                iconElement.style.opacity = '1';
                setTimeout(function () {
                    iconElement.className = originalClass;
                    iconElement.style.opacity = '0.7';
                }, 2000);

                if (ctx.notification) {
                    ctx.notification({
                        message: _t('Copied to clipboard'),
                        type: 'success',
                        sticky: false
                    });
                }
            }
        } catch (err) {
            console.error('Fallback copy failed:', err);
            if (ctx.notification) {
                ctx.notification({
                    message: _t('Error copying to clipboard'),
                    type: 'danger',
                    sticky: false
                });
            }
        } finally {
            document.body.removeChild(textArea);
        }
    }

    /**
     * Copy message content to clipboard.
     * Supports 'content' (raw text or HTML source, as-is) and 'markdown'
     * (HTML converted to Markdown) modes.
     *
     * @param {Event} ev - Click event with data-msg-index and data-copy-type attributes
     * @param {ExportContext} ctx - Component context
     */
    function copyToClipboard(ev, ctx) {
        var msgIndex = parseInt(ev.target.getAttribute('data-msg-index'));
        var copyType = ev.target.getAttribute('data-copy-type') || 'content';

        if (isNaN(msgIndex) || msgIndex < 0 || msgIndex >= ctx.messages.length) {
            return;
        }

        var msg = ctx.messages[msgIndex];
        if (!msg) return;

        var textToCopy = '';

        if (copyType === 'markdown' && msg.role === 'assistant') {
            var clipMd = clipDataToMarkdown(msg.clip_data);
            if (clipMd) {
                textToCopy = clipMd;
            } else {
                var mdHtml = resolveExportHtml(msg);
                if (mdHtml) {
                    textToCopy = htmlToMarkdown(mdHtml);
                } else {
                    textToCopy = msg.original_content || msg.content || '';
                }
            }

            textToCopy = textToCopy
                .replace(/\r\n/g, '\n')
                .replace(/\r/g, '\n')
                .replace(/\n/g, '\r\n')
                .trim();
        } else {
            // Misma fuente que el chat (HTML formateado), no el raw del último payload.
            var clipPlain = clipDataToTsv(msg.clip_data);
            if (clipPlain) {
                textToCopy = clipPlain;
            } else {
            var plainHtml = resolveExportHtml(msg);
            if (plainHtml) {
                textToCopy = htmlToPlainExportText(plainHtml);
            } else if (msg.original_content) {
                textToCopy = msg.original_content;
            } else {
                var messageCards = ctx.messagesEl.querySelectorAll('.o_chatboo_message, .o_chatboo_bubble');
                if (msgIndex < messageCards.length) {
                    var messageCard = messageCards[msgIndex];
                    var contentDiv = messageCard.querySelector('.o_chatboo_content');

                    if (contentDiv) {
                        var innerHTML = contentDiv.innerHTML;
                        var tempDivForBr = document.createElement('div');
                        tempDivForBr.innerHTML = innerHTML.replace(/<br\s*\/?>/gi, '\n');
                        textToCopy = tempDivForBr.textContent || tempDivForBr.innerText || '';
                    } else {
                        var tempDivFallback = document.createElement('div');
                        tempDivFallback.innerHTML = msg.content || '';
                        textToCopy = tempDivFallback.textContent || tempDivFallback.innerText || '';
                    }
                } else {
                    var tempDivFallback2 = document.createElement('div');
                    tempDivFallback2.innerHTML = msg.content || '';
                    textToCopy = tempDivFallback2.textContent || tempDivFallback2.innerText || '';
                }
            }
            }

            textToCopy = textToCopy
                .replace(/\r\n/g, '\n')
                .replace(/\r/g, '\n')
                .replace(/\n/g, '\r\n')
                .trim();
        }

        doCopy(textToCopy, ev.target, ctx);
    }

    /**
     * Download message as structured PDF report (jsPDF + AutoTable).
     *
     * Uses the same HTML / data-chatboo-dataset as the chat render and Excel export.
     *
     * @param {Event} ev - Click event with data-msg-index
     * @param {ExportContext} ctx - Component context
     */
    /**
     * Locate the on-screen .o_chatboo_content for this PDF button (true WYSIWYG).
     *
     * @param {Event} ev
     * @returns {HTMLElement|null}
     */
    function resolveBubbleContentNode(ev) {
        var btn = ev && (ev.currentTarget || ev.target);
        if (!btn || !btn.closest) {
            return null;
        }
        var bubble = btn.closest('.o_chatboo_message, .o_chatboo_bubble');
        if (!bubble) {
            return null;
        }
        return bubble.querySelector('.o_chatboo_content');
    }

    /**
     * Off-screen clone of the bubble for html2canvas (strip toolbar, keep chart).
     *
     * @param {HTMLElement|null} sourceEl
     * @param {string} [fallbackHtml]
     * @returns {HTMLElement}
     */
    function buildPdfCaptureHost(sourceEl, fallbackHtml) {
        var host = document.createElement('div');
        host.setAttribute('data-chatboo-pdf-host', '1');
        host.className = 'o_chatboo_pdf_capture';
        host.style.cssText = [
            'position:fixed',
            'left:-14000px',
            'top:0',
            'width:794px',
            'padding:28px 36px',
            'background:#ffffff',
            'color:#212529',
            'box-sizing:border-box',
            'overflow:visible',
            'z-index:-1',
            'font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,"Helvetica Neue",Arial,sans-serif',
            'font-size:14px',
            'line-height:1.55',
            'text-align:left',
            'letter-spacing:normal',
            'word-spacing:normal',
        ].join(';');
        var inner;
        if (sourceEl) {
            inner = sourceEl.cloneNode(true);
        } else {
            inner = document.createElement('div');
            inner.className = 'o_chatboo_content o_chatboo_prose';
            inner.innerHTML = fallbackHtml || '';
        }
        var kill = inner.querySelectorAll(
            '.o_chatboo_chart_toolbar, .o_chatboo_export_bar,' +
            ' .o_chatboo_card_resize, .o_chatboo_card_width_reset,' +
            ' .o_chatboo_copy_btn, .o_chatboo_noexport, .o_chatboo_ts'
        );
        for (var i = 0; i < kill.length; i++) {
            if (kill[i].parentNode) {
                kill[i].parentNode.removeChild(kill[i]);
            }
        }
        // Avoid bubble max-width / flex shrink looking like letter-spacing.
        inner.style.maxWidth = 'none';
        inner.style.width = '100%';
        inner.style.letterSpacing = 'normal';
        inner.style.wordSpacing = 'normal';
        inner.style.textAlign = 'left';
        host.appendChild(inner);
        document.body.appendChild(host);
        return host;
    }

    /**
     * Slice a tall canvas into A4 PDF pages (JPEG, Helvetica-free raster).
     *
     * @param {HTMLCanvasElement} canvas
     * @param {Function} jsPDF
     * @param {number} msgIndex
     * @param {ExportContext} ctx
     */
    function saveCanvasAsPdf(canvas, jsPDF, msgIndex, ctx) {
        var pdf = new jsPDF({ orientation: 'portrait', unit: 'mm', format: 'a4' });
        var pageW = pdf.internal.pageSize.getWidth();
        var pageH = pdf.internal.pageSize.getHeight();
        var margin = 8;
        var usableW = pageW - 2 * margin;
        var usableH = pageH - 2 * margin;
        var imgW = usableW;
        var pageCanvasPx = (usableH * canvas.width) / imgW;
        var y = 0;
        var page = 0;
        while (y < canvas.height - 1) {
            if (page > 0) {
                pdf.addPage();
            }
            var sliceH = Math.min(pageCanvasPx, canvas.height - y);
            var pageCanvas = document.createElement('canvas');
            pageCanvas.width = canvas.width;
            pageCanvas.height = Math.max(1, Math.ceil(sliceH));
            var ctx2d = pageCanvas.getContext('2d');
            ctx2d.fillStyle = '#ffffff';
            ctx2d.fillRect(0, 0, pageCanvas.width, pageCanvas.height);
            ctx2d.drawImage(
                canvas,
                0, y, canvas.width, sliceH,
                0, 0, canvas.width, sliceH
            );
            var sliceHmm = (sliceH * imgW) / canvas.width;
            pdf.addImage(
                pageCanvas.toDataURL('image/jpeg', 0.93),
                'JPEG',
                margin,
                margin,
                imgW,
                sliceHmm
            );
            y += sliceH;
            page += 1;
        }
        var filename = generateFilename(msgIndex, 'pdf', ctx);
        pdf.save(filename);
        if (ctx.notification) {
            ctx.notification({ message: 'PDF descargado: ' + filename, type: 'success', sticky: false });
        }
    }

    /**
     * PDF = screenshot of the bubble already rendered on screen (WYSIWYG).
     * Avoids re-typesetting Markdown with jsPDF fonts / AutoTable justify bugs.
     *
     * @returns {Promise<boolean>} true if handled
     */
    function generateWysiwygPDF(ev, msg, msgIndex, ctx) {
        var h2c = typeof html2canvas === 'function' ? html2canvas
            : (window.html2canvas || null);
        if (typeof h2c !== 'function') {
            return Promise.resolve(false);
        }
        var jsPDF = jspdfCtor();
        if (!jsPDF) {
            return Promise.resolve(false);
        }
        var sourceEl = resolveBubbleContentNode(ev);
        var fallbackHtml = resolveExportHtml(msg);
        if (!sourceEl && !fallbackHtml) {
            return Promise.resolve(false);
        }
        if (ctx.notification) {
            ctx.notification({
                message: 'Generando PDF…',
                type: 'info',
                sticky: false,
            });
        }
        var host = buildPdfCaptureHost(sourceEl, fallbackHtml);
        return h2c(host, {
            scale: 2,
            useCORS: true,
            allowTaint: true,
            backgroundColor: '#ffffff',
            logging: false,
            windowWidth: host.scrollWidth,
            windowHeight: host.scrollHeight,
        }).then(function (canvas) {
            if (host.parentNode) {
                host.parentNode.removeChild(host);
            }
            saveCanvasAsPdf(canvas, jsPDF, msgIndex, ctx);
            return true;
        }).catch(function (err) {
            if (host.parentNode) {
                host.parentNode.removeChild(host);
            }
            console.error('WYSIWYG PDF failed:', err);
            return false;
        });
    }

    var PDF_LANDSCAPE_MIN_COLS = 6;
    var PDF_LANDSCAPE_MIN_HEADER_CHARS = 48;

    function pdfCellText(cell) {
        if (cell && typeof cell === 'object' && !Array.isArray(cell) && cell.content !== undefined) {
            return String(cell.content == null ? '' : cell.content);
        }
        return String(cell == null ? '' : cell);
    }

    function pdfCellImg(cell) {
        return cell && typeof cell === 'object' ? (cell._pdfImg || '') : '';
    }

    function pdfWinAnsiOk(code) {
        return code === 0x09 || code === 0x0A || code === 0x0D
            || (code >= 0x20 && code <= 0x7E)
            || (code >= 0xA0 && code <= 0xFF);
    }

    function pdfNextCodePoint(s, i) {
        var c = s.charCodeAt(i);
        if (c >= 0xD800 && c <= 0xDBFF && i + 1 < s.length) {
            var d = s.charCodeAt(i + 1);
            if (d >= 0xDC00 && d <= 0xDFFF) {
                return {
                    code: ((c - 0xD800) << 10) + (d - 0xDC00) + 0x10000,
                    next: i + 2,
                };
            }
        }
        return { code: c, next: i + 1 };
    }

    function pdfReadCluster(s, i) {
        var first = pdfNextCodePoint(s, i);
        var start = i;
        var end = first.next;
        var kind = pdfWinAnsiOk(first.code) ? 'text' : 'glyph';
        if (kind === 'text' && end < s.length) {
            var peek = pdfNextCodePoint(s, end);
            if (peek.code === 0xFE0F || peek.code === 0xFE0E || peek.code === 0x20E3) {
                kind = 'glyph';
            }
        }
        if (kind === 'glyph') {
            var guard = 0;
            while (end < s.length && guard < 16) {
                guard += 1;
                var nxt = pdfNextCodePoint(s, end);
                if (nxt.code === 0xFE0F || nxt.code === 0xFE0E || nxt.code === 0x20E3
                    || (nxt.code >= 0x1F3FB && nxt.code <= 0x1F3FF)) {
                    end = nxt.next;
                    continue;
                }
                if (nxt.code === 0x200D) {
                    end = nxt.next;
                    if (end < s.length) {
                        end = pdfNextCodePoint(s, end).next;
                    }
                    continue;
                }
                if (first.code >= 0x1F1E6 && first.code <= 0x1F1FF
                    && nxt.code >= 0x1F1E6 && nxt.code <= 0x1F1FF
                    && end === first.next) {
                    end = nxt.next;
                    continue;
                }
                break;
            }
            return { kind: 'glyph', text: s.slice(start, end), next: end };
        }
        return { kind: 'text', text: s.slice(start, end), next: end };
    }

    function pdfSplitTextRuns(text) {
        text = String(text == null ? '' : text);
        var runs = [];
        var i = 0;
        var buf = '';
        var bufKind = '';
        function flush() {
            if (buf && bufKind) {
                runs.push({ kind: bufKind, text: buf });
            }
            buf = '';
            bufKind = '';
        }
        while (i < text.length) {
            var cluster = pdfReadCluster(text, i);
            i = cluster.next;
            if (cluster.kind === bufKind) {
                buf += cluster.text;
            } else {
                flush();
                buf = cluster.text;
                bufKind = cluster.kind;
            }
        }
        flush();
        return runs;
    }

    var _pdfGlyphCache = {};

    function pdfGlyphPng(cluster) {
        cluster = String(cluster || '');
        if (!cluster) {
            return '';
        }
        if (_pdfGlyphCache[cluster]) {
            return _pdfGlyphCache[cluster];
        }
        if (typeof document === 'undefined') {
            return '';
        }
        try {
            var px = 64;
            var canvas = document.createElement('canvas');
            canvas.width = px;
            canvas.height = px;
            var ctx = canvas.getContext('2d');
            if (!ctx) {
                return '';
            }
            ctx.clearRect(0, 0, px, px);
            ctx.font = Math.round(px * 0.78) + 'px sans-serif';
            ctx.textAlign = 'center';
            ctx.textBaseline = 'middle';
            ctx.fillText(cluster, px / 2, px / 2);
            var url = canvas.toDataURL('image/png');
            _pdfGlyphCache[cluster] = url;
            return url;
        } catch (e) {
            return '';
        }
    }

    function pdfPrepareCell(cell) {
        if (cell && typeof cell === 'object' && !Array.isArray(cell) && cell._pdfImg) {
            return { content: '', _pdfImg: cell._pdfImg };
        }
        if (cell && typeof cell === 'object' && !Array.isArray(cell) && cell._pdfGlyphs) {
            return cell;
        }
        var text = pdfCellText(cell);
        var runs = pdfSplitTextRuns(text);
        var glyphs = [];
        var parts = [];
        var r;
        for (r = 0; r < runs.length; r++) {
            if (runs[r].kind === 'glyph') {
                var png = pdfGlyphPng(runs[r].text);
                if (png) {
                    glyphs.push(png);
                }
            } else {
                parts.push(runs[r].text);
            }
        }
        var content = parts.join('').replace(/^\s+/, '').replace(/\s+$/, '');
        if (!glyphs.length) {
            return text;
        }
        return { content: content, _pdfGlyphs: glyphs };
    }

    function pdfGlyphMm(doc) {
        var fs = doc && doc.getFontSize ? doc.getFontSize() : 10;
        return Math.max(3.2, fs * 0.35);
    }

    function pdfTokenWidth(doc, tok) {
        if (tok.kind === 'glyph') {
            return pdfGlyphMm(doc) + 0.4;
        }
        return doc.getTextWidth ? doc.getTextWidth(tok.text) : tok.text.length * 1.5;
    }

    function pdfRunsToTokens(runs) {
        var tokens = [];
        var i;
        for (i = 0; i < runs.length; i++) {
            if (runs[i].kind === 'glyph') {
                tokens.push({ kind: 'glyph', text: runs[i].text });
            } else {
                var chunks = String(runs[i].text || '').split(/(\s+)/);
                var c;
                for (c = 0; c < chunks.length; c++) {
                    if (chunks[c]) {
                        tokens.push({ kind: 'text', text: chunks[c] });
                    }
                }
            }
        }
        return tokens;
    }

    function pdfSplitRichLines(doc, text, maxWidth) {
        var tokens = pdfRunsToTokens(pdfSplitTextRuns(text));
        var lines = [];
        var cur = [];
        var w = 0;
        var t;
        for (t = 0; t < tokens.length; t++) {
            var tok = tokens[t];
            var tw = pdfTokenWidth(doc, tok);
            var isSpace = tok.kind === 'text' && /^\s+$/.test(tok.text);
            if (cur.length && maxWidth && w + tw > maxWidth && !isSpace) {
                lines.push(cur);
                cur = [];
                w = 0;
            }
            if (!cur.length && isSpace) {
                continue;
            }
            cur.push(tok);
            w += tw;
        }
        if (cur.length) {
            lines.push(cur);
        }
        return lines.length ? lines : [[]];
    }

    function pdfPaintRichTokens(doc, tokens, x, y) {
        var cursor = x;
        var glyphMm = pdfGlyphMm(doc);
        var i;
        for (i = 0; i < tokens.length; i++) {
            var tok = tokens[i];
            if (tok.kind === 'glyph') {
                var png = pdfGlyphPng(tok.text);
                if (png) {
                    try {
                        doc.addImage(png, 'PNG', cursor, y - glyphMm * 0.78, glyphMm, glyphMm);
                    } catch (e) { /* skip */ }
                }
                cursor += glyphMm + 0.4;
            } else {
                doc.text(tok.text, cursor, y);
                cursor += doc.getTextWidth ? doc.getTextWidth(tok.text) : tok.text.length * 1.5;
            }
        }
        return cursor;
    }

    function pdfDrawRichLine(doc, text, x, y, opts) {
        opts = opts || {};
        text = String(text == null ? '' : text);
        var maxWidth = opts.maxWidth;
        var fs = doc.getFontSize ? doc.getFontSize() : 10;
        var lineHeight = opts.lineHeight || Math.max(3.8, fs * 0.42);
        var runs = pdfSplitTextRuns(text);
        var hasGlyph = false;
        var g;
        for (g = 0; g < runs.length; g++) {
            if (runs[g].kind === 'glyph') {
                hasGlyph = true;
                break;
            }
        }
        var lines;
        if (!hasGlyph) {
            lines = maxWidth ? doc.splitTextToSize(text, maxWidth) : [text];
            if (!Array.isArray(lines)) {
                lines = [lines];
            }
        } else {
            lines = null;
        }
        var i;
        if (lines) {
            for (i = 0; i < lines.length; i++) {
                if (opts.breakAt != null && y + lineHeight > opts.breakAt) {
                    doc.addPage();
                    y = opts.margin != null ? opts.margin : 20;
                } else if (opts.pageHeight != null && y > opts.pageHeight - 16) {
                    doc.addPage();
                    y = opts.margin != null ? opts.margin : 14;
                }
                var textOpts = opts.align ? { align: opts.align } : undefined;
                doc.text(lines[i], x, y, textOpts);
                y += lineHeight;
            }
            return y;
        }
        var richLines = maxWidth
            ? pdfSplitRichLines(doc, text, maxWidth)
            : [pdfRunsToTokens(runs)];
        for (i = 0; i < richLines.length; i++) {
            if (opts.breakAt != null && y + lineHeight > opts.breakAt) {
                doc.addPage();
                y = opts.margin != null ? opts.margin : 20;
            } else if (opts.pageHeight != null && y > opts.pageHeight - 16) {
                doc.addPage();
                y = opts.margin != null ? opts.margin : 14;
            }
            pdfPaintRichTokens(doc, richLines[i], x, y);
            y += lineHeight;
        }
        return y;
    }

    function cellLooksLikeImage(val) {
        if (typeof val !== 'string' || !val) {
            return false;
        }
        if (val.indexOf('data:image/') === 0) {
            return true;
        }
        if (val.indexOf('/web/image/') !== -1) {
            return true;
        }
        return /^(iVBORw|\/9j\/|R0lGOD|UklGR)/.test(val.slice(0, 8));
    }

    function imgElementToDataUrl(img) {
        if (!img) {
            return '';
        }
        var src = img.currentSrc || img.src || '';
        if (src.indexOf('data:') === 0) {
            return src;
        }
        try {
            var c = document.createElement('canvas');
            c.width = img.naturalWidth || img.width || 64;
            c.height = img.naturalHeight || img.height || 64;
            if (c.width < 2 || c.height < 2) {
                return '';
            }
            c.getContext('2d').drawImage(img, 0, 0);
            return c.toDataURL('image/png');
        } catch (e) {
            return '';
        }
    }

    function largestChartCanvas(root) {
        var canvases = root && root.querySelectorAll ? root.querySelectorAll('canvas') : [];
        var best = null;
        var area = 0;
        for (var i = 0; i < canvases.length; i++) {
            var canvas = canvases[i];
            var next = (canvas.width || 0) * (canvas.height || 0);
            if (next > area) {
                area = next;
                best = canvas;
            }
        }
        return best;
    }

    function chartInstancePng(inst) {
        if (!inst) {
            return '';
        }
        try {
            if (typeof inst.getDataURL === 'function') {
                return inst.getDataURL({
                    type: 'png',
                    pixelRatio: 2,
                    backgroundColor: '#ffffff',
                }) || '';
            }
        } catch (e) { /* */ }
        try {
            if (typeof inst.toBase64Image === 'function') {
                return inst.toBase64Image('image/png', 1) || '';
            }
        } catch (e2) { /* */ }
        return '';
    }

    function resolveBlockChartInstance(block, host) {
        if (block && block._chatbooChart) {
            return block._chatbooChart;
        }
        var surface = (host || block) && (host || block).querySelector
            ? (host || block).querySelector('.o_chatboo_echarts_surface')
            : null;
        if (surface && window.echarts && typeof window.echarts.getInstanceByDom === 'function') {
            return window.echarts.getInstanceByDom(surface);
        }
        return null;
    }

    function canvasSampleIsPainted(canvas) {
        if (!canvas || canvas.width < 8 || canvas.height < 8) {
            return false;
        }
        try {
            var ctx = canvas.getContext('2d');
            if (!ctx) {
                return false;
            }
            var size = Math.min(32, canvas.width, canvas.height);
            var sx = Math.max(0, Math.floor((canvas.width - size) / 2));
            var sy = Math.max(0, Math.floor((canvas.height - size) / 2));
            var sample = ctx.getImageData(sx, sy, size, size);
            var painted = 0;
            for (var i = 3; i < sample.data.length; i += 4) {
                if (sample.data[i] > 8) {
                    painted += 1;
                }
            }
            return painted > 10;
        } catch (e) {
            return canvas.width > 16;
        }
    }

    function chartHostIsPainted(host) {
        if (!host) {
            return false;
        }
        var block = host.closest ? host.closest('.o_chatboo_table_block') : null;
        if (resolveBlockChartInstance(block, host)) {
            return true;
        }
        var style = window.getComputedStyle ? window.getComputedStyle(host) : null;
        if (style && (style.display === 'none' || style.visibility === 'hidden')) {
            return false;
        }
        if (style && parseFloat(style.height) < 8) {
            return false;
        }
        return canvasSampleIsPainted(largestChartCanvas(host));
    }

    function collectPaintedChartPngs(sourceEl) {
        var out = [];
        if (!sourceEl || !sourceEl.querySelectorAll) {
            return out;
        }
        var api = window.ChatbooCharts;
        var blocks = sourceEl.querySelectorAll('.o_chatboo_table_block');
        var i;
        if (blocks.length && api && typeof api.snapshotPng === 'function') {
            for (i = 0; i < blocks.length; i++) {
                var snap = api.snapshotPng(blocks[i]);
                if (!snap) {
                    continue;
                }
                var mode = blocks[i].getAttribute('data-chatboo-show-mode');
                var before = mode === 'show-chart' || mode === 'chart-table';
                out.push({ dataUrl: snap, before: before });
            }
            return out;
        }
        var hosts = sourceEl.querySelectorAll('.o_chatboo_chart_host');
        for (i = 0; i < hosts.length; i++) {
            var host = hosts[i];
            var block = host.closest ? host.closest('.o_chatboo_table_block') : null;
            var png = chartInstancePng(resolveBlockChartInstance(block, host));
            if (!png) {
                var canvas = largestChartCanvas(host);
                if (!canvas || !chartHostIsPainted(host)) {
                    continue;
                }
                try {
                    png = canvas.toDataURL('image/png');
                } catch (e) { /* tainted canvas */ }
            }
            if (!png) {
                continue;
            }
            var hostMode = block && block.getAttribute('data-chatboo-show-mode');
            out.push({
                dataUrl: png,
                before: hostMode === 'show-chart' || hostMode === 'chart-table',
            });
        }
        return out;
    }

    function isExportChromeImg(img) {
        if (!img || !img.closest) {
            return true;
        }
        return !!(
            img.closest('table') ||
            img.closest('.o_chatboo_table_block') ||
            img.closest('.o_chatboo_chart_host') ||
            img.closest('.o_chatboo_noexport') ||
            img.closest('.o_chatboo_file_banner') ||
            img.closest('.o_chatboo_file_banner_card') ||
            img.closest('.o_chatboo_export_bar')
        );
    }

    function collectStandaloneImageFigures(sourceEl) {
        var out = [];
        if (!sourceEl || !sourceEl.querySelectorAll) {
            return out;
        }
        var imgs = sourceEl.querySelectorAll('img');
        for (var i = 0; i < imgs.length; i++) {
            var img = imgs[i];
            if (isExportChromeImg(img)) {
                continue;
            }
            var w = img.naturalWidth || img.width || 0;
            var h = img.naturalHeight || img.height || 0;
            if (w && h && w < 20 && h < 20) {
                continue;
            }
            var dataUrl = imgElementToDataUrl(img);
            if (dataUrl) {
                out.push({
                    dataUrl: dataUrl,
                    before: false,
                    figure: true,
                    width: w,
                    height: h,
                });
            }
        }
        return out;
    }

    function figuresFromHtmlOrEl(sourceEl, html) {
        var fromEl = collectStandaloneImageFigures(sourceEl);
        if (fromEl.length) {
            return fromEl;
        }
        if (!html) {
            return [];
        }
        var host = document.createElement('div');
        host.innerHTML = html;
        return collectStandaloneImageFigures(host);
    }

    function clipLandscapeFlag(clip) {
        if (clip && typeof clip === 'object' && !Array.isArray(clip) && Object.prototype.hasOwnProperty.call(clip, 'landscape')) {
            return !!clip.landscape;
        }
        return null;
    }

    function clipIncludeTable(clip) {
        if (!clip || typeof clip !== 'object' || Array.isArray(clip)) {
            return true;
        }
        if (Object.prototype.hasOwnProperty.call(clip, 'include_table')) {
            return !!clip.include_table;
        }
        return true;
    }

    function clipIncludeChart(clip) {
        if (!clip || typeof clip !== 'object' || Array.isArray(clip)) {
            return null;
        }
        if (Object.prototype.hasOwnProperty.call(clip, 'include_chart')) {
            return !!clip.include_chart;
        }
        return null;
    }

    var _STAT_I18N = {
        table: _t('Table'),
        title: _t('Statistics'),
        n: _t('n'),
        min: _t('Min'),
        max: _t('Max'),
        mean: _t('Mean'),
        median: _t('Median'),
        stdev: _t('Std. dev.'),
        sum: _t('Sum'),
    };

    function pdfShouldBeLandscape(sections, explicit) {
        if (explicit === true || explicit === false) {
            return explicit;
        }
        var maxCols = 0;
        var headerChars = 0;
        (sections || []).forEach(function (section) {
            var row = section.aoa && section.aoa[0];
            if (!row) {
                return;
            }
            maxCols = Math.max(maxCols, row.length);
            var chars = 0;
            row.forEach(function (cell) {
                chars += pdfCellText(cell).length;
            });
            headerChars = Math.max(headerChars, chars);
        });
        return maxCols >= PDF_LANDSCAPE_MIN_COLS || headerChars >= PDF_LANDSCAPE_MIN_HEADER_CHARS;
    }

    function loadImgDataUrl(src) {
        return new Promise(function (resolve) {
            if (!src) {
                resolve('');
                return;
            }
            if (src.indexOf('data:') === 0) {
                resolve(src);
                return;
            }
            var img = new Image();
            img.crossOrigin = 'anonymous';
            img.onload = function () {
                resolve(imgElementToDataUrl(img) || '');
            };
            img.onerror = function () {
                resolve('');
            };
            img.src = src;
        });
    }

    function resolveSectionImages(sections) {
        var jobs = [];
        (sections || []).forEach(function (section) {
            (section.aoa || []).forEach(function (row) {
                (row || []).forEach(function (cell) {
                    if (!cell || typeof cell !== 'object' || cell._pdfImg || !cell._imgSrc) {
                        return;
                    }
                    jobs.push(loadImgDataUrl(cell._imgSrc).then(function (url) {
                        if (url) {
                            cell._pdfImg = url;
                        }
                    }));
                });
            });
        });
        return Promise.all(jobs);
    }

    function enrichSectionsImagesFromDom(sections, sourceEl) {
        if (!sourceEl || !sections || !sections.length) {
            return;
        }
        var tables = sourceEl.querySelectorAll('table');
        var n = Math.min(sections.length, tables.length);
        for (var s = 0; s < n; s++) {
            var live = htmlTableToAoa(tables[s], { images: true });
            if (live.length) {
                sections[s].aoa = live;
            }
        }
    }

    /**
     * Structured PDF (AutoTable + painted chart rasters). html2canvas is last resort.
     */
    function downloadAsPDFLegacy(msg, msgIndex, ctx, extras) {
        extras = extras || {};
        var jsPDF = jspdfCtor();
        if (!jsPDF) {
            if (ctx.notification) {
                ctx.notification({ message: _t('Error: jsPDF is not available'), type: 'danger', sticky: false });
            }
            return;
        }
        var exportHtml = resolveExportHtml(msg);
        var sections = extras.sections || extractTableSections(exportHtml, msg.clip_data, { images: true });
        var reportTitle = extras.title || extractReportTitle(exportHtml) || clipDataTitle(msg.clip_data);
        var rawMd = msg.original_content || '';
        if (!rawMd && msg.content && String(msg.content).indexOf('<') === -1) {
            rawMd = msg.content;
        }
        if (typeof ChatbooSse !== 'undefined' && ChatbooSse.normalizeGluedMarkdown && rawMd) {
            rawMd = ChatbooSse.normalizeGluedMarkdown(rawMd);
        }
        var prose = extractProseBlocks(exportHtml, rawMd);

        if (!sections.length && !reportTitle && !prose.length && !(extras.charts || []).length) {
            var plain = extractPlainText(msg) || msg.original_content || '';
            if (plain && String(plain).indexOf('<') !== -1) {
                plain = htmlToPlainExportText(plain);
            }
            if (!plain && msg.content && String(msg.content).indexOf('<') === -1) {
                plain = msg.content;
            }
            if (plain && typeof ChatbooSse !== 'undefined' && ChatbooSse.normalizeGluedMarkdown) {
                plain = ChatbooSse.normalizeGluedMarkdown(plain);
            }
            prose = markdownToProseBlocks(plain || '');
            if (prose.length) {
                generateReportPDF(jsPDF, {
                    title: reportTitle,
                    sections: sections,
                    prose: prose,
                    charts: extras.charts || [],
                    landscape: extras.landscape,
                }, msgIndex, ctx);
                return;
            }
            if (!plain) {
                if (ctx.notification) {
                    ctx.notification({ message: _t('Nothing to export'), type: 'warning', sticky: false });
                }
                return;
            }
            var fallbackDoc = new jsPDF({ orientation: 'portrait', unit: 'mm', format: 'a4' });
            generateTextPDF(fallbackDoc, plain, msgIndex, ctx);
            return;
        }

        generateReportPDF(jsPDF, {
            title: reportTitle,
            sections: sections,
            prose: prose,
            charts: extras.charts || [],
            landscape: extras.landscape,
            statsAoa: extras.statsAoa || [],
        }, msgIndex, ctx);
    }

    function downloadAsPDF(ev, ctx) {
        var msgIndex = parseInt(ev.target.getAttribute('data-msg-index'));
        if (isNaN(msgIndex) || msgIndex < 0 || msgIndex >= ctx.messages.length) return;

        var msg = ctx.messages[msgIndex];
        if (!msg || msg.role !== 'assistant') return;

        try {
            if (!jspdfCtor()) {
                if (ctx.notification) {
                    ctx.notification({ message: _t('Error: jsPDF is not available'), type: 'danger', sticky: false });
                }
                return;
            }

            var sourceEl = resolveBubbleContentNode(ev);
            var exportHtml = cardHtmlForExport(msg, sourceEl);
            var sections = resolveExportSections(exportHtml, msg.clip_data, { images: true });
            enrichSectionsImagesFromDom(sections, sourceEl);
            var charts = resolveExportCharts(msg, sourceEl);
            var extras = {
                sections: sections,
                charts: charts,
                prose: exportProseFromMessage(msg, exportHtml),
                statsAoa: resolveExportStatsAoa(msg.clip_data, sourceEl, charts),
                title: extractReportTitle(exportHtml) || clipDataTitle(msg.clip_data),
                landscape: clipLandscapeFlag(msg.clip_data),
            };
            if (sections.length || charts.length || (extras.prose && extras.prose.length)) {
                resolveSectionImages(sections).then(function () {
                    var built = buildDocument('pdf', {
                        title: extras.title,
                        sections: extras.sections,
                        prose: extras.prose,
                        charts: extras.charts,
                        landscape: extras.landscape,
                        statsAoa: extras.statsAoa || [],
                        filename: generateFilename(msgIndex, 'pdf', ctx),
                        msgIndex: msgIndex,
                        ctx: ctx,
                    });
                    if (built && built.blob) {
                        triggerBlobDownload(built.blob, built.filename || extras.title || 'export.pdf');
                        if (ctx.notification) {
                            ctx.notification({
                                message: 'PDF descargado: ' + (built.filename || 'export.pdf'),
                                type: 'success',
                                sticky: false,
                            });
                        }
                        return;
                    }
                    downloadAsPDFLegacy(msg, msgIndex, ctx, extras);
                });
                return;
            }
            generateWysiwygPDF(ev, msg, msgIndex, ctx).then(function (ok) {
                if (!ok) {
                    downloadAsPDFLegacy(msg, msgIndex, ctx, extras);
                }
            });
        } catch (error) {
            console.error('Error generating PDF:', error);
            if (ctx.notification) {
                ctx.notification({ message: _t('Error while generating PDF'), type: 'danger', sticky: false });
            }
        }
    }

    /**
     * Infer right-aligned columns (numbers / times) from body sample.
     *
     * @param {Array} aoa
     * @returns {Object} columnStyles for AutoTable
     */
    function inferNumericColumnStyles(aoa) {
        var styles = {};
        if (!aoa || aoa.length < 2) {
            return styles;
        }
        var colCount = aoa[0].length;
        var sample = aoa.slice(1, Math.min(aoa.length, 12));
        var numRe = /^-?\d{1,3}([.,]\d{3})*([.,]\d+)?$|^-?\d+([.,]\d+)?$|^\d{1,2}:\d{2}(:\d{2})?$|^—$|^-$/;
        for (var c = 0; c < colCount; c++) {
            var hits = 0;
            var seen = 0;
            for (var r = 0; r < sample.length; r++) {
                var cell = sample[r][c];
                if (pdfCellImg(cell)) {
                    continue;
                }
                var cellText = pdfCellText(cell).trim();
                if (!cellText) {
                    continue;
                }
                seen += 1;
                if (numRe.test(cellText)) {
                    hits += 1;
                }
            }
            if (seen && hits / seen >= 0.7) {
                styles[c] = { halign: 'right' };
            }
        }
        return styles;
    }

    function drawPdfGroupTitle(doc, label, y, margin, pageHeight) {
        if (y > pageHeight - 36) {
            doc.addPage();
            y = margin;
        } else {
            y += 8;
        }
        doc.setFont('helvetica', 'bold');
        doc.setFontSize(12);
        doc.setTextColor(26, 26, 26);
        return pdfDrawRichLine(doc, label, margin, y, { lineHeight: 7 });
    }

    function drawPdfStats(doc, aoa, y, margin, contentWidth, pageHeight) {
        if (!aoa || aoa.length < 2 || typeof doc.autoTable !== 'function') {
            return y;
        }
        doc.autoTable({
            startY: y,
            head: [aoa[0]],
            body: aoa.slice(1),
            theme: 'grid',
            styles: {
                font: 'helvetica',
                fontSize: 8,
                cellPadding: 1.2,
                overflow: 'linebreak',
                lineColor: [200, 200, 200],
                lineWidth: 0.1,
                textColor: [40, 40, 40],
            },
            headStyles: {
                fillColor: [236, 239, 241],
                textColor: [26, 26, 26],
                fontStyle: 'bold',
            },
            margin: { left: margin, right: margin },
            tableWidth: contentWidth,
        });
        return (doc.lastAutoTable && doc.lastAutoTable.finalY || y) + 10;
    }

    function drawPdfCharts(doc, charts, y, margin, contentWidth, pageHeight, landscape) {
        var pending = (charts || []).filter(function (chart) {
            return chart && chart.dataUrl;
        });
        if (!pending.length) {
            return y;
        }
        pending.forEach(function (chart) {
            var maxH = chart.figure
                ? Math.min(landscape ? 70 : 55, contentWidth)
                : Math.min(landscape ? 118 : 92, contentWidth * 0.48);
            var imgW = contentWidth;
            var imgH = maxH;
            if (chart.figure && chart.width && chart.height) {
                var ratio = chart.height / chart.width;
                imgW = Math.min(contentWidth, Math.max(28, contentWidth * 0.42));
                imgH = imgW * ratio;
                if (imgH > maxH) {
                    imgH = maxH;
                    imgW = imgH / ratio;
                }
            }
            if (y + imgH > pageHeight - 16) {
                doc.addPage();
                y = margin;
            }
            try {
                doc.addImage(chart.dataUrl, 'PNG', margin, y, imgW, imgH);
                y += imgH + 10;
            } catch (e) { /* tainted or bad png */ }
        });
        return y;
    }

    /**
     * Multi-section A4 report (Chatboo tokens, row-aware pages, painted charts).
     *
     * @param {Function} jsPDF
     * @param {{title: string, sections: Array, prose: Array, charts: Array, landscape: boolean|null}} report
     * @param {number} msgIndex
     * @param {ExportContext} ctx
     */
    function generateReportPDF(jsPDF, report, msgIndex, ctx, opts) {
        opts = opts || {};
        var landscape = pdfShouldBeLandscape(report.sections, report.landscape);
        var doc = new jsPDF({
            orientation: landscape ? 'landscape' : 'portrait',
            unit: 'mm',
            format: 'a4',
        });

        if (typeof doc.autoTable !== 'function') {
            var md = (report.title ? report.title + '\n\n' : '') +
                (report.sections || []).map(function (s) {
                    return (s.title ? '## ' + s.title + '\n' : '') +
                        (s.aoa || []).map(function (row) {
                            return row.map(pdfCellText).join(' | ');
                        }).join('\n');
                }).join('\n\n') +
                ((report.prose || []).length ? '\n\n' + report.prose.map(function (b) {
                    return typeof b === 'string' ? b : (b.text || '');
                }).join('\n') : '');
            if (opts.returnBlob) {
                return doc.output('blob');
            }
            generateTextPDF(doc, md, msgIndex, ctx);
            return;
        }

        var margin = 14;
        var pageWidth = doc.internal.pageSize.getWidth();
        var pageHeight = doc.internal.pageSize.getHeight();
        var y = margin;
        var contentWidth = pageWidth - 2 * margin;
        var chartsBefore = [];
        var chartsAfter = [];
        (report.charts || []).forEach(function (chart) {
            if (!chart) {
                return;
            }
            if (chart.before) {
                chartsBefore.push(chart);
            } else {
                chartsAfter.push(chart);
            }
        });

        if (report.title) {
            doc.setFont('helvetica', 'bold');
            doc.setFontSize(16);
            doc.setTextColor(26, 26, 26);
            y = pdfDrawRichLine(doc, report.title, margin, y, {
                maxWidth: contentWidth,
                lineHeight: 6.5,
            });
            y += 2;
        }

        doc.setFont('helvetica', 'normal');
        doc.setFontSize(8);
        doc.setTextColor(110, 110, 110);
        var exportedAt = new Date().toLocaleString();
        doc.text(exportedAt, margin, y);
        y += 7;
        doc.setTextColor(26, 26, 26);

        y = drawPdfCharts(doc, chartsBefore, y, margin, contentWidth, pageHeight, landscape);
        y = drawProseBlocks(doc, report.prose || [], y, margin, contentWidth, pageHeight);
        var statsPlaced = false;
        if (chartsBefore.length || !(report.charts || []).length) {
            y = drawPdfStats(doc, report.statsAoa, y, margin, contentWidth, pageHeight);
            statsPlaced = true;
        }

        (report.sections || []).forEach(function (section, index) {
            var aoa = section.aoa || [];
            if (!aoa.length) {
                return;
            }
            if (y > pageHeight - 36) {
                doc.addPage();
                y = margin;
            }
            var caption = sectionCaption(section);
            if (caption) {
                y = drawPdfGroupTitle(doc, caption, y, margin, pageHeight);
            }

            var hasImg = false;
            var hasGlyph = false;
            var head = [aoa[0].map(function (cell) {
                var preparedHead = pdfPrepareCell(cell);
                if (preparedHead && preparedHead._pdfGlyphs && preparedHead._pdfGlyphs.length) {
                    hasGlyph = true;
                }
                return preparedHead;
            })];
            var body = aoa.slice(1).map(function (row) {
                return row.map(function (cell) {
                    var img = pdfCellImg(cell);
                    if (img) {
                        hasImg = true;
                        return { content: '', _pdfImg: img };
                    }
                    var prepared = pdfPrepareCell(cell);
                    if (prepared && prepared._pdfGlyphs && prepared._pdfGlyphs.length) {
                        hasGlyph = true;
                    }
                    return prepared;
                });
            });

            doc.autoTable({
                startY: y,
                head: head,
                body: body,
                theme: 'grid',
                styles: {
                    font: 'helvetica',
                    fontSize: 8,
                    cellPadding: 1.4,
                    overflow: 'linebreak',
                    lineColor: [200, 200, 200],
                    lineWidth: 0.1,
                    textColor: [40, 40, 40],
                    valign: 'middle',
                    minCellHeight: hasImg ? 16 : (hasGlyph ? 6 : 0),
                },
                headStyles: {
                    fillColor: [236, 239, 241],
                    textColor: [26, 26, 26],
                    fontStyle: 'bold',
                    lineColor: [180, 180, 180],
                },
                alternateRowStyles: {
                    fillColor: [248, 249, 250],
                },
                columnStyles: inferNumericColumnStyles(aoa),
                margin: { left: margin, right: margin },
                tableWidth: 'auto',
                rowPageBreak: 'avoid',
                didParseCell: function (data) {
                    var raw = data.cell && data.cell.raw;
                    var glyphs = raw && raw._pdfGlyphs;
                    if (!glyphs || !glyphs.length || raw._pdfImg) {
                        return;
                    }
                    var extra = glyphs.length * 4.6 + 0.6;
                    var pad = data.cell.styles.cellPadding;
                    var num = typeof pad === 'number';
                    data.cell.styles.cellPadding = {
                        top: num ? pad : (pad && pad.top != null ? pad.top : 1.4),
                        right: num ? pad : (pad && pad.right != null ? pad.right : 1.4),
                        bottom: num ? pad : (pad && pad.bottom != null ? pad.bottom : 1.4),
                        left: (num ? pad : (pad && pad.left != null ? pad.left : 1.4)) + extra,
                    };
                },
                didDrawCell: function (data) {
                    var raw = data.cell && data.cell.raw;
                    if (!raw) {
                        return;
                    }
                    var img = raw._pdfImg;
                    if (img && data.section !== 'head') {
                        try {
                            var pad = 0.8;
                            var dim = Math.min(
                                data.cell.height - pad * 2,
                                data.cell.width - pad * 2,
                                14
                            );
                            if (dim < 4) {
                                return;
                            }
                            doc.addImage(
                                img, 'PNG',
                                data.cell.x + pad,
                                data.cell.y + pad,
                                dim, dim
                            );
                        } catch (e) { /* skip broken thumb */ }
                        return;
                    }
                    var glyphs = raw._pdfGlyphs;
                    if (!glyphs || !glyphs.length) {
                        return;
                    }
                    var gpad = 0.8;
                    var gdim = Math.min(data.cell.height - gpad * 2, 4.2);
                    if (gdim < 2.4) {
                        return;
                    }
                    var gx = data.cell.x + gpad;
                    var gy = data.cell.y + (data.cell.height - gdim) / 2;
                    var gi;
                    for (gi = 0; gi < glyphs.length; gi++) {
                        try {
                            doc.addImage(glyphs[gi], 'PNG', gx, gy, gdim, gdim);
                        } catch (e) { /* skip */ }
                        gx += gdim + 0.4;
                    }
                },
            });
            y = (doc.lastAutoTable && doc.lastAutoTable.finalY ? doc.lastAutoTable.finalY : y) + 12;
            if (index < report.sections.length - 1 && y > pageHeight - 30) {
                doc.addPage();
                y = margin;
            }
        });

        y = drawPdfCharts(doc, chartsAfter, y, margin, contentWidth, pageHeight, landscape);
        if (!statsPlaced) {
            y = drawPdfStats(doc, report.statsAoa, y, margin, contentWidth, pageHeight);
        }

        var pageCount = doc.internal.getNumberOfPages();
        for (var p = 1; p <= pageCount; p++) {
            doc.setPage(p);
            doc.setFont('helvetica', 'normal');
            doc.setFontSize(8);
            doc.setTextColor(130, 130, 130);
            doc.text(
                String(p) + ' / ' + pageCount,
                pageWidth / 2,
                pageHeight - 8,
                { align: 'center' }
            );
        }

        if (opts.returnBlob) {
            return doc.output('blob');
        }
        var filename = generateFilename(msgIndex, 'pdf', ctx);
        doc.save(filename);
        if (ctx.notification) {
            ctx.notification({ message: 'PDF descargado: ' + filename, type: 'success', sticky: false });
        }
    }

    /**
     * Fallback: Generate a text-based PDF from Markdown / plain text.
     *
     * @param {Object} doc - jsPDF document instance
     * @param {string} markdown - Markdown / plain source
     * @param {number} msgIndex - Message index (for filename)
     * @param {ExportContext} ctx - Component context
     */
    function generateTextPDF(doc, markdown, msgIndex, ctx) {
        var segments = markdownToPDFSegments(markdown);
        var maxWidth = 180;
        var y = 20;
        var lineHeight = 7;
        var pageHeight = 280;

        segments.forEach(function (seg) {
            if (seg.mono) {
                doc.setFont('courier', 'normal');
                doc.setFontSize(9);
            } else {
                doc.setFont('helvetica', 'normal');
                doc.setFontSize(10);
            }
            y = pdfDrawRichLine(doc, seg.text, 10, y, {
                maxWidth: maxWidth,
                lineHeight: lineHeight,
                breakAt: pageHeight,
                margin: 20,
            });
        });

        var filename = generateFilename(msgIndex, 'pdf', ctx);
        doc.save(filename);

        if (ctx.notification) {
            ctx.notification({ message: 'PDF descargado: ' + filename, type: 'success', sticky: false });
        }
    }

    /**
     * HTML visible en el chat (misma fuente que Chart.js / burbuja).
     *
     * @param {Object} msg
     * @returns {string}
     */
    function resolveExportHtml(msg) {
        if (!msg) return '';
        if (msg.formatted_html) return msg.formatted_html;
        if (msg.content && String(msg.content).indexOf('<') !== -1) return msg.content;
        return '';
    }

    function cardHtmlForExport(msg, sourceEl) {
        if (sourceEl) {
            var host = sanitizeWordClone(sourceEl, '');
            if (host && host.innerHTML) {
                return host.innerHTML;
            }
        }
        return resolveExportHtml(msg);
    }

    function exportProseFromMessage(msg, exportHtml) {
        var rawMd = (msg && msg.original_content) || '';
        if (!rawMd && msg && msg.content && String(msg.content).indexOf('<') === -1) {
            rawMd = msg.content;
        }
        if (typeof ChatbooSse !== 'undefined' && ChatbooSse.normalizeGluedMarkdown && rawMd) {
            rawMd = ChatbooSse.normalizeGluedMarkdown(rawMd);
        }
        return extractProseBlocks(exportHtml || '', rawMd);
    }

    function proseBlocksToHtml(blocks) {
        var html = '';
        (blocks || []).forEach(function (b) {
            if (!b || !b.text) {
                return;
            }
            var t = escapeWordText(b.text);
            var type = b.type || 'p';
            if (type === 'h1') {
                html += '<h1>' + t + '</h1>';
            } else if (type === 'h2') {
                html += '<h2>' + t + '</h2>';
            } else if (type === 'h3' || type === 'h4') {
                html += '<h3>' + t + '</h3>';
            } else if (type === 'li') {
                html += '<p>• ' + t + '</p>';
            } else {
                html += '<p>' + t + '</p>';
            }
        });
        return html;
    }

    /**
     * Plain text from chat HTML (strips chart toolbars / noexport).
     *
     * @param {string} html
     * @returns {string}
     */
    function htmlToPlainExportText(html) {
        if (!html) return '';
        var tempDiv = document.createElement('div');
        tempDiv.innerHTML = String(html).replace(/<br\s*\/?>/gi, '\n');
        var skip = tempDiv.querySelectorAll('.o_chatboo_noexport');
        for (var i = 0; i < skip.length; i++) {
            if (skip[i].parentNode) {
                skip[i].parentNode.removeChild(skip[i]);
            }
        }
        return (tempDiv.textContent || tempDiv.innerText || '').replace(/\n{3,}/g, '\n\n').trim();
    }

    function excelSheetName(title, index, used) {
        var base = String(title || ('Datos ' + (index + 1)))
            .replace(/[\\\/\?\*\[\]]/g, ' ')
            .replace(/\s+/g, ' ')
            .trim()
            .substring(0, 31);
        if (!base) {
            base = 'Datos ' + (index + 1);
        }
        var name = base;
        var n = 1;
        while (used[name]) {
            var suffix = '_' + n;
            name = (base.substring(0, Math.max(1, 31 - suffix.length)) + suffix).substring(0, 31);
            n += 1;
        }
        used[name] = true;
        return name;
    }

    function datasetRowsToAoa(rows, opts) {
        var withImages = !!(opts && opts.images);
        if (!Array.isArray(rows) || !rows.length) {
            return [];
        }
        if (typeof rows[0] !== 'object' || rows[0] === null) {
            return [['Valor']].concat(rows.map(function (v) { return [v]; }));
        }
        var keys = [];
        var seen = {};
        rows.forEach(function (row) {
            if (!row || typeof row !== 'object') {
                return;
            }
            Object.keys(row).forEach(function (key) {
                if (key.charAt(0) === '_' || key === '__model') {
                    return;
                }
                if (!seen[key]) {
                    seen[key] = true;
                    keys.push(key);
                }
            });
        });
        if (!keys.length) {
            return [];
        }
        var aoa = [keys];
        rows.forEach(function (row) {
            aoa.push(keys.map(function (key) {
                var value = row ? row[key] : '';
                if (value && typeof value === 'object') {
                    return JSON.stringify(value);
                }
                if (value === undefined || value === null) {
                    return '';
                }
                if (withImages && cellLooksLikeImage(String(value))) {
                    var src = String(value);
                    if (src.indexOf('data:') === 0) {
                        return { content: '', _pdfImg: src };
                    }
                    return { content: '', _imgSrc: src };
                }
                return value;
            }));
        });
        return aoa;
    }

    function htmlTableToAoa(table, opts) {
        var aoa = [];
        var withImages = !!(opts && opts.images);
        if (!table) {
            return aoa;
        }
        var rows = table.querySelectorAll('tr');
        rows.forEach(function (row) {
            if (row.classList && row.classList.contains('o_chatboo_ficha_title')) {
                return;
            }
            var cells = Array.from(row.querySelectorAll('th, td')).filter(function (cell) {
                return !(cell.classList && cell.classList.contains('o_chatboo_noexport'));
            }).map(function (cell) {
                if (withImages) {
                    var img = cell.querySelector && cell.querySelector('img');
                    if (img) {
                        var src = img.currentSrc || img.src || img.getAttribute('src') || '';
                        var dataUrl = imgElementToDataUrl(img);
                        if (dataUrl || cellLooksLikeImage(src)) {
                            return { content: '', _pdfImg: dataUrl, _imgSrc: src };
                        }
                    }
                    var text = (cell.textContent || cell.innerText || '').trim();
                    if (cellLooksLikeImage(text)) {
                        return { content: '', _imgSrc: text };
                    }
                    return text;
                }
                return (cell.textContent || cell.innerText || '').trim();
            });
            if (cells.length > 0) {
                aoa.push(cells);
            }
        });
        return aoa;
    }

    function precedingHeadingText(el) {
        var prev = el ? el.previousElementSibling : null;
        while (prev) {
            if (/^H[1-6]$/i.test(prev.tagName)) {
                return (prev.textContent || '').trim();
            }
            if (prev.classList && prev.classList.contains('o_chatboo_table_block')) {
                break;
            }
            if (prev.querySelector && prev.querySelector('table')) {
                break;
            }
            prev = prev.previousElementSibling;
        }
        return '';
    }

    /**
     * Section title from ficha thead row (preferred over preceding h3).
     *
     * @param {Element} el - table block or table
     * @returns {string}
     */
    function fichaTitleFromEl(el) {
        if (!el || !el.querySelector) {
            return '';
        }
        var tr = el.querySelector('tr.o_chatboo_ficha_title');
        if (!tr) {
            return '';
        }
        return (tr.textContent || tr.innerText || '').replace(/\s+/g, ' ').trim();
    }

    function blockTitleFromEl(el) {
        var titled = fichaTitleFromEl(el);
        if (titled) {
            return titled;
        }
        if (el && el.querySelector) {
            var h = el.querySelector('.o_chatboo_block_title');
            if (h) {
                return (h.textContent || h.innerText || '').replace(/\s+/g, ' ').trim();
            }
        }
        return precedingHeadingText(el);
    }

    function sectionCaption(section) {
        return section && section.title ? String(section.title).trim() : '';
    }

    /**
     * Global report title from rendered HTML.
     *
     * @param {string} html
     * @returns {string}
     */
    function extractReportTitle(html) {
        if (!html) {
            return '';
        }
        var root = document.createElement('div');
        root.innerHTML = html;
        var h = root.querySelector(
            'h1.o_chatboo_prose_h, .o_chatboo_prose_host h1, h1'
        );
        return h ? (h.textContent || '').replace(/\s+/g, ' ').trim() : '';
    }

    /**
     * Strip markdown tables / code fences so narrative parse stays clean.
     *
     * @param {string} markdown
     * @returns {string}
     */
    function stripMarkdownTables(markdown) {
        if (!markdown) {
            return '';
        }
        var lines = String(markdown).split('\n');
        var out = [];
        var inCode = false;
        var inTable = false;
        lines.forEach(function (line) {
            if (line.trim().indexOf('```') === 0) {
                inCode = !inCode;
                return;
            }
            if (inCode) {
                return;
            }
            if (line.indexOf('|') !== -1 && /^\s*\|/.test(line)) {
                inTable = true;
                return;
            }
            if (inTable) {
                if (!line.trim()) {
                    inTable = false;
                }
                return;
            }
            out.push(line);
        });
        return out.join('\n');
    }

    /**
     * Inline markdown cleanup for PDF prose (bold/italic/code → plain).
     *
     * @param {string} text
     * @returns {string}
     */
    function stripInlineMarkdown(text) {
        return String(text || '')
            .replace(/\*\*(.*?)\*\*/g, '$1')
            .replace(/__(.*?)__/g, '$1')
            .replace(/\*(.*?)\*/g, '$1')
            .replace(/_(.*?)_/g, '$1')
            .replace(/`(.*?)`/g, '$1')
            .replace(/\s+/g, ' ')
            .trim();
    }

    /**
     * Parse Markdown narrative into typed prose blocks (no tables).
     *
     * @param {string} markdown
     * @returns {Array<{type: string, text: string}>}
     */
    function markdownToProseBlocks(markdown) {
        var text = stripMarkdownTables(markdown);
        if (typeof ChatbooSse !== 'undefined' && ChatbooSse.normalizeGluedMarkdown) {
            text = ChatbooSse.normalizeGluedMarkdown(text);
        }
        if (!text.trim()) {
            return [];
        }
        if (typeof showdown !== 'undefined') {
            try {
                var converter = new showdown.Converter({
                    tables: false,
                    strikethrough: true,
                    simplifiedAutoLink: true,
                    ghCompatibleHeaderId: true,
                });
                return normalizeProseBlocks(htmlFragmentToProseBlocks(converter.makeHtml(text)));
            } catch (e) {
                console.warn('Showdown prose parse failed, using line parser:', e);
            }
        }
        var blocks = [];
        var para = [];
        var flushPara = function () {
            if (!para.length) {
                return;
            }
            var joined = stripInlineMarkdown(para.join(' '));
            if (joined) {
                blocks.push({ type: 'p', text: joined });
            }
            para = [];
        };
        text.split('\n').forEach(function (line) {
            var trimmed = line.trim();
            if (!trimmed) {
                flushPara();
                return;
            }
            if (/^#{1,6}$/.test(trimmed)) {
                return;
            }
            var hm = trimmed.match(/^(#{1,6})\s+(.+)$/);
            if (hm) {
                flushPara();
                blocks.push({ type: 'h' + hm[1].length, text: stripInlineMarkdown(hm[2]) });
                return;
            }
            if (/^[-*•]\s+/.test(trimmed)) {
                flushPara();
                blocks.push({ type: 'li', text: stripInlineMarkdown(trimmed.replace(/^[-*•]\s+/, '')) });
                return;
            }
            if (/^\d+\.\s+/.test(trimmed)) {
                flushPara();
                blocks.push({ type: 'li', text: stripInlineMarkdown(trimmed) });
                return;
            }
            para.push(trimmed);
        });
        flushPara();
        return normalizeProseBlocks(blocks);
    }

    /**
     * Walk an HTML fragment into typed prose blocks.
     *
     * @param {string} html
     * @returns {Array<{type: string, text: string}>}
     */
    function htmlFragmentToProseBlocks(html) {
        var blocks = [];
        if (!html) {
            return blocks;
        }
        var root = document.createElement('div');
        root.innerHTML = html;
        var skip = root.querySelectorAll(
            '.o_chatboo_table_block, .o_chatboo_noexport, table, h3.o_chatboo_result_title, h3.pns-result-title, .pns-result-title'
        );
        for (var i = 0; i < skip.length; i++) {
            if (skip[i].parentNode) {
                skip[i].parentNode.removeChild(skip[i]);
            }
        }

        var pushText = function (type, el) {
            var t = stripInlineMarkdown((el.textContent || el.innerText || '').replace(/\s+/g, ' '));
            if (t) {
                blocks.push({ type: type, text: t });
            }
        };

        var walk = function (node) {
            if (!node) {
                return;
            }
            if (node.nodeType === Node.TEXT_NODE) {
                var raw = (node.textContent || '').replace(/\s+/g, ' ').trim();
                if (raw) {
                    blocks.push({ type: 'p', text: stripInlineMarkdown(raw) });
                }
                return;
            }
            if (node.nodeType !== Node.ELEMENT_NODE) {
                return;
            }
            var tag = node.tagName.toLowerCase();
            if (tag === 'script' || tag === 'style') {
                return;
            }
            if (node.classList && (
                node.classList.contains('o_chatboo_table_block') ||
                node.classList.contains('o_chatboo_noexport')
            )) {
                return;
            }
            if (tag === 'table' || tag === 'img') {
                return;
            }
            if (/^h[1-6]$/.test(tag)) {
                pushText(tag, node);
                return;
            }
            if (tag === 'li') {
                pushText('li', node);
                return;
            }
            if (tag === 'p' || tag === 'blockquote') {
                var isMeta = (node.classList && (
                    node.classList.contains('text-muted') ||
                    node.classList.contains('pns-result-footer') ||
                    node.classList.contains('small')
                )) || (tag === 'p' && /^Total:\s*\d+/i.test((node.textContent || '').trim()));
                pushText(isMeta ? 'meta' : (tag === 'blockquote' ? 'quote' : 'p'), node);
                return;
            }
            if (tag === 'br') {
                return;
            }
            if (tag === 'ul' || tag === 'ol' || tag === 'div' || tag === 'section' || tag === 'article' ||
                tag === 'span' || tag === 'strong' || tag === 'em' || tag === 'b' || tag === 'i') {
                var children = node.childNodes;
                for (var c = 0; c < children.length; c++) {
                    walk(children[c]);
                }
                return;
            }
            pushText('p', node);
        };

        var kids = root.childNodes;
        for (var k = 0; k < kids.length; k++) {
            walk(kids[k]);
        }
        return blocks;
    }

    /**
     * Split paragraphs that still contain raw Markdown headings.
     *
     * @param {Array<{type: string, text: string}>} blocks
     * @returns {Array<{type: string, text: string}>}
     */
    function normalizeProseBlocks(blocks) {
        var out = [];
        (blocks || []).forEach(function (b) {
            if (!b) {
                return;
            }
            if (typeof b === 'string') {
                b = { type: 'p', text: b };
            }
            var text = stripInlineMarkdown(b.text || '');
            if (!text || /^#{1,6}$/.test(text)) {
                return;
            }
            if (b.type === 'p' && /#{1,6}\s/.test(text)) {
                var parts = text.split(/(?=#{1,6}\s)/);
                parts.forEach(function (part) {
                    var chunk = part.trim();
                    if (!chunk || /^#{1,6}$/.test(chunk)) {
                        return;
                    }
                    var m = chunk.match(/^(#{1,6})\s+(.+)$/);
                    if (m) {
                        out.push({ type: 'h' + Math.min(6, m[1].length), text: stripInlineMarkdown(m[2]) });
                    } else {
                        out.push({ type: 'p', text: stripInlineMarkdown(chunk) });
                    }
                });
                return;
            }
            out.push({ type: b.type || 'p', text: text });
        });
        return out;
    }

    /**
     * Draw typed prose blocks with report typography (left-aligned wrap).
     *
     * @returns {number} next Y
     */
    function drawProseBlocks(doc, blocks, y, margin, contentWidth, pageHeight) {
        if (!blocks || !blocks.length) {
            return y;
        }
        if (y > margin + 2) {
            y += 2;
        }
        blocks.forEach(function (block) {
            if (!block) {
                return;
            }
            if (typeof block === 'string') {
                block = { type: 'p', text: block };
            }
            var text = block.text || '';
            if (!text) {
                return;
            }
            var type = block.type || 'p';
            var fontSize = 9;
            var fontStyle = 'normal';
            var gapAfter = 3.2;
            var indent = 0;
            var color = [40, 40, 40];

            if (type === 'h1') {
                fontSize = 14; fontStyle = 'bold'; gapAfter = 4; color = [26, 26, 26];
            } else if (type === 'h2') {
                fontSize = 12; fontStyle = 'bold'; gapAfter = 3.5; color = [26, 26, 26];
            } else if (type === 'h3' || type === 'h4') {
                fontSize = 10; fontStyle = 'bold'; gapAfter = 3; color = [26, 26, 26];
            } else if (type === 'h5' || type === 'h6') {
                fontSize = 9; fontStyle = 'bold'; gapAfter = 2.5; color = [26, 26, 26];
            } else if (type === 'li') {
                text = '• ' + text;
                indent = 2;
                gapAfter = 2;
            } else if (type === 'quote') {
                indent = 3;
                color = [90, 90, 90];
                fontStyle = 'italic';
            } else if (type === 'meta') {
                fontSize = 8;
                color = [120, 120, 120];
                gapAfter = 4;
            }

            doc.setFont('helvetica', fontStyle);
            doc.setFontSize(fontSize);
            doc.setTextColor(color[0], color[1], color[2]);
            var width = contentWidth - indent;
            var lineH = Math.max(3.8, fontSize * 0.42);
            y = pdfDrawRichLine(doc, text, margin + indent, y, {
                maxWidth: width,
                lineHeight: lineH,
                pageHeight: pageHeight,
                margin: margin,
                align: 'left',
            });
            y += gapAfter;
            doc.setTextColor(26, 26, 26);
        });
        return y;
    }

    /**
     * Non-table prose for the PDF body (structured headings / paragraphs).
     *
     * @param {string} html
     * @param {string} [rawMarkdown]
     * @returns {Array<{type: string, text: string}>}
     */
    function extractProseBlocks(html, rawMarkdown) {
        var fromHtml = normalizeProseBlocks(htmlFragmentToProseBlocks(html || ''));
        var hasRawHashes = fromHtml.some(function (b) {
            return b.type === 'p' && /^#{1,6}\s/.test(b.text);
        });
        var md = rawMarkdown || '';
        if (md && (/^#{1,6}\s/m.test(md) || hasRawHashes || fromHtml.length < 2)) {
            var fromMd = markdownToProseBlocks(md);
            if (fromMd.length && (fromMd.length >= fromHtml.length || hasRawHashes)) {
                return fromMd;
            }
        }
        return fromHtml;
    }

    /**
     * JSON rows stored on the message when the table is not painted
     * (named download). Same shape as data-chatboo-dataset.
     *
     * @param {*} clip
     * @returns {Array<Object>}
     */
    function clipRows(clip) {
        if (!clip) {
            return [];
        }
        if (Array.isArray(clip)) {
            return clip;
        }
        if (typeof clip === 'object' && Array.isArray(clip.rows)) {
            return clip.rows;
        }
        return [];
    }

    function clipDataTitle(clip) {
        if (clip && typeof clip === 'object' && !Array.isArray(clip) && clip.title) {
            return String(clip.title);
        }
        return '';
    }

    function clipDataToSections(clip, opts) {
        var aoa = datasetRowsToAoa(clipRows(clip), opts);
        if (!aoa.length) {
            return [];
        }
        return [{ title: clipDataTitle(clip), aoa: aoa }];
    }

    function aoaToMarkdown(aoa) {
        if (!aoa || !aoa.length) {
            return '';
        }
        var lines = [];
        aoa.forEach(function (row, i) {
            var cells = (row || []).map(function (c) {
                return pdfCellText(c).replace(/\|/g, '\\|');
            });
            lines.push('| ' + cells.join(' | ') + ' |');
            if (i === 0) {
                lines.push('| ' + cells.map(function () { return '---'; }).join(' | ') + ' |');
            }
        });
        return lines.join('\n');
    }

    function clipDataToMarkdown(clip) {
        var sections = clipDataToSections(clip);
        if (!sections.length) {
            return '';
        }
        var parts = [];
        sections.forEach(function (section) {
            if (section.title) {
                parts.push('# ' + section.title);
            }
            parts.push(aoaToMarkdown(section.aoa));
        });
        return parts.join('\n\n');
    }

    function clipDataToTsv(clip) {
        var sections = clipDataToSections(clip);
        if (!sections.length || !sections[0].aoa) {
            return '';
        }
        return sections[0].aoa.map(function (row) {
            return (row || []).map(function (c) {
                return pdfCellText(c);
            }).join('\t');
        }).join('\n');
    }

    function visibleContentHasTable(msg, ev) {
        var html = '';
        if (msg && msg.formatted_html) {
            html = String(msg.formatted_html);
        } else if (msg && msg.content && String(msg.content).indexOf('<') !== -1) {
            html = String(msg.content);
        }
        if (html && /<table[\s>]/i.test(html)) {
            return true;
        }
        var el = ev && resolveBubbleContentNode(ev);
        return !!(el && el.querySelector && el.querySelector('table'));
    }

    /**
     * Table sections from the turn card. clip_data is fallback only
     * when the card has no tables (hidden listing).
     *
     * @param {string} html
     * @param {*} [clipData]
     * @returns {Array<{title: string, aoa: Array}>}
     */
    function extractTableSections(html, clipData, opts) {
        var fromHtml = sectionsFromRenderedHtml(html, opts);
        if (fromHtml.length) {
            return fromHtml;
        }
        return clipDataToSections(clipData, opts);
    }

    function sectionsFromRenderedHtml(html, opts) {
        var sections = [];
        if (!html) {
            return sections;
        }
        var root = document.createElement('div');
        root.innerHTML = html;
        var blocks = root.querySelectorAll('.o_chatboo_table_block[data-chatboo-dataset]');
        if (blocks.length) {
            for (var i = 0; i < blocks.length; i++) {
                var block = blocks[i];
                var aoa = [];
                try {
                    aoa = datasetRowsToAoa(JSON.parse(block.getAttribute('data-chatboo-dataset')), opts);
                } catch (e) {
                    aoa = [];
                }
                if (!aoa.length) {
                    aoa = htmlTableToAoa(block.querySelector('table'), opts);
                }
                if (aoa.length) {
                    sections.push({ title: blockTitleFromEl(block), aoa: aoa });
                }
            }
            return sections;
        }
        var tables = root.querySelectorAll('table');
        for (var t = 0; t < tables.length; t++) {
            var table = tables[t];
            var aoa2 = htmlTableToAoa(table, opts);
            if (!aoa2.length) {
                continue;
            }
            var host = table.closest ? table.closest('.o_chatboo_table_block') : null;
            sections.push({
                title: blockTitleFromEl(host || table),
                aoa: aoa2,
            });
        }
        return sections;
    }

    function sectionsForServer(sections) {
        return (sections || []).map(function (section) {
            return {
                title: section.title || '',
                aoa: (section.aoa || []).map(function (row) {
                    return (row || []).map(function (cell) {
                        if (typeof cell === 'number' && isFinite(cell)) {
                            return cell;
                        }
                        return pdfCellText(cell);
                    });
                }),
            };
        });
    }

    function plainTextToSections(textContent) {
        var worksheetData = [];
        try {
            var jsonData = JSON.parse(textContent);
            if (Array.isArray(jsonData)) {
                if (jsonData.length > 0 && typeof jsonData[0] === 'object') {
                    var keys = Object.keys(jsonData[0]).filter(function (key) {
                        return key.charAt(0) !== '_' && key !== '__model';
                    });
                    worksheetData.push(keys);
                    jsonData.forEach(function (item) {
                        worksheetData.push(keys.map(function (key) {
                            var value = item[key];
                            if (value && typeof value === 'object') return JSON.stringify(value);
                            return value || '';
                        }));
                    });
                } else {
                    worksheetData.push(['Valor']);
                    jsonData.forEach(function (item) { worksheetData.push([item]); });
                }
            } else if (typeof jsonData === 'object' && jsonData) {
                worksheetData.push(['Campo', 'Valor']);
                Object.keys(jsonData).forEach(function (key) {
                    var value = jsonData[key];
                    worksheetData.push([key, value && typeof value === 'object' ? JSON.stringify(value) : value]);
                });
            }
        } catch (e) {
            var lines = String(textContent || '').split('\n').filter(function (l) { return l.trim(); });
            if (lines.length > 0 && lines[0].includes(',')) {
                lines.forEach(function (line) {
                    var cells = [];
                    var currentCell = '';
                    var inQuotes = false;
                    for (var i = 0; i < line.length; i++) {
                        var char = line[i];
                        if (char === '"') { inQuotes = !inQuotes; }
                        else if (char === ',' && !inQuotes) { cells.push(currentCell.trim()); currentCell = ''; }
                        else { currentCell += char; }
                    }
                    cells.push(currentCell.trim());
                    if (cells.length > 0) worksheetData.push(cells);
                });
            } else if (lines.length) {
                worksheetData.push(['Contenido']);
                lines.forEach(function (line) { worksheetData.push([line]); });
            }
        }
        if (!worksheetData.length) {
            var lines2 = String(textContent || '').split('\n').filter(function (l) { return l.trim(); });
            if (!lines2.length) {
                return [];
            }
            worksheetData.push(['Contenido']);
            lines2.forEach(function (line) { worksheetData.push([line]); });
        }
        return [{ title: _STAT_I18N.table, aoa: worksheetData }];
    }

    function base64ToExcelBlob(b64, mime) {
        var bin = atob(b64);
        var u8 = new Uint8Array(bin.length);
        for (var i = 0; i < bin.length; i++) {
            u8[i] = bin.charCodeAt(i);
        }
        return new Blob([u8], {
            type: mime || 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        });
    }

    /**
     * Download message as Excel. Tables come from the card; bytes from the server writer.
     *
     * @param {Event} ev - Click event with data-msg-index
     * @param {ExportContext} ctx - Component context
     */
    function downloadAsExcel(ev, ctx) {
        var msgIndex = parseInt(ev.target.getAttribute('data-msg-index'));
        if (isNaN(msgIndex) || msgIndex < 0 || msgIndex >= ctx.messages.length) return;

        var msg = ctx.messages[msgIndex];
        if (!msg || msg.role !== 'assistant') return;

        try {
            var exportHtml = cardHtmlForExport(msg, resolveBubbleContentNode(ev));
            var sections = extractTableSections(exportHtml, msg.clip_data);
            if (!sections.length) {
                sections = plainTextToSections(extractPlainText(msg));
            }
            if (!sections.length) {
                if (ctx.notification) {
                    ctx.notification({ message: _t('Error while generating Excel'), type: 'danger', sticky: false });
                }
                return;
            }
            var filename = generateFilename(msgIndex, 'xlsx', ctx);
            if (!ctx.rpc) {
                if (ctx.notification) {
                    ctx.notification({ message: _t('Error while generating Excel'), type: 'danger', sticky: false });
                }
                return;
            }
            Promise.resolve(ctx.rpc({
                route: '/chatboo/export/xlsx',
                params: {
                    sections: sectionsForServer(sections),
                    filename: filename,
                },
            })).then(function (res) {
                if (!res || res.status !== 'ok' || !res.datas) {
                    throw new Error((res && res.message) || 'excel');
                }
                triggerBlobDownload(
                    base64ToExcelBlob(res.datas, res.mimetype),
                    res.filename || filename
                );
                if (ctx.notification) {
                    ctx.notification({
                        message: 'Excel descargado: ' + (res.filename || filename),
                        type: 'success',
                        sticky: false,
                    });
                }
            }).catch(function (error) {
                console.error('Error generating Excel:', error);
                if (ctx.notification) {
                    ctx.notification({ message: _t('Error while generating Excel'), type: 'danger', sticky: false });
                }
            });
        } catch (error) {
            console.error('Error generating Excel:', error);
            if (ctx.notification) {
                ctx.notification({ message: _t('Error while generating Excel'), type: 'danger', sticky: false });
            }
        }
    }

    var WORD_STYLE = (
        'body{font-family:Helvetica,Arial,sans-serif;color:#1a1a1a;font-size:11pt;}' +
        'h1{font-size:16pt;color:#1a1a1a;margin:0 0 12pt;}' +
        'h2.o_chatboo_export_h2{font-size:13pt;color:#1a1a1a;margin:0 0 8pt;}' +
        '.o_chatboo_export_group{margin:0 0 20pt;}' +
        'caption{caption-side:top;text-align:left;font-weight:600;padding:0 0 6pt;}' +
        'table{border-collapse:collapse;width:100%;}' +
        'th{background:#eceff1;color:#1a1a1a;font-weight:bold;padding:6px 8px;border:0.5pt solid #c8c8c8;text-align:left;}' +
        'td{padding:5px 8px;border:0.5pt solid #c8c8c8;color:#282828;vertical-align:middle;}' +
        'tr:nth-child(even) td{background:#f8f9fa;}' +
        'td img{max-width:72px;max-height:72px;}' +
        'table.o_chatboo_word_figure,table.o_chatboo_word_figure td,table.o_chatboo_word_figure th{border:none !important;background:transparent;padding:0;}' +
        'table.o_chatboo_word_figure td img{max-width:100%;max-height:none;width:100%;height:auto;}'
    );

    function escapeWordText(s) {
        return String(s || '')
            .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
    }

    function wrapWordHtml(title, body, landscape) {
        var t = escapeWordText(title || '');
        var page = landscape
            ? '@page{size:297mm 210mm;mso-page-orientation:landscape;margin:14mm;}'
            : '@page{size:210mm 297mm;mso-page-orientation:portrait;margin:18mm;}';
        return '<html xmlns:o="urn:schemas-microsoft-com:office:office" '
            + 'xmlns:w="urn:schemas-microsoft-com:office:word">'
            + '<head><meta charset="utf-8"/><title>' + t + '</title>'
            + '<style>' + page + WORD_STYLE + '</style></head><body>' + body + '</body></html>';
    }

    function sanitizeWordClone(sourceEl, fallbackHtml) {
        var host = document.createElement('div');
        if (sourceEl) {
            host.appendChild(sourceEl.cloneNode(true));
        } else {
            host.innerHTML = fallbackHtml || '';
        }
        var kill = host.querySelectorAll(
            '.o_chatboo_chart_toolbar, .o_chatboo_export_bar,'
            + ' .o_chatboo_card_resize, .o_chatboo_card_width_reset,'
            + ' .o_chatboo_copy_btn, .o_chatboo_noexport, .o_chatboo_ts, script,'
            + ' .o_chatboo_chart_host, .o_chatboo_echarts_surface,'
            + ' .echarts-tooltip, div[class*="echarts-tooltip"]'
        );
        for (var i = 0; i < kill.length; i++) {
            if (kill[i].parentNode) {
                kill[i].parentNode.removeChild(kill[i]);
            }
        }
        var imgs = host.querySelectorAll('img');
        for (var n = 0; n < imgs.length; n++) {
            var dataUrl = imgElementToDataUrl(imgs[n]);
            if (dataUrl) {
                imgs[n].setAttribute('src', dataUrl);
            }
        }
        return host;
    }

    function bubbleLooksLikeRichDoc(host) {
        if (!host) {
            return false;
        }
        var clone = host.cloneNode(true);
        var remove = clone.querySelectorAll(
            'table, .o_chatboo_table_block, .o_chatboo_chart_host,'
            + ' .o_chatboo_chart_toolbar, .o_chatboo_echarts_surface,'
            + ' .echarts-tooltip, div[class*="echarts-tooltip"]'
        );
        for (var i = 0; i < remove.length; i++) {
            if (remove[i].parentNode) {
                remove[i].parentNode.removeChild(remove[i]);
            }
        }
        var leftover = (clone.textContent || '').replace(/\s+/g, ' ').trim();
        var hasImg = !!(clone.querySelector && clone.querySelector('img'));
        var hasHeading = !!(clone.querySelector && clone.querySelector('h1,h2,h3,h4'));
        return leftover.length > 80 || hasImg || hasHeading;
    }

    function aoaToWordTable(aoa, caption) {
        if (!aoa || !aoa.length) {
            return '';
        }
        var html = '<table>';
        if (caption) {
            html += '<caption>' + escapeWordText(caption) + '</caption>';
        }
        html += '<thead><tr>';
        (aoa[0] || []).forEach(function (cell) {
            html += '<th>' + escapeWordText(pdfCellText(cell)) + '</th>';
        });
        html += '</tr></thead><tbody>';
        aoa.slice(1).forEach(function (row) {
            html += '<tr>';
            (row || []).forEach(function (cell) {
                var img = pdfCellImg(cell);
                if (img) {
                    html += '<td><img src="' + img + '" alt=""/></td>';
                } else {
                    html += '<td>' + escapeWordText(pdfCellText(cell)) + '</td>';
                }
            });
            html += '</tr>';
        });
        html += '</tbody></table>';
        return html;
    }

    function triggerWordDownload(html, filename) {
        triggerBlobDownload(new Blob(['\ufeff', html], { type: 'application/msword' }), filename);
    }

    function triggerBlobDownload(blob, filename) {
        if (!blob || !filename) {
            return;
        }
        var url = URL.createObjectURL(blob);
        var a = document.createElement('a');
        a.href = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        setTimeout(function () { URL.revokeObjectURL(url); }, 1000);
    }

    function kindFromChip(chip) {
        if (chip && chip.fulfill) {
            return String(chip.fulfill);
        }
        var name = ((chip && chip.name) || '').toLowerCase();
        if (/\.docx?$/.test(name)) {
            return 'doc';
        }
        if (name.slice(-4) === '.pdf') {
            return 'pdf';
        }
        if (/\.html?$/.test(name)) {
            return 'html';
        }
        var mt = ((chip && chip.mimetype) || '').toLowerCase();
        if (mt.indexOf('word') >= 0 || mt === 'application/msword') {
            return 'doc';
        }
        if (mt === 'application/pdf') {
            return 'pdf';
        }
        if (mt.indexOf('html') >= 0) {
            return 'html';
        }
        return '';
    }

    function isPendingFulfillChip(chip) {
        var kind = kindFromChip(chip);
        return !!(chip && chip.pending && (kind === 'doc' || kind === 'pdf' || kind === 'html'));
    }

    function wordFigureWidthPx(landscape) {
        return landscape ? 900 : 624;
    }

    function exportGroupHtml(label, inner) {
        if (!inner) {
            return '';
        }
        return '<div class="o_chatboo_export_group">'
            + '<h2 class="o_chatboo_export_h2">' + escapeWordText(label) + '</h2>'
            + inner + '</div>';
    }

    function chartFiguresHtml(charts, landscape) {
        var fullW = wordFigureWidthPx(landscape);
        var labeled = '';
        var bare = '';
        (charts || []).forEach(function (c) {
            if (!c || !c.dataUrl) {
                return;
            }
            var w = fullW;
            if (c.figure && c.width) {
                w = Math.min(fullW, Math.max(120, c.width));
            }
            var block = '<table class="o_chatboo_word_figure" width="' + w + '"'
                + ' style="width:' + w + 'px;border:none;border-collapse:collapse;">'
                + '<tr><td style="border:none;padding:0;">'
                + '<img src="' + c.dataUrl + '" width="' + w + '" alt=""'
                + ' style="width:' + w + 'px;max-width:' + w + 'px;height:auto;"/>'
                + '</td></tr></table>';
            if (c.figure) {
                bare += block;
            } else {
                labeled += block;
            }
        });
        return bare + labeled;
    }

    function tablesHtmlFromSections(sections) {
        var body = '';
        (sections || []).forEach(function (section) {
            var caption = sectionCaption(section);
            var table = aoaToWordTable(section.aoa);
            body += caption ? exportGroupHtml(caption, table) : table;
        });
        return body;
    }

    function composeHtmlBody(title, sections, charts, richFallback, statsHtml, landscape, proseHtml) {
        var tables = tablesHtmlFromSections(sections);
        var body = (proseHtml || '') + (tables || richFallback || '');
        var chartHtml = chartFiguresHtml(charts, landscape);
        var stats = statsHtml || '';
        if (chartHtml) {
            var before = (charts || []).some(function (c) { return c && c.before; });
            var chartBlock = chartHtml + stats;
            body = before ? (chartBlock + body) : (body + chartBlock);
        } else if (stats) {
            body += stats;
        }
        if (body && body.toLowerCase().indexOf('<h1') === -1 && title) {
            body = '<h1>' + escapeWordText(title) + '</h1>' + body;
        }
        return body;
    }

    function paintOffscreenChartPngs(clip) {
        var rows = clipRows(clip);
        if (!rows.length) {
            return [];
        }
        var api = window.ChatbooCharts;
        if (!api || typeof api.snapshotPng !== 'function') {
            return [];
        }
        var width = clipLandscapeFlag(clip) ? 1000 : 680;
        var host = document.createElement('div');
        host.setAttribute('aria-hidden', 'true');
        host.style.cssText = 'position:absolute;left:-99999px;top:0;width:' + width + 'px;height:420px;overflow:hidden;';
        var block = document.createElement('div');
        block.className = 'o_chatboo_table_block';
        block.setAttribute('data-chatboo-dataset', JSON.stringify(rows));
        block.setAttribute('data-chatboo-show-mode', 'show-chart');
        block.setAttribute('data-chatboo-chart-engine', 'echarts');
        host.appendChild(block);
        document.body.appendChild(host);
        try {
            if (typeof api.hydrate === 'function') {
                api.hydrate(host);
            }
            var png = api.snapshotPng(block);
            return png ? [{ dataUrl: png, before: true }] : [];
        } catch (e) {
            return [];
        } finally {
            try {
                if (typeof api.destroyIn === 'function') {
                    api.destroyIn(host);
                }
            } catch (e2) { /* noop */ }
            if (host.parentNode) {
                host.parentNode.removeChild(host);
            }
        }
    }

    function ensureChartPngs(msg, sourceEl) {
        var painted = collectPaintedChartPngs(sourceEl);
        if (painted && painted.length) {
            return painted;
        }
        return paintOffscreenChartPngs(msg && msg.clip_data);
    }

    function resolveExportSections(exportHtml, clip, opts) {
        if (clipIncludeTable(clip) === false) {
            return [];
        }
        return extractTableSections(exportHtml, clip, opts);
    }

    function resolveExportCharts(msg, sourceEl) {
        var figures = figuresFromHtmlOrEl(sourceEl, resolveExportHtml(msg));
        var flag = clipIncludeChart(msg && msg.clip_data);
        var charts = [];
        if (flag === false) {
            charts = [];
        } else if (flag === true) {
            charts = ensureChartPngs(msg, sourceEl);
        } else {
            charts = collectPaintedChartPngs(sourceEl);
        }
        return (charts || []).concat(figures);
    }

    function rowsFromDatasetEl(el) {
        if (!el || !el.querySelector) {
            return [];
        }
        var block = el.querySelector('.o_chatboo_table_block[data-chatboo-dataset]');
        if (!block) {
            return [];
        }
        try {
            var parsed = JSON.parse(block.getAttribute('data-chatboo-dataset') || '[]');
            return Array.isArray(parsed) ? parsed : [];
        } catch (e) {
            return [];
        }
    }

    function resolveExportRows(clip, sourceEl) {
        var rows = clipRows(clip);
        return rows.length ? rows : rowsFromDatasetEl(sourceEl);
    }

    function metaFromPaintedBlock(sourceEl) {
        if (!sourceEl || !sourceEl.querySelector) {
            return null;
        }
        var block = sourceEl.querySelector('.o_chatboo_table_block');
        return (block && block._chatbooChartMeta) || null;
    }

    function publicRowKeys(rows) {
        var keys = [];
        var seen = {};
        (rows || []).forEach(function (row) {
            Object.keys(row || {}).forEach(function (key) {
                if (seen[key] || key.charAt(0) === '_' || key === 'id') {
                    return;
                }
                seen[key] = 1;
                keys.push(key);
            });
        });
        return keys;
    }

    function coerceExportNumber(val) {
        if (typeof val === 'number' && isFinite(val)) {
            return val;
        }
        if (typeof val === 'boolean' || val === null || val === undefined || val === '') {
            return null;
        }
        var s = String(val).trim().replace(/\s/g, '').replace(/[€$£¥]/g, '');
        if (/[a-zA-ZÀ-ÿ]/.test(s) && !/^-?\d+(\.\d+)?[eE][+-]?\d+$/.test(s)) {
            return null;
        }
        if (/^-?\d{1,3}(\.\d{3})+(,\d+)?$/.test(s)) {
            s = s.replace(/\./g, '').replace(',', '.');
        } else if (/^-?\d{1,3}(,\d{3})+(\.\d+)?$/.test(s)) {
            s = s.replace(/,/g, '');
        } else if (s.indexOf(',') >= 0 && s.indexOf('.') < 0) {
            s = s.replace(',', '.');
        } else {
            s = s.replace(/[^\d.\-eE]/g, '');
        }
        var n = Number(s);
        return isFinite(n) ? n : null;
    }

    function columnLooksNumeric(rows, key) {
        var seen = 0;
        var ok = 0;
        var i;
        for (i = 0; i < rows.length && i < 40; i++) {
            var v = rows[i][key];
            if (v === null || v === undefined || v === '') {
                continue;
            }
            seen += 1;
            if (coerceExportNumber(v) !== null) {
                ok += 1;
            }
        }
        return seen > 0 && ok >= Math.max(1, Math.floor(seen * 0.8));
    }

    function computeSeriesStatsLocal(values) {
        var nums = [];
        var i;
        for (i = 0; i < (values || []).length; i++) {
            if (typeof values[i] === 'number' && isFinite(values[i])) {
                nums.push(values[i]);
            }
        }
        if (!nums.length) {
            return null;
        }
        nums.sort(function (a, b) { return a - b; });
        var n = nums.length;
        var sum = 0;
        for (i = 0; i < n; i++) {
            sum += nums[i];
        }
        var mean = sum / n;
        var mid = Math.floor(n / 2);
        var median = n % 2 ? nums[mid] : (nums[mid - 1] + nums[mid]) / 2;
        var varSum = 0;
        for (i = 0; i < n; i++) {
            varSum += (nums[i] - mean) * (nums[i] - mean);
        }
        return {
            n: n,
            min: nums[0],
            max: nums[n - 1],
            mean: mean,
            median: median,
            stdev: n > 1 ? Math.sqrt(varSum / (n - 1)) : 0,
            sum: sum,
        };
    }

    function formatExportStatNumber(v) {
        if (typeof v !== 'number' || !isFinite(v)) {
            return '';
        }
        if (Math.abs(v - Math.round(v)) < 1e-9 && Math.abs(v) < 1e12) {
            return String(Math.round(v));
        }
        return String(Math.round(v * 100) / 100);
    }

    function statsAoaFromRows(rows) {
        var keys = publicRowKeys(rows).filter(function (key) {
            return columnLooksNumeric(rows, key);
        });
        if (!keys.length) {
            return [];
        }
        var aoa = [[
            '',
            _STAT_I18N.n,
            _STAT_I18N.min,
            _STAT_I18N.max,
            _STAT_I18N.mean,
            _STAT_I18N.median,
            _STAT_I18N.stdev,
            _STAT_I18N.sum,
        ]];
        var metricKeys = ['n', 'min', 'max', 'mean', 'median', 'stdev', 'sum'];
        keys.forEach(function (key) {
            var st = computeSeriesStatsLocal((rows || []).map(function (row) {
                return coerceExportNumber(row[key]);
            }));
            if (!st) {
                return;
            }
            aoa.push([key].concat(metricKeys.map(function (mk) {
                return formatExportStatNumber(st[mk]);
            })));
        });
        return aoa.length >= 2 ? aoa : [];
    }

    function statsAoaToWordHtml(aoa) {
        if (!aoa || aoa.length < 2) {
            return '';
        }
        return '<div class="o_chatboo_series_stats">'
            + aoaToWordTable(aoa, _STAT_I18N.title)
            + '</div>';
    }

    function resolveExportStatsAoa(clip, sourceEl, charts) {
        if (!(charts && charts.length) && clipIncludeChart(clip) === false) {
            return [];
        }
        var api = window.ChatbooCharts;
        var live = metaFromPaintedBlock(sourceEl);
        if (live && api && typeof api.statsAoa === 'function') {
            var fromLive = api.statsAoa(live) || [];
            if (fromLive.length >= 2) {
                return fromLive;
            }
        }
        var rows = resolveExportRows(clip, sourceEl);
        if (api && typeof api.analyzeForStats === 'function' && typeof api.statsAoa === 'function') {
            var meta = api.analyzeForStats(rows);
            var fromPivot = meta ? (api.statsAoa(meta) || []) : [];
            if (fromPivot.length >= 2) {
                return fromPivot;
            }
        }
        if (api && typeof api.analyze === 'function' && typeof api.statsAoa === 'function') {
            var plain = api.analyze(rows);
            var fromPlain = plain ? (api.statsAoa(plain) || []) : [];
            if (fromPlain.length >= 2) {
                return fromPlain;
            }
        }
        return statsAoaFromRows(rows);
    }

    function resolveExportStatsHtml(clip, sourceEl, charts) {
        return statsAoaToWordHtml(resolveExportStatsAoa(clip, sourceEl, charts));
    }

    function buildHtmlDocument(title, sections, charts, richFallback, statsHtml, landscape, proseHtml) {
        var body = composeHtmlBody(title, sections, charts, richFallback, statsHtml, landscape, proseHtml);
        var t = escapeWordText(title || '');
        return '<!DOCTYPE html><html><head><meta charset="utf-8"/><title>' + t + '</title>'
            + '<style>' + WORD_STYLE + '</style></head><body>' + body + '</body></html>';
    }

    function buildDocument(kind, spec) {
        spec = spec || {};
        var title = spec.title || '';
        var sections = spec.sections || [];
        var charts = spec.charts || [];
        var rich = spec.richHtml || '';
        var landscape = spec.landscape;
        var statsHtml = spec.statsHtml || statsAoaToWordHtml(spec.statsAoa);
        var proseHtml = spec.proseHtml || proseBlocksToHtml(spec.prose);
        var hasContent = !!(sections && sections.length) || !!(charts && charts.length) || !!rich || !!statsHtml || !!proseHtml;
        if (kind === 'doc') {
            var wordBody = composeHtmlBody(title, sections, charts, rich, statsHtml, landscape, proseHtml);
            if (!wordBody) {
                return null;
            }
            var wordHtml = wrapWordHtml(title, wordBody, landscape);
            return {
                kind: 'doc',
                filename: spec.filename,
                mimetype: 'application/msword',
                blob: new Blob(['\ufeff', wordHtml], { type: 'application/msword' }),
            };
        }
        if (kind === 'html') {
            if (!hasContent) {
                return null;
            }
            var page = buildHtmlDocument(title, sections, charts, rich, statsHtml, landscape, proseHtml);
            return {
                kind: 'html',
                filename: spec.filename,
                mimetype: 'text/html; charset=utf-8',
                blob: new Blob([page], { type: 'text/html; charset=utf-8' }),
            };
        }
        if (kind === 'pdf') {
            if (!jspdfCtor()) {
                return null;
            }
            var jsPDF = jspdfCtor();
            var blob = generateReportPDF(jsPDF, {
                title: title,
                sections: sections,
                prose: spec.prose || [],
                charts: charts,
                landscape: spec.landscape,
                statsAoa: spec.statsAoa || [],
            }, spec.msgIndex || 0, spec.ctx || {}, { returnBlob: true });
            if (!blob) {
                return null;
            }
            return {
                kind: 'pdf',
                filename: spec.filename,
                mimetype: 'application/pdf',
                blob: blob,
            };
        }
        return null;
    }

    function blobToBase64(blob) {
        return new Promise(function (resolve, reject) {
            var reader = new FileReader();
            reader.onload = function () {
                var s = String(reader.result || '');
                var comma = s.indexOf(',');
                resolve(comma >= 0 ? s.slice(comma + 1) : s);
            };
            reader.onerror = reject;
            reader.readAsDataURL(blob);
        });
    }

    function fulfillPendingSessionDocuments(msg, sourceEl, ctx) {
        if (!msg || !ctx || !ctx.sessionId || typeof ctx.rpc !== 'function') {
            return Promise.resolve();
        }
        var pending = (msg.files || []).filter(isPendingFulfillChip);
        if (!pending.length) {
            return Promise.resolve();
        }
        var exportHtml = cardHtmlForExport(msg, sourceEl);
        var sections = resolveExportSections(exportHtml, msg.clip_data, { images: true });
        enrichSectionsImagesFromDom(sections, sourceEl);
        var charts = resolveExportCharts(msg, sourceEl);
        var title = extractReportTitle(exportHtml) || clipDataTitle(msg.clip_data) || '';
        var prose = exportProseFromMessage(msg, exportHtml);
        var statsAoa = resolveExportStatsAoa(msg.clip_data, sourceEl, charts);
        var statsHtml = statsAoaToWordHtml(statsAoa);
        var chain = Promise.resolve();
        pending.forEach(function (chip) {
            chain = chain.then(function () {
                var kind = kindFromChip(chip);
                var built = buildDocument(kind, {
                    title: title,
                    sections: sections,
                    prose: prose,
                    charts: charts,
                    landscape: clipLandscapeFlag(msg.clip_data),
                    statsHtml: statsHtml,
                    statsAoa: statsAoa,
                    filename: chip.name,
                    ctx: ctx,
                    msgIndex: 0,
                });
                if (!built || !built.blob) {
                    return null;
                }
                return blobToBase64(built.blob).then(function (b64) {
                    return ctx.rpc({
                        route: '/chatboo/sessions/fulfill_export',
                        params: {
                            session_id: ctx.sessionId,
                            filename: chip.name,
                            mimetype: built.mimetype,
                            datas: b64,
                            kind: kind,
                        },
                    });
                }).then(function (res) {
                    if (res && res.status === 'ok' && res.chip) {
                        Object.assign(chip, res.chip);
                        chip.pending = false;
                        if (typeof ctx.onChipFulfilled === 'function') {
                            ctx.onChipFulfilled(msg, chip);
                        }
                    }
                });
            });
        });
        return chain;
    }

    function downloadAsWord(ev, ctx) {
        var msgIndex = parseInt(ev.target.getAttribute('data-msg-index'));
        if (isNaN(msgIndex) || msgIndex < 0 || msgIndex >= ctx.messages.length) return;

        var msg = ctx.messages[msgIndex];
        if (!msg || msg.role !== 'assistant') return;

        try {
            var sourceEl = resolveBubbleContentNode(ev);
            var exportHtml = cardHtmlForExport(msg, sourceEl);
            var host = sanitizeWordClone(sourceEl, exportHtml);
            var charts = resolveExportCharts(msg, sourceEl);
            var title = extractReportTitle(exportHtml) || clipDataTitle(msg.clip_data) || '';
            var sections = resolveExportSections(exportHtml, msg.clip_data, { images: true });
            enrichSectionsImagesFromDom(sections, sourceEl);
            var prose = exportProseFromMessage(msg, exportHtml);
            var rich = '';
            if (!(sections && sections.length) && !(prose && prose.length) && bubbleLooksLikeRichDoc(host)) {
                rich = host.innerHTML;
            }
            if (!(sections && sections.length) && !(prose && prose.length) && !rich && !charts.length) {
                var plain = extractPlainText(msg) || '';
                if (plain) {
                    rich = '<p>' + escapeWordText(plain).replace(/\n/g, '<br/>') + '</p>';
                }
            }
            var filename = generateFilename(msgIndex, 'doc', ctx);
            var built = buildDocument('doc', {
                title: title,
                sections: sections,
                prose: prose,
                charts: charts,
                richHtml: rich,
                landscape: clipLandscapeFlag(msg.clip_data),
                statsHtml: resolveExportStatsHtml(msg.clip_data, sourceEl, charts),
                statsAoa: resolveExportStatsAoa(msg.clip_data, sourceEl, charts),
                filename: filename,
            });
            if (!built) {
                if (ctx.notification) {
                    ctx.notification({ message: _t('Nothing to export'), type: 'warning', sticky: false });
                }
                return;
            }
            triggerBlobDownload(built.blob, filename);
            if (ctx.notification) {
                ctx.notification({
                    message: _t('Download as Word') + ': ' + filename,
                    type: 'success',
                    sticky: false,
                });
            }
        } catch (error) {
            console.error('Error generating Word:', error);
            if (ctx.notification) {
                ctx.notification({ message: _t('Error while generating Word'), type: 'danger', sticky: false });
            }
        }
    }

export {
    htmlToMarkdown,
    tableToMarkdown,
    markdownToPDFText,
    markdownToHTML,
    normalizeFilename,
    extractPlainText,
    generateFilename,
    sessionFileHref,
    sessionFileIsInline,
    doCopy,
    fallbackCopy,
    copyToClipboard,
    downloadAsPDF,
    generateTextPDF,
    generateReportPDF,
    downloadAsExcel,
    downloadAsWord,
    buildDocument,
    ensureChartPngs,
    fulfillPendingSessionDocuments,
};
