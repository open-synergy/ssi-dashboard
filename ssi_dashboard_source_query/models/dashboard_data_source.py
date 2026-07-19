# Copyright 2026 OpenSynergy Indonesia
# Copyright 2026 PT. Simetri Sinergi Indonesia
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError


class DashboardDataSource(models.Model):
    """Extends `dashboard.data_source` with the 'query' type: runs a raw
    SQL SELECT statement written by a dashboard administrator and
    returns its rows in the same shape other data source types return.
    See :meth:`_fetch_data_query` for the safeguards enforced before the
    statement is ever sent to the database."""

    _name = "dashboard.data_source"
    _inherit = [
        "dashboard.data_source",
    ]

    type = fields.Selection(
        selection_add=[
            ("query", "SQL Query"),
        ],
        ondelete={"query": "set default"},
    )
    query = fields.Text(
        groups="ssi_dashboard.group_dashboard_admin",
        help="Raw SQL SELECT statement executed to fetch this data "
        "source's rows. Must start with 'SELECT' and must not contain "
        "a semicolon other than a single trailing one. May reference "
        "the named parameters '%(date_start)s', '%(date_end)s', "
        "'%(uid)s' and '%(company_id)s' — never concatenate values "
        "into the statement itself, they are always passed as "
        "parameters to the query. Executed with full database "
        "privileges, so this field is readable and editable only by "
        "the Dashboard Administrator group. Only used when 'Type' is "
        "'SQL Query' (query).",
    )

    @api.constrains("type", "query")
    def _check_query_required(self):
        for record in self:
            if record.type == "query" and not record.query:
                error_message = f"""
Context: Configure dashboard data source query
Database ID: {record.id}
Problem: 'Type' is 'SQL Query' but 'Query' is empty
Solution: Set 'Query', or change 'Type' to another value
"""
                raise ValidationError(error_message)

    def _fetch_data_query(self, item):
        """Fetch data for the 'query' data source type.

        Runs :attr:`query` against the database and returns its rows.
        Every safeguard below is enforced before the statement is ever
        sent to the database:

        - :attr:`query`, once normalized (collapsed whitespace, upper
          case), must start with the keyword ``SELECT`` — anything else
          is rejected. See :meth:`_check_query_is_select`.
        - :attr:`query` must not contain a semicolon anywhere other
          than as its very last character, which blocks appending a
          second statement after the ``SELECT``. See
          :meth:`_check_query_no_stacked_statements`.
        - The statement runs inside a ``SAVEPOINT``
          (:meth:`~odoo.sql_db.BaseCursor.savepoint`), so a failing
          query only rolls back to that savepoint instead of aborting
          the whole caller transaction.
        - A 10-second ``statement_timeout`` is set on the session
          before the statement runs, so a heavy query cannot hang the
          worker indefinitely.

        :attr:`query` is executed through
        :meth:`~odoo.sql_db.Cursor.execute` with a **named parameter
        dict** built by :meth:`_prepare_query_params`
        (``%(date_start)s``/``%(date_end)s``/``%(uid)s``/
        ``%(company_id)s``) — every dynamic value is passed to the
        database driver as a bind parameter, never concatenated or
        string-formatted into the SQL text itself, so nothing in those
        values can alter the statement's structure or smuggle a second
        statement.

        As a last step, :meth:`~dashboard.data_source._postprocess_rows`
        applies :attr:`fill_temporal`, :attr:`sort_by`/:attr:`sort_order`
        and :attr:`limit` to the rows, exactly like every other data
        source type. When :attr:`query` returns a column named
        ``group_label``, that column is used as-is as each row's group
        label, so a chart or table bound to a ``query`` data source
        works without further changes.

        :param item: ``dashboard.item`` record requesting the data.
        :return: list of dict, one per row, keyed by the SQL column
            names — the shape
            :meth:`~odoo.sql_db.Cursor.dictfetchall` already returns,
            matching the ``_fetch_data`` contract — after
            :meth:`~dashboard.data_source._postprocess_rows`.
        :rtype: list
        :raises UserError: when :attr:`query` fails either safeguard
            above, or when the database rejects the statement (syntax
            error, missing privilege, timeout, ...).
        """
        self.ensure_one()
        query = self._prepare_query_statement()
        params = self._prepare_query_params()
        cr = self.env.cr
        try:
            with cr.savepoint():
                cr.execute("SET LOCAL statement_timeout = 10000")
                cr.execute(query, params)
                rows = cr.dictfetchall()
        except Exception as error:
            raise self._query_error(
                f"'Query' failed to execute ({error.__class__.__name__})",
                f"Fix 'Query' so it runs successfully against the "
                f"database. Original error: {error}",
            ) from error
        return self._postprocess_rows(rows)

    def _prepare_query_statement(self):
        """Validate and return :attr:`query`, ready to execute.

        See :meth:`_fetch_data_query` for what is enforced here.

        :return: :attr:`query`, stripped of leading/trailing whitespace.
        :rtype: str
        :raises UserError: see :meth:`_fetch_data_query`.
        """
        self.ensure_one()
        query = (self.query or "").strip()
        self._check_query_is_select(query)
        self._check_query_no_stacked_statements(query)
        return query

    def _check_query_is_select(self, query):
        """Reject `query` when it does not start with ``SELECT``.

        :param query: stripped :attr:`query` value being validated.
        :type query: str
        :raises UserError: when the normalized (collapsed whitespace,
            upper case) `query` does not start with ``SELECT``.
        """
        self.ensure_one()
        normalized = " ".join(query.split()).upper()
        if not normalized.startswith("SELECT"):
            raise self._query_error(
                "'Query' does not start with the keyword SELECT",
                "Write a single SELECT statement in 'Query'",
            )

    def _check_query_no_stacked_statements(self, query):
        """Reject `query` when it stacks more than one statement.

        A semicolon is only allowed as the very last character of
        `query` — anywhere else it is treated as the separator between
        two statements and rejected, so :attr:`query` cannot be used to
        append a second, unreviewed statement after the ``SELECT``.

        :param query: stripped :attr:`query` value being validated.
        :type query: str
        :raises UserError: when a semicolon is found anywhere in `query`
            other than as its last character.
        """
        self.ensure_one()
        body = query[:-1] if query.endswith(";") else query
        if ";" in body:
            raise self._query_error(
                "'Query' contains a semicolon other than a single trailing one",
                "Write exactly one SELECT statement in 'Query' — remove "
                "the extra semicolon and everything chained after it",
            )

    def _prepare_query_params(self):
        """Build the named parameter dict :attr:`query` is executed
        with.

        :attr:`query` may reference any of these as ``%(name)s``
        placeholders; keys `query` does not reference are simply
        ignored by :meth:`~odoo.sql_db.Cursor.execute`.

        :return: dict with keys ``date_start``/``date_end`` (from
            :meth:`_prepare_date_range`, either may be ``None`` — see
            that method), ``uid`` (current user id) and ``company_id``
            (current company id).
        :rtype: dict
        """
        self.ensure_one()
        date_start, date_end = self._prepare_date_range()
        return {
            "date_start": date_start,
            "date_end": date_end,
            "uid": self.env.uid,
            "company_id": self.env.company.id,
        }

    def _query_error(self, problem, solution):
        """Build the ``UserError`` this data source type raises on
        failure.

        :param problem: str, what went wrong.
        :param solution: str, how the user can fix it.
        :return: ``UserError`` ready to be raised by the caller.
        :rtype: UserError
        """
        self.ensure_one()
        error_message = f"""
Document Type: {self._description}
Context: Fetch dashboard item data from a SQL query
Database ID: {self.id}
Problem: {problem}
Solution: {solution}
"""
        return UserError(error_message)
