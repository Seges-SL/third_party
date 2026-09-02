/**
 * Chatboo reusable pick-list (checkboxes) — before the Safe Plan Confirm aviso.
 *
 * Shared owl1 / owl2. Host calls ChatbooChoiceList.show(evt, api).
 */
(function (global) {
    "use strict";

    function show(evt, api) {
        var t = api.t || function (s) { return s; };
        var choiceId = evt.choice_id;
        if (!choiceId) {
            return;
        }
        if (document.getElementById("pns_choice_" + choiceId)) {
            return;
        }
        var items = evt.items || [];
        var card = document.createElement("div");
        card.id = "pns_choice_" + choiceId;
        card.style.cssText = "position:fixed;right:24px;bottom:24px;z-index:20000;max-width:440px;max-height:70vh;overflow:auto;background:#fff;border:1px solid #1565c0;border-left:5px solid #1565c0;border-radius:8px;box-shadow:0 6px 24px rgba(0,0,0,.18);padding:14px 16px;font-family:system-ui,Segoe UI,sans-serif;font-size:13px;color:#222;";

        var title = document.createElement("div");
        title.style.cssText = "font-weight:700;margin-bottom:8px;color:#1565c0;";
        title.textContent = t("Choose views") + (evt.title ? (" — " + evt.title) : "");
        card.appendChild(title);

        var hint = document.createElement("div");
        hint.style.cssText = "margin-bottom:8px;color:#555;";
        hint.textContent = t("Mark the screens that should receive this change. Confirm comes next.");
        card.appendChild(hint);

        var box = document.createElement("div");
        box.style.cssText = "margin:8px 0;";
        var checks = [];
        items.forEach(function (item) {
            var row = document.createElement("label");
            row.style.cssText = "display:flex;align-items:flex-start;gap:8px;margin:4px 0;cursor:pointer;";
            var cb = document.createElement("input");
            cb.type = "checkbox";
            cb.value = String(item.id);
            cb.checked = !!item.selected;
            checks.push(cb);
            var lab = document.createElement("span");
            lab.textContent = (item.label || ("#" + item.id))
                + (item.type ? (" · " + item.type) : "")
                + " (#" + item.id + ")";
            row.appendChild(cb);
            row.appendChild(lab);
            box.appendChild(row);
        });
        card.appendChild(box);

        var toggleRow = document.createElement("div");
        toggleRow.style.cssText = "margin:8px 0;";
        var allBtn = document.createElement("button");
        allBtn.type = "button";
        allBtn.textContent = t("All");
        allBtn.style.cssText = "margin-right:8px;background:#eee;border:none;border-radius:4px;padding:4px 10px;cursor:pointer;";
        allBtn.addEventListener("click", function () {
            checks.forEach(function (c) { c.checked = true; });
        });
        var noneBtn = document.createElement("button");
        noneBtn.type = "button";
        noneBtn.textContent = t("None");
        noneBtn.style.cssText = "background:#eee;border:none;border-radius:4px;padding:4px 10px;cursor:pointer;";
        noneBtn.addEventListener("click", function () {
            checks.forEach(function (c) { c.checked = false; });
        });
        toggleRow.appendChild(allBtn);
        toggleRow.appendChild(noneBtn);
        card.appendChild(toggleRow);

        var status = document.createElement("div");
        status.style.cssText = "margin-top:8px;font-size:12px;";

        var acceptBtn = document.createElement("button");
        acceptBtn.textContent = t("Accept");
        acceptBtn.style.cssText = "background:#1565c0;color:#fff;border:none;border-radius:5px;padding:6px 14px;cursor:pointer;font-weight:600;margin-right:8px;";
        var cancelBtn = document.createElement("button");
        cancelBtn.textContent = t("Cancel");
        cancelBtn.style.cssText = "background:#eee;color:#333;border:none;border-radius:5px;padding:6px 14px;cursor:pointer;";

        function selectedIds() {
            return checks.filter(function (c) { return c.checked; }).map(function (c) {
                return parseInt(c.value, 10);
            });
        }

        acceptBtn.addEventListener("click", function () {
            acceptBtn.disabled = true;
            cancelBtn.disabled = true;
            status.textContent = t("Saving…");
            api.callJson("/pns_ai_mcp/choice/accept", {
                choice_id: choiceId,
                selected_ids: selectedIds(),
            }).then(function (res) {
                if (!res || res.success === false) {
                    status.style.color = "#c62828";
                    status.textContent = t("Error: ") + ((res && res.error) || "");
                    acceptBtn.disabled = false;
                    cancelBtn.disabled = false;
                    return;
                }
                card.remove();
                if (typeof api.onAccepted === "function") {
                    api.onAccepted(res);
                }
            }).catch(function (err) {
                status.style.color = "#c62828";
                status.textContent = t("Error: ") + err;
                acceptBtn.disabled = false;
                cancelBtn.disabled = false;
            });
        });

        cancelBtn.addEventListener("click", function () {
            acceptBtn.disabled = true;
            cancelBtn.disabled = true;
            api.callJson("/pns_ai_mcp/choice/cancel", { choice_id: choiceId })
                .then(function () {
                    card.remove();
                    if (typeof api.onCancelled === "function") {
                        api.onCancelled();
                    }
                })
                .catch(function () {
                    card.remove();
                });
        });

        var btnRow = document.createElement("div");
        btnRow.style.cssText = "margin-top:10px;";
        btnRow.appendChild(acceptBtn);
        btnRow.appendChild(cancelBtn);
        card.appendChild(btnRow);
        card.appendChild(status);
        document.body.appendChild(card);
    }

    global.ChatbooChoiceList = { show: show };
}(typeof globalThis !== "undefined" ? globalThis : window));
