/**
 * Field widget: show an API key and copy it to the clipboard (Odoo 14).
 *
 * SPDX-License-Identifier: Apache-2.0
 * Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
 */
odoo.define('pns_ai_mcp.mcp_api_key_widget', function (require) {
    "use strict";

    var AbstractField = require('web.AbstractField');
    var field_registry = require('web.field_registry');
    var core = require('web.core');

    var _t = core._t;

    var MCPApiKeyWidget = AbstractField.extend({
        className: 'o_field_mcp_api_key',
        supportedFieldTypes: ['char'],
        
        _render: function () {
            var self = this;
            
            // Call the parent method to make sure this.$el is initialized
            this._super.apply(this, arguments);
            
            if (!this.$el || !this.$el.length) {
                return;
            }
            
            this.$el.empty();
            
            // Flex container
            var $container = $('<div>', {
                class: 'd-flex align-items-center'
            });
            
            // Action buttons when there is a value (on the left)
            if (this.value) {
                // Copy button
                var $copyButton = $('<button>', {
                    class: 'btn btn-sm btn-link',
                    title: _t('Copy to clipboard')
                }).append($('<i>', {
                    class: 'fa fa-copy'
                }));
                
                $copyButton.on('click', function(ev) {
                    ev.preventDefault();
                    ev.stopPropagation();
                    navigator.clipboard.writeText(self.value).then(function() {
                        self.displayNotification({
                            type: 'success',
                            title: _t('Success'),
                            message: _t('MCP API Key copied to clipboard'),
                        });
                    }).catch(function() {
                        self.displayNotification({
                            type: 'danger',
                            title: _t('Error'),
                            message: _t('Error copying the MCP API Key'),
                        });
                    });
                });
                
                $container.append($copyButton);
            }
            
            // Span for the value (right of the button)
            var $value = $('<span>', {
                class: 'flex-grow-1',
                text: this.value || _t('No API Key')
            });
            
            $container.append($value);
            
            this.$el.append($container);
        },
    });

    field_registry.add('mcp_api_key_display', MCPApiKeyWidget);
    
    return MCPApiKeyWidget;
});

