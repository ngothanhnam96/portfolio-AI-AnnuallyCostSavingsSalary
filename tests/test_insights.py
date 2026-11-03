from __future__ import annotations

import datetime as dt
import unittest

from app import insights
from tests.helpers import salary_month, tx

TODAY = dt.date(2026, 11, 20)


def ids(found: list[insights.Insight]) -> set[str]:
    return {insight.id for insight in found}


class InsightTests(unittest.TestCase):
    def test_empty_month(self) -> None:
        self.assertEqual(ids(insights.generate([], {}, "2026-11", TODAY)), {"empty"})

    def test_healthy_month_only_suggests_biggest_want(self) -> None:
        found = insights.generate(salary_month("2026-11"), {}, "2026-11", TODAY)
        self.assertEqual(ids(found), {"cut_an_choi"})
        self.assertEqual(found[0].annual_impact, 400_000 * 12)

    def test_low_savings_rate_reports_gap(self) -> None:
        found = insights.generate(salary_month("2026-11", saved=2_000_000), {}, "2026-11", TODAY)
        gap = next(item for item in found if item.id == "savings_rate_gap")
        self.assertEqual(gap.severity, "warning")
        self.assertEqual(gap.annual_impact, 2_000_000 * 12)  # target 4M, saved 2M

    def test_wants_over_thirty_percent(self) -> None:
        found = insights.generate(salary_month("2026-11", an_choi=7_000_000), {}, "2026-11", TODAY)
        wants = next(item for item in found if item.id == "wants_share")
        self.assertEqual(wants.annual_impact, 1_000_000 * 12)

    def test_negative_balance_is_critical_and_first(self) -> None:
        rows = salary_month("2026-10", an_choi=12_000_000)
        found = insights.generate(rows, {}, "2026-10", TODAY)
        self.assertEqual(found[0].id, "negative_balance")
        self.assertEqual(found[0].severity, "critical")

    def test_no_negative_alert_before_salary_arrives(self) -> None:
        rows = [tx("2026-11-01", "sinh_hoat_phi", 6_000_000)]
        found = insights.generate(rows, {}, "2026-11", dt.date(2026, 11, 2))
        self.assertNotIn("negative_balance", ids(found))
        self.assertIn("no_income", ids(found))

    def test_anomaly_against_previous_months(self) -> None:
        rows = (
            salary_month("2026-08")
            + salary_month("2026-09")
            + salary_month("2026-10")
            + salary_month("2026-11", an_choi=3_000_000)
        )
        found = insights.generate(rows, {}, "2026-11", TODAY)
        anomaly = next(item for item in found if item.id == "anomaly_an_choi")
        self.assertEqual(anomaly.annual_impact, 1_000_000 * 12)

    def test_small_increase_is_not_an_anomaly(self) -> None:
        rows = salary_month("2026-10", an_choi=200_000) + salary_month("2026-11", an_choi=350_000)
        self.assertNotIn("anomaly_an_choi", ids(insights.generate(rows, {}, "2026-11", TODAY)))

    def test_budget_over_and_chi_ho(self) -> None:
        rows = salary_month("2026-11") + [tx("2026-11-07", "chi_ho", 500_000)]
        found = insights.generate(rows, {"an_choi": 1_500_000}, "2026-11", TODAY)
        self.assertIn("budget_over_an_choi", ids(found))
        self.assertIn("chi_ho_outstanding", ids(found))
        self.assertEqual(found[0].severity, "critical")

    def test_vnd_format(self) -> None:
        self.assertEqual(insights.vnd(1_234_000), "1.234.000 ₫")


if __name__ == "__main__":
    unittest.main()
