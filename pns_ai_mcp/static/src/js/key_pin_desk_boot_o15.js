/** @odoo-module **/
/**
 * Starts the key PIN desk once the Odoo 15 web client is up.
 *
 * SPDX-License-Identifier: Apache-2.0
 * Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
 */
import { registry } from "@web/core/registry";
import desk from "pns_ai_mcp.key_pin_desk";

registry.category("services").add("pns_key_pin_desk", {
    start(env) {
        if (!desk.enabled) {
            return;
        }
        env.bus.on("WEB_CLIENT_READY", null, () => {
            const bus = owl.Component.env.services.bus_service;
            desk.listen(desk, (method, ...args) => bus[method](...args));
        });
    },
});
