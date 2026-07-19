import {Component, onWillStart} from "@odoo/owl";
import {DashboardItem} from "../dashboard_item/dashboard_item.esm";
import {registry} from "@web/core/registry";
import {standardActionServiceProps} from "@web/webclient/actions/action_service";
import {useService} from "@web/core/utils/hooks";

/**
 * Root client action registered under the "ssi_dashboard.dashboard_view"
 * tag (see models/dashboard_dashboard.py, action_open_dashboard()).
 *
 * Fetches the dashboard payload once through get_dashboard_payload(), then
 * renders one DashboardItem per entry in "items" and turns "color_scheme"
 * into CSS custom properties scoped to this component's root element.
 */
export class DashboardAction extends Component {
    static template = "ssi_dashboard.DashboardAction";
    static components = {DashboardItem};
    static props = {...standardActionServiceProps};

    setup() {
        this.orm = useService("orm");
        this.dashboard = {name: "", color_scheme: {}, items: []};
        onWillStart(async () => {
            const dashboardId = this.props.action.context.dashboard_id;
            this.dashboard = await this.orm.call(
                "dashboard.dashboard",
                "get_dashboard_payload",
                [[dashboardId]]
            );
        });
    }

    /**
     * Turn the "color_scheme" mapping (already "--ssi-dashboard-<key>":
     * "<value>" pairs, built server-side by
     * dashboard.color_scheme._prepare_css_variables()) into an inline
     * style string, so the variables stay scoped to this dashboard and
     * never leak to the rest of the backend.
     *
     * @returns {String}
     */
    get rootStyle() {
        const colorScheme = this.dashboard.color_scheme || {};
        return Object.entries(colorScheme)
            .map(([key, value]) => `${key}: ${value}`)
            .join("; ");
    }
}

registry.category("actions").add("ssi_dashboard.dashboard_view", DashboardAction);
