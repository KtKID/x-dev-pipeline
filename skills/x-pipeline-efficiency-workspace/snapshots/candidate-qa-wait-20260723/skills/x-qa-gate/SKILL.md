---
name: x-qa-gate
description: |
  verify 通过后的质量审查。risk Q2 由一个 reviewer 一次完成 q1-intent、q2-correctness、q3-evidence；risk Q3 依次使用三个独立 reviewer：q1-intent 检查用户意图、需求、公开契约与实现是否对齐，q2-correctness 检查边界、失败路径、状态与并发是否正确，q3-evidence 检查测试和 verify 证据是否真实有效。发现 P0/P1 后登记 issue 并交 x-fix 批量修复，修复后增量复审。
---

# verify 后续质量审查

## 路由

verify exit 0 后进入质量审查。读取 task `dev-checklist.md` 头部的 `risk:`：

- Q0/Q1：直接交付，不启动 reviewer。
- Q2：启动一个综合 reviewer，一次覆盖 q1-intent、q2-correctness、q3-evidence。
- Q3：依次启动三个独立 reviewer，顺序为 q1-intent → q2-correctness → q3-evidence。

## 三类审查

### q1-intent

检查实现是否对齐用户意图、已确认需求、验收 Scenario、既有公开契约和声明的改动范围。

### q2-correctness

检查非法输入、边界条件、失败路径、状态转换、缓存、并发、幂等性和资源清理是否正确。

### q3-evidence

检查测试和 verify 证据是否真实触达改动路径，断言是否独立于实现，mock 是否保留真实契约，证据是否能击穿错误实现。

## 事实源

1. 用户原始请求、已确认 spec、既有公开契约。
2. 真实调用方、schema/数据约束、改动前测试契约。
3. spec2 的 Requirement/Scenario、系统不变量、modules/design；或 spec3 的目标、影响边界与不变量、判断依据、建模覆盖和直接 Scenarios。
4. dev-report verify 块、verify JSON 或失败报告、当前 diff。

## 输入裁剪

| Reviewer | 必读输入 |
|---|---|
| 综合 reviewer | diff + task 引用的 Scenario + 相关边界/不变量 + dev-report + 测试文件 |
| q1-intent | diff + 目标/Requirement + task 引用的 Scenario |
| q2-correctness | diff + 影响边界、不变量、建模覆盖及相关 modules/design |
| q3-evidence | diff + dev-report verify 块 + 测试文件 |

主 agent 提供文件路径、节名、`git diff --stat`、`git diff --name-only` 和按需 diff 命令。reviewer 按需读取源代码与测试文件。

## Token 约束与调度纪律

reviewer 调度的等待轮次会重复计入主 agent 的完整上下文。按以下规则保持审查独立性并限制 token：

1. 启动 reviewer 前一次性组装完整 prompt，包含任务边界、输入路径、按需 diff 命令和输出格式。
2. 每个 reviewer 只创建一次。运行期间保持其 turn 连续，禁止 `send_message`、`followup_task`、`interrupt_agent` 和重复派发。
3. 等待使用 `wait_agent(timeout_ms=60000)`。超时后先给用户一条短状态，再继续等待；省略 `list_agents` 轮询。
4. reviewer 完成后直接消费 FINAL_ANSWER。主 agent 只复核候选问题的定位和严重度，复用 reviewer 已给出的证据。
5. Q3 三个 reviewer 共享同一份 diff 路径清单，各自只读取输入裁剪表对应的内容。后一 reviewer 不接收前一 reviewer 的分析文本。
6. 无 P0/P1 时进入下一 reviewer；P2 统一登记，三个 reviewer 完成后一次处理。P0/P1 立即结束本轮并进入 issue 登记与 x-fix。
7. 同一轮候选按根因合并为一个 x-fix 批次。集中完成关联编辑，随后用一个聚焦测试命令和一次 verify 复跑收集证据；省略逐文件、逐测试的状态探测 turn。

## Review 纪律

- 每个 reviewer 独立、只读，只返回 review 回执；x-fix 负责改动。
- 每轮穷尽检查范围后一次返回全部问题候选，并声明“已检查范围内无其他 P0/P1”。
- 每条候选固定提供 `task`、`severity`、`loc`、`msg`；`task` 可为 `T2,T3`，`severity` 为 P0/P1/P2，`loc` 为 `file:line`，`msg` 为单条问题描述。
- reviewer 省略 issue ID。主 agent 调用 `flag` 后使用其 JSON `issue` 字段建立编号映射。
- P0 需要位置与可复现依据；证据不完整时降级。P0 或未处置 P1 使本轮 fail；P2 登记且保持非阻塞。

## issue 登记

主 agent 按 reviewer 返回顺序逐条执行：

```text
python3 tools/xdev.py flag <task-dir> --task T2,T3 --severity P0 \
    --loc src/a.py:10 --msg "空输入未处理" [--new-round] --json
```

1. 本轮第一条候选添加 `--new-round`；后续候选追加到同一 ledger。
2. 保存 JSON 返回的 `issue`、`downgraded`、`report`、`recovered`，把 issue ID 回填到交给 x-fix 的问题映射。
3. `recovered:true` 表示命令完成了上一笔 pending 事务；主 agent 使用原参数再次调用，完成本条候选登记。
4. `flag` 是 issue ledger 与 P0/P1 checklist 降级的唯一写入口。reviewer、子 agent 与 x-fix 保持这两处原样。
5. 本轮无问题时省略 ledger 创建，直接输出通过回执。

## 回流

本轮存在 P0/P1 时，主 agent 把带 `issue-<n>` 的完整问题映射交给 x-fix 批量修复。修复后复审对应 issue 与 fix diff；fix 扩大到新文件时纳入新文件，公开 API 签名变化时重做相关意图和契约对照。`reports/.fix-counter` 记录 verify 与质量审查共享的批量修复轮数，保留三轮上限；质量审查最终通过后写回 0。

## Prompt 模板

```text
Agent({
  description: "<combined/q1-intent/q2-correctness/q3-evidence> review round <N>",
  subagent_type: "general-purpose",
  prompt: <task root + 输入裁剪表指定路径/节 + diff 命令 + 一次穷尽范围 + 固定输出格式>
})
```

## 回执与状态

问题 ledger 路径以 `flag --json` 返回的 `report` 为准。通过时输出：

```text
✅ 质量审查通过 · <task> · risk Q2 combined / risk Q3 q1-intent→q2-correctness→q3-evidence · P0 ×0 · P1 ×0
```

失败回执列出 issue ID、严重度、task、位置和 x-fix 去向。最终通过后，主 agent 亲自确认复审结果并把已解除阻塞的 checklist 状态升为 `[x] ✅`。
