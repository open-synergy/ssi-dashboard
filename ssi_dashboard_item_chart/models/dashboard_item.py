# Copyright 2026 OpenSynergy Indonesia
# Copyright 2026 PT. Simetri Sinergi Indonesia
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from odoo import api, fields, models
from odoo.exceptions import ValidationError

_CHART_TYPE_SELECTION = [
    ("bar", "Bar"),
    ("horizontal_bar", "Horizontal Bar"),
    ("line", "Line"),
    ("area", "Area"),
    ("pie", "Pie"),
    ("doughnut", "Doughnut"),
    ("polar", "Polar Area"),
]

_CHART_DATA_LABEL_SELECTION = [
    ("none", "Hidden"),
    ("value", "Value"),
    ("percent", "Percentage"),
]

# `chart_type` values that support `chart_stacked`.
_CHART_STACKED_TYPES = ("bar", "horizontal_bar", "area")

# `chart_type` values that support `chart_semi_circle`.
_CHART_SEMI_CIRCLE_TYPES = ("pie", "doughnut")

# `chart_type` values that reject `chart_cumulative` — a running total is
# meaningless on a proportion chart.
_CHART_CUMULATIVE_EXCLUDED_TYPES = ("pie", "doughnut", "polar")


class DashboardItem(models.Model):
    """Extends `dashboard.item` with the 'chart' type: a chart built out of
    the real, structured fields already added to `dashboard.data_source`
    (`group_by_field_id`, `sub_group_by_field_id`, `measure_field_id` /
    `measure_ids`, `_prepare_groupby_spec`, `_prepare_aggregate_spec`) — no
    `config` JSON is read here. Supports seven chart kinds
    (:attr:`chart_type`) and assembles either one dataset per second
    dimension value (:attr:`dashboard.data_source.sub_group_by_field_id`)
    or one dataset per configured measure, never both at once (see
    :meth:`_check_chart_multi_measure_requires_no_sub_group`). Also adds
    composition/readability options on top of the seven chart kinds:
    stacking datasets (:attr:`chart_stacked`), drawing pie/doughnut as a
    half circle (:attr:`chart_semi_circle`), an extra running-total
    dataset drawn as a line (:attr:`chart_cumulative`), and on-chart data
    labels (:attr:`chart_data_label`)."""

    _name = "dashboard.item"
    _inherit = [
        "dashboard.item",
    ]

    type = fields.Selection(
        selection_add=[
            ("chart", "Chart"),
        ],
        ondelete={"chart": "set default"},
    )
    chart_type = fields.Selection(
        selection=_CHART_TYPE_SELECTION,
        default="bar",
        required=True,
        help="Kind of chart rendered by the browser. Only used when 'Type' "
        "is 'Chart'. 'Horizontal Bar' and 'Area' are rendered as Chart.js "
        "'bar'/'line' charts with a client-side option added (horizontal "
        "index axis / area fill) — the server sends this value unchanged, "
        "the mapping happens in the browser.",
    )
    chart_show_legend = fields.Boolean(
        default=True,
        help="Show the chart's legend. Only used when 'Type' is 'Chart'.",
    )
    chart_stacked = fields.Boolean(
        default=False,
        help="Stack this chart's datasets on top of each other instead of "
        "side by side. Only used when 'Type' is 'Chart' and only "
        "supported when 'Chart Type' is 'Bar', 'Horizontal Bar' or "
        "'Area'.",
    )
    chart_semi_circle = fields.Boolean(
        default=False,
        help="Draw this chart as a half circle instead of a full circle. "
        "Only used when 'Type' is 'Chart' and only supported when 'Chart "
        "Type' is 'Pie' or 'Doughnut'.",
    )
    chart_cumulative = fields.Boolean(
        default=False,
        help="Add one extra dataset with the running cumulative total of "
        "this chart's first dataset, always drawn as a line regardless "
        "of 'Chart Type'. Only used when 'Type' is 'Chart' and not "
        "available when 'Chart Type' is 'Pie', 'Doughnut' or 'Polar "
        "Area'.",
    )
    chart_data_label = fields.Selection(
        selection=_CHART_DATA_LABEL_SELECTION,
        default="none",
        required=True,
        help="Show each data point's value directly on the chart. "
        "'Percentage' shows each point's share of its own dataset's "
        "total instead of its raw value. Only used when 'Type' is "
        "'Chart'.",
    )

    @api.onchange("chart_type")
    def _onchange_chart_type(self):
        """Reset :attr:`chart_stacked`/:attr:`chart_semi_circle` when the
        newly chosen :attr:`chart_type` no longer supports them — mirrors
        :meth:`_check_chart_stacked_requires_supported_type` and
        :meth:`_check_chart_semi_circle_requires_supported_type` so the
        form never gets stuck offering a combination the constraint would
        reject on save."""
        for item in self:
            if item.chart_type not in _CHART_STACKED_TYPES:
                item.chart_stacked = False
            if item.chart_type not in _CHART_SEMI_CIRCLE_TYPES:
                item.chart_semi_circle = False

    @api.constrains("type", "chart_type", "chart_stacked")
    def _check_chart_stacked_requires_supported_type(self):
        for item in self:
            if item.type != "chart" or not item.chart_stacked:
                continue
            if item.chart_type not in _CHART_STACKED_TYPES:
                error_message = f"""
Context: Configure dashboard item chart
Database ID: {item.id}
Problem: 'Stacked' is enabled but 'Chart Type' ('{item.chart_type}') does \
not support it
Solution: Disable 'Stacked', or set 'Chart Type' to 'Bar', 'Horizontal \
Bar' or 'Area'
"""
                raise ValidationError(error_message)

    @api.constrains("type", "chart_type", "chart_semi_circle")
    def _check_chart_semi_circle_requires_supported_type(self):
        for item in self:
            if item.type != "chart" or not item.chart_semi_circle:
                continue
            if item.chart_type not in _CHART_SEMI_CIRCLE_TYPES:
                error_message = f"""
Context: Configure dashboard item chart
Database ID: {item.id}
Problem: 'Semi Circle' is enabled but 'Chart Type' ('{item.chart_type}') \
does not support it
Solution: Disable 'Semi Circle', or set 'Chart Type' to 'Pie' or \
'Doughnut'
"""
                raise ValidationError(error_message)

    @api.constrains("type", "chart_type", "chart_cumulative")
    def _check_chart_cumulative_requires_supported_type(self):
        for item in self:
            if item.type != "chart" or not item.chart_cumulative:
                continue
            if item.chart_type in _CHART_CUMULATIVE_EXCLUDED_TYPES:
                error_message = f"""
Context: Configure dashboard item chart
Database ID: {item.id}
Problem: 'Cumulative' is enabled but 'Chart Type' ('{item.chart_type}') \
does not support it
Solution: Disable 'Cumulative', or choose a 'Chart Type' other than \
'Pie', 'Doughnut' or 'Polar Area'
"""
                raise ValidationError(error_message)

    @api.constrains("type", "data_source_id")
    def _check_chart_requires_group_by_field(self):
        for item in self:
            if item.type != "chart":
                continue
            if not item.data_source_id.group_by_field_id:
                error_message = f"""
Context: Configure dashboard item chart
Database ID: {item.id}
Problem: 'Type' is set to 'Chart' but 'Data Source' \
('{item.data_source_id.name}') has no 'Group By Field'
Solution: Set 'Group By Field' on 'Data Source' ('{item.data_source_id.name}'), \
or choose a different 'Type'
"""
                raise ValidationError(error_message)

    @api.constrains("type", "data_source_id")
    def _check_chart_multi_measure_requires_no_sub_group(self):
        for item in self:
            if item.type != "chart":
                continue
            data_source = item.data_source_id
            if data_source.sub_group_by_field_id and len(data_source.measure_ids) > 1:
                error_message = f"""
Context: Configure dashboard item chart
Database ID: {item.id}
Problem: 'Data Source' ('{data_source.name}') has both more than one row in \
'Measures' and 'Sub Group By Field' set, which produces an ambiguous set of \
chart datasets
Solution: Reduce 'Measures' on 'Data Source' ('{data_source.name}') to at \
most one row, or clear its 'Sub Group By Field'
"""
                raise ValidationError(error_message)

    def _prepare_render_payload_chart(self, payload):
        """Enrich the render payload of a 'chart' item.

        :param payload: dict built by
            :meth:`dashboard.item._prepare_render_payload`.
        :return: `payload`, with a 'chart' key added — dict with 'type'
            (:attr:`chart_type`), 'labels' (see
            :meth:`_get_chart_labels`), 'datasets' (see
            :meth:`_get_chart_datasets`, with one extra entry appended by
            :meth:`_add_chart_cumulative_dataset` when
            :attr:`chart_cumulative` is set), 'show_legend'
            (:attr:`chart_show_legend`), 'stacked' (:attr:`chart_stacked`),
            'semi_circle' (:attr:`chart_semi_circle`), 'cumulative'
            (:attr:`chart_cumulative`) and 'data_label'
            (:attr:`chart_data_label`).
        :rtype: dict
        """
        self.ensure_one()
        data = payload.get("data") or []
        labels = self._get_chart_labels(data)
        datasets = self._get_chart_datasets(data, labels)
        if self.chart_cumulative:
            datasets = self._add_chart_cumulative_dataset(datasets)
        payload["chart"] = {
            "type": self.chart_type,
            "labels": labels,
            "datasets": datasets,
            "show_legend": self.chart_show_legend,
            "stacked": self.chart_stacked,
            "semi_circle": self.chart_semi_circle,
            "cumulative": self.chart_cumulative,
            "data_label": self.chart_data_label,
        }
        return payload

    def _add_chart_cumulative_dataset(self, datasets):
        """Append one extra dataset holding the running cumulative total
        of `datasets`' first entry, used by
        :meth:`_prepare_render_payload_chart` when :attr:`chart_cumulative`
        is set.

        The extra dataset is tagged with a ``render_as`` key set to
        ``"line"`` so every consumer of this payload — the OWL chart
        component as well as any future export — draws it as a line even
        when the chart itself is a bar chart, following the same
        accumulation rule everywhere.

        :param datasets: list of dict, from :meth:`_get_chart_datasets` —
            not modified in place.
        :return: `datasets` plus one extra dict with keys 'label', 'data'
            (running total of `datasets[0]['data']`, same length) and
            'render_as' (``"line"``). Returned unchanged if `datasets` is
            empty.
        :rtype: list
        """
        self.ensure_one()
        if not datasets:
            return datasets
        first_dataset = datasets[0]
        running_total = 0
        cumulative_data = []
        for value in first_dataset["data"]:
            running_total += value or 0
            cumulative_data.append(running_total)
        cumulative_dataset = {
            "label": f"{first_dataset['label']} (Cumulative)",
            "data": cumulative_data,
            "render_as": "line",
        }
        return datasets + [cumulative_dataset]

    def _get_chart_labels(self, data):
        """Build the chart's x-axis labels out of fetched `data`.

        :param data: list of dict, the item's fetched data
            (``payload["data"]``) — each row carries a 'group_label' key,
            guaranteed by :meth:`_check_chart_requires_group_by_field`
            requiring :attr:`dashboard.data_source.group_by_field_id` to
            be set for any 'chart' item.
        :return: list of str, one per unique 'group_label' value, in
            first-seen order.
        :rtype: list
        """
        labels = []
        seen = set()
        for row in data:
            label = row.get("group_label")
            if label not in seen:
                seen.add(label)
                labels.append(label)
        return labels

    def _get_chart_measure_specs(self):
        """Build the ``(row_key, dataset_label)`` pairs this item's
        datasets are read from, one per configured measure of
        :attr:`dashboard.item.data_source_id`.

        Delegates to
        :meth:`dashboard.data_source._prepare_aggregate_spec` so this
        method never needs to know whether :attr:`measure_ids` or the
        single :attr:`measure_field_id` / :attr:`aggregate` pair is in
        effect.

        :return: list of 2-tuple ``(row_key, label)``. When the data
            source has at least one row in :attr:`measure_ids`, one pair
            per row — both `row_key` and `label` are that measure's
            'Name' (fetched rows already carry that same key, see
            :meth:`dashboard.data_source._fetch_data_orm`). Otherwise a
            single pair whose `row_key` is the internal aggregate spec
            (e.g. ``"__count"``) and whose `label` is this item's own
            :attr:`name`, so a data source without any :attr:`measure_ids`
            row still gets a sensible dataset label.
        :rtype: list
        """
        self.ensure_one()
        data_source = self.data_source_id
        _aggregates, column_names = data_source._prepare_aggregate_spec()
        if data_source.measure_ids:
            return [(name, name) for name in column_names.values()]
        (row_key,) = column_names.values()
        return [(row_key, self.name)]

    def _get_chart_datasets(self, data, labels):
        """Build the chart's datasets out of fetched `data`.

        :param data: list of dict, the item's fetched data
            (``payload["data"]``).
        :param labels: list of str, from :meth:`_get_chart_labels` — every
            dataset's 'data' is aligned to this list, one value per
            label, in the same order.
        :return: list of dict with keys 'label' (str) and 'data' (list of
            number, same length as `labels`). One dataset per unique
            'sub_group_label' when :attr:`dashboard.data_source.sub_group_by_field_id`
            is set on this item's data source (see
            :meth:`_get_chart_datasets_by_sub_group`); otherwise one
            dataset per configured measure (see
            :meth:`_get_chart_datasets_by_measure`). A label/measure (or
            label/sub-group) combination absent from `data` contributes
            ``0``, never a missing entry.
        :rtype: list
        """
        self.ensure_one()
        if self.data_source_id.sub_group_by_field_id:
            return self._get_chart_datasets_by_sub_group(data, labels)
        return self._get_chart_datasets_by_measure(data, labels)

    def _get_chart_datasets_by_sub_group(self, data, labels):
        """Build one dataset per unique 'sub_group_label', used by
        :meth:`_get_chart_datasets` when this item's data source has
        :attr:`dashboard.data_source.sub_group_by_field_id` set. Only
        ever called with exactly one configured measure — combining
        several measures with a second dimension is rejected by
        :meth:`_check_chart_multi_measure_requires_no_sub_group`.

        :param data: list of dict, the item's fetched data.
        :param labels: list of str, from :meth:`_get_chart_labels`.
        :return: list of dict with keys 'label' (a 'sub_group_label'
            value) and 'data' (list of number, aligned to `labels`, ``0``
            for a label/sub-group combination absent from `data`), one
            per unique 'sub_group_label', in first-seen order.
        :rtype: list
        """
        self.ensure_one()
        row_key, _default_label = self._get_chart_measure_specs()[0]
        sub_group_labels = []
        seen = set()
        values_by_sub_group_and_label = {}
        for row in data:
            sub_group_label = row.get("sub_group_label")
            if sub_group_label not in seen:
                seen.add(sub_group_label)
                sub_group_labels.append(sub_group_label)
            key = (sub_group_label, row.get("group_label"))
            values_by_sub_group_and_label[key] = row.get(row_key) or 0
        return [
            {
                "label": sub_group_label,
                "data": [
                    values_by_sub_group_and_label.get((sub_group_label, label), 0)
                    for label in labels
                ],
            }
            for sub_group_label in sub_group_labels
        ]

    def _get_chart_datasets_by_measure(self, data, labels):
        """Build one dataset per configured measure, used by
        :meth:`_get_chart_datasets` when this item's data source has no
        :attr:`dashboard.data_source.sub_group_by_field_id` set.

        :param data: list of dict, the item's fetched data — at most one
            row per 'group_label' in this branch (no second dimension).
        :param labels: list of str, from :meth:`_get_chart_labels`.
        :return: list of dict with keys 'label' and 'data' (list of
            number, aligned to `labels`, ``0`` for a label absent from
            `data`), one per pair returned by
            :meth:`_get_chart_measure_specs`, in that order.
        :rtype: list
        """
        self.ensure_one()
        rows_by_label = {row.get("group_label"): row for row in data}
        return [
            {
                "label": measure_label,
                "data": [
                    (rows_by_label.get(label) or {}).get(row_key) or 0
                    for label in labels
                ],
            }
            for row_key, measure_label in self._get_chart_measure_specs()
        ]
