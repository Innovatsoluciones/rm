from odoo import models, fields, api
from odoo.exceptions import UserError
from odoo.tools.translate import _
import logging

_logger = logging.getLogger(__name__)

class StockPicking(models.Model):
    _inherit = 'stock.picking'

    po_creation_locked = fields.Boolean(string="PO Creation Locked", default=False, copy=False)

    def _check_overdelivery(self, move_line):
        """ Comprueba si una línea de movimiento excede la cantidad del documento origen (PO o SO). """
        move = move_line.move_id
        source_line = move.purchase_line_id or move.sale_line_id
        if not source_line:
            return # No hay línea origen para comparar

        # Determinar tipo de documento y campos relevantes
        if move.purchase_line_id:
            ordered_qty = source_line.product_qty
            source_doc_ref = source_line.order_id.name
            doc_type_str = _("orden de compra")
            operation_type_str = _("recibir")
            already_processed_field = 'purchase_line_id'
        elif move.sale_line_id:
            ordered_qty = source_line.product_uom_qty
            source_doc_ref = source_line.order_id.name
            doc_type_str = _("orden de venta")
            operation_type_str = _("entregar")
            already_processed_field = 'sale_line_id'
        else:
             return # No debería ocurrir si source_line existe

        # Cantidad ya procesada en otros albaranes para la misma línea origen
        domain = [
            ('state', '=', 'done'),
            (already_processed_field, '=', source_line.id),
            ('picking_id', '!=', move_line.picking_id.id)
        ]
        other_picking_moves = self.env['stock.move'].search(domain)
        already_processed_qty = sum(m.quantity_done for m in other_picking_moves)

        # Cantidad procesada en otras líneas del MISMO albarán para la misma línea origen
        sibling_move_lines_domain = [
            ('picking_id', '=', move_line.picking_id.id),
            ('id', '!=', move_line.id), # Excluir la línea actual
            ('move_id.' + already_processed_field, '=', source_line.id)
        ]
        sibling_move_lines = self.env['stock.move.line'].search(sibling_move_lines_domain)
        already_processed_qty += sum(sml.qty_done for sml in sibling_move_lines)

        # Validación
        current_line_qty = move_line.qty_done
        total_processed_including_current = already_processed_qty + current_line_qty
        
        if total_processed_including_current > ordered_qty:
            error_msg = _(
                'No puede %(operation_type)s más cantidad del producto "%(product_name)s" ' 
                'que la solicitada en la %(doc_type)s %(source_ref)s.\n'
                'Pedido: %(ordered).2f\n'
                'Ya Procesado (otros albaranes/líneas): %(already).2f\n'
                'Procesando Ahora: %(current).2f\n'
                'Total Intentado: %(total).2f'
            ) % {
                'operation_type': operation_type_str,
                'product_name': move_line.product_id.display_name,
                'doc_type': doc_type_str,
                'source_ref': source_doc_ref,
                'ordered': ordered_qty,
                'already': already_processed_qty,
                'current': current_line_qty,
                'total': total_processed_including_current,
            }
            raise UserError(error_msg)

    def button_validate(self):
        # Mostrar el modal de confirmación
        return {
            'type': 'ir.actions.act_window',
            'name': 'Confirmar Validación',
            'res_model': 'stock.picking',
            'view_mode': 'form',
            'view_id': self.env.ref('crimiro_users.view_confirm_validate_picking').id,
            'target': 'new',
            'res_id': self.id,
            'context': self.env.context,
        }

    def button_validate_confirmed(self):
        # Realizar validación de sobre-entrega/recepción ANTES de la validación estándar
        for picking in self:
            # Solo validar si es entrada o salida y tiene documento origen
            if picking.picking_type_id.code in ('incoming', 'outgoing') and picking.origin:
                 # Si no hay move_lines (ej. backorder vacío), no hacer nada
                if not picking.move_line_ids:
                    continue
                
                for move_line in picking.move_line_ids:
                    # Solo validar líneas con cantidad > 0
                    if move_line.qty_done > 0:
                        self._check_overdelivery(move_line)

        # Llamar al método original DESPUÉS de nuestra validación
        res = super(StockPicking, self).button_validate()
        
        # Lógica para crear nueva PO de ajuste (solo para recepciones)
        for picking in self:
             # Ejecutar solo si la validación fue exitosa (estado es done)
            if picking.state == 'done' and picking.picking_type_id.code == 'incoming' and picking.origin:
                if picking.po_creation_locked:
                    # Si ya estaba bloqueado, asumimos que ya se procesó o no se debe procesar.
                    continue 

                # Volver a buscar la PO por si acaso
                purchase_order = self.env['purchase.order'].search([('name', '=', picking.origin)], limit=1)
                
                # Crear PO de ajuste solo si la PO original NO viene de una Requisición
                if purchase_order and not purchase_order.requisition_id:
                    lines_to_process = []
                    
                    for move_line in picking.move_line_ids:
                        if move_line.qty_done > 0:
                            po_line_for_data = purchase_order.order_line.filtered(
                                lambda l: l.product_id == move_line.product_id
                            )
                            if po_line_for_data:
                                po_line_data = po_line_for_data[0]
                                # Podríamos añadir una condición aquí para crear solo si hay diferencia,
                                # pero por ahora la lógica original creaba la PO si había líneas procesadas.
                                lines_to_process.append({
                                    'product_id': move_line.product_id.id,
                                    'product_qty': move_line.qty_done, # La cantidad realmente recibida
                                    'price_unit': po_line_data.price_unit,
                                    'date_planned': po_line_data.date_planned,
                                    'taxes_id': [(6, 0, po_line_data.taxes_id.ids)],
                                    'name': po_line_data.name,
                                })

                    if lines_to_process:
                        new_order_vals = {
                            'partner_id': purchase_order.partner_id.id,
                            'origin': f'{purchase_order.name} (Receipt Adj. {picking.name})',
                            'order_line': [(0, 0, line) for line in lines_to_process],
                            'state': 'purchase' 
                        }
                        new_purchase_order = self.env['purchase.order'].create(new_order_vals)
                        picking.message_post(body=_(f'Ajuste de recepción creado: {new_purchase_order.name}'))
                        purchase_order.message_post(body=_(f'Ajuste de recepción {picking.name} generó la orden {new_purchase_order.name}'))
                        
                        # Bloquear futura creación desde este picking
                        picking.po_creation_locked = True
                
                elif purchase_order and purchase_order.requisition_id:
                     # Bloquear igualmente para evitar reprocesamiento
                     picking.po_creation_locked = True
                else:
                    # Si no se encontró la PO original, bloqueamos para evitar errores
                     picking.po_creation_locked = True
        
        return res
    