"""token 用量：从本机会话记录算出一段工作用了多少 token，写进 spec 的「用量」表。

- start：在 spec 的「用量」表追加一行，记期次、开始时间、做了什么和本会话编号，数字留空。
- fill：把表里数字还空着的行算出来填上：读这一行会话编号对应的本机记录，加总开始时间以后的用量。
- 不带子命令：按期次和工具分开打印合计。

只读本机会话记录，数字由脚本算，不手填：
- Claude Code：`$CLAUDE_CONFIG_DIR`（默认 ~/.claude）/projects/*/<会话编号>.jsonl，
  每条 assistant 消息带 usage（input_tokens、cache_creation_input_tokens、cache_read_input_tokens、output_tokens），
  同一条消息可能写成多行，按 message.id 只算一次；`<会话编号>/subagents/*.jsonl` 存在时一起算。
- Codex：`$CODEX_HOME`（默认 ~/.codex）/sessions/**/rollout-*<会话编号>*.jsonl，
  token_count 事件是累计值，用量 = 最后一次累计 − 开始前最后一次累计；
  cached_input_tokens 包含在 input_tokens 里，所以输入记 input − cached，缓存读取记 cached，缓存写入记“—”。
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

SECTION = "用量"
COLUMNS = ["期次", "开始", "结束", "做了什么", "工具 · 模型", "输入", "缓存写入", "缓存读取", "输出", "会话"]
NUMS = ["输入", "缓存写入", "缓存读取", "输出"]
RECENT = 600  # 秒：这段时间内都在写的会话记录不止一个，就要调用方用 --session 指明


class UsageError(Exception):
    pass


def now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_time(value: str) -> datetime:
    v = value.strip().replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(v)
    except ValueError as e:
        raise UsageError(f"时间格式不对：{value}（要 UTC ISO 时间，如 2026-11-22T10:05:00Z）") from e
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def claude_home() -> Path:
    return Path(os.environ.get("CLAUDE_CONFIG_DIR") or Path.home() / ".claude")


def codex_home() -> Path:
    return Path(os.environ.get("CODEX_HOME") or Path.home() / ".codex")


def read_jsonl(path: Path):
    with path.open(encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(row, dict):
                yield row


# ───────────────────────────── 找会话记录 ─────────────────────────────

def codex_meta(path: Path) -> dict:
    for row in read_jsonl(path):
        if row.get("type") == "session_meta" and isinstance(row.get("payload"), dict):
            return row["payload"]
    return {}


def claude_cwd(path: Path) -> str | None:
    for i, row in enumerate(read_jsonl(path)):
        if row.get("cwd"):
            return row["cwd"]
        if i > 50:
            break
    return None


def candidates(cwd: Path) -> list[tuple[float, str, Path]]:
    """本项目目录下的会话记录：(修改时间, 工具, 文件)。"""
    cwd_s = str(cwd.resolve())
    out: list[tuple[float, str, Path]] = []
    projects = claude_home() / "projects"
    if projects.is_dir():
        mapped = projects / re.sub(r"[^A-Za-z0-9]", "-", cwd_s)
        files = list(mapped.glob("*.jsonl")) if mapped.is_dir() else []
        if not files:
            files = [p for p in projects.glob("*/*.jsonl") if claude_cwd(p) == cwd_s]
        out += [(p.stat().st_mtime, "claude", p) for p in files]
    sessions = codex_home() / "sessions"
    if sessions.is_dir():
        for p in sessions.rglob("rollout-*.jsonl"):
            if str(codex_meta(p).get("cwd", "")) == cwd_s:
                out.append((p.stat().st_mtime, "codex", p))
    return sorted(out, reverse=True)


def current_session(cwd: Path) -> tuple[str, Path]:
    found = candidates(cwd)
    if not found:
        raise UsageError(f"在本机找不到 {cwd} 的会话记录（Claude Code 看 {claude_home()}/projects，Codex 看 {codex_home()}/sessions）；用 --session 指明记录文件")
    newest = found[0][0]
    busy = [p for m, _, p in found if newest - m < RECENT and m > time.time() - RECENT]
    if len(busy) > 1:
        listing = "、".join(str(p) for p in busy)
        raise UsageError(f"最近有不止一个会话在写记录，分不清哪个是本会话：{listing}。用 --session 指明")
    return found[0][1], found[0][2]


def session_id(tool: str, path: Path) -> str:
    if tool == "claude":
        return path.stem
    return str(codex_meta(path).get("id") or path.stem)


def tool_of(path: Path) -> str:
    return "codex" if path.name.startswith("rollout-") or codex_meta(path) else "claude"


def files_for(sid: str, extra: list[Path]) -> tuple[str, list[Path]] | None:
    """按会话编号找本机记录文件；--session 给的文件优先。"""
    for p in extra:
        tool = tool_of(p)
        if session_id(tool, p) == sid:
            return tool, [p] + subagent_files(tool, p)
    projects = claude_home() / "projects"
    if projects.is_dir():
        for p in projects.glob(f"*/{sid}.jsonl"):
            return "claude", [p] + subagent_files("claude", p)
    sessions = codex_home() / "sessions"
    if sessions.is_dir():
        for p in sessions.rglob(f"rollout-*{sid}*.jsonl"):
            return "codex", [p]
    return None


def subagent_files(tool: str, path: Path) -> list[Path]:
    if tool != "claude":
        return []
    return sorted((path.parent / path.stem / "subagents").glob("*.jsonl"))


# ───────────────────────────── 加总 ─────────────────────────────

def claude_usage(files: list[Path], since: datetime) -> dict:
    seen: dict[str, dict] = {}
    models: set[str] = set()
    last: datetime | None = None
    for path in files:
        for row in read_jsonl(path):
            msg = row.get("message")
            if row.get("type") != "assistant" or not isinstance(msg, dict) or not isinstance(msg.get("usage"), dict):
                continue
            ts = row.get("timestamp")
            if not ts or parse_time(ts) < since:
                continue
            key = f"{path}:{msg.get('id') or row.get('uuid')}"
            seen[key] = msg["usage"]  # 同一条消息写成多行时只留最后一行
            if msg.get("model"):
                models.add(msg["model"])
            t = parse_time(ts)
            last = t if last is None or t > last else last
    total = {"输入": 0, "缓存写入": 0, "缓存读取": 0, "输出": 0}
    for u in seen.values():
        total["输入"] += int(u.get("input_tokens") or 0)
        total["缓存写入"] += int(u.get("cache_creation_input_tokens") or 0)
        total["缓存读取"] += int(u.get("cache_read_input_tokens") or 0)
        total["输出"] += int(u.get("output_tokens") or 0)
    return {"tool": "Claude Code", "models": sorted(models), "last": last, **total}


def codex_usage(path: Path, since: datetime) -> dict:
    before = {"input_tokens": 0, "cached_input_tokens": 0, "output_tokens": 0}
    end = dict(before)
    models: set[str] = set()
    last: datetime | None = None
    for row in read_jsonl(path):
        payload = row.get("payload") if isinstance(row.get("payload"), dict) else {}
        ts = row.get("timestamp")
        if row.get("type") == "turn_context" and payload.get("model") and ts and parse_time(ts) >= since:
            models.add(payload["model"])
        if row.get("type") != "event_msg" or payload.get("type") != "token_count":
            continue
        usage = (payload.get("info") or {}).get("total_token_usage")
        if not isinstance(usage, dict) or not ts:
            continue
        snap = {k: int(usage.get(k) or 0) for k in before}
        t = parse_time(ts)
        if t < since:
            before = snap
        else:
            end = snap
            last = t
    if last is None:
        end = before
    d = {k: end[k] - before[k] for k in before}
    return {"tool": "Codex", "models": sorted(models), "last": last,
            "输入": d["input_tokens"] - d["cached_input_tokens"], "缓存写入": None,
            "缓存读取": d["cached_input_tokens"], "输出": d["output_tokens"]}


# ───────────────────────────── spec 里的「用量」表 ─────────────────────────────

def split_cells(line: str) -> list[str]:
    return [c.strip() for c in line.strip().strip("|").split("|")]


def table_lines(lines: list[str]) -> tuple[int, int, int] | None:
    """返回 (节标题行, 表头行, 表格结束的下一行)；没有「用量」节返回 None。"""
    head = next((i for i, l in enumerate(lines) if re.match(rf"^##\s+{SECTION}\s*$", l)), None)
    if head is None:
        return None
    i = head + 1
    while i < len(lines) and not lines[i].startswith("## "):
        if lines[i].lstrip().startswith("|") and "期次" in lines[i]:
            j = i + 2
            while j < len(lines) and lines[j].lstrip().startswith("|"):
                j += 1
            return head, i, j
        i += 1
    raise UsageError(f"「{SECTION}」一节里没有表格（表头：{' | '.join(COLUMNS)}）")


def ensure_section(lines: list[str]) -> list[str]:
    if table_lines(lines) is not None:
        return lines
    block = [f"## {SECTION}", "", "| " + " | ".join(COLUMNS) + " |", "|" + "---|" * len(COLUMNS), ""]
    at = next((i for i, l in enumerate(lines) if re.match(r"^##\s+变更记录", l)), len(lines))
    return lines[:at] + block + lines[at:]


def rows(lines: list[str]) -> list[tuple[int, dict]]:
    found = table_lines(lines)
    if not found:
        return []
    _, h, end = found
    cols = split_cells(lines[h])
    out = []
    for i in range(h + 2, end):
        cells = split_cells(lines[i])
        out.append((i, {c: (cells[k] if k < len(cells) else "") for k, c in enumerate(cols)}))
    return out


def render(row: dict) -> str:
    return "| " + " | ".join(row.get(c, "") for c in COLUMNS) + " |"


def fmt(n) -> str:
    return "—" if n is None else str(n)


# ───────────────────────────── 子命令 ─────────────────────────────

def start(spec: Path, phase: str, what: str, since: str | None, session: Path | None) -> int:
    if not spec.is_file():
        raise UsageError(f"找不到 spec：{spec}")
    began = now_utc() if since is None else parse_time(since).strftime("%Y-%m-%dT%H:%M:%SZ")
    if session is not None:
        tool, path = tool_of(session), session
    else:
        tool, path = current_session(Path.cwd())
    sid = session_id(tool, path)
    lines = ensure_section(spec.read_text(encoding="utf-8").splitlines())
    _, _, end = table_lines(lines)
    row = {"期次": phase, "开始": began, "做了什么": what, "会话": sid}
    lines.insert(end, render(row))
    spec.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"✅ 用量开始记录 · {spec} · {phase} · {began} · 会话 {sid}")
    return 0


def fill(spec: Path, extra: list[Path]) -> int:
    lines = spec.read_text(encoding="utf-8").splitlines()
    todo = [(i, r) for i, r in rows(lines) if not r.get("输入")]
    if not todo:
        print("用量表没有待填的行")
        return 0
    missing = []
    for i, r in todo:
        sid = r.get("会话", "")
        found = files_for(sid, extra) if sid else None
        if not found:
            missing.append(f"{r.get('期次')} · {r.get('做了什么')} · 会话 {sid or '空'}")
            continue
        tool, files = found
        since = parse_time(r["开始"])
        u = claude_usage(files, since) if tool == "claude" else codex_usage(files[0], since)
        r["结束"] = u["last"].strftime("%Y-%m-%dT%H:%M:%SZ") if u["last"] else r["开始"]
        r["工具 · 模型"] = u["tool"] + (" · " + "、".join(u["models"]) if u["models"] else "")
        for k in NUMS:
            r[k] = fmt(u[k])
        lines[i] = render(r)
        extra_note = f"（含 {len(files) - 1} 个子 agent 记录）" if len(files) > 1 else ""
        print(f"✅ 已填 · {r['期次']} · {r['做了什么']} · 输入 {r['输入']} · 缓存写入 {r['缓存写入']} · 缓存读取 {r['缓存读取']} · 输出 {r['输出']}{extra_note}")
    spec.write_text("\n".join(lines) + "\n", encoding="utf-8")
    if missing:
        print("⚠️ 这些行的会话记录不在本机，请在做这段工作的那台机器上运行 xdev usage fill：" + "；".join(missing))
        return 1
    return 0


def summary(spec: Path) -> int:
    lines = spec.read_text(encoding="utf-8").splitlines()
    totals: dict[tuple[str, str], dict] = {}
    pending = 0
    for _, r in rows(lines):
        if not r.get("输入"):
            pending += 1
            continue
        key = (r.get("期次", ""), r.get("工具 · 模型", "").split(" · ")[0])
        t = totals.setdefault(key, {k: 0 for k in NUMS})
        for k in NUMS:
            v = r.get(k, "")
            if v.isdigit():
                t[k] += int(v)
    for (phase, tool), t in sorted(totals.items()):
        print(f"{phase} · {tool} · 输入 {t['输入']} · 缓存写入 {t['缓存写入'] if tool != 'Codex' else '—'} · 缓存读取 {t['缓存读取']} · 输出 {t['输出']}")
    if pending:
        print(f"还有 {pending} 行没填数字（运行 xdev usage fill）")
    if not totals and not pending:
        print("用量表还没有记录")
    return 0


def main(args) -> int:
    try:
        spec = Path(args.spec)
        if args.action == "start":
            return start(spec, args.phase, args.what, args.since, Path(args.session[0]) if args.session else None)
        if args.action == "fill":
            return fill(spec, [Path(p) for p in args.session])
        return summary(spec)
    except UsageError as e:
        print(f"错误：{e}", file=sys.stderr)
        return 2
