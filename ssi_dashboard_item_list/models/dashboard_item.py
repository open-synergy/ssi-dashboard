# Copyright 2026 OpenSynergy Indonesia
# Copyright 2026 PT. Simetri Sinergi Indonesia
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
import json

from odoo import fields, models
from odoo.exceptions import UserError

_DEFAULT_LIMIT = 10
_MIN_LIMIT = 1
_MAX_LIMIT = 100


class DashboardItem(models.Model):
    """Extends `dashboard.item` with the 'list' type: a table of the
    item's fetched data, rendered with the columns named by 'columns' in
    the item's existing `config` JSON field, and capped at 'limit' rows.
    Adds no field of its own to :attr:`type` beyond the selection value."""

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

    def _prepare_render_payload_list(self, payload):
        """Enrich the render payload of a 'list' item.

        Reads 'columns' (required, list of dict — see
        :meth:`_get_list_columns`) and 'limit' (optional Integer, 1-100,
        defaulting to 10) out of :attr:`config` (JSON), then caps the
        item's fetched data at 'limit' rows **before** building the row
        payload — the browser never receives more than 'limit' rows.

        :param payload: dict built by
            :meth:`dashboard.item._prepare_render_payload`.
        :return: `payload`, with 'columns' (list of dict with keys 'key'
            and 'label') and 'rows' (list of dict, at most 'limit' long,
            each keyed like 'columns') added.
        :rtype: dict
        :raises UserError: when :attr:`config` is missing, is not valid
            JSON, is valid JSON that is not an object, names no 'columns'
            or an empty/non-list 'columns', a 'columns' entry without a
            'key', or a 'limit' outside 1-100.
        """
        self.ensure_one()
        config = self._parse_list_config_json()
        columns = self._get_list_columns(config)
        limit = self._get_list_limit(config)
        data = payload.get("data") or []
        payload["columns"] = columns
        payload["rows"] = self._compute_list_rows(data, columns, limit)
        return payload

    def _parse_list_config_json(self):
        """Parse this item's :attr:`config` as a JSON object.

        :return: the parsed JSON object.
        :rtype: dict
        :raises UserError: when :attr:`config` is empty, is not valid
            JSON, or is valid JSON that is not an object.
        """
        self.ensure_one()
        if not self.config:
            error_message = f"""
Context: Render dashboard item 'list' payload
Database ID: {self.id}
Problem: 'Config' is empty, but the 'list' item type requires 'columns'
Solution: Set 'Config' to a JSON object, e.g. \
{{"columns": [{{"key": "name"}}, {{"key": "amount", "label": "Amount"}}]}}
"""
            raise UserError(error_message)
        try:
            config = json.loads(self.config)
        except ValueError as parse_error:
            error_message = f"""
Context: Render dashboard item 'list' payload
Database ID: {self.id}
Problem: 'Config' is not valid JSON ({parse_error})
Solution: Fix the JSON syntax in the 'Config' field, e.g. \
{{"columns": [{{"key": "name"}}, {{"key": "amount", "label": "Amount"}}]}}
"""
            raise UserError(error_message) from parse_error
        if not isinstance(config, dict):
            error_message = f"""
Context: Render dashboard item 'list' payload
Database ID: {self.id}
Problem: 'Config' is valid JSON but is not a JSON object
Solution: Set 'Config' to a JSON object, e.g. \
{{"columns": [{{"key": "name"}}, {{"key": "amount", "label": "Amount"}}]}}
"""
            raise UserError(error_message)
        return config

    def _get_list_columns(self, config):
        """Parse and normalize the 'columns' key of `config`.

        Each entry of 'columns' must be a JSON object naming a 'key'
        (required — the row key rendered in that column) and, optionally,
        a 'label' (defaulting to 'key' as-is when empty).

        :param config: dict, this item's parsed :attr:`config`.
        :return: list of dict with keys 'key' and 'label', in the same
            order as `config`'s 'columns'.
        :rtype: list
        :raises UserError: when 'columns' is missing, empty, not a list,
            or contains an entry that is not an object or names no 'key'.
        """
        self.ensure_one()
        columns_raw = config.get("columns")
        if not isinstance(columns_raw, list) or not columns_raw:
            error_message = f"""
Context: Render dashboard item 'list' payload
Database ID: {self.id}
Problem: 'Config' does not name a non-empty 'columns' list
Solution: Set 'columns' to a list of objects with a 'key', e.g. \
{{"columns": [{{"key": "name"}}, {{"key": "amount", "label": "Amount"}}]}}
"""
            raise UserError(error_message)
        columns = []
        for column in columns_raw:
            if not isinstance(column, dict) or not column.get("key"):
                error_message = f"""
Context: Render dashboard item 'list' payload
Database ID: {self.id}
Problem: 'Config' key 'columns' has an entry without a 'key'
Solution: Give every entry of 'columns' a 'key', e.g. \
{{"key": "amount", "label": "Amount"}}
"""
                raise UserError(error_message)
            key = column["key"]
            label = column.get("label") or key
            columns.append({"key": key, "label": label})
        return columns

    def _get_list_limit(self, config):
        """Parse and validate the 'limit' key of `config`.

        :param config: dict, this item's parsed :attr:`config`.
        :return: the row limit, defaulting to 10 when 'limit' is absent.
        :rtype: int
        :raises UserError: when 'limit' is set but is not an integer
            between 1 and 100.
        """
        self.ensure_one()
        limit = config.get("limit")
        if limit is None:
            return _DEFAULT_LIMIT
        if (
            isinstance(limit, bool)
            or not isinstance(limit, int)
            or not (_MIN_LIMIT <= limit <= _MAX_LIMIT)
        ):
            error_message = f"""
Context: Render dashboard item 'list' payload
Database ID: {self.id}
Problem: 'Config' key 'limit' must be an integer between \
{_MIN_LIMIT} and {_MAX_LIMIT}, got '{limit}'
Solution: Set 'limit' to an integer between {_MIN_LIMIT} and {_MAX_LIMIT}, \
or remove it to use the default of {_DEFAULT_LIMIT}
"""
            raise UserError(error_message)
        return limit

    def _compute_list_rows(self, data, columns, limit):
        """Build the row payload a 'list' item's table renders.

        Caps `data` at `limit` rows **before** building rows, so the
        browser never receives more than `limit` rows. Each returned row
        holds exactly `columns`' keys — a source row missing a column's
        key contributes ``None`` for that key, so the browser renders an
        empty cell instead of erroring, since non-ORM sources (API, ODBC)
        do not guarantee a uniform row shape.

        :param data: list of dict, the item's fetched data
            (``payload["data"]``).
        :param columns: list of dict with keys 'key' and 'label', as
            returned by :meth:`_get_list_columns`.
        :param limit: int, maximum number of rows to return.
        :return: list of dict, at most `limit` long, each keyed like
            `columns`.
        :rtype: list
        """
        rows = []
        for row in data[:limit]:
            rows.append({column["key"]: row.get(column["key"]) for column in columns})
        return rows
