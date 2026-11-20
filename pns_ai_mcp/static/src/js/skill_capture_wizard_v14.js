/**
 * Skill capture wizard: stepped AI pass with typing dots (Odoo 14).
 *
 * SPDX-License-Identifier: Apache-2.0
 * Copyright (C) 2026 Patanegra Soft <https://patanegra.com>
 */
odoo.define('pns_ai_mcp.skill_capture_wizard', function (require) {
    "use strict";

    var FormController = require('web.FormController');
    var core = require('web.core');
    var _t = core._t;

    var MODEL = 'ai.skill.capture.wizard';

    function captureSteps() {
        return [
            {msg: _t('Reading the parameters…'), method: 'action_author_params'},
            {msg: _t('Writing the help text…'), method: 'action_author_help'},
            {msg: _t('Checking the Code…'), method: 'action_adapt_code'},
            {msg: _t('Saving the skill…'), method: 'action_create_draft'},
        ];
    }

    function usageHasTokens(usage) {
        if (!usage || typeof usage !== 'object') {
            return false;
        }
        var keys = [
            'prompt_tokens', 'completion_tokens', 'total_tokens',
            'input_tokens', 'output_tokens',
        ];
        return keys.some(function (key) {
            return Number(usage[key]) > 0;
        });
    }

    function formatUsageChip(usage) {
        if (!usageHasTokens(usage)) {
            return '';
        }
        var total = Number(usage.total_tokens) ||
            ((Number(usage.prompt_tokens) || 0) + (Number(usage.completion_tokens) || 0));
        var label = (total / 1024).toFixed(2) + 'k';
        var raw = usage.cost;
        if (raw === undefined || raw === null || raw === '') {
            return label;
        }
        var n = Number(raw);
        if (!isFinite(n) || n < 0) {
            return label;
        }
        var costLabel;
        try {
            costLabel = new Intl.NumberFormat(undefined, {
                style: 'currency',
                currency: 'USD',
                minimumFractionDigits: n === 0 || n >= 0.01 ? 2 : 4,
                maximumFractionDigits: n === 0 ? 2 : (n >= 0.01 ? 4 : 6),
            }).format(n);
        } catch (err) {
            costLabel = 'USD ' + (n === 0 ? n.toFixed(2) : n.toFixed(4));
        }
        return label + ' · ' + costLabel;
    }

    FormController.include({
        _onButtonClicked: function (ev) {
            var attrs = ev.data && ev.data.attrs;
            if (this.modelName === MODEL
                    && attrs && attrs.name === 'action_create_draft') {
                ev.stopPropagation();
                this._pnsSkillCaptureCommit();
                return;
            }
            return this._super.apply(this, arguments);
        },

        _pnsSkillCaptureProgressEls: function () {
            var $root = this.$el.closest('.modal');
            if (!$root.length) {
                $root = this.$el;
            }
            return {
                box: $root.find('.o_skill_capture_progress'),
                dots: $root.find('.o_skill_capture_typing'),
                label: $root.find('.o_skill_capture_progress_label'),
                usage: $root.find('.o_skill_capture_usage'),
                stop: $root.find('.o_skill_capture_stop'),
                stopLabel: $root.find('.o_skill_capture_stop_label'),
                buttons: $root.find('footer button'),
            };
        },

        _pnsSkillCaptureBindStop: function () {
            var self = this;
            var els = this._pnsSkillCaptureProgressEls();
            if (!els.stop.length || els.stop.data('pnsBound')) {
                return;
            }
            els.stop.data('pnsBound', true);
            els.stop.on('click', function (ev) {
                ev.preventDefault();
                ev.stopPropagation();
                self._pnsCaptureAborted = true;
            });
        },

        _pnsSkillCaptureSetUsage: function (usage) {
            var els = this._pnsSkillCaptureProgressEls();
            var text = formatUsageChip(usage);
            if (!text) {
                els.usage.hide().text('');
                return;
            }
            els.usage.text(text).show();
        },

        _pnsSkillCaptureSetBusy: function (busy, message) {
            var els = this._pnsSkillCaptureProgressEls();
            els.stopLabel.text(_t('Cancel'));
            if (busy) {
                els.box.css('display', 'flex');
                els.dots.show();
                els.stop.show().prop('disabled', false);
                if (message) {
                    els.label.text(message);
                }
                els.buttons.not('.o_skill_capture_stop').prop('disabled', true);
            } else {
                els.box.hide();
                els.dots.hide();
                els.stop.hide().prop('disabled', true);
                els.buttons.prop('disabled', false);
            }
        },

        _pnsSkillCaptureSetCancelled: function () {
            var els = this._pnsSkillCaptureProgressEls();
            els.box.css('display', 'flex');
            els.dots.hide();
            els.stop.hide().prop('disabled', true);
            els.label.text(_t('Cancelled.'));
            els.buttons.prop('disabled', false);
        },

        _pnsSkillCaptureCommit: function () {
            var self = this;
            if (this._pnsCaptureBusy) {
                return;
            }
            this._pnsCaptureBusy = true;
            this._pnsCaptureAborted = false;
            this._pnsSkillCaptureBindStop();
            this._pnsSkillCaptureSetUsage({});
            this._pnsSkillCaptureSetBusy(true, _t('Keeping your edits…'));
            return this.saveRecord().then(function () {
                if (self._pnsCaptureAborted) {
                    self._pnsSkillCaptureSetCancelled();
                    return undefined;
                }
                var rec = self.model.get(self.handle);
                var id = rec && rec.res_id;
                if (!id) {
                    throw new Error(_t('Could not save the wizard.'));
                }
                var ctx = rec.getContext ? rec.getContext() : {};
                var steps = captureSteps();
                var run = function (i) {
                    if (self._pnsCaptureAborted) {
                        self._pnsSkillCaptureSetCancelled();
                        return undefined;
                    }
                    if (i >= steps.length) {
                        return undefined;
                    }
                    var step = steps[i];
                    self._pnsSkillCaptureSetBusy(true, step.msg);
                    var params = {
                        model: MODEL,
                        method: step.method,
                        args: [id],
                    };
                    if (step.method === 'action_create_draft') {
                        params.context = Object.assign({}, ctx, {
                            skill_capture_authored: true,
                        });
                    }
                    return self._rpc(params, {shadow: true}).then(function (action) {
                        if (action && !action.type && action.usage) {
                            self._pnsSkillCaptureSetUsage(action.usage);
                        }
                        if (self._pnsCaptureAborted && !(action && action.type)) {
                            self._pnsSkillCaptureSetCancelled();
                            return undefined;
                        }
                        if (i === steps.length - 1) {
                            return action;
                        }
                        return run(i + 1);
                    });
                };
                return run(0);
            }).then(function (action) {
                self._pnsCaptureBusy = false;
                if (self._pnsCaptureAborted && !(action && action.type)) {
                    return undefined;
                }
                if (action && action.type) {
                    return self.do_action(action);
                }
                return undefined;
            }).guardedCatch(function () {
                self._pnsCaptureBusy = false;
                self._pnsSkillCaptureSetBusy(false);
            });
        },
    });
});
