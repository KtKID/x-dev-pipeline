import json
import os
import re
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
XDEV = ROOT / "skills" / "x-dev" / "scripts" / "xdev.py"

SPEC = """# loan：借阅

> spec：loan

## feat01: 续借

> 状态：待实现
> 期次：1 期

## 变更记录

| 日期 | 改了什么 | 依据 / task | 状态 |
|---|---|---|---|
"""


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")


def claude_msg(ts: str, mid: str, inp: int, cw: int, cr: int, out: int, model="claude-opus-5-5") -> dict:
    return {"type": "assistant", "timestamp": ts, "sessionId": "s",
            "message": {"id": mid, "model": model, "usage": {
                "input_tokens": inp, "cache_creation_input_tokens": cw,
                "cache_read_input_tokens": cr, "output_tokens": out}}}


def codex_count(ts: str, inp: int, cached: int, out: int) -> dict:
    return {"type": "event_msg", "timestamp": ts, "payload": {"type": "token_count", "info": {
        "total_token_usage": {"input_tokens": inp, "cached_input_tokens": cached, "output_tokens": out,
                              "reasoning_output_tokens": 0, "total_tokens": inp + out}}}}


class UsageTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        self.repo = base / "repo"
        self.repo.mkdir()
        self.claude = base / "claude"
        self.codex = base / "codex"
        self.spec = self.repo / "spec.md"
        self.spec.write_text(SPEC, encoding="utf-8")
        self.env = {**os.environ, "CLAUDE_CONFIG_DIR": str(self.claude), "CODEX_HOME": str(self.codex)}
        self.claude_dir = self.claude / "projects" / re.sub(r"[^A-Za-z0-9]", "-", str(self.repo.resolve()))

    def tearDown(self):
        self.tmp.cleanup()

    def run_xdev(self, *args):
        p = subprocess.run([sys.executable, str(XDEV), "usage", *args], cwd=self.repo, env=self.env,
                           capture_output=True, text=True)
        return p.returncode, p.stdout + p.stderr

    def usage_rows(self):
        lines = self.spec.read_text(encoding="utf-8").splitlines()
        head = next(i for i, l in enumerate(lines) if l.startswith("| 期次"))
        cols = [c.strip() for c in lines[head].strip("|").split("|")]
        out = []
        for l in lines[head + 2:]:
            if not l.startswith("|"):
                break
            cells = [c.strip() for c in l.strip("|").split("|")]
            out.append(dict(zip(cols, cells)))
        return out

    def test_claude_start_and_fill(self):
        session = self.claude_dir / "sess-1.jsonl"
        write_jsonl(session, [
            {"type": "user", "timestamp": "2026-11-22T09:00:00Z", "cwd": str(self.repo.resolve())},
            claude_msg("2026-11-22T09:00:05Z", "m0", 999, 999, 999, 999),       # 开始之前，不算
            claude_msg("2026-11-22T10:00:05Z", "m1", 10, 100, 1000, 50),
            claude_msg("2026-11-22T10:00:06Z", "m1", 10, 100, 1000, 50),        # 同一条消息写成两行，只算一次
            claude_msg("2026-11-22T10:30:00Z", "m2", 5, 0, 2000, 20),
        ])
        write_jsonl(self.claude_dir / "sess-1" / "subagents" / "agent-a.jsonl", [
            claude_msg("2026-11-22T10:10:00Z", "x1", 1, 2, 3, 4, model="claude-haiku-5-5")])
        code, out = self.run_xdev("start", str(self.spec), "--phase", "1 期", "--what", "续借：讨论到验收", "--since", "2026-11-22T10:00:00Z")
        self.assertEqual(code, 0, out)
        row = self.usage_rows()[0]
        self.assertEqual((row["期次"], row["开始"], row["会话"], row["输入"]), ("1 期", "2026-11-22T10:00:00Z", "sess-1", ""))
        text = self.spec.read_text(encoding="utf-8")
        self.assertLess(text.index("## 用量"), text.index("## 变更记录"))
        code, out = self.run_xdev("fill", str(self.spec))
        self.assertEqual(code, 0, out)
        row = self.usage_rows()[0]
        self.assertEqual([row[k] for k in ("输入", "缓存写入", "缓存读取", "输出")], ["16", "102", "3003", "74"])
        self.assertEqual(row["结束"], "2026-11-22T10:30:00Z")
        self.assertIn("claude-haiku-5-5", row["工具 · 模型"])
        self.assertIn("含 1 个子 agent 记录", out)

    def test_codex_delta_and_cache_mapping(self):
        sid = "019a-codex-uuid"
        session = self.codex / "sessions" / "2026" / "11" / "22" / f"rollout-2026-11-22T09-00-00-{sid}.jsonl"
        write_jsonl(session, [
            {"type": "session_meta", "timestamp": "2026-11-22T09:00:00Z", "payload": {"id": sid, "cwd": str(self.repo.resolve())}},
            codex_count("2026-11-22T09:30:00Z", 1000, 600, 100),
            {"type": "turn_context", "timestamp": "2026-11-22T10:01:00Z", "payload": {"model": "gpt-5-codex"}},
            codex_count("2026-11-22T10:20:00Z", 5000, 3000, 400),
            codex_count("2026-11-22T10:40:00Z", 9000, 6000, 700),
        ])
        code, out = self.run_xdev("start", str(self.spec), "--phase", "1 期", "--what", "修 bug：续借时区", "--since", "2026-11-22T10:00:00Z")
        self.assertEqual(code, 0, out)
        self.assertEqual(self.usage_rows()[0]["会话"], sid)
        code, out = self.run_xdev("fill", str(self.spec))
        self.assertEqual(code, 0, out)
        row = self.usage_rows()[0]
        # 输入 = (9000-1000) - (6000-600)，缓存读取 = 6000-600，输出 = 700-100
        self.assertEqual([row[k] for k in ("输入", "缓存写入", "缓存读取", "输出")], ["2600", "—", "5400", "600"])
        self.assertEqual(row["工具 · 模型"], "Codex · gpt-5-codex")

    def test_two_recent_sessions_need_explicit_file(self):
        write_jsonl(self.claude_dir / "a.jsonl", [claude_msg("2026-11-22T10:00:00Z", "m", 1, 1, 1, 1)])
        write_jsonl(self.claude_dir / "b.jsonl", [claude_msg("2026-11-22T10:00:00Z", "m", 1, 1, 1, 1)])
        code, out = self.run_xdev("start", str(self.spec), "--phase", "1 期", "--what", "x")
        self.assertEqual(code, 2)
        self.assertIn("--session", out)
        code, out = self.run_xdev("start", str(self.spec), "--phase", "1 期", "--what", "x", "--session", str(self.claude_dir / "b.jsonl"))
        self.assertEqual(code, 0, out)
        self.assertEqual(self.usage_rows()[0]["会话"], "b")

    def test_row_from_other_machine_stays_and_warns(self):
        write_jsonl(self.claude_dir / "here.jsonl", [
            {"type": "user", "timestamp": "2026-11-22T10:00:00Z", "cwd": str(self.repo.resolve())},
            claude_msg("2026-11-22T10:05:00Z", "m", 1, 2, 3, 4)])
        self.run_xdev("start", str(self.spec), "--phase", "1 期", "--what", "本机", "--since", "2026-11-22T10:00:00Z")
        text = self.spec.read_text(encoding="utf-8").replace(
            "| 1 期 | 2026-11-22T10:00:00Z |", "| 1 期 | 2026-11-21T08:00:00Z |  | 别的机器 |  |  |  |  |  | far-away |\n| 1 期 | 2026-11-22T10:00:00Z |")
        self.spec.write_text(text, encoding="utf-8")
        code, out = self.run_xdev("fill", str(self.spec))
        self.assertEqual(code, 1, out)
        self.assertIn("far-away", out)
        rows = {r["做了什么"]: r for r in self.usage_rows()}
        self.assertEqual(rows["本机"]["输出"], "4")
        self.assertEqual(rows["别的机器"]["输入"], "")

    def test_sum_by_phase_and_tool(self):
        lines = SPEC.replace("## 变更记录", "## 用量\n\n| 期次 | 开始 | 结束 | 做了什么 | 工具 · 模型 | 输入 | 缓存写入 | 缓存读取 | 输出 | 会话 |\n|---|---|---|---|---|---|---|---|---|---|\n"
            "| 1 期 | t | t | a | Claude Code · opus | 10 | 20 | 30 | 40 | s1 |\n"
            "| 1 期 | t | t | b | Claude Code · opus | 1 | 2 | 3 | 4 | s2 |\n"
            "| 1 期 | t | t | c | Codex · gpt | 5 | — | 6 | 7 | s3 |\n"
            "| 2 期 | t |  | d |  |  |  |  |  | s4 |\n\n## 变更记录")
        self.spec.write_text(lines, encoding="utf-8")
        code, out = self.run_xdev("sum", str(self.spec))
        self.assertEqual(code, 0, out)
        self.assertIn("1 期 · Claude Code · 输入 11 · 缓存写入 22 · 缓存读取 33 · 输出 44", out)
        self.assertIn("1 期 · Codex · 输入 5 · 缓存写入 — · 缓存读取 6 · 输出 7", out)
        self.assertIn("还有 1 行没填数字", out)


if __name__ == "__main__":
    unittest.main()
