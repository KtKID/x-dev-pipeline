#!/usr/bin/env python3
"""x-code-audit 的机械部分。

  audit.py start [--module DIR]... [--layers L1,L2,...] [--full] [--root DIR]
      生成 8 位检查 ID，定范围，写报告骨架 reports/audit/audit-<ID>.md，列出检查单位。
  audit.py l1|l2|l3|l5 <ID>     跑这一层的脚本部分，结果写进报告；需要 AI 的部分登记成新单位。
  audit.py scripts <ID>         按顺序跑完范围内的 l1、l2、l3、l5。
  audit.py units <ID>           列出还没做的子 agent 单位（派工用）。
  audit.py merge <ID>           把 reports/audit/audit-<ID>.parts/ 里的回执合进报告，问题按 P0→P2 排序编号。
  audit.py verify <ID>          核对报告：每个单位都查了、检查项都有结论、代码位置真实存在。

只用标准库。退出码：0 成功，1 核对不过或有单位出错，2 用法错误。
"""
from __future__ import annotations

import argparse
import ast
import datetime as dt
import json
import re
import secrets
import shutil
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

LAYERS = ["L1", "L2", "L3", "L4", "L5", "L6"]
LAYER_NAMES = {"L1": "机器检查", "L2": "死代码", "L3": "文档对代码", "L4": "模块审查", "L5": "架构审查", "L6": "性能"}
CODE_EXT = {".py", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".go", ".cs", ".java", ".kt", ".rs", ".rb", ".php"}
SKIP_DIRS = {".git", "node_modules", "reports", "docs", "evals", "dist", "build", ".venv", "venv", "__pycache__",
             ".pytest_cache", ".mypy_cache", ".ruff_cache", "coverage", ".cov"}
MODULE_ROOTS = {"src", "lib", "packages", "apps", "pkg", "internal", "cmd"}
CHECK_ITEMS = {
    "L3": ["功能描述对得上", "使用方式能用", "关键函数说明对得上", "spec 索引还对"],
    "L4": ["职责单一", "对外接口说清楚", "错误情况处理清楚", "测试真在测"],
    "L5": ["同一信息只在一处维护", "模块放对地方", "没有绕过既有抽象", "以前定的约束还守着", "没有多余的抽象"],
    "L6": ["循环里没有查库或调接口", "没有重复计算", "数据结构用得合适", "没有不必要的等待", "资源用完会释放"],
}
RESULTS = {"没问题", "有问题", "没法判断"}
SEVERITIES = ["P0", "P1", "P2"]
ISSUE_FIELDS = ["是什么", "影响", "位置", "证据"]
ENTRY_DECORATOR = re.compile(r"route|command|fixture|register|app\.|router|task|listener|hook|cli|click|typer|"
                             r"get|post|put|delete|patch|subscribe|handler", re.I)


class UsageError(Exception):
    pass


# ---------- 通用 ----------

def run(cmd: list[str], cwd: Path, timeout: int = 600) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout)
    except FileNotFoundError:
        return subprocess.CompletedProcess(cmd, 127, "", f"找不到命令 {cmd[0]}")
    except subprocess.TimeoutExpired:
        return subprocess.CompletedProcess(cmd, 124, "", "超时")


def git(root: Path, *args: str) -> str | None:
    r = run(["git", *args], root)
    return r.stdout.strip() if r.returncode == 0 else None


def find_root(arg: str | None) -> Path:
    if arg:
        return Path(arg).resolve()
    top = git(Path.cwd(), "rev-parse", "--show-toplevel")
    return Path(top) if top else Path.cwd()


def is_code(path: Path) -> bool:
    return path.suffix in CODE_EXT


def is_test(rel: str) -> bool:
    name = Path(rel).name
    parts = Path(rel).parts
    return ("tests" in parts or "test" in parts or "__tests__" in parts or name.startswith("test_")
            or name.endswith("_test.py") or name.endswith("_test.go") or ".test." in name or ".spec." in name)


def all_files(root: Path) -> list[str]:
    out = []
    for p in root.rglob("*"):
        rel = p.relative_to(root)
        if p.is_file() and not (set(rel.parts[:-1]) & SKIP_DIRS) and not rel.parts[0].endswith(".orig"):
            out.append(rel.as_posix())
    return sorted(out)


def code_files(root: Path) -> list[str]:
    return [f for f in all_files(root) if is_code(Path(f))]


def readme_in(root: Path, d: str) -> str | None:
    for name in ("readme.md", "README.md", "Readme.md"):
        if (root / d / name).is_file():
            return (Path(d) / name).as_posix() if d != "." else name
    return None


def module_of(root: Path, rel: str) -> str:
    parts = Path(rel).parts[:-1]
    for i in range(len(parts), 0, -1):
        d = "/".join(parts[:i])
        if readme_in(root, d):
            return d
    return "/".join(parts) if parts else "."


def now() -> str:
    return dt.datetime.now().strftime("%Y-%m-%d %H:%M")


def table(headers: list[str], rows: list[list[str]]) -> str:
    def cell(x) -> str:
        return str(x).replace("|", "\\|").replace("\n", " ")
    lines = ["| " + " | ".join(headers) + " |", "|" + "---|" * len(headers)]
    lines += ["| " + " | ".join(cell(c) for c in r) + " |" for r in rows]
    return "\n".join(lines)


def parse_table(text: str, required: tuple[str, ...]) -> tuple[list[str], list[list[str]]] | None:
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        if not lines[i].lstrip().startswith("|"):
            i += 1
            continue
        block = []
        while i < len(lines) and lines[i].lstrip().startswith("|"):
            block.append([c.strip().replace("\\|", "|") for c in re.split(r"(?<!\\)\|", lines[i].strip().strip("|"))])
            i += 1
        if len(block) >= 2 and all(h in block[0] for h in required):
            return block[0], [r for r in block[2:] if len(r) == len(block[0])]
    return None


# ---------- 报告读写 ----------

class Report:
    SECTIONS = ["范围", "结论", "问题", "检查进度", "检查记录"]

    def __init__(self, root: Path, audit_id: str):
        if not re.fullmatch(r"[0-9a-f]{8}", audit_id):
            raise UsageError(f"检查 ID 要是 8 位十六进制：{audit_id}")
        self.root, self.id = root, audit_id
        self.path = root / "reports/audit" / f"audit-{audit_id}.md"
        self.parts = root / "reports/audit" / f"audit-{audit_id}.parts"
        if not self.path.exists():
            raise UsageError(f"没有这份报告：{self.path}")
        self.text = self.path.read_text(encoding="utf-8")

    def header(self, key: str) -> str | None:
        m = re.search(rf"^> {re.escape(key)}：(.*)$", self.text, re.M)
        return m.group(1).strip() if m else None

    def set_header(self, key: str, value: str) -> None:
        self.text = re.sub(rf"^> {re.escape(key)}：.*$", f"> {key}：{value}", self.text, count=1, flags=re.M)

    def section(self, name: str) -> str:
        m = re.search(rf"^## {re.escape(name)}\s*$\n([\s\S]*?)(?=^## |\Z)", self.text, re.M)
        return m.group(1) if m else ""

    def set_section(self, name: str, body: str) -> None:
        body = body.strip("\n") + "\n\n"
        body = re.sub(r"\n{3,}", "\n\n", body)
        pat = re.compile(rf"(^## {re.escape(name)}\s*$\n)([\s\S]*?)(?=^## |\Z)", re.M)
        self.text = pat.sub(lambda m: m.group(1) + "\n" + body, self.text, count=1)
        self.text = re.sub(r"(^## [^\n]*\n)\n{2,}", r"\1\n", self.text, flags=re.M)

    def save(self) -> None:
        self.path.write_text(self.text, encoding="utf-8")

    # 检查进度
    def units(self) -> list[dict]:
        t = parse_table(self.section("检查进度"), ("单位", "层", "范围", "谁查", "状态"))
        if not t:
            return []
        h, rows = t
        return [dict(zip(h, r)) for r in rows]

    def write_units(self, units: list[dict], files: list[str] | None = None) -> None:
        old = self.section("检查进度")
        tail = old.split("\n范围内的文件：", 1)[1] if "\n范围内的文件：" in old else None
        body = table(["单位", "层", "范围", "谁查", "状态"],
                     [[u["单位"], u["层"], u["范围"], u["谁查"], u["状态"]] for u in units])
        if files is not None:
            body += "\n\n范围内的文件：" + ("、".join(f"`{f}`" for f in files) if files else "无")
        elif tail is not None:
            body += "\n\n范围内的文件：" + tail.strip()
        self.set_section("检查进度", body)

    def add_unit(self, layer: str, scope: str, who: str) -> str:
        units = self.units()
        uid = f"U{len(units) + 1}"
        units.append({"单位": uid, "层": layer, "范围": scope, "谁查": who, "状态": "待查"})
        self.write_units(units)
        return uid

    def set_unit_status(self, uid: str, status: str) -> None:
        units = self.units()
        for u in units:
            if u["单位"] == uid:
                u["状态"] = status
        self.write_units(units)

    def add_record(self, title: str, body: str) -> None:
        rec = self.section("检查记录").strip("\n")
        rec = re.sub(rf"^### {re.escape(title)}\s*$[\s\S]*?(?=^### |\Z)", "", rec, flags=re.M).strip("\n")
        self.set_section("检查记录", (rec + "\n\n" if rec else "") + f"### {title}\n\n{body.strip()}\n")

    # 问题
    def issues(self) -> list[dict]:
        return parse_issues(self.section("问题"), heading="### ")

    def write_issues(self, issues: list[dict]) -> None:
        order = {s: i for i, s in enumerate(SEVERITIES)}
        issues = sorted(issues, key=lambda x: (order.get(x["严重度"], 9), LAYERS.index(x["层"]) if x["层"] in LAYERS else 9))
        blocks = []
        for n, iss in enumerate(issues, 1):
            lines = [f"### A{n} · {iss['严重度']} · {iss['层']} · {iss['标题']}", ""]
            for f in ISSUE_FIELDS + ["怎么改", "来源"]:
                if iss.get(f):
                    lines.append(f"- {f}：{iss[f]}")
            blocks.append("\n".join(lines))
        self.set_section("问题", "\n\n".join(blocks) if blocks else "未发现问题")

    def add_issues(self, new: list[dict]) -> None:
        self.write_issues(self.issues() + new)


def parse_issues(text: str, heading: str) -> list[dict]:
    out = []
    for block in re.split(rf"^(?={re.escape(heading)})", text, flags=re.M):
        if not block.startswith(heading):
            continue
        first, _, rest = block.partition("\n")
        title = first[len(heading):].strip()
        m = re.match(r"A\d+ · (P\d) · (L\d) · (.*)$", title)
        iss = {"标题": m.group(3) if m else title}
        if m:
            iss["严重度"], iss["层"] = m.group(1), m.group(2)
        for fm in re.finditer(r"^- ([^：\n]+)：(.*)$", rest, re.M):
            iss[fm.group(1).strip()] = fm.group(2).strip()
        out.append(iss)
    return out


def issue(layer: str, sev: str, title: str, what: str, impact: str, where: str, evidence: str, fix: str, src: str) -> dict:
    return {"层": layer, "严重度": sev, "标题": title, "是什么": what, "影响": impact, "位置": where,
            "证据": evidence, "怎么改": fix, "来源": src}


# ---------- start ----------

def previous_audit(root: Path, exclude: str | None = None) -> tuple[str, str] | None:
    best = None
    for p in (root / "reports/audit").glob("audit-*.md"):
        t = p.read_text(encoding="utf-8")
        aid = re.search(r"^> 检查 ID：(\S+)", t, re.M)
        if not aid or aid.group(1) == exclude or not re.search(r"^> 状态：完成", t, re.M):
            continue
        commit = re.search(r"^> 代码版本：([0-9a-f]{7,40})", t, re.M)
        started = re.search(r"^> 开始时间：(.*)$", t, re.M)
        if commit:
            key = started.group(1) if started else ""
            if best is None or key > best[0]:
                best = (key, aid.group(1), commit.group(1))
    return (best[1], best[2]) if best else None


def changed_since(root: Path, commit: str) -> list[str]:
    files = set()
    diff = git(root, "diff", "--name-only", f"{commit}..HEAD")
    for line in (diff or "").splitlines():
        files.add(line.strip())
    status = git(root, "status", "--porcelain", "--untracked-files=all")
    for line in (status or "").splitlines():
        files.add(line[3:].strip().split(" -> ")[-1])
    return sorted(f for f in files if f and (root / f).is_file())


def cmd_start(args) -> int:
    root = find_root(args.root)
    layers = [x.strip().upper() for x in args.layers.split(",")] if args.layers else LAYERS
    bad = [x for x in layers if x not in LAYERS]
    if bad:
        raise UsageError(f"没有这一层：{bad}，只有 {LAYERS}")
    head = git(root, "rev-parse", "--short", "HEAD")
    dirty = bool(git(root, "status", "--porcelain"))
    prev = previous_audit(root)
    every = code_files(root)
    note = ""
    if args.module:
        mods = [m.strip("/") for m in args.module]
        for m in mods:
            if not (root / m).is_dir():
                raise UsageError(f"没有这个目录：{m}")
        files = [f for f in every if any(f == m or f.startswith(m + "/") for m in mods)]
        kind = "指定模块 " + "、".join(mods)
        changed_docs: set[str] = set(mods)
    elif args.full or not prev or not head:
        files = every
        mods = sorted({module_of(root, f) for f in files if not is_test(f) and (root / f).stat().st_size > 0})
        kind = "全量" if args.full else "全量（第一次巡检）"
        changed_docs = set(mods)
        if not args.full and len(mods) > 5:
            sizes = defaultdict(int)
            for f in files:
                if not is_test(f):
                    sizes[module_of(root, f)] += (root / f).stat().st_size
            top = sorted(mods, key=lambda m: -sizes[m])[:5]
            note = "第一次巡检，AI 部分先查最大的 5 个模块；没查的：" + "、".join(m for m in mods if m not in top)
            mods = top
            changed_docs = set(top)
    else:
        changed = changed_since(root, prev[1])
        files = [f for f in changed if is_code(Path(f))]
        mods = sorted({module_of(root, f) for f in files if not is_test(f) and (root / f).stat().st_size > 0})
        doc_mods = {module_of(root, f) for f in changed if Path(f).name.lower() == "readme.md"}
        changed_docs = set(mods) | {m for m in doc_mods}
        mods = sorted(set(mods) | doc_mods)
        kind = f"增量（上次巡检 {prev[0]} 以来变了的）"

    audit_id = secrets.token_hex(4)
    out_dir = root / "reports/audit"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"audit-{audit_id}.md"
    head_text = "\n".join([
        f"# 代码巡检报告 · {audit_id}", "",
        f"> 检查 ID：{audit_id}",
        f"> 开始时间：{now()}",
        "> 状态：进行中",
        f"> 代码版本：{head or '无 git'}{'（另有未提交改动）' if dirty else ''}",
        f"> 上次巡检：{prev[0] + ' @ ' + prev[1] if prev else '无'}",
        f"> 范围：{kind}",
        f"> 层：{'、'.join(layers)}", "",
    ])
    scope = [f"- 模块（{len(mods)} 个）：" + ("、".join(mods) if mods else "无"),
             f"- 文件：{len(files)} 个，清单在「检查进度」下面"]
    if note:
        scope.append(f"- 说明：{note}")
    body = head_text + "\n" + "\n\n".join(
        [f"## 范围\n\n" + "\n".join(scope), "## 结论\n\n（主 agent 在 merge、verify 之后写）",
         "## 问题\n\n未发现问题", "## 检查进度\n\n", "## 检查记录\n\n"]) + "\n"
    path.write_text(body, encoding="utf-8")
    rep = Report(root, audit_id)
    units = []
    script_layers = [x for x in ("L1", "L2", "L3", "L5") if x in layers]
    for layer in script_layers:
        units.append({"单位": f"U{len(units) + 1}", "层": layer, "范围": "范围内全部文件" if layer != "L3" else "范围内模块的说明",
                      "谁查": "脚本", "状态": "待查"})
    for m in mods:
        for layer in ("L4", "L6"):
            if layer in layers:
                units.append({"单位": f"U{len(units) + 1}", "层": layer, "范围": m, "谁查": "子 agent", "状态": "待查"})
    if "L5" in layers and mods:
        units.append({"单位": f"U{len(units) + 1}", "层": "L5", "范围": "、".join(mods), "谁查": "子 agent", "状态": "待查"})
    info = {"files": files, "modules": mods, "doc_modules": sorted(changed_docs), "prev": prev[1] if prev else None}
    first, _, rest = rep.text.partition("\n")
    rep.text = first + f"\n<!-- x-code-audit:{json.dumps(info, ensure_ascii=False)} -->\n" + rest
    rep.write_units(units, files)
    rep.save()
    print(json.dumps({"id": audit_id, "report": str(path.relative_to(root)), "units": units}, ensure_ascii=False, indent=2))
    return 0


def meta(rep: Report) -> dict:
    m = re.search(r"<!-- x-code-audit:(.*) -->", rep.text)
    return json.loads(m.group(1)) if m else {"files": [], "modules": [], "doc_modules": []}


def unit_for(rep: Report, layer: str, who: str = "脚本") -> dict | None:
    return next((u for u in rep.units() if u["层"] == layer and u["谁查"] == who), None)


# ---------- L1 ----------

def ruff_selects(text: str) -> set[str]:
    sel = set()
    for key in ("select", "extend-select"):
        for m in re.finditer(rf"^\s*{key}\s*=\s*\[([^\]]*)\]", text, re.M):
            sel |= {s.strip().strip("\"'") for s in m.group(1).split(",") if s.strip()}
    return sel


def cmd_l1(rep: Report) -> list[dict]:
    root, m = rep.root, meta(rep)
    files = m["files"]
    langs = {Path(f).suffix for f in files} or {Path(f).suffix for f in code_files(root)}
    py = ".py" in langs
    ts = bool(langs & {".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs"})
    go = ".go" in langs
    read = lambda p: (root / p).read_text(encoding="utf-8", errors="ignore") if (root / p).is_file() else ""
    ci_text = "\n".join(read(p) for p in all_files(root) if p.startswith(".github/workflows/") or p == ".gitlab-ci.yml")
    ci_files = [p for p in all_files(root) if p.startswith(".github/workflows/") or p == ".gitlab-ci.yml"]
    ci_where = ci_files[0] if ci_files else next((p for p in ("pyproject.toml", "package.json", "go.mod") if (root / p).is_file()), "README.md")
    found, missing, runs, issues = [], [], [], []
    src = unit_for(rep, "L1")["单位"]

    def gap(rule: str, where: str, how: str) -> None:
        missing.append([rule, where, how])
        issues.append(issue("L1", "P2", f"缺少 lint 规则：{rule}", f"项目没有配置「{rule}」这条检查。",
                            "这类问题现在没有工具把关，只能靠人看，迟早会混进代码。", f"`{where}`",
                            f"在 `{where}` 里找不到这条配置", how, src))

    def run_tool(name: str, cmd: list[str], severe: bool) -> None:
        r = run(cmd, root)
        out = (r.stdout + r.stderr).strip().splitlines()
        if r.returncode == 127:
            runs.append([name, " ".join(cmd), "没装", "-"])
            issues.append(issue("L1", "P2", f"{name} 没装，没法检查", f"配置里用到了 {name}，但这台机器上找不到它。",
                                "这一项检查没跑，结果未知。", "`" + cmd[0] + "`", out[0] if out else "", f"安装 {name}", src))
            return
        locs = [l for l in out if re.match(r"^[\w./-]+:\d+", l)]
        runs.append([name, " ".join(cmd[:3]) + (" …" if len(cmd) > 3 else ""), str(r.returncode), str(len(locs))])
        if r.returncode != 0 and locs:
            first = locs[0].split(":")
            issues.append(issue("L1", "P1" if severe else "P2", f"{name} 报了 {len(locs)} 处问题",
                                f"跑 {name}，有 {len(locs)} 处不过。",
                                "类型或代码错误留在代码里，运行到那里可能出错。" if severe else "代码规范不统一，越积越难改。",
                                f"`{first[0]}`，第 {first[1]} 行", "；".join(locs[:3]), f"按 {name} 的提示逐条改", src))

    if py:
        pyproject, ruff_toml = read("pyproject.toml"), read("ruff.toml") + read(".ruff.toml")
        ruff_cfg = ruff_toml or ("[tool.ruff" in pyproject and pyproject)
        flake8_cfg = read(".flake8") or ("[flake8]" in read("setup.cfg") and read("setup.cfg")) or ("[flake8]" in read("tox.ini") and read("tox.ini"))
        mypy_cfg = read("mypy.ini") or ("[tool.mypy]" in pyproject) or ("[mypy]" in read("setup.cfg"))
        cfg_file = "ruff.toml" if ruff_toml else "pyproject.toml"
        pyfiles = [f for f in files if f.endswith(".py")] or ["."]
        if ruff_cfg:
            found.append(["ruff", cfg_file])
            sel = ruff_selects(ruff_cfg)
            if sel and not any(s in sel for s in ("F", "ALL")):
                gap("未使用的导入和变量（ruff F）", cfg_file, "在 ruff 的 select 里加上 \"F\"")
            if not any(s in sel for s in ("N", "ALL")):
                gap("命名规范（ruff N）", cfg_file, "在 ruff 的 select 里加上 \"N\"")
            if not any(s in sel for s in ("C90", "C901", "ALL")):
                gap("函数太复杂（ruff C90）", cfg_file, "在 ruff 的 select 里加上 \"C90\"，并设 max-complexity")
            run_tool("ruff", ["ruff", "check", "--output-format=concise", *pyfiles], False)
            if "ruff" not in ci_text:
                gap("CI 里跑 ruff", ci_where, "在 CI（如 .github/workflows/ci.yml）里加一步 `ruff check .`")
        elif flake8_cfg:
            found.append(["flake8", ".flake8 / setup.cfg"])
            gap("命名规范（pep8-naming）", ".flake8", "装 pep8-naming 插件，或换用 ruff 并启用 N")
            run_tool("flake8", ["flake8", *pyfiles], False)
        else:
            gap("Python lint（ruff 或 flake8）", "pyproject.toml", "加 [tool.ruff]，select 至少含 F、N、C90")
        if mypy_cfg:
            found.append(["mypy", "mypy.ini / pyproject.toml"])
            run_tool("mypy", ["mypy", *[f for f in pyfiles if f != "."]] if pyfiles != ["."] else ["mypy", "."], True)
            if "mypy" not in ci_text:
                gap("CI 里跑 mypy", ci_where, "在 CI 里加一步 `mypy .`")
        else:
            gap("Python 类型检查（mypy）", "pyproject.toml", "加 [tool.mypy]")
        if not ("[tool.black]" in pyproject or "format" in (ruff_cfg or "") or (ruff_cfg and "ruff format" in ci_text)):
            gap("Python 格式化（black 或 ruff format）", "pyproject.toml", "加 [tool.black]，或在 CI 跑 `ruff format --check`")
    if ts:
        eslint = next((p for p in all_files(root) if re.match(r"^(eslint\.config\.\w+|\.eslintrc(\.\w+)?)$", p)), None)
        tsconfig = read("tsconfig.json")
        if eslint:
            found.append(["eslint", eslint])
            et = read(eslint)
            if "naming-convention" not in et:
                gap("命名规范（@typescript-eslint/naming-convention）", eslint, "在 eslint 配置里启用 naming-convention")
            if "complexity" not in et:
                gap("函数太复杂（eslint complexity）", eslint, "在 eslint 配置里启用 complexity")
            run_tool("eslint", ["npx", "--no-install", "eslint", *[f for f in files if Path(f).suffix in {".ts", ".tsx", ".js", ".jsx"}]] or ["."], False)
        else:
            gap("JS/TS lint（eslint）", "eslint.config.js", "加 eslint 配置")
        if tsconfig:
            found.append(["tsc", "tsconfig.json"])
            if not re.search(r'"strict"\s*:\s*true', tsconfig):
                gap("严格类型（strict）", "tsconfig.json", "在 compilerOptions 里设 \"strict\": true")
            if not re.search(r'"noUnusedLocals"\s*:\s*true', tsconfig) and "no-unused-vars" not in (read(eslint) if eslint else ""):
                gap("未使用的变量（noUnusedLocals）", "tsconfig.json", "设 \"noUnusedLocals\": true, \"noUnusedParameters\": true")
            run_tool("tsc", ["npx", "--no-install", "tsc", "--noEmit", "-p", "tsconfig.json"], True)
        if not any(p.startswith(".prettierrc") for p in all_files(root)) and '"prettier"' not in read("package.json"):
            gap("JS/TS 格式化（prettier）", "package.json", "加 prettier 配置")
    if go:
        golangci = read(".golangci.yml") or read(".golangci.yaml")
        if golangci:
            found.append(["golangci-lint", ".golangci.yml"])
            for linter in ("staticcheck", "unused"):
                if linter not in golangci:
                    gap(f"Go 静态检查（{linter}）", ".golangci.yml", f"启用 {linter}")
        else:
            gap("Go lint（golangci-lint）", ".golangci.yml", "加 .golangci.yml，启用 staticcheck、unused")
        run_tool("go vet", ["go", "vet", "./..."], True)

    body = ["找到的工具：", table(["工具", "配置"], found) if found else "无",
            "", "缺的规则：", table(["规则", "该配在哪", "怎么配"], missing) if missing else "无",
            "", "跑过的命令：", table(["工具", "命令", "退出码", "报错条数"], runs) if runs else "无"]
    rep.add_record(f"{src} · L1 机器检查", "\n".join(body))
    rep.add_issues(issues)
    rep.set_unit_status(src, "完成")
    return issues


# ---------- L2 ----------

def py_defs_and_refs(root: Path, pyfiles: list[str]):
    defs, refs, strings = [], defaultdict(lambda: [0, 0]), defaultdict(int)
    for rel in pyfiles:
        try:
            tree = ast.parse((root / rel).read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError):
            continue
        test = is_test(rel)
        exported = set()
        for node in tree.body:
            if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "__all__" for t in node.targets):
                if isinstance(node.value, (ast.List, ast.Tuple)):
                    exported |= {e.value for e in node.value.elts if isinstance(e, ast.Constant)}
        if not test:
            for node in tree.body:
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    decos = [ast.unparse(d) for d in node.decorator_list]
                    defs.append({"name": node.name, "file": rel, "line": node.lineno, "kind": "类" if isinstance(node, ast.ClassDef) else "函数",
                                 "entry": any(ENTRY_DECORATOR.search(d) for d in decos) or node.name in exported
                                 or node.name in {"main", "handler", "lambda_handler"},
                                 "decos": decos})
                elif isinstance(node, ast.Assign):
                    for t in node.targets:
                        if isinstance(t, ast.Name) and t.id.isupper() and not t.id.startswith("__"):
                            defs.append({"name": t.id, "file": rel, "line": node.lineno, "kind": "常量",
                                         "entry": t.id in exported, "decos": []})
        own = {(d["name"], d["line"]) for d in defs if d["file"] == rel}
        for node in ast.walk(tree):
            name = None
            if isinstance(node, ast.Name):
                name = node.id
            elif isinstance(node, ast.Attribute):
                name = node.attr
            elif isinstance(node, ast.alias):
                name = node.name.split(".")[-1]
            elif isinstance(node, ast.Constant) and isinstance(node.value, str):
                for w in re.findall(r"[A-Za-z_]\w*", node.value):
                    strings[w] += 1
            if name and not (isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store) and (name, getattr(node, "lineno", 0)) in own):
                refs[name][1 if test else 0] += 1
    return defs, refs, strings


def removed_names(root: Path, prev: str | None) -> set[str]:
    if not prev:
        return set()
    d = git(root, "diff", "-U0", f"{prev}..HEAD") or ""
    d += "\n" + (git(root, "diff", "-U0") or "")
    return {w for line in d.splitlines() if line.startswith("-") and not line.startswith("---")
            for w in re.findall(r"[A-Za-z_]\w*", line)}


def cmd_l2(rep: Report) -> list[dict]:
    root, m = rep.root, meta(rep)
    src = unit_for(rep, "L2")["单位"]
    scope_files = set(m["files"])
    full = rep.header("范围").startswith("全量")
    removed = removed_names(root, m.get("prev"))
    rows, issues, unsure, notes = [], [], [], []
    every = code_files(root)
    pyfiles = [f for f in every if f.endswith(".py")]
    if pyfiles:
        defs, refs, strings = py_defs_and_refs(root, pyfiles)
        for d in defs:
            if not (full or d["file"] in scope_files or d["name"] in removed):
                continue
            if d["name"].startswith("_") and d["kind"] != "函数":
                continue
            prod, test = refs[d["name"]]
            if prod > 0:
                continue
            where = f"`{d['file']}` 的 `{d['name']}{'()' if d['kind'] == '函数' else ''}`，第 {d['line']} 行"
            if d["entry"] or strings.get(d["name"]):
                why = "带装饰器 " + "、".join(d["decos"]) if d["decos"] else ("名字出现在字符串里" if strings.get(d["name"]) else "像对外入口")
                unsure.append([d["name"], where, why])
                rows.append([d["name"], d["kind"], where, "拿不准：" + why])
            elif test:
                rows.append([d["name"], d["kind"], where, f"只有测试在用（{test} 处）"])
                issues.append(issue("L2", "P2", f"{d['kind']} {d['name']} 只有测试在用",
                                    f"生产代码里没有任何地方用到 {d['kind']} `{d['name']}`，只有测试在调用它。",
                                    "它和它的测试一起白白占着维护成本，读代码的人还会以为它在起作用。", where,
                                    f"全项目非测试代码引用 0 处，测试引用 {test} 处", "确认没用后连同测试一起删掉", src))
            else:
                rows.append([d["name"], d["kind"], where, "确认没用（0 引用）"])
                issues.append(issue("L2", "P2", f"{d['kind']} {d['name']} 没人用",
                                    f"全项目找不到任何地方用到 {d['kind']} `{d['name']}`。",
                                    "没人用的代码会让人误以为它在起作用，改相关逻辑时还得顺带看它。", where,
                                    "全项目引用 0 处（含测试、字符串）", "删掉", src))
    tsfiles = [f for f in every if Path(f).suffix in {".ts", ".tsx", ".js", ".jsx"}]
    if tsfiles:
        r = run(["npx", "--no-install", "knip", "--reporter", "json"], root)
        if r.returncode in (0, 1) and r.stdout.strip().startswith("{"):
            data = json.loads(r.stdout)
            for f in data.get("files", []):
                where = f"`{f}`"
                rows.append([Path(f).name, "文件", where, "确认没用（knip）"])
                issues.append(issue("L2", "P2", f"文件 {f} 没人引用", f"没有任何文件 import `{f}`。",
                                    "没人用的文件会被误改、误读。", where, "knip 报 unused file", "删掉", src))
            for item in data.get("issues", []):
                for e in item.get("exports", []):
                    where = f"`{item['file']}` 的 `{e['name']}`，第 {e.get('line', 1)} 行"
                    rows.append([e["name"], "导出", where, "确认没用（knip）"])
                    issues.append(issue("L2", "P2", f"导出 {e['name']} 没人用", f"`{e['name']}` 导出了，但没有别的文件用它。",
                                        "多余的导出让模块的对外接口看起来比实际更大。", where, "knip 报 unused export", "删掉导出，或连同代码删掉", src))
        else:
            r2 = run(["npx", "--no-install", "tsc", "--noEmit", "--noUnusedLocals", "--noUnusedParameters"], root)
            notes.append("knip 不可用，退回 tsc 只能查文件内没用的变量和参数；建议安装 knip：`npm i -D knip`")
            for line in (r2.stdout or "").splitlines()[:50]:
                mm = re.match(r"^(.+)\((\d+),\d+\): error TS6133: '(.+)' is declared", line)
                if mm:
                    where = f"`{mm.group(1)}`，第 {mm.group(2)} 行"
                    rows.append([mm.group(3), "变量", where, "确认没用（tsc）"])
                    issues.append(issue("L2", "P2", f"变量 {mm.group(3)} 没用", f"`{mm.group(3)}` 声明了但没用到。",
                                        "多余的变量让代码更难读。", where, line.strip(), "删掉", src))
    gofiles = [f for f in every if f.endswith(".go")]
    if gofiles:
        r = run(["staticcheck", "-checks", "U1000", "./..."], root)
        if r.returncode == 127:
            notes.append("staticcheck 没装，Go 死代码没查：`go install honnef.co/go/tools/cmd/staticcheck@latest`")
        for line in r.stdout.splitlines():
            mm = re.match(r"^(.+?):(\d+):\d+: (.*) is unused", line)
            if mm:
                where = f"`{mm.group(1)}`，第 {mm.group(2)} 行"
                rows.append([mm.group(3), "Go", where, "确认没用（staticcheck）"])
                issues.append(issue("L2", "P2", f"{mm.group(3)} 没人用", f"{mm.group(3)} 没有任何地方用到。",
                                    "没人用的代码会被误读、误改。", where, line.strip(), "删掉", src))
    body = [table(["名字", "类型", "位置", "结论"], rows) if rows else "没有找到 0 引用的代码"]
    body += [f"\n说明：{n}" for n in notes]
    if unsure:
        uid = rep.add_unit("L2", f"拿不准的候选 {len(unsure)} 个", "子 agent")
        body.append(f"\n交给 {uid} 确认的候选：\n\n" + table(["检查项", "位置", "为什么拿不准"], unsure))
    rep.add_record(f"{src} · L2 死代码", "\n".join(body))
    rep.add_issues(issues)
    rep.set_unit_status(src, "完成" if not any("没装" in n for n in notes) else "未完成")
    return issues


# ---------- L3 ----------

def slug(heading: str) -> str:
    return re.sub(r"[^\w\u4e00-\u9fff-]", "", heading.strip().lower().replace(" ", "-"))


def cmd_l3(rep: Report) -> list[dict]:
    root, m = rep.root, meta(rep)
    src = unit_for(rep, "L3")["单位"]
    mods = m["modules"]
    rows, issues, no_readme = [], [], []
    for mod in mods:
        readme = readme_in(root, mod)
        if not readme:
            no_readme.append(mod)
            continue
        text = (root / readme).read_text(encoding="utf-8")
        base = (root / readme).parent
        code = "\n".join((root / f).read_text(encoding="utf-8", errors="ignore") for f in code_files(root)
                         if f.startswith(mod + "/") or mod == ".")
        all_code = None
        for lineno, line in enumerate(text.splitlines(), 1):
            for link in re.findall(r"\]\(([^)\s]+)\)", line):
                if re.match(r"^[a-z]+://|^mailto:", link):
                    continue
                path, _, anchor = link.partition("#")
                target = (base / path).resolve() if path else (root / readme).resolve()
                ok = target.exists()
                result = "对得上" if ok else "找不到"
                if ok and anchor and target.suffix == ".md":
                    heads = {slug(h) for h in re.findall(r"^#+\s+(.*)$", target.read_text(encoding="utf-8"), re.M)}
                    if slug(anchor) not in heads:
                        result = "找不到章节"
                rows.append([readme, lineno, f"链接 {link}", result])
                if result != "对得上":
                    issues.append(issue("L3", "P2", f"说明里的链接失效：{link}", f"`{readme}` 第 {lineno} 行的链接 `{link}` 打不开（{result}）。",
                                        "读者点进去什么也找不到，只能自己翻代码。", f"`{readme}`，第 {lineno} 行",
                                        f"目标 {path or readme}{'#' + anchor if anchor else ''} {result}", "用 x-feat-doc 更新这一节的链接", src))
            for fn in re.findall(r"`([A-Za-z_][\w.]*)\(\)`", line):
                name = fn.split(".")[-1]
                pat = rf"(def|function|func|class)\s+{re.escape(name)}\b|\b{re.escape(name)}\s*[:=]\s*(async\s*)?\(|\b{re.escape(name)}\s*\("
                ok = re.search(rf"(def|function|func|class)\s+{re.escape(name)}\b|(const|let|var)\s+{re.escape(name)}\s*=", code)
                rows.append([readme, lineno, f"函数 {fn}()", "对得上" if ok else "找不到"])
                if not ok:
                    issues.append(issue("L3", "P1", f"说明里写的函数 {fn}() 不存在",
                                        f"`{readme}` 第 {lineno} 行提到函数 `{fn}()`，但模块代码里找不到这个函数。",
                                        "照着说明去调用会失败，读者会以为模块有这个能力。", f"`{readme}`，第 {lineno} 行",
                                        f"在 {mod}/ 的代码里搜不到 `{name}` 的定义", "用 x-feat-doc 按现在的代码重写这一节", src))
            for key, val in re.findall(r"`([A-Za-z_][\w.]*)`\s*默认(?:是|为)?\s*`([^`]+)`", line) + \
                    re.findall(r"`([A-Za-z_][\w.]*)\s*=\s*([^`]+)`", line):
                k = key.split(".")[-1]
                mm = re.search(rf"\b{re.escape(k)}\b\s*(?::\s*[\w\[\], ]+)?\s*[=:]\s*([^\n#,)]+)", code)
                if not mm:
                    rows.append([readme, lineno, f"配置 {key}", "找不到"])
                    issues.append(issue("L3", "P1", f"说明里的配置项 {key} 在代码里找不到",
                                        f"`{readme}` 第 {lineno} 行写了配置项 `{key}`，代码里没有这个名字。",
                                        "照着说明去配会不起作用。", f"`{readme}`，第 {lineno} 行", f"在 {mod}/ 里搜不到 `{k}`",
                                        "用 x-feat-doc 更新这一节", src))
                    continue
                actual = mm.group(1).strip().strip("\"'")
                same = actual == val.strip().strip("\"'")
                rows.append([readme, lineno, f"默认值 {key}={val}", "对得上" if same else f"值不一样（代码是 {actual}）"])
                if not same:
                    issues.append(issue("L3", "P1", f"说明里 {key} 的默认值写错了",
                                        f"`{readme}` 第 {lineno} 行说 `{key}` 默认是 `{val}`，代码里实际是 `{actual}`。",
                                        "照着说明理解的人会以为是另一个值，配置和排查都会出错。", f"`{readme}`，第 {lineno} 行",
                                        f"代码：{mm.group(0).strip()}", "用 x-feat-doc 按代码更新默认值", src))
            for p in re.findall(r"`([\w./-]+\.(?:py|ts|tsx|js|go|md|json|yaml|yml|toml))`", line):
                if (base / p).exists() or (root / p).exists():
                    rows.append([readme, lineno, f"文件 {p}", "对得上"])
                else:
                    rows.append([readme, lineno, f"文件 {p}", "找不到"])
                    issues.append(issue("L3", "P2", f"说明里提到的文件 {p} 不存在", f"`{readme}` 第 {lineno} 行提到文件 `{p}`，但它不存在。",
                                        "读者按说明找文件会找不到。", f"`{readme}`，第 {lineno} 行", f"{p} 不存在", "用 x-feat-doc 更新", src))
        if mod in m.get("doc_modules", []):
            rep.add_unit("L3", mod, "子 agent")
    body = [table(["说明文件", "行", "提到的东西", "结果"], [[a, str(b), c, d] for a, b, c, d in rows]) if rows else "范围内没有可核对的说明"]
    if no_readme:
        body.append("\n没有说明文档的模块：" + "、".join(no_readme) + "（可以用 x-feat-doc 补）")
    rep.add_record(f"{src} · L3 文档对代码（脚本部分）", "\n".join(body))
    rep.add_issues(issues)
    rep.set_unit_status(src, "完成")
    return issues


# ---------- L5 ----------

def py_module_name(rel: str) -> list[str]:
    p = Path(rel).with_suffix("")
    parts = list(p.parts)
    if parts and parts[-1] == "__init__":
        parts = parts[:-1]
    names = [".".join(parts[i:]) for i in range(len(parts))]
    return [n for n in names if n]


def import_graph(root: Path, files: list[str]) -> dict[str, set[str]]:
    index = {}
    for f in files:
        if f.endswith(".py"):
            for n in py_module_name(f):
                index.setdefault(n, f)
    graph = defaultdict(set)
    for f in files:
        text = (root / f).read_text(encoding="utf-8", errors="ignore")
        if f.endswith(".py"):
            try:
                tree = ast.parse(text)
            except SyntaxError:
                continue
            for node in ast.walk(tree):
                targets = []
                if isinstance(node, ast.Import):
                    targets = [a.name for a in node.names]
                elif isinstance(node, ast.ImportFrom) and node.module:
                    if node.level:
                        pkg = list(Path(f).parent.parts)[: len(Path(f).parent.parts) - node.level + 1]
                        targets = [".".join(pkg + [node.module])]
                    else:
                        targets = [node.module] + [f"{node.module}.{a.name}" for a in node.names]
                for t in targets:
                    if t in index and index[t] != f:
                        graph[f].add(index[t])
        elif Path(f).suffix in {".ts", ".tsx", ".js", ".jsx"}:
            for spec in re.findall(r"""(?:from|import|require\()\s*['"](\.[^'"]+)['"]""", text):
                base = (root / f).parent / spec
                for cand in [base, *[base.with_suffix(s) for s in (".ts", ".tsx", ".js", ".jsx")], base / "index.ts", base / "index.js"]:
                    if cand.is_file():
                        graph[f].add(cand.resolve().relative_to(root.resolve()).as_posix())
                        break
    return graph


def cycles(graph: dict[str, set[str]]) -> list[list[str]]:
    index, low, stack, on, out, counter = {}, {}, [], set(), [], [0]

    def strong(v):
        index[v] = low[v] = counter[0]
        counter[0] += 1
        stack.append(v)
        on.add(v)
        for w in graph.get(v, ()):
            if w not in index:
                strong(w)
                low[v] = min(low[v], low[w])
            elif w in on:
                low[v] = min(low[v], index[w])
        if low[v] == index[v]:
            comp = []
            while True:
                w = stack.pop()
                on.discard(w)
                comp.append(w)
                if w == v:
                    break
            if len(comp) > 1:
                out.append(sorted(comp))

    sys.setrecursionlimit(10000)
    for v in list(graph):
        if v not in index:
            strong(v)
    return out


def cycle_path(graph: dict[str, set[str]], comp: list[str]) -> list[str]:
    start = comp[0]
    seen, path = set(), [start]

    def dfs(v):
        for w in sorted(graph.get(v, ())):
            if w == start and len(path) > 1:
                return True
            if w in comp and w not in seen:
                seen.add(w)
                path.append(w)
                if dfs(w):
                    return True
                path.pop()
        return False

    dfs(start)
    return path + [start]


def cmd_l5(rep: Report) -> list[dict]:
    root, m = rep.root, meta(rep)
    src = unit_for(rep, "L5")["单位"]
    every = [f for f in code_files(root) if not is_test(f)]
    graph = import_graph(root, every)
    issues, body = [], []
    mods = set(m["modules"])
    full = rep.header("范围").startswith("全量")
    relevant = lambda files: full or any(module_of(root, f) in mods for f in files)
    cyc_rows = []
    for comp in cycles(graph):
        if not relevant(comp):
            continue
        path = cycle_path(graph, comp)
        cyc_rows.append([" → ".join(path)])
        issues.append(issue("L5", "P1", f"循环依赖：{Path(path[0]).name} 和 {Path(path[1]).name} 互相引用",
                            "这几个文件互相 import，形成一个环：" + " → ".join(f"`{p}`" for p in path) + "。",
                            "改其中一个就可能牵动另一个，测试也没法单独测；启动顺序稍有变化还可能直接报导入错误。",
                            f"`{path[0]}`", "依赖路径：" + " → ".join(path),
                            "把两边共用的部分抽到第三个模块，让依赖只朝一个方向", src))
    body += ["循环依赖：", table(["依赖路径"], cyc_rows) if cyc_rows else "无"]
    cfg = root / ".x-code-audit.json"
    layer_rows = []
    if cfg.is_file():
        try:
            layers = json.loads(cfg.read_text(encoding="utf-8")).get("layers", [])
        except json.JSONDecodeError:
            layers = []
        def level(f):
            parts = set(Path(f).parts[:-1]) | {Path(f).stem}
            for i, names in enumerate(layers):
                if parts & set(names):
                    return i
            return None
        for f, deps in graph.items():
            for d in deps:
                a, b = level(f), level(d)
                if a is not None and b is not None and a > b and relevant([f, d]):
                    layer_rows.append([f, d])
                    issues.append(issue("L5", "P1", f"下层依赖了上层：{Path(f).name} → {Path(d).name}",
                                        f"`{f}` 属于下层，却 import 了上层的 `{d}`。",
                                        "分层被打破后，改上层会牵动下层，越改越乱。", f"`{f}`", f"{f} import {d}",
                                        "把需要的东西移到下层，或改成由上层把数据传下来", src))
        body += ["", "分层（按 .x-code-audit.json）：", table(["下层文件", "依赖的上层文件"], layer_rows) if layer_rows else "没有违反"]
    else:
        body += ["", "分层：项目没有 .x-code-audit.json 的 layers 配置，跳过"]
    consts = defaultdict(list)
    for f in every:
        if not f.endswith(".py"):
            continue
        try:
            tree = ast.parse((root / f).read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        for node in tree.body:
            if isinstance(node, ast.Assign):
                for t in node.targets:
                    if isinstance(t, ast.Name) and t.id.isupper() and not t.id.startswith("__"):
                        consts[t.id].append((f, node.lineno, ast.unparse(node.value)))
    dup_rows = []
    for name, places in sorted(consts.items()):
        if len({p[0] for p in places}) < 2 or not relevant([p[0] for p in places]):
            continue
        values = {p[2] for p in places}
        dup_rows.append([name, "；".join(f"`{p[0]}` 第 {p[1]} 行 = {p[2]}" for p in places), "已不一致" if len(values) > 1 else "一致"])
    body += ["", "多处定义的常量（交给子 agent 判断是不是同一件事）：",
             table(["名字", "位置和值", "值"], dup_rows) if dup_rows else "无"]
    rep.add_record(f"{src} · L5 架构审查（脚本部分）", "\n".join(body))
    rep.add_issues(issues)
    rep.set_unit_status(src, "完成")
    return issues


# ---------- units / merge / verify ----------

def cmd_units(rep: Report) -> list[dict]:
    here = Path(__file__).resolve().parents[1]
    out = []
    for u in rep.units():
        if u["谁查"] == "子 agent" and u["状态"] != "完成":
            ref = {"L2": "l2-dead-code.md", "L3": "l3-docs.md", "L4": "l4-module.md", "L5": "l5-architecture.md", "L6": "l6-perf.md"}[u["层"]]
            out.append({**u, "细则": str(here / "references" / ref),
                        "回执写到": str(rep.parts / f"{u['单位']}.md")})
    return out


def parse_receipt(text: str) -> dict:
    head = {k: v.strip() for k, v in re.findall(r"^- (单位|层|范围|模型)：(.*)$", text, re.M)}
    sec = lambda name: (re.search(rf"^## {name}\s*$\n([\s\S]*?)(?=^## |\Z)", text, re.M) or [None, ""])[1]
    t = parse_table(sec("检查项"), ("检查项", "结论", "位置"))
    items = [dict(zip(t[0], r)) for r in t[1]] if t else []
    issues = parse_issues(sec("问题"), heading="### ")
    return {"head": head, "items": items, "issues": issues}


def cmd_merge(rep: Report) -> list[str]:
    errors = []
    if not rep.parts.is_dir():
        return ["没有回执目录：" + str(rep.parts.relative_to(rep.root))]
    units = {u["单位"]: u for u in rep.units()}
    new_issues = []
    merged = []
    for part in sorted(rep.parts.glob("*.md")):
        r = parse_receipt(part.read_text(encoding="utf-8"))
        uid = r["head"].get("单位") or part.stem
        u = units.get(uid)
        if not u:
            errors.append(f"{part.name}：单位 {uid} 不在检查进度里")
            continue
        for iss in r["issues"]:
            iss["层"], iss["来源"] = u["层"], uid
            iss.setdefault("严重度", iss.get("严重度", ""))
            new_issues.append(iss)
        rows = [[i.get("检查项", ""), i.get("结论", ""), i.get("位置", "")] for i in r["items"]]
        model = r["head"].get("模型", "未写")
        rep.add_record(f"{uid} · {u['层']} {LAYER_NAMES[u['层']]} · {u['范围']}",
                       f"模型：{model}\n\n" + (table(["检查项", "结论", "位置"], rows) if rows else "回执里没有检查项"))
        rep.set_unit_status(uid, "完成")
        merged.append(part)
    rep.add_issues(new_issues)
    rep.save()
    for p in merged:
        p.unlink()
    if rep.parts.is_dir() and not any(rep.parts.iterdir()):
        rep.parts.rmdir()
    return errors


LOC_FILE = re.compile(r"`([^`\s]+\.[A-Za-z0-9]+)`")
LOC_FUNC = re.compile(r"`([A-Za-z_][\w.]*)\(\)`")
LOC_LINE = re.compile(r"第\s*(\d+)(?:\s*[–\-~至]\s*(\d+))?\s*行")


def check_location(root: Path, where: str) -> str | None:
    files = [f for f in LOC_FILE.findall(where) if not f.endswith("()")]
    if not files:
        dirs = re.findall(r"`([^`\s]+/)`", where)
        if dirs and all((root / d).is_dir() for d in dirs):
            return None
        return f"位置没写文件：{where}"
    path = root / files[0]
    if not path.exists():
        return f"位置里的文件不存在：{files[0]}"
    if path.is_dir():
        return None
    text = path.read_text(encoding="utf-8", errors="ignore")
    for fn in LOC_FUNC.findall(where):
        if not re.search(rf"\b{re.escape(fn.split('.')[-1])}\b", text):
            return f"{files[0]} 里没有 {fn}()"
    lines = text.count("\n") + 1
    for a, b in LOC_LINE.findall(where):
        if int(b or a) > lines:
            return f"{files[0]} 只有 {lines} 行，位置写了第 {b or a} 行"
    return None


def cmd_verify(rep: Report) -> list[str]:
    errors = []
    root = rep.root
    if rep.header("检查 ID") != rep.id:
        errors.append("报告头部的检查 ID 和文件名对不上")
    if rep.parts.exists() and any(rep.parts.iterdir()):
        errors.append("还有回执没合进报告：先运行 merge")
    units = rep.units()
    if not units:
        errors.append("检查进度是空的")
    records = rep.section("检查记录")
    unfinished = []
    for u in units:
        if u["状态"] != "完成":
            unfinished.append(u["单位"])
            continue
        title = re.search(rf"^### {re.escape(u['单位'])} · .*$", records, re.M)
        if not title:
            errors.append(f"{u['单位']} 标了完成，但检查记录里没有它")
            continue
        if u["谁查"] != "子 agent":
            continue
        block = re.search(rf"^### {re.escape(u['单位'])} · .*$\n([\s\S]*?)(?=^### |\Z)", records, re.M).group(1)
        t = parse_table(block, ("检查项", "结论", "位置"))
        items = {r[0]: r for r in t[1]} if t else {}
        need = CHECK_ITEMS.get(u["层"])
        if u["层"] == "L2":
            cand = re.search(rf"交给 {re.escape(u['单位'])} 确认的候选：\s*\n([\s\S]*?)(?=^### |\Z)", records, re.M)
            ct = parse_table(cand.group(1), ("检查项", "位置")) if cand else None
            need = [r[0] for r in ct[1]] if ct else []
        for name in need or []:
            row = items.get(name)
            if not row:
                errors.append(f"{u['单位']}（{u['层']} {u['范围']}）缺检查项「{name}」")
            elif row[1] not in RESULTS:
                errors.append(f"{u['单位']} 的「{name}」结论不对：{row[1]}，只能是 没问题 / 有问题 / 没法判断")
            elif row[1] == "有问题":
                err = check_location(root, row[2])
                if err:
                    errors.append(f"{u['单位']} 的「{name}」：{err}")
        has_issue = [r for r in items.values() if r[1] == "有问题"]
        unit_issues = [i for i in rep.issues() if i.get("来源") == u["单位"]]
        if has_issue and not unit_issues:
            errors.append(f"{u['单位']} 有检查项写了“有问题”，但问题里没有它的条目")
    issues = rep.issues()
    order = [SEVERITIES.index(i["严重度"]) if i.get("严重度") in SEVERITIES else 9 for i in issues]
    if order != sorted(order):
        errors.append("问题没按 P0 → P1 → P2 排好：先运行 merge")
    for n, iss in enumerate(issues, 1):
        tag = f"A{n}"
        if iss.get("严重度") not in SEVERITIES:
            errors.append(f"{tag} 的严重度不对：{iss.get('严重度')}")
        for f in ISSUE_FIELDS:
            if not iss.get(f):
                errors.append(f"{tag} 缺「{f}」")
        if iss.get("位置"):
            err = check_location(root, iss["位置"])
            if err:
                errors.append(f"{tag}：{err}")
    if not errors:
        rep.set_header("状态", "完成" if not unfinished else "未完成（" + "、".join(unfinished) + " 没做完）")
        rep.save()
        if unfinished:
            errors.append("这些单位还没做完：" + "、".join(unfinished))
    return errors


# ---------- main ----------

def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(description="x-code-audit 机械部分")
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("start")
    s.add_argument("--module", action="append")
    s.add_argument("--layers")
    s.add_argument("--full", action="store_true")
    s.add_argument("--root")
    for name in ("l1", "l2", "l3", "l5", "scripts", "units", "merge", "verify"):
        x = sub.add_parser(name)
        x.add_argument("id")
        x.add_argument("--root")
    args = p.parse_args(argv)
    try:
        if args.cmd == "start":
            return cmd_start(args)
        rep = Report(find_root(args.root), args.id)
        if args.cmd in ("l1", "l2", "l3", "l5", "scripts"):
            todo = [args.cmd] if args.cmd != "scripts" else ["l1", "l2", "l3", "l5"]
            for c in todo:
                if unit_for(rep, c.upper()) is None:
                    continue
                found = {"l1": cmd_l1, "l2": cmd_l2, "l3": cmd_l3, "l5": cmd_l5}[c](rep)
                rep.save()
                print(f"{c.upper()}：{len(found)} 个问题")
            pending = cmd_units(rep)
            print(f"还要派子 agent 的单位：{len(pending)} 个（audit.py units {rep.id} 查看）")
            return 0
        if args.cmd == "units":
            print(json.dumps(cmd_units(rep), ensure_ascii=False, indent=2))
            return 0
        errors = cmd_merge(rep) if args.cmd == "merge" else cmd_verify(rep)
        for e in errors:
            print("❌ " + e)
        print("OK" if not errors else f"{len(errors)} 处不过")
        return 1 if errors else 0
    except UsageError as e:
        print(f"用法错误：{e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
