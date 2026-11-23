/** @odoo-module **/
/**
 * Tools cog-menu item for the Contexts list (Odoo 17+).
 * Opens the Python/XML contexts tools wizard.
 *
 * SPDX-License-Identifier: Apache-2.0
 * Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
 */
import { registry } from "@web/core/registry";
import { Component, xml } from "@odoo/owl";
import { DropdownItem } from "@web/core/dropdown/dropdown_item";
import { _t } from "@web/core/l10n/translation";

class ContextToolsCogItem extends Component {
    static template = xml`<DropdownItem onSelected.bind="openWizard"><i class="fa fa-cog me-2"></i> <t t-esc="toolsLabel"/></DropdownItem>`;
    static components = { DropdownItem };
    static props = {};

    get toolsLabel() {
        return _t("Tools");
    }

    openWizard() {
        this.env.services.action.doAction("pns_ai_mcp.action_mcp_context_tools_wizard");
    }
}

registry.category("cogMenu").add("mcp_context_tools", {
    Component: ContextToolsCogItem,
    groupNumber: 20,
    isDisplayed: (env) => env.config.viewType === "list" && env.searchModel?.resModel === "ai.context",
});
