/** @odoo-module **/
/**
 * Readonly HTML display without loading web_editor / WYSIWYG assets.
 * Use instead of widget="html" on report/help fields in backend-only installs.
 */
import { Component, onMounted, onPatched, useRef, xml } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

export class PnsHtmlReadonlyField extends Component {
    static template = xml`
        <div class="o_field_widget o_readonly pns_html_readonly" t-ref="root"/>
    `;
    static props = {
        ...standardFieldProps,
    };

    setup() {
        this.rootRef = useRef("root");
        onMounted(() => this._renderHtml());
        onPatched(() => this._renderHtml());
    }

    _renderHtml() {
        const el = this.rootRef.el;
        if (!el) {
            return;
        }
        el.innerHTML = this.props.record.data[this.props.name] || "";
    }
}

registry.category("fields").add("pns_html_readonly", {
    component: PnsHtmlReadonlyField,
    supportedTypes: ["html", "text"],
});
