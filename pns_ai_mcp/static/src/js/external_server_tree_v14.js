// -*- coding: utf-8 -*-
// Operations button for External Servers list (Odoo 14).
odoo.define('pns_ai_mcp.external_server_tree', function (require) {
    "use strict";

    var ListController = require('web.ListController');
    var core = require('web.core');
    var _t = core._t;

    ListController.include({
        renderButtons: function () {
            this._super.apply(this, arguments);

            if (this.modelName !== 'ai.api.server') {
                return;
            }

            if (!this.$buttons || typeof this.$buttons !== 'object' || !this.$buttons.length) {
                return;
            }

            var self = this;

            var $toolsBtn = $('<button>', {
                type: 'button',
                class: 'btn btn-secondary o_mcp_btn_sm',
                html: "<i class='fa fa-cog'></i> " + _t("Tools"),
                title: _t("External Server Tools"),
                style: 'margin-left: 4px;',
                click: function () {
                    self.do_action('pns_ai_mcp.action_external_server_tools_wizard');
                },
            });

            self.$buttons.append($toolsBtn);
        },
    });
});
