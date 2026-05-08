from dateutil.relativedelta import relativedelta

from odoo import fields, models, _, api
from odoo.exceptions import UserError


class SiteProject(models.Model):
    _name = "site.project"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name desc, id desc'
    _description = 'Project Site'

    name = fields.Char(string='Reference', required=True, copy=False, readonly=True,
                       default=lambda self: _('New'), tracking=True)
    company_id = fields.Many2one('res.company', 'Company', required=True, index=True,
                                 default=lambda self: self.env.company, tracking=True)
    partner_id = fields.Many2one('res.partner', 'Customer', tracking=True)
    user_id = fields.Many2one('res.users', 'Manager', tracking=True)
    user_ids = fields.Many2many('res.users', string='Site Engineers', tracking=True)
    date_start = fields.Date('Started On', tracking=True)
    date_complete = fields.Date('Completed On', tracking=True)
    warranty_period = fields.Integer('Warranty Period', default=12, tracking=True)  # in months
    warranty_expiry_date = fields.Date('Warranty Expiry Date', compute='_compute_warranty_expiry_date')
    warranty_state = fields.Selection(
        [('no', 'No Warranty'), ('under', 'Under Warranty'), ('expire', 'Warranty Expired'), ],
        compute='_compute_warranty_state', string='Warranty Status')
    origin = fields.Char("Source Document")
    boq_ids = fields.One2many('crm.boq', 'site_project_id', string="Bill of Quantities")
    boq_count = fields.Integer('Sale Orders Count', compute='_compute_boq_count')
    sale_ids = fields.One2many('sale.order', 'site_project_id', string="Sales Orders")
    sale_count = fields.Integer('Sale Orders Count', compute='_compute_sale_count')
    purchase_ids = fields.One2many('purchase.order', 'site_project_id', string="Purchase Orders")
    purchase_count = fields.Integer('Purchase Orders Count', compute='_compute_purchase_count')
    invoice_ids = fields.One2many('account.move', 'site_project_id', string="Invoices",
                                  domain=[('move_type', 'in', ('out_invoice', 'out_refund'))])
    invoice_count = fields.Integer('Invoice Count', compute='_compute_invoice_count')
    bill_ids = fields.One2many('account.move', 'site_project_id', string="Bills",
                               domain=[('move_type', 'in', ('in_invoice', 'in_refund'))])
    bill_count = fields.Integer('Bill Count', compute='_compute_bill_count')
    picking_in_ids = fields.One2many('stock.picking', 'site_project_id', string="Receipts",
                                     domain=[('picking_type_code', '=', 'incoming')])
    picking_out_ids = fields.One2many('stock.picking', 'site_project_id', string="Deliveries",
                                      domain=[('picking_type_code', '=', 'outgoing')])
    picking_internal_ids = fields.One2many('stock.picking', 'site_project_id', string="Internal Transfers",
                                           domain=[('picking_type_code', '=', 'internal')])
    picking_in_count = fields.Integer('Receipts Count', compute='_compute_picking_in_count')
    picking_dropship_ids = fields.One2many('stock.picking', 'site_project_id', string="Dropships",
                                           domain=[('picking_type_code', '=', 'dropship')])
    picking_dropship_count = fields.Integer('Dropship Count', compute='_compute_picking_dropship_count')
    picking_out_count = fields.Integer('Deliveries Count', compute='_compute_picking_out_count')
    picking_internal_count = fields.Integer('Internal Transfer Count', compute='_compute_picking_internal_count')
    state = fields.Selection(
        [('new', 'New'), ('ongoing', 'Ongoing'), ('done', 'Completed'), ('postponed', 'Postponed'),
         ('cancel', 'Dropped')], default='new', tracking=True, copy=False)
    consultant_name = fields.Char('Consultant Name')
    architect_name = fields.Char('Architect Name')
    # site address
    site_id = fields.Many2one('crm.inquiry.site', string="Site")
    street = fields.Char('Street', tracking=True)
    street2 = fields.Char("Street", tracking=True)
    zip = fields.Char('Zip', tracking=True)
    city = fields.Char('City', tracking=True)
    state_id = fields.Many2one("res.country.state", string='State', domain="[('country_id', '=?', country_id)]",
                               tracking=True)
    country_id = fields.Many2one('res.country', string='Country', tracking=True)

    @api.depends('partner_id')
    def _compute_display_name(self):
        for site in self:
            name = site.name
            if site.partner_id:
                name = f'{name} - {site.partner_id.name}'
            site.display_name = name
        return super(SiteProject, self)._compute_display_name()

    @api.depends('boq_ids')
    def _compute_boq_count(self):
        for rec in self:
            rec.boq_count = len(rec.boq_ids)

    @api.depends('sale_ids')
    def _compute_sale_count(self):
        for rec in self:
            rec.sale_count = len(rec.sale_ids)

    @api.depends('purchase_ids')
    def _compute_purchase_count(self):
        for rec in self:
            rec.purchase_count = len(rec.purchase_ids)

    @api.depends('invoice_ids')
    def _compute_invoice_count(self):
        for rec in self:
            rec.invoice_count = len(rec.invoice_ids)

    @api.depends('bill_ids')
    def _compute_bill_count(self):
        for rec in self:
            rec.bill_count = len(rec.bill_ids)

    @api.depends('picking_in_ids')
    def _compute_picking_in_count(self):
        for rec in self:
            rec.picking_in_count = len(rec.picking_in_ids)

    @api.depends('picking_out_ids')
    def _compute_picking_out_count(self):
        for rec in self:
            rec.picking_out_count = len(rec.picking_out_ids)

    @api.depends('picking_dropship_ids')
    def _compute_picking_dropship_count(self):
        for rec in self:
            rec.picking_dropship_count = len(rec.picking_dropship_ids)

    @api.depends('picking_internal_ids')
    def _compute_picking_internal_count(self):
        for rec in self:
            rec.picking_internal_count = len(rec.picking_internal_ids)

    @api.depends('date_complete', 'warranty_period')
    def _compute_warranty_expiry_date(self):
        for rec in self:
            if rec.date_complete and rec.warranty_period:
                date_warranty = rec.date_complete + relativedelta(months=rec.warranty_period)
                rec.warranty_expiry_date = date_warranty
            else:
                rec.warranty_expiry_date = False

    @api.depends('warranty_expiry_date')
    def _compute_warranty_state(self):
        today = fields.Date.today()
        for rec in self:
            state = 'no'
            if rec.warranty_expiry_date:
                if rec.warranty_expiry_date >= today:
                    state = 'under'
                elif rec.warranty_expiry_date < today:
                    state = 'expire'
            rec.warranty_state = state

    @api.depends('name', 'site_id')
    def _compute_display_name(self):
        for order in self:
            name = order.name
            if order.site_id:
                name = f'{name} - {order.site_id.name}'
            order.display_name = name


    @api.onchange('partner_id')
    def _onchange_partner_id(self):
        if self.partner_id:
            self.update({
                'street': self.partner_id.street,
                'street2': self.partner_id.street2,
                'city': self.partner_id.city,
                'state_id': self.partner_id.state_id.id,
                'country_id': self.partner_id.country_id.id,
                'zip': self.partner_id.zip,
            })

    @api.model_create_multi
    def create(self, vals_list):
        # project site record is not allowed to create manually.
        if not self._context.get('allow_site_project_creation'):
            raise UserError(_('You cannot create a new project site manually.'))
        Company = self.env['res.company']
        for val in vals_list:
            if val.get('name', _('New')) == _('New'):
                company_id = val.get('company_id')
                if not company_id:
                    raise UserError(_("No company could set to create a project site record."))
                company_id = Company.browse(company_id)
                sequence_id = company_id.site_project_sequence_id
                if not sequence_id:
                    raise UserError(
                        _('Project site creation failed. No sequence was found. Goto Company and set a Project Site Sequence.'))
                val['name'] = sequence_id.next_by_id() or _('New')
        result = super(SiteProject, self).create(vals_list)
        return result

    @api.model
    def _search(self, domain, offset=0, limit=None, order=None, access_rights_uid=None):
        print(domain)
        print(access_rights_uid)
        return super()._search(domain, offset, limit, order, access_rights_uid)

    def set_to_ongoing(self):
        self.write({
            'state': 'ongoing',
        })

    def set_to_done(self):
        if any(not l.date_complete for l in self):
            raise UserError(_('Please enter the completion date of this project.'))
        self.write({
            'state': 'done',
        })

    def set_to_postponed(self):
        self.write({
            'state': 'postponed',
        })

    def set_to_cancel(self):
        self.write({
            'state': 'cancel',
        })

    def set_to_new(self):
        self.write({
            'state': 'new',
        })

    def action_view_boq(self):
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id("presales.action_view_crm_boq")
        boq_ids = self.boq_ids
        if len(boq_ids) > 1:
            action['domain'] = [('id', 'in', boq_ids.ids)]
        elif boq_ids:
            form_view = [(self.env.ref('presales.crm_boq_view_form').id, 'form')]
            if 'views' in action:
                action['views'] = form_view + [(state, view) for state, view in action['views'] if view != 'form']
            else:
                action['views'] = form_view
            action['res_id'] = boq_ids.id
        action['context'] = dict(self._context, default_site_project_id=self.id)
        action['domain'] = [('site_project_id', '=', self.id)]
        return action

    def action_view_sale_orders(self):
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id("sale.action_quotations_with_onboarding")
        sales = self.sale_ids
        if len(sales) > 1:
            action['domain'] = [('id', 'in', sales.ids)]
        elif sales:
            form_view = [(self.env.ref('sale.view_order_form').id, 'form')]
            if 'views' in action:
                action['views'] = form_view + [(state, view) for state, view in action['views'] if view != 'form']
            else:
                action['views'] = form_view
            action['res_id'] = sales.id
        action['context'] = dict(self._context, default_site_project_id=self.id)
        action['domain'] = [('site_project_id', '=', self.id)]
        return action

    def action_view_purchase_orders(self):
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id("purchase.purchase_rfq")
        purchases = self.purchase_ids
        if len(purchases) > 1:
            action['domain'] = [('id', 'in', purchases.ids)]
        elif purchases:
            form_view = [(self.env.ref('purchase.purchase_order_form').id, 'form')]
            if 'views' in action:
                action['views'] = form_view + [(state, view) for state, view in action['views'] if view != 'form']
            else:
                action['views'] = form_view
            action['res_id'] = purchases.id
        action['context'] = dict(self._context, default_site_project_id=self.id)
        action['domain'] = [('site_project_id', '=', self.id)]
        return action

    def action_view_invoices(self):
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id("account.action_move_out_invoice_type")
        invoices = self.invoice_ids
        if len(invoices) > 1:
            action['domain'] = [('id', 'in', invoices.ids)]
        elif invoices:
            form_view = [(self.env.ref('account.view_move_form').id, 'form')]
            if 'views' in action:
                action['views'] = form_view + [(state, view) for state, view in action['views'] if view != 'form']
            else:
                action['views'] = form_view
            action['res_id'] = invoices.id
        action['context'] = dict(self._context, default_site_project_id=self.id)
        action['domain'] = [('site_project_id', '=', self.id), ('move_type', 'in', ('out_invoice', 'out_refund'))]
        return action

    def action_view_bills(self):
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id("account.action_move_in_invoice_type")
        bills = self.bill_ids
        if len(bills) > 1:
            action['domain'] = [('id', 'in', bills.ids)]
        elif bills:
            form_view = [(self.env.ref('account.view_move_form').id, 'form')]
            if 'views' in action:
                action['views'] = form_view + [(state, view) for state, view in action['views'] if view != 'form']
            else:
                action['views'] = form_view
            action['res_id'] = bills.id
        action['context'] = dict(self._context, default_site_project_id=self.id, default_move_type='in_invoice', display_account_trust=True)
        action['domain'] = [('site_project_id', '=', self.id), ('move_type', 'in', ('in_invoice', 'in_refund'))]
        return action

    def action_view_in_picking(self):
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id("stock.action_picking_tree_incoming")
        pickings = self.picking_in_ids
        if len(pickings) > 1:
            action['domain'] = [('id', 'in', pickings.ids)]
        elif pickings:
            form_view = [(self.env.ref('stock.view_picking_form').id, 'form')]
            if 'views' in action:
                action['views'] = form_view + [(state, view) for state, view in action['views'] if view != 'form']
            else:
                action['views'] = form_view
            action['res_id'] = pickings.id
        action['context'] = dict(self._context, default_site_project_id=self.id)
        action['domain'] = [('site_project_id', '=', self.id)]
        return action

    def action_view_out_picking(self):
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id("stock.action_picking_tree_outgoing")
        pickings = self.picking_out_ids
        if len(pickings) > 1:
            action['domain'] = [('id', 'in', pickings.ids)]
        elif pickings:
            form_view = [(self.env.ref('stock.view_picking_form').id, 'form')]
            if 'views' in action:
                action['views'] = form_view + [(state, view) for state, view in action['views'] if view != 'form']
            else:
                action['views'] = form_view
            action['res_id'] = pickings.id
        action['context'] = dict(self._context, default_site_project_id=self.id)
        action['domain'] = [('site_project_id', '=', self.id)]
        return action

    def action_view_dropship_picking(self):
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id("stock_dropshipping.action_picking_tree_dropship")
        pickings = self.picking_dropship_ids
        if len(pickings) > 1:
            action['domain'] = [('id', 'in', pickings.ids)]
        elif pickings:
            form_view = [(self.env.ref('stock_dropshipping.view_order_form_inherit_sale_stock').id, 'form')]
            if 'views' in action:
                action['views'] = form_view + [(state, view) for state, view in action['views'] if view != 'form']
            else:
                action['views'] = form_view
            action['res_id'] = pickings.id
        action['context'] = dict(self._context, default_site_project_id=self.id)
        action['domain'] = [('site_project_id', '=', self.id)]
        return action

    def action_view_internal_picking(self):
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id("stock.action_picking_tree_internal")
        pickings = self.picking_internal_ids
        if len(pickings) > 1:
            action['domain'] = [('id', 'in', pickings.ids)]
        elif pickings:
            form_view = [(self.env.ref('stock.view_picking_form').id, 'form')]
            if 'views' in action:
                action['views'] = form_view + [(state, view) for state, view in action['views'] if view != 'form']
            else:
                action['views'] = form_view
            action['res_id'] = pickings.id
        action['context'] = dict(self._context, default_site_project_id=self.id)
        action['domain'] = [('site_project_id', '=', self.id)]
        return action

    def action_view_all_picking(self):
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id("stock.action_picking_tree_all")
        action['context'] = dict(self._context, default_site_project_id=self.id, search_default_picking_type=True)
        action['domain'] = [('site_project_id', '=', self.id)]
        return action

    def _get_report_sale_orders(self):
        return self.sale_ids.filtered(lambda l: l.state != 'cancel')
