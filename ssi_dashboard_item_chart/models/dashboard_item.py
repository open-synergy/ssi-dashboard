# Copyright 2026 OpenSynergy Indonesia
# Copyright 2026 PT. Simetri Sinergi Indonesia
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
import json

from odoo import fields, models
from odoo.exceptions import UserError

_VALID_CHART_TYPES = ("bar", "line", "pie")
_DEFAULT_CHART_TYPE = "bar"


class DashboardItem(models.Model):
    """Extends `dashboard.item` with the 'chart' type: a bar, line or pie
    chart built from data grouped by one field ('group_by') and, optionally,
    aggregated over another ('measure') — both read out of the item's
    existing `config` JSON field. Adds no field of its own to :attr:`type`
    beyond the selection value."""

    _name = "dashboard.item"
    _inherit = [
        "dashboard.item",
    ]

    type = fields.Selection(
        selection_add=[
            ("chart", "Chart"),
        ],
        ondelete={"chart": "set default"},
    )

    def _prepare_render_payload_chart(self, payload):
        """Enrich the render payload of a 'chart' item.

        Reads 'chart_type' (one of 'bar', 'line', 'pie', defaulting to
        'bar'), 'group_by' (required field name) and 'measure' (optional
        field name to sum; counts records per group when empty) out of
        :attr:`config` (JSON).

        :param payload: dict built by
            :meth:`dashboard.item._prepare_render_payload`.
        :return: `payload`, with 'chart_type' (str) and 'chart_data' (dict
            with keys 'labels' and 'datasets', see
            :meth:`_compute_chart_data`) added.
        :rtype: dict
        :raises UserError: when :attr:`config` is missing, is not valid
            JSON, is valid JSON that is not an object, names no
            'group_by', or names a 'chart_type' outside 'bar'/'line'/'pie'.
        """
        self.ensure_one()
        chart_type, group_by, measure = self._get_chart_config()
        data = payload.get("data") or []
        payload["chart_type"] = chart_type
        payload["chart_data"] = self._compute_chart_data(data, group_by, measure)
        return payload

    def _get_chart_config(self):
        """Parse this item's :attr:`config` for the 'chart' item type.

        :return: tuple ``(chart_type, group_by, measure)`` — `chart_type`
            is one of 'bar'/'line'/'pie', `group_by` is the field name
            rows are bucketed by, `measure` is the field name summed per
            group (``None`` when not configured, in which case each group
            is counted instead).
        :rtype: tuple
        :raises UserError: when :attr:`config` is missing, is not valid
            JSON, is valid JSON that is not an object, names no
            'group_by', or names a 'chart_type' outside 'bar'/'line'/'pie'.
        """
        self.ensure_one()
        config = self._parse_chart_config_json()
        chart_type = config.get("chart_type") or _DEFAULT_CHART_TYPE
        if chart_type not in _VALID_CHART_TYPES:
            error_message = f"""
Context: Render dashboard item 'chart' payload
Database ID: {self.id}
Problem: 'Config' key 'chart_type' has unsupported value '{chart_type}'
Solution: Set 'chart_type' to one of: {", ".join(_VALID_CHART_TYPES)}
"""
            raise UserError(error_message)
        group_by = config.get("group_by")
        if not group_by:
            error_message = f"""
Context: Render dashboard item 'chart' payload
Database ID: {self.id}
Problem: 'Config' does not name a 'group_by' field
Solution: Set 'group_by' to the field name to bucket rows by, e.g. \
{{"group_by": "state", "measure": "amount"}}
"""
            raise UserError(error_message)
        measure = config.get("measure") or None
        return chart_type, group_by, measure

    def _parse_chart_config_json(self):
        """Parse this item's :attr:`config` as a JSON object.

        :return: the parsed JSON object.
        :rtype: dict
        :raises UserError: when :attr:`config` is empty, is not valid
            JSON, or is valid JSON that is not an object.
        """
        self.ensure_one()
        if not self.config:
            error_message = f"""
Context: Render dashboard item 'chart' payload
Database ID: {self.id}
Problem: 'Config' is empty, but the 'chart' item type requires 'group_by'
Solution: Set 'Config' to a JSON object, e.g. \
{{"group_by": "state", "measure": "amount"}}
"""
            raise UserError(error_message)
        try:
            config = json.loads(self.config)
        except ValueError as parse_error:
            error_message = f"""
Context: Render dashboard item 'chart' payload
Database ID: {self.id}
Problem: 'Config' is not valid JSON ({parse_error})
Solution: Fix the JSON syntax in the 'Config' field, e.g. \
{{"group_by": "state", "measure": "amount"}}
"""
            raise UserError(error_message) from parse_error
        if not isinstance(config, dict):
            error_message = f"""
Context: Render dashboard item 'chart' payload
Database ID: {self.id}
Problem: 'Config' is valid JSON but is not a JSON object
Solution: Set 'Config' to a JSON object, e.g. \
{{"group_by": "state", "measure": "amount"}}
"""
            raise UserError(error_message)
        return config

    def _compute_chart_data(self, data, group_by, measure):
        """Group `data` into the labels/datasets structure a chart needs.

        Buckets rows of `data` by their `group_by` key, in first-seen
        order, then builds a single dataset out of `measure` (summed per
        group) or, when `measure` is empty, the row count per group.

        :param data: list of dict, the item's fetched data
            (``payload["data"]``).
        :param group_by: field name each row of `data` is bucketed by.
            Rows missing this key, or whose value is ``None``, are
            bucketed under an empty label.
        :param measure: field name to sum per group. Rows missing this
            key, or whose value is ``None``, contribute 0. When falsy,
            each group's value is its row count instead.
        :return: dict with keys 'labels' (list of str, one per group, in
            first-seen order) and 'datasets' (list holding a single dict —
            'label': this item's :attr:`name`, 'data': list of numbers,
            one per entry of 'labels', in the same order).
        :rtype: dict
        """
        labels = []
        values_by_label = {}
        for row in data:
            label = row.get(group_by)
            label = "" if label is None else str(label)
            if label not in values_by_label:
                labels.append(label)
                values_by_label[label] = 0
            if measure:
                value = row.get(measure)
                if value is not None:
                    values_by_label[label] += value
            else:
                values_by_label[label] += 1
        return {
            "labels": labels,
            "datasets": [
                {
                    "label": self.name,
                    "data": [values_by_label[label] for label in labels],
                }
            ],
        }
