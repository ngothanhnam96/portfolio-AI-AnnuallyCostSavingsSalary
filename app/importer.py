"""Import/export in the layout of the monthly spending template (CSV or Excel .xlsx).

Template rows look like `Ngày | Tên chi phí | Sinh hoạt phí | Xăng | ... | Lương`, with one
amount per row. Title, `All` and `Total` rows are skipped. Import is idempotent: ids are
derived from the row content, so re-importing the same file never duplicates entries.

Each file format is only a reader that turns the file into rows of strings; the template
rules live once in `parse_template_rows`.
"""

from __future__ import annotations

import csv
import datetime as dt
import hashlib
import io
import re
import unicodedata
from collections import Counter
from dataclasses import dataclass, field

from openpyxl import load_workbook

from app.categories import CATEGORIES
from app.models import Transaction

XLSX_MAGIC = b"PK\x03\x04"
XLS_MAGIC = b"\xd0\xcf\x11\xe0"

DATE_HEADER = "ngay"
NAME_HEADER = "ten chi phi"
SKIP_MARKERS = {"", "total", "all", "tong", "tong cong"}
DATE_FORMATS = ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y", "%d.%m.%Y")
AMOUNT_PATTERN = re.compile(r"^(\d+(?:[.,]\d+)*)(k|tr|m)?$")
CURRENCY_SUFFIX = re.compile(r"(vnd|d|₫)$")
MULTIPLIERS = {"k": 1_000, "tr": 1_000_000, "m": 1_000_000}


@dataclass
class ImportResult:
    transactions: list[Transaction] = field(default_factory=list)
    skipped: list[dict[str, object]] = field(default_factory=list)
    unknown_columns: list[str] = field(default_factory=list)


def normalize(text: str) -> str:
    """Lower-case, accent-free, single-spaced: 'Sinh hoạt phí ' -> 'sinh hoat phi'."""
    text = text.replace("đ", "d").replace("Đ", "D")
    text = unicodedata.normalize("NFD", text)
    text = "".join(char for char in text if unicodedata.category(char) != "Mn")
    return " ".join(text.lower().split())


def parse_amount(raw: str) -> int | None:
    """Parse VND amounts such as '1.234.000', '1,234,000', '150k', '1.5tr'. Empty -> None."""
    text = CURRENCY_SUFFIX.sub("", normalize(raw).replace(" ", ""))
    if not text or text in {"0", "-"}:
        return None
    match = AMOUNT_PATTERN.match(text)
    if not match:
        raise ValueError(f"invalid amount '{raw}'")
    number, suffix = match.groups()
    if suffix:
        value = float(number.replace(",", "."))
        return round(value * MULTIPLIERS[suffix])
    return int(number.replace(".", "").replace(",", "")) or None


def parse_date(raw: str) -> dt.date | None:
    text = raw.strip()
    for date_format in DATE_FORMATS:
        try:
            return dt.datetime.strptime(text, date_format).date()
        except ValueError:
            continue
    return None


def _read_rows(text: str) -> list[list[str]]:
    text = text.lstrip("﻿")
    try:
        dialect = csv.Sniffer().sniff(text[:4096], delimiters=",;\t")
    except csv.Error:
        dialect = csv.excel
    return list(csv.reader(io.StringIO(text), dialect))


def _cell_text(value: object) -> str:
    """Excel cell -> the string the CSV path would have seen."""
    if value is None:
        return ""
    if isinstance(value, (dt.datetime, dt.date)):
        return value.strftime("%d/%m/%Y")
    if isinstance(value, float):
        return str(round(value))
    return str(value)


def _read_xlsx_sheets(data: bytes) -> list[tuple[str, list[list[str]]]]:
    workbook = load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    try:
        return [
            (
                sheet.title,
                [[_cell_text(value) for value in row] for row in sheet.iter_rows(values_only=True)],
            )
            for sheet in workbook.worksheets
        ]
    finally:
        workbook.close()


def _transaction_id(date: str, name: str, category: str, amount: int, occurrence: int) -> str:
    key = f"{date}|{name}|{category}|{amount}|{occurrence}"
    return "imp_" + hashlib.sha1(key.encode("utf-8")).hexdigest()[:16]


def _header_index(rows: list[list[str]]) -> int | None:
    return next(
        (index for index, row in enumerate(rows) if row and normalize(row[0]) == DATE_HEADER),
        None,
    )


def parse_template_csv(text: str) -> ImportResult:
    rows = _read_rows(text)
    if _header_index(rows) is None:
        raise ValueError("header row starting with 'Ngày' not found")
    result = ImportResult()
    parse_template_rows(rows, result, Counter())
    return result


def parse_template_xlsx(data: bytes) -> ImportResult:
    """Every sheet with a 'Ngày' header row is imported; other sheets are ignored."""
    try:
        sheets = _read_xlsx_sheets(data)
    except Exception as error:  # openpyxl raises a variety of zip/xml errors
        raise ValueError(f"cannot read Excel file: {error}") from error
    result = ImportResult()
    seen: Counter[tuple[str, str, str, int]] = Counter()
    matched = 0
    for title, rows in sheets:
        if _header_index(rows) is not None:
            matched += 1
            parse_template_rows(rows, result, seen, sheet=title)
    if not matched:
        raise ValueError("no sheet has a header row starting with 'Ngày'")
    return result


def parse_template_file(data: bytes) -> ImportResult:
    """Detect the format from the file's bytes, not its name or content type."""
    if data.startswith(XLSX_MAGIC):
        return parse_template_xlsx(data)
    if data.startswith(XLS_MAGIC):
        raise ValueError("old .xls (Excel 97-2003) is not supported, save it as .xlsx")
    return parse_template_csv(data.decode("utf-8-sig"))


def parse_template_rows(
    rows: list[list[str]],
    result: ImportResult,
    seen: Counter[tuple[str, str, str, int]],
    sheet: str | None = None,
) -> None:
    """Apply the template rules to rows of strings, appending to `result`.

    `seen` counts identical rows across everything parsed into the same result, so
    duplicates in different sheets still get distinct, stable ids.
    """
    header_index = _header_index(rows)
    if header_index is None:
        return
    where = {"sheet": sheet} if sheet else {}
    labels = {normalize(category.label): category.id for category in CATEGORIES}
    labels.update({category.id: category.id for category in CATEGORIES})
    columns: dict[int, str] = {}
    name_column = None
    for index, cell in enumerate(rows[header_index]):
        key = normalize(cell)
        if not key:
            # In the template, 'Chi hộ' and 'Tiết kiệm' are labelled only in the group row
            # above the 'Ngày' row, so fall back to the nearest label above in that column.
            key = next(
                (
                    normalize(row[index])
                    for row in reversed(rows[:header_index])
                    if index < len(row) and normalize(row[index]) in labels
                ),
                "",
            )
        if index == 0 or not key:
            continue
        if key == NAME_HEADER:
            name_column = index
        elif key in labels:
            columns[index] = labels[key]
        elif cell.strip() not in result.unknown_columns:
            result.unknown_columns.append(cell.strip())

    for line, row in enumerate(rows[header_index + 1 :], start=header_index + 2):
        if not row or normalize(row[0]) in SKIP_MARKERS:
            continue
        name = (
            row[name_column].strip() if name_column is not None and name_column < len(row) else ""
        )
        try:
            amounts = [
                (category_id, parse_amount(row[index]))
                for index, category_id in columns.items()
                if index < len(row)
            ]
        except ValueError as error:
            result.skipped.append({**where, "line": line, "reason": str(error)})
            continue
        amounts = [(category_id, amount) for category_id, amount in amounts if amount]
        if not amounts:
            continue  # date-only placeholder rows, as in the template
        day = parse_date(row[0])
        if day is None:
            result.skipped.append({**where, "line": line, "reason": f"invalid date '{row[0]}'"})
            continue
        for category_id, amount in amounts:
            key = (day.isoformat(), name, category_id, amount)
            seen[key] += 1
            result.transactions.append(
                Transaction(
                    id=_transaction_id(*key, seen[key]),
                    date=day.isoformat(),
                    name=name or category_id,
                    category=category_id,
                    amount=amount,
                )
            )


def without_duplicates(
    incoming: list[Transaction], existing: list[Transaction]
) -> list[Transaction]:
    """Drop incoming rows whose content already exists, respecting repeat counts.

    Covers rows that were entered by hand (random ids) and later come back via an export.
    """

    def content(transaction: Transaction) -> tuple[str, str, str, int]:
        return (transaction.date, transaction.name, transaction.category, transaction.amount)

    stored = Counter(content(transaction) for transaction in existing)
    seen: Counter[tuple[str, str, str, int]] = Counter()
    fresh = []
    for transaction in incoming:
        key = content(transaction)
        seen[key] += 1
        if seen[key] > stored[key]:
            fresh.append(transaction)
    return fresh


def export_template_csv(transactions: list[Transaction]) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(["Ngày", "Tên chi phí", *[category.label for category in CATEGORIES]])
    totals = {category.id: 0 for category in CATEGORIES}
    for transaction in sorted(transactions, key=lambda item: item.date):
        cells = ["" for _ in CATEGORIES]
        index = next(i for i, c in enumerate(CATEGORIES) if c.id == transaction.category)
        cells[index] = str(transaction.amount)
        totals[transaction.category] += transaction.amount
        day = dt.date.fromisoformat(transaction.date)
        writer.writerow([day.strftime("%d/%m/%Y"), transaction.name, *cells])
    writer.writerow(["Total", "", *[str(totals[category.id]) for category in CATEGORIES]])
    return buffer.getvalue()
