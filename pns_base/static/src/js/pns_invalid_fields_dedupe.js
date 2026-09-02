odoo.define('pns_base.invalid_fields_dedupe', function (require) {
    "use strict";

    var BasicController = require('web.BasicController');
    var ListController = require('web.ListController');
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

    ListController.include({
        /**
         * Multi-edit with no valid row: same toast as the form, not
         * «No valid record to save».
         */
        _saveMultipleRecords: function (recordId, node, changes) {
            var fieldName = Object.keys(changes)[0];
            var value = Object.values(changes)[0];
            var recordIds = _.union([recordId], this.selectedRecords);
            var self = this;
            var validRecordIds = recordIds.reduce(function (result, nextRecordId) {
                var record = self.model.get(nextRecordId);
                var modifiers = self.renderer._registerModifiers(node, record);
                var fieldType = record.fields[fieldName].type;
                if (!modifiers.readonly && (!modifiers.required || self._isValueSet(fieldType, value))) {
                    result.push(nextRecordId);
                }
                return result;
            }, []);
            if (validRecordIds.length > 0) {
                return this._super.apply(this, arguments);
            }
            var record = this.model.get(recordId);
            var label = (node.attrs && node.attrs.string) ||
                (record.fields[fieldName] && record.fields[fieldName].string) ||
                fieldName;
            this._pnsNotifyRequiredFields([label]);
            return new Promise(function (resolve, reject) {
                self.model.discardChanges(recordId);
                self._confirmSave(recordId).then(function () {
                    self.renderer.focusCell(recordId, node);
                    reject();
                });
            });
        },
        _onSetDirty: function (ev) {
            var recordId = ev.data.dataPointID;
            if (!this.renderer.isInMultipleRecordEdition(recordId)) {
                return this._super.apply(this, arguments);
            }
            ev.stopPropagation();
            var node = ev.target && ev.target.__node;
            var record = this.model.get(recordId);
            var fieldName = node && node.attrs && node.attrs.name;
            var label = (node && node.attrs && node.attrs.string) ||
                (fieldName && record.fields[fieldName] && record.fields[fieldName].string) ||
                fieldName;
            if (label) {
                this._pnsNotifyRequiredFields([label]);
            }
            var self = this;
            this.model.discardChanges(recordId);
            return this._confirmSave(recordId).then(function () {
                if (node) {
                    self.renderer.focusCell(recordId, node);
                }
            });
        },
    });
});
