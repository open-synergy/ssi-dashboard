# Copyright 2026 OpenSynergy Indonesia
# Copyright 2026 PT. Simetri Sinergi Indonesia
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from odoo import api, fields, models
from odoo.exceptions import ValidationError

_TILE_ROW_KEY_BLOCKLIST = (
    "group_key",
    "group_label",
    "sub_group_key",
    "sub_group_label",
)


class DashboardItem(models.Model):
    """Extends `dashboard.item` with the 'tile' type: a single aggregate
    number, plus its label, rendered in one of six layouts
    (:attr:`tile_layout`). The aggregation itself (measure/aggregate,
    grouping, comparison, target) is entirely computed by core
    `dashboard.item`/`dashboard.data_source` (see
    `_prepare_render_payload`/`_fetch_data`) — this module only picks the
    first row of the fetched data and formats/decorates it for its own
    layout."""

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
    tile_layout = fields.Selection(
        selection=[
            ("layout_1", "Value Only"),
            ("layout_2", "Value With Icon"),
            ("layout_3", "Value With Comparison"),
            ("layout_4", "Value With Target"),
            ("layout_5", "Value With Sparkline"),
            ("layout_6", "Value With Background Icon"),
        ],
        required=True,
        default="layout_1",
        help="Arrangement the browser renders this tile in. Only used "
        "when 'Type' is 'Tile'. 'Value With Comparison' requires the "
        "'Data Source''s 'Comparison' to be set. 'Value With Target' "
        "requires 'Goal Type' to be set.",
    )
    tile_icon = fields.Char(
        help="Font Awesome icon class already bundled with the Odoo "
        "backend, e.g. 'fa-shopping-cart'. Only used, and only shown, "
        "when 'Type' is 'Tile' and 'Tile Layout' is 'Value With Icon' or "
        "'Value With Background Icon'. Left empty, no icon is rendered.",
    )
    tile_background_color = fields.Char(
        help="CSS color value used as this tile's background. Only used "
        "when 'Type' is 'Tile'. Left empty, the dashboard's own "
        "'--ssi-dashboard-surface' color scheme variable is used instead.",
    )
    tile_text_color = fields.Char(
        help="CSS color value used for this tile's text. Only used when "
        "'Type' is 'Tile'. Left empty, the dashboard's own "
        "'--ssi-dashboard-text' color scheme variable is used instead.",
    )

    @api.constrains("type", "tile_layout", "goal_type")
    def _check_tile_layout_target_requires_goal(self):
        for item in self:
            if (
                item.type == "tile"
                and item.tile_layout == "layout_4"
                and item.goal_type == "none"
            ):
                error_message = f"""
Context: Configure dashboard item tile layout
Database ID: {item.id}
Problem: 'Tile Layout' is set to 'Value With Target' but 'Goal Type' is \
'No Target'
Solution: Set 'Goal Type' to 'Fixed Value' or 'Dated Targets', or choose a \
different 'Tile Layout'
"""
                raise ValidationError(error_message)

    @api.constrains("type", "tile_layout", "data_source_id")
    def _check_tile_layout_comparison_requires_comparison(self):
        for item in self:
            if (
                item.type == "tile"
                and item.tile_layout == "layout_3"
                and item.data_source_id.comparison == "none"
            ):
                error_message = f"""
Context: Configure dashboard item tile layout
Database ID: {item.id}
Problem: 'Tile Layout' is set to 'Value With Comparison' but 'Comparison' \
on 'Data Source' ('{item.data_source_id.name}') is 'No Comparison'
Solution: Set 'Comparison' on 'Data Source' to a value other than 'No \
Comparison', or choose a different 'Tile Layout'
"""
                raise ValidationError(error_message)

    def _prepare_render_payload_tile(self, payload):
        """Enrich the render payload of a 'tile' item.

        Adds this item's own tile configuration fields, plus 'value' — the
        single number a tile displays, taken from the first row of
        ``payload["data"]``. When the data source returns more than one
        row (e.g. it has a 'Group By Field' configured), every row after
        the first is ignored: a tile is a single number, not a table.

        :param payload: dict built by
            :meth:`dashboard.item._prepare_render_payload`.
        :return: `payload`, with 'tile_layout', 'tile_icon',
            'tile_background_color', 'tile_text_color' (this item's own
            fields) and 'value' (see :meth:`_get_tile_value`) added.
        :rtype: dict
        """
        self.ensure_one()
        data = payload.get("data") or []
        payload["tile_layout"] = self.tile_layout
        payload["tile_icon"] = self.tile_icon
        payload["tile_background_color"] = self.tile_background_color
        payload["tile_text_color"] = self.tile_text_color
        payload["value"] = self._get_tile_value(data)
        return payload

    def _get_tile_value(self, data):
        """Pick the single number a tile displays out of fetched `data`.

        Reads the first measure column of the first row of `data`,
        skipping the grouping metadata keys ('group_key', 'group_label',
        'sub_group_key', 'sub_group_label') that
        :meth:`dashboard.data_source._fetch_data_orm` adds when a
        'Group By Field' is configured — so a tile still renders a single
        number even when its data source is grouped, using whichever
        group happens to come first.

        :param data: list of dict, the item's fetched data
            (``payload["data"]``).
        :return: the first row's first measure value, or ``0`` when
            `data` is empty or its first row has no measure column.
        :rtype: int or float
        """
        if not data:
            return 0
        first_row = data[0]
        for key, value in first_row.items():
            if key in _TILE_ROW_KEY_BLOCKLIST:
                continue
            return value or 0
        return 0
