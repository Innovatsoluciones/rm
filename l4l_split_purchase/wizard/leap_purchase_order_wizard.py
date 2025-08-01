# -*- coding: utf-8 -*-
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2023 Leap4Logic Solutions PVT LTD
#    Email : sales@leap4logic.com
#################################################

from odoo import fields, models
from odoo.exceptions import ValidationError


class LeapPurchaseOrderWizard(models.TransientModel):
    _name = 'leap.purchase.order.wizard'
    _description = 'Split Purchase Order Wizard'

    split_order_line = fields.One2many('leap.purchase.order.line', 'split_order_id', string='Split Lines')

    def split_purchase(self):
        purchase_order = self.split_order_line.line_id.order_id
        name = self.env['ir.sequence'].next_by_code('x.purchase.order')
        new_order_id = purchase_order.copy(default={"name": str(name)})
        new_order_id.purchase_origin_id = purchase_order and purchase_order.id or False
        new_order_id.order_line.unlink()

        for line in self.split_order_line:
            original_qty = line.line_id.product_qty
            if line.quantity > original_qty:
                raise ValidationError(f"The Quantity of {line.product_id.name} cannot exceed {original_qty}")
            lines = line.line_id.copy()
            lines.write({'order_id': new_order_id.id, 'product_qty': line.quantity})
            if line.line_id.product_qty == line.quantity:
                line.line_id.unlink()
            elif line.quantity < line.line_id.product_qty:
                line.line_id.product_qty -= line.quantity

        for sale_order_line in new_order_id.order_line:
            split_order_line = self.env["x.purchase.order.line.received"]. \
                create({'order_id': purchase_order.id, 'x_order_line_id': sale_order_line.id, 'x_pc_order_id': new_order_id.id,
                        'qty_received': sale_order_line.qty_received, 'product_qty': sale_order_line.product_uom_qty, })

        action = {
            'name': 'Purchase Order',
            'type': 'ir.actions.act_window',
            'res_model': 'purchase.order',
            'res_id': new_order_id.id,
            'view_type': 'form',
            'view_mode': 'form',
            'target': 'current',
        }
        return action


class LeapPurchaseOrderLine(models.TransientModel):
    _name = 'leap.purchase.order.line'
    _description = 'Wizard For Purchase Order'

    split_order_id = fields.Many2one('leap.purchase.order.wizard', string='Split ID', ondelete='cascade')
    line_id = fields.Many2one(comodel_name='purchase.order.line')
    product_id = fields.Many2one('product.product', string='Product')
    quantity = fields.Float(string='Quantity')
    uom = fields.Many2one('uom.uom', string='Unit of Measure')

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
