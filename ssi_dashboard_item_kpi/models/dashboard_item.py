# Copyright 2026 OpenSynergy Indonesia
# Copyright 2026 PT. Simetri Sinergi Indonesia
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from odoo import api, fields, models
from odoo.exceptions import ValidationError

_KPI_ROW_KEY_BLOCKLIST = (
    "group_key",
    "group_label",
    "sub_group_key",
    "sub_group_label",
)


class DashboardItem(models.Model):
    """Extends `dashboard.item` with the 'kpi' type: a realized value shown
    side by side with either its target (`goal_type`) or a comparison
    period (`data_source_id.comparison`), plus the achievement percentage
    and movement direction between the two. The aggregation itself
    (measure, grouping, comparison, target) is entirely computed by core
    `dashboard.item`/`dashboard.data_source` (see `_prepare_render_payload`,
    `_get_goal_value`, `_fetch_comparison_data`) — this module only reads
    the first row/first measure of what is already fetched and computes
    the comparison numbers for its own two layouts."""

    _name = "dashboard.item"
    _inherit = [
        "dashboard.item",
    ]

    type = fields.Selection(
        selection_add=[
            ("kpi", "KPI"),
        ],
        ondelete={"kpi": "set default"},
    )
    kpi_layout = fields.Selection(
        selection=[
            ("target", "KPI With Target"),
            ("comparison", "Data Comparison"),
        ],
        required=True,
        default="target",
        help="Arrangement the browser renders this KPI in. Only used "
        "when 'Type' is 'KPI'. 'KPI With Target' compares 'Value' "
        "against today's target (see 'Goal Type' / '_get_goal_value') "
        "and requires 'Goal Type' to be set to something other than "
        "'No Target'. 'Data Comparison' compares 'Value' against the "
        "first comparison range of 'Data Source', and requires 'Data "
        "Source''s 'Comparison' to be set to something other than 'No "
        "Comparison'.",
    )
    kpi_display = fields.Selection(
        selection=[
            ("number", "Number"),
            ("percentage", "Percentage"),
            ("ratio", "Ratio"),
        ],
        required=True,
        default="percentage",
        help="Shape of the comparison number shown alongside 'Value'. "
        "Only used when 'Type' is 'KPI'.",
    )
    kpi_invert_direction = fields.Boolean(
        default=False,
        help="Tick when a decrease in 'Value' is actually an improvement, "
        "e.g. a count of complaints, so the movement marker is flipped. "
        "Only used when 'Type' is 'KPI'.",
    )

    @api.constrains("type", "kpi_layout", "goal_type")
    def _check_kpi_layout_target_requires_goal(self):
        for item in self:
            if (
                item.type == "kpi"
                and item.kpi_layout == "target"
                and item.goal_type == "none"
            ):
                error_message = f"""
Context: Configure dashboard item kpi layout
Database ID: {item.id}
Problem: 'KPI Layout' is set to 'KPI With Target' but 'Goal Type' is 'No \
Target'
Solution: Set 'Goal Type' to 'Fixed Value' or 'Dated Targets', or choose a \
different 'KPI Layout'
"""
                raise ValidationError(error_message)

    @api.constrains("type", "kpi_layout", "data_source_id")
    def _check_kpi_layout_comparison_requires_comparison(self):
        for item in self:
            if (
                item.type == "kpi"
                and item.kpi_layout == "comparison"
                and item.data_source_id.comparison == "none"
            ):
                error_message = f"""
Context: Configure dashboard item kpi layout
Database ID: {item.id}
Problem: 'KPI Layout' is set to 'Data Comparison' but 'Comparison' on \
'Data Source' ('{item.data_source_id.name}') is 'No Comparison'
Solution: Set 'Comparison' on 'Data Source' ('{item.data_source_id.name}') \
to a value other than 'No Comparison', or choose a different 'KPI Layout'
"""
                raise ValidationError(error_message)

    def _prepare_render_payload_kpi(self, payload):
        """Enrich the render payload of a 'kpi' item.

        :param payload: dict built by
            :meth:`dashboard.item._prepare_render_payload`.
        :return: `payload`, with a 'kpi' key added — dict with 'layout'
            (:attr:`kpi_layout`), 'display' (:attr:`kpi_display`),
            'invert_direction' (:attr:`kpi_invert_direction`), 'value'
            (see :meth:`_get_kpi_value`), 'reference' (see
            :meth:`_get_kpi_reference`), 'achievement' ('value' /
            'reference' as a float, ``None`` when 'reference' is zero,
            so the browser shows a dash instead of dividing by zero) and
            'direction' (``"up"``/``"down"``/``"flat"``, see
            :meth:`_get_kpi_direction`).
        :rtype: dict
        """
        self.ensure_one()
        value = self._get_kpi_value(payload.get("data") or [])
        reference = self._get_kpi_reference(payload)
        payload["kpi"] = {
            "layout": self.kpi_layout,
            "display": self.kpi_display,
            "invert_direction": self.kpi_invert_direction,
            "value": value,
            "reference": reference,
            "achievement": (value / reference) if reference else None,
            "direction": self._get_kpi_direction(value, reference),
        }
        return payload

    def _get_kpi_value(self, rows):
        """Pick the single realized number out of `rows`.

        Reads the first measure column of the first row, skipping the
        grouping metadata keys ('group_key', 'group_label',
        'sub_group_key', 'sub_group_label') that
        :meth:`dashboard.data_source._fetch_data_orm` adds when a 'Group
        By Field' is configured — mirrors
        `ssi_dashboard_item_tile`'s `_get_tile_value`.

        :param rows: list of dict — either the item's own fetched data
            (``payload["data"]``) or one comparison range's rows
            (one entry of ``payload["comparison_data"]``).
        :return: the first row's first measure value, or ``0.0`` when
            `rows` is empty or its first row has no measure column.
        :rtype: float
        """
        if not rows:
            return 0.0
        first_row = rows[0]
        for key, value in first_row.items():
            if key in _KPI_ROW_KEY_BLOCKLIST:
                continue
            return value or 0.0
        return 0.0

    def _get_kpi_reference(self, payload):
        """Compute the number :meth:`_get_kpi_value`'s result is compared
        against, following :attr:`kpi_layout`.

        :param payload: dict built by
            :meth:`dashboard.item._prepare_render_payload`, as seen by
            :meth:`_prepare_render_payload_kpi` before it adds the 'kpi'
            key.
        :return: today's target (:meth:`dashboard.item._get_goal_value`)
            when :attr:`kpi_layout` is ``target`` — guaranteed available
            since :meth:`_check_kpi_layout_target_requires_goal` rejects
            saving a ``target`` item without a target configured. The
            first row of the first comparison range
            (``payload["comparison_data"][0]``, read the same way as
            `value` — see :meth:`_get_kpi_value`) when ``comparison`` —
            guaranteed available the same way by
            :meth:`_check_kpi_layout_comparison_requires_comparison`.
        :rtype: float
        """
        self.ensure_one()
        if self.kpi_layout == "target":
            return self._get_goal_value(fields.Date.context_today(self))
        comparison_data = payload.get("comparison_data") or []
        first_range_rows = comparison_data[0] if comparison_data else []
        return self._get_kpi_value(first_range_rows)

    def _get_kpi_direction(self, value, reference):
        """Compute the movement marker between `value` and `reference`.

        :param value: :meth:`_get_kpi_value`'s result.
        :type value: float
        :param reference: :meth:`_get_kpi_reference`'s result.
        :type reference: float
        :return: ``"up"`` when `value` is greater than `reference`,
            ``"down"`` when smaller, ``"flat"`` when equal — with
            ``"up"``/``"down"`` swapped when :attr:`kpi_invert_direction`
            is set, so a metric where lower is better (e.g. a complaint
            count) still shows an "up" marker for an improvement.
        :rtype: str
        """
        self.ensure_one()
        if value > reference:
            direction = "up"
        elif value < reference:
            direction = "down"
        else:
            direction = "flat"
        if self.kpi_invert_direction and direction != "flat":
            direction = "down" if direction == "up" else "up"
        return direction
