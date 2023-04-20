# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
import logging

from odoo import api, fields, models, tools, _
from odoo.exceptions import ValidationError
from datetime import timedelta, datetime

_logger = logging.getLogger(__name__)


class HrCareClearance(models.Model):
    _name = "hr.care.clearance"
    _description = "Clearance Review By HR Department"

    name = fields.Char('Name')
    employee_id = fields.Many2one('hr.employee', 'Employee')
    hr_contract = fields.One2many('hr.contract', 'care_clearance')
    account_asset = fields.One2many('account.asset', 'care_clearance')
    loan = fields.One2many('hr.loan', 'care_clearance')

    work_phone = fields.Char('Work Phone')
    work_location = fields.Char('Work Location')
    company_id = fields.Many2one('res.company', 'Company')
    department_id = fields.Many2one('hr.department', string='Department')
    parent_id = fields.Many2one('hr.employee', string='Manager')
    coach_id = fields.Many2one('hr.employee', string='Coach')

    state = fields.Selection(
        [('new', 'New'),
         ('inventory_approve', 'Inventory Approve'),
         ('finance_approve', 'Finance Approve'),
         ('depart_approve', 'Department Approve'),
         ('hr_approve', 'HR Approve'),
         ('approved', 'Approved')],
        string="Request Type", default='new', required=True)

    @api.onchange('employee_id')
    def onchange_employee(self):
        self.name = f"{self.employee_id.name}'s Clearance"
        self.work_phone = self.employee_id.work_phone
        self.work_location = self.employee_id.work_location
        self.company_id = self.employee_id.company_id.id
        self.department_id = self.employee_id.department_id.id
        self.parent_id = self.employee_id.parent_id.id
        self.coach_id = self.employee_id.coach_id.id

        account_asset = self.env['account.asset'].search(
                [('employee', '=', self.employee_id.id), ('state', '=', 'open')])
        loan = self.env['hr.loan'].search([('employee_id', '=', self.employee_id.id)])

        if account_asset:
            for data in account_asset:
                self.write({'account_asset': [(4, data.id)]})

        for data in self.employee_id.contract_ids:
            self.write({'hr_contract': [(4, data.id)]})

        if loan:
            for data in loan:
                self.write({'loan': [(4, data.id)]})

    def experience_report(self):
        if self.state == 'finance_approve':
            email_template = self.env.ref('hr_self_care.email_template_department_request')
        elif self.state == 'new':
            email_template = self.env.ref('hr_self_care.email_template_finance_request')
        else:
            email_template = self.env.ref('hr_self_care.email_template_hr_clearance_request')

        return self._get_report(email_template=email_template)

    def _get_report(self, email_template=False):
        # context dictionary
        ctx = {}

        # get the users who has HR manager and Department Manager roles
        if self.state == 'finance_approve':
            email_list = [user.email for user in self.env['res.users'].sudo().search([])
                          if user.has_group('hr.group_hr_manager') and user.email is not False]

            user_ids = self.department_id.manager_id.user_id.id
        elif self.state == 'new':
            email_list = [user.email for user in self.env['res.users'].sudo().search([])
                          if user.has_group('account.group_account_manager') and user.email is not False]

            user_ids = self.env['res.users'].search(
                [('groups_id', '=', self.env.ref('account.group_account_manager').id)])
        else:
            email_list = [user.email for user in self.env['res.users'].sudo().search([])
                          if user.has_group('hr.group_hr_manager') and user.email is not False]

            user_ids = self.env['res.users'].search(
                [('groups_id', '=', self.env.ref('hr.group_hr_manager').id)])
        if user_ids:
            users_char = ','.join(v.login for v in user_ids)

            if email_list and email_template:
                ctx['lang'] = self.env.user.lang
                ctx['date'] = datetime.today().strftime('%d %b, %Y')
                ctx['users_char'] = users_char
                email_template.with_context(ctx).send_mail(self.id, force_send=True, raise_exception=False)

    def inventory_approve(self):
        group= 'stock.group_stock_manager'
        user_ids = self.env['res.users'].search(
            [('groups_id', '=', self.env.ref(group).id)])
        user = self.env['res.users'].browse(self._uid)

        account_asset = self.env['account.asset'].search(
            [('employee', '=', self.employee_id.id), ('state', '!=', 'model')])

        if user in user_ids:
            if account_asset:
                raise ValidationError(_('Clearance can not be confirmed when there is an asset not returned. If the assets are returned make sure to set the asset to draft and remove it.'))
            else:
                self.experience_report()
                self.state = 'finance_approve'

    def finance_approve(self):
        loan = self.env['hr.loan'].search([('employee_id', '=', self.employee_id.id)])
        if loan:
            for lon in loan:
                if lon.total_amount != lon.total_paid_amount:
                    raise ValidationError(_('There is a loan still not paid. Make sure the loan is paid before confirming the clearance request.'))
                else:
                    self.experience_report()
                    self.state = 'depart_approve'
        else:
            self.experience_report()
            self.state = 'depart_approve'

    def department_approve(self):
        user = self.env['res.users'].browse(self._uid)
        if user.id == self.department_id.manager_id.user_id.id:
            self.experience_report()
            self.state = 'hr_approve'

    def hr_approve(self):
        group = 'hr.group_hr_manager'
        user_ids = self.env['res.users'].search(
            [('groups_id', '=', self.env.ref(group).id)])
        user = self.env['res.users'].browse(self._uid)
        if user in user_ids:
            experience = self.env['hr.care.experience'].search(
                [('name', '=', self.employee_id.id), ('state', '=', 'resignation')], limit=1)

            experience.state = 'approved'
            self.state = 'approved'