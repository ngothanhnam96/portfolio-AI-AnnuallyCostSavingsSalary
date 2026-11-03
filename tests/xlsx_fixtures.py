"""Build .xlsx workbooks in memory, shaped like the real spending template."""

from __future__ import annotations

import datetime as dt
import io

from openpyxl import Workbook

GROUP_ROW = [2026, None, "Chi", None, None, None, None, None, "Chi hộ", "Tiết kiệm", "Thu", None]
HEADER_ROW = [
    "Ngày",
    "Tên chi phí",
    "Sinh hoạt phí",
    "Xăng",
    "Ăn chơi",
    "Mua sắm",
    "Đám đình",
    "Yêu Minh Anh",
    None,
    None,
    "Được cho",
    "Lương",
]


def entry(day: dt.date, name: str, column: int, amount: float | int | str) -> list[object]:
    row: list[object] = [day, name] + [None] * (len(HEADER_ROW) - 2)
    row[column] = amount
    return row


def template_workbook() -> bytes:
    workbook = Workbook()

    november = workbook.active
    november.title = "T11_2026"
    november.append(GROUP_ROW)
    november.append(["All", None, "=SUM(C4:H4)"])
    november.append(HEADER_ROW)
    november.append(["Total", None, "=SUM(C5:C100)", "=SUM(D5:D100)"])
    november.append([dt.datetime(2026, 11, 1)])  # date-only placeholder row
    november.append(entry(dt.datetime(2026, 11, 1), "Tiền nhà", 2, 5_000_000))
    november.append(entry(dt.datetime(2026, 11, 2), "Đổ xăng", 3, 80_000.0))  # float cell
    november.append(entry(dt.datetime(2026, 11, 5), "Lương", 11, 25_000_000))
    november.append(entry(dt.datetime(2026, 11, 6), "Gửi tiết kiệm", 9, 3_000_000))
    november.append(entry(dt.datetime(2026, 11, 9), "Mua hộ mẹ", 8, "200k"))  # typed as text
    november.append(entry(dt.datetime(2026, 11, 10), "Sai số", 4, "abc"))

    notes = workbook.create_sheet("Ghi chú")
    notes.append(["Mục tiêu năm", "Tiết kiệm 60tr"])

    december = workbook.create_sheet("T12_2026")
    december.append(HEADER_ROW)
    december.append(entry(dt.date(2026, 12, 2), "Đổ xăng", 3, 80_000))
    december.append(entry(dt.date(2026, 12, 2), "Đổ xăng", 3, 80_000))

    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def workbook_without_template() -> bytes:
    workbook = Workbook()
    workbook.active.append(["Hello", "world"])
    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()
