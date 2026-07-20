# Copyright 2026 OpenSynergy Indonesia
# Copyright 2026 PT. Simetri Sinergi Indonesia
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from odoo_yaml_test import YamlTransactionCase

from odoo.tests import tagged


@tagged("post_install", "-at_install")
class TestDashboardItemMove(YamlTransactionCase):
    def test_dashboard_item_move(self):
        self.run_yaml_scenario("test_data_dashboard_item_move.yaml")
