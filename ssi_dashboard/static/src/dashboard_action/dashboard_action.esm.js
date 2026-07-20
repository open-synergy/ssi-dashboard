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
 * The same administrators get a per-tile 'Edit' button (see
 * DashboardItem's "props.isAdmin"/"props.onEditClick") that opens that
 * item's own form (models/dashboard_item.py's
 * "dashboard_item_view_form", the same one already used by
 * action_open_item_goals()) in a dialog — see onEditItemClick(). That
 * form embeds a live preview widget calling
 * dashboard.item.preview_render_payload() (see
 * dashboard_item_preview.esm.js), so an administrator sees the tile's
 * rendered result update as the dialog's fields change, before ever
 * pressing 'Save'. Closing the dialog (Save or Discard) reloads only
 * that one item (see reloadItem()) instead of the whole dashboard, so
 * the rest of the grid — and the filter bar's current selection —
 * stays untouched.
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
 *
 * Also implements alternate layouts (backlog issue #50): when
 * "dashboard.layouts" has more than one entry, a layout picker (see
 * "showLayoutPicker") is shown next to the reload button. Picking a
 * different layout (see "onLayoutChange") re-fetches the payload with
 * that layout's id as get_dashboard_payload's "layout_id" argument,
 * changing every item's on-screen coordinates without navigating away
 * from this action. The currently selected layout is read from
 * "dashboard.active_layout_id" (part of the reactive payload state
 * itself, so the picker's own selection always mirrors what the server
 * actually resolved — see get_dashboard_payload's docstring) and is
 * carried forward by refreshDashboard()/onFilterChange()/reloadItem()
 * so switching filters, an automatic/manual refresh, or editing one
 * item's form never silently drops back to the default layout. Editing
 * positions through "DashboardLayoutEditor"/"onSaveLayoutClick" always
 * writes to each item's own base coordinates regardless of which
 * layout is selected here — dashboard.dashboard.save_layout's
 * "layout_id" argument exists for other callers, wiring this editor to
 * it is out of scope for issue #50 (see its "Ruang Lingkup").
 *
 * Also implements "Print to PDF" (backlog issue #49): a 'Print' button,
 * only shown when "dashboard.allow_pdf_export" (see
 * models/dashboard_dashboard.py's "allow_pdf_export" field), calls the
 * browser's own print dialog — no PDF-generating JS library is added.
 * Pressing it (see onPrintClick()) first adds the
 * "o_ssi_dashboard_print_mode" class to this component's own root
 * element ("rootRef"), which the SCSS in "dashboard_action.scss" keys
 * off (in addition to a matching "@media print" block, for the actual
 * printed page) to hide the surrounding Odoo backend chrome, the filter
 * bar and every action button, and to show a print-only summary of this
 * dashboard's title and its currently active filters
 * ("printFilterSummary") instead. Every chart's "canvas" element is then
 * swapped for a static "img" built from that canvas' own "toDataURL()"
 * (see preparePrintSnapshot()) — most browsers print an empty box in
 * place of a "canvas" otherwise — and every ".o_ssi_dashboard_item"
 * tile's current on-screen height is frozen as an inline style, so the
 * print layout's single full-width column (see the SCSS) still gives
 * each tile's content a definite height to lay out against, exactly the
 * height it already had on screen. "window.print()" is only called once
 * all of that is in place. The browser's own "afterprint" event (see
 * onAfterPrint()) restores every canvas/height and removes the print
 * mode class once the print dialog is dismissed — printing whatever
 * drill-down level an item currently shows, since nothing here resets
 * "DashboardItem"'s own "drilldown" state.
 */
export class DashboardAction extends Component {
    static template = "ssi_dashboard.DashboardAction";
    static components = {DashboardItem, DashboardFilterBar, DashboardLayoutEditor};
    static props = {...standardActionServiceProps};

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.gridRef = useRef("grid");
        this.rootRef = useRef("root");
        // Resolved "active_filters" the dashboard is currently showing
        // — set from every loadDashboard() response (see
        // "payload.active_filter_ids"), never left null once the first
        // fetch completes, even when nothing was ever passed to
        // get_dashboard_payload (see loadDashboard()'s docstring: the
        // server resolves its own default_active filters in that case,
        // and this must mirror that resolution, not the raw argument,
        // so DashboardItem's export button — see "activeFilters" prop —
        // always forwards exactly the filters the tile itself was
        // rendered with, per backlog issue #43's Keputusan Desain). Not
        // reactive state on purpose, it is only ever read back by
        // refreshDashboard() to repeat the same selection and by the
        // template to build DashboardItem's "activeFilters" prop, never
        // rendered directly itself.
        this.currentFilters = null;
        this.refreshTimerId = null;
        // Non-reactive on purpose, same reasoning as "currentFilters":
        // one cleanup closure per element touched by preparePrintSnapshot()
        // (canvas → img swaps, frozen tile heights), popped and run by
        // restorePrintSnapshot() — never rendered, so it does not need to
        // go through useState().
        this.printRestoreQueue = [];
        this.onVisibilityChange = this.onVisibilityChange.bind(this);
        this.onFullscreenChange = this.onFullscreenChange.bind(this);
        this.onAfterPrint = this.onAfterPrint.bind(this);
        this.dashboard = useState({
            name: "",
            color_scheme: {},
            filters: [],
            active_filter_ids: [],
            refresh_interval: 0,
            fullscreen_enabled: true,
            allow_pdf_export: true,
            layouts: [],
            active_layout_id: false,
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
        onMounted(() => window.addEventListener("afterprint", this.onAfterPrint));
        onWillUnmount(() =>
            window.removeEventListener("afterprint", this.onAfterPrint)
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
     * "this.currentFilters" is (re)built from the response rather than
     * echoing "activeFilters" back verbatim: "payload.active_filter_ids"
     * is the dashboard's own *resolved* filter selection (falls back to
     * this dashboard's default_active filters server-side when
     * "activeFilters" is null/omitted — see models/dashboard_dashboard.py's
     * "_resolve_active_filters"), so this keeps working correctly even
     * before the filter bar has ever been touched.
     *
     * "layoutId" (backlog issue #50) is forwarded to
     * get_dashboard_payload's own "layout_id" argument as-is; the
     * server resolves it the same way regardless of what a caller
     * passes (falls back to the dashboard's own default layout, then to
     * each item's base coordinates — see get_dashboard_payload's
     * docstring), so no local resolution is duplicated here. The
     * resolved "payload.active_layout_id" ends up in "this.dashboard"
     * through the Object.assign below, which is what the layout picker
     * itself reads back (see the "value" of its <select>).
     *
     * @param {Object} [activeFilters]
     * @param {Number|Boolean} [layoutId]
     */
    async loadDashboard(activeFilters = null, layoutId = null) {
        const payload = await this.orm.call(
            "dashboard.dashboard",
            "get_dashboard_payload",
            [[this.dashboardId], activeFilters, layoutId || null]
        );
        this.currentFilters = {
            filter_ids: payload.active_filter_ids,
            date_start: activeFilters ? activeFilters.date_start : null,
            date_end: activeFilters ? activeFilters.date_end : null,
        };
        Object.assign(this.dashboard, payload);
        this.state.refreshFailed = false;
    }

    /**
     * Bound to DashboardFilterBar's "onChange" prop. Keeps whatever
     * layout is currently selected (see "dashboard.active_layout_id")
     * instead of silently dropping back to the default layout every
     * time the filter selection changes.
     *
     * @param {Object} activeFilters
     */
    onFilterChange(activeFilters) {
        this.loadDashboard(activeFilters, this.dashboard.active_layout_id);
    }

    get layoutPickerLabel() {
        return _t("Layout");
    }

    /**
     * Whether the layout picker (backlog issue #50) should be shown —
     * only once this dashboard actually has more than one layout to
     * choose from (Keputusan Desain), so a dashboard without alternate
     * layouts renders exactly as before this feature existed.
     *
     * @returns {Boolean}
     */
    get showLayoutPicker() {
        return this.dashboard.layouts.length > 1;
    }

    /**
     * Bound to the layout picker's "change" event.
     *
     * @param {Event} ev
     */
    onLayoutChange(ev) {
        const layoutId = Number(ev.target.value) || null;
        this.loadDashboard(this.currentFilters, layoutId);
    }

    /**
     * Re-fetches the dashboard with "currentFilters" — the selection
     * currently active on the filter bar, so an automatic or manual
     * refresh never silently drops it back to the server-side default
     * (see models/dashboard_dashboard.py, get_dashboard_payload()'s
     * docstring) — and with "dashboard.active_layout_id", so it never
     * silently drops back to the default layout either (backlog issue
     * #50). Bound to the manual reload button and to the auto-refresh
     * timer (autoRefreshTick()).
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
            await this.loadDashboard(
                this.currentFilters,
                this.dashboard.active_layout_id
            );
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

    get printLabel() {
        return _t("Print");
    }

    get printFilterSummaryLabel() {
        return _t("Active Filters");
    }

    get noActiveFiltersLabel() {
        return _t("No active filters");
    }

    /**
     * Names of "dashboard.filters" currently active, in the order the
     * filter bar itself lists them — the toggleable-chip part of
     * "printFilterSummary".
     *
     * @returns {Array}
     */
    get activePrintFilterNames() {
        const activeIds = new Set(this.dashboard.active_filter_ids || []);
        return this.dashboard.filters
            .filter((filter) => activeIds.has(filter.id))
            .map((filter) => filter.name);
    }

    /**
     * Human-readable date range part of "printFilterSummary", built from
     * "currentFilters" (see loadDashboard()) — the same selection every
     * tile on screen was last rendered with. Empty string when neither
     * bound is set, so "printFilterSummary" can skip it entirely.
     *
     * @returns {String}
     */
    get printDateRangeText() {
        const dateStart = this.currentFilters && this.currentFilters.date_start;
        const dateEnd = this.currentFilters && this.currentFilters.date_end;
        if (!dateStart && !dateEnd) {
            return "";
        }
        return `${dateStart || "…"} – ${dateEnd || "…"}`;
    }

    /**
     * Single-line summary of every filter active at the time of
     * printing — required to print alongside this dashboard's title
     * (Keputusan Desain, backlog issue #49: a PDF without it is a set
     * of numbers with no context). Rendered by the print-only
     * ".o_ssi_dashboard_print_summary" block (see the template).
     *
     * @returns {String}
     */
    get printFilterSummary() {
        const parts = [...this.activePrintFilterNames];
        const dateRange = this.printDateRangeText;
        if (dateRange) {
            parts.push(dateRange);
        }
        return parts.length ? parts.join(", ") : this.noActiveFiltersLabel;
    }

    /**
     * Bound to the 'Print' button, only shown when
     * "dashboard.allow_pdf_export" (see models/dashboard_dashboard.py's
     * "allow_pdf_export" field). See the class docstring for the full
     * sequence — this only orders the three steps.
     */
    onPrintClick() {
        this.rootRef.el.classList.add("o_ssi_dashboard_print_mode");
        this.preparePrintSnapshot();
        window.print();
    }

    /**
     * Prepares this dashboard's current DOM for printing, right before
     * "onPrintClick" calls "window.print()":
     *
     * - Every ".o_ssi_dashboard_item" tile's current on-screen height is
     *   frozen as an inline "height" (restored afterwards) — the print
     *   layout switches the grid to a single full-width column (see the
     *   SCSS), so a tile's content can no longer size itself off the
     *   original CSS grid area; freezing the height it already had on
     *   screen keeps every chart's container a non-zero size instead.
     * - Every "canvas" element (drawn by chart item widgets such as
     *   "ssi_dashboard_item_chart") is replaced by a same-sized "img"
     *   built from that canvas' own "toDataURL()", and the canvas itself
     *   is hidden — most browsers print an empty box in place of a
     *   "canvas" otherwise.
     *
     * Every change made here is paired with a matching restore closure
     * pushed onto "this.printRestoreQueue", popped and run in order by
     * "restorePrintSnapshot()" once "onAfterPrint" fires.
     */
    preparePrintSnapshot() {
        const gridEl = this.gridRef.el;
        if (!gridEl) {
            return;
        }
        gridEl.querySelectorAll(":scope > .o_ssi_dashboard_item").forEach((itemEl) => {
            const height = itemEl.getBoundingClientRect().height;
            const previousHeight = itemEl.style.height;
            itemEl.style.height = `${height}px`;
            this.printRestoreQueue.push(() => {
                itemEl.style.height = previousHeight;
            });
        });
        gridEl.querySelectorAll("canvas").forEach((canvas) => {
            let dataUrl = null;
            try {
                dataUrl = canvas.toDataURL("image/png");
            } catch {
                return;
            }
            const image = document.createElement("img");
            image.src = dataUrl;
            image.className = "o_ssi_dashboard_print_canvas_image";
            canvas.insertAdjacentElement("afterend", image);
            const previousDisplay = canvas.style.display;
            canvas.style.display = "none";
            this.printRestoreQueue.push(() => {
                canvas.style.display = previousDisplay;
                image.remove();
            });
        });
    }

    /**
     * Runs every restore closure queued by "preparePrintSnapshot()", in
     * reverse (last change made, first undone), and empties the queue.
     */
    restorePrintSnapshot() {
        while (this.printRestoreQueue.length) {
            this.printRestoreQueue.pop()();
        }
    }

    /**
     * Bound to the browser's own "afterprint" event (see setup()),
     * fired once the print dialog is dismissed regardless of how it was
     * opened. Always safe to call even when "onPrintClick" was never
     * pressed — "printRestoreQueue" is simply empty in that case.
     */
    onAfterPrint() {
        this.rootRef.el.classList.remove("o_ssi_dashboard_print_mode");
        this.restorePrintSnapshot();
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

    /**
     * Bound to DashboardItem's "onEditClick" prop, only reachable when
     * "state.isAdmin" (see DashboardItem's "props.isAdmin").
     *
     * Opens "itemId"'s own form — the same
     * "ssi_dashboard.dashboard_item_view_form" already used by
     * dashboard.item.action_open_item_goals()/_open_item_goals() — as a
     * dialog ("target": "new"). "views: [[false, "form"]]" lets the web
     * client resolve that model's own (only) form view instead of this
     * component having to know its database id. Regardless of how the
     * dialog is closed (Save or Discard), "onClose" fires and
     * reloadItem() re-fetches this one item — cheap and idempotent even
     * when nothing actually changed.
     *
     * @param {Number} itemId
     */
    onEditItemClick(itemId) {
        this.action.doAction(
            {
                type: "ir.actions.act_window",
                res_model: "dashboard.item",
                res_id: itemId,
                view_mode: "form",
                views: [[false, "form"]],
                target: "new",
            },
            {onClose: () => this.reloadItem(itemId)}
        );
    }

    /**
     * Re-fetches the whole dashboard payload (there is no
     * single-item endpoint — "active_filters" resolution lives on
     * dashboard.dashboard, see get_dashboard_payload()) but only
     * merges "itemId"'s own entry into "dashboard.items", so the rest
     * of the grid — and everything else in "state"/"dashboard" — is
     * left exactly as it was. Reuses "currentFilters" so the merged
     * entry reflects the same filter/date-range selection every other
     * tile is currently showing.
     *
     * If "itemId" is no longer present in the result (e.g. it was
     * deleted through the dialog), its tile is removed instead of
     * being left showing stale data.
     *
     * Also reuses "dashboard.active_layout_id" (backlog issue #50), so
     * the merged entry is positioned exactly like every other tile
     * currently showing, whichever layout is selected.
     *
     * @param {Number} itemId
     */
    async reloadItem(itemId) {
        const payload = await this.orm.call(
            "dashboard.dashboard",
            "get_dashboard_payload",
            [[this.dashboardId], this.currentFilters, this.dashboard.active_layout_id]
        );
        const updated = payload.items.find((item) => item.id === itemId);
        const index = this.dashboard.items.findIndex((item) => item.id === itemId);
        if (updated) {
            if (index === -1) {
                this.dashboard.items.push(updated);
            } else {
                this.dashboard.items[index] = updated;
            }
        } else if (index !== -1) {
            this.dashboard.items.splice(index, 1);
        }
    }
}

registry.category("actions").add("ssi_dashboard.dashboard_view", DashboardAction);
