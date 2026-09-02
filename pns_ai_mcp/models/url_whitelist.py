# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
"""PNS AI MCP - URL Whitelist. PATANEGRA Soft (https://patanegra.com).

Part of Patanegra Soft Suite (`pns_suite`), distributed via Patanegra Soft Hub.
Egress control of the Patanegra Application Agent Protocol (PAAP): a TYPED
instance-level whitelist with temporal validity governing every domain the AI
may reach. The ``kind`` field says WHICH egress channel the entry authorizes:
  - web:     fetch_url (safe GET/QUERY requests).
  - mcp:     external MCP servers (ai.api.server, api_type='mcp').
  - openapi: external OpenAPI servers (ai.api.server, api_type='openapi').
Matching requires the kind to coincide: whitelisting a domain for plain web
fetches does NOT authorize it as an API server, and vice versa.

Access policy (Settings -> URL access policy):
  - whitelist_only: only listed domains; anything else is blocked unless an AI
    Administrator confirms adding the domain and executes.
  - open: any domain is allowed and added to the list on access.
The user permission (group_ai_external_url) is independent: without it fetch_url
cannot even be proposed. This whitelist is the instance-level layer.
Licensed under the Apache License 2.0 - see LICENSE.
"""

import logging
from odoo import api, fields, models, _

from ..utils import mcp_ui
from ..utils.import_export_guard import ensure_ai_admin
from ..utils.portable_io import export_record_dict

_logger = logging.getLogger(__name__)


class URLWhitelist(models.Model):
    """Global URL whitelist for Safe Plan fetch_url operations.

    Temporal scope:
        - valid_from: when the domain becomes active (empty = immediately)
        - valid_until: when the domain expires (empty = NEVER, permanent)
    """
    _name = 'ai.url.whitelist'
    _description = 'Safe Plan URL Whitelist'
    _order = 'domain'
    _rec_name = 'domain'

    domain = fields.Char(
        string='Domain',
        required=True,
        index=True,
        help=(
            'Allowed domain (e.g. api.exchangerate.host). '
            'Subdomains are also matched: if you add exchangerate.host, '
            'api.exchangerate.host is also allowed.'
        ),
    )
    kind = fields.Selection(
        [('web', 'Web (fetch_url)'), ('mcp', 'MCP server'),
         ('openapi', 'OpenAPI server')],
        string='Kind',
        required=True,
        default='web',
        index=True,
        help=(
            'Egress channel this entry authorizes. web: plain fetch_url '
            'queries. mcp / openapi: domains of registered external API '
            'servers (added automatically when a server is activated). '
            'Matching requires the kind to coincide.'
        ),
    )
    active = fields.Boolean(
        string='Active',
        default=True,
        help='Uncheck to temporarily disable this domain without deleting it.',
    )
    valid_from = fields.Datetime(
        string='Valid from',
        help='When this domain starts being trusted. Empty = immediately.',
    )
    valid_until = fields.Datetime(
        string='Valid until',
        help=(
            'When this domain stops being trusted. '
            'Empty = PERMANENT (no expiration).'
        ),
    )
    notes = fields.Text(
        string='Notes',
        help='Optional description of why this domain is trusted.',
    )
    added_by = fields.Many2one(
        'res.users',
        string='Added by',
        default=lambda self: self.env.uid,
        readonly=True,
    )

    _sql_constraints = [
        ('domain_kind_unique', 'UNIQUE(domain, kind)',
         'This domain is already in the whitelist for that kind.'),
    ]

    @api.model
    def _match_whitelist_entry(self, hostname, kind='web'):
        """Return the whitelist row for *hostname* + *kind* (exact or subdomain),
        any active state."""
        if not hostname:
            return self.browse()
        hostname = hostname.lower().strip()
        for rec in self.sudo().with_context(active_test=False).search(
                [('kind', '=', kind)]):
            allowed = rec.domain.lower().strip()
            if hostname == allowed or hostname.endswith('.' + allowed):
                return rec
        return self.browse()

    @api.model
    def is_domain_whitelisted(self, hostname, kind='web'):
        """Check if a hostname matches an active, temporally valid entry of *kind*.

        Matches exact domain or subdomain (e.g. api.example.com matches example.com).
        Respects valid_from / valid_until:
            - valid_from empty → active immediately
            - valid_until empty → permanent (never expires)

        Returns True if whitelisted and within time window, False otherwise.
        """
        if not hostname:
            return False
        hostname = hostname.lower().strip()
        now = fields.Datetime.now()
        entries = self.sudo().search(
            [('active', '=', True), ('kind', '=', kind)])
        for rec in entries:
            allowed = rec.domain.lower().strip()
            if hostname != allowed and not hostname.endswith('.' + allowed):
                continue
            # Temporal check
            if rec.valid_from and rec.valid_from > now:
                continue  # not yet active
            if rec.valid_until and rec.valid_until < now:
                continue  # expired
            return True
        return False

    @api.model
    def url_access_policy(self):
        """Configured URL access policy: 'whitelist_only' or 'open'."""
        return self.env['ir.config_parameter'].sudo().get_param(
            'pns_ai_mcp.url_access_policy', 'whitelist_only'
        )

    @api.model
    def is_url_access_open(self):
        """True when settings allow all URLs without confirmation."""
        return self.url_access_policy() == 'open'

    @api.model
    def is_fetch_url_trusted(self, hostname):
        """True if fetch_url may auto-execute without admin confirmation toast.

        Whitelisted domains (kind='web') always qualify. Under open policy any
        hostname qualifies (domain is added on access). Under whitelist_only,
        domains outside the list require an AI Administrator confirmation first.
        """
        if self.is_domain_whitelisted(hostname, kind='web'):
            return True
        return self.is_url_access_open()

    @api.model
    def _fetch_url_access_status(self, hostname, user=None):
        """Return how a hostname is treated for fetch_url.

        allowed              — whitelisted, active and within valid window
        needs_reactivation   — row exists but active=False; admin may confirm to reactivate
        open_add             — open policy: access + auto-add to whitelist
        admin_add            — whitelist_only: admin may confirm add + access
        denied               — whitelist_only: blocked for non-admins
        """
        user = user or self.env.user
        hostname = (hostname or '').lower().strip()
        if not hostname:
            return 'denied'
        if self.is_domain_whitelisted(hostname, kind='web'):
            return 'allowed'
        entry = self._match_whitelist_entry(hostname, kind='web')
        if entry and not entry.active:
            if user.has_group('pns_ai_mcp.group_ai_admin'):
                return 'needs_reactivation'
            return 'denied'
        if self.is_url_access_open():
            return 'open_add'
        if user.has_group('pns_ai_mcp.group_ai_admin'):
            return 'admin_add'
        return 'denied'

    @api.model
    def check_fetch_url_steps(self, steps, user=None):
        """Validate fetch_url steps against instance URL policy.

        Returns:
            tuple: (ok, error_message)
        """
        from urllib.parse import urlparse
        user = user or self.env.user
        for step in steps or []:
            if step.get('op') != 'fetch_url':
                continue
            url = step.get('url') or ''
            hostname = (urlparse(url).hostname or '').lower()
            if not hostname:
                return False, _("fetch_url step requires a valid URL with a hostname.")
            status = self._fetch_url_access_status(hostname, user=user)
            if status == 'denied':
                entry = self._match_whitelist_entry(hostname, kind='web')
                if entry and not entry.active:
                    return False, _(
                        'Domain "%(domain)s" is in the URL whitelist but disabled. '
                        'Ask an AI Administrator to reactivate it.'
                    ) % {'domain': hostname}
                return False, _(
                    'Domain "%(domain)s" is not in the URL whitelist. '
                    'Ask an AI Administrator to add it.'
                ) % {'domain': hostname}
        return True, None

    @api.model
    def ensure_domain_whitelisted(self, hostname, notes='', kind='web'):
        """Add hostname to the whitelist for *kind*, or reactivate a disabled row."""
        hostname = (hostname or '').lower().strip()
        if not hostname or self.is_domain_whitelisted(hostname, kind=kind):
            return False
        entry = self._match_whitelist_entry(hostname, kind=kind)
        if entry:
            if entry.active:
                return False
            vals = {'active': True}
            if notes:
                extra = notes.strip()
                if extra:
                    vals['notes'] = (
                        ((entry.notes or '').strip() + '\n' + extra).strip()
                        if entry.notes else extra
                    )
            entry.sudo().write(vals)
            _logger.info(
                "MCP: Reactivated domain '%s' (%s) in URL whitelist",
                hostname, kind)
            return True
        self.sudo().create({
            'domain': hostname,
            'kind': kind,
            'notes': notes or '',
            'added_by': self.env.uid,
        })
        _logger.info(
            "MCP: Domain '%s' (%s) added to URL whitelist", hostname, kind)
        return True

    @api.model
    def get_active_domains(self, kind='web'):
        """Active, temporally valid whitelisted domain strings of *kind*."""
        now = fields.Datetime.now()
        return [
            r.domain.lower().strip()
            for r in self.sudo().search(
                [('active', '=', True), ('kind', '=', kind)])
            if (not r.valid_from or r.valid_from <= now)
            and (not r.valid_until or r.valid_until >= now)
        ]

    # ── Export / Import ───────────────────────────────────────────

    @api.model
    def action_export_whitelist(self, *args, **kwargs):
        """Export all whitelist entries to a downloadable JSON file."""
        ensure_ai_admin(self.env)
        entries = self.with_context(active_test=False).search([])
        if not entries:
            return mcp_ui.open_json_export_empty_wizard(
                self.env,
                dialog_title=_('Export'),
                message=_('There are no whitelist entries to export.'),
            )
        export_data = [export_record_dict(rec) for rec in entries]
        filename = mcp_ui.build_export_filename(self.env, 'url_whitelist', 'json')
        attachment = mcp_ui.write_json_attachment(
            self.env, filename, export_data,
        )
        return mcp_ui.open_json_export_wizard(
            self.env,
            dialog_title=_('Export result'),
            summary_text=_('%s whitelist entry(ies) exported.') % len(export_data),
            count=len(export_data),
            attachment=attachment,
        )

    @api.model
    def action_import_whitelist(self, *args, **kwargs):
        """Open the import wizard for URL whitelist entries.

        The wizard accepts a ``.json`` or ``.zip`` file (containing .json).
        Import is resilient: unknown fields are ignored, missing fields
        use defaults, individual entry errors are collected and shown
        in the result report without aborting the batch.

        The key field for matching is ``domain`` (case-insensitive).

        Returns:
            dict: Odoo action opening ``pns_ai_mcp.import_whitelist_wizard``
                  as a modal dialog.
        """
        ensure_ai_admin(self.env)
        return {
            'type': 'ir.actions.act_window',
            'name': _('Import URL Whitelist'),
            'res_model': 'pns_ai_mcp.import_whitelist_wizard',
            'view_mode': 'form',
            'views': [[False, 'form']],
            'target': 'new',
        }
