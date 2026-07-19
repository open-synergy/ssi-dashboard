# Copyright 2026 OpenSynergy Indonesia
# Copyright 2026 PT. Simetri Sinergi Indonesia
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from odoo import fields, models


class DashboardColorScheme(models.Model):
    """Represents a reusable palette that a dashboard can be styled with.
    Each palette is made of key/value color rows that are turned into CSS
    custom properties for the browser to consume when rendering a
    dashboard."""

    _name = "dashboard.color_scheme"
    _inherit = [
        "mixin.master_data",
    ]
    _description = "Dashboard Color Scheme"

    _dashboard_color_scheme_code_uniq = models.Constraint(
        "UNIQUE(code)",
        "Another color scheme with that code already exists.",
    )

    color_ids = fields.One2many(
        string="Colors",
        comodel_name="dashboard.color_scheme.color",
        inverse_name="color_scheme_id",
        help="Color rows that make up this palette.",
    )

    def _prepare_css_variables(self):
        """Build the CSS custom properties for this color scheme.

        :return: mapping of ``--ssi-dashboard-<key>`` to its CSS value,
            one entry per row in :attr:`color_ids`.
        :rtype: dict
        """
        self.ensure_one()
        return {f"--ssi-dashboard-{color.key}": color.value for color in self.color_ids}
