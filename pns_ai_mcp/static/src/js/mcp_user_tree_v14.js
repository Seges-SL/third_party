/**
 * Tools button, key-list refresh and chip for MCP Users (Odoo 14).
 *
 * SPDX-License-Identifier: Apache-2.0
 * Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
 */
odoo.define('pns_ai_mcp.mcp_user_tree', function (require) {
    "use strict";

    var ListController = require('web.ListController');
    var FormController = require('web.FormController');
    var core = require('web.core');
    var _t = core._t;

    var VAULT = 'pns.key.pin.vault';

    function heldCount() {
        if (typeof window.pnsKeyPinHeldCount === 'function') {
            return window.pnsKeyPinHeldCount() || 0;
        }
        try {
            return Object.keys(JSON.parse(sessionStorage.getItem(VAULT) || '{}')).length;
        } catch (e) {
            return 0;
        }
    }

    function paintToolbarChip(controller) {
        if (!controller.$buttons || !controller.$buttons.length) {
            return;
        }
        var count = heldCount();
        var $chip = controller.$buttons.find('.o_mcp_key_pin_held_chip');
        if (!count) {
            $chip.remove();
            return;
        }
        var label = _t('This tab is holding keys:') + ' ' + count;
        if (!$chip.length) {
            $chip = $('<button>', {
                type: 'button',
                class: 'btn btn-primary o_mcp_btn_sm o_mcp_key_pin_held_chip o_mcp_key_pin_open',
                title: _t('This browser tab is holding the key list in session storage. Click to open it.'),
            });
            controller.$buttons.append($chip);
        }
        $chip.html("<i class='fa fa-key'></i> " + label);
    }

    function refreshAfterPin() {
        return {
            start: function () {
                var self = this;
                var onChanged = function () {
                    if (self.modelName === 'ai.mcp.user') {
                        self.reload().then(function () {
                            paintToolbarChip(self);
                        });
                    }
                };
                this._pnsKeyPinOnChanged = onChanged;
                core.bus.on('pns_key_pin_changed', this, onChanged);
                return this._super.apply(this, arguments);
            },
            destroy: function () {
                if (this._pnsKeyPinOnChanged) {
                    core.bus.off('pns_key_pin_changed', this, this._pnsKeyPinOnChanged);
                    this._pnsKeyPinOnChanged = null;
                }
                return this._super.apply(this, arguments);
            },
        };
    }

    ListController.include(refreshAfterPin());
    FormController.include(refreshAfterPin());

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

            if (!this.$buttons.find('.o_mcp_btn_tools').length) {
                const $toolsBtn = $('<button>', {
                    type: 'button',
                    class: 'btn btn-secondary o_mcp_btn_sm o_mcp_btn_tools',
                    html: "<i class='fa fa-cog'></i> " + _t("Tools"),
                    title: _t("User Tools"),
                    style: 'margin-left: 4px;',
                    click: function () {
                        self.do_action('pns_ai_mcp.action_user_tools_wizard');
                    },
                });
                self.$buttons.append($toolsBtn);
            }
            paintToolbarChip(self);
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
