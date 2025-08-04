# -*- coding: utf-8 -*-
#
#################################################

from odoo import fields, models, api


class xSaleOrderLinesReceived(models.Model):
    _name = "x.sale.order.line.delivered"

    order_id = fields.Many2one(comodel_name="sale.order", string="Pedido de venta")
    x_so_order_id = fields.Many2one(comodel_name="sale.order", string="SO de venta")
    x_order_line_id = fields.Many2one(comodel_name="sale.order.line", string="Límea de Orden de venta", copy=False)
    qty_delivered = fields.Float(string="Entregado", compute="_compute_qty_delivered")
    product_uom_qty = fields.Float(string="Cantidad", compute="_compute_qty_delivered")

    @api.depends('x_order_line_id', 'x_order_line_id.qty_delivered', 'x_order_line_id.product_uom_qty')
    def _compute_qty_delivered(self):
        for line in self:
            line.product_uom_qty = line.x_order_line_id.product_uom_qty
            line.qty_delivered = line.x_order_line_id.qty_delivered


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    delivery_state_progress = fields.Float(string='Progreso de entrega', default=0.0, store=True, digits=(16, 1))
    delivered_count = fields.Integer(string='Entregado', compute="_compute_total_order_count")
    total_count = fields.Integer(string='Cantidad', compute="_compute_total_order_count")
    state = fields.Selection(selection_add=[('by_authorize', 'Por autorizar'), ('pend', 'Pendiente')],
                             ondelete={'by_authorize': 'cascade', 'pend': 'cascade', })

    sale_origin_id = fields.Many2one('sale.order', string='SO Original')
    split_order_count = fields.Integer(compute="_compute_split_order_count")
    order_line_count = fields.Integer(compute="_compute_split_order_line_count")
    lines_delivered_ids = fields.One2many('x.sale.order.line.delivered', 'order_id', string='Productos entregados')
    checklist_state_progress = fields.Float(string='Progreso de Estado', default=25.0, store=True, digits=(16, 1))

    @api.onchange('state')
    def onchange_state(self):
        if self.state:
            if self.state == "draft":
                self.checklist_state_progress = 25.0
            elif self.state == "by_authorize":
                self.checklist_state_progress = 50.0
            elif self.state == "pend":
                self.checklist_state_progress = 75.0
            elif self.state == "sale":
                self.checklist_state_progress = 100.0

    def _can_be_confirmed(self):
        self.ensure_one()
        return self.state in {'draft', 'sent', 'pend'}

    def action_pend(self):
        self.state = "pend"

    def _compute_split_order_line_count(self):
        for res in self:
            res.order_line_count = len(res.order_line)

    def _compute_split_order_count(self):
        for res in self:
            res.split_order_count = self.env["sale.order"].search_count([("sale_origin_id", "=", res.id)])

    @api.depends('order_line.qty_delivered', 'order_line.product_uom_qty')
    def _compute_total_order_count(self):
        """This function count the totals of sale orders"""
        for res in self:
            delivered_count = sum(res.order_line.mapped('qty_delivered')) or 0
            total_count = sum(res.order_line.mapped('product_uom_qty')) or 0
            split_orders = self.env["sale.order"].search([("sale_origin_id", "=", res.id)])
            for order in split_orders:
                delivered_count = delivered_count + order.delivered_count
                total_count = total_count + order.total_count
            res.delivered_count = delivered_count
            res.total_count = total_count
            if total_count:
                res.delivery_state_progress = (delivered_count * 100) / total_count
            else:
                res.delivery_state_progress = 0

    def button_split_order(self):
        view_id = self.env.ref('l4l_split_sales.l4l_view_split_sale_wizard_order_form').id
        lines = []
        for line in self.order_line:
            lines.append((0, 0, {
                'line_id': line and line.id or False,
                'product_id': line.product_id and line.product_id.id or False,
                'quantity': line.product_uom_qty or 0,
                'uom': line.product_id.uom_id and line.product_id.uom_id.id or False,
            }))

        return {
            'name': 'Dividir venta',
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'leap.sale.order.wizard',
            'view': 'form',
            'view_id': view_id,
            'target': 'new',
            'context': {'default_split_order_line': lines},
        }

    def sale_split_order_count(self):
        lst = []
        total_order = self.search([('sale_origin_id', '=', self.id)])
        for ids in total_order:
            lst.append(ids)
        self.split_order_count = len(lst)
        return total_order

    def action_split_smart_button(self):
        sale_order_list = self.sale_split_order_count()
        action = self.env['ir.actions.actions']._for_xml_id('sale.action_quotations')

        if len(sale_order_list) > 1:
            action['domain'] = [('id', 'in', sale_order_list.ids)]
        elif len(sale_order_list) == 1:
            form_view = [(self.env.ref('sale.view_order_form').id, 'form')]
            if 'views' in action:
                action['views'] = form_view + [(state, view) for state, view in action['views'] if view != 'form']
            else:
                action['views'] = form_view

            action['res_id'] = sale_order_list[0].id
        else:
            action = {'type': 'ir.actions.act_window_close'}
            return action
        return action

