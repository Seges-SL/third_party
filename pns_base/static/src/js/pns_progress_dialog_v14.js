/* SPDX-License-Identifier: Apache-2.0
 * Copyright (C) 2026 Patanegra Soft <https://patanegra.com>
 */
odoo.define('pns_base.progress_dialog', function (require) {
'use strict';

// Follows a pns.progress.job: live step and bar, then the summary the job wrote.

var AbstractAction = require('web.AbstractAction');
var core = require('web.core');

var QWeb = core.qweb;

var POLL_MS = 800;
var RETRY_MS = 3000;

var PnsProgressDialog = AbstractAction.extend({
    template: 'pns_base.ProgressDialog',
    events: {
        'click .o_pns_progress_close': '_onClose',
        'click .o_pns_progress_done': '_onDone',
    },

    init: function (parent, action) {
        this._super.apply(this, arguments);
        var params = action.params || {};
        this.jobId = params.job_id;
        this.doneAction = params.done_action || false;
        this.doneLabel = params.done_label || '';
        this.data = null;
    },

    start: function () {
        var self = this;
        return this._super.apply(this, arguments).then(function () {
            self._render();
            self._poll();
        });
    },

    destroy: function () {
        this._stopped = true;
        clearTimeout(this._timer);
        this._super.apply(this, arguments);
    },

    _running: function () {
        return !this.data || this.data.state === 'queued' || this.data.state === 'running';
    },

    _render: function () {
        this.$('.o_pns_progress_body').html(QWeb.render('pns_base.ProgressDialogBody', {
            data: this.data,
            running: this._running(),
            doneAction: this.doneAction,
            doneLabel: this.doneLabel,
        }));
    },

    _poll: function () {
        var self = this;
        if (this._stopped || !this.jobId) {
            return;
        }
        this._rpc({
            model: 'pns.progress.job',
            method: 'read_progress',
            args: [[this.jobId]],
        }, {shadow: true}).then(function (data) {
            if (self._stopped) {
                return;
            }
            self.data = data;
            self._render();
            if (self._running()) {
                self._timer = setTimeout(self._poll.bind(self), POLL_MS);
            }
        }).guardedCatch(function () {
            if (!self._stopped) {
                self._timer = setTimeout(self._poll.bind(self), RETRY_MS);
            }
        });
    },

    _onClose: function () {
        this.do_action({type: 'ir.actions.act_window_close'});
    },

    _onDone: function () {
        this.do_action(this.doneAction);
    },
});

core.action_registry.add('pns_progress_dialog', PnsProgressDialog);

return PnsProgressDialog;
});
