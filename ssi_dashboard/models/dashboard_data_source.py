# Copyright 2026 OpenSynergy Indonesia
# Copyright 2026 PT. Simetri Sinergi Indonesia
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.tools.safe_eval import safe_eval


class DashboardDataSource(models.Model):
    """Represents a reusable data feed that dashboard items pull their
    numbers from. This core module only ships the 'orm' type, which reads
    an Odoo model through ``_read_group``. Extension modules add further
    types via ``selection_add`` on :attr:`type` and by implementing the
    matching ``_fetch_data_<type>`` method — see :meth:`_fetch_data`."""

    _name = "dashboard.data_source"
    _inherit = [
        "mixin.master_data",
    ]
    _description = "Dashboard Data Source"

    _dashboard_data_source_code_uniq = models.Constraint(
        "UNIQUE(code)",
        "Another data source with that code already exists.",
    )

    type = fields.Selection(
        selection=[
            ("orm", "Odoo Model"),
        ],
        required=True,
        default="orm",
        help="Kind of data feed. Extension modules add more choices via "
        "'selection_add' and must implement a matching "
        "'_fetch_data_<type>' method.",
    )
    model_id = fields.Many2one(
        comodel_name="ir.model",
        help="Odoo model to read data from. Only used when 'Type' is "
        "'Odoo Model' (orm).",
    )
    domain = fields.Text(
        help="Odoo domain (Python list syntax) applied when reading "
        "'Model'. Only used when 'Type' is 'Odoo Model' (orm).",
    )
    measure_field_id = fields.Many2one(
        comodel_name="ir.model.fields",
        ondelete="set null",
        domain="[('model_id', '=', model_id), "
        "('ttype', 'in', ['integer', 'float', 'monetary'])]",
        help="Numeric field of 'Model' that 'Aggregate' is computed on. "
        "Left empty, 'Aggregate' falls back to counting records.",
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
        default="count",
        help="Aggregation applied to 'Measure Field' (ignored when set to "
        "'Count', which counts records instead).",
    )
    group_by_field_id = fields.Many2one(
        comodel_name="ir.model.fields",
        ondelete="set null",
        domain="[('model_id', '=', model_id)]",
        help="Field of 'Model' that rows are grouped by. Left empty, "
        "'Aggregate' is computed over every matching record as one group.",
    )
    limit = fields.Integer(
        default=0,
        help="Maximum number of rows to return. 0 means no limit.",
    )

    @api.onchange("model_id")
    def onchange_measure_field_id(self):
        self.measure_field_id = False

    @api.onchange("model_id")
    def onchange_group_by_field_id(self):
        self.group_by_field_id = False

    def _fetch_data(self, item):
        """Fetch the raw data for a dashboard item.

        Dispatches to ``self._fetch_data_<type>(item)``. Extension modules
        implementing a new :attr:`type` only need to add that method —
        this dispatcher stays untouched.

        :param item: ``dashboard.item`` record requesting the data.
        :return: list of dict, the raw rows for the item to render.
        :rtype: list
        :raises UserError: when no ``_fetch_data_<type>`` method exists
            for :attr:`type`.
        """
        self.ensure_one()
        method_name = f"_fetch_data_{self.type}"
        method = getattr(self, method_name, None)
        if method is None:
            error_message = f"""
Document Type: {self._description}
Context: Fetch dashboard item data
Database ID: {self.id}
Problem: No data fetch implementation for data source type '{self.type}'
Solution: Install a module that implements {method_name}
"""
            raise UserError(error_message)
        return method(item)

    def _fetch_data_orm(self, item):
        """Fetch data for the 'orm' data source type.

        Reads :attr:`model_id` through ``_read_group`` filtered by
        :attr:`domain`. ``read_group`` is deprecated since 19.0 in favor
        of ``_read_group``/``formatted_read_group``; ``_read_group`` is
        used here and its tuple result is turned back into the list of
        dict this method's contract promises.

        :param item: ``dashboard.item`` record requesting the data.
        :return: list of dict, one per group returned by ``_read_group``.
        :rtype: list
        :raises UserError: when :attr:`model_id` is not configured.
        """
        self.ensure_one()
        if not self.model_id:
            error_message = f"""
Document Type: {self._description}
Context: Fetch dashboard item data
Database ID: {self.id}
Problem: Data source type is 'orm' but no target Model is configured
Solution: Set the Model field on this data source
"""
            raise UserError(error_message)
        domain = safe_eval(self.domain) if self.domain else []
        model = self.env[self.model_id.model].sudo()
        aggregates = ["__count"]
        rows = model._read_group(domain, groupby=[], aggregates=aggregates)
        return [dict(zip(aggregates, row, strict=True)) for row in rows]
