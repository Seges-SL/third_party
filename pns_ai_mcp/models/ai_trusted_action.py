# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""ai.trusted.action — declarative registry for Safe Plan trusted actions
(``op='action'`` steps, see ``controllers/safe_plan.py``).

Zero Python coupling between pns_ai_mcp and the addons that own a trusted
action. An owning addon (e.g. pns_acl_manager) contributes a plain
``<record>`` here — naming a model and two of ITS OWN method names — the
exact same "call a method by name" pattern Odoo already uses for
``ir.cron`` and ``ir.actions.server`` (code actions): pns_ai_mcp never
imports a single line from the owning addon, and the owning addon never
imports pns_ai_mcp's Python internals either. The ORM (this model) is the
only contract, in both directions.

A trusted action is a small, pre-vetted server-side operation that Safe
Plan can propose and, after human Confirm, execute — as an alternative to
generic create/write/unlink for changes whose invariants are too complex
or dangerous to express safely as raw CRUD (e.g. ACL least-privilege
enforcement). The LLM only ever sees a closed vocabulary of ``code``
values, exactly like it only sees a closed vocabulary of CRUD verbs.
"""
from odoo import api, fields, models
from odoo.exceptions import ValidationError
from odoo.addons.pns_base.utils.compat import user_has_group


class AiTrustedAction(models.Model):
    _name = 'ai.trusted.action'
    _description = 'AI Safe Plan — Trusted Action'
    _rec_name = 'code'
    _order = 'code'

    code = fields.Char(
        required=True, index=True,
        help="Closed-vocabulary action_code the LLM proposes in a Safe Plan "
             "op='action' step (e.g. 'acl.prune').",
    )
    label = fields.Char(
        required=True,
        help="Human-readable label shown in the Confirm toast. Stored as the "
             "plain (English) source string declared by the owning addon's "
             "XML record — translate it at display time with _(), the same "
             "way ir.actions.server/ir.cron display names normally aren't "
             "field-translated either. In practice this string is already a "
             "translated msgid elsewhere (e.g. the matching UI button), so "
             "no extra i18n binding is needed for this field itself.",
    )
    danger = fields.Selection([
        ('low', 'Low'), ('medium', 'Medium'), ('high', 'High'),
    ], required=True, default='high')
    group_ids = fields.Many2many(
        'res.groups', string='Required groups',
        help="User needs at least one of these (in addition to the generic "
             "AI Writer group already required for any 'action' step). "
             "Empty = no extra restriction beyond the generic one.",
    )
    model_id = fields.Many2one(
        'ir.model', required=True, ondelete='cascade',
        help="Model that owns preview_method / apply_method.",
    )
    model_name = fields.Char(related='model_id.model', store=True, readonly=True)
    preview_method = fields.Char(
        required=True,
        help="Name of an @api.model method on model_id, called as "
             "env[model_name].<preview_method>(**args); must return a "
             "human-readable str for the toast.",
    )
    apply_method = fields.Char(
        required=True,
        help="Name of an @api.model method on model_id, called as "
             "env[model_name].<apply_method>(**args); must return a "
             "JSON-serializable result.",
    )
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ('code_uniq', 'unique(code)',
         'A trusted action with this code is already registered.'),
    ]

    @api.model
    def _get(self, code):
        """Look up a registered action by its closed-vocabulary code.

        Uses ``self.env`` as passed by the caller (the human requester's
        env in every real Safe Plan call-site) — no sudo: reading which
        actions exist requires no elevated access, only base.group_user
        (see ir.model.access.csv).
        """
        return self.search([('code', '=', code)], limit=1)

    def _resolve_method(self, method_field):
        self.ensure_one()
        try:
            model = self.env[self.model_name]
        except KeyError:
            raise ValidationError(
                "Trusted action %r: unknown model %r (addon uninstalled?)"
                % (self.code, self.model_name)
            )
        method_name = self[method_field]
        method = getattr(model, method_name, None)
        if method is None:
            raise ValidationError(
                "Trusted action %r: model %r has no method %r (%s)" % (
                    self.code, self.model_name, method_name, method_field,
                )
            )
        return method

    def preview(self, **args):
        """Human-readable summary for the Confirm toast. Never mutates."""
        self.ensure_one()
        return self._resolve_method('preview_method')(**args)

    def apply(self, **args):
        """Perform the action. Runs in the SAME transaction/cursor as any
        other Safe Plan step, so the atomicity guarantee in
        ``mcp_safe_operation.execute_plan_now`` covers it automatically."""
        self.ensure_one()
        return self._resolve_method('apply_method')(**args)

    def user_has_required_groups(self, user):
        """True when ``user`` has at least one of ``group_ids`` (direct or
        implied — same semantics as ``res.users.has_group()``).

        Deliberately does NOT read ``user.groups_id`` directly: that field
        was renamed to ``group_ids``/``all_group_ids`` in Odoo 19 (see
        ``pns_base.utils.compat.USER_ALL_GROUPS_FIELD``) — reading the old
        name would silently break (or hard-crash) on Odoo 19.
        """
        self.ensure_one()
        return not self.group_ids or any(
            user_has_group(user, group) for group in self.group_ids
        )
