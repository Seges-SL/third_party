/**
 * Starts the key PIN desk once the Odoo 14 web client is up.
 *
 * SPDX-License-Identifier: Apache-2.0
 * Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
 */
odoo.define('pns_ai_mcp.key_pin_desk_boot', function (require) {
    "use strict";

    var WebClient = require('web.WebClient');
    var desk = require('pns_ai_mcp.key_pin_desk');

    if (!desk.enabled) {
        return;
    }
    WebClient.include({
        start: function () {
            var self = this;
            return this._super.apply(this, arguments).then(function () {
                desk.listen(self, function () {
                    return self.call.apply(self, ['bus_service'].concat(Array.prototype.slice.call(arguments)));
                });
            });
        },
    });
});
