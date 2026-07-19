import {Component} from "@odoo/owl";
import {DashboardItemFallback} from "../dashboard_item_fallback/dashboard_item_fallback.esm";
import {_t} from "@web/core/l10n/translation";
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
 */
export class DashboardItem extends Component {
    static template = "ssi_dashboard.DashboardItem";
    static props = {
        item: Object,
        useExplicitPosition: {type: Boolean, optional: true},
        isAdmin: {type: Boolean, optional: true},
        onEditClick: {type: Function, optional: true},
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
}
