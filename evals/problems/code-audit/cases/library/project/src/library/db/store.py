"""极简数据库：每次 query 都算一次真实查询。"""
from library.api.views import PAGE_SIZE


class DB:
    def __init__(self, rows: dict[str, list[dict]]):
        self.rows = rows
        self.queries = 0

    def query(self, table: str, **where) -> list[dict]:
        self.queries += 1
        return [r for r in self.rows.get(table, []) if all(r.get(k) == v for k, v in where.items())]

    def page(self, table: str, n: int) -> list[dict]:
        self.queries += 1
        return self.rows.get(table, [])[n * PAGE_SIZE:(n + 1) * PAGE_SIZE]
