odoo.define('pns_ai_mcp.ContextWindowComboWidget', function (require) {
    "use strict";
    // Context window (tokens) as a plain dropdown <select>. Options are a
    // curated ladder of ROUND sizes (powers of two and their 1.5x/3x multiples,
    // all exact multiples of 1024), matching real LLM context windows from 1K
    // to 2M. An off-grid stored value (import/backup) is injected as an option.

    var AbstractField = require('web.AbstractField');
    var registry = require('web.field_registry');

    // Round token sizes (K = 1024). Clean powers of two plus 1.5x/3x half-steps.
    var STEP_VALUES = [
        1024, 2048, 4096, 8192, 12288, 16384, 24576, 32768, 49152, 65536,
        98304, 131072, 196608, 262144, 393216, 524288, 786432, 1048576,
        1572864, 2097152,
    ];

    function buildValues() {
        return STEP_VALUES.slice();
    }

    function compact(n) {
        if (n >= 1048576) {
            return (n / 1048576).toFixed(n % 1048576 ? 1 : 0) + 'M';
        }
        if (n >= 1024) {
            return (n / 1024).toFixed(n % 1024 ? 1 : 0) + 'K';
        }
        return '' + n;
    }

    function label(n) {
        if (!n || isNaN(n) || n <= 0) {
            return '';
        }
        return compact(n) + ' — ' + n.toLocaleString();
    }

    var ContextWindowComboWidget = AbstractField.extend({
        tagName: 'span',
        supportedFieldTypes: ['integer'],
        events: {
            'change select': '_onChangeSelect',
        },

        _render: function () {
            this.$el.empty();
            if (this.mode === 'edit') {
                var $select = $('<select class="o_input" style="width:auto;">');
                var values = buildValues();
                var cur = this.value;
                if (cur && values.indexOf(cur) === -1) {
                    values.unshift(cur);
                }
                values.forEach(function (v) {
                    var $o = $('<option>').val(v).text(label(v));
                    if (v === cur) {
                        $o.attr('selected', 'selected');
                    }
                    $select.append($o);
                });
                this.$select = $select;
                this.$el.append($select);
            } else {
                this.$el.text(label(this.value));
            }
        },

        _onChangeSelect: function () {
            // OJO: _setValue -> field_utils.parse.integer espera una CADENA
            // (hace value.replace(...)). Si le pasamos un Number, lanza y el
            // campo se marca como "inválido" (label en rojo). Pasamos el string
            // tal cual del <select> y que Odoo lo parsee.
            var raw = this.$select.val();
            this._setValue(raw === '' ? false : raw);
        },

        isSet: function () {
            return true;
        },
    });

    registry.add('context_window_combo', ContextWindowComboWidget);

    return ContextWindowComboWidget;
});
