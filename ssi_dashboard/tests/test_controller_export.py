# Copyright 2026 OpenSynergy Indonesia
# Copyright 2026 PT. Simetri Sinergi Indonesia
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from odoo.tests import HttpCase, new_test_user, tagged
from odoo.tools import mute_logger


@tagged("post_install", "-at_install")
class TestDashboardItemExportController(HttpCase):
    """Python murni — pemicu P8 (L-19: controller HTTP/route hanya bisa
    dijangkau lewat `HttpCase`, sepenuhnya di luar jangkauan
    `odoo-yaml-test`'s `YamlTransactionCase`).

    Hanya menguji dua Skenario Uji negatif dari issue #43 — respons
    endpoint gagal (bukan berkas) saat 'Allow Export' mati, dan saat user
    tidak punya hak baca item. Jalur positif (isi `prepare_export_data`)
    sudah diuji Python murni di `test_dashboard_item_export.py`; endpoint
    itu sendiri hanya memanggil method itu, jadi tidak diulang di sini.
    """

    def _create_item(self, code_suffix, **item_vals):
        """Shared fixture: one data source over 'res.partner', one
        dashboard, one item — 'code_suffix' keeps every scenario's
        'code' unique so they never collide in the same transaction.
        """
        partner_model = self.env.ref("base.model_res_partner")
        data_source = self.env["dashboard.data_source"].create(
            {
                "name": "Export Partners",
                "code": f"DASH-EXPORT-DS-{code_suffix}",
                "type": "orm",
                "model_id": partner_model.id,
            }
        )
        dashboard = self.env["dashboard.dashboard"].create(
            {
                "name": "Export Dashboard",
                "code": f"DASH-EXPORT-DASH-{code_suffix}",
            }
        )
        values = {
            "name": f"Export Item {code_suffix}",
            "dashboard_id": dashboard.id,
            "type": "placeholder",
            "data_source_id": data_source.id,
        }
        values.update(item_vals)
        return self.env["dashboard.item"].create(values)

    @mute_logger("odoo.http")
    def test_export_xlsx_rejects_item_with_allow_export_disabled(self):
        """Skenario Uji negatif: panggil endpoint XLSX untuk item ber-
        'Allow Export' = False → respons gagal, bukan berkas. The
        requesting user is otherwise a normal dashboard user (has read
        access) so the failure is unambiguously about 'allow_export',
        not about access rights.

        `mute_logger("odoo.http")` bungkam baris WARNING NORMAL yang
        dicetak `odoo.http`'s dispatcher saat `UserError` yang sengaja
        dipicu di sini merambat keluar dari route `type="http"`; tanpa
        ini `oca_checklog_odoo` menggagalkan CI walau test lulus (lihat
        `python-escape-hatch.md` bagian "Jebakan CI").
        """
        item = self._create_item("XLSX-01", allow_export=False)
        user = new_test_user(
            self.env,
            login="dashboard-export-user-xlsx@example.com",
            groups="base.group_user,ssi_dashboard.group_dashboard_user",
        )
        self.authenticate(user.login, user.login)
        response = self.url_open(f"/ssi_dashboard/export/xlsx?item_id={item.id}")
        self.assertNotEqual(response.status_code, 200)

    @mute_logger("odoo.http")
    def test_export_csv_rejects_user_without_read_access(self):
        """Skenario Uji negatif: panggil endpoint CSV sebagai user tanpa
        hak baca item ('Allow Export' stays at its True default, so the
        failure is unambiguously about access, not about
        'allow_export') → respons gagal.

        `mute_logger("odoo.http")` — sama seperti di atas, membungkam
        baris WARNING normal yang dicetak `odoo.http` saat `AccessError`
        yang sengaja dipicu di sini merambat keluar dari route
        `type="http"`.
        """
        item = self._create_item("CSV-01")
        user = new_test_user(
            self.env,
            login="dashboard-export-user-noaccess@example.com",
            groups="base.group_user",
        )
        self.authenticate(user.login, user.login)
        response = self.url_open(f"/ssi_dashboard/export/csv?item_id={item.id}")
        self.assertNotEqual(response.status_code, 200)
