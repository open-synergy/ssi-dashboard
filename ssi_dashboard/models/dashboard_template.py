# Copyright 2026 OpenSynergy Indonesia
# Copyright 2026 PT. Simetri Sinergi Indonesia
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from odoo import api, fields, models


class DashboardTemplate(models.Model):
    """Represents a reusable dashboard template: a pointer to a
    ``dashboard.dashboard`` (:attr:`source_dashboard_id`) that acts as
    the mold a new dashboard is duplicated from, through the
    ``dashboard.create.from.template`` wizard's ``action_create``.

    Never stores its own separate copy of the mold's items/filters —
    see :attr:`source_dashboard_id`'s own help for why."""

    _name = "dashboard.template"
    _inherit = [
        "mixin.master_data",
    ]
    _description = "Dashboard Template"

    _dashboard_template_code_uniq = models.Constraint(
        "UNIQUE(code)",
        "Another template with that code already exists.",
    )

    source_dashboard_id = fields.Many2one(
        comodel_name="dashboard.dashboard",
        required=True,
        ondelete="cascade",
        help="Dashboard this template is built from. "
        "'dashboard.create.from.template' duplicates this record "
        "(through 'dashboard.dashboard''s own 'copy', inherited from "
        "'mixin.master_data') into a new dashboard rather than "
        "replaying a separate stored definition — this template keeps "
        "no copy of the mold's items/filters of its own, so the two "
        "can never drift out of sync. Automatically marked "
        "'is_locked' as soon as it is referenced here (see 'create'/"
        "'write' below), protecting its identity ('Code') from being "
        "deleted or renamed out from under this template, while its "
        "name/items/layout stay freely editable.",
    )
    description = fields.Text(
        help="Short explanation of what this template's dashboard "
        "contains, shown to help a user pick a template before ever "
        "having seen a dashboard built from it.",
    )
    is_predefined = fields.Boolean(
        default=False,
        readonly=True,
        help="Marks this template as one shipped by a module, rather "
        "than created by a user through the UI. Informational only — "
        "set through data files, never through the UI (read-only).",
    )

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for record in records:
            record._lock_source_dashboard()
        return records

    def write(self, vals):
        result = super().write(vals)
        if "source_dashboard_id" in vals:
            for record in self:
                record._lock_source_dashboard()
        return result

    def _lock_source_dashboard(self):
        """Ensure :attr:`source_dashboard_id` is marked ``is_locked``.

        Called from both :meth:`create` and :meth:`write` so a
        dashboard becomes, and stays, protected the moment any
        template starts pointing at it — see :attr:`source_dashboard_id`'s
        help. No-op when it is already locked, so this never triggers
        an extra ``dashboard.dashboard.write`` on the common case of a
        template pointing at an already-locked dashboard.

        :return: None
        """
        self.ensure_one()
        if self.source_dashboard_id and not self.source_dashboard_id.is_locked:
            self.source_dashboard_id.write({"is_locked": True})
