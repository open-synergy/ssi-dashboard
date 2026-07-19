# Copyright 2026 OpenSynergy Indonesia
# Copyright 2026 PT. Simetri Sinergi Indonesia
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from unittest.mock import Mock, patch

import requests
from odoo_yaml_test import YamlTransactionCase

from odoo.exceptions import UserError
from odoo.tests import tagged


@tagged("post_install", "-at_install")
class TestDashboardDataSourceApi(YamlTransactionCase):
    def test_dashboard_data_source_api(self):
        self.run_yaml_scenario("test_data_dashboard_data_source_api.yaml")

    def _create_api_data_source(self, code, **values):
        """Create a `dashboard.data_source` of type `api`, used as fixture
        by the Python-only tests below (registry from `run_yaml_scenario`
        does not survive outside that method)."""
        vals = {
            "name": "Mocked API",
            "code": code,
            "type": "api",
            "api_url": "https://example.test/api/metrics",
        }
        vals.update(values)
        return self.env["dashboard.data_source"].create(vals)

    def test_fetch_data_api_maps_root_list_response(self):
        """Python murni — pemicu P6 (L-15): `odoo-yaml-test` tidak
        menyediakan mock/patch sama sekali, dan menguji `_fetch_data_api`
        dengan sungguhan memanggil jaringan dilarang eksplisit oleh
        skenario uji di issue ini. Menguji respons sukses berupa list
        dict di akar (tanpa `api_result_path`) dipetakan apa adanya jadi
        hasil `_fetch_data_api`.
        """
        data_source = self._create_api_data_source("DASH-API-MOCK-ROOT-01")
        mock_response = Mock(status_code=200)
        mock_response.json.return_value = [{"label": "A", "value": 1}]
        with patch("requests.request", return_value=mock_response) as mock_request:
            result = data_source._fetch_data_api(self.env["dashboard.item"])
        self.assertEqual(result, [{"label": "A", "value": 1}])
        mock_request.assert_called_once()

    def test_fetch_data_api_resolves_nested_result_path(self):
        """Python murni — pemicu P6 (L-15), lihat docstring method di
        atas. Menguji `api_result_path` bertingkat ('data.rows')
        menemukan list yang tersembunyi di dalam objek JSON.
        """
        data_source = self._create_api_data_source(
            "DASH-API-MOCK-NESTED-01", api_result_path="data.rows"
        )
        mock_response = Mock(status_code=200)
        mock_response.json.return_value = {"data": {"rows": [{"label": "B"}]}}
        with patch("requests.request", return_value=mock_response):
            result = data_source._fetch_data_api(self.env["dashboard.item"])
        self.assertEqual(result, [{"label": "B"}])

    def test_fetch_data_api_http_error_status_raises_user_error(self):
        """Python murni — pemicu P6 (L-15), lihat docstring method di
        atas. Menguji status HTTP >= 400 dilempar sebagai `UserError`
        terbaca, bukan traceback mentah.
        """
        data_source = self._create_api_data_source("DASH-API-MOCK-500-01")
        mock_response = Mock(status_code=500)
        with patch("requests.request", return_value=mock_response):
            with self.assertRaises(UserError) as error_catcher:
                data_source._fetch_data_api(self.env["dashboard.item"])
        self.assertIn("500", str(error_catcher.exception))

    def test_fetch_data_api_timeout_raises_user_error(self):
        """Python murni — pemicu P6 (L-15), lihat docstring method di
        atas. Memaksa `requests.exceptions.Timeout` dan menguji timeout
        dilempar sebagai `UserError` terbaca.
        """
        data_source = self._create_api_data_source("DASH-API-MOCK-TIMEOUT-01")
        with patch("requests.request", side_effect=requests.exceptions.Timeout()):
            with self.assertRaises(UserError):
                data_source._fetch_data_api(self.env["dashboard.item"])

    def test_fetch_data_api_invalid_json_raises_user_error(self):
        """Python murni — pemicu P6 (L-15), lihat docstring method di
        atas. Menguji respons yang bukan JSON valid dilempar sebagai
        `UserError` terbaca.
        """
        data_source = self._create_api_data_source("DASH-API-MOCK-BADJSON-01")
        mock_response = Mock(status_code=200)
        mock_response.json.side_effect = ValueError("not json")
        with patch("requests.request", return_value=mock_response):
            with self.assertRaises(UserError):
                data_source._fetch_data_api(self.env["dashboard.item"])

    def test_fetch_data_api_error_message_excludes_token(self):
        """Python murni — pemicu P4 (L-23): `message_contains` di
        `odoo-yaml-test` hanya mendukung satu substring POSITIF polos,
        tidak ada pencocokan negatif — mustahil menyatakan "pesan ini
        TIDAK boleh memuat X" lewat YAML. Memaksa kegagalan (timeout)
        pada data source yang membawa `api_token`, lalu memastikan
        pesan `UserError`-nya tidak memuat nilai token itu.
        """
        secret_token = "super-secret-token-value"  # noqa: S105
        data_source = self._create_api_data_source(
            "DASH-API-MOCK-NOLEAK-01",
            api_auth_type="bearer",
            api_token=secret_token,
        )
        with patch("requests.request", side_effect=requests.exceptions.Timeout()):
            with self.assertRaises(UserError) as error_catcher:
                data_source._fetch_data_api(self.env["dashboard.item"])
        self.assertNotIn(secret_token, str(error_catcher.exception))
