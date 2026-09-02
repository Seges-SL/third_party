// -*- coding: utf-8 -*-
// Operations button for AI Agents list (Odoo 14).
// Model: 'ai.agent'.
odoo.define('pns_ai_mcp.ai_agent_tree', function (require) {
    "use strict";

    var ListController = require('web.ListController');
    var core = require('web.core');
    var _t = core._t;

    ListController.include({
        renderButtons: function () {
            this._super.apply(this, arguments);

            if (this.modelName !== 'ai.agent') {
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
                title: _t("Agent Tools"),
                style: 'margin-left: 4px;',
                click: function () {
                    self.do_action('pns_ai_mcp.action_agent_tools_wizard');
                },
            });

            self.$buttons.append($toolsBtn);
        },
    });
});
