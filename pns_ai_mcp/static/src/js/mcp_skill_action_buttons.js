/** @odoo-module **/
/**
 * mcp_skill_action_buttons.js
 *
 * Registers "Herramientas" in the native cogMenu (gear) for the ai.skill
 * list view in Odoo 17+. Opens the python/XML tools wizard, mirroring the
 * Contexts tools UX (mcp_context_action_buttons.js).
 *
 * Legacy Odoo 14 version: mcp_skill_tree_v14.js (loaded via assets.xml).
 */
import { registry } from "@web/core/registry";
import { Component, xml } from "@odoo/owl";
import { DropdownItem } from "@web/core/dropdown/dropdown_item";
import { _t } from "@web/core/l10n/translation";

class SkillToolsCogItem extends Component {
    static template = xml`<DropdownItem onSelected.bind="openWizard"><i class="fa fa-cog me-2"></i> <t t-esc="toolsLabel"/></DropdownItem>`;
    static components = { DropdownItem };
    static props = {};

    get toolsLabel() {
        return _t("Tools");
    }

    openWizard() {
        this.env.services.action.doAction("pns_ai_mcp.action_ai_skill_tools_wizard");
    }
}

registry.category("cogMenu").add("mcp_skill_tools", {
    Component: SkillToolsCogItem,
    groupNumber: 20,
    isDisplayed: (env) => env.config.viewType === "list" && env.searchModel?.resModel === "ai.skill",
});
