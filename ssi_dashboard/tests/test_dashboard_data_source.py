# Copyright 2026 OpenSynergy Indonesia
# Copyright 2026 PT. Simetri Sinergi Indonesia
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from odoo_yaml_test import YamlTransactionCase
from psycopg2 import IntegrityError

from odoo.exceptions import UserError
from odoo.tests import tagged


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
        (L-22), sehingga tidak bisa diuji lewat YAML.
        """
        self.env["dashboard.data_source"].create(
            {"name": "First", "code": "DASH-DUP-01"}
        )
        with self.assertRaises(IntegrityError):
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
