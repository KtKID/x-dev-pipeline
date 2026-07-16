#!/usr/bin/env python3
"""test_xdev_orchestration — xdev.py status/graph 子命令的单元测试。

零依赖：用标准库 unittest（`python3 -m unittest test.test_xdev_orchestration`）。
覆盖：表格解析、token→引擎状态映射、progress 计算、纯 emoji 旧 checklist 兼容、
      product 锚点交叉验证、Kahn 拓扑排序、环检测、ready/blocked、空依赖、parallel_batches。

fixture 通过临时目录构造，不依赖项目真实 task。
"""

from __future__ import annotations

import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from contextlib import redirect_stdout

# 把 tools/ 加入 import 路径，直接测内部函数（更细粒度）
TOOLS_DIR = Path(__file__).resolve().parent.parent / "tools"
sys.path.insert(0, str(TOOLS_DIR))

import xdev  # noqa: E402


def write_checklist(task_dir: Path, content: str) -> None:
    (task_dir / "dev-checklist.md").write_text(content, encoding="utf-8")


def run_status_json(task_dir: Path) -> dict:
    buf = io.StringIO()
    with redirect_stdout(buf):
        code = xdev.status_command(task_dir, as_json=True)
    assert code == 0, f"status_command 返回 {code}"
    return json.loads(buf.getvalue())


def run_graph_json(task_dir: Path) -> tuple[dict, int]:
    buf = io.StringIO()
    with redirect_stdout(buf):
        code = xdev.graph_command(task_dir, as_json=True)
    return json.loads(buf.getvalue()), code


# ---------- status：token 状态映射 ----------

class TestTokenStatusMapping(unittest.TestCase):
    def test_done_token(self):
        self.assertEqual(xdev.task_engine_status("[x] 🟢"), "done")
        self.assertEqual(xdev.task_engine_status("[x] ✅"), "done")

    def test_blocked_token(self):
        self.assertEqual(xdev.task_engine_status("[!] 🔴"), "blocked")

    def test_todo_token(self):
        self.assertEqual(xdev.task_engine_status("[ ] ⏳"), "todo")
        self.assertEqual(xdev.task_engine_status("[ ] ▶️"), "todo")
        self.assertEqual(xdev.task_engine_status("[ ] 🟡"), "todo")

    def test_token_priority_over_emoji(self):
        # 矛盾标注：token 优先（[x] 🔴 → done，不是 blocked）
        self.assertEqual(xdev.task_engine_status("[x] 🔴"), "done")
        self.assertEqual(xdev.task_engine_status("[ ] 🟢"), "todo")


class TestEmojiFallback(unittest.TestCase):
    """纯 emoji 旧 checklist（无 token）的兼容降级。"""

    def test_green_to_done(self):
        self.assertEqual(xdev.task_engine_status("🟢"), "done")
        self.assertEqual(xdev.task_engine_status("✅"), "done")

    def test_red_to_blocked(self):
        self.assertEqual(xdev.task_engine_status("🔴"), "blocked")

    def test_others_to_todo(self):
        self.assertEqual(xdev.task_engine_status("⏳"), "todo")
        self.assertEqual(xdev.task_engine_status("▶️"), "todo")
        self.assertEqual(xdev.task_engine_status("🟡"), "todo")
        self.assertEqual(xdev.task_engine_status(""), "todo")


# ---------- status：依赖列解析 ----------

class TestParseDeps(unittest.TestCase):
    def test_empty(self):
        self.assertEqual(xdev.parse_deps("—"), [])
        self.assertEqual(xdev.parse_deps("-"), [])
        self.assertEqual(xdev.parse_deps(""), [])
        self.assertEqual(xdev.parse_deps("  "), [])

    def test_single(self):
        self.assertEqual(xdev.parse_deps("T1"), ["T1"])
        self.assertEqual(xdev.parse_deps("#1"), ["T1"])

    def test_multi_separators(self):
        # 逗号、斜杠、空格、混合
        self.assertEqual(sorted(xdev.parse_deps("T2,T3")), ["T2", "T3"])
        self.assertEqual(sorted(xdev.parse_deps("T2/T3")), ["T2", "T3"])
        self.assertEqual(sorted(xdev.parse_deps("T2 T3")), ["T2", "T3"])
        self.assertEqual(sorted(xdev.parse_deps("#1 #2")), ["T1", "T2"])

    def test_bare_digit_not_matched(self):
        # 依赖列要求前缀（TASK_ID_RE），裸数字不匹配——符合契约
        self.assertEqual(xdev.parse_deps("1"), [])
        self.assertEqual(xdev.parse_deps("1,2"), [])


# ---------- status：checklist 解析 + progress ----------

class TestParseChecklist(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_basic_parse(self):
        write_checklist(self.dir, """# t

| # | 任务 | 涉及文件 | 依赖 | 状态 | fix |
|---|------|---------|------|------|-----|
| T1 | 基础 | a.py | — | [x] 🟢 | — |
| T2 | 上层 | b.py | T1 | [ ] ⏳ | — |
""")
        tasks, findings = xdev.resolve_task_list(self.dir)
        self.assertEqual(len(tasks), 2)
        self.assertEqual(tasks[0]["id"], "T1")
        self.assertEqual(tasks[0]["status"], "done")
        self.assertEqual(tasks[1]["deps"], ["T1"])

    def test_pure_digit_id_column(self):
        # F1 回归：id 列纯数字也能归一化
        write_checklist(self.dir, """# t

| # | 任务 | 依赖 | 状态 | fix |
|---|------|------|------|-----|
| 1 | 任务一 | — | [ ] ⏳ | — |
| 2 | 任务二 | 1 | [x] 🟢 | — |
""")
        tasks, _ = xdev.resolve_task_list(self.dir)
        ids = [t["id"] for t in tasks]
        self.assertEqual(ids, ["T1", "T2"])

    def test_progress(self):
        tasks = [
            {"id": "T1", "status": "done"},
            {"id": "T2", "status": "todo"},
            {"id": "T3", "status": "todo"},
            {"id": "T4", "status": "blocked"},
        ]
        p = xdev.compute_progress(tasks)
        self.assertEqual(p, {"total": 4, "done": 1, "todo": 2, "blocked": 1})

    def test_product_anchor_missing(self):
        # done 但产物文件不存在 → product_check: missing
        write_checklist(self.dir, """# t

| # | 任务 | 涉及文件 | 状态 | fix |
|---|------|---------|------|-----|
| T1 | 基础 | a.py, product:reports/T1.md | [x] 🟢 | — |
""")
        tasks, findings = xdev.resolve_task_list(self.dir)
        self.assertEqual(tasks[0]["product_check"], "missing")
        self.assertEqual(len(findings), 1)

    def test_product_anchor_stale(self):
        # todo 但产物文件已存在 → product_check: stale
        (self.dir / "reports").mkdir()
        (self.dir / "reports" / "T1.md").write_text("done", encoding="utf-8")
        write_checklist(self.dir, """# t

| # | 任务 | 涉及文件 | 状态 | fix |
|---|------|---------|------|-----|
| T1 | 基础 | a.py, product:reports/T1.md | [ ] ⏳ | — |
""")
        tasks, findings = xdev.resolve_task_list(self.dir)
        self.assertEqual(tasks[0]["product_check"], "stale")

    def test_missing_checklist(self):
        with self.assertRaises(FileNotFoundError):
            xdev.parse_checklist(self.dir)

    def test_missing_table(self):
        write_checklist(self.dir, "# t\n\n无表格的文件")
        with self.assertRaises(ValueError):
            xdev.parse_checklist(self.dir)

    def test_missing_required_column(self):
        # F1 回归：表格存在但表头缺关键列（# 或 状态）→ ValueError
        # 构造一个缺"状态"列的表头（只有 # | 任务 | 依赖 | fix）
        write_checklist(self.dir, """# t

| # | 任务 | 依赖 | fix |
|---|------|------|-----|
| T1 | 基础 | — | — |
""")
        with self.assertRaises(ValueError) as ctx:
            xdev.parse_checklist(self.dir)
        self.assertIn("状态", str(ctx.exception))  # 错误信息应点名缺哪列

    def test_status_command_happy_path(self):
        # F2 回归：status_command 成功路径（exit 0 + JSON 含 progress 字段）
        write_checklist(self.dir, """# t

| # | 任务 | 依赖 | 状态 | fix |
|---|------|------|------|-----|
| T1 | done | — | [x] 🟢 | — |
| T2 | todo | T1 | [ ] ⏳ | — |
""")
        result = run_status_json(self.dir)
        self.assertEqual(result["progress"], {"total": 2, "done": 1, "todo": 1, "blocked": 0})
        self.assertEqual(len(result["tasks"]), 2)


# ---------- graph：拓扑排序 ----------

class TestTopoSort(unittest.TestCase):
    def test_linear(self):
        order, cycle = xdev.topo_sort(["T1", "T2", "T3"], {"T1": [], "T2": ["T1"], "T3": ["T2"]})
        self.assertEqual(order, ["T1", "T2", "T3"])
        self.assertEqual(cycle, [])

    def test_parallel_roots(self):
        # 两个无依赖的根节点
        order, cycle = xdev.topo_sort(["T1", "T2"], {"T1": [], "T2": []})
        self.assertEqual(set(order), {"T1", "T2"})
        self.assertEqual(cycle, [])

    def test_cycle_detection(self):
        order, cycle = xdev.topo_sort(["T1", "T2"], {"T1": ["T2"], "T2": ["T1"]})
        self.assertEqual(set(cycle), {"T1", "T2"})
        self.assertEqual(order, [])

    def test_self_loop(self):
        # 自环：T1 依赖自己
        order, cycle = xdev.topo_sort(["T1", "T2"], {"T1": ["T1"], "T2": []})
        self.assertIn("T1", cycle)

    def test_dangling_dep_ignored_in_topo(self):
        # 悬空依赖（指向不存在的 id）不计入入度，不污染拓扑。
        # T1 依赖 T99（不在 valid 集合）→ indeg[T1]=0 → T1 正常进 order。
        # 悬空依赖由 compute_graph 的 blocked 暴露，不阻塞拓扑排序本身。
        order, cycle = xdev.topo_sort(["T1"], {"T1": ["T99"]})
        self.assertEqual(order, ["T1"])
        self.assertEqual(cycle, [])


class TestTopoSortDangling(unittest.TestCase):
    def test_dangling_does_not_block(self):
        # 悬空依赖不进 adj（只对 valid 内的 dep 建边），所以 T1 入度 0，正常进 order
        order, cycle = xdev.topo_sort(["T1", "T2"], {"T1": ["T99"], "T2": []})
        self.assertEqual(set(order), {"T1", "T2"})
        self.assertEqual(cycle, [])


# ---------- graph：compute_graph 集成 ----------

class TestComputeGraph(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def _setup(self, md: str) -> list[dict]:
        write_checklist(self.dir, md)
        tasks, _ = xdev.resolve_task_list(self.dir)
        return tasks

    def test_ready_and_blocked(self):
        tasks = self._setup("""# t

| # | 任务 | 依赖 | 状态 | fix |
|---|------|------|------|-----|
| T1 | 基础 | — | [x] 🟢 | — |
| T2 | 上层 | T1 | [ ] ⏳ | — |
| T3 | 阻塞 | T99 | [ ] ⏳ | — |
""")
        g = xdev.compute_graph(tasks)
        self.assertIn("T2", g["ready"])
        # T3 有悬空依赖 T99 → blocked
        blocked_ids = [b["id"] for b in g["blocked"]]
        self.assertIn("T3", blocked_ids)

    def test_parallel_batches(self):
        # T1 done，T2/T3 依赖 T1（ready 可并行），T4 依赖 T2+T3
        tasks = self._setup("""# t

| # | 任务 | 依赖 | 状态 | fix |
|---|------|------|------|-----|
| T1 | 基础 | — | [x] 🟢 | — |
| T2 | 左 | T1 | [ ] ⏳ | — |
| T3 | 右 | T1 | [ ] ⏳ | — |
| T4 | 合 | T2,T3 | [ ] ⏳ | — |
""")
        g = xdev.compute_graph(tasks)
        # batch 1 应该是 T2,T3（可并行），batch 2 是 T4
        self.assertEqual(g["parallel_batches"][0], ["T2", "T3"])
        self.assertEqual(g["parallel_batches"][1], ["T4"])

    def test_all_done_no_batches(self):
        tasks = self._setup("""# t

| # | 任务 | 依赖 | 状态 | fix |
|---|------|------|------|-----|
| T1 | 基础 | — | [x] 🟢 | — |
| T2 | 上层 | T1 | [x] ✅ | — |
""")
        g = xdev.compute_graph(tasks)
        self.assertEqual(g["parallel_batches"], [])
        self.assertEqual(g["ready"], [])

    def test_cycle_reported(self):
        tasks = self._setup("""# t

| # | 任务 | 依赖 | 状态 | fix |
|---|------|------|------|-----|
| T1 | 环1 | T2 | [ ] ⏳ | — |
| T2 | 环2 | T1 | [ ] ⏳ | — |
""")
        g = xdev.compute_graph(tasks)
        self.assertEqual(set(g["cycle"]), {"T1", "T2"})


# ---------- CLI 退出码 ----------

class TestCLIExitCodes(unittest.TestCase):
    def test_status_nonexistent_dir(self):
        code = xdev.status_command(Path("/nonexistent/xyz"), as_json=True)
        self.assertEqual(code, 2)

    def test_graph_cycle_exit1(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            write_checklist(d, """# t

| # | 任务 | 依赖 | 状态 | fix |
|---|------|------|------|-----|
| T1 | 环1 | T2 | [ ] ⏳ | — |
| T2 | 环2 | T1 | [ ] ⏳ | — |
""")
            _, code = run_graph_json(d)
            self.assertEqual(code, 1)

    def test_graph_clean_exit0(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            write_checklist(d, """# t

| # | 任务 | 依赖 | 状态 | fix |
|---|------|------|------|-----|
| T1 | 基础 | — | [ ] ⏳ | — |
""")
            _, code = run_graph_json(d)
            self.assertEqual(code, 0)


if __name__ == "__main__":
    unittest.main()
