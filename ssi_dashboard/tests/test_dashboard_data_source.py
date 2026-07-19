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
