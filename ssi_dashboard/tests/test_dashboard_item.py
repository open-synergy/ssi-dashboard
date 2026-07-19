# Copyright 2026 OpenSynergy Indonesia
# Copyright 2026 PT. Simetri Sinergi Indonesia
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from odoo_yaml_test import YamlTransactionCase

from odoo.tests import tagged


@tagged("post_install", "-at_install")
class TestDashboardItem(YamlTransactionCase):
    def test_dashboard_item(self):
        self.run_yaml_scenario("test_data_dashboard_item.yaml")

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
