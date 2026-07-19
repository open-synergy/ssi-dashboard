# Copyright 2026 OpenSynergy Indonesia
# Copyright 2026 PT. Simetri Sinergi Indonesia
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from odoo import fields, models
from odoo.exceptions import UserError


class DashboardItemTodo(models.Model):
    """Represents one row of a ``dashboard.item`` whose ``type`` is 'todo'
    — either a 'section' heading or a checkable 'task' (see
    ``ssi_dashboard_item_todo/models/dashboard_item.py``,
    ``_prepare_render_payload_todo``). Unlike every other item type,
    'todo' does not need a ``dashboard.data_source`` at all — see
    ``dashboard.item._is_data_source_required``."""

    _name = "dashboard.item.todo"
    _description = "Dashboard Item To Do Row"
    _order = "item_id, sequence"

    item_id = fields.Many2one(
        string="# Item",
        comodel_name="dashboard.item",
        required=True,
        ondelete="cascade",
        help="Dashboard item (of 'Type' 'To Do') this row belongs to.",
    )
    sequence = fields.Integer(
        default=10,
        help="Determines the display order of rows on the checklist.",
    )
    name = fields.Char(
        required=True,
        help="Text shown for this row — a heading for 'Section', a "
        "checkable label for 'Task'.",
    )
    line_type = fields.Selection(
        selection=[
            ("section", "Section"),
            ("task", "Task"),
        ],
        required=True,
        default="task",
        help="Kind of row. 'Section' is a heading and ignores 'Done'. "
        "'Task' is a checkable row toggled through 'toggle_todo_done'.",
    )
    done = fields.Boolean(
        default=False,
        help="Ticked state of a 'Task' row, toggled by 'toggle_todo_done'. "
        "Ignored by 'Section' rows.",
    )

    def toggle_todo_done(self):
        """Flip :attr:`done` on this single row, called by the browser
        when the user ticks/unticks a 'Task' row's checkbox.

        :return: the new value of :attr:`done`.
        :rtype: bool
        :raises UserError: when called on a 'Section' row, which carries
            no meaningful 'Done' state.
        """
        self.ensure_one()
        if self.line_type == "section":
            error_message = f"""
Context: Toggle dashboard item to do row
Database ID: {self.id}
Problem: 'Line Type' is 'Section', which has no 'Done' state to toggle
Solution: Toggle a 'Task' row instead
"""
            raise UserError(error_message)
        self.done = not self.done
        return self.done
