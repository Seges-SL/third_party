/* SPDX-License-Identifier: Apache-2.0 */
/* Copyright (C) 2026 Patanegra Soft <https://patanegra.com> */
/**
 * Load Chart.js, ECharts, jsPDF and html2canvas only when the chat opens.
 */
odoo.define('pns_ai_chatboo.heavy_libs', function (require) {
    "use strict";

    var ajax = require('web.ajax');
    var promise;

    var VENDOR = [
        '/pns_ai_chatboo/static/src/js/jspdf.umd.min.js',
        '/pns_ai_chatboo/static/src/js/jspdf.plugin.autotable.min.js',
        '/pns_ai_chatboo/static/src/js/html2canvas.min.js',
        // Seges: parche 20 (PNS-70, compatibilidad). Ver docs/pendiente/parches_pns_ai.md
        // New url: a browser must not reuse its cached copy of the original.
        '/pns_ai_chatboo/static/src/js/chart.umd.min.js?seges=20',
        '/pns_ai_chatboo/static/src/js/echarts.min.js',
    ];

    function loadHeavyLibs() {
        if (promise) {
            return promise;
        }
        promise = VENDOR.reduce(function (chain, url) {
            return chain.then(function () {
                return ajax.loadJS(url);
            });
        }, Promise.resolve()).then(function () {
            // Seges: parche 20 (PNS-70, compatibilidad). Ver docs/pendiente/parches_pns_ai.md
            var chart = window.PnsChatbooChart;
            var echarts = window.echarts;
            if (window.ChatbooCharts && window.ChatbooCharts.bindEngines) {
                window.ChatbooCharts.bindEngines(chart, echarts);
            }
        });
        return promise;
    }

    return {loadHeavyLibs: loadHeavyLibs};
});
