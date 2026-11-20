#!/usr/bin/env python3
"""当前格式 task 引擎：scaffold / validate / status / graph / impact / baseline。

服务 docs/spec/<spec>/tasks/<task>/dev-checklist.md，父 spec 使用
x-explore-for-spec 的当前模板（`## featNN:` + `场景N:`，没有 spec_version: 3 标记）。
声明 spec_version: 3 的旧契约包仍由同目录的 req.py 处理。

能机械判断的都在这里判断，agent 不用猜：
- validate：头部字段、任务表列、场景 / C / D / 用例编号是否真实存在、文件是否存在、
  并行组硬规则（涉及文件有交集必须同组）、依赖是否存在且无环、risk 是否和任务行一致。
- graph：按并行组和依赖给出派工顺序，并列出"必须合并"的最小分组供参考。
- impact：比较 checklist 记录的拆解基线和当前 spec / tech-design，
  按 change-sync 规则列出受影响的 T、D、任务行和测试文件。
- baseline：同步完成后把当前 spec / tech-design 记为新的拆解基线。

退出码：0 成功；1 校验失败、依赖环或存在未同步变化；2 用法、目标或 IO 错误。
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

CHECKLIST = "dev-checklist.md"
TEMPLATE = Path(__file__).resolve().parent.parent / "templates" / "dev-checklist.md"

REQUIRED_HEADERS = ("spec", "状态", "执行者", "tech-design", "本轮范围", "范围依据", "拆解基线", "risk", "分组理由", "创建")
REQUIRED_COLUMNS = ("#", "任务", "场景回指", "涉及文件", "风险", "并行组", "依赖", "状态")
STATUS_EMOJI = ("⏳", "▶️", "🟡", "🟢", "🔴", "✅", "↗️")
REOPEN_STATUS = "[ ] ⏳"
NONE_WORDS = {"", "none", "无", "-", "—", "n/a"}

FEAT_RE = re.compile(r"^##\s*feat(\d+)\s*[:：]", re.I)
SCENE_RE = re.compile(r"^场景(\d+)\s*[:：]")
C_ROW_RE = re.compile(r"^\|\s*(C\d+)\b")
D_ROW_RE = re.compile(r"^\|\s*(D\d+)\b")
T_ROW_RE = re.compile(r"^\|\s*(T\d+)\b")
ROW_ID_RE = re.compile(r"^T\d+$")
SCENE_REF_RE = re.compile(
    r"(?:(?P<spec>[a-z0-9][a-z0-9-]*)\s*:\s*)?feat(?P<feat>\d+)\s*场景(?P<a>\d+)(?:\s*[-~]\s*(?P<b>\d+))?",
    re.I,
)
BARE_SCENE_RE = re.compile(r"^场景(?P<a>\d+)(?:\s*[-~]\s*(?P<b>\d+))?$")
CASE_REF_RE = re.compile(r"用例\s*((?:T\d+(?:\s*[–~-]\s*T?\d+)?\s*[、,，/\s]*)+)")
D_REF_RE = re.compile(r"\bD\d{2,}\b")
C_REF_RE = re.compile(r"(?<![A-Za-z0-9])C\d+\b")
T_IN_TEXT_RE = re.compile(r"\bT\d+\b")
TEST_FILE_RE = re.compile(r"(^|/)(tests?|__tests__|spec)/|\.test\.|\.spec\.|_test\.|(^|/)test_")
HIGH_RE = re.compile(r"^高")


# ───────────────────────────── 通用解析 ─────────────────────────────

def norm(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def split_cells(line: str) -> list[str]:
    body = line.strip()
    if body.startswith("|"):
        body = body[1:]
    if body.endswith("|"):
        body = body[:-1]
    return [cell.strip() for cell in body.split("|")]


def is_separator(cells: list[str]) -> bool:
    return all(re.fullmatch(r":?-{2,}:?", cell) for cell in cells if cell)


def split_list(cell: str) -> list[str]:
    return [p.strip() for p in re.split(r"[,，、;；]", cell) if p.strip()]


def is_none(cell: str) -> bool:
    return cell.strip().lower() in NONE_WORDS


def spec_name_of(spec_path: Path) -> str:
    return spec_path.parent.name


def parse_scene_refs(cell: str, default_spec: str) -> list[tuple[str, int, int]]:
    """`feat01 场景1, 场景2`、`fine:feat01 场景2-3` → [(spec, feat, scene), ...]。"""
    refs: list[tuple[str, int, int]] = []
    if is_none(cell):
        return refs
    last_spec, last_feat = default_spec, None
    for part in split_list(cell):
        m = SCENE_REF_RE.search(part)
        if m:
            last_spec = (m.group("spec") or default_spec).lower()
            last_feat = int(m.group("feat"))
            a = int(m.group("a"))
            b = int(m.group("b") or a)
        else:
            m2 = BARE_SCENE_RE.match(part)
            if not m2 or last_feat is None:
                raise ValueError(f"无法识别的场景回指：{part}")
            a = int(m2.group("a"))
            b = int(m2.group("b") or a)
        for n in range(a, b + 1):
            refs.append((last_spec, last_feat, n))
    return refs


def scene_refs_in_text(text: str, default_spec: str) -> set[tuple[str, int, int]]:
    """在自由文本里找 `featNN 场景M` 回指（tech-design 的 D / T 行用）。"""
    found: set[tuple[str, int, int]] = set()
    for m in SCENE_REF_RE.finditer(text):
        spec = (m.group("spec") or default_spec).lower()
        feat = int(m.group("feat"))
        a = int(m.group("a"))
        b = int(m.group("b") or a)
        for n in range(a, b + 1):
            found.add((spec, feat, n))
        # 紧跟的 `、场景3` / `, 场景3`
        tail = text[m.end():]
        for extra in re.finditer(r"^\s*[、,，]\s*场景(\d+)(?:\s*[-~]\s*(\d+))?", tail):
            x = int(extra.group(1))
            y = int(extra.group(2) or x)
            for n in range(x, y + 1):
                found.add((spec, feat, n))
            tail = tail[extra.end():]
    return found


def scene_label(ref: tuple[str, int, int], main_spec: str) -> str:
    spec, feat, scene = ref
    prefix = "" if spec == main_spec else f"{spec}:"
    return f"{prefix}feat{feat:02d} 场景{scene}"


# ───────────────────────────── spec / tech-design ─────────────────────────────

@dataclass
class SpecDoc:
    name: str
    scenes: dict[tuple[str, int, int], str] = field(default_factory=dict)
    constraints: dict[str, str] = field(default_factory=dict)


def parse_spec(text: str, name: str) -> SpecDoc:
    doc = SpecDoc(name=name)
    feat = None
    current: tuple[str, int, int] | None = None
    buf: list[str] = []

    def flush() -> None:
        if current is not None:
            doc.scenes[current] = norm("\n".join(buf))

    in_comment = False
    for raw in text.splitlines():
        line = raw.rstrip()
        if "<!--" in line and "-->" not in line:
            in_comment = True
            continue
        if in_comment:
            if "-->" in line:
                in_comment = False
            continue
        if line.startswith("## "):
            flush()
            current, buf = None, []
            m = FEAT_RE.match(line)
            feat = int(m.group(1)) if m else None
            continue
        cm = C_ROW_RE.match(line)
        if cm:
            doc.constraints[cm.group(1)] = norm(line)
            continue
        sm = SCENE_RE.match(line.strip())
        if sm and feat is not None:
            flush()
            current = (name, feat, int(sm.group(1)))
            buf = [line]
            continue
        if current is not None:
            buf.append(line)
    flush()
    return doc


@dataclass
class DesignDoc:
    d_rules: dict[str, dict] = field(default_factory=dict)  # id -> {text, scenes, cs}
    cases: dict[str, dict] = field(default_factory=dict)    # id -> {text, scenes, cs, ds}


def parse_design(text: str, default_spec: str) -> DesignDoc:
    doc = DesignDoc()
    for raw in text.splitlines():
        line = raw.strip()
        if not line.startswith("|"):
            continue
        dm = D_ROW_RE.match(line)
        if dm:
            cells = split_cells(line)
            refs_cell = cells[1] if len(cells) > 1 else ""
            doc.d_rules[dm.group(1)] = {
                "text": norm(line),
                "scenes": scene_refs_in_text(refs_cell, default_spec),
                "cs": set(C_REF_RE.findall(refs_cell)),
            }
            continue
        tm = T_ROW_RE.match(line)
        if tm:
            doc.cases[tm.group(1)] = {
                "text": norm(line),
                "scenes": scene_refs_in_text(line, default_spec),
                "cs": set(C_REF_RE.findall(line)),
                "ds": set(D_REF_RE.findall(line)),
            }
    return doc


# ───────────────────────────── checklist ─────────────────────────────

@dataclass
class Row:
    id: str
    line: int
    task: str
    scenes_raw: str
    files: list[str]
    risk: str
    group: str
    deps: list[str]
    status: str
    cells: list[str]

    @property
    def cases(self) -> set[str]:
        out: set[str] = set()
        for m in CASE_REF_RE.finditer(self.task):
            for rng in re.finditer(r"T(\d+)(?:\s*[–~-]\s*T?(\d+))?", m.group(1)):
                a = int(rng.group(1))
                b = int(rng.group(2) or a)
                out.update(f"T{n}" for n in range(a, b + 1))
        return out

    @property
    def ds(self) -> set[str]:
        return set(D_REF_RE.findall(self.task))

    @property
    def cs(self) -> set[str]:
        return set(C_REF_RE.findall(self.task))

    @property
    def high(self) -> bool:
        return bool(HIGH_RE.match(self.risk.strip()))


@dataclass
class Checklist:
    path: Path
    headers: dict[str, tuple[str, int]]
    columns: list[str]
    rows: list[Row]
    table_line: int
    tree_new: set[str]
    lines: list[str]


TREE_ENTRY_RE = re.compile(
    r"^(?P<lead>[\s│├└─|`-]*)(?P<name>[^\s#]+(?:\s+/\s+[^\s#]+)*)(?:\s+(?P<mark>[UMD]))?\s*(?:#.*)?$"
)


def parse_tree_line(raw: str, stack: list[tuple[int, str]], tree_new: set[str], root_name: str | None = None) -> None:
    """影响文件树一行：支持完整路径写法、按目录缩进的嵌套写法，以及 `a.ts / b.ts` 合并写法。"""
    m = TREE_ENTRY_RE.match(raw.rstrip())
    if not m:
        return
    lead, name, mark = m.group("lead"), m.group("name"), m.group("mark")
    depth = len(lead)
    if not stack and not lead.strip() and depth == 0 and name.endswith("/") and not mark:
        # 第一行无标记的目录：是仓库根就不计入路径；不知道根目录名时两种都认
        stack.append((-1, ""))
        dirname = name.rstrip("/")
        # 仓库目录名常和检出目录名不同，名字对不上时两种都认（只会放宽“文件存在”检查，不会误报）
        if dirname != root_name and dirname not in {"<repo-root>", "repo-root"}:
            stack.append((-1, "?" + dirname))
        return
    while stack and stack[-1][0] >= depth:
        stack.pop()
    pieces = [p.strip() for p in name.split(" / ")]
    parents = [""]
    for _, part in stack:
        if not part:
            continue
        if part.startswith("?"):
            parents = parents + [part[1:]]  # 根可能是这个目录：两种路径都算
        else:
            parents = [f"{pp}/{part}" if pp else part for pp in parents]
    if mark == "U":
        for parent in parents:
            first = f"{parent}/{pieces[0]}" if parent else pieces[0]
            base = first.rsplit("/", 1)[0] if "/" in first else ""
            for x in [first] + [f"{base}/{p}" if base else p for p in pieces[1:]]:
                tree_new.add(x.rstrip("/"))
    if len(pieces) == 1 and name.endswith("/"):
        stack.append((depth, name.rstrip("/")))


def parse_checklist(path: Path) -> Checklist:
    lines = path.read_text(encoding="utf-8").splitlines()
    root_name = find_root(path.resolve().parent).name
    headers: dict[str, tuple[str, int]] = {}
    columns: list[str] = []
    rows: list[Row] = []
    table_line = 0
    tree_new: set[str] = set()
    in_comment = False
    in_tree = False
    tree_stack: list[tuple[int, str]] = []
    for idx, raw in enumerate(lines, 1):
        line = raw.strip()
        if line.startswith("<!--"):
            in_comment = "-->" not in line
            continue
        if in_comment:
            if "-->" in line:
                in_comment = False
            continue
        if line.startswith("```"):
            in_tree = not in_tree
            tree_stack: list[tuple[int, str]] = []
            continue
        if in_tree:
            parse_tree_line(raw, tree_stack, tree_new, root_name)
            continue
        hm = re.match(r"^>\s*([^:：]+?)\s*[:：]\s*(.*)$", line)
        if hm and not columns:
            headers[hm.group(1).strip()] = (hm.group(2).strip(), idx)
            continue
        if line.startswith("|"):
            cells = split_cells(line)
            if not columns:
                columns = cells
                table_line = idx
                continue
            if is_separator(cells):
                continue
            col = {name: i for i, name in enumerate(columns)}

            def get(name: str) -> str:
                i = col.get(name)
                return cells[i] if i is not None and i < len(cells) else ""

            rows.append(Row(
                id=get("#"),
                line=idx,
                task=get("任务"),
                scenes_raw=get("场景回指"),
                files=[f.strip("` ") for f in split_list(get("涉及文件"))],
                risk=get("风险"),
                group=get("并行组"),
                deps=[] if is_none(get("依赖")) else split_list(get("依赖")),
                status=get("状态"),
                cells=cells,
            ))
    return Checklist(path, headers, columns, rows, table_line, tree_new, lines)


def computed_risk(rows: list[Row]) -> str:
    highs = sum(1 for r in rows if r.high)
    if highs >= 2:
        return "Q3"
    if highs == 1:
        return "Q2"
    if any(not is_none(r.scenes_raw) for r in rows):
        return "Q1"
    return "Q0"


# ───────────────────────────── 路径与仓库 ─────────────────────────────

def find_root(start: Path) -> Path:
    for p in [start, *start.parents]:
        if (p / ".git").exists() or (p / "docs" / "spec").is_dir():
            return p
    return start


def is_v3_spec(spec_path: Path) -> bool:
    try:
        text = spec_path.read_text(encoding="utf-8")
    except OSError:
        return False
    return bool(re.search(r"^>\s*spec_version:\s*3\s*$", text, re.M))


def task_spec_path(task_dir: Path) -> Path | None:
    """docs/spec/<spec>/tasks/<task>/ → docs/spec/<spec>/spec.md。"""
    task_dir = task_dir.resolve()
    if task_dir.parent.name != "tasks":
        return None
    spec = task_dir.parent.parent / "spec.md"
    return spec if spec.parent.parent.name == "spec" else None


def has_version_marker(spec_path: Path) -> bool:
    try:
        text = spec_path.read_text(encoding="utf-8")
    except OSError:
        return False
    return bool(re.search(r"^>\s*spec_version:", text, re.M))


def handles(task_dir: Path) -> bool:
    """当前模板的 spec 没有 spec_version 标记；带标记的是旧契约包（v3 由 req.py 处理，其他已废除）。"""
    spec = task_spec_path(task_dir)
    return spec is not None and spec.is_file() and not has_version_marker(spec)


def rel(path: Path, root: Path) -> str:
    try:
        return str(path.resolve().relative_to(root.resolve()))
    except ValueError:
        return str(path)


def git(root: Path, *args: str, stdin: str | None = None) -> str:
    out = subprocess.run(
        ["git", "-C", str(root), *args],
        input=stdin, capture_output=True, text=True, check=True,
    )
    return out.stdout


def store_blob(root: Path, path: Path) -> str:
    """把文件内容写进 git 对象库并返回短哈希，以后可以取回旧内容做比较。"""
    return git(root, "hash-object", "-w", str(path.resolve())).strip()[:12]


def read_blob(root: Path, blob: str) -> str:
    return git(root, "cat-file", "-p", blob)


def parse_baseline(value: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for part in re.split(r"\s*·\s*", value):
        if "@" in part:
            p, h = part.rsplit("@", 1)
            out[p.strip().strip("`")] = h.strip()
    return out


def involved_docs(task_dir: Path, cl: Checklist, root: Path) -> list[Path]:
    docs: list[Path] = []
    spec = task_spec_path(task_dir)
    if spec:
        docs.append(spec)
    other = cl.headers.get("其他 spec", ("", 0))[0]
    if not other.startswith("<"):
        for p in split_list(other):
            if p.strip():
                docs.append((root / p.strip("` ")).resolve())
    td = cl.headers.get("tech-design", ("", 0))[0].strip("` ")
    if td and not td.startswith("<") and not td.startswith("本文件"):
        docs.append((root / td).resolve())
    return docs


# ───────────────────────────── validate ─────────────────────────────

def issue(file: str, line: int, rule: str, msg: str) -> dict:
    return {"file": file, "line": line, "rule": rule, "msg": msg}


def _segments(path: str) -> list[str]:
    return [p for p in path.strip("/").split("/") if p]


def files_overlap(a: str, b: str) -> bool:
    """按路径段比较：同一个文件、一个是另一个的上级目录，或 glob 能匹配到对方时算重叠。"""
    from fnmatch import fnmatch

    a, b = a.rstrip("/"), b.rstrip("/")
    if a == b:
        return True
    if "*" in a or "*" in b:
        sa, sb = _segments(a), _segments(b)
        if "**" in sa or "**" in sb:
            # ** 可以跨任意多层：只比较 ** 之前的部分
            ka = sa.index("**") if "**" in sa else len(sa)
            kb = sb.index("**") if "**" in sb else len(sb)
            n = min(ka, kb)
        else:
            n = min(len(sa), len(sb))
        return all(fnmatch(x, y) or fnmatch(y, x) for x, y in zip(sa[:n], sb[:n]))
    sa, sb = _segments(a), _segments(b)
    shorter, longer = (sa, sb) if len(sa) <= len(sb) else (sb, sa)
    return longer[: len(shorter)] == shorter


def must_merge_groups(rows: list[Row]) -> list[list[str]]:
    """按涉及文件有无交集求最小分组（并查集）。"""
    parent = {r.id: r.id for r in rows}

    def find(x: str) -> str:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for i, a in enumerate(rows):
        for b in rows[i + 1:]:
            if any(files_overlap(fa, fb) for fa in a.files for fb in b.files):
                parent[find(a.id)] = find(b.id)
    groups: dict[str, list[str]] = {}
    for r in rows:
        groups.setdefault(find(r.id), []).append(r.id)
    return list(groups.values())


def group_order(rows: list[Row]) -> tuple[list[list[str]], list[str]]:
    """返回 (派工批次，每批若干组；环里的组)。"""
    groups = list(dict.fromkeys(r.group for r in rows))
    by_id = {r.id: r for r in rows}
    edges: dict[str, set[str]] = {g: set() for g in groups}
    for r in rows:
        for d in r.deps:
            dep = by_id.get(d)
            if dep and dep.group != r.group:
                edges[r.group].add(dep.group)
    waves: list[list[str]] = []
    done: set[str] = set()
    remaining = set(groups)
    while remaining:
        ready = [g for g in groups if g in remaining and edges[g] <= done]
        if not ready:
            return waves, sorted(remaining)
        waves.append(ready)
        done.update(ready)
        remaining.difference_update(ready)
    return waves, []


def validate_issues(task_dir: Path) -> list[dict]:
    task_dir = Path(task_dir)
    path = task_dir / CHECKLIST
    f = str(path)
    if not path.is_file():
        return [issue(f, 0, "TASK_FILE", "缺少 dev-checklist.md")]
    root = find_root(task_dir.resolve())
    cl = parse_checklist(path)
    out: list[dict] = []

    # 头部
    other = cl.headers.get("其他 spec")
    if other and other[0].startswith("<"):
        out.append(issue(f, other[1], "HEADER", "“其他 spec”还是占位符：跨 spec 时填路径，不跨时删掉这一行"))
    for key in REQUIRED_HEADERS:
        value = cl.headers.get(key)
        if value is None or not value[0] or value[0].startswith("<"):
            out.append(issue(f, value[1] if value else 0, "HEADER", f"头部缺少或未填写：{key}"))
    spec = task_spec_path(task_dir)
    declared = cl.headers.get("spec", ("", 0))
    if spec and declared[0] and not declared[0].startswith("<"):
        if (root / declared[0].strip("` ")).resolve() != spec.resolve():
            out.append(issue(f, declared[1], "HEADER_SPEC", f"spec 应指向 task 所在的 {rel(spec, root)}"))

    # 列
    missing = [c for c in REQUIRED_COLUMNS if c not in cl.columns]
    if missing:
        out.append(issue(f, cl.table_line, "COLUMNS", f"任务表缺少列：{'、'.join(missing)}"))
        return out
    if not cl.rows:
        out.append(issue(f, cl.table_line, "ROWS", "任务表没有任务行"))
        return out

    # 被引用文档
    main = spec_name_of(spec) if spec else ""
    specs: dict[str, SpecDoc] = {}
    for doc in involved_docs(task_dir, cl, root):
        if doc.name == "spec.md" and doc.is_file():
            specs[spec_name_of(doc)] = parse_spec(doc.read_text(encoding="utf-8"), spec_name_of(doc))
    design: DesignDoc | None = None
    td = cl.headers.get("tech-design", ("", 0))
    td_path = (root / td[0].strip("` ")) if td[0] and not td[0].startswith(("<", "本文件")) else None
    if td_path is not None:
        if td_path.is_file():
            design = parse_design(td_path.read_text(encoding="utf-8"), main)
        else:
            out.append(issue(f, td[1], "HEADER_TD", f"tech-design 文件不存在：{td[0]}"))

    seen: set[str] = set()
    ids = {r.id for r in cl.rows}
    for r in cl.rows:
        if not ROW_ID_RE.match(r.id):
            out.append(issue(f, r.line, "ROW_ID", f"任务行编号应为 T1、T2…：{r.id}"))
        if r.id in seen:
            out.append(issue(f, r.line, "ROW_ID", f"任务行编号重复：{r.id}"))
        seen.add(r.id)
        # 场景回指
        try:
            refs = parse_scene_refs(r.scenes_raw, main)
        except ValueError as e:
            out.append(issue(f, r.line, "SCENE_REF", str(e)))
            refs = []
        for ref in refs:
            doc = specs.get(ref[0])
            if doc is None:
                out.append(issue(f, r.line, "SCENE_REF", f"{scene_label(ref, main)}：找不到 {ref[0]} 的 spec，跨 spec 时在头部“其他 spec”列出"))
            elif ref not in doc.scenes:
                out.append(issue(f, r.line, "SCENE_REF", f"spec 里没有 {scene_label(ref, main)}"))
        # C / D / 用例
        for c in sorted(r.cs):
            if specs.get(main) and c not in specs[main].constraints:
                out.append(issue(f, r.line, "C_REF", f"spec 里没有约束 {c}"))
        if design is not None:
            for d in sorted(r.ds):
                if d not in design.d_rules:
                    out.append(issue(f, r.line, "D_REF", f"tech-design 里没有 {d}"))
            for t in sorted(r.cases):
                if t not in design.cases:
                    out.append(issue(f, r.line, "CASE_REF", f"tech-design 里没有用例 {t}"))
        # 文件
        if not r.files:
            out.append(issue(f, r.line, "FILES", "涉及文件为空"))
        for p in r.files:
            if "*" in p or p in cl.tree_new or p.rstrip("/") in cl.tree_new:
                continue
            if not (root / p).exists():
                out.append(issue(f, r.line, "FILES", f"文件不存在，也没有在影响文件树标 U：{p}"))
        # 风险、组、状态
        if not (is_none(r.risk) or r.high):
            out.append(issue(f, r.line, "RISK_CELL", f"风险列只能是 None 或 高:<依据>：{r.risk}"))
        if is_none(r.group):
            out.append(issue(f, r.line, "GROUP", "并行组为空"))
        if not any(e in r.status for e in STATUS_EMOJI):
            out.append(issue(f, r.line, "STATUS", f"无法识别的状态：{r.status}"))
        for d in r.deps:
            if d not in ids:
                out.append(issue(f, r.line, "DEP", f"依赖的任务行不存在：{d}"))
            elif d == r.id:
                out.append(issue(f, r.line, "DEP", "任务行不能依赖自己"))

    # 并行组硬规则：涉及文件有交集必须同组
    by_id = {r.id: r for r in cl.rows}
    for i, a in enumerate(cl.rows):
        for b in cl.rows[i + 1:]:
            shared = [fa for fa in a.files for fb in b.files if files_overlap(fa, fb)]
            if shared and a.group != b.group:
                out.append(issue(f, b.line, "GROUP_OVERLAP",
                                 f"{a.id} 与 {b.id} 都改 {shared[0]}，必须在同一并行组（现在是 {a.group} / {b.group}）"))
    # 同组内依赖只能指向前面的行
    order = {r.id: i for i, r in enumerate(cl.rows)}
    for r in cl.rows:
        for d in r.deps:
            dep = by_id.get(d)
            if dep and dep.group == r.group and order[d] > order[r.id]:
                out.append(issue(f, r.line, "DEP_ORDER", f"同组内 {r.id} 依赖的 {d} 排在它后面，调换行序"))
    _, cycle = group_order(cl.rows)
    if cycle:
        out.append(issue(f, cl.table_line, "DEP_CYCLE", f"并行组之间的依赖有环：{'、'.join(cycle)}"))

    # risk 与任务行一致
    risk = cl.headers.get("risk")
    expected = computed_risk(cl.rows)
    if risk and risk[0] and not risk[0].startswith("<") and risk[0].split()[0] != expected:
        out.append(issue(f, risk[1], "RISK", f"risk 应为 {expected}（按任务行：高风险行数和场景回指算出），现在是 {risk[0]}"))

    # 拆解基线格式
    base = cl.headers.get("拆解基线")
    if base and base[0] and not base[0].startswith("<"):
        parsed = parse_baseline(base[0])
        for doc in involved_docs(task_dir, cl, root):
            if rel(doc, root) not in parsed:
                out.append(issue(f, base[1], "BASELINE", f"拆解基线缺少 {rel(doc, root)}，运行 xdev baseline 生成"))
    return out


# ───────────────────────────── scaffold / baseline ─────────────────────────────

def baseline_value(task_dir: Path, cl: Checklist | None, root: Path, extra: list[Path] | None = None) -> str:
    docs = involved_docs(task_dir, cl, root) if cl else []
    if not docs:
        spec = task_spec_path(task_dir)
        docs = [spec] if spec else []
        td = spec.parent / "tech-design.md" if spec else None
        if td and td.is_file():
            docs.append(td)
    for e in extra or []:
        if e not in docs:
            docs.append(e)
    parts = [f"{rel(d, root)}@{store_blob(root, d)}" for d in docs if d.is_file()]
    return " · ".join(parts)


def scaffold(task_dir: Path, as_json: bool = False) -> int:
    task_dir = Path(task_dir)
    spec = task_spec_path(task_dir)
    if spec is None or not spec.is_file():
        print(f"错误：task 必须位于 docs/spec/<spec>/tasks/<task>/，且上级有 spec.md：{task_dir}", file=sys.stderr)
        return 2
    task_dir.mkdir(parents=True, exist_ok=True)
    target = task_dir / CHECKLIST
    created = False
    if not target.exists():
        root = find_root(task_dir.resolve())
        text = TEMPLATE.read_text(encoding="utf-8")
        td = spec.parent / "tech-design.md"
        text = text.replace("<task-name>", task_dir.name)
        text = text.replace("docs/spec/<spec-name>/spec.md", rel(spec, root))
        text = text.replace("docs/spec/<spec-name>/tech-design.md", rel(td, root) if td.is_file() else "<tech-design 路径>")
        text = text.replace("YYYY-MM-DD", date.today().isoformat())
        try:
            base = baseline_value(task_dir, None, root)
            text = re.sub(r"^(>\s*拆解基线\s*[:：]).*$", lambda m: f"{m.group(1)}{base}", text, flags=re.M)
        except (subprocess.CalledProcessError, FileNotFoundError):
            pass
        target.write_text(text, encoding="utf-8")
        created = True
    result = {"task": str(task_dir), "checklist": str(target), "created": created}
    print(json.dumps(result, ensure_ascii=False) if as_json else
          (f"已创建 {target}" if created else f"已存在，未覆盖：{target}"))
    return 0


def baseline(task_dir: Path, as_json: bool = False) -> int:
    path = Path(task_dir) / CHECKLIST
    if not path.is_file():
        print(f"错误：缺少 {path}", file=sys.stderr)
        return 2
    root = find_root(Path(task_dir).resolve())
    cl = parse_checklist(path)
    try:
        value = baseline_value(Path(task_dir), cl, root)
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        print(f"错误：需要 git 仓库来保存基线：{e}", file=sys.stderr)
        return 2
    text = path.read_text(encoding="utf-8")
    if re.search(r"^>\s*拆解基线\s*[:：]", text, re.M):
        text = re.sub(r"^(>\s*拆解基线\s*[:：]).*$", lambda m: f"{m.group(1)}{value}", text, count=1, flags=re.M)
    else:
        text = re.sub(r"^(>\s*创建\s*[:：].*)$", lambda m: f"> 拆解基线：{value}\n{m.group(1)}", text, count=1, flags=re.M)
    path.write_text(text, encoding="utf-8")
    print(json.dumps({"baseline": value}, ensure_ascii=False) if as_json else f"拆解基线已更新：{value}")
    return 0


# ───────────────────────────── status / graph ─────────────────────────────

def status(task_dir: Path, as_json: bool = False) -> int:
    path = Path(task_dir) / CHECKLIST
    if not path.is_file():
        print(f"错误：缺少 {path}", file=sys.stderr)
        return 2
    cl = parse_checklist(path)
    counts: dict[str, int] = {}
    for r in cl.rows:
        key = next((e for e in STATUS_EMOJI if e in r.status), "?")
        counts[key] = counts.get(key, 0) + 1
    done = counts.get("🟢", 0) + counts.get("✅", 0)
    result = {
        "task": str(task_dir),
        "rows": [{"id": r.id, "group": r.group, "status": r.status} for r in cl.rows],
        "counts": counts,
        "done": done,
        "total": len(cl.rows),
        "risk": cl.headers.get("risk", ("", 0))[0],
    }
    if as_json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"{Path(task_dir).name}：{done}/{len(cl.rows)} 完成 · risk {result['risk'] or '未填'}")
        for r in cl.rows:
            print(f"  {r.id} [{r.group}] {r.status}")
    return 0


def graph(task_dir: Path, as_json: bool = False) -> int:
    path = Path(task_dir) / CHECKLIST
    if not path.is_file():
        print(f"错误：缺少 {path}", file=sys.stderr)
        return 2
    cl = parse_checklist(path)
    waves, cycle = group_order(cl.rows)
    groups: dict[str, dict] = {}
    for r in cl.rows:
        g = groups.setdefault(r.group, {"rows": [], "files": []})
        g["rows"].append(r.id)
        for p in r.files:
            if p not in g["files"]:
                g["files"].append(p)
    result = {
        "groups": groups,
        "waves": waves,
        "cycle": cycle,
        "must_merge": must_merge_groups(cl.rows),
    }
    if as_json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        for i, wave in enumerate(waves, 1):
            print(f"第 {i} 批（可同时派）：")
            for g in wave:
                print(f"  组 {g}：{'、'.join(groups[g]['rows'])} · 文件 {'、'.join(groups[g]['files'])}")
        if cycle:
            print(f"依赖有环，无法排序：{'、'.join(cycle)}")
        print("按文件交集算出的最小分组（必须同组的行）：" + "；".join("、".join(m) for m in result["must_merge"]))
    return 1 if cycle else 0


# ───────────────────────────── impact ─────────────────────────────

def _diff(old: dict, new: dict) -> tuple[set, set, set]:
    changed = {k for k in old if k in new and old[k] != new[k]}
    return changed, set(new) - set(old), set(old) - set(new)


def compute_impact(task_dir: Path) -> dict:
    task_dir = Path(task_dir)
    path = task_dir / CHECKLIST
    root = find_root(task_dir.resolve())
    cl = parse_checklist(path)
    spec = task_spec_path(task_dir)
    main = spec_name_of(spec) if spec else ""
    base = parse_baseline(cl.headers.get("拆解基线", ("", 0))[0])

    spec_changes: list[dict] = []
    changed_scenes: set = set()
    added_scenes: set = set()
    removed_scenes: set = set()
    changed_cs: set = set()
    old_design = new_design = None
    missing: list[str] = []

    for doc in involved_docs(task_dir, cl, root):
        key = rel(doc, root)
        blob = base.get(key)
        if not blob:
            missing.append(key)
            continue
        old_text = read_blob(root, blob)
        new_text = doc.read_text(encoding="utf-8") if doc.is_file() else ""
        if doc.name == "spec.md":
            name = spec_name_of(doc)
            o, n = parse_spec(old_text, name), parse_spec(new_text, name)
            ch, add, rem = _diff(o.scenes, n.scenes)
            cch, cadd, crem = _diff(o.constraints, n.constraints)
            changed_scenes |= ch
            added_scenes |= add
            removed_scenes |= rem
            if name == main:
                changed_cs |= cch | crem
            for k in sorted(ch):
                spec_changes.append({"item": scene_label(k, main), "change": "改"})
            for k in sorted(add):
                spec_changes.append({"item": scene_label(k, main), "change": "新增"})
            for k in sorted(rem):
                spec_changes.append({"item": scene_label(k, main), "change": "删除"})
            for c in sorted(cch | cadd | crem):
                spec_changes.append({"item": c, "change": "改" if c in cch else ("新增" if c in cadd else "删除")})
        else:
            old_design, new_design = parse_design(old_text, main), parse_design(new_text, main)

    design = new_design or old_design or DesignDoc()
    before = old_design or design
    actions: dict[str, dict] = {}

    def put(item: str, action: str, reason: str, judge: bool = False) -> None:
        prev = actions.get(item)
        rank = {"退役": 3, "改": 2, "新增": 2, "重开": 1, "重跑": 0, "判断": 0}
        if prev is None or rank.get(action, 0) > rank.get(prev["action"], 0):
            actions[item] = {"item": item, "action": action, "reason": reason, "judge": judge}

    touched_scenes = changed_scenes | removed_scenes
    # T：引用改动或删除场景、改动 C 的用例
    for tid, case in before.cases.items():
        hit = case["scenes"] & touched_scenes
        hit_c = case["cs"] & changed_cs
        if not hit and not hit_c:
            continue
        only_removed = case["scenes"] and case["scenes"] <= removed_scenes
        if only_removed:
            put(tid, "退役", "只为已删除的场景存在")
        else:
            why = "、".join(sorted(scene_label(s, main) for s in hit) + sorted(hit_c))
            put(tid, "改", f"回指的 {why} 变了，改预期或操作")
    for s in sorted(added_scenes):
        put(f"新T（{scene_label(s, main)}）", "新增", "新增场景至少要有一条用例")
    for s in sorted(removed_scenes):
        put(f"新T（{scene_label(s, main)} 移除后）", "新增", "验证移除后的行为")
    # D：引用改动场景 / C 的要判断是否仍成立；只为删除场景存在的退役
    changed_ds: set[str] = set()
    if old_design and new_design:
        dch, _, drem = _diff({k: v["text"] for k, v in old_design.d_rules.items()},
                             {k: v["text"] for k, v in new_design.d_rules.items()})
        changed_ds = dch
        for d in sorted(dch):
            put(d, "改", "tech-design 里这条 D 已改")
        for d in sorted(drem):
            put(d, "退役", "tech-design 里这条 D 已删")
    for did, rule in before.d_rules.items():
        if did in actions:
            continue
        hit = rule["scenes"] & changed_scenes
        hit_c = rule["cs"] & changed_cs
        if rule["scenes"] and rule["scenes"] <= removed_scenes:
            put(did, "退役", "只为已删除的场景存在")
        elif hit or hit_c:
            why = "、".join(sorted(scene_label(s, main) for s in hit) + sorted(hit_c))
            put(did, "判断", f"回指的 {why} 变了：新行为下这条约束还成立就不动，不成立就改", judge=True)
    # D 改了：引用它的 T 要看预期
    for tid, case in design.cases.items():
        if case["ds"] & changed_ds and tid not in actions:
            put(tid, "判断", f"引用的 {'、'.join(sorted(case['ds'] & changed_ds))} 改了，预期变了才改", judge=True)

    # 任务行与测试文件
    changed_t = {a["item"] for a in actions.values() if a["action"] in {"改", "退役"} and a["item"].startswith("T")}
    new_feats = {(s[0], s[1]) for s in added_scenes}
    reopened: set[str] = set()
    for r in cl.rows:
        try:
            refs = set(parse_scene_refs(r.scenes_raw, main))
        except ValueError:
            refs = set()
        reason = []
        if r.cases & changed_t:
            reason.append("用例 " + "、".join(sorted(r.cases & changed_t)) + " 要改或退役")
        if r.ds & changed_ds:
            reason.append("D " + "、".join(sorted(r.ds & changed_ds)) + " 已改，共用实现可能变")
        if refs & touched_scenes:
            reason.append("回指的场景变了")
        if {(s[0], s[1]) for s in refs} & new_feats:
            reason.append("同一 feat 新增了场景，放进这一行")
        if reason:
            put(f"任务行 {r.id}", "重开", "；".join(reason))
            reopened.add(r.id)
    if new_feats and not any({(s[0], s[1]) for s in _safe_refs(r, main)} & new_feats for r in cl.rows):
        put("新任务行", "新增", "新增场景没有承接同一 feat 的已有任务行")
    for r in cl.rows:
        if r.id not in reopened:
            continue
        edits = bool(r.cases & changed_t) or bool(refs_new(r, main) & new_feats) or bool(set(_safe_refs(r, main)) & touched_scenes)
        for p in r.files:
            if TEST_FILE_RE.search(p):
                put(p, "改" if edits else "重跑", f"任务行 {r.id} 的测试文件")

    items = sorted(actions.values(), key=lambda a: (a["item"].startswith("tests") or "/" in a["item"], a["item"]))
    return {"spec_changes": spec_changes, "actions": items, "missing_baseline": missing}


def _safe_refs(r: Row, main: str) -> list[tuple[str, int, int]]:
    try:
        return parse_scene_refs(r.scenes_raw, main)
    except ValueError:
        return []


def refs_new(r: Row, main: str) -> set[tuple[str, int]]:
    return {(s[0], s[1]) for s in _safe_refs(r, main)}


def impact(task_dir: Path, as_json: bool = False) -> int:
    path = Path(task_dir) / CHECKLIST
    if not path.is_file():
        print(f"错误：缺少 {path}", file=sys.stderr)
        return 2
    try:
        result = compute_impact(Path(task_dir))
    except subprocess.CalledProcessError as e:
        print(f"错误：读取基线失败（需要 git，且基线由 xdev baseline 写入）：{e.stderr.strip()}", file=sys.stderr)
        return 2
    dirty = bool(result["spec_changes"] or result["actions"] or result["missing_baseline"])
    if as_json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        if result["missing_baseline"]:
            print("拆解基线里没有这些文件，先运行 xdev baseline：" + "、".join(result["missing_baseline"]))
        if not result["spec_changes"] and not result["actions"]:
            if not result["missing_baseline"]:
                print("拆解基线之后 spec 和 tech-design 没有变化，可以开工。")
        else:
            print("spec 变化：" + ("；".join(f"{c['item']} {c['change']}" for c in result["spec_changes"]) or "无（只有 tech-design 变化）"))
            print("按 change-sync 需要处理：")
            for a in result["actions"]:
                mark = "（需判断）" if a["judge"] else ""
                print(f"  {a['item']}：{a['action']}{mark} · {a['reason']}")
            print("全部同步后运行 xdev baseline 记录新基线。只是措辞变化、行为没变时，不用改下游，直接记新基线。")
    return 1 if dirty else 0
