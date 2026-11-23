# Copyright 2026 Seges
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0).
"""Does loading the Chatboo libraries replace Odoo's window.Chart? (patch 20)

Odoo 17 loads Chart.js plus chartjs-adapter-luxon on demand (bundle
web.chartjs_lib). Chatboo loads its own Chart.js with loadJS when the chat
opens (loadHeavyLibs). Both UMD builds write window.Chart, and loadJS and
loadBundle are memoized, so whoever loads last owns window.Chart for the
rest of the page.

Every failure message starts with a tag:
- [HYPOTHESIS]: the check this test exists for failed;
- [SETUP]: a precondition failed (module or bundle missing, Odoo's Chart.js
  without luxon); says nothing about the hypothesis;
- [ERROR]: unexpected exception in the test itself.
Each message ends with the Chart.js version and date adapter found.
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

_CHAT_BEFORE_ODOO = _HELPERS + r"""
return run(async () => {
    await loadChatLibs();
    const chat = window.Chart;
    if (typeof chat !== "function") {
        throw setup("the chat libraries did not define window.Chart");
    }
    await loadOdooChart();
    if (window.Chart === chat) {
        throw setup("web.chartjs_lib did not load after the chat libraries");
    }
    checkOdooChart(null);
});
"""


def _wrap(body):
    return "(async () => {" + body + "})();"


@tagged("post_install", "-at_install")
class TestChatbooChartCollision(HttpCase):

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
