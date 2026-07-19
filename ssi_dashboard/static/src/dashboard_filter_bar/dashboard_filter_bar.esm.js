import {Component, useState} from "@odoo/owl";
import {DateTimeInput} from "@web/core/datetime/datetime_input";
import {_t} from "@web/core/l10n/translation";

/**
 * Global filter bar rendered above a dashboard's item grid (see
 * ../dashboard_action/dashboard_action.esm.js). Renders one toggle chip
 * per "domain"/"field" dashboard.filter entry plus a single date range
 * picker (independent of any "date" typed filter — see
 * dashboard.filter's docstring in models/dashboard_filter.py), and calls
 * "onChange" with the dict shape dashboard.dashboard.get_dashboard_payload
 * expects as its "active_filters" argument whenever the selection changes.
 *
 * Props:
 *  - filters: the "filters" list from get_dashboard_payload's result —
 *    [{id, name, filter_type, default_active}, ...].
 *  - activeFilterIds: the "active_filter_ids" list from the same
 *    payload — filters considered active when the bar is first mounted.
 *  - onChange: ({filter_ids, date_start, date_end}) => any, called with
 *    the new selection every time a chip is toggled, a date is applied,
 *    or "Reset" is pressed.
 */
export class DashboardFilterBar extends Component {
    static template = "ssi_dashboard.DashboardFilterBar";
    static components = {DateTimeInput};
    static props = {
        filters: Array,
        activeFilterIds: Array,
        onChange: Function,
    };

    setup() {
        this.state = useState({
            activeFilterIds: [...this.props.activeFilterIds],
            dateStart: null,
            dateEnd: null,
        });
    }

    get resetLabel() {
        return _t("Reset");
    }

    get dateStartPlaceholder() {
        return _t("From");
    }

    get dateEndPlaceholder() {
        return _t("To");
    }

    /**
     * "date" typed filters carry no domain and are not toggleable — the
     * date range picker below is always shown instead. See
     * models/dashboard_filter.py, DashboardFilter's docstring.
     *
     * @returns {Array}
     */
    get toggleableFilters() {
        return this.props.filters.filter((filter) => filter.filter_type !== "date");
    }

    /**
     * @param {Number} filterId
     * @returns {Boolean}
     */
    isActive(filterId) {
        return this.state.activeFilterIds.includes(filterId);
    }

    /**
     * @param {Number} filterId
     */
    onToggleFilter(filterId) {
        if (this.isActive(filterId)) {
            this.state.activeFilterIds = this.state.activeFilterIds.filter(
                (id) => id !== filterId
            );
        } else {
            this.state.activeFilterIds = [...this.state.activeFilterIds, filterId];
        }
        this.notifyChange();
    }

    /**
     * @param {luxon.DateTime|null} value
     */
    onDateStartApply(value) {
        this.state.dateStart = value || null;
        this.notifyChange();
    }

    /**
     * @param {luxon.DateTime|null} value
     */
    onDateEndApply(value) {
        this.state.dateEnd = value || null;
        this.notifyChange();
    }

    /**
     * Returns every selection to its initial state: the filters active
     * when the dashboard was first opened (props.activeFilterIds), and
     * no date range override.
     */
    onReset() {
        this.state.activeFilterIds = [...this.props.activeFilterIds];
        this.state.dateStart = null;
        this.state.dateEnd = null;
        this.notifyChange();
    }

    notifyChange() {
        this.props.onChange({
            filter_ids: this.state.activeFilterIds,
            date_start: this.state.dateStart ? this.state.dateStart.toISODate() : null,
            date_end: this.state.dateEnd ? this.state.dateEnd.toISODate() : null,
        });
    }
}
