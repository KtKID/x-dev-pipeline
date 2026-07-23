#!/usr/bin/env python3
"""Deterministic, stdlib-only evaluator for journal-index-recovery."""

from __future__ import annotations

import argparse
import ast
import importlib.util
import json
import os
import pathlib
import shutil
import subprocess
import sys
import sysconfig
import tempfile
import zlib


REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
ORACLE_CASE = REPO_ROOT / "cases" / "journal-index-recovery"
RECORD_FIELDS = {"seq", "op", "key", "value", "request_id", "expected_version", "crc32"}


def canonical_body(record: dict[str, object], *, ensure_ascii: bool = False) -> bytes:
    return json.dumps(
        {key: value for key, value in record.items() if key != "crc32"},
        ensure_ascii=ensure_ascii,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def make_record(*, seq: int, op: str, key: str, value: str | None, request_id: str, expected_version: int) -> bytes:
    record: dict[str, object] = {
        "seq": seq,
        "op": op,
        "key": key,
        "value": value,
        "request_id": request_id,
        "expected_version": expected_version,
    }
    record["crc32"] = f"{zlib.crc32(canonical_body(record)) & 0xFFFFFFFF:08x}"
    return json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8") + b"\n"


class Harness:
    def __init__(self, fixture: pathlib.Path) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="journal-eval-")
        self.root = pathlib.Path(self.temp.name)
        self.backend = self.root / "backend"
        self.state = self.root / "state"
        shutil.copytree(fixture / "backend", self.backend)
        self.cli = self.backend / "cli.py"
        if not self.cli.is_file():
            raise AssertionError("fixture/backend/cli.py missing")

    def command(self, *args: str, timeout: float = 8) -> tuple[int, dict[str, object]]:
        result = subprocess.run(
            [sys.executable, str(self.cli), "--root", str(self.state), *args],
            cwd=self.backend,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
        )
        lines = [line for line in result.stdout.decode("utf-8", errors="strict").splitlines() if line.strip()]
        assert len(lines) == 1, {"stdout": result.stdout.decode(errors="replace"), "stderr": result.stderr.decode(errors="replace")}
        value = json.loads(lines[0])
        assert isinstance(value, dict), value
        return result.returncode, value

    def process(self, *args: str) -> subprocess.Popen[bytes]:
        return subprocess.Popen(
            [sys.executable, str(self.cli), "--root", str(self.state), *args],
            cwd=self.backend,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

    def close(self) -> None:
        self.temp.cleanup()

    def __enter__(self) -> "Harness":
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()


def error(value: dict[str, object]) -> str:
    detail = value.get("error")
    assert value.get("ok") is False and isinstance(detail, dict), value
    code = detail.get("code")
    assert isinstance(code, str), value
    return code


class Checks:
    def __init__(self, workspace: pathlib.Path) -> None:
        self.workspace = workspace
        self.fixture = workspace / "fixture"
        self.details: dict[str, tuple[bool, str]] = {}

    def record(self, key: str, fn) -> None:
        try:
            evidence = fn()
            self.details[key] = (True, str(evidence or "check passed"))
        except Exception as exc:
            self.details[key] = (False, f"{type(exc).__name__}: {exc}")

    def cli_contract(self) -> str:
        with Harness(self.fixture) as h:
            rc, value = h.command("get")
            assert rc == 2 and error(value), (rc, value)
            rc, value = h.command("get", "--key", "missing")
            assert rc == 3 and error(value) == "NOT_FOUND"
            rc, value = h.command("put", "--key", "a", "--value", "A", "--request-id", "r1", "--expected-version", "0")
            assert rc == 0 and value.get("ok") is True
            rc, value = h.command("put", "--key", "a", "--value", "B", "--request-id", "r2", "--expected-version", "0")
            assert rc == 4 and error(value) == "VERSION_CONFLICT"
            rc, value = h.command("put", "--key", "b", "--value", "B", "--request-id", "r1", "--expected-version", "0")
            assert rc == 5 and error(value) == "IDEMPOTENCY_CONFLICT"
        return "CLI emitted one JSON object and stable usage/not-found/version/idempotency exits"

    def persistence(self) -> str:
        with Harness(self.fixture) as h:
            rc, beta = h.command("put", "--key", "beta", "--value", "B", "--request-id", "r-beta", "--expected-version", "0")
            rc2, alpha = h.command("put", "--key", "alpha", "--value", "A", "--request-id", "r-alpha", "--expected-version", "0")
            assert rc == rc2 == 0 and beta["version"] == 1 and alpha["version"] == 2
            rc, got = h.command("get", "--key", "alpha")
            assert rc == 0 and got == {"ok": True, "key": "alpha", "value": "A", "version": 2}
            rc, listed = h.command("list")
            assert rc == 0 and [item["key"] for item in listed["items"]] == ["alpha", "beta"]
        return "put/get/list persisted exact values and versions across fresh CLI processes"

    def idempotent_replay(self) -> str:
        with Harness(self.fixture) as h:
            args = ("put", "--key", "a", "--value", "A", "--request-id", "same", "--expected-version", "0")
            rc, first = h.command(*args)
            before = (h.state / "events.log").read_bytes()
            rc2, second = h.command(*args)
            after = (h.state / "events.log").read_bytes()
            assert rc == rc2 == 0 and first["seq"] == second["seq"] == 1
            assert first["replayed"] is False and second["replayed"] is True
            assert before == after
        return "identical request replay returned seq=1 and appended zero bytes"

    def idempotency_conflict(self) -> str:
        with Harness(self.fixture) as h:
            h.command("put", "--key", "a", "--value", "A", "--request-id", "r", "--expected-version", "0")
            before = (h.state / "events.log").read_bytes()
            rc, value = h.command("put", "--key", "a", "--value", "B", "--request-id", "r", "--expected-version", "1")
            assert rc == 5 and error(value) == "IDEMPOTENCY_CONFLICT"
            assert (h.state / "events.log").read_bytes() == before
            assert h.command("get", "--key", "a")[1]["value"] == "A"
        return "request_id conflict preserved log and live value"

    def version_conflict(self) -> str:
        with Harness(self.fixture) as h:
            h.command("put", "--key", "a", "--value", "A", "--request-id", "r1", "--expected-version", "0")
            before = (h.state / "events.log").read_bytes()
            rc, value = h.command("put", "--key", "a", "--value", "B", "--request-id", "r2", "--expected-version", "0")
            assert rc == 4 and error(value) == "VERSION_CONFLICT"
            assert (h.state / "events.log").read_bytes() == before
            assert h.command("get", "--key", "a")[1]["version"] == 1
        return "stale expected_version caused a side-effect-free VERSION_CONFLICT"

    def tombstone(self) -> str:
        with Harness(self.fixture) as h:
            put = h.command("put", "--key", "a", "--value", "A", "--request-id", "r1", "--expected-version", "0")[1]
            deleted = h.command("delete", "--key", "a", "--request-id", "r2", "--expected-version", str(put["version"]))[1]
            assert deleted["version"] == 2
            rc, value = h.command("get", "--key", "a")
            assert rc == 3 and error(value) == "NOT_FOUND"
            assert h.command("list")[1]["items"] == []
            resurrected = h.command("put", "--key", "a", "--value", "A2", "--request-id", "r3", "--expected-version", "2")[1]
            assert resurrected["version"] == 3
            rc, value = h.command("delete", "--key", "never", "--request-id", "r4", "--expected-version", "0")
            assert rc == 3 and error(value) == "NOT_FOUND"
        return "delete hid live data, retained version=2, and allowed versioned resurrection"

    def canonical_log(self) -> str:
        with Harness(self.fixture) as h:
            h.command("put", "--key", "天气", "--value", "晴", "--request-id", "r-cn", "--expected-version", "0")
            lines = (h.state / "events.log").read_bytes().splitlines()
            assert len(lines) == 1
            record = json.loads(lines[0].decode("utf-8"))
            assert set(record) == RECORD_FIELDS
            modes = []
            for ensure_ascii in (False, True):
                rendered = json.dumps(record, ensure_ascii=ensure_ascii, sort_keys=True, separators=(",", ":")).encode("utf-8")
                expected = f"{zlib.crc32(canonical_body(record, ensure_ascii=ensure_ascii)) & 0xFFFFFFFF:08x}"
                if lines[0] == rendered and record["crc32"] == expected:
                    modes.append(ensure_ascii)
            assert len(modes) == 1, {"raw": lines[0], "crc32": record["crc32"]}
        return "events.log matched canonical UTF-8 JSON and independently computed CRC-32"

    def truncated_tail(self) -> str:
        with Harness(self.fixture) as h:
            h.command("put", "--key", "a", "--value", "A", "--request-id", "r1", "--expected-version", "0")
            log = h.state / "events.log"
            healthy = log.read_bytes()
            tail = b'{"crc32":"dead'
            with log.open("ab") as handle:
                handle.write(tail)
            rc, value = h.command("get", "--key", "a")
            assert rc == 6 and error(value) == "RECOVERY_REQUIRED"
            rc, recovered = h.command("recover")
            assert rc == 0 and recovered["truncated_bytes"] == len(tail)
            assert log.read_bytes() == healthy and h.command("get", "--key", "a")[1]["value"] == "A"
        return "recover truncated an incomplete tail at the last valid byte boundary"

    def bad_crc_tail(self) -> str:
        with Harness(self.fixture) as h:
            h.command("put", "--key", "a", "--value", "A", "--request-id", "r1", "--expected-version", "0")
            log = h.state / "events.log"
            healthy = log.read_bytes()
            bad = bytearray(make_record(seq=2, op="put", key="b", value="B", request_id="r2", expected_version=0))
            marker = bad.find(b'"crc32":"') + len(b'"crc32":"')
            bad[marker] = ord("0") if bad[marker] != ord("0") else ord("1")
            with log.open("ab") as handle:
                handle.write(bad)
            assert h.command("list")[0] == 6
            rc, recovered = h.command("recover")
            assert rc == 0 and recovered["truncated_bytes"] == len(bad)
            assert log.read_bytes() == healthy and [item["key"] for item in h.command("list")[1]["items"]] == ["a"]
        return "recover removed a final CRC-invalid record and preserved committed state"

    def middle_corruption(self) -> str:
        with Harness(self.fixture) as h:
            for index, key in enumerate(("a", "b", "c"), start=1):
                h.command("put", "--key", key, "--value", key.upper(), "--request-id", f"r{index}", "--expected-version", "0")
            log = h.state / "events.log"
            lines = log.read_bytes().splitlines(keepends=True)
            bad = bytearray(lines[1])
            marker = bad.find(b'"crc32":"') + len(b'"crc32":"')
            bad[marker] = ord("0") if bad[marker] != ord("0") else ord("1")
            lines[1] = bytes(bad)
            log.write_bytes(b"".join(lines))
            frozen = log.read_bytes()
            for command in (("list",), ("recover",)):
                rc, value = h.command(*command)
                assert rc == 7 and error(value) == "CORRUPT_LOG", (rc, value)
                assert log.read_bytes() == frozen
        return "middle corruption produced read-only CORRUPT_LOG for normal and recover paths"

    def compact_state(self) -> str:
        with Harness(self.fixture) as h:
            h.command("put", "--key", "live", "--value", "L", "--request-id", "r1", "--expected-version", "0")
            h.command("put", "--key", "gone", "--value", "G", "--request-id", "r2", "--expected-version", "0")
            h.command("delete", "--key", "gone", "--request-id", "r3", "--expected-version", "2")
            rc, value = h.command("compact")
            assert rc == 0 and value["snapshot_seq"] == 3
            assert (h.state / "snapshot.json").is_file() and (h.state / "events.log").read_bytes() == b""
            assert h.command("get", "--key", "live")[1]["value"] == "L"
            assert h.command("get", "--key", "gone")[0] == 3
            assert [item["key"] for item in h.command("list")[1]["items"]] == ["live"]
        return "compact restored live and tombstoned states from snapshot with an empty log"

    def compact_ledger(self) -> str:
        with Harness(self.fixture) as h:
            args = ("put", "--key", "a", "--value", "A", "--request-id", "r1", "--expected-version", "0")
            first = h.command(*args)[1]
            h.command("compact")
            replay = h.command(*args)[1]
            assert replay["replayed"] is True and replay["seq"] == first["seq"] == 1
            assert (h.state / "events.log").read_bytes() == b""
            next_value = h.command("put", "--key", "b", "--value", "B", "--request-id", "r2", "--expected-version", "0")[1]
            assert next_value["seq"] == 2
        return "snapshot retained request replay data and next global seq"

    def snapshot_commit(self) -> str:
        with Harness(self.fixture) as h:
            h.command("put", "--key", "a", "--value", "A", "--request-id", "r1", "--expected-version", "0")
            (h.state / "snapshot.json.tmp").write_text("uncommitted garbage", encoding="utf-8")
            assert h.command("get", "--key", "a")[1]["value"] == "A"
            h.command("compact")
            (h.state / "snapshot.json").write_text("committed garbage", encoding="utf-8")
            rc, value = h.command("get", "--key", "a")
            assert rc == 8 and error(value) == "CORRUPT_SNAPSHOT"
        return "stale snapshot.tmp was ignored and malformed committed snapshot was rejected"

    def concurrent_writers(self) -> str:
        with Harness(self.fixture) as h:
            processes = [h.process("put", "--key", f"k{i:02}", "--value", str(i), "--request-id", f"r{i:02}", "--expected-version", "0") for i in range(20)]
            results = []
            for process in processes:
                out, err = process.communicate(timeout=15)
                assert process.returncode == 0, (out.decode(errors="replace"), err.decode(errors="replace"))
                results.append(json.loads(out))
            assert len({value["seq"] for value in results}) == 20
            listed = h.command("list")[1]["items"]
            assert len(listed) == 20 and [item["key"] for item in listed] == [f"k{i:02}" for i in range(20)]
        return "20 concurrent processes committed unique seq values with no lost keys"

    def concurrent_conflict(self) -> str:
        with Harness(self.fixture) as h:
            h.command("put", "--key", "shared", "--value", "initial", "--request-id", "seed", "--expected-version", "0")
            processes = [h.process("put", "--key", "shared", "--value", f"v{i}", "--request-id", f"r{i}", "--expected-version", "1") for i in range(8)]
            exits = []
            for process in processes:
                out, err = process.communicate(timeout=15)
                assert out.strip(), err.decode(errors="replace")
                exits.append(process.returncode)
            assert exits.count(0) == 1 and exits.count(4) == 7, exits
            assert h.command("get", "--key", "shared")[1]["version"] == 2
        return "one of eight same-version writers committed and seven observed VERSION_CONFLICT"

    def stdlib_only(self) -> str:
        backend = self.fixture / "backend"
        local = {path.stem for path in backend.glob("*.py")}
        stdlib_root = pathlib.Path(sysconfig.get_paths()["stdlib"]).resolve()
        external: set[str] = set()
        for path in backend.glob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    roots = [alias.name.split(".")[0] for alias in node.names]
                elif isinstance(node, ast.ImportFrom) and node.module:
                    roots = [node.module.split(".")[0]]
                else:
                    continue
                for root in roots:
                    if root in local:
                        continue
                    spec = importlib.util.find_spec(root)
                    origin = None if spec is None else spec.origin
                    if origin in ("built-in", "frozen"):
                        continue
                    if origin is None:
                        external.add(root)
                        continue
                    resolved = pathlib.Path(origin).resolve()
                    if stdlib_root not in resolved.parents or "site-packages" in resolved.parts:
                        external.add(root)
        assert not external, sorted(external)
        return "backend imports resolve to Python stdlib or local modules"

    def spec_document(self) -> str:
        spec_path = self.workspace / "docs" / "spec" / "journal-index-recovery" / "spec.md"
        assert spec_path.is_file(), "spec.md missing"
        body = spec_path.read_text(encoding="utf-8")
        assert "> spec_version: 3" in body
        assert "待确认" not in body or "待确认：无" in body
        for token in ("影响边界", "判断依据", "建模覆盖", "验收清单", "SC_01", "RECOVERY_REQUIRED", "CORRUPT_LOG"):
            assert token in body, token
        for module in ("cli.py", "record.py", "store.py", "locking.py"):
            assert module in body, module
        tool = self.workspace / "tools" / "xdev.py"
        result = subprocess.run([sys.executable, str(tool), "validate", str(spec_path.parent), "--json"], cwd=self.workspace, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=30)
        assert result.returncode == 0, result.stdout.decode(errors="replace")[-3000:]
        return f"{spec_path} validates with stable scenarios and all four implementation modules"

    def req_checklist(self) -> str:
        root = self.workspace / "docs" / "spec" / "journal-index-recovery"
        spec = root / "spec.md"
        checklists = sorted(root.glob("tasks/*/dev-checklist.md"))
        assert checklists, "dev-checklist.md missing"
        import re
        spec_refs = set(re.findall(r"Scenario (SC_\d{2})", spec.read_text(encoding="utf-8")))
        task_refs: set[str] = set()
        tool = self.workspace / "tools" / "xdev.py"
        for path in checklists:
            body = path.read_text(encoding="utf-8")
            assert "risk:" in body and "Scenario IDs" in body
            task_refs.update(re.findall(r"SC_\d{2}", body))
            result = subprocess.run([sys.executable, str(tool), "validate", str(path.parent), "--json"], cwd=self.workspace, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=30)
            assert result.returncode == 0, result.stdout.decode(errors="replace")[-3000:]
        assert spec_refs and spec_refs <= task_refs, (sorted(spec_refs), sorted(task_refs))
        return f"{len(checklists)} checklist(s) cover all {len(spec_refs)} scenarios and validate"

    def verify_evidence(self) -> str:
        root = self.workspace / "docs" / "spec" / "journal-index-recovery"
        reports = sorted(root.glob("tasks/*/dev-report*.md"))
        assert reports, "dev-report missing"
        body = "\n".join(path.read_text(encoding="utf-8") for path in reports)
        assert body.count("```verify") >= 3 and "mode: auto" in body
        assert "unit" in body.lower() and "smoke" in body.lower() and "e2e" in body.lower()
        tool = self.workspace / "tools" / "xdev.py"
        for task_dir in sorted({path.parent for path in reports}):
            result = subprocess.run([sys.executable, str(tool), "verify", str(task_dir), "--json"], cwd=self.workspace, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=180)
            assert result.returncode == 0, result.stdout.decode(errors="replace")[-5000:]
        return f"{len(reports)} dev-report file(s) replayed unit, smoke, and e2e evidence"

    def hygiene(self) -> str:
        assert not (self.workspace / ".git").exists()
        for relative in ("task", "fixture/README.md"):
            candidate = self.workspace / relative
            oracle = ORACLE_CASE / relative
            if candidate.is_file():
                assert candidate.read_bytes() == oracle.read_bytes(), relative
            else:
                candidate_files = sorted(path.relative_to(candidate) for path in candidate.rglob("*") if path.is_file())
                oracle_files = sorted(path.relative_to(oracle) for path in oracle.rglob("*") if path.is_file())
                assert candidate_files == oracle_files, relative
                for item in oracle_files:
                    assert (candidate / item).read_bytes() == (oracle / item).read_bytes(), f"{relative}/{item}"
        for path in self.workspace.rglob("*.pid"):
            raise AssertionError(f"pid leftover: {path}")
        return "task and fixture README remained byte-identical; no nested git or pid state"


EXPECTATIONS = [
    ("CLI JSON 结构与稳定退出码符合契约。", "cli_contract"),
    ("put/get/list 跨进程保持值、version 与排序。", "persistence"),
    ("同 request_id 同内容重试返回原 seq 且不追加。", "idempotent_replay"),
    ("同 request_id 不同内容产生无副作用幂等冲突。", "idempotency_conflict"),
    ("expected_version 冲突保持状态稳定。", "version_conflict"),
    ("delete、tombstone version 与 NOT_FOUND 语义正确。", "tombstone"),
    ("events.log 使用规范 JSON 与可独立校验 CRC-32。", "canonical_log"),
    ("截断尾部触发恢复并精确截断。", "truncated_tail"),
    ("最后记录 CRC 损坏可恢复且既有状态稳定。", "bad_crc_tail"),
    ("中间记录损坏只读失败且 recover 拒绝改写。", "middle_corruption"),
    ("compact 通过 snapshot + 空 log 恢复 live/tombstone 状态。", "compact_state"),
    ("compact 保留幂等账本与后续 seq 单调性。", "compact_ledger"),
    ("未提交 snapshot 临时文件被忽略，损坏的已提交 snapshot 被拒绝。", "snapshot_commit"),
    ("多进程并发写不同 key 无丢失且 seq 唯一。", "concurrent_writers"),
    ("同 key 同 expected_version 并发更新只有一个成功。", "concurrent_conflict"),
    ("backend 运行时代码只依赖 Python 标准库与本地模块。", "stdlib_only"),
    ("spec3 覆盖持久化状态机、损坏分类、并发不变量与稳定 Scenario。", "spec_document"),
    ("req3 checklist 完整覆盖 Scenario 且通过机械校验。", "req_checklist"),
    ("dev-report 提供可复跑的 unit、smoke、e2e 证据。", "verify_evidence"),
    ("运行产物保持在声明范围且输入未被改写。", "hygiene"),
]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("workspace", type=pathlib.Path)
    parser.add_argument("--output", type=pathlib.Path)
    args = parser.parse_args()
    checks = Checks(args.workspace.resolve())
    for _text, method in EXPECTATIONS:
        checks.record(method, getattr(checks, method))
    expectations = []
    for text, method in EXPECTATIONS:
        passed, evidence = checks.details[method]
        expectations.append({"text": text, "passed": passed, "evidence": evidence})
    passed = sum(1 for item in expectations if item["passed"])
    critical_passed = all(checks.details[method][0] for _text, method in EXPECTATIONS[:19])
    result = {
        "expectations": expectations,
        "summary": {"passed": passed, "failed": len(expectations) - passed, "total": len(expectations), "pass_rate": passed / len(expectations)},
        "quality_score": passed * 5,
        "critical_gate_passed": critical_passed,
        "execution_metrics": {"total_tool_calls": 0, "errors_encountered": len(expectations) - passed},
        "eval_feedback": {"suggestions": [], "overall": "Deterministic local CLI, corruption, compaction, process-concurrency, and pipeline checks."},
    }
    rendered = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 0 if passed == 20 and critical_passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
