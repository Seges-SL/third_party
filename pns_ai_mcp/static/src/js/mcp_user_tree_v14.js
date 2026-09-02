// -*- coding: utf-8 -*-
// Archivo: static/src/js/mcp_user_tree_v14.js
// Descripción: Operations button + toggle reload for MCP Users (Odoo 14).

odoo.define('pns_ai_mcp.mcp_user_tree', function (require) {
    "use strict";

    var ListController = require('web.ListController');
    var core = require('web.core');
    var _t = core._t;

    ListController.include({
        renderButtons: function () {
            this._super.apply(this, arguments);

            if (this.modelName !== 'ai.mcp.user') {
                return;
            }

            if (!this.$buttons || typeof this.$buttons !== 'object' || !this.$buttons.length) {
                return;
            }

            const self = this;

            const $toolsBtn = $('<button>', {
                type: 'button',
                class: 'btn btn-secondary o_mcp_btn_sm',
                html: "<i class='fa fa-cog'></i> " + _t("Tools"),
                title: _t("User Tools"),
                style: 'margin-left: 4px;',
                click: function () {
                    self.do_action('pns_ai_mcp.action_user_tools_wizard');
                },
            });

            self.$buttons.append($toolsBtn);
        },

        _onToggleBoolean: function (event) {
            if (this.modelName !== 'ai.mcp.user') {
                return this._super.apply(this, arguments);
            }

            var self = this;
            var result = this._super.apply(this, arguments);

            var fieldName = event.data && event.data.field && event.data.field.name;
            if (fieldName === 'is_mcp_manager') {
                if (result && typeof result.then === 'function') {
                    result.then(function() {
                        self.reload();
                    });
                }
            }

            return result;
        },
    });

    return {};
});
