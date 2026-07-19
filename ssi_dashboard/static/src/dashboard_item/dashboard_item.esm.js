import {Component, useState} from "@odoo/owl";
import {DashboardItemFallback} from "../dashboard_item_fallback/dashboard_item_fallback.esm";
import {_t} from "@web/core/l10n/translation";
import {registry} from "@web/core/registry";
import {useService} from "@web/core/utils/hooks";

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
 *
 * "props.isAdmin" (mirrors DashboardAction's "state.isAdmin") shows a
 * per-tile 'Edit' button overlaid on top of whatever the type-specific
 * component renders. Pressing it calls "props.onEditClick" with this
 * item's id — DashboardAction.onEditItemClick() opens the item's own
 * form (see models/dashboard_item.py's "dashboard_item_view_form") in a
 * dialog and, once closed, reloads only this one tile (see
 * DashboardAction.reloadItem()) rather than the whole dashboard. Both
 * props are optional so this component keeps working unchanged
 * wherever it is reused without them, e.g.
 * dashboard_item_preview.esm.js's own preview tile, which never shows
 * the button.
 *
 * Also implements "Open Records": clicking a value or segment of the
 * type-specific component opens the list of records behind it (see
 * models/dashboard_item.py's "action_open_records"). The type-specific
 * component never calls the ORM itself — it only marks whichever
 * element represents one data row with a "data-ssi-dashboard-row-
 * domain" attribute (that row's own "row_domain" key, JSON-encoded —
 * see models/dashboard_data_source.py's "_fetch_data_orm") and this
 * wrapper does the rest through event delegation on its own root
 * element (see "onContainerClick"). This is a plain HTML/DOM contract,
 * not an Owl prop, so a type-specific component that does not (yet)
 * implement it is entirely unaffected — it simply renders no element
 * matching that selector, and this handler never fires for it.
 *
 * On top of "Open Records", also implements "Drill-Down" for items whose
 * "props.item.has_drilldown" is true (see models/dashboard_item.py's
 * "drilldown_ids"/"fetch_drilldown_data"): a click on a
 * "data-ssi-dashboard-row-domain" element drills one level deeper
 * instead of opening records, re-rendering the SAME type-specific
 * component with that level's rows ("displayItem" below) rather than
 * navigating away, until the last level of the chain is reached — from
 * then on a click opens records exactly as an item without a chain
 * always has. "this.drilldown.stack" holds one entry per level visited
 * (index 0 = the item's own original view), so going back
 * ("goBack"/"goToLevel") never re-fetches anything, only drops entries
 * off the end. Entirely client-side/in-memory — nothing here is
 * persisted, so a dashboard reload always starts back at level 0.
 *
 * Also shows two download buttons — XLSX/CSV — when
 * "props.item.allow_export" is true (see "canExport"/models/
 * dashboard_item.py's "allow_export"), each linking straight to
 * "controllers/export.py"'s endpoints with this item's id and
 * "props.activeFilters" (mirrors DashboardAction's "currentFilters")
 * carried as query parameters — see "buildExportUrl". Plain browser
 * navigation over an authenticated GET, no fetch/blob handling needed;
 * the server re-checks read access and "allow_export" on its own
 * regardless of what this component shows.
 */
export class DashboardItem extends Component {
    static template = "ssi_dashboard.DashboardItem";
    static props = {
        item: Object,
        useExplicitPosition: {type: Boolean, optional: true},
        isAdmin: {type: Boolean, optional: true},
        activeFilters: {type: Object, optional: true},
        onEditClick: {type: Function, optional: true},
    };

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.drilldown = useState({
            stack: [
                {
                    level: 0,
                    rows: null,
                    groupFieldLabel: null,
                    isLast: !this.props.item.has_drilldown,
                },
            ],
        });
    }

    /**
     * Top of "this.drilldown.stack" — the level currently on screen.
     *
     * @returns {Object}
     */
    get currentDrilldown() {
        return this.drilldown.stack[this.drilldown.stack.length - 1];
    }

    /**
     * "item" prop forwarded to the type-specific component
     * ("this.Component" below). Identical to "props.item" while at
     * level 0 (nothing has been drilled into yet); once drilled in,
     * "data" is swapped for the current level's own rows so the
     * type-specific component renders unchanged, only fed different
     * rows — it never needs to know drill-down exists.
     *
     * @returns {Object}
     */
    get displayItem() {
        const current = this.currentDrilldown;
        if (current.level === 0) {
            return this.props.item;
        }
        return {...this.props.item, data: current.rows};
    }

    /**
     * Whether the "back" control and breadcrumb trail are shown at all —
     * true once at least one level has been drilled into.
     *
     * @returns {Boolean}
     */
    get canDrillBack() {
        return this.drilldown.stack.length > 1;
    }

    get backLabel() {
        return _t("Back");
    }

    /**
     * One entry per level drilled into so far (excludes the level 0 root
     * entry, which has no field to label), each carrying the stack index
     * "goToLevel" needs to jump straight back to it.
     *
     * @returns {Array}
     */
    get drilldownTrail() {
        return this.drilldown.stack
            .map((entry, index) => ({index, entry}))
            .slice(1)
            .map(({index, entry}) => ({
                index,
                label: entry.groupFieldLabel || _t("Level %s", entry.level),
            }));
    }

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

    /**
     * Turn "props.item.theme" (see models/dashboard_item.py,
     * _get_theme_config()) into the "--ssi-dashboard-item-header-color"/
     * "--ssi-dashboard-item-border-color" CSS custom properties consumed
     * by this component's own SCSS and by whichever component renders
     * the item's content (e.g. DashboardItemFallback) — so both the
     * tile's border and any header area it renders pick up the same
     * theme without either side hardcoding it.
     *
     * "theme.name" "inherit" sets neither property, leaving the
     * dashboard's own styling untouched. "primary"/"success"/"warning"/
     * "danger" point both properties at the matching
     * "--ssi-dashboard-<name>" variable already set on the dashboard's
     * root element by DashboardAction's "rootStyle" (built server-side
     * from the color scheme) — the browser resolves the color, this
     * component never copies it. "custom" uses "theme.header_color"/
     * "theme.border_color" verbatim, falling back to not setting the
     * property when a color is empty.
     *
     * @returns {String}
     */
    get themeStyle() {
        const theme = this.props.item.theme;
        if (!theme || theme.name === "inherit") {
            return "";
        }
        const isCustom = theme.name === "custom";
        const headerColor = isCustom
            ? theme.header_color
            : `var(--ssi-dashboard-${theme.name})`;
        const borderColor = isCustom
            ? theme.border_color
            : `var(--ssi-dashboard-${theme.name})`;
        const declarations = [];
        if (headerColor) {
            declarations.push(`--ssi-dashboard-item-header-color: ${headerColor}`);
        }
        if (borderColor) {
            declarations.push(`--ssi-dashboard-item-border-color: ${borderColor}`);
        }
        return declarations.join("; ");
    }

    get editLabel() {
        return _t("Edit");
    }

    /**
     * Bound to the 'Edit' button, only rendered when "props.isAdmin".
     * Forwards to "props.onEditClick" with this item's own id — see the
     * class docstring for what happens next.
     */
    onEditClick() {
        this.props.onEditClick(this.props.item.id);
    }

    /**
     * Whether the download buttons are shown at all — mirrors
     * "props.item.allow_export" (see models/dashboard_item.py's
     * "allow_export"). The export endpoints (see "controllers/
     * export.py") re-check this server-side regardless of what this
     * getter hides in the browser.
     *
     * @returns {Boolean}
     */
    get canExport() {
        return Boolean(this.props.item.allow_export);
    }

    get exportXlsxLabel() {
        return _t("Export XLSX");
    }

    get exportCsvLabel() {
        return _t("Export CSV");
    }

    /**
     * Query-string URL for one of the export endpoints, always carrying
     * this item's own id and — when available — "props.activeFilters"
     * (see DashboardAction's "currentFilters", forwarded down as this
     * prop), JSON-encoded exactly as
     * "dashboard.item.prepare_export_data" expects its own
     * "active_filters" argument. Forwarding the very same selection the
     * tile itself was last rendered with is the whole point (backlog
     * issue #43's Keputusan Desain) — a download built without it could
     * silently disagree with what is on screen.
     *
     * @param {String} format "xlsx" or "csv"
     * @returns {String}
     */
    buildExportUrl(format) {
        const params = new URLSearchParams();
        params.set("item_id", this.props.item.id);
        if (this.props.activeFilters) {
            params.set("active_filters", JSON.stringify(this.props.activeFilters));
        }
        return `/ssi_dashboard/export/${format}?${params.toString()}`;
    }

    get exportXlsxUrl() {
        return this.buildExportUrl("xlsx");
    }

    get exportCsvUrl() {
        return this.buildExportUrl("csv");
    }

    /**
     * Bound to both download links — only stops the click from
     * bubbling up to "onContainerClick" (see the class docstring's
     * "data-ssi-dashboard-row-domain" contract); the link's own default
     * navigation, which triggers the actual download, is left alone
     * (no "preventDefault").
     *
     * @param {MouseEvent} ev
     */
    onExportClick(ev) {
        ev.stopPropagation();
    }

    /**
     * Whether this item exposes "Open Records" clicks at all — mirrors
     * "props.item.allow_open_records" (see models/dashboard_item.py's
     * "allow_open_records"). Also drives the pointer cursor on
     * clickable elements (see dashboard_item.scss) — false here means
     * no element of this tile shows one, regardless of what the
     * type-specific component renders.
     *
     * @returns {Boolean}
     */
    get canOpenRecords() {
        return Boolean(this.props.item.allow_open_records);
    }

    /**
     * Delegated click handler bound on this item's own root element
     * (".o_ssi_dashboard_item", see the template). See the class
     * docstring for the "data-ssi-dashboard-row-domain" contract this
     * relies on. A malformed (non-JSON) attribute value is treated the
     * same as no match at all — the click is silently ignored rather
     * than raising in the browser.
     *
     * Dispatches to "drillInto" while the current drill-down level is
     * not yet the last one of the chain, and to "openRecords" otherwise
     * — either because this item has no chain at all
     * ("props.item.has_drilldown" false, "currentDrilldown.isLast"
     * already true from "setup()") or because the chain has been
     * followed all the way down.
     *
     * @param {MouseEvent} ev
     */
    onContainerClick(ev) {
        if (!this.canOpenRecords) {
            return;
        }
        const target = ev.target.closest("[data-ssi-dashboard-row-domain]");
        if (!target) {
            return;
        }
        let rowDomain = null;
        try {
            rowDomain = JSON.parse(target.dataset.ssiDashboardRowDomain);
        } catch {
            return;
        }
        if (this.currentDrilldown.isLast) {
            this.openRecords(rowDomain);
        } else {
            this.drillInto(rowDomain);
        }
    }

    /**
     * Calls "action_open_records" (models/dashboard_item.py) with
     * "rowDomain" and forwards the resulting window action to Odoo's
     * own action service. The browser never builds or trusts a domain
     * itself — "action_open_records" rebuilds/ANDs in this item's own
     * data source domain server-side before returning the action (see
     * that method's docstring).
     *
     * @param {Array} rowDomain
     */
    async openRecords(rowDomain) {
        const action = await this.orm.call("dashboard.item", "action_open_records", [
            [this.props.item.id],
            rowDomain,
        ]);
        this.action.doAction(action);
    }

    /**
     * Calls "fetch_drilldown_data" (models/dashboard_item.py) for the
     * level right after "currentDrilldown", passing "rowDomain" (the
     * clicked row's own domain) as "path" — already self-contained (see
     * that method's docstring), so no accumulation across earlier levels
     * is needed here. Pushes the result onto "this.drilldown.stack",
     * which re-renders "displayItem" with the new level's rows.
     *
     * @param {Array} rowDomain
     */
    async drillInto(rowDomain) {
        const nextLevel = this.currentDrilldown.level + 1;
        const result = await this.orm.call("dashboard.item", "fetch_drilldown_data", [
            [this.props.item.id],
            nextLevel,
            rowDomain,
        ]);
        this.drilldown.stack = [
            ...this.drilldown.stack,
            {
                level: result.level,
                rows: result.rows,
                groupFieldLabel: result.group_field_label,
                isLast: result.is_last,
            },
        ];
    }

    /**
     * Bound to the breadcrumb trail's "Back" control — drops the last
     * entry off "this.drilldown.stack", restoring the previous level's
     * already-fetched rows without any further RPC call.
     */
    goBack() {
        if (this.canDrillBack) {
            this.drilldown.stack = this.drilldown.stack.slice(0, -1);
        }
    }

    /**
     * Bound to one breadcrumb trail segment — jumps straight back to
     * that level, dropping every entry pushed after it. Restores
     * already-fetched rows, no RPC call.
     *
     * @param {Number} stackIndex
     */
    goToLevel(stackIndex) {
        this.drilldown.stack = this.drilldown.stack.slice(0, stackIndex + 1);
    }
}
