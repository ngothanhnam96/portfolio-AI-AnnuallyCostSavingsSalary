"""Domain records and API input schemas. Money is always integer VND."""

from __future__ import annotations

import datetime as dt
from dataclasses import asdict, dataclass

from pydantic import BaseModel, Field, field_validator

from app.categories import BY_ID, CHI, ids_in_group


@dataclass
class Transaction:
    id: str
    date: str  # ISO yyyy-mm-dd
    name: str
    category: str
    amount: int
    note: str = ""

    @property
    def month(self) -> str:
        return self.date[:7]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


class TransactionIn(BaseModel):
    date: dt.date
    name: str = Field(min_length=1, max_length=200)
    category: str
    amount: int = Field(gt=0, le=100_000_000_000)
    note: str = Field(default="", max_length=500)

    @field_validator("name", "note")
    @classmethod
    def strip_text(cls, value: str) -> str:
        return value.strip()

    @field_validator("category")
    @classmethod
    def known_category(cls, value: str) -> str:
        if value not in BY_ID:
            raise ValueError(f"unknown category '{value}'")
        return value

    def to_transaction(self, transaction_id: str) -> Transaction:
        return Transaction(
            id=transaction_id,
            date=self.date.isoformat(),
            name=self.name,
            category=self.category,
            amount=self.amount,
            note=self.note,
        )


class BudgetIn(BaseModel):
    amount: int = Field(ge=0, le=100_000_000_000)


class WhatIfIn(BaseModel):
    cuts: dict[str, float]

    @field_validator("cuts")
    @classmethod
    def valid_cuts(cls, value: dict[str, float]) -> dict[str, float]:
        spending = set(ids_in_group(CHI))
        for category, cut in value.items():
            if category not in spending:
                raise ValueError(f"'{category}' is not a spending category")
            if not 0 <= cut <= 1:
                raise ValueError("cut must be between 0 and 1")
        return value
