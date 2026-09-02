/** @odoo-module **/
/**
 * mcp_json_compressed_widget.js  (OWL 2 – Odoo 17+)
 * Displays a compressed JSON field with click-to-expand and clipboard copy.
 * On expand, fetches the full original field value via ORM.
 * Legacy Odoo 14 version: mcp_json_compressed_widget_v14.js (loaded via assets.xml)
 */

import { Component, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { standardFieldProps } from "@web/views/fields/standard_field_props";
import { useService } from "@web/core/utils/hooks";

// Map of compressed field name → original field name
const ORIGINAL_FIELD_MAP = {
    prompt_data_compressed: "prompt_data",
    result_summary_compressed: "result_data",
};

function _getOriginalField(fieldName) {
    return ORIGINAL_FIELD_MAP[fieldName] || fieldName.replace("_compressed", "");
}

function _compressValue(raw) {
    if (!raw) return "";
    try {
        let parsed = JSON.parse(raw);
        if (typeof parsed === "string") {
            try { parsed = JSON.parse(parsed); } catch { /* ok */ }
        }
        return JSON.stringify(parsed, null, 0).replace(/\s+/g, " ").trim();
    } catch {
        return raw.replace(/\\n/g, " ").replace(/\\"/g, '"').replace(/\\t/g, " ").replace(/\s+/g, " ").trim();
    }
}

function _formatValue(raw) {
    if (!raw) return "";
    try {
        let parsed = JSON.parse(raw);
        if (typeof parsed === "string") {
            try { parsed = JSON.parse(parsed); } catch { /* ok */ }
        }
        return JSON.stringify(parsed, null, 2);
    } catch {
        return raw.replace(/\\n/g, "\n").replace(/\\"/g, '"').replace(/\\t/g, "\t").replace(/\\r/g, "\r");
    }
}

export class MCPJsonCompressedWidget extends Component {
    static template = "pns_ai_mcp.MCPJsonCompressedWidget";
    static props = {
        ...standardFieldProps,
    };

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.state = useState({
            expanded: false,
            expandedValue: null,
        });
    }

    get value() {
        return this.props.record.data[this.props.name] || "";
    }

    get compressedValue() {
        return _compressValue(this.value);
    }

    async toggleExpanded() {
        if (this.state.expanded) {
            this.state.expanded = false;
            return;
        }
        // Load full value if not yet fetched
        if (this.state.expandedValue === null) {
            await this._loadFullValue();
        }
        this.state.expanded = true;
    }

    async _loadFullValue() {
        const resId = this.props.record.resId;
        const model = this.props.record.resModel;
        const originalField = _getOriginalField(this.props.name);

        if (!resId) {
            this.state.expandedValue = _formatValue(this.value);
            return;
        }
        try {
            const result = await this.orm.read(model, [resId], [originalField]);
            const raw = result?.[0]?.[originalField] || this.value;
            this.state.expandedValue = _formatValue(raw);
        } catch {
            this.state.expandedValue = _formatValue(this.value);
        }
    }

    async copyToClipboard() {
        let text = this.state.expandedValue;
        if (!text) {
            // Load if not yet fetched
            await this._loadFullValue();
            text = this.state.expandedValue;
        }
        text = text || this.compressedValue;
        try {
            await navigator.clipboard.writeText(text);
            this.notification.add("Contenido copiado al portapapeles", {
                type: "success",
                title: "Copiado",
            });
        } catch {
            this.notification.add("Error al copiar", { type: "danger" });
        }
    }
}

registry.category("fields").add("mcp_json_compressed", {
    component: MCPJsonCompressedWidget,
    supportedTypes: ["char", "text"],
});
