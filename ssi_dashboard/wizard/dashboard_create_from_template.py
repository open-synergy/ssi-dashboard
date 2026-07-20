# Copyright 2026 OpenSynergy Indonesia
# Copyright 2026 PT. Simetri Sinergi Indonesia
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from odoo import api, fields, models


class DashboardCreateFromTemplate(models.TransientModel):
    """Wizard that creates a new ``dashboard.dashboard`` out of a
    ``dashboard.template``'s :attr:`~dashboard.template.
    source_dashboard_id`.

    Bound to ``dashboard.template``'s list/form views through
    ``dashboard_create_from_template_action``'s ``binding_model_id``,
    which is what fills in :attr:`template_id` (see
    :meth:`_default_template_id`) when opened from there.

    Reuses ``dashboard.dashboard``'s own ``copy`` (inherited from
    ``mixin.master_data``, which overrides only
    ``dashboard.dashboard.copy_data`` — see that method) instead of
    writing a duplicate deep-copy of its own: the new dashboard ends up
    with the exact same items/filters as :attr:`template_id`'s
    :attr:`~dashboard.template.source_dashboard_id`, and never carries
    'Generate Menu'/'Locked' over from it, since both 'generate_menu'
    and 'is_locked' are declared ``copy=False`` on ``dashboard.
    dashboard``.
    """

    _name = "dashboard.create.from.template"
    _description = "Create Dashboard from Template"

    @api.model
    def _default_template_id(self):
        """Read the calling list/form view's ``active_id`` off the
        context, the same way ``dashboard.item.move._default_item_ids``
        reads its own selection off ``active_ids``.

        :return: a ``dashboard.template`` id, or ``False`` when opened
            outside a template's own list/form (e.g. directly through
            this model's own form).
        :rtype: int or bool
        """
        return self.env.context.get("active_id") or False

    template_id = fields.Many2one(
        comodel_name="dashboard.template",
        default=lambda self: self._default_template_id(),
        required=True,
        help="Template whose 'Source Dashboard' is duplicated into a "
        "new dashboard. Pre-filled when this wizard is opened through "
        "'Create Dashboard from Template' on a template's own list/"
        "form.",
    )
    name = fields.Char(
        required=True,
        help="Name of the new dashboard.",
    )
    code = fields.Char(
        required=True,
        help="Unique code of the new dashboard.",
    )

    def action_create(self):
        """Duplicate :attr:`template_id`'s :attr:`~dashboard.template.
        source_dashboard_id`, overriding 'Name'/'Code' with
        :attr:`name`/:attr:`code`, then open the result.

        :return: ``ir.actions.client`` opening the newly created
            dashboard — see ``dashboard.dashboard.action_open_dashboard``.
        :rtype: dict
        """
        self.ensure_one()
        dashboard = self.template_id.source_dashboard_id.copy(
            {"name": self.name, "code": self.code}
        )
        return dashboard.action_open_dashboard()
