from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from app.database import FinanceStore
from tests.helpers import tx


class FinanceStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.store = FinanceStore(Path(self.temp_dir.name) / "savings.db")

    def tearDown(self) -> None:
        self.store.close()
        self.temp_dir.cleanup()

    def test_add_list_filters_by_month(self) -> None:
        self.store.add_transactions([tx("2026-10-31", "xang", 100), tx("2026-11-01", "xang", 200)])
        self.assertEqual(len(self.store.list_transactions()), 2)
        self.assertEqual([t.amount for t in self.store.list_transactions("2026-11")], [200])

    def test_add_is_idempotent_by_id(self) -> None:
        row = tx("2026-11-01", "xang", 200)
        self.store.add_transactions([row])
        self.store.add_transactions([row])
        self.assertEqual(len(self.store.list_transactions()), 1)

    def test_update_and_delete(self) -> None:
        row = tx("2026-11-01", "xang", 200)
        self.store.add_transactions([row])
        row.amount = 300
        self.assertTrue(self.store.update_transaction(row))
        self.assertEqual(self.store.get_transaction(row.id).amount, 300)
        self.assertTrue(self.store.delete_transaction(row.id))
        self.assertFalse(self.store.delete_transaction(row.id))
        self.assertIsNone(self.store.get_transaction(row.id))

    def test_budgets_carry_forward_until_changed(self) -> None:
        self.store.set_budget("2026-09", "an_choi", 3_000_000)
        self.store.set_budget("2026-11", "an_choi", 2_000_000)
        self.store.set_budget("2026-10", "xang", 500_000)
        self.assertEqual(self.store.budgets_for("2026-08"), {})
        self.assertEqual(self.store.budgets_for("2026-10"), {"an_choi": 3_000_000, "xang": 500_000})
        self.assertEqual(self.store.budgets_for("2027-01"), {"an_choi": 2_000_000, "xang": 500_000})

    def test_zero_budget_removes_it_from_that_month(self) -> None:
        self.store.set_budget("2026-09", "an_choi", 3_000_000)
        self.store.set_budget("2026-11", "an_choi", 0)
        self.assertEqual(self.store.budgets_for("2026-10"), {"an_choi": 3_000_000})
        self.assertEqual(self.store.budgets_for("2026-12"), {})


if __name__ == "__main__":
    unittest.main()
