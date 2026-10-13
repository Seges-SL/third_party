/**
 * Clear History and Tools buttons on the ai.log list (Odoo 14).
 *
 * SPDX-License-Identifier: Apache-2.0
 * Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
 */
odoo.define('pns_ai_mcp.mcp_log_tree', function (require) {
"use strict";

    var ListController = require('web.ListController');
    var ActionManager = require('web.ActionManager');
    var core = require('web.core');

    ListController.include({
        renderButtons: function ($node) {
            this._super.apply(this, arguments);
            
            // Only add the button for the ai.log model
            if (this.modelName === 'ai.log') {
                // Validaciones m├ís estrictas para evitar errores al duplicar pesta├▒as
                if (!this.$buttons || typeof this.$buttons !== 'object' || !this.$buttons.length) {
                    return;
                }
                
                // Verificar que $buttons tiene m├®todos jQuery
                if (typeof this.$buttons.prepend !== 'function') {
                    return;
                }
                
                var self = this;
                
                // Evitar duplicados eliminando el bot├│n previo
                this.$buttons.find('.o_mcp_log_delete_button').remove();
                
                var $deleteButton = $('<button>', {
                    class: 'btn btn-primary o_mcp_log_delete_button',
                    type: 'button',
                    text: 'Clear History',
                    title: 'Deletes the oldest logs, keeping the most recent ones. Can delete all or keep the N newest.',
                    click: function() {
                        self._onDeleteMenuClick();
                    }
                });
                
                try {
                    this.$buttons.prepend($deleteButton);
                } catch (e) {
                    console.warn('Error al añadir botón de borrar historial:', e);
                }

                // Operations button
                this.$buttons.find('.o_mcp_log_ops_button').remove();
                var $opsBtn = $('<button>', {
                    type: 'button',
                    class: 'btn btn-secondary o_mcp_btn_sm o_mcp_log_ops_button',
                    html: "<i class='fa fa-cog'></i> Tools",
                    title: "History tools",
                    style: 'margin-left: 4px;',
                    click: function () {
                        self.do_action('pns_ai_mcp.action_log_tools_wizard');
                    },
                });
                this.$buttons.append($opsBtn);
            }
        },

        on_attach_callback: function () {
            this._super.apply(this, arguments);
            if (this.modelName === 'ai.log') {
                this._mcpLogLegendReady();
            }
        },

        /**
         * Promise of the legend bar in the control panel (resolves true once
         * it is there). The usage chip lives inside that bar.
         */
        _mcpLogLegendReady: function () {
            var self = this;
            if (!this._mcpLogLegend) {
                this._mcpLogLegend = this._insertMcpLogLegend().then(function (done) {
                    if (!done) {
                        self._mcpLogLegend = null;
                    }
                    return done;
                });
            }
            return this._mcpLogLegend;
        },

        _insertMcpLogLegend: function () {
            if (this.modelName !== 'ai.log') {
                return Promise.resolve(false);
            }
            // La leyenda se inserta en el CONTROL PANEL (zona fija, sin scroll) y no
            // antes de la tabla: insertarla dentro del área con scroll generaba un
            // segundo scrollbar vertical. Así queda un único scroll (el de la lista).
            var $cp = $();
            if (this.$buttons && this.$buttons.length) {
                $cp = this.$buttons.closest('.o_control_panel');
            }
            if (!$cp.length) {
                $cp = this.$el.closest('.o_action_manager, .o_action').find('.o_control_panel').first();
            }
            if (!$cp.length) {
                return Promise.resolve(false);
            }
            // Idempotente: si ya existe la barra en este control panel, no duplicar.
            if ($cp.find('.o_mcp_log_legend_bar').length) {
                return Promise.resolve(true);
            }
            // FUENTE ÚNICA: el HTML lo genera el servidor (ai.log.render_flow_legend),
            // el mismo método que usa la ficha (form). Grid y form nunca divergen.
            return Promise.resolve(this._rpc({
                model: 'ai.log',
                method: 'render_flow_legend',
                args: ['grid'],
            })).then(function (html) {
                if (!html) {
                    return false;
                }
                if (!$cp.find('.o_mcp_log_legend_bar').length) {
                    $cp.append(html);
                }
                return true;
            }, function () {
                return false;
            });
        },
        
        _onDeleteMenuClick: function() {
            this.do_action('pns_ai_mcp.action_ai_log_delete_menu_window');
        },
    });

    // Interceptar cuando se ejecuta display_notification con next para recargar la vista de logs
    ActionManager.include({
        _executeClientAction: function (action, options) {
            var self = this;
            
            var result = this._super.apply(this, arguments);
            
            // Si es display_notification con next que recarga, cerrar wizard y recargar vista de logs
            if (action && action.tag === 'display_notification' && action.params && action.params.next) {
                if (action.params.next.tag === 'reload') {
                    // Cerrar wizard activo y recargar vista de logs
                    if (result && typeof result.then === 'function') {
                        result.then(function() {
                            // Cerrar di├ílogos activos (wizards)
                            if (self._dialogs && Array.isArray(self._dialogs)) {
                                var i = self._dialogs.length - 1;
                                while (i >= 0) {
                                    var dialog = self._dialogs[i];
                                    if (dialog && typeof dialog.close === 'function') {
                                        try {
                                            dialog.close();
                                        } catch (e) {
                                            console.warn('Error al cerrar di├ílogo:', e);
                                        }
                                        break;
                                    }
                                    i--;
                                }
                            }

                            // Buscar y recargar controladores de logs
                            if (self._controllers && Array.isArray(self._controllers)) {
                                for (var j = 0; j < self._controllers.length; j++) {
                                    var controller = self._controllers[j];
                                    if (controller && controller.modelName === 'ai.log' && typeof controller.reload === 'function') {
                                        try {
                                            controller.reload();
                                        } catch (e) {
                                            console.warn('Error al recargar controlador:', e);
                                        }
                                    }
                                }
                            }

                            // Tambi├®n recargar el controlador actual si es de logs
                            try {
                                var currentController = self.getCurrentController && self.getCurrentController();
                                if (currentController && currentController.modelName === 'ai.log' && typeof currentController.reload === 'function') {
                                    currentController.reload();
                                }
                            } catch (e) {
                                console.warn('Error al obtener/recargar controlador actual:', e);
                            }
                        });
                    } else {
                        try {
                            var currentController = self.getCurrentController && self.getCurrentController();
                            if (currentController && currentController.modelName === 'ai.log' && typeof currentController.reload === 'function') {
                                currentController.reload();
                            }
                        } catch (e) {
                            console.warn('Error al obtener/recargar controlador actual:', e);
                        }
                    }
                }
            }
            
            return result;
        },
    });


    return {};
});

