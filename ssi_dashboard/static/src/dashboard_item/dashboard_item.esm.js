import {Component} from "@odoo/owl";
import {DashboardItemFallback} from "../dashboard_item_fallback/dashboard_item_fallback.esm";
import {registry} from "@web/core/registry";

/**
 * Registry item modules register their dashboard item component into,
 * keyed by the "dashboard.item" type they render:
 *
 *   registry.category("ssi_dashboard.item_widgets").add("<type>", Component);
 *
 * The "item" prop each registered component receives is one entry of the
 * "items" key returned by dashboard.dashboard.get_dashboard_payload() —
 * id, name, type, column_width, row_height, active and data.
 */
const itemWidgetRegistry = registry.category("ssi_dashboard.item_widgets");

/**
 * Positions one dashboard item on the grid and delegates its rendering to
 * whichever component is registered for its "type" in item_widgets, or to
 * DashboardItemFallback when no such component is registered yet — so an
 * unsupported/unknown type never breaks the whole dashboard.
 */
export class DashboardItem extends Component {
    static template = "ssi_dashboard.DashboardItem";
    static props = {
        item: Object,
        useExplicitPosition: {type: Boolean, optional: true},
    };

    get Component() {
        return itemWidgetRegistry.get(this.props.item.type, DashboardItemFallback);
    }

    /**
     * "props.useExplicitPosition" mirrors dashboard.item's "Aturan tata
     * letak tunggal" (see models/dashboard_item.py docstring on
     * "column_start"): when every item of the dashboard is still at the
     * (0, 0) flowing-placement default, this is false for all of them
     * and the browser's own CSS grid auto-placement positions the tile
     * (unchanged from before "column_start"/"row_start" existed). Once
     * a layout has been saved through the layout editor, this is true
     * and the tile is positioned at its explicit coordinates instead.
     *
     * @returns {String}
     */
    get style() {
        const item = this.props.item;
        if (this.props.useExplicitPosition) {
            return (
                `grid-column: ${item.column_start + 1} / span ${item.column_width}; ` +
                `grid-row: ${item.row_start + 1} / span ${item.row_height};`
            );
        }
        return `grid-column: span ${item.column_width}; grid-row: span ${item.row_height};`;
    }
}
