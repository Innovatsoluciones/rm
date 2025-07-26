from odoo import _, fields, models, api
from odoo.exceptions import UserError


class xSaleOrderLinesDelivered(models.Model):
    _name = "x.sale.order.line.delivered"

    x_sale_order = fields.Many2one(comodel_name="sale.order", string="Pedido de venta", copy=False)
    x_pedido_id = fields.Many2one(comodel_name="sale.order", string="Pedido hijo",
                                    related='x_order_line_id.order_id')
    x_order_line_id = fields.Many2one(comodel_name="sale.order.line", string="Línea de Orden de venta", copy=False)
    qty_delivered = fields.Float(string="Entregado", compute="_compute_qty_delivered")
    product_uom_qty = fields.Float(string="Cantidad", compute="_compute_qty_delivered")

    @api.depends('x_order_line_id', 'x_order_line_id.qty_delivered', 'x_order_line_id.product_uom_qty')
    def _compute_qty_delivered(self):
        for line in self:
            line.product_uom_qty = line.x_order_line_id.product_uom_qty
            line.qty_delivered = line.x_order_line_id.qty_delivered


class SaleOrder(models.Model):
    _inherit = "sale.order"

    delivery_state_progress = fields.Float(string='Delivery Progress', default=0.0, store=True, digits=(16, 1))
    delivered_count = fields.Integer(string='Delivered count', compute="_compute_total_order_count")
    total_count = fields.Integer(string='Total count', compute="_compute_total_order_count")
    state = fields.Selection(selection_add=[('by_authorize', 'Por autorizar'), ('pend', 'Pendiente')],
                             ondelete={'by_authorize': 'cascade', 'pend': 'cascade', })
    checklist_state_progress = fields.Float(string='Checklist State Progress', default=25.0, store=True, digits=(16, 1))

    # Added new field
    split_sale_order_id = fields.Many2one(comodel_name="sale.order", string="Source Order Reference", copy=False)
    split_order_count = fields.Integer(compute="_compute_split_order_count")
    lines_delivered_ids = fields.One2many('x.sale.order.line.delivered', 'x_sale_order', string='Productos entregados')

    def _can_be_confirmed(self):
        self.ensure_one()
        return self.state in {'draft', 'sent', 'pend'}

    def action_pend(self):
        self.state = "pend"

    @api.depends('order_line.qty_delivered', 'order_line.product_uom_qty')
    def _compute_total_order_count(self):
        """This function count the totals of sale orders"""
        for res in self:
            delivered_count = sum(res.order_line.mapped('qty_delivered')) or 0
            total_count = sum(res.order_line.mapped('product_uom_qty')) or 0
            split_orders = self.env["sale.order"].search([("split_sale_order_id", "=", res.id)])
            for order in split_orders:
                delivered_count = delivered_count + order.delivered_count
                total_count = total_count + order.total_count
            res.delivered_count = delivered_count
            res.total_count = total_count
            if total_count:
                res.delivery_state_progress = (delivered_count * 100)/total_count
            else:
                res.delivery_state_progress = 0

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

    def _compute_split_order_count(self):
        """This function count the split sale orders"""
        for res in self:
            res.split_order_count = self.env["sale.order"].search_count(
                [("split_sale_order_id", "=", res.id)]
            )

    def action_split_sale_order_quotation(self):
        """
        This function used to trigger the wizard from button with correct context
        """
        return {
            "name": ("Split Sale Order Wizard"),
            "type": "ir.actions.act_window",
            "res_model": "sale.order.split.quotation",
            "view_mode": "form",
            "target": "new",
        }

    def action_split_orders(self):
        """This function open tree and form view of split sale order"""
        self.ensure_one()
        action = self.env["ir.actions.act_window"]._for_xml_id("sale.action_quotations")
        action["domain"] = [("split_sale_order_id", "=", self.id)]
        return action

    def _check_split_order(self):
        """This function Check the order state and condition before split"""
        self.ensure_one()
        if self.state not in ("draft", "sent"):
            raise UserError(_("You can't split sale order in %s state!") % (self.state))
        if not len(self.order_line) > 1:
            raise UserError(
                _("More than one Order Line is required to Split the Sale Order")
            )

    def _split_order_by_lines(self, lines, num_order):
        """
        This function remove lines from orders in self and put them into
        a new one
        """
        for order in self:
            order._check_split_order()
            sale_name = self.env['ir.sequence'].next_by_code('x.sale.order')
            split_order = self.env["sale.order"]
            for order in self:
                if not order.order_line - lines:
                    raise UserError(
                        _("You can't split off all lines from order %s") % order.name
                    )
                split_order = order.copy(default={"name": str(sale_name),
                                                  "state": "by_authorize",
                                                  "checklist_state_progress": 25.0,
                                                  "split_sale_order_id": order.id})
                split_order.write({"order_line": lines})
                for line in lines:
                    split_order_line = self.env["x.sale.order.line.delivered"].\
                        create({'x_sale_order': order.id, 'x_order_line_id': line.id,
                                'qty_delivered': line.qty_delivered, 'product_uom_qty': line.product_uom_qty,})

            return split_order

    def _split_order_by_category(self):
        """
        This function split sale order lines into new sale orders based
        on category
        """
        for order in self:
            order._check_split_order()

            split_order = self.env["sale.order"]
            for order in self:
                categories = order.order_line.mapped("product_id.categ_id")
                if len(categories) == 1:
                    raise UserError(
                        _(
                            "You can't split the sale order as there is only one "
                            "category available."
                        )
                    )
                num_order = 1
                for category in categories[1:]:
                    order_lines_with_current_category = order.order_line.filtered(
                        lambda line, category=category: line.product_id.categ_id
                        == category
                    )
                    sale_name = self.env['ir.sequence'].next_by_code('x.sale.order')

                    new_order = order.copy(
                        default={
                            "name": str(sale_name),
                            "state": "by_authorize",
                            "checklist_state_progress": 25.0,
                            "split_sale_order_id": order.id,
                            "order_line": [
                                (4, line.id)
                                for line in order_lines_with_current_category
                            ],
                        }
                    )
                    split_order |= new_order
                    for line in order_lines_with_current_category:
                        split_order_line = self.env["x.sale.order.line.delivered"]. \
                            create({'x_sale_order': order.id, 'x_order_line_id': line.id,
                                    'qty_delivered': line.qty_delivered, 'product_uom_qty': line.product_uom_qty, })

            return split_order
