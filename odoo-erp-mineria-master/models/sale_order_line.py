from odoo import fields, models, api

class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    completed = fields.Float(string="Realizado")
    origin_sale_order_id = fields.Many2one(
        'sale.order', 
        string='Orden de Venta de Origen'
    )