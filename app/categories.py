"""Category catalog mirroring the monthly spending template (Chi tieu T11_2026).

This is the single source of truth for groups, columns and their order. Rename a label here
when the spreadsheet template changes; stored transactions only reference the stable ids.
"""

from __future__ import annotations

from dataclasses import dataclass

CHI = "chi"
CHI_HO = "chi_ho"
TIET_KIEM = "tiet_kiem"
THU = "thu"

GROUPS: tuple[tuple[str, str], ...] = (
    (CHI, "Chi"),
    (CHI_HO, "Chi hộ"),
    (TIET_KIEM, "Tiết kiệm"),
    (THU, "Thu"),
)

NEEDS = "needs"
WANTS = "wants"
SOCIAL = "social"


@dataclass(frozen=True)
class Category:
    id: str
    label: str
    group: str
    kind: str = ""


CATEGORIES: tuple[Category, ...] = (
    Category("sinh_hoat_phi", "Sinh hoạt phí", CHI, NEEDS),
    Category("xang", "Xăng", CHI, NEEDS),
    Category("an_choi", "Ăn chơi", CHI, WANTS),
    Category("mua_sam", "Mua sắm", CHI, WANTS),
    Category("dam_dinh", "Đám đình", CHI, SOCIAL),
    Category("yeu", "Yêu Minh Anh", CHI, WANTS),
    Category("chi_ho", "Chi hộ", CHI_HO),
    Category("tiet_kiem", "Tiết kiệm", TIET_KIEM),
    Category("duoc_cho", "Được cho", THU),
    Category("luong", "Lương", THU),
)

BY_ID: dict[str, Category] = {category.id: category for category in CATEGORIES}


def ids_in_group(group: str) -> list[str]:
    return [category.id for category in CATEGORIES if category.group == group]


def ids_of_kind(kind: str) -> list[str]:
    return [category.id for category in CATEGORIES if category.kind == kind]


def as_dicts() -> dict[str, list[dict[str, str]]]:
    return {
        "groups": [{"id": group_id, "label": label} for group_id, label in GROUPS],
        "categories": [category.__dict__ for category in CATEGORIES],
    }
