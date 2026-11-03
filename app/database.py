"""SQLite storage for transactions and budgets."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterable
from pathlib import Path

from app.models import Transaction

SCHEMA = """
CREATE TABLE IF NOT EXISTS transactions (
    id TEXT PRIMARY KEY,
    date TEXT NOT NULL,
    name TEXT NOT NULL,
    category TEXT NOT NULL,
    amount INTEGER NOT NULL,
    note TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_transactions_date ON transactions(date);
CREATE TABLE IF NOT EXISTS budgets (
    month TEXT NOT NULL,
    category TEXT NOT NULL,
    amount INTEGER NOT NULL,
    PRIMARY KEY (month, category)
);
"""


class FinanceStore:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(self.path, check_same_thread=False)
        self.connection.row_factory = sqlite3.Row
        self.connection.executescript(SCHEMA)
        self.connection.commit()

    # Transactions -------------------------------------------------------------------------

    def add_transactions(self, transactions: Iterable[Transaction]) -> int:
        """Insert or replace by id, so re-importing the same rows never duplicates them."""
        cursor = self.connection.executemany(
            """
            INSERT OR REPLACE INTO transactions (id, date, name, category, amount, note)
            VALUES (:id, :date, :name, :category, :amount, :note)
            """,
            [transaction.to_dict() for transaction in transactions],
        )
        self.connection.commit()
        return cursor.rowcount

    def get_transaction(self, transaction_id: str) -> Transaction | None:
        row = self.connection.execute(
            "SELECT * FROM transactions WHERE id = ?", (transaction_id,)
        ).fetchone()
        return Transaction(**dict(row)) if row else None

    def update_transaction(self, transaction: Transaction) -> bool:
        cursor = self.connection.execute(
            """
            UPDATE transactions SET date = :date, name = :name, category = :category,
                amount = :amount, note = :note
            WHERE id = :id
            """,
            transaction.to_dict(),
        )
        self.connection.commit()
        return cursor.rowcount > 0

    def delete_transaction(self, transaction_id: str) -> bool:
        cursor = self.connection.execute("DELETE FROM transactions WHERE id = ?", (transaction_id,))
        self.connection.commit()
        return cursor.rowcount > 0

    def list_transactions(self, month: str | None = None) -> list[Transaction]:
        if month:
            rows = self.connection.execute(
                "SELECT * FROM transactions WHERE substr(date, 1, 7) = ? ORDER BY date, rowid",
                (month,),
            ).fetchall()
        else:
            rows = self.connection.execute(
                "SELECT * FROM transactions ORDER BY date, rowid"
            ).fetchall()
        return [Transaction(**dict(row)) for row in rows]

    def clear(self) -> None:
        self.connection.execute("DELETE FROM transactions")
        self.connection.execute("DELETE FROM budgets")
        self.connection.commit()

    # Budgets ------------------------------------------------------------------------------

    def set_budget(self, month: str, category: str, amount: int) -> None:
        """Set the budget from `month` onward. An amount of 0 removes it from then on."""
        self.connection.execute(
            "INSERT OR REPLACE INTO budgets (month, category, amount) VALUES (?, ?, ?)",
            (month, category, amount),
        )
        self.connection.commit()

    def budgets_for(self, month: str) -> dict[str, int]:
        """Effective budgets: the latest value set at or before `month` (carry-forward)."""
        rows = self.connection.execute(
            """
            SELECT b.category, b.amount FROM budgets b
            WHERE b.month = (
                SELECT MAX(month) FROM budgets
                WHERE category = b.category AND month <= ?
            )
            """,
            (month,),
        ).fetchall()
        return {row["category"]: row["amount"] for row in rows if row["amount"] > 0}

    def close(self) -> None:
        self.connection.close()
