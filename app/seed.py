"""Generate deterministic demo data: `python -m app.seed [--months N] [--reset]`.

Seeding is always explicit so demo rows never mix into a real ledger by accident.
"""

from __future__ import annotations

import argparse
import datetime as dt
import random

from app import analytics
from app.config import database_path
from app.database import FinanceStore
from app.models import Transaction

SALARY = 25_000_000
RENT = 5_000_000
SAVINGS = 4_000_000

DEMO_BUDGETS = {
    "sinh_hoat_phi": 9_000_000,
    "xang": 600_000,
    "an_choi": 3_000_000,
    "mua_sam": 2_000_000,
    "dam_dinh": 1_000_000,
    "yeu": 2_500_000,
}


def demo_transactions(today: dt.date, months: int = 6, seed: int = 2026) -> list[Transaction]:
    rng = random.Random(seed)
    current = analytics.month_of(today)
    transactions: list[Transaction] = []

    def add(month: str, day: int, name: str, category: str, amount: int) -> None:
        last_day = analytics.days_in_month(month) if month < current else today.day
        if day > last_day:
            return
        date = f"{month}-{day:02d}"
        transactions.append(
            Transaction(f"demo_{len(transactions):05d}", date, name, category, amount)
        )

    for offset in range(months - 1, -1, -1):
        month = analytics.shift_month(current, -offset)
        add(month, 1, "Tiền nhà", "sinh_hoat_phi", RENT)
        add(month, 3, "Điện nước, internet", "sinh_hoat_phi", rng.randint(9, 14) * 100_000)
        add(month, 5, "Lương tháng", "luong", SALARY)
        add(month, 6, "Chuyển tiết kiệm", "tiet_kiem", SAVINGS)
        for week_day in (2, 9, 16, 23):
            add(month, week_day, "Đi chợ", "sinh_hoat_phi", rng.randint(5, 9) * 100_000)
            add(month, week_day + 1, "Đổ xăng", "xang", rng.randint(7, 12) * 10_000)
        for _ in range(rng.randint(4, 8)):
            add(
                month,
                rng.randint(1, 28),
                "Cà phê / ăn ngoài",
                "an_choi",
                rng.randint(1, 6) * 100_000,
            )
        for _ in range(rng.randint(1, 3)):
            add(
                month, rng.randint(1, 28), "Mua sắm online", "mua_sam", rng.randint(2, 12) * 100_000
            )
        for _ in range(rng.randint(2, 4)):
            add(month, rng.randint(1, 28), "Hẹn hò", "yeu", rng.randint(3, 8) * 100_000)
        if rng.random() < 0.5:
            add(
                month,
                rng.randint(1, 28),
                "Đám cưới bạn",
                "dam_dinh",
                rng.choice([500_000, 1_000_000]),
            )
        if rng.random() < 0.4:
            add(month, rng.randint(1, 28), "Mua đồ giúp mẹ", "chi_ho", rng.randint(2, 6) * 100_000)
        if rng.random() < 0.3:
            add(month, rng.randint(1, 28), "Mẹ cho", "duoc_cho", 1_000_000)
    return transactions


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--months", type=int, default=6)
    parser.add_argument("--reset", action="store_true", help="delete all existing data first")
    args = parser.parse_args()

    today = dt.date.today()
    store = FinanceStore(database_path())
    try:
        if args.reset:
            store.clear()
        transactions = demo_transactions(today, args.months)
        store.add_transactions(transactions)
        first_month = analytics.shift_month(analytics.month_of(today), -(args.months - 1))
        for category, amount in DEMO_BUDGETS.items():
            store.set_budget(first_month, category, amount)
    finally:
        store.close()
    print(f"Seeded {len(transactions)} demo transactions into {database_path()}")


if __name__ == "__main__":
    main()
