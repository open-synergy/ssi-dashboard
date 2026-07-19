# Copyright 2026 OpenSynergy Indonesia
# Copyright 2026 PT. Simetri Sinergi Indonesia
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from odoo_yaml_test import YamlTransactionCase

from odoo.tests import tagged


@tagged("post_install", "-at_install")
class TestDashboardColorScheme(YamlTransactionCase):
    def test_dashboard_color_scheme(self):
        self.run_yaml_scenario("test_data_dashboard_color_scheme.yaml")

    def test_prepare_css_variables_returns_dict(self):
        """Python murni — pemicu P1 (L-01, L-02).

        `_prepare_css_variables` diuji lewat nilai balik method (dict CSS
        variable), bukan efek sampingnya pada record. `action: call` di
        YAML membuang nilai balik method (L-01), dan sisi actual sebuah
        assert selalu berupa dotted `getattr` pada record (L-02) — isi
        dict hasil method tidak bisa diverifikasi lewat YAML sama sekali.
        """
        color_scheme = self.env["dashboard.color_scheme"].create(
            {
                "name": "Palette",
                "code": "CS-P1-01",
                "color_ids": [
                    (0, 0, {"key": "primary", "value": "#1f6feb"}),
                    (0, 0, {"key": "secondary", "value": "#6c757d"}),
                ],
            }
        )
        css_variables = color_scheme._prepare_css_variables()
        self.assertEqual(
            css_variables,
            {
                "--ssi-dashboard-primary": "#1f6feb",
                "--ssi-dashboard-secondary": "#6c757d",
            },
        )
