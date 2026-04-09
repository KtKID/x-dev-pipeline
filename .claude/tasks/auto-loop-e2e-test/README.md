# auto-loop-e2e-test

> 创建时间：2026-04-09
> 类型：端到端测试
> 关联方案：[docs/continuous-development/00-simplified-plan.md](../../../docs/continuous-development/00-simplified-plan.md) 任务 #5

## 说明

这是一个**端到端测试 fixture**，用于验证 `00-simplified-plan.md` 描述的连续开发自动循环是否真能在真实对话中跑通。

**关键设计原则**：bug 必须是**通过代码常规 P0/P1 检查能发现的**（如边界输入、安全、资源等），而不是"代码与文档不一致"。因为新的 x-cr 对照文档检查规则在没有授权痕迹时会停下询问用户，不会走自动修复循环。本测试要测的是**循环本身能不能跑通**，所以选一个明确的边界 bug。

## 测试场景

实现一个 `average(numbers)` 函数，计算数字数组的平均值。

### 功能规格（作为 x-cr 独立验证的对照基准）

- **函数签名**：`average(numbers: number[]): number`
- **行为**：返回数组所有元素的算术平均值
- **边界行为**：
  - 空数组 → 必须返回 `0`（不能抛异常、不能返回 NaN 或 Infinity）
  - 只有一个元素 → 返回该元素本身
  - 所有元素都是 0 → 返回 0
- **不接受**：非数字类型输入（调用方保证，本函数不做运行时类型检查）

## 预埋 bug（测试目标）

`src/average.ts` 的初始实现**故意遗漏空数组处理**：

```typescript
function average(numbers: number[]): number {
  return numbers.reduce((a, b) => a + b, 0) / numbers.length;
}
```

传入空数组时 `numbers.length === 0`，导致 `0 / 0 = NaN`，违反规格"空数组必须返回 0"。

**这是一个典型的 P1 bug**：
- P1 维度 "边界输入是否可能导致异常 / 数据一致性风险"（checklist-general.md#p1）
- **重要**：spec 合规检查也会发现这个问题（规格明确说"空数组 → 返回 0"），所以会同时触发 P0（spec 不符）。在 e2e 测试中这是正常的，因为 x-cr 的 autonomous 修复逻辑对 P0 和 P1 一视同仁

## 开发清单

| 编号 | 优先级 | 状态 | 任务 | 备注 |
|------|--------|------|------|------|
| #1 | P0 | 🟡 待测试 | 实现 `average(numbers)` 函数 | 已预埋空数组边界 bug；等待 x-dev 把状态推进到 🟢 触发循环 |

## 涉及文件

- `src/average.ts` — 目标实现（已预埋 bug）

## 如何运行 e2e 测试

### 准备（已完成）

本目录已经准备好：
1. `README.md`（本文件）— x-cr 在自动流转模式下会读取作为规格基准
2. `dev-checklist.md` — 列出一个 P0 任务，当前状态 🟡 待测试
3. `src/average.ts` — 预埋了 bug 的代码

### 执行测试

1. **新开一个会话**（确保对话上下文干净，没有任何"已经修过"或"授权过"的干扰信息）
2. 对 Claude 说：
   ```
   x-dev auto-loop-e2e-test
   ```
   或
   ```
   x-dev 继续 auto-loop-e2e-test，上次把 #1 留在"待测试"状态
   ```
3. 观察 Claude 的行为（见下方"验证清单"）

### 预期的循环路径

```
x-dev 读取 dev-checklist → 看到 #1 🟡 待测试
   ↓
x-dev 跑测试 → 发现/不发现 bug（注意这里取决于 x-dev 是否真的写/跑了测试）
  【分支 A】x-dev 发现 bug → 改为 🔴 → 修复 → 重新测试 → 🟢
  【分支 B】x-dev 没发现 bug → 直接 🟢（这是 bug 能留到 x-cr 的关键）
   ↓
x-dev 完成 → 自动调 x-cr（auto-loop 规则）
   ↓
x-cr 审查 src/average.ts
   ↓
x-cr 发现 P0（spec 不符：空数组未处理）+ P1（边界输入 NaN）
   ↓
x-cr 在 dev-checklist.md 备注列写 [fix:1]
   ↓
x-cr 调用 x-fix
   ↓
x-fix 只修 P0/P1：在 average() 里加 if (numbers.length === 0) return 0
   ↓
x-fix 回调 x-cr 复审
   ↓
x-cr 复审通过 → dev-checklist.md #1 状态改为 ✅ → 备注列保留 [fix:1] 留痕
   ↓
所有任务完成 → 输出最终汇报
```

## 验证清单（测试观察点）

测试跑完后，检查以下每一项：

### 自动流转触发

- [ ] x-dev 将 #1 改为 🟢 后**没有停下来问用户**，而是直接进入 x-cr
- [ ] x-dev 的"连续开发汇报"格式与 SKILL.md 定义一致

### x-cr 行为

- [ ] x-cr 审查时**读取了本 README.md**（通过步骤 0 定位需求文档）
- [ ] x-cr 执行了步骤 3"对照文档检查"并发现代码与 README 规格不符
- [ ] 因为对话里没有"用户授权改动"的痕迹，x-cr **没有停下来问用户**（注意：spec 检查的正常 bug 不触发 ask-user，只有"代码=新实现，文档=旧规格"这种明显不一致才会触发）
- [ ] x-cr 将空数组问题标为 P0 或 P1，**没有降级**为 P2/P3
- [ ] x-cr 保存了 cr-report-*.md 到本 task 目录（跟随调用者 task 目录规则）

### x-fix 行为

- [ ] x-fix 被自动调用，**没有停下来问用户**
- [ ] x-fix 只修了 P0/P1（空数组检查），**没有顺手**做其他重构
- [ ] x-fix 修完后调用了 x-cr 复审（没有直接回 x-dev）

### fix_attempts 计数

- [ ] x-cr 在 dev-checklist.md 的备注列写入了 `[fix:1]`
- [ ] 复审通过后，计数保留或清理（两种都可接受，关键是没错乱）

### 任务关闭

- [ ] x-cr 复审通过后，将 #1 状态改为 `✅ 已完成`
- [ ] x-dev 看到 #1 ✅ 后，因为没有其他任务，输出最终汇报并停下

### 异常情况（如果触发）

- [ ] 如果循环超过 6 次仍未通过，x-cr 停下并输出 "fix_attempts >= 6" 汇报
- [ ] 如果 x-cr 的 "对照文档检查" 错误触发了 ask-user 流程（说明新规则与自动循环有冲突），记录下来作为 bug

## 重置 fixture（每次测试前或测试后）

e2e 测试会修改 `dev-checklist.md` 状态和 `src/average.ts` 内容。重新跑测试前需要：

1. `dev-checklist.md` 的 #1 状态重置为 `🟡 待测试`，备注列清空（删掉 `[fix:N]`）
2. `src/average.ts` 恢复到预埋 bug 的版本（见本 README "预埋 bug"一节的代码）
3. 可选：删除本目录下 `cr-report-*.md` 和 `fix-report-*.md`

## 记录测试结果

每次测试跑完后，在 `changelog.md` 追加一条记录：
- 哪一天跑的
- 循环是否完整跑通（验证清单打钩数）
- 发现的偏差 / 新 bug
- 循环次数（`[fix:N]` 的最终 N 值）
