/**
 * Chatboo screen context — shared between owl1 and owl2 clients.
 *
 * Reads the Odoo screen underneath the Chatboo overlay via the action service
 * (OWL2) or URL hash (OWL1 fallback). Loaded as a plain script (global
 * ChatbooScreenContext). Deploy copies common/ into the stack addon via i.sh.
 */
(function (global) {
    "use strict";

    function parseHashParams() {
        var hash = (global.location.hash || "").replace(/^#/, "");
        if (!hash) {
            return {};
        }
        var params = {};
        hash.split("&").forEach(function (pair) {
            var idx = pair.indexOf("=");
            var key = idx >= 0 ? pair.slice(0, idx) : pair;
            var val = idx >= 0 ? decodeURIComponent(pair.slice(idx + 1)) : "";
            if (key) {
                params[key] = val;
            }
        });
        return params;
    }

    function parseActiveIds(raw) {
        if (!raw) {
            return [];
        }
        if (Array.isArray(raw)) {
            return raw.map(function (x) { return parseInt(x, 10); }).filter(Boolean);
        }
        if (typeof raw === "string") {
            try {
                var normalized = raw.replace(/'/g, '"');
                raw = JSON.parse(normalized);
            } catch (_) {
                return [];
            }
        }
        if (Array.isArray(raw)) {
            return raw.map(function (x) { return parseInt(x, 10); }).filter(Boolean);
        }
        return [];
    }

    function fromHash() {
        var p = parseHashParams();
        var idRaw = p.id || p.res_id;
        var resId = idRaw ? parseInt(idRaw, 10) || null : null;
        return {
            url_hash: global.location.hash || "",
            action: {
                action_id: p.action ? parseInt(p.action, 10) || null : null,
                name: null,
                res_model: p.model || null,
                view_type: p.view_type || null,
                res_id: resId,
                active_ids: resId ? [resId] : [],
                domain: null,
                menu_id: p.menu_id ? parseInt(p.menu_id, 10) || null : null,
            },
        };
    }

    function fromActionService(env) {
        var hashCtx = fromHash();
        try {
            var actionSvc = env && env.services && env.services.action;
            var ctrl = actionSvc && actionSvc.currentController;
            if (!ctrl) {
                return hashCtx;
            }
            var act = ctrl.action || {};
            var props = ctrl.props || {};
            var resId = typeof ctrl.resId === "function"
                ? ctrl.resId()
                : (props.resId != null ? props.resId : act.res_id);
            if (resId === false) {
                resId = null;
            }
            var activeIds = parseActiveIds(act.context && act.context.active_ids);
            if (!activeIds.length && resId) {
                activeIds = [resId];
            }
            var viewType = props.type || act.view_mode || hashCtx.action.view_type;
            if (typeof viewType === "string" && viewType.indexOf(",") >= 0) {
                viewType = viewType.split(",")[0];
            }
            return {
                url_hash: hashCtx.url_hash,
                action: {
                    action_id: act.id || hashCtx.action.action_id,
                    name: act.display_name || act.name || null,
                    res_model: props.resModel || act.res_model || hashCtx.action.res_model,
                    view_type: viewType || null,
                    res_id: resId != null ? resId : hashCtx.action.res_id,
                    active_ids: activeIds,
                    domain: act.domain || null,
                    menu_id: hashCtx.action.menu_id,
                },
            };
        } catch (_) {
            return hashCtx;
        }
    }

    function get(env) {
        var ctx = (env && env.services && env.services.action)
            ? fromActionService(env)
            : fromHash();
        ctx.captured_at = new Date().toISOString();
        return ctx;
    }

    function hasSendableContext(ctx) {
        if (!ctx || !ctx.action) {
            return false;
        }
        var a = ctx.action;
        return !!(a.res_model || a.view_type || a.action_id);
    }

    function formatChipLabel(ctx) {
        if (!ctx || !ctx.action) {
            return "";
        }
        var a = ctx.action;
        if (!a.res_model && !a.view_type && !a.action_id) {
            return "";
        }
        var label = a.name || a.res_model || ("action " + a.action_id);
        if (a.res_id) {
            label += " #" + a.res_id;
        } else if (a.active_ids && a.active_ids.length > 1) {
            label += " (" + a.active_ids.length + " selected)";
        } else if (a.view_type) {
            label += " · " + a.view_type;
        }
        return label;
    }

    global.ChatbooScreenContext = {
        get: get,
        formatChipLabel: formatChipLabel,
        hasSendableContext: hasSendableContext,
    };
}(typeof globalThis !== "undefined" ? globalThis : window));
