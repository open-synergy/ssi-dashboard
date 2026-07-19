import {Component} from "@odoo/owl";
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
 */
export class DashboardItem extends Component {
    static template = "ssi_dashboard.DashboardItem";
    static props = {
        item: Object,
        useExplicitPosition: {type: Boolean, optional: true},
        isAdmin: {type: Boolean, optional: true},
        onEditClick: {type: Function, optional: true},
    };

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
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
        this.openRecords(rowDomain);
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
}
