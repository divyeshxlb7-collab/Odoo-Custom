# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models

AVAILABLE_PRIORITIES = [
    ('0', 'Low'),
    ('1', 'Medium'),
    ('2', 'High'),
    ('3', 'Very High'),
]


class InquiryStage(models.Model):
    _name = "inquiry.stage"
    _description = "Inquiry Stages"
    _rec_name = 'name'
    _order = "sequence, id desc"

    @api.model
    def default_get(self, fields):
        """ As we have lots of default_team_id in context used to filter out
        leads and opportunities, we pop this key from default of stage creation.
        Otherwise stage will be created for a given team only which is not the
        standard behavior of stages. """
        if 'default_team_id' in self.env.context:
            ctx = dict(self.env.context)
            ctx.pop('default_team_id')
            self = self.with_context(ctx)
        return super(InquiryStage, self).default_get(fields)

    name = fields.Char('Stage Name', required=True)
    sequence = fields.Integer('Sequence', default=1, help="Used to order stages. Lower is better.")
    is_won = fields.Boolean('Is Won Stage?')
    requirements = fields.Text('Requirements', help="Enter the internal requirements for this stage (ex: Offer sent to customer). It will appear as a tooltip over the stage's name.")
    team_id = fields.Many2one('crm.team', string='Sales Team', ondelete="set null",
        help='Specific team that uses this stage. Other teams will not be able to see or use this stage.')
    fold = fields.Boolean('Folded in Pipeline',
        help='This stage is folded in the kanban view when there are no records in that stage to display.')
    company_id = fields.Many2one('res.company', required=True, readonly=True, default=lambda self: self.env.company)
    # This field for interface only
    team_count = fields.Integer('team_count', compute='_compute_team_count')
    state = fields.Selection([
        ('inquiry', 'Inquiry'), 
        ('design', 'Design'), 
        ('proposal', 'Proposal'),
        ('won', 'Won'),
        ('sale', 'Sales'),
        ("invoice", "Invoiced"),
        ('lost', 'Lost')], default='inquiry', required=True)

    _sql_constraints = [
        ('unique_state', 'UNIQUE(state, company_id)', 'The state must be unique for all inquiry stages.'),
    ]

    def _compute_team_count(self):
        self.team_count = self.env['crm.team'].search_count([])
