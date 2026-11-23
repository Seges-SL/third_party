/** @odoo-module **/
/**
 * Shared LLM usage chip (tokens + display currency).
 *
 * SPDX-License-Identifier: Apache-2.0
 * Copyright (C) 2026 Patanegra Soft <https://patanegra.com>
 */

import { _t } from "@web/core/l10n/translation";

let _displayCtx = null;

export function usageHasTokens(usage) {
    if (!usage || typeof usage !== "object") {
        return false;
    }
    return [
        "prompt_tokens",
        "completion_tokens",
        "total_tokens",
        "input_tokens",
        "output_tokens",
    ].some((key) => Number(usage[key]) > 0);
}

export function addUsage(acc, piece) {
    const out = Object.assign({}, acc || {});
    const src = piece || {};
    ["prompt_tokens", "completion_tokens", "total_tokens", "cached_tokens"].forEach((key) => {
        const n = Number(src[key]) || 0;
        if (n) {
            out[key] = (Number(out[key]) || 0) + n;
        }
    });
    if (src.cost !== undefined && src.cost !== null && src.cost !== "") {
        const n = Number(src.cost);
        if (Number.isFinite(n)) {
            out.cost = (Number(out.cost) || 0) + n;
        }
    }
    return out;
}

export function spendCost(usage) {
    if (!usage || typeof usage !== "object") {
        return null;
    }
    const raw = usage.cost;
    if (raw === undefined || raw === null || raw === "") {
        return null;
    }
    const n = Number(raw);
    return Number.isFinite(n) && n >= 0 ? n : null;
}

export function formatCostLabel(usd, currency, fx) {
    if (usd === undefined || usd === null || usd === "") {
        return { label: "-", title: _t("Cost unknown") };
    }
    const n = Number(usd);
    if (!Number.isFinite(n) || n < 0) {
        return { label: "-", title: _t("Cost unknown") };
    }
    const want = (currency || "USD").toUpperCase();
    let amount = n;
    let code = "USD";
    let rate = 1;
    let failed = false;
    if (want !== "USD") {
        const r = Number(fx && fx.rates ? fx.rates[want] : NaN);
        if (Number.isFinite(r) && r > 0) {
            rate = r;
            amount = n * r;
            code = want;
        } else {
            failed = true;
        }
    }
    const zero = amount === 0;
    let label;
    try {
        label = new Intl.NumberFormat(undefined, {
            style: "currency",
            currency: code,
            minimumFractionDigits: zero || amount >= 0.01 ? 2 : 4,
            maximumFractionDigits: zero ? 2 : (amount >= 0.01 ? 4 : 6),
        }).format(amount);
    } catch (err) {
        label = code + " " + (zero ? amount.toFixed(2) : amount.toFixed(4));
    }
    const asOf = fx && fx.as_of ? fx.as_of : "";
    let title;
    if (failed) {
        label += " ⚠";
        const why = (fx && fx.error) || _t("no exchange rate available");
        title = _t("Could not convert to %s: shown in USD").replace("%s", want)
            + " · " + why;
    } else if (code === "USD") {
        title = "USD" + (asOf ? " · " + asOf : "");
    } else {
        title = code + " · 1 USD = " + rate + (asOf ? " · " + asOf : "");
    }
    return { label, title };
}

export function formatTurnTokensLabel(usage) {
    if (!usageHasTokens(usage)) {
        return "-";
    }
    const total = Number(usage.total_tokens) ||
        ((Number(usage.prompt_tokens) || 0) + (Number(usage.completion_tokens) || 0));
    if (!total) {
        return "-";
    }
    if (total < 1024) {
        return String(total);
    }
    return (total / 1024).toFixed(2) + "k";
}

export function formatUsageChip(usage, options = {}) {
    if (!usageHasTokens(usage) && spendCost(usage) === null) {
        return "";
    }
    const currency = options.currency || "USD";
    const fx = options.fx || null;
    const turnLabel = formatTurnTokensLabel(usage);
    const cost = formatCostLabel(spendCost(usage), currency, fx);
    if (cost.label === "-") {
        return turnLabel === "-" ? "" : turnLabel;
    }
    return turnLabel + " · " + cost.label;
}

export async function loadUsageDisplayContext(orm) {
    if (_displayCtx) {
        return _displayCtx;
    }
    const call = (orm.silent && typeof orm.silent.call === "function")
        ? orm.silent.call.bind(orm.silent)
        : orm.call.bind(orm);
    _displayCtx = await call(
        "ai.execution.engine",
        "get_usage_display_context",
        [],
    );
    return _displayCtx || { display_currency: "USD", fx: { rates: {} } };
}

export async function formatUsageChipWithFx(orm, usage) {
    const ctx = await loadUsageDisplayContext(orm);
    return formatUsageChip(usage, {
        currency: (ctx && ctx.display_currency) || "USD",
        fx: (ctx && ctx.fx) || null,
    });
}

export function findUsageElements(root) {
    const base = root || document;
    return {
        inline: base.querySelector(".o_skill_capture_usage"),
        lastOp: base.querySelector(".o_ai_last_operation_usage"),
    };
}

export function setUsageElements(els, usage, options = {}) {
    const text = formatUsageChip(usage, options);
    const prefix = options.lastOpPrefix || _t("Last operation:");
    if (els && els.inline) {
        if (!text) {
            els.inline.style.display = "none";
            els.inline.textContent = "";
        } else {
            els.inline.textContent = text;
            els.inline.style.display = "";
        }
    }
    if (els && els.lastOp) {
        if (!text) {
            els.lastOp.style.display = "none";
            els.lastOp.textContent = "";
        } else {
            els.lastOp.textContent = prefix + " " + text;
            els.lastOp.style.display = "";
        }
    }
    return text;
}

export async function setUsageElementsWithFx(orm, root, usage, options = {}) {
    const ctx = await loadUsageDisplayContext(orm);
    const els = findUsageElements(root);
    return setUsageElements(els, usage, Object.assign({}, options, {
        currency: (ctx && ctx.display_currency) || "USD",
        fx: (ctx && ctx.fx) || null,
    }));
}
