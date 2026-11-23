/** @odoo-module **/
/* SPDX-License-Identifier: Apache-2.0
 * Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
 *
 * Apps field widget: embed the module's local static/description/index.html.
 */
import { Component, xml } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

export class PnsModuleIndexField extends Component {
    static template = xml`
        <div class="pns_module_index">
            <iframe t-if="url" class="pns_module_index_iframe"
                    t-att-src="url" frameborder="0" title="Index"
                    sandbox="allow-same-origin allow-popups allow-popups-to-escape-sandbox"
                    t-on-load="onIframeLoad"/>
        </div>
    `;
    static props = {
        ...standardFieldProps,
    };

    get url() {
        return this.props.record.data[this.props.name] || "";
    }

    onIframeLoad(ev) {
        const iframe = ev.target;
        const fit = () => {
            try {
                const doc = iframe.contentDocument;
                if (!doc) {
                    iframe.style.height = "80vh";
                    return;
                }
                const h = Math.max(
                    doc.documentElement.scrollHeight || 0,
                    doc.body ? doc.body.scrollHeight : 0,
                    Math.round(window.innerHeight * 0.8)
                );
                iframe.style.height = h + "px";
            } catch (_err) {
                iframe.style.height = "80vh";
            }
        };
        fit();
        const doc = iframe.contentDocument;
        if (window.ResizeObserver && doc && doc.body) {
            new window.ResizeObserver(fit).observe(doc.body);
        }
    }
}

registry.category("fields").add("pns_module_index", {
    component: PnsModuleIndexField,
    supportedTypes: ["char"],
});
