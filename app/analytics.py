"""Pure analytics over transactions. Every function takes `today` explicitly when time matters."""

from __future__ import annotations

import calendar
import datetime as dt
from collections import defaultdict
from collections.abc import Iterable

from app.categories import BY_ID, CATEGORIES, CHI, CHI_HO, GROUPS, THU, TIET_KIEM, ids_in_group
from app.models import Transaction

AT_RISK_MARGIN = 0.10
DEFAULT_LOOKBACK = 3


# Month helpers ----------------------------------------------------------------------------


def month_of(day: dt.date) -> str:
    return f"{day.year:04d}-{day.month:02d}"


def shift_month(month: str, delta: int) -> str:
    year, number = int(month[:4]), int(month[5:7])
    index = year * 12 + (number - 1) + delta
    return f"{index // 12:04d}-{index % 12 + 1:02d}"


def days_in_month(month: str) -> int:
    return calendar.monthrange(int(month[:4]), int(month[5:7]))[1]


# Aggregation ------------------------------------------------------------------------------


def category_totals(transactions: Iterable[Transaction]) -> dict[str, int]:
    totals = {category.id: 0 for category in CATEGORIES}
    for transaction in transactions:
        totals[transaction.category] = totals.get(transaction.category, 0) + transaction.amount
    return totals


def group_totals(categories: dict[str, int]) -> dict[str, int]:
    totals = {group_id: 0 for group_id, _ in GROUPS}
    for category_id, amount in categories.items():
        if category_id in BY_ID:
            totals[BY_ID[category_id].group] += amount
    return totals


def balance_of(groups: dict[str, int]) -> int:
    return groups[THU] - groups[CHI] - groups[CHI_HO] - groups[TIET_KIEM]


def monthly_category_totals(transactions: Iterable[Transaction]) -> dict[str, dict[str, int]]:
    by_month: dict[str, list[Transaction]] = defaultdict(list)
    for transaction in transactions:
        by_month[transaction.month].append(transaction)
    return {month: category_totals(items) for month, items in sorted(by_month.items())}


def _ratio(numerator: int, denominator: int) -> float | None:
    return round(numerator / denominator, 4) if denominator else None


# Monthly views ----------------------------------------------------------------------------


def month_summary(transactions: Iterable[Transaction], month: str) -> dict[str, object]:
    in_month = [transaction for transaction in transactions if transaction.month == month]
    categories = category_totals(in_month)
    groups = group_totals(categories)
    return {
        "month": month,
        "groups": groups,
        "categories": categories,
        "balance": balance_of(groups),
        "savings_rate": _ratio(groups[TIET_KIEM], groups[THU]),
        "spend_ratio": _ratio(groups[CHI], groups[THU]),
        "transaction_count": len(in_month),
    }


def month_sheet(transactions: Iterable[Transaction], month: str) -> dict[str, object]:
    """The monthly sheet in the template's layout: one row per entry, Total and All rows."""
    in_month = sorted(
        (transaction for transaction in transactions if transaction.month == month),
        key=lambda transaction: transaction.date,
    )
    summary = month_summary(in_month, month)
    return {
        "month": month,
        "columns": [category.__dict__ for category in CATEGORIES],
        "rows": [transaction.to_dict() for transaction in in_month],
        "total": summary["categories"],
        "all": {**summary["groups"], "balance": summary["balance"]},
    }


def budget_pace(month: str, today: dt.date) -> float:
    """Expected share of a monthly budget used by `today`."""
    current = month_of(today)
    if month < current:
        return 1.0
    if month > current:
        return 0.0
    return round(today.day / days_in_month(month), 4)


def budget_status(
    transactions: Iterable[Transaction],
    budgets: dict[str, int],
    month: str,
    today: dt.date,
) -> list[dict[str, object]]:
    spent = month_summary(transactions, month)["categories"]
    pace = budget_pace(month, today)
    rows = []
    for category_id in ids_in_group(CHI):
        budget = budgets.get(category_id, 0)
        amount = spent[category_id]
        used = _ratio(amount, budget)
        if not budget:
            status = "none"
        elif amount > budget:
            status = "over"
        elif used is not None and used > pace + AT_RISK_MARGIN:
            status = "at_risk"
        else:
            status = "ok"
        rows.append(
            {
                "category": category_id,
                "label": BY_ID[category_id].label,
                "spent": amount,
                "budget": budget,
                "remaining": budget - amount,
                "used": used,
                "pace": pace,
                "status": status,
            }
        )
    return rows


# Multi-month views ------------------------------------------------------------------------


def trend(
    transactions: Iterable[Transaction], end_month: str, months: int = 12
) -> list[dict[str, object]]:
    by_month = monthly_category_totals(transactions)
    rows = []
    for offset in range(months - 1, -1, -1):
        month = shift_month(end_month, -offset)
        groups = group_totals(by_month.get(month, {}))
        rows.append({"month": month, **groups, "balance": balance_of(groups)})
    return rows


def _average(rows: list[dict[str, int]], keys: Iterable[str]) -> dict[str, int]:
    keys = list(keys)
    if not rows:
        return {key: 0 for key in keys}
    return {key: round(sum(row.get(key, 0) for row in rows) / len(rows)) for key in keys}


def annual_projection(transactions: Iterable[Transaction], year: int, today: dt.date) -> dict:
    """YTD actuals for complete months + their average pace for every other month of the year.

    The current month is still partial, so it is replaced by the average instead of being
    counted as a low month.
    """
    by_month = monthly_category_totals(transactions)
    current = month_of(today)
    group_ids = [group_id for group_id, _ in GROUPS]

    complete = [f"{year:04d}-{number:02d}" for number in range(1, 13)]
    complete = [month for month in complete if month < current]
    tracked = [group_totals(by_month[month]) for month in complete if month in by_month]
    average = _average(tracked, group_ids)

    months = []
    projected = {group_id: 0 for group_id in group_ids}
    ytd = {group_id: 0 for group_id in group_ids}
    for number in range(1, 13):
        month = f"{year:04d}-{number:02d}"
        actual = group_totals(by_month.get(month, {}))
        if month <= current:
            for group_id in group_ids:
                ytd[group_id] += actual[group_id]
        is_actual = month in complete and month in by_month
        values = actual if is_actual else average
        for group_id in group_ids:
            projected[group_id] += values[group_id]
        months.append(
            {"month": month, **values, "balance": balance_of(values), "projected": not is_actual}
        )

    return {
        "year": year,
        "months": months,
        "tracked_months": len(tracked),
        "monthly_average": {**average, "balance": balance_of(average)},
        "ytd": {**ytd, "balance": balance_of(ytd)},
        "projected": {**projected, "balance": balance_of(projected)},
        "projected_savings_rate": _ratio(projected[TIET_KIEM], projected[THU]),
    }


def category_baseline(
    transactions: Iterable[Transaction], before_month: str, lookback: int = DEFAULT_LOOKBACK
) -> dict[str, int]:
    """Average per category over the last `lookback` months with data before `before_month`."""
    by_month = monthly_category_totals(transactions)
    history = [totals for month, totals in by_month.items() if month < before_month][-lookback:]
    return _average(history, [category.id for category in CATEGORIES])


def what_if(
    transactions: Iterable[Transaction],
    cuts: dict[str, float],
    today: dt.date,
    lookback: int = DEFAULT_LOOKBACK,
) -> dict[str, object]:
    transactions = list(transactions)
    current = month_of(today)
    baseline = category_baseline(transactions, current, lookback)
    if not any(baseline.values()):
        # No complete history yet: fall back to the month in progress.
        baseline = category_totals(t for t in transactions if t.month == current)

    lines = []
    for category_id in ids_in_group(CHI):
        cut = cuts.get(category_id, 0.0)
        monthly_gain = round(baseline[category_id] * cut)
        lines.append(
            {
                "category": category_id,
                "label": BY_ID[category_id].label,
                "average": baseline[category_id],
                "cut": cut,
                "monthly_gain": monthly_gain,
                "annual_gain": monthly_gain * 12,
            }
        )
    monthly = sum(line["monthly_gain"] for line in lines)
    return {"lines": lines, "monthly_gain": monthly, "annual_gain": monthly * 12}
