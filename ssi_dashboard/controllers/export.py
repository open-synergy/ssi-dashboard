# Copyright 2026 OpenSynergy Indonesia
# Copyright 2026 PT. Simetri Sinergi Indonesia
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
"""HTTP endpoints downloading a dashboard item's currently displayed data
as XLSX/CSV — see backlog issue #43's Keputusan Desain. Both routes call
``dashboard.item.prepare_export_data`` with the exact ``active_filters``
the browser's tile was last rendered with (see
``static/src/dashboard_item/dashboard_item.esm.js``'s
``buildExportUrl``), so the downloaded file can never drift from what is
on screen.

Read access is checked explicitly through ``record.check_access("read")``
before any data is assembled — a ``type="http"`` route is not covered by
the view-level access checks the backend UI relies on, so this endpoint
must check it itself. ``allow_export`` is checked the same way, right
after — never ``sudo()`` for either check."""

import csv
import io
import json
import re

import xlsxwriter

from odoo import http
from odoo.exceptions import MissingError, UserError
from odoo.http import request

#: Characters not safe inside a filename or an HTTP header value —
#: everything else in the item's own 'Name' is kept as-is.
_UNSAFE_FILENAME_CHARS = re.compile(r'[\\/:*?"<>|\r\n\x00-\x1f]')


def _sanitize_filename(name):
    """Strip characters that are not safe in a filename / HTTP
    'Content-Disposition' header value, per backlog issue #43's
    Keputusan Desain ("Nama berkas dibersihkan dari karakter yang tidak
    sah ... sebelum masuk ke header Content-Disposition").

    :param name: raw filename, e.g. a ``dashboard.item``'s own 'Name'.
    :type name: str
    :return: ``name`` with every unsafe character replaced by ``"_"``,
        falling back to ``"export"`` when that leaves nothing usable.
    :rtype: str
    """
    cleaned = _UNSAFE_FILENAME_CHARS.sub("_", name or "").strip()
    return cleaned or "export"


class DashboardItemExportController(http.Controller):
    def _resolve_export_item(self, item_id):
        """Resolve and authorize the ``dashboard.item`` an export
        request targets, shared by :meth:`export_xlsx`/:meth:`export_csv`.

        :param item_id: raw ``item_id`` query parameter.
        :type item_id: str
        :return: the resolved, authorized ``dashboard.item`` record.
        :rtype: recordset
        :raises UserError: when ``item_id`` is missing/not an integer,
            or the item exists but its 'Allow Export' is off.
        :raises MissingError: when ``item_id`` does not resolve to an
            existing record.
        :raises AccessError: propagated from ``check_access("read")``
            when the current user cannot read this item.
        """
        try:
            item_id_int = int(item_id)
        except (TypeError, ValueError):
            error_message = f"""
Context: Export dashboard item data
Problem: 'item_id' ({item_id!r}) is missing or not a valid integer
Solution: Pass a valid dashboard.item id as 'item_id'
"""
            raise UserError(error_message) from None
        item = request.env["dashboard.item"].browse(item_id_int)
        if not item.exists():
            error_message = f"""
Context: Export dashboard item data
Database ID: {item_id_int}
Problem: Dashboard item does not exist
Solution: Check the item id and try again
"""
            raise MissingError(error_message)
        # Row-level access is this endpoint's own responsibility — a
        # type="http" route is not covered by the view-level checks the
        # backend UI relies on. Never sudo() around this.
        item.check_access("read")
        if not item.allow_export:
            error_message = f"""
Context: Export dashboard item data
Database ID: {item.id}
Problem: 'Allow Export' is disabled for this item
Solution: Enable 'Allow Export' on the item, or export a different item
"""
            raise UserError(error_message)
        return item

    def _prepare_export(self, item_id, active_filters):
        """Resolve+authorize the item, then build its export data.

        :param item_id: raw ``item_id`` query parameter.
        :type item_id: str
        :param active_filters: raw ``active_filters`` query parameter —
            a JSON-encoded object matching
            ``dashboard.item.prepare_export_data``'s ``active_filters``
            argument, or empty/``None``/malformed (silently treated as
            "no filter", exactly like omitting it — this only narrows or
            widens the *data* returned, never bypasses the access checks
            done in :meth:`_resolve_export_item`).
        :type active_filters: str or None
        :return: see ``dashboard.item.prepare_export_data``.
        :rtype: dict
        """
        item = self._resolve_export_item(item_id)
        filters = None
        if active_filters:
            try:
                filters = json.loads(active_filters)
            except ValueError:
                filters = None
        return item.prepare_export_data(active_filters=filters)

    @http.route(
        "/ssi_dashboard/export/xlsx",
        type="http",
        auth="user",
        methods=["GET"],
        csrf=False,
    )
    def export_xlsx(self, item_id=None, active_filters=None, **kwargs):
        """Download the item's currently displayed data as XLSX.

        Numbers are written with ``write_number`` so Excel treats them
        as actual numbers (see ``dashboard.item.prepare_export_data``'s
        docstring) — never ``write`` for a numeric cell.
        """
        export_data = self._prepare_export(item_id, active_filters)
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {"in_memory": True})
        # Worksheet name is capped at 31 characters by the XLSX format
        # itself, regardless of how long the item's own 'Name' is.
        sheet = workbook.add_worksheet(request.env._("Export")[:31])
        header_format = workbook.add_format({"bold": True, "border": 1})
        cell_format = workbook.add_format({"border": 1})
        for col, header in enumerate(export_data["headers"]):
            sheet.write(0, col, header, header_format)
        for row_index, row in enumerate(export_data["rows"], start=1):
            for col, value in enumerate(row):
                if isinstance(value, (int, float)) and not isinstance(value, bool):
                    sheet.write_number(row_index, col, value, cell_format)
                else:
                    sheet.write(row_index, col, value or "", cell_format)
        workbook.close()
        filename = f"{_sanitize_filename(export_data['name'])}.xlsx"
        headers = [
            (
                "Content-Type",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            ),
            ("Content-Disposition", f'attachment; filename="{filename}"'),
        ]
        return request.make_response(output.getvalue(), headers=headers)

    @http.route(
        "/ssi_dashboard/export/csv",
        type="http",
        auth="user",
        methods=["GET"],
        csrf=False,
    )
    def export_csv(self, item_id=None, active_filters=None, **kwargs):
        """Download the item's currently displayed data as CSV.

        Encoded UTF-8 with a BOM (``utf-8-sig``) so the file opens with
        the right characters in an Indonesian-locale Excel — Keputusan
        Desain.
        """
        export_data = self._prepare_export(item_id, active_filters)
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(export_data["headers"])
        writer.writerows(export_data["rows"])
        content = buffer.getvalue().encode("utf-8-sig")
        filename = f"{_sanitize_filename(export_data['name'])}.csv"
        headers = [
            ("Content-Type", "text/csv; charset=utf-8"),
            ("Content-Disposition", f'attachment; filename="{filename}"'),
        ]
        return request.make_response(content, headers=headers)
