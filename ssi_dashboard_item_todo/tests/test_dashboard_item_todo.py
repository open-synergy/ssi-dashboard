# Copyright 2026 OpenSynergy Indonesia
# Copyright 2026 PT. Simetri Sinergi Indonesia
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from odoo_yaml_test import YamlTransactionCase

from odoo.tests import tagged


@tagged("post_install", "-at_install")
class TestDashboardItemTodo(YamlTransactionCase):
    def test_dashboard_item_todo(self):
        self.run_yaml_scenario("test_data_dashboard_item_todo.yaml")

    def _create_todo_item(self, code_suffix, **item_values):
        dashboard = self.env["dashboard.dashboard"].create(
            {"name": "To Do Dashboard", "code": f"DASH-TODO-PY-{code_suffix}"}
        )
        values = {
            "name": "Month-End Checklist",
            "dashboard_id": dashboard.id,
            "type": "todo",
        }
        values.update(item_values)
        return self.env["dashboard.item"].create(values)

    def test_toggle_todo_done_flips_and_returns_new_value(self):
        """Python murni — P1 (L-01, L-02): `toggle_todo_done` mengembalikan

        nilai `done` yang baru; `action: call` di YAML membuang nilai
        balik method (L-01) dan sisi "actual" sebuah assert selalu berupa
        dotted `getattr` pada record (L-02), sehingga nilai balik itu
        sendiri hanya bisa diverifikasi lewat pemanggilan Python langsung.
        Sebuah baris `task` yang baru dibuat harus `done` = False, dan
        memanggil `toggle_todo_done()` sekali harus membuatnya True —
        sekaligus nilai balik method itu sendiri harus True — sesuai
        Skenario Uji issue #33.
        """
        item = self._create_todo_item("01")
        row = self.env["dashboard.item.todo"].create(
            {
                "item_id": item.id,
                "name": "Close the books",
                "line_type": "task",
            }
        )
        self.assertFalse(row.done)
        result = row.toggle_todo_done()
        self.assertTrue(result)
        self.assertTrue(row.done)

    def test_prepare_render_payload_todo_key_ordered_by_sequence(self):
        """Python murni — P3 (L-06): urutan baris x2m tertentu tak bisa

        di-assert lewat YAML. Sebuah item to-do dengan tiga baris
        (sequence 30, 10, 20, dalam urutan pembuatan itu) harus membuat
        `_prepare_render_payload()`'s 'todo' key memuat tiga dict
        terurut menaik berdasarkan 'Sequence' (10, 20, 30), tidak
        mengikuti urutan pembuatan — sesuai Skenario Uji issue #33.
        """
        item = self._create_todo_item("02")
        row_third = self.env["dashboard.item.todo"].create(
            {
                "item_id": item.id,
                "sequence": 30,
                "name": "Third",
                "line_type": "task",
            }
        )
        row_first = self.env["dashboard.item.todo"].create(
            {
                "item_id": item.id,
                "sequence": 10,
                "name": "First",
                "line_type": "section",
            }
        )
        row_second = self.env["dashboard.item.todo"].create(
            {
                "item_id": item.id,
                "sequence": 20,
                "name": "Second",
                "line_type": "task",
                "done": True,
            }
        )
        payload = item._prepare_render_payload()
        self.assertIn("todo", payload)
        todo_rows = payload["todo"]
        self.assertEqual(len(todo_rows), 3)
        self.assertEqual(
            [row["id"] for row in todo_rows],
            [row_first.id, row_second.id, row_third.id],
        )
        self.assertEqual(
            [row["name"] for row in todo_rows], ["First", "Second", "Third"]
        )
        self.assertEqual(
            [row["line_type"] for row in todo_rows],
            ["section", "task", "task"],
        )
        self.assertEqual([row["done"] for row in todo_rows], [False, True, False])
