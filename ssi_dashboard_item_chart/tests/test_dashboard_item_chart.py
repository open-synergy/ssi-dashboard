# Copyright 2026 OpenSynergy Indonesia
# Copyright 2026 PT. Simetri Sinergi Indonesia
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from odoo_yaml_test import YamlTransactionCase

from odoo.tests import tagged


@tagged("post_install", "-at_install")
class TestDashboardItemChart(YamlTransactionCase):
    def test_dashboard_item_chart(self):
        self.run_yaml_scenario("test_data_dashboard_item_chart.yaml")

    def _create_chart_item(self, model_xml_id, group_by_name, sub_group_by_name=None):
        """Shared helper: build a data source (with an optional second
        grouping dimension) and a chart item on top of it, without going
        through a real ``_fetch_data_orm`` query — every test below feeds
        its own synthetic ``data`` rows straight into
        ``_prepare_render_payload_chart``.

        :param model_xml_id: xml id of the ``ir.model`` the data source
            targets.
        :param group_by_name: field name (of that model) used as 'Group
            By Field'.
        :param sub_group_by_name: optional field name used as 'Sub Group
            By Field'.
        :return: the created ``dashboard.item`` record.
        """
        model = self.env.ref(model_xml_id)
        fields_model = self.env["ir.model.fields"]
        group_by_field = fields_model.search(
            [("model_id", "=", model.id), ("name", "=", group_by_name)], limit=1
        )
        values = {
            "name": "Partners",
            "code": f"DASH-CHART-PY-DS-{group_by_name}-{sub_group_by_name}",
            "type": "orm",
            "model_id": model.id,
            "group_by_field_id": group_by_field.id,
        }
        if sub_group_by_name:
            sub_group_by_field = fields_model.search(
                [("model_id", "=", model.id), ("name", "=", sub_group_by_name)],
                limit=1,
            )
            values["sub_group_by_field_id"] = sub_group_by_field.id
        data_source = self.env["dashboard.data_source"].create(values)
        dashboard = self.env["dashboard.dashboard"].create(
            {"name": "Chart Dashboard", "code": f"DASH-CHART-PY-{values['code']}"}
        )
        return self.env["dashboard.item"].create(
            {
                "name": "Chart Item",
                "dashboard_id": dashboard.id,
                "type": "chart",
                "data_source_id": data_source.id,
            }
        )

    def test_chart_payload_two_dimensions_one_dataset_per_sub_group(self):
        """Python murni — P1/P3: nilai balik `_prepare_render_payload_chart`
        dan isi/urutan `datasets`/`labels`-nya.

        `action: call` YAML membuang nilai balik method (L-01), dan urutan
        serta isi list `datasets`/`data` tak terjangkau assert YAML biasa
        (L-07). Data source berdimensi dua (dua negara x dua tipe partner),
        kombinasi Singapore/Individual sengaja tidak ada datanya untuk
        membuktikan itu terisi 0, bukan hilang dari deret.
        """
        item = self._create_chart_item(
            "base.model_res_partner", "country_id", "company_type"
        )
        rows = [
            {"group_label": "Indonesia", "sub_group_label": "Company", "__count": 3},
            {
                "group_label": "Indonesia",
                "sub_group_label": "Individual",
                "__count": 5,
            },
            {"group_label": "Singapore", "sub_group_label": "Company", "__count": 2},
            # Singapore / Individual intentionally absent.
        ]

        payload = item._prepare_render_payload_chart({"data": rows})

        self.assertIn("chart", payload)
        chart = payload["chart"]
        self.assertEqual(chart["type"], "bar")
        self.assertTrue(chart["show_legend"])
        self.assertEqual(chart["labels"], ["Indonesia", "Singapore"])
        self.assertEqual(
            chart["datasets"],
            [
                {"label": "Company", "data": [3, 2]},
                {"label": "Individual", "data": [5, 0]},
            ],
        )
        for dataset in chart["datasets"]:
            self.assertEqual(len(dataset["data"]), len(chart["labels"]))

    def test_chart_payload_one_dimension_two_measures_one_dataset_per_measure(self):
        """Python murni — P1/P3: multi-measure tanpa dimensi kedua
        menghasilkan satu dataset per measure, dengan label diambil dari
        nama measure.
        """
        model = self.env.ref("base.model_res_partner")
        fields_model = self.env["ir.model.fields"]
        group_by_field = fields_model.search(
            [("model_id", "=", model.id), ("name", "=", "country_id")], limit=1
        )
        numeric_field_a = fields_model.search(
            [
                ("model_id", "=", model.id),
                ("ttype", "in", ["integer", "float", "monetary"]),
            ],
            order="id asc",
            limit=1,
        )
        numeric_field_b = fields_model.search(
            [
                ("model_id", "=", model.id),
                ("ttype", "in", ["integer", "float", "monetary"]),
            ],
            order="id desc",
            limit=1,
        )
        data_source = self.env["dashboard.data_source"].create(
            {
                "name": "Partners",
                "code": "DASH-CHART-PY-DS-MULTI-MEASURE",
                "type": "orm",
                "model_id": model.id,
                "group_by_field_id": group_by_field.id,
                "measure_ids": [
                    (
                        0,
                        0,
                        {
                            "name": "Measure A",
                            "aggregate": "sum",
                            "field_id": numeric_field_a.id,
                        },
                    ),
                    (
                        0,
                        0,
                        {
                            "name": "Measure B",
                            "aggregate": "sum",
                            "field_id": numeric_field_b.id,
                        },
                    ),
                ],
            }
        )
        dashboard = self.env["dashboard.dashboard"].create(
            {"name": "Chart Dashboard", "code": "DASH-CHART-PY-MULTI-MEASURE"}
        )
        item = self.env["dashboard.item"].create(
            {
                "name": "Chart Item",
                "dashboard_id": dashboard.id,
                "type": "chart",
                "data_source_id": data_source.id,
            }
        )
        rows = [
            {"group_label": "Jakarta", "Measure A": 10, "Measure B": 100.0},
            {"group_label": "Bandung", "Measure A": 4, "Measure B": 40.0},
        ]

        payload = item._prepare_render_payload_chart({"data": rows})

        chart = payload["chart"]
        self.assertEqual(chart["labels"], ["Jakarta", "Bandung"])
        self.assertEqual(
            chart["datasets"],
            [
                {"label": "Measure A", "data": [10, 4]},
                {"label": "Measure B", "data": [100.0, 40.0]},
            ],
        )
