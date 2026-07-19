# Copyright 2026 OpenSynergy Indonesia
# Copyright 2026 PT. Simetri Sinergi Indonesia
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from odoo_yaml_test import YamlTransactionCase

from odoo.tests import tagged


@tagged("post_install", "-at_install")
class TestDashboardItemKpi(YamlTransactionCase):
    def test_dashboard_item_kpi(self):
        self.run_yaml_scenario("test_data_dashboard_item_kpi.yaml")

    def _create_kpi_item(self, code_suffix, data_source_values=None, **item_values):
        data_source_vals = {
            "name": "Partners",
            "code": f"DASH-KPI-PY-DS-{code_suffix}",
            "type": "orm",
            "model_id": self.env.ref("base.model_res_partner").id,
        }
        data_source_vals.update(data_source_values or {})
        data_source = self.env["dashboard.data_source"].create(data_source_vals)
        dashboard = self.env["dashboard.dashboard"].create(
            {"name": "KPI Dashboard", "code": f"DASH-KPI-PY-{code_suffix}"}
        )
        values = {
            "name": "Total Partners",
            "dashboard_id": dashboard.id,
            "type": "kpi",
            "data_source_id": data_source.id,
        }
        values.update(item_values)
        return self.env["dashboard.item"].create(values)

    def test_kpi_achievement_and_direction_with_target(self):
        """Python murni — P1: assert nilai balik `_prepare_render_payload_kpi`,
        P2: toleransi float pada `achievement`.

        `action: call` YAML membuang nilai balik method (L-01) dan assert
        YAML hanya bisa dotted `getattr` atas record (L-02), sedangkan
        `kpi` di sini adalah dict biasa yang hanya ada di nilai balik
        method itu sendiri, bukan atribut record. Realisasi 75 atas
        target (fixed) 100 harus menghasilkan `achievement` 0.75 (dengan
        toleransi float, bukan perbandingan exact) dan `direction`
        'down' — sesuai Skenario Uji issue #32.
        """
        item = self._create_kpi_item(
            "01",
            kpi_layout="target",
            goal_type="fixed",
            goal_value=100.0,
        )
        payload = item._prepare_render_payload_kpi({"data": [{"__count": 75}]})
        kpi = payload["kpi"]
        self.assertAlmostEqual(kpi["value"], 75.0)
        self.assertAlmostEqual(kpi["reference"], 100.0)
        self.assertAlmostEqual(kpi["achievement"], 0.75)
        self.assertEqual(kpi["direction"], "down")

    def test_kpi_direction_inverted(self):
        """Python murni — P1: assert nilai balik `_prepare_render_payload_kpi`.

        Item yang sama seperti test di atas (realisasi 75 atas target
        100, yang tanpa `kpi_invert_direction` menghasilkan 'down'), tapi
        dengan `kpi_invert_direction` = True — 'direction' harus terbalik
        menjadi 'up', sesuai Skenario Uji issue #32.
        """
        item = self._create_kpi_item(
            "02",
            kpi_layout="target",
            goal_type="fixed",
            goal_value=100.0,
            kpi_invert_direction=True,
        )
        payload = item._prepare_render_payload_kpi({"data": [{"__count": 75}]})
        self.assertEqual(payload["kpi"]["direction"], "up")

    def test_kpi_achievement_none_when_reference_zero(self):
        """Python murni — P1: assert nilai balik `_prepare_render_payload_kpi`.

        Target (fixed) bernilai 0 harus membuat 'achievement' bernilai
        None, bukan error pembagian oleh nol, sesuai Skenario Uji issue
        #32.
        """
        item = self._create_kpi_item(
            "03",
            kpi_layout="target",
            goal_type="fixed",
            goal_value=0.0,
        )
        payload = item._prepare_render_payload_kpi({"data": [{"__count": 42}]})
        self.assertIsNone(payload["kpi"]["achievement"])

    def test_kpi_reference_uses_first_comparison_range_for_comparison_layout(self):
        """Python murni — P1: assert nilai balik `_prepare_render_payload_kpi`.

        Untuk `kpi_layout` = 'comparison', 'reference' harus dibaca dari
        baris pertama rentang pembanding pertama
        (`payload["comparison_data"][0]`), bukan dari target — melengkapi
        cakupan test achievement/direction di atas (yang hanya menguji
        layout 'target') dengan layout 'comparison'.
        """
        date_field = self.env["ir.model.fields"].search(
            [("model", "=", "res.partner"), ("name", "=", "create_date")], limit=1
        )
        item = self._create_kpi_item(
            "04",
            kpi_layout="comparison",
            data_source_values={
                "comparison": "previous_period",
                "date_field_id": date_field.id,
            },
        )
        payload = item._prepare_render_payload_kpi(
            {
                "data": [{"__count": 120}],
                "comparison_data": [[{"__count": 80}]],
            }
        )
        kpi = payload["kpi"]
        self.assertAlmostEqual(kpi["value"], 120.0)
        self.assertAlmostEqual(kpi["reference"], 80.0)
        self.assertAlmostEqual(kpi["achievement"], 1.5)
        self.assertEqual(kpi["direction"], "up")

    def test_get_kpi_value_returns_zero_when_rows_empty(self):
        """Python murni — P1: assert nilai balik `_get_kpi_value`.

        Sama seperti test di atas (L-01/L-02): baris kosong (data source
        tanpa baris yang cocok) harus membuat nilai 0.0, bukan error.
        """
        item = self._create_kpi_item(
            "05",
            kpi_layout="target",
            goal_type="fixed",
            goal_value=10.0,
        )
        self.assertEqual(item._get_kpi_value([]), 0.0)
