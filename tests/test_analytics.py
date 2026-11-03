from __future__ import annotations

import datetime as dt
import unittest

from app import analytics
from tests.helpers import salary_month, tx


class MonthHelperTests(unittest.TestCase):
    def test_shift_month_crosses_years(self) -> None:
        self.assertEqual(analytics.shift_month("2026-01", -1), "2025-12")
        self.assertEqual(analytics.shift_month("2026-11", 3), "2027-02")

    def test_budget_pace(self) -> None:
        today = dt.date(2026, 11, 15)
        self.assertEqual(analytics.budget_pace("2026-11", today), 0.5)
        self.assertEqual(analytics.budget_pace("2026-10", today), 1.0)
        self.assertEqual(analytics.budget_pace("2026-12", today), 0.0)


class SummaryTests(unittest.TestCase):
    def test_summary_groups_balance_and_ratios(self) -> None:
        rows = salary_month("2026-10") + [tx("2026-10-12", "chi_ho", 1_000_000)]
        summary = analytics.month_summary(rows, "2026-10")
        self.assertEqual(
            summary["groups"],
            {"chi": 8_000_000, "chi_ho": 1_000_000, "tiet_kiem": 5_000_000, "thu": 20_000_000},
        )
        self.assertEqual(summary["balance"], 6_000_000)
        self.assertEqual(summary["savings_rate"], 0.25)
        self.assertEqual(summary["spend_ratio"], 0.4)

    def test_summary_without_income_has_no_ratios(self) -> None:
        summary = analytics.month_summary([tx("2026-10-01", "xang", 100_000)], "2026-10")
        self.assertIsNone(summary["savings_rate"])
        self.assertEqual(summary["balance"], -100_000)

    def test_sheet_matches_template_layout(self) -> None:
        sheet = analytics.month_sheet(salary_month("2026-10") + salary_month("2026-09"), "2026-10")
        self.assertEqual(sheet["columns"][0]["label"], "Sinh hoạt phí")
        self.assertEqual(sheet["columns"][-1]["label"], "Lương")
        self.assertEqual(len(sheet["rows"]), 4)
        self.assertEqual(sheet["total"]["an_choi"], 2_000_000)
        self.assertEqual(sheet["all"]["balance"], 7_000_000)


class BudgetStatusTests(unittest.TestCase):
    def test_statuses_respect_pace(self) -> None:
        rows = [
            tx("2026-11-02", "an_choi", 2_500_000),  # 83% used at 33% pace -> at risk
            tx("2026-11-03", "xang", 700_000),  # over
            tx("2026-11-04", "mua_sam", 200_000),  # 10% -> ok
        ]
        budgets = {"an_choi": 3_000_000, "xang": 600_000, "mua_sam": 2_000_000}
        status = {
            row["category"]: row["status"]
            for row in analytics.budget_status(rows, budgets, "2026-11", dt.date(2026, 11, 10))
        }
        self.assertEqual(status["an_choi"], "at_risk")
        self.assertEqual(status["xang"], "over")
        self.assertEqual(status["mua_sam"], "ok")
        self.assertEqual(status["yeu"], "none")


class MultiMonthTests(unittest.TestCase):
    def test_trend_fills_missing_months_with_zero(self) -> None:
        rows = analytics.trend(salary_month("2026-09") + salary_month("2026-11"), "2026-11", 3)
        self.assertEqual([row["month"] for row in rows], ["2026-09", "2026-10", "2026-11"])
        self.assertEqual(rows[1]["thu"], 0)
        self.assertEqual(rows[2]["tiet_kiem"], 5_000_000)

    def test_projection_uses_complete_months_and_skips_partial_current(self) -> None:
        history = salary_month("2026-09") + salary_month("2026-10", saved=3_000_000)
        partial = [tx("2026-11-01", "sinh_hoat_phi", 6_000_000)]
        result = analytics.annual_projection(history + partial, 2026, dt.date(2026, 11, 2))

        self.assertEqual(result["tracked_months"], 2)
        self.assertEqual(result["monthly_average"]["tiet_kiem"], 4_000_000)
        # 2 actual months (8M) + 10 months at the 4M average.
        self.assertEqual(result["projected"]["tiet_kiem"], 8_000_000 + 10 * 4_000_000)
        self.assertEqual(result["ytd"]["chi"], 22_000_000)
        november = result["months"][10]
        self.assertTrue(november["projected"])
        self.assertFalse(result["months"][8]["projected"])
        self.assertEqual(result["projected_savings_rate"], 0.2)

    def test_projection_without_history_is_zero(self) -> None:
        result = analytics.annual_projection([], 2026, dt.date(2026, 11, 2))
        self.assertEqual(result["projected"]["tiet_kiem"], 0)
        self.assertIsNone(result["projected_savings_rate"])

    def test_what_if_uses_last_three_months(self) -> None:
        rows = (
            salary_month("2026-07", an_choi=9_000_000)  # outside the 3-month window
            + salary_month("2026-08", an_choi=1_000_000)
            + salary_month("2026-09", an_choi=2_000_000)
            + salary_month("2026-10", an_choi=3_000_000)
        )
        result = analytics.what_if(rows, {"an_choi": 0.5}, dt.date(2026, 11, 2))
        line = next(line for line in result["lines"] if line["category"] == "an_choi")
        self.assertEqual(line["average"], 2_000_000)
        self.assertEqual(result["monthly_gain"], 1_000_000)
        self.assertEqual(result["annual_gain"], 12_000_000)

    def test_what_if_falls_back_to_current_month(self) -> None:
        rows = [tx("2026-11-01", "an_choi", 1_000_000)]
        result = analytics.what_if(rows, {"an_choi": 0.2}, dt.date(2026, 11, 2))
        self.assertEqual(result["monthly_gain"], 200_000)


if __name__ == "__main__":
    unittest.main()
