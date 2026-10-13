/**
 * Tools button for the Skills list (Odoo 14).
 *
 * SPDX-License-Identifier: Apache-2.0
 * Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
 */
odoo.define('pns_ai_mcp.mcp_skill_tree', function (require) {
    "use strict";

    const ListController = require('web.ListController');
    const { _t } = require('web.core');

    ListController.include({
        renderButtons: function () {
            this._super.apply(this, arguments);

            if (this.modelName !== 'ai.skill') {
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
                title: _t("Skill Tools"),
                style: 'margin-left: 4px;',
                click: function () {
                    self.do_action('pns_ai_mcp.action_ai_skill_tools_wizard');
                },
            });

            self.$buttons.append($toolsBtn);
        },
    });
});
