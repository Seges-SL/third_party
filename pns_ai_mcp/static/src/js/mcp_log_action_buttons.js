/** @odoo-module **/
/**
 * Operations cogMenu item for History (ai.log) list view (Odoo 17+).
 * Opens the tools wizard with Export/Clear operations.
 */
import { registry } from "@web/core/registry";
import { Component, xml } from "@odoo/owl";
import { DropdownItem } from "@web/core/dropdown/dropdown_item";
import { _t } from "@web/core/l10n/translation";

class LogToolsCogItem extends Component {
    static template = xml`<DropdownItem onSelected.bind="openWizard"><i class="fa fa-cog me-2"></i> <t t-esc="toolsLabel"/></DropdownItem>`;
    static components = { DropdownItem };
    static props = {};

    get toolsLabel() {
        return _t("Tools");
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
