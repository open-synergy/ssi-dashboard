import {Component} from "@odoo/owl";
import {formatFloat} from "@web/core/utils/numbers";
import {registry} from "@web/core/registry";

const ROW_KEY_BLOCKLIST = new Set([
    "group_key",
    "group_label",
    "sub_group_key",
    "sub_group_label",
]);

const INDIAN_SCALE_UNITS = [
    {threshold: 1e7, suffix: "Cr"},
    {threshold: 1e5, suffix: "L"},
];

/**
 * Picks the first measure value out of a row built by
 * dashboard.data_source._fetch_data_orm(), skipping the grouping
 * metadata keys it adds when a 'Group By Field' is configured. Shared by
 * the "value" (current period) and "comparisonValue" (layout_3) getters
 * below, which both read one row of raw data the same way
 * DashboardItem._get_tile_value() does server-side.
 *
 * @param {Object} row
 * @returns {Number}
 */
function firstMeasureValue(row) {
    for (const [key, value] of Object.entries(row)) {
        if (ROW_KEY_BLOCKLIST.has(key)) {
            continue;
        }
        return value || 0;
    }
    return 0;
}

/**
 * Renders a "tile" dashboard item — a single aggregate number, decorated
 * according to its own "tile_layout" (one of six arrangements). Registered
 * under registry.category("ssi_dashboard.item_widgets") for the
 * "dashboard.item" type "tile" (see
 * ssi_dashboard_item_tile/models/dashboard_item.py,
 * _prepare_render_payload_tile()).
 *
 * The "item" prop is one entry of "items" from
 * dashboard.dashboard.get_dashboard_payload(), enriched by
 * _prepare_render_payload_tile() with "tile_layout", "tile_icon",
 * "tile_background_color", "tile_text_color" and "value", and by core
 * dashboard.item._prepare_render_payload() with "name",
 * "number_format_config" and, only when configured, "comparison_data"
 * (layout_3) / "goal" (layout_4). This single component covers all six
 * layouts through template branches — no per-layout component is
 * registered.
 */
export class DashboardItemTile extends Component {
    static template = "ssi_dashboard_item_tile.DashboardItemTile";
    static props = {item: Object};

    /**
     * @returns {Object} this item's "number_format_config" (see
     *     dashboard.item._get_number_format_config()), or {} before it
     *     ever became part of the payload.
     */
    get numberFormatConfig() {
        return this.props.item.number_format_config || {};
    }

    /**
     * Formats a raw number following "number_format_config" — multiplier,
     * then abbreviation ("number_format"), then "precision_digits", then
     * the unit symbol at "unit_position". Used for the tile's own "value"
     * and, for layout_3, the comparison value — both read the same
     * configuration so they stay visually consistent.
     *
     * @param {Number} rawValue
     * @returns {String}
     */
    formatValue(rawValue) {
        const config = this.numberFormatConfig;
        const multiplier = config.multiplier === undefined ? 1 : config.multiplier;
        const precisionDigits =
            config.precision_digits === undefined ? 2 : config.precision_digits;
        const value = (rawValue || 0) * multiplier;
        const formatted = this.formatByScale(
            value,
            config.number_format,
            precisionDigits
        );
        return this.withUnit(formatted, config);
    }

    /**
     * @param {Number} value already multiplied
     * @param {String} numberFormat "number_format_config"'s "number_format"
     * @param {Number} precisionDigits
     * @returns {String}
     */
    formatByScale(value, numberFormat, precisionDigits) {
        if (numberFormat === "short") {
            return formatFloat(value, {
                humanReadable: true,
                decimals: precisionDigits,
                trailingZeros: false,
            });
        }
        if (numberFormat === "indian") {
            return this.formatIndianScale(value, precisionDigits);
        }
        return formatFloat(value, {
            digits: [0, precisionDigits],
            trailingZeros: false,
        });
    }

    /**
     * "Indian Scale" abbreviation (lakh = 1e5, crore = 1e7) — not
     * covered by @web/core/utils/numbers, which only knows the
     * thousand/million/billion ("Short Scale") ladder.
     *
     * @param {Number} value already multiplied
     * @param {Number} precisionDigits
     * @returns {String}
     */
    formatIndianScale(value, precisionDigits) {
        const sign = value < 0 ? "-" : "";
        const absValue = Math.abs(value);
        for (const {threshold, suffix} of INDIAN_SCALE_UNITS) {
            if (absValue >= threshold) {
                const scaled = absValue / threshold;
                const digits = formatFloat(scaled, {
                    digits: [0, precisionDigits],
                    trailingZeros: false,
                });
                return `${sign}${digits}${suffix}`;
            }
        }
        const digits = formatFloat(absValue, {
            digits: [0, precisionDigits],
            trailingZeros: false,
        });
        return `${sign}${digits}`;
    }

    /**
     * @param {String} formatted
     * @param {Object} config "number_format_config"
     * @returns {String}
     */
    withUnit(formatted, config) {
        const symbol = config.unit_symbol;
        if (!symbol) {
            return formatted;
        }
        return config.unit_position === "before"
            ? `${symbol}${formatted}`
            : `${formatted}${symbol}`;
    }

    get formattedValue() {
        return this.formatValue(this.props.item.value);
    }

    /**
     * Layout_3 ("Value With Comparison") — the first row of the first
     * comparison range, read the same way "value" is (see
     * firstMeasureValue()). "comparison_data" is only present on the
     * payload when the data source's "comparison" is not "none" — see
     * dashboard.item._prepare_render_payload().
     *
     * @returns {string|null} formatted comparison value, or null when no
     *     comparison data is available to show.
     */
    get formattedComparisonValue() {
        const comparisonData = this.props.item.comparison_data;
        if (!comparisonData || !comparisonData.length) {
            return null;
        }
        const rows = comparisonData[0];
        if (!rows || !rows.length) {
            return null;
        }
        return this.formatValue(firstMeasureValue(rows[0]));
    }

    /**
     * Layout_4 ("Value With Target") — "goal" is only present on the
     * payload when this item's "goal_type" is not "none" — see
     * dashboard.item._prepare_render_payload().
     *
     * @returns {string|null}
     */
    get formattedGoalValue() {
        const goal = this.props.item.goal;
        if (goal === undefined) {
            return null;
        }
        return this.formatValue(goal);
    }

    /**
     * Layout_5 ("Value With Sparkline") — one point per row of this
     * item's own fetched "data" (unlike "value", every row is used here,
     * not just the first — a sparkline draws a trend, a tile's "value"
     * shows a single instant). Points are normalized to a 0-100 x 0-30
     * viewBox so the SVG scales to any tile size.
     *
     * @returns {String} SVG polyline "points" attribute value, empty when
     *     there are fewer than two rows to draw a line between.
     */
    get sparklinePoints() {
        const rows = this.props.item.data || [];
        const values = rows.map(firstMeasureValue);
        if (values.length < 2) {
            return "";
        }
        const min = Math.min(...values);
        const max = Math.max(...values);
        const range = max - min || 1;
        const stepX = 100 / (values.length - 1);
        return values
            .map((value, index) => {
                const x = index * stepX;
                const y = 30 - ((value - min) / range) * 30;
                return `${x},${y}`;
            })
            .join(" ");
    }

    /**
     * @returns {String} inline style for the tile's own background/text
     *     colors, falling back to the dashboard's color scheme variables
     *     when this item does not override them.
     */
    get tileStyle() {
        const item = this.props.item;
        const background = item.tile_background_color || "var(--ssi-dashboard-surface)";
        const color = item.tile_text_color || "var(--ssi-dashboard-text)";
        return `background-color: ${background}; color: ${color};`;
    }

    /**
     * @returns {String} Font Awesome class(es) for "tile_icon", empty
     *     when not configured.
     */
    get iconClass() {
        return this.props.item.tile_icon ? `fa ${this.props.item.tile_icon}` : "";
    }
}

registry.category("ssi_dashboard.item_widgets").add("tile", DashboardItemTile);
