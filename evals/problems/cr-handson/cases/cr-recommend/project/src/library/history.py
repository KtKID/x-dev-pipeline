"""借阅历史。"""
from collections import defaultdict

CATALOG = {
    "三体": "科幻", "球状闪电": "科幻", "沙丘": "科幻", "基地": "科幻",
    "活着": "文学", "许三观卖血记": "文学",
}


class HistoryStore:
    def __init__(self):
        self._by_member: dict[int, list[str]] = defaultdict(list)

    def add(self, member_id: int, book: str) -> None:
        self._by_member[member_id].append(book)

    def books_of(self, member_id: int) -> list[str]:
        return list(self._by_member[member_id])
