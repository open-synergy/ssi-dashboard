import {Component, onMounted, onWillStart, onWillUnmount, useRef} from "@odoo/owl";
import {loadBundle} from "@web/core/assets";
import {registry} from "@web/core/registry";

/* global Chart */

/**
 * Renders a "chart" dashboard item — a bar, line or pie chart built with
 * Odoo's bundled Chart.js ("web.chartjs_lib"). Registered under
 * registry.category("ssi_dashboard.item_widgets") for the "dashboard.item"
 * type "chart" (see ssi_dashboard_item_chart/models/dashboard_item.py,
 * _prepare_render_payload_chart()).
 *
 * The "item" prop is one entry of "items" from
 * dashboard.dashboard.get_dashboard_payload(), enriched with "chart_type"
 * and "chart_data" (labels + datasets) by _prepare_render_payload_chart().
 * Series colors are read from the dashboard's own
 * "--ssi-dashboard-chart-<n>" CSS custom properties (set by DashboardAction
 * from dashboard.color_scheme) at mount time — this component carries no
 * palette of its own; an index without a matching property falls back to
 * Chart.js' own default color rotation.
 */
export class DashboardItemChart extends Component {
    static template = "ssi_dashboard_item_chart.DashboardItemChart";
    static props = {item: Object};

    setup() {
        this.canvasRef = useRef("canvas");
        this.chart = null;

        onWillStart(async () => await loadBundle("web.chartjs_lib"));
        onMounted(() => this.renderChart());
        onWillUnmount(() => this.destroyChart());
    }

    /**
     * Reads `count` "--ssi-dashboard-chart-<n>" CSS custom properties off
     * this component's own root element, cycling through 8 declared slots
     * when there are more series/slices than declared colors.
     *
     * @param {Number} count
     * @returns {Array} one CSS color string per requested slot, or
     *     `undefined` for any slot whose custom property is not set.
     */
    getSeriesColors(count) {
        const style = getComputedStyle(this.canvasRef.el);
        const colors = [];
        for (let index = 0; index < count; index++) {
            const key = `--ssi-dashboard-chart-${(index % 8) + 1}`;
            const value = style.getPropertyValue(key).trim();
            colors.push(value || undefined);
        }
        return colors;
    }

    renderChart() {
        const {chart_type: chartType, chart_data: chartData} = this.props.item;
        const isSliced = chartType === "pie";
        const datasets = (chartData.datasets || []).map((dataset) => {
            const colors = this.getSeriesColors(isSliced ? dataset.data.length : 1);
            return isSliced
                ? {...dataset, backgroundColor: colors}
                : {...dataset, backgroundColor: colors[0], borderColor: colors[0]};
        });
        this.chart = new Chart(this.canvasRef.el, {
            type: chartType,
            data: {labels: chartData.labels, datasets},
            options: {
                responsive: true,
                maintainAspectRatio: false,
            },
        });
    }

    destroyChart() {
        if (this.chart) {
            this.chart.destroy();
            this.chart = null;
        }
    }
}

registry.category("ssi_dashboard.item_widgets").add("chart", DashboardItemChart);
