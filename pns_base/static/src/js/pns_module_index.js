odoo.define('pns_base.pns_module_index', function (require) {
    "use strict";

    var AbstractField = require('web.AbstractField');
    var fieldRegistry = require('web.field_registry');

    var PnsModuleIndexWidget = AbstractField.extend({
        className: 'o_field_widget pns_module_index',
        supportedFieldTypes: ['char'],

        _render: function () {
            this.$el.empty();
            var url = this.value;
            if (!url) {
                return;
            }
            this.$el.append($('<iframe/>', {
                src: url,
                class: 'pns_module_index_iframe',
                frameborder: '0',
                title: 'Index',
            }));
        },
    });

    fieldRegistry.add('pns_module_index', PnsModuleIndexWidget);
    return PnsModuleIndexWidget;
});
