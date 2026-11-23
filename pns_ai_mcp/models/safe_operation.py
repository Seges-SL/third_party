# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""Two-box write: the AI proposes intent as data; a human (or trust policy) authorizes.

Box A is the declaration. Box B is fixed, audited server code the AI can
neither see nor invoke. Governs supervised writes, egress/URLs, and calls
to external MCP servers.
"""

from odoo import models, fields, api, _
from odoo.exceptions import AccessError, UserError, ValidationError
from datetime import datetime, timedelta
import hashlib
import hmac
import json
import logging
import random
import secrets
from ..constants import HIGH_CONFIRM_WAIT_SECONDS, PENDING_OPERATION_TTL_MINUTES
from ..utils import mcp_ui
from ..utils.import_export_guard import ensure_ai_admin
from ..utils.portable_io import export_record_dict

_logger = logging.getLogger(__name__)

# Last lazy expiry refresh per database (time.time()). Not on the model class:
# Odoo 18+ rejects attributes set on a registry class at run time.
_EXPIRY_REFRESH_LAST_TS = {}


def _hash_confirm_token(raw):
    """SHA-256 of the card token. Empty in, empty out."""
    raw = (raw or '').strip()
    if not raw:
        return ''
    return hashlib.sha256(raw.encode('utf-8')).hexdigest()

class SafeOperation(models.Model):
    """AI Supervised Operation — the 'Safe Plan' (Box B).

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

    # Operation identification
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
    turn = fields.Char(
        string='Turn',
        readonly=True,
        index=True,
        help='Turn id of the conversation turn that proposed this plan',
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
    
    # Model and records info
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
    
    # Changes info (serialized JSON)
    changes_info = fields.Text(
        string='Changes Info',
        readonly=True,
        help='Detailed information about the proposed changes (serialized JSON)'
    )
    
    # User who requested the operation
    user_id = fields.Many2one(
        'res.users',
        string='User',
        required=True,
        readonly=True,
        index=True,
        ondelete='cascade'
    )

    # Session-bound confirmation: human user who confirmed from the browser
    confirmed_by_uid = fields.Many2one(
        'res.users',
        string='Confirmed by',
        readonly=True,
        help='User (browser session) who confirmed the operation from the toast'
    )

    # Guard against running the same verification twice
    executed = fields.Boolean(
        string='Executed',
        default=False,
        readonly=True,
        help='True when the confirmed operation has already been executed (prevents double execution)'
    )

    # Result of running the declarative plan (box B), serialized JSON
    result_info = fields.Text(
        string='Execution result',
        readonly=True,
        help='Result of executing the plan after human confirmation (serialized JSON)'
    )

    # Verification status
    status = fields.Selection(
        [
            ('pending', 'Pending'),
            ('confirmed', 'Confirmed'),
            ('executed', 'Executed'),
            ('cancelled', 'Cancelled'),
            ('expired', 'Expired'),
        ],
        string='Status',
        required=True,
        default='pending',
        readonly=True,
        index=True
    )
    
    # Creation date
    create_date = fields.Datetime(
        string='Creation Date',
        required=True,
        readonly=True,
        default=fields.Datetime.now,
        index=True
    )
    
    # Expiration date
    expires_at = fields.Datetime(
        string='Expires at',
        required=True,
        readonly=True,
        compute='_compute_expires_at',
        store=True,
        help='Date and time when this verification expires'
    )
    

    
    # LIVE flag (not stored): has a pending verification already expired?
    # Lets the form show "expired" without waiting for a cron.
    is_expired = fields.Boolean(
        string='Expired',
        compute='_compute_is_expired',
        help='True when a pending verification has passed its expiration time'
    )

    # Confirmation/cancellation date
    resolved_at = fields.Datetime(
        string='Resolved at',
        readonly=True,
        help='Date and time when the verification was confirmed or cancelled'
    )

    # One-use token painted on the chat card. Plaintext never hits the
    # database: RelaxAICode reads as the asking user. Hash only, system-only.
    confirm_token_hash = fields.Char(
        string='Confirm token hash',
        readonly=True,
        copy=False,
        groups='base.group_system',
    )
    confirm_token_at = fields.Datetime(
        string='Confirm token issued at',
        readonly=True,
        copy=False,
        groups='base.group_system',
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
    
    # Extra info (tool_name, arguments, etc.)
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
    
    # Display name
    display_name = fields.Char(
        string='Name',
        compute='_compute_display_name',
        store=False
    )
    
    @api.depends('operation_type', 'model_name', 'records_count', 'create_date')
    def _compute_display_name(self):
        """Compute the display name"""
        for record in self:
            op_type = dict(record._fields['operation_type'].selection).get(record.operation_type, '')
            record.display_name = _('%s - %s (%s records) - %s') % (
                op_type,
                record.model_name,
                record.records_count,
                record.create_date.strftime('%Y-%m-%d %H:%M') if record.create_date else '',
            )
    
    @api.depends('create_date')
    def _compute_expires_at(self):
        """Pending operation expiry: PENDING_OPERATION_TTL_MINUTES after creation."""
        for record in self:
            base = record.create_date or fields.Datetime.now()
            record.expires_at = base + timedelta(minutes=PENDING_OPERATION_TTL_MINUTES)

    @api.depends('expires_at', 'status', 'executed')
    def _compute_is_expired(self):
        """True if past expiry and not executed (pending/confirmed/expired).

        Not stored: recomputed on every read. The stored status
        ``expired`` is updated when the list/form opens or from Tools
        (no new cron).
        """
        now = fields.Datetime.now()
        for record in self:
            past = bool(record.expires_at and record.expires_at < now)
            record.is_expired = bool(
                past
                and not record.executed
                and record.status in ('pending', 'confirmed', 'expired')
            )

    # UI buttons: only actions that still make sense (e.g. whitelist already
    # covered → no «add» button).
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
            # Confirmed without execute is only actionable inside the window.
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
        """Who can confirm/cancel: the user who requested it OR an MCP
        administrator (group_ai_admin), who can resolve other people's ones."""
        self.ensure_one()
        return (
            self.env.user.id == self.user_id.id
            or self.env.user.has_group('pns_ai_mcp.group_ai_admin')
        )
    
    # Requester IP (for audit / security statistics)
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
        """Get (or create if missing) the per-verb typed sequence.

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
                'company_id': False,
            })
        else:
            vals = {}
            if seq.prefix != prefix:
                vals['prefix'] = prefix
            if seq.padding != 8:
                vals['padding'] = 8
            # next_by_code only sees the active company's sequences.
            if seq.company_id:
                vals['company_id'] = False
            if vals:
                seq.write(vals)
        return seq

    def _generate_verification_id(self, verb=None):
        """Generate a per-verb typed ID: CREA0001, WRIT0042, FURL0003, etc.

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
                f"MCP: Error generating verification_id for verb '{verb}': "
                f"sequence '{seq_code}' returned no value."
            )
        return vid
    
    @api.model
    def _resolve_turn(self, turn=None):
        """Turn id of the MCP turn: argument > context > http request."""
        if turn:
            return turn
        ctx_turn = (self.env.context or {}).get('mcp_turn')
        if ctx_turn:
            return ctx_turn
        try:
            from odoo.http import request as http_request
            return getattr(http_request, 'mcp_turn', None) or None
        except Exception:
            return None

    @api.model
    def create_verification(self, operation_type, model_name, records_count,
                            changes_info, user_id, tool_name=None,
                            operation_data=None, request_ip=None,
                            turn=None):
        """Create a new supervised operation (Safe Plan).

        :param operation_type: Primary verb ('create', 'write', 'unlink', 'fetch_url')
        :param model_name: Name of the affected model
        :param records_count: Number of records / steps
        :param changes_info: Changes info (dict → JSON)
        :param user_id: ID of the user who requested the operation
        :param tool_name: Name of the MCP tool (optional)
        :param operation_data: Full operation data (dict → JSON)
        :param request_ip: Client IP (optional, for audit)
        :param turn: Turn id of the MCP conversation turn (e.g. VWVN)
        :return: Recordset of the created verification
        """
        # Expire overdue pending rows (SKIP LOCKED). Do not block propose if
        # rows are locked by a half-done execute.
        try:
            self.cleanup_expired()
        except Exception as cleanup_err:
            _logger.warning(
                'MCP: cleanup_expired in create_verification ignored: %s',
                cleanup_err,
            )

        # Confirmation is per session (toast + endpoint auth='user'), NOT by PIN:
        # the AI can read the DB (relaxaicode), so no stored secret is safe.
        changes_info_json = json.dumps(changes_info, default=str) if isinstance(changes_info, dict) else (changes_info or '')
        operation_data_json = json.dumps(operation_data, default=str) if isinstance(operation_data, dict) else (operation_data or '')

        now = fields.Datetime.now()
        expires_at = now + timedelta(minutes=PENDING_OPERATION_TTL_MINUTES)

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
        turn_corr = self._resolve_turn(turn)

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
            'turn': turn_corr or None,
        })
        verification._notify_safe_plan_hosts()
        return verification


    # RPC write() does not honour readonly=True. Every column is written by
    # the system (plan, expiry, danger, state), only inside sudo() after the
    # caller has passed _can_resolve().
    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.su:
            raise AccessError(_(
                'Only the system can open a supervised operation.'
            ))
        return super().create(vals_list)

    def write(self, vals):
        if not self.env.su and vals:
            raise AccessError(_(
                'Only the system can change the state of a supervised operation.'
            ))
        return super().write(vals)

    def _mint_confirm_token(self):
        """New plaintext token for the card. Stores only the hash.

        Rotates on every paint so a restored card still has a token. The
        browser that just received this payload is the one that can confirm.
        """
        self.ensure_one()
        raw = secrets.token_urlsafe(32)
        self.sudo().write({
            'confirm_token_hash': _hash_confirm_token(raw),
            'confirm_token_at': fields.Datetime.now(),
        })
        return raw

    def _confirm_token_ok(self, raw):
        """True when ``raw`` matches the hash painted on the card."""
        self.ensure_one()
        expected = (self.sudo().confirm_token_hash or '').strip()
        got = _hash_confirm_token(raw)
        if not expected or not got:
            return False
        return hmac.compare_digest(expected, got)

    def _confirm_wait_elapsed(self):
        """High-danger cards wait a few seconds after the last paint."""
        self.ensure_one()
        if self.danger_level != 'high':
            return True
        issued = self.sudo().confirm_token_at
        if not issued:
            return False
        delta = fields.Datetime.now() - issued
        return delta.total_seconds() >= HIGH_CONFIRM_WAIT_SECONDS

    def _consume_confirm_token(self):
        """Drop the hash after the card has confirmed and applied."""
        self.ensure_one()
        self.sudo().write({
            'confirm_token_hash': False,
            'confirm_token_at': False,
        })

    def _confirm_by_user(self, confirmed_uid=None):
        """
        Confirm the operation from the human's browser session.

        Prefer ``_resolve_confirm_and_execute`` (Authorizations).
        The host toast still uses two HTTP calls. This method stays for tests.
        ``confirmed_uid`` is ignored: the confirmer is the session user.
        """
        self.ensure_one()
        if not self._can_resolve():
            raise AccessError(_(
                'Only the owner or an AI Administrator can resolve this operation.'
            ))
        confirmed_uid = self.env.uid
        now = fields.Datetime.now()
        if self.status != 'pending':
            raise ValidationError(_(
                'Verification %s is no longer pending (status: %s)'
            ) % (self.verification_id, self.status))
        if self.expires_at and now > self.expires_at:
            self.sudo().write({'status': 'expired', 'resolved_at': now})
            raise ValidationError(_(
                'Verification %s has expired'
            ) % self.verification_id)
        self.sudo().write({
            'status': 'confirmed',
            'confirmed_by_uid': confirmed_uid,
            'resolved_at': now,
        })
        _logger.info(
            "MCP: Verification %s confirmed by session (uid=%s)",
            self.verification_id, confirmed_uid,
        )

        # Auto-whitelist: if the config flag is ON and this is a fetch_url,
        # add the domain to the whitelist so future requests are 🟢.
        if self.operation_type == 'fetch_url':
            self._maybe_auto_whitelist()

        return True

    def _lock_row_nowait(self):
        """FOR UPDATE NOWAIT: toast and Authorizations do not block each other."""
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

    def _resolve_confirm(self, confirmed_uid=None):
        """Phase A — ONLY confirm (short TX, NOWAIT). Never runs the plan.

        Robust contract: the toast's Confirm HTTP call only calls this.
        That way a lock on the target / zombie worker cannot hang Odoo on
        confirm. The apply is ``resolve_execute`` in another request.
        """
        self.ensure_one()
        if not self._can_resolve():
            raise AccessError(_(
                'Only the owner or an AI Administrator can resolve this operation.'
            ))
        from odoo import api
        from ..controllers.safe_plan import (
            attach_verification_chat_hints,
            build_verification_followup_message,
        )
        from ..utils.compat import invalidate_recordset_fields

        # The uid that comes in over RPC does not authorize another person.
        confirmed_uid = self.env.uid
        data = self.get_operation_data() or {}
        title = data.get('title') or _('Supervised operation')
        steps = data.get('plan_steps') or []
        vid = self.verification_id
        op_id = self.id
        registry = self.env.registry
        context = dict(self.env.context)

        with registry.cursor() as cr1:
            # Fail-fast: on contention, busy right away (do not wait).
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

            if op1.executed or op1.status == 'executed':
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
                    op1.sudo().write({'status': 'expired', 'resolved_at': now})
                    op1._notify_safe_plan_hosts(status='expired')
                    cr1.commit()
                    return {
                        'success': False,
                        'error': 'expired',
                        'status': 'expired',
                        'verification_id': vid,
                    }
                op1.sudo().write({
                    'status': 'confirmed',
                    'confirmed_by_uid': confirmed_uid,
                    'resolved_at': now,
                })
                _logger.info(
                    'MCP: Verification %s confirmed (uid=%s) — no execute',
                    vid, confirmed_uid,
                )
                if op1.operation_type == 'fetch_url':
                    op1._maybe_auto_whitelist()
                op1._notify_safe_plan_hosts(status='confirmed')
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
            env=self.env,
        )

    def _resolve_execute(self, confirmed_uid=None):
        """Phase B — apply the plan (another HTTP request, with PG timeouts).

        Idempotent. If another worker holds the claim or the target is locked,
        returns busy/async without hanging the worker past statement_timeout.
        """
        self.ensure_one()
        if not self._can_resolve():
            raise AccessError(_(
                'Only the owner or an AI Administrator can resolve this operation.'
            ))
        from ..controllers.safe_plan import (
            _ack_tr,
            attach_verification_chat_hints,
            build_verification_followup_message,
        )
        from ..utils.compat import invalidate_recordset_fields

        confirmed_uid = self.env.uid
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
        if self.executed or self.status == 'executed':
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
                env=self.env,
            )

        out = self._execute_plan_with_timeouts(
            op_id, confirmed_uid, context, vid, title,
        )
        if out.get('success') and out.get('status') == 'executed':
            self._notify_safe_plan_hosts(status='executed', executed=True)
            return attach_verification_chat_hints(
                out, title, results=out.get('results'), action='confirm',
                steps=steps, env=self.env,
            )
        if out.get('status') == 'error':
            # A duplicate key is not «applying…»: the write finished and
            # did not happen. Only a busy claim is worth the host waiting.
            return attach_verification_chat_hints(
                {
                    'success': False,
                    'status': 'error',
                    'error': out.get('error'),
                    'verification_id': vid,
                    'confirmed': True,
                    'followup_message': out.get('followup_message'),
                },
                title, action='confirm', error=out.get('error'),
                steps=steps, env=self.env,
            )
        # Do not drop the confirmation: the human already authorized.
        soft = _ack_tr(self.env, _(
            '«%s» is confirmed. Applying the changes — this may take a moment.'
        )) % title
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
            env=self.env,
        )

    def _resolve_confirm_and_execute(self, confirmed_uid=None):
        """One row, one flight: confirm and apply.

        Authorizations use this. The host toast still uses two HTTP calls
        (confirm, then execute). We must commit between phases: the Odoo
        cursor is REPEATABLE READ and, otherwise, execute sees pending. After
        execute, another commit: a host reading the sequence of the newly
        created record would see the row missing if it kept the snapshot
        from before.
        """
        from ..utils.compat import invalidate_recordset_fields

        out = self._resolve_confirm(confirmed_uid=confirmed_uid)
        if not out.get('success'):
            return out
        if out.get('status') == 'executed' or out.get('idempotent'):
            return out
        if not out.get('needs_execute', True):
            return out
        self.env.cr.commit()
        invalidate_recordset_fields(
            self, ['status', 'executed', 'result_info'],
        )
        out = self.browse(self.id)._resolve_execute(confirmed_uid=confirmed_uid)
        # Execute ran on another cursor. This one still sees the world from
        # before that write (REPEATABLE READ), so a host that reads the new
        # sequence would find the row missing. Sleep would not help.
        if out.get('success') and out.get('status') == 'executed':
            self.env.cr.commit()
            invalidate_recordset_fields(
                self, ['status', 'executed', 'result_info'],
            )
        return out

    @api.model
    def _execute_plan_with_timeouts(self, op_id, uid, context, vid, title):
        """Execute in a fresh cursor with PG fail-fast timeouts (single flight)."""
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
                    # Another session already holds the execute claim (NOWAIT).
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
                'MCP: Error executing plan %s: %s', vid, exc, exc_info=True,
            )
            err = str(exc)
            low = err.lower()
            if (
                'lock_timeout' in low
                or 'canceling statement' in low
                or 'statement timeout' in low
                or 'querycanceled' in low
            ):
                err = 'timeout_or_lock: ' + _(
                    'another process is locking the target record (usually '
                    'a zombie Odoo worker). Restart the Odoo container; the '
                    'operation is already confirmed. Detail: %s'
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
    def _cleanup_stuck_state(self, older_than_minutes=10):
        """Safe Plan state cleaner (the one that was missing).

        ``cleanup_expired`` only touches overdue ``pending``. The real hole is
        ``confirmed`` + ``executed=False`` (half-done auto-confirm/toast, 6YR2):
        it leaves a zombie queue and the next propose/orchestration gets stuck.

        1. Releases orphan ``_executing`` claims.
        2. Retries execute (one flight, with timeouts).
        3. Whatever is still confirmed without execute and older than
           ``older_than_minutes`` → ``cancelled`` with a diagnosis.

        Cheap early exit: if there is no stuck queue, no cursors or retries.
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
                'MCP: _cleanup_stuck_state claims=%s executed=%s cancelled=%s',
                stats['claims_cleared'], stats['executed'], stats['cancelled'],
            )
        return stats

    @api.model
    def _retry_confirmed_not_executed(self, limit=20):
        """One execute attempt per pending confirmed op."""
        from odoo import api

        pending = self.search([
            ('status', '=', 'confirmed'),
            ('executed', '=', False),
        ], order='id', limit=limit)
        if not pending:
            return 0

        done = 0
        registry = self.env.registry
        for op_meta in pending:
            uid = op_meta.user_id.id or op_meta.confirmed_by_uid.id
            if not uid:
                continue
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
        """Cancel confirmed-without-execute rows that are too old (zombie state)."""
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
            # Open policy lets the fetch run. Confirming does not grow the list.
            return
        if not self.env.user.has_group('pns_ai_mcp.group_ai_admin'):
            return
        Whitelist._ensure_domain_whitelisted(
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
        Whitelist._ensure_domain_whitelisted(
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
        """Cancel the operation from the human's browser session."""
        self.ensure_one()
        if not self._can_resolve():
            raise AccessError(_(
                'Only the owner or an AI Administrator can resolve this operation.'
            ))
        if self.status != 'pending':
            raise ValidationError(_(
                'Verification %s is no longer pending (status: %s)'
            ) % (self.verification_id, self.status))
        self.sudo().write({
            'status': 'cancelled',
            'resolved_at': fields.Datetime.now(),
        })
        _logger.info("MCP: Verification %s cancelled by session", self.verification_id)
        self._notify_safe_plan_hosts(status='cancelled')
        return True

    def _claim_execute(self, stale_seconds=45):
        """Atomic execute claim (single-flight) on its own cursor.

        Important: it does NOT commit the caller's cursor. The old claim
        did ``env.cr.commit()`` and that:
        1) killed the toast/cron ``SET LOCAL lock/statement_timeout``, and
        2) released the ``ir.cron`` FOR UPDATE halfway through the job → worker
           forever-busy (the «Another process… already busy» symptom).

        The claim lives in a short cursor; the plan then runs on the caller's
        cursor (with timeouts reapplied in ``execute_plan_now``).
        Steals orphan claims (> ``stale_seconds``) of the same record.
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
            # Steal an orphan claim of THIS row (dead worker / hung toast).
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
        """Remove the ``_executing`` claim (own cursor; no caller commit).

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
        """Orphan ``_executing`` claims (dead worker) → retry possible."""
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
        """Run the declarative plan (box B) with the CURRENT user's env.

        Single-flight via atomic claim (no FOR UPDATE during the plan):
        toast/cron/auto-confirm cannot apply the same plan at once, and
        the fetch_url HTTP call does not hold the op lock (avoids a hung 6YR2).

        Atomicity (critical — do not split): the business mutations
        (``execute_safe_plan``) and the ``executed=True`` + ``result_info``
        mark are committed TOGETHER, in a single transaction of THIS cursor
        (``self.env.cr``). Either everything stays, or nothing does:

        - Plan/commit fails → no mutations and no ``executed``; the
          authorization is **cancelled** (new toast if the human insists). The
          "lying toast" (success reported without real changes) is impossible.
          A zombie ``confirmed`` must not survive a failure: once the code is
          fixed, ``safe_plan_status`` / cron would replay the
          same Confirm without new permission.
        - Success → mutations and ``executed=True`` durable at once. The
          reverse window (mutations committed with ``executed`` still
          False) that let ``_retry_confirmed_not_executed`` rerun the
          whole plan and duplicate the work after the claim expired is gone too.

        To write the op row in this same transaction without a
        ``SerializationFailure`` (PG 40001) against the claim commit (which
        happens on its own cursor AFTER this cursor took its
        REPEATABLE READ snapshot), the snapshot is renewed with a ``commit()``
        right after getting the claim. All callers
        (``_execute_plan_with_timeouts``, auto-confirm in propose,
        ``safe_plan_status``, ``_retry_confirmed_not_executed``)
        reach here with a freshly committed cursor or no pending work,
        so that early commit persists nobody's half-done work; their
        later ``cr.commit()`` calls become harmless no-ops.

        Returns:
            list|dict results | [] if already executed | None no plan/skip |
            False if another executor holds the claim (busy).
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
        from ..utils.session_download import resolve_session_ref
        from ..utils.one_company import SCREEN_COMPANIES, one_company_context
        session_ref = data.get('ai_session_ref') or resolve_session_ref(self.env)
        # The plan writes with the rights of whoever asked for it, not of
        # whoever pressed confirm, and in the companies it was asked in.
        exec_env = self.env(user=self.user_id.id) if self.user_id else self.env
        exec_env = exec_env(context=one_company_context(
            exec_env, requested=data.get(SCREEN_COMPANIES) or (),
        ))
        if session_ref:
            exec_env = exec_env(context=dict(
                exec_env.context or {},
                ai_session_ref=int(session_ref),
            ))
        vid = self.verification_id
        dbname = self.env.cr.dbname
        op_id = self.id
        try:
            # Fresh snapshot AFTER the claim commit: that way the
            # executed=True UPDATE below can live in the SAME transaction as
            # the mutations without SerializationFailure (see docstring).
            # Callers arrive with a freshly committed cursor or no pending
            # work, so nothing half-done is persisted here.
            self.env.cr.commit()
            # SET LOCAL dies with the commit: reapply timeouts in the
            # new transaction (without them the plan hangs forever on a lock).
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
                ai_journal_turn=self.turn or False,
                ai_journal_user_id=self.user_id.id,
                ai_journal_confirmed_by_uid=(
                    self.confirmed_by_uid.id if self.confirmed_by_uid else exec_env.uid
                ),
                ai_journal_origin=self._resolve_log_origin(),
                ai_journal_note=(data.get('title') or '')[:500],
            ))
            results = execute_safe_plan(exec_env, steps)
            # Mutations + executed=True in ONE transaction (all or nothing).
            # Explicit flush before the raw UPDATE: cr.commit() alone does not
            # flush the ORM cache in every supported version.
            flush_all = getattr(self.env, 'flush_all', None)
            if flush_all is not None:
                flush_all()  # Odoo 17+
            else:
                self.env['base'].flush()  # Odoo 14
            payload = json.dumps(results, ensure_ascii=False, default=str)
            self.env.cr.execute(
                "UPDATE %s SET executed = true, status = 'executed', "
                "result_info = %%s, "
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
            # Leave the caller's cursor usable (an aborted PG tx
            # rejects all later SQL until rollback).
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
                self.env['ai.change.journal'].sudo()._record_failed_plan(
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
                "UPDATE %s SET executed = true, status = 'executed', "
                "result_info = %%s, "
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
        from ..utils.mcp_logging import known_doors
        if origin in known_doors(self.env):
            return origin
        tn = (self.tool_name or '')
        if tn in ('safe_plan_request', 'propose_safe_operations'):
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
        # HTTP request (toast), so advance step via max(ai.log.turn_step)+1 when
        # the live MCP counter is not available — never leave turn_step=0 blank.
        corr = self.turn or None
        step = None
        if corr:
            try:
                from odoo.http import request as http_request
                from ..utils.mcp_correlation import next_turn_step
                if http_request and getattr(http_request, 'mcp_turn', None) == corr:
                    step = next_turn_step(http_request, corr)
            except Exception:
                step = None
            if not step:
                Log = self.env['ai.log'].sudo()
                last = Log.search_read(
                    [('turn', '=', corr)],
                    ['turn_step'],
                    order='turn_step desc',
                    limit=1,
                )
                step = (last[0]['turn_step'] or 0) + 1 if last else 1
        try:
            self.env['ai.log'].sudo()._create_log_entry(
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
                agent_code=(
                    data.get('mcp_agent_code')
                    or (self.env.context or {}).get('mcp_agent_code')
                ),
                turn=corr,
                turn_step=step or False,
            )
        except Exception as exc:
            _logger.warning(
                'MCP: could not log safe plan execution %s: %s',
                self.verification_id, exc,
            )

    def _notify_safe_plan_hosts(self, status=None, executed=None):
        """Tell Authorizations / toast / walkie that this row changed.

        One row is the fact. Hosts must not keep a private pending copy.

        The send sits in a savepoint. A Postgres error aborts the whole
        transaction; catching it without one leaves the next statement
        as «current transaction is aborted» on the walkie card.
        """
        try:
            with self.env.cr.savepoint():
                self._notify_safe_plan_hosts_now(status=status, executed=executed)
        except Exception:
            _logger.debug(
                'MCP: could not notify Safe Plan hosts',
                exc_info=True,
            )

    def _notify_safe_plan_hosts_now(self, status=None, executed=None):
        admin = self.env.ref(
            'pns_ai_mcp.group_ai_admin', raise_if_not_found=False,
        )
        admin_partners = (
            admin.users.mapped('partner_id') if admin else self.env['res.partner']
        )
        bus = self.env['bus.bus']
        sendone = getattr(bus, '_sendone', None)
        legacy = getattr(bus, 'sendone', None)
        if not sendone and not legacy:
            return
        for rec in self:
            dests = rec.user_id.partner_id | admin_partners
            payload = {
                'type': 'pns_safe_plan',
                'verification_id': rec.verification_id,
                'status': status or rec.status,
                'executed': bool(
                    rec.executed if executed is None else executed
                ),
            }
            for partner in dests:
                if sendone:
                    sendone(partner, 'pns_safe_plan', payload)
                elif legacy:
                    channel = (
                        rec.env.cr.dbname, 'res.partner', partner.id,
                    )
                    legacy(
                        channel,
                        json.dumps(payload, ensure_ascii=False),
                    )

    def _notify_reload(self, message, ntype='success'):
        """Notification action that also reloads the view.

        Without this, a button that returns a ``display_notification`` leaves
        the Authorizations list/form with the old state until F5 is pressed.
        We chain a ``reload`` in ``params.next`` to refresh the record
        state after confirm/cancel.
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
        """Authorizations button: one click = confirm + write + executed.

        Simple UX (no Apply button). Anti-hang: PG timeouts on the apply
        (5s/15s) and any orphan claim is released first. If the target is
        locked, the op stays confirmed and the error is explicit — no endless
        spinner.
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
            self._notify_safe_plan_hosts(status='expired')
            raise UserError(_(
                'Operation %s has expired and can no longer be confirmed.'
            ) % self.verification_id)

        out = self._resolve_confirm_and_execute(confirmed_uid=self.env.user.id)
        if out.get('busy') and not out.get('success'):
            raise UserError(_(
                'Another session is confirming this operation. '
                'Wait a moment and refresh the list.'
            ))
        if out.get('idempotent') or out.get('status') == 'executed':
            return self._notify_reload(
                _('Operation %s executed.') % self.verification_id,
                'success',
            )
        if not out.get('success'):
            err = out.get('error') or out.get('status') or 'error'
            if err in ('expired', 'not_pending'):
                raise UserError(_(
                    'Operation %s can no longer be confirmed (status: %s).'
                ) % (self.verification_id, out.get('status') or err))
            raise UserError(_("Error confirming the operation: %s") % err)
        raise UserError(_(
            'Operation %s was confirmed but could not be applied: %s. '
            'Retry Confirm.'
        ) % (
            self.verification_id,
            out.get('error') or out.get('status') or 'busy',
        ))

    def action_execute_plan(self):
        """Compat: redirects to the same one-click flow (confirm+execute)."""
        return self.action_confirm_and_execute()

    def action_cancel(self):
        """Authorizations: cancel the row, or the rows marked in the list.

        The row button sits past Confirm and a narrow list clips it, so the
        Action menu calls this with everything that was ticked.
        """
        if len(self) > 1:
            return self._cancel_marked()
        self.ensure_one()
        if not self._can_resolve():
            raise UserError(_("Only the user who requested the operation can cancel it."))
        if self.status == 'cancelled':
            return self._notify_reload(
                _('Operation %s was already cancelled.') % self.verification_id,
                'info',
            )
        if self.executed or self.status in ('confirmed', 'executed'):
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

    def _cancel_marked(self):
        """The ticked rows. One that can no longer be cancelled is skipped."""
        ok = self.browse()
        for rec in self:
            if not rec._can_resolve():
                continue
            if rec.executed or rec.status not in ('pending', 'cancelled'):
                continue
            if rec.status == 'pending':
                rec.cancel_by_user(cancelled_uid=self.env.user.id)
            ok |= rec
        if not ok:
            raise UserError(_(
                'Operation %s can no longer be cancelled (status: %s).'
            ) % (self[:1].verification_id, self[:1].status))
        named = ', '.join(str(v) for v in ok.mapped('verification_id'))
        return self._notify_reload(
            _('Operation %s cancelled.') % named,
            'success',
        )

    # Throttle of the lazy refresh when opening list/form (seconds).
    _EXPIRY_REFRESH_THROTTLE_S = 15

    def init(self):
        super().init()
        self._align_executed_status()

    @api.model
    def _align_executed_status(self):
        """Leftover: apply used to leave status=confirmed with executed=true."""
        self.env.cr.execute(
            "UPDATE %s SET status = 'executed' "
            "WHERE COALESCE(executed, false) = true "
            "AND status = 'confirmed'" % self._table,
        )
        return self.env.cr.rowcount

    @api.model
    def refresh_expiry_statuses(self, limit=100):
        """Mark overdue pending and confirmed-not-executed rows ``expired``.

        No new cron: called when opening list/form (last N) or from
        Tools (all). ``limit=None`` = no cap.
        """
        if self.env.context.get('skip_expiry_refresh'):
            return 0
        self._align_executed_status()
        import time
        now_ts = time.time()
        # Throttle only on the lazy path (list/form); Tools forces it.
        if limit is not None:
            last = _EXPIRY_REFRESH_LAST_TS.get(self.env.cr.dbname, 0.0)
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
                _EXPIRY_REFRESH_LAST_TS[self.env.cr.dbname] = now_ts
            return 0
        self.sudo().with_context(skip_expiry_refresh=True).browse(ids).write({
            'status': 'expired',
            'resolved_at': now,
        })
        if limit is not None:
            _EXPIRY_REFRESH_LAST_TS[self.env.cr.dbname] = now_ts
        _logger.info(
            'MCP: %s verification(s) marked expired (refresh, limit=%s)',
            len(ids), limit,
        )
        return len(ids)

    @api.model
    def action_refresh_expiry_statuses(self):
        """Tools: refresh every expiry status and reload."""
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
        # Odoo 17+; on O14 the list uses search_read.
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
        """Compat/existing cron: same refresh with no cap (adds no new cron)."""
        return self.refresh_expiry_statuses(limit=None)

    def get_operation_data(self):
        """Get the deserialized operation data"""
        self.ensure_one()
        if self.operation_data:
            try:
                return json.loads(self.operation_data)
            except (json.JSONDecodeError, TypeError):
                return None
        return None

    def card_payload(self, mint_token=True):
        """SSE-shaped dict for the host's card (same row the Security menu shows)."""
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
        payload = {
            'verification_id': self.verification_id,
            'title': data.get('title') or '',
            'plan': plan,
            'danger_level': danger,
        }
        if mint_token:
            payload['confirm_token'] = self._mint_confirm_token()
        return payload

    @api.model
    def pending_card_payloads(self, mint_token=True, held=None):
        """Live pending cards for the current user. Read-only; does not create rows.

        ``mint_token=False`` is a count/peek: it must not rotate the card token.
        ``held`` are the cards the screen already paints with their token: a new
        token for them would leave the painted one behind.
        """
        held = {str(one) for one in (held or []) if one}
        self.refresh_expiry_statuses(limit=100)
        now = fields.Datetime.now()
        ops = self.search([
            ('user_id', '=', self.env.uid),
            ('status', '=', 'pending'),
            ('executed', '=', False),
            ('expires_at', '>', now),
        ], order='id desc')
        return [
            op.card_payload(
                mint_token=mint_token and op.verification_id not in held,
            )
            for op in ops
        ]

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
