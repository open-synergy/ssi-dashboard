import {
    Component,
    onMounted,
    onWillStart,
    onWillUnmount,
    useRef,
    useState,
} from "@odoo/owl";
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
 *
 * While mounted, the dashboard also re-fetches itself on a timer driven
 * by the payload's "refresh_interval" (seconds; 0 means auto-refresh is
 * off — see models/dashboard_dashboard.py's "refresh_interval" field).
 * The timer is armed in onMounted and always cleared in onWillUnmount
 * (see startAutoRefresh()/stopAutoRefresh()) so navigating away from
 * this action never leaves a background fetch loop running. Ticks are
 * skipped while the browser tab is not visible ("document.hidden") and
 * one catch-up fetch runs as soon as it becomes visible again (see
 * autoRefreshTick()/onVisibilityChange()); a tick is also skipped
 * outright while a previous refresh is still in flight
 * ("state.isRefreshing"), rather than being queued. Every refresh —
 * automatic or through the manual reload button — reuses whatever
 * filter/date-range selection is currently active ("currentFilters"),
 * and a failed refresh leaves the last successfully loaded data in
 * place while flipping "state.refreshFailed" (see refreshDashboard()).
 */
export class DashboardAction extends Component {
    static template = "ssi_dashboard.DashboardAction";
    static components = {DashboardItem, DashboardFilterBar, DashboardLayoutEditor};
    static props = {...standardActionServiceProps};

    setup() {
        this.orm = useService("orm");
        this.gridRef = useRef("grid");
        this.rootRef = useRef("root");
        // Last "active_filters" selection sent to get_dashboard_payload
        // (see DashboardFilterBar's "onChange" prop) — not reactive
        // state on purpose, it is only ever read back by
        // refreshDashboard() to repeat the same selection, never
        // rendered directly.
        this.currentFilters = null;
        this.refreshTimerId = null;
        this.onVisibilityChange = this.onVisibilityChange.bind(this);
        this.onFullscreenChange = this.onFullscreenChange.bind(this);
        this.dashboard = useState({
            name: "",
            color_scheme: {},
            filters: [],
            active_filter_ids: [],
            refresh_interval: 0,
            fullscreen_enabled: true,
            items: [],
        });
        this.state = useState({
            isAdmin: false,
            editMode: false,
            editItems: [],
            isRefreshing: false,
            refreshFailed: false,
            isFullscreen: false,
        });
        onWillStart(async () => {
            await this.loadDashboard();
            this.state.isAdmin = await user.hasGroup(
                "ssi_dashboard.group_dashboard_admin"
            );
        });
        onMounted(() => this.startAutoRefresh());
        onWillUnmount(() => this.stopAutoRefresh());
        onMounted(() =>
            document.addEventListener("fullscreenchange", this.onFullscreenChange)
        );
        onWillUnmount(() =>
            document.removeEventListener("fullscreenchange", this.onFullscreenChange)
        );
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
     * Used for the very first fetch (onWillStart) and whenever the
     * filter bar's selection changes (onFilterChange) — errors are
     * intentionally left to propagate here, same as before auto-refresh
     * existed. For refreshing already-loaded data without wiping it on
     * failure, see refreshDashboard() instead.
     *
     * @param {Object} [activeFilters]
     */
    async loadDashboard(activeFilters = null) {
        if (activeFilters !== null) {
            this.currentFilters = activeFilters;
        }
        const payload = await this.orm.call(
            "dashboard.dashboard",
            "get_dashboard_payload",
            [[this.dashboardId], activeFilters]
        );
        Object.assign(this.dashboard, payload);
        this.state.refreshFailed = false;
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
     * Re-fetches the dashboard with "currentFilters" — the selection
     * currently active on the filter bar, so an automatic or manual
     * refresh never silently drops it back to the server-side default
     * (see models/dashboard_dashboard.py, get_dashboard_payload()'s
     * docstring). Bound to the manual reload button and to the
     * auto-refresh timer (autoRefreshTick()).
     *
     * Unlike loadDashboard(): skips outright when a previous refresh is
     * still in flight ("state.isRefreshing") instead of queueing one,
     * and swallows failures into "state.refreshFailed" instead of
     * letting them propagate, so a flaky refresh never clears the tile
     * grid — it keeps showing the last successfully loaded data.
     */
    async refreshDashboard() {
        if (this.state.isRefreshing) {
            return;
        }
        this.state.isRefreshing = true;
        try {
            await this.loadDashboard(this.currentFilters);
        } catch {
            this.state.refreshFailed = true;
        } finally {
            this.state.isRefreshing = false;
        }
    }

    /**
     * Bound to the manual reload button, always shown regardless of
     * "refresh_interval".
     */
    onManualRefreshClick() {
        this.refreshDashboard();
    }

    /**
     * Arms the auto-refresh timer from "dashboard.refresh_interval"
     * (seconds; 0 means off — no timer is armed at all) and starts
     * listening for "visibilitychange" so a tick skipped while the tab
     * was hidden is caught up once it is shown again. Called from
     * onMounted(); always paired with stopAutoRefresh() in
     * onWillUnmount().
     */
    startAutoRefresh() {
        const intervalSeconds = this.dashboard.refresh_interval;
        if (!intervalSeconds) {
            return;
        }
        this.refreshTimerId = setInterval(
            () => this.autoRefreshTick(),
            intervalSeconds * 1000
        );
        document.addEventListener("visibilitychange", this.onVisibilityChange);
    }

    /**
     * Clears the auto-refresh timer (if any) and removes the
     * "visibilitychange" listener. Safe to call even when
     * startAutoRefresh() never armed a timer (refresh_interval "0").
     */
    stopAutoRefresh() {
        if (this.refreshTimerId) {
            clearInterval(this.refreshTimerId);
            this.refreshTimerId = null;
        }
        document.removeEventListener("visibilitychange", this.onVisibilityChange);
    }

    /**
     * Auto-refresh timer callback. Skipped entirely while the browser
     * tab is not visible, so dashboards left open in background tabs
     * never hit the server on their own — see onVisibilityChange() for
     * the catch-up fetch once the tab is shown again.
     */
    autoRefreshTick() {
        if (document.hidden) {
            return;
        }
        this.refreshDashboard();
    }

    /**
     * Bound to the "visibilitychange" DOM event while auto-refresh is
     * enabled (see startAutoRefresh()). Fires one refresh as soon as the
     * tab becomes visible again — any tick that landed while it was
     * hidden was skipped by autoRefreshTick().
     */
    onVisibilityChange() {
        if (!document.hidden) {
            this.refreshDashboard();
        }
    }

    get refreshLabel() {
        return _t("Reload");
    }

    get refreshFailedLabel() {
        return _t("Refresh failed — showing last loaded data");
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

    get fullscreenLabel() {
        return this.state.isFullscreen ? _t("Exit Fullscreen") : _t("Fullscreen");
    }

    /**
     * Bound to the 'Fullscreen'/'Exit Fullscreen' button, only shown
     * when "dashboard.fullscreen_enabled" (see
     * models/dashboard_dashboard.py's "fullscreen_enabled" field).
     *
     * Uses the browser's native Fullscreen API on this component's own
     * root element (".o_ssi_dashboard", see "rootRef") rather than
     * hiding the surrounding Odoo backend chrome with CSS — so exiting
     * fullscreen (via this button, the browser's own UI, or Escape)
     * always restores the page correctly, and the filter bar/reload
     * button (rendered inside the root element) stay available while
     * fullscreen. "state.isFullscreen" itself is kept in sync by
     * "onFullscreenChange" listening for the native "fullscreenchange"
     * event, so it also reflects fullscreen exited through means other
     * than this button.
     */
    onFullscreenClick() {
        if (document.fullscreenElement) {
            document.exitFullscreen();
        } else {
            this.rootRef.el.requestFullscreen();
        }
    }

    /**
     * Bound to the document's "fullscreenchange" event (see setup()).
     * Keeps "state.isFullscreen" in sync with the actual browser state,
     * regardless of what triggered the change (this component's own
     * button, the browser's UI, or the Escape key).
     */
    onFullscreenChange() {
        this.state.isFullscreen = document.fullscreenElement === this.rootRef.el;
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
