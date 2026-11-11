/**
 * Tools button and flow legend on the ai.log list (Odoo 14).
 *
 * SPDX-License-Identifier: Apache-2.0
 * Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
 */
odoo.define('pns_ai_mcp.mcp_log_tree', function (require) {
"use strict";

    var ListController = require('web.ListController');
    var ListRenderer = require('web.ListRenderer');
    require('web.EditableListRenderer');
    var core = require('web.core');

    // O14 takes an absolute `width` from the arch only as a minimum, then
    // spreads the spare room over every column. O19 keeps it fixed.
    ListRenderer.include({
        _freezeColumnWidths: function () {
            this._super.apply(this, arguments);
            var cls = (this.arch && this.arch.attrs && this.arch.attrs.class) || '';
            if (cls.split(/\s+/).indexOf('o_mcp_log_tree') < 0) {
                return;
            }
            var self = this;
            this.columns.forEach(function (column) {
                var th = self._getColumnHeader(column);
                if (!th) {
                    return;
                }
                var width = column.attrs.width;
                if (width && /^\d+px$/.test(width)) {
                    var cs = window.getComputedStyle(th);
                    var px = (parseFloat(width) + parseFloat(cs.paddingLeft) + parseFloat(cs.paddingRight)) + 'px';
                    ['width', 'min-width', 'max-width'].forEach(function (prop) {
                        th.style.setProperty(prop, px, 'important');
                    });
                } else {
                    th.style.removeProperty('width');
                    th.style.removeProperty('max-width');
                }
            });
        },
    });

    ListController.include({
        renderButtons: function ($node) {
            this._super.apply(this, arguments);
            
            if (this.modelName === 'ai.log') {
                // Stricter checks to avoid errors when duplicating tabs
                if (!this.$buttons || typeof this.$buttons !== 'object' || !this.$buttons.length) {
                    return;
                }

                var self = this;

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
            // The legend goes into the CONTROL PANEL (fixed area, no scroll) and not
            // before the table: putting it inside the scrolling area created a
            // second vertical scrollbar. This way there is a single scroll (the list's).
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
            // Idempotent: if the bar already exists in this control panel, do not duplicate.
            if ($cp.find('.o_mcp_log_legend_bar').length) {
                return Promise.resolve(true);
            }
            // SINGLE SOURCE: the server builds the HTML (ai.log.render_flow_legend),
            // the same method the form uses. Grid and form never diverge.
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
    });

    return {};
});

