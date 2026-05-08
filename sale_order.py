import json

from markupsafe import Markup

from odoo import fields, models, api, _


class SaleOrder(models.Model):
    _inherit = "sale.order"

    inquiry_id = fields.Many2one('crm.inquiry', string='Inquiry')
    quotation_ids = fields.Many2many('crm.quotation', string='Quotations')
    quotation_ids_domain = fields.Char(default="[]", compute='_compute_quotation_ids_domain')
    boq_id = fields.Many2one('crm.boq', string='Bill of Quantity')
    site_project_id = fields.Many2one('site.project', 'Project Site', tracking=True)
    boq_domain = fields.Char(default="[]", compute='_compute_boq_domain')

    @api.depends('site_project_id')
    def _compute_display_name(self):
        orders = self.filtered(lambda l: l.site_project_id)
        for order in orders:
            name = order.name
            if order.site_project_id:
                name = f'{name} - {order.site_project_id.name}'
            order.display_name = name
        return super(SaleOrder, self - orders)._compute_display_name()

    @api.depends('inquiry_id', 'inquiry_id.sale_order_ids.state')
    def _compute_boq_domain(self):
        for order in self:
            domain = [('inquiry_id', '=', order.inquiry_id.id), ('state', '=', 'verify')]
            previous_boq = order.inquiry_id.sale_order_ids.filtered(
                lambda l: l.id != order.id and l.state != 'cancel').mapped('boq_id')
            if previous_boq:
                domain += [('id', 'not in', previous_boq.ids)]
            order.boq_domain = json.dumps(domain)

    @api.depends('inquiry_id', 'inquiry_id.sale_order_ids.state')
    def _compute_quotation_ids_domain(self):
        for order in self:
            domain = [('inquiry_id', '=', order.inquiry_id.id), ('state', '=', 'verify')]
            previous_quotations = order.inquiry_id.sale_order_ids.filtered(
                lambda l: l.id != order.id and l.state != 'cancel').mapped('quotation_ids')
            if previous_quotations:
                domain += [('id', 'not in', previous_quotations.ids)]
            order.quotation_ids_domain = json.dumps(domain)

    @api.onchange('boq_id')
    def _onchange_boq_id(self):
        if self.state != 'draft':
            return
        order_line_vals = [(5, 0, 0)]
        boq_line_ids = self.boq_id.line_ids
        boq_line_ids |= self.boq_id.material_line_ids
        for line in boq_line_ids:
            order_line_vals.append((0, 0, {
                'name': line.name,
                'product_id': line.product_id.id,
                'product_uom_qty': line.product_uom_qty,
                'product_uom': line.uom_id.id,
                'price_unit': line.price_unit,
                'tax_id': line.material_line_id.tax_id.ids if line.material_line_id else line.tax_id.ids,
                'discount': 0.0,  # we are not passing discount as it is already applied in the price_unit calculation
                'boq_line_id': line.id,
                'sequence': line.sequence,
            }))
        self.update({
            'site_project_id': self.boq_id.site_project_id.id,
            'order_line': order_line_vals,
        })

    def action_confirm(self):
        res = super().action_confirm()
        for order in self.filtered(
                lambda l: l.state == 'sale' and l.inquiry_id and l.inquiry_id.state != 'sale'):
            order.inquiry_id.move_to_sales()
            if order.inquiry_id.state == 'sale':
                order.inquiry_id.message_post(body=Markup(_(
                    'The stage is automatically changed to <b><i>%s</i></b> when the sale order <b><i>%s</i></b> is confirmed.') % (
                                                              order.inquiry_id.stage_id.name, order.name)))
        return res

    def _get_order_lines_to_report(self):
        res = super()._get_order_lines_to_report()
        if self.boq_id:
            return res.filtered(lambda l: l.product_cost_type != 'accessory')
        return res

    def _prepare_invoice(self):
        invoice_vals = super(SaleOrder, self)._prepare_invoice()
        if self.site_project_id:
            invoice_vals['site_project_id'] = self.site_project_id.id
        if self.boq_id:
            invoice_vals['boq_id'] = self.boq_id.id
        return invoice_vals

    def _get_invoiceable_lines(self, final=False):
        # we want to restrict creating invoice lines from sale order line having the related boq line cost type is accessory.
        # because, the price of the accessory is already included in the material line(Passing through line._prepare_invoice_line)
        res = super()._get_invoiceable_lines(final)
        accessory_lines = res.filtered(lambda l: l.boq_line_id and l.boq_line_id.cost_type == 'accessory')
        return res - accessory_lines


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    related_material_id = fields.Many2one('product.product', 'Related Material',
                                          domain=['|', ('product_cost_type', '=', 'product'),
                                                  ('product_cost_type', '=', False)])
    product_cost_type = fields.Selection(related='product_id.product_cost_type')
    boq_line_id = fields.Many2one('crm.boq.line', string='Boq Line')
    boq_price_unit = fields.Float(related='boq_line_id.boq_price_unit', store=True)
    quotation_line_id = fields.Many2one('crm.quotation.line', string='Quotation Line')
    jca_price = fields.Float(string='JCA Rate')

    @api.depends('state', 'boq_line_id')
    def _compute_product_uom_readonly(self):
        # OVERRIDE
        for line in self:
            # line.ids checks whether it's a new record not yet saved
            line.product_uom_readonly = (line.ids and line.state in ['sale', 'cancel']) or line.boq_line_id

    def _prepare_invoice_line(self, **optional_values):
        res = super()._prepare_invoice_line(**optional_values)
        if self.boq_line_id:
            res['boq_line_id'] = self.boq_line_id.id
            res['price_unit'] = self.boq_price_unit
            res['boq_price_unit'] = self.boq_price_unit
        return res

    def _prepare_procurement_group_vals(self):
        res = super()._prepare_procurement_group_vals()
        res['site_project_id'] = self.order_id.site_project_id.id
        return res

    # def _convert_to_tax_base_line_dict(self, **kwargs):
    #     """
    #     If the product has accessories related to it, the tax must be calculated :
    #         Tax amount = (Material Sub Price + All Accessories Sub Price) * Tax Percentage
    #     """
    #     self.ensure_one()
    #     res = super()._convert_to_tax_base_line_dict(**kwargs)
    #     if not self.boq_line_id:
    #         return res
    #     return self.env['account.tax']._convert_to_tax_base_line_dict(
    #         self,
    #         partner=self.order_id.partner_id,
    #         currency=self.order_id.currency_id,
    #         product=self.product_id,
    #         taxes=self.tax_id,
    #         price_unit=self.boq_line_id.boq_price_unit,
    #         quantity=self.product_uom_qty,
    #         discount=self.discount,
    #         price_subtotal=self.boq_line_id.boq_price_subtotal,
    #         **kwargs,
    #     )
