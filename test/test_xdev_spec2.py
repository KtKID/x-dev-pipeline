#!/usr/bin/env python3
"""x-spec2 包检测、V2 规则集与存量 profile 回归测试。"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import sys


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import xdev  # noqa: E402


def valid_spec(
    requirement: str = "可验证需求",
    data_flow: str = "modules.md#模块总览",
    *,
    trace_target: str | None = None,
    trace_location: str | None = None,
    judgments: str = "",
) -> str:
    target = trace_target or requirement
    location = trace_location or f"spec.md#requirement-{requirement}"
    return f"""> spec_version: 2

# demo

## 需求说明

### 需求本质

形成稳定需求。

### 系统目标

需求可进入 x-req。

### 范围边界

- 包含需求建模。

### 关键约束

- 保持旧版兼容。

### 系统不变量

- task 由 x-req 产生。

## 用户要求追溯

| U-ID | 用户原话要求 | 对应目标 | 落实位置 |
|---|---|---|---|
| U1 | "需要可验证" | {target} | {location} |

## 判断依据

| J-ID | 判断 | 来源类型 | 证据或推断说明 | 确认状态 |
|---|---|---|---|---|
{judgments}

## 建模覆盖声明

| 元组 | 落点或不适用理由 |
|---|---|
| 数据流 | {data_flow} |
| 状态 | 不适用：没有持久状态 |
| 时序 | 不适用：没有顺序约束 |
| 资源 | 不适用：没有资源生命周期 |
| 不变量 | spec.md#系统不变量 |
| 故障 | 不适用：没有外部依赖 |

## 验收

### Requirement: {requirement}

系统 SHALL 生成可验证需求。

#### Scenario: 需求通过验证

- **WHEN** 校验 spec2 包
- **THEN** 返回零 issue
- 验证: auto
"""


def valid_modules(
    requirement: str = "可验证需求",
    status: str = "可进入 x-req",
    *,
    decision_ref: str = "D1",
    decisions: str = "| D1 | 独立需求编写模块 | U1 | 隔离需求建模职责 | 放入调用方：边界混合 | 用户改为指定其他归属 |",
) -> str:
    return f"""# 模块设计

## 模块总览

| 模块 | 职责 | 依赖 | 边界类/对外契约 | 风险 | 决策回指 | 状态 | 回指 Requirement |
|---|---|---|---|---|---|---|---|
| Spec Writer | 写需求 | 无 | SpecService | 低 | {decision_ref} | {status} | {requirement} |

## 关键决策

| D-ID | 决策 | 依据 U/J | 选择理由 | 备选与否决原因 | 重评条件 |
|---|---|---|---|---|---|
{decisions}

## 模块详情

### 模块：Spec Writer

负责写需求。
"""


def write_spec2(pkg: Path, *, spec: str | None = None, modules: str | None = None) -> None:
    pkg.mkdir(parents=True, exist_ok=True)
    if spec is not None:
        (pkg / "spec.md").write_text(spec, encoding="utf-8")
    if modules is not None:
        (pkg / "modules.md").write_text(modules, encoding="utf-8")


class TestSpec2Validation(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def validate(self, pkg: Path) -> list[dict]:
        result = xdev.validate_pkg(pkg, include_legacy=False)
        self.assertEqual(result["type"], "spec2")
        return result["issues"]

    def test_valid_minimum_package_has_zero_issues(self):
        pkg = self.root / "valid"
        write_spec2(pkg, spec=valid_spec(), modules=valid_modules())
        self.assertEqual(self.validate(pkg), [])

    def test_marker_or_modules_detects_partial_spec2(self):
        marker_only = self.root / "marker-only"
        write_spec2(marker_only, spec=valid_spec())
        messages = "\n".join(item["msg"] for item in self.validate(marker_only))
        self.assertIn("modules.md", messages)

        modules_only = self.root / "modules-only"
        write_spec2(modules_only, modules=valid_modules())
        messages = "\n".join(item["msg"] for item in self.validate(modules_only))
        self.assertIn("spec.md", messages)
        self.assertIn("spec_version", messages)

    def test_task_artifacts_are_rejected_inside_spec2(self):
        pkg = self.root / "task-leak"
        write_spec2(pkg, spec=valid_spec(), modules=valid_modules())
        (pkg / "tasks.md").write_text("# leaked", encoding="utf-8")
        messages = "\n".join(item["msg"] for item in self.validate(pkg))
        self.assertIn("不得包含 task 产物", messages)

    def test_spec2_scenario_allows_missing_given_and_requires_validation(self):
        pkg = self.root / "scenario"
        write_spec2(pkg, spec=valid_spec(), modules=valid_modules())
        self.assertEqual(self.validate(pkg), [])

        broken = valid_spec().replace("- 验证: auto\n", "")
        (pkg / "spec.md").write_text(broken, encoding="utf-8")
        messages = "\n".join(item["msg"] for item in self.validate(pkg) if item["rule"] == "V3")
        self.assertIn("验证", messages)
        self.assertNotIn("GIVEN", messages)

    def test_modeling_requires_all_six_rows_and_meaningful_absence(self):
        pkg = self.root / "modeling"
        broken = valid_spec().replace("| 故障 | 不适用：没有外部依赖 |\n", "")
        broken = broken.replace("不适用：没有顺序约束", "不适用：")
        write_spec2(pkg, spec=broken, modules=valid_modules())
        messages = "\n".join(item["msg"] for item in self.validate(pkg) if item["rule"] == "V14")
        self.assertIn("缺少元组：故障", messages)
        self.assertIn("不适用理由为空", messages)

    def test_modeling_rejects_dangling_file_or_anchor(self):
        pkg = self.root / "dangling-model"
        write_spec2(pkg, spec=valid_spec(data_flow="design.md#缺失段落"), modules=valid_modules())
        messages = "\n".join(item["msg"] for item in self.validate(pkg))
        self.assertIn("落点文件不存在", messages)
        self.assertIn("design.md", messages)

    def test_user_trace_requires_existing_unique_requirement_and_location(self):
        pkg = self.root / "trace"
        broken = valid_spec().replace(
            '| U1 | "需要可验证" | 可验证需求 | spec.md#requirement-可验证需求 |',
            '| U1 | "需要可验证" | 不存在需求 |  |',
        )
        write_spec2(pkg, spec=broken, modules=valid_modules())
        messages = "\n".join(item["msg"] for item in self.validate(pkg) if item["rule"] == "V15")
        self.assertIn("不存在或不唯一", messages)
        self.assertIn("缺少落实位置", messages)

    def test_reasoning_rejects_duplicate_missing_and_orphan_j(self):
        pkg = self.root / "bad-judgments"
        judgments = """| J1 | 代码现状 | 仓库事实 | repo:src/a.py | 已确认 |
| J1 | 重复判断 | LLM 推断 | 由接口形状推断 | 待确认 |
| J2 | 缺字段 |  |  |  |
| J3 | 无消费者 | 仓库事实 | repo:src/orphan.py | 已确认 |"""
        spec = valid_spec(judgments=judgments).replace(
            "系统 SHALL 生成可验证需求。",
            "系统 SHALL 生成可验证需求。依据：J1。",
        )
        write_spec2(pkg, spec=spec, modules=valid_modules())
        messages = "\n".join(item["msg"] for item in self.validate(pkg) if item["rule"] == "V18")
        self.assertIn("J-ID 重名：J1", messages)
        self.assertIn("J2", messages)
        self.assertIn("孤儿 J：J3", messages)

    def test_reasoning_rejects_dangling_refs_and_decision_without_basis(self):
        pkg = self.root / "bad-decisions"
        decisions = """| D1 | 缺依据 |  | 仍然选择 | 合并：职责混合 | 需求改变 |
| D2 | 悬空依据 | U9、J9 | 保持隔离 | 合并：职责混合 | 依赖变化 |
| D2 | 重复决策 | U1 | 保持隔离 | 合并：职责混合 | 依赖变化 |
| D3 | 无消费者 | U1 | 保持独立 | 合并：职责混合 | 需求改变 |"""
        write_spec2(pkg, spec=valid_spec(), modules=valid_modules(decision_ref="D1、D2", decisions=decisions))
        messages = "\n".join(item["msg"] for item in self.validate(pkg) if item["rule"] == "V18")
        self.assertIn("D 依据缺少 U/J 引用：D1", messages)
        self.assertIn("D-ID 重名：D2", messages)
        self.assertIn("引用悬空：U9", messages)
        self.assertIn("引用悬空：J9", messages)
        self.assertIn("孤儿 D：D3", messages)

    def test_design_may_reference_but_must_not_define_decisions(self):
        pkg = self.root / "design-decision-source"
        write_spec2(pkg, spec=valid_spec(data_flow="design.md#数据流"), modules=valid_modules())
        (pkg / "design.md").write_text("# 动态模型\n\n## 数据流\n\n关联决策：D1。\n", encoding="utf-8")
        self.assertEqual(self.validate(pkg), [])

        (pkg / "design.md").write_text(
            "# 动态模型\n\n## 数据流\n\n关联决策：D1。\n\n"
            "| D-ID | 决策 | 依据 U/J |\n"
            "|---|---|---|\n"
            "| D1 | 在 design 中重复定义 | U1 |\n",
            encoding="utf-8",
        )
        messages = "\n".join(item["msg"] for item in self.validate(pkg) if item["rule"] == "V18")
        self.assertIn("design.md 不得定义 D-ID", messages)

    def test_structural_u_requires_existing_module(self):
        pkg = self.root / "bad-structural-u"
        spec = valid_spec(trace_target="不存在模块", trace_location="modules.md#模块总览")
        write_spec2(pkg, spec=spec, modules=valid_modules())
        messages = "\n".join(item["msg"] for item in self.validate(pkg) if item["rule"] == "V15")
        self.assertIn("回指目标不存在或不唯一：不存在模块", messages)

    def test_structural_u_and_atomic_mixed_requirements_pass(self):
        pkg = self.root / "structural-u"
        spec = valid_spec().replace(
            '| U1 | "需要可验证" | 可验证需求 | spec.md#requirement-可验证需求 |',
            '| U1 | "需要可验证" | 可验证需求 | spec.md#requirement-可验证需求 |\n'
            '| U2 | "模块边界使用 Spec Writer" | Spec Writer | modules.md#模块总览 |',
        )
        modules = valid_modules(decision_ref="U2", decisions="")
        write_spec2(pkg, spec=spec, modules=modules)
        self.assertEqual(self.validate(pkg), [])

    def test_two_file_package_with_decision_and_pulled_j_passes(self):
        pkg = self.root / "two-file-decision"
        spec = valid_spec(judgments="| J1 | 写入职责需要隔离 | 仓库事实 | repo:tools/xdev.py | 已确认 |")
        modules = valid_modules(
            decisions="| D1 | 独立需求编写模块 | U1、J1 | 隔离需求建模职责 | 放入调用方：边界混合 | 用户改为指定其他归属 |"
        )
        write_spec2(pkg, spec=spec, modules=modules)
        self.assertEqual(self.validate(pkg), [])

    def test_modules_check_both_reference_directions(self):
        pkg = self.root / "module-refs"
        write_spec2(pkg, spec=valid_spec(), modules=valid_modules("悬空需求"))
        messages = "\n".join(item["msg"] for item in self.validate(pkg) if item["rule"] == "V16")
        self.assertIn("不存在或不唯一", messages)
        self.assertIn("未被任何模块承接：可验证需求", messages)

    def test_modules_reject_invalid_status(self):
        pkg = self.root / "status"
        write_spec2(pkg, spec=valid_spec(), modules=valid_modules(status="差不多"))
        messages = "\n".join(item["msg"] for item in self.validate(pkg) if item["rule"] == "V16")
        self.assertIn("状态取值非法", messages)

    def test_duplicate_requirement_name_is_ambiguous(self):
        pkg = self.root / "duplicate"
        duplicate = valid_spec() + """
### Requirement: 可验证需求

#### Scenario: 第二场景

- **WHEN** 再次校验
- **THEN** 结果明确
- 验证: manual
"""
        write_spec2(pkg, spec=duplicate, modules=valid_modules())
        messages = "\n".join(item["msg"] for item in self.validate(pkg))
        self.assertIn("Requirement 名重名", messages)

    def test_design_is_required_when_referenced_and_rejected_when_empty(self):
        pkg = self.root / "design"
        write_spec2(pkg, spec=valid_spec(data_flow="design.md#数据流"), modules=valid_modules())
        messages = "\n".join(item["msg"] for item in self.validate(pkg))
        self.assertIn("design.md", messages)

        (pkg / "design.md").write_text("# 动态模型\n\n## 数据流\n\nA → B。\n", encoding="utf-8")
        self.assertEqual(self.validate(pkg), [])

        (pkg / "spec.md").write_text(valid_spec(), encoding="utf-8")
        messages = "\n".join(item["msg"] for item in self.validate(pkg) if item["rule"] == "V17")
        self.assertIn("仅在动态模型", messages)

    def test_spec2_links_allow_parent_and_spaces_but_reject_absolute(self):
        pkg = self.root / "links"
        write_spec2(pkg, spec=valid_spec(), modules=valid_modules())
        shared = self.root / "shared file.md"
        shared.write_text("# shared", encoding="utf-8")
        modules = valid_modules() + "\n[shared](<../shared file.md>)\n[repo](README.md)\n[web](https://example.com)\n"
        (pkg / "modules.md").write_text(modules, encoding="utf-8")
        self.assertEqual(self.validate(pkg), [])

        (pkg / "modules.md").write_text(modules + "\n[local](/tmp/machine.md)\n", encoding="utf-8")
        messages = "\n".join(item["msg"] for item in self.validate(pkg) if item["rule"] == "V2")
        self.assertIn("机器绑定绝对路径", messages)


class TestSpec2ProfileRegression(unittest.TestCase):
    def test_openspec_capability_keeps_legacy_scenario_contract(self):
        spec = ROOT / "openspec" / "specs" / "xdev-task-artifact-engine"
        result = xdev.validate_pkg(spec, include_legacy=False)
        self.assertEqual(result["type"], "capability")
        self.assertEqual(result["issues"], [])

    def test_spec7_detection_stays_on_existing_path(self):
        with tempfile.TemporaryDirectory() as raw:
            pkg = Path(raw) / "spec7"
            pkg.mkdir()
            (pkg / "01-goals-and-boundaries.md").write_text("# old", encoding="utf-8")
            result = xdev.validate_pkg(pkg, include_legacy=False)
            self.assertEqual(result["type"], "spec7")
            self.assertTrue(any(item["rule"] == "V1" for item in result["issues"]))


if __name__ == "__main__":
    unittest.main()
