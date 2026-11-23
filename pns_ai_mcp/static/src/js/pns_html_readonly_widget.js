/** @odoo-module **/
/**
 * Readonly HTML display without loading web_editor / WYSIWYG assets.
 * Use instead of widget="html" on report/help fields in backend-only installs.
 *
 * SPDX-License-Identifier: Apache-2.0
 * Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
 */
import { Component, onMounted, onPatched, useRef, xml } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

const DROP_TAGS = "script,iframe,frame,object,embed,link,meta,base,form";
const URL_ATTRS = /^(href|src|xlink:href|action|formaction)$/;
const BAD_URL = /^(javascript|vbscript|data):/;

// Parsed in an inert <template>: nothing runs while it is cleaned.
function withoutActiveContent(html) {
    const tpl = document.createElement("template");
    tpl.innerHTML = html || "";
    tpl.content.querySelectorAll(DROP_TAGS).forEach((node) => node.remove());
    tpl.content.querySelectorAll("*").forEach((el) => {
        for (const attr of Array.from(el.attributes)) {
            const name = attr.name.toLowerCase();
            const value = (attr.value || "").replace(/[\s\u0000-\u001f]/g, "").toLowerCase();
            const badUrl = URL_ATTRS.test(name) && BAD_URL.test(value)
                && !/^data:image\//.test(value);
            if (name.startsWith("on") || badUrl || name === "srcdoc") {
                el.removeAttribute(attr.name);
            }
        }
    });
    return tpl.innerHTML;
}

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
        el.innerHTML = withoutActiveContent(this.props.record.data[this.props.name]);
    }
}

registry.category("fields").add("pns_html_readonly", {
    component: PnsHtmlReadonlyField,
    supportedTypes: ["html", "text"],
});
