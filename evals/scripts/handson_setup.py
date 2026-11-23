#!/usr/bin/env python3
"""给实操题准备一份项目副本。

用法：
  python3 evals/scripts/handson_setup.py <case> <workdir>
      从 evals/problems/cr-handson/cases/<case>/ 建副本：复制 project/，git 提交一次，
      再把 overlay/（如果有）盖上去、不提交，模拟“写完还没提交”的 diff。
  python3 evals/scripts/handson_setup.py --chain <上一阶段的 workdir> <workdir>
      x-fix 接着 x-cr 的结果跑：复制上一阶段的副本，把 x-cr 的报告一起提交。

两种用法都会在 <workdir>.orig/ 留一份开工时的原样，判分脚本拿它比对。答题 agent 只拿到 <workdir>。
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CASES = ROOT / "evals/problems/cr-handson/cases"
IGNORE = shutil.ignore_patterns("__pycache__", ".pytest_cache", ".git")


def git(workdir: Path, *args: str) -> None:
    subprocess.run(["git", "-c", "user.email=eval@local", "-c", "user.name=eval", *args],
                   cwd=workdir, check=True, capture_output=True)


def fresh(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)


def main(argv: list[str]) -> int:
    if len(argv) == 3 and argv[0] == "--chain":
        src, workdir = Path(argv[1]), Path(argv[2])
        fresh(workdir)
        shutil.copytree(src, workdir, ignore=IGNORE)
        git(workdir, "init", "-q")
        git(workdir, "add", "-A")
        git(workdir, "commit", "-qm", "x-cr 阶段结束时的状态")
    elif len(argv) == 2:
        case, workdir = argv[0], Path(argv[1])
        case_dir = CASES / case
        if not case_dir.is_dir():
            print(f"没有这道题：{case}", file=sys.stderr)
            return 2
        fresh(workdir)
        shutil.copytree(case_dir / "project", workdir, ignore=IGNORE)
        git(workdir, "init", "-q")
        git(workdir, "add", "-A")
        git(workdir, "commit", "-qm", "base")
        overlay = case_dir / "overlay"
        if overlay.is_dir():
            shutil.copytree(overlay, workdir, dirs_exist_ok=True, ignore=IGNORE)
    else:
        print(__doc__, file=sys.stderr)
        return 2
    orig = Path(str(workdir) + ".orig")
    fresh(orig)
    shutil.copytree(workdir, orig, ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache"))
    print(workdir)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
