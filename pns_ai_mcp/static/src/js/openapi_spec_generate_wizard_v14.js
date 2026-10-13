/**
 * OpenAPI spec wizard: stepped fetch + LLM conversion (Odoo 14).
 *
 * SPDX-License-Identifier: Apache-2.0
 * Copyright (C) 2026 Patanegra Soft <https://patanegra.com>
 */
odoo.define('pns_ai_mcp.openapi_spec_generate_wizard', function (require) {
    "use strict";

    var FormController = require('web.FormController');
    var core = require('web.core');
    var _t = core._t;

    var MODEL = 'ai.openapi.spec.generate.wizard';
    var CANCEL_CONFIRM = _t(
        'Cancel OpenAPI generation? Stop the conversion in progress? Usage so far will be saved in AI Logs.'
    );
    var CANCEL_WAITING = _t(
        'Cancelling… waiting for the current AI call to finish.'
    );
    var CONVERTING_MSG = _t(
        'Converting with AI Admin…'
    );

    function openapiSteps() {
        return [
            {
                msg: _t('Fetching documentation…'),
                method: 'action_fetch_documentation',
            },
            {
                msg: CONVERTING_MSG,
                method: 'action_generate_openapi',
            },
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

    function addUsage(acc, piece) {
        var out = Object.assign({}, acc || {});
        var src = piece || {};
        ['prompt_tokens', 'completion_tokens', 'total_tokens', 'cached_tokens'].forEach(function (key) {
            var n = Number(src[key]) || 0;
            if (n) {
                out[key] = (Number(out[key]) || 0) + n;
            }
        });
        if (src.cost !== undefined && src.cost !== null && src.cost !== '') {
            var c = Number(src.cost);
            if (isFinite(c)) {
                out.cost = (Number(out.cost) || 0) + c;
            }
        }
        return out;
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

    function isFooterCancelButton($btn) {
        if (!$btn || !$btn.length) {
            return false;
        }
        if ($btn.hasClass('o_skill_capture_stop')) {
            return false;
        }
        var special = ($btn.attr('special') || '').toLowerCase();
        if (special === 'cancel') {
            return true;
        }
        // O14 often renders special=cancel without keeping the attr on the DOM node.
        var name = ($btn.attr('name') || '').toLowerCase();
        if (name === 'action_generate' || name === 'action_apply'
                || name === 'action_abort_openapi') {
            return false;
        }
        var text = ($btn.text() || '').replace(/\s+/g, ' ').trim().toLowerCase();
        return text === 'cancel' || text === 'cancelar'
            || text === 'close' || text === 'cerrar';
    }

    FormController.include({
        _onButtonClicked: function (ev) {
            var attrs = ev.data && ev.data.attrs;
            if (this.modelName === MODEL
                    && attrs && attrs.name === 'action_generate') {
                ev.stopPropagation();
                this._pnsOpenapiGenerate();
                return;
            }
            if (this.modelName === MODEL && this._pnsOpenapiBusy) {
                var $target = $(ev.target).closest('button');
                var isCancel = isFooterCancelButton($target)
                    || (attrs && (attrs.special === 'cancel'
                        || String(attrs.special || '').toLowerCase() === 'cancel'));
                if (isCancel) {
                    if (this._pnsOpenapiAborted) {
                        // Already aborting: let special=cancel close the dialog.
                        this._pnsOpenapiBusy = false;
                        return this._super.apply(this, arguments);
                    }
                    ev.stopPropagation();
                    this._pnsOpenapiRequestCancel();
                    return;
                }
            }
            return this._super.apply(this, arguments);
        },

        _pnsOpenapiProgressEls: function () {
            var $root = this.$el.closest('.modal');
            if (!$root.length) {
                $root = this.$el;
            }
            return {
                root: $root,
                box: $root.find('.o_skill_capture_progress'),
                dots: $root.find('.o_skill_capture_typing'),
                label: $root.find('.o_skill_capture_progress_label'),
                usage: $root.find('.o_skill_capture_usage'),
                stop: $root.find('.o_skill_capture_stop'),
                stopLabel: $root.find('.o_skill_capture_stop_label'),
                buttons: $root.find('footer button'),
            };
        },

        _pnsOpenapiConfirmCancel: function () {
            return window.confirm(CANCEL_CONFIRM);
        },

        _pnsOpenapiCloseWizard: function () {
            this._pnsOpenapiBusy = false;
            return this.do_action({type: 'ir.actions.act_window_close'});
        },

        _pnsOpenapiMarkAborting: function () {
            this._pnsOpenapiAborted = true;
            var els = this._pnsOpenapiProgressEls();
            els.dots.hide();
            els.label.text(CANCEL_WAITING);
            els.stop.prop('disabled', true);
            // Footer Cancel must close the wizard (not re-prompt).
            els.buttons.filter(function () {
                return isFooterCancelButton($(this));
            }).prop('disabled', false);
        },

        _pnsOpenapiRequestCancel: function () {
            var self = this;
            if (this._pnsOpenapiAborted) {
                return this._pnsOpenapiCloseWizard();
            }
            if (!this._pnsOpenapiConfirmCancel()) {
                return;
            }
            this._pnsOpenapiMarkAborting();
            var wizardId = this._pnsOpenapiWizardId;
            var usage = this._pnsOpenapiUsage;
            return this._pnsOpenapiLogUsage(
                wizardId, usage, 'cancelled'
            ).then(function () {
                return self._pnsOpenapiCloseWizard();
            });
        },

        _pnsOpenapiBindStop: function () {
            var self = this;
            var els = this._pnsOpenapiProgressEls();
            if (!els.stop.length) {
                return;
            }
            // Re-bind every busy cycle (modal DOM may be recreated).
            els.stop.off('click.pnsOpenapiStop');
            els.stop.on('click.pnsOpenapiStop', function (ev) {
                ev.preventDefault();
                ev.stopPropagation();
                self._pnsOpenapiRequestCancel();
            });
            els.root.off('click.pnsOpenapiFooterCancel');
            els.root.on('click.pnsOpenapiFooterCancel', 'footer button', function (ev) {
                if (!self._pnsOpenapiBusy) {
                    return;
                }
                var $btn = $(this);
                if (!isFooterCancelButton($btn)) {
                    return;
                }
                if (self._pnsOpenapiAborted) {
                    // Let Odoo special=cancel close; do not block.
                    return;
                }
                ev.preventDefault();
                ev.stopPropagation();
                self._pnsOpenapiRequestCancel();
            });
        },

        _pnsOpenapiSetUsage: function (usage) {
            var els = this._pnsOpenapiProgressEls();
            var text = formatUsageChip(usage);
            if (!text) {
                els.usage.hide().text('');
                return;
            }
            els.usage.text(text).show();
        },

        _pnsOpenapiSetBusy: function (busy, message) {
            var els = this._pnsOpenapiProgressEls();
            els.stopLabel.text(_t('Cancel'));
            if (busy) {
                els.box.css('display', 'flex');
                if (!this._pnsOpenapiAborted) {
                    els.dots.show();
                    els.stop.show().prop('disabled', false);
                }
                if (message) {
                    els.label.text(message);
                }
                els.buttons.not('.o_skill_capture_stop').prop('disabled', true);
                // Keep footer Cancel clickable so the user can confirm-abort.
                els.buttons.filter(function () {
                    return isFooterCancelButton($(this));
                }).prop('disabled', false);
                this._pnsOpenapiBindStop();
            } else {
                els.box.hide();
                els.dots.hide();
                els.stop.hide().prop('disabled', true);
                els.buttons.prop('disabled', false);
            }
        },

        _pnsOpenapiSetCancelled: function () {
            var els = this._pnsOpenapiProgressEls();
            els.box.css('display', 'flex');
            els.dots.hide();
            els.stop.hide().prop('disabled', true);
            els.label.text(_t('Cancelled.'));
            els.buttons.prop('disabled', false);
        },

        _pnsOpenapiLogUsage: function (id, usage, status) {
            if (!id || !usageHasTokens(usage)) {
                return Promise.resolve();
            }
            return this._rpc({
                model: MODEL,
                method: 'action_log_generation_usage',
                args: [id],
                kwargs: {usage: usage, status: status},
            }, {shadow: true}).guardedCatch(function () {
                return undefined;
            });
        },

        _pnsOpenapiGenerate: function () {
            var self = this;
            if (this._pnsOpenapiBusy) {
                return;
            }
            this._pnsOpenapiBusy = true;
            this._pnsOpenapiAborted = false;
            this._pnsOpenapiUsage = {};
            this._pnsOpenapiWizardId = null;
            this._pnsOpenapiBindStop();
            this._pnsOpenapiSetUsage({});
            this._pnsOpenapiSetBusy(true, _t('Saving…'));
            var wizardId = null;
            return this.saveRecord().then(function () {
                if (self._pnsOpenapiAborted) {
                    return self._pnsOpenapiCloseWizard();
                }
                var rec = self.model.get(self.handle);
                wizardId = rec && rec.res_id;
                self._pnsOpenapiWizardId = wizardId;
                if (!wizardId) {
                    throw new Error(_t('Could not save the wizard.'));
                }
                var steps = openapiSteps();
                var run = function (i) {
                    if (self._pnsOpenapiAborted) {
                        // Confirm already logged usage and closed the dialog.
                        return Promise.resolve(undefined);
                    }
                    if (i >= steps.length) {
                        return undefined;
                    }
                    var step = steps[i];
                    self._pnsOpenapiSetBusy(true, step.msg);
                    return self._rpc({
                        model: MODEL,
                        method: step.method,
                        args: [wizardId],
                    }, {shadow: true}).then(function (result) {
                        if (self._pnsOpenapiAborted) {
                            return undefined;
                        }
                        if (result && !result.type && result.usage) {
                            self._pnsOpenapiUsage = addUsage(
                                self._pnsOpenapiUsage, result.usage);
                            self._pnsOpenapiSetUsage(self._pnsOpenapiUsage);
                        }
                        if (self._pnsOpenapiAborted) {
                            return undefined;
                        }
                        if (result && result.ok === false) {
                            var after = Promise.resolve();
                            if (result.reload) {
                                after = self.reload();
                            }
                            return after.then(function () {
                                self._pnsOpenapiSetBusy(false);
                                return {_halt: true};
                            });
                        }
                        if (i === steps.length - 1) {
                            return result;
                        }
                        return run(i + 1);
                    });
                };
                return run(0);
            }).then(function (result) {
                if (self._pnsOpenapiAborted || (result && result._halt)) {
                    return undefined;
                }
                if (result && result.reload) {
                    return self.reload().then(function () {
                        self._pnsOpenapiSetBusy(false);
                    });
                }
                self._pnsOpenapiSetBusy(false);
                return undefined;
            }).guardedCatch(function () {
                if (self._pnsOpenapiAborted) {
                    self._pnsOpenapiBusy = false;
                    return undefined;
                }
                return self._pnsOpenapiLogUsage(
                    wizardId, self._pnsOpenapiUsage, 'error'
                ).then(function () {
                    return self.reload();
                }).then(function () {
                    self._pnsOpenapiBusy = false;
                    self._pnsOpenapiSetBusy(false);
                }).guardedCatch(function () {
                    self._pnsOpenapiBusy = false;
                    self._pnsOpenapiSetBusy(false);
                });
            }).then(function () {
                self._pnsOpenapiBusy = false;
            });
        },
    });
});
