odoo.define('pns_ai_mcp.mcp_json_compressed_widget', function (require) {
    "use strict";

    var AbstractField = require('web.AbstractField');
    var fieldRegistry = require('web.field_registry');
    var core = require('web.core');
    var Notification = require('web.Notification');

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
            
            // Limpiar contenido anterior
            this.$el.empty();
            
            if (!compressedValue) {
                this.$el.text('');
                return;
            }
            
            // Limpiar escapes si el valor los tiene (puede venir de doble serializaci├│n)
            // Intentar parsear como JSON string primero
            try {
                var parsed = JSON.parse(compressedValue);
                if (typeof parsed === 'string') {
                    // Si es un string JSON, intentar parsearlo de nuevo (doble serializaci├│n)
                    try {
                        parsed = JSON.parse(parsed);
                    } catch (e) {
                        // Si falla, usar el string parseado
                    }
                }
                // Serializar limpiamente sin escapes innecesarios
                compressedValue = JSON.stringify(parsed, null, 0).replace(/\s+/g, ' ').trim();
            } catch (e) {
                // Si no es JSON v├ílido, limpiar escapes manualmente
                // Primero intentar limpiar escapes comunes
                compressedValue = compressedValue
                    .replace(/\\n/g, ' ')
                    .replace(/\\"/g, '"')
                    .replace(/\\t/g, ' ')
                    .replace(/\\r/g, ' ')
                    .replace(/\\\\/g, '\\')  // Reemplazar \\ por \
                    .replace(/\s+/g, ' ')
                    .trim();
            }
            
            // Crear contenedor principal - sin width inline para respetar el ancho de la columna
            var $container = $('<div>', {
                class: 'mcp_json_container'
            });
            
            // Contenedor para la l├¡nea comprimida (flex para alinear bot├│n a la derecha)
            var $compressedLine = $('<div>', {
                css: {
                    'display': 'flex',
                    'align-items': 'center',
                    'width': '100%'
                }
            });
            
            // Contenedor para texto comprimido (flexible)
            var $compressedWrapper = $('<span>', {
                css: {
                    'flex': '1',
                    'min-width': '0',
                    'overflow': 'hidden',
                    'text-overflow': 'ellipsis',
                    'white-space': 'nowrap'
                }
            });
            
            // Texto comprimido (siempre visible)
            var $compressed = $('<span>', {
                class: 'mcp_json_compressed',
                text: compressedValue,
                css: {
                    'cursor': 'pointer',
                    'user-select': 'none',
                    'display': 'inline-block'
                }
            });
            
            // Bot├│n de copiar al clipboard (pegado a la derecha del campo)
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
                title: 'Copiar al portapapeles',
                click: function(e) {
                    e.stopPropagation();
                    self._copyToClipboard();
                }
            });
            
            $compressedWrapper.append($compressed);
            $compressedLine.append($compressedWrapper);
            $compressedLine.append($copyButton);
            
            // Contenedor para JSON expandido (oculto por defecto)
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
            
            // Placeholder mientras se carga
            var $expanded = $('<pre>', {
                class: 'mcp_json_expanded',
                text: 'Cargando...',
                css: {
                    'margin': '0',
                    'white-space': 'pre-wrap',
                    'word-wrap': 'break-word',
                    'font-size': '12px',
                    'font-family': 'monospace'
                }
            });
            
            // Bot├│n de copiar en el contenedor expandido
            var $copyButtonExpanded = $('<button>', {
                class: 'btn btn-sm btn-link mcp_json_copy_btn_expanded',
                html: '<i class="fa fa-copy"></i> Copiar',
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
                title: 'Copiar al portapapeles',
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
            
            // Guardar referencias
            this._$expandedContainer = $expandedContainer;
            this._$expanded = $expanded;
            this._fullValueLoaded = false;
            
            // Toggle al hacer click
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
                // Si no se ha cargado el valor completo, cargarlo ahora
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
            
            // Determinar el campo original seg├║n el campo comprimido
            var originalFieldName = '';
            if (fieldName === 'prompt_data_compressed') {
                originalFieldName = 'prompt_data';
            } else if (fieldName === 'result_summary_compressed') {
                // Para resultado, usar result_data (el JSON completo) en lugar de result_summary
                originalFieldName = 'result_data';
            } else {
                originalFieldName = fieldName.replace('_compressed', '');
            }
            
            if (!record || !record.res_id) {
                // Si no hay record ID, usar el valor comprimido
                this._formatAndDisplayValue(this.value || '');
                return;
            }
            
            // Hacer RPC para obtener el valor completo desde el campo original
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
            
            // Limpiar escapes si el valor los tiene (puede venir de doble serializaci├│n)
            try {
                // Intentar parsear como JSON (puede tener escapes si fue doblemente serializado)
                var parsed = JSON.parse(fullValue);
                
                // Si el resultado parseado es un string, puede ser JSON dentro de JSON
                if (typeof parsed === 'string') {
                    try {
                        parsed = JSON.parse(parsed);
                    } catch (e) {
                        // Si falla, usar el string parseado
                    }
                }
                
                // Formatear el JSON limpiamente
                formattedValue = JSON.stringify(parsed, null, 2);
            } catch (e) {
                // Si no es JSON v├ílido, limpiar escapes manualmente y mostrar tal cual
                formattedValue = fullValue
                    .replace(/\\n/g, '\n')
                    .replace(/\\"/g, '"')
                    .replace(/\\t/g, '\t')
                    .replace(/\\r/g, '\r');
            }
            
            this._$expanded.text(formattedValue);
            this._fullValueLoaded = true;
            // Guardar el valor formateado para poder copiarlo (igual que en form)
            this._formattedValue = formattedValue;
        },
        
        _copyToClipboard: function() {
            var self = this;
            var record = this.record;
            var fieldName = this.name;
            
            // Determinar el campo original seg├║n el campo comprimido (igual que en _loadFullValue)
            var originalFieldName = '';
            if (fieldName === 'prompt_data_compressed') {
                originalFieldName = 'prompt_data';
            } else if (fieldName === 'result_summary_compressed') {
                // Para resultado, usar result_data (el JSON completo) igual que en form
                originalFieldName = 'result_data';
            } else {
                originalFieldName = fieldName.replace('_compressed', '');
            }
            
            // Si el valor completo ya est├í cargado y formateado, usarlo directamente
            if (this._fullValueLoaded && this._formattedValue) {
                this._doCopy(this._formattedValue);
                return;
            }
            
            // Si hay record ID, cargar el valor completo desde el campo original
            if (record && record.res_id) {
                this._rpc({
                    model: record.model || 'ai.log',
                    method: 'read',
                    args: [[record.res_id], [originalFieldName]],
                }).then(function(result) {
                    if (result && result.length > 0 && result[0][originalFieldName]) {
                        // Formatear el valor igual que en _formatAndDisplayValue
                        var fullValue = result[0][originalFieldName];
                        var formattedValue = fullValue;
                        
                        try {
                            var parsed = JSON.parse(fullValue);
                            if (typeof parsed === 'string') {
                                try {
                                    parsed = JSON.parse(parsed);
                                } catch (e) {
                                    // Si falla, usar el string parseado
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
                        // Si no hay valor, usar el comprimido como fallback
                        self._doCopy(self.value || '');
                    }
                }).catch(function() {
                    // Si falla, usar el comprimido como fallback
                    self._doCopy(self.value || '');
                });
            } else {
                // Si no hay record ID, usar el valor comprimido como fallback
                this._doCopy(this.value || '');
            }
        },
        
        _doCopy: function(text) {
            var self = this;
            // Crear elemento temporal para copiar
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
                    // Siempre usar toast para todas las copias
                    this._showCopyToast();
                } else {
                    console.warn('No se pudo copiar al portapapeles');
                }
            } catch (err) {
                console.error('Error al copiar:', err);
            }
            
            $temp.remove();
        },
        
        _showCopyToast: function() {
            // Usar el sistema de notificaciones de Odoo
            this.displayNotification({
                title: 'Copiado',
                message: 'Contenido copiado al portapapeles',
                type: 'success',
                sticky: false,
                className: 'o_mcp_copy_toast'
            });
        },
    });

    fieldRegistry.add('mcp_json_compressed', MCPJsonCompressedWidget);

    return MCPJsonCompressedWidget;
});

