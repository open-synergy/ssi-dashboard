# Copyright 2026 OpenSynergy Indonesia
# Copyright 2026 PT. Simetri Sinergi Indonesia
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
import json

from odoo import fields, models
from odoo.exceptions import UserError

_VALID_AGGREGATES = ("sum", "avg", "min", "max", "count")
_DEFAULT_AGGREGATE = "count"


class DashboardItem(models.Model):
    """Extends `dashboard.item` with the 'tile' type: a single aggregate
    number, plus its label, computed from the item's fetched data. Adds no
    field of its own to :attr:`type` beyond the selection value — the
    aggregation reads 'measure' and 'aggregate' out of the item's existing
    `config` JSON field."""

    _name = "dashboard.item"
    _inherit = [
        "dashboard.item",
    ]

    type = fields.Selection(
        selection_add=[
            ("tile", "Tile"),
        ],
        ondelete={"tile": "set default"},
    )

    def _prepare_render_payload_tile(self, payload):
        """Enrich the render payload of a 'tile' item.

        Reads 'measure' (field name to aggregate) and 'aggregate' (one of
        'sum', 'avg', 'min', 'max', 'count') out of :attr:`config` (JSON).
        Defaults to 'count' when `config` is empty or names neither key.

        :param payload: dict built by
            :meth:`dashboard.item._prepare_render_payload`.
        :return: `payload`, with 'value' (the aggregated number) and
            'label' (this item's :attr:`name`) added.
        :rtype: dict
        :raises UserError: when :attr:`config` is set but is not valid
            JSON, or is valid JSON that is not an object.
        """
        self.ensure_one()
        measure, aggregate = self._get_tile_measure_and_aggregate()
        data = payload.get("data") or []
        payload["value"] = self._compute_tile_value(data, measure, aggregate)
        payload["label"] = self.name
        return payload

    def _get_tile_measure_and_aggregate(self):
        """Parse this item's :attr:`config` for the 'tile' item type.

        :return: tuple ``(measure, aggregate)`` — `measure` is the field
            name to aggregate (``None`` when not configured), `aggregate`
            is one of 'sum'/'avg'/'min'/'max'/'count', defaulting to
            'count'.
        :rtype: tuple
        :raises UserError: when :attr:`config` is set but is not valid
            JSON, or is valid JSON that is not an object.
        """
        self.ensure_one()
        if not self.config:
            return None, _DEFAULT_AGGREGATE
        try:
            config = json.loads(self.config)
        except ValueError as parse_error:
            error_message = f"""
Context: Render dashboard item 'tile' payload
Database ID: {self.id}
Problem: 'Config' is not valid JSON ({parse_error})
Solution: Fix the JSON syntax in the 'Config' field, e.g. \
{{"measure": "amount", "aggregate": "sum"}}
"""
            raise UserError(error_message) from parse_error
        if not isinstance(config, dict):
            error_message = f"""
Context: Render dashboard item 'tile' payload
Database ID: {self.id}
Problem: 'Config' is valid JSON but is not a JSON object
Solution: Set 'Config' to a JSON object, e.g. \
{{"measure": "amount", "aggregate": "sum"}}
"""
            raise UserError(error_message)
        measure = config.get("measure")
        aggregate = config.get("aggregate") or _DEFAULT_AGGREGATE
        if aggregate not in _VALID_AGGREGATES:
            error_message = f"""
Context: Render dashboard item 'tile' payload
Database ID: {self.id}
Problem: 'Config' key 'aggregate' has unsupported value '{aggregate}'
Solution: Set 'aggregate' to one of: {", ".join(_VALID_AGGREGATES)}
"""
            raise UserError(error_message)
        return measure, aggregate

    def _compute_tile_value(self, data, measure, aggregate):
        """Aggregate `data` into the single number a tile displays.

        :param data: list of dict, the item's fetched data
            (``payload["data"]``).
        :param measure: field name to read out of each row of `data`,
            used by every `aggregate` except 'count'. Rows missing this
            key, or whose value is ``None``, are skipped.
        :param aggregate: one of 'sum', 'avg', 'min', 'max', 'count'.
        :return: the aggregated number. 0 when `aggregate` needs values
            but none are found.
        :rtype: int or float
        """
        if aggregate == "count":
            return len(data)
        values = [
            row[measure]
            for row in data
            if measure and measure in row and row[measure] is not None
        ]
        if not values:
            return 0
        if aggregate == "sum":
            return sum(values)
        if aggregate == "avg":
            return sum(values) / len(values)
        if aggregate == "min":
            return min(values)
        return max(values)
