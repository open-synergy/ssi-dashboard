# Copyright 2026 OpenSynergy Indonesia
# Copyright 2026 PT. Simetri Sinergi Indonesia
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from odoo_yaml_test import YamlTransactionCase
from psycopg2 import IntegrityError

from odoo.tests import tagged
from odoo.tools import mute_logger


@tagged("post_install", "-at_install")
class TestDashboardColorSchemeSsi(YamlTransactionCase):
    def test_dashboard_color_scheme_ssi(self):
        self.run_yaml_scenario("test_data_dashboard_color_scheme_ssi.yaml")

    @mute_logger("odoo.sql_db")
    def test_duplicate_color_key_raises_integrity_error(self):
        """Python murni — pemicu P5 (L-22, L-23).

        Constraint unik ``UNIQUE(color_scheme_id, key)`` pada
        ``dashboard.color_scheme.color`` bekerja di tingkat database dan
        melempar ``psycopg2.IntegrityError``, sebuah tipe yang tidak
        termasuk 12 tipe yang dikenali `expect_error` (L-22), dan pesannya
        tidak bisa dicocokkan lewat `message_contains` polos tanpa regex
        (L-23). Negative path ini karenanya tidak bisa ditulis di YAML.
        """
        color_scheme = self.env["dashboard.color_scheme"].create(
            {
                "name": "Duplicate Key Scheme",
                "code": "CS-P5-01",
                "color_ids": [
                    (0, 0, {"key": "primary", "value": "#111111"}),
                ],
            }
        )
        with self.assertRaises(IntegrityError), self.cr.savepoint():
            self.env["dashboard.color_scheme.color"].create(
                {
                    "color_scheme_id": color_scheme.id,
                    "key": "primary",
                    "value": "#222222",
                }
            )

    def test_prepare_css_variables_on_seeded_ssi_light(self):
        """Python murni — pemicu P1 (L-01, L-02).

        `_prepare_css_variables` diuji lewat nilai balik method (dict CSS
        variable) dari tema ``ssi_light`` yang disemai modul ini, bukan
        lewat efek sampingnya pada record. `action: call` di YAML
        membuang nilai balik method (L-01), dan sisi actual sebuah assert
        selalu berupa dotted `getattr` pada record (L-02) — isi dict hasil
        method tidak bisa diverifikasi lewat YAML sama sekali.
        """
        color_scheme = self.env.ref(
            "ssi_dashboard_color_scheme_ssi.dashboard_color_scheme_ssi_light"
        )
        css_variables = color_scheme._prepare_css_variables()
        self.assertIn("--ssi-dashboard-primary", css_variables)
        self.assertEqual(css_variables["--ssi-dashboard-primary"], "#1f6feb")

    def test_prepare_css_variables_chart_8_on_seeded_ssi_dark(self):
        """Python murni — pemicu P1 (L-01, L-02).

        `_prepare_css_variables` diuji lewat nilai balik method (dict CSS
        variable) dari tema ``ssi_dark``, membuktikan seluruh delapan key
        deret chart (``chart-1``..``chart-8``) menghasilkan CSS custom
        property. `action: call` di YAML membuang nilai balik method
        (L-01), dan sisi actual sebuah assert selalu berupa dotted
        `getattr` pada record (L-02) — isi dict hasil method tidak bisa
        diverifikasi lewat YAML sama sekali.
        """
        color_scheme = self.env.ref(
            "ssi_dashboard_color_scheme_ssi.dashboard_color_scheme_ssi_dark"
        )
        css_variables = color_scheme._prepare_css_variables()
        self.assertIn("--ssi-dashboard-chart-8", css_variables)

    def test_chart_1_equals_primary_on_ssi_light(self):
        """Python murni — pemicu P1 (L-01, L-02).

        Nilai ``chart-1`` dibandingkan dengan nilai ``primary`` lewat dict
        hasil `_prepare_css_variables()` (nilai balik method) pada tema
        ``ssi_light``, sesuai Keputusan Desain: chart deret tunggal wajib
        menyatu dengan identitas dashboard. `action: call` di YAML
        membuang nilai balik method (L-01), dan sisi actual sebuah assert
        selalu berupa dotted `getattr` pada record (L-02) — perbandingan
        dua entri dict hasil method tidak bisa diverifikasi lewat YAML.
        """
        color_scheme = self.env.ref(
            "ssi_dashboard_color_scheme_ssi.dashboard_color_scheme_ssi_light"
        )
        css_variables = color_scheme._prepare_css_variables()
        self.assertEqual(
            css_variables["--ssi-dashboard-chart-1"],
            css_variables["--ssi-dashboard-primary"],
        )

    @mute_logger("odoo.sql_db")
    def test_duplicate_chart_1_key_on_ssi_light_raises_integrity_error(self):
        """Python murni — pemicu P5 (L-22, L-23).

        Constraint unik ``UNIQUE(color_scheme_id, key)`` juga berlaku
        untuk baris ``chart-1`` yang baru disemai pada palet ``ssi_light``
        — melempar ``psycopg2.IntegrityError``, sebuah tipe yang tidak
        termasuk 12 tipe yang dikenali `expect_error` (L-22), dan
        pesannya tidak bisa dicocokkan lewat `message_contains` polos
        tanpa regex (L-23). Negative path ini karenanya tidak bisa
        ditulis di YAML.
        """
        color_scheme = self.env.ref(
            "ssi_dashboard_color_scheme_ssi.dashboard_color_scheme_ssi_light"
        )
        with self.assertRaises(IntegrityError), self.cr.savepoint():
            self.env["dashboard.color_scheme.color"].create(
                {
                    "color_scheme_id": color_scheme.id,
                    "key": "chart-1",
                    "value": "#000000",
                }
            )
