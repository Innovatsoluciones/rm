from odoo import models, fields, api
import re

class AccountMove(models.TransientModel):
    _inherit = 'account.payment.register'

    related_products = fields.Many2many('product.product', compute='_compute_related_products')

    @api.depends('line_ids.product_id')
    def _compute_related_products(self):
        for move in self:
            related_product_ids = []
            for line in move.line_ids:
                itemtest = self.env["account.move.line"].search([('id','=',line._origin.id)])
                for account_move in itemtest.mapped('move_id'):
                    products = self.env["account.move.line"].search([('move_id','=',account_move._origin.id)])
                    related_products = products.mapped('product_id')
                    move.related_products = [(6, 0, related_products.ids)]
                    
                    for product_ids in related_products:
                        productitem = self.env["product.product"].search([('id','=',product_ids._origin.id)])
                        related_product_ids.append(productitem.mapped('name'))
            return related_product_ids

