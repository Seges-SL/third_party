/**
 * Chatboo dashboard — draggable/closable cards for show_mode=dashboard.
 * Persists layout in localStorage (per dashboard id). Charts hydrate via ChatbooCharts.
 * SPDX-License-Identifier: Apache-2.0
 */
(function (global) {
    "use strict";

    var STORAGE_PREFIX = "chatboo_dash_v1_";

    function storageKey(dashboardId) {
        return STORAGE_PREFIX + (dashboardId || "default");
    }

    function readLayout(dashboardId) {
        try {
            var raw = global.localStorage.getItem(storageKey(dashboardId));
            if (!raw) {
                return null;
            }
            var data = JSON.parse(raw);
            if (!data || typeof data !== "object") {
                return null;
            }
            return data;
        } catch (e) {
            return null;
        }
    }

    function writeLayout(dashboardId, layout) {
        try {
            global.localStorage.setItem(
                storageKey(dashboardId),
                JSON.stringify(layout)
            );
        } catch (e) {
            /* quota / private mode */
        }
    }

    function cardIds(grid) {
        var cards = grid.querySelectorAll(".o_chatboo_dashboard_card");
        var ids = [];
        var i;
        for (i = 0; i < cards.length; i++) {
            ids.push(cards[i].getAttribute("data-card-id") || "");
        }
        return ids;
    }

    function collectLayout(dashboard) {
        var grid = dashboard.querySelector(".o_chatboo_dashboard_grid");
        if (!grid) {
            return { order: [], hidden: [], collapsed: [] };
        }
        var hidden = [];
        var collapsed = [];
        var cards = grid.querySelectorAll(".o_chatboo_dashboard_card");
        var i;
        for (i = 0; i < cards.length; i++) {
            var c = cards[i];
            var id = c.getAttribute("data-card-id");
            if (!id) {
                continue;
            }
            if (c.classList.contains("o_chatboo_dashboard_card_hidden")) {
                hidden.push(id);
            }
            if (c.classList.contains("o_chatboo_dashboard_card_collapsed")) {
                collapsed.push(id);
            }
        }
        return {
            order: cardIds(grid),
            hidden: hidden,
            collapsed: collapsed,
        };
    }

    function applyLayout(dashboard, layout) {
        if (!layout) {
            return;
        }
        var grid = dashboard.querySelector(".o_chatboo_dashboard_grid");
        if (!grid) {
            return;
        }
        var byId = {};
        var cards = grid.querySelectorAll(".o_chatboo_dashboard_card");
        var i;
        for (i = 0; i < cards.length; i++) {
            var id = cards[i].getAttribute("data-card-id");
            if (id) {
                byId[id] = cards[i];
            }
        }
        if (layout.order && layout.order.length) {
            for (i = 0; i < layout.order.length; i++) {
                var card = byId[layout.order[i]];
                if (card) {
                    grid.appendChild(card);
                }
            }
        }
        for (i = 0; i < cards.length; i++) {
            var node = cards[i];
            var cid = node.getAttribute("data-card-id");
            node.classList.toggle(
                "o_chatboo_dashboard_card_hidden",
                layout.hidden && layout.hidden.indexOf(cid) >= 0
            );
            node.classList.toggle(
                "o_chatboo_dashboard_card_collapsed",
                layout.collapsed && layout.collapsed.indexOf(cid) >= 0
            );
            var collapseBtn = node.querySelector(".o_chatboo_dashboard_collapse");
            if (collapseBtn) {
                var isCollapsed = node.classList.contains(
                    "o_chatboo_dashboard_card_collapsed"
                );
                collapseBtn.setAttribute(
                    "aria-expanded",
                    isCollapsed ? "false" : "true"
                );
            }
            syncCardChrome(node);
        }
    }

    function saveLayout(dashboard) {
        var id = dashboard.getAttribute("data-chatboo-dashboard-id");
        writeLayout(id, collectLayout(dashboard));
    }

    function cardTitle(card) {
        var titleEl = card.querySelector(".o_chatboo_dashboard_card_title");
        return titleEl ? (titleEl.textContent || "").trim() : "";
    }

    function mdiSvg(kind) {
        var common =
            'xmlns="http://www.w3.org/2000/svg" width="11" height="11" ' +
            'viewBox="0 0 11 11" aria-hidden="true" focusable="false"';
        if (kind === "min") {
            // Raya inferior — minimizar MDI.
            return (
                "<svg " + common + ">" +
                '<rect x="1" y="8" width="9" height="1.6" fill="currentColor"/>' +
                "</svg>"
            );
        }
        if (kind === "max") {
            // Cuadrado vacío — maximizar.
            return (
                "<svg " + common + ">" +
                '<rect x="1.2" y="1.2" width="8.6" height="8.6" fill="none" ' +
                'stroke="currentColor" stroke-width="1.5"/>' +
                "</svg>"
            );
        }
        if (kind === "restore") {
            // Dos cuadrados solapados — restaurar tamaño estándar.
            return (
                "<svg " + common + ">" +
                '<rect x="3" y="1" width="7" height="7" fill="none" ' +
                'stroke="currentColor" stroke-width="1.3"/>' +
                '<rect x="1" y="3" width="7" height="7" fill="#e8e8e8" ' +
                'stroke="currentColor" stroke-width="1.3"/>' +
                "</svg>"
            );
        }
        // Cerrar ×
        return (
            "<svg " + common + ">" +
            '<path d="M2 2 L9 9 M9 2 L2 9" fill="none" stroke="currentColor" ' +
            'stroke-width="1.6" stroke-linecap="square"/>' +
            "</svg>"
        );
    }

    function makeWinButton(cls, title) {
        var btn = global.document.createElement("button");
        btn.type = "button";
        btn.className = "o_chatboo_dashboard_winbtn " + cls;
        btn.setAttribute("title", title);
        btn.setAttribute("aria-label", title);
        return btn;
    }

    function ensureCardChrome(card) {
        if (!card) {
            return;
        }
        var actions = card.querySelector(".o_chatboo_dashboard_card_actions");
        if (!actions) {
            return;
        }
        actions.classList.add("o_chatboo_dashboard_mdi");

        var collapse = actions.querySelector(".o_chatboo_dashboard_collapse");
        var maximize = actions.querySelector(".o_chatboo_dashboard_maximize");
        var closeBtn = actions.querySelector(".o_chatboo_dashboard_close");

        if (!collapse) {
            collapse = makeWinButton(
                "o_chatboo_dashboard_collapse",
                "Minimizar"
            );
        } else {
            collapse.classList.add("o_chatboo_dashboard_winbtn");
            collapse.classList.remove("btn", "btn-sm", "btn-link");
        }
        if (!maximize) {
            maximize = makeWinButton(
                "o_chatboo_dashboard_maximize",
                "Maximizar"
            );
        } else {
            maximize.classList.add("o_chatboo_dashboard_winbtn");
            maximize.classList.remove("btn", "btn-sm", "btn-link");
        }
        if (!closeBtn) {
            closeBtn = makeWinButton("o_chatboo_dashboard_close", "Cerrar");
        } else {
            closeBtn.classList.add("o_chatboo_dashboard_winbtn");
            closeBtn.classList.remove("btn", "btn-sm", "btn-link");
        }

        // Orden MDI: minimizar · maximizar/restaurar · cerrar.
        actions.appendChild(collapse);
        actions.appendChild(maximize);
        actions.appendChild(closeBtn);
        syncCardChrome(card);
    }

    function syncCardChrome(card) {
        if (!card) {
            return;
        }
        var collapse = card.querySelector(".o_chatboo_dashboard_collapse");
        var maximize = card.querySelector(".o_chatboo_dashboard_maximize");
        var closeBtn = card.querySelector(".o_chatboo_dashboard_close");
        var collapsed = card.classList.contains(
            "o_chatboo_dashboard_card_collapsed"
        );
        var maximized = card.classList.contains(
            "o_chatboo_dashboard_card_maximized"
        );

        if (collapse) {
            collapse.innerHTML = mdiSvg("min");
            var minTitle = collapsed ? "Restaurar" : "Minimizar";
            collapse.setAttribute("title", minTitle);
            collapse.setAttribute("aria-label", minTitle);
            collapse.setAttribute("aria-expanded", collapsed ? "false" : "true");
        }
        if (maximize) {
            if (maximized) {
                maximize.innerHTML = mdiSvg("restore");
                maximize.setAttribute("title", "Tamaño estándar");
                maximize.setAttribute("aria-label", "Tamaño estándar");
                maximize.setAttribute("aria-expanded", "true");
            } else {
                maximize.innerHTML = mdiSvg("max");
                maximize.setAttribute("title", "Maximizar");
                maximize.setAttribute("aria-label", "Maximizar");
                maximize.setAttribute("aria-expanded", "false");
            }
        }
        if (closeBtn) {
            closeBtn.innerHTML = mdiSvg("close");
            closeBtn.setAttribute("title", "Cerrar");
            closeBtn.setAttribute("aria-label", "Cerrar");
        }
    }

    function ensureAllCardChrome(dashboard) {
        var cards = dashboard.querySelectorAll(".o_chatboo_dashboard_card");
        var i;
        for (i = 0; i < cards.length; i++) {
            ensureCardChrome(cards[i]);
        }
    }

    function hiddenTrayEl(dashboard) {
        var toolbar = dashboard.querySelector(".o_chatboo_dashboard_toolbar");
        if (!toolbar) {
            return null;
        }
        var tray = toolbar.querySelector(".o_chatboo_dashboard_hidden_tray");
        if (!tray) {
            tray = global.document.createElement("div");
            tray.className = "o_chatboo_dashboard_hidden_tray o_chatboo_noexport";
            toolbar.insertBefore(tray, toolbar.firstChild);
        }
        return tray;
    }

    function restoreCard(dashboard, card) {
        if (!card) {
            return;
        }
        card.classList.remove("o_chatboo_dashboard_card_hidden");
        saveLayout(dashboard);
        syncHiddenTray(dashboard);
        if (global.ChatbooCharts && typeof global.ChatbooCharts.hydrate === "function") {
            global.ChatbooCharts.hydrate(card);
        }
        resizeChartsIn(dashboard);
    }

    function showAllHiddenCards(dashboard) {
        var cards = dashboard.querySelectorAll(
            ".o_chatboo_dashboard_card.o_chatboo_dashboard_card_hidden"
        );
        var i;
        for (i = 0; i < cards.length; i++) {
            cards[i].classList.remove("o_chatboo_dashboard_card_hidden");
        }
        saveLayout(dashboard);
        syncHiddenTray(dashboard);
        if (global.ChatbooCharts && typeof global.ChatbooCharts.hydrate === "function") {
            global.ChatbooCharts.hydrate(dashboard);
        }
        resizeChartsIn(dashboard);
    }

    function syncHiddenTray(dashboard) {
        var tray = hiddenTrayEl(dashboard);
        if (!tray) {
            return;
        }
        var hidden = dashboard.querySelectorAll(
            ".o_chatboo_dashboard_card.o_chatboo_dashboard_card_hidden"
        );
        while (tray.firstChild) {
            tray.removeChild(tray.firstChild);
        }
        if (!hidden.length) {
            tray.classList.remove("o_chatboo_dashboard_hidden_tray_visible");
            return;
        }
        tray.classList.add("o_chatboo_dashboard_hidden_tray_visible");

        var label = global.document.createElement("span");
        label.className = "o_chatboo_dashboard_hidden_label";
        label.textContent = "Tarjetas ocultas:";
        tray.appendChild(label);

        var i;
        for (i = 0; i < hidden.length; i++) {
            (function (card) {
                var btn = global.document.createElement("button");
                btn.type = "button";
                btn.className = "btn btn-sm btn-outline-secondary o_chatboo_dashboard_restore";
                btn.setAttribute("title", "Mostrar de nuevo");
                btn.textContent = cardTitle(card) || card.getAttribute("data-card-id") || "Tarjeta";
                btn.addEventListener("click", function (ev) {
                    ev.preventDefault();
                    restoreCard(dashboard, card);
                });
                tray.appendChild(btn);
            })(hidden[i]);
        }

        var showAll = global.document.createElement("button");
        showAll.type = "button";
        showAll.className = "btn btn-sm btn-link o_chatboo_dashboard_show_all";
        showAll.textContent = "Mostrar todas";
        showAll.addEventListener("click", function (ev) {
            ev.preventDefault();
            showAllHiddenCards(dashboard);
        });
        tray.appendChild(showAll);
    }

    function demaximizeAll(dashboard, except) {
        var cards = dashboard.querySelectorAll(
            ".o_chatboo_dashboard_card.o_chatboo_dashboard_card_maximized"
        );
        var i;
        for (i = 0; i < cards.length; i++) {
            if (cards[i] !== except) {
                setCardMaximized(dashboard, cards[i], false);
            }
        }
    }

    function setCardMaximized(dashboard, card, maximized) {
        if (!card) {
            return;
        }
        if (maximized) {
            demaximizeAll(dashboard, card);
            card.classList.remove("o_chatboo_dashboard_card_collapsed");
            card.classList.add("o_chatboo_dashboard_card_maximized");
            if (card.scrollIntoView) {
                card.scrollIntoView({ behavior: "smooth", block: "nearest" });
            }
        } else {
            card.classList.remove("o_chatboo_dashboard_card_maximized");
        }
        syncCardChrome(card);
        if (global.ChatbooCharts && typeof global.ChatbooCharts.hydrate === "function") {
            global.ChatbooCharts.hydrate(card);
        }
        resizeChartsIn(dashboard);
    }

    function resetLayout(dashboard) {
        var id = dashboard.getAttribute("data-chatboo-dashboard-id");
        try {
            global.localStorage.removeItem(storageKey(id));
        } catch (e) {
            /* ignore */
        }
        var cards = dashboard.querySelectorAll(".o_chatboo_dashboard_card");
        var i;
        for (i = 0; i < cards.length; i++) {
            cards[i].classList.remove("o_chatboo_dashboard_card_hidden");
            cards[i].classList.remove("o_chatboo_dashboard_card_collapsed");
            cards[i].classList.remove("o_chatboo_dashboard_card_maximized");
        }
        ensureAllCardChrome(dashboard);
        syncHiddenTray(dashboard);
        if (global.ChatbooCharts && typeof global.ChatbooCharts.hydrate === "function") {
            global.ChatbooCharts.hydrate(dashboard);
        }
        // Diferir relayout: el grid ya no está maximizado y hay que recalcular alturas.
        setTimeout(function () {
            resizeChartsIn(dashboard);
        }, 0);
        setTimeout(function () {
            if (global.ChatbooCharts && typeof global.ChatbooCharts.softResize === "function") {
                global.ChatbooCharts.softResize(dashboard);
            } else {
                resizeChartsIn(dashboard);
            }
        }, 120);
    }

    function visibleCards(grid, except) {
        var nodes = grid.querySelectorAll(
            ".o_chatboo_dashboard_card:not(.o_chatboo_dashboard_card_hidden)"
        );
        var out = [];
        var i;
        for (i = 0; i < nodes.length; i++) {
            if (nodes[i] !== except) {
                out.push(nodes[i]);
            }
        }
        return out;
    }

    function cardsInReadingOrder(grid, except) {
        var cards = visibleCards(grid, except);
        cards.sort(function (a, b) {
            var ra = a.getBoundingClientRect();
            var rb = b.getBoundingClientRect();
            if (Math.abs(ra.top - rb.top) > 16) {
                return ra.top - rb.top;
            }
            return ra.left - rb.left;
        });
        return cards;
    }

    function insertBeforeReadingPoint(grid, placeholder, dragCard, clientX, clientY) {
        var cards = cardsInReadingOrder(grid, dragCard);
        var i;
        for (i = 0; i < cards.length; i++) {
            var rect = cards[i].getBoundingClientRect();
            var cx = rect.left + rect.width / 2;
            var cy = rect.top + rect.height / 2;
            if (clientY < cy - 4) {
                grid.insertBefore(placeholder, cards[i]);
                return;
            }
            if (
                clientY <= cy + rect.height * 0.45 &&
                clientX < cx
            ) {
                grid.insertBefore(placeholder, cards[i]);
                return;
            }
        }
        grid.appendChild(placeholder);
    }

    function copySpanClasses(fromNode, toNode) {
        toNode.classList.toggle(
            "o_chatboo_dashboard_card_span2",
            fromNode.classList.contains("o_chatboo_dashboard_card_span2")
        );
    }

    function finishPointerDrag(dashboard, grid, state) {
        if (!state) {
            return;
        }
        var card = state.card;
        var placeholder = state.placeholder;
        card.classList.remove(
            "o_chatboo_dashboard_card_dragging",
            "o_chatboo_dashboard_card_floating"
        );
        card.style.position = "";
        card.style.left = "";
        card.style.top = "";
        card.style.width = "";
        card.style.height = "";
        card.style.margin = "";
        card.style.zIndex = "";
        if (placeholder && placeholder.parentNode === grid) {
            grid.insertBefore(card, placeholder);
            placeholder.parentNode.removeChild(placeholder);
        }
        global.document.removeEventListener("pointermove", state.onMove);
        global.document.removeEventListener("pointerup", state.onUp);
        global.document.removeEventListener("pointercancel", state.onUp);
        if (state.header && state.header.releasePointerCapture) {
            try {
                state.header.releasePointerCapture(state.pointerId);
            } catch (e) {
                /* ignore */
            }
        }
        saveLayout(dashboard);
        resizeChartsIn(dashboard);
    }

    function setupDragDrop(dashboard, grid) {
        var active = null;

        function onMove(ev) {
            if (!active || ev.pointerId !== active.pointerId) {
                return;
            }
            ev.preventDefault();
            var card = active.card;
            card.style.left = ev.clientX - active.offsetX + "px";
            card.style.top = ev.clientY - active.offsetY + "px";
            insertBeforeReadingPoint(
                grid,
                active.placeholder,
                card,
                ev.clientX,
                ev.clientY
            );
        }

        function onUp(ev) {
            if (!active || ev.pointerId !== active.pointerId) {
                return;
            }
            ev.preventDefault();
            var state = active;
            active = null;
            finishPointerDrag(dashboard, grid, state);
        }

        grid.addEventListener("pointerdown", function (ev) {
            if (ev.button !== 0 || active) {
                return;
            }
            var header = ev.target.closest(".o_chatboo_dashboard_card_header");
            if (!header || ev.target.closest("button")) {
                return;
            }
            var card = header.closest(".o_chatboo_dashboard_card");
            if (
                !card ||
                card.classList.contains("o_chatboo_dashboard_card_hidden")
            ) {
                return;
            }
            if (card.classList.contains("o_chatboo_dashboard_card_maximized")) {
                setCardMaximized(dashboard, card, false);
            }
            ev.preventDefault();
            card.setAttribute("draggable", "false");

            var rect = card.getBoundingClientRect();
            var placeholder = global.document.createElement("div");
            placeholder.className = "o_chatboo_dashboard_placeholder";
            placeholder.setAttribute("aria-hidden", "true");
            copySpanClasses(card, placeholder);
            placeholder.style.minHeight = Math.max(rect.height, 120) + "px";
            grid.insertBefore(placeholder, card);

            card.classList.add(
                "o_chatboo_dashboard_card_dragging",
                "o_chatboo_dashboard_card_floating"
            );
            card.style.width = rect.width + "px";
            card.style.height = rect.height + "px";
            card.style.left = rect.left + "px";
            card.style.top = rect.top + "px";

            active = {
                card: card,
                placeholder: placeholder,
                header: header,
                pointerId: ev.pointerId,
                offsetX: ev.clientX - rect.left,
                offsetY: ev.clientY - rect.top,
                onMove: onMove,
                onUp: onUp,
            };

            if (header.setPointerCapture) {
                header.setPointerCapture(ev.pointerId);
            }
            global.document.addEventListener("pointermove", onMove);
            global.document.addEventListener("pointerup", onUp);
            global.document.addEventListener("pointercancel", onUp);
        });

        var initCards = grid.querySelectorAll(".o_chatboo_dashboard_card");
        var ci;
        for (ci = 0; ci < initCards.length; ci++) {
            initCards[ci].setAttribute("draggable", "false");
        }
    }

    function bindCardActions(dashboard) {
        dashboard.addEventListener("click", function (ev) {
            var closeBtn = ev.target.closest(".o_chatboo_dashboard_close");
            if (closeBtn) {
                var cardClose = closeBtn.closest(".o_chatboo_dashboard_card");
                if (cardClose) {
                    cardClose.classList.add("o_chatboo_dashboard_card_hidden");
                    saveLayout(dashboard);
                    syncHiddenTray(dashboard);
                }
                return;
            }
            var collapseBtn = ev.target.closest(".o_chatboo_dashboard_collapse");
            if (collapseBtn) {
                var cardCol = collapseBtn.closest(".o_chatboo_dashboard_card");
                if (!cardCol) {
                    return;
                }
                if (cardCol.classList.contains("o_chatboo_dashboard_card_maximized")) {
                    setCardMaximized(dashboard, cardCol, false);
                }
                var collapsed = cardCol.classList.toggle(
                    "o_chatboo_dashboard_card_collapsed"
                );
                syncCardChrome(cardCol);
                saveLayout(dashboard);
                if (!collapsed && global.ChatbooCharts) {
                    global.ChatbooCharts.hydrate(cardCol);
                }
                return;
            }
            var maxBtn = ev.target.closest(".o_chatboo_dashboard_maximize");
            if (maxBtn) {
                var cardMax = maxBtn.closest(".o_chatboo_dashboard_card");
                if (!cardMax) {
                    return;
                }
                var willMax = !cardMax.classList.contains(
                    "o_chatboo_dashboard_card_maximized"
                );
                setCardMaximized(dashboard, cardMax, willMax);
                return;
            }
            var resetBtn = ev.target.closest(".o_chatboo_dashboard_reset");
            if (resetBtn) {
                resetLayout(dashboard);
            }
        });
    }

    function resizeChartsIn(dashboard) {
        if (!dashboard || !dashboard.querySelectorAll) {
            return;
        }
        if (global.ChatbooCharts && typeof global.ChatbooCharts.relayout === "function") {
            global.ChatbooCharts.relayout(dashboard);
            return;
        }
        var blocks = dashboard.querySelectorAll(".o_chatboo_table_block");
        var i;
        for (i = 0; i < blocks.length; i++) {
            var block = blocks[i];
            if (block._chatbooChart && typeof block._chatbooChart.resize === "function") {
                try {
                    block._chatbooChart.resize();
                } catch (e) {
                    /* ignore */
                }
            }
        }
    }

    function expandMessageCanvas(dashboard) {
        var bubble = dashboard.closest(".o_chatboo_message, .o_chatboo_bubble");
        if (bubble) {
            bubble.classList.add("o_chatboo_message--dashboard");
            bubble.style.maxWidth = "100%";
            bubble.style.width = "100%";
        }
        var row = dashboard.closest(".d-flex");
        if (row) {
            row.classList.add("o_chatboo_message_row--dashboard");
            row.style.width = "100%";
            row.style.maxWidth = "100%";
        }
    }

    function syncGridColumnMin(grid) {
        var w = grid.clientWidth || 0;
        if (w <= 0) {
            return;
        }
        /* Objetivo ~3 columnas en canvas ancho; mínimo 280px por celda. */
        var minCol = Math.max(280, Math.min(380, Math.floor(w / 3)));
        grid.style.setProperty("--chatboo-dash-col-min", minCol + "px");
    }

    function observeDashboardResize(dashboard, grid) {
        if (dashboard._chatbooDashboardRO) {
            return;
        }
        if (typeof global.ResizeObserver === "undefined") {
            return;
        }
        var scheduled = null;
        var ro = new global.ResizeObserver(function () {
            // Nunca mutar layout dentro del callback del RO (provoca
            // "ResizeObserver loop completed with undelivered notifications").
            if (scheduled !== null) {
                return;
            }
            scheduled = global.setTimeout(function () {
                scheduled = null;
                syncGridColumnMin(grid);
                if (
                    global.ChatbooCharts &&
                    typeof global.ChatbooCharts.softResize === "function"
                ) {
                    global.ChatbooCharts.softResize(dashboard);
                } else {
                    softResizeFallback(dashboard);
                }
            }, 0);
        });
        ro.observe(grid);
        dashboard._chatbooDashboardRO = ro;
        syncGridColumnMin(grid);
    }

    function softResizeFallback(dashboard) {
        var blocks = dashboard.querySelectorAll(".o_chatboo_table_block");
        var i;
        for (i = 0; i < blocks.length; i++) {
            var block = blocks[i];
            if (block._chatbooChart && typeof block._chatbooChart.resize === "function") {
                try {
                    block._chatbooChart.resize();
                } catch (e) {
                    /* ignore */
                }
            }
        }
    }

    function hydrateDashboard(dashboard) {
        if (
            !dashboard ||
            dashboard.getAttribute("data-chatboo-dashboard-ready") === "1"
        ) {
            return;
        }
        var grid = dashboard.querySelector(".o_chatboo_dashboard_grid");
        if (!grid) {
            return;
        }
        expandMessageCanvas(dashboard);
        var dashId = dashboard.getAttribute("data-chatboo-dashboard-id");
        applyLayout(dashboard, readLayout(dashId));
        ensureAllCardChrome(dashboard);
        syncHiddenTray(dashboard);
        setupDragDrop(dashboard, grid);
        bindCardActions(dashboard);
        observeDashboardResize(dashboard, grid);
        dashboard.setAttribute("data-chatboo-dashboard-ready", "1");
        if (global.ChatbooCharts && typeof global.ChatbooCharts.hydrate === "function") {
            global.ChatbooCharts.hydrate(dashboard);
        }
        resizeChartsIn(dashboard);
        // Segundo pase tras layout del mensaje/grid (chart-table suele medir mal al 1º).
        setTimeout(function () {
            resizeChartsIn(dashboard);
            if (
                global.ChatbooCharts &&
                typeof global.ChatbooCharts.softResize === "function"
            ) {
                global.ChatbooCharts.softResize(dashboard);
            }
        }, 200);
    }

    function hydrateRoot(root) {
        if (!root || !root.querySelectorAll) {
            return;
        }
        var boards = root.querySelectorAll(".o_chatboo_dashboard");
        var i;
        for (i = 0; i < boards.length; i++) {
            hydrateDashboard(boards[i]);
        }
    }

    function destroyInRoot(root) {
        if (!root || !root.querySelectorAll) {
            return;
        }
        var boards = root.querySelectorAll(".o_chatboo_dashboard");
        var i;
        for (i = 0; i < boards.length; i++) {
            if (boards[i]._chatbooDashboardRO) {
                boards[i]._chatbooDashboardRO.disconnect();
                boards[i]._chatbooDashboardRO = null;
            }
            boards[i].removeAttribute("data-chatboo-dashboard-ready");
        }
        if (global.ChatbooCharts && typeof global.ChatbooCharts.destroyIn === "function") {
            global.ChatbooCharts.destroyIn(root);
        }
    }

    function hydrateContent(root) {
        hydrateRoot(root);
        if (global.ChatbooCharts && typeof global.ChatbooCharts.hydrate === "function") {
            global.ChatbooCharts.hydrate(root);
        }
        if (global.ChatbooSvgCards && typeof global.ChatbooSvgCards.hydrate === "function") {
            global.ChatbooSvgCards.hydrate(root);
        }
    }

    global.ChatbooDashboard = {
        hydrate: hydrateRoot,
        hydrateContent: hydrateContent,
        destroyIn: destroyInRoot,
    };
})(typeof window !== "undefined" ? window : this);
