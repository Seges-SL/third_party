/** @odoo-module **/
/**
 * context_window_combo.js  (OWL 2 – Odoo 17+)
 * Context window (tokens) as a plain dropdown <select>. Options are a curated
 * ladder of ROUND sizes (powers of two and their 1.5x/3x multiples, all exact
 * multiples of 1024), matching real LLM context windows from 1K to 2M. If the
 * stored value is off-grid (set via import/backup), it is injected as an extra
 * option so it still shows.
 * Legacy Odoo 14 version: context_window_combo_v14.js (loaded via assets.xml).
 */

import { Component } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

// Round token sizes (K = 1024). Clean powers of two plus 1.5x/3x half-steps.
const STEP_VALUES = [
    1024, 2048, 4096, 8192, 12288, 16384, 24576, 32768, 49152, 65536,
    98304, 131072, 196608, 262144, 393216, 524288, 786432, 1048576,
    1572864, 2097152,
];

function _compact(n) {
    if (n >= 1048576) {
        return `${(n / 1048576).toFixed(n % 1048576 ? 1 : 0)}M`;
    }
    if (n >= 1024) {
        return `${(n / 1024).toFixed(n % 1024 ? 1 : 0)}K`;
    }
    return `${n}`;
}

function _label(n) {
    if (!n || isNaN(n) || n <= 0) {
        return "";
    }
    return `${_compact(n)} — ${new Intl.NumberFormat().format(n)}`;
}

export class ContextWindowComboWidget extends Component {
    static template = "pns_ai_mcp.ContextWindowComboWidget";
    static props = {
        ...standardFieldProps,
        id: { type: String, optional: true },
    };

    setup() {
        this.options = this._buildOptions();
    }

    get value() {
        return this.props.record.data[this.props.name] ?? "";
    }

    get readonlyLabel() {
        return _label(this.value);
    }

    _buildOptions() {
        const values = [...STEP_VALUES];
        const cur = this.value;
        if (cur && !values.includes(cur)) {
            values.unshift(cur);
        }
        return values.map((v) => ({ value: v, label: _label(v) }));
    }

    onChange(ev) {
        const val = parseInt(ev.target.value, 10);
        this.props.record.update({ [this.props.name]: isNaN(val) ? false : val });
    }
}

registry.category("fields").add("context_window_combo", {
    component: ContextWindowComboWidget,
    supportedTypes: ["integer"],
});
