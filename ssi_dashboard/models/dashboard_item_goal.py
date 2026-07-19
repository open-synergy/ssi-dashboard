# Copyright 2026 OpenSynergy Indonesia
# Copyright 2026 PT. Simetri Sinergi Indonesia
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from odoo import api, fields, models
from odoo.exceptions import ValidationError


class DashboardItemGoal(models.Model):
    """Represents one dated target row of a ``dashboard.item`` whose
    ``goal_type`` is 'dated'. Each row states the target 'Value' that
    applies for the inclusive ``date_start``/``date_end`` range — see
    ``dashboard.item._get_goal_value``, which picks the first row whose
    range contains the date being looked up."""

    _name = "dashboard.item.goal"
    _description = "Dashboard Item Goal"
    _order = "item_id, date_start"

    _date_start_end_check = models.Constraint(
        "CHECK (date_start <= date_end)",
        "'Date Start' must not be after 'Date End'.",
    )

    item_id = fields.Many2one(
        string="# Item",
        comodel_name="dashboard.item",
        required=True,
        ondelete="cascade",
        help="Dashboard item this dated target belongs to.",
    )
    date_start = fields.Date(
        required=True,
        help="First date (inclusive) this target's 'Value' applies to.",
    )
    date_end = fields.Date(
        required=True,
        help="Last date (inclusive) this target's 'Value' applies to.",
    )
    value = fields.Float(
        required=True,
        default=0.0,
        help="Target value that applies for the 'Date Start'/'Date End' range.",
    )

    @api.constrains("item_id", "date_start", "date_end")
    def _check_date_range_overlap(self):
        for goal in self:
            siblings = goal.item_id.goal_ids - goal
            for sibling in siblings:
                overlaps = (
                    goal.date_start <= sibling.date_end
                    and sibling.date_start <= goal.date_end
                )
                if overlaps:
                    error_message = f"""
Context: Configure dashboard item goal
Database ID: {goal.id}
Problem: Date range ({goal.date_start} - {goal.date_end}) overlaps with \
another goal's date range ({sibling.date_start} - {sibling.date_end}) on the \
same item
Solution: Adjust 'Date Start'/'Date End' so no two goals on the same item \
have overlapping date ranges
"""
                    raise ValidationError(error_message)
