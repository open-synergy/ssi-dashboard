# Copyright 2026 OpenSynergy Indonesia
# Copyright 2026 PT. Simetri Sinergi Indonesia
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
import json

from odoo_yaml_test import YamlTransactionCase

from odoo.tests import tagged


@tagged("post_install", "-at_install")
class TestDashboardItemTile(YamlTransactionCase):
    def test_dashboard_item_tile(self):
        self.run_yaml_scenario("test_data_dashboard_item_tile.yaml")

    def test_prepare_render_payload_tile_count_and_sum(self):
        """Python murni — P1: assert nilai balik `_prepare_render_payload_tile`.

        `action: call` YAML membuang nilai balik method (L-01) dan assert
        YAML hanya bisa dotted `getattr` atas record (L-02), sedangkan yang
        diuji di sini adalah isi dict yang dikembalikan langsung oleh
        `_prepare_render_payload_tile()` — kunci `value`/`label` harus ada,
        dan `value`-nya harus benar untuk `aggregate` `count` (default) dan
        `sum`.
        """
        data_source = self.env["dashboard.data_source"].create(
            {
                "name": "Partners",
                "code": "DASH-TILE-PY-DS-01",
                "type": "orm",
                "model_id": self.env.ref("base.model_res_partner").id,
            }
        )
        dashboard = self.env["dashboard.dashboard"].create(
            {"name": "Tile Dashboard", "code": "DASH-TILE-PY-01"}
        )
        item = self.env["dashboard.item"].create(
            {
                "name": "Total Amount",
                "dashboard_id": dashboard.id,
                "type": "tile",
                "data_source_id": data_source.id,
            }
        )
        rows = [{"amount": 10}, {"amount": 5}, {"amount": 7}]

        count_payload = item._prepare_render_payload_tile({"data": rows})
        self.assertIn("value", count_payload)
        self.assertIn("label", count_payload)
        self.assertEqual(count_payload["value"], 3)
        self.assertEqual(count_payload["label"], "Total Amount")

        item.config = json.dumps({"measure": "amount", "aggregate": "sum"})
        sum_payload = item._prepare_render_payload_tile({"data": rows})
        self.assertEqual(sum_payload["value"], 22)
        self.assertEqual(sum_payload["label"], "Total Amount")
