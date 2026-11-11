/* SPDX-License-Identifier: Apache-2.0 */
/* Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com> */
/**
 * Chatboo app / menu click on Odoo 14 (legacy ActionManager).
 */
odoo.define('pns_ai_chatboo.chatboo_open', function (require) {
    "use strict";

    var ActionManager = require('web.ActionManager');
    var core = require('web.core');
    var ChatbooSystrayItem = require('pns_ai_chatboo.chatboo_systray');

    // App / menu: show the overlay and do NOT push the client action
    // (that empty action is the blank page on collapse).
    ActionManager.include({
        _executeClientAction: function (action, options) {
            if (action && ChatbooSystrayItem.CLIENT_TAGS[action.tag]) {
                core.bus.trigger('chatboo_overlay_show', ChatbooSystrayItem.contextFromAction(action));
                return $.when();
            }
            return this._super.apply(this, arguments);
        },
    });
});
