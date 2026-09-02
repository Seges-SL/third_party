# -*- coding: utf-8 -*-
# SPDX-License-Identifier: Apache-2.0
from odoo import fields, models, _
from odoo.exceptions import UserError

from ..utils import artifact_bundle, mcp_ui


class AIArtifactBundleExportWizard(models.TransientModel):
    _name = 'pns_ai_mcp.artifact_bundle.export.wizard'
    _description = 'Export selected AI artifacts bundle'

    skill_ids = fields.Many2many('ai.skill', string='Skills')
    context_ids = fields.Many2many('ai.context', string='Contexts')
    provider_ids = fields.Many2many('ai.provider', string='Providers')
    agent_ids = fields.Many2many('ai.agent', string='Agents')
    server_ids = fields.Many2many('ai.api.server', string='External servers')
    user_ids = fields.Many2many('ai.mcp.user', string='MCP users')
    whitelist_ids = fields.Many2many('ai.url.whitelist', string='URL whitelist')
    include_secrets = fields.Boolean(
        string='Include secrets',
        default=False,
        help='When off, provider API keys and server auth tokens/env vars are blank.',
    )
    include_settings = fields.Boolean(
        string='Include AI settings',
        default=False,
        help='Export global AI configuration parameters (ir.config_parameter).',
    )
    export_tag = fields.Char(
        string='File tag',
        help='Optional label (e.g. piloto, occ) inserted into the download file name '
             'between the Odoo instance and the artifact type. '
             'Pattern: timestamp_instance_tag_artifact.zip',
    )
    export_artifact_name = fields.Char(
        string='Artifact name',
        help='Optional override for the artifact segment in the file name '
             '(default: ai_artifact_bundle). Timestamp and instance are always kept.',
    )

    def action_export(self):
        self.ensure_one()
        if not any([
            self.skill_ids,
            self.context_ids,
            self.provider_ids,
            self.agent_ids,
            self.server_ids,
            self.user_ids,
            self.whitelist_ids,
            self.include_settings,
        ]):
            raise UserError(_(
                'Select at least one artifact to export.'
            ))
        result = artifact_bundle.export_bundle(
            self.env,
            skills=self.skill_ids,
            contexts=self.context_ids,
            providers=self.provider_ids,
            agents=self.agent_ids,
            servers=self.server_ids,
            users=self.user_ids,
            whitelists=self.whitelist_ids,
            include_secrets=self.include_secrets,
            include_settings=self.include_settings,
            export_tag=self.export_tag,
            export_artifact=self.export_artifact_name,
        )
        attachment = artifact_bundle.bundle_export_attachment(self.env, result)
        counts = result['counts']
        return mcp_ui.open_json_export_wizard(
            self.env,
            dialog_title=_('Artifact bundle export'),
            summary_text=_(
                'Partial bundle exported: %(skills)s skill(s), '
                '%(contexts)s context(s), %(providers)s provider(s), '
                '%(agents)s agent(s), %(servers)s server(s), '
                '%(users)s MCP user(s), %(whitelists)s whitelist entry(ies)'
                '%(settings)s.'
            ) % {
                **counts,
                'settings': (
                    _(', settings included') if counts.get('settings') else ''
                ),
            },
            count=sum(v for k, v in counts.items() if k != 'settings') + counts.get('settings', 0),
            attachment=attachment,
        )
