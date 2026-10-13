/* SPDX-License-Identifier: Apache-2.0
 * Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
 *
 * Deduplicate invalid-field names in the form/list error toast.
 */
odoo.define('pns_base.invalid_fields_dedupe', function (require) {
    "use strict";

    var BasicController = require('web.BasicController');
    var core = require('web.core');
    var _t = core._t;

    function uniqueNames(names) {
        var seen = {};
        var out = [];
        (names || []).forEach(function (name) {
            if (name && !seen[name]) {
                seen[name] = true;
                out.push(name);
            }
        });
        return out;
    }

    function isEmptyValue(value) {
        if (value === false || value === null || value === undefined || value === '') {
            return true;
        }
        if (_.isArray(value) && !value[0]) {
            return true;
        }
        return false;
    }

    function requiredTitle(labels) {
        var unique = uniqueNames(labels);
        var joined = unique.join(', ');
        if (unique.length === 1) {
            return _.str.sprintf(_t('Required field: %s'), joined);
        }
        return _.str.sprintf(_t('Required fields: %s'), joined);
    }

    BasicController.include({
        _pnsNotifyRecord: function () {
            var record;
            try {
                record = this.model.get(this.handle, {raw: true});
            } catch (e) {
                return null;
            }
            if (record && record.type === 'list' && this.renderer &&
                    this.renderer.getEditableRecordID) {
                var editedId = this.renderer.getEditableRecordID();
                if (editedId) {
                    return this.model.get(editedId, {raw: true});
                }
            }
            return record;
        },
        _pnsFieldLabels: function (names) {
            var record = this._pnsNotifyRecord();
            var fields = (record && record.fields) || {};
            return names.map(function (name) {
                return (fields[name] && fields[name].string) || name;
            });
        },
        _pnsAllEmpty: function (names) {
            var record = this._pnsNotifyRecord();
            if (!record || record.type === 'list') {
                return true;
            }
            var data = record.data || {};
            return names.every(function (name) {
                return isEmptyValue(data[name]);
            });
        },
        _pnsNotifyRequiredFields: function (labels) {
            var title = requiredTitle(labels);
            if (this.displayNotification) {
                this.displayNotification({
                    title: title,
                    type: 'danger',
                });
                return;
            }
            this.do_warn(title, '');
        },
        _notifyInvalidFields: function (invalidFields) {
            var names = uniqueNames(invalidFields);
            if (names.length && this._pnsAllEmpty(names)) {
                this._pnsNotifyRequiredFields(this._pnsFieldLabels(names));
                return;
            }
            return this._super(names);
        },
    });
});
