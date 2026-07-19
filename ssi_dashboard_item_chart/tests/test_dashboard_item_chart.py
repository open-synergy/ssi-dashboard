# Copyright 2026 OpenSynergy Indonesia
# Copyright 2026 PT. Simetri Sinergi Indonesia
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
import json

from odoo_yaml_test import YamlTransactionCase

from odoo.tests import tagged


@tagged("post_install", "-at_install")
class TestDashboardItemChart(YamlTransactionCase):
    def test_dashboard_item_chart(self):
        self.run_yaml_scenario("test_data_dashboard_item_chart.yaml")

    def test_prepare_render_payload_chart_labels_and_datasets(self):
        """Python murni — P1: assert nilai balik `_prepare_render_payload_chart`.

        `action: call` YAML membuang nilai balik method (L-01) dan assert
        YAML hanya bisa dotted `getattr` atas record (L-02), sedangkan yang
        diuji di sini adalah isi dict yang dikembalikan langsung oleh
        `_prepare_render_payload_chart()` — kunci `chart_type`/`chart_data`
        harus ada, dan `chart_data`'s `labels`/`datasets` harus berisi hasil
        pengelompokan yang benar (L-07: isi dict per-kunci tak terjangkau
        assert YAML).
        """
        data_source = self.env["dashboard.data_source"].create(
            {
                "name": "Partners",
                "code": "DASH-CHART-PY-DS-01",
                "type": "orm",
                "model_id": self.env.ref("base.model_res_partner").id,
            }
        )
        dashboard = self.env["dashboard.dashboard"].create(
            {"name": "Chart Dashboard", "code": "DASH-CHART-PY-01"}
        )
        item = self.env["dashboard.item"].create(
            {
                "name": "Amount by State",
                "dashboard_id": dashboard.id,
                "type": "chart",
                "data_source_id": data_source.id,
                "config": json.dumps(
                    {"chart_type": "line", "group_by": "state", "measure": "amount"}
                ),
            }
        )
        rows = [
            {"state": "draft", "amount": 10},
            {"state": "done", "amount": 5},
            {"state": "draft", "amount": 7},
        ]

        payload = item._prepare_render_payload_chart({"data": rows})

        self.assertIn("chart_type", payload)
        self.assertIn("chart_data", payload)
        self.assertEqual(payload["chart_type"], "line")
        self.assertEqual(payload["chart_data"]["labels"], ["draft", "done"])
        self.assertEqual(
            payload["chart_data"]["datasets"],
            [{"label": "Amount by State", "data": [17, 5]}],
        )

    def test_prepare_render_payload_chart_default_type_and_count(self):
        """Python murni — P1: default `chart_type` dan agregasi 'count'.

        Melengkapi test di atas: `chart_type` default ('bar') saat tak
        disebut di `Config`, dan tanpa `measure` tiap grup dihitung jumlah
        baris-nya, bukan dijumlahkan.
        """
        data_source = self.env["dashboard.data_source"].create(
            {
                "name": "Partners",
                "code": "DASH-CHART-PY-DS-02",
                "type": "orm",
                "model_id": self.env.ref("base.model_res_partner").id,
            }
        )
        dashboard = self.env["dashboard.dashboard"].create(
            {"name": "Chart Dashboard 2", "code": "DASH-CHART-PY-02"}
        )
        item = self.env["dashboard.item"].create(
            {
                "name": "Count by State",
                "dashboard_id": dashboard.id,
                "type": "chart",
                "data_source_id": data_source.id,
                "config": json.dumps({"group_by": "state"}),
            }
        )
        rows = [
            {"state": "draft", "amount": 10},
            {"state": "done", "amount": 5},
            {"state": "draft", "amount": 7},
        ]

        payload = item._prepare_render_payload_chart({"data": rows})

        self.assertEqual(payload["chart_type"], "bar")
        self.assertEqual(payload["chart_data"]["labels"], ["draft", "done"])
        self.assertEqual(
            payload["chart_data"]["datasets"],
            [{"label": "Count by State", "data": [2, 1]}],
        )
