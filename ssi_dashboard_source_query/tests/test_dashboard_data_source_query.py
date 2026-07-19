# Copyright 2026 OpenSynergy Indonesia
# Copyright 2026 PT. Simetri Sinergi Indonesia
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from odoo_yaml_test import YamlTransactionCase

from odoo.exceptions import UserError
from odoo.tests import tagged


@tagged("post_install", "-at_install")
class TestDashboardDataSourceQuery(YamlTransactionCase):
    def test_dashboard_data_source_query(self):
        self.run_yaml_scenario("test_data_dashboard_data_source_query.yaml")

    def _create_query_dashboard_item(self, code, query):
        """Create a `dashboard.dashboard` + `dashboard.item` bound to a
        `dashboard.data_source` of type `query`, used as fixture by the
        Python-only tests below (registry from `run_yaml_scenario` does
        not survive outside that method)."""
        dashboard = self.env["dashboard.dashboard"].create(
            {"name": "Query Dashboard", "code": f"{code}-DASH"}
        )
        data_source = self.env["dashboard.data_source"].create(
            {
                "name": "Query",
                "code": code,
                "type": "query",
                "query": query,
            }
        )
        item = self.env["dashboard.item"].create(
            {
                "name": "Item",
                "dashboard_id": dashboard.id,
                "type": "placeholder",
                "data_source_id": data_source.id,
            }
        )
        return data_source, item

    def test_fetch_data_query_returns_rows_as_list_of_dict(self):
        """Python murni — pemicu P1 (L-01, L-02): `action: call` di
        `odoo-yaml-test` membuang nilai balik method, dan tidak ada cara
        meng-assert sebuah ekspresi bebas seperti "baris pertama, kunci
        'value'" lewat YAML. Menguji bahwa sebuah `SELECT` sederhana
        mengembalikan `list` of `dict` berkunci nama kolom, sesuai
        kontrak `_fetch_data`.
        """
        data_source, item = self._create_query_dashboard_item(
            "DASH-QUERY-MOCK-SIMPLE-01", "SELECT 1 AS value"
        )
        result = data_source._fetch_data(item)
        self.assertEqual(result, [{"value": 1}])

    def test_fetch_data_query_uid_placeholder_is_substituted(self):
        """Python murni — pemicu P1 (L-01, L-02), lihat docstring method
        di atas. Menguji bahwa placeholder bernama `%(uid)s` terisi id
        user yang sedang menjalankan query — sekaligus bukti bahwa
        parameter diteruskan lewat `execute()` yang terparameterisasi,
        bukan digabungkan ke string query.
        """
        data_source, item = self._create_query_dashboard_item(
            "DASH-QUERY-MOCK-UID-01", "SELECT %(uid)s AS current_uid"
        )
        result = data_source._fetch_data(item)
        self.assertEqual(result, [{"current_uid": self.env.uid}])

    def test_fetch_data_query_sql_injection_payload_is_rejected(self):
        """Python murni — pemicu P1 (L-01, L-02), lihat docstring method
        di atas: kegagalan sebuah query harus tidak membatalkan
        transaksi pemanggil (`SAVEPOINT`), yang hanya bisa dibuktikan
        dengan menjalankan sebuah query yang gagal, lalu membuktikan
        `env.cr` tetap dapat dipakai sesudahnya — efek yang mustahil
        diekspresikan lewat `expect_error` YAML (yang hanya menegaskan
        error terjadi, bukan bahwa transaksi tetap sehat sesudahnya).

        Payload `1=1; --` dilewatkan sebagai isi query itu sendiri (bukan
        sebagai parameter) untuk membuktikan mitigasi titik-koma
        menahannya sebelum mencapai database, dan bahwa kursor tetap bisa
        dipakai sesudahnya karena kegagalan dibatasi ke `SAVEPOINT`.
        """
        data_source, item = self._create_query_dashboard_item(
            "DASH-QUERY-MOCK-INJECT-01",
            "SELECT 1 AS value WHERE 1=1; DROP TABLE res_partner; --",
        )
        with self.assertRaises(UserError):
            data_source._fetch_data(item)
        # The savepoint must have protected the caller's transaction:
        # the cursor is still usable for a completely unrelated query.
        self.env.cr.execute("SELECT 1")
        self.assertEqual(self.env.cr.fetchone(), (1,))
        # res_partner must still exist and be queryable.
        self.env["res.partner"].search_count([])
