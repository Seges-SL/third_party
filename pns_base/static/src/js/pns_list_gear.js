/** @odoo-module **/
/* SPDX-License-Identifier: Apache-2.0
 * Copyright (C) 2026 Patanegra Soft <https://patanegra.com>
 *
 * Gear button on the list where the control panel has no gear menu (16).
 * Modules register their list tools in registry "cogMenu"; here those same
 * entries are drawn next to New. Where the gear exists, it draws nothing.
 */
import { Component } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { Dropdown } from "@web/core/dropdown/dropdown";
import { ListController } from "@web/views/list/list_controller";

const cogMenu = registry.category("cogMenu");

// Odoo puts its own "Export All" in the gear wherever the gear exists.
function webHasGear() {
    return cogMenu.contains("export-all-menu");
}

export class PnsListGear extends Component {
    static template = "pns_base.ListGear";
    static components = { Dropdown };
    static props = {};

    get items() {
        if (webHasGear()) {
            return [];
        }
        return cogMenu
            .getEntries()
            .filter(([, item]) => !item.isDisplayed || item.isDisplayed(this.env))
            .sort(([, a], [, b]) => (a.groupNumber || 0) - (b.groupNumber || 0))
            .map(([key, item]) => ({ key, Component: item.Component }));
    }
}

ListController.components = { ...ListController.components, PnsListGear };
