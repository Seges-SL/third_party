/**
 * Shared LLM usage chip (Odoo 14).
 *
 * SPDX-License-Identifier: Apache-2.0
 * Copyright (C) 2026 Patanegra Soft <https://patanegra.com>
 */
odoo.define('pns_ai_mcp.ai_usage_chip', function (require) {
    "use strict";

    var core = require('web.core');
    var rpc = require('web.rpc');
    var _t = core._t;

    var _displayCtx = null;

    function usageHasTokens(usage) {
        if (!usage || typeof usage !== 'object') {
            return false;
        }
        var keys = [
            'prompt_tokens', 'completion_tokens', 'total_tokens',
            'input_tokens', 'output_tokens',
        ];
        return keys.some(function (key) {
            return Number(usage[key]) > 0;
        });
    }

    function addUsage(acc, piece) {
        var out = Object.assign({}, acc || {});
        var src = piece || {};
        ['prompt_tokens', 'completion_tokens', 'total_tokens', 'cached_tokens'].forEach(function (key) {
            var n = Number(src[key]) || 0;
            if (n) {
                out[key] = (Number(out[key]) || 0) + n;
            }
        });
        if (src.cost !== undefined && src.cost !== null && src.cost !== '') {
            var c = Number(src.cost);
            if (isFinite(c)) {
                out.cost = (Number(out.cost) || 0) + c;
            }
        }
        return out;
    }

    function spendCost(usage) {
        if (!usage || typeof usage !== 'object') {
            return null;
        }
        var raw = usage.cost;
        if (raw === undefined || raw === null || raw === '') {
            return null;
        }
        var n = Number(raw);
        return isFinite(n) && n >= 0 ? n : null;
    }

    function formatCostLabel(usd, currency, fx) {
        if (usd === undefined || usd === null || usd === '') {
            return { label: '-', title: _t('Cost unknown') };
        }
        var n = Number(usd);
        if (!isFinite(n) || n < 0) {
            return { label: '-', title: _t('Cost unknown') };
        }
        var want = (currency || 'USD').toUpperCase();
        var amount = n;
        var code = 'USD';
        var rate = 1;
        var failed = false;
        if (want !== 'USD') {
            var r = Number(fx && fx.rates ? fx.rates[want] : NaN);
            if (isFinite(r) && r > 0) {
                rate = r;
                amount = n * r;
                code = want;
            } else {
                failed = true;
            }
        }
        var zero = amount === 0;
        var label;
        try {
            label = new Intl.NumberFormat(undefined, {
                style: 'currency',
                currency: code,
                minimumFractionDigits: zero || amount >= 0.01 ? 2 : 4,
                maximumFractionDigits: zero ? 2 : (amount >= 0.01 ? 4 : 6),
            }).format(amount);
        } catch (err) {
            label = code + ' ' + (zero ? amount.toFixed(2) : amount.toFixed(4));
        }
        var asOf = fx && fx.as_of ? fx.as_of : '';
        var title;
        if (failed) {
            label += ' ⚠';
            var why = (fx && fx.error) || _t('no exchange rate available');
            title = _t('Could not convert to %s: shown in USD').replace('%s', want)
                + ' · ' + why;
        } else if (code === 'USD') {
            title = 'USD' + (asOf ? ' · ' + asOf : '');
        } else {
            title = code + ' · 1 USD = ' + rate + (asOf ? ' · ' + asOf : '');
        }
        return { label: label, title: title };
    }

    function formatTurnTokensLabel(usage) {
        if (!usageHasTokens(usage)) {
            return '-';
        }
        var total = Number(usage.total_tokens) ||
            ((Number(usage.prompt_tokens) || 0) + (Number(usage.completion_tokens) || 0));
        if (!total) {
            return '-';
        }
        if (total < 1024) {
            return String(total);
        }
        return (total / 1024).toFixed(2) + 'k';
    }

    function formatUsageChip(usage, options) {
        options = options || {};
        if (!usageHasTokens(usage) && spendCost(usage) === null) {
            return '';
        }
        var currency = options.currency || 'USD';
        var fx = options.fx || null;
        var turnLabel = formatTurnTokensLabel(usage);
        var cost = formatCostLabel(spendCost(usage), currency, fx);
        if (cost.label === '-') {
            return turnLabel === '-' ? '' : turnLabel;
        }
        return turnLabel + ' · ' + cost.label;
    }

    function loadUsageDisplayContext() {
        if (_displayCtx) {
            return Promise.resolve(_displayCtx);
        }
        return rpc.query({
            model: 'ai.execution.engine',
            method: 'get_usage_display_context',
            args: [],
        }).then(function (ctx) {
            _displayCtx = ctx || { display_currency: 'USD', fx: { rates: {} } };
            return _displayCtx;
        });
    }

    function formatUsageChipWithFx(usage) {
        return loadUsageDisplayContext().then(function (ctx) {
            return formatUsageChip(usage, {
                currency: (ctx && ctx.display_currency) || 'USD',
                fx: (ctx && ctx.fx) || null,
            });
        });
    }

    function findUsageElements(root) {
        var $root = root ? $(root) : $(document);
        return {
            inline: $root.find('.o_skill_capture_usage'),
            lastOp: $root.find('.o_ai_last_operation_usage'),
        };
    }

    function setUsageElements(els, usage, options) {
        options = options || {};
        var text = formatUsageChip(usage, options);
        var prefix = options.lastOpPrefix || _t('Last operation:');
        if (els && els.inline && els.inline.length) {
            if (!text) {
                els.inline.hide().text('');
            } else {
                els.inline.text(text).show();
            }
        }
        if (els && els.lastOp && els.lastOp.length) {
            if (!text) {
                els.lastOp.hide().text('');
            } else {
                els.lastOp.text(prefix + ' ' + text).show();
            }
        }
        return text;
    }

    function setUsageElementsWithFx(root, usage, options) {
        return loadUsageDisplayContext().then(function (ctx) {
            var els = findUsageElements(root);
            return setUsageElements(els, usage, Object.assign({}, options || {}, {
                currency: (ctx && ctx.display_currency) || 'USD',
                fx: (ctx && ctx.fx) || null,
            }));
        });
    }

    return {
        usageHasTokens: usageHasTokens,
        addUsage: addUsage,
        spendCost: spendCost,
        formatCostLabel: formatCostLabel,
        formatTurnTokensLabel: formatTurnTokensLabel,
        formatUsageChip: formatUsageChip,
        loadUsageDisplayContext: loadUsageDisplayContext,
        formatUsageChipWithFx: formatUsageChipWithFx,
        findUsageElements: findUsageElements,
        setUsageElements: setUsageElements,
        setUsageElementsWithFx: setUsageElementsWithFx,
    };
});
