# x-spec 模板说明

本文件是 x-spec 文档模板的格式正源。`SKILL.md` 负责判断、收敛、调度和审核；本文件负责产物字段、路径规则、图表规则和模板写法。

## 核心写法

所有关键结论都采用“为什么优先”的结构：

| 字段 | 写法 |
|------|------|
| 为什么重要 | 说明该判断保护的用户结果、系统边界或协作效率 |
| 判断依据 | 引用用户输入、代码、文档、配置、日志、测试或明确推断 |
| 缺失后果 | 说明继续推进会产生的偏差、返工、风险或维护成本 |
| 产物落点 | 写明该判断进入哪个 spec 文件、哪个模块或哪个 task |

“怎么做”写在方案、模块、数据、验证和 task 段里；“为什么这样做”必须先出现，并且每个关键目标都要能追溯到依据。

## 文件职责

| 文件 | 负责内容 |
|------|---------|
| `README.md` | spec 导航、Framing Summary、推荐方案、模块导航、当前建议 |
| `01-goals-and-boundaries.md` | 需求本质、目标充分性判断、DoD、范围、约束、不变量、追溯矩阵 |
| `02-module-breakdown.md` | 模块划分、边界类、职责、依赖、接口、复用/新建、风险 |
| `04-data-and-state.md` | 核心实体、数据归属、状态流转、持久化、共享结构 |
| `05-validation-and-evolution.md` | 验证目标、smoke/e2e、单元/契约/边界测试、演进路线 |
| `90-task-map.md` | 模块到 x-req task 的映射、排序依据、风险和前置条件 |
| `diagrams.md` | 全量 mermaid 图集，包含总览、E2E 验证链路、模块局部图 |

## Framing Summary 落点

头脑风暴模式产生的结论按下列规则写入模板：

| 头脑风暴结论 | 写入位置 |
|-------------|---------|
| 需求本质 | `README.md` → Framing Summary；`01-goals-and-boundaries.md` → 需求本质 |
| 第一性原理推导 | `01-goals-and-boundaries.md` → 第一性原理推导 |
| 目标充分性判断 | `01-goals-and-boundaries.md` → 目标充分性判断 |
| 方案空间与推荐方案 | `README.md` → 方案结论；按需补入 `02-module-breakdown.md` |
| 关键约束与不变量 | `01-goals-and-boundaries.md` → 关键约束 / 系统不变量 |
| 模块边界判断 | `02-module-breakdown.md` → 模块总览 / 模块详情 |
| 数据和状态归属 | `04-data-and-state.md` → 数据归属决策 / 状态流转 |
| 验证和反例 | `05-validation-and-evolution.md` → 验证策略 / 对抗性检验 |
| task 拆分条件 | `90-task-map.md` → Task Map |

## DoD 追溯规则

DoD 追溯矩阵写入 `01-goals-and-boundaries.md`，作为验收目标和模块设计之间的闭环证据。

每条 DoD 都要写清：

| 字段 | 写法 |
|------|------|
| DoD 条目 | 可验证的完成条件 |
| 需要哪些模块 | 支撑该条件的模块集合 |
| 需要哪些 task | 进入 x-req 后可拆出的 task |
| 判断依据 | 来自需求要点、用户验收、代码现状或系统约束 |
| 缺失后果 | 支撑缺口造成的用户结果缺口或实现风险 |
| 状态 | 待实现 / 方案确认 / 可进入 x-req / 已覆盖 |

追溯检查规则：

1. 每条 DoD 至少对应一个模块或明确标为待确认。
2. 每个进入实现链路的模块至少回指一个 DoD。
3. 支撑性模块可以标为“支撑模块”，并写清支撑哪个 DoD 或哪个系统不变量。
4. 发现追溯缺口时，在状态列写明补模块、调 DoD、保留探索或移出范围。

## 风险与 PoC 落点

风险标注写入 `02-module-breakdown.md`，PoC 和开发排序写入 `90-task-map.md`。

模块风险字段：

| 字段 | 写法 |
|------|------|
| 风险等级 | 低 / 中 / 高 |
| 风险类型 | 可行性 / 性能容量 / 依赖稳定性 / 数据兼容 / 权限安全 / 运维回滚 |
| 风险说明 | 风险是什么，触发条件是什么 |
| 判断依据 | 代码证据、历史问题、依赖文档、数据规模、用户约束 |
| 为什么重要 | 该风险影响哪个 DoD、系统不变量或交付路径 |
| 缺失后果 | 延后验证会造成的返工、阻塞或质量风险 |
| PoC 建议 | 需要先实验时写实验目标、最小验证方式、通过标准 |

Task Map 排序规则：

1. 高风险且会影响主链路的模块排在前面。
2. 被多个模块依赖的边界类优先稳定。
3. PoC task 写明实验目标、通过标准和失败后的备选方向。
4. 可进入 x-req 的 task 必须能回指 DoD 和模块边界。

## 路径引用规则

spec 需求包必须能整体移动，包内链接使用当前位置可解析的相对路径。

- 文档间 Markdown 链接只使用当前需求包内的相对路径：`./README.md`、`./diagrams.md`、`./02-module-breakdown.md#模块-a`
- 包内文档由 `docs/spec/README.md` 索引进入；包内文档之间保持同层相对链接
- 代码文件、脚本、配置路径写成不可点击的 repo 逻辑路径：`repo:src/foo/bar.ts`、`repo:package.json`
- 生成文档中排除会随移动失效的链接形态：`../../`、`docs/spec/<spec-name>/...`、绝对路径、`file://`、Windows 盘符路径

## 图表规范

所有图统一写入 `diagrams.md`，其他文档在对应位置引用 `diagrams.md` 的小节。

| 节 | 放什么图 | mermaid 类型 |
|----|---------|-------------|
| 总览 | 模块级依赖图：每个模块一个节点，只画模块间关系；节点写中文模块作用和关键类/函数名 | `flowchart TD` |
| E2E 测试链路 | 从测试数据准备、用户动作、系统处理到断言的验证路径 | `flowchart LR` |
| 模块节 | 局部组件依赖图，模块内组件包在 subgraph 内，邻居模块压成单节点 | `flowchart TD` |
| 模块节 | 核心流程图或时序图 | `flowchart LR/TD` / `sequenceDiagram` |
| 模块节 | 状态流转图 | `stateDiagram-v2` |
| 模块节 | 数据关系图 | `flowchart LR` |

图表写法：

1. 总览节点格式：`ID["模块名<br/>中文模块作用<br/>类/函数：ClassName.methodName()"]:::module`
2. 实线 `-->` 表示强依赖；虚线 `-.->` 表示弱依赖、可选依赖或调起关系
3. 单图节点上限约 12 个；超限时压缩同质节点，继续超限时拆到模块局部图
4. `subgraph` 按模块划分；一个模块一个 subgraph，框线即模块边界，边界类节点放在框内第一位
5. 同质重复节点压成 `×N`
6. 图与 `02-module-breakdown.md`、`04-data-and-state.md`、`05-validation-and-evolution.md` 保持一致
7. 数据关系图只在节点内保留主键、外键、状态/类型字段；完整字段清单写入 `04-data-and-state.md`

Flowchart / 局部组件图使用以下节点类：

```text
classDef p0 fill:#E8F1FE,stroke:#0071E3,color:#1D1D1F,stroke-width:1.5px
classDef p1 fill:#FFF4E5,stroke:#FF9500,color:#1D1D1F,stroke-width:1.5px
classDef p2 fill:#F2F2F7,stroke:#8E8E93,color:#1D1D1F,stroke-width:1.5px
```

- P0（蓝）= 核心 / 阻塞性
- P1（橙）= 主要 / 必须完成
- P2（灰）= 辅助 / 可选

数据关系图使用紧凑实体节点：

```text
%%{init: {"theme": "base", "themeVariables": {"background": "#181A1F", "primaryColor": "#242933", "primaryTextColor": "#F5F7FA", "primaryBorderColor": "#6BA7FF", "lineColor": "#AAB4C0", "textColor": "#F5F7FA", "edgeLabelBackground": "#181A1F"}}}%%
classDef entity fill:#1F2633,stroke:#6BA7FF,color:#F5F7FA,stroke-width:1.5px
classDef supporting fill:#191F29,stroke:#AAB4C0,color:#F5F7FA,stroke-width:1.2px
```

节点格式：`Entity["ENTITY<br/>────────<br/>PK id<br/>FK parent_id<br/>status"]:::entity`。关系格式：`A -->|owns 1:N| B`。

## 模块边界规则

- 每个模块对外暴露一个边界类作为唯一入口：业务域用 `<模块>Service`、资源/生命周期域用 `<模块>Manager`、外部系统用 `<系统>Client` / `<系统>Gateway`、数据持久层用 `<实体>Repository`
- 模块内功能由边界类收口调用；跨模块代码通过边界类调用
- 模块外代码只 import 边界类；内部实现放在私有文件、`internal/` 目录或未导出的模块内
- 内部能力需要对外暴露时，优先给边界类补委托方法；通用能力提取到底层共享模块；批量外露内部能力时回到 x-spec 重画边界

## 模板审核标准

主 agent 审核时按 P0/P1 分级：

| 等级 | 判定 |
|------|------|
| P0 | 需求要点漏写、DoD 支撑缺口、模块回指缺口、缺 spec 必需文件、路径不可移动、推荐方案缺判断依据 |
| P1 | 图表格式偏差、字段注释缺失、状态值写法偏差、风险解释不足、模块排序依据偏弱 |

P0 修复后进入下一步；P1 写入收尾参考项。
