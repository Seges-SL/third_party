/** @odoo-module **/
/**
 * Skill capture wizard: stepped AI pass with typing dots (Odoo 19).
 *
 * SPDX-License-Identifier: Apache-2.0
 * Copyright (C) 2026 Patanegra Soft <https://patanegra.com>
 */

import { FormController } from "@web/views/form/form_controller";
import { pnsPatch } from "@pns_base/js/pns_patch";
import { _t } from "@web/core/l10n/translation";
import {
    addUsage,
    findUsageElements,
    setUsageElementsWithFx,
    usageHasTokens,
} from "./ai_usage_chip";

const MODEL = "ai.skill.capture.wizard";

function captureSteps() {
    return [
        { msg: _t("Reading the parameters…"), method: "action_author_params" },
        { msg: _t("Writing the help text…"), method: "action_author_help" },
        { msg: _t("Checking the Code…"), method: "action_adapt_code" },
        { msg: _t("Saving the skill…"), method: "action_create_draft" },
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

async function setUsage(controller, usage) {
    const orm = controller.env.services.orm;
    await setUsageElementsWithFx(orm, progressRoot(controller), usage);
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
        els.dots.style.display = busy ? "" : "none";
    }
    if (els.stop) {
        els.stop.style.display = busy ? "" : "none";
        els.stop.disabled = !busy;
    }
    if (els.label && message) {
        els.label.textContent = message;
    }
    els.footerButtons.forEach((btn) => {
        if (btn.classList.contains("o_skill_capture_stop")) {
            return;
        }
        btn.disabled = Boolean(busy);
    });
}

function setCancelled(controller) {
    const els = progressEls(controller);
    if (els.box) {
        els.box.style.display = "flex";
    }
    if (els.dots) {
        els.dots.style.display = "none";
    }
    if (els.stop) {
        els.stop.style.display = "none";
        els.stop.disabled = true;
    }
    if (els.label) {
        els.label.textContent = _t("Cancelled.");
    }
    els.footerButtons.forEach((btn) => {
        btn.disabled = false;
    });
}

function bindStop(controller) {
    const els = progressEls(controller);
    if (!els.stop || els.stop.dataset.pnsBound) {
        return;
    }
    els.stop.dataset.pnsBound = "1";
    els.stop.addEventListener("click", (ev) => {
        ev.preventDefault();
        ev.stopPropagation();
        controller._pnsCaptureAborted = true;
    });
}

pnsPatch(FormController.prototype, "pns_ai_mcp.skill_capture_wizard", {
    async beforeExecuteActionButton(clickParams) {
        if (
            this.props.resModel === MODEL
            && clickParams
            && clickParams.name === "action_create_draft"
        ) {
            await this._pnsSkillCaptureCommit();
            return false;
        }
        return super.beforeExecuteActionButton(clickParams);
    },

    async _pnsSkillCaptureCommit() {
        if (this._pnsCaptureBusy) {
            return;
        }
        this._pnsCaptureBusy = true;
        this._pnsCaptureAborted = false;
        this._pnsCaptureUsage = {};
        bindStop(this);
        await setUsage(this, {});
        setBusy(this, true, _t("Keeping your edits…"));
        try {
            await this.model.root.save({ reload: false, noInvalidCheck: false });
            if (this._pnsCaptureAborted) {
                setCancelled(this);
                return;
            }
            const id = this.model.root.resId;
            if (!id) {
                throw new Error(_t("Could not save the wizard."));
            }
            let action;
            for (const step of captureSteps()) {
                if (this._pnsCaptureAborted) {
                    setCancelled(this);
                    return;
                }
                setBusy(this, true, step.msg);
                const kwargs = {};
                if (step.method === "action_create_draft") {
                    kwargs.context = Object.assign(
                        {},
                        this.props.context || {},
                        { skill_capture_authored: true },
                    );
                }
                const orm = this.env.services.orm;
                const call = (orm.silent && typeof orm.silent.call === "function")
                    ? orm.silent.call.bind(orm.silent)
                    : orm.call.bind(orm);
                action = await call(
                    MODEL,
                    step.method,
                    [id],
                    kwargs,
                );
                if (action && !action.type && action.usage) {
                    this._pnsCaptureUsage = addUsage(
                        this._pnsCaptureUsage, action.usage);
                    await setUsage(this, this._pnsCaptureUsage);
                }
                if (this._pnsCaptureAborted && !(action && action.type)) {
                    setCancelled(this);
                    return;
                }
            }
            setBusy(this, false);
            if (this._pnsCaptureUsage && usageHasTokens(this._pnsCaptureUsage)) {
                await setUsage(this, this._pnsCaptureUsage);
            }
            if (action && action.type) {
                await this.env.services.action.doAction(action);
            }
        } catch (err) {
            setBusy(this, false);
            throw err;
        } finally {
            this._pnsCaptureBusy = false;
        }
    },
});
