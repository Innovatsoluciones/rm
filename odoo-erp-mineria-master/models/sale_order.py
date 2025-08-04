from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
import logging

class SaleOrder(models.Model):
    _inherit = 'sale.order'

    sales_agent = fields.Many2one('res.partner', string='Agente de ventas', domain=lambda self: [('team_id.name', 'ilike', 'Ventas')])
    delivery_time = fields.Date(string='Tiempo de entrega')
    recipient_name = fields.Char(string='Nombre del destinatario')
    project_reference = fields.Char(string='Número de proyecto o requisción')
    general_notes = fields.Text(string='Observaciones generales')
    completed = fields.Integer(string="Realizado")
    origin_sale_order_ids = fields.Many2many(
        'sale.order', 
        'sale_order_origin_rel', 
        'sale_order_id', 
        'origin_sale_order_id', 
        string='Órdenes de Venta de Origen'
    )
    origin_sale_order_links = fields.Html(string='Órdenes de Venta de Origen (Links)', compute='_compute_origin_sale_order_links')

    state = fields.Selection(selection_add=[
        ('approved', 'Aprobado'),
        ('partial_draft', 'Presupuesto parcial'),
        ('partial_sale', 'Pedido parcial'),
        ('completed_sale', 'Pedido completado'),
        ('billed_sale', 'Pedido facturado'),
    ])
    input_value = fields.Char(string="Input Value")

    @api.depends('origin_sale_order_ids')
    def _compute_origin_sale_order_links(self):
        for order in self:
            links = []
            for origin_order in order.origin_sale_order_ids:
                url = f"/web#id={origin_order.id}&view_type=form&model=sale.order"
                links.append(f'<a href="{url}" target="_blank">{origin_order.name}</a>')
            order.origin_sale_order_links = '<br/>'.join(links)
    
    def get_existing_sale_orders(self, selected_sale_order_id):
        sale_order = self.env['sale.order'].browse(selected_sale_order_id)
        sale_order.write({
            'origin_sale_order_ids': [(4, self.id)]
        })
        return sale_order


    def clone_sale_order(self):
        new_order = self.copy(default={'order_line': [(5, 0, 0)]})
        new_order.write({
            'name': new_order.name.replace('C', 'P'),
            'state': 'sale',
            'origin_sale_order_ids': [(4, self.id)]
        })
        return new_order
    
    def custom_add_product(self, test):
        pass

    def custom_function(self, sale_order_id, change_to_completed):
        # Lógica personalizada que utilizará el input
        self.ensure_one()
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        url = f"{base_url}/web#id={sale_order_id}&action=297&view_type=form&model=sale.order"
        body = f'Custom function executed with input: <a href="{url}">Ver orden de venta</a>'
        self.message_post(body=body)
        for order in self:
            order.validate_taxes_on_sales_order()
            if order.partner_id in order.message_partner_ids:
                continue
            order.message_subscribe([order.partner_id.id])
        new_state = 'partial_draft'
        if change_to_completed:
            new_state = 'completed_sale'
        if order.state != 'partial_draft' or order.state != 'completed_sale':
            order.write({
                'state': new_state
            })

    def action_confirm(self):
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'custom.input.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_sale_order_id': self.id,
                'default_order_line_ids': [
                    (0, 0, {
                        'sale_order_line_id': line.id,
                        'custom_quantity': line.product_uom_qty - line.completed,
                        'sale_order_completed': line.completed,
                        'sale_order_product_uom_qty': line.product_uom_qty
                    }) for line in self.order_line
                ]
            }
        }


    def action_cancel(self):
        for origin_sale_order in self.origin_sale_order_ids:
            for line in self.order_line:
                origin_line = line.origin_sale_order_id.order_line.filtered(lambda l: l.product_id == line.product_id)
                if origin_line:
                    new_completed_value = origin_line.completed - line.product_uom_qty
                    origin_line.completed = max(new_completed_value, 0)
        self.ensure_one()
        self.write({'state': 'cancel'})
        return True