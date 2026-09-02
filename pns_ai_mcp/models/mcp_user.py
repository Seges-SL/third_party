# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""MCP user model: per-user API keys and access scope."""

import secrets
import string
from odoo import models, fields, api, _
from odoo.exceptions import UserError

from ..utils import mcp_ui
from ..utils.import_export_guard import ensure_ai_admin
from ..utils.api_key import hash_api_key, normalize_to_hash
from ..utils.portable_io import export_record_dict, import_vals_from_dict
from ..utils.compat import (
    USER_GROUPS_FIELD,
    USER_ALL_GROUPS_FIELD,
    user_has_group,
    user_has_group_direct,
    user_add_group,
    user_remove_group,
    invalidate_recordset_fields,
)
import logging

_logger = logging.getLogger(__name__)


class MCPUser(models.Model):
    """MCP User profile — links an Odoo user to the AI ecosystem.

    This model extends ``res.users`` with AI-specific fields (API key, group
    membership flags). It does NOT define a new permission model; it uses
    standard Odoo groups (``res.groups``) for authorization.

    Permission model (v2 — orthogonal capabilities)
    ==============================================

    ========================  ====================================================
    Group                     Capabilities
    ========================  ====================================================
    **User** (internal user    Read via MCP API key / Chatboo. No CRUD, external
    + MCP API key, no extra    URL or external API until explicitly granted.
    AI groups)
    **AI Writer**             CRUD via propose_safe_operations + AI content mgmt.
    **AI External URL**       fetch_url via propose_safe_operations.
    **AI External API**       api_call (MCP/OpenAPI) via propose_safe_operations.
    **AI Administrator**      All of the above + infrastructure administration.
    ========================  ====================================================

    API key (usuario MCP — NO confundir con ``ai.provider.api_key``)
    ================================================================

    Esta key autentica clientes **externos** contra ``/mcp`` (Cursor, Claude
    Desktop…). **No** es la credencial del gateway LLM; esa vive en
    ``ai.provider.api_key`` (solo admins, uso server-side al inferir).

    Chatboo **no** usa el valor de esta key para chatear: va por sesión Odoo +
    ``AgentEngine`` in-process. Aquí solo importa que exista
    ``mcp_api_key_hash`` (carnet de acceso UI). Ver ``docs/dos_credenciales_api.md``.

    We are the *verifier* of this credential, so we store only a one-way
    **SHA-256 hash** in ``mcp_api_key_hash``, never the plaintext. The raw key
    is shown to the admin only once, at generation time ("copy it now").
    See ``utils/api_key.py`` and ``docs/decisions/api_key_hashing.md``.

    Without a generated hash, internal AI menus and Chatboo systray stay hidden
    for that user (external MCP clients also cannot authenticate).
    """
    _name = 'ai.mcp.user'
    _description = 'MCP User'
    _rec_name = 'user_id'
    _order = 'user_id'

    # Relación One2one con res.users (campo único)
    user_id = fields.Many2one(
        'res.users',
        string='User',
        required=True,
        ondelete='cascade',
        index=True
    )

    # Campos relacionados desde el usuario (readonly)
    name = fields.Char(
        string='Name',
        related='user_id.name',
        readonly=True,
        store=True
    )

    email = fields.Char(
        string='Email',
        related='user_id.email',
        readonly=True,
        store=True
    )

    login = fields.Char(
        string='Login',
        related='user_id.login',
        readonly=True,
        store=True
    )

    # SHA-256 hash of the authentication token. We NEVER store the plaintext:
    # the raw key is shown once at generation time and then only its hash is
    # kept. Indexed for O(1) lookup on the MCP endpoint. This hash is what gets
    # exported/imported to make the key portable across instances (it is not a
    # usable secret on its own).
    mcp_api_key_hash = fields.Char(
        string='AI API Key (hash)',
        copy=False,
        readonly=True,
        index=True,
        help='One-way SHA-256 hash of the API key. The plaintext key is shown '
             'only once, at generation time. Portable across instances.'
    )

    mcp_api_key_state = fields.Selection(
        [
            ('not_generated', 'Not generated'),
            ('generated', 'Generated'),
        ],
        string='AI API Key Status',
        default='not_generated',
        readonly=True,
        copy=False
    )

    mcp_api_key_generated_date = fields.Datetime(
        string='Generated on',
        readonly=True,
        copy=False
    )

    # AI permission flags — synced with res.groups (compute + inverse).
    is_mcp_manager = fields.Boolean(
        string='AI Administrator',
        compute='_compute_is_mcp_manager',
        inverse='_inverse_is_mcp_manager',
        store=False,
        help='Full AI infrastructure management: providers, API keys, agents, '
             'system skills/contexts, logs. Implies Writer, External URL and External API.',
    )
    is_ai_writer = fields.Boolean(
        string='AI Writer',
        compute='_compute_is_ai_writer',
        inverse='_inverse_is_ai_writer',
        store=False,
        help='Create, edit or delete Odoo records via supervised safe plans (CRUD steps).',
    )
    is_ai_external_url = fields.Boolean(
        string='AI External URL',
        compute='_compute_is_ai_external_url',
        inverse='_inverse_is_ai_external_url',
        store=False,
        help='Query external HTTP/HTTPS URLs via supervised safe plans (fetch_url).',
    )
    is_ai_external_api = fields.Boolean(
        string='AI External API',
        compute='_compute_is_ai_external_api',
        inverse='_inverse_is_ai_external_api',
        store=False,
        help='Call tools on configured external API servers (MCP or OpenAPI) '
             'via supervised safe plans (api_call).',
    )

    last_mcp_client_label = fields.Char(
        string='Last MCP Client',
        readonly=True,
        copy=False,
        help='Name and version of the last external MCP client (Cursor, Claude…). '
             'Updated on each MCP initialize handshake.',
    )
    last_mcp_client_ip = fields.Char(
        string='Last MCP Client IP',
        readonly=True,
        copy=False,
    )
    last_mcp_client_seen = fields.Datetime(
        string='Last MCP Client Seen',
        readonly=True,
        copy=False,
    )

    def register_mcp_client(self, label, remote_ip=None):
        """Persist external MCP client identity (survives worker restarts)."""
        if not label:
            return
        vals = {
            'last_mcp_client_label': str(label)[:255],
            'last_mcp_client_seen': fields.Datetime.now(),
        }
        if remote_ip:
            vals['last_mcp_client_ip'] = str(remote_ip)[:64]
        self.sudo().write(vals)

    @api.model
    def get_last_mcp_client_label(self, user_id):
        if not user_id:
            return None
        mu = self.sudo().search([('user_id', '=', user_id)], limit=1)
        return mu.last_mcp_client_label if mu else None

    def _ai_security_group(self, xml_id):
        return self.env.ref('pns_ai_mcp.%s' % xml_id, raise_if_not_found=False)

    def _inverse_ai_group_flag(self, group_xml_id, field_name):
        group = self._ai_security_group(group_xml_id)
        if not group:
            return
        for record in self:
            if not record.user_id:
                continue
            enabled = record[field_name]
            if enabled:
                if not user_has_group_direct(record.user_id, group):
                    user_add_group(record.user_id, group)
                    _logger.info(
                        "MCP: Usuario %s añadido al grupo %s",
                        record.user_id.name, group_xml_id,
                    )
            elif user_has_group_direct(record.user_id, group):
                user_remove_group(record.user_id, group)
                _logger.info(
                    "MCP: Usuario %s eliminado del grupo %s",
                    record.user_id.name, group_xml_id,
                )
            invalidate_recordset_fields(record, [field_name])
            invalidate_recordset_fields(
                record.user_id, [USER_GROUPS_FIELD, USER_ALL_GROUPS_FIELD],
            )

    @api.depends('user_id')
    def _compute_is_mcp_manager(self):
        group = self._ai_security_group('group_ai_admin')
        for record in self:
            if record.user_id and group:
                record.is_mcp_manager = user_has_group(record.user_id, group)
            else:
                record.is_mcp_manager = False

    def _inverse_is_mcp_manager(self):
        self._inverse_ai_group_flag('group_ai_admin', 'is_mcp_manager')
        self._compute_is_mcp_manager()

    @api.depends('user_id')
    def _compute_is_ai_writer(self):
        group = self._ai_security_group('group_ai_writer')
        for record in self:
            if record.user_id and group:
                record.is_ai_writer = user_has_group(record.user_id, group)
            else:
                record.is_ai_writer = False

    def _inverse_is_ai_writer(self):
        self._inverse_ai_group_flag('group_ai_writer', 'is_ai_writer')
        self._compute_is_ai_writer()

    @api.depends('user_id')
    def _compute_is_ai_external_url(self):
        group = self._ai_security_group('group_ai_external_url')
        for record in self:
            if record.user_id and group:
                record.is_ai_external_url = user_has_group(record.user_id, group)
            else:
                record.is_ai_external_url = False

    def _inverse_is_ai_external_url(self):
        self._inverse_ai_group_flag('group_ai_external_url', 'is_ai_external_url')
        self._compute_is_ai_external_url()

    @api.depends('user_id')
    def _compute_is_ai_external_api(self):
        group = self._ai_security_group('group_ai_external_api')
        for record in self:
            if record.user_id and group:
                record.is_ai_external_api = user_has_group(record.user_id, group)
            else:
                record.is_ai_external_api = False

    def _inverse_is_ai_external_api(self):
        self._inverse_ai_group_flag('group_ai_external_api', 'is_ai_external_api')
        self._compute_is_ai_external_api()

    @api.model
    def user_has_mcp_api_key(self, user=None):
        """True si el usuario tiene API key MCP activa (hash no vacío)."""
        user = user or self.env.user
        for rec in self.sudo().search([('user_id', '=', user.id)]):
            raw = rec.mcp_api_key_hash
            if raw and str(raw).strip():
                return True
        return False

    @api.model_create_multi
    def create(self, vals_list):
        """Sobreescribe create para asegurar que solo se crea un registro por usuario"""
        for vals in vals_list:
            if 'user_id' in vals:
                # Verificar que no existe ya un registro para este usuario
                existing = self.with_context(mcp_skip_ensure_all_users=True).search(
                    [('user_id', '=', vals['user_id'])], limit=1,
                )
                if existing:
                    raise UserError(_('An MCP record already exists for this user'))
        
        # Filtrar campos que no existen en el modelo para evitar errores
        # (útil cuando hay contaminación cruzada de otros módulos)
        model_fields = self._fields
        filtered_vals_list = []
        for vals in vals_list:
            filtered_vals = {k: v for k, v in vals.items() if k in model_fields}
            if len(filtered_vals) != len(vals):
                extra_fields = set(vals.keys()) - set(filtered_vals.keys())
                _logger.debug("MCP: Campos ignorados al crear registro: %s", extra_fields)
            filtered_vals_list.append(filtered_vals)
        
        return super(MCPUser, self).create(filtered_vals_list)

    def write(self, vals):
        """Sobreescribe write para filtrar campos ajenos al modelo."""
        # Filtrar campos que no existen en el modelo para evitar errores
        # (útil cuando hay contaminación cruzada de otros módulos)
        model_fields = self._fields
        filtered_vals = {k: v for k, v in vals.items() if k in model_fields}
        if len(filtered_vals) != len(vals):
            extra_fields = set(vals.keys()) - set(filtered_vals.keys())
            _logger.debug("MCP: Campos ignorados al escribir registro: %s", extra_fields)
        
        return super(MCPUser, self).write(filtered_vals)

    @api.model
    def ensure_all_users_have_record(self):
        """
        Crea registros MCP para todos los usuarios internos activos que no tengan uno.
        Se llama al abrir la lista (contexto ensure_all_users).
        """
        skip = {'mcp_skip_ensure_all_users': True}
        mcp = self.env['ai.mcp.user'].with_context(**skip)
        active_users = self.env['res.users'].with_context(**skip).search([
            ('active', '=', True),
            ('share', '=', False),
        ])
        created_count = 0

        for user in active_users:
            existing = mcp.search([('user_id', '=', user.id)], limit=1)
            if not existing:
                mcp.create({'user_id': user.id})
                created_count += 1
        
        if created_count > 0:
            _logger.info("MCP: Creados %d registros MCP para usuarios existentes", created_count)
        
        return created_count

    def _store_api_key_hash(self, raw_key):
        """Persist the SHA-256 hash of ``raw_key`` (plaintext is never stored)."""
        self.ensure_one()
        try:
            self.sudo().write({
                'mcp_api_key_hash': hash_api_key(raw_key),
                'mcp_api_key_state': 'generated',
                'mcp_api_key_generated_date': fields.Datetime.now(),
            })
        except Exception as e:
            _logger.error("MCP: Error storing API key hash for user %s: %s", self.user_id.name, str(e))
            raise UserError(_("Technical error while storing API key")) from e

    def _do_generate_mcp_api_key(self):
        """
        Genera una nueva API key usando secrets, guarda SOLO su hash y devuelve
        el valor en claro UNA sola vez para mostrarlo al admin ("cópialo ahora").

        Returns:
            str: la API key en claro (no se vuelve a poder recuperar).

        Raises:
            UserError: Si falla la generación
        """
        self.ensure_one()

        # Generar API key segura (32 caracteres alfanuméricos)
        alphabet = string.ascii_letters + string.digits
        api_key = ''.join(secrets.choice(alphabet) for _ in range(32))

        self._store_api_key_hash(api_key)
        _logger.info("MCP: API key generada para usuario %s (ID: %s)", self.user_id.name, self.user_id.id)
        return api_key

    def action_generate_mcp_api_key(self):
        """
        Acción pública para generar API key. Llamada desde el wizard.

        Returns:
            str: la API key en claro (mostrar una vez; solo se guarda su hash).
        """
        self.ensure_one()
        return self._do_generate_mcp_api_key()

    def set_mcp_api_key(self, raw_key):
        """Fuerza un valor de API key elegido por el admin (como establecer una
        contraseña). Se guarda solo el hash; el admin ya conoce el valor.

        Acepta tanto texto plano (se hashea) como un hash ya calculado
        proveniente de otra instancia (se guarda tal cual).
        """
        self.ensure_one()
        if not raw_key or not str(raw_key).strip():
            raise UserError(_("The API key value cannot be empty"))
        self.sudo().write({
            'mcp_api_key_hash': normalize_to_hash(str(raw_key).strip()),
            'mcp_api_key_state': 'generated',
            'mcp_api_key_generated_date': fields.Datetime.now(),
        })
        _logger.info("MCP: API key forzada/importada para usuario %s (ID: %s)", self.user_id.name, self.user_id.id)
        return True

    def generate_mcp_api_key(self):
        """
        Abre el wizard para generar API key.
        Siempre pide confirmación, igual que geopunch_attendance.
        """
        self.ensure_one()
        
        # Siempre abrir wizard (con o sin API key)
        return {
            'type': 'ir.actions.act_window',
            'name': 'Generate AI API Key',
            'res_model': 'pns_ai_mcp.api_key_wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_mcp_user_id': self.id,
            }
        }

    def clear_mcp_api_key(self):
        """Muestra wizard de confirmación para eliminar la API key"""
        self.ensure_one()
        
        if not self.mcp_api_key_hash:
            # Si no hay API key, no hacer nada
            return mcp_ui.client_notification(
                _('Information'),
                _('This user has no API key.'),
                notification_type='info',
                sticky=False,
            )
        
        # Mostrar wizard de confirmación
        return {
            'type': 'ir.actions.act_window',
            'name': 'Eliminar API Key MCP',
            'res_model': 'pns_ai_mcp.api_key_wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_mcp_user_id': self.id,
                'default_is_clear': True,
            }
        }

    def action_import_mcp_api_key(self):
        """Abre wizard en modo importación para pegar una key existente de otra instancia."""
        self.ensure_one()
        ensure_ai_admin(self.env)
        return {
            'type': 'ir.actions.act_window',
            'name': 'Importar API Key MCP',
            'res_model': 'pns_ai_mcp.api_key_wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_mcp_user_id': self.id,
                'default_is_import': True,
            }
        }

    def name_get(self):
        """Muestra el nombre del usuario relacionado"""
        result = []
        for record in self:
            if record.user_id:
                result.append((record.id, record.user_id.name))
            else:
                result.append((record.id, 'Sin usuario'))
        return result

    @api.model
    def action_open_mcp_users_list(self):
        """Sync internal users, then open the list (menu entry)."""
        self.with_context(mcp_skip_ensure_all_users=True).ensure_all_users_have_record()
        action = self.env.ref('pns_ai_mcp.action_mcp_users').sudo().read()[0]
        ctx = action.get('context') or {}
        if isinstance(ctx, str):
            from odoo.tools.safe_eval import safe_eval
            ctx = safe_eval(ctx) if ctx else {}
        action['context'] = dict(ctx, mcp_ensure_all_users_done=True)
        return action

    @api.model
    def _maybe_ensure_all_users(self):
        """Auto-create MCP rows when opening the Users list (ensure_all_users context)."""
        if not self.env.context.get('ensure_all_users'):
            return
        if self.env.context.get('mcp_skip_ensure_all_users'):
            return
        if self.env.context.get('mcp_ensure_all_users_done'):
            return
        self.with_context(
            mcp_skip_ensure_all_users=True,
            mcp_ensure_all_users_done=True,
        ).ensure_all_users_have_record()

    @api.model
    def _search(self, domain, *args, **kwargs):
        """O17+ list views call _search/search_fetch, not search/search_read."""
        self._maybe_ensure_all_users()
        return super(MCPUser, self)._search(domain, *args, **kwargs)

    @api.model
    def search_fetch(self, domain, *args, **kwargs):
        self._maybe_ensure_all_users()
        return super(MCPUser, self).search_fetch(domain, *args, **kwargs)

    @api.model
    def web_search_read(self, domain, *args, **kwargs):
        # Firma agnóstica de versión: Odoo 14/15/16 usan (domain, fields, ...) sin
        # count_limit; Odoo 17+ usa (domain, specification, ..., count_limit). Solo
        # interceptamos para autocrear filas y reenviamos los argumentos tal cual.
        self._maybe_ensure_all_users()
        return super(MCPUser, self).web_search_read(domain, *args, **kwargs)

    @api.model
    def search(self, domain, *args, **kwargs):
        self._maybe_ensure_all_users()
        return super(MCPUser, self).search(domain, *args, **kwargs)

    @api.model
    def search_read(self, *args, **kwargs):
        self._maybe_ensure_all_users()
        return super(MCPUser, self).search_read(*args, **kwargs)

    # Fields managed specially during import/export (identity, relational)
    _EXPORT_SKIP_FIELDS = {
        'id', 'create_uid', 'create_date', 'write_uid', 'write_date',
        '__last_update', 'display_name',
        'user_id',  # set by the wizard from the login match
    }

    @api.model
    def _import_vals_from_json_row(self, user_data):
        """Build ORM vals from a JSON row using dynamic field introspection.

        RESILIENT: iterates model._fields via portable_io. Unknown/invalid
        keys are skipped with a warning — never blocks the import.

        Accepts both:
        - new exports: ``mcp_api_key_hash`` (already hashed → stored as-is).
        - legacy exports / manual entries: ``mcp_api_key`` or ``api_key``
          (plaintext → hashed on the fly).

        Returns: (vals_dict, has_api_key, warnings_list)
        """
        warnings = []

        # ── Credential: prefer the already-hashed value, fall back to legacy
        #    plaintext keys (which we hash). We never persist plaintext. ──
        key_hash = ''
        try:
            raw = (
                user_data.get('mcp_api_key_hash')
                or user_data.get('mcp_api_key')
                or user_data.get('api_key')
                or ''
            )
            if isinstance(raw, str) and raw.strip():
                key_hash = normalize_to_hash(raw.strip())
        except Exception as e:
            warnings.append("api_key: %s" % e)

        # Dynamic field mapping. We skip the credential fields here and set them
        # explicitly below so a legacy plaintext value never lands verbatim.
        vals, field_warnings = import_vals_from_dict(
            self, user_data,
            skip_fields={'user_id', 'mcp_api_key', 'api_key', 'mcp_api_key_hash'},
        )
        warnings.extend(field_warnings)

        if key_hash:
            vals['mcp_api_key_hash'] = key_hash
            vals['mcp_api_key_state'] = 'generated'
            vals['mcp_api_key_generated_date'] = fields.Datetime.now()

        return vals, bool(key_hash), warnings

    def _export_user_dict(self):
        """Export a single user record to a portable dict using dynamic fields."""
        try:
            data = export_record_dict(self, skip_fields={'user_id'})
        except Exception:
            data = {'login': self.login or '', 'name': self.name or ''}
        # Extra: group membership flags (not model fields but useful for portability)
        try:
            if self.user_id:
                data['is_ai_admin'] = self.user_id.has_group('pns_ai_mcp.group_ai_admin')
                data['is_ai_writer'] = self.user_id.has_group('pns_ai_mcp.group_ai_writer')
                data['is_ai_external_url'] = self.user_id.has_group(
                    'pns_ai_mcp.group_ai_external_url')
                data['is_ai_external_api'] = self.user_id.has_group(
                    'pns_ai_mcp.group_ai_external_api')
        except Exception:
            pass
        return data

    def action_export_users(self, *args, **kwargs):
        """Export all MCP users to a JSON file (portable; not Odoo CSV export)."""
        ensure_ai_admin(self.env)
        del args, kwargs
        users = self.env['ai.mcp.user'].search([])
        if not users:
            return mcp_ui.open_json_export_empty_wizard(
                self.env,
                dialog_title=_('Export'),
                message=_('There are no users to export.'),
            )
        
        export_data = [user._export_user_dict() for user in users]
        
        filename = mcp_ui.build_export_filename(self.env, 'mcp_users', 'json')
        attachment = mcp_ui.write_json_attachment(
            self.env, filename, export_data,
        )
        
        return mcp_ui.open_json_export_wizard(
            self.env,
            dialog_title=_('Export result'),
            summary_text=_('%s user(s) exported.') % len(export_data),
            count=len(export_data),
            attachment=attachment,
        )

    def action_export_selected(self, *args, **kwargs):
        """Export selected MCP users to JSON (tree multi-select action)."""
        ensure_ai_admin(self.env)
        del args, kwargs
        if not self:
            return mcp_ui.open_json_export_empty_wizard(
                self.env,
                dialog_title=_('Export'),
                message=_('No users selected for export.'),
            )
        export_data = [user._export_user_dict() for user in self]

        filename = mcp_ui.build_export_filename(self.env, 'mcp_users_selected', 'json')
        attachment = mcp_ui.write_json_attachment(
            self.env, filename, export_data,
        )
        return mcp_ui.open_json_export_wizard(
            self.env,
            dialog_title=_('Export result'),
            summary_text=_('%s user(s) exported.') % len(export_data),
            count=len(export_data),
            attachment=attachment,
        )

    def action_import_users(self, *args, **kwargs):
        """Open wizard to import MCP users from JSON."""
        ensure_ai_admin(self.env)
        del args, kwargs
        return {
            'type': 'ir.actions.act_window',
            'name': _('Import MCP Users'),
            'res_model': 'pns_ai_mcp.import_users_wizard',
            'view_mode': 'form',
            'views': [[False, 'form']],
            'target': 'new',
        }

