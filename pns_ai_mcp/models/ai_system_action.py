# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""ai.system.action — preview/apply for generic system trusted actions.

View modifiers, module install/upgrade/uninstall, native group grant/revoke.
No domain literals (no partner fields, no tenant names). Args are closed:
model/field/view_ids/view_types, module+operation, user_id+group.
"""
import logging

from odoo import _, api, models
from odoo.exceptions import UserError
from odoo.addons.pns_base.utils.compat import user_add_group, user_remove_group

from ..utils.view_policy_arch import (
    MODIFIERS,
    arch_contains_field,
    build_modifier_arch,
    check_ident,
    format_domain,
    policy_xmlid_name,
)
from ..utils.module_update_heal import (
    module_ids_from_args,
    module_name_from_args,
    operation_from_args,
    should_skip_module_op,
)

_logger = logging.getLogger(__name__)

_MODULE_OPS = {
    'install': 'button_immediate_install',
    'upgrade': 'button_immediate_upgrade',
    'uninstall': 'button_immediate_uninstall',
}
_CORE_UNINSTALL_BLOCK = frozenset({
    'base', 'web', 'pns_base', 'pns_ai_mcp',
})
_XMLID_MODULE = 'pns_ai_mcp'


def _as_bool(value, default=True):
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return bool(value)
    text = str(value).strip().lower()
    if text in ('1', 'true', 'yes', 'on'):
        return True
    if text in ('0', 'false', 'no', 'off'):
        return False
    raise UserError(_('Invalid boolean value: %s') % value)


def _as_view_ids(view_ids):
    if not view_ids:
        return []
    if isinstance(view_ids, (int, float)) and not isinstance(view_ids, bool):
        return [int(view_ids)]
    if isinstance(view_ids, str) and view_ids.strip().isdigit():
        return [int(view_ids.strip())]
    if isinstance(view_ids, (list, tuple)):
        return [int(x) for x in view_ids]
    raise UserError(_('view_ids must be a list of view ids (or empty).'))


def _view_ids_arg(view_ids=None, **kw):
    """Official ``view_ids``, or LLM alias ``view_id`` (single id)."""
    if view_ids not in (None, False, [], ''):
        return view_ids
    alias = kw.get('view_id')
    if alias not in (None, False, ''):
        return alias
    return []


_VIEW_TYPE_ALIASES = {
    'form': ('form',),
    'tree': ('tree', 'list'),
    'list': ('tree', 'list'),
}


def _as_view_types(view_types):
    """Normalize ``form`` / ``tree`` / ``list``; empty means form-first default."""
    if view_types in (None, False, '', []):
        return None
    if isinstance(view_types, str):
        view_types = [view_types]
    if not isinstance(view_types, (list, tuple)):
        raise UserError(_('Invalid view type: %s') % view_types)
    out = []
    for raw in view_types:
        key = str(raw).strip().lower()
        if key not in _VIEW_TYPE_ALIASES:
            raise UserError(_('Invalid view type: %s') % raw)
        for item in _VIEW_TYPE_ALIASES[key]:
            if item not in out:
                out.append(item)
    return out


def _view_types_arg(view_types=None, **kw):
    """Official ``view_types``, or LLM alias ``view_type`` (single type)."""
    if view_types not in (None, False, [], ''):
        return view_types
    alias = kw.get('view_type')
    if alias not in (None, False, ''):
        return alias
    return None


class AiSystemAction(models.AbstractModel):
    _name = 'ai.system.action'
    _description = 'AI System Trusted Action'

    # ── shared helpers ────────────────────────────────────────────────────

    def _ensure_model_field(self, model, field):
        try:
            check_ident(model, 'model')
            check_ident(field, 'field')
        except ValueError as exc:
            raise UserError(str(exc))
        if model not in self.env:
            raise UserError(_('Unknown model: %s') % model)
        if field not in self.env[model]._fields:
            raise UserError(
                _('Field %s does not exist on model %s') % (field, model)
            )

    def _views_showing_field(self, model, field, types):
        View = self.env['ir.ui.view'].sudo()
        candidates = View.search([
            ('model', '=', model),
            ('type', 'in', list(types)),
        ])
        return candidates.filtered(
            lambda v: arch_contains_field(v.arch or '', field)
        )

    def _resolve_target_views(self, model, field, view_ids, view_types=None):
        View = self.env['ir.ui.view'].sudo()
        ids = _as_view_ids(view_ids)
        types = _as_view_types(view_types)
        if ids:
            views = View.browse(ids)
            missing = [i for i in ids if i not in views.ids]
            if missing:
                raise UserError(_('Unknown view id(s): %s') % missing)
            for view in views:
                if view.model != model:
                    raise UserError(
                        _('View %s does not belong to model %s')
                        % (view.id, model)
                    )
                if types and view.type not in types:
                    raise UserError(
                        _('View %s is type %s, not %s')
                        % (view.id, view.type, ', '.join(types))
                    )
                if not arch_contains_field(view.arch or '', field):
                    from ..utils.field_required_plan import combined_arch
                    if not arch_contains_field(combined_arch(view), field):
                        raise UserError(
                            _('View %s does not display field %s')
                            % (view.id, field)
                        )
            return views
        if types:
            hits = self._views_showing_field(model, field, types)
        else:
            hits = self._views_showing_field(model, field, ('form',))
            if not hits:
                hits = self._views_showing_field(model, field, ('tree', 'list'))
        if not hits:
            raise UserError(
                _('No form or list view of model %s already displays field %s')
                % (model, field)
            )
        return hits

    def _inherit_xmlid(self, xmlid_name, view_vals):
        """Create or write the extension view bound to a stable xmlid."""
        View = self.env['ir.ui.view'].sudo()
        Imd = self.env['ir.model.data'].sudo()
        existing = Imd.search([
            ('module', '=', _XMLID_MODULE),
            ('name', '=', xmlid_name),
        ], limit=1)
        if existing:
            rec = View.browse(existing.res_id)
            if rec.exists():
                rec.write(view_vals)
                return rec
            existing.unlink()
        rec = View.create(view_vals)
        Imd.create({
            'module': _XMLID_MODULE,
            'name': xmlid_name,
            'model': 'ir.ui.view',
            'res_id': rec.id,
            'noupdate': True,
        })
        return rec

    def _apply_view_modifier(
            self, modifier, model, field, value, view_ids=None, view_types=None,
            uniform=False):
        self._ensure_model_field(model, field)
        if modifier not in MODIFIERS:
            raise UserError(_('Unknown view modifier: %s') % modifier)
        try:
            arch = build_modifier_arch(
                field, modifier, value, uniform=uniform,
            )
        except ValueError as exc:
            raise UserError(str(exc))
        views = self._resolve_target_views(model, field, view_ids, view_types)
        stored = (
            format_domain(value) if modifier == 'domain'
            else ('1' if value else '0')
        )
        Policy = self.env['ai.view.policy'].sudo()
        inherit_ids = []
        policy_ids = []
        before_records = []
        after_records = []
        for view in views:
            xmlid_name = policy_xmlid_name(model, field, modifier, view.id)
            policy = Policy.search([
                ('model_name', '=', model),
                ('field_name', '=', field),
                ('modifier', '=', modifier),
                ('view_id', '=', view.id),
            ], limit=1)
            if policy and policy.inherit_view_id:
                before_records.append({
                    'id': policy.inherit_view_id.id,
                    'arch': policy.inherit_view_id.arch or '',
                    'display_name': policy.inherit_view_id.display_name,
                })
            inherit = self._inherit_xmlid(xmlid_name, {
                'name': 'AI policy: %s.%s %s' % (model, field, modifier),
                'model': model,
                'inherit_id': view.id,
                'priority': 99,
                'arch': arch,
            })
            if policy:
                policy.write({
                    'value': stored,
                    'inherit_view_id': inherit.id,
                })
            else:
                policy = Policy.create({
                    'model_name': model,
                    'field_name': field,
                    'modifier': modifier,
                    'value': stored,
                    'view_id': view.id,
                    'inherit_view_id': inherit.id,
                })
            inherit_ids.append(inherit.id)
            policy_ids.append(policy.id)
            after_records.append({
                'id': inherit.id,
                'arch': inherit.arch or '',
                'display_name': inherit.display_name,
            })
        return {
            'ok': True,
            'model': 'ir.ui.view',
            'ids': inherit_ids,
            'policy_ids': policy_ids,
            'change_journal': {
                'model': 'ir.ui.view',
                'ids': inherit_ids,
                'change_kind': 'view_modifier',
                'reversible': True,
                'before': {
                    'schema_version': 1,
                    'op': 'action',
                    'model': 'ir.ui.view',
                    'ids': [r['id'] for r in before_records],
                    'records': before_records,
                    'meta': {'change_kind': 'view_modifier'},
                },
                'after': {
                    'schema_version': 1,
                    'op': 'action',
                    'model': 'ir.ui.view',
                    'ids': inherit_ids,
                    'records': after_records,
                    'meta': {
                        'change_kind': 'view_modifier',
                        'modifier': modifier,
                        'field': field,
                        'model_name': model,
                    },
                },
            },
        }

    def _preview_view_modifier(
            self, modifier, model, field, value, view_ids=None, view_types=None):
        self._ensure_model_field(model, field)
        if modifier == 'domain':
            try:
                format_domain(value)
            except ValueError as exc:
                raise UserError(str(exc))
        views = self._resolve_target_views(
            model, field, view_ids, view_types,
        )
        n = len(views)
        if modifier == 'domain':
            if value is False or value is None or value == [] or value == '[]':
                return _(
                    'Clear domain on field %s of model %s in %s view(s)'
                ) % (field, model, n)
            return _(
                'Set domain on field %s of model %s in %s view(s)'
            ) % (field, model, n)
        flag = '1' if value else '0'
        return _(
            'Set %s=%s on field %s of model %s in %s view(s)'
        ) % (modifier, flag, field, model, n)

    # ── view.set_field_required ───────────────────────────────────────────

    @api.model
    def preview_view_set_field_required(
            self, model=None, field=None, required=True, view_ids=None,
            view_types=None, **kw):
        return self._preview_view_modifier(
            'required', model, field, _as_bool(required),
            _view_ids_arg(view_ids, **kw),
            _view_types_arg(view_types, **kw),
        )

    @api.model
    def apply_view_set_field_required(
            self, model=None, field=None, required=True, view_ids=None,
            view_types=None, uniform=False, **kw):
        return self._apply_view_modifier(
            'required', model, field, _as_bool(required),
            _view_ids_arg(view_ids, **kw),
            _view_types_arg(view_types, **kw),
            uniform=_as_bool(uniform, default=False),
        )

    # ── field.set_required (ORM + registry; called by op=field_required) ──

    @api.model
    def preview_field_set_required(
            self, model=None, field=None, required=True, **_kw):
        self._ensure_model_field(model, field)
        flag = _as_bool(required)
        Imf = self.env['ir.model.fields'].sudo().search([
            ('model', '=', model), ('name', '=', field),
        ], limit=1)
        extra = ''
        if Imf and Imf.state == 'base':
            extra = _(
                ' This field is defined by a module; an upgrade may revert '
                'the required flag.'
            )
        extra += _(
            ' Registry of this worker is updated; other workers until restart.'
        )
        return _(
            'Set required=%s on field %s of model %s (ORM).%s'
        ) % ('1' if flag else '0', field, model, extra)

    @api.model
    def apply_field_set_required(
            self, model=None, field=None, required=True, **_kw):
        self._ensure_model_field(model, field)
        required = _as_bool(required)
        notes = []
        Imf = self.env['ir.model.fields'].sudo().search([
            ('model', '=', model), ('name', '=', field),
        ], limit=1)
        if Imf:
            if Imf.state == 'base':
                notes.append(
                    'Field is defined by a module; an upgrade may revert '
                    'required.'
                )
            try:
                Imf.write({'required': required})
            except Exception as exc:
                notes.append(
                    'Could not persist ir.model.fields.required: %s' % exc
                )
        fld = self.env[model]._fields.get(field)
        if fld is not None:
            fld.required = required
        notes.append(
            'Registry of this worker updated; other workers until restart.'
        )
        return {
            'ok': True,
            'model': model,
            'field': field,
            'required': required,
            'notes': notes,
        }

    # ── view.set_field_readonly ───────────────────────────────────────────

    @api.model
    def preview_view_set_field_readonly(
            self, model=None, field=None, readonly=True, view_ids=None,
            view_types=None, **kw):
        return self._preview_view_modifier(
            'readonly', model, field, _as_bool(readonly),
            _view_ids_arg(view_ids, **kw),
            _view_types_arg(view_types, **kw),
        )

    @api.model
    def apply_view_set_field_readonly(
            self, model=None, field=None, readonly=True, view_ids=None,
            view_types=None, **kw):
        return self._apply_view_modifier(
            'readonly', model, field, _as_bool(readonly),
            _view_ids_arg(view_ids, **kw),
            _view_types_arg(view_types, **kw),
        )

    # ── view.set_field_invisible ──────────────────────────────────────────

    @api.model
    def preview_view_set_field_invisible(
            self, model=None, field=None, invisible=True, view_ids=None,
            view_types=None, **kw):
        return self._preview_view_modifier(
            'invisible', model, field, _as_bool(invisible),
            _view_ids_arg(view_ids, **kw),
            _view_types_arg(view_types, **kw),
        )

    @api.model
    def apply_view_set_field_invisible(
            self, model=None, field=None, invisible=True, view_ids=None,
            view_types=None, **kw):
        return self._apply_view_modifier(
            'invisible', model, field, _as_bool(invisible),
            _view_ids_arg(view_ids, **kw),
            _view_types_arg(view_types, **kw),
        )

    # ── view.set_field_domain ─────────────────────────────────────────────

    @api.model
    def preview_view_set_field_domain(
            self, model=None, field=None, domain=None, view_ids=None,
            view_types=None, **kw):
        return self._preview_view_modifier(
            'domain', model, field, domain,
            _view_ids_arg(view_ids, **kw),
            _view_types_arg(view_types, **kw),
        )

    @api.model
    def apply_view_set_field_domain(
            self, model=None, field=None, domain=None, view_ids=None,
            view_types=None, **kw):
        return self._apply_view_modifier(
            'domain', model, field, domain,
            _view_ids_arg(view_ids, **kw),
            _view_types_arg(view_types, **kw),
        )

    # ── view.reset_field_modifiers ────────────────────────────────────────

    @api.model
    def preview_view_reset_field_modifiers(
            self, model=None, field=None, **_kw):
        self._ensure_model_field(model, field)
        n = self.env['ai.view.policy'].sudo().search_count([
            ('model_name', '=', model),
            ('field_name', '=', field),
        ])
        return _(
            'Remove AI view-modifier inherits for field %s of model %s '
            '(%s polic(y/ies))'
        ) % (field, model, n)

    @api.model
    def apply_view_reset_field_modifiers(
            self, model=None, field=None, **_kw):
        self._ensure_model_field(model, field)
        policies = self.env['ai.view.policy'].sudo().search([
            ('model_name', '=', model),
            ('field_name', '=', field),
        ])
        inherit_ids = policies.mapped('inherit_view_id').ids
        before_records = [{
            'id': v.id,
            'arch': v.arch or '',
            'display_name': v.display_name,
        } for v in policies.mapped('inherit_view_id')]
        n = len(policies)
        policies.unlink()
        return {
            'ok': True,
            'model': 'ir.ui.view',
            'removed': n,
            'ids': inherit_ids,
            'change_journal': {
                'model': 'ir.ui.view',
                'ids': inherit_ids,
                'change_kind': 'view_modifier',
                'reversible': False,
                'reversible_reason': 'inherit views unlinked',
                'before': {
                    'schema_version': 1,
                    'op': 'action',
                    'model': 'ir.ui.view',
                    'ids': inherit_ids,
                    'records': before_records,
                    'meta': {'change_kind': 'view_modifier'},
                },
                'after': {
                    'schema_version': 1,
                    'op': 'action',
                    'model': 'ir.ui.view',
                    'ids': [],
                    'records': [],
                    'meta': {'change_kind': 'view_modifier'},
                },
            },
        }

    # ── module.update ─────────────────────────────────────────────────────

    def _sql_module_state(self, name):
        """Read ``ir_module_module.state`` from SQL (bypass stale ORM cache)."""
        self.env.cr.execute(
            "SELECT id, state FROM ir_module_module WHERE name = %s LIMIT 1",
            (name,),
        )
        row = self.env.cr.fetchone()
        if not row:
            return None, None
        return row[0], row[1]

    def _module_loaded(self, name):
        loaded = getattr(self.env.registry, '_init_modules', None)
        if loaded is None:
            return None
        return name in loaded

    def _get_module(self, name):
        if not name or not isinstance(name, str):
            raise UserError(_('Unknown module: %s') % name)
        try:
            check_ident(name, 'model')
        except ValueError:
            raise UserError(_('Unknown module: %s') % name)
        mod = self.env['ir.module.module'].sudo().search(
            [('name', '=', name)], limit=1,
        )
        if not mod:
            raise UserError(_('Unknown module: %s') % name)
        return mod

    def _coerce_module_update_args(self, module=None, operation=None, **kw):
        """Canonical ``(technical_name, install|upgrade|uninstall)``.

        Official args are ``module`` + ``operation``. Also accept Apps-form
        aliases (``module_ids`` / ``module_id`` + ``button`` /
        ``button_immediate_install``) so a hallucinated toast still applies.
        """
        payload = dict(kw or {})
        if module is not None:
            payload['module'] = module
        if operation is not None:
            payload['operation'] = operation
        name = module_name_from_args(payload)
        op = operation_from_args(payload)
        ids = module_ids_from_args(payload)
        if not name and ids:
            recs = self.env['ir.module.module'].sudo().browse(ids).exists()
            if recs:
                name = recs[0].name
            else:
                raise UserError(_('Unknown module: %s') % ids)
        if op not in _MODULE_OPS:
            raise UserError(
                _('Invalid module operation: %s (use install, upgrade or uninstall)')
                % (operation or payload.get('button') or payload.get('operation'))
            )
        if not name:
            raise UserError(_('Unknown module: %s') % module)
        return name, op

    @api.model
    def preview_module_update(self, module=None, operation=None, **kw):
        module, op = self._coerce_module_update_args(
            module=module, operation=operation, **kw
        )
        if op == 'uninstall' and module in _CORE_UNINSTALL_BLOCK:
            raise UserError(_('Refusing to uninstall core module %s') % module)
        _mid, sql_state = self._sql_module_state(module)
        if not _mid:
            raise UserError(_('Unknown module: %s') % module)
        mod = self.env['ir.module.module'].sudo().browse(_mid)
        loaded = self._module_loaded(module)
        if op == 'upgrade' and sql_state not in ('installed', 'to upgrade'):
            raise UserError(
                _('Cannot upgrade module %s (state: %s)') % (module, sql_state)
            )
        label = mod.shortdesc or module
        state_note = sql_state or '?'
        if op == 'install' and sql_state == 'installed' and loaded is False:
            state_note = '%s, not loaded' % sql_state
        return _(
            "Will %s module '%s' (current state: %s)"
        ) % (op, label, state_note)

    @api.model
    def apply_module_update(self, module=None, operation=None, **kw):
        module, op = self._coerce_module_update_args(
            module=module, operation=operation, **kw
        )
        if op == 'uninstall' and module in _CORE_UNINSTALL_BLOCK:
            raise UserError(_('Refusing to uninstall core module %s') % module)
        _mid, sql_state = self._sql_module_state(module)
        if not _mid:
            raise UserError(_('Unknown module: %s') % module)
        mod = self.env['ir.module.module'].sudo().browse(_mid)
        loaded = self._module_loaded(module)
        if should_skip_module_op(op, sql_state, loaded):
            return {
                'ok': True, 'skipped': True, 'module': module,
                'state': sql_state, 'loaded': loaded,
                'model': 'ir.module.module',
                'ids': [mod.id],
            }
        if op == 'upgrade' and sql_state not in ('installed', 'to upgrade'):
            raise UserError(
                _('Cannot upgrade module %s (state: %s)') % (module, sql_state)
            )
        method = getattr(mod, _MODULE_OPS[op])
        _logger.info('AI system action module.update %s %s', op, module)
        method()
        return {
            'ok': True,
            'module': module,
            'operation': op,
            'model': 'ir.module.module',
            'ids': [mod.id],
            'change_journal': {
                'model': 'ir.module.module',
                'ids': [mod.id],
                'change_kind': 'module',
                'reversible': False,
                'reversible_reason': 'module install/upgrade/uninstall',
            },
        }

    # ── user.add_group / user.remove_group ────────────────────────────────

    def _resolve_user(self, user_id):
        try:
            uid = int(user_id)
        except (TypeError, ValueError):
            raise UserError(_('Unknown user: %s') % user_id)
        user = self.env['res.users'].sudo().browse(uid)
        if not user.exists():
            raise UserError(_('Unknown user: %s') % user_id)
        return user

    def _resolve_group(self, group):
        Groups = self.env['res.groups'].sudo()
        if isinstance(group, bool):
            raise UserError(_('Unknown group: %s') % group)
        if isinstance(group, (int, float)) or (
                isinstance(group, str) and str(group).strip().isdigit()):
            rec = Groups.browse(int(group))
            if rec.exists():
                return rec
            raise UserError(_('Unknown group: %s') % group)
        if isinstance(group, str) and '.' in group:
            rec = self.env.ref(group, raise_if_not_found=False)
            if rec is not None and rec._name == 'res.groups' and rec.exists():
                return rec
        raise UserError(_('Unknown group: %s') % group)

    def _acl_role_note(self):
        if 'acl.role' in self.env:
            return ' ' + _(
                'This instance uses ACL roles; Unique Role Law may still '
                'apply after a native group change.'
            )
        return ''

    @api.model
    def preview_user_add_group(self, user_id=None, group=None, **_kw):
        user = self._resolve_user(user_id)
        grp = self._resolve_group(group)
        return (
            _('Add group %s to user %s') % (grp.display_name, user.display_name)
            + self._acl_role_note()
        )

    @api.model
    def apply_user_add_group(self, user_id=None, group=None, **_kw):
        user = self._resolve_user(user_id)
        grp = self._resolve_group(group)
        user_add_group(user, grp)
        return {
            'ok': True,
            'user_id': user.id,
            'group_id': grp.id,
            'model': 'res.users',
            'ids': [user.id],
            'change_journal': {
                'model': 'res.users',
                'ids': [user.id],
                'change_kind': 'acl',
                'reversible': False,
                'reversible_reason': 'native group membership',
            },
        }

    @api.model
    def preview_user_remove_group(self, user_id=None, group=None, **_kw):
        user = self._resolve_user(user_id)
        grp = self._resolve_group(group)
        return (
            _('Remove group %s from user %s')
            % (grp.display_name, user.display_name)
            + self._acl_role_note()
        )

    @api.model
    def apply_user_remove_group(self, user_id=None, group=None, **_kw):
        user = self._resolve_user(user_id)
        grp = self._resolve_group(group)
        user_remove_group(user, grp)
        return {
            'ok': True,
            'user_id': user.id,
            'group_id': grp.id,
            'model': 'res.users',
            'ids': [user.id],
            'change_journal': {
                'model': 'res.users',
                'ids': [user.id],
                'change_kind': 'acl',
                'reversible': False,
                'reversible_reason': 'native group membership',
            },
        }
