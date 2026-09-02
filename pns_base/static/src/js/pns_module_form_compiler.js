/** @odoo-module **/
import { FormCompiler } from "@web/views/form/form_compiler";
import { patch } from "@web/core/utils/patch";
import { append, createElement } from "@web/core/utils/xml";

function isPnsModuleForm(el) {
    const form = el.closest("form") || (el.tagName === "form" ? el : null);
    return Boolean(form && /\bpns_module_form\b/.test(form.getAttribute("class") || ""));
}

patch(FormCompiler.prototype, {
    compileForm(el, params) {
        const compiled = super.compileForm(el, params);
        if (!isPnsModuleForm(el)) {
            return compiled;
        }
        compiled.classList.add("o_form_nosheet", "pns_module_form");
        compiled.setAttribute(
            "t-attf-class",
            "{{__comp__.props.record.isInEdition ? 'o_form_editable' : 'o_form_readonly'}} d-block {{ __comp__.props.record.dirty ? 'o_form_dirty' : !__comp__.props.record.isNew ? 'o_form_saved' : '' }}",
        );
        return compiled;
    },

    compileSheet(el, params) {
        if (!isPnsModuleForm(el)) {
            return super.compileSheet(el, params);
        }
        const box = createElement("div");
        box.className = "pns_module_nosheet";
        for (const child of el.childNodes) {
            const compiled = this.compileNode(child, params);
            if (!compiled || compiled.nodeName === "ButtonBox") {
                continue;
            }
            append(box, compiled);
        }
        return box;
    },
});
