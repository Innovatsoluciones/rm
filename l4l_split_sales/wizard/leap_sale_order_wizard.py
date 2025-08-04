# -*- coding: utf-8 -*-


from odoo import fields, models
from odoo.exceptions import ValidationError


class LeapSaleOrderWizard(models.TransientModel):
    _name = 'leap.sale.order.wizard'
    _description = 'Split Sale Order Wizard'

    split_order_line = fields.One2many('leap.sale.order.line', 'split_order_id', string='Líneas')

    def split_sale(self):
        sale_order = self.split_order_line.line_id.order_id
        name = self.env['ir.sequence'].next_by_code('x.sale.order')
        new_order_id = sale_order.copy(default={"name": str(name), "state": "by_authorize",
                                                "checklist_state_progress": 25.0,})
        new_order_id.sale_origin_id = sale_order and sale_order.id or False
        new_order_id.order_line.unlink()

        for line in self.split_order_line:
            original_qty = line.line_id.product_uom_qty
            if line.quantity > original_qty:
                raise ValidationError(f"La cantidad de {line.product_id.name} no puede exceder {original_qty}")
            lines = line.line_id.copy(default={'order_id': new_order_id.id, 'product_uom_qty': line.quantity})

            if line.line_id.product_uom_qty == line.quantity:
                line.line_id.unlink()
            elif line.quantity < line.line_id.product_uom_qty:
                line.line_id.product_uom_qty -= line.quantity

        for sale_order_line in new_order_id.order_line:
            split_order_line = self.env["x.sale.order.line.delivered"]. \
                create({'order_id': sale_order.id, 'x_order_line_id': sale_order_line.id, 'x_so_order_id': new_order_id.id,
                        'qty_delivered': sale_order_line.qty_delivered, 'product_uom_qty': sale_order_line.product_uom_qty, })

        action = {
            'name': 'Pedido de venta',
            'type': 'ir.actions.act_window',
            'res_model': 'sale.order',
            'res_id': new_order_id.id,
            'view_type': 'form',
            'view_mode': 'form',
            'target': 'current',
        }
        return action


class LeapSaleOrderLine(models.TransientModel):
    _name = 'leap.sale.order.line'
    _description = 'Wizard For Sale Order'

    split_order_id = fields.Many2one('leap.sale.order.wizard', string='Split ID', ondelete='cascade')
    line_id = fields.Many2one(comodel_name='sale.order.line')
    product_id = fields.Many2one('product.product', string='Product')
    quantity = fields.Float(string='Cantidad')
    uom = fields.Many2one('uom.uom', string='Unidad de medida')

