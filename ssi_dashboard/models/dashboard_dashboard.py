# Copyright 2026 OpenSynergy Indonesia
# Copyright 2026 PT. Simetri Sinergi Indonesia
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from odoo import api, fields, models
from odoo.exceptions import UserError


class DashboardDashboard(models.Model):
    """Represents a configurable dashboard: a named grid of items, each
    backed by a data source, optionally styled with a color scheme and
    restricted to a set of user groups. :meth:`get_dashboard_payload` is
    the single entry point the browser side calls to render one
    dashboard, and :meth:`save_layout` is the single entry point it
    calls to persist positions/sizes arranged through the drag-and-resize
    layout editor.

    When :attr:`generate_menu` is set, :meth:`_sync_menu` keeps a matching
    ``ir.ui.menu``/``ir.actions.client`` pair (:attr:`menu_id`,
    :attr:`client_action_id`) in sync so the dashboard also shows up as a
    regular menu item, not just a button on this form."""

    _name = "dashboard.dashboard"
    _inherit = [
        "mixin.master_data",
    ]
    _description = "Dashboard"

    # Fields that feed the generated menu/action: writing any of these
    # re-runs _sync_menu() so a plain save that touches none of them never
    # has to touch ir.ui.menu/ir.actions.client.
    _menu_sync_fields = {
        "name",
        "generate_menu",
        "menu_name",
        "parent_menu_id",
        "menu_sequence",
        "group_ids",
    }

    _dashboard_dashboard_code_uniq = models.Constraint(
        "UNIQUE(code)",
        "Another dashboard with that code already exists.",
    )

    color_scheme_id = fields.Many2one(
        comodel_name="dashboard.color_scheme",
        ondelete="restrict",
        help="Color scheme applied when rendering this dashboard. Left "
        "empty to render with the default browser styling.",
    )
    item_ids = fields.One2many(
        string="Items",
        comodel_name="dashboard.item",
        inverse_name="dashboard_id",
        help="Tiles placed on this dashboard.",
    )
    filter_ids = fields.One2many(
        string="Filters",
        comodel_name="dashboard.filter",
        inverse_name="dashboard_id",
        help="Entries of this dashboard's global filter bar. Each active "
        "filter narrows every item's data on top of that item's own "
        "data source configuration.",
    )
    group_ids = fields.Many2many(
        string="Allowed Groups",
        comodel_name="res.groups",
        help="Groups allowed to view this dashboard. Leave empty to allow "
        "every user with the Dashboard User access right.",
    )
    generate_menu = fields.Boolean(
        default=False,
        help="When enabled, this dashboard also shows up as its own menu "
        "item under 'Parent Menu', in addition to being reachable from "
        "the 'Open Dashboard' button here.",
    )
    menu_name = fields.Char(
        help="Label of the generated menu item. Leave empty to reuse this "
        "dashboard's 'Name'.",
    )
    parent_menu_id = fields.Many2one(
        comodel_name="ir.ui.menu",
        ondelete="restrict",
        help="Menu the generated menu item is placed under. Required when "
        "'Generate Menu' is enabled.",
    )
    menu_sequence = fields.Integer(
        default=10,
        help="Determines the display order of the generated menu item "
        "among its siblings under 'Parent Menu'.",
    )
    menu_id = fields.Many2one(
        string="Generated Menu",
        comodel_name="ir.ui.menu",
        readonly=True,
        ondelete="set null",
        help="Menu item generated for this dashboard. Managed by "
        "'_sync_menu', do not edit manually.",
    )
    client_action_id = fields.Many2one(
        string="Generated Client Action",
        comodel_name="ir.actions.client",
        readonly=True,
        ondelete="set null",
        help="Client action generated for this dashboard's menu item. "
        "Managed by '_sync_menu', do not edit manually.",
    )
    refresh_interval = fields.Selection(
        string="Auto-Refresh Interval",
        selection=[
            ("0", "Off"),
            ("30", "30 Seconds"),
            ("60", "1 Minute"),
            ("300", "5 Minutes"),
            ("600", "10 Minutes"),
            ("1800", "30 Minutes"),
        ],
        default="0",
        required=True,
        help="How often the browser automatically re-fetches this "
        "dashboard's data while it is open. 'Off' disables automatic "
        "refresh; the manual reload button is always available "
        "regardless of this setting.",
    )
    fullscreen_enabled = fields.Boolean(
        default=True,
        help="Whether the browser shows a button to display this "
        "dashboard in fullscreen mode, hiding the surrounding Odoo "
        "backend chrome while keeping the filter bar and reload button "
        "available.",
    )

    @api.constrains("generate_menu", "parent_menu_id")
    def _check_generate_menu_parent(self):
        for dashboard in self.sudo():
            if not dashboard._check_generate_menu_parent_condition():
                error_message = f"""
Document Type: {dashboard._description}
Context: Create or update dashboard
Database ID: {dashboard.id}
Problem: 'Generate Menu' is enabled but 'Parent Menu' is empty
Solution: Set 'Parent Menu' or disable 'Generate Menu'
"""
                raise UserError(error_message)

    def _check_generate_menu_parent_condition(self):
        self.ensure_one()
        if not self.generate_menu:
            return True
        return bool(self.parent_menu_id)

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for record in records:
            record._sync_menu()
        return records

    def write(self, vals):
        result = super().write(vals)
        if self._menu_sync_fields & set(vals):
            for record in self:
                record._sync_menu()
        return result

    def unlink(self):
        for record in self:
            if record.menu_id:
                record.menu_id.sudo().unlink()
            if record.client_action_id:
                record.client_action_id.sudo().unlink()
        return super().unlink()

    def _sync_menu(self):
        """Reconcile :attr:`menu_id`/:attr:`client_action_id` with the
        dashboard's current 'Generate Menu' fields.

        Single entry point for all three directions: creates the menu/
        action when :attr:`generate_menu` is set and none exist yet,
        updates their name/parent/sequence/groups when they already
        exist, and removes both when :attr:`generate_menu` is turned off.
        Runs entirely through ``sudo()`` because a user in
        ``group_dashboard_admin`` has full CRUD on ``dashboard.dashboard``
        but not necessarily on ``ir.ui.menu``/``ir.actions.client``.

        :return: None
        """
        self.ensure_one()
        record = self.sudo()
        if not record.generate_menu:
            vals = {}
            if record.menu_id:
                record.menu_id.unlink()
                vals["menu_id"] = False
            if record.client_action_id:
                record.client_action_id.unlink()
                vals["client_action_id"] = False
            if vals:
                record.write(vals)
            return
        menu_name = record.menu_name or record.name
        if not record.client_action_id:
            client_action = (
                self.env["ir.actions.client"]
                .sudo()
                .create(
                    {
                        "name": menu_name,
                        "tag": "ssi_dashboard.dashboard_view",
                        "context": repr({"dashboard_id": record.id}),
                    }
                )
            )
            record.write({"client_action_id": client_action.id})
        else:
            record.client_action_id.write({"name": menu_name})
        menu_values = {
            "name": menu_name,
            "parent_id": record.parent_menu_id.id,
            "sequence": record.menu_sequence,
            "group_ids": [(6, 0, record.group_ids.ids)],
        }
        if not record.menu_id:
            menu_values["action"] = f"ir.actions.client,{record.client_action_id.id}"
            menu = self.env["ir.ui.menu"].sudo().create(menu_values)
            record.write({"menu_id": menu.id})
        else:
            record.menu_id.write(menu_values)

    def get_dashboard_payload(self, active_filters=None):
        """Build the payload the browser uses to render this dashboard.

        This is the single entry point called from the browser side.

        :param active_filters: optional dict describing the filter bar's
            current selection, with keys:

            - ``filter_ids`` — list of active ``dashboard.filter`` ids.
            - ``date_start``, ``date_end`` — ISO date strings or
              ``None``, overriding the date range of every item's data
              source that has a ``date_field_id`` set (see
              ``dashboard.data_source._prepare_date_domain``).

            ``None`` (the default) means "use this dashboard's filters
            with ``default_active`` set to True, and no date override" —
            see :meth:`_resolve_active_filters` — so a call made before
            this argument existed keeps behaving exactly the same.
        :type active_filters: dict or None
        :return: dict with keys ``id``, ``name``, ``color_scheme`` (result
            of :meth:`dashboard.color_scheme._prepare_css_variables`, or
            ``{}`` when :attr:`color_scheme_id` is empty), ``filters``
            (list of :meth:`dashboard.filter._prepare_filter_payload`
            results, ordered by ``sequence`` — the filter bar's
            definitions), ``active_filter_ids`` (the resolved
            ``filter_ids`` from :meth:`_resolve_active_filters`, so the
            browser can pre-select them), ``refresh_interval`` (int,
            :attr:`refresh_interval` converted to seconds; ``0`` means
            auto-refresh is off), ``fullscreen_enabled`` (bool,
            :attr:`fullscreen_enabled` as-is) and ``items`` (list of
            :meth:`dashboard.item._prepare_render_payload` results,
            ordered by ``sequence``, each filtered per
            ``active_filters``).
        :rtype: dict
        """
        self.ensure_one()
        resolved_filters = self._resolve_active_filters(active_filters)
        color_scheme = (
            self.color_scheme_id._prepare_css_variables()
            if self.color_scheme_id
            else {}
        )
        items = self.item_ids.sorted("sequence")
        filters = self.filter_ids.sorted("sequence")
        return {
            "id": self.id,
            "name": self.name,
            "color_scheme": color_scheme,
            "filters": [filter_._prepare_filter_payload() for filter_ in filters],
            "active_filter_ids": resolved_filters["filter_ids"],
            "refresh_interval": int(self.refresh_interval),
            "fullscreen_enabled": self.fullscreen_enabled,
            "items": [
                item._prepare_render_payload(active_filters=resolved_filters)
                for item in items
            ],
        }

    def _resolve_active_filters(self, active_filters):
        """Normalize the ``active_filters`` argument of
        :meth:`get_dashboard_payload` into the dict form propagated down
        to every item/data source.

        :param active_filters: see :meth:`get_dashboard_payload`.
        :type active_filters: dict or None
        :return: dict with keys ``filter_ids`` (list of int),
            ``date_start`` and ``date_end`` (str or None). When
            ``active_filters`` is ``None``, ``filter_ids`` is this
            dashboard's :attr:`filter_ids` filtered on
            ``default_active`` and both dates are ``None`` (no
            override) — otherwise, each key is read from
            ``active_filters`` as given (missing/falsy ``filter_ids``
            becomes an empty list).
        :rtype: dict
        """
        self.ensure_one()
        if active_filters is None:
            default_filters = self.filter_ids.filtered("default_active")
            return {
                "filter_ids": default_filters.ids,
                "date_start": None,
                "date_end": None,
            }
        return {
            "filter_ids": list(active_filters.get("filter_ids") or []),
            "date_start": active_filters.get("date_start"),
            "date_end": active_filters.get("date_end"),
        }

    def save_layout(self, layout):
        """Persist a dashboard layout arranged through the browser's
        drag-and-resize layout editor.

        Called from the browser side (see
        ``static/src/dashboard_layout_editor/dashboard_layout_editor.esm.js``)
        once the user presses 'Save' in the editor. Restricted to
        :meth:`_check_save_layout_access` regardless of what the browser
        side hides/shows, and to items that actually belong to this
        dashboard (see :meth:`_check_layout_item_ids`) — otherwise a
        user able to call this method could overwrite the coordinates
        of items on a dashboard they are not editing.

        :param layout: list of dict, one per repositioned/resized item,
            each with keys ``id`` (int, a ``dashboard.item`` id that
            must belong to :attr:`item_ids`), ``column_start``,
            ``row_start``, ``column_width`` and ``row_height`` (int) —
            the new values written to that item's fields of the same
            name. Range constraints on those fields (see
            ``models/dashboard_item.py``) still apply and raise
            ``ValidationError`` when violated.
        :type layout: list of dict
        :return: ``True``
        :rtype: bool
        """
        self.ensure_one()
        self._check_save_layout_access()
        items_by_id = {item.id: item for item in self.item_ids}
        self._check_layout_item_ids(layout, items_by_id)
        for entry in layout:
            items_by_id[entry["id"]].write(
                {
                    "column_start": entry["column_start"],
                    "row_start": entry["row_start"],
                    "column_width": entry["column_width"],
                    "row_height": entry["row_height"],
                }
            )
        return True

    def _check_save_layout_access(self):
        """Raise ``UserError`` unless the current user belongs to
        ``group_dashboard_admin``.

        Called by :meth:`save_layout` itself so the restriction applies
        no matter how the method is reached — an RPC call bypassing the
        browser's own 'Edit Layout' button visibility would otherwise
        let a plain 'Dashboard User' overwrite the layout despite having
        read-only access rights on ``dashboard.item``.

        :return: None
        """
        self.ensure_one()
        if not self.env.user.has_group("ssi_dashboard.group_dashboard_admin"):
            error_message = f"""
Context: Save dashboard layout
Database ID: {self.id}
Problem: Current user is not a member of the 'Administrator' dashboard \
group
Solution: Ask a dashboard administrator to save the layout, or request \
'Administrator' access
"""
            raise UserError(error_message)

    def _check_layout_item_ids(self, layout, items_by_id):
        """Raise ``UserError`` when ``layout`` names an ``id`` that is
        not a key of ``items_by_id`` — i.e. an item that does not
        belong to this dashboard.

        Runs fully before :meth:`save_layout` writes anything, so a
        ``layout`` naming one foreign id leaves every item of this
        dashboard untouched instead of partially applying.

        :param layout: see :meth:`save_layout`.
        :type layout: list of dict
        :param items_by_id: this dashboard's :attr:`item_ids` indexed by
            ``id``, as built by :meth:`save_layout`.
        :type items_by_id: dict
        :return: None
        """
        self.ensure_one()
        for entry in layout:
            if entry["id"] not in items_by_id:
                error_message = f"""
Context: Save dashboard layout
Database ID: {self.id}
Problem: Item ID {entry["id"]} sent in 'layout' does not belong to \
this dashboard
Solution: Reload the dashboard and try arranging the layout again
"""
                raise UserError(error_message)

    def action_open_dashboard(self):
        for record in self.sudo():
            result = record._open_dashboard()
        return result

    def _open_dashboard(self):
        """Build the client action that opens this dashboard in the browser.

        :return: dict describing an ``ir.actions.client`` bound to the
            OWL client action registered under the
            ``ssi_dashboard.dashboard_view`` tag, with :attr:`id` passed
            through ``context['dashboard_id']`` so the browser side knows
            which dashboard to fetch via :meth:`get_dashboard_payload`.
        :rtype: dict
        """
        self.ensure_one()
        return {
            "type": "ir.actions.client",
            "tag": "ssi_dashboard.dashboard_view",
            "name": self.name,
            "context": {"dashboard_id": self.id},
        }
