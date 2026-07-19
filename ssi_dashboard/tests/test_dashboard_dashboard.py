# Copyright 2026 OpenSynergy Indonesia
# Copyright 2026 PT. Simetri Sinergi Indonesia
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from odoo_yaml_test import YamlTransactionCase
from psycopg2 import IntegrityError

from odoo.tests import tagged


@tagged("post_install", "-at_install")
class TestDashboardDashboard(YamlTransactionCase):
    def test_dashboard_dashboard(self):
        self.run_yaml_scenario("test_data_dashboard_dashboard.yaml")

    def test_get_dashboard_payload_returns_expected_keys(self):
        """Python murni — pemicu P1 (L-01, L-02).

        `get_dashboard_payload` diuji lewat nilai balik method (dict
        payload render), bukan efek sampingnya pada record. `action: call`
        di YAML membuang nilai balik method (L-01), dan sisi actual sebuah
        assert selalu berupa dotted `getattr` pada record (L-02) — isi
        dict hasil method (termasuk list `items` bersarang) tidak bisa
        diverifikasi lewat YAML sama sekali.
        """
        color_scheme = self.env["dashboard.color_scheme"].create(
            {
                "name": "Palette",
                "code": "DASH-PAYLOAD-CS-01",
                "color_ids": [(0, 0, {"key": "primary", "value": "#1f6feb"})],
            }
        )
        data_source = self.env["dashboard.data_source"].create(
            {
                "name": "Partners",
                "code": "DASH-PAYLOAD-DS-01",
                "type": "orm",
                "model_id": self.env["ir.model"]._get("res.partner").id,
            }
        )
        dashboard = self.env["dashboard.dashboard"].create(
            {
                "name": "Payload Dashboard",
                "code": "DASH-PAYLOAD-01",
                "color_scheme_id": color_scheme.id,
                "item_ids": [
                    (
                        0,
                        0,
                        {
                            "name": "Item A",
                            "type": "placeholder",
                            "data_source_id": data_source.id,
                        },
                    )
                ],
            }
        )
        payload = dashboard.get_dashboard_payload()
        self.assertEqual(payload["id"], dashboard.id)
        self.assertEqual(payload["name"], "Payload Dashboard")
        self.assertEqual(
            payload["color_scheme"], {"--ssi-dashboard-primary": "#1f6feb"}
        )
        self.assertEqual(len(payload["items"]), 1)
        self.assertEqual(payload["items"][0]["name"], "Item A")

    def test_unlink_referenced_color_scheme_raises_integrity_error(self):
        """Python murni — pemicu P5 (L-22).

        `color_scheme_id` memakai `ondelete="restrict"`, ditegakkan lewat
        foreign key asli di database. Menghapus record yang masih dirujuk
        melempar `psycopg2.errors.ForeignKeyViolation` (subclass
        `psycopg2.IntegrityError`), tipe yang tidak termasuk 12 tipe yang
        dikenali `expect_error` (L-22), sehingga tidak bisa diuji lewat
        YAML.
        """
        color_scheme = self.env["dashboard.color_scheme"].create(
            {"name": "Referenced", "code": "DASH-RESTRICT-CS-01"}
        )
        self.env["dashboard.dashboard"].create(
            {
                "name": "Referencing Dashboard",
                "code": "DASH-RESTRICT-01",
                "color_scheme_id": color_scheme.id,
            }
        )
        with self.assertRaises(IntegrityError):
            with self.env.cr.savepoint():
                color_scheme.unlink()
