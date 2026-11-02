# 01 · Specification

## Problem

Salaried people track spending in a monthly spreadsheet (see template below) but the sheet
only *records* money. It does not answer the questions that actually change behaviour:

- How much of my salary am I really keeping each month (savings rate)?
- Which category is drifting compared to my normal months?
- If I keep this pace, how much will I have saved by year end?
- If I cut category X by Y %, what is that worth per year?

## Goal

A self-hosted web app that keeps the familiar monthly-sheet workflow and adds budgeting,
annual projection, what-if simulation and rule-based insights ("AI advisor") on top of it.

## Source template (`Chi tieu T11_2026`)

The monthly sheet the user already maintains defines the data model:

| Group (sheet header) | Categories (columns)                                                   | Meaning                         |
|----------------------|------------------------------------------------------------------------|---------------------------------|
| **Chi**              | Sinh hoạt phí [1], Xăng, Ăn chơi, Mua sắm, Đám đình, Yêu Minh Anh      | Own spending                    |
| **Chi hộ**           | Chi hộ                                                                 | Paid on behalf of someone else  |
| **Tiết kiệm**        | Tiết kiệm                                                              | Money moved to savings          |
| **Thu**              | Được cho, Lương                                                        | Income (gifts, salary)          |

[1] *Sinh hoạt phí* = all living costs (rent, utilities, groceries…).

Rows are `Ngày | Tên chi phí | <amount in exactly one category column>`. The sheet shows a
`Total` row (per column) and an `All` row (per group plus a cyan balance cell).

## Users

Single household / single person, self-hosted (laptop, home server or private container).

## Functional requirements

| ID   | Requirement                                                                                          |
|------|------------------------------------------------------------------------------------------------------|
| FR-1 | Create, edit and delete transactions: date, name, category, amount (VND, integer > 0), optional note. |
| FR-2 | Monthly sheet view that mirrors the template: rows per transaction, `Total` per column, `All` per group, balance. |
| FR-3 | Monthly summary: total per group and category, balance, savings rate, spend ratio.                   |
| FR-4 | Monthly budget per spending category. A budget carries forward to later months until changed.       |
| FR-5 | Budget status per category with pace awareness (on track / at risk / over).                         |
| FR-6 | 12-month trend of income, spending and savings.                                                      |
| FR-7 | Annual projection: YTD actuals + average pace for the remaining months → projected annual savings.   |
| FR-8 | What-if simulator: cut % per category → monthly and annual savings gain.                             |
| FR-9 | Insights: rule-based advisor (savings-rate gap, 50/30/20 split, anomalies vs. history, budget overrun, outstanding "chi hộ", negative balance), each with severity and annual VND impact. |
| FR-10| Data acquisition: import the template as an Excel `.xlsx` workbook (all template sheets) or a CSV export of one sheet, idempotently; export any month back to the same layout. |
| FR-11| Demo mode: a seed command that generates realistic sample months.                                   |

## Definitions

- `balance = thu − chi − chi_ho − tiet_kiem` (cash left in hand for the period).
- `savings_rate = tiet_kiem / thu` (undefined when `thu = 0`).
- `spend_ratio = chi / thu`.
- Needs = Sinh hoạt phí, Xăng · Wants = Ăn chơi, Mua sắm, Yêu Minh Anh · Social = Đám đình.

## Non-functional requirements

| ID    | Requirement                                                                     |
|-------|---------------------------------------------------------------------------------|
| NFR-1 | Runs locally with one command; no external services or API keys required.       |
| NFR-2 | Money is stored as integer VND, never floats.                                   |
| NFR-3 | Data stays on the user's machine (SQLite file, mounted volume in Docker).       |
| NFR-4 | Optional HTTP Basic auth when exposed beyond localhost.                         |
| NFR-5 | Analytics are pure functions with injectable `today` so they are deterministic in tests. |
| NFR-6 | UI works on phone width, light and dark theme.                                  |
| NFR-7 | CI: lint + tests on Python 3.10–3.12, Docker image build.                       |

## Out of scope (v1)

Bank/e-wallet sync, multi-user accounts, multi-currency, LLM-generated advice (the insight
engine exposes an interface so an LLM narrator can be added later — see `04-ANALYSIS.md`).
