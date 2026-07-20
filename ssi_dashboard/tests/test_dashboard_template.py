# Copyright 2026 OpenSynergy Indonesia
# Copyright 2026 PT. Simetri Sinergi Indonesia
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from odoo_yaml_test import YamlTransactionCase
from psycopg2 import IntegrityError

from odoo.tests import tagged
from odoo.tools import mute_logger


@tagged("post_install", "-at_install")
class TestDashboardTemplate(YamlTransactionCase):
    def test_dashboard_template(self):
        self.run_yaml_scenario("test_data_dashboard_template.yaml")

    def test_create_duplicate_code_raises_integrity_error(self):
        """Python murni — pemicu P5 (L-22).

        `code` memakai `models.Constraint("UNIQUE(code)", ...)`, constraint
        tingkat database. Membuat template kedua dengan `code` yang sama
        melempar `psycopg2.errors.UniqueViolation` (subclass
        `psycopg2.IntegrityError`), tipe yang tidak termasuk 12 tipe yang
        dikenali `expect_error` (L-22), sehingga tidak bisa diuji lewat
        YAML. `mute_logger` membungkam log ERROR `odoo.sql_db` yang normal
        muncul saat Postgres menolak query ini — errornya memang
        diharapkan dan sudah ditangkap lewat `assertRaises`, bukan
        kebocoran nyata yang harus menggagalkan `oca_checklog_odoo` di CI.
        """
        source = self.env["dashboard.dashboard"].create(
            {"name": "Mold", "code": "TPL-DUP-SOURCE-01"}
        )
        self.env["dashboard.template"].create(
            {
                "name": "First",
                "code": "TPL-DUP-01",
                "source_dashboard_id": source.id,
            }
        )
        with mute_logger("odoo.sql_db"), self.assertRaises(IntegrityError):
            with self.env.cr.savepoint():
                self.env["dashboard.template"].create(
                    {
                        "name": "Second",
                        "code": "TPL-DUP-01",
                        "source_dashboard_id": source.id,
                    }
                )
