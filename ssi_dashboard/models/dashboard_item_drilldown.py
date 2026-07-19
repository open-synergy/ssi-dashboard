# Copyright 2026 OpenSynergy Indonesia
# Copyright 2026 PT. Simetri Sinergi Indonesia
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from odoo import api, fields, models
from odoo.exceptions import UserError

GRANULARITY_SELECTION = [
    ("hour", "Hour"),
    ("day", "Day"),
    ("week", "Week"),
    ("month", "Month"),
    ("quarter", "Quarter"),
    ("year", "Year"),
]


class DashboardItemDrilldown(models.Model):
    """Represents one level of a ``dashboard.item``'s drill-down chain.

    Rows are ordered by :attr:`sequence`, lowest first: level ``1`` of
    :meth:`dashboard.item.fetch_drilldown_data` is the first row of
    :attr:`item_id`'s chain (``drilldown_ids[0]``), level ``2`` the second,
    and so on. An item whose chain is empty behaves exactly as it did
    before this model existed: clicking a value opens the list of records
    behind it straight away (``dashboard.item.action_open_records``)."""

    _name = "dashboard.item.drilldown"
    _description = "Dashboard Item Drill-Down Level"
    _order = "item_id, sequence"

    _item_id_sequence_uniq = models.Constraint(
        "UNIQUE(item_id, sequence)",
        "Another drill-down level with that 'Sequence' already exists on this item.",
    )

    item_id = fields.Many2one(
        string="# Item",
        comodel_name="dashboard.item",
        required=True,
        ondelete="cascade",
        help="Dashboard item this drill-down level belongs to.",
    )
    sequence = fields.Integer(
        default=10,
        help="Determines this level's position in 'Item''s drill-down "
        "chain, lowest first. Must be unique within the same 'Item'.",
    )
    field_id = fields.Many2one(
        comodel_name="ir.model.fields",
        required=True,
        ondelete="cascade",
        help="Field of 'Item''s data source model that rows are grouped "
        "by at this drill-down level. Must belong to the same model as "
        "'Item'.'Data Source'.'Model' — see "
        "'_check_field_id_belongs_to_data_source_model'. Deleting this "
        "field from its model deletes this drill-down level along with it.",
    )
    data_source_model_id = fields.Many2one(
        comodel_name="ir.model",
        related="item_id.data_source_id.model_id",
        string="# Data Source Model",
        help="Technical field, not stored. 'Model' configured on 'Item''s "
        "'Data Source', used only to filter 'Field''s selection in the "
        "form view.",
    )
    granularity = fields.Selection(
        selection=GRANULARITY_SELECTION,
        default="month",
        help="Granularity used to group 'Field' when it is a date or "
        "datetime field. Must be left empty for any other field type — "
        "see '_check_granularity_requires_date_field'.",
    )

    @api.onchange("field_id")
    def onchange_granularity(self):
        if not self.field_id or self.field_id.ttype not in ("date", "datetime"):
            self.granularity = False

    @api.constrains("field_id", "item_id")
    def _check_field_id_belongs_to_data_source_model(self):
        for record in self:
            model = record.item_id.data_source_id.model_id
            if not model or record.field_id.model_id != model:
                error_message = f"""
Context: Configure dashboard item drill-down level
Database ID: {record.id}
Problem: 'Field' does not belong to 'Item''s data source model
Solution: Choose a field of the model configured on 'Item''s 'Data Source'
"""
                raise UserError(error_message)

    @api.constrains("field_id", "granularity")
    def _check_granularity_requires_date_field(self):
        for record in self:
            if record.granularity and record.field_id.ttype not in (
                "date",
                "datetime",
            ):
                error_message = f"""
Context: Configure dashboard item drill-down level
Database ID: {record.id}
Problem: 'Granularity' is set but 'Field' is not a date/datetime field
Solution: Clear 'Granularity', or choose a date/datetime 'Field'
"""
                raise UserError(error_message)
