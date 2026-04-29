from odoo import api, fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    exaly_no_notify_models = fields.Many2many(
        comodel_name='ir.model',
        string='Models to exclude from notification',
        related='company_id.exaly_no_notify_models',
        readonly=False,
    )
