# Copyright 2026 OpenSynergy Indonesia
# Copyright 2026 PT. Simetri Sinergi Indonesia
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from odoo_yaml_test import YamlTransactionCase
from psycopg2 import IntegrityError

from odoo.tests import tagged
from odoo.tools import mute_logger


@tagged("post_install", "-at_install")
class TestDashboardItemDrilldown(YamlTransactionCase):
    def test_dashboard_item_drilldown(self):
        self.run_yaml_scenario("test_data_dashboard_item_drilldown.yaml")

    def _create_two_level_chain_item(self, code_suffix):
        """Shared fixture for the drill-down positive scenarios below:
        a data source over 'res.partner' scoped to freshly created
        partners only (so pre-existing/demo partners never leak into the
        assertions), an item, and a two-level drill-down chain — level 1
        groups by 'Country', level 2 by 'Industry'.

        :param code_suffix: unique suffix appended to every 'code' this
            builds, so parallel scenarios in the same test never collide.
        :type code_suffix: str
        :return: 4-tuple ``(item, country_a, country_b, industry)``.
        :rtype: tuple
        """
        partner_model = self.env.ref("base.model_res_partner")
        country_field = self.env["ir.model.fields"].search(
            [("model", "=", "res.partner"), ("name", "=", "country_id")],
            limit=1,
        )
        industry_field = self.env["ir.model.fields"].search(
            [("model", "=", "res.partner"), ("name", "=", "industry_id")],
            limit=1,
        )
        country_a = self.env.ref("base.us")
        country_b = self.env.ref("base.id")
        industry = self.env["res.partner.industry"].create(
            {"name": f"Drilldown Industry {code_suffix}"}
        )
        partners = self.env["res.partner"].create(
            [
                {
                    "name": f"Drilldown Partner A1 {code_suffix}",
                    "country_id": country_a.id,
                    "industry_id": industry.id,
                },
                {
                    "name": f"Drilldown Partner A2 {code_suffix}",
                    "country_id": country_a.id,
                    "industry_id": industry.id,
                },
                {
                    "name": f"Drilldown Partner B1 {code_suffix}",
                    "country_id": country_b.id,
                    "industry_id": industry.id,
                },
            ]
        )
        # `dashboard.data_source.company_id` defaults to the active
        # company, and `_prepare_company_domain` narrows `_fetch_data_orm`
        # reads on 'res.partner' to that same company — unrelated to what
        # the drill-down scenarios below exercise. Match these fixture
        # partners to it so that filter never changes their result.
        partners.write({"company_id": self.env.company.id})
        data_source = self.env["dashboard.data_source"].create(
            {
                "name": "Partners For Drilldown",
                "code": f"DASH-DRILLDOWN-DS-{code_suffix}",
                "type": "orm",
                "model_id": partner_model.id,
                "domain": f"[('id', 'in', {partners.ids!r})]",
            }
        )
        dashboard = self.env["dashboard.dashboard"].create(
            {
                "name": "Drilldown Dashboard",
                "code": f"DASH-DRILLDOWN-DASH-{code_suffix}",
            }
        )
        item = self.env["dashboard.item"].create(
            {
                "name": "Item With Drilldown Chain",
                "dashboard_id": dashboard.id,
                "type": "placeholder",
                "data_source_id": data_source.id,
                "drilldown_ids": [
                    (
                        0,
                        0,
                        {
                            "sequence": 10,
                            "field_id": country_field.id,
                            "granularity": False,
                        },
                    ),
                    (
                        0,
                        0,
                        {
                            "sequence": 20,
                            "field_id": industry_field.id,
                            "granularity": False,
                        },
                    ),
                ],
            }
        )
        return item, country_a, country_b, industry

    def test_fetch_drilldown_data_level_one_groups_by_first_field(self):
        """Python murni — pemicu P1 (L-01, L-02).

        Nilai balik `fetch_drilldown_data` (dict berisi `rows`/`level`/
        `is_last`) hanya bisa diverifikasi dengan meng-assert hasil
        pemanggilan method langsung — `action: call` di YAML membuang
        nilai baliknya (L-01) dan isi dict tidak bisa diperiksa lewat
        assert dotted path (L-02). Skenario Uji positif dari issue: item
        dengan rantai dua tingkat (Country lalu Industry) — meminta level
        1 harus mengelompokkan data menurut 'Country' (dimensi tingkat
        pertama, bukan 'Industry') dan `is_last` harus `False` karena
        masih ada tingkat kedua (Kriteria Penerimaan:
        `fetch_drilldown_data(1, [])` mengelompokkan data menurut
        `field_id` tingkat pertama).
        """
        item, country_a, country_b, _industry = self._create_two_level_chain_item("L1")
        result = item.fetch_drilldown_data(1, [])
        self.assertEqual(result["level"], 1)
        self.assertFalse(result["is_last"])
        self.assertEqual(len(result["rows"]), 2)
        labels = {row["group_label"] for row in result["rows"]}
        self.assertEqual(labels, {country_a.display_name, country_b.display_name})
        counts = {row["group_label"]: row["__count"] for row in result["rows"]}
        self.assertEqual(counts[country_a.display_name], 2)
        self.assertEqual(counts[country_b.display_name], 1)

    def test_fetch_drilldown_data_level_two_is_last_true(self):
        """Python murni — pemicu P1 (L-01, L-02).

        Sama seperti di atas: nilai balik hanya bisa diperiksa lewat
        pemanggilan method langsung. Skenario Uji positif dari issue:
        meminta level 2 (tingkat terakhir dari rantai dua tingkat) dengan
        `path` berisi domain baris tingkat 1 yang diklik harus membuat
        `is_last` bernilai `True` (Kriteria Penerimaan: `is_last`
        bernilai `True` pada tingkat terakhir rantai).
        """
        item, country_a, _country_b, industry = self._create_two_level_chain_item("L2")
        level_one_rows = item.fetch_drilldown_data(1, [])["rows"]
        country_a_row = next(
            row
            for row in level_one_rows
            if row["group_label"] == country_a.display_name
        )
        result = item.fetch_drilldown_data(2, country_a_row["row_domain"])
        self.assertEqual(result["level"], 2)
        self.assertTrue(result["is_last"])
        self.assertEqual(len(result["rows"]), 1)
        self.assertEqual(result["rows"][0]["group_label"], industry.display_name)
        self.assertEqual(result["rows"][0]["__count"], 2)

    def test_fetch_drilldown_data_level_zero_matches_fetch_data(self):
        """Python murni — pemicu P1 (L-01, L-02).

        Sama seperti di atas: nilai balik hanya bisa diperiksa lewat
        pemanggilan method langsung. Skenario Uji positif dari issue:
        `fetch_drilldown_data(0, [])` — level 0, tampilan asli — harus
        mengembalikan `rows` yang identik dengan hasil
        `data_source_id._fetch_data(item)` langsung, membuktikan level 0
        memakai jalur baca yang sama persis tanpa penukaran dimensi
        (Kriteria Penerimaan: item tanpa penelusuran berperilaku persis
        seperti sebelum perubahan ini).
        """
        item, _country_a, _country_b, _industry = self._create_two_level_chain_item(
            "L0"
        )
        result = item.fetch_drilldown_data(0, [])
        self.assertEqual(result["level"], 0)
        self.assertFalse(result["is_last"])
        self.assertEqual(result["rows"], item.data_source_id._fetch_data(item))

    def test_fetch_drilldown_data_path_cannot_override_data_source_domain(self):
        """Python murni — pemicu P1 (L-01, L-02).

        Sama seperti di atas: nilai balik hanya bisa diperiksa lewat
        pemanggilan method langsung. Skenario Uji positif dari issue:
        'Data Source' dibatasi `is_company = True`; `path` mencoba
        meniadakannya dengan `('is_company', '=', False)`. Karena domain
        selalu diperlakukan sebagai konjungsi (AND), kombinasi keduanya
        mustahil dipenuhi record mana pun, sehingga jumlah baris harus
        tetap 0 — membuktikan domain 'Data Source' tetap terpasang di
        server meski `path` dari browser mencoba menghilangkannya
        (Kriteria Penerimaan: domain data source tetap terpasang meski
        `path` mencoba menghilangkannya).
        """
        partner_model = self.env.ref("base.model_res_partner")
        data_source = self.env["dashboard.data_source"].create(
            {
                "name": "Companies Only For Drilldown",
                "code": "DASH-DRILLDOWN-DOMAIN-DS-01",
                "type": "orm",
                "model_id": partner_model.id,
                "domain": "[('is_company', '=', True)]",
            }
        )
        dashboard = self.env["dashboard.dashboard"].create(
            {"name": "Drilldown Domain Dashboard", "code": "DASH-DRILLDOWN-DOMAIN-01"}
        )
        item = self.env["dashboard.item"].create(
            {
                "name": "Item Drilldown Domain",
                "dashboard_id": dashboard.id,
                "type": "placeholder",
                "data_source_id": data_source.id,
            }
        )
        result = item.fetch_drilldown_data(0, [("is_company", "=", False)])
        self.assertEqual(len(result["rows"]), 1)
        self.assertEqual(result["rows"][0]["__count"], 0)

    def test_create_drilldown_duplicate_sequence_raises_integrity_error(self):
        """Python murni — pemicu P5 (L-22 — constraint DB-level).

        `dashboard.item.drilldown` memvalidasi keunikan `(item_id,
        sequence)` lewat `models.Constraint("UNIQUE(item_id, sequence)",
        ...)`, constraint tingkat database (bukan `@api.constrains`).
        Membuat dua baris rantai dengan `item_id` dan `sequence` yang
        sama melempar `psycopg2.errors.UniqueViolation` (subclass
        `psycopg2.IntegrityError`), tipe yang tidak termasuk 12 tipe yang
        dikenali `expect_error` (L-22), sehingga tidak bisa diuji lewat
        YAML. `mute_logger` membungkam log ERROR `odoo.sql_db` yang
        normal muncul saat Postgres menolak query ini (Kriteria
        Penerimaan: dua baris rantai dengan `sequence` sama pada satu
        item ditolak).
        """
        partner_model = self.env.ref("base.model_res_partner")
        country_field = self.env["ir.model.fields"].search(
            [("model", "=", "res.partner"), ("name", "=", "country_id")],
            limit=1,
        )
        data_source = self.env["dashboard.data_source"].create(
            {
                "name": "Partners For Drilldown Unique",
                "code": "DASH-DRILLDOWN-UNIQ-DS-01",
                "type": "orm",
                "model_id": partner_model.id,
            }
        )
        dashboard = self.env["dashboard.dashboard"].create(
            {"name": "Drilldown Unique Dashboard", "code": "DASH-DRILLDOWN-UNIQ-01"}
        )
        item = self.env["dashboard.item"].create(
            {
                "name": "Item Drilldown Unique Sequence",
                "dashboard_id": dashboard.id,
                "type": "placeholder",
                "data_source_id": data_source.id,
            }
        )
        self.env["dashboard.item.drilldown"].create(
            {
                "item_id": item.id,
                "sequence": 10,
                "field_id": country_field.id,
                "granularity": False,
            }
        )
        with mute_logger("odoo.sql_db"), self.assertRaises(IntegrityError):
            with self.env.cr.savepoint():
                self.env["dashboard.item.drilldown"].create(
                    {
                        "item_id": item.id,
                        "sequence": 10,
                        "field_id": country_field.id,
                        "granularity": False,
                    }
                )
