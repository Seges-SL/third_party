/** @odoo-module alias=jspdf **/
/**
 * AMD alias for jsPDF so later `require("jspdf")` resolves.
 *
 * The vendor UMD is loaded as a classic script (pre → umd → autotable → post)
 * so `globalThis.jspdf` is set before this module runs. Do not read the UMD
 * here first: on Odoo 19 that takes the AMD path and leaves the global empty.
 */
const jspdf = globalThis.jspdf;
export default jspdf;
