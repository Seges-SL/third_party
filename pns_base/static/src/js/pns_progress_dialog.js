/** @odoo-module **/
/* SPDX-License-Identifier: Apache-2.0
 * Copyright (C) 2026 Patanegra Soft <https://patanegra.com>
 */

// Follows a pns.progress.job: live step and bar, then the summary the job wrote.

import { Component, onWillStart, onWillUnmount, useState } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

const POLL_MS = 800;
const RETRY_MS = 3000;

export class PnsProgressDialog extends Component {
    static template = "pns_base.ProgressDialog";
    static components = { Dialog };
    static props = {
        jobId: { type: Number },
        title: { type: String, optional: true },
        doneAction: { type: [String, Boolean], optional: true },
        doneLabel: { type: [String, Boolean], optional: true },
        close: { type: Function },
    };

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.state = useState({ data: null });
        this._stopped = false;
        this._timer = null;
        onWillStart(() => {
            this._poll();
        });
        onWillUnmount(() => {
            this._stopped = true;
            clearTimeout(this._timer);
        });
    }

    get data() {
        return this.state.data;
    }

    get running() {
        const data = this.state.data;
        return !data || data.state === "queued" || data.state === "running";
    }

    get progress() {
        return this.state.data ? this.state.data.progress : 0;
    }

    async _poll() {
        if (this._stopped) {
            return;
        }
        let delay = POLL_MS;
        try {
            this.state.data = await this.orm.silent.call(
                "pns.progress.job", "read_progress", [[this.props.jobId]]
            );
        } catch {
            delay = RETRY_MS;
        }
        if (!this._stopped && this.running) {
            this._timer = setTimeout(() => this._poll(), delay);
        }
    }

    onClose() {
        this.props.close();
    }

    async onDone() {
        const action = this.props.doneAction;
        this.props.close();
        await this.action.doAction(action);
    }
}

registry.category("actions").add("pns_progress_dialog", async (env, action) => {
    const params = action.params || {};
    if (!params.job_id) {
        return;
    }
    await env.services.action.doAction({ type: "ir.actions.act_window_close" });
    env.services.dialog.add(PnsProgressDialog, {
        jobId: params.job_id,
        title: action.name || "",
        doneAction: params.done_action || false,
        doneLabel: params.done_label || false,
    });
});
