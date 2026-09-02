# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""PNS AI MCP - Safe Operation. PATANEGRA Soft (https://patanegra.com).

Part of Patanegra Soft Suite (`pns_suite`), distributed via Patanegra Soft Hub.
Core of the Patanegra Application Agent Protocol (PAAP): the "two boxes"
principle -- the AI proposes an intent as data (Box A) and a human (or a
pre-configured trust policy) authorizes it, so the server executes it with
fixed, audited code the AI can neither see nor invoke (Box B). Governs
supervised writes, egress/URLs and calls to external MCP servers.
Licensed under the Apache License 2.0 - see LICENSE.
"""

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools.misc import formatLang
from datetime import datetime, timedelta
import json
import random
import logging
from ..constants import SERVIDOR_MCP_SOLICITUD, SERVIDOR_MCP_COMPLETADO, PIN_EXPIRY_MINUTES
from ..utils import mcp_ui
from ..utils.import_export_guard import ensure_ai_admin
from ..utils.portable_io import export_record_dict

_logger = logging.getLogger(__name__)

class MCPSafeOperation(models.Model):
    """AI Supervised Operation — the 'Safe Plan' (Caja B).

    The AI NEVER executes operations directly. It DECLARES an intent as data
    (a list of steps with closed verbs: create/write/copy/unlink/fetch_url/api_call).
    The intent is saved as a pending operation, the human is notified via toast
    in Odoo, and ONLY when the human clicks Confirm does the server execute
    the plan using fixed, audited code. The AI cannot see or invoke this code.

    Danger levels (traffic light):
      🟢 Low:    create, copy, fetch_url (whitelisted domain)
      🟡 Medium: write
      🔴 High:   unlink
    """
    _name = 'ai.safe.operation'
    _description = 'AI Supervised Operation'
    _order = 'create_date desc'
    _rec_name = 'display_name'

    # Identificación de la operación
    verification_id = fields.Char(
        string='Verification ID',
        required=True,
        readonly=True,
        index=True,
        default=lambda self: self._generate_verification_id(),
        help='Unique identifier of the verification'
    )

    # Turn correlation: id of the conversation turn that proposed this plan, so
    # the later execute_safe_plan audit row threads under the same operation
    # code (e.g. MT0X) instead of appearing orphaned in the log.
    correlation_id = fields.Char(
        string='Turn Correlation',
        readonly=True,
        index=True,
        help='Correlation id of the turn that proposed this plan',
    )
    
    operation_type = fields.Selection(
        [
            ('create', 'Create'),
            ('write', 'Update'),
            ('unlink', 'Delete'),
            ('fetch_url', 'Fetch URL'),
            ('api_call', 'API Call'),
            # Legacy value kept so historical rows keep rendering.
            ('mcp_call', 'MCP Call (legacy)'),
            ('action', 'Action'),
        ],
        string='Operation Type',
        required=True,
        readonly=True,
        index=True
    )

    # Danger level (traffic light)
    danger_level = fields.Selection(
        [
            ('low', '🟢 Low'),
            ('medium', '🟡 Medium'),
            ('high', '🔴 High'),
        ],
        string='Danger Level',
        default='medium',
        readonly=True,
        index=True,
        help='Risk level of the operation: low (create/copy/url), medium (write), high (unlink)'
    )
    
    # Información del modelo y registros
    model_name = fields.Char(
        string='Model',
        required=True,
        readonly=True,
        index=True,
        help='Name of the affected Odoo model (e.g.: calendar.event)'
    )
    
    records_count = fields.Integer(
        string='Affected Records',
        required=True,
        readonly=True,
        help='Number of records that will be affected by the operation'
    )
    
    # Información de cambios (JSON serializado)
    changes_info = fields.Text(
        string='Changes Info',
        readonly=True,
        help='Detailed information about the proposed changes (serialized JSON)'
    )
    
    # Usuario que solicitó la operación
    user_id = fields.Many2one(
        'res.users',
        string='User',
        required=True,
        readonly=True,
        index=True,
        ondelete='cascade'
    )

    # Confirmación ligada a sesión: usuario humano que confirmó desde el navegador
    confirmed_by_uid = fields.Many2one(
        'res.users',
        string='Confirmed by',
        readonly=True,
        help='User (browser session) who confirmed the operation from the toast'
    )

    # Guarda contra doble ejecución de la misma verificación
    executed = fields.Boolean(
        string='Executed',
        default=False,
        readonly=True,
        help='True when the confirmed operation has already been executed (prevents double execution)'
    )

    # Resultado de la ejecución del plan declarativo (caja B), JSON serializado
    result_info = fields.Text(
        string='Execution result',
        readonly=True,
        help='Result of executing the plan after human confirmation (serialized JSON)'
    )

    # Estado de la verificación
    status = fields.Selection(
        [
            ('pending', 'Pending'),
            ('confirmed', 'Confirmed'),
            ('cancelled', 'Cancelled'),
            ('expired', 'Expired'),
        ],
        string='Status',
        required=True,
        default='pending',
        readonly=True,
        index=True
    )
    
    # Fecha de creación
    create_date = fields.Datetime(
        string='Creation Date',
        required=True,
        readonly=True,
        default=fields.Datetime.now,
        index=True
    )
    
    # Fecha de expiración
    expires_at = fields.Datetime(
        string='Expires at',
        required=True,
        readonly=True,
        compute='_compute_expires_at',
        store=True,
        help='Date and time when this verification expires'
    )
    

    
    # Marca VIVA (no almacenada) de si una verificación pendiente ya caducó.
    # Permite que el formulario muestre "caducada" sin esperar a un cron.
    is_expired = fields.Boolean(
        string='Expired',
        compute='_compute_is_expired',
        help='True when a pending verification has passed its expiration time'
    )

    # Fecha de confirmación/cancelación
    resolved_at = fields.Datetime(
        string='Resolved at',
        readonly=True,
        help='Date and time when the verification was confirmed or cancelled'
    )

    # ── Temporal scope (for fetch_url reuse) ──────────────────────────────
    valid_from = fields.Datetime(
        string='Valid from',
        readonly=True,
        help='Start of validity window for URL permissions. Empty = valid immediately.'
    )
    valid_until = fields.Datetime(
        string='Valid until',
        readonly=True,
        help='End of validity window for URL permissions. Empty = single-use (CRUD default).'
    )
    
    # Información adicional (tool_name, arguments, etc.)
    tool_name = fields.Char(
        string='MCP Tool',
        readonly=True,
        help='Name of the MCP tool that requested the operation'
    )
    
    operation_data = fields.Text(
        string='Operation Data',
        readonly=True,
        help='Complete data of the pending operation (serialized JSON)'
    )
    
    # Nombre para mostrar
    display_name = fields.Char(
        string='Name',
        compute='_compute_display_name',
        store=False
    )
    
    @api.depends('operation_type', 'model_name', 'records_count', 'create_date')
    def _compute_display_name(self):
        """Calcula el nombre para mostrar"""
        for record in self:
            op_type = dict(record._fields['operation_type'].selection).get(record.operation_type, '')
            record.display_name = f"{op_type} - {record.model_name} ({record.records_count} registros) - {record.create_date.strftime('%Y-%m-%d %H:%M') if record.create_date else ''}"
    
    @api.depends('create_date')
    def _compute_expires_at(self):
        """Calcula la fecha de expiración del PIN (PIN_EXPIRY_MINUTES después de la creación)"""
        for record in self:
            base = record.create_date or fields.Datetime.now()
            record.expires_at = base + timedelta(minutes=PIN_EXPIRY_MINUTES)

    @api.depends('expires_at', 'status', 'executed')
    def _compute_is_expired(self):
        """True si ya pasó caducidad y no está ejecutada (pending/confirmed/expired).

        No se almacena: se recalcula en cada lectura. El status persistido
        ``expired`` se actualiza al abrir la lista/form o desde Herramientas
        (sin cron nuevo).
        """
        now = fields.Datetime.now()
        for record in self:
            past = bool(record.expires_at and record.expires_at < now)
            record.is_expired = bool(
                past
                and not record.executed
                and record.status in ('pending', 'confirmed', 'expired')
            )

    # Botones de UI: solo acciones que aún tienen sentido (como whitelist ya
    # cubierta → sin botón «añadir»).
    can_resolve = fields.Boolean(
        string='Can confirm/cancel',
        compute='_compute_action_flags',
        help='Pending and not expired — show Confirm/Cancel',
    )
    can_apply = fields.Boolean(
        string='Can apply',
        compute='_compute_action_flags',
        help='Confirmed and not yet executed — Confirm retries the write',
    )
    can_add_whitelist = fields.Boolean(
        string='Can add to whitelist',
        compute='_compute_action_flags',
        help='fetch_url whose domain is not yet trusted (whitelist or open policy)',
    )

    @api.depends(
        'status', 'expires_at', 'executed', 'operation_type', 'operation_data',
    )
    def _compute_action_flags(self):
        Whitelist = self.env['ai.url.whitelist'].sudo()
        policy_open = Whitelist.is_url_access_open()
        now = fields.Datetime.now()
        for record in self:
            past = bool(record.expires_at and record.expires_at < now)
            record.can_resolve = bool(
                record.status == 'pending' and not past
            )
            # Confirmed sin execute solo es accionable dentro de la ventana.
            record.can_apply = bool(
                record.status == 'confirmed'
                and not record.executed
                and not past
            )
            show_wl = False
            if record.operation_type == 'fetch_url' and not policy_open:
                domain = record._extract_fetch_url_domain()
                if domain and not Whitelist.is_domain_whitelisted(domain):
                    show_wl = True
            record.can_add_whitelist = show_wl

    def _can_resolve(self):
        """Quién puede confirmar/cancelar: el usuario que la solicitó O un
        administrador de MCP (group_ai_admin), que puede resolver las de otros."""
        self.ensure_one()
        return (
            self.env.user.id == self.user_id.id
            or self.env.user.has_group('pns_ai_mcp.group_ai_admin')
        )
    
    # IP del solicitante (para auditoría / estadísticas de seguridad)
    request_ip = fields.Char(
        string='Request IP',
        readonly=True,
        index=True,
        help='IP address of the client that requested this operation',
    )

    fetch_url_display = fields.Char(
        string='URL',
        compute='_compute_fetch_url_display',
        store=False,
        help='Target URL for fetch_url operations (extracted from operation_data)',
    )

    @api.depends('operation_type', 'operation_data')
    def _compute_fetch_url_display(self):
        """Extract the full URL from the first fetch_url step in operation_data."""
        for record in self:
            if record.operation_type != 'fetch_url':
                record.fetch_url_display = False
                continue
            try:
                data = record.get_operation_data() or {}
                steps = data.get('plan_steps', [])
                for step in steps:
                    if step.get('op') == 'fetch_url' and step.get('url'):
                        record.fetch_url_display = step['url']
                        break
                else:
                    record.fetch_url_display = False
            except Exception:
                record.fetch_url_display = False

    # ── Typed verification IDs ─────────────────────────────────────────
    # Fixed-width codes: 4-char verb prefix + 4-digit counter per verb.
    # This enables security analytics by operation type at a glance.
    #   CREA0001, CREA0002, ...  (create)
    #   WRIT0001, WRIT0002, ...  (write)
    #   COPY0001, COPY0002, ...  (copy)
    #   UNLK0001, UNLK0002, ...  (unlink)
    #   FURL0001, FURL0002, ...  (fetch_url)

    _VERB_PREFIX = {
        'create':    'CREA',
        'write':     'WRIT',
        'copy':      'COPY',
        'unlink':    'UNLK',
        'fetch_url': 'FURL',
        'api_call':  'APIC',
        'mcp_call':  'MCPC',  # legacy alias rows
    }

    def _get_verification_sequence(self, verb=None):
        """Obtiene (o crea si no existe) la secuencia tipada por verbo.

        Each verb has its own ir.sequence with its own counter.
        Legacy sequence 'pns_ai_mcp.operation' is kept but not used for new records.
        """
        prefix = self._VERB_PREFIX.get(verb, 'SAFE')
        seq_code = f'pns_ai_mcp.safe_op.{verb or "generic"}'
        seq = self.env['ir.sequence'].sudo().search([
            ('code', '=', seq_code)
        ], limit=1)
        if not seq:
            seq = self.env['ir.sequence'].sudo().create({
                'name': f'Safe Operation – {prefix}',
                'code': seq_code,
                'implementation': 'standard',
                'prefix': prefix,
                'padding': 8,
            })
        else:
            vals = {}
            if seq.prefix != prefix:
                vals['prefix'] = prefix
            if seq.padding != 8:
                vals['padding'] = 8
            if vals:
                seq.write(vals)
        return seq

    def _generate_verification_id(self, verb=None):
        """Genera un ID tipado por verbo: CREA0001, WRIT0042, FURL0003, etc.

        Falls back to the legacy sequence if verb is not provided (backwards
        compatible with the default= lambda on the field).
        """
        if not verb:
            # Called from default= lambda (no verb yet). Use legacy sequence.
            self._get_verification_sequence(verb=None)
            vid = self.env['ir.sequence'].next_by_code('pns_ai_mcp.safe_op.generic')
            return vid or 'SAFE0000'
        self._get_verification_sequence(verb=verb)
        seq_code = f'pns_ai_mcp.safe_op.{verb}'
        vid = self.env['ir.sequence'].next_by_code(seq_code)
        if not vid:
            raise ValueError(
                f"MCP: Error generando verification_id para verbo '{verb}': "
                f"la secuencia '{seq_code}' no devolvió un valor."
            )
        return vid
    
    @api.model
    def _resolve_turn_correlation(self, correlation_id=None):
        """Correlación del turno MCP: argumento > context > http request."""
        if correlation_id:
            return correlation_id
        ctx_corr = (self.env.context or {}).get('mcp_correlation_id')
        if ctx_corr:
            return ctx_corr
        try:
            from odoo.http import request as http_request
            return getattr(http_request, 'mcp_corr_id', None) or None
        except Exception:
            return None

    @api.model
    def create_verification(self, operation_type, model_name, records_count,
                            changes_info, user_id, tool_name=None,
                            operation_data=None, request_ip=None,
                            correlation_id=None):
        """Crea una nueva operación supervisada (Safe Plan).

        :param operation_type: Primary verb ('create', 'write', 'unlink', 'fetch_url')
        :param model_name: Nombre del modelo afectado
        :param records_count: Número de registros / pasos
        :param changes_info: Información de cambios (dict → JSON)
        :param user_id: ID del usuario que solicitó la operación
        :param tool_name: Nombre de la herramienta MCP (opcional)
        :param operation_data: Datos completos de la operación (dict → JSON)
        :param request_ip: IP del cliente (opcional, para auditoría)
        :param correlation_id: Código de sesión del turno MCP (p. ej. VWVN)
        :return: Recordset de la verificación creada
        """
        # Caducar pendientes vencidos (SKIP LOCKED). No bloquear propose si hay
        # filas locked por un execute a medias.
        try:
            self.cleanup_expired()
        except Exception as cleanup_err:
            _logger.warning(
                'MCP: cleanup_expired en create_verification ignorado: %s',
                cleanup_err,
            )

        # La confirmación es por sesión (toast + endpoint auth='user'), NO por PIN:
        # la IA puede leer la BD (relaxaicode), así que ningún secreto persistido es seguro.
        changes_info_json = json.dumps(changes_info, default=str) if isinstance(changes_info, dict) else (changes_info or '')
        operation_data_json = json.dumps(operation_data, default=str) if isinstance(operation_data, dict) else (operation_data or '')

        now = fields.Datetime.now()
        expires_at = now + timedelta(minutes=PIN_EXPIRY_MINUTES)

        # Extract danger_level from changes_info or operation_data
        dl = 'medium'
        if isinstance(changes_info, dict):
            dl = changes_info.get('danger_level', 'medium')
        elif isinstance(operation_data, dict):
            dl = operation_data.get('danger_level', 'medium')

        # Generate typed verification_id: CREA0001, WRIT0042, FURL0003, ...
        typed_vid = self._generate_verification_id(verb=operation_type)

        # Prefer an explicit correlation (propose captures it before opening a
        # nested cursor). Fallback: context / live request attribute.
        turn_corr = self._resolve_turn_correlation(correlation_id)

        verification = self.create({
            'verification_id': typed_vid,
            'operation_type': operation_type,
            'model_name': model_name,
            'records_count': records_count,
            'changes_info': changes_info_json,
            'user_id': user_id,
            'status': 'pending',
            'tool_name': tool_name,
            'operation_data': operation_data_json,
            'expires_at': expires_at,
            'danger_level': dl,
            'request_ip': request_ip or '',
            'correlation_id': turn_corr or None,
        })

        return verification

    def _model_display(self):
        """Nombre amigable del modelo afectado (para el toast)."""
        self.ensure_one()
        model_display = self.model_name or 'Desconocido'
        if not self.model_name:
            return model_display
        try:
            if self.model_name == 'ir.filters':
                return 'Filtro personalizado'
            model_class = self.env.get(self.model_name)
            if model_class is not None and hasattr(model_class, '_description') and model_class._description:
                return model_class._description
            model_record = self.env['ir.model'].sudo().with_context(
                lang=self.user_id.lang or 'es_ES'
            ).search([('model', '=', self.model_name)], limit=1)
            if model_record and model_record.name:
                return model_record.name
        except Exception:
            pass
        return model_display

    def confirm_by_user(self, confirmed_uid=None):
        """
        Confirma la operación desde la sesión del navegador del humano.
        La comprobación de propiedad (user_id == usuario de sesión) la hace el endpoint.

        Preferir ``resolve_confirm_and_execute`` (toast y Autorizaciones): es
        idempotente y serializa ambas UIs. Este método queda para compat.
        """
        self.ensure_one()
        now = fields.Datetime.now()
        if self.status != 'pending':
            raise ValidationError(f"La verificación {self.verification_id} ya no está pendiente (estado: {self.status})")
        if self.expires_at and now > self.expires_at:
            self.status = 'expired'
            self.resolved_at = now
            raise ValidationError(f"La verificación {self.verification_id} ha expirado")
        self.status = 'confirmed'
        self.confirmed_by_uid = confirmed_uid or self.env.uid
        self.resolved_at = now
        _logger.info("MCP: Verificación %s confirmada por sesión (uid=%s)", self.verification_id, self.confirmed_by_uid.id if self.confirmed_by_uid else None)

        # Auto-whitelist: if the config flag is ON and this is a fetch_url,
        # add the domain to the whitelist so future requests are 🟢.
        if self.operation_type == 'fetch_url':
            self._maybe_auto_whitelist()

        return True

    def _lock_row_nowait(self):
        """FOR UPDATE NOWAIT: toast vs Autorizaciones no se bloquean mutuamente."""
        self.ensure_one()
        try:
            self.env.cr.execute(
                'SELECT id FROM %s WHERE id = %%s FOR UPDATE NOWAIT' % self._table,
                (self.id,),
            )
            return True
        except Exception as exc:
            msg = str(exc).lower()
            if (
                'nowait' in msg
                or 'could not obtain lock' in msg
                or '55p03' in msg
                or 'lock_not_available' in msg
            ):
                try:
                    self.env.cr.rollback()
                except Exception:
                    pass
                return False
            raise

    def resolve_confirm(self, confirmed_uid=None):
        """Fase A — SOLO confirmar (TX corta, NOWAIT). Nunca ejecuta el plan.

        Contrato robusto: el HTTP de Confirmar del toast solo llama esto.
        Así un lock en el destino / worker zombie no puede colgar Odoo al
        confirmar. El apply es ``resolve_execute`` en otra petición.
        """
        self.ensure_one()
        from odoo import api
        from ..controllers.safe_plan import (
            attach_verification_chat_hints,
            build_verification_followup_message,
        )
        from ..utils.compat import invalidate_recordset_fields

        confirmed_uid = confirmed_uid or self.env.uid
        data = self.get_operation_data() or {}
        title = data.get('title') or _('Supervised operation')
        steps = data.get('plan_steps') or []
        vid = self.verification_id
        op_id = self.id
        registry = self.env.registry
        context = dict(self.env.context)

        with registry.cursor() as cr1:
            # Fail-fast: si hay contención, busy al momento (no esperar).
            cr1.execute("SET LOCAL lock_timeout = '2s'")
            cr1.execute("SET LOCAL statement_timeout = '5s'")
            env1 = api.Environment(cr1, confirmed_uid, context)
            op1 = env1['ai.safe.operation'].browse(op_id)
            if not op1.exists():
                return {
                    'success': False,
                    'error': 'not_found',
                    'verification_id': vid,
                }
            if not op1._lock_row_nowait():
                return {
                    'success': False,
                    'busy': True,
                    'error': 'busy',
                    'verification_id': vid,
                }

            invalidate_recordset_fields(
                op1,
                ['status', 'executed', 'result_info', 'expires_at',
                 'confirmed_by_uid', 'resolved_at'],
            )
            op1 = op1.browse(op_id)

            if op1.executed:
                results = None
                if op1.result_info:
                    try:
                        results = json.loads(op1.result_info)
                    except Exception:
                        results = None
                return attach_verification_chat_hints(
                    {
                        'success': True,
                        'status': 'executed',
                        'idempotent': True,
                        'verification_id': vid,
                        'results': results,
                        'followup_message': build_verification_followup_message(
                            title, results=results, action='confirm',
                        ),
                    },
                    title, results=results, action='confirm', steps=steps,
                    env=env1,
                )

            if op1.status in ('cancelled', 'expired'):
                return {
                    'success': False,
                    'error': 'not_pending',
                    'status': op1.status,
                    'verification_id': vid,
                }

            now = fields.Datetime.now()
            if op1.status == 'pending':
                if op1.expires_at and now > op1.expires_at:
                    op1.write({'status': 'expired', 'resolved_at': now})
                    cr1.commit()
                    return {
                        'success': False,
                        'error': 'expired',
                        'status': 'expired',
                        'verification_id': vid,
                    }
                op1.write({
                    'status': 'confirmed',
                    'confirmed_by_uid': confirmed_uid,
                    'resolved_at': now,
                })
                _logger.info(
                    'MCP: Verificación %s confirmada (uid=%s) — sin execute',
                    vid, confirmed_uid,
                )
                if op1.operation_type == 'fetch_url':
                    op1._maybe_auto_whitelist()
                cr1.commit()
            elif op1.status == 'confirmed':
                cr1.commit()
            else:
                return {
                    'success': False,
                    'error': 'not_pending',
                    'status': op1.status,
                    'verification_id': vid,
                }

        return attach_verification_chat_hints(
            {
                'success': True,
                'status': 'confirmed',
                'needs_execute': True,
                'verification_id': vid,
                'followup_message': build_verification_followup_message(
                    title, action='confirm',
                ),
            },
            title, action='confirm', steps=steps,
        )

    def resolve_execute(self, confirmed_uid=None):
        """Fase B — aplicar el plan (otra petición HTTP, con timeouts PG).

        Idempotente. Si otro worker tiene el claim o el destino está locked,
        devuelve busy/async sin colgar el worker más del statement_timeout.
        """
        self.ensure_one()
        from ..controllers.safe_plan import (
            attach_verification_chat_hints,
            build_verification_followup_message,
        )
        from ..utils.compat import invalidate_recordset_fields

        confirmed_uid = confirmed_uid or self.env.uid
        data = self.get_operation_data() or {}
        title = data.get('title') or _('Supervised operation')
        steps = data.get('plan_steps') or []
        vid = self.verification_id
        op_id = self.id
        context = dict(self.env.context)

        invalidate_recordset_fields(
            self, ['status', 'executed', 'result_info', 'operation_data'],
        )
        self = self.browse(op_id)
        if self.executed:
            results = None
            if self.result_info:
                try:
                    results = json.loads(self.result_info)
                except Exception:
                    results = None
            return attach_verification_chat_hints(
                {
                    'success': True,
                    'status': 'executed',
                    'idempotent': True,
                    'verification_id': vid,
                    'results': results,
                    'followup_message': build_verification_followup_message(
                        title, results=results, action='confirm',
                    ),
                },
                title, results=results, action='confirm', steps=steps,
                env=self.env,
            )
        if self.status != 'confirmed':
            return {
                'success': False,
                'error': 'not_confirmed',
                'status': self.status,
                'verification_id': vid,
            }
        if not steps:
            return attach_verification_chat_hints(
                {
                    'success': True,
                    'status': 'confirmed',
                    'verification_id': vid,
                    'followup_message': build_verification_followup_message(
                        title, action='confirm',
                    ),
                },
                title, action='confirm', steps=steps,
            )

        out = self._execute_plan_with_timeouts(
            op_id, confirmed_uid, context, vid, title,
        )
        if out.get('success') and out.get('status') == 'executed':
            return attach_verification_chat_hints(
                out, title, results=out.get('results'), action='confirm',
                steps=steps, env=self.env,
            )
        # No tumbar la confirmación: el humano ya autorizó.
        soft = _(
            '«%s» is confirmed. Applying the changes — this may take a moment.'
        ) % title
        return attach_verification_chat_hints(
            {
                'success': True,
                'status': 'confirmed',
                'async_execute': True,
                'busy': bool(out.get('busy')),
                'error': out.get('error'),
                'verification_id': vid,
                'followup_message': build_verification_followup_message(
                    title, action='confirm',
                ),
                'user_ack_message': soft if any(
                    isinstance(s, dict) and s.get('op') in (
                        'create', 'write', 'copy', 'unlink',
                    )
                    for s in steps
                ) else None,
            },
            title, action='confirm', steps=steps,
        )

    def resolve_confirm_and_execute(self, confirmed_uid=None):
        """Compat Autorizaciones: confirm + execute en dos fases internas.

        El toast Chatboo NO debe usar esto: llama ``resolve_confirm`` y luego
        ``resolve_execute`` en HTTP distintos.
        """
        out = self.resolve_confirm(confirmed_uid=confirmed_uid)
        if not out.get('success'):
            return out
        if out.get('status') == 'executed' or out.get('idempotent'):
            return out
        if not out.get('needs_execute', True):
            return out
        return self.resolve_execute(confirmed_uid=confirmed_uid)

    @api.model
    def _execute_plan_with_timeouts(self, op_id, uid, context, vid, title):
        """Execute in a fresh cursor with PG fail-fast timeouts (un solo vuelo)."""
        from odoo import api
        from ..controllers.safe_plan import build_verification_followup_message

        registry = self.env.registry
        try:
            with registry.cursor() as cr2:
                cr2.execute("SET LOCAL lock_timeout = '5s'")
                cr2.execute("SET LOCAL statement_timeout = '15s'")
                env2 = api.Environment(cr2, uid, context or {})
                op2 = env2['ai.safe.operation'].browse(op_id)
                results = op2.execute_plan_now()
                if results is False:
                    # Otra sesión ya tiene el claim de execute (NOWAIT).
                    return {
                        'success': False,
                        'busy': True,
                        'error': 'busy',
                        'verification_id': vid,
                        'confirmed': True,
                    }
                cr2.commit()
        except Exception as exc:
            _logger.error(
                'MCP: Error ejecutando plan %s: %s', vid, exc, exc_info=True,
            )
            err = str(exc)
            low = err.lower()
            if (
                'lock_timeout' in low
                or 'canceling statement' in low
                or 'statement timeout' in low
                or 'querycanceled' in low
            ):
                err = (
                    'timeout_or_lock: otro proceso bloquea el registro destino '
                    '(suele ser un worker Odoo zombie). Reinicia el contenedor '
                    'Odoo; la operación ya quedó confirmed. Detalle: %s'
                ) % err
            return {
                'success': False,
                'status': 'error',
                'error': err,
                'verification_id': vid,
                'confirmed': True,
                'followup_message': build_verification_followup_message(
                    title, action='confirm', error=err,
                ),
            }

        if results is None:
            return {
                'success': True,
                'status': 'confirmed',
                'verification_id': vid,
                'followup_message': build_verification_followup_message(
                    title, action='confirm',
                ),
            }
        # Hints (user_ack / needs_llm) added by resolve_execute.
        return {
            'success': True,
            'status': 'executed',
            'verification_id': vid,
            'results': results,
            'followup_message': build_verification_followup_message(
                title, results=results, action='confirm',
            ),
        }

    @api.model
    def cleanup_stuck_state(self, older_than_minutes=10):
        """Limpiador de estado Safe Plan (el que faltaba).

        ``cleanup_expired`` solo toca ``pending`` vencidos. El agujero real es
        ``confirmed`` + ``executed=False`` (auto-confirm/toast a medias, 6YR2):
        deja la cola zombie y el siguiente propose/orquestación se atasca.

        1. Suelta claims ``_executing`` huérfanos.
        2. Reintenta execute (un vuelo, con timeouts).
        3. Lo que siga confirmed sin execute y más viejo que
           ``older_than_minutes`` → ``cancelled`` con diagnóstico.

        Early-exit barato: si no hay cola stuck, no abre cursores ni reintentos.
        """
        stats = {'claims_cleared': 0, 'executed': 0, 'cancelled': 0}
        stuck_n = self.search_count([
            ('status', '=', 'confirmed'),
            ('executed', '=', False),
        ])
        if not stuck_n:
            return stats
        stats['claims_cleared'] = self._clear_stale_execute_claims(
            older_than_seconds=45,
        )
        stats['executed'] = self._retry_confirmed_not_executed(limit=20)
        stats['cancelled'] = self._cancel_stale_confirmed_not_executed(
            older_than_minutes=older_than_minutes,
        )
        if any(stats.values()):
            _logger.warning(
                'MCP: cleanup_stuck_state claims=%s executed=%s cancelled=%s',
                stats['claims_cleared'], stats['executed'], stats['cancelled'],
            )
        return stats

    @api.model
    def _retry_confirmed_not_executed(self, limit=20):
        """Un intento de execute por op confirmed pendiente."""
        from odoo import api, SUPERUSER_ID

        pending = self.search([
            ('status', '=', 'confirmed'),
            ('executed', '=', False),
        ], order='id', limit=limit)
        if not pending:
            return 0

        done = 0
        registry = self.env.registry
        for op_meta in pending:
            uid = (
                op_meta.confirmed_by_uid.id
                or op_meta.user_id.id
                or SUPERUSER_ID
            )
            try:
                with registry.cursor() as cr:
                    cr.execute("SET LOCAL lock_timeout = '8s'")
                    cr.execute("SET LOCAL statement_timeout = '25s'")
                    env = api.Environment(cr, uid, {})
                    rec = env['ai.safe.operation'].browse(op_meta.id)
                    results = rec.execute_plan_now()
                    if results is False:
                        continue
                    cr.commit()
                    if env['ai.safe.operation'].browse(op_meta.id).executed:
                        done += 1
                        _logger.info(
                            'MCP: retry execute OK for %s', rec.verification_id,
                        )
            except Exception as exc:
                _logger.warning(
                    'MCP: retry execute skip id=%s: %s', op_meta.id, exc,
                )
        return done

    @api.model
    def _cancel_stale_confirmed_not_executed(self, older_than_minutes=10):
        """Cancela confirmed sin execute demasiado viejos (estado zombie)."""
        mins = max(2, int(older_than_minutes))
        cutoff = fields.Datetime.now() - timedelta(minutes=mins)
        stuck = self.search([
            ('status', '=', 'confirmed'),
            ('executed', '=', False),
            ('write_date', '<', cutoff),
        ], order='id', limit=50)
        if not stuck:
            return 0
        now = fields.Datetime.now()
        for op in stuck:
            op.sudo().write({
                'status': 'cancelled',
                'resolved_at': now,
                'result_info': json.dumps({
                    'error': 'stuck_state_cleaner',
                    'detail': (
                        'confirmed without execute for >%s min; '
                        'cancelled to unblock Safe Plan queue'
                    ) % mins,
                    'verification_id': op.verification_id,
                }, ensure_ascii=False),
            })
            _logger.warning(
                'MCP: stuck_state_cleaner cancelled %s', op.verification_id,
            )
        return len(stuck)

    @api.model
    def cron_execute_confirmed_pending(self):
        """Legacy no-op: este cron secuestraba workers (forever-busy).

        Se auto-apaga por SQL (el ORM no deja write si el job está running).
        El apply de confirmed lo hace ``get_safe_operation_status`` / botón.
        """
        try:
            self.env.cr.execute(
                "UPDATE ir_cron SET active = false "
                "WHERE id IN ("
                "  SELECT res_id FROM ir_model_data "
                "   WHERE module = 'pns_ai_mcp' "
                "     AND name = 'ir_cron_ai_safe_operation_execute_confirmed' "
                "     AND model = 'ir.cron'"
                ")"
            )
        except Exception:
            _logger.warning(
                'MCP: could not SQL-disable execute-confirmed cron',
                exc_info=True,
            )
        return 0

    def _extract_fetch_url_domain(self):
        """Extract the hostname from the first fetch_url step in operation_data."""
        self.ensure_one()
        data = self.get_operation_data() or {}
        steps = data.get('plan_steps', [])
        for step in steps:
            if step.get('op') == 'fetch_url' and step.get('url'):
                from urllib.parse import urlparse
                return (urlparse(step['url']).hostname or '').lower()
        return ''

    def _maybe_auto_whitelist(self):
        """Add fetch_url domain to the global whitelist when policy allows.

        open policy: any user with External URL — auto-add on access.
        whitelist_only: only AI Administrators add domains (on confirm).
        """
        self.ensure_one()
        domain = self._extract_fetch_url_domain()
        if not domain:
            return
        Whitelist = self.env['ai.url.whitelist'].sudo()
        if Whitelist.is_url_access_open():
            Whitelist.ensure_domain_whitelisted(
                domain,
                notes='Auto-added on fetch_url (open URL policy) — %s' % self.verification_id,
            )
            return
        if not self.env.user.has_group('pns_ai_mcp.group_ai_admin'):
            return
        Whitelist.ensure_domain_whitelisted(
            domain,
            notes='Added by AI Administrator on confirm of %s' % self.verification_id,
        )

    def action_add_to_whitelist(self):
        """Button on the form: manually add this fetch_url's domain to the whitelist."""
        self.ensure_one()
        if not self.env.user.has_group('pns_ai_mcp.group_ai_admin'):
            raise UserError(_("Only AI Administrators can add domains to the URL whitelist."))
        domain = self._extract_fetch_url_domain()
        if not domain:
            raise UserError(_("Cannot extract domain from this operation."))
        Whitelist = self.env['ai.url.whitelist'].sudo()
        exact = Whitelist.with_context(active_test=False).search(
            [('domain', '=ilike', domain)], limit=1)
        if exact and exact.active:
            raise UserError(_("Domain '%s' is already in the whitelist.") % domain)
        if exact and not exact.active:
            exact.write({
                'active': True,
                'notes': ((exact.notes or '').strip() + '\nReactivated from operation %s'
                          % self.verification_id).strip(),
            })
            from ..utils.mcp_ui import client_notification
            return client_notification(
                _("Whitelist"),
                _("Domain '%s' reactivated in the whitelist 🟢") % domain,
                'success',
                sticky=False,
            )
        Whitelist.ensure_domain_whitelisted(
            domain,
            notes='Added from operation %s' % self.verification_id,
        )
        from ..utils.mcp_ui import client_notification
        return client_notification(
            _("Whitelist"),
            _("Domain '%s' added to the whitelist 🟢") % domain,
            'success',
            sticky=False,
        )

    def cancel_by_user(self, cancelled_uid=None):
        """Cancela la operación desde la sesión del navegador del humano."""
        self.ensure_one()
        if self.status != 'pending':
            raise ValidationError(f"La verificación {self.verification_id} ya no está pendiente (estado: {self.status})")
        self.status = 'cancelled'
        self.resolved_at = fields.Datetime.now()
        _logger.info("MCP: Verificación %s cancelada por sesión", self.verification_id)
        return True

    def _claim_execute(self, stale_seconds=45):
        """Claim atómico del execute (single-flight) en cursor propio.

        Importante: NO hace commit del cursor del caller. El claim antiguo
        hacía ``env.cr.commit()`` y eso:
        1) mataba los ``SET LOCAL lock/statement_timeout`` del toast/cron, y
        2) soltaba el FOR UPDATE de ``ir.cron`` a mitad de job → worker
           forever-busy (el síntoma «Another process… already busy»).

        El claim vive en un cursor corto; el plan corre después en el cursor
        del caller (con timeouts reaplicados en ``execute_plan_now``).
        Roba claims huérfanos (> ``stale_seconds``) del mismo registro.
        """
        self.ensure_one()
        from ..utils.compat import invalidate_recordset_fields

        if self.executed:
            return 'done'
        if self.status != 'confirmed':
            return 'skip'

        stale = max(30, int(stale_seconds))
        claim = json.dumps({'_executing': True})
        table = self._table
        op_id = self.id
        registry = self.env.registry

        with registry.cursor() as cr:
            # Robar claim huérfano de ESTA fila (worker muerto / toast colgado).
            cr.execute(
                "UPDATE %s SET result_info = NULL, "
                "write_date = (now() at time zone 'UTC') "
                "WHERE id = %%s AND status = 'confirmed' "
                "AND COALESCE(executed, false) = false "
                "AND COALESCE(result_info, '') LIKE %%s "
                "AND write_date < (now() at time zone 'UTC') "
                "- (%%s * interval '1 second')" % table,
                (op_id, '%"_executing": true%', stale),
            )
            cr.execute(
                "UPDATE %s SET result_info = %%s, "
                "write_date = (now() at time zone 'UTC') "
                "WHERE id = %%s AND status = 'confirmed' "
                "AND COALESCE(executed, false) = false "
                "AND COALESCE(result_info, '') NOT LIKE %%s "
                "RETURNING id" % table,
                (claim, op_id, '%"_executing": true%'),
            )
            row = cr.fetchone()
            if not row:
                cr.execute(
                    "SELECT executed, status, COALESCE(result_info, '') "
                    "FROM %s WHERE id = %%s" % table,
                    (op_id,),
                )
                meta = cr.fetchone() or (False, '', '')
                cr.rollback()
                if meta[0]:
                    return 'done'
                if meta[1] != 'confirmed':
                    return 'skip'
                if '"_executing": true' in (meta[2] or ''):
                    return 'busy'
                return 'skip'
            cr.commit()

        invalidate_recordset_fields(
            self, ['status', 'executed', 'result_info'],
        )
        return 'claimed'

    def _release_execute_claim(self, error=None):
        """Quita el claim ``_executing`` (cursor propio; no commit del caller).

        If *error* is set, the human authorization is revoked (``cancelled``).
        A failed execute must not stay ``confirmed``: later code fixes would
        replay the same Confirm without a new toast.
        """
        self.ensure_one()
        from ..utils.compat import invalidate_recordset_fields

        registry = self.env.registry
        with registry.cursor() as cr:
            if error:
                payload = json.dumps(
                    {'error': error, '_executing': False},
                    ensure_ascii=False,
                )
                cr.execute(
                    "UPDATE %s SET result_info = %%s, status = 'cancelled', "
                    "resolved_at = (now() at time zone 'UTC'), "
                    "write_date = (now() at time zone 'UTC') "
                    "WHERE id = %%s AND COALESCE(executed, false) = false "
                    "AND status = 'confirmed'" % self._table,
                    (payload, self.id),
                )
            else:
                cr.execute(
                    "UPDATE %s SET result_info = %%s, "
                    "write_date = (now() at time zone 'UTC') "
                    "WHERE id = %%s AND COALESCE(executed, false) = false "
                    "AND COALESCE(result_info, '') LIKE %%s" % self._table,
                    (None, self.id, '%"_executing": true%'),
                )
            cr.commit()
        invalidate_recordset_fields(
            self, ['status', 'executed', 'result_info', 'resolved_at'],
        )

    @api.model
    def _clear_stale_execute_claims(self, older_than_seconds=45):
        """Claims ``_executing`` huérfanos (worker muerto) → reintento posible."""
        secs = max(30, int(older_than_seconds))
        self.env.cr.execute(
            "UPDATE %s SET result_info = NULL, "
            "write_date = (now() at time zone 'UTC') "
            "WHERE status = 'confirmed' AND COALESCE(executed, false) = false "
            "AND COALESCE(result_info, '') LIKE %%s "
            "AND write_date < (now() at time zone 'UTC') "
            "- (%s * interval '1 second')" % (self._table, secs),
            ('%"_executing": true%',),
        )
        n = self.env.cr.rowcount
        if n:
            self.env.cr.commit()
            _logger.warning('MCP: cleared %s stale execute claim(s)', n)
        return n

    def execute_plan_now(self):
        """Ejecuta el plan declarativo (caja B) con el env del usuario ACTUAL.

        Single-flight por claim atómico (no FOR UPDATE durante el plan):
        toast/cron/auto-confirm no pueden aplicar el mismo plan a la vez, y
        el HTTP de fetch_url no retiene el lock de la op (evita 6YR2 colgada).

        Atomicidad (crítico — no separar): las mutaciones de negocio
        (``execute_safe_plan``) y la marca ``executed=True`` + ``result_info``
        se comitean JUNTAS, en una única transacción de ESTE cursor
        (``self.env.cr``). O queda todo, o no queda nada:

        - Falla el plan/commit → ni mutaciones ni ``executed``; la
          autorización se **cancela** (nuevo toast si el humano insiste). El
          "toast mentiroso" (éxito reportado sin cambios reales) es imposible.
          Un ``confirmed`` zombie no debe sobrevivir a un fallo: al arreglar
          el código, ``get_safe_operation_status`` / cron reaplicarían el
          mismo Confirmar sin permiso nuevo.
        - Éxito → mutaciones y ``executed=True`` durables a la vez. Tampoco
          existe la ventana inversa (mutaciones comiteadas con ``executed``
          aún False) que permitía a ``_retry_confirmed_not_executed`` relanzar
          el plan entero y duplicar el trabajo tras caducar el claim.

        Para poder escribir la fila de la op en esta misma transacción sin el
        ``SerializationFailure`` (PG 40001) contra el commit del claim (que
        ocurre en su propio cursor DESPUÉS de que este cursor tomara su
        snapshot REPEATABLE READ), se renueva el snapshot con un ``commit()``
        inmediatamente después de obtener el claim. Todos los llamadores
        (``_execute_plan_with_timeouts``, auto-confirm en propose,
        ``get_safe_operation_status``, ``_retry_confirmed_not_executed``)
        llegan aquí con su cursor recién comiteado o sin trabajo pendiente,
        así que ese commit temprano no persiste nada a medias de nadie; sus
        ``cr.commit()`` posteriores quedan como no-ops inofensivos.

        Returns:
            list|dict results | [] si ya executed | None sin plan/skip |
            False si otro ejecutor tiene el claim (busy).
        """
        self.ensure_one()
        from ..utils.compat import invalidate_recordset_fields

        invalidate_recordset_fields(
            self, ['status', 'executed', 'result_info', 'operation_data'],
        )
        self = self.browse(self.id)

        if self.executed:
            if self.result_info:
                try:
                    return json.loads(self.result_info)
                except Exception:
                    return []
            return []

        claim = self._claim_execute()
        if claim == 'done':
            invalidate_recordset_fields(self, ['executed', 'result_info'])
            self = self.browse(self.id)
            if self.result_info:
                try:
                    return json.loads(self.result_info)
                except Exception:
                    return []
            return []
        if claim == 'busy':
            _logger.info(
                'MCP: execute_plan_now %s — busy (claim)', self.verification_id,
            )
            return False
        if claim != 'claimed':
            return None

        from ..controllers.safe_plan import execute_safe_plan
        data = self.get_operation_data() or {}
        steps = data.get('plan_steps')
        if not steps:
            self._release_execute_claim(error='no_plan_steps')
            return None
        session_id = data.get('chatboo_session_id')
        exec_env = self.env
        if session_id:
            exec_env = self.env(context=dict(
                self.env.context or {},
                chatboo_session_id=int(session_id),
            ))
        else:
            from ..utils.session_download import resolve_chatboo_session_id
            resolved = resolve_chatboo_session_id(self.env)
            if resolved:
                exec_env = self.env(context=dict(
                    self.env.context or {},
                    chatboo_session_id=int(resolved),
                ))
        vid = self.verification_id
        dbname = self.env.cr.dbname
        op_id = self.id
        try:
            # Snapshot fresco POSTERIOR al commit del claim: así el UPDATE de
            # executed=True de abajo puede vivir en la MISMA transacción que
            # las mutaciones sin SerializationFailure (ver docstring). Los
            # llamadores llegan con su cursor recién comiteado o sin trabajo
            # pendiente, así que aquí no se persiste nada a medias.
            self.env.cr.commit()
            # SET LOCAL muere con el commit: reaplicar timeouts en la
            # transacción nueva (sin ellos el plan cuelga forever ante un lock).
            try:
                from ..utils.module_update_heal import plan_has_module_update
                if plan_has_module_update(steps):
                    # button_immediate_* reloads the registry; 15s is too tight.
                    self.env.cr.execute("SET LOCAL lock_timeout = '30s'")
                    self.env.cr.execute("SET LOCAL statement_timeout = '120s'")
                else:
                    self.env.cr.execute("SET LOCAL lock_timeout = '5s'")
                    self.env.cr.execute("SET LOCAL statement_timeout = '15s'")
            except Exception:
                pass
            _logger.info('MCP: execute_plan_now %s — start (%s steps)', vid, len(steps))
            exec_env = exec_env(context=dict(
                exec_env.context or {},
                ai_journal_safe_operation_id=self.id,
                ai_journal_correlation_id=self.correlation_id or False,
                ai_journal_user_id=self.user_id.id,
                ai_journal_confirmed_by_uid=(
                    self.confirmed_by_uid.id if self.confirmed_by_uid else exec_env.uid
                ),
                ai_journal_origin=self._resolve_log_origin(),
                ai_journal_note=(data.get('title') or '')[:500],
            ))
            results = execute_safe_plan(exec_env, steps)
            # Mutaciones + executed=True en UNA transacción (todo o nada).
            # Flush explícito antes del UPDATE crudo: cr.commit() no vuelca la
            # caché ORM por sí solo en todas las versiones soportadas.
            flush_all = getattr(self.env, 'flush_all', None)
            if flush_all is not None:
                flush_all()  # Odoo 17+
            else:
                self.env['base'].flush()  # Odoo 14
            payload = json.dumps(results, ensure_ascii=False, default=str)
            self.env.cr.execute(
                "UPDATE %s SET executed = true, result_info = %%s, "
                "write_date = (now() at time zone 'UTC') "
                "WHERE id = %%s" % self._table,
                (payload, self.id),
            )
            _logger.info('MCP: execute_plan_now %s — plan done, committing', vid)
            self.env.cr.commit()
        except Exception as exc:
            _logger.error(
                'MCP: execute_plan_now %s — failed: %s', vid, exc, exc_info=True,
            )
            # Dejar el cursor del caller utilizable (una tx PG abortada
            # rechaza todo SQL posterior hasta rollback).
            try:
                self.env.cr.rollback()
            except Exception:
                pass
            healed = None
            try:
                healed = self._heal_module_update_after_registry_reset(
                    steps, exc, dbname=dbname, op_id=op_id, exec_env=exec_env,
                )
            except Exception:
                _logger.exception(
                    'MCP: module.update heal failed for %s', vid,
                )
                healed = None
            if healed is not None:
                _logger.info(
                    'MCP: execute_plan_now %s — module.update succeeded; '
                    'registry reload looked like a crash',
                    vid,
                )
                return healed
            try:
                self._release_execute_claim(error=str(exc)[:500])
            except Exception:
                pass
            try:
                self.env['ai.change.journal'].sudo().record_failed_plan(
                    steps, str(exc), env=exec_env,
                )
            except Exception:
                _logger.exception(
                    'MCP: could not journal failed plan %s', vid,
                )
            raise

        invalidate_recordset_fields(self, ['executed', 'result_info'])
        self._log_safe_plan_execution(results)
        _logger.info('MCP: execute_plan_now %s — finished', vid)
        return results

    def _heal_module_update_after_registry_reset(
            self, steps, exc, dbname=None, op_id=None, exec_env=None):
        """If ``button_immediate_*`` already committed, don't journal a fake failure.

        Module install/upgrade/uninstall reloads the Odoo registry. The Safe Plan
        cursor then errors even though the module state already changed. A fresh
        registry cursor reads the live state and, on match, marks executed +
        journals ``applied``.
        """
        from odoo import SUPERUSER_ID, api as odoo_api
        from odoo.modules.registry import Registry
        from ..utils.module_update_heal import (
            module_state_matches,
            module_update_args_from_steps,
        )

        module, operation, module_ids = module_update_args_from_steps(steps)
        if not operation or not dbname or not op_id:
            return None
        if not module and not module_ids:
            return None
        try:
            registry = Registry(dbname)
        except Exception:
            try:
                registry = Registry.new(dbname)
            except Exception:
                _logger.exception(
                    'MCP: no live registry to heal module.update %s', module,
                )
                return None
        ctx = dict((exec_env.context if exec_env is not None else self.env.context) or {})
        results = [{
            'op': 'action',
            'action_code': 'module.update',
            'result': {
                'ok': True,
                'healed': True,
                'module': module,
                'operation': operation,
                'model': 'ir.module.module',
            },
        }]
        payload = json.dumps(results, ensure_ascii=False, default=str)
        with registry.cursor() as cr:
            jenv = odoo_api.Environment(cr, SUPERUSER_ID, ctx)
            if not module and module_ids:
                recs = jenv['ir.module.module'].sudo().browse(module_ids).exists()
                if recs:
                    module = recs[0].name
            if not module:
                return None
            results[0]['result']['module'] = module
            mod = jenv['ir.module.module'].sudo().search(
                [('name', '=', module)], limit=1,
            )
            loaded = module in (getattr(registry, '_init_modules', None) or ())
            if not mod or not module_state_matches(operation, mod.state, loaded):
                return None
            results[0]['result']['ids'] = [mod.id]
            results[0]['result']['state'] = mod.state
            results[0]['result']['change_journal'] = {
                'model': 'ir.module.module',
                'ids': [mod.id],
                'change_kind': 'module',
                'reversible': False,
                'reversible_reason': 'module install/upgrade/uninstall',
            }
            payload = json.dumps(results, ensure_ascii=False, default=str)
            already_applied = jenv['ai.change.journal'].sudo().search([
                ('safe_operation_id', '=', op_id),
                ('action_code', '=', 'module.update'),
                ('state', '=', 'applied'),
            ], limit=1)
            if not already_applied:
                step = next(
                    (s for s in (steps or [])
                     if isinstance(s, dict)
                     and s.get('action_code') == 'module.update'),
                    {'op': 'action', 'action_code': 'module.update'},
                )
                jenv['ai.change.journal'].sudo().record_executed_step(
                    jenv, step, 'action', results[0], None, 1,
                )
            cr.execute(
                "UPDATE %s SET executed = true, result_info = %%s, "
                "write_date = (now() at time zone 'UTC') "
                "WHERE id = %%s" % self._table,
                (payload, op_id),
            )
            rec = jenv[self._name].browse(op_id)
            if rec.exists():
                try:
                    rec._log_safe_plan_execution(results)
                except Exception:
                    _logger.exception(
                        'MCP: heal log skipped for module.update %s', module,
                    )
            cr.commit()
        return results

    def _resolve_log_origin(self):
        """Origin channel for execute_safe_plan audit rows."""
        self.ensure_one()
        data = self.get_operation_data() or {}
        origin = data.get('log_origin')
        if origin in ('chatboo', 'mcp_client', 'internal'):
            return origin
        tn = (self.tool_name or '')
        if tn.startswith('skill:'):
            return 'chatboo'
        if tn == 'propose_safe_operations':
            return 'mcp_client'
        return 'internal'

    def _log_safe_plan_execution(self, results):
        """Audit trail: supervised writes must appear as write rows in ai.log."""
        if 'ai.log' not in self.env:
            return
        data = self.get_operation_data() or {}
        steps = data.get('plan_steps') or []
        parts = []
        for item in results or []:
            if not isinstance(item, dict):
                continue
            op = item.get('op') or '?'
            target = item.get('model') or item.get('url') or item.get('server') or ''
            parts.append('%s:%s' % (op, target))
        summary = _('Executed %(vid)s — %(steps)s') % {
            'vid': self.verification_id,
            'steps': ', '.join(parts[:8]) or _('no steps'),
        }
        # Thread under the turn that proposed the plan. Confirm runs in a new
        # HTTP request (toast), so advance step via max(ai.log.step_seq)+1 when
        # the live MCP counter is not available — never leave step_seq=0 blank.
        corr = self.correlation_id or None
        step = None
        if corr:
            try:
                from odoo.http import request as http_request
                from ..utils.mcp_correlation import next_step_seq
                if http_request and getattr(http_request, 'mcp_corr_id', None) == corr:
                    step = next_step_seq(http_request, corr)
            except Exception:
                step = None
            if not step:
                Log = self.env['ai.log'].sudo()
                last = Log.search_read(
                    [('correlation_id', '=', corr)],
                    ['step_seq'],
                    order='step_seq desc',
                    limit=1,
                )
                step = (last[0]['step_seq'] or 0) + 1 if last else 1
        try:
            self.env['ai.log'].sudo().create_log_entry(
                user_id=self.user_id.id,
                operation_type='write',
                tool_name='execute_safe_plan',
                prompt_data={
                    'verification_id': self.verification_id,
                    'title': data.get('title'),
                    'plan_steps': steps,
                },
                result_data=results,
                result_summary=summary[:500],
                request_type='tool',
                source_channel=self._resolve_log_origin(),
                correlation_id=corr,
                step_seq=step or False,
            )
        except Exception as exc:
            _logger.warning(
                'MCP: could not log safe plan execution %s: %s',
                self.verification_id, exc,
            )

    def _notify_reload(self, message, ntype='success'):
        """Acción de notificación que además recarga la vista.

        Sin esto, un botón que devuelve un ``display_notification`` deja la
        lista/formulario de Autorizaciones con el estado viejo hasta pulsar
        F5. Encadenamos un ``reload`` en ``params.next`` para refrescar el
        estado del registro tras confirmar/cancelar.
        """
        from ..utils.mcp_ui import client_notification
        action = client_notification(
            _('Authorizations'), message, ntype, sticky=False,
        )
        action.setdefault('params', {})['next'] = {
            'type': 'ir.actions.client', 'tag': 'reload',
        }
        return action

    def action_confirm_and_execute(self):
        """Botón Autorizaciones: un clic = confirmar + escribir + executed.

        UX simple (sin botón Aplicar). Anti-cuelgue: timeouts PG en el apply
        (5s/15s) y se suelta claim huérfano antes. Si el destino está locked,
        la op queda confirmed y el error es explícito — no spinner eterno.
        """
        self.ensure_one()
        from ..utils.compat import invalidate_recordset_fields

        if not self._can_resolve():
            raise UserError(_("Only the user who requested the operation can confirm it."))

        invalidate_recordset_fields(
            self, ['status', 'executed', 'result_info'],
        )
        self = self.browse(self.id)

        if self.executed:
            return self._notify_reload(
                _('Operation %s was already executed.') % self.verification_id,
                'info',
            )

        if (
            self.expires_at
            and fields.Datetime.now() > self.expires_at
            and self.status in ('pending', 'confirmed')
        ):
            self.sudo().with_context(skip_expiry_refresh=True).write({
                'status': 'expired',
                'resolved_at': fields.Datetime.now(),
            })
            raise UserError(_(
                'Operation %s has expired and can no longer be confirmed.'
            ) % self.verification_id)

        # Ya confirmed (p. ej. clic previo a medias): solo aplicar.
        if self.status != 'confirmed':
            out = self.resolve_confirm(confirmed_uid=self.env.user.id)
            if out.get('busy'):
                raise UserError(_(
                    'Another session is confirming this operation. '
                    'Wait a moment and refresh the list.'
                ))
            if not out.get('success'):
                err = out.get('error') or out.get('status') or 'error'
                if err in ('expired', 'not_pending'):
                    raise UserError(_(
                        'Operation %s can no longer be confirmed (status: %s).'
                    ) % (self.verification_id, out.get('status') or err))
                raise UserError(_("Error confirming the operation: %s") % err)
            if out.get('idempotent') or out.get('status') == 'executed':
                return self._notify_reload(
                    _('Operation %s was already executed.') % self.verification_id,
                    'info',
                )
            # resolve_confirm() dejó 'confirmed' commiteado en un cursor
            # SEPARADO. Los cursores de Odoo son REPEATABLE READ, así que esta
            # transacción aún ve el snapshot antiguo ('pending') y el
            # resolve_execute() de abajo abortaría con 'not_confirmed'
            # (obligando a un segundo clic). Commiteamos aquí para arrancar un
            # snapshot fresco que ya vea el estado recién confirmado.
            self.env.cr.commit()
            invalidate_recordset_fields(
                self, ['status', 'executed', 'result_info'],
            )

        # Soltar claim huérfano de un intento colgado.
        self.env.cr.execute(
            "UPDATE %s SET result_info = NULL, "
            "write_date = (now() at time zone 'UTC') "
            "WHERE id = %%s AND status = 'confirmed' "
            "AND COALESCE(executed, false) = false "
            "AND COALESCE(result_info, '') LIKE %%s" % self._table,
            (self.id, '%"_executing": true%'),
        )
        out2 = self.resolve_execute(confirmed_uid=self.env.user.id)
        if out2.get('status') == 'executed':
            return self._notify_reload(
                _('Operation %s executed.') % self.verification_id,
                'success',
            )
        raise UserError(_(
            'Operation %s was confirmed but could not be applied: %s. '
            'Retry Confirm.'
        ) % (
            self.verification_id,
            out2.get('error') or out2.get('status') or 'busy',
        ))

    def action_execute_plan(self):
        """Compat: redirige al mismo flujo de un clic (confirm+execute)."""
        return self.action_confirm_and_execute()

    def action_cancel(self):
        """Botón Autorizaciones: cancelar (idempotente si ya estaba cancelada)."""
        self.ensure_one()
        if not self._can_resolve():
            raise UserError(_("Only the user who requested the operation can cancel it."))
        if self.status == 'cancelled':
            return self._notify_reload(
                _('Operation %s was already cancelled.') % self.verification_id,
                'info',
            )
        if self.executed or self.status == 'confirmed':
            raise UserError(_(
                'Operation %s is already confirmed/executed and cannot be cancelled.'
            ) % self.verification_id)
        if self.status != 'pending':
            raise UserError(_(
                'Operation %s can no longer be cancelled (status: %s).'
            ) % (self.verification_id, self.status))
        self.cancel_by_user(cancelled_uid=self.env.user.id)
        return self._notify_reload(
            _('Operation %s cancelled.') % self.verification_id,
            'success',
        )
    
    def send_execution_summary(self, total_processed, successful_count, failed_count=0, is_cancelled=False, record_ids=None):
        """
        Envía un resumen final al chatter después de ejecutar o cancelar la operación.
        
        :param total_processed: Número total de registros procesados
        :param successful_count: Número de registros procesados exitosamente
        :param failed_count: Número de registros que fallaron (opcional)
        :param is_cancelled: Si es True, indica que la operación fue cancelada
        :param record_ids: Lista de IDs de registros creados/modificados para mostrar display names
        """
        if not self.user_id or not self.user_id.partner_id:
            return
        
        try:
            from odoo.tools import formatLang
            from odoo import fields
            
            # 1. Usuario que lanza el proceso
            user_display = self.user_id.name if self.user_id else 'Desconocido'
            
            # 2. Fecha y hora de la ejecución (momento en que se completa la operación)
            execution_datetime = ""
            try:
                user_lang = self.user_id.lang or 'es_ES'
                now_dt = fields.Datetime.now()
                execution_datetime = formatLang(
                    self.env.with_context(
                        lang=user_lang,
                        tz=self.user_id.tz or 'Europe/Madrid'
                    ),
                    now_dt,
                    dt=True
                )
            except Exception:
                execution_datetime = fields.Datetime.to_string(fields.Datetime.now())
            
            # 3. Nombre friendly del modelo
            model_display = self.model_name or 'Desconocido'
            if self.model_name:
                try:
                    # Caso especial: ir.filters debe mostrar "Filtro personalizado" o "Filtros"
                    if self.model_name == 'ir.filters':
                        model_display = 'Filtro personalizado'
                    else:
                        model_class = self.env.get(self.model_name)
                        if model_class and hasattr(model_class, '_description'):
                            model_display = model_class._description
                        else:
                            model_record = self.env['ir.model'].sudo().with_context(
                                lang=self.user_id.lang or 'es_ES'
                            ).search([('model', '=', self.model_name)], limit=1)
                            if model_record and model_record.name:
                                model_display = model_record.name
                except Exception:
                    pass
            
            # 4. Operación ("Alta", "Modificación", "Borrado" o "Duplicación")
            # Verificar si hay concepto descriptivo en operation_data
            operation_concept = None
            try:
                operation_data = self.get_operation_data()
                if operation_data and isinstance(operation_data, dict):
                    dangerous_op = operation_data.get('dangerous_op_info', {})
                    if isinstance(dangerous_op, dict):
                        operation_concept = dangerous_op.get('operation_concept')
            except Exception:
                pass
            
            # Mapeo de tipos de operación (simplificado)
            operation_map = {
                'create': 'Alta',
                'write': 'Modificación',
                'unlink': 'Borrado',
                'duplicacion': 'Duplicación'
            }
            
            # Si hay concepto de duplicación, mostrar "Duplicación" en lugar de "Alta"
            if operation_concept == 'duplicacion':
                operation_display = 'Duplicación'
            else:
                operation_display = operation_map.get(self.operation_type, dict(self._fields['operation_type'].selection).get(self.operation_type, ''))
            
            # Determinar si es documento o registro maestro
            def _is_document_model(model_name):
                """Determina si un modelo es un documento (presupuesto, factura, etc.) o un registro maestro"""
                if not model_name:
                    return False
                # Modelos de documentos (tienen numeración, estados, etc.)
                document_models = {
                    'sale.order',  # Presupuestos/Pedidos de venta
                    'account.move',  # Facturas/Asientos contables
                    'purchase.order',  # Pedidos de compra
                    'stock.picking',  # Albaranes
                    'account.payment',  # Pagos
                    'purchase.requisition',  # Licitaciones
                    'sale.subscription',  # Suscripciones
                    'account.bank.statement',  # Extractos bancarios
                    'hr.expense',  # Gastos
                    'mrp.production',  # Órdenes de fabricación
                    'mrp.workorder',  # Órdenes de trabajo
                    'project.task',  # Tareas
                    'project.project',  # Proyectos
                }
                # Verificar si el modelo o alguno de sus padres es un documento
                if model_name in document_models:
                    return True
                # Verificar modelos que empiezan con ciertos prefijos
                document_prefixes = ('account.', 'sale.', 'purchase.', 'stock.', 'mrp.', 'project.')
                if any(model_name.startswith(prefix) for prefix in document_prefixes):
                    return True
                return False
            
            # Determinar tipo de entidad (documento o registro)
            entity_type = 'documento' if _is_document_model(self.model_name) else 'registro'
            
            # 5. Número de registros afectados con display names
            records_info = ""
            if record_ids and isinstance(record_ids, list) and len(record_ids) > 0:
                try:
                    # Limitar a 3 para el mensaje
                    display_names = []
                    model_records = self.env[self.model_name].sudo().browse(record_ids[:3])
                    for rec in model_records:
                        if rec.exists():
                            if hasattr(rec, 'display_name'):
                                display_names.append(rec.display_name)
                            else:
                                display_names.append(f"{self.model_name} (ID: {rec.id})")
                    
                    # Construir información según las reglas (igual que en el PIN):
                    # - Si es 1 registro: mostrar display name
                    # - Si son varios: [display_name1, ...] hasta 3, sin "..." si son exactamente 3
                    if total_processed == 1:
                        if display_names:
                            records_info = f"<br/><b>Registro procesado:</b> {display_names[0]}<br/>"
                        else:
                            records_info = f"<br/><b>Registros procesados:</b> {total_processed} registro<br/>"
                    elif total_processed > 1:
                        if display_names:
                            if len(display_names) == total_processed and total_processed <= 3:
                                # Todos los registros (hasta 3), mostrar todos sin "..."
                                records_list = ", ".join(display_names)
                                records_info = f"<br/><b>Registros procesados ({total_processed}):</b> [{records_list}]<br/>"
                            elif len(display_names) < total_processed:
                                # Más registros de los que tenemos display names
                                records_list = ", ".join(display_names)
                                records_info = f"<br/><b>Registros procesados ({total_processed}):</b> [{records_list}, ...]<br/>"
                            else:
                                # Tenemos más display names de los necesarios
                                records_list = ", ".join(display_names[:3])
                                if total_processed > 3:
                                    records_info = f"<br/><b>Registros procesados ({total_processed}):</b> [{records_list}, ...]<br/>"
                                else:
                                    records_info = f"<br/><b>Registros procesados ({total_processed}):</b> [{records_list}]<br/>"
                        else:
                            # No tenemos display names, solo mostrar número
                            records_info = f"<br/><b>Registros procesados:</b> {total_processed} registro(s)<br/>"
                except Exception as e:
                    _logger.warning(f"MCP: Error obteniendo display names para resumen: {e}")
                    records_info = f"<br/><b>Registros procesados:</b> {total_processed} registro(s)<br/>"
            else:
                # Si no hay record_ids, mostrar solo el número
                if total_processed == 1:
                    records_info = f"<br/><b>Registros procesados:</b> {total_processed} registro<br/>"
                else:
                    records_info = f"<br/><b>Registros procesados:</b> {total_processed} registro(s)<br/>"
            
            # Construir mensaje de resumen (con la misma información que el PIN)
            if is_cancelled:
                # Mensaje de cancelación
                summary_body = f"""
❌ <strong>Operación cancelada</strong><br/>
<br/>
<b>Usuario:</b> {user_display}<br/>
<b>Fecha y hora:</b> {execution_datetime}<br/>
<b>Modelo:</b> {model_display}<br/>
<b>Operación:</b> {operation_display} de {entity_type}{records_info}
<b>ID de verificación:</b> {self.verification_id}<br/>
"""
            elif total_processed > 1:
                # Operación masiva completada
                if failed_count > 0:
                    summary_body = f"""
✅ <strong>{SERVIDOR_MCP_COMPLETADO}</strong><br/>
<br/>
<b>Usuario:</b> {user_display}<br/>
<b>Fecha y hora:</b> {execution_datetime}<br/>
<b>Modelo:</b> {model_display}<br/>
<b>Operación:</b> {operation_display} de {entity_type}{records_info}
<b>Total procesados:</b> {total_processed} registro(s)<br/>
<b>Exitosos:</b> {successful_count} registro(s)<br/>
<b>Fallidos:</b> {failed_count} registro(s)<br/>
<b>ID de verificación:</b> {self.verification_id}<br/>
"""
                else:
                    summary_body = f"""
✅ <strong>{SERVIDOR_MCP_COMPLETADO}</strong><br/>
<br/>
<b>Usuario:</b> {user_display}<br/>
<b>Fecha y hora:</b> {execution_datetime}<br/>
<b>Modelo:</b> {model_display}<br/>
<b>Operación:</b> {operation_display} de {entity_type}{records_info}
<b>ID de verificación:</b> {self.verification_id}<br/>
"""
            else:
                # Operación individual completada
                summary_body = f"""
✅ <strong>{SERVIDOR_MCP_COMPLETADO}</strong><br/>
<br/>
<b>Usuario:</b> {user_display}<br/>
<b>Fecha y hora:</b> {execution_datetime}<br/>
<b>Modelo:</b> {model_display}<br/>
<b>Operación:</b> {operation_display} de {entity_type}{records_info}
<b>ID de verificación:</b> {self.verification_id}<br/>
"""
            
            # Obtener partner autor (OdooBot o sistema)
            author_partner = self.env.ref('base.partner_root', raise_if_not_found=False)
            if not author_partner:
                author_partner = self.env.user.partner_id if self.env.user.partner_id else False
            
            # Obtener o crear canal directo con el usuario
            channel_info = self.env['mail.channel'].sudo().channel_get([self.user_id.partner_id.id])
            
            if channel_info and isinstance(channel_info, dict) and 'id' in channel_info:
                channel = self.env['mail.channel'].sudo().browse(channel_info['id'])
                
                # Enviar mensaje al canal
                _logger.info(f"MCP: Enviando mensaje resumen al canal {channel_info['id']} para usuario {self.user_id.id}")
                channel.sudo().message_post(
                    body=summary_body,
                    author_id=author_partner.id if author_partner else False,
                    message_type='comment',
                    subtype_xmlid='mail.mt_comment',
                    partner_ids=[self.user_id.partner_id.id],
                )
                _logger.info(f"MCP: Mensaje resumen enviado correctamente al chatter para verificación {self.verification_id}")
            else:
                _logger.warning(f"MCP: No se pudo obtener canal para enviar resumen (channel_info: {channel_info})")
        except Exception as e:
            _logger.error(f"MCP: Error enviando resumen de ejecución: {e}", exc_info=True)
            raise
    
    def _create_trust_token(self):
        """
        DESHABILITADO: La reutilización del PIN está deshabilitada por seguridad.
        Cada operación requiere confirmación explícita con un PIN único.
        """
        # No crear tokens de confianza - cada operación requiere confirmación explícita
        pass
    


    @api.model
    def auto_cancel_expired_periods(self):
        """Cron/compat: marca como expired los pendientes vencidos (no los deja en pending)."""
        try:
            n = self.cleanup_expired()
            if n:
                _logger.info(
                    "MCP: %s verificación(es) expirada(s) purgadas automáticamente", n
                )
        except Exception as e:
            _logger.warning("MCP: Error purgando verificaciones expiradas: %s", e)
    
    @api.model
    def get_valid_trust_token(self, user_id, operation_type, model_name, tool_name, renew=True):
        """
        DESHABILITADO: La reutilización del PIN está deshabilitada por seguridad.
        Cada operación requiere confirmación explícita con un PIN único.
        
        :param user_id: ID del usuario
        :param operation_type: Tipo de operación ('create', 'write', 'unlink')
        :param model_name: Nombre del modelo
        :param tool_name: Nombre de la herramienta MCP
        :param renew: Si es True, renueva el token actualizando resolved_at (default: True)
        :return: Siempre retorna None (reutilización deshabilitada)
        """
        # Reutilización del PIN deshabilitada por seguridad
        # Cada operación requiere confirmación explícita
        return None
    
    def cancel(self):
        """Cancela una verificación pendiente (sin PIN, para uso interno)"""
        self.ensure_one()
        
        if self.status != 'pending':
            raise ValidationError(f"La verificación {self.verification_id} no puede cancelarse (estado: {self.status})")
        
        self.status = 'cancelled'
        self.resolved_at = fields.Datetime.now()
        
        # Enviar mensaje de cancelación (usando el partner del usuario)
        if self.user_id.partner_id:
            try:
                if hasattr(self.user_id.partner_id, 'message_post'):
                    self.user_id.partner_id.message_post(
                        body=f"❌ Operación cancelada. La verificación {self.verification_id} ha sido cancelada.",
                        subject=f'Operación cancelada: {self.verification_id}',
                        message_type='notification',
                        subtype_xmlid='mail.mt_note',
                    )
                else:
                    self.env['mail.message'].create({
                        'model': 'res.partner',
                        'res_id': self.user_id.partner_id.id,
                        'body': f"❌ Operación cancelada. La verificación {self.verification_id} ha sido cancelada.",
                        'subject': f'Operación cancelada: {self.verification_id}',
                        'message_type': 'notification',
                        'subtype_id': self.env.ref('mail.mt_note').id,
                        'author_id': self.env.user.partner_id.id if self.env.user.partner_id else False,
                        'partner_ids': [(6, 0, [self.user_id.partner_id.id])],
                    })
            except Exception as e:
                _logger.error(f"MCP: Error enviando mensaje de cancelación: {e}")
        
        _logger.info(f"MCP: Verificación {self.verification_id} cancelada")
    
    # Throttle del refresco lazy al abrir lista/form (segundos).
    _EXPIRY_REFRESH_THROTTLE_S = 15
    _expiry_refresh_last_ts = 0.0

    @api.model
    def refresh_expiry_statuses(self, limit=100):
        """Marca ``expired`` pendientes y confirmed-no-ejecutados vencidos.

        Sin cron nuevo: se llama al abrir lista/form (últimas N) o desde
        Herramientas (todas). ``limit=None`` = sin tope.
        """
        if self.env.context.get('skip_expiry_refresh'):
            return 0
        import time
        now_ts = time.time()
        # Throttle solo en el camino lazy (lista/form); Herramientas fuerza.
        if limit is not None:
            last = type(self)._expiry_refresh_last_ts
            if now_ts - last < self._EXPIRY_REFRESH_THROTTLE_S:
                return 0
        now = fields.Datetime.now()
        cr = self.env.cr
        sql = (
            'SELECT id FROM %s '
            "WHERE status IN ('pending', 'confirmed') "
            "AND COALESCE(executed, false) = false "
            "AND expires_at < %%s "
            'ORDER BY create_date DESC NULLS LAST, id DESC '
        ) % self._table
        params = [now]
        if limit is not None:
            sql += 'LIMIT %s '
            params.append(int(limit))
        sql += 'FOR UPDATE SKIP LOCKED'
        cr.execute(sql, tuple(params))
        ids = [row[0] for row in cr.fetchall()]
        if not ids:
            if limit is not None:
                type(self)._expiry_refresh_last_ts = now_ts
            return 0
        self.sudo().with_context(skip_expiry_refresh=True).browse(ids).write({
            'status': 'expired',
            'resolved_at': now,
        })
        if limit is not None:
            type(self)._expiry_refresh_last_ts = now_ts
        _logger.info(
            'MCP: %s verificación(es) marcadas expired (refresh, limit=%s)',
            len(ids), limit,
        )
        return len(ids)

    @api.model
    def action_refresh_expiry_statuses(self):
        """Herramientas: actualiza todos los estados de caducidad y recarga."""
        n = self.refresh_expiry_statuses(limit=None)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Authorizations'),
                'message': _(
                    '%s operation(s) marked as expired. Refresh the list.'
                ) % n,
                'type': 'success' if n else 'info',
                'sticky': False,
                'next': {'type': 'ir.actions.client', 'tag': 'reload'},
            },
        }

    @api.model
    def search_read(self, *args, **kwargs):
        self.refresh_expiry_statuses(limit=100)
        return super().search_read(*args, **kwargs)

    @api.model
    def web_search_read(self, *args, **kwargs):
        # Odoo 17+; en O14 la lista usa search_read.
        self.refresh_expiry_statuses(limit=100)
        parent = getattr(super(), 'web_search_read', None)
        if parent is None:
            return self.search_read(*args, **kwargs)
        return parent(*args, **kwargs)

    def read(self, fields=None, load='_classic_read'):
        if self and not self.env.context.get('skip_expiry_refresh'):
            self.refresh_expiry_statuses(limit=100)
        return super().read(fields=fields, load=load)

    @api.model
    def cleanup_expired(self):
        """Compat/cron existente: mismo refresco sin tope (no añade cron nuevo)."""
        return self.refresh_expiry_statuses(limit=None)

    def get_operation_data(self):
        """Obtiene los datos de la operación deserializados"""
        self.ensure_one()
        if self.operation_data:
            try:
                return json.loads(self.operation_data)
            except (json.JSONDecodeError, TypeError):
                return None
        return None

    def chatboo_card_payload(self):
        """SSE-shaped dict for the Chatboo card (same row the Security menu shows)."""
        self.ensure_one()
        data = self.get_operation_data() or {}
        changes = {}
        if self.changes_info:
            try:
                parsed = json.loads(self.changes_info)
                if isinstance(parsed, dict):
                    changes = parsed
            except (json.JSONDecodeError, TypeError):
                pass
        plan = data.get('plan') or changes.get('plan') or []
        if isinstance(plan, str):
            plan = [plan] if plan.strip() else []
        danger = (
            data.get('danger_level')
            or changes.get('danger_level')
            or self.danger_level
            or 'medium'
        )
        return {
            'verification_id': self.verification_id,
            'title': data.get('title') or '',
            'plan': plan,
            'danger_level': danger,
        }

    @api.model
    def chatboo_pending_card_payloads(self):
        """Live pending cards for the current user. Read-only; does not create rows."""
        self.refresh_expiry_statuses(limit=100)
        now = fields.Datetime.now()
        ops = self.search([
            ('user_id', '=', self.env.uid),
            ('status', '=', 'pending'),
            ('executed', '=', False),
            ('expires_at', '>', now),
        ], order='id desc')
        return [op.chatboo_card_payload() for op in ops]

    # ── Export ────────────────────────────────────────────────────────

    _SAFE_OPS_EXPORT_ONLY = (
        'verification_id', 'operation_type', 'danger_level',
        'model_name', 'records_count', 'status',
        'create_date', 'resolved_at', 'expires_at',
        'executed', 'tool_name',
    )

    @api.model
    def action_export_operations(self, *args, **kwargs):
        """Export all AI supervised operations to a downloadable JSON file.

        Intended for audit trails and compliance.  This is export-only;
        there is no import counterpart (operations are runtime state).

        Each entry includes the user name (denormalized), the audit
        subset in ``_SAFE_OPS_EXPORT_ONLY``, and ``changes_info`` parsed
        as JSON when possible.
        """
        ensure_ai_admin(self.env)
        ops = self.with_context(active_test=False).search([])
        if not ops:
            return mcp_ui.open_json_export_empty_wizard(
                self.env,
                dialog_title=_('Export'),
                message=_('There are no operations to export.'),
            )
        export_data = []
        for rec in ops:
            extra = {'user': rec.user_id.name or ''}
            if rec.changes_info:
                try:
                    extra['changes_info'] = json.loads(rec.changes_info)
                except (json.JSONDecodeError, TypeError):
                    extra['changes_info'] = rec.changes_info
            export_data.append(export_record_dict(
                rec, only_fields=self._SAFE_OPS_EXPORT_ONLY, extra=extra,
            ))
        filename = mcp_ui.build_export_filename(self.env, 'safe_operations', 'json')
        attachment = mcp_ui.write_json_attachment(
            self.env, filename, export_data,
        )
        return mcp_ui.open_json_export_wizard(
            self.env,
            dialog_title=_('Export result'),
            summary_text=_('%s operation(s) exported.') % len(export_data),
            count=len(export_data),
            attachment=attachment,
        )
