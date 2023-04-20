# -*- coding: utf-8 -*-
{
    'name' : 'Self Care',
    'version' : '1.00',
    'summary': 'help to manage sel care',
    'sequence': 10,
    'description': """
    """,
    'category': 'hr',
    'website': 'https://www.odoo.com/page/etta',
    'depends' : ['hr', 'hr_contract', 'asset_employee', 'sign', 'ohrms_loan'],
    'data': [
        'security/ir.model.access.csv',
        'views/experience.xml',
        'views/clearance.xml',
        'report/experience_report.xml',
        'report/resign_experience_report.xml',
        'data/department_request_template.xml',
        'data/hr_clearance_template.xml',
        'data/hr_request_template.xml',
        'data/inventory_request_template.xml',
        'data/finance_request_template.xml',
    ],
    'demo': [
    ],
    'images': [],
    'installable': True,
    'application': True,
    'auto_install': False,
    'license': 'LGPL-3',
}
