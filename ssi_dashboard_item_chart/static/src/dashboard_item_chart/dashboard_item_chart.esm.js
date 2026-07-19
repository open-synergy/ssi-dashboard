import {Component, onMounted, onWillStart, onWillUnmount, useRef} from "@odoo/owl";
import {loadBundle} from "@web/core/assets";
import {registry} from "@web/core/registry";

/* global Chart, ChartDataLabels */

const SLICED_CHART_TYPES = ["pie", "doughnut", "polar"];
const SEMI_CIRCLE_CHART_TYPES = ["pie", "doughnut"];

/**
 * Renders a "chart" dashboard item — one of seven chart kinds, built with
 * Odoo's bundled Chart.js ("web.chartjs_lib"). Registered under
 * registry.category("ssi_dashboard.item_widgets") for the "dashboard.item"
 * type "chart" (see ssi_dashboard_item_chart/models/dashboard_item.py,
 * _prepare_render_payload_chart()).
 *
 * The "item" prop is one entry of "items" from
 * dashboard.dashboard.get_dashboard_payload(), enriched with a "chart" key
 * by _prepare_render_payload_chart() — {type, labels, datasets, show_legend,
 * stacked, semi_circle, cumulative, data_label}. "datasets" already carries
 * one entry per second dimension value or per measure, plus one extra
 * cumulative entry (tagged {render_as: "line"}) when "cumulative" is set —
 * all built server-side; this component only maps "type"/"stacked"/
 * "semi_circle" to Chart.js type/options, draws the "render_as: line"
 * dataset as a line regardless of the overall chart type (Chart.js mixed
 * chart), draws data labels when "data_label" isn't "none", and assigns
 * series colors — no aggregation happens here.
 *
 * Series colors are read from the dashboard's own
 * "--ssi-dashboard-chart-<n>" CSS custom properties (set by DashboardAction
 * from dashboard.color_scheme) at mount time — this component carries no
 * palette of its own; an index without a matching property falls back to
 * Chart.js' own default color rotation.
 *
 * Data labels are drawn with the "chartjs-plugin-datalabels" plugin when
 * it is already registered globally as part of the "web.chartjs_lib"
 * bundle; otherwise a small inline Chart.js plugin — defined in this file,
 * not vendored — draws them instead. No extra JS library is added to this
 * module either way.
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
     * Builds the `scales` option that stacks every dataset on top of each
     * other, used by "bar"/"horizontal_bar"/"area" when `stacked` is set
     * (see ssi_dashboard_item_chart/models/dashboard_item.py,
     * `chart_stacked`). Chart.js keeps the scale ids "x"/"y" regardless of
     * `indexAxis`, so the same keys apply to "horizontal_bar" too.
     *
     * @param {Boolean} stacked
     * @returns {Object} `{}` when `stacked` is falsy, otherwise
     *     `{scales: {x: {stacked: true}, y: {stacked: true}}}`.
     */
    getStackedScaleOptions(stacked) {
        if (!stacked) {
            return {};
        }
        return {scales: {x: {stacked: true}, y: {stacked: true}}};
    }

    /**
     * Maps this item's server-side "chart" object (all seven
     * `chart.type` kinds from ssi_dashboard_item_chart/models/dashboard_item.py,
     * plus `chart.stacked`/`chart.semi_circle`) to the Chart.js chart
     * "type" plus any extra chart/dataset options that mapping needs.
     * "horizontal_bar" is a Chart.js "bar" chart with `indexAxis: "y"`.
     * "area" is a Chart.js "line" chart with `fill: true` on every
     * dataset. "polar" is Chart.js' "polarArea" (its exact spelling). A
     * "pie"/"doughnut" chart with `semi_circle` set is drawn as a half
     * circle via `circumference: 180, rotation: -90` — Chart.js' own
     * recipe for that shape. Every other value ("line", "pie",
     * "doughnut" without `semi_circle`) is already a valid Chart.js type
     * and needs no mapping.
     *
     * @param {Object} chart this.props.item.chart
     * @returns {Object} {chartJsType, chartOptions, datasetOptions}
     */
    mapChartType(chart) {
        const {type: chartType, stacked, semi_circle: semiCircle} = chart;
        if (chartType === "horizontal_bar") {
            return {
                chartJsType: "bar",
                chartOptions: {
                    indexAxis: "y",
                    ...this.getStackedScaleOptions(stacked),
                },
                datasetOptions: {},
            };
        }
        if (chartType === "area") {
            return {
                chartJsType: "line",
                chartOptions: this.getStackedScaleOptions(stacked),
                datasetOptions: {fill: true},
            };
        }
        if (chartType === "bar") {
            return {
                chartJsType: "bar",
                chartOptions: this.getStackedScaleOptions(stacked),
                datasetOptions: {},
            };
        }
        if (chartType === "polar") {
            return {chartJsType: "polarArea", chartOptions: {}, datasetOptions: {}};
        }
        if (semiCircle && SEMI_CIRCLE_CHART_TYPES.includes(chartType)) {
            return {
                chartJsType: chartType,
                chartOptions: {circumference: 180, rotation: -90},
                datasetOptions: {},
            };
        }
        return {chartJsType: chartType, chartOptions: {}, datasetOptions: {}};
    }

    /**
     * Formats one data point's on-chart label according to
     * `chart.data_label` (see
     * ssi_dashboard_item_chart/models/dashboard_item.py, `chart_data_label`).
     * "percent" divides `value` by its own `dataset`'s total — the same
     * rule regardless of which plugin ends up drawing the text (official
     * or inline, see `getDataLabelPlugin`).
     *
     * @param {Number} value
     * @param {Object} dataset the Chart.js dataset `value` belongs to
     * @param {String} dataLabel chart.data_label ("value" or "percent" —
     *     never called with "none")
     * @returns {String} empty string for a missing `value`.
     */
    formatDataLabel(value, dataset, dataLabel) {
        if (value === undefined || value === null) {
            return "";
        }
        if (dataLabel !== "percent") {
            return `${value}`;
        }
        const total = (dataset.data || []).reduce(
            (sum, point) => sum + (point || 0),
            0
        );
        return total ? `${((value / total) * 100).toFixed(1)}%` : "0%";
    }

    /**
     * Builds a small self-contained Chart.js plugin drawing each data
     * point's formatted label centered above it, used as the fallback by
     * `getDataLabelPlugin` when "chartjs-plugin-datalabels" isn't
     * registered globally. Not a vendored library — a plain Chart.js
     * plugin object local to this component.
     *
     * @param {String} dataLabel chart.data_label ("value" or "percent")
     * @returns {Object} a Chart.js plugin ({id, afterDatasetsDraw}).
     */
    buildInlineDataLabelPlugin(dataLabel) {
        const formatDataLabel = (value, dataset) =>
            this.formatDataLabel(value, dataset, dataLabel);
        return {
            id: "ssiDashboardItemChartDataLabel",
            afterDatasetsDraw(chartInstance) {
                const {ctx} = chartInstance;
                chartInstance.data.datasets.forEach((dataset, datasetIndex) => {
                    const meta = chartInstance.getDatasetMeta(datasetIndex);
                    if (meta.hidden) {
                        return;
                    }
                    meta.data.forEach((element, index) => {
                        const text = formatDataLabel(dataset.data[index], dataset);
                        if (!text) {
                            return;
                        }
                        const position = element.tooltipPosition
                            ? element.tooltipPosition()
                            : element.getCenterPoint();
                        ctx.save();
                        ctx.fillStyle =
                            getComputedStyle(chartInstance.canvas).color || "#000";
                        ctx.textAlign = "center";
                        ctx.textBaseline = "bottom";
                        ctx.fillText(text, position.x, position.y - 4);
                        ctx.restore();
                    });
                });
            },
        };
    }

    /**
     * Picks which Chart.js plugin draws data labels for `dataLabel`
     * (chart.data_label): "chartjs-plugin-datalabels" when it is already
     * registered globally as part of the "web.chartjs_lib" bundle,
     * otherwise the inline fallback from `buildInlineDataLabelPlugin`.
     *
     * @param {String} dataLabel chart.data_label
     * @returns {Object|null} `null` when `dataLabel` is "none".
     */
    getDataLabelPlugin(dataLabel) {
        if (dataLabel === "none") {
            return null;
        }
        if (typeof ChartDataLabels !== "undefined") {
            return ChartDataLabels;
        }
        return this.buildInlineDataLabelPlugin(dataLabel);
    }

    renderChart() {
        const {chart} = this.props.item;
        const {chartJsType, chartOptions, datasetOptions} = this.mapChartType(chart);
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
            const typeOptions =
                dataset.render_as === "line"
                    ? {type: "line", fill: false}
                    : datasetOptions;
            return {
                ...dataset,
                ...typeOptions,
                backgroundColor: color,
                borderColor: color,
            };
        });
        const dataLabelPlugin = this.getDataLabelPlugin(chart.data_label);
        const usingOfficialDataLabelPlugin =
            Boolean(dataLabelPlugin) && typeof ChartDataLabels !== "undefined";
        this.chart = new Chart(this.canvasRef.el, {
            type: chartJsType,
            data: {labels: chart.labels, datasets},
            plugins: dataLabelPlugin ? [dataLabelPlugin] : [],
            options: {
                responsive: true,
                maintainAspectRatio: false,
                ...chartOptions,
                plugins: {
                    legend: {display: chart.show_legend},
                    ...(usingOfficialDataLabelPlugin
                        ? {
                              datalabels: {
                                  formatter: (value, context) =>
                                      this.formatDataLabel(
                                          value,
                                          context.dataset,
                                          chart.data_label
                                      ),
                              },
                          }
                        : {}),
                },
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
