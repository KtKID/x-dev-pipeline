---
name: x-qa-gate
description: |
  xdev check 通过后的独立审查。按 checklist 的 risk 派一个只读 reviewer，单轮穷尽检查需求对齐（q1-intent）、边界与失败路径（q2-correctness）、测试是否真的证明了场景（q3-evidence）、技术设计与架构偏好（q4-design）；Q3 用完整输入和逐 lens 回执。发现 P0/P1 后登记 issue 并交 x-fix 批量修复，主 agent 用反例测试、全量测试和 xdev check 关闭 issue。
---

# x-qa-gate · 独立审查

## 路由

`xdev check <task>` 通过后进入（旧 `spec_version: 3` 契约包为 `xdev verify` exit 0）。常规 task 读 checklist 头部的 `risk:`（x-req 按任务行算出）：

| risk | 审查 |
|---|---|
| qdev 单文档 | 写了场景按 Q1；只记变更、没写场景的不审。reviewer 读 task 的①–⑤代替 checklist |
| Q0 | 不派 reviewer。`xdev check` 通过即交付 |
| Q1 | 一个精简 reviewer：q1-intent、q3-evidence、q4-design |
| Q2 | 一个精简 reviewer：四个 lens 全做 |
| Q3 | 一个完整 reviewer：四个 lens 全做，读完整输入，逐 lens 分段回执 |

机械项（编号、状态、场景→用例→测试是否存在、测试是否通过、改动行覆盖率、真实性检查记录）已由 `xdev check` 核对，测试代码是否造假已由测试真实性检查做过，reviewer 都不重复，只做剩下的判断。

## 四个 lens

- **q1-intent**：实现是否对齐用户原始要求、已确认的场景和 C 约束、既有公开接口和声明的改动范围；有没有做了没要的、漏了要的。
- **q2-correctness**：非法输入、边界条件、失败路径、状态转换、缓存、并发、幂等和资源清理是否正确。
- **q3-evidence**：用例对应表里的测试，测的内容是否对得上场景的 THEN 和 C 的禁止结果（有没有漏掉某个预期结果、测的是不是场景说的那件事）；人工验证记录是否有步骤和实际观察；覆盖率排除标记的理由是否成立；场景回指写 None 的行理由是否成立；测试真实性检查里“不采纳”的理由是否成立。测试代码本身有没有造假（重写生产逻辑、mock 掉被测对象、断言恒真等）已由 x-dev 的 [测试真实性检查](../x-dev/references/test-integrity.md) 做过，不重复。
- **q4-design**：实现是否落实了 tech-design 的 D 机制和 [共用开发规范](../x-tech-design/references/development-rules.md) R1–R7，是否符合项目的 [架构偏好](../x-tech-design/templates/architecture-preferences.md) 文件（默认 `docs/architecture.md`，没有就跳过这一项）。核对方法按 [x-verify-tech](../x-verify-tech/SKILL.md) 第 1–2 节：先列约束，再对照代码；能跑的检查实际跑，语义判断写明文件、调用链和理由。

## 输入

| risk | reviewer 必读 |
|---|---|
| Q1 / Q2 | `git diff <代码基线>` + checklist（含「结果」）+ 被回指的场景与 C + 本轮 D + 架构偏好文件 + 用例对应表里的测试文件 |
| Q3 | 以上全部 + spec 的影响边界与不变量 + tech-design 的建模覆盖 + `evidence/` 原始输出 |

主 agent 给出文件路径、节名、`git diff --stat <代码基线>`、`git diff --name-only <代码基线>` 和按需 diff 命令。reviewer 按需读源代码与测试文件。

## 调度纪律

reviewer 等待期间会重复计入主 agent 的上下文，按下面做保持独立并省 token：

1. 派 reviewer 前一次性组装完整 prompt：任务边界、输入路径、diff 命令、四个 lens 的要求和输出格式。reviewer 只凭这份 prompt 和工作区完成审查。
2. reviewer 不继承主 agent 的对话历史（Codex 用 `fork_turns: "none"`），只创建一次、只跑一个 turn；拿到回执后结束，修复后不发回原 reviewer，也不重复派同角色。
3. 等待超时先给用户一条短状态，再继续等。
4. Q3 reviewer 先独立做完每个 lens 的候选清单，再合并同根因问题；一个 lens 的结论不能替代另一个 lens 的检查。

## Review 纪律

- reviewer 只读，只返回回执；改动统一走 x-fix。
- 一轮穷尽检查后一次返回全部问题候选；每个 lens 声明“已检查范围内无其他 P0/P1”。
- 每条候选固定字段：`lens`（q1-intent / q2-correctness / q3-evidence / q4-design）、`task`（可写 `T2,T3`）、`severity`（P0/P1/P2）、`loc`（`file:line`）、`msg`（单条问题）和证据。不写 issue 编号。
- 严重度：**P0** 会让用户拿到错误结果、丢数据、越权或无法使用，必须有位置和可复现依据，证据不全就降为 P1；**P1** 需求或设计没落实、测试证明不了场景、违反架构偏好、边界或失败路径有确定缺陷；**P2** 不影响正确性的改进建议。P0 或未处置的 P1 使本轮不通过；P2 只登记。

## issue 登记

`XDEV_SKILL_DIR` 指当前加载的 `x-dev/SKILL.md` 所在目录。主 agent 按 reviewer 返回顺序逐条串行执行：

```text
python3 "${XDEV_SKILL_DIR}/scripts/xdev.py" flag <task-dir> --task T2,T3 --severity P0 \
    --loc src/a.py:10 --msg "空输入未处理" [--new-round] --json
```

1. 本轮第一条加 `--new-round`，后续追加到同一 ledger。
2. 保存返回的 `issue`、`downgraded`、`report`、`recovered`，把 issue 编号写进交给 x-fix 的问题映射。
3. `recovered:true` 表示补完了上一笔中断的登记，用原参数再调一次。
4. `flag` 是 issue ledger 和 P0/P1 行降为 `[!] 🔴` 的唯一写入口；reviewer、子 agent、x-fix 不碰这两处。内容没变化时不建 checklist 临时文件，实际降级用固定的 `.dev-checklist.md.flag.tmp` 原子替换，提交或恢复后清理。
5. 本轮没有问题就不建 ledger，直接输出通过回执。
6. qdev 单文档没有 checklist，不调 `flag`：主 agent 把问题按顺序编号 issue-1、issue-2… 写进⑤「问题与处置」，交 x-fix。

## 回流

有 P0/P1 时，主 agent 把带 `issue-<n>` 的完整问题映射交 x-fix 一次修完。关闭按这个顺序：

1. x-fix 交回：每条 issue 的聚焦反例测试通过，`xdev coverage` 通过（全量测试与回归、改动行覆盖率仍 100%）。
2. x-fix 新增或改了测试时，主 agent 确认 `xdev coverage` 是在测试改完之后跑的，再按 [测试真实性检查](../x-dev/references/test-integrity.md) 派一个轻量子 agent 检查，运行 `xdev integrity`。
3. 主 agent 核对以上各项后，把被 `flag` 降为 `[!] 🔴` 的行改回 `[x] 🟢`。
4. 主 agent 运行 `xdev check`，通过才算关闭（旧契约包为一次完整 `xdev verify`）。不通过就把行再降回 🔴，问题交下一轮。

不把修复发回原 reviewer。修复扩大到新文件或改了公开接口签名时，另派一个裁剪 reviewer 只看新增部分，同样只跑一个 turn。`reports/.fix-counter` 记批量修复轮数（x-fix 每轮递增），上限 3 轮；最终通过后写回 0。

## 回执与状态

通过时输出：

```text
✅ 独立审查通过 · <task> · risk Q1/Q2/Q3 · lens q1+q3+q4（Q2/Q3 加 q2）· P0 ×0 · P1 ×0 · P2 ×N
```

不通过时列出 issue 编号、严重度、行、位置和 x-fix 去向。最终通过后，主 agent 确认问题已关闭，把行升为 `[x] ✅`，在 checklist「问题与处置」记下每条 issue 的处置。
