/** @odoo-module **/
/**
 * mcp_log_form.js  (OWL 2 – Odoo 17+)
 *
 * Copy buttons in the log form use native clipboard API via inline event
 * delegation — no framework dependency needed. This minimal module wires
 * them up once the page is ready using a MutationObserver approach.
 *
 * Legacy Odoo 14 version: mcp_log_form_v14.js (loaded via assets.xml)
 */

// Simple delegation: clipboard copy for .o_field_text_copy_btn buttons
// Works without any OWL component since the buttons are standard HTML.
document.addEventListener("click", async function (ev) {
    const btn = ev.target.closest(".o_field_text_copy_btn");
    if (!btn) return;
    ev.preventDefault();
    ev.stopPropagation();

    const container = btn.closest(".o_field_text_copy_container");
    const target = container?.querySelector(".o_field_text_copy_target");
    if (!target) return;

    const textarea = target.querySelector("textarea");
    const text = textarea ? textarea.value : (target.querySelector("pre, div, .o_field_text")?.textContent || target.textContent);

    if (text?.trim()) {
        try {
            await navigator.clipboard.writeText(text.trim());
        } catch {
            console.warn("Clipboard copy failed");
        }
    }
}, true);
