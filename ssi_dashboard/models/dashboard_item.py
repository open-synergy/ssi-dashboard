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
        required=True,
        ondelete="restrict",
        help="Data source this item pulls its data from.",
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

    def _prepare_render_payload(self):
        """Build the payload the browser uses to render this item.

        Fetches the item's data through :attr:`data_source_id`, then
        dispatches to ``self._prepare_render_payload_<type>(payload)`` when
        that method exists, so extension modules can enrich the payload
        with type-specific keys. When no such method exists, the base
        payload is returned as-is.

        :return: dict with keys ``id``, ``name``, ``type``,
            ``column_width``, ``row_height``, ``active`` and ``data``.
            Also carries ``comparison_data`` — list of list of dict,
            one list per comparison range — when :attr:`data_source_id`
            has its ``comparison`` field set to anything other than
            ``none``; absent entirely otherwise, so an item pulling
            from a data source without comparison configured pays no
            extra query cost. Also carries ``goal`` — result of
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
            "data": self.data_source_id._fetch_data(self),
        }
        if self.data_source_id.comparison != "none":
            payload["comparison_data"] = self.data_source_id._fetch_comparison_data(
                self
            )
        if self.goal_type != "none":
            payload["goal"] = self._get_goal_value(fields.Date.context_today(self))
        enrich_method = getattr(self, f"_prepare_render_payload_{self.type}", None)
        if enrich_method is not None:
            payload = enrich_method(payload)
        return payload
