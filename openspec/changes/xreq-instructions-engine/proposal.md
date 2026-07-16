## 背景与动机

`x-req` 当前需要消耗模型上下文在子 agent 间复制需求、随 skill 全量加载格式规则，并由 LLM 审核多项可机械判定的约束。现有 `tools/xdev.py` 编排能力与 V1-V7 校验已经形成确定性边界，可以承接产物骨架、按需 instructions 和格式校验。

## 变更内容

- 在 `tools/xdev.py` 中加入确定性产物注册表，以及 `instructions` 和幂等 `scaffold` 命令。
- 扩展 `xdev.py validate`，加入显式 task 包规则 V8-V11，同时保持 spec 包 V1-V7 的既有行为。
- **破坏性变更（BREAKING）**：将 `x-req` task 包精简为必需的 `README.md` 与 `dev-checklist.md`；`diagram.md` 作为可选产物；新流程停止创建 `changelog.md`。
- **破坏性变更（BREAKING）**：将 `x-req` 的“子 agent 编写—主 agent 审核”循环改为主 agent 直接编写、机械校验和四项判断自审。
- **破坏性变更（BREAKING）**：统一移除活跃 `x-req`、`x-dev`、`x-qdev` 流程中的 changelog 生产与消费职责；执行记录由 `dev-report.md` 和 git 历史承载。
- 使用标准库单元测试和端到端 fixture 覆盖 instructions、scaffold、task 校验及 spec 校验回归。
- 更新仓库文档，说明精简后的产物集合与确定性规划流程。
- 后续 Gate 1、Gate 2、fix、cr、audit 改造，dev-report 命令清单治理，capability 归档自动化，指纹校验，第三方依赖，历史 task 迁移，以及 x-spec 七件套模型均保留在各自后续阶段。

## 能力

### 新增能力

- `xdev-task-artifact-engine`：查询 task 产物 instructions，以保留已有内容的方式生成 task 包骨架，并通过 V8-V11 校验 task 包结构。
- `xreq-lean-planning`：通过直接编写、确定性校验、判断自审和新的流水线记录策略，产出并维护精简的 x-req task 包。

### 修改能力

<!-- 本仓库当前没有已归档的 OpenSpec capability。 -->

## 影响范围

- 代码与测试：`tools/xdev.py`、`test/test_xdev_artifacts.py`、既有编排回归测试。
- 产品行为：`skills/x-req/SKILL.md`、`skills/x-req/templates/`、`skills/x-dev/`、`skills/x-qdev/`。
- 仓库文档：`README.md`、`README_zh.md`。
- 公共 CLI：新增 `instructions`、`scaffold` 子命令，并让 `validate` 识别 task 包。
- 迁移策略：历史 task 目录保持可读和原状；活跃流程停止创建 changelog 产物。
- 交付依赖：当前 `xdev-orchestration-engine` 工作区内容作为独立变更提交后，本变更进入实现。
