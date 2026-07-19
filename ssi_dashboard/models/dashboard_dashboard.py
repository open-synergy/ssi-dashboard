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
    dashboard.

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

    def get_dashboard_payload(self):
        """Build the payload the browser uses to render this dashboard.

        This is the single entry point called from the browser side.

        :return: dict with keys ``id``, ``name``, ``color_scheme`` (result
            of :meth:`dashboard.color_scheme._prepare_css_variables`, or
            ``{}`` when :attr:`color_scheme_id` is empty) and ``items``
            (list of :meth:`dashboard.item._prepare_render_payload`
            results, ordered by ``sequence``).
        :rtype: dict
        """
        self.ensure_one()
        color_scheme = (
            self.color_scheme_id._prepare_css_variables()
            if self.color_scheme_id
            else {}
        )
        items = self.item_ids.sorted("sequence")
        return {
            "id": self.id,
            "name": self.name,
            "color_scheme": color_scheme,
            "items": [item._prepare_render_payload() for item in items],
        }

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
