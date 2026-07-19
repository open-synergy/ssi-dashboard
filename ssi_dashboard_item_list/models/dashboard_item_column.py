# Copyright 2026 OpenSynergy Indonesia
# Copyright 2026 PT. Simetri Sinergi Indonesia
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from odoo import fields, models


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
