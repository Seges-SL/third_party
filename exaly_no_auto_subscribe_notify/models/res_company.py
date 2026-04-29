from odoo import api, fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    exaly_no_notify_models = fields.Many2many(comodel_name='ir.model', string='Models to exclude from notification')

