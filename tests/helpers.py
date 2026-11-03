from __future__ import annotations

from app.models import Transaction


def tx(date: str, category: str, amount: int, name: str = "x") -> Transaction:
    tx.counter += 1
    return Transaction(f"t{tx.counter}", date, name, category, amount)


tx.counter = 0


def salary_month(
    month: str, *, an_choi: int = 2_000_000, saved: int = 5_000_000
) -> list[Transaction]:
    """A typical month: 20M salary, 6M living costs, some fun, a transfer to savings."""
    return [
        tx(f"{month}-01", "sinh_hoat_phi", 6_000_000),
        tx(f"{month}-05", "luong", 20_000_000),
        tx(f"{month}-06", "tiet_kiem", saved),
        tx(f"{month}-10", "an_choi", an_choi),
    ]
