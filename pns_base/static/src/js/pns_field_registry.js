/** @odoo-module **/
/* SPDX-License-Identifier: Apache-2.0
 * Copyright (C) 2026 Patanegra Soft <https://patanegra.com>
 *
 * Our field widgets register as { component, supportedTypes, ... }, the
 * shape Odoo 17+ reads. Odoo 16 reads the component class itself, with
 * those keys as statics: there an object stops the view with
 * "C is not a constructor". Where Odoo's own "char" is a class (16), each
 * object is handed out as its component with the rest of the keys on it.
 * Where it is an object, nothing changes.
 *
 * Decided when a view reads the registry, not when this file runs: the 16
 * loader orders modules by dependency, so "char" may not be there yet.
 */
import { registry } from "@web/core/registry";

const fields = registry.category("fields");
const get = fields.get.bind(fields);
let readsClasses;

function asClass(entry) {
    if (!entry || typeof entry === "function" || !entry.component) {
        return entry;
    }
    const { component, ...statics } = entry;
    return Object.assign(component, statics);
}

fields.get = (...args) => {
    const entry = get(...args);
    if (readsClasses === undefined && fields.contains("char")) {
        readsClasses = typeof get("char") === "function";
    }
    return readsClasses ? asClass(entry) : entry;
};
