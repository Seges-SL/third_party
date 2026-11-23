/** @odoo-module **/
/* SPDX-License-Identifier: Apache-2.0 */
/* Copyright (C) 2026 Patanegra Soft <https://patanegra.com> */
/**
 * Load Chart.js, ECharts, jsPDF and html2canvas only when the chat opens.
 */
import { loadJS } from "@web/core/assets";

let promise;

const VENDOR = [
    "/pns_ai_chatboo/static/src/js/jspdf_umd_pre.js",
    "/pns_ai_chatboo/static/src/js/jspdf.umd.min.js",
    "/pns_ai_chatboo/static/src/js/jspdf.plugin.autotable.min.js",
    "/pns_ai_chatboo/static/src/js/jspdf_umd_post.js",
    "/pns_ai_chatboo/static/src/js/html2canvas.min.js",
    "/pns_ai_chatboo/static/src/js/chart.umd.min.js",
    "/pns_ai_chatboo/static/src/js/echarts.min.js",
];

export function loadHeavyLibs() {
    if (!promise) {
        promise = (async () => {
            for (const url of VENDOR) {
                await loadJS(url);
            }
            const chart = window.Chart;
            const echarts = window.echarts;
            if (window.ChatbooCharts && window.ChatbooCharts.bindEngines) {
                window.ChatbooCharts.bindEngines(chart, echarts);
            }
        })();
    }
    return promise;
}
