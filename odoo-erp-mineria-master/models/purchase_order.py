from odoo import models, fields, exceptions, api
from time import sleep
import logging
import json
from . import utils

class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    requisition_ids = fields.Many2many(
        'purchase.requisition',
        'purchase_requisition_order_rel',
        'purcharse_order_id',
        'purcharse_requisition_id',
        string='Requisiciones',
        copy=False,
    )

    @api.model
    def create(self, vals):
        sequence = self.env['ir.sequence'].next_by_code('purchase.order')
        vals['name'] = self.custom_update_name(sequence, utils.PURCHASE_ORDER_STATE_PREFIXES.get('PURCHASE'), utils.PURCHASE_ORDER_STATE_PREFIXES.get('DRAFT'))
        return super(PurchaseOrder, self).create(vals)

    @api.onchange('requisition_id')
    def _onchange_requisition_id(self):
        for order in self:
            order.requisition_ids = order.requisition_id
            order.update({'requisition_ids': order.requisition_id})

    @api.onchange('requisition_ids')
    def _onchange_requisition_ids(self):
        for order in self:
            if not order.partner_id:
                order.update({'partner_id': order.requisition_ids.vendor_id.id})
            if order.requisition_ids:
                temporal_order_line = order.order_line
                order.order_line = [(5, 0, 0)]
                for requisition in order.requisition_ids:
                    for line in requisition.line_ids:
                        if temporal_order_line.filtered(lambda ol: ol.product_id == line.product_id):
                            if not order.order_line.filtered(lambda ol: ol.product_id == line.product_id):
                                order.order_line += temporal_order_line.filtered(lambda ol: ol.product_id == line.product_id)
                            continue
                        order.order_line += order.order_line.new({
                            'product_id': line.product_id.id,
                            'name': line.product_description_variants or line.product_id.display_name,
                            'date_planned': fields.Datetime.now(),
                            'product_qty': 0,
                            'product_uom': line.product_uom_id.id,
                            'price_unit': line.price_unit,
                            'taxes_id': [],
                        })

    @api.onchange('order_line')
    def _onchange_order_line_product_qty(self):
        requisitions = self.requisition_ids
        for requisition in requisitions:
            for line in requisition.line_ids:
                for order_line in self.order_line:
                    max_qty = line.product_qty - line.qty_ordered
                    if line.product_id == order_line.product_id:
                        order_line.update({
                            'price_unit': line.price_unit,
                            'name': line.product_description_variants or order_line.name
                        })
                        if order_line.product_qty > max_qty:
                            raise exceptions.ValidationError(
                                f'La cantidad supera la establecida en el acuerdo marco, {max_qty} es la cantidad máxima permitida'
                            )
                        
    def custom_update_name(self, original_string, old_value, new_value):
        """
        Actualiza el nombre de la orden de compra reemplazando un valor específico por otro.
        
        Args:
            original_string (str): Cadena original a modificar
            old_value (str): Valor a buscar y reemplazar (por defecto 'P')
            new_value (str): Nuevo valor para reemplazar (por defecto 'PR')
            
        Returns:
            str: Nueva cadena con el valor reemplazado
        """
        if not original_string:
            return original_string
            
        return original_string.replace(old_value, new_value)

    def button_confirm(self):
        # Itera sobre todas las órdenes de compra
        for order in self:
            # Buscar el acuerdo marco usando el requisition_id
            requisition = self.env['purchase.requisition'].browse(order.requisition_id.id)
            
            # Validar si la cantidad de cada línea del acuerdo marco es mayor a la cantidad de la línea de la orden
            for line in order.order_line:
                requisition_line = requisition.line_ids.filtered(lambda l: l.product_id == line.product_id)
                requistion_line_qty_max_left = requisition_line.product_qty - requisition_line.qty_ordered
                if requisition_line and requistion_line_qty_max_left < line.product_qty:
                    raise exceptions.ValidationError(f'La cantidad supera la establecida en el acuerdo marco, {requistion_line_qty_max_left} es la cantidad máxima permitida')
                else:
                    if utils.PURCHASE_ORDER_STATE_PREFIXES.get('DRAFT') in self.name: 
                        self.name = self.custom_update_name(self.name, utils.PURCHASE_ORDER_STATE_PREFIXES.get('DRAFT'), utils.PURCHASE_ORDER_STATE_PREFIXES.get('PURCHASE'))
                    return super(PurchaseOrder, self).button_confirm()

    def force_cancel_with_pickings(self):
        for order in self:
            # Cancelar todos los albaranes relacionados
            pickings = self.env['stock.picking'].search([
                ('origin', '=', order.name),
                ('state', 'not in', ['cancel', 'draft'])
            ])
            
            for picking in pickings:
                if picking.state == 'done':
                    # Crear devolución del albarán completo
                    return_wizard = self.env['stock.return.picking'].with_context(
                        active_ids=picking.ids,
                        active_id=picking.id,
                        active_model='stock.picking'
                    ).create({
                        'picking_id': picking.id,
                    })
                    # Obtener valores por defecto
                    return_wizard._onchange_picking_id()
                    
                    # Establecer cantidades para devolver
                    for return_line in return_wizard.product_return_moves:
                        return_line.quantity = return_line.move_id.product_uom_qty
                    
                    # Crear la devolución
                    new_picking_id, pick_type_id = return_wizard._create_returns()
                    # Confirmar y validar la devolución
                    new_picking = self.env['stock.picking'].browse(new_picking_id)
                    new_picking.action_confirm()
                    new_picking.action_assign()
                    
                    # Procesar todas las líneas de movimiento
                    for move in new_picking.move_ids:
                        move.quantity_done = move.product_uom_qty
                    
                    new_picking.with_context(skip_backorder=True).button_validate()
                else:
                    # Si no está en 'done', simplemente cancelar
                    picking.action_cancel()
            
            # Procesar los movimientos de stock recibidos
            stock_moves = self.env['stock.move'].search([
                ('purchase_line_id', 'in', order.order_line.ids),
                ('state', '=', 'done')
            ])

            self.create_return_moves(stock_moves)
            

            
            # Forzar la cancelación de la orden directamente
            order.write({
                'state': 'cancel',
            })
            
            # Actualizar el estado de las líneas y limpiar referencias
            order.order_line.write({
                'state': 'cancel',
                'move_ids': [(5, 0, 0)]  # Desvincula todos los movimientos de stock
            })
            
            # Desvincula los albaranes
            order.picking_ids = [(5, 0, 0)]
            
        return True
    
    def create_return_moves(self, stock_moves):
        if not stock_moves:
            return

        original_picking = stock_moves[0].picking_id
        if not original_picking:
            return

        return_picking = self.env['stock.picking'].create({
            'partner_id': original_picking.partner_id.id,
            'picking_type_id': original_picking.picking_type_id.id,
            'location_id': original_picking.location_dest_id.id,
            'location_dest_id': original_picking.location_id.id,
            'origin': f'Devolución de {original_picking.name}',
            'move_type': original_picking.move_type,
        })

        for move in stock_moves:
            return_move = self.env['stock.move'].create({
                'name': f'Return: {move.name}',
                'product_id': move.product_id.id,
                'product_uom': move.product_uom.id,
                'product_uom_qty': move.product_uom_qty,
                'location_id': move.location_dest_id.id,
                'location_dest_id': move.location_id.id,
                'picking_id': return_picking.id,
                'origin_returned_move_id': move.id,
                'procure_method': 'make_to_stock',
            })

            return_move._action_confirm()
            return_move._action_assign()
            return_move._set_quantity_done(move.product_uom_qty)

        return_picking._action_done()