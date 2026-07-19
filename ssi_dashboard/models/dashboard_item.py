# Copyright 2026 OpenSynergy Indonesia
# Copyright 2026 PT. Simetri Sinergi Indonesia
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from odoo import fields, models


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
            extra query cost.
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
        enrich_method = getattr(self, f"_prepare_render_payload_{self.type}", None)
        if enrich_method is not None:
            payload = enrich_method(payload)
        return payload
