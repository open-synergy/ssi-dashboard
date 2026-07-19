import {Component, useState} from "@odoo/owl";
import {formatFloat} from "@web/core/utils/numbers";
import {registry} from "@web/core/registry";

const INDIAN_SCALE_UNITS = [
    {threshold: 1e7, suffix: "Cr"},
    {threshold: 1e5, suffix: "L"},
];

/**
 * Renders a "list" dashboard item — a table of the item's fetched data.
 * Registered under registry.category("ssi_dashboard.item_widgets") for the
 * "dashboard.item" type "list" (see
 * ssi_dashboard_item_list/models/dashboard_item.py,
 * _prepare_render_payload_list()).
 *
 * The "item" prop is one entry of "items" from
 * dashboard.dashboard.get_dashboard_payload(), enriched by
 * _prepare_render_payload_list() with "columns" (list of {key, name,
 * column_type}, built from real "dashboard.item.column" rows — no
 * "config" JSON is read anywhere here), "rows" (list of dict keyed like
 * "columns", each optionally carrying "group_label"), "list_mode"
 * ("flat"/"grouped"), "page_size" and, only when "list_mode" is
 * "grouped", "groups" (list of {label, rows, subtotals}). Colors come
 * from the dashboard's own CSS custom properties (set by DashboardAction
 * from dashboard.color_scheme) — this component carries no palette of
 * its own.
 *
 * Pagination always slices the full "rows" list (not "groups"), and — in
 * "grouped" mode — a subtotal row is rendered right after the last row of
 * each group that is visible on the current page, reusing that group's
 * server-computed "subtotals" regardless of whether the rest of the
 * group lands on a different page. This keeps the meaning of "page_size"
 * ("how many already-fetched rows are shown at once") identical between
 * "flat" and "grouped" — no separate "groups per page" notion.
 */
export class DashboardItemList extends Component {
    static template = "ssi_dashboard_item_list.DashboardItemList";
    static props = {item: Object};

    setup() {
        this.state = useState({page: 0});
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
     * the unit symbol at "unit_position". Used for "number" and
     * "deviation" columns, so both kinds stay visually consistent with
     * the rest of the dashboard (tiles, charts).
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
     * @returns {Boolean} true when this item's "list_mode" is "grouped".
     */
    get isGrouped() {
        return this.props.item.list_mode === "grouped";
    }

    /**
     * @returns {Number} this item's "page_size", defaulting to 10 before
     *     it ever became part of the payload.
     */
    get pageSize() {
        return this.props.item.page_size || 10;
    }

    /**
     * @returns {Object} "group_label" -> that group's "subtotals" dict
     *     (see dashboard.item._compute_list_groups()), built from
     *     "groups" — empty when this item is not "grouped".
     */
    get subtotalsByLabel() {
        const groups = this.props.item.groups || [];
        const map = {};
        for (const group of groups) {
            map[group.label] = group.subtotals || {};
        }
        return map;
    }

    /**
     * Every row of "rows", each carrying whether it is the last row of
     * its group ("isGroupEnd") — computed once over the full,
     * unpaginated list so a group split across two pages still gets its
     * subtotal row exactly once, at its real end.
     *
     * @returns {Array} list of {row, isGroupEnd}.
     */
    get decoratedRows() {
        const rows = this.props.item.rows || [];
        return rows.map((row, index) => {
            const nextRow = rows[index + 1];
            const isGroupEnd = !nextRow || nextRow.group_label !== row.group_label;
            return {row, isGroupEnd};
        });
    }

    /**
     * @returns {Number} total number of pages, at least 1 even when
     *     "rows" is empty, so the pager never divides by zero.
     */
    get pageCount() {
        const total = (this.props.item.rows || []).length;
        return Math.max(1, Math.ceil(total / this.pageSize));
    }

    /**
     * @returns {Array} the slice of decoratedRows shown on the current
     *     page.
     */
    get pagedRows() {
        const start = this.state.page * this.pageSize;
        return this.decoratedRows.slice(start, start + this.pageSize);
    }

    /**
     * @returns {String} e.g. "2 / 5".
     */
    get pageLabel() {
        return `${this.state.page + 1} / ${this.pageCount}`;
    }

    previousPage() {
        if (this.state.page > 0) {
            this.state.page -= 1;
        }
    }

    nextPage() {
        if (this.state.page < this.pageCount - 1) {
            this.state.page += 1;
        }
    }

    /**
     * @param {Object} row one entry of `this.props.item.rows`
     * @param {Object} column one entry of `this.props.item.columns`
     * @returns {String} `row`'s value for `column.key`, formatted
     *     following "number_format_config" for "number"/"deviation"
     *     columns, or "" when the row does not carry that key.
     */
    cellValue(row, column) {
        const value = row[column.key];
        if (value === undefined || value === null) {
            return "";
        }
        if (column.column_type === "number" || column.column_type === "deviation") {
            return this.formatValue(value);
        }
        return value;
    }

    /**
     * Value shown in a group's subtotal row for one column: the group's
     * label (prefixed) in the first column, the summed "subtotals" value
     * for "number"/"deviation" columns, and an empty cell for "text"
     * columns elsewhere.
     *
     * @param {Object} row a row belonging to the group being subtotaled
     * @param {Object} column one entry of `this.props.item.columns`
     * @param {Number} columnIndex index of `column` within
     *     `this.props.item.columns`
     * @returns {String}
     */
    subtotalCellValue(row, column, columnIndex) {
        if (columnIndex === 0) {
            return `Subtotal — ${row.group_label ?? ""}`;
        }
        if (column.column_type === "number" || column.column_type === "deviation") {
            const subtotals = this.subtotalsByLabel[row.group_label] || {};
            const value = subtotals[column.key];
            return value === undefined ? "" : this.formatValue(value);
        }
        return "";
    }
}

registry.category("ssi_dashboard.item_widgets").add("list", DashboardItemList);
