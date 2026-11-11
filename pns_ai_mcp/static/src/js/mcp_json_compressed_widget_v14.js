/**
 * Compressed JSON field with expand and clipboard copy (Odoo 14).
 *
 * SPDX-License-Identifier: Apache-2.0
 * Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
 */
odoo.define('pns_ai_mcp.mcp_json_compressed_widget', function (require) {
    "use strict";

    var AbstractField = require('web.AbstractField');
    var fieldRegistry = require('web.field_registry');
    var core = require('web.core');

    var _t = core._t;

    var MCPJsonCompressedWidget = AbstractField.extend({
        className: 'o_field_mcp_json_compressed',
        supportedFieldTypes: ['char', 'text'],
        
        init: function() {
            this._super.apply(this, arguments);
            this._expanded = false;
        },
        
        _render: function() {
            var self = this;
            var compressedValue = this.value || '';
            
            // Clear previous content
            this.$el.empty();
            
            if (!compressedValue) {
                this.$el.text('');
                return;
            }
            
            // Clean escapes if the value has them (may come from double serialization)
            // Try to parse as a JSON string first
            try {
                var parsed = JSON.parse(compressedValue);
                if (typeof parsed === 'string') {
                    // If it is a JSON string, try to parse it again (double serialization)
                    try {
                        parsed = JSON.parse(parsed);
                    } catch (e) {
                        // If that fails, use the parsed string
                    }
                }
                // Serialize cleanly, with no needless escapes
                compressedValue = JSON.stringify(parsed, null, 0).replace(/\s+/g, ' ').trim();
            } catch (e) {
                // If it is not valid JSON, clean escapes by hand
                // First try to clean common escapes
                compressedValue = compressedValue
                    .replace(/\\n/g, ' ')
                    .replace(/\\"/g, '"')
                    .replace(/\\t/g, ' ')
                    .replace(/\\r/g, ' ')
                    .replace(/\\\\/g, '\\')  // Replace \\ with \
                    .replace(/\s+/g, ' ')
                    .trim();
            }
            
            // Main container - no inline width, so the column width is respected
            var $container = $('<div>', {
                class: 'mcp_json_container'
            });
            
            // Container for the compressed line (flex to push the button to the right)
            var $compressedLine = $('<div>', {
                css: {
                    'display': 'flex',
                    'align-items': 'center',
                    'width': '100%'
                }
            });
            
            // Container for the compressed text (flexible)
            var $compressedWrapper = $('<span>', {
                css: {
                    'flex': '1',
                    'min-width': '0',
                    'overflow': 'hidden',
                    'text-overflow': 'ellipsis',
                    'white-space': 'nowrap'
                }
            });
            
            // Compressed text (always visible)
            var $compressed = $('<span>', {
                class: 'mcp_json_compressed',
                text: compressedValue,
                css: {
                    'cursor': 'pointer',
                    'user-select': 'none',
                    'display': 'inline-block'
                }
            });
            
            // Copy-to-clipboard button (stuck to the right of the field)
            var $copyButton = $('<button>', {
                class: 'btn btn-sm btn-link mcp_json_copy_btn',
                html: '<i class="fa fa-copy"></i>',
                css: {
                    'padding': '2px 5px',
                    'margin-left': '3px',
                    'font-size': '12px',
                    'vertical-align': 'middle',
                    'border': 'none',
                    'background': 'transparent',
                    'color': '#6c757d',
                    'cursor': 'pointer',
                    'display': 'inline-block',
                    'line-height': '1',
                    'flex-shrink': '0'
                },
                title: _t('Copy to clipboard'),
                click: function(e) {
                    e.stopPropagation();
                    self._copyToClipboard();
                }
            });
            
            $compressedWrapper.append($compressed);
            $compressedLine.append($compressedWrapper);
            $compressedLine.append($copyButton);
            
            // Container for the expanded JSON (hidden by default)
            var $expandedContainer = $('<div>', {
                class: 'mcp_json_expanded_container',
                css: {
                    'display': 'none',
                    'margin-top': '5px',
                    'padding': '10px',
                    'background-color': '#f8f9fa',
                    'border': '1px solid #dee2e6',
                    'border-radius': '4px',
                    'max-width': '100%',
                    'overflow-x': 'auto',
                    'position': 'relative'
                }
            });
            
            // Placeholder while it loads
            var $expanded = $('<pre>', {
                class: 'mcp_json_expanded',
                text: _t('Loading...'),
                css: {
                    'margin': '0',
                    'white-space': 'pre-wrap',
                    'word-wrap': 'break-word',
                    'font-size': '12px',
                    'font-family': 'monospace'
                }
            });
            
            // Copy button in the expanded container
            var $copyButtonExpanded = $('<button>', {
                class: 'btn btn-sm btn-link mcp_json_copy_btn_expanded',
                html: '<i class="fa fa-copy"></i>',
                css: {
                    'position': 'absolute',
                    'top': '5px',
                    'right': '5px',
                    'padding': '2px 8px',
                    'font-size': '11px',
                    'border': '1px solid #dee2e6',
                    'background': '#fff',
                    'color': '#6c757d',
                    'cursor': 'pointer',
                    'border-radius': '3px'
                },
                title: _t('Copy to clipboard'),
                click: function(e) {
                    e.stopPropagation();
                    self._copyToClipboard();
                }
            });
            
            $expandedContainer.append($expanded);
            $expandedContainer.append($copyButtonExpanded);
            $container.append($compressedLine);
            $container.append($expandedContainer);
            this.$el.append($container);
            
            // Keep references
            this._$expandedContainer = $expandedContainer;
            this._$expanded = $expanded;
            this._fullValueLoaded = false;
            
            // Toggle on click
            $compressed.on('click', function(e) {
                e.stopPropagation();
                self._toggleExpanded();
            });
        },
        
        _toggleExpanded: function() {
            var self = this;
            var $expandedContainer = this._$expandedContainer;
            
            if (this._expanded) {
                $expandedContainer.slideUp(200);
                this._expanded = false;
            } else {
                // If the full value is not loaded yet, load it now
                if (!this._fullValueLoaded) {
                    this._loadFullValue();
                }
                $expandedContainer.slideDown(200);
                this._expanded = true;
            }
        },
        
        _loadFullValue: function() {
            var self = this;
            var record = this.record;
            var fieldName = this.name;
            
            // Find the original field from the compressed field
            var originalFieldName = '';
            if (fieldName === 'prompt_data_compressed') {
                originalFieldName = 'prompt_data';
            } else if (fieldName === 'result_summary_compressed') {
                // For the result, use result_data (the full JSON) instead of result_summary
                originalFieldName = 'result_data';
            } else {
                originalFieldName = fieldName.replace('_compressed', '');
            }
            
            if (!record || !record.res_id) {
                // If there is no record ID, use the compressed value
                this._formatAndDisplayValue(this.value || '');
                return;
            }
            
            // RPC call to get the full value from the original field
            this._rpc({
                model: record.model || 'ai.log',
                method: 'read',
                args: [[record.res_id], [originalFieldName]],
            }).then(function(result) {
                if (result && result.length > 0 && result[0][originalFieldName]) {
                    self._formatAndDisplayValue(result[0][originalFieldName]);
                } else {
                    self._formatAndDisplayValue(self.value || '');
                }
            }).catch(function() {
                self._formatAndDisplayValue(self.value || '');
            });
        },
        
        _formatAndDisplayValue: function(fullValue) {
            var formattedValue = fullValue;
            
            // Clean escapes if the value has them (may come from double serialization)
            try {
                // Try to parse as JSON (may have escapes if it was serialized twice)
                var parsed = JSON.parse(fullValue);
                
                // If the parsed result is a string, it may be JSON inside JSON
                if (typeof parsed === 'string') {
                    try {
                        parsed = JSON.parse(parsed);
                    } catch (e) {
                        // If that fails, use the parsed string
                    }
                }
                
                // Format the JSON cleanly
                formattedValue = JSON.stringify(parsed, null, 2);
            } catch (e) {
                // If it is not valid JSON, clean escapes by hand and show it as is
                formattedValue = fullValue
                    .replace(/\\n/g, '\n')
                    .replace(/\\"/g, '"')
                    .replace(/\\t/g, '\t')
                    .replace(/\\r/g, '\r');
            }
            
            this._$expanded.text(formattedValue);
            this._fullValueLoaded = true;
            // Keep the formatted value so it can be copied (same as in form)
            this._formattedValue = formattedValue;
        },
        
        _copyToClipboard: function() {
            var self = this;
            var record = this.record;
            var fieldName = this.name;
            
            // Find the original field from the compressed field (same as in _loadFullValue)
            var originalFieldName = '';
            if (fieldName === 'prompt_data_compressed') {
                originalFieldName = 'prompt_data';
            } else if (fieldName === 'result_summary_compressed') {
                // For the result, use result_data (the full JSON), same as in form
                originalFieldName = 'result_data';
            } else {
                originalFieldName = fieldName.replace('_compressed', '');
            }
            
            // If the full value is already loaded and formatted, use it directly
            if (this._fullValueLoaded && this._formattedValue) {
                this._doCopy(this._formattedValue);
                return;
            }
            
            // If there is a record ID, load the full value from the original field
            if (record && record.res_id) {
                this._rpc({
                    model: record.model || 'ai.log',
                    method: 'read',
                    args: [[record.res_id], [originalFieldName]],
                }).then(function(result) {
                    if (result && result.length > 0 && result[0][originalFieldName]) {
                        // Format the value as in _formatAndDisplayValue
                        var fullValue = result[0][originalFieldName];
                        var formattedValue = fullValue;
                        
                        try {
                            var parsed = JSON.parse(fullValue);
                            if (typeof parsed === 'string') {
                                try {
                                    parsed = JSON.parse(parsed);
                                } catch (e) {
                                    // If that fails, use the parsed string
                                }
                            }
                            formattedValue = JSON.stringify(parsed, null, 2);
                        } catch (e) {
                            formattedValue = fullValue
                                .replace(/\\n/g, '\n')
                                .replace(/\\"/g, '"')
                                .replace(/\\t/g, '\t')
                                .replace(/\\r/g, '\r');
                        }
                        
                        self._doCopy(formattedValue);
                    } else {
                        // If there is no value, fall back to the compressed one
                        self._doCopy(self.value || '');
                    }
                }).catch(function() {
                    // If that fails, fall back to the compressed one
                    self._doCopy(self.value || '');
                });
            } else {
                // If there is no record ID, fall back to the compressed value
                this._doCopy(this.value || '');
            }
        },
        
        _doCopy: function(text) {
            var self = this;
            // Create a temporary element to copy from
            var $temp = $('<textarea>', {
                css: {
                    'position': 'fixed',
                    'opacity': '0',
                    'left': '-9999px'
                },
                val: text
            });
            
            $('body').append($temp);
            $temp.select();
            
            try {
                var successful = document.execCommand('copy');
                if (successful) {
                    // Always use a toast for every copy
                    this._showCopyToast();
                } else {
                    console.warn('Could not copy to clipboard');
                }
            } catch (err) {
                console.error('Error copying:', err);
            }
            
            $temp.remove();
        },
        
        _showCopyToast: function() {
            // Use the Odoo notification system
            this.displayNotification({
                title: _t('Copied'),
                message: _t('Content copied to clipboard'),
                type: 'success',
                sticky: false,
                className: 'o_mcp_copy_toast'
            });
        },
    });

    fieldRegistry.add('mcp_json_compressed', MCPJsonCompressedWidget);

    return MCPJsonCompressedWidget;
});

