# <SPEC_NAME> · 图集

> 本 spec 的唯一图源：所有 mermaid 图集中于此，按模块分节。02/03/04 是文字事实源，本文件是只读视图——增减模块/组件时同步更新对应节。
>
> **查看与缩放**：GitHub 渲染 mermaid 自带缩放/平移控件；VS Code 建议安装 Mermaid Chart（官方）或 Markdown Preview Enhanced 插件以支持缩放。

## 目录

- [总览](#总览)
- [模块 A](#模块-a)
- [模块 B](#模块-b)

图例：🔵 P0 核心/阻塞 · 🟠 P1 主要/必须 · ⚪ P2 辅助/可选

## 总览

[模块级依赖图：每模块一个节点，只画模块间关系]

```mermaid
flowchart TD
  classDef p0 fill:#E8F1FE,stroke:#0071E3,color:#1D1D1F,stroke-width:1.5px
  classDef p1 fill:#FFF4E5,stroke:#FF9500,color:#1D1D1F,stroke-width:1.5px
  classDef p2 fill:#F2F2F7,stroke:#8E8E93,color:#1D1D1F,stroke-width:1.5px

  %% 写图守则：
  %% 1. 节点格式：ID["名称<br/>P0/P1/P2 · 一句话"]:::p{0|1|2}
  %% 2. 实线 -->（强依赖）；虚线 -.->（弱依赖/可选/调起）
  %% 3. 单图节点上限 ~12：超限先压缩同质节点（×N），还超就拆图——
  %%    总览只画模块级，细节下沉到模块节的局部图
  %% 4. subgraph 一律按模块划分：一个模块一个框，框线即模块边界，
  %%    边界类节点放框内第一位；邻居模块压成单节点放框外
  %% 5. 同质重复节点压成单节点 + "×N" 后缀，避免图爆炸
  %% 6. 图与 02/03/04 文字描述完全一致——这里是只读视图

  ModA["模块 A<br/>P0 · 一句话职责"]:::p0
  ModB["模块 B<br/>P1 · 一句话职责"]:::p1
  ModC["模块 C<br/>P2 · 一句话职责"]:::p2

  ModA --> ModB
  ModA -.-> ModC
```

## 模块 A

[该模块的局部图，按需保留小节：组件依赖 / 流程 / 时序 / 状态 / ER，没有内容的小节删掉]

### 组件依赖

```mermaid
flowchart TD
  classDef p0 fill:#E8F1FE,stroke:#0071E3,color:#1D1D1F,stroke-width:1.5px
  classDef p1 fill:#FFF4E5,stroke:#FF9500,color:#1D1D1F,stroke-width:1.5px
  classDef p2 fill:#F2F2F7,stroke:#8E8E93,color:#1D1D1F,stroke-width:1.5px

  subgraph ModA["模块 A（边界 = subgraph 框线）"]
    SvcA["AService<br/>P0 · 边界类，唯一入口"]:::p0
    CompA1["内部组件 1<br/>P1 · 一句话职责"]:::p1
    CompA2["内部组件 2<br/>P2 · 一句话职责"]:::p2
  end

  ModB["模块 B<br/>邻居，压成单节点"]:::p2

  ModB --> SvcA
  SvcA --> CompA1
  SvcA --> CompA2
```

### 状态流转

```mermaid
stateDiagram-v2
  [*] --> created
  created --> running: 启动
  running --> done: 完成
  running --> failed: 出错
  failed --> running: 重试
  done --> [*]
```

## 模块 B

[同上结构，按需]
