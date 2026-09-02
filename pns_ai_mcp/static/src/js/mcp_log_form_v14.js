odoo.define('pns_ai_mcp.mcp_log_form', function (require) {
    "use strict";

    var FormController = require('web.FormController');
    var FormRenderer = require('web.FormRenderer');
    var Notification = require('web.Notification');
    var core = require('web.core');


    FormRenderer.include({
        _render: function() {
            var self = this;
            var result = this._super.apply(this, arguments);
            
            // Cualquier formulario con botones Copy (logs, wizard import usuarios, etc.)
            var scheduleCopy = function () {
                if (!self.$el.find('.o_field_text_copy_btn').length) {
                    return;
                }
                self._setupCopyButtons();
            };
            if (result && typeof result.then === 'function') {
                result.then(scheduleCopy);
            } else {
                setTimeout(scheduleCopy, 100);
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
                
                // Obtener el texto del campo
                var textToCopy = '';
                if ($field.length) {
                    // Buscar el textarea dentro del campo
                    var $textarea = $field.find('textarea');
                    if ($textarea.length) {
                        textToCopy = $textarea.val();
                    } else {
                        // Si no hay textarea, buscar directamente en el campo o en su contenedor
                        var $fieldContent = $field.find('.o_field_text, pre, div');
                        if ($fieldContent.length) {
                            textToCopy = $fieldContent.text();
                        } else {
                            textToCopy = $field.text();
                        }
                    }
                }
                
                if (textToCopy) {
                    // Copiar al portapapeles
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
                            // Obtener el controlador para mostrar la notificaci├│n
                            var controller = self.getParent();
                            while (controller && !controller.displayNotification) {
                                controller = controller.getParent ? controller.getParent() : null;
                            }
                            
                            if (controller && controller.displayNotification) {
                                controller.displayNotification({
                                    title: 'Copiado',
                                    message: 'Contenido copiado al portapapeles',
                                    type: 'success',
                                    sticky: false,
                                    className: 'o_mcp_copy_toast'
                                });
                            } else {
                                // Fallback: usar trigger_up
                                self.trigger_up('show_notification', {
                                    title: 'Copiado',
                                    message: 'Contenido copiado al portapapeles',
                                    type: 'success',
                                    sticky: false,
                                });
                            }
                        } else {
                            console.warn('No se pudo copiar al portapapeles');
                        }
                    } catch (err) {
                        console.error('Error al copiar:', err);
                    }
                    
                    $temp.remove();
                }
            });
        },
    });

    return {};
});

