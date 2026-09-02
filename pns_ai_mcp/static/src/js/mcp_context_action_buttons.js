/** @odoo-module **/
/**
 * mcp_context_action_buttons.js
 *
 * Registers "Herramientas de Contextos" in the native cogMenu (⚙️)
 * for the mcp.context list view in Odoo 17+.
 * This launches the python/XML wizard, ensuring logic is unified
 * and UX is native.
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
