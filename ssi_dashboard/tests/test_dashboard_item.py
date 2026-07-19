# Copyright 2026 OpenSynergy Indonesia
# Copyright 2026 PT. Simetri Sinergi Indonesia
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
import datetime

from odoo_yaml_test import YamlTransactionCase
from psycopg2 import IntegrityError

from odoo.tests import tagged
from odoo.tools import mute_logger


@tagged("post_install", "-at_install")
class TestDashboardItem(YamlTransactionCase):
    def test_dashboard_item(self):
        self.run_yaml_scenario("test_data_dashboard_item.yaml")

    def test_get_goal_value_fixed_returns_goal_value_for_any_date(self):
        """Python murni — pemicu P1 (L-01, L-02) dan P2 (L-04).

        Nilai balik `_get_goal_value` hanya bisa diverifikasi dengan
        meng-assert hasil pemanggilan method langsung — `action: call` di
        YAML membuang nilai baliknya (L-01) dan tidak bisa meng-assert
        ekspresi bebas seperti perbandingan angka pecahan (L-02).
        `assertAlmostEqual` dipakai karena 'Goal Value' adalah `Float`
        (P2/L-04): 'Goal Type' 'Fixed Value' harus mengembalikan
        'Goal Value' untuk tanggal apa pun, termasuk dua tanggal yang
        jauh berbeda.
        """
        data_source = self.env["dashboard.data_source"].create(
            {
                "name": "Partners",
                "code": "DASH-ITEM-GOAL-FIXED-DS-01",
                "type": "orm",
                "model_id": self.env["ir.model"]._get("res.partner").id,
            }
        )
        dashboard = self.env["dashboard.dashboard"].create(
            {"name": "Goal Fixed Dashboard", "code": "DASH-ITEM-GOAL-FIXED-01"}
        )
        item = self.env["dashboard.item"].create(
            {
                "name": "Item Fixed Goal",
                "dashboard_id": dashboard.id,
                "type": "placeholder",
                "data_source_id": data_source.id,
                "goal_type": "fixed",
                "goal_value": 1000.0,
            }
        )
        self.assertAlmostEqual(
            item._get_goal_value(datetime.date(2026, 1, 1)), 1000.0, places=2
        )
        self.assertAlmostEqual(
            item._get_goal_value(datetime.date(2030, 12, 31)), 1000.0, places=2
        )

    def test_get_goal_value_dated_returns_matching_row_else_zero(self):
        """Python murni — pemicu P1 (L-01, L-02) dan P2 (L-04).

        Sama seperti test di atas: nilai balik `_get_goal_value` hanya
        bisa diverifikasi lewat pemanggilan method langsung (L-01/L-02),
        dan hasilnya (`Float`) dibandingkan dengan `assertAlmostEqual`
        (P2/L-04). 'Goal Type' 'Dated Targets' dengan satu baris 1-31
        Januari 2026 bernilai 500 harus mengembalikan 500 untuk 15
        Januari (di dalam rentang) dan 0.0 untuk 15 Februari (di luar
        rentang, tidak ada baris yang cocok).
        """
        data_source = self.env["dashboard.data_source"].create(
            {
                "name": "Partners",
                "code": "DASH-ITEM-GOAL-DATED-DS-01",
                "type": "orm",
                "model_id": self.env["ir.model"]._get("res.partner").id,
            }
        )
        dashboard = self.env["dashboard.dashboard"].create(
            {"name": "Goal Dated Dashboard", "code": "DASH-ITEM-GOAL-DATED-01"}
        )
        item = self.env["dashboard.item"].create(
            {
                "name": "Item Dated Goal",
                "dashboard_id": dashboard.id,
                "type": "placeholder",
                "data_source_id": data_source.id,
                "goal_type": "dated",
                "goal_ids": [
                    (
                        0,
                        0,
                        {
                            "date_start": "2026-01-01",
                            "date_end": "2026-01-31",
                            "value": 500.0,
                        },
                    )
                ],
            }
        )
        self.assertAlmostEqual(
            item._get_goal_value(datetime.date(2026, 1, 15)), 500.0, places=2
        )
        self.assertAlmostEqual(
            item._get_goal_value(datetime.date(2026, 2, 15)), 0.0, places=2
        )

    def test_create_goal_date_start_after_date_end_raises_integrity_error(self):
        """Python murni — pemicu P5 (L-22).

        `dashboard.item.goal` memvalidasi `date_start <= date_end` lewat
        `models.Constraint("CHECK (date_start <= date_end)", ...)`,
        constraint tingkat database (bukan `_sql_constraints`
        Python-level lama, dan bukan `@api.constrains`). Membuat baris
        dengan `date_start` sesudah `date_end` melempar
        `psycopg2.errors.CheckViolation` (subclass `psycopg2.IntegrityError`),
        tipe yang tidak termasuk 12 tipe yang dikenali `expect_error`
        (L-22), sehingga tidak bisa diuji lewat YAML. `mute_logger`
        membungkam log ERROR `odoo.sql_db` yang normal muncul saat
        Postgres menolak query ini.
        """
        data_source = self.env["dashboard.data_source"].create(
            {
                "name": "Partners",
                "code": "DASH-ITEM-GOAL-CHECK-DS-01",
                "type": "orm",
                "model_id": self.env["ir.model"]._get("res.partner").id,
            }
        )
        dashboard = self.env["dashboard.dashboard"].create(
            {"name": "Goal Check Dashboard", "code": "DASH-ITEM-GOAL-CHECK-01"}
        )
        with mute_logger("odoo.sql_db"), self.assertRaises(IntegrityError):
            with self.env.cr.savepoint():
                self.env["dashboard.item"].create(
                    {
                        "name": "Item Goal Check",
                        "dashboard_id": dashboard.id,
                        "type": "placeholder",
                        "data_source_id": data_source.id,
                        "goal_type": "dated",
                        "goal_ids": [
                            (
                                0,
                                0,
                                {
                                    "date_start": "2026-01-31",
                                    "date_end": "2026-01-01",
                                    "value": 500.0,
                                },
                            )
                        ],
                    }
                )

    def test_prepare_render_payload_excludes_config_key(self):
        """Python murni — pemicu P1 (L-01, L-02).

        `_prepare_render_payload` diuji lewat nilai balik method (dict
        payload render), bukan efek sampingnya pada record. `action: call`
        di YAML membuang nilai balik method (L-01) dan sisi actual sebuah
        assert selalu berupa dotted `getattr` pada record (L-02) — isi
        dict hasil method tidak bisa diperiksa lewat YAML sama sekali.

        Ini juga bukti langsung Kriteria Penerimaan #18: kunci 'config'
        sudah tidak ada di payload dasar, sementara field `config` pada
        `dashboard.item` itu sendiri tetap ada di model (tidak disentuh
        issue ini) dan kunci 'active' baru ikut ditambahkan.
        """
        data_source = self.env["dashboard.data_source"].create(
            {
                "name": "Partners",
                "code": "DASH-ITEM-PAYLOAD-DS-01",
                "type": "orm",
                "model_id": self.env["ir.model"]._get("res.partner").id,
            }
        )
        dashboard = self.env["dashboard.dashboard"].create(
            {"name": "Payload Item Dashboard", "code": "DASH-ITEM-PAYLOAD-01"}
        )
        item = self.env["dashboard.item"].create(
            {
                "name": "Item A",
                "dashboard_id": dashboard.id,
                "type": "placeholder",
                "data_source_id": data_source.id,
            }
        )
        payload = item._prepare_render_payload()
        self.assertIn("active", payload)
        self.assertTrue(payload["active"])
        self.assertNotIn("config", payload)

    def test_prepare_render_payload_excludes_comparison_data_when_none(self):
        """Python murni — pemicu P1 (L-01, L-02).

        Sama seperti test di atas: isi dict payload hanya bisa diperiksa
        lewat nilai balik method (L-01/L-02). `comparison` defaultnya
        `none`, jadi payload tidak boleh memuat kunci `comparison_data`
        sama sekali — bukan hanya `False`/kosong — sehingga tipe item
        yang tidak butuh perbandingan tidak terkena biaya query
        tambahan (Kriteria Penerimaan #1).
        """
        data_source = self.env["dashboard.data_source"].create(
            {
                "name": "Partners",
                "code": "DASH-ITEM-COMPARISON-NONE-DS-01",
                "type": "orm",
                "model_id": self.env["ir.model"]._get("res.partner").id,
            }
        )
        dashboard = self.env["dashboard.dashboard"].create(
            {"name": "Comparison None Dashboard", "code": "DASH-ITEM-COMPNONE-01"}
        )
        item = self.env["dashboard.item"].create(
            {
                "name": "Item A",
                "dashboard_id": dashboard.id,
                "type": "placeholder",
                "data_source_id": data_source.id,
            }
        )
        payload = item._prepare_render_payload()
        self.assertNotIn("comparison_data", payload)

    def test_prepare_render_payload_includes_comparison_data_when_active(self):
        """Python murni — pemicu P1 (L-01, L-02).

        Sama seperti test di atas. `comparison` = `previous_period`
        harus membuat payload memuat kunci `comparison_data` berisi
        `list` yang panjangnya sama dengan jumlah rentang pembanding
        dari `_prepare_comparison_date_range` (satu untuk
        `previous_period`), masing-masing berupa `list` baris data
        (di sini kosong karena tidak ada `res.partner` yang cocok
        dengan rentang tanggal pembanding).
        """
        currency_rate_model = self.env["ir.model"]._get("res.currency.rate")
        date_field = self.env["ir.model.fields"].search(
            [("model", "=", "res.currency.rate"), ("name", "=", "name")],
            limit=1,
        )
        data_source = self.env["dashboard.data_source"].create(
            {
                "name": "Rates",
                "code": "DASH-ITEM-COMPARISON-ACTIVE-DS-01",
                "type": "orm",
                "model_id": currency_rate_model.id,
                "date_field_id": date_field.id,
                "date_range": "custom",
                "date_start": "2026-01-01",
                "date_end": "2026-01-31",
                "comparison": "previous_period",
            }
        )
        dashboard = self.env["dashboard.dashboard"].create(
            {"name": "Comparison Active Dashboard", "code": "DASH-ITEM-COMPACTIVE-01"}
        )
        item = self.env["dashboard.item"].create(
            {
                "name": "Item A",
                "dashboard_id": dashboard.id,
                "type": "placeholder",
                "data_source_id": data_source.id,
            }
        )
        payload = item._prepare_render_payload()
        self.assertIn("comparison_data", payload)
        self.assertEqual(len(payload["comparison_data"]), 1)
        self.assertIsInstance(payload["comparison_data"][0], list)

    def test_prepare_render_payload_excludes_goal_key_when_none(self):
        """Python murni — pemicu P1 (L-01, L-02).

        Sama seperti test payload lain di atas: isi dict payload hanya
        bisa diperiksa lewat nilai balik method (L-01/L-02). 'Goal Type'
        defaultnya 'none', jadi payload tidak boleh memuat kunci 'goal'
        sama sekali — bukan hanya `0.0`/kosong — sehingga item tanpa
        target tidak terkena biaya perhitungan tambahan.
        """
        data_source = self.env["dashboard.data_source"].create(
            {
                "name": "Partners",
                "code": "DASH-ITEM-GOALKEY-NONE-DS-01",
                "type": "orm",
                "model_id": self.env["ir.model"]._get("res.partner").id,
            }
        )
        dashboard = self.env["dashboard.dashboard"].create(
            {"name": "Goal Key None Dashboard", "code": "DASH-ITEM-GOALKEY-NONE-01"}
        )
        item = self.env["dashboard.item"].create(
            {
                "name": "Item A",
                "dashboard_id": dashboard.id,
                "type": "placeholder",
                "data_source_id": data_source.id,
            }
        )
        payload = item._prepare_render_payload()
        self.assertNotIn("goal", payload)

    def test_prepare_render_payload_includes_goal_key_when_fixed(self):
        """Python murni — pemicu P1 (L-01, L-02) dan P2 (L-04).

        Sama seperti test di atas: kunci 'goal' hanya bisa diperiksa
        lewat nilai balik method (L-01/L-02), dan nilainya (`Float`)
        dibandingkan dengan `assertAlmostEqual` (P2/L-04). 'Goal Type'
        'Fixed Value' harus membuat payload memuat kunci 'goal' berisi
        'Goal Value'.
        """
        data_source = self.env["dashboard.data_source"].create(
            {
                "name": "Partners",
                "code": "DASH-ITEM-GOALKEY-FIXED-DS-01",
                "type": "orm",
                "model_id": self.env["ir.model"]._get("res.partner").id,
            }
        )
        dashboard = self.env["dashboard.dashboard"].create(
            {"name": "Goal Key Fixed Dashboard", "code": "DASH-ITEM-GOALKEY-FIXED-01"}
        )
        item = self.env["dashboard.item"].create(
            {
                "name": "Item A",
                "dashboard_id": dashboard.id,
                "type": "placeholder",
                "data_source_id": data_source.id,
                "goal_type": "fixed",
                "goal_value": 2500.0,
            }
        )
        payload = item._prepare_render_payload()
        self.assertIn("goal", payload)
        self.assertAlmostEqual(payload["goal"], 2500.0, places=2)
