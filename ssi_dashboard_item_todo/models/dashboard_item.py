# Copyright 2026 OpenSynergy Indonesia
# Copyright 2026 PT. Simetri Sinergi Indonesia
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from odoo import fields, models


class DashboardItem(models.Model):
    """Extends `dashboard.item` with the 'todo' type: a checklist made of
    'section' and 'task' rows (:attr:`todo_ids`, model
    `dashboard.item.todo`), rendered without pulling from any
    `dashboard.data_source` at all — see
    :meth:`_is_data_source_required`."""

    _name = "dashboard.item"
    _inherit = [
        "dashboard.item",
    ]

    type = fields.Selection(
        selection_add=[
            ("todo", "To Do"),
        ],
        ondelete={"todo": "set default"},
    )
    todo_ids = fields.One2many(
        string="To Do Rows",
        comodel_name="dashboard.item.todo",
        inverse_name="item_id",
        help="Section/task rows rendered as a checklist. Only used when "
        "'Type' is 'To Do'.",
    )

    def _is_data_source_required(self):
        """'todo' items render their own :attr:`todo_ids` and never pull
        from a `dashboard.data_source` — see :meth:`_prepare_render_payload_todo`.
        """
        self.ensure_one()
        if self.type == "todo":
            return False
        return super()._is_data_source_required()

    def _prepare_render_payload_todo(self, payload):
        """Enrich the render payload of a 'todo' item.

        :param payload: dict built by
            :meth:`dashboard.item._prepare_render_payload`.
        :return: `payload`, with a 'todo' key added — list of dict with
            keys 'id', 'name', 'line_type' and 'done', one per
            :attr:`todo_ids` row, in 'Sequence' order.
        :rtype: dict
        """
        self.ensure_one()
        payload["todo"] = [
            {
                "id": row.id,
                "name": row.name,
                "line_type": row.line_type,
                "done": row.done,
            }
            for row in self.todo_ids.sorted("sequence")
        ]
        return payload
