from odoo import models


class MailThread(models.AbstractModel):
    _inherit = 'mail.thread'

    def _message_auto_subscribe_notify(self, partner_ids, template):
        """
        return void if self recordset is in company.exaly_no_notify_models (model not to notify)
        to prevent sending notification to followers of the document
        """
        for record in self:
            company = hasattr(record, 'company_id') and record.company_id or self.env.company
            # SOLUCIÓN: Agregamos .sudo() al recordset de la compañía para poder leer 
            # los registros de ir.model sin generar un Access Error para usuarios estándar.
            if record._name in company.sudo().exaly_no_notify_models.mapped('model'):
                return
        super()._message_auto_subscribe_notify(partner_ids, template)
