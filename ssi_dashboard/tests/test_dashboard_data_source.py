# Copyright 2026 OpenSynergy Indonesia
# Copyright 2026 PT. Simetri Sinergi Indonesia
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from odoo_yaml_test import YamlTransactionCase
from psycopg2 import IntegrityError

from odoo.exceptions import UserError
from odoo.tests import tagged
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
