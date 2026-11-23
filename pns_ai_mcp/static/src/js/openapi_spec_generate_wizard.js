/** @odoo-module **/
/**
 * OpenAPI spec wizard: stepped fetch + LLM conversion with typing dots.
 *
 * SPDX-License-Identifier: Apache-2.0
 * Copyright (C) 2026 Patanegra Soft <https://patanegra.com>
 */

import { FormController } from "@web/views/form/form_controller";
import { pnsPatch } from "@pns_base/js/pns_patch";
import { _t } from "@web/core/l10n/translation";
import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import {
    addUsage,
    findUsageElements,
    setUsageElementsWithFx,
    usageHasTokens,
} from "./ai_usage_chip";

const MODEL = "ai.openapi.spec.generate.wizard";

const CANCEL_CONFIRM_BODY = _t(
    "Stop the conversion in progress? Usage so far will be saved in AI Logs."
);
const CANCEL_WAITING = _t(
    "Cancelling… waiting for the current AI call to finish."
);
const CONVERTING_MSG = _t(
    "Converting with AI Admin…"
);

function silentCall(orm) {
    return (orm.silent && typeof orm.silent.call === "function")
        ? orm.silent.call.bind(orm.silent)
        : orm.call.bind(orm);
}

function openapiSteps() {
    return [
        {
            msg: _t("Fetching documentation…"),
            method: "action_fetch_documentation",
        },
        {
            msg: CONVERTING_MSG,
            method: "action_generate_openapi",
        },
    ];
}

function progressRoot(controller) {
    const el = controller.el;
    if (!el) {
        return document;
    }
    return el.closest(".modal, .o_dialog") || el;
}

function progressEls(controller) {
    const root = progressRoot(controller);
    const usageEls = findUsageElements(root);
    return {
        root,
        box: root.querySelector(".o_skill_capture_progress"),
        dots: root.querySelector(".o_skill_capture_typing"),
        label: root.querySelector(".o_skill_capture_progress_label"),
        usage: usageEls.inline,
        lastOp: usageEls.lastOp,
        stop: root.querySelector(".o_skill_capture_stop"),
        stopLabel: root.querySelector(".o_skill_capture_stop_label"),
        footerButtons: root.querySelectorAll("footer button"),
    };
}

function isFooterCancelButton(btn) {
    if (!btn || btn.classList.contains("o_skill_capture_stop")) {
        return false;
    }
    const special = (btn.getAttribute("special") || "").toLowerCase();
    if (special === "cancel") {
        return true;
    }
    const name = (btn.getAttribute("name") || "").toLowerCase();
    if (
        name === "action_generate"
        || name === "action_apply"
        || name === "action_abort_openapi"
    ) {
        return false;
    }
    const text = (btn.textContent || "").replace(/\s+/g, " ").trim().toLowerCase();
    return text === "cancel" || text === "cancelar"
        || text === "close" || text === "cerrar";
}

async function setUsage(controller, usage) {
    const orm = controller.env.services.orm;
    await setUsageElementsWithFx(orm, progressRoot(controller), usage);
}

function markAborting(controller) {
    controller._pnsOpenapiAborted = true;
    const els = progressEls(controller);
    if (els.dots) {
        els.dots.style.display = "none";
    }
    if (els.label) {
        els.label.textContent = CANCEL_WAITING;
    }
    if (els.stop) {
        els.stop.disabled = true;
    }
    els.footerButtons.forEach((btn) => {
        if (isFooterCancelButton(btn)) {
            btn.disabled = false;
        }
    });
}

function closeWizard(controller) {
    controller._pnsOpenapiBusy = false;
    const action = controller.env.services.action;
    if (action && typeof action.doAction === "function") {
        return action.doAction({type: "ir.actions.act_window_close"});
    }
    return undefined;
}

async function requestCancel(controller) {
    if (controller._pnsOpenapiAborted) {
        await closeWizard(controller);
        return;
    }
    const dialog = controller.env.services.dialog;
    const afterConfirm = async () => {
        markAborting(controller);
        await logUsage(
            controller,
            controller._pnsOpenapiWizardId,
            controller._pnsOpenapiUsage,
            "cancelled",
        );
        await closeWizard(controller);
    };
    if (!dialog) {
        if (window.confirm(_t(
            "Cancel OpenAPI generation? Stop the conversion in progress? Usage so far will be saved in AI Logs."
        ))) {
            await afterConfirm();
        }
        return;
    }
    dialog.add(ConfirmationDialog, {
        title: _t("Cancel OpenAPI generation?"),
        body: CANCEL_CONFIRM_BODY,
        confirm: () => {
            afterConfirm();
        },
        confirmLabel: _t("Yes, cancel"),
        cancelLabel: _t("Keep waiting"),
    });
}

function setBusy(controller, busy, message) {
    const els = progressEls(controller);
    if (els.stopLabel) {
        els.stopLabel.textContent = _t("Cancel");
    }
    if (els.box) {
        els.box.style.display = busy ? "flex" : "none";
    }
    if (els.dots) {
        els.dots.style.display = (busy && !controller._pnsOpenapiAborted) ? "" : "none";
    }
    if (els.stop) {
        els.stop.style.display = busy ? "" : "none";
        els.stop.disabled = !busy || Boolean(controller._pnsOpenapiAborted);
    }
    if (els.label && message) {
        els.label.textContent = message;
    }
    els.footerButtons.forEach((btn) => {
        if (btn.classList.contains("o_skill_capture_stop")) {
            return;
        }
        if (busy && isFooterCancelButton(btn)) {
            btn.disabled = false;
            return;
        }
        btn.disabled = Boolean(busy);
    });
    if (busy) {
        bindStop(controller);
        bindFooterCancel(controller);
    }
}

function bindStop(controller) {
    const els = progressEls(controller);
    if (!els.stop) {
        return;
    }
    // Re-bind every busy cycle (modal DOM may be recreated).
    if (els.stop._pnsOpenapiStopHandler) {
        els.stop.removeEventListener("click", els.stop._pnsOpenapiStopHandler);
    }
    const handler = (ev) => {
        ev.preventDefault();
        ev.stopPropagation();
        requestCancel(controller);
    };
    els.stop._pnsOpenapiStopHandler = handler;
    els.stop.addEventListener("click", handler);
}

function bindFooterCancel(controller) {
    const els = progressEls(controller);
    const root = els.root;
    if (!root || root === document) {
        return;
    }
    if (root._pnsOpenapiFooterHandler) {
        root.removeEventListener("click", root._pnsOpenapiFooterHandler, true);
    }
    const handler = (ev) => {
        if (!controller._pnsOpenapiBusy) {
            return;
        }
        const btn = ev.target && ev.target.closest
            ? ev.target.closest("footer button")
            : null;
        if (!isFooterCancelButton(btn)) {
            return;
        }
        if (controller._pnsOpenapiAborted) {
            return;
        }
        ev.preventDefault();
        ev.stopPropagation();
        requestCancel(controller);
    };
    root._pnsOpenapiFooterHandler = handler;
    root.addEventListener("click", handler, true);
}

async function logUsage(controller, id, usage, status) {
    if (!id || !usageHasTokens(usage)) {
        return;
    }
    try {
        const orm = controller.env.services.orm;
        const call = (orm.silent && typeof orm.silent.call === "function")
            ? orm.silent.call.bind(orm.silent)
            : orm.call.bind(orm);
        await call(MODEL, "action_log_generation_usage", [id], {
            usage: usage,
            status: status,
        });
    } catch (err) {
        /* logging must not break the wizard */
    }
}

pnsPatch(FormController.prototype, "pns_ai_mcp.openapi_spec_generate_wizard", {
    async beforeExecuteActionButton(clickParams) {
        if (
            this.props.resModel === MODEL
            && clickParams
            && clickParams.name === "action_generate"
        ) {
            await this._pnsOpenapiGenerate();
            return false;
        }
        if (
            this.props.resModel === MODEL
            && this._pnsOpenapiBusy
            && clickParams
            && (clickParams.special === "cancel"
                || String(clickParams.special || "").toLowerCase() === "cancel")
        ) {
            if (this._pnsOpenapiAborted) {
                this._pnsOpenapiBusy = false;
                return super.beforeExecuteActionButton(clickParams);
            }
            await requestCancel(this);
            return false;
        }
        return super.beforeExecuteActionButton(clickParams);
    },

    async _pnsOpenapiGenerate() {
        if (this._pnsOpenapiBusy) {
            return;
        }
        this._pnsOpenapiBusy = true;
        this._pnsOpenapiAborted = false;
        this._pnsOpenapiUsage = {};
        this._pnsOpenapiWizardId = null;
        bindStop(this);
        bindFooterCancel(this);
        await setUsage(this, {});
        setBusy(this, true, _t("Saving…"));
        let id = null;
        try {
            await this.model.root.save({ reload: false, noInvalidCheck: false });
            if (this._pnsOpenapiAborted) {
                await closeWizard(this);
                return;
            }
            id = this.model.root.resId;
            this._pnsOpenapiWizardId = id;
            if (!id) {
                throw new Error(_t("Could not save the wizard."));
            }
            const orm = this.env.services.orm;
            const call = silentCall(orm);
            let lastResult;
            for (const step of openapiSteps()) {
                if (this._pnsOpenapiAborted) {
                    return;
                }
                setBusy(this, true, step.msg);
                lastResult = await call(MODEL, step.method, [id]);
                if (this._pnsOpenapiAborted) {
                    return;
                }
                if (lastResult && !lastResult.type && lastResult.usage) {
                    this._pnsOpenapiUsage = addUsage(
                        this._pnsOpenapiUsage, lastResult.usage);
                    await setUsage(this, this._pnsOpenapiUsage);
                }
                if (lastResult && lastResult.ok === false) {
                    if (lastResult.reload) {
                        await this.model.root.load();
                    }
                    setBusy(this, false);
                    return;
                }
                if (this._pnsOpenapiAborted) {
                    return;
                }
            }
            if (lastResult && lastResult.reload) {
                await this.model.root.load();
            }
            setBusy(this, false);
            if (this._pnsOpenapiUsage && usageHasTokens(this._pnsOpenapiUsage)) {
                await setUsage(this, this._pnsOpenapiUsage);
            }
        } catch (err) {
            if (!this._pnsOpenapiAborted) {
                await logUsage(this, id, this._pnsOpenapiUsage, "error");
            }
            try {
                await this.model.root.load();
            } catch (loadErr) {
                /* reload is best-effort: the draft may already be committed */
            }
            setBusy(this, false);
            if (!this._pnsOpenapiAborted) {
                throw err;
            }
        } finally {
            this._pnsOpenapiBusy = false;
        }
    },
});
