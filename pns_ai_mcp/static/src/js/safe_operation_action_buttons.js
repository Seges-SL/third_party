/** @odoo-module **/
/**
 * Operations cogMenu item for Approvals (safe_operation) list view (Odoo 17+).
 * Opens Approval Tools (refresh expiry + export).
 *
 * SPDX-License-Identifier: Apache-2.0
 * Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
 */
import { registry } from "@web/core/registry";
import { Component, xml } from "@odoo/owl";
import { DropdownItem } from "@web/core/dropdown/dropdown_item";
import { _t } from "@web/core/l10n/translation";
import { pnsPatch } from "@pns_base/js/pns_patch";
import { ListController } from "@web/views/list/list_controller";
import { FormController } from "@web/views/form/form_controller";

function _isSafePlanView(controller) {
    return (
        controller.props?.resModel === "ai.safe.operation"
        || controller.env?.searchModel?.resModel === "ai.safe.operation"
    );
}

function _reloadSafePlanView(controller) {
    if (!_isSafePlanView(controller)) {
        return;
    }
    // Same client reload as the Confirm button (_notify_reload).
    const action = controller.env.services.action;
    if (action && typeof action.doAction === "function") {
        action.doAction({ type: "ir.actions.client", tag: "reload" });
    }
}

function _bindSafePlanBus(controller) {
    const bus = controller.env.services.bus_service;
    if (!_isSafePlanView(controller)) {
        return;
    }
    if (typeof bus.subscribe === "function") {
        bus.subscribe("pns_safe_plan", () => _reloadSafePlanView(controller));
    }
}

pnsPatch(ListController.prototype, "pns_ai_mcp.safe_operation_action_buttons", {
    setup() {
        super.setup();
        _bindSafePlanBus(this);
    },
});

pnsPatch(FormController.prototype, "pns_ai_mcp.safe_operation_action_buttons", {
    setup() {
        super.setup();
        _bindSafePlanBus(this);
    },
});

class SafeOperationToolsCogItem extends Component {
    static template = xml`<DropdownItem onSelected.bind="openWizard"><i class="fa fa-cog me-2"></i> <t t-esc="toolsLabel"/></DropdownItem>`;
    static components = { DropdownItem };
    static props = {};

    get toolsLabel() {
        return _t("Tools");
    }

    openWizard() {
        this.env.services.action.doAction("pns_ai_mcp.action_safe_operation_tools_wizard");
    }
}

registry.category("cogMenu").add("safe_operation_tools", {
    Component: SafeOperationToolsCogItem,
    groupNumber: 20,
    isDisplayed: (env) => env.config.viewType === "list" && env.searchModel?.resModel === "ai.safe.operation",
});
