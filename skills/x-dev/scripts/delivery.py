#!/usr/bin/env python3
"""交付检查：start / coverage / check。

- start：开工时把 git HEAD 记为「代码基线」，之后的改动都和它比。
- coverage：运行测试命令，读覆盖率报告，算出本次改动的代码行有多少被测试跑到；
  不到 100% 就列出没跑到的 文件:行，退出码 1。结果写进证据目录和交付文档的「结果」节。
- check：交付前的机械核对（原 x-verify-spec 里能用脚本判断的部分）：
  结构与编号、需求变化已同步、行状态、每个场景都有通过的用例、每个用例都有真实存在的测试、
  高风险行有真实链路用例、覆盖率记录 100% 且代码之后没再改过、
  功能检查回执（证据目录 feature-check.md，risk Q0 不要求）通过且是在最后一次跑覆盖率之后写的。

对象：
- 常规 task：docs/spec/<spec>/tasks/<task>/（读写 dev-checklist.md，证据放 <task>/evidence/）。
- qdev 单文档：docs/spec/<spec>/tasks/<task>.md（证据放 tasks/<task>-evidence/）。

退出码：0 通过；1 未通过；2 用法、目标、IO 或报告格式错误。
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path

CODE_EXT = {
    ".py", ".go", ".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx", ".vue", ".svelte",
    ".java", ".kt", ".kts", ".scala", ".rs", ".rb", ".php", ".cs", ".swift", ".m", ".mm",
    ".c", ".cc", ".cpp", ".cxx", ".h", ".hpp", ".dart", ".lua", ".ex", ".exs", ".sh",
}
TEST_PATH_RE = re.compile(r"(^|/)(tests?|__tests__|spec|testdata|fixtures?)/|\.test\.|\.spec\.|_test\.|(^|/)test_|(^|/)conftest\.py$")
DOC_DIRS = ("docs/", "evals/", "reports/")
PASS_WORDS = {"通过", "人工通过"}
REAL_LAYERS = ("smoke", "e2e", "集成", "integration", "真实链路")
RECORD = "coverage.json"
RECEIPT = "feature-check.md"
SKIP_DIRS = re.compile(r"(^|/)(evidence|[^/]+-evidence)/")


class UsageError(Exception):
    pass


# ───────────────────────────── 定位 ─────────────────────────────

class Target:
    """交付文档（dev-checklist.md 或 qdev task.md）及其证据目录。"""

    def __init__(self, raw: str | Path):
        p = Path(raw)
        if p.is_dir():
            self.doc = p / "dev-checklist.md"
            self.task_dir = p
            self.evidence = p / "evidence"
            self.kind = "checklist"
        elif p.suffix == ".md":
            self.doc = p
            self.task_dir = None
            self.evidence = p.with_name(p.stem + "-evidence")
            self.kind = "checklist" if p.name == "dev-checklist.md" else "qdev"
            if self.kind == "checklist":
                self.task_dir = p.parent
                self.evidence = p.parent / "evidence"
        else:
            raise UsageError(f"目标应为 task 目录或 qdev 的 task .md 文件：{raw}")
        if not self.doc.is_file():
            raise UsageError(f"找不到交付文档：{self.doc}")
        self.root = find_root(self.doc.resolve().parent)

    def text(self) -> str:
        return self.doc.read_text(encoding="utf-8")


def find_root(start: Path) -> Path:
    try:
        out = subprocess.run(["git", "rev-parse", "--show-toplevel"], cwd=start, capture_output=True, text=True, check=True)
        return Path(out.stdout.strip())
    except (subprocess.CalledProcessError, FileNotFoundError):
        for p in [start, *start.parents]:
            if (p / ".git").exists():
                return p
        return start


def git(root: Path, *args: str) -> str:
    try:
        return subprocess.run(["git", *args], cwd=root, capture_output=True, text=True, check=True).stdout
    except FileNotFoundError as e:
        raise UsageError("需要 git：没有找到 git 命令") from e
    except subprocess.CalledProcessError as e:
        detail = (e.stderr or "").strip().splitlines()[-1:] or [""]
        raise UsageError(f"需要 git 仓库且至少有一个 commit、代码基线 commit 存在（git {' '.join(args[:2])} 失败：{detail[0]}）") from e


def rel(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


# ───────────────────────────── 文档读写 ─────────────────────────────

def header(text: str, key: str) -> str | None:
    m = re.search(rf"^>\s*{re.escape(key)}\s*[:：]\s*(.*)$", text, re.M)
    if not m:
        return None
    value = m.group(1).strip()
    return None if not value or value.startswith(("<", "（", "(")) else value


def set_header(text: str, key: str, value: str, after: tuple[str, ...]) -> str:
    """改写 `> key：value`；没有这一行时插到 after 中第一个存在的头部行后面。"""
    pat = re.compile(rf"^(>\s*{re.escape(key)}\s*[:：]).*$", re.M)
    if pat.search(text):
        return pat.sub(lambda m: f"{m.group(1)}{value}", text, count=1)
    for anchor in after:
        am = re.search(rf"^>\s*{re.escape(anchor)}\s*[:：].*$", text, re.M)
        if am:
            return text[:am.end()] + f"\n> {key}：{value}" + text[am.end():]
    first = re.search(r"^>.*$", text, re.M)
    if first:
        return text[:first.end()] + f"\n> {key}：{value}" + text[first.end():]
    return f"> {key}：{value}\n" + text


RESULT_HEADING = {"checklist": "## 结果", "qdev": "## ⑤ 验证结果"}


def set_result_line(text: str, kind: str, key: str, value: str) -> str:
    heading = RESULT_HEADING[kind]
    section = re.search(rf"^{re.escape(heading)}.*$", text, re.M)
    if section is None:
        text = text.rstrip("\n") + f"\n\n{heading}\n"
        section = re.search(rf"^{re.escape(heading)}.*$", text, re.M)
    start = section.end()
    nxt = re.search(r"^## ", text[start:], re.M)
    end = start + nxt.start() if nxt else len(text)
    body = text[start:end]
    pat = re.compile(rf"^(>\s*{re.escape(key)}\s*[:：]).*$", re.M)
    if pat.search(body):
        body = pat.sub(lambda m: f"{m.group(1)}{value}", body, count=1)
    else:
        body = f"\n\n> {key}：{value}" + body if not body.strip() else f"\n\n> {key}：{value}\n" + body.lstrip("\n")
    return text[:start] + body + text[end:]


def split_cells(line: str) -> list[str]:
    s = line.strip()
    if s.startswith("|"):
        s = s[1:]
    if s.endswith("|"):
        s = s[:-1]
    return [c.strip() for c in s.split("|")]


def table_after(text: str, heading_word: str) -> list[dict[str, str]]:
    """读取标题含 heading_word 的那一节里的第一张表，返回 [{列名: 值, '_line': 行号}]。"""
    lines = text.splitlines()
    rows: list[dict[str, str]] = []
    in_section = False
    columns: list[str] = []
    level = 0
    for idx, raw in enumerate(lines, 1):
        line = raw.strip()
        hm = re.match(r"^(#+)\s+(.*)$", line)
        if hm:
            if in_section and len(hm.group(1)) <= level:
                break
            if heading_word in hm.group(2):
                in_section, level, columns = True, len(hm.group(1)), []
            continue
        if not in_section or not line.startswith("|"):
            if in_section and columns and rows and not line.startswith("|") and line:
                break
            continue
        cells = split_cells(line)
        if not columns:
            columns = cells
            continue
        if all(re.fullmatch(r":?-{2,}:?", c) for c in cells if c):
            continue
        row = {name: (cells[i] if i < len(cells) else "") for i, name in enumerate(columns)}
        row["_line"] = str(idx)
        rows.append(row)
    return rows


def section_text(text: str, heading_word: str) -> str:
    m = re.search(rf"^(#+)\s+[^\n]*{re.escape(heading_word)}[^\n]*$", text, re.M)
    if not m:
        return ""
    level = len(m.group(1))
    rest = text[m.end():]
    nxt = re.search(rf"^#{{1,{level}}}\s", rest, re.M)
    return rest[:nxt.start()] if nxt else rest


def col(row: dict[str, str], *names: str) -> str:
    for name in names:
        for key, value in row.items():
            if key.startswith(name):
                return value
    return ""


# ───────────────────────────── start ─────────────────────────────

def is_code_file(path: str) -> bool:
    if any(path.startswith(d) for d in DOC_DIRS) or TEST_PATH_RE.search(path):
        return False
    return Path(path).suffix.lower() in CODE_EXT


def start(raw: str, as_json: bool = False) -> int:
    t = Target(raw)
    text = t.text()
    existing = header(text, "代码基线")
    head = git(t.root, "rev-parse", "HEAD").strip()
    dirty = [line[3:] for line in git(t.root, "status", "--porcelain").splitlines()
             if is_code_file(line[3:].strip('"'))]
    if existing is None:
        text = set_header(text, "代码基线", head, ("拆解基线", "tech-design", "执行者", "状态"))
        t.doc.write_text(text, encoding="utf-8")
    t.evidence.mkdir(parents=True, exist_ok=True)
    result = {"code_baseline": existing or head, "kept_existing": existing is not None, "dirty_code_files": dirty}
    if as_json:
        print(json.dumps(result, ensure_ascii=False))
    else:
        print(f"代码基线：{result['code_baseline']}" + ("（已有，未改）" if existing else ""))
        if dirty:
            print("注意：开工前已有未提交的代码改动，会算进本次改动：" + "、".join(dirty))
    return 0


# ───────────────────────────── 改动行 ─────────────────────────────

HUNK_RE = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@")


def changed_lines(root: Path, base: str) -> dict[str, set[int]]:
    out: dict[str, set[int]] = {}
    diff = git(root, "diff", "-U0", "--no-color", "--no-ext-diff", "--no-renames", base, "--")
    current: str | None = None
    for line in diff.splitlines():
        if line.startswith("+++ "):
            path = line[4:].strip()
            current = None if path == "/dev/null" else path[2:] if path.startswith("b/") else path
            continue
        m = HUNK_RE.match(line)
        if m and current is not None:
            a, n = int(m.group(1)), int(m.group(2) or 1)
            out.setdefault(current, set()).update(range(a, a + n))
    for path in git(root, "ls-files", "--others", "--exclude-standard").splitlines():
        try:
            n = len((root / path).read_text(encoding="utf-8", errors="replace").splitlines())
        except OSError:
            continue
        out[path] = set(range(1, n + 1))
    return {p: lines for p, lines in out.items()
            if lines and is_code_file(p) and not SKIP_DIRS.search(p) and (root / p).is_file()}


def code_state(root: Path, files: list[str]) -> dict[str, str]:
    state = {}
    for p in sorted(files):
        state[p] = git(root, "hash-object", "--", p).strip()
    return state


# ───────────────────────────── 覆盖率报告 ─────────────────────────────

class Cov:
    """file -> (可执行行, 已执行行)"""

    def __init__(self) -> None:
        self.files: dict[str, tuple[set[int], set[int]]] = {}

    def add(self, path: str, line: int, hit: bool) -> None:
        exe, cov = self.files.setdefault(path, (set(), set()))
        exe.add(line)
        if hit:
            cov.add(line)


def parse_lcov(text: str, cov: Cov) -> None:
    current = None
    for line in text.splitlines():
        if line.startswith("SF:"):
            current = line[3:].strip()
        elif line.startswith("DA:") and current:
            parts = line[3:].split(",")
            cov.add(current, int(parts[0]), int(float(parts[1])) > 0)
        elif line.startswith("end_of_record"):
            current = None


def parse_cobertura(text: str, cov: Cov) -> None:
    tree = ET.fromstring(text)
    sources = [s.text.strip() for s in tree.iter("source") if s.text and s.text.strip()]
    for cls in tree.iter("class"):
        name = cls.get("filename", "")
        lines = cls.find("lines")
        if lines is None:
            continue
        paths = [str(Path(s) / name) for s in sources] + [name]
        for ln in lines.iter("line"):
            for p in paths:
                cov.add(p, int(ln.get("number", "0")), int(float(ln.get("hits", "0"))) > 0)


def parse_coverage_json(text: str, cov: Cov) -> None:
    data = json.loads(text)
    for path, info in (data.get("files") or {}).items():
        for n in info.get("executed_lines", []):
            cov.add(path, int(n), True)
        for n in info.get("missing_lines", []):
            cov.add(path, int(n), False)


GO_RE = re.compile(r"^(.+):(\d+)\.\d+,(\d+)\.\d+ \d+ (\d+)$")


def parse_go(text: str, cov: Cov) -> None:
    for line in text.splitlines():
        m = GO_RE.match(line.strip())
        if not m:
            continue
        path, a, b, count = m.group(1), int(m.group(2)), int(m.group(3)), int(m.group(4))
        for n in range(a, b + 1):
            cov.add(path, n, count > 0)


def load_report(path: Path, cov: Cov) -> str:
    text = path.read_text(encoding="utf-8", errors="replace")
    head = text.lstrip()[:200]
    if head.startswith("mode:"):
        parse_go(text, cov)
        return "go"
    if head.startswith("<"):
        parse_cobertura(text, cov)
        return "cobertura"
    if head.startswith("{"):
        parse_coverage_json(text, cov)
        return "coverage.py-json"
    if "SF:" in text:
        parse_lcov(text, cov)
        return "lcov"
    raise UsageError(f"认不出覆盖率报告格式（支持 lcov、cobertura XML、coverage.py JSON、Go coverprofile）：{path}")


def match_report_path(report_path: str, root: Path, changed: set[str]) -> str | None:
    p = report_path.replace("\\", "/")
    cand = Path(p)
    if cand.is_absolute():
        try:
            p = cand.resolve().relative_to(root.resolve()).as_posix()
        except ValueError:
            pass
    p = p[2:] if p.startswith("./") else p
    if p in changed:
        return p
    hits = [c for c in changed if c.endswith("/" + p) or p.endswith("/" + c)]
    return hits[0] if len(hits) == 1 else None


def ranges(nums: list[int]) -> str:
    out, i = [], 0
    nums = sorted(nums)
    while i < len(nums):
        j = i
        while j + 1 < len(nums) and nums[j + 1] == nums[j] + 1:
            j += 1
        out.append(str(nums[i]) if i == j else f"{nums[i]}-{nums[j]}")
        i = j + 1
    return ",".join(out)


def nonblank(root: Path, path: str, lines: set[int]) -> set[int]:
    try:
        content = (root / path).read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return set(lines)
    return {n for n in lines if n <= len(content) and content[n - 1].strip()}


EXCLUDE_RE = re.compile(r"pragma:\s*no\s*cover|istanbul\s+ignore|[cv]8\s+ignore|coverage:\s*ignore|LCOV_EXCL|nocover", re.I)


def exclusions(root: Path, changed: dict[str, set[int]]) -> list[str]:
    """改动行里新加的覆盖率排除标记：允许用，但要在「问题与处置」写理由。"""
    found = []
    for path in sorted(changed):
        try:
            content = (root / path).read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        for n in sorted(changed[path]):
            if n <= len(content) and EXCLUDE_RE.search(content[n - 1]):
                found.append(f"{path}:{n}")
    return found


def measure(root: Path, base: str, reports: list[Path]) -> dict:
    changed = changed_lines(root, base)
    cov = Cov()
    formats = [load_report(r, cov) for r in reports]
    mapped: dict[str, tuple[set[int], set[int]]] = {}
    for path, (exe, hit) in cov.files.items():
        key = match_report_path(path, root, set(changed))
        if key is None:
            continue
        e, h = mapped.setdefault(key, (set(), set()))
        e.update(exe)
        h.update(hit)
    files, missing = {}, {}
    total = covered = 0
    for path in sorted(changed):
        lines = changed[path]
        if path not in mapped:
            body = nonblank(root, path, lines)
            if body:
                missing[path] = ranges(list(body))
                total += len(body)
            continue
        exe, hit = mapped[path]
        relevant = lines & exe
        if not relevant:
            continue
        unc = relevant - hit
        files[path] = {"changed_exec": len(relevant), "covered": len(relevant) - len(unc), "uncovered": ranges(list(unc))}
        total += len(relevant)
        covered += len(relevant) - len(unc)
    percent = 100.0 if total == 0 else round(covered * 100.0 / total, 2)
    return {
        "base": base, "formats": formats, "total": total, "covered": covered, "percent": percent,
        "files": files, "not_in_report": missing, "exclusions": exclusions(root, changed),
        "code_state": code_state(root, list(changed) + changed_test_files(root, base)),
    }


def coverage(raw: str, reports: list[str], cmds: list[str], out_dir: str | None, as_json: bool = False) -> int:
    t = Target(raw)
    base = header(t.text(), "代码基线")
    if base is None:
        raise UsageError("交付文档没有「代码基线」，开工时先运行 xdev start")
    evidence = Path(out_dir) if out_dir else t.evidence
    evidence.mkdir(parents=True, exist_ok=True)
    runs = []
    for i, cmd in enumerate(cmds, 1):
        proc = subprocess.run(cmd, shell=True, cwd=t.root, capture_output=True, text=True)
        log = evidence / f"test-run-{i}.log"
        log.write_text(f"$ {cmd}\n(exit {proc.returncode})\n\n{proc.stdout}\n{proc.stderr}", encoding="utf-8")
        runs.append({"cmd": cmd, "exit": proc.returncode, "log": rel(log, t.root)})
    report_paths = [t.root / r if not Path(r).is_absolute() else Path(r) for r in reports]
    for r in report_paths:
        if not r.is_file():
            raise UsageError(f"覆盖率报告不存在：{r}" + ("（测试命令失败，见日志）" if any(x["exit"] for x in runs) else ""))
    result = measure(t.root, base, report_paths)
    result["reports"] = [rel(r, t.root) for r in report_paths]
    result["runs"] = runs
    result["finished_at"] = time.time()
    tests_ok = bool(runs) and all(x["exit"] == 0 for x in runs)
    result["tests_ok"] = tests_ok
    result["ok"] = tests_ok and result["percent"] == 100.0
    record = evidence / RECORD
    record.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    summary = coverage_summary(result, rel(record, t.root))
    if out_dir is None:
        t.doc.write_text(set_result_line(t.text(), t.kind, "覆盖率", summary), encoding="utf-8")
    if as_json:
        print(json.dumps(result, ensure_ascii=False))
    else:
        print(summary)
        for x in runs:
            if x["exit"]:
                print(f"测试命令失败（exit {x['exit']}）：{x['cmd']} · 日志 {x['log']}")
        for path, info in result["files"].items():
            if info["uncovered"]:
                print(f"未覆盖 {path}:{info['uncovered']}")
        for path, lines in result["not_in_report"].items():
            print(f"报告里没有这个文件（测试没加载它，算未覆盖）{path}:{lines}")
        for loc in result["exclusions"]:
            print(f"新加了覆盖率排除标记 {loc}：在「问题与处置」写一行理由")
        if not runs:
            print("没有用 --cmd 运行测试：xdev check 不会认这份记录")
    return 0 if result["ok"] else 1


def coverage_summary(result: dict, record: str) -> str:
    mark = "✅" if result.get("ok") else "❌"
    lines = f"{result['covered']}/{result['total']} 行" if result["total"] else "本次没有可执行的代码改动"
    tests = "测试通过" if result.get("tests_ok") else "测试未通过或未运行"
    return f"{mark} {result['percent']:g}%（{lines}）· {tests} · 基线 {result['base'][:12]} · 记录 {record}"


# ───────────────────────────── 功能检查回执 ─────────────────────────────

def is_test_file(path: str) -> bool:
    if any(path.startswith(d) for d in DOC_DIRS) or SKIP_DIRS.search(path):
        return False
    return Path(path).suffix.lower() in CODE_EXT and bool(TEST_PATH_RE.search(path))


def changed_test_files(root: Path, base: str) -> list[str]:
    names = set(git(root, "diff", "--name-only", "--no-renames", base, "--").splitlines())
    names |= set(git(root, "ls-files", "--others", "--exclude-standard").splitlines())
    return sorted(p for p in names if is_test_file(p) and (root / p).is_file())


def parse_feature_receipt(text: str) -> tuple[str | None, list[tuple[str, str]], set[str]]:
    """返回 (结论, [(编号, 严重度)], “已检查”里列出的文件)。"""
    m = re.search(r"结论\s*[:：]\s*(不通过|通过)", text)
    verdict = m.group(1) if m else None
    issues: list[tuple[str, str]] = []
    columns: list[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line.startswith("|"):
            columns = [] if not line else columns
            continue
        cells = split_cells(line)
        if not columns:
            if any(c.startswith("编号") for c in cells) and any(c.startswith("严重度") for c in cells):
                columns = cells
            continue
        if all(re.fullmatch(r":?-{2,}:?", c) for c in cells if c):
            continue
        row = {name: (cells[i] if i < len(cells) else "") for i, name in enumerate(columns)}
        iid = col(row, "编号").strip("` ")
        if iid and not iid.startswith("<"):
            issues.append((iid, col(row, "严重度").strip("` ").upper()))
    checked: set[str] = set()
    sm = re.search(r"已检查\s*[:：](.*?)(?:\n\s*\n|\n\s*\||\Z)", text, re.S)
    if sm:
        body = re.sub(r"[（(]共[^）)]*[）)]", "", sm.group(1))
        checked = {x.strip("` ") for x in re.split(r"[、,，;；\s]+", body) if x.strip("` ")}
        checked.discard("无")
    return verdict, issues, checked


def needs_feature_check(t: Target) -> bool:
    """risk Q0 和只记变更、没写场景的 qdev 不做功能检查。"""
    text = t.text()
    if t.kind == "checklist":
        return (header(text, "risk") or "").upper() != "Q0"
    confirm = table_section_line(text, "spec 归属与确认") or ""
    # 只有整条记录都是“无需确认”才跳过；一份 spec 无需确认、另一份已确认的混合情况仍要检查
    return "无需确认" not in confirm or bool(re.search(r"已确认|用户确认|用户回复", confirm))


def check_feature(t: Target, out: list[dict]) -> None:
    """功能检查回执（证据目录 feature-check.md）：要做时必须有；“已检查”列全改动的测试文件；
    P0/P1 都没了（结论通过）或每条都在「问题与处置」写了不采纳理由；
    回执写在最后一次跑覆盖率之后（代码或测试一改覆盖率就要重跑，旧回执随之过期）。"""
    if not needs_feature_check(t):
        return
    base = header(t.text(), "代码基线")
    if base is None:
        return
    try:
        tests = changed_test_files(t.root, base)
    except UsageError as e:
        problem(out, "FEATURE_CHECK", f"无法列出改动的测试：{e}")
        return
    rp = t.evidence / RECEIPT
    where = rel(rp, t.root)
    listing = "要检查的测试文件（派工单照抄这份完整清单）：" + ("、".join(tests) if tests else "无")
    if not rp.is_file():
        problem(out, "FEATURE_CHECK", f"没有功能检查回执 {where}：按 x-verify-spec 的功能检查派子 agent。{listing}")
        return
    text = rp.read_text(encoding="utf-8")
    verdict, issues, checked = parse_feature_receipt(text)
    if "功能检查回执" not in text or verdict is None:
        problem(out, "FEATURE_CHECK", f"{where} 格式不对：要有“功能检查回执”和“结论：通过/不通过”")
        return
    missing = [p for p in tests if p not in checked]
    if missing:
        problem(out, "FEATURE_CHECK", "回执的“已检查”没有列出这些测试文件：" + "、".join(missing) + f"。重做功能检查，{listing}")
    notes = section_text(t.text(), "问题与处置").splitlines()
    blocking = [iid for iid, sev in issues if sev in ("P0", "P1")]
    open_items = [iid for iid in blocking
                  if not any("功能检查" in ln and re.search(rf"{re.escape(iid)}(?!\d)", ln) and "不采纳" in ln for ln in notes)]
    if verdict == "不通过" and not blocking:
        open_items = ["（结论不通过，但没列出 P0/P1）"]
    if open_items:
        problem(out, "FEATURE_CHECK_OPEN", "当前回执里还有 P0/P1：" + "、".join(open_items) + "。没修就交 x-fix；修好了要重做功能检查，新回执里没有它才关闭；认为报错了就写不采纳理由")
    record = t.evidence / RECORD
    if record.is_file():
        finished = json.loads(record.read_text(encoding="utf-8")).get("finished_at")
        if finished and rp.stat().st_mtime < finished:
            problem(out, "FEATURE_CHECK_STALE", f"覆盖率在功能检查之后重跑过（代码或测试改了）：重做功能检查，覆盖回执。{listing}")


# ───────────────────────────── check ─────────────────────────────

def load_checklist_engine():
    here = Path(__file__).resolve().parent
    sys.path.insert(0, str(here.parent.parent / "x-req" / "scripts"))
    import checklist_engine  # noqa: E402
    return checklist_engine


def problem(out: list[dict], rule: str, msg: str, line: int | str = 0) -> None:
    out.append({"rule": rule, "line": int(line or 0), "msg": msg})


def check_coverage_record(t: Target, out: list[dict]) -> None:
    base = header(t.text(), "代码基线")
    if base is None:
        problem(out, "CODE_BASELINE", "没有「代码基线」：开工时运行 xdev start")
        return
    record = t.evidence / RECORD
    if not record.is_file():
        problem(out, "COVERAGE", f"没有覆盖率记录 {rel(record, t.root)}：运行 xdev coverage")
        return
    data = json.loads(record.read_text(encoding="utf-8"))
    if data.get("base") != base:
        problem(out, "COVERAGE", "覆盖率记录的基线和「代码基线」不一致：重跑 xdev coverage")
    if not data.get("runs"):
        problem(out, "COVERAGE", "覆盖率记录不是用 --cmd 跑出来的：用 xdev coverage --cmd 运行全量测试")
    elif not data.get("tests_ok"):
        problem(out, "TESTS", "最近一次测试命令没通过：" + "；".join(f"{r['cmd']}（exit {r['exit']}）" for r in data["runs"] if r["exit"]))
    notes = section_text(t.text(), "问题与处置")
    unc = [f"{p}:{i['uncovered']}" for p, i in data.get("files", {}).items() if i.get("uncovered")]
    # 没有覆盖率工具的语言（如 Shell）：报告里没有的文件，在「问题与处置」写了文件路径和理由就认
    unc += [f"{p}:{l}（报告里没有）" for p, l in data.get("not_in_report", {}).items() if p not in notes]
    if unc:
        problem(out, "COVERAGE", f"改动行覆盖率 {data.get('percent')}%，没到 100%：" + "；".join(unc))
    for loc in data.get("exclusions", []):
        if loc.split(":")[0] not in notes:
            problem(out, "COVERAGE_EXCLUDE", f"新加了覆盖率排除标记 {loc}，「问题与处置」里没写理由")
    try:
        now = changed_lines(t.root, base)
        state = code_state(t.root, list(now) + changed_test_files(t.root, base))
    except UsageError as e:
        problem(out, "COVERAGE", f"无法和代码基线比较：{e}")
        return
    if state != data.get("code_state"):
        diff = sorted(set(state.items()) ^ set((data.get("code_state") or {}).items()))
        files = sorted({p for p, _ in diff})
        problem(out, "COVERAGE_STALE", "覆盖率跑完后代码或测试又改了，重跑 xdev coverage：" + "、".join(files))


def check_mapping(t: Target, cases_needed: dict[str, str], scenes_needed: set, design_cases: dict,
                  rows_high: list[tuple[str, set[str], int]], ce, main: str, out: list[dict]) -> None:
    table = table_after(t.text(), "用例对应")
    if not table:
        problem(out, "MAPPING", "「用例对应」表没有内容（用例 | 测试位置 | 层级 | 结果）")
    mapped: dict[str, dict] = {}
    scene_hits: set = set()
    for row in table:
        line = row["_line"]
        case = col(row, "用例").strip("` ")
        where = col(row, "测试位置")
        layer = col(row, "层级").lower()
        result = col(row, "结果").strip()
        if result not in PASS_WORDS:
            problem(out, "MAPPING_RESULT", f"{case} 的结果是「{result or '空'}」，要写 通过 / 人工通过", line)
        for loc in [x.strip("` ") for x in re.split(r"[、,，;；]\s*", where) if x.strip("` ")]:
            path, _, name = loc.partition("::")
            fp = t.root / path
            if not fp.is_file():
                problem(out, "MAPPING_PATH", f"{case} 的测试位置不存在：{path}", line)
                continue
            leaf = re.split(r"::|\.", name)[-1].split("[")[0].strip() if name else ""
            if leaf and leaf not in fp.read_text(encoding="utf-8", errors="replace"):
                problem(out, "MAPPING_PATH", f"{case} 的测试 {leaf} 在 {path} 里找不到", line)
            if result == "人工通过" and not rel(fp, t.root).startswith(rel(t.evidence, t.root)):
                problem(out, "MAPPING_MANUAL", f"{case} 人工通过的记录应放在证据目录 {rel(t.evidence, t.root)}/", line)
        if not where.strip():
            problem(out, "MAPPING_PATH", f"{case} 没写测试位置", line)
        ok = result in PASS_WORDS
        for cid in re.findall(r"\bT\d+\b", case):
            mapped[cid] = {"ok": ok, "layer": layer}
            if ok and cid in design_cases:
                scene_hits |= design_cases[cid]["scenes"]
        if ok:
            scene_hits |= ce.scene_refs_in_text(case, main)
    for cid, src in sorted(cases_needed.items()):
        if cid not in mapped:
            problem(out, "CASE_UNMAPPED", f"用例 {cid}（{src}）没有对应的测试")
    for sc in sorted(scenes_needed):
        if sc not in scene_hits:
            problem(out, "SCENE_UNCOVERED", f"{ce.scene_label(sc, main)} 没有通过的用例")
    for rid, cases, line in rows_high:
        if not any(mapped.get(c, {}).get("ok") and any(w in mapped[c]["layer"] for w in REAL_LAYERS) for c in cases):
            problem(out, "HIGH_RISK", f"{rid} 是高风险行，要有通过的 smoke / 集成 / e2e 用例", line)


def check_checklist(t: Target) -> list[dict]:
    ce = load_checklist_engine()
    out: list[dict] = []
    for i in ce.validate_issues(t.task_dir):
        problem(out, i["rule"], i["msg"], i["line"])
    cl = ce.parse_checklist(t.doc)
    impact = ce.compute_impact(t.task_dir)
    if impact.get("spec_changes") or impact.get("missing_baseline"):
        problem(out, "SPEC_CHANGED", "拆解基线之后 spec / tech-design 改了（或基线缺失）：按 change-sync 同步后运行 xdev baseline，xdev impact 看明细")
    for r in cl.rows:
        if not (r.status.startswith("[x]") and ("🟢" in r.status or "✅" in r.status)):
            problem(out, "ROW_STATUS", f"{r.id} 状态是 {r.status}，交付要求 [x] 🟢", r.line)
    spec = ce.task_spec_path(t.task_dir)
    main = ce.spec_name_of(spec) if spec else ""
    root = t.root
    td = cl.headers.get("tech-design", ("", 0))[0].strip("` ")
    design_cases: dict = {}
    if td and not td.startswith(("<", "本文件")) and (root / td).is_file():
        design_cases = ce.parse_design((root / td).read_text(encoding="utf-8"), main).cases
    scenes_needed = set()
    scope = cl.headers.get("本轮范围", ("", 0))[0]
    scenes_needed |= ce.scene_refs_in_text(scope, main)
    cases_needed: dict[str, str] = {}
    rows_high = []
    for r in cl.rows:
        try:
            scenes_needed |= set(ce.parse_scene_refs(r.scenes_raw, main))
        except ValueError:
            pass
        for c in r.cases:
            cases_needed.setdefault(c, f"任务行 {r.id}")
        if r.high:
            rows_high.append((r.id, r.cases, r.line))
    for cid, case in design_cases.items():
        if case["scenes"] & scenes_needed:
            cases_needed.setdefault(cid, "tech-design 里回指本轮场景")
    check_mapping(t, cases_needed, scenes_needed, design_cases, rows_high, ce, main, out)
    check_coverage_record(t, out)
    check_feature(t, out)
    return out


def check_qdev(t: Target) -> list[dict]:
    ce = load_checklist_engine()
    out: list[dict] = []
    text = t.text()
    confirm = table_section_line(text, "spec 归属与确认")
    if confirm is None or confirm.startswith("<"):
        problem(out, "SPEC_CONFIRM", "①缺「spec 归属与确认」：写清用户确认的时间和消息位置，或“未写场景，无需确认”")
    cases_needed: dict[str, str] = {}
    for row in table_after(text, "③"):
        kind = col(row, "变化类型")
        for cid in re.findall(r"\bT\d+\b", col(row, "用例")):
            if "删除" not in kind:
                cases_needed[cid] = "③"
    check_mapping(t, cases_needed, set(), {}, [], ce, "", out)
    check_coverage_record(t, out)
    check_feature(t, out)
    return out


def coverage_line(t: Target) -> str:
    try:
        data = json.loads((t.evidence / RECORD).read_text(encoding="utf-8"))
        return f"改动行覆盖率 {data['percent']:g}%（{data['covered']}/{data['total']} 行）"
    except (OSError, ValueError, KeyError):
        return "改动行覆盖率 100%"


def feature_line(t: Target) -> str:
    if not needs_feature_check(t):
        return "不需要功能检查（Q0 或未写场景）"
    try:
        _, issues, _ = parse_feature_receipt((t.evidence / RECEIPT).read_text(encoding="utf-8"))
    except OSError:
        return "功能检查已核对"
    p2 = sum(1 for _, sev in issues if sev == "P2")
    return f"功能检查通过（P2 ×{p2}）"


def table_section_line(text: str, key: str) -> str | None:
    m = re.search(rf"^-\s*{re.escape(key)}\s*[:：]\s*(.*)$", text, re.M)
    return m.group(1).strip() if m else None


def check(raw: str, as_json: bool = False) -> int:
    t = Target(raw)
    out = check_checklist(t) if t.kind == "checklist" else check_qdev(t)
    if as_json:
        print(json.dumps({"target": str(t.doc), "ok": not out, "problems": out}, ensure_ascii=False))
    elif out:
        print(f"❌ 交付检查未通过 · {rel(t.doc, t.root)} · {len(out)} 项")
        for p in out:
            print(f"  [{p['rule']}]" + (f" 第 {p['line']} 行" if p["line"] else "") + f" {p['msg']}")
    else:
        print(f"✅ 交付检查通过 · {rel(t.doc, t.root)} · 编号、状态、场景→用例→测试 · {coverage_line(t)} · {feature_line(t)}")
    return 0 if not out else 1


__all__ = ["start", "coverage", "check", "measure", "UsageError"]
