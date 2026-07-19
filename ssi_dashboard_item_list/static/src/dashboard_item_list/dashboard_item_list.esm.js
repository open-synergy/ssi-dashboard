import {Component} from "@odoo/owl";
import {registry} from "@web/core/registry";

/**
 * Renders a "list" dashboard item — a table of the item's fetched data.
 * Registered under registry.category("ssi_dashboard.item_widgets") for the
 * "dashboard.item" type "list" (see
 * ssi_dashboard_item_list/models/dashboard_item.py,
 * _prepare_render_payload_list()).
 *
 * The "item" prop is one entry of "items" from
 * dashboard.dashboard.get_dashboard_payload(), enriched with "columns"
 * (list of {key, label}) and "rows" (list of dict keyed like "columns",
 * already capped server-side at "limit") by _prepare_render_payload_list().
 * A row missing a column's key renders an empty cell rather than erroring,
 * since non-ORM sources (API, ODBC) do not guarantee a uniform row shape.
 * Colors come from the dashboard's own CSS custom properties (set by
 * DashboardAction from dashboard.color_scheme) — this component carries no
 * palette of its own.
 */
export class DashboardItemList extends Component {
    static template = "ssi_dashboard_item_list.DashboardItemList";
    static props = {item: Object};

    /**
     * @param {Object} row one entry of `this.props.item.rows`
     * @param {Object} column one entry of `this.props.item.columns`
     * @returns {String} `row`'s value for `column.key`, or "" when the
     *     row does not carry that key.
     */
    cellValue(row, column) {
        const value = row[column.key];
        return value === undefined || value === null ? "" : value;
    }
}

registry.category("ssi_dashboard.item_widgets").add("list", DashboardItemList);
