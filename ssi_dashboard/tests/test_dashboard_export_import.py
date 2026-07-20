# Copyright 2026 OpenSynergy Indonesia
# Copyright 2026 PT. Simetri Sinergi Indonesia
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
import base64
import json

from odoo_yaml_test import YamlTransactionCase

from odoo.exceptions import UserError
from odoo.tests import new_test_user, tagged


@tagged("post_install", "-at_install")
class TestDashboardExportImport(YamlTransactionCase):
    """No YAML scenario file: every Skenario Uji for
    `prepare_export_definition`/`dashboard.import.action_import` hits
    one of the Python-pure triggers documented per method below — see
    `python-escape-hatch.md`. Positive scenarios assert the *return
    value* of a method (P1, L-01/L-02: `action: call` in YAML discards
    return values and dotted-path asserts only ever read a stored
    record field, never a method's result). Negative scenarios that
    raise `UserError` could in principle be written in YAML
    (`expect_error`), but are kept here so the whole feature's test
    coverage stays in one file, next to the fixtures/JSON payloads the
    positive scenarios already build.
    """

    def _create_dashboard_with_items(self, suffix):
        """Shared fixture: one 'res.partner' data source, one dashboard
        with two items sharing that same data source (so the export's
        deduplication of `data_sources` — Keputusan Desain: 'seluruh
        item_ids beserta ... definisi setiap dashboard.data_source yang
        dirujuk' — is exercised by every test using this fixture).
        """
        partner_model = self.env.ref("base.model_res_partner")
        latitude_field = self.env["ir.model.fields"].search(
            [("model", "=", "res.partner"), ("name", "=", "partner_latitude")],
            limit=1,
        )
        data_source = self.env["dashboard.data_source"].create(
            {
                "name": "Export Import Partners",
                "code": f"DASH-EI-DS-{suffix}",
                "type": "orm",
                "model_id": partner_model.id,
                "domain": "[]",
                "measure_field_id": latitude_field.id,
                "aggregate": "sum",
            }
        )
        dashboard = self.env["dashboard.dashboard"].create(
            {
                "name": f"Export Import Dashboard {suffix}",
                "code": f"DASH-EI-{suffix}",
                "item_ids": [
                    (
                        0,
                        0,
                        {
                            "name": "Item A",
                            "type": "placeholder",
                            "data_source_id": data_source.id,
                            "sequence": 10,
                        },
                    ),
                    (
                        0,
                        0,
                        {
                            "name": "Item B",
                            "type": "placeholder",
                            "data_source_id": data_source.id,
                            "sequence": 20,
                            "multiplier": 2.5,
                        },
                    ),
                ],
            }
        )
        return dashboard, data_source

    def _wizard_from_definition(self, definition, **wizard_vals):
        """Build a `dashboard.import` wizard record whose `data_file`
        is `definition` (a dict, as returned by
        `prepare_export_definition`) encoded exactly the way a real
        exported file would be — JSON text, UTF-8, base64 — never a
        Python literal/pickle.
        """
        content = json.dumps(definition).encode("utf-8")
        vals = {
            "data_file": base64.b64encode(content),
            "filename": "dashboard.json",
        }
        vals.update(wizard_vals)
        return self.env["dashboard.import"].create(vals)

    def test_prepare_export_definition_schema_version_and_keys(self):
        """Python murni — pemicu P1 (L-01, L-02: nilai balik method).

        Kriteria Penerimaan: `prepare_export_definition()` menghasilkan
        dict ber-`schema_version` bernilai `1`.
        """
        dashboard, _data_source = self._create_dashboard_with_items("SCHEMA-01")
        definition = dashboard.prepare_export_definition()
        self.assertEqual(definition["schema_version"], 1)
        self.assertIn("dashboard", definition)
        self.assertIn("items", definition)
        self.assertIn("filters", definition)
        self.assertIn("data_sources", definition)

    def test_prepare_export_definition_stores_names_not_ids(self):
        """Python murni — pemicu P1 (L-01, L-02).

        Kriteria Penerimaan: rujukan model dan field tersimpan sebagai
        nama, bukan id numerik. `data_sources[code]['model']` harus
        string teknis model ('res.partner'), dan `['measure_field']`
        harus dict `{'model', 'field'}` berisi nama field, bukan id
        `ir.model.fields`.
        """
        dashboard, data_source = self._create_dashboard_with_items("NAMES-01")
        definition = dashboard.prepare_export_definition()
        ds_vals = definition["data_sources"][data_source.code]
        self.assertEqual(ds_vals["model"], "res.partner")
        self.assertIsInstance(ds_vals["model"], str)
        self.assertEqual(
            ds_vals["measure_field"],
            {"model": "res.partner", "field": "partner_latitude"},
        )
        self.assertEqual(definition["items"][0]["data_source"], data_source.code)
        self.assertIsInstance(definition["items"][0]["data_source"], str)

    def test_prepare_export_definition_dedups_shared_data_source(self):
        """Python murni — pemicu P1 (L-01, L-02).

        Kedua item dari `_create_dashboard_with_items` memakai data
        source yang sama — 'data_sources' hanya boleh memuat satu
        salinan definisinya, dikunci oleh `code`.
        """
        dashboard, data_source = self._create_dashboard_with_items("DEDUP-01")
        definition = dashboard.prepare_export_definition()
        self.assertEqual(list(definition["data_sources"].keys()), [data_source.code])
        self.assertEqual(len(definition["items"]), 2)

    def test_prepare_export_definition_excludes_query_field(self):
        """Python murni — pemicu P1 (L-01, L-02).

        Skenario Uji positif dari issue: ekspor dashboard yang memakai
        data source → dict hasil tidak memuat isi query. Field 'query'
        (ditambahkan modul terpisah `ssi_dashboard_source_query`, tidak
        menjadi dependensi issue ini) tidak pernah masuk whitelist yang
        dibangun `dashboard.data_source._prepare_export_data_source_vals`
        — dibuktikan di sini dengan memastikan kuncinya benar-benar
        tidak ada pada dict hasil, apa pun tipe data source-nya.
        """
        dashboard, data_source = self._create_dashboard_with_items("NOQUERY-01")
        definition = dashboard.prepare_export_definition()
        ds_vals = definition["data_sources"][data_source.code]
        self.assertNotIn("query", ds_vals)

    def test_prepare_export_definition_item_excludes_config_key(self):
        """Skenario Uji regresi ekspor dari issue #53: item yang diekspor
        tidak lagi memuat kunci 'config'. Field `dashboard.item.config`
        sudah dihapus dari model, dan `_prepare_export_item_vals()`
        berhenti menaruhnya ke dict ekspor. Python murni — pemicu P1
        (L-01, L-02: nilai balik method).
        """
        dashboard, _data_source = self._create_dashboard_with_items("NOCONFIG-01")
        definition = dashboard.prepare_export_definition()
        self.assertTrue(definition["items"])
        for item_vals in definition["items"]:
            self.assertNotIn("config", item_vals)

    def test_action_import_roundtrip_creates_matching_items(self):
        """Python murni — pemicu P1 (L-01, L-02).

        Skenario Uji positif dari issue: ekspor dashboard berisi dua
        item lalu impor kembali → dashboard baru punya dua item dengan
        konfigurasi sama, dan dashboard asal tetap utuh.
        """
        dashboard, data_source = self._create_dashboard_with_items("ROUNDTRIP-01")
        definition = dashboard.prepare_export_definition()
        wizard = self._wizard_from_definition(definition)
        action = wizard.action_import()
        self.assertEqual(action["type"], "ir.actions.client")
        new_dashboard = self.env["dashboard.dashboard"].browse(
            action["context"]["dashboard_id"]
        )
        self.assertTrue(new_dashboard.exists())
        self.assertNotEqual(new_dashboard.id, dashboard.id)
        self.assertEqual(new_dashboard.name, f"{dashboard.name} (Imported)")
        self.assertEqual(len(new_dashboard.item_ids), 2)
        new_items = new_dashboard.item_ids.sorted("sequence")
        self.assertEqual(new_items.mapped("name"), ["Item A", "Item B"])
        self.assertEqual(new_items[1].multiplier, 2.5)
        for item in new_items:
            self.assertTrue(item.data_source_id)
            self.assertEqual(item.data_source_id.model_id.model, "res.partner")
            self.assertNotEqual(item.data_source_id.id, data_source.id)
        # The original dashboard is untouched.
        self.assertTrue(dashboard.exists())
        self.assertEqual(len(dashboard.item_ids), 2)
        self.assertEqual(dashboard.item_ids.mapped("data_source_id"), data_source)

    def test_action_import_twice_produces_different_codes(self):
        """Python murni — pemicu P1 (L-01, L-02).

        Skenario Uji positif dari issue: impor dua kali berturut-turut
        → dua dashboard terbentuk dengan `code` berbeda. Membuktikan
        `_generate_unique_code` menyuffiks `code` saat sudah terpakai —
        keduanya berasal dari file yang persis sama.
        """
        dashboard, _data_source = self._create_dashboard_with_items("TWICE-01")
        definition = dashboard.prepare_export_definition()
        wizard_1 = self._wizard_from_definition(definition)
        action_1 = wizard_1.action_import()
        wizard_2 = self._wizard_from_definition(definition)
        action_2 = wizard_2.action_import()
        dashboard_1 = self.env["dashboard.dashboard"].browse(
            action_1["context"]["dashboard_id"]
        )
        dashboard_2 = self.env["dashboard.dashboard"].browse(
            action_2["context"]["dashboard_id"]
        )
        self.assertNotEqual(dashboard_1.id, dashboard_2.id)
        self.assertNotEqual(dashboard_1.code, dashboard_2.code)
        data_source_1 = dashboard_1.item_ids[0].data_source_id
        data_source_2 = dashboard_2.item_ids[0].data_source_id
        self.assertNotEqual(data_source_1.code, data_source_2.code)

    def test_action_import_ignores_legacy_config_key(self):
        """Skenario Uji regresi impor dari issue #53: mengimpor sebuah
        definisi yang masih memuat kunci 'config' pada salah satu item
        (persis seperti berkas JSON lama yang diekspor sebelum field
        `dashboard.item.config` dihapus) tidak menyebabkan error saat
        `action_import()` — kunci itu diabaikan diam-diam, tidak
        diteruskan ke `dashboard.item.create()` (yang akan menolaknya
        karena field 'config' sudah tidak ada pada model). Python murni
        — pemicu P1 (L-01, L-02: nilai balik method / record baru).
        """
        dashboard, _data_source = self._create_dashboard_with_items("LEGACYCFG-01")
        definition = dashboard.prepare_export_definition()
        definition["items"][0]["config"] = '{"legacy": true}'
        wizard = self._wizard_from_definition(definition)
        action = wizard.action_import()
        new_dashboard = self.env["dashboard.dashboard"].browse(
            action["context"]["dashboard_id"]
        )
        self.assertEqual(len(new_dashboard.item_ids), 2)

    def test_action_import_rejects_unknown_schema_version(self):
        """Skenario Uji negatif dari issue: impor berkas ber-
        `schema_version` bernilai `99` → `UserError`.
        """
        wizard = self._wizard_from_definition(
            {
                "schema_version": 99,
                "dashboard": {"name": "Future Schema"},
                "items": [],
                "filters": [],
                "data_sources": {},
            }
        )
        with self.assertRaises(UserError):
            wizard.action_import()

    def test_action_import_rejects_unknown_model(self):
        """Skenario Uji negatif dari issue: impor berkas yang menyebut
        model `model.tidak.ada` → `UserError` yang memuat nama model
        itu.
        """
        wizard = self._wizard_from_definition(
            {
                "schema_version": 1,
                "dashboard": {"name": "Unknown Model Dashboard"},
                "items": [],
                "filters": [],
                "data_sources": {
                    "DS-UNKNOWN": {
                        "name": "Unknown Model DS",
                        "code": "DS-UNKNOWN",
                        "type": "orm",
                        "model": "model.tidak.ada",
                    }
                },
            }
        )
        with self.assertRaises(UserError) as capture:
            wizard.action_import()
        self.assertIn("model.tidak.ada", str(capture.exception))

    def test_action_import_rejects_malformed_json(self):
        """Skenario Uji negatif (keamanan): berkas bukan JSON valid →
        `UserError`, bukan traceback tak tertangani. Membuktikan
        `_parse_data_file` memakai `json.loads` (yang gagal aman pada
        input rusak) dan bukan `eval`/`pickle` (yang bisa
        mengeksekusi/mem-unpickle input arbitrer alih-alih hanya gagal
        parsing).
        """
        wizard = self.env["dashboard.import"].create(
            {
                "data_file": base64.b64encode(b"this is not json { at all"),
                "filename": "broken.json",
            }
        )
        with self.assertRaises(UserError):
            wizard.action_import()

    def test_action_import_rejects_unexpected_structure(self):
        """Skenario Uji negatif (keamanan): JSON valid tapi struktur
        tak terduga (mis. `dashboard` berupa string, bukan objek) →
        `UserError`, bukan `AttributeError`/`TypeError` mentah saat
        `action_import` mencoba membaca field-nya.
        """
        wizard = self._wizard_from_definition(
            {
                "schema_version": 1,
                "dashboard": "not-an-object",
                "items": [],
                "filters": [],
                "data_sources": {},
            }
        )
        with self.assertRaises(UserError):
            wizard.action_import()

    def test_prepare_export_definition_denied_for_dashboard_user(self):
        """Skenario Uji negatif dari issue (`as_user` bergrup
        `group_dashboard_user`): panggil `prepare_export_definition()`
        → `UserError`. Python murni — pemicu P1 (L-01, L-02): the
        assertion is on what a method call raises, not on a stored
        record field, and `as_user` in YAML only changes who a
        subsequent `action:`/`assert:` runs as, it cannot itself invoke
        an arbitrary method and capture its exception.
        """
        dashboard, _data_source = self._create_dashboard_with_items("DENY-EXPORT-01")
        user = new_test_user(
            self.env,
            login="dashboard-export-denied@example.com",
            groups="base.group_user,ssi_dashboard.group_dashboard_user",
        )
        with self.assertRaises(UserError):
            dashboard.with_user(user).prepare_export_definition()

    def test_action_import_denied_for_dashboard_user(self):
        """Sama seperti ekspor (Keputusan Desain: 'Ekspor dan impor
        hanya boleh dijalankan user bergrup group_dashboard_admin') —
        `action_import()` juga menolak `group_dashboard_user`. Python
        murni — pemicu P1 (L-01, L-02), alasan sama seperti test
        ekspor di atas.
        """
        dashboard, _data_source = self._create_dashboard_with_items("DENY-IMPORT-01")
        definition = dashboard.prepare_export_definition()
        user = new_test_user(
            self.env,
            login="dashboard-import-denied@example.com",
            groups="base.group_user,ssi_dashboard.group_dashboard_user",
        )
        wizard = self._wizard_from_definition(definition).with_user(user)
        with self.assertRaises(UserError):
            wizard.action_import()
