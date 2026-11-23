/** @odoo-module **/
/* SPDX-License-Identifier: Apache-2.0
 * Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
 *
 * Deduplicate invalid-field names in the form/list error toast.
 */

import { FormController } from "@web/views/form/form_controller";
import { Record } from "@web/model/relational_model/record";
import { pnsPatch } from "@pns_base/js/pns_patch";
import { _t } from "@web/core/l10n/translation";

function uniqueNames(names) {
    const seen = new Set();
    const out = [];
    for (const name of names || []) {
        if (name && !seen.has(name)) {
            seen.add(name);
            out.push(name);
        }
    }
    return out;
}

function uniqueFieldItems(items) {
    const seen = new Set();
    const out = [];
    for (const item of items || []) {
        const key = typeof item === "string" ? item : (item && (item.name || item.string));
        if (!key || seen.has(key)) {
            continue;
        }
        seen.add(key);
        out.push(item);
    }
    return out;
}

function dedupeRecordInvalid(record) {
    if (!record) {
        return;
    }
    if (record._invalidFields instanceof Set) {
        return;
    }
    if (Array.isArray(record._invalidFields)) {
        record._invalidFields = uniqueNames(record._invalidFields);
    }
    if (Array.isArray(record.invalidFields)) {
        record.invalidFields = uniqueFieldItems(record.invalidFields);
    }
}

function fieldLabel(record, name) {
    const fields = record.fields || {};
    return (fields[name] && fields[name].string) || name;
}

function requiredTitle(labels) {
    const unique = uniqueNames(labels);
    const joined = unique.join(", ");
    if (unique.length === 1) {
        return _t("Required field: %s", joined);
    }
    return _t("Required fields: %s", joined);
}

function archHasPnsClass(arch) {
    if (!arch) {
        return false;
    }
    if (typeof arch === "string") {
        return arch.includes("o_pns_view");
    }
    const attrs = arch.attrs || arch.attributes || {};
    return String(attrs.class || "").split(/\s+/).includes("o_pns_view");
}

pnsPatch(FormController.prototype, "pns_base.pns_invalid_fields_dedupe", {
    setup() {
        super.setup(...arguments);
        this.model._pnsOwnedView = archHasPnsClass(this.props && this.props.arch);
    },
    /**
     * One row per field name when the same field is on the form
     * several times (oe_read_only / oe_edit_only copies).
     */
    async save(params) {
        if (!this.model._pnsOwnedView) {
            return super.save(params);
        }
        dedupeRecordInvalid(this.model && this.model.root);
        return super.save(params);
    },
});

pnsPatch(Record.prototype, "pns_base.pns_invalid_fields_dedupe", {
    /**
     * Name the empty required fields. Format errors keep the core toast.
     */
    _displayInvalidFieldNotification() {
        if (!this.model._pnsOwnedView) {
            if (typeof super._displayInvalidFieldNotification === "function") {
                return super._displayInvalidFieldNotification();
            }
            return;
        }
        const required = this._unsetRequiredFields
            ? uniqueNames([...this._unsetRequiredFields])
            : [];
        const invalid = this._invalidFields ? uniqueNames([...this._invalidFields]) : [];
        const onlyRequired =
            required.length &&
            invalid.every((name) => this._unsetRequiredFields.has(name));
        if (!onlyRequired && typeof super._displayInvalidFieldNotification === "function") {
            return super._displayInvalidFieldNotification();
        }
        const names = onlyRequired || required.length ? required : invalid;
        const labels = names.map((name) => fieldLabel(this, name));
        return this.model.notification.add(requiredTitle(labels), { type: "danger" });
    },
});
