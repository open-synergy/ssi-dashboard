# Copyright 2026 OpenSynergy Indonesia
# Copyright 2026 PT. Simetri Sinergi Indonesia
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from odoo import api, fields, models
from odoo.exceptions import ValidationError


class DashboardLayoutPosition(models.Model):
    """Represents one item's coordinates on a specific
    ``dashboard.layout``. Meaning and range constraints on
    :attr:`column_start`/:attr:`row_start`/:attr:`column_width`/
    :attr:`row_height` are exactly the same as the fields of the same
    name on ``dashboard.item`` — see that model's own fields for the
    reasoning; this model only carries a layout-specific override, the
    base coordinates on ``dashboard.item`` itself are untouched."""

    _name = "dashboard.layout.position"
    _description = "Dashboard Layout Position"
    _order = "layout_id, item_id"

    _dashboard_layout_position_layout_item_uniq = models.Constraint(
        "UNIQUE(layout_id, item_id)",
        "This item already has a position on this layout.",
    )

    layout_id = fields.Many2one(
        comodel_name="dashboard.layout",
        required=True,
        ondelete="cascade",
        help="Layout this position row belongs to.",
    )
    item_id = fields.Many2one(
        comodel_name="dashboard.item",
        required=True,
        ondelete="cascade",
        help="Dashboard item this position row overrides the coordinates of.",
    )
    column_start = fields.Integer(
        default=0,
        help="Starting column of this item's tile on this layout's "
        "12-column grid, 0-indexed. Must be between 0 and 11, and "
        "'Column Start' plus 'Column Width' must not exceed 12.",
    )
    row_start = fields.Integer(
        default=0,
        help="Starting row of this item's tile on this layout's grid, 0-indexed.",
    )
    column_width = fields.Integer(
        default=4,
        help="Width of this item's tile on this layout, in grid columns "
        "out of 12. Must be between 1 and 12, and 'Column Start' plus "
        "'Column Width' must not exceed 12.",
    )
    row_height = fields.Integer(
        default=1,
        help="Height of this item's tile on this layout, in grid rows. "
        "Must be at least 1.",
    )

    @api.constrains("column_start")
    def _check_column_start_range(self):
        for position in self:
            if not 0 <= position.column_start <= 11:
                error_message = f"""
Context: Configure dashboard layout position
Database ID: {position.id}
Problem: 'Column Start' is set to {position.column_start}, which is \
outside the allowed range of 0 to 11
Solution: Set 'Column Start' to a value between 0 and 11
"""
                raise ValidationError(error_message)

    @api.constrains("column_width")
    def _check_column_width_range(self):
        for position in self:
            if not 1 <= position.column_width <= 12:
                error_message = f"""
Context: Configure dashboard layout position
Database ID: {position.id}
Problem: 'Column Width' is set to {position.column_width}, which is \
outside the allowed range of 1 to 12
Solution: Set 'Column Width' to a value between 1 and 12
"""
                raise ValidationError(error_message)

    @api.constrains("column_start", "column_width")
    def _check_column_start_width_within_grid(self):
        for position in self:
            if position.column_start + position.column_width > 12:
                error_message = f"""
Context: Configure dashboard layout position
Database ID: {position.id}
Problem: 'Column Start' ({position.column_start}) plus 'Column Width' \
({position.column_width}) exceeds the layout's 12-column grid
Solution: Reduce 'Column Start' or 'Column Width' so their sum does \
not exceed 12
"""
                raise ValidationError(error_message)

    @api.constrains("row_height")
    def _check_row_height_minimum(self):
        for position in self:
            if position.row_height < 1:
                error_message = f"""
Context: Configure dashboard layout position
Database ID: {position.id}
Problem: 'Row Height' is set to {position.row_height}, which is below \
the minimum of 1
Solution: Set 'Row Height' to 1 or more
"""
                raise ValidationError(error_message)
