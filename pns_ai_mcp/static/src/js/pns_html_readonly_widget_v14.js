/**
 * Readonly HTML field without loading web_editor / WYSIWYG (Odoo 14).
 *
 * SPDX-License-Identifier: Apache-2.0
 * Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
 */
odoo.define('pns_ai_mcp.pns_html_readonly_widget', function (require) {
    "use strict";

    var AbstractField = require('web.AbstractField');
    var fieldRegistry = require('web.field_registry');

    var DROP_TAGS = 'script,iframe,frame,object,embed,link,meta,base,form';
    var URL_ATTRS = /^(href|src|xlink:href|action|formaction)$/;
    var BAD_URL = /^(javascript|vbscript|data):/;

    // Parsed in an inert <template>: nothing runs while it is cleaned.
    function withoutActiveContent(html) {
        var tpl = document.createElement('template');
        tpl.innerHTML = html || '';
        var dropped = tpl.content.querySelectorAll(DROP_TAGS);
        for (var i = 0; i < dropped.length; i++) {
            dropped[i].remove();
        }
        var all = tpl.content.querySelectorAll('*');
        for (var j = 0; j < all.length; j++) {
            var attrs = Array.prototype.slice.call(all[j].attributes);
            for (var k = 0; k < attrs.length; k++) {
                var name = attrs[k].name.toLowerCase();
                var value = (attrs[k].value || '')
                    .replace(/[\s\u0000-\u001f]/g, '').toLowerCase();
                var badUrl = URL_ATTRS.test(name) && BAD_URL.test(value)
                    && !/^data:image\//.test(value);
                if (name.indexOf('on') === 0 || badUrl || name === 'srcdoc') {
                    all[j].removeAttribute(attrs[k].name);
                }
            }
        }
        return tpl.innerHTML;
    }

    var PnsHtmlReadonlyWidget = AbstractField.extend({
        className: 'o_field_html o_readonly pns_html_readonly',
        supportedFieldTypes: ['html', 'text'],

        _renderReadonly: function () {
            this.$el.html(withoutActiveContent(this.value));
        },
    });

    fieldRegistry.add('pns_html_readonly', PnsHtmlReadonlyWidget);

    return PnsHtmlReadonlyWidget;
});
