# Copyright 2026 OpenSynergy Indonesia
# Copyright 2026 PT. Simetri Sinergi Indonesia
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
import json

from odoo_yaml_test import YamlTransactionCase

from odoo.tests import tagged


@tagged("post_install", "-at_install")
class TestDashboardItemList(YamlTransactionCase):
    def test_dashboard_item_list(self):
        self.run_yaml_scenario("test_data_dashboard_item_list.yaml")

    def test_prepare_render_payload_list_columns_and_limit(self):
        """Python murni — P1 & P3: nilai balik `_prepare_render_payload_list`
        beserta urutan `columns`, dan penegakan `limit`.

        `action: call` YAML membuang nilai balik method (L-01, P1), dan
        perbandingan YAML berbasis `set` tidak bisa menegakkan urutan
        (L-06, P3) — di sini urutan pasangan `key`/`label` pada `columns`
        dan penegakan `len(rows) <= limit` diuji langsung atas dict yang
        dikembalikan method.
        """
        data_source = self.env["dashboard.data_source"].create(
            {
                "name": "Partners",
                "code": "DASH-LIST-PY-DS-01",
                "type": "orm",
                "model_id": self.env.ref("base.model_res_partner").id,
            }
        )
        dashboard = self.env["dashboard.dashboard"].create(
            {"name": "List Dashboard", "code": "DASH-LIST-PY-01"}
        )
        item = self.env["dashboard.item"].create(
            {
                "name": "Top Partners",
                "dashboard_id": dashboard.id,
                "type": "list",
                "data_source_id": data_source.id,
                "config": json.dumps(
                    {
                        "columns": [
                            {"key": "name"},
                            {"key": "amount", "label": "Amount"},
                        ],
                        "limit": 3,
                    }
                ),
            }
        )
        rows = [
            {"name": "Alpha", "amount": 10},
            {"name": "Beta", "amount": 5},
            {"name": "Gamma", "amount": 7},
            {"name": "Delta", "amount": 3},
            {"name": "Epsilon", "amount": 1},
        ]

        payload = item._prepare_render_payload_list({"data": rows})

        self.assertIn("columns", payload)
        self.assertIn("rows", payload)
        self.assertEqual(
            payload["columns"],
            [
                {"key": "name", "label": "name"},
                {"key": "amount", "label": "Amount"},
            ],
        )
        self.assertEqual(len(payload["rows"]), 3)
        self.assertEqual(
            payload["rows"],
            [
                {"name": "Alpha", "amount": 10},
                {"name": "Beta", "amount": 5},
                {"name": "Gamma", "amount": 7},
            ],
        )

    def test_prepare_render_payload_list_default_label_and_missing_column(self):
        """Python murni — P1 & P3: label default = 'key', 'limit' default
        10, dan kolom yang tak ada di baris sumber menghasilkan `None`
        (sel kosong) alih-alih error.

        Sama seperti test di atas, ini menyentuh nilai balik method (P1)
        dan urutan pasangan `key`/`label` (P3) — L-01/L-06.
        """
        data_source = self.env["dashboard.data_source"].create(
            {
                "name": "Partners",
                "code": "DASH-LIST-PY-DS-02",
                "type": "orm",
                "model_id": self.env.ref("base.model_res_partner").id,
            }
        )
        dashboard = self.env["dashboard.dashboard"].create(
            {"name": "List Dashboard 2", "code": "DASH-LIST-PY-02"}
        )
        item = self.env["dashboard.item"].create(
            {
                "name": "Partner Names",
                "dashboard_id": dashboard.id,
                "type": "list",
                "data_source_id": data_source.id,
                "config": json.dumps({"columns": [{"key": "name"}, {"key": "amount"}]}),
            }
        )
        rows = [{"name": "Alpha"}]

        payload = item._prepare_render_payload_list({"data": rows})

        self.assertEqual(
            payload["columns"],
            [
                {"key": "name", "label": "name"},
                {"key": "amount", "label": "amount"},
            ],
        )
        self.assertEqual(payload["rows"], [{"name": "Alpha", "amount": None}])
