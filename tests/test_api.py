from __future__ import annotations

import base64
import datetime as dt
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from fastapi.testclient import TestClient

from app.main import app, get_today
from tests.xlsx_fixtures import template_workbook

TODAY = dt.date(2026, 11, 20)
XLSX_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


class ApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        db_path = str(Path(self.temp_dir.name) / "api.db")
        self.env = mock.patch.dict(os.environ, {"SAVINGS_DB": db_path, "SAVINGS_PASSWORD": ""})
        self.env.start()
        app.dependency_overrides[get_today] = lambda: TODAY
        self.client = TestClient(app)

    def tearDown(self) -> None:
        app.dependency_overrides.clear()
        self.env.stop()
        self.temp_dir.cleanup()

    def add(self, date: str, category: str, amount: int, name: str = "x") -> dict:
        response = self.client.post(
            "/api/transactions",
            json={"date": date, "name": name, "category": category, "amount": amount},
        )
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()

    def test_index_and_health(self) -> None:
        self.assertEqual(self.client.get("/api/health").json(), {"status": "ok"})
        self.assertIn("Tiết kiệm lương", self.client.get("/").text)

    def test_categories_follow_template(self) -> None:
        body = self.client.get("/api/categories").json()
        self.assertEqual(
            [group["label"] for group in body["groups"]], ["Chi", "Chi hộ", "Tiết kiệm", "Thu"]
        )
        self.assertEqual(len(body["categories"]), 10)

    def test_transaction_crud(self) -> None:
        created = self.add("2026-11-02", "xang", 80_000, "Đổ xăng")
        listed = self.client.get("/api/transactions", params={"month": "2026-11"}).json()
        self.assertEqual([row["id"] for row in listed], [created["id"]])

        update = {**created, "amount": 90_000}
        del update["id"]
        response = self.client.put(f"/api/transactions/{created['id']}", json=update)
        self.assertEqual(response.json()["amount"], 90_000)

        self.assertEqual(self.client.delete(f"/api/transactions/{created['id']}").status_code, 204)
        self.assertEqual(self.client.delete(f"/api/transactions/{created['id']}").status_code, 404)

    def test_validation(self) -> None:
        bad = [
            {"date": "2026-11-02", "name": "x", "category": "unknown", "amount": 1},
            {"date": "2026-11-02", "name": "x", "category": "xang", "amount": 0},
            {"date": "2026-11-02", "name": "", "category": "xang", "amount": 1},
        ]
        for payload in bad:
            with self.subTest(payload=payload):
                self.assertEqual(
                    self.client.post("/api/transactions", json=payload).status_code, 422
                )
        self.assertEqual(self.client.get("/api/months/2026-13/summary").status_code, 422)
        self.assertEqual(self.client.get("/api/transactions?month=nov").status_code, 422)

    def test_monthly_views(self) -> None:
        self.add("2026-11-05", "luong", 20_000_000)
        self.add("2026-11-06", "tiet_kiem", 5_000_000)
        self.add("2026-11-07", "an_choi", 2_000_000)

        summary = self.client.get("/api/months/2026-11/summary").json()
        self.assertEqual(summary["balance"], 13_000_000)
        self.assertEqual(summary["savings_rate"], 0.25)

        sheet = self.client.get("/api/months/2026-11/sheet").json()
        self.assertEqual(len(sheet["rows"]), 3)

        insights = self.client.get("/api/months/2026-11/insights").json()
        self.assertTrue(any(item["id"] == "cut_an_choi" for item in insights))

        trend = self.client.get("/api/trend", params={"months": 2}).json()
        self.assertEqual([row["month"] for row in trend], ["2026-10", "2026-11"])

        projection = self.client.get("/api/projection").json()
        self.assertEqual(projection["year"], 2026)

    def test_budgets(self) -> None:
        self.add("2026-11-07", "an_choi", 2_000_000)
        response = self.client.put(
            "/api/months/2026-11/budgets/an_choi", json={"amount": 1_500_000}
        )
        self.assertEqual(response.status_code, 200)
        rows = self.client.get("/api/months/2026-11/budgets").json()
        an_choi = next(row for row in rows if row["category"] == "an_choi")
        self.assertEqual(an_choi["status"], "over")
        # Carried forward into the next month.
        rows = self.client.get("/api/months/2026-12/budgets").json()
        self.assertEqual(next(r for r in rows if r["category"] == "an_choi")["budget"], 1_500_000)
        # Income categories cannot have a budget.
        bad = self.client.put("/api/months/2026-11/budgets/luong", json={"amount": 1})
        self.assertEqual(bad.status_code, 422)

    def test_what_if(self) -> None:
        self.add("2026-10-07", "an_choi", 2_000_000)
        result = self.client.post("/api/what-if", json={"cuts": {"an_choi": 0.5}}).json()
        self.assertEqual(result["annual_gain"], 12_000_000)
        bad = self.client.post("/api/what-if", json={"cuts": {"luong": 0.5}})
        self.assertEqual(bad.status_code, 422)

    def test_import_export_is_idempotent(self) -> None:
        self.add("2026-11-02", "xang", 80_000, "Đổ xăng")
        csv_text = self.client.get("/api/months/2026-11/export.csv").text
        self.assertIn("Đổ xăng", csv_text)

        result = self.client.post("/api/import", content=csv_text.encode("utf-8")).json()
        self.assertEqual((result["imported"], result["duplicates"]), (0, 1))

        extra = csv_text.replace("Total", "03/11/2026,Cà phê,,,45k,,,,,,,\nTotal")
        result = self.client.post("/api/import", content=extra.encode("utf-8")).json()
        self.assertEqual(result["imported"], 1)
        self.assertEqual(len(self.client.get("/api/transactions").json()), 2)

    def test_import_rejects_bad_files(self) -> None:
        response = self.client.post("/api/import", content=b"no,header\n1,2\n")
        self.assertEqual(response.status_code, 422)
        legacy = self.client.post("/api/import", content=b"\xd0\xcf\x11\xe0" + b"\x00" * 64)
        self.assertEqual(legacy.status_code, 422)
        self.assertIn(".xlsx", legacy.json()["detail"])

    def test_import_excel_workbook(self) -> None:
        xlsx = template_workbook()
        headers = {"Content-Type": XLSX_TYPE}
        result = self.client.post("/api/import", content=xlsx, headers=headers).json()
        self.assertEqual(result["imported"], 7)
        self.assertEqual(result["skipped"][0]["sheet"], "T11_2026")

        again = self.client.post("/api/import", content=xlsx, headers=headers).json()
        self.assertEqual((again["imported"], again["duplicates"]), (0, 7))

        summary = self.client.get("/api/months/2026-11/summary").json()
        self.assertEqual(summary["groups"]["thu"], 25_000_000)
        self.assertEqual(summary["groups"]["tiet_kiem"], 3_000_000)
        self.assertEqual(summary["groups"]["chi_ho"], 200_000)

    def test_basic_auth_when_password_set(self) -> None:
        with mock.patch.dict(os.environ, {"SAVINGS_PASSWORD": "s3cret"}):
            self.assertEqual(self.client.get("/api/health").status_code, 200)
            self.assertEqual(self.client.get("/api/categories").status_code, 401)
            token = base64.b64encode(b"admin:s3cret").decode()
            ok = self.client.get("/api/categories", headers={"Authorization": f"Basic {token}"})
            self.assertEqual(ok.status_code, 200)
            wrong = base64.b64encode(b"admin:nope").decode()
            denied = self.client.get("/api/categories", headers={"Authorization": f"Basic {wrong}"})
            self.assertEqual(denied.status_code, 401)


if __name__ == "__main__":
    unittest.main()
