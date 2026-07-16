# xdev-orchestration-engine · 模块/组件图

> 来源：x-req 阶段产出。README.md 是文字事实源，本文件是架构拆分的只读视图——模块、边界或任务切分变化时同步更新。
>
> **查看与缩放**：GitHub 渲染 mermaid 自带缩放/平移控件；VS Code 建议安装 Mermaid Chart（官方）或 Markdown Preview Enhanced 插件。

图例：🔵 P0 阻塞性/核心 · 🟠 P1 必须完成/主要 · ⚪ P2 增强/辅助

```mermaid
flowchart TD
  classDef p0 fill:#E8F1FE,stroke:#0071E3,color:#1D1D1F,stroke-width:1.5px
  classDef p1 fill:#FFF4E5,stroke:#FF9500,color:#1D1D1F,stroke-width:1.5px
  classDef p2 fill:#F2F2F7,stroke:#8E8E93,color:#1D1D1F,stroke-width:1.5px
  classDef existing fill:#FFFFFF,stroke:#8E8E93,color:#1D1D1F,stroke-width:1px,stroke-dasharray:4 2

  %% 写图守则：
  %% 1. 节点格式：ID["名称<br/>P0/P1/P2 · 一句话职责"]:::p{0|1|2}
  %% 2. 实线 -->（强依赖）；虚线 -.->（弱依赖、可选、调起、数据回流）
  %% 3. 单图节点上限 ~12：超限先压缩同质节点（×N）
  %% 4. subgraph 一律按模块划分：一个模块一个框，框线即模块边界
  %% 5. 模块清单和架构单元必须与 README.md 完全一致——这里是只读视图，README 才是事实源
  %% 6. 虚线框（existing class）= 现有不改动的部分；实线框 = 本 task 新增/改造

  subgraph Tool["确定性工具层（tools/xdev.py）"]
    Main["main 子命令分发器<br/>P0 · add_subparsers 入口"]:::p0
    Validate["validate[现有]<br/>P2 · spec/change 结构校验，不动"]:::existing
    Status["status[新增]<br/>P0 · checklist 解析 + token 状态 + JSON"]:::p0
    Graph["graph[新增]<br/>P0 · 拓扑排序 + 环检测 + JSON"]:::p0
    Parse["first_table/col_values/cells[现有复用]<br/>P0 · 表格解析基础函数"]:::existing
  end

  subgraph Doc["文档层"]
    Checklist["dev-checklist.md<br/>P0 · 被解析对象，任务/状态/依赖事实源"]:::p0
    Template["x-req templates/dev-checklist.md<br/>P1 · 格式定义，token+emoji 双轨"]:::p1
  end

  subgraph Skill["skill 层"]
    XDev["x-dev SKILL.md<br/>P1 · 调用方，按 ready 派子 agent"]:::p1
    SubAgent["子 agent ×N<br/>P1 · 按 parallel_batches 并行开发"]:::p1
  end

  Readme["项目 README.md<br/>P2 · 编排引擎说明"]:::p2

  %% 解析复用：status/graph 都依赖现有解析函数
  Main --> Status
  Main --> Graph
  Main --> Validate
  Status --> Parse
  Graph --> Parse
  %% graph 复用 status 的解析（T2→T1 依赖）
  Graph -.->|"复用解析"| Status

  %% 数据流：文档被工具解析
  Checklist -.->|"被读"| Parse
  Template -.->|"定义格式"| Checklist

  %% 调用链：x-dev 调 status/graph 拿 JSON
  XDev -->|"status --json"| Status
  XDev -->|"graph --json"| Graph
  Status -.->|"progress JSON"| XDev
  Graph -.->|"ready/batches JSON"| XDev
  XDev -->|"按 ready 派发"| SubAgent
  %% 状态回流：子 agent 完成后主流程更新 checklist token
  SubAgent -.->|"主流程更新 token"| Checklist

  Readme -.->|"文档说明"| Tool
```
