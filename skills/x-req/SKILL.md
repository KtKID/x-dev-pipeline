---
name: x-req
description: |
  需求与开发准备 skill。把确认后的需求直接写成可执行的 task 包，使用 xdev 的 scaffold、instructions 和 validate 完成机械闭环。
  触发场景：“帮我处理需求”、“梳理需求”、“开个 task”、“新建任务”、“这个功能怎么做”、“帮我拆一下”、`x-req`、`x-plan`（重定向），以及用户提供需求文档路径或描述预计超过 2 小时的功能。
  适用中大型功能、跨模块改动、协议或状态设计；小型局部改动转 x-qdev，架构归属未闭合时先转 x-spec。
---

# x-req — 精简规划

## 产物与职责

新 task 必需 `README.md` 与 `dev-checklist.md`。涉及至少三个模块或用户明确要求图时加入 `diagram.md`。README 记录需求与更新摘要，dev-checklist 跟踪执行状态，dev-report 保存实现证据，git history 保存仓库变更。

## 路由与现状调查

1. 定位目标 task：新建使用 `dev-pipeline/tasks/<name>/`；更新读取同目录已有活跃产物。
2. 阅读用户请求、关联 spec、相关模块文档和代码入口，明确需求、边界类、公开契约、数据流、失败路径和验证方式。
3. 小型单模块任务转 `/x-qdev`；模块归属、状态模型或跨模块边界未闭合时转 `/x-spec`。
4. 更新模式先提炼需求与架构 delta；保留已有无关内容，并在 README 顶部附近写 `updated: YYYY-MM-DD <summary>`。
5. Q3 升级读取源 task 的 README 与 dev-report 作为只读证据。用户未指定名称时新建 `<source-name>-full`，在新 README 写入 `source-qdev: dev-pipeline/tasks/<source-name>`。

## 一次确认

写入前按 `templates/confirmation.md` 展示并等待一次确认。确认内容覆盖：

- 需求要点和归属 spec；
- 核心目标、涉及模块和架构归属；
- 架构拆分策略、依赖、风险与事实源；
- 技术设计、可客观判定的 DoD、Smoke/E2E 路径与自动化测试责任；
- checklist 预览。

用户提出修改时更新确认内容并再次确认；用户取消时结束且不写入文件。

## 已确认后的编写流程

主 agent 直接写 task 产物：

1. 运行 `python3 tools/xdev.py scaffold <task-dir>`；满足图条件时增加 `--with-diagram`。
2. 按 `readme → dev-checklist → diagram（存在时）` 顺序运行 `instructions <artifact-id> --task <task-dir>`，每次先阅读已存在的依赖产物。
3. 依据模板和 instruction 填写内容；删除 HTML 注释，避免把填写规则复制进产物。
4. 运行 `python3 tools/xdev.py validate <task-dir>`；修复 V2、V8–V11 finding，直到退出码为 0。
5. 完成四项判断自审：每条需求已经覆盖；DoD 可由命令、产物、可观察输出或明确人工结果证明；技术设计保持已确认的架构归属；checklist 每行能追溯到架构拆分、契约或依赖。
6. 自审带来内容调整时同步下游产物并重跑 validate。

## 内容规则

- README 是文字事实源：模块、边界与依赖先在 README 表达，diagram 仅作投影。
- DoD 采用可检查的结果；Smoke/E2E 提供围栏命令或 `manual` 标记。
- dev-checklist 使用 `# | 任务 | 涉及文件 | 依赖 | 状态 | fix` 表头与 token+emoji 状态；依赖必须引用表中 task ID。
- `diagram.md` 的 Mermaid 节点标签与 README「涉及模块」保持双向一致。
- 历史 task 已有文件保持原状；活跃规划只更新上述产物。

## 完成汇报

汇报 task 路径、真实产物清单、`validate` 零 finding、四项判断自审结论，以及下一条命令：`x-dev <task-name>`。
