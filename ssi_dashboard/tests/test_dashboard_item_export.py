# Copyright 2026 OpenSynergy Indonesia
# Copyright 2026 PT. Simetri Sinergi Indonesia
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from odoo_yaml_test import YamlTransactionCase

from odoo.tests import tagged


@tagged("post_install", "-at_install")
class TestDashboardItemExport(YamlTransactionCase):
    """No YAML scenario file: every Skenario Uji for `prepare_export_data`
    hits one of the Python-pure triggers documented per method below
    (return value / rounding / row count) — see `python-escape-hatch.md`.
    The `allow_export` default-True scenario is plain CRUD/field-default
    and lives in `test_data_dashboard_item.yaml` (run by
    `test_dashboard_item.py`) instead of being duplicated here.
    """

    def test_prepare_export_data_two_measures_builds_two_column_table(self):
        """Python murni — pemicu P1 (L-01, L-02: nilai balik method, tak
        bisa di-assert dari `action: call`/dotted-path YAML) dan P3
        (L-06: isi dan urutan `rows` harus di-assert per-sel).

        Skenario Uji positif dari issue: item tabel berdua kolom (dua
        baris `measure_ids`) — `prepare_export_data()` harus
        menghasilkan `headers` berisi kedua nama measure, dan satu baris
        `rows` berisi dua sel — nilainya numerik (Kriteria Penerimaan:
        jumlah kolom tiap baris sama dengan jumlah headers; angka
        bertipe numerik).
        """
        partner_model = self.env.ref("base.model_res_partner")
        latitude_field = self.env["ir.model.fields"].search(
            [("model", "=", "res.partner"), ("name", "=", "partner_latitude")],
            limit=1,
        )
        partners = self.env["res.partner"].create(
            [
                {"name": "Export Partner A", "partner_latitude": 10.5},
                {"name": "Export Partner B", "partner_latitude": 20.25},
            ]
        )
        data_source = self.env["dashboard.data_source"].create(
            {
                "name": "Export Partners Two Measures",
                "code": "DASH-EXPORT-DS-01",
                "type": "orm",
                "model_id": partner_model.id,
                "domain": f"[('id', 'in', {partners.ids!r})]",
                # These fixture partners have no company_id, unrelated to
                # what this test exercises — see
                # `dashboard_filter._create_partner_data_source` for the
                # same reasoning.
                "company_id": False,
                "measure_ids": [
                    (
                        0,
                        0,
                        {
                            "sequence": 10,
                            "name": "Partner Count",
                            "aggregate": "count",
                        },
                    ),
                    (
                        0,
                        0,
                        {
                            "sequence": 20,
                            "name": "Latitude Total",
                            "field_id": latitude_field.id,
                            "aggregate": "sum",
                        },
                    ),
                ],
            }
        )
        dashboard = self.env["dashboard.dashboard"].create(
            {"name": "Export Dashboard", "code": "DASH-EXPORT-DASH-01"}
        )
        item = self.env["dashboard.item"].create(
            {
                "name": "Export Item Two Measures",
                "dashboard_id": dashboard.id,
                "type": "placeholder",
                "data_source_id": data_source.id,
            }
        )
        export_data = item.prepare_export_data()
        self.assertEqual(export_data["headers"], ["Partner Count", "Latitude Total"])
        self.assertEqual(len(export_data["rows"]), 1)
        row = export_data["rows"][0]
        self.assertEqual(len(row), 2)
        self.assertEqual(row[0], 2.0)
        self.assertEqual(row[1], 30.75)
        for value in row:
            self.assertIsInstance(value, (int, float))
            self.assertNotIsInstance(value, bool)

    def test_prepare_export_data_applies_multiplier(self):
        """Python murni — pemicu P1 (L-01, L-02) dan P2 (L-04: nilai
        pecahan hasil `multiplier` butuh dibandingkan lewat perhitungan
        yang sama, bukan literal tebakan).

        Skenario Uji positif dari issue: item ber-`multiplier` = 0.001 →
        nilai pada `rows` sudah terkali, bertipe numerik (Kriteria
        Penerimaan: angka pada `rows` bertipe numerik, bukan string
        terformat).
        """
        partner_model = self.env.ref("base.model_res_partner")
        latitude_field = self.env["ir.model.fields"].search(
            [("model", "=", "res.partner"), ("name", "=", "partner_latitude")],
            limit=1,
        )
        partner = self.env["res.partner"].create(
            {"name": "Export Partner Multiplier", "partner_latitude": 1234.5678}
        )
        data_source = self.env["dashboard.data_source"].create(
            {
                "name": "Export Partners Multiplier",
                "code": "DASH-EXPORT-DS-02",
                "type": "orm",
                "model_id": partner_model.id,
                "domain": f"[('id', '=', {partner.id})]",
                "measure_field_id": latitude_field.id,
                "aggregate": "sum",
                # See test_prepare_export_data_two_measures_builds_two_column_table.
                "company_id": False,
            }
        )
        dashboard = self.env["dashboard.dashboard"].create(
            {"name": "Export Dashboard", "code": "DASH-EXPORT-DASH-02"}
        )
        item = self.env["dashboard.item"].create(
            {
                "name": "Export Item Multiplier",
                "dashboard_id": dashboard.id,
                "type": "placeholder",
                "data_source_id": data_source.id,
                "multiplier": 0.001,
            }
        )
        export_data = item.prepare_export_data()
        expected_value = round(1234.5678 * 0.001, item.precision_digits)
        self.assertEqual(len(export_data["rows"]), 1)
        value = export_data["rows"][0][0]
        self.assertEqual(value, expected_value)
        self.assertIsInstance(value, (int, float))
        self.assertNotIsInstance(value, bool)

    def test_prepare_export_data_active_filters_narrows_rows(self):
        """Python murni — pemicu P1 (L-01, L-02: nilai balik method).

        Skenario Uji positif dari issue:
        `prepare_export_data(active_filters=...)` dengan filter yang
        mempersempit → jumlah baris berkurang dibanding tanpa filter.
        Data source dikelompokkan menurut `is_company` (dua grup: True/
        False); mengaktifkan filter 'Field Value' pada `is_company`
        (mensyaratkan nilainya truthy) menghilangkan grup False,
        menyisakan satu baris (Kriteria Penerimaan: filter aktif yang
        dikirim menghasilkan `rows` yang sama dengan yang tampil di
        layar — di sini dibuktikan lewat jumlah baris yang berkurang
        secara konsisten dengan domain filter itu sendiri).
        """
        partner_model = self.env.ref("base.model_res_partner")
        is_company_field = self.env["ir.model.fields"].search(
            [("model", "=", "res.partner"), ("name", "=", "is_company")],
            limit=1,
        )
        partners = self.env["res.partner"].create(
            [
                {"name": "Export Company A", "is_company": True},
                {"name": "Export Company B", "is_company": True},
                {"name": "Export Individual A", "is_company": False},
            ]
        )
        data_source = self.env["dashboard.data_source"].create(
            {
                "name": "Export Partners Filter",
                "code": "DASH-EXPORT-DS-03",
                "type": "orm",
                "model_id": partner_model.id,
                "domain": f"[('id', 'in', {partners.ids!r})]",
                "group_by_field_id": is_company_field.id,
                # See test_prepare_export_data_two_measures_builds_two_column_table.
                "company_id": False,
            }
        )
        dashboard = self.env["dashboard.dashboard"].create(
            {"name": "Export Dashboard", "code": "DASH-EXPORT-DASH-03"}
        )
        item = self.env["dashboard.item"].create(
            {
                "name": "Export Item Filter",
                "dashboard_id": dashboard.id,
                "type": "placeholder",
                "data_source_id": data_source.id,
            }
        )
        dashboard_filter = self.env["dashboard.filter"].create(
            {
                "dashboard_id": dashboard.id,
                "name": "Companies Only",
                "filter_type": "field",
                "field_id": is_company_field.id,
            }
        )
        unfiltered = item.prepare_export_data()
        self.assertEqual(len(unfiltered["rows"]), 2)
        filtered = item.prepare_export_data(
            active_filters={"filter_ids": [dashboard_filter.id]}
        )
        self.assertEqual(len(filtered["rows"]), 1)
