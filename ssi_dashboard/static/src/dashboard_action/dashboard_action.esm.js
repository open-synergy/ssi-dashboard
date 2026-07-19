import {Component, onWillStart, useState} from "@odoo/owl";
import {DashboardFilterBar} from "../dashboard_filter_bar/dashboard_filter_bar.esm";
import {DashboardItem} from "../dashboard_item/dashboard_item.esm";
import {registry} from "@web/core/registry";
import {standardActionServiceProps} from "@web/webclient/actions/action_service";
import {useService} from "@web/core/utils/hooks";

/**
 * Root client action registered under the "ssi_dashboard.dashboard_view"
 * tag (see models/dashboard_dashboard.py, action_open_dashboard()).
 *
 * Fetches the dashboard payload through get_dashboard_payload(), then
 * renders a DashboardFilterBar (filters/date range picker) above one
 * DashboardItem per entry in "items", and turns "color_scheme" into CSS
 * custom properties scoped to this component's root element. Changing
 * the filter bar's selection re-fetches the payload with that selection
 * as get_dashboard_payload's "active_filters" argument, without
 * navigating away from this action.
 */
export class DashboardAction extends Component {
    static template = "ssi_dashboard.DashboardAction";
    static components = {DashboardItem, DashboardFilterBar};
    static props = {...standardActionServiceProps};

    setup() {
        this.orm = useService("orm");
        this.dashboard = useState({
            name: "",
            color_scheme: {},
            filters: [],
            active_filter_ids: [],
            items: [],
        });
        onWillStart(() => this.loadDashboard());
    }

    get dashboardId() {
        return this.props.action.context.dashboard_id;
    }

    /**
     * Fetches get_dashboard_payload() with the given "active_filters"
     * selection (or the server-side default when omitted) and merges
     * the result into the reactive "dashboard" state, so the template
     * re-renders with the new data.
     *
     * @param {Object} [activeFilters]
     */
    async loadDashboard(activeFilters = null) {
        const payload = await this.orm.call(
            "dashboard.dashboard",
            "get_dashboard_payload",
            [[this.dashboardId], activeFilters]
        );
        Object.assign(this.dashboard, payload);
    }

    /**
     * Bound to DashboardFilterBar's "onChange" prop.
     *
     * @param {Object} activeFilters
     */
    onFilterChange(activeFilters) {
        this.loadDashboard(activeFilters);
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
