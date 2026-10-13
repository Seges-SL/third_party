/**
 * Show LLM usage chip after server detection suggest (Odoo 14).
 *
 * SPDX-License-Identifier: Apache-2.0
 * Copyright (C) 2026 Patanegra Soft <https://patanegra.com>
 */
odoo.define('pns_ai_mcp.external_server_usage', function (require) {
    "use strict";

    var FormController = require('web.FormController');
    var ListController = require('web.ListController');
    var UsageChip = require('pns_ai_mcp.ai_usage_chip');

    var MODEL = 'ai.api.server';

    function showServerUsage(controller, usage) {
        if (!usage) {
            return Promise.resolve();
        }
        var $root = controller.$el.closest('.o_content');
        if (!$root.length) {
            $root = controller.$el;
        }
        return UsageChip.setUsageElementsWithFx($root[0], usage);
    }

    function runSuggestDetection(controller, resIds) {
        return controller._rpc({
            model: MODEL,
            method: 'action_suggest_detection',
            args: [resIds],
        }).then(function (action) {
            if (action && action.usage) {
                return showServerUsage(controller, action.usage).then(function () {
                    return action;
                });
            }
            return action;
        }).then(function (action) {
            if (action && action.type) {
                return controller.do_action(action);
            }
        });
    }

    FormController.include({
        _onButtonClicked: function (ev) {
            var attrs = ev.data && ev.data.attrs;
            if (this.modelName === MODEL
                    && attrs && attrs.name === 'action_suggest_detection') {
                ev.stopPropagation();
                runSuggestDetection(this, [this.renderer.state.res_id]);
                return;
            }
            return this._super.apply(this, arguments);
        },
    });

    ListController.include({
        _onButtonClicked: function (ev) {
            var attrs = ev.data && ev.data.attrs;
            if (this.modelName === MODEL
                    && attrs && attrs.name === 'action_suggest_detection') {
                ev.stopPropagation();
                var self = this;
                this.getSelectedIds().then(function (ids) {
                    return runSuggestDetection(self, ids);
                });
                return;
            }
            return this._super.apply(this, arguments);
        },
    });
});
