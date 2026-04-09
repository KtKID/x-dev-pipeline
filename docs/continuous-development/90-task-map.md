# Task Map

| 模块 | 建议 task 名 | 是否创建 task | 前置依赖 | 当前状态 |
|------|--------------|----------------|----------|----------|
| x-finish | `x-finish-skill` | **是** | 无 | 可进入 x-req |
| x-req-ext | `x-req-design-doc` | **是** | 无 | 可进入 x-req |
| x-drive | `x-drive-skill` | **是** | x-finish + x-dev-ext | 方案确认（新增：六类停止条件 + 唤醒机制） |
| x-dev-ext | `x-dev-subagent-mode` | 是（合并到 x-drive） | x-finish | 方案确认（新增：四状态机 + 模型选择策略） |
| session-start hook | `session-hook-design` | 是 | x-drive | 探索中 |

## 推荐开发顺序

### 第一批（无依赖，可并行）

| task 名 | 说明 |
|---------|------|
| `x-finish-skill` | 新增收尾决策 skill，独立性强 |
| `x-req-design-doc` | 扩展 x-req，输出设计文档 |

### 第二批（依赖第一批）

| task 名 | 说明 |
|---------|------|
| `x-drive-skill` | 连续编排层，含 batch 模式（无需 subagent） |
| `x-dev-subagent-mode` | 合并到 x-drive，作为可选执行模式 |

### 第三批（依赖前两批）

| task 名 | 说明 |
|---------|------|
| `session-hook-design` | 配置层，探索验证 |

## 元规则检查清单（各 task 必须体现）

每次开发新的 skill 或扩展时，对照检查：

- [ ] **无等待人类设计**：该阶段是否有硬编码循环，不依赖用户主动询问？
- [ ] **implementer 状态机**：subagent 模式是否实现了 DONE/DONE_WITH_CONCERNS/BLOCKED/NEEDS_CONTEXT 四状态？
- [ ] **spec 合规独立验证**：reviewer 是否必须独立验证，不信任 implementer 报告？
- [ ] **reviewer 硬编码循环**：发现问题后是否无条件进入修复→重新审核，不给人类等待窗口？
- [ ] **checkpoint 强制执行**：是否设定了固定频率强制向用户汇报进度？

## 完整 pipeline 改造路线图

```
阶段 1：独立上线
├─ x-finish-skill        → 完成
└─ x-req-design-doc      → 完成
  ↓
阶段 2：核心流水线
├─ x-drive-skill（batch）→ 完成
└─ x-dev-subagent-mode   → 完成
  ↓
阶段 3：持续增强
└─ session-hook-design   → 完成
```
