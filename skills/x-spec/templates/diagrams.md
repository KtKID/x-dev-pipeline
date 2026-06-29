# <SPEC_NAME> · 图集

> 本 spec 的唯一图源：所有 mermaid 图集中于此，按模块分节。02/03/04 是文字事实源，本文件是只读视图——增减模块/组件时同步更新对应节。
>
> **查看与缩放**：GitHub 渲染 mermaid 自带缩放/平移控件；VS Code 建议安装 Mermaid Chart（官方）或 Markdown Preview Enhanced 插件以支持缩放。

<!-- 模板说明：skills/x-spec/templates/TEMPLATE_GUIDE.md。生成产物时删除本注释。 -->

## 目录

- [总览](./diagrams.md#总览)
- [E2E 测试链路](./diagrams.md#e2e-测试链路)
- [模块 A](./diagrams.md#模块-a)
- [模块 B](./diagrams.md#模块-b)

图例：总览节点写模块名、中文作用、关键类/函数；局部组件图可按 🔵 核心 · 🟠 主要 · ⚪ 辅助 配色。

## 图类型规范

| 节 | 放什么图 | mermaid 类型 |
|----|---------|-------------|
| 总览 | 模块级依赖图：每个模块一个节点，只画模块间关系；节点写中文模块作用和关键类/函数名 | `flowchart TD` |
| E2E 测试链路 | 从测试数据准备、用户动作、系统处理到断言的验证路径 | `flowchart LR` |
| 模块节 | 局部组件依赖图、核心流程图、时序图、状态流转图、数据关系图 | `flowchart TD/LR` / `sequenceDiagram` / `stateDiagram-v2` |

写图顺序：先总览，再 E2E 测试链路，再按模块拆局部图。单图节点约 12 个以内；更大的图拆到模块节。

## 总览

[模块级依赖图：每模块一个节点，只画模块间关系；每个节点写中文模块作用和关键类/函数名]

```mermaid
flowchart TD
  classDef module fill:#E8F1FE,stroke:#0071E3,color:#1D1D1F,stroke-width:1.5px
  classDef support fill:#F2F2F7,stroke:#8E8E93,color:#1D1D1F,stroke-width:1.5px

  %% 写图守则：
  %% 1. 总览节点格式：ID["模块名<br/>中文模块作用<br/>类/函数：ClassName.methodName()"]:::module
  %% 2. 实线 -->（强依赖）；虚线 -.->（弱依赖/可选/调起）
  %% 3. 单图节点上限 ~12：超限先压缩同质节点（×N），还超就拆图——
  %%    总览只画模块级，细节下沉到模块节的局部图
  %% 4. subgraph 一律按模块划分：一个模块一个框，框线即模块边界，
  %%    边界类节点放框内第一位；邻居模块压成单节点放框外
  %% 5. 同质重复节点压成单节点 + "×N" 后缀，避免图爆炸
  %% 6. 图与 02/03/04 文字描述完全一致——这里是只读视图

  ModA["需求入口<br/>收集用户需求并确定任务边界<br/>类/函数：RequirementService.collect()"]:::module
  ModB["方案拆解<br/>拆分模块职责和开发清单<br/>类/函数：SpecPlanner.buildModules()"]:::module
  ModC["交付校验<br/>汇总验收条件和风险检查<br/>类/函数：AcceptanceChecker.validate()"]:::support

  ModA --> ModB
  ModA -.-> ModC
```

## E2E 测试链路

[从测试数据准备到断言的端到端验证路径；节点写动作、入口、关键类/函数或断言点]

```mermaid
flowchart LR
  classDef setup fill:#E8F1FE,stroke:#0071E3,color:#1D1D1F,stroke-width:1.5px
  classDef action fill:#FFF4E5,stroke:#FF9500,color:#1D1D1F,stroke-width:1.5px
  classDef assert fill:#F2F2F7,stroke:#8E8E93,color:#1D1D1F,stroke-width:1.5px

  Seed["准备测试数据<br/>TestDataFactory.createThread()"]:::setup
  Act["执行用户动作<br/>CLI: x-spec create"]:::action
  Service["业务处理<br/>SpecPlanner.buildModules()"]:::action
  Persist["写入产物<br/>DiagramWriter.write()"]:::action
  Check["断言结果<br/>diagram.md 存在<br/>包含总览和数据关系"]:::assert

  Seed --> Act --> Service --> Persist --> Check
```

## 模块 A

[该模块的局部图，按需保留小节：组件依赖 / 流程 / 时序 / 状态 / 数据关系，没有内容的小节删掉]

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

### 数据关系

```mermaid
%%{init: {"theme": "base", "themeVariables": {"background": "#181A1F", "primaryColor": "#242933", "primaryTextColor": "#F5F7FA", "primaryBorderColor": "#6BA7FF", "lineColor": "#AAB4C0", "textColor": "#F5F7FA", "edgeLabelBackground": "#181A1F"}}}%%
flowchart LR
  classDef entity fill:#1F2633,stroke:#6BA7FF,color:#F5F7FA,stroke-width:1.5px
  classDef supporting fill:#191F29,stroke:#AAB4C0,color:#F5F7FA,stroke-width:1.2px

  THREAD["THREAD<br/>────────<br/>PK thread_id<br/>FK source_id"]:::entity
  MESSAGE["MESSAGE<br/>────────<br/>PK message_id<br/>FK thread_id<br/>role"]:::entity
  RUN["RUN<br/>────────<br/>PK run_id<br/>FK thread_id<br/>status"]:::supporting

  THREAD -->|contains 1:N| MESSAGE
  THREAD -->|starts 1:N| RUN
```

## 模块 B

[同上结构，按需]
