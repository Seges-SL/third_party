# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025-2026 Patanegra Soft <https://patanegra.com>
from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools.safe_eval import safe_eval

from odoo.addons.pns_base.utils.compat import ODOO_VERSION

from ..utils import mcp_ui
from ..utils import config_backup
from ..utils.display_currency import (
    CURRENCY_SELECTION,
    ICP_DISPLAY_CURRENCY,
    get_display_currency,
    normalize_currency,
)
from ..utils.skill_code_prefix import (
    DEFAULT_SKILL_CODE_PREFIX,
    DEFAULT_SKILL_COMMAND_PREFIX,
    ICP_SKILL_CODE_PREFIX,
    ICP_SKILL_COMMAND_PREFIX,
    normalize_skill_code_prefix,
    normalize_skill_command_prefix,
    prefix_stomps_slash,
)
from ..utils.domain_index import INJECT_ICP_KEY, icp_flag_enabled


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    display_currency = fields.Selection(
        CURRENCY_SELECTION,
        string='Display currency',
        default='USD',
        config_parameter=ICP_DISPLAY_CURRENCY,
        help=(
            'Currency for Chatboo cost chips across all providers. '
            'Vendors report USD; Chatboo converts at the rate loaded when '
            'the chat opens. Stored usage stays in USD.'
        ),
    )

    domain_index_inject = fields.Boolean(
        string='Turn-scoped domain packs',
        default=True,
        config_parameter=INJECT_ICP_KEY,
        help=(
            'When enabled, indexed domain knowledge leaves the always-on agent '
            'cache and is injected only on matching turns (smaller base context). '
            'When disabled, all linked domains stay in the cache (monolith). '
            'Saving a change rebuilds inference agent caches.'
        ),
    )

    url_access_policy = fields.Selection(
        [('whitelist_only', 'Whitelist only'), ('open', 'Open (auto-add URLs)')],
        string='URL access policy',
        default='whitelist_only',
        config_parameter='pns_ai_mcp.url_access_policy',
        help=(
            'Whitelist only: only listed domains are accessible. Domains outside '
            'the list are blocked for regular users; AI Administrators can confirm '
            'adding them to the whitelist and executing the fetch.\n'
            'Open: any URL is allowed for users with External URL permission; '
            'new domains are added to the whitelist automatically on access.'
        ),
    )

    skill_code_prefix = fields.Char(
        string='Skill code prefix',
        default=DEFAULT_SKILL_CODE_PREFIX,
        config_parameter=ICP_SKILL_CODE_PREFIX,
        help=(
            'Snake-case prefix for catalog codes of skills created on this '
            'instance (/create-skill). Empty = no prefix. A tenant pack may '
            'seed a default. No {company} or {user} placeholders. '
            'Does not rewrite existing slashes by itself.'
        ),
    )
    skill_command_prefix = fields.Char(
        string='Skill command prefix',
        default=DEFAULT_SKILL_COMMAND_PREFIX,
        config_parameter=ICP_SKILL_COMMAND_PREFIX,
        help=(
            'Kebab-case prefix for the chat slash of skills created on this '
            'instance (/create-skill). Empty = no prefix. A tenant pack may '
            'seed a default. Must not equal an existing slash or a builtin.'
        ),
    )

    def _primary_list_view_mode(self):
        return 'list' if ODOO_VERSION >= 17 else 'tree'

    def _eval_action_field(self, value, default):
        if value in (None, False, ''):
            return default
        if isinstance(value, str):
            return safe_eval(value, {'uid': self.env.uid})
        return value

    def _prepare_act_window_action(self, xmlid, **overrides):
        """Build an act_window dict safe for O14 web (always includes type)."""
        raw = self.env.ref(xmlid).sudo().read()[0]
        action = {
            'type': 'ir.actions.act_window',
            'name': overrides.pop('name', None) or raw.get('name'),
            'res_model': overrides.pop('res_model', None) or raw.get('res_model'),
            'view_mode': overrides.pop('view_mode', None) or raw.get('view_mode') or 'tree,form',
            'target': overrides.pop('target', None) or raw.get('target') or 'current',
            'domain': self._eval_action_field(overrides.pop('domain', raw.get('domain')), []),
            'context': self._eval_action_field(overrides.pop('context', raw.get('context')), {}),
        }
        if 'views' in overrides:
            action['views'] = overrides.pop('views')
        elif raw.get('views'):
            action['views'] = raw['views']
        if 'res_id' in overrides:
            action['res_id'] = overrides.pop('res_id')
        action.update(overrides)
        return action

    def _action_open_module_agents(self, agent_type):
        """Open module-origin agents of the given type (settings-safe; no M2M fields)."""
        xmlid = (
            'pns_ai_mcp.action_module_endpoint_agents'
            if agent_type == 'endpoint'
            else 'pns_ai_mcp.action_module_inference_agents'
        )
        list_mode = self._primary_list_view_mode()
        tree_view = self.env.ref('pns_ai_mcp.view_ai_agent_tree')
        return self._prepare_act_window_action(
            xmlid,
            view_mode='%s,form' % list_mode,
            views=[(tree_view.id, list_mode), (False, 'form')],
        )

    def action_open_module_endpoint_agents(self):
        return self._action_open_module_agents('endpoint')

    def action_open_module_inference_agents(self):
        return self._action_open_module_agents('inference')

    def action_open_module_agent(self):
        """Open one module agent form (agent_code in context)."""
        code = (self.env.context.get('agent_code') or '').strip()
        if not code:
            raise UserError(_("Agent code is required."))
        agent = self.env['ai.agent'].sudo().search([
            ('code', '=', code),
            ('origin', '=', 'module'),
            ('active', '=', True),
        ], limit=1)
        if not agent:
            raise UserError(_("Module agent '%s' is not installed or inactive.") % code)
        return agent.action_open_form()

    def action_open_url_whitelist(self):
        """Open URL whitelist from settings (type=object; type=action breaks on O14)."""
        return self._prepare_act_window_action('pns_ai_mcp.action_url_whitelist')

    def action_open_fx_sources(self):
        """Open currency rate feeds (deterministic; not the Safe Plan whitelist)."""
        return self._prepare_act_window_action('pns_ai_mcp.action_ai_fx_source')

    def action_export_ai_config(self):
        """Export the whole AI configuration to a downloadable JSON file."""
        self.ensure_one()
        from ..utils.import_export_guard import ensure_ai_admin
        ensure_ai_admin(self.env)
        data = config_backup.export_config(self.env, include_secrets=True)
        filename = mcp_ui.build_export_filename(self.env, 'ai_config_backup', 'json')
        attachment = mcp_ui.write_json_attachment(self.env, filename, data)
        counts = [
            len(data.get('providers') or []),
            len(data.get('agents') or []),
            len(data.get('contexts') or []),
            len(data.get('skills') or []),
            len(data.get('mcp_servers') or []),
            len(data.get('url_whitelists') or []),
            len(data.get('mcp_users') or []),
        ]
        return mcp_ui.open_json_export_wizard(
            self.env,
            dialog_title=_('AI configuration export'),
            summary_text=_(
                'Configuration exported (secrets included). '
                'Providers: %s, Agents: %s, Contexts: %s, Skills: %s, '
                'Servers: %s, Whitelist: %s, User keys: %s.'
            ) % tuple(counts),
            count=sum(counts),
            attachment=attachment,
        )

    def action_import_ai_config(self):
        """Open the wizard to restore the AI configuration from a JSON backup."""
        self.ensure_one()
        from ..utils.import_export_guard import ensure_ai_admin
        ensure_ai_admin(self.env)
        return {
            'type': 'ir.actions.act_window',
            'name': _('Import AI configuration'),
            'res_model': 'pns_ai_mcp.config_backup_wizard',
            'view_mode': 'form',
            'views': [[False, 'form']],
            'target': 'new',
        }

    def action_export_artifact_bundle(self):
        self.ensure_one()
        from ..utils.import_export_guard import ensure_ai_admin
        ensure_ai_admin(self.env)
        return self._prepare_act_window_action(
            'pns_ai_mcp.action_artifact_bundle_export_wizard',
            target='new',
        )

    def action_import_artifact_bundle(self):
        self.ensure_one()
        from ..utils.import_export_guard import ensure_ai_admin
        ensure_ai_admin(self.env)
        return self._prepare_act_window_action(
            'pns_ai_mcp.action_artifact_bundle_import_wizard',
            target='new',
        )

    def get_values(self):
        res = super().get_values()
        ICP = self.env['ir.config_parameter'].sudo()
        res['url_access_policy'] = ICP.get_param(
            'pns_ai_mcp.url_access_policy', 'whitelist_only'
        )
        res['domain_index_inject'] = icp_flag_enabled(
            ICP.get_param(INJECT_ICP_KEY, 'True'), default=True,
        )
        res['display_currency'] = get_display_currency(self.env)
        res['skill_code_prefix'] = normalize_skill_code_prefix(
            ICP.get_param(ICP_SKILL_CODE_PREFIX, DEFAULT_SKILL_CODE_PREFIX),
        )
        res['skill_command_prefix'] = normalize_skill_command_prefix(
            ICP.get_param(
                ICP_SKILL_COMMAND_PREFIX, DEFAULT_SKILL_COMMAND_PREFIX,
            ),
        )
        return res

    def set_values(self):
        super().set_values()
        ICP = self.env['ir.config_parameter'].sudo()
        ICP.set_param(
            'pns_ai_mcp.url_access_policy',
            self.url_access_policy or 'whitelist_only',
        )
        prev_inject = icp_flag_enabled(
            ICP.get_param(INJECT_ICP_KEY, 'True'), default=True,
        )
        new_inject = bool(self.domain_index_inject)
        ICP.set_param(
            INJECT_ICP_KEY,
            'True' if new_inject else 'False',
        )
        if prev_inject != new_inject:
            self._rebuild_inference_agent_caches_after_domain_index_toggle()
        ICP.set_param(
            ICP_DISPLAY_CURRENCY,
            normalize_currency(self.display_currency),
        )
        code_pfx = normalize_skill_code_prefix(self.skill_code_prefix)
        cmd_pfx = normalize_skill_command_prefix(self.skill_command_prefix)
        taken = []
        if 'ai.skill' in self.env:
            taken = [
                (s.command or s.code or '').strip()
                for s in self.env['ai.skill'].sudo().search([])
                if (s.command or s.code)
            ]
        if prefix_stomps_slash(code_pfx, cmd_pfx, taken):
            raise UserError(_(
                'A skill prefix cannot equal an existing slash command '
                'or a builtin (/skills, /create-skill, …).'
            ))
        ICP.set_param(ICP_SKILL_CODE_PREFIX, code_pfx)
        ICP.set_param(ICP_SKILL_COMMAND_PREFIX, cmd_pfx)

    def _rebuild_inference_agent_caches_after_domain_index_toggle(self):
        """Always-on vs turn-scoped composition changes with the flag."""
        import logging
        _logger = logging.getLogger(__name__)
        if 'ai.agent' not in self.env:
            return
        agents = self.env['ai.agent'].sudo().search([
            ('agent_type', 'in', ('inference', 'endpoint')),
        ])
        for agent in agents:
            try:
                if hasattr(agent, 'action_rebuild_cache'):
                    agent.action_rebuild_cache()
                else:
                    agent.get_content(force_rebuild=True)
            except Exception:
                _logger.warning(
                    'MCP: cache rebuild after domain_index toggle failed for %s',
                    agent.code, exc_info=True,
                )

    @api.model
    def _seed_install_icp(self):
        """First-install Settings defaults. Never overwrite an existing key.

        Called from ``instance_defaults_data.xml`` via ``post_init_hook``
        only (not manifest ``data:``). A later ``-u`` does not run this.
        Present keys (including an explicit empty prefix) stay as they are.
        """
        import logging
        _logger = logging.getLogger(__name__)
        pairs = (
            (ICP_SKILL_CODE_PREFIX, DEFAULT_SKILL_CODE_PREFIX),
            (ICP_SKILL_COMMAND_PREFIX, DEFAULT_SKILL_COMMAND_PREFIX),
            (INJECT_ICP_KEY, 'True'),
        )
        ICP = self.env['ir.config_parameter'].sudo()
        for key, value in pairs:
            if ICP.search([('key', '=', key)], limit=1):
                continue
            ICP.set_param(key, value)
            _logger.info('MCP: seeded install ICP %s=%s', key, value)
