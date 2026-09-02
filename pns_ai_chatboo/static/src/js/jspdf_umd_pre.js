/** @odoo-module ignore */
/**
 * Force the jsPDF UMD onto globalThis. The Odoo 19 loader exposes AMD
 * (and sometimes CommonJS), so the vendor file never sets window.jspdf.
 * Classic scripts: this file → jspdf.umd.min.js → autotable → jspdf_umd_post.js.
 */
(function (g) {
    if (!g) {
        return;
    }
    g.__pnsJspdfSaved = {
        define: g.define,
        hasModule: typeof g.module !== "undefined",
        module: g.module,
        hasExports: typeof g.exports !== "undefined",
        exports: g.exports,
    };
    if (g.define && g.define.amd) {
        g.define = undefined;
    }
    try {
        g.module = undefined;
        g.exports = undefined;
    } catch (e) {
        /* ignore */
    }
})(typeof globalThis !== "undefined" ? globalThis : window);
