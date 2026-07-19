# Copyright 2026 OpenSynergy Indonesia
# Copyright 2026 PT. Simetri Sinergi Indonesia
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
import requests

from odoo import fields, models
from odoo.exceptions import UserError

_DEFAULT_API_TIMEOUT = 10


class DashboardDataSource(models.Model):
    """Extends `dashboard.data_source` with the 'api' type: fetches rows
    from an HTTP JSON endpoint. Adds no field beyond the selection value
    plus the endpoint/auth/payload configuration this type reads — the
    dispatcher itself stays owned by `ssi_dashboard`."""

    _name = "dashboard.data_source"
    _inherit = [
        "dashboard.data_source",
    ]

    type = fields.Selection(
        selection_add=[
            ("api", "REST API"),
        ],
        ondelete={"api": "set default"},
    )
    api_url = fields.Char(
        string="API URL",
        help="Full HTTP(S) endpoint to call. Only used when 'Type' is "
        "'REST API' (api).",
    )
    api_method = fields.Selection(
        string="API Method",
        selection=[
            ("get", "GET"),
            ("post", "POST"),
        ],
        default="get",
        help="HTTP method used to call 'API URL'. Only used when 'Type' "
        "is 'REST API' (api).",
    )
    api_auth_type = fields.Selection(
        string="API Authentication",
        selection=[
            ("none", "None"),
            ("basic", "Basic"),
            ("bearer", "Bearer Token"),
            ("header", "Custom Header"),
        ],
        default="none",
        help="How 'API URL' is authenticated. Only used when 'Type' is "
        "'REST API' (api).",
    )
    api_username = fields.Char(
        string="API Username",
        help="Username sent as HTTP Basic Auth. Only used when 'API "
        "Authentication' is 'Basic'.",
    )
    api_password = fields.Char(
        string="API Password",
        groups="ssi_dashboard.group_dashboard_admin",
        help="Password sent as HTTP Basic Auth. Readable and editable "
        "only by the Dashboard Administrator group. Only used when "
        "'API Authentication' is 'Basic'.",
    )
    api_token = fields.Char(
        string="API Token",
        groups="ssi_dashboard.group_dashboard_admin",
        help="Token sent as an 'Authorization: Bearer <token>' header, or "
        "as the value of 'API Auth Header' when 'API Authentication' is "
        "'Custom Header'. Readable and editable only by the Dashboard "
        "Administrator group.",
    )
    api_auth_header = fields.Char(
        string="API Auth Header",
        help="Name of the HTTP header carrying 'API Token'. Only used "
        "when 'API Authentication' is 'Custom Header'.",
    )
    api_payload = fields.Text(
        string="API Payload",
        help="JSON body sent with the request. Only used when 'API Method' is 'POST'.",
    )
    api_result_path = fields.Char(
        string="API Result Path",
        help="Dotted path to the list of rows inside the JSON response "
        "body (e.g. 'data.rows'). Leave empty when the response body "
        "itself is the list of rows.",
    )
    api_timeout = fields.Integer(
        string="API Timeout (s)",
        default=_DEFAULT_API_TIMEOUT,
        help="Number of seconds to wait for 'API URL' to respond before "
        "the request fails with a timeout error.",
    )

    def _fetch_data_api(self, item):
        """Fetch data for the 'api' data source type.

        Calls :attr:`api_url` over HTTP, optionally authenticated, and
        turns its JSON response into the list of dict this method's
        contract promises. Every failure mode — missing URL, connection
        error, timeout, HTTP status >= 400, a response that is not valid
        JSON, an :attr:`api_result_path` that does not resolve, or a
        final result that is not a list — is raised as a readable
        ``UserError``. See :meth:`_api_error` for the guarantee that
        those messages never include :attr:`api_password`/:attr:`api_token`.

        :param item: ``dashboard.item`` record requesting the data.
        :return: list of dict, the rows found at :attr:`api_result_path`
            (or at the response root when :attr:`api_result_path` is
            empty).
        :rtype: list
        :raises UserError: see above.
        """
        self.ensure_one()
        if not self.api_url:
            raise self._api_error(
                "Data source type is 'api' but no 'API URL' is configured",
                "Set the 'API URL' field on this data source",
            )
        response_body = self._api_request()
        result = self._resolve_api_result_path(response_body)
        if not isinstance(result, list):
            raise self._api_error(
                "The data found at 'API Result Path' is not a list",
                "Set 'API Result Path' to the dotted path of a JSON "
                "array in the response, or leave it empty when the "
                "response body itself is a JSON array",
            )
        return result

    def _api_request(self):
        """Call :attr:`api_url` and return its parsed JSON body.

        :return: the parsed JSON response body (any JSON type — callers
            are responsible for shaping it into the final list).
        :raises UserError: on connection error, timeout, HTTP status
            >= 400, or a response body that is not valid JSON.
        """
        self.ensure_one()
        request_kwargs = {
            "headers": self._get_api_headers(),
            "auth": self._get_api_auth(),
        }
        if self.api_method == "post":
            request_kwargs["data"] = self.api_payload or None
        try:
            response = requests.request(
                self.api_method or "get",
                self.api_url,
                timeout=self.api_timeout or _DEFAULT_API_TIMEOUT,
                **request_kwargs,
            )
        except requests.exceptions.Timeout as request_error:
            raise self._api_error(
                f"Request to 'API URL' timed out after "
                f"{self.api_timeout or _DEFAULT_API_TIMEOUT} second(s)",
                "Check that the endpoint is reachable, or increase 'API Timeout (s)'",
            ) from request_error
        except requests.exceptions.RequestException as request_error:
            raise self._api_error(
                f"Could not connect to 'API URL' ({request_error.__class__.__name__})",
                "Check that 'API URL' is correct and the endpoint is reachable",
            ) from request_error
        if response.status_code >= 400:
            raise self._api_error(
                f"'API URL' responded with HTTP status {response.status_code}",
                "Check 'API URL', 'API Method' and authentication settings",
            )
        try:
            return response.json()
        except ValueError as parse_error:
            raise self._api_error(
                "The response from 'API URL' is not valid JSON",
                "Make the endpoint return a JSON body, or fix 'API URL'",
            ) from parse_error

    def _resolve_api_result_path(self, response_body):
        """Walk :attr:`api_result_path` inside `response_body`.

        :param response_body: the parsed JSON response, as returned by
            :meth:`_api_request`.
        :return: the value found at :attr:`api_result_path`, or
            `response_body` unchanged when :attr:`api_result_path` is
            empty.
        :raises UserError: when a segment of :attr:`api_result_path` is
            not found (the value at that point is not a dict, or does
            not have that key).
        """
        self.ensure_one()
        if not self.api_result_path:
            return response_body
        value = response_body
        for segment in self.api_result_path.split("."):
            if not isinstance(value, dict) or segment not in value:
                raise self._api_error(
                    f"'API Result Path' segment '{segment}' was not "
                    "found in the response",
                    "Fix 'API Result Path' to match the response's JSON "
                    "structure, or leave it empty when the response "
                    "body itself is a JSON array",
                )
            value = value[segment]
        return value

    def _get_api_auth(self):
        """Build the ``requests`` ``auth`` argument for this data source.

        Reads :attr:`api_username`/:attr:`api_password` through
        :meth:`~odoo.models.BaseModel.sudo` — those fields are restricted
        at the ORM level to ``ssi_dashboard.group_dashboard_admin`` so
        they stay invisible to regular dashboard users (see their
        ``groups`` attribute), but the fetch itself still needs the
        value to authenticate the request on the current user's behalf.

        :return: ``(username, password)`` tuple when 'API Authentication'
            is 'Basic', ``None`` otherwise.
        :rtype: tuple or None
        """
        self.ensure_one()
        if self.api_auth_type != "basic":
            return None
        secure_self = self.sudo()
        return (secure_self.api_username or "", secure_self.api_password or "")

    def _get_api_headers(self):
        """Build the extra HTTP headers for this data source's request.

        See :meth:`_get_api_auth` for why :attr:`api_token` is read
        through ``sudo()``.

        :return: dict of extra headers, empty when 'API Authentication'
            is 'None' or 'Basic'.
        :rtype: dict
        """
        self.ensure_one()
        if self.api_auth_type == "bearer":
            return {"Authorization": f"Bearer {self.sudo().api_token or ''}"}
        if self.api_auth_type == "header" and self.api_auth_header:
            return {self.api_auth_header: self.sudo().api_token or ""}
        return {}

    def _api_error(self, problem, solution):
        """Build the ``UserError`` this data source type raises on failure.

        `problem`/`solution` are always static text supplied by the
        caller (endpoint names, HTTP status codes, exception class
        names, :attr:`api_result_path` segments) — :attr:`api_password`
        and :attr:`api_token` are never interpolated into either, so the
        resulting message never leaks a credential value.

        :param problem: str, what went wrong.
        :param solution: str, how the user can fix it.
        :return: ``UserError`` ready to be raised by the caller.
        :rtype: UserError
        """
        self.ensure_one()
        error_message = f"""
Document Type: {self._description}
Context: Fetch dashboard item data from a REST API
Database ID: {self.id}
Problem: {problem}
Solution: {solution}
"""
        return UserError(error_message)
