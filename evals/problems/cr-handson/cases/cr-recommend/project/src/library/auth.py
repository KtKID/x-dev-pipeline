"""登录会话。"""
from dataclasses import dataclass


@dataclass
class Member:
    member_id: int
    favorite_category: str


SESSIONS: dict[str, Member] = {}


def current_member(token: str) -> Member:
    member = SESSIONS.get(token)
    if member is None:
        raise PermissionError("未登录")
    return member
