"""FastAPI application for the annual cost savings tracker."""

from __future__ import annotations

import base64
import binascii
import datetime as dt
import secrets
import uuid
from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Path, Query, Request, Response
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app import analytics, categories, insights
from app.categories import BY_ID, CHI
from app.config import MAX_IMPORT_BYTES, ROOT_DIR, auth_password, auth_user, database_path
from app.database import FinanceStore
from app.importer import export_template_csv, parse_template_file, without_duplicates
from app.models import BudgetIn, TransactionIn, WhatIfIn

MONTH_PATTERN = r"^\d{4}-(0[1-9]|1[0-2])$"
Month = Annotated[str, Path(pattern=MONTH_PATTERN)]
OptionalMonth = Annotated[str | None, Query(pattern=MONTH_PATTERN)]

app = FastAPI(title="Annual Cost Savings", version="0.1.0")
frontend_dir = ROOT_DIR / "frontend"
app.mount("/static", StaticFiles(directory=frontend_dir), name="static")


@app.middleware("http")
async def basic_auth(request: Request, call_next):
    password = auth_password()
    if not password or request.url.path == "/api/health":
        return await call_next(request)
    header = request.headers.get("authorization", "")
    if header.startswith("Basic "):
        try:
            user, _, given = base64.b64decode(header[6:]).decode("utf-8").partition(":")
        except (binascii.Error, UnicodeDecodeError):
            user, given = "", ""
        user_ok = secrets.compare_digest(user.encode(), auth_user().encode())
        password_ok = secrets.compare_digest(given.encode(), password.encode())
        if user_ok and password_ok:
            return await call_next(request)
    return Response(status_code=401, headers={"WWW-Authenticate": 'Basic realm="savings"'})


def get_store() -> Iterator[FinanceStore]:
    store = FinanceStore(database_path())
    try:
        yield store
    finally:
        store.close()


def get_today() -> dt.date:
    return dt.date.today()


Store = Annotated[FinanceStore, Depends(get_store)]
Today = Annotated[dt.date, Depends(get_today)]


@app.get("/")
def index() -> FileResponse:
    return FileResponse(frontend_dir / "index.html")


@app.get("/favicon.ico", include_in_schema=False)
def favicon() -> FileResponse:
    return FileResponse(frontend_dir / "favicon.svg")


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/categories")
def list_categories() -> dict[str, object]:
    return categories.as_dicts()


# Transactions -----------------------------------------------------------------------------


@app.get("/api/transactions")
def list_transactions(store: Store, month: OptionalMonth = None) -> list[dict[str, object]]:
    return [transaction.to_dict() for transaction in store.list_transactions(month)]


@app.post("/api/transactions", status_code=201)
def create_transaction(payload: TransactionIn, store: Store) -> dict[str, object]:
    transaction = payload.to_transaction(uuid.uuid4().hex)
    store.add_transactions([transaction])
    return transaction.to_dict()


@app.put("/api/transactions/{transaction_id}")
def update_transaction(
    transaction_id: str, payload: TransactionIn, store: Store
) -> dict[str, object]:
    transaction = payload.to_transaction(transaction_id)
    if not store.update_transaction(transaction):
        raise HTTPException(status_code=404, detail="transaction not found")
    return transaction.to_dict()


@app.delete("/api/transactions/{transaction_id}", status_code=204)
def delete_transaction(transaction_id: str, store: Store) -> Response:
    if not store.delete_transaction(transaction_id):
        raise HTTPException(status_code=404, detail="transaction not found")
    return Response(status_code=204)


# Monthly views ----------------------------------------------------------------------------


@app.get("/api/months/{month}/sheet")
def month_sheet(month: Month, store: Store) -> dict[str, object]:
    return analytics.month_sheet(store.list_transactions(month), month)


@app.get("/api/months/{month}/summary")
def month_summary(month: Month, store: Store) -> dict[str, object]:
    return analytics.month_summary(store.list_transactions(month), month)


@app.get("/api/months/{month}/budgets")
def month_budgets(month: Month, store: Store, today: Today) -> list[dict[str, object]]:
    return analytics.budget_status(
        store.list_transactions(month), store.budgets_for(month), month, today
    )


@app.put("/api/months/{month}/budgets/{category}")
def set_budget(month: Month, category: str, payload: BudgetIn, store: Store) -> dict[str, object]:
    if category not in BY_ID or BY_ID[category].group != CHI:
        raise HTTPException(status_code=422, detail="budgets apply to spending categories only")
    store.set_budget(month, category, payload.amount)
    return {"month": month, "category": category, "amount": payload.amount}


@app.get("/api/months/{month}/insights")
def month_insights(month: Month, store: Store, today: Today) -> list[dict[str, object]]:
    found = insights.generate(store.list_transactions(), store.budgets_for(month), month, today)
    return [insight.to_dict() for insight in found]


@app.get("/api/months/{month}/export.csv")
def export_month(month: Month, store: Store) -> Response:
    return Response(
        content=export_template_csv(store.list_transactions(month)),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="chi-tieu-{month}.csv"'},
    )


# Multi-month views ------------------------------------------------------------------------


@app.get("/api/trend")
def trend(
    store: Store,
    today: Today,
    end: OptionalMonth = None,
    months: int = 12,
) -> list[dict[str, object]]:
    months = max(1, min(months, 36))
    return analytics.trend(store.list_transactions(), end or analytics.month_of(today), months)


@app.get("/api/projection")
def projection(store: Store, today: Today, year: int | None = None) -> dict[str, object]:
    return analytics.annual_projection(store.list_transactions(), year or today.year, today)


@app.post("/api/what-if")
def what_if(payload: WhatIfIn, store: Store, today: Today) -> dict[str, object]:
    return analytics.what_if(store.list_transactions(), payload.cuts, today)


# Data acquisition -------------------------------------------------------------------------


@app.post("/api/import")
async def import_file(request: Request, store: Store) -> dict[str, object]:
    """Body is the raw file: a template CSV or an Excel .xlsx workbook."""
    body = await request.body()
    if len(body) > MAX_IMPORT_BYTES:
        limit_mb = MAX_IMPORT_BYTES // (1024 * 1024)
        raise HTTPException(status_code=413, detail=f"file too large (max {limit_mb} MB)")
    try:
        result = parse_template_file(body)
    except ValueError as error:  # includes UnicodeDecodeError
        raise HTTPException(status_code=422, detail=str(error)) from error
    fresh = without_duplicates(result.transactions, store.list_transactions())
    store.add_transactions(fresh)
    return {
        "imported": len(fresh),
        "duplicates": len(result.transactions) - len(fresh),
        "skipped": result.skipped,
        "unknown_columns": result.unknown_columns,
    }
