/** @odoo-module **/
/**
 * mcp_api_key_widget.js  (OWL 2 – Odoo 17+)
 * Custom field widget: shows API key value + clipboard copy button.
 * Legacy Odoo 14 version: mcp_api_key_widget_v14.js (loaded via assets.xml)
 */

import { Component } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { standardFieldProps } from "@web/views/fields/standard_field_props";
import { useService } from "@web/core/utils/hooks";

export class MCPApiKeyField extends Component {
    static template = "pns_ai_mcp.MCPApiKeyField";
    static props = {
        ...standardFieldProps,
    };

    setup() {
        this.notification = useService("notification");
    }

    get value() {
        return this.props.record.data[this.props.name] || "";
    }

    async copyToClipboard() {
        if (!this.value) return;
        try {
            await navigator.clipboard.writeText(this.value);
            this.notification.add("API Key MCP copiada al portapapeles", { type: "success" });
        } catch {
            this.notification.add("Error al copiar API Key MCP", { type: "danger" });
        }
    }
}

registry.category("fields").add("mcp_api_key_display", {
    component: MCPApiKeyField,
    supportedTypes: ["char"],
});
