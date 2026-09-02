odoo.define('pns_ai_mcp.mcp_iso_datetime_widget', function (require) {
    "use strict";

    var AbstractField = require('web.AbstractField');
    var fieldRegistry = require('web.field_registry');
    var fieldUtils = require('web.field_utils');

    var McpIsoDatetimeWidget = AbstractField.extend({
        className: 'o_field_mcp_iso_datetime',
        supportedFieldTypes: ['datetime'],

        _formatIso: function (value) {
            if (!value) {
                return '';
            }
            if (typeof value === 'string') {
                return value.trim().replace(' ', 'T').slice(0, 19);
            }
            if (value._isAMomentObject && value.isValid && value.isValid()) {
                return value.clone().utc().format('YYYY-MM-DDTHH:mm:ss');
            }
            try {
                var parsed = fieldUtils.parse.datetime(value);
                if (parsed && parsed._isAMomentObject) {
                    return parsed.clone().utc().format('YYYY-MM-DDTHH:mm:ss');
                }
            } catch (e) {
                // fall through
            }
            return String(value);
        },

        _render: function () {
            this._super.apply(this, arguments);
            if (!this.$el || !this.$el.length) {
                return;
            }
            this.$el.empty();
            this.$el.append($('<span>', {
                class: 'text-monospace',
                text: this._formatIso(this.value),
            }));
        },
    });

    fieldRegistry.add('mcp_iso_datetime', McpIsoDatetimeWidget);
});
