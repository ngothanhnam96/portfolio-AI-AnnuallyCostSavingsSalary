# portfolio-AI-AnnuallyCostSavingsSalary

Application/Platform help saving money — a self-hosted salary-efficiency tracker that keeps the
familiar monthly spending spreadsheet and adds the answers a spreadsheet doesn't give you:

- **How much of my salary do I really keep?** Savings rate and cash left, every month.
- **What is drifting?** Budgets with pace tracking and anomaly detection against your own history.
- **Where will I be in December?** Annual projection from your real monthly pace.
- **What is a habit worth?** What-if simulator: cut Ăn chơi by 30 % → +X ₫ per year.
- **What should I do?** A rule-based advisor (savings-rate gap, 50/30/20, budget overruns,
  anomalies, outstanding "chi hộ") — every suggestion carries an annual VND impact.

## Built from your spreadsheet

The data model mirrors the monthly template (`Chi tieu T11_2026`):

| Chi                                                                 | Chi hộ | Tiết kiệm | Thu               |
|---------------------------------------------------------------------|--------|-----------|-------------------|
| Sinh hoạt phí · Xăng · Ăn chơi · Mua sắm · Đám đình · Yêu Minh Anh  | Chi hộ | Tiết kiệm | Được cho · Lương  |

`Còn lại = Thu − Chi − Chi hộ − Tiết kiệm`. Use **Import CSV / Excel** with the workbook itself
(`.xlsx`, every sheet that has a `Ngày` header row is imported) or a CSV download of one sheet.
The importer understands the template's title, `All` and `Total` rows, real Excel date and
number cells, and text amounts like `1.234.000`, `80k` and `1.5tr`. Re-importing never
duplicates. **Export CSV** writes the same layout back.

Categories live in [`app/categories.py`](app/categories.py) — edit labels there when the
template changes.

## Quick start

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1      # macOS/Linux: source .venv/bin/activate
python -m pip install -r requirements.txt -r requirements-dev.txt
python -m app.seed --reset        # optional: 6 months of demo data
python -m uvicorn app.main:app --reload
```

Use a virtual environment and `python -m uvicorn` rather than a bare `uvicorn`: with several
Pythons installed, the `uvicorn` on PATH may belong to an interpreter that lacks the
dependencies (e.g. `ModuleNotFoundError: No module named 'openpyxl'`).

Open `http://127.0.0.1:8000`. Or with Docker: `docker compose up --build`.

```powershell
python -m unittest discover -s tests -t .   # 51 tests
python -m ruff check app tests
```

## API

```text
GET    /api/health
GET    /api/categories
GET    /api/transactions?month=YYYY-MM
POST   /api/transactions
PUT    /api/transactions/{id}
DELETE /api/transactions/{id}
GET    /api/months/{month}/sheet          template layout with Total / All rows
GET    /api/months/{month}/summary
GET    /api/months/{month}/budgets
PUT    /api/months/{month}/budgets/{category}
GET    /api/months/{month}/insights
GET    /api/months/{month}/export.csv
GET    /api/trend?end=YYYY-MM&months=12
GET    /api/projection?year=YYYY
POST   /api/what-if                       {"cuts": {"an_choi": 0.3}}
POST   /api/import                        body: raw .xlsx or .csv file (max 5 MB)
```

Interactive docs at `/docs`.

## Engineering process

The project was built spec-first; each stage has its own document:

1. [Spec](docs/01-SPEC.md) — problem, requirements, definitions
2. [Plan](docs/02-PLAN.md) — architecture, stack, milestones
3. [Tasks](docs/03-TASKS.md) — traceable task list and backlog
4. [Analysis](docs/04-ANALYSIS.md) — data model, formulas, insight rules, risks
5. Implementation — `app/`, `frontend/`
6. [Testing](docs/05-TESTING.md) — suites, coverage map, regressions found
7. [Deploy](docs/06-DEPLOY.md) — Docker, backups, security, CI

## Architecture

```text
Excel .xlsx ─► xlsx reader ─┐
CSV ─────────► csv reader ──┴─► template rules ──┐
                                                 ▼
Browser UI ────────────────────► FastAPI ────────┼──► SQLite (transactions, budgets)
                                                 ├──► analytics  (pure functions)
                                                 └──► insights   (rule engine → annual ₫ impact)
```

## Roadmap

LLM narrator over the structured insights, Google Sheets API sync, recurring transactions,
settling "chi hộ" — see [docs/03-TASKS.md](docs/03-TASKS.md).

## License

MIT
