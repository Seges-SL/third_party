odoo.define('pns_ai_mcp.pns_html_readonly_widget', function (require) {
    "use strict";

    var AbstractField = require('web.AbstractField');
    var fieldRegistry = require('web.field_registry');

    var PnsHtmlReadonlyWidget = AbstractField.extend({
        className: 'o_field_html o_readonly pns_html_readonly',
        supportedFieldTypes: ['html', 'text'],

        _renderReadonly: function () {
            this.$el.html(this.value || '');
        },
    });

    fieldRegistry.add('pns_html_readonly', PnsHtmlReadonlyWidget);

    return PnsHtmlReadonlyWidget;
});
