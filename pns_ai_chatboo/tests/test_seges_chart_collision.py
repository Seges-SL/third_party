# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 Seges
# Seges: parche 20 (PNS-70, compatibilidad; test de la fase 2, T6, copiado del
# laboratorio). Ver docs/pendiente/parches_pns_ai.md
"""Parche 20 (PNS-70): el Chart.js del chat no sustituye a window.Chart.

Odoo 17 carga su Chart.js con chartjs-adapter-luxon a demanda (bundle
web.chartjs_lib). Chatboo carga el suyo (4.4.8) con loadJS al abrir el chat
(loadHeavyLibs). loadJS y loadBundle están memorizados
(addons/web/static/src/core/assets.js:30 y :98) y los dos UMD escriben
window.Chart: sin el parche, el último que carga se queda window.Chart hasta
recargar la página. Con el parche, el del chat es window.PnsChatbooChart y es
el que recibe bindEngines (static/src/js/chatboo_heavy_libs.js).

Copiado de seges_pruebas_3996/tests/test_chart_collision.py (decisión 117):
- test_chat_after_odoo_keeps_odoo_chart: el [HYPOTHESIS], sin cambios;
- test_chat_before_odoo: el testigo, adaptado; el del laboratorio exige que
  las librerías del chat definan window.Chart, que es lo que el parche quita;
- test_chat_engine_is_its_own_chart: nuevo, lo que recibe bindEngines (el
  segundo trozo de chatboo_heavy_libs.js).
Cada test abre /web en una página nueva. Sin Chrome, Odoo los omite.

Cada fallo empieza por una etiqueta:
- [HYPOTHESIS]: falló la comprobación del parche;
- [SETUP]: falló una precondición; no dice nada del parche;
- [ERROR]: excepción inesperada del propio test.
Cada mensaje termina con la versión y el adaptador de fechas de window.Chart.
"""

from odoo.tests import HttpCase, tagged

_HELPERS = r"""
const tagged = (tag, message) => Object.assign(new Error(message), { tag });
const setup = (message) => tagged("[SETUP]", message);
const hypothesis = (message) => tagged("[HYPOTHESIS]", message);

function adapterId(chart) {
    return new chart._adapters._date({})._id;
}
function describe(chart) {
    if (typeof chart !== "function") {
        return `window.Chart is ${typeof chart}`;
    }
    let adapter;
    try {
        adapter = adapterId(chart);
    } catch (e) {
        adapter = `error (${e.message})`;
    }
    return `Chart.js ${chart.version}, date adapter ${adapter}`;
}
function getModule(name) {
    const mod = odoo.loader.modules.get(name);
    if (!mod) {
        throw setup(`JS module ${name} not found`);
    }
    return mod;
}
async function loadOdooChart() {
    await getModule("@web/core/assets").loadBundle("web.chartjs_lib");
    if (typeof window.Chart !== "function") {
        throw setup("web.chartjs_lib did not define window.Chart");
    }
}
async function loadChatLibs() {
    // Same call as chatboo_overlay.js show().
    await getModule("@pns_ai_chatboo/js/chatboo_heavy_libs").loadHeavyLibs();
}
function drawTimeChart(chart) {
    const canvas = document.createElement("canvas");
    canvas.width = 300;
    canvas.height = 150;
    document.body.appendChild(canvas);
    let instance;
    try {
        instance = new chart(canvas, {
            type: "line",
            data: {
                datasets: [{
                    label: "t",
                    data: [
                        { x: Date.UTC(2026, 0, 1), y: 1 },
                        { x: Date.UTC(2026, 0, 2), y: 2 },
                    ],
                }],
            },
            options: {
                animation: false,
                responsive: false,
                scales: { x: { type: "time" } },
            },
        });
    } catch (e) {
        throw hypothesis(`a "time" axis chart failed: ${e.message}`);
    } finally {
        if (instance) {
            instance.destroy();
        }
        canvas.remove();
    }
}
function checkOdooChart(expected) {
    if (expected && window.Chart !== expected.chart) {
        throw hypothesis(
            `window.Chart was replaced: expected Odoo's Chart.js ` +
            `${expected.version} with luxon`
        );
    }
    if (adapterId(window.Chart) !== "luxon") {
        throw hypothesis("window.Chart has no luxon date adapter");
    }
    drawTimeChart(window.Chart);
}
async function run(steps) {
    try {
        await steps();
        console.log("test successful");
    } catch (e) {
        const tag = e.tag || "[ERROR]";
        console.error(`${tag} ${e.message} | found: ${describe(window.Chart)}`);
    }
}
"""

_CHAT_AFTER_ODOO = _HELPERS + r"""
return run(async () => {
    await loadOdooChart();
    const odooChart = { chart: window.Chart, version: window.Chart.version };
    if (adapterId(odooChart.chart) !== "luxon") {
        throw setup("Odoo's Chart.js has no luxon adapter before the chat");
    }
    await loadChatLibs();
    checkOdooChart(odooChart);
});
"""

# Seges: adaptado a la 17 (fase 2, T6): con el parche, las librerías del chat
# ya no definen window.Chart; el testigo comprueba que no lo cambian y que el
# Chart.js del chat es window.PnsChatbooChart.
_CHAT_BEFORE_ODOO = _HELPERS + r"""
return run(async () => {
    const before = window.Chart;
    await loadChatLibs();
    if (window.Chart !== before) {
        throw hypothesis("the chat libraries replaced window.Chart");
    }
    const chat = window.PnsChatbooChart;
    if (typeof chat !== "function") {
        throw hypothesis("the chat libraries did not define PnsChatbooChart");
    }
    await loadOdooChart();
    if (window.Chart === chat || window.PnsChatbooChart !== chat) {
        throw hypothesis("Odoo's Chart.js and the chat's are mixed up");
    }
    checkOdooChart(null);
});
"""

# Seges: nuevo en la 17 (fase 2, T6): lo que recibe bindEngines.
_CHAT_ENGINE = _HELPERS + r"""
return run(async () => {
    const charts = window.ChatbooCharts;
    if (!charts || typeof charts.bindEngines !== "function") {
        throw setup("window.ChatbooCharts.bindEngines not found");
    }
    const bound = [];
    const original = charts.bindEngines;
    charts.bindEngines = (chart, echarts) => {
        bound.push(chart);
        return original(chart, echarts);
    };
    try {
        await loadOdooChart();
        await loadChatLibs();
    } finally {
        charts.bindEngines = original;
    }
    if (bound.length !== 1) {
        throw setup(`bindEngines was called ${bound.length} times`);
    }
    const chat = window.PnsChatbooChart;
    if (typeof chat !== "function" || bound[0] !== chat) {
        throw hypothesis(
            `bindEngines did not get the chat's Chart.js: got ${describe(bound[0])}`
        );
    }
    if (chat === window.Chart) {
        throw hypothesis("the chat's Chart.js is window.Chart");
    }
});
"""


def _wrap(body):
    return "(async () => {" + body + "})();"


@tagged('post_install', '-at_install', 'pns_ai_chatboo', 'seges_t6')
class TestSegesChatbooChartCollision(HttpCase):

    def test_chat_after_odoo_keeps_odoo_chart(self):
        self.browser_js(
            "/web",
            _wrap(_CHAT_AFTER_ODOO),
            ready="odoo.isReady === true",
            login="admin",
            timeout=120,
        )

    def test_chat_before_odoo(self):
        self.browser_js(
            "/web",
            _wrap(_CHAT_BEFORE_ODOO),
            ready="odoo.isReady === true",
            login="admin",
            timeout=120,
        )

    def test_chat_engine_is_its_own_chart(self):
        self.browser_js(
            "/web",
            _wrap(_CHAT_ENGINE),
            ready="odoo.isReady === true",
            login="admin",
            timeout=120,
        )
