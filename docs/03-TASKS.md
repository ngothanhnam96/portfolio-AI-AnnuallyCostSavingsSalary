# 03 · Tasks

Status: ✅ done in v0.1.0 · ⏭ backlog

| ID   | Milestone | Task                                                                   | Covers        | Status |
|------|-----------|------------------------------------------------------------------------|---------------|--------|
| T-01 | M1        | Category catalog from the template (`app/categories.py`)               | FR-1, FR-2    | ✅ |
| T-02 | M1        | `Transaction` / `Budget` models + Pydantic input schemas               | FR-1, NFR-2   | ✅ |
| T-03 | M1        | SQLite `FinanceStore`: transactions CRUD, budgets with carry-forward   | FR-1, FR-4    | ✅ |
| T-04 | M2        | `month_sheet` in template layout (Total + All rows)                    | FR-2          | ✅ |
| T-05 | M2        | `month_summary` (groups, categories, balance, ratios)                  | FR-3          | ✅ |
| T-06 | M2        | `budget_status` with pace for the current month                        | FR-5          | ✅ |
| T-07 | M2        | `trend` over N months                                                  | FR-6          | ✅ |
| T-08 | M2        | `annual_projection`                                                    | FR-7          | ✅ |
| T-09 | M2        | `what_if`                                                              | FR-8          | ✅ |
| T-10 | M2        | Insight rules engine                                                   | FR-9          | ✅ |
| T-11 | M3        | Template CSV import (header detection, VN number formats, idempotent)  | FR-10         | ✅ |
| T-12 | M3        | Template CSV export                                                    | FR-10         | ✅ |
| T-21 | M3        | Excel .xlsx import (multi-sheet, format detected from file bytes)      | FR-10         | ✅ |
| T-13 | M3        | Demo seed generator                                                    | FR-11         | ✅ |
| T-14 | M4        | REST API + optional Basic auth                                         | all, NFR-4    | ✅ |
| T-15 | M5        | Frontend: dashboard, sheet, form, budgets, chart, what-if, import      | NFR-6         | ✅ |
| T-16 | M6        | Dockerfile, compose, CI workflow, deploy guide                         | NFR-1, NFR-7  | ✅ |
| T-17 | —         | LLM narrator for insights (Claude API) behind the `InsightRule` output | —             | ⏭ |
| T-18 | —         | Google Sheets API pull instead of manual CSV export                    | —             | ⏭ |
| T-19 | —         | Recurring transactions (salary, rent) auto-filled each month           | —             | ⏭ |
| T-20 | —         | Settle "chi hộ" (mark reimbursed, link to repayment)                   | —             | ⏭ |
