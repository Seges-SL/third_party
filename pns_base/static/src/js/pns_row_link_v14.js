/* SPDX-License-Identifier: Apache-2.0
 * Copyright (C) 2026 Patanegra Soft <https://patanegra.com>
 *
 * List many2one. On a form, the row is already open, so the link stacks
 * the related record and the breadcrumb keeps this one. A list has no
 * form yet. Open this row's form, then the related record the same way
 * the form does. The address stays "#" so Odoo does not load a new screen.
 *
 * The row model is the list record, never the many2one's relation.
 * In the list, add display_name invisible so the crumb has a name at once.
 *   <field name="display_name" invisible="1"/>
 *   <field name="link_id" widget="pns_row_link"/>
 */
odoo.define('pns_base.row_link', function (require) {
    "use strict";

    var relational = require('web.relational_fields');
    var fieldRegistry = require('web.field_registry');

    var RowLink = relational.FieldMany2One.extend({
        className: 'o_field_pns_row_link',

        _renderReadonly: function () {
            if (!this.value || !this.value.res_id) {
                this.$el.empty().removeAttr('href');
                return;
            }
            this._super.apply(this, arguments);
            this.$el.attr('href', '#');
        },

        _onClick: function (ev) {
            ev.preventDefault();
            ev.stopPropagation();
            var relatedId = this.value && this.value.res_id;
            var rowModel = this.record && this.record.model;
            var rowId = this.res_id;
            var relation = this.field && this.field.relation;
            if (!relatedId || !rowId || !rowModel || !relation) {
                return;
            }
            var self = this;
            var rowName = (this.recordData && this.recordData.display_name) || '';
            this.trigger_up('do_action', {
                action: {
                    type: 'ir.actions.act_window',
                    name: rowName,
                    res_model: rowModel,
                    res_id: rowId,
                    views: [[false, 'form']],
                    target: 'current',
                },
                on_success: function () {
                    self._rpc({
                        model: relation,
                        method: 'get_formview_action',
                        args: [[relatedId]],
                    }).then(function (action) {
                        if (!action) {
                            return;
                        }
                        action.target = 'current';
                        delete action.id;
                        self.trigger_up('do_action', {action: action});
                    });
                },
            });
        },
    });

    fieldRegistry.add('pns_row_link', RowLink);
});
