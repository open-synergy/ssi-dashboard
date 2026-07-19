# Copyright 2026 OpenSynergy Indonesia
# Copyright 2026 PT. Simetri Sinergi Indonesia
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from odoo import api, fields, models
from odoo.exceptions import ValidationError


class DashboardItem(models.Model):
    """Represents a single tile placed on a dashboard. This core module
    only ships the 'placeholder' type so the module can be installed and
    tested standalone. Extension modules add further types via
    ``selection_add`` on :attr:`type` and may implement a matching
    ``_prepare_render_payload_<type>`` method to enrich the payload built
    by :meth:`_prepare_render_payload`."""

    _name = "dashboard.item"
    _description = "Dashboard Item"
    _order = "dashboard_id, sequence"

    dashboard_id = fields.Many2one(
        string="# Dashboard",
        comodel_name="dashboard.dashboard",
        required=True,
        ondelete="cascade",
        help="Dashboard this item is placed on.",
    )
    name = fields.Char(
        required=True,
        help="Label shown on the item's tile.",
    )
    sequence = fields.Integer(
        default=10,
        help="Determines the display order of items on the dashboard.",
    )
    type = fields.Selection(
        selection=[
            ("placeholder", "Placeholder"),
        ],
        required=True,
        default="placeholder",
        help="Kind of tile rendered by the browser. Extension modules add "
        "more choices via 'selection_add' and may implement a matching "
        "'_prepare_render_payload_<type>' method.",
    )
    data_source_id = fields.Many2one(
        comodel_name="dashboard.data_source",
        ondelete="restrict",
        help="Data source this item pulls its data from. Required unless "
        "'Type' is one that overrides '_is_data_source_required' to "
        "return False.",
    )
    config = fields.Text(
        help="JSON configuration specific to this item's 'Type'.",
    )
    column_width = fields.Integer(
        default=4,
        help="Width of this item's tile, in grid columns out of 12.",
    )
    row_height = fields.Integer(
        default=1,
        help="Height of this item's tile, in grid rows.",
    )
    active = fields.Boolean(
        default=True,
        help="Untick to hide this item from its dashboard without deleting it.",
    )
    goal_type = fields.Selection(
        selection=[
            ("none", "No Target"),
            ("fixed", "Fixed Value"),
            ("dated", "Dated Targets"),
        ],
        required=True,
        default="none",
        help="Kind of target this item is measured against. 'No Target' "
        "carries no target value. 'Fixed Value' uses 'Goal Value' for "
        "every date. 'Dated Targets' looks up 'Goals' for the value that "
        "applies to a given date, see '_get_goal_value'.",
    )
    goal_value = fields.Float(
        default=0.0,
        help="Target value applied for every date. Only used when 'Goal "
        "Type' is 'Fixed Value'.",
    )
    goal_ids = fields.One2many(
        string="Goals",
        comodel_name="dashboard.item.goal",
        inverse_name="item_id",
        help="Dated target rows, each stating the value that applies for "
        "its own date range. Only used when 'Goal Type' is 'Dated "
        "Targets'.",
    )
    multiplier = fields.Float(
        default=1.0,
        help="Factor the raw value is multiplied by before the browser "
        "formats it, e.g. use 0.000001 to show a value in millions. "
        "Must not be 0.",
    )
    unit_type = fields.Selection(
        selection=[
            ("none", "No Unit"),
            ("monetary", "Currency"),
            ("custom", "Custom Text"),
        ],
        required=True,
        default="none",
        help="Kind of unit shown alongside the value. 'No Unit' shows the "
        "value alone. 'Currency' shows 'Currency''s symbol, and requires "
        "'Currency' to be filled in. 'Custom Text' shows 'Unit Text', and "
        "requires 'Unit Text' to be filled in.",
    )
    currency_id = fields.Many2one(
        comodel_name="res.currency",
        ondelete="restrict",
        help="Currency whose symbol is shown alongside the value. Only "
        "used, and required, when 'Unit Type' is 'Currency'.",
    )
    unit_text = fields.Char(
        help="Free-form unit text shown alongside the value, e.g. 'kg', "
        "'pcs', '%'. Only used, and required, when 'Unit Type' is "
        "'Custom Text'.",
    )
    unit_position = fields.Selection(
        selection=[
            ("before", "Before Value"),
            ("after", "After Value"),
        ],
        required=True,
        default="after",
        help="Where the unit is shown relative to the value.",
    )
    number_format = fields.Selection(
        selection=[
            ("exact", "Exact"),
            ("short", "Short Scale"),
            ("indian", "Indian Scale"),
        ],
        required=True,
        default="exact",
        help="How the browser abbreviates the value. 'Exact' shows the "
        "full number. 'Short Scale' abbreviates using thousand/million/"
        "billion suffixes. 'Indian Scale' abbreviates using lakh/crore "
        "suffixes.",
    )
    precision_digits = fields.Integer(
        default=2,
        help="Number of digits shown after the decimal point. Must be between 0 and 6.",
    )

    def _is_data_source_required(self):
        """Whether :attr:`data_source_id` must be filled in for this
        item's :attr:`type`.

        Default implementation always returns ``True``, so every type
        shipped without overriding this method keeps requiring a data
        source exactly as before this method existed. Extension modules
        adding a type that renders without pulling any data (e.g. a
        static checklist) override this to return ``False`` for that
        type, and :meth:`_check_data_source_required` enforces it.

        :return: ``True`` when :attr:`data_source_id` is required.
        :rtype: bool
        """
        self.ensure_one()
        return True

    @api.constrains("data_source_id", "type")
    def _check_data_source_required(self):
        for item in self:
            if item._is_data_source_required() and not item.data_source_id:
                error_message = f"""
Context: Configure dashboard item
Database ID: {item.id}
Problem: 'Data Source' is empty but 'Type' '{item.type}' requires one
Solution: Set 'Data Source', or choose a 'Type' that does not require one
"""
                raise ValidationError(error_message)

    @api.constrains("multiplier")
    def _check_multiplier_not_zero(self):
        for item in self:
            if item.multiplier == 0.0:
                error_message = f"""
Context: Configure dashboard item
Database ID: {item.id}
Problem: 'Multiplier' is set to 0
Solution: Set 'Multiplier' to a non-zero value
"""
                raise ValidationError(error_message)

    @api.constrains("precision_digits")
    def _check_precision_digits_range(self):
        for item in self:
            if not 0 <= item.precision_digits <= 6:
                error_message = f"""
Context: Configure dashboard item
Database ID: {item.id}
Problem: 'Precision Digits' is set to {item.precision_digits}, which is \
outside the allowed range of 0 to 6
Solution: Set 'Precision Digits' to a value between 0 and 6
"""
                raise ValidationError(error_message)

    @api.constrains("unit_type", "currency_id")
    def _check_unit_type_monetary_requires_currency(self):
        for item in self:
            if item.unit_type == "monetary" and not item.currency_id:
                error_message = f"""
Context: Configure dashboard item
Database ID: {item.id}
Problem: 'Unit Type' is set to 'Currency' but 'Currency' is empty
Solution: Fill in 'Currency', or change 'Unit Type' to another value
"""
                raise ValidationError(error_message)

    @api.constrains("unit_type", "unit_text")
    def _check_unit_type_custom_requires_unit_text(self):
        for item in self:
            if item.unit_type == "custom" and not item.unit_text:
                error_message = f"""
Context: Configure dashboard item
Database ID: {item.id}
Problem: 'Unit Type' is set to 'Custom Text' but 'Unit Text' is empty
Solution: Fill in 'Unit Text', or change 'Unit Type' to another value
"""
                raise ValidationError(error_message)

    @api.onchange("unit_type")
    def onchange_currency_id(self):
        if self.unit_type != "monetary":
            self.currency_id = False

    @api.onchange("unit_type")
    def onchange_unit_text(self):
        if self.unit_type != "custom":
            self.unit_text = False

    @api.constrains("goal_type", "goal_ids")
    def _check_goal_type_dated_requires_goal_ids(self):
        for item in self:
            if item.goal_type == "dated" and not item.goal_ids:
                error_message = f"""
Context: Configure dashboard item
Database ID: {item.id}
Problem: 'Goal Type' is set to 'Dated Targets' but 'Goals' has no rows
Solution: Add at least one row to 'Goals', or change 'Goal Type' to \
another value
"""
                raise ValidationError(error_message)

    @api.onchange("goal_type")
    def onchange_goal_value(self):
        if self.goal_type == "none":
            self.goal_value = 0.0

    @api.onchange("goal_type")
    def onchange_goal_ids(self):
        if self.goal_type == "none":
            self.goal_ids = [(5, 0, 0)]

    def _get_goal_value(self, target_date):
        """Compute the target value that applies to ``target_date``.

        :param target_date: date the target value is looked up for.
        :type target_date: datetime.date
        :return: ``0.0`` when 'Goal Type' is 'No Target'; 'Goal Value' when
            'Goal Type' is 'Fixed Value'; the 'Value' of the first 'Goals'
            row whose 'Date Start'/'Date End' range contains
            ``target_date`` when 'Goal Type' is 'Dated Targets' — ``0.0``
            when no row matches.
        :rtype: float
        """
        self.ensure_one()
        if self.goal_type == "fixed":
            return self.goal_value
        if self.goal_type == "dated":
            for goal in self.goal_ids:
                if goal.date_start <= target_date <= goal.date_end:
                    return goal.value
            return 0.0
        return 0.0

    def action_open_item_goals(self):
        for record in self.sudo():
            result = record._open_item_goals()
        return result

    def _open_item_goals(self):
        """Build the window action that opens this item's own form view in
        a dialog, so 'Goals' (a nested one2many that cannot be edited
        inline inside the dashboard form's editable 'Items' list) can be
        managed.

        :return: dict describing an ``ir.actions.act_window`` targeting
            this record's form view, opened as a dialog
            (``target='new'``).
        :rtype: dict
        """
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "res_model": "dashboard.item",
            "res_id": self.id,
            "view_mode": "form",
            "view_id": self.env.ref("ssi_dashboard.dashboard_item_view_form").id,
            "target": "new",
            "name": self.name,
        }

    def _get_number_format_config(self):
        """Build the number formatting configuration passed to the browser.

        No formatting happens server-side — this is a passthrough of the
        item's own configuration fields so the browser can format the raw
        value following the user's locale (and still have the raw value
        available to draw charts).

        :return: dict with keys ``multiplier``, ``unit_type``,
            ``unit_symbol`` (:attr:`currency_id`'s symbol when
            :attr:`unit_type` is ``monetary``, :attr:`unit_text` when
            ``custom``, empty string when ``none``), ``unit_position``,
            ``number_format`` and ``precision_digits``.
        :rtype: dict
        """
        self.ensure_one()
        if self.unit_type == "monetary":
            unit_symbol = self.currency_id.symbol
        elif self.unit_type == "custom":
            unit_symbol = self.unit_text
        else:
            unit_symbol = ""
        return {
            "multiplier": self.multiplier,
            "unit_type": self.unit_type,
            "unit_symbol": unit_symbol,
            "unit_position": self.unit_position,
            "number_format": self.number_format,
            "precision_digits": self.precision_digits,
        }

    def _prepare_render_payload(self):
        """Build the payload the browser uses to render this item.

        Fetches the item's data through :attr:`data_source_id`, then
        dispatches to ``self._prepare_render_payload_<type>(payload)`` when
        that method exists, so extension modules can enrich the payload
        with type-specific keys. When no such method exists, the base
        payload is returned as-is.

        :return: dict with keys ``id``, ``name``, ``type``,
            ``column_width``, ``row_height``, ``active``, ``data`` and
            ``number_format_config`` (see :meth:`_get_number_format_config`).
            ``data`` is an empty list when :attr:`data_source_id` is
            empty (types that override :meth:`_is_data_source_required`
            to return ``False``), instead of fetching anything. Also
            carries ``comparison_data`` — list of list of dict, one
            list per comparison range — when :attr:`data_source_id` is
            filled in and its ``comparison`` field is set to anything
            other than ``none``; absent entirely otherwise, so an item
            pulling from a data source without comparison configured
            (or without a data source at all) pays no extra query
            cost. Also carries ``goal`` — result of
            :meth:`_get_goal_value` for today's date — when
            :attr:`goal_type` is anything other than ``none``; absent
            entirely otherwise, so an item without a target configured
            pays no extra cost.
        :rtype: dict
        """
        self.ensure_one()
        payload = {
            "id": self.id,
            "name": self.name,
            "type": self.type,
            "column_width": self.column_width,
            "row_height": self.row_height,
            "active": self.active,
            "data": self.data_source_id._fetch_data(self)
            if self.data_source_id
            else [],
            "number_format_config": self._get_number_format_config(),
        }
        if self.data_source_id and self.data_source_id.comparison != "none":
            payload["comparison_data"] = self.data_source_id._fetch_comparison_data(
                self
            )
        if self.goal_type != "none":
            payload["goal"] = self._get_goal_value(fields.Date.context_today(self))
        enrich_method = getattr(self, f"_prepare_render_payload_{self.type}", None)
        if enrich_method is not None:
            payload = enrich_method(payload)
        return payload
