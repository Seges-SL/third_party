/** @odoo-module **/
/**
 * Activity list chrome (OWL 2): flow-legend bar + spend chip (tokens · money).
 *
 * Legend HTML: ``ai.log.render_flow_legend('grid')`` (same source as form).
 * Spend totals: ``ai.log.get_user_usage_summary`` for the active list domain.
 *
 * SPDX-License-Identifier: Apache-2.0
 * Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
 */
import { ListController } from "@web/views/list/list_controller";
import { pnsPatch } from "@pns_base/js/pns_patch";
import { useService } from "@web/core/utils/hooks";
import { useEffect } from "@odoo/owl";

const MODEL = "ai.log";
const CHIP_TITLE = "Tokens and cost for the current filter";

let _legendHtmlCache = null;
const _refreshSeq = new WeakMap();

function isMcpLogList(component) {
    return (
        component.props?.resModel === MODEL ||
        component.props?.list?.resModel === MODEL
    );
}

function resolveActionScope(component) {
    const start =
        component.el ||
        component.rootRef?.el ||
        component.root?.el;
    if (start) {
        const action = start.closest(".o_action");
        if (action) {
            return action;
        }
    }
    return document.querySelector(".o_action:has(.o_mcp_log_tree)");
}

function controlPanel(scope) {
    if (!scope) {
        return null;
    }
    return (
        scope.querySelector(".o_control_panel") ||
        scope.querySelector(".o_control_panel_main") ||
        document.querySelector(".o_action:has(.o_mcp_log_tree) .o_control_panel")
    );
}

function listDomain(component) {
    const sm = component.env?.searchModel;
    if (sm?.domain) {
        return sm.domain;
    }
    const list = component.props?.list;
    if (list?.domain) {
        return list.domain;
    }
    const root = component.model?.root;
    if (root?.domain) {
        return root.domain;
    }
    return [];
}

async function fetchLegendHtml(orm) {
    if (_legendHtmlCache === null) {
        _legendHtmlCache = await orm.call("ai.log", "render_flow_legend", ["grid"]);
    }
    return _legendHtmlCache;
}

function insertMcpLogLegend(scope, html) {
    if (!scope || !html) {
        return false;
    }
    if (scope.querySelector(".o_mcp_log_legend_bar")) {
        return true;
    }
    const cp = controlPanel(scope);
    if (!cp) {
        return false;
    }
    const wrapper = document.createElement("div");
    wrapper.innerHTML = html;
    const legend = wrapper.firstElementChild;
    if (!legend) {
        return false;
    }
    cp.appendChild(legend);
    return true;
}

function paintUsageChip(scope, summary) {
    const cp = controlPanel(scope);
    if (!cp) {
        return false;
    }
    const chip = cp.querySelector(".o_mcp_log_usage_chip");
    if (!chip) {
        return false;
    }
    if (!summary || !summary.spend_label) {
        chip.textContent = "";
        chip.setAttribute("hidden", "hidden");
        return true;
    }
    chip.textContent = summary.spend_label;
    chip.setAttribute("title", CHIP_TITLE);
    chip.removeAttribute("hidden");
    scope.querySelectorAll(".o_ai_usage_summary_banner").forEach((node) => {
        node.remove();
    });
    return true;
}

async function refreshMcpLogChrome(component, orm) {
    if (!isMcpLogList(component)) {
        return false;
    }
    const seq = (_refreshSeq.get(component) || 0) + 1;
    _refreshSeq.set(component, seq);
    const scope = resolveActionScope(component);
    if (!scope) {
        return false;
    }
    let html;
    try {
        html = await fetchLegendHtml(orm);
    } catch (e) {
        return false;
    }
    if (!insertMcpLogLegend(scope, html)) {
        return false;
    }
    let summary;
    try {
        summary = await orm.call(MODEL, "get_user_usage_summary", [], {
            domain: listDomain(component),
        });
    } catch (e) {
        return false;
    }
    if (_refreshSeq.get(component) !== seq) {
        return false;
    }
    return paintUsageChip(scope, summary);
}

pnsPatch(ListController.prototype, "pns_ai_mcp.mcp_log_legend", {
    setup() {
        super.setup(...arguments);
        const orm = useService("orm");
        useEffect(
            () => {
                if (isMcpLogList(this)) {
                    refreshMcpLogChrome(this, orm);
                }
            },
            () => [isMcpLogList(this) ? JSON.stringify(listDomain(this)) : ""]
        );
    },
});
