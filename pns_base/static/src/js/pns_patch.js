/** @odoo-module **/
/* SPDX-License-Identifier: Apache-2.0
 * Copyright (C) 2026 Patanegra Soft <https://patanegra.com>
 *
 * patch() written the 17+ way (`super.x()` inside the extension) that also
 * runs where patch() asks for a name and only offers this._super (16).
 * The name must be unique per patched object.
 */
import { patch } from "@web/core/utils/patch";

export function pnsPatch(obj, name, extension) {
    if (patch.length < 3) {
        return patch(obj, extension);
    }
    // `super` in the extension's methods looks up the extension's prototype:
    // hang the current behaviour there, then hand patch() only own keys.
    const current = Object.create(Object.getPrototypeOf(obj), Object.getOwnPropertyDescriptors(obj));
    Object.setPrototypeOf(extension, current);
    const own = Object.defineProperties({}, Object.getOwnPropertyDescriptors(extension));
    return patch(obj, name, own, { pure: true });
}
