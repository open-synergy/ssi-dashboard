import {Component, onWillStart, useRef, useState} from "@odoo/owl";
import {
    gridColumnStep,
    gridRowStep,
} from "../dashboard_grid/dashboard_grid_constants.esm";
import {DashboardFilterBar} from "../dashboard_filter_bar/dashboard_filter_bar.esm";
import {DashboardItem} from "../dashboard_item/dashboard_item.esm";
import {DashboardLayoutEditor} from "../dashboard_layout_editor/dashboard_layout_editor.esm";
import {_t} from "@web/core/l10n/translation";
import {registry} from "@web/core/registry";
import {standardActionServiceProps} from "@web/webclient/actions/action_service";
import {useService} from "@web/core/utils/hooks";
import {user} from "@web/core/user";

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
 *
 * Dashboard administrators (see "state.isAdmin") also get an "Edit
 * Layout" button that swaps the read-only item grid for a
 * DashboardLayoutEditor — dragging/resizing there and pressing 'Save'
 * calls dashboard.dashboard.save_layout(); 'Cancel' discards the
 * editor's local state without calling the server.
 */
export class DashboardAction extends Component {
    static template = "ssi_dashboard.DashboardAction";
    static components = {DashboardItem, DashboardFilterBar, DashboardLayoutEditor};
    static props = {...standardActionServiceProps};

    setup() {
        this.orm = useService("orm");
        this.gridRef = useRef("grid");
        this.dashboard = useState({
            name: "",
            color_scheme: {},
            filters: [],
            active_filter_ids: [],
            items: [],
        });
        this.state = useState({
            isAdmin: false,
            editMode: false,
            editItems: [],
        });
        onWillStart(async () => {
            await this.loadDashboard();
            this.state.isAdmin = await user.hasGroup(
                "ssi_dashboard.group_dashboard_admin"
            );
        });
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

    get editLayoutLabel() {
        return _t("Edit Layout");
    }

    /**
     * Whether every DashboardItem tile should be positioned at its
     * explicit "column_start"/"row_start" instead of the browser's own
     * CSS grid auto-placement — see dashboard_item.esm.js's "style"
     * getter and models/dashboard_item.py's docstring on
     * "column_start" ('Aturan tata letak tunggal'): true as soon as any
     * item of this dashboard carries a non-zero coordinate, i.e. a
     * layout has been saved through the editor at least once.
     *
     * @returns {Boolean}
     */
    get useExplicitPosition() {
        return this.dashboard.items.some(
            (item) => item.column_start !== 0 || item.row_start !== 0
        );
    }

    /**
     * Bound to the 'Edit Layout' button, shown only when "state.isAdmin".
     *
     * Seeds "state.editItems" with each item's current on-screen
     * position and switches to edit mode. When "useExplicitPosition" is
     * false (every item still at the flowing-placement default), those
     * starting positions are read back from the read-only grid's own
     * DOM — the browser's CSS grid auto-placement already computed
     * them — instead of reimplementing that placement algorithm here.
     */
    onEditLayoutClick() {
        const gridEl = this.gridRef.el;
        const containerRect = gridEl.getBoundingClientRect();
        const columnStep = gridColumnStep(containerRect.width);
        const rowStep = gridRowStep();
        const tileEls = gridEl.querySelectorAll(":scope > .o_ssi_dashboard_item");
        const useExplicitPosition = this.useExplicitPosition;
        this.state.editItems = this.dashboard.items.map((item, index) => {
            let columnStart = item.column_start;
            let rowStart = item.row_start;
            if (!useExplicitPosition) {
                const tileRect = tileEls[index].getBoundingClientRect();
                columnStart = Math.round(
                    (tileRect.left - containerRect.left) / columnStep
                );
                rowStart = Math.round((tileRect.top - containerRect.top) / rowStep);
            }
            return {
                id: item.id,
                name: item.name,
                column_start: columnStart,
                row_start: rowStart,
                column_width: item.column_width,
                row_height: item.row_height,
            };
        });
        this.state.editMode = true;
    }

    /**
     * Bound to DashboardLayoutEditor's "onCancel" prop. Discards the
     * editor's local state and returns to the read-only grid at the
     * last saved coordinates — no server call.
     */
    onCancelLayoutClick() {
        this.state.editItems = [];
        this.state.editMode = false;
    }

    /**
     * Bound to DashboardLayoutEditor's "onSave" prop.
     *
     * @param {Array} layout [{id, column_start, row_start, column_width,
     *  row_height}, ...], see dashboard.dashboard.save_layout().
     */
    async onSaveLayoutClick(layout) {
        await this.orm.call("dashboard.dashboard", "save_layout", [
            [this.dashboardId],
            layout,
        ]);
        this.state.editItems = [];
        this.state.editMode = false;
        await this.loadDashboard();
    }
}

registry.category("actions").add("ssi_dashboard.dashboard_view", DashboardAction);
