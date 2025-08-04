from odoo import models, api, _
from odoo.exceptions import ValidationError

class User(models.Model):
    _inherit = 'res.partner'
    #this is the solution
    @api.model
    def create(self, vals):
        users_count = len(self.env["res.partner"].search([]))
        if users_count >= 100:
            raise ValidationError(_("No es posible crear más usuarios, ponte en contacto con tu administrador para poder añadir más."))
        res = super(User, self).create(vals)
        
        return res