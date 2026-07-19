# Copyright 2026 OpenSynergy Indonesia
# Copyright 2026 PT. Simetri Sinergi Indonesia
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from odoo import api, fields, models
from odoo.exceptions import ValidationError


class DashboardFilter(models.Model):
    """Represents one entry of a dashboard's global filter bar. Every
    active filter narrows every item's data, on top of that item's own
    data source configuration — a filter never widens what a data source
    already allows, see :meth:`_prepare_domain` and
    ``dashboard.data_source._prepare_filter_domain``.

    Three kinds exist, picked with :attr:`filter_type`:

    - ``domain`` (Predefined Domain) — :attr:`domain` is combined as-is
      into the domain of every 'orm' data source, through the same
      substitution/evaluation as a data source's own domain (see
      ``dashboard.data_source._eval_domain_text``).
    - ``field`` (Field Value) — :attr:`field_id` must have a value
      (``!= False``); skipped for a data source whose model does not
      have that field, instead of failing the whole dashboard.
    - ``date`` (Date Range) — carries no domain of its own. It marks the
      dashboard as showing the global date range picker, whose selection
      is passed through ``get_dashboard_payload``'s ``date_start``/
      ``date_end`` instead (applied to every data source that has a
      ``date_field_id``, regardless of any 'date' filter's own active
      state)."""

    _name = "dashboard.filter"
    _description = "Dashboard Filter"
    _order = "dashboard_id, sequence"

    dashboard_id = fields.Many2one(
        string="# Dashboard",
        comodel_name="dashboard.dashboard",
        required=True,
        ondelete="cascade",
        help="Dashboard this filter belongs to.",
    )
    sequence = fields.Integer(
        default=10,
        help="Determines the display order of filters on the filter bar.",
    )
    name = fields.Char(
        required=True,
        help="Label shown for this filter on the filter bar.",
    )
    filter_type = fields.Selection(
        selection=[
            ("domain", "Predefined Domain"),
            ("field", "Field Value"),
            ("date", "Date Range"),
        ],
        required=True,
        default="domain",
        help="Kind of filter. 'Predefined Domain' applies 'Domain' as-is "
        "to every 'orm' data source. 'Field Value' requires 'Field' to "
        "have a value, and is skipped for any data source whose model "
        "does not have that field. 'Date Range' requires neither and "
        "carries no domain of its own — it only marks this dashboard as "
        "showing the global date range picker.",
    )
    domain = fields.Text(
        help="Odoo domain (Python list syntax) applied when this filter "
        "is active. Only used, and required, when 'Filter Type' is "
        "'Predefined Domain'. Supports the same '%UID'/'%MYCOMPANY' "
        "placeholders as a data source's own 'Domain'.",
    )
    field_id = fields.Many2one(
        comodel_name="ir.model.fields",
        ondelete="set null",
        help="Field checked for a non-empty value when this filter is "
        "active. Only used, and required, when 'Filter Type' is 'Field "
        "Value'. Data sources whose 'Model' does not have this field "
        "skip this filter instead of failing.",
    )
    default_active = fields.Boolean(
        default=False,
        help="Enable so this filter is already active the first time the "
        "dashboard is opened, i.e. when 'get_dashboard_payload' is "
        "called without an explicit 'active_filters' argument.",
    )

    @api.constrains("filter_type", "domain")
    def _check_filter_type_domain(self):
        for filter_ in self:
            if filter_.filter_type != "domain":
                continue
            if not filter_.domain:
                error_message = f"""
Document Type: {filter_._description}
Context: Configure dashboard filter
Database ID: {filter_.id}
Problem: 'Filter Type' is 'Predefined Domain' but 'Domain' is empty
Solution: Set 'Domain', or change 'Filter Type' to another value
"""
                raise ValidationError(error_message)
            try:
                domain = self.env["dashboard.data_source"]._eval_domain_text(
                    filter_.domain
                )
            except Exception as error:
                error_message = f"""
Document Type: {filter_._description}
Context: Configure dashboard filter
Database ID: {filter_.id}
Problem: 'Domain' cannot be evaluated as a domain expression
Solution: Fix the domain syntax. Original error: {error}
"""
                raise ValidationError(error_message) from error
            if not isinstance(domain, list):
                error_message = f"""
Document Type: {filter_._description}
Context: Configure dashboard filter
Database ID: {filter_.id}
Problem: 'Domain' does not evaluate to a list
Solution: Write 'Domain' as a Python list of domain tuples/leaves
"""
                raise ValidationError(error_message)

    @api.constrains("filter_type", "field_id")
    def _check_filter_type_field(self):
        for filter_ in self:
            if filter_.filter_type == "field" and not filter_.field_id:
                error_message = f"""
Document Type: {filter_._description}
Context: Configure dashboard filter
Database ID: {filter_.id}
Problem: 'Filter Type' is 'Field Value' but 'Field' is empty
Solution: Set 'Field', or change 'Filter Type' to another value
"""
                raise ValidationError(error_message)

    def _is_applicable(self, model_name):
        """Whether this filter contributes a domain fragment for a data
        source whose model is ``model_name``.

        Only 'Field Value' filters can be inapplicable to a given model —
        'Predefined Domain' and 'Date Range' filters are always
        considered applicable, since only :attr:`field_id` carries the
        model association needed to tell.

        :param model_name: technical model name of the data source being
            evaluated (``dashboard.data_source.model_id.model``).
        :type model_name: str
        :return: ``True`` when this filter should contribute its domain
            (see :meth:`_prepare_domain`) for that model.
        :rtype: bool
        """
        self.ensure_one()
        if self.filter_type != "field":
            return True
        return bool(self.field_id) and self.field_id.model == model_name

    def _prepare_domain(self):
        """Build the domain fragment this filter contributes when active.

        :return: list of domain tuples, meant to be ANDed (implicit
            ``&``) with the rest of the domain a data source builds.
            Empty for 'Date Range' filters, and for 'Predefined Domain'/
            'Field Value' filters missing their required field (should
            not happen once :meth:`_check_filter_type_domain`/
            :meth:`_check_filter_type_field` have run, kept defensive
            here).
        :rtype: list
        """
        self.ensure_one()
        if self.filter_type == "domain":
            if not self.domain:
                return []
            return self.env["dashboard.data_source"]._eval_domain_text(self.domain)
        if self.filter_type == "field":
            if not self.field_id:
                return []
            return [(self.field_id.name, "!=", False)]
        return []

    def _prepare_filter_payload(self):
        """Build the payload entry the browser uses to render this
        filter on the filter bar.

        :return: dict with keys ``id``, ``name``, ``filter_type`` and
            ``default_active``.
        :rtype: dict
        """
        self.ensure_one()
        return {
            "id": self.id,
            "name": self.name,
            "filter_type": self.filter_type,
            "default_active": self.default_active,
        }

    def _prepare_export_filter_vals(self):
        """Build this filter's own entry under
        ``dashboard.dashboard.prepare_export_definition``'s ``filters``
        key.

        :return: dict with keys ``name``, ``sequence``, ``filter_type``,
            ``domain``, ``field`` (see
            ``dashboard.data_source._export_field_ref``) and
            ``default_active``.
        :rtype: dict
        """
        self.ensure_one()
        return {
            "name": self.name,
            "sequence": self.sequence,
            "filter_type": self.filter_type,
            "domain": self.domain,
            "field": self.env["dashboard.data_source"]._export_field_ref(self.field_id),
            "default_active": self.default_active,
        }
