from odoo import models, fields, api, _
import logging
from odoo.exceptions import ValidationError

class CustomInputWizard(models.TransientModel):
    _name = 'custom.input.wizard'
    _description = 'Custom Input Wizard'

    sale_order_id = fields.Many2one('sale.order', string="Sale Order")
    order_line_ids = fields.One2many('custom.input.wizard.line', 'wizard_id', string="Order Lines")
    sale_order_state_sale_id = fields.Many2one('sale.order', string='Sale Order', domain="[('state', '=', 'sale')]")
    selected_sale_order_id = fields.Integer(string="Sale Order Selected")

    @api.model
    def fields_view_get(self, fields):
        if self.env.context:
            selected_id = self.env.context.get('default_order_line_ids')
            # self.write({'sale_order_id': selected_id.id})

    @api.onchange('sale_order_id')
    def _onchange_sale_order_id(self):
        pass

    @api.onchange('sale_order_state_sale_id')
    def _onchange_sale_order_state_sale_id(self):
        self.write({'selected_sale_order_id': self.sale_order_state_sale_id.id})

    def write_order_line(self, sale_order, sale_order_line_object):
        sale_order.order_line.create(sale_order_line_object)

    def action_confirm(self):
        sale_order_id = self.sale_order_id.id
        sale_order = self.env['sale.order'].browse(sale_order_id)
        sale_order_to_process = None
        if self.selected_sale_order_id:
            sale_order_to_process = sale_order.get_existing_sale_orders(self.selected_sale_order_id)
        else:
            sale_order_to_process = sale_order.clone_sale_order()
        change_to_completed = True
        for wizard_line in self.order_line_ids:
            if wizard_line.sale_order_line_id:
                line = wizard_line.sale_order_line_id
                actual_price_unit = line.price_unit
                new_completed = line.completed + wizard_line.custom_quantity
                line.write({
                    'price_unit': actual_price_unit,
                    'completed': new_completed
                })
                sale_order_line_object = {
                    'order_id': sale_order_to_process.id,
                    'product_id': line.product_id.id,
                    'product_uom_qty': wizard_line.custom_quantity,
                    'price_unit': actual_price_unit,
                    'tax_id': line.tax_id.ids,
                    'name': line.name,
                    'origin_sale_order_id': sale_order_id
                }
                self.write_order_line(sale_order_to_process, sale_order_line_object)
                if new_completed != line.product_uom_qty:
                    change_to_completed = False
            else:
                logging.warning('No Sale Order Line found with the given ID')
        sale_order.custom_function(sale_order_to_process.id, change_to_completed)
        return

class CustomInputWizardLine(models.TransientModel):
    _name = 'custom.input.wizard.line'
    _description = 'Custom Input Wizard Line'

    wizard_id = fields.Many2one('custom.input.wizard', string="Wizard")
    sale_order_line_id = fields.Many2one('sale.order.line', string="Sale Order Line")
    custom_quantity = fields.Float(string="Custom Quantity", required=True)
    sale_order_completed = fields.Integer(string="Realizado")
    sale_order_product_uom_qty = fields.Float(string="Custom UOM Qty", required=True)

    @api.onchange('custom_quantity')
    def _onchange_custom_quantity(self):
        is_valid_quantity = self.validate_quantity()
        if not is_valid_quantity:
            remaining = self.sale_order_product_uom_qty - self.sale_order_completed
            self.custom_quantity = remaining
            return {
                'warning': {
                    'title': _('Cantidad no válida'),
                    'message': _('La cantidad ingresada excede el límite permitido. La cantidad máxima disponible es: %s y se ajustará al valor máximo') % remaining
                }
            }

    def validate_quantity(self):
        new_completed = self.sale_order_completed + self.custom_quantity
        if self.custom_quantity < 0 or new_completed > self.sale_order_product_uom_qty:
            return False
        return True