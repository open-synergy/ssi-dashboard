# Copyright 2026 OpenSynergy Indonesia
# Copyright 2026 PT. Simetri Sinergi Indonesia
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from odoo_yaml_test import YamlTransactionCase
from psycopg2 import IntegrityError

from odoo.tests import tagged
from odoo.tools import mute_logger


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

    def test_get_dashboard_payload_refresh_interval_is_int(self):
        """Python murni — pemicu P1 (L-01, L-02).

        `get_dashboard_payload` diuji lewat nilai balik method (kunci
        `refresh_interval` di dalam dict payload, hasil konversi
        `int(self.refresh_interval)`). `action: call` di YAML membuang
        nilai balik method (L-01), dan sisi actual sebuah assert selalu
        berupa dotted `getattr` pada record (L-02) — isi dict hasil
        method tidak bisa diverifikasi lewat YAML sama sekali, dan tipe
        Python (`int` vs `str`) juga tidak bisa dibedakan lewat YAML.
        """
        dashboard = self.env["dashboard.dashboard"].create(
            {
                "name": "Refresh Payload Dashboard",
                "code": "DASH-PAYLOAD-REFRESH-01",
                "refresh_interval": "300",
            }
        )
        payload = dashboard.get_dashboard_payload()
        self.assertEqual(payload["refresh_interval"], 300)
        self.assertIsInstance(payload["refresh_interval"], int)

    def test_get_dashboard_payload_refresh_interval_off_is_zero(self):
        """Python murni — pemicu P1 (L-01, L-02).

        Sama seperti di atas: nilai balik method, bukan efek samping pada
        record, jadi tidak bisa diuji lewat YAML (L-01, L-02).
        """
        dashboard = self.env["dashboard.dashboard"].create(
            {"name": "Refresh Off Dashboard", "code": "DASH-PAYLOAD-REFRESH-OFF-01"}
        )
        payload = dashboard.get_dashboard_payload()
        self.assertEqual(payload["refresh_interval"], 0)

    def test_action_open_dashboard_returns_client_action(self):
        """Python murni — pemicu P1 (L-01, L-02).

        `action_open_dashboard` diuji lewat nilai balik method (dict
        `ir.actions.client`), sedangkan `action: call` di YAML membuang
        nilai balik method (L-01) dan sisi actual sebuah assert selalu
        berupa dotted `getattr` pada record, bukan pada dict hasil method
        (L-02).
        """
        dashboard = self.env["dashboard.dashboard"].create(
            {"name": "Action Dashboard", "code": "DASH-ACTION-01"}
        )
        action = dashboard.action_open_dashboard()
        self.assertEqual(action["type"], "ir.actions.client")
        self.assertEqual(action["tag"], "ssi_dashboard.dashboard_view")
        self.assertEqual(action["context"]["dashboard_id"], dashboard.id)

    def test_save_layout_writes_coordinates_and_returns_true(self):
        """Python murni — pemicu P1 (L-01, L-02).

        `save_layout` diuji lewat nilai balik method (harus `True`,
        Kriteria Penerimaan) sekaligus lewat field yang benar-benar
        tertulis di `dashboard.item` setelah dipanggil. `action: call`
        di YAML membuang nilai balik method (L-01) dan sisi actual
        sebuah assert selalu berupa dotted `getattr` pada record
        (L-02) — 'nilai balik `True`' pada bagian ini tidak bisa
        diverifikasi lewat YAML sama sekali. Berjalan sebagai
        `self.env.user` bawaan `TransactionCase` (OdooBot/uid=1), yang
        menjadi anggota `group_dashboard_admin` lewat
        `security/res_groups/dashboard.xml` (`base.user_root`), jadi
        `_check_save_layout_access` lolos di sini tanpa perlu
        membuat user tambahan.
        """
        data_source = self.env["dashboard.data_source"].create(
            {
                "name": "Partners",
                "code": "DASH-SAVE-LAYOUT-DS-01",
                "type": "orm",
                "model_id": self.env["ir.model"]._get("res.partner").id,
            }
        )
        dashboard = self.env["dashboard.dashboard"].create(
            {"name": "Save Layout Dashboard", "code": "DASH-SAVE-LAYOUT-01"}
        )
        item = self.env["dashboard.item"].create(
            {
                "name": "Item A",
                "dashboard_id": dashboard.id,
                "type": "placeholder",
                "data_source_id": data_source.id,
            }
        )
        result = dashboard.save_layout(
            [
                {
                    "id": item.id,
                    "column_start": 3,
                    "row_start": 2,
                    "column_width": 5,
                    "row_height": 4,
                }
            ]
        )
        self.assertTrue(result)
        self.assertEqual(item.column_start, 3)
        self.assertEqual(item.row_start, 2)
        self.assertEqual(item.column_width, 5)
        self.assertEqual(item.row_height, 4)

    def test_unlink_referenced_color_scheme_raises_integrity_error(self):
        """Python murni — pemicu P5 (L-22).

        `color_scheme_id` memakai `ondelete="restrict"`, ditegakkan lewat
        foreign key asli di database. Menghapus record yang masih dirujuk
        melempar `psycopg2.errors.ForeignKeyViolation` (subclass
        `psycopg2.IntegrityError`), tipe yang tidak termasuk 12 tipe yang
        dikenali `expect_error` (L-22), sehingga tidak bisa diuji lewat
        YAML. `mute_logger` membungkam log ERROR `odoo.sql_db` yang normal
        muncul saat Postgres menolak query ini — errornya memang
        diharapkan dan sudah ditangkap lewat `assertRaises`, bukan
        kebocoran nyata yang harus menggagalkan `oca_checklog_odoo` di CI.
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
        with mute_logger("odoo.sql_db"), self.assertRaises(IntegrityError):
            with self.env.cr.savepoint():
                color_scheme.unlink()
