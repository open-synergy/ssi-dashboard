# Copyright 2026 OpenSynergy Indonesia
# Copyright 2026 PT. Simetri Sinergi Indonesia
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
import datetime

from odoo import api, fields, models
from odoo.exceptions import ValidationError

_MIN_PAGE_SIZE = 1
_MAX_PAGE_SIZE = 200


class DashboardItem(models.Model):
    """Extends `dashboard.item` with the 'list' type: a table of the
    item's fetched data. Columns are configured through real fields
    (:attr:`column_ids`, model `dashboard.item.column`) instead of the
    'columns' key of the item's `config` JSON field — that field, and
    the 'limit' key that used to cap row count alongside it, are no
    longer read anywhere in this module. Row count is still bounded, but
    by `dashboard.data_source.limit` upstream; :attr:`page_size` only
    tells the browser how many already-fetched rows to show per page."""

    _name = "dashboard.item"
    _inherit = [
        "dashboard.item",
    ]

    type = fields.Selection(
        selection_add=[
            ("list", "List"),
        ],
        ondelete={"list": "set default"},
    )
    column_ids = fields.One2many(
        string="Columns",
        comodel_name="dashboard.item.column",
        inverse_name="item_id",
        help="Columns rendered by the table, in 'Sequence' order. Only "
        "used, and required, when 'Type' is 'List'.",
    )
    list_mode = fields.Selection(
        selection=[
            ("flat", "Flat"),
            ("grouped", "Grouped"),
        ],
        required=True,
        default="flat",
        help="How the table's rows are arranged. Only used when 'Type' "
        "is 'List'. 'Grouped' arranges rows under their 'Data Source''s "
        "'Group By Field' value, with a subtotal row per group, and "
        "requires 'Group By Field' to be set on 'Data Source'.",
    )
    page_size = fields.Integer(
        default=10,
        help="Number of rows shown at once in the browser before "
        "pagination hides the rest. Applied client-side, over rows "
        "already sent to the browser — it does not change how many rows "
        "'Data Source' fetches from the database ('Limit' on 'Data "
        "Source' still governs that). Must be between "
        f"{_MIN_PAGE_SIZE} and {_MAX_PAGE_SIZE}.",
    )

    @api.constrains("type", "column_ids")
    def _check_list_requires_column_ids(self):
        for item in self:
            if item.type == "list" and not item.column_ids:
                error_message = f"""
Context: Configure dashboard item list
Database ID: {item.id}
Problem: 'Type' is set to 'List' but 'Columns' has no rows
Solution: Add at least one row to 'Columns'
"""
                raise ValidationError(error_message)

    @api.constrains("type", "list_mode", "data_source_id")
    def _check_list_mode_grouped_requires_group_by(self):
        for item in self:
            if item.type != "list" or item.list_mode != "grouped":
                continue
            if not item.data_source_id.group_by_field_id:
                error_message = f"""
Context: Configure dashboard item list
Database ID: {item.id}
Problem: 'List Mode' is set to 'Grouped' but 'Data Source' \
('{item.data_source_id.name}') has no 'Group By Field'
Solution: Set 'Group By Field' on 'Data Source' \
('{item.data_source_id.name}'), or change 'List Mode' to 'Flat'
"""
                raise ValidationError(error_message)

    @api.constrains("goal_type")
    def _check_deviation_column_requires_goal(self):
        """Reject 'Goal Type' being set to 'No Target' while this item
        already has one or more 'Deviation From Target' columns.

        Only triggered on 'goal_type' (this model's own field) — the
        symmetric case (a 'Deviation From Target' column being added on
        an item that already has no target) is covered by
        :meth:`dashboard.item.column._check_column_type_deviation_requires_goal`
        instead, since that only requires a same-model trigger there
        too ('column_type'/'item_id'), unlike triggering this method on
        'column_ids' itself — which does not fire when a
        'dashboard.item.column' row is created directly against
        'item_id' rather than through this item's own 'Columns' nested
        one2many.
        """
        for item in self:
            deviation_columns = item.column_ids.filtered(
                lambda column: column.column_type == "deviation"
            )
            if deviation_columns and item.goal_type == "none":
                error_message = f"""
Context: Configure dashboard item list column
Database ID: {item.id}
Problem: 'Columns' has one or more 'Deviation From Target' columns \
({", ".join(deviation_columns.mapped("name"))}) but 'Goal Type' is 'No \
Target'
Solution: Set 'Goal Type' to 'Fixed Value' or 'Dated Targets', or change \
those columns' 'Column Type' to something other than 'Deviation From \
Target'
"""
                raise ValidationError(error_message)

    @api.constrains("page_size")
    def _check_page_size_range(self):
        for item in self:
            if not _MIN_PAGE_SIZE <= item.page_size <= _MAX_PAGE_SIZE:
                error_message = f"""
Context: Configure dashboard item list
Database ID: {item.id}
Problem: 'Page Size' is set to {item.page_size}, which is outside the \
allowed range of {_MIN_PAGE_SIZE} to {_MAX_PAGE_SIZE}
Solution: Set 'Page Size' to a value between {_MIN_PAGE_SIZE} and \
{_MAX_PAGE_SIZE}
"""
                raise ValidationError(error_message)

    def _prepare_render_payload_list(self, payload):
        """Enrich the render payload of a 'list' item.

        :param payload: dict built by
            :meth:`dashboard.item._prepare_render_payload`.
        :return: `payload`, with 'columns' (list of dict built from
            :attr:`column_ids`, see :meth:`_get_list_columns`), 'rows'
            (list of dict, see :meth:`_compute_list_rows`), 'list_mode'
            (:attr:`list_mode`), 'page_size' (:attr:`page_size`) and,
            only when :attr:`list_mode` is 'grouped', 'groups' (see
            :meth:`_compute_list_groups`) added.
        :rtype: dict
        """
        self.ensure_one()
        columns = self._get_list_columns()
        data = payload.get("data") or []
        rows = self._compute_list_rows(data, columns)
        payload["columns"] = columns
        payload["list_mode"] = self.list_mode
        payload["page_size"] = self.page_size
        payload["rows"] = rows
        if self.list_mode == "grouped":
            payload["groups"] = self._compute_list_groups(rows, columns)
        return payload

    def _get_list_columns(self):
        """Build the 'columns' key of the render payload out of
        :attr:`column_ids`.

        :return: list of dict with keys 'key', 'name' and 'column_type',
            one per row of :attr:`column_ids`, in 'Sequence' order.
        :rtype: list
        """
        self.ensure_one()
        return [
            {
                "key": column.key,
                "name": column.name,
                "column_type": column.column_type,
            }
            for column in self.column_ids.sorted("sequence")
        ]

    def _compute_list_rows(self, data, columns):
        """Build the 'rows' key of the render payload out of fetched
        `data`.

        A row missing a column's 'key' contributes ``None`` for that
        key, so the browser renders an empty cell instead of erroring,
        since non-ORM sources (API, ODBC) do not guarantee a uniform row
        shape. When a source row carries a 'group_label' (added by
        `dashboard.data_source._fetch_data_orm` when its 'Group By
        Field' is set), it is copied onto the built row unchanged, so
        :meth:`_compute_list_groups` and the browser's 'Grouped'
        rendering can key off it.

        :param data: list of dict, the item's fetched data
            (``payload["data"]``).
        :param columns: list of dict with keys 'key', 'name' and
            'column_type', as returned by :meth:`_get_list_columns`.
        :return: list of dict, one per entry of `data`, each keyed like
            `columns` (plus 'group_label' when present on the source
            row).
        :rtype: list
        """
        self.ensure_one()
        rows = []
        for source_row in data:
            row = {}
            for column in columns:
                if column["column_type"] == "deviation":
                    row[column["key"]] = self._get_list_deviation_value(
                        source_row, column["key"]
                    )
                else:
                    row[column["key"]] = source_row.get(column["key"])
            if "group_label" in source_row:
                row["group_label"] = source_row["group_label"]
            rows.append(row)
        return rows

    def _get_list_deviation_value(self, source_row, key):
        """Compute one 'Deviation From Target' column's value for a
        single source row.

        :param source_row: dict, one entry of the item's fetched data.
        :param key: str, the column's 'Key'.
        :return: `source_row[key]` (``0`` when absent/falsy) minus this
            item's target for the row's date, see
            :meth:`_get_list_row_target_date` and
            :meth:`dashboard.item._get_goal_value`.
        :rtype: float
        """
        self.ensure_one()
        value = source_row.get(key) or 0.0
        target_date = self._get_list_row_target_date(source_row)
        return value - self._get_goal_value(target_date)

    def _get_list_row_target_date(self, source_row):
        """Pick the date a source row's target is looked up for.

        :param source_row: dict, one entry of the item's fetched data —
            carries a 'group_key' (raw, pre-label, groupby value) when
            `dashboard.data_source.group_by_field_id` is a date/datetime
            field.
        :return: `source_row['group_key']` as a ``date`` when it is a
            ``date``/``datetime``; otherwise today's date (in the
            current user's context), so a list without a date-based
            'Group By Field' still gets a sensible target.
        :rtype: datetime.date
        """
        self.ensure_one()
        group_key = source_row.get("group_key")
        if isinstance(group_key, datetime.datetime):
            return group_key.date()
        if isinstance(group_key, datetime.date):
            return group_key
        return fields.Date.context_today(self)

    def _compute_list_groups(self, rows, columns):
        """Build the 'groups' key of the render payload, used by the
        browser's 'Grouped' rendering to show a subtotal row per group.

        :param rows: list of dict, as returned by
            :meth:`_compute_list_rows` — each carrying a 'group_label'
            key, guaranteed by
            :meth:`_check_list_mode_grouped_requires_group_by` requiring
            `dashboard.data_source.group_by_field_id` to be set whenever
            :attr:`list_mode` is 'grouped'.
        :param columns: list of dict, as returned by
            :meth:`_get_list_columns`.
        :return: list of dict with keys 'label' (a 'group_label' value),
            'rows' (the subset of `rows` sharing that label) and
            'subtotals' (dict keyed by every 'number'/'deviation'
            column's 'key', summing that column's value over the
            group's rows), one per unique 'group_label', in first-seen
            order.
        :rtype: list
        """
        self.ensure_one()
        numeric_keys = [
            column["key"]
            for column in columns
            if column["column_type"] in ("number", "deviation")
        ]
        groups = []
        index_by_label = {}
        for row in rows:
            label = row.get("group_label")
            if label not in index_by_label:
                index_by_label[label] = len(groups)
                groups.append(
                    {
                        "label": label,
                        "rows": [],
                        "subtotals": dict.fromkeys(numeric_keys, 0),
                    }
                )
            group = groups[index_by_label[label]]
            group["rows"].append(row)
            for key in numeric_keys:
                group["subtotals"][key] += row.get(key) or 0
        return groups
