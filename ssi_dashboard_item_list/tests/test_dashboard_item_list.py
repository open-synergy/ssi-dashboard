# Copyright 2026 OpenSynergy Indonesia
# Copyright 2026 PT. Simetri Sinergi Indonesia
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from odoo_yaml_test import YamlTransactionCase
from psycopg2 import IntegrityError

from odoo.tests import tagged
from odoo.tools import mute_logger


@tagged("post_install", "-at_install")
class TestDashboardItemList(YamlTransactionCase):
    def test_dashboard_item_list(self):
        self.run_yaml_scenario("test_data_dashboard_item_list.yaml")

    def test_prepare_render_payload_list_columns_ordered_by_sequence(self):
        """Python murni — P3: urutan pasangan 'key'/'name' pada 'columns'
        beserta isi baris.

        `action: call` YAML membuang nilai balik method (L-01), dan
        perbandingan YAML berbasis `set` tidak bisa menegakkan urutan
        (L-06, P3) — di sini urutan `columns` (dibangun dari `column_ids`
        menurut `sequence`, bukan urutan pembuatan) dan isi `rows` diuji
        langsung atas dict yang dikembalikan `_prepare_render_payload()`.
        """
        data_source = self.env["dashboard.data_source"].create(
            {
                "name": "Partners",
                "code": "DASH-LIST-PY-DS-01",
                "type": "orm",
                "model_id": self.env.ref("base.model_res_partner").id,
            }
        )
        dashboard = self.env["dashboard.dashboard"].create(
            {"name": "List Dashboard", "code": "DASH-LIST-PY-01"}
        )
        item = self.env["dashboard.item"].create(
            {
                "name": "Top Partners",
                "dashboard_id": dashboard.id,
                "type": "list",
                "data_source_id": data_source.id,
                "column_ids": [
                    (0, 0, {"key": "amount", "name": "Amount", "sequence": 20}),
                    (0, 0, {"key": "name", "name": "Name", "sequence": 10}),
                ],
            }
        )

        payload = item._prepare_render_payload()

        self.assertIn("columns", payload)
        self.assertIn("rows", payload)
        self.assertEqual(payload["list_mode"], "flat")
        self.assertEqual(payload["page_size"], 10)
        self.assertNotIn("config", payload)
        self.assertEqual(
            payload["columns"],
            [
                {"key": "name", "name": "Name", "column_type": "text"},
                {"key": "amount", "name": "Amount", "column_type": "text"},
            ],
        )

    def test_prepare_render_payload_list_missing_column_key_is_none(self):
        """Python murni — P3: isi baris saat sumber data tidak punya salah
        satu 'key' kolom.

        Sama seperti test di atas (L-01/L-06): isi `rows` hanya bisa
        diperiksa lewat nilai balik method. Baris sumber di sini sengaja
        tidak mempunyai kunci 'amount' sama sekali.
        """
        data_source = self.env["dashboard.data_source"].create(
            {
                "name": "Partners",
                "code": "DASH-LIST-PY-DS-02",
                "type": "orm",
                "model_id": self.env.ref("base.model_res_partner").id,
            }
        )
        dashboard = self.env["dashboard.dashboard"].create(
            {"name": "List Dashboard 2", "code": "DASH-LIST-PY-02"}
        )
        item = self.env["dashboard.item"].create(
            {
                "name": "Partner Names",
                "dashboard_id": dashboard.id,
                "type": "list",
                "data_source_id": data_source.id,
                "column_ids": [
                    (0, 0, {"key": "name", "name": "Name"}),
                    (0, 0, {"key": "amount", "name": "Amount"}),
                ],
            }
        )
        rows = [{"name": "Alpha"}]

        payload = item._prepare_render_payload_list({"data": rows})

        self.assertEqual(payload["rows"], [{"name": "Alpha", "amount": None}])

    @mute_logger("odoo.sql_db")
    def test_column_key_must_be_unique_per_item(self):
        """Python murni — pemicu P5 (L-22: `psycopg2.IntegrityError` di
        luar 12 tipe `expect_error`).

        `dashboard.item.column._item_id_key_uniq` adalah `models.Constraint`
        tingkat DB (UNIQUE(item_id, key)); `expect_error` YAML tidak bisa
        menangkap `psycopg2.IntegrityError` (L-22). `mute_logger` membungkam
        baris ERROR PostgreSQL yang NORMAL muncul di sini, agar
        `oca_checklog_odoo` tidak menggagalkan CI walau test-nya sendiri
        lulus.
        """
        data_source = self.env["dashboard.data_source"].create(
            {
                "name": "Partners",
                "code": "DASH-LIST-PY-DS-03",
                "type": "orm",
                "model_id": self.env.ref("base.model_res_partner").id,
            }
        )
        dashboard = self.env["dashboard.dashboard"].create(
            {"name": "List Dashboard 3", "code": "DASH-LIST-PY-03"}
        )
        item = self.env["dashboard.item"].create(
            {
                "name": "Duplicate Key List",
                "dashboard_id": dashboard.id,
                "type": "list",
                "data_source_id": data_source.id,
                "column_ids": [(0, 0, {"key": "name", "name": "Name"})],
            }
        )
        with self.assertRaises(IntegrityError):
            with self.env.cr.savepoint():
                self.env["dashboard.item.column"].create(
                    {
                        "item_id": item.id,
                        "key": "name",
                        "name": "Name Again",
                    }
                )
