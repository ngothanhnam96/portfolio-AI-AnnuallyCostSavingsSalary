# 04 · Analysis

Design decisions, the formulas behind each number, and the risks considered before coding.

## Data model

```text
transactions(id TEXT PK, date TEXT ISO, name TEXT, category TEXT, amount INTEGER, note TEXT)
budgets(month TEXT 'YYYY-MM', category TEXT, amount INTEGER, PK(month, category))
```

- **One row per amount cell.** A template row such as `05/11 | Đổ xăng | Xăng = 80.000` becomes
  one transaction. This keeps every aggregate a plain `SUM … GROUP BY category`.
- **Category, not group, is stored.** Group membership comes from `app/categories.py`, so
  renaming a column in the template is a one-line change.
- **Integer VND** — no rounding drift; percentages are computed only at the edge.

## Formulas

| Metric                | Formula                                                                                  |
|-----------------------|------------------------------------------------------------------------------------------|
| Balance               | `thu − chi − chi_ho − tiet_kiem`                                                         |
| Savings rate          | `tiet_kiem / thu`                                                                        |
| Budget pace           | Current month: `day / days_in_month`; past month: `1.0`                                   |
| Budget status         | `over` if spent > budget; `at_risk` if spent/budget > pace + 10 pp; else `ok`           |
| Projection            | `Σ complete tracked months + avg(those months) × every other month of the year` — the partial current month and untracked months are filled with the average |
| What-if               | `avg monthly spend (last 3 months with data) × cut %`, × 12 for annual                   |

## Insight rules (the "AI advisor")

Deterministic rules, each returning `Insight(severity, title, detail, annual_impact_vnd)`.
Rules are explainable and testable; an LLM can later turn the same structured list into prose
(T-17) without being trusted with the numbers.

| Rule                 | Trigger                                                     | Impact estimate                          |
|----------------------|-------------------------------------------------------------|------------------------------------------|
| Negative balance     | balance < 0                                                 | —                                        |
| Savings-rate gap     | savings rate < 20 %                                         | `(20 % × thu − tiet_kiem) × 12`          |
| Needs > 50 %         | needs / thu > 50 %                                          | —                                        |
| Wants > 30 %         | wants / thu > 30 %                                          | `(wants − 30 % × thu) × 12`              |
| Anomaly              | category ≥ 1.3 × its 3-month average and ≥ 200 000 VND above | `(spent − avg) × 12`                     |
| Budget over / at risk| from budget status                                          | `(spent − budget) × 12` when over        |
| Outstanding chi hộ   | chi_ho > 0                                                  | —                                        |
| Biggest want         | largest Wants category > 0                                  | `20 % × spent × 12` (the cut suggestion) |

## Import (Excel .xlsx and CSV)

- Each format is only a *reader* that turns the file into rows of strings; the template rules
  below run once on those rows, so CSV and Excel behave identically and produce the same ids.
- Format is detected from the file's first bytes (`PK` = .xlsx), not its name.
  Legacy `.xls` is rejected with a "save as .xlsx" message.
- Workbooks: every sheet with a `Ngày` header row is imported (e.g. one sheet per month);
  other sheets are ignored. Skipped rows are reported as `sheet!line`.
- Excel cells keep their types: date cells, numeric cells and text such as `80k` all work.
  Formulas are read from their cached values (`data_only=True`).

- Header row is found by its first cell `Ngày`; title, `All` and `Total` rows are skipped.
- In the real template the `Chi hộ` and `Tiết kiệm` columns are blank on the `Ngày` row and
  labelled only on the group row above it, so blank header cells fall back to the nearest
  matching label above in the same column.
- Columns are matched by label, accent- and case-insensitively, so column order may change.
- Amounts accept `1.234.000`, `1,234,000`, `1234000`, `150k`, `1.5tr`.
- Dates accept `dd/mm/yyyy`, `d/m/yyyy` and ISO.
- **Idempotency:** each transaction id is the hash of `(date, name, category, amount, n)`, where
  `n` counts identical rows in the file. On top of that, incoming rows are compared by content
  with what is already stored (respecting repeat counts), so exporting hand-entered rows and
  importing them back never duplicates either.

## Risks

| Risk                                          | Mitigation                                              |
|-----------------------------------------------|---------------------------------------------------------|
| Personal finance data exposed on a network    | Binds to localhost by default; Basic auth via env var   |
| Partner's name in a category label is public in this repo | Labels live in one catalog; rename before publishing   |
| Template changes column names                 | Label-based matching; unknown columns reported, not lost silently |
| Demo data mixed into real data                | Seeding is an explicit command, never automatic         |
