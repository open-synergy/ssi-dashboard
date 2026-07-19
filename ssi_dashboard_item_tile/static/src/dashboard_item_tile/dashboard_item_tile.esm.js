import {Component} from "@odoo/owl";
import {formatFloat} from "@web/core/utils/numbers";
import {registry} from "@web/core/registry";

/**
 * Renders a "tile" dashboard item — a single aggregate number with its
 * label. Registered under registry.category("ssi_dashboard.item_widgets")
 * for the "dashboard.item" type "tile" (see
 * ssi_dashboard_item_tile/models/dashboard_item.py,
 * _prepare_render_payload_tile()).
 *
 * The "item" prop is one entry of "items" from
 * dashboard.dashboard.get_dashboard_payload(), enriched with "value" (the
 * aggregated number) and "label" by _prepare_render_payload_tile(). Color
 * comes from the dashboard's own "--ssi-dashboard-primary" CSS custom
 * property (set by DashboardAction from dashboard.color_scheme) — this
 * component carries no palette of its own.
 */
export class DashboardItemTile extends Component {
    static template = "ssi_dashboard_item_tile.DashboardItemTile";
    static props = {item: Object};

    get formattedValue() {
        return formatFloat(this.props.item.value, {trailingZeros: false});
    }
}

registry.category("ssi_dashboard.item_widgets").add("tile", DashboardItemTile);
