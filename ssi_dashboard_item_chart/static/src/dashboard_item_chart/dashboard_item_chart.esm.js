import {Component, onMounted, onWillStart, onWillUnmount, useRef} from "@odoo/owl";
import {loadBundle} from "@web/core/assets";
import {registry} from "@web/core/registry";

/* global Chart */

const SLICED_CHART_TYPES = ["pie", "doughnut", "polar"];

/**
 * Renders a "chart" dashboard item — one of seven chart kinds, built with
 * Odoo's bundled Chart.js ("web.chartjs_lib"). Registered under
 * registry.category("ssi_dashboard.item_widgets") for the "dashboard.item"
 * type "chart" (see ssi_dashboard_item_chart/models/dashboard_item.py,
 * _prepare_render_payload_chart()).
 *
 * The "item" prop is one entry of "items" from
 * dashboard.dashboard.get_dashboard_payload(), enriched with a "chart" key
 * by _prepare_render_payload_chart() — {type, labels, datasets, show_legend}.
 * "datasets" already carries one entry per second dimension value or per
 * measure, built server-side; this component only maps "type" to a Chart.js
 * type/option and assigns series colors — no aggregation happens here.
 *
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

    /**
     * Maps this item's server-side "chart.type" (all seven kinds from
     * ssi_dashboard_item_chart/models/dashboard_item.py) to the Chart.js
     * chart "type" plus any extra chart/dataset options that mapping
     * needs. "horizontal_bar" is a Chart.js "bar" chart with
     * `indexAxis: "y"`. "area" is a Chart.js "line" chart with `fill:
     * true` on every dataset. "polar" is Chart.js' "polarArea" (its exact
     * spelling). Every other value ("bar", "line", "pie", "doughnut") is
     * already a valid Chart.js type and needs no mapping.
     *
     * @param {String} chartType
     * @returns {Object} {chartJsType, chartOptions, datasetOptions}
     */
    mapChartType(chartType) {
        if (chartType === "horizontal_bar") {
            return {
                chartJsType: "bar",
                chartOptions: {indexAxis: "y"},
                datasetOptions: {},
            };
        }
        if (chartType === "area") {
            return {
                chartJsType: "line",
                chartOptions: {},
                datasetOptions: {fill: true},
            };
        }
        if (chartType === "polar") {
            return {chartJsType: "polarArea", chartOptions: {}, datasetOptions: {}};
        }
        return {chartJsType: chartType, chartOptions: {}, datasetOptions: {}};
    }

    renderChart() {
        const {chart} = this.props.item;
        const {chartJsType, chartOptions, datasetOptions} = this.mapChartType(
            chart.type
        );
        const isSliced = SLICED_CHART_TYPES.includes(chart.type);
        const seriesColors = isSliced
            ? null
            : this.getSeriesColors(chart.datasets.length);
        const datasets = chart.datasets.map((dataset, index) => {
            if (isSliced) {
                const colors = this.getSeriesColors(dataset.data.length);
                return {...dataset, ...datasetOptions, backgroundColor: colors};
            }
            const color = seriesColors[index];
            return {
                ...dataset,
                ...datasetOptions,
                backgroundColor: color,
                borderColor: color,
            };
        });
        this.chart = new Chart(this.canvasRef.el, {
            type: chartJsType,
            data: {labels: chart.labels, datasets},
            options: {
                responsive: true,
                maintainAspectRatio: false,
                ...chartOptions,
                plugins: {legend: {display: chart.show_legend}},
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
