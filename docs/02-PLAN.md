# 02 · Plan

## Architecture

```text
 Google Sheet / Excel (template)        Browser UI (frontend/)
          │ .xlsx / CSV                       │ fetch JSON
          ▼                                   ▼
   app/importer.py  ───────────►  app/main.py  (FastAPI, optional Basic auth)
   (format readers → one set of template rules)
                                      │
               ┌──────────────────────┼─────────────────────────┐
               ▼                      ▼                         ▼
      app/database.py         app/analytics.py           app/insights.py
      (SQLite store:          (pure functions: sheet,    (rule engine →
       transactions,           summary, budgets, trend,   Insight list with
       budgets)                projection, what-if)       annual VND impact)
               ▲
       app/categories.py  — the template catalog (single source of truth)
```

## Technology

Same stack as the sibling portfolio repos so they share tooling:

| Layer     | Choice                                   | Why                                         |
|-----------|------------------------------------------|---------------------------------------------|
| API       | FastAPI + Pydantic v2                    | Typed validation, OpenAPI docs for free     |
| Storage   | SQLite (stdlib `sqlite3`)                | Zero-ops, a single file, easy to back up    |
| Excel     | openpyxl (read-only, cached values)      | Pure Python, reads .xlsx without Excel      |
| Frontend  | Static HTML/CSS/JS, hand-rolled SVG chart| No build step, no CDN dependency            |
| Tests     | `unittest` + FastAPI `TestClient`        | Matches sibling repos                       |
| Lint      | Ruff                                     |                                             |
| Deploy    | Docker + docker-compose, GitHub Actions  |                                             |

## Milestones

| #  | Milestone                      | Exit criterion                                  |
|----|--------------------------------|-------------------------------------------------|
| M1 | Domain + storage               | Catalog, models and store pass their unit tests |
| M2 | Analytics + insights           | Sheet, summary, budgets, projection, what-if and rules tested with a fixed `today` |
| M3 | Data acquisition               | Template .xlsx and CSV import; export → import gives no duplicates |
| M4 | API                            | Every endpoint covered by an API test           |
| M5 | UI                             | Dashboard, sheet, add form, budgets, trend chart, what-if, import/export |
| M6 | Ship                           | Dockerfile, compose, CI, deploy guide           |
