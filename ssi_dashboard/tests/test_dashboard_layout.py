# Copyright 2026 OpenSynergy Indonesia
# Copyright 2026 PT. Simetri Sinergi Indonesia
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from odoo_yaml_test import YamlTransactionCase
from psycopg2 import IntegrityError

from odoo.exceptions import UserError
from odoo.tests import tagged
from odoo.tools import mute_logger


@tagged("post_install", "-at_install")
class TestDashboardLayout(YamlTransactionCase):
    def test_dashboard_layout(self):
        self.run_yaml_scenario("test_data_dashboard_layout.yaml")

    def _create_partner_data_source(self, code):
        partner_model = self.env.ref("base.model_res_partner")
        return self.env["dashboard.data_source"].create(
            {
                "name": "Partners",
                "code": code,
                "type": "orm",
                "model_id": partner_model.id,
            }
        )

    def test_dashboard_without_layout_payload_has_empty_layouts(self):
        """Python murni — pemicu P1 (L-01, L-02).

        Kriteria Penerimaan: dashboard tanpa `layout_ids` dirender dengan
        `layouts` berisi list kosong dan `active_layout_id` bernilai
        `False`. Nilai balik method di-assert, jadi tidak bisa lewat
        YAML (L-01, L-02).
        """
        dashboard = self.env["dashboard.dashboard"].create(
            {"name": "No Layout Dashboard", "code": "DASH-LAYOUT-PAYLOAD-NONE-01"}
        )
        payload = dashboard.get_dashboard_payload()
        self.assertEqual(payload["layouts"], [])
        self.assertFalse(payload["active_layout_id"])

    def test_get_dashboard_payload_without_layout_id_uses_default_layout(self):
        """Python murni — pemicu P1 (L-01, L-02).

        Kriteria Penerimaan: `get_dashboard_payload()` tanpa `layout_id`
        memakai tata letak ber-`is_default`. Nilai balik method
        di-assert, jadi tidak bisa lewat YAML (L-01, L-02).
        """
        dashboard = self.env["dashboard.dashboard"].create(
            {"name": "Two Layouts Dashboard", "code": "DASH-LAYOUT-PAYLOAD-DEFAULT-01"}
        )
        self.env["dashboard.layout"].create(
            {
                "name": "Branch Manager",
                "dashboard_id": dashboard.id,
                "sequence": 10,
            }
        )
        default_layout = self.env["dashboard.layout"].create(
            {
                "name": "Executive",
                "dashboard_id": dashboard.id,
                "sequence": 20,
                "is_default": True,
            }
        )
        payload = dashboard.get_dashboard_payload()
        self.assertEqual(payload["active_layout_id"], default_layout.id)
        self.assertEqual(
            sorted(entry["name"] for entry in payload["layouts"]),
            ["Branch Manager", "Executive"],
        )

    def test_get_dashboard_payload_with_explicit_layout_id(self):
        """Python murni — pemicu P1 (L-01, L-02).

        Melengkapi test di atas: memilih `layout_id` secara eksplisit
        harus mengalahkan tata letak ber-`is_default`. Nilai balik
        method di-assert (L-01, L-02).
        """
        dashboard = self.env["dashboard.dashboard"].create(
            {"name": "Two Layouts Dashboard", "code": "DASH-LAYOUT-PAYLOAD-PICK-01"}
        )
        self.env["dashboard.layout"].create(
            {
                "name": "Executive",
                "dashboard_id": dashboard.id,
                "is_default": True,
            }
        )
        other_layout = self.env["dashboard.layout"].create(
            {
                "name": "Branch Manager",
                "dashboard_id": dashboard.id,
            }
        )
        payload = dashboard.get_dashboard_payload(layout_id=other_layout.id)
        self.assertEqual(payload["active_layout_id"], other_layout.id)

    def test_item_without_position_row_still_renders_with_base_coordinates(self):
        """Python murni — pemicu P1 (L-01, L-02).

        Kriteria Penerimaan: item tanpa baris posisi pada tata letak
        terpilih tetap muncul di payload, memakai koordinat dasar
        `dashboard.item`. Nilai balik method di-assert (L-01, L-02).
        """
        data_source = self._create_partner_data_source("DASH-LAYOUT-NOPOS-DS-01")
        dashboard = self.env["dashboard.dashboard"].create(
            {"name": "Partial Layout Dashboard", "code": "DASH-LAYOUT-NOPOS-01"}
        )
        item_with_position = self.env["dashboard.item"].create(
            {
                "name": "Item With Position",
                "dashboard_id": dashboard.id,
                "type": "placeholder",
                "data_source_id": data_source.id,
                "column_start": 0,
                "row_start": 0,
                "column_width": 4,
                "row_height": 1,
            }
        )
        item_without_position = self.env["dashboard.item"].create(
            {
                "name": "Item Without Position",
                "dashboard_id": dashboard.id,
                "type": "placeholder",
                "data_source_id": data_source.id,
                "column_start": 4,
                "row_start": 0,
                "column_width": 3,
                "row_height": 2,
            }
        )
        layout = self.env["dashboard.layout"].create(
            {
                "name": "Executive",
                "dashboard_id": dashboard.id,
                "is_default": True,
                "position_ids": [
                    (
                        0,
                        0,
                        {
                            "item_id": item_with_position.id,
                            "column_start": 8,
                            "row_start": 1,
                            "column_width": 4,
                            "row_height": 3,
                        },
                    )
                ],
            }
        )
        payload = dashboard.get_dashboard_payload(layout_id=layout.id)
        items_by_id = {item["id"]: item for item in payload["items"]}
        self.assertEqual(items_by_id[item_with_position.id]["column_start"], 8)
        self.assertEqual(items_by_id[item_with_position.id]["row_start"], 1)
        self.assertEqual(items_by_id[item_with_position.id]["column_width"], 4)
        self.assertEqual(items_by_id[item_with_position.id]["row_height"], 3)
        # No position row for this item on the selected layout — falls
        # back to its own base dashboard.item coordinates, never hidden.
        self.assertIn(item_without_position.id, items_by_id)
        self.assertEqual(items_by_id[item_without_position.id]["column_start"], 4)
        self.assertEqual(items_by_id[item_without_position.id]["row_start"], 0)
        self.assertEqual(items_by_id[item_without_position.id]["column_width"], 3)
        self.assertEqual(items_by_id[item_without_position.id]["row_height"], 2)

    def test_save_layout_with_layout_id_writes_position_not_item(self):
        """Python murni — pemicu P1 (L-01, L-02).

        Kriteria Penerimaan: `save_layout()` dengan `layout_id` menulis
        ke `dashboard.layout.position`, bukan ke `dashboard.item`. Nilai
        balik method (harus `True`) dan field yang benar-benar tertulis
        hanya bisa diverifikasi lewat `action: call`+assert Python
        (L-01, L-02). Berjalan sebagai `self.env.user` bawaan
        `TransactionCase` (OdooBot/uid=1), anggota `group_dashboard_admin`
        lewat `security/res_groups/dashboard.xml`.
        """
        data_source = self._create_partner_data_source("DASH-LAYOUT-SAVE-DS-01")
        dashboard = self.env["dashboard.dashboard"].create(
            {"name": "Save Layout Dashboard", "code": "DASH-LAYOUT-SAVE-01"}
        )
        item = self.env["dashboard.item"].create(
            {
                "name": "Item A",
                "dashboard_id": dashboard.id,
                "type": "placeholder",
                "data_source_id": data_source.id,
                "column_start": 0,
                "row_start": 0,
                "column_width": 4,
                "row_height": 1,
            }
        )
        layout = self.env["dashboard.layout"].create(
            {"name": "Executive", "dashboard_id": dashboard.id}
        )
        result = dashboard.save_layout(
            [
                {
                    "id": item.id,
                    "column_start": 6,
                    "row_start": 2,
                    "column_width": 5,
                    "row_height": 3,
                }
            ],
            layout_id=layout.id,
        )
        self.assertTrue(result)
        # The base dashboard.item coordinates stay untouched.
        self.assertEqual(item.column_start, 0)
        self.assertEqual(item.row_start, 0)
        self.assertEqual(item.column_width, 4)
        self.assertEqual(item.row_height, 1)
        # A dashboard.layout.position row was created instead.
        position = layout.position_ids.filtered(lambda p: p.item_id == item)
        self.assertTrue(position)
        self.assertEqual(position.column_start, 6)
        self.assertEqual(position.row_start, 2)
        self.assertEqual(position.column_width, 5)
        self.assertEqual(position.row_height, 3)

    def test_save_layout_with_layout_id_updates_existing_position(self):
        """Python murni — pemicu P1 (L-01, L-02).

        Melengkapi test di atas: memanggil `save_layout` dua kali dengan
        `layout_id` yang sama untuk item yang sama harus menulis ulang
        baris `dashboard.layout.position` yang sudah ada, bukan membuat
        duplikat (yang akan ditolak `_dashboard_layout_position_layout_
        item_uniq`). Nilai balik/field hasil hanya bisa diverifikasi
        lewat assert Python (L-01, L-02).
        """
        data_source = self._create_partner_data_source("DASH-LAYOUT-SAVE-UPD-DS-01")
        dashboard = self.env["dashboard.dashboard"].create(
            {"name": "Save Layout Update Dashboard", "code": "DASH-LAYOUT-SAVE-UPD-01"}
        )
        item = self.env["dashboard.item"].create(
            {
                "name": "Item A",
                "dashboard_id": dashboard.id,
                "type": "placeholder",
                "data_source_id": data_source.id,
            }
        )
        layout = self.env["dashboard.layout"].create(
            {"name": "Executive", "dashboard_id": dashboard.id}
        )
        layout_entry = {
            "id": item.id,
            "column_start": 1,
            "row_start": 1,
            "column_width": 3,
            "row_height": 1,
        }
        dashboard.save_layout([layout_entry], layout_id=layout.id)
        layout_entry_updated = dict(layout_entry, column_start=9, row_start=5)
        dashboard.save_layout([layout_entry_updated], layout_id=layout.id)
        self.assertEqual(len(layout.position_ids), 1)
        self.assertEqual(layout.position_ids.column_start, 9)
        self.assertEqual(layout.position_ids.row_start, 5)

    def test_save_layout_with_unknown_layout_id_raises_user_error(self):
        """Python murni — pemicu P1 (L-01, L-02).

        `save_layout` melempar `UserError` lewat `action: call` biasa
        secara teknis mungkin, tapi nilai baliknya (tidak ada — method
        harus gagal sebelum menulis apa pun) hanya bisa dipastikan lewat
        `assertRaises` di Python, karena skenario ini butuh dua
        dashboard berbeda dirakit terprogram sebelum memanggilnya
        (L-01, L-02, P10).
        """
        data_source = self._create_partner_data_source("DASH-LAYOUT-BADID-DS-01")
        dashboard = self.env["dashboard.dashboard"].create(
            {"name": "Save Layout Bad Id Dashboard", "code": "DASH-LAYOUT-BADID-01"}
        )
        item = self.env["dashboard.item"].create(
            {
                "name": "Item A",
                "dashboard_id": dashboard.id,
                "type": "placeholder",
                "data_source_id": data_source.id,
            }
        )
        other_dashboard = self.env["dashboard.dashboard"].create(
            {"name": "Other Dashboard", "code": "DASH-LAYOUT-BADID-OTHER-01"}
        )
        foreign_layout = self.env["dashboard.layout"].create(
            {"name": "Foreign", "dashboard_id": other_dashboard.id}
        )
        with self.assertRaises(UserError):
            dashboard.save_layout(
                [
                    {
                        "id": item.id,
                        "column_start": 0,
                        "row_start": 0,
                        "column_width": 4,
                        "row_height": 1,
                    }
                ],
                layout_id=foreign_layout.id,
            )

    def test_duplicate_layout_name_on_same_dashboard_raises_integrity_error(self):
        """Python murni — pemicu P5 (L-22).

        `_dashboard_layout_dashboard_name_uniq` memakai `models.
        Constraint` dengan `UNIQUE(dashboard_id, name)`, ditegakkan
        lewat constraint database asli. Melanggarnya melempar
        `psycopg2.errors.UniqueViolation` (subclass `psycopg2.
        IntegrityError`), tipe yang tidak termasuk 12 tipe yang dikenali
        `expect_error` (L-22), sehingga tidak bisa diuji lewat YAML.
        `mute_logger` membungkam log ERROR `odoo.sql_db` normal saat
        Postgres menolak query ini — errornya memang diharapkan dan
        sudah ditangkap lewat `assertRaises`.
        """
        dashboard = self.env["dashboard.dashboard"].create(
            {"name": "Duplicate Layout Dashboard", "code": "DASH-LAYOUT-DUP-01"}
        )
        self.env["dashboard.layout"].create(
            {"name": "Executive", "dashboard_id": dashboard.id}
        )
        with mute_logger("odoo.sql_db"), self.assertRaises(IntegrityError):
            with self.env.cr.savepoint():
                self.env["dashboard.layout"].create(
                    {"name": "Executive", "dashboard_id": dashboard.id}
                )

    def test_duplicate_position_layout_item_raises_integrity_error(self):
        """Python murni — pemicu P5 (L-22).

        Sama seperti di atas, tapi untuk `_dashboard_layout_position_
        layout_item_uniq` (`UNIQUE(layout_id, item_id)`) pada
        `dashboard.layout.position` — `psycopg2.IntegrityError` di luar
        12 tipe `expect_error` (L-22).
        """
        data_source = self._create_partner_data_source("DASH-LAYOUT-POSDUP-DS-01")
        dashboard = self.env["dashboard.dashboard"].create(
            {"name": "Duplicate Position Dashboard", "code": "DASH-LAYOUT-POSDUP-01"}
        )
        item = self.env["dashboard.item"].create(
            {
                "name": "Item A",
                "dashboard_id": dashboard.id,
                "type": "placeholder",
                "data_source_id": data_source.id,
            }
        )
        layout = self.env["dashboard.layout"].create(
            {"name": "Executive", "dashboard_id": dashboard.id}
        )
        self.env["dashboard.layout.position"].create(
            {"layout_id": layout.id, "item_id": item.id}
        )
        with mute_logger("odoo.sql_db"), self.assertRaises(IntegrityError):
            with self.env.cr.savepoint():
                self.env["dashboard.layout.position"].create(
                    {"layout_id": layout.id, "item_id": item.id}
                )
