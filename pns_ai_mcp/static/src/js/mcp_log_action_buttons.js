/** @odoo-module **/
/**
 * Operations cogMenu item for History (ai.log) list view (Odoo 17+).
 * Opens the tools wizard with Export/Clear operations.
 *
 * SPDX-License-Identifier: Apache-2.0
 * Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
 */
import { registry } from "@web/core/registry";
import { Component, xml } from "@odoo/owl";
import { DropdownItem } from "@web/core/dropdown/dropdown_item";

class LogToolsCogItem extends Component {
    static template = xml`<DropdownItem onSelected.bind="openWizard"><i class="fa fa-cog me-2"></i> <t t-esc="toolsLabel"/></DropdownItem>`;
    static components = { DropdownItem };
    static props = {};

    get toolsLabel() {
        return "Tools";
    }

    openWizard() {
        this.env.services.action.doAction("pns_ai_mcp.action_log_tools_wizard");
    }
}

registry.category("cogMenu").add("mcp_log_tools", {
    Component: LogToolsCogItem,
    groupNumber: 20,
    isDisplayed: (env) => env.config.viewType === "list" && env.searchModel?.resModel === "ai.log",
});
