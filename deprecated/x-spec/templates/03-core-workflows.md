# 核心流程与时序

> 跨模块协作（调用顺序、错误路径、异步边界）的唯一载体：02 按模块切块、04 是静态数据，只有这里把"模块之间怎么配合"显性化。流程文字与时序图同文件同源——改一个流程只动本文件。
>
> 默认必有：最小可用路径 1 条（含错误路径），随 01 一起交用户确认；可选：最高风险链路、E2E 验收链路。图表写法见 `TEMPLATE_GUIDE.md`「图表规范」。

<!-- 模板说明：skills/x-spec/templates/TEMPLATE_GUIDE.md。生成产物时删除本注释。 -->

## 流程 1：<最小可用路径名>（必有）

**目标**：[用户做什么 → 系统处理什么 → 用户看到什么，一句话]

**参与模块**：[模块 A（边界类）→ 模块 B（边界类）]

**关键步骤**（文字为真源，图与此一致）：

1. ...
2. ...
3. 失败分支：[哪一步可能失败 → 系统怎么表现 → 用户看到什么]

```mermaid
sequenceDiagram
  actor U as 用户
  participant A as RequirementService
  participant B as SpecPlanner

  U->>A: 发起请求（入口/命令）
  A->>B: buildModules(需求要点)
  alt 成功
    B-->>A: 模块清单
    A-->>U: 展示方案
  else 失败（校验不过 / 依赖缺失）
    B-->>A: 错误语义（原因，不静默）
    A-->>U: 提示与建议动作
  end
```

## 流程 2：<最高风险链路名>（可选，链路风险高时才写）

[同流程 1 结构：目标 / 参与模块 / 关键步骤 / 时序图]

## E2E 验收链路（可选，验收复杂到文字说不清时才画）

[从测试数据准备、用户动作、系统处理到断言的验证路径；与 `./05-validation-and-evolution.md` 的 Smoke/E2E 入口一致]

```mermaid
flowchart LR
  classDef setup fill:#E8F1FE,stroke:#0071E3,color:#1D1D1F,stroke-width:1.5px
  classDef action fill:#FFF4E5,stroke:#FF9500,color:#1D1D1F,stroke-width:1.5px
  classDef assert fill:#F2F2F7,stroke:#8E8E93,color:#1D1D1F,stroke-width:1.5px

  Seed["准备测试数据"]:::setup
  Act["执行用户动作 + 系统处理"]:::action
  Check["断言结果（可观察证据）"]:::assert

  Seed --> Act --> Check
```
