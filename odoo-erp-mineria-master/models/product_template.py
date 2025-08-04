from odoo import models, fields
from odoo.exceptions import ValidationError

class ProductTemplate(models.Model):
    _inherit = 'product.template'

    test_external_product_id = fields.Char(string="External Product ID")
    