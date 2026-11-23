/** @odoo-module **/
/* SPDX-License-Identifier: Apache-2.0
 * Copyright (C) 2026 Patanegra Soft <https://patanegra.com>
 *
 * List many2one. On a form, the row is already open, so the link stacks
 * the related record and the breadcrumb keeps this one. A list has no
 * form yet. Open this row's form, then the related record the same way
 * the form does. The address stays "#" so the router does not load a
 * new screen.
 *
 * The row model is the list record, never the many2one's relation.
 * In the list, add display_name invisible so the crumb has a name at once.
 *   <field name="display_name" invisible="1"/>
 *   <field name="link_id" widget="pns_row_link"/>
 */
import { Component } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { standardFieldProps } from "@web/views/fields/standard_field_props";
import { useService } from "@web/core/utils/hooks";

class PnsRowLink extends Component {
    static template = "pns_base.RowLink";
    static props = { ...standardFieldProps };

    setup() {
        this.action = useService("action");
        this.orm = useService("orm");
    }

    get label() {
        const value = this.props.record.data[this.props.name];
        if (!value) {
            return "";
        }
        if (Array.isArray(value)) {
            return value[1] || "";
        }
        return value.display_name || "";
    }

    get relatedId() {
        const value = this.props.record.data[this.props.name];
        if (!value) {
            return 0;
        }
        return Array.isArray(value) ? value[0] : value.id;
    }

    async openRelated() {
        const relatedId = this.relatedId;
        const rowId = this.props.record.resId;
        const rowModel = this.props.record.resModel;
        const relation = this.props.record.fields[this.props.name].relation;
        if (!relatedId || !rowId || !rowModel || !relation) {
            return;
        }
        const rowName = this.props.record.data.display_name || "";
        await this.action.doAction({
            type: "ir.actions.act_window",
            name: rowName,
            res_model: rowModel,
            res_id: rowId,
            views: [[false, "form"]],
            target: "current",
        });
        const linked = await this.orm.call(relation, "get_formview_action", [[relatedId]]);
        if (!linked) {
            return;
        }
        linked.target = "current";
        delete linked.id;
        await this.action.doAction(linked);
    }
}

registry.category("fields").add("pns_row_link", {
    component: PnsRowLink,
    supportedTypes: ["many2one"],
});
