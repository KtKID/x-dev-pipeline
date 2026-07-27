#!/usr/bin/env python3
"""xdev — x-dev-pipeline 确定性工具的统一 CLI。

本文件只负责参数解析、目标发现和引擎分流：

- validator.py：spec/spec7/change/capability 包校验
- req.py：spec task 的 scaffold/validate/instructions/status/graph
- verify.py：Gate ① 事实验证
- flag.py：QA Gate issue ledger 与状态降级事务

用法：
  python3 tools/xdev.py validate [目标目录 ...] [--include-legacy] [--json]
  python3 tools/xdev.py instructions <artifact-id> --task <task-dir> [--json]
  python3 tools/xdev.py scaffold <task-dir> [--with-diagram] [--json]
  python3 tools/xdev.py status <task-dir> [--json]
  python3 tools/xdev.py graph <task-dir> [--json]
  python3 tools/xdev.py verify <task-dir> [--json] [--only <id>]
  python3 tools/xdev.py flag <task-dir> --task T2,T3 --severity P0 \
      --loc src/a.py:10 --msg "空输入未处理" [--new-round] [--json]

退出码：0 成功；1 校验失败或依赖环；2 用法、目标或 IO 错误。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import flag as flag_engine
import req
import validator
import verify as verify_engine


def discover(root: Path) -> list[Path]:
    """发现 spec/change 包；task 始终由调用方显式传入。"""
    packages: list[Path] = []
    for base in ("docs/spec", "docs/changes", "docs/specs"):
        directory = root / base
        if not directory.is_dir():
            continue
        packages.extend(
            child
            for child in sorted(directory.iterdir())
            if child.is_dir() and child.name != "archive"
        )
    return packages


def validate_target(target: Path, include_legacy: bool) -> dict:
    """按 spec task 或 package 类型委托对应校验引擎。"""
    if req.spec_of_task_dir(target) is not None:
        if req.resolve_spec_dir(target) is None:
            return {
                "path": str(target),
                "type": "unsupported-task",
                "skipped": False,
                "issues": [{
                    "file": str(target),
                    "line": 0,
                    "rule": "TASK_VERSION",
                    "msg": "当前 task 引擎只支持父 spec 声明 spec_version: 3",
                }],
            }
        return {
            "path": str(target),
            "type": "req-task",
            "skipped": False,
            "issues": req.validate_issues(target),
        }
    return validator.validate_pkg(target, include_legacy)


def task_engine(task_dir: Path):
    """仅为父 spec 声明 spec_version: 3 的 task 返回 req 引擎。"""
    if req.spec_of_task_dir(task_dir) is None:
        return None
    if req.resolve_spec_dir(task_dir) is not None:
        return req
    return None


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="xdev",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    validate = sub.add_parser("validate", help="结构校验（机械项）")
    validate.add_argument(
        "targets",
        nargs="*",
        help="包或当前 task 目录；缺省时自动发现 docs/{spec,changes,specs}/*/",
    )
    validate.add_argument(
        "--include-legacy",
        action="store_true",
        help="把 legacy 图集结构的包纳入检查",
    )
    validate.add_argument("--json", action="store_true", dest="as_json")

    status = sub.add_parser("status", help="输出当前 task 状态和进度")
    status.add_argument("task_dir", help="docs/spec/<spec>/tasks/<task>/")
    status.add_argument("--json", action="store_true", dest="as_json")

    graph = sub.add_parser("graph", help="输出当前 task 依赖拓扑")
    graph.add_argument("task_dir", help="docs/spec/<spec>/tasks/<task>/")
    graph.add_argument("--json", action="store_true", dest="as_json")

    instructions = sub.add_parser("instructions", help="返回当前 task 产物填写规则")
    instructions.add_argument("artifact_id", help="artifact ID")
    instructions.add_argument("--task", required=True, dest="task_dir")
    instructions.add_argument("--json", action="store_true", dest="as_json")

    scaffold = sub.add_parser("scaffold", help="增量创建当前 task 包骨架")
    scaffold.add_argument("task_dir", help="docs/spec/<spec>/tasks/<task>/")
    scaffold.add_argument("--with-diagram", action="store_true")
    scaffold.add_argument("--json", action="store_true", dest="as_json")

    verify = sub.add_parser("verify", help="复跑 dev-report 并对账自动场景")
    verify.add_argument("task_dir", help="docs/spec/<spec>/tasks/<task>/")
    verify.add_argument("--json", action="store_true", dest="as_json")
    verify.add_argument("--only", help="只执行指定 auto verify 块")

    flag = sub.add_parser("flag", help="登记 QA Gate issue 并执行状态降级")
    flag.add_argument("task_dir", help="docs/spec/<spec>/tasks/<task>/")
    flag.add_argument("--task", required=True, dest="task_ids")
    flag.add_argument("--severity", required=True, choices=["P0", "P1", "P2"])
    flag.add_argument("--loc", required=True)
    flag.add_argument("--msg", required=True)
    flag.add_argument("--new-round", action="store_true")
    flag.add_argument("--json", action="store_true", dest="as_json")
    return parser


def _task_command(args: argparse.Namespace) -> int:
    task_dir = Path(args.task_dir)
    engine = task_engine(task_dir)
    if engine is None:
        print(
            "错误：只支持父 spec 声明 spec_version: 3 的 "
            f"docs/spec/<spec-name>/tasks/<task-name>/：{task_dir}",
            file=sys.stderr,
        )
        return 2
    if args.cmd == "instructions":
        return engine.instructions(args.artifact_id, task_dir, args.as_json)
    if args.cmd == "scaffold":
        return engine.scaffold(task_dir, args.with_diagram, args.as_json)
    if not task_dir.is_dir():
        print(f"错误：不是目录：{task_dir}", file=sys.stderr)
        return 2
    if args.cmd == "status":
        return engine.status(task_dir, args.as_json)
    return engine.graph(task_dir, args.as_json)


def _validate_command(args: argparse.Namespace) -> int:
    if args.targets:
        packages = [Path(value) for value in args.targets]
        for package in packages:
            if not package.is_dir():
                print(f"错误：不是目录：{package}", file=sys.stderr)
                return 2
    else:
        packages = discover(Path.cwd())
        if not packages:
            print(
                "错误：未发现任何包（docs/spec|changes|specs 下无子目录），可显式传目录",
                file=sys.stderr,
            )
            return 2

    results = [validate_target(package, args.include_legacy) for package in packages]
    total = sum(len(result["issues"]) for result in results)
    skipped = sum(1 for result in results if result["skipped"])
    if args.as_json:
        print(
            json.dumps(
                {
                    "packages": results,
                    "total_issues": total,
                    "skipped_legacy": skipped,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    else:
        for result in results:
            tag = f"[{result['type']}]"
            if result["skipped"]:
                print(f"== {result['path']}  {tag}  跳过（legacy；--include-legacy 可纳入）")
                continue
            print(f"== {result['path']}  {tag}")
            if not result["issues"]:
                print("   ok")
            for finding in result["issues"]:
                location = (
                    f"{finding['file']}:{finding['line']}"
                    if finding["line"]
                    else finding["file"]
                )
                print(f"   {location}  {finding['rule']}  {finding['msg']}")
        mark = "✓" if total == 0 else "✗"
        print(f"{mark} validate：{len(results)} 包，{total} issue(s)，{skipped} legacy 跳过")
    return 0 if total == 0 else 1


def main(argv: list[str] | None = None) -> int:
    """解析统一 CLI，并将命令分发给单一实现引擎。"""
    args = _build_parser().parse_args(argv)
    if args.cmd in {"instructions", "scaffold", "status", "graph"}:
        return _task_command(args)
    if args.cmd == "verify":
        return verify_engine.verify(Path(args.task_dir), args.as_json, args.only)
    if args.cmd == "flag":
        return flag_engine.flag_command(
            Path(args.task_dir),
            args.task_ids,
            args.severity,
            args.loc,
            args.msg,
            args.new_round,
            args.as_json,
        )
    return _validate_command(args)


if __name__ == "__main__":
    raise SystemExit(main())
