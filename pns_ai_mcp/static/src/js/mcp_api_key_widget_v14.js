odoo.define('pns_ai_mcp.mcp_api_key_widget', function (require) {
    "use strict";

    var AbstractField = require('web.AbstractField');
    var field_registry = require('web.field_registry');

    var MCPApiKeyWidget = AbstractField.extend({
        className: 'o_field_mcp_api_key',
        supportedFieldTypes: ['char'],
        
        _render: function () {
            var self = this;
            
            // Llamar al m├®todo padre para asegurar que this.$el est├® inicializado
            this._super.apply(this, arguments);
            
            if (!this.$el || !this.$el.length) {
                return;
            }
            
            this.$el.empty();
            
            // Contenedor flex
            var $container = $('<div>', {
                class: 'd-flex align-items-center'
            });
            
            // Botones de acci├│n si hay valor (a la izquierda)
            if (this.value) {
                // Bot├│n de copiar
                var $copyButton = $('<button>', {
                    class: 'btn btn-sm btn-link',
                    title: 'Copiar al portapapeles'
                }).append($('<i>', {
                    class: 'fa fa-copy'
                }));
                
                $copyButton.on('click', function(ev) {
                    ev.preventDefault();
                    ev.stopPropagation();
                    navigator.clipboard.writeText(self.value).then(function() {
                        self.displayNotification({
                            type: 'success',
                            title: '├ëxito',
                            message: 'API Key MCP copiada al portapapeles',
                        });
                    }).catch(function() {
                        self.displayNotification({
                            type: 'danger',
                            title: 'Error',
                            message: 'Error al copiar API Key MCP',
                        });
                    });
                });
                
                $container.append($copyButton);
            }
            
            // Span para el valor (a la derecha del bot├│n)
            var $value = $('<span>', {
                class: 'flex-grow-1',
                text: this.value || 'No API Key'
            });
            
            $container.append($value);
            
            this.$el.append($container);
        },
    });

    field_registry.add('mcp_api_key_display', MCPApiKeyWidget);
    
    return MCPApiKeyWidget;
});

