/** @odoo-module **/
/* SPDX-License-Identifier: Apache-2.0 */
/* Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com> */
/**
 * Chatboo app / menu click on Odoo 15 (action service).
 */
import { registry } from "@web/core/registry";
import core from "web.core";
import ChatbooSystrayItem from "pns_ai_chatboo.chatboo_systray";

// App / menu: show the overlay and do NOT push the client action
// (that empty action is the blank page on collapse).
for (const tag of Object.keys(ChatbooSystrayItem.CLIENT_TAGS)) {
    registry.category("actions").add(tag, (env, action) => {
        core.bus.trigger("chatboo_overlay_show", ChatbooSystrayItem.contextFromAction(action));
    });
}
