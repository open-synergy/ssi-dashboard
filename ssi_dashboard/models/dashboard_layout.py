# Copyright 2026 OpenSynergy Indonesia
# Copyright 2026 PT. Simetri Sinergi Indonesia
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from odoo import api, fields, models
from odoo.exceptions import ValidationError


class DashboardLayout(models.Model):
    """Represents one alternative arrangement of a dashboard's items —
    a named, orderable set of :attr:`position_ids` rows overriding a
    subset of :attr:`~dashboard.dashboard.item_ids`' coordinates. A
    dashboard with no layout at all (the state right after installing/
    updating this module) keeps rendering from each item's own base
    coordinates, see ``dashboard.dashboard.get_dashboard_payload``.

    Only one layout per dashboard may have :attr:`is_default` set — see
    :meth:`_check_single_default_layout` — that is the layout resolved
    when the dashboard is opened without an explicit ``layout_id``."""

    _name = "dashboard.layout"
    _description = "Dashboard Layout"
    _order = "dashboard_id, sequence"

    _dashboard_layout_dashboard_name_uniq = models.Constraint(
        "UNIQUE(dashboard_id, name)",
        "Another layout with that name already exists on this dashboard.",
    )

    dashboard_id = fields.Many2one(
        comodel_name="dashboard.dashboard",
        required=True,
        ondelete="cascade",
        help="Dashboard this alternate layout belongs to.",
    )
    name = fields.Char(
        required=True,
        help="Label shown for this layout in the layout picker.",
    )
    sequence = fields.Integer(
        default=10,
        help="Determines the display order of layouts in the layout picker.",
    )
    is_default = fields.Boolean(
        string="Default Layout",
        default=False,
        help="Layout resolved when the dashboard is opened without "
        "explicitly picking one (see 'get_dashboard_payload'). At most "
        "one layout of the same dashboard can have this set — see "
        "'_check_single_default_layout'.",
    )
    position_ids = fields.One2many(
        string="Positions",
        comodel_name="dashboard.layout.position",
        inverse_name="layout_id",
        help="Item coordinates specific to this layout. An item of this "
        "layout's dashboard with no row here still renders, using its "
        "own base coordinates instead — see 'dashboard.dashboard."
        "get_dashboard_payload'.",
    )

    @api.constrains("dashboard_id", "is_default")
    def _check_single_default_layout(self):
        # NOTE: backlog issue #50's 'Keputusan Desain' asks for the SSI
        # structured error message convention ("konvensi UserError
        # terstruktur SSI", see references/odoo-module-guidelines/
        # 10-error-messages.md), while its own 'Skenario Uji' expects
        # this exact violation to raise ValidationError. Both
        # dashboard.item (ValidationError) and this same
        # dashboard.dashboard module's own '_check_generate_menu_parent'
        # (UserError) already raise the identical structured format
        # under @api.constrains elsewhere in this codebase, so "UserError
        # terstruktur" reads as the message *format*, not the exception
        # *class*. Resolved in favor of the concrete, testable Skenario
        # Uji: ValidationError, structured message kept as specified.
        for layout in self:
            if not layout.is_default:
                continue
            siblings = layout.dashboard_id.layout_ids.filtered("is_default") - layout
            if siblings:
                error_message = f"""
Document Type: {layout._description}
Context: Configure dashboard layout
Database ID: {layout.id}
Problem: Another layout of the same dashboard ('{siblings[0].name}') is \
already the 'Default Layout'
Solution: Unset 'Default Layout' on '{siblings[0].name}' before enabling it \
here, or leave this layout non-default
"""
                raise ValidationError(error_message)
