# Copyright 2026 OpenSynergy Indonesia
# Copyright 2026 PT. Simetri Sinergi Indonesia
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
import base64
import json

from odoo import fields, models
from odoo.exceptions import UserError

SUPPORTED_SCHEMA_VERSION = 1


class DashboardImport(models.TransientModel):
    """Wizard that recreates a dashboard, its items and their data
    sources from a JSON file built by
    ``dashboard.dashboard.prepare_export_definition``.

    Security notes (untrusted input — the uploaded file is written by
    whoever exported it, possibly on a different, less trusted database):

    - The file is parsed with :func:`json.loads` only. Never
      :func:`eval`/:func:`ast.literal_eval` on the raw bytes, and never
      :mod:`pickle` — see :meth:`_parse_data_file`.
    - Its overall shape (expected keys, container types) is validated
      before any of its content is trusted — see :meth:`_check_structure`.
      A record is never built straight from a raw JSON dict; every
      ``create()`` call in this wizard passes an explicit, hand-picked
      ``vals`` dict (see :meth:`_import_one_data_source`,
      :meth:`_import_one_item`, :meth:`_import_one_filter`).
    - ``schema_version`` must equal :data:`SUPPORTED_SCHEMA_VERSION` — a
      file with an unrecognized version is rejected outright, never
      processed best-effort. See :meth:`_check_schema_version`.
    - Every model/field the file references is resolved and checked to
      exist on this database *before* anything is created — see
      :meth:`_check_missing_refs`. A file naming one missing model/field
      reports every missing reference in a single ``UserError`` instead
      of failing midway through, leaving a half-imported dashboard
      behind.
    - Restricted to ``ssi_dashboard.group_dashboard_admin``, checked
      here (see :meth:`_check_import_access`), same as
      ``dashboard.dashboard.prepare_export_definition``.

    Never overwrites an existing record: :meth:`action_import` always
    creates a brand new ``dashboard.dashboard`` (see
    :meth:`_import_dashboard`) and a brand new ``dashboard.data_source``
    for every entry under the file's ``data_sources`` key (see
    :meth:`_import_data_sources`), suffixing ``code`` with a numeric
    counter (:meth:`_generate_unique_code`) whenever the original value
    is already taken — both models enforce a UNIQUE constraint on
    ``code``.
    """

    _name = "dashboard.import"
    _description = "Import Dashboard Definition"

    data_file = fields.Binary(
        string="Dashboard File",
        required=True,
        help="JSON file produced by a dashboard's 'Export' action "
        "(dashboard.dashboard.prepare_export_definition).",
    )
    filename = fields.Char(
        help="Original name of the uploaded file, kept so the binary "
        "widget can offer it back for download.",
    )
    name_suffix = fields.Char(
        default=" (Imported)",
        help="Appended to the imported dashboard's 'Name', so it is "
        "never mistaken for the dashboard the file was exported from.",
    )

    def action_import(self):
        """Create a new dashboard from :attr:`data_file`.

        :return: ``ir.actions.client`` opening the newly created
            dashboard — see ``dashboard.dashboard.action_open_dashboard``.
        :rtype: dict
        :raises UserError: see :meth:`_check_import_access`,
            :meth:`_parse_data_file`, :meth:`_check_structure`,
            :meth:`_check_schema_version` and :meth:`_check_missing_refs`.
        """
        self.ensure_one()
        self._check_import_access()
        data = self._parse_data_file()
        self._check_schema_version(data)
        self._check_structure(data)
        self._check_missing_refs(data)
        dashboard = self._import_dashboard(data)
        data_source_map = self._import_data_sources(data.get("data_sources") or {})
        self._import_items(dashboard, data.get("items") or [], data_source_map)
        self._import_filters(dashboard, data.get("filters") or [])
        return dashboard.action_open_dashboard()

    def _check_import_access(self):
        """Raise ``UserError`` unless the current user belongs to
        ``group_dashboard_admin``. Same restriction, checked the same
        way, as ``dashboard.dashboard._check_export_access``.

        :return: None
        :raises UserError: when the current user is not a member of
            ``ssi_dashboard.group_dashboard_admin``.
        """
        self.ensure_one()
        if not self.env.user.has_group("ssi_dashboard.group_dashboard_admin"):
            error_message = f"""
Context: Import dashboard definition
Database ID: {self.id}
Problem: Current user is not a member of the 'Administrator' dashboard \
group
Solution: Ask a dashboard administrator to import this file, or request \
'Administrator' access
"""
            raise UserError(error_message)

    def _parse_data_file(self):
        """Decode and JSON-parse :attr:`data_file`.

        Uses :func:`json.loads` only — never ``eval``/``ast.literal_eval``
        /``pickle`` — so a crafted file can, at worst, produce a plain
        Python ``dict``/``list``/scalar tree; it can never execute code
        while being parsed.

        :return: parsed JSON value.
        :raises UserError: when :attr:`data_file` is not valid base64,
            not valid UTF-8 text, not valid JSON, or does not parse to a
            ``dict``.
        """
        self.ensure_one()
        try:
            raw_bytes = base64.b64decode(self.data_file or b"", validate=True)
        except Exception as error:
            error_message = f"""
Context: Import dashboard definition
Database ID: {self.id}
Problem: 'Dashboard File' is not a valid file upload ({error})
Solution: Upload a JSON file produced by a dashboard's 'Export' action
"""
            raise UserError(error_message) from error
        try:
            text = raw_bytes.decode("utf-8")
        except UnicodeDecodeError as error:
            error_message = f"""
Context: Import dashboard definition
Database ID: {self.id}
Problem: 'Dashboard File' is not valid UTF-8 text
Solution: Upload a JSON file produced by a dashboard's 'Export' action
"""
            raise UserError(error_message) from error
        try:
            data = json.loads(text)
        except json.JSONDecodeError as error:
            error_message = f"""
Context: Import dashboard definition
Database ID: {self.id}
Problem: 'Dashboard File' is not valid JSON ({error})
Solution: Upload a JSON file produced by a dashboard's 'Export' action
"""
            raise UserError(error_message) from error
        if not isinstance(data, dict):
            error_message = f"""
Context: Import dashboard definition
Database ID: {self.id}
Problem: 'Dashboard File' does not contain a JSON object at its top level
Solution: Upload a JSON file produced by a dashboard's 'Export' action
"""
            raise UserError(error_message)
        return data

    def _check_schema_version(self, data):
        """Raise ``UserError`` unless ``data['schema_version']`` equals
        :data:`SUPPORTED_SCHEMA_VERSION`.

        A file with an unrecognized ``schema_version`` is rejected
        outright rather than processed best-effort — a future version of
        this module may change the meaning of existing keys, and
        guessing would silently misimport instead of failing loud.

        :param data: parsed file, see :meth:`_parse_data_file`.
        :type data: dict
        :raises UserError: when ``schema_version`` is missing or not
            equal to :data:`SUPPORTED_SCHEMA_VERSION`.
        """
        self.ensure_one()
        schema_version = data.get("schema_version")
        if schema_version != SUPPORTED_SCHEMA_VERSION:
            error_message = f"""
Context: Import dashboard definition
Database ID: {self.id}
Problem: 'Dashboard File' has 'schema_version' {schema_version!r}, which \
this version of the module only supports {SUPPORTED_SCHEMA_VERSION!r}
Solution: Re-export the dashboard with a version of this module that \
produces schema_version {SUPPORTED_SCHEMA_VERSION!r}, or upgrade this \
module to one that supports schema_version {schema_version!r}
"""
            raise UserError(error_message)

    def _check_structure(self, data):
        """Validate the overall shape of ``data`` before any of its
        content is trusted — keys expected to be present, and of the
        right container type.

        Runs before :meth:`_check_missing_refs`/import so a file with
        an unexpected structure (hand-edited, truncated, or not
        actually produced by ``prepare_export_definition``) fails with
        one readable ``UserError`` instead of an unhandled
        ``AttributeError``/``TypeError`` partway through reading it.

        :param data: parsed file, see :meth:`_parse_data_file`.
        :type data: dict
        :raises UserError: when ``dashboard`` is missing/not an object
            with a ``name``, ``items``/``filters`` are present but not
            a list of objects, or ``data_sources`` is present but not
            an object of objects.
        """
        self.ensure_one()
        problems = []
        dashboard_vals = data.get("dashboard")
        if not isinstance(dashboard_vals, dict) or not dashboard_vals.get("name"):
            problems.append("'dashboard' must be an object with a 'name'")
        items = data.get("items", [])
        if not isinstance(items, list) or not all(
            isinstance(item, dict) for item in items
        ):
            problems.append("'items' must be a list of objects")
        filters = data.get("filters", [])
        if not isinstance(filters, list) or not all(
            isinstance(filter_, dict) for filter_ in filters
        ):
            problems.append("'filters' must be a list of objects")
        data_sources = data.get("data_sources", {})
        if not isinstance(data_sources, dict) or not all(
            isinstance(vals, dict) for vals in data_sources.values()
        ):
            problems.append("'data_sources' must be an object of objects")
        if problems:
            joined = "\n".join(f"- {problem}" for problem in problems)
            error_message = f"""
Context: Import dashboard definition
Database ID: {self.id}
Problem: 'Dashboard File' does not have the expected structure:
{joined}
Solution: Upload a JSON file produced by a dashboard's 'Export' action, \
unmodified apart from field values
"""
            raise UserError(error_message)

    def _check_missing_refs(self, data):
        """Validate every model/field reference in ``data`` exists on
        this database, and raise one ``UserError`` listing all of them
        at once when any is missing.

        Checked, each contributing its own label to the collected list:
        every data source's ``model`` (:meth:`_check_missing_model_ref`)
        and every field-ref dict anywhere in the file (``measure_field``,
        ``group_by_field``, ``sub_group_by_field``, ``date_field``, each
        ``measure_ids`` row's ``field``, each item's ``drilldown_ids``
        row's ``field``, each filter's ``field``) via
        :meth:`_check_missing_field_ref`.

        Deliberately does not check ``dashboard.color_scheme``/
        ``res.groups``/``res.currency`` references (``color_scheme``,
        ``group_ids``, ``currency``) — those are best-effort (see
        :meth:`_resolve_color_scheme`, :meth:`_resolve_currency`,
        :meth:`_resolve_group_ids`), left empty rather than blocking the
        whole import, since a dashboard/item still renders without them.

        :param data: parsed file, already passed :meth:`_check_structure`.
        :type data: dict
        :raises UserError: when at least one model/field reference is
            missing, formatted as one line per missing reference.
        """
        self.ensure_one()
        missing = []
        data_sources = data.get("data_sources") or {}
        for code, vals in data_sources.items():
            self._check_missing_model_ref(
                vals.get("model"), f"data source '{code}'", missing
            )
            for key in (
                "measure_field",
                "group_by_field",
                "sub_group_by_field",
                "date_field",
            ):
                self._check_missing_field_ref(
                    vals.get(key), f"data source '{code}' ({key})", missing
                )
            for measure in vals.get("measure_ids") or []:
                if not isinstance(measure, dict):
                    continue
                self._check_missing_field_ref(
                    measure.get("field"),
                    f"data source '{code}' measure '{measure.get('name')}'",
                    missing,
                )
        for item in data.get("items") or []:
            for drilldown in item.get("drilldown_ids") or []:
                if not isinstance(drilldown, dict):
                    continue
                self._check_missing_field_ref(
                    drilldown.get("field"),
                    f"item '{item.get('name')}' drill-down level",
                    missing,
                )
        for filter_ in data.get("filters") or []:
            self._check_missing_field_ref(
                filter_.get("field"), f"filter '{filter_.get('name')}'", missing
            )
        if missing:
            joined = "\n".join(f"- {line}" for line in missing)
            error_message = f"""
Context: Import dashboard definition
Database ID: {self.id}
Problem: 'Dashboard File' refers to model(s)/field(s) that do not exist \
on this database:
{joined}
Solution: Install the module(s) that provide the missing model(s)/ \
field(s) on this database, or edit 'Dashboard File' to remove the \
references, then import again
"""
            raise UserError(error_message)

    def _check_missing_model_ref(self, model_name, label, missing):
        """Append a description to ``missing`` when ``model_name`` does
        not exist on this database.

        :param model_name: technical model name to look up, or falsy.
        :type model_name: str or bool
        :param label: human-readable description of where this
            reference was found in the file, appended to the message.
        :type label: str
        :param missing: accumulator list, appended to in place.
        :type missing: list
        :return: None
        """
        if not model_name or not isinstance(model_name, str):
            return
        if not self.env["ir.model"].sudo().search_count([("model", "=", model_name)]):
            missing.append(f"Model '{model_name}' (referenced by {label})")

    def _check_missing_field_ref(self, ref, label, missing):
        """Append a description to ``missing`` when the field-ref
        ``ref`` (see ``dashboard.data_source._export_field_ref``) does
        not resolve to an existing ``ir.model.fields`` record on this
        database.

        :param ref: ``{"model": ..., "field": ...}`` dict, or falsy.
        :type ref: dict or bool
        :param label: human-readable description of where this
            reference was found in the file, appended to the message.
        :type label: str
        :param missing: accumulator list, appended to in place.
        :type missing: list
        :return: None
        """
        if not ref or not isinstance(ref, dict):
            return
        model_name = ref.get("model")
        field_name = ref.get("field")
        domain = [("model", "=", model_name), ("name", "=", field_name)]
        if not self.env["ir.model.fields"].sudo().search_count(domain):
            missing.append(f"Field '{model_name}.{field_name}' (referenced by {label})")

    def _resolve_field(self, ref):
        """Resolve one field-ref dict (see ``dashboard.data_source.
        _export_field_ref``) back into an ``ir.model.fields`` record.

        Only called after :meth:`_check_missing_refs` has already
        proven every field-ref in the file resolves, so the ``search``
        here is not expected to come back empty — kept defensive
        (returns an empty recordset rather than raising) so a race (the
        field having been removed between the check and here) degrades
        to "field left empty" instead of a raw ORM exception escaping
        mid-import.

        :param ref: ``{"model": ..., "field": ...}`` dict, or falsy.
        :type ref: dict or bool
        :return: ``ir.model.fields`` record, or empty recordset.
        :rtype: recordset
        """
        self.ensure_one()
        if not ref or not isinstance(ref, dict):
            return self.env["ir.model.fields"]
        return (
            self.env["ir.model.fields"]
            .sudo()
            .search(
                [("model", "=", ref.get("model")), ("name", "=", ref.get("field"))],
                limit=1,
            )
        )

    def _resolve_model(self, model_name):
        """Resolve a technical model name back into an ``ir.model``
        record. See :meth:`_resolve_field` for why this stays defensive
        instead of raising.

        :param model_name: technical model name, or falsy.
        :type model_name: str or bool
        :return: ``ir.model`` record, or empty recordset.
        :rtype: recordset
        """
        self.ensure_one()
        if not model_name or not isinstance(model_name, str):
            return self.env["ir.model"]
        return self.env["ir.model"].sudo().search([("model", "=", model_name)], limit=1)

    def _resolve_color_scheme(self, code):
        """Resolve a ``dashboard.color_scheme`` ``code`` back into a
        record. Best-effort — see :meth:`_check_missing_refs`: a
        dashboard still renders (with default styling) without one.

        :param code: :attr:`~dashboard.color_scheme.code`, or falsy.
        :type code: str or bool
        :return: ``dashboard.color_scheme`` record, or empty recordset.
        :rtype: recordset
        """
        self.ensure_one()
        if not code or not isinstance(code, str):
            return self.env["dashboard.color_scheme"]
        return self.env["dashboard.color_scheme"].search([("code", "=", code)], limit=1)

    def _resolve_currency(self, code):
        """Resolve a currency ISO code back into a ``res.currency``
        record. Best-effort — see :meth:`_check_missing_refs`: only
        used to prefill an item's ``currency_id``.

        :param code: currency ISO code (``res.currency.name``), or
            falsy.
        :type code: str or bool
        :return: ``res.currency`` record, or empty recordset.
        :rtype: recordset
        """
        self.ensure_one()
        if not code or not isinstance(code, str):
            return self.env["res.currency"]
        return self.env["res.currency"].search([("name", "=", code)], limit=1)

    def _resolve_group_ids(self, xmlids):
        """Resolve a list of external id strings (see ``dashboard.
        dashboard._export_group_xmlids``) back into a ``res.groups``
        recordset. Best-effort — see :meth:`_check_missing_refs`: any
        entry that is not a well-formed ``"module.name"`` string, or
        does not resolve to a ``res.groups`` record, is silently
        skipped instead of blocking the import.

        :param xmlids: list of ``"module.name"`` strings, or falsy.
        :type xmlids: list or bool
        :return: ``res.groups`` recordset, possibly empty.
        :rtype: recordset
        """
        self.ensure_one()
        groups = self.env["res.groups"]
        for xmlid in xmlids or []:
            if not isinstance(xmlid, str) or "." not in xmlid:
                continue
            group = self.env.ref(xmlid, raise_if_not_found=False)
            if group is not None and group._name == "res.groups":
                groups |= group
        return groups

    def _generate_unique_code(self, model_name, base_code):
        """Build a ``code`` value guaranteed unused on ``model_name``,
        starting from ``base_code`` and appending a numeric counter
        when it is already taken.

        Both ``dashboard.dashboard`` (``_dashboard_dashboard_code_uniq``)
        and ``dashboard.data_source`` (``_dashboard_data_source_code_uniq``)
        enforce a UNIQUE constraint on ``code`` — since :meth:`action_import`
        never overwrites an existing record, importing the same file
        twice, or importing into a database that already has a
        dashboard/data source with the same ``code``, must not collide.

        :param model_name: ``"dashboard.dashboard"`` or
            ``"dashboard.data_source"``.
        :type model_name: str
        :param base_code: ``code`` value read from the file (or a
            fallback when the file did not carry one).
        :type base_code: str
        :return: ``base_code`` unchanged when unused, otherwise
            ``f"{base_code}-{counter}"`` for the smallest ``counter``
            starting at ``2`` not already used.
        :rtype: str
        """
        self.ensure_one()
        model = self.env[model_name].sudo()
        if not model.search_count([("code", "=", base_code)]):
            return base_code
        counter = 2
        while model.search_count([("code", "=", f"{base_code}-{counter}")]):
            counter += 1
        return f"{base_code}-{counter}"

    def _import_dashboard(self, data):
        """Create the new ``dashboard.dashboard`` behind
        :attr:`data`'s ``dashboard`` key.

        Always creates a new record with menu generation off (see
        ``dashboard.dashboard._prepare_export_dashboard_vals``) —
        :attr:`~dashboard.dashboard.generate_menu` simply is not set,
        keeping the model's own default (``False``).

        :param data: parsed file, already passed :meth:`_check_structure`
            and :meth:`_check_missing_refs`.
        :type data: dict
        :return: newly created ``dashboard.dashboard`` record.
        :rtype: recordset
        """
        self.ensure_one()
        vals = data.get("dashboard") or {}
        base_code = vals.get("code") or "IMPORTED-DASHBOARD"
        code = self._generate_unique_code("dashboard.dashboard", base_code)
        color_scheme = self._resolve_color_scheme(vals.get("color_scheme"))
        group_ids = self._resolve_group_ids(vals.get("group_ids"))
        return self.env["dashboard.dashboard"].create(
            {
                "name": f"{vals.get('name') or ''}{self.name_suffix or ''}",
                "code": code,
                "color_scheme_id": color_scheme.id,
                "refresh_interval": vals.get("refresh_interval") or "0",
                "fullscreen_enabled": bool(vals.get("fullscreen_enabled", True)),
                "group_ids": [(6, 0, group_ids.ids)],
            }
        )

    def _import_data_sources(self, data_sources):
        """Create one new ``dashboard.data_source`` per entry of
        ``data_sources``.

        :param data_sources: ``data['data_sources']``, already passed
            :meth:`_check_structure` and :meth:`_check_missing_refs`.
        :type data_sources: dict
        :return: mapping of the file's own ``code`` (the key of
            ``data_sources``) to the matching newly created
            ``dashboard.data_source`` record — used by
            :meth:`_import_items` to resolve each item's
            ``data_source``.
        :rtype: dict
        """
        self.ensure_one()
        return {
            code: self._import_one_data_source(code, vals)
            for code, vals in data_sources.items()
        }

    def _import_one_data_source(self, code, vals):
        """Create one ``dashboard.data_source`` record from one entry
        of ``data_sources``.

        Every value comes from an explicit key read off ``vals`` — never
        ``self.env["dashboard.data_source"].create(vals)`` on the raw
        dict — so an unexpected key in ``vals`` can never reach
        ``create()``.

        :param code: this entry's key in the file's ``data_sources``
            dict — used as a fallback ``name``/``code`` base when
            ``vals`` does not carry its own.
        :type code: str
        :param vals: this entry's own dict, see ``dashboard.
            data_source._prepare_export_data_source_vals`` for the
            shape.
        :type vals: dict
        :return: newly created ``dashboard.data_source`` record.
        :rtype: recordset
        """
        self.ensure_one()
        model = self._resolve_model(vals.get("model"))
        new_code = self._generate_unique_code(
            "dashboard.data_source", vals.get("code") or code or "IMPORTED-DS"
        )
        measure_vals = [
            (0, 0, self._prepare_import_measure_vals(measure))
            for measure in vals.get("measure_ids") or []
            if isinstance(measure, dict)
        ]
        return self.env["dashboard.data_source"].create(
            {
                "name": vals.get("name") or code,
                "code": new_code,
                "type": vals.get("type") or "orm",
                "model_id": model.id,
                "domain": vals.get("domain") or "[]",
                "measure_field_id": self._resolve_field(vals.get("measure_field")).id,
                "aggregate": vals.get("aggregate") or "count",
                "group_by_field_id": self._resolve_field(vals.get("group_by_field")).id,
                "group_by_granularity": vals.get("group_by_granularity") or False,
                "sub_group_by_field_id": self._resolve_field(
                    vals.get("sub_group_by_field")
                ).id,
                "sub_group_by_granularity": vals.get("sub_group_by_granularity")
                or False,
                "limit": vals.get("limit") or 0,
                "sort_by": vals.get("sort_by") or "none",
                "sort_order": vals.get("sort_order") or "desc",
                "fill_temporal": bool(vals.get("fill_temporal")),
                "measure_ids": measure_vals,
                "date_field_id": self._resolve_field(vals.get("date_field")).id,
                "date_range": vals.get("date_range") or "all_time",
                "date_start": vals.get("date_start") or False,
                "date_end": vals.get("date_end") or False,
                "comparison": vals.get("comparison") or "none",
                "comparison_year_count": vals.get("comparison_year_count") or 1,
            }
        )

    def _prepare_import_measure_vals(self, vals):
        """Build the ``(0, 0, vals)`` payload of one ``measure_ids`` row
        for :meth:`_import_one_data_source`.

        :param vals: one entry of the file's ``measure_ids`` list, see
            ``dashboard.data_source.measure._prepare_export_measure_vals``.
        :type vals: dict
        :return: dict accepted by ``dashboard.data_source.measure.create``.
        :rtype: dict
        """
        self.ensure_one()
        return {
            "sequence": vals.get("sequence") or 10,
            "name": vals.get("name") or "",
            "field_id": self._resolve_field(vals.get("field")).id,
            "aggregate": vals.get("aggregate") or "sum",
        }

    def _import_items(self, dashboard, items, data_source_map):
        """Create one new ``dashboard.item`` per entry of ``items``,
        linked to ``dashboard``.

        :param dashboard: newly created ``dashboard.dashboard`` record,
            see :meth:`_import_dashboard`.
        :type dashboard: recordset
        :param items: ``data['items']``, already passed
            :meth:`_check_structure` and :meth:`_check_missing_refs`.
        :type items: list
        :param data_source_map: see :meth:`_import_data_sources`.
        :type data_source_map: dict
        :return: None
        """
        self.ensure_one()
        for vals in items:
            self._import_one_item(dashboard, vals, data_source_map)

    def _import_one_item(self, dashboard, vals, data_source_map):
        """Create one ``dashboard.item`` record from one entry of
        ``items``.

        Every value comes from an explicit key read off ``vals`` — see
        :meth:`_import_one_data_source` for why.

        :param dashboard: see :meth:`_import_items`.
        :type dashboard: recordset
        :param vals: this entry's own dict, see ``dashboard.item.
            _prepare_export_item_vals`` for the shape.
        :type vals: dict
        :param data_source_map: see :meth:`_import_data_sources`. Used
            to resolve ``vals['data_source']`` (a ``code`` string) back
            into the newly created data source with that ``code`` --
            ``False``/missing when the item had none, which
            :meth:`dashboard.item._is_data_source_required` may or may
            not allow depending on ``type``.
        :type data_source_map: dict
        :return: newly created ``dashboard.item`` record.
        :rtype: recordset
        """
        self.ensure_one()
        data_source = data_source_map.get(vals.get("data_source"))
        currency = self._resolve_currency(vals.get("currency"))
        goal_vals = [
            (0, 0, self._prepare_import_goal_vals(goal))
            for goal in vals.get("goal_ids") or []
            if isinstance(goal, dict)
        ]
        drilldown_vals = [
            (0, 0, self._prepare_import_drilldown_vals(drilldown))
            for drilldown in vals.get("drilldown_ids") or []
            if isinstance(drilldown, dict)
        ]
        return self.env["dashboard.item"].create(
            {
                "dashboard_id": dashboard.id,
                "name": vals.get("name") or "",
                "sequence": vals.get("sequence") or 10,
                "type": vals.get("type") or "placeholder",
                "data_source_id": data_source.id if data_source else False,
                "config": vals.get("config") or False,
                "column_width": vals.get("column_width") or 4,
                "row_height": vals.get("row_height") or 1,
                "column_start": vals.get("column_start") or 0,
                "row_start": vals.get("row_start") or 0,
                "active": bool(vals.get("active", True)),
                "allow_open_records": bool(vals.get("allow_open_records", True)),
                "allow_export": bool(vals.get("allow_export", True)),
                "goal_type": vals.get("goal_type") or "none",
                "goal_value": vals.get("goal_value") or 0.0,
                "goal_ids": goal_vals,
                "drilldown_ids": drilldown_vals,
                "multiplier": vals.get("multiplier") or 1.0,
                "unit_type": vals.get("unit_type") or "none",
                "currency_id": currency.id if currency else False,
                "unit_text": vals.get("unit_text") or False,
                "unit_position": vals.get("unit_position") or "after",
                "number_format": vals.get("number_format") or "exact",
                "precision_digits": (
                    vals.get("precision_digits")
                    if vals.get("precision_digits") is not None
                    else 2
                ),
                "item_theme": vals.get("item_theme") or "inherit",
                "item_header_color": vals.get("item_header_color") or False,
                "item_border_color": vals.get("item_border_color") or False,
            }
        )

    def _prepare_import_goal_vals(self, vals):
        """Build the ``(0, 0, vals)`` payload of one ``goal_ids`` row
        for :meth:`_import_one_item`.

        :param vals: one entry of the file's ``goal_ids`` list, see
            ``dashboard.item.goal._prepare_export_goal_vals``.
        :type vals: dict
        :return: dict accepted by ``dashboard.item.goal.create``.
        :rtype: dict
        """
        self.ensure_one()
        return {
            "date_start": vals.get("date_start") or False,
            "date_end": vals.get("date_end") or False,
            "value": vals.get("value") or 0.0,
        }

    def _prepare_import_drilldown_vals(self, vals):
        """Build the ``(0, 0, vals)`` payload of one ``drilldown_ids``
        row for :meth:`_import_one_item`.

        :param vals: one entry of the file's ``drilldown_ids`` list,
            see ``dashboard.item.drilldown._prepare_export_drilldown_vals``.
        :type vals: dict
        :return: dict accepted by ``dashboard.item.drilldown.create``.
        :rtype: dict
        """
        self.ensure_one()
        return {
            "sequence": vals.get("sequence") or 10,
            "field_id": self._resolve_field(vals.get("field")).id,
            "granularity": vals.get("granularity") or False,
        }

    def _import_filters(self, dashboard, filters):
        """Create one new ``dashboard.filter`` per entry of ``filters``,
        linked to ``dashboard``.

        :param dashboard: see :meth:`_import_items`.
        :type dashboard: recordset
        :param filters: ``data['filters']``, already passed
            :meth:`_check_structure` and :meth:`_check_missing_refs`.
        :type filters: list
        :return: None
        """
        self.ensure_one()
        for vals in filters:
            self._import_one_filter(dashboard, vals)

    def _import_one_filter(self, dashboard, vals):
        """Create one ``dashboard.filter`` record from one entry of
        ``filters``.

        :param dashboard: see :meth:`_import_items`.
        :type dashboard: recordset
        :param vals: this entry's own dict, see ``dashboard.filter.
            _prepare_export_filter_vals`` for the shape.
        :type vals: dict
        :return: newly created ``dashboard.filter`` record.
        :rtype: recordset
        """
        self.ensure_one()
        field = self._resolve_field(vals.get("field"))
        return self.env["dashboard.filter"].create(
            {
                "dashboard_id": dashboard.id,
                "name": vals.get("name") or "",
                "sequence": vals.get("sequence") or 10,
                "filter_type": vals.get("filter_type") or "domain",
                "domain": vals.get("domain") or False,
                "field_id": field.id if field else False,
                "default_active": bool(vals.get("default_active")),
            }
        )
