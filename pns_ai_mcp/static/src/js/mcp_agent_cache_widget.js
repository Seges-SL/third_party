/** @odoo-module **/
/**
 * Read-only Text field for agent cache with clipboard copy button (OWL 2).
 */

import { Component } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { standardFieldProps } from "@web/views/fields/standard_field_props";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

export class MCPAgentCacheField extends Component {
    static template = "pns_ai_mcp.AgentCacheTextField";
    static props = {
        ...standardFieldProps,
    };

    setup() {
        this.notification = useService("notification");
    }

    get value() {
        return this.props.record.data[this.props.name] || "";
    }

    get copyTitle() {
        return _t("Copy to clipboard");
    }

    async copyToClipboard() {
        if (!this.value) {
            return;
        }
        try {
            await navigator.clipboard.writeText(this.value);
            this.notification.add(_t("Copied to clipboard"), { type: "success" });
        } catch {
            this.notification.add(_t("Could not copy to clipboard"), { type: "danger" });
        }
    }
}

registry.category("fields").add("agent_cache_copy", {
    component: MCPAgentCacheField,
    supportedTypes: ["text"],
});
