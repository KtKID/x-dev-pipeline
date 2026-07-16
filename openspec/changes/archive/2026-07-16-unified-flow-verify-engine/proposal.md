## Why

完整开发链路的固定成本已经从 task 产物与格式校验中移除，`x-qdev` 继续维护独立入口只会复制风险路由、验证和文档规则。现有 Gate ① 又把命令复跑、退出码和输出片段比对交给 LLM，造成可机械化的上下文消耗与不一致证据。

## What Changes

- 新增 `xdev.py verify`：解析 dev-report 的 fenced `verify` 块，复跑自动化命令，输出可机器消费的事实 JSON，并对账 README 自动验收场景。
- **BREAKING**：task README 的 `risk: Q0|Q1|Q2|Q3` 成为唯一风险真源；验收收敛为 Requirement/Scenario（GIVEN/WHEN/THEN）结构；dev-report 停止读取旧验证命令表与 risk 字段。
- **BREAKING**：移除 `x-qdev` 与 `x-plan` skills，统一由 x-req 的风险定级进入 x-dev、verify 和按风险选择的 qa-gate。
- 将 x-verify 收敛为 verify 引擎的失败诊断壳；重构 qa-gate 的风险路由、最小输入和置信度纪律；清偿活跃 skills 中的 changelog 依赖。
- 更新单元测试、模板、安装输出、插件示例及中英文 README；历史 task 与已归档变更保持原状。

## Capabilities

### New Capabilities

- `xdev-verification-engine`: 确定性解析、执行与报告 task 验证证据。
- `risk-routed-development-flow`: 基于 README risk 字段的统一开发、验证与质量门禁路由。

### Modified Capabilities

- `xdev-task-artifact-engine`: task README 校验从 DoD/Smoke 结构迁移到 risk 与验收 Scenario 契约。
- `xreq-lean-planning`: x-req 增加 Q0-Q3 定级、轻量路径与统一的后续执行路由。

## Impact

- 代码与测试：`tools/xdev.py`、`test/test_xdev_artifacts.py`、新增 `test/test_xdev_verify.py`。
- 工作流与模板：x-req、x-dev、x-verify、x-qa-gate、x-fix、x-cr、x-spec、x-multi-llm-align；删除 `skills/x-qdev/`、`skills/x-plan/`。
- 发行面：`README.md`、`README_zh.md`、`install.sh`、`.codex-plugin/plugin.json`。
- 范围不含 capability 自动归档、delta 指纹、audit skills、fix-counter 规则、版本发布与历史档案迁移。
