# 05 · Testing

```powershell
python -m unittest discover -s tests -t .
python -m ruff check app tests
```

51 tests, all deterministic: analytics receive a fixed `today`, and API tests override the
`get_today` dependency and point `SAVINGS_DB` at a temp file.

| Suite                 | What it proves                                                                  | Spec       |
|-----------------------|---------------------------------------------------------------------------------|------------|
| `test_database.py`    | CRUD, idempotent insert, budget carry-forward, zero budget removal              | FR-1, FR-4 |
| `test_analytics.py`   | Month math across years, summary/balance/ratios, sheet layout, budget pace, trend gaps, projection skips the partial month, what-if window and fallback | FR-2–FR-8 |
| `test_insights.py`    | Every rule fires on its trigger and stays silent otherwise; severity ordering; no false "negative balance" before payday | FR-9 |
| `test_importer.py`    | VN amount formats, template parsing (title/All/Total rows, group-row labels), stable ids, unknown columns, export→import round trip, content dedupe; Excel: multi-sheet workbook with date/number/text/formula cells, non-template sheets ignored, CSV↔Excel equivalence, corrupt and legacy `.xls` files | FR-10 |
| `test_api.py`         | Every endpoint, validation errors (422), 404s, import idempotency, Basic auth   | all, NFR-4 |

## Manual checks done for v0.1.0

- Seeded 6 demo months, opened the UI at 1280 px and 390 px: KPI tiles, insights, projection,
  what-if sliders, trend chart with tooltip, sheet with Total/All rows and budgets render
  without horizontal page scroll (only the sheet table scrolls).
- Export → re-import of a month reports `0 imported, N duplicates`.

## Regressions found and fixed during testing

| Found                                                                                     | Fix |
|-------------------------------------------------------------------------------------------|-----|
| Re-importing an export of hand-entered rows doubled them (random ids ≠ content-hash ids)   | Content-based `without_duplicates` before insert |
| Template's `Chi hộ` / `Tiết kiệm` columns are unlabeled on the `Ngày` row → silently dropped | Header fallback to the group row above |
| "Chi vượt thu" raised as critical on the 2nd of the month, before salary arrives          | Only when income exists or the month is closed |
| Form date used UTC → wrong day before 07:00 in Vietnam                                    | Local-date helper in the frontend |
