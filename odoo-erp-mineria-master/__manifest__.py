{
  "name": "ERP Mineria",
  "version": "1.0.0",
  "author": "Christian Rosales",
  "website": "https://google.com",
  "depends": [
    "base",
    "product",
    "account",
    "purchase",
    "sale",
    "purchase_requisition"
  ],
  "data": [
    "security/ir.model.access.csv",
    "views/custom_input_wizard_views.xml",
    "views/product_template_customizations_form.xml",
    "views/purchase_order_form_custom.xml",
    "views/sale_order_views.xml",
    "views/sale_order_line_views.xml",
    "views/sale_order_line_form.xml",
    "views/requistion_agrement_custom.xml",
    "data/sequence_account_move_custom.xml",
    "views/sale_order_menu.xml",
    "views/stock_picking_views.xml"
  ],
  "installable": True,
  "auto_install": False
}