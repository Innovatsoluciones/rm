# -*- coding: utf-8 -*-


{
    'name': "Split Sales",
    'category': 'Sales',
    'version': '17.0.1.0',
    'sequence': 1,
    'summary': """ Split Sale, Split Sale Order, Sale Order Split, Split, Sale Split""",
    'description': """This Module Helps Users to Split Sale Order.""",
    'author': 'MX',
    'website': 'https://mx.com/',
    'depends': ['sale'],
    'data': [
        'data/ir_sequence.xml',
        'security/ir.model.access.csv',
        'views/sale_order_view.xml',
        'wizard/leap_sale_order_wizard_view.xml',
    ],
    'installable': True,
    'application': True,
    'images': [],
    'license': 'LGPL-3',
    'price': '0',
    'currency': 'USD',
}

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
