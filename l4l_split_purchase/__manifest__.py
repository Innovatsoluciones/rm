# -*- coding: utf-8 -*-
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2023 Leap4Logic Solutions PVT LTD
#    Email : sales@leap4logic.com
#################################################

{
    'name': "Split Purchase",
    'category': 'Purchase',
    'version': '17.0.1.0',
    'sequence': 1,
    'summary': """ Split Purchase, Split Purchase Order, Purchase Order Split, Split, Purchase Split""",
    'description': """This Module Helps Users to Split Purchase Order.""",

    'author': 'Leap4Logic Solutions Private Limited',
    'website': 'https://leap4logic.com/',
    'depends': ['purchase'],
    'data': [
        'data/ir_sequence.xml',
        'security/ir.model.access.csv',
        'views/purchase_order_view.xml',
        'wizard/leap_purchase_order_wizard_view.xml',

    ],
    'installable': True,
    'application': True,
    'images': ['static/description/banner.gif'],
    'license': 'OPL-1',
    'price': '7.99',
    'currency': 'USD',
    'live_test_url': 'https://youtu.be/UVnLsZg3Q9I',
}

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
