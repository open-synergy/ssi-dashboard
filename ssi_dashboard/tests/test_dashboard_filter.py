# Copyright 2026 OpenSynergy Indonesia
# Copyright 2026 PT. Simetri Sinergi Indonesia
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from odoo_yaml_test import YamlTransactionCase

from odoo.tests import tagged


@tagged("post_install", "-at_install")
class TestDashboardFilter(YamlTransactionCase):
    def test_dashboard_filter(self):
        self.run_yaml_scenario("test_data_dashboard_filter.yaml")

    def _create_partner_data_source(self, code, **values):
        """Create a `dashboard.data_source` targeting `res.partner`.

        `company_id` is forced empty: this suite's `res.partner` fixtures
        are created without a `company_id` (unrelated to what these
        tests exercise), and `dashboard.data_source.company_id` now
        defaults to the active company — leaving it at that default
        would make `_prepare_company_domain` filter those company-less
        partners out, breaking these tests over a concern they do not
        test.
        """
        partner_model = self.env.ref("base.model_res_partner")
        vals = {
            "name": "Partners",
            "code": code,
            "type": "orm",
            "model_id": partner_model.id,
            "company_id": False,
        }
        vals.update(values)
        return self.env["dashboard.data_source"].create(vals)

    def test_active_domain_filter_narrows_item_data(self):
        """Python murni — pemicu P1 (L-01, L-02).

        `get_dashboard_payload`'s nilai balik (isi `data` tiap item)
        hanya bisa diverifikasi dengan meng-assert hasil pemanggilan
        method langsung — `action: call` YAML membuang nilai baliknya
        (L-01) dan tidak bisa meng-assert ekspresi bebas seperti
        `len(rows)` (L-02). Dua partner dibuat, satu dengan `user_id`
        milik pengguna saat ini; filter domain `[('user_id', '=', %UID)]`
        aktif harus mempersempit jumlah baris item dari 2 menjadi 1
        dibanding tanpa filter aktif sama sekali.
        """
        partners = self.env["res.partner"].create(
            [
                {"name": "Filter Narrow Partner Mine", "user_id": self.env.uid},
                {"name": "Filter Narrow Partner Other"},
            ]
        )
        data_source = self._create_partner_data_source(
            "DASH-FILTER-NARROW-DS-01",
            domain=f"[('id', 'in', {partners.ids!r})]",
        )
        dashboard = self.env["dashboard.dashboard"].create(
            {"name": "Narrow Dashboard", "code": "DASH-FILTER-NARROW-01"}
        )
        self.env["dashboard.item"].create(
            {
                "name": "Item Narrow",
                "dashboard_id": dashboard.id,
                "type": "placeholder",
                "data_source_id": data_source.id,
            }
        )
        dashboard_filter = self.env["dashboard.filter"].create(
            {
                "name": "Mine Only",
                "dashboard_id": dashboard.id,
                "filter_type": "domain",
                "domain": "[('user_id', '=', %UID)]",
            }
        )
        payload_without_filter = dashboard.get_dashboard_payload()
        payload_with_filter = dashboard.get_dashboard_payload(
            {"filter_ids": [dashboard_filter.id]}
        )
        self.assertEqual(payload_without_filter["items"][0]["data"][0]["__count"], 2)
        self.assertEqual(payload_with_filter["items"][0]["data"][0]["__count"], 1)
        self.assertEqual(
            payload_with_filter["active_filter_ids"], [dashboard_filter.id]
        )

    def test_default_active_filter_applied_without_argument(self):
        """Python murni — pemicu P1 (L-01, L-02).

        `get_dashboard_payload()` dipanggil tanpa argumen (nilai default
        `active_filters=None`) — hanya bisa diverifikasi dengan
        meng-assert nilai balik method langsung (L-01/L-02). Filter
        dengan `default_active` = True harus tetap diterapkan walau
        tidak ada argumen sama sekali yang dikirim, membuktikan
        `_resolve_active_filters` mengambil default filter dengan benar.
        """
        partners = self.env["res.partner"].create(
            [
                {"name": "Default Active Partner Mine", "user_id": self.env.uid},
                {"name": "Default Active Partner Other"},
            ]
        )
        data_source = self._create_partner_data_source(
            "DASH-FILTER-DEFAULT-DS-01",
            domain=f"[('id', 'in', {partners.ids!r})]",
        )
        dashboard = self.env["dashboard.dashboard"].create(
            {"name": "Default Active Dashboard", "code": "DASH-FILTER-DEFAULT-01"}
        )
        self.env["dashboard.item"].create(
            {
                "name": "Item Default Active",
                "dashboard_id": dashboard.id,
                "type": "placeholder",
                "data_source_id": data_source.id,
            }
        )
        self.env["dashboard.filter"].create(
            {
                "name": "Mine Only Default",
                "dashboard_id": dashboard.id,
                "filter_type": "domain",
                "domain": "[('user_id', '=', %UID)]",
                "default_active": True,
            }
        )
        payload = dashboard.get_dashboard_payload()
        self.assertEqual(payload["items"][0]["data"][0]["__count"], 1)

    def test_field_filter_skipped_for_model_without_field(self):
        """Python murni — pemicu P1 (L-01, L-02).

        Nilai balik `get_dashboard_payload` (isi `data` dua item dari
        model berbeda) hanya bisa diverifikasi dengan meng-assert hasil
        pemanggilan method langsung (L-01/L-02). Filter berbasis field
        `res.partner.email` diaktifkan bersama dua item: satu dari model
        `res.partner` (punya field itu, harus ikut mempersempit) dan satu
        dari `res.currency` (tidak punya field itu, harus dilewati —
        item ini tetap terisi datanya, bukan gagal).
        """
        email_field = self.env["ir.model.fields"].search(
            [("model", "=", "res.partner"), ("name", "=", "email")],
            limit=1,
        )
        partners = self.env["res.partner"].create(
            [
                {"name": "Field Filter Partner With Email", "email": "a@example.com"},
                {"name": "Field Filter Partner Without Email"},
            ]
        )
        partner_data_source = self._create_partner_data_source(
            "DASH-FILTER-FIELD-DS-01",
            domain=f"[('id', 'in', {partners.ids!r})]",
        )
        currency_model = self.env.ref("base.model_res_currency")
        new_currencies = self.env["res.currency"].create(
            [
                {"name": "FF1", "symbol": "F1", "rounding": 0.01},
                {"name": "FF2", "symbol": "F2", "rounding": 0.01},
            ]
        )
        currency_data_source = self.env["dashboard.data_source"].create(
            {
                "name": "Currencies",
                "code": "DASH-FILTER-FIELD-DS-02",
                "type": "orm",
                "model_id": currency_model.id,
                "domain": f"[('id', 'in', {new_currencies.ids!r})]",
            }
        )
        dashboard = self.env["dashboard.dashboard"].create(
            {"name": "Field Filter Dashboard", "code": "DASH-FILTER-FIELD-01"}
        )
        partner_item = self.env["dashboard.item"].create(
            {
                "name": "Partner Item",
                "dashboard_id": dashboard.id,
                "sequence": 10,
                "type": "placeholder",
                "data_source_id": partner_data_source.id,
            }
        )
        currency_item = self.env["dashboard.item"].create(
            {
                "name": "Currency Item",
                "dashboard_id": dashboard.id,
                "sequence": 20,
                "type": "placeholder",
                "data_source_id": currency_data_source.id,
            }
        )
        dashboard_filter = self.env["dashboard.filter"].create(
            {
                "name": "Has Email",
                "dashboard_id": dashboard.id,
                "filter_type": "field",
                "field_id": email_field.id,
            }
        )
        payload = dashboard.get_dashboard_payload({"filter_ids": [dashboard_filter.id]})
        items_by_id = {item["id"]: item for item in payload["items"]}
        self.assertEqual(items_by_id[partner_item.id]["data"][0]["__count"], 1)
        self.assertEqual(items_by_id[currency_item.id]["data"][0]["__count"], 2)

    def test_date_range_override_narrows_item_data(self):
        """Python murni — pemicu P1 (L-01, L-02).

        Nilai balik `get_dashboard_payload` hanya bisa diverifikasi
        dengan meng-assert hasil pemanggilan method langsung (L-01/L-02).
        Data source memakai `date_range` = `all_time` (tanpa pembatasan
        tanggal bawaan); `date_start`/`date_end` di argumen
        `active_filters` harus menimpa itu dan mempersempit ke rentang
        yang diberikan.
        """
        currency_rate_model = self.env.ref("base.model_res_currency_rate")
        date_field = self.env["ir.model.fields"].search(
            [("model", "=", "res.currency.rate"), ("name", "=", "name")],
            limit=1,
        )
        currency = self.env.ref("base.EUR")
        rates = self.env["res.currency.rate"].create(
            [
                {"currency_id": currency.id, "name": "2026-01-15", "rate": 1.1},
                {"currency_id": currency.id, "name": "2026-06-15", "rate": 1.3},
            ]
        )
        data_source = self.env["dashboard.data_source"].create(
            {
                "name": "Rates Override",
                "code": "DASH-FILTER-DATEOVERRIDE-DS-01",
                "type": "orm",
                "model_id": currency_rate_model.id,
                "domain": f"[('id', 'in', {rates.ids!r})]",
                "date_field_id": date_field.id,
                "date_range": "all_time",
            }
        )
        dashboard = self.env["dashboard.dashboard"].create(
            {"name": "Date Override Dashboard", "code": "DASH-FILTER-DATEOVERRIDE-01"}
        )
        self.env["dashboard.item"].create(
            {
                "name": "Item Date Override",
                "dashboard_id": dashboard.id,
                "type": "placeholder",
                "data_source_id": data_source.id,
            }
        )
        payload_without_override = dashboard.get_dashboard_payload()
        payload_with_override = dashboard.get_dashboard_payload(
            {"date_start": "2026-01-01", "date_end": "2026-01-31"}
        )
        self.assertEqual(payload_without_override["items"][0]["data"][0]["__count"], 2)
        self.assertEqual(payload_with_override["items"][0]["data"][0]["__count"], 1)

    def test_get_dashboard_payload_without_filters_unaffected(self):
        """Python murni — pemicu P1 (L-01, L-02).

        Kriteria Penerimaan: `get_dashboard_payload()` tanpa argumen
        tetap bekerja seperti sebelum fitur filter ada. Nilai balik
        method hanya bisa diverifikasi dengan meng-assert hasil
        pemanggilan langsung (L-01/L-02). Dashboard ini sengaja tidak
        punya `dashboard.filter` sama sekali.
        """
        data_source = self._create_partner_data_source("DASH-FILTER-NONE-DS-01")
        dashboard = self.env["dashboard.dashboard"].create(
            {"name": "No Filter Dashboard", "code": "DASH-FILTER-NONE-01"}
        )
        self.env["dashboard.item"].create(
            {
                "name": "Item No Filter",
                "dashboard_id": dashboard.id,
                "type": "placeholder",
                "data_source_id": data_source.id,
            }
        )
        payload = dashboard.get_dashboard_payload()
        self.assertEqual(payload["filters"], [])
        self.assertEqual(payload["active_filter_ids"], [])
        self.assertEqual(len(payload["items"]), 1)
