# Copyright 2026 OpenSynergy Indonesia
# Copyright 2026 PT. Simetri Sinergi Indonesia
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from odoo import fields, models


class DashboardDashboard(models.Model):
    """Represents a configurable dashboard: a named grid of items, each
    backed by a data source, optionally styled with a color scheme and
    restricted to a set of user groups. :meth:`get_dashboard_payload` is
    the single entry point the browser side calls to render one
    dashboard."""

    _name = "dashboard.dashboard"
    _inherit = [
        "mixin.master_data",
    ]
    _description = "Dashboard"

    _dashboard_dashboard_code_uniq = models.Constraint(
        "UNIQUE(code)",
        "Another dashboard with that code already exists.",
    )

    color_scheme_id = fields.Many2one(
        string="Color Scheme",
        comodel_name="dashboard.color_scheme",
        ondelete="restrict",
        help="Color scheme applied when rendering this dashboard. Left "
        "empty to render with the default browser styling.",
    )
    item_ids = fields.One2many(
        string="Items",
        comodel_name="dashboard.item",
        inverse_name="dashboard_id",
        help="Tiles placed on this dashboard.",
    )
    group_ids = fields.Many2many(
        string="Allowed Groups",
        comodel_name="res.groups",
        help="Groups allowed to view this dashboard. Leave empty to allow "
        "every user with the Dashboard User access right.",
    )

    def get_dashboard_payload(self):
        """Build the payload the browser uses to render this dashboard.

        This is the single entry point called from the browser side.

        :return: dict with keys ``id``, ``name``, ``color_scheme`` (result
            of :meth:`dashboard.color_scheme._prepare_css_variables`, or
            ``{}`` when :attr:`color_scheme_id` is empty) and ``items``
            (list of :meth:`dashboard.item._prepare_render_payload`
            results, ordered by ``sequence``).
        :rtype: dict
        """
        self.ensure_one()
        color_scheme = (
            self.color_scheme_id._prepare_css_variables()
            if self.color_scheme_id
            else {}
        )
        items = self.item_ids.sorted("sequence")
        return {
            "id": self.id,
            "name": self.name,
            "color_scheme": color_scheme,
            "items": [item._prepare_render_payload() for item in items],
        }

    def action_open_dashboard(self):
        for record in self.sudo():
            result = record._open_dashboard()
        return result

    def _open_dashboard(self):
        """Build the client action that opens this dashboard in the browser.

        :return: dict describing an ``ir.actions.client`` bound to the
            OWL client action registered under the
            ``ssi_dashboard.dashboard_view`` tag, with :attr:`id` passed
            through ``context['dashboard_id']`` so the browser side knows
            which dashboard to fetch via :meth:`get_dashboard_payload`.
        :rtype: dict
        """
        self.ensure_one()
        return {
            "type": "ir.actions.client",
            "tag": "ssi_dashboard.dashboard_view",
            "name": self.name,
            "context": {"dashboard_id": self.id},
        }
