/** @odoo-module **/
/**
 * Operations cogMenu item for Approvals (safe_operation) list view (Odoo 17+).
 * Opens Approval Tools (refresh expiry + export).
 */
import { registry } from "@web/core/registry";
import { Component, xml } from "@odoo/owl";
import { DropdownItem } from "@web/core/dropdown/dropdown_item";
import { _t } from "@web/core/l10n/translation";

class SafeOperationToolsCogItem extends Component {
    static template = xml`<DropdownItem onSelected.bind="openWizard"><i class="fa fa-cog me-2"></i> <t t-esc="toolsLabel"/></DropdownItem>`;
    static components = { DropdownItem };
    static props = {};

    get toolsLabel() {
        return _t("Tools");
    }

    openWizard() {
        this.env.services.action.doAction("pns_ai_mcp.action_safe_operation_tools_wizard");
    }
}

registry.category("cogMenu").add("safe_operation_tools", {
    Component: SafeOperationToolsCogItem,
    groupNumber: 20,
    isDisplayed: (env) => env.config.viewType === "list" && env.searchModel?.resModel === "ai.safe.operation",
});
