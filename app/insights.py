"""Rule-based savings advisor.

Each rule reads the month's numbers and returns structured `Insight`s with an estimated
annual VND impact. The output is deliberately structured so an LLM narrator can be layered
on later without ever being trusted to compute the numbers itself.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import asdict, dataclass

from app import analytics
from app.categories import BY_ID, CHI_HO, NEEDS, THU, TIET_KIEM, WANTS, ids_of_kind
from app.models import Transaction

TARGET_SAVINGS_RATE = 0.20
NEEDS_LIMIT = 0.50
WANTS_LIMIT = 0.30
ANOMALY_FACTOR = 1.3
ANOMALY_MIN_VND = 200_000
SUGGESTED_CUT = 0.20

SEVERITY_RANK = {"critical": 0, "warning": 1, "info": 2}


@dataclass
class Insight:
    id: str
    severity: str  # critical | warning | info
    title: str
    detail: str
    annual_impact: int = 0

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def vnd(amount: int) -> str:
    return f"{amount:,.0f}".replace(",", ".") + " ₫"


def pct(ratio: float) -> str:
    return f"{ratio * 100:.0f}%"


def generate(
    transactions: list[Transaction],
    budgets: dict[str, int],
    month: str,
    today: dt.date,
) -> list[Insight]:
    summary = analytics.month_summary(transactions, month)
    if not summary["transaction_count"]:
        return [
            Insight(
                "empty",
                "info",
                "Chưa có dữ liệu tháng này",
                "Thêm giao dịch hoặc import file CSV từ bảng chi tiêu để nhận gợi ý.",
            )
        ]

    groups, categories = summary["groups"], summary["categories"]
    income = groups[THU]
    insights: list[Insight] = []

    # Early in the current month salary may simply not have arrived yet.
    month_closed = month < analytics.month_of(today)
    if summary["balance"] < 0 and (income or month_closed):
        insights.append(
            Insight(
                "negative_balance",
                "critical",
                "Chi vượt thu",
                f"Tháng này đang âm {vnd(-summary['balance'])}. "
                "Hãy kiểm tra các khoản Ăn chơi / Mua sắm trước khi chạm vào tiền tiết kiệm.",
            )
        )

    if not income:
        insights.append(
            Insight(
                "no_income",
                "info",
                "Chưa ghi nhận thu nhập",
                "Nhập Lương / Được cho để tính tỷ lệ tiết kiệm và cơ cấu chi tiêu.",
            )
        )
    else:
        insights.extend(_ratio_rules(income, groups[TIET_KIEM], categories))

    insights.extend(_anomaly_rules(transactions, month, categories))
    insights.extend(_budget_rules(transactions, budgets, month, today))

    if groups[CHI_HO]:
        insights.append(
            Insight(
                "chi_ho_outstanding",
                "info",
                "Nhớ thu lại khoản chi hộ",
                f"Bạn đã chi hộ {vnd(groups[CHI_HO])} trong tháng. Đánh dấu và đòi lại để "
                "không bị tính nhầm vào chi tiêu cá nhân.",
            )
        )

    return sorted(insights, key=lambda item: (SEVERITY_RANK[item.severity], -item.annual_impact))


def _ratio_rules(income: int, saved: int, categories: dict[str, int]) -> list[Insight]:
    insights = []
    rate = saved / income
    if rate < TARGET_SAVINGS_RATE:
        gap = round(TARGET_SAVINGS_RATE * income) - saved
        insights.append(
            Insight(
                "savings_rate_gap",
                "warning",
                f"Tỷ lệ tiết kiệm {pct(rate)} — mục tiêu {pct(TARGET_SAVINGS_RATE)}",
                f"Cần để dành thêm {vnd(gap)}/tháng để đạt mục tiêu.",
                gap * 12,
            )
        )

    needs = sum(categories[category_id] for category_id in ids_of_kind(NEEDS))
    if needs / income > NEEDS_LIMIT:
        insights.append(
            Insight(
                "needs_share",
                "warning",
                f"Chi thiết yếu chiếm {pct(needs / income)} thu nhập",
                f"Quy tắc 50/30/20 gợi ý ≤ {pct(NEEDS_LIMIT)}. Xem lại Sinh hoạt phí và Xăng.",
            )
        )

    wants_ids = ids_of_kind(WANTS)
    wants = sum(categories[category_id] for category_id in wants_ids)
    if wants / income > WANTS_LIMIT:
        excess = wants - round(WANTS_LIMIT * income)
        insights.append(
            Insight(
                "wants_share",
                "warning",
                f"Chi hưởng thụ chiếm {pct(wants / income)} thu nhập",
                f"Vượt mức {pct(WANTS_LIMIT)} khoảng {vnd(excess)}/tháng.",
                excess * 12,
            )
        )

    top = max(wants_ids, key=lambda category_id: categories[category_id])
    if categories[top]:
        cut = round(categories[top] * SUGGESTED_CUT)
        insights.append(
            Insight(
                f"cut_{top}",
                "info",
                f"Giảm {pct(SUGGESTED_CUT)} {BY_ID[top].label}",
                f"Khoản hưởng thụ lớn nhất tháng này là {BY_ID[top].label} "
                f"({vnd(categories[top])}). Cắt {pct(SUGGESTED_CUT)} = {vnd(cut)}/tháng.",
                cut * 12,
            )
        )
    return insights


def _anomaly_rules(
    transactions: list[Transaction], month: str, categories: dict[str, int]
) -> list[Insight]:
    baseline = analytics.category_baseline(transactions, month)
    if not any(baseline.values()):
        return []
    insights = []
    for category_id in ids_of_kind(NEEDS) + ids_of_kind(WANTS) + ids_of_kind("social"):
        spent, usual = categories[category_id], baseline[category_id]
        if usual and spent >= usual * ANOMALY_FACTOR and spent - usual >= ANOMALY_MIN_VND:
            insights.append(
                Insight(
                    f"anomaly_{category_id}",
                    "warning",
                    f"{BY_ID[category_id].label} tăng bất thường",
                    f"{vnd(spent)} so với trung bình {vnd(usual)} của các tháng trước "
                    f"(+{pct(spent / usual - 1)}).",
                    (spent - usual) * 12,
                )
            )
    return insights


def _budget_rules(
    transactions: list[Transaction], budgets: dict[str, int], month: str, today: dt.date
) -> list[Insight]:
    insights = []
    for row in analytics.budget_status(transactions, budgets, month, today):
        if row["status"] == "over":
            over = row["spent"] - row["budget"]
            insights.append(
                Insight(
                    f"budget_over_{row['category']}",
                    "critical",
                    f"Vượt ngân sách {row['label']}",
                    f"Đã chi {vnd(row['spent'])} / ngân sách {vnd(row['budget'])} "
                    f"(vượt {vnd(over)}).",
                    over * 12,
                )
            )
        elif row["status"] == "at_risk":
            insights.append(
                Insight(
                    f"budget_risk_{row['category']}",
                    "warning",
                    f"{row['label']} chi nhanh hơn kế hoạch",
                    f"Đã dùng {pct(row['used'])} ngân sách khi mới qua {pct(row['pace'])} tháng.",
                )
            )
    return insights
