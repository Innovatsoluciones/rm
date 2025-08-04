from odoo import models, fields, api

class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'


    @api.depends('product_id', 'product_uom', 'product_uom_qty')
    def _compute_price_unit(self):
        for line in self:
            if line.price_unit > 0:
                continue
            else:
                super(PurchaseOrderLine, line)._compute_price_unit()

    @api.onchange('product_uom_qty')
    def onchange_product_uom_qty(self):
        for line in self:
            if line.price_unit_manual:
                continue
            else:
                super(PurchaseOrderLine, line).onchange_product_uom_qty()

    def _compute_price_unit(self):
        """Evita que el precio se actualice si ya tiene un valor manual"""
        if not self.price_unit or self.price_unit == 0.0:
            return super(PurchaseOrderLine, self)._compute_price_unit()

    @api.model
    def write(self, vals):
        if 'product_qty' in vals:
            for line in self:
                if line.order_id.state == 'purchase':
                    raise ValueError("No puedes modificar la cantidad en una orden de compra confirmada.")
        return super(PurchaseOrderLine, self).write(vals)