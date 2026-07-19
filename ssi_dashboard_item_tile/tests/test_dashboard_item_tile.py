# Copyright 2026 OpenSynergy Indonesia
# Copyright 2026 PT. Simetri Sinergi Indonesia
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from odoo_yaml_test import YamlTransactionCase

from odoo.tests import tagged


@tagged("post_install", "-at_install")
class TestDashboardItemTile(YamlTransactionCase):
    def test_dashboard_item_tile(self):
        self.run_yaml_scenario("test_data_dashboard_item_tile.yaml")

    def test_prepare_render_payload_includes_required_tile_keys(self):
        """Python murni — P1: assert nilai balik `_prepare_render_payload`.

        `action: call` YAML membuang nilai balik method (L-01) dan assert
        YAML hanya bisa dotted `getattr` atas record (L-02), sedangkan
        yang diuji di sini adalah isi dict yang dikembalikan langsung oleh
        `_prepare_render_payload()` — kelima kunci di Kriteria Penerimaan
        (`tile_layout`, `tile_icon`, `tile_background_color`,
        `tile_text_color`, `value`) harus ada, dengan nilai yang mengikuti
        field item-nya, tidak lagi lewat `config` JSON.
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
                "name": "Total Partners",
                "dashboard_id": dashboard.id,
                "type": "tile",
                "data_source_id": data_source.id,
                "tile_icon": "fa-shopping-cart",
                "tile_background_color": "#112233",
                "tile_text_color": "#ffffff",
            }
        )
        payload = item._prepare_render_payload()
        for key in (
            "tile_layout",
            "tile_icon",
            "tile_background_color",
            "tile_text_color",
            "value",
        ):
            self.assertIn(key, payload)
        self.assertEqual(payload["tile_layout"], "layout_1")
        self.assertEqual(payload["tile_icon"], "fa-shopping-cart")
        self.assertEqual(payload["tile_background_color"], "#112233")
        self.assertEqual(payload["tile_text_color"], "#ffffff")
        self.assertNotIn("config", payload)

    def test_prepare_render_payload_tile_uses_first_row_when_grouped(self):
        """Python murni — P1: assert nilai balik `_prepare_render_payload_tile`.

        Sama seperti test di atas: isi payload hanya bisa diperiksa lewat
        nilai balik method (L-01/L-02). Baris yang disuntikkan di sini
        meniru bentuk baris ber-grup yang dibangun
        `dashboard.data_source._fetch_data_orm` ('group_key'/'group_label'
        + satu kolom measure) — tile harus memakai baris pertama dan
        mengabaikan sisanya (Kriteria Penerimaan: "Tile tetap dirender
        saat data source mengembalikan lebih dari satu baris").
        """
        data_source = self.env["dashboard.data_source"].create(
            {
                "name": "Partners",
                "code": "DASH-TILE-PY-DS-02",
                "type": "orm",
                "model_id": self.env.ref("base.model_res_partner").id,
            }
        )
        dashboard = self.env["dashboard.dashboard"].create(
            {"name": "Tile Dashboard Grouped", "code": "DASH-TILE-PY-02"}
        )
        item = self.env["dashboard.item"].create(
            {
                "name": "Grouped Tile",
                "dashboard_id": dashboard.id,
                "type": "tile",
                "data_source_id": data_source.id,
            }
        )
        rows = [
            {"group_key": 1, "group_label": "A", "__count": 10},
            {"group_key": 2, "group_label": "B", "__count": 20},
            {"group_key": 3, "group_label": "C", "__count": 30},
        ]
        payload = item._prepare_render_payload_tile({"data": rows})
        self.assertEqual(payload["value"], 10)

    def test_get_tile_value_returns_zero_when_data_empty(self):
        """Python murni — P1: assert nilai balik `_get_tile_value`.

        Sama seperti test di atas (L-01/L-02): `data` kosong (data source
        tanpa baris yang cocok) harus membuat 'value' bernilai 0, bukan
        error, mengikuti dokumentasi method.
        """
        data_source = self.env["dashboard.data_source"].create(
            {
                "name": "Partners",
                "code": "DASH-TILE-PY-DS-03",
                "type": "orm",
                "model_id": self.env.ref("base.model_res_partner").id,
            }
        )
        dashboard = self.env["dashboard.dashboard"].create(
            {"name": "Tile Dashboard Empty", "code": "DASH-TILE-PY-03"}
        )
        item = self.env["dashboard.item"].create(
            {
                "name": "Empty Tile",
                "dashboard_id": dashboard.id,
                "type": "tile",
                "data_source_id": data_source.id,
            }
        )
        self.assertEqual(item._get_tile_value([]), 0)
