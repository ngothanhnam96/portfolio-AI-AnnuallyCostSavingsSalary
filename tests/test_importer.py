from __future__ import annotations

import unittest

from app.importer import (
    export_template_csv,
    parse_amount,
    parse_template_csv,
    parse_template_file,
    without_duplicates,
)
from tests.helpers import tx
from tests.xlsx_fixtures import template_workbook, workbook_without_template

# Shaped like a CSV download of the Google Sheet template, including title/All/Total rows.
TEMPLATE_CSV = """﻿2026,,Chi,,,,,,Chi hộ,Tiết kiệm,Thu,,
All,,"6.700.000",,,,,,0,,0,0,0
Ngày,Tên chi phí,Sinh hoạt phí,Xăng,Ăn chơi,Mua sắm,Đám đình,Yêu Minh Anh,,,Được cho,Lương,
Total,,"5.700.000",0,0,0,0,0,0,,0,
01/11/2026,,,,,,,,,,,,
01/11/2026,Tiền nhà,"5.000.000",,,,,,,,,,
02/11/2026,Đổ xăng,,80k,,,,,,,,,
02/11/2026,Đổ xăng,,80k,,,,,,,,,
05/11/2026,Lương tháng 10,,,,,,,,,,"25,000,000",
06/11/2026,Áo khoác,,,,1.2tr,,,,,,,
07/11/2026,Sai số,,,abc,,,,,,,,
08/11/2026,Gửi tiết kiệm,,,,,,,,"3.000.000",,,
09/11/2026,Mua hộ mẹ,,,,,,,200k,,,,
"""


class ParseAmountTests(unittest.TestCase):
    def test_formats(self) -> None:
        cases = {
            "1.234.000": 1_234_000,
            "1,234,000": 1_234_000,
            "250000": 250_000,
            "80k": 80_000,
            "1.5tr": 1_500_000,
            "1,5tr": 1_500_000,
            "2tr": 2_000_000,
            "500.000 đ": 500_000,
            "500000 VND": 500_000,
            "300.000₫": 300_000,
            "": None,
            "0": None,
        }
        for raw, expected in cases.items():
            with self.subTest(raw=raw):
                self.assertEqual(parse_amount(raw), expected)

    def test_invalid(self) -> None:
        with self.assertRaises(ValueError):
            parse_amount("abc")


class TemplateImportTests(unittest.TestCase):
    def test_parses_template_rows(self) -> None:
        result = parse_template_csv(TEMPLATE_CSV)
        rows = [(t.date, t.name, t.category, t.amount) for t in result.transactions]
        self.assertEqual(
            rows,
            [
                ("2026-11-01", "Tiền nhà", "sinh_hoat_phi", 5_000_000),
                ("2026-11-02", "Đổ xăng", "xang", 80_000),
                ("2026-11-02", "Đổ xăng", "xang", 80_000),
                ("2026-11-05", "Lương tháng 10", "luong", 25_000_000),
                ("2026-11-06", "Áo khoác", "mua_sam", 1_200_000),
                # Columns labelled only in the group row above 'Ngày'.
                ("2026-11-08", "Gửi tiết kiệm", "tiet_kiem", 3_000_000),
                ("2026-11-09", "Mua hộ mẹ", "chi_ho", 200_000),
            ],
        )
        self.assertEqual(result.unknown_columns, [])
        self.assertEqual([row["line"] for row in result.skipped], [11])

    def test_identical_rows_get_distinct_stable_ids(self) -> None:
        first = parse_template_csv(TEMPLATE_CSV).transactions
        second = parse_template_csv(TEMPLATE_CSV).transactions
        self.assertNotEqual(first[1].id, first[2].id)
        self.assertEqual([t.id for t in first], [t.id for t in second])

    def test_header_matching_ignores_accents_case_and_order(self) -> None:
        text = "ngay;LUONG;ten chi phi;xang\n03/11/2026;20.000.000;Lương;\n"
        result = parse_template_csv(text)
        self.assertEqual(result.transactions[0].category, "luong")
        self.assertEqual(result.transactions[0].name, "Lương")

    def test_unknown_columns_are_reported(self) -> None:
        result = parse_template_csv("Ngày,Tên chi phí,Du lịch\n01/11/2026,Đà Lạt,3tr\n")
        self.assertEqual(result.unknown_columns, ["Du lịch"])
        self.assertEqual(result.transactions, [])

    def test_missing_header_raises(self) -> None:
        with self.assertRaises(ValueError):
            parse_template_csv("a,b,c\n1,2,3\n")

    def test_export_then_import_round_trip(self) -> None:
        rows = [
            tx("2026-11-02", "xang", 80_000, "Đổ xăng"),
            tx("2026-11-05", "luong", 25_000_000, "Lương, tháng 10"),
        ]
        exported = export_template_csv(rows)
        self.assertIn("Total", exported.splitlines()[-1])
        reimported = parse_template_csv(exported).transactions
        self.assertEqual(
            [(t.date, t.name, t.category, t.amount) for t in reimported],
            [(t.date, t.name, t.category, t.amount) for t in rows],
        )

    def test_without_duplicates_respects_counts(self) -> None:
        existing = [tx("2026-11-02", "xang", 80_000, "Đổ xăng")]
        incoming = parse_template_csv(TEMPLATE_CSV).transactions
        fresh = without_duplicates(incoming, existing)
        # One of the two identical fuel rows already exists; the other is new.
        self.assertEqual(len(fresh), len(incoming) - 1)
        self.assertEqual(without_duplicates(incoming, incoming), [])


class ExcelImportTests(unittest.TestCase):
    def test_parses_every_template_sheet(self) -> None:
        result = parse_template_file(template_workbook())
        rows = [(t.date, t.name, t.category, t.amount) for t in result.transactions]
        self.assertEqual(
            rows,
            [
                ("2026-11-01", "Tiền nhà", "sinh_hoat_phi", 5_000_000),
                ("2026-11-02", "Đổ xăng", "xang", 80_000),
                ("2026-11-05", "Lương", "luong", 25_000_000),
                ("2026-11-06", "Gửi tiết kiệm", "tiet_kiem", 3_000_000),
                ("2026-11-09", "Mua hộ mẹ", "chi_ho", 200_000),
                ("2026-12-02", "Đổ xăng", "xang", 80_000),
                ("2026-12-02", "Đổ xăng", "xang", 80_000),
            ],
        )
        # The 'Ghi chú' sheet has no template header and is ignored, not reported.
        self.assertEqual(result.unknown_columns, [])
        self.assertEqual(
            result.skipped,
            [{"sheet": "T11_2026", "line": 11, "reason": "invalid amount 'abc'"}],
        )

    def test_ids_are_stable_and_distinct_across_sheets(self) -> None:
        first = parse_template_file(template_workbook()).transactions
        second = parse_template_file(template_workbook()).transactions
        self.assertEqual([t.id for t in first], [t.id for t in second])
        self.assertEqual(len({t.id for t in first}), len(first))

    def test_csv_and_excel_produce_the_same_ids(self) -> None:
        from_excel = parse_template_file(template_workbook()).transactions
        exported = export_template_csv(from_excel)
        from_csv = parse_template_file(exported.encode("utf-8")).transactions
        self.assertEqual(
            sorted((t.date, t.name, t.amount) for t in from_csv),
            sorted((t.date, t.name, t.amount) for t in from_excel),
        )
        self.assertEqual(without_duplicates(from_csv, from_excel), [])

    def test_workbook_without_template_sheet(self) -> None:
        with self.assertRaisesRegex(ValueError, "no sheet"):
            parse_template_file(workbook_without_template())

    def test_corrupt_and_legacy_files(self) -> None:
        with self.assertRaisesRegex(ValueError, "cannot read Excel"):
            parse_template_file(b"PK\x03\x04 not really a zip")
        with self.assertRaisesRegex(ValueError, r"\.xls"):
            parse_template_file(b"\xd0\xcf\x11\xe0" + b"\x00" * 64)


if __name__ == "__main__":
    unittest.main()
