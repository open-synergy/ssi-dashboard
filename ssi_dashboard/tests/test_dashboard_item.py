# Copyright 2026 OpenSynergy Indonesia
# Copyright 2026 PT. Simetri Sinergi Indonesia
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
import datetime

from odoo_yaml_test import YamlTransactionCase
from psycopg2 import IntegrityError

from odoo.exceptions import UserError
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

    def test_prepare_render_payload_number_format_config_unit_symbol_monetary(self):
        """Python murni — pemicu P1 (L-01, L-02).

        Sama seperti test payload lain di atas: isi dict payload hanya
        bisa diperiksa lewat nilai balik method (L-01/L-02). 'Unit Type'
        'Currency' dengan 'Currency' terisi harus membuat
        `number_format_config['unit_symbol']` sama dengan simbol currency
        itu (Kriteria Penerimaan: 'unit_symbol' berisi simbol currency
        saat 'unit_type' = 'monetary').
        """
        data_source = self.env["dashboard.data_source"].create(
            {
                "name": "Partners",
                "code": "DASH-ITEM-NFC-MONETARY-DS-01",
                "type": "orm",
                "model_id": self.env["ir.model"]._get("res.partner").id,
            }
        )
        dashboard = self.env["dashboard.dashboard"].create(
            {"name": "Number Format Config Dashboard", "code": "DASH-ITEM-NFC-01"}
        )
        currency = self.env.ref("base.USD")
        item = self.env["dashboard.item"].create(
            {
                "name": "Item Monetary Unit",
                "dashboard_id": dashboard.id,
                "type": "placeholder",
                "data_source_id": data_source.id,
                "unit_type": "monetary",
                "currency_id": currency.id,
            }
        )
        payload = item._prepare_render_payload()
        self.assertIn("number_format_config", payload)
        number_format_config = payload["number_format_config"]
        self.assertEqual(number_format_config["unit_symbol"], currency.symbol)
        self.assertEqual(number_format_config["unit_type"], "monetary")
        self.assertEqual(number_format_config["multiplier"], 1.0)
        self.assertEqual(number_format_config["number_format"], "exact")
        self.assertEqual(number_format_config["precision_digits"], 2)
        self.assertEqual(number_format_config["unit_position"], "after")

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

    def test_prepare_render_payload_theme_non_custom_has_none_colors(self):
        """Python murni — pemicu P1 (L-01, L-02).

        Sama seperti test payload lain di atas: isi dict payload hanya
        bisa diperiksa lewat nilai balik method (L-01/L-02). 'Item
        Theme' 'Warning' (bukan 'custom') harus membuat
        `payload['theme']['header_color']` dan `['border_color']`
        bernilai `None` — server tidak menyalin warna, browser yang
        merujuk variabel CSS palet '--ssi-dashboard-warning' (Kriteria
        Penerimaan: tema selain 'custom' menghasilkan warna bernilai
        `None` di payload).
        """
        data_source = self.env["dashboard.data_source"].create(
            {
                "name": "Partners",
                "code": "DASH-ITEM-THEME-WARNING-DS-01",
                "type": "orm",
                "model_id": self.env["ir.model"]._get("res.partner").id,
            }
        )
        dashboard = self.env["dashboard.dashboard"].create(
            {"name": "Theme Warning Dashboard", "code": "DASH-ITEM-THEME-WARNING-01"}
        )
        item = self.env["dashboard.item"].create(
            {
                "name": "Item Warning Theme",
                "dashboard_id": dashboard.id,
                "type": "placeholder",
                "data_source_id": data_source.id,
                "item_theme": "warning",
            }
        )
        payload = item._prepare_render_payload()
        self.assertIn("theme", payload)
        self.assertEqual(payload["theme"]["name"], "warning")
        self.assertIsNone(payload["theme"]["header_color"])
        self.assertIsNone(payload["theme"]["border_color"])

    def test_prepare_render_payload_theme_custom_carries_its_own_colors(self):
        """Python murni — pemicu P1 (L-01, L-02).

        Sama seperti di atas. 'Item Theme' 'Custom Colors' dengan
        'Header Color' terisi harus membuat payload memuat warna itu
        apa adanya di `payload['theme']['header_color']`.
        """
        data_source = self.env["dashboard.data_source"].create(
            {
                "name": "Partners",
                "code": "DASH-ITEM-THEME-CUSTOM-DS-01",
                "type": "orm",
                "model_id": self.env["ir.model"]._get("res.partner").id,
            }
        )
        dashboard = self.env["dashboard.dashboard"].create(
            {"name": "Theme Custom Dashboard", "code": "DASH-ITEM-THEME-CUSTOM-01"}
        )
        item = self.env["dashboard.item"].create(
            {
                "name": "Item Custom Theme",
                "dashboard_id": dashboard.id,
                "type": "placeholder",
                "data_source_id": data_source.id,
                "item_theme": "custom",
                "item_header_color": "#ff0000",
            }
        )
        payload = item._prepare_render_payload()
        self.assertEqual(payload["theme"]["name"], "custom")
        self.assertEqual(payload["theme"]["header_color"], "#ff0000")

    def test_preview_render_payload_reflects_unsaved_vals_without_writing_db(self):
        """Python murni — pemicu P1 (L-01, L-02).

        `preview_render_payload` hanya bisa diverifikasi lewat nilai
        balik method (dict payload) — `action: call` di YAML membuang
        nilai baliknya (L-01) dan isi dict tidak bisa diperiksa lewat
        assert dotted path (L-02). Payload harus memuat 'name' dari
        'vals' yang belum disimpan, sementara record di basis data tetap
        memakai nama lamanya — membuktikan pratinjau memakai `new()` di
        atas record yang ada tanpa pernah menulis ke basis data
        (Kriteria Penerimaan: 'Nilai pada vals terpakai di payload tanpa
        tersimpan ke basis data').
        """
        data_source = self.env["dashboard.data_source"].create(
            {
                "name": "Partners",
                "code": "DASH-ITEM-PREVIEW-DS-01",
                "type": "orm",
                "model_id": self.env["ir.model"]._get("res.partner").id,
            }
        )
        dashboard = self.env["dashboard.dashboard"].create(
            {"name": "Preview Dashboard", "code": "DASH-ITEM-PREVIEW-01"}
        )
        item = self.env["dashboard.item"].create(
            {
                "name": "Old Name",
                "dashboard_id": dashboard.id,
                "type": "placeholder",
                "data_source_id": data_source.id,
            }
        )
        payload = item.preview_render_payload({"name": "Judul Baru"})
        self.assertEqual(payload["name"], "Judul Baru")
        self.assertEqual(item.name, "Old Name")
        self.assertEqual(payload["id"], item.id)

    def test_preview_render_payload_ignores_unknown_keys(self):
        """Python murni — pemicu P1 (L-01, L-02).

        Sama seperti di atas: nilai balik hanya bisa diperiksa lewat
        pemanggilan method langsung. Kunci yang bukan field
        'dashboard.item' harus diabaikan, bukan diteruskan ke ORM —
        memverifikasi Kriteria Penerimaan 'Kunci pada vals yang bukan
        field dashboard.item diabaikan'.
        """
        data_source = self.env["dashboard.data_source"].create(
            {
                "name": "Partners",
                "code": "DASH-ITEM-PREVIEW-DS-02",
                "type": "orm",
                "model_id": self.env["ir.model"]._get("res.partner").id,
            }
        )
        dashboard = self.env["dashboard.dashboard"].create(
            {"name": "Preview Dashboard", "code": "DASH-ITEM-PREVIEW-02"}
        )
        item = self.env["dashboard.item"].create(
            {
                "name": "Item A",
                "dashboard_id": dashboard.id,
                "type": "placeholder",
                "data_source_id": data_source.id,
            }
        )
        payload = item.preview_render_payload({"kunci_ngawur": 1})
        self.assertEqual(payload["name"], "Item A")

    def test_preview_render_payload_empty_vals_matches_prepare_render_payload(self):
        """Python murni — pemicu P1 (L-01, L-02).

        'vals' kosong harus menghasilkan payload yang identik dengan
        `_prepare_render_payload()` langsung — membuktikan
        `preview_render_payload` tidak mengubah bentuk payload dasar
        (Kriteria Penerimaan: '`preview_render_payload()` mengembalikan
        payload berbentuk sama dengan `_prepare_render_payload()`').
        """
        data_source = self.env["dashboard.data_source"].create(
            {
                "name": "Partners",
                "code": "DASH-ITEM-PREVIEW-DS-03",
                "type": "orm",
                "model_id": self.env["ir.model"]._get("res.partner").id,
            }
        )
        dashboard = self.env["dashboard.dashboard"].create(
            {"name": "Preview Dashboard", "code": "DASH-ITEM-PREVIEW-03"}
        )
        item = self.env["dashboard.item"].create(
            {
                "name": "Item A",
                "dashboard_id": dashboard.id,
                "type": "placeholder",
                "data_source_id": data_source.id,
            }
        )
        self.assertEqual(
            item.preview_render_payload({}), item._prepare_render_payload()
        )

    def test_prepare_render_payload_includes_allow_open_records_key(self):
        """Python murni — pemicu P1 (L-01, L-02).

        Sama seperti test payload lain di atas: isi dict payload hanya
        bisa diperiksa lewat nilai balik method (L-01/L-02). Kunci
        'allow_open_records' pada payload harus sama dengan field
        'allow_open_records' item itu sendiri (Keputusan Desain:
        'Payload item mendapat kunci allow_open_records').
        """
        data_source = self.env["dashboard.data_source"].create(
            {
                "name": "Partners",
                "code": "DASH-ITEM-AOR-PAYLOAD-DS-01",
                "type": "orm",
                "model_id": self.env["ir.model"]._get("res.partner").id,
            }
        )
        dashboard = self.env["dashboard.dashboard"].create(
            {"name": "Allow Open Records Payload Dashboard", "code": "DASH-AOR-PL-01"}
        )
        item = self.env["dashboard.item"].create(
            {
                "name": "Item A",
                "dashboard_id": dashboard.id,
                "type": "placeholder",
                "data_source_id": data_source.id,
                "allow_open_records": False,
            }
        )
        payload = item._prepare_render_payload()
        self.assertIn("allow_open_records", payload)
        self.assertFalse(payload["allow_open_records"])

    def test_action_open_records_returns_list_form_action(self):
        """Python murni — pemicu P1 (L-01, L-02).

        Nilai balik `action_open_records` (dict aksi window) hanya bisa
        diverifikasi dengan meng-assert hasil pemanggilan method langsung
        — `action: call` YAML membuang nilai baliknya (L-01) dan isi
        dict tidak bisa diperiksa lewat assert dotted path (L-02).
        Kriteria Penerimaan: `action_open_records()` mengembalikan aksi
        ber-`view_mode` bernilai `list,form` (konvensi 19.0).
        """
        partner_model = self.env["ir.model"]._get("res.partner")
        data_source = self.env["dashboard.data_source"].create(
            {
                "name": "Partners",
                "code": "DASH-ITEM-OPENRECS-DS-01",
                "type": "orm",
                "model_id": partner_model.id,
            }
        )
        dashboard = self.env["dashboard.dashboard"].create(
            {"name": "Open Records Dashboard", "code": "DASH-ITEM-OPENRECS-01"}
        )
        item = self.env["dashboard.item"].create(
            {
                "name": "Item Open Records",
                "dashboard_id": dashboard.id,
                "type": "placeholder",
                "data_source_id": data_source.id,
            }
        )
        row = data_source._fetch_data(item)[0]
        action = item.action_open_records(row["row_domain"])
        self.assertEqual(action["res_model"], "res.partner")
        self.assertEqual(action["view_mode"], "list,form")
        self.assertEqual(action["type"], "ir.actions.act_window")

    def test_action_open_records_domain_cannot_override_data_source_domain(self):
        """Python murni — pemicu P1 (L-01, L-02).

        Sama seperti di atas: nilai balik `action_open_records` (dict
        aksi, khususnya kunci `domain`) hanya bisa diverifikasi lewat
        pemanggilan method langsung (L-01/L-02). Kriteria Penerimaan:
        domain 'Data Source' tetap terpasang meski domain kiriman
        ('row_domain' = `[]` di sini) mencoba menghilangkannya — server
        memasang ulang domain 'Data Source' sebagai konjungsi.
        """
        partner_model = self.env["ir.model"]._get("res.partner")
        data_source = self.env["dashboard.data_source"].create(
            {
                "name": "Companies Only",
                "code": "DASH-ITEM-OPENRECS-DOMAIN-DS-01",
                "type": "orm",
                "model_id": partner_model.id,
                "domain": "[('is_company', '=', True)]",
            }
        )
        dashboard = self.env["dashboard.dashboard"].create(
            {
                "name": "Open Records Domain Dashboard",
                "code": "DASH-ITEM-OPENRECS-DOM-01",
            }
        )
        item = self.env["dashboard.item"].create(
            {
                "name": "Item Open Records Domain",
                "dashboard_id": dashboard.id,
                "type": "placeholder",
                "data_source_id": data_source.id,
            }
        )
        action = item.action_open_records([])
        self.assertIn(("is_company", "=", True), action["domain"])

    def test_action_open_records_without_model_id_raises_user_error(self):
        """Python murni — pemicu P1 (L-01, L-02) — negative path.

        `data_source_id.model_id` tidak `required`, jadi bisa dibuat
        kosong lewat `create` biasa (tidak butuh bypass SQL) — Kriteria
        Penerimaan: item atas data source non-'orm'-configured (tanpa
        'Model') tidak menghasilkan aksi. `expect_error` YAML hanya bisa
        menguji aksi yang membuang nilai balik (`action: call`); di sini
        yang diuji justru KETIADAAN nilai balik (exception dilempar
        sebelum sempat mengembalikan apa pun), sehingga tetap ditulis
        Python murni supaya jelas method mana yang diuji dan pesan error
        apa yang diharapkan (L-01/L-02 tidak relevan untuk ini secara
        ketat, tapi menjaga test tetap satu file dengan test positif di
        atas yang memang butuh Python murni).
        """
        data_source = self.env["dashboard.data_source"].create(
            {
                "name": "No Model Source",
                "code": "DASH-ITEM-OPENRECS-NOMODEL-DS-01",
                "type": "orm",
            }
        )
        dashboard = self.env["dashboard.dashboard"].create(
            {
                "name": "Open Records No Model Dashboard",
                "code": "DASH-ITEM-OPENRECS-NM-01",
            }
        )
        item = self.env["dashboard.item"].create(
            {
                "name": "Item Open Records No Model",
                "dashboard_id": dashboard.id,
                "type": "placeholder",
                "data_source_id": data_source.id,
            }
        )
        with self.assertRaises(UserError):
            item.action_open_records([])

    def test_preview_render_payload_unreadable_data_source_returns_error_dict(self):
        """Python murni — pemicu P1 (L-01, L-02).

        Nilai balik hanya bisa diperiksa lewat pemanggilan method
        langsung. 'vals' menunjuk 'data_source_id' ke sebuah id yang
        tidak ada di basis data, sehingga pengambilan data gagal
        ('MissingError') saat pratinjau dihitung — method harus
        menangkap kegagalan itu dan mengembalikan dict berkunci 'error',
        bukan melempar traceback (Kriteria Penerimaan: 'Pratinjau atas
        konfigurasi yang salah mengembalikan dict berkunci error').
        """
        data_source = self.env["dashboard.data_source"].create(
            {
                "name": "Partners",
                "code": "DASH-ITEM-PREVIEW-DS-04",
                "type": "orm",
                "model_id": self.env["ir.model"]._get("res.partner").id,
            }
        )
        dashboard = self.env["dashboard.dashboard"].create(
            {"name": "Preview Dashboard", "code": "DASH-ITEM-PREVIEW-04"}
        )
        item = self.env["dashboard.item"].create(
            {
                "name": "Item A",
                "dashboard_id": dashboard.id,
                "type": "placeholder",
                "data_source_id": data_source.id,
            }
        )
        nonexistent_id = data_source.id + 1000000
        payload = item.preview_render_payload({"data_source_id": nonexistent_id})
        self.assertIn("error", payload)
