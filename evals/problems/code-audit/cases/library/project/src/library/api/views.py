"""接口层：读者列表页。"""
from __future__ import annotations

import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from library.db.store import DB

PAGE_SIZE = 20
MAX_RENEWALS = 3
WEEKDAYS = ["一", "二", "三", "四", "五", "六", "日"]


def member_page(db: DB) -> list[dict]:
    """列出所有读者和各自的借阅数。"""
    out = []
    for member in db.query("members"):
        loans = db.query("loans", member_id=member["id"])
        out.append({"name": member["name"], "loans": len(loans), "max": MAX_RENEWALS})
    return out


def week_header() -> list[str]:
    """每周七天的表头，每天标出和其他天的相对位置。"""
    header = []
    for i, a in enumerate(WEEKDAYS):
        offset = 0
        for j, b in enumerate(WEEKDAYS):
            if j < i:
                offset += 1
        header.append(f"周{a}({offset})")
    return header
