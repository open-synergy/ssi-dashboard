import {Component, useState} from "@odoo/owl";
import {registry} from "@web/core/registry";
import {useService} from "@web/core/utils/hooks";

/**
 * Renders a "todo" dashboard item — a checklist made of "section"
 * headings and checkable "task" rows. Registered under
 * registry.category("ssi_dashboard.item_widgets") for the "dashboard.item"
 * type "todo" (see ssi_dashboard_item_todo/models/dashboard_item.py,
 * _prepare_render_payload_todo()).
 *
 * The "item" prop is one entry of "items" from
 * dashboard.dashboard.get_dashboard_payload(), enriched by
 * _prepare_render_payload_todo() with a "todo" key — list of dict with
 * "id", "name", "line_type" ("section"/"task") and "done", already sorted
 * by "Sequence" server-side.
 *
 * Ticking a "task" row calls dashboard.item.todo.toggle_todo_done()
 * (write access granted to group_dashboard_user, see
 * security/ir_model_access/dashboard_item_todo.xml) and applies its
 * return value locally, instead of re-fetching the whole dashboard
 * payload — "section" rows render without a checkbox and are never
 * clickable.
 */
export class DashboardItemTodo extends Component {
    static template = "ssi_dashboard_item_todo.DashboardItemTodo";
    static props = {item: Object};

    setup() {
        this.orm = useService("orm");
        this.state = useState({rows: this.props.item.todo || []});
    }

    /**
     * @param {Object} row one entry of "state.rows" — mutated in place
     *     with the server's answer so the template re-renders without a
     *     full dashboard refetch.
     */
    async onToggleDone(row) {
        if (row.line_type === "section") {
            return;
        }
        row.done = await this.orm.call("dashboard.item.todo", "toggle_todo_done", [
            [row.id],
        ]);
    }
}

registry.category("ssi_dashboard.item_widgets").add("todo", DashboardItemTodo);
