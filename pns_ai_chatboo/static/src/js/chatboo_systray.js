/* SPDX-License-Identifier: Apache-2.0 */
/* Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com> */
/**
 * Chatboo systray launcher (OWL1). Opens the floating overlay, not a client action.
 */
odoo.define('pns_ai_chatboo.chatboo_systray', function (require) {
    "use strict";

    var SystrayMenu = require('web.SystrayMenu');
    var Widget = require('web.Widget');
    var ActionManager = require('web.ActionManager');
    var core = require('web.core');
    var session = require('web.session');
    var _t = core._t;

    var CHATBOO_CLIENT_TAGS = {
        'chatboo.action': true,
        'chatboo.history.action': true,
        'chatboo.new.action': true,
    };

    var ChatbooSystrayItem = Widget.extend({
        template: 'pns_ai_chatboo.chatboo_systray_item',
        events: {
            'click': '_onClick',
        },

        init: function () {
            this._super.apply(this, arguments);
            this._hasAccess = false;
        },

        start: function () {
            var self = this;
            this.el.style.display = 'none';
            this.$el.addClass('o_chatboo_systray_item');
            // App click llega por ActionManager, no por el icono. El listener
            // vive aquí (no solo en _enableSystray) para que el overlay abra
            // aunque el flag del tray esté apagado.
            core.bus.on('chatboo_overlay_show', this, function (context) {
                self._showOverlay(context || {});
            });
            // A shared page reaches users without Chatboo too: listen before
            // the access check. Chat replies still need access (_hasAccess).
            this.call('bus_service', 'onNotification', this, this._onBusNotifications);

            return this._super.apply(this, arguments).then(function () {
                if (session.pns_chatboo_show_systray) {
                    self._enableSystray();
                    return;
                }
            });
        },

        /**
         * Muestra el icono y engancha los listeners. Idempotente: si ya se
         * activó, no repite el trabajo (puede llamarse desde el then o el catch).
         */
        _enableSystray: function () {
            var self = this;
            if (this._hasAccess) {
                return;
            }
            this.el.style.display = '';
            this._hasAccess = true;

            // Listen for SSE response completion (badge when overlay hidden)
            core.bus.on('chatboo_response_ready', this, function (payload) {
                var isError = payload && payload.isError;
                if (isError) {
                    self._showBadge('error');
                } else {
                    self._refreshAuthCue({ fallbackUnread: true });
                }
            });

            core.bus.on('chatboo_auth_cue', this, function (payload) {
                self._refreshAuthCue(payload || {});
            });

            this._refreshAuthCue({ notify: false }).then(function (hadAuth) {
                if (hadAuth) {
                    return;
                }
                var storedBadge = localStorage.getItem('chatboo_unread');
                if (storedBadge) {
                    self._showBadge(storedBadge === 'error' ? 'error' : 'info');
                }
            });

            // Delegated handler: "Open Chatboo" button in notification channels
            $(document).on('click.chatboo_systray', '.o_chatboo_dismiss_btn', function (ev) {
                ev.preventDefault();
                ev.stopPropagation();

                var $chatWin = $(ev.target).closest(
                    '.o_ChatWindow,' +
                    '.o_mail_chat_window,' +
                    '.o_thread_window,' +
                    '.o_mail_messaging_widget'
                );
                if ($chatWin.length) {
                    var $closeBtn = $chatWin.find(
                        '.o_ChatWindowHeader_commandClose,' +
                        '.o_mail_chat_window_close_button,' +
                        '.o_thread_window_close,' +
                        '[class*="commandClose"]'
                    ).first();
                    if ($closeBtn.length) {
                        $closeBtn.trigger('click');
                    } else {
                        $chatWin.fadeOut(150, function () { $chatWin.remove(); });
                    }
                } else {
                    $('.o_ChatWindow, .o_mail_chat_window, .o_thread_window').each(function () {
                        var $w = $(this);
                        if ($w.find('.o_chatboo_dismiss_btn').length) {
                            $w.fadeOut(150, function () { $w.remove(); });
                        }
                    });
                }

                self._rpc({ route: '/chatboo/dismiss_messages', params: {} })
                    .catch(function () { });

                var isOnChatboo = !!document.querySelector('.o_chatboo_container');
                if (!isOnChatboo) {
                    var btnHref = $(ev.target).closest('a').attr('href') || '/chatboo/dismiss_notification';
                    window.open(btnHref, '_blank', 'noopener');
                }
            });
        },

        destroy: function () {
            $(document).off('click.chatboo_systray');
            this._super.apply(this, arguments);
        },

        // ── Bus notification handler ──
        _onBusNotifications: function (notifications) {
            if (!notifications || !Array.isArray(notifications)) return;
            for (var i = 0; i < notifications.length; i++) {
                var notif = notifications[i];
                var payload = null;

                if (Array.isArray(notif) && notif.length === 2) {
                    payload = notif[1];
                } else if (notif && typeof notif === 'object') {
                    payload = notif;
                }

                if (typeof payload === 'string') {
                    try { payload = JSON.parse(payload); } catch (_) { continue; }
                }

                if (payload && payload.action === 'page_shared') {
                    this._showSharedPage(payload);
                    continue;
                }
                if (!this._hasAccess) {
                    continue;
                }
                if (payload && typeof payload === 'object') {
                    var _isAsyncDone = payload.type === 'pns_chatboo_async_done'
                        || (payload.type === 'pns_chatboo_sync'
                            && (payload.action === 'async_done' || payload.action === 'error'));
                    if (_isAsyncDone) {
                        // Con auto-promoción todos los turnos avisan por bus; solo
                        // molestamos (campanita) si el overlay está oculto o
                        // si hubo error. Si lo estás viendo en vivo, silencio.
                        var _isErr = payload.is_error || payload.action === 'error';
                        if (_isErr) {
                            this._showBadge('error');
                            this._onAsyncDone(payload);
                        } else if (this._isOverlayHidden()) {
                            this._onAsyncDone(payload);
                        }
                    }
                }
            }
        },

        _onAsyncDone: function (payload) {
            var isErr = payload && (payload.is_error || payload.action === 'error');
            core.bus.trigger('chatboo_async_done', payload);
            if (isErr) {
                this._showChatbooNotification();
                this._showBadge('error');
            } else {
                this._refreshAuthCue({ notify: true, fallbackUnread: true });
            }

            try {
                core.bus.trigger('update_message_number');
            } catch (e) {
                console.warn("Could not auto-refresh Odoo notification badge", e);
            }
        },

        _isOverlayHidden: function () {
            var ov = document.getElementById('o_chatboo_persistent_overlay');
            return !ov
                || ov.classList.contains('d-none')
                || ov.style.display === 'none';
        },

        _showChatbooNotification: function () {
            if (this.displayNotification) {
                this.displayNotification({
                    type: 'info',
                    title: 'Chatboo AI',
                    message: _t('New Chatboo response ready'),
                    sticky: false,
                    className: 'o_chatboo_async_toast bg-info text-white'
                });
            } else {
                this.do_notify('Chatboo AI', _t('New Chatboo response ready'), false, 'o_chatboo_async_toast bg-info text-white');
            }
        },

        _showSharedPage: function (payload) {
            var url = String(payload.url || '');
            if (url.indexOf('/chatboo/page/') !== 0) {
                return;
            }
            var open = function () {
                window.open(url, '_blank', 'noopener');
            };
            this.displayNotification({
                type: 'info',
                title: payload.title || _t('Shared page'),
                message: _t('%s shared a page with you').replace('%s', payload.owner || ''),
                sticky: true,
                buttons: [{
                    name: _t('Open page'),
                    text: _t('Open page'),
                    primary: true,
                    click: open,
                    onClick: open,
                }],
            });
        },

        _showAuthNotification: function () {
            var now = Date.now();
            if (this._lastAuthToast && now - this._lastAuthToast < 8000) {
                return;
            }
            this._lastAuthToast = now;
            if (this.displayNotification) {
                this.displayNotification({
                    type: 'warning',
                    title: 'Chatboo AI',
                    message: _t('Chatboo is waiting for your confirmation'),
                    sticky: false,
                    className: 'o_chatboo_async_toast bg-warning'
                });
            } else {
                this.do_notify('Chatboo AI', _t('Chatboo is waiting for your confirmation'), false, 'o_chatboo_async_toast bg-warning');
            }
        },

        _refreshAuthCue: function (opts) {
            var self = this;
            opts = opts || {};
            return this._rpc({
                route: '/pns_ai_mcp/verification/pending',
                params: {},
            }).then(function (res) {
                var items = (res && res.items) || [];
                if (!self._isOverlayHidden()) {
                    return false;
                }
                if (items.length) {
                    self._showBadge('auth');
                    if (opts.notify) {
                        self._showAuthNotification();
                    }
                    return true;
                }
                if (opts.fallbackUnread) {
                    self._showBadge('info');
                    if (opts.notify) {
                        self._showChatbooNotification();
                    }
                }
                return false;
            }).catch(function () {
                if (opts.fallbackUnread && self._isOverlayHidden()) {
                    self._showBadge('info');
                    if (opts.notify) {
                        self._showChatbooNotification();
                    }
                }
                return false;
            });
        },

        /**
         * Show the notification badge on the systray elephant icon.
         *
         * @param {string} [type='info'] - Badge type:
         *   'info'  → fa-bell-o (white on standard badge bg)
         *   'auth'  → fa-bell-o (white on warning / pending confirm)
         *   'error' → fa-exclamation (white on red bg-danger)
         */
        _showBadge: function (type) {
            var badge = this.el && this.el.querySelector('.o_chatboo_badge');
            if (badge) {
                badge.classList.remove('bg-danger', 'bg-warning', 'text-white');
                if (type === 'error') {
                    badge.innerHTML = '<i class="fa fa-exclamation fw-bold"/>';
                    badge.classList.add('bg-danger');
                } else if (type === 'auth') {
                    badge.innerHTML = '<i class="fa fa-bell-o"/>';
                    badge.classList.add('bg-warning', 'text-white');
                } else {
                    badge.innerHTML = '<i class="fa fa-bell-o"/>';
                }
                badge.style.display = '';
            }
            if (type !== 'auth') {
                try {
                    localStorage.setItem('chatboo_unread', type === 'error' ? 'error' : '1');
                } catch (_) {}
            }
        },

        _clearBadge: function () {
            var badge = this.el && this.el.querySelector('.o_chatboo_badge');
            if (badge) {
                badge.style.display = 'none';
                badge.innerHTML = '<i class="fa fa-bell-o"/>';
                badge.classList.remove('bg-danger', 'bg-warning', 'text-white');
            }
            try { localStorage.removeItem('chatboo_unread'); } catch (_) {}
        },

        /** Refresca el contexto de pantalla activa (vista/registro bajo el overlay). */
        _refreshChatbooScreenFocus: function () {
            var comp = window.__chatboo_component;
            if (comp && comp._refreshScreenFocus) {
                comp._refreshScreenFocus();
            }
        },

        _cueAuthOnHide: function () {
            core.bus.trigger('chatboo_auth_cue', { notify: false });
        },

        _clearScreenFocusOnHide: function () {
            var comp = window.__chatboo_component;
            if (comp && comp._closeSlashUi) {
                comp._closeSlashUi();
            } else if (comp && comp.state) {
                comp.state.slashOpen = false;
                comp.state.slashItems = [];
            } else {
                var orphan = document.getElementById('o_chatboo_slash_menu');
                if (orphan && orphan.parentNode) {
                    orphan.parentNode.removeChild(orphan);
                }
            }
            if (comp && comp.state) {
                comp.state.screenFocusLabel = '';
                comp.state.screenContextSnapshot = null;
            }
        },

        _hideOverlay: function () {
            var overlay = document.getElementById('o_chatboo_persistent_overlay');
            if (overlay) {
                overlay.style.display = 'none';
            }
            window.pnsLayer.release('chatboo');
            this._clearScreenFocusOnHide();
            this._cueAuthOnHide();
        },

        _showOverlay: function (context) {
            var self = this;
            var libs = require('pns_ai_chatboo.heavy_libs');
            return libs.loadHeavyLibs().then(function () {
                self._clearBadge();
                window.pnsLayer.claim('chatboo', self._hideOverlay.bind(self));
                var overlay = document.getElementById('o_chatboo_persistent_overlay');
                if (!overlay) {
                    self._createPersistentOverlay(context || {});
                    return;
                }
                overlay.classList.remove('d-none');
                overlay.style.display = 'flex';
                self._afterOverlayShown(context || {});
            });
        },

        _afterOverlayShown: function (context) {
            this._refreshChatbooScreenFocus();
            var comp = window.__chatboo_component;
            if (!comp) {
                return;
            }
            if (context.new_chat && comp._createNewSession) {
                comp._createNewSession(true);
            } else if (context.show_history_modal && comp._showSessions) {
                comp._showSessions();
            }
            if (comp._focusChatInput) {
                comp._focusChatInput();
            }
            if (comp._restorePendingVerifications) {
                comp._restorePendingVerifications();
            }
        },

        _onClick: function (ev) {
            ev.preventDefault();
            var overlay = document.getElementById('o_chatboo_persistent_overlay');
            var isVisible = overlay
                && overlay.style.display !== 'none'
                && !overlay.classList.contains('d-none');
            if (isVisible) {
                this._hideOverlay();
                return;
            }
            this._showOverlay({});
        },

        _createPersistentOverlay: function (context) {
            var self = this;

            // Build overlay container
            var overlay = document.createElement('div');
            overlay.id = 'o_chatboo_persistent_overlay';
            overlay.className = 'o_chatboo_persistent_overlay';
            // Position below Odoo's navbar — never cover system menus/icons
            var navbar = document.querySelector('.o_main_navbar');
            var navbarHeight = navbar ? navbar.offsetHeight + 'px' : '46px';
            overlay.style.cssText = [
                'position: fixed',
                'top: ' + navbarHeight,
                'left: 0',
                'right: 0',
                'bottom: 0',
                'z-index: 1039', /* Debajo del modal de Odoo (1050); pns_base lo oculta al pulsar el navbar */
                'display: flex',
                'flex-direction: column',
                'background-color: #fff',
            ].join(';');

            // Close bar (thin header with close button)
            var closeBar = document.createElement('div');
            closeBar.className = 'o_chatboo_persistent_closebar';
            closeBar.style.cssText = [
                'display: flex',
                'align-items: center',
                'justify-content: flex-end',
                'padding: 2px 8px',
                'background-color: #f8f9fa',
                'border-bottom: 1px solid #dee2e6',
                'flex-shrink: 0',
            ].join(';');

            var closeBtn = document.createElement('button');
            closeBtn.className = 'btn btn-sm btn-link text-dark';
            closeBtn.innerHTML = '<i class="fa fa-times"></i>';
            closeBtn.title = 'Cerrar (ocultar)';
            closeBtn.style.cssText = 'font-size: 18px; line-height: 1; padding: 2px 6px; text-decoration: none;';
            closeBtn.addEventListener('click', function () {
                self._hideOverlay();
            });
            closeBar.appendChild(closeBtn);
            overlay.appendChild(closeBar);

            // Mount point for the OWL component
            var mountPoint = document.createElement('div');
            mountPoint.className = 'o_chatboo_persistent_mount';
            mountPoint.style.cssText = 'flex: 1; overflow: hidden; display: flex; flex-direction: column;';
            overlay.appendChild(mountPoint);

            document.body.appendChild(overlay);

            // Require the component module and instantiate
            try {
                var ChatbooModule = require('pns_ai_chatboo.Chatboo');
                var ChatbooComponent = ChatbooModule.ChatbooComponent;
                // shadow:true — los RPC de Chatboo NUNCA bloquean el spinner
                // global de Odoo (abrir el elefante no puede congelar la UI).
                var chatbooRpc = function (params) {
                    return self._rpc(params, {shadow: true});
                };
                var component = new ChatbooComponent(null, {
                    rpc: chatbooRpc,
                    notification: (self.displayNotification || self.do_notify || function () {}).bind(self),
                    doAction: self.do_action.bind(self),
                    context: {}
                });

                window.__chatboo_component = component;

                component.mount(mountPoint).then(function () {
                    if (component._initSession) {
                        component._initSession();
                    }
                    self._afterOverlayShown(context || {});
                }).catch(function (err) {
                    console.error('Chatboo: failed to mount singleton component', err);
                });
            } catch (err) {
                console.error('Chatboo: failed to require component module', err);
            }
        },
    });

    SystrayMenu.Items.push(ChatbooSystrayItem);

    function chatbooContextFromAction(action) {
        var ctx = {};
        if (!action) {
            return ctx;
        }
        if (action.tag === 'chatboo.history.action') {
            ctx.show_history_modal = true;
        } else if (action.tag === 'chatboo.new.action') {
            ctx.new_chat = true;
        }
        if (!action.context) {
            return ctx;
        }
        if (typeof action.context === 'string') {
            ctx.show_history_modal = ctx.show_history_modal
                || action.context.indexOf("'show_history_modal': True") !== -1
                || action.context.indexOf('"show_history_modal": True') !== -1;
            ctx.new_chat = ctx.new_chat
                || action.context.indexOf("'new_chat': True") !== -1
                || action.context.indexOf('"new_chat": True') !== -1;
            return ctx;
        }
        ctx.show_history_modal = ctx.show_history_modal
            || action.context.show_history_modal === true
            || action.context.show_history_modal === 'True';
        ctx.new_chat = ctx.new_chat
            || action.context.new_chat === true
            || action.context.new_chat === 'True';
        return ctx;
    }

    // App / menú: mostrar el overlay y NO empujar la client action
    // (esa acción vacía es la página en blanco al retraer).
    ActionManager.include({
        _executeClientAction: function (action, options) {
            if (action && CHATBOO_CLIENT_TAGS[action.tag]) {
                core.bus.trigger('chatboo_overlay_show', chatbooContextFromAction(action));
                return $.when();
            }
            return this._super.apply(this, arguments);
        },
    });

    return ChatbooSystrayItem;

});
