# Copyright 2026 OpenSynergy Indonesia
# Copyright 2026 PT. Simetri Sinergi Indonesia
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from odoo import fields, models


class DashboardColorSchemeColor(models.Model):
    """Represents a single CSS custom-property entry (key/value) that
    belongs to a dashboard color scheme. A color scheme is rendered by the
    browser as a set of ``--ssi-dashboard-<key>`` CSS variables built from
    the rows of this model."""

    _name = "dashboard.color_scheme.color"
    _description = "Dashboard Color Scheme - Color"
    _order = "color_scheme_id, key"

    _color_scheme_id_key_uniq = models.Constraint(
        "UNIQUE(color_scheme_id, key)",
        "Another color with that key already exists on this color scheme.",
    )

    color_scheme_id = fields.Many2one(
        string="# Color Scheme",
        comodel_name="dashboard.color_scheme",
        required=True,
        ondelete="cascade",
        help="Color scheme this color entry belongs to.",
    )
    key = fields.Char(
        required=True,
        help="CSS custom-property name fragment, appended to the "
        "'--ssi-dashboard-' prefix (e.g. 'primary' becomes "
        "'--ssi-dashboard-primary').",
    )
    value = fields.Char(
        required=True,
        help="CSS value assigned to the custom property (e.g. '#1f6feb').",
    )
