/* SPDX-License-Identifier: Apache-2.0
 * Copyright (C) 2026 Patanegra Soft <https://patanegra.com>
 *
 * Three web modules that our code imports do not exist in Odoo 16:
 * @web/core/network/rpc, @web/core/user and @web/model/relational_model/record.
 * Odoo 17.0 still lacks the first two. Where Odoo lacks one, it is defined
 * here on top of what that version has. Where Odoo has it, nothing happens.
 * Plain script, not @odoo-module: it must run while the bundle registers
 * modules, before anything imports them.
 *
 * Odoo 17+ turns every static/src file into a module and lists each
 * require of a quoted name as a dependency, so the 16-only names stay in
 * constants: a quoted name here would be a missing module there.
 */
(function () {
    const OWL = "@odoo/owl";
    const RPC = "@web/core/network/rpc";
    const RPC_16 = "@web/core/network/rpc_service";
    const SESSION = "@web/session";
    const MODEL_16 = "@web/views/relational_model";
    const loader = odoo.loader;
    const has = (name) => (loader ? loader.factories.has(name) : name in odoo.__DEBUG__.factories);
    const define = (name, deps, factory) => {
        if (!has(name)) {
            odoo.define(name, deps, factory);
        }
    };

    define(RPC, [OWL, RPC_16], function (require) {
        const { EventBus } = require(OWL);
        const { jsonrpc } = require(RPC_16);
        const env = { bus: new EventBus() };
        let rpcId = 0;
        // 16: jsonrpc(env, rpcId, url, params, settings). 17.0: jsonrpc(url, params, settings).
        const takesEnv = jsonrpc.length > 1;
        function rpc(url, params = {}, settings = {}) {
            return takesEnv
                ? jsonrpc(env, ++rpcId, url, params, settings)
                : jsonrpc(url, params, settings);
        }
        return { rpc };
    });

    define("@web/core/user", [RPC, SESSION], function (require) {
        const { rpc } = require(RPC);
        const { session } = require(SESSION);
        const groups = new Map();
        const user = {
            hasGroup(group) {
                if (!groups.has(group)) {
                    groups.set(group, rpc("/web/dataset/call_kw/res.users/has_group", {
                        model: "res.users",
                        method: "has_group",
                        args: [group],
                        kwargs: { context: session.user_context },
                    }));
                }
                return groups.get(group);
            },
        };
        return { user };
    });

    define("@web/model/relational_model/record", [MODEL_16], function (require) {
        return { Record: require(MODEL_16).Record };
    });
})();
