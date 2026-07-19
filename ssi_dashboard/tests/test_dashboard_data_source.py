# Copyright 2026 OpenSynergy Indonesia
# Copyright 2026 PT. Simetri Sinergi Indonesia
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
import datetime

from odoo_yaml_test import YamlTransactionCase
from psycopg2 import IntegrityError

from odoo.exceptions import UserError
from odoo.tests import tagged
from odoo.tests.common import freeze_time
from odoo.tools import mute_logger


@tagged("post_install", "-at_install")
class TestDashboardDataSource(YamlTransactionCase):
    def test_dashboard_data_source(self):
        self.run_yaml_scenario("test_data_dashboard_data_source.yaml")

    def test_create_duplicate_code_raises_integrity_error(self):
        """Python murni — pemicu P5 (L-22).

        `code` memakai `models.Constraint("UNIQUE(code)", ...)`, constraint
        tingkat database (bukan `_sql_constraints` Python-level lama).
        Membuat record kedua dengan `code` yang sama melempar
        `psycopg2.errors.UniqueViolation` (subclass `psycopg2.IntegrityError`),
        tipe yang tidak termasuk 12 tipe yang dikenali `expect_error`
        (L-22), sehingga tidak bisa diuji lewat YAML. `mute_logger`
        membungkam log ERROR `odoo.sql_db` yang normal muncul saat
        Postgres menolak query ini — errornya memang diharapkan dan
        sudah ditangkap lewat `assertRaises`, bukan kebocoran nyata yang
        harus menggagalkan `oca_checklog_odoo` di CI.
        """
        self.env["dashboard.data_source"].create(
            {"name": "First", "code": "DASH-DUP-01"}
        )
        with mute_logger("odoo.sql_db"), self.assertRaises(IntegrityError):
            with self.env.cr.savepoint():
                self.env["dashboard.data_source"].create(
                    {"name": "Second", "code": "DASH-DUP-01"}
                )

    def test_fetch_data_missing_dispatch_raises_user_error(self):
        """Python murni — celah terdekat P10 (L-09, L-11).

        `dashboard.data_source.type` adalah field Selection yang divalidasi
        ORM terhadap nilai yang terdaftar (hanya 'orm' di modul inti);
        tidak ada aksi YAML yang bisa membuat record dengan nilai `type`
        di luar selection terdaftar — `create`/`write` akan menolaknya
        lebih dulu dengan `ValueError` validasi field, bukan `UserError`
        dispatch yang sedang diuji di sini. Untuk menguji guard dispatch
        `_fetch_data` itu sendiri, `type` diubah lewat SQL langsung
        (bypass validasi ORM) — transformasi yang mustahil diekspresikan
        lewat `EVAL:` karena sandbox-nya tidak mengizinkan `cr.execute`
        (L-09/L-11).
        """
        data_source = self.env["dashboard.data_source"].create(
            {
                "name": "No Dispatch",
                "code": "DASH-NODISPATCH-01",
                "type": "orm",
            }
        )
        self.env.cr.execute(
            "UPDATE dashboard_data_source SET type = %s WHERE id = %s",
            ("bogus_type", data_source.id),
        )
        data_source.invalidate_recordset()
        with self.assertRaises(UserError):
            data_source._fetch_data(self.env["dashboard.item"])

    def test_fetch_data_orm_groups_by_relational_field(self):
        """Python murni — pemicu P1 (L-01, L-02).

        `_fetch_data_orm` mengembalikan `list` of `dict` yang hanya bisa
        diverifikasi dengan meng-assert nilai balik method secara langsung
        (jumlah baris, isi `group_key`/`group_label`); YAML tidak menyimpan
        nilai balik `action: call` (L-01) dan tidak bisa meng-assert
        ekspresi bebas seperti `len(rows)` (L-02).
        """
        partner_model = self.env.ref("base.model_res_partner")
        country_field = self.env["ir.model.fields"].search(
            [("model", "=", "res.partner"), ("name", "=", "country_id")],
            limit=1,
        )
        country_a = self.env.ref("base.us")
        country_b = self.env.ref("base.id")
        partners = self.env["res.partner"].create(
            [
                {"name": "Group By Partner A1", "country_id": country_a.id},
                {"name": "Group By Partner A2", "country_id": country_a.id},
                {"name": "Group By Partner B1", "country_id": country_b.id},
            ]
        )
        data_source = self.env["dashboard.data_source"].create(
            {
                "name": "Partners By Country",
                "code": "DASH-GROUPBY-COUNTRY-01",
                "type": "orm",
                "model_id": partner_model.id,
                "domain": f"[('id', 'in', {partners.ids!r})]",
                "group_by_field_id": country_field.id,
            }
        )
        rows = data_source._fetch_data(self.env["dashboard.item"])
        self.assertEqual(len(rows), 2)
        labels = {row["group_label"] for row in rows}
        self.assertEqual(labels, {country_a.display_name, country_b.display_name})
        counts = {row["group_label"]: row["__count"] for row in rows}
        self.assertEqual(counts[country_a.display_name], 2)
        self.assertEqual(counts[country_b.display_name], 1)

    def test_fetch_data_orm_without_group_by_returns_one_row(self):
        """Python murni — pemicu P1 (L-01, L-02).

        Sama seperti di atas: nilai balik `_fetch_data_orm` (jumlah baris,
        ketiadaan kunci `group_key`/`group_label`) hanya bisa di-assert
        langsung terhadap hasil pemanggilan method, bukan lewat `action:
        call` YAML yang membuang nilai baliknya (L-01).
        """
        partner_model = self.env.ref("base.model_res_partner")
        partners = self.env["res.partner"].create(
            [{"name": "No Group Partner 1"}, {"name": "No Group Partner 2"}]
        )
        data_source = self.env["dashboard.data_source"].create(
            {
                "name": "All Partners",
                "code": "DASH-NOGROUPBY-01",
                "type": "orm",
                "model_id": partner_model.id,
                "domain": f"[('id', 'in', {partners.ids!r})]",
            }
        )
        rows = data_source._fetch_data(self.env["dashboard.item"])
        self.assertEqual(len(rows), 1)
        self.assertNotIn("group_key", rows[0])
        self.assertNotIn("group_label", rows[0])
        self.assertEqual(rows[0]["__count"], 2)

    def test_fetch_data_orm_groups_by_date_field_year_granularity(self):
        """Python murni — pemicu P1 (L-01, L-02).

        Menguji `group_by_granularity = "year"` pada field bertipe `date`
        (`res.currency.rate.name`, selalu tersedia lewat modul `base`).
        Nilai balik `_fetch_data_orm` (jumlah baris per tahun, label
        `group_label`) hanya bisa diverifikasi dengan meng-assert hasil
        pemanggilan method langsung (L-01/L-02).
        """
        currency_rate_model = self.env.ref("base.model_res_currency_rate")
        date_field = self.env["ir.model.fields"].search(
            [("model", "=", "res.currency.rate"), ("name", "=", "name")],
            limit=1,
        )
        currency = self.env.ref("base.EUR")
        rates = self.env["res.currency.rate"].create(
            [
                {"currency_id": currency.id, "name": "2022-03-15", "rate": 1.1},
                {"currency_id": currency.id, "name": "2022-07-20", "rate": 1.2},
                {"currency_id": currency.id, "name": "2023-01-10", "rate": 1.3},
            ]
        )
        data_source = self.env["dashboard.data_source"].create(
            {
                "name": "Rates By Year",
                "code": "DASH-GROUPBY-DATE-01",
                "type": "orm",
                "model_id": currency_rate_model.id,
                "domain": f"[('id', 'in', {rates.ids!r})]",
                "group_by_field_id": date_field.id,
                "group_by_granularity": "year",
            }
        )
        rows = data_source._fetch_data(self.env["dashboard.item"])
        self.assertEqual(len(rows), 2)
        counts = {row["group_label"]: row["__count"] for row in rows}
        self.assertEqual(counts.get("2022"), 2)
        self.assertEqual(counts.get("2023"), 1)

    def test_fetch_data_orm_groups_by_datetime_field_year_granularity(self):
        """Python murni — pemicu P1 (L-01, L-02).

        Menguji `group_by_granularity = "year"` pada field bertipe
        `datetime` (`mail.message.date`, selalu tersedia karena
        `ssi_master_data_mixin` bergantung pada modul `mail`) — jalur kode
        berbeda dari test grouping field `date` di atas (format lewat
        `babel.dates.format_datetime`, bukan `format_date`). Nilai balik
        `_fetch_data_orm` hanya bisa diverifikasi dengan meng-assert hasil
        pemanggilan method langsung (L-01/L-02).
        """
        message_model = self.env.ref("mail.model_mail_message")
        date_field = self.env["ir.model.fields"].search(
            [("model", "=", "mail.message"), ("name", "=", "date")],
            limit=1,
        )
        messages = self.env["mail.message"].create(
            [
                {"body": "Group by datetime 1", "date": "2022-05-01 10:00:00"},
                {"body": "Group by datetime 2", "date": "2022-07-20 08:00:00"},
                {"body": "Group by datetime 3", "date": "2023-02-01 09:00:00"},
            ]
        )
        data_source = self.env["dashboard.data_source"].create(
            {
                "name": "Messages By Year",
                "code": "DASH-GROUPBY-DATETIME-01",
                "type": "orm",
                "model_id": message_model.id,
                "domain": f"[('id', 'in', {messages.ids!r})]",
                "group_by_field_id": date_field.id,
                "group_by_granularity": "year",
            }
        )
        rows = data_source._fetch_data(self.env["dashboard.item"])
        self.assertEqual(len(rows), 2)
        counts = {row["group_label"]: row["__count"] for row in rows}
        self.assertEqual(counts.get("2022"), 2)
        self.assertEqual(counts.get("2023"), 1)

    def test_fetch_data_orm_groups_by_selection_field_with_empty_group(self):
        """Python murni — pemicu P1 (L-01, L-02).

        Menguji pengelompokan pada field bertipe Selection —
        `dashboard.data_source.group_by_granularity` dipakai di sini
        sekaligus sebagai field TARGET grouping pada model
        `dashboard.data_source` itu sendiri (field itu tidak `required`,
        jadi bisa dikosongkan lewat `write` biasa untuk menghasilkan grup
        kosong tanpa perlu bypass SQL). Ini melatih jalur kode berbeda
        dari test grouping relasional/tanggal di atas: label selection dan
        label "None" untuk grup kosong. Nilai balik `_fetch_data_orm`
        (jumlah baris, `group_label` per grup) hanya bisa diverifikasi
        dengan meng-assert hasil pemanggilan method langsung (L-01/L-02).
        """
        data_source_model = self.env["ir.model"].search(
            [("model", "=", "dashboard.data_source")], limit=1
        )
        granularity_field = self.env["ir.model.fields"].search(
            [
                ("model", "=", "dashboard.data_source"),
                ("name", "=", "group_by_granularity"),
            ],
            limit=1,
        )
        sources = self.env["dashboard.data_source"].create(
            [
                {"name": "Sel Src Month A", "code": "DASH-SEL-01"},
                {"name": "Sel Src Month B", "code": "DASH-SEL-02"},
                {"name": "Sel Src Empty", "code": "DASH-SEL-03"},
            ]
        )
        sources[2].write({"group_by_granularity": False})
        data_source = self.env["dashboard.data_source"].create(
            {
                "name": "Group By Selection Meta",
                "code": "DASH-GROUPBY-SEL-01",
                "type": "orm",
                "model_id": data_source_model.id,
                "domain": f"[('id', 'in', {sources.ids!r})]",
                "group_by_field_id": granularity_field.id,
            }
        )
        rows = data_source._fetch_data(self.env["dashboard.item"])
        self.assertEqual(len(rows), 2)
        counts = {row["group_label"]: row["__count"] for row in rows}
        self.assertEqual(counts.get("Month"), 2)
        self.assertEqual(counts.get("None"), 1)

    def test_fetch_data_orm_measure_field_sum_returns_total(self):
        """Python murni — pemicu P1 (L-01, L-02) dan P2 (L-04).

        Nilai balik `_fetch_data_orm` (agregat `sum`, bukan jumlah
        record) hanya bisa diverifikasi dengan meng-assert hasil
        pemanggilan method langsung (L-01/L-02). Perbandingannya memakai
        `assertAlmostEqual` karena nilai float hasil `sum` tidak dijamin
        presisi bit demi bit (L-04/P2). `partner_latitude` dipakai
        sebagai field numerik karena tidak ada field `Monetary` yang
        tersedia tanpa dependensi tambahan pada rantai modul
        `ssi_master_data_mixin` (mail, ssi_print_mixin,
        ssi_sequence_mixin) — constraint measure memvalidasi
        `integer`/`float`/`monetary` secara setara, jadi `float` melatih
        jalur kode yang sama.
        """
        partner_model = self.env.ref("base.model_res_partner")
        latitude_field = self.env["ir.model.fields"].search(
            [("model", "=", "res.partner"), ("name", "=", "partner_latitude")],
            limit=1,
        )
        partners = self.env["res.partner"].create(
            [
                {"name": "Sum Partner 1", "partner_latitude": 10.0},
                {"name": "Sum Partner 2", "partner_latitude": 20.0},
                {"name": "Sum Partner 3", "partner_latitude": 30.0},
            ]
        )
        data_source = self.env["dashboard.data_source"].create(
            {
                "name": "Partners Latitude Sum",
                "code": "DASH-MEASURE-SUM-01",
                "type": "orm",
                "model_id": partner_model.id,
                "domain": f"[('id', 'in', {partners.ids!r})]",
                "measure_field_id": latitude_field.id,
                "aggregate": "sum",
            }
        )
        rows = data_source._fetch_data(self.env["dashboard.item"])
        self.assertEqual(len(rows), 1)
        self.assertAlmostEqual(rows[0]["partner_latitude:sum"], 60.0, places=2)

    def test_fetch_data_orm_multiple_measures_returns_one_key_per_measure(self):
        """Python murni — pemicu P1 (L-01, L-02).

        Nilai balik `_fetch_data_orm` (dict dengan satu kunci per baris
        `measure_ids`, dinamai sesuai `name` masing-masing measure) hanya
        bisa diverifikasi dengan meng-assert hasil pemanggilan method
        langsung (L-01/L-02).
        """
        partner_model = self.env.ref("base.model_res_partner")
        latitude_field = self.env["ir.model.fields"].search(
            [("model", "=", "res.partner"), ("name", "=", "partner_latitude")],
            limit=1,
        )
        partners = self.env["res.partner"].create(
            [
                {"name": "Multi Measure Partner 1", "partner_latitude": 10.0},
                {"name": "Multi Measure Partner 2", "partner_latitude": 20.0},
                {"name": "Multi Measure Partner 3", "partner_latitude": 30.0},
            ]
        )
        data_source = self.env["dashboard.data_source"].create(
            {
                "name": "Partners Latitude Multi Measure",
                "code": "DASH-MEASURE-MULTI-01",
                "type": "orm",
                "model_id": partner_model.id,
                "domain": f"[('id', 'in', {partners.ids!r})]",
                "measure_ids": [
                    (
                        0,
                        0,
                        {
                            "field_id": latitude_field.id,
                            "aggregate": "sum",
                            "name": "total_latitude",
                        },
                    ),
                    (
                        0,
                        0,
                        {
                            "aggregate": "count",
                            "name": "partner_count",
                        },
                    ),
                ],
            }
        )
        rows = data_source._fetch_data(self.env["dashboard.item"])
        self.assertEqual(len(rows), 1)
        self.assertAlmostEqual(rows[0]["total_latitude"], 60.0, places=2)
        self.assertEqual(rows[0]["partner_count"], 3)

    def test_create_duplicate_measure_name_raises_integrity_error(self):
        """Python murni — pemicu P5 (L-22).

        `dashboard.data_source.measure` memvalidasi keunikan
        `(data_source_id, name)` lewat `models.Constraint`, constraint
        tingkat database. Membuat measure kedua dengan `name` yang sama
        pada `data_source` yang sama melempar
        `psycopg2.errors.UniqueViolation` (subclass
        `psycopg2.IntegrityError`), tipe yang tidak termasuk 12 tipe yang
        dikenali `expect_error` (L-22), sehingga tidak bisa diuji lewat
        YAML. `mute_logger` membungkam log ERROR `odoo.sql_db` yang
        normal muncul saat Postgres menolak query ini — errornya memang
        diharapkan dan sudah ditangkap lewat `assertRaises`.
        """
        data_source = self.env["dashboard.data_source"].create(
            {"name": "Dup Measure Source", "code": "DASH-MEASURE-DUP-01"}
        )
        self.env["dashboard.data_source.measure"].create(
            {
                "data_source_id": data_source.id,
                "aggregate": "count",
                "name": "Total",
            }
        )
        with mute_logger("odoo.sql_db"), self.assertRaises(IntegrityError):
            with self.env.cr.savepoint():
                self.env["dashboard.data_source.measure"].create(
                    {
                        "data_source_id": data_source.id,
                        "aggregate": "count",
                        "name": "Total",
                    }
                )

    def test_date_range_selection_has_28_choices(self):
        """Python murni — pemicu P1 (L-01, L-02).

        Kriteria Penerimaan mensyaratkan `date_range` menyediakan 28
        pilihan. Metadata `selection` field hanya bisa diperiksa dengan
        meng-assert nilai balik `fields_get`/`_fields` langsung — YAML
        tidak bisa meng-assert ekspresi bebas seperti `len(selection)`.
        """
        selection = self.env["dashboard.data_source"]._fields["date_range"].selection
        self.assertEqual(len(selection), 28)

    def test_prepare_date_range_all_time_returns_none_none(self):
        """Python murni — pemicu P1 (L-01, L-02).

        Nilai balik `_prepare_date_range()` hanya bisa diverifikasi
        dengan meng-assert hasil pemanggilan method langsung — `action:
        call` YAML membuang nilai baliknya (L-01).
        """
        data_source = self.env["dashboard.data_source"].create(
            {"name": "All Time Source", "code": "DASH-DATERANGE-ALLTIME-01"}
        )
        self.assertEqual(data_source._prepare_date_range(), (None, None))

    def test_prepare_date_domain_without_date_field_id_is_empty(self):
        """Python murni — pemicu P1 (L-01, L-02).

        Nilai balik `_prepare_date_domain()` (list domain) hanya bisa
        diverifikasi dengan meng-assert hasil pemanggilan method
        langsung (L-01/L-02). Data source tanpa `date_field_id` harus
        menghasilkan domain kosong walau `date_range` bukan `all_time`,
        sehingga fetch data-nya tidak berubah dari sebelum fitur ini ada.
        """
        data_source = self.env["dashboard.data_source"].create(
            {
                "name": "No Date Field Source",
                "code": "DASH-DATERANGE-NOFIELD-01",
                "date_range": "this_month",
            }
        )
        self.assertEqual(data_source._prepare_date_domain(), [])

    @freeze_time("2026-07-19 10:00:00")
    def test_prepare_date_range_today_frozen(self):
        """Python murni — pemicu P6 (L-16: tidak ada pembekuan waktu di
        sandbox YAML — `datetime`/`date` adalah kelas asli).

        Waktu dibekukan pada 2026-07-19 10:00:00 UTC (pengguna tanpa
        `tz`, jadi jatuh ke UTC). `date_range` = `today` harus
        menghasilkan rentang mulai dan selesai sama-sama tanggal itu.
        """
        data_source = self.env["dashboard.data_source"].create(
            {
                "name": "Today Source",
                "code": "DASH-DATERANGE-TODAY-01",
                "date_range": "today",
            }
        )
        date_start, date_end = data_source._prepare_date_range()
        self.assertEqual(date_start, datetime.date(2026, 7, 19))
        self.assertEqual(date_end, datetime.date(2026, 7, 19))

    @freeze_time("2026-07-19 10:00:00")
    def test_prepare_date_range_last_7_days_frozen(self):
        """Python murni — pemicu P6 (L-16).

        Waktu dibekukan pada 2026-07-19. `date_range` = `last_7_days`
        harus menghasilkan rentang tujuh hari (13 Juli s.d. 19 Juli
        2026, inklusif keduanya).
        """
        data_source = self.env["dashboard.data_source"].create(
            {
                "name": "Last 7 Days Source",
                "code": "DASH-DATERANGE-LAST7-01",
                "date_range": "last_7_days",
            }
        )
        date_start, date_end = data_source._prepare_date_range()
        self.assertEqual(date_start, datetime.date(2026, 7, 13))
        self.assertEqual(date_end, datetime.date(2026, 7, 19))

    @freeze_time("2026-07-20 10:00:00")
    def test_prepare_date_range_this_week_follows_lang_not_hardcoded_monday(self):
        """Python murni — pemicu P6 (L-16).

        Waktu dibekukan pada Senin, 20 Juli 2026. Lang default database
        test adalah `en_US`, yang menurut CLDR memulai minggu pada
        **Minggu** (bukan Senin). Bila awal minggu di-hardcode Senin,
        `this_week` akan mulai dari 20 Juli (hari ini); karena
        mengikuti `lang`, seharusnya mulai dari Minggu 19 Juli
        (sehari sebelum hari ini) sampai Sabtu 25 Juli.
        """
        data_source = self.env["dashboard.data_source"].create(
            {
                "name": "This Week Source",
                "code": "DASH-DATERANGE-THISWEEK-01",
                "date_range": "this_week",
            }
        )
        date_start, date_end = data_source._prepare_date_range()
        self.assertEqual(date_start, datetime.date(2026, 7, 19))
        self.assertEqual(date_end, datetime.date(2026, 7, 25))

    @freeze_time("2026-07-20 10:00:00")
    def test_prepare_date_range_computes_every_relative_selection_value(self):
        """Python murni — pemicu P6 (L-16: pembekuan waktu) dan P11
        (L-12: tidak ada matriks/parametrisasi kasus data-driven di
        YAML — setiap varian butuh skenario tertulis tangan sendiri,
        jadi >=5 varian dengan bentuk assert identik ditulis Python).

        Waktu dibekukan pada Senin, 20 Juli 2026 (lang default `en_US`,
        awal minggu Minggu — lihat
        `test_prepare_date_range_this_week_follows_lang_not_hardcoded_monday`).
        Menguji seluruh nilai `date_range` relatif yang belum dicakup
        test lain (`all_time`, `custom`, `today`, `last_7_days`,
        `this_week` sudah diuji tersendiri di atas) sekaligus, karena
        assert-nya identik — hanya pasangan input/output yang berbeda.
        """
        data_source = self.env["dashboard.data_source"].create(
            {"name": "Every Range Source", "code": "DASH-DATERANGE-MATRIX-01"}
        )
        cases = {
            "yesterday": (datetime.date(2026, 7, 19), datetime.date(2026, 7, 19)),
            "last_week": (datetime.date(2026, 7, 12), datetime.date(2026, 7, 18)),
            "next_week": (datetime.date(2026, 7, 26), datetime.date(2026, 8, 1)),
            "week_to_date": (datetime.date(2026, 7, 19), datetime.date(2026, 7, 20)),
            "this_month": (datetime.date(2026, 7, 1), datetime.date(2026, 7, 31)),
            "last_month": (datetime.date(2026, 6, 1), datetime.date(2026, 6, 30)),
            "next_month": (datetime.date(2026, 8, 1), datetime.date(2026, 8, 31)),
            "month_to_date": (datetime.date(2026, 7, 1), datetime.date(2026, 7, 20)),
            "this_quarter": (datetime.date(2026, 7, 1), datetime.date(2026, 9, 30)),
            "last_quarter": (datetime.date(2026, 4, 1), datetime.date(2026, 6, 30)),
            "next_quarter": (datetime.date(2026, 10, 1), datetime.date(2026, 12, 31)),
            "quarter_to_date": (datetime.date(2026, 7, 1), datetime.date(2026, 7, 20)),
            "this_year": (datetime.date(2026, 1, 1), datetime.date(2026, 12, 31)),
            "last_year": (datetime.date(2025, 1, 1), datetime.date(2025, 12, 31)),
            "next_year": (datetime.date(2027, 1, 1), datetime.date(2027, 12, 31)),
            "year_to_date": (datetime.date(2026, 1, 1), datetime.date(2026, 7, 20)),
            "last_30_days": (datetime.date(2026, 6, 21), datetime.date(2026, 7, 20)),
            "last_90_days": (datetime.date(2026, 4, 22), datetime.date(2026, 7, 20)),
            "last_365_days": (datetime.date(2025, 7, 21), datetime.date(2026, 7, 20)),
            "past_till_now": (None, datetime.date(2026, 7, 20)),
            "past_excluding_today": (None, datetime.date(2026, 7, 19)),
            "future_starting_now": (datetime.date(2026, 7, 20), None),
            "future_starting_tomorrow": (datetime.date(2026, 7, 21), None),
        }
        for date_range, expected in cases.items():
            data_source.write({"date_range": date_range})
            with self.subTest(date_range=date_range):
                self.assertEqual(data_source._prepare_date_range(), expected)

    def test_prepare_date_range_unknown_value_raises_user_error(self):
        """Python murni — celah terdekat P10 (L-09, L-11), pola yang
        sama seperti `test_fetch_data_missing_dispatch_raises_user_error`
        di atas.

        `date_range` adalah Selection tervalidasi ORM (28 nilai
        terdaftar); tidak ada aksi YAML yang bisa membuat record dengan
        nilai di luar itu. Untuk menguji guard fallback
        `_prepare_date_range` itu sendiri, `date_range` diubah lewat SQL
        langsung (bypass validasi ORM) — transformasi yang mustahil lewat
        `EVAL:` (L-09/L-11).
        """
        data_source = self.env["dashboard.data_source"].create(
            {"name": "Unknown Range Source", "code": "DASH-DATERANGE-UNKNOWN-01"}
        )
        self.env.cr.execute(
            "UPDATE dashboard_data_source SET date_range = %s WHERE id = %s",
            ("bogus_range", data_source.id),
        )
        data_source.invalidate_recordset()
        with self.assertRaises(UserError):
            data_source._prepare_date_range()

    @freeze_time("2026-07-19 23:30:00")
    def test_fetch_data_orm_filters_by_datetime_field_uses_user_timezone(self):
        """Python murni — pemicu P6 (L-16).

        Waktu dibekukan pada 2026-07-19 23:30:00 UTC. Pengguna diberi
        `tz` `Asia/Jakarta` (UTC+7), sehingga "hari ini" baginya adalah
        2026-07-20, bukan 2026-07-19 (UTC) — membuktikan konversi
        timezone di `_prepare_date_domain`/`_fetch_data_orm` benar-benar
        dipakai, bukan sekadar `_prepare_date_range` yang diuji
        terisolasi. Satu message tercatat 2026-07-19 23:45:00 UTC (=
        2026-07-20 06:45 Jakarta, termasuk "hari ini" Jakarta) harus
        ikut; satu message tercatat 2026-07-19 10:00:00 UTC (= 2026-07-19
        17:00 Jakarta, "kemarin" Jakarta) harus tidak ikut.
        """
        self.env.user.write({"tz": "Asia/Jakarta"})
        message_model = self.env.ref("mail.model_mail_message")
        date_field = self.env["ir.model.fields"].search(
            [("model", "=", "mail.message"), ("name", "=", "date")],
            limit=1,
        )
        messages = self.env["mail.message"].create(
            [
                {"body": "Within Jakarta Today", "date": "2026-07-19 23:45:00"},
                {"body": "Yesterday In Jakarta", "date": "2026-07-19 10:00:00"},
            ]
        )
        data_source = self.env["dashboard.data_source"].create(
            {
                "name": "Messages Jakarta Today",
                "code": "DASH-DATEFILTER-TZ-01",
                "type": "orm",
                "model_id": message_model.id,
                "domain": f"[('id', 'in', {messages.ids!r})]",
                "date_field_id": date_field.id,
                "date_range": "today",
            }
        )
        rows = data_source._fetch_data(self.env["dashboard.item"])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["__count"], 1)

    @freeze_time("2026-07-19 10:00:00")
    def test_prepare_domain_substitutes_uid(self):
        """Python murni — pemicu P1 (L-01).

        Nilai balik `_prepare_domain()` (list domain dengan placeholder
        `%UID` tersubstitusi) hanya bisa diverifikasi dengan meng-assert
        hasil pemanggilan method langsung — `action: call` YAML membuang
        nilai baliknya (L-01).
        """
        partner_model = self.env.ref("base.model_res_partner")
        data_source = self.env["dashboard.data_source"].create(
            {
                "name": "My Tickets",
                "code": "DASH-PLACEHOLDER-UID-01",
                "type": "orm",
                "model_id": partner_model.id,
                "domain": "[('user_id', '=', %UID)]",
            }
        )
        self.assertEqual(
            data_source._prepare_domain(), [("user_id", "=", self.env.uid)]
        )

    def test_prepare_domain_substitutes_mycompany(self):
        """Python murni — pemicu P1 (L-01).

        Sama seperti `test_prepare_domain_substitutes_uid`, kali ini
        untuk placeholder `%MYCOMPANY`. Nilai balik `_prepare_domain()`
        hanya bisa diverifikasi dengan meng-assert hasil pemanggilan
        method langsung (L-01).
        """
        partner_model = self.env.ref("base.model_res_partner")
        data_source = self.env["dashboard.data_source"].create(
            {
                "name": "My Company Partners",
                "code": "DASH-PLACEHOLDER-MYCOMPANY-01",
                "type": "orm",
                "model_id": partner_model.id,
                "domain": "[('company_id', '=', %MYCOMPANY)]",
            }
        )
        self.assertEqual(
            data_source._prepare_domain(),
            [("company_id", "=", self.env.company.id)],
        )

    def test_fetch_data_orm_filters_by_date_field_today(self):
        """Python murni — pemicu P6 (L-16).

        Membuktikan `_prepare_date_domain` benar-benar tergabung ke
        domain di `_fetch_data_orm` (bukan cuma diuji terisolasi):
        dengan `date_field_id` mengarah ke field bertipe `date`
        (`res.currency.rate.name`) dan `date_range` = `today`, hanya
        baris bertanggal hari ini yang ikut terhitung.
        """
        currency_rate_model = self.env.ref("base.model_res_currency_rate")
        date_field = self.env["ir.model.fields"].search(
            [("model", "=", "res.currency.rate"), ("name", "=", "name")],
            limit=1,
        )
        currency = self.env.ref("base.EUR")
        rates = self.env["res.currency.rate"].create(
            [
                {"currency_id": currency.id, "name": "2026-07-19", "rate": 1.1},
                {"currency_id": currency.id, "name": "2026-07-01", "rate": 1.2},
            ]
        )
        data_source = self.env["dashboard.data_source"].create(
            {
                "name": "Rates Today",
                "code": "DASH-DATEFILTER-DATE-01",
                "type": "orm",
                "model_id": currency_rate_model.id,
                "domain": f"[('id', 'in', {rates.ids!r})]",
                "date_field_id": date_field.id,
                "date_range": "today",
            }
        )
        rows = data_source._fetch_data(self.env["dashboard.item"])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["__count"], 1)

    def test_fetch_data_orm_sort_by_measure_desc_orders_rows(self):
        """Python murni — pemicu P3 (L-02: urutan baris hasil harus
        di-assert, tidak bisa diekspresikan lewat `expect_count`/assert
        YAML biasa).

        Tiga negara dengan jumlah partner berbeda (1, 2, 3). `sort_by` =
        `measure`, `sort_order` = `desc` harus mengembalikan baris
        terurut menurun berdasarkan `__count` (measure tunggal, karena
        `measure_ids` kosong).
        """
        partner_model = self.env.ref("base.model_res_partner")
        country_a = self.env.ref("base.us")
        country_b = self.env.ref("base.id")
        country_c = self.env.ref("base.sg")
        partners = self.env["res.partner"].create(
            [
                {"name": "Sort Partner A1", "country_id": country_a.id},
                {"name": "Sort Partner B1", "country_id": country_b.id},
                {"name": "Sort Partner B2", "country_id": country_b.id},
                {"name": "Sort Partner C1", "country_id": country_c.id},
                {"name": "Sort Partner C2", "country_id": country_c.id},
                {"name": "Sort Partner C3", "country_id": country_c.id},
            ]
        )
        country_field = self.env["ir.model.fields"].search(
            [("model", "=", "res.partner"), ("name", "=", "country_id")],
            limit=1,
        )
        data_source = self.env["dashboard.data_source"].create(
            {
                "name": "Partners By Country Sorted",
                "code": "DASH-SORT-MEASURE-01",
                "type": "orm",
                "model_id": partner_model.id,
                "domain": f"[('id', 'in', {partners.ids!r})]",
                "group_by_field_id": country_field.id,
                "sort_by": "measure",
                "sort_order": "desc",
            }
        )
        rows = data_source._fetch_data(self.env["dashboard.item"])
        self.assertEqual(len(rows), 3)
        counts = [row["__count"] for row in rows]
        self.assertEqual(counts, [3, 2, 1])

    def test_fetch_data_orm_limit_cuts_rows_after_sort(self):
        """Python murni — pemicu P1 (L-01, L-02).

        Data source dengan tiga grup dan `limit` = 2 harus mengembalikan
        tepat dua baris — jumlah baris hasil hanya bisa diverifikasi
        dengan meng-assert nilai balik method langsung (L-01/L-02).
        """
        partner_model = self.env.ref("base.model_res_partner")
        country_a = self.env.ref("base.us")
        country_b = self.env.ref("base.id")
        country_c = self.env.ref("base.sg")
        partners = self.env["res.partner"].create(
            [
                {"name": "Limit Partner A1", "country_id": country_a.id},
                {"name": "Limit Partner B1", "country_id": country_b.id},
                {"name": "Limit Partner C1", "country_id": country_c.id},
            ]
        )
        country_field = self.env["ir.model.fields"].search(
            [("model", "=", "res.partner"), ("name", "=", "country_id")],
            limit=1,
        )
        data_source = self.env["dashboard.data_source"].create(
            {
                "name": "Partners By Country Limited",
                "code": "DASH-LIMIT-CUT-01",
                "type": "orm",
                "model_id": partner_model.id,
                "domain": f"[('id', 'in', {partners.ids!r})]",
                "group_by_field_id": country_field.id,
                "limit": 2,
            }
        )
        rows = data_source._fetch_data(self.env["dashboard.item"])
        self.assertEqual(len(rows), 2)

    def test_fetch_data_orm_limit_zero_returns_every_row(self):
        """Python murni — pemicu P1 (L-01, L-02).

        `limit` = 0 (nilai default) berarti tanpa batas — mengembalikan
        seluruh baris. Nilai balik hanya bisa diverifikasi dengan
        meng-assert hasil pemanggilan method langsung (L-01/L-02).
        """
        partner_model = self.env.ref("base.model_res_partner")
        country_a = self.env.ref("base.us")
        country_b = self.env.ref("base.id")
        country_c = self.env.ref("base.sg")
        partners = self.env["res.partner"].create(
            [
                {"name": "NoLimit Partner A1", "country_id": country_a.id},
                {"name": "NoLimit Partner B1", "country_id": country_b.id},
                {"name": "NoLimit Partner C1", "country_id": country_c.id},
            ]
        )
        country_field = self.env["ir.model.fields"].search(
            [("model", "=", "res.partner"), ("name", "=", "country_id")],
            limit=1,
        )
        data_source = self.env["dashboard.data_source"].create(
            {
                "name": "Partners By Country No Limit",
                "code": "DASH-LIMIT-ZERO-01",
                "type": "orm",
                "model_id": partner_model.id,
                "domain": f"[('id', 'in', {partners.ids!r})]",
                "group_by_field_id": country_field.id,
                "limit": 0,
            }
        )
        rows = data_source._fetch_data(self.env["dashboard.item"])
        self.assertEqual(len(rows), 3)

    def test_fetch_data_orm_fill_temporal_adds_zero_row_for_empty_month(self):
        """Python murni — pemicu P3 (L-02: baris tambahan hasil fill
        hanya bisa diverifikasi lewat assert nilai balik method
        langsung, bukan `expect_count`/assert YAML biasa).

        Data hanya ada di Januari dan Maret 2026 (granularitas bulan).
        `fill_temporal` = `True` harus menambah satu baris bernilai nol
        untuk Februari 2026 di antara keduanya.
        """
        currency_rate_model = self.env.ref("base.model_res_currency_rate")
        date_field = self.env["ir.model.fields"].search(
            [("model", "=", "res.currency.rate"), ("name", "=", "name")],
            limit=1,
        )
        currency = self.env.ref("base.EUR")
        rates = self.env["res.currency.rate"].create(
            [
                {"currency_id": currency.id, "name": "2026-01-15", "rate": 1.1},
                {"currency_id": currency.id, "name": "2026-03-10", "rate": 1.3},
            ]
        )
        data_source = self.env["dashboard.data_source"].create(
            {
                "name": "Rates By Month Filled",
                "code": "DASH-FILLTEMPORAL-01",
                "type": "orm",
                "model_id": currency_rate_model.id,
                "domain": f"[('id', 'in', {rates.ids!r})]",
                "group_by_field_id": date_field.id,
                "group_by_granularity": "month",
                "fill_temporal": True,
            }
        )
        rows = data_source._fetch_data(self.env["dashboard.item"])
        self.assertEqual(len(rows), 3)
        counts_by_label = {row["group_label"]: row["__count"] for row in rows}
        self.assertIn("February 2026", counts_by_label)
        self.assertEqual(counts_by_label["February 2026"], 0)
        self.assertEqual(counts_by_label["January 2026"], 1)
        self.assertEqual(counts_by_label["March 2026"], 1)

    def test_fetch_data_orm_fill_temporal_ignored_for_non_date_group_by(self):
        """Python murni — pemicu P1 (L-01, L-02).

        `fill_temporal` = `True` tanpa `group_by_field_id` bertipe
        tanggal harus diabaikan tanpa error dan tanpa menambah baris —
        hanya bisa diverifikasi dengan meng-assert nilai balik method
        langsung.
        """
        partner_model = self.env.ref("base.model_res_partner")
        country_a = self.env.ref("base.us")
        partners = self.env["res.partner"].create(
            [{"name": "Fill Ignored Partner 1", "country_id": country_a.id}]
        )
        country_field = self.env["ir.model.fields"].search(
            [("model", "=", "res.partner"), ("name", "=", "country_id")],
            limit=1,
        )
        data_source = self.env["dashboard.data_source"].create(
            {
                "name": "Partners Fill Ignored",
                "code": "DASH-FILLTEMPORAL-IGNORED-01",
                "type": "orm",
                "model_id": partner_model.id,
                "domain": f"[('id', 'in', {partners.ids!r})]",
                "group_by_field_id": country_field.id,
                "fill_temporal": True,
            }
        )
        rows = data_source._fetch_data(self.env["dashboard.item"])
        self.assertEqual(len(rows), 1)

    def test_fetch_data_orm_fill_temporal_without_any_data_returns_empty(self):
        """Python murni — pemicu P1 (L-01, L-02).

        `fill_temporal` = `True` tanpa satu pun baris data (domain tidak
        cocok apa pun) tidak boleh membangkitkan periode apa pun (tidak
        ada batas rentang untuk diturunkan) — hanya bisa diverifikasi
        dengan meng-assert hasil pemanggilan method langsung.
        """
        currency_rate_model = self.env.ref("base.model_res_currency_rate")
        date_field = self.env["ir.model.fields"].search(
            [("model", "=", "res.currency.rate"), ("name", "=", "name")],
            limit=1,
        )
        data_source = self.env["dashboard.data_source"].create(
            {
                "name": "Rates Fill No Data",
                "code": "DASH-FILLTEMPORAL-EMPTY-01",
                "type": "orm",
                "model_id": currency_rate_model.id,
                "domain": "[('id', 'in', [])]",
                "group_by_field_id": date_field.id,
                "group_by_granularity": "month",
                "fill_temporal": True,
            }
        )
        rows = data_source._fetch_data(self.env["dashboard.item"])
        self.assertEqual(rows, [])

    def test_fetch_data_orm_fill_temporal_week_granularity_adds_missing_week(self):
        """Python murni — pemicu P3 (L-02: baris tambahan hasil fill

        hanya bisa diverifikasi lewat assert nilai balik method langsung).

        Dua tanggal berjarak dua minggu (granularitas week) harus
        menghasilkan satu baris nol untuk minggu di antaranya — melatih
        jalur kode `_temporal_bucket_start`/`_temporal_bucket_next` untuk
        granularitas `week`, berbeda dari jalur `month` yang sudah diuji
        di atas.
        """
        currency_rate_model = self.env.ref("base.model_res_currency_rate")
        date_field = self.env["ir.model.fields"].search(
            [("model", "=", "res.currency.rate"), ("name", "=", "name")],
            limit=1,
        )
        currency = self.env.ref("base.EUR")
        rates = self.env["res.currency.rate"].create(
            [
                {"currency_id": currency.id, "name": "2026-01-05", "rate": 1.1},
                {"currency_id": currency.id, "name": "2026-01-19", "rate": 1.3},
            ]
        )
        data_source = self.env["dashboard.data_source"].create(
            {
                "name": "Rates By Week Filled",
                "code": "DASH-FILLTEMPORAL-WEEK-01",
                "type": "orm",
                "model_id": currency_rate_model.id,
                "domain": f"[('id', 'in', {rates.ids!r})]",
                "group_by_field_id": date_field.id,
                "group_by_granularity": "week",
                "fill_temporal": True,
            }
        )
        rows = data_source._fetch_data(self.env["dashboard.item"])
        self.assertEqual(len(rows), 3)
        self.assertEqual(sum(row["__count"] for row in rows), 2)
        zero_rows = [row for row in rows if row["__count"] == 0]
        self.assertEqual(len(zero_rows), 1)

    def test_fetch_data_orm_fill_temporal_quarter_granularity_adds_missing_quarter(
        self,
    ):
        """Python murni — pemicu P3 (L-02).

        Dua tanggal berjarak dua kuartal (granularitas quarter) harus
        menghasilkan satu baris nol untuk kuartal di antaranya — melatih
        jalur kode `_temporal_bucket_start`/`_temporal_bucket_next` untuk
        granularitas `quarter`.
        """
        currency_rate_model = self.env.ref("base.model_res_currency_rate")
        date_field = self.env["ir.model.fields"].search(
            [("model", "=", "res.currency.rate"), ("name", "=", "name")],
            limit=1,
        )
        currency = self.env.ref("base.EUR")
        rates = self.env["res.currency.rate"].create(
            [
                {"currency_id": currency.id, "name": "2026-01-15", "rate": 1.1},
                {"currency_id": currency.id, "name": "2026-07-15", "rate": 1.3},
            ]
        )
        data_source = self.env["dashboard.data_source"].create(
            {
                "name": "Rates By Quarter Filled",
                "code": "DASH-FILLTEMPORAL-QUARTER-01",
                "type": "orm",
                "model_id": currency_rate_model.id,
                "domain": f"[('id', 'in', {rates.ids!r})]",
                "group_by_field_id": date_field.id,
                "group_by_granularity": "quarter",
                "fill_temporal": True,
            }
        )
        rows = data_source._fetch_data(self.env["dashboard.item"])
        self.assertEqual(len(rows), 3)
        self.assertEqual(sum(row["__count"] for row in rows), 2)
        zero_rows = [row for row in rows if row["__count"] == 0]
        self.assertEqual(len(zero_rows), 1)

    def test_fetch_data_orm_fill_temporal_year_granularity_adds_missing_year(self):
        """Python murni — pemicu P3 (L-02).

        Dua tanggal berjarak dua tahun (granularitas year) harus
        menghasilkan satu baris nol untuk tahun di antaranya — melatih
        jalur kode `_temporal_bucket_start`/`_temporal_bucket_next` untuk
        granularitas `year`.
        """
        currency_rate_model = self.env.ref("base.model_res_currency_rate")
        date_field = self.env["ir.model.fields"].search(
            [("model", "=", "res.currency.rate"), ("name", "=", "name")],
            limit=1,
        )
        currency = self.env.ref("base.EUR")
        rates = self.env["res.currency.rate"].create(
            [
                {"currency_id": currency.id, "name": "2024-06-15", "rate": 1.1},
                {"currency_id": currency.id, "name": "2026-06-15", "rate": 1.3},
            ]
        )
        data_source = self.env["dashboard.data_source"].create(
            {
                "name": "Rates By Year Filled",
                "code": "DASH-FILLTEMPORAL-YEAR-01",
                "type": "orm",
                "model_id": currency_rate_model.id,
                "domain": f"[('id', 'in', {rates.ids!r})]",
                "group_by_field_id": date_field.id,
                "group_by_granularity": "year",
                "fill_temporal": True,
            }
        )
        rows = data_source._fetch_data(self.env["dashboard.item"])
        self.assertEqual(len(rows), 3)
        counts_by_label = {row["group_label"]: row["__count"] for row in rows}
        self.assertEqual(counts_by_label.get("2025"), 0)

    def test_fetch_data_orm_fill_temporal_day_granularity_adds_missing_day(self):
        """Python murni — pemicu P3 (L-02).

        Dua tanggal berjarak tiga hari (granularitas day) harus
        menghasilkan dua baris nol untuk hari-hari di antaranya —
        melatih jalur `_temporal_bucket_start` yang tidak punya aturan
        floor sendiri untuk `day`/`hour` (baris terakhir yang
        mengembalikan ``value`` apa adanya).
        """
        currency_rate_model = self.env.ref("base.model_res_currency_rate")
        date_field = self.env["ir.model.fields"].search(
            [("model", "=", "res.currency.rate"), ("name", "=", "name")],
            limit=1,
        )
        currency = self.env.ref("base.EUR")
        rates = self.env["res.currency.rate"].create(
            [
                {"currency_id": currency.id, "name": "2026-01-10", "rate": 1.1},
                {"currency_id": currency.id, "name": "2026-01-13", "rate": 1.3},
            ]
        )
        data_source = self.env["dashboard.data_source"].create(
            {
                "name": "Rates By Day Filled",
                "code": "DASH-FILLTEMPORAL-DAY-01",
                "type": "orm",
                "model_id": currency_rate_model.id,
                "domain": f"[('id', 'in', {rates.ids!r})]",
                "group_by_field_id": date_field.id,
                "group_by_granularity": "day",
                "fill_temporal": True,
            }
        )
        rows = data_source._fetch_data(self.env["dashboard.item"])
        self.assertEqual(len(rows), 4)
        self.assertEqual(sum(row["__count"] for row in rows), 2)
        zero_rows = [row for row in rows if row["__count"] == 0]
        self.assertEqual(len(zero_rows), 2)

    def test_fetch_data_orm_sort_by_label_orders_rows_alphabetically(self):
        """Python murni — pemicu P3 (L-02: urutan baris hasil harus
        di-assert, tidak bisa diekspresikan lewat `expect_count`/assert
        YAML biasa).

        `sort_by` = `label`, `sort_order` = `asc` harus mengembalikan
        baris terurut menaik berdasarkan `group_label` — jalur kode
        berbeda dari `sort_by` = `measure` yang sudah diuji di atas.
        """
        partner_model = self.env.ref("base.model_res_partner")
        country_id = self.env.ref("base.id")  # "Indonesia"
        country_us = self.env.ref("base.us")  # "United States"
        partners = self.env["res.partner"].create(
            [
                {"name": "Label Sort Partner US", "country_id": country_us.id},
                {"name": "Label Sort Partner ID", "country_id": country_id.id},
            ]
        )
        country_field = self.env["ir.model.fields"].search(
            [("model", "=", "res.partner"), ("name", "=", "country_id")],
            limit=1,
        )
        data_source = self.env["dashboard.data_source"].create(
            {
                "name": "Partners By Country Sorted By Label",
                "code": "DASH-SORT-LABEL-01",
                "type": "orm",
                "model_id": partner_model.id,
                "domain": f"[('id', 'in', {partners.ids!r})]",
                "group_by_field_id": country_field.id,
                "sort_by": "label",
                "sort_order": "asc",
            }
        )
        rows = data_source._fetch_data(self.env["dashboard.item"])
        self.assertEqual(len(rows), 2)
        labels = [row["group_label"] for row in rows]
        self.assertEqual(labels, [country_id.display_name, country_us.display_name])

    def test_fetch_data_orm_groups_by_two_dimensions(self):
        """Python murni — pemicu P1 (L-01, L-02).

        `sub_group_by_field_id` menghasilkan satu baris per kombinasi
        (`group_by_field_id`, `sub_group_by_field_id`) yang punya data —
        jumlah baris dan isi `sub_group_key`/`sub_group_label` hanya bisa
        diverifikasi dengan meng-assert nilai balik method langsung
        (L-01/L-02), karena `action: call` YAML membuang nilai balik dan
        tidak bisa meng-assert ekspresi bebas seperti `len(rows)`.

        `industry_id` (bukan `company_type`) dipakai sebagai field sub
        group karena `company_type` adalah field computed tanpa
        `store=True` di `res.partner` — `_read_group` tidak bisa
        mengelompokkan field yang tidak tersimpan di database
        (`ValueError: Cannot convert ... to SQL because it is not
        stored`). `industry_id` sekaligus melatih jalur label relasional
        (`display_name`) untuk dimensi kedua, sama seperti `country_id`
        untuk dimensi pertama.
        """
        partner_model = self.env.ref("base.model_res_partner")
        country_field = self.env["ir.model.fields"].search(
            [("model", "=", "res.partner"), ("name", "=", "country_id")],
            limit=1,
        )
        industry_field = self.env["ir.model.fields"].search(
            [("model", "=", "res.partner"), ("name", "=", "industry_id")],
            limit=1,
        )
        country_a = self.env.ref("base.us")
        country_b = self.env.ref("base.id")
        industry_x, industry_y = self.env["res.partner.industry"].create(
            [
                {"name": "Two Dim Industry X"},
                {"name": "Two Dim Industry Y"},
            ]
        )
        partners = self.env["res.partner"].create(
            [
                {
                    "name": "Two Dim Partner A Industry X",
                    "country_id": country_a.id,
                    "industry_id": industry_x.id,
                },
                {
                    "name": "Two Dim Partner A Industry Y",
                    "country_id": country_a.id,
                    "industry_id": industry_y.id,
                },
                {
                    "name": "Two Dim Partner B Industry Y 1",
                    "country_id": country_b.id,
                    "industry_id": industry_y.id,
                },
                {
                    "name": "Two Dim Partner B Industry Y 2",
                    "country_id": country_b.id,
                    "industry_id": industry_y.id,
                },
            ]
        )
        data_source = self.env["dashboard.data_source"].create(
            {
                "name": "Partners By Country And Industry",
                "code": "DASH-SUBGROUPBY-01",
                "type": "orm",
                "model_id": partner_model.id,
                "domain": f"[('id', 'in', {partners.ids!r})]",
                "group_by_field_id": country_field.id,
                "sub_group_by_field_id": industry_field.id,
            }
        )
        rows = data_source._fetch_data(self.env["dashboard.item"])
        # Country A has two distinct industries (2 rows), country B has a
        # single industry (1 row) -> 3 combinations.
        self.assertEqual(len(rows), 3)
        combos = {
            (row["group_label"], row["sub_group_label"]): row["__count"] for row in rows
        }
        self.assertEqual(combos[(country_a.display_name, industry_x.display_name)], 1)
        self.assertEqual(combos[(country_a.display_name, industry_y.display_name)], 1)
        self.assertEqual(combos[(country_b.display_name, industry_y.display_name)], 2)
        for row in rows:
            self.assertIn("sub_group_key", row)
            self.assertIn("sub_group_label", row)

    def test_fetch_data_orm_single_dimension_has_no_sub_group_keys(self):
        """Python murni — pemicu P1 (L-01, L-02).

        Data source dengan satu dimensi (tanpa `sub_group_by_field_id`)
        harus mengembalikan baris tanpa kunci `sub_group_key`/
        `sub_group_label` sama sekali — bukan bernilai `False`. Hanya bisa
        diverifikasi dengan `assertNotIn` atas dict hasil pemanggilan
        method langsung (L-01/L-02).
        """
        partner_model = self.env.ref("base.model_res_partner")
        country_field = self.env["ir.model.fields"].search(
            [("model", "=", "res.partner"), ("name", "=", "country_id")],
            limit=1,
        )
        country_a = self.env.ref("base.us")
        partners = self.env["res.partner"].create(
            [{"name": "Single Dim Partner 1", "country_id": country_a.id}]
        )
        data_source = self.env["dashboard.data_source"].create(
            {
                "name": "Partners By Country Single Dim",
                "code": "DASH-SUBGROUPBY-NONE-01",
                "type": "orm",
                "model_id": partner_model.id,
                "domain": f"[('id', 'in', {partners.ids!r})]",
                "group_by_field_id": country_field.id,
            }
        )
        rows = data_source._fetch_data(self.env["dashboard.item"])
        self.assertEqual(len(rows), 1)
        self.assertNotIn("sub_group_key", rows[0])
        self.assertNotIn("sub_group_label", rows[0])

    def test_fetch_data_orm_fill_temporal_uses_custom_date_range_bounds(self):
        """Python murni — pemicu P3 (L-02).

        `date_range` = `custom` (bukan `all_time`) harus membuat rentang
        pengisian `fill_temporal` mengikuti `Date Start`/`Date End`
        secara langsung — bukan cuma periode terkecil/terbesar yang ada
        di data. Rentang kustom sengaja dibuat lebih lebar dari data
        (November 2025 s.d. April 2026, data hanya Januari & Maret 2026)
        untuk membuktikan itu, melatih cabang kode berbeda dari test
        `fill_temporal` lain di atas yang semuanya memakai `date_range`
        default `all_time`.
        """
        currency_rate_model = self.env.ref("base.model_res_currency_rate")
        date_field = self.env["ir.model.fields"].search(
            [("model", "=", "res.currency.rate"), ("name", "=", "name")],
            limit=1,
        )
        currency = self.env.ref("base.EUR")
        rates = self.env["res.currency.rate"].create(
            [
                {"currency_id": currency.id, "name": "2026-01-15", "rate": 1.1},
                {"currency_id": currency.id, "name": "2026-03-10", "rate": 1.3},
            ]
        )
        data_source = self.env["dashboard.data_source"].create(
            {
                "name": "Rates By Month Filled Custom Range",
                "code": "DASH-FILLTEMPORAL-CUSTOMRANGE-01",
                "type": "orm",
                "model_id": currency_rate_model.id,
                "domain": f"[('id', 'in', {rates.ids!r})]",
                "group_by_field_id": date_field.id,
                "group_by_granularity": "month",
                "fill_temporal": True,
                "date_range": "custom",
                "date_start": "2025-11-01",
                "date_end": "2026-04-30",
            }
        )
        rows = data_source._fetch_data(self.env["dashboard.item"])
        self.assertEqual(len(rows), 6)
        counts_by_label = {row["group_label"]: row["__count"] for row in rows}
        self.assertEqual(counts_by_label.get("November 2025"), 0)
        self.assertEqual(counts_by_label.get("December 2025"), 0)
        self.assertEqual(counts_by_label.get("January 2026"), 1)
        self.assertEqual(counts_by_label.get("February 2026"), 0)
        self.assertEqual(counts_by_label.get("March 2026"), 1)

    def test_prepare_comparison_date_range_none_returns_empty_list(self):
        """Python murni — pemicu P1 (L-01, L-02).

        `_prepare_comparison_date_range` mengembalikan `list` yang hanya
        bisa diverifikasi dengan meng-assert nilai balik method secara
        langsung; YAML tidak menyimpan nilai balik `action: call` (L-01)
        dan tidak bisa meng-assert ekspresi bebas seperti panjang list
        (L-02). `comparison` defaultnya `none`, jadi data source ini
        tidak perlu `date_field_id`.
        """
        data_source = self.env["dashboard.data_source"].create(
            {
                "name": "No Comparison Source",
                "code": "DASH-COMPARISON-NONE-01",
            }
        )
        self.assertEqual(data_source._prepare_comparison_date_range(), [])

    def test_prepare_comparison_date_range_previous_period_shifts_by_duration(self):
        """Python murni — pemicu P1 (L-01, L-02).

        Sama seperti di atas: nilai balik `_prepare_comparison_date_range`
        (2-tuple tanggal pembanding) hanya bisa diverifikasi dengan
        meng-assert nilai balik method secara langsung. Rentang berjalan
        1-31 Januari 2026 dibandingkan dengan rentang sepanjang yang
        sama tepat sebelum 1 Januari 2026, yaitu 1-31 Desember 2025 —
        membuktikan pergeserannya dihitung dari durasi hasil
        `_prepare_date_range()`, bukan dari kalender bulan.
        """
        currency_rate_model = self.env.ref("base.model_res_currency_rate")
        date_field = self.env["ir.model.fields"].search(
            [("model", "=", "res.currency.rate"), ("name", "=", "name")],
            limit=1,
        )
        data_source = self.env["dashboard.data_source"].create(
            {
                "name": "Previous Period Source",
                "code": "DASH-COMPARISON-PREVPERIOD-01",
                "type": "orm",
                "model_id": currency_rate_model.id,
                "date_field_id": date_field.id,
                "date_range": "custom",
                "date_start": "2026-01-01",
                "date_end": "2026-01-31",
                "comparison": "previous_period",
            }
        )
        self.assertEqual(
            data_source._prepare_comparison_date_range(),
            [(datetime.date(2025, 12, 1), datetime.date(2025, 12, 31))],
        )

    def test_prepare_comparison_date_range_previous_year_two_ranges(self):
        """Python murni — pemicu P1 (L-01, L-02).

        `comparison_year_count` = 2 harus menghasilkan dua tuple
        rentang, satu per tahun ke belakang, dengan tanggal awal/akhir
        yang sama persis — hanya bisa diverifikasi lewat nilai balik
        method (lihat docstring test di atas).
        """
        currency_rate_model = self.env.ref("base.model_res_currency_rate")
        date_field = self.env["ir.model.fields"].search(
            [("model", "=", "res.currency.rate"), ("name", "=", "name")],
            limit=1,
        )
        data_source = self.env["dashboard.data_source"].create(
            {
                "name": "Previous Year Source",
                "code": "DASH-COMPARISON-PREVYEAR-01",
                "type": "orm",
                "model_id": currency_rate_model.id,
                "date_field_id": date_field.id,
                "date_range": "custom",
                "date_start": "2026-03-01",
                "date_end": "2026-03-31",
                "comparison": "previous_year",
                "comparison_year_count": 2,
            }
        )
        self.assertEqual(
            data_source._prepare_comparison_date_range(),
            [
                (datetime.date(2025, 3, 1), datetime.date(2025, 3, 31)),
                (datetime.date(2024, 3, 1), datetime.date(2024, 3, 31)),
            ],
        )
        self.assertEqual(counts_by_label.get("April 2026"), 0)
