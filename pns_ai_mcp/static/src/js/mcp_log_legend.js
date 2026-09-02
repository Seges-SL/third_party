/** @odoo-module **/
/**
 * Barra de leyenda de colores en la lista de MCP Logs (owl2 / Odoo 17+).
 *
 * FUENTE ÚNICA: el HTML de la leyenda lo genera el servidor en
 * ``ai.log.render_flow_legend('grid')``. Aquí solo se trae (una vez, cacheado)
 * y se inyecta. La ficha (form) usa el mismo método, así que grid y form nunca
 * divergen.
 */
import { ListController } from "@web/views/list/list_controller";
import { ListRenderer } from "@web/views/list/list_renderer";
import { patch } from "@web/core/utils/patch";
import { useService } from "@web/core/utils/hooks";
import { onMounted, onPatched } from "@odoo/owl";

let _legendHtmlCache = null;

async function fetchLegendHtml(orm) {
    if (_legendHtmlCache === null) {
        _legendHtmlCache = await orm.call("ai.log", "render_flow_legend", ["grid"]);
    }
    return _legendHtmlCache;
}

function insertMcpLogLegend(root, html) {
    if (!root || !html) {
        return false;
    }
    const scope = root.closest(".o_action") || root;
    if (scope.querySelector(".o_mcp_log_legend_bar")) {
        return true;
    }
    // La leyenda se inserta en el CONTROL PANEL (zona fija, sin scroll). Insertarla
    // antes del renderer/list dejaba la barra dentro del área scrollable y, al sumar
    // altura, aparecía un segundo scrollbar vertical. En el control panel queda un
    // único scroll (el de la lista).
    const cp = scope.querySelector(".o_control_panel");
    if (!cp) {
        return false;
    }
    const wrapper = document.createElement("div");
    wrapper.innerHTML = html;
    const legend = wrapper.firstElementChild;
    if (!legend) {
        return false;
    }
    cp.appendChild(legend);
    return true;
}

function scheduleLegendInsert(component, orm, isMcpLogList) {
    if (!isMcpLogList()) {
        return;
    }
    // Insert with bounded retries: on first mount the list table may not be in
    // the DOM yet (anchor not found). Retry a few times via timeout instead of
    // giving up, so the legend reliably appears in the list view.
    const runWithRetries = async (attempt = 0) => {
        if (!isMcpLogList()) {
            return;
        }
        let html;
        try {
            html = await fetchLegendHtml(orm);
        } catch (e) {
            return;
        }
        const root =
            component.rootRef?.el ||
            component.root?.el ||
            component.el ||
            document.querySelector(".o_action .o_list_view");
        const done = insertMcpLogLegend(root, html);
        if (!done && attempt < 10) {
            setTimeout(() => runWithRetries(attempt + 1), 60);
        }
    };
    onMounted(() => runWithRetries(0));
    onPatched(() => runWithRetries(0));
}

patch(ListRenderer.prototype, {
    setup() {
        super.setup(...arguments);
        const orm = useService("orm");
        scheduleLegendInsert(this, orm, () => this.props.list?.resModel === "ai.log");
    },
});

patch(ListController.prototype, {
    setup() {
        super.setup(...arguments);
        const orm = useService("orm");
        scheduleLegendInsert(this, orm, () => this.props.resModel === "ai.log");
    },
});
