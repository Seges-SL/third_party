/** @odoo-module **/
/**
 * Datetime field rendered as fixed ISO 8601 (no locale, no relative dates).
 */
import { Component } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

export function formatMcpIsoDatetime(value) {
    if (!value) {
        return "";
    }
    if (typeof value === "string") {
        return value.trim().replace(" ", "T").slice(0, 19);
    }
    if (value && typeof value.toUTC === "function" && typeof value.toFormat === "function") {
        return value.toUTC().toFormat("yyyy-MM-dd'T'HH:mm:ss");
    }
    if (value instanceof Date) {
        const pad = (n) => String(n).padStart(2, "0");
        return (
            `${value.getUTCFullYear()}-${pad(value.getUTCMonth() + 1)}-${pad(value.getUTCDate())}` +
            `T${pad(value.getUTCHours())}:${pad(value.getUTCMinutes())}:${pad(value.getUTCSeconds())}`
        );
    }
    return String(value);
}

export class McpIsoDatetimeField extends Component {
    static template = "pns_ai_mcp.McpIsoDatetimeField";
    static props = {
        ...standardFieldProps,
    };

    get isoValue() {
        return formatMcpIsoDatetime(this.props.record.data[this.props.name]);
    }
}

registry.category("fields").add("mcp_iso_datetime", {
    component: McpIsoDatetimeField,
    supportedTypes: ["datetime"],
});
