/**
 * Spend chip on the Activity legend bar (tokens · money), Odoo 14.
 *
 * SPDX-License-Identifier: Apache-2.0
 * Copyright (C) 2026 Patanegra Soft <https://patanegra.com>
 */
odoo.define('pns_ai_mcp.mcp_log_usage_summary', function (require) {
    "use strict";

    var ListController = require('web.ListController');

    var MODEL = 'ai.log';
    var CHIP_TITLE = 'Tokens and cost for the current filter';

    function controlPanel(controller) {
        var $cp = $();
        if (controller.$buttons && controller.$buttons.length) {
            $cp = controller.$buttons.closest('.o_control_panel');
        }
        if (!$cp.length && controller.$el) {
            $cp = controller.$el.closest('.o_action_manager, .o_action')
                .find('.o_control_panel').first();
        }
        return $cp;
    }

    function paintChip($scope, summary) {
        if (!$scope || !$scope.length) {
            return false;
        }
        var $chip = $scope.find('.o_mcp_log_usage_chip').first();
        if (!$chip.length) {
            return false;
        }
        if (!summary || !summary.spend_label) {
            $chip.text('').attr('hidden', 'hidden');
            return true;
        }
        $chip.text(summary.spend_label)
            .attr('title', CHIP_TITLE)
            .removeAttr('hidden');
        $scope.find('.o_ai_usage_summary_banner').remove();
        return true;
    }

    ListController.include({
        _pnsListDomain: function () {
            if (this.renderer && this.renderer.state && this.renderer.state.domain) {
                return this.renderer.state.domain;
            }
            return this.domain || [];
        },

        _pnsLoadUsageSummary: function () {
            if (this.modelName !== MODEL) {
                return;
            }
            var self = this;
            var seq = (this._pnsUsageSeq || 0) + 1;
            this._pnsUsageSeq = seq;
            var summary = this._rpc({
                model: MODEL,
                method: 'get_user_usage_summary',
                args: [],
                kwargs: { domain: this._pnsListDomain() },
            });
            Promise.all([summary, this._mcpLogLegendReady()]).then(function (res) {
                if (seq === self._pnsUsageSeq) {
                    paintChip(controlPanel(self), res[0]);
                }
            }, function () {
                /* optional chip */
            });
        },

        on_attach_callback: function () {
            this._super.apply(this, arguments);
            this._pnsLoadUsageSummary();
        },

        update: function (state, params) {
            var self = this;
            return this._super.apply(this, arguments).then(function () {
                self._pnsLoadUsageSummary();
            });
        },
    });
});
