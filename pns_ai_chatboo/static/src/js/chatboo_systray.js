odoo.define('pns_ai_chatboo.chatboo_systray', function (require) {
    "use strict";

    var SystrayMenu = require('web.SystrayMenu');
    var Widget = require('web.Widget');
    var core = require('web.core');
    var _t = core._t;

    function afterOverlayPaint(fn) {
        window.requestAnimationFrame(function () {
            window.requestAnimationFrame(fn);
        });
    }

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

            return this._super.apply(this, arguments).then(function () {
                return self._rpc({
                    route: '/chatboo/check_health',
                    params: {}
                }).then(function (result) {
                    if (!result || result.show_systray === false) {
                        // Ocultación intencionada (sin acceso IA): olvida el flag.
                        try { localStorage.removeItem('chatboo_has_access'); } catch (_) {}
                        return;
                    }
                    // Recuerda que este usuario SÍ tiene acceso, para poder
                    // recuperar el icono aunque un futuro check_health falle.
                    try { localStorage.setItem('chatboo_has_access', '1'); } catch (_) {}
                    self._enableSystray();
                }).catch(function () {
                    // Fail-closed: sin confirmación del servidor, no mostrar
                    // Chatboo (evita que un localStorage viejo o un error RPC
                    // den acceso a quien no tiene carnet MCP).
                    try { localStorage.removeItem('chatboo_has_access'); } catch (_) {}
                });
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

            // Register bus listener (Odoo 14)
            this.call('bus_service', 'onNotification', this, this._onBusNotifications);

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
                    window.open(btnHref, '_blank');
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
                this.call('mail_service', 'getMessaging').then(function (messaging) {
                    if (messaging && messaging.rpc) {
                        messaging.rpc({ route: '/mail/init_messaging' }).then(function (res) {
                            core.bus.trigger('mail.chat.needaction_successful');
                        });
                    }
                });
            } catch (e) {
                console.warn("Could not auto-refresh Odoo notification badge", e);
            }
        },

        _isOverlayHidden: function () {
            var ov = document.getElementById('o_chatboo_persistent_overlay');
            return !ov || ov.style.display === 'none';
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

        _onClick: function (ev) {
            ev.preventDefault();
            var self = this;
            // Clear badge on open
            this._clearBadge();

            // ── Singleton pattern: create once, toggle visibility ──
            // The overlay and component persist in document.body across navigation.
            // SSE streams and in-flight prompts survive toggle.

            var overlay = document.getElementById('o_chatboo_persistent_overlay');

            if (overlay) {
                var isVisible = overlay.style.display !== 'none';
                if (isVisible) {
                    // Hide the overlay
                    overlay.style.display = 'none';
                    self._clearScreenFocusOnHide();
                    self._cueAuthOnHide();
                    // Only navigate to home if behind the overlay is a blank
                    // ChatbooAction (opened via app menu). If the user was on
                    // another page and just toggled the overlay, stay there.
                    var currentHash = window.location.hash || '';
                    if (currentHash.indexOf('pns_ai_chatboo') !== -1) {
                        window.location.hash = '#home';
                    }
                } else {
                    // Show the overlay — recapturar la vista/registro actual
                    overlay.style.display = 'flex';
                    afterOverlayPaint(function () {
                        self._refreshChatbooScreenFocus();
                        var comp = window.__chatboo_component;
                        if (comp && comp._focusChatInput) {
                            comp._focusChatInput();
                        }
                        if (comp && comp._restorePendingVerifications) {
                            comp._restorePendingVerifications();
                        }
                    });
                }
                return;
            }

            // ── First click: create persistent overlay ──

            // Build overlay container
            overlay = document.createElement('div');
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
                'z-index: 1050', /* Por encima del navbar/panel de control sticky de Odoo; el overlay se auto-oculta al pulsar el navbar */
                'display: flex',
                'flex-direction: column',
                'background-color: #fff',
            ].join(';');

            // Auto-hide when user clicks any navbar item (except our systray icon)
            if (navbar) {
                navbar.addEventListener('click', function (navEv) {
                    // Don't hide if the click is on our own systray item
                    if (navEv.target.closest('.o_chatboo_systray_item')) return;
                    var ov = document.getElementById('o_chatboo_persistent_overlay');
                    if (ov && ov.style.display !== 'none') {
                        ov.style.display = 'none';
                        if (self._cueAuthOnHide) {
                            self._cueAuthOnHide();
                        }
                        if (self._clearScreenFocusOnHide) {
                            self._clearScreenFocusOnHide();
                        } else if (window.__chatboo_component && window.__chatboo_component.state) {
                            window.__chatboo_component.state.screenFocusLabel = '';
                            window.__chatboo_component.state.screenContextSnapshot = null;
                        }
                    }
                }, true);
            }

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
                overlay.style.display = 'none';
                self._clearScreenFocusOnHide();
                self._cueAuthOnHide();
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
                    afterOverlayPaint(function () {
                        if (component._refreshScreenFocus) {
                            component._refreshScreenFocus();
                        }
                        if (component._focusChatInput) {
                            component._focusChatInput();
                        }
                        if (component._restorePendingVerifications) {
                            component._restorePendingVerifications();
                        }
                    });
                }).catch(function (err) {
                    console.error('Chatboo: failed to mount singleton component', err);
                });
            } catch (err) {
                console.error('Chatboo: failed to require component module', err);
            }
        },
    });

    SystrayMenu.Items.push(ChatbooSystrayItem);

    return ChatbooSystrayItem;

});
