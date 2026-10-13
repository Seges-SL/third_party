/**
 * Tools button for the Approvals (safe_operation) list (Odoo 14).
 *
 * SPDX-License-Identifier: Apache-2.0
 * Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
 */
odoo.define('pns_ai_mcp.safe_operation_tree', function (require) {
    "use strict";

    var ListController = require('web.ListController');
    var core = require('web.core');
    var _t = core._t;

    var SafePlanHost = {
        _bindSafePlanBus: function () {
            var busService = this.env && this.env.services && this.env.services.bus_service;
            if (busService && typeof busService.on === 'function') {
                busService.on('notification', this, this._onSafePlanBus);
                if (busService.addChannel) {
                    busService.addChannel('partner');
                }
                if (busService.startPolling) {
                    busService.startPolling();
                }
                return;
            }
            try {
                this.call('bus_service', 'on', 'notification', this, this._onSafePlanBus);
                this.call('bus_service', 'addChannel', 'partner');
                this.call('bus_service', 'startPolling');
            } catch (e) { /* no bus in this client */ }
        },
        _reloadSafePlanView: function () {
            // Same client reload as the Confirm button (_notify_reload).
            if (this.do_action) {
                this.do_action({
                    type: 'ir.actions.client',
                    tag: 'reload',
                });
                return;
            }
            this.reload();
        },
        _onSafePlanBus: function (notifications) {
            if (this.modelName !== 'ai.safe.operation' || !notifications) {
                return;
            }
            var found = false;
            notifications.forEach(function (notif) {
                var payload = Array.isArray(notif) ? notif[1] : (notif && notif.payload);
                if (typeof payload === 'string') {
                    try {
                        var parsed = payload;
                        for (var i = 0; i < 3 && typeof parsed === 'string'; i++) {
                            parsed = JSON.parse(parsed);
                        }
                        payload = parsed;
                    } catch (e) { /* leftover bus wire format */ }
                }
                if (
                    (payload && payload.type === 'pns_safe_plan')
                    || (notif && notif.type === 'pns_safe_plan')
                ) {
                    found = true;
                }
            });
            if (found) {
                this._reloadSafePlanView();
            }
        },
    };

    ListController.include(Object.assign({}, SafePlanHost, {
        start: function () {
            var def = this._super.apply(this, arguments);
            if (this.modelName === 'ai.safe.operation') {
                this._bindSafePlanBus();
            }
            return def;
        },
        renderButtons: function () {
            this._super.apply(this, arguments);

            if (this.modelName !== 'ai.safe.operation') {
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
                title: _t("Authorization Tools"),
                style: 'margin-left: 4px;',
                click: function () {
                    self.do_action('pns_ai_mcp.action_safe_operation_tools_wizard');
                },
            });

            self.$buttons.append($toolsBtn);
        },
    }));
});
