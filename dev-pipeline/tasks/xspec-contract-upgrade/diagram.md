# xspec-contract-upgrade · 模块/组件图

> 来源：x-req 阶段产出。README.md 是文字事实源，本文件是架构拆分的只读视图——模块、边界或任务切分变化时同步更新。
>
> **查看与缩放**：GitHub 渲染 mermaid 自带缩放/平移控件；VS Code 建议安装 Mermaid Chart（官方）或 Markdown Preview Enhanced 插件。

图例：🔵 P0 阻塞性/核心 · 🟠 P1 必须完成/主要 · ⚪ P2 增强/辅助

```mermaid
flowchart TD
  classDef p0 fill:#E8F1FE,stroke:#0071E3,color:#1D1D1F,stroke-width:1.5px
  classDef p1 fill:#FFF4E5,stroke:#FF9500,color:#1D1D1F,stroke-width:1.5px
  classDef p2 fill:#F2F2F7,stroke:#8E8E93,color:#1D1D1F,stroke-width:1.5px

  Tool["工具层（格式法律）<br/>P0 · 场景契约 profile 分派（spec7/task 新契约、capability/change 原契约）+ spec_tier 分档 V1 + V2 死链语义 + V5 名称回指"]:::p0
  Tpl["x-spec 模板层<br/>P0 · 01 模板 DoD 段 R/S 化 + 02/90 回指改 Requirement 名 + TEMPLATE_GUIDE 改写"]:::p0
  Flow["x-spec 流程层<br/>P1 · 步骤 6 tier 化 + 6.2 裁判降级与按档位审 + update 三纪律（可执行定义）"]:::p1
  Smoke["测试层（样例冒烟）<br/>P1 · 新契约正反样例 + lite/full 分档 + OpenSpec 存量回归 + 悬空/重名 + 路径族 + 75 测试全绿"]:::p1

  Tool --> Tpl
  Tool -.-> Flow
  Tool --> Smoke
  Tpl --> Smoke
```
