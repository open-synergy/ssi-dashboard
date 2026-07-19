# Copyright 2026 OpenSynergy Indonesia
# Copyright 2026 PT. Simetri Sinergi Indonesia
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
import datetime

import babel.dates

from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.tools import get_lang
from odoo.tools.safe_eval import safe_eval

GROUP_BY_DATE_FORMAT = {
    "hour": "HH:00 dd MMM yyyy",
    "day": "dd MMM yyyy",
    "week": "'W'w yyyy",
    "month": "MMMM yyyy",
    "quarter": "QQQ yyyy",
    "year": "yyyy",
}


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
    group_by_granularity = fields.Selection(
        selection=[
            ("hour", "Hour"),
            ("day", "Day"),
            ("week", "Week"),
            ("month", "Month"),
            ("quarter", "Quarter"),
            ("year", "Year"),
        ],
        default="month",
        help="Granularity used to group 'Group By Field' when it is a "
        "date or datetime field. Ignored for any other field type.",
    )
    group_by_field_is_date = fields.Boolean(
        compute="_compute_group_by_field_is_date",
        help="Technical field. True when 'Group By Field' is a date or "
        "datetime field, used to show/hide 'Group By Granularity' in the "
        "form view.",
    )
    limit = fields.Integer(
        default=0,
        help="Maximum number of rows to return. 0 means no limit.",
    )

    @api.depends("group_by_field_id.ttype")
    def _compute_group_by_field_is_date(self):
        for record in self:
            record.group_by_field_is_date = record.group_by_field_id.ttype in (
                "date",
                "datetime",
            )

    @api.onchange("model_id")
    def onchange_measure_field_id(self):
        self.measure_field_id = False

    @api.onchange("model_id")
    def onchange_group_by_field_id(self):
        self.group_by_field_id = False

    @api.onchange("group_by_field_id")
    def onchange_group_by_granularity(self):
        if not self.group_by_field_id or self.group_by_field_id.ttype not in (
            "date",
            "datetime",
        ):
            self.group_by_granularity = False

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

    def _prepare_groupby_spec(self):
        """Build the ``_read_group`` groupby specification for this data
        source, so extension modules can add further grouping dimensions
        without touching :meth:`_fetch_data_orm`.

        :return: list with zero or one string — ``"<field_name>:<granularity>"``
            when :attr:`group_by_field_id` is a date/datetime field,
            ``"<field_name>"`` for any other field type, or an empty list
            when :attr:`group_by_field_id` is not set.
        :rtype: list
        """
        self.ensure_one()
        if not self.group_by_field_id:
            return []
        field_name = self.group_by_field_id.name
        if self.group_by_field_id.ttype in ("date", "datetime"):
            granularity = self.group_by_granularity or "month"
            return [f"{field_name}:{granularity}"]
        return [field_name]

    def _prepare_group_key(self, group_value):
        """Normalize a raw ``_read_group`` groupby value into a plain key
        usable later as the base of a drill-down domain.

        :param group_value: raw value returned by ``_read_group`` for the
            groupby column — a recordset for relational fields, a
            ``date``/``datetime`` for temporal fields, or a plain scalar
            (possibly ``False``) for anything else.
        :return: ``False``, an ``int`` id (relational fields), or the raw
            scalar value unchanged.
        """
        self.ensure_one()
        if isinstance(group_value, models.BaseModel):
            return group_value.id
        return group_value

    def _prepare_group_label(self, group_value):
        """Build a human-readable label for a raw ``_read_group`` groupby
        value.

        :param group_value: raw value returned by ``_read_group`` for the
            groupby column, same shape as received by
            :meth:`_prepare_group_key`.
        :return: display string. ``"None"`` when the group has no value.
        :rtype: str
        """
        self.ensure_one()
        if isinstance(group_value, models.BaseModel):
            return group_value.sudo().display_name if group_value else "None"
        if not group_value:
            return "None"
        field = self.group_by_field_id
        if field.ttype in ("date", "datetime"):
            return self._format_group_by_date_label(group_value)
        if field.ttype == "selection":
            selection = (
                self.env[self.model_id.model]
                .fields_get([field.name])[field.name]
                .get("selection", [])
            )
            return dict(selection).get(group_value, str(group_value))
        return str(group_value)

    def _format_group_by_date_label(self, value):
        """Format a date/datetime groupby value according to
        :attr:`group_by_granularity`.

        :param value: ``date`` or ``datetime`` value returned by
            ``_read_group`` for a temporal groupby column.
        :return: locale-aware display string, e.g. ``"2024"`` for
            granularity ``year``.
        :rtype: str
        """
        self.ensure_one()
        granularity = self.group_by_granularity or "month"
        locale = get_lang(self.env).code
        date_format = GROUP_BY_DATE_FORMAT.get(
            granularity, GROUP_BY_DATE_FORMAT["month"]
        )
        if isinstance(value, datetime.datetime):
            return babel.dates.format_datetime(value, format=date_format, locale=locale)
        return babel.dates.format_date(value, format=date_format, locale=locale)

    def _fetch_data_orm(self, item):
        """Fetch data for the 'orm' data source type.

        Reads :attr:`model_id` through ``_read_group`` filtered by
        :attr:`domain`. ``read_group`` is deprecated since 19.0 in favor
        of ``_read_group``/``formatted_read_group``; ``_read_group`` is
        used here and its tuple result is turned back into the list of
        dict this method's contract promises.

        When :attr:`group_by_field_id` is set, each row is enriched with
        two extra keys: ``group_key`` (raw group value, for a future
        drill-down domain) and ``group_label`` (human-readable label). With
        no grouping field configured, behavior is unchanged: exactly one
        aggregate row without those two keys.

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
        groupby = self._prepare_groupby_spec()
        rows = model._read_group(domain, groupby=groupby, aggregates=aggregates)
        if not groupby:
            return [dict(zip(aggregates, row, strict=True)) for row in rows]
        result = []
        for row in rows:
            group_value, *aggregate_values = row
            row_dict = dict(zip(aggregates, aggregate_values, strict=True))
            row_dict["group_key"] = self._prepare_group_key(group_value)
            row_dict["group_label"] = self._prepare_group_label(group_value)
            result.append(row_dict)
        return result
