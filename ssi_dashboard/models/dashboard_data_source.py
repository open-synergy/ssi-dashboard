# Copyright 2026 OpenSynergy Indonesia
# Copyright 2026 PT. Simetri Sinergi Indonesia
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
import datetime

import babel.dates
import pytz
from babel import Locale
from dateutil.relativedelta import relativedelta

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError
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

DATE_RANGE_SELECTION = [
    ("all_time", "All Time"),
    ("today", "Today"),
    ("yesterday", "Yesterday"),
    ("this_week", "This Week"),
    ("last_week", "Last Week"),
    ("next_week", "Next Week"),
    ("this_month", "This Month"),
    ("last_month", "Last Month"),
    ("next_month", "Next Month"),
    ("this_quarter", "This Quarter"),
    ("last_quarter", "Last Quarter"),
    ("next_quarter", "Next Quarter"),
    ("this_year", "This Year"),
    ("last_year", "Last Year"),
    ("next_year", "Next Year"),
    ("week_to_date", "Week to Date"),
    ("month_to_date", "Month to Date"),
    ("quarter_to_date", "Quarter to Date"),
    ("year_to_date", "Year to Date"),
    ("last_7_days", "Last 7 Days"),
    ("last_30_days", "Last 30 Days"),
    ("last_90_days", "Last 90 Days"),
    ("last_365_days", "Last 365 Days"),
    ("past_till_now", "Past Till Now"),
    ("past_excluding_today", "Past Excluding Today"),
    ("future_starting_now", "Future Starting Now"),
    ("future_starting_tomorrow", "Future Starting Tomorrow"),
    ("custom", "Custom"),
]


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
    sub_group_by_field_id = fields.Many2one(
        comodel_name="ir.model.fields",
        ondelete="set null",
        domain="[('model_id', '=', model_id)]",
        help="Optional second field of 'Model' that rows are further "
        "grouped by, after 'Group By Field' — needed for chart series "
        "that break the same rows down by a second dimension (e.g. team "
        "within country). Requires 'Group By Field' to be set and must "
        "be different from it. Left empty, rows carry a single "
        "dimension exactly as before this field existed.",
    )
    sub_group_by_granularity = fields.Selection(
        selection=[
            ("hour", "Hour"),
            ("day", "Day"),
            ("week", "Week"),
            ("month", "Month"),
            ("quarter", "Quarter"),
            ("year", "Year"),
        ],
        default="month",
        help="Granularity used to group 'Sub Group By Field' when it is "
        "a date or datetime field. Ignored for any other field type.",
    )
    sub_group_by_field_is_date = fields.Boolean(
        compute="_compute_sub_group_by_field_is_date",
        help="Technical field. True when 'Sub Group By Field' is a date "
        "or datetime field, used to show/hide 'Sub Group By Granularity' "
        "in the form view.",
    )
    limit = fields.Integer(
        default=0,
        help="Maximum number of rows to return, applied after 'Sort By' "
        "sorts the rows. 0 means no limit. Negative values are rejected.",
    )
    sort_by = fields.Selection(
        selection=[
            ("none", "Unsorted"),
            ("label", "Group Label"),
            ("measure", "Measure Value"),
        ],
        required=True,
        default="none",
        help="Field rows are sorted by before 'Limit' cuts them off. "
        "'Group Label' sorts by the row's group label. 'Measure Value' "
        "sorts by the first measure in 'Measures' order, or the single "
        "measure built from 'Measure Field' / 'Aggregate' when "
        "'Measures' is empty. Ignored when set to 'Unsorted'.",
    )
    sort_order = fields.Selection(
        selection=[
            ("asc", "Ascending"),
            ("desc", "Descending"),
        ],
        required=True,
        default="desc",
        help="Sort direction applied when 'Sort By' is not 'Unsorted'. "
        "Ignored when 'Sort By' is 'Unsorted'.",
    )
    fill_temporal = fields.Boolean(
        default=False,
        help="When enabled and 'Group By Field' is a date/datetime field, "
        "empty periods between the smallest and largest period with data "
        "are added as zero-value rows, so a time series chart does not "
        "break its line. Silently ignored when 'Group By Field' is not a "
        "date/datetime field.",
    )
    measure_ids = fields.One2many(
        string="Measures",
        comodel_name="dashboard.data_source.measure",
        inverse_name="data_source_id",
        help="Measures computed per row. When at least one row is set "
        "here, it is used instead of 'Measure Field' / 'Aggregate' and "
        "each row of data carries one value per measure, keyed by that "
        "measure's 'Name'. Left empty, 'Measure Field' / 'Aggregate' are "
        "used as a single measure, keeping older data sources working "
        "unchanged.",
    )
    date_field_id = fields.Many2one(
        comodel_name="ir.model.fields",
        ondelete="set null",
        domain="[('model_id', '=', model_id), ('ttype', 'in', ['date', 'datetime'])]",
        help="Date or datetime field of 'Model' that 'Date Range' is "
        "applied on. Left empty, no date filtering is applied regardless "
        "of 'Date Range'.",
    )
    date_range = fields.Selection(
        selection=DATE_RANGE_SELECTION,
        required=True,
        default="all_time",
        help="Predefined period the data is filtered on, computed in the "
        "current user's timezone. 'All Time' applies no date filtering. "
        "'Custom' uses 'Date Start' / 'Date End' instead.",
    )
    date_start = fields.Date(
        help="Custom period start (inclusive). Only used when 'Date "
        "Range' is 'Custom'.",
    )
    date_end = fields.Date(
        help="Custom period end (inclusive). Only used when 'Date Range' is 'Custom'.",
    )
    comparison = fields.Selection(
        selection=[
            ("none", "No Comparison"),
            ("previous_period", "Previous Period"),
            ("previous_year", "Same Period Previous Year"),
        ],
        required=True,
        default="none",
        help="Comparison range computed alongside the current period and "
        "returned separately (see 'comparison_data'). 'Previous Period' "
        "shifts the current range (from 'Date Range') backward by its "
        "own duration. 'Same Period Previous Year' shifts the current "
        "range backward by 'Comparison Year Count' years, keeping the "
        "same start/end day. Requires 'Date Field' to be set.",
    )
    comparison_year_count = fields.Integer(
        default=1,
        help="Number of years back to compare against, one comparison "
        "range per year. Only used when 'Comparison' is 'Same Period "
        "Previous Year'. Must be between 1 and 5.",
    )

    @api.depends("group_by_field_id.ttype")
    def _compute_group_by_field_is_date(self):
        for record in self:
            record.group_by_field_is_date = record.group_by_field_id.ttype in (
                "date",
                "datetime",
            )

    @api.depends("sub_group_by_field_id.ttype")
    def _compute_sub_group_by_field_is_date(self):
        for record in self:
            record.sub_group_by_field_is_date = record.sub_group_by_field_id.ttype in (
                "date",
                "datetime",
            )

    @api.constrains("group_by_field_id", "sub_group_by_field_id")
    def _check_sub_group_by_field_id(self):
        for record in self:
            if not record.sub_group_by_field_id:
                continue
            if not record.group_by_field_id:
                error_message = f"""
Context: Configure dashboard data source sub group by field
Database ID: {record.id}
Problem: 'Sub Group By Field' is set but 'Group By Field' is empty
Solution: Set 'Group By Field' first, or clear 'Sub Group By Field'
"""
                raise ValidationError(error_message)
            if record.sub_group_by_field_id == record.group_by_field_id:
                error_message = f"""
Context: Configure dashboard data source sub group by field
Database ID: {record.id}
Problem: 'Sub Group By Field' is the same as 'Group By Field'
Solution: Choose a different field for 'Sub Group By Field', or clear it
"""
                raise ValidationError(error_message)

    @api.constrains("domain", "model_id")
    def _check_domain(self):
        for record in self:
            try:
                domain = record._prepare_domain()
            except Exception as error:
                error_message = f"""
Context: Configure dashboard data source domain
Database ID: {record.id}
Problem: 'Domain' cannot be evaluated as a domain expression
Solution: Fix the domain syntax. Original error: {error}
"""
                raise ValidationError(error_message) from error
            if not isinstance(domain, list):
                error_message = f"""
Context: Configure dashboard data source domain
Database ID: {record.id}
Problem: 'Domain' does not evaluate to a list
Solution: Write 'Domain' as a Python list of domain tuples/leaves
"""
                raise ValidationError(error_message)
            if not record.model_id:
                continue
            try:
                record.env[record.model_id.model].sudo().search_count(domain, limit=0)
            except Exception as error:
                error_message = f"""
Context: Configure dashboard data source domain
Database ID: {record.id}
Problem: 'Domain' is not valid for Model '{record.model_id.name}'
Solution: Fix 'Domain' so it only refers to fields that exist on \
'{record.model_id.name}'. Original error: {error}
"""
                raise ValidationError(error_message) from error

    @api.constrains("limit")
    def _check_limit(self):
        for record in self:
            if record.limit < 0:
                error_message = f"""
Context: Configure dashboard data source limit
Database ID: {record.id}
Problem: 'Limit' ({record.limit}) is negative
Solution: Set 'Limit' to zero (no limit) or a positive number
"""
                raise ValidationError(error_message)

    @api.constrains("date_range", "date_start", "date_end")
    def _check_date_range_custom(self):
        for record in self:
            if record.date_range != "custom":
                continue
            if not record.date_start or not record.date_end:
                error_message = f"""
Context: Configure dashboard data source date range
Database ID: {record.id}
Problem: 'Date Range' is set to 'Custom' but 'Date Start' or 'Date End' \
is empty
Solution: Set both 'Date Start' and 'Date End', or change 'Date Range' \
to another value
"""
                raise ValidationError(error_message)
            if record.date_start > record.date_end:
                error_message = f"""
Context: Configure dashboard data source date range
Database ID: {record.id}
Problem: 'Date Start' ({record.date_start}) is after 'Date End' \
({record.date_end})
Solution: Set 'Date Start' to a date on or before 'Date End'
"""
                raise ValidationError(error_message)

    @api.constrains("comparison_year_count")
    def _check_comparison_year_count(self):
        for record in self:
            if not 1 <= record.comparison_year_count <= 5:
                error_message = f"""
Context: Configure dashboard data source comparison
Database ID: {record.id}
Problem: 'Comparison Year Count' ({record.comparison_year_count}) is out \
of range
Solution: Set 'Comparison Year Count' between 1 and 5
"""
                raise ValidationError(error_message)

    @api.constrains("comparison", "date_field_id")
    def _check_comparison_date_field_id(self):
        for record in self:
            if record.comparison == "none":
                continue
            if not record.date_field_id:
                error_message = f"""
Context: Configure dashboard data source comparison
Database ID: {record.id}
Problem: 'Comparison' is set to '{record.comparison}' but 'Date Field' \
is empty
Solution: Set 'Date Field', or change 'Comparison' back to 'No Comparison'
"""
                raise ValidationError(error_message)

    @api.onchange("model_id")
    def onchange_measure_field_id(self):
        self.measure_field_id = False

    @api.onchange("model_id")
    def onchange_date_field_id(self):
        self.date_field_id = False

    @api.onchange("date_range")
    def onchange_date_start(self):
        if self.date_range != "custom":
            self.date_start = False

    @api.onchange("date_range")
    def onchange_date_end(self):
        if self.date_range != "custom":
            self.date_end = False

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

    @api.onchange("group_by_field_id")
    def onchange_sub_group_by_field_id(self):
        if not self.group_by_field_id:
            self.sub_group_by_field_id = False

    @api.onchange("comparison")
    def onchange_comparison_year_count(self):
        if self.comparison != "previous_year":
            self.comparison_year_count = 1

    @api.onchange("sub_group_by_field_id")
    def onchange_sub_group_by_granularity(self):
        if not self.sub_group_by_field_id or self.sub_group_by_field_id.ttype not in (
            "date",
            "datetime",
        ):
            self.sub_group_by_granularity = False

    def _fetch_data(self, item, active_filters=None, extra_domain=None):
        """Fetch the raw data for a dashboard item.

        Dispatches to ``self._fetch_data_<type>(item)``. Extension modules
        implementing a new :attr:`type` only need to add that method —
        this dispatcher stays untouched.

        Neither :attr:`active_filters` nor ``extra_domain`` is passed as a
        positional/keyword argument to ``_fetch_data_<type>`` — that would
        break every extension module's existing
        ``_fetch_data_<type>(self, item)`` signature. Instead both travel
        through context keys (``dashboard_active_filters``,
        ``dashboard_drilldown_extra_domain``), so only
        :meth:`_fetch_data_orm` (which reads them back via
        :meth:`_prepare_filter_domain`/:meth:`_prepare_date_domain`/
        :meth:`_prepare_drilldown_extra_domain`) needs to know about them;
        any other ``_fetch_data_<type>`` keeps working completely
        unmodified.

        :param item: ``dashboard.item`` record requesting the data.
        :param active_filters: resolved 'active_filters' dict, as built
            by ``dashboard.dashboard._resolve_active_filters`` — carries
            ``filter_ids``, ``date_start``, ``date_end``. ``None`` (the
            default) applies no filter/date override, keeping calls made
            before this argument existed working unchanged.
        :type active_filters: dict or None
        :param extra_domain: extra domain ANDed in front of the domain
            :meth:`_fetch_data_orm` would otherwise build on its own —
            used by ``dashboard.item.fetch_drilldown_data`` to narrow a
            read down to the branch of the drill-down chain being
            explored (its own ``path`` argument). Never trusted to
            replace this data source's own domain/date/filter
            contributions, only to narrow them further — see
            :meth:`_prepare_drilldown_extra_domain`. ``None`` (the
            default) contributes nothing, keeping calls made before this
            argument existed working unchanged.
        :type extra_domain: list or None
        :return: list of dict, the raw rows for the item to render.
        :rtype: list
        :raises UserError: when no ``_fetch_data_<type>`` method exists
            for :attr:`type`.
        """
        self.ensure_one()
        method_name = f"_fetch_data_{self.type}"
        record = self.with_context(
            dashboard_active_filters=active_filters,
            dashboard_drilldown_extra_domain=extra_domain,
        )
        method = getattr(record, method_name, None)
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

    def _prepare_drilldown_extra_domain(self):
        """Build the domain fragment contributed by an in-progress
        drill-down navigation, read back from the
        ``dashboard_drilldown_extra_domain`` context key set by
        :meth:`_fetch_data`.

        Not trusted as-is beyond being ANDed onto the rest of
        :meth:`_fetch_data_orm`'s own domain (:attr:`domain`,
        :meth:`_prepare_date_domain`, :meth:`_prepare_filter_domain`):
        this only ever narrows the result down further, it can never
        widen it — see ``dashboard.item.fetch_drilldown_data``.

        :return: the ``dashboard_drilldown_extra_domain`` context value
            when it is a ``list``; ``[]`` otherwise (including when the
            context key is absent, e.g. every call made before drill-down
            existed).
        :rtype: list
        """
        self.ensure_one()
        extra_domain = self.env.context.get("dashboard_drilldown_extra_domain")
        return extra_domain if isinstance(extra_domain, list) else []

    def _prepare_groupby_spec(self):
        """Build the ``_read_group`` groupby specification for this data
        source, so extension modules can add further grouping dimensions
        without touching :meth:`_fetch_data_orm`.

        :return: list with zero, one, or two strings —
            ``"<field_name>:<granularity>"`` for a date/datetime field,
            ``"<field_name>"`` for any other field type. Empty when
            :attr:`group_by_field_id` is not set. The first item, when
            present, always comes from :attr:`group_by_field_id`; a
            second item, from :attr:`sub_group_by_field_id`, is only
            added when that field is set — so the first dimension stays
            the main axis.
        :rtype: list
        """
        self.ensure_one()
        if not self.group_by_field_id:
            return []
        spec = [
            self._prepare_groupby_spec_one(
                self.group_by_field_id, self.group_by_granularity
            )
        ]
        if self.sub_group_by_field_id:
            spec.append(
                self._prepare_groupby_spec_one(
                    self.sub_group_by_field_id, self.sub_group_by_granularity
                )
            )
        return spec

    def _prepare_groupby_spec_one(self, field, granularity):
        """Build a single ``_read_group`` groupby spec string for one
        field, shared by :meth:`_prepare_groupby_spec` for both the
        primary and the sub grouping dimension.

        :param field: ``ir.model.fields`` record the groupby spec is
            built for (:attr:`group_by_field_id` or
            :attr:`sub_group_by_field_id`).
        :param granularity: granularity to use when ``field`` is a
            date/datetime field (:attr:`group_by_granularity` or
            :attr:`sub_group_by_granularity`).
        :return: ``"<field_name>:<granularity>"`` for a date/datetime
            field, ``"<field_name>"`` otherwise.
        :rtype: str
        """
        self.ensure_one()
        field_name = field.name
        if field.ttype in ("date", "datetime"):
            granularity = granularity or "month"
            return f"{field_name}:{granularity}"
        return field_name

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

    def _prepare_group_condition_domain(self, group_value, field, granularity):
        """Build the domain leaf(s) that isolate the record(s) behind one
        grouping dimension's raw value, used by :meth:`_fetch_data_orm`/
        :meth:`_fill_temporal_rows` to build each row's ``row_domain``.

        :param group_value: raw value returned by ``_read_group`` for the
            groupby column (or a bucket-start ``date`` built by
            :meth:`_fill_temporal_rows` for a zero-value row), same shape
            as received by :meth:`_prepare_group_key`.
        :param field: ``ir.model.fields`` record the groupby column was
            built from (:attr:`group_by_field_id` or
            :attr:`sub_group_by_field_id`).
        :param granularity: granularity used when ``field`` is a
            date/datetime field (:attr:`group_by_granularity` or
            :attr:`sub_group_by_granularity`).
        :return: list of domain tuples, meant to be ANDed (implicit
            ``&``) with the rest of a row's ``row_domain``. A date range
            (two tuples) for a date/datetime ``field`` — see
            :meth:`_prepare_group_condition_domain_date`; a single
            equality tuple otherwise (unwrapping a relational
            ``group_value`` to its id first).
        :rtype: list
        """
        self.ensure_one()
        if field.ttype in ("date", "datetime"):
            return self._prepare_group_condition_domain_date(
                group_value, field, granularity
            )
        if isinstance(group_value, models.BaseModel):
            group_value = group_value.id
        return [(field.name, "=", group_value)]

    def _prepare_group_condition_domain_date(self, group_value, field, granularity):
        """Build the date-range domain leaves behind
        :meth:`_prepare_group_condition_domain` for a date/datetime
        ``field``.

        ``group_value`` (or the bucket-start date passed in by
        :meth:`_fill_temporal_rows`) is floored to its own bucket start
        with :meth:`_temporal_bucket_start` — a no-op when it is already
        a bucket start, as ``_read_group`` already returns for a real
        row — and the upper bound is the start of the *next* bucket
        (:meth:`_temporal_bucket_next`), so the range is exactly the
        half-open period ``_read_group`` grouped that row from. Both
        bounds go through :meth:`_date_range_bound_to_field_value` so a
        'datetime' ``field`` gets the same local-timezone-to-UTC
        conversion :meth:`_prepare_date_domain` applies elsewhere.

        :param group_value: raw ``date``/``datetime`` group value, or
            ``False``/``None`` for an empty group.
        :param field: ``ir.model.fields`` record, 'date' or 'datetime'
            typed.
        :param granularity: granularity to bucket by, one of
            :attr:`group_by_granularity`'s values. Falls back to
            ``month`` when falsy, same as :meth:`_prepare_groupby_spec_one`.
        :return: list of domain tuples. A single ``(field_name, "=",
            False)`` when ``group_value`` is empty; otherwise two
            tuples, the half-open bucket range.
        :rtype: list
        """
        self.ensure_one()
        field_name = field.name
        if not group_value:
            return [(field_name, "=", False)]
        is_datetime = field.ttype == "datetime"
        granularity = granularity or "month"
        bucket_date = (
            group_value.date()
            if isinstance(group_value, datetime.datetime)
            else group_value
        )
        bucket_start = self._temporal_bucket_start(bucket_date, granularity)
        bucket_next = self._temporal_bucket_next(bucket_start, granularity)
        return [
            (
                field_name,
                ">=",
                self._date_range_bound_to_field_value(
                    bucket_start, is_datetime, end_of_day=False
                ),
            ),
            (
                field_name,
                "<",
                self._date_range_bound_to_field_value(
                    bucket_next, is_datetime, end_of_day=False
                ),
            ),
        ]

    def _prepare_group_label(self, group_value):
        """Build a human-readable label for a raw ``_read_group`` groupby
        value of the primary grouping dimension (:attr:`group_by_field_id`).

        :param group_value: raw value returned by ``_read_group`` for the
            groupby column, same shape as received by
            :meth:`_prepare_group_key`.
        :return: display string. ``"None"`` when the group has no value.
        :rtype: str
        """
        self.ensure_one()
        return self._prepare_group_label_for_field(
            group_value, self.group_by_field_id, self.group_by_granularity
        )

    def _prepare_sub_group_label(self, group_value):
        """Build a human-readable label for a raw ``_read_group`` groupby
        value of the second grouping dimension
        (:attr:`sub_group_by_field_id`). Construction rules are exactly
        the same as :meth:`_prepare_group_label`, only reading the sub
        group's field/granularity instead of the primary one's.

        :param group_value: raw value returned by ``_read_group`` for the
            sub groupby column, same shape as received by
            :meth:`_prepare_group_key`.
        :return: display string. ``"None"`` when the group has no value.
        :rtype: str
        """
        self.ensure_one()
        return self._prepare_group_label_for_field(
            group_value, self.sub_group_by_field_id, self.sub_group_by_granularity
        )

    def _prepare_group_label_for_field(self, group_value, field, granularity):
        """Shared implementation behind :meth:`_prepare_group_label` and
        :meth:`_prepare_sub_group_label`, parametrized by which field/
        granularity pair to read metadata from.

        :param group_value: raw value returned by ``_read_group`` for the
            groupby column, same shape as received by
            :meth:`_prepare_group_key`.
        :param field: ``ir.model.fields`` record the groupby column was
            built from (:attr:`group_by_field_id` or
            :attr:`sub_group_by_field_id`).
        :param granularity: granularity to use when ``field`` is a
            date/datetime field (:attr:`group_by_granularity` or
            :attr:`sub_group_by_granularity`).
        :return: display string. ``"None"`` when the group has no value.
        :rtype: str
        """
        self.ensure_one()
        if isinstance(group_value, models.BaseModel):
            return group_value.sudo().display_name if group_value else "None"
        if not group_value:
            return "None"
        if field.ttype in ("date", "datetime"):
            return self._format_group_by_date_label_for_granularity(
                group_value, granularity
            )
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
        return self._format_group_by_date_label_for_granularity(
            value, self.group_by_granularity
        )

    def _format_group_by_date_label_for_granularity(self, value, granularity):
        """Shared implementation behind :meth:`_format_group_by_date_label`,
        parametrized by which granularity to format with, so the primary
        and the sub grouping dimension can each keep their own
        :attr:`group_by_granularity` / :attr:`sub_group_by_granularity`.

        :param value: ``date`` or ``datetime`` value returned by
            ``_read_group`` for a temporal groupby column.
        :param granularity: one of :attr:`group_by_granularity`'s values.
        :return: locale-aware display string, e.g. ``"2024"`` for
            granularity ``year``.
        :rtype: str
        """
        self.ensure_one()
        granularity = granularity or "month"
        locale = get_lang(self.env).code
        date_format = GROUP_BY_DATE_FORMAT.get(
            granularity, GROUP_BY_DATE_FORMAT["month"]
        )
        if isinstance(value, datetime.datetime):
            return babel.dates.format_datetime(value, format=date_format, locale=locale)
        return babel.dates.format_date(value, format=date_format, locale=locale)

    def _postprocess_rows(self, rows, domain=None):
        """Apply :attr:`fill_temporal`, then :attr:`sort_by`/
        :attr:`sort_order`, then :attr:`limit` to the raw rows built by a
        ``_fetch_data_<type>`` method — always in that order, so a chart
        sees empty periods filled in before it is sorted and cut down to
        size.

        Not specific to the 'orm' type: every step here only reads
        fields declared on :class:`DashboardDataSource` itself, so any
        extension module implementing another ``_fetch_data_<type>`` can
        call this as the last step of its own method too.

        :param rows: raw rows, as built by a ``_fetch_data_<type>``
            method.
        :type rows: list
        :param domain: base domain the rows were read with, passed
            through to :meth:`_fill_temporal_rows` so the zero-value
            rows it may add also carry a ``row_domain`` key. ``None``
            (the default) leaves those zero-value rows without
            ``row_domain``, keeping any caller that does not pass this
            argument working exactly as before ``row_domain`` existed.
        :type domain: list or None
        :return: rows after fill/sort/limit.
        :rtype: list
        """
        self.ensure_one()
        rows = self._fill_temporal_rows(rows, domain=domain)
        rows = self._sort_rows(rows)
        rows = self._limit_rows(rows)
        return rows

    def _prepare_zero_measure_values(self):
        """Build a row dict with every configured measure column set to
        ``0``, used by :meth:`_fill_temporal_rows` as the template for
        the zero-value rows it adds for empty periods.

        :return: dict keyed the same way a real data row is (see
            :meth:`_prepare_aggregate_spec`), every value ``0``.
        :rtype: dict
        """
        self.ensure_one()
        _aggregates, column_names = self._prepare_aggregate_spec()
        return {name: 0 for name in column_names.values()}

    def _temporal_bucket_start(self, value, granularity):
        """Floor a ``date`` to the start of its bucket for a given
        :attr:`group_by_granularity`, mirroring the buckets ``_read_group``
        produces for a date/datetime groupby field — so periods generated
        by :meth:`_fill_temporal_rows` line up with real data buckets.

        :param value: date to floor.
        :type value: datetime.date
        :param granularity: one of :attr:`group_by_granularity`'s values.
        :type granularity: str
        :return: start of the bucket ``value`` falls into.
        :rtype: datetime.date
        """
        self.ensure_one()
        if granularity == "week":
            first_week_day = self._get_date_range_first_week_day()
            return value - datetime.timedelta(
                days=(value.weekday() - first_week_day) % 7
            )
        if granularity == "month":
            return value.replace(day=1)
        if granularity == "quarter":
            start_month = ((value.month - 1) // 3) * 3 + 1
            return value.replace(month=start_month, day=1)
        if granularity == "year":
            return value.replace(month=1, day=1)
        return value  # "hour" / "day": a plain date is already the bucket start

    def _temporal_bucket_next(self, value, granularity):
        """Step a bucket-start ``date`` forward by one
        :attr:`group_by_granularity` unit. See
        :meth:`_temporal_bucket_start`.

        :param value: bucket-start date to step forward from.
        :type value: datetime.date
        :param granularity: one of :attr:`group_by_granularity`'s values.
        :type granularity: str
        :return: start of the next bucket.
        :rtype: datetime.date
        """
        self.ensure_one()
        step_by_granularity = {
            "hour": relativedelta(hours=1),
            "day": relativedelta(days=1),
            "week": relativedelta(weeks=1),
            "month": relativedelta(months=1),
            "quarter": relativedelta(months=3),
            "year": relativedelta(years=1),
        }
        return value + step_by_granularity.get(granularity, relativedelta(months=1))

    def _fill_temporal_rows(self, rows, domain=None):
        """Add zero-value rows for empty periods between the smallest
        and largest period covered, when :attr:`fill_temporal` is
        enabled and :attr:`group_by_field_id` is a date/datetime field.

        The range filled follows :meth:`_prepare_date_range`; when
        :attr:`date_range` is ``all_time`` (or leaves a side open-ended),
        that side falls back to the smallest/largest period already
        present in ``rows``. Silently returns ``rows`` unchanged when
        :attr:`fill_temporal` is off, :attr:`group_by_field_id` is not a
        date/datetime field, or there is no data to derive a fallback
        range from.

        :param rows: raw rows, as built by a ``_fetch_data_<type>``
            method — rows for a date/datetime groupby carry a
            ``group_key`` that is the bucket-start ``date``/``datetime``.
        :type rows: list
        :param domain: base domain the rows were read with. When given,
            every zero-value row added here also gets a ``row_domain``
            key (base ``domain`` plus the condition matching that empty
            bucket — see :meth:`_prepare_group_condition_domain`), same
            as real rows carry. ``None`` (the default) leaves zero-value
            rows without ``row_domain``.
        :type domain: list or None
        :return: ``rows`` plus one zero-value row per empty period.
        :rtype: list
        """
        self.ensure_one()
        field = self.group_by_field_id
        if (
            not self.fill_temporal
            or not field
            or field.ttype
            not in (
                "date",
                "datetime",
            )
        ):
            return rows
        granularity = self.group_by_granularity or "month"
        data_dates = [
            value.date() if isinstance(value, datetime.datetime) else value
            for value in (row.get("group_key") for row in rows)
            if value
        ]
        range_start, range_end = self._prepare_date_range()
        if range_start is None:
            if not data_dates:
                return rows
            range_start = min(data_dates)
        if range_end is None:
            if not data_dates:
                return rows
            range_end = max(data_dates)
        bucket_end = self._temporal_bucket_start(range_end, granularity)
        cursor = self._temporal_bucket_start(range_start, granularity)
        existing_labels = {row.get("group_label") for row in rows}
        zero_row_template = self._prepare_zero_measure_values()
        filled_rows = list(rows)
        while cursor <= bucket_end:
            label = self._format_group_by_date_label(cursor)
            if label not in existing_labels:
                zero_row = dict(zero_row_template)
                zero_row["group_key"] = False
                zero_row["group_label"] = label
                if domain is not None:
                    group_condition = self._prepare_group_condition_domain(
                        cursor, field, granularity
                    )
                    zero_row["row_domain"] = domain + group_condition
                filled_rows.append(zero_row)
                existing_labels.add(label)
            cursor = self._temporal_bucket_next(cursor, granularity)
        return filled_rows

    def _sort_rows(self, rows):
        """Sort rows according to :attr:`sort_by` / :attr:`sort_order`.

        :param rows: rows to sort, after :meth:`_fill_temporal_rows`.
        :type rows: list
        :return: ``rows`` unchanged when :attr:`sort_by` is ``none``,
            otherwise sorted by group label or first measure value.
        :rtype: list
        """
        self.ensure_one()
        if self.sort_by == "none":
            return rows
        reverse = self.sort_order != "asc"
        if self.sort_by == "label":
            return sorted(
                rows, key=lambda row: row.get("group_label") or "", reverse=reverse
            )
        _aggregates, column_names = self._prepare_aggregate_spec()
        first_measure_key = next(iter(column_names.values()))
        return sorted(
            rows, key=lambda row: row.get(first_measure_key) or 0, reverse=reverse
        )

    def _limit_rows(self, rows):
        """Cut ``rows`` down to :attr:`limit` rows, after sorting.

        :param rows: rows to limit, after :meth:`_sort_rows`.
        :type rows: list
        :return: ``rows`` unchanged when :attr:`limit` is ``0``,
            otherwise the first :attr:`limit` rows.
        :rtype: list
        """
        self.ensure_one()
        if not self.limit:
            return rows
        return rows[: self.limit]

    def _get_date_range_tz(self):
        """Return the current user's timezone for :attr:`date_range`
        computations.

        :return: ``pytz`` timezone parsed from the current user's
            :attr:`res.users.tz`, falling back to ``UTC`` when unset or
            unrecognized.
        :rtype: datetime.tzinfo
        """
        self.ensure_one()
        tz_name = self.env.user.tz
        if not tz_name:
            return pytz.utc
        try:
            return pytz.timezone(tz_name)
        except pytz.UnknownTimeZoneError:
            return pytz.utc

    def _get_date_range_today(self):
        """Return "today" as a plain ``date``, in the current user's
        timezone — so "today" for a user in Jakarta is not "today" UTC.

        :return: current date in :meth:`_get_date_range_tz`.
        :rtype: datetime.date
        """
        self.ensure_one()
        tz = self._get_date_range_tz()
        now_utc = pytz.utc.localize(fields.Datetime.now())
        return now_utc.astimezone(tz).date()

    def _get_date_range_first_week_day(self):
        """Return the first day of the week for the current user's
        language, instead of a hardcoded Monday.

        :return: ``0`` (Monday) .. ``6`` (Sunday), from the CLDR
            ``first_week_day`` of the current user's language — same
            numbering as ``datetime.date.weekday()``.
        :rtype: int
        """
        self.ensure_one()
        locale = Locale.parse(get_lang(self.env).code)
        return locale.first_week_day

    def _prepare_date_range(self):
        """Translate :attr:`date_range` into concrete date boundaries.

        Boundaries are computed against "today" in the current user's
        timezone (see :meth:`_get_date_range_today`), and the first day
        of the week follows the current user's language (see
        :meth:`_get_date_range_first_week_day`) rather than a hardcoded
        Monday.

        :return: 2-tuple ``(date_start, date_end)``. Each side is a
            ``date`` or ``None``. Both sides ``None`` means no date
            filtering at all (:attr:`date_range` = ``all_time``); only
            one side ``None`` means that side is open-ended (e.g.
            ``past_till_now`` has no lower bound, ``future_starting_now``
            has no upper bound).
        :rtype: tuple
        :raises UserError: when :attr:`date_range` has no computation
            rule — only reachable if an extension module adds a
            selection value via ``selection_add`` without overriding
            this method.
        """
        self.ensure_one()
        if self.date_range == "all_time":
            return None, None
        if self.date_range == "custom":
            return self.date_start, self.date_end

        today = self._get_date_range_today()
        if self.date_range in ("today", "yesterday"):
            return self._prepare_date_range_day(today)
        if self.date_range in ("this_week", "last_week", "next_week", "week_to_date"):
            return self._prepare_date_range_week(today)
        if self.date_range in (
            "this_month",
            "last_month",
            "next_month",
            "month_to_date",
        ):
            return self._prepare_date_range_month(today)
        if self.date_range in (
            "this_quarter",
            "last_quarter",
            "next_quarter",
            "quarter_to_date",
        ):
            return self._prepare_date_range_quarter(today)
        if self.date_range in ("this_year", "last_year", "next_year", "year_to_date"):
            return self._prepare_date_range_year(today)
        if self.date_range in (
            "last_7_days",
            "last_30_days",
            "last_90_days",
            "last_365_days",
        ):
            return self._prepare_date_range_last_n_days(today)
        if self.date_range in (
            "past_till_now",
            "past_excluding_today",
            "future_starting_now",
            "future_starting_tomorrow",
        ):
            return self._prepare_date_range_open_ended(today)

        error_message = f"""
Context: Compute dashboard data source date range
Database ID: {self.id}
Problem: 'Date Range' value '{self.date_range}' has no computation rule
Solution: Install a module that implements this 'Date Range' value
"""
        raise UserError(error_message)

    def _prepare_date_range_day(self, today):
        """Compute the boundaries for the ``today`` / ``yesterday``
        :attr:`date_range` values. See :meth:`_prepare_date_range`.

        :param today: "today" in the current user's timezone, from
            :meth:`_get_date_range_today`.
        :type today: datetime.date
        :return: 2-tuple ``(date_start, date_end)``, both the same date.
        :rtype: tuple
        """
        self.ensure_one()
        if self.date_range == "today":
            return today, today
        yesterday = today - datetime.timedelta(days=1)
        return yesterday, yesterday

    def _prepare_date_range_week(self, today):
        """Compute the boundaries for the week-based :attr:`date_range`
        values (``this_week``, ``last_week``, ``next_week``,
        ``week_to_date``). See :meth:`_prepare_date_range`.

        The week starts on :meth:`_get_date_range_first_week_day`
        instead of a hardcoded Monday.

        :param today: "today" in the current user's timezone.
        :type today: datetime.date
        :return: 2-tuple ``(date_start, date_end)``.
        :rtype: tuple
        """
        self.ensure_one()
        first_week_day = self._get_date_range_first_week_day()
        week_start = today - datetime.timedelta(
            days=(today.weekday() - first_week_day) % 7
        )
        week_end = week_start + datetime.timedelta(days=6)
        if self.date_range == "this_week":
            return week_start, week_end
        if self.date_range == "last_week":
            return (
                week_start - datetime.timedelta(days=7),
                week_end - datetime.timedelta(days=7),
            )
        if self.date_range == "next_week":
            return (
                week_start + datetime.timedelta(days=7),
                week_end + datetime.timedelta(days=7),
            )
        return week_start, today  # week_to_date

    def _prepare_date_range_month(self, today):
        """Compute the boundaries for the month-based :attr:`date_range`
        values (``this_month``, ``last_month``, ``next_month``,
        ``month_to_date``). See :meth:`_prepare_date_range`.

        :param today: "today" in the current user's timezone.
        :type today: datetime.date
        :return: 2-tuple ``(date_start, date_end)``.
        :rtype: tuple
        """
        self.ensure_one()
        month_start = today.replace(day=1)
        month_end = month_start + relativedelta(months=1, days=-1)
        if self.date_range == "this_month":
            return month_start, month_end
        if self.date_range == "last_month":
            start = month_start - relativedelta(months=1)
            return start, start + relativedelta(months=1, days=-1)
        if self.date_range == "next_month":
            start = month_start + relativedelta(months=1)
            return start, start + relativedelta(months=1, days=-1)
        return month_start, today  # month_to_date

    def _prepare_date_range_quarter(self, today):
        """Compute the boundaries for the quarter-based
        :attr:`date_range` values (``this_quarter``, ``last_quarter``,
        ``next_quarter``, ``quarter_to_date``). See
        :meth:`_prepare_date_range`.

        :param today: "today" in the current user's timezone.
        :type today: datetime.date
        :return: 2-tuple ``(date_start, date_end)``.
        :rtype: tuple
        """
        self.ensure_one()
        quarter_start_month = ((today.month - 1) // 3) * 3 + 1
        quarter_start = today.replace(month=quarter_start_month, day=1)
        quarter_end = quarter_start + relativedelta(months=3, days=-1)
        if self.date_range == "this_quarter":
            return quarter_start, quarter_end
        if self.date_range == "last_quarter":
            start = quarter_start - relativedelta(months=3)
            return start, start + relativedelta(months=3, days=-1)
        if self.date_range == "next_quarter":
            start = quarter_start + relativedelta(months=3)
            return start, start + relativedelta(months=3, days=-1)
        return quarter_start, today  # quarter_to_date

    def _prepare_date_range_year(self, today):
        """Compute the boundaries for the year-based :attr:`date_range`
        values (``this_year``, ``last_year``, ``next_year``,
        ``year_to_date``). See :meth:`_prepare_date_range`.

        :param today: "today" in the current user's timezone.
        :type today: datetime.date
        :return: 2-tuple ``(date_start, date_end)``.
        :rtype: tuple
        """
        self.ensure_one()
        year_start = today.replace(month=1, day=1)
        year_end = today.replace(month=12, day=31)
        if self.date_range == "this_year":
            return year_start, year_end
        if self.date_range == "last_year":
            return (
                year_start.replace(year=year_start.year - 1),
                year_end.replace(year=year_end.year - 1),
            )
        if self.date_range == "next_year":
            return (
                year_start.replace(year=year_start.year + 1),
                year_end.replace(year=year_end.year + 1),
            )
        return year_start, today  # year_to_date

    def _prepare_date_range_last_n_days(self, today):
        """Compute the boundaries for the rolling-window
        :attr:`date_range` values (``last_7_days``, ``last_30_days``,
        ``last_90_days``, ``last_365_days``). See
        :meth:`_prepare_date_range`.

        :param today: "today" in the current user's timezone, also the
            inclusive upper bound of every value handled here.
        :type today: datetime.date
        :return: 2-tuple ``(date_start, date_end)``.
        :rtype: tuple
        """
        self.ensure_one()
        days_back_by_range = {
            "last_7_days": 6,
            "last_30_days": 29,
            "last_90_days": 89,
            "last_365_days": 364,
        }
        days_back = days_back_by_range[self.date_range]
        return today - datetime.timedelta(days=days_back), today

    def _prepare_date_range_open_ended(self, today):
        """Compute the boundaries for the open-ended :attr:`date_range`
        values (``past_till_now``, ``past_excluding_today``,
        ``future_starting_now``, ``future_starting_tomorrow``). See
        :meth:`_prepare_date_range`.

        :param today: "today" in the current user's timezone.
        :type today: datetime.date
        :return: 2-tuple ``(date_start, date_end)`` with exactly one
            side ``None`` (no bound on that side).
        :rtype: tuple
        """
        self.ensure_one()
        one_day = datetime.timedelta(days=1)
        if self.date_range == "past_till_now":
            return None, today
        if self.date_range == "past_excluding_today":
            return None, today - one_day
        if self.date_range == "future_starting_now":
            return today, None
        return today + one_day, None  # future_starting_tomorrow

    def _date_range_bound_to_field_value(self, value, is_datetime, end_of_day):
        """Convert one boundary from :meth:`_prepare_date_range` into the
        value compared against :attr:`date_field_id`.

        :param value: boundary computed by :meth:`_prepare_date_range`.
        :type value: datetime.date
        :param is_datetime: ``True`` when :attr:`date_field_id` is a
            'datetime' field, so the user's local midnight / end-of-day
            must be converted into naive UTC — the form ``Datetime``
            fields are stored/compared in.
        :type is_datetime: bool
        :param end_of_day: ``True`` to use ``23:59:59`` as the local
            time of day instead of ``00:00:00`` — used for the upper
            bound so the whole last day is included.
        :type end_of_day: bool
        :return: ``value`` unchanged for a 'date' field, or the
            equivalent naive UTC ``datetime`` for a 'datetime' field.
        """
        self.ensure_one()
        if not is_datetime:
            return value
        tz = self._get_date_range_tz()
        time_of_day = datetime.time(23, 59, 59) if end_of_day else datetime.time.min
        local_dt = tz.localize(datetime.datetime.combine(value, time_of_day))
        return local_dt.astimezone(pytz.utc).replace(tzinfo=None)

    def _parse_active_filter_date(self, value):
        """Parse one ``active_filters`` ``date_start``/``date_end``
        boundary, as received by :meth:`_prepare_date_domain` through
        the ``dashboard_active_filters`` context key.

        :param value: ISO date string (e.g. ``'2026-01-31'``), or falsy.
        :type value: str or None
        :return: parsed date, or ``None`` when ``value`` is falsy (open
            bound on that side).
        :rtype: datetime.date or None
        """
        self.ensure_one()
        if not value:
            return None
        return fields.Date.from_string(value)

    def _prepare_date_domain(self, date_range_override=None):
        """Build the domain fragment date filtering contributes to
        :meth:`_fetch_data_orm`.

        Three sources are tried in order, the first that applies wins:

        1. ``date_range_override`` — used by :meth:`_fetch_comparison_data`
           to filter on a comparison range instead of the current one.
        2. The ``dashboard_active_filters`` context key (set by
           :meth:`_fetch_data`) — when it carries a non-empty
           ``date_start`` or ``date_end``, those override this data
           source's own :attr:`date_range` entirely, letting a
           dashboard's global date range picker control every data
           source with a :attr:`date_field_id` at once.
        3. :attr:`date_range`/:meth:`_prepare_date_range`, exactly as
           before either of the above existed.

        :param date_range_override: optional 2-tuple ``(date_start,
            date_end)`` to build the domain from directly, bypassing
            both the active filters and :attr:`date_range` entirely.
            Either side may be ``None`` for an open-ended bound. Omitted
            (default) for the current-period read done by
            :meth:`_fetch_data`.
        :type date_range_override: tuple or None
        :return: list of domain tuples on :attr:`date_field_id`, meant
            to be ANDed (implicit ``&``) with the rest of the domain
            built in :meth:`_fetch_data_orm`. Empty when
            :attr:`date_field_id` is not set, or (with no override in
            effect) :attr:`date_range` is ``all_time``.
        :rtype: list
        """
        self.ensure_one()
        if not self.date_field_id:
            return []
        if date_range_override is not None:
            date_start, date_end = date_range_override
        else:
            active_filters = self.env.context.get("dashboard_active_filters")
            override_start = (
                active_filters.get("date_start") if active_filters else None
            )
            override_end = active_filters.get("date_end") if active_filters else None
            if active_filters and (override_start or override_end):
                date_start = self._parse_active_filter_date(override_start)
                date_end = self._parse_active_filter_date(override_end)
            elif self.date_range == "all_time":
                return []
            else:
                date_start, date_end = self._prepare_date_range()
        field_name = self.date_field_id.name
        is_datetime = self.date_field_id.ttype == "datetime"
        domain = []
        if date_start is not None:
            domain.append(
                (
                    field_name,
                    ">=",
                    self._date_range_bound_to_field_value(
                        date_start, is_datetime, end_of_day=False
                    ),
                )
            )
        if date_end is not None:
            domain.append(
                (
                    field_name,
                    "<=",
                    self._date_range_bound_to_field_value(
                        date_end, is_datetime, end_of_day=True
                    ),
                )
            )
        return domain

    def _prepare_aggregate_spec(self):
        """Build the ``_read_group`` aggregate specification for this data
        source, so :meth:`_fetch_data_orm` does not need to know whether
        :attr:`measure_ids` or the single :attr:`measure_field_id` /
        :attr:`aggregate` pair is in effect.

        When :attr:`measure_ids` is set, it takes precedence and
        :attr:`measure_field_id` / :attr:`aggregate` are ignored — one
        spec is built per measure row, in :attr:`measure_ids` order.
        Otherwise, a single spec is built from :attr:`measure_field_id`
        and :attr:`aggregate`, keeping older data sources (created before
        :attr:`measure_ids` existed) working unchanged.

        :return: 2-tuple ``(aggregates, column_names)``. ``aggregates``
            is a list of string specs accepted by ``_read_group``'s
            ``aggregates`` argument (e.g. ``"amount_total:sum"``,
            ``"__count"``). ``column_names`` maps each spec to the key
            its value is stored under in the rows built by
            :meth:`_fetch_data_orm` — the measure's ``name`` when
            :attr:`measure_ids` is set, or the spec itself otherwise (so
            the single-measure fallback keeps its historical output key,
            e.g. ``"__count"``).
        :rtype: tuple
        """
        self.ensure_one()
        if self.measure_ids:
            aggregates = []
            column_names = {}
            for measure in self.measure_ids:
                spec = (
                    "__count"
                    if measure.aggregate == "count"
                    else f"{measure.field_id.name}:{measure.aggregate}"
                )
                aggregates.append(spec)
                column_names[spec] = measure.name
            return aggregates, column_names
        spec = (
            "__count"
            if self.aggregate == "count"
            else f"{self.measure_field_id.name}:{self.aggregate}"
        )
        return [spec], {spec: spec}

    @api.model
    def _eval_domain_text(self, domain_text):
        """Evaluate a raw domain string into a domain list, substituting
        the placeholders recognized in it before evaluating.

        Two placeholders are substituted directly on the **string**,
        before ``safe_eval`` runs on it:

        - ``%UID`` — the current user id (``self.env.uid``).
        - ``%MYCOMPANY`` — the current company id (``self.env.company.id``).

        Any other ``%``-prefixed token is left untouched, so it fails
        ``safe_eval`` and is caught by the caller instead of silently
        being ignored.

        Shared by :meth:`_prepare_domain` (this data source's own
        'Domain') and ``dashboard.filter._prepare_domain``/``_check_
        filter_type_domain`` (a filter's 'Domain', 'Predefined Domain'
        type), so a filter's domain goes through the exact same
        substitution and validation as a data source's own domain.

        :param domain_text: raw domain string, as stored in 'Domain'.
        :type domain_text: str
        :return: domain, ready to use with ``search``/``_read_group``.
        :rtype: list
        :raises Exception: whatever ``safe_eval`` raises when
            ``domain_text`` (after substitution) is not valid Python
            domain syntax — left uncaught here so callers such as
            :meth:`_check_domain` can turn it into a ``ValidationError``.
        """
        domain_str = domain_text.replace("%UID", str(self.env.uid)).replace(
            "%MYCOMPANY", str(self.env.company.id)
        )
        return safe_eval(domain_str)

    def _prepare_domain(self):
        """Build the domain applied on :attr:`model_id`, substituting the
        ``%UID``/``%MYCOMPANY`` placeholders recognized in the raw
        :attr:`domain` string before evaluating it. See
        :meth:`_eval_domain_text` for the substitution/evaluation rules.

        :return: domain, ready to use with ``search``/``_read_group``.
        :rtype: list
        :raises Exception: see :meth:`_eval_domain_text`.
        """
        self.ensure_one()
        if not self.domain:
            return []
        return self._eval_domain_text(self.domain)

    def _prepare_filter_domain(self):
        """Build the domain fragment the dashboard's active filters (see
        ``dashboard.filter``) contribute to :meth:`_fetch_data_orm`, for
        this data source's own :attr:`model_id`.

        Active filter ids are read from the ``dashboard_active_filters``
        context key (set by :meth:`_fetch_data`). 'Field Value' filters
        whose :attr:`~dashboard.filter.field_id` does not exist on
        :attr:`model_id` are skipped for this data source instead of
        raising — see ``dashboard.filter._is_applicable`` — so one
        dashboard can mix items pulling from several different models.

        :return: list of domain tuples, meant to be ANDed (implicit
            ``&``) with the rest of the domain built in
            :meth:`_fetch_data_orm`. Empty when :attr:`model_id` is not
            set, no filter is active, or none of the active filters
            applies to :attr:`model_id`.
        :rtype: list
        """
        self.ensure_one()
        if not self.model_id:
            return []
        active_filters = self.env.context.get("dashboard_active_filters")
        if not active_filters:
            return []
        filter_ids = active_filters.get("filter_ids") or []
        if not filter_ids:
            return []
        domain = []
        dashboard_filters = (
            self.env["dashboard.filter"].sudo().browse(filter_ids).exists()
        )
        for dashboard_filter in dashboard_filters:
            if not dashboard_filter._is_applicable(self.model_id.model):
                continue
            domain += dashboard_filter._prepare_domain()
        return domain

    def _fetch_data_orm(self, item, date_range_override=None):
        """Fetch data for the 'orm' data source type.

        Reads :attr:`model_id` through ``_read_group`` filtered by the
        domain built by :meth:`_prepare_domain` (that is, :attr:`domain`
        with its ``%UID`` / ``%MYCOMPANY`` placeholders substituted).
        ``read_group`` is deprecated since 19.0 in favor of
        ``_read_group``/``formatted_read_group``; ``_read_group`` is
        used here and its tuple result is turned back into the list of
        dict this method's contract promises.

        Aggregate values are built by :meth:`_prepare_aggregate_spec`, so
        a row carries one key per configured measure (see
        :attr:`measure_ids`) instead of always being a plain record
        count.

        When :attr:`group_by_field_id` is set, each row is enriched with
        two extra keys: ``group_key`` (raw group value, for a future
        drill-down domain) and ``group_label`` (human-readable label). With
        no grouping field configured, behavior is unchanged: exactly one
        row per configured measure spec, without those two keys.

        When :attr:`sub_group_by_field_id` is also set, each row gets two
        further keys: ``sub_group_key`` and ``sub_group_label``, built the
        same way as ``group_key``/``group_label`` but for the second
        dimension — one row per combination of the two dimensions that
        has data. Without :attr:`sub_group_by_field_id`, those two keys
        are absent entirely (not ``False``), keeping single-dimension
        data sources exactly as before this second dimension existed.

        Every row also carries a ``row_domain`` key — a domain that,
        run through ``search``/``search_count`` on :attr:`model_id`,
        returns exactly the records behind that row: ``domain`` (this
        method's own base domain, see below) with no grouping applied,
        or ``domain`` plus the condition(s) matching that row's group
        (and sub group, when configured) — see
        :meth:`_prepare_group_condition_domain`. Built server-side, from
        the same grouping metadata the row's own aggregate was computed
        from, so it can never drift from what the row actually shows.

        :attr:`date_field_id` / :attr:`date_range` contribute an extra
        domain fragment built by :meth:`_prepare_date_domain`, ANDed
        with :attr:`domain`. A data source without :attr:`date_field_id`
        set behaves exactly as before this fragment existed.

        The dashboard's active filters (see ``dashboard.filter``, read
        through the ``dashboard_active_filters`` context key) contribute
        a further domain fragment built by :meth:`_prepare_filter_domain`,
        also ANDed in. A data source read outside of
        ``dashboard.dashboard.get_dashboard_payload`` (that context key
        unset) behaves exactly as before filters existed.

        An in-progress drill-down navigation (see
        ``dashboard.item.fetch_drilldown_data``) contributes one more
        fragment, built by :meth:`_prepare_drilldown_extra_domain`, also
        ANDed in. A call made outside of that navigation (the
        ``dashboard_drilldown_extra_domain`` context key unset) behaves
        exactly as before drill-down existed.

        As a last step, :meth:`_postprocess_rows` applies
        :attr:`fill_temporal`, :attr:`sort_by`/:attr:`sort_order`, and
        :attr:`limit`, in that order.

        :param item: ``dashboard.item`` record requesting the data.
        :param date_range_override: optional 2-tuple ``(date_start,
            date_end)`` passed straight through to
            :meth:`_prepare_date_domain` — used by
            :meth:`_fetch_comparison_data` to read a comparison range
            instead of the current one. Omitted (default) for the
            current-period read done by :meth:`_fetch_data`.
        :type date_range_override: tuple or None
        :return: list of dict, one per group returned by ``_read_group``,
            after :meth:`_postprocess_rows`.
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
        domain = (
            self._prepare_domain()
            + self._prepare_date_domain(date_range_override)
            + self._prepare_filter_domain()
            + self._prepare_drilldown_extra_domain()
        )
        model = self.env[self.model_id.model].sudo()
        aggregates, column_names = self._prepare_aggregate_spec()
        groupby = self._prepare_groupby_spec()
        rows = model._read_group(domain, groupby=groupby, aggregates=aggregates)
        if not groupby:
            result = [
                {
                    column_names[spec]: value
                    for spec, value in zip(aggregates, row, strict=True)
                }
                for row in rows
            ]
            for row_dict in result:
                row_dict["row_domain"] = domain
            return self._postprocess_rows(result, domain=domain)
        result = []
        has_sub_group = len(groupby) == 2
        for row in rows:
            if has_sub_group:
                group_value, sub_group_value, *aggregate_values = row
            else:
                group_value, *aggregate_values = row
            row_dict = {
                column_names[spec]: value
                for spec, value in zip(aggregates, aggregate_values, strict=True)
            }
            row_dict["group_key"] = self._prepare_group_key(group_value)
            row_dict["group_label"] = self._prepare_group_label(group_value)
            row_domain = domain + self._prepare_group_condition_domain(
                group_value, self.group_by_field_id, self.group_by_granularity
            )
            if has_sub_group:
                row_dict["sub_group_key"] = self._prepare_group_key(sub_group_value)
                row_dict["sub_group_label"] = self._prepare_sub_group_label(
                    sub_group_value
                )
                row_domain = row_domain + self._prepare_group_condition_domain(
                    sub_group_value,
                    self.sub_group_by_field_id,
                    self.sub_group_by_granularity,
                )
            row_dict["row_domain"] = row_domain
            result.append(row_dict)
        return self._postprocess_rows(result, domain=domain)

    def _prepare_comparison_date_range(self):
        """Build the comparison date range(s) matching :attr:`comparison`.

        :return: list of 2-tuple ``(date_start, date_end)``. Empty when
            :attr:`comparison` is ``none``. Exactly one element for
            ``previous_period``, shifted backward from the current
            range (see :meth:`_prepare_date_range`) by that range's own
            duration — e.g. 1-31 Jan compares against 1-31 Dec the
            previous year. Exactly :attr:`comparison_year_count`
            elements for ``previous_year``, one per year back, keeping
            the same start/end day. Either side of a tuple is ``None``
            when the current range has that side open-ended (or
            :attr:`date_range` is ``all_time``) — no meaningful shift
            can be computed in that case.
        :rtype: list
        """
        self.ensure_one()
        if self.comparison == "none":
            return []
        date_start, date_end = self._prepare_date_range()
        if self.comparison == "previous_period":
            return [
                self._prepare_comparison_date_range_previous_period(
                    date_start, date_end
                )
            ]
        return [
            self._prepare_comparison_date_range_previous_year(
                date_start, date_end, year_offset
            )
            for year_offset in range(1, self.comparison_year_count + 1)
        ]

    def _prepare_comparison_date_range_previous_period(self, date_start, date_end):
        """Build the single comparison range for :attr:`comparison` =
        ``previous_period``. See :meth:`_prepare_comparison_date_range`.

        The comparison range ends the day before ``date_start`` and has
        exactly the same duration (in days) as ``[date_start,
        date_end]`` — computed from the boundaries themselves, not from
        calendar months, so it also works for ranges that do not align
        with a month.

        :param date_start: current range start, from
            :meth:`_prepare_date_range`.
        :type date_start: datetime.date or None
        :param date_end: current range end, from
            :meth:`_prepare_date_range`.
        :type date_end: datetime.date or None
        :return: 2-tuple ``(date_start, date_end)`` of the comparison
            range. ``(None, None)`` when either side of the current
            range is open-ended.
        :rtype: tuple
        """
        self.ensure_one()
        if date_start is None or date_end is None:
            return None, None
        duration = date_end - date_start
        comparison_end = date_start - datetime.timedelta(days=1)
        comparison_start = comparison_end - duration
        return comparison_start, comparison_end

    def _prepare_comparison_date_range_previous_year(
        self, date_start, date_end, year_offset
    ):
        """Build one comparison range for :attr:`comparison` =
        ``previous_year``. See :meth:`_prepare_comparison_date_range`.

        :param date_start: current range start, from
            :meth:`_prepare_date_range`.
        :type date_start: datetime.date or None
        :param date_end: current range end, from
            :meth:`_prepare_date_range`.
        :type date_end: datetime.date or None
        :param year_offset: number of years back this comparison range
            is shifted, from ``1`` to :attr:`comparison_year_count`.
        :type year_offset: int
        :return: 2-tuple ``(date_start, date_end)`` shifted back
            ``year_offset`` years, same start/end day. ``(None, None)``
            when either side of the current range is open-ended.
        :rtype: tuple
        """
        self.ensure_one()
        if date_start is None or date_end is None:
            return None, None
        return (
            date_start - relativedelta(years=year_offset),
            date_end - relativedelta(years=year_offset),
        )

    def _fetch_comparison_data(self, item):
        """Fetch comparison data for a dashboard item.

        Reuses the same ``_fetch_data_<type>`` read path as
        :meth:`_fetch_data`, called once per comparison range from
        :meth:`_prepare_comparison_date_range`, with the date domain
        shifted to that range instead of the current one (via
        ``date_range_override`` — see :meth:`_fetch_data_orm`). The
        contract of :meth:`_fetch_data` itself is unchanged: it never
        calls this method, so a data source with :attr:`comparison` =
        ``none`` pays no extra query cost.

        :param item: ``dashboard.item`` record requesting the data.
        :return: list of list of dict — one list of rows per
            comparison range, in :meth:`_prepare_comparison_date_range`
            order. Empty when :attr:`comparison` is ``none``.
        :rtype: list
        :raises UserError: when no ``_fetch_data_<type>`` method exists
            for :attr:`type` — same guard as :meth:`_fetch_data`.
        """
        self.ensure_one()
        method_name = f"_fetch_data_{self.type}"
        method = getattr(self, method_name, None)
        if method is None:
            error_message = f"""
Document Type: {self._description}
Context: Fetch dashboard item comparison data
Database ID: {self.id}
Problem: No data fetch implementation for data source type '{self.type}'
Solution: Install a module that implements {method_name}
"""
            raise UserError(error_message)
        return [
            method(item, date_range_override=date_range)
            for date_range in self._prepare_comparison_date_range()
        ]
