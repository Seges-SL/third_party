/** @odoo-module ignore */
/**
 * Restore AMD / CommonJS after the jsPDF UMD and AutoTable have attached
 * to globalThis.jspdf (see jspdf_umd_pre.js).
 */
(function (g) {
    if (!g) {
        return;
    }
    var saved = g.__pnsJspdfSaved;
    if (saved) {
        if (typeof saved.define !== "undefined") {
            g.define = saved.define;
        }
        try {
            if (saved.hasModule) {
                g.module = saved.module;
            }
            if (saved.hasExports) {
                g.exports = saved.exports;
            }
        } catch (e) {
            /* ignore */
        }
        delete g.__pnsJspdfSaved;
    }
})(typeof globalThis !== "undefined" ? globalThis : window);
