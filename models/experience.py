# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
import logging

from odoo import api, fields, models, tools, _
from datetime import timedelta, datetime
import base64

_logger = logging.getLogger(__name__)


class HRLoan(models.Model):
    _inherit = "hr.loan"

    care_experience = fields.Many2one('hr.care.experience')
    care_clearance = fields.Many2one('hr.care.clearance')


class HRContract(models.Model):
    _inherit = "hr.contract"

    care_experience = fields.Many2one('hr.care.experience')
    care_clearance = fields.Many2one('hr.care.clearance')


class AccountAsset(models.Model):
    _inherit = "account.asset"

    care_experience = fields.Many2one('hr.care.experience')
    care_clearance = fields.Many2one('hr.care.clearance')


class HrCareExperience(models.Model):
    _name = "hr.care.experience"
    _description = "Experience Request By Employee"

    name = fields.Many2one('hr.employee', string='Employee', default=lambda self: self.env.user.employee_id.id)
    request_type = fields.Selection([('evidence_request', 'Evidence Request'),
                                     ('resignation_request', 'Resignation Request')],
                                     string="Request Type", default='evidence_request', required=True)
    expected_revealing_date = fields.Date(string="Last Day of Employee",
                                          help='Employee requested date on which he is revealing from the company.')
    hr_contract = fields.One2many('hr.contract', 'care_experience')
    current_contract = fields.Many2one('hr.contract', sting='Current Contract')
    account_asset = fields.One2many('account.asset', 'care_experience')
    loan = fields.One2many('hr.loan', 'care_experience')

    work_phone = fields.Char('Work Phone')
    work_location = fields.Char('Work Location')
    company_id = fields.Many2one('res.company', 'Company')
    department_id = fields.Many2one('hr.department', string='Department')
    parent_id = fields.Many2one('hr.employee', string='Manager')
    coach_id = fields.Many2one('hr.employee', string='Coach')
    date = fields.Datetime(string='Date', readonly=True, index=True, default=fields.Datetime.now)

    state = fields.Selection([('new', 'New'),
                              ('request_sent', 'Request Sent'),
                              ('resignation', 'Resignation Created'),
                              ('approved', 'Approved')],
                             string="Request Type",
                             default='new',
                             required=True)

    @api.onchange('name')
    def onchange_employee(self):
        self.work_phone = self.name.work_phone
        self.work_location = self.name.work_location
        self.company_id = self.name.company_id.id
        self.department_id = self.name.department_id.id
        self.parent_id = self.name.parent_id.id
        self.coach_id = self.name.coach_id.id

        account_asset = self.env['account.asset'].search([('employee', '=', self.name.id), ('state', '=', 'open')])
        current_contract = self.env['hr.contract'].search([('employee_id', '=', self.name.id), ('state', '=', 'open')], limit=1)
        loan = self.env['hr.loan'].search([('employee_id', '=', self.name.id)])
        self.current_contract = current_contract.id

        if account_asset:
            for data in account_asset:
                self.write({'account_asset': [(4, data.id)]})

        for data in self.name.contract_ids:
            self.write({'hr_contract': [(4, data.id)]})

        if loan:
            for data in loan:
                self.write({'loan': [(4, data.id)]})

    def request_experience(self):
        if self.request_type == 'evidence_request':
            self.experience_report()
            self.state = 'request_sent'
        else:
            self.env['hr.resignation'].create({
                'employee_id': self.name.id,
                'department_id': self.department_id.id,
                'expected_revealing_date': self.expected_revealing_date,
                'hr_experience': self.id,
            })
            self.experience_report()
            self.state = 'resignation'

    def request_approve(self):
        group = 'hr.group_hr_manager'
        user_ids = self.env['res.users'].search(
            [('groups_id', '=', self.env.ref(group).id)])
        user = self.env['res.users'].browse(self._uid)
        if user in user_ids:
            self.state = 'approved'

    def experience_report(self):
        if self.request_type == 'evidence_request':
            email_template = self.env.ref('hr_self_care.email_template_hr_request')
        else:
            email_template = self.env.ref('hr_self_care.email_template_inventory_request')

        return self._get_report(email_template=email_template)

    def _get_report(self, email_template=False):
        # context dictionary
        ctx = {}

        # get the users who has HR manager and Department Manager roles
        if self.request_type == 'evidence_request':
            email_list = [user.email for user in self.env['res.users'].sudo().search([])
                          if user.has_group('hr.group_hr_manager') and user.email is not False]

            user_ids = self.env['res.users'].search(
                [('groups_id', '=', self.env.ref('hr.group_hr_manager').id)])
        else:
            email_list = [user.email for user in self.env['res.users'].sudo().search([])
                          if user.has_group('stock.group_stock_manager') and user.email is not False]

            user_ids = self.env['res.users'].search(
                [('groups_id', '=', self.env.ref('stock.group_stock_manager').id)])

        users_char = ','.join(v.login for v in user_ids)

        if email_list and email_template:
            ctx['lang'] = self.env.user.lang
            ctx['date'] = datetime.today().strftime('%d %b, %Y')
            ctx['users_char'] = users_char
            email_template.with_context(ctx).send_mail(self.id, force_send=True, raise_exception=False)

    def edit_resign_experience_report(self):
        self.ensure_one()
        if self.request_type == 'evidence_request':
            report = self.env.ref('hr_self_care.hr_experience_report')._render_qweb_pdf(self.ids[0])
        elif self.request_type == 'resignation_request':
            report = self.env.ref('hr_self_care.hr_resign_experience_report')._render_qweb_pdf(self.ids[0])

        filename = self.name.name + ' Resign Experience.pdf'

        attachment = self.env['ir.attachment'].create({
            'name': filename,
            'type': 'binary',
            'datas': base64.b64encode(report[0]),
            'res_model': 'hr.care.experience',
            'res_id': self.ids[0],
            'mimetype': 'application/x-pdf'
        })

        sing_temp = self.env['sign.template'].create({
            'attachment_id': attachment.id
        })

        res = self.env.ref('sign.sign_template_view_form', False)
        form_view = [(res and res.id or False, 'form')]

        return {
            'type': 'ir.actions.act_window',
            'name': 'Signature Requests',
            'view_mode': 'kanban',
            'res_model': 'sign.template',
            'views': form_view,
            'res_id': sing_temp.id
        }




