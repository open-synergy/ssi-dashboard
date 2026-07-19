import {Component} from "@odoo/owl";
import {formatFloat} from "@web/core/utils/numbers";
import {registry} from "@web/core/registry";

const INDIAN_SCALE_UNITS = [
    {threshold: 1e7, suffix: "Cr"},
    {threshold: 1e5, suffix: "L"},
];

/**
 * Renders a "kpi" dashboard item — a realized value shown side by side
 * with either its target ("KPI With Target" layout) or a comparison
 * period ("Data Comparison" layout), plus the achievement percentage and
 * a movement marker. Registered under
 * registry.category("ssi_dashboard.item_widgets") for the "dashboard.item"
 * type "kpi" (see ssi_dashboard_item_kpi/models/dashboard_item.py,
 * _prepare_render_payload_kpi()).
 *
 * The "item" prop is one entry of "items" from
 * dashboard.dashboard.get_dashboard_payload(), enriched by
 * _prepare_render_payload_kpi() with a "kpi" key ("layout", "display",
 * "invert_direction", "value", "reference", "achievement", "direction")
 * and by core dashboard.item._prepare_render_payload() with "name" and
 * "number_format_config". Number formatting mirrors
 * ssi_dashboard_item_tile.DashboardItemTile so values look the same
 * across item types.
 */
export class DashboardItemKpi extends Component {
    static template = "ssi_dashboard_item_kpi.DashboardItemKpi";
    static props = {item: Object};

    /**
     * @returns {Object} this item's "kpi" payload key, always present for
     *     a "kpi" item — see _prepare_render_payload_kpi().
     */
    get kpi() {
        return this.props.item.kpi;
    }

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
     * the unit symbol at "unit_position". Used for "value" and, for the
     * "Number" kpi_display, the "reference" value too.
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

    /**
     * @returns {String} "value", formatted.
     */
    get formattedValue() {
        return this.formatValue(this.kpi.value);
    }

    /**
     * @returns {String} "reference" (target or comparison number),
     *     formatted the same way as "value".
     */
    get formattedReference() {
        return this.formatValue(this.kpi.reference);
    }

    /**
     * Formats "achievement" as a percentage string, following
     * "precision_digits" from "number_format_config".
     *
     * @returns {String|null} e.g. "75%", or null when "achievement" is
     *     null (this item's "reference" is zero).
     */
    get formattedAchievementPercentage() {
        const achievement = this.kpi.achievement;
        if (achievement === null || achievement === undefined) {
            return null;
        }
        const precisionDigits = this.numberFormatConfig.precision_digits ?? 2;
        return `${formatFloat(achievement * 100, {
            digits: [0, precisionDigits],
            trailingZeros: false,
        })}%`;
    }

    /**
     * Builds the comparison number shown alongside "value", shaped
     * following "display" ("number_format_config"'s Selection):
     * "number" — "reference" alone; "percentage" — "achievement" as a
     * percentage; "ratio" — "value / reference".
     *
     * @returns {String} a dash ("—") when the shape needing "achievement"
     *     has none to show (zero "reference").
     */
    get comparisonText() {
        const display = this.kpi.display;
        if (display === "number") {
            return this.formattedReference;
        }
        if (display === "ratio") {
            return `${this.formattedValue} / ${this.formattedReference}`;
        }
        return this.formattedAchievementPercentage || "—";
    }

    /**
     * @returns {Number} "achievement" clamped to the 0-100 range used by
     *     the progress bar's width, for the "target" layout. 0 when
     *     "achievement" is null (zero "reference").
     */
    get progressPercent() {
        const achievement = this.kpi.achievement;
        if (achievement === null || achievement === undefined) {
            return 0;
        }
        return Math.max(0, Math.min(100, achievement * 100));
    }

    /**
     * @returns {String} inline style for the progress bar's width, for
     *     the "target" layout.
     */
    get progressBarStyle() {
        return `width: ${this.progressPercent}%;`;
    }

    /**
     * @returns {String} Font Awesome class for the movement marker
     *     ("direction").
     */
    get directionIconClass() {
        if (this.kpi.direction === "up") {
            return "fa fa-arrow-up";
        }
        if (this.kpi.direction === "down") {
            return "fa fa-arrow-down";
        }
        return "fa fa-minus";
    }

    /**
     * @returns {String} CSS class coloring the movement marker — "up" is
     *     always shown as positive and "down" as negative, since
     *     "direction" itself already accounts for "invert_direction"
     *     server-side (dashboard.item._get_kpi_direction()).
     */
    get directionColorClass() {
        if (this.kpi.direction === "up") {
            return "o_ssi_dashboard_item_kpi_direction_up";
        }
        if (this.kpi.direction === "down") {
            return "o_ssi_dashboard_item_kpi_direction_down";
        }
        return "o_ssi_dashboard_item_kpi_direction_flat";
    }
}

registry.category("ssi_dashboard.item_widgets").add("kpi", DashboardItemKpi);
