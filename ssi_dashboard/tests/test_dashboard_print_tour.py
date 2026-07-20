# Copyright 2026 OpenSynergy Indonesia
# Copyright 2026 PT. Simetri Sinergi Indonesia
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from odoo.tests import HttpCase, new_test_user, tagged


@tagged("post_install", "-at_install")
class TestDashboardPrintTour(HttpCase):
    """Python murni — pemicu P7 (L-19: controller HTTP/route/tour JS
    hanya bisa dijangkau lewat `HttpCase`, sepenuhnya di luar jangkauan
    `odoo-yaml-test`'s `YamlTransactionCase`).

    Menutup dua Skenario Uji backlog issue #49 yang eksplisit meminta
    `HttpCase` + tour: mengaktifkan mode cetak menyembunyikan kerangka
    backend & menampilkan judul dashboard (positif), dan tombol cetak
    tidak dirender saat 'allow_pdf_export' mati (negatif). Tour-nya
    sendiri ada di 'static/tests/tours/dashboard_print.esm.js'.
    """

    def _create_client_action(self, dashboard):
        """Bikin `ir.actions.client` langsung, mengikuti pola yang sama
        seperti `dashboard.dashboard._sync_menu()` sendiri, tanpa perlu
        `generate_menu`/`parent_menu_id` — supaya URL
        `/odoo/action-<id>` bisa dibuka tour tanpa efek samping
        tambahan (tak ada menu yang perlu ada).
        """
        return self.env["ir.actions.client"].create(
            {
                "name": dashboard.name,
                "tag": "ssi_dashboard.dashboard_view",
                "context": repr({"dashboard_id": dashboard.id}),
            }
        )

    def test_print_mode_hides_chrome_and_shows_title(self):
        """Skenario Uji positif: buka dashboard, aktifkan mode cetak,
        pastikan elemen kerangka backend tersembunyi & judul dashboard
        terlihat.
        """
        dashboard = self.env["dashboard.dashboard"].create(
            {"name": "Print Mode Tour Dashboard", "code": "DASH-PRINT-TOUR-01"}
        )
        action = self._create_client_action(dashboard)
        user = new_test_user(
            self.env,
            login="dashboard-print-user@example.com",
            groups="base.group_user,ssi_dashboard.group_dashboard_user",
        )
        self.start_tour(
            f"/odoo/action-{action.id}",
            "ssi_dashboard_print_mode_tour",
            login=user.login,
        )

    def test_print_button_hidden_when_allow_pdf_export_disabled(self):
        """Skenario Uji negatif: dashboard ber-'allow_pdf_export' =
        False → tombol cetak tidak ditemukan di halaman.
        """
        dashboard = self.env["dashboard.dashboard"].create(
            {
                "name": "Print Disabled Tour Dashboard",
                "code": "DASH-PRINT-TOUR-02",
                "allow_pdf_export": False,
            }
        )
        action = self._create_client_action(dashboard)
        user = new_test_user(
            self.env,
            login="dashboard-print-disabled-user@example.com",
            groups="base.group_user,ssi_dashboard.group_dashboard_user",
        )
        self.start_tour(
            f"/odoo/action-{action.id}",
            "ssi_dashboard_print_disabled_tour",
            login=user.login,
        )
