# Copyright 2026 OpenSynergy Indonesia
# Copyright 2026 PT. Simetri Sinergi Indonesia
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from odoo import api, fields, models
from odoo.exceptions import ValidationError


class DashboardItemColumn(models.Model):
    """Represents one column of a ``dashboard.item`` whose ``type`` is
    'list'. Replaces the hand-typed 'columns' JSON list that used to live
    in the item's ``config`` field (see
    ``ssi_dashboard_item_list/models/dashboard_item.py``,
    ``_prepare_render_payload_list``)."""

    _name = "dashboard.item.column"
    _description = "Dashboard Item List Column"
    _order = "item_id, sequence"

    _item_id_key_uniq = models.Constraint(
        "UNIQUE(item_id, key)",
        "Another column with that 'Key' already exists on this item.",
    )

    item_id = fields.Many2one(
        string="# Item",
        comodel_name="dashboard.item",
        required=True,
        ondelete="cascade",
        help="Dashboard item (of 'Type' 'List') this column belongs to.",
    )
    sequence = fields.Integer(
        default=10,
        help="Determines the display order of columns in the table.",
    )
    key = fields.Char(
        required=True,
        help="Name of the key on the item's fetched data row that this "
        "column reads its value from.",
    )
    name = fields.Char(
        required=True,
        help="Column header shown in the table.",
    )
    column_type = fields.Selection(
        selection=[
            ("text", "Text"),
            ("number", "Number"),
            ("deviation", "Deviation From Target"),
        ],
        default="text",
        required=True,
        help="How this column's value is formatted. 'Number' formats the "
        "raw value following the item's 'Number Format Config'. "
        "'Deviation From Target' subtracts the item's target for the "
        "row's date (see 'dashboard.item._get_goal_value') from 'Key''s "
        "numeric value, and requires the item's 'Goal Type' to not be "
        "'No Target'.",
    )

    @api.constrains("column_type", "item_id")
    def _check_column_type_deviation_requires_goal(self):
        """Reject a 'Deviation From Target' column on an item without a
        target, at the moment this column is (re)linked to that item —
        whether that happens through the item's own 'Columns' nested
        one2many or by creating/writing this model directly.

        Triggered on 'item_id' rather than 'item_id.goal_type': the
        symmetric case (an item's 'Goal Type' changing to 'No Target'
        while a 'Deviation From Target' column already exists on it) is
        covered by
        :meth:`dashboard.item._check_deviation_column_requires_goal`
        instead, since 'Goal Type' is that model's own field.
        """
        for column in self:
            if column.column_type != "deviation":
                continue
            if column.item_id.goal_type == "none":
                error_message = f"""
Context: Configure dashboard item list column
Database ID: {column.id}
Problem: 'Column Type' is set to 'Deviation From Target' but 'Goal Type' \
on item '{column.item_id.name}' is 'No Target'
Solution: Set 'Goal Type' to 'Fixed Value' or 'Dated Targets' on \
'{column.item_id.name}', or change 'Column Type' to something other than \
'Deviation From Target'
"""
                raise ValidationError(error_message)
