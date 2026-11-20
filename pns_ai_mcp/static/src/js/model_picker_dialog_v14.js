/**
 * Mark the model-catalogue dialog so the stylesheet can stretch it.
 *
 * SPDX-License-Identifier: Apache-2.0
 * Copyright (C) 2026 Patanegra Soft <https://patanegra.com>
 */
odoo.define('pns_ai_mcp.model_picker_dialog', function (require) {
    "use strict";

    var ListController = require('web.ListController');

    ListController.include({
        start: function () {
            var self = this;
            var res = this._super.apply(this, arguments);
            var mark = function () {
                if (self.modelName !== 'ai.provider.model') {
                    return;
                }
                self.$el.addClass('o_pns_model_picker');
                self.$el.closest('.modal').addClass('o_pns_model_picker_modal');
            };
            if (res && typeof res.then === 'function') {
                return res.then(mark);
            }
            mark();
            return res;
        },
    });
});
