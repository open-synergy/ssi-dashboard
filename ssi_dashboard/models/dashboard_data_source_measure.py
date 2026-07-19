# Copyright 2026 OpenSynergy Indonesia
# Copyright 2026 PT. Simetri Sinergi Indonesia
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from odoo import api, fields, models
from odoo.exceptions import ValidationError


class DashboardDataSourceMeasure(models.Model):
    """Represents one numeric measure computed by a
    ``dashboard.data_source`` of type 'orm'. A data source with at least
    one row here reports one aggregate value per row for each measure,
    keyed by that measure's 'Name', instead of the single value built
    from its own 'Measure Field' / 'Aggregate' pair — see
    ``dashboard.data_source._prepare_aggregate_spec``."""

    _name = "dashboard.data_source.measure"
    _description = "Dashboard Data Source - Measure"
    _order = "data_source_id, sequence"

    _data_source_id_name_uniq = models.Constraint(
        "UNIQUE(data_source_id, name)",
        "Another measure with that name already exists on this data source.",
    )

    data_source_id = fields.Many2one(
        string="# Data Source",
        comodel_name="dashboard.data_source",
        required=True,
        ondelete="cascade",
        help="Data source this measure belongs to.",
    )
    sequence = fields.Integer(
        default=10,
        help="Determines the order this measure is listed in, and so its "
        "position among the aggregate values built per row.",
    )
    field_id = fields.Many2one(
        comodel_name="ir.model.fields",
        ondelete="restrict",
        help="Numeric field of the data source's 'Model' that 'Aggregate' "
        "is computed on. Left empty is only valid when 'Aggregate' is "
        "'Count'.",
    )
    aggregate = fields.Selection(
        selection=[
            ("count", "Count"),
            ("sum", "Sum"),
            ("avg", "Average"),
            ("min", "Minimum"),
            ("max", "Maximum"),
        ],
        required=True,
        default="sum",
        help="Aggregation applied to 'Field' (ignored when set to "
        "'Count', which counts records instead).",
    )
    name = fields.Char(
        required=True,
        help="Label of this measure. Used as the key its aggregate value "
        "is stored under in each row of data returned by the data source.",
    )

    @api.constrains("aggregate", "field_id")
    def _check_field_id(self):
        for measure in self:
            if measure.aggregate != "count" and not measure.field_id:
                error_message = f"""
Context: Configure dashboard data source measure
Database ID: {measure.id}
Problem: 'Aggregate' is set to '{measure.aggregate}' but 'Field' is empty
Solution: Set 'Field' or change 'Aggregate' to 'Count'
"""
                raise ValidationError(error_message)
            if measure.field_id and measure.field_id.ttype not in (
                "integer",
                "float",
                "monetary",
            ):
                error_message = f"""
Context: Configure dashboard data source measure
Database ID: {measure.id}
Problem: 'Field' ({measure.field_id.name}) is not a numeric field
Solution: Select a field of type Integer, Float, or Monetary
"""
                raise ValidationError(error_message)
