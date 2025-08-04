# -*- coding: utf-8 -*-
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2023 Leap4Logic Solutions PVT LTD
#    Email : sales@leap4logic.com
#################################################

from odoo import fields, models, api


class xPurchaseOrderLinesReceived(models.Model):
    _name = "x.purchase.order.line.received"

    order_id = fields.Many2one(comodel_name="purchase.order", string="Pedido de compra")
    x_pc_order_id = fields.Many2one(comodel_name="purchase.order", string="PC de compra")
    x_order_line_id = fields.Many2one(comodel_name="purchase.order.line", string="Límea de Orden de compra", copy=False)
    qty_received = fields.Float(string="Recibido", compute="_compute_qty_received")
    product_qty = fields.Float(string="Cantidad", compute="_compute_qty_received")

    @api.onchange('x_order_line_id', 'x_order_line_id.qty_received', 'x_order_line_id.product_qty')
    @api.depends('x_order_line_id', 'x_order_line_id.qty_received', 'x_order_line_id.product_qty')
    def _compute_qty_received(self):
        for line in self:
            line.product_qty = line.x_order_line_id.product_qty
            line.qty_received = line.x_order_line_id.qty_received


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    received_state_progress = fields.Float(string='Progreso', default=0.0, store=True, digits=(16, 1))
    received_count = fields.Integer(string='Recibido', compute="_compute_total_order_count")
    total_count = fields.Integer(string='Total', compute="_compute_total_order_count")

    purchase_origin_id = fields.Many2one('purchase.order', string='Pedido Original')
    split_order_count = fields.Integer(string='Split Order Count', compute='purchase_split_order_count')
    order_line_count = fields.Integer(compute="_compute_split_order_line_count")
    lines_received_ids = fields.One2many('x.purchase.order.line.received', inverse_name='order_id', string='Productos recibidos',
                                         readonly=True)

    def _compute_split_order_line_count(self):
        for res in self:
            res.order_line_count = len(res.order_line)

    @api.depends('order_line.qty_received', 'order_line.product_qty')
    def _compute_total_order_count(self):
        """This function count the totals of sale orders"""
        for res in self:
            received_count = sum(res.order_line.mapped('qty_received')) or 0
            total_count = sum(res.order_line.mapped('product_qty')) or 0
            split_orders = self.env["purchase.order"].search([("purchase_origin_id", "=", res.id)])
            for order in split_orders:
                received_count = received_count + order.received_count
                total_count = total_count + order.total_count
            res.received_count = received_count
            res.total_count = total_count
            if total_count:
                res.received_state_progress = (received_count * 100) / total_count
            else:
                res.received_state_progress = 0

    def button_split_order(self):
        view_id = self.env.ref('l4l_split_purchase.l4l_view_split_purchase_wizard_order_form').id
        lines = []
        for line in self.order_line:
            lines.append((0, 0, {
                'line_id': line and line.id or False,
                'product_id': line.product_id and line.product_id.id or False,
                'quantity': line.product_qty or 0,
                'uom': line.product_id.uom_id and line.product_id.uom_id.id or False,
            }))

        return {
            'name': 'Split Purchase',
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'leap.purchase.order.wizard',
            'view': 'form',
            'view_id': view_id,
            'target': 'new',
            'context': {'default_split_order_line': lines},
        }

    def purchase_split_order_count(self):
        lst = []
        total_order = self.search([('purchase_origin_id', '=', self.id)])
        for ids in total_order:
            lst.append(ids)
        self.split_order_count = len(lst)
        return total_order

    def action_split_smart_button(self):
        purchase_order_list = self.purchase_split_order_count()

        action = self.env['ir.actions.actions']._for_xml_id('purchase.purchase_rfq')

        if len(purchase_order_list) > 1:
            action['domain'] = [('id', 'in', purchase_order_list.ids)]
        elif len(purchase_order_list) == 1:
            form_view = [(self.env.ref('purchase.purchase_order_form').id, 'form')]
            if 'views' in action:
                action['views'] = form_view + [(state, view) for state, view in action['views'] if view != 'form']
            else:
                action['views'] = form_view

            action['res_id'] = purchase_order_list[0].id
        else:
            action = {'type': 'ir.actions.act_window_close'}
            return action
        return action

