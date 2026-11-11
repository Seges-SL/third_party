/**
 * Copy-to-clipboard buttons on log (and similar) forms (Odoo 14).
 *
 * SPDX-License-Identifier: Apache-2.0
 * Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
 */
odoo.define('pns_ai_mcp.mcp_log_form', function (require) {
    "use strict";

    var FormController = require('web.FormController');
    var FormRenderer = require('web.FormRenderer');
    var core = require('web.core');

    var _t = core._t;

    FormRenderer.include({
        _render: function() {
            var self = this;
            var result = this._super.apply(this, arguments);
            
            // Any form with Copy buttons (logs, user import wizard, etc.)
            var scheduleCopy = function () {
                if (!self.$el.find('.o_field_text_copy_btn').length) {
                    return;
                }
                self._setupCopyButtons();
            };
            if (result && typeof result.then === 'function') {
                result.then(scheduleCopy);
            } else {
                scheduleCopy();
            }
            
            return result;
        },
        
        _setupCopyButtons: function() {
            var self = this;
            var $copyButtons = this.$el.find('.o_field_text_copy_btn');
            
            $copyButtons.off('click.mcp_copy').on('click.mcp_copy', function(e) {
                e.preventDefault();
                e.stopPropagation();
                
                var $button = $(this);
                var $container = $button.closest('.o_field_text_copy_container');
                var $field = $container.find('.o_field_text_copy_target');
                
                // Get the field text
                var textToCopy = '';
                if ($field.length) {
                    // Look for the textarea inside the field
                    var $textarea = $field.find('textarea');
                    if ($textarea.length) {
                        textToCopy = $textarea.val();
                    } else {
                        // If there is no textarea, look directly in the field or its container
                        var $fieldContent = $field.find('.o_field_text, pre, div');
                        if ($fieldContent.length) {
                            textToCopy = $fieldContent.text();
                        } else {
                            textToCopy = $field.text();
                        }
                    }
                }
                
                if (textToCopy) {
                    // Copy to the clipboard
                    var $temp = $('<textarea>', {
                        css: {
                            'position': 'fixed',
                            'opacity': '0',
                            'left': '-9999px'
                        },
                        val: textToCopy
                    });
                    
                    $('body').append($temp);
                    $temp.select();
                    
                    try {
                        var successful = document.execCommand('copy');
                        if (successful) {
                            // Get the controller to show the notification
                            var controller = self.getParent();
                            while (controller && !controller.displayNotification) {
                                controller = controller.getParent ? controller.getParent() : null;
                            }
                            
                            if (controller && controller.displayNotification) {
                                controller.displayNotification({
                                    title: _t('Copied'),
                                    message: _t('Content copied to clipboard'),
                                    type: 'success',
                                    sticky: false,
                                    className: 'o_mcp_copy_toast'
                                });
                            } else {
                                // Fallback: use trigger_up
                                self.trigger_up('show_notification', {
                                    title: _t('Copied'),
                                    message: _t('Content copied to clipboard'),
                                    type: 'success',
                                    sticky: false,
                                });
                            }
                        } else {
                            console.warn('Could not copy to clipboard');
                        }
                    } catch (err) {
                        console.error('Error copying:', err);
                    }
                    
                    $temp.remove();
                }
            });
        },
    });

    return {};
});

