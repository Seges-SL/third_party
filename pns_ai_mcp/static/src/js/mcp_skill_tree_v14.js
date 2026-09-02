// -*- coding: utf-8 -*-
// Archivo: static/src/js/mcp_skill_tree_v14.js
// Descripción: Botón unificado "Herramientas" para la gestión de skills (Odoo 14).
//              Equivalente a mcp_context_tree_v14.js pero para el modelo ai.skill.

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
