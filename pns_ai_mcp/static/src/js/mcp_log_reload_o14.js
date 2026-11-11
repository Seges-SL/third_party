/**
 * ai.log list on Odoo 14: a notification whose next is a reload closes
 * the wizard and reloads the logs (legacy ActionManager).
 *
 * SPDX-License-Identifier: Apache-2.0
 * Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
 */
odoo.define('pns_ai_mcp.mcp_log_reload', function (require) {
"use strict";

    var ActionManager = require('web.ActionManager');

    // Intercept display_notification with next, to reload the logs view
    ActionManager.include({
        _executeClientAction: function (action, options) {
            var self = this;
            
            var result = this._super.apply(this, arguments);
            
            // If it is display_notification with a reloading next, close the wizard and reload the logs view
            if (action && action.tag === 'display_notification' && action.params && action.params.next) {
                if (action.params.next.tag === 'reload') {
                    // Close the active wizard and reload the logs view
                    if (result && typeof result.then === 'function') {
                        result.then(function() {
                            // Close active dialogs (wizards)
                            if (self._dialogs && Array.isArray(self._dialogs)) {
                                var i = self._dialogs.length - 1;
                                while (i >= 0) {
                                    var dialog = self._dialogs[i];
                                    if (dialog && typeof dialog.close === 'function') {
                                        try {
                                            dialog.close();
                                        } catch (e) {
                                            console.warn('Error closing dialog:', e);
                                        }
                                        break;
                                    }
                                    i--;
                                }
                            }

                            // Find and reload the logs controllers
                            if (self._controllers && Array.isArray(self._controllers)) {
                                for (var j = 0; j < self._controllers.length; j++) {
                                    var controller = self._controllers[j];
                                    if (controller && controller.modelName === 'ai.log' && typeof controller.reload === 'function') {
                                        try {
                                            controller.reload();
                                        } catch (e) {
                                            console.warn('Error reloading controller:', e);
                                        }
                                    }
                                }
                            }

                            // Also reload the current controller if it is a logs one
                            try {
                                var currentController = self.getCurrentController && self.getCurrentController();
                                if (currentController && currentController.modelName === 'ai.log' && typeof currentController.reload === 'function') {
                                    currentController.reload();
                                }
                            } catch (e) {
                                console.warn('Error getting/reloading the current controller:', e);
                            }
                        });
                    } else {
                        try {
                            var currentController = self.getCurrentController && self.getCurrentController();
                            if (currentController && currentController.modelName === 'ai.log' && typeof currentController.reload === 'function') {
                                currentController.reload();
                            }
                        } catch (e) {
                            console.warn('Error getting/reloading the current controller:', e);
                        }
                    }
                }
            }
            
            return result;
        },
    });
});
