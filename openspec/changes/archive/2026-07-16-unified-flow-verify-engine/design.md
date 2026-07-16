## Context

### 当前仓库事实

- `tools/xdev.py` 已提供 task scaffold、instructions、V8-V11 校验，以及 checklist 的 status/graph 编排。
- `x-verify` 仍让 LLM 从 dev-report 表格和 README Smoke/E2E 两处复跑命令；`x-qa-gate` 仍读取 changelog 并含 qdev 分支。
- x-req、x-dev 与 x-qdev 已停止生产 changelog，Gate 与 cr 的剩余消费路径会使新 task 缺少输入。
- 当前主 specs 已描述 task 产物与精简规划契约；本 change 直接对其写 delta。

### 约束

- Python 运行时代码仅用标准库；测试使用 `unittest` 和临时目录 fixture。
- 历史 `dev-pipeline/tasks/` 与已归档 OpenSpec change 不迁移、不清理。
- 不保留 qdev/x-plan alias、旧 dev-report 表格式解析或双轨风险字段。
- 维持 fix-counter 与三轮上限的既有规则；不新增依赖、版本号或发布记录。

## Goals / Non-Goals

**Goals:**

- 让命令复跑、退出码比较、关键输出检查和自动场景覆盖对账在确定性工具层完成。
- 让 Q0-Q3 成为 task 数据，替代按 skill 入口分叉的流程。
- 让 x-verify 和 x-qa-gate 只消费必要证据，且所有高严重度 finding 有可复现的定位。
- 删除 qdev/x-plan 与所有活跃引用，令新 task 只有一条风险路由主线。

**Non-Goals:**

- 不实现 capability 自动归档、delta 指纹或任何 audit 系列改造。
- 不改历史 task 与归档 change，也不为其提供新格式兼容解析。
- 不改变 fix-counter、三轮上限或 qa-gate 的 reviewer 类型；只改变它们的输入与路由依据。

## Decisions

### Decision 1: fenced verify 块是唯一自动验证输入

dev-report 使用 `verify` fenced block 表达 `id`、`scenario`、`cmd`、`cwd`、`expect_exit`、可重复的 `expect_contains`、`timeout`、`mode` 与 manual `steps`。`xdev.py verify` 解析并执行 auto 块，manual 块只进入结果清单。未知 key、重复 ID、缺少必要字段与非法模式统一返回退出码 2；执行失败与自动场景未覆盖返回退出码 1。

备选方案是保留 Markdown 表并增加解析器。该表无法可靠表达重复输出断言、manual 步骤和 scenario 回指，且会继续保留旧 schema；本 change 采用单一 fenced schema。

### Decision 2: README 验收 Scenario 是覆盖对账真源

README 头部的 `risk:` 是 Q0-Q3 唯一风险字段；`## 验收` 下每个 Requirement 至少有一个 Scenario，每个 Scenario 有 WHEN、THEN 和 `验证: auto|manual`。verify 收集所有 auto 场景名并要求每个场景至少被一个 `scenario:` 回指的 auto verify 块覆盖；名称在 strip 后精确匹配。

备选方案是让 x-verify 继续同时解释 README 散文与 dev-report 命令。该方案会把相同事实再交给 LLM 判读一次；本 change 让 README 只定义验收，dev-report 只提供可执行证据。

### Decision 3: Q0-Q3 是 task 字段，流程由字段路由

x-req 在创建或更新 task 时判断 Q0-Q3 并写入 README。Q0/Q1 跳过确认，使用 lite README 契约并续接 x-dev；Q2/Q3 在一次确认中展示风险并在确认后续接全链。x-dev 完成 verify 后，Q0/Q1 交付，Q2 进入 RC，Q3 进入 R1→R2→R3。

备选方案是保留 qdev 作为轻量入口。该方案把风险规则、模板和收尾门禁复制到两个入口；本 change 选择单一 task 契约与单一路由。

### Decision 4: skills 只诊断失败并读取最小输入

x-verify 运行 verify 引擎：全过只给对话回执，有失败或 uncovered 才写 verify 报告并交 x-fix。qa-gate 按 README risk 选择 reviewer，并向每个 reviewer 传入精确的 README 节、diff、dev-report verify 块或测试文件。P0 finding 必须能给出 `file:line` 和复现依据；无法确认的 finding 降一级。

备选方案是以全量 task 文档、changelog 和 qdev 分支继续喂给 reviewer。该方案扩大上下文且会读取新流程不再生成的 changelog；本 change 只传与 reviewer 目标对应的证据。

## Risks / Trade-offs

- [Risk] README 场景改名而 dev-report 未同步会产生 uncovered。→ Mitigation：JSON 同时列出 README auto 场景与 verify 回指；这是可见的证据漂移。
- [Risk] 旧 task 的表格式 dev-report 无法通过新 verify。→ Mitigation：历史 task 保持原状，新 task 只按新模板生产；不提供双格式兼容。
- [Risk] Q0/Q1 免确认会低估风险。→ Mitigation：x-req 记录定级依据，用户随时可指令按 Q2 处理；Q3 判据集中在 x-req。
- [Risk] 删除 qdev/x-plan 会使旧命令失效。→ Mitigation：发行面明确列出 `/x-req` 入口，删除不提供 alias 的路线符合 change 的破坏性契约。

## Migration Plan

1. 先完成 verify 引擎、V11/V12、模板和覆盖测试。
2. 更新 x-req、x-dev、x-verify、x-qa-gate 与关联 references，使运行时读写契约与引擎一致。
3. 删除 qdev/x-plan，改写活跃引用及发行文案。
4. 运行单测、fixture evidence、OpenSpec strict 校验和引用清理检查；按代码测试、skills、发行面三段本地提交。
5. 归档 change，更新主 specs。回滚按相反的提交边界进行；历史档案不需要迁移回滚。

## Open Questions

无。`timeout` 只在 verify 块显式出现时生效；无显式超时的命令不引入新的默认值。失败 JSON 保留合并 stdout/stderr，以避免新增输出截断阈值。
