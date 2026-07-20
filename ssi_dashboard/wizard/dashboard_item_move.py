# Copyright 2026 OpenSynergy Indonesia
# Copyright 2026 PT. Simetri Sinergi Indonesia
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from odoo import api, fields, models
from odoo.exceptions import UserError


class DashboardItemMove(models.TransientModel):
    """Wizard that moves or copies one or more ``dashboard.item`` records
    to a different ``dashboard.dashboard``.

    Bound to ``dashboard.item``'s list view through
    ``dashboard_item_move_action``'s ``binding_model_id`` — opened from
    the 'Action' menu with one or more items selected, which is what
    fills in :attr:`item_ids` (see :meth:`_default_item_ids`).

    'Move' (:meth:`_apply_move`) reassigns :attr:`item_ids` to
    :attr:`dashboard_id` in place — the items stop existing on their
    original dashboard. 'Copy' (:meth:`_apply_copy`) instead creates a
    full duplicate of each item (including its own
    :attr:`~dashboard.item.goal_ids`/:attr:`~dashboard.item.
    drilldown_ids`, via :meth:`dashboard.item._prepare_copy_vals`) on
    :attr:`dashboard_id`, leaving the originals untouched. Either way,
    every affected item's :attr:`~dashboard.item.column_start`/
    :attr:`~dashboard.item.row_start` is reset to ``0`` — see
    :meth:`_apply_move`/:meth:`_apply_copy` — so it never overlaps
    whatever is already laid out on the destination dashboard.

    A destination whose :attr:`~dashboard.dashboard.company_id` differs
    from an item's own data source company is rejected — not by this
    wizard directly, but for free through ``dashboard.item``'s own
    ``_check_data_source_company`` constraint, which already runs on
    any write/create that changes :attr:`~dashboard.item.dashboard_id`.
    """

    _name = "dashboard.item.move"
    _description = "Move / Copy Dashboard Item(s)"

    @api.model
    def _default_item_ids(self):
        """Read the list view's current multi-selection off the
        context, exactly as ``base.select_cancel_reason`` and similar
        SSI wizards read ``active_ids`` — except here it prefills a
        field default instead of being read again inside
        :meth:`action_apply`, since :attr:`item_ids` is itself editable
        on the wizard's own form (a dashboard administrator may still
        deselect an item there before applying).

        :return: list of ``dashboard.item`` ids from the context, or an
            empty list when opened outside a list view selection (e.g.
            directly through this model's own form).
        :rtype: list
        """
        return self.env.context.get("active_ids") or []

    item_ids = fields.Many2many(
        comodel_name="dashboard.item",
        default=lambda self: self._default_item_ids(),
        required=True,
        help="Items being moved or copied. Pre-filled from the list "
        "view's current selection when this wizard is opened through "
        "'Move / Copy Item(s)'.",
    )
    dashboard_id = fields.Many2one(
        string="Destination Dashboard",
        comodel_name="dashboard.dashboard",
        required=True,
        help="Dashboard 'Items' are moved or copied to.",
    )
    operation = fields.Selection(
        selection=[
            ("move", "Move"),
            ("copy", "Copy"),
        ],
        default="move",
        required=True,
        help="'Move' reassigns 'Items' to 'Destination Dashboard' in "
        "place, removing them from their current dashboard. 'Copy' "
        "instead creates a full duplicate of each item on 'Destination "
        "Dashboard', leaving the originals untouched.",
    )

    def action_apply(self):
        """Apply :attr:`operation` on :attr:`item_ids`, then open
        :attr:`dashboard_id`.

        :return: ``ir.actions.client`` opening :attr:`dashboard_id` —
            see ``dashboard.dashboard.action_open_dashboard``.
        :rtype: dict
        :raises UserError: see :meth:`_check_move_access`.
        """
        self.ensure_one()
        self._check_move_access()
        if self.operation == "move":
            self._apply_move()
        else:
            self._apply_copy()
        return self.dashboard_id.action_open_dashboard()

    def _check_move_access(self):
        """Raise ``UserError`` unless the current user belongs to
        ``group_dashboard_admin``. Same restriction, checked the same
        way, as ``dashboard.dashboard._check_export_access``.

        :return: None
        :raises UserError: when the current user is not a member of
            ``ssi_dashboard.group_dashboard_admin``.
        """
        self.ensure_one()
        if not self.env.user.has_group("ssi_dashboard.group_dashboard_admin"):
            error_message = f"""
Context: Move or copy dashboard item(s)
Database ID: {self.id}
Problem: Current user is not a member of the 'Administrator' dashboard \
group
Solution: Ask a dashboard administrator to move/copy these items, or \
request 'Administrator' access
"""
            raise UserError(error_message)

    def _apply_move(self):
        """Reassign every row of :attr:`item_ids` to
        :attr:`dashboard_id`, resetting its layout coordinates.

        Writing :attr:`~dashboard.item.dashboard_id` re-runs
        ``dashboard.item``'s own ``_check_data_source_company``
        constraint, rejecting the move when the destination's company
        conflicts with an item's data source company.

        :return: None
        """
        self.ensure_one()
        self.item_ids.write(
            {
                "dashboard_id": self.dashboard_id.id,
                "column_start": 0,
                "row_start": 0,
            }
        )

    def _apply_copy(self):
        """Create a full duplicate of every row of :attr:`item_ids` on
        :attr:`dashboard_id`, leaving the originals untouched.

        Reuses :meth:`dashboard.item._prepare_copy_vals` — the same
        method ``dashboard.dashboard.copy_data`` uses to duplicate an
        item while copying a whole dashboard — so a copy made through
        this wizard also keeps that item's own :attr:`~dashboard.item.
        goal_ids`/:attr:`~dashboard.item.drilldown_ids`.

        :return: None
        """
        self.ensure_one()
        for item in self.item_ids:
            vals = item._prepare_copy_vals()
            vals.update(
                {
                    "dashboard_id": self.dashboard_id.id,
                    "column_start": 0,
                    "row_start": 0,
                }
            )
            self.env["dashboard.item"].create(vals)
