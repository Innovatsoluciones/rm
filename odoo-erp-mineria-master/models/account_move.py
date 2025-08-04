from odoo import models, api

class AccountMove(models.Model):
    _inherit = 'account.move'

    @api.model
    def _get_sequence_prefix(self):
        return 'INV/'

    @api.model
    def _get_next_invoice_number(self):
        sequence = self.env['ir.sequence'].next_by_code('account.move')
        return f'INV/{sequence[-5:]}'
