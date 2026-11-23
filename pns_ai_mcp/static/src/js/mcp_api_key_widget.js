/** @odoo-module **/
/**
 * mcp_api_key_widget.js  (OWL 2 – Odoo 17+)
 * Custom field widget: shows API key value + clipboard copy button.
 * Legacy Odoo 14 version: mcp_api_key_widget_v14.js (loaded via assets.xml)
 *
 * SPDX-License-Identifier: Apache-2.0
 * Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
 */

import { Component } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { standardFieldProps } from "@web/views/fields/standard_field_props";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

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

    get emptyLabel() {
        return _t("No API Key");
    }

    async copyToClipboard() {
        if (!this.value) return;
        try {
            await navigator.clipboard.writeText(this.value);
            this.notification.add(_t("MCP API Key copied to clipboard"), { type: "success" });
        } catch {
            this.notification.add(_t("Error copying the MCP API Key"), { type: "danger" });
        }
    }
}

registry.category("fields").add("mcp_api_key_display", {
    component: MCPApiKeyField,
    supportedTypes: ["char"],
});
