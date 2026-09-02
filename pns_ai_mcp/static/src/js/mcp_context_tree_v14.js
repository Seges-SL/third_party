// -*- coding: utf-8 -*-
// Archivo: static/src/js/mcp_context_tree.js
// Creado: 2025-11-24 13:16:51
// Modificado: 2026-01-26 (Force Update for Context Stats)
// Descripciín: Botones unificados para gestiín de contextos (Importar Mídulo, Importar ZIP, Exportar Todo)

odoo.define('pns_ai_mcp.mcp_context_tree', function (require) {
    "use strict";

    const ListController = require('web.ListController');
    const { _t } = require('web.core');

    ListController.include({
        renderButtons: function () {
            this._super.apply(this, arguments);

            if (this.modelName !== 'ai.context') {
                return;
            }
            
            if (!this.$buttons || typeof this.$buttons !== 'object' || !this.$buttons.length) {
                console.warn("MCP Context Tree: this.$buttons not ready or invalid", this.$buttons);
                return;
            }
            
            console.log("MCP Context Tree: Rendering Buttons (Debug Enabled)");
            const self = this;
            
            const $toolsBtn = $('<button>', {
                type: 'button',
                class: 'btn btn-secondary o_mcp_btn_sm',
                html: "<i class='fa fa-cog'></i> " + _t("Tools"),
                title: _t("Context Tools"),
                style: 'margin-left: 4px;',
                click: function () {
                    self.do_action('pns_ai_mcp.action_mcp_context_tools_wizard');
                },
            });

            self.$buttons.append($toolsBtn);
        },
    });
});


